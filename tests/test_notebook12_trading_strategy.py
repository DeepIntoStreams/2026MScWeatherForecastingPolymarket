from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Notebook12TradingStrategyTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "12_trading_strategy_manifest.json"
            ).read_text(encoding="utf-8")
        )

        cls.candidates = pd.read_csv(
            "outputs/diagnostics/"
            "12_development_trading_candidate_summary.csv"
        )

        cls.locked_dates = pd.read_csv(
            "outputs/diagnostics/"
            "12_locked_trading_date_panel.csv"
        )

        cls.locked_trades = pd.read_csv(
            "outputs/diagnostics/"
            "12_locked_trading_trade_panel.csv"
        )

        cls.costs = pd.read_csv(
            "outputs/diagnostics/"
            "12_locked_trading_cost_sensitivity.csv"
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "12_trading_strategy_integrity_checks.csv"
        )

        cls.summary = pd.read_csv(
            "outputs/final_tables/"
            "12_trading_strategy_summary.csv"
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
            "TRADING_STRATEGY_LOCKED_AND_EVALUATED",
        )

    def test_balanced_development_support(
        self,
    ) -> None:
        self.assertGreaterEqual(
            self.manifest[
                "balanced_development_dates"
            ],
            20,
        )

        self.assertEqual(
            self.manifest[
                "balanced_development_books"
            ],
            4
            * self.manifest[
                "balanced_development_dates"
            ],
        )

    def test_single_selected_strategy(
        self,
    ) -> None:
        selected = self.as_bool(
            self.candidates[
                "selected_strategy"
            ]
        )

        self.assertEqual(
            int(selected.sum()),
            1,
        )

    def test_raw_market_prices_used(
        self,
    ) -> None:
        self.assertTrue(
            self.manifest[
                "raw_market_prices_used"
            ]
        )

        self.assertFalse(
            self.manifest[
                "categorically_normalised_market_prices_used"
            ]
        )

    def test_no_holdout_selection(
        self,
    ) -> None:
        self.assertFalse(
            self.manifest[
                "holdout_used_for_strategy_selection"
            ]
        )

        self.assertFalse(
            self.manifest[
                "external_test_used_for_strategy_selection"
            ]
        )

    def test_no_model_or_calibration_reselection(
        self,
    ) -> None:
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

    def test_no_external_refit(self) -> None:
        self.assertFalse(
            self.manifest[
                "strategy_refitted_before_external_test"
            ]
        )

    def test_one_position_per_date(
        self,
    ) -> None:
        trades = self.locked_dates.loc[
            self.as_bool(
                self.locked_dates["trade"]
            )
        ]

        duplicates = trades[
            [
                "target_date",
                "chronology_block",
            ]
        ].duplicated()

        self.assertFalse(
            duplicates.any()
        )

        self.assertEqual(
            self.manifest[
                "maximum_positions_per_settlement_date"
            ],
            1,
        )

    def test_evaluation_blocks(self) -> None:
        self.assertEqual(
            set(
                self.summary[
                    "chronology_block"
                ]
            ),
            {
                "holdout",
                "external_test",
            },
        )

    def test_calendar_date_counts(self) -> None:
        counts = (
            self.summary.set_index(
                "chronology_block"
            )["calendar_dates"]
            .to_dict()
        )

        self.assertEqual(
            int(counts["holdout"]),
            10,
        )

        self.assertEqual(
            int(counts["external_test"]),
            30,
        )

    def test_payoffs_are_finite(self) -> None:
        columns = [
            "cumulative_gross_payoff",
            "cumulative_net_payoff",
            "mean_calendar_date_net_payoff",
        ]

        self.assertTrue(
            np.isfinite(
                self.summary[
                    columns
                ].to_numpy(dtype=float)
            ).all()
        )

    def test_cost_sensitivity_blocks(
        self,
    ) -> None:
        self.assertEqual(
            set(
                self.costs[
                    "chronology_block"
                ]
            ),
            {
                "holdout",
                "external_test",
            },
        )

    def test_integrity_checks(self) -> None:
        self.assertTrue(
            self.as_bool(
                self.integrity["passed"]
            ).all()
        )


if __name__ == "__main__":
    unittest.main()
