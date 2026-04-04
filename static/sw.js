/* Tessymetry PWA — network-first with offline fallback for same-origin assets */
const STATIC_CACHE = "tessymetry-v1";

const PRECACHE_URLS = [
  "/dashboard",
  "/static/dashboard.css",
  "/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) =>
        Promise.all(
          PRECACHE_URLS.map((url) => cache.add(url).catch(() => {}))
        )
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(req)
      .then((response) => {
        if (
          response &&
          response.status === 200 &&
          url.origin === self.location.origin
        ) {
          const copy = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(req, copy));
        }
        return response;
      })
      .catch(() => caches.match(req))
  );
});
