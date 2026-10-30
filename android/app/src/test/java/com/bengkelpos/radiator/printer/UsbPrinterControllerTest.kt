package com.bengkelpos.radiator.printer

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.time.LocalDateTime

class UsbPrinterControllerTest {

    private val identity = "usb:04b8:0202"
    private val otherIdentity = "usb:1234:5678"

    private val bulkIn = UsbEndpointInfo(
        address = 0x82,
        direction = UsbEndpointDirection.IN,
        type = UsbEndpointType.BULK,
        maxPacketSize = 64,
    )

    private class FakeTransport(
        private val connectDelayMs: Long = 0,
        private val connectFailure: Throwable? = null,
        private val writeFailure: Throwable? = null,
        private val writeDelayMs: Long = 0,
        private val reportsConnected: Boolean = true,
    ) : UsbTransport {
        @Volatile
        var connected = false

        @Volatile
        var closed = false
        var closeCount = 0
        var connectCount = 0
        val written = mutableListOf<ByteArray>()

        override fun connect() {
            connectCount += 1
            if (connectDelayMs > 0) Thread.sleep(connectDelayMs)
            connectFailure?.let { throw it }
            connected = reportsConnected
        }

        override fun write(bytes: ByteArray) {
            if (!connected || closed) throw IOException("Koneksi USB tertutup")
            if (writeDelayMs > 0) Thread.sleep(writeDelayMs)
            if (closed) throw IOException("Koneksi USB tertutup")
            writeFailure?.let { throw it }
            written.add(bytes.copyOf())
        }

        override fun isConnected(): Boolean = connected && !closed

        override fun close() {
            closed = true
            connected = false
            closeCount += 1
        }
    }

    private class FakeGateway(
        var supported: Boolean = true,
        val devices: MutableList<UsbPrinterDevice> = mutableListOf(),
        val attached: MutableSet<String> = mutableSetOf(),
        var permissionGranted: Boolean = false,
        var permissionResult: UsbPermissionResult = UsbPermissionResult.GRANTED,
        var permissionRemovesDevice: Boolean = false,
        var transportFactory: () -> FakeTransport = { FakeTransport() },
    ) : UsbPrinterGateway {
        val transports = mutableListOf<FakeTransport>()
        var permissionRequests = 0
        var transportRequests = 0

        override fun isSupported(): Boolean = supported

        override fun devices(): List<UsbPrinterDevice> = devices.toList()

        override fun deviceByIdentity(identity: String): UsbPrinterDevice? =
            devices.firstOrNull { it.identity == identity }

        override fun isAttached(identity: String): Boolean = attached.contains(identity)

        override fun hasPermission(identity: String): Boolean = permissionGranted

        override fun requestPermission(identity: String): UsbPermissionResult {
            permissionRequests += 1
            val result = permissionResult
            if (result == UsbPermissionResult.GRANTED) {
                permissionGranted = true
                if (permissionRemovesDevice) {
                    devices.removeAll { it.identity == identity }
                }
            }
            return result
        }

        override fun createTransport(identity: String): UsbTransport {
            transportRequests += 1
            return transportFactory().also { transports.add(it) }
        }
    }

    private class Harness {
        val gateway = FakeGateway()

        fun addPrinter(
            identity: String = "usb:04b8:0202",
            name: String = "Printer USB",
            endpoints: List<UsbEndpointInfo> = listOf(
                UsbEndpointInfo(
                    address = 0x01,
                    direction = UsbEndpointDirection.OUT,
                    type = UsbEndpointType.BULK,
                    maxPacketSize = 64,
                ),
            ),
            interfaceClass: Int = 7,
        ): UsbPrinterDevice {
            val device = UsbPrinterDevice(
                identity = identity,
                name = name,
                vendorId = 0x04B8,
                productId = 0x0202,
                interfaces = listOf(
                    UsbInterfaceInfo(
                        index = 0,
                        interfaceClass = interfaceClass,
                        interfaceSubclass = 0,
                        interfaceProtocol = 0,
                        endpoints = endpoints,
                    ),
                ),
                supported = true,
                requiresPermission = false,
            )
            gateway.devices.add(device)
            gateway.attached.add(identity)
            return device
        }

