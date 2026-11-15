"""Offline regression checks for target resolution, IRSA fallback, and cache behavior."""

import io
import json
import os
import tempfile
import time
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import requests
from astropy.io import fits

import fetch_all_targets
import server


class BackendRegressionTests(unittest.TestCase):
    def test_resolver_rejects_nonsense_and_assistant_marks_unknown_values(self):
        coordinate = fetch_all_targets.resolve_any_input("42.125, -17.75", allow_geographic=False)
        self.assertFalse(coordinate["proper_motion_known"])
        self.assertAlmostEqual(coordinate["ra_deg"], 42.125)
        self.assertAlmostEqual(coordinate["dec_deg"], -17.75)

        galactic = fetch_all_targets.resolve_any_input("galactic|12.3, -4.5", allow_geographic=False)
        self.assertEqual(galactic["input_frame"], "galactic")
        self.assertGreaterEqual(galactic["ra_deg"], 0)
        self.assertTrue(-90 <= galactic["dec_deg"] <= 90)

        with patch.object(fetch_all_targets.SkyCoord, "from_name", side_effect=ValueError("not found")):
            with self.assertRaisesRegex(ValueError, "recognized astronomical name"):
                fetch_all_targets.resolve_any_input("qzvpt", allow_geographic=False)

        summary = server.compact_target_summary({
            "name": "Test field",
            "ra_deg": 1.0,
            "dec_deg": 2.0,
            "proper_motion": 0.0,
            "proper_motion_known": False,
            "wavelength_um": 1.45,
            "epoch_count": 2,
            "data_source": "simulated",
            "spectrum_is_synthetic": True,
        })
        answer = server._local_analysis("What does 4.26 microns mean for its spectrum and motion?", summary)
        self.assertIn("4.26 µm", answer["reply"])
        self.assertIn("Proper motion is not available", answer["reply"])
        self.assertIn("No measured spectrum is available", answer["reply"])

    def test_earth_location_reports_geocoder_timeout(self):
        with patch.object(fetch_all_targets.requests, "get", side_effect=requests.Timeout):
            with self.assertRaisesRegex(ValueError, "location service timed out"):
                fetch_all_targets.resolve_any_input(
                    "Some District", allow_coordinates=False,
                    allow_astronomical=False, allow_geographic=True,
                )

    def test_scraper_tries_alternate_fits_and_records_hdu_provenance(self):
        image = np.ones((128, 128), dtype=np.float32)
        image[62:66, 62:66] = 20
        fits_stream = io.BytesIO()
        primary = fits.PrimaryHDU()
        primary.header["VERSION"] = "qr3-test-v7"
        fits.HDUList([
            primary,
            fits.ImageHDU(data=image, name="IMAGE"),
            fits.ImageHDU(data=np.ones_like(image), name="ZODI"),
        ]).writeto(fits_stream)
        valid_fits = fits_stream.getvalue()

        rows = [
            {"uri": "https://archive.example/dr1/bad.fits", "time_bounds_lower": 60000.0},
            {"uri": "https://archive.example/dr1/epoch1.fits", "time_bounds_lower": 60010.0},
            {"uri": "https://archive.example/qr3/epoch2.fits", "time_bounds_lower": 60200.0},
        ]

        query_text = []

        def query_tap(query):
            query_text.append(query)
            return rows

        def download(uri, **kwargs):
            self.assertTrue(kwargs["cache"])
            self.assertLessEqual(kwargs["timeout"], fetch_all_targets.IRSA_FITS_READ_TIMEOUT_SECONDS)
            self.assertGreater(kwargs["timeout"], fetch_all_targets.IRSA_FITS_READ_TIMEOUT_SECONDS - 0.1)
            if "bad.fits" in uri:
                error = urllib.error.HTTPError(uri, 503, "temporary archive error", {}, None)
                error.close()
                raise error
            return fits_path

        target = fetch_all_targets.resolve_any_input("269.452083, 4.693389", allow_geographic=False)
        workspace_temp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "work"))
        os.makedirs(workspace_temp, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="spherex-archive-test-", dir=workspace_temp) as fits_dir:
            fits_path = os.path.join(fits_dir, "valid.fits")
            with open(fits_path, "wb") as fits_file:
                fits_file.write(valid_fits)
            with patch.object(fetch_all_targets.Irsa, "query_tap", side_effect=query_tap), \
                    patch.object(fetch_all_targets, "download_file", side_effect=download), \
                    patch.object(fetch_all_targets.time, "sleep"):
                result = fetch_all_targets.scrape_spherex_target(target, max_epochs=2, grid_size=128)

        self.assertEqual(result["data_source"], "irsa_live_tap")
        self.assertNotIn("TOP 200", query_text[0].upper())
        self.assertIn("%/dr1/%", query_text[0])
        self.assertIn("%/qr3/%", query_text[0])
        self.assertEqual(len(result["epochs"]), 2)
        self.assertEqual(len(result["data_manifest"]), 2)
        self.assertEqual(result["data_manifest"][0]["image_hdu"], "IMAGE")
        self.assertEqual(result["data_manifest"][0]["hdu_index"], 1)
        self.assertEqual(result["data_manifest"][0]["processing_version"], "qr3-test-v7")
        self.assertEqual(result["data_manifest"][0]["data_release"], "DR1")
        self.assertIn("ZODI", result["data_manifest"][0]["background_method"])
        self.assertIn("alternate FITS candidate", result["retrieval_note"])

    def test_cache_expires_simulation_and_preserves_last_live_product(self):
        workspace_temp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "work"))
        os.makedirs(workspace_temp, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="spherex-cache-", dir=workspace_temp) as cache_dir:
            previous_cache_dir = server.LIVE_CACHE_DIR
            server.LIVE_CACHE_DIR = cache_dir
            current_source = {"data_source": "irsa_live_tap", "source": "irsa_live_tap"}
            scrape_calls = []

            def fake_scrape(coord, **kwargs):
                scrape_calls.append(current_source["data_source"])
                return {
                    **current_source,
                    "target_id": "custom_coord",
                    "name": "Test coordinate",
                    "ra_deg": 1.0,
                    "dec_deg": 2.0,
                    "proper_motion_known": False,
                    "epochs": [{"epoch_index": 1, "pixels_u8": [[0]], "date_str": "2026-01-01"}],
                    "spectral_points": [],
                }

            try:
                with patch.object(server, "scrape_spherex_target", side_effect=fake_scrape):
                    live = server.get_sky_cutout("1, 2", 0.05, "SPHEREx-D2", 1, "sky", True)
                    self.assertEqual(live["metadata"]["data_source"], "irsa_live_tap")

                    current_source.update(data_source="simulated", source="simulated")
                    fallback = server.get_sky_cutout("1, 2", 0.05, "SPHEREx-D2", 1, "sky", True)
                    self.assertEqual(fallback["metadata"]["data_source"], "irsa_live_tap")
                    self.assertEqual(fallback["metadata"]["cache_status"], "stale_archive_fallback")
                    cached_live = server.get_sky_cutout("1, 2", 0.05, "SPHEREx-D2", 1, "sky", False)
                    self.assertEqual(cached_live["metadata"]["data_source"], "irsa_live_tap")
                    self.assertEqual(cached_live["metadata"]["cache_status"], "cache_hit")

                    server.get_sky_cutout("3, 4", 0.05, "SPHEREx-D2", 1, "sky", False)
                    sim_cache_path = next(
                        path for path in Path(cache_dir).glob("*.json")
                        if json.loads(path.read_text(encoding="utf-8"))["coordinates"]["ra_deg"] == 3.0
                    )
                    record = json.loads(sim_cache_path.read_text(encoding="utf-8"))
                    record["_cache"]["created_at"] = time.time() - server.SIMULATED_CACHE_TTL_SECONDS - 1
                    sim_cache_path.write_text(json.dumps(record), encoding="utf-8")
                    calls_before_expiry = len(scrape_calls)
                    server.get_sky_cutout("3, 4", 0.05, "SPHEREx-D2", 1, "sky", False)
                    self.assertEqual(len(scrape_calls), calls_before_expiry + 1)
            finally:
                server.LIVE_CACHE_DIR = previous_cache_dir


if __name__ == "__main__":
    unittest.main(verbosity=2)
