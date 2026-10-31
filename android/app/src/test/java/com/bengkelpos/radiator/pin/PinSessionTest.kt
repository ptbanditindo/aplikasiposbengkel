package com.bengkelpos.radiator.pin

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class PinSessionTest {

    private class FakeClock(var elapsed: Long = 0L) : LockoutClock {
        override fun elapsedRealtimeMs(): Long = elapsed
        override fun wallClockMs(): Long = 1_000_000L + elapsed
    }

    private class FakeStore : SessionStore {
        var backgroundElapsed = -1L
        var forced = false

        override fun saveBackground(elapsedMs: Long) {
            backgroundElapsed = elapsedMs
        }

        override fun clearBackground() {
            backgroundElapsed = -1L
        }

        override fun backgroundElapsedMs(): Long = backgroundElapsed

        override fun saveForcedLock() {
            forced = true
        }

        override fun isForcedLock(): Boolean = forced

        override fun clearSession() {
            backgroundElapsed = -1L
            forced = false
        }
    }

    private val clock = FakeClock()
    private val store = FakeStore()
    private val oneMinute = 60_000L

    @Before
    fun setUp() {
        PinSession.clear()
        clock.elapsed = 0L
        store.clearSession()
    }

    @Test
    fun `tanpa pin tidak perlu gerbang`() {
        assertFalse(PinSession.requiresPin(clock, oneMinute, hasPin = false))
    }

    @Test
    fun `proses baru selalu meminta pin`() {
        assertTrue(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `selama di depan tidak meminta pin lagi`() {
        PinSession.markUnlocked(clock)
        clock.elapsed = 10_000L
        assertFalse(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `latar belakang kurang dari batas tidak meminta pin`() {
        PinSession.markUnlocked(clock)
        clock.elapsed = 5_000L
        PinSession.markBackground(clock)
        clock.elapsed = 60_000L
        assertFalse(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `latar belakang melewati batas meminta pin`() {
        PinSession.markUnlocked(clock)
        clock.elapsed = 5_000L
        PinSession.markBackground(clock)
        clock.elapsed = 66_000L
        assertTrue(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `unlock ulang menghapus waktu latar belakang`() {
        PinSession.markUnlocked(clock)
        clock.elapsed = 5_000L
        PinSession.markBackground(clock)
        clock.elapsed = 70_000L
        PinSession.markUnlocked(clock)
        clock.elapsed = 200_000L
        assertFalse(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `markResumed menghapus penanda latar belakang`() {
        PinSession.markUnlocked(clock)
        clock.elapsed = 5_000L
        PinSession.markBackground(clock)
        clock.elapsed = 70_000L
        PinSession.markResumed()
        assertFalse(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `proses mati dalam batas tidak meminta pin`() {
        PinSession.markUnlocked(clock, store)
        clock.elapsed = 5_000L
        PinSession.markBackground(clock, store)

        // Proses dimatikan sistem: memori hilang, penyimpanan tetap.
        PinSession.clear()
        clock.elapsed = 50_000L
        PinSession.restore(clock, store)

        assertFalse(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `proses mati melewati batas meminta pin`() {
        PinSession.markUnlocked(clock, store)
        clock.elapsed = 5_000L
        PinSession.markBackground(clock, store)

        PinSession.clear()
        clock.elapsed = 70_000L
        PinSession.restore(clock, store)

        assertTrue(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `reboot selalu meminta pin`() {
        PinSession.markUnlocked(clock, store)
        clock.elapsed = 500_000L
        PinSession.markBackground(clock, store)

        PinSession.clear()
        // elapsedRealtime kembali kecil setelah perangkat menyala ulang.
        clock.elapsed = 10_000L
        PinSession.restore(clock, store)

        assertTrue(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `restore tanpa penanda latar belakang meminta pin`() {
        PinSession.markUnlocked(clock, store)

        PinSession.clear()
        clock.elapsed = 10_000L
        PinSession.restore(clock, store)

        assertTrue(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `kunci sekarang tetap meminta pin setelah proses baru`() {
        PinSession.markUnlocked(clock, store)
        PinSession.forceLock(store)

        PinSession.clear()
        clock.elapsed = 10_000L
        PinSession.restore(clock, store)

        assertTrue(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `unlock menghapus kunci paksa tersimpan`() {
        PinSession.markUnlocked(clock, store)
        PinSession.forceLock(store)
        clock.elapsed = 10_000L
        PinSession.markUnlocked(clock, store)

        assertFalse(store.isForcedLock())

        clock.elapsed = 15_000L
        PinSession.markBackground(clock, store)
        PinSession.clear()
        clock.elapsed = 20_000L
        PinSession.restore(clock, store)

        assertFalse(PinSession.requiresPin(clock, oneMinute, hasPin = true))
    }

    @Test
    fun `markResumed menghapus penanda tersimpan`() {
        PinSession.markUnlocked(clock, store)
        clock.elapsed = 5_000L
        PinSession.markBackground(clock, store)
        PinSession.markResumed(store)

        assertTrue(store.backgroundElapsedMs() < 0L)
    }
}
