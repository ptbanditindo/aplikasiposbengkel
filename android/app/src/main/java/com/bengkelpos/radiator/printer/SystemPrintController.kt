package com.bengkelpos.radiator.printer

import android.app.Activity
import android.content.Context
import android.print.PrintJob
import android.print.PrintManager
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

data class SystemPrintResult(
    val jobId: Int,
    val title: String,
    val paperWidth: Int,
    val pages: Int,
    val lines: Int,
)

data class SystemPrintStatus(
    val supported: Boolean,
    val jobId: Int?,
    val state: String,
    val message: String?,
)

/**
 * Membungkus Android Print Framework untuk struk teks.
 *
 * Dialog pemilihan printer, pratinjau, dan pembatalan disediakan sistem
 * Android. Kelas ini hanya memastikan dokumen dibuat dan melaporkan status
 * pekerjaan apa adanya; membukanya tidak berarti printer berhasil mencetak.
 */
class SystemPrintController(private val activity: Activity) {

    private data class TrackedJob(val jobId: Int, val job: PrintJob)

    private val manager: PrintManager? =
        activity.getSystemService(Context.PRINT_SERVICE) as? PrintManager
    private val jobs = LinkedHashMap<Int, TrackedJob>()
    private var nextJobId = 0

    fun isSupported(): Boolean = manager != null

    fun submit(
        title: String,
        lines: List<String>,
        paperWidth: Int,
    ): SystemPrintResult {
        val printManager = manager
            ?: throw PrinterException(
                PrinterErrorCode.SYSTEM_PRINT_UNAVAILABLE,
                "Android Print tidak tersedia di perangkat ini. Gunakan printer " +
                    "Bluetooth, Wi-Fi/LAN, atau USB OTG.",
            )
        val clean = SystemPrintLayout.sanitize(lines)
        if (clean.isEmpty()) {
            throw PrinterException(
                PrinterErrorCode.INVALID_PAYLOAD,
                "Struk tidak memiliki teks untuk dicetak.",
            )
        }
        val width = SystemPrintLayout.normalizePaperWidth(paperWidth)
        val safeTitle = title.trim().take(MAX_TITLE_CHARS).ifEmpty { "Struk BengkelPOS" }
        val pages = SystemPrintLayout.pageCount(clean, width)

        val latch = CountDownLatch(1)
        val result = AtomicReference<SystemPrintResult?>()
        val failure = AtomicReference<Throwable?>()
        activity.runOnUiThread {
            try {
                val attributes = SystemPrintLayout.attributes(width)
                val adapter = ThermalPrintDocumentAdapter(
                    context = activity.applicationContext,
                    title = safeTitle,
                    lines = clean,
                    paperWidth = width,
                )
                val job = printManager.print(safeTitle, adapter, attributes)
                val jobId = synchronized(this) {
                    nextJobId += 1
                    jobs[nextJobId] = TrackedJob(nextJobId, job)
                    while (jobs.size > MAX_TRACKED_JOBS) {
                        val oldest = jobs.keys.first()
                        jobs.remove(oldest)
                    }
                    nextJobId
                }
                result.set(
                    SystemPrintResult(
                        jobId = jobId,
                        title = safeTitle,
                        paperWidth = width,
                        pages = pages,
                        lines = clean.size,
                    ),
                )
            } catch (error: Throwable) {
                failure.set(error)
            } finally {
                latch.countDown()
            }
        }

        val opened = try {
            latch.await(DIALOG_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        } catch (error: InterruptedException) {
            Thread.currentThread().interrupt()
            false
        }
        if (!opened) {
            throw PrinterException(
                PrinterErrorCode.TIMEOUT,
                "Dialog cetak Android tidak merespons. Coba lagi.",
            )
        }
        failure.get()?.let { error ->
            throw PrinterException(
                PrinterErrorCode.SYSTEM_PRINT_FAILED,
                "Dialog cetak Android gagal dibuka. Pastikan layanan cetak " +
                    "tersedia lalu coba lagi.",
                error,
            )
        }
        return result.get() ?: throw PrinterException(
            PrinterErrorCode.SYSTEM_PRINT_FAILED,
            "Pekerjaan cetak Android tidak dapat dibuat. Coba lagi.",
        )
    }

    /** Status pekerjaan terakhir bila [jobId] tidak diberikan. */
    fun status(jobId: Int? = null): SystemPrintStatus {
        if (manager == null) {
            return SystemPrintStatus(
                supported = false,
                jobId = jobId,
                state = "UNAVAILABLE",
                message = "Android Print tidak tersedia di perangkat ini.",
            )
        }
        val tracked = synchronized(this) {
            if (jobId != null) jobs[jobId] else jobs.values.lastOrNull()
        } ?: return SystemPrintStatus(
            supported = true,
            jobId = null,
            state = "IDLE",
            message = "Belum ada pekerjaan cetak Android.",
        )
        val state = when {
            tracked.job.isCancelled -> "CANCELLED"
            tracked.job.isFailed -> "FAILED"
            tracked.job.isCompleted -> "COMPLETED"
            tracked.job.isStarted -> "PRINTING"
            tracked.job.isBlocked -> "BLOCKED"
            tracked.job.isQueued -> "QUEUED"
            else -> "UNKNOWN"
        }
        val message = when (state) {
            "CANCELLED" -> "Pekerjaan cetak dibatalkan dari dialog Android."
            "FAILED" -> "Layanan cetak melaporkan pekerjaan gagal."
            "COMPLETED" -> "Layanan cetak melaporkan pekerjaan selesai."
            "PRINTING" -> "Dokumen sedang dikirim ke layanan cetak."
            "BLOCKED" -> "Pekerjaan cetak tertahan. Periksa printer di dialog Android."
            "QUEUED" -> "Dokumen menunggu diproses layanan cetak."
            else -> "Status pekerjaan cetak belum tersedia."
        }
        return SystemPrintStatus(
            supported = true,
            jobId = tracked.jobId,
            state = state,
            message = message,
        )
    }

    fun cancel(jobId: Int): Boolean = synchronized(this) {
        val tracked = jobs[jobId] ?: return false
        runCatching { tracked.job.cancel() }.isSuccess
    }

    fun testPrint(paperWidth: Int): SystemPrintResult {
        val width = SystemPrintLayout.normalizePaperWidth(paperWidth)
        val timestamp = LocalDateTime.now().format(TEST_TICKET_TIME)
        val separator = "-".repeat(SystemPrintLayout.columns(width))
        return submit(
            title = "Tes Printer Android",
            lines = listOf(
                "BENGKELPOS RADIATOR",
                "Tes Printer Android System",
                separator,
                "Waktu: $timestamp",
                "Printer siap digunakan.",
                separator,
            ),
            paperWidth = width,
        )
    }

    companion object {
        private const val DIALOG_TIMEOUT_MS = 15_000L
        private const val MAX_TITLE_CHARS = 80
        private const val MAX_TRACKED_JOBS = 10
        private val TEST_TICKET_TIME = DateTimeFormatter.ofPattern("dd-MM-yyyy HH:mm")
    }
}
