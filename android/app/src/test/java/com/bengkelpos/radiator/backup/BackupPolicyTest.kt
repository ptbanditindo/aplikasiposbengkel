package com.bengkelpos.radiator.backup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId
import java.time.ZonedDateTime

class BackupPolicyTest {

    private fun moment(hour: Int, minute: Int): ZonedDateTime =
        ZonedDateTime.of(2026, 10, 30, hour, minute, 0, 0, ZoneId.of("Asia/Jakarta"))

    @Test
    fun `jam tidak valid ditolak`() {
        assertNull(BackupPolicy.normalizeJam("25:00"))
        assertNull(BackupPolicy.normalizeJam("21:60"))
        assertNull(BackupPolicy.normalizeJam(""))
        assertNull(BackupPolicy.normalizeJam(null))
        assertEquals(21 to 0, BackupPolicy.normalizeJam("21:00"))
        assertEquals(7 to 5, BackupPolicy.normalizeJam(" 07:05 "))
    }

    @Test
    fun `format jam memakai default 21 00`() {
        assertEquals("21:00", BackupPolicy.formatJam(null))
        assertEquals("07:05", BackupPolicy.formatJam(7 to 5))
    }

    @Test
    fun `jeda awal menuju jam kirim hari ini`() {
        val delay = BackupPolicy.initialDelayMillis(moment(9, 0), 21, 0)
        assertEquals(12 * 60 * 60 * 1000L, delay)
    }

    @Test
    fun `jam yang sudah lewat dijadwalkan besok`() {
        val delay = BackupPolicy.initialDelayMillis(moment(22, 0), 21, 0)
        assertEquals(23 * 60 * 60 * 1000L, delay)
    }

    @Test
    fun `hanya status ok yang tidak diulang`() {
        assertFalse(BackupPolicy.shouldRetry("ok"))
        assertTrue(BackupPolicy.shouldRetry("failed"))
        assertTrue(BackupPolicy.shouldRetry("busy"))
        assertTrue(BackupPolicy.shouldRetry(null))
    }

    @Test
    fun `kegagalan baca token sementara diulang`() {
        val error = IllegalStateException(
            "Keystore belum tersedia karena perangkat belum dibuka",
        )
        assertEquals(
            BackupPolicy.Decision.RETRY,
            BackupPolicy.tokenFailureDecision(error, 0),
        )
    }

    @Test
    fun `data kredensial rusak tidak diulang terus-menerus`() {
        val error = IllegalStateException(
            "javax.crypto.AEADBadTagException: data corrupt",
        )
        assertEquals(
            BackupPolicy.Decision.GIVE_UP,
            BackupPolicy.tokenFailureDecision(error, 0),
        )
    }

    @Test
    fun `percobaan sementara dibatasi jumlahnya`() {
        val error = IllegalStateException("sementara tidak tersedia")
        assertEquals(
            BackupPolicy.Decision.RETRY,
            BackupPolicy.tokenFailureDecision(error, BackupPolicy.MAX_ATTEMPTS - 1),
        )
        assertEquals(
            BackupPolicy.Decision.GIVE_UP,
            BackupPolicy.tokenFailureDecision(error, BackupPolicy.MAX_ATTEMPTS),
        )
    }

    @Test
    fun `kegagalan backend juga dibatasi`() {
        assertEquals(
            BackupPolicy.Decision.RETRY,
            BackupPolicy.backendFailureDecision(0),
        )
        assertEquals(
            BackupPolicy.Decision.GIVE_UP,
            BackupPolicy.backendFailureDecision(BackupPolicy.MAX_ATTEMPTS),
        )
    }
}
