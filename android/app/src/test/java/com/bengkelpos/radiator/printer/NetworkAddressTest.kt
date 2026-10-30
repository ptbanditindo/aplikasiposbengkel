package com.bengkelpos.radiator.printer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NetworkAddressTest {

    @Test
    fun `IPv4 valid dinormalisasi dan spasi diabaikan`() {
        assertEquals("192.168.1.9", NetworkAddress.normalizeIp(" 192.168.1.9 "))
        assertEquals("10.0.0.1", NetworkAddress.normalizeIp("10.0.0.1"))
        assertEquals("255.255.255.255", NetworkAddress.normalizeIp("255.255.255.255"))
    }

    @Test
    fun `IPv4 tidak valid ditolak`() {
        assertNull(NetworkAddress.normalizeIp("256.1.1.1"))
        assertNull(NetworkAddress.normalizeIp("192.168.1"))
        assertNull(NetworkAddress.normalizeIp("192.168.1.9.1"))
        assertNull(NetworkAddress.normalizeIp("010.0.0.1"))
        assertNull(NetworkAddress.normalizeIp("192.168.1.-1"))
        assertNull(NetworkAddress.normalizeIp("999.999.999.999"))
    }

    @Test
    fun `hostname dan alamat bersubnet ditolak`() {
        assertNull(NetworkAddress.normalizeIp("printer.local"))
        assertNull(NetworkAddress.normalizeIp("printer-bengkel"))
        assertNull(NetworkAddress.normalizeIp("http://192.168.1.9"))
        assertNull(NetworkAddress.normalizeIp("192.168.1.9/24"))
        assertNull(NetworkAddress.normalizeIp(""))
        assertNull(NetworkAddress.normalizeIp(null))
    }

    @Test
    fun `IPv6 literal diterima`() {
        assertEquals("::1", NetworkAddress.normalizeIp("::1"))
        // Bentuk panjang IPv6 tetap diterima sebagai alamat literal.
        assertEquals("2001:db8::1", NetworkAddress.normalizeIp("2001:db8::1"))
        assertNull(NetworkAddress.normalizeIp("2001:zz::1"))
    }

    @Test
    fun `port hanya 1 sampai 65535`() {
        assertEquals(9100, NetworkAddress.normalizePort(9100))
        assertEquals(1, NetworkAddress.normalizePort(1))
        assertEquals(65535, NetworkAddress.normalizePort(65535))
        assertNull(NetworkAddress.normalizePort(0))
        assertNull(NetworkAddress.normalizePort(-1))
        assertNull(NetworkAddress.normalizePort(65536))
        assertNull(NetworkAddress.normalizePort(null))
    }
}
