package com.bengkelpos.radiator.backend

import android.content.Context
import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.zip.ZipInputStream

/**
 * Mengekstrak bengkel_backend.zip (dibuat Gradle dari root repo) ke codeCacheDir.
 * codeCacheDir dipakai karena tidak ikut terhapus saat reset data pengguna,
 * sehingga backend tetap tersedia untuk proses restore.
 */
class BackendInstaller(private val context: Context) {

    fun ensureInstalled(): File {
        val root = File(context.codeCacheDir, ROOT_DIR)
        if (isReady(root)) return root

        root.deleteRecursively()
        if (!root.mkdirs() && !root.isDirectory) {
            throw IOException("Tidak dapat membuat direktori backend.")
        }

        val canonicalRoot = root.canonicalFile
        context.assets.open(ASSET_NAME).use { raw ->
            ZipInputStream(BufferedInputStream(raw)).use { zip ->
                while (true) {
                    val entry = zip.nextEntry ?: break
                    val target = File(root, entry.name).canonicalFile
                    if (!target.path.startsWith(canonicalRoot.path + File.separator)) {
                        throw IOException("Entri zip tidak valid: ${entry.name}")
                    }
                    if (entry.isDirectory) {
                        target.mkdirs()
                    } else {
                        target.parentFile?.mkdirs()
                        FileOutputStream(target).use { out -> zip.copyTo(out) }
                    }
                    zip.closeEntry()
                }
            }
        }

        File(root, VERSION_FILE).writeText(currentVersionTag())
        return root
    }

    private fun isReady(root: File): Boolean {
        if (!root.isDirectory) return false
        val marker = File(root, VERSION_FILE)
        if (!marker.isFile || marker.readText().trim() != currentVersionTag()) return false
        return REQUIRED_ENTRIES.all { File(root, it).isFile }
    }

    @Suppress("DEPRECATION")
    private fun currentVersionTag(): String {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        return "${info.versionName}-${info.longVersionCode}"
    }

    companion object {
        private const val ASSET_NAME = "bengkel_backend.zip"
        private const val ROOT_DIR = "backend"
        private const val VERSION_FILE = "VERSION"
        private val REQUIRED_ENTRIES = listOf(
            "config.py",
            "api/app.py",
            "frontend/index.html",
        )
    }
}
