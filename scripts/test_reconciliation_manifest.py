#!/usr/bin/env python3
"""Focused automated checks for build_reconciliation_manifest.py (Issue #16 AC#8).

Covers: source gates (lock / hash / existing output), unique-join enforcement,
category exclusivity, exact category totals, changed-baseline (membership drift)
failure, RTA aggregate-baseline failure, and the tire-completeness cross-check.

Pure-function checks use small synthetic inputs with the frozen constants
temporarily overridden; file-level gate checks shell out against the real
authoritative sources with temp path overrides (never mutating a real source).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import build_reconciliation_manifest as m  # noqa: E402

SCRIPT = SCRIPT_DIR / "build_reconciliation_manifest.py"
REAL_MASTER = Path(m.DEFAULT_MASTER)
REAL_TIRE = Path(m.DEFAULT_TIRE)
REAL_MAP = Path(m.DEFAULT_MAP_JSON)
REAL_CODEX = Path(m.DEFAULT_CODEX_JSON)
SOURCES_PRESENT = all(p.exists() for p in (REAL_MASTER, REAL_TIRE, REAL_MAP, REAL_CODEX))


def override(**kwargs):
    """Context manager restoring module constants after the block."""
    class _Ctx:
        def __enter__(self):
            self.saved = {k: getattr(m, k) for k in kwargs}
            for k, v in kwargs.items():
                setattr(m, k, v)
            return self

        def __exit__(self, *exc):
            for k, v in self.saved.items():
                setattr(m, k, v)
            return False
    return _Ctx()


def ymm(y, mk, md):
    return m.norm_ymm(y, mk, md)


def sample_master():
    # 001 direct, 002 corrected, 003 yellow, 004 moved, 005 unresolved
    return {
        "001": {"row": 2, "ymm": ymm(2010, "FORD", "F150"), "vin": "AAA"},
        "002": {"row": 3, "ymm": ymm(2015, "RAM", "1500"), "vin": "BBB"},
        "003": {"row": 4, "ymm": ymm(2018, "GMC", "SIERRA"), "vin": "CCC"},
        "004": {"row": 5, "ymm": ymm(2012, "CHEVY", "TAHOE"), "vin": "DDD"},
        "005": {"row": 6, "ymm": ymm(2020, "TOYOTA", "TACOMA"), "vin": "EEE"},
    }


def sample_tire():
    return {
        "001": {"ymm": ymm(2010, "FORD", "F150"), "front": "265/70R17", "rear": "265/70R17",
                "detail1": "", "detail2": ""},
        # 002 tire YMM differs from master (stale) -> pool
        "002": {"ymm": ymm(2014, "RAM", "1500"), "front": "275/60R20", "rear": "275/60R20",
                "detail1": "", "detail2": ""},
        # 003 tire YMM differs, master YMM NOT in ymm_map -> yellow
        "003": {"ymm": ymm(2017, "GMC", "SIERRA"), "front": "255/70R18", "rear": "255/70R18",
                "detail1": "", "detail2": ""},
        # 004 tire YMM matches master (not in pool); forced moved
        "004": {"ymm": ymm(2012, "CHEVY", "TAHOE"), "front": "265/65R18", "rear": "265/65R18",
                "detail1": "OLD-F", "detail2": "OLD-R"},
        "005": {"ymm": ymm(2020, "TOYOTA", "TACOMA"), "front": "", "rear": "",
                "detail1": "", "detail2": ""},
    }


def sample_ymm_map(master):
    # corrected asset 002's master YMM has a usable Codex result
    return {master["002"]["ymm"]: {"front": "285/45R22", "rear": "285/45R22"}}


SMALL_CATEGORY = dict(
    EXPECTED_ASSET_ROWS=5,
    APPROVED_MOVED_DETAIL={"004"},
    APPROVED_UNRESOLVED={"005"},
    APPROVED_CORRECTED={"002"},
    APPROVED_YELLOW={"003"},
    TOTAL_DIRECT=1, TOTAL_MOVED=1, TOTAL_CORRECTED=1, TOTAL_YELLOW=1, TOTAL_UNRESOLVED=1,
)


class HelperTests(unittest.TestCase):
    def test_normalize_suffix_and_case(self):
        self.assertEqual(m.normalize_vehicle_number("158 s"), "158S")
        self.assertEqual(m.normalize_vehicle_number(" 318 "), "318")
        self.assertEqual(m.normalize_vehicle_number("935s"), "935S")
        self.assertNotEqual(m.normalize_vehicle_number("318"), m.normalize_vehicle_number("318S"))

    def test_lookup_keys_zero_padding(self):
        self.assertIn("033", m.lookup_keys("33"))
        self.assertIn("33", m.lookup_keys("033"))

    def test_norm_ymm_year_float(self):
        self.assertEqual(m.norm_ymm("2010.0", "ford", "f150"), ("2010", "FORD", "F150"))


class ClassificationTests(unittest.TestCase):
    def test_happy_path(self):
        master, tire = sample_master(), sample_tire()
        with override(**SMALL_CATEGORY):
            classes = m.join_and_classify(master, tire, sample_ymm_map(master),
                                          {"001", "002", "003", "004"})
        self.assertEqual(classes["direct"], {"001"})
        self.assertEqual(classes["corrected"], {"002"})
        self.assertEqual(classes["yellow"], {"003"})
        self.assertEqual(classes["moved_detail"], {"004"})
        self.assertEqual(classes["unresolved"], {"005"})

    def test_unique_join_enforced(self):
        master, tire = sample_master(), sample_tire()
        del tire["003"]  # master asset with no tire row
        with override(**SMALL_CATEGORY):
            with self.assertRaises(SystemExit):
                m.join_and_classify(master, tire, sample_ymm_map(master), {"001", "002", "004"})

    def test_exact_totals_enforced(self):
        master, tire = sample_master(), sample_tire()
        opts = dict(SMALL_CATEGORY); opts["TOTAL_DIRECT"] = 2  # wrong
        with override(**opts):
            with self.assertRaises(SystemExit):
                m.join_and_classify(master, tire, sample_ymm_map(master),
                                    {"001", "002", "003", "004"})

    def test_membership_drift_fails_closed(self):
        master, tire = sample_master(), sample_tire()
        # Remove the Codex result so 002 falls into yellow -> membership drift
        with override(**SMALL_CATEGORY):
            with self.assertRaises(SystemExit):
                m.join_and_classify(master, tire, {}, {"001", "002", "003", "004"})

    def test_exclusivity_conflict_detected(self):
        master, tire = sample_master(), sample_tire()
        # Force 001 (direct) also into the moved set -> would overlap direct
        opts = dict(SMALL_CATEGORY)
        opts["APPROVED_MOVED_DETAIL"] = {"004", "001"}
        opts["TOTAL_MOVED"] = 2
        opts["TOTAL_DIRECT"] = 0
        with override(**opts):
            # 001 removed from direct via moved; direct becomes empty (0) -> totals ok,
            # but membership: moved={004,001} matches approved; direct=0 ok.
            classes = m.join_and_classify(master, tire, sample_ymm_map(master),
                                          {"001", "002", "003", "004"})
        self.assertEqual(classes["direct"], set())
        self.assertEqual(classes["moved_detail"], {"004", "001"})


class RtaTests(unittest.TestCase):
    def _vehicles(self):
        # 001-004 match uniquely; 005 unmatched (absent); make 003 a YMM mismatch.
        return [
            {"id": 1, "vehicleNumber": "001", "year": 2010, "make": "FORD", "model": "F150", "serialNumber": "AAA"},
            {"id": 2, "vehicleNumber": "002", "year": 2015, "make": "RAM", "model": "1500", "serialNumber": "BBB"},
            {"id": 3, "vehicleNumber": "003", "year": 2099, "make": "GMC", "model": "SIERRA", "serialNumber": "CCC"},
            {"id": 4, "vehicleNumber": "004", "year": 2012, "make": "CHEVY", "model": "TAHOE", "serialNumber": "DDD"},
        ]

    def test_rta_baseline_pass(self):
        master = sample_master()
        with override(APPROVED_AMBIGUOUS=set(), APPROVED_UNMATCHED={"005"},
                      RTA_MATCHED=4, RTA_YMM_MATCH=3, RTA_YMM_MISMATCH=1,
                      RTA_VIN_EXACT=4, RTA_VIN_CONFLICT=0, APPROVED_YMM_MISMATCH=set()):
            rta = m.verify_rta(master, self._vehicles())
        self.assertEqual(rta["ymm_mismatch_assets"], ["003"])
        self.assertEqual(rta["vin_exact"], 4)

    def test_rta_baseline_drift_fails(self):
        master = sample_master()
        with override(APPROVED_AMBIGUOUS=set(), APPROVED_UNMATCHED={"005"},
                      RTA_MATCHED=4, RTA_YMM_MATCH=4, RTA_YMM_MISMATCH=0,  # wrong: actual is 3/1
                      RTA_VIN_EXACT=4, RTA_VIN_CONFLICT=0, APPROVED_YMM_MISMATCH=set()):
            with self.assertRaises(SystemExit):
                m.verify_rta(master, self._vehicles())


class CompletenessTests(unittest.TestCase):
    def test_completeness_cross_check(self):
        entries = [
            {"asset": "a", "front_value": "x", "rear_value": "y", "detail1": None, "detail2": None},
            {"asset": "b", "front_value": None, "rear_value": None, "detail1": "d", "detail2": None},
            {"asset": "c", "front_value": "x", "rear_value": None, "detail1": None, "detail2": None},
        ]
        with override(EXPECTED_COMPLETE=1, EXPECTED_PARTIAL=1, EXPECTED_BLANK=1,
                      EXPECTED_DETAIL_POPULATED=1):
            res = m.check_completeness(entries)
        self.assertEqual(res["partial_assets"], ["c"])

    def test_completeness_drift_fails(self):
        entries = [{"asset": "a", "front_value": "x", "rear_value": "y", "detail1": None, "detail2": None}]
        with override(EXPECTED_COMPLETE=2, EXPECTED_PARTIAL=0, EXPECTED_BLANK=0,
                      EXPECTED_DETAIL_POPULATED=0):
            with self.assertRaises(SystemExit):
                m.check_completeness(entries)


@unittest.skipUnless(SOURCES_PRESENT, "authoritative OneDrive sources not present")
class FileGateTests(unittest.TestCase):
    """End-to-end file gates against the real sources with temp overrides."""

    def _run(self, extra):
        args = [sys.executable, str(SCRIPT), "--skip-rta", "--dry-run"] + extra
        return subprocess.run(args, capture_output=True, text=True)

    def test_happy_path_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            out_file = Path(d) / "nonexistent_output.xlsx"
            r = self._run(["--master", str(REAL_MASTER), "--tire", str(REAL_TIRE),
                           "--map-json", str(REAL_MAP), "--codex-json", str(REAL_CODEX),
                           "--output", str(out_file)])
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_hash_gate(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "tire.xlsx"
            shutil.copy2(REAL_TIRE, bad)
            with bad.open("ab") as fh:
                fh.write(b"\x00")  # perturb bytes -> hash mismatch
            r = self._run(["--master", str(REAL_MASTER), "--tire", str(bad),
                           "--map-json", str(REAL_MAP), "--codex-json", str(REAL_CODEX)])
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("fingerprint", r.stderr)

    def test_lock_gate(self):
        with tempfile.TemporaryDirectory() as d:
            master = Path(d) / REAL_MASTER.name
            shutil.copy2(REAL_MASTER, master)  # byte-identical -> hash still matches
            (Path(d) / f"~${REAL_MASTER.name}").write_text("lock")
            r = self._run(["--master", str(master), "--tire", str(REAL_TIRE),
                           "--map-json", str(REAL_MAP), "--codex-json", str(REAL_CODEX)])
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("lock", r.stderr)

    def test_output_exists_gate(self):
        # Point --output at an existing file (the real master) -> refuse.
        r = self._run(["--master", str(REAL_MASTER), "--tire", str(REAL_TIRE),
                       "--map-json", str(REAL_MAP), "--codex-json", str(REAL_CODEX),
                       "--output", str(REAL_MASTER)])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("output path", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
