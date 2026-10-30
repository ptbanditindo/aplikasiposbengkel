/* Jembatan async ke kode native APK Android.
   Ref: T-03 - permintaan memakai requestId + Promise dengan batas waktu,
   sehingga app.js tidak perlu menangani callback native secara langsung. */
(function () {
  'use strict';

  const pending = new Map();
  let sequence = 0;

  const DEFAULT_TIMEOUT_MS = 120000;

  window.__nativeResult = function (requestId, json) {
    const entry = pending.get(requestId);
    if (!entry) return;
    pending.delete(requestId);
    clearTimeout(entry.timer);

    let data;
    try {
      data = JSON.parse(json);
    } catch (err) {
      entry.reject(new Error('Jawaban dari perangkat tidak dapat dibaca.'));
      return;
    }

    if (data && data.ok) {
      entry.resolve(data);
      return;
    }
    const error = new Error(
      (data && data.message) || 'Perintah ke perangkat gagal.'
    );
    error.code = data && data.code;
    entry.reject(error);
  };

  function available() {
    return typeof window.BengkelNative !== 'undefined' && !!window.BengkelNative;
  }

  function call(method, args, timeoutMs) {
    if (!available()) {
      return Promise.reject(new Error('Fitur perangkat tidak tersedia.'));
    }
    return new Promise((resolve, reject) => {
      const requestId =
        'n' + Date.now().toString(36) + '_' + (++sequence).toString(36);
      const timer = setTimeout(() => {
        pending.delete(requestId);
        reject(new Error('Perangkat tidak merespons. Coba lagi.'));
      }, timeoutMs || DEFAULT_TIMEOUT_MS);

      pending.set(requestId, { resolve, reject, timer });
      try {
        window.BengkelNative.call(
          requestId,
          method,
          JSON.stringify(args || {})
        );
      } catch (err) {
        pending.delete(requestId);
        clearTimeout(timer);
        reject(new Error('Perintah ke perangkat gagal dikirim.'));
      }
    });
  }

  window.BengkelBridge = { available, call };
})();
