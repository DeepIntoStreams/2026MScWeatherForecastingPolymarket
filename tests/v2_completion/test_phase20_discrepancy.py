from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase20DiscrepancyTest(unittest.TestCase):
    def test_discrepancy_outputs(self) -> None:
        root = Path(__file__).resolve().parents[2]
        books = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_book_discrepancy_panel.csv"
        )
        events = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_event_discrepancy_panel.csv"
        )
        coefficients = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_discrepancy_regression_coefficients.csv"
        )
        regressions = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_discrepancy_regression_summary.csv"
        )
        gaps = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_gap_updates.csv"
        )

        self.assertEqual(len(books), 350)
        self.assertEqual(len(events), 3850)
        self.assertTrue(
            books["total_variation_distance"].between(0, 1).all()
        )
        self.assertTrue(
            books["jensen_shannon_divergence"].ge(0).all()
        )
        self.assertEqual(len(regressions), 2)
        self.assertGreaterEqual(len(coefficients), 12)
        self.assertTrue(
            regressions[
                "joint_non_intercept_cluster_robust_p_value"
            ].between(0, 1).all()
        )
        self.assertEqual(set(gaps["gap_id"]), {"G13", "G14"})
        self.assertTrue((gaps["status"] == "CLOSED").all())


if __name__ == "__main__":
    unittest.main()
