package com.bengkelpos.radiator.pin

import android.content.Context
import android.webkit.CookieManager
import android.webkit.WebStorage
import com.bengkelpos.radiator.backend.BackendManager
import java.io.File
import java.security.KeyStore

/**
 * Menghapus seluruh data lokal aplikasi (database, pengaturan, hash PIN, data WebView)
 * beserta kunci Keystore. Dipakai oleh alur "Lupa PIN?" sebelum membuat PIN baru.
 */
object LocalDataResetter {
    private val KEEP_ENTRIES = setOf("lib", "code_cache")

    fun reset(context: Context) {
        val appContext = context.applicationContext

        // Hentikan server lokal lebih dulu: koneksi SQLite harus ditutup sebelum
        // file database dihapus, dan token admin lama tidak boleh dipakai lagi.
        runCatching { BackendManager.stop() }

        runCatching { CookieManager.getInstance().removeAllCookies(null) }
        runCatching { WebStorage.getInstance().deleteAllData() }
        runCatching { deleteKeystoreKey() }

        PinSession.clear()

        val dataDir = File(appContext.applicationInfo.dataDir)
        dataDir.listFiles()?.forEach { entry ->
            if (entry.name !in KEEP_ENTRIES) {
                runCatching { entry.deleteRecursively() }
            }
        }
    }

    private fun deleteKeystoreKey() {
        val keyStore = KeyStore.getInstance("AndroidKeyStore")
        keyStore.load(null)
        if (keyStore.containsAlias(PinStore.MASTER_KEY_ALIAS)) {
            keyStore.deleteEntry(PinStore.MASTER_KEY_ALIAS)
        }
    }
}
