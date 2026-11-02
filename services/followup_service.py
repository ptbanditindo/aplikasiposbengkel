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
    PengerjaanNota,
    ServiceRecord,
    VehicleOrUnit,
    WhatsAppLog,
)
from services import payment_service, settings_service, whatsapp_service
from services import contact_gate_service
from services.auth_service import Operator
from services.customer_service import describe_unit
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import is_valid_whatsapp, mask_phone, money

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
STATUS_AKAN_DATANG = "AKAN_DATANG"
STATUS_TIDAK_DATANG = "TIDAK_DATANG"
STATUS_SUDAH_BAYAR = "SUDAH_BAYAR"
STATUS_VALUES = {
    STATUS_BARU,
    STATUS_SUDAH,
    STATUS_JANJI,
    STATUS_KENDALA,
    STATUS_SELESAI,
    STATUS_ARSIP,
    STATUS_AKAN_DATANG,
    STATUS_TIDAK_DATANG,
    STATUS_SUDAH_BAYAR,
}
STATUS_LABELS = {
    STATUS_BARU: "Baru",
    STATUS_SUDAH: "Sudah dihubungi",
    STATUS_JANJI: "Janji bayar",
    STATUS_KENDALA: "Masih kendala",
    STATUS_SELESAI: "Selesai",
    STATUS_ARSIP: "Arsip",
    STATUS_AKAN_DATANG: "Akan datang service",
    STATUS_TIDAK_DATANG: "Tidak akan datang service",
    STATUS_SUDAH_BAYAR: "Sudah bayar",
}
OPEN_STATUSES = {
    STATUS_BARU,
    STATUS_SUDAH,
    STATUS_JANJI,
    STATUS_KENDALA,
    STATUS_AKAN_DATANG,
}
JADWAL_JENIS = {JENIS_SERVIS, JENIS_GARANSI}

SYSTEM_OPERATOR = "Sistem"
AUTO_ARCHIVE_REASON = "Sumber pengingat sudah tidak aktif."
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


