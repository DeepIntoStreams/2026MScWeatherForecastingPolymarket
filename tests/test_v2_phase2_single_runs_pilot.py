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
    / "data/manifests/v2/"
    "01_single_runs_pilot_manifest.json"
)

SPEC_PATH = (
    ROOT
    / "config/v2/"
    "single_runs_pilot_spec.json"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "01_single_runs_pilot_integrity_checks.csv"
)

PROBES_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "01_single_runs_archive_probe_results.csv"
)

BOUNDARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "01_single_runs_archive_boundary_audit.csv"
)

REQUEST_PLAN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "01_single_runs_pilot_request_plan.csv"
)

OVERLAP_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "01_single_runs_overlap_reconstruction.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/v2/"
    "01_single_runs_source_pilot.ipynb"
)

V1_VERIFIER_PATH = (
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


class Phase2SingleRunsPilotTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.spec = json.loads(
            SPEC_PATH.read_text(
                encoding="utf-8"
            )
        )

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

        cls.probes = pd.read_csv(
            PROBES_PATH
        )

        cls.boundary = pd.read_csv(
            BOUNDARY_PATH
        )

        cls.request_plan = pd.read_csv(
            REQUEST_PLAN_PATH
        )

        cls.overlap = pd.read_csv(
            OVERLAP_PATH
        )

    def test_phase_status(self) -> None:
        self.assertEqual(
            self.manifest["phase_status"],
            "PHASE2_COMPLETE",
        )

        self.assertTrue(
            self.manifest["pilot_approved"]
        )

        self.assertIn(
            self.manifest["status"],
            {
                "SINGLE_RUNS_PILOT_APPROVED",
                (
                    "SINGLE_RUNS_PILOT_APPROVED_"
                    "WITH_OVERLAP_DIFFERENCES"
                ),
            },
        )

    def test_historical_cycle_policy(self) -> None:
        self.assertEqual(
            self.manifest[
                "historical_training_core_cycles_utc"
            ],
            [0, 12],
        )

        self.assertEqual(
            self.manifest[
                "supplementary_cycles_utc"
            ],
            [6, 18],
        )

        self.assertFalse(
            self.manifest[
                "four_cycle_archive_completeness_assumed"
            ]
        )

    def test_archive_probes(self) -> None:
        self.assertEqual(
            len(self.probes),
            4,
        )

        self.assertTrue(
            as_bool(
                self.probes[
                    "request_succeeded"
                ]
            ).all()
        )

        self.assertTrue(
            pd.to_numeric(
                self.probes["hourly_rows"],
                errors="coerce",
            ).ge(24).all()
        )

        self.assertTrue(
            self.probes[
                "returned_timezone"
            ].eq(
                "Asia/Hong_Kong"
            ).all()
        )

    def test_archive_boundary_evidence(self) -> None:
        archive_start = self.boundary.loc[
            self.boundary["window"].eq(
                "archive_start"
            )
        ].copy()

        archive_start["usable"] = (
            as_bool(
                archive_start[
                    "request_succeeded"
                ]
            )
            & pd.to_numeric(
                archive_start["hourly_rows"],
                errors="coerce",
            ).ge(24)
            & archive_start[
                "returned_timezone"
            ].eq(
                "Asia/Hong_Kong"
            )
        )

        total_dates = (
            archive_start[
                "run_date"
            ].nunique()
        )

        coverage = (
            archive_start.groupby(
                "cycle_utc"
            )["usable"]
            .sum()
        )

        self.assertEqual(
            int(coverage.loc[0]),
            total_dates,
        )

        self.assertEqual(
            int(coverage.loc[12]),
            total_dates,
        )

        self.assertLess(
            int(coverage.loc[6]),
            total_dates,
        )

        self.assertLess(
            int(coverage.loc[18]),
            total_dates,
        )

    def test_required_integrity_checks(self) -> None:
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

    def test_overlap_dimensions(self) -> None:
        self.assertEqual(
            len(self.request_plan),
            20,
        )

        self.assertEqual(
            len(self.overlap),
            20,
        )

        self.assertEqual(
            self.overlap[
                "target_date"
            ].nunique(),
            5,
        )

        self.assertEqual(
            self.overlap[
                "decision_rule"
            ].nunique(),
            4,
        )

    def test_local_day_and_timing(self) -> None:
        self.assertTrue(
            self.overlap[
                "local_hour_count"
            ].eq(24).all()
        )

        self.assertTrue(
            as_bool(
                self.overlap[
                    "available_before_decision"
                ]
            ).all()
        )

    def test_exact_overlap_reconstruction(self) -> None:
        differences = pd.to_numeric(
            self.overlap[
                "absolute_difference_c"
            ],
            errors="coerce",
        )

        self.assertFalse(
            differences.isna().any()
        )

        self.assertEqual(
            float(differences.max()),
            0.0,
        )

    def test_evidential_boundary(self) -> None:
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

    def test_tracked_evidence_hashes(self) -> None:
        for (
            relative_path,
            expected_hash,
        ) in self.manifest[
            "tracked_evidence_hashes"
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
                str(V1_VERIFIER_PATH),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
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
