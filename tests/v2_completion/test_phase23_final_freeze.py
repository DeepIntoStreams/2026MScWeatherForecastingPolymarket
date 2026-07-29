from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path


class Phase23FinalFreezeTest(unittest.TestCase):
    root = Path.cwd()
    output = root / "outputs/v2_completion/phase23_final_freeze"
    config = root / "config/v2_completion/phase23_final_freeze_spec.json"

    def read_csv(self, name: str) -> list[dict[str, str]]:
        with (self.output / name).open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            return list(csv.DictReader(handle))

    def test_required_outputs(self) -> None:
        required = {
            "phase23_report.md",
            "phase23_release_notes.md",
            "phase23_thesis_handover.md",
            "phase23_validation_checks.csv",
            "phase23_gap_closure_register.csv",
            "phase23_frozen_file_inventory.csv",
            "phase23_frozen_key_metrics.csv",
            "phase23_checksums.sha256",
            "phase23_manifest.json",
        }
        observed = {
            path.name
            for path in self.output.iterdir()
            if path.is_file()
        }
        self.assertTrue(required.issubset(observed))

    def test_validation_checks(self) -> None:
        rows = self.read_csv("phase23_validation_checks.csv")
        self.assertGreaterEqual(len(rows), 13)
        self.assertTrue(all(row["status"] == "PASSED" for row in rows))

    def test_all_gaps_closed(self) -> None:
        rows = self.read_csv("phase23_gap_closure_register.csv")
        self.assertEqual(len(rows), 17)
        self.assertEqual(
            {row["gap_id"] for row in rows},
            {f"G{number:02d}" for number in range(1, 18)},
        )
        self.assertTrue(
            all(row["status_after_phase23"] == "CLOSED" for row in rows)
        )

    def test_frozen_inventory(self) -> None:
        rows = self.read_csv("phase23_frozen_file_inventory.csv")
        self.assertGreater(len(rows), 100)
        self.assertTrue(all(row["tracked"] == "True" for row in rows))
        self.assertTrue(all(row["status"] == "PASSED" for row in rows))
        self.assertTrue(
            all(len(row["sha256"]) == 64 for row in rows)
        )

    def test_frozen_key_metrics(self) -> None:
        rows = self.read_csv("phase23_frozen_key_metrics.csv")
        self.assertEqual(len(rows), 23)
        self.assertTrue(all(row["status"] == "VERIFIED" for row in rows))
        self.assertTrue(all(row["freeze_status"] == "FROZEN" for row in rows))

    def test_manifest(self) -> None:
        manifest = json.loads(
            (self.output / "phase23_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        config = json.loads(self.config.read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "PASSED")
        self.assertEqual(config["status"], "PASSED")
        self.assertEqual(config["gaps"], {"closed": 17, "open": 0})
        self.assertEqual(config["final_tag"], "v2-empirical-complete")
        self.assertTrue(config["no_new_empirical_estimation"])

        for item in manifest["outputs"]:
            path = self.root / item["relative_path"]
            self.assertTrue(path.is_file())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, item["sha256"])


if __name__ == "__main__":
    unittest.main()
