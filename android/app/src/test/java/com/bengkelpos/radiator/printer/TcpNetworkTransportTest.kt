package com.bengkelpos.radiator.printer

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicInteger

class TcpNetworkTransportTest {

    private fun localServer(): ServerSocket =
        ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))

    @Test
    fun `byte ESC POS terkirim ke server TCP lokal`() {
        val server = localServer()
        val payload = byteArrayOf(0x1B, 0x40, 0x48, 0x69, 0x0A)
        val received = ByteArrayOutputStream()
        val readCount = AtomicInteger(0)
        val reader = Thread {
            runCatching {
                server.accept().use { client ->
                    val buffer = ByteArray(payload.size)
                    var total = 0
                    while (total < payload.size) {
                        val read = client.getInputStream().read(
                            buffer,
                            total,
                            payload.size - total,
                        )
                        if (read <= 0) break
                        total += read
                    }
                    received.write(buffer, 0, total)
                    readCount.set(total)
                }
            }
        }
        reader.start()

        val transport = TcpNetworkTransport("127.0.0.1", server.localPort, 2000)
        try {
            transport.connect()
            assertTrue(transport.isConnected())
            transport.write(payload)
            reader.join(3000)

            assertEquals(payload.size, readCount.get())
            assertArrayEquals(payload, received.toByteArray())
        } finally {
            transport.close()
            server.close()
        }
    }

    @Test
    fun `close menutup socket dan aman dipanggil berulang`() {
        val server = localServer()
        val transport = TcpNetworkTransport("127.0.0.1", server.localPort, 2000)
        try {
            transport.connect()
            assertTrue(transport.isConnected())
            transport.close()
            assertFalse(transport.isConnected())
            transport.close()
            assertFalse(transport.isConnected())
        } finally {
            transport.close()
            server.close()
        }
    }

    @Test
    fun `tulis setelah close gagal dan tidak crash`() {
        val server = localServer()
        val transport = TcpNetworkTransport("127.0.0.1", server.localPort, 2000)
        try {
            transport.connect()
            transport.close()
            var failed = false
            try {
                transport.write(byteArrayOf(0x1B, 0x40))
            } catch (error: IOException) {
                failed = true
            }
            assertTrue(failed)
        } finally {
            transport.close()
            server.close()
        }
    }

    @Test
    fun `tulis sebelum connect gagal`() {
        val transport = TcpNetworkTransport("127.0.0.1", 9100, 2000)
        var failed = false
        try {
            transport.write(byteArrayOf(0x1B, 0x40))
        } catch (error: IOException) {
            failed = true
        }
        assertTrue(failed)
        transport.close()
    }

    @Test
    fun `port tertutup ditolak dan socket tidak dianggap terhubung`() {
        val server = localServer()
        val port = server.localPort
        server.close()

        val transport = TcpNetworkTransport("127.0.0.1", port, 1000)
        var failed = false
        try {
            transport.connect()
        } catch (error: Throwable) {
            failed = true
        } finally {
            transport.close()
        }
        assertTrue(failed)
        assertFalse(transport.isConnected())
    }
}
