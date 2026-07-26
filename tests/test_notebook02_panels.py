from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

from weather_polymarket.forecast_adapter import (
    normalise_rule,
    temperature_to_celsius,
)


class ForecastAdapterTests(unittest.TestCase):
    def test_rule_normalisation(self) -> None:
        cases = {
            "24h prior": "24h_prior",
            "12-hour": "12h_prior",
            "6h": "6h_prior",
            "event day open": "event_day_open",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(
                    normalise_rule(raw),
                    expected,
                )

    def test_kelvin_conversion(self) -> None:
        converted, basis = temperature_to_celsius(
            pd.Series(
                [
                    300.15,
                    301.15,
                ]
            )
        )

        self.assertEqual(
            basis,
            "kelvin_converted_to_celsius",
        )

        self.assertAlmostEqual(
            float(converted.iloc[0]),
            27.0,
            places=6,
        )


class Notebook02PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.training = pd.read_csv(
            "data/processed/"
            "02_weather_training_panel.csv"
        )

        cls.evaluation = pd.read_csv(
            "data/processed/"
            "02_market_evaluation_forecast_panel.csv"
        )

        cls.selected = pd.read_csv(
            "data/processed/"
            "02_selected_deterministic_forecast_panel.csv"
        )

        cls.admission = pd.read_csv(
            "outputs/diagnostics/"
            "02_forecast_admission_audit.csv"
        )

        cls.mapping = pd.read_csv(
            "outputs/diagnostics/"
            "02_request_timestamp_mapping.csv"
        )

        cls.summary = json.loads(
            Path(
                "outputs/diagnostics/"
                "02_panel_construction_summary.json"
            ).read_text(
                encoding="utf-8"
            )
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.summary["status"],
            "NOTEBOOK02_PANELS_READY",
        )

    def test_timestamp_columns_are_detected(self) -> None:
        self.assertTrue(
            self.mapping[
                "issue_column"
            ].fillna("").str.len().gt(0).any()
        )

        self.assertTrue(
            self.mapping[
                "decision_column"
            ].fillna("").str.len().gt(0).any()
        )

    def test_audited_grouping_definition(self) -> None:
        self.assertTrue(
            self.selected[
                "grouping_definition"
            ].eq(
                "source_target_date_decision_rule_issue_time"
            ).all()
        )

    def test_paths_have_24_local_hours(self) -> None:
        self.assertTrue(
            self.selected[
                "unique_local_hours"
            ].eq(24).all()
        )

    def test_all_required_times_are_present(self) -> None:
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

    def test_evaluation_is_training_subset(self) -> None:
        training_keys = set(
            zip(
                self.training[
                    "target_date"
                ],
                self.training[
                    "decision_rule"
                ],
            )
        )

        evaluation_keys = set(
            zip(
                self.evaluation[
                    "target_date"
                ],
                self.evaluation[
                    "decision_rule"
                ],
            )
        )

        self.assertTrue(
            evaluation_keys.issubset(
                training_keys
            )
        )

    def test_admission_audit_has_passed_paths(self) -> None:
        self.assertTrue(
            self.admission[
                "status"
            ].eq(
                "ADMITTED"
            ).any()
        )

    def test_panel_reaches_june_30(self) -> None:
        self.assertGreaterEqual(
            self.training[
                "target_date"
            ].max(),
            "2026-06-30",
        )


if __name__ == "__main__":
    unittest.main()
