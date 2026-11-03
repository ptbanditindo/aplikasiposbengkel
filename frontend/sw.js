/* Service worker: shell web tetap terbuka saat offline (W5).
   Endpoint autentikasi/keamanan tidak pernah disajikan dari cache (B-07). */
const CACHE_NAME = 'bengkel-shell-v2';
const SHELL = [
  '/',
  '/manifest.webmanifest',
  '/static/favicon.svg',
  '/static/css/style.css',
  '/static/js/offline-queue.js',
  '/static/js/api-client.js',
  '/static/js/app.js',
];
const NO_CACHE_PREFIXES = [
  '/api/auth/',
  '/api/premium/',
  '/api/license/',
  '/api/accounts',
  '/api/devices',
  '/api/sync/',
  '/api/owner-app/',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type !== 'clear-api-cache') return;
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      const requests = await cache.keys();
      await Promise.all(
        requests
          .filter((request) => {
            const url = new URL(request.url);
            return url.pathname.startsWith('/api/');
          })
          .map((request) => cache.delete(request))
      );
    })
  );
});

async function networkFirst(request, fallback) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    if (fallback) {
      const shell = await caches.match(fallback);
      if (shell) return shell;
    }
    throw err;
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) {
    if (NO_CACHE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
      event.respondWith(fetch(request));
      return;
    }
    event.respondWith(networkFirst(request));
    return;
  }
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, '/'));
    return;
  }
  event.respondWith(cacheFirst(request));
});
