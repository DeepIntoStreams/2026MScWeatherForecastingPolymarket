from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "04f_hko_daily_max_manifest.json"
)

PANEL_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04f_hko_daily_max_training_panel.csv"
)

SUPPORT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_decision_support_panel.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04f_hko_daily_max_integrity_checks.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/v2/"
    "04_hko_daily_max_temperature.ipynb"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


class Phase4FHKOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.panel = pd.read_csv(
            PANEL_PATH
        )

        cls.support = pd.read_csv(
            SUPPORT_PATH
        )

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "HKO_DAILY_MAXIMUM_TRAINING_PANEL_CERTIFIED",
        )

    def test_training_date_count(self) -> None:
        self.assertEqual(
            len(self.panel),
            730,
        )

        self.assertEqual(
            self.panel["target_date"].nunique(),
            730,
        )

    def test_exact_support_dates(self) -> None:
        expected = set(
            self.support[
                "target_date"
            ].astype(str)
        )

        actual = set(
            self.panel[
                "target_date"
            ].astype(str)
        )

        self.assertEqual(
            actual,
            expected,
        )

    def test_no_missing_temperature(self) -> None:
        self.assertTrue(
            self.panel[
                "hko_daily_max_c"
            ].notna().all()
        )

    def test_plausible_temperature(self) -> None:
        self.assertTrue(
            self.panel[
                "hko_daily_max_c"
            ].between(
                -20.0,
                60.0,
                inclusive="both",
            ).all()
        )

    def test_no_post_training_rows_used(self) -> None:
        self.assertEqual(
            self.manifest[
                "post_training_hko_rows_used"
            ],
            0,
        )

    def test_evidential_boundary(self) -> None:
        self.assertTrue(
            self.manifest[
                "training_hko_observations_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "market_prices_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "polymarket_outcomes_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "model_fitted"
            ]
        )

        self.assertFalse(
            self.manifest[
                "model_selected"
            ]
        )

    def test_required_integrity_checks(self) -> None:
        required = self.checks.loc[
            self.checks[
                "required"
            ]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"true", "1"})
        ]

        passed = (
            required[
                "passed"
            ]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"true", "1"})
        )

        self.assertTrue(
            passed.all()
        )

    def test_output_hashes(self) -> None:
        for relative, expected_hash in (
            self.manifest[
                "output_hashes"
            ].items()
        ):
            path = ROOT / relative

            self.assertTrue(
                path.exists(),
                relative,
            )

            self.assertEqual(
                sha256_file(path),
                expected_hash,
                relative,
            )

    def test_notebook_executed(self) -> None:
        notebook = nbformat.read(
            NOTEBOOK_PATH,
            as_version=4,
        )

        code_cells = [
            cell
            for cell in notebook.cells
            if cell.cell_type == "code"
        ]

        errors = [
            output
            for cell in code_cells
            for output in cell.get(
                "outputs",
                [],
            )
            if output.get(
                "output_type"
            ) == "error"
        ]

        self.assertTrue(code_cells)
        self.assertFalse(errors)

        self.assertTrue(
            all(
                cell.execution_count is not None
                for cell in code_cells
            )
        )


if __name__ == "__main__":
    unittest.main()
