package com.bengkelpos.radiator.pin

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.security.SecureRandom

class PinStorageException(cause: Throwable) : Exception(cause)

/**
 * Menyimpan hash PIN, jumlah percobaan gagal, dan status kunci di
 * EncryptedSharedPreferences. Semua nilai ditulis dengan commit() agar
 * percobaan gagal tetap tersimpan walau proses aplikasi dimatikan.
 */
class PinStore private constructor(private val prefs: SharedPreferences) {

    fun hasPin(): Boolean = prefs.getString(KEY_PIN_HASH, null) != null

    /**
     * Token instalasi per-perangkat untuk REST API lokal
     * (header X-Install-Token). Disimpan terenkripsi dan tidak pernah
     * ditampilkan ke pengguna.
     */
    fun getOrCreateAdminToken(): String {
        val existing = prefs.getString(KEY_ADMIN_TOKEN, null)
        if (!existing.isNullOrBlank()) return existing
        val token = ByteArray(32)
            .also { SecureRandom().nextBytes(it) }
            .joinToString("") { "%02x".format(it.toInt() and 0xFF) }
        val saved = prefs.edit().putString(KEY_ADMIN_TOKEN, token).commit()
        if (!saved) {
            throw PinStorageException(
                IllegalStateException("Penyimpanan kredensial perangkat gagal.")
            )
        }
        return token
    }

    fun savePin(pin: CharArray) {
        val record = PinHasher.create(pin)
        prefs.edit()
            .putString(KEY_PIN_HASH, record)
            .putInt(KEY_FAILED_ATTEMPTS, 0)
            .putLong(KEY_LOCK_STARTED_WALL, 0L)
            .putLong(KEY_LOCK_STARTED_ELAPSED, 0L)
            .putLong(KEY_LOCK_DURATION, 0L)
            .commit()
    }

    fun verifyPin(pin: CharArray): Boolean {
        val record = prefs.getString(KEY_PIN_HASH, null) ?: return false
        return PinHasher.verify(pin, record)
    }

    fun resetFailures() {
        prefs.edit()
            .putInt(KEY_FAILED_ATTEMPTS, 0)
            .putLong(KEY_LOCK_STARTED_WALL, 0L)
            .putLong(KEY_LOCK_STARTED_ELAPSED, 0L)
            .putLong(KEY_LOCK_DURATION, 0L)
            .commit()
    }

    /** Hapus hash PIN tanpa menyentuh token instalasi atau data aplikasi. */
    fun clearPin() {
        val saved = prefs.edit()
            .remove(KEY_PIN_HASH)
            .putInt(KEY_FAILED_ATTEMPTS, 0)
            .putLong(KEY_LOCK_STARTED_WALL, 0L)
            .putLong(KEY_LOCK_STARTED_ELAPSED, 0L)
            .putLong(KEY_LOCK_DURATION, 0L)
            .commit()
        if (!saved) {
            throw PinStorageException(
                IllegalStateException("Penghapusan PIN gagal disimpan.")
            )
        }
    }

    fun state(): LockoutState = LockoutState(
        failedAttempts = prefs.getInt(KEY_FAILED_ATTEMPTS, 0),
        lockStartedWallMs = prefs.getLong(KEY_LOCK_STARTED_WALL, 0L),
        lockStartedElapsedMs = prefs.getLong(KEY_LOCK_STARTED_ELAPSED, 0L),
        lockDurationMs = prefs.getLong(KEY_LOCK_DURATION, 0L),
    )

    fun registerFailure(clock: LockoutClock): LockoutState {
        val attempts = state().failedAttempts + 1
        val durationMs = LockoutPolicy.lockDurationMs(attempts)
        prefs.edit()
            .putInt(KEY_FAILED_ATTEMPTS, attempts)
            .putLong(KEY_LOCK_STARTED_WALL, if (durationMs > 0L) clock.wallClockMs() else 0L)
            .putLong(KEY_LOCK_STARTED_ELAPSED, if (durationMs > 0L) clock.elapsedRealtimeMs() else 0L)
            .putLong(KEY_LOCK_DURATION, durationMs)
            .commit()
        return state()
    }

    /** Kunci yang sudah habis dihapus, jumlah percobaan gagal tetap disimpan. */
    fun clearExpiredLock(clock: LockoutClock): LockoutState {
        val current = state()
        if (!current.hasLock) return current
        if (current.isLocked(clock.elapsedRealtimeMs(), clock.wallClockMs())) return current
        prefs.edit()
            .putLong(KEY_LOCK_STARTED_WALL, 0L)
            .putLong(KEY_LOCK_STARTED_ELAPSED, 0L)
            .putLong(KEY_LOCK_DURATION, 0L)
            .commit()
        return state()
    }

    companion object {
        private const val FILE_NAME = "bengkel_pin_store"
        const val MASTER_KEY_ALIAS = "bengkelpos_pin_master_key"
        private const val KEY_PIN_HASH = "pin_hash"
        private const val KEY_ADMIN_TOKEN = "admin_token"
        private const val KEY_FAILED_ATTEMPTS = "failed_attempts"
        private const val KEY_LOCK_STARTED_WALL = "lock_started_wall"
        private const val KEY_LOCK_STARTED_ELAPSED = "lock_started_elapsed"
        private const val KEY_LOCK_DURATION = "lock_duration"

        fun open(context: Context): PinStore {
            try {
                val masterKey = MasterKey.Builder(context.applicationContext, MASTER_KEY_ALIAS)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build()
                val prefs = EncryptedSharedPreferences.create(
                    context.applicationContext,
                    FILE_NAME,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
                )
                return PinStore(prefs)
            } catch (error: Exception) {
                throw PinStorageException(error)
            }
        }
    }
}
