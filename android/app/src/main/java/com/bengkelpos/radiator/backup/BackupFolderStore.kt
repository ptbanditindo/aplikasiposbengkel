package com.bengkelpos.radiator.backup

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import java.io.IOException

data class BackupFolder(
    val uri: String,
    val name: String,
)

/**
 * Folder tujuan backup pilihan pengguna (Storage Access Framework).
 *
 * Izin baca/tulis diambil sekali lewat pemilih folder lalu disimpan sebagai
 * persistable permission, sehingga backup otomatis tetap bisa menulis walau
 * aplikasi sudah ditutup.
 */
object BackupFolderStore {

    private const val PREFS = "bengkel_backup_folder"
    private const val KEY_URI = "tree_uri"
    private const val KEY_NAME = "display_name"
    private const val KEY_COPIED = "last_copied_name"
    private const val MIME_TYPE = "application/x-sqlite3"
    private val BACKUP_NAME = Regex("bengkel_radiator_[0-9_]+\\.db")

    fun isValidBackupName(name: String): Boolean = BACKUP_NAME.matches(name)

    fun save(context: Context, uri: Uri, name: String?) {
        val label = name?.trim().takeUnless { it.isNullOrEmpty() }
            ?: displayName(context, uri)
            ?: "Folder backup"
        prefs(context).edit()
            .putString(KEY_URI, uri.toString())
            .putString(KEY_NAME, label)
            .remove(KEY_COPIED)
            .commit()
    }

    fun state(context: Context): BackupFolder? = current(context)

    fun current(context: Context): BackupFolder? {
        val appContext = context.applicationContext
        val prefs = prefs(appContext)
        val raw = prefs.getString(KEY_URI, null) ?: return null
        val uri = runCatching { Uri.parse(raw) }.getOrNull()
        if (uri == null) {
            clear(appContext)
            return null
        }
        val granted = appContext.contentResolver.persistedUriPermissions
            .any { it.uri == uri && it.isWritePermission }
        if (!granted) {
            clear(appContext)
            return null
        }
        val name = prefs.getString(KEY_NAME, null) ?: "Folder backup"
        return BackupFolder(raw, name)
    }

    fun save(context: Context, bytes: ByteArray, displayName: String): SavedBackup {
        if (bytes.isEmpty()) {
            throw IOException("Isi backup kosong.")
        }
        val folder = current(context)
            ?: throw IOException("Folder backup belum dipilih.")
        val resolver = context.applicationContext.contentResolver
        val tree = Uri.parse(folder.uri)
        val treeId = runCatching { DocumentsContract.getTreeDocumentId(tree) }
            .getOrElse { throw IOException("Folder backup tidak dapat dibaca.") }
        val parent = DocumentsContract.buildDocumentUriUsingTree(tree, treeId)
        val name = uniqueName(context, tree, treeId, displayName)
        val document = DocumentsContract.createDocument(resolver, parent, MIME_TYPE, name)
            ?: throw IOException("Tidak dapat membuat file di folder backup.")

        try {
            resolver.openOutputStream(document, "w")?.use { output ->
                output.write(bytes)
                output.flush()
            } ?: throw IOException("Tidak dapat menulis file backup.")

            val written = resolver.openFileDescriptor(document, "r")
                ?.use { it.statSize } ?: -1L
            if (written != bytes.size.toLong()) {
                throw IOException("Ukuran file backup tidak sesuai.")
            }
        } catch (error: Throwable) {
            runCatching { DocumentsContract.deleteDocument(resolver, document) }
            throw error
        }

        return SavedBackup(displayName = name, location = folder.name)
    }

    fun wasCopied(context: Context, filename: String): Boolean =
        prefs(context).getString(KEY_COPIED, null) == filename

    fun markCopied(context: Context, filename: String) {
        prefs(context).edit().putString(KEY_COPIED, filename).commit()
    }

    fun displayName(context: Context, uri: Uri): String? {
        val resolver = context.applicationContext.contentResolver
        val documentUri = runCatching {
            DocumentsContract.buildDocumentUriUsingTree(
                uri,
                DocumentsContract.getTreeDocumentId(uri),
            )
        }.getOrDefault(uri)

        val queried = runCatching {
            resolver.query(
                documentUri,
                arrayOf(OpenableColumns.DISPLAY_NAME),
                null,
                null,
                null,
            )?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) else null
            }
        }.getOrNull()
        if (!queried.isNullOrBlank()) return queried

        return uri.lastPathSegment
            ?.substringAfterLast(':')
            ?.substringAfterLast('/')
            ?.takeUnless { it.isBlank() }
    }

    private fun uniqueName(
        context: Context,
        tree: Uri,
        treeId: String,
        displayName: String,
    ): String {
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, treeId)
        val names = runCatching {
            val collected = mutableSetOf<String>()
            context.applicationContext.contentResolver.query(
                children,
                arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME),
                null,
                null,
                null,
            )?.use { cursor ->
                while (cursor.moveToNext()) {
                    cursor.getString(0)?.let(collected::add)
                }
            }
            collected
        }.getOrDefault(emptySet())

        if (displayName !in names) return displayName

        val base = displayName.removeSuffix(".db")
        var index = 1
        while ("${base}_$index.db" in names) {
            index += 1
        }
        return "${base}_$index.db"
    }

    private fun clear(context: Context) {
        prefs(context).edit()
            .remove(KEY_URI)
            .remove(KEY_NAME)
            .remove(KEY_COPIED)
            .commit()
    }

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
