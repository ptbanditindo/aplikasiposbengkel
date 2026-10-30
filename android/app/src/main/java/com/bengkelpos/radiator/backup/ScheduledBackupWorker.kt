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
        val token = runCatching {
            PinStore.open(applicationContext).getOrCreateAdminToken()
        }.getOrNull() ?: return@withContext Result.success()

        val startedHere = !BackendManager.isRunning()
        if (startedHere && !BackendManager.start(applicationContext, token)) {
            BackupScheduler.recordResult(
                applicationContext,
                "failed",
                "Server lokal gagal dijalankan.",
            )
            return@withContext Result.retry()
        }

        try {
            val body = requestScheduledBackup(token)
            val status = body.optString("status", "failed")
            val message = body.optString("message", "")
            BackupScheduler.recordResult(applicationContext, status, message)
            if (BackupPolicy.shouldRetry(status)) Result.retry() else Result.success()
        } catch (error: Exception) {
            BackupScheduler.recordResult(
                applicationContext,
                "failed",
                error.message ?: "Backup gagal.",
            )
            Result.retry()
        } finally {
            if (startedHere && !ForegroundState.isForeground) {
                runCatching { BackendManager.stop() }
            }
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
                    "Server backup lokal menolak permintaan (HTTP $code).",
                )
            }
            return JSONObject(text)
        } finally {
            connection.disconnect()
        }
    }
}
