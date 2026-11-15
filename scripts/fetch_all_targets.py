"""
Live IRSA Scraper, Astrometric Resolver & Target Pre-cacher
Team Pioneer Matrix - NASA Space Apps Challenge 2026
"""

import os
import sys
import json
import time
import hashlib
import re
import http.client
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import requests
import numpy as np
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Union

# Astropy coordinates and units
import astropy.units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, ICRS, frame_transform_graph
from astropy.time import Time
from astropy.io import fits
from astropy.wcs import WCS
from astropy.stats import sigma_clipped_stats
from astropy.utils.data import conf as astropy_data_conf, download_file
from astroquery.ipac.irsa import Irsa
from requests.adapters import HTTPAdapter

# Ensure local scripts importable
sys.path.insert(0, os.path.dirname(__file__))
from astro_tools import project_proper_motion

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
CUTOUTS_DIR = os.path.join(CONFIG_DIR, "cutouts")
IRSA_FITS_READ_TIMEOUT_SECONDS = 120
IRSA_EPOCH_DOWNLOAD_BUDGET_SECONDS = 120
astropy_data_conf.remote_timeout = IRSA_FITS_READ_TIMEOUT_SECONDS


class _TimeoutHTTPAdapter(HTTPAdapter):
    """Keep archive TAP calls bounded when astroquery omits a timeout."""

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (5, 20)
        return super().send(request, **kwargs)


def _configure_irsa_tap_timeout() -> None:
    # PyVO's synchronous TAP request currently supplies no timeout. Mount an
    # adapter on its shared session so network stalls reach the retry/fallback.
    tap_session = Irsa.tap._session
    tap_session.mount("https://", _TimeoutHTTPAdapter())


def parse_coordinate_input(value: str) -> tuple[SkyCoord, str]:
    """Parse a coordinate pair in an explicitly named Astropy frame or ICRS by default.

    Accepted forms include ``269.4, 4.6``, ``17:57:48 +04:41:36`` and
    ``galactic|12.3, -4.5``. Any registered Astropy frame may be named before ``|``.
    """
    raw = value.strip()
    frame_name, separator, coordinate_text = raw.partition("|")
    if not separator:
        frame_name, coordinate_text = "icrs", raw
    frame_name = frame_name.strip().lower()
    coordinate_text = coordinate_text.strip()
    if frame_name not in frame_transform_graph.get_names():
        raise ValueError(f"Unsupported coordinate frame '{frame_name}'.")

    parts = [part.strip() for part in re.split(r"[,;\t]", coordinate_text) if part.strip()]
    if len(parts) == 2:
        first_is_sexagesimal = bool(re.search(r"[:hmsd°′″]", parts[0], re.IGNORECASE))
        equatorial_frame = frame_name in {"icrs", "fk4", "fk5", "fk4noeterms", "gcrs", "cirs"}
        units = (u.hourangle, u.deg) if first_is_sexagesimal and equatorial_frame else (u.deg, u.deg)
        coord = SkyCoord(parts[0], parts[1], frame=frame_name, unit=units)
    else:
        try:
            coord = SkyCoord(coordinate_text, frame=frame_name)
        except Exception:
            if frame_name in {"icrs", "fk4", "fk5", "fk4noeterms", "gcrs", "cirs"}:
                coord = SkyCoord(coordinate_text, frame=frame_name, unit=(u.hourangle, u.deg))
            else:
                coord = SkyCoord(coordinate_text, frame=frame_name, unit=(u.deg, u.deg))
    if not coord.isscalar:
        raise ValueError("Enter exactly one coordinate pair.")
    return coord.icrs, frame_name


