package com.bengkelpos.radiator.pin

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PinEnrollmentTest {

    @Test
    fun `pin konfirmasi yang cocok tetap utuh hingga disimpan`() {
        val firstPin = "246810".toCharArray()
        val confirmation = "246810".toCharArray()

        val toSave = PinEnrollment.confirmedPin(firstPin, confirmation)
        assertNotNull(toSave)
        assertEquals("246810", String(toSave!!))

        val record = PinHasher.create(toSave, iterations = 1_000)
        toSave.fill('\u0000')

        assertTrue(PinHasher.verify("246810".toCharArray(), record))
    }

    @Test
    fun `pin berbeda tidak dikembalikan untuk disimpan`() {
        val firstPin = "246810".toCharArray()
        val confirmation = "246811".toCharArray()

        assertNull(PinEnrollment.confirmedPin(firstPin, confirmation))
        assertNull(PinEnrollment.confirmedPin(null, confirmation))
    }
}
