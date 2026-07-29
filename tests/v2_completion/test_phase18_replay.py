from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


class Phase18ReplayTest(unittest.TestCase):
    def test_exact_replay_reconciles(self) -> None:
        root = Path(__file__).resolve().parents[2]
        reconciliation = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_replay_prediction_reconciliation.csv"
        )
        folds = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase18_gp_fold_hyperparameters.csv"
        )
        specification = json.loads(
            (
                root
                / "config/v2_completion/"
                / "phase18_gp_stability_spec.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(len(folds), 32)
        self.assertTrue((reconciliation["status"] == "PASSED").all())
        self.assertLessEqual(
            float(reconciliation["maximum_absolute_error"].max()),
            1e-8,
        )
        self.assertEqual(
            specification["exact_phase7_replay"]["status"],
            "PASSED",
        )


if __name__ == "__main__":
    unittest.main()
