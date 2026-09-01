from __future__ import annotations

import json
import math
import unittest

from pathlib import Path

import pandas as pd


SUMMARY = Path(
    "outputs/final_pipeline/release/"
    "final_release_summary.json"
)

CORE = Path(
    "outputs/final_pipeline/release/"
    "seven_question_core_narrative.csv"
)

PRUNING = Path(
    "outputs/final_pipeline/release/"
    "thesis_pruning_register.csv"
)

AUDIT = Path(
    "outputs/final_pipeline/release/"
    "three_layer_final_audit.csv"
)

MANIFEST = Path(
    "outputs/final_pipeline/release/"
    "final_release_manifest.csv"
)

CHECKSUMS = Path(
    "outputs/final_pipeline/release/"
    "final_release_checksums.sha256"
)

NUMBERS = Path(
    "outputs/final_pipeline/thesis/"
    "generated/numbers.tex"
)


class TestFinalRelease(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            SUMMARY.read_text()
        )

        cls.core = pd.read_csv(
            CORE
        )

        cls.pruning = pd.read_csv(
            PRUNING
        )

        cls.audit = pd.read_csv(
            AUDIT
        )

        cls.manifest = pd.read_csv(
            MANIFEST
        )

    def test_release_pass(self):
        self.assertEqual(
            self.summary["status"],
            "PASS",
        )

    def test_steps_1_90_frozen(self):
        self.assertTrue(
            self.summary[
                "steps_1_90_frozen"
            ]
        )

        self.assertFalse(
            self.summary[
                "new_empirical_modeling"
            ]
        )

        self.assertFalse(
            self.summary[
                "external_data_used_for_reselection"
            ]
        )

    def test_final_selectors(self):
        self.assertEqual(
            self.summary[
                "weather_kernel"
            ],
            "matern32",
        )

        self.assertTrue(
            math.isclose(
                self.summary[
                    "pool_weight_gp"
                ],
                0.188,
                abs_tol=1e-12,
            )
        )

        self.assertEqual(
            self.summary[
                "trading_rule"
            ],
            "24h_prior",
        )

        self.assertTrue(
            math.isclose(
                self.summary[
                    "trading_threshold"
                ],
                0.15,
                abs_tol=1e-12,
            )
        )

    def test_seven_questions(self):
        self.assertEqual(
            len(self.core),
            7,
        )

        self.assertEqual(
            set(
                self.core[
                    "question_id"
                ]
            ),
            {
                "Q1",
                "Q2",
                "Q3",
                "Q4",
                "Q5",
                "Q6",
                "Q7",
            },
        )

    def test_pruning_guards(self):
        self.assertGreater(
            len(self.pruning),
            10,
        )

        self.assertTrue(
            (
                self.pruning[
                    "final_empirical_decision"
                ]
                == "EXCLUDE_FROM_PRIMARY_RESULTS"
            ).any()
        )

    def test_three_layer_audit(self):
        self.assertEqual(
            set(
                self.audit[
                    "layer"
                ]
            ),
            {
                "data",
                "methodology",
                "results",
            },
        )

        self.assertTrue(
            (
                self.audit[
                    "passed"
                ]
                .astype(str)
                .str.lower()
                == "true"
            ).all()
        )

    def test_manifest(self):
        self.assertGreater(
            len(self.manifest),
            100,
        )

        self.assertTrue(
            self.manifest[
                "sha256"
            ]
            .astype(str)
            .str.len()
            .eq(64)
            .all()
        )

    def test_checksums(self):
        self.assertTrue(
            CHECKSUMS.exists()
        )

        self.assertEqual(
            len(
                CHECKSUMS.read_text()
                .strip()
                .splitlines()
            ),
            len(
                self.manifest
            ),
        )

    def test_numbers_source(self):
        text = NUMBERS.read_text()

        for macro in [
            r"\WeatherRawCRPS",
            r"\WeatherMaternCRPS",
            r"\FinalPoolGPWeight",
            r"\ExternalGPPnL",
            r"\TradingThreshold",
        ]:
            self.assertIn(
                macro,
                text,
            )

    def test_pending_gate(self):
        self.assertIn(
            self.summary[
                "pending_target_dates"
            ],
            [
                [],
                [
                    "2026-08-31"
                ],
            ],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
