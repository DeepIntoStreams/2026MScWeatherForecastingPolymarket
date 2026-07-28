from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from datetime import date
from pathlib import Path

import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "02_two_year_request_plan_manifest.json"
)

PLAN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_request_plan.csv"
)

CORE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_core_request_plan.csv"
)

SUPPLEMENTARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_supplementary_request_plan.csv"
)

SUPPORT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_training_target_support_map.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_request_plan_integrity_checks.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/v2/"
    "02_two_year_weather_request_plan.ipynb"
)

V1_VERIFIER = (
    ROOT
    / "tools/v2/"
    "verify_v1_release_unchanged.py"
)


def as_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1"})
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


class Phase3TwoYearRequestPlanTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.plan = pd.read_csv(
            PLAN_PATH
        )

        cls.core = pd.read_csv(
            CORE_PATH
        )

        cls.supplementary = pd.read_csv(
            SUPPLEMENTARY_PATH
        )

        cls.support = pd.read_csv(
            SUPPORT_PATH
        )

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

    def test_phase_status(self) -> None:
        self.assertEqual(
            self.manifest["phase_status"],
            "PHASE3_COMPLETE",
        )

        self.assertEqual(
            self.manifest["status"],
            "TWO_YEAR_REQUEST_PLAN_CERTIFIED",
        )

    def test_period_boundaries(self) -> None:
        self.assertEqual(
            self.manifest[
                "weather_only_training_start"
            ],
            "2024-03-16",
        )

        self.assertEqual(
            self.manifest[
                "weather_only_training_end"
            ],
            "2026-03-15",
        )

        self.assertEqual(
            self.manifest[
                "weather_only_training_dates"
            ],
            730,
        )

        self.assertEqual(
            self.manifest[
                "request_initialisation_start"
            ],
            "2024-03-14",
        )

        self.assertEqual(
            self.manifest[
                "request_initialisation_end"
            ],
            "2026-03-15",
        )

        self.assertEqual(
            self.manifest[
                "request_initialisation_dates"
            ],
            732,
        )

    def test_request_counts(self) -> None:
        self.assertEqual(
            len(self.plan),
            2928,
        )

        self.assertEqual(
            len(self.core),
            1464,
        )

        self.assertEqual(
            len(self.supplementary),
            1464,
        )

        self.assertEqual(
            len(self.support),
            730,
        )

    def test_request_keys_unique(self) -> None:
        self.assertTrue(
            self.plan["request_id"].is_unique
        )

        self.assertTrue(
            self.plan["run_init_utc"].is_unique
        )

        self.assertTrue(
            self.plan["request_url"].is_unique
        )

    def test_core_cycle_policy(self) -> None:
        self.assertEqual(
            sorted(
                self.core["cycle_utc"]
                .astype(int)
                .unique()
                .tolist()
            ),
            [0, 12],
        )

        self.assertTrue(
            as_bool(
                self.core[
                    "retrieval_selected"
                ]
            ).all()
        )

        counts = (
            self.core.groupby(
                "run_date"
            )["cycle_utc"]
            .nunique()
        )

        self.assertTrue(
            counts.eq(2).all()
        )

    def test_supplementary_cycle_policy(
        self,
    ) -> None:
        self.assertEqual(
            sorted(
                self.supplementary[
                    "cycle_utc"
                ]
                .astype(int)
                .unique()
                .tolist()
            ),
            [6, 18],
        )

        self.assertFalse(
            as_bool(
                self.supplementary[
                    "retrieval_selected"
                ]
            ).any()
        )

    def test_training_target_support(
        self,
    ) -> None:
        self.assertTrue(
            as_bool(
                self.support[
                    "support_complete"
                ]
            ).all()
        )

        self.assertTrue(
            self.support[
                "available_core_support_requests"
            ].eq(6).all()
        )

        self.assertEqual(
            self.support[
                "target_date"
            ].min(),
            "2024-03-16",
        )

        self.assertEqual(
            self.support[
                "target_date"
            ].max(),
            "2026-03-15",
        )

    def test_no_market_or_validation_dates(
        self,
    ) -> None:
        run_dates = pd.to_datetime(
            self.plan["run_date"],
            errors="raise",
        ).dt.date

        self.assertTrue(
            (
                run_dates
                < date(2026, 3, 16)
            ).all()
        )

        self.assertTrue(
            (
                run_dates
                < date(2026, 6, 1)
            ).all()
        )

    def test_no_network_or_outcomes(self) -> None:
        self.assertFalse(
            self.manifest[
                "network_requests_made"
            ]
        )

        self.assertFalse(
            self.manifest[
                "market_prices_accessed"
            ]
        )

        self.assertFalse(
            self.manifest[
                "realised_outcomes_accessed"
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

    def test_required_integrity_checks(
        self,
    ) -> None:
        required = self.checks.loc[
            as_bool(
                self.checks["required"]
            )
        ]

        self.assertTrue(
            as_bool(
                required["passed"]
            ).all()
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
                str(path),
            )

            self.assertEqual(
                sha256(path),
                expected_hash,
            )

    def test_version_1_preserved(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(V1_VERIFIER),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout
            + result.stderr,
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
