package com.bengkelpos.radiator

import java.net.URI
import java.util.Locale

/** Hanya tautan WhatsApp resmi yang boleh keluar dari WebView. */
object ExternalLinkPolicy {
    private val WHATSAPP_HOSTS = setOf("wa.me", "api.whatsapp.com")

    fun isAllowed(url: String?): Boolean {
        if (url.isNullOrBlank()) return false
        val parsed = runCatching { URI(url.trim()) }.getOrNull() ?: return false
        if (!"https".equals(parsed.scheme, ignoreCase = true)) return false
        val host = parsed.host?.lowercase(Locale.US) ?: return false
        return host in WHATSAPP_HOSTS
    }
}
