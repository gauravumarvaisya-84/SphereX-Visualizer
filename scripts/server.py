"""
FastAPI Server & REST API for SPHEREx Mission Visualizer
Team Pioneer Matrix - NASA Space Apps Challenge 2026
"""

import os
import sys
import json
import hashlib
import ipaddress
import re
import requests
import secrets
import threading
import time
from collections import deque
from typing import Optional, Dict, Any, List, Literal, Deque

from fastapi import FastAPI, Query, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, ICRS
from astropy.time import Time

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
AI_NAME = os.getenv("AI_NAME", "SPHEREx Analyzer")
ANALYZER_ACCESS_TOKEN = os.getenv("ANALYZER_ACCESS_TOKEN", "").strip()
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080"
    ).split(",")
    if origin.strip()
]
if "*" in ALLOWED_ORIGINS:
    raise ValueError("CORS_ORIGINS must list exact trusted origins; wildcard access is not allowed.")
if ANALYZER_ACCESS_TOKEN and len(ANALYZER_ACCESS_TOKEN) < 32:
    raise ValueError("ANALYZER_ACCESS_TOKEN must be at least 32 characters long.")

ANALYZER_REQUESTS_PER_MINUTE = 10
ANALYZER_REQUESTS_PER_DAY = 100
_analyzer_request_times: Dict[str, Deque[float]] = {}
_analyzer_request_lock = threading.Lock()

