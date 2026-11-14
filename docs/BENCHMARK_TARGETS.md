# BENCHMARK TARGETS & ASTROPHYSICAL CALIBRATION
### Team Pioneer Matrix &bull; NASA Space Apps Challenge 2026
**Challenge Focus:** Planet X and SPHEREx

---

## 1. Overview of the Benchmark Suite

To validate the SPHEREx Visualizer & Object Identifier across the diverse range of astronomical phenomena targeted by the SPHEREx mission, Team Pioneer Matrix selected and codified 5 official benchmark targets. These targets span extreme astrometric proper motion, sub-stellar planetary atmospheres, circumstellar dust occultations, and high-amplitude stellar pulsations.

```
+-----------------------------------------------------------------------------------------+
|                               BENCHMARK TARGET SPECTRUM                                 |
+-----------------------------------------------------------------------------------------+
| High Proper Motion Movers:        | Barnard's Star (10.36"/yr), WISE 0855 (8.16"/yr)    |
| Sub-Stellar Brown Dwarfs:         | WISE 0855 (Y2, ~250 K), Epsilon Indi B (T1+T6)      |
| Variable & Circumstellar Systems: | RW Aurigae (T Tauri Dust), R Draconis (Mira 245d)   |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Benchmark Profiles

### Target 1: Barnard's Star (V2500 Ophiuchi)
- **Object Class:** High Proper-Motion M-Dwarf Main-Sequence Star
- **Spectral Type:** M4.0V
- **Coordinates (J2000):** $\alpha = 269.452083^{\circ}$ (`17h 57m 48.50s`), $\delta = +04.693389^{\circ}$ (`+04° 41′ 36.2″`)
- **Proper Motion:**
  - $\mu_\alpha^* = -801.55\,\text{mas/yr}$
  - $\mu_\delta = +10362.54\,\text{mas/yr}$
  - $\mu_{\text{total}} = 10.360''/\text{yr}$
- **Parallax / Distance:** $\varpi = 547.45\,\text{mas} \implies d = 1.829\,\text{pc}$ ($5.96\,\text{ly}$)
- **Effective Temperature:** $T_{\text{eff}} \approx 3,134\,\text{K}$
- **6-Month SPHEREx Shift:** $\Delta \theta = 5.180''$ ($\sim 3.7\,\text{pixels}$ on 128x128 grid)
- **Astrobiological & Mission Relevance:**
  Barnard's Star is the benchmark astrometric calibrator for SPHEREx. In difference imaging, it produces the most prominent dipole in the entire sky, proving the sensitivity of our sub-pixel registration and motion detection algorithms.

---

### Target 2: WISE J085510.83-071442.5 (WISE 0855-0714)
- **Object Class:** Sub-Stellar Ultra-Cool Y-Type Brown Dwarf
- **Spectral Type:** Y2
- **Coordinates (J2000):** $\alpha = 133.795129^{\circ}$ (`08h 55m 10.83s`), $\delta = -07.245147^{\circ}$ (`-07° 14′ 42.5″`)
- **Proper Motion:**
  - $\mu_\alpha^* = -8132.0\,\text{mas/yr}$
  - $\mu_\delta = +683.0\,\text{mas/yr}$
  - $\mu_{\text{total}} = 8.160''/\text{yr}$
- **Parallax / Distance:** $\varpi = 432.8\,\text{mas} \implies d = 2.31\,\text{pc}$ ($7.53\,\text{ly}$)
- **Effective Temperature:** $T_{\text{eff}} \approx 250\,\text{K}$ ($-23^{\circ}\text{C}$, below freezing)
- **6-Month SPHEREx Shift:** $\Delta \theta = 4.080''$ ($\sim 2.9\,\text{pixels}$)
- **Gaia DR3 Status:** **UNCATALOGED / NO DETECTION** ($G > 21.5\,\text{mag}$)
- **Spectral Signatures in SPHEREx:**
  Exhibits deep absorption bands of methane ($CH_4$) at $1.66\,\mu\text{m}$, $2.20\,\mu\text{m}$, and $3.32\,\mu\text{m}$, strong water vapor absorption ($1.4\,\mu\text{m}, 1.9\,\mu\text{m}$), and a distinctive $3.05\,\mu\text{m}$ water-ice cloud mantle. In Arrays 5–6 ($4.4 - 5.0\,\mu\text{m}$), it reveals a bright emission spike through the $4.65\,\mu\text{m}$ opacity window.
- **Planet X Analogy:**
  WISE 0855 is the primary astronomical analog for an undiscovered Planet X or free-floating outer solar system body: bright in near/mid-infrared, cold, methane-rich, and totally dark in optical catalogs.

---

### Target 3: Epsilon Indi B (HD 209100 BC)
- **Object Class:** Benchmark Binary Brown Dwarf System
- **Spectral Type:** T1V (primary) + T6V (secondary)
- **Coordinates (J2000):** $\alpha = 331.043792^{\circ}$ (`22h 04m 10.51s`), $\delta = -56.782694^{\circ}$ (`-56° 46′ 57.7″`)
- **Proper Motion:**
  - $\mu_\alpha^* = +3961.0\,\text{mas/yr}$
  - $\mu_\delta = -2538.0\,\text{mas/yr}$
  - $\mu_{\text{total}} = 4.704''/\text{yr}$
- **Parallax / Distance:** $\varpi = 274.8\,\text{mas} \implies d = 3.64\,\text{pc}$ ($11.87\,\text{ly}$)
- **Effective Temperature:** $T_{\text{eff}} \approx 1,280\,\text{K}$ (T1) and $940\,\text{K}$ (T6)
- **6-Month SPHEREx Shift:** $\Delta \theta = 2.352''$
- **Spectral Signatures in SPHEREx:**
  Classic transition spectrum from late-L to T-dwarf regime, demonstrating progressive methane absorption onset in Array 3 ($1.66\,\mu\text{m}$ and $2.2\,\mu\text{m}$) and CO depletion due to chemical disequilibrium in cool sub-stellar atmospheres.

---

### Target 4: RW Aurigae
- **Object Class:** Classical T Tauri Pre-Main-Sequence Binary
- **Spectral Type:** K3e + K5e
- **Coordinates (J2000):** $\alpha = 076.956417^{\circ}$ (`05h 07m 49.54s`), $\delta = +30.401417^{\circ}$ (`+30° 24′ 05.1″`)
- **Proper Motion:**
  - $\mu_\alpha^* = +1.2\,\text{mas/yr}$
  - $\mu_\delta = -21.4\,\text{mas/yr}$
  - $\mu_{\text{total}} = 0.021''/\text{yr}$ (stationary on SPHEREx grid)
- **Distance:** $d \approx 163\,\text{pc}$ ($531\,\text{ly}$)
- **6-Month SPHEREx Shift:** Negligible ($0.011''$)
- **Photometric Behavior:**
  Subject to prolonged multi-magnitude dimming events ($\Delta V \sim 3\,\text{mag}$) caused by tidal interactions pulling circumstellar dust streams across the line of sight.
- **Difference Imaging Signature:**
  Produces a prominent **unipolar residual** in difference imaging without a paired negative counterpart, diagnostic of pure flux variability in young protoplanetary disk systems.

---

### Target 5: R Draconis
- **Object Class:** Long-Period Asymptotic Giant Branch (AGB) Pulsating Variable
- **Spectral Type:** M5e–M9e III
- **Coordinates (J2000):** $\alpha = 248.167625^{\circ}$ (`16h 32m 40.23s`), $\delta = +66.755000^{\circ}$ (`+66° 45′ 18.0″`)
- **Proper Motion:**
  - $\mu_\alpha^* = -12.4\,\text{mas/yr}$
  - $\mu_\delta = +18.9\,\text{mas/yr}$
  - $\mu_{\text{total}} = 0.023''/\text{yr}$
- **Pulsation Period:** $P \approx 245.6\,\text{days}$
- **Distance:** $d \approx 644\,\text{pc}$ ($2,100\,\text{ly}$)
- **Difference Imaging Signature:**
  Because the SPHEREx survey cadence is $\sim 182.5\,\text{days}$ ($\approx 0.74 \times P$), R Draconis is sampled at alternating phases between maximum light and deep minimum. This produces alternating massive unipolar residuals across SPHEREx Arrays 1–4.

