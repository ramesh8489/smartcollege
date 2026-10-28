// Takshashila University Smart College - Progressive Web App Service Worker
const CACHE_NAME = 'takshashila-pwa-v1';
const OFFLINE_URL = '/offline/';

const CORE_ASSETS = [
  '/',
  OFFLINE_URL,
  '/static/css/theme.css',
  '/static/manifest.webmanifest',
  '/static/images/pwa/icon-192.png',
  '/static/images/pwa/icon-512.png',
  '/static/images/pwa/apple-touch-icon.png'
];

// Install Event: cache core offline assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      for (const asset of CORE_ASSETS) {
        try {
          await cache.add(asset);
        } catch (err) {
          console.warn('[PWA SW] Pre-caching asset failed:', asset, err);
        }
      }
    }).then(() => self.skipWaiting())
  );
});

// Activate Event: clean up outdated caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            console.log('[PWA SW] Clearing old cache:', name);
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event: Network-first for pages, Stale-while-revalidate for static assets
self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Only handle GET requests
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  // Exclude admin or live payment endpoints from caching
  if (url.pathname.startsWith('/admin/')) {
    return;
  }

  // HTML page navigation: Network first, fallback to offline page
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          return networkResponse;
        })
        .catch(async () => {
          const cache = await caches.open(CACHE_NAME);
          const cachedResponse = await cache.match(request);
          if (cachedResponse) {
            return cachedResponse;
          }
          const offlineFallback = await cache.match(OFFLINE_URL);
          return offlineFallback || new Response('Offline - No connection available', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
          });
        })
    );
    return;
  }

  // Static Assets (CSS, JS, Fonts, Images): Stale-while-revalidate
  if (
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('fonts.googleapis.com') ||
    url.hostname.includes('fonts.gstatic.com')
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        const fetchPromise = fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        }).catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
      })
    );
    return;
  }
});
