#!/usr/bin/env python3
"""test_validate_and_publish_master_workbook.py  (Issue #18 AC)

Automated test suite for validate_and_publish_master_workbook.py.
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
import validate_and_publish_master_workbook as v  # noqa: E402

SCRIPT = SCRIPT_DIR / "validate_and_publish_master_workbook.py"
REAL_MASTER = Path(v.DEFAULT_MASTER)
REAL_TIRE = Path(v.DEFAULT_TIRE)
REAL_PUBLISHED = Path(v.DEFAULT_PUBLISHED)
REAL_MANIFEST = Path(v.DEFAULT_MANIFEST)

SOURCES_PRESENT = all(p.exists() for p in (REAL_MASTER, REAL_TIRE, REAL_PUBLISHED, REAL_MANIFEST))


@unittest.skipUnless(SOURCES_PRESENT, "Authoritative OneDrive sources / published workbook not present")
class Issue18ValidationTests(unittest.TestCase):
    def test_full_publication_validation_pass(self):
        res = v.validate_and_publish(
            master_path=REAL_MASTER,
            tire_path=REAL_TIRE,
            published_path=REAL_PUBLISHED,
            manifest_path=REAL_MANIFEST
        )
        self.assertEqual(res["complete_count"], 423)
        self.assertEqual(res["partial_count"], 1)
        self.assertEqual(res["partial_assets"], ["0SAN07"])
        self.assertEqual(res["blank_count"], 20)
        self.assertEqual(res["detail_count"], 23)
        self.assertEqual(res["yellow_cells_count"], 30)
        self.assertEqual(res["master_sha256"], v.EXPECTED_MASTER_SHA)
        self.assertEqual(res["tire_sha256"], v.EXPECTED_TIRE_SHA)

    def test_master_lock_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            master_copy = Path(d) / REAL_MASTER.name
            shutil.copy2(REAL_MASTER, master_copy)
            lock_file = Path(d) / f"~${REAL_MASTER.name}"
            lock_file.write_text("lock")

            cmd = [
                sys.executable, str(SCRIPT),
                "--master", str(master_copy),
                "--tire", str(REAL_TIRE),
                "--published", str(REAL_PUBLISHED),
                "--manifest", str(REAL_MANIFEST)
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("Lock file exists", r.stderr)

    def test_fingerprint_mismatch_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            master_copy = Path(d) / REAL_MASTER.name
            shutil.copy2(REAL_MASTER, master_copy)
            with master_copy.open("ab") as fh:
                fh.write(b"\x00")

            cmd = [
                sys.executable, str(SCRIPT),
                "--master", str(master_copy),
                "--tire", str(REAL_TIRE),
                "--published", str(REAL_PUBLISHED),
                "--manifest", str(REAL_MANIFEST)
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("fingerprint drift", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
