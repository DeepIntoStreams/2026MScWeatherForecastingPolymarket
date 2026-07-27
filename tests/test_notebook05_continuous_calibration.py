from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def as_boolean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "yes",
            }
        )
    )


class Notebook05ContinuousCalibrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(
            Path(
                "config/"
                "continuous_calibration_spec.yaml"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.model_manifest = json.loads(
            Path(
                "data/manifests/"
                "04_model_selection_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "05_continuous_calibration_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.raw_predictions = pd.read_csv(
            "outputs/diagnostics/"
            "04_oof_model_predictions.csv",
            low_memory=False,
        )

        cls.candidate_predictions = pd.read_csv(
            "outputs/diagnostics/"
            "05_calibration_candidate_predictions.csv",
            low_memory=False,
        )

        cls.summary = pd.read_csv(
            "outputs/diagnostics/"
            "05_calibration_candidate_summary.csv",
            low_memory=False,
        )

        cls.selected_predictions = pd.read_csv(
            "outputs/diagnostics/"
            "05_selected_oof_calibrated_predictions.csv",
            low_memory=False,
        )

    def test_calibration_status_and_locked_periods(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest["status"],
            "DEVELOPMENT_CONTINUOUS_CALIBRATION_COMPLETE",
        )

        self.assertTrue(
            self.manifest[
                "calibration_locked"
            ]
        )

        self.assertFalse(
            self.manifest[
                "holdout_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "external_test_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "market_data_accessed"
            ]
        )

    def test_candidate_scales_match_predeclared_grid(
        self,
    ) -> None:
        declared = {
            float(value)
            for value in self.config[
                "candidate_scales"
            ]
        }

        observed = {
            float(value)
            for value in self.summary[
                "dispersion_scale"
            ]
        }

        self.assertEqual(
            declared,
            observed,
        )

        self.assertIn(
            1.0,
            observed,
        )

        self.assertEqual(
            len(observed),
            7,
        )

    def test_only_selected_model_development_rows_used(
        self,
    ) -> None:
        self.assertTrue(
            self.candidate_predictions[
                "candidate_model"
            ].eq(
                self.model_manifest[
                    "selected_model"
                ]
            ).all()
        )

        self.assertTrue(
            self.candidate_predictions[
                "chronology_block"
            ].eq(
                "development_validation"
            ).all()
        )

        self.assertEqual(
            self.selected_predictions[
                "target_date"
            ].nunique(),
            self.manifest[
                "development_dates"
            ],
        )

    def test_selected_quantiles_are_finite_and_monotone(
        self,
    ) -> None:
        quantile_columns = [
            f"q_{index:02d}"
            for index in range(
                1,
                100,
            )
        ]

        values = self.selected_predictions[
            quantile_columns
        ].to_numpy(
            dtype=float
        )

        self.assertTrue(
            np.isfinite(
                values
            ).all()
        )

        self.assertTrue(
            (
                np.diff(
                    values,
                    axis=1,
                )
                >= -1.0e-10
            ).all()
        )

    def test_predictive_median_is_unchanged(
        self,
    ) -> None:
        selected_model = self.model_manifest[
            "selected_model"
        ]

        raw = (
            self.raw_predictions.loc[
                self.raw_predictions[
                    "candidate_model"
                ].eq(
                    selected_model
                ),
                [
                    "row_id",
                    "q_50",
                ],
            ]
            .drop_duplicates(
                "row_id"
            )
            .set_index(
                "row_id"
            )
        )

        calibrated = (
            self.selected_predictions[
                [
                    "row_id",
                    "q_50",
                ]
            ]
            .drop_duplicates(
                "row_id"
            )
            .set_index(
                "row_id"
            )
        )

        common = raw.index.intersection(
            calibrated.index
        )

        self.assertEqual(
            len(common),
            len(calibrated),
        )

        maximum_change = np.max(
            np.abs(
                raw.loc[
                    common,
                    "q_50",
                ].to_numpy(
                    dtype=float
                )
                - calibrated.loc[
                    common,
                    "q_50",
                ].to_numpy(
                    dtype=float
                )
            )
        )

        self.assertLessEqual(
            float(maximum_change),
            1.0e-12,
        )

    def test_selected_scale_satisfies_parsimony_rule(
        self,
    ) -> None:
        eligible_mask = as_boolean(
            self.summary[
                "within_one_standard_error"
            ]
        )

        selected_mask = as_boolean(
            self.summary[
                "selected_scale"
            ]
        )

        eligible = self.summary.loc[
            eligible_mask
        ]

        selected = self.summary.loc[
            selected_mask
        ]

        self.assertEqual(
            len(selected),
            1,
        )

        self.assertTrue(
            bool(
                as_boolean(
                    selected[
                        "within_one_standard_error"
                    ]
                ).iloc[0]
            )
        )

        self.assertAlmostEqual(
            float(
                selected.iloc[0][
                    "distance_from_identity"
                ]
            ),
            float(
                eligible[
                    "distance_from_identity"
                ].min()
            ),
            places=12,
        )

        self.assertAlmostEqual(
            float(
                selected.iloc[0][
                    "dispersion_scale"
                ]
            ),
            float(
                self.manifest[
                    "selected_scale"
                ]
            ),
            places=12,
        )

    def test_selected_model_fits_have_no_failures(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest[
                "selected_model_non_ok_fit_records"
            ],
            0,
        )


if __name__ == "__main__":
    unittest.main()
