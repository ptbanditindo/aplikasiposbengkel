package com.bengkelpos.radiator.printer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UsbPrinterSupportTest {

    private val bulkOut = UsbEndpointInfo(
        address = 0x01,
        direction = UsbEndpointDirection.OUT,
        type = UsbEndpointType.BULK,
        maxPacketSize = 64,
    )
    private val bulkIn = UsbEndpointInfo(
        address = 0x82,
        direction = UsbEndpointDirection.IN,
        type = UsbEndpointType.BULK,
        maxPacketSize = 64,
    )
    private val interruptOut = UsbEndpointInfo(
        address = 0x02,
        direction = UsbEndpointDirection.OUT,
        type = UsbEndpointType.INTERRUPT,
        maxPacketSize = 8,
    )

    private fun iface(
        index: Int,
        interfaceClass: Int = 0xFF,
        vararg endpoints: UsbEndpointInfo,
    ) = UsbInterfaceInfo(
        index = index,
        interfaceClass = interfaceClass,
        interfaceSubclass = 0,
        interfaceProtocol = 0,
        endpoints = endpoints.toList(),
    )

    @Test
    fun `identitas memakai VID dan PID heksadesimal kecil`() {
        assertEquals("usb:04b8:0202", UsbPrinterSupport.identity(0x04B8, 0x0202))
        assertEquals("usb:1234:ffff", UsbPrinterSupport.identity(0x1234, 0xFFFF))
        assertEquals(
            "usb:04b8:0202",
            UsbPrinterSupport.identity(0x10000 + 0x04B8, 0x0202),
        )
    }

    @Test
    fun `identitas dari konfigurasi dinormalisasi`() {
        assertEquals("usb:04b8:0202", UsbPrinterSupport.normalizeIdentity(" USB:04B8:0202 "))
        assertEquals("usb:04b8:0202", UsbPrinterSupport.normalizeIdentity("usb:04b8:0202"))
        assertNull(UsbPrinterSupport.normalizeIdentity("usb:04b8"))
        assertNull(UsbPrinterSupport.normalizeIdentity("04b8:0202"))
        assertNull(UsbPrinterSupport.normalizeIdentity("usb:zzzz:0202"))
        assertNull(UsbPrinterSupport.normalizeIdentity(""))
        assertNull(UsbPrinterSupport.normalizeIdentity(null))
    }

    @Test
    fun `interface kelas printer diutamakan`() {
        val vendor = iface(index = 0, interfaceClass = 0xFF, bulkOut, bulkIn)
        val printer = iface(index = 1, interfaceClass = 7, bulkOut)

        val selected = UsbPrinterSupport.selectInterface(listOf(vendor, printer))

        assertNotNull(selected)
        assertEquals(1, selected!!.index)
    }

    @Test
    fun `interface vendor dengan bulk out tetap diterima`() {
        val vendor = iface(index = 3, interfaceClass = 0xFF, bulkOut)

        assertEquals(3, UsbPrinterSupport.selectInterface(listOf(vendor))!!.index)
    }

    @Test
    fun `perangkat tanpa bulk out tidak didukung`() {
        val onlyIn = iface(index = 0, interfaceClass = 7, bulkIn)
        val onlyInterrupt = iface(index = 1, interfaceClass = 7, interruptOut)

        assertNull(UsbPrinterSupport.selectInterface(listOf(onlyIn, onlyInterrupt)))
        assertFalse(
            UsbPrinterSupport.supportsBulkOut(
                UsbPrinterDevice(
                    identity = "usb:1111:2222",
                    name = "USB",
                    vendorId = 0x1111,
                    productId = 0x2222,
                    interfaces = listOf(onlyIn),
                    supported = false,
                    requiresPermission = false,
                ),
            ),
        )
    }

    @Test
    fun `endpoint bulk out dipilih bukan bulk in`() {
        val selected = UsbPrinterSupport.selectBulkOutEndpoint(
            iface(index = 0, interfaceClass = 7, bulkIn, bulkOut),
        )

        assertNotNull(selected)
        assertEquals(0x01, selected!!.address)
        assertEquals(UsbEndpointDirection.OUT, selected.direction)
    }
}
