package com.bengkelpos.radiator.printer

import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Implementasi Android untuk daftar perangkat, pemindaian, dan socket SPP.
 *
 * Tidak ada pemanggilan removeBond di kelas ini maupun di seluruh paket printer:
 * memutus koneksi tidak boleh menghapus pasangan Bluetooth pengguna.
 */
class AndroidBluetoothGateway(context: Context) : BluetoothPrinterGateway {

    private val appContext = context.applicationContext
    private val manager =
        appContext.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager

    private val adapter: BluetoothAdapter?
        get() = manager?.adapter

    override fun isSupported(): Boolean = adapter != null

    override fun isEnabled(): Boolean = try {
        adapter?.isEnabled == true
    } catch (error: SecurityException) {
        false
    }

    override fun runtimePermissions(discovery: Boolean): List<String> =
        BluetoothPermissionPolicy.runtimePermissions(Build.VERSION.SDK_INT, discovery)

    override fun missingPermissions(discovery: Boolean): List<String> =
        BluetoothPermissionPolicy.missingRuntimePermissions(
            sdkInt = Build.VERSION.SDK_INT,
            discovery = discovery,
            isGranted = { permission ->
                appContext.checkSelfPermission(permission) ==
                    PackageManager.PERMISSION_GRANTED
            },
        )

    override fun bondedDevices(): List<PrinterDeviceInfo> {
        val bluetooth = requireAdapter()
        return try {
            bluetooth.bondedDevices
                .map { it.toInfo(paired = true) }
                .sortedBy { it.name.lowercase(Locale.US) }
        } catch (error: SecurityException) {
            throw permissionError(error)
        }
    }

    override fun discoverAvailable(windowMs: Long): List<PrinterDeviceInfo> {
        val bluetooth = requireAdapter()
        if (missingPermissions(discovery = true).isNotEmpty()) {
            throw PrinterException(
                PrinterErrorCode.PERMISSION_DENIED,
                BluetoothPermissionPolicy.denialMessage(discovery = true),
            )
        }
        val found = LinkedHashMap<String, PrinterDeviceInfo>()
        val finished = CountDownLatch(1)
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                when (intent?.action) {
                    BluetoothDevice.ACTION_FOUND -> {
                        val device = foundDevice(intent) ?: return
                        found[device.address] = device
                    }
                    BluetoothAdapter.ACTION_DISCOVERY_FINISHED -> finished.countDown()
                }
            }
        }
        val filter = IntentFilter().apply {
            addAction(BluetoothDevice.ACTION_FOUND)
            addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED)
        }
        try {
            ContextCompat.registerReceiver(
                appContext,
                receiver,
                filter,
                ContextCompat.RECEIVER_EXPORTED,
            )
            runCatching { bluetooth.cancelDiscovery() }
            if (!bluetooth.startDiscovery()) {
                throw PrinterException(
                    PrinterErrorCode.DISCOVERY_FAILED,
                    "Pencarian printer tidak dapat dimulai. Matikan lalu nyalakan " +
                        "Bluetooth, kemudian coba lagi.",
                )
            }
            finished.await(windowMs, TimeUnit.MILLISECONDS)
        } catch (error: SecurityException) {
            throw permissionError(error)
        } finally {
            runCatching { bluetooth.cancelDiscovery() }
            runCatching { appContext.unregisterReceiver(receiver) }
        }
        return found.values.sortedBy { it.name.lowercase(Locale.US) }
    }

    override fun deviceByAddress(address: String): PrinterDeviceInfo? {
        val bluetooth = requireAdapter()
        return try {
            val device = bluetooth.getRemoteDevice(address)
            device.toInfo(paired = device.bondState == BluetoothDevice.BOND_BONDED)
        } catch (error: IllegalArgumentException) {
            null
        } catch (error: SecurityException) {
            throw permissionError(error)
        }
    }

    override fun supportsSpp(address: String): Boolean? {
        val bluetooth = requireAdapter()
        return try {
            val uuids = bluetooth.getRemoteDevice(address).uuids ?: return null
            if (uuids.isEmpty()) return null
            uuids.any { it.uuid == ClassicSppTransport.SPP_UUID }
        } catch (error: IllegalArgumentException) {
            null
        } catch (error: SecurityException) {
            throw permissionError(error)
        }
    }

    override fun createTransport(address: String): BluetoothTransport {
        val bluetooth = requireAdapter()
        return try {
            ClassicSppTransport(bluetooth.getRemoteDevice(address))
        } catch (error: IllegalArgumentException) {
            throw PrinterException(
                PrinterErrorCode.INVALID_ADDRESS,
                "Alamat Bluetooth printer tidak valid.",
            )
        } catch (error: SecurityException) {
            throw permissionError(error)
        }
    }

    private fun foundDevice(intent: Intent): PrinterDeviceInfo? {
        val device: BluetoothDevice = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
        } ?: return null
        return try {
            device.toInfo(paired = device.bondState == BluetoothDevice.BOND_BONDED)
        } catch (error: SecurityException) {
            null
        }
    }

    private fun BluetoothDevice.toInfo(paired: Boolean): PrinterDeviceInfo =
        PrinterDeviceInfo(
            name = name?.trim().takeUnless { it.isNullOrEmpty() } ?: "Printer Bluetooth",
            address = address.uppercase(Locale.US),
            paired = paired,
        )

    private fun requireAdapter(): BluetoothAdapter =
        adapter ?: throw PrinterException(
            PrinterErrorCode.BLUETOOTH_UNSUPPORTED,
            "Perangkat ini tidak memiliki Bluetooth.",
        )

    private fun permissionError(cause: SecurityException): PrinterException =
        PrinterException(
            PrinterErrorCode.PERMISSION_DENIED,
            "Izin Bluetooth belum lengkap. Pilih Izinkan saat aplikasi meminta akses.",
            cause,
        )
}
