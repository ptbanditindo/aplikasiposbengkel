package com.bengkelpos.radiator.pin

/**
 * Status sesi di memori proses. Proses yang mati otomatis menghapus status ini,
 * sehingga aplikasi yang dibuka lagi selalu melewati layar PIN.
 */
object PinSession {
    private var unlockedAtElapsedMs = -1L
    private var backgroundSinceElapsedMs = -1L

    fun markUnlocked(clock: LockoutClock) {
        unlockedAtElapsedMs = clock.elapsedRealtimeMs()
        backgroundSinceElapsedMs = -1L
    }

    fun markBackground(clock: LockoutClock) {
        if (unlockedAtElapsedMs >= 0L) {
            backgroundSinceElapsedMs = clock.elapsedRealtimeMs()
        }
    }

    fun markResumed() {
        backgroundSinceElapsedMs = -1L
    }

    fun requiresPin(clock: LockoutClock, idleTimeoutMs: Long, hasPin: Boolean): Boolean {
        if (!hasPin) return false
        if (unlockedAtElapsedMs < 0L) return true
        val backgroundSince = backgroundSinceElapsedMs
        if (backgroundSince < 0L) return false
        return clock.elapsedRealtimeMs() - backgroundSince >= idleTimeoutMs
    }

    fun clear() {
        unlockedAtElapsedMs = -1L
        backgroundSinceElapsedMs = -1L
    }
}
