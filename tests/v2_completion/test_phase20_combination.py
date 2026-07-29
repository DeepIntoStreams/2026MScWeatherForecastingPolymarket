from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase20CombinationTest(unittest.TestCase):
    def test_weight_selection_and_june_pairing(self) -> None:
        root = Path(__file__).resolve().parents[2]
        grid = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_combination_weight_grid.csv"
        )
        summary = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_combination_weight_summary.csv"
        )
        scores = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_score_summary.csv"
        )
        paired = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_june_paired_differences.csv"
        )

        self.assertEqual(len(grid), 1001)
        self.assertAlmostEqual(
            float(grid["gp_weight"].min()),
            0.0,
        )
        self.assertAlmostEqual(
            float(grid["gp_weight"].max()),
            1.0,
        )
        selected = float(summary["selected_gp_weight"].iloc[0])
        self.assertGreaterEqual(selected, 0.0)
        self.assertLessEqual(selected, 1.0)
        self.assertEqual(len(scores), 9)
        self.assertEqual(len(paired), 16)
        self.assertTrue((paired["dates"] == 30).all())
        self.assertEqual(
            set(paired["metric"]),
            {
                "binary_brier",
                "binary_log",
                "categorical_log",
                "multiclass_brier",
            },
        )
        self.assertTrue(
            paired["bootstrap_probability_difference_below_zero"]
            .between(0, 1)
            .all()
        )


if __name__ == "__main__":
    unittest.main()
