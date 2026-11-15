"""
FastAPI Server & REST API for SPHEREx Mission Visualizer
Team Pioneer Matrix - NASA Space Apps Challenge 2026
"""

import os
import sys
import json
import hashlib
import tempfile
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

from fetch_all_targets import (
    resolve_any_input,
    scrape_spherex_target,
    parse_coordinate_input,
)

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CUTOUTS_DIR = os.path.join(CONFIG_DIR, "cutouts")
DEFAULT_LIVE_CACHE_DIR = os.path.join(CUTOUTS_DIR, "live_cache")
CACHE_SCHEMA_VERSION = 5
STALE_CACHE_SCHEMA_VERSIONS = {4, CACHE_SCHEMA_VERSION}
LIVE_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
SIMULATED_CACHE_TTL_SECONDS = 5 * 60

# Load environment variables from .env if present
ENV_PATH = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

# Use a mounted persistent directory in deployments whose application disk is
# ephemeral. Relative paths resolve from the project root.
_cache_dir_setting = os.getenv("SPHEREX_CACHE_DIR", DEFAULT_LIVE_CACHE_DIR)
LIVE_CACHE_DIR = (
    _cache_dir_setting if os.path.isabs(_cache_dir_setting)
    else os.path.join(BASE_DIR, _cache_dir_setting)
)
os.makedirs(LIVE_CACHE_DIR, exist_ok=True)

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

ANALYZER_REQUESTS_PER_MINUTE = 20
ANALYZER_REQUESTS_PER_DAY = 300
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
            "/api/sky?q=<query>&input_mode=sky|earth&size_deg=<degrees>&bandpass=<band>",
            "/api/analyze"
        ]
    }


@app.get("/api/benchmarks")
def get_benchmark_examples():
    """Serve the optional, collapsible curated examples from the project catalog."""
    catalog_path = os.path.join(CONFIG_DIR, "targets.json")
    try:
        with open(catalog_path, "r", encoding="utf-8") as source:
            catalog = json.load(source)
        examples = []
        for item in catalog.get("benchmark_targets", []):
            try:
                examples.append({
                    "name": str(item["name"]),
                    "ra_deg": float(item["ra_deg"]),
                    "dec_deg": float(item["dec_deg"]),
                    "description": str(item.get("description") or "Curated archive example."),
                    "spectral_type": item.get("spectral_type"),
                })
            except (KeyError, TypeError, ValueError):
                continue
        return {"examples": examples}
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=503, detail=f"Benchmark examples are unavailable: {type(error).__name__}.")


