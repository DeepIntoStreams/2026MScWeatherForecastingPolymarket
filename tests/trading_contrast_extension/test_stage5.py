import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


OUT = Path("outputs/trading_contrast_extension/stage5")


class TestTradingContrastStage5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (OUT / "stage5_summary.json").read_text()
        )
        cls.cost = pd.read_csv(
            OUT / "transaction_cost_sensitivity.csv"
        )
        cls.break_even = pd.read_csv(
            OUT / "transaction_cost_break_even_summary.csv"
        )
        cls.threshold = pd.read_csv(
            OUT / "taec_threshold_sensitivity.csv"
        )
        cls.execution = pd.read_csv(
            OUT / "taec_open_only_execution_sensitivity.csv"
        )
        cls.concentration = pd.read_csv(
            OUT / "external_concentration_robustness.csv"
        )
        cls.monthly = pd.read_csv(
            OUT / "external_monthly_stability.csv"
        )
        cls.deletion = pd.read_csv(
            OUT / "external_seven_observation_deletion_summary.csv"
        )
        cls.paired_delete = pd.read_csv(
            OUT / "taec_minus_fixed_seven_observation_deletion.csv"
        )
        cls.block = pd.read_csv(
            OUT / "moving_block_length_sensitivity.csv"
        )
        cls.perturbation = pd.read_csv(
            OUT / "temperature_perturbation_robustness_summary.csv"
        )
        cls.cost_recon = pd.read_csv(
            OUT / "stage2_cost_baseline_reconciliation.csv"
        )
        cls.threshold_recon = pd.read_csv(
            OUT / "stage2_taec_threshold_reconciliation.csv"
        )

    def test_stage_pass(self):
        self.assertEqual(
            self.summary["status"],
            "PASS",
        )

    def test_cost_baseline_reproduction(self):
        self.assertTrue(
            self.cost_recon["passed"].all()
        )

    def test_threshold_baseline_reproduction(self):
        self.assertTrue(
            self.threshold_recon["passed"].all()
        )

    def test_cost_grid(self):
        self.assertEqual(
            sorted(
                self.cost["cost_per_position"].unique().tolist()
            ),
            [
                0.0,
                0.0025,
                0.005,
                0.0075,
                0.01,
                0.015,
                0.02,
                0.025,
                0.03,
                0.04,
                0.05,
            ],
        )

    def test_break_even_identity(self):
        x = self.break_even.loc[
            self.break_even["positions"] > 0
        ]
        expected = (
            x["gross_pre_cost_pnl"]
            / x["positions"]
        )
        self.assertTrue(
            np.allclose(
                expected,
                x["break_even_cost_per_position"],
            )
        )

    def test_threshold_grid(self):
        self.assertEqual(
            sorted(
                self.threshold["threshold"].unique().tolist()
            ),
            [
                0.01,
                0.015,
                0.02,
                0.025,
                0.03,
                0.04,
                0.05,
                0.075,
                0.10,
                0.15,
            ],
        )

    def test_threshold_diagnostic_only(self):
        self.assertTrue(
            self.threshold[
                "diagnostic_only_no_reselection"
            ].all()
        )

    def test_open_only_models(self):
        ext = self.execution.loc[
            self.execution["empirical_period"]
            == "external_validation"
        ]
        self.assertEqual(
            set(ext["model"]),
            {
                "raw",
                "static",
                "rbf",
                "matern32",
            },
        )

    def test_concentration_rows(self):
        self.assertEqual(
            len(self.concentration),
            8,
        )

    def test_months(self):
        self.assertEqual(
            set(self.monthly["month"]),
            {
                "2026-07",
                "2026-08",
            },
        )

    def test_deletion_rows(self):
        self.assertEqual(
            len(self.deletion),
            8,
        )
        self.assertEqual(
            len(self.paired_delete),
            4,
        )

    def test_block_lengths(self):
        self.assertEqual(
            sorted(
                self.block["block_length"].unique().tolist()
            ),
            [
                3,
                5,
                7,
                10,
                14,
            ],
        )

    def test_block_contrasts(self):
        self.assertEqual(
            set(self.block["contrast"]),
            {
                "taec_minus_fixed",
                "fixed_profitability",
                "precost_convergence",
            },
        )

    def test_primary_block_guard(self):
        self.assertTrue(
            self.block[
                "diagnostic_only_primary_block_remains_7"
            ].all()
        )

    def test_perturbation_rows(self):
        self.assertEqual(
            len(self.perturbation),
            8,
        )

    def test_perturbation_sign_boolean_is_scalar(self):
        self.assertTrue(
            self.perturbation[
                "local_sign_preserved"
            ].isin(
                [True, False]
            ).all()
        )

    def test_frozen_policy_guard(self):
        guards = self.summary[
            "frozen_policy_guards"
        ]
        self.assertFalse(
            guards[
                "external_diagnostics_may_reselect"
            ]
        )
        self.assertEqual(
            guards[
                "primary_bootstrap_block_length"
            ],
            7,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
