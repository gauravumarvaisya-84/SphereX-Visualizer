"""
Astro Tools & Mathematical Engine for SphereX Visualizer
Team Pioneer Matrix - NASA Space Apps Challenge 2026
"""

import re
import numpy as np
from typing import Tuple, List, Dict, Any, Union


def parse_ra_to_deg(ra_input: Union[str, float, int]) -> float:
    """
    Parse Right Ascension string or number into decimal degrees [0, 360).
    Supports:
      - Decimal degrees: 269.452083
      - Sexagesimal hours: '17h 57m 48.50s', '17:57:48.50', '17 57 48.5'
      - Sexagesimal degrees: '269d 27m 07.5s'
    """
    if isinstance(ra_input, (int, float)):
        return float(ra_input) % 360.0

    s = str(ra_input).strip()
    if not s:
        raise ValueError("Empty RA input")

    # Try direct float
    try:
        val = float(s)
        return val % 360.0
    except ValueError:
        pass

    # Check if sexagesimal hours with 'h', 'm', 's'
    hms_match = re.match(r'^([+-]?\d+(?:\.\d+)?)\s*h(?:ours?)?\s*(\d+(?:\.\d+)?)\s*m(?:in(?:utes?)?)?\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?', s, re.IGNORECASE)
    if hms_match:
        h, m, sec = map(float, hms_match.groups())
        deg = (h + m / 60.0 + sec / 3600.0) * 15.0
        return deg % 360.0

    # Colon or space separated '17:57:48.5' or '17 57 48.5'
    colon_match = re.match(r'^([+-]?\d+(?:\.\d+)?)(?::|\s+)(\d+(?:\.\d+)?)(?::|\s+)(\d+(?:\.\d+)?)$', s)
    if colon_match:
        p1, p2, p3 = map(float, colon_match.groups())
        # If p1 <= 24, typically sexagesimal hours
        if abs(p1) <= 24.0:
            deg = (p1 + p2 / 60.0 + p3 / 3600.0) * 15.0
        else:
            deg = p1 + p2 / 60.0 + p3 / 3600.0
        return deg % 360.0

    # '269d 27m 07.5s'
    dms_match = re.match(r'^([+-]?\d+(?:\.\d+)?)\s*d(?:eg(?:rees?)?)?\s*(\d+(?:\.\d+)?)\s*m(?:in)?\s*(\d+(?:\.\d+)?)\s*s?', s, re.IGNORECASE)
    if dms_match:
        d, m, sec = map(float, dms_match.groups())
        deg = d + m / 60.0 + sec / 3600.0
        return deg % 360.0

    raise ValueError(f"Unable to parse Right Ascension: '{ra_input}'")


def parse_dec_to_deg(dec_input: Union[str, float, int]) -> float:
    """
    Parse Declination string or number into decimal degrees [-90, +90].
    Supports:
      - Decimal degrees: 4.693389, -7.245147
      - Sexagesimal degrees: '+04° 41′ 36.2″', '+04d 41m 36.2s', '-07:14:42.5', '+04 41 36.2'
    """
    if isinstance(dec_input, (int, float)):
        val = float(dec_input)
        if not (-90.0 <= val <= 90.0):
            raise ValueError(f"Declination {val} out of range [-90, +90]")
        return val

    s = str(dec_input).strip()
    if not s:
        raise ValueError("Empty Dec input")

    # Try direct float
    try:
        val = float(s)
        if -90.0 <= val <= 90.0:
            return val
    except ValueError:
        pass

    # Normalize unicode symbols: '°' -> 'd', '′' or "'" -> 'm', '″' or '"' -> 's'
    norm = s.replace('°', 'd').replace('′', 'm').replace("'", 'm').replace('″', 's').replace('"', 's')

    # Match format like +04d 41m 36.2s
    dms_match = re.match(r'^([+-]?\d+(?:\.\d+)?)\s*d(?:eg)?\s*(\d+(?:\.\d+)?)\s*m(?:in)?\s*(\d+(?:\.\d+)?)\s*s?$', norm, re.IGNORECASE)
    if dms_match:
        d_str, m_str, s_str = dms_match.groups()
        sign = -1.0 if d_str.strip().startswith('-') else 1.0
        d = abs(float(d_str))
        m = float(m_str)
        sec = float(s_str)
        val = sign * (d + m / 60.0 + sec / 3600.0)
        if not (-90.0 <= val <= 90.0):
            raise ValueError(f"Declination {val} out of range [-90, +90]")
        return val

    # Match colon or space separated '+04:41:36.2' or '-07 14 42.5'
    sep_match = re.match(r'^([+-]?\d+(?:\.\d+)?)(?::|\s+)(\d+(?:\.\d+)?)(?::|\s+)(\d+(?:\.\d+)?)$', norm)
    if sep_match:
        d_str, m_str, s_str = sep_match.groups()
        sign = -1.0 if d_str.strip().startswith('-') else 1.0
        d = abs(float(d_str))
        m = float(m_str)
        sec = float(s_str)
        val = sign * (d + m / 60.0 + sec / 3600.0)
        if not (-90.0 <= val <= 90.0):
            raise ValueError(f"Declination {val} out of range [-90, +90]")
        return val

    raise ValueError(f"Unable to parse Declination: '{dec_input}'")


