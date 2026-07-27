#!/usr/bin/env python3
"""Create canonical Notebook 06."""

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
        # 06 — Locked Predictive Distributions

        This notebook fits the locked probabilistic specification using all
        warm-up and development observations.

        It then generates holdout and June predictive distributions using the
        dispersion scale selected in Notebook 05.

        No realised holdout or June outcome enters model fitting or appears in
        the prediction output.
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
                    "locked_prediction_spec.yaml"
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
                    "generate_locked_evaluation_predictions.py"
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
                "Locked prediction generation failed."
            )
        """
    ),
    markdown(
        """
        ## Final fitting sample

        The selected model is fitted using only the warm-up and development
        blocks. The fitting sample therefore ends before the first holdout
        date.

        No refitting occurs after observing holdout outcomes.
        """
    ),
    code(
        """
        manifest = json.loads(
            (
                ROOT
                / "data/manifests/"
                "06_locked_prediction_manifest.json"
            ).read_text(encoding="utf-8")
        )

        blocks = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "06_locked_prediction_block_summary.csv"
        )

        print("Selected model:", manifest["selected_model"])
        print("Selected family:", manifest["selected_family"])
        print(
            "Dispersion scale:",
            manifest["selected_dispersion_scale"],
        )
        print()
        print(
            "Training period:",
            manifest["training_start"],
            "to",
            manifest["training_end"],
        )
        print()
        print(blocks.to_string(index=False))
        """
    ),
    markdown(
        """
        ## Locked prediction files

        Both the uncalibrated and calibrated distributions contain 99
        quantiles.

        Calibration changes the dispersion around the median but leaves the
        predictive median unchanged.
        """
    ),
    code(
        """
        calibrated = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "06_locked_calibrated_predictions.csv"
        )

        prohibited = [
            column
            for column in calibrated.columns
            if any(
                term in column.lower()
                for term in [
                    "hko_daily_max",
                    "residual",
                    "outcome",
                    "crps",
                    "brier",
                    "pnl",
                    "market_price",
                ]
            )
        ]

        assert not prohibited
        assert len(calibrated) == 159
        assert calibrated["target_date"].nunique() == 40

        print(
            "Locked prediction rows:",
            len(calibrated),
        )

        print(
            "Locked prediction dates:",
            calibrated["target_date"].nunique(),
        )
        """
    ),
    markdown(
        """
        ## Evidential boundary

        This notebook generates forecasts but does not evaluate them.

        Continuous scoring, event probability construction, market comparison
        and trading analysis are separate later stages.
        """
    ),
    code(
        """
        assert manifest["predictions_locked"] is True
        assert manifest["holdout_outcomes_used_for_fit"] is False
        assert manifest["external_test_outcomes_used_for_fit"] is False
        assert manifest["continuous_scores_calculated"] is False
        assert manifest["event_probabilities_calculated"] is False
        assert manifest["market_data_accessed"] is False
        assert manifest["trading_returns_calculated"] is False

        print(
            "Predictions locked without evaluation:",
            True,
        )
        """
    ),
]

destination = Path(
    "notebooks/final/"
    "06_locked_predictive_distributions.ipynb"
)

nbf.write(
    notebook,
    destination,
)

print("Created:", destination)
