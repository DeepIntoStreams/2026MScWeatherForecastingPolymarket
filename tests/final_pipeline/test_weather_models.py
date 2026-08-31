from __future__ import annotations

import json
import unittest

from pathlib import Path

import numpy as np
import pandas as pd


VALIDATION = Path(
    "data/processed/final_pipeline/weather_models/"
    "chronological_validation_predictions.csv"
)

DATE_LOSSES = Path(
    "data/processed/final_pipeline/weather_models/"
    "chronological_validation_date_losses.csv"
)

FUTURE = Path(
    "data/processed/final_pipeline/weather_models/"
    "frozen_weather_model_predictions_mar_aug.csv"
)

FITS = Path(
    "outputs/final_pipeline/weather/models/"
    "gp_fit_ledger.csv"
)

FULL_FITS = Path(
    "outputs/final_pipeline/weather/models/"
    "full_history_fit_ledger.csv"
)

SELECTION = Path(
    "outputs/final_pipeline/weather/models/"
    "weather_kernel_selection.json"
)

VARIANCE = Path(
    "outputs/final_pipeline/audit/"
    "gp_predictive_variance_audit.json"
)

SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "weather_models_summary.json"
)


class TestWeatherModels(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.val = pd.read_csv(
            VALIDATION
        )

        cls.date_losses = (
            pd.read_csv(
                DATE_LOSSES
            )
        )

        cls.future = pd.read_csv(
            FUTURE
        )

        cls.fits = pd.read_csv(
            FITS
        )

        cls.full_fits = (
            pd.read_csv(
                FULL_FITS
            )
        )

        cls.selection = json.loads(
            SELECTION.read_text()
        )

        cls.variance = json.loads(
            VARIANCE.read_text()
        )

        cls.summary = json.loads(
            SUMMARY.read_text()
        )

    def test_summary_pass(self):
        self.assertEqual(
            self.summary[
                "status"
            ],
            "PASS",
        )

    def test_validation_fit_count(self):
        self.assertEqual(
            len(
                self.fits
            ),
            32,
        )

    def test_full_fit_count(self):
        self.assertEqual(
            len(
                self.full_fits
            ),
            8,
        )

    def test_no_validation_duplicate_keys(self):
        self.assertFalse(
            self.val[
                [
                    "target_date",
                    "decision_rule",
                ]
            ].duplicated().any()
        )

    def test_raw_crps_identity(self):
        expected = np.abs(
            self.val[
                "hko_daily_max_c"
            ]
            - self.val[
                "forecast_daily_max_c"
            ]
        )

        error = np.max(
            np.abs(
                expected
                - self.val[
                    "raw_crps_c"
                ]
            )
        )

        self.assertLess(
            float(error),
            1e-9,
        )

    def test_gaussian_scales_positive(self):
        self.assertTrue(
            (
                self.val[
                    [
                        "static_sd_c",
                        "rbf_sd_c",
                        "matern_sd_c",
                    ]
                ]
                > 0
            ).all().all()
        )

    def test_selection_uses_weather_only(self):
        self.assertIn(
            self.selection[
                "selected_kernel"
            ],
            {
                "rbf",
                "matern32",
            },
        )

        self.assertFalse(
            self.selection[
                "external_validation_used_for_selection"
            ]
        )

        self.assertFalse(
            self.selection[
                "market_prices_used_for_selection"
            ]
        )

        self.assertFalse(
            self.selection[
                "trading_pnl_used_for_selection"
            ]
        )

    def test_matern_prediction_schema(self):
        required = {
            "matern_mean_c",
            "matern_sd_c",
            "matern_crps_c",
            "matern_z",
            "matern_pit",
        }

        self.assertTrue(
            required.issubset(
                self.val.columns
            )
        )

        forbidden = {
            "matern32_mean_c",
            "matern32_sd_c",
            "matern32_crps_c",
            "matern32_z",
            "matern32_pit",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                self.val.columns
            )
        )

    def test_selection_equals_lower_validation_crps(self):
        means = self.selection[
            "mean_date_crps_c"
        ]

        expected = min(
            ["rbf", "matern32"],
            key=lambda x:
                means[x],
        )

        self.assertEqual(
            self.selection[
                "selected_kernel"
            ],
            expected,
        )

    def test_white_noise_variance_semantics(self):
        self.assertLess(
            abs(
                self.variance[
                    "software_minus_manual_observation"
                ]
            ),
            1e-8,
        )

        self.assertLess(
            abs(
                self.variance[
                    "noise_identity_error"
                ]
            ),
            1e-8,
        )

    def test_external_distributions_complete(self):
        external = self.future[
            self.future[
                "empirical_period"
            ]
            == "external_validation"
        ]

        self.assertEqual(
            len(
                external
            ),
            248,
        )

        self.assertFalse(
            external[
                "selected_gp_mean_c"
            ].isna().any()
        )

        self.assertFalse(
            external[
                "selected_gp_sd_c"
            ].isna().any()
        )

        self.assertTrue(
            (
                external[
                    "selected_gp_sd_c"
                ]
                > 0
            ).all()
        )

    def test_august_31_forecast_exists(self):
        x = self.future[
            self.future[
                "target_date"
            ]
            == "2026-08-31"
        ]

        self.assertEqual(
            len(x),
            4,
        )

        self.assertFalse(
            x[
                "selected_gp_mean_c"
            ].isna().any()
        )

    def test_validation_date_losses(self):
        self.assertEqual(
            len(
                self.date_losses
            ),
            self.val[
                "target_date"
            ].nunique(),
        )

        required = {
            "raw_date_crps_c",
            "static_date_crps_c",
            "rbf_date_crps_c",
            "matern32_date_crps_c",
        }

        self.assertTrue(
            required.issubset(
                self.date_losses.columns
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
