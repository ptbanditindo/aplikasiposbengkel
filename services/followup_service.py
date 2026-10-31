"""Follow-up pelanggan, servis berkala, garansi, dan piutang (Tahap 13).

Pengingat disusun dari data nota (sumber tunggal), lalu disalin ke tabel
`followup_items` agar status, penanggung jawab, dan riwayat perpindahan tidak
hilang. Tidak ada pesan otomatis: tombol follow-up hanya membuka WhatsApp dan
mencatat upaya.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from database.models import (
    FollowupEvent,
    FollowupItem,
    ServiceRecord,
    VehicleOrUnit,
)
from services import payment_service, settings_service, whatsapp_service
from services.auth_service import Operator
from services.customer_service import describe_unit
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import is_valid_whatsapp, mask_phone

JENIS_PROSPEK = "prospek"
JENIS_SERVIS = "servis_berkala"
JENIS_GARANSI = "garansi"
JENIS_PIUTANG = "piutang"
JENIS_VALUES = {JENIS_PROSPEK, JENIS_SERVIS, JENIS_GARANSI, JENIS_PIUTANG}
JENIS_LABELS = {
    JENIS_PROSPEK: "Prospek",
    JENIS_SERVIS: "Servis berkala",
    JENIS_GARANSI: "Garansi",
    JENIS_PIUTANG: "Piutang",
}

STATUS_BARU = "BARU"
STATUS_SUDAH = "SUDAH_FOLLOWUP"
STATUS_JANJI = "JANJI_BAYAR"
STATUS_KENDALA = "MASIH_KENDALA"
STATUS_SELESAI = "SELESAI"
STATUS_ARSIP = "ARSIP"
STATUS_VALUES = {
    STATUS_BARU,
    STATUS_SUDAH,
    STATUS_JANJI,
    STATUS_KENDALA,
    STATUS_SELESAI,
    STATUS_ARSIP,
}
STATUS_LABELS = {
    STATUS_BARU: "Baru",
    STATUS_SUDAH: "Sudah follow up",
    STATUS_JANJI: "Janji bayar",
    STATUS_KENDALA: "Masih kendala",
    STATUS_SELESAI: "Selesai",
    STATUS_ARSIP: "Arsip",
}
OPEN_STATUSES = {STATUS_BARU, STATUS_SUDAH, STATUS_JANJI, STATUS_KENDALA}

SYSTEM_OPERATOR = "Sistem"
WA_JENIS = {
    JENIS_PROSPEK: whatsapp_service.JENIS_FOLLOWUP,
    JENIS_SERVIS: whatsapp_service.JENIS_FOLLOWUP,
    JENIS_GARANSI: whatsapp_service.JENIS_GARANSI,
    JENIS_PIUTANG: whatsapp_service.JENIS_PIUTANG,
}


def add_months(day: date, months: int) -> date:
    """Tambah bulan dengan kalender; tanggal 31 mengikuti akhir bulan tujuan."""
    months = int(months)
    if months == 0:
        return day
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def _format_date(day: Optional[date]) -> str:
    return day.strftime("%d/%m/%Y") if day else "-"


def _label_acuan(record: ServiceRecord) -> str:
    return ", ".join(job.deskripsi for job in record.jobs) or "servis"


def _sisa(record: ServiceRecord) -> Decimal:
    return payment_service.record_sisa(record)


def _load_records(db: Session) -> List[ServiceRecord]:
    statement = (
        select(ServiceRecord)
        .where(ServiceRecord.status == "NORMAL")
        .options(
            joinedload(ServiceRecord.unit).joinedload(VehicleOrUnit.customer),
            selectinload(ServiceRecord.jobs),
            selectinload(ServiceRecord.parts),
        )
        .order_by(ServiceRecord.waktu_service.desc(), ServiceRecord.id.desc())
    )
    return list(db.scalars(statement).unique().all())


def _record_source(
    jenis: str,
    record: ServiceRecord,
    jatuh_tempo: date,
    judul: str,
    rincian: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "jenis": jenis,
        "customer": record.unit.customer,
        "unit": record.unit,
        "record": record,
        "jatuh_tempo": jatuh_tempo,
        "judul": judul,
        "rincian": rincian,
    }


def _collect_sources(
    db: Session, today: date, ops: Dict[str, Any]
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """Hitung pengingat aktif dari nota; satu sumber per pelanggan/jenis."""
    records = _load_records(db)
    by_customer: Dict[int, List[ServiceRecord]] = {}
    for record in records:
        by_customer.setdefault(record.unit.customer_id, []).append(record)

    horizon_garansi = today + timedelta(days=int(ops["garansi_akan_habis_hari"]))
    horizon_servis = today + timedelta(days=int(ops["servis_berkala_awal_hari"]))
    prospek_hari = int(ops["prospek_hari"])

    sources: Dict[Tuple[str, int], Dict[str, Any]] = {}

    for customer_id, customer_records in by_customer.items():
        latest = customer_records[0]
        customer = latest.unit.customer

        # --- Prospek pasca servis ---
        latest_day = latest.waktu_service.date()
        age = (today - latest_day).days
        consent = bool(getattr(customer, "wa_consent", True))
        if (
            age >= prospek_hari
            and consent
            and is_valid_whatsapp(customer.nomor_hp)
        ):
            sources[(JENIS_PROSPEK, customer_id)] = _record_source(
                JENIS_PROSPEK,
                latest,
                latest_day + timedelta(days=prospek_hari),
                f"Follow up pasca servis {describe_unit(latest.unit)}",
                [
                    {
                        "no_nota": latest.no_nota,
                        "tanggal_servis": latest_day,
                        "umur_hari": age,
                        "pekerjaan": _label_acuan(latest),
                        "garansi_sampai": latest.garansi_sampai
                        if latest.bergaransi
                        else None,
                    }
                ],
            )

        # --- Garansi akan habis ---
        garansi_record: Optional[ServiceRecord] = None
        for record in customer_records:
            if not record.bergaransi or record.garansi_sampai is None:
                continue
            if record.status_klaim == "Sudah claim":
                continue
            if today <= record.garansi_sampai <= horizon_garansi:
                if (
                    garansi_record is None
                    or record.garansi_sampai < garansi_record.garansi_sampai
                ):
                    garansi_record = record
        if garansi_record is not None:
            sources[(JENIS_GARANSI, customer_id)] = _record_source(
                JENIS_GARANSI,
                garansi_record,
                garansi_record.garansi_sampai,
                f"Garansi {describe_unit(garansi_record.unit)} berakhir "
                f"{_format_date(garansi_record.garansi_sampai)}",
                [
                    {
                        "no_nota": garansi_record.no_nota,
                        "tanggal_servis": garansi_record.waktu_service.date(),
                        "pekerjaan": _label_acuan(garansi_record),
                        "garansi_sampai": garansi_record.garansi_sampai,
                        "sisa_hari": (garansi_record.garansi_sampai - today).days,
                    }
                ],
            )

        # --- Servis berkala dari baris jasa dan sparepart nota ---
        seen_rows: set = set()
        servis_rows: List[Dict[str, Any]] = []
        for record in customer_records:
            for job in record.jobs:
                interval = int(getattr(job, "interval_servis_bulan", 0) or 0)
                if interval <= 0:
                    continue
                key = (
                    "jasa",
                    job.harga_jasa_id
                    if job.harga_jasa_id is not None
                    else (job.deskripsi or "").strip().lower(),
                )
                if key in seen_rows:
                    continue
                seen_rows.add(key)
                servis_day = record.waktu_service.date()
                servis_rows.append(
                    {
                        "no_nota": record.no_nota,
                        "jenis_item": "jasa",
                        "nama": job.deskripsi,
                        "pekerjaan": job.deskripsi,
                        "tanggal_servis": servis_day,
                        "interval_bulan": interval,
                        "jatuh_tempo": add_months(servis_day, interval),
                        "record": record,
                    }
                )
            for part in record.parts:
                interval = int(getattr(part, "interval_servis_bulan", 0) or 0)
                if interval <= 0:
                    continue
                key = (
                    "part",
                    part.stock_item_id
                    if part.stock_item_id is not None
                    else (part.nama_part or "").strip().lower(),
                )
                if key in seen_rows:
                    continue
                seen_rows.add(key)
                servis_day = record.waktu_service.date()
                label = f"Sparepart {part.nama_part}"
                servis_rows.append(
                    {
                        "no_nota": record.no_nota,
                        "jenis_item": "sparepart",
                        "nama": part.nama_part,
                        "pekerjaan": label,
                        "tanggal_servis": servis_day,
                        "interval_bulan": interval,
                        "jatuh_tempo": add_months(servis_day, interval),
                        "record": record,
                    }
                )
        due_rows = [row for row in servis_rows if row["jatuh_tempo"] <= horizon_servis]
        if due_rows:
            nearest = min(
                due_rows,
                key=lambda row: (row["jatuh_tempo"], row["no_nota"]),
            )
            record = nearest["record"]
            sources[(JENIS_SERVIS, customer_id)] = _record_source(
                JENIS_SERVIS,
                record,
                nearest["jatuh_tempo"],
                f"Servis berkala {describe_unit(record.unit)}: "
                f"{nearest['pekerjaan']}",
                [
                    {
                        "no_nota": row["no_nota"],
                        "jenis_item": row["jenis_item"],
                        "nama": row["nama"],
                        "pekerjaan": row["pekerjaan"],
                        "tanggal_servis": row["tanggal_servis"],
                        "interval_bulan": row["interval_bulan"],
                        "jatuh_tempo": row["jatuh_tempo"],
                    }
                    for row in sorted(
                        servis_rows, key=lambda row: row["jatuh_tempo"]
                    )
                ],
            )

        # --- Piutang (digabung per pelanggan) ---
        unpaid = [
            record
            for record in customer_records
            if record.status_bayar == "BELUM_LUNAS" and _sisa(record) > 0
        ]
        if unpaid:
            nearest_due = min(
                (
                    record.jatuh_tempo
                    for record in unpaid
                    if record.jatuh_tempo is not None
                ),
                default=None,
            )
            anchor = next(
                (record for record in unpaid if record.jatuh_tempo == nearest_due),
                unpaid[0],
            )
            total_sisa = sum((_sisa(record) for record in unpaid), Decimal("0.00"))
            sources[(JENIS_PIUTANG, customer_id)] = _record_source(
                JENIS_PIUTANG,
                anchor,
                nearest_due or anchor.waktu_service.date(),
                f"Piutang {len(unpaid)} nota",
                [
                    {
                        "no_nota": record.no_nota,
                        "tanggal_servis": record.waktu_service.date(),
                        "total_servis": record.total_servis,
                        "sisa_bayar": _sisa(record),
                        "jatuh_tempo": record.jatuh_tempo,
                    }
                    for record in sorted(
                        unpaid, key=lambda row: row.waktu_service
                    )
                ],
            )

    return sources


def _same_cycle(item: FollowupItem, source: Dict[str, Any]) -> bool:
    record = source["record"]
    return (
        item.service_record_id == record.id
        and item.jatuh_tempo == source["jatuh_tempo"]
    )


def _add_event(
    db: Session,
    item: FollowupItem,
    from_status: Optional[str],
    to_status: str,
    reason: Optional[str],
    operator: str,
    now: datetime,
) -> FollowupEvent:
    event = FollowupEvent(
        item_id=item.id,
        from_status=from_status,
        to_status=to_status,
        alasan=reason,
        operator=operator,
        created_at=now,
    )
    db.add(event)
    return event


def _update_item(
    db: Session,
    item: FollowupItem,
    source: Dict[str, Any],
    now: datetime,
) -> bool:
    """Perbarui item dari sumber; True bila siklus baru memulai status BARU."""
    record = source["record"]
    new_cycle = (
        item.service_record_id is not None
        and item.service_record_id != record.id
        and item.jenis in {JENIS_PROSPEK, JENIS_SERVIS, JENIS_GARANSI}
    )
    item.unit_id = record.unit_id
    item.service_record_id = record.id
    item.judul = source["judul"]
    item.jatuh_tempo = source["jatuh_tempo"]
    if new_cycle:
        previous = item.status
        item.status = STATUS_BARU
        item.penanggung_jawab = None
        item.diambil_pada = None
        item.followup_terakhir = None
        item.janji_bayar = None
        item.alasan_arsip = None
        item.archived_at = None
        _add_event(
            db,
            item,
            previous,
            STATUS_BARU,
            "Siklus baru dari nota terbaru.",
            SYSTEM_OPERATOR,
            now,
        )
    return new_cycle


def _archive_item(
    db: Session,
    item: FollowupItem,
    reason: str,
    operator: str,
    now: datetime,
) -> None:
    previous = item.status
    item.status = STATUS_ARSIP
    item.alasan_arsip = reason
    item.archived_at = now
    _add_event(db, item, previous, STATUS_ARSIP, reason, operator, now)


def sync_items(
    db: Session,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
    commit: bool = True,
) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """Sinkronkan pengingat aktif dari nota tanpa menghapus riwayat."""
    day = today or date.today()
    moment = now or datetime.now()
    ops = settings_service.get_ops_settings(db)
    sources = _collect_sources(db, day, ops)
    items = list(db.scalars(select(FollowupItem)).all())

    by_key: Dict[Tuple[str, int], List[FollowupItem]] = {}
    for item in items:
        by_key.setdefault((item.jenis, item.customer_id), []).append(item)

    for key, source in sources.items():
        rows = by_key.get(key, [])
        active = next((row for row in rows if row.status != STATUS_ARSIP), None)
        if active is not None:
            _update_item(db, active, source, moment)
            continue
        if any(row.status == STATUS_ARSIP and _same_cycle(row, source) for row in rows):
            # Pengingat untuk siklus ini sudah diarsipkan manual.
            continue
        item = FollowupItem(
            jenis=key[0],
            customer_id=key[1],
            unit_id=source["record"].unit_id,
            service_record_id=source["record"].id,
            judul=source["judul"],
            jatuh_tempo=source["jatuh_tempo"],
            status=STATUS_BARU,
            created_at=moment,
            updated_at=moment,
        )
        db.add(item)
        db.flush()
        _add_event(db, item, None, STATUS_BARU, "Pengingat baru.", SYSTEM_OPERATOR, moment)

    for key, rows in by_key.items():
        if key in sources:
            continue
        for item in rows:
            if item.status == STATUS_ARSIP:
                continue
            _archive_item(
                db,
                item,
                "Sumber pengingat sudah tidak aktif.",
                SYSTEM_OPERATOR,
                moment,
            )

    db.flush()
    if commit:
        db.commit()
    return sources


def _serialize(
    item: FollowupItem,
    source: Optional[Dict[str, Any]],
    ops: Dict[str, Any],
    today: date,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    customer = item.customer
    unit = item.unit
    record = item.service_record
    sisa_hari = (item.jatuh_tempo - today).days if item.jatuh_tempo else None
    cooldown = int(ops.get("cooldown_hari", 7))
    cooldown_until = (
        item.followup_terakhir + timedelta(days=cooldown)
        if item.followup_terakhir is not None and cooldown > 0
        else None
    )
    moment = now or datetime.now()
    consent = bool(getattr(customer, "wa_consent", True))
    valid_number = is_valid_whatsapp(customer.nomor_hp)
    on_cooldown = cooldown_until is not None and moment < cooldown_until
    bisa = (
        item.status not in {STATUS_ARSIP, STATUS_SELESAI}
        and consent
        and valid_number
        and not on_cooldown
    )
    return {
        "id": item.id,
        "jenis": item.jenis,
        "jenis_label": JENIS_LABELS.get(item.jenis, item.jenis),
        "customer_id": item.customer_id,
        "customer_nama": customer.nama,
        "nomor_hp": customer.nomor_hp,
        "nomor_masked": mask_phone(customer.nomor_hp),
        "wa_consent": consent,
        "unit_id": item.unit_id,
        "unit_deskripsi": describe_unit(unit) if unit is not None else "-",
        "service_record_id": item.service_record_id,
        "no_nota": record.no_nota if record is not None else None,
        "judul": item.judul,
        "jatuh_tempo": item.jatuh_tempo,
        "sisa_hari": sisa_hari,
        "terlambat": bool(sisa_hari is not None and sisa_hari < 0),
        "status": item.status,
        "status_label": STATUS_LABELS.get(item.status, item.status),
        "penanggung_jawab": item.penanggung_jawab,
        "diambil_pada": item.diambil_pada,
        "followup_terakhir": item.followup_terakhir,
        "sudah_followup": item.followup_terakhir is not None,
        "janji_bayar": item.janji_bayar,
        "alasan_arsip": item.alasan_arsip,
        "cooldown_sampai": cooldown_until,
        "bisa_followup": bisa,
        "rincian": list(source["rincian"]) if source else [],
    }


def _item_statement(jenis: Optional[str], customer_id: Optional[int]):
    statement = select(FollowupItem)
    if jenis:
        statement = statement.where(FollowupItem.jenis == jenis)
    if customer_id is not None:
        statement = statement.where(FollowupItem.customer_id == customer_id)
    return statement.options(
        joinedload(FollowupItem.customer),
        joinedload(FollowupItem.unit),
        joinedload(FollowupItem.service_record),
    )


def _active_items(
    db: Session,
    jenis: Optional[str] = None,
    customer_id: Optional[int] = None,
) -> List[FollowupItem]:
    statement = _item_statement(jenis, customer_id).where(
        FollowupItem.status != STATUS_ARSIP
    )
    return list(db.scalars(statement).unique().all())


def _archived_items(
    db: Session,
    jenis: Optional[str] = None,
    customer_id: Optional[int] = None,
) -> List[FollowupItem]:
    statement = _item_statement(jenis, customer_id).where(
        FollowupItem.status == STATUS_ARSIP
    )
    return list(db.scalars(statement).unique().all())


def list_items(
    db: Session,
    filter: str = "semua",
    jenis: Optional[str] = None,
    customer_id: Optional[int] = None,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
    sync: bool = True,
) -> Dict[str, Any]:
    day = today or date.today()
    moment = now or datetime.now()
    sources = sync_items(db, today=day, now=moment) if sync else {}
    ops = settings_service.get_ops_settings(db)

    if filter == "arsip":
        items = _archived_items(db, jenis, customer_id)
        items.sort(
            key=lambda item: (
                item.archived_at or datetime.min,
                item.id,
            ),
            reverse=True,
        )
        serialized = [
            _serialize(item, sources.get((item.jenis, item.customer_id)), ops, day, moment)
            for item in items
        ]
        return {"items": serialized, "jumlah": len(serialized)}

    items = _active_items(db, jenis, customer_id)
    if filter == "hari_ini":
        items = [
            item
            for item in items
            if item.jatuh_tempo is not None
            and item.jatuh_tempo <= day
            and item.status in OPEN_STATUSES
        ]
    elif filter == "terlambat":
        items = [
            item
            for item in items
            if item.jatuh_tempo is not None
            and item.jatuh_tempo < day
            and item.status in OPEN_STATUSES
        ]
    elif filter == "belum_ditugaskan":
        items = [
            item
            for item in items
            if item.penanggung_jawab is None
            and item.status in OPEN_STATUSES
        ]
    elif filter == "milik_saya":
        items = [
            item
            for item in items
            if item.penanggung_jawab is not None
            and item.status in OPEN_STATUSES
        ]
    elif filter not in {"semua", ""}:
        raise BusinessValidationError(
            "Filter tugas harus semua, hari_ini, terlambat, "
            "belum_ditugaskan, milik_saya, atau arsip."
        )

    items.sort(
        key=lambda item: (
            item.jatuh_tempo or date.max,
            item.customer.nama.lower(),
            item.id,
        )
    )
    serialized = []
    for item in items:
        source = sources.get((item.jenis, item.customer_id))
        serialized.append(_serialize(item, source, ops, day, moment))
    return {"items": serialized, "jumlah": len(serialized)}


def counts(
    db: Session,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
) -> Dict[str, int]:
    """Angka kartu Ringkasan; dihitung dari item aktif yang sama."""
    day = today or date.today()
    sync_items(db, today=day, now=now)
    rows = db.execute(
        select(FollowupItem.jenis, FollowupItem.jatuh_tempo, FollowupItem.status)
        .where(FollowupItem.status != STATUS_ARSIP)
    ).all()
    servis_due = 0
    prospek = 0
    hari_ini = 0
    for jenis, jatuh_tempo, status in rows:
        if status == STATUS_SELESAI:
            continue
        if jenis == JENIS_SERVIS:
            servis_due += 1
        if jenis == JENIS_PROSPEK:
            prospek += 1
        if jatuh_tempo is not None and jatuh_tempo <= day:
            hari_ini += 1
    return {
        "servis_berkala_due": servis_due,
        "prospek_count": prospek,
        "followup_hari_ini": hari_ini,
    }


def serialize_item(
    db: Session,
    item: FollowupItem,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    day = today or date.today()
    moment = now or datetime.now()
    if source is None:
        ops = settings_service.get_ops_settings(db)
        sources = _collect_sources(db, day, ops)
        source = sources.get((item.jenis, item.customer_id))
    else:
        ops = settings_service.get_ops_settings(db)
    return _serialize(item, source, ops, day, moment)


def _get_item(db: Session, item_id: int) -> FollowupItem:
    item = db.get(FollowupItem, item_id)
    if item is None:
        raise NotFoundError("Item follow-up tidak ditemukan.")
    return item


def _pekerjaan(record: Optional[ServiceRecord]) -> str:
    if record is None:
        return "servis"
    return _label_acuan(record)


def _garansi_clause(record: Optional[ServiceRecord], today: date) -> str:
    if record is None or not record.bergaransi or record.garansi_sampai is None:
        return ""
    days = (record.garansi_sampai - today).days
    if days < 0:
        return "Masa garansi sudah berakhir. "
    if days <= 7:
        return (
            f"Garansi akan berakhir pada {_format_date(record.garansi_sampai)} "
            f"({days} hari lagi). "
        )
    return f"Garansi berlaku sampai {_format_date(record.garansi_sampai)}. "


def _gejala(record: Optional[ServiceRecord]) -> str:
    text = (_pekerjaan(record) or "").lower()
    if "radiator" in text:
        return "kebocoran atau suhu mesin"
    if "oli" in text:
        return "suara mesin atau tenaga"
    return "keluhan"


def _message(db: Session, item: FollowupItem, today: date) -> str:
    info = settings_service.get_bengkel_info(db)
    customer = item.customer
    record = item.service_record
    unit = describe_unit(item.unit) if item.unit is not None else "unit"
    pekerjaan = _pekerjaan(record)
    tanggal = _format_date(record.waktu_service.date() if record else None)

    if item.jenis == JENIS_GARANSI and record is not None:
        days = (record.garansi_sampai - today).days if record.garansi_sampai else 0
        return (
            f"Halo Bapak/Ibu {customer.nama}, kami dari {info['nama']}. "
            f"Garansi servis {unit} tanggal {tanggal} akan berakhir pada "
            f"{_format_date(record.garansi_sampai)} ({days} hari lagi). "
            f"Bagaimana kondisi {unit} setelah {pekerjaan}? Bila masih ada "
            f"{_gejala(record)}, silakan cek ulang ke bengkel sebelum masa "
            "garansi berakhir."
        )

    if item.jenis == JENIS_SERVIS and record is not None:
        interval = 0
        for row in list(record.jobs) + list(record.parts):
            interval = max(interval, int(getattr(row, "interval_servis_bulan", 0) or 0))
        jadwal = _format_date(item.jatuh_tempo)
        return (
            f"Halo Bapak/Ibu {customer.nama}, kami dari {info['nama']}. "
            f"Terakhir kami kerjakan {pekerjaan} pada {unit} tanggal {tanggal}. "
            f"Sesuai jadwal servis berkala"
            + (f" {interval} bulan" if interval else "")
            + f", waktunya servis lagi sekitar {jadwal}. "
            "Silakan datang bila ingin dijadwalkan. Terima kasih."
        )

    if item.jenis == JENIS_PIUTANG:
        if record is not None:
            return whatsapp_service.completion_wa_text(record, info)
        return (
            f"Halo Bapak/Ibu {customer.nama}, kendaraan {unit} sudah selesai "
            f"dikerjakan dan siap diambil di {info['nama']}. "
            "Sisa pembayaran dapat diselesaikan saat pengambilan. Terima kasih."
        )

    return (
        f"Halo Bapak/Ibu {customer.nama}, kami dari {info['nama']}. "
        f"Sudah beberapa waktu sejak servis {unit} tanggal {tanggal} "
        f"({pekerjaan}). Apakah masih ada kendala? "
        f"{_garansi_clause(record, today)}"
        "Silakan hubungi kami bila perlu dicek ulang. Terima kasih."
    )


def follow_up(
    db: Session,
    item_id: int,
    status: str,
    operator: Operator,
    catatan: Optional[str] = None,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Catat upaya follow-up dan buka WhatsApp; tidak menghapus item."""
    day = today or date.today()
    moment = now or datetime.now()
    normalized = (status or "").strip().upper()
    if normalized not in whatsapp_service.VALID_STATUSES:
        raise BusinessValidationError(
            "Status WhatsApp harus DIBUKA, DIBATALKAN, atau TIDAK_TERSEDIA."
        )

    with db.begin():
        ops = settings_service.get_ops_settings(db)
        item = _get_item(db, item_id)
        if item.status == STATUS_ARSIP:
            raise ConflictError("Item sudah diarsipkan.")
        if item.status == STATUS_SELESAI:
            raise ConflictError("Item sudah selesai.")
        cooldown = int(ops.get("cooldown_hari", 7))
        if cooldown > 0 and item.followup_terakhir is not None:
            until = item.followup_terakhir + timedelta(days=cooldown)
            if moment < until:
                raise ConflictError(
                    "Follow up baru bisa diulang setelah "
                    f"{until.strftime('%d/%m/%Y %H:%M')}."
                )

        message = _message(db, item, day)
        log, link = whatsapp_service.append_attempt(
            db,
            item.customer,
            jenis=WA_JENIS.get(item.jenis, whatsapp_service.JENIS_FOLLOWUP),
            status=normalized,
            message=message,
            operator=operator,
            record=item.service_record,
            catatan=catatan,
            now=moment,
        )
        item.followup_terakhir = moment
        if item.status in {STATUS_BARU, STATUS_SUDAH}:
            previous = item.status
            item.status = STATUS_SUDAH
            _add_event(
                db,
                item,
                previous,
                STATUS_SUDAH,
                "Follow up " + normalized.lower() + (f": {catatan}" if catatan else ""),
                operator.label,
                moment,
            )
        db.flush()

    db.refresh(item)
    return {"item": item, "wa_text": message, "link": link, "log": log}


