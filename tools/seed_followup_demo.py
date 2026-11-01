"""Isi database dummy untuk menguji Tugas follow-up.

Skrip ini menolak berjalan bila DATABASE_URL tidak mengandung kata "dummy",
sehingga database kasir asli tidak tersentuh.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_REL = "data/dummy_followup.db"
os.environ["DATABASE_URL"] = f"sqlite:///./{DB_REL}"
os.environ["BACKUP_DIR"] = "./backups_dummy_followup"
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
    ServiceJob,
    ServicePart,
    ServicePayment,
    ServiceRecord,
    StockItem,
    VehicleOrUnit,
)
from database.session import SessionLocal, init_db  # noqa: E402
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

jobs_master = {
    "Ganti oli": (Decimal("150000.00"), 6),
    "Servis radiator": (Decimal("250000.00"), 6),
    "Cuci radiator": (Decimal("100000.00"), 3),
    "Tune up": (Decimal("200000.00"), 0),
    "Cek radiator": (Decimal("50000.00"), 0),
    "Cek kebocoran": (Decimal("75000.00"), 0),
}
parts_master = {
    "Oli Mesin 10W-40": (Decimal("45000.00"), Decimal("65000.00"), 6),
    "Coolant Radiator": (Decimal("30000.00"), Decimal("45000.00"), 12),
    "Tangki Radiator Avanza": (Decimal("350000.00"), Decimal("500000.00"), 0),
}


def service_day_for(interval: int, target_due: date) -> date:
    for offset in range(0, 400):
        candidate = today - timedelta(days=offset)
        if add_months(candidate, interval) == target_due:
            return candidate
    for offset in range(0, 400):
        candidate = today - timedelta(days=offset)
        due = add_months(candidate, interval)
        if today < due <= today + timedelta(days=14):
            return candidate
    raise RuntimeError("Tidak menemukan tanggal servis untuk jatuh tempo demo.")


with SessionLocal() as db:
    jasa = {}
    for nama, (harga, interval) in jobs_master.items():
        row = HargaJasa(nama=nama, harga_standar=harga, interval_servis_bulan=interval)
        db.add(row)
        jasa[nama] = row

    stok = {}
    for nama, (modal, jual, interval) in parts_master.items():
        row = StockItem(
            kode="DMY-" + nama.split()[0].upper(),
            nama=nama,
            harga_modal=modal,
            harga_jual=jual,
            jumlah=25,
            interval_servis_bulan=interval,
        )
        db.add(row)
        stok[nama] = row

    for key, value in {
        "ops.tempo_hari": "7",
        "ops.prospek_hari": "7",
        "ops.cooldown_hari": "7",
        "ops.garansi_akan_habis_hari": "7",
        "ops.servis_berkala_awal_hari": "14",
    }.items():
        db.add(AppSetting(key=key, value=value))

    def customer(nama, nomor_hp, alamat):
        row = Customer(nama=nama, nomor_hp=nomor_hp, alamat=alamat, wa_consent=True)
        db.add(row)
        db.flush()
        return row

    def unit(cust, nopol, jenis, tahun, label):
        row = VehicleOrUnit(
            customer_id=cust.id,
            unit_type="MOBIL",
            nopol=nopol,
            jenis_mobil=jenis,
            tahun_mobil=tahun,
            label_radiator=label,
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
        bergaransi=False,
        garansi_sampai=None,
    ):
        biaya_jasa = sum(
            (money(Decimal(qty) * harga) for _, qty, harga, _ in job_rows),
            Decimal("0.00"),
        )
        total_part = sum(
            (money(Decimal(qty) * harga) for _, qty, harga, _ in part_rows),
            Decimal("0.00"),
        )
        total = money(biaya_jasa + total_part)
        paid = money(dibayar if dibayar is not None else total)
        status_bayar = "LUNAS" if paid >= total else "BELUM_LUNAS"
        row = ServiceRecord(
            unit_id=veh.id,
            no_nota=nota,
            request_id="demo-" + nota.lower(),
            waktu_service=when,
            keluhan_awal=keluhan,
            catatan_pengerjaan="Data demo Tahap 13.",
            biaya_jasa=biaya_jasa,
            total_part=total_part,
            diskon=Decimal("0.00"),
            total_servis=total,
            metode_bayar=metode,
            bayar=paid,
            kembalian=Decimal("0.00"),
            status_bayar=status_bayar,
            jenis_bayar=jenis_bayar,
            jatuh_tempo=jatuh_tempo,
            total_dibayar=paid,
            bergaransi=bergaransi,
            garansi_sampai=garansi_sampai,
            catatan_garansi="Garansi demo." if bergaransi else None,
            status_klaim="Belum claim",
        )
        db.add(row)
        db.flush()

        for nama, qty, harga, interval in job_rows:
            db.add(
                ServiceJob(
                    service_record_id=row.id,
                    harga_jasa_id=jasa[nama].id,
                    deskripsi=nama,
                    jumlah=qty,
                    harga=harga,
                    subtotal=money(Decimal(qty) * harga),
                    interval_servis_bulan=interval,
                )
            )
        for nama, qty, harga, interval in part_rows:
            db.add(
                ServicePart(
                    service_record_id=row.id,
                    stock_item_id=stok[nama].id,
                    nama_part=nama,
                    jumlah=qty,
                    harga_satuan=harga,
                    subtotal=money(Decimal(qty) * harga),
                    harga_modal=parts_master[nama][0],
                    harga_modal_estimasi=False,
                    interval_servis_bulan=interval,
                )
            )
        if paid > 0:
            db.add(
                ServicePayment(
                    service_record_id=row.id,
                    jenis=(
                        "UANG_MUKA"
                        if status_bayar == "BELUM_LUNAS"
                        else "PELUNASAN"
                    ),
                    metode=metode,
                    nominal=paid,
                    waktu=when,
                    operator="Demo",
                    catatan="Uang muka demo"
                    if status_bayar == "BELUM_LUNAS"
                    else "Pelunasan demo",
                )
            )
        return row

    budi = customer("Budi Santoso", "082117836284", "Jl. Melati 1")
    budi_unit = unit(budi, "B 1234 BUD", "Toyota Avanza", 2018, "AVANZA-BUDI")

    siti = customer("Siti Rahayu", "62 858-4641-4593", "Jl. Kenanga 2")
    siti_unit = unit(siti, "B 5678 SIT", "Honda Brio", 2019, "BRIO-SITI")

    agus = customer("Agus Pratama", "62 815-7275-4673", "Jl. Anggrek 3")
    agus_unit = unit(agus, "B 9012 AGU", "Mitsubishi Xpander", 2020, "XPANDER-AGUS")

    # 1) Piutang + prospek: servis 10 hari lalu, kredit, sisa Rp 650.000.
    record(
        budi_unit,
        "DEMO-0001",
        datetime.combine(today - timedelta(days=10), datetime.min.time()).replace(hour=9),
        [
            ("Servis radiator", 1, Decimal("250000.00"), 6),
            ("Tune up", 1, Decimal("200000.00"), 0),
        ],
        [("Tangki Radiator Avanza", 1, Decimal("500000.00"), 0)],
        keluhan="Radiator bocor dan mesin panas.",
        jenis_bayar="KREDIT",
        dibayar=Decimal("300000.00"),
        jatuh_tempo=today + timedelta(days=2),
        bergaransi=True,
        garansi_sampai=today + timedelta(days=20),
    )

    # 2) Servis berkala + garansi akan habis.
    siti_old = service_day_for(6, today + timedelta(days=5))
    record(
        siti_unit,
        "DEMO-0002",
        datetime.combine(siti_old, datetime.min.time()).replace(hour=9),
        [("Ganti oli", 1, Decimal("150000.00"), 6)],
        [("Oli Mesin 10W-40", 1, Decimal("65000.00"), 6)],
        keluhan="Ganti oli rutin.",
        bergaransi=True,
        garansi_sampai=today + timedelta(days=5),
    )
    record(
        siti_unit,
        "DEMO-0003",
        datetime.combine(today - timedelta(days=2), datetime.min.time()).replace(hour=10),
        [("Cek radiator", 1, Decimal("50000.00"), 0)],
        keluhan="Cek suhu mesin.",
    )

    # 3) Sumber garansi/servis untuk item berstatus akan datang.
    agus_old = service_day_for(6, today + timedelta(days=3))
    record(
        agus_unit,
        "DEMO-0004",
        datetime.combine(agus_old, datetime.min.time()).replace(hour=9),
        [("Servis radiator", 1, Decimal("250000.00"), 6)],
        [("Coolant Radiator", 1, Decimal("45000.00"), 12)],
        keluhan="Radiator kurang dingin.",
        bergaransi=True,
        garansi_sampai=today + timedelta(days=3),
    )
    record(
        agus_unit,
        "DEMO-0005",
        datetime.combine(today - timedelta(days=1), datetime.min.time()).replace(hour=11),
        [("Cek kebocoran", 1, Decimal("75000.00"), 0)],
        keluhan="Cek kebocoran setelah servis.",
    )

    # 4) Empat item: piutang, prospek, servis berkala, dan garansi akan habis.
    dewi = customer("Dewi Lestari", "+62 878-2405-3959", "Jl. Mawar 4")
    dewi_unit = unit(dewi, "B 3456 DEW", "Daihatsu Terios", 2017, "TERIOS-DEWI")
    dewi_old = service_day_for(6, today + timedelta(days=5))
    record(
        dewi_unit,
        "DEMO-0006",
        datetime.combine(dewi_old, datetime.min.time()).replace(hour=9),
        [("Ganti oli", 1, Decimal("150000.00"), 6)],
        [("Oli Mesin 10W-40", 1, Decimal("65000.00"), 6)],
        keluhan="Ganti oli rutin.",
    )
    record(
        dewi_unit,
        "DEMO-0007",
        datetime.combine(today - timedelta(days=12), datetime.min.time()).replace(hour=9),
        [
            ("Servis radiator", 1, Decimal("250000.00"), 6),
            ("Tune up", 1, Decimal("200000.00"), 0),
        ],
        [("Tangki Radiator Avanza", 2, Decimal("500000.00"), 0)],
        keluhan="Radiator bocor dan mesin panas.",
        jenis_bayar="KREDIT",
        dibayar=Decimal("500000.00"),
        jatuh_tempo=today + timedelta(days=4),
        bergaransi=True,
        garansi_sampai=today + timedelta(days=6),
    )

    # 5) Dua jadwal akan datang: garansi dan servis berkala.
    rudi = customer("Rudi Hartono", "+62 882-9474-4259", "Jl. Dahlia 5")
    rudi_unit = unit(rudi, "B 7890 RUD", "Suzuki Ertiga", 2019, "ERTIGA-RUDI")
    rudi_old = service_day_for(6, today + timedelta(days=7))
    record(
        rudi_unit,
        "DEMO-0008",
        datetime.combine(rudi_old, datetime.min.time()).replace(hour=9),
        [("Servis radiator", 1, Decimal("250000.00"), 6)],
        [("Coolant Radiator", 1, Decimal("45000.00"), 12)],
        keluhan="Servis radiator rutin.",
        bergaransi=True,
        garansi_sampai=today + timedelta(days=4),
    )
    record(
        rudi_unit,
        "DEMO-0009",
        datetime.combine(today - timedelta(days=3), datetime.min.time()).replace(hour=10),
        [("Cek radiator", 1, Decimal("50000.00"), 0)],
        keluhan="Cek kebocoran.",
    )

    # 6) Piutang lewat jatuh tempo + prospek + servis berkala + garansi.
    maya = customer("Maya Sari", "+62 859-7252-2572", "Jl. Cempaka 6")
    maya_unit = unit(maya, "B 2345 MAY", "Nissan Grand Livina", 2016, "LIVINA-MAYA")
    maya_old = service_day_for(3, today + timedelta(days=6))
    record(
        maya_unit,
        "DEMO-0010",
        datetime.combine(maya_old, datetime.min.time()).replace(hour=9),
        [("Cuci radiator", 1, Decimal("100000.00"), 3)],
        keluhan="Cuci radiator rutin.",
    )
    record(
        maya_unit,
        "DEMO-0011",
        datetime.combine(today - timedelta(days=15), datetime.min.time()).replace(hour=9),
        [
            ("Servis radiator", 1, Decimal("250000.00"), 0),
            ("Tune up", 1, Decimal("200000.00"), 0),
        ],
        keluhan="Radiator kurang dingin.",
        jenis_bayar="KREDIT",
        dibayar=Decimal("200000.00"),
        jatuh_tempo=today - timedelta(days=1),
        bergaransi=True,
        garansi_sampai=today + timedelta(days=2),
    )

    # 7) Piutang + prospek + garansi + servis berkala.
    fajar = customer("Fajar Nugroho", "62 857-2091-4159", "Jl. Flamboyan 7")
    fajar_unit = unit(fajar, "B 6789 FAJ", "Toyota Rush", 2021, "RUSH-FAJAR")
    fajar_old = service_day_for(6, today + timedelta(days=9))
    record(
        fajar_unit,
        "DEMO-0012",
        datetime.combine(fajar_old, datetime.min.time()).replace(hour=9),
        [("Ganti oli", 1, Decimal("150000.00"), 6)],
        [("Oli Mesin 10W-40", 1, Decimal("65000.00"), 6)],
        keluhan="Ganti oli rutin.",
    )
    record(
        fajar_unit,
        "DEMO-0013",
        datetime.combine(today - timedelta(days=8), datetime.min.time()).replace(hour=9),
        [
            ("Servis radiator", 1, Decimal("250000.00"), 0),
            ("Tune up", 1, Decimal("200000.00"), 0),
        ],
        [("Tangki Radiator Avanza", 1, Decimal("500000.00"), 0)],
        keluhan="Radiator bocor.",
        jenis_bayar="KREDIT",
        dibayar=Decimal("400000.00"),
        jatuh_tempo=today + timedelta(days=1),
        bergaransi=True,
        garansi_sampai=today + timedelta(days=6),
    )

    # 8) Piutang + prospek + garansi + servis yang sudah di-follow up.
    lina = customer("Lina Marlina", "+62 882-2230-6379", "Jl. Teratai 8")
    lina_unit = unit(lina, "B 4567 LIN", "Honda Mobilio", 2018, "MOBILIO-LINA")
    lina_old = service_day_for(3, today + timedelta(days=8))
    record(
        lina_unit,
        "DEMO-0014",
        datetime.combine(lina_old, datetime.min.time()).replace(hour=9),
        [("Cuci radiator", 1, Decimal("100000.00"), 3)],
        keluhan="Cuci radiator rutin.",
    )
    record(
        lina_unit,
        "DEMO-0015",
        datetime.combine(today - timedelta(days=10), datetime.min.time()).replace(hour=9),
        [("Tune up", 1, Decimal("200000.00"), 0)],
        keluhan="Mesin kurang bertenaga.",
        jenis_bayar="KREDIT",
        dibayar=Decimal("100000.00"),
        jatuh_tempo=today + timedelta(days=5),
        bergaransi=True,
        garansi_sampai=today + timedelta(days=3),
    )

    db.commit()

    sync_items(db, today=today)

    items = {
        (item.jenis, item.customer_id): item
        for item in db.query(FollowupItem).all()
        if item.status != "ARSIP"
    }

    def move(item, target, *, days=None, followup_at=None, operator="Demo", reason="Demo."):
        previous = item.status
        item.status = target
        if days is not None:
            item.tanggal_service = today + timedelta(days=days)
        if followup_at is not None:
            item.followup_terakhir = followup_at
        db.add(
            FollowupEvent(
                item_id=item.id,
                from_status=previous,
                to_status=target,
                alasan=reason,
                operator=operator,
                created_at=followup_at or now,
            )
        )

    for jenis, days in (("garansi", 4), ("servis_berkala", 8)):
        move(
            items[(jenis, agus.id)],
            "AKAN_DATANG",
            days=days,
            reason="Demo: pelanggan sudah menjadwalkan datang.",
        )
    for jenis, days in (("garansi", 6), ("servis_berkala", 10)):
        move(
            items[(jenis, rudi.id)],
            "AKAN_DATANG",
            days=days,
            reason="Demo: pelanggan sudah menjadwalkan datang.",
        )
    move(
        items[("servis_berkala", lina.id)],
        "SUDAH_FOLLOWUP",
        followup_at=now - timedelta(days=8),
        operator="Kasir Siti",
        reason="Demo: sudah dihubungi, menunggu konfirmasi.",
    )

    items[("piutang", dewi.id)].penanggung_jawab = "Kasir Siti"
    items[("piutang", fajar.id)].penanggung_jawab = "Kasir Siti"
    items[("garansi", lina.id)].penanggung_jawab = "Mekanik Andi"
    items[("servis_berkala", rudi.id)].penanggung_jawab = "Mekanik Andi"
    db.commit()

    print("Database dummy:", DB_PATH)
    print("Hari ini:", today.isoformat())
    print("Kartu:", counts(db, today=today))
    print("Item follow-up:")
    for (jenis, customer_id), item in sorted(items.items()):
        print(
            f"  {jenis:14s} | {item.customer.nama:16s} | {item.status:12s}"
            f" | jatuh tempo {item.jatuh_tempo} | datang {item.tanggal_service}"
            f" | {item.judul}"
        )
