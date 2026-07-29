from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Phase17DeterministicErrorTest(unittest.TestCase):
    def test_rule_error_outputs(self) -> None:
        root = Path(__file__).resolve().parents[2]

        summary = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase17_rule_error_summary.csv"
        )
        self.assertEqual(len(summary), 4)
        self.assertTrue((summary["dates"] == 730).all())
        self.assertEqual(
            set(summary["decision_rule"]),
            {
                "24h_prior",
                "12h_prior",
                "6h_prior",
                "event_day_open",
            },
        )
        self.assertTrue((summary["mae_c"] > 0).all())
        self.assertTrue((summary["rmse_c"] >= summary["mae_c"]).all())
        self.assertTrue(
            (
                summary["mean_error_bootstrap_lower_95_c"]
                <= summary["mean_error_hko_minus_forecast_c"]
            ).all()
        )
        self.assertTrue(
            (
                summary["mean_error_hko_minus_forecast_c"]
                <= summary["mean_error_bootstrap_upper_95_c"]
            ).all()
        )

        blocks = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase17_error_by_validation_block.csv"
        )
        self.assertEqual(len(blocks), 16)
        self.assertEqual(blocks["decision_rule"].nunique(), 4)
        self.assertEqual(blocks["fold_id"].nunique(), 4)
        self.assertEqual(int(blocks["validation_dates"].sum()), 1460)


if __name__ == "__main__":
    unittest.main()
