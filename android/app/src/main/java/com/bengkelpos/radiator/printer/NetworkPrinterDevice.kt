package com.bengkelpos.radiator.printer

/** Printer jaringan yang ditemukan lewat NSD; bukan hasil ping alamat IP. */
data class NetworkPrinterDevice(
    val name: String,
    val ip: String,
    val port: Int,
)

/** Pasangan alamat yang sedang dipakai controller jaringan. */
data class NetworkEndpoint(
    val ip: String,
    val port: Int,
)

data class NetworkPrinterStatus(
    val connected: Boolean,
    val ip: String?,
    val port: Int?,
    val message: String?,
    val discoverySupported: Boolean,
)

/**
 * Pencarian printer jaringan. Implementasi Android memakai NSD (mDNS) untuk
 * layanan RAW `_pdl-datastream._tcp.`; banyak printer 9100 tidak mengiklankan
 * layanan ini sehingga entri manual IP:port tetap menjadi jalur utama.
 */
interface NetworkPrinterDiscovery {
    fun isSupported(): Boolean
    fun discover(windowMs: Long): List<NetworkPrinterDevice>
}

class UnsupportedNetworkPrinterDiscovery : NetworkPrinterDiscovery {
    override fun isSupported(): Boolean = false

    override fun discover(windowMs: Long): List<NetworkPrinterDevice> =
        throw PrinterException(
            PrinterErrorCode.DISCOVERY_FAILED,
            "Pencarian otomatis printer jaringan tidak tersedia di perangkat " +
                "ini. Masukkan IP dan port printer secara manual.",
        )
}
