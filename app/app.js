"use strict";

const AI_CONFIG = { name: "SPHEREx Analyzer" };
const API_BASE = window.SPHEREX_API_BASE || `${window.location.protocol}//${window.location.hostname || "localhost"}:8000`;
const state = {
  inputMode: "sky",
  queryMode: "name",
  screen: "observatory",
  view: "single",
  data: null,
  activeEpoch: 0,
  differenceEpoch: 1,
  blinkTimer: null,
  blinkPlaying: true,
  history: [],
  analyzerBusy: false,
  analyzerRequestId: 0,
  analyzerController: null,
  searchRequestId: 0,
  searchController: null
};

const elements = Object.fromEntries([
  "search-form", "target-query", "ra-query", "dec-query", "coordinate-frame", "coordinate-one-label", "coordinate-two-label", "field-size", "bandpass-select", "epoch-count", "earth-query", "name-field", "coordinate-fields", "earth-field", "sky-entry-tabs", "search-help", "search-message",
  "target-summary", "data-source", "sky-canvas", "epoch-label", "observation-meta", "dot-hud",
  "blink-controls", "blink-toggle", "blink-speed", "blink-speed-value", "epoch-controls", "epoch-range", "epoch-range-value", "difference-controls", "difference-epoch", "wipe-controls", "wipe-range", "wipe-range-value", "wipe-view", "wipe-canvas-a", "wipe-canvas-b", "wipe-divider", "wipe-label-a", "wipe-label-b", "comparison-view", "comparison-canvas-a", "comparison-canvas-b", "comparison-label-a", "comparison-label-b", "spectrum-canvas", "spectrum-tooltip",
  "chat-form", "chat-input", "chat-messages", "suggested-question", "assistant-name", "analyzer-token",
  "workspace", "open-data-products", "data-products-dialog", "close-data-products", "data-source-detail", "data-product-list", "refresh-archive", "assistant-activity", "spectrum-source", "spectrum-target-name", "feature-list",
  "benchmark-list", "benchmark-count", "benchmark-disclosure", "open-data-inspector", "data-inspector-dialog", "close-data-inspector", "data-inspector-summary", "epoch-inspector-rows", "spectrum-inspector-rows", "spectrum-inspector-empty", "assistant-mode-status", "spectrum-series-legend", "spectrum-array-count", "spectrum-snr"
].map((id) => [id, document.getElementById(id)]));

function setMessage(text, isError = false) {
  elements["search-message"].textContent = text;
  elements["search-message"].classList.toggle("error", isError);
}

