"""
FastAPI Server & REST API for SphereX Visualizer
Team Pioneer Matrix - NASA Space Apps Challenge 2026
"""

import os
import sys
import json
import hashlib
import requests
from typing import Optional, Dict, Any

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure scripts directory in path
sys.path.insert(0, os.path.dirname(__file__))

from astro_tools import (
    parse_ra_to_deg,
    parse_dec_to_deg,
    deg_to_sexagesimal,
    project_proper_motion,
    compute_image_difference,
    generate_spherex_spectral_profile
)
from fetch_all_targets import (
    resolve_any_input,
    scrape_spherex_target,
    load_benchmark_targets
)

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CUTOUTS_DIR = os.path.join(CONFIG_DIR, "cutouts")
LIVE_CACHE_DIR = os.path.join(CUTOUTS_DIR, "live_cache")
os.makedirs(LIVE_CACHE_DIR, exist_ok=True)

# Load environment variables from .env if present
ENV_PATH = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Initialize FastAPI App
app = FastAPI(
    title="SphereX Visualizer & Object Identifier API",
    description="Backend Astrometry, Live Scraper, and Spectral Engine for NASA Space Apps Challenge 2026",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "mission": "SPHEREx Visualizer & Object Identifier",
        "team": "Pioneer Matrix - NASA Space Apps Challenge 2026",
        "status": "operational",
        "endpoints": [
            "/api/sky?q=<query>&size_deg=0.05&bandpass=SPHEREx-D2",
            "/api/targets",
            "/api/spectrum?object_type=<type>",
            "/api/explain?target=<name>&object_type=<type>"
        ]
    }


@app.get("/api/targets")
def get_benchmark_targets():
    """Returns the 5 official benchmark targets from config/targets.json."""
    targets = load_benchmark_targets()
    return {"benchmark_targets": targets}


