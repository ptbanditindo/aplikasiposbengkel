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

    private val clock = FakeClock()
    private val oneMinute = 60_000L

    @Before
    fun setUp() {
        PinSession.clear()
        clock.elapsed = 0L
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
}
