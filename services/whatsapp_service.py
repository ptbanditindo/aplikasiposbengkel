"""Pesan WhatsApp, izin pelanggan, dan log upaya membuka WhatsApp (Tahap 12).

Aplikasi tidak mengirim pesan di latar belakang. Backend hanya menyusun teks,
membuat tautan `wa.me`, dan mencatat status upaya yang dilakukan kasir.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Customer, ServiceRecord, Supplier, VehicleOrUnit, WhatsAppLog
from services import audit_service, payment_service, settings_service
from services.auth_service import Operator
from services.customer_service import describe_unit
from services.errors import BusinessValidationError, ConflictError, NotFoundError
from services.utils import (
    format_rupiah,
    is_valid_whatsapp,
    mask_phone,
    normalize_whatsapp,
)

STATUS_OPENED = "DIBUKA"
STATUS_CANCELLED = "DIBATALKAN"
STATUS_UNAVAILABLE = "TIDAK_TERSEDIA"
VALID_STATUSES = {STATUS_OPENED, STATUS_CANCELLED, STATUS_UNAVAILABLE}

JENIS_STRUK = "struk"
JENIS_FOLLOWUP = "followup"
JENIS_GARANSI = "garansi"
JENIS_PIUTANG = "piutang"
JENIS_PENGERJAAN = "pengerjaan"
JENIS_SUPPLIER = "supplier"
VALID_JENIS = {
    JENIS_STRUK,
    JENIS_FOLLOWUP,
    JENIS_GARANSI,
    JENIS_PIUTANG,
    JENIS_PENGERJAAN,
    JENIS_SUPPLIER,
}

def formal_opening(
    bengkel: Dict[str, str], customer_nama: Optional[str] = None
) -> str:
    """Sapaan formal: minta maaf, lalu perkenalkan bengkel dari Pengaturan."""
    nama = (customer_nama or "").strip()
    sapaan = f"Bapak/Ibu {nama}" if nama else "Bapak/Ibu"
    bengkel_nama = (bengkel.get("nama") or "").strip()
    perkenalan = (
        f"Perkenalkan, kami dari {bengkel_nama}."
        if bengkel_nama
        else "Perkenalkan, kami dari bengkel kami."
    )
    return (
        f"Mohon maaf apabila pesan ini mengganggu waktu {sapaan}.\n\n"
        f"{perkenalan}"
    )


def completion_wa_text(record: ServiceRecord, bengkel: Dict[str, str]) -> str:
    """Satu-satunya sumber kalimat "kendaraan selesai" untuk pelanggan.

    Tidak memakai kata hutang/piutang/tagihan/kekurangan; sisa pembayaran
    disebut sebagai informasi pelunasan saat pengambilan.
    """
    customer = record.unit.customer
    unit = describe_unit(record.unit)
    text = (
        f"Kami ingin menyampaikan bahwa kendaraan {unit} dengan nota "
        f"{record.no_nota} sudah selesai dikerjakan dan siap diambil "
        "di bengkel kami."
    )
    sisa = payment_service.record_sisa(record)
    if (record.status or "NORMAL") != "VOID" and sisa > 0:
        if Decimal(record.total_dibayar or 0) > 0:
            text += " Pembayaran awal sudah kami terima."
        text += (
            f" Sisa pembayaran {format_rupiah(sisa)} dapat diselesaikan "
            "saat pengambilan."
        )
    return (
        f"{formal_opening(bengkel, customer.nama)} {text}\n\n"
        "Terima kasih atas kepercayaan Bapak/Ibu kepada kami."
    )


def receivable_wa_text(record: ServiceRecord, bengkel: Dict[str, str]) -> str:
    """Pengingat piutang formal; tidak mengklaim kendaraan siap diambil."""
    customer = record.unit.customer
    unit = describe_unit(record.unit)
    sisa = payment_service.record_sisa(record)
    due = (
        f" Jatuh tempo pembayaran pada {record.jatuh_tempo.strftime('%d/%m/%Y')}."
        if record.jatuh_tempo
        else ""
    )
    variants = [
        (
            f"Kami ingin mengingatkan bahwa pembayaran nota {record.no_nota} "
            f"untuk {unit} masih memiliki sisa sebesar {format_rupiah(sisa)}."
            + due
            + " Apabila pembayaran sudah dilakukan, mohon abaikan pesan ini."
        ),
        (
            f"Mohon izin mengingatkan kembali pembayaran nota {record.no_nota} "
            f"untuk {unit}. Pada nota ini masih ada sisa sebesar "
            f"{format_rupiah(sisa)}." + due
            + " Jika pembayaran sudah dilakukan, mohon abaikan pesan ini."
        ),
        (
            f"Kami ingin menyampaikan informasi pembayaran nota {record.no_nota} "
            f"untuk {unit}. Saat ini masih ada sisa sebesar "
            f"{format_rupiah(sisa)}." + due
            + " Apabila sudah dilakukan pembayaran, mohon abaikan pesan ini."
        ),
    ]
    body = variants[int(record.id or 0) % len(variants)]
    return (
        f"{formal_opening(bengkel, customer.nama)} {body}\n\n"
        "Terima kasih atas perhatian dan kerja samanya."
    )


def receivable_wa_text_multi(
    records: List[ServiceRecord], bengkel: Dict[str, str]
) -> str:
    """Satu pengingat formal untuk semua nota piutang pelanggan yang sama."""
    if not records:
        return ""
    ordered = sorted(
        records,
        key=lambda record: (record.jatuh_tempo or date.max, record.waktu_service),
    )
    customer = ordered[0].unit.customer
    total = Decimal("0.00")
    rincian = []
    for record in ordered:
        sisa = payment_service.record_sisa(record)
        total += sisa
        keterangan = (
            f"nota {record.no_nota} untuk {describe_unit(record.unit)} "
            f"sebesar {format_rupiah(sisa)}"
        )
        if record.jatuh_tempo:
            keterangan += (
                f" (jatuh tempo {record.jatuh_tempo.strftime('%d/%m/%Y')})"
            )
        rincian.append(keterangan)
    body = (
        "Kami ingin mengingatkan pembayaran beberapa nota berikut:\n"
        + "\n".join("- " + row for row in rincian)
        + f"\nTotal sisa pembayaran sebesar {format_rupiah(total)}. "
        "Apabila pembayaran sudah dilakukan, mohon abaikan pesan ini."
    )
    return (
        f"{formal_opening(bengkel, customer.nama)} {body}\n\n"
        "Terima kasih atas perhatian dan kerja samanya."
    )


PENGERJAAN_STATUS_TEXT = {
    "SEDANG_DIKERJAKAN": "Kami ingin menginformasikan bahwa kendaraan {unit} dengan nota {nota} sedang dikerjakan.",
    "MENUNGGU_SPAREPART": "Kami ingin menginformasikan bahwa pengerjaan kendaraan {unit} dengan nota {nota} sedang menunggu ketersediaan sparepart.",
    "MENUNGGU_PERSETUJUAN": "Kami ingin meminta persetujuan Bapak/Ibu untuk melanjutkan pengerjaan kendaraan {unit} dengan nota {nota}.",
    "SELESAI_SIAP_DIAMBIL": "Kami ingin menyampaikan bahwa kendaraan {unit} dengan nota {nota} sudah selesai dikerjakan dan siap diambil di bengkel kami.",
    "SUDAH_DIAMBIL": "Kami ingin menyampaikan bahwa kendaraan {unit} dengan nota {nota} sudah diambil. Terima kasih telah mempercayakan servis kepada kami.",
}


def pengerjaan_status_wa_text(
    record: ServiceRecord, status: str, bengkel: Dict[str, str]
) -> str:
    """Pesan pengerjaan untuk status tertentu, bukan pesan piutang."""
    customer = record.unit.customer
    unit = describe_unit(record.unit)
    normalized = (status or "").strip().upper()
    body = PENGERJAAN_STATUS_TEXT.get(normalized)
    if body is None:
        body = (
            "Kami ingin menginformasikan pembaruan pengerjaan kendaraan "
            "{unit} dengan nota {nota}."
        )
    body = body.format(unit=unit, nota=record.no_nota)
    sisa = payment_service.record_sisa(record)
    if normalized == "SELESAI_SIAP_DIAMBIL" and sisa > 0:
        body += (
            f" Sisa pembayaran {format_rupiah(sisa)} dapat diselesaikan "
            "saat pengambilan."
        )
    return (
        f"{formal_opening(bengkel, customer.nama)} {body}\n\n"
        "Terima kasih atas perhatian Bapak/Ibu."
    )



def supplier_wa_text(
    supplier: Supplier, items: List[Dict[str, Any]], bengkel: Dict[str, str]
) -> str:
    """Pesan formal untuk menanyakan ketersediaan stok ke supplier/reseller."""
    nama = (supplier.nama or "").strip()
    sapaan = f"Bapak/Ibu pengelola {nama}," if nama else "Bapak/Ibu pengelola,"
    bengkel_nama = (bengkel.get("nama") or "").strip()
    perkenalan = (
        f"Perkenalkan, kami dari {bengkel_nama}."
        if bengkel_nama
        else "Perkenalkan, kami dari bengkel kami."
    )
    names = [item.get("nama") or "-" for item in items]
    body = (
        f"{sapaan}\n\n{perkenalan} Kami ingin menanyakan ketersediaan "
        "barang berikut:\n"
        + "\n".join(f"- {nama}" for nama in names)
        + "\n\nMohon informasikan apakah stok tersedia, harga per satuan, "
        "dan perkiraan waktu pengiriman. Terima kasih atas perhatiannya."
    )
    return body


def log_supplier_attempt(
    db: Session,
    supplier_id: int,
    items: List[Dict[str, Any]],
    operator: Operator,
    status: str = STATUS_OPENED,
    pesan: Optional[str] = None,
    now: Optional[datetime] = None,
):
    """Catat chat supplier dan kembalikan (log, teks, tautan)."""
    normalized = (status or "").strip().upper()
    if normalized not in VALID_STATUSES:
        raise BusinessValidationError(
            "Status WhatsApp harus DIBUKA, DIBATALKAN, atau TIDAK_TERSEDIA."
        )
    moment = now or datetime.now()
    with db.begin():
        supplier = db.get(Supplier, supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier tidak ditemukan.")
        if not supplier.aktif:
            raise ConflictError(
                "Supplier sedang nonaktif. Aktifkan kembali di halaman Supplier."
            )
        if normalized == STATUS_OPENED:
            ops = settings_service.get_ops_settings(db)
            if not settings_service.within_followup_window(ops, moment):
                raise ConflictError(settings_service.followup_window_message(ops))
            if not is_valid_whatsapp(supplier.nomor_hp):
                raise BusinessValidationError("Nomor WhatsApp supplier tidak valid.")
        info = settings_service.get_bengkel_info(db)
        message = (pesan or "").strip() or supplier_wa_text(supplier, items, info)
        link = (
            build_link(supplier.nomor_hp, message)
            if normalized == STATUS_OPENED
            else ""
        )
        log = WhatsAppLog(
            supplier_id=supplier.id,
            customer_id=None,
            jenis=JENIS_SUPPLIER,
            nomor_masked=mask_phone(supplier.nomor_hp),
            status=normalized,
            pesan=message,
            operator=operator.label,
            created_at=moment,
        )
        db.add(log)
        audit_service.record_event(
            db,
            operator,
            audit_service.ACTION_WHATSAPP,
            audit_service.REFERENCE_SUPPLIER,
            reference_id=str(supplier.id),
            reason=f"WhatsApp supplier {normalized}",
            now=moment,
        )
        db.flush()
    db.refresh(log)
    return log, message, link


def build_link(nomor: str, message: str) -> str:
    digits = normalize_whatsapp(nomor)
    if not digits:
        return ""
    return f"https://wa.me/{digits}?text={quote(message, safe='')}"


def append_attempt(
    db: Session,
    customer,
    *,
    jenis: str,
    status: str,
    message: str,
    operator: Operator,
    record: Optional[ServiceRecord] = None,
    followup_item_id: Optional[int] = None,
    catatan: Optional[str] = None,
    now: Optional[datetime] = None,
):
    """Tambahkan log WhatsApp tanpa membuka transaksi baru.

    Pemanggil bertanggung jawab atas transaksi; dipakai juga oleh follow-up
    (Tahap 13) yang mencatat beberapa perubahan dalam satu atom.
    """
    normalized = (status or "").strip().upper()
    if normalized not in VALID_STATUSES:
        raise BusinessValidationError(
            "Status WhatsApp harus DIBUKA, DIBATALKAN, atau TIDAK_TERSEDIA."
        )
    normalized_jenis = (jenis or JENIS_STRUK).strip().lower()
    if normalized_jenis not in VALID_JENIS:
        raise BusinessValidationError(
            "Jenis pesan WhatsApp harus struk, followup, garansi, atau piutang."
        )
    if normalized == STATUS_OPENED and not is_valid_whatsapp(customer.nomor_hp):
        raise BusinessValidationError("Nomor WhatsApp pelanggan tidak valid.")

    link = (
        build_link(customer.nomor_hp, message)
        if normalized == STATUS_OPENED
        else ""
    )
    moment = now or datetime.now()
    warning = ""
    if normalized == STATUS_OPENED:
        from services import contact_gate_service

        warning = contact_gate_service.ensure_can_open(
            db, customer, normalized_jenis, moment
        )
    log = WhatsAppLog(
        service_record_id=record.id if record is not None else None,
        followup_item_id=followup_item_id,
        customer_id=customer.id,
        jenis=normalized_jenis,
        nomor_masked=mask_phone(customer.nomor_hp),
        status=normalized,
        pesan=message,
        operator=operator.label,
        created_at=moment,
    )
    log.peringatan = warning
    db.add(log)
    audit_service.record_event(
        db,
        operator,
        audit_service.ACTION_WHATSAPP,
        (
            audit_service.REFERENCE_SERVICE_RECORD
            if record is not None
            else audit_service.REFERENCE_CUSTOMER
        ),
        reference_id=record.no_nota if record is not None else str(customer.id),
        reason=f"WhatsApp {normalized_jenis} {normalized}"
        + (f": {catatan}" if catatan else ""),
        now=moment,
    )
    db.flush()
    return log, link


def log_attempt(
    db: Session,
    record_id: int,
    status: str,
    operator: Operator,
    catatan: Optional[str] = None,
    pesan: Optional[str] = None,
    now: Optional[datetime] = None,
    jenis: str = JENIS_STRUK,
):
    """Catat upaya WhatsApp nota. Mengembalikan (log, wa_text, link)."""
    normalized_jenis = (jenis or JENIS_STRUK).strip().lower()
    normalized_status = (status or "").strip().upper()
    if normalized_jenis not in {JENIS_STRUK, JENIS_PIUTANG, JENIS_PENGERJAAN}:
        raise BusinessValidationError(
            "Jenis pesan WhatsApp nota harus struk, piutang, atau pengerjaan."
        )
    moment = now or datetime.now()
    with db.begin():
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        info = settings_service.get_bengkel_info(db)
        if normalized_jenis == JENIS_STRUK:
            # Impor lokal agar tidak melingkar: receipt_service memakai layanan ini.
            from services.receipt_service import receipt_wa_text

            default_message = receipt_wa_text(
                record, info, show=settings_service.display_receipt_settings(db)
            )
        else:
            default_message = completion_wa_text(record, info)
        message = (pesan or "").strip() or default_message
        log, link = append_attempt(
            db,
            record.unit.customer,
            jenis=normalized_jenis,
            status=normalized_status,
            message=message,
            operator=operator,
            record=record,
            catatan=catatan,
            now=moment,
        )

    db.refresh(log)
    return log, message, link


def piutang_reminder_state(
    record: ServiceRecord, ops: Dict[str, Any], moment: datetime
) -> Tuple[bool, str]:
    """Kelayakan pengingat piutang: jatuh tempo, jeda 2 minggu, maksimal 3 kali."""
    reminder_ke = int(record.piutang_reminder_ke or 0)
    maks = int(ops.get("piutang_maks_pengingat", 3))
    jeda = int(ops.get("piutang_jeda_hari", 14))
    if reminder_ke >= maks:
        return (
            False,
            "Pengingat piutang sudah {0} kali. Hubungi pelanggan lewat telepon.".format(
                maks
            ),
        )
    if reminder_ke == 0:
        if record.jatuh_tempo is not None and moment.date() < record.jatuh_tempo:
            return (
                False,
                "Pengingat bisa dikirim mulai "
                + record.jatuh_tempo.strftime("%d-%m-%Y")
                + ".",
            )
        return True, ""
    next_at = record.piutang_next_at
    if next_at is not None and moment < next_at:
        return (
            False,
            "Pengingat berikutnya bisa dikirim setelah "
            + next_at.strftime("%d-%m-%Y %H:%M")
            + ".",
        )
    return True, ""


def apply_piutang_reminder(
    record: ServiceRecord, ops: Dict[str, Any], moment: datetime
) -> int:
    """Naikkan hitungan pengingat; setelah batas, tandai perlu telepon."""
    maks = int(ops.get("piutang_maks_pengingat", 3))
    jeda = int(ops.get("piutang_jeda_hari", 14))
    record.piutang_reminder_ke = int(record.piutang_reminder_ke or 0) + 1
    record.diingatkan_pada = moment
    if record.piutang_reminder_ke >= maks:
        record.piutang_next_at = None
        record.piutang_perlu_telepon = True
    else:
        record.piutang_next_at = moment + timedelta(days=jeda)
        record.piutang_perlu_telepon = False
    return record.piutang_reminder_ke


def remind_receivable(
    db: Session,
    record_id: int,
    operator: Operator,
    now: Optional[datetime] = None,
):
    """Kirim pengingat piutang sesuai jadwal: jatuh tempo lalu tiap 2 minggu."""
    moment = now or datetime.now()
    with db.begin():
        record = db.get(ServiceRecord, record_id)
        if record is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        if (record.status or "NORMAL") == "VOID":
            raise ConflictError("Nota sudah dibatalkan (VOID).")
        if (
            (record.status_bayar or "LUNAS") == "LUNAS"
            or payment_service.record_sisa(record) <= 0
        ):
            raise ConflictError("Nota ini sudah lunas.")
        ops = settings_service.get_ops_settings(db)
        ready, reason = piutang_reminder_state(record, ops, moment)
        if not ready:
            raise ConflictError(reason)
        if not settings_service.within_followup_window(ops, moment):
            raise ConflictError(settings_service.followup_window_message(ops))
        from services import contact_gate_service

        blocked = contact_gate_service.daily_cap_reason(
            db, record.unit.customer.id, moment, ops
        )
        if blocked:
            raise ConflictError(blocked)
        if contact_gate_service.blocked_by_pengerjaan(
            db, record.unit.customer.id
        ):
            raise ConflictError(
                "Masih ada unit pelanggan di bengkel. Kabari pengambilan lebih dulu."
            )
        info = settings_service.get_bengkel_info(db)
        message = receivable_wa_text(record, info)
        log, link = append_attempt(
            db,
            record.unit.customer,
            jenis=JENIS_PIUTANG,
            status=STATUS_OPENED,
            message=message,
            operator=operator,
            record=record,
            now=moment,
        )
        apply_piutang_reminder(record, ops, moment)
        from services import followup_service

        followup_service.sync_items(db, commit=False)
        followup_service.mark_piutang_followed(
            db,
            record.id,
            moment,
            operator.label,
            "Pengingat piutang dari daftar piutang.",
        )

    db.refresh(log)
    return log, message, link


def remind_customer_receivables(
    db: Session,
    customer_id: int,
    operator: Operator,
    now: Optional[datetime] = None,
):
    """Satu pesan untuk nota pelanggan yang jatuh tempo, sesuai jadwal masing-masing."""
    moment = now or datetime.now()
    with db.begin():
        customer = db.get(Customer, customer_id)
        if customer is None:
            raise NotFoundError("Pelanggan tidak ditemukan.")
        rows = list(
            db.scalars(
                select(ServiceRecord)
                .join(VehicleOrUnit, ServiceRecord.unit_id == VehicleOrUnit.id)
                .where(
                    VehicleOrUnit.customer_id == customer_id,
                    ServiceRecord.status == "NORMAL",
                )
                .order_by(
                    ServiceRecord.jatuh_tempo.asc(),
                    ServiceRecord.waktu_service.asc(),
                )
            )
            .unique()
            .all()
        )
        records = [
            record
            for record in rows
            if (record.status_bayar or "LUNAS") == "BELUM_LUNAS"
            and payment_service.record_sisa(record) > 0
        ]
        if not records:
            raise ConflictError("Tidak ada piutang berjalan.")
        ops = settings_service.get_ops_settings(db)
        eligible: List[ServiceRecord] = []
        reasons: List[str] = []
        for record in records:
            ready, reason = piutang_reminder_state(record, ops, moment)
            if ready:
                eligible.append(record)
            elif reason:
                reasons.append(reason)
        if not eligible:
            raise ConflictError(
                reasons[0] if reasons else "Belum ada nota yang jatuh tempo."
            )
        if not settings_service.within_followup_window(ops, moment):
            raise ConflictError(settings_service.followup_window_message(ops))
        from services import contact_gate_service

        blocked = contact_gate_service.daily_cap_reason(
            db, customer.id, moment, ops
        )
        if blocked:
            raise ConflictError(blocked)
        if contact_gate_service.blocked_by_pengerjaan(db, customer.id):
            raise ConflictError(
                "Masih ada unit pelanggan di bengkel. Kabari pengambilan lebih dulu."
            )
        info = settings_service.get_bengkel_info(db)
        message = receivable_wa_text_multi(eligible, info)
        log = None
        link = ""
        for record in eligible:
            log, link = append_attempt(
                db,
                customer,
                jenis=JENIS_PIUTANG,
                status=STATUS_OPENED,
                message=message,
                operator=operator,
                record=record,
                now=moment,
            )
            apply_piutang_reminder(record, ops, moment)
        from services import followup_service

        followup_service.sync_items(db, commit=False)
        for record in eligible:
            followup_service.mark_piutang_followed(
                db,
                record.id,
                moment,
                operator.label,
                "Pengingat piutang pelanggan.",
            )

    db.refresh(log)
    return log, message, link


def list_logs(
    db: Session, record_id: Optional[int] = None, limit: int = 100
) -> List[WhatsAppLog]:
    statement = select(WhatsAppLog).order_by(
        WhatsAppLog.created_at.desc(), WhatsAppLog.id.desc()
    )
    if record_id is not None:
        if db.get(ServiceRecord, record_id) is None:
            raise NotFoundError("Nota servis tidak ditemukan.")
        statement = statement.where(WhatsAppLog.service_record_id == record_id)
    return list(db.scalars(statement.limit(max(1, min(limit, 500)))).all())
