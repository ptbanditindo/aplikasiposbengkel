package com.bengkelpos.radiator.printer

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException
import java.net.ConnectException
import java.net.NoRouteToHostException
import java.time.LocalDateTime

class NetworkPrinterControllerTest {

    private val ip = "192.168.1.9"
    private val otherIp = "10.0.0.5"

    private class FakeDiscovery(
        var supported: Boolean = true,
        val devices: MutableList<NetworkPrinterDevice> = mutableListOf(),
        var failure: Throwable? = null,
    ) : NetworkPrinterDiscovery {
        override fun isSupported(): Boolean = supported
        override fun discover(windowMs: Long): List<NetworkPrinterDevice> {
            failure?.let { throw it }
            return devices.toList()
        }
    }

    private class FakeTransport(
        private val connectDelayMs: Long = 0,
        private val connectFailure: Throwable? = null,
        private val writeFailure: Throwable? = null,
        private val writeDelayMs: Long = 0,
        private val reportsConnected: Boolean = true,
    ) : NetworkTransport {
        @Volatile
        var connected = false

        @Volatile
        var closed = false
        var closeCount = 0
        val written = mutableListOf<ByteArray>()

        override fun connect() {
            if (connectDelayMs > 0) Thread.sleep(connectDelayMs)
            connectFailure?.let { throw it }
            connected = reportsConnected
        }

        override fun write(bytes: ByteArray) {
            if (!connected || closed) throw IOException("Socket tertutup")
            if (writeDelayMs > 0) Thread.sleep(writeDelayMs)
            if (closed) throw IOException("Socket tertutup")
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

    private class Harness {
        val transports = mutableListOf<FakeTransport>()
        val opened = mutableListOf<Pair<String, Int>>()
        var factory: (String, Int, Int) -> FakeTransport = { _, _, _ -> FakeTransport() }

        fun build(
            discovery: NetworkPrinterDiscovery = FakeDiscovery(),
            connectTimeoutMs: Long = 1_000,
            printTimeoutMs: Long = 1_000,
        ): NetworkPrinterController = NetworkPrinterController(
            discovery = discovery,
            transportFactory = { address, port, timeout ->
                opened.add(address to port)
                factory(address, port, timeout).also { transports.add(it) }
            },
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
    fun `koneksi berhasil membuka satu socket dan menyimpan endpoint`() {
        val harness = Harness()
        val controller = harness.build()

        val endpoint = controller.connect(ip, 9100)

        assertEquals(NetworkEndpoint(ip, 9100), endpoint)
        assertEquals(1, harness.transports.size)
        assertTrue(controller.isConnected())
        assertTrue(harness.transports[0].isConnected())
        controller.close()
        assertEquals(1, harness.transports[0].closeCount)
    }

    @Test
    fun `port dari konfigurasi pengguna dipakai bukan asumsi 9100`() {
        val harness = Harness()
        val controller = harness.build()

        controller.connect(ip, 6101)

        assertEquals(listOf(ip to 6101), harness.opened)
        controller.close()
    }

    @Test
    fun `IP tidak valid ditolak sebelum socket dibuka`() {
        val harness = Harness()
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.INVALID_IP) {
            controller.connect("printer.local", 9100)
        }
        assertTrue(error.message.orEmpty().contains("IP"))
        assertTrue(harness.transports.isEmpty())
    }

    @Test
    fun `port tidak valid ditolak sebelum socket dibuka`() {
        val harness = Harness()
        val controller = harness.build()

        assertPrinterError(PrinterErrorCode.INVALID_PORT) {
            controller.connect(ip, 0)
        }
        assertPrinterError(PrinterErrorCode.INVALID_PORT) {
            controller.connect(ip, 70000)
        }
        assertTrue(harness.transports.isEmpty())
    }

    @Test
    fun `koneksi ditolak memberi pesan port RAW yang jelas`() {
        val harness = Harness()
        val controller = harness.build()
        harness.factory = { _, _, _ ->
            FakeTransport(connectFailure = ConnectException("Connection refused"))
        }

        val error = assertPrinterError(PrinterErrorCode.CONNECTION_REFUSED) {
            controller.connect(ip, 9100)
        }

        assertTrue(error.message.orEmpty().contains("9100"))
        assertTrue(error.message.orEmpty().contains("RAW"))
        assertEquals(1, harness.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `alamat tidak terjangkau dilaporkan terpisah`() {
        val harness = Harness()
        val controller = harness.build()
        harness.factory = { _, _, _ ->
            FakeTransport(connectFailure = NoRouteToHostException("No route to host"))
        }

        val error = assertPrinterError(PrinterErrorCode.NETWORK_UNREACHABLE) {
            controller.connect(ip, 9100)
        }

        assertTrue(error.message.orEmpty().contains("jaringan yang sama"))
        assertEquals(1, harness.transports[0].closeCount)
    }

    @Test
    fun `koneksi yang menggantung dihentikan oleh timeout dan socket ditutup`() {
        val harness = Harness()
        val controller = harness.build(connectTimeoutMs = 50)
        harness.factory = { _, _, _ -> FakeTransport(connectDelayMs = 500) }

        assertPrinterError(PrinterErrorCode.TIMEOUT) {
            controller.connect(ip, 9100)
        }

        assertEquals(1, harness.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `socket yang tidak melaporkan terhubung tidak disimpan sebagai CONNECTED`() {
        val harness = Harness()
        val controller = harness.build()
        harness.factory = { _, _, _ -> FakeTransport(reportsConnected = false) }

        assertPrinterError(PrinterErrorCode.CONNECT_FAILED) {
            controller.connect(ip, 9100)
        }

        assertEquals(1, harness.transports[0].closeCount)
        assertFalse(controller.status().connected)
    }

    @Test
    fun `connect ke endpoint sama memakai ulang socket`() {
        val harness = Harness()
        val controller = harness.build()

        controller.connect(ip, 9100)
        controller.connect(ip, 9100)

        assertEquals(1, harness.transports.size)
        controller.close()
    }

    @Test
    fun `connect ke printer lain menutup socket lama tanpa menghapus apa pun`() {
        val harness = Harness()
        val controller = harness.build()

        controller.connect(ip, 9100)
        controller.connect(otherIp, 9100)

        assertEquals(2, harness.transports.size)
        assertEquals(1, harness.transports[0].closeCount)
        assertEquals(otherIp, controller.status().ip)
        controller.close()
    }

    @Test
    fun `print mengirim byte ESC POS apa adanya`() {
        val harness = Harness()
        val controller = harness.build()
        controller.connect(ip, 9100)
        val payload = byteArrayOf(0x1B, 0x40, 0x54, 0x6F, 0x74, 0x61, 0x6C)

        controller.print(payload)

        assertArrayEquals(payload, harness.transports[0].written.single())
    }

    @Test
    fun `print otomatis menghubungkan ulang bila belum terhubung`() {
        val harness = Harness()
        val controller = harness.build()
        val payload = byteArrayOf(0x1B, 0x40, 0x41)

        controller.print(payload, ip, 9100)

        assertEquals(1, harness.transports.size)
        assertArrayEquals(payload, harness.transports[0].written.single())
        assertTrue(controller.isConnected())
        controller.close()
        // Socket hasil auto-reconnect ikut ditutup, tidak bocor.
        assertEquals(1, harness.transports[0].closeCount)
    }

    @Test
    fun `print menghubungkan ulang socket mati tanpa struk ganda`() {
        val harness = Harness()
        val controller = harness.build()
        controller.connect(ip, 9100)
        val dead = harness.transports[0]
        dead.connected = false
        val payload = byteArrayOf(0x1B, 0x40, 0x42)

        controller.print(payload, ip, 9100)

        assertEquals(2, harness.transports.size)
        assertEquals(1, dead.closeCount)
        assertTrue(dead.written.isEmpty())
        assertArrayEquals(payload, harness.transports[1].written.single())
        controller.close()
    }

    @Test
    fun `print tanpa endpoint saat terputus memberi kesalahan jelas`() {
        val harness = Harness()
        val controller = harness.build()

        val error = assertPrinterError(PrinterErrorCode.DISCONNECTED) {
            controller.print(byteArrayOf(0x1B, 0x40))
        }

        assertTrue(error.message.orEmpty().contains("belum terhubung"))
        assertTrue(harness.transports.isEmpty())
    }

    @Test
    fun `print gagal menutup socket dan tidak menyisakan koneksi hidup`() {
        val harness = Harness()
        val controller = harness.build()
        harness.factory = { _, _, _ ->
            FakeTransport(writeFailure = IOException("Broken pipe"))
        }
        controller.connect(ip, 9100)

        assertPrinterError(PrinterErrorCode.PRINT_FAILED) {
            controller.print(byteArrayOf(0x1B, 0x40))
        }

        assertEquals(1, harness.transports[0].closeCount)
        assertFalse(controller.isConnected())
    }

    @Test
    fun `write menggantung dihentikan timeout dan socket ditutup`() {
        val harness = Harness()
        val controller = harness.build(printTimeoutMs = 50)
        harness.factory = { _, _, _ -> FakeTransport(writeDelayMs = 500) }
        controller.connect(ip, 9100)

        assertPrinterError(PrinterErrorCode.TIMEOUT) {
            controller.print(byteArrayOf(0x1B, 0x40))
        }

        assertEquals(1, harness.transports[0].closeCount)
        assertFalse(controller.isConnected())
        assertFalse(controller.status().connected)
    }

    @Test
    fun `disconnect menutup socket tetapi endpoint dapat dihubungkan ulang`() {
        val harness = Harness()
        val controller = harness.build()
        controller.connect(ip, 9100)

        controller.disconnect()

        assertEquals(1, harness.transports[0].closeCount)
        assertFalse(controller.isConnected())
        assertFalse(controller.status().connected)

        controller.connect(ip, 9100)
        assertEquals(2, harness.transports.size)
        assertTrue(controller.isConnected())
        controller.close()
    }

    @Test
    fun `status menutup socket mati dan tidak melaporkan CONNECTED`() {
        val harness = Harness()
        val controller = harness.build()
        controller.connect(ip, 9100)
        harness.transports[0].connected = false

        val status = controller.status()

        assertFalse(status.connected)
        assertTrue(status.message.orEmpty().contains("terputus"))
        assertEquals(1, harness.transports[0].closeCount)
    }

    @Test
    fun `ganti port pada saat print membuat koneksi baru`() {
        val harness = Harness()
        val controller = harness.build()
        controller.connect(ip, 9100)
        val payload = byteArrayOf(0x1B, 0x40, 0x50)

        controller.print(payload, ip, 9101)

        assertEquals(listOf(ip to 9100, ip to 9101), harness.opened)
        assertEquals(1, harness.transports[0].closeCount)
        assertArrayEquals(payload, harness.transports[1].written.single())
        controller.close()
    }

    @Test
    fun `tes cetak memakai ESC POS dan label jaringan`() {
        val harness = Harness()
        val controller = harness.build()
        controller.connect(ip, 9100)

        controller.testPrint(58)

        val ticket = harness.transports[0].written.single()
        val text = String(ticket, Charsets.US_ASCII)
        assertEquals(0x1B, ticket[0].toInt() and 0xFF)
        assertEquals(0x40, ticket[1].toInt() and 0xFF)
        assertTrue(text.contains("Tes Printer Wi-Fi/LAN"))
        assertTrue(text.contains("31-10-2026 08:00"))
    }

    @Test
    fun `payload kosong atau terlalu besar ditolak tanpa menulis`() {
        val harness = Harness()
        val controller = harness.build()
        controller.connect(ip, 9100)

        assertPrinterError(PrinterErrorCode.INVALID_PAYLOAD) {
            controller.print(ByteArray(0))
        }

        assertTrue(harness.transports[0].written.isEmpty())
        controller.close()
    }

    @Test
    fun `discovery tanpa dukungan NSD memberi arahan manual`() {
        val harness = Harness()
        val controller = harness.build(FakeDiscovery(supported = false))

        val error = assertPrinterError(PrinterErrorCode.DISCOVERY_FAILED) {
            controller.discover()
        }

        assertTrue(error.message.orEmpty().contains("manual"))
    }

    @Test
    fun `discovery menyaring alamat atau port tidak valid dan duplikat`() {
        val discovery = FakeDiscovery(
            devices = mutableListOf(
                NetworkPrinterDevice("Kasir", ip, 9100),
                NetworkPrinterDevice("Kasir Duplikat", ip, 9100),
                NetworkPrinterDevice("Hostname", "printer.local", 9100),
                NetworkPrinterDevice("Port Salah", otherIp, 0),
            ),
        )
        val controller = Harness().build(discovery)

        val devices = controller.discover()

        assertEquals(listOf(NetworkPrinterDevice("Kasir", ip, 9100)), devices)
    }

    @Test
    fun `kegagalan discovery dilaporkan sebagai DISCOVERY_FAILED`() {
        val discovery = FakeDiscovery(failure = IOException("NSD mati"))
        val controller = Harness().build(discovery)

        assertPrinterError(PrinterErrorCode.DISCOVERY_FAILED) {
            controller.discover()
        }
    }
}
