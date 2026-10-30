package com.bengkelpos.radiator.printer

import java.net.Inet6Address
import java.net.InetAddress

/** Validasi alamat IP literal dan port sebelum socket dibuka. */
object NetworkAddress {

    private val IPV4 = Regex("^(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})$")
    private val IPV6_CHARS = Regex("^[0-9A-Fa-f:.]+$")

    fun normalizeIp(value: String?): String? {
        val trimmed = value?.trim().orEmpty()
        if (trimmed.isEmpty() || trimmed.contains('/')) return null
        val match = IPV4.matchEntire(trimmed)
        if (match != null) {
            val parts = match.groupValues.drop(1)
            if (parts.any { it.length > 1 && it.startsWith("0") }) return null
            val octets = parts.map { it.toIntOrNull() ?: return null }
            if (octets.any { it !in 0..255 }) return null
            return octets.joinToString(".")
        }
        // Hostname sengaja ditolak; konfigurasi printer memakai alamat IP literal.
        if (!trimmed.contains(':') || !IPV6_CHARS.matches(trimmed)) return null
        return runCatching {
            if (InetAddress.getByName(trimmed) is Inet6Address) trimmed else null
        }.getOrNull()
    }

    fun normalizePort(value: Int?): Int? = value?.takeIf { it in 1..65535 }
}
