package com.bengkelpos.radiator

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.DownloadManager
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.URLUtil
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.bengkelpos.radiator.backend.BackendManager
import com.bengkelpos.radiator.backup.BackupFolder
import com.bengkelpos.radiator.backup.BackupFolderStore
import com.bengkelpos.radiator.nativebridge.NativeBridge
import com.bengkelpos.radiator.pin.PinActivity
import com.bengkelpos.radiator.pin.PinSession
import com.bengkelpos.radiator.pin.PinSettings
import com.bengkelpos.radiator.pin.PinStore
import com.bengkelpos.radiator.pin.SystemLockoutClock
import com.bengkelpos.radiator.printer.AndroidBluetoothGateway
import com.bengkelpos.radiator.printer.AndroidUsbPrinterGateway
import com.bengkelpos.radiator.printer.BluetoothPrinterController
import com.bengkelpos.radiator.printer.NetworkPrinterController
import com.bengkelpos.radiator.printer.NsdNetworkPrinterDiscovery
import com.bengkelpos.radiator.printer.SystemPrintController
import com.bengkelpos.radiator.printer.UsbPrinterController
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var offlinePanel: View
    private lateinit var offlineText: TextView
    private lateinit var offlineSpinner: ProgressBar
    private lateinit var retryButton: Button
    private lateinit var privacyCover: View
    private lateinit var pinSettings: PinSettings
    private lateinit var adminToken: String

    private var cachedStore: PinStore? = null
    private var pageLoaded = false
    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null
    private var activePort: Int = BackendManager.DEFAULT_PORT
    private var startingBackend = false
    private var registeredOrigin: String? = null
    private lateinit var nativeBridge: NativeBridge
    private lateinit var bluetoothPrinter: BluetoothPrinterController
    private lateinit var networkPrinter: NetworkPrinterController
    private lateinit var usbPrinter: UsbPrinterController
    private lateinit var systemPrinter: SystemPrintController
    private val nativeExecutor: ExecutorService = Executors.newFixedThreadPool(2)
    private var pendingStorageCallback: ((Boolean) -> Unit)? = null
    private var pendingBluetoothCallback: ((Boolean) -> Unit)? = null
    private var pendingBackupFolderCallback: ((BackupFolder?) -> Unit)? = null

    private val storagePermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        val callback = pendingStorageCallback
        pendingStorageCallback = null
        callback?.invoke(granted)
    }

    private val bluetoothPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result ->
        val callback = pendingBluetoothCallback
        pendingBluetoothCallback = null
        callback?.invoke(result.values.all { it })
    }

    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val callback = fileChooserCallback ?: return@registerForActivityResult
        fileChooserCallback = null
        if (result.resultCode != Activity.RESULT_OK) {
            callback.onReceiveValue(null)
            return@registerForActivityResult
        }
        val data = result.data
        val clipData = data?.clipData
        val uris: Array<Uri>? = when {
            clipData != null -> Array(clipData.itemCount) { clipData.getItemAt(it).uri }
            data?.data != null -> arrayOf(data.data!!)
            else -> null
        }
        callback.onReceiveValue(uris)
    }

    private val backupFolderLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val callback = pendingBackupFolderCallback ?: return@registerForActivityResult
        pendingBackupFolderCallback = null
        val uri = result.data?.data
        if (result.resultCode != Activity.RESULT_OK || uri == null) {
            callback(null)
            return@registerForActivityResult
        }
        val flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        val persisted = runCatching {
            contentResolver.takePersistableUriPermission(uri, flags)
        }.isSuccess
        if (!persisted) {
            Toast.makeText(
                this@MainActivity,
                "Folder tidak dapat diakses. Pilih folder lain.",
                Toast.LENGTH_LONG,
            ).show()
            callback(null)
            return@registerForActivityResult
        }
        val name = BackupFolderStore.displayName(this@MainActivity, uri) ?: "Folder backup"
        callback(BackupFolder(uri.toString(), name))
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        offlinePanel = findViewById(R.id.offlinePanel)
        offlineText = findViewById(R.id.offlineText)
        offlineSpinner = findViewById(R.id.offlineSpinner)
        retryButton = findViewById(R.id.retryButton)
        privacyCover = findViewById(R.id.privacyCover)
        configureWindowInsets()
        applyAppTheme(dark = false)
        pinSettings = PinSettings(this)
        adminToken = resolveAdminToken()
        bluetoothPrinter = BluetoothPrinterController(AndroidBluetoothGateway(this))
        networkPrinter = NetworkPrinterController(
            NsdNetworkPrinterDiscovery(applicationContext),
        )
        usbPrinter = UsbPrinterController(AndroidUsbPrinterGateway(this))
        systemPrinter = SystemPrintController(this)
        nativeBridge = NativeBridge(
            activity = this,
            webView = webView,
            adminToken = adminToken,
            ioExecutor = nativeExecutor,
            requestLegacyStoragePermission = ::requestStoragePermission,
            onBackendRestarted = ::restartBackendAfterRestore,
            printerController = bluetoothPrinter,
            networkPrinterController = networkPrinter,
            usbPrinterController = usbPrinter,
            systemPrintController = systemPrinter,
            requestBluetoothPermissions = ::requestBluetoothPermissions,
            requestBackupFolder = ::requestBackupFolder,
        )

        retryButton.setOnClickListener { startBackend() }

        configureWebView()
        startBackend()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
    }

    override fun onResume() {
        super.onResume()
        if (PinSession.requiresPin(
                SystemLockoutClock,
                pinSettings.idleTimeoutMs(),
                storeHasPin(),
            )
        ) {
            privacyCover.visibility = View.VISIBLE
            startActivity(Intent(this, PinActivity::class.java))
        } else {
            PinSession.markResumed(pinSettings)
            val contentReady = pageLoaded || offlinePanel.visibility == View.VISIBLE
            privacyCover.visibility = if (contentReady) View.GONE else View.VISIBLE
        }
    }

    override fun onStop() {
        super.onStop()
        // Cegah data transaksi terlihat sekilas saat aplikasi kembali dari latar belakang.
        privacyCover.visibility = View.VISIBLE
    }

    override fun onDestroy() {
        fileChooserCallback?.onReceiveValue(null)
        fileChooserCallback = null
        pendingStorageCallback = null
        pendingBluetoothCallback = null
        runCatching { bluetoothPrinter.close() }
        runCatching { networkPrinter.close() }
        runCatching { usbPrinter.close() }
        nativeExecutor.shutdownNow()
        webView.loadUrl("about:blank")
        webView.clearHistory()
        webView.removeAllViews()
        webView.destroy()
        super.onDestroy()
    }

    /**
     * targetSdk 35 menggambar konten sampai ke balik status bar. Padding root
     * memakai inset sistem agar header tidak tertutup dan halaman tetap utuh.
     */
    private fun configureWindowInsets() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val root = findViewById<View>(R.id.appRoot)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
    }

    private fun applyAppTheme(dark: Boolean) {
        val ground = Color.parseColor(if (dark) "#0D0D0E" else "#F7F7F7")
        val surface = Color.parseColor(if (dark) "#161618" else "#FFFFFF")
        val textColor = Color.parseColor(if (dark) "#F4F4F5" else "#0A0A0A")
        val accent = Color.parseColor(if (dark) "#6EA8FF" else "#1D5FBF")

        findViewById<View>(R.id.appRoot).setBackgroundColor(ground)
        findViewById<View>(R.id.privacyCover).setBackgroundColor(ground)
        findViewById<View>(R.id.offlinePanel).setBackgroundColor(surface)
        findViewById<TextView>(R.id.offlineText).setTextColor(textColor)
        findViewById<ProgressBar>(R.id.offlineSpinner).indeterminateTintList =
            ColorStateList.valueOf(accent)
        findViewById<Button>(R.id.retryButton).setTextColor(accent)

        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.isAppearanceLightStatusBars = !dark
        controller.isAppearanceLightNavigationBars = !dark
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            window.isStatusBarContrastEnforced = false
            window.isNavigationBarContrastEnforced = false
        }
    }

    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            allowFileAccessFromFileURLs = false
            allowUniversalAccessFromFileURLs = false
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
            mediaPlaybackRequiresUserGesture = true
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            cacheMode = WebSettings.LOAD_NO_CACHE
            builtInZoomControls = false
            displayZoomControls = false
            loadWithOverviewMode = true
            useWideViewPort = true
        }
        webView.addJavascriptInterface(PinBridge(), "BengkelPin")
        webView.addJavascriptInterface(nativeBridge, "BengkelNative")
        webView.setDownloadListener { url, _, contentDisposition, mimeType, _ ->
            handleDownload(url, contentDisposition, mimeType)
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest,
            ): Boolean {
                if (isLocalUrl(request.url)) return false
                Toast.makeText(this@MainActivity, R.string.external_link_blocked, Toast.LENGTH_SHORT)
                    .show()
                return true
            }

            override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                injectAdminToken()
            }

            override fun onPageFinished(view: WebView, url: String) {
                injectAdminToken()
                pageLoaded = true
                privacyCover.visibility = View.GONE
                offlineSpinner.visibility = View.GONE
                offlinePanel.visibility = View.GONE
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                if (request.isForMainFrame) {
                    showOfflineMessage(R.string.offline_hint)
                }
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView,
                filePathCallback: ValueCallback<Array<Uri>>,
                fileChooserParams: FileChooserParams,
            ): Boolean {
                this@MainActivity.fileChooserCallback?.onReceiveValue(null)
                this@MainActivity.fileChooserCallback = filePathCallback
                val intent = fileChooserParams.createIntent().apply {
                    type = "*/*"
                    addCategory(Intent.CATEGORY_OPENABLE)
                }
                return try {
                    fileChooserLauncher.launch(intent)
                    true
                } catch (error: ActivityNotFoundException) {
                    this@MainActivity.fileChooserCallback = null
                    false
                }
            }
        }
    }

    private fun startBackend() {
        if (startingBackend) return
        startingBackend = true
        showPreparing()
        val token = adminToken
        Thread {
            val ready = runCatching {
                BackendManager.start(applicationContext, token)
            }.getOrDefault(false)
            runOnUiThread {
                startingBackend = false
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (ready) {
                    activePort = BackendManager.activePort
                    loadApp()
                } else {
                    showBackendError()
                }
            }
        }.start()
    }

    private fun showPreparing() {
        pageLoaded = false
        privacyCover.visibility = View.GONE
        offlineText.visibility = View.GONE
        retryButton.visibility = View.GONE
        offlineSpinner.visibility = View.VISIBLE
        offlinePanel.visibility = View.VISIBLE
    }

    private fun showOfflineMessage(messageRes: Int) {
        pageLoaded = false
        privacyCover.visibility = View.GONE
        offlineSpinner.visibility = View.GONE
        offlineText.setText(messageRes)
        offlineText.visibility = View.VISIBLE
        retryButton.visibility = View.VISIBLE
        offlinePanel.visibility = View.VISIBLE
    }

    private fun showBackendError() {
        showOfflineMessage(R.string.backend_error_hint)
    }

    private fun restartBackendAfterRestore() {
        activePort = BackendManager.activePort
        pageLoaded = false
        loadApp()
    }

    private fun requestStoragePermission(callback: (Boolean) -> Unit) {
        runOnUiThread {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q ||
                checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) ==
                PackageManager.PERMISSION_GRANTED
            ) {
                callback(true)
                return@runOnUiThread
            }
            pendingStorageCallback = callback
            storagePermissionLauncher.launch(
                Manifest.permission.WRITE_EXTERNAL_STORAGE
            )
        }
    }

    private fun requestBackupFolder(callback: (BackupFolder?) -> Unit) {
        val previous = pendingBackupFolderCallback
        pendingBackupFolderCallback = null
        previous?.invoke(null)
        pendingBackupFolderCallback = callback
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
            addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION or
                    Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION or
                    Intent.FLAG_GRANT_PREFIX_URI_PERMISSION
            )
        }
        runOnUiThread {
            if (isFinishing || isDestroyed) {
                pendingBackupFolderCallback = null
                callback(null)
                return@runOnUiThread
            }
            try {
                backupFolderLauncher.launch(intent)
            } catch (error: ActivityNotFoundException) {
                pendingBackupFolderCallback = null
                callback(null)
            }
        }
    }

    private fun requestBluetoothPermissions(
        permissions: List<String>,
        callback: (Boolean) -> Unit,
    ) {
        runOnUiThread {
            if (isFinishing || isDestroyed) {
                callback(false)
                return@runOnUiThread
            }
            val missing = permissions.filter {
                checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
            }
            if (missing.isEmpty()) {
                callback(true)
                return@runOnUiThread
            }
            if (pendingBluetoothCallback != null) {
                callback(false)
                return@runOnUiThread
            }
            pendingBluetoothCallback = callback
            bluetoothPermissionLauncher.launch(missing.toTypedArray())
        }
    }

    private fun handleDownload(
        url: String,
        contentDisposition: String?,
        mimeType: String?,
    ) {
        if (!url.startsWith("http://$APP_HOST:")) {
            Toast.makeText(this, R.string.download_blocked, Toast.LENGTH_LONG).show()
            return
        }
        val fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)
        val request = DownloadManager.Request(Uri.parse(url))
            .setNotificationVisibility(
                DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
            )
            .setDestinationInExternalPublicDir(
                Environment.DIRECTORY_DOWNLOADS,
                fileName,
            )
            .addRequestHeader("X-Install-Token", adminToken)
        runCatching {
            val manager = getSystemService(DownloadManager::class.java)
                ?: error("DownloadManager tidak tersedia")
            manager.enqueue(request)
        }.onFailure {
            Toast.makeText(this, R.string.download_failed, Toast.LENGTH_LONG).show()
        }
    }

    private fun registerAdminTokenScript() {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) return
        val origin = appOrigin()
        if (origin == registeredOrigin) return
        runCatching {
            WebViewCompat.addDocumentStartJavaScript(
                webView,
                adminTokenScript(),
                setOf(origin),
            )
            registeredOrigin = origin
        }
    }

    private fun adminTokenScript(): String =
        "window.__BENGKEL_ADMIN_TOKEN__=${JSONObject.quote(adminToken)};"

    private fun injectAdminToken() {
        webView.evaluateJavascript(adminTokenScript(), null)
    }

    private fun resolveAdminToken(): String =
        runCatching { pinStore().getOrCreateAdminToken() }
            .getOrElse { fallbackAdminToken() }

    private fun fallbackAdminToken(): String {
        val bytes = ByteArray(32).also { java.security.SecureRandom().nextBytes(it) }
        return bytes.joinToString("") { "%02x".format(it.toInt() and 0xFF) }
    }

    private fun loadApp() {
        pageLoaded = false
        privacyCover.visibility = View.GONE
        offlineSpinner.visibility = View.GONE
        offlinePanel.visibility = View.GONE
        registerAdminTokenScript()
        webView.loadUrl(appUrl())
    }

    private fun appOrigin(): String = "http://$APP_HOST:$activePort"

    private fun appUrl(): String = "${appOrigin()}/"

    private fun isLocalUrl(url: Uri?): Boolean {
        if (url == null) return false
        if (url.scheme == "about") return true
        if (url.scheme != "http") return false
        if (url.host != APP_HOST) return false
        // Hanya port backend aplikasi ini; port localhost lain tetap ditolak.
        return url.port == activePort
    }

    private fun storeHasPin(): Boolean =
        runCatching { pinStore().hasPin() }.getOrDefault(false)

    private fun pinStore(): PinStore =
        cachedStore ?: PinStore.open(this).also { cachedStore = it }

    inner class PinBridge {

        @JavascriptInterface
        fun getIdleMinutes(): Int = pinSettings.idleMinutes

        @JavascriptInterface
        fun setIdleMinutes(minutes: Int) {
            runOnUiThread { pinSettings.idleMinutes = minutes }
        }

        @JavascriptInterface
        fun hasPin(): Boolean = storeHasPin()

        @JavascriptInterface
        fun lockNow() {
            runOnUiThread {
                if (storeHasPin()) {
                    PinSession.markBackground(SystemLockoutClock, pinSettings)
                    PinSession.forceLock(pinSettings)
                    privacyCover.visibility = View.VISIBLE
                    startActivity(Intent(this@MainActivity, PinActivity::class.java))
                }
            }
        }

        @JavascriptInterface
        fun applyChromeTheme(theme: String) {
            runOnUiThread { applyAppTheme(dark = theme == "dark") }
        }
    }

    companion object {
        const val APP_HOST = "127.0.0.1"
    }
}
