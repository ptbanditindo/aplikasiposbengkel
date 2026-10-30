package com.bengkelpos.radiator.backend

import java.net.HttpURLConnection
import java.net.URL

/** Menunggu server lokal siap menerima permintaan HTTP. */
object BackendHealth {

    fun awaitReady(
        port: Int = BackendManager.activePort,
        timeoutMs: Long = 90_000L,
    ): Boolean {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            if (ping(port)) return true
            try {
                Thread.sleep(250L)
            } catch (interrupted: InterruptedException) {
                Thread.currentThread().interrupt()
                return false
            }
        }
        return false
    }

    private fun ping(port: Int): Boolean = runCatching {
        val connection = URL("http://127.0.0.1:$port/api/health")
            .openConnection() as HttpURLConnection
        connection.connectTimeout = 1_500
        connection.readTimeout = 1_500
        connection.requestMethod = "GET"
        try {
            connection.responseCode == HttpURLConnection.HTTP_OK
        } finally {
            connection.disconnect()
        }
    }.getOrDefault(false)
}
