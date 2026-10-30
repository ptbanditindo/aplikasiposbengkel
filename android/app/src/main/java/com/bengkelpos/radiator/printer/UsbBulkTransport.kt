package com.bengkelpos.radiator.printer

import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import java.io.IOException

/**
 * Transport BULK OUT ke printer USB. Koneksi dibuka dan interface diklaim saat
 * [connect]; semuanya dilepas saat [close]. Data dikirim per potongan kecil
 * agar transfer besar tidak melebihi buffer driver dan sisa byte tetap terkirim.
 */
class UsbBulkTransport(
    private val usbManager: UsbManager,
    private val device: UsbDevice,
    private val usbInterface: UsbInterface,
    private val endpoint: UsbEndpoint,
) : UsbTransport {

    private val lock = Any()
    private var connection: UsbDeviceConnection? = null

    @Volatile
    private var closed = false

    override fun connect() {
        synchronized(lock) {
            if (closed) throw IOException("Transport USB sudah ditutup.")
            if (connection != null) return
            val opened = usbManager.openDevice(device)
                ?: throw IOException(
                    "Perangkat USB tidak dapat dibuka. Izin mungkin dicabut.",
                )
            if (!opened.claimInterface(usbInterface, true)) {
                runCatching { opened.close() }
                throw IOException(
                    "Interface printer USB sedang dipakai atau tidak dapat diklaim.",
                )
            }
            connection = opened
        }
    }

    override fun write(bytes: ByteArray) {
        if (closed) throw IOException("Koneksi printer USB sudah ditutup.")
        val active = synchronized(lock) { connection }
            ?: throw IOException("Koneksi printer USB belum dibuka.")
        var offset = 0
        while (offset < bytes.size) {
            val chunk = minOf(bytes.size - offset, WRITE_CHUNK_BYTES)
            val sent = active.bulkTransfer(
                endpoint,
                bytes,
                offset,
                chunk,
                WRITE_TIMEOUT_MS,
            )
            if (sent <= 0) {
                throw IOException(
                    "Data struk gagal dikirim ke printer USB (kode $sent).",
                )
            }
            offset += sent
        }
    }

    override fun isConnected(): Boolean =
        !closed && synchronized(lock) { connection != null }

    override fun close() {
        synchronized(lock) {
            closed = true
            val active = connection ?: return
            connection = null
            runCatching { active.releaseInterface(usbInterface) }
            runCatching { active.close() }
        }
    }

    companion object {
        private const val WRITE_CHUNK_BYTES = 8 * 1024
        private const val WRITE_TIMEOUT_MS = 5_000
    }
}