@app.get("/api/sky")
def get_sky_cutout(
    q: str = Query(..., description="Target name, RA/Dec coordinates, or Earth city/address"),
    size_deg: float = Query(0.05, ge=0.01, le=0.5, description="Field of view size in degrees"),
    bandpass: str = Query("ALL", description="One SPHEREx detector array or ALL for a multi-array spectral sample"),
    max_epochs: int = Query(3, ge=1, le=6, description="Number of survey epochs"),
    input_mode: Literal["sky", "earth"] = Query("sky", description="Interpret coordinates as sky or Earth coordinates"),
    refresh_archive: bool = Query(False, description="Bypass response cache and retry IRSA")
):
    """
    Search and retrieve multi-epoch SPHEREx calibrated cutouts for any input query.
    Results use versioned, validated cache entries. Live products stay cached for a week;
    simulated fallbacks expire quickly so they cannot hide a later archive result.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query 'q' cannot be empty.")
    if bandpass not in {"ALL", *(f"SPHEREx-D{i}" for i in range(1, 7))}:
        raise HTTPException(status_code=422, detail="bandpass must be ALL or a supported SPHEREx-D1 through SPHEREx-D6 array.")

    query_str = q.strip()
    # Resolve names/frames/geographic input before using a coordinate-keyed cache.
    try:
        if input_mode == "earth":
            resolved = resolve_earth_lat_lon(query_str)
            if resolved is None:
                resolved = resolve_any_input(
                    query_str,
                    allow_coordinates=False,
                    allow_astronomical=False,
                    allow_geographic=True,
                )
        else:
            resolved = resolve_any_input(query_str, allow_geographic=False)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Target resolution error: {str(e)}")

    cache_payload = json.dumps(
        [
            input_mode,
            round(float(resolved["ra_deg"]), 8), round(float(resolved["dec_deg"]), 8),
            round(size_deg, 4), bandpass, max_epochs,
        ],
        separators=(",", ":"),
    )
    cache_key = hashlib.sha256(cache_payload.encode("utf-8")).hexdigest()
    cache_file = os.path.join(LIVE_CACHE_DIR, f"{cache_key}.json")

    def apply_current_resolution(payload):
        coordinates = payload.setdefault("coordinates", {})
        coordinates.update({
            "frame": "icrs",
            "ra_deg": float(resolved["ra_deg"]),
            "dec_deg": float(resolved["dec_deg"]),
            "input_frame": resolved.get("input_frame", "icrs"),
            "input_mode": input_mode,
            "earth_lat": resolved.get("earth_lat"),
            "earth_lon": resolved.get("earth_lon"),
            "observation_time_utc": resolved.get("observation_time_utc"),
        })
        metadata = payload.setdefault("metadata", {})
        metadata.update({
            "name": resolved.get("name") or metadata.get("name"),
            "target_id": resolved.get("target_id") or metadata.get("target_id"),
            "classification": resolved.get("object_type"),
            "spectral_type": resolved.get("spectral_type"),
            "proper_motion": resolved.get("total_pm_arcsec_yr"),
            "proper_motion_known": bool(resolved.get("proper_motion_known", False)),
            "pm_ra_mas_yr": resolved.get("pm_ra_mas_yr"),
            "pm_dec_mas_yr": resolved.get("pm_dec_mas_yr"),
        })
        return payload

    def has_usable_image_payload(payload):
        """Reject incomplete cache records before they reach the canvas renderer."""
        epochs = payload.get("epochs")
        if not isinstance(epochs, list) or not epochs:
            return False
        for epoch in epochs:
            pixels = epoch.get("pixels_u8") if isinstance(epoch, dict) else None
            if not isinstance(pixels, list) or not pixels or not isinstance(pixels[0], list):
                return False
            width = len(pixels[0])
            if width == 0 or len(pixels) > 2048 or width > 2048:
                return False
            if any(not isinstance(row, list) or len(row) != width for row in pixels):
                return False
            if any(
                not isinstance(value, (int, float)) or not 0 <= value <= 255
                for row in pixels for value in row
            ):
                return False
        return isinstance(payload.get("spectral_points", []), list)

    stale_live_cache = None
    stale_live_age_seconds = None
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                previous = json.load(f)
            previous_meta = previous.get("_cache", {})
            previous_source = previous.get("metadata", {}).get("data_source")
            previous_age = max(0, time.time() - float(previous_meta.get("created_at", 0)))
            if (
                previous_meta.get("schema_version") in STALE_CACHE_SCHEMA_VERSIONS
                and previous_source == "irsa_live_tap"
                and previous.get("coordinates")
                and has_usable_image_payload(previous)
                and abs(float(
                    previous["coordinates"].get("ra_deg")
                    if isinstance(previous["coordinates"], dict)
                    else previous["coordinates"][0]
                ) - float(resolved["ra_deg"])) < 1e-7
                and abs(float(
                    previous["coordinates"].get("dec_deg")
                    if isinstance(previous["coordinates"], dict)
                    else previous["coordinates"][1]
                ) - float(resolved["dec_deg"])) < 1e-7
            ):
                stale_live_cache = dict(previous)
                stale_live_cache.pop("_cache", None)
                stale_live_age_seconds = previous_age
        except Exception:
            stale_live_cache = None

    # Version 4 included the cache schema in its key. Probe that exact legacy
    # key once so good live results written by the previous build can migrate.
    if stale_live_cache is None:
        legacy_payload = json.dumps(
            [4, input_mode, round(float(resolved["ra_deg"]), 8), round(float(resolved["dec_deg"]), 8),
             round(size_deg, 4), bandpass, max_epochs],
            separators=(",", ":"),
        )
        legacy_file = os.path.join(LIVE_CACHE_DIR, f"{hashlib.sha256(legacy_payload.encode('utf-8')).hexdigest()}.json")
        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            legacy_cache = legacy.get("_cache", {})
            legacy_coords = legacy.get("coordinates")
            if (legacy_cache.get("schema_version") == 4
                    and legacy.get("metadata", {}).get("data_source") == "irsa_live_tap"
                    and legacy.get("epochs") and legacy_coords
                    and all(isinstance(epoch.get("pixels_u8"), list) and epoch["pixels_u8"] for epoch in legacy["epochs"])):
                stale_live_cache = {key: value for key, value in legacy.items() if key != "_cache"}
                stale_live_age_seconds = max(0, time.time() - float(legacy_cache.get("created_at", 0)))
        except (OSError, ValueError, TypeError, KeyError):
            pass

    if not refresh_archive and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cache_meta = cached.pop("_cache", {})
            metadata = cached.get("metadata", {})
            data_source = metadata.get("data_source")
            ttl = LIVE_CACHE_TTL_SECONDS if data_source == "irsa_live_tap" else SIMULATED_CACHE_TTL_SECONDS
            valid = (
                cache_meta.get("schema_version") == CACHE_SCHEMA_VERSION
                and data_source in {"irsa_live_tap", "simulated"}
                and has_usable_image_payload(cached)
                and time.time() - float(cache_meta.get("created_at", 0)) < ttl
            )
            if valid:
                metadata["cache_status"] = "cache_hit"
                metadata["cache_age_seconds"] = round(max(0, time.time() - float(cache_meta.get("created_at", time.time()))))
                print(f"[cache] hit {cache_key[:12]} ({metadata['data_source']}, {metadata['cache_age_seconds']}s old)")
                return apply_current_resolution(cached)
        except Exception:
            pass

    print(f"[cache] miss {cache_key[:12]} (refresh={refresh_archive})")

    try:
        try:
            cutout_data = scrape_spherex_target(
                coord=resolved,
                size_deg=size_deg,
                bandpass=bandpass,
                max_epochs=max_epochs,
                grid_size=384
            )
        except Exception as scrape_error:
            print(f"[archive] retrieval failed ({type(scrape_error).__name__}): {scrape_error}")
            if stale_live_cache is not None:
                stale_metadata = stale_live_cache.setdefault("metadata", {})
                stale_metadata["cache_status"] = "stale_archive_fallback"
                stale_metadata["cache_key"] = cache_key[:16]
                stale_metadata["stale_age_days"] = round((stale_live_age_seconds or 0) / 86400, 1)
                stale_metadata["retrieval_note"] = (
                    f"Fresh archive retrieval failed ({type(scrape_error).__name__}); showing the last successful archive result."
                )
                return apply_current_resolution(stale_live_cache)
            raise HTTPException(status_code=502, detail=f"Archive retrieval failed: {type(scrape_error).__name__}.")
        data_source = cutout_data.get("data_source") or (
            "irsa_live_tap" if cutout_data.get("source") == "irsa_live_tap" else "simulated"
        )
        cache_status = (
            "live_processed" if data_source == "irsa_live_tap" else "simulated_fallback"
        )
        public_data = {
            "coordinates": {
                "frame": "icrs",
                "ra_deg": float(resolved["ra_deg"]),
                "dec_deg": float(resolved["dec_deg"]),
                "input_frame": resolved.get("input_frame", "icrs"),
                "input_mode": input_mode,
                "earth_lat": resolved.get("earth_lat"),
                "earth_lon": resolved.get("earth_lon"),
                "observation_time_utc": resolved.get("observation_time_utc"),
            },
            "epochs": cutout_data.get("epochs", []),
            "spectral_points": cutout_data.get("spectral_points", []),
            "metadata": {
                "target_id": cutout_data.get("target_id") or resolved.get("target_id"),
                "name": cutout_data.get("name") or resolved.get("name"),
                "description": cutout_data.get("description") or resolved.get("description"),
                "catalog_fields": resolved.get("catalog_fields", {}),
                "proper_motion": resolved.get("total_pm_arcsec_yr"),
                "proper_motion_known": bool(resolved.get("proper_motion_known", False)),
                "pm_ra_mas_yr": resolved.get("pm_ra_mas_yr"),
                "pm_dec_mas_yr": resolved.get("pm_dec_mas_yr"),
                "classification": resolved.get("object_type"),
                "spectral_type": resolved.get("spectral_type"),
                "data_source": data_source,
                "cache_status": cache_status,
                "cache_key": cache_key[:16],
                "bandpass": bandpass,
                "size_deg": size_deg,
                "pixel_scale_arcsec": cutout_data.get("pixel_scale_arcsec"),
                "spectrum_status": "measured" if cutout_data.get("spectral_points") else "unavailable",
                "data_manifest": cutout_data.get("data_manifest", []),
                "retrieval_note": cutout_data.get("retrieval_note", ""),
            },
        }

        # A temporary archive outage should never replace the last usable FITS
        # result with a simulation. Return that result as stale and keep it on disk.
        if data_source == "simulated" and stale_live_cache is not None:
            stale_metadata = stale_live_cache.setdefault("metadata", {})
            stale_metadata["cache_status"] = "stale_archive_fallback"
            stale_metadata["cache_key"] = cache_key[:16]
            stale_metadata["stale_age_days"] = round((stale_live_age_seconds or 0) / 86400, 1)
            stale_metadata["retrieval_note"] = (
                (stale_metadata.get("retrieval_note", "") + " ").strip()
                + "A fresh archive request did not return usable FITS data; showing the last successful archive result."
            )
            return apply_current_resolution(stale_live_cache)

        # Save atomically: a partial write must never poison a future lookup.
        try:
            if data_source != "simulated" or stale_live_cache is None:
                cache_record = dict(public_data)
                cache_record["_cache"] = {
                    "schema_version": CACHE_SCHEMA_VERSION,
                    "created_at": time.time(),
                    "coordinates": [resolved["ra_deg"], resolved["dec_deg"]],
                    "query_parameters": {
                        "input_mode": input_mode,
                        "size_deg": size_deg,
                        "bandpass": bandpass,
                        "max_epochs": max_epochs,
                        "grid_size": 384,
                    },
                }
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=LIVE_CACHE_DIR, delete=False, suffix=".tmp"
                ) as temp_file:
                    json.dump(cache_record, temp_file, separators=(",", ":"))
                    temp_path = temp_file.name
                os.replace(temp_path, cache_file)
        except Exception as write_err:
            print(f"Warning: Could not write cache file: {write_err}")

        return public_data
    except HTTPException:
        raise
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
For technical questions about coordinates, measured spectral points, quality flags, or epoch comparisons, answer with precise astrophysical depth and provide a useful next question.
Return only JSON with exactly these string fields: {"reply":"...","suggested_question":"..."}.
Keep reply below 120 words. Say when a measurement is unavailable. Distinguish archive measurements from simulated data. Never infer a chemical identification from a local maximum/minimum alone."""


