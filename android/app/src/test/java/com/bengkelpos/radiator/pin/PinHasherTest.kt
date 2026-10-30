package com.bengkelpos.radiator.pin

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PinHasherTest {

    @Test
    fun `hash dapat diverifikasi setelah dibuat ulang`() {
        val record = PinHasher.create("246810".toCharArray(), iterations = 1_000)

        assertTrue(PinHasher.verify("246810".toCharArray(), record))
        assertFalse(PinHasher.verify("246811".toCharArray(), record))
    }

    @Test
    fun `format menyimpan skema iterasi salt dan hash`() {
        val record = PinHasher.create("123456".toCharArray(), iterations = 1_000)
        val parts = record.split("$")

        assertEquals(4, parts.size)
        assertEquals("pbkdf2_sha256", parts[0])
        assertEquals("1000", parts[1])
        assertTrue(parts[2].isNotEmpty())
        assertTrue(parts[3].isNotEmpty())
    }

    @Test
    fun `salt acak membuat record berbeda untuk pin yang sama`() {
        val first = PinHasher.create("123456".toCharArray(), iterations = 1_000)
        val second = PinHasher.create("123456".toCharArray(), iterations = 1_000)

        assertNotEquals(first, second)
        assertTrue(PinHasher.verify("123456".toCharArray(), first))
        assertTrue(PinHasher.verify("123456".toCharArray(), second))
    }
}
