from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


class Phase19OutputTest(unittest.TestCase):
    def test_outputs_and_figures(self) -> None:
        root = Path(__file__).resolve().parents[2]

        expected_csv_rows = {
            "phase19_pit_summary.csv": 18,
            "phase19_pit_histogram.csv": 180,
            "phase19_sharpness_summary.csv": 50,
            "phase19_standardised_residual_summary.csv": 50,
            "phase19_heteroskedasticity_quartiles.csv": 120,
            "phase19_gap_updates.csv": 2,
        }

        for filename, rows in expected_csv_rows.items():
            frame = pd.read_csv(
                root / "outputs/v2_completion" / filename
            )
            self.assertEqual(len(frame), rows)

        specification = json.loads(
            (
                root
                / "config/v2_completion/"
                / "phase19_predictive_diagnostics_spec.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(specification["status"], "PASSED")
        self.assertEqual(
            specification["support"]["validation_rows"],
            2920,
        )
        self.assertEqual(
            specification["support"]["validation_dates"],
            365,
        )
        self.assertEqual(
            set(specification["closed_gaps"]),
            {"G10", "G11"},
        )

        figure_names = [
            "phase19_quantile_calibration",
            "phase19_central_coverage_errors",
            "phase19_pit_histogram",
            "phase19_standardised_residual_acf",
            "phase19_squared_standardised_residual_acf",
            "phase19_variance_by_sharpness_quartile",
        ]
        for name in figure_names:
            for suffix in ("png", "pdf"):
                path = (
                    root
                    / "outputs/v2_completion/phase19_figures"
                    / f"{name}.{suffix}"
                )
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
