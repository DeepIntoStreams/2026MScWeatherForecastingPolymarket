from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


class Notebook08EventProbabilityTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prediction_manifest = json.loads(
            Path(
                "data/manifests/"
                "06_locked_prediction_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.evaluation_manifest = json.loads(
            Path(
                "data/manifests/"
                "07_continuous_evaluation_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "08_event_probability_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.panel = pd.read_csv(
            "outputs/diagnostics/"
            "08_locked_event_probability_panel.csv",
            low_memory=False,
        )

        cls.summary = pd.read_csv(
            "outputs/diagnostics/"
            "08_event_probability_book_summary.csv",
            low_memory=False,
        )

        cls.integrity = pd.read_csv(
            "outputs/diagnostics/"
            "08_event_probability_integrity_checks.csv",
            low_memory=False,
        )

    def test_status_and_locked_lineage(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest["status"],
            "LOCKED_EVENT_PROBABILITY_CONSTRUCTION_COMPLETE",
        )

        self.assertTrue(
            self.manifest[
                "probability_construction_locked"
            ]
        )

        self.assertEqual(
            self.manifest[
                "selected_model"
            ],
            self.prediction_manifest[
                "selected_model"
            ],
        )

        self.assertAlmostEqual(
            float(
                self.manifest[
                    "selected_dispersion_scale"
                ]
            ),
            float(
                self.prediction_manifest[
                    "selected_dispersion_scale"
                ]
            ),
            places=12,
        )

    def test_probability_panel_dimensions(
        self,
    ) -> None:
        self.assertEqual(
            len(self.panel),
            1749,
        )

        self.assertEqual(
            self.panel[
                "row_id"
            ].nunique(),
            159,
        )

        self.assertEqual(
            self.panel[
                "target_date"
            ].nunique(),
            40,
        )

    def test_each_prediction_has_eleven_events(
        self,
    ) -> None:
        counts = self.panel.groupby(
            "row_id"
        ).size()

        self.assertTrue(
            counts.eq(
                11
            ).all()
        )

    def test_probability_books_sum_to_one(
        self,
    ) -> None:
        sums = self.panel.groupby(
            "row_id"
        )[
            "raw_event_probability"
        ].sum()

        self.assertTrue(
            np.allclose(
                sums.to_numpy(
                    dtype=float
                ),
                1.0,
                atol=1.0e-12,
                rtol=0.0,
            )
        )

    def test_particle_counts_define_probabilities(
        self,
    ) -> None:
        counts = self.panel[
            "quantile_particle_count"
        ].to_numpy(
            dtype=float
        )

        probabilities = self.panel[
            "raw_event_probability"
        ].to_numpy(
            dtype=float
        )

        self.assertTrue(
            np.allclose(
                counts / 99.0,
                probabilities,
                atol=1.0e-12,
                rtol=0.0,
            )
        )

        count_sums = self.panel.groupby(
            "row_id"
        )[
            "quantile_particle_count"
        ].sum()

        self.assertTrue(
            count_sums.eq(
                99
            ).all()
        )

    def test_probabilities_are_finite_and_bounded(
        self,
    ) -> None:
        values = self.panel[
            "raw_event_probability"
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
                (
                    values >= 0.0
                )
                & (
                    values <= 1.0
                )
            ).all()
        )

    def test_partition_has_one_lower_and_upper_tail(
        self,
    ) -> None:
        lower = self.panel.groupby(
            "row_id"
        )[
            "lower_unbounded"
        ].sum()

        upper = self.panel.groupby(
            "row_id"
        )[
            "upper_unbounded"
        ].sum()

        self.assertTrue(
            lower.eq(
                1
            ).all()
        )

        self.assertTrue(
            upper.eq(
                1
            ).all()
        )

    def test_no_duplicate_row_event_keys(
        self,
    ) -> None:
        self.assertFalse(
            self.panel[
                [
                    "row_id",
                    "event_order",
                ]
            ].duplicated().any()
        )

    def test_no_outcomes_scores_prices_or_regularisation(
        self,
    ) -> None:
        self.assertFalse(
            self.manifest[
                "probability_regularisation_applied"
            ]
        )

        self.assertFalse(
            self.manifest[
                "realised_outcomes_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "categorical_scores_calculated"
            ]
        )

        self.assertFalse(
            self.manifest[
                "market_prices_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "trading_returns_calculated"
            ]
        )

        self.assertTrue(
            (
                ~self.panel[
                    "probability_regularised"
                ].astype(bool)
            ).all()
        )

        self.assertTrue(
            (
                ~self.panel[
                    "market_price_accessed"
                ].astype(bool)
            ).all()
        )

        self.assertTrue(
            (
                ~self.panel[
                    "outcome_accessed"
                ].astype(bool)
            ).all()
        )

        self.assertTrue(
            (
                ~self.panel[
                    "score_calculated"
                ].astype(bool)
            ).all()
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
