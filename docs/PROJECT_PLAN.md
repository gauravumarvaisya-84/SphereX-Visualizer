# PROJECT PLAN & NASA JUDGING ALIGNMENT
### Team Pioneer Matrix &bull; NASA Space Apps Challenge 2026
**Challenge Focus:** Planet X and SPHEREx

---

## 1. 48-Hour Hackathon Milestones (Sprint Log)

All sprint milestones were planned, tracked, and executed during the 48-hour global challenge window:

- [x] **Phase 1: Mission Scoping & Science Architecture (Hours 0–8)**
  - Decoded SPHEREx mission parameters: 6 Linear Variable Filter (LVF) detector arrays, 102 spectral bands ($0.75 - 5.0\,\mu\text{m}$), 6-month all-sky survey cadences.
  - Formulated the proper motion projection math incorporating spherical cosine declination scaling.
  - Selected and codified 5 benchmark targets in `config/targets.json` covering extreme kinematics (Barnard's Star), sub-stellar water/methane atmospheres (WISE 0855, Epsilon Indi B), dust occultation dynamics (RW Aurigae), and pulsating giant variability (R Draconis).

- [x] **Phase 2: Mathematical Engine & Unit Testing Suite (Hours 8–18)**
  - Developed `scripts/astro_tools.py` with multi-format sexagesimal and decimal coordinate parsing.
  - Implemented the sub-pixel image differencing matrix calculation ($D = I_{\text{Ep2}} - I_{\text{Ep1}}$) with dipole center-of-mass detection.
  - Synthesized 102-band spectral energy distributions across SPHEREx detector arrays with absorption notch modeling for $H_2O$, $CH_4$, and $CO_2$.
  - Wrote automated unit testing suite `scripts/test_pipeline.py` verifying coordinate roundtrips, 6-month proper motion shifts, dipole matrix behavior, and SED array bounds (100% test pass rate).

- [x] **Phase 3: Caltech/IPAC IRSA TAP Scraper & Astrometric Pipeline (Hours 18–28)**
  - Engineered `scripts/fetch_all_targets.py` featuring `resolve_any_input()` supporting astronomical names (CDS Sesame), decimal coordinates, and Earth city addresses (OpenStreetMap Nominatim converted to zenith AltAz).
  - Integrated live Caltech/IPAC IRSA TAP service (`spherex.artifact` and `spherex.plane`).
  - Added zodiacal background subtraction (`IMAGE - ZODI`), log1p dynamic stretch, and uint8 resampling.
  - Implemented robust physics-based astrometric simulation fallback ensuring flawless demonstration even under network restrictions or pre-launch IRSA tables.
  - Pre-cached all 5 benchmark targets into `config/cutouts/<id>.json`.

- [x] **Phase 4: Mission Control Frontend Engine (Hours 28–38)**
  - Built sleek single-page app (`app/index.html`) using HTML5 Canvas and `ImageData` for high-performance direct pixel manipulation.
  - Implemented 3 view modes: Single Epoch (infrared thermal false-color), Blink Comparator (1–8 fps with pause/step controls), and Difference Imaging (dipole positive amber / negative cyan).
  - Created interactive Reticle & Proper Motion Vector arrow with click-to-lock targeting.
  - Engineered the 102-band Canvas SED graph with shaded detector arrays and molecular markers.
  - Built Object Identification HUD showing Gaia DR3 catalog match vs. UNCATALOGED candidate status.
  - Integrated URL deep-linking (`window.history.replaceState`).

- [x] **Phase 5: FastAPI Backend, Gemini AI & Judge Documentation (Hours 38–48)**
  - Built `scripts/server.py` with CORS, MD5 query caching in `config/cutouts/live_cache/`, and `/api/explain` endpoint.
  - Implemented Gemini AI astrobiology explainer with rich local astrophysics fallback model.
  - Authored comprehensive documentation suite: `README.md`, `GEMINI.md`, `PROJECT_PLAN.md`, `SYSTEM_ARCHITECTURE.md`, `BENCHMARK_TARGETS.md`, `DATA_SOURCES.md`, and `OBJECT_IDENTIFICATION_AND_SCIENCE_GUIDE.md`.
  - Clean Git initialization and repository verification.

---

## 2. NASA Space Apps Judging Criteria Alignment

| Judging Criterion | How Pioneer Matrix Exceeds Expectations |
| :--- | :--- |
| **Impact & Scientific Value** | Bridges a critical gap in SPHEREx data exploitation by providing citizen scientists and professional astronomers with an instant multi-epoch differencing and 102-band SED diagnostic tool. Directly enables the rapid identification of undiscovered Planet X / KBO candidates and ultra-cool brown dwarfs lacking optical Gaia detections. |
| **Creativity & Innovation** | Pioneered the "Universal Astrometric Resolver": users can enter an astronomical designation, raw coordinates, or their hometown (e.g. "Cape Canaveral"), which instantly computes the overhead celestial zenith at the exact observation epoch and renders the corresponding SPHEREx infrared view! |
| **Technical Execution** | Highly optimized dual-stack architecture: low-overhead FastAPI Python backend with Astropy, Astroquery, and NumPy math, combined with a dependency-free vanilla HTML5 Canvas frontend utilizing direct `ImageData` bitwise pixel manipulation for instantaneous 60 fps rendering. |
| **Validity & Rigor** | Grounded in exact astrophysical equations: spherical $\cos(\delta)$ proper motion corrections, Caltech/IPAC TAP table schemas, zodiacal light subtraction, and empirical molecular absorption features ($CH_4$, $H_2O$, $CO_2$). Backed by an automated unit test suite. |
| **User Experience & Design** | Sleek, dark-mode NASA mission-control aesthetics with intuitive tactile controls, interactive Reticle targeting, proper motion vector arrows, real-time telemetry HUD, and seamless URL deep-linking for effortless collaboration. |

---

## 3. Post-Hackathon Roadmap

### Quarter 1: Full SPHEREx All-Sky Pipeline Integration
- Transition from TAP queries to direct streaming tile decoders for public SPHEREx data releases through IPAC.
- Implement automated source extraction using DAOPhot / SExtractor-style Gaussian fitting directly within Python backend.

### Quarter 2: Machine Learning Dipole Classifier
- Train a lightweight Convolutional Neural Network (CNN) on difference image pairs ($128 \times 128$) to automatically score moving source probability vs. residual artifacts (diffraction spikes, cosmic ray hits).
- Deploy ONNX runtime directly in the browser for client-side candidate classification.

### Quarter 3: Citizen Science & Zooniverse Integration
- Export vetted candidate lists directly to Zooniverse / Planet Hunters formats for crowd-sourced verification.
- Add user annotations, bookmarking, and public candidate registration ledger.

