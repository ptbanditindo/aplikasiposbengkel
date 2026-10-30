package com.bengkelpos.radiator.printer

import android.content.Context
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.PageRange
import android.print.PrintAttributes
import android.print.PrintDocumentAdapter
import android.print.PrintDocumentInfo
import android.print.pdf.PrintedPdfDocument
import java.io.FileOutputStream
import java.io.IOException

/**
 * Membuat dokumen PDF struk untuk dialog Android Print.
 *
 * Teks digambar apa adanya dari baris backend; tidak ada perhitungan uang di
 * sini. Pembatalan dari dialog Android diteruskan melalui [CancellationSignal].
 */
class ThermalPrintDocumentAdapter(
    private val context: Context,
    private val title: String,
    lines: List<String>,
    private val paperWidth: Int,
) : PrintDocumentAdapter() {

    private val pages = SystemPrintLayout.paginate(lines, paperWidth)

    override fun onLayout(
        oldAttributes: PrintAttributes?,
        newAttributes: PrintAttributes?,
        cancellationSignal: CancellationSignal?,
        callback: LayoutResultCallback,
        extras: Bundle?,
    ) {
        if (cancellationSignal?.isCanceled == true) {
            callback.onLayoutCancelled()
            return
        }
        if (pages.isEmpty()) {
            callback.onLayoutFailed("Data struk kosong.")
            return
        }
        val info = PrintDocumentInfo.Builder(title)
            .setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT)
            .setPageCount(pages.size)
            .build()
        callback.onLayoutFinished(info, true)
    }

    override fun onWrite(
        pages: Array<out PageRange>?,
        destination: ParcelFileDescriptor,
        cancellationSignal: CancellationSignal?,
        callback: WriteResultCallback,
    ) {
        val document = PrintedPdfDocument(context, SystemPrintLayout.attributes(paperWidth))
        try {
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.BLACK
                typeface = Typeface.MONOSPACE
                textSize = SystemPrintLayout.textSizePt(paperWidth)
            }
            val lineHeight = SystemPrintLayout.lineHeightPt(paperWidth)
            var drawn = 0
            for ((index, pageLines) in this.pages.withIndex()) {
                if (cancellationSignal?.isCanceled == true) {
                    callback.onWriteCancelled()
                    return
                }
                if (!covers(pages, index)) continue
                val page = document.startPage(index + 1)
                page.canvas.drawColor(Color.WHITE)
                var y = SystemPrintLayout.MARGIN_PT + paint.textSize
                pageLines.forEach { line ->
                    page.canvas.drawText(
                        line,
                        SystemPrintLayout.MARGIN_PT,
                        y,
                        paint,
                    )
                    y += lineHeight
                }
                document.finishPage(page)
                drawn += 1
            }
            if (drawn == 0) {
                callback.onWriteFailed("Tidak ada halaman struk yang diminta.")
                return
            }
            FileOutputStream(destination.fileDescriptor).use { output ->
                document.writeTo(output)
            }
            callback.onWriteFinished(arrayOf(PageRange.ALL_PAGES))
        } catch (error: IOException) {
            callback.onWriteFailed("Gagal menyiapkan dokumen struk untuk dicetak.")
        } catch (error: Throwable) {
            callback.onWriteFailed("Dokumen struk gagal dibuat.")
        } finally {
            document.close()
        }
    }

    private fun covers(ranges: Array<out PageRange>?, pageIndex: Int): Boolean {
        if (ranges == null || ranges.isEmpty()) return true
        if (ranges.any { it == PageRange.ALL_PAGES }) return true
        return ranges.any { pageIndex >= it.start && pageIndex <= it.end }
    }
}
