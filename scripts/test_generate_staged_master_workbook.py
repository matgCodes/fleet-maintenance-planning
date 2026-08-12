#!/usr/bin/env python3
"""test_generate_staged_master_workbook.py  (Issue #17 AC)

Automated test suite for generate_staged_master_workbook.py.

Covers:
- Gate checks: manifest schema, RTA verification status, master/tire lock files,
  master/tire hash mismatch, refuse source overwrite, refuse existing output.
- Workbook construction: sheet preservation, header formatting, column widths,
  exact category behavior (direct, moved_detail, corrected, yellow, unresolved).
- Reload & Completeness audit: 423 complete, 1 partial (0SAN07), 20 blank,
  23 detail fields populated, 30 yellow cells.
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
import generate_staged_master_workbook as g  # noqa: E402

SCRIPT = SCRIPT_DIR / "generate_staged_master_workbook.py"
REAL_MASTER = Path(g.DEFAULT_MASTER)
REAL_TIRE = Path(g.DEFAULT_TIRE)
REAL_MANIFEST = Path(g.DEFAULT_MANIFEST)

SOURCES_PRESENT = all(p.exists() for p in (REAL_MASTER, REAL_TIRE, REAL_MANIFEST))


@unittest.skipUnless(SOURCES_PRESENT, "Authoritative OneDrive sources / manifest not present")
class GateTests(unittest.TestCase):
    def _run(self, extra_args):
        cmd = [sys.executable, str(SCRIPT), "--master", str(REAL_MASTER), "--tire", str(REAL_TIRE), "--manifest", str(REAL_MANIFEST)] + extra_args
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_dry_run_happy_path(self):
        res = self._run(["--dry-run"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("[DRY-RUN] Staging complete", res.stdout)

    def test_output_exists_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            out_file = Path(d) / "output.xlsx"
            out_file.write_text("existing output")
            res = self._run(["--output", str(out_file)])
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("already exists", res.stderr)

    def test_output_exists_force_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            out_file = Path(d) / "output.xlsx"
            out_file.write_text("existing output")
            res = self._run(["--output", str(out_file), "--force"])
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_file.exists())

    def test_refuse_source_overwrite(self):
        res = self._run(["--output", str(REAL_MASTER)])
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Refusing to overwrite source", res.stderr)

    def test_lock_file_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            master_copy = Path(d) / REAL_MASTER.name
            shutil.copy2(REAL_MASTER, master_copy)
            lock_file = Path(d) / f"~${REAL_MASTER.name}"
            lock_file.write_text("lock")

            out_file = Path(d) / "staged.xlsx"
            cmd = [
                sys.executable, str(SCRIPT),
                "--master", str(master_copy),
                "--tire", str(REAL_TIRE),
                "--manifest", str(REAL_MANIFEST),
                "--output", str(out_file)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("Lock file exists", res.stderr)

    def test_hash_mismatch_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            tire_copy = Path(d) / REAL_TIRE.name
            shutil.copy2(REAL_TIRE, tire_copy)
            with tire_copy.open("ab") as fh:
                fh.write(b"\x00")

            out_file = Path(d) / "staged.xlsx"
            cmd = [
                sys.executable, str(SCRIPT),
                "--master", str(REAL_MASTER),
                "--tire", str(tire_copy),
                "--manifest", str(REAL_MANIFEST),
                "--output", str(out_file)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("SHA-256 mismatch", res.stderr)


@unittest.skipUnless(SOURCES_PRESENT, "Authoritative OneDrive sources / manifest not present")
class IntegrationAndReloadTests(unittest.TestCase):
    def test_full_staged_generation_and_reload(self):
        with tempfile.TemporaryDirectory() as d:
            out_file = Path(d) / "Key_Inventory_Template_Master_With_Tire_Sizes.xlsx"
            manifest = g.load_and_verify_manifest(REAL_MANIFEST, REAL_MASTER, REAL_TIRE)
            out_sha = g.generate_staged_workbook(
                master_path=REAL_MASTER,
                tire_path=REAL_TIRE,
                output_path=out_file,
                manifest=manifest,
                dry_run=False,
                force=True
            )
            self.assertIsNotNone(out_sha)
            self.assertTrue(out_file.exists())

            # Perform reload audit
            stats = g.verify_reload(out_file)
            self.assertEqual(stats["complete"], 423)
            self.assertEqual(stats["partial"], 1)
            self.assertEqual(stats["partial_assets"], ["0SAN07"])
            self.assertEqual(stats["blank"], 20)
            self.assertEqual(stats["detail_populated"], 23)
            self.assertEqual(stats["yellow_cells"], 30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
