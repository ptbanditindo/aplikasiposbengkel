package com.bengkelpos.radiator.printer

/** Saluran byte ke printer USB lewat endpoint BULK OUT. */
interface UsbTransport {
    fun connect()
    fun write(bytes: ByteArray)
    fun isConnected(): Boolean
    fun close()
}

/**
 * Akses ke USB Host Android. Implementasi Android memakai UsbManager;
 * implementasi palsu dipakai hanya di unit test JVM.
 */
interface UsbPrinterGateway {
    fun isSupported(): Boolean
    fun devices(): List<UsbPrinterDevice>
    fun deviceByIdentity(identity: String): UsbPrinterDevice?
    fun isAttached(identity: String): Boolean
    fun hasPermission(identity: String): Boolean
    fun requestPermission(identity: String): UsbPermissionResult
    fun createTransport(identity: String): UsbTransport
}
