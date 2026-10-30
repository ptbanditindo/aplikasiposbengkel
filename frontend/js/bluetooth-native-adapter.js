/* Adapter BLUETOOTH untuk APK: meneruskan perintah ke NativeBridge Android.
 *
 * Web Bluetooth di browser tetap ditangani modul terpisah. Adapter ini hanya
 * didaftarkan bila jembatan native tersedia, sehingga desktop tidak berubah.
 * Semua koneksi, pengiriman byte, dan pemutusan socket dilakukan kode native.
 */
(function () {
  'use strict';

  if (!window.BengkelBridge || !window.BengkelBridge.available()) return;
  if (!window.PrinterManager || !window.printerManager) return;

  const DISCOVER_TIMEOUT_MS = 90000;
  const CONNECT_TIMEOUT_MS = 90000;
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

  function toDevice(device) {
    return {
      name: device.name || 'Printer Bluetooth',
      address: device.address || '',
      paired: device.paired === true,
      connection_type: 'BLUETOOTH',
    };
  }

  const adapter = {
    async discover(options) {
      const opts = options || {};
      let result;
      try {
        result = await call(
          'printerDiscover',
          { discovery: opts.discovery !== false },
          DISCOVER_TIMEOUT_MS
        );
      } catch (error) {
        throw asPrinterError(error);
      }
      return (result.devices || []).map(toDevice);
    },

    async connect(printer) {
      let result;
      try {
        result = await call(
          'printerConnect',
          { address: printer && printer.address },
          CONNECT_TIMEOUT_MS
        );
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
        await call('printerDisconnect', {}, STATUS_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
    },

    async getStatus() {
      let result;
      try {
        result = await call('printerStatus', {}, STATUS_TIMEOUT_MS);
      } catch (error) {
        const failure = asPrinterError(error);
        return { available: false, connected: false, message: failure.message };
      }
      if (result.supported === false) {
        return {
          available: false,
          connected: false,
          message: result.message || 'Perangkat ini tidak memiliki Bluetooth.',
        };
      }
      if (result.permissions_granted === false) {
        return {
          available: false,
          connected: false,
          message:
            result.message ||
            'Izin Bluetooth belum diberikan. Pilih Izinkan saat diminta.',
        };
      }
      if (result.enabled === false) {
        return {
          available: false,
          connected: false,
          message:
            result.message ||
            'Bluetooth perangkat sedang nonaktif. Aktifkan Bluetooth lalu coba lagi.',
        };
      }
      return {
        available: true,
        connected: result.connected === true,
        message: result.message || null,
      };
    },

    async print(printer, payload) {
      const data = payload || {};
      const request = {
        paperWidth: Number(data.paperWidth) === 80 ? 80 : 58,
        encoding: data.encoding || '',
      };
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
        await call('printerPrint', request, PRINT_TIMEOUT_MS);
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
      try {
        await call('printerTestPrint', { paperWidth: paperWidth }, PRINT_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
    },
  };

  window.printerManager.registerAdapter('BLUETOOTH', adapter);
  window.BluetoothNativeAdapter = adapter;
})();
