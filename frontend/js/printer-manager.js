/* PrinterManager: satu pengelola koneksi printer dengan adapter terpisah.
 *
 * Kontrak adapter:
 *   discover(options) -> Promise<Array<device>>
 *   connect(printer) -> Promise<true|{connected:true}>
 *   disconnect(printer) -> Promise<void>
 *   print(printer, payload) -> Promise<void>
 *   getStatus(printer) -> Promise<{available, connected, message?}>
 *   testPrint(printer) -> Promise<void>
 *
 * Status yang ditampilkan hanya CONNECTED setelah adapter benar-benar
 * melaporkan koneksi berhasil. Konfigurasi disimpan di backend lokal dan
 * tidak pernah memuat data transaksi.
 */
(function () {
  'use strict';

  const STATUS = Object.freeze({
    CONNECTED: 'CONNECTED',
    SAVED: 'SAVED',
    UNAVAILABLE: 'UNAVAILABLE',
    CONNECTING: 'CONNECTING',
    ERROR: 'ERROR',
  });

  const CONNECTION_TYPES = Object.freeze([
    'BLUETOOTH',
    'NETWORK',
    'USB',
    'SYSTEM',
    'WEB',
  ]);

  const ADAPTER_METHODS = [
    'discover',
    'connect',
    'disconnect',
    'print',
    'getStatus',
    'testPrint',
  ];

  const TYPE_LABELS = {
    BLUETOOTH: 'Bluetooth',
    NETWORK: 'Wi-Fi atau LAN',
    USB: 'USB',
    SYSTEM: 'Cetak Android',
    WEB: 'Cetak browser',
  };

  function printerTypeLabel(type) {
    return TYPE_LABELS[String(type || '').toUpperCase()] || 'ini';
  }

  class PrinterError extends Error {
    constructor(message, code) {
      super(message);
      this.name = 'PrinterError';
      this.code = code || 'PRINTER_ERROR';
    }
  }

  function normalizeStatus(value) {
    const status = String(value || '').toUpperCase();
    if (status === STATUS.CONNECTED || status === STATUS.CONNECTING) {
      // Status koneksi hidup tidak berlaku lagi setelah halaman dimuat ulang.
      return STATUS.SAVED;
    }
    return [STATUS.SAVED, STATUS.UNAVAILABLE, STATUS.ERROR].includes(status)
      ? status
      : STATUS.SAVED;
  }

  function configPayload(printer) {
    return {
      id: printer.id,
      name: printer.name,
      connection_type: printer.connection_type,
      paper_width: printer.paper_width,
      print_mode: printer.print_mode,
      encoding: printer.encoding,
      address: printer.address || '',
      ip: printer.ip || '',
      port: printer.port == null ? null : printer.port,
      last_status: printer.last_status || STATUS.SAVED,
      last_connected_at: printer.last_connected_at || null,
      last_error: printer.last_error || null,
    };
  }

  function nowISO() {
    return new Date().toISOString();
  }

  class PrinterManager {
    constructor(options) {
      const opts = options || {};
      this.api = opts.api || window.API;
      this.adapters = {};
      this.config = {
        version: 1,
        printers: [],
        primary_id: null,
        updated_at: null,
        warning: null,
      };
      this.runtime = {};
      this.loaded = false;
      this.loading = null;
      this.listeners = new Set();
      this.storageWarning = null;
    }

    registerAdapter(type, adapter) {
      const key = String(type || '').toUpperCase();
      if (!CONNECTION_TYPES.includes(key)) {
        throw new PrinterError('Jenis printer tidak dikenal.');
      }
      if (!adapter || typeof adapter !== 'object') {
        throw new PrinterError('Pengaturan printer tidak valid.');
      }
      const missing = ADAPTER_METHODS.filter(
        (method) => typeof adapter[method] !== 'function'
      );
      if (missing.length) {
        throw new PrinterError('Pengaturan printer belum lengkap.');
      }
      this.adapters[key] = adapter;
      this._emit();
      return adapter;
    }

    adapterFor(type) {
      return this.adapters[String(type || '').toUpperCase()] || null;
    }

    onChange(listener) {
      if (typeof listener !== 'function') return () => {};
      this.listeners.add(listener);
      return () => this.listeners.delete(listener);
    }

    _emit() {
      const snapshot = this.snapshot();
      this.listeners.forEach((listener) => {
        try {
          listener(snapshot);
        } catch (err) {
          /* Pendengar UI tidak boleh menghentikan operasi printer. */
        }
      });
    }

    snapshot() {
      const primaryId = this.config.primary_id;
      return {
        version: this.config.version,
        loaded: this.loaded,
        primary_id: primaryId,
        updated_at: this.config.updated_at,
        warning: this.config.warning,
        storage_warning: this.storageWarning,
        printers: this.config.printers.map((printer) => {
          const state = this.runtime[printer.id] || {};
          const status = state.status || normalizeStatus(printer.last_status);
          const hasAdapter = Boolean(this.adapterFor(printer.connection_type));
          return {
            id: printer.id,
            name: printer.name,
            connection_type: printer.connection_type,
            paper_width: printer.paper_width,
            print_mode: printer.print_mode,
            encoding: printer.encoding,
            address: printer.address || '',
            ip: printer.ip || '',
            port: printer.port == null ? null : printer.port,
            status: hasAdapter ? status : STATUS.UNAVAILABLE,
            error:
              state.error ||
              (hasAdapter
                ? printer.last_error || null
                : 'Jenis printer ini belum didukung di perangkat ini.'),
            connected_at: state.connectedAt || printer.last_connected_at || null,
            is_primary: printer.id === primaryId,
            supported: hasAdapter,
          };
        }),
      };
    }

    printerSnapshot(id) {
      return this.snapshot().printers.find((item) => item.id === id) || null;
    }

    primaryPrinter() {
      return this.snapshot().printers.find((item) => item.is_primary) || null;
    }

    async load(force) {
      if (this.loaded && !force) return this.snapshot();
      if (this.loading) return this.loading;
      this.loading = (async () => {
        const data = await this.api.printerConfig();
        this._applyServerConfig(data, false);
        this.loaded = true;
        this._emit();
        return this.snapshot();
      })().finally(() => {
        this.loading = null;
      });
      return this.loading;
    }

    _applyServerConfig(data, preserveRuntime) {
      const source = data || {};
      this.config = {
        version: Number(source.version) || 1,
        printers: Array.isArray(source.printers)
          ? source.printers.map((printer) => Object.assign({}, printer))
          : [],
        primary_id: source.primary_id || null,
        updated_at: source.updated_at || null,
        warning: source.warning || null,
      };

      const runtime = {};
      const validIds = new Set();
      this.config.printers.forEach((printer) => {
        validIds.add(printer.id);
        const previous = preserveRuntime ? this.runtime[printer.id] : null;
        if (previous) {
          runtime[printer.id] = previous;
          return;
        }
        runtime[printer.id] = {
          status: normalizeStatus(printer.last_status),
          error: printer.last_error || null,
          connectedAt: printer.last_connected_at || null,
        };
      });
      Object.keys(this.runtime).forEach((id) => {
        if (!validIds.has(id)) delete this.runtime[id];
      });
      this.runtime = runtime;
    }

    _setRuntime(id, patch) {
      const current = this.runtime[id] || {
        status: STATUS.SAVED,
        error: null,
        connectedAt: null,
      };
      this.runtime[id] = Object.assign({}, current, patch);
      this._emit();
    }

    _findPrinter(id) {
      return this.config.printers.find((printer) => printer.id === id) || null;
    }

    _requirePrinter(id) {
      const printer = this._findPrinter(id);
      if (!printer) {
        throw new PrinterError('Printer tidak ditemukan pada daftar tersimpan.');
      }
      return printer;
    }

    _requireAdapter(printer) {
      const adapter = this.adapterFor(printer.connection_type);
      if (!adapter) {
        throw new PrinterError(
          'Printer ' + printerTypeLabel(printer.connection_type) +
            ' belum didukung di perangkat ini.',
          'ADAPTER_UNSUPPORTED'
        );
      }
      return adapter;
    }

    _payload() {
      return {
        printers: this.config.printers.map(configPayload),
        primary_id: this.config.primary_id,
      };
    }

    async _saveConfig(options) {
      const opts = options || {};
      const saved = await this.api.updatePrinterConfig(this._payload());
      this._applyServerConfig(saved, opts.preserveRuntime !== false);
      this.loaded = true;
      if (opts.emit !== false) this._emit();
      return this.snapshot();
    }

    _updateConfigPrinter(id, patch) {
      this.config.printers = this.config.printers.map((printer) =>
        printer.id === id ? Object.assign({}, printer, patch) : printer
      );
    }

    async _persistStatus(id, status, connectedAt, error) {
      this._updateConfigPrinter(id, {
        last_status: status,
        last_connected_at: connectedAt || null,
        last_error: error || null,
      });
      try {
        await this._saveConfig({ preserveRuntime: true, emit: false });
        this.storageWarning = null;
      } catch (err) {
        // Koneksi tetap berhasil walau riwayat status gagal disimpan.
        this.storageWarning = 'Status printer gagal disimpan. Coba lagi nanti.';
      }
      this._emit();
    }

    async discover(type, options) {
      const key = String(type || '').toUpperCase();
      const adapter = this.adapterFor(key);
      if (!adapter) {
        throw new PrinterError(
          'Pencarian printer jenis ini belum didukung di perangkat ini.',
          'ADAPTER_UNSUPPORTED'
        );
      }
      try {
        const devices = await adapter.discover(options || {});
        return Array.isArray(devices) ? devices : [];
      } catch (err) {
        throw new PrinterError(
          'Pencarian printer gagal. Coba lagi.',
          'DISCOVERY_FAILED'
        );
      }
    }

    async addPrinter(draft, options) {
      const opts = options || {};
      const data = Object.assign({}, draft);
      if (!data.id) {
        data.id =
          String(data.connection_type || 'printer').toLowerCase() +
          '-' +
          Date.now().toString(36);
      }
      data.name = String(data.name || '').trim();
      data.connection_type = String(data.connection_type || '').toUpperCase();
      data.last_status = STATUS.SAVED;
      data.last_error = null;
      data.last_connected_at = null;

      if (this._findPrinter(data.id)) {
        throw new PrinterError('Printer ini sudah ada di daftar.');
      }
      const makePrimary =
        opts.makePrimary === true && opts.allowDisconnected === true;

      this.config.printers = this.config.printers.concat([data]);
      this.runtime[data.id] = {
        status: STATUS.SAVED,
        error: null,
        connectedAt: null,
      };
      if (makePrimary) this.config.primary_id = data.id;

      try {
        await this._saveConfig({ preserveRuntime: true });
      } catch (err) {
        this.config.printers = this.config.printers.filter(
          (printer) => printer.id !== data.id
        );
        delete this.runtime[data.id];
        if (makePrimary) this.config.primary_id = null;
        this._emit();
        throw err;
      }
      return this.printerSnapshot(data.id);
    }

    async updatePrinter(id, patch, options) {
      const printer = this._requirePrinter(id);
      const opts = options || {};
      const next = Object.assign({}, printer, patch || {});
      next.connection_type = String(next.connection_type || '').toUpperCase();
      next.name = String(next.name || '').trim();

      const identityChanged =
        next.connection_type !== printer.connection_type ||
        String(next.address || '') !== String(printer.address || '') ||
        String(next.ip || '') !== String(printer.ip || '') ||
        Number(next.port || 0) !== Number(printer.port || 0);

      if (identityChanged) {
        await this._safeDisconnect(printer);
        this._setRuntime(id, {
          status: STATUS.SAVED,
          error: null,
          connectedAt: null,
        });
        next.last_status = STATUS.SAVED;
        next.last_error = null;
        next.last_connected_at = null;
      }

      this.config.printers = this.config.printers.map((item) =>
        item.id === id ? next : item
      );
      try {
        await this._saveConfig({
          preserveRuntime: true,
          emit: opts.emit !== false,
        });
      } catch (err) {
        this.config.printers = this.config.printers.map((item) =>
          item.id === id ? printer : item
        );
        this._emit();
        throw err;
      }
      return this.printerSnapshot(id);
    }

    async removePrinter(id) {
      const printer = this._requirePrinter(id);
      await this._safeDisconnect(printer);
      this.config.printers = this.config.printers.filter(
        (item) => item.id !== id
      );
      delete this.runtime[id];
      if (this.config.primary_id === id) this.config.primary_id = null;
      await this._saveConfig({ preserveRuntime: true });
      return this.snapshot();
    }

    async selectPrimary(id, options) {
      const opts = options || {};
      this._requirePrinter(id);
      if (!opts.allowDisconnected) {
        const state = this.runtime[id] || {};
        const status = state.status || STATUS.SAVED;
        if (status !== STATUS.CONNECTED) {
          throw new PrinterError(
            'Hubungkan printer dan pastikan koneksinya berhasil sebelum ' +
              'menjadikannya printer utama.'
          );
        }
      }
      this.config.primary_id = id;
      await this._saveConfig({ preserveRuntime: true });
      return this.printerSnapshot(id);
    }

    async connect(id) {
      const printer = this._requirePrinter(id);
      const adapter = this._requireAdapter(printer);
      const state = this.runtime[id] || {};
      if (state.status === STATUS.CONNECTED) {
        return this.printerSnapshot(id);
      }

      if (adapter.connectionless === true) {
        // Printer berbasis dialog tidak punya sesi koneksi yang bisa
        // ditampilkan "Terhubung". Cukup pastikan layanannya tersedia.
        let status;
        try {
          status = await adapter.getStatus(printer);
        } catch (err) {
          const message = err && err.message ? err.message : String(err);
          this._setRuntime(id, { status: STATUS.UNAVAILABLE, error: message });
          throw new PrinterError(message, 'CONNECT_FAILED');
        }
        if (status && status.available === false) {
          const message =
            status.message || 'Layanan cetak tidak tersedia di perangkat ini.';
          this._setRuntime(id, { status: STATUS.UNAVAILABLE, error: message });
          throw new PrinterError(message, 'CONNECT_FAILED');
        }
        this._setRuntime(id, {
          status: STATUS.SAVED,
          error: null,
          connectedAt: state.connectedAt || null,
        });
        return this.printerSnapshot(id);
      }

      this._setRuntime(id, {
        status: STATUS.CONNECTING,
        error: null,
        connectedAt: state.connectedAt || null,
      });

      let result;
      try {
        result = await adapter.connect(printer);
      } catch (err) {
        const message = err && err.message ? err.message : String(err);
        this._setRuntime(id, { status: STATUS.ERROR, error: message });
        await this._persistStatus(
          id,
          STATUS.ERROR,
          state.connectedAt || null,
          message
        );
        throw new PrinterError(
          'Gagal menghubungkan printer: ' + message,
          'CONNECT_FAILED'
        );
      }

      const connected =
        result === true || (result && result.connected === true);
      if (!connected) {
        const message =
          (result && result.message) ||
          'Printer tidak melaporkan koneksi berhasil.';
        this._setRuntime(id, { status: STATUS.ERROR, error: message });
        await this._persistStatus(
          id,
          STATUS.ERROR,
          state.connectedAt || null,
          message
        );
        throw new PrinterError(message, 'CONNECT_FAILED');
      }

      const connectedAt = nowISO();
      this._setRuntime(id, {
        status: STATUS.CONNECTED,
        error: null,
        connectedAt: connectedAt,
      });
      await this._persistStatus(
        id,
        STATUS.CONNECTED,
        connectedAt,
        null
      );
      return this.printerSnapshot(id);
    }

    async disconnect(id) {
      const printer = this._requirePrinter(id);
      const adapter = this.adapterFor(printer.connection_type);
      const state = this.runtime[id] || {};
      let warning = null;

      if (adapter && state.status === STATUS.CONNECTED) {
        try {
          await adapter.disconnect(printer);
        } catch (err) {
          // Koneksi mungkin sudah tertutup; konfigurasi tetap disimpan.
          warning = err && err.message ? err.message : String(err);
        }
      }

      this._setRuntime(id, {
        status: STATUS.SAVED,
        error: null,
        connectedAt: state.connectedAt || null,
      });
      await this._persistStatus(
        id,
        STATUS.SAVED,
        state.connectedAt || null,
        null
      );
      if (warning) {
        return Object.assign(this.printerSnapshot(id), { warning: warning });
      }
      return this.printerSnapshot(id);
    }

    async reconnect(id) {
      const printer = this._requirePrinter(id);
      const state = this.runtime[id] || {};
      if (state.status === STATUS.CONNECTED) {
        await this._safeDisconnect(printer);
        this._setRuntime(id, {
          status: STATUS.SAVED,
          error: null,
          connectedAt: state.connectedAt || null,
        });
      }
      return this.connect(id);
    }

    async _safeDisconnect(printer) {
      const adapter = this.adapterFor(printer.connection_type);
      if (!adapter) return;
      try {
        await adapter.disconnect(printer);
      } catch (err) {
        /* Putuskan koneksi bersifat best-effort; pairing tidak dihapus. */
      }
    }

    async refreshStatus(id) {
      const printer = this._requirePrinter(id);
      const adapter = this._requireAdapter(printer);
      let result;
      try {
        result = await adapter.getStatus(printer);
      } catch (err) {
        const message = err && err.message ? err.message : String(err);
        this._setRuntime(id, { status: STATUS.UNAVAILABLE, error: message });
        return this.printerSnapshot(id);
      }
      const state = this.runtime[id] || {};
      if (adapter.connectionless === true) {
        if (result && result.available === false) {
          this._setRuntime(id, {
            status: STATUS.UNAVAILABLE,
            error: (result && result.message) || 'Layanan cetak tidak tersedia.',
          });
        } else {
          this._setRuntime(id, {
            status: STATUS.SAVED,
            error: null,
            connectedAt: state.connectedAt || null,
          });
        }
      } else if (result && result.connected) {
        this._setRuntime(id, {
          status: STATUS.CONNECTED,
          error: null,
          connectedAt: state.connectedAt || nowISO(),
        });
      } else if (result && result.available === false) {
        this._setRuntime(id, {
          status: STATUS.UNAVAILABLE,
          error: (result && result.message) || 'Printer tidak tersedia.',
        });
      } else {
        this._setRuntime(id, {
          status: STATUS.SAVED,
          error: null,
          connectedAt: state.connectedAt || null,
        });
      }
      return this.printerSnapshot(id);
    }

    _payloadForReceipt(printer, receipt) {
      const paperWidth = Number(printer.paper_width) === 80 ? 80 : 58;
      if (printer.print_mode === 'ESCPOS') {
        const base64 =
          paperWidth === 80
            ? receipt && receipt.escpos_80_base64
            : receipt && receipt.escpos_58_base64;
        if (!base64) {
          throw new PrinterError(
            'Data struk belum siap. Muat ulang nota lalu coba lagi.'
          );
        }
        return {
          mode: 'ESCPOS',
          base64: base64,
          paperWidth: paperWidth,
          encoding: printer.encoding,
        };
      }
      const lines =
        paperWidth === 80 ? receipt && receipt.struk_80 : receipt && receipt.struk_58;
      if (!Array.isArray(lines) || !lines.length) {
        throw new PrinterError(
          'Data baris struk tidak tersedia. Muat ulang nota lalu coba lagi.'
        );
      }
      return {
        mode: printer.print_mode,
        lines: lines,
        paperWidth: paperWidth,
        encoding: printer.encoding,
      };
    }

    async printReceipt(receipt, options) {
      const opts = options || {};
      const printerId = opts.printerId || this.config.primary_id;
      if (!printerId) {
        throw new PrinterError(
          'Belum ada printer utama. Pilih printer di Pengaturan > Printer.'
        );
      }
      const printer = this._requirePrinter(printerId);
      const adapter = this._requireAdapter(printer);
      const payload = this._payloadForReceipt(printer, receipt);
      const state = this.runtime[printerId] || {};
      const connectionless = adapter.connectionless === true;
      const transient = !connectionless && state.status !== STATUS.CONNECTED;

      if (transient) {
        await this.connect(printerId);
      }

      let adapterResult;
      try {
        adapterResult = await adapter.print(printer, payload);
      } catch (err) {
        const message = err && err.message ? err.message : String(err);
        if (transient) await this._safeDisconnect(printer);
        this._setRuntime(printerId, {
          status: STATUS.ERROR,
          error: message,
          connectedAt: state.connectedAt || null,
        });
        await this._persistStatus(
          printerId,
          STATUS.ERROR,
          state.connectedAt || null,
          message
        );
        throw new PrinterError('Gagal mencetak: ' + message, 'PRINT_FAILED');
      }

      const connectedAt = nowISO();
      if (transient || connectionless) {
        // Koneksi hanya dibuka saat dibutuhkan; printer berbasis dialog tidak
        // memiliki sesi koneksi sehingga tetap berstatus tersimpan.
        if (transient) await this._safeDisconnect(printer);
        this._setRuntime(printerId, {
          status: STATUS.SAVED,
          error: null,
          connectedAt: connectedAt,
        });
        await this._persistStatus(
          printerId,
          STATUS.SAVED,
          connectedAt,
          null
        );
      } else {
        this._setRuntime(printerId, {
          status: STATUS.CONNECTED,
          error: null,
          connectedAt: connectedAt,
        });
        await this._persistStatus(
          printerId,
          STATUS.CONNECTED,
          connectedAt,
          null
        );
      }

      return {
        printer_id: printerId,
        printer_name: printer.name,
        no_nota: receipt && receipt.no_nota ? receipt.no_nota : null,
        adapter_result: adapterResult == null ? null : adapterResult,
      };
    }

    async testPrint(id) {
      const printer = this._requirePrinter(id);
      const adapter = this._requireAdapter(printer);
      const state = this.runtime[id] || {};
      const connectionless = adapter.connectionless === true;
      const transient = !connectionless && state.status !== STATUS.CONNECTED;

      if (transient) {
        await this.connect(id);
      }

      let adapterResult;
      try {
        adapterResult = await adapter.testPrint(printer, {
          paperWidth: printer.paper_width,
          encoding: printer.encoding,
        });
      } catch (err) {
        const message = err && err.message ? err.message : String(err);
        if (transient) await this._safeDisconnect(printer);
        this._setRuntime(id, {
          status: STATUS.ERROR,
          error: message,
          connectedAt: state.connectedAt || null,
        });
        throw new PrinterError('Tes cetak gagal: ' + message, 'PRINT_FAILED');
      }

      const connectedAt = nowISO();
      if (transient || connectionless) {
        if (transient) await this._safeDisconnect(printer);
        this._setRuntime(id, {
          status: STATUS.SAVED,
          error: null,
          connectedAt: connectedAt,
        });
      } else {
        this._setRuntime(id, {
          status: STATUS.CONNECTED,
          error: null,
          connectedAt: connectedAt,
        });
      }
      await this._persistStatus(
        id,
        this.runtime[id].status,
        connectedAt,
        null
      );
      return Object.assign(this.printerSnapshot(id), {
        adapter_result: adapterResult == null ? null : adapterResult,
      });
    }
  }

  window.PrinterManager = PrinterManager;
  window.PrinterStatus = STATUS;
  window.createPrinterManager = function (options) {
    return new PrinterManager(options || { api: window.API });
  };
  window.printerManager =
    window.printerManager || new PrinterManager({ api: window.API });
})();
