from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Notebook09ProbabilityCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "09_probability_calibration_manifest.json"
            ).read_text(encoding="utf-8")
        )

        cls.grid = pd.read_csv(
            "outputs/diagnostics/"
            "09_probability_mixing_grid_scores.csv"
        )

        cls.development = pd.read_csv(
            "outputs/diagnostics/"
            "09_development_regularised_event_probability_panel.csv"
        )

        cls.locked = pd.read_csv(
            "outputs/diagnostics/"
            "09_locked_regularised_event_probability_panel.csv"
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "09_probability_calibration_integrity_checks.csv"
        )

    @staticmethod
    def as_bool(series: pd.Series) -> pd.Series:
        return (
            series.astype(str)
            .str.strip()
            .str.lower()
            .isin({"true", "1"})
        )

    def test_status_and_locked_lineage(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "PROBABILITY_CALIBRATION_LOCKED",
        )

        self.assertTrue(
            self.manifest["probability_calibration_locked"]
        )

        self.assertEqual(
            self.manifest["selected_model"],
            "pooled_empirical_residual",
        )

        self.assertEqual(
            self.manifest["selected_family"],
            "empirical_residual",
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

    def test_correct_development_source(self) -> None:
        self.assertEqual(
            self.manifest["development_source"],
            (
                "outputs/diagnostics/"
                "05_selected_oof_calibrated_predictions.csv"
            ),
        )

        self.assertTrue(
            self.manifest[
                "development_source_is_calibrated_oof"
            ]
        )

        self.assertFalse(
            self.manifest[
                "uncalibrated_notebook04_source_used"
            ]
        )

    def test_development_support(self) -> None:
        self.assertEqual(
            self.manifest["development_dates"],
            38,
        )

        self.assertEqual(
            self.manifest["development_date_rule_rows"],
            152,
        )

        self.assertEqual(
            self.manifest["development_probability_rows"],
            1672,
        )

        self.assertEqual(
            self.development["row_id"].nunique(),
            152,
        )

        self.assertEqual(
            self.development["target_date"].nunique(),
            38,
        )

    def test_complete_lambda_grid(self) -> None:
        self.assertEqual(
            len(self.grid),
            101,
        )

        self.assertAlmostEqual(
            float(self.grid["mixing_lambda"].min()),
            0.00,
            places=12,
        )

        self.assertAlmostEqual(
            float(self.grid["mixing_lambda"].max()),
            1.00,
            places=12,
        )

    def test_one_standard_error_selection(self) -> None:
        strict_winner = self.grid.loc[
            self.as_bool(
                self.grid["strict_log_score_winner"]
            )
        ]

        selected = self.grid.loc[
            self.as_bool(
                self.grid["selected_lambda"]
            )
        ]

        eligible = self.grid.loc[
            self.as_bool(
                self.grid["within_one_standard_error"]
            )
        ]

        self.assertEqual(len(strict_winner), 1)
        self.assertEqual(len(selected), 1)

        self.assertAlmostEqual(
            float(
                strict_winner["mixing_lambda"].iloc[0]
            ),
            0.02,
            places=12,
        )

        self.assertAlmostEqual(
            float(
                selected["mixing_lambda"].iloc[0]
            ),
            0.01,
            places=12,
        )

        self.assertAlmostEqual(
            float(
                selected["mixing_lambda"].iloc[0]
            ),
            float(
                eligible["mixing_lambda"].min()
            ),
            places=12,
        )

        self.assertAlmostEqual(
            float(
                self.manifest[
                    "selected_uniform_mixing_lambda"
                ]
            ),
            0.01,
            places=12,
        )

    def test_date_is_uncertainty_unit(self) -> None:
        self.assertEqual(
            self.manifest["uncertainty_unit"],
            "settlement_date",
        )

        self.assertTrue(
            self.manifest[
                "decision_rules_aggregated_within_date"
            ]
        )

    def test_development_books_sum_to_one(self) -> None:
        sums = self.development.groupby(
            "row_id"
        )[
            "regularised_event_probability"
        ].sum()

        self.assertEqual(len(sums), 152)

        self.assertTrue(
            np.allclose(
                sums.to_numpy(dtype=float),
                1.0,
                atol=1.0e-12,
                rtol=0.0,
            )
        )

    def test_locked_dimensions_and_sums(self) -> None:
        self.assertEqual(
            len(self.locked),
            1749,
        )

        self.assertEqual(
            self.locked["row_id"].nunique(),
            159,
        )

        self.assertEqual(
            self.locked["target_date"].nunique(),
            40,
        )

        self.assertEqual(
            set(
                self.locked[
                    "chronology_block"
                ].unique()
            ),
            {"holdout", "external_test"},
        )

        sums = self.locked.groupby(
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

    def test_positive_mixing_removes_zero_probabilities(
        self,
    ) -> None:
        self.assertGreater(
            float(
                self.locked[
                    "regularised_event_probability"
                ].min()
            ),
            0.0,
        )

    def test_evidential_boundary(self) -> None:
        self.assertFalse(
            self.manifest[
                "holdout_outcomes_used_for_selection"
            ]
        )

        self.assertFalse(
            self.manifest[
                "external_test_outcomes_used_for_selection"
            ]
        )

        self.assertFalse(
            self.manifest[
                "holdout_scores_calculated"
            ]
        )

        self.assertFalse(
            self.manifest[
                "external_test_scores_calculated"
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
