"""Mode maintenance saat pemulihan database.

Menahan permintaan baru selama restore berlangsung, menghitung permintaan
aktif (termasuk backup terjadwal), dan memberi jalan bagi restore untuk
menunggu sampai tidak ada penulis yang memakai database lama.
"""
from __future__ import annotations

import threading
import time

RESTORE_PATH = "/api/admin/restore"
HEALTH_PATH = "/api/health"
RESTORE_WAIT_TIMEOUT = 30.0


class MaintenanceGate:
    def __init__(self) -> None:
        self._cond = threading.Condition(threading.Lock())
        self._active = 0
        self._restoring = False

    def try_enter(self) -> bool:
        """Daftarkan satu pekerjaan aktif; False bila sedang restore."""
        with self._cond:
            if self._restoring:
                return False
            self._active += 1
            return True

    def leave(self) -> None:
        with self._cond:
            self._active = max(0, self._active - 1)
            if self._active == 0:
                self._cond.notify_all()

    def begin_restore(self, timeout: float = RESTORE_WAIT_TIMEOUT) -> bool:
        """Masuk mode restore dan tunggu pekerjaan aktif selesai.

        False bila restore lain sedang berjalan atau pekerjaan aktif belum
        selesai sampai batas waktu.
        """
        deadline = time.monotonic() + timeout
        with self._cond:
            if self._restoring:
                return False
            self._restoring = True
            while self._active > 0:
                sisa = deadline - time.monotonic()
                if sisa <= 0:
                    self._restoring = False
                    self._cond.notify_all()
                    return False
                self._cond.wait(sisa)
            return True

    def end_restore(self) -> None:
        with self._cond:
            self._restoring = False
            self._cond.notify_all()

    def is_restoring(self) -> bool:
        with self._cond:
            return self._restoring

    @property
    def active_count(self) -> int:
        with self._cond:
            return self._active


gate = MaintenanceGate()

__all__ = [
    "HEALTH_PATH",
    "RESTORE_PATH",
    "RESTORE_WAIT_TIMEOUT",
    "MaintenanceGate",
    "gate",
]
