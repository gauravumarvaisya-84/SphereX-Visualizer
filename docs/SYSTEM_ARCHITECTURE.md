# SYSTEM ARCHITECTURE & MATHEMATICAL ENGINE
### Team Pioneer Matrix &bull; NASA Space Apps Challenge 2026
**Challenge Focus:** Planet X and SPHEREx

---

## 1. End-to-End Data Flow

The **SPHEREx Visualizer & Object Identifier** employs a decoupled, high-performance architecture separating compute-intensive astrometric ingestion from zero-latency browser rendering:

```
[User Input Query]
       │
       ▼
[fetch_all_targets.py / resolve_any_input()]
 ├── Format A: Decimal / Sexagesimal Coordinates ──> Direct Angle Parsing
 ├── Format B: Astronomical Designation ───────────> CDS Sesame / SIMBAD
 └── Format C: Earth City / Address ───────────────> OSM Nominatim -> AltAz Zenith Transform
       │
       ▼
[scrape_spherex_target()]
 ├── 1. Caltech/IPAC IRSA TAP Query (`spherex.artifact` JOIN `spherex.plane`)
 ├── 2. Temporal Epoch Filtering (Δt >= 150 days)
 ├── 3. Zodiacal Background Subtraction (IMAGE - ZODI)
 ├── 4. Log1p Dynamic Range Compression & uint8 Normalization
 └── 5. Resampling to 128x128 Matrix & MD5 Live Cache Write
       │
       ▼
[FastAPI REST API / JSON Response]
 ├── /api/sky (Cached cutouts & epochs)
 ├── /api/spectrum (102-band SED array)
 └── /api/explain (Gemini AI narrative)
       │
       ▼
[HTML5 Canvas Mission-Control Frontend]
 ├── Viewport Engine: Single Epoch | Blink (1-8 fps) | Difference Matrix
 ├── Interactive Overlay: Reticle & Proper Motion Vectors
 ├── 102-Band SED Plotter: 6 Arrays + Molecular Markers
 └── Object Identification HUD: Gaia DR3 vs. UNCATALOGED Candidate
```

---

## 2. SPHEREx 6 Detector Arrays & Spectral Specifications

SPHEREx utilizes an innovative spectrophotometric design consisting of six Linear Variable Filters (LVF) mounted directly over HgCdTe and H2RG detector arrays:

| Detector Array | Wavelength Range ($\mu\text{m}$) | Spectral Resolution ($R = \lambda / \Delta\lambda$) | Science Target & Diagnostic Features | Shading Color in UI |
| :--- | :--- | :--- | :--- | :--- |
| **Array 1** | $0.75 - 1.11\,\mu\text{m}$ | $R \approx 41$ | Optical-NIR transition, TiO/VO bands in M-dwarfs, Solar continuum | `rgba(0, 180, 255, 0.08)` |
| **Array 2** | $1.11 - 1.64\,\mu\text{m}$ | $R \approx 41$ | $H_2O$ vapor ($1.15\,\mu\text{m}, 1.40\,\mu\text{m}$), $H^-$ opacity minimum peak ($1.6\,\mu\text{m}$) | `rgba(0, 229, 255, 0.12)` |
| **Array 3** | $1.64 - 2.42\,\mu\text{m}$ | $R \approx 41$ | $CH_4$ overtone ($1.66\,\mu\text{m}, 2.20\,\mu\text{m}$), $H_2O$ ($1.9\,\mu\text{m}$), CO ($2.32\,\mu\text{m}$) | `rgba(0, 255, 136, 0.08)` |
| **Array 4** | $2.42 - 3.82\,\mu\text{m}$ | $R \approx 35$ | $H_2O$ Ice Mantle ($3.05\,\mu\text{m}$), Fundamental $CH_4$ ($\nu_3$ at $3.32\,\mu\text{m}$) | `rgba(255, 215, 0, 0.10)` |
| **Array 5** | $3.82 - 4.42\,\mu\text{m}$ | $R \approx 110$ | $CO_2$ fundamental band ($4.26\,\mu\text{m}$ in circumstellar/planetary ices) | `rgba(255, 140, 0, 0.12)` |
| **Array 6** | $4.42 - 5.00\,\mu\text{m}$ | $R \approx 130$ | Mid-IR Methane Opacity Window ($4.65\,\mu\text{m}$ emission), Fundamental CO ($4.67\,\mu\text{m}$) | `rgba(255, 51, 102, 0.09)` |

