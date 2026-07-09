/* Walking Tour — app genérico; cidade vem de cities/<slug>/tour.json */
(function () {
  "use strict";

  // ---------- estado ----------
  const params = new URLSearchParams(location.search);
  const CITY = params.get("city") || localStorage.getItem("wt-city") || "dubrovnik";
  localStorage.setItem("wt-city", CITY);
  const BASE = "../cities/" + CITY + "/";
  const VISITED_KEY = "wt-" + CITY + "-visited";

  let tour = null;
  let map = null;
  let markers = {};          // poiId -> L.Marker
  let audioEl = null;        // player atual
  let wakeLock = null;
  let gpsWatchId = null;
  let gpsLayer = null;

  const $ = (sel) => document.querySelector(sel);

  // ---------- util ----------
  function visited() {
    try { return new Set(JSON.parse(localStorage.getItem(VISITED_KEY) || "[]")); }
    catch { return new Set(); }
  }
  function setVisited(id, on) {
    const v = visited();
    if (on) v.add(id); else v.delete(id);
    localStorage.setItem(VISITED_KEY, JSON.stringify([...v]));
  }
  function haversineM(a, b) {
    const R = 6371000, rad = Math.PI / 180;
    const dLat = (b[0] - a[0]) * rad, dLng = (b[1] - a[1]) * rad;
    const s = Math.sin(dLat / 2) ** 2 +
      Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }
  function fmtTime(s) {
    if (!isFinite(s)) return "0:00";
    const m = Math.floor(s / 60), r = Math.floor(s % 60);
    return m + ":" + String(r).padStart(2, "0");
  }
  let toastTimer = null;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 3500);
  }
  function fail(msg) {
    const e = $("#app-error");
    e.textContent = msg; e.hidden = false;
    $("#map").style.display = "none";
  }

  // ---------- mapa ----------
  function initMap() {
    map = L.map("map", { zoomControl: false });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    if (tour.route && tour.route.length > 1) {
      L.polyline(tour.route, { color: "#0e7c66", weight: 4, opacity: 0.75, dashArray: "1 8" }).addTo(map);
    }
    const v = visited();
    const pts = [];
    for (const poi of tour.pois) {
      pts.push([poi.lat, poi.lng]);
      const mk = L.marker([poi.lat, poi.lng], { icon: numIcon(poi.order, v.has(poi.id)) })
        .addTo(map).on("click", () => openPoi(poi.id));
      markers[poi.id] = mk;
    }
    map.fitBounds(L.latLngBounds(pts), { padding: [36, 36] });
  }
  function numIcon(n, isVisited) {
    return L.divIcon({
      className: "",
      html: '<div class="poi-marker' + (isVisited ? " visited" : "") + '">' + n + "</div>",
      iconSize: [30, 30], iconAnchor: [15, 15]
    });
  }
  function refreshMarker(poi) {
    markers[poi.id] && markers[poi.id].setIcon(numIcon(poi.order, visited().has(poi.id)));
  }

  // ---------- GPS ----------
  function toggleGps() {
    const btn = $("#btn-gps");
    if (gpsWatchId != null) {
      navigator.geolocation.clearWatch(gpsWatchId);
      gpsWatchId = null;
      if (gpsLayer) { map.removeLayer(gpsLayer); gpsLayer = null; }
      btn.classList.remove("on");
      return;
    }
    if (!("geolocation" in navigator)) { toast("GPS indisponível — use o mapa"); return; }
    gpsWatchId = navigator.geolocation.watchPosition((pos) => {
      const ll = [pos.coords.latitude, pos.coords.longitude];
      if (!gpsLayer) {
        gpsLayer = L.layerGroup([
          L.circle(ll, { radius: pos.coords.accuracy, color: "#2563eb", weight: 1, fillOpacity: 0.08 }),
          L.circleMarker(ll, { radius: 8, color: "#fff", weight: 2, fillColor: "#2563eb", fillOpacity: 1 })
        ]).addTo(map);
      } else {
        const [circle, dot] = gpsLayer.getLayers();
        circle.setLatLng(ll); circle.setRadius(pos.coords.accuracy);
        dot.setLatLng(ll);
      }
      btn.classList.add("on");
    }, () => {
      toast("GPS indisponível — use o mapa");
      navigator.geolocation.clearWatch(gpsWatchId); gpsWatchId = null;
      btn.classList.remove("on");
    }, { enableHighAccuracy: true, maximumAge: 5000 });
  }

  // ---------- lista ----------
  function renderList() {
    const v = visited();
    const box = $("#list");
    box.innerHTML = "";
    tour.pois.forEach((poi, i) => {
      const next = tour.pois[i + 1];
      let nextTxt = "Fim do tour 🎉";
      if (next) {
        const m = Math.round(haversineM([poi.lat, poi.lng], [next.lat, next.lng]));
        nextTxt = "→ " + next.name + ": " + (m >= 1000 ? (m / 1000).toFixed(1) + " km" : m + " m") +
          " · ~" + Math.max(1, Math.ceil(m / 75)) + " min a pé";
      }
      const item = document.createElement("div");
      item.className = "list-item" + (v.has(poi.id) ? " visited" : "");
      const thumb = poi.photos && poi.photos[0]
        ? '<img src="' + BASE + poi.photos[0].file + '" alt="" loading="lazy">' : "";
      item.innerHTML =
        '<div class="num">' + poi.order + "</div>" + thumb +
        '<div class="li-info"><div class="li-name">' + poi.name + "</div>" +
        '<div class="li-next">' + nextTxt + "</div></div>" +
        (v.has(poi.id) ? '<div class="li-check">✓</div>' : "");
      item.addEventListener("click", () => openPoi(poi.id));
      box.appendChild(item);
    });
  }
  function setView(mode) {
    localStorage.setItem("wt-view", mode);
    const isList = mode === "list";
    $("#list").hidden = !isList;
    $("#map").style.display = isList ? "none" : "";
    $("#btn-view").textContent = isList ? "🗺 Mapa" : "☰ Lista";
    if (isList) renderList(); else map && map.invalidateSize();
  }

  // ---------- wake lock ----------
  async function requestWakeLock() {
    try {
      if ("wakeLock" in navigator) wakeLock = await navigator.wakeLock.request("screen");
    } catch { /* sem suporte/permissão: segue sem */ }
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && wakeLock !== null) requestWakeLock();
  });

  // ---------- painel do POI ----------
  function openPoi(id) {
    const poi = tour.pois.find((p) => p.id === id);
    if (!poi) return;
    stopAudio();
    const v = visited();
    const c = $("#sheet-content");

    const photosHtml = (poi.photos || []).map((ph) =>
      '<figure><img src="' + BASE + ph.file + '" alt="' + (ph.caption || poi.name) + '" loading="lazy">' +
      "<figcaption>" + (ph.caption || "") +
      (ph.credit ? ' <span class="credit">· ' + ph.credit + "</span>" : "") +
      "</figcaption></figure>").join("");

    let audioHtml;
    if (poi.audio) {
      audioHtml =
        '<div class="player">' +
        '<div class="player-row">' +
        '<button class="play" id="pl-play" aria-label="Tocar narração">▶</button>' +
        '<input type="range" id="pl-seek" min="0" max="100" value="0" step="0.1" aria-label="Progresso">' +
        '<span class="time" id="pl-time">0:00</span>' +
        '<button class="rate" id="pl-rate" aria-label="Velocidade">1×</button>' +
        "</div></div>" +
        '<details class="transcript"><summary>Ler transcrição</summary>' +
        '<div class="script-text">' + poi.script + "</div></details>";
    } else {
      audioHtml =
        '<span class="badge-prep">🎙️ Áudio em preparo — leia por enquanto:</span>' +
        '<div class="script-text">' + poi.script + "</div>";
    }

    c.innerHTML =
      '<div class="sheet-head"><div class="num">' + poi.order + "</div>" +
      "<h2>" + poi.name + "</h2>" +
      '<button class="close" id="sheet-close" aria-label="Fechar">✕</button></div>' +
      (photosHtml ? '<div class="photos">' + photosHtml + "</div>" : "") +
      '<div class="sheet-body">' + audioHtml +
      (poi.practical ? '<div class="practical">ℹ️ ' + poi.practical + "</div>" : "") +
      '<div class="sheet-actions">' +
      '<a class="btn-maps" href="' + poi.maps_url + '" target="_blank" rel="noopener">🧭 Abrir no Maps</a>' +
      '<button class="btn-visited' + (v.has(poi.id) ? " on" : "") + '" id="btn-visited">' +
      (v.has(poi.id) ? "✓ Visitado" : "Marcar visitado") + "</button>" +
      "</div></div>";

    $("#sheet").hidden = false;
    $("#sheet-close").addEventListener("click", closeSheet);
    $("#btn-visited").addEventListener("click", () => {
      const on = !visited().has(poi.id);
      setVisited(poi.id, on);
      const b = $("#btn-visited");
      b.classList.toggle("on", on);
      b.textContent = on ? "✓ Visitado" : "Marcar visitado";
      refreshMarker(poi);
      if (!$("#list").hidden) renderList();
    });
    if (poi.audio) bindPlayer(poi);
    if (map && $("#list").hidden) map.panTo([poi.lat, poi.lng]);
  }
  function closeSheet() { $("#sheet").hidden = true; stopAudio(); }

  const RATES = [1, 1.25, 1.5];
  function bindPlayer(poi) {
    audioEl = new Audio(BASE + poi.audio);
    audioEl.preload = "metadata";
    let rateIdx = 0;
    const play = $("#pl-play"), seek = $("#pl-seek"), time = $("#pl-time"), rate = $("#pl-rate");

    play.addEventListener("click", () => {
      if (audioEl.paused) {
        audioEl.play().then(() => {
          requestWakeLock();
          if ("mediaSession" in navigator) {
            navigator.mediaSession.metadata = new MediaMetadata({
              title: poi.name, artist: "Walking Tour — " + tour.city
            });
          }
        }).catch(() => toast("Não consegui tocar o áudio"));
      } else audioEl.pause();
    });
    audioEl.addEventListener("play", () => { play.textContent = "⏸"; });
    audioEl.addEventListener("pause", () => { play.textContent = "▶"; });
    audioEl.addEventListener("timeupdate", () => {
      if (audioEl.duration) seek.value = (audioEl.currentTime / audioEl.duration) * 100;
      time.textContent = fmtTime(audioEl.currentTime);
    });
    audioEl.addEventListener("ended", () => { play.textContent = "▶"; seek.value = 0; });
    audioEl.addEventListener("error", () => toast("Áudio indisponível offline — recarregue no wifi"));
    seek.addEventListener("input", () => {
      if (audioEl.duration) audioEl.currentTime = (seek.value / 100) * audioEl.duration;
    });
    rate.addEventListener("click", () => {
      rateIdx = (rateIdx + 1) % RATES.length;
      audioEl.playbackRate = RATES[rateIdx];
      rate.textContent = RATES[rateIdx] + "×";
    });
  }
  function stopAudio() {
    if (audioEl) { audioEl.pause(); audioEl.src = ""; audioEl = null; }
  }

  // ---------- boot ----------
  async function boot() {
    try {
      const r = await fetch(BASE + "tour.json");
      if (!r.ok) throw new Error("HTTP " + r.status);
      tour = await r.json();
    } catch (e) {
      fail('Não consegui carregar o tour "' + CITY + '" (' + e.message +
        "). Confira a conexão e recarregue.");
      return;
    }
    document.title = tour.title || "Walking Tour";
    $("#city-title").textContent = (tour.city ? tour.city + " — " : "") + (tour.title || "");
    initMap();
    $("#btn-view").addEventListener("click", () =>
      setView($("#list").hidden ? "list" : "map"));
    $("#btn-gps").addEventListener("click", toggleGps);
    if (localStorage.getItem("wt-view") === "list") setView("list");

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    }
  }
  boot();
})();
