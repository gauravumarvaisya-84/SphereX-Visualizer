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


def generate_spherex_spectral_profile(object_type: str) -> Dict[str, Any]:
    """
    Synthesize high-fidelity 102-band spectral energy distribution (SED) across 0.75 - 5.0 µm,
    covering the 6 SPHEREx detector arrays (Arr 1 to Arr 6) with key astrophysical molecular features:
    - H2O: 1.15, 1.4, 1.9, 2.7, 3.0 µm ice absorption
    - CH4: 1.66, 2.2, 3.3 µm
    - CO2: 4.26 µm
    - CO: 2.3 µm, 4.6 µm
    """
    # 102 bands logarithmically spaced from 0.75 to 5.00 µm
    wavelengths = np.geomspace(0.75, 5.00, 102)

    # Assign each wavelength to its SPHEREx detector array
    # Array 1: 0.75 - 1.11 µm
    # Array 2: 1.11 - 1.64 µm
    # Array 3: 1.64 - 2.42 µm
    # Array 4: 2.42 - 3.82 µm
    # Array 5: 3.82 - 4.42 µm
    # Array 6: 4.42 - 5.00 µm
    def get_array(w: float) -> str:
        if w < 1.11: return "Arr 1 (0.75-1.11 µm)"
        if w < 1.64: return "Arr 2 (1.11-1.64 µm)"
        if w < 2.42: return "Arr 3 (1.64-2.42 µm)"
        if w < 3.82: return "Arr 4 (2.42-3.82 µm)"
        if w < 4.42: return "Arr 5 (3.82-4.42 µm)"
        return "Arr 6 (4.42-5.00 µm)"

    arrays = [get_array(w) for w in wavelengths]

    norm_type = object_type.lower().replace("-", "_").replace(" ", "_")

    # Planck blackbody function approximation
    def planck(w_um: np.ndarray, temp_k: float) -> np.ndarray:
        w_m = w_um * 1e-6
        h = 6.626e-34
        c = 3.0e8
        k = 1.38e-23
        exp_arg = (h * c) / (w_m * k * temp_k)
        exp_arg = np.clip(exp_arg, 1e-4, 50.0)
        return (2.0 * h * c**2) / (w_m**5 * (np.exp(exp_arg) - 1.0))

    features = []

    if "brown_dwarf" in norm_type or "wise" in norm_type or "y_dwarf" in norm_type or "t_dwarf" in norm_type:
        # Sub-stellar ultra-cool brown dwarf (~250 - 600 K)
        # Strong CH4, H2O vapor + ice, and a distinct 4.5-4.8 µm flux window
        base_flux = planck(wavelengths, 450.0)
        base_flux = base_flux / np.max(base_flux) * 0.4

        # Molecular absorption bands (Gaussian notches)
        def absorption(w_center: float, width: float, depth: float):
            return 1.0 - depth * np.exp(-0.5 * ((wavelengths - w_center) / width) ** 2)

        # H2O absorption at 1.15, 1.4, 1.9, 2.7 µm
        base_flux *= absorption(1.15, 0.05, 0.6)
        base_flux *= absorption(1.40, 0.08, 0.85)
        base_flux *= absorption(1.90, 0.10, 0.90)
        base_flux *= absorption(2.70, 0.12, 0.85)
        # H2O water ice absorption around 3.05 µm
        base_flux *= absorption(3.05, 0.20, 0.75)
        # CH4 methane absorption at 1.66, 2.20, 3.32 µm
        base_flux *= absorption(1.66, 0.06, 0.70)
        base_flux *= absorption(2.20, 0.09, 0.80)
        base_flux *= absorption(3.32, 0.15, 0.92)
        # CO2 absorption at 4.26 µm
        base_flux *= absorption(4.26, 0.06, 0.65)

        # 4.5-4.8 µm methane opacity window peak (prominent in Y/T dwarfs like WISE 0855)
        window_boost = 0.85 * np.exp(-0.5 * ((wavelengths - 4.65) / 0.22) ** 2)
        base_flux += window_boost

        features = [
            {"molecule": "H2O vapor", "wavelength_um": 1.40, "note": "Vapor bandhead in cool atmosphere"},
            {"molecule": "CH4 methane", "wavelength_um": 1.66, "note": "Characteristic 2ν3 band"},
            {"molecule": "H2O vapor", "wavelength_um": 1.90, "note": "Deep water absorption trough"},
            {"molecule": "CH4 methane", "wavelength_um": 2.20, "note": "Strong overtone absorption"},
            {"molecule": "H2O ice clouds", "wavelength_um": 3.05, "note": "Diagnostic water-ice mantle (sub-250K)"},
            {"molecule": "CH4 methane (ν3)", "wavelength_um": 3.32, "note": "Fundamental methane vibrational band"},
            {"molecule": "CO2 band", "wavelength_um": 4.26, "note": "Atmospheric carbon dioxide notch"},
            {"molecule": "4.65 µm Opacity Window", "wavelength_um": 4.65, "note": "Clear-atmosphere infrared emission peak"}
        ]

    elif "red_dwarf" in norm_type or "barnard" in norm_type or "m_dwarf" in norm_type:
        # M-dwarf star (~3100 K, e.g., Barnard's Star)
        base_flux = planck(wavelengths, 3134.0)
        base_flux = base_flux / np.max(base_flux)

        def absorption(w_center: float, width: float, depth: float):
            return 1.0 - depth * np.exp(-0.5 * ((wavelengths - w_center) / width) ** 2)

        # TiO / VO / H2O / CO
        base_flux *= absorption(0.85, 0.04, 0.18)
        base_flux *= absorption(1.13, 0.05, 0.25)
        base_flux *= absorption(1.40, 0.07, 0.35)
        base_flux *= absorption(1.90, 0.08, 0.40)
        base_flux *= absorption(2.32, 0.05, 0.30)  # CO bandhead
        base_flux *= absorption(4.60, 0.10, 0.22)  # CO fundamental

        features = [
            {"molecule": "TiO / VO", "wavelength_um": 0.85, "note": "Optical-NIR oxide absorption"},
            {"molecule": "H2O vapor", "wavelength_um": 1.40, "note": "Stellar photosphere water vapor"},
            {"molecule": "H2O vapor", "wavelength_um": 1.90, "note": "Deep IR water band"},
            {"molecule": "CO First Overtone", "wavelength_um": 2.32, "note": "Carbon monoxide molecular bandhead"},
            {"molecule": "CO Fundamental", "wavelength_um": 4.60, "note": "Photospheric CO absorption"}
        ]

    elif "t_tauri" in norm_type or "rw_aurigae" in norm_type:
        # Young Stellar Object (T Tauri) with circumstellar dust accretion disk
        # Stellar component (~4000 K) + warm dust disk component (1000 K - 300 K)
        star = planck(wavelengths, 4000.0)
        star = star / np.max(star) * 0.7
        disk = planck(wavelengths, 950.0)
        disk = disk / np.max(disk) * 0.65
        base_flux = star + disk

        def absorption(w_center: float, width: float, depth: float):
            return 1.0 - depth * np.exp(-0.5 * ((wavelengths - w_center) / width) ** 2)

        # Circumstellar ices and CO
        base_flux *= absorption(2.35, 0.06, 0.25)
        base_flux *= absorption(3.05, 0.15, 0.35)  # Ice coating on grains
        base_flux *= absorption(4.26, 0.05, 0.20)  # CO2 ice in protoplanetary disk
        base_flux *= absorption(4.67, 0.08, 0.28)  # CO ice / gas

        features = [
            {"molecule": "Circumstellar Dust Excess", "wavelength_um": 1.80, "note": "Accretion disk continuum rise"},
            {"molecule": "CO overtone", "wavelength_um": 2.35, "note": "Inner accretion disk gas"},
            {"molecule": "H2O Ice Mantle", "wavelength_um": 3.05, "note": "Protoplanetary disk frost line ice"},
            {"molecule": "CO2 Ice", "wavelength_um": 4.26, "note": "Cold grain surface volatile ice"},
            {"molecule": "CO fundamental", "wavelength_um": 4.67, "note": "Disk outflow/envelope gas"}
        ]

    elif "mira" in norm_type or "r_draconis" in norm_type:
        # Pulsating AGB red giant (~2400 K)
        base_flux = planck(wavelengths, 2400.0)
        base_flux = base_flux / np.max(base_flux)

        def absorption(w_center: float, width: float, depth: float):
            return 1.0 - depth * np.exp(-0.5 * ((wavelengths - w_center) / width) ** 2)

        base_flux *= absorption(1.40, 0.09, 0.50)
        base_flux *= absorption(1.90, 0.10, 0.60)
        base_flux *= absorption(2.30, 0.06, 0.45)
        base_flux *= absorption(2.70, 0.11, 0.55)
        base_flux *= absorption(4.26, 0.05, 0.25)
        base_flux *= absorption(4.65, 0.08, 0.40)

        features = [
            {"molecule": "H2O vapor envelope", "wavelength_um": 1.40, "note": "Extended giant envelope water vapor"},
            {"molecule": "H2O vapor", "wavelength_um": 1.90, "note": "Strong molecular opacity in cool atmosphere"},
            {"molecule": "CO overtone", "wavelength_um": 2.30, "note": "Diagnostic carbon monoxide bandhead"},
            {"molecule": "CO fundamental", "wavelength_um": 4.65, "note": "Strong circumstellar absorption"}
        ]

    else:
        # Generic stellar / solar profile (~5770 K)
        base_flux = planck(wavelengths, 5770.0)
        base_flux = base_flux / np.max(base_flux)
        features = [
            {"molecule": "NIR Continuum", "wavelength_um": 1.60, "note": "H- opacity minimum peak"},
            {"molecule": "CO band", "wavelength_um": 4.65, "note": "Photospheric carbon monoxide"}
        ]

    # Normalize flux to 0..100 scale for plotting
    max_f = np.max(base_flux)
    if max_f > 0:
        base_flux = (base_flux / max_f) * 100.0

    return {
        "object_type": object_type,
        "bands_count": len(wavelengths),
        "wavelengths_um": [round(float(w), 4) for w in wavelengths],
        "flux": [round(float(f), 2) for f in base_flux],
        "detector_arrays": arrays,
        "absorption_features": features
    }
