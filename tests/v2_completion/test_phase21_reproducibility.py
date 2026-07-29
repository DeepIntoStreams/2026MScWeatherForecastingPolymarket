from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


class Phase21ReproducibilityTest(unittest.TestCase):
    def test_clean_replay(self) -> None:
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads(
            (
                root
                / "outputs/v2_completion/"
                / "phase21_replay_manifest.json"
            ).read_text(encoding="utf-8")
        )
        commands = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase21_replay_command_registry.csv"
        )
        comparisons = pd.read_csv(
            root
            / "outputs/v2_completion/"
            / "phase21_artifact_comparison.csv"
        )

        self.assertEqual(manifest["status"], "PASSED")
        self.assertEqual(
            manifest["phases_replayed"],
            [15, 16, 17, 18, 19, 20],
        )
        self.assertEqual(set(commands["phase"]), set(range(15, 21)))
        self.assertTrue((commands["status"] == "PASSED").all())
        self.assertGreater(len(comparisons), 20)
        self.assertTrue(
            (comparisons["status"] == "PASSED").all()
        )
        self.assertEqual(
            manifest["failed_artifact_comparisons"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
