from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


class Phase20SupportTest(unittest.TestCase):
    def test_exact_support_and_probabilities(self) -> None:
        root = Path(__file__).resolve().parents[2]
        panel = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase20_exact_common_support_event_panel.csv"
        )
        specification = json.loads(
            (
                root
                / "config/v2_completion/"
                / "phase20_forecast_combination_spec.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(len(panel), 3850)
        self.assertEqual(panel["target_date"].nunique(), 97)
        self.assertEqual(panel["book_key"].nunique(), 350)
        self.assertEqual(
            panel.loc[
                panel["sample_period"]
                == "weather_plus_market_development",
                "target_date",
            ].nunique(),
            67,
        )
        self.assertEqual(
            panel.loc[
                panel["sample_period"] == "june_out_of_sample",
                "target_date",
            ].nunique(),
            30,
        )
        self.assertTrue(
            (
                panel.groupby("book_key")["realised_yes"].sum()
                == 1
            ).all()
        )
        self.assertLessEqual(
            float(
                (
                    panel.groupby("book_key")["gp_probability"].sum()
                    - 1.0
                ).abs().max()
            ),
            1e-6,
        )
        self.assertLessEqual(
            float(
                (
                    panel.groupby("book_key")[
                        "market_probability"
                    ].sum()
                    - 1.0
                ).abs().max()
            ),
            1e-8,
        )
        self.assertEqual(specification["status"], "PASSED")
        self.assertEqual(
            set(specification["closed_gaps"]),
            {"G13", "G14"},
        )


if __name__ == "__main__":
    unittest.main()
