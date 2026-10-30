package com.bengkelpos.radiator.printer

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/**
 * Pencarian printer jaringan lewat NSD/mDNS untuk layanan RAW TCP.
 *
 * Hanya layanan `_pdl-datastream._tcp.` yang dianggap kandidat printer. Banyak
 * printer port 9100 tidak mengiklankan layanan ini, sehingga hasil kosong bukan
 * berarti printer tidak ada; entri manual IP:port tetap jalur utama. Alamat IP
 * yang sekadar "bisa dijangkau" tidak pernah dilaporkan sebagai temuan.
 *
 * Pemanggil wajib menjalankan [discover] di luar main thread (NativeBridge
 * memakai executor), karena method ini menunggu jendela pencarian.
 */
class NsdNetworkPrinterDiscovery(private val context: Context) : NetworkPrinterDiscovery {

    override fun isSupported(): Boolean =
        runCatching { context.getSystemService(Context.NSD_SERVICE) as? NsdManager }
            .getOrNull() != null

    override fun discover(windowMs: Long): List<NetworkPrinterDevice> {
        val manager = context.getSystemService(Context.NSD_SERVICE) as? NsdManager
            ?: throw PrinterException(
                PrinterErrorCode.DISCOVERY_FAILED,
                "Pencarian otomatis printer jaringan tidak tersedia di perangkat " +
                    "ini. Masukkan IP dan port printer secara manual.",
            )
        val found = Collections.synchronizedList(ArrayList<PrinterCandidate>())
        val resolvePool = Executors.newSingleThreadExecutor()
        val finished = CountDownLatch(1)
        val startFailure = AtomicReference<Int?>(null)
        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) = Unit

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                startFailure.set(errorCode)
                finished.countDown()
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) = Unit

            override fun onDiscoveryStopped(serviceType: String) = Unit

            override fun onServiceLost(serviceInfo: NsdServiceInfo) = Unit

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                if (serviceInfo.serviceType != SERVICE_TYPE) return
                val candidate = PrinterCandidate(
                    info = serviceInfo,
                    name = serviceInfo.serviceName?.trim().orEmpty(),
                )
                found.add(candidate)
                resolvePool.execute { resolve(manager, candidate) }
            }
        }

        try {
            manager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
            finished.await(windowMs, TimeUnit.MILLISECONDS)
            val code = startFailure.get()
            if (code != null) {
                throw PrinterException(
                    PrinterErrorCode.DISCOVERY_FAILED,
                    "Perangkat gagal memulai pencarian printer jaringan " +
                        "(kode $code). Masukkan IP dan port printer secara manual.",
                )
            }
        } catch (error: PrinterException) {
            throw error
        } catch (error: InterruptedException) {
            Thread.currentThread().interrupt()
            throw PrinterException(
                PrinterErrorCode.DISCOVERY_FAILED,
                "Pencarian printer jaringan dibatalkan.",
                error,
            )
        } catch (error: Throwable) {
            throw PrinterException(
                PrinterErrorCode.DISCOVERY_FAILED,
                "Pencarian printer jaringan gagal. Masukkan IP dan port printer " +
                    "secara manual.",
                error,
            )
        } finally {
            runCatching { manager.stopServiceDiscovery(listener) }
            resolvePool.shutdown()
            runCatching { resolvePool.awaitTermination(RESOLVE_GRACE_MS, TimeUnit.MILLISECONDS) }
        }

        return synchronized(found) {
            found.mapNotNull { it.resolved }
                .distinctBy { "${it.ip}:${it.port}" }
        }
    }

    private class PrinterCandidate(
        val info: NsdServiceInfo,
        val name: String,
        @Volatile var resolved: NetworkPrinterDevice? = null,
    )

    @Suppress("DEPRECATION")
    private fun resolve(
        manager: NsdManager,
        candidate: PrinterCandidate,
    ) {
        val info = candidate.info
        val latch = CountDownLatch(1)
        val listener = object : NsdManager.ResolveListener {
            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                latch.countDown()
            }

            override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                val address = serviceInfo.host?.hostAddress
                if (address != null &&
                    NetworkAddress.normalizeIp(address) != null &&
                    NetworkAddress.normalizePort(serviceInfo.port) != null
                ) {
                    candidate.resolved = NetworkPrinterDevice(
                        name = candidate.name.ifEmpty { "$address:${serviceInfo.port}" },
                        ip = address,
                        port = serviceInfo.port,
                    )
                }
                latch.countDown()
            }
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                manager.resolveService(info, { command -> command.run() }, listener)
            } else {
                manager.resolveService(info, listener)
            }
            latch.await(RESOLVE_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        } catch (error: Throwable) {
            // Satu layanan gagal dipetakan tidak boleh menggagalkan seluruh pencarian.
        }
    }

    companion object {
        const val SERVICE_TYPE = "_pdl-datastream._tcp."
        private const val RESOLVE_TIMEOUT_MS = 4_000L
        private const val RESOLVE_GRACE_MS = 5_000L
    }
}
