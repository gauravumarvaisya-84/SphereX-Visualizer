"use strict";

const AI_CONFIG = { name: "SPHEREx Analyzer" };
const API_BASE = window.SPHEREX_API_BASE || `${window.location.protocol}//${window.location.hostname || "localhost"}:8000`;
const BANDPASSES = ["SPHEREx-D1", "SPHEREx-D2", "SPHEREx-D3", "SPHEREx-D4", "SPHEREx-D5", "SPHEREx-D6"];

const state = {
  inputMode: "sky",
  view: "single",
  data: null,
  activeEpoch: 0,
  blinkTimer: null,
  blinkPlaying: true,
  history: [],
  presets: []
};

const elements = Object.fromEntries([
  "search-form", "target-query", "query-label", "search-help", "search-message", "preset-list",
  "target-summary", "data-source", "sky-canvas", "epoch-label", "observation-meta", "dot-hud",
  "blink-controls", "blink-toggle", "blink-speed", "blink-speed-value", "spectrum-canvas",
  "chat-form", "chat-input", "chat-messages", "suggested-question", "assistant-name", "analyzer-token"
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

async function loadPresets() {
  try {
    const result = await fetchJson(`${API_BASE}/api/targets`);
    state.presets = result.benchmark_targets || [];
    elements["preset-list"].replaceChildren(...state.presets.map((target) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "preset-button";
      button.innerHTML = `<span class="preset-name"></span><span class="preset-motion"></span>`;
      button.querySelector(".preset-name").textContent = target.name;
      button.querySelector(".preset-motion").textContent = `${target.total_pm_arcsec_yr}″/yr`;
      button.addEventListener("click", () => {
        updateInputMode("sky");
        elements["target-query"].value = target.name;
        observeTarget(target.name);
      });
      return button;
    }));
  } catch (error) {
    setMessage(`Could not load benchmark targets: ${error.message}`, true);
  }
}

function updateInputMode(mode) {
  state.inputMode = mode;
  document.querySelectorAll("[data-input-mode]").forEach((button) => {
    const active = button.dataset.inputMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  elements["query-label"].textContent = mode === "earth" ? "Earth city or latitude, longitude" : "Target name or RA, Dec";
  elements["target-query"].placeholder = mode === "earth"
    ? "Pasadena, CA or 34.1478, -118.1445"
    : "Barnard's Star, M101, or 269.452083, 4.693389";
  elements["search-help"].textContent = mode === "earth"
    ? "Enter a city/address or latitude, longitude; the current zenith is resolved."
    : "Decimal or sexagesimal coordinates, star and galaxy names.";
}

async function observeTarget(query) {
  const targetQuery = (query || elements["target-query"].value).trim();
  if (!targetQuery) return;
  setMessage("Resolving target and loading observations…");
  document.querySelectorAll(".preset-button").forEach((button) => button.classList.remove("active"));
  try {
    const params = new URLSearchParams({ q: targetQuery, input_mode: state.inputMode });
    const data = await fetchJson(`${API_BASE}/api/sky?${params.toString()}`);
    if (!Array.isArray(data.epochs) || data.epochs.length === 0) {
      throw new Error("The observation response contains no epochs.");
    }
    state.data = data;
    state.activeEpoch = 0;
    state.history = [];
    elements["chat-messages"].replaceChildren();
    elements["suggested-question"].replaceChildren();
    renderTargetSummary(data);
    renderObservationMeta(data);
    renderSpectrum(data.spectral_profile);
    elements["data-source"].textContent = (data.cache_status || data.source || "DATA READY").replaceAll("_", " ").toUpperCase();
    elements["data-source"].title = data.source || "";
    setMessage(`Loaded ${data.epochs.length} observation epoch(s).`);
    renderCurrentView();
    addMessage("assistant", `Target locked: ${data.name}. Ask me about its motion, infrared spectrum, or epoch-to-epoch changes.`);
  } catch (error) {
    setMessage(error.message, true);
  }
}

function renderTargetSummary(data) {
  const summary = elements["target-summary"];
  summary.hidden = false;
  summary.replaceChildren();
  const title = document.createElement("div");
  title.className = "summary-name";
  title.textContent = data.name || "Unknown target";
  summary.append(title);
  const fields = [
    ["RA", `${formatNumber(data.ra_deg, 5)}°`],
    ["Dec", `${formatNumber(data.dec_deg, 5)}°`],
    ["Proper motion", `${formatNumber(data.total_pm_arcsec_yr, 3)}″/yr`],
    ["Spectral type", data.spectral_type || "Unknown"]
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
  const epochs = data.epochs;
  const first = epochs[0];
  elements["observation-meta"].textContent =
    `${data.bandpass || first.bandpass || "SPHEREx"} · ${data.pixel_scale_arcsec || "—"} arcsec/pixel · ${epochs.length} epochs · ${epochs[0].date_str || "date n/a"} → ${epochs.at(-1).date_str || "date n/a"}`;
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("[data-view]").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  elements["blink-controls"].hidden = view !== "blink";
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
      image.data[i + 1] = Math.round(value * 0.88);
      image.data[i + 2] = Math.min(255, Math.round(value * 1.12 + 5));
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
  const image = new ImageData(width, height);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const diff = Number(b[y][x]) - Number(a[y][x]);
      const i = (y * width + x) * 4;
      if (diff > 15) {
        image.data[i] = 255;
        image.data[i + 1] = Math.max(70, 190 - Math.abs(diff));
        image.data[i + 2] = 18;
        image.data[i + 3] = 255;
      } else if (diff < -15) {
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

function renderCurrentView() {
  const canvas = elements["sky-canvas"];
  const context = canvas.getContext("2d");
  if (!state.data) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }
  const epochs = state.data.epochs;
  let epochIndex = Math.min(state.activeEpoch, epochs.length - 1);
  let image;
  if (state.view === "difference" && epochs.length > 1) {
    canvas.width = epochs[0].pixels_u8[0].length;
    canvas.height = epochs[0].pixels_u8.length;
    image = differenceImage(epochs[0], epochs[1]);
    elements["epoch-label"].textContent = `${epochs[1].date_str} − ${epochs[0].date_str}`;
  } else {
    if (state.view === "difference" && epochs.length < 2) {
      elements["epoch-label"].textContent = "Need at least two epochs";
    } else {
      epochIndex = state.view === "blink" ? epochIndex : 0;
      state.activeEpoch = epochIndex;
      canvas.width = epochs[epochIndex].pixels_u8[0].length;
      canvas.height = epochs[epochIndex].pixels_u8.length;
      image = getImageData(epochs[epochIndex]);
      elements["epoch-label"].textContent = `E${epochs[epochIndex].epoch_index || epochIndex + 1} · ${epochs[epochIndex].date_str}`;
    }
  }
  if (image) context.putImageData(image, 0, 0);
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

function drawSpectrum(profile) {
  const canvas = elements["spectrum-canvas"];
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(320, Math.round(canvas.clientWidth * ratio));
  const height = Math.round(200 * ratio);
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#090e17";
  ctx.fillRect(0, 0, width, height);
  if (!profile || !Array.isArray(profile.flux) || !profile.flux.length) {
    ctx.fillStyle = "#8c9aad";
    ctx.font = `${12 * ratio}px sans-serif`;
    ctx.fillText("Spectrum unavailable", 20 * ratio, 32 * ratio);
    return;
  }
  const waves = profile.wavelengths_um;
  const flux = profile.flux;
  const left = 42 * ratio, right = 12 * ratio, top = 14 * ratio, bottom = 30 * ratio;
  const plotW = width - left - right, plotH = height - top - bottom;
  const minWave = Math.min(...waves), maxWave = Math.max(...waves);
  const maxFlux = Math.max(1, ...flux);
  ctx.strokeStyle = "rgba(172,194,222,.12)";
  ctx.fillStyle = "#8c9aad";
  ctx.font = `${9 * ratio}px monospace`;
  for (let i = 0; i <= 4; i += 1) {
    const y = top + plotH * i / 4;
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke();
  }
  ctx.textAlign = "center";
  for (let i = 0; i <= 4; i += 1) {
    const wave = minWave + (maxWave - minWave) * i / 4;
    const x = left + plotW * i / 4;
    ctx.fillText(wave.toFixed(1), x, height - 8 * ratio);
  }
  const regions = [[1.38, 1.48, "#00c2e0"], [1.62, 1.7, "#ffb703"], [1.86, 1.96, "#00c2e0"], [3.0, 3.1, "#00c2e0"], [4.2, 4.3, "#ffb703"]];
  for (const [start, end, color] of regions) {
    const x1 = left + (start - minWave) / (maxWave - minWave) * plotW;
    const x2 = left + (end - minWave) / (maxWave - minWave) * plotW;
    ctx.fillStyle = color + "18";
    ctx.fillRect(x1, top, Math.max(2, x2 - x1), plotH);
  }
  ctx.beginPath();
  ctx.strokeStyle = "#00c2e0";
  ctx.lineWidth = 2 * ratio;
  flux.forEach((value, i) => {
    const x = left + (waves[i] - minWave) / (maxWave - minWave) * plotW;
    const y = top + plotH - (value / maxFlux) * plotH;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = "#ffb703";
  ctx.textAlign = "left";
  ctx.fillText("H₂O", left + (1.4 - minWave) / (maxWave - minWave) * plotW, top + 11 * ratio);
  ctx.fillText("CH₄", left + (3.3 - minWave) / (maxWave - minWave) * plotW, top + 11 * ratio);
  ctx.fillText("CO₂", left + (4.25 - minWave) / (maxWave - minWave) * plotW, top + 23 * ratio);
}

function renderSpectrum(profile) {
  drawSpectrum(profile);
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
  return {
    name: data.name,
    ra_deg: data.ra_deg,
    dec_deg: data.dec_deg,
    proper_motion: data.total_pm_arcsec_yr,
    optical_ir_ratio: data.optical_ir_ratio ?? null,
    wavelength_um: latest.wavelength_um ?? null,
    epoch_count: data.epochs.length,
    discovery_status: data.discovery_status || "unverified"
  };
}

async function askAnalyzer(prompt) {
  if (!state.data) {
    addMessage("assistant", "Load a target first so I can ground the answer in its observations.");
    return;
  }
  const question = prompt.trim();
  if (!question) return;
  const history = state.history.slice(-4);
  addMessage("user", question);
  state.history.push({ role: "user", content: question });
  elements["suggested-question"].replaceChildren();
  const submitButton = elements["chat-form"].querySelector("button");
  submitButton.disabled = true;
  try {
    const headers = { "Content-Type": "application/json" };
    if (elements["analyzer-token"].value) {
      headers["X-Analyzer-Token"] = elements["analyzer-token"].value;
    }
    const result = await fetchJson(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify({ prompt: question, target: activeTargetSummary(state.data), history })
    });
    addMessage("assistant", result.reply);
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
    addMessage("assistant", `Analysis request failed: ${error.message}`);
  } finally {
    submitButton.disabled = false;
    elements["chat-input"].value = "";
    elements["chat-input"].focus();
  }
}

function inspectDot(event) {
  if (!state.data) return;
  const rect = elements["sky-canvas"].getBoundingClientRect();
  const x = Math.max(0, Math.min(elements["sky-canvas"].width - 1,
    Math.floor((event.clientX - rect.left) / rect.width * elements["sky-canvas"].width)));
  const y = Math.max(0, Math.min(elements["sky-canvas"].height - 1,
    Math.floor((event.clientY - rect.top) / rect.height * elements["sky-canvas"].height)));
  const epoch = state.data.epochs[state.activeEpoch] || state.data.epochs[0];
  const center = epoch.target_pixel_pos || [elements["sky-canvas"].width / 2, elements["sky-canvas"].height / 2];
  const scale = Number(state.data.pixel_scale_arcsec) || 0;
  const cosDec = Math.cos(Number(state.data.dec_deg) * Math.PI / 180);
  const ra = Number(state.data.ra_deg) + ((x - center[0]) * scale / 3600) / (cosDec || 1);
  const dec = Number(state.data.dec_deg) + ((center[1] - y) * scale / 3600);
  elements["dot-hud"].textContent =
    `Dot View · pixel (${x}, ${y}) · approx. RA ${ra.toFixed(6)}°, Dec ${dec.toFixed(6)}° · ${Math.hypot(x - center[0], y - center[1]).toFixed(1)} px from target centroid`;
}

elements["search-form"].addEventListener("submit", (event) => {
  event.preventDefault();
  observeTarget();
});
document.querySelectorAll("[data-input-mode]").forEach((button) =>
  button.addEventListener("click", () => updateInputMode(button.dataset.inputMode))
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
  if (state.data) renderSpectrum(state.data.spectral_profile);
});

elements["blink-speed-value"].value = `${elements["blink-speed"].value} fps`;
document.getElementById("analyzer-title").textContent = AI_CONFIG.name;
elements["assistant-name"].value = AI_CONFIG.name;
document.querySelector(".assistant-message .message-author").textContent = AI_CONFIG.name;
drawSpectrum(null);
loadPresets();