def resolve_any_input(
    user_input: str,
    *,
    allow_coordinates: bool = True,
    allow_astronomical: bool = True,
    allow_geographic: bool = True,
) -> Dict[str, Any]:
    """
    Resolve any user input into RA, Dec (J2000 decimal degrees).
    Supports:
      (a) Raw decimal or sexagesimal "ra, dec" coordinates
      (b) Astronomical names via SkyCoord.from_name() (CDS Sesame)
      (c) Earth cities/addresses via OpenStreetMap Nominatim -> overhead zenith (RA, Dec) at Time.now()
    """
    raw = str(user_input).strip()
    if not raw:
        raise ValueError("Input string is empty.")

    if allow_coordinates:
        try:
            coord, input_frame = parse_coordinate_input(raw)
            ra_deg, dec_deg = float(coord.ra.deg), float(coord.dec.deg)
            return {
                "target_id": "coordinate_" + hashlib.sha256(f"{ra_deg:.8f},{dec_deg:.8f}".encode()).hexdigest()[:16],
                "name": f"Coordinates ({ra_deg:.5f}°, {dec_deg:.5f}°)",
                "ra_deg": ra_deg,
                "dec_deg": dec_deg,
                "input_frame": input_frame,
                "pm_ra_mas_yr": None,
                "pm_dec_mas_yr": None,
                "total_pm_arcsec_yr": None,
                "proper_motion_known": False,
                "spectral_type": None,
                "object_type": None,
                "description": "Resolved coordinate field in ICRS.",
                "source": "coordinates",
            }
        except Exception:
            pass

    # (b) Try Astronomical Name Resolution via CDS Sesame (SkyCoord.from_name)
    geographic_lookup_error = None
    try:
        if not allow_astronomical:
            raise ValueError("Astronomical name lookup is disabled for Earth location mode.")
        coord = SkyCoord.from_name(raw)
        ra_deg = float(coord.ra.deg)
        dec_deg = float(coord.dec.deg)
        return {
            "target_id": raw.lower().replace(" ", "_"),
            "name": raw,
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "pm_ra_mas_yr": 0.0,
            "pm_dec_mas_yr": 0.0,
            "total_pm_arcsec_yr": 0.0,
            "spectral_type": "Catalog Object",
            "object_type": "stellar_object",
            "description": f"Astronomical target {raw} resolved via CDS Sesame / SIMBAD",
            "proper_motion_known": False,
            "source": "cds_sesame"
        }
    except Exception:
        # Not recognized by CDS Sesame or network down, fall through to Nominatim
        pass

    # (c) Try Earth city / geographic location via OpenStreetMap Nominatim
    try:
        if not allow_geographic:
            raise ValueError("Geographic lookup is disabled for sky target mode.")
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "SphereX-Visualizer-PioneerMatrix-NASA-SpaceApps/1.0 (contact: info@pioneermatrix.space)"}
        params = {"q": raw, "format": "json", "limit": 1}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            results = resp.json()
            if results and len(results) > 0:
                first = results[0]
                lat = float(first["lat"])
                lon = float(first["lon"])
                display_name = first.get("display_name", raw)

                # Convert Earth location to overhead zenith (Alt=90, Az=0) at Time.now()
                now = Time.now()
                loc = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
                zenith_altaz = AltAz(alt=90.0 * u.deg, az=0.0 * u.deg, obstime=now, location=loc)
                zenith_icrs = zenith_altaz.transform_to(ICRS())

                ra_deg = float(zenith_icrs.ra.deg)
                dec_deg = float(zenith_icrs.dec.deg)

                return {
                    "target_id": f"zenith_{raw.lower()[:12].replace(' ', '_')}",
                    "name": f"Zenith above {raw.split(',')[0]}",
                    "ra_deg": ra_deg,
                    "dec_deg": dec_deg,
                    "pm_ra_mas_yr": 0.0,
                    "pm_dec_mas_yr": 0.0,
                    "total_pm_arcsec_yr": 0.0,
                    "proper_motion_known": False,
                    "spectral_type": "Zenith Field",
                    "object_type": "overhead_sky",
                    "city": raw,
                    "earth_lat": lat,
                    "earth_lon": lon,
                    "observation_time_utc": str(now.iso),
                    "description": f"Overhead night-sky coordinates directly above {display_name} at {now.iso}",
                    "source": "zenith_nominatim"
                }
            geographic_lookup_error = "The location service returned no matching place."
        else:
            geographic_lookup_error = f"The location service returned HTTP {resp.status_code}."
    except requests.Timeout:
        geographic_lookup_error = "The location service timed out. Please retry or enter coordinates."
    except requests.RequestException as exc:
        geographic_lookup_error = f"The location service could not be reached ({exc.__class__.__name__})."
    except (KeyError, TypeError, ValueError):
        geographic_lookup_error = "The location service returned an invalid result."

    # If all resolvers fail, raise descriptive error
    if allow_geographic:
        guidance = geographic_lookup_error or "Please provide a valid city/address or latitude, longitude."
    else:
        guidance = "Please provide a recognized astronomical name or valid RA/Dec coordinates."
    raise ValueError(f"Could not resolve input '{raw}'. {guidance}")


