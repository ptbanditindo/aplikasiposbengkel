package com.bengkelpos.radiator.pin

/**
 * Status sesi di memori proses. Waktu masuk latar belakang juga dicatat ke
 * [SessionStore] agar batas "Kunci otomatis" tetap berlaku setelah proses
 * aplikasi dimatikan sistem. Reboot perangkat selalu meminta PIN lagi.
 */
object PinSession {
    private var unlockedAtElapsedMs = -1L
    private var backgroundSinceElapsedMs = -1L
    private var forcedLock = false

    fun restore(clock: LockoutClock, store: SessionStore) {
        forcedLock = store.isForcedLock()
        val stored = store.backgroundElapsedMs()
        if (stored < 0L) return

        val current = clock.elapsedRealtimeMs()
        if (stored > current) {
            // elapsedRealtime kembali ke nol berarti perangkat reboot; sesi
            // lama tidak boleh dipercaya.
            forcedLock = true
            unlockedAtElapsedMs = 0L
            backgroundSinceElapsedMs = 0L
            return
        }
        unlockedAtElapsedMs = 0L
        backgroundSinceElapsedMs = stored
    }

    fun markUnlocked(clock: LockoutClock, store: SessionStore? = null) {
        unlockedAtElapsedMs = clock.elapsedRealtimeMs()
        backgroundSinceElapsedMs = -1L
        forcedLock = false
        store?.clearSession()
    }

    fun markBackground(clock: LockoutClock, store: SessionStore? = null) {
        if (unlockedAtElapsedMs >= 0L) {
            backgroundSinceElapsedMs = clock.elapsedRealtimeMs()
            store?.saveBackground(backgroundSinceElapsedMs)
        }
    }

    fun markResumed(store: SessionStore? = null) {
        backgroundSinceElapsedMs = -1L
        store?.clearBackground()
    }

    fun forceLock(store: SessionStore) {
        forcedLock = true
        store.saveForcedLock()
    }

    fun requiresPin(clock: LockoutClock, idleTimeoutMs: Long, hasPin: Boolean): Boolean {
        if (!hasPin) return false
        if (forcedLock) return true
        if (unlockedAtElapsedMs < 0L) return true
        val backgroundSince = backgroundSinceElapsedMs
        if (backgroundSince < 0L) return false
        return clock.elapsedRealtimeMs() - backgroundSince >= idleTimeoutMs
    }

    fun clear(store: SessionStore? = null) {
        unlockedAtElapsedMs = -1L
        backgroundSinceElapsedMs = -1L
        forcedLock = false
        store?.clearSession()
    }
}
