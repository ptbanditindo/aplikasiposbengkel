package com.bengkelpos.radiator.printer

import java.io.ByteArrayOutputStream
import java.nio.charset.Charset

/**
 * Merender baris struk yang sudah diformat backend menjadi byte ESC/POS.
 *
 * Baris diterima apa adanya dari backend; modul ini tidak menghitung ulang
 * harga, diskon, atau total. Gunakan jalur base64 bila struk sudah berupa byte
 * ESC/POS lengkap.
 */
object EscPosTextRenderer {

    private val INIT = byteArrayOf(0x1B, 0x40)
    private val FEED_AND_CUT = byteArrayOf(0x0A, 0x0A, 0x0A, 0x1D, 0x56, 0x42, 0x00)
    private val CONTROL_CHARS = Regex("[\\x00-\\x1F\\x7F]")
    private val DEFAULT_CHARSET = Charsets.US_ASCII

    fun render(
        lines: List<String>,
        charsetName: String?,
    ): ByteArray {
        val charset = resolveCharset(charsetName)
        val out = ByteArrayOutputStream()
        out.write(INIT)
        lines.forEach { line ->
            val clean = line.replace(CONTROL_CHARS, " ")
            out.write(clean.toByteArray(charset))
            out.write('\n'.code)
        }
        out.write(FEED_AND_CUT)
        return out.toByteArray()
    }

    private fun resolveCharset(name: String?): Charset {
        if (name.isNullOrBlank()) return DEFAULT_CHARSET
        return runCatching { Charset.forName(name) }.getOrDefault(DEFAULT_CHARSET)
    }
}
