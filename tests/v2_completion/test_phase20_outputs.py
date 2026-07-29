from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd


class Phase20OutputTest(unittest.TestCase):
    def test_output_files_and_figures(self) -> None:
        root = Path(__file__).resolve().parents[2]

        expected_nonempty = [
            "phase20_probability_column_audit.csv",
            "phase20_outcome_column_audit.csv",
            "phase20_combination_weight_bootstrap.csv",
            "phase20_rule_specific_weight_diagnostics.csv",
            "phase20_date_score_panel.csv",
            "phase20_book_discrepancy_summary.csv",
            "phase20_rank_discrepancy_summary.csv",
            "phase20_discrepancy_regression_coefficients.csv",
            "phase20_discrepancy_regression_summary.csv",
        ]
        for filename in expected_nonempty:
            frame = pd.read_csv(
                root / "outputs/v2_completion" / filename
            )
            self.assertGreater(len(frame), 0)

        figure_names = [
            "phase20_weight_objective",
            "phase20_weight_bootstrap",
            "phase20_june_score_comparison",
            "phase20_total_variation_by_rule",
            "phase20_rank_discrepancy_event_day_open",
        ]
        for name in figure_names:
            for suffix in ("png", "pdf"):
                path = (
                    root
                    / "outputs/v2_completion/phase20_figures"
                    / f"{name}.{suffix}"
                )
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 1000)

        report = (
            root
            / "outputs/v2_completion/"
            / "phase20_forecast_combination_report.md"
        )
        self.assertTrue(report.is_file())
        self.assertIn(
            "## Evidential boundary",
            report.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
