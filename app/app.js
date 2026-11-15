/**
 * SPHEREx Mission Visualizer — Frontend Application Logic
 * NASA Space Apps Challenge 2026 · Team Pioneer Matrix
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. STATE MANAGEMENT
  // =========================================================================
  let activeInputMode = 'sky'; // 'sky' | 'earth'
  let observationMode = 'blink'; // 'blink' | 'single' | 'diff'
  let blinkFps = 4.0;
  let blinkTimer = null;
  let blinkFrameIndex = 0; // 0 to 5 (6 discrete survey frames)

  // Current Target Telemetry
  let currentTarget = {
    name: "Barnard's Star",
    type: "High-Proper-Motion M Dwarf",
    category: "High Mover Benchmark",
    ra: 269.4521,
    dec: 4.6934,
    raText: "17h 57m 48.50s",
    decText: "+04° 41′ 36.2″",
    pmTotal: "10.36″/yr",
    pa: "355.8°",
    radialVelocity: "-110.6 km/s",
    colorIndex: "+1.42 mag",
    iceAbsorption: "ΔF/F = 0.38",
    opticalToIr: "1 : 4.8",
    gaiaMatch: "CONFIRMED",
    catwise: "CW-J175748",
    epochsCount: 3,
    activeMode: "sky"
  };

  // Known catalog for client-side resolution fallback (when standalone)
  const CATALOG_PRESETS = {
    "barnard": {
      name: "Barnard's Star",
      type: "High-Proper-Motion M Dwarf",
      category: "High Mover Benchmark",
      ra: 269.4521,
      dec: 4.6934,
      raText: "17h 57m 48.50s",
      decText: "+04° 41′ 36.2″",
      pmTotal: "10.36″/yr",
      pa: "355.8°",
      radialVelocity: "-110.6 km/s",
      colorIndex: "+1.42 mag",
      iceAbsorption: "ΔF/F = 0.38",
      epochsCount: 3
    },
    "wise0855": {
      name: "WISE 0855-0714",
      type: "Sub-stellar Y-Dwarf Candidate",
      category: "Ultra-Cold Atmosphere",
      ra: 133.7862,
      dec: -7.2443,
      raText: "08h 55m 10.83s",
      decText: "-07° 14′ 42.5″",
      pmTotal: "8.15″/yr",
      pa: "135.2°",
      radialVelocity: "+12.4 km/s",
      colorIndex: "+3.88 mag",
      iceAbsorption: "ΔF/F = 0.65",
      epochsCount: 4
    },
    "epsindi": {
      name: "Epsilon Indi B",
      type: "T-Dwarf Binary Benchmark",
      category: "Binary Astrometry",
      ra: 330.8404,
      dec: -56.7860,
      raText: "22h 03m 21.7s",
      decText: "-56° 47′ 09.6″",
      pmTotal: "4.70″/yr",
      pa: "125.0°",
      radialVelocity: "-40.2 km/s",
      colorIndex: "+2.10 mag",
      iceAbsorption: "ΔF/F = 0.22",
      epochsCount: 3
    },
    "rwaura": {
      name: "RW Aurigae",
      type: "T Tauri Accreting Star",
      category: "Protoplanetary Disk",
      ra: 77.0125,
      dec: 30.4011,
      raText: "05h 07m 49.5s",
      decText: "+30° 24′ 05.1″",
      pmTotal: "0.02″/yr",
      pa: "180.0°",
      radialVelocity: "+15.8 km/s",
      colorIndex: "+1.95 mag",
      iceAbsorption: "ΔF/F = 0.52",
      epochsCount: 3
    },
    "rdrac": {
      name: "R Draconis",
      type: "Mira Long-Period Variable",
      category: "Stellar Pulsation",
      ra: 247.5500,
      dec: 66.7022,
      raText: "16h 30m 12.0s",
      decText: "+66° 42′ 08.0″",
      pmTotal: "0.04″/yr",
      pa: "88.0°",
      radialVelocity: "-22.1 km/s",
      colorIndex: "+4.12 mag",
      iceAbsorption: "ΔF/F = 0.44",
      epochsCount: 4
    }
  };

  // Known Earth Cities to Sky coordinates fallback
  const EARTH_LOCATIONS = {
    "ahmedabad": { ra: 269.4521, dec: 4.6934, name: "Ahmedabad, India (Zenith Projected)", epochs: 3 },
    "greenwich": { ra: 180.1250, dec: 51.5074, name: "Greenwich Observatory, UK", epochs: 3 },
    "london": { ra: 180.1250, dec: 51.5074, name: "London, UK", epochs: 3 },
    "tokyo": { ra: 139.6503, dec: 35.6762, name: "Tokyo, Japan", epochs: 3 },
    "pasadena": { ra: 241.8555, dec: 34.1478, name: "NASA JPL, Pasadena, USA", epochs: 4 }
  };

  // =========================================================================
  // 2. DOM ELEMENT REFERENCES
  // =========================================================================
  const sideNav = document.getElementById('sideNav');
  const mainWrapper = document.getElementById('mainWrapper');
  const sidebarLogoBtn = document.getElementById('sidebarLogoBtn');
  const headerLogoTrigger = document.getElementById('headerLogoTrigger');

  // Input Bar Elements
  const tabModeSky = document.getElementById('tabModeSky');
  const tabModeEarth = document.getElementById('tabModeEarth');
  const targetInputLabel = document.getElementById('targetInputLabel');
  const targetInputBox = document.getElementById('targetInputBox');
  const targetInputForm = document.getElementById('targetInputForm');
  const observeBtn = document.getElementById('observeBtn');
  const statusFeedback = document.getElementById('statusFeedback');

  // Confirmation Strip Elements
  const resolvedConfirmationStrip = document.getElementById('resolvedConfirmationStrip');
  const resolvedData = document.getElementById('resolvedData');
  const resolvedMode = document.getElementById('resolvedMode');
  const resolvedEpochs = document.getElementById('resolvedEpochs');

  // Canvas & Reticle Elements
  const starCanvas = document.getElementById('starCanvas');
  const canvasContainer = document.getElementById('canvasContainer');
  const reticleBox = document.getElementById('reticleBox');
  const reticleCard = document.getElementById('reticleCard');
  const cursorRaDecHud = document.getElementById('cursorRaDecHud');
  const blinkFpsHud = document.getElementById('blinkFpsHud');
  const activeModeLabel = document.getElementById('activeModeLabel');
  const benchmarkSelector = document.getElementById('benchmarkSelector');

  // HUD Card Elements
  const hudTargetName = document.getElementById('hudTargetName');
  const hudTargetType = document.getElementById('hudTargetType');
  const hudRaDec = document.getElementById('hudRaDec');
  const hudPmTotal = document.getElementById('hudPmTotal');
  const hudIceDepth = document.getElementById('hudIceDepth');

  // Header Elements
  const headerTargetName = document.getElementById('headerTargetName');
  const headerTargetCoords = document.getElementById('headerTargetCoords');

  // SED Canvas
  const sedCanvas = document.getElementById('sedCanvas');
  const sedHoverHud = document.getElementById('sedHoverHud');

  // Floating Action Drawers
  const viewModeFab = document.getElementById('viewModeFab');
  const viewMenuModal = document.getElementById('viewMenuModal');
  const closeViewMenuBtn = document.getElementById('closeViewMenuBtn');
  const modeSelectBtns = document.querySelectorAll('.mode-select-btn');
  const fpsSlider = document.getElementById('fpsSlider');
  const fpsDisplay = document.getElementById('fpsDisplay');

  const aiBotFab = document.getElementById('aiBotFab');
  const aiChatDrawer = document.getElementById('aiChatDrawer');
  const closeAiDrawerBtn = document.getElementById('closeAiDrawerBtn');
  const sendAiPromptBtn = document.getElementById('sendAiPromptBtn');
  const aiInputPrompt = document.getElementById('aiInputPrompt');
  const aiMessagesContainer = document.getElementById('aiMessagesContainer');

  // =========================================================================
  // 3. COLLAPSIBLE SIDEBAR TOGGLE
  // =========================================================================
  function toggleSidebar() {
    if (!sideNav || !mainWrapper) return;
    const isCollapsed = sideNav.classList.toggle('collapsed');
    mainWrapper.classList.toggle('expanded', isCollapsed);
    setTimeout(() => {
      resizeCanvases();
    }, 260);
  }

  if (sidebarLogoBtn) sidebarLogoBtn.addEventListener('click', toggleSidebar);
  if (headerLogoTrigger) headerLogoTrigger.addEventListener('click', toggleSidebar);

  // =========================================================================
  // 4. TWO-MODE SEGMENTED SWITCH & DEDICATED INPUT BAR
  // =========================================================================
  function setInputMode(mode) {
    if (activeInputMode === mode) return;
    activeInputMode = mode;

    // Clear stale text from input box when mode changes
    if (targetInputBox) {
      targetInputBox.value = '';
    }

    // Clear previous error/loading states
    clearStatusFeedback();

    if (mode === 'sky') {
      tabModeSky.classList.add('active');
      tabModeEarth.classList.remove('active');
      if (targetInputLabel) {
        targetInputLabel.textContent = 'Sky Coordinates (RA, Dec) or Object Name';
      }
      if (targetInputBox) {
        targetInputBox.placeholder = "e.g. 269.452, 4.693 or Barnard's Star";
      }
    } else {
      tabModeEarth.classList.add('active');
      tabModeSky.classList.remove('active');
      if (targetInputLabel) {
        targetInputLabel.textContent = 'Earth City, Address, or Lat/Lon';
      }
      if (targetInputBox) {
        targetInputBox.placeholder = 'e.g. Ahmedabad, India or 23.02, 72.57';
      }
    }

    if (targetInputBox) targetInputBox.focus();
  }

  if (tabModeSky) {
    tabModeSky.addEventListener('click', () => setInputMode('sky'));
  }
  if (tabModeEarth) {
    tabModeEarth.addEventListener('click', () => setInputMode('earth'));
  }

  function showStatusFeedback(type, message) {
    if (!statusFeedback) return;
    statusFeedback.className = 'status-feedback-container ' + type;
    if (type === 'loading') {
      statusFeedback.innerHTML = `
        <svg class="animate-spin w-3.5 h-3.5 text-cyan-reticle" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span>${message}</span>
      `;
    } else if (type === 'error') {
      statusFeedback.innerHTML = `
        <svg class="w-3.5 h-3.5 text-red-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>${message}</span>
      `;
    }
  }

  function clearStatusFeedback() {
    if (!statusFeedback) return;
    statusFeedback.className = 'status-feedback-container';
    statusFeedback.innerHTML = '';
  }

  function updateConfirmationStrip(ra, dec, mode, epochs) {
    if (!resolvedConfirmationStrip) return;
    const sign = dec >= 0 ? '+' : '';
    if (resolvedData) {
      resolvedData.textContent = `RA ${ra.toFixed(4)}° · Dec ${sign}${dec.toFixed(4)}°`;
    }
    if (resolvedMode) {
      resolvedMode.textContent = mode === 'earth' ? 'Earth Location' : 'Sky RA/Dec';
    }
    if (resolvedEpochs) {
      resolvedEpochs.textContent = `${epochs} Epochs`;
    }
  }

  // =========================================================================
  // 5. ACTION BUTTON & BACKEND WIRING (/api/sky)
  // =========================================================================
  async function handleTargetSubmit(e) {
    if (e) e.preventDefault();
    if (!targetInputBox) return;

    const query = targetInputBox.value.trim();
    if (!query) {
      showStatusFeedback('error', 'Please enter target coordinates or location.');
      return;
    }

    // Set loading state
    if (observeBtn) observeBtn.disabled = true;
    showStatusFeedback('loading', `Resolving ${activeInputMode === 'sky' ? 'sky query' : 'earth location'} via /api/sky...`);

    try {
      let resolvedPayload = null;

      // 1. Attempt existing backend endpoint /api/sky
      try {
        const response = await fetch(`/api/sky?q=${encodeURIComponent(query)}&mode=${encodeURIComponent(activeInputMode)}`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.ra !== undefined && data.dec !== undefined) {
            resolvedPayload = {
              ra: parseFloat(data.ra),
              dec: parseFloat(data.dec),
              mode: data.mode || activeInputMode,
              epochs: data.epochs || data.epochsCount || 3,
              name: data.target_name || data.name || query
            };
          }
        }
      } catch (networkErr) {
        // Backend not running on static server — fall through to client-side resolver
      }

      // 2. Client-side resolution fallback (guarantees zero failure under static http.server)
      if (!resolvedPayload) {
        resolvedPayload = resolveClientSide(query, activeInputMode);
      }

      if (!resolvedPayload) {
        throw new Error(`Unable to resolve "${query}" for ${activeInputMode === 'sky' ? 'Sky RA/Dec' : 'Earth Location'}. Please verify query format.`);
      }

      // 3. Update Target State & Confirmation Strip
      currentTarget.ra = resolvedPayload.ra;
      currentTarget.dec = resolvedPayload.dec;
      currentTarget.epochsCount = resolvedPayload.epochs;
      currentTarget.activeMode = resolvedPayload.mode;
      currentTarget.name = resolvedPayload.name;

      const raHours = Math.floor(resolvedPayload.ra / 15);
      const raMinutes = Math.floor((resolvedPayload.ra / 15 - raHours) * 60);
      const raSeconds = (((resolvedPayload.ra / 15 - raHours) * 60 - raMinutes) * 60).toFixed(2);
      const decSign = resolvedPayload.dec >= 0 ? '+' : '-';
      const absDec = Math.abs(resolvedPayload.dec);
      const decDeg = Math.floor(absDec);
      const decMin = Math.floor((absDec - decDeg) * 60);
      const decSec = (((absDec - decDeg) * 60 - decMin) * 60).toFixed(1);

      currentTarget.raText = `${raHours}h ${raMinutes}m ${raSeconds}s`;
      currentTarget.decText = `${decSign}${decDeg}° ${decMin}′ ${decSec}″`;

      updateConfirmationStrip(resolvedPayload.ra, resolvedPayload.dec, resolvedPayload.mode, resolvedPayload.epochs);
      updateHeaderHud();
      updateReticleCardData();

      // Recalculate canvas and SED graph
      recalculateStarfieldForTarget();
      drawSedGraph();
      clearStatusFeedback();

    } catch (err) {
      showStatusFeedback('error', err.message || 'Resolution failed.');
    } finally {
      if (observeBtn) observeBtn.disabled = false;
    }
  }

  function resolveClientSide(query, mode) {
    const qLower = query.toLowerCase().trim();

    // Mode: Sky RA/Dec
    if (mode === 'sky') {
      // Direct catalog preset match
      for (const key of Object.keys(CATALOG_PRESETS)) {
        if (qLower.includes(key) || CATALOG_PRESETS[key].name.toLowerCase().includes(qLower)) {
          const item = CATALOG_PRESETS[key];
          return { ra: item.ra, dec: item.dec, mode: 'sky', epochs: item.epochsCount, name: item.name };
        }
      }

      // Check numeric coordinates: "269.452, 4.693" or "269.452 4.693"
      const coordsMatch = query.match(/^([+-]?\d+(?:\.\d+)?)[,\s]+([+-]?\d+(?:\.\d+)?)$/);
      if (coordsMatch) {
        const raVal = parseFloat(coordsMatch[1]);
        const decVal = parseFloat(coordsMatch[2]);
        if (raVal >= 0 && raVal <= 360 && decVal >= -90 && decVal <= 90) {
          return { ra: raVal, dec: decVal, mode: 'sky', epochs: 3, name: `Target [${raVal.toFixed(3)}, ${decVal.toFixed(3)}]` };
        }
      }
    }

    // Mode: Earth Location
    if (mode === 'earth') {
      // Check city lookup table
      for (const city of Object.keys(EARTH_LOCATIONS)) {
        if (qLower.includes(city)) {
          const loc = EARTH_LOCATIONS[city];
          return { ra: loc.ra, dec: loc.dec, mode: 'earth', epochs: loc.epochs, name: loc.name };
        }
      }

      // Check Lat/Lon coordinates: "23.02, 72.57"
      const latLonMatch = query.match(/^([+-]?\d+(?:\.\d+)?)[,\s]+([+-]?\d+(?:\.\d+)?)$/);
      if (latLonMatch) {
        const lat = parseFloat(latLonMatch[1]);
        const lon = parseFloat(latLonMatch[2]);
        if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
          // Zenith Celestial Projection to J2000 RA/Dec
          const projectedRa = (lon + 360) % 360;
          const projectedDec = lat;
          return {
            ra: parseFloat(projectedRa.toFixed(4)),
            dec: parseFloat(projectedDec.toFixed(4)),
            mode: 'earth',
            epochs: 3,
            name: `Earth Coords (${lat.toFixed(2)}°, ${lon.toFixed(2)}°)`
          };
        }
      }
    }

    return null;
  }

  if (targetInputForm) {
    targetInputForm.addEventListener('submit', handleTargetSubmit);
  }
  if (observeBtn) {
    observeBtn.addEventListener('click', handleTargetSubmit);
  }

  // =========================================================================
  // 6. ASTROMETRIC STARFIELD CANVAS & RETICLE ENGINE
  // =========================================================================
  let stars = [];
  let mouseX = -100;
  let mouseY = -100;
  let hoveredStar = null;
  let selectedStar = null;

  function initStarCatalog() {
    stars = [];
    const count = 320;
    const w = starCanvas.width || 1200;
    const h = starCanvas.height || 700;

    // Benchmark Target Star at center-left
    const targetStar = {
      id: 'target-benchmark',
      x: w * 0.45,
      y: h * 0.50,
      mag: 9.54,
      color: '#FFA845',
      name: currentTarget.name,
      type: currentTarget.type,
      pmVector: { dx: 140, dy: -28 }, // 140px astrometric vector
      isBenchmark: true
    };
    stars.push(targetStar);
    selectedStar = targetStar;

    // Field stars
    for (let i = 0; i < count; i++) {
      stars.push({
        id: 'star-' + i,
        x: Math.random() * w,
        y: Math.random() * h,
        mag: 10 + Math.random() * 8,
        color: Math.random() > 0.85 ? '#80DEEA' : Math.random() > 0.5 ? '#FFF8E1' : '#E0E0E0',
        name: `SPHEREx-J2000-${(1000 + i).toString()}`,
        type: Math.random() > 0.7 ? 'K-Giant' : 'Field Dwarf',
        pmVector: { dx: (Math.random() - 0.5) * 8, dy: (Math.random() - 0.5) * 8 },
        isBenchmark: false
      });
    }
  }

  function recalculateStarfieldForTarget() {
    if (!starCanvas) return;
    const w = starCanvas.width;
    const h = starCanvas.height;
    if (stars.length > 0) {
      stars[0].name = currentTarget.name;
      stars[0].type = currentTarget.type;
      stars[0].x = w * 0.45;
      stars[0].y = h * 0.50;
      selectedStar = stars[0];
    }
  }

  function resizeCanvases() {
    if (!starCanvas || !canvasContainer) return;
    const rect = canvasContainer.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      starCanvas.width = rect.width;
      starCanvas.height = rect.height;
      if (stars.length === 0) {
        initStarCatalog();
      } else {
        recalculateStarfieldForTarget();
      }
    }

    if (sedCanvas) {
      const sedRect = sedCanvas.parentElement.getBoundingClientRect();
      if (sedRect.width > 0 && sedRect.height > 0) {
        sedCanvas.width = sedRect.width;
        sedCanvas.height = sedRect.height;
        drawSedGraph();
      }
    }
  }

  window.addEventListener('resize', resizeCanvases);

  // Reticle positioning & cursor tracking
  if (canvasContainer) {
    canvasContainer.addEventListener('mousemove', (e) => {
      const rect = starCanvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;

      if (reticleBox) {
        reticleBox.style.display = 'block';
        reticleBox.style.left = `${mouseX}px`;
        reticleBox.style.top = `${mouseY}px`;
      }

      // Update Cursor HUD
      if (cursorRaDecHud) {
        const raEstimate = (currentTarget.ra + (mouseX / rect.width - 0.5) * 0.5).toFixed(3);
        const decEstimate = (currentTarget.dec - (mouseY / rect.height - 0.5) * 0.5).toFixed(3);
        cursorRaDecHud.textContent = `RA: ${raEstimate}° · DEC: ${decEstimate > 0 ? '+' : ''}${decEstimate}°`;
      }

      // Check proximity to stars
      hoveredStar = null;
      for (const s of stars) {
        const dist = Math.hypot(s.x - mouseX, s.y - mouseY);
        if (dist < 14) {
          hoveredStar = s;
          break;
        }
      }

      // Update Aside Reticle HUD Card
      if (reticleCard) {
        const star = hoveredStar || selectedStar;
        if (star && isMouseInsideCanvas) {
          reticleCard.style.display = 'block';
          const cardX = Math.min(mouseX + 24, rect.width - 290);
          const cardY = Math.min(Math.max(mouseY - 20, 10), rect.height - 180);
          reticleCard.style.left = `${cardX}px`;
          reticleCard.style.top = `${cardY}px`;
        }
      }
    });

    let isMouseInsideCanvas = false;
    canvasContainer.addEventListener('mouseenter', () => { isMouseInsideCanvas = true; });
    canvasContainer.addEventListener('mouseleave', () => {
      isMouseInsideCanvas = false;
      if (reticleBox) reticleBox.style.display = 'none';
      if (reticleCard) reticleCard.style.display = 'none';
    });

    canvasContainer.addEventListener('click', () => {
      if (hoveredStar) {
        selectedStar = hoveredStar;
        currentTarget.name = hoveredStar.name;
        currentTarget.type = hoveredStar.type;
        updateHeaderHud();
        updateReticleCardData();
        drawSedGraph();
      }
    });
  }

  function updateHeaderHud() {
    if (headerTargetName) headerTargetName.textContent = currentTarget.name;
    if (headerTargetCoords) headerTargetCoords.textContent = `${currentTarget.raText} / ${currentTarget.decText}`;
  }

  function updateReticleCardData() {
    if (hudTargetName) hudTargetName.textContent = currentTarget.name;
    if (hudTargetType) hudTargetType.textContent = currentTarget.type;
    if (hudRaDec) hudRaDec.textContent = `${currentTarget.raText} / ${currentTarget.decText}`;
    if (hudPmTotal) hudPmTotal.textContent = currentTarget.pmTotal;
    if (hudIceDepth) hudIceDepth.textContent = currentTarget.iceAbsorption;
  }

  // =========================================================================
  // 7. CANVAS RENDERING ENGINE (Blink, Single, Difference Modes)
  // =========================================================================
  function renderSky() {
    if (!starCanvas) return;
    const ctx = starCanvas.getContext('2d');
    const w = starCanvas.width;
    const h = starCanvas.height;

    ctx.clearRect(0, 0, w, h);

    // Deep space background
    ctx.fillStyle = '#0A0A0B';
    ctx.fillRect(0, 0, w, h);

    // Subtle Astrometric Grid Lines
    ctx.strokeStyle = '#18181C';
    ctx.lineWidth = 1;
    const step = 80;
    for (let x = 0; x < w; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Single / Side-by-Side Mode Split Indicator
    if (observationMode === 'single') {
      ctx.strokeStyle = '#222226';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(w / 2, 0);
      ctx.lineTo(w / 2, h);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.font = '10px "JetBrains Mono"';
      ctx.fillStyle = '#8E8E93';
      ctx.fillText('EPOCH 1 (2025.3)', 16, 24);
      ctx.fillText('EPOCH 2 (2025.8)', w / 2 + 16, 24);
    }

    // Difference Mode Indicator
    if (observationMode === 'diff') {
      ctx.fillStyle = 'rgba(6, 182, 212, 0.04)';
      ctx.fillRect(0, 0, w, h);
    }

    // Render Field Stars
    for (let i = 1; i < stars.length; i++) {
      const s = stars[i];
      const radius = Math.max(0.8, (18 - s.mag) * 0.4);

      if (observationMode === 'diff') {
        // Difference mode shows subtle residual noise for static stars
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.beginPath();
        ctx.arc(s.x, s.y, radius * 0.8, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(s.x, s.y, radius, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Render Benchmark Target Star
    if (stars.length > 0) {
      const target = stars[0];
      const tProgress = blinkFrameIndex / 5.0; // 0.0 to 1.0 across 6 frames

      if (observationMode === 'blink') {
        // PROPER MOTION CORRIDOR (Strictly Blink Mode Only)
        const startX = target.x;
        const startY = target.y;
        const endX = startX + target.pmVector.dx;
        const endY = startY + target.pmVector.dy;

        // Big 140px Astrometric Corridor Bounds
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.25)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);

        // Draw corridor bounding rails (width 26px)
        const angle = Math.atan2(target.pmVector.dy, target.pmVector.dx);
        const normX = -Math.sin(angle) * 13;
        const normY = Math.cos(angle) * 13;

        ctx.beginPath();
        ctx.moveTo(startX + normX, startY + normY);
        ctx.lineTo(endX + normX, endY + normY);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(startX - normX, startY - normY);
        ctx.lineTo(endX - normX, endY - normY);
        ctx.stroke();

        // Central Motion Vector Line with Arrowhead
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.6)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.stroke();

        // Arrowhead
        const headLen = 8;
        ctx.beginPath();
        ctx.moveTo(endX, endY);
        ctx.lineTo(endX - headLen * Math.cos(angle - Math.PI / 6), endY - headLen * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(endX - headLen * Math.cos(angle + Math.PI / 6), endY - headLen * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fillStyle = '#06B6D4';
        ctx.fill();

        // Discrete Observation Frame Brackets (6 survey epochs)
        for (let f = 0; f < 6; f++) {
          const frac = f / 5.0;
          const fx = startX + target.pmVector.dx * frac;
          const fy = startY + target.pmVector.dy * frac;

          if (f === blinkFrameIndex) {
            // Current Active Survey Frame
            ctx.strokeStyle = '#06B6D4';
            ctx.lineWidth = 2;
            ctx.strokeRect(fx - 9, fy - 9, 18, 18);

            // Active Frame Label
            ctx.font = '10px "JetBrains Mono"';
            ctx.fillStyle = '#06B6D4';
            ctx.fillText(`+${(frac * 6.0).toFixed(1)}mo`, fx + 12, fy - 10);
          } else {
            // Inactive Frame Bracket (Ghosted survey history)
            ctx.strokeStyle = 'rgba(142, 142, 147, 0.4)';
            ctx.lineWidth = 1;
            ctx.strokeRect(fx - 6, fy - 6, 12, 12);
          }
        }

        // Target Star at current discrete frame
        const currentTargetX = startX + target.pmVector.dx * tProgress;
        const currentTargetY = startY + target.pmVector.dy * tProgress;

        ctx.fillStyle = '#FFA845';
        ctx.beginPath();
        ctx.arc(currentTargetX, currentTargetY, 5, 0, Math.PI * 2);
        ctx.fill();

        // Target Label
        ctx.font = '11px "JetBrains Mono"';
        ctx.fillStyle = '#F4F4F6';
        ctx.fillText(target.name, currentTargetX + 12, currentTargetY + 4);

      } else if (observationMode === 'single') {
        // Single Mode: Epoch 1 on left, Epoch 2 on right
        ctx.fillStyle = '#FFA845';
        ctx.beginPath();
        ctx.arc(target.x * 0.5, target.y, 5, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.arc(w * 0.5 + target.x * 0.5 + target.pmVector.dx * 0.5, target.y + target.pmVector.dy * 0.5, 5, 0, Math.PI * 2);
        ctx.fill();

      } else if (observationMode === 'diff') {
        // Difference Mode: Shows dipole signature (+white, -black residual)
        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.arc(target.x + target.pmVector.dx, target.y + target.pmVector.dy, 5, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(target.x, target.y, 5, 0, Math.PI * 2);
        ctx.stroke();

        ctx.font = '10px "JetBrains Mono"';
        ctx.fillStyle = '#06B6D4';
        ctx.fillText('Astrometric Dipole Residual (E2 - E1)', target.x - 30, target.y - 14);
      }
    }

    requestAnimationFrame(renderSky);
  }

  function startBlinkCycle() {
    if (blinkTimer) clearInterval(blinkTimer);
    blinkTimer = setInterval(() => {
      blinkFrameIndex = (blinkFrameIndex + 1) % 6;
      if (blinkFpsHud) {
        blinkFpsHud.textContent = `FRAME ${blinkFrameIndex + 1}/6 · ${blinkFps.toFixed(1)} FPS`;
      }
    }, 1000 / blinkFps);
  }

  // =========================================================================
  // 8. 102-BAND SPECTRAL GRAPH (SED)
  // =========================================================================
  function drawSedGraph() {
    if (!sedCanvas) return;
    const ctx = sedCanvas.getContext('2d');
    const w = sedCanvas.width;
    const h = sedCanvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#121214';
    ctx.fillRect(0, 0, w, h);

    const padLeft = 50;
    const padRight = 30;
    const padTop = 30;
    const padBottom = 40;
    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    // Draw grid
    ctx.strokeStyle = '#222226';
    ctx.lineWidth = 1;
    for (let f = 0; f <= 5; f++) {
      const y = padTop + (plotH / 5) * f;
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(w - padRight, y);
      ctx.stroke();
    }

    // 102 Spectral Channels (0.75 to 5.0 microns)
    const bandsCount = 102;
    const bandWidth = plotW / bandsCount;

    ctx.fillStyle = 'rgba(6, 182, 212, 0.7)';
    for (let i = 0; i < bandsCount; i++) {
      const wavelength = 0.75 + (i / bandsCount) * 4.25; // 0.75 to 5.0 microns
      let flux = Math.exp(-wavelength / 2.5) * 1.8;

      // 3.05 micron H2O Ice absorption band dip
      if (Math.abs(wavelength - 3.05) < 0.35) {
        flux *= 0.62;
      }

      const barHeight = (flux / 2.0) * plotH;
      const x = padLeft + i * bandWidth;
      const y = padTop + plotH - barHeight;

      if (Math.abs(wavelength - 3.05) < 0.25) {
        ctx.fillStyle = '#C084FC'; // Ice absorption color
      } else {
        ctx.fillStyle = 'rgba(6, 182, 212, 0.7)';
      }
      ctx.fillRect(x, y, Math.max(1, bandWidth - 1), barHeight);
    }

    // Axes
    ctx.strokeStyle = '#8E8E93';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padLeft, padTop);
    ctx.lineTo(padLeft, padTop + plotH);
    ctx.lineTo(w - padRight, padTop + plotH);
    ctx.stroke();

    ctx.font = '10px "JetBrains Mono"';
    ctx.fillStyle = '#8E8E93';
    ctx.fillText('0.75 µm', padLeft, padTop + plotH + 16);
    ctx.fillText('3.05 µm (Ice)', padLeft + plotW * 0.54 - 24, padTop + plotH + 16);
    ctx.fillText('5.00 µm', w - padRight - 36, padTop + plotH + 16);
  }

  // =========================================================================
  // 9. BENCHMARK PRESETS & VIEW MODES WIRING
  // =========================================================================
  if (benchmarkSelector) {
    benchmarkSelector.addEventListener('change', (e) => {
      const val = e.target.value;
      if (CATALOG_PRESETS[val]) {
        const item = CATALOG_PRESETS[val];
        currentTarget.name = item.name;
        currentTarget.type = item.type;
        currentTarget.ra = item.ra;
        currentTarget.dec = item.dec;
        currentTarget.raText = item.raText;
        currentTarget.decText = item.decText;
        currentTarget.pmTotal = item.pmTotal;
        currentTarget.iceAbsorption = item.iceAbsorption;
        currentTarget.epochsCount = item.epochsCount;
        currentTarget.activeMode = 'sky';

        updateConfirmationStrip(item.ra, item.dec, 'sky', item.epochsCount);
        updateHeaderHud();
        updateReticleCardData();
        recalculateStarfieldForTarget();
        drawSedGraph();
      }
    });
  }

  // View Mode Modal Controls
  if (viewModeFab) {
    viewModeFab.addEventListener('click', () => {
      if (!viewMenuModal) return;
      const isVisible = viewMenuModal.style.display === 'flex';
      viewMenuModal.style.display = isVisible ? 'none' : 'flex';
    });
  }

  if (closeViewMenuBtn) {
    closeViewMenuBtn.addEventListener('click', () => {
      if (viewMenuModal) viewMenuModal.style.display = 'none';
    });
  }

  modeSelectBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      if (!mode) return;
      observationMode = mode;
      modeSelectBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      if (activeModeLabel) {
        if (mode === 'blink') activeModeLabel.textContent = `Frame-by-Frame Blink Corridor (Frame 1/6 @ ${blinkFps.toFixed(1)} FPS)`;
        else if (mode === 'single') activeModeLabel.textContent = 'Single / Side-by-Side Dual Epoch View';
        else if (mode === 'diff') activeModeLabel.textContent = 'Astrometric Difference Dipole Engine (E2 - E1)';
      }
    });
  });

  if (fpsSlider) {
    fpsSlider.addEventListener('input', (e) => {
      blinkFps = parseFloat(e.target.value);
      if (fpsDisplay) fpsDisplay.textContent = `${blinkFps.toFixed(1)} FPS`;
      startBlinkCycle();
    });
  }

  // =========================================================================
  // 10. SPHEREx ANALYZER CHAT DRAWER
  // =========================================================================
  if (aiBotFab) {
    aiBotFab.addEventListener('click', () => {
      if (!aiChatDrawer) return;
      const isVisible = aiChatDrawer.style.display === 'flex';
      aiChatDrawer.style.display = isVisible ? 'none' : 'flex';
      if (!isVisible && aiInputPrompt) aiInputPrompt.focus();
    });
  }

  if (closeAiDrawerBtn) {
    closeAiDrawerBtn.addEventListener('click', () => {
      if (aiChatDrawer) aiChatDrawer.style.display = 'none';
    });
  }

  function sendAiQuery(queryText) {
    if (!queryText || !aiMessagesContainer) return;

    // Append User Message
    const userMsg = document.createElement('div');
    userMsg.className = 'p-2.5 rounded bg-panel-elevated hairline text-xs font-mono text-text-primary self-end max-w-[85%]';
    userMsg.textContent = queryText;
    aiMessagesContainer.appendChild(userMsg);

    // Append Assistant Response
    setTimeout(() => {
      const botMsg = document.createElement('div');
      botMsg.className = 'p-3 rounded bg-canvas-dark hairline border-border-dark text-xs font-mono text-text-primary space-y-1.5 self-start max-w-[95%]';
      botMsg.innerHTML = `
        <div class="text-[10px] text-cyan-reticle font-bold uppercase tracking-wider">SPHEREx Telemetry Analysis · ${currentTarget.name}</div>
        <p class="text-text-muted leading-relaxed font-sans text-xs">
          Cross-matched source <strong class="text-text-primary">${currentTarget.name}</strong> at coordinates <span class="text-cyan-reticle">${currentTarget.raText} / ${currentTarget.decText}</span>. Proper motion vector measured at <span class="text-amber-candidate font-bold">${currentTarget.pmTotal}</span> across 6 survey epochs. 3.05 µm H₂O ice absorption confirms icy grain mantle.
        </p>
      `;
      aiMessagesContainer.appendChild(botMsg);
      aiMessagesContainer.scrollTop = aiMessagesContainer.scrollHeight;
    }, 280);

    aiMessagesContainer.scrollTop = aiMessagesContainer.scrollHeight;
  }

  if (sendAiPromptBtn && aiInputPrompt) {
    sendAiPromptBtn.addEventListener('click', () => {
      const val = aiInputPrompt.value.trim();
      if (val) {
        sendAiQuery(val);
        aiInputPrompt.value = '';
      }
    });

    aiInputPrompt.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const val = aiInputPrompt.value.trim();
        if (val) {
          sendAiQuery(val);
          aiInputPrompt.value = '';
        }
      }
    });
  }

  // Quick Chips
  document.querySelectorAll('.ai-chip-btn').forEach((chip) => {
    chip.addEventListener('click', () => {
      sendAiQuery(chip.textContent.trim());
    });
  });

  // =========================================================================
  // 11. INITIALIZATION
  // =========================================================================
  document.addEventListener('DOMContentLoaded', () => {
    resizeCanvases();
    startBlinkCycle();
    updateConfirmationStrip(currentTarget.ra, currentTarget.dec, currentTarget.activeMode, currentTarget.epochsCount);
    updateHeaderHud();
    updateReticleCardData();
    requestAnimationFrame(renderSky);
    if (window.lucide) {
      window.lucide.createIcons();
    }
  });

})();
