package com.bengkelpos.radiator

import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.bengkelpos.radiator.backend.BackendHealth
import com.bengkelpos.radiator.backend.BackendManager
import com.bengkelpos.radiator.pin.PinActivity
import com.bengkelpos.radiator.pin.PinSession
import com.bengkelpos.radiator.pin.PinSettings
import com.bengkelpos.radiator.pin.PinStore
import com.bengkelpos.radiator.pin.SystemLockoutClock
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var offlinePanel: View
    private lateinit var offlineText: TextView
    private lateinit var privacyCover: View
    private lateinit var pinSettings: PinSettings
    private lateinit var adminToken: String

    private var cachedStore: PinStore? = null
    private var pageLoaded = false
    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null

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

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        offlinePanel = findViewById(R.id.offlinePanel)
        offlineText = findViewById(R.id.offlineText)
        privacyCover = findViewById(R.id.privacyCover)
        pinSettings = PinSettings(this)
        adminToken = resolveAdminToken()

        findViewById<Button>(R.id.retryButton).setOnClickListener { startBackend() }

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
            PinSession.markResumed()
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
        webView.loadUrl("about:blank")
        webView.clearHistory()
        webView.removeAllViews()
        webView.destroy()
        super.onDestroy()
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
        registerAdminTokenScript()
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
                offlinePanel.visibility = View.GONE
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                if (request.isForMainFrame) {
                    pageLoaded = false
                    privacyCover.visibility = View.GONE
                    offlineText.setText(R.string.offline_hint)
                    offlinePanel.visibility = View.VISIBLE
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
        pageLoaded = false
        privacyCover.visibility = View.GONE
        offlineText.setText(R.string.preparing_hint)
        offlinePanel.visibility = View.VISIBLE
        val token = adminToken
        Thread {
            val ready = runCatching {
                BackendManager.start(applicationContext, token)
                BackendHealth.awaitReady()
            }.getOrDefault(false)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (ready) loadApp() else showBackendError()
            }
        }.start()
    }

    private fun showBackendError() {
        pageLoaded = false
        privacyCover.visibility = View.GONE
        offlineText.setText(R.string.backend_error_hint)
        offlinePanel.visibility = View.VISIBLE
    }

    private fun registerAdminTokenScript() {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) return
        runCatching {
            WebViewCompat.addDocumentStartJavaScript(
                webView,
                adminTokenScript(),
                setOf(APP_ORIGIN),
            )
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
        offlinePanel.visibility = View.GONE
        webView.loadUrl(APP_URL)
    }

    private fun isLocalUrl(url: Uri?): Boolean {
        if (url == null) return false
        if (url.scheme == "about") return true
        if (url.scheme != "http") return false
        if (url.host != APP_HOST) return false
        // Hanya port backend aplikasi ini; port localhost lain tetap ditolak.
        return url.port == APP_PORT
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
                    PinSession.markBackground(SystemLockoutClock)
                    privacyCover.visibility = View.VISIBLE
                    startActivity(Intent(this@MainActivity, PinActivity::class.java))
                }
            }
        }
    }

    companion object {
        private const val APP_HOST = "127.0.0.1"
        private const val APP_PORT = BackendManager.PORT
        private val APP_ORIGIN = "http://$APP_HOST:$APP_PORT"
        private val APP_URL = "$APP_ORIGIN/"
    }
}
