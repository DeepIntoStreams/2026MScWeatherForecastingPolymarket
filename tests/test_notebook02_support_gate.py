from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd
import yaml


class Notebook02SupportGateTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            Path(
                "data/manifests/"
                "02_support_and_chronology_manifest.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.chronology = yaml.safe_load(
            Path(
                "config/"
                "chronology_policy.yaml"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.support = pd.read_csv(
            "outputs/diagnostics/"
            "02_date_rule_support_matrix.csv"
        )

    def test_support_expansion_is_required(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest["status"],
            "SUPPORT_EXPANSION_REQUIRED",
        )

        self.assertFalse(
            self.manifest[
                "model_fitting_permitted"
            ]
        )

    def test_chronology_is_not_assigned_prematurely(
        self,
    ) -> None:
        self.assertEqual(
            self.chronology["status"],
            "BLOCKED_PENDING_SUPPORT_EXPANSION",
        )

        self.assertFalse(
            self.chronology[
                "model_fitting_permitted"
            ]
        )

        assignments = self.chronology[
            "block_assignments"
        ]

        self.assertTrue(
            all(
                value == "NOT_ASSIGNED"
                for value in assignments.values()
            )
        )

    def test_june_support_is_audited(
        self,
    ) -> None:
        june = self.support.loc[
            self.support[
                "target_date"
            ].between(
                "2026-06-01",
                "2026-06-30",
            )
        ]

        self.assertEqual(
            len(june),
            120,
        )

        self.assertEqual(
            int(
                june[
                    "selected_forecast_present"
                ].sum()
            ),
            119,
        )

        self.assertEqual(
            int(
                (
                    ~june[
                        "selected_forecast_present"
                    ]
                ).sum()
            ),
            1,
        )

    def test_training_and_evaluation_dates_are_currently_identical(
        self,
    ) -> None:
        training = self.manifest[
            "current_training"
        ]

        evaluation = self.manifest[
            "current_evaluation"
        ]

        self.assertEqual(
            training["dates"],
            30,
        )

        self.assertEqual(
            evaluation["dates"],
            30,
        )

        self.assertEqual(
            training[
                "weather_only_dates"
            ],
            0,
        )


if __name__ == "__main__":
    unittest.main()
