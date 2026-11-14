"""
Unit Test Suite for SphereX Astrometric & Math Engine
Team Pioneer Matrix - NASA Space Apps Challenge 2026
"""

import os
import sys
import json
import numpy as np

# Ensure scripts directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from astro_tools import (
    parse_ra_to_deg,
    parse_dec_to_deg,
    deg_to_sexagesimal,
    project_proper_motion,
    compute_image_difference,
    generate_spherex_spectral_profile
)


def test_coordinate_parsing_and_roundtrips():
    print("[TEST 1/4] Testing Coordinate Parsing & Roundtrips...")

    # 1. Decimal strings and floats
    assert abs(parse_ra_to_deg("269.452083") - 269.452083) < 1e-5
    assert abs(parse_dec_to_deg("4.693389") - 4.693389) < 1e-5
    assert abs(parse_dec_to_deg("-7.245147") - (-7.245147)) < 1e-5

    # 2. Sexagesimal string formats
    ra_barnard = "17h 57m 48.50s"
    dec_barnard = "+04° 41′ 36.2″"
    ra_deg = parse_ra_to_deg(ra_barnard)
    dec_deg = parse_dec_to_deg(dec_barnard)

    assert abs(ra_deg - 269.452083) < 0.001, f"RA parsed: {ra_deg}"
    assert abs(dec_deg - 4.693389) < 0.001, f"Dec parsed: {dec_deg}"

    # Roundtrip test
    ra_hms_out, dec_dms_out = deg_to_sexagesimal(ra_deg, dec_deg)
    ra_deg_roundtrip = parse_ra_to_deg(ra_hms_out)
    dec_deg_roundtrip = parse_dec_to_deg(dec_dms_out)

    assert abs(ra_deg - ra_deg_roundtrip) < 0.0001
    assert abs(dec_deg - dec_deg_roundtrip) < 0.0001

    # WISE 0855 (-07° 14′ 42.5″)
    dec_wise = "-07° 14′ 42.5″"
    dec_wise_deg = parse_dec_to_deg(dec_wise)
    assert abs(dec_wise_deg - (-7.245139)) < 0.001

    # Colon separated format
    assert abs(parse_ra_to_deg("17:57:48.50") - 269.452083) < 0.001
    assert abs(parse_dec_to_deg("+04:41:36.2") - 4.693389) < 0.001

    print("  [PASS] Decimal and Sexagesimal coordinate parsing passed.")
    print("  [PASS] Coordinate roundtrip tests passed.")


def test_six_month_proper_motion_shifts():
    print("[TEST 2/4] Testing 6-Month Proper Motion Shifts for Benchmark Targets...")

    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "targets.json")
    with open(config_path, "r", encoding="utf-8") as f:
        targets_data = json.load(f)

    benchmark_targets = targets_data["benchmark_targets"]
    assert len(benchmark_targets) == 5, f"Expected 5 benchmark targets, found {len(benchmark_targets)}"

    # 6 months = 0.5 years
    delta_years = 0.5

    for target in benchmark_targets:
        t_id = target["id"]
        ra = target["ra_deg"]
        dec = target["dec_deg"]
        pm_ra = target["pm_ra_mas_yr"]
        pm_dec = target["pm_dec_mas_yr"]
        expected_total_pm = target["total_pm_arcsec_yr"]

        new_ra, new_dec, shift_arcsec = project_proper_motion(ra, dec, pm_ra, pm_dec, delta_years)

        # Expected 6-month shift should be total_pm_arcsec_yr * 0.5
        expected_shift_arcsec = expected_total_pm * delta_years
        assert abs(shift_arcsec - expected_shift_arcsec) < 0.05, (
            f"Target {t_id}: Expected shift {expected_shift_arcsec:.3f}\", got {shift_arcsec:.3f}\""
        )

        # RA must stay within [0, 360) and Dec within [-90, +90]
        assert 0.0 <= new_ra < 360.0
        assert -90.0 <= new_dec <= 90.0

        print(f"  [PASS] {target['name']}: 6-month shift = {shift_arcsec:.3f}\" (expected {expected_shift_arcsec:.3f}\")")


