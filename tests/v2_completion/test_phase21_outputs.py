from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase21OutputTest(unittest.TestCase):
    def test_report_figures_and_gap(self) -> None:
        root = Path(__file__).resolve().parents[2]
        report = (
            root
            / "outputs/v2_completion/"
            / "phase21_reproducibility_report.md"
        )
        text = report.read_text(encoding="utf-8")
        self.assertIn("## Isolation boundary", text)
        self.assertIn("## Evidential boundary", text)

        gaps = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase21_gap_updates.csv"
        )
        self.assertEqual(gaps["gap_id"].tolist(), ["G15"])
        self.assertEqual(gaps["status"].tolist(), ["CLOSED"])

        for suffix in ("png", "pdf"):
            path = (
                root
                / "outputs/v2_completion/phase21_figures/"
                / f"phase21_replay_artifact_counts.{suffix}"
            )
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1000)

        self.assertTrue(
            (root / "REPRODUCIBILITY_V2.md").is_file()
        )


if __name__ == "__main__":
    unittest.main()
