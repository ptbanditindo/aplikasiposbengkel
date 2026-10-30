package com.bengkelpos.radiator.printer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EscPosTestTicketTest {

    private fun ByteArray.indexOf(bytes: ByteArray): Int {
        if (bytes.isEmpty()) return -1
        for (start in 0..(size - bytes.size)) {
            var match = true
            for (offset in bytes.indices) {
                if (this[start + offset] != bytes[offset]) {
                    match = false
                    break
                }
            }
            if (match) return start
        }
        return -1
    }

    @Test
    fun `struk tes 58mm memakai pemisah 32 kolom`() {
        val ticket = EscPosTestTicket.build(paperWidth = 58, timestamp = "30-10-2026 10:00")
        val text = String(ticket, Charsets.US_ASCII)

        assertTrue(ticket.size > 4)
        assertEquals(0x1B, ticket[0].toInt() and 0xFF)
        assertEquals(0x40, ticket[1].toInt() and 0xFF)
        assertTrue(text.contains("BENGKELPOS RADIATOR"))
        assertTrue(text.contains("-".repeat(32)))
        assertTrue(text.contains("30-10-2026 10:00"))
        assertTrue(
            ticket.indexOf(byteArrayOf(0x1D, 0x56, 0x42, 0x00)) > 0,
        )
    }

    @Test
    fun `struk tes 80mm memakai pemisah 48 kolom`() {
        val ticket = EscPosTestTicket.build(paperWidth = 80, timestamp = "01-01-2027 09:30")
        val text = String(ticket, Charsets.US_ASCII)
        assertTrue(text.contains("-".repeat(48)))
    }

    @Test
    fun `label koneksi USB tampil pada struk tes`() {
        val ticket = EscPosTestTicket.build(
            paperWidth = 58,
            timestamp = "31-10-2026 08:00",
            connectionLabel = "USB OTG",
        )
        val text = String(ticket, Charsets.US_ASCII)
        assertTrue(text.contains("Tes Printer USB OTG"))
    }

    @Test
    fun `lebar tidak dikenal memakai 58mm`() {
        val ticket = EscPosTestTicket.build(paperWidth = 72, timestamp = "01-01-2027 09:30")
        val text = String(ticket, Charsets.US_ASCII)
        assertTrue(text.contains("-".repeat(32)))
    }

    @Test
    fun `label koneksi jaringan tampil pada struk tes`() {
        val ticket = EscPosTestTicket.build(
            paperWidth = 58,
            timestamp = "31-10-2026 08:00",
            connectionLabel = "Wi-Fi/LAN",
        )
        assertTrue(
            String(ticket, Charsets.US_ASCII).contains("Tes Printer Wi-Fi/LAN"),
        )
    }

    @Test
    fun `label koneksi default tetap Bluetooth`() {
        val ticket = EscPosTestTicket.build(
            paperWidth = 58,
            timestamp = "31-10-2026 08:00",
        )
        assertTrue(
            String(ticket, Charsets.US_ASCII).contains("Tes Printer Bluetooth"),
        )
    }

    @Test
    fun `baris teks backend dirender tanpa mengubah isi`() {
        val lines = listOf(
            "BENGKEL RADIATOR",
            "Total: Rp 150.000",
            "",
            "Terima kasih",
        )
        val rendered = EscPosTextRenderer.render(
            lines = lines,
            charsetName = "US-ASCII",
        )
        val text = String(rendered, Charsets.US_ASCII)

        assertEquals(0x1B, rendered[0].toInt() and 0xFF)
        assertTrue(text.contains("Total: Rp 150.000"))
        assertTrue(text.contains("Terima kasih"))
        assertTrue(
            rendered.indexOf(byteArrayOf(0x1D, 0x56, 0x42, 0x00)) > 0,
        )
    }

    @Test
    fun `karakter kontrol dihapus dari baris cetak`() {
        val rendered = EscPosTextRenderer.render(
            lines = listOf("A\u0000B\u001FC"),
            charsetName = "US-ASCII",
        )
        val text = String(rendered, Charsets.US_ASCII)
        assertTrue(text.contains("A B C"))
    }

    @Test
    fun `charset tidak dikenal kembali ke ASCII`() {
        val rendered = EscPosTextRenderer.render(
            lines = listOf("Total 100"),
            charsetName = "charset-tidak-ada",
        )
        assertTrue(String(rendered, Charsets.US_ASCII).contains("Total 100"))
    }
}
