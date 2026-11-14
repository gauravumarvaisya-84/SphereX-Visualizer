# OBJECT IDENTIFICATION & CITIZEN SCIENCE DISCOVERY GUIDE
### Team Pioneer Matrix &bull; NASA Space Apps Challenge 2026
**Challenge Focus:** Planet X and SPHEREx

---

## 1. Classification Decision Tree

Use this decision tree when analyzing candidate signals in the SPHEREx Difference Imaging and Blink Comparator modes:

```
                            [EXAMINE DIFFERENCE MATRIX]
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
      [Residual Detected (|Δ| > 15)]                   [Static Field (|Δ| <= 15)]
                 │                                               │
                 ▼                                               ▼
         Does residual have                              Static background star.
         both (+) and (-) lobes?                         Perfect cross-epoch
                 │                                       subtraction.
        ┌────────┴────────┐
        │                 │
      [YES]              [NO]
        │                 │
        ▼                 ▼
     [DIPOLE]       [UNIPOLAR RESIDUAL]
        │                 │
        │                 ├─► If (+) only in Ep2: Source Brightened (Flare, Nova, Mira cycle)
        │                 └─► If (-) only in Ep2: Source Faded (Occultation, Dust cloud)
        │
        ▼
   Check Gaia DR3 Optical Counterpart
        │
   ┌────┴──────────────────────────┐
   │                               │
[MATCHED]                     [NO MATCH]
   │                               │
   ▼                               ▼
Standard High Proper         POTENTIAL ULTRA-COOL BROWN DWARF
Motion Star (e.g. M-dwarf)   OR PLANET X / KBO CANDIDATE!
Check Proper Motion:         Inspect 102-Band SED:
• If μ > 1"/yr: Fast mover   • Strong CH4 (1.66, 2.2, 3.32 µm)
• If μ > 5"/yr: Barnard-type • H2O ice absorption at 3.05 µm
                             • Bright 4.65 µm opacity window
```

---

## 2. Citizen Science Discovery Workflow

### Step 1: Scan with Blink Comparator
1. Set the Blink Comparator rate between **2 and 4 fps**.
2. Look for sources that shift position relative to the static star background.
3. Note: true moving objects maintain consistent PSF shape across frames.

### Step 2: Confirm Dipole in Difference Mode
1. Switch to **Difference Imaging ($Epoch_2 - Epoch_1$)**.
2. Static stars cancel to dark background noise.
3. A real moving target will show an **amber/red peak** at its new position ($Epoch_2$) and a **cyan trough** at its old position ($Epoch_1$).
4. The line connecting the positive and negative lobes points exactly along the proper motion vector $\vec{\mu}$.

### Step 3: Check the Object Identification HUD
1. Click the dipole target on the canvas to lock the reticle.
2. Observe the **Catalog Match Banner**:
   - **CATALOG MATCH (Gaia DR3):** Already known star.
   - **NEW CANDIDATE (UNCATALOGED):** High priority candidate! No optical counterpart exists in Gaia DR3.

### Step 4: Validate Atmospheric Chemistry via 102-Band SED
1. Review the bottom **SPHEREx 102-Band Spectral Graph**.
2. Check for the diagnostic absorption features:
   - **Water Vapor ($H_2O$):** $1.40\,\mu\text{m}$ and $1.90\,\mu\text{m}$.
   - **Methane ($CH_4$):** $1.66\,\mu\text{m}$ ($2\nu_3$ overtone), $2.20\,\mu\text{m}$, and $3.32\,\mu\text{m}$ ($\nu_3$ fundamental).
   - **Water Ice Mantle:** $3.05\,\mu\text{m}$ broad notch (indicates $T_{\text{eff}} < 300\,\text{K}$).
   - **Mid-IR Opacity Peak:** Luminous emergence at $4.65\,\mu\text{m}$.

### Step 5: Generate AI Astrophysical Report
1. Click the **Generate Deep Science Report (Gemini AI)** button.
2. The AI astrobiologist will synthesize the astrometric kinematics, molecular profile, and planetary implications into a judge-ready scientific dossier.
