from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase18ScoreTest(unittest.TestCase):
    def test_score_dimensions_and_support(self) -> None:
        root = Path(__file__).resolve().parents[2]

        by_rule = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_model_scores_by_rule.csv"
        )
        by_block = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_model_scores_by_block.csv"
        )
        by_rule_block = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_model_scores_by_rule_block.csv"
        )

        self.assertEqual(len(by_rule), 16)
        self.assertEqual(len(by_block), 16)
        self.assertEqual(len(by_rule_block), 64)
        self.assertEqual(by_rule["model"].nunique(), 4)
        self.assertEqual(by_rule["decision_rule"].nunique(), 4)
        self.assertEqual(by_block["fold_id"].nunique(), 4)
        self.assertEqual(by_rule_block["fold_id"].nunique(), 4)
        self.assertTrue((by_rule["dates"] == 365).all())
        self.assertTrue((by_rule["mean_crps_c"] > 0).all())
        self.assertTrue((by_block["decision_rules"] == 4).all())
        self.assertTrue(
            (by_block["minimum_rules_within_date"] == 4).all()
        )


if __name__ == "__main__":
    unittest.main()
