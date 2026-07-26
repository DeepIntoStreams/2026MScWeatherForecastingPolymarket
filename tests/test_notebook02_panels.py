from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


class Notebook02VerifiedPanelTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selected = pd.read_csv(
            "data/processed/"
            "02_selected_deterministic_forecast_panel.csv"
        )

        cls.training = pd.read_csv(
            "data/processed/"
            "02_weather_training_panel.csv"
        )

        cls.evaluation = pd.read_csv(
            "data/processed/"
            "02_market_evaluation_forecast_panel.csv"
        )

        cls.reconciliation = pd.read_csv(
            "outputs/diagnostics/"
            "02_historical_daily_hourly_reconciliation.csv"
        )

        cls.support = pd.read_csv(
            "outputs/diagnostics/"
            "02_date_rule_support_matrix.csv"
        )

        cls.summary = json.loads(
            Path(
                "outputs/diagnostics/"
                "02_full_support_summary.json"
            ).read_text(
                encoding="utf-8"
            )
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.summary["status"],
            "NOTEBOOK02_VERIFIED_PANEL_READY",
        )

    def test_dimensions(self) -> None:
        self.assertEqual(
            len(self.selected),
            375,
        )

        self.assertEqual(
            self.selected[
                "target_date"
            ].nunique(),
            102,
        )

        self.assertEqual(
            len(self.training),
            375,
        )

        self.assertEqual(
            len(self.evaluation),
            375,
        )

    def test_historical_and_june_support(self) -> None:
        self.assertEqual(
            int(
                self.selected[
                    "source_period"
                ].eq(
                    "historical_march_may"
                ).sum()
            ),
            256,
        )

        self.assertEqual(
            int(
                self.selected[
                    "source_period"
                ].eq(
                    "june_external"
                ).sum()
            ),
            119,
        )

    def test_daily_hourly_reconciliation(self) -> None:
        self.assertEqual(
            len(self.reconciliation),
            256,
        )

        self.assertTrue(
            self.reconciliation[
                "unique_local_hours"
            ].eq(24).all()
        )

        self.assertTrue(
            self.reconciliation[
                "absolute_difference_c"
            ].le(1e-9).all()
        )

    def test_all_paths_have_24_hours(self) -> None:
        self.assertTrue(
            self.selected[
                "unique_local_hours"
            ].eq(24).all()
        )

    def test_no_lookahead(self) -> None:
        issue = pd.to_datetime(
            self.selected[
                "forecast_issue_time_utc"
            ],
            utc=True,
        )

        decision = pd.to_datetime(
            self.selected[
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

    def test_unique_date_rule_rows(self) -> None:
        self.assertFalse(
            self.selected[
                [
                    "target_date",
                    "decision_rule",
                ]
            ].duplicated().any()
        )

    def test_unsupported_rows_are_explicit(self) -> None:
        missing = self.support.loc[
            ~self.support[
                "forecast_present"
            ]
        ]

        historical = missing.loc[
            missing[
                "target_date"
            ] < "2026-06-01"
        ]

        june = missing.loc[
            missing[
                "target_date"
            ] >= "2026-06-01"
        ]

        self.assertEqual(
            len(missing),
            37,
        )

        self.assertEqual(
            len(historical),
            36,
        )

        self.assertEqual(
            len(june),
            1,
        )


if __name__ == "__main__":
    unittest.main()
