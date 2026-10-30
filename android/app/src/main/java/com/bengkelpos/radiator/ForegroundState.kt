package com.bengkelpos.radiator

/**
 * Menandai apakah ada activity yang terlihat. Worker backup memakai ini agar
 * tidak mematikan server lokal ketika pengguna sedang memakai aplikasi.
 */
object ForegroundState {

    @Volatile
    var isForeground: Boolean = false
        private set

    fun set(value: Boolean) {
        isForeground = value
    }
}
