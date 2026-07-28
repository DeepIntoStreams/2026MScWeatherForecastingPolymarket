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
    "05_weather_only_residual_manifest.json"
)

PANEL_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_forecast_residual_panel.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_residual_integrity_checks.csv"
)

RULE_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_residual_rule_summary.csv"
)

NOTEBOOK_PATH = (
    ROOT
    / "notebooks/v2/"
    "05_weather_only_forecast_residuals.ipynb"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


class Phase5ResidualTests(unittest.TestCase):
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

        cls.checks = pd.read_csv(
            CHECKS_PATH
        )

        cls.rule_summary = pd.read_csv(
            RULE_SUMMARY_PATH
        )

    def test_status(self) -> None:
        self.assertEqual(
            self.manifest["status"],
            "TWO_YEAR_FORECAST_RESIDUAL_PANEL_CERTIFIED",
        )

    def test_dimensions(self) -> None:
        self.assertEqual(
            len(self.panel),
            2920,
        )

        self.assertEqual(
            self.panel[
                "target_date"
            ].nunique(),
            730,
        )

        self.assertEqual(
            self.panel[
                "decision_rule"
            ].nunique(),
            4,
        )

    def test_unique_date_rule_keys(self) -> None:
        self.assertFalse(
            self.panel.duplicated(
                [
                    "target_date",
                    "decision_rule",
                ]
            ).any()
        )

    def test_four_rules_per_date(self) -> None:
        counts = self.panel.groupby(
            "target_date"
        )["decision_rule"].nunique()

        self.assertTrue(
            counts.eq(4).all()
        )

    def test_residual_definition(self) -> None:
        expected = (
            self.panel[
                "hko_daily_max_c"
            ]
            - self.panel[
                "forecast_daily_max_c"
            ]
        )

        self.assertTrue(
            np.allclose(
                self.panel[
                    "residual_c"
                ],
                expected,
                atol=1e-12,
                rtol=0.0,
            )
        )

    def test_forecast_error_definition(self) -> None:
        expected = (
            self.panel[
                "forecast_daily_max_c"
            ]
            - self.panel[
                "hko_daily_max_c"
            ]
        )

        self.assertTrue(
            np.allclose(
                self.panel[
                    "forecast_error_c"
                ],
                expected,
                atol=1e-12,
                rtol=0.0,
            )
        )

    def test_seasonal_features_finite(self) -> None:
        self.assertTrue(
            np.isfinite(
                self.panel[
                    [
                        "seasonal_sin",
                        "seasonal_cos",
                    ]
                ].to_numpy()
            ).all()
        )

    def test_rule_summary(self) -> None:
        self.assertEqual(
            len(self.rule_summary),
            4,
        )

        self.assertEqual(
            set(
                self.rule_summary[
                    "decision_rule"
                ]
            ),
            {
                "24h_prior",
                "12h_prior",
                "6h_prior",
                "event_day_open",
            },
        )

        self.assertTrue(
            self.rule_summary[
                "rows"
            ].eq(730).all()
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
                "model_selected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "calibration_selected"
            ]
        )

        self.assertFalse(
            self.manifest[
                "trading_returns_calculated"
            ]
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