def test_image_difference_dipole_behavior():
    print("[TEST 3/4] Testing Image Differencing and Dipole Detection Engine...")

    size = 128
    epoch1 = np.full((size, size), 20.0, dtype=np.float32)
    epoch2 = np.full((size, size), 20.0, dtype=np.float32)

    # Add 4 static stars (should cancel out in diff)
    static_stars = [(30, 30), (30, 90), (90, 30), (90, 90)]
    for sx, sy in static_stars:
        epoch1[sy-2:sy+3, sx-2:sx+3] += 120.0
        epoch2[sy-2:sy+3, sx-2:sx+3] += 120.0

    # Add a moving star:
    # At Epoch 1, star is at (x=60, y=64)
    # At Epoch 2, star moves to (x=68, y=64)
    epoch1[62:67, 58:63] += 180.0
    epoch2[62:67, 66:71] += 180.0

    res = compute_image_difference(epoch1, epoch2)

    assert res["is_dipole"] is True, "Expected moving star to produce a detected dipole signature"
    assert res["pos_count"] > 0, "Expected positive residual count > 0"
    assert res["neg_count"] > 0, "Expected negative residual count > 0"

    # Static stars should have diff ~ 0 (well below the 15 threshold)
    diff_arr = np.array(res["diff_matrix"])
    for sx, sy in static_stars:
        static_residual = np.max(np.abs(diff_arr[sy-2:sy+3, sx-2:sx+3]))
        assert static_residual < 1.0, f"Static star at ({sx}, {sy}) failed to cancel! Max residual: {static_residual}"

    # Verify dipole centers
    pos_x, pos_y = res["pos_center"]
    neg_x, neg_y = res["neg_center"]
    assert abs(pos_x - 68.0) < 1.5, f"Pos center X: {pos_x}"
    assert abs(neg_x - 60.0) < 1.5, f"Neg center X: {neg_x}"
    assert abs(pos_y - 64.0) < 1.5, f"Pos center Y: {pos_y}"

    print(f"  [PASS] Difference image cancelled static stars. Dipole detected: pos=({pos_x:.1f}, {pos_y:.1f}), neg=({neg_x:.1f}, {neg_y:.1f})")


def test_spherex_spectral_profiles():
    print("[TEST 4/4] Testing 102-Band SPHEREx Spectral Synthesis...")

    types_to_test = ["brown_dwarf", "red_dwarf", "t_tauri_variable", "mira_variable"]

    for obj_type in types_to_test:
        profile = generate_spherex_spectral_profile(obj_type)

        assert profile["bands_count"] == 102, f"Expected 102 bands, got {profile['bands_count']}"
        assert len(profile["wavelengths_um"]) == 102
        assert len(profile["flux"]) == 102
        assert len(profile["detector_arrays"]) == 102

        # Check wavelength range covers SPHEREx 0.75 - 5.0 µm
        assert abs(profile["wavelengths_um"][0] - 0.75) < 0.05
        assert abs(profile["wavelengths_um"][-1] - 5.00) < 0.05

        # Check all flux values are normalized between 0 and 100
        fluxes = profile["flux"]
        assert min(fluxes) >= 0.0
        assert max(fluxes) <= 100.0

        # Check molecular features
        features = profile["absorption_features"]
        assert len(features) >= 4, f"Object {obj_type} missing sufficient molecular features"

        # Verify brown dwarf specific features: H2O and CH4
        if obj_type == "brown_dwarf":
            mol_names = [f["molecule"] for f in features]
            assert any("CH4" in m for m in mol_names), "Brown dwarf missing CH4 methane signature"
            assert any("H2O" in m for m in mol_names), "Brown dwarf missing H2O signature"

        print(f"  [PASS] {obj_type}: 102 spectral bands synthesized (0.75 to 5.00 µm) with {len(features)} molecular diagnostic markers.")


def run_all_tests():
    print("=" * 60)
    print("SPHEREx Mission Visualizer Math Engine Test Suite")
    print("Team Pioneer Matrix - NASA Space Apps Challenge 2026")
    print("=" * 60)

    test_coordinate_parsing_and_roundtrips()
    test_six_month_proper_motion_shifts()
    test_image_difference_dipole_behavior()
    test_spherex_spectral_profiles()

    print("=" * 60)
    print("ALL 4 TEST MODULES PASSED SUCCESSFULLY! (100% Verified)")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
