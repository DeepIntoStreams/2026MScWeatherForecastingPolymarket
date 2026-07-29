from __future__ import annotations

import math
import unittest
from pathlib import Path

import pandas as pd


class Phase17StructureTest(unittest.TestCase):
    def test_pairwise_and_variance_outputs(self) -> None:
        root = Path(__file__).resolve().parents[2]

        pairwise = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase17_pairwise_rule_differences.csv"
        )
        self.assertEqual(len(pairwise), 6)
        self.assertTrue((pairwise["dates"] == 730).all())

        decomposition = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase17_error_variance_decomposition.csv"
        )
        components = decomposition.set_index("component")
        self.assertEqual(
            set(components.index),
            {
                "target_date",
                "decision_rule",
                "date_by_rule_interaction",
                "total",
            },
        )
        share = (
            float(
                components.loc[
                    "target_date",
                    "share_of_total_sum_squares",
                ]
            )
            + float(
                components.loc[
                    "decision_rule",
                    "share_of_total_sum_squares",
                ]
            )
            + float(
                components.loc[
                    "date_by_rule_interaction",
                    "share_of_total_sum_squares",
                ]
            )
        )
        self.assertTrue(
            math.isclose(
                share,
                1.0,
                abs_tol=1e-10,
                rel_tol=0.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
