from __future__ import annotations

import csv
import hashlib
import json
import unittest

from pathlib import Path

import numpy as np
import pandas as pd


MASTER = Path(
    "data/processed/final_pipeline/"
    "weather_residual_panel.csv"
)

MANIFEST = Path(
    "data/processed/final_pipeline/"
    "residual_sample_manifest.csv"
)

SAMPLE_DIR = Path(
    "data/processed/final_pipeline/"
    "residual_samples"
)

SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "residual_panel_summary.json"
)

ERROR_SUMMARY = Path(
    "outputs/final_pipeline/weather/"
    "deterministic_error_summary.csv"
)


def sha256_file(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


class TestResidualPanel(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.panel = pd.read_csv(
            MASTER
        )

        cls.panel[
            "target_date"
        ] = pd.to_datetime(
            cls.panel[
                "target_date"
            ]
        )

        cls.summary = json.loads(
            SUMMARY.read_text()
        )

        cls.manifest = (
            pd.read_csv(
                MANIFEST
            )
        )

    def test_master_shape(self):
        self.assertEqual(
            len(self.panel),
            3596,
        )

        self.assertEqual(
            self.panel[
                [
                    "target_date",
                    "decision_rule",
                ]
            ]
            .drop_duplicates()
            .shape[0],
            3596,
        )

    def test_period_counts(self):
        counts = (
            self.panel[
                "empirical_period"
            ]
            .value_counts()
            .to_dict()
        )

        self.assertEqual(
            counts.get(
                "weather_history"
            ),
            2920,
        )

        self.assertEqual(
            counts.get(
                "market_development"
            ),
            428,
        )

        self.assertEqual(
            counts.get(
                "external_validation"
            ),
            248,
        )

    def test_residual_identity(self):
        usable = self.panel[
            self.panel[
                "residual_usable"
            ]
            .astype(str)
            .str.lower()
            == "true"
        ]

        residual_error = np.abs(
            usable[
                "residual_c"
            ]
            - (
                usable[
                    "hko_daily_max_c"
                ]
                - usable[
                    "forecast_daily_max_c"
                ]
            )
        )

        self.assertLess(
            float(
                residual_error.max()
            ),
            1e-9,
        )

        forecast_error = np.abs(
            usable[
                "forecast_error_c"
            ]
            + usable[
                "residual_c"
            ]
        )

        self.assertLess(
            float(
                forecast_error.max()
            ),
            1e-9,
        )

    def test_unusable_has_no_error_values(self):
        usable = (
            self.panel[
                "residual_usable"
            ]
            .astype(str)
            .str.lower()
            == "true"
        )

        bad = self.panel.loc[
            ~usable,
            [
                "residual_c",
                "forecast_error_c",
                "absolute_error_c",
                "squared_error_c",
            ],
        ]

        self.assertFalse(
            bad.notna().any().any()
        )

    def test_hko_pending_or_complete(self):
        status = self.summary[
            "hko_status"
        ]

        pending_dates = (
            self.summary[
                "target_pending_dates"
            ]
        )

        if status == "PENDING_FINAL_DATE":
            self.assertEqual(
                pending_dates,
                ["2026-08-31"],
            )

            self.assertEqual(
                self.summary[
                    "residual_usable_keys"
                ],
                3394,
            )

        elif status == "COMPLETE":
            self.assertEqual(
                pending_dates,
                [],
            )

            self.assertEqual(
                self.summary[
                    "residual_usable_keys"
                ],
                3398,
            )

        else:
            self.fail(
                f"Unexpected HKO status: {status}"
            )

    def test_frozen_split_counts(self):
        period_counts = (
            self.summary[
                "period_counts"
            ]
        )

        self.assertEqual(
            period_counts[
                "weather_history"
            ][
                "residual_usable_keys"
            ],
            2726,
        )

        self.assertEqual(
            period_counts[
                "market_development"
            ][
                "residual_usable_keys"
            ],
            424,
        )

        expected_external = (
            244
            if self.summary[
                "hko_status"
            ]
            == "PENDING_FINAL_DATE"
            else 248
        )

        self.assertEqual(
            period_counts[
                "external_validation"
            ][
                "residual_usable_keys"
            ],
            expected_external,
        )

    def test_samples_equal_master_complete_cases(self):
        mapping = {
            "weather_history_training":
                (
                    "weather_history",
                    SAMPLE_DIR
                    / "weather_history_training.csv",
                ),

            "market_development":
                (
                    "market_development",
                    SAMPLE_DIR
                    / "market_development.csv",
                ),

            "external_validation":
                (
                    "external_validation",
                    SAMPLE_DIR
                    / "external_validation.csv",
                ),
        }

        usable = (
            self.panel[
                "residual_usable"
            ]
            .astype(str)
            .str.lower()
            == "true"
        )

        for (
            sample_name,
            (
                period,
                path,
            ),
        ) in mapping.items():

            expected = self.panel[
                usable
                & (
                    self.panel[
                        "empirical_period"
                    ]
                    == period
                )
            ]

            actual = pd.read_csv(
                path
            )

            self.assertEqual(
                len(actual),
                len(expected),
                msg=sample_name,
            )

    def test_manifest_hashes(self):
        for _, row in (
            self.manifest.iterrows()
        ):
            path = Path(
                row["path"]
            )

            self.assertTrue(
                path.exists()
            )

            self.assertEqual(
                sha256_file(path),
                row["sha256"],
            )

    def test_no_split_leakage(self):
        train = pd.read_csv(
            SAMPLE_DIR
            / "weather_history_training.csv"
        )

        train_dates = pd.to_datetime(
            train["target_date"]
        )

        self.assertTrue(
            (
                train_dates
                <= pd.Timestamp(
                    "2026-03-15"
                )
            ).all()
        )

        development = pd.read_csv(
            SAMPLE_DIR
            / "market_development.csv"
        )

        development_dates = (
            pd.to_datetime(
                development[
                    "target_date"
                ]
            )
        )

        self.assertTrue(
            (
                development_dates
                >= pd.Timestamp(
                    "2026-03-16"
                )
            ).all()
        )

        self.assertTrue(
            (
                development_dates
                <= pd.Timestamp(
                    "2026-06-30"
                )
            ).all()
        )

        external = pd.read_csv(
            SAMPLE_DIR
            / "external_validation.csv"
        )

        external_dates = (
            pd.to_datetime(
                external[
                    "target_date"
                ]
            )
        )

        self.assertTrue(
            (
                external_dates
                >= pd.Timestamp(
                    "2026-07-01"
                )
            ).all()
        )

    def test_gp_features_exist(self):
        required = {
            "forecast_daily_max_c",
            "seasonal_sin",
            "seasonal_cos",
            "calendar_day_index",
            "residual_c",
        }

        self.assertTrue(
            required.issubset(
                self.panel.columns
            )
        )

    def test_error_summary_shape(self):
        x = pd.read_csv(
            ERROR_SUMMARY
        )

        self.assertEqual(
            len(x),
            20,
        )

        self.assertEqual(
            set(
                x[
                    "decision_rule"
                ]
            ),
            {
                "24h_prior",
                "12h_prior",
                "6h_prior",
                "event_day_open",
            },
        )

    def test_summary_status(self):
        self.assertIn(
            self.summary[
                "status"
            ],
            {
                "PASS",
                "PASS_PENDING_HKO_FINAL_DATE",
            },
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
