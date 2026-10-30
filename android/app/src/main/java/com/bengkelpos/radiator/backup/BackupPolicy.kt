package com.bengkelpos.radiator.backup

import java.time.Duration
import java.time.ZonedDateTime

/**
 * Aturan murni penjadwalan backup agar bisa diuji tanpa perangkat.
 *
 * Ref: T-06 - WorkManager menentukan kapan worker berjalan; kelas ini hanya
 * menghitung jeda awal dan memutuskan perlu-tidaknya retry dari status API.
 */
object BackupPolicy {

    const val PERIOD_HOURS = 24L
    const val RETRY_MINUTES = 30L
    const val DEFAULT_JAM = "21:00"

    private val JAM_PATTERN = Regex("^([01]\\d|2[0-3]):([0-5]\\d)$")

    fun normalizeJam(value: String?): Pair<Int, Int>? {
        val match = JAM_PATTERN.matchEntire(value?.trim().orEmpty()) ?: return null
        return match.groupValues[1].toInt() to match.groupValues[2].toInt()
    }

    fun formatJam(value: Pair<Int, Int>?): String {
        val jam = value ?: return DEFAULT_JAM
        return "%02d:%02d".format(jam.first, jam.second)
    }

    /** Jeda sampai jam kirim berikutnya; jam yang sudah lewat berarti besok. */
    fun initialDelayMillis(now: ZonedDateTime, hour: Int, minute: Int): Long {
        var target = now
            .withHour(hour)
            .withMinute(minute)
            .withSecond(0)
            .withNano(0)
        if (target.isBefore(now)) target = target.plusDays(1)
        return Duration.between(now, target).toMillis()
    }

    /** Hanya status "ok" yang dianggap tuntas; selain itu WorkManager mencoba lagi. */
    fun shouldRetry(status: String?): Boolean = status != "ok"
}
