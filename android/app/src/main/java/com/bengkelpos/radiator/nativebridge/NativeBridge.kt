package com.bengkelpos.radiator.nativebridge

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.core.content.FileProvider
import com.bengkelpos.radiator.backend.BackendManager
import com.bengkelpos.radiator.backup.BackupScheduler
import com.bengkelpos.radiator.backup.BackupStore
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.ExecutorService

/**
 * Jembatan async antara halaman WebView dan kode native.
 *
 * Ref: T-03 - semua pekerjaan lambat berjalan di executor; JS menerima hasil
 * lewat `window.__nativeResult(requestId, json)` sehingga tidak ada callback
 * yang tersebar di app.js.
 */
class NativeBridge(
    private val activity: Activity,
    private val webView: WebView,
    private val adminToken: String,
    private val ioExecutor: ExecutorService,
    private val requestLegacyStoragePermission: (callback: (Boolean) -> Unit) -> Unit,
    private val onBackendRestarted: () -> Unit,
) {

    @JavascriptInterface
    fun call(requestId: String, method: String, argsJson: String) {
        val args = runCatching { JSONObject(argsJson.ifBlank { "{}" }) }
            .getOrElse { JSONObject() }
        ioExecutor.execute {
            try {
                when (method) {
                    "saveBackup" -> saveBackup(requestId)
                    "shareBackup" -> shareBackup(requestId, args)
                    "restartBackend" -> restartBackend(requestId)
                    "syncScheduledBackup" -> syncScheduledBackup(requestId, args)
                    else -> fail(requestId, "UNKNOWN", "Perintah tidak dikenal.")
                }
            } catch (error: BridgeError) {
                fail(requestId, error.code, error.message ?: "Perintah gagal.")
            } catch (error: Throwable) {
                Log.e(TAG, "Perintah native '$method' gagal", error)
                fail(requestId, "INTERNAL", "Terjadi kesalahan di perangkat. Coba lagi.")
            }
        }
    }

    private fun saveBackup(requestId: String) {
        val needsPermission = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q &&
            activity.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) !=
            PackageManager.PERMISSION_GRANTED
        if (!needsPermission) {
            runSave(requestId)
            return
        }
        requestLegacyStoragePermission { granted ->
            if (granted) {
                ioExecutor.execute { runSaveSafely(requestId) }
            } else {
                fail(
                    requestId,
                    "PERMISSION",
                    "Izin penyimpanan ditolak. Backup tidak disimpan.",
                )
            }
        }
    }

    private fun runSaveSafely(requestId: String) {
        try {
            runSave(requestId)
        } catch (error: BridgeError) {
            fail(requestId, error.code, error.message ?: "Backup gagal.")
        } catch (error: Throwable) {
            Log.e(TAG, "Backup gagal", error)
            fail(requestId, "INTERNAL", "Backup gagal disimpan. Coba lagi.")
        }
    }

    private fun runSave(requestId: String) {
        val bytes = fetchBackup()
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val displayName = "bengkel_radiator_$stamp.db"
        val saved = BackupStore.save(activity, bytes, displayName)
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("filename", saved.displayName)
                .put("location", saved.location),
        )
    }

    private fun fetchBackup(): ByteArray {
        val connection = URL("${BackendManager.baseUrl}/api/admin/backup")
            .openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 15_000
        connection.readTimeout = 60_000
        connection.doOutput = false
        connection.setRequestProperty("X-Install-Token", adminToken)
        try {
            val status = connection.responseCode
            if (status == HttpURLConnection.HTTP_UNAUTHORIZED) {
                throw BridgeError(
                    "AUTH",
                    "Sesi aplikasi tidak valid. Tutup lalu buka kembali aplikasi.",
                )
            }
            if (status != HttpURLConnection.HTTP_OK) {
                val detail = connection.errorStream?.bufferedReader()?.use { it.readText() }
                    ?.take(MAX_ERROR_CHARS)
                    ?.trim()
                    .orEmpty()
                throw BridgeError(
                    "HTTP",
                    "Server gagal membuat backup (HTTP $status). $detail".trim(),
                )
            }
            val data = connection.inputStream.use { it.readBytes() }
            if (data.isEmpty()) {
                throw BridgeError("EMPTY", "File backup kosong. Coba lagi.")
            }
            return data
        } catch (error: IOException) {
            throw BridgeError(
                "NETWORK",
                "Tidak dapat menghubungi server lokal. Coba lagi.",
            )
        } finally {
            connection.disconnect()
        }
    }

    private fun shareBackup(requestId: String, args: JSONObject) {
        val displayName = args.optString("filename", "")
        if (!BACKUP_NAME.matches(displayName)) {
            throw BridgeError("INVALID", "Nama file backup tidak valid.")
        }
        val file = File(File(activity.cacheDir, SHARE_DIR), displayName)
        if (!file.isFile || file.length() <= 0L) {
            throw BridgeError(
                "MISSING",
                "File backup belum tersedia. Unduh backup terlebih dahulu.",
            )
        }
        val uri = FileProvider.getUriForFile(
            activity,
            "${activity.packageName}.fileprovider",
            file,
        )
        activity.runOnUiThread {
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "application/octet-stream"
                putExtra(Intent.EXTRA_STREAM, uri)
                putExtra(Intent.EXTRA_SUBJECT, "Backup BengkelPOS Radiator")
                putExtra(
                    Intent.EXTRA_TEXT,
                    "File backup database BengkelPOS Radiator.",
                )
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            try {
                activity.startActivity(Intent.createChooser(intent, "Bagikan backup"))
                reply(requestId, JSONObject().put("ok", true))
            } catch (error: ActivityNotFoundException) {
                fail(
                    requestId,
                    "NO_APP",
                    "Tidak ada aplikasi untuk membagikan file. Pasang WhatsApp atau aplikasi lain.",
                )
            }
        }
    }

    private fun restartBackend(requestId: String) {
        val ready = runCatching {
            BackendManager.stop()
            BackendManager.start(activity.applicationContext, adminToken)
        }.getOrDefault(false)
        if (!ready) {
            fail(
                requestId,
                "BACKEND",
                "Server lokal gagal dijalankan ulang. Tutup lalu buka aplikasi.",
            )
            return
        }
        reply(requestId, JSONObject().put("ok", true))
        activity.runOnUiThread { onBackendRestarted() }
    }

    private fun syncScheduledBackup(requestId: String, args: JSONObject) {
        val enabled = args.optBoolean("enabled", false)
        BackupScheduler.sync(
            activity.applicationContext,
            enabled,
            args.optString("jam", "21:00"),
        )
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("scheduled", enabled),
        )
    }

    private fun reply(requestId: String, payload: JSONObject) {
        val script = "window.__nativeResult(${JSONObject.quote(requestId)}," +
            "${JSONObject.quote(payload.toString())});"
        webView.post { webView.evaluateJavascript(script, null) }
    }

    private fun fail(requestId: String, code: String, message: String) {
        reply(
            requestId,
            JSONObject()
                .put("ok", false)
                .put("code", code)
                .put("message", message),
        )
    }

    private class BridgeError(
        val code: String,
        message: String,
    ) : Exception(message)

    companion object {
        private const val TAG = "BengkelNative"
        private const val SHARE_DIR = "backup-share"
        private const val MAX_ERROR_CHARS = 200
        private val BACKUP_NAME = Regex("bengkel_radiator_[0-9_]+\\.db")
    }
}