def synthesize_spherex_cutouts(
    target_info: Dict[str, Any],
    size_deg: float = 0.05,
    bandpass: str = "SPHEREx-D2",
    max_epochs: int = 3,
    grid_size: int = 128
) -> Dict[str, Any]:
    """
    Deterministic astrophysics simulation fallback when IRSA TAP has no coverage or during offline testing.
    Synthesizes calibrated SPHEREx cutouts across ~6-month epochs, incorporating:
    - Target proper motion displacement (cos(dec) corrected)
    - Zodiacal background subtraction
    - Instrumental Gaussian PSF (FWHM ~ 6.2")
    - Photon noise and log1p dynamic range compression
    - Resampling to 128x128 uint8
    """
    ra = target_info["ra_deg"]
    dec = target_info["dec_deg"]
    # Unknown motion stays unknown in metadata and is treated as zero only for
    # generating a visually stable fallback scene.
    pm_ra = float(target_info.get("pm_ra_mas_yr") or 0.0)
    pm_dec = float(target_info.get("pm_dec_mas_yr") or 0.0)

    # Deterministic pseudo-random seed based on coordinate hash
    coord_seed = int(hashlib.md5(f"{ra:.5f}_{dec:.5f}".encode()).hexdigest()[:8], 16) % (2**31 - 1)
    rng = np.random.RandomState(coord_seed)

    # 1 arcmin = 1/60 deg; size_deg = 0.05 -> ~3 arcmin FOV
    # Plate scale: size_deg * 3600 arcsec / grid_size pixels
    # e.g. 0.05 * 3600 / 128 = 1.406 arcsec/pixel
    fov_arcsec = size_deg * 3600.0
    pixel_scale_arcsec = fov_arcsec / float(grid_size)

    # Background static stars (50-80 stars in field)
    n_bg_stars = rng.randint(45, 80)
    bg_xs = rng.uniform(8, grid_size - 8, n_bg_stars)
    bg_ys = rng.uniform(8, grid_size - 8, n_bg_stars)
    # Stellar magnitudes converted to infrared flux (log-normal distribution)
    bg_fluxes = rng.exponential(scale=65.0, size=n_bg_stars) + 15.0

    # SPHEREx PSF standard deviation in pixels (FWHM ~ 6.2" / 2.355 / pixel_scale)
    psf_sigma_px = max(1.1, (6.2 / 2.355) / pixel_scale_arcsec)

    # Simulation-only dates are separated from the archive's actual observation span.
    base_mjd = 61000.0
    epoch_interval_days = 182.5

    # Target center at epoch 1 is near center of frame (x0, y0)
    center_x = (grid_size - 1) / 2.0
    center_y = (grid_size - 1) / 2.0

    epochs = []
    data_products = []
    display_signals = []
    y_coords, x_coords = np.mgrid[0:grid_size, 0:grid_size]

    # Wavelength in microns corresponding to bandpass
    bandpass_wavelengths = {
        "SPHEREx-D1": 0.95,
        "SPHEREx-D2": 1.45,
        "SPHEREx-D3": 2.10,
        "SPHEREx-D4": 3.10,
        "SPHEREx-D5": 4.10,
        "SPHEREx-D6": 4.70
    }
    wl_um = bandpass_wavelengths.get(bandpass)
    target_flux = float(rng.uniform(140.0, 220.0))

    for i in range(max_epochs):
        epoch_idx = i + 1
        mjd = base_mjd + i * epoch_interval_days
        delta_years = i * (epoch_interval_days / 365.25)

        # Target proper motion displacement
        # pm_ra is mas/yr -> arcsec in delta_years: pm_ra * delta_years / 1000
        # dx_pixels = (pm_ra_mas * delta_years / 1000) / pixel_scale_arcsec (note: RA increases to left in sky coordinates)
        dx_arcsec = (pm_ra * delta_years) / 1000.0
        dy_arcsec = (pm_dec * delta_years) / 1000.0

        target_x = center_x - (dx_arcsec / pixel_scale_arcsec)
        target_y = center_y + (dy_arcsec / pixel_scale_arcsec)

        # Construct frame: start with Zodiacal light background emission
        # SPHEREx observes in low-Earth orbit where Zodiacal light is 10-30 MJy/sr
        zodiacal_light = 120.0 + rng.normal(0, 1.5, (grid_size, grid_size))
        frame = zodiacal_light.copy()

        # Add background stars
        for sx, sy, sf in zip(bg_xs, bg_ys, bg_fluxes):
            star_profile = sf * np.exp(-0.5 * (((x_coords - sx) / psf_sigma_px)**2 + ((y_coords - sy) / psf_sigma_px)**2))
            frame += star_profile

        # Add target star/brown dwarf
        target_profile = target_flux * np.exp(-0.5 * (((x_coords - target_x) / psf_sigma_px)**2 + ((y_coords - target_y) / psf_sigma_px)**2))
        frame += target_profile

        # Add instrumental Poisson / Gaussian photon noise
        noise = rng.normal(0, 3.2, (grid_size, grid_size))
        frame += noise

        # Pipeline reduction step: ZODIACAL BACKGROUND SUBTRACTION (IMAGE - ZODI)
        # Zodi model estimated from local background median
        estimated_zodi = np.median(frame) - 2.0
        reduced_frame = frame - estimated_zodi

        _, sky_median, sky_std = sigma_clipped_stats(reduced_frame, sigma=3.0, maxiters=5)
        reduced_frame = reduced_frame - sky_median
        reduced_frame[reduced_frame < 3.0 * sky_std] = 0.0
        reduced_frame = np.clip(np.nan_to_num(reduced_frame, nan=0.0, posinf=0.0, neginf=0.0), 0.0, None)
        display_signal = np.log1p(reduced_frame * 0.45)
        display_signals.append(display_signal)

        # Date string from MJD
        t_epoch = Time(mjd, format='mjd')
        date_str = f"SIM E{epoch_idx}"

        epochs.append({
            "epoch_index": epoch_idx,
            "mjd": round(float(mjd), 2),
            "date_str": date_str,
            "wavelength_um": round(float(wl_um), 2) if wl_um is not None else None,
            "bandpass": bandpass,
            "size": grid_size,
            "target_pixel_pos": [round(float(target_x), 2), round(float(target_y), 2)],
            "pixels_u8": [],
            "_display_signal": display_signal,
        })
        data_products.append({
            "epoch_index": epoch_idx,
            "product_type": "synthetic_image",
            "source": "SPHEREx Visualizer simulator",
            "bandpass": bandpass,
            "wavelength_um": round(float(wl_um), 2) if wl_um is not None else None,
            "mjd": round(float(mjd), 2),
            "file_name": None,
            "file_uri": None,
            "image_hdu": None,
            "hdu_index": None,
            "processing": "Generated synthetic scene with modeled point sources, PSF, background, noise, and proper-motion displacement.",
            "archive_note": target_info.get("retrieval_note", "No FITS file was imported for this simulated epoch."),
        })

    shared_peak = max((float(np.max(signal)) for signal in display_signals), default=0.0)
    for epoch in epochs:
        signal = epoch.pop("_display_signal")
        epoch["pixels_u8"] = (
            np.clip(signal / shared_peak * 255.0, 0, 255).astype(np.uint8).tolist()
            if shared_peak > 0 else np.zeros((grid_size, grid_size), dtype=np.uint8).tolist()
        )

    return {
        "target_id": target_info.get("target_id", "custom_target"),
        "name": target_info.get("name", "Unknown Field"),
        "ra_deg": round(float(ra), 6),
        "dec_deg": round(float(dec), 6),
        "pm_ra_mas_yr": round(pm_ra, 2) if target_info.get("proper_motion_known") else None,
        "pm_dec_mas_yr": round(pm_dec, 2) if target_info.get("proper_motion_known") else None,
        "total_pm_arcsec_yr": round(float(target_info.get("total_pm_arcsec_yr") or 0.0), 3) if target_info.get("proper_motion_known") else None,
        "proper_motion_known": bool(target_info.get("proper_motion_known", False)),
        "spectral_type": target_info.get("spectral_type", "Unknown"),
        "object_type": target_info.get("object_type"),
        "description": target_info.get("description", ""),
        "source": target_info.get("source", "simulated"),
        "data_source": "simulated",
        "size_deg": size_deg,
        "pixel_scale_arcsec": round(float(pixel_scale_arcsec), 3),
        "epochs": epochs,
        "spectral_points": [],
        "spectrum_is_synthetic": False,
        "data_manifest": data_products,
        "retrieval_note": target_info.get("retrieval_note", "Synthetic demonstration data; no live archive files were imported."),
    }


