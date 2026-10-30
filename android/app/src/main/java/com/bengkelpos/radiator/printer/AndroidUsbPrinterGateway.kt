package com.bengkelpos.radiator.printer

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Build
import androidx.core.content.ContextCompat
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * USB Host Android untuk printer ESC/POS.
 *
 * Deteksi memakai UsbManager. Izin diminta lewat dialog sistem dan hasilnya
 * ditangkap broadcast lokal aplikasi. Tidak ada izin runtime Android tambahan
 * yang dibutuhkan, dan tidak ada driver proprietary yang diimplementasikan:
 * hanya perangkat dengan endpoint BULK OUT yang dapat dipakai.
 */
class AndroidUsbPrinterGateway(
    private val activity: Activity,
) : UsbPrinterGateway {

    private val usbManager: UsbManager? =
        activity.getSystemService(Context.USB_SERVICE) as? UsbManager

    private val permissionAction = "${activity.packageName}.USB_PERMISSION"

    override fun isSupported(): Boolean =
        usbManager != null &&
            activity.packageManager.hasSystemFeature(PackageManager.FEATURE_USB_HOST)

    override fun devices(): List<UsbPrinterDevice> =
        usbManager?.deviceList?.values
            ?.map(::describe)
            ?.sortedBy { it.identity }
            .orEmpty()

    override fun deviceByIdentity(identity: String): UsbPrinterDevice? =
        findDevice(identity)?.let(::describe)

    override fun isAttached(identity: String): Boolean = findDevice(identity) != null

    override fun hasPermission(identity: String): Boolean {
        val manager = usbManager ?: return false
        val device = findDevice(identity) ?: return false
        return manager.hasPermission(device)
    }

    override fun requestPermission(identity: String): UsbPermissionResult {
        val manager = usbManager ?: return UsbPermissionResult.DENIED
        val device = findDevice(identity) ?: return UsbPermissionResult.DENIED
        if (manager.hasPermission(device)) return UsbPermissionResult.GRANTED

        val answered = CountDownLatch(1)
        val granted = AtomicBoolean(false)
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.action != permissionAction) return
                if (intent.getParcelableExtra<UsbDevice>(UsbManager.EXTRA_DEVICE)
                        ?.deviceId != device.deviceId
                ) {
                    return
                }
                granted.set(
                    intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false),
                )
                answered.countDown()
            }
        }

        ContextCompat.registerReceiver(
            activity,
            receiver,
            IntentFilter(permissionAction),
            ContextCompat.RECEIVER_NOT_EXPORTED,
        )
        return try {
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    PendingIntent.FLAG_MUTABLE
                } else {
                    0
                }
            val pending = PendingIntent.getBroadcast(
                activity,
                0,
                Intent(permissionAction).setPackage(activity.packageName),
                flags,
            )
            activity.runOnUiThread {
                runCatching { manager.requestPermission(device, pending) }
            }
            if (!answered.await(PERMISSION_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                UsbPermissionResult.TIMEOUT
            } else if (granted.get()) {
                UsbPermissionResult.GRANTED
            } else {
                UsbPermissionResult.DENIED
            }
        } catch (error: InterruptedException) {
            Thread.currentThread().interrupt()
            UsbPermissionResult.TIMEOUT
        } finally {
            runCatching { activity.unregisterReceiver(receiver) }
        }
    }

    override fun createTransport(identity: String): UsbTransport {
        val manager = usbManager
            ?: throw PrinterException(
                PrinterErrorCode.USB_UNSUPPORTED,
                "USB Host tidak tersedia di perangkat ini.",
            )
        val device = findDevice(identity)
            ?: throw PrinterException(
                PrinterErrorCode.DEVICE_NOT_FOUND,
                "Perangkat USB tidak ditemukan atau sudah dicabut.",
            )
        val descriptor = describe(device)
        val ifaceInfo = UsbPrinterSupport.selectInterface(descriptor.interfaces)
            ?: throw PrinterException(
                PrinterErrorCode.UNSUPPORTED_USB,
                "Perangkat USB ini tidak menyediakan endpoint BULK OUT untuk " +
                    "ESC/POS. Printer yang membutuhkan driver khusus tidak " +
                    "didukung aplikasi ini.",
            )
        val endpointIndex = ifaceInfo.endpoints.indexOfFirst {
            it.direction == UsbEndpointDirection.OUT &&
                it.type == UsbEndpointType.BULK
        }
        val usbInterface = device.getInterface(ifaceInfo.index)
        return UsbBulkTransport(
            usbManager = manager,
            device = device,
            usbInterface = usbInterface,
            endpoint = usbInterface.getEndpoint(endpointIndex),
        )
    }

    private fun findDevice(identity: String): UsbDevice? {
        val normalized = UsbPrinterSupport.normalizeIdentity(identity) ?: return null
        return usbManager?.deviceList?.values?.firstOrNull {
            UsbPrinterSupport.identity(it.vendorId, it.productId) == normalized
        }
    }

    private fun describe(device: UsbDevice): UsbPrinterDevice {
        val interfaces = (0 until device.interfaceCount).map { index ->
            val iface = device.getInterface(index)
            UsbInterfaceInfo(
                index = index,
                interfaceClass = iface.interfaceClass,
                interfaceSubclass = iface.interfaceSubclass,
                interfaceProtocol = iface.interfaceProtocol,
                endpoints = (0 until iface.endpointCount).map { endpointIndex ->
                    val endpoint = iface.getEndpoint(endpointIndex)
                    UsbEndpointInfo(
                        address = endpoint.address,
                        direction = if (endpoint.direction == UsbConstants.USB_DIR_IN) {
                            UsbEndpointDirection.IN
                        } else {
                            UsbEndpointDirection.OUT
                        },
                        type = when (endpoint.type) {
                            UsbConstants.USB_ENDPOINT_XFER_CONTROL ->
                                UsbEndpointType.CONTROL
                            UsbConstants.USB_ENDPOINT_XFER_ISOC ->
                                UsbEndpointType.ISOCHRONOUS
                            UsbConstants.USB_ENDPOINT_XFER_BULK ->
                                UsbEndpointType.BULK
                            UsbConstants.USB_ENDPOINT_XFER_INT ->
                                UsbEndpointType.INTERRUPT
                            else -> UsbEndpointType.CONTROL
                        },
                        maxPacketSize = endpoint.maxPacketSize,
                    )
                },
            )
        }
        val name = runCatching { device.productName }
            .getOrNull()
            ?.takeIf { it.isNotBlank() }
            ?: String.format(
                Locale.ROOT,
                "USB %04X:%04X",
                device.vendorId and 0xFFFF,
                device.productId and 0xFFFF,
            )
        return UsbPrinterDevice(
            identity = UsbPrinterSupport.identity(device.vendorId, device.productId),
            name = name,
            vendorId = device.vendorId,
            productId = device.productId,
            interfaces = interfaces,
            supported = UsbPrinterSupport.selectInterface(interfaces) != null,
            requiresPermission = usbManager?.hasPermission(device) == false,
        )
    }

    companion object {
        private const val PERMISSION_TIMEOUT_MS = 60_000L
    }
}
