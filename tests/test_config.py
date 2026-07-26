from __future__ import annotations

import unittest
from pathlib import Path

from weather_polymarket.config import (
    find_repo_root,
    load_project_config,
)


class ConfigurationTests(unittest.TestCase):
    def test_repository_root_is_found(self) -> None:
        root = find_repo_root(Path.cwd())

        self.assertTrue(
            (root / "config" / "analysis.yaml").exists()
        )

    def test_project_configuration_loads(self) -> None:
        root = find_repo_root(Path.cwd())
        config = load_project_config(root)

        self.assertEqual(
            set(
                config["analysis"]["decision_rules"]
            ),
            {
                "24h_prior",
                "12h_prior",
                "6h_prior",
                "event_day_open",
            },
        )

        self.assertEqual(
            config["analysis"]["project"][
                "uncertainty_unit"
            ],
            "settlement_date",
        )


if __name__ == "__main__":
    unittest.main()
