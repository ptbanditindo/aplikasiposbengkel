package com.bengkelpos.radiator.printer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class BluetoothPermissionPolicyTest {

    @Test
    fun `android 31 ke atas meminta izin connect dan scan`() {
        assertEquals(
            listOf(
                BluetoothPermissionPolicy.BLUETOOTH_CONNECT,
                BluetoothPermissionPolicy.BLUETOOTH_SCAN,
            ),
            BluetoothPermissionPolicy.runtimePermissions(31, discovery = true),
        )
        assertEquals(
            listOf(BluetoothPermissionPolicy.BLUETOOTH_CONNECT),
            BluetoothPermissionPolicy.runtimePermissions(34, discovery = false),
        )
    }

    @Test
    fun `android lama hanya meminta lokasi saat memindai`() {
        assertEquals(
            listOf(BluetoothPermissionPolicy.ACCESS_FINE_LOCATION),
            BluetoothPermissionPolicy.runtimePermissions(30, discovery = true),
        )
        assertEquals(
            emptyList<String>(),
            BluetoothPermissionPolicy.runtimePermissions(26, discovery = false),
        )
    }

    @Test
    fun `izin yang sudah diberikan tidak diminta ulang`() {
        val missing = BluetoothPermissionPolicy.missingRuntimePermissions(
            sdkInt = 33,
            discovery = true,
            isGranted = { it == BluetoothPermissionPolicy.BLUETOOTH_CONNECT },
        )
        assertEquals(listOf(BluetoothPermissionPolicy.BLUETOOTH_SCAN), missing)
    }

    @Test
    fun `pesan penolakan membedakan pencarian dan koneksi`() {
        val scanMessage = BluetoothPermissionPolicy.denialMessage(discovery = true)
        val connectMessage = BluetoothPermissionPolicy.denialMessage(discovery = false)
        assertEquals(true, scanMessage.contains("mencari printer"))
        assertEquals(true, connectMessage.contains("menghubungkan printer"))
    }

    @Test
    fun `alamat bluetooth dinormalisasi dan yang tidak valid ditolak`() {
        assertEquals(
            "AA:BB:CC:DD:EE:FF",
            BluetoothAddress.normalize(" aa:bb:cc:dd:ee:ff "),
        )
        assertNull(BluetoothAddress.normalize("AA:BB:CC:DD:EE"))
        assertNull(BluetoothAddress.normalize("AA-BB-CC-DD-EE-FF"))
        assertNull(BluetoothAddress.normalize("AA:BB:CC:DD:EE:FF;DROP"))
        assertNull(BluetoothAddress.normalize(null))
    }
}
