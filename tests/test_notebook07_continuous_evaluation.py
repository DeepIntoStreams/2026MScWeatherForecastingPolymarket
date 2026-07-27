from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_VARIANTS = {
    "raw_deterministic",
    "selected_uncalibrated",
    "selected_calibrated",
}


class Notebook07ContinuousEvaluationTests(
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

        cls.prediction_manifest = json.loads(
            Path(
                "data/manifests/"
                "06_locked_prediction_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "07_continuous_evaluation_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.panel = pd.read_csv(
            "outputs/diagnostics/"
            "07_continuous_prediction_and_outcome_panel.csv",
            low_memory=False,
        )

        cls.scores = pd.read_csv(
            "outputs/diagnostics/"
            "07_continuous_score_panel.csv",
            low_memory=False,
        )

        cls.date_scores = pd.read_csv(
            "outputs/diagnostics/"
            "07_continuous_date_score_panel.csv",
            low_memory=False,
        )

        cls.summary = pd.read_csv(
            "outputs/diagnostics/"
            "07_continuous_block_summary.csv",
            low_memory=False,
        )

        cls.pairwise = pd.read_csv(
            "outputs/diagnostics/"
            "07_continuous_pairwise_comparison.csv",
            low_memory=False,
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "07_continuous_integrity_checks.csv",
            low_memory=False,
        )

    def test_evaluation_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "LOCKED_CONTINUOUS_EVALUATION_COMPLETE",
        )

        self.assertTrue(
            self.manifest[
                "evaluation_locked"
            ]
        )

    def test_locked_lineage_is_unchanged(
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

        self.assertFalse(
            self.manifest[
                "model_refitted_during_evaluation"
            ]
        )

        self.assertFalse(
            self.manifest[
                "model_reselected_during_evaluation"
            ]
        )

        self.assertFalse(
            self.manifest[
                "calibration_reselected_during_evaluation"
            ]
        )

    def test_panel_dimensions(self) -> None:
        self.assertEqual(
            len(self.panel),
            477,
        )

        self.assertEqual(
            len(self.scores),
            477,
        )

        self.assertEqual(
            self.scores[
                "target_date"
            ].nunique(),
            40,
        )

        self.assertEqual(
            set(
                self.scores[
                    "forecast_variant"
                ]
            ),
            EXPECTED_VARIANTS,
        )

        self.assertFalse(
            self.scores[
                [
                    "row_id",
                    "forecast_variant",
                ]
            ].duplicated().any()
        )

    def test_evaluation_blocks(self) -> None:
        self.assertEqual(
            set(
                self.scores[
                    "chronology_block"
                ]
            ),
            {
                "holdout",
                "external_test",
            },
        )

        for variant in EXPECTED_VARIANTS:
            variant_scores = self.scores.loc[
                self.scores[
                    "forecast_variant"
                ].eq(
                    variant
                )
            ]

            self.assertEqual(
                int(
                    variant_scores[
                        "chronology_block"
                    ].eq(
                        "holdout"
                    ).sum()
                ),
                40,
            )

            self.assertEqual(
                int(
                    variant_scores[
                        "chronology_block"
                    ].eq(
                        "external_test"
                    ).sum()
                ),
                119,
            )

            self.assertEqual(
                variant_scores.loc[
                    variant_scores[
                        "chronology_block"
                    ].eq(
                        "holdout"
                    ),
                    "target_date",
                ].nunique(),
                10,
            )

            self.assertEqual(
                variant_scores.loc[
                    variant_scores[
                        "chronology_block"
                    ].eq(
                        "external_test"
                    ),
                    "target_date",
                ].nunique(),
                30,
            )

    def test_outcomes_are_complete_and_consistent(
        self,
    ) -> None:
        self.assertTrue(
            self.scores[
                "hko_daily_max_c"
            ].notna().all()
        )

        outcome_counts = (
            self.scores.groupby(
                "target_date"
            )[
                "hko_daily_max_c"
            ]
            .nunique()
        )

        self.assertTrue(
            outcome_counts.eq(1).all()
        )

    def test_scores_are_finite_and_nonnegative(
        self,
    ) -> None:
        values = self.scores[
            "crps_99q"
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
                values >= 0.0
            ).all()
        )

    def test_raw_crps_equals_absolute_error(
        self,
    ) -> None:
        raw = self.scores.loc[
            self.scores[
                "forecast_variant"
            ].eq(
                "raw_deterministic"
            )
        ]

        expected = np.abs(
            raw[
                "hko_daily_max_c"
            ].to_numpy(
                dtype=float
            )
            - raw[
                "forecast_daily_max_c"
            ].to_numpy(
                dtype=float
            )
        )

        observed = raw[
            "crps_99q"
        ].to_numpy(
            dtype=float
        )

        self.assertTrue(
            np.allclose(
                observed,
                expected,
                atol=1.0e-10,
                rtol=0.0,
            )
        )

    def test_date_is_primary_uncertainty_unit(
        self,
    ) -> None:
        expected_rows = (
            40
            * 3
        )

        self.assertEqual(
            len(self.date_scores),
            expected_rows,
        )

        counts = (
            self.date_scores.groupby(
                [
                    "chronology_block",
                    "forecast_variant",
                ]
            )[
                "target_date"
            ]
            .nunique()
        )

        self.assertTrue(
            counts.loc[
                "holdout"
            ].eq(10).all()
        )

        self.assertTrue(
            counts.loc[
                "external_test"
            ].eq(30).all()
        )

        self.assertEqual(
            self.manifest[
                "primary_uncertainty_unit"
            ],
            "settlement_date",
        )

    def test_block_summary_dimensions(
        self,
    ) -> None:
        self.assertEqual(
            len(self.summary),
            6,
        )

        combinations = set(
            zip(
                self.summary[
                    "chronology_block"
                ],
                self.summary[
                    "forecast_variant"
                ],
            )
        )

        expected = {
            (
                block,
                variant,
            )
            for block in {
                "holdout",
                "external_test",
            }
            for variant in EXPECTED_VARIANTS
        }

        self.assertEqual(
            combinations,
            expected,
        )

    def test_pairwise_comparisons(self) -> None:
        self.assertEqual(
            len(self.pairwise),
            6,
        )

        self.assertTrue(
            self.pairwise[
                "formal_significance_claim_permitted"
            ].astype(str)
            .str.lower()
            .isin(
                {
                    "false",
                    "0",
                }
            )
            .all()
        )

        self.assertTrue(
            self.pairwise[
                "mean_paired_crps_difference"
            ].notna().all()
        )

        self.assertTrue(
            self.pairwise[
                "descriptive_95_interval_lower"
            ].notna().all()
        )

        self.assertTrue(
            self.pairwise[
                "descriptive_95_interval_upper"
            ].notna().all()
        )

    def test_market_and_trading_boundary(
        self,
    ) -> None:
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

        self.assertFalse(
            self.manifest[
                "formal_significance_claim_made"
            ]
        )

    def test_all_integrity_checks_pass(
        self,
    ) -> None:
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