def change_status(
    db: Session,
    item_id: int,
    status: str,
    operator: Operator,
    alasan: Optional[str] = None,
    janji_bayar: Optional[date] = None,
    now: Optional[datetime] = None,
) -> FollowupItem:
    moment = now or datetime.now()
    target = (status or "").strip().upper()
    if target not in STATUS_VALUES:
        raise BusinessValidationError(
            "Status follow-up harus BARU, SUDAH_FOLLOWUP, JANJI_BAYAR, "
            "MASIH_KENDALA, SELESAI, atau ARSIP."
        )

    with db.begin():
        item = _get_item(db, item_id)
        if item.status == STATUS_ARSIP:
            raise ConflictError("Item arsip tidak dapat diubah.")
        if target == item.status:
            raise BusinessValidationError("Status item sudah sama.")
        if item.jenis == JENIS_PIUTANG and target in {STATUS_SELESAI, STATUS_ARSIP}:
            raise BusinessValidationError(
                "Piutang hanya keluar dari daftar lewat pelunasan penuh atau void."
            )
        if target == STATUS_JANJI and item.jenis != JENIS_PIUTANG:
            raise BusinessValidationError("Janji bayar hanya untuk piutang.")
        if target == STATUS_JANJI and janji_bayar is None:
            raise BusinessValidationError("Tanggal janji bayar wajib diisi.")
        if target == STATUS_ARSIP and not (alasan or "").strip():
            raise BusinessValidationError("Alasan arsip wajib diisi.")

        previous = item.status
        item.status = target
        if target == STATUS_JANJI:
            item.janji_bayar = janji_bayar
        elif target != STATUS_JANJI:
            item.janji_bayar = None
        if target == STATUS_ARSIP:
            item.alasan_arsip = (alasan or "").strip()
            item.archived_at = moment
        _add_event(db, item, previous, target, alasan, operator.label, moment)
        db.flush()

    db.refresh(item)
    return item


