# GEMINI.md - SphereX Visualizer & Object Identifier
**Team Pioneer Matrix — NASA Space Apps Challenge 2026**
**Challenge Focus:** Planet X and SPHEREx (Spectro-Photometer for the History of the Universe, Epoch of Reionization, and Ices Explorer)

---

## 1. Project Overview & Science Objectives
The **SphereX Visualizer & Object Identifier** is an astronomical analysis tool and interactive mission-control dashboard developed by Team **Pioneer Matrix** for the NASA Space Apps Challenge 2026.

SPHEREx scans the entire celestial sphere every 6 months across 102 near-infrared spectral bands (0.75–5.0 µm) utilizing 6 Linear Variable Filter (LVF) detector arrays. This mission is uniquely positioned to uncover undiscovered solar system objects (Planet X / Kuiper Belt Objects), ultra-cool Y/T-type brown dwarfs, high-proper-motion stellar neighbors, and infrared transient/variable phenomena.

### Core Capabilities:
1. **Multi-Input Target Resolution:** Accepts raw decimal coordinates (`RA, Dec`), catalog object designations (via CDS Sesame / Simbad), or Earth geographic locations/addresses (via OpenStreetMap Nominatim, converting to overhead zenith `RA, Dec` at epoch).
2. **Real-time Caltech/IPAC IRSA TAP Scraper:** Queries the official NASA/IPAC Infrared Science Archive TAP service (`spherex.artifact` and `spherex.plane`) to retrieve multi-epoch calibrated cutouts, subtract zodiacal background light, and extract spectral metadata.
3. **Multi-Epoch Blink Comparator:** Cycles multi-epoch observations at user-defined rates (1–8 fps) to distinguish moving targets and variables from static background stars.
4. **Sub-Pixel Image Differencing ($Epoch_2 - Epoch_1$):** Cancels static stellar emission ($|\Delta| \le 15$), revealing proper-motion targets as dipolar positive (amber/red) and negative (cyan) residuals, and variable stars as unipolar flux changes.
5. **102-Band SED Extraction & Molecular Diagnostic:** Visualizes synthesized and observed spectral energy distributions (SED) across detector arrays Arr 1 through Arr 6, identifying absorption bands for $H_2O$ (1.4 µm, 1.9 µm, 3.0 µm ice), $CH_4$ (1.66 µm, 2.2 µm, 3.3 µm), and $CO_2$ (4.26 µm).
6. **Cross-Catalog Verification (Gaia DR3 vs. CatWISE):** Flags high-proper-motion infrared sources lacking optical Gaia counterparts as prime candidates for sub-stellar brown dwarfs or undiscovered solar system bodies.

---

## 2. Repository Architecture & Directory Layout

```
SphereX/
├── .gitignore                      # Git ignore file (.env, .venv, caches)
├── LICENSE                         # MIT License (Pioneer Matrix Team 2026)
├── GEMINI.md                       # Comprehensive system architecture & developer guide
├── README.md                       # Hackathon & judge-ready repository documentation
├── config/
│   ├── targets.json                # 5 Official benchmark targets with astrometry & physics
│   └── cutouts/                    # Pre-cached JSON cutouts for instant mission-control demo
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

## 3. Astrometric & Photometric Mathematical Formulations

### Proper Motion Spherical Projection
Because celestial coordinates conform to spherical geometry, proper motion along Right Ascension must be scaled by the cosine of Declination:
$$\Delta \alpha = \frac{\mu_\alpha \cos(\delta)}{\cos(\delta)} \times \Delta t = \mu_\alpha \times \Delta t$$
$$\alpha_{new} = \alpha_0 + \frac{\mu_\alpha^* \cdot \Delta t}{\cos(\delta_0) \cdot 3.6 \times 10^6}$$
$$\delta_{new} = \delta_0 + \frac{\mu_\delta \cdot \Delta t}{3.6 \times 10^6}$$
Where $\mu_\alpha^* = \mu_\alpha \cos(\delta)$ in mas/yr, $\mu_\delta$ in mas/yr, and coordinates are in degrees.

### Image Differencing Residuals
$$D(x, y) = I_{\text{epoch } 2}(x, y) - I_{\text{epoch } 1}(x, y)$$
- **Static Background Stars:** $|D(x, y)| \le 15 \implies$ Dark/Transparent background.
- **New Position / Brightened ($+ \Delta$):** $D(x, y) > 15 \implies$ Amber / Red glow ($[255, 100, 30]$).
- **Previous Position / Dimmed ($- \Delta$):** $D(x, y) < -15 \implies$ Cyan glow ($[0, 220, 255]$).
- **Moving Object Signature:** Classic dipole with co-aligned positive and negative lobes along the proper motion vector.

---

## 4. Key CLI Commands & Workflows

### Virtual Environment & Verification
```powershell
# Run the test pipeline
python scripts/test_pipeline.py

# Pre-cache benchmark cutouts or test IRSA scraper
python scripts/fetch_all_targets.py
```

### Running the Full Stack
```powershell
# 1. Start the FastAPI backend server (Port 8000)
uvicorn scripts.server:app --port 8000

# 2. Serve the mission-control frontend (Port 8080)
python -m http.server 8080 --directory app
```

### Accessing the Dashboard:
Open `http://localhost:8080` in your web browser.
- Select any preset chip (e.g., Barnard's Star, WISE 0855-0714).
- Switch between **Single Epoch**, **Blink Comparator**, and **Difference Imaging**.
- Click anywhere on the canvas to inspect celestial targets and review the Object Identification HUD.

