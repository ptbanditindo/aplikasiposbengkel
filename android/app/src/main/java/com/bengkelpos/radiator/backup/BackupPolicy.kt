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
    const val MAX_ATTEMPTS = 5

    private val JAM_PATTERN = Regex("^([01]\\d|2[0-3]):([0-5]\\d)$")
    private val PERMANENT_TOKEN_MARKERS = listOf(
        "aeadbadtag",
        "corrupt",
        "invalidprotocolbuffer",
        "invalid key",
        "permanently invalidated",
    )

    enum class Decision { RETRY, GIVE_UP }

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

    /**
     * Kredensial yang rusak permanen tidak boleh diulang selamanya. Kegagalan
     * lain (mis. perangkat belum dibuka setelah reboot) dianggap sementara.
     */
    fun isPermanentTokenFailure(error: Throwable?): Boolean {
        val text = generateSequence(error) { it.cause }
            .joinToString(" ") { (it.message ?: "") + " " + it.javaClass.simpleName }
            .lowercase()
        return PERMANENT_TOKEN_MARKERS.any { text.contains(it) }
    }

    fun tokenFailureDecision(error: Throwable?, attempt: Int): Decision =
        if (isPermanentTokenFailure(error)) Decision.GIVE_UP else failureDecision(attempt)

    fun backendFailureDecision(attempt: Int): Decision = failureDecision(attempt)

    private fun failureDecision(attempt: Int): Decision =
        if (attempt >= MAX_ATTEMPTS) Decision.GIVE_UP else Decision.RETRY
}
