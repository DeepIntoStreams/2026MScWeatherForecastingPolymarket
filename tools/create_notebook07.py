#!/usr/bin/env python3
"""Create canonical Notebook 07."""

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


def markdown(text: str):
    return nbf.v4.new_markdown_cell(
        dedent(text).strip()
    )


def code(text: str):
    return nbf.v4.new_code_cell(
        dedent(text).strip()
    )


notebook = nbf.v4.new_notebook()

notebook["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
}

notebook["cells"] = [
    markdown(
        """
        # 07 — Locked Continuous Evaluation

        This notebook evaluates the predictive distributions generated and
        locked in Notebook 06.

        The raw deterministic forecast, the selected uncalibrated distribution
        and the selected calibrated distribution are compared separately on
        the holdout and June external blocks.
        """
    ),
    code(
        """
        from pathlib import Path
        import json
        import subprocess
        import sys

        import pandas as pd

        def locate_repository(start: Path) -> Path:
            current = start.resolve()

            for candidate in (current, *current.parents):
                if (
                    candidate
                    / "config/"
                    "continuous_evaluation_spec.yaml"
                ).exists():
                    return candidate

            raise FileNotFoundError("Repository root not found.")

        ROOT = locate_repository(Path.cwd())

        completed = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "tools/"
                    "evaluate_locked_continuous_predictions.py"
                ),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        print(completed.stdout)

        if completed.returncode != 0:
            print(completed.stderr)
            raise RuntimeError(
                "Locked continuous evaluation failed."
            )
        """
    ),
    markdown(
        """
        ## Primary score

        The continuous ranked probability score evaluates the full predictive
        distribution.

        A score is first calculated for every date and decision-rule
        observation. Scores are then averaged within settlement date, after
        which the date-level values are averaged within each evaluation block.

        Settlement date is therefore the primary uncertainty unit.
        """
    ),
    code(
        """
        summary = pd.read_csv(
            ROOT
            / "outputs/final_tables/"
            "07_continuous_block_summary.csv"
        )

        print(
            summary[
                [
                    "chronology_block",
                    "forecast_variant_display",
                    "mean_date_crps",
                    "standard_error_date_crps",
                    "relative_crps_reduction_vs_raw",
                    "median_mae_c",
                    "median_bias_c",
                    "empirical_80_coverage",
                    "mean_80_width_c",
                ]
            ].to_string(index=False)
        )
        """
    ),
    markdown(
        """
        ## Secondary diagnostics

        Predictive median error measures the central location of each
        distribution.

        Empirical coverage and average width are reported for the central
        50 per cent, 80 per cent and 90 per cent intervals. Coverage measures
        reliability, whereas interval width measures concentration.

        These diagnostics did not determine model or calibration selection.
        """
    ),
    code(
        """
        pairwise = pd.read_csv(
            ROOT
            / "outputs/final_tables/"
            "07_continuous_pairwise_comparison.csv"
        )

        print(
            pairwise[
                [
                    "chronology_block",
                    "left_display",
                    "right_display",
                    "paired_dates",
                    "mean_paired_crps_difference",
                    "descriptive_95_interval_lower",
                    "descriptive_95_interval_upper",
                    "left_better_date_share",
                ]
            ].to_string(index=False)
        )
        """
    ),
    markdown(
        """
        ## Paired differences

        Each comparison uses date-level CRPS differences. A negative
        difference means that the forecast listed on the left has the lower
        CRPS.

        The reported intervals use the standard error across settlement
        dates. They are descriptive rather than formal significance tests
        because dates may be serially dependent and the holdout contains only
        ten dates.
        """
    ),
    code(
        """
        manifest = json.loads(
            (
                ROOT
                / "data/manifests/"
                "07_continuous_evaluation_manifest.json"
            ).read_text(encoding="utf-8")
        )

        assert manifest["evaluation_locked"] is True
        assert manifest["model_refitted_during_evaluation"] is False
        assert manifest["model_reselected_during_evaluation"] is False
        assert manifest["calibration_reselected_during_evaluation"] is False
        assert manifest["event_probabilities_calculated"] is False
        assert manifest["market_data_accessed"] is False
        assert manifest["trading_returns_calculated"] is False

        print(
            "Evaluation completed without changing the locked design:",
            True,
        )
        """
    ),
    markdown(
        """
        ## Evidential boundary

        This notebook answers whether probabilistic post-processing improves
        the raw deterministic temperature forecast.

        It does not yet answer whether the forecast outperforms Polymarket or
        generates economic value. Those questions require event probabilities,
        market prices and a separately specified trading rule.
        """
    ),
]

destination = Path(
    "notebooks/final/"
    "07_locked_continuous_evaluation.ipynb"
)

nbf.write(
    notebook,
    destination,
)

print("Created:", destination)
