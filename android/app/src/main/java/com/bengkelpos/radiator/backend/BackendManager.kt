package com.bengkelpos.radiator.backend

import android.content.Context
import com.chaquo.python.Python

/**
 * Mengelola siklus hidup server uvicorn di dalam proses aplikasi.
 */
object BackendManager {

    const val PORT = 8000
    const val BASE_URL = "http://127.0.0.1:$PORT"

    private val lock = Any()
    private var running = false

    fun start(context: Context, adminToken: String) {
        synchronized(lock) {
            if (running) return
            running = true
            try {
                val appContext = context.applicationContext
                val backendDir = BackendInstaller(appContext).ensureInstalled()
                val module = Python.getInstance().getModule("bootstrap")
                module.callAttr(
                    "start",
                    backendDir.absolutePath,
                    appContext.filesDir.absolutePath,
                    PORT,
                    adminToken,
                )
            } catch (error: Throwable) {
                running = false
                throw error
            }
        }
    }

    fun stop() {
        synchronized(lock) {
            if (!running) return
            running = false
            runCatching { Python.getInstance().getModule("bootstrap").callAttr("stop") }
        }
    }
}
