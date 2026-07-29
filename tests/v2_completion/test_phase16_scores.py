from __future__ import annotations

import math
import unittest
from pathlib import Path

import pandas as pd


class Phase16ScoreTest(unittest.TestCase):
    def test_scores_and_pairs(self) -> None:
        root = Path(__file__).resolve().parents[2]
        scores = pd.read_csv(
            root / "outputs/v2_completion/phase16_model_scores_overall.csv"
        ).set_index("model")
        self.assertEqual(
            set(scores.index),
            {"raw_point", "static_gaussian", "rbf", "matern32"},
        )
        self.assertTrue(
            math.isclose(
                float(scores.loc["rbf", "legacy_mean_date_crps_c"]),
                0.877561,
                abs_tol=5e-6,
                rel_tol=0.0,
            )
        )
        self.assertTrue(
            math.isclose(
                float(scores.loc["matern32", "legacy_mean_date_crps_c"]),
                0.863340,
                abs_tol=5e-6,
                rel_tol=0.0,
            )
        )
        self.assertTrue((scores["mean_date_crps_c"] > 0).all())

        paired = pd.read_csv(
            root / "outputs/v2_completion/phase16_paired_model_differences.csv"
        )
        overall = paired.loc[paired["scope"] == "overall"]
        self.assertEqual(
            set(overall["comparison"]),
            {
                "static_minus_raw",
                "rbf_minus_static",
                "matern32_minus_static",
                "matern32_minus_rbf",
            },
        )
        self.assertTrue((overall["dates"] == 365).all())


if __name__ == "__main__":
    unittest.main()
