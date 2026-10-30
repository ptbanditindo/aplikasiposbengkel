package com.bengkelpos.radiator.printer

/** Saluran byte RAW TCP ke printer jaringan. */
interface NetworkTransport {
    fun connect()
    fun write(bytes: ByteArray)
    fun isConnected(): Boolean
    fun close()
}
