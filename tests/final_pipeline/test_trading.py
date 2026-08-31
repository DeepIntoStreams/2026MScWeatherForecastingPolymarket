from __future__ import annotations

import json
import math
import unittest

from pathlib import Path

import numpy as np
import pandas as pd


POLICY = Path(
    "outputs/final_pipeline/trading/"
    "selected_trading_policy.json"
)

GRID = Path(
    "data/processed/final_pipeline/trading/"
    "development_threshold_grid.csv"
)

LEDGERS = Path(
    "data/processed/final_pipeline/trading/"
    "fixed_policy_ledgers.csv"
)

RISK = Path(
    "outputs/final_pipeline/trading/"
    "trading_risk_summary.csv"
)

STRESS = Path(
    "outputs/final_pipeline/trading/"
    "selected_gp_full_strategy_mean_shocks.csv"
)

DERIV = Path(
    "outputs/final_pipeline/trading/"
    "probability_derivative_validation.csv"
)

COST = Path(
    "outputs/final_pipeline/trading/"
    "selected_gp_cost_sensitivity.csv"
)

SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "trading_stage_summary.json"
)

CHECKS = Path(
    "outputs/final_pipeline/audit/"
    "trading_stage_integrity_checks.csv"
)


class TestFinalTradingStage(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(
            POLICY.read_text()
        )

        cls.grid = pd.read_csv(
            GRID
        )

        cls.ledgers = pd.read_csv(
            LEDGERS
        )

        cls.risk = pd.read_csv(
            RISK
        )

        cls.stress = pd.read_csv(
            STRESS
        )

        cls.deriv = pd.read_csv(
            DERIV
        )

        cls.cost = pd.read_csv(
            COST
        )

        cls.summary = json.loads(
            SUMMARY.read_text()
        )

        cls.checks = pd.read_csv(
            CHECKS
        )

    def test_stage_pass(self):
        self.assertEqual(
            self.summary[
                "status"
            ],
            "PASS",
        )

    def test_gp_signal_not_pool(self):
        self.assertEqual(
            self.policy[
                "selection_probability_source"
            ],
            "selected_gp",
        )

        self.assertFalse(
            self.policy[
                "pool_used_for_trading"
            ]
        )

    def test_development_only_selection(self):
        self.assertFalse(
            self.policy[
                "external_data_used_for_selection"
            ]
        )

    def test_reference_cost(self):
        self.assertTrue(
            math.isclose(
                self.policy[
                    "reference_cost_per_share"
                ],
                0.01,
                abs_tol=1e-15,
            )
        )

    def test_threshold_grid(self):
        h = self.policy[
            "selected_threshold"
        ]

        self.assertTrue(
            np.isclose(
                self.grid[
                    "threshold"
                ],
                h,
                atol=1e-14,
            ).any()
        )

        selected = self.grid[
            (
                self.grid[
                    "decision_rule"
                ]
                == self.policy[
                    "selected_rule"
                ]
            )
            & np.isclose(
                self.grid[
                    "threshold"
                ],
                h,
                atol=1e-14,
            )
        ]

        self.assertEqual(
            len(
                selected
            ),
            1,
        )

        self.assertGreaterEqual(
            int(
                selected.iloc[
                    0
                ][
                    "trade_count"
                ]
            ),
            10,
        )

    def test_one_row_per_date_method_period(self):
        self.assertFalse(
            self.ledgers[
                [
                    "event_date",
                    "empirical_period",
                    "probability_source",
                ]
            ]
            .duplicated()
            .any()
        )

    def test_fixed_pnl_identity(self):
        x = self.ledgers[
            self.ledgers[
                "target_available"
            ].astype(str)
            .str.lower()
            .eq(
                "true"
            )
            & self.ledgers[
                "trade"
            ].astype(str)
            .str.lower()
            .eq(
                "true"
            )
        ]

        self.assertTrue(
            np.allclose(
                x[
                    "net_pnl"
                ],
                (
                    x[
                        "Y"
                    ]
                    - x[
                        "market_raw_yes"
                    ]
                    - 0.01
                ),
                atol=1e-12,
            )
        )

    def test_external_method_support_same(self):
        x = self.ledgers[
            self.ledgers[
                "empirical_period"
            ]
            == "external_validation"
        ]

        sets = []

        for source in [
            "raw",
            "static",
            "selected_gp",
        ]:
            sets.append(
                set(
                    x.loc[
                        x[
                            "probability_source"
                        ]
                        == source,
                        "event_date",
                    ]
                )
            )

        self.assertEqual(
            sets[
                0
            ],
            sets[
                1
            ],
        )

        self.assertEqual(
            sets[
                1
            ],
            sets[
                2
            ],
        )

    def test_zero_stress_matches_gp_baseline(self):
        zero = self.stress[
            np.isclose(
                self.stress[
                    "mean_shift_c"
                ],
                0.0,
                atol=1e-14,
            )
        ]

        gp = self.risk[
            (
                self.risk[
                    "analysis_period"
                ]
                == "external_validation"
            )
            & (
                self.risk[
                    "probability_source"
                ]
                == "selected_gp"
            )
        ]

        self.assertEqual(
            len(
                zero
            ),
            1,
        )

        self.assertEqual(
            len(
                gp
            ),
            1,
        )

        self.assertTrue(
            math.isclose(
                float(
                    zero.iloc[
                        0
                    ][
                        "total_net_pnl"
                    ]
                ),
                float(
                    gp.iloc[
                        0
                    ][
                        "total_net_pnl"
                    ]
                ),
                abs_tol=1e-10,
            )
        )

    def test_probability_derivatives(self):
        self.assertLess(
            self.deriv[
                "probability_reconstruction_error"
            ]
            .abs()
            .max(),
            1e-10,
        )

        self.assertLess(
            self.deriv[
                "delta_error_vs_finite_difference"
            ]
            .abs()
            .max(),
            1e-7,
        )

    def test_cost_baseline_matches(self):
        cost = self.cost[
            np.isclose(
                self.cost[
                    "cost_per_trade"
                ],
                0.01,
                atol=1e-14,
            )
        ]

        gp = self.risk[
            (
                self.risk[
                    "analysis_period"
                ]
                == "external_validation"
            )
            & (
                self.risk[
                    "probability_source"
                ]
                == "selected_gp"
            )
        ]

        self.assertEqual(
            len(
                cost
            ),
            1,
        )

        self.assertTrue(
            math.isclose(
                float(
                    cost.iloc[
                        0
                    ][
                        "total_net_pnl"
                    ]
                ),
                float(
                    gp.iloc[
                        0
                    ][
                        "total_net_pnl"
                    ]
                ),
                abs_tol=1e-10,
            )
        )

    def test_integrity_checks(self):
        passed = (
            self.checks[
                "passed"
            ]
            .astype(str)
            .str.lower()
            .eq(
                "true"
            )
        )

        self.assertTrue(
            passed.all()
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
