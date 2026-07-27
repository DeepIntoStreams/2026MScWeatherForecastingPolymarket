from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Notebook10CategoricalEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "10_categorical_evaluation_manifest.json"
            ).read_text(encoding="utf-8")
        )

        cls.outcomes = pd.read_csv(
            "outputs/diagnostics/"
            "10_locked_event_probability_outcome_panel.csv"
        )

        cls.scores = pd.read_csv(
            "outputs/diagnostics/"
            "10_locked_categorical_score_panel.csv"
        )

        cls.summary = pd.read_csv(
            "outputs/final_tables/"
            "10_locked_categorical_block_summary.csv"
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "10_locked_categorical_integrity_checks.csv"
        )

    @staticmethod
    def as_bool(series: pd.Series) -> pd.Series:
        return (
            series.astype(str)
            .str.strip()
            .str.lower()
            .isin({"true", "1", "yes", "y"})
        )

    def test_status_and_locked_lineage(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "LOCKED_CATEGORICAL_EVALUATION_COMPLETE",
        )

        self.assertEqual(
            self.manifest["selected_model"],
            "pooled_empirical_residual",
        )

        self.assertAlmostEqual(
            float(
                self.manifest[
                    "locked_continuous_dispersion_scale"
                ]
            ),
            1.25,
            places=12,
        )

        self.assertAlmostEqual(
            float(
                self.manifest[
                    "locked_uniform_mixing_lambda"
                ]
            ),
            0.01,
            places=12,
        )

    def test_complete_dimensions(self) -> None:
        self.assertEqual(len(self.outcomes), 1749)
        self.assertEqual(len(self.scores), 159)

        self.assertEqual(
            self.scores["row_id"].nunique(),
            159,
        )

        self.assertEqual(
            self.scores["target_date"].nunique(),
            40,
        )

    def test_block_dimensions(self) -> None:
        indexed = self.summary.set_index(
            "chronology_block"
        )

        self.assertEqual(
            int(indexed.loc["holdout", "dates"]),
            10,
        )

        self.assertEqual(
            int(
                indexed.loc[
                    "holdout",
                    "probability_books",
                ]
            ),
            40,
        )

        self.assertEqual(
            int(
                indexed.loc[
                    "external_test",
                    "dates",
                ]
            ),
            30,
        )

        self.assertEqual(
            int(
                indexed.loc[
                    "external_test",
                    "probability_books",
                ]
            ),
            119,
        )

    def test_exact_outcome_join(self) -> None:
        event_order = pd.to_numeric(
            self.outcomes["event_order"],
            errors="raise",
        )

        event_index = pd.to_numeric(
            self.outcomes["event_index"],
            errors="raise",
        )

        self.assertTrue(
            event_order.eq(event_index + 1).all()
        )

        winners = self.outcomes.groupby(
            "row_id"
        )[
            "realised_yes"
        ].apply(
            lambda values: int(
                self.as_bool(values).sum()
            )
        )

        self.assertTrue(winners.eq(1).all())

    def test_probability_books_sum_to_one(self) -> None:
        sums = self.outcomes.groupby(
            "row_id"
        )[
            "regularised_event_probability"
        ].sum()

        self.assertTrue(
            np.allclose(
                sums.to_numpy(dtype=float),
                1.0,
                atol=1.0e-12,
                rtol=0.0,
            )
        )

    def test_regularised_log_scores_are_finite(self) -> None:
        self.assertTrue(
            np.isfinite(
                self.scores[
                    "regularised_categorical_log_score"
                ].to_numpy(dtype=float)
            ).all()
        )

    def test_one_external_raw_zero_probability(self) -> None:
        external = self.scores.loc[
            self.scores[
                "chronology_block"
            ].eq("external_test")
        ]

        finite = self.as_bool(
            external["raw_log_score_finite"]
        )

        self.assertEqual(
            int((~finite).sum()),
            1,
        )

        holdout = self.scores.loc[
            self.scores[
                "chronology_block"
            ].eq("holdout")
        ]

        self.assertTrue(
            self.as_bool(
                holdout["raw_log_score_finite"]
            ).all()
        )

    def test_regularisation_has_small_brier_cost(self) -> None:
        difference = pd.to_numeric(
            self.summary[
                "mean_date_brier_difference_regularised_minus_raw"
            ],
            errors="raise",
        )

        self.assertTrue((difference > 0.0).all())
        self.assertTrue((difference < 0.01).all())

    def test_no_reselection_or_market_access(self) -> None:
        self.assertFalse(
            self.manifest["model_reselected"]
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
            self.manifest["market_prices_accessed"]
        )

        self.assertFalse(
            self.manifest["trading_returns_calculated"]
        )

    def test_all_integrity_checks_pass(self) -> None:
        self.assertTrue(
            self.as_bool(
                self.integrity["passed"]
            ).all()
        )


if __name__ == "__main__":
    unittest.main()
