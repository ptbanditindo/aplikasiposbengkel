package com.bengkelpos.radiator.pin

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LockoutStateTest {

    private fun locked(
        durationMs: Long = 30_000L,
        startedElapsed: Long = 10_000L,
        startedWall: Long = 1_000_000L,
    ) = LockoutState(
        failedAttempts = 3,
        lockStartedWallMs = startedWall,
        lockStartedElapsedMs = startedElapsed,
        lockDurationMs = durationMs,
    )

    @Test
    fun `tanpa kunci sisa selalu nol`() {
        val state = locked(durationMs = 0L)
        assertFalse(state.hasLock)
        assertEquals(0L, state.remainingLockMs(0L, 0L))
    }

    @Test
    fun `sisa kunci mengikuti jam elapsed`() {
        val state = locked()
        assertEquals(30_000L, state.remainingLockMs(10_000L, 1_000_000L))
        assertEquals(20_000L, state.remainingLockMs(20_000L, 1_010_000L))
        assertEquals(0L, state.remainingLockMs(40_000L, 1_030_000L))
        assertTrue(state.isLocked(20_000L, 1_010_000L))
        assertFalse(state.isLocked(40_000L, 1_030_000L))
    }

    @Test
    fun `jam dinding dimundurkan tidak memperpendek kunci`() {
        val state = locked()
        // elapsed baru 5 detik, jam dinding malah lebih awal dari waktu mulai kunci.
        assertEquals(30_000L, state.remainingLockMs(15_000L, 900_000L))
    }

    @Test
    fun `reboot membuat elapsed kembali nol sehingga kunci tetap penuh`() {
        val state = locked()
        assertEquals(30_000L, state.remainingLockMs(1_000L, 1_000_000L))
    }

    @Test
    fun `jam dinding dimajukan tidak memperpendek kunci bila elapsed belum habis`() {
        val state = locked()
        assertEquals(20_000L, state.remainingLockMs(20_000L, 9_999_999L))
    }

    @Test
    fun `nilai terbesar dari dua jam dipakai`() {
        val state = locked()
        // elapsed tersisa 5 detik, jam dinding tersisa 25 detik.
        assertEquals(25_000L, state.remainingLockMs(35_000L, 1_005_000L))
    }
}
