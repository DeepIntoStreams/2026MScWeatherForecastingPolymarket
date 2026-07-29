from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase18HyperparameterTest(unittest.TestCase):
    def test_hyperparameter_registry(self) -> None:
        root = Path(__file__).resolve().parents[2]

        folds = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_gp_fold_hyperparameters.csv"
        )
        full = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_gp_full_fit_hyperparameters.csv"
        )
        stability = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_gp_hyperparameter_stability.csv"
        )

        self.assertEqual(len(folds), 32)
        self.assertEqual(len(full), 4)
        self.assertEqual(len(stability), 8)
        self.assertEqual(set(folds["model"]), {"rbf", "matern32"})
        self.assertEqual(set(full["model"]), {"matern32"})
        self.assertEqual(folds["decision_rule"].nunique(), 4)
        self.assertEqual(folds["fold_id"].nunique(), 4)
        self.assertTrue((folds["signal_variance"] > 0).all())
        self.assertTrue((folds["length_scale"] > 0).all())
        self.assertTrue((folds["noise_level"] >= 0).all())

        duplicate_audit = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_feature_response_duplicate_audit.csv"
        )
        self.assertGreaterEqual(len(duplicate_audit), 1)
        self.assertTrue(
            duplicate_audit[
                "values_consistent_within_1e_12"
            ].astype(bool).all()
        )
        self.assertLessEqual(
            float(duplicate_audit["target_spread"].fillna(0.0).max()),
            1e-12,
        )


if __name__ == "__main__":
    unittest.main()