def deg_to_sexagesimal(ra_deg: float, dec_deg: float) -> Tuple[str, str]:
    """
    Convert decimal (RA, Dec) in degrees into standard sexagesimal strings:
      RA:  'HHh MMm SS.SSs'
      Dec: '±DD° MM′ SS.S″'
    """
    # RA to hours
    ra_hrs = (ra_deg % 360.0) / 15.0
    h = int(ra_hrs)
    rem_m = (ra_hrs - h) * 60.0
    m = int(rem_m)
    s = (rem_m - m) * 60.0
    ra_hms = f"{h:02d}h {m:02d}m {s:05.2f}s"

    # Dec
    sign = "+" if dec_deg >= 0 else "-"
    abs_dec = abs(dec_deg)
    d = int(abs_dec)
    rem_dm = (abs_dec - d) * 60.0
    dm = int(rem_dm)
    ds = (rem_dm - dm) * 60.0
    dec_dms = f"{sign}{d:02d}° {dm:02d}′ {ds:04.1f}″"

    return ra_hms, dec_dms


def project_proper_motion(
    ra_deg: float,
    dec_deg: float,
    pm_ra_mas_yr: float,
    pm_dec_mas_yr: float,
    delta_years: float
) -> Tuple[float, float, float]:
    """
    Project astronomical position forward or backward in time using spherical geometry.
    Proper motion in RA (pm_ra_mas_yr) is assumed to be pm_ra * cos(dec), standard for Gaia/Hipparcos.
    Returns:
      (projected_ra_deg, projected_dec_deg, total_shift_arcsec)
    """
    dec_rad = np.radians(dec_deg)
    cos_dec = np.cos(dec_rad)
    
    # Avoid division by zero near celestial poles
    if abs(cos_dec) < 1e-7:
        cos_dec = 1e-7

    # delta RA in degrees: pm_ra_mas_yr / cos(dec) converted from mas to deg
    delta_ra_deg = (pm_ra_mas_yr * delta_years / (cos_dec * 3.6e6))
    delta_dec_deg = (pm_dec_mas_yr * delta_years) / 3.6e6

    new_ra = (ra_deg + delta_ra_deg) % 360.0
    new_dec = np.clip(dec_deg + delta_dec_deg, -90.0, 90.0)

    # Total angular displacement on sky in arcseconds
    shift_arcsec = (np.sqrt(pm_ra_mas_yr**2 + pm_dec_mas_yr**2) * abs(delta_years)) / 1000.0

    return float(new_ra), float(new_dec), float(shift_arcsec)


def compute_image_difference(
    epoch1_img: Union[np.ndarray, List[List[float]]],
    epoch2_img: Union[np.ndarray, List[List[float]]]
) -> Dict[str, Any]:
    """
    Compute pixel-by-pixel image difference (Epoch 2 - Epoch 1).
    Static stars cancel (|diff| <= 15).
    Positive residuals (> 15) indicate new object position or brightening.
    Negative residuals (< -15) indicate prior object position or fading.
    """
    e1 = np.asarray(epoch1_img, dtype=np.float32)
    e2 = np.asarray(epoch2_img, dtype=np.float32)

    if e1.shape != e2.shape:
        raise ValueError(f"Shape mismatch: {e1.shape} vs {e2.shape}")

    diff = e2 - e1
    abs_diff = np.abs(diff)

    # Dipole analysis
    pos_mask = diff > 15.0
    neg_mask = diff < -15.0

    pos_count = int(np.sum(pos_mask))
    neg_count = int(np.sum(neg_mask))

    # Center of mass for positive and negative residuals
    pos_center = None
    neg_center = None
    if pos_count > 0:
        y_indices, x_indices = np.where(pos_mask)
        weights = diff[pos_mask]
        total_w = np.sum(weights)
        pos_center = [float(np.sum(x_indices * weights) / total_w), float(np.sum(y_indices * weights) / total_w)]

    if neg_count > 0:
        y_indices, x_indices = np.where(neg_mask)
        weights = np.abs(diff[neg_mask])
        total_w = np.sum(weights)
        neg_center = [float(np.sum(x_indices * weights) / total_w), float(np.sum(y_indices * weights) / total_w)]

    is_dipole = bool(pos_count >= 2 and neg_count >= 2)

    return {
        "diff_matrix": diff.tolist(),
        "min_val": float(np.min(diff)),
        "max_val": float(np.max(diff)),
        "mean_val": float(np.mean(diff)),
        "std_val": float(np.std(diff)),
        "pos_count": pos_count,
        "neg_count": neg_count,
        "pos_center": pos_center,
        "neg_center": neg_center,
        "is_dipole": is_dipole
    }


def generate_spherex_spectral_profile(object_type: str = "") -> Dict[str, Any]:
    """Compatibility stub: spectra must come from archive measurements, never templates.

    The argument is accepted for older callers but does not select a modeled spectrum.
    New code should use `spectral_points` returned by the archive processing pipeline.
    """
    return {
        "object_type": None,
        "bands_count": 0,
        "wavelengths_um": [],
        "flux": [],
        "detector_arrays": [],
        "absorption_features": [],
        "status": "unavailable",
        "note": "No synthetic spectrum is generated; use measured archive spectral points.",
    }
