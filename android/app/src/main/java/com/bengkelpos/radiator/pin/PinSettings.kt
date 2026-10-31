package com.bengkelpos.radiator.pin

import android.content.Context

class PinSettings(context: Context) : SessionStore {
    private val prefs = context.applicationContext.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)

    var idleMinutes: Int
        get() = prefs.getInt(KEY_IDLE_MINUTES, DEFAULT_IDLE_MINUTES)
            .coerceIn(MIN_IDLE_MINUTES, MAX_IDLE_MINUTES)
        set(value) {
            prefs.edit()
                .putInt(KEY_IDLE_MINUTES, value.coerceIn(MIN_IDLE_MINUTES, MAX_IDLE_MINUTES))
                .apply()
        }

    fun idleTimeoutMs(): Long = idleMinutes * 60_000L

    // Waktu latar belakang harus tersimpan sebelum proses dimatikan, jadi
    // memakai commit() yang menulis langsung ke disk.
    override fun saveBackground(elapsedMs: Long) {
        prefs.edit().putLong(KEY_BACKGROUND_ELAPSED, elapsedMs).commit()
    }

    override fun clearBackground() {
        prefs.edit().remove(KEY_BACKGROUND_ELAPSED).commit()
    }

    override fun backgroundElapsedMs(): Long = prefs.getLong(KEY_BACKGROUND_ELAPSED, -1L)

    override fun saveForcedLock() {
        prefs.edit().putBoolean(KEY_FORCED_LOCK, true).commit()
    }

    override fun isForcedLock(): Boolean = prefs.getBoolean(KEY_FORCED_LOCK, false)

    override fun clearSession() {
        prefs.edit()
            .remove(KEY_BACKGROUND_ELAPSED)
            .remove(KEY_FORCED_LOCK)
            .commit()
    }

    companion object {
        const val DEFAULT_IDLE_MINUTES = 1
        const val MIN_IDLE_MINUTES = 1
        const val MAX_IDLE_MINUTES = 60

        private const val FILE_NAME = "pin_settings"
        private const val KEY_IDLE_MINUTES = "idle_minutes"
        private const val KEY_BACKGROUND_ELAPSED = "background_elapsed_ms"
        private const val KEY_FORCED_LOCK = "forced_lock"
    }
}
