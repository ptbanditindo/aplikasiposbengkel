package com.bengkelpos.radiator.printer

import java.util.Locale

/** Informasi interface USB yang dibaca dari descriptor perangkat. */
data class UsbEndpointInfo(
    val address: Int,
    val direction: UsbEndpointDirection,
    val type: UsbEndpointType,
    val maxPacketSize: Int,
)

data class UsbInterfaceInfo(
    val index: Int,
    val interfaceClass: Int,
    val interfaceSubclass: Int,
    val interfaceProtocol: Int,
    val endpoints: List<UsbEndpointInfo>,
)

/**
 * Perangkat USB yang terpasang. [identity] dipakai sebagai alamat konfigurasi
 * karena ID internal Android berubah setiap kali kabel dicabut/dipasang.
 */
data class UsbPrinterDevice(
    val identity: String,
    val name: String,
    val vendorId: Int,
    val productId: Int,
    val interfaces: List<UsbInterfaceInfo>,
    val supported: Boolean,
    val requiresPermission: Boolean,
)

data class UsbPrinterStatus(
    val supported: Boolean,
    val connected: Boolean,
    val identity: String?,
    val name: String?,
    val message: String?,
)

enum class UsbEndpointDirection { IN, OUT }

enum class UsbEndpointType { CONTROL, ISOCHRONOUS, BULK, INTERRUPT }

enum class UsbPermissionResult { GRANTED, DENIED, TIMEOUT }

/**
 * Seleksi interface/endpoint dan identitas perangkat USB. Logika ini murni
 * Kotlin agar dapat diuji tanpa perangkat maupun framework Android.
 *
 * Aplikasi hanya mendukung printer yang mengekspos endpoint BULK OUT untuk
 * data ESC/POS. Printer dengan driver khusus atau protokol vendor lain tidak
 * dianggap kompatibel.
 */
object UsbPrinterSupport {

    private val IDENTITY = Regex(
        "^usb:([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})$",
        RegexOption.IGNORE_CASE,
    )
    private const val USB_CLASS_PRINTER = 7

    fun identity(vendorId: Int, productId: Int): String =
        String.format(Locale.ROOT, "usb:%04x:%04x", vendorId and 0xFFFF, productId and 0xFFFF)

    fun normalizeIdentity(value: String?): String? {
        val trimmed = value?.trim().orEmpty()
        val match = IDENTITY.matchEntire(trimmed) ?: return null
        val vendor = match.groupValues[1].toInt(16)
        val product = match.groupValues[2].toInt(16)
        return identity(vendor, product)
    }

    fun supportsBulkOut(device: UsbPrinterDevice): Boolean =
        selectInterface(device.interfaces) != null

    /** Interface kelas printer diutamakan; jika tidak ada, interface apa pun dengan BULK OUT. */
    fun selectInterface(interfaces: List<UsbInterfaceInfo>): UsbInterfaceInfo? {
        val candidates = interfaces.filter { iface ->
            iface.endpoints.any {
                it.direction == UsbEndpointDirection.OUT &&
                    it.type == UsbEndpointType.BULK
            }
        }
        return candidates.firstOrNull { it.interfaceClass == USB_CLASS_PRINTER }
            ?: candidates.firstOrNull()
    }

    fun selectBulkOutEndpoint(iface: UsbInterfaceInfo): UsbEndpointInfo? =
        iface.endpoints.firstOrNull {
            it.direction == UsbEndpointDirection.OUT &&
                it.type == UsbEndpointType.BULK
        }
}
