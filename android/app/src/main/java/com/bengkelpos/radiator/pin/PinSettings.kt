package com.bengkelpos.radiator.pin

import android.content.Context

class PinSettings(context: Context) {
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

    companion object {
        const val DEFAULT_IDLE_MINUTES = 1
        const val MIN_IDLE_MINUTES = 1
        const val MAX_IDLE_MINUTES = 60

        private const val FILE_NAME = "pin_settings"
        private const val KEY_IDLE_MINUTES = "idle_minutes"
    }
}
