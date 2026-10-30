/* Adapter Wi-Fi/LAN untuk APK: RAW TCP ESC/POS lewat NativeBridge Android.
 *
 * Web desktop tidak dapat membuka socket TCP mentah dari halaman, sehingga
 * adapter ini hanya didaftarkan bila jembatan native tersedia. Konfigurasi IP
 * dan port tetap disimpan backend lokal; adapter hanya meneruskan byte cetak
 * dan tidak menghitung ulang nominal struk.
 */
(function () {
  'use strict';

  if (!window.BengkelBridge || !window.BengkelBridge.available()) return;
  if (!window.PrinterManager || !window.printerManager) return;

  const DISCOVER_TIMEOUT_MS = 30000;
  const CONNECT_TIMEOUT_MS = 30000;
  const PRINT_TIMEOUT_MS = 30000;
  const STATUS_TIMEOUT_MS = 10000;

  function call(method, args, timeoutMs) {
    return window.BengkelBridge.call(method, args || {}, timeoutMs);
  }

  function asPrinterError(error) {
    const result = new Error(
      (error && error.message) || 'Perintah printer gagal.'
    );
    result.name = 'PrinterError';
    result.code = (error && error.code) || 'NATIVE_PRINTER_ERROR';
    return result;
  }

  function endpoint(printer) {
    const source = printer || {};
    const port = Number(source.port);
    return {
      ip: String(source.ip || '').trim(),
      port: Number.isInteger(port) ? port : null,
    };
  }

  function toDevice(device) {
    return {
      name: device.name || 'Printer Jaringan',
      ip: device.ip || '',
      port: Number(device.port) || null,
      connection_type: 'NETWORK',
    };
  }

  const adapter = {
    async discover() {
      let result;
      try {
        result = await call('networkDiscover', {}, DISCOVER_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
      if (result.discovery_supported === false) {
        throw new Error(
          'Pencarian otomatis printer jaringan tidak tersedia di perangkat ' +
            'ini. Masukkan IP dan port printer secara manual.'
        );
      }
      return (result.devices || []).map(toDevice);
    },

    async connect(printer) {
      const target = endpoint(printer);
      let result;
      try {
        result = await call('networkConnect', target, CONNECT_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
      if (!result.connected) {
        throw new Error(
          result.message || 'Printer tidak melaporkan koneksi berhasil.'
        );
      }
      return { connected: true };
    },

    async disconnect() {
      try {
        await call('networkDisconnect', {}, STATUS_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
    },

    async getStatus() {
      let result;
      try {
        result = await call('networkStatus', {}, STATUS_TIMEOUT_MS);
      } catch (error) {
        const failure = asPrinterError(error);
        return { available: false, connected: false, message: failure.message };
      }
      return {
        available: true,
        connected: result.connected === true,
        discovery_supported: result.discovery_supported !== false,
        message: result.message || null,
      };
    },

    async print(printer, payload) {
      const data = payload || {};
      const request = Object.assign(
        {
          paperWidth: Number(data.paperWidth) === 80 ? 80 : 58,
          encoding: data.encoding || '',
        },
        endpoint(printer)
      );
      if (data.mode === 'ESCPOS' && data.base64) {
        request.base64 = data.base64;
      } else if (Array.isArray(data.lines) && data.lines.length) {
        request.lines = data.lines;
      } else {
        throw new Error(
          'Data cetak tidak didukung. Muat ulang nota lalu coba lagi.'
        );
      }
      try {
        await call('networkPrint', request, PRINT_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
    },

    async testPrint(printer, options) {
      const opts = options || {};
      const paperWidth =
        Number(opts.paperWidth || (printer && printer.paper_width)) === 80
          ? 80
          : 58;
      const request = Object.assign({ paperWidth: paperWidth }, endpoint(printer));
      try {
        await call('networkTestPrint', request, PRINT_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
    },
  };

  window.printerManager.registerAdapter('NETWORK', adapter);
  window.NetworkNativeAdapter = adapter;
})();
