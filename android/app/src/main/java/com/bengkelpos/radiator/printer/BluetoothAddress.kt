package com.bengkelpos.radiator.printer

/** Validasi alamat MAC Bluetooth sebelum dipakai untuk membuka socket. */
object BluetoothAddress {

    private val PATTERN = Regex("^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")

    fun normalize(value: String?): String? {
        val trimmed = value?.trim().orEmpty()
        if (!PATTERN.matches(trimmed)) return null
        return trimmed.uppercase()
    }
}
