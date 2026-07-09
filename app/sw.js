/* Walking Tour — service worker: app shell + mídia + tiles OSM offline. */
const VERSION = "wt-v19";
const SHELL = [
  "./",
  "index.html",
  "app.css",
  "app.js",
  "manifest.webmanifest",
  "icon-192.png",
  "icon-512.png",
  "vendor/leaflet.js",
  "vendor/leaflet.css",
  "vendor/images/marker-icon.png",
  "vendor/images/marker-icon-2x.png",
  "vendor/images/marker-shadow.png",
  "cities.json"
];

self.addEventListener("install", (ev) => {
  ev.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    await cache.addAll(SHELL);
    // precache por cidade: assets (relativos à raiz do repo) + tiles (absolutos)
    try {
      const cities = await (await fetch("cities.json")).json();
      for (const slug of cities) {
        const pre = await (await fetch("../cities/" + slug + "/precache.json")).json();
        const urls = [...pre.assets.map((a) => "../" + a), ...pre.tiles];
        // addAll falha tudo se 1 falhar; adiciona um a um e tolera falhas
        await Promise.allSettled(urls.map(async (u) => {
          const r = await fetch(u, { mode: u.startsWith("http") ? "no-cors" : "same-origin" });
          if (r) await cache.put(u, r);
        }));
      }
    } catch (e) { /* sem precache.json ainda: segue só com o shell */ }
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (ev) => {
  ev.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (k !== VERSION) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (ev) => {
  const url = ev.request.url;
  const isTile = url.includes("tile.openstreetmap.org");
  const isMedia = /\.(jpg|jpeg|png|mp3|m4a)(\?|$)/i.test(url);
  if (isTile || isMedia) {
    // cache-first (mídia e tiles são imutáveis por versão)
    ev.respondWith((async () => {
      const hit = await caches.match(ev.request, { ignoreSearch: false }) ||
                  await caches.match(url);
      if (hit) return hit;
      try {
        const r = await fetch(ev.request);
        const cache = await caches.open(VERSION);
        cache.put(ev.request, r.clone());
        return r;
      } catch (e) {
        return new Response("", { status: 504 });
      }
    })());
  } else if (ev.request.mode === "navigate") {
    // navegação: network-first, fallback pro index.html do escopo (query varia)
    ev.respondWith((async () => {
      try {
        const r = await fetch(ev.request);
        (await caches.open(VERSION)).put(ev.request, r.clone());
        return r;
      } catch (e) {
        return (await caches.match(ev.request, { ignoreSearch: true })) ||
               (await caches.match(new URL("index.html", self.registration.scope).href)) ||
               new Response("offline", { status: 504 });
      }
    })());
  } else if (ev.request.method === "GET" && url.startsWith(self.location.origin)) {
    // stale-while-revalidate para shell e tour.json
    ev.respondWith((async () => {
      const cached = await caches.match(ev.request);
      const net = fetch(ev.request).then(async (r) => {
        (await caches.open(VERSION)).put(ev.request, r.clone());
        return r;
      }).catch(() => null);
      return cached || (await net) || new Response("offline", { status: 504 });
    })());
  }
});
