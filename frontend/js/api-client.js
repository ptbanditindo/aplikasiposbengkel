/* HTTP client tipis untuk backend FastAPI. */
(function () {
  'use strict';

  class ApiError extends Error {
    constructor(message, status, detail) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.detail = detail;
    }
  }

  const GENERIC_VALIDATION =
    'Isian belum sesuai. Periksa kembali data yang dimasukkan.';
  const GENERIC_FAILURE = 'Permintaan gagal. Coba lagi.';
  const INTERNAL_MARKERS =
    /traceback|sqlite|basis data|database|\.py\b|\/api\/|localhost|127\.0\.0\.1|port\s*\d|http\s*\d{3}|stack/i;

  function safeDetail(detail) {
    if (!detail) return null;
    const text =
      typeof detail === 'string'
        ? detail
        : typeof detail.message === 'string'
          ? detail.message
          : '';
    const trimmed = text.trim();
    if (!trimmed || INTERNAL_MARKERS.test(trimmed)) return null;
    return trimmed;
  }

  function extractMessage(detail, fallback) {
    if (Array.isArray(detail)) return GENERIC_VALIDATION;
    return safeDetail(detail) || fallback;
  }

  function friendlyStatusMessage(status) {
    if (status === 401) return 'Sesi berakhir. Masukkan PIN lagi.';
    if (status === 403) return 'Akses ditolak.';
    if (status === 429) return 'Terlalu banyak percobaan. Tunggu sebentar.';
    if (status === 503) return 'Aplikasi belum siap. Tutup lalu buka lagi.';
    if (status >= 500) return 'Aplikasi sedang bermasalah. Coba lagi.';
    return null;
  }

  function messageFor(status, detail) {
    const friendly = friendlyStatusMessage(status);
    if (status >= 500) return friendly;
    return extractMessage(detail, friendly || GENERIC_FAILURE);
  }

  function installToken() {
    // APK Android menyuntikkan token per-instalasi sebelum halaman dimuat.
    const injected = window.__BENGKEL_ADMIN_TOKEN__;
    return typeof injected === 'string' ? injected.trim() : '';
  }

  async function request(path, options) {
    const opts = options || {};
    const headers = Object.assign({}, opts.headers || {});
    const token = installToken();
    if (token) headers['X-Install-Token'] = token;

    const init = {
      method: opts.method || 'GET',
      headers: headers,
      cache: 'no-store',
      credentials: 'same-origin',
    };
    if (opts.body !== undefined && opts.body !== null) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }

    let response;
    try {
      response = await fetch(path, init);
    } catch (err) {
      throw new ApiError(
        'Tidak dapat menghubungi aplikasi. Pastikan aplikasi masih berjalan.',
        0,
        null
      );
    }

    if (response.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new CustomEvent('bengkel:unauthorized'));
    }

    if (response.status === 204) return null;

    if (!response.ok) {
      let detail = null;
      try {
        const data = await response.json();
        detail = data ? data.detail : null;
      } catch (err) {
        detail = null;
      }
      const message = messageFor(response.status, detail);
      throw new ApiError(message, response.status, detail);
    }

    try {
      return await response.json();
    } catch (err) {
      return null;
    }
  }

  const qs = (value) => encodeURIComponent(value == null ? '' : String(value));

  async function downloadBackupBlob(path, method) {
    const headers = {};
    const token = installToken();
    if (token) headers['X-Install-Token'] = token;

    let response;
    try {
      response = await fetch(path, {
        method: method,
        headers: headers,
        credentials: 'same-origin',
        cache: 'no-store',
      });
    } catch (err) {
      throw new ApiError(
        'Tidak dapat menghubungi aplikasi. Pastikan aplikasi masih berjalan.',
        0,
        null
      );
    }

    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('bengkel:unauthorized'));
    }

    if (!response.ok) {
      let detail = null;
      try {
        const data = await response.json();
        detail = data ? data.detail : null;
      } catch (err) {
        detail = null;
      }
      throw new ApiError(
        messageFor(response.status, detail),
        response.status,
        detail
      );
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const filename =
      (match && match[1]) ||
      'bengkel_radiator_backup_' + new Date().toISOString().slice(0, 10) + '.db';

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    return { filename: filename };
  }

  window.API = {
    ApiError: ApiError,

    authStatus: () => request('/api/auth/status'),
    authSetup: (pin) =>
      request('/api/auth/setup', { method: 'POST', body: { pin: pin } }),
    authLogin: (pin) =>
      request('/api/auth/login', { method: 'POST', body: { pin: pin } }),
    authLogout: () => request('/api/auth/logout', { method: 'POST' }),
    setKasirPin: (pin) =>
      request('/api/auth/kasir-pin', { method: 'PUT', body: { pin: pin } }),
    clearKasirPin: () =>
      request('/api/auth/kasir-pin', { method: 'DELETE' }),

    getConfig: () => request('/api/config'),
    health: () => request('/api/health'),

    searchCustomers: (q) => request('/api/customers/search?q=' + qs(q)),
    customerOverview: (q) => request('/api/customers/overview?q=' + qs(q)),
    createCustomer: (data) =>
      request('/api/customers', { method: 'POST', body: data }),
    customerUnits: (customerId) =>
      request('/api/customers/' + customerId + '/units'),
    createUnit: (data) => request('/api/units', { method: 'POST', body: data }),
    deleteUnit: (id) => request('/api/units/' + id, { method: 'DELETE' }),

    stock: () => request('/api/stock'),
    createStock: (data) => request('/api/stock', { method: 'POST', body: data }),
    updateStock: (id, data) =>
      request('/api/stock/' + id, { method: 'PUT', body: data }),
    deleteStock: (id) =>
      request('/api/stock/' + id, { method: 'DELETE' }),

    jasa: () => request('/api/harga-jasa'),
    createJasa: (data) =>
      request('/api/harga-jasa', { method: 'POST', body: data }),
    updateJasa: (id, data) =>
      request('/api/harga-jasa/' + id, { method: 'PUT', body: data }),
    deleteJasa: (id) =>
      request('/api/harga-jasa/' + id, { method: 'DELETE' }),

    previewTransaction: (data) =>
      request('/api/pos/preview', { method: 'POST', body: data }),
    createTransaction: (data) =>
      request('/api/pos/transaction', { method: 'POST', body: data }),
    records: (q) => request('/api/service-records?q=' + qs(q || '')),
    receipt: (id) => request('/api/service-records/' + id + '/receipt'),
    claim: (id) =>
      request('/api/service-records/' + id + '/claim', { method: 'PUT' }),
    returns: (id) =>
      request('/api/service-records/' + id + '/returns'),

    payments: (recordId) =>
      request('/api/service-records/' + recordId + '/payments'),
    createPayment: (recordId, data) =>
      request('/api/service-records/' + recordId + '/payments', {
        method: 'POST',
        body: data,
      }),
    receivables: (customerId) =>
      request(
        '/api/receivables' +
          (customerId ? '?customer_id=' + qs(customerId) : '')
      ),
    customerReceivables: (customerId) =>
      request('/api/customers/' + customerId + '/receivables'),

    recordWhatsapp: (recordId, data) =>
      request('/api/service-records/' + recordId + '/whatsapp', {
        method: 'POST',
        body: data,
      }),
    recordWhatsappLogs: (recordId) =>
      request('/api/service-records/' + recordId + '/whatsapp-logs'),
    whatsappLogs: (limit) =>
      request('/api/whatsapp/logs?limit=' + qs(limit || 100)),

    opsSettings: () => request('/api/settings/ops'),
    updateOpsSettings: (data) =>
      request('/api/settings/ops', { method: 'PUT', body: data }),

    followupItems: (filter, jenis, customerId, status) =>
      request(
        '/api/followup/items?filter=' +
          qs(filter || 'semua') +
          (jenis ? '&jenis=' + qs(jenis) : '') +
          (customerId ? '&customer_id=' + qs(customerId) : '') +
          (status ? '&status=' + qs(status) : '')
      ),
    followupCounts: () => request('/api/followup/counts'),
    followupDetail: (id) => request('/api/followup/items/' + id),
    followupItem: (id, data) =>
      request('/api/followup/items/' + id + '/followup', {
        method: 'POST',
        body: data || {},
      }),
    followupStatus: (id, data) =>
      request('/api/followup/items/' + id + '/status', {
        method: 'POST',
        body: data,
      }),

    updateBengkel: (data) =>
      request('/api/settings/bengkel', { method: 'PUT', body: data }),

    printerConfig: () => request('/api/printer/config'),
    updatePrinterConfig: (data) =>
      request('/api/printer/config', { method: 'PUT', body: data }),

    updateTelegram: (data) =>
      request('/api/settings/telegram', { method: 'PUT', body: data }),

    backupNow: () => request('/api/admin/backup-now', { method: 'POST' }),

    restoreDatabase: async (file) => {
      const form = new FormData();
      form.append('file', file);
      const headers = {};
      const token = installToken();
      if (token) headers['X-Install-Token'] = token;

      let response;
      try {
        response = await fetch('/api/admin/restore', {
          method: 'POST',
          headers: headers,
          credentials: 'same-origin',
          body: form,
          cache: 'no-store',
        });
      } catch (err) {
        throw new ApiError(
          'Tidak dapat menghubungi aplikasi. Pastikan aplikasi masih berjalan.',
          0,
          null
        );
      }

      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('bengkel:unauthorized'));
      }

      if (!response.ok) {
        let detail = null;
        try {
          const data = await response.json();
          detail = data ? data.detail : null;
        } catch (err) {
          detail = null;
        }
        throw new ApiError(
          messageFor(response.status, detail),
          response.status,
          detail
        );
      }
      return response.json();
    },

    daily: (dateStr) =>
      request('/api/reports/daily-cash?tanggal=' + qs(dateStr || '')),
    period: (start, end) =>
      request('/api/reports/period?start=' + qs(start) + '&end=' + qs(end)),
    allTime: () => request('/api/reports/all-time'),
    soldParts: (start, end) =>
      request(
        '/api/reports/sold-parts' +
          (start && end
            ? '?start=' + qs(start) + '&end=' + qs(end)
            : '')
      ),

    downloadBackup: async () => {
      // APK: file ditulis native ke folder pilihan (atau Unduhan) dan ukurannya diverifikasi.
      if (window.BengkelBridge && window.BengkelBridge.available()) {
        const result = await window.BengkelBridge.call('saveBackup', {}, 180000);
        return {
          filename: result.filename,
          location: result.location || 'folder Unduhan',
        };
      }
      return downloadBackupBlob('/api/admin/backup', 'POST');
    },

    downloadBackupFile: (filename) =>
      downloadBackupBlob(
        '/api/admin/backup/file/' + encodeURIComponent(filename),
        'GET'
      ),
  };
})();
