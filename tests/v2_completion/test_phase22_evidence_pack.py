from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


class Phase22EvidencePackTest(unittest.TestCase):
    root = Path.cwd()
    output = root / "outputs/v2_completion/phase22_thesis_evidence_pack"
    config = root / "config/v2_completion/phase22_thesis_evidence_pack_spec.json"

    def test_required_outputs(self) -> None:
        required = {
            "phase22_report.md",
            "phase22_empirical_instruction_book.md",
            "phase22_methodology_evidence.md",
            "phase22_results_evidence.md",
            "phase22_discussion_evidence.md",
            "phase22_key_metrics.csv",
            "phase22_claim_register.csv",
            "phase22_evidential_boundaries.csv",
            "phase22_gap_closure_register.csv",
            "phase22_source_inventory.csv",
            "phase22_table_inventory.csv",
            "phase22_figure_inventory.csv",
            "phase22_reproducibility_summary.csv",
            "phase22_manifest.json",
        }
        observed = {
            path.name for path in self.output.iterdir()
            if path.is_file()
        }
        self.assertTrue(required.issubset(observed))

    def test_gap_closure(self) -> None:
        path = self.output / "phase22_gap_closure_register.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        status = {row["gap_id"]: row["status_after_phase22"] for row in rows}
        for number in range(1, 17):
            self.assertEqual(status[f"G{number:02d}"], "CLOSED")
        self.assertEqual(status["G17"], "OPEN")

    def test_instruction_book_scope(self) -> None:
        text = (
            self.output / "phase22_empirical_instruction_book.md"
        ).read_text(encoding="utf-8")
        required_phrases = [
            "static Gaussian benchmark",
            "Matern-3/2",
            "exact common support",
            "forecast combination",
            "Polymarket",
            "reproducibility",
            "CatBoost",
            "Claims that must not appear",
        ]
        for phrase in required_phrases:
            self.assertIn(phrase.lower(), text.lower())

    def test_phase21_reproducibility_summary(self) -> None:
        path = self.output / "phase22_reproducibility_summary.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        values = {row["item"]: row["value"] for row in rows}
        self.assertEqual(values["phases_replayed"], "6")
        self.assertEqual(values["artifacts_compared"], "116")
        self.assertEqual(values["failed_artifact_comparisons"], "0")
        self.assertEqual(values["maximum_finite_replay_error"], "0.000e+00")

    def test_manifest_and_config(self) -> None:
        manifest = json.loads(
            (self.output / "phase22_manifest.json").read_text(encoding="utf-8")
        )
        config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "PASSED")
        self.assertEqual(config["status"], "PASSED")
        self.assertEqual(config["counts"]["closed_gaps"], 16)
        self.assertEqual(config["counts"]["open_gaps"], 1)
        self.assertTrue(config["design_constraints"]["exact_common_support_preserved"])
        self.assertTrue(config["design_constraints"]["june_not_used_for_development"])


if __name__ == "__main__":
    unittest.main()