def _process_irsa_candidate(
    row: Any,
    epoch_index: int,
    ra: float,
    dec: float,
    bandpass: str,
    grid_size: int,
    deadline: Optional[float] = None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Download and normalize one archive cutout, returning its UI epoch and provenance."""
    def get_value(key, default=None):
        try:
            return row[key]
        except (KeyError, TypeError, IndexError):
            return getattr(row, key, default)

    uri = str(get_value("uri", ""))
    mjd = float(get_value("time_bounds_lower", 61000.0))
    wavelength_um = None
    local_fits_path = None
    for attempt in range(2):
        try:
            remaining = deadline - time.monotonic() if deadline is not None else IRSA_FITS_READ_TIMEOUT_SECONDS
            if remaining <= 0:
                raise TimeoutError("IRSA epoch download budget expired.")
            # Astropy's file cache lets repeated archive lookups reuse a successful
            # FITS download. IRSA notes that large MEF reads can exceed short defaults.
            local_fits_path = download_file(
                uri,
                cache=True,
                show_progress=False,
                timeout=min(IRSA_FITS_READ_TIMEOUT_SECONDS, remaining),
            )
            break
        except (TimeoutError, urllib.error.URLError, http.client.IncompleteRead,
                http.client.RemoteDisconnected) as error:
            status_code = error.code if isinstance(error, urllib.error.HTTPError) else 0
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            should_retry = attempt == 0 and (
                status_code == 0 or status_code in {408, 429} or status_code >= 500
            ) and (deadline is None or time.monotonic() < deadline)
            if not should_retry:
                raise
            time.sleep(0.75)
    if local_fits_path is None:
        raise RuntimeError("Archive FITS download did not return a response.")
    with fits.open(local_fits_path, memmap=False) as hdul:
        processing_version = str(hdul[0].header.get("VERSION", ""))
        image_hdu = next(
            (hdu for hdu in hdul[1:] if hdu.name.upper().startswith("IMAGE") and hdu.data is not None),
            None,
        )
        if image_hdu is None:
            raise ValueError("FITS file has no populated IMAGE extension.")
        image = np.asarray(image_hdu.data, dtype=np.float32).squeeze()
        if image.ndim != 2 or not np.isfinite(image).any():
            raise ValueError("IMAGE extension must contain a finite 2D image.")

        flags_hdu = next(
            (hdu for hdu in hdul[1:] if hdu.name.upper().startswith("FLAGS") and hdu.data is not None),
            None,
        )
        variance_hdu = next(
            (hdu for hdu in hdul[1:] if hdu.name.upper().startswith(("VARIANCE", "VAR")) and hdu.data is not None),
            None,
        )
        flags = np.asarray(flags_hdu.data).squeeze() if flags_hdu else None
        variance = np.asarray(variance_hdu.data, dtype=np.float32).squeeze() if variance_hdu else None
        invalid_pixels = ~np.isfinite(image)
        flag_counts = {}
        if flags is not None and flags.shape == image.shape:
            flags = np.asarray(flags, dtype=np.uint64)
            nonzero_flags = flags != 0
            bad_flag_mask = 0
            bad_flag_terms = ("TRANSIENT", "OVERFLOW", "ERROR", "NONFUNC", "DICHROIC", "MISSING", "HOT", "COSMIC", "SATURAT")
            for key, value in flags_hdu.header.items():
                key_upper = str(key).upper()
                if not key_upper.startswith("MP_"):
                    continue
                flag_name = key_upper[3:]
                bit_index = int(value)
                bit = 1 << bit_index
                count = int(np.count_nonzero(flags & bit))
                if count:
                    flag_counts[flag_name] = count
                if any(term in flag_name for term in bad_flag_terms):
                    bad_flag_mask |= bit
            if bad_flag_mask:
                invalid_pixels |= (flags & bad_flag_mask) != 0

        zodi_hdu = next(
            (hdu for hdu in hdul[1:] if hdu.name.upper().startswith("ZODI") and hdu.data is not None),
            None,
        )
        zodi = np.asarray(zodi_hdu.data, dtype=np.float32).squeeze() if zodi_hdu else None
        if zodi is not None and zodi.shape == image.shape:
            residual = image - zodi
            background_method = f"IMAGE − {zodi_hdu.name} model"
        else:
            residual = image
            background_method = "IMAGE minus sigma-clipped median sky background"

        spatial_wcs = None
        spectral_wcs = None
        target_pixel = None
        target = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs")
        try:
            spatial_wcs = WCS(image_hdu.header, fobj=hdul)
            celestial_wcs = spatial_wcs.celestial if spatial_wcs.has_celestial else spatial_wcs
            pixel_x, pixel_y = celestial_wcs.world_to_pixel(target)
            if np.isfinite(pixel_x) and np.isfinite(pixel_y):
                target_pixel = [float(pixel_x), float(pixel_y)]
        except Exception:
            spatial_wcs = None

        # The alternate WCS can encode wavelength on a 2D plane or across a
        # higher-dimensional detector solution. Extract the axis whose physical
        # type/unit is spectral, convert frequencies through spectral equivalencies.
        try:
            spectral_wcs = WCS(image_hdu.header, fobj=hdul, key="W")
            pixel_values = [
                float(spectral_wcs.wcs.crpix[index] - 1) if index < len(spectral_wcs.wcs.crpix) else 0.0
                for index in range(spectral_wcs.pixel_n_dim)
            ]
            if spectral_wcs.pixel_n_dim >= 2:
                reference_position = target_pixel or [(image.shape[1] - 1) / 2, (image.shape[0] - 1) / 2]
                pixel_values[0], pixel_values[1] = map(float, reference_position)
            if spectral_wcs.pixel_n_dim == len(pixel_values):
                world_values = spectral_wcs.pixel_to_world_values(*pixel_values)
                if not isinstance(world_values, tuple):
                    world_values = (world_values,)
                physical_types = list(spectral_wcs.world_axis_physical_types or [])
                units = list(spectral_wcs.world_axis_units or [])
                for index, value in enumerate(world_values):
                    if np.size(value) != 1:
                        continue
                    physical_type = physical_types[index] if index < len(physical_types) else ""
                    unit_text = units[index] if index < len(units) else ""
                    if physical_type and not str(physical_type).startswith("em."):
                        continue
                    try:
                        quantity = float(np.asarray(value).reshape(-1)[0]) * u.Unit(unit_text)
                        wavelength_um = float(quantity.to_value(u.um, equivalencies=u.spectral()))
                        if np.isfinite(wavelength_um) and wavelength_um > 0:
                            break
                    except Exception:
                        continue
        except Exception:
            spectral_wcs = None

        _, sky_median, sky_std = sigma_clipped_stats(
            residual,
            mask=invalid_pixels,
            sigma=3.0,
            maxiters=5,
        )
        if not np.isfinite(sky_median) or not np.isfinite(sky_std):
            raise ValueError("No unmasked finite pixels remain for sky-background estimation.")
        background_subtracted = np.nan_to_num(residual - sky_median, nan=0.0, posinf=0.0, neginf=0.0)
        cleaned = background_subtracted.copy()
        cleaned[cleaned < 3.0 * sky_std] = 0.0
        cleaned[invalid_pixels] = 0.0
        cleaned = np.clip(cleaned, 0.0, None)
        stretched = np.log1p(cleaned)
        if not np.isfinite(stretched).any() or float(np.max(stretched)) <= 0:
            raise ValueError("No positive signal remains after background subtraction.")
        original_shape = stretched.shape
        if stretched.shape != (grid_size, grid_size):
            from scipy.ndimage import gaussian_filter, zoom
            factors = (grid_size / stretched.shape[0], grid_size / stretched.shape[1])
            if any(factor < 1 for factor in factors):
                blur_sigma = tuple(max(0.0, (1.0 / factor - 1.0) * 0.45) for factor in factors)
                stretched = gaussian_filter(stretched, sigma=blur_sigma, mode="nearest")
            stretched = zoom(stretched, factors, order=3, prefilter=True).astype(np.float32)
        if stretched.shape != (grid_size, grid_size):
            raise ValueError(f"Resampling produced unexpected shape {stretched.shape}.")

        resized_target_pixel = None
        spectral_point = None
        flux_unit = image_hdu.header.get("BUNIT")
        if target_pixel is not None and -0.5 <= target_pixel[0] < image.shape[1] - 0.5 and -0.5 <= target_pixel[1] < image.shape[0] - 0.5:
            source_x = int(np.clip(round(target_pixel[0]), 0, image.shape[1] - 1))
            source_y = int(np.clip(round(target_pixel[1]), 0, image.shape[0] - 1))
            resized_target_pixel = [
                (target_pixel[0] + 0.5) * grid_size / image.shape[1] - 0.5,
                (target_pixel[1] + 0.5) * grid_size / image.shape[0] - 0.5,
            ]
            if wavelength_um is not None and not invalid_pixels[source_y, source_x]:
                point = {
                    "wavelength_um": wavelength_um,
                    "flux": float(background_subtracted[source_y, source_x]),
                    "flux_unit": str(flux_unit) if flux_unit else None,
                    "epoch_index": epoch_index,
                    "mjd": round(mjd, 2),
                    "bandpass": bandpass,
                    "measurement_method": "background-subtracted target pixel",
                    "detection_snr": None,
                }
                if variance is not None and variance.shape == image.shape:
                    point["uncertainty"] = float(np.sqrt(max(float(variance[source_y, source_x]), 0.0)))
                else:
                    point["uncertainty"] = float(sky_std)
                if point["uncertainty"] > 0:
                    point["detection_snr"] = point["flux"] / point["uncertainty"]
                spectral_point = point

        def serialize_wcs(wcs):
            if wcs is None:
                return None
            return {key: value for key, value in wcs.to_header(relax=True).items()}

        target_flags = int(flags[source_y, source_x]) if flags is not None and resized_target_pixel is not None and flags.shape == image.shape else None

        time_value = Time(mjd, format="mjd")
        epoch = {
            "epoch_index": epoch_index,
            "mjd": round(mjd, 2),
            "date_str": str(time_value.to_datetime().strftime("%Y-%m-%d")),
            "wavelength_um": round(wavelength_um, 3) if wavelength_um is not None else None,
            "bandpass": bandpass,
            "size": grid_size,
            "target_pixel_pos": resized_target_pixel,
            "pixels_u8": [],
            "_display_signal": stretched,
        }
        parsed_uri = urlparse(uri)
        uri_path = parsed_uri.path.lower()
        data_release = "DR1" if "/dr1/" in uri_path else "QR3" if "/qr3/" in uri_path else "Unknown"
        product = {
            "epoch_index": epoch_index,
            "product_type": "archive_cutout",
            "source": "Caltech/IPAC IRSA SPHEREx archive",
            "file_name": os.path.basename(parsed_uri.path) or "SPHEREx FITS cutout",
            "file_uri": uri,
            "data_release": data_release,
            "image_hdu": image_hdu.name,
            "hdu_index": next(index for index, hdu in enumerate(hdul) if hdu is image_hdu),
            "available_hdus": [hdu.name for hdu in hdul],
            "processing_version": processing_version or None,
            "quality_flag_counts": flag_counts,
            "nonzero_quality_pixels": int(np.count_nonzero(flags)) if flags is not None and flags.shape == image.shape else None,
            "target_quality_flags": target_flags,
            "background_median": float(sky_median),
            "background_sigma": float(sky_std),
            "background_method": background_method,
            "processing": f"{original_shape[1]}×{original_shape[0]} IMAGE plane; quality-masked, sigma-clipped background-subtracted at 3σ, log-stretched, shared-scale normalized, resampled to {grid_size}×{grid_size}.",
            "wavelength_um": round(wavelength_um, 3) if wavelength_um is not None else None,
            "mjd": round(mjd, 2),
            "bandpass": bandpass,
            "flux_unit": str(flux_unit) if flux_unit else None,
            "spatial_wcs": serialize_wcs(spatial_wcs),
            "spectral_wcs": serialize_wcs(spectral_wcs),
            "spectral_point": spectral_point,
        }
        return epoch, product


def scrape_spherex_target(
    coord: Union[SkyCoord, Dict[str, Any]],
    size_deg: float = 0.05,
    bandpass: str = "SPHEREx-D2",
    max_epochs: int = 3,
    grid_size: int = 128
) -> Dict[str, Any]:
    """
    Query Caltech/IPAC IRSA TAP joining spherex.artifact and spherex.plane ordered by time_bounds_lower.
    Filter to 1 clean frame per ~6-month epoch (>= 150 days apart).
    If IRSA has records, downloads cutouts, subtracts zodiacal background (IMAGE - ZODI),
    clips negatives, applies np.log1p stretch, normalizes to 0..255 uint8, resamples to grid_size,
    and extracts central_wavelength_um via WCS(header, fobj=hdul, key="W").
    If archive records are unavailable or unusable, a clearly labeled generic simulation is returned.
    """
    if isinstance(coord, SkyCoord):
        ra = float(coord.ra.deg)
        dec = float(coord.dec.deg)
        target_info = {
            "target_id": "sky_coord",
            "name": f"Coordinates ({ra:.4f}, {dec:.4f})",
            "ra_deg": ra,
            "dec_deg": dec,
            "object_type": "generic_star"
        }
    else:
        ra = float(coord["ra_deg"])
        dec = float(coord["dec_deg"])
        target_info = coord

    print(f"[*] Querying IRSA TAP for RA={ra:.5f}°, Dec={dec:.5f}°, size={size_deg}°...")

    try:
        # Query SPHEREx metadata and request an IRSA cutout URL for this position.
        valid_bandpasses = [f"SPHEREx-D{i}" for i in range(1, 7)]
        bandpass_filter = (
            "p.energy_bandpassname IN (" + ", ".join(f"'{value}'" for value in valid_bandpasses) + ")"
            if bandpass == "ALL" else f"p.energy_bandpassname = '{bandpass}'"
        )
        query = f"""
        SELECT
            'https://irsa.ipac.caltech.edu/' || a.uri || '?center={ra},{dec}d&size={size_deg}' AS uri,
            p.time_bounds_lower,
            p.energy_bandpassname AS bandpass
        FROM spherex.artifact AS a
        JOIN spherex.plane AS p ON a.planeid = p.planeid
        WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
          AND {bandpass_filter}
          AND (a.uri LIKE '%/dr1/%' OR a.uri LIKE '%/qr3/%')
        ORDER BY p.time_bounds_lower
        """
        tap_results = None
        _configure_irsa_tap_timeout()
        for attempt in range(3):
            try:
                tap_results = Irsa.query_tap(query)
                break
            except Exception as tap_error:
                if attempt == 2:
                    raise
                print(f"[*] IRSA TAP attempt {attempt + 1} failed ({type(tap_error).__name__}); retrying shortly...")
                time.sleep(0.75 * (attempt + 1))

        if tap_results and len(tap_results) > 0:
            print(f"[+] Found {len(tap_results)} records in IRSA TAP! Processing multi-epoch cutouts...")
            # Group nearby frames into survey epochs; each epoch has several file
            # candidates so one broken FITS link does not discard that observation.
            candidate_groups = []
            group_start_mjd = None
            for row in tap_results:
                try:
                    mjd = float(row["time_bounds_lower"])
                except (KeyError, TypeError, IndexError):
                    mjd = float(getattr(row, "time_bounds_lower", 0.0))
                if group_start_mjd is None or mjd - group_start_mjd >= 150.0:
                    candidate_groups.append([row])
                    group_start_mjd = mjd
                else:
                    candidate_groups[-1].append(row)
            # Keep the most recent distinct survey epochs. IRSA returns old to
            # new here; taking the first N quietly made the UI appear frozen.
            candidate_groups = candidate_groups[-max_epochs:]
            epochs = []
            data_products = []
            candidate_failures = []
            def row_value(row, key, default=None):
                try:
                    return row[key]
                except (KeyError, TypeError, IndexError):
                    return getattr(row, key, default)

            def process_epoch_group(group_index: int, candidate_rows: List[Any]):
                failures = []
                deadline = time.monotonic() + IRSA_EPOCH_DOWNLOAD_BUDGET_SECONDS
                by_band = {}
                for row in candidate_rows:
                    actual_band = str(row_value(row, "bandpass", bandpass))
                    by_band.setdefault(actual_band, []).append(row)
                requested_bands = valid_bandpasses if bandpass == "ALL" else [bandpass]
                epochs_for_group, products_for_group = [], []
                for requested_band in requested_bands:
                    for row in by_band.get(requested_band, [])[:4]:
                        if time.monotonic() >= deadline:
                            failures.append("epoch download time budget expired")
                            break
                        try:
                            epoch, product = _process_irsa_candidate(
                                row=row,
                                epoch_index=group_index,
                                ra=ra,
                                dec=dec,
                                bandpass=requested_band,
                                grid_size=grid_size,
                                deadline=deadline,
                            )
                            epoch["bandpass"] = requested_band
                            epochs_for_group.append(epoch)
                            products_for_group.append(product)
                            break
                        except Exception as fits_err:
                            uri = str(row_value(row, "uri", ""))
                            failures.append(f"{os.path.basename(urlparse(uri).path)}: {fits_err}")
                            print(f"[-] Error opening FITS at {uri}: {fits_err}")
                if not epochs_for_group:
                    return None, [], failures
                display_choice = next(
                    (index for index, product in enumerate(products_for_group) if product.get("bandpass") == "SPHEREx-D2"),
                    0,
                )
                display_epoch = epochs_for_group[display_choice]
                for index, epoch in enumerate(epochs_for_group):
                    if index != display_choice:
                        epoch.pop("_display_signal", None)
                return display_epoch, products_for_group, failures

            if candidate_groups:
                with ThreadPoolExecutor(max_workers=min(3, len(candidate_groups))) as executor:
                    futures = [
                        executor.submit(process_epoch_group, index, group)
                        for index, group in enumerate(candidate_groups, start=1)
                    ]
                    for future in futures:
                        epoch, products, failures = future.result()
                        candidate_failures.extend(failures)
                        if epoch is not None:
                            next_index = len(epochs) + 1
                            epoch["epoch_index"] = next_index
                            epochs.append(epoch)
                            for product in products:
                                product["epoch_index"] = next_index
                                data_products.append(product)

            if len(epochs) > 0:
                shared_peak = max((float(np.max(epoch["_display_signal"])) for epoch in epochs), default=0.0)
                spectral_points = []
                for epoch in epochs:
                    display_signal = epoch.pop("_display_signal")
                    epoch["pixels_u8"] = (
                        np.clip(display_signal / shared_peak * 255.0, 0, 255).astype(np.uint8).tolist()
                        if shared_peak > 0 else np.zeros((grid_size, grid_size), dtype=np.uint8).tolist()
                    )
                for product in data_products:
                    point = product.pop("spectral_point", None)
                    if point is not None:
                        point["epoch_index"] = product["epoch_index"]
                        point["series_id"] = product.get("bandpass")
                        spectral_points.append(point)
                return {
                    "target_id": target_info.get("target_id", "irsa_target"),
                    "name": target_info.get("name", "IRSA Target"),
                    "ra_deg": ra,
                    "dec_deg": dec,
                    "pm_ra_mas_yr": target_info.get("pm_ra_mas_yr", 0.0),
                    "pm_dec_mas_yr": target_info.get("pm_dec_mas_yr", 0.0),
                    "total_pm_arcsec_yr": target_info.get("total_pm_arcsec_yr", 0.0),
                    "proper_motion_known": bool(target_info.get("proper_motion_known", False)),
                    "spectral_type": target_info.get("spectral_type", "Unknown"),
                    "object_type": target_info.get("object_type", "generic_star"),
                    "description": target_info.get("description", "Retrieved directly from NASA/IPAC IRSA TAP"),
                    "source": "irsa_live_tap",
                    "data_source": "irsa_live_tap",
                    "spectrum_is_synthetic": False,
                    "size_deg": size_deg,
                    "pixel_scale_arcsec": round(size_deg * 3600.0 / grid_size, 4),
                    "epochs": epochs,
                    "spectral_points": spectral_points,
                    "data_manifest": data_products,
                    "retrieval_note": (
                        f"Processed {len(epochs)} archive epoch(s) from IRSA. "
                        + (f"{len(candidate_failures)} alternate FITS candidate(s) failed before fallback within their epoch groups. " if candidate_failures else "")
                        + f"Extracted {len(spectral_points)} target-position spectral measurement(s) from IMAGE/WCS data."
                    ),
                }
            if candidate_failures:
                target_info = dict(target_info)
                target_info["retrieval_note"] = (
                    "IRSA returned records, but FITS candidates failed processing: "
                    + "; ".join(candidate_failures[:3])
                )
    except Exception as e:
        target_info = dict(target_info)
        target_info["retrieval_note"] = f"IRSA request failed: {type(e).__name__}: {e}"
        print(f"[*] IRSA TAP request failed ({type(e).__name__}: {e}); using labeled fallback...")

    # Fallback scenes are clearly labeled and never presented as archive measurements.
    print(f"[*] Utilizing SPHEREx scene simulator for '{target_info.get('name')}'...")
    return synthesize_spherex_cutouts(target_info, size_deg=size_deg, bandpass=bandpass, max_epochs=max_epochs, grid_size=grid_size)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/fetch_all_targets.py <object-name-or-coordinates>")
    query = " ".join(sys.argv[1:])
    resolved = resolve_any_input(query)
    result = scrape_spherex_target(resolved)
    print(json.dumps(result, indent=2))