@app.get("/api/sky")
def get_sky_cutout(
    q: str = Query(..., description="Target name, RA/Dec coordinates, or Earth city/address"),
    size_deg: float = Query(0.05, ge=0.01, le=0.5, description="Field of view size in degrees"),
    bandpass: str = Query("SPHEREx-D2", description="SPHEREx bandpass (SPHEREx-D1 to D6)"),
    max_epochs: int = Query(3, ge=1, le=6, description="Number of survey epochs")
):
    """
    Search and retrieve multi-epoch SPHEREx calibrated cutouts for any input query.
    Results are cached by MD5 key in config/cutouts/live_cache/ for instant recall.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' cannot be empty.")

    query_str = q.strip()

    # 1. Check if query matches a pre-cached benchmark target file
    clean_q = query_str.lower().replace("-", "_").replace(" ", "_")
    benchmark_file = os.path.join(CUTOUTS_DIR, f"{clean_q}.json")
    if os.path.exists(benchmark_file):
        try:
            with open(benchmark_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["cache_status"] = "preset_hit"
                return data
        except Exception:
            pass

    # 2. Check MD5 cache in live_cache
    cache_key = hashlib.md5(f"{query_str}_{size_deg:.4f}_{bandpass}_{max_epochs}".encode()).hexdigest()
    cache_file = os.path.join(LIVE_CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                cached_data["cache_status"] = "cache_hit"
                return cached_data
        except Exception:
            pass

    # 3. Resolve target coordinates from input
    try:
        resolved = resolve_any_input(query_str)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Target resolution error: {str(e)}")

    # 4. Scrape or synthesize multi-epoch cutouts
    try:
        cutout_data = scrape_spherex_target(
            coord=resolved,
            size_deg=size_deg,
            bandpass=bandpass,
            max_epochs=max_epochs,
            grid_size=128
        )
        cutout_data["cache_status"] = "live_processed"

        # Save to live_cache
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cutout_data, f)
        except Exception as write_err:
            print(f"Warning: Could not write cache file: {write_err}")

        return cutout_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate SPHEREx data: {str(e)}")


@app.get("/api/spectrum")
def get_spectrum(object_type: str = Query("brown_dwarf", description="Astrophysical object classification")):
    """Returns 102-band synthesized spectral profile with molecular diagnostic markers."""
    return generate_spherex_spectral_profile(object_type)


@app.get("/api/explain")
def explain_target(
    target: str = Query(..., description="Target name or identifier"),
    object_type: Optional[str] = Query("unknown", description="Classification (e.g. brown_dwarf, red_dwarf)"),
    pm: Optional[float] = Query(0.0, description="Total proper motion in arcsec/yr"),
    optical_to_ir_ratio: Optional[float] = Query(None, description="Optical-to-IR flux ratio"),
    is_gaia_match: Optional[bool] = Query(True, description="Whether an optical Gaia counterpart exists")
):
    """
    AI Astrobiology & Astrophysics narrative generator.
    Uses GEMINI_API_KEY from .env if available, or rich local astrophysics reasoning model.
    """
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)

    # 1. Attempt Google Gemini API if API key is present
    if api_key:
        try:
            prompt = (
                f"You are the senior astrophysicist for Team Pioneer Matrix in the NASA Space Apps Challenge 2026. "
                f"Analyze this celestial object observed by the SPHEREx satellite mission:\n"
                f"- Name/ID: {target}\n"
                f"- Object Classification: {object_type}\n"
                f"- Proper Motion: {pm:.3f} arcsec/year\n"
                f"- Gaia Optical Counterpart: {'Yes (Catalog Match)' if is_gaia_match else 'None (UNCATALOGED / Extreme IR Candidate)'}\n"
                f"- Optical-to-IR flux ratio: {optical_to_ir_ratio if optical_to_ir_ratio is not None else 'High IR excess'}\n\n"
                f"Provide a concise, 3-paragraph scientific breakdown covering:\n"
                f"1. Astrometric significance (motion and cross-epoch dipole behavior).\n"
                f"2. Infrared spectral characteristics across SPHEREx's 102 bands (mention H2O, CH4, or CO features).\n"
                f"3. Science implication for the search for Planet X, brown dwarfs, or stellar evolution."
            )

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600}
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                res_data = resp.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "source": "gemini_api",
                    "model": "gemini-2.5-flash",
                    "explanation": text.strip()
                }
        except Exception as e:
            print(f"Gemini API request failed ({e}), falling back to local science engine.")

    # 2. High-fidelity Astrophysics Knowledge Engine Fallback
    target_clean = target.lower()
    norm_type = (object_type or "unknown").lower()

    if not is_gaia_match or "wise" in target_clean or "brown" in norm_type or pm > 5.0:
        headline = "Sub-Stellar Brown Dwarf / Planet X Candidate"
        astrometry_desc = (
            f"The target demonstrates an extreme proper motion of {pm:.2f}\"/yr without an optical Gaia DR3 counterpart. "
            "In SPHEREx multi-epoch difference imaging (Epoch 2 - Epoch 1), this source produces a textbook dipolar signature "
            "composed of an amber positive flux peak adjacent to a cyan negative trough."
        )
        spec_desc = (
            "Spectral energy distribution across SPHEREx's 102 bands (0.75–5.0 µm) reveals massive methane (CH4) absorption troughs "
            "at 1.66 µm, 2.2 µm, and 3.32 µm, coupled with deep atmospheric water-vapor bands at 1.4 µm and 1.9 µm. "
            "The distinct emission peak at 4.65 µm confirms low atmospheric opacity in the mid-infrared window, characteristic of "
            "ultra-cool sub-stellar atmospheres below 500 K."
        )
        science_desc = (
            "Because this source is completely extinguished in optical surveys (G > 21 mag) but luminous in SPHEREx Detector Arrays 4–6, "
            "it represents a prime candidate for a nearby sub-stellar neighbor or high-albedo outer Solar System body."
        )
    elif "barnard" in target_clean or "red_dwarf" in norm_type:
        headline = "High Proper-Motion M-Dwarf Benchmark (Barnard's Star Class)"
        astrometry_desc = (
            f"With a staggering proper motion of {pm:.2f}\"/yr, this high-velocity stellar neighbor exhibits a 5.18\" displacement "
            "between consecutive 6-month SPHEREx survey epochs, shifting by ~3.7 pixels across the 128x128 grid."
        )
        spec_desc = (
            "Its SED reflects a 3,130 K photospheric blackbody modulated by broad titanium oxide (TiO) and vanadium oxide (VO) "
            "absorption bands in Arrays 1–2 (0.75–1.6 µm), and prominent carbon monoxide (CO) overtone bandheads near 2.32 µm."
        )
        science_desc = (
            "High-contrast astrometric differencing on this benchmark proves the capability of the SPHEREx all-sky survey to detect "
            "rapid transverse kinematic motions across the solar neighborhood."
        )
    elif "rw_aurigae" in target_clean or "t_tauri" in norm_type:
        headline = "Circumstellar Dust Obscuration in Young Stellar Object (RW Aurigae)"
        astrometry_desc = (
            f"The object maintains stationary astrometry ({pm:.3f}\"/yr) but displays prominent single-epoch unipolar residuals "
            "in difference imaging, indicative of dramatic multi-magnitude occultation events."
        )
        spec_desc = (
            "The 102-band spectrum exhibits a pronounced warm dust excess spanning SPHEREx Arrays 3–6 (2.0–5.0 µm), accompanied by "
            "ice-mantle absorption bands at 3.05 µm (H2O ice) and 4.26 µm (CO2 ice) within the protoplanetary disk."
        )
        science_desc = (
            "SPHEREx's bi-annual sky cadences enable continuous photometric monitoring of protoplanetary dust dynamics, shedding light "
            "on tidal disruptions and planet-forming circumstellar environments."
        )
    elif "r_draconis" in target_clean or "mira" in norm_type:
        headline = "Long-Period Mira Pulsating Variable (R Draconis)"
        astrometry_desc = (
            f"Displaying negligible proper motion ({pm:.3f}\"/yr), the source undergoes enormous periodic flux swings (~245-day cycle) "
            "between high and low pulsation states across successive SPHEREx sky scans."
        )
        spec_desc = (
            "The NIR spectrum is dominated by cool giant molecular envelopes with severe water vapor absorption (1.4 and 1.9 µm), "
            "first-overtone CO absorption at 2.3 µm, and fundamental CO vibrational features at 4.65 µm."
        )
        science_desc = (
            "Tracking Mira variables across SPHEREx's 102 channels provides critical calibration for cosmic distance scales and stellar "
            "mass-loss return into the interstellar medium."
        )
    else:
        headline = f"Astronomical Analysis: {target}"
        astrometry_desc = f"Target exhibits measured proper motion of {pm:.3f}\"/yr at J2000 coordinates."
        spec_desc = "Continuum flux across SPHEREx 102 bands (0.75–5.0 µm) shows standard stellar photospheric absorption characteristics."
        science_desc = "Calibrated against Gaia DR3 astrometric frame and CatWISE infrared photometric standards."

    full_narrative = f"### {headline}\n\n**1. Astrometric Kinematics:**\n{astrometry_desc}\n\n**2. Molecular & Spectral Signatures:**\n{spec_desc}\n\n**3. Mission Impact & Planet X Search:**\n{science_desc}"

    return {
        "source": "pioneer_matrix_astrophysics_engine",
        "headline": headline,
        "explanation": full_narrative
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
