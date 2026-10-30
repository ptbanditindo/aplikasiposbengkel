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

  function extractMessage(detail, fallback) {
    if (!detail) return fallback;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      const first = detail[0];
      if (first && first.msg) return first.msg;
      return fallback;
    }
    if (typeof detail.message === 'string') return detail.message;
    return fallback;
  }

  async function request(path, options) {
    const opts = options || {};
    const init = {
      method: opts.method || 'GET',
      headers: Object.assign({}, opts.headers || {}),
      cache: 'no-store',
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
        'Tidak dapat menghubungi server lokal. Pastikan aplikasi masih berjalan.',
        0,
        null
      );
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
      const message = extractMessage(
        detail,
        'Permintaan gagal (HTTP ' + response.status + ').'
      );
      throw new ApiError(message, response.status, detail);
    }

    try {
      return await response.json();
    } catch (err) {
      return null;
    }
  }

  const qs = (value) => encodeURIComponent(value == null ? '' : String(value));

  window.API = {
    ApiError: ApiError,

    getConfig: () => request('/api/config'),
    health: () => request('/api/health'),

    searchCustomers: (q) => request('/api/customers/search?q=' + qs(q)),
    customerOverview: (q) => request('/api/customers/overview?q=' + qs(q)),
    createCustomer: (data) =>
      request('/api/customers', { method: 'POST', body: data }),
    customerUnits: (customerId) =>
      request('/api/customers/' + customerId + '/units'),
    createUnit: (data) => request('/api/units', { method: 'POST', body: data }),

    stock: () => request('/api/stock'),
    createStock: (data) => request('/api/stock', { method: 'POST', body: data }),
    updateStock: (id, data) =>
      request('/api/stock/' + id, { method: 'PUT', body: data }),
    deleteStock: (id, token) =>
      request('/api/stock/' + id, {
        method: 'DELETE',
        headers: token ? { 'X-Admin-Token': token } : {},
      }),

    jasa: () => request('/api/harga-jasa'),
    createJasa: (data) =>
      request('/api/harga-jasa', { method: 'POST', body: data }),
    updateJasa: (id, data) =>
      request('/api/harga-jasa/' + id, { method: 'PUT', body: data }),
    deleteJasa: (id, token) =>
      request('/api/harga-jasa/' + id, {
        method: 'DELETE',
        headers: token ? { 'X-Admin-Token': token } : {},
      }),

    createTransaction: (data) =>
      request('/api/pos/transaction', { method: 'POST', body: data }),
    records: (q) => request('/api/service-records?q=' + qs(q || '')),
    receipt: (id) => request('/api/service-records/' + id + '/receipt'),
    claim: (id) =>
      request('/api/service-records/' + id + '/claim', { method: 'PUT' }),

    updateBengkel: (data, token) =>
      request('/api/settings/bengkel', {
        method: 'PUT',
        body: data,
        headers: token ? { 'X-Admin-Token': token } : {},
      }),

    updateTelegram: (data, token) =>
      request('/api/settings/telegram', {
        method: 'PUT',
        body: data,
        headers: token ? { 'X-Admin-Token': token } : {},
      }),

    sendTelegramBackup: (token) =>
      request('/api/admin/telegram-backup', {
        method: 'POST',
        headers: token ? { 'X-Admin-Token': token } : {},
      }),

    restoreDatabase: async (file, token) => {
      const form = new FormData();
      form.append('file', file);

      let response;
      try {
        response = await fetch('/api/admin/restore', {
          method: 'POST',
          headers: token ? { 'X-Admin-Token': token } : {},
          body: form,
          cache: 'no-store',
        });
      } catch (err) {
        throw new ApiError('Tidak dapat menghubungi server lokal.', 0, null);
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
          extractMessage(detail, 'Restore gagal (HTTP ' + response.status + ').'),
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
    soldParts: (start, end) =>
      request(
        '/api/reports/sold-parts' +
          (start && end
            ? '?start=' + qs(start) + '&end=' + qs(end)
            : '')
      ),

    downloadBackup: async (token) => {
      const headers = {};
      if (token) headers['X-Admin-Token'] = token;

      let response;
      try {
        response = await fetch('/api/admin/backup', {
          method: 'POST',
          headers: headers,
          cache: 'no-store',
        });
      } catch (err) {
        throw new ApiError('Tidak dapat menghubungi server lokal.', 0, null);
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
          extractMessage(detail, 'Backup gagal (HTTP ' + response.status + ').'),
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
      return filename;
    },
  };
})();
