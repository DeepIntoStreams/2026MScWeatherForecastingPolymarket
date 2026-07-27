from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


EXPECTED_MODELS = {
    "raw_deterministic",
    "pooled_mean_residual",
    "rule_mean_residual",
    "pooled_empirical_residual",
    "rule_empirical_residual",
    "rule_gp_rbf",
    "rule_gp_matern32",
    "pooled_catboost_quantile",
    "rule_catboost_quantile",
}


class Notebook04ModelSelectionTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(
            Path(
                "config/"
                "probabilistic_model_spec.yaml"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.predictions = pd.read_csv(
            "outputs/diagnostics/"
            "04_oof_model_predictions.csv",
            low_memory=False,
        )

        cls.scores = pd.read_csv(
            "outputs/diagnostics/"
            "04_oof_score_panel.csv",
            low_memory=False,
        )

        cls.summary = pd.read_csv(
            "outputs/diagnostics/"
            "04_candidate_score_summary.csv",
            low_memory=False,
        )

        cls.fit_log = pd.read_csv(
            "outputs/diagnostics/"
            "04_model_fit_log.csv",
            low_memory=False,
        )

        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "04_model_selection_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

    def test_nine_declared_candidates(self) -> None:
        declared = {
            candidate["name"]
            for candidate in self.config[
                "candidates"
            ]
        }

        observed = set(
            self.summary[
                "candidate_model"
            ]
        )

        self.assertEqual(
            declared,
            EXPECTED_MODELS,
        )

        self.assertEqual(
            observed,
            EXPECTED_MODELS,
        )

        self.assertEqual(
            self.manifest[
                "candidate_count"
            ],
            9,
        )

    def test_only_development_rows_are_scored(
        self,
    ) -> None:
        self.assertTrue(
            self.scores[
                "chronology_block"
            ].eq(
                "development_validation"
            ).all()
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

    def test_common_support_is_sufficient(
        self,
    ) -> None:
        self.assertGreaterEqual(
            self.manifest[
                "common_support_rows"
            ],
            120,
        )

        self.assertGreaterEqual(
            self.manifest[
                "common_support_dates"
            ],
            30,
        )

        expected_score_rows = (
            self.manifest[
                "common_support_rows"
            ]
            * 9
        )

        self.assertEqual(
            len(self.scores),
            expected_score_rows,
        )

    def test_predictions_have_99_monotone_quantiles(
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
                self.predictions.columns
            )
        )

        values = self.predictions[
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

    def test_fold_training_precedes_validation(
        self,
    ) -> None:
        relevant = self.fit_log.loc[
            self.fit_log[
                "training_end"
            ].notna()
            & self.fit_log[
                "validation_start"
            ].notna()
        ].copy()

        training_end = pd.to_datetime(
            relevant[
                "training_end"
            ],
            errors="raise",
        )

        validation_start = pd.to_datetime(
            relevant[
                "validation_start"
            ],
            errors="raise",
        )

        self.assertTrue(
            (
                training_end
                < validation_start
            ).all()
        )

    def test_selection_is_locked(self) -> None:
        self.assertTrue(
            self.manifest[
                "selection_locked"
            ]
        )

        self.assertIn(
            self.manifest[
                "strict_crps_winner"
            ],
            EXPECTED_MODELS,
        )

        self.assertIn(
            self.manifest[
                "selected_model"
            ],
            EXPECTED_MODELS,
        )

        selected_rows = self.summary.loc[
            self.summary[
                "parsimonious_selected_model"
            ].astype(bool)
        ]

        self.assertEqual(
            len(selected_rows),
            1,
        )

        self.assertEqual(
            selected_rows.iloc[0][
                "candidate_model"
            ],
            self.manifest[
                "selected_model"
            ],
        )

    def test_parsimony_selection_is_within_one_se(
        self,
    ) -> None:
        selected = self.summary.loc[
            self.summary[
                "candidate_model"
            ].eq(
                self.manifest[
                    "selected_model"
                ]
            )
        ].iloc[0]

        self.assertTrue(
            bool(
                selected[
                    "within_one_standard_error"
                ]
            )
        )

        eligible = self.summary.loc[
            self.summary[
                "within_one_standard_error"
            ].astype(bool)
        ]

        self.assertEqual(
            int(
                selected[
                    "complexity_rank"
                ]
            ),
            int(
                eligible[
                    "complexity_rank"
                ].min()
            ),
        )


if __name__ == "__main__":
    unittest.main()
