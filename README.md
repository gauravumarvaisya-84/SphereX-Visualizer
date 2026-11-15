# SPHEREx Mission Visualizer
### Team Pioneer Matrix &bull; NASA Space Apps Challenge 2026
**Challenge:** Planet X and SPHEREx (Spectro-Photometer for the History of the Universe, Epoch of Reionization, and Ices Explorer)

[![NASA Space Apps 2026](https://img.shields.io/badge/NASA%20Space%20Apps-2026%20Global%20Challenge-blue.svg)](https://www.spaceappschallenge.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](#)
[![Astropy](https://img.shields.io/badge/Astronomy-Astropy%20%26%20Astroquery-orange.svg)](#)
[![Canvas Engine](https://img.shields.io/badge/Frontend-HTML5%20Canvas%20ImageData-00e5ff.svg)](#)

---

## 1. Overview

The application resolves a user supplied sky target (name or supported coordinate frame) or Earth location, queries the IRSA SPHEREx archive, processes returned FITS cutouts, and sends a compact JSON payload to a tabbed visualizer. The API returns the resolved ICRS coordinates, observation epochs, measured spectral points when they can be extracted, and provenance metadata.

Archive retrieval is the source of scientific measurements. If IRSA cannot return usable products, the backend can supply clearly labeled simulated image epochs so the interface remains explorable; these are not archive observations and are not sent to the assistant as measurements. No target-specific spectrum or object-to-color behavior is used. Cache entries are keyed by resolved coordinates and query parameters.

The spectral panel plots only wavelength/flux measurements extracted from FITS/WCS data. Empty spectral results are shown as unavailable. The assistant receives scalar metadata and a small set of spectral points, never image pixel arrays; its local fallback reports missing measurements instead of inventing them.

The API keeps the latest successful live archive payload when a refresh fails and marks it as stale. Cache keys are stable across application schema upgrades and include resolved coordinates and retrieval parameters. Local runs use `config/cutouts/live_cache`; on a host with an ephemeral filesystem, mount a persistent volume and set `SPHEREX_CACHE_DIR` to that mounted path. Without a persistent volume, data cannot survive the host replacing its instance, regardless of the application cache logic.

## 2. General workflow

1. The UI submits a sky name/coordinate or an Earth place/latitude-longitude pair, plus archive bandpass, field size, and epoch count.
2. The backend resolves sky coordinates to ICRS, or computes the current zenith coordinates for the Earth location. The response echoes the resolved position.
3. The backend queries IRSA dynamically, groups nearby observations into separated epochs, downloads FITS products with bounded retries, and caches by coordinate and query parameters.
4. The FITS processor reads the IMAGE plane and available FLAGS, VARIANCE, ZODI, and WCS metadata; estimates and subtracts background, masks flagged pixels, clips at a 3-sigma floor, log-stretches, resamples, and normalizes all epochs to a shared display range.
5. The tabbed UI renders individual epochs, blinking, side-by-side/wipe comparisons, differences, and any measured spectral points. Simulated fallback frames are labeled and are never represented as archive data. The assistant receives compact metadata and up to 24 measured spectral points, never image arrays.

## 3. API contract

`GET /api/sky` accepts `q`, `input_mode`, `bandpass`, `size_deg`, `max_epochs`, and `refresh_archive`. Its JSON response has four top-level fields: `coordinates`, `epochs`, `spectral_points`, and `metadata`. Each epoch contains its display pixel grid and time; metadata contains source, retrieval notes, and FITS provenance. Spectral points are empty when target-position wavelength/flux samples cannot be extracted.

`POST /api/analyze` accepts a question, recent chat turns, and a compact active-target summary. With `GEMINI_API_KEY`, the configured model answers using only the supplied summary; without it, a limited local fallback reports the available values and missing data. Raw image pixels are not sent. Configure `ANALYZER_ACCESS_TOKEN` before exposing analyzer access beyond localhost.

## 4. Important data limits

Archive availability, coordinate resolution, FITS WCS layouts, and network access determine which products can be returned. Simulated image epochs preserve the UI workflow during archive failures, but they do not validate archive detection, photometry, motion, or spectral features. The spectral view intentionally shows no curve when no measured points are available.

## 5. Quickstart & Verification

### Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, and 3.14)
- Git

### Installation
```bash
# Run these commands from the repository root

# 2. Create and activate a Python virtual environment
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install required astronomical and backend packages
pip install -r requirements.txt
```

Optional Gemini setup: copy `.env.example` to `.env`, add your `GEMINI_API_KEY`, and set `AI_NAME` to customize the assistant label. The key stays on the backend; the frontend sends only target summary fields, recent chat turns, and a compact sample of measured spectral points to `/api/analyze`. Image pixels stay in the browser. The `.env` file is Git-ignored; never commit or publish it.

The backend listens on localhost by default. Keep it local for personal use. If you intentionally expose it remotely, configure a random `ANALYZER_ACCESS_TOKEN` (at least 32 characters) and an exact `CORS_ORIGINS` allowlist in the backend `.env`; generate a token with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and enter it in the chat panel. Serve the app and API over HTTPS so the access token is encrypted in transit. The token is held only in the current browser tab. If Gemini is rate limited, the assistant falls back to a metadata-only answer. For multi-worker public deployments, configure provider-side limits as well as the in-process safeguard.

### Running Unit Tests
```bash
python scripts/test_pipeline.py
python scripts/test_backend.py
```
`test_pipeline.py` checks coordinate parsing, proper-motion math, image-difference behavior, and that missing spectra are not replaced by synthetic templates. `test_backend.py` checks arbitrary coordinate resolution, Earth geocoder errors, alternate FITS recovery, multi-epoch processing, archive provenance, cache expiry, and preservation of the last valid archive result during a failed refresh. Archive interactions in backend tests are mocked.

### Fetching a target from the command line
```bash
python scripts/fetch_all_targets.py "42.125, -17.75"
```
*Resolves the supplied target and prints the returned archive products or explicitly labeled fallback payload. The app's collapsible benchmark list is served from `/api/benchmarks`.*

### Starting the Servers
Open two terminal windows:

**Terminal 1 — FastAPI Backend (Port 8000):**
```bash
uvicorn scripts.server:app --port 8000
```

**Terminal 2 — Mission Control Frontend (Port 8080):**
```bash
python -m http.server 8080 --directory app
```

Open your browser to: **`http://localhost:8080`**

---

## 6. Project Directory Layout

```
SPHEREx Mission Visualizer/
├── .gitignore                      # Git exclusion rules
├── LICENSE                         # MIT License
├── GEMINI.md                       # LLM agent context & project guide
├── README.md                       # Comprehensive mission documentation
├── config/
│   ├── targets.json                # Benchmark targets astrometry & metadata
│   └── cutouts/                    # Pre-cached JSON cutouts
│       ├── barnards_star.json
│       ├── wise_0855.json
│       ├── eps_indi_b.json
│       ├── rw_aurigae.json
│       ├── r_draconis.json
│       └── live_cache/             # MD5-hashed search query cutouts
├── scripts/
│   ├── astro_tools.py              # Astrometry parser, proper motion math, SED & diff engine
│   ├── test_pipeline.py            # Automated unit testing suite
│   ├── fetch_all_targets.py        # IRSA TAP query scraper & CLI pre-cacher
│   └── server.py                   # FastAPI backend with CORS, caching, and Gemini API explain
├── app/
│   ├── index.html                  # Mission-control page structure
│   ├── styles.css                  # Dark observatory design system
│   ├── app.js                      # Canvas views, target lookup, SED and analyzer chat
│   └── package.json                # Frontend metadata and scripts
└── docs/
    ├── PROJECT_PLAN.md             # 48-hour sprint log, milestones & post-hackathon roadmap
    ├── SYSTEM_ARCHITECTURE.md      # Detailed detector array, data flow & algorithm spec
    ├── BENCHMARK_TARGETS.md        # Physics, observational strategy & benchmarks
    ├── DATA_SOURCES.md             # IRSA, CDS Sesame, Gaia DR3, CatWISE & Nominatim specs
    └── OBJECT_IDENTIFICATION_AND_SCIENCE_GUIDE.md  # Scientific classification tree & workflows
```

---

## 7. License & Attribution
Developed with pride by **Team Pioneer Matrix** for the **NASA Space Apps Challenge 2026**.  
Distributed under the **MIT License**.
