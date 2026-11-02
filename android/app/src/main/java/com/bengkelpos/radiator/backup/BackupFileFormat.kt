package com.bengkelpos.radiator.backup

/**
 * Nama dan MIME berkas backup yang boleh disalin keluar aplikasi.
 *
 * Format database dapat dipulihkan; Excel/CSV hanya untuk dibaca.
 */
object BackupFileFormat {

    const val SQLITE = "application/x-sqlite3"
    const val XLSX =
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    const val ZIP = "application/zip"

    private val NAME = Regex("bengkel_radiator_[0-9_]+(?:_csv)?\\.(?:db|xlsx|zip)")

    fun isValidName(name: String): Boolean = NAME.matches(name)

    fun mimeType(name: String): String = when {
        name.endsWith(".xlsx", ignoreCase = true) -> XLSX
        name.endsWith(".zip", ignoreCase = true) -> ZIP
        else -> SQLITE
    }
}
