package com.bengkelpos.radiator.printer

import java.io.ByteArrayOutputStream

/**
 * Struk tes dasar ESC/POS untuk memastikan printer menerima perintah.
 *
 * Isi struk hanya teks tetap dan waktu perangkat, bukan data transaksi atau
 * perhitungan uang.
 */
object EscPosTestTicket {

    private val INIT = byteArrayOf(0x1B, 0x40)
    private val ALIGN_CENTER = byteArrayOf(0x1B, 0x61, 0x01)
    private val ALIGN_LEFT = byteArrayOf(0x1B, 0x61, 0x00)
    private val BOLD_ON = byteArrayOf(0x1B, 0x45, 0x01)
    private val BOLD_OFF = byteArrayOf(0x1B, 0x45, 0x00)
    private val DOUBLE_ON = byteArrayOf(0x1D, 0x21, 0x11)
    private val DOUBLE_OFF = byteArrayOf(0x1D, 0x21, 0x00)
    private val FEED = byteArrayOf(0x1B, 0x64, 0x03)
    private val PARTIAL_CUT = byteArrayOf(0x1D, 0x56, 0x42, 0x00)

    fun build(
        paperWidth: Int,
        timestamp: String,
        connectionLabel: String = "Bluetooth",
    ): ByteArray {
        val columns = if (paperWidth == 80) 48 else 32
        val label = connectionLabel
            .replace(Regex("[\\x00-\\x1F\\x7F]"), " ")
            .take(32)
        val out = ByteArrayOutputStream()
        out.write(INIT)
        out.write(ALIGN_CENTER)
        out.write(BOLD_ON)
        out.write(DOUBLE_ON)
        out.write("BENGKELPOS RADIATOR\n".ascii())
        out.write(DOUBLE_OFF)
        out.write(BOLD_OFF)
        out.write("Tes Printer $label\n".ascii())
        out.write(("-".repeat(columns) + "\n").ascii())
        out.write(("Waktu: $timestamp\n").ascii())
        out.write("Printer siap digunakan.\n".ascii())
        out.write(("-".repeat(columns) + "\n").ascii())
        out.write(ALIGN_LEFT)
        out.write(FEED)
        // Printer tanpa pemotong mengabaikan perintah ini.
        out.write(PARTIAL_CUT)
        return out.toByteArray()
    }

    private fun String.ascii(): ByteArray = toByteArray(Charsets.US_ASCII)
}
