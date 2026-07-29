from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase19DependenceTest(unittest.TestCase):
    def test_dependence_and_variance_outputs(self) -> None:
        root = Path(__file__).resolve().parents[2]
        acf = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_autocorrelation.csv"
        )
        dependence = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_dependence_summary.csv"
        )
        correlations = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_cross_rule_residual_correlations.csv"
        )
        coefficients = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_variance_regression_coefficients.csv"
        )
        variance = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase19_variance_regression_summary.csv"
        )

        self.assertEqual(len(acf), 420)
        self.assertEqual(len(dependence), 10)
        self.assertEqual(len(correlations), 12)
        self.assertEqual(len(coefficients), 22)
        self.assertEqual(len(variance), 2)
        self.assertTrue(acf["autocorrelation"].between(-1, 1).all())
        self.assertTrue(
            correlations["pearson_correlation"].between(-1, 1).all()
        )
        self.assertTrue(
            variance[
                "joint_non_intercept_cluster_robust_p_value"
            ].between(0, 1).all()
        )


if __name__ == "__main__":
    unittest.main()
