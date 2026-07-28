from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = (
    ROOT
    / "data/manifests/"
    "15_reproducibility_release_manifest.json"
)

CHECKS_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "15_release_integrity_checks.csv"
)

NOTEBOOK_AUDIT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "15_notebook_execution_audit.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/final/"
    "15_reproducibility_release_audit.ipynb"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def as_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1"})
    )


class Notebook15ReleaseAuditTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

        cls.notebooks = pd.read_csv(
            NOTEBOOK_AUDIT_PATH
        )

    def test_release_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "FINAL_EMPIRICAL_RELEASE_CERTIFIED",
        )

        self.assertTrue(
            self.manifest["release_ready"]
        )

    def test_all_release_checks_pass(self) -> None:
        self.assertTrue(
            as_bool(
                self.checks["passed"]
            ).all()
        )

    def test_canonical_notebook_coverage(self) -> None:
        self.assertEqual(
            set(
                self.notebooks[
                    "notebook_number"
                ].astype(int)
            ),
            set(range(15)),
        )

        self.assertEqual(
            len(self.notebooks),
            15,
        )

    def test_upstream_notebooks_executed(self) -> None:
        self.assertTrue(
            as_bool(
                self.notebooks[
                    "execution_complete"
                ]
            ).all()
        )

    def test_locked_choices_not_reselected(self) -> None:
        for key in [
            "model_reselected",
            "continuous_calibration_reselected",
            "probability_calibration_reselected",
            "trading_strategy_reselected",
            "holdout_used_for_selection",
            "external_test_used_for_selection",
        ]:
            self.assertFalse(
                self.manifest[key],
                key,
            )

    def test_output_hashes(self) -> None:
        for relative_path, expected in (
            self.manifest[
                "output_hashes"
            ].items()
        ):
            path = ROOT / relative_path

            self.assertTrue(
                path.exists(),
                relative_path,
            )

            self.assertEqual(
                sha256(path),
                expected,
                relative_path,
            )

    def test_audited_commit_is_ancestor(self) -> None:
        completed = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                self.manifest[
                    "audited_commit"
                ],
                "HEAD",
            ],
            cwd=ROOT,
        )

        self.assertEqual(
            completed.returncode,
            0,
        )

    def test_notebook15_executed(self) -> None:
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
                cell.execution_count
                is not None
                for cell in code_cells
            )
        )


if __name__ == "__main__":
    unittest.main()
