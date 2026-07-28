from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "00_v2_initialisation_manifest.json"
)

INVENTORY_PATH = (
    ROOT
    / "data/manifests/v2/"
    "00_v1_protected_file_inventory.csv"
)

VERIFIER_PATH = (
    ROOT
    / "tools/v2/"
    "verify_v1_release_unchanged.py"
)


class V2Phase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        with INVENTORY_PATH.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            cls.inventory = list(
                csv.DictReader(handle)
            )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "V2_PHASE1_INITIALISATION_COMPLETE",
        )

    def test_source_release(self) -> None:
        self.assertTrue(
            self.manifest[
                "source_commit"
            ].startswith("1ddf22a")
        )

    def test_periods(self) -> None:
        self.assertEqual(
            self.manifest[
                "weather_only_training_start"
            ],
            "2024-03-14",
        )

        self.assertEqual(
            self.manifest[
                "weather_plus_market_training_end"
            ],
            "2026-05-31",
        )

        self.assertEqual(
            self.manifest[
                "june_validation_start"
            ],
            "2026-06-01",
        )

        self.assertEqual(
            self.manifest[
                "july_validation_end"
            ],
            "2026-07-31",
        )

    def test_v1_is_protected(self) -> None:
        self.assertFalse(
            self.manifest[
                "version_1_files_may_be_overwritten"
            ]
        )

        self.assertGreater(
            len(self.inventory),
            0,
        )

    def test_inventory_hash(self) -> None:
        actual = hashlib.sha256(
            INVENTORY_PATH.read_bytes()
        ).hexdigest()

        self.assertEqual(
            actual,
            self.manifest[
                "protected_inventory_sha256"
            ],
        )

    def test_excluded_sources(self) -> None:
        self.assertFalse(
            self.manifest[
                "era5_in_empirical_study"
            ]
        )

        self.assertFalse(
            self.manifest[
                "direct_ecmwf_open_data_in_main_study"
            ]
        )

    def test_retained_work(self) -> None:
        self.assertTrue(
            self.manifest[
                "catboost_retained_pending_supervisor_advice"
            ]
        )

        self.assertTrue(
            self.manifest[
                "ensemble_work_retained_pending_supervisor_advice"
            ]
        )

    def test_preservation_verifier(self) -> None:
        result = subprocess.run(
            ["python3", str(VERIFIER_PATH)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
