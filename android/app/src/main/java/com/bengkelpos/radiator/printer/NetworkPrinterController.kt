package com.bengkelpos.radiator.printer

import java.net.ConnectException
import java.net.NoRouteToHostException
import java.net.SocketException
import java.net.SocketTimeoutException
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.atomic.AtomicReference

/**
 * Pengelola satu koneksi RAW TCP ke printer jaringan (Wi-Fi/LAN).
 *
 * Kelas ini tidak menyentuh konfigurasi printer maupun data transaksi; ia hanya
 * membuka, memakai, dan menutup socket. Pemanggil (NativeBridge) menjalankannya
 * di executor sehingga UI tidak pernah diblokir.
 *
 * Auto-reconnect saat mencetak hanya dilakukan bila belum ada byte yang dikirim
 * ke printer. Kegagalan di tengah penulisan tidak diulang agar struk tidak
 * tercetak ganda.
 */
class NetworkPrinterController(
    private val discovery: NetworkPrinterDiscovery,
    private val transportFactory: (
        ip: String,
        port: Int,
        connectTimeoutMs: Int,
    ) -> NetworkTransport = { ip, port, timeout ->
        TcpNetworkTransport(ip, port, timeout)
    },
    private val connectTimeoutMs: Long = DEFAULT_CONNECT_TIMEOUT_MS,
    private val printTimeoutMs: Long = DEFAULT_PRINT_TIMEOUT_MS,
    private val clock: () -> LocalDateTime = { LocalDateTime.now() },
) : AutoCloseable {

    private data class ActiveConnection(
        val ip: String,
        val port: Int,
        val transport: NetworkTransport,
    )

    private var active: ActiveConnection? = null

    fun isDiscoverySupported(): Boolean = discovery.isSupported()

    /** Hasil NSD; alamat IP yang hanya "bisa dijangkau" tidak pernah dianggap temuan. */
    fun discover(): List<NetworkPrinterDevice> {
        if (!discovery.isSupported()) {
            throw PrinterException(
                PrinterErrorCode.DISCOVERY_FAILED,
                "Pencarian otomatis printer jaringan tidak tersedia di perangkat " +
                    "ini. Masukkan IP dan port printer secara manual.",
            )
        }
        return try {
            discovery.discover(DISCOVERY_WINDOW_MS)
                .filter {
                    NetworkAddress.normalizeIp(it.ip) != null &&
                        NetworkAddress.normalizePort(it.port) != null
                }
                .distinctBy { "${it.ip}:${it.port}" }
        } catch (error: PrinterException) {
            throw error
        } catch (error: Throwable) {
            throw PrinterException(
                PrinterErrorCode.DISCOVERY_FAILED,
                "Pencarian printer jaringan gagal. Masukkan IP dan port printer " +
                    "secara manual.",
                error,
            )
        }
    }

    @Synchronized
    fun connect(ip: String, port: Int): NetworkEndpoint {
        val endpoint = resolveEndpoint(ip, port)
        val current = active
        if (current != null && current.ip == endpoint.ip &&
            current.port == endpoint.port && current.transport.isConnected()
        ) {
            return endpoint
        }
        closeActive()
        active = openConnection(endpoint)
        return endpoint
    }

    /** Menutup socket saja; konfigurasi IP/port tetap tersimpan di backend. */
    @Synchronized
    fun disconnect() {
        closeActive()
    }

    @Synchronized
    fun status(): NetworkPrinterStatus {
        val current = active
        if (current != null && !current.transport.isConnected()) {
            closeActive()
            return NetworkPrinterStatus(
                connected = false,
                ip = null,
                port = null,
                message = "Koneksi printer terputus. Gunakan Hubungkan Ulang.",
                discoverySupported = discovery.isSupported(),
            )
        }
        return NetworkPrinterStatus(
            connected = current?.transport?.isConnected() == true,
            ip = current?.ip,
            port = current?.port,
            message = if (current == null) "Printer jaringan belum terhubung." else null,
            discoverySupported = discovery.isSupported(),
        )
    }

    /**
     * Mengirim byte ESC/POS apa adanya; tidak ada perhitungan uang di sini.
     *
     * Bila [ip] dan [port] dikirim, koneksi yang mati atau belum ada akan dibuka
     * ulang ke alamat konfigurasi sebelum byte pertama ditulis (auto-reconnect).
     */
    @Synchronized
    fun print(bytes: ByteArray, ip: String? = null, port: Int? = null) {
        validatePayload(bytes)
        val target = if (ip != null || port != null) {
            resolveEndpoint(ip.orEmpty(), port ?: 0)
        } else {
            null
        }
        val transport = usableTransport(target)
        try {
            runWithTimeout(printTimeoutMs, { transport.write(bytes) }) {
                transport.close()
            }
        } catch (error: PrinterException) {
            if (error.code == PrinterErrorCode.TIMEOUT) {
                // runWithTimeout sudah menutup socket; cukup lepaskan referensi.
                active = null
            } else {
                closeActive()
            }
            throw error
        } catch (error: Throwable) {
            closeActive()
            throw PrinterException(
                PrinterErrorCode.PRINT_FAILED,
                "Gagal mengirim struk ke printer jaringan. Pastikan printer menyala " +
                    "dan tetap terhubung ke Wi-Fi/LAN." + error.messageOrEmpty(),
                error,
            )
        }
    }

    fun testPrint(paperWidth: Int, ip: String? = null, port: Int? = null) {
        val bytes = EscPosTestTicket.build(
            paperWidth = paperWidth,
            timestamp = clock().format(TEST_TICKET_TIME),
            connectionLabel = "Wi-Fi/LAN",
        )
        print(bytes, ip, port)
    }

    @Synchronized
    fun isConnected(): Boolean = active?.transport?.isConnected() == true

    @Synchronized
    override fun close() {
        closeActive()
    }

    private fun usableTransport(target: NetworkEndpoint?): NetworkTransport {
        val current = active
        if (current != null && current.transport.isConnected() &&
            (target == null || (current.ip == target.ip && current.port == target.port))
        ) {
            return current.transport
        }
        if (current != null) closeActive()
        if (target == null) {
            throw PrinterException(
                PrinterErrorCode.DISCONNECTED,
                "Printer jaringan belum terhubung. Hubungkan printer lalu coba lagi.",
            )
        }
        val connection = openConnection(target)
        active = connection
        return connection.transport
    }

    private fun openConnection(endpoint: NetworkEndpoint): ActiveConnection {
        val transport = transportFactory(
            endpoint.ip,
            endpoint.port,
            connectTimeoutMs.toInt(),
        )
        try {
            runWithTimeout(connectTimeoutMs, { transport.connect() }) {
                transport.close()
            }
            if (!transport.isConnected()) {
                throw PrinterException(
                    PrinterErrorCode.CONNECT_FAILED,
                    "Printer tidak melaporkan koneksi berhasil. Pastikan printer " +
                        "menyala dan mendukung cetak RAW TCP pada port yang dipakai.",
                )
            }
        } catch (error: PrinterException) {
            if (error.code != PrinterErrorCode.TIMEOUT) transport.close()
            throw error
        } catch (error: Throwable) {
            transport.close()
            throw mapConnectFailure(endpoint, error)
        }
        return ActiveConnection(endpoint.ip, endpoint.port, transport)
    }

    private fun mapConnectFailure(
        endpoint: NetworkEndpoint,
        error: Throwable,
    ): PrinterException {
        val where = "${endpoint.ip}:${endpoint.port}"
        val code = when {
            error is SocketTimeoutException -> PrinterErrorCode.TIMEOUT
            error is ConnectException -> PrinterErrorCode.CONNECTION_REFUSED
            error is NoRouteToHostException -> PrinterErrorCode.NETWORK_UNREACHABLE
            error is SocketException &&
                error.message.orEmpty().contains("unreachable", ignoreCase = true) ->
                PrinterErrorCode.NETWORK_UNREACHABLE
            else -> PrinterErrorCode.CONNECT_FAILED
        }
        val message = when (code) {
            PrinterErrorCode.TIMEOUT ->
                "Koneksi ke printer $where melebihi batas waktu. Periksa kabel/" +
                    "Wi-Fi, pastikan IP benar, dan printer menyala."
            PrinterErrorCode.CONNECTION_REFUSED ->
                "Printer menolak koneksi pada port ${endpoint.port}. Pastikan port " +
                    "RAW TCP benar (umumnya 9100) dan printer mendukung mode RAW, " +
                    "bukan hanya protokol lain."
            PrinterErrorCode.NETWORK_UNREACHABLE ->
                "Alamat ${endpoint.ip} tidak dapat dijangkau dari perangkat ini. " +
                    "Pastikan HP dan printer berada di jaringan yang sama."
            else ->
                "Gagal terhubung ke printer $where. Pastikan printer menyala, " +
                    "IP dan port benar, serta mendukung cetak RAW TCP." +
                    error.messageOrEmpty()
        }
        return PrinterException(code, message, error)
    }

    private fun resolveEndpoint(ip: String, port: Int): NetworkEndpoint {
        val normalizedIp = NetworkAddress.normalizeIp(ip)
            ?: throw PrinterException(
                PrinterErrorCode.INVALID_IP,
                "Alamat IP printer tidak valid. Gunakan format IPv4 seperti " +
                    "192.168.1.9 atau alamat IPv6 literal.",
            )
        val normalizedPort = NetworkAddress.normalizePort(port)
            ?: throw PrinterException(
                PrinterErrorCode.INVALID_PORT,
                "Port printer tidak valid. Gunakan angka 1-65535 (umumnya 9100).",
            )
        return NetworkEndpoint(normalizedIp, normalizedPort)
    }

    private fun validatePayload(bytes: ByteArray) {
        if (bytes.isEmpty()) {
            throw PrinterException(
                PrinterErrorCode.INVALID_PAYLOAD,
                "Data cetak kosong.",
            )
        }
        if (bytes.size > MAX_PRINT_BYTES) {
            throw PrinterException(
                PrinterErrorCode.INVALID_PAYLOAD,
                "Data cetak terlalu besar untuk dikirim ke printer.",
            )
        }
    }

    private fun closeActive() {
        val current = active ?: return
        active = null
        runCatching { current.transport.close() }
    }

    /**
     * Menjalankan operasi socket dengan batas waktu. Socket ditutup dari thread
     * pemanggil saat batas waktu habis agar operasi yang menggantung berhenti.
     */
    private fun runWithTimeout(
        timeoutMs: Long,
        action: () -> Unit,
        onTimeout: () -> Unit,
    ) {
        val failure = AtomicReference<Throwable?>()
        val worker = Thread {
            try {
                action()
            } catch (error: Throwable) {
                failure.set(error)
            }
        }
        worker.isDaemon = true
        worker.name = "bengkel-net-printer"
        worker.start()
        worker.join(timeoutMs)
        if (worker.isAlive) {
            runCatching { onTimeout() }
            worker.join(TIMEOUT_CLOSE_GRACE_MS)
            throw PrinterException(
                PrinterErrorCode.TIMEOUT,
                "Printer jaringan tidak merespons tepat waktu. Periksa Wi-Fi/LAN, " +
                    "alamat IP, dan port printer.",
            )
        }
        failure.get()?.let { throw it }
    }

    private fun Throwable.messageOrEmpty(): String {
        val detail = message?.trim().orEmpty()
        return if (detail.isEmpty()) "" else " ($detail)"
    }

    companion object {
        const val DEFAULT_CONNECT_TIMEOUT_MS = 10_000L
        const val DEFAULT_PRINT_TIMEOUT_MS = 15_000L
        const val DISCOVERY_WINDOW_MS = 8_000L
        const val MAX_PRINT_BYTES = 512 * 1024
        private const val TIMEOUT_CLOSE_GRACE_MS = 1_000L
        private val TEST_TICKET_TIME = DateTimeFormatter.ofPattern("dd-MM-yyyy HH:mm")
    }
}
