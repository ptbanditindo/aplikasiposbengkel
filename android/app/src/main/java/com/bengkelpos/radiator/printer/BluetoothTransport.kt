package com.bengkelpos.radiator.printer

/** Saluran byte ke printer; implementasi Android memakai socket RFCOMM. */
interface BluetoothTransport {
    fun connect()
    fun write(bytes: ByteArray)
    fun isConnected(): Boolean
    fun close()
}
