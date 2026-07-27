#!/usr/bin/env python3
"""Create canonical Notebook 05."""

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
        # 05 — Continuous Distribution Calibration

        This notebook calibrates the dispersion of the locked probabilistic
        model using development out-of-fold predictions only.

        Holdout and external-test outcomes are not accessed.
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
                    "continuous_calibration_spec.yaml"
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
                    "calibrate_selected_oof_distribution.py"
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
                "Development-only continuous calibration failed."
            )
        """
    ),
    markdown(
        """
        ## Median-preserving dispersion scaling

        Let \(Q(\tau)\) denote a predictive quantile and let \(m=Q(0.5)\).
        For a positive scale \(s\), the calibrated quantile is

        \[
        \\widetilde Q_s(\\tau)
        =
        m+s\\{Q(\\tau)-m\\}.
        \]

        This transformation changes predictive dispersion without changing
        the predictive median. Positive scaling also preserves quantile order.
        """
    ),
    code(
        """
        summary = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "05_calibration_candidate_summary.csv"
        )

        manifest = json.loads(
            (
                ROOT
                / "data/manifests/"
                "05_continuous_calibration_manifest.json"
            ).read_text(encoding="utf-8")
        )

        print(
            summary[
                [
                    "dispersion_scale",
                    "mean_date_crps",
                    "standard_error_date_crps",
                    "empirical_80_coverage",
                    "mean_80_width_c",
                    "within_one_standard_error",
                    "strict_crps_winner",
                    "selected_scale",
                ]
            ].to_string(index=False)
        )
        """
    ),
    markdown(
        """
        ## Selection principle

        CRPS remains the sole selection criterion.

        Coverage and interval width are reported as diagnostics but do not
        determine the selected scale. This avoids replacing a proper scoring
        rule with a collection of separate calibration targets.

        Among scales within one paired standard error of the strict CRPS
        winner, the selected scale is the one closest to one. Thus calibration
        is retained only when the development evidence supports changing the
        original distribution.
        """
    ),
    code(
        """
        assert manifest["calibration_locked"] is True
        assert manifest["holdout_accessed"] is False
        assert manifest["external_test_accessed"] is False
        assert manifest["market_data_accessed"] is False
        assert (
            manifest["maximum_predictive_median_change_c"]
            <= 1.0e-12
        )

        print(
            "Locked model:",
            manifest["selected_model"],
        )

        print(
            "Strict CRPS winner scale:",
            manifest["strict_crps_winner_scale"],
        )

        print(
            "Selected scale:",
            manifest["selected_scale"],
        )

        print(
            "Calibration applied:",
            manifest["calibration_applied"],
        )
        """
    ),
    markdown(
        """
        ## Evidential boundary

        This stage does not evaluate holdout transfer, June transfer,
        market-implied probabilities or trading returns.

        Event-probability regularisation is a later and separate operation.
        """
    ),
]

destination = Path(
    "notebooks/final/"
    "05_continuous_distribution_calibration.ipynb"
)

nbf.write(
    notebook,
    destination,
)

print("Created:", destination)
