package com.bengkelpos.radiator.pin

data class LockoutState(
    val failedAttempts: Int,
    val lockStartedWallMs: Long,
    val lockStartedElapsedMs: Long,
    val lockDurationMs: Long,
) {
    val hasLock: Boolean get() = lockDurationMs > 0L

    /**
     * Sisa kunci memakai nilai terbesar dari dua jam, supaya pemunduran jam dinding
     * atau reboot (elapsedRealtime kembali ke nol) tidak memperpendek kunci.
     */
    fun remainingLockMs(nowElapsedMs: Long, nowWallMs: Long): Long {
        if (!hasLock) return 0L
        val elapsedRemaining = if (nowElapsedMs < lockStartedElapsedMs) {
            lockDurationMs
        } else {
            lockDurationMs - (nowElapsedMs - lockStartedElapsedMs)
        }
        val wallRemaining = if (nowWallMs < lockStartedWallMs) {
            lockDurationMs
        } else {
            lockDurationMs - (nowWallMs - lockStartedWallMs)
        }
        return maxOf(elapsedRemaining, wallRemaining, 0L)
    }

    fun isLocked(nowElapsedMs: Long, nowWallMs: Long): Boolean =
        remainingLockMs(nowElapsedMs, nowWallMs) > 0L
}
