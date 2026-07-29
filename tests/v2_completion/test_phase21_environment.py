from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


class Phase21EnvironmentTest(unittest.TestCase):
    def test_environment_and_sources(self) -> None:
        root = Path(__file__).resolve().parents[2]
        specification = json.loads(
            (
                root
                / "config/v2_completion/"
                / "phase21_reproducibility_spec.json"
            ).read_text(encoding="utf-8")
        )
        packages = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase21_package_version_comparison.csv"
        )
        sources = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase21_source_hash_inventory.csv"
        )
        seeds = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase21_random_seed_registry.csv"
        )

        self.assertTrue(specification["pip_check_passed"])
        self.assertTrue((packages["status"] == "PASSED").all())
        self.assertEqual(len(packages), 6)
        self.assertTrue(sources["git_tracked"].all())
        self.assertTrue(
            sources["sha256"].str.fullmatch(
                r"[0-9a-f]{64}"
            ).all()
        )
        self.assertGreater(len(seeds), 0)
        self.assertEqual(
            len(
                (
                    root
                    / "requirements-v2-completion.txt"
                ).read_text().splitlines()
            ),
            6,
        )
        self.assertTrue(
            (
                root / "environment-v2-completion.yml"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
