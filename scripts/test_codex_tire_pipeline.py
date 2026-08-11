#!/usr/bin/env python3

import json
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codex_excel_injection import file_hash, inject
from codex_research_queue import (
    initialize_results,
    load_codex_results,
    merge_batch,
    pending_payload,
    task_index,
)


def result(task_id: str, score: int, tire_size: str) -> dict:
    return {
        "taskId": task_id,
        "tireData": {
            "frontTireSize": tire_size,
            "rearTireSize": tire_size,
            "isStaggered": False,
        },
        "researchMetadata": {
            "sourceName": "Manufacturer specification",
            "sourceUrl": f"https://example.com/{task_id}",
            "reliabilityScore": score,
            "reliabilityRationale": "Exact model-year specification.",
            "fleetEdgeCaseNotes": "Verify installed equipment in the field.",
        },
    }


class CodexTirePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.tasks_path = self.root / "tasks.json"
        self.seed_path = self.root / "seed.json"
        self.codex_path = self.root / "codex.json"
        self.tasks = [
            {
                "taskId": "veh_001",
                "vehicle": {"year": 2024, "make": "MAKE", "model": "ONE"},
            },
            {
                "taskId": "veh_002",
                "vehicle": {"year": 2025, "make": "MAKE", "model": "TWO"},
            },
        ]
        self.tasks_path.write_text(json.dumps(self.tasks), encoding="utf-8")
        self.seed_path.write_text(json.dumps([result("veh_001", 5, "225/65R17")]), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_queue_bootstraps_copy_and_merges_without_changing_seed(self):
        _, known_tasks = task_index(self.tasks_path)
        seed_before = self.seed_path.read_bytes()
        initialize_results(self.seed_path, self.codex_path, known_tasks)

        pending = pending_payload(
            self.tasks,
            {item["taskId"] for item in load_codex_results(self.codex_path, known_tasks)},
            None,
        )
        self.assertEqual([item["taskId"] for item in pending], ["veh_002"])

        batch_path = self.root / "batch.json"
        batch_path.write_text(json.dumps([result("veh_002", 3, "245/70R17")]), encoding="utf-8")
        merged, total = merge_batch(batch_path, self.codex_path, known_tasks, False)

        self.assertEqual((merged, total), (1, 2))
        self.assertEqual(self.seed_path.read_bytes(), seed_before)

    def test_injection_creates_new_workbook_and_preserves_source(self):
        source = self.root / "source.xlsx"
        output = self.root / "output.xlsx"
        audit = self.root / "audit.json"
        mapping = self.root / "mapping.json"
        results_path = self.root / "results.json"

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "Asset ID Number",
                "Year",
                "Make",
                "Model",
                "Front Tire Size",
                "Rear Tire Size",
            ]
        )
        sheet.append(["001", 2024, "MAKE", "ONE", None, None])
        sheet.append(["002", 2025, "MAKE", "TWO", None, None])
        workbook.save(source)

        mapping.write_text(
            json.dumps(
                {
                    "veh_001": {"vehicle": self.tasks[0]["vehicle"], "assets": [{"row": 2}]},
                    "veh_002": {"vehicle": self.tasks[1]["vehicle"], "assets": [{"row": 3}]},
                }
            ),
            encoding="utf-8",
        )
        results_path.write_text(
            json.dumps(
                [
                    result("veh_001", 5, "225/65R17"),
                    result("veh_002", 3, "245/70R17"),
                ]
            ),
            encoding="utf-8",
        )

        source_hash = file_hash(source)
        tasks, rows = inject(
            source,
            output,
            self.tasks_path,
            mapping,
            results_path,
            audit,
        )

        self.assertEqual((tasks, rows), (2, 2))
        self.assertEqual(file_hash(source), source_hash)
        self.assertTrue(output.exists())
        self.assertTrue(audit.exists())

        enriched = openpyxl.load_workbook(output)
        enriched_sheet = enriched.active
        self.assertEqual(enriched_sheet["E2"].value, "225/65R17")
        self.assertEqual(enriched_sheet["F3"].value, "245/70R17")
        self.assertEqual(enriched_sheet["E2"].fill.fgColor.rgb, "00D9EAD3")
        self.assertEqual(enriched_sheet["E3"].fill.fgColor.rgb, "00FFF2CC")


if __name__ == "__main__":
    unittest.main()
