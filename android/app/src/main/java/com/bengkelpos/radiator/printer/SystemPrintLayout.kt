package com.bengkelpos.radiator.printer

import android.print.PrintAttributes
import kotlin.math.roundToInt

/**
 * Perhitungan tata letak struk untuk Android Print Framework.
 *
 * Semua angka murni (tanpa API Android) agar pagination dapat diuji di JVM.
 * Ukuran kertas 58/80 mm memakai tinggi gulungan 100 mm per halaman; layanan
 * cetak dapat mengganti ukuran tersebut sesuai kemampuannya.
 */
object SystemPrintLayout {

    const val MM_PER_INCH = 25.4f
    const val PT_PER_INCH = 72f
    const val MILS_PER_INCH = 1000f
    const val PAGE_HEIGHT_MM = 100f
    const val MARGIN_PT = 8f
    private const val MIN_PAPER_WIDTH = 58
    private const val WIDE_PAPER_WIDTH = 80

    fun normalizePaperWidth(value: Int): Int =
        if (value == WIDE_PAPER_WIDTH) WIDE_PAPER_WIDTH else MIN_PAPER_WIDTH

    fun columns(paperWidth: Int): Int =
        if (normalizePaperWidth(paperWidth) == WIDE_PAPER_WIDTH) 48 else 32

    fun textSizePt(paperWidth: Int): Float =
        if (normalizePaperWidth(paperWidth) == WIDE_PAPER_WIDTH) 9f else 8f

    fun lineHeightPt(paperWidth: Int): Float =
        if (normalizePaperWidth(paperWidth) == WIDE_PAPER_WIDTH) 11f else 10f

    fun pageWidthPt(paperWidth: Int): Int =
        (normalizePaperWidth(paperWidth) * PT_PER_INCH / MM_PER_INCH).roundToInt()

    fun pageHeightPt(): Int =
        (PAGE_HEIGHT_MM * PT_PER_INCH / MM_PER_INCH).roundToInt()

    fun linesPerPage(paperWidth: Int): Int {
        val usable = pageHeightPt() - (MARGIN_PT * 2)
        return (usable / lineHeightPt(paperWidth)).toInt().coerceAtLeast(1)
    }

    /** Menghapus karakter kontrol dan baris kosong di awal/akhir. */
    fun sanitize(lines: List<String>): List<String> {
        val clean = lines.map { line ->
            line.replace(CONTROL_CHARS, " ").trimEnd()
        }
        val start = clean.indexOfFirst { it.isNotBlank() }
        if (start < 0) return emptyList()
        val end = clean.indexOfLast { it.isNotBlank() }
        return clean.subList(start, end + 1).toList()
    }

    fun paginate(lines: List<String>, paperWidth: Int): List<List<String>> {
        val clean = sanitize(lines)
        if (clean.isEmpty()) return emptyList()
        return clean.chunked(linesPerPage(paperWidth))
    }

    fun pageCount(lines: List<String>, paperWidth: Int): Int =
        paginate(lines, paperWidth).size

    fun attributes(paperWidth: Int): PrintAttributes {
        val width = normalizePaperWidth(paperWidth)
        val media = PrintAttributes.MediaSize(
            "thermal_${width}mm",
            "Thermal ${width}mm",
            (width * MILS_PER_INCH / MM_PER_INCH).roundToInt(),
            (PAGE_HEIGHT_MM * MILS_PER_INCH / MM_PER_INCH).roundToInt(),
        )
        return PrintAttributes.Builder()
            .setMediaSize(media)
            .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
            .build()
    }

    private val CONTROL_CHARS = Regex("[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F\\x7F]")
}
