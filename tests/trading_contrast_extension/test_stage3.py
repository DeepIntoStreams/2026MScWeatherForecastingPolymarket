import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


OUT = Path(
    "outputs/trading_contrast_extension/stage3"
)


class TestTradingContrastStage3(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (
                OUT
                / "stage3_summary.json"
            ).read_text()
        )

        cls.risk = pd.read_csv(
            OUT
            / "portfolio_risk_performance_summary.csv"
        )

        cls.external = pd.read_csv(
            OUT
            / "external_eight_portfolio_risk_table.csv"
        )

        cls.greeks = pd.read_csv(
            OUT
            / "event_probability_greeks.csv.gz"
        )

        cls.greek_summary = pd.read_csv(
            OUT
            / "portfolio_greek_risk_summary.csv"
        )

        cls.mass = pd.read_csv(
            OUT
            / "greek_probability_mass_checks.csv"
        )

        cls.stress = pd.read_csv(
            OUT
            / "temperature_stress_policy_summary.csv"
        )

        cls.zero = pd.read_csv(
            OUT
            / "zero_shift_policy_reproduction.csv"
        )

        cls.recon = pd.read_csv(
            OUT
            / "probability_reconstruction_checks.csv"
        )

    def test_stage_pass(self):
        self.assertEqual(
            self.summary["status"],
            "PASS",
        )

    def test_eight_external_portfolios(self):
        self.assertEqual(
            len(self.external),
            8,
        )

        self.assertEqual(
            set(
                self.external[
                    "strategy"
                ]
            ),
            {
                "fixed_settlement",
                "taec11",
            },
        )

        self.assertEqual(
            set(
                self.external[
                    "model"
                ]
            ),
            {
                "raw",
                "static",
                "rbf",
                "matern32",
            },
        )

    def test_risk_rows(self):
        self.assertEqual(
            len(self.risk),
            16,
        )

    def test_stage2_pnl_reconciliation(self):
        x = pd.read_csv(
            OUT
            / "stage2_stage3_pnl_reconciliation.csv"
        )

        self.assertTrue(
            x["passed"].all()
        )

    def test_zero_shift_reproduction(self):
        self.assertTrue(
            self.zero[
                "passed"
            ].all()
        )

        self.assertLessEqual(
            float(
                self.zero[
                    "absolute_difference"
                ].max()
            ),
            1e-10,
        )

    def test_predictive_law_reconstruction(self):
        self.assertTrue(
            self.recon[
                "passed"
            ].all()
        )

        self.assertLessEqual(
            float(
                self.recon[
                    "max_abs_error"
                ].max()
            ),
            1e-8,
        )

    def test_greek_steps(self):
        self.assertEqual(
            sorted(
                self.greeks[
                    "temperature_step_c"
                ].unique().tolist()
            ),
            [
                0.25,
                0.5,
                1.0,
            ],
        )

    def test_greek_delta_mass(self):
        self.assertLessEqual(
            float(
                self.mass[
                    "sum_delta"
                ].abs().max()
            ),
            1e-8,
        )

    def test_greek_gamma_mass(self):
        self.assertLessEqual(
            float(
                self.mass[
                    "sum_gamma"
                ].abs().max()
            ),
            1e-8,
        )

    def test_greek_summary_rows(self):
        self.assertEqual(
            len(
                self.greek_summary
            ),
            16,
        )

    def test_stress_grid(self):
        self.assertEqual(
            sorted(
                self.stress[
                    "temperature_shift_c"
                ].unique().tolist()
            ),
            [
                -1.0,
                -0.5,
                -0.25,
                0.0,
                0.25,
                0.5,
                1.0,
            ],
        )

    def test_taec_cost_identity_external(self):
        x = self.external.loc[
            self.external[
                "strategy"
            ]
            == "taec11"
        ]

        expected = (
            x[
                "total_net_pnl"
            ]
            + x[
                "total_transaction_cost"
            ]
        )

        self.assertTrue(
            np.allclose(
                expected,
                x[
                    "gross_pre_cost_pnl"
                ],
            )
        )

    def test_taec_all_positions_round_trip_cost(self):
        x = self.external.loc[
            self.external[
                "strategy"
            ]
            == "taec11"
        ]

        self.assertTrue(
            np.allclose(
                x[
                    "total_transaction_cost"
                ],
                x[
                    "positions"
                ]
                * 0.02,
            )
        )

    def test_fixed_all_positions_one_leg_cost(self):
        x = self.external.loc[
            self.external[
                "strategy"
            ]
            == "fixed_settlement"
        ]

        self.assertTrue(
            np.allclose(
                x[
                    "total_transaction_cost"
                ],
                x[
                    "positions"
                ]
                * 0.01,
            )
        )

    def test_rbf_distinctness_survives(self):
        stage2 = pd.read_csv(
            "outputs/trading_contrast_extension/stage2/"
            "canonical_four_model_event_panel.csv.gz"
        )

        d = (
            stage2[
                "p_rbf"
            ]
            - stage2[
                "p_static"
            ]
        ).abs()

        self.assertGreater(
            int(
                (
                    d > 1e-12
                ).sum()
            ),
            0,
        )

    def test_figures_exist(self):
        for filename in [
            "external_cumulative_pnl_fixed_settlement.png",
            "external_cumulative_pnl_taec11.png",
            "external_risk_return_scatter.png",
            "external_gross_probability_delta.png",
            "external_taec_convergence_diagnostics.png",
        ]:
            self.assertTrue(
                (
                    OUT
                    / filename
                ).exists()
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