def assign(
    db: Session,
    item_id: int,
    operator: Operator,
    release: bool = False,
    alasan: Optional[str] = None,
    now: Optional[datetime] = None,
) -> FollowupItem:
    moment = now or datetime.now()
    with db.begin():
        item = _get_item(db, item_id)
        if item.status in {STATUS_ARSIP, STATUS_SELESAI}:
            raise ConflictError("Item yang sudah selesai/arsip tidak ditugaskan.")
        previous = item.penanggung_jawab
        if release:
            if previous is None:
                raise BusinessValidationError("Item belum punya penanggung jawab.")
            item.penanggung_jawab = None
            item.diambil_pada = None
            reason = "Penanggung jawab dilepas" + (f": {alasan}" if alasan else "")
        else:
            if previous == operator.label:
                raise BusinessValidationError("Anda sudah memegang tugas ini.")
            item.penanggung_jawab = operator.label
            item.diambil_pada = moment
            reason = (
                f"Penanggung jawab diganti dari {previous}"
                if previous
                else "Tugas diambil"
            ) + (f": {alasan}" if alasan else "")
        _add_event(db, item, item.status, item.status, reason, operator.label, moment)
        db.flush()

    db.refresh(item)
    return item


def detail(
    db: Session,
    item_id: int,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    day = today or date.today()
    moment = now or datetime.now()
    sources = sync_items(db, today=day, now=moment)
    item = _get_item(db, item_id)
    ops = settings_service.get_ops_settings(db)
    event_rows = list(
        db.scalars(
            select(FollowupEvent)
            .where(FollowupEvent.item_id == item.id)
            .order_by(FollowupEvent.created_at.asc(), FollowupEvent.id.asc())
        ).all()
    )
    return {
        "item": _serialize(
            item, sources.get((item.jenis, item.customer_id)), ops, day, moment
        ),
        "events": event_rows,
        "pesan": _message(db, item, day),
    }


def reminders(
    db: Session,
    today: Optional[date] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Pengingat H-7/H-3/H-1 garansi dan H-3/0/+7 piutang."""
    day = today or date.today()
    moment = now or datetime.now()
    sources = sync_items(db, today=day, now=moment)
    ops = settings_service.get_ops_settings(db)
    wanted = {
        JENIS_GARANSI: {7: "H-7", 3: "H-3", 1: "H-1"},
        JENIS_PIUTANG: {-7: "H+7", -3: "H-3", 0: "Hari ini"},
    }
    rows: List[Dict[str, Any]] = []
    for (jenis, customer_id), source in sources.items():
        labels = wanted.get(jenis)
        if not labels:
            continue
        offset = (source["jatuh_tempo"] - day).days
        label = labels.get(offset)
        if label is None:
            continue
        item = db.scalar(
            select(FollowupItem).where(
                FollowupItem.jenis == jenis,
                FollowupItem.customer_id == customer_id,
                FollowupItem.status != STATUS_ARSIP,
            )
        )
        if item is None:
            continue
        payload = _serialize(item, source, ops, day, moment)
        payload["pengingat"] = label
        rows.append(payload)
    rows.sort(key=lambda row: (row["jatuh_tempo"] or date.max, row["customer_nama"]))
    return rows