        fun build(
            connectTimeoutMs: Long = 1_000,
            printTimeoutMs: Long = 1_000,
        ): UsbPrinterController = UsbPrinterController(
            gateway = gateway,
            connectTimeoutMs = connectTimeoutMs,
            printTimeoutMs = printTimeoutMs,
            clock = { LocalDateTime.of(2026, 10, 31, 8, 0) },
        )
    }

    private fun assertPrinterError(code: String, block: () -> Unit): PrinterException {
        try {
            block()
        } catch (error: PrinterException) {
            assertEquals(code, error.code)
            return error
        }
        throw AssertionError("Diharapkan PrinterException dengan kode $code")
    }

    @Test
    fun `deteksi mengembalikan perangkat USB yang terpasang`() {
        val harness = Harness()
        harness.addPrinter()
        val controller = harness.build()

        val devices = controller.discover()

        assertEquals(1, devices.size)
        assertEquals(identity, devices[0].identity)
        assertEquals(0x04B8, devices[0].vendorId)
        assertEquals(0x0202, devices[0].productId)
        assertTrue(devices[0].interfaces.isNotEmpty())
    }

    @Test
    fun `deteksi tanpa USB host memberi arahan alternatif`() {
        val harness = Harness()
        harness.gateway.supported = false
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.USB_UNSUPPORTED) {
            controller.discover()
        }

