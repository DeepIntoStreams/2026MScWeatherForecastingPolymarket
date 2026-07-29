from __future__ import annotations

import math
import unittest
from pathlib import Path

import pandas as pd


class Phase16EventScoreTest(unittest.TestCase):
    def test_event_score_reconciliation(self) -> None:
        root = Path(__file__).resolve().parents[2]
        frame = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase16_static_event_probability_scores.csv"
        )
        phase9 = frame.loc[
            (frame["support_scope"] == "phase9_legacy_forecast_supported")
            & (frame["period"] == "overall")
            & (frame["model"] == "matern32_gp")
        ].iloc[0]
        self.assertEqual(
            phase9["aggregation"],
            "equal date-rule-book weight, matching certified Phase 9",
        )
        expected = {
            "mean_binary_brier": 0.06664735,
            "mean_binary_log": 0.21621827,
            "mean_categorical_log": 1.53611577,
            "mean_multiclass_brier": 0.73312081,
        }
        for column, value in expected.items():
            self.assertTrue(
                math.isclose(
                    float(phase9[column]),
                    value,
                    abs_tol=5e-8,
                    rel_tol=0.0,
                )
            )

        exact_june = frame.loc[
            (frame["support_scope"] == "exact_common_support")
            & (frame["period"] == "june")
        ].set_index("model")
        expected_differences = {
            "mean_binary_brier": 0.009324,
            "mean_binary_log": 0.038628,
            "mean_categorical_log": 0.357342,
            "mean_multiclass_brier": 0.101710,
        }
        for column, value in expected_differences.items():
            observed = (
                float(exact_june.loc["matern32_gp", column])
                - float(exact_june.loc["polymarket", column])
            )
            self.assertTrue(
                math.isclose(observed, value, abs_tol=5e-6, rel_tol=0.0)
            )


if __name__ == "__main__":
    unittest.main()
