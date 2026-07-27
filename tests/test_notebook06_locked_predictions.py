from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Notebook06LockedPredictionTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model_manifest = json.loads(
            Path(
                "data/manifests/"
                "04_model_selection_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.calibration_manifest = json.loads(
            Path(
                "data/manifests/"
                "05_continuous_calibration_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "06_locked_prediction_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.uncalibrated = pd.read_csv(
            "outputs/diagnostics/"
            "06_locked_uncalibrated_predictions.csv",
            low_memory=False,
        )

        cls.calibrated = pd.read_csv(
            "outputs/diagnostics/"
            "06_locked_calibrated_predictions.csv",
            low_memory=False,
        )

        cls.fit_log = pd.read_csv(
            "outputs/diagnostics/"
            "06_locked_prediction_fit_log.csv",
            low_memory=False,
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "06_locked_prediction_integrity_checks.csv",
            low_memory=False,
        )

    def test_lineage_matches_locked_choices(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest[
                "selected_model"
            ],
            self.model_manifest[
                "selected_model"
            ],
        )

        self.assertEqual(
            self.manifest[
                "selected_family"
            ],
            self.model_manifest[
                "selected_family"
            ],
        )

        self.assertAlmostEqual(
            float(
                self.manifest[
                    "selected_dispersion_scale"
                ]
            ),
            float(
                self.calibration_manifest[
                    "selected_scale"
                ]
            ),
            places=12,
        )

    def test_locked_prediction_dimensions(
        self,
    ) -> None:
        self.assertEqual(
            len(self.calibrated),
            159,
        )

        self.assertEqual(
            self.calibrated[
                "target_date"
            ].nunique(),
            40,
        )

        self.assertEqual(
            int(
                self.calibrated[
                    "chronology_block"
                ].eq(
                    "holdout"
                ).sum()
            ),
            40,
        )

        self.assertEqual(
            int(
                self.calibrated[
                    "chronology_block"
                ].eq(
                    "external_test"
                ).sum()
            ),
            119,
        )

    def test_training_precedes_holdout(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest[
                "training_rows"
            ],
            216,
        )

        self.assertEqual(
            self.manifest[
                "training_dates"
            ],
            62,
        )

        self.assertLess(
            self.manifest[
                "training_end"
            ],
            self.calibrated.loc[
                self.calibrated[
                    "chronology_block"
                ].eq(
                    "holdout"
                ),
                "target_date",
            ].min(),
        )

    def test_prediction_files_contain_no_outcomes_or_scores(
        self,
    ) -> None:
        prohibited_fragments = (
            "hko_daily_max",
            "residual",
            "outcome",
            "realised",
            "realized",
            "crps",
            "brier",
            "log_score",
            "pnl",
            "profit",
            "market_price",
        )

        for frame in (
            self.uncalibrated,
            self.calibrated,
        ):
            prohibited = [
                column
                for column in frame.columns
                if any(
                    fragment in column.lower()
                    for fragment in prohibited_fragments
                )
            ]

            self.assertEqual(
                prohibited,
                [],
            )

    def test_quantiles_are_finite_and_monotone(
        self,
    ) -> None:
        quantile_columns = [
            f"q_{index:02d}"
            for index in range(
                1,
                100,
            )
        ]

        self.assertTrue(
            set(
                quantile_columns
            ).issubset(
                self.calibrated.columns
            )
        )

        values = self.calibrated[
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

    def test_calibration_preserves_median(
        self,
    ) -> None:
        raw = (
            self.uncalibrated.set_index(
                "row_id"
            )[
                "q_50"
            ]
        )

        calibrated = (
            self.calibrated.set_index(
                "row_id"
            )[
                "q_50"
            ]
        )

        calibrated = calibrated.loc[
            raw.index
        ]

        maximum_change = float(
            np.max(
                np.abs(
                    raw.to_numpy(
                        dtype=float
                    )
                    - calibrated.to_numpy(
                        dtype=float
                    )
                )
            )
        )

        self.assertLessEqual(
            maximum_change,
            1.0e-12,
        )

    def test_no_forecast_lookahead(
        self,
    ) -> None:
        issue = pd.to_datetime(
            self.calibrated[
                "forecast_issue_time_utc"
            ],
            utc=True,
        )

        decision = pd.to_datetime(
            self.calibrated[
                "decision_time_utc"
            ],
            utc=True,
        )

        self.assertTrue(
            issue.notna().all()
        )

        self.assertTrue(
            decision.notna().all()
        )

        self.assertTrue(
            (issue <= decision).all()
        )

        self.assertTrue(
            self.calibrated[
                "unique_local_hours"
            ].eq(24).all()
        )

    def test_final_fit_has_no_failures(
        self,
    ) -> None:
        self.assertFalse(
            self.fit_log.empty
        )

        self.assertTrue(
            self.fit_log[
                "status"
            ].astype(str).eq(
                "OK"
            ).all()
        )

        self.assertEqual(
            self.manifest[
                "final_fit_non_ok_records"
            ],
            0,
        )

    def test_evaluation_boundary_is_preserved(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest["status"],
            "LOCKED_HOLDOUT_AND_EXTERNAL_PREDICTIONS_GENERATED",
        )

        self.assertTrue(
            self.manifest[
                "predictions_locked"
            ]
        )

        self.assertFalse(
            self.manifest[
                "holdout_outcomes_used_for_fit"
            ]
        )

        self.assertFalse(
            self.manifest[
                "external_test_outcomes_used_for_fit"
            ]
        )

        self.assertFalse(
            self.manifest[
                "continuous_scores_calculated"
            ]
        )

        self.assertFalse(
            self.manifest[
                "event_probabilities_calculated"
            ]
        )

        self.assertFalse(
            self.manifest[
                "market_data_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "trading_returns_calculated"
            ]
        )

        passed = (
            self.integrity[
                "passed"
            ].astype(str)
            .str.lower()
            .isin(
                {
                    "true",
                    "1",
                }
            )
        )

        self.assertTrue(
            passed.all()
        )


if __name__ == "__main__":
    unittest.main()