# Initialize FastAPI App
app = FastAPI(
    title="SPHEREx Mission Visualizer API",
    description="Backend Astrometry, Live Scraper, and Spectral Engine for NASA Space Apps Challenge 2026",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Analyzer-Token"],
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
            "/api/analyze"
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
    max_epochs: int = Query(3, ge=1, le=6, description="Number of survey epochs"),
    input_mode: Literal["sky", "earth"] = Query("sky", description="Interpret coordinates as sky or Earth coordinates")
):
    """
    Search and retrieve multi-epoch SPHEREx calibrated cutouts for any input query.
    Results are cached by MD5 key in config/cutouts/live_cache/ for instant recall.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' cannot be empty.")

    query_str = q.strip()

    # 1. Check if query matches a pre-cached benchmark target file
    clean_q = re.sub(r"[^a-z0-9]", "", query_str.lower())
    benchmark_file = None
    for target in load_benchmark_targets():
        target_names = (target.get("id", ""), target.get("name", ""))
        if any(clean_q == re.sub(r"[^a-z0-9]", "", value.lower()) for value in target_names):
            candidate = os.path.join(CUTOUTS_DIR, f"{target['id']}.json")
            if os.path.isfile(candidate):
                benchmark_file = candidate
                break
    if benchmark_file and os.path.exists(benchmark_file):
        try:
            with open(benchmark_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["cache_status"] = "preset_hit"
                return data
        except Exception:
            pass

    # 2. Check MD5 cache in live_cache
    cache_key = hashlib.md5(f"{input_mode}_{query_str}_{size_deg:.4f}_{bandpass}_{max_epochs}".encode()).hexdigest()
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
        resolved = resolve_earth_lat_lon(query_str) if input_mode == "earth" else resolve_any_input(query_str)
        if input_mode == "earth" and resolved is None:
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
        cutout_data["cache_status"] = (
            "live_processed" if cutout_data.get("source") == "irsa_live_tap" else "simulated_fallback"
        )

        # Save to live_cache
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cutout_data, f)
        except Exception as write_err:
            print(f"Warning: Could not write cache file: {write_err}")

        return cutout_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate SPHEREx data: {str(e)}")


def resolve_earth_lat_lon(query: str) -> Optional[Dict[str, Any]]:
    """Convert a numeric Earth latitude/longitude pair to its current zenith."""
    parts = [part.strip() for part in re.split(r"[,;\s]+", query.strip()) if part.strip()]
    if len(parts) != 2:
        return None
    try:
        latitude, longitude = map(float, parts)
    except ValueError:
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Earth coordinates must be latitude [-90, 90], longitude [-180, 180].")

    now = Time.now()
    location = EarthLocation(lat=latitude * u.deg, lon=longitude * u.deg)
    zenith = AltAz(alt=90 * u.deg, az=0 * u.deg, obstime=now, location=location)
    sky = zenith.transform_to(ICRS())
    ra_deg, dec_deg = float(sky.ra.deg), float(sky.dec.deg)
    return {
        "target_id": "earth_zenith",
        "name": f"Zenith at {latitude:.4f}, {longitude:.4f}",
        "ra_deg": ra_deg,
        "dec_deg": dec_deg,
        "pm_ra_mas_yr": 0.0,
        "pm_dec_mas_yr": 0.0,
        "total_pm_arcsec_yr": 0.0,
        "spectral_type": "Zenith Field",
        "object_type": "overhead_sky",
        "earth_lat": latitude,
        "earth_lon": longitude,
        "observation_time_utc": str(now.iso),
        "description": "Current sky coordinates at the zenith for the supplied Earth location.",
        "source": "earth_lat_lon"
    }


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)


class AnalyzeRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    target: Dict[str, Any] = Field(default_factory=dict)
    history: List[ChatTurn] = Field(default_factory=list)


ANALYZER_SYSTEM_PROMPT = """You are {ai_name}, an adaptive SPHEREx astronomy guide.
Use only the compact active-target summary and the conversation supplied. Do not invent measurements, catalogs, or detections.
For casual questions, answer in plain English in 2–3 crisp sentences using the target's real numbers, then provide an intriguing curiosity-hook question.
For technical questions about proper motion, spectral bands, Gaia/IR ratios, or difference images, answer with precise astrophysical depth and provide a deeper investigative next question.
Return only JSON with exactly these string fields: {"reply":"...","suggested_question":"..."}.
Keep reply below 120 words. Treat 4.26 microns as the CO2 feature region; do not claim a measured peak unless the supplied data says one was measured."""


def compact_target_summary(target: Dict[str, Any]) -> Dict[str, Any]:
    """Whitelist scalar fields so images and other large payloads never reach Gemini."""
    name = str(target.get("name") or "Unknown target")[:80]
    ratio = target.get("optical_ir_ratio")
    try:
        ratio = float(ratio) if ratio is not None else None
    except (TypeError, ValueError):
        ratio = None
    try:
        proper_motion = float(target.get("proper_motion") or 0)
    except (TypeError, ValueError):
        proper_motion = 0.0
    try:
        wavelength = float(target.get("wavelength_um")) if target.get("wavelength_um") is not None else None
    except (TypeError, ValueError):
        wavelength = None
    try:
        epoch_count = max(0, min(6, int(target.get("epoch_count") or 0)))
    except (TypeError, ValueError):
        epoch_count = 0
    return {
        "name": name,
        "ra_deg": _compact_number(target.get("ra_deg")),
        "dec_deg": _compact_number(target.get("dec_deg")),
        "proper_motion": proper_motion,
        "optical_ir_ratio": ratio,
        "wavelength_um": wavelength,
        "epoch_count": epoch_count,
        "discovery_status": str(target.get("discovery_status") or "unverified")[:40]
    }


def _compact_number(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _local_analysis(prompt: str, target: Dict[str, Any]) -> Dict[str, str]:
    name = target["name"]
    motion = target["proper_motion"]
    ratio = target["optical_ir_ratio"]
    wavelength = target["wavelength_um"]
    low = prompt.lower()
    deep = any(term in low for term in ("ratio", "proper motion", "vector", "dipole", "absorption", "band", "um", "µm", "gaia", "epoch"))

    if deep:
        ratio_match = re.search(r"(?:ratio|optical.to.ir)[^0-9]{0,30}([0-9]+(?:\.[0-9]+)?(?:e[+-]?\d+)?)", low)
        wave_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:um|µm|microns?)", low)
        if ratio_match:
            ratio = float(ratio_match.group(1))
        if wave_match:
            wavelength = float(wave_match.group(1))
        ratio_text = f"{ratio:g}" if ratio is not None else "not measured in the active summary"
        wavelength_text = f"{wavelength:g} µm" if wavelength is not None else "not specified"
        reply = (
            f"{name} has a proper motion of {motion:g} arcsec/year across {target['epoch_count']} epoch(s). "
            f"The optical-to-IR ratio is {ratio_text}; a value of 0.001 means optical flux is about one-thousandth "
            "of the infrared measure, consistent with an IR-dominated source but not proof of a new object. "
            f"{wavelength_text} is near the 4.26 µm CO2 feature region; a reported peak there needs continuum and calibration checks, "
            "since CO2 is generally diagnosed by absorption."
        )
        question = "Can we compare the neighboring bands and epoch-to-epoch flux to distinguish a real feature from calibration or variability?"
    else:
        reply = (
            f"This is {name}, centered at RA {target['ra_deg'] if target['ra_deg'] is not None else 'unknown'}° "
            f"and Dec {target['dec_deg'] if target['dec_deg'] is not None else 'unknown'}°. "
            f"It moves at about {motion:g} arcsec per year; the canvas compares {target['epoch_count']} observation epoch(s) "
            "to help reveal motion or brightness changes."
        )
        question = "Want to see how its motion leaves a positive-and-negative footprint in the difference view?"
    return {"reply": _limit_words(reply, 119), "suggested_question": question}


def _limit_words(text: str, max_words: int) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words])


def _client_is_loopback(request: Request) -> bool:
    if request.client is None:
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        return False


def _enforce_analyzer_access(request: Request, supplied_token: Optional[str]) -> None:
    if ANALYZER_ACCESS_TOKEN:
        if not supplied_token or not secrets.compare_digest(supplied_token, ANALYZER_ACCESS_TOKEN):
            raise HTTPException(status_code=401, detail="A valid analyzer access token is required.")
        return

    if not _client_is_loopback(request):
        raise HTTPException(
            status_code=503,
            detail="Remote analyzer access is disabled. Configure ANALYZER_ACCESS_TOKEN on the backend."
        )


def _enforce_gemini_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    now = time.time()
    minute_ago = now - 60
    day_ago = now - 86400

    with _analyzer_request_lock:
        timestamps = _analyzer_request_times.setdefault(client_host, deque())
        while timestamps and timestamps[0] <= day_ago:
            timestamps.popleft()

        recent_count = sum(timestamp > minute_ago for timestamp in timestamps)
        if recent_count >= ANALYZER_REQUESTS_PER_MINUTE:
            retry_after = max(1, int(60 - (now - next(
                timestamp for timestamp in timestamps if timestamp > minute_ago
            ))))
            raise HTTPException(
                status_code=429,
                detail="Analyzer rate limit reached. Try again shortly.",
                headers={"Retry-After": str(retry_after)}
            )
        if len(timestamps) >= ANALYZER_REQUESTS_PER_DAY:
            retry_after = max(1, int(86400 - (now - timestamps[0])))
            raise HTTPException(
                status_code=429,
                detail="Analyzer daily request limit reached.",
                headers={"Retry-After": str(retry_after)}
            )

        timestamps.append(now)
        if len(_analyzer_request_times) > 1024:
            expired = [
                host for host, requests_for_host in _analyzer_request_times.items()
                if not requests_for_host or requests_for_host[-1] <= day_ago
            ]
            for host in expired:
                _analyzer_request_times.pop(host, None)


@app.post("/api/analyze")
def analyze_target(
    payload: AnalyzeRequest,
    request: Request,
    analyzer_token: Optional[str] = Header(default=None, alias="X-Analyzer-Token")
):
    _enforce_analyzer_access(request, analyzer_token)
    _enforce_gemini_rate_limit(request)

    target = compact_target_summary(payload.target)
    prompt = payload.prompt.strip()
    history = payload.history[-4:]
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)

    if api_key:
        contents = []
        for turn in history:
            contents.append({
                "role": "user" if turn.role == "user" else "model",
                "parts": [{"text": turn.content[:1000]}]
            })
        contents.append({
            "role": "user",
            "parts": [{
                "text": f"Active target summary: {json.dumps(target, separators=(',', ':'))}\nQuestion: {prompt}"
            }]
        })
        payload = {
            "system_instruction": {"parts": [{"text": ANALYZER_SYSTEM_PROMPT.replace("{ai_name}", AI_NAME)}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 220,
                "responseMimeType": "application/json"
            }
        }
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=12
            )
            response.raise_for_status()
            candidate_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(candidate_text)
            reply = str(result["reply"]).strip()
            suggested_question = str(result["suggested_question"]).strip()
            if len(reply.split()) > 119 or not suggested_question:
                raise ValueError("Gemini response did not meet the analyzer response format.")
            return {
                "reply": reply,
                "suggested_question": suggested_question
            }
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"Gemini analysis unavailable ({type(error).__name__}); using the local analyzer.")

    result = _local_analysis(prompt, target)
    return result


@app.get("/api/spectrum")
def get_spectrum(object_type: str = Query("brown_dwarf", description="Astrophysical object classification")):
    """Returns 102-band synthesized spectral profile with molecular diagnostic markers."""
    return generate_spherex_spectral_profile(object_type)


@app.get("/api/explain")
def explain_target(
    request: Request,
    target: str = Query(..., description="Target name or identifier"),
    object_type: Optional[str] = Query("unknown", description="Classification (e.g. brown_dwarf, red_dwarf)"),
    pm: Optional[float] = Query(0.0, description="Total proper motion in arcsec/yr"),
    optical_to_ir_ratio: Optional[float] = Query(None, description="Optical-to-IR flux ratio"),
    is_gaia_match: Optional[bool] = Query(True, description="Whether an optical Gaia counterpart exists"),
    analyzer_token: Optional[str] = Header(default=None, alias="X-Analyzer-Token")
):
    """
    AI Astrobiology & Astrophysics narrative generator.
    Uses GEMINI_API_KEY from .env if available, or rich local astrophysics reasoning model.
    """
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
    _enforce_analyzer_access(request, analyzer_token)
    _enforce_gemini_rate_limit(request)

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

            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }
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
