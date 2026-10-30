package com.bengkelpos.radiator.printer

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.atomic.AtomicReference

/**
 * Pengelola satu koneksi printer USB OTG.
 *
 * Logika ini tidak menyentuh API Android sehingga dapat diuji di JVM. Socket
 * USB (koneksi + interface) hanya dibuka saat diminta, ditutup saat disconnect
 * atau kegagalan, dan tidak pernah mengubah konfigurasi printer maupun data
 * transaksi.
 *
 * Hanya printer dengan endpoint BULK OUT yang didukung. Printer dengan driver
 * proprietary atau protokol vendor lain tidak diklaim kompatibel.
 */
class UsbPrinterController(
    private val gateway: UsbPrinterGateway,
    private val connectTimeoutMs: Long = DEFAULT_CONNECT_TIMEOUT_MS,
    private val printTimeoutMs: Long = DEFAULT_PRINT_TIMEOUT_MS,
    private val clock: () -> LocalDateTime = { LocalDateTime.now() },
) : AutoCloseable {

    private data class ActiveConnection(
        val identity: String,
        val name: String,
        val transport: UsbTransport,
    )

    private var active: ActiveConnection? = null

    fun discover(): List<UsbPrinterDevice> {
        ensureHostSupported()
        return gateway.devices()
    }

    @Synchronized
    fun connect(identity: String): UsbPrinterDevice =
        openConnection(normalizeIdentity(identity)).let { connection ->
            gateway.deviceByIdentity(connection.identity)
                ?: UsbPrinterDevice(
                    identity = connection.identity,
                    name = connection.name,
                    vendorId = 0,
                    productId = 0,
                    interfaces = emptyList(),
                    supported = true,
                    requiresPermission = false,
                )
        }

    /** Menutup koneksi dan melepas interface; konfigurasi tetap tersimpan. */
    @Synchronized
    fun disconnect() {
        closeActive()
    }

    @Synchronized
    fun status(): UsbPrinterStatus {
        if (!gateway.isSupported()) {
            return UsbPrinterStatus(
                supported = false,
                connected = false,
                identity = null,
                name = null,
                message = "Perangkat ini tidak mendukung USB Host (OTG).",
            )
        }
        val current = active
            ?: return UsbPrinterStatus(
                supported = true,
                connected = false,
                identity = null,
                name = null,
                message = "Printer USB belum terhubung.",
            )
        if (!gateway.isAttached(current.identity)) {
            closeActive()
            return UsbPrinterStatus(
                supported = true,
                connected = false,
                identity = null,
                name = null,
                message = "Printer USB terputus. Sambungkan kabel lalu gunakan " +
                    "Hubungkan Ulang.",
            )
        }
        if (!current.transport.isConnected()) {
            closeActive()
            return UsbPrinterStatus(
                supported = true,
                connected = false,
                identity = null,
                name = null,
                message = "Koneksi printer USB terputus. Gunakan Hubungkan Ulang.",
            )
        }
        return UsbPrinterStatus(
            supported = true,
            connected = true,
            identity = current.identity,
            name = current.name,
            message = null,
        )
    }

    /**
     * Mengirim byte ESC/POS apa adanya. Bila [identity] dikirim dan belum ada
     * koneksi hidup, printer dihubungkan ulang sebelum byte pertama ditulis.
     * Kegagalan di tengah penulisan tidak diulang agar struk tidak ganda.
     */
    @Synchronized
    fun print(bytes: ByteArray, identity: String? = null) {
        validatePayload(bytes)
        val target = identity?.let { normalizeIdentity(it) }
        val connection = usableConnection(target)
        try {
            runWithTimeout(printTimeoutMs, { connection.transport.write(bytes) }) {
                connection.transport.close()
            }
        } catch (error: PrinterException) {
            if (error.code == PrinterErrorCode.TIMEOUT) {
                active = null
            } else {
                closeActive()
            }
            throw error
        } catch (error: Throwable) {
            val detached = !gateway.isAttached(connection.identity)
            closeActive()
            if (detached) {
                throw PrinterException(
                    PrinterErrorCode.DEVICE_DETACHED,
                    "Kabel USB terputus saat mencetak. Sambungkan kembali printer " +
                        "lalu cetak ulang dari riwayat transaksi.",
                    error,
                )
            }
            throw PrinterException(
                PrinterErrorCode.PRINT_FAILED,
                "Gagal mengirim struk ke printer USB. Periksa kabel USB dan " +
                    "pastikan printer menyala serta tidak sedang dipakai " +
                    "aplikasi lain." + error.messageOrEmpty(),
                error,
            )
        }
    }

    fun testPrint(paperWidth: Int, identity: String? = null) {
        val bytes = EscPosTestTicket.build(
            paperWidth = paperWidth,
            timestamp = clock().format(TEST_TICKET_TIME),
            connectionLabel = "USB OTG",
        )
        print(bytes, identity)
    }

    @Synchronized
    fun isConnected(): Boolean = active?.transport?.isConnected() == true

    @Synchronized
    override fun close() {
        closeActive()
    }

    private fun usableConnection(target: String?): ActiveConnection {
        val current = active
        if (current != null && current.transport.isConnected() &&
            (target == null || current.identity == target)
        ) {
            return current
        }
        if (current != null) closeActive()
        if (target == null) {
            throw PrinterException(
                PrinterErrorCode.DISCONNECTED,
                "Printer USB belum terhubung. Hubungkan printer lalu coba lagi.",
            )
        }
        return openConnection(target)
    }

    private fun openConnection(identity: String): ActiveConnection {
        ensureHostSupported()
        var device = gateway.deviceByIdentity(identity)
            ?: throw PrinterException(
                PrinterErrorCode.DEVICE_NOT_FOUND,
                "Perangkat USB tidak ditemukan. Pastikan kabel OTG dan printer " +
                    "terhubung, lalu cari ulang perangkat.",
            )
        ensureSupportedInterface(device)

        val current = active
        if (current != null && current.identity == identity &&
            current.transport.isConnected()
        ) {
            return current
        }
        closeActive()

        if (!gateway.hasPermission(identity)) {
            when (gateway.requestPermission(identity)) {
                UsbPermissionResult.GRANTED -> Unit
                UsbPermissionResult.DENIED -> throw PrinterException(
                    PrinterErrorCode.USB_PERMISSION_DENIED,
                    "Izin akses perangkat USB ditolak. Setujui izin saat " +
                        "aplikasi meminta, lalu hubungkan kembali.",
                )
                UsbPermissionResult.TIMEOUT -> throw PrinterException(
                    PrinterErrorCode.TIMEOUT,
                    "Permintaan izin USB tidak dijawab. Setujui izin pada dialog " +
                        "Android lalu coba lagi.",
                )
            }
            device = gateway.deviceByIdentity(identity)
                ?: throw PrinterException(
                    PrinterErrorCode.DEVICE_NOT_FOUND,
                    "Perangkat USB terputus saat menunggu izin. Sambungkan " +
                        "kembali lalu coba lagi.",
                )
            ensureSupportedInterface(device)
        }

        val transport = gateway.createTransport(identity)
        try {
            runWithTimeout(connectTimeoutMs, { transport.connect() }) {
                transport.close()
            }
            if (!transport.isConnected()) {
                throw PrinterException(
                    PrinterErrorCode.CONNECT_FAILED,
                    "Printer tidak melaporkan koneksi USB berhasil. Pastikan " +
                        "printer menyala dan tidak sedang dipakai aplikasi lain.",
                )
            }
        } catch (error: PrinterException) {
            if (error.code != PrinterErrorCode.TIMEOUT) transport.close()
            throw error
        } catch (error: Throwable) {
            transport.close()
            if (!gateway.isAttached(identity)) {
                throw PrinterException(
                    PrinterErrorCode.DEVICE_DETACHED,
                    "Kabel USB terputus saat menghubungkan printer. Sambungkan " +
                        "kembali lalu coba lagi.",
                    error,
                )
            }
            throw PrinterException(
                PrinterErrorCode.CONNECT_FAILED,
                "Gagal membuka koneksi printer USB. Pastikan printer menyala, " +
                    "mendukung ESC/POS, dan tidak sedang dipakai aplikasi lain." +
                    error.messageOrEmpty(),
                error,
            )
        }

        val connection = ActiveConnection(identity, device.name, transport)
        active = connection
        return connection
    }

    private fun ensureHostSupported() {
        if (!gateway.isSupported()) {
            throw PrinterException(
                PrinterErrorCode.USB_UNSUPPORTED,
                "Perangkat ini tidak mendukung USB Host (OTG). Gunakan " +
                    "Bluetooth, Wi-Fi/LAN, atau Android System Print.",
            )
        }
    }

    private fun ensureSupportedInterface(device: UsbPrinterDevice) {
        if (!UsbPrinterSupport.supportsBulkOut(device)) {
            throw PrinterException(
                PrinterErrorCode.UNSUPPORTED_USB,
                "Perangkat USB ini tidak menyediakan endpoint BULK OUT untuk " +
                    "ESC/POS. Printer yang membutuhkan driver khusus tidak " +
                    "didukung aplikasi ini.",
            )
        }
    }

    private fun normalizeIdentity(value: String?): String =
        UsbPrinterSupport.normalizeIdentity(value)
            ?: throw PrinterException(
                PrinterErrorCode.INVALID_ADDRESS,
                "Identitas perangkat USB tidak valid. Pilih printer dari hasil " +
                    "pencarian USB.",
            )

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
        worker.name = "bengkel-usb-printer"
        worker.start()
        worker.join(timeoutMs)
        if (worker.isAlive) {
            runCatching { onTimeout() }
            worker.join(TIMEOUT_CLOSE_GRACE_MS)
            throw PrinterException(
                PrinterErrorCode.TIMEOUT,
                "Printer USB tidak merespons tepat waktu. Cabut dan sambungkan " +
                    "kembali kabel USB, lalu coba lagi.",
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
        const val MAX_PRINT_BYTES = 512 * 1024
        private const val TIMEOUT_CLOSE_GRACE_MS = 1_000L
        private val TEST_TICKET_TIME = DateTimeFormatter.ofPattern("dd-MM-yyyy HH:mm")
    }
}
