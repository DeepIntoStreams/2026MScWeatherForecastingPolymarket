#!/usr/bin/env python3
"""Generate verified canonical Notebooks 02 and 03."""

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


def metadata():
    return {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        }
    }


notebook02 = nbf.v4.new_notebook()
notebook02["metadata"] = metadata()

notebook02["cells"] = [
    markdown(
        """
        # 02 — Verified Deterministic Forecast Panel

        This notebook constructs the deterministic forecast and HKO outcome
        panel used by the probabilistic post-processing models.

        Only forecast paths that can be independently certified from 24
        Hong Kong local hourly forecasts are retained.
        """
    ),
    code(
        """
        from pathlib import Path
        import json

        import pandas as pd

        def locate_repository(start: Path) -> Path:
            current = start.resolve()

            for candidate in (current, *current.parents):
                if (
                    candidate
                    / "data/manifests/"
                    "02_verified_full_panel_manifest.json"
                ).exists():
                    return candidate

            raise FileNotFoundError("Repository root not found.")

        ROOT = locate_repository(Path.cwd())

        selected = pd.read_csv(
            ROOT
            / "data/processed/"
            "02_selected_deterministic_forecast_panel.csv"
        )

        training = pd.read_csv(
            ROOT
            / "data/processed/"
            "02_weather_training_panel.csv"
        )

        reconciliation = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "02_historical_daily_hourly_reconciliation.csv"
        )

        support = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "02_date_rule_support_matrix.csv"
        )

        summary = json.loads(
            (
                ROOT
                / "outputs/diagnostics/"
                "02_full_support_summary.json"
            ).read_text(encoding="utf-8")
        )

        print("Status:", summary["status"])
        print("Verified rows:", len(selected))
        print("Verified dates:", selected["target_date"].nunique())
        print("Historical rows:", summary["historical_verified_rows"])
        print("June rows:", summary["june_verified_rows"])
        """
    ),
    markdown(
        """
        ## Historical forecast identification

        The stored column `forecast_hko_daily_max_C` is a forecast of the
        daily maximum at the HKO location. It is not the realised HKO target.

        On all 256 independently reconstructed historical paths, the stored
        value and the maximum of the 24 hourly forecasts agree exactly.
        """
    ),
    code(
        """
        assert len(reconciliation) == 256

        assert reconciliation[
            "unique_local_hours"
        ].eq(24).all()

        assert reconciliation[
            "absolute_difference_c"
        ].le(1e-9).all()

        print(
            "Maximum stored-versus-reconstructed discrepancy:",
            reconciliation[
                "absolute_difference_c"
            ].max(),
        )
        """
    ),
    markdown(
        """
        ## Information-time condition

        Every forecast issue time must be no later than the applicable
        decision cutoff. Settlement date is used as the uncertainty unit.
        """
    ),
    code(
        """
        issue = pd.to_datetime(
            selected["forecast_issue_time_utc"],
            utc=True,
        )

        decision = pd.to_datetime(
            selected["decision_time_utc"],
            utc=True,
        )

        assert issue.notna().all()
        assert decision.notna().all()
        assert (issue <= decision).all()

        assert not selected[
            ["target_date", "decision_rule"]
        ].duplicated().any()

        print(
            "All forecasts available by decision time:",
            bool((issue <= decision).all()),
        )
        """
    ),
    markdown(
        """
        ## Evidential boundary

        Thirty-six March-May request rows are not promoted into the empirical
        sample because no complete independently verified hourly path is
        available. One June date-rule combination is also unavailable.

        The retained panel therefore contains 375 date-rule observations over
        102 settlement dates.
        """
    ),
    code(
        """
        missing = support.loc[
            ~support["forecast_present"],
            [
                "target_date",
                "decision_rule",
                "support_status",
            ],
        ]

        print(
            missing[
                "support_status"
            ].value_counts().to_string()
        )

        assert len(missing) == 37
        assert len(selected) == 375
        assert selected["target_date"].nunique() == 102
        """
    ),
    code(
        """
        support_by_period = (
            selected.groupby("source_period")
            .agg(
                rows=("target_date", "size"),
                dates=("target_date", "nunique"),
                start_date=("target_date", "min"),
                end_date=("target_date", "max"),
            )
            .reset_index()
        )

        print(support_by_period.to_string(index=False))
        """
    ),
]


notebook03 = nbf.v4.new_notebook()
notebook03["metadata"] = metadata()

notebook03["cells"] = [
    markdown(
        """
        # 03 — Chronological Empirical Design

        The empirical blocks are declared before any probabilistic model is
        fitted. Random splitting is prohibited and settlement date is the
        uncertainty unit.
        """
    ),
    code(
        """
        from pathlib import Path
        import json

        import pandas as pd
        import yaml

        def locate_repository(start: Path) -> Path:
            current = start.resolve()

            for candidate in (current, *current.parents):
                if (
                    candidate
                    / "config/"
                    "chronology_policy.yaml"
                ).exists():
                    return candidate

            raise FileNotFoundError("Repository root not found.")

        ROOT = locate_repository(Path.cwd())

        panel = pd.read_csv(
            ROOT
            / "data/processed/"
            "02_chronological_design_panel.csv"
        )

        blocks = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "03_chronology_block_summary.csv"
        )

        folds = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "03_development_fold_summary.csv"
        )

        policy = yaml.safe_load(
            (
                ROOT
                / "config/"
                "chronology_policy.yaml"
            ).read_text(encoding="utf-8")
        )

        manifest = json.loads(
            (
                ROOT
                / "data/manifests/"
                "03_chronology_manifest.json"
            ).read_text(encoding="utf-8")
        )

        print("Status:", policy["status"])
        print(
            "Model fitting permitted:",
            policy["model_fitting_permitted"],
        )
        print()
        print(blocks.to_string(index=False))
        """
    ),
    markdown(
        """
        ## Expanding validation

        The warm-up block forms the initial training sample. Development dates
        are divided into four contiguous validation folds.

        For every fold, all training dates precede the validation dates. Model
        families are compared using date-grouped out-of-fold CRPS.
        """
    ),
    code(
        """
        assert len(folds) == 4
        assert folds["date_sets_disjoint"].all()
        assert folds["training_precedes_validation"].all()

        print(folds.to_string(index=False))
        """
    ),
    markdown(
        """
        ## Locked evaluation periods

        Holdout and external outcomes cannot affect the model family,
        hyperparameters, calibration choice or trading rule.

        The model fitted before the holdout is transferred to June without
        refitting after observing holdout outcomes.
        """
    ),
    code(
        """
        locked = panel[
            "chronology_block"
        ].isin(
            ["holdout", "external_test"]
        )

        assert not panel.loc[
            locked,
            "outcome_may_influence_model_choice",
        ].any()

        assert not panel[
            "used_to_refit_before_external_test"
        ].any()

        assert manifest["holdout_locked"] is True
        assert manifest["external_test_locked"] is True
        assert manifest["refit_before_external_test"] is False

        print(
            "Holdout and external outcomes excluded from selection:",
            True,
        )
        """
    ),
    markdown(
        """
        ## Later observations

        July and August observations may be appended as an additional temporal
        extension. They cannot retroactively alter any model or decision rule
        selected from the declared development period.
        """
    ),
]

path02 = Path(
    "notebooks/final/"
    "02_deterministic_weather_training_panel.ipynb"
)

path03 = Path(
    "notebooks/final/"
    "03_chronological_design.ipynb"
)

nbf.write(
    notebook02,
    path02,
)

nbf.write(
    notebook03,
    path03,
)

print("Created:", path02)
print("Created:", path03)
