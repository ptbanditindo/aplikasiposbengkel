package com.bengkelpos.radiator.nativebridge

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Base64
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.core.content.FileProvider
import com.bengkelpos.radiator.backend.BackendManager
import com.bengkelpos.radiator.backup.BackupScheduler
import com.bengkelpos.radiator.backup.BackupStore
import com.bengkelpos.radiator.printer.BluetoothPermissionPolicy
import com.bengkelpos.radiator.printer.BluetoothPrinterController
import com.bengkelpos.radiator.printer.EscPosTextRenderer
import com.bengkelpos.radiator.printer.NetworkPrinterController
import com.bengkelpos.radiator.printer.PrinterErrorCode
import com.bengkelpos.radiator.printer.PrinterException
import com.bengkelpos.radiator.printer.SystemPrintController
import com.bengkelpos.radiator.printer.UsbPrinterController
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

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
    private val printerController: BluetoothPrinterController,
    private val networkPrinterController: NetworkPrinterController,
    private val usbPrinterController: UsbPrinterController,
    private val systemPrintController: SystemPrintController,
    private val requestBluetoothPermissions: (
        permissions: List<String>,
        callback: (Boolean) -> Unit,
    ) -> Unit,
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
                    "scheduledBackupStatus" -> scheduledBackupStatus(requestId)
                    "printerDiscover" -> printerDiscover(requestId)
                    "printerConnect" -> printerConnect(requestId, args)
                    "printerDisconnect" -> printerDisconnect(requestId)
                    "printerStatus" -> printerStatus(requestId)
                    "printerPrint" -> printerPrint(requestId, args)
                    "printerTestPrint" -> printerTestPrint(requestId, args)
                    "networkDiscover" -> networkDiscover(requestId)
                    "networkConnect" -> networkConnect(requestId, args)
                    "networkDisconnect" -> networkDisconnect(requestId)
                    "networkStatus" -> networkStatus(requestId)
                    "networkPrint" -> networkPrint(requestId, args)
                    "networkTestPrint" -> networkTestPrint(requestId, args)
                    "usbDiscover" -> usbDiscover(requestId)
                    "usbConnect" -> usbConnect(requestId, args)
                    "usbDisconnect" -> usbDisconnect(requestId)
                    "usbStatus" -> usbStatus(requestId)
                    "usbPrint" -> usbPrint(requestId, args)
                    "usbTestPrint" -> usbTestPrint(requestId, args)
                    "systemPrint" -> systemPrint(requestId, args)
                    "systemTestPrint" -> systemTestPrint(requestId, args)
                    "systemPrintStatus" -> systemPrintStatus(requestId, args)
                    "systemPrintCancel" -> systemPrintCancel(requestId, args)
                    else -> fail(requestId, "UNKNOWN", "Perintah tidak dikenal.")
                }
            } catch (error: BridgeError) {
                fail(requestId, error.code, error.message ?: "Perintah gagal.")
            } catch (error: PrinterException) {
                fail(requestId, error.code, error.message ?: "Perintah printer gagal.")
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
                throw BridgeError(
                    "HTTP",
                    "Backup gagal dibuat. Coba lagi.",
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
                "Tidak dapat menghubungi aplikasi. Coba lagi.",
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
                "Aplikasi gagal dijalankan ulang. Tutup lalu buka aplikasi.",
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

    private fun scheduledBackupStatus(requestId: String) {
        val status = BackupScheduler.status(activity.applicationContext)
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("last_attempt_at", status.lastAttemptAt ?: JSONObject.NULL)
                .put("last_success_at", status.lastSuccessAt ?: JSONObject.NULL)
                .put("last_status", status.lastStatus ?: JSONObject.NULL)
                .put("last_message", status.lastMessage ?: JSONObject.NULL),
        )
    }

    private fun printerDiscover(requestId: String) {
        ensurePrinterPermissions(discovery = true)
        val devices = JSONArray()
        printerController.discover().forEach { device ->
            devices.put(
                JSONObject()
                    .put("name", device.name)
                    .put("address", device.address)
                    .put("paired", device.paired),
            )
        }
        reply(requestId, JSONObject().put("ok", true).put("devices", devices))
    }

    private fun printerConnect(requestId: String, args: JSONObject) {
        ensurePrinterPermissions(discovery = false)
        val device = printerController.connect(args.optString("address", "").trim())
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("connected", true)
                .put("name", device.name)
                .put("address", device.address),
        )
    }

    private fun printerDisconnect(requestId: String) {
        printerController.disconnect()
        reply(requestId, JSONObject().put("ok", true).put("connected", false))
    }

    private fun printerStatus(requestId: String) {
        val status = printerController.status()
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("supported", status.supported)
                .put("permissions_granted", status.permissionsGranted)
                .put("enabled", status.enabled)
                .put("connected", status.connected)
                .put("address", status.address ?: JSONObject.NULL)
                .put("name", status.name ?: JSONObject.NULL)
                .put("message", status.message ?: JSONObject.NULL),
        )
    }

    private fun printerPrint(requestId: String, args: JSONObject) {
        ensurePrinterPermissions(discovery = false)
        val bytes = printPayload(args)
        printerController.print(bytes)
        reply(requestId, JSONObject().put("ok", true).put("bytes", bytes.size))
    }

    private fun printerTestPrint(requestId: String, args: JSONObject) {
        ensurePrinterPermissions(discovery = false)
        printerController.testPrint(args.optInt("paperWidth", 58))
        reply(requestId, JSONObject().put("ok", true))
    }

    private fun networkDiscover(requestId: String) {
        val devices = JSONArray()
        networkPrinterController.discover().forEach { device ->
            devices.put(
                JSONObject()
                    .put("name", device.name)
                    .put("ip", device.ip)
                    .put("port", device.port),
            )
        }
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("discovery_supported", networkPrinterController.isDiscoverySupported())
                .put("devices", devices),
        )
    }

    private fun networkConnect(requestId: String, args: JSONObject) {
        val endpoint = networkPrinterController.connect(
            ip = args.optString("ip", "").trim(),
            port = if (args.has("port")) args.optInt("port") else 0,
        )
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("connected", true)
                .put("ip", endpoint.ip)
                .put("port", endpoint.port),
        )
    }

    private fun networkDisconnect(requestId: String) {
        networkPrinterController.disconnect()
        reply(requestId, JSONObject().put("ok", true).put("connected", false))
    }

    private fun networkStatus(requestId: String) {
        val status = networkPrinterController.status()
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("connected", status.connected)
                .put("ip", status.ip ?: JSONObject.NULL)
                .put("port", status.port ?: JSONObject.NULL)
                .put("message", status.message ?: JSONObject.NULL)
                .put("discovery_supported", status.discoverySupported),
        )
    }

    private fun networkPrint(requestId: String, args: JSONObject) {
        val bytes = printPayload(args)
        networkPrinterController.print(bytes, optionalIp(args), optionalPort(args))
        reply(requestId, JSONObject().put("ok", true).put("bytes", bytes.size))
    }

    private fun networkTestPrint(requestId: String, args: JSONObject) {
        networkPrinterController.testPrint(
            paperWidth = args.optInt("paperWidth", 58),
            ip = optionalIp(args),
            port = optionalPort(args),
        )
        reply(requestId, JSONObject().put("ok", true))
    }

    private fun usbDiscover(requestId: String) {
        val devices = JSONArray()
        usbPrinterController.discover().forEach { device ->
            val interfaces = JSONArray()
            device.interfaces.forEach { iface ->
                val endpoints = JSONArray()
                iface.endpoints.forEach { endpoint ->
                    endpoints.put(
                        JSONObject()
                            .put("address", endpoint.address)
                            .put("direction", endpoint.direction.name)
                            .put("type", endpoint.type.name)
                            .put("max_packet_size", endpoint.maxPacketSize),
                    )
                }
                interfaces.put(
                    JSONObject()
                        .put("index", iface.index)
                        .put("class", iface.interfaceClass)
                        .put("subclass", iface.interfaceSubclass)
                        .put("protocol", iface.interfaceProtocol)
                        .put("endpoints", endpoints),
                )
            }
            devices.put(
                JSONObject()
                    .put("identity", device.identity)
                    .put("name", device.name)
                    .put("vendor_id", device.vendorId)
                    .put("product_id", device.productId)
                    .put("supported", device.supported)
                    .put("requires_permission", device.requiresPermission)
                    .put("interfaces", interfaces),
            )
        }
        reply(requestId, JSONObject().put("ok", true).put("devices", devices))
    }

    private fun usbConnect(requestId: String, args: JSONObject) {
        val device = usbPrinterController.connect(usbIdentity(args))
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("connected", true)
                .put("identity", device.identity)
                .put("name", device.name),
        )
    }

    private fun usbDisconnect(requestId: String) {
        usbPrinterController.disconnect()
        reply(requestId, JSONObject().put("ok", true).put("connected", false))
    }

    private fun usbStatus(requestId: String) {
        val status = usbPrinterController.status()
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("supported", status.supported)
                .put("connected", status.connected)
                .put("identity", status.identity ?: JSONObject.NULL)
                .put("name", status.name ?: JSONObject.NULL)
                .put("message", status.message ?: JSONObject.NULL),
        )
    }

    private fun usbPrint(requestId: String, args: JSONObject) {
        val bytes = printPayload(args)
        usbPrinterController.print(bytes, optionalUsbIdentity(args))
        reply(requestId, JSONObject().put("ok", true).put("bytes", bytes.size))
    }

    private fun usbTestPrint(requestId: String, args: JSONObject) {
        usbPrinterController.testPrint(
            paperWidth = args.optInt("paperWidth", 58),
            identity = optionalUsbIdentity(args),
        )
        reply(requestId, JSONObject().put("ok", true))
    }

    private fun usbIdentity(args: JSONObject): String =
        args.optString("identity", "").trim().ifEmpty {
            args.optString("address", "").trim()
        }

    private fun systemPrint(requestId: String, args: JSONObject) {
        val result = systemPrintController.submit(
            title = args.optString("title", "").trim(),
            lines = textLines(args),
            paperWidth = args.optInt("paperWidth", 58),
        )
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("job_id", result.jobId)
                .put("title", result.title)
                .put("paper_width", result.paperWidth)
                .put("pages", result.pages)
                .put("lines", result.lines)
                .put("state", systemPrintController.status(result.jobId).state),
        )
    }

    private fun systemTestPrint(requestId: String, args: JSONObject) {
        val result = systemPrintController.testPrint(args.optInt("paperWidth", 58))
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("job_id", result.jobId)
                .put("paper_width", result.paperWidth)
                .put("pages", result.pages),
        )
    }

    private fun systemPrintStatus(requestId: String, args: JSONObject) {
        val jobId = if (args.has("job_id")) args.optInt("job_id") else null
        val status = systemPrintController.status(jobId)
        reply(
            requestId,
            JSONObject()
                .put("ok", true)
                .put("supported", status.supported)
                .put("job_id", status.jobId ?: JSONObject.NULL)
                .put("state", status.state)
                .put("message", status.message ?: JSONObject.NULL),
        )
    }

    private fun systemPrintCancel(requestId: String, args: JSONObject) {
        val cancelled = systemPrintController.cancel(args.optInt("job_id", 0))
        reply(requestId, JSONObject().put("ok", true).put("cancelled", cancelled))
    }

    private fun textLines(args: JSONObject): List<String> {
        val lines = args.optJSONArray("lines")
            ?: throw BridgeError(
                PrinterErrorCode.INVALID_PAYLOAD,
                "Data baris struk tidak tersedia untuk Android Print.",
            )
        if (lines.length() == 0) {
            throw BridgeError(
                PrinterErrorCode.INVALID_PAYLOAD,
                "Data baris struk kosong.",
            )
        }
        val collected = ArrayList<String>(lines.length())
        for (index in 0 until lines.length()) {
            collected.add(lines.optString(index, ""))
        }
        return collected
    }

    private fun optionalUsbIdentity(args: JSONObject): String? =
        usbIdentity(args).ifEmpty { null }

    private fun printPayload(args: JSONObject): ByteArray {
        val base64 = args.optString("base64", "").trim()
        return if (base64.isNotEmpty()) {
            decodePrintPayload(base64)
        } else {
            renderTextPayload(args)
        }
    }

    private fun optionalIp(args: JSONObject): String? =
        args.optString("ip", "").trim().ifEmpty { null }

    private fun optionalPort(args: JSONObject): Int? =
        if (args.has("port")) args.optInt("port") else null

    private fun decodePrintPayload(base64: String): ByteArray = try {
        Base64.decode(base64, Base64.DEFAULT)
    } catch (error: IllegalArgumentException) {
        throw BridgeError(
            PrinterErrorCode.INVALID_PAYLOAD,
            "Data struk ESC/POS tidak dapat dibaca.",
        )
    }

    private fun renderTextPayload(args: JSONObject): ByteArray {
        val lines = args.optJSONArray("lines")
            ?: throw BridgeError(
                PrinterErrorCode.INVALID_PAYLOAD,
                "Data cetak tidak berisi struk ESC/POS atau baris teks.",
            )
        if (lines.length() == 0) {
            throw BridgeError(
                PrinterErrorCode.INVALID_PAYLOAD,
                "Data baris struk kosong.",
            )
        }
        val collected = ArrayList<String>(lines.length())
        for (index in 0 until lines.length()) {
            collected.add(lines.optString(index, ""))
        }
        return EscPosTextRenderer.render(
            lines = collected,
            charsetName = args.optString("encoding", "").ifBlank { null },
        )
    }

    private fun ensurePrinterPermissions(discovery: Boolean) {
        val missing = printerController.missingPermissions(discovery)
        if (missing.isEmpty()) return
        val granted = AtomicBoolean(false)
        val answered = CountDownLatch(1)
        activity.runOnUiThread {
            requestBluetoothPermissions(missing) { allowed ->
                granted.set(allowed)
                answered.countDown()
            }
        }
        val completed = try {
            answered.await(PERMISSION_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        } catch (error: InterruptedException) {
            Thread.currentThread().interrupt()
            false
        }
        if (!completed || !granted.get()) {
            throw BridgeError(
                PrinterErrorCode.PERMISSION_DENIED,
                BluetoothPermissionPolicy.denialMessage(discovery),
            )
        }
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
        private const val PERMISSION_TIMEOUT_MS = 60_000L
        private val BACKUP_NAME = Regex("bengkel_radiator_[0-9_]+\\.db")
    }
}