def _fully_returned(record: ServiceRecord) -> bool:
    return money(
        Decimal(record.total_servis or 0) - Decimal(record.total_retur or 0)
    ) <= 0


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
) -> Dict[str, Dict[str, Any]]:
    """Hitung sumber follow-up per unit, baris servis, dan nota piutang."""
    records = _load_records(db)
    pengerjaan_rows = list(db.scalars(select(PengerjaanNota)).all())
    open_record_ids = {
        row.service_record_id
        for row in pengerjaan_rows
        if row.diambil_pada is None
    }
    taken_by_unit: Dict[int, datetime] = {}
    for row in pengerjaan_rows:
        if row.diambil_pada is None or row.unit_id is None:
            continue
        current = taken_by_unit.get(row.unit_id)
        if current is None or row.diambil_pada > current:
            taken_by_unit[row.unit_id] = row.diambil_pada

    def reference_day(record: ServiceRecord) -> date:
        taken = taken_by_unit.get(record.unit_id)
        return taken.date() if taken is not None else record.waktu_service.date()

    by_unit: Dict[int, List[ServiceRecord]] = {}
    for record in records:
        if record.id in open_record_ids:
            continue
        if record.unit is not None and record.unit.unit_type == "SPAREPART":
            continue
        by_unit.setdefault(record.unit_id, []).append(record)

    existing_rows = list(
        db.scalars(
            select(FollowupItem).where(FollowupItem.status != STATUS_ARSIP)
        ).all()
    )
    existing_by_key = {
        row.item_key: row for row in existing_rows if row.item_key
    }

    horizon_servis = today + timedelta(days=int(ops["servis_berkala_awal_hari"]))

    def add_source(
        key: str,
        jenis: str,
        record: ServiceRecord,
        due: date,
        judul: str,
        rincian: List[Dict[str, Any]],
        **extra: Any,
    ) -> None:
        sources[key] = {
            "jenis": jenis,
            "item_key": key,
            "customer": record.unit.customer,
            "unit": record.unit,
            "record": record,
            "jatuh_tempo": due,
            "judul": judul,
            "rincian": rincian,
            **extra,
        }

    sources: Dict[str, Dict[str, Any]] = {}

    for unit_id, unit_records in by_unit.items():
        if not unit_records:
            continue
        latest = unit_records[0]
        is_sparepart_unit = latest.unit.unit_type == "SPAREPART"
        lifecycle_records = [] if is_sparepart_unit else unit_records
        reference = reference_day(latest)
        lifecycle_key = "lifecycle:unit:" + str(unit_id)
        existing = existing_by_key.get(lifecycle_key)
        stage = (
            int(existing.stage)
            if existing is not None
            and existing.jenis in {JENIS_PROSPEK, JENIS_GARANSI}
            else 0
        )

        warranty_record = next(
            (
                record
                for record in lifecycle_records
                if record.bergaransi
                and record.garansi_sampai is not None
                and record.garansi_sampai
                + timedelta(days=int(ops["garansi_arsip_hari"]))
                >= today
                and not _fully_returned(record)
                and record.status_klaim != "Sudah claim"
            ),
            None,
        )

        lifecycle_source = None
        no_reminder = False
        if warranty_record is not None:
            expiry = warranty_record.garansi_sampai
            h7 = expiry - timedelta(days=int(ops["garansi_akan_habis_hari"]))
            archive_after = expiry + timedelta(
                days=int(ops["garansi_arsip_hari"])
            )
            if h7 <= today <= archive_after:
                answered = (
                    existing is not None
                    and existing.followup_terakhir is not None
                    and existing.followup_terakhir.date() >= h7
                )
                promised = (
                    existing is not None
                    and existing.status == STATUS_AKAN_DATANG
                    and existing.tanggal_service is not None
                    and existing.tanggal_service <= expiry
                )
                no_reminder = today >= expiry and (answered or promised)
                if today >= expiry and not no_reminder:
                    due = expiry
                    stage = max(stage, 2)
                else:
                    due = h7 if today < expiry else expiry
                    stage = max(stage, 1)
                lifecycle_source = (
                    JENIS_GARANSI,
                    warranty_record,
                    due,
                    "Garansi "
                    + describe_unit(warranty_record.unit)
                    + " berakhir "
                    + _format_date(expiry),
                    [
                        {
                            "no_nota": warranty_record.no_nota,
                            "tanggal_servis": warranty_record.waktu_service.date(),
                            "pekerjaan": _label_acuan(warranty_record),
                            "garansi_sampai": expiry,
                            "sisa_hari": (expiry - today).days,
                        }
                    ],
                )
            elif today < h7:
                milestone_days = (
                    int(ops["prospek_hari_1"]),
                    int(ops["prospek_hari_2"]),
                    int(ops["prospek_hari_3"]),
                )
                if reference + timedelta(days=milestone_days[0]) < h7:
                    milestones = [
                        days
                        for days in milestone_days
                        if reference + timedelta(days=days) < h7
                    ]
                    if milestones and stage < len(milestones):
                        due = reference + timedelta(days=milestones[stage])
                        lifecycle_source = (
                            JENIS_PROSPEK,
                            latest,
                            due,
                            "Follow up pasca servis " + describe_unit(latest.unit),
                            [
                                {
                                    "no_nota": latest.no_nota,
                                    "tanggal_servis": reference,
                                    "umur_hari": max((today - reference).days, 0),
                                    "pekerjaan": _label_acuan(latest),
                                    "garansi_sampai": expiry,
                                }
                            ],
                        )
        elif lifecycle_records:
            milestones = [int(ops["prospek_hari_1"]), int(ops["prospek_hari_3"])]
            if stage < len(milestones):
                due = reference + timedelta(days=milestones[stage])
                lifecycle_source = (
                    JENIS_PROSPEK,
                    latest,
                    due,
                    "Follow up pasca servis " + describe_unit(latest.unit),
                    [
                        {
                            "no_nota": latest.no_nota,
                            "tanggal_servis": reference,
                            "umur_hari": max((today - reference).days, 0),
                            "pekerjaan": _label_acuan(latest),
                            "garansi_sampai": None,
                        }
                    ],
                )

        if lifecycle_source is not None:
            jenis, record, due, judul, rincian = lifecycle_source
            add_source(
                lifecycle_key,
                jenis,
                record,
                due,
                judul,
                rincian,
                stage=stage,
                item_kind="lifecycle",
                reference_date=reference,
                no_reminder=no_reminder,
            )

        seen_rows: set = set()
        servis_rows: Dict[str, Dict[str, Any]] = {}
        for record in lifecycle_records:
            if _fully_returned(record):
                continue
            servis_day = reference_day(record)
            for job in record.jobs:
                interval = int(getattr(job, "interval_servis_bulan", 0) or 0)
                if interval <= 0:
                    continue
                identifier = (
                    job.harga_jasa_id
                    if job.harga_jasa_id is not None
                    else (job.deskripsi or "").strip().lower()
                )
                key = ("servis:" + str(unit_id) + ":jasa:" + str(identifier))[:180]
                if key in seen_rows:
                    continue
                seen_rows.add(key)
                servis_rows[key] = {
                    "no_nota": record.no_nota,
                    "jenis_item": "jasa",
                    "nama": job.deskripsi,
                    "pekerjaan": job.deskripsi,
                    "tanggal_servis": servis_day,
                    "interval_bulan": interval,
                    "jatuh_tempo": add_months(servis_day, interval),
                    "record": record,
                    "item_key": key,
                    "item_nama": job.deskripsi,
                }
            for part in record.parts:
                interval = int(getattr(part, "interval_servis_bulan", 0) or 0)
                if interval <= 0:
                    continue
                identifier = (
                    part.stock_item_id
                    if part.stock_item_id is not None
                    else (part.nama_part or "").strip().lower()
                )
                key = ("servis:" + str(unit_id) + ":part:" + str(identifier))[:180]
                if key in seen_rows:
                    continue
                seen_rows.add(key)
                servis_rows[key] = {
                    "no_nota": record.no_nota,
                    "jenis_item": "sparepart",
                    "nama": part.nama_part,
                    "pekerjaan": "Sparepart " + part.nama_part,
                    "tanggal_servis": servis_day,
                    "interval_bulan": interval,
                    "jatuh_tempo": add_months(servis_day, interval),
                    "record": record,
                    "item_key": key,
                    "item_nama": part.nama_part,
                }

        for key, row in servis_rows.items():
            existing = existing_by_key.get(key)
            stage = 0
            if (
                existing is not None
                and existing.service_record_id == row["record"].id
            ):
                stage = int(existing.stage or 0)
            due = add_months(
                row["tanggal_servis"],
                row["interval_bulan"] * (stage + 1),
            )
            if due > horizon_servis:
                continue
            record = row["record"]
            rincian = [
                {
                    "no_nota": other["no_nota"],
                    "jenis_item": other["jenis_item"],
                    "nama": other["nama"],
                    "pekerjaan": other["pekerjaan"],
                    "tanggal_servis": other["tanggal_servis"],
                    "interval_bulan": other["interval_bulan"],
                    "jatuh_tempo": other["jatuh_tempo"],
                }
                for other in servis_rows.values()
                if other["record"].id == record.id
            ]
            add_source(
                key,
                JENIS_SERVIS,
                record,
                due,
                "Servis berkala "
                + describe_unit(record.unit)
                + ": "
                + row["pekerjaan"],
                rincian,
                stage=stage,
                interval_bulan=row["interval_bulan"],
                item_nama=row["item_nama"],
                item_kind=row["jenis_item"],
                reference_date=row["tanggal_servis"],
            )

        for record in unit_records:
            if record.status_bayar != "BELUM_LUNAS" or _sisa(record) <= 0:
                continue
            key = "piutang:record:" + str(record.id)
            due = record.jatuh_tempo or reference_day(record)
            add_source(
                key,
                JENIS_PIUTANG,
                record,
                due,
                "Piutang nota " + record.no_nota,
                [
                    {
                        "no_nota": record.no_nota,
                        "tanggal_servis": reference_day(record),
                        "total_servis": record.total_servis,
                        "sisa_bayar": _sisa(record),
                        "jatuh_tempo": record.jatuh_tempo,
                    }
                ],
                item_kind="nota",
                reference_date=reference_day(record),
            )

    servis_due_by_unit: Dict[int, List[date]] = {}
    for source in sources.values():
        if source["jenis"] == JENIS_SERVIS:
            servis_due_by_unit.setdefault(source["unit"].id, []).append(
                source["jatuh_tempo"]
            )
    for key in list(sources):
        source = sources[key]
        if source["jenis"] != JENIS_PROSPEK:
            continue
        existing = existing_by_key.get(key)
        known = existing is not None and existing.status != STATUS_ARSIP
        if not known and source["jatuh_tempo"] > today:
            del sources[key]
            continue
        if known:
            continue
        nearby_servis = servis_due_by_unit.get(source["unit"].id, [])
        tunda_hari = int(ops["servis_berkala_awal_hari"])
        if any(abs((due - today).days) <= tunda_hari for due in nearby_servis):
            del sources[key]
            continue
        garansi_sampai = (
            source["rincian"][0].get("garansi_sampai")
            if source["rincian"]
            else None
        )
        if garansi_sampai is not None and (
            (
                garansi_sampai
                - timedelta(days=int(ops["garansi_akan_habis_hari"]))
                - today
            ).days
            <= tunda_hari
        ):
            del sources[key]

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
    item.jenis = source.get("jenis", item.jenis)
    item.item_key = source.get("item_key", item.item_key)
    item.stage = int(source.get("stage", 0) or 0)
    item.interval_bulan = source.get("interval_bulan")
    item.item_nama = source.get("item_nama")
    item.item_kind = source.get("item_kind")
    item.reference_date = source.get("reference_date")
    item.judul = source["judul"]
    item.jatuh_tempo = source["jatuh_tempo"]
    if new_cycle:
        previous = item.status
        item.status = STATUS_BARU
        item.followup_terakhir = None
        item.janji_bayar = None
        item.tanggal_service = None
        item.alasan_arsip = None
        item.archived_at = None
        item.cycle_started_at = now
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
) -> Dict[str, Dict[str, Any]]:
    """Sinkronkan pengingat aktif dari nota tanpa menghapus riwayat."""
    day = today or date.today()
    moment = now or datetime.now()
    ops = settings_service.get_ops_settings(db)
    sources = _collect_sources(db, day, ops)
    items = list(db.scalars(select(FollowupItem)).all())

    by_key: Dict[str, List[FollowupItem]] = {}
    for item in items:
        key = item.item_key or f"legacy:{item.id}"
        by_key.setdefault(key, []).append(item)

    for key, source in sources.items():
        rows = by_key.get(key, [])
        active = next((row for row in rows if row.status != STATUS_ARSIP), None)
        if active is not None:
            _update_item(db, active, source, moment)
            continue
        if any(row.status == STATUS_ARSIP and _same_cycle(row, source) for row in rows):
            # Pengingat untuk siklus ini sudah diarsipkan manual.
            continue
        if any(
            row.status == STATUS_ARSIP
            and row.service_record_id == source["record"].id
            and (row.alasan_arsip or "") != AUTO_ARCHIVE_REASON
            for row in rows
        ):
            # Arsip manual berlaku sampai nota/unit memulai siklus baru.
            continue
        item = FollowupItem(
            jenis=source["jenis"],
            item_key=key,
            customer_id=source["customer"].id,
            unit_id=source["record"].unit_id,
            service_record_id=source["record"].id,
            judul=source["judul"],
            jatuh_tempo=source["jatuh_tempo"],
            status=STATUS_BARU,
            stage=int(source.get("stage", 0) or 0),
            interval_bulan=source.get("interval_bulan"),
            item_nama=source.get("item_nama"),
            item_kind=source.get("item_kind"),
            reference_date=source.get("reference_date"),
            created_at=moment,
            cycle_started_at=moment,
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
                AUTO_ARCHIVE_REASON,
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
    valid_number = is_valid_whatsapp(customer.nomor_hp)
    on_cooldown = cooldown_until is not None and moment < cooldown_until
    tunda_aktif = item.tunda_sampai is not None and moment < item.tunda_sampai
    piutang_ke = 0
    piutang_berikutnya = None
    perlu_telepon = bool(item.perlu_telepon)
    piutang_ready = True
    if item.jenis == JENIS_PIUTANG and record is not None:
        piutang_ke = int(record.piutang_reminder_ke or 0)
        piutang_berikutnya = record.piutang_next_at
        perlu_telepon = perlu_telepon or bool(record.piutang_perlu_telepon)
        piutang_ready, _reason = whatsapp_service.piutang_reminder_state(
            record, ops, moment
        )
    bisa_alasan = ""
    no_reminder = bool(source and source.get("no_reminder"))
    dnc_blocked = bool(customer.do_not_contact) and item.jenis in {
        JENIS_PROSPEK,
        JENIS_SERVIS,
        JENIS_GARANSI,
    }
    if no_reminder:
        bisa_alasan = "Garansi H-7 sudah dibalas atau sudah ada janji datang."
    elif dnc_blocked:
        bisa_alasan = "Pelanggan meminta berhenti dihubungi (DNC)."
    elif not valid_number:
        bisa_alasan = "Nomor WhatsApp pelanggan belum valid."
    elif on_cooldown:
        bisa_alasan = "Jeda follow up belum selesai."
    elif tunda_aktif:
        bisa_alasan = "Follow up ditunda sampai " + item.tunda_sampai.strftime(
            "%d/%m/%Y %H:%M"
        ) + "."
    elif perlu_telepon:
        bisa_alasan = "Pengingat piutang sudah mencapai batas. Hubungi lewat telepon."
    elif not piutang_ready:
        bisa_alasan = "Pengingat piutang belum jatuh tempo atau sedang dijeda."
    elif not settings_service.within_followup_window(ops, moment):
        bisa_alasan = "Di luar jam follow up."
    bisa = (
        item.status
        not in {
            STATUS_ARSIP,
            STATUS_SELESAI,
            STATUS_TIDAK_DATANG,
            STATUS_SUDAH_BAYAR,
        }
        and valid_number
        and not no_reminder
        and not dnc_blocked
        and not on_cooldown
        and not tunda_aktif
        and not perlu_telepon
        and piutang_ready
        and settings_service.within_followup_window(ops, moment)
    )
    status_label = STATUS_LABELS.get(item.status, item.status)
    if item.jenis == JENIS_PROSPEK and item.status == STATUS_BARU:
        status_label = "Masih bagus"
    return {
        "id": item.id,
        "jenis": item.jenis,
        "jenis_label": JENIS_LABELS.get(item.jenis, item.jenis),
        "item_key": item.item_key,
        "stage": item.stage or 0,
        "interval_bulan": item.interval_bulan,
        "item_nama": item.item_nama,
        "item_kind": item.item_kind,
        "perlu_telepon": perlu_telepon,
        "pengingat_ke": piutang_ke,
        "pengingat_berikutnya": piutang_berikutnya,
        "customer_id": item.customer_id,
        "customer_nama": customer.nama,
        "customer_alamat": customer.alamat,
        "nomor_hp": customer.nomor_hp,
        "nomor_masked": mask_phone(customer.nomor_hp),
        "unit_id": item.unit_id,
        "unit_deskripsi": describe_unit(unit) if unit is not None else "-",
        "service_record_id": item.service_record_id,
        "no_nota": record.no_nota if record is not None else None,
        "judul": item.judul,
        "jatuh_tempo": item.jatuh_tempo,
        "sisa_hari": sisa_hari,
        "terlambat": bool(
            item.status != STATUS_AKAN_DATANG
            and sisa_hari is not None
            and sisa_hari < 0
        ),
        "status": item.status,
        "status_label": status_label,
        "followup_terakhir": item.followup_terakhir,
        "sudah_followup": item.followup_terakhir is not None,
        "janji_bayar": item.janji_bayar,
        "tanggal_service": item.tanggal_service,
        "alasan_arsip": item.alasan_arsip,
        "cooldown_sampai": cooldown_until,
        "tunda_sampai": item.tunda_sampai,
        "bisa_alasan": bisa_alasan,
        "bisa_followup": bisa,
        "rincian": list(source["rincian"]) if source else [],
    }


def _apply_policy(
    db: Session,
    data: Dict[str, Any],
    item: FollowupItem,
    moment: datetime,
    ops: Dict[str, Any],
) -> Dict[str, Any]:
    if not data.get("bisa_followup"):
        return data
    blocked = contact_gate_service.policy_reason(db, item, moment, ops)
    if blocked:
        data["bisa_followup"] = False
        data["bisa_alasan"] = blocked
    return data


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
        FollowupItem.status.notin_(
            [STATUS_ARSIP, STATUS_TIDAK_DATANG, STATUS_SELESAI, STATUS_SUDAH_BAYAR]
        )
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
    status: Optional[str] = None,
    exclude_status: Optional[str] = None,
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
            _apply_policy(
                db,
                _serialize(item, sources.get(item.item_key), ops, day, moment),
                item,
                moment,
                ops,
            )
            for item in items
        ]
        return {"items": serialized, "jumlah": len(serialized)}

    items = _active_items(db, jenis, customer_id)
    if status:
        items = [item for item in items if item.status == status]
    if exclude_status:
        items = [item for item in items if item.status != exclude_status]
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
    elif filter not in {"semua", ""}:
        raise BusinessValidationError(
            "Filter tugas harus semua, hari_ini, terlambat, atau arsip."
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
        source = sources.get(item.item_key)
        data = _serialize(item, source, ops, day, moment)
        serialized.append(_apply_policy(db, data, item, moment, ops))
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
    berkendala_prospek = 0
    hari_ini = 0
    aktif = 0
    akan_datang_servis = 0
    akan_datang_garansi = 0
    akan_datang_prospek = 0
    for jenis, jatuh_tempo, status in rows:
        if status in {STATUS_SELESAI, STATUS_TIDAK_DATANG}:
            continue
        aktif += 1
        if status == STATUS_AKAN_DATANG:
            if jenis == JENIS_SERVIS:
                akan_datang_servis += 1
            elif jenis == JENIS_GARANSI:
                akan_datang_garansi += 1
            elif jenis == JENIS_PROSPEK:
                akan_datang_prospek += 1
                prospek += 1
            continue
        if jenis == JENIS_SERVIS:
            servis_due += 1
        if jenis == JENIS_PROSPEK:
            if status == STATUS_KENDALA:
                berkendala_prospek += 1
            else:
                prospek += 1
        if jatuh_tempo is not None and jatuh_tempo <= day:
            hari_ini += 1
    return {
        "servis_berkala_due": servis_due,
        "prospek_count": prospek,
        "berkendala_prospek": berkendala_prospek,
        "followup_hari_ini": hari_ini,
        "followup_aktif": aktif,
        "akan_datang_servis": akan_datang_servis,
        "akan_datang_garansi": akan_datang_garansi,
        "akan_datang_prospek": akan_datang_prospek,
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
        source = sources.get(item.item_key)
    else:
        ops = settings_service.get_ops_settings(db)
    return _apply_policy(
        db,
        _serialize(item, source, ops, day, moment),
        item,
        moment,
        ops,
    )


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
    opening = whatsapp_service.formal_opening(info, customer.nama)

    if item.jenis == JENIS_GARANSI and record is not None:
        days = (record.garansi_sampai - today).days if record.garansi_sampai else 0
        variants = [
            (
                f"Kami ingin menginformasikan bahwa garansi servis {unit} "
                f"tanggal {tanggal} akan berakhir pada "
                f"{_format_date(record.garansi_sampai)} ({days} hari lagi). "
                f"Bagaimana kondisi {unit} setelah {pekerjaan}? Apabila masih ada "
                f"{_gejala(record)}, kami berharap Bapak/Ibu berkenan memeriksakan "
                "kembali ke bengkel kami sebelum masa garansi berakhir."
            ),
            (
                f"Kami ingin mengingatkan bahwa garansi servis {unit} tanggal "
                f"{tanggal} berakhir pada {_format_date(record.garansi_sampai)} "
                f"({days} hari lagi). Kami berharap Bapak/Ibu berkenan memeriksa "
                f"kembali {unit} apabila masih ada {_gejala(record)} sebelum masa "
                "garansi berakhir."
            ),
            (
                f"Menjelang berakhirnya garansi servis {unit} tanggal {tanggal} "
                f"pada {_format_date(record.garansi_sampai)} ({days} hari lagi), "
                f"kami ingin menanyakan kondisi {unit} setelah {pekerjaan}. "
                "Apabila masih ada keluhan, silakan menghubungi kami untuk "
                "pemeriksaan sebelum masa garansi berakhir."
            ),
        ]
        body = variants[int(item.id or 0) % len(variants)]
        return (
            f"{opening} {body}\n\n"
            "Terima kasih atas perhatian Bapak/Ibu."
        )

    if item.jenis == JENIS_SERVIS and record is not None:
        interval = int(item.interval_bulan or 0)
        jadwal = _format_date(item.jatuh_tempo)
        jadwal_text = f" {interval} bulan" if interval else ""
        variants = [
            (
                f"Kami ingin mengingatkan bahwa servis terakhir {pekerjaan} "
                f"pada {unit} dilaksanakan tanggal {tanggal}. Sesuai jadwal servis "
                f"berkala{jadwal_text}, waktunya servis kembali sekitar {jadwal}. "
                "Kami berharap Bapak/Ibu berkenan datang untuk menjadwalkan servis."
            ),
            (
                f"Servis berkala{jadwal_text} untuk {unit} sudah mendekati jadwal "
                f"pada {jadwal}. Servis terakhir {pekerjaan} dilakukan tanggal "
                f"{tanggal}. Kami berharap Bapak/Ibu berkenan menjadwalkan "
                "kedatangan ke bengkel kami."
            ),
            (
                f"Kami ingin mengingatkan jadwal servis berkala{jadwal_text} "
                f"untuk {unit}, yaitu sekitar {jadwal}. Sebelumnya, {pekerjaan} "
                f"dilakukan tanggal {tanggal}. Apabila berkenan, kami dapat "
                "membantu menyiapkan jadwal kedatangan Bapak/Ibu."
            ),
        ]
        body = variants[int(item.id or 0) % len(variants)]
        return (
            f"{opening} {body}\n\n"
            "Terima kasih atas perhatian Bapak/Ibu."
        )

    if item.jenis == JENIS_PIUTANG:
        if record is not None:
            return whatsapp_service.receivable_wa_text(record, info)
        body = (
            f"Kami ingin mengingatkan bahwa masih terdapat sisa pembayaran "
            f"untuk {unit}. Mohon kiranya pembayaran dapat diselesaikan. "
            "Apabila pembayaran sudah dilakukan, mohon abaikan pesan ini."
        )
        return (
            f"{opening} {body}\n\n"
            "Terima kasih atas perhatian dan kerja samanya."
        )

    variants = [
        (
            f"Kami ingin menanyakan kondisi {unit} setelah servis {pekerjaan} "
            f"tanggal {tanggal}. Apakah masih ada kendala? "
            f"{_garansi_clause(record, today)}"
            "Kami berharap Bapak/Ibu berkenan menghubungi kami apabila perlu "
            "dilakukan pemeriksaan ulang."
        ),
        (
            f"Kami ingin memastikan {unit} tetap nyaman digunakan setelah "
            f"servis {pekerjaan} tanggal {tanggal}. "
            f"{_garansi_clause(record, today)}"
            "Apabila ada keluhan, kami siap membantu pemeriksaan ulang."
        ),
        (
            f"Setelah servis {pekerjaan} tanggal {tanggal}, kami ingin "
            f"menanyakan kabar {unit}. "
            f"{_garansi_clause(record, today)}"
            "Silakan menghubungi kami jika Bapak/Ibu memerlukan pemeriksaan "
            "lanjutan."
        ),
    ]
    body = variants[int(item.id or 0) % len(variants)]
    first_contact = (
        item.stage == 0 and item.followup_terakhir is None
    )
    if first_contact:
        body += (
            " Jika Bapak/Ibu tidak ingin dihubungi lagi, cukup balas BERHENTI."
        )
    return (
        f"{opening} {body}\n\n"
        "Terima kasih atas perhatian Bapak/Ibu."
    )


def _group_message(db: Session, items: List[FollowupItem], today: date) -> str:
    """Satu pesan formal untuk beberapa pengingat sejenis yang jatuh bersamaan."""
    info = settings_service.get_bengkel_info(db)
    customer = items[0].customer
    opening = whatsapp_service.formal_opening(info, customer.nama)
    lines = []
    for row in items:
        jadwal = _format_date(row.jatuh_tempo)
        lines.append("- " + row.judul + " (jadwal " + jadwal + ")")
    body = (
        "Kami ingin menyampaikan beberapa pengingat berikut:\n"
        + "\n".join(lines)
        + "\n\nApabila sudah ditindaklanjuti, mohon abaikan pesan ini."
    )
    return (
        f"{opening} {body}\n\n"
        "Terima kasih atas perhatian Bapak/Ibu."
    )


def _piutang_group_records(
    db: Session,
    item: FollowupItem,
    ops: Dict[str, Any],
    moment: datetime,
) -> List[ServiceRecord]:
    """Nota piutang pelanggan yang sudah jatuh tempo dan siap diingatkan."""
    rows = db.scalars(
        select(FollowupItem)
        .where(
            FollowupItem.customer_id == item.customer_id,
            FollowupItem.jenis == JENIS_PIUTANG,
            FollowupItem.status.in_([STATUS_BARU, STATUS_SUDAH, STATUS_KENDALA]),
        )
        .options(joinedload(FollowupItem.service_record))
        .order_by(FollowupItem.jatuh_tempo.asc(), FollowupItem.id.asc())
    ).unique().all()
    records: List[ServiceRecord] = []
    for row in rows:
        record = row.service_record
        if record is None:
            continue
        if (record.status or "NORMAL") != "NORMAL":
            continue
        if (record.status_bayar or "LUNAS") == "LUNAS" or _sisa(record) <= 0:
            continue
        ready, _reason = whatsapp_service.piutang_reminder_state(
            record, ops, moment
        )
        if ready:
            records.append(record)
    return records


def _merge_group(
    db: Session,
    item: FollowupItem,
    day: date,
    moment: datetime,
    ops: Dict[str, Any],
) -> List[FollowupItem]:
    """Item sejenis yang jatuh bersamaan agar satu pesan mencakup semuanya."""
    if item.jenis == JENIS_PIUTANG:
        record_ids = {
            record.id
            for record in _piutang_group_records(db, item, ops, moment)
        }
        if not record_ids:
            return [item]
        rows = db.scalars(
            select(FollowupItem)
            .where(
                FollowupItem.customer_id == item.customer_id,
                FollowupItem.jenis == JENIS_PIUTANG,
                FollowupItem.status.in_(
                    [STATUS_BARU, STATUS_SUDAH, STATUS_KENDALA]
                ),
                FollowupItem.service_record_id.in_(record_ids),
            )
            .order_by(FollowupItem.jatuh_tempo.asc(), FollowupItem.id.asc())
        ).all()
        return list(rows) or [item]

    rows = list(
        db.scalars(
            select(FollowupItem)
            .where(
                FollowupItem.customer_id == item.customer_id,
                FollowupItem.jenis == item.jenis,
                FollowupItem.status.in_(
                    [STATUS_BARU, STATUS_SUDAH, STATUS_KENDALA]
                ),
                FollowupItem.jatuh_tempo.is_not(None),
                FollowupItem.jatuh_tempo <= day,
            )
            .order_by(FollowupItem.jatuh_tempo.asc(), FollowupItem.id.asc())
        ).all()
    )
    group = []
    cooldown = int(ops.get("cooldown_hari", 7))
    for row in rows:
        if row.tunda_sampai is not None and moment < row.tunda_sampai:
            continue
        if (
            cooldown > 0
            and row.followup_terakhir is not None
            and moment < row.followup_terakhir + timedelta(days=cooldown)
        ):
            continue
        group.append(row)
    if item not in group:
        group.append(item)
    return group


def follow_up(
    db: Session,
    item_id: int,
    status: str,
    operator: Operator,
    catatan: Optional[str] = None,
    pesan: Optional[str] = None,
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
        if item.status in {
            STATUS_SELESAI,
            STATUS_TIDAK_DATANG,
            STATUS_SUDAH_BAYAR,
        }:
            raise ConflictError("Item sudah ditutup.")
        if not settings_service.within_followup_window(ops, moment):
            raise ConflictError(settings_service.followup_window_message(ops))
        cooldown = int(ops.get("cooldown_hari", 7))
        if cooldown > 0 and item.followup_terakhir is not None:
            until = item.followup_terakhir + timedelta(days=cooldown)
            if moment < until:
                raise ConflictError(
                    "Follow up baru bisa diulang setelah "
                    f"{until.strftime('%d/%m/%Y %H:%M')}."
                )
        if item.tunda_sampai is not None and moment < item.tunda_sampai:
            raise ConflictError(
                "Follow up ditunda sampai "
                f"{item.tunda_sampai.strftime('%d/%m/%Y %H:%M')}."
            )
        piutang_record = None
        if item.jenis == JENIS_PIUTANG and item.service_record is not None:
            piutang_record = item.service_record
            ready, reason = whatsapp_service.piutang_reminder_state(
                piutang_record, ops, moment
            )
            if not ready:
                raise ConflictError(reason)
        from services import contact_gate_service

        blocked = contact_gate_service.policy_reason(db, item, moment, ops)
        if blocked:
            raise ConflictError(blocked)

        group = (
            _merge_group(db, item, day, moment, ops)
            if normalized == whatsapp_service.STATUS_OPENED
            else [item]
        )
        if len(group) > 1:
            if item.jenis == JENIS_PIUTANG:
                records = _piutang_group_records(db, item, ops, moment)
                info = settings_service.get_bengkel_info(db)
                message = whatsapp_service.receivable_wa_text_multi(records, info)
            else:
                message = _group_message(db, group, day)
            if (pesan or "").strip():
                message = pesan.strip()
        else:
            message = (pesan or "").strip() or _message(db, item, day)

        log = None
        link = ""
        for member in group:
            member_record = member.service_record
            log, link = whatsapp_service.append_attempt(
                db,
                member.customer,
                jenis=WA_JENIS.get(
                    member.jenis, whatsapp_service.JENIS_FOLLOWUP
                ),
                status=normalized,
                message=message,
                operator=operator,
                record=member_record,
                followup_item_id=member.id,
                catatan=catatan,
                now=moment,
            )
            member.followup_terakhir = moment
            if (
                normalized == whatsapp_service.STATUS_OPENED
                and member.jenis in {JENIS_PROSPEK, JENIS_SERVIS, JENIS_GARANSI}
            ):
                member.stage = int(member.stage or 0) + 1
                member.no_response_count = int(member.no_response_count or 0) + 1
            if (
                normalized == whatsapp_service.STATUS_OPENED
                and member.jenis == JENIS_PIUTANG
            ):
                record = member_record
                if (
                    record is not None
                    and (record.status or "NORMAL") == "NORMAL"
                    and (record.status_bayar or "LUNAS") == "BELUM_LUNAS"
                    and _sisa(record) > 0
                ):
                    whatsapp_service.apply_piutang_reminder(record, ops, moment)
            if member.status in {STATUS_BARU, STATUS_SUDAH}:
                previous = member.status
                member.status = STATUS_SUDAH
                _add_event(
                    db,
                    member,
                    previous,
                    STATUS_SUDAH,
                    "Follow up "
                    + normalized.lower()
                    + (f": {catatan}" if catatan else ""),
                    operator.label,
                    moment,
                )
            if (
                normalized == whatsapp_service.STATUS_OPENED
                and member.jenis in {JENIS_PROSPEK, JENIS_SERVIS, JENIS_GARANSI}
                and member.no_response_count
                >= int(ops.get("maks_tidak_merespons", 3))
                and member.status
                not in {STATUS_AKAN_DATANG, STATUS_SELESAI, STATUS_JANJI}
            ):
                _archive_item(
                    db,
                    member,
                    "Tidak merespons 3 kali.",
                    SYSTEM_OPERATOR,
                    moment,
                )
        db.flush()

    db.refresh(item)
    return {"item": item, "wa_text": message, "link": link, "log": log}


def mark_piutang_followed(
    db: Session,
    record_id: int,
    moment: datetime,
    operator_label: str,
    reason: str,
) -> Optional[FollowupItem]:
    """Samakan item piutang nota dengan pengingat yang dikirim dari jalur lain."""
    item = db.scalar(
        select(FollowupItem)
        .where(
            FollowupItem.item_key == "piutang:record:" + str(record_id),
            FollowupItem.status != STATUS_ARSIP,
        )
        .order_by(FollowupItem.id.desc())
        .limit(1)
    )
    if item is None:
        return None
    item.followup_terakhir = moment
    if item.status in {STATUS_BARU, STATUS_SUDAH}:
        previous = item.status
        item.status = STATUS_SUDAH
        _add_event(db, item, previous, STATUS_SUDAH, reason, operator_label, moment)
    db.flush()
    return item


def change_status(
    db: Session,
    item_id: int,
    status: str,
    operator: Operator,
    alasan: Optional[str] = None,
    janji_bayar: Optional[date] = None,
    tanggal_service: Optional[date] = None,
    now: Optional[datetime] = None,
    tunda_hari: Optional[int] = None,
) -> FollowupItem:
    moment = now or datetime.now()
    target = (status or "").strip().upper()
    if target not in STATUS_VALUES:
        raise BusinessValidationError("Status follow-up tidak dikenal.")

    with db.begin():
        item = _get_item(db, item_id)
        if item.status == STATUS_ARSIP:
            raise ConflictError("Item arsip tidak dapat diubah.")
        if item.jenis in JADWAL_JENIS:
            if target not in {
                STATUS_AKAN_DATANG,
                STATUS_KENDALA,
                STATUS_TIDAK_DATANG,
                STATUS_SELESAI,
                STATUS_ARSIP,
            }:
                raise BusinessValidationError(
                    "Status servis berkala dan garansi hanya akan datang "
                    "service, belum bisa, datang, tidak akan datang service, "
                    "atau dihapus dari daftar."
                )
            if target == STATUS_AKAN_DATANG and tanggal_service is None:
                raise BusinessValidationError("Tanggal service wajib diisi.")
            if target != STATUS_ARSIP and item.followup_terakhir is None:
                raise ConflictError(
                    "Lakukan follow up WhatsApp dulu sebelum mengubah status."
                )
        elif item.jenis == JENIS_PROSPEK:
            if target != STATUS_ARSIP and item.followup_terakhir is None:
                raise ConflictError(
                    "Lakukan follow up WhatsApp dulu sebelum mengubah status."
                )
            if target == STATUS_AKAN_DATANG and tanggal_service is None:
                raise BusinessValidationError("Tanggal kunjungan wajib diisi.")
        elif target in {STATUS_AKAN_DATANG, STATUS_TIDAK_DATANG}:
            raise BusinessValidationError(
                "Status akan/tidak datang service hanya untuk prospek, "
                "servis berkala, dan garansi."
            )
        if target == item.status and item.jenis not in JADWAL_JENIS:
            if not (
                item.jenis == JENIS_PROSPEK
                and target == STATUS_AKAN_DATANG
                and tanggal_service is not None
            ):
                raise BusinessValidationError("Status item sudah sama.")
        if target == STATUS_SUDAH_BAYAR:
            if item.jenis != JENIS_PIUTANG:
                raise BusinessValidationError("Sudah bayar hanya untuk piutang.")
            record = item.service_record
            if record is None or _sisa(record) > 0:
                raise BusinessValidationError(
                    "Sisa pembayaran belum lunas. Selesaikan pelunasan lebih dulu."
                )
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
        item.tanggal_service = (
            tanggal_service if target == STATUS_AKAN_DATANG else None
        )
        if target == STATUS_JANJI:
            item.janji_bayar = janji_bayar
        else:
            item.janji_bayar = None
        if target == STATUS_KENDALA:
            ops = settings_service.get_ops_settings(db)
            hari = int(tunda_hari or ops.get("belum_bisa_hari", 14))
            item.tunda_sampai = moment + timedelta(days=hari)
        else:
            item.tunda_sampai = None
        if target in {STATUS_AKAN_DATANG, STATUS_SELESAI, STATUS_JANJI}:
            item.no_response_count = 0
        if target == STATUS_SUDAH_BAYAR:
            item.alasan_arsip = "Sudah bayar."
            item.archived_at = moment
        if target == STATUS_ARSIP:
            item.alasan_arsip = (alasan or "").strip()
            item.archived_at = moment
        _add_event(db, item, previous, target, alasan, operator.label, moment)
        db.flush()

    db.refresh(item)
    return item


def _last_sent_message(db: Session, item: FollowupItem) -> str:
    jenis = WA_JENIS.get(item.jenis, whatsapp_service.JENIS_FOLLOWUP)
    cycle_start = item.cycle_started_at or item.created_at
    statement = select(WhatsAppLog).where(
        WhatsAppLog.customer_id == item.customer_id,
        WhatsAppLog.jenis == jenis,
        WhatsAppLog.status == whatsapp_service.STATUS_OPENED,
    )
    if item.service_record_id is not None:
        statement = statement.where(
            WhatsAppLog.service_record_id == item.service_record_id
        )
    if cycle_start is not None:
        statement = statement.where(WhatsAppLog.created_at >= cycle_start)
    log = db.scalar(
        statement.order_by(
            WhatsAppLog.created_at.desc(), WhatsAppLog.id.desc()
        ).limit(1)
    )
    return (log.pesan or "").strip() if log is not None else ""


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
    item_data = _serialize(item, sources.get(item.item_key), ops, day, moment)
    item_data = _apply_policy(db, item_data, item, moment, ops)
    return {
        "item": item_data,
        "events": event_rows,
        "pesan": _last_sent_message(db, item) or _message(db, item, day),
    }
