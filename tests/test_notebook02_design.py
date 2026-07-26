from __future__ import annotations

import json
import unittest
from pathlib import Path

from weather_polymarket.notebook02_design import (
    load_notebook02_design,
    validate_notebook02_design,
)


class Notebook02DesignTests(unittest.TestCase):
    def test_design_is_valid(self) -> None:
        design = load_notebook02_design(
            Path.cwd()
        )

        validate_notebook02_design(
            design
        )

    def test_training_and_evaluation_are_separate(self) -> None:
        design = load_notebook02_design(
            Path.cwd()
        )

        self.assertFalse(
            design.training_requires_market
        )

        self.assertTrue(
            design.evaluation_requires_market
        )

    def test_chronology_and_local_path_rules(self) -> None:
        design = load_notebook02_design(
            Path.cwd()
        )

        self.assertEqual(
            design.local_timezone,
            "Asia/Hong_Kong",
        )

        self.assertEqual(
            design.required_local_hours,
            24,
        )

        self.assertFalse(
            design.random_split_permitted
        )

        self.assertTrue(
            design.group_by_date
        )

    def test_bundle_contains_june_hourly_and_daily_sources(self) -> None:
        payload = json.loads(
            Path(
                "data/manifests/"
                "02_weather_source_bundle_manifest.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            payload["status"],
            "NOTEBOOK02_SOURCE_BUNDLE_READY",
        )

        required = {
            "hourly_forecasts",
            "daily_max_forecasts",
            "request_plan",
            "fetch_inventory",
        }

        self.assertTrue(
            required.issubset(
                payload["role_summary"]
            )
        )

        self.assertTrue(
            payload["june_coverage"][
                "hourly_source_reaches_2026_06_30"
            ]
        )

        self.assertTrue(
            payload["june_coverage"][
                "daily_max_source_reaches_2026_06_30"
            ]
        )


if __name__ == "__main__":
    unittest.main()
