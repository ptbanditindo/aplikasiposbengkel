/* Antrean tulis offline berbasis IndexedDB (K-23, W5). */
(function () {
  'use strict';

  const DB_NAME = 'bengkel-offline';
  const DB_VERSION = 1;
  const STORE = 'outbox';
  let opening = null;

  function openDb() {
    if (opening) return opening;
    opening = new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error('Penyimpanan offline tidak tersedia di peramban ini.'));
        return;
      }
      const request = window.indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('status', 'status', { unique: false });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Gagal membuka antrean.'));
    });
    return opening;
  }

  function deviceToken() {
    try {
      return (window.sessionStorage.getItem('bengkel.deviceToken') || '').trim();
    } catch (err) {
      return '';
    }
  }

  function installToken() {
    const injected = window.__BENGKEL_ADMIN_TOKEN__;
    return typeof injected === 'string' ? injected.trim() : '';
  }

  async function enqueue(entry) {
    const record = {
      method: (entry.method || 'POST').toUpperCase(),
      url: entry.url,
      body: entry.body == null ? null : entry.body,
      label: entry.label || entry.url,
      request_id: entry.request_id || '',
      status: 'pending',
      attempts: 0,
      error: '',
      created_at: new Date().toISOString(),
    };
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      const request = tx.objectStore(STORE).add(record);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function all() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const request = tx.objectStore(STORE).getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  async function remove(id) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function markFailed(id, message) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      const store = tx.objectStore(STORE);
      const request = store.get(id);
      request.onsuccess = () => {
        const row = request.result;
        if (!row) return;
        row.status = 'failed';
        row.attempts = (row.attempts || 0) + 1;
        row.error = String(message || '').slice(0, 500);
        store.put(row);
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function count() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const request = tx.objectStore(STORE).count();
      request.onsuccess = () => resolve(request.result || 0);
      request.onerror = () => reject(request.error);
    });
  }

  function notify() {
    window.dispatchEvent(new CustomEvent('bengkel:offline-queue'));
  }

  async function flush() {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      return { sent: 0, failed: 0, pending: await count().catch(() => 0) };
    }
    let sent = 0;
    let failed = 0;
    let items = [];
    try {
      items = await all();
    } catch (err) {
      return { sent: 0, failed: 0, pending: 0 };
    }
    for (const item of items) {
      if (item.status !== 'pending') continue;
      const headers = { 'Content-Type': 'application/json' };
      const install = installToken();
      if (install) headers['X-Install-Token'] = install;
      const device = deviceToken();
      if (device) headers['X-Device-Token'] = device;
      let response;
      try {
        response = await fetch(item.url, {
          method: item.method,
          headers,
          body: item.body == null ? undefined : JSON.stringify(item.body),
          credentials: 'same-origin',
          cache: 'no-store',
        });
      } catch (err) {
        break;
      }
      if (response.ok || response.status === 204) {
        await remove(item.id);
        sent += 1;
        continue;
      }
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('bengkel:unauthorized'));
        break;
      }
      if (response.status >= 400 && response.status < 500) {
        let message = response.statusText;
        try {
          const data = await response.json();
          message = typeof data.detail === 'string' ? data.detail : message;
        } catch (err) {
          /* biarkan status teks */
        }
        await markFailed(item.id, message);
        failed += 1;
        continue;
      }
      break;
    }
    notify();
    return { sent, failed, pending: await count().catch(() => 0) };
  }

  window.addEventListener('online', () => {
    window.setTimeout(() => {
      flush().catch(() => {});
    }, 800);
  });

  window.OfflineQueue = {
    enqueue,
    flush,
    all,
    remove,
    count,
    notify,
  };
})();
