/* Adapter Web Desktop untuk mencetak lewat dialog browser.
 *
 * Hanya didaftarkan saat jembatan native tidak tersedia, sehingga Web
 * Bluetooth tidak pernah dipakai sebagai jalur printer native Android.
 * Pengiriman ENTER/ESC/POS jaringan atau USB tetap melalui adapter native.
 */
(function () {
  'use strict';

  if (window.BengkelBridge && window.BengkelBridge.available()) return;
  if (!window.PrinterManager || !window.printerManager) return;

  function unavailable() {
    return new Error(
      'Cetak browser tidak tersedia. Muat ulang halaman lalu coba lagi.'
    );
  }

  function printLines(lines, width) {
    if (!Array.isArray(lines) || !lines.length) {
      throw new Error(
        'Data baris struk tidak tersedia. Muat ulang nota lalu coba lagi.'
      );
    }
    if (!window.BengkelWebPrint || typeof window.BengkelWebPrint.print !== 'function') {
      throw unavailable();
    }
    window.BengkelWebPrint.print(lines, width);
  }

  function testLines(paperWidth) {
    const columns = paperWidth === 80 ? 48 : 32;
    const now = new Date();
    const stamp =
      String(now.getDate()).padStart(2, '0') +
      '-' +
      String(now.getMonth() + 1).padStart(2, '0') +
      '-' +
      now.getFullYear() +
      ' ' +
      String(now.getHours()).padStart(2, '0') +
      ':' +
      String(now.getMinutes()).padStart(2, '0');
    return [
      'BENGKELPOS RADIATOR',
      'Tes Printer Browser',
      '-'.repeat(columns),
      'Waktu: ' + stamp,
      'Printer siap digunakan.',
      '-'.repeat(columns),
    ];
  }

  const adapter = {
    // Dialog browser tidak memiliki sesi koneksi persisten.
    connectionless: true,

    async discover() {
      return [
        {
          name: 'Printer Browser (Web Desktop)',
          address: 'browser',
          identity: 'browser',
          connection_type: 'WEB',
          supported: true,
          requires_permission: false,
        },
      ];
    },

    async connect() {
      if (!window.BengkelWebPrint) throw unavailable();
      return { connected: true };
    },

    async disconnect() {
      return { connected: false };
    },

    async getStatus() {
      const available = Boolean(
        window.BengkelWebPrint &&
          typeof window.BengkelWebPrint.print === 'function'
      );
      return {
        available: available,
        connected: false,
        message: available
          ? 'Cetak melalui dialog browser. Hanya tersedia di Web Desktop.'
          : 'Cetak browser tidak tersedia di perangkat ini.',
      };
    },

    async print(printer, payload) {
      const width = Number(payload && payload.paperWidth) === 80 ? 80 : 58;
      printLines(payload && payload.lines, width);
      return { queued: true, printer: (printer && printer.name) || 'Browser' };
    },

    async testPrint(printer, options) {
      const width =
        Number((options && options.paperWidth) || (printer && printer.paper_width)) === 80
          ? 80
          : 58;
      printLines(testLines(width), width);
      return { queued: true };
    },
  };

  window.printerManager.registerAdapter('WEB', adapter);
  window.WebPrintAdapter = adapter;
})();
