from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase18PairTest(unittest.TestCase):
    def test_paired_outputs_and_rankings(self) -> None:
        root = Path(__file__).resolve().parents[2]

        paired = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_paired_model_differences.csv"
        )
        rankings = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_rule_block_rankings.csv"
        )
        rank_summary = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_model_rank_stability.csv"
        )

        self.assertEqual(len(paired), 100)
        self.assertEqual(
            set(paired["scope"]),
            {
                "overall",
                "decision_rule",
                "validation_block",
                "rule_by_validation_block",
            },
        )
        overall = paired.loc[paired["scope"] == "overall"]
        self.assertEqual(len(overall), 4)
        self.assertTrue((overall["dates"] == 365).all())

        self.assertEqual(len(rankings), 64)
        self.assertEqual(len(rank_summary), 4)
        self.assertEqual(int(rank_summary["best_cells"].sum()), 16)
        self.assertTrue(rankings["rank"].between(1, 4).all())


if __name__ == "__main__":
    unittest.main()
