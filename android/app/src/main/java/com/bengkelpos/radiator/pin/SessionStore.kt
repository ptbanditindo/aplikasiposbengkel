package com.bengkelpos.radiator.pin

/**
 * Simpanan waktu latar belakang agar batas "Kunci otomatis" tetap berlaku
 * ketika proses aplikasi dimatikan sistem lalu dibuka kembali.
 */
interface SessionStore {
    fun saveBackground(elapsedMs: Long)
    fun clearBackground()
    fun backgroundElapsedMs(): Long
    fun saveForcedLock()
    fun isForcedLock(): Boolean
    fun clearSession()
}
