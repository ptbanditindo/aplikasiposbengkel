"""S-02: seed default hanya sekali; restart dan restore tidak menghidupkannya."""
from __future__ import annotations

from sqlalchemy import delete, func, select

from database.models import AppSetting, HargaJasa, StockItem
from database.seed import SEED_DONE_KEY, seed_defaults



def _count(db, model):
    return db.scalar(select(func.count()).select_from(model)) or 0


def _delete_catalog(db):
    db.execute(delete(StockItem))
    db.execute(delete(HargaJasa))
    db.commit()


def _remove_seed_marker(db):
    db.execute(delete(AppSetting).where(AppSetting.key == SEED_DONE_KEY))
    db.commit()


def test_restart_tidak_menghidupkan_master_yang_dihapus(client, db_session):
    _delete_catalog(db_session)

    # Simulasi startup berikutnya.
    seed_defaults(db_session)

    assert _count(db_session, StockItem) == 0
    assert _count(db_session, HargaJasa) == 0
    marker = db_session.get(AppSetting, SEED_DONE_KEY)
    assert marker is not None and marker.value == "1"


def test_database_lama_dengan_data_hanya_ditandai(client, db_session, create_customer):
    create_customer(nama="Pelanggan Lama")
    _delete_catalog(db_session)
    _remove_seed_marker(db_session)

    seed_defaults(db_session)

    assert _count(db_session, StockItem) == 0
    assert _count(db_session, HargaJasa) == 0
    marker = db_session.get(AppSetting, SEED_DONE_KEY)
    assert marker is not None and marker.value == "1"


def test_restore_backup_katalog_kosong_tetap_kosong(client, db_session):
    _delete_catalog(db_session)
    _remove_seed_marker(db_session)

    backup = client.post("/api/admin/backup")
    assert backup.status_code == 200, backup.text

    restore = client.post(
        "/api/admin/restore",
        files={"file": ("backup.db", backup.content, "application/x-sqlite3")},
    )
    assert restore.status_code == 200, restore.text

    assert client.get("/api/stock").json() == []
    assert client.get("/api/harga-jasa").json() == []
    marker = db_session.get(AppSetting, SEED_DONE_KEY)
    assert marker is not None and marker.value == "1"
