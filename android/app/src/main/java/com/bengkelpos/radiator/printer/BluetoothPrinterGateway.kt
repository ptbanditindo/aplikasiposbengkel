package com.bengkelpos.radiator.printer

/**
 * Batas antara logika printer yang dapat diuji di JVM dan API Bluetooth Android.
 *
 * Gateway sengaja tidak menyediakan operasi unpair. Memutus koneksi hanya
 * menutup socket, sedangkan pasangan Bluetooth tetap tersimpan di perangkat.
 */
interface BluetoothPrinterGateway {
    fun isSupported(): Boolean
    fun isEnabled(): Boolean
    fun runtimePermissions(discovery: Boolean): List<String>
    fun missingPermissions(discovery: Boolean): List<String>
    fun bondedDevices(): List<PrinterDeviceInfo>
    fun discoverAvailable(windowMs: Long): List<PrinterDeviceInfo>
    fun deviceByAddress(address: String): PrinterDeviceInfo?

    /** null bila perangkat tidak mengiklankan UUID; false bila jelas bukan SPP. */
    fun supportsSpp(address: String): Boolean?
    fun createTransport(address: String): BluetoothTransport
}
