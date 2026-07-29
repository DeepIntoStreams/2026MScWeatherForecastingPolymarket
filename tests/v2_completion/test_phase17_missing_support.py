from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase17MissingSupportTest(unittest.TestCase):
    def test_missing_support_partition(self) -> None:
        root = Path(__file__).resolve().parents[2]

        missing = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase17_missing_key_registry.csv"
        )
        support = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase17_support_by_date.csv"
        )

        self.assertEqual(len(missing), 37)
        self.assertFalse(
            missing.duplicated(
                ["target_date", "decision_rule"]
            ).any()
        )
        self.assertTrue((missing["imputed"] == False).all())
        self.assertTrue(
            missing["reason_category"].notna().all()
        )

        self.assertEqual(len(support), 103)
        self.assertEqual(int(support["theoretical_keys"].sum()), 412)
        self.assertEqual(int(support["supported_keys"].sum()), 375)
        self.assertEqual(int(support["missing_keys"].sum()), 37)
        self.assertEqual(
            int(support["any_forecast_support"].sum()),
            102,
        )


if __name__ == "__main__":
    unittest.main()
