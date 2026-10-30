package com.bengkelpos.radiator.printer

/** Perangkat Bluetooth yang terpasang atau ditemukan saat pemindaian. */
data class PrinterDeviceInfo(
    val name: String,
    val address: String,
    val paired: Boolean,
)

/** Status koneksi printer Bluetooth yang sedang dipakai aplikasi. */
data class BluetoothPrinterStatus(
    val supported: Boolean,
    val permissionsGranted: Boolean,
    val enabled: Boolean,
    val connected: Boolean,
    val address: String?,
    val name: String?,
    val message: String?,
)
