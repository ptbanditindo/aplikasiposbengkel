package com.bengkelpos.radiator.printer

/**
 * Aturan izin Bluetooth menurut versi Android.
 *
 * API 31+ memakai izin runtime BLUETOOTH_CONNECT/BLUETOOTH_SCAN. API 26-30
 * memakai izin Bluetooth lama (diberikan saat instalasi) dan ACCESS_FINE_LOCATION
 * hanya untuk pemindaian perangkat. Izin lokasi tidak diminta untuk koneksi ke
 * printer yang sudah dipasangkan.
 */
object BluetoothPermissionPolicy {

    const val BLUETOOTH = "android.permission.BLUETOOTH"
    const val BLUETOOTH_ADMIN = "android.permission.BLUETOOTH_ADMIN"
    const val ACCESS_FINE_LOCATION = "android.permission.ACCESS_FINE_LOCATION"
    const val BLUETOOTH_CONNECT = "android.permission.BLUETOOTH_CONNECT"
    const val BLUETOOTH_SCAN = "android.permission.BLUETOOTH_SCAN"

    private const val API_S = 31

    /** Izin runtime yang perlu diminta; izin instalasi tidak diminta ulang. */
    fun runtimePermissions(sdkInt: Int, discovery: Boolean): List<String> {
        if (sdkInt >= API_S) {
            return buildList {
                add(BLUETOOTH_CONNECT)
                if (discovery) add(BLUETOOTH_SCAN)
            }
        }
        return if (discovery) listOf(ACCESS_FINE_LOCATION) else emptyList()
    }

    fun missingRuntimePermissions(
        sdkInt: Int,
        discovery: Boolean,
        isGranted: (String) -> Boolean,
    ): List<String> = runtimePermissions(sdkInt, discovery)
        .filterNot(isGranted)

    fun denialMessage(discovery: Boolean): String =
        if (discovery) {
            "Izin Bluetooth dan lokasi diperlukan untuk mencari printer. " +
                "Pilih Izinkan saat aplikasi meminta akses."
        } else {
            "Izin Bluetooth diperlukan untuk menghubungkan printer. " +
                "Pilih Izinkan saat aplikasi meminta akses."
        }
}
