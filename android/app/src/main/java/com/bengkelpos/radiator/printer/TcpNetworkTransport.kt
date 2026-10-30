package com.bengkelpos.radiator.printer

import java.io.IOException
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Socket TCP RAW untuk printer ESC/POS (umumnya port 9100).
 *
 * Port tidak dipaksa 9100: nilai berasal dari konfigurasi pengguna. Socket hanya
 * membuktikan port dapat dibuka; dukungan protokol RAW tetap harus diuji dengan
 * tes cetak pada printer nyata.
 */
class TcpNetworkTransport(
    private val host: String,
    private val port: Int,
    private val connectTimeoutMs: Int,
) : NetworkTransport {

    private var socket: Socket? = null
    private var output: OutputStream? = null

    @Volatile
    private var closed = false

    override fun connect() {
        val created = Socket()
        socket = created
        try {
            created.tcpNoDelay = true
            created.keepAlive = true
            created.connect(InetSocketAddress(host, port), connectTimeoutMs)
            output = created.getOutputStream()
        } catch (error: Throwable) {
            output = null
            socket = null
            runCatching { created.close() }
            throw error
        }
    }

    override fun write(bytes: ByteArray) {
        if (closed) throw IOException("Socket printer sudah ditutup.")
        val stream = output ?: throw IOException("Socket printer belum dibuka.")
        val current = socket ?: throw IOException("Socket printer sudah ditutup.")
        if (!current.isConnected || current.isClosed) {
            throw IOException("Socket printer sudah tertutup.")
        }
        stream.write(bytes)
        stream.flush()
    }

    override fun isConnected(): Boolean {
        val current = socket ?: return false
        return !closed && current.isConnected && !current.isClosed && !current.isOutputShutdown
    }

    override fun close() {
        closed = true
        output = null
        val current = socket
        socket = null
        runCatching { current?.close() }
    }
}
