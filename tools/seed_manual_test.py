"""Bangun ulang database dummy lengkap untuk uji manual.

Seluruh data bersifat fiktif. Skrip menolak berjalan bila path database tidak
mengandung kata "dummy", sehingga database kasir asli tidak tersentuh.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_REL = os.environ.get("SEED_DB_REL", "data/dummy_manual.db")
os.environ["DATABASE_URL"] = f"sqlite:///./{DB_REL}"
os.environ["BACKUP_DIR"] = "./backups_dummy_manual"
os.environ["PRINTER_CONFIG_PATH"] = "./data/printer_config_dummy.json"
os.environ["TELEGRAM_BACKUP_ENABLED"] = "0"
os.environ["APP_HOST"] = "127.0.0.1"

if "dummy" not in os.environ["DATABASE_URL"]:
    raise SystemExit("Dibatalkan: DATABASE_URL bukan database dummy.")

from database.models import (  # noqa: E402
    AppSetting,
    Customer,
    FollowupEvent,
    FollowupItem,
    HargaJasa,
    PengerjaanNota,
    ServiceJob,
    ServicePart,
    ServicePayment,
    ServiceRecord,
    ServiceReturn,
    ServiceReturnItem,
    StockItem,
    StockMovement,
    VehicleOrUnit,
)
from database.session import SessionLocal, init_db  # noqa: E402
from services import payment_service, pengerjaan_service  # noqa: E402
from services.followup_service import add_months, counts, sync_items  # noqa: E402
from services.utils import money  # noqa: E402

DB_PATH = ROOT / DB_REL
for suffix in ("", "-wal", "-shm"):
    candidate = Path(str(DB_PATH) + suffix)
    if candidate.exists():
        candidate.unlink()

init_db()

today = date.today()
now = datetime.now().replace(microsecond=0)


def at(offset_days: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime.combine(today + timedelta(days=offset_days), time(hour, minute))


def day_at(day: date, hour: int = 9) -> datetime:
    return datetime.combine(day, time(hour))


def service_day_for(interval: int, target_due: date) -> date:
    for offset in range(0, 500):
        candidate = today - timedelta(days=offset)
        if add_months(candidate, interval) == target_due:
            return candidate
    raise RuntimeError(f"Tanggal servis untuk jatuh tempo {target_due} tidak ada.")


jobs_master = {
    "Ganti Oli": (Decimal("150000.00"), 6),
    "Servis Radiator": (Decimal("250000.00"), 6),
    "Cuci Radiator": (Decimal("100000.00"), 3),
    "Tune Up": (Decimal("200000.00"), 0),
    "Cek Radiator": (Decimal("50000.00"), 0),
    "Cek Kebocoran": (Decimal("75000.00"), 0),
    "Ganti Coolant": (Decimal("120000.00"), 12),
    "Las Radiator": (Decimal("300000.00"), 0),
}

# nama: (harga modal, harga jual, interval bulan, stok awal)
parts_master = {
    "Oli Mesin 10W-40": (Decimal("45000.00"), Decimal("65000.00"), 6, 40),
    "Coolant Radiator": (Decimal("30000.00"), Decimal("45000.00"), 12, 30),
    "Tangki Radiator Avanza": (Decimal("350000.00"), Decimal("500000.00"), 0, 6),
    "Tutup Radiator": (Decimal("20000.00"), Decimal("35000.00"), 0, 3),
    "Selang Radiator": (Decimal("40000.00"), Decimal("70000.00"), 0, 0),
    "Kipas Radiator": (Decimal("250000.00"), Decimal("400000.00"), 0, 8),
}

stock_out = {nama: 0 for nama in parts_master}
stock_return = {nama: 0 for nama in parts_master}

with SessionLocal() as db:
    jasa = {}
    for nama, (harga, interval) in jobs_master.items():
        row = HargaJasa(nama=nama, harga_standar=harga, interval_servis_bulan=interval)
        db.add(row)
        jasa[nama] = row

    stok = {}
    for index, (nama, (modal, jual, interval, _awal)) in enumerate(
        parts_master.items(), start=1
    ):
        row = StockItem(
            kode=f"SP-{index:03d}",
            nama=nama,
            harga_modal=modal,
            harga_jual=jual,
            jumlah=0,
            interval_servis_bulan=interval,
        )
        db.add(row)
        stok[nama] = row

    for key, value in {
        "bengkel.nama": "BENGKEL RADIATOR BERKAH",
        "bengkel.tagline": "Spesialis servis, korok & las radiator",
        "bengkel.alamat": "Jl. Raya Industri No. 12, Bandung",
        "bengkel.telepon": "022-1234567",
        "bengkel.wa": "081200000001",
        "bengkel.bank_nama": "BCA",
        "bengkel.no_rekening": "1234567890",
        "bengkel.atas_nama": "Bengkel Radiator Berkah",
        "ops.tempo_hari": "7",
        "ops.prospek_hari": "7",
        "ops.cooldown_hari": "3",
        "ops.garansi_akan_habis_hari": "14",
        "ops.servis_berkala_awal_hari": "30",
    }.items():
        db.add(AppSetting(key=key, value=value))

    db.flush()

    def customer(nama, nomor_hp, alamat, wa_consent=True):
        row = Customer(
            nama=nama, nomor_hp=nomor_hp, alamat=alamat, wa_consent=wa_consent
        )
        db.add(row)
        db.flush()
        return row

    def unit(
        cust,
        nopol,
        jenis,
        tahun,
        label,
        *,
        radiator_only=False,
        tipe=None,
        keterangan=None,
        archived=False,
    ):
        row = VehicleOrUnit(
            customer_id=cust.id,
            unit_type="RADIATOR_ONLY" if radiator_only else "MOBIL",
            nopol=nopol,
            jenis_mobil=jenis,
            tahun_mobil=tahun,
            label_radiator=label,
            tipe_radiator=tipe,
            keterangan=keterangan,
            archived_at=now if archived else None,
        )
        db.add(row)
        db.flush()
        return row

    def record(
        veh,
        nota,
        when,
        job_rows,
        part_rows=(),
        *,
        keluhan,
        jenis_bayar="LUNAS",
        metode="CASH",
        dibayar=None,
        jatuh_tempo=None,
        rencana_bayar=None,
        bergaransi=False,
        garansi_sampai=None,
        catatan_garansi=None,
        status_klaim="Belum claim",
        tanggal_klaim=None,
        diskon="0.00",
        unit_ditinggal=None,
    ):
        biaya_jasa = money(
            sum(
                (
                    Decimal(jumlah) * harga
                    for _, jumlah, harga, _ in job_rows
                ),
                Decimal("0.00"),
            )
        )
        total_part = money(
            sum(
                (
                    Decimal(jumlah) * harga
                    for _, jumlah, harga, _ in part_rows
                ),
                Decimal("0.00"),
            )
        )
        diskon_value = money(diskon)
        total = money(biaya_jasa + total_part - diskon_value)
        kredit = jenis_bayar == "KREDIT"
        if kredit:
            received = money(dibayar if dibayar is not None else 0)
            status_bayar = "LUNAS" if received >= total else "BELUM_LUNAS"
            total_dibayar = received
            kembalian = Decimal("0.00")
        else:
            received = money(dibayar if dibayar is not None else total)
            status_bayar = "LUNAS"
            total_dibayar = total
            kembalian = money(max(received - total, Decimal("0.00")))

        row = ServiceRecord(
            unit_id=veh.id,
            no_nota=nota,
            request_id="seed-" + nota.lower(),
            waktu_service=when,
            keluhan_awal=keluhan,
            catatan_pengerjaan="Data demo untuk uji manual.",
            biaya_jasa=biaya_jasa,
            total_part=total_part,
            diskon=diskon_value,
            total_servis=total,
            metode_bayar=metode,
            bayar=received,
            kembalian=kembalian,
            status_bayar=status_bayar,
            jenis_bayar=jenis_bayar,
            jatuh_tempo=jatuh_tempo,
            rencana_bayar=(
                money(rencana_bayar) if rencana_bayar is not None else None
            ),
            total_dibayar=total_dibayar,
            bergaransi=bergaransi,
            garansi_sampai=garansi_sampai,
            catatan_garansi=catatan_garansi,
            status_klaim=status_klaim,
            tanggal_klaim=tanggal_klaim,
        )
        db.add(row)
        db.flush()

        for nama, jumlah, harga, interval in job_rows:
            db.add(
                ServiceJob(
                    service_record_id=row.id,
                    harga_jasa_id=jasa[nama].id,
                    deskripsi=nama,
                    jumlah=jumlah,
                    harga=harga,
                    subtotal=money(Decimal(jumlah) * harga),
                    interval_servis_bulan=interval,
                )
            )
        for nama, jumlah, harga, interval in part_rows:
            db.add(
                ServicePart(
                    service_record_id=row.id,
                    stock_item_id=stok[nama].id,
                    nama_part=nama,
                    jumlah=jumlah,
                    harga_satuan=harga,
                    subtotal=money(Decimal(jumlah) * harga),
                    harga_modal=parts_master[nama][0],
                    harga_modal_estimasi=False,
                    interval_servis_bulan=interval,
                )
            )
            stock_out[nama] += jumlah
            db.add(
                StockMovement(
                    stock_item_id=stok[nama].id,
                    nama_item=nama,
                    jenis="KELUAR",
                    jumlah=-jumlah,
                    alasan=f"Penjualan {nota}",
                    oleh="Kasir Demo",
                    service_record_id=row.id,
                    created_at=when,
                )
            )

        if total_dibayar > 0:
            db.add(
                ServicePayment(
                    service_record_id=row.id,
                    jenis=(
                        "UANG_MUKA" if status_bayar == "BELUM_LUNAS" else "PELUNASAN"
                    ),
                    metode=metode,
                    nominal=total_dibayar,
                    waktu=when,
                    created_at=when,
                    operator="Kasir Demo",
                    catatan=(
                        "Uang muka demo"
                        if status_bayar == "BELUM_LUNAS"
                        else "Pembayaran demo"
                    ),
                )
            )

        if unit_ditinggal is not None:
            status_pengerjaan, janji_ambil = unit_ditinggal
            db.add(
                PengerjaanNota(
                    service_record_id=row.id,
                    unit_id=veh.id,
                    customer_id=veh.customer_id,
                    status_pengerjaan=status_pengerjaan,
                    janji_ambil=janji_ambil,
                    dibuat_pada=when,
                    diubah_pada=when,
                    diubah_oleh="Kasir Demo",
                )
            )
        return row

    def add_payment(rec, jenis, nominal, when, metode="CASH", catatan=None):
        value = money(nominal)
        db.add(
            ServicePayment(
                service_record_id=rec.id,
                jenis=jenis,
                metode=metode,
                nominal=value,
                waktu=when,
                created_at=when,
                operator="Kasir Demo",
                catatan=catatan,
            )
        )
        paid = money(Decimal(rec.total_dibayar or 0) + value)
        rec.total_dibayar = paid
        netto = money(
            Decimal(rec.total_servis or 0) - Decimal(rec.total_retur or 0)
        )
        rec.status_bayar = "LUNAS" if money(netto - paid) <= 0 else "BELUM_LUNAS"
        return rec

    budi = customer("Budi Santoso", "082117836284", "Jl. Melati No. 1, Bandung")
    budi_unit = unit(budi, "D 1234 BUD", "Toyota Avanza", 2018, "AVANZA-BUDI")
    budi_rad = unit(
        budi,
        None,
        None,
        None,
        "RAD-BUDI-01",
        radiator_only=True,
        tipe="Radiator Avanza",
        keterangan="Radiator copotan.",
    )

    siti = customer("Siti Rahayu", "085846414593", "Jl. Kenanga No. 2, Bandung")
    siti_unit = unit(siti, "D 5678 SIT", "Honda Brio", 2019, "BRIO-SITI")

    agus = customer("Agus Pratama", "081572754673", "Jl. Anggrek No. 3, Cimahi")
    agus_unit = unit(agus, "D 9012 AGU", "Mitsubishi Xpander", 2020, "XPANDER-AGUS")
    unit(
        agus,
        "D 1122 AGU",
        "Daihatsu Gran Max",
        2015,
        "GRANMAX-AGUS",
        archived=True,
        keterangan="Unit lama, disembunyikan dari pilihan kasir.",
    )

    dewi = customer("Dewi Lestari", "087824053959", "Jl. Mawar No. 4, Bandung")
    dewi_unit = unit(dewi, "D 3456 DEW", "Daihatsu Terios", 2017, "TERIOS-DEWI")

    rudi = customer("Rudi Hartono", "088294744259", "Jl. Dahlia No. 5, Bandung")
    rudi_unit = unit(rudi, "D 7890 RUD", "Suzuki Ertiga", 2019, "ERTIGA-RUDI")

    maya = customer("Maya Sari", "085972522572", "Jl. Cempaka No. 6, Bandung")
    maya_unit = unit(maya, "D 2345 MAY", "Nissan Grand Livina", 2016, "LIVINA-MAYA")

    fajar = customer("Fajar Nugroho", "085720914159", "Jl. Flamboyan No. 7, Bandung")
    fajar_unit = unit(fajar, "D 6789 FAJ", "Toyota Rush", 2021, "RUSH-FAJAR")
    fajar_rad = unit(
        fajar,
        None,
        None,
        None,
        "RAD-FAJAR-01",
        radiator_only=True,
        tipe="Radiator Rush",
        keterangan="Radiator cadangan.",
    )

    lina = customer("Lina Marlina", "088222306379", "Jl. Teratai No. 8, Bandung")
    lina_unit = unit(lina, "D 4567 LIN", "Honda Mobilio", 2018, "MOBILIO-LINA")

    hendra = customer("Hendra Wijaya", "081311223344", "Jl. Sukamaju No. 9, Bandung")
    hendra_unit = unit(hendra, "D 8899 HEN", "Isuzu Panther", 2014, "PANTHER-HENDRA")

    nur = customer(
        "Nur Aini",
        "081399887766",
        "Jl. Cibaduyut No. 10, Bandung",
        wa_consent=False,
    )
    nur_unit = unit(nur, "D 2211 NUR", "Toyota Yaris", 2020, "YARIS-NUR")

    slamet = customer("Slamet Riyadi", "081255667788", "Jl. Kopo No. 11, Bandung")
    unit(
        slamet,
        None,
        None,
        None,
        "RAD-SLAMET-01",
        radiator_only=True,
        tipe="Radiator Truk",
        keterangan="Hanya radiator, tanpa kendaraan.",
    )

    # Transaksi hari ini: tunai, transfer, kredit, unit ditinggal, consent mati.
    record(
        siti_unit,
        "DEMO-0001",
        at(0, 8),
        [("Ganti Oli", 1, Decimal("150000.00"), 6)],
        [("Oli Mesin 10W-40", 1, Decimal("65000.00"), 6)],
        keluhan="Servis rutin dan cek radiator.",
        bergaransi=True,
        garansi_sampai=today + timedelta(days=90),
        catatan_garansi="Garansi servis 3 bulan.",
        status_klaim="Sudah claim",
        tanggal_klaim=today - timedelta(days=1),
    )
    record(
        agus_unit,
        "DEMO-0002",
        at(0, 9),
        [("Servis Radiator", 1, Decimal("250000.00"), 6)],
        [("Coolant Radiator", 1, Decimal("45000.00"), 12)],
        keluhan="Radiator kurang dingin.",
        metode="TRANSFER",
        diskon="20000.00",
        bergaransi=True,
        garansi_sampai=today + timedelta(days=9),
        catatan_garansi="Garansi servis 1 bulan.",
    )
    record(
        rudi_unit,
        "DEMO-0003",
        at(0, 10),
        [("Tune Up", 1, Decimal("200000.00"), 0)],
        [("Oli Mesin 10W-40", 1, Decimal("65000.00"), 6)],
        keluhan="Mesin kurang bertenaga.",
        jenis_bayar="KREDIT",
        dibayar="100000.00",
        jatuh_tempo=today + timedelta(days=7),
        rencana_bayar="100000.00",
        unit_ditinggal=("MENUNGGU_SPAREPART", today + timedelta(days=3)),
    )
    record(
        maya_unit,
        "DEMO-0004",
        at(0, 11),
        [("Cuci Radiator", 1, Decimal("100000.00"), 3)],
        keluhan="Cuci radiator rutin.",
        unit_ditinggal=("SEDANG_DIKERJAKAN", today + timedelta(days=2)),
    )
    record(
        lina_unit,
        "DEMO-0005",
        at(0, 13),
        [("Cek Kebocoran", 1, Decimal("75000.00"), 0)],
        keluhan="Cek kebocoran setelah servis.",
        unit_ditinggal=("SELESAI_SIAP_DIAMBIL", None),
    )
    record(
        hendra_unit,
        "DEMO-0006",
        at(0, 14),
        [("Las Radiator", 1, Decimal("300000.00"), 0)],
        keluhan="Radiator retak.",
        jenis_bayar="KREDIT",
        dibayar="50000.00",
        jatuh_tempo=None,
    )
    record(
        nur_unit,
        "DEMO-0018",
        at(0, 15),
        [("Ganti Coolant", 1, Decimal("120000.00"), 12)],
        [("Coolant Radiator", 1, Decimal("45000.00"), 12)],
        keluhan="Ganti coolant.",
        metode="TRANSFER",
    )

    # Piutang lewat tempo yang sudah diingatkan.
    budi_overdue = record(
        budi_unit,
        "DEMO-0007",
        at(-20, 9),
        [("Servis Radiator", 1, Decimal("250000.00"), 6)],
        [("Tangki Radiator Avanza", 1, Decimal("500000.00"), 0)],
        keluhan="Radiator bocor dan mesin panas.",
        jenis_bayar="KREDIT",
        dibayar="300000.00",
        jatuh_tempo=today - timedelta(days=5),
        bergaransi=True,
        garansi_sampai=today + timedelta(days=3),
        catatan_garansi="Garansi servis 3 bulan.",
    )
    add_payment(
        budi_overdue,
        "PELUNASAN",
        "100000.00",
        at(-10, 10),
        catatan="Pelunasan sebagian.",
    )
    budi_overdue.diingatkan_pada = at(-1, 8, 30)

    # Piutang jatuh tempo hari ini, belum diingatkan.
    record(
        dewi_unit,
        "DEMO-0008",
        at(-10, 9),
        [("Ganti Oli", 1, Decimal("150000.00"), 6)],
        [("Oli Mesin 10W-40", 1, Decimal("65000.00"), 6)],
        keluhan="Ganti oli rutin.",
        jenis_bayar="KREDIT",
        dibayar="65000.00",
        jatuh_tempo=today,
        rencana_bayar="100000.00",
    )

    # Dua nota piutang untuk pelanggan yang sama (pengelompokan piutang).
    record(
        fajar_unit,
        "DEMO-0009",
        at(-12, 9),
        [
            ("Servis Radiator", 1, Decimal("250000.00"), 6),
            ("Tune Up", 1, Decimal("200000.00"), 0),
        ],
        keluhan="Radiator kurang dingin.",
        jenis_bayar="KREDIT",
        dibayar="150000.00",
        jatuh_tempo=today + timedelta(days=10),
        bergaransi=True,
        garansi_sampai=today + timedelta(days=12),
    )
    record(
        fajar_rad,
        "DEMO-0010",
        at(-12, 11),
        [("Cek Radiator", 1, Decimal("50000.00"), 0)],
        keluhan="Cek radiator cadangan.",
        jenis_bayar="KREDIT",
        dibayar="0",
        jatuh_tempo=today + timedelta(days=4),
    )

    # Nota dengan retur sebagian dan refund.
    siti_retur_day = service_day_for(6, today + timedelta(days=25))
    siti_retur = record(
        siti_unit,
        "DEMO-0011",
        day_at(siti_retur_day),
        [("Servis Radiator", 1, Decimal("250000.00"), 6)],
        [("Coolant Radiator", 1, Decimal("45000.00"), 12)],
        keluhan="Servis radiator dan ganti coolant.",
    )
    db.flush()
    coolant_part = (
        db.query(ServicePart)
        .filter(ServicePart.service_record_id == siti_retur.id)
        .one()
    )
    retur_at = day_at(siti_retur_day + timedelta(days=1), 10)
    retur = ServiceReturn(
        service_record_id=siti_retur.id,
        alasan="Coolant tidak jadi dipakai.",
        oleh="Kasir Demo",
        total_nilai=money("45000.00"),
        created_at=retur_at,
    )
    db.add(retur)
    db.flush()
    db.add(
        ServiceReturnItem(
            service_return_id=retur.id,
            service_part_id=coolant_part.id,
            stock_item_id=coolant_part.stock_item_id,
            nama_item=coolant_part.nama_part,
            jumlah=1,
            harga_satuan=money("45000.00"),
            harga_modal=money("30000.00"),
            subtotal=money("45000.00"),
        )
    )
    stock_return["Coolant Radiator"] += 1
    db.add(
        StockMovement(
            stock_item_id=coolant_part.stock_item_id,
            nama_item=coolant_part.nama_part,
            jenis="RETUR",
            jumlah=1,
            alasan=f"Retur nota {siti_retur.no_nota}",
            oleh="Kasir Demo",
            service_record_id=siti_retur.id,
            service_return_id=retur.id,
            created_at=retur_at,
        )
    )
    siti_retur.total_retur = money("45000.00")
    siti_retur.total_retur_part = money("45000.00")
    siti_retur.retur_count = 1
    add_payment(
        siti_retur,
        "REFUND",
        "-45000.00",
        retur_at,
        catatan="Refund retur coolant.",
    )

    # Servis rutin lama: sumber servis berkala dan garansi.
    rudi_old_day = service_day_for(6, today + timedelta(days=20))
    record(
        rudi_unit,
        "DEMO-0012",
        day_at(rudi_old_day),
        [("Servis Radiator", 1, Decimal("250000.00"), 6)],
        keluhan="Servis radiator rutin.",
        bergaransi=True,
        garansi_sampai=today + timedelta(days=6),
        catatan_garansi="Garansi servis 1 bulan.",
    )
    lina_old_day = service_day_for(3, today + timedelta(days=15))
    record(
        lina_unit,
        "DEMO-0013",
        day_at(lina_old_day),
        [("Cuci Radiator", 1, Decimal("100000.00"), 3)],
        keluhan="Cuci radiator rutin.",
    )

    # Nota void dengan refund penuh.
    agus_void = record(
        agus_unit,
        "DEMO-0014",
        at(-15, 10),
        [("Cek Kebocoran", 1, Decimal("75000.00"), 0)],
        keluhan="Cek kebocoran.",
    )
    void_at = at(-15, 12)
    agus_void.status = "VOID"
    agus_void.void_reason = "Pelanggan membatalkan servis."
    agus_void.voided_at = void_at
    agus_void.voided_by = "Kasir Demo"
    add_payment(
        agus_void,
        "REFUND",
        "-75000.00",
        void_at,
        catatan="Refund void DEMO-0014.",
    )

    # Kredit yang sudah lunas (riwayat pembayaran bertahap).
    siti_kredit = record(
        siti_unit,
        "DEMO-0015",
        at(-5, 9),
        [("Cek Radiator", 1, Decimal("50000.00"), 0)],
        keluhan="Cek radiator.",
        jenis_bayar="KREDIT",
        dibayar="20000.00",
        jatuh_tempo=today + timedelta(days=3),
    )
    add_payment(
        siti_kredit,
        "PELUNASAN",
        "30000.00",
        at(-4, 10),
        catatan="Pelunasan kredit.",
    )

    # Garansi yang sudah kedaluwarsa.
    record(
        dewi_unit,
        "DEMO-0016",
        at(-100, 9),
        [("Tune Up", 1, Decimal("200000.00"), 0)],
        keluhan="Tune up tahunan.",
        bergaransi=True,
        garansi_sampai=today - timedelta(days=30),
    )

    # Unit radiator copotan tanpa nopol.
    record(
        budi_rad,
        "DEMO-0017",
        at(-40, 9),
        [("Servis Radiator", 1, Decimal("250000.00"), 6)],
        keluhan="Radiator copotan dari Avanza.",
    )

    for nama, (_modal, _jual, _interval, awal) in parts_master.items():
        sisa = awal - stock_out[nama] + stock_return[nama]
        if sisa < 0:
            raise SystemExit(f"Stok {nama} menjadi negatif ({sisa}).")
        stok[nama].jumlah = sisa

    db.commit()

    sync_items(db, today=today)

    items = {
        (item.jenis, item.customer_id): item
        for item in db.query(FollowupItem).all()
        if item.status != "ARSIP"
    }
    required = [
        ("piutang", budi.id),
        ("piutang", dewi.id),
        ("piutang", fajar.id),
        ("piutang", rudi.id),
        ("piutang", hendra.id),
        ("garansi", budi.id),
        ("garansi", agus.id),
        ("garansi", rudi.id),
        ("garansi", fajar.id),
        ("servis_berkala", siti.id),
        ("servis_berkala", rudi.id),
        ("servis_berkala", lina.id),
        ("prospek", budi.id),
        ("prospek", dewi.id),
        ("prospek", fajar.id),
    ]
    missing = [key for key in required if key not in items]
    if missing:
        raise SystemExit(f"Item follow-up tidak lengkap: {missing}")

    def move(
        item,
        target,
        *,
        days=None,
        followup_days_ago=None,
        janji_days=None,
        reason,
    ):
        previous = item.status
        item.status = target
        if days is not None:
            item.tanggal_service = today + timedelta(days=days)
        if followup_days_ago is not None:
            item.followup_terakhir = now - timedelta(days=followup_days_ago)
        if janji_days is not None:
            item.janji_bayar = today + timedelta(days=janji_days)
        db.add(
            FollowupEvent(
                item_id=item.id,
                from_status=previous,
                to_status=target,
                alasan=reason,
                operator="Demo",
                created_at=now,
            )
        )

    move(
        items[("piutang", budi.id)],
        "SUDAH_FOLLOWUP",
        followup_days_ago=1,
        reason="Sudah dihubungi lewat WhatsApp.",
    )
    move(
        items[("piutang", dewi.id)],
        "JANJI_BAYAR",
        followup_days_ago=2,
        janji_days=3,
        reason="Pelanggan berjanji bayar minggu ini.",
    )
    move(
        items[("garansi", agus.id)],
        "AKAN_DATANG",
        days=4,
        followup_days_ago=1,
        reason="Pelanggan menjadwalkan datang.",
    )
    move(
        items[("garansi", rudi.id)],
        "SUDAH_FOLLOWUP",
        followup_days_ago=1,
        reason="Sudah dihubungi, menunggu konfirmasi.",
    )
    move(
        items[("servis_berkala", rudi.id)],
        "AKAN_DATANG",
        days=10,
        followup_days_ago=2,
        reason="Pelanggan menjadwalkan servis.",
    )
    move(
        items[("servis_berkala", lina.id)],
        "MASIH_KENDALA",
        followup_days_ago=3,
        reason="Pelanggan masih menunggu waktu luang.",
    )
    db.commit()

    ringkasan = payment_service.receivables(db)
    pengerjaan = pengerjaan_service.list_items(db)
    kartu = counts(db, today=today)

    print("Database uji manual:", DB_PATH)
    print("Hari ini:", today.isoformat())
    print(
        "Pelanggan:",
        db.query(Customer).count(),
        "| Unit:",
        db.query(VehicleOrUnit).count(),
        "| Nota:",
        db.query(ServiceRecord).count(),
        "| Pembayaran:",
        db.query(ServicePayment).count(),
        "| Retur:",
        db.query(ServiceReturn).count(),
    )
    print(
        "Stok:",
        ", ".join(
            f"{nama}={row.jumlah}" for nama, row in stok.items()
        ),
    )
    print(
        "Piutang:",
        ringkasan["jumlah_pelanggan"],
        "pelanggan ·",
        ringkasan["jumlah_nota"],
        "nota · sisa",
        ringkasan["total_sisa"],
    )
    print("Kendaraan selesai:", pengerjaan["jumlah"])
    print("Kartu follow-up:", kartu)
    print("Item follow-up:")
    for (jenis, customer_id), item in sorted(items.items()):
        print(
            f"  {jenis:14s} | {item.customer.nama:16s} | {item.status:13s}"
            f" | jatuh tempo {item.jatuh_tempo}"
            f" | datang {item.tanggal_service}"
        )
