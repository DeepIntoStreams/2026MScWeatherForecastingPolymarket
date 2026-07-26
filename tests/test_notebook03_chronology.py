from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


class Notebook03ChronologyTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.panel = pd.read_csv(
            "data/processed/"
            "02_chronological_design_panel.csv"
        )

        cls.blocks = pd.read_csv(
            "outputs/diagnostics/"
            "03_chronology_block_summary.csv"
        )

        cls.folds = pd.read_csv(
            "outputs/diagnostics/"
            "03_development_fold_summary.csv"
        )

        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "03_chronology_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

    def test_all_rows_are_assigned(self) -> None:
        self.assertFalse(
            self.panel[
                "chronology_block"
            ].isna().any()
        )

        self.assertFalse(
            self.panel[
                "chronology_block"
            ].eq(
                "UNASSIGNED"
            ).any()
        )

    def test_external_block_contains_30_dates(self) -> None:
        external = self.blocks.loc[
            self.blocks[
                "chronology_block"
            ].eq(
                "external_test"
            )
        ]

        self.assertEqual(
            len(external),
            1,
        )

        self.assertEqual(
            int(
                external.iloc[0][
                    "dates"
                ]
            ),
            30,
        )

    def test_four_expanding_folds(self) -> None:
        self.assertEqual(
            len(self.folds),
            4,
        )

        self.assertTrue(
            self.folds[
                "date_sets_disjoint"
            ].all()
        )

        self.assertTrue(
            self.folds[
                "training_precedes_validation"
            ].all()
        )

    def test_locked_outcomes_do_not_influence_selection(
        self,
    ) -> None:
        locked = self.panel[
            "chronology_block"
        ].isin(
            [
                "holdout",
                "external_test",
            ]
        )

        self.assertFalse(
            self.panel.loc[
                locked,
                "outcome_may_influence_model_choice",
            ].any()
        )

    def test_no_external_refit(self) -> None:
        self.assertFalse(
            self.panel[
                "used_to_refit_before_external_test"
            ].any()
        )

        self.assertFalse(
            self.manifest[
                "refit_before_external_test"
            ]
        )


if __name__ == "__main__":
    unittest.main()
