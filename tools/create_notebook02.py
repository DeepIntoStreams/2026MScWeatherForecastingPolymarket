#!/usr/bin/env python3
"""Generate canonical Notebook 02."""

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


path = Path(
    "notebooks/final/"
    "02_deterministic_weather_training_panel.ipynb"
)

notebook = nbf.v4.new_notebook()

notebook["metadata"]["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}

notebook["cells"] = [
    markdown(
        """
        # 02 — Deterministic Weather Training Panel

        This notebook constructs the deterministic forecast sample used by
        the probabilistic post-processing models.

        Weather model training is separated from Polymarket evaluation.
        Training requires an admissible forecast and the later HKO outcome;
        it does not require a market.
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
                if (candidate / "config/notebook02.yaml").exists():
                    return candidate

            raise FileNotFoundError("Repository root not found.")

        ROOT = locate_repository(Path.cwd())

        print(f"Repository root: {ROOT}")
        """
    ),
    code(
        """
        training = pd.read_csv(
            ROOT
            / "data/processed/"
            "02_weather_training_panel.csv"
        )

        evaluation = pd.read_csv(
            ROOT
            / "data/processed/"
            "02_market_evaluation_forecast_panel.csv"
        )

        selected = pd.read_csv(
            ROOT
            / "data/processed/"
            "02_selected_deterministic_forecast_panel.csv"
        )

        admission = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "02_forecast_admission_audit.csv"
        )

        reconciliation = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "02_hourly_daily_reconciliation.csv"
        )

        mapping = pd.read_csv(
            ROOT
            / "outputs/diagnostics/"
            "02_request_timestamp_mapping.csv"
        )

        summary = json.loads(
            (
                ROOT
                / "outputs/diagnostics/"
                "02_panel_construction_summary.json"
            ).read_text(encoding="utf-8")
        )

        print("Status:", summary["status"])
        print("Selected forecast rows:", len(selected))
        print("Weather training rows:", len(training))
        print(
            "Weather training dates:",
            training["target_date"].nunique(),
        )
        print("Market evaluation rows:", len(evaluation))
        print(
            "Market evaluation dates:",
            evaluation["target_date"].nunique(),
        )
        """
    ),
    markdown(
        """
        ## Candidate path and time information

        One candidate forecast path is identified by its source, target date,
        decision rule and forecast issue time.

        Issue and decision timestamps are read from the historical request
        plans and merged into the hourly forecasts by target date and decision
        rule. The request identifier remains as provenance.
        """
    ),
    code(
        """
        print(
            mapping[
                [
                    "source",
                    "issue_column",
                    "decision_column",
                ]
            ].to_string(index=False)
        )
        """
    ),
    markdown(
        """
        ## Admission and selection

        A path must contain 24 unique hourly positions on the Hong Kong local
        target date. Its issue time must not exceed the decision time.

        If several paths are admissible, the latest issue time available by
        the decision is selected. Source preference breaks only an exact tie.
        """
    ),
    code(
        """
        assert selected[
            "unique_local_hours"
        ].eq(24).all()

        issue = pd.to_datetime(
            selected[
                "forecast_issue_time_utc"
            ],
            utc=True,
        )

        decision = pd.to_datetime(
            selected[
                "decision_time_utc"
            ],
            utc=True,
        )

        assert issue.notna().all()
        assert decision.notna().all()
        assert (issue <= decision).all()

        assert not selected[
            ["target_date", "decision_rule"]
        ].duplicated().any()

        print(
            "All paths contain 24 HKT hours:",
            selected[
                "unique_local_hours"
            ].eq(24).all(),
        )

        print(
            "All forecasts available by decision time:",
            bool(
                (issue <= decision).all()
            ),
        )
        """
    ),
    code(
        """
        admission_summary = (
            admission.groupby(
                ["status", "reason"],
                dropna=False,
            )
            .size()
            .reset_index(name="candidate_paths")
            .sort_values(
                [
                    "status",
                    "candidate_paths",
                ],
                ascending=[
                    True,
                    False,
                ],
            )
        )

        print(
            admission_summary.to_string(
                index=False
            )
        )
        """
    ),
    markdown(
        """
        ## Daily maximum

        The deterministic daily maximum is the maximum of the 24 admitted
        hourly forecasts. The archived daily maximum table is used as a
        reconciliation check, not as another model.
        """
    ),
    code(
        """
        reconciliation_summary = (
            reconciliation[
                "reconciliation_status"
            ]
            .value_counts(dropna=False)
            .rename_axis("status")
            .reset_index(name="rows")
        )

        print(
            reconciliation_summary.to_string(
                index=False
            )
        )
        """
    ),
    code(
        """
        support_by_rule = (
            training.groupby(
                "decision_rule"
            )
            .agg(
                rows=("target_date", "size"),
                dates=("target_date", "nunique"),
                start_date=("target_date", "min"),
                end_date=("target_date", "max"),
                mean_forecast_c=(
                    "forecast_daily_max_c",
                    "mean",
                ),
                mean_hko_c=(
                    "hko_daily_max_c",
                    "mean",
                ),
                mean_residual_c=(
                    "residual_c",
                    "mean",
                ),
            )
            .reset_index()
        )

        print(
            support_by_rule.to_string(
                index=False
            )
        )
        """
    ),
    markdown(
        """
        ## Current sample boundary

        The current official HKO outcome table ends on 30 June 2026. July and
        August can later be appended by refreshing official outcomes and
        rerunning this unchanged construction.
        """
    ),
]

path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

nbf.write(
    notebook,
    path,
)

print(f"Created {path}")
