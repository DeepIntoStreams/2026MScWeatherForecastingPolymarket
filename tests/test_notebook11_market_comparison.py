from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Notebook11MarketComparisonTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "11_market_comparison_manifest.json"
            ).read_text(encoding="utf-8")
        )

        cls.alias_audit = json.loads(
            Path(
                "outputs/diagnostics/"
                "11_market_alias_difference_audit.json"
            ).read_text(encoding="utf-8")
        )

        cls.probabilities = pd.read_csv(
            "outputs/diagnostics/"
            "11_common_support_probability_panel.csv"
        )

        cls.book_scores = pd.read_csv(
            "outputs/diagnostics/"
            "11_common_support_book_score_panel.csv"
        )

        cls.date_scores = pd.read_csv(
            "outputs/diagnostics/"
            "11_common_support_date_score_panel.csv"
        )

        cls.missing = pd.read_csv(
            "outputs/diagnostics/"
            "11_common_support_missing_books.csv"
        )

        cls.summary = pd.read_csv(
            "outputs/final_tables/"
            "11_common_support_block_summary.csv"
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "11_common_support_integrity_checks.csv"
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
            "COMMON_SUPPORT_MARKET_COMPARISON_COMPLETE",
        )

    def test_market_source(self) -> None:
        self.assertTrue(
            self.manifest[
                "market_source_certified"
            ]
        )

        self.assertEqual(
            self.manifest[
                "market_price_column"
            ],
            "p_market",
        )

    def test_canonical_precedence(self) -> None:
        self.assertTrue(
            self.manifest[
                "canonical_source_precedence"
            ]
        )

        self.assertFalse(
            self.manifest[
                "exact_alias_equivalence_required"
            ]
        )

        self.assertTrue(
            self.alias_audit[
                "canonical_source_certified"
            ]
        )

    def test_eleven_events_per_book(self) -> None:
        sizes = self.probabilities.groupby(
            "row_id"
        ).size()

        self.assertTrue(
            sizes.eq(11).all()
        )

    def test_probability_sums(self) -> None:
        model_sums = self.probabilities.groupby(
            "row_id"
        )[
            "model_probability"
        ].sum()

        market_sums = self.probabilities.groupby(
            "row_id"
        )[
            "market_probability_normalised"
        ].sum()

        self.assertTrue(
            np.allclose(
                model_sums.to_numpy(dtype=float),
                1.0,
                atol=1.0e-10,
                rtol=0.0,
            )
        )

        self.assertTrue(
            np.allclose(
                market_sums.to_numpy(dtype=float),
                1.0,
                atol=1.0e-10,
                rtol=0.0,
            )
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

    def test_missing_books_are_explicit(self) -> None:
        model_only = int(
            self.missing[
                "support_status"
            ].eq("model_only").sum()
        )

        market_only = int(
            self.missing[
                "support_status"
            ].eq("market_only").sum()
        )

        self.assertEqual(
            model_only,
            self.manifest[
                "model_only_books"
            ],
        )

        self.assertEqual(
            market_only,
            self.manifest[
                "market_only_books"
            ],
        )

    def test_scores_are_finite(self) -> None:
        columns = [
            "model_categorical_log_score",
            "market_categorical_log_score",
            "model_multiclass_brier_score",
            "market_multiclass_brier_score",
        ]

        self.assertTrue(
            np.isfinite(
                self.book_scores[
                    columns
                ].to_numpy(dtype=float)
            ).all()
        )

    def test_date_is_uncertainty_unit(self) -> None:
        self.assertEqual(
            self.manifest[
                "uncertainty_unit"
            ],
            "settlement_date",
        )

        self.assertFalse(
            self.date_scores[
                [
                    "chronology_block",
                    "target_date",
                ]
            ].duplicated().any()
        )

    def test_no_reselection(self) -> None:
        self.assertFalse(
            self.manifest[
                "market_prices_used_for_model_selection"
            ]
        )

        self.assertFalse(
            self.manifest[
                "model_reselected"
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

    def test_no_trading_calculation(self) -> None:
        self.assertFalse(
            self.manifest[
                "trading_strategy_selected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "trading_returns_calculated"
            ]
        )

    def test_integrity_checks(self) -> None:
        self.assertTrue(
            self.as_bool(
                self.integrity["passed"]
            ).all()
        )


if __name__ == "__main__":
    unittest.main()
