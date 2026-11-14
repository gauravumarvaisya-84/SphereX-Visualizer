# SPHEREx Visualizer & Object Identifier
### Team Pioneer Matrix &bull; NASA Space Apps Challenge 2026
**Challenge:** Planet X and SPHEREx (Spectro-Photometer for the History of the Universe, Epoch of Reionization, and Ices Explorer)

[![NASA Space Apps 2026](https://img.shields.io/badge/NASA%20Space%20Apps-2026%20Global%20Challenge-blue.svg)](https://www.spaceappschallenge.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](#)
[![Astropy](https://img.shields.io/badge/Astronomy-Astropy%20%26%20Astroquery-orange.svg)](#)
[![Canvas Engine](https://img.shields.io/badge/Frontend-HTML5%20Canvas%20ImageData-00e5ff.svg)](#)

---

## 1. Executive Summary & Mission Overview

The **SPHEREx Visualizer & Object Identifier** is an astronomical analysis tool and mission-control platform engineered by **Team Pioneer Matrix** for the 2026 NASA Space Apps Challenge. 

NASA's **SPHEREx** mission surveys the entire celestial sphere every six months across **102 near-infrared spectral channels** ($0.75 - 5.0\,\mu\text{m}$) using six Linear Variable Filter (LVF) detector arrays. This bi-annual cadence and wide spectral grasp provides an unprecedented opportunity to discover:
1. **Hypothetical Outer Solar System Bodies (Planet X / Trans-Neptunian Objects):** High-albedo infrared emitters exhibiting significant transverse parallax and proper motion between 6-month epochs.
2. **Sub-Stellar Brown Dwarfs (Y- and T-types):** Ultra-cool objects ($T_{\text{eff}} < 500\,\text{K}$) with atmospheres laden with methane ($CH_4$), water vapor ($H_2O$), and water-ice clouds, completely invisible to optical surveys (e.g. Gaia DR3 $G > 21.0$).
3. **High Proper-Motion Stellar Neighbors:** Nearby low-mass stars (M-dwarfs) shifting several arcseconds per year.
4. **Infrared Flux Variables & Occultations:** Young stellar objects (T Tauri) and pulsating asymptotic giant branch stars (Miras).

Our platform combines a **live Caltech/IPAC IRSA TAP scraper**, a **sub-pixel image differencing engine**, a **multi-epoch blink comparator (1–8 fps)**, a **102-band spectral energy distribution (SED) diagnostic tool**, and an **AI astrophysics explainer powered by Google Gemini**.

---

## 2. Benchmark Targets

Our system comes pre-configured with 5 official benchmark targets covering the full spectrum of high-proper-motion, sub-stellar, and variable infrared phenomena:

| Target Name | J2000 Coordinates ($\alpha, \delta$) | Proper Motion ($\mu$) | Spectral Type | Distance | Scientific Benchmark Significance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Barnard's Star** | `269.452083°, +04.693389°` | $10.36''/\text{yr}$ | M4.0V | 5.96 ly (1.83 pc) | Fastest proper motion star in the sky; calibration standard for cross-epoch 6-month dipole shifts ($5.18''$). |
| **WISE 0855-0714** | `133.795129°, -07.245147°` | $8.16''/\text{yr}$ | Y2 | 7.53 ly (2.31 pc) | 4th closest stellar/sub-stellar system; sub-freezing ($\sim 250\,\text{K}$) brown dwarf with $H_2O$ ice clouds; invisible to Gaia optical. |
| **Epsilon Indi B** | `331.043792°, -56.782694°` | $4.70''/\text{yr}$ | T1 + T6 | 11.87 ly (3.64 pc) | Benchmark binary brown dwarf system exhibiting deep methane ($CH_4$) and water absorption. |
| **RW Aurigae** | `076.956417°, +30.401417°` | $0.021''/\text{yr}$ | T Tauri | 531 ly (163 pc) | Pre-main-sequence binary undergoing multi-magnitude circumstellar dust stream obscuration events. |
| **R Draconis** | `248.167625°, +66.755000°` | $0.023''/\text{yr}$ | M5e-M9e III | 2100 ly (644 pc) | High-amplitude Mira variable ($\sim 245$-day pulsation) yielding dramatic single-epoch unipolar difference residuals. |

---

## 3. Extracted Observables & Science Key

| Observable | Extraction Engine | Physical Interpretation |
| :--- | :--- | :--- |
| **Cross-Epoch Dipole** | $D(x, y) = I_{\text{Ep2}}(x, y) - I_{\text{Ep1}}(x, y)$ | Static stars cancel ($|\Delta| \le 15$). Moving objects form an amber peak ($+ \Delta$) adjacent to a cyan trough ($- \Delta$). |
| **6-Month Angular Shift** | $\Delta \theta = \frac{\sqrt{\mu_\alpha^{*2} + \mu_\delta^2} \times 0.5}{1000}$ | Quantifies transverse angular displacement across successive 6-month SPHEREx scans. |
| **Optical-to-IR Ratio** | $F_{\text{Gaia}} / F_{\text{SPHEREx}}$ | Values $< 0.01$ indicate uncatalogued ultra-cool brown dwarfs or outer solar system bodies. |
| **Molecular Markers** | 102-Band SED Decomposition | Identifies $H_2O$ vapor ($1.4\,\mu\text{m}, 1.9\,\mu\text{m}$), $CH_4$ ($1.66\,\mu\text{m}, 2.2\,\mu\text{m}, 3.32\,\mu\text{m}$), $CO_2$ ($4.26\,\mu\text{m}$), and $4.65\,\mu\text{m}$ opacity window. |

---

## 4. System Architecture

```
   +-----------------------------------------------------------------------------------------+
   |                             USER / CITIZEN SCIENTIST / JUDGE                            |
   +-----------------------------------------------------------------------------------------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
         [Astronomical Name / Coord]                                [City / Address]
                     |                                                 |
                     v                                                 v
           CDS Sesame / SIMBAD                               OpenStreetMap Nominatim
                     |                                                 |
                     +------------------------+------------------------+
                                              |
                                  J2000 (RA, Dec) + Epoch
                                              |
                                              v
         +-------------------------------------------------------------------------+
         |                    FastAPI Backend & Astrometry Engine                  |
         |  - Irsa.query_tap ("spherex.artifact" & "spherex.plane")                |
         |  - Local Calibrated FITS / Astrometric Physics Simulator                |
         |  - Zodiacal Background Light Subtraction (IMAGE - ZODI)                 |
         |  - log1p Dynamic Stretch & uint8 Resampling (128 x 128)                 |
         |  - MD5 Hash Live Caching in config/cutouts/live_cache/                  |
         +-------------------------------------------------------------------------+
                                              |
                            JSON Payload (Epochs & 102-band SED)
                                              |
                                              v
         +-------------------------------------------------------------------------+
         |                   Single-Page Mission-Control UI (HTML5)                |
         |  - Canvas 1: Single Epoch | Blink (1-8 fps) | Difference (Ep2 - Ep1)    |
         |  - Canvas 2: 102-Band SED across Arrays 1-6 with Molecular Notches      |
         |  - Interactive Target Reticle & Proper Motion Vector Arrow              |
         |  - Object Identification HUD (Gaia DR3 vs. UNCATALOGED Candidate)      |
         |  - Gemini AI Explainer Integration (/api/explain)                       |
         +-------------------------------------------------------------------------+
```

---

## 5. Quickstart & Verification

### Prerequisites
- Python 3.10+ (tested on Python 3.11, 3.12, and 3.14)
- Git

### Installation
```bash
# 1. Clone or navigate to the repository
cd SpaceTex/SphereX

# 2. Create and activate a Python virtual environment
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install required astronomical and backend packages
pip install numpy astropy astroquery fastapi uvicorn requests
```

### Running Unit Tests
```bash
python scripts/test_pipeline.py
```
*Executes all 4 unit test modules: coordinate parsing/roundtrips, 6-month proper motion shifts, difference matrix dipole behavior, and 102-band SED array validation.*

### Pre-Caching Benchmark Cutouts
```bash
python scripts/fetch_all_targets.py
```
*Queries IRSA TAP / calibrated simulator and pre-caches `barnards_star.json`, `wise_0855.json`, `eps_indi_b.json`, `rw_aurigae.json`, and `r_draconis.json` into `config/cutouts/`.*

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
SphereX/
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
│   ├── index.html                  # Sleek single-page HTML5 Canvas mission-control interface
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
