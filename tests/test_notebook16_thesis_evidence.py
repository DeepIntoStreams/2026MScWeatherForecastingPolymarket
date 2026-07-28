from __future__ import annotations

import json
import unittest
from pathlib import Path

import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = (
    ROOT
    / "data/manifests/"
    "16_thesis_evidence_manifest.json"
)

RELEASE_PATH = (
    ROOT
    / "data/manifests/"
    "15_reproducibility_release_manifest.json"
)

MODEL_PATH = (
    ROOT
    / "outputs/thesis/"
    "16_model_selection_table.csv"
)

CALIBRATION_PATH = (
    ROOT
    / "outputs/thesis/"
    "16_calibration_table.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/thesis/"
    "16_thesis_evidence_integrity_checks.csv"
)

INVENTORY_PATH = (
    ROOT
    / "outputs/thesis/"
    "16_thesis_output_inventory.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/final/"
    "16_thesis_evidence_and_reporting.ipynb"
)


def as_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1"})
    )


class Notebook16ThesisEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.release = json.loads(
            RELEASE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.model = pd.read_csv(
            MODEL_PATH
        )

        cls.calibration = pd.read_csv(
            CALIBRATION_PATH
        )

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

        cls.inventory = pd.read_csv(
            INVENTORY_PATH
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "THESIS_EVIDENCE_PACKAGE_COMPLETE",
        )

    def test_release_is_certified(self) -> None:
        self.assertEqual(
            self.release["status"],
            "FINAL_EMPIRICAL_RELEASE_CERTIFIED",
        )

        self.assertTrue(
            self.release["release_ready"]
        )

    def test_integrity_checks(self) -> None:
        self.assertTrue(
            as_bool(
                self.checks["passed"]
            ).all()
        )

        self.assertTrue(
            self.manifest[
                "all_integrity_checks_passed"
            ]
        )

    def test_locked_model_recorded(self) -> None:
        self.assertEqual(
            len(self.model),
            1,
        )

        self.assertEqual(
            self.model.loc[
                0,
                "selected_model",
            ],
            self.manifest[
                "selected_model"
            ],
        )

    def test_calibration_stages_recorded(self) -> None:
        self.assertEqual(
            set(
                self.calibration[
                    "calibration_stage"
                ]
            ),
            {
                "continuous dispersion",
                "event probability mixing",
            },
        )

    def test_no_reselection(self) -> None:
        for key in [
            "model_reselected",
            "continuous_calibration_reselected",
            "probability_calibration_reselected",
            "trading_strategy_reselected",
        ]:
            self.assertFalse(
                self.manifest[key],
                key,
            )

    def test_output_inventory(self) -> None:
        self.assertGreaterEqual(
            self.manifest["table_count"],
            7,
        )

        self.assertGreaterEqual(
            self.manifest["figure_count"],
            1,
        )

        self.assertFalse(
            self.inventory.empty
        )

        for relative_path in self.inventory["path"]:
            self.assertTrue(
                (
                    ROOT
                    / relative_path
                ).exists(),
                relative_path,
            )

    def test_latex_report_exists(self) -> None:
        self.assertTrue(
            (
                ROOT
                / self.manifest[
                    "report_latex_path"
                ]
            ).exists()
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

        self.assertTrue(
            code_cells
        )

        self.assertFalse(
            errors
        )

        self.assertTrue(
            all(
                cell.execution_count is not None
                for cell in code_cells
            )
        )


if __name__ == "__main__":
    unittest.main()
