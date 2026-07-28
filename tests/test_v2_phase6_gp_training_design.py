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
    "06_gp_training_design_manifest.json"
)

DESIGN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_raw_design_panel.csv"
)

ASSIGNMENT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_date_assignments.csv"
)

MATRIX_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_matrix_panel.csv"
)

SCALING_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_scaling_parameters.csv"
)

FOLD_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_training_design_integrity_checks.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/v2/"
    "06_gp_training_design.ipynb"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


class Phase6GPDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.design = pd.read_csv(
            DESIGN_PATH
        )

        cls.assignments = pd.read_csv(
            ASSIGNMENT_PATH
        )

        cls.matrix = pd.read_csv(
            MATRIX_PATH
        )

        cls.scaling = pd.read_csv(
            SCALING_PATH
        )

        cls.folds = pd.read_csv(
            FOLD_SUMMARY_PATH
        )

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "TWO_YEAR_GP_TRAINING_DESIGN_CERTIFIED",
        )

    def test_raw_design_dimensions(self) -> None:
        self.assertEqual(
            len(self.design),
            2920,
        )

        self.assertEqual(
            self.design[
                "target_date"
            ].nunique(),
            730,
        )

        self.assertEqual(
            self.design[
                "decision_rule"
            ].nunique(),
            4,
        )

    def test_unique_date_rule_keys(self) -> None:
        self.assertFalse(
            self.design.duplicated(
                [
                    "target_date",
                    "decision_rule",
                ]
            ).any()
        )

    def test_fold_sizes(self) -> None:
        self.assertEqual(
            self.folds[
                "training_dates"
            ].tolist(),
            [
                365,
                456,
                547,
                638,
            ],
        )

        self.assertEqual(
            self.folds[
                "validation_dates"
            ].tolist(),
            [
                91,
                91,
                91,
                92,
            ],
        )

    def test_training_precedes_validation(self) -> None:
        training_end = pd.to_datetime(
            self.folds[
                "training_end"
            ]
        )

        validation_start = pd.to_datetime(
            self.folds[
                "validation_start"
            ]
        )

        self.assertTrue(
            (
                training_end
                < validation_start
            ).all()
        )

    def test_each_validation_date_once(self) -> None:
        validation = (
            self.assignments.loc[
                self.assignments[
                    "sample_role"
                ].eq("validation")
            ]
        )

        self.assertEqual(
            len(validation),
            365,
        )

        self.assertTrue(
            validation.groupby(
                "target_date"
            ).size().eq(1).all()
        )

    def test_fold_matrix_dimensions(self) -> None:
        self.assertEqual(
            len(self.matrix),
            9484,
        )

        self.assertEqual(
            len(self.scaling),
            64,
        )

    def test_features_finite(self) -> None:
        columns = [
            "calendar_time_years",
            "seasonal_sin",
            "seasonal_cos",
            "forecast_daily_max_c",
            "calendar_time_years_z",
            "seasonal_sin_z",
            "seasonal_cos_z",
            "forecast_daily_max_c_z",
            "gp_target",
        ]

        self.assertTrue(
            np.isfinite(
                self.matrix[
                    columns
                ].to_numpy()
            ).all()
        )

    def test_training_standardisation(self) -> None:
        training = self.matrix.loc[
            self.matrix[
                "sample_role"
            ].eq("training")
        ]

        columns = [
            "calendar_time_years_z",
            "seasonal_sin_z",
            "seasonal_cos_z",
            "forecast_daily_max_c_z",
        ]

        for (
            fold_id,
            decision_rule,
        ), group in training.groupby(
            [
                "fold_id",
                "decision_rule",
            ],
            sort=False,
        ):
            for column in columns:
                self.assertLessEqual(
                    abs(
                        float(
                            group[
                                column
                            ].mean()
                        )
                    ),
                    1e-10,
                )

                self.assertLessEqual(
                    abs(
                        float(
                            group[
                                column
                            ].std(ddof=0)
                        )
                        - 1.0
                    ),
                    1e-10,
                )

    def test_target_is_residual(self) -> None:
        self.assertTrue(
            np.allclose(
                self.design[
                    "gp_target"
                ],
                self.design[
                    "residual_c"
                ],
                atol=1e-12,
                rtol=0.0,
            )
        )

    def test_evidential_boundary(self) -> None:
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
                "hyperparameters_estimated"
            ]
        )

        self.assertFalse(
            self.manifest[
                "model_selected"
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
            relative,
            expected_hash,
        ) in self.manifest[
            "output_hashes"
        ].items():
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
                cell.execution_count
                is not None
                for cell in code_cells
            )
        )


if __name__ == "__main__":
    unittest.main()
