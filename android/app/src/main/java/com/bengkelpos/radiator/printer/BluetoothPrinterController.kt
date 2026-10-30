package com.bengkelpos.radiator.printer

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.atomic.AtomicReference

/**
 * Pengelola satu koneksi Bluetooth Classic SPP pada satu waktu.
 *
 * Logika ini tidak menyentuh API Android sehingga dapat diuji di JVM. Socket
 * hanya dibuka saat diminta, ditutup saat disconnect, dan tidak pernah
 * menghapus pasangan Bluetooth perangkat.
 */
class BluetoothPrinterController(
    private val gateway: BluetoothPrinterGateway,
    private val connectTimeoutMs: Long = DEFAULT_CONNECT_TIMEOUT_MS,
    private val printTimeoutMs: Long = DEFAULT_PRINT_TIMEOUT_MS,
    private val clock: () -> LocalDateTime = { LocalDateTime.now() },
) : AutoCloseable {

    private data class ActiveConnection(
        val address: String,
        val name: String,
        val transport: BluetoothTransport,
    )

    private var active: ActiveConnection? = null

    fun runtimePermissions(discovery: Boolean): List<String> =
        gateway.runtimePermissions(discovery)

    fun missingPermissions(discovery: Boolean): List<String> =
        gateway.missingPermissions(discovery)

    /**
     * Menggabungkan perangkat terpasang dengan hasil pemindaian. Perangkat
     * terpasang menang saat alamatnya sama karena status pasangan wajib benar.
     */
    fun discover(): List<PrinterDeviceInfo> {
        ensureReady(discovery = true)
        val merged = LinkedHashMap<String, PrinterDeviceInfo>()
        gateway.bondedDevices().forEach { merged[it.address] = it }
        gateway.discoverAvailable(DISCOVERY_WINDOW_MS).forEach {
            merged.putIfAbsent(it.address, it.copy(paired = false))
        }
        return merged.values.toList()
    }

    @Synchronized
    fun connect(address: String): PrinterDeviceInfo {
        ensureReady(discovery = false)
        val normalized = BluetoothAddress.normalize(address)
            ?: throw PrinterException(
                PrinterErrorCode.INVALID_ADDRESS,
                "Alamat Bluetooth printer tidak valid.",
            )

        val current = active
        if (current != null && current.address == normalized &&
            current.transport.isConnected()
        ) {
            return PrinterDeviceInfo(current.name, current.address, true)
        }
        closeActive()

        val device = gateway.deviceByAddress(normalized)
            ?: throw PrinterException(
                PrinterErrorCode.DEVICE_NOT_FOUND,
                "Printer Bluetooth tidak ditemukan. Pastikan printer aktif, " +
                    "berada dalam jangkauan, lalu cari ulang perangkat.",
            )
        if (!device.paired) {
            throw PrinterException(
                PrinterErrorCode.DEVICE_NOT_PAIRED,
                "Printer belum dipasangkan dengan perangkat ini. Pasangkan lewat " +
                    "Pengaturan Bluetooth Android, lalu hubungkan kembali.",
            )
        }
        if (gateway.supportsSpp(normalized) == false) {
            throw PrinterException(
                PrinterErrorCode.UNSUPPORTED_SPP,
                "Printer ini tidak menyediakan layanan Bluetooth Classic SPP. " +
                    "Adapter Bluetooth native hanya mendukung printer SPP; printer " +
                    "BLE memerlukan jalur koneksi lain.",
            )
        }

        val transport = gateway.createTransport(normalized)
        try {
            runWithTimeout(connectTimeoutMs, { transport.connect() }) {
                transport.close()
            }
            if (!transport.isConnected()) {
                throw PrinterException(
                    PrinterErrorCode.CONNECT_FAILED,
                    "Printer tidak melaporkan koneksi berhasil. Pastikan printer " +
                        "menyala dan tidak sedang dipakai perangkat lain.",
                )
            }
        } catch (error: PrinterException) {
            if (error.code != PrinterErrorCode.TIMEOUT) transport.close()
            throw error
        } catch (error: Throwable) {
            transport.close()
            throw PrinterException(
                PrinterErrorCode.CONNECT_FAILED,
                "Gagal terhubung ke printer. Pastikan printer Bluetooth Classic " +
                    "(SPP) menyala, sudah dipasangkan, dan dalam jangkauan." +
                    error.messageOrEmpty(),
                error,
            )
        }

        active = ActiveConnection(normalized, device.name, transport)
        return device
    }

    /** Menutup socket saja; pasangan Bluetooth tidak dihapus. */
    @Synchronized
    fun disconnect() {
        closeActive()
    }

    @Synchronized
    fun status(): BluetoothPrinterStatus {
        val supported = gateway.isSupported()
        if (!supported) {
            return BluetoothPrinterStatus(
                supported = false,
                permissionsGranted = true,
                enabled = false,
                connected = false,
                address = null,
                name = null,
                message = "Perangkat ini tidak memiliki Bluetooth.",
            )
        }
        val permissionsGranted = gateway.missingPermissions(false).isEmpty()
        if (!permissionsGranted) {
            return BluetoothPrinterStatus(
                supported = true,
                permissionsGranted = false,
                enabled = false,
                connected = false,
                address = null,
                name = null,
                message = "Izin Bluetooth belum diberikan. Pilih Izinkan saat " +
                    "aplikasi meminta akses.",
            )
        }
        val enabled = gateway.isEnabled()
        if (!enabled) {
            closeActive()
            return BluetoothPrinterStatus(
                supported = true,
                permissionsGranted = true,
                enabled = false,
                connected = false,
                address = null,
                name = null,
                message = "Bluetooth perangkat sedang nonaktif. Aktifkan " +
                    "Bluetooth lalu coba lagi.",
            )
        }

        val current = active
        if (current != null && !current.transport.isConnected()) {
            closeActive()
            return BluetoothPrinterStatus(
                supported = true,
                permissionsGranted = true,
                enabled = true,
                connected = false,
                address = null,
                name = null,
                message = "Koneksi printer terputus. Gunakan Hubungkan Ulang.",
            )
        }
        return BluetoothPrinterStatus(
            supported = true,
            permissionsGranted = true,
            enabled = true,
            connected = current?.transport?.isConnected() == true,
            address = current?.address,
            name = current?.name,
            message = if (current == null) "Printer belum terhubung." else null,
        )
    }

    /** Mengirim byte ESC/POS apa adanya; tidak ada perhitungan uang di sini. */
    @Synchronized
    fun print(bytes: ByteArray) {
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
        val current = active
            ?: throw PrinterException(
                PrinterErrorCode.DISCONNECTED,
                "Printer Bluetooth belum terhubung.",
            )
        if (!current.transport.isConnected()) {
            closeActive()
            throw PrinterException(
                PrinterErrorCode.DISCONNECTED,
                "Koneksi printer terputus. Hubungkan ulang lalu coba lagi.",
            )
        }
        try {
            runWithTimeout(printTimeoutMs, { current.transport.write(bytes) }) {
                current.transport.close()
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
                "Gagal mengirim data ke printer." + error.messageOrEmpty(),
                error,
            )
        }
    }

    fun testPrint(paperWidth: Int) {
        val bytes = EscPosTestTicket.build(
            paperWidth = paperWidth,
            timestamp = clock().format(TEST_TICKET_TIME),
        )
        print(bytes)
    }

    @Synchronized
    fun isConnected(): Boolean = active?.transport?.isConnected() == true

    @Synchronized
    override fun close() {
        closeActive()
    }

    private fun closeActive() {
        val current = active ?: return
        active = null
        runCatching { current.transport.close() }
    }

    private fun ensureReady(discovery: Boolean) {
        if (!gateway.isSupported()) {
            throw PrinterException(
                PrinterErrorCode.BLUETOOTH_UNSUPPORTED,
                "Perangkat ini tidak memiliki Bluetooth.",
            )
        }
        val missing = gateway.missingPermissions(discovery)
        if (missing.isNotEmpty()) {
            throw PrinterException(
                PrinterErrorCode.PERMISSION_DENIED,
                BluetoothPermissionPolicy.denialMessage(discovery),
            )
        }
        if (!gateway.isEnabled()) {
            throw PrinterException(
                PrinterErrorCode.BLUETOOTH_DISABLED,
                "Bluetooth perangkat sedang nonaktif. Aktifkan Bluetooth lalu " +
                    "coba lagi.",
            )
        }
    }

    /**
     * Menjalankan operasi socket dengan batas waktu. Java tidak menyediakan
     * timeout untuk BluetoothSocket.connect, jadi socket ditutup dari thread
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
        worker.name = "bengkel-bt-printer"
        worker.start()
        worker.join(timeoutMs)
        if (worker.isAlive) {
            runCatching { onTimeout() }
            worker.join(TIMEOUT_CLOSE_GRACE_MS)
            throw PrinterException(
                PrinterErrorCode.TIMEOUT,
                "Printer tidak merespons tepat waktu. Pastikan printer menyala " +
                    "dan dalam jangkauan, lalu coba lagi.",
            )
        }
        failure.get()?.let { throw it }
    }

    private fun Throwable.messageOrEmpty(): String {
        val detail = message?.trim().orEmpty()
        return if (detail.isEmpty()) "" else " ($detail)"
    }

    companion object {
        const val DEFAULT_CONNECT_TIMEOUT_MS = 15_000L
        const val DEFAULT_PRINT_TIMEOUT_MS = 20_000L
        const val DISCOVERY_WINDOW_MS = 12_000L
        const val MAX_PRINT_BYTES = 512 * 1024
        private const val TIMEOUT_CLOSE_GRACE_MS = 1_000L
        private val TEST_TICKET_TIME = DateTimeFormatter.ofPattern("dd-MM-yyyy HH:mm")
    }
}
