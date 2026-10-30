package com.bengkelpos.radiator.backup

import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

data class SavedBackup(
    val displayName: String,
    val location: String,
    val shareUri: Uri,
)

/**
 * Menyimpan file backup ke folder Unduhan dan menyiapkan salinan untuk dibagikan.
 *
 * Ref: T-03 - WebView tidak bisa menulis blob download sendiri, jadi file
 * ditulis dari sisi native lalu ukurannya diverifikasi sebelum dilaporkan sukses.
 */
object BackupStore {

    private const val MIME_TYPE = "application/x-sqlite3"
    private const val SHARE_DIR = "backup-share"

    fun save(context: Context, bytes: ByteArray, displayName: String): SavedBackup {
        if (bytes.isEmpty()) {
            throw IOException("Isi backup kosong.")
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            saveToMediaStore(context, bytes, displayName)
        } else {
            saveToLegacyDownloads(context, bytes, displayName)
        }
        val shareUri = cacheForSharing(context, bytes, displayName)
        return SavedBackup(
            displayName = displayName,
            location = "folder Unduhan",
            shareUri = shareUri,
        )
    }

    private fun saveToMediaStore(context: Context, bytes: ByteArray, displayName: String) {
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, displayName)
            put(MediaStore.Downloads.MIME_TYPE, MIME_TYPE)
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Tidak dapat membuat file di folder Unduhan.")

        try {
            resolver.openOutputStream(uri)?.use { output ->
                output.write(bytes)
                output.flush()
            } ?: throw IOException("Tidak dapat menulis file backup.")

            val written = resolver.openFileDescriptor(uri, "r")?.use { it.statSize } ?: -1L
            if (written != bytes.size.toLong()) {
                throw IOException("Ukuran file backup tidak sesuai.")
            }

            values.clear()
            values.put(MediaStore.Downloads.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
        } catch (error: Throwable) {
            resolver.delete(uri, null, null)
            throw error
        }
    }

    private fun saveToLegacyDownloads(context: Context, bytes: ByteArray, displayName: String) {
        val directory = Environment.getExternalStoragePublicDirectory(
            Environment.DIRECTORY_DOWNLOADS
        )
        if (!directory.exists() && !directory.mkdirs()) {
            throw IOException("Folder Unduhan tidak dapat dibuat.")
        }
        val file = uniqueFile(directory, displayName)
        FileOutputStream(file).use { output ->
            output.write(bytes)
            output.flush()
            output.fd.sync()
        }
        if (file.length() != bytes.size.toLong()) {
            file.delete()
            throw IOException("Ukuran file backup tidak sesuai.")
        }
        MediaScannerConnection.scanFile(
            context,
            arrayOf(file.absolutePath),
            arrayOf(MIME_TYPE),
            null,
        )
    }

    private fun uniqueFile(directory: File, displayName: String): File {
        val base = displayName.removeSuffix(".db")
        var candidate = File(directory, displayName)
        var index = 1
        while (candidate.exists()) {
            candidate = File(directory, "${base}_$index.db")
            index += 1
        }
        return candidate
    }

    private fun cacheForSharing(context: Context, bytes: ByteArray, displayName: String): Uri {
        val directory = File(context.cacheDir, SHARE_DIR)
        if (!directory.exists() && !directory.mkdirs()) {
            throw IOException("Folder sementara untuk berbagi tidak dapat dibuat.")
        }
        val file = File(directory, displayName)
        FileOutputStream(file).use { output ->
            output.write(bytes)
            output.flush()
        }
        if (file.length() != bytes.size.toLong()) {
            file.delete()
            throw IOException("Salinan file untuk berbagi tidak lengkap.")
        }
        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file,
        )
    }
}