def compact_target_summary(target: Dict[str, Any]) -> Dict[str, Any]:
    """Whitelist scalar fields so images and other large payloads never reach Gemini."""
    name = str(target.get("name") or "Unknown target")[:80]
    ratio = target.get("optical_ir_ratio")
    try:
        ratio = float(ratio) if ratio is not None else None
    except (TypeError, ValueError):
        ratio = None
    try:
        proper_motion = float(target.get("proper_motion")) if target.get("proper_motion") is not None else None
    except (TypeError, ValueError):
        proper_motion = None
    try:
        wavelength = float(target.get("wavelength_um")) if target.get("wavelength_um") is not None else None
    except (TypeError, ValueError):
        wavelength = None
    try:
        epoch_count = max(0, min(6, int(target.get("epoch_count") or 0)))
    except (TypeError, ValueError):
        epoch_count = 0
    spectral_points = []
    for point in target.get("spectral_points", [])[:24]:
        if not isinstance(point, dict):
            continue
        compact_point = {
            key: _compact_number(point.get(key))
            for key in ("wavelength_um", "flux", "uncertainty", "detection_snr", "mjd")
        }
        compact_point.update({
            "flux_unit": str(point.get("flux_unit") or "")[:32],
            "bandpass": str(point.get("bandpass") or "")[:24],
            "epoch_index": _compact_number(point.get("epoch_index")),
        })
        spectral_points.append(compact_point)
    return {
        "name": name,
        "ra_deg": _compact_number(target.get("ra_deg")),
        "dec_deg": _compact_number(target.get("dec_deg")),
        "proper_motion": proper_motion,
        "proper_motion_known": bool(target.get("proper_motion_known", proper_motion is not None)),
        "optical_ir_ratio": ratio,
        "wavelength_um": wavelength,
        "epoch_count": epoch_count,
        "discovery_status": str(target.get("discovery_status") or "unverified")[:40],
        "data_source": str(target.get("data_source") or "unknown")[:40],
        "spectrum_is_synthetic": bool(target.get("spectrum_is_synthetic", False)),
        "spectral_points": spectral_points,
        "classification": str(target.get("classification") or "")[:80] or None,
        "catalog_fields": {
            str(key)[:40]: value if isinstance(value, (str, int, float, bool)) or value is None else str(value)[:80]
            for key, value in (target.get("catalog_fields", {}) if isinstance(target.get("catalog_fields"), dict) else {}).items()
        },
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
    asked_wavelength = None
    technical = bool(re.search(
        r"\b(proper motion|motion|vector|dipole|absorption|band|spectrum|spectral|sed|epoch|difference|wavelength|microns?|quality|flag|coordinate|brightness|flux|ratio|catalog)\b",
        low,
    )) or bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:µm|um)\b", low))

    if technical:
        wave_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:um|µm|microns?)\b", low)
        if wave_match:
            asked_wavelength = float(wave_match.group(1))
        wavelength_text = f"{wavelength:g} µm" if wavelength is not None else "not specified"
        motion_text = (
            f"The supplied proper motion is {motion:g} arcsec/year."
            if target.get("proper_motion_known") and motion is not None
            else "Proper motion is not available in the active target summary."
        )
        if any(term in low for term in ("spectrum", "spectral", "sed", "absorption", "band", "wavelength", "micron", "µm")):
            reference_wavelength = asked_wavelength if asked_wavelength is not None else wavelength
            reference_text = f"{reference_wavelength:g} µm" if reference_wavelength is not None else "unspecified"
            wavelength_note = f"The question refers to {reference_text}." if reference_wavelength is not None else "No wavelength is available in the active summary."
            if wavelength is not None:
                wavelength_note += f" The latest image band is {wavelength_text}."
            measured = [p for p in target.get("spectral_points", []) if _compact_number(p.get("wavelength_um")) is not None and _compact_number(p.get("flux")) is not None]
            spectrum_note = f"The active payload includes {len(measured)} measured wavelength/flux point(s)." if measured else "No measured spectrum is available in the active payload."
            if asked_wavelength is not None and measured:
                nearest = min(measured, key=lambda point: abs(float(point["wavelength_um"]) - asked_wavelength))
                wave = float(nearest["wavelength_um"])
                flux = float(nearest["flux"])
                unit = str(nearest.get("flux_unit") or "flux units")
                uncertainty = _compact_number(nearest.get("uncertainty"))
                sample_note = f"Nearest returned point: {wave:.5g} µm = {flux:.5g} {unit}"
                if uncertainty is not None:
                    sample_note += f" ± {uncertainty:.3g}"
                sample_note += f" (epoch {nearest.get('epoch_index', 'unknown')})."
                spectrum_note += " " + sample_note
            reply = f"{name}: {wavelength_note} {spectrum_note} {motion_text}"
            question = "Would you like to inspect returned measurements or compare the observation epochs?"
        elif "ratio" in low or "catalog" in low:
            ratio_note = (
                f"The supplied optical-to-infrared ratio is {ratio:g}."
                if ratio is not None else "An optical-to-infrared flux ratio is not available in the active data."
            )
            catalog_fields = target.get("catalog_fields") or {}
            catalog_note = (
                " Catalog fields supplied: " + ", ".join(f"{key}={value}" for key, value in list(catalog_fields.items())[:5]) + "."
                if catalog_fields else " No cross-catalog match fields were supplied."
            )
            reply = f"{name}: {ratio_note}{catalog_note} {motion_text}"
            question = "Would you like to inspect the available measurements or catalog fields?"
        else:
            image_note = "The displayed images are simulated, so they are not archive detections." if target.get("data_source") != "irsa_live_tap" else "The displayed images are processed IRSA archive cutouts."
            reply = f"{name}: {motion_text} The active image contains {target['epoch_count']} epoch(s). {image_note}"
            question = "Would you like to compare the first two epochs or inspect the data source?"
    else:
        motion_text = (
            f"The configured proper motion is {motion:g} arcsec/year."
            if target.get("proper_motion_known") and motion is not None
            else "Proper motion is not available for this target."
        )
        ra_text = f"{target['ra_deg']:.5f}°" if target["ra_deg"] is not None else "unknown"
        dec_text = f"{target['dec_deg']:.5f}°" if target["dec_deg"] is not None else "unknown"
        reply = f"{name} is centered at RA {ra_text}, Dec {dec_text}. {motion_text} The view compares {target['epoch_count']} epoch(s); check the source label to see whether they are live archive data or simulated."
        question = "Would you like to inspect the image source or compare the first two epochs?"
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
    target = compact_target_summary(payload.target)
    prompt = payload.prompt.strip()
    history = payload.history[-4:]
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)

    try:
        _enforce_gemini_rate_limit(request)
    except HTTPException as error:
        if error.status_code != 429:
            raise
        local = _local_analysis(prompt, target)
        local["source"] = "local_rate_limit_fallback"
        local["notice"] = "The assistant's online request limit was reached; this answer uses the available target metadata."
        return local

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
                "suggested_question": suggested_question,
                "source": "gemini"
            }
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"Gemini analysis unavailable ({type(error).__name__}); using the local analyzer.")

    result = _local_analysis(prompt, target)
    result["source"] = "local_metadata"
    return result


@app.get("/api/spectrum")
def get_spectrum():
    """No target-independent synthetic spectrum is served; use measured /api/sky points."""
    return {"spectral_points": [], "status": "unavailable", "note": "Load a target through /api/sky to request archive measurements."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
