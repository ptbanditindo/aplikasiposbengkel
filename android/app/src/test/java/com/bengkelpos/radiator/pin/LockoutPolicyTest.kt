package com.bengkelpos.radiator.pin

import org.junit.Assert.assertEquals
import org.junit.Test

class LockoutPolicyTest {

    @Test
    fun `percobaan pertama dan kedua belum mengunci`() {
        assertEquals(0L, LockoutPolicy.lockDurationMs(1))
        assertEquals(0L, LockoutPolicy.lockDurationMs(2))
    }

    @Test
    fun `percobaan ketiga dan keempat dikunci 30 detik`() {
        assertEquals(30_000L, LockoutPolicy.lockDurationMs(3))
        assertEquals(30_000L, LockoutPolicy.lockDurationMs(4))
    }

    @Test
    fun `percobaan kelima dan keenam dikunci 5 menit`() {
        assertEquals(300_000L, LockoutPolicy.lockDurationMs(5))
        assertEquals(300_000L, LockoutPolicy.lockDurationMs(6))
    }

    @Test
    fun `percobaan ketujuh sampai kesembilan dikunci 30 menit`() {
        assertEquals(1_800_000L, LockoutPolicy.lockDurationMs(7))
        assertEquals(1_800_000L, LockoutPolicy.lockDurationMs(8))
        assertEquals(1_800_000L, LockoutPolicy.lockDurationMs(9))
    }

    @Test
    fun `percobaan kesepuluh dan seterusnya dikunci 1 jam`() {
        assertEquals(3_600_000L, LockoutPolicy.lockDurationMs(10))
        assertEquals(3_600_000L, LockoutPolicy.lockDurationMs(11))
        assertEquals(3_600_000L, LockoutPolicy.lockDurationMs(50))
    }

    @Test
    fun `sisa percobaan sebelum dikunci`() {
        assertEquals(2, LockoutPolicy.remainingAttemptsBeforeLock(1))
        assertEquals(1, LockoutPolicy.remainingAttemptsBeforeLock(2))
        assertEquals(0, LockoutPolicy.remainingAttemptsBeforeLock(3))
        assertEquals(0, LockoutPolicy.remainingAttemptsBeforeLock(10))
    }
}
