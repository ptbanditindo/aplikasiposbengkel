package com.bengkelpos.radiator.backup

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.bengkelpos.radiator.ForegroundState
import com.bengkelpos.radiator.backend.BackendManager
import com.bengkelpos.radiator.pin.PinStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Worker harian: menyalakan backend bila perlu, memanggil endpoint backup
 * idempoten, lalu mematikan backend lagi bila worker yang menyalakannya.
 *
 * Ref: T-06 - endpoint backend yang menyimpan snapshot lokal lebih dulu,
 * memakai ulang file hari yang sama, dan mencatat status terakhir.
 */
class ScheduledBackupWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val token = try {
            PinStore.open(applicationContext).getOrCreateAdminToken()
        } catch (error: Exception) {
            // Perangkat bisa belum dibuka setelah reboot atau Keystore sementara
            // tidak tersedia; jangan pernah menganggap backup berhasil.
            return@withContext handleTokenFailure(error)
        }

        val startedHere = !BackendManager.isRunning()
        if (startedHere && !BackendManager.start(applicationContext, token)) {
            return@withContext recordFailure(
                "Aplikasi gagal dijalankan. Backup akan dicoba lagi.",
                BackupPolicy.backendFailureDecision(runAttemptCount),
            )
        }

        try {
            val body = requestScheduledBackup(token)
            val status = body.optString("status", "failed")
            val message = body.optString("message", "")
            BackupScheduler.recordResult(applicationContext, status, message)
            if (!BackupPolicy.shouldRetry(status)) return@withContext Result.success()
            if (runAttemptCount >= BackupPolicy.MAX_ATTEMPTS) {
                BackupScheduler.recordResult(
                    applicationContext,
                    "failed",
                    "Backup belum berhasil setelah beberapa percobaan. " +
                        message.ifBlank {
                            "Akan dicoba lagi pada jadwal berikutnya."
                        },
                )
                // Biarkan jadwal harian tetap hidup; backoff retry dihentikan.
                return@withContext Result.success()
            }
            Result.retry()
        } catch (error: Exception) {
            return@withContext recordFailure(
                "Backup lokal gagal dihubungi. Backup akan dicoba lagi.",
                BackupPolicy.backendFailureDecision(runAttemptCount),
            )
        } finally {
            if (startedHere && !ForegroundState.isForeground) {
                runCatching { BackendManager.stop() }
            }
        }
    }

    private fun handleTokenFailure(error: Throwable): Result {
        val decision = BackupPolicy.tokenFailureDecision(error, runAttemptCount)
        val message = if (decision == BackupPolicy.Decision.GIVE_UP) {
            "Kredensial perangkat tidak dapat dibaca. Buka aplikasi, atur ulang " +
                "PIN, lalu jalankan backup manual."
        } else {
            "Kredensial perangkat belum dapat dibaca (mis. perangkat baru " +
                "dibuka setelah restart). Backup akan dicoba lagi."
        }
        BackupScheduler.recordResult(applicationContext, "failed", message)
        return if (decision == BackupPolicy.Decision.RETRY) {
            Result.retry()
        } else {
            // Jangan mengulang tanpa batas, tetapi jadwal harian tetap ada.
            Result.success()
        }
    }

    private fun recordFailure(message: String, decision: BackupPolicy.Decision): Result {
        BackupScheduler.recordResult(applicationContext, "failed", message)
        return if (decision == BackupPolicy.Decision.RETRY) {
            Result.retry()
        } else {
            Result.success()
        }
    }

    private fun requestScheduledBackup(token: String): JSONObject {
        val connection = URL("${BackendManager.baseUrl}/api/admin/scheduled-backup")
            .openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 30_000
        connection.readTimeout = 120_000
        connection.doOutput = true
        connection.setFixedLengthStreamingMode(0)
        connection.setRequestProperty("X-Install-Token", token)
        try {
            val code = connection.responseCode
            val stream =
                if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                throw IllegalStateException(
                    "Backup otomatis gagal dijalankan.",
                )
            }
            return JSONObject(text)
        } finally {
            connection.disconnect()
        }
    }
}
