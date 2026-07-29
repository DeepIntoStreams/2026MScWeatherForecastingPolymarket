from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase16SupportTest(unittest.TestCase):
    def test_static_event_support(self) -> None:
        root = Path(__file__).resolve().parents[2]
        forecast = pd.read_csv(
            root
            / "data/processed/v2_completion/"
            / "phase16_full_history_static_market_predictions.csv"
        )
        exact = pd.read_csv(
            root
            / "data/processed/v2_completion/"
            / "phase16_exact_common_support_static_event_panel.csv"
        )

        self.assertEqual(len(forecast), 4125)
        self.assertEqual(pd.to_datetime(forecast["target_date"]).nunique(), 102)
        self.assertEqual(
            forecast[["target_date", "decision_rule"]].drop_duplicates().shape[0],
            375,
        )
        required_columns = {
            "forecast_daily_max_c",
            "residual_mean_c",
            "residual_standard_deviation_c",
            "static_temperature_mean_c",
            "static_temperature_standard_deviation_c",
        }
        self.assertTrue(required_columns.issubset(set(forecast.columns)))
        self.assertFalse(
            any(column.endswith("_x") or column.endswith("_y") for column in forecast.columns)
        )
        mass = forecast.groupby(["target_date", "decision_rule"])[
            "static_event_probability"
        ].sum()
        self.assertLess(float((mass - 1.0).abs().max()), 1e-10)
        winners = forecast.groupby(["target_date", "decision_rule"])[
            "realised_event"
        ].sum()
        self.assertTrue((winners == 1).all())

        self.assertEqual(len(exact), 3850)
        self.assertEqual(pd.to_datetime(exact["target_date"]).nunique(), 97)
        self.assertEqual(
            exact[["target_date", "decision_rule"]].drop_duplicates().shape[0],
            350,
        )


if __name__ == "__main__":
    unittest.main()