        assertTrue(error.message.orEmpty().contains("USB Host"))
    }

    @Test
    fun `status tanpa USB host tidak mengklaim didukung`() {
        val harness = Harness()
        harness.gateway.supported = false
        val controller = harness.build()

        val status = controller.status()

        assertFalse(status.supported)
        assertFalse(status.connected)
        assertTrue(status.message.orEmpty().contains("USB Host"))
    }

    @Test
    fun `connect meminta izin lalu membuka transport`() {
        val harness = Harness()
        harness.addPrinter()
        val controller = harness.build()

        val connected = controller.connect(identity)

        assertEquals(1, harness.gateway.permissionRequests)
        assertEquals(1, harness.gateway.transportRequests)
        assertEquals(1, harness.gateway.transports[0].connectCount)
        assertEquals(identity, connected.identity)
        assertTrue(controller.isConnected())
        val status = controller.status()
        assertTrue(status.connected)
        assertEquals(identity, status.identity)
        controller.close()
        assertEquals(1, harness.gateway.transports[0].closeCount)
    }

    @Test
    fun `izin yang sudah tersimpan tidak diminta ulang`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()

        controller.connect(identity)

        assertEquals(0, harness.gateway.permissionRequests)
        assertTrue(controller.isConnected())
        controller.close()
    }

    @Test
    fun `izin ditolak tidak membuka transport`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionResult = UsbPermissionResult.DENIED
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.USB_PERMISSION_DENIED) {
            controller.connect(identity)
        }

        assertTrue(error.message.orEmpty().contains("ditolak"))
        assertEquals(0, harness.gateway.transportRequests)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `permintaan izin tanpa jawaban dilaporkan timeout`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionResult = UsbPermissionResult.TIMEOUT
        val controller = harness.build()

        assertPrinterError(PrinterErrorCode.TIMEOUT) {
            controller.connect(identity)
        }

        assertEquals(0, harness.gateway.transportRequests)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `perangkat hilang saat menunggu izin dilaporkan tidak ditemukan`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionRemovesDevice = true
        val controller = harness.build()

        assertPrinterError(PrinterErrorCode.DEVICE_NOT_FOUND) {
            controller.connect(identity)
        }

        assertEquals(0, harness.gateway.transportRequests)
    }

    @Test
    fun `perangkat tidak ditemukan tidak membuka transport`() {
        val harness = Harness()
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.DEVICE_NOT_FOUND) {
            controller.connect(identity)
        }

        assertTrue(error.message.orEmpty().contains("tidak ditemukan"))
        assertEquals(0, harness.gateway.permissionRequests)
        assertEquals(0, harness.gateway.transportRequests)
    }

    @Test
    fun `identitas tidak valid ditolak sebelum izin diminta`() {
        val harness = Harness()
        harness.addPrinter()
        val controller = harness.build()

        assertPrinterError(PrinterErrorCode.INVALID_ADDRESS) {
            controller.connect("printer.usb")
        }

        assertEquals(0, harness.gateway.permissionRequests)
        assertEquals(0, harness.gateway.transportRequests)
    }

    @Test
    fun `perangkat tanpa bulk out dilaporkan tidak didukung`() {
        val harness = Harness()
        harness.addPrinter(endpoints = listOf(bulkIn))
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.UNSUPPORTED_USB) {
            controller.connect(identity)
        }

        assertTrue(error.message.orEmpty().contains("BULK OUT"))
        assertEquals(0, harness.gateway.permissionRequests)
        assertEquals(0, harness.gateway.transportRequests)
    }

    @Test
    fun `koneksi gagal menutup transport dan tidak tersisa hidup`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.transportFactory = {
            FakeTransport(connectFailure = IOException("Device busy"))
        }
        val controller = harness.build()

        assertPrinterError(PrinterErrorCode.CONNECT_FAILED) {
            controller.connect(identity)
        }

        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `koneksi menggantung dihentikan timeout dan transport ditutup`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.transportFactory = { FakeTransport(connectDelayMs = 500) }
        val controller = harness.build(connectTimeoutMs = 50)

        assertPrinterError(PrinterErrorCode.TIMEOUT) {
            controller.connect(identity)
        }

        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `kabel dicabut saat connect dilaporkan DEVICE_DETACHED`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.transportFactory = {
            FakeTransport(connectFailure = IOException("No such device"))
        }
        harness.gateway.attached.clear()
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.DEVICE_DETACHED) {
            controller.connect(identity)
        }

        assertTrue(error.message.orEmpty().contains("terputus"))
        assertEquals(1, harness.gateway.transports[0].closeCount)
    }

    @Test
    fun `transport yang tidak melaporkan terhubung tidak disimpan`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.transportFactory = { FakeTransport(reportsConnected = false) }
        val controller = harness.build()

        assertPrinterError(PrinterErrorCode.CONNECT_FAILED) {
            controller.connect(identity)
        }

        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertFalse(controller.status().connected)
    }

    @Test
    fun `disconnect menutup koneksi dan printer bisa dihubungkan ulang`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()
        controller.connect(identity)

        controller.disconnect()

        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
        assertFalse(controller.status().connected)

        controller.connect(identity)
        assertEquals(2, harness.gateway.transports.size)
        assertTrue(controller.isConnected())
        controller.close()
    }

    @Test
    fun `ganti printer menutup koneksi lama tanpa menghapus konfigurasi`() {
        val harness = Harness()
        harness.addPrinter()
        harness.addPrinter(identity = otherIdentity, name = "Printer Kedua")
        harness.gateway.permissionGranted = true
        val controller = harness.build()

        controller.connect(identity)
        controller.connect(otherIdentity)

        assertEquals(2, harness.gateway.transports.size)
        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertEquals(otherIdentity, controller.status().identity)
        controller.close()
    }

    @Test
    fun `status menutup koneksi saat perangkat USB dicabut`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()
        controller.connect(identity)
        harness.gateway.attached.remove(identity)

        val status = controller.status()

        assertFalse(status.connected)
        assertTrue(status.message.orEmpty().contains("terputus"))
        assertEquals(1, harness.gateway.transports[0].closeCount)
    }

    @Test
    fun `status saat belum terhubung tidak mengklaim CONNECTED`() {
        val harness = Harness()
        harness.addPrinter()
        val controller = harness.build()

        val status = controller.status()

        assertTrue(status.supported)
        assertFalse(status.connected)
        assertTrue(status.message.orEmpty().contains("belum terhubung"))
    }

    @Test
    fun `print mengirim byte ESC POS apa adanya`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()
        controller.connect(identity)
        val payload = byteArrayOf(0x1B, 0x40, 0x54, 0x6F, 0x74, 0x61, 0x6C)

        controller.print(payload)

        assertArrayEquals(payload, harness.gateway.transports[0].written.single())
        controller.close()
    }

    @Test
    fun `print otomatis menghubungkan bila belum terhubung`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()
        val payload = byteArrayOf(0x1B, 0x40, 0x41)

        controller.print(payload, identity)

        assertEquals(1, harness.gateway.transports.size)
        assertArrayEquals(payload, harness.gateway.transports[0].written.single())
        assertTrue(controller.isConnected())
        controller.close()
        assertEquals(1, harness.gateway.transports[0].closeCount)
    }

    @Test
    fun `print tanpa koneksi dan identitas memberi kesalahan jelas`() {
        val harness = Harness()
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.DISCONNECTED) {
            controller.print(byteArrayOf(0x1B, 0x40))
        }

        assertTrue(error.message.orEmpty().contains("belum terhubung"))
        assertEquals(0, harness.gateway.transportRequests)
    }

    @Test
    fun `kabel dicabut saat mencetak dilaporkan DEVICE_DETACHED`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        harness.gateway.transportFactory = {
            FakeTransport(writeFailure = IOException("Device disconnected"))
        }
        val controller = harness.build()
        controller.connect(identity)
        harness.gateway.attached.remove(identity)

        val error = assertPrinterError(PrinterErrorCode.DEVICE_DETACHED) {
            controller.print(byteArrayOf(0x1B, 0x40))
        }

        assertTrue(error.message.orEmpty().contains("Kabel USB terputus"))
        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `kegagalan cetak tanpa cabut dilaporkan PRINT_FAILED`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        harness.gateway.transportFactory = {
            FakeTransport(writeFailure = IOException("Printer error"))
        }
        val controller = harness.build()
        controller.connect(identity)

        val error = assertPrinterError(PrinterErrorCode.PRINT_FAILED) {
            controller.print(byteArrayOf(0x1B, 0x40))
        }

        assertTrue(error.message.orEmpty().contains("Gagal mengirim struk"))
        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `write menggantung dihentikan timeout dan transport ditutup`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        harness.gateway.transportFactory = { FakeTransport(writeDelayMs = 500) }
        val controller = harness.build(printTimeoutMs = 50)
        controller.connect(identity)

        assertPrinterError(PrinterErrorCode.TIMEOUT) {
            controller.print(byteArrayOf(0x1B, 0x40))
        }

        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
        assertFalse(controller.status().connected)
    }

    @Test
    fun `print ke identitas lain menutup koneksi lama`() {
        val harness = Harness()
        harness.addPrinter()
        harness.addPrinter(identity = otherIdentity, name = "Printer Kedua")
        harness.gateway.permissionGranted = true
        val controller = harness.build()
        controller.connect(identity)
        val payload = byteArrayOf(0x1B, 0x40, 0x42)

        controller.print(payload, otherIdentity)

        assertEquals(1, harness.gateway.transports[0].closeCount)
        assertArrayEquals(payload, harness.gateway.transports[1].written.single())
        assertEquals(otherIdentity, controller.status().identity)
        controller.close()
    }

    @Test
    fun `payload kosong atau terlalu besar ditolak tanpa menulis`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()
        controller.connect(identity)

        assertPrinterError(PrinterErrorCode.INVALID_PAYLOAD) {
            controller.print(ByteArray(0))
        }
        assertPrinterError(PrinterErrorCode.INVALID_PAYLOAD) {
            controller.print(ByteArray(UsbPrinterController.MAX_PRINT_BYTES + 1))
        }

        assertTrue(harness.gateway.transports[0].written.isEmpty())
        controller.close()
    }

    @Test
    fun `tes cetak memakai ESC POS dan label USB OTG`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()
        controller.connect(identity)

        controller.testPrint(58)

        val ticket = harness.gateway.transports[0].written.single()
        val text = String(ticket, Charsets.US_ASCII)
        assertEquals(0x1B, ticket[0].toInt() and 0xFF)
        assertEquals(0x40, ticket[1].toInt() and 0xFF)
        assertTrue(text.contains("Tes Printer USB OTG"))
        assertTrue(text.contains("31-10-2026 08:00"))
        controller.close()
    }

    @Test
    fun `tes cetak menyambungkan printer yang belum terhubung`() {
        val harness = Harness()
        harness.addPrinter()
        harness.gateway.permissionGranted = true
        val controller = harness.build()

        controller.testPrint(80, identity)

        val text = String(harness.gateway.transports[0].written.single(), Charsets.US_ASCII)
        assertTrue(text.contains("Tes Printer USB OTG"))
        assertTrue(text.contains("-".repeat(48)))
        controller.close()
    }
}
