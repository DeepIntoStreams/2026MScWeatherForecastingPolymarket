from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Notebook13UncertaintyAnalysisTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "13_uncertainty_analysis_manifest.json"
            ).read_text(encoding="utf-8")
        )

        cls.date_effects = pd.read_csv(
            "outputs/diagnostics/"
            "13_uncertainty_date_effect_panel.csv"
        )

        cls.summary = pd.read_csv(
            "outputs/diagnostics/"
            "13_uncertainty_summary.csv"
        )

        cls.sign_flip = pd.read_csv(
            "outputs/diagnostics/"
            "13_sign_flip_summary.csv"
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "13_uncertainty_integrity_checks.csv"
        )

        cls.final_table = pd.read_csv(
            "outputs/final_tables/"
            "13_uncertainty_main_table.csv"
        )

    @staticmethod
    def as_bool(
        series: pd.Series,
    ) -> pd.Series:
        return (
            series.astype(str)
            .str.strip()
            .str.lower()
            .isin(
                {
                    "true",
                    "1",
                    "yes",
                    "y",
                }
            )
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "DATE_LEVEL_UNCERTAINTY_ANALYSIS_COMPLETE",
        )

    def test_uncertainty_unit(self) -> None:
        self.assertEqual(
            self.manifest[
                "uncertainty_unit"
            ],
            "settlement_date",
        )

    def test_six_estimands(self) -> None:
        self.assertEqual(
            self.manifest[
                "estimand_count"
            ],
            6,
        )

        self.assertEqual(
            set(
                self.summary[
                    "estimand"
                ]
            ),
            {
                "continuous_crps_improvement",
                "categorical_log_score_improvement",
                "categorical_brier_improvement",
                "model_minus_market_log_score_improvement",
                "model_minus_market_brier_improvement",
                "trading_net_payoff",
            },
        )

    def test_both_blocks_present(self) -> None:
        expected = {
            "holdout",
            "external_test",
        }

        self.assertEqual(
            set(
                self.summary[
                    "chronology_block"
                ]
            ),
            expected,
        )

        pairs = set(
            zip(
                self.summary[
                    "estimand"
                ],
                self.summary[
                    "chronology_block"
                ],
            )
        )

        self.assertEqual(
            len(pairs),
            12,
        )

    def test_date_effect_keys_unique(
        self,
    ) -> None:
        duplicates = (
            self.date_effects.duplicated(
                [
                    "estimand",
                    "chronology_block",
                    "target_date",
                ]
            )
        )

        self.assertFalse(
            duplicates.any()
        )

    def test_effects_finite(self) -> None:
        self.assertTrue(
            np.isfinite(
                self.date_effects[
                    "effect"
                ].to_numpy(
                    dtype=float
                )
            ).all()
        )

    def test_minimum_dates(self) -> None:
        self.assertTrue(
            self.summary[
                "settlement_dates"
            ].ge(5).all()
        )

    def test_bootstrap_intervals_ordered(
        self,
    ) -> None:
        self.assertTrue(
            (
                self.summary[
                    "bootstrap_lower"
                ]
                <= self.summary[
                    "bootstrap_median"
                ]
            ).all()
        )

        self.assertTrue(
            (
                self.summary[
                    "bootstrap_median"
                ]
                <= self.summary[
                    "bootstrap_upper"
                ]
            ).all()
        )

    def test_bootstrap_probability_valid(
        self,
    ) -> None:
        self.assertTrue(
            self.summary[
                "bootstrap_probability_positive"
            ].between(
                0.0,
                1.0,
                inclusive="both",
            ).all()
        )

    def test_sign_flip_p_values_valid(
        self,
    ) -> None:
        self.assertTrue(
            self.sign_flip[
                "sign_flip_two_sided_p_value"
            ].between(
                0.0,
                1.0,
                inclusive="both",
            ).all()
        )

    def test_exact_holdout_sign_flip(
        self,
    ) -> None:
        holdout = self.sign_flip.loc[
            self.sign_flip[
                "chronology_block"
            ].eq("holdout")
        ]

        self.assertTrue(
            holdout[
                "sign_flip_method"
            ].eq("exact").all()
        )

    def test_no_reselection(self) -> None:
        self.assertFalse(
            self.manifest[
                "weather_model_reselected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "continuous_calibration_reselected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "probability_calibration_reselected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "trading_strategy_reselected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "strategy_refitted_before_external_test"
            ]
        )

    def test_no_overclaim(self) -> None:
        self.assertFalse(
            self.manifest[
                "formal_population_inference_claimed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "market_inefficiency_claimed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "executable_profitability_claimed"
            ]
        )

    def test_integrity_checks(self) -> None:
        self.assertTrue(
            self.as_bool(
                self.integrity["passed"]
            ).all()
        )

    def test_final_table_dimensions(
        self,
    ) -> None:
        self.assertEqual(
            len(
                self.final_table
            ),
            12,
        )


if __name__ == "__main__":
    unittest.main()
