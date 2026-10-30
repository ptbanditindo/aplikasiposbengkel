package com.bengkelpos.radiator.pin

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PinResetKeywordTest {

    @Test
    fun `menerima reset dengan variasi huruf dan spasi`() {
        assertTrue(PinResetKeyword.matches("RESET"))
        assertTrue(PinResetKeyword.matches("reset"))
        assertTrue(PinResetKeyword.matches("Reset"))
        assertTrue(PinResetKeyword.matches("  reset  "))
    }

    @Test
    fun `menolak kata yang bukan reset`() {
        assertFalse(PinResetKeyword.matches("RESETX"))
        assertFalse(PinResetKeyword.matches("RESE"))
        assertFalse(PinResetKeyword.matches(""))
        assertFalse(PinResetKeyword.matches(null))
    }
}
