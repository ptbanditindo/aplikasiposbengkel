package com.bengkelpos.radiator

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExternalLinkPolicyTest {

    @Test
    fun `tautan wa me dan api whatsapp diterima`() {
        assertTrue(ExternalLinkPolicy.isAllowed("https://wa.me/6281234567890?text=Halo"))
        assertTrue(
            ExternalLinkPolicy.isAllowed(
                "https://api.whatsapp.com/send?phone=6281234567890",
            ),
        )
        assertTrue(ExternalLinkPolicy.isAllowed("HTTPS://WA.ME/6281234567890"))
    }

    @Test
    fun `host lain dan kemiripan domain ditolak`() {
        assertFalse(ExternalLinkPolicy.isAllowed("https://whatsapp.com"))
        assertFalse(ExternalLinkPolicy.isAllowed("https://evil.com/wa.me"))
        assertFalse(ExternalLinkPolicy.isAllowed("https://wa.me.evil.com"))
        assertFalse(ExternalLinkPolicy.isAllowed("https://wa.me@evil.com"))
        assertFalse(ExternalLinkPolicy.isAllowed("https://api.whatsapp.com.evil.com"))
    }

    @Test
    fun `skema selain https ditolak`() {
        assertFalse(ExternalLinkPolicy.isAllowed("http://wa.me/6281234567890"))
        assertFalse(ExternalLinkPolicy.isAllowed("javascript:alert(1)"))
        assertFalse(ExternalLinkPolicy.isAllowed("file:///data/local/tmp/x"))
        assertFalse(ExternalLinkPolicy.isAllowed("whatsapp://send?text=Halo"))
        assertFalse(ExternalLinkPolicy.isAllowed("ftp://wa.me/x"))
    }

    @Test
    fun `tautan kosong atau tidak valid ditolak`() {
        assertFalse(ExternalLinkPolicy.isAllowed(null))
        assertFalse(ExternalLinkPolicy.isAllowed(""))
        assertFalse(ExternalLinkPolicy.isAllowed("   "))
        assertFalse(ExternalLinkPolicy.isAllowed("bukan url"))
    }
}
