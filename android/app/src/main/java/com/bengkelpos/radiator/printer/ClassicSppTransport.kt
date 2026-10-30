package com.bengkelpos.radiator.printer

import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import java.io.IOException
import java.util.UUID

/**
 * Socket RFCOMM Bluetooth Classic memakai profil Serial Port (SPP).
 *
 * Batasan: hanya printer yang menyediakan layanan SPP yang dapat dipakai.
 * Printer BLE (GATT) atau printer dengan protokol vendor khusus tidak didukung
 * oleh jalur ini dan akan mendapat pesan kesalahan yang jelas.
 */
class ClassicSppTransport(private val device: BluetoothDevice) : BluetoothTransport {

    private var socket: BluetoothSocket? = null

    @Volatile
    private var closed = false

    override fun connect() {
        if (closed) throw IOException("Koneksi printer sudah ditutup.")
        val created = try {
            device.createRfcommSocketToServiceRecord(SPP_UUID)
        } catch (error: IOException) {
            throw PrinterException(
                PrinterErrorCode.UNSUPPORTED_SPP,
                "Printer tidak dapat membuka layanan Bluetooth Classic SPP. " +
                    "Periksa apakah printer memakai Bluetooth Classic (SPP), " +
                    "bukan Bluetooth Low Energy.",
                error,
            )
        }
        socket = created
        created.connect()
    }

    override fun write(bytes: ByteArray) {
        val current = socket ?: throw IOException("Socket printer belum dibuka.")
        if (!current.isConnected) throw IOException("Socket printer sudah tertutup.")
        current.outputStream.write(bytes)
        current.outputStream.flush()
    }

    override fun isConnected(): Boolean {
        val current = socket ?: return false
        return !closed && current.isConnected
    }

    /** Menutup socket saja; pemasangan Bluetooth tidak diubah. */
    override fun close() {
        closed = true
        val current = socket
        socket = null
        runCatching { current?.close() }
    }

    companion object {
        val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }
}
