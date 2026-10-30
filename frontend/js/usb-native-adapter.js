/* Adapter USB OTG untuk APK: ESC/POS lewat endpoint BULK OUT printer USB.
 *
 * Hanya didaftarkan bila jembatan native tersedia. Identitas perangkat memakai
 * VID/PID (mis. usb:04b8:0202) agar konfigurasi tetap berlaku setelah kabel
 * dicabut dan dipasang kembali. Izin USB diminta oleh Android saat connect.
 */
(function () {
  'use strict';

  if (!window.BengkelBridge || !window.BengkelBridge.available()) return;
  if (!window.PrinterManager || !window.printerManager) return;

  const DISCOVER_TIMEOUT_MS = 20000;
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

  function identityOf(printer) {
    const source = printer || {};
    return String(source.address || source.identity || '').trim();
  }

  function toDevice(device) {
    return {
      name: device.name || 'Perangkat USB',
      address: device.identity || '',
      identity: device.identity || '',
      vendor_id: Number(device.vendor_id) || null,
      product_id: Number(device.product_id) || null,
      supported: device.supported === true,
      requires_permission: device.requires_permission === true,
      interfaces: Array.isArray(device.interfaces) ? device.interfaces : [],
      connection_type: 'USB',
    };
  }

  const adapter = {
    async discover() {
      let result;
      try {
        result = await call('usbDiscover', {}, DISCOVER_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
      return (result.devices || []).map(toDevice);
    },

    async connect(printer) {
      let result;
      try {
        result = await call(
          'usbConnect',
          { identity: identityOf(printer) },
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
        await call('usbDisconnect', {}, STATUS_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
    },

    async getStatus() {
      let result;
      try {
        result = await call('usbStatus', {}, STATUS_TIMEOUT_MS);
      } catch (error) {
        const failure = asPrinterError(error);
        return { available: false, connected: false, message: failure.message };
      }
      if (result.supported === false) {
        return {
          available: false,
          connected: false,
          message:
            result.message ||
            'Perangkat ini tidak mendukung USB Host (OTG).',
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
        identity: identityOf(printer),
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
        await call('usbPrint', request, PRINT_TIMEOUT_MS);
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
        await call(
          'usbTestPrint',
          { paperWidth: paperWidth, identity: identityOf(printer) },
          PRINT_TIMEOUT_MS
        );
      } catch (error) {
        throw asPrinterError(error);
      }
    },
  };

  window.printerManager.registerAdapter('USB', adapter);
  window.UsbNativeAdapter = adapter;
})();