function formatNumber(value, digits = 4) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || `Request failed (${response.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function updateInputMode(mode) {
  state.inputMode = mode;
  document.querySelectorAll("[data-input-mode]").forEach((button) => {
    const active = button.dataset.inputMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  elements["sky-entry-tabs"].hidden = mode !== "sky";
  elements["name-field"].hidden = mode !== "sky" || state.queryMode !== "name";
  elements["coordinate-fields"].hidden = mode !== "sky" || state.queryMode !== "coordinates";
  elements["earth-field"].hidden = mode !== "earth";
  elements["target-query"].required = mode === "sky" && state.queryMode === "name";
  elements["ra-query"].required = mode === "sky" && state.queryMode === "coordinates";
  elements["dec-query"].required = mode === "sky" && state.queryMode === "coordinates";
  elements["earth-query"].required = mode === "earth";
  elements["search-help"].textContent = mode === "earth"
    ? "A city, neighborhood, district, address, or latitude/longitude resolves the sky directly overhead."
    : state.queryMode === "coordinates"
      ? "Enter a coordinate pair in the selected Astropy frame; sexagesimal or decimal formats are accepted."
      : "Search an astronomical object name through the name resolver.";
}

function updateQueryMode(mode) {
  state.queryMode = mode;
  document.querySelectorAll("[data-query-mode]").forEach((button) => {
    const active = button.dataset.queryMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  updateInputMode(state.inputMode);
}

function setScreen(screen) {
  state.screen = screen;
  elements.workspace.dataset.screen = screen;
  document.querySelectorAll("[data-screen-tab]").forEach((button) => {
    const active = button.dataset.screenTab === screen;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  if (screen === "spectrum" && state.data) renderSpectrum(state.data);
}

async function observeTarget(query, refreshArchive = false) {
  let targetQuery = query;
  if (!targetQuery) {
    if (state.inputMode === "earth") targetQuery = elements["earth-query"].value;
    else if (state.queryMode === "coordinates") targetQuery = `${elements["coordinate-frame"].value.trim()}|${elements["ra-query"].value.trim()}, ${elements["dec-query"].value.trim()}`;
    else targetQuery = elements["target-query"].value;
  }
  targetQuery = (targetQuery || "").trim();
  if (!targetQuery) return;
  const requestId = ++state.searchRequestId;
  state.searchController?.abort();
  state.analyzerController?.abort();
  state.analyzerController = null;
  state.analyzerRequestId += 1;
  state.analyzerBusy = false;
  elements["assistant-activity"].hidden = true;
  elements["chat-form"].querySelector("button").disabled = false;
  document.querySelectorAll("[data-prompt]").forEach((button) => { button.disabled = false; });
  elements["assistant-mode-status"].textContent = "Target change requested · previous analysis cancelled";
  const controller = new AbortController();
  state.searchController = controller;
  let timedOut = false;
  const timeoutId = window.setTimeout(() => { timedOut = true; controller.abort(); }, 210_000);
  const searchButton = elements["search-form"].querySelector("button[type='submit']");
  searchButton.disabled = true;
  setMessage(refreshArchive ? "Retrying the live IRSA archive…" : "Resolving target and loading observations…");
  try {
    const params = new URLSearchParams({
      q: targetQuery,
      input_mode: state.inputMode,
      refresh_archive: String(refreshArchive),
      bandpass: elements["bandpass-select"].value,
      size_deg: elements["field-size"].value,
      max_epochs: elements["epoch-count"].value
    });
    const data = await fetchJson(`${API_BASE}/api/sky?${params.toString()}`, { signal: controller.signal });
    const metadata = data.metadata || {};
    if (!Array.isArray(data.epochs) || data.epochs.length === 0) {
      throw new Error("The observation response contains no epochs.");
    }
    if (!data.coordinates || !Number.isFinite(Number(data.coordinates.ra_deg)) || !Number.isFinite(Number(data.coordinates.dec_deg))) {
      throw new Error("The observation response does not include resolved ICRS coordinates.");
    }
    if (requestId !== state.searchRequestId) return;
    state.data = data;
    state.activeEpoch = 0;
    state.differenceEpoch = 1;
    elements["epoch-range"].max = String(Math.max(0, data.epochs.length - 1));
    elements["epoch-range"].value = "0";
    elements["epoch-controls"].hidden = state.view !== "single" || data.epochs.length < 2;
    elements["wipe-controls"].hidden = state.view !== "wipe" || data.epochs.length < 2;
    elements["difference-controls"].hidden = state.view !== "difference" || data.epochs.length < 2;
    elements["difference-epoch"].replaceChildren(...data.epochs.slice(1).map((epoch, index) => {
      const option = document.createElement("option");
      option.value = String(index + 1);
      option.textContent = `Epoch ${index + 2}${epoch.date_str ? ` · ${epoch.date_str}` : ""}`;
      return option;
    }));
    elements["blink-controls"].hidden = state.view !== "blink";
    state.history = [];
    elements["chat-messages"].replaceChildren();
    elements["suggested-question"].replaceChildren();
    renderTargetSummary(data);
    renderObservationMeta(data);
    renderSpectrum(data);
    elements["open-data-products"].disabled = false;
    elements["open-data-inspector"].disabled = false;
    if (elements["data-products-dialog"].open) renderDataProducts();
    const dataSource = metadata.data_source || "unknown";
    const sourceLabels = {
      irsa_live_tap: "LIVE IRSA DATA",
      simulated: "SIMULATED DATA"
    };
    elements["data-source"].textContent = metadata.cache_status === "stale_archive_fallback"
      ? "CACHED IRSA DATA · STALE"
      : sourceLabels[dataSource]
      || dataSource.replaceAll("_", " ").toUpperCase();
    elements["data-source"].title = `Data source: ${dataSource}; cache: ${metadata.cache_status || "unknown"}`;
    elements["assistant-mode-status"].textContent = "Grounded in the active target · no image pixels are sent";
    setMessage(metadata.cache_status === "stale_archive_fallback"
      ? `Showing the last successful archive result (${metadata.stale_age_days} days old); the latest refresh did not return usable files.`
      : dataSource === "irsa_live_tap"
      ? `Loaded ${data.epochs.length} live archive epoch(s).`
      : `Loaded ${data.epochs.length} simulated epoch(s); archive FITS images were not available.`);
    renderCurrentView();
    if (state.view === "blink") startBlink();
    addMessage("assistant", `Resolved ${metadata.name || "target"} to RA ${formatNumber(data.coordinates.ra_deg, 5)}°, Dec ${formatNumber(data.coordinates.dec_deg, 5)}°. Ask about the returned archive measurements.`);
  } catch (error) {
    if (requestId === state.searchRequestId) {
      const message = timedOut
        ? "The archive lookup timed out. The current target remains loaded; retry when the archive is reachable."
        : error.name === "AbortError"
          ? "Lookup cancelled."
          : error.message;
      setMessage(message, true);
    }
  } finally {
    window.clearTimeout(timeoutId);
    if (requestId === state.searchRequestId) {
      searchButton.disabled = false;
      state.searchController = null;
    }
  }
}

function renderTargetSummary(data) {
  const summary = elements["target-summary"];
  const metadata = data.metadata || {};
  const coordinates = data.coordinates || {};
  summary.hidden = false;
  summary.replaceChildren();
  const title = document.createElement("div");
  title.className = "summary-name";
  title.textContent = metadata.name || "Resolved field";
  summary.append(title);
  const fields = [
    ["Resolved frame", coordinates.frame || "ICRS"],
    ["RA", `${formatNumber(coordinates.ra_deg, 6)}°`],
    ["Dec", `${formatNumber(coordinates.dec_deg, 6)}°`],
    ["Input mode", coordinates.input_mode || "Sky"],
    ...(coordinates.input_frame ? [["Input frame", coordinates.input_frame]] : []),
    ...(coordinates.earth_lat != null && coordinates.earth_lon != null
      ? [["Earth location", `${formatNumber(coordinates.earth_lat, 5)}°, ${formatNumber(coordinates.earth_lon, 5)}°`]] : []),
    ...(coordinates.observation_time_utc ? [["Zenith time (UTC)", coordinates.observation_time_utc]] : []),
    ...(metadata.proper_motion_known ? [["Proper motion", `${formatNumber(metadata.proper_motion, 4)}″/yr`]] : []),
    ...(metadata.spectral_type ? [["Spectral type", metadata.spectral_type]] : []),
    ...(metadata.classification ? [["Classification", metadata.classification]] : []),
    ...Object.entries(metadata.catalog_fields || {}).map(([key, value]) => [key, String(value)])
  ];
  const grid = document.createElement("div");
  grid.className = "summary-grid";
  for (const [label, value] of fields) {
    const cell = document.createElement("div");
    cell.append(document.createTextNode(`${label}:`));
    const strong = document.createElement("strong");
    strong.textContent = value;
    cell.append(strong);
    grid.append(cell);
  }
  summary.append(grid);
}

function renderObservationMeta(data) {
  const metadata = data.metadata || {};
  const epochs = data.epochs;
  const first = epochs[0];
  elements["observation-meta"].textContent =
    `${metadata.bandpass || first.bandpass || "Archive"} · ${metadata.pixel_scale_arcsec ? `${metadata.pixel_scale_arcsec} arcsec/pixel · ` : ""}${epochs.length} epoch(s) · ${first.date_str || "date n/a"} → ${epochs.at(-1).date_str || "date n/a"}`;
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  elements["blink-controls"].hidden = view !== "blink";
  elements["epoch-controls"].hidden = view !== "single" || !state.data || state.data.epochs.length < 2;
  elements["wipe-controls"].hidden = view !== "wipe" || !state.data || state.data.epochs.length < 2;
  elements["difference-controls"].hidden = view !== "difference" || !state.data || state.data.epochs.length < 2;
  if (view === "blink") startBlink();
  else stopBlink();
  renderCurrentView();
}

function getImageData(epoch) {
  const pixels = epoch?.pixels_u8;
  if (!Array.isArray(pixels) || !pixels.length || !Array.isArray(pixels[0])) {
    throw new Error("An epoch is missing its image pixels.");
  }
  const height = pixels.length;
  const width = pixels[0].length;
  const image = new ImageData(width, height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const i = (y * width + x) * 4;
      const value = Number(pixels[y][x]) || 0;
      image.data[i] = value;
      image.data[i + 1] = value;
      image.data[i + 2] = value;
      image.data[i + 3] = 255;
    }
  }
  return image;
}

function differenceImage(epochA, epochB) {
  const a = epochA.pixels_u8;
  const b = epochB.pixels_u8;
  const height = Math.min(a.length, b.length);
  const width = Math.min(a[0].length, b[0].length);
  const differences = [];
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) differences.push(Number(b[y][x]) - Number(a[y][x]));
  }
  let center = differences.reduce((sum, value) => sum + value, 0) / Math.max(1, differences.length);
  let sigma = 0;
  let sample = differences;
  for (let iteration = 0; iteration < 4; iteration += 1) {
    sigma = Math.sqrt(sample.reduce((sum, value) => sum + (value - center) ** 2, 0) / Math.max(1, sample.length));
    const clipped = differences.filter((value) => Math.abs(value - center) <= Math.max(1, 3 * sigma));
    if (!clipped.length || clipped.length === sample.length) break;
    sample = clipped;
    center = sample.reduce((sum, value) => sum + value, 0) / sample.length;
  }
  const threshold = Math.max(1, 3 * sigma);
  const image = new ImageData(width, height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const diff = Number(b[y][x]) - Number(a[y][x]) - center;
      const i = (y * width + x) * 4;
      if (diff > threshold) {
        image.data[i] = 255;
        image.data[i + 1] = Math.max(70, 190 - Math.abs(diff));
        image.data[i + 2] = 18;
        image.data[i + 3] = 255;
      } else if (diff < -threshold) {
        image.data[i] = 0;
        image.data[i + 1] = 190;
        image.data[i + 2] = 235;
        image.data[i + 3] = 255;
      } else {
        image.data[i] = 5;
        image.data[i + 1] = 8;
        image.data[i + 2] = 14;
        image.data[i + 3] = 255;
      }
    }
  }
  return image;
}

function drawCanvasImage(canvas, image, epoch = null, vector = null) {
  const cssWidth = canvas.clientWidth || image.width;
  const cssHeight = canvas.clientHeight || cssWidth * image.height / image.width;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.round(cssWidth * dpr));
  const height = Math.max(1, Math.round(cssHeight * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  const buffer = document.createElement("canvas");
  buffer.width = image.width;
  buffer.height = image.height;
  buffer.getContext("2d").putImageData(image, 0, 0);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.clearRect(0, 0, width, height);
  context.drawImage(buffer, 0, 0, width, height);
  const point = epoch?.target_pixel_pos;
  if (Array.isArray(point) && point.length === 2 && point.every(Number.isFinite)) {
    const scaleX = width / image.width, scaleY = height / image.height;
    const px = point[0] * scaleX, py = point[1] * scaleY;
    context.save();
    context.strokeStyle = "rgba(255,255,255,.92)";
    context.lineWidth = Math.max(1, dpr * 1.1);
    context.beginPath();
    const reticle = Math.max(8 * dpr, Math.min(width, height) * .035);
    context.rect(px - reticle / 2, py - reticle / 2, reticle, reticle);
    context.stroke();
    if (vector && vector.every(Number.isFinite)) {
      context.strokeStyle = "rgba(255,255,255,.7)";
      context.beginPath();
      context.moveTo(px, py);
      context.lineTo(vector[0] * scaleX, vector[1] * scaleY);
      context.stroke();
    }
    context.restore();
  }
}

function renderCurrentView() {
  const canvas = elements["sky-canvas"];
  const context = canvas.getContext("2d");
  const comparisonView = elements["comparison-view"];
  const wipeView = elements["wipe-view"];
  const isSplit = state.view === "split";
  const isWipe = state.view === "wipe";
  canvas.hidden = isSplit || isWipe;
  comparisonView.hidden = !isSplit;
  wipeView.hidden = !isWipe;
  elements["epoch-label"].hidden = isSplit || isWipe;
  if (!state.data) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }
  const epochs = state.data.epochs;
  let epochIndex = Math.min(state.activeEpoch, epochs.length - 1);
  let image;
  let reticleEpoch = null;
  let motionVector = null;
  if (isSplit) {
    if (epochs.length < 2) {
      elements["comparison-label-a"].textContent = "Need 2 epochs";
      elements["comparison-label-b"].textContent = "Need 2 epochs";
      return;
    }
    const epochA = epochs[0], epochB = epochs[1];
    elements["comparison-label-a"].textContent = `E${epochA.epoch_index || 1} · ${epochA.date_str || "date n/a"}`;
    elements["comparison-label-b"].textContent = `E${epochB.epoch_index || 2} · ${epochB.date_str || "date n/a"}`;
    for (const [canvasId, epoch] of [["comparison-canvas-a", epochA], ["comparison-canvas-b", epochB]]) {
      drawCanvasImage(elements[canvasId], getImageData(epoch), epoch, epoch.target_pixel_pos === epochA.target_pixel_pos ? null : epochA.target_pixel_pos);
    }
    return;
  }
  if (isWipe) {
    if (epochs.length < 2) return;
    const epochA = epochs[0], epochB = epochs[1];
    for (const [canvasId, epoch] of [["wipe-canvas-a", epochA], ["wipe-canvas-b", epochB]]) {
      drawCanvasImage(elements[canvasId], getImageData(epoch), epoch, epoch.target_pixel_pos === epochA.target_pixel_pos ? null : epochA.target_pixel_pos);
    }
    elements["wipe-label-a"].textContent = `E${epochA.epoch_index || 1} · ${epochA.date_str || "date n/a"}`;
    elements["wipe-label-b"].textContent = `E${epochB.epoch_index || 2} · ${epochB.date_str || "date n/a"}`;
    const reveal = Number(elements["wipe-range"].value);
    wipeView.style.setProperty("--wipe-percent", `${reveal}%`);
    elements["wipe-range-value"].value = `${reveal}%`;
    return;
  }
  if (state.view === "difference" && epochs.length > 1) {
    const compareIndex = Math.max(1, Math.min(Number(elements["difference-epoch"].value || state.differenceEpoch), epochs.length - 1));
    state.differenceEpoch = compareIndex;
    image = differenceImage(epochs[0], epochs[compareIndex]);
    reticleEpoch = epochs[compareIndex];
    motionVector = epochs[0].target_pixel_pos;
    elements["epoch-label"].textContent = `${epochs[compareIndex].date_str || `Epoch ${compareIndex + 1}`} − ${epochs[0].date_str || "Epoch 1"}`;
  } else {
    if (state.view === "difference" && epochs.length < 2) {
      elements["epoch-label"].textContent = "Need at least two epochs";
    } else {
      epochIndex = state.activeEpoch;
      state.activeEpoch = epochIndex;
      image = getImageData(epochs[epochIndex]);
      reticleEpoch = epochs[epochIndex];
      motionVector = epochIndex > 0 ? epochs[0].target_pixel_pos : null;
      elements["epoch-label"].textContent = `E${epochs[epochIndex].epoch_index || epochIndex + 1} · ${epochs[epochIndex].date_str}`;
      elements["epoch-range"].value = String(epochIndex);
      elements["epoch-range-value"].value = `E${epochIndex + 1} · ${epochs[epochIndex].date_str || "date n/a"}`;
    }
  }
  if (image) drawCanvasImage(canvas, image, reticleEpoch || epochs[epochIndex], motionVector);
}

function startBlink() {
  stopBlink();
  if (!state.data || state.data.epochs.length < 2 || !state.blinkPlaying) return;
  const fps = Number(elements["blink-speed"].value);
  elements["blink-speed-value"].value = `${fps} fps`;
  state.blinkTimer = window.setInterval(() => {
    state.activeEpoch = (state.activeEpoch + 1) % state.data.epochs.length;
    renderCurrentView();
  }, 1000 / fps);
}

function stopBlink() {
  if (state.blinkTimer !== null) {
    window.clearInterval(state.blinkTimer);
    state.blinkTimer = null;
  }
}

function seriesColor(seriesId) {
  let hash = 0;
  for (const character of String(seriesId)) hash = (hash * 31 + character.charCodeAt(0)) | 0;
  return `hsl(${Math.abs(hash) % 360} 78% 62%)`;
}

function drawSpectrum(data) {
  const canvas = elements["spectrum-canvas"];
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(320, Math.round(canvas.clientWidth * ratio));
  const height = Math.round(width * 340 / 1100);
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#070d16";
  ctx.fillRect(0, 0, width, height);
  const points = (Array.isArray(data?.spectral_points) ? data.spectral_points : [])
    .filter((point) => Number.isFinite(Number(point.wavelength_um)) && Number.isFinite(Number(point.flux)));
  if (!points.length) {
    state.spectrumHitPoints = [];
    elements["spectrum-series-legend"].textContent = "No plotted series · flux units are supplied by the archive";
    ctx.fillStyle = "#8c9aad";
    ctx.font = `${12 * ratio}px sans-serif`;
    ctx.fillText("No archive spectral measurements were returned for this field.", 20 * ratio, 32 * ratio);
    return;
  }
  const waves = points.map((point) => Number(point.wavelength_um));
  const flux = points.map((point) => Number(point.flux));
  const fluxUnit = points.find((point) => point.flux_unit)?.flux_unit || "archive units";
  const left = 54 * ratio, right = 20 * ratio, top = 24 * ratio, bottom = 42 * ratio;
  const plotW = width - left - right, plotH = height - top - bottom;
  const minWave = Math.min(...waves), rawMaxWave = Math.max(...waves);
  const maxWave = rawMaxWave === minWave ? minWave + 1 : rawMaxWave;
  let minFlux = Math.min(0, ...flux), maxFlux = Math.max(...flux);
  if (maxFlux <= minFlux) maxFlux = minFlux + 1;
  const fluxPad = (maxFlux - minFlux) * 0.08;
  minFlux -= fluxPad;
  maxFlux += fluxPad;
  const xAt = (wave) => left + (wave - minWave) / (maxWave - minWave) * plotW;
  const yAt = (value) => top + plotH - (value - minFlux) / (maxFlux - minFlux) * plotH;
  ctx.font = `${9 * ratio}px monospace`;
  ctx.textAlign = "right";
  ctx.fillStyle = "#8190a4";
  for (let i = 0; i <= 4; i += 1) {
    const fraction = i / 4;
    const y = top + plotH * fraction;
    ctx.strokeStyle = "rgba(172,194,222,.12)";
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke();
    ctx.fillText(`${(maxFlux - fraction * (maxFlux - minFlux)).toPrecision(3)}`, left - 9 * ratio, y + 3 * ratio);
  }
  ctx.save();
  ctx.translate(12 * ratio, top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center";
  ctx.fillStyle = "#9aa9bb";
  ctx.fillText(`Flux (${fluxUnit})`, 0, 0);
  ctx.restore();
  ctx.textAlign = "center";
  for (let i = 0; i <= 5; i += 1) {
    const wave = minWave + (maxWave - minWave) * i / 5;
    const x = xAt(wave);
    ctx.strokeStyle = "rgba(172,194,222,.08)";
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + plotH); ctx.stroke();
    ctx.fillStyle = "#9aa9bb";
    ctx.fillText(`${wave.toPrecision(3)} µm`, x, height - 15 * ratio);
  }

  const features = Array.isArray(data?.metadata?.feature_markers) ? data.metadata.feature_markers : [];
  features.forEach((feature, index) => {
    const wave = Number(feature.wavelength_um);
    if (!Number.isFinite(wave) || wave < minWave || wave > maxWave) return;
    const x = xAt(wave);
    ctx.save();
    ctx.setLineDash([3 * ratio, 4 * ratio]);
    ctx.strokeStyle = "rgba(255,255,255,.4)";
    ctx.beginPath(); ctx.moveTo(x, top + 18 * ratio); ctx.lineTo(x, top + plotH); ctx.stroke();
    ctx.restore();
    ctx.fillStyle = "#e9f4ff";
    ctx.beginPath(); ctx.arc(x, top + 8 * ratio + (index % 2) * 10 * ratio, 7 * ratio, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#07101a";
    ctx.font = `700 ${7 * ratio}px monospace`;
    ctx.textAlign = "center";
    ctx.fillText(String(feature.name || feature.compound || index + 1).slice(0, 8), x, top + 10.5 * ratio + (index % 2) * 10 * ratio);
  });

  const groups = new Map();
  for (const point of points) {
    const id = point.epoch_index == null ? String(point.series_id || "measurement") : `epoch-${point.epoch_index}`;
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id).push(point);
  }
  state.spectrumHitPoints = [];
  const epochLabels = new Map((data.epochs || []).map((epoch, index) => [
    `epoch-${epoch.epoch_index ?? index + 1}`,
    `Epoch ${epoch.epoch_index ?? index + 1}${epoch.date_str ? ` · ${epoch.date_str}` : ""}`
  ]));
  const legendItems = [];
  for (const [seriesId, series] of groups) {
    const color = seriesColor(seriesId);
    legendItems.push({ label: epochLabels.get(seriesId) || seriesId, color });
    const ordered = [...series].sort((a, b) => Number(a.wavelength_um) - Number(b.wavelength_um));
    ctx.beginPath();
    ordered.forEach((point, index) => {
      const x = xAt(Number(point.wavelength_um)), y = yAt(Number(point.flux));
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.7 * ratio;
    ctx.stroke();
    for (const point of ordered) {
      const x = xAt(Number(point.wavelength_um)), y = yAt(Number(point.flux));
      const uncertainty = Number(point.uncertainty);
      if (Number.isFinite(uncertainty) && uncertainty > 0) {
        const halfBar = Math.min(plotH / 3, uncertainty / (maxFlux - minFlux) * plotH);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1 * ratio;
        ctx.beginPath(); ctx.moveTo(x, y - halfBar); ctx.lineTo(x, y + halfBar); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x - 3 * ratio, y - halfBar); ctx.lineTo(x + 3 * ratio, y - halfBar); ctx.moveTo(x - 3 * ratio, y + halfBar); ctx.lineTo(x + 3 * ratio, y + halfBar); ctx.stroke();
      }
      ctx.beginPath(); ctx.arc(x, y, 3.1 * ratio, 0, Math.PI * 2);
      ctx.fillStyle = color; ctx.fill();
      state.spectrumHitPoints.push({ point, x: x / ratio, y: y / ratio });
    }
  }
  elements["spectrum-series-legend"].replaceChildren(...legendItems.map((item) => {
    const label = document.createElement("span");
    const marker = document.createElement("i");
    marker.className = "legend-line"; marker.style.background = item.color;
    label.append(marker, document.createTextNode(item.label));
    return label;
  }));
}

function renderSpectrum(data) {
  const metadata = data?.metadata || {};
  const points = Array.isArray(data?.spectral_points) ? data.spectral_points : [];
  elements["spectrum-target-name"].textContent = metadata.name || "Awaiting target";
  const status = document.getElementById("spectrum-status");
  if (status) status.textContent = points.length ? "Archive measured" : "No measurement returned";
  const validPoints = points.filter((point) => Number.isFinite(Number(point.wavelength_um)) && Number.isFinite(Number(point.flux)));
  const waves = validPoints.map((point) => Number(point.wavelength_um));
  const flux = validPoints.map((point) => Number(point.flux));
  const valid = validPoints.length > 0;
  document.getElementById("spectrum-coverage").textContent = valid
    ? `${Math.min(...waves).toPrecision(3)}–${Math.max(...waves).toPrecision(3)} µm` : "Unavailable";
  document.getElementById("spectrum-channel-count").textContent = String(points.length);
  const peakIndex = valid ? flux.reduce((best, value, index) => value > flux[best] ? index : best, 0) : -1;
  document.getElementById("spectrum-peak").textContent = peakIndex >= 0
    ? `${Number(flux[peakIndex]).toPrecision(3)} ${validPoints[peakIndex].flux_unit || ""} @ ${Number(waves[peakIndex]).toPrecision(3)} µm` : "Unavailable";
  const arrays = [...new Set(validPoints.map((point) => point.bandpass).filter(Boolean))];
  document.getElementById("spectrum-array-count").textContent = String(arrays.length);
  const snrValues = validPoints.map((point) => Number(point.flux) / Number(point.uncertainty))
    .filter((value) => Number.isFinite(value) && value > 0).sort((a, b) => a - b);
  document.getElementById("spectrum-snr").textContent = snrValues.length
    ? formatNumber(snrValues[Math.floor(snrValues.length / 2)], 2) : "Unavailable";
  const measuredFeatures = detectMeasuredFeatures(validPoints);
  const markers = Array.isArray(metadata.feature_markers) && metadata.feature_markers.length
    ? metadata.feature_markers : measuredFeatures;
  document.getElementById("spectrum-feature-count").textContent = String(markers.length);
  elements["spectrum-source"].textContent = points.length ? "ARCHIVE MEASUREMENTS" : "NO ARCHIVE MEASUREMENTS";
  elements["spectrum-source"].title = metadata.spectrum_status === "measured"
    ? "Points are sampled from archive IMAGE planes using the supplied spatial and spectral WCS."
    : "No target-position wavelength/flux measurements were returned; no synthetic spectrum is substituted.";
  renderFeatureList(markers);
  drawSpectrum(data);
}

function detectMeasuredFeatures(points) {
  const byEpoch = new Map();
  for (const point of points) {
    const key = point.epoch_index ?? "measurement";
    if (!byEpoch.has(key)) byEpoch.set(key, []);
    byEpoch.get(key).push(point);
  }
  const extrema = [];
  for (const [epoch, series] of byEpoch) {
    const ordered = [...series].sort((a, b) => Number(a.wavelength_um) - Number(b.wavelength_um));
    if (ordered.length < 3) continue;
    const values = ordered.map((point) => Number(point.flux));
    const span = Math.max(...values) - Math.min(...values);
    if (!(span > 0)) continue;
    for (let i = 1; i < ordered.length - 1; i += 1) {
      const value = values[i], left = values[i - 1], right = values[i + 1];
      const isPeak = value > left && value > right;
      const isTrough = value < left && value < right;
      const prominence = Math.min(Math.abs(value - left), Math.abs(value - right));
      if ((isPeak || isTrough) && prominence >= span * .12) {
        extrema.push({
          name: isPeak ? "Measured local maximum" : "Measured local minimum",
          wavelength_um: Number(ordered[i].wavelength_um),
          note: `Epoch ${epoch}; data-derived shape marker, not a chemical identification.`
        });
      }
    }
  }
  return extrema.slice(0, 12);
}

function renderFeatureList(features) {
  features = Array.isArray(features) ? features : [];
  elements["feature-list"].replaceChildren(...features.map((feature, index) => {
    const item = document.createElement("article");
    item.className = "feature-card";
    const indexLabel = document.createElement("span");
    indexLabel.className = "feature-index";
    indexLabel.textContent = String(index + 1).padStart(2, "0");
    const text = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = feature.name || feature.compound || "Archive marker";
    const detail = document.createElement("p");
    detail.textContent = `${formatNumber(feature.wavelength_um, 3)} µm${feature.note ? ` · ${feature.note}` : ""}`;
    text.append(name, detail);
    item.append(indexLabel, text);
    return item;
  }));
}

function renderDataProducts() {
  if (!state.data) return;
  const data = state.data;
  const metadata = data.metadata || {};
  const source = metadata.data_source || "unknown";
  elements["data-source-detail"].replaceChildren();
  const status = document.createElement("div");
  status.className = `provenance-status ${source === "irsa_live_tap" ? "is-live" : "is-simulated"}`;
  status.textContent = source === "irsa_live_tap" ? "LIVE ARCHIVE CUTOUTS" : "SIMULATED CUTOUTS";
  const description = document.createElement("p");
  description.textContent = metadata.retrieval_note || (source === "irsa_live_tap"
    ? "Images and any displayed spectrum are processed from IRSA FITS products. Unavailable measurements are left blank."
    : "No archive FITS product was imported for these images.");
  elements["data-source-detail"].append(status, description);

  const products = Array.isArray(metadata.data_manifest) ? metadata.data_manifest : [];
  elements["data-product-list"].replaceChildren(...products.map((product) => {
    const card = document.createElement("article");
    card.className = "product-card";
    const head = document.createElement("div");
    head.className = "product-head";
    const title = document.createElement("strong");
    title.textContent = `E${product.epoch_index || "—"} · ${product.file_name || "Synthetic scene"}`;
    const type = document.createElement("span");
    type.textContent = product.product_type === "archive_cutout" ? "FITS IMPORT" : "SIMULATED";
    head.append(title, type);
    const sourceLine = document.createElement("p");
    sourceLine.textContent = product.source || "Source not supplied";
    const details = document.createElement("dl");
    const rows = [
      ["Displayed part", product.image_hdu ? `${product.image_hdu} extension (HDU ${product.hdu_index ?? "?"})` : "Generated pixel grid; no file extension"],
      ["Data release", product.data_release || "Not recorded"],
      ["Band / wavelength", [product.bandpass || data.epochs?.[Number(product.epoch_index || 1) - 1]?.bandpass, product.wavelength_um ? `${product.wavelength_um} µm` : null].filter(Boolean).join(" · ") || "Not recorded"],
      ["Quality flags", JSON.stringify(product.quality_flag_counts || {})],
      ["Spatial WCS", product.spatial_wcs ? JSON.stringify(product.spatial_wcs) : "Not recorded"],
      ["Spectral WCS", product.spectral_wcs ? JSON.stringify(product.spectral_wcs) : "Not recorded"],
      ["Processing version", product.processing_version || "Not recorded"],
      ["Processing", product.background_method || product.processing || "No processing details supplied"],
      ["Available HDUs", Array.isArray(product.available_hdus) ? product.available_hdus.join(", ") : "—"],
      ["Archive note", product.archive_note || "—"]
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt"); dt.textContent = label;
      const dd = document.createElement("dd"); dd.textContent = value;
      details.append(dt, dd);
    }
    card.append(head, sourceLine, details);
    if (product.file_uri) {
      const link = document.createElement("a");
      link.className = "product-uri";
      link.href = product.file_uri;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Open archive cutout URL ↗";
      card.append(link);
    }
    return card;
  }));
}

function renderDataInspector() {
  if (!state.data) return;
  const data = state.data, metadata = data.metadata || {}, coordinates = data.coordinates || {};
  elements["data-inspector-summary"].replaceChildren();
  const summaryItems = [
    ["Target", metadata.name || "Resolved field"],
    ["ICRS", `${formatNumber(coordinates.ra_deg, 6)}°, ${formatNumber(coordinates.dec_deg, 6)}°`],
    ["Source", metadata.cache_status === "stale_archive_fallback" ? "Previous successful archive response (stale)" : (metadata.data_source || "unknown")],
    ["Request", `${metadata.bandpass || "Any band"} · ${metadata.size_deg ?? "—"}° field · ${data.epochs.length} epoch(s)`]
  ];
  for (const [label, value] of summaryItems) {
    const item = document.createElement("div"); item.className = "inspector-stat";
    const small = document.createElement("small"); small.textContent = label;
    const strong = document.createElement("strong"); strong.textContent = value;
    item.append(small, strong); elements["data-inspector-summary"].append(item);
  }
  const products = new Map();
  for (const product of metadata.data_manifest || []) {
    const key = Number(product.epoch_index);
    if (!products.has(key)) products.set(key, []);
    products.get(key).push(product);
  }
  elements["epoch-inspector-rows"].replaceChildren(...data.epochs.map((epoch, index) => {
    const pixels = epoch.pixels_u8 || [];
    let min = Infinity, max = -Infinity, count = 0;
    for (const line of pixels) for (const pixel of line) {
      const value = Number(pixel);
      if (!Number.isFinite(value)) continue;
      min = Math.min(min, value); max = Math.max(max, value); count += 1;
    }
    const epochProducts = products.get(Number(epoch.epoch_index || index + 1)) || [];
    const row = document.createElement("tr");
    const fields = [
      `E${epoch.epoch_index || index + 1}`,
      epoch.date_str || "Date unavailable",
      count ? `${pixels[0]?.length || 0} × ${pixels.length}` : "No pixels",
      count ? `${min}–${max} / 255` : "—",
      `${[...new Set(epochProducts.map((product) => product.bandpass).filter(Boolean))].join(", ") || epoch.bandpass || "—"} · σ ${epochProducts.map((product) => Number(product.background_sigma)).filter(Number.isFinite).map((value) => value.toPrecision(3)).join(", ") || "—"}`,
      JSON.stringify(Object.fromEntries(epochProducts.map((product) => [product.bandpass || "image", product.quality_flag_counts || {}])))
    ];
    for (const value of fields) { const cell = document.createElement("td"); cell.textContent = value; row.append(cell); }
    return row;
  }));
  const points = Array.isArray(data.spectral_points) ? data.spectral_points : [];
  elements["spectrum-inspector-empty"].hidden = points.length > 0;
  elements["spectrum-inspector-rows"].replaceChildren(...points.map((point) => {
    const row = document.createElement("tr");
    const values = [
      `E${point.epoch_index ?? "—"}`,
      `${formatNumber(point.wavelength_um, 5)} µm`,
      `${formatNumber(point.flux, 6)} ${point.flux_unit || ""}`.trim(),
      point.uncertainty == null ? "—" : formatNumber(point.uncertainty, 6),
      point.bandpass || metadata.bandpass || "—"
    ];
    for (const value of values) { const cell = document.createElement("td"); cell.textContent = value; row.append(cell); }
    return row;
  }));
}

async function loadBenchmarkExamples() {
  try {
    const { examples = [] } = await fetchJson(`${API_BASE}/api/benchmarks`);
    elements["benchmark-count"].textContent = `${examples.length} optional examples`;
    elements["benchmark-list"].replaceChildren(...examples.map((example) => {
      const card = document.createElement("article"); card.className = "benchmark-card";
      const title = document.createElement("strong"); title.textContent = example.name;
      const details = document.createElement("p"); details.textContent = `${Number(example.ra_deg).toFixed(5)}°, ${Number(example.dec_deg).toFixed(5)}°${example.spectral_type ? ` · ${example.spectral_type}` : ""}`;
      const description = document.createElement("p"); description.textContent = example.description;
      const button = document.createElement("button"); button.type = "button"; button.className = "button button-secondary"; button.textContent = "Open example";
      button.addEventListener("click", () => {
        updateInputMode("sky"); updateQueryMode("coordinates");
        elements["coordinate-frame"].value = "icrs";
        elements["ra-query"].value = String(example.ra_deg);
        elements["dec-query"].value = String(example.dec_deg);
        elements["benchmark-disclosure"].open = false;
        observeTarget();
      });
      card.append(title, details, description, button); return card;
    }));
  } catch (error) {
    elements["benchmark-count"].textContent = "Examples unavailable";
    elements["benchmark-list"].textContent = error.message;
  }
}

function addMessage(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `chat-message ${role === "user" ? "user-message" : "assistant-message"}`;
  const author = document.createElement("span");
  author.className = "message-author";
  author.textContent = role === "user" ? "YOU" : AI_CONFIG.name;
  const body = document.createElement("p");
  body.textContent = text;
  bubble.append(author, body);
  elements["chat-messages"].append(bubble);
  elements["chat-messages"].scrollTop = elements["chat-messages"].scrollHeight;
}

function activeTargetSummary(data) {
  const latest = data.epochs[data.epochs.length - 1] || {};
  const metadata = data.metadata || {};
  const coordinates = data.coordinates || {};
  const spectralPoints = (data.spectral_points || []).slice(-24).map((point) => ({
    wavelength_um: Number(point.wavelength_um),
    flux: Number(point.flux),
    flux_unit: point.flux_unit || null,
    epoch_index: point.epoch_index
  }));
  return {
    name: metadata.name,
    coordinates: { frame: coordinates.frame, ra_deg: coordinates.ra_deg, dec_deg: coordinates.dec_deg },
    classification: metadata.classification || null,
    spectral_type: metadata.spectral_type || null,
    catalog_fields: metadata.catalog_fields || {},
    proper_motion: metadata.proper_motion_known ? metadata.proper_motion : null,
    proper_motion_known: Boolean(metadata.proper_motion_known),
    wavelength_um: latest.wavelength_um ?? null,
    epoch_count: data.epochs.length,
    data_source: metadata.data_source || "unknown",
    spectrum_status: metadata.spectrum_status || "unavailable",
    spectral_points: spectralPoints
  };
}

async function askAnalyzer(prompt) {
  if (state.analyzerBusy) return;
  if (!state.data) {
    addMessage("assistant", "Load a target first so I can ground the answer in its observations.");
    return;
  }
  const question = prompt.trim();
  if (!question) return;
  const history = state.history.slice(-4);
  addMessage("user", question);
  elements["suggested-question"].replaceChildren();
  const submitButton = elements["chat-form"].querySelector("button");
  const requestId = ++state.analyzerRequestId;
  const controller = new AbortController();
  state.analyzerController = controller;
  state.analyzerBusy = true;
  let answerReceived = false;
  submitButton.disabled = true;
  document.querySelectorAll("[data-prompt]").forEach((button) => { button.disabled = true; });
  elements["assistant-activity"].hidden = false;
  elements["assistant-mode-status"].textContent = "Analyzing the current target metadata…";
  try {
    const headers = { "Content-Type": "application/json" };
    if (elements["analyzer-token"].value) {
      headers["X-Analyzer-Token"] = elements["analyzer-token"].value;
    }
    const result = await fetchJson(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify({ prompt: question, target: activeTargetSummary(state.data), history }),
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(20_000)])
    });
    if (requestId !== state.analyzerRequestId) return;
    if (!result || typeof result.reply !== "string" || !result.reply.trim()) {
      throw new Error("The assistant returned an empty answer. Please retry.");
    }
    addMessage("assistant", result.reply);
    elements["assistant-mode-status"].textContent = result.source === "gemini"
      ? "Online answer · grounded in target measurements"
      : "Metadata-only answer · online assistant unavailable or rate-limited";
    if (result.notice) addMessage("assistant", result.notice);
    answerReceived = true;
    state.history.push({ role: "user", content: question });
    state.history.push({ role: "assistant", content: result.reply });
    if (result.suggested_question) {
      const suggestion = document.createElement("button");
      suggestion.className = "suggestion-button";
      suggestion.type = "button";
      suggestion.textContent = `↳ ${result.suggested_question}`;
      suggestion.addEventListener("click", () => askAnalyzer(result.suggested_question));
      elements["suggested-question"].replaceChildren(suggestion);
    }
  } catch (error) {
    if (requestId === state.analyzerRequestId) {
      const message = error.name === "TimeoutError"
        ? "The analysis request timed out. Your target is still loaded; try again in a moment."
        : error.name === "AbortError"
          ? "Analysis cancelled because the active target changed."
          : `Analysis request failed: ${error.message}`;
      addMessage("assistant", message);
      elements["assistant-mode-status"].textContent = "Request failed · you can retry";
    }
  } finally {
    if (requestId === state.analyzerRequestId) {
      state.analyzerBusy = false;
      state.analyzerController = null;
      submitButton.disabled = false;
      document.querySelectorAll("[data-prompt]").forEach((button) => { button.disabled = false; });
      elements["assistant-activity"].hidden = true;
      if (state.data && requestId === state.analyzerRequestId && !answerReceived) {
        elements["assistant-mode-status"].textContent = "Ready · grounded in the active target";
      }
      if (answerReceived) elements["chat-input"].value = "";
      elements["chat-input"].focus();
    }
  }
}

function inspectDot(event, comparisonEpochIndex = null, canvas = elements["sky-canvas"]) {
  if (!state.data) return;
  const rect = canvas.getBoundingClientRect();
  const epochIndex = comparisonEpochIndex === null ? state.activeEpoch : comparisonEpochIndex;
  const epoch = state.data.epochs[epochIndex] || state.data.epochs[0];
  const pixelHeight = epoch.pixels_u8.length;
  const pixelWidth = epoch.pixels_u8[0]?.length || pixelHeight;
  const x = Math.max(0, Math.min(pixelWidth - 1,
    Math.floor((event.clientX - rect.left) / rect.width * pixelWidth)));
  const y = Math.max(0, Math.min(pixelHeight - 1,
    Math.floor((event.clientY - rect.top) / rect.height * pixelHeight)));
  const coordinates = state.data.coordinates;
  const metadata = state.data.metadata;
  const center = epoch.target_pixel_pos || [pixelWidth / 2, pixelHeight / 2];
  const scale = Number(metadata.pixel_scale_arcsec) || 0;
  const cosDec = Math.cos(Number(coordinates.dec_deg) * Math.PI / 180);
  const ra = Number(coordinates.ra_deg) + ((x - center[0]) * scale / 3600) / (cosDec || 1);
  const dec = Number(coordinates.dec_deg) + ((center[1] - y) * scale / 3600);
  const catalogFields = Object.entries(metadata.catalog_fields || {}).map(([key, value]) => `${key}: ${value}`).join(" · ");
  elements["dot-hud"].textContent =
    `E${epoch.epoch_index || epochIndex + 1} · pixel (${x}, ${y}) · approx. RA ${ra.toFixed(6)}°, Dec ${dec.toFixed(6)}°${metadata.proper_motion_known ? ` · motion ${formatNumber(metadata.proper_motion, 4)}″/yr` : ""}${metadata.classification ? ` · ${metadata.classification}` : ""}${catalogFields ? ` · ${catalogFields}` : ""}`;
}

elements["search-form"].addEventListener("submit", (event) => {
  event.preventDefault();
  observeTarget();
});
document.querySelectorAll("[data-screen-tab]").forEach((button) =>
  button.addEventListener("click", () => setScreen(button.dataset.screenTab))
);
document.querySelectorAll("[data-input-mode]").forEach((button) =>
  button.addEventListener("click", () => updateInputMode(button.dataset.inputMode))
);
document.querySelectorAll("[data-query-mode]").forEach((button) =>
  button.addEventListener("click", () => updateQueryMode(button.dataset.queryMode))
);
document.querySelectorAll("[data-view]").forEach((button) =>
  button.addEventListener("click", () => setView(button.dataset.view))
);
elements["blink-toggle"].addEventListener("click", () => {
  state.blinkPlaying = !state.blinkPlaying;
  elements["blink-toggle"].textContent = state.blinkPlaying ? "Pause" : "Play";
  state.blinkPlaying ? startBlink() : stopBlink();
});
elements["blink-speed"].addEventListener("input", () => {
  elements["blink-speed-value"].value = `${elements["blink-speed"].value} fps`;
  if (state.view === "blink") startBlink();
});
elements["sky-canvas"].addEventListener("click", inspectDot);
elements["comparison-canvas-a"].addEventListener("click", (event) => inspectDot(event, 0, elements["comparison-canvas-a"]));
elements["comparison-canvas-b"].addEventListener("click", (event) => inspectDot(event, 1, elements["comparison-canvas-b"]));
elements["wipe-canvas-a"].addEventListener("click", (event) => inspectDot(event, 0, elements["wipe-canvas-a"]));
elements["wipe-canvas-b"].addEventListener("click", (event) => inspectDot(event, 1, elements["wipe-canvas-b"]));
elements["wipe-range"].addEventListener("input", () => {
  elements["wipe-view"].style.setProperty("--wipe-percent", `${elements["wipe-range"].value}%`);
  elements["wipe-range-value"].value = `${elements["wipe-range"].value}%`;
});
elements["epoch-range"].addEventListener("input", () => {
  state.activeEpoch = Number(elements["epoch-range"].value);
  renderCurrentView();
});
elements["difference-epoch"].addEventListener("change", () => {
  state.differenceEpoch = Number(elements["difference-epoch"].value);
  renderCurrentView();
});
elements["spectrum-canvas"].addEventListener("mousemove", (event) => {
  const rect = elements["spectrum-canvas"].getBoundingClientRect();
  const x = event.clientX - rect.left, y = event.clientY - rect.top;
  const nearest = state.spectrumHitPoints?.reduce((best, hit) => {
    const distance = Math.hypot(hit.x - x, hit.y - y);
    return distance < best.distance ? { hit, distance } : best;
  }, { hit: null, distance: 14 });
  const tooltip = elements["spectrum-tooltip"];
  if (!nearest?.hit) { tooltip.hidden = true; return; }
  const point = nearest.hit.point;
  tooltip.textContent = `${Number(point.wavelength_um).toPrecision(5)} µm · ${Number(point.flux).toPrecision(5)} ${point.flux_unit || "flux"}${point.uncertainty != null ? ` ± ${Number(point.uncertainty).toPrecision(3)}` : ""}${point.mjd != null ? ` · MJD ${point.mjd}` : ""}`;
  tooltip.style.left = `${Math.min(rect.width - 230, Math.max(8, x + 12))}px`;
  tooltip.style.top = `${Math.max(8, y - 30)}px`;
  tooltip.hidden = false;
});
elements["spectrum-canvas"].addEventListener("mouseleave", () => { elements["spectrum-tooltip"].hidden = true; });
elements["open-data-products"].addEventListener("click", () => {
  if (!state.data) return;
  renderDataProducts();
  elements["data-products-dialog"].showModal();
});
elements["open-data-inspector"].addEventListener("click", () => {
  if (!state.data) return;
  renderDataInspector();
  elements["data-inspector-dialog"].showModal();
});
elements["close-data-inspector"].addEventListener("click", () => elements["data-inspector-dialog"].close());
elements["data-inspector-dialog"].addEventListener("click", (event) => {
  if (event.target === elements["data-inspector-dialog"]) elements["data-inspector-dialog"].close();
});
elements["close-data-products"].addEventListener("click", () => elements["data-products-dialog"].close());
elements["data-products-dialog"].addEventListener("click", (event) => {
  if (event.target === elements["data-products-dialog"]) elements["data-products-dialog"].close();
});
elements["refresh-archive"].addEventListener("click", async () => {
  if (!state.data) return;
  elements["refresh-archive"].disabled = true;
  elements["refresh-archive"].textContent = "Querying IRSA…";
  await observeTarget(undefined, true);
  renderDataProducts();
  elements["refresh-archive"].disabled = false;
  elements["refresh-archive"].textContent = "Retry live archive lookup";
});
elements["chat-form"].addEventListener("submit", (event) => {
  event.preventDefault();
  askAnalyzer(elements["chat-input"].value);
});
document.querySelectorAll("[data-prompt]").forEach((button) =>
  button.addEventListener("click", () => askAnalyzer(button.dataset.prompt))
);
elements["assistant-name"].addEventListener("change", () => {
  AI_CONFIG.name = elements["assistant-name"].value.trim() || AI_CONFIG.name;
  elements["assistant-name"].value = AI_CONFIG.name;
  document.getElementById("analyzer-title").textContent = AI_CONFIG.name;
  document.querySelectorAll(".assistant-message .message-author").forEach((node) => {
    node.textContent = AI_CONFIG.name;
  });
});
window.addEventListener("resize", () => {
  if (state.data) { renderSpectrum(state.data); renderCurrentView(); }
});

elements["blink-speed-value"].value = `${elements["blink-speed"].value} fps`;
updateInputMode("sky");
updateQueryMode("name");
document.getElementById("analyzer-title").textContent = AI_CONFIG.name;
elements["assistant-name"].value = AI_CONFIG.name;
document.querySelector(".assistant-message .message-author").textContent = AI_CONFIG.name;
drawSpectrum(null);
loadBenchmarkExamples();
