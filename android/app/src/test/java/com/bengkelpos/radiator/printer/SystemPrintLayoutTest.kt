package com.bengkelpos.radiator.printer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SystemPrintLayoutTest {

    @Test
    fun `lebar kertas hanya 58 atau 80`() {
        assertEquals(58, SystemPrintLayout.normalizePaperWidth(0))
        assertEquals(58, SystemPrintLayout.normalizePaperWidth(57))
        assertEquals(80, SystemPrintLayout.normalizePaperWidth(80))
        assertEquals(58, SystemPrintLayout.normalizePaperWidth(120))
        assertEquals(32, SystemPrintLayout.columns(58))
        assertEquals(48, SystemPrintLayout.columns(80))
    }

    @Test
    fun `baris kontrol dibersihkan dan baris kosong tepi dibuang`() {
        val clean = SystemPrintLayout.sanitize(
            listOf("", "  ", "Total\u0000 Rp 10.000 ", "\u001B@", "Selesai", "", ""),
        )

        assertEquals(listOf("Total  Rp 10.000", " @", "Selesai"), clean)
    }

    @Test
    fun `daftar kosong tidak menghasilkan halaman`() {
        assertEquals(emptyList<List<String>>(), SystemPrintLayout.paginate(emptyList(), 58))
        assertEquals(0, SystemPrintLayout.pageCount(listOf("", "  "), 80))
    }

    @Test
    fun `halaman dibagi sesuai kapasitas 58 dan 80 mm`() {
        val lines = (1..60).map { "Baris $it" }
        val pages58 = SystemPrintLayout.paginate(lines, 58)
        val pages80 = SystemPrintLayout.paginate(lines, 80)

        assertEquals(SystemPrintLayout.linesPerPage(58), pages58[0].size)
        assertEquals(SystemPrintLayout.linesPerPage(80), pages80[0].size)
        assertEquals(60, pages58.sumOf { it.size })
        assertEquals(60, pages80.sumOf { it.size })
        assertEquals("Baris 1", pages58[0].first())
        assertEquals("Baris 60", pages58.last().last())
        assertTrue(pages58.size >= pages80.size)
    }

    @Test
    fun `kapasitas halaman selalu positif`() {
        assertTrue(SystemPrintLayout.linesPerPage(58) > 0)
        assertTrue(SystemPrintLayout.linesPerPage(80) > 0)
        assertTrue(SystemPrintLayout.pageHeightPt() > 0)
        assertTrue(SystemPrintLayout.pageWidthPt(58) < SystemPrintLayout.pageWidthPt(80))
    }
}
