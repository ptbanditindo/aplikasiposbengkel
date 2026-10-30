/* Adapter Android System Print untuk APK.
 *
 * Dialog pemilihan printer, pratinjau, dan pembatalan disediakan Android.
 * Adapter ini hanya mengirim baris struk dari backend dan melaporkan status
 * pekerjaan apa adanya. Membuka dialog tidak berarti printer sudah mencetak.
 */
(function () {
  'use strict';

  if (!window.BengkelBridge || !window.BengkelBridge.available()) return;
  if (!window.PrinterManager || !window.printerManager) return;

  const STATUS_TIMEOUT_MS = 15000;
  const PRINT_TIMEOUT_MS = 30000;

  function call(method, args, timeoutMs) {
    return window.BengkelBridge.call(method, args || {}, timeoutMs);
  }

  function asPrinterError(error) {
    const result = new Error(
      (error && error.message) || 'Perintah cetak Android gagal.'
    );
    result.name = 'PrinterError';
    result.code = (error && error.code) || 'SYSTEM_PRINT_FAILED';
    return result;
  }

  function payloadLines(payload) {
    const lines = payload && payload.lines;
    if (!Array.isArray(lines) || !lines.length) {
      throw new Error(
        'Data baris struk tidak tersedia. Muat ulang nota lalu coba lagi.'
      );
    }
    return lines;
  }

  function paperWidthOf(printer, payload) {
    const requested = Number(
      (payload && payload.paperWidth) || (printer && printer.paper_width) || 58
    );
    return requested === 80 ? 80 : 58;
  }

  async function availability() {
    try {
      return await call('systemPrintStatus', {}, STATUS_TIMEOUT_MS);
    } catch (error) {
      throw asPrinterError(error);
    }
  }

  const adapter = {
    // Dialog cetak Android tidak memiliki sesi koneksi persisten.
    connectionless: true,

    async discover() {
      const status = await availability();
      if (!status.supported) return [];
      return [
        {
          name: 'Android System Print',
          address: 'system',
          identity: 'system',
          connection_type: 'SYSTEM',
          supported: true,
          requires_permission: false,
        },
      ];
    },

    async connect() {
      const status = await availability();
      if (!status.supported) {
        throw new Error(
          status.message ||
            'Android Print tidak tersedia di perangkat ini. Gunakan printer lain.'
        );
      }
      return { connected: true };
    },

    async disconnect() {
      return { connected: false };
    },

    async getStatus() {
      try {
        const status = await availability();
        return {
          available: status.supported === true,
          connected: false,
          message:
            status.message ||
            'Cetak melalui dialog Android. Pilih printer di dialog saat mencetak.',
          job_state: status.state || null,
          job_id: status.job_id == null ? null : status.job_id,
        };
      } catch (error) {
        const failure = asPrinterError(error);
        return { available: false, connected: false, message: failure.message };
      }
    },

    async print(printer, payload) {
      const request = {
        title: 'Struk ' + ((printer && printer.name) || 'BengkelPOS'),
        lines: payloadLines(payload),
        paperWidth: paperWidthOf(printer, payload),
      };
      try {
        return await call('systemPrint', request, PRINT_TIMEOUT_MS);
      } catch (error) {
        throw asPrinterError(error);
      }
    },

    async testPrint(printer, options) {
      try {
        return await call(
          'systemTestPrint',
          { paperWidth: paperWidthOf(printer, options) },
          PRINT_TIMEOUT_MS
        );
      } catch (error) {
        throw asPrinterError(error);
      }
    },

    async jobStatus(jobId) {
      const args = jobId == null ? {} : { job_id: jobId };
      return call('systemPrintStatus', args, STATUS_TIMEOUT_MS);
    },

    async cancelJob(jobId) {
      return call('systemPrintCancel', { job_id: jobId }, STATUS_TIMEOUT_MS);
    },
  };

  window.printerManager.registerAdapter('SYSTEM', adapter);
  window.SystemNativeAdapter = adapter;
})();
