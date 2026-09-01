from __future__ import annotations

import json
import math
import unittest

from pathlib import Path

import pandas as pd


SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "reporting_stage_summary.json"
)

CHECKS = Path(
    "outputs/final_pipeline/audit/"
    "reporting_stage_integrity_checks.csv"
)

RECON = Path(
    "outputs/final_pipeline/reporting/"
    "march_june_audit_reconciliation.csv"
)

DISCREPANCIES = Path(
    "outputs/final_pipeline/reporting/"
    "benchmark_discrepancy_register.csv"
)

SAMPLE = Path(
    "outputs/final_pipeline/reporting/"
    "authoritative_sample_sizes.csv"
)

MANIFEST = Path(
    "outputs/final_pipeline/reporting/"
    "final_empirical_output_manifest.csv"
)

CLAIMS = Path(
    "outputs/final_pipeline/reporting/"
    "final_thesis_claims_register.csv"
)

NUMBERS = Path(
    "outputs/final_pipeline/thesis/"
    "generated/numbers.tex"
)


class TestFinalReportingStage(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            SUMMARY.read_text()
        )

        cls.checks = pd.read_csv(
            CHECKS
        )

        cls.recon = pd.read_csv(
            RECON
        )

        cls.discrepancies = pd.read_csv(
            DISCREPANCIES
        )

        cls.sample = pd.read_csv(
            SAMPLE
        )

        cls.manifest = pd.read_csv(
            MANIFEST
        )

        cls.claims = pd.read_csv(
            CLAIMS
        )

    def test_stage_pass(self):
        self.assertEqual(
            self.summary[
                "status"
            ],
            "PASS",
        )

    def test_upstream_frozen(self):
        self.assertTrue(
            self.summary[
                "steps_1_80_frozen"
            ]
        )

        self.assertFalse(
            self.summary[
                "new_model_fitted"
            ]
        )

        self.assertFalse(
            self.summary[
                "external_data_used_for_selection"
            ]
        )

    def test_final_selectors_unchanged(self):
        self.assertEqual(
            self.summary[
                "selected_weather_kernel"
            ],
            "matern32",
        )

        self.assertTrue(
            math.isclose(
                self.summary[
                    "selected_pool_weight_gp"
                ],
                0.188,
                abs_tol=1e-12,
            )
        )

        self.assertEqual(
            self.summary[
                "selected_trading_rule"
            ],
            "24h_prior",
        )

        self.assertTrue(
            math.isclose(
                self.summary[
                    "selected_trading_threshold"
                ],
                0.15,
                abs_tol=1e-12,
            )
        )

    def test_historical_must_match(self):
        x = self.recon[
            self.recon[
                "reconciliation_class"
            ]
            == "must_match"
        ]

        self.assertGreaterEqual(
            len(
                x
            ),
            1,
        )

        self.assertTrue(
            (
                x[
                    "reconciliation_pass"
                ]
                .astype(str)
                .str.lower()
                == "true"
            ).all()
        )

    def test_expected_changes_not_used_as_failures(self):
        x = self.recon[
            self.recon[
                "reconciliation_class"
            ]
            == "expected_change"
        ]

        metrics = set(
            x[
                "metric"
            ]
        )

        self.assertIn(
            "pool_weight_gp",
            metrics,
        )

        self.assertIn(
            "trading_threshold",
            metrics,
        )

        self.assertIn(
            "trading_rule",
            metrics,
        )

        # The old weather CRPS values pre-date the final certified
        # ECMWF chronology/core-repair reconstruction and are therefore
        # historical expected-change benchmarks, not must-match values.
        for weather_metric in [
            "weather_raw_crps",
            "weather_static_crps",
            "weather_rbf_crps",
            "weather_matern32_crps",
        ]:
            self.assertIn(
                weather_metric,
                metrics,
            )

    def test_no_unexplained_discrepancy(self):
        self.assertEqual(
            len(
                self.discrepancies
            ),
            1,
        )

        self.assertEqual(
            self.discrepancies.iloc[
                0
            ][
                "status"
            ],
            "NO_UNEXPLAINED_DISCREPANCY",
        )

    def test_sample_sizes(self):
        names = set(
            self.sample[
                "sample"
            ]
        )

        required = {
            "weather_only_history",
            "march_june_development",
            "july_august_external",
            "trading_development_selected_rule",
            "trading_external_selected_rule",
        }

        self.assertTrue(
            required.issubset(
                names
            )
        )

    def test_manifest(self):
        self.assertGreater(
            len(
                self.manifest
            ),
            50,
        )

        self.assertTrue(
            self.manifest[
                "sha256"
            ]
            .astype(str)
            .str.len()
            .eq(
                64
            )
            .all()
        )

        self.assertTrue(
            (
                self.manifest[
                    "git_tracked"
                ]
                .astype(str)
                .str.lower()
                == "true"
            ).all()
        )

    def test_claim_guards(self):
        self.assertGreaterEqual(
            len(
                self.claims
            ),
            10,
        )

        self.assertTrue(
            (
                self.claims[
                    "final_inclusion_status"
                ]
                == "DO_NOT_USE_AS_PRIMARY"
            ).any()
        )

    def test_numbers_tex(self):
        self.assertTrue(
            NUMBERS.exists()
        )

        text = NUMBERS.read_text()

        for macro in [
            r"\WeatherRawCRPS",
            r"\FinalPoolGPWeight",
            r"\TradingThreshold",
            r"\ExternalGPPnL",
            r"\ExternalGPSharpe",
            r"\AugThirtyOnePendingFlag",
        ]:
            self.assertIn(
                macro,
                text,
            )

    def test_integrity_checks(self):
        self.assertTrue(
            (
                self.checks[
                    "passed"
                ]
                .astype(str)
                .str.lower()
                == "true"
            ).all()
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
