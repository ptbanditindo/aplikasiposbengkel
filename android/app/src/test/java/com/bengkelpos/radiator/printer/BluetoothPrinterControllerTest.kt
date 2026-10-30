package com.bengkelpos.radiator.printer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class BluetoothPrinterControllerTest {

    private val address = "AA:BB:CC:DD:EE:FF"
    private val otherAddress = "11:22:33:44:55:66"

    private class FakeTransport(
        private val connectDelayMs: Long = 0,
        private val connectFailure: Throwable? = null,
        private val writeFailure: Throwable? = null,
    ) : BluetoothTransport {
        @Volatile
        var connected = false
        var closeCount = 0
        var closed = false
        val written = mutableListOf<ByteArray>()

        override fun connect() {
            if (connectDelayMs > 0) Thread.sleep(connectDelayMs)
            connectFailure?.let { throw it }
            connected = true
        }

        override fun write(bytes: ByteArray) {
            if (!connected) throw IOException("Socket tertutup")
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
        var enabled: Boolean = true,
        var missing: List<String> = emptyList(),
        val bonded: MutableList<PrinterDeviceInfo> = mutableListOf(),
        var discovered: MutableList<PrinterDeviceInfo> = mutableListOf(),
        var sppSupported: Boolean? = true,
        private val transportFactory: () -> FakeTransport = { FakeTransport() },
    ) : BluetoothPrinterGateway {
        val transports = mutableListOf<FakeTransport>()

        override fun isSupported(): Boolean = supported
        override fun isEnabled(): Boolean = enabled
        override fun runtimePermissions(discovery: Boolean): List<String> = emptyList()
        override fun missingPermissions(discovery: Boolean): List<String> = missing
        override fun bondedDevices(): List<PrinterDeviceInfo> = bonded.toList()
        override fun discoverAvailable(windowMs: Long): List<PrinterDeviceInfo> =
            discovered.toList()

        override fun deviceByAddress(address: String): PrinterDeviceInfo? =
            bonded.find { it.address == address }

        override fun supportsSpp(address: String): Boolean? = sppSupported

        override fun createTransport(address: String): BluetoothTransport {
            val transport = transportFactory()
            transports.add(transport)
            return transport
        }
    }

    private fun pairedDevice(
        address: String = this.address,
        name: String = "Printer Thermal",
        paired: Boolean = true,
    ) = PrinterDeviceInfo(name, address, paired)

    private fun assertPrinterError(expectedCode: String, block: () -> Unit) {
        val error = try {
            block()
            null
        } catch (caught: PrinterException) {
            caught
        }
        assertNotNull("Kesalahan printer tidak dilempar", error)
        assertEquals(expectedCode, error!!.code)
    }

    @Test
    fun `koneksi berhasil baru tercatat setelah transport terhubung`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)

        val device = controller.connect(address)

        assertEquals(address, device.address)
        assertEquals(1, gateway.transports.size)
        assertTrue(gateway.transports[0].connected)
        assertTrue(controller.isConnected())
        val status = controller.status()
        assertTrue(status.connected)
        assertEquals(address, status.address)
    }

    @Test
    fun `perangkat tidak ditemukan memberi pesan jelas`() {
        val gateway = FakeGateway()
        val controller = BluetoothPrinterController(gateway)

        assertPrinterError(PrinterErrorCode.DEVICE_NOT_FOUND) {
            controller.connect(address)
        }
        assertFalse(controller.isConnected())
    }

    @Test
    fun `alamat tidak valid ditolak sebelum membuka socket`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)

        assertPrinterError(PrinterErrorCode.INVALID_ADDRESS) {
            controller.connect("bukan-mac")
        }
        assertTrue(gateway.transports.isEmpty())
    }

    @Test
    fun `printer yang belum dipasangkan tidak dibuka socketnya`() {
        val gateway = FakeGateway(
            bonded = mutableListOf(pairedDevice(paired = false)),
        )
        val controller = BluetoothPrinterController(gateway)

        assertPrinterError(PrinterErrorCode.DEVICE_NOT_PAIRED) {
            controller.connect(address)
        }
        assertTrue(gateway.transports.isEmpty())
    }

    @Test
    fun `printer non SPP ditolak dengan pesan batasan`() {
        val gateway = FakeGateway(
            bonded = mutableListOf(pairedDevice()),
            sppSupported = false,
        )
        val controller = BluetoothPrinterController(gateway)

        assertPrinterError(PrinterErrorCode.UNSUPPORTED_SPP) {
            controller.connect(address)
        }
        assertTrue(gateway.transports.isEmpty())
    }

    @Test
    fun `kegagalan koneksi menutup socket`() {
        val gateway = FakeGateway(
            bonded = mutableListOf(pairedDevice()),
            transportFactory = { FakeTransport(connectFailure = IOException("gagal")) },
        )
        val controller = BluetoothPrinterController(gateway)

        assertPrinterError(PrinterErrorCode.CONNECT_FAILED) {
            controller.connect(address)
        }
        assertEquals(1, gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `timeout koneksi menutup socket dan tidak menyisakan koneksi`() {
        val gateway = FakeGateway(
            bonded = mutableListOf(pairedDevice()),
            transportFactory = { FakeTransport(connectDelayMs = 400) },
        )
        val controller = BluetoothPrinterController(
            gateway,
            connectTimeoutMs = 50,
        )

        assertPrinterError(PrinterErrorCode.TIMEOUT) {
            controller.connect(address)
        }
        assertEquals(1, gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `disconnect menutup socket tanpa menghapus pasangan`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)
        controller.connect(address)

        controller.disconnect()

        assertEquals(1, gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
        assertTrue(gateway.bondedDevices().any { it.address == address })
        assertTrue(gateway.bondedDevices().first().paired)
    }

    @Test
    fun `disconnect saat belum terhubung tetap aman`() {
        val controller = BluetoothPrinterController(FakeGateway())
        controller.disconnect()
        assertFalse(controller.isConnected())
    }

    @Test
    fun `reconnect membuka transport baru`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)

        controller.connect(address)
        controller.disconnect()
        controller.connect(address)

        assertEquals(2, gateway.transports.size)
        assertTrue(gateway.transports[1].connected)
        assertTrue(controller.isConnected())
    }

    @Test
    fun `print mengirim byte apa adanya`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)
        controller.connect(address)
        val payload = byteArrayOf(0x1B, 0x40, 0x41, 0x0A)

        controller.print(payload)

        assertEquals(1, gateway.transports[0].written.size)
        assertTrue(payload.contentEquals(gateway.transports[0].written[0]))
    }

    @Test
    fun `print gagal menutup socket dan memberi kode kegagalan`() {
        val gateway = FakeGateway(
            bonded = mutableListOf(pairedDevice()),
            transportFactory = { FakeTransport(writeFailure = IOException("putus")) },
        )
        val controller = BluetoothPrinterController(gateway)
        controller.connect(address)

        assertPrinterError(PrinterErrorCode.PRINT_FAILED) {
            controller.print(byteArrayOf(0x41))
        }
        assertEquals(1, gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `print saat belum terhubung memberi kode disconnected`() {
        val controller = BluetoothPrinterController(FakeGateway())

        assertPrinterError(PrinterErrorCode.DISCONNECTED) {
            controller.print(byteArrayOf(0x41))
        }
    }

    @Test
    fun `payload kosong atau terlalu besar ditolak`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)
        controller.connect(address)

        assertPrinterError(PrinterErrorCode.INVALID_PAYLOAD) {
            controller.print(ByteArray(0))
        }
        assertPrinterError(PrinterErrorCode.INVALID_PAYLOAD) {
            controller.print(ByteArray(BluetoothPrinterController.MAX_PRINT_BYTES + 1))
        }
        assertTrue(gateway.transports[0].written.isEmpty())
    }

    @Test
    fun `status melaporkan unsupported, izin, dan bluetooth nonaktif`() {
        val unsupported = BluetoothPrinterController(FakeGateway(supported = false))
        val unsupportedStatus = unsupported.status()
        assertFalse(unsupportedStatus.supported)
        assertTrue(unsupportedStatus.message!!.contains("tidak memiliki Bluetooth"))

        val noPermission = BluetoothPrinterController(
            FakeGateway(
                missing = listOf(BluetoothPermissionPolicy.BLUETOOTH_CONNECT),
            ),
        )
        val permissionStatus = noPermission.status()
        assertFalse(permissionStatus.permissionsGranted)
        assertTrue(permissionStatus.message!!.contains("Izin Bluetooth"))

        val disabled = BluetoothPrinterController(FakeGateway(enabled = false))
        val disabledStatus = disabled.status()
        assertFalse(disabledStatus.enabled)
        assertTrue(disabledStatus.message!!.contains("nonaktif"))
    }

    @Test
    fun `discover menolak saat izin belum diberikan`() {
        val controller = BluetoothPrinterController(
            FakeGateway(
                missing = listOf(BluetoothPermissionPolicy.BLUETOOTH_SCAN),
            ),
        )

        assertPrinterError(PrinterErrorCode.PERMISSION_DENIED) {
            controller.discover()
        }
    }

    @Test
    fun `discover menggabungkan perangkat terpasang tanpa duplikat`() {
        val gateway = FakeGateway(
            bonded = mutableListOf(pairedDevice()),
            discovered = mutableListOf(
                pairedDevice(paired = false),
                pairedDevice(address = otherAddress, name = "Printer Kedua", paired = false),
            ),
        )
        val controller = BluetoothPrinterController(gateway)

        val devices = controller.discover()

        assertEquals(2, devices.size)
        val first = devices.first { it.address == address }
        val second = devices.first { it.address == otherAddress }
        assertTrue(first.paired)
        assertFalse(second.paired)
    }

    @Test
    fun `status mendeteksi koneksi yang terputus`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)
        controller.connect(address)
        gateway.transports[0].connected = false

        val status = controller.status()

        assertFalse(status.connected)
        assertTrue(status.message!!.contains("terputus"))
        assertPrinterError(PrinterErrorCode.DISCONNECTED) {
            controller.print(byteArrayOf(0x41))
        }
    }

    @Test
    fun `test print mengirim byte ESC POS`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)
        controller.connect(address)

        controller.testPrint(58)

        val sent = gateway.transports[0].written.single()
        assertEquals(0x1B, sent[0].toInt() and 0xFF)
        assertEquals(0x40, sent[1].toInt() and 0xFF)
        assertTrue(
            String(sent, Charsets.US_ASCII).contains("BENGKELPOS RADIATOR"),
        )
    }

    @Test
    fun `close menutup socket aktif`() {
        val gateway = FakeGateway(bonded = mutableListOf(pairedDevice()))
        val controller = BluetoothPrinterController(gateway)
        controller.connect(address)

        controller.close()

        assertEquals(1, gateway.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }
}
