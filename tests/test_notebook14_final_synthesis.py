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
    / "data/manifests/"
    "14_final_empirical_synthesis_manifest.json"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "14_empirical_synthesis_integrity_checks.csv"
)

STAGE_STATUS_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "14_stage_status_register.csv"
)

RESULTS_PATH = (
    ROOT
    / "outputs/final_tables/"
    "14_primary_empirical_results_register.csv"
)

CLAIMS_PATH = (
    ROOT
    / "outputs/final_tables/"
    "14_claim_boundary_table.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/final/"
    "14_final_empirical_synthesis.ipynb"
)


def as_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
            }
        )
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


class Notebook14FinalSynthesisTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.integrity = pd.read_csv(
            INTEGRITY_PATH
        )

        cls.stage_status = pd.read_csv(
            STAGE_STATUS_PATH
        )

        cls.results = pd.read_csv(
            RESULTS_PATH,
            low_memory=False,
        )

        cls.claims = pd.read_csv(
            CLAIMS_PATH
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "FINAL_EMPIRICAL_SYNTHESIS_COMPLETE",
        )

    def test_all_integrity_checks_pass(
        self,
    ) -> None:
        self.assertTrue(
            as_bool(
                self.integrity[
                    "passed"
                ]
            ).all()
        )

        self.assertTrue(
            self.manifest[
                "all_integrity_checks_passed"
            ]
        )

    def test_source_stage_count(
        self,
    ) -> None:
        self.assertEqual(
            self.manifest[
                "source_stage_count"
            ],
            8,
        )

        self.assertEqual(
            len(
                self.stage_status
            ),
            8,
        )

    def test_no_failure_statuses(
        self,
    ) -> None:
        status_text = (
            self.stage_status[
                "status"
            ]
            .astype(str)
            .str.upper()
        )

        self.assertFalse(
            status_text.str.contains(
                "FAILED|ERROR|BLOCKED",
                regex=True,
            ).any()
        )

    def test_no_selection_leakage(
        self,
    ) -> None:
        self.assertFalse(
            self.manifest[
                "holdout_used_for_selection"
            ]
        )

        self.assertFalse(
            self.manifest[
                "external_test_used_for_selection"
            ]
        )

        self.assertFalse(
            self.manifest[
                "market_prices_used_for_model_selection"
            ]
        )

    def test_locked_choices_not_reselected(
        self,
    ) -> None:
        self.assertFalse(
            self.manifest[
                "model_reselected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "continuous_calibration_reselected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "probability_calibration_reselected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "trading_strategy_reselected"
            ]
        )

    def test_primary_results_nonempty(
        self,
    ) -> None:
        self.assertGreater(
            len(
                self.results
            ),
            0,
        )

        self.assertEqual(
            len(
                self.results
            ),
            self.manifest[
                "primary_result_metric_rows"
            ],
        )

    def test_claim_boundaries(
        self,
    ) -> None:
        self.assertGreaterEqual(
            len(
                self.claims
            ),
            10,
        )

        required = {
            "claim_id",
            "claim",
            "principal_evidence",
            "permitted_strength",
            "prohibited_extension",
        }

        self.assertTrue(
            required.issubset(
                self.claims.columns
            )
        )

    def test_output_hashes(
        self,
    ) -> None:
        for relative_path, expected_hash in (
            self.manifest[
                "output_hashes"
            ].items()
        ):
            path = (
                ROOT
                / relative_path
            )

            self.assertTrue(
                path.exists(),
                relative_path,
            )

            self.assertEqual(
                sha256_file(
                    path
                ),
                expected_hash,
                relative_path,
            )

    def test_notebook_executed(
        self,
    ) -> None:
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
                cell.execution_count
                is not None
                for cell in code_cells
            )
        )


if __name__ == "__main__":
    unittest.main()
