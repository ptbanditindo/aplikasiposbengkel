package com.bengkelpos.radiator.pin

object LockoutPolicy {
    private const val SECOND_MS = 1_000L
    private const val MINUTE_MS = 60L * SECOND_MS

    /** Percobaan ke-3 memicu kunci 30 detik; percobaan 1-2 belum mengunci. */
    const val ATTEMPTS_BEFORE_LOCK = 3

    fun lockDurationMs(failedAttempts: Int): Long = when {
        failedAttempts < 3 -> 0L
        failedAttempts < 5 -> 30L * SECOND_MS
        failedAttempts < 7 -> 5L * MINUTE_MS
        failedAttempts < 10 -> 30L * MINUTE_MS
        else -> 60L * MINUTE_MS
    }

    fun remainingAttemptsBeforeLock(failedAttempts: Int): Int =
        (ATTEMPTS_BEFORE_LOCK - failedAttempts).coerceAtLeast(0)
}
