from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase19CalibrationTest(unittest.TestCase):
    def test_calibration_dimensions_and_ranges(self) -> None:
        root = Path(__file__).resolve().parents[2]
        coverage = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_coverage_summary.csv"
        )
        curve = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_quantile_calibration.csv"
        )
        summary = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_quantile_calibration_summary.csv"
        )
        reconciliation = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_reconciliation_checks.csv"
        )

        self.assertEqual(len(coverage), 150)
        self.assertEqual(len(curve), 990)
        self.assertEqual(len(summary), 10)
        self.assertTrue(
            coverage["empirical_coverage"].between(0, 1).all()
        )
        self.assertTrue(
            curve["empirical_probability"].between(0, 1).all()
        )
        self.assertEqual(
            set(coverage["nominal_coverage"]),
            {0.5, 0.8, 0.9},
        )
        self.assertEqual(curve["nominal_probability"].nunique(), 99)
        self.assertTrue((reconciliation["status"] == "PASSED").all())
        self.assertLessEqual(
            float(
                reconciliation["maximum_absolute_error"].max()
            ),
            float(reconciliation["tolerance"].max()),
        )
        self.assertNotIn(
            "phase19_failed_reconciliation_checks.csv",
            {
                path.name
                for path in (
                    root / "outputs/v2_completion"
                ).glob("phase19_failed_reconciliation_checks.csv")
            },
        )


if __name__ == "__main__":
    unittest.main()
