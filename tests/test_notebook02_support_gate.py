from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


class Notebook02SupportGateTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision = json.loads(
            Path(
                "data/manifests/"
                "02_verified_historical_forecast_decision.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        cls.policy = yaml.safe_load(
            Path(
                "config/"
                "chronology_policy.yaml"
            ).read_text(
                encoding="utf-8"
            )
        )

    def test_verified_historical_decision(self) -> None:
        self.assertEqual(
            self.decision["status"],
            "USE_256_INDEPENDENTLY_VERIFIED_HISTORICAL_ROWS",
        )

        self.assertEqual(
            self.decision[
                "historical_rows_retained"
            ],
            256,
        )

        self.assertEqual(
            self.decision[
                "historical_request_rows_not_promoted"
            ],
            36,
        )

        self.assertFalse(
            self.decision[
                "automatic_292_row_historical_panel_permitted"
            ]
        )

    def test_chronology_is_assigned(self) -> None:
        self.assertEqual(
            self.policy["status"],
            "CHRONOLOGY_ASSIGNED",
        )

        self.assertTrue(
            self.policy[
                "model_fitting_permitted"
            ]
        )

    def test_random_split_is_prohibited(self) -> None:
        self.assertFalse(
            self.policy[
                "random_split_permitted"
            ]
        )

        self.assertEqual(
            self.policy[
                "uncertainty_unit"
            ],
            "settlement_date",
        )


if __name__ == "__main__":
    unittest.main()
