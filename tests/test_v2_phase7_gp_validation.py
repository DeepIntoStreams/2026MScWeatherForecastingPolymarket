from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "07_gp_validation_manifest.json"
)

PREDICTIONS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_validation_predictions.csv"
)

LEDGER_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_model_fit_ledger.csv"
)

DATE_SCORE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_date_level_scores.csv"
)

PAIRED_DATE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_kernel_paired_date_comparison.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs/v2/final_tables/"
    "07_gp_kernel_validation_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_validation_integrity_checks.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/v2/"
    "07_gp_validation_distributions.ipynb"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


class Phase7GPValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.predictions = pd.read_csv(
            PREDICTIONS_PATH
        )

        cls.ledger = pd.read_csv(
            LEDGER_PATH
        )

        cls.date_scores = pd.read_csv(
            DATE_SCORE_PATH
        )

        cls.paired_dates = pd.read_csv(
            PAIRED_DATE_PATH
        )

        cls.summary = pd.read_csv(
            SUMMARY_PATH
        )

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "TWO_YEAR_GP_VALIDATION_DISTRIBUTIONS_CERTIFIED",
        )

    def test_dimensions(self) -> None:
        self.assertEqual(
            len(self.ledger),
            32,
        )

        self.assertEqual(
            len(self.predictions),
            2920,
        )

        self.assertEqual(
            self.predictions[
                "target_date"
            ].nunique(),
            365,
        )

        self.assertEqual(
            len(self.date_scores),
            730,
        )

        self.assertEqual(
            len(self.paired_dates),
            365,
        )

        self.assertEqual(
            len(self.summary),
            2,
        )

    def test_prediction_keys(self) -> None:
        self.assertFalse(
            self.predictions.duplicated(
                [
                    "target_date",
                    "decision_rule",
                    "kernel",
                ]
            ).any()
        )

        self.assertTrue(
            self.predictions.groupby(
                "target_date"
            ).size().eq(8).all()
        )

    def test_kernels_and_rules(self) -> None:
        self.assertEqual(
            set(
                self.predictions[
                    "kernel"
                ]
            ),
            {
                "rbf",
                "matern32",
            },
        )

        self.assertEqual(
            self.predictions[
                "decision_rule"
            ].nunique(),
            4,
        )

    def test_training_precedes_validation(self) -> None:
        self.assertTrue(
            (
                pd.to_datetime(
                    self.ledger[
                        "training_end"
                    ]
                )
                < pd.to_datetime(
                    self.ledger[
                        "validation_start"
                    ]
                )
            ).all()
        )

    def test_predictive_standard_deviation(self) -> None:
        self.assertTrue(
            self.predictions[
                "predictive_standard_deviation_c"
            ].gt(0.0).all()
        )

    def test_scores(self) -> None:
        columns = [
            "crps_c",
            "negative_log_score",
            "pit_value",
            "temperature_predictive_mean_c",
            "predictive_standard_deviation_c",
        ]

        self.assertTrue(
            np.isfinite(
                self.predictions[
                    columns
                ].to_numpy()
            ).all()
        )

        self.assertTrue(
            self.predictions[
                "crps_c"
            ].ge(0.0).all()
        )

        self.assertTrue(
            self.predictions[
                "pit_value"
            ].between(
                0.0,
                1.0,
                inclusive="both",
            ).all()
        )

    def test_quantiles(self) -> None:
        columns = [
            f"q{integer:02d}_c"
            for integer in range(1, 100)
        ]

        self.assertTrue(
            all(
                column
                in self.predictions.columns
                for column in columns
            )
        )

        matrix = self.predictions[
            columns
        ].to_numpy(dtype=float)

        self.assertTrue(
            np.isfinite(matrix).all()
        )

        self.assertTrue(
            (
                np.diff(
                    matrix,
                    axis=1,
                )
                >= -1e-10
            ).all()
        )

        self.assertTrue(
            np.allclose(
                self.predictions[
                    "q50_c"
                ],
                self.predictions[
                    "temperature_predictive_mean_c"
                ],
                atol=1e-10,
                rtol=0.0,
            )
        )

    def test_no_market_information(self) -> None:
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
                "final_kernel_selected"
            ]
        )

    def test_required_checks(self) -> None:
        required = self.checks.loc[
            self.checks[
                "required"
            ]
            .astype(str)
            .str.lower()
            .isin({"true", "1"})
        ]

        passed = (
            required[
                "passed"
            ]
            .astype(str)
            .str.lower()
            .isin({"true", "1"})
        )

        self.assertTrue(
            passed.all()
        )

    def test_output_hashes(self) -> None:
        for (
            relative_path,
            expected_hash,
        ) in self.manifest[
            "output_hashes"
        ].items():
            path = ROOT / relative_path

            self.assertTrue(
                path.exists(),
                relative_path,
            )

            self.assertEqual(
                sha256_file(path),
                expected_hash,
                relative_path,
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
                cell.execution_count
                is not None
                for cell in code_cells
            )
        )


if __name__ == "__main__":
    unittest.main()
