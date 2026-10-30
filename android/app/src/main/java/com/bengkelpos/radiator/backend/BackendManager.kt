package com.bengkelpos.radiator.backend

import android.content.Context
import com.chaquo.python.Python
import java.io.File
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket

/**
 * Mengelola siklus hidup server uvicorn di dalam proses aplikasi.
 *
 * Ref: T-07 - `running` baru bernilai true setelah health check lulus, sehingga
 * tombol "Coba lagi" benar-benar memulai ulang setelah kegagalan, dan port
 * dicari otomatis di rentang 8000-8010 bila port sebelumnya dipakai aplikasi lain.
 */
object BackendManager {

    const val DEFAULT_PORT = 8000
    const val LAST_PORT = 8010
    private const val HOST = "127.0.0.1"
    private const val READY_TIMEOUT_MS = 25_000L
    private const val THREAD_START_TIMEOUT_MS = 3_000L

    private val lock = Any()
    private var running = false

    @Volatile
    var activePort: Int = DEFAULT_PORT
        private set

    val baseUrl: String
        get() = "http://$HOST:$activePort"

    /**
     * Menjalankan server pada port bebas pertama di 8000-8010.
     * Mengembalikan true hanya bila server benar-benar menjawab /api/health.
     */
    fun start(context: Context, adminToken: String): Boolean = synchronized(lock) {
        if (running && isThreadAlive()) return true
        running = false

        val appContext = context.applicationContext
        val backendDir = BackendInstaller(appContext).ensureInstalled()

        for (port in DEFAULT_PORT..LAST_PORT) {
            if (!isPortFree(port)) continue
            if (!startOn(backendDir, appContext, port, adminToken)) continue
            if (!waitForThread()) {
                stopServer()
                continue
            }
            if (BackendHealth.awaitReady(port, READY_TIMEOUT_MS)) {
                activePort = port
                running = true
                return true
            }
            // Thread hidup tetapi server tidak siap (mis. bind gagal): bersihkan
            // lalu coba port berikutnya.
            stopServer()
        }

        running = false
        false
    }

    fun isRunning(): Boolean = synchronized(lock) { running && isThreadAlive() }

    fun stop() {
        synchronized(lock) {
            running = false
            stopServer()
        }
    }

    private fun startOn(
        backendDir: File,
        appContext: Context,
        port: Int,
        adminToken: String,
    ): Boolean = runCatching {
        Python.getInstance().getModule("bootstrap").callAttr(
            "start",
            backendDir.absolutePath,
            appContext.filesDir.absolutePath,
            port,
            adminToken,
        )
        true
    }.getOrDefault(false)

    private fun waitForThread(): Boolean {
        val deadline = System.currentTimeMillis() + THREAD_START_TIMEOUT_MS
        while (System.currentTimeMillis() < deadline) {
            if (isThreadAlive()) return true
            try {
                Thread.sleep(100L)
            } catch (interrupted: InterruptedException) {
                Thread.currentThread().interrupt()
                return false
            }
        }
        return false
    }

    private fun isThreadAlive(): Boolean = runCatching {
        Python.getInstance().getModule("bootstrap").callAttr("is_alive").toBoolean()
    }.getOrDefault(false)

    private fun stopServer() {
        runCatching {
            Python.getInstance().getModule("bootstrap").callAttr("stop")
        }
    }

    private fun isPortFree(port: Int): Boolean = runCatching {
        ServerSocket().use { socket ->
            socket.reuseAddress = true
            socket.bind(InetSocketAddress(InetAddress.getByName(HOST), port))
        }
        true
    }.getOrDefault(false)
}
