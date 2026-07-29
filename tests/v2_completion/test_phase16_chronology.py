from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Phase16ChronologyTest(unittest.TestCase):
    def test_chronological_predictions(self) -> None:
        root = Path(__file__).resolve().parents[2]
        path = (
            root
            / "data/processed/v2_completion/"
            / "phase16_chronological_raw_static_predictions.csv"
        )
        frame = pd.read_csv(path)
        self.assertEqual(len(frame), 5840)
        self.assertEqual(pd.to_datetime(frame["target_date"]).nunique(), 365)
        self.assertEqual(frame["decision_rule"].nunique(), 4)
        self.assertEqual(
            set(frame["model"]),
            {"raw_point", "static_gaussian", "rbf", "matern32"},
        )
        raw = frame.loc[frame["model"] == "raw_point"]
        expected = np.abs(raw["forecast_daily_max_c"] - raw["hko_daily_max_c"])
        self.assertTrue(np.allclose(raw["crps_c"], expected, atol=1e-12, rtol=0.0))

        static = frame.loc[frame["model"] == "static_gaussian"]
        self.assertTrue((static["predictive_standard_deviation_c"] > 0).all())
        self.assertTrue(
            (
                pd.to_datetime(static["training_end"])
                < pd.to_datetime(static["validation_start"])
            ).all()
        )


if __name__ == "__main__":
    unittest.main()