---

## 3. Mathematical Foundations

### 3.1 Astrometric Proper Motion Projection
Because celestial spherical coordinates converge at the celestial poles, proper motion along Right Ascension must be scaled by the cosine of Declination:
$$\mu_\alpha^* = \mu_\alpha \cos(\delta)$$
$$\Delta \alpha = \frac{\mu_\alpha^* \cdot \Delta t}{\cos(\delta_0) \cdot 3.6 \times 10^6} \quad [\text{degrees}]$$
$$\Delta \delta = \frac{\mu_\delta \cdot \Delta t}{3.6 \times 10^6} \quad [\text{degrees}]$$
$$\alpha_{\text{projected}} = (\alpha_0 + \Delta \alpha) \pmod{360^{\circ}}$$
$$\delta_{\text{projected}} = \text{clip}(\delta_0 + \Delta \delta, -90^{\circ}, +90^{\circ})$$
Total transverse angular displacement on the sky:
$$\Delta \theta = \frac{\sqrt{(\mu_\alpha^*)^2 + (\mu_\delta)^2} \times |\Delta t|}{1000} \quad [\text{arcseconds}]$$

### 3.2 Sub-Pixel Image Differencing & Dipole Formation
Given two registered images $I_{\text{Ep1}}(x, y)$ and $I_{\text{Ep2}}(x, y)$:
$$D(x, y) = I_{\text{Ep2}}(x, y) - I_{\text{Ep1}}(x, y)$$

**Residual Color Mapping:**
- **Static Background Emission:**
  $$|D(x, y)| \le 15 \implies [R, G, B] = [\text{faint noise background}]$$
- **Positive Residual ($+ \Delta$ / New Position or Brightened):**
  $$D(x, y) > 15 \implies [R, G, B] = \left[200 + 55 \cdot \sigma, \, 80 + 90 \cdot \sigma, \, 20 \cdot (1 - \sigma)\right] \quad (\text{Amber/Electric Red})$$
  where $\sigma = \min(1.0, (D - 15) / 140)$.
- **Negative Residual ($- \Delta$ / Prior Position or Dimmed):**
  $$D(x, y) < -15 \implies [R, G, B] = \left[10 \cdot (1 - \sigma), \, 180 + 75 \cdot \sigma, \, 220 + 35 \cdot \sigma\right] \quad (\text{Electric Cyan})$$
  where $\sigma = \min(1.0, (-D - 15) / 140)$.

**Dipole Center-of-Mass Detection:**
$$\vec{C}_{\text{pos}} = \frac{\sum x_i D(x_i, y_i)}{\sum D(x_i, y_i)} \quad \text{for } D > 15$$
$$\vec{C}_{\text{neg}} = \frac{\sum x_i |D(x_i, y_i)|}{\sum |D(x_i, y_i)|} \quad \text{for } D < -15$$
A moving object is confirmed when both positive and negative clusters exist with separation matching the projected astrometric shift vector.

---

## 4. URL Deep-Linking Schema

The state of the visualizer is synchronized in real time with the browser URL using HTML5 `window.history.replaceState`:

`http://localhost:8080/?target=<id>&ra=<deg>&dec=<deg>&fov=<arcmin>&mode=<mode>`

### Parameters:
- `target`: Target ID (e.g., `barnards_star`, `wise_0855`, `eps_indi_b`, `rw_aurigae`, `r_draconis`, or custom query string).
- `ra`: Decimal Right Ascension in J2000 degrees (e.g., `269.4521`).
- `dec`: Decimal Declination in J2000 degrees (e.g., `4.6934`).
- `fov`: Field of view in arcminutes (integer from `4` to `30`).
- `mode`: Viewport display mode:
  - `single`: Single-epoch calibrated infrared frame.
  - `blink`: Multi-epoch cycling comparator (1–8 fps).
  - `diff`: Sub-pixel difference matrix ($Epoch_2 - Epoch_1$).
