package com.bengkelpos.radiator.printer

/**
 * Kesalahan printer dengan kode stabil yang diteruskan ke WebView.
 *
 * Kode dipakai adapter JavaScript untuk memberi pesan yang dapat ditindaklanjuti;
 * pesan tidak boleh memuat token, PIN, atau isi transaksi.
 */
class PrinterException(
    val code: String,
    message: String,
    cause: Throwable? = null,
) : Exception(message, cause)

object PrinterErrorCode {
    const val PERMISSION_DENIED = "PERMISSION_DENIED"
    const val BLUETOOTH_DISABLED = "BLUETOOTH_DISABLED"
    const val BLUETOOTH_UNSUPPORTED = "BLUETOOTH_UNSUPPORTED"
    const val DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    const val DEVICE_NOT_PAIRED = "DEVICE_NOT_PAIRED"
    const val UNSUPPORTED_SPP = "UNSUPPORTED_SPP"
    const val INVALID_ADDRESS = "INVALID_ADDRESS"
    const val CONNECT_FAILED = "CONNECT_FAILED"
    const val TIMEOUT = "TIMEOUT"
    const val DISCONNECTED = "DISCONNECTED"
    const val PRINT_FAILED = "PRINT_FAILED"
    const val INVALID_PAYLOAD = "INVALID_PAYLOAD"
    const val INVALID_IP = "INVALID_IP"
    const val INVALID_PORT = "INVALID_PORT"
    const val CONNECTION_REFUSED = "CONNECTION_REFUSED"
    const val NETWORK_UNREACHABLE = "NETWORK_UNREACHABLE"
    const val DISCOVERY_FAILED = "DISCOVERY_FAILED"
    const val USB_UNSUPPORTED = "USB_UNSUPPORTED"
    const val UNSUPPORTED_USB = "UNSUPPORTED_USB"
    const val DEVICE_DETACHED = "DEVICE_DETACHED"
    const val USB_PERMISSION_DENIED = "USB_PERMISSION_DENIED"
    const val SYSTEM_PRINT_UNAVAILABLE = "SYSTEM_PRINT_UNAVAILABLE"
    const val SYSTEM_PRINT_FAILED = "SYSTEM_PRINT_FAILED"
}
