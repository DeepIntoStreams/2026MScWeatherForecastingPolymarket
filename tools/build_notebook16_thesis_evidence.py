from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/thesis"
FIGURES = OUTPUT / "figures"

MANIFEST_PATH = (
    ROOT
    / "data/manifests/"
    "16_thesis_evidence_manifest.json"
)

SOURCES = {
    "model_selection_manifest": (
        ROOT
        / "data/manifests/"
        "04_model_selection_manifest.json"
    ),
    "continuous_calibration_manifest": (
        ROOT
        / "data/manifests/"
        "05_continuous_calibration_manifest.json"
    ),
    "probability_calibration_manifest": (
        ROOT
        / "data/manifests/"
        "09_probability_calibration_manifest.json"
    ),
    "release_manifest": (
        ROOT
        / "data/manifests/"
        "15_reproducibility_release_manifest.json"
    ),
    "categorical_evaluation": (
        ROOT
        / "outputs/final_tables/"
        "10_locked_categorical_block_summary.csv"
    ),
    "market_comparison": (
        ROOT
        / "outputs/final_tables/"
        "11_common_support_block_summary.csv"
    ),
    "trading_evaluation": (
        ROOT
        / "outputs/final_tables/"
        "12_trading_strategy_summary.csv"
    ),
    "uncertainty_main": (
        ROOT
        / "outputs/final_tables/"
        "13_uncertainty_main_table.csv"
    ),
    "uncertainty_rule": (
        ROOT
        / "outputs/final_tables/"
        "13_uncertainty_rule_sensitivity.csv"
    ),
    "claim_boundaries": (
        ROOT
        / "outputs/final_tables/"
        "14_claim_boundary_table.csv"
    ),
}


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def first_value(
    mapping: dict[str, Any],
    names: list[str],
) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]

    return None


def first_column(
    frame: pd.DataFrame,
    patterns: list[str],
) -> str | None:
    for pattern in patterns:
        regex = re.compile(
            pattern,
            flags=re.IGNORECASE,
        )

        for column in frame.columns:
            if regex.search(
                str(column)
            ):
                return str(column)

    return None


def select_columns(
    frame: pd.DataFrame,
    patterns: list[str],
    maximum: int = 16,
) -> pd.DataFrame:
    selected: list[str] = []

    for column in frame.columns:
        if any(
            re.search(
                pattern,
                str(column),
                flags=re.IGNORECASE,
            )
            for pattern in patterns
        ):
            selected.append(
                str(column)
            )

    selected = list(
        dict.fromkeys(
            selected
        )
    )[:maximum]

    if not selected:
        selected = list(
            frame.columns[:maximum]
        )

    return frame.loc[
        :,
        selected,
    ].copy()


def write_table(
    frame: pd.DataFrame,
    stem: str,
) -> tuple[Path, Path]:
    csv_path = OUTPUT / f"{stem}.csv"
    tex_path = OUTPUT / f"{stem}.tex"

    frame.to_csv(
        csv_path,
        index=False,
        float_format="%.8f",
    )

    latex = frame.to_latex(
        index=False,
        escape=True,
        na_rep="",
        float_format=lambda value: (
            f"{value:.6f}"
        ),
    )

    tex_path.write_text(
        latex,
        encoding="utf-8",
    )

    return (
        csv_path,
        tex_path,
    )


def tex_escape(value: Any) -> str:
    text = str(value)

    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    return text


def bool_is_true(value: Any) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    return (
        str(value)
        .strip()
        .lower()
        in {
            "true",
            "1",
            "yes",
        }
    )


def create_model_figure(
    raw_crps: float,
    selected_crps: float,
    selected_model: str,
) -> Path:
    figure_path = (
        FIGURES
        / "16_model_selection_crps.png"
    )

    figure, axis = plt.subplots(
        figsize=(8, 5)
    )

    labels = [
        "Raw deterministic",
        selected_model.replace(
            "_",
            " ",
        ),
    ]

    values = [
        raw_crps,
        selected_crps,
    ]

    axis.bar(
        labels,
        values,
    )

    axis.set_ylabel(
        "Mean date CRPS"
    )

    axis.set_title(
        "Development model comparison"
    )

    axis.tick_params(
        axis="x",
        rotation=15,
    )

    figure.tight_layout()

    figure.savefig(
        figure_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )

    return figure_path


def create_comparison_figure(
    frame: pd.DataFrame,
) -> Path | None:
    block_column = first_column(
        frame,
        [
            r"^chronology_block$",
            r"evaluation.*block",
            r"sample.*block",
            r"^block$",
        ],
    )

    model_column = first_column(
        frame,
        [
            r"mean_date_model_log_score",
            r"model.*log.*score",
        ],
    )

    market_column = first_column(
        frame,
        [
            r"mean_date_market_log_score",
            r"market.*log.*score",
        ],
    )

    if not all(
        [
            block_column,
            model_column,
            market_column,
        ]
    ):
        return None

    plot_frame = frame[
        [
            block_column,
            model_column,
            market_column,
        ]
    ].copy()

    plot_frame[
        model_column
    ] = pd.to_numeric(
        plot_frame[
            model_column
        ],
        errors="coerce",
    )

    plot_frame[
        market_column
    ] = pd.to_numeric(
        plot_frame[
            market_column
        ],
        errors="coerce",
    )

    plot_frame = plot_frame.dropna()

    if plot_frame.empty:
        return None

    figure_path = (
        FIGURES
        / "16_model_market_log_score.png"
    )

    plot_frame = plot_frame.set_index(
        block_column
    )

    axis = plot_frame.plot.bar(
        figsize=(9, 5)
    )

    axis.set_ylabel(
        "Mean date categorical log score"
    )

    axis.set_xlabel(
        "Evaluation block"
    )

    axis.set_title(
        "Locked model and market comparison"
    )

    axis.tick_params(
        axis="x",
        rotation=0,
    )

    axis.figure.tight_layout()

    axis.figure.savefig(
        figure_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        axis.figure
    )

    return figure_path


def create_trading_figure(
    frame: pd.DataFrame,
) -> Path | None:
    block_column = first_column(
        frame,
        [
            r"^chronology_block$",
            r"evaluation.*block",
            r"sample.*block",
            r"^block$",
        ],
    )

    payoff_column = first_column(
        frame,
        [
            r"mean_date_net_payoff",
            r"net.*payoff",
            r"net.*return",
        ],
    )

    if not block_column or not payoff_column:
        return None

    plot_frame = frame[
        [
            block_column,
            payoff_column,
        ]
    ].copy()

    plot_frame[
        payoff_column
    ] = pd.to_numeric(
        plot_frame[
            payoff_column
        ],
        errors="coerce",
    )

    plot_frame = plot_frame.dropna()

    if plot_frame.empty:
        return None

    figure_path = (
        FIGURES
        / "16_locked_trading_payoff.png"
    )

    figure, axis = plt.subplots(
        figsize=(8, 5)
    )

    axis.bar(
        plot_frame[
            block_column
        ].astype(str),
        plot_frame[
            payoff_column
        ],
    )

    axis.axhline(
        0.0,
        linewidth=1,
    )

    axis.set_ylabel(
        payoff_column.replace(
            "_",
            " ",
        )
    )

    axis.set_xlabel(
        "Evaluation block"
    )

    axis.set_title(
        "Locked reduced-form trading evaluation"
    )

    figure.tight_layout()

    figure.savefig(
        figure_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )

    return figure_path


def main() -> None:
    OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    FIGURES.mkdir(
        parents=True,
        exist_ok=True,
    )

    missing = [
        relative(path)
        for path in SOURCES.values()
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Notebook 16 sources are missing:\n  "
            + "\n  ".join(
                missing
            )
        )

    model = load_json(
        SOURCES[
            "model_selection_manifest"
        ]
    )

    continuous = load_json(
        SOURCES[
            "continuous_calibration_manifest"
        ]
    )

    probability = load_json(
        SOURCES[
            "probability_calibration_manifest"
        ]
    )

    release = load_json(
        SOURCES[
            "release_manifest"
        ]
    )

    if (
        release.get(
            "status"
        )
        != "FINAL_EMPIRICAL_RELEASE_CERTIFIED"
    ):
        raise RuntimeError(
            "The Notebook 15 empirical release "
            "is not certified."
        )

    if not bool_is_true(
        release.get(
            "release_ready"
        )
    ):
        raise RuntimeError(
            "The Notebook 15 release is not marked ready."
        )

    selected_model = model.get(
        "selected_model"
    )

    selected_family = model.get(
        "selected_family"
    )

    raw_crps = float(
        model[
            "raw_mean_date_crps"
        ]
    )

    selected_crps = float(
        model[
            "selected_mean_date_crps"
        ]
    )

    reduction = float(
        model[
            "selected_relative_crps_reduction_vs_raw"
        ]
    )

    selected_scale = continuous.get(
        "selected_scale"
    )

    selected_lambda = first_value(
        probability,
        [
            "selected_uniform_mixing_lambda",
            "selected_lambda",
            "mixing_lambda",
        ],
    )

    strict_lambda = first_value(
        probability,
        [
            "strict_winner_lambda",
            "strict_crps_winner_lambda",
            "strict_log_score_winner_lambda",
        ],
    )

    model_table = pd.DataFrame(
        [
            {
                "selected_model": selected_model,
                "selected_family": selected_family,
                "candidate_count": model.get(
                    "candidate_count"
                ),
                "development_dates": model.get(
                    "common_support_dates"
                ),
                "development_rows": model.get(
                    "common_support_rows"
                ),
                "raw_mean_date_crps": raw_crps,
                "selected_mean_date_crps": selected_crps,
                "relative_crps_reduction": reduction,
                "relative_crps_reduction_percent": (
                    100.0 * reduction
                ),
                "selection_rule": model.get(
                    "selection_rule"
                ),
            }
        ]
    )

    calibration_table = pd.DataFrame(
        [
            {
                "calibration_stage": (
                    "continuous dispersion"
                ),
                "selected_value": selected_scale,
                "strict_winner_value": continuous.get(
                    "strict_crps_winner_scale"
                ),
                "primary_score": continuous.get(
                    "primary_score"
                ),
                "selected_mean_score": continuous.get(
                    "selected_mean_date_crps"
                ),
                "selection_rule": continuous.get(
                    "selection_rule"
                ),
            },
            {
                "calibration_stage": (
                    "event probability mixing"
                ),
                "selected_value": selected_lambda,
                "strict_winner_value": strict_lambda,
                "primary_score": (
                    "settlement-date categorical log score"
                ),
                "selected_mean_score": first_value(
                    probability,
                    [
                        "selected_mean_date_log_score",
                        "selected_mean_log_score",
                    ],
                ),
                "selection_rule": first_value(
                    probability,
                    [
                        "selection_rule",
                        "selected_reason",
                    ],
                ),
            },
        ]
    )

    categorical_source = pd.read_csv(
        SOURCES[
            "categorical_evaluation"
        ],
        low_memory=False,
    )

    market_source = pd.read_csv(
        SOURCES[
            "market_comparison"
        ],
        low_memory=False,
    )

    trading_source = pd.read_csv(
        SOURCES[
            "trading_evaluation"
        ],
        low_memory=False,
    )

    uncertainty_main = pd.read_csv(
        SOURCES[
            "uncertainty_main"
        ],
        low_memory=False,
    )

    uncertainty_rule = pd.read_csv(
        SOURCES[
            "uncertainty_rule"
        ],
        low_memory=False,
    )

    claims = pd.read_csv(
        SOURCES[
            "claim_boundaries"
        ],
        low_memory=False,
    )

    categorical_table = select_columns(
        categorical_source,
        [
            r"chronology_block",
            r"dates",
            r"probability_books",
            r"decision_rules",
            r"zero_probability",
            r"mean_date.*log_score",
            r"standard_error.*log_score",
            r"mean_date.*brier",
            r"standard_error.*brier",
        ],
    )

    market_table = select_columns(
        market_source,
        [
            r"chronology_block",
            r"dates",
            r"probability_books",
            r"decision_rules",
            r"model.*log_score",
            r"market.*log_score",
            r"log_score.*difference",
            r"model.*brier",
            r"market.*brier",
            r"brier.*difference",
            r"win_share",
        ],
    )

    trading_table = select_columns(
        trading_source,
        [
            r"chronology_block",
            r"dates",
            r"strategy",
            r"decision_rule",
            r"threshold",
            r"cost",
            r"trade",
            r"net_payoff",
            r"return",
            r"win",
        ],
    )

    uncertainty_main.insert(
        0,
        "source_table",
        "main",
    )

    uncertainty_rule.insert(
        0,
        "source_table",
        "decision_rule",
    )

    uncertainty_table = pd.concat(
        [
            uncertainty_main,
            uncertainty_rule,
        ],
        ignore_index=True,
        sort=False,
    )

    output_files: list[Path] = []

    for frame, stem in [
        (
            model_table,
            "16_model_selection_table",
        ),
        (
            calibration_table,
            "16_calibration_table",
        ),
        (
            categorical_table,
            "16_categorical_evaluation_table",
        ),
        (
            market_table,
            "16_market_comparison_table",
        ),
        (
            trading_table,
            "16_trading_evaluation_table",
        ),
        (
            uncertainty_table,
            "16_uncertainty_table",
        ),
        (
            claims,
            "16_claim_boundary_table",
        ),
    ]:
        csv_path, tex_path = write_table(
            frame,
            stem,
        )

        output_files.extend(
            [
                csv_path,
                tex_path,
            ]
        )

    figures: list[Path] = []

    figures.append(
        create_model_figure(
            raw_crps,
            selected_crps,
            str(selected_model),
        )
    )

    market_figure = create_comparison_figure(
        market_source
    )

    if market_figure is not None:
        figures.append(
            market_figure
        )

    trading_figure = create_trading_figure(
        trading_source
    )

    if trading_figure is not None:
        figures.append(
            trading_figure
        )

    key_results = {
        "selected_model": selected_model,
        "selected_family": selected_family,
        "candidate_count": model.get(
            "candidate_count"
        ),
        "development_common_support_dates": model.get(
            "common_support_dates"
        ),
        "development_common_support_rows": model.get(
            "common_support_rows"
        ),
        "raw_mean_date_crps": raw_crps,
        "selected_mean_date_crps": selected_crps,
        "relative_crps_reduction": reduction,
        "relative_crps_reduction_percent": (
            100.0 * reduction
        ),
        "selected_continuous_scale": selected_scale,
        "selected_probability_mixing_lambda": selected_lambda,
        "strict_probability_mixing_lambda": strict_lambda,
        "release_commit": release.get(
            "audited_commit"
        ),
        "full_test_count_at_release": release.get(
            "full_test_count"
        ),
        "release_ready": release.get(
            "release_ready"
        ),
        "uncertainty_unit": release.get(
            "uncertainty_unit",
            "settlement_date",
        ),
    }

    key_results_path = (
        OUTPUT
        / "16_key_results.json"
    )

    key_results_path.write_text(
        json.dumps(
            key_results,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    output_files.append(
        key_results_path
    )

    report_md = f"""# Final Empirical Results Register

## Locked probabilistic model

The selected probabilistic model is `{selected_model}`, belonging to
the `{selected_family}` family. Selection was conducted using
date-grouped out-of-fold CRPS on the development period.

Mean date CRPS decreased from {raw_crps:.6f} for the raw deterministic
forecast to {selected_crps:.6f} for the selected model. This is a
relative reduction of {100.0 * reduction:.2f}%.

## Calibration

The locked continuous dispersion scale is {selected_scale}. The
locked uniform event-probability mixing parameter is {selected_lambda}.
Neither value was reselected using the May holdout or June external
evaluation block.

## Evaluation tables

The thesis-ready categorical evaluation table is:

`outputs/thesis/16_categorical_evaluation_table.csv`

The exact-common-support model and market comparison is:

`outputs/thesis/16_market_comparison_table.csv`

The locked reduced-form trading evaluation is:

`outputs/thesis/16_trading_evaluation_table.csv`

The settlement-date uncertainty results are:

`outputs/thesis/16_uncertainty_table.csv`

## Evidential limits

The evidence is finite-sample and block-specific. It does not establish
universal model superiority, population-level statistical significance,
market inefficiency or executable profitability. The implemented
forecast source is deterministic IFS with probabilistic post-processing;
the empirical release does not claim an implemented AIFS ENS, ECMWF ENS
or Earth-2 experiment.
"""

    report_md_path = (
        OUTPUT
        / "16_final_empirical_report.md"
    )

    report_md_path.write_text(
        report_md,
        encoding="utf-8",
    )

    output_files.append(
        report_md_path
    )

    report_tex = rf"""\subsection{{Final empirical evidence}}

The selected probabilistic specification is
\texttt{{{tex_escape(selected_model)}}}, from the
\texttt{{{tex_escape(selected_family)}}} family. Model selection used
date-grouped out-of-fold continuous ranked probability score on the
development period. Mean date CRPS decreased from
\({raw_crps:.6f}\) for the raw deterministic forecast to
\({selected_crps:.6f}\) for the selected model, corresponding to a
relative reduction of \({100.0 * reduction:.2f}\%\).

The selected continuous dispersion scale is
\({selected_scale}\), while the selected uniform probability-mixing
parameter is \({selected_lambda}\). These quantities were selected
before the May holdout and June external evaluation blocks were scored.

\paragraph{{Interpretation.}}
The results are finite-sample, block-specific comparisons. They do not
establish population-level significance, universal superiority, market
inefficiency or executable profitability.

\input{{outputs/thesis/16_model_selection_table.tex}}

\input{{outputs/thesis/16_calibration_table.tex}}

\input{{outputs/thesis/16_categorical_evaluation_table.tex}}

\input{{outputs/thesis/16_market_comparison_table.tex}}

\input{{outputs/thesis/16_trading_evaluation_table.tex}}
"""

    report_tex_path = (
        OUTPUT
        / "16_final_empirical_report.tex"
    )

    report_tex_path.write_text(
        report_tex,
        encoding="utf-8",
    )

    output_files.append(
        report_tex_path
    )

    inventory_rows = []

    for path in [
        *output_files,
        *figures,
    ]:
        inventory_rows.append(
            {
                "path": relative(
                    path
                ),
                "file_type": path.suffix.lstrip(
                    "."
                ),
                "bytes": path.stat().st_size,
                "sha256": sha256(
                    path
                ),
            }
        )

    inventory = pd.DataFrame(
        inventory_rows
    ).sort_values(
        "path"
    )

    inventory_path = (
        OUTPUT
        / "16_thesis_output_inventory.csv"
    )

    inventory.to_csv(
        inventory_path,
        index=False,
    )

    output_files.append(
        inventory_path
    )

    checks = pd.DataFrame(
        [
            {
                "check": "release_is_certified",
                "passed": (
                    release.get(
                        "status"
                    )
                    == "FINAL_EMPIRICAL_RELEASE_CERTIFIED"
                ),
            },
            {
                "check": "release_is_ready",
                "passed": bool_is_true(
                    release.get(
                        "release_ready"
                    )
                ),
            },
            {
                "check": "model_selection_remains_locked",
                "passed": bool(
                    model.get(
                        "selection_locked"
                    )
                ),
            },
            {
                "check": "continuous_calibration_remains_locked",
                "passed": bool(
                    continuous.get(
                        "calibration_locked"
                    )
                ),
            },
            {
                "check": "probability_calibration_remains_locked",
                "passed": (
                    str(
                        probability.get(
                            "status",
                            "",
                        )
                    ).upper()
                    == "PROBABILITY_CALIBRATION_LOCKED"
                ),
            },
            {
                "check": "no_model_reselection",
                "passed": not bool_is_true(
                    release.get(
                        "model_reselected",
                        False,
                    )
                ),
            },
            {
                "check": "no_calibration_reselection",
                "passed": not any(
                    [
                        bool_is_true(
                            release.get(
                                "continuous_calibration_reselected",
                                False,
                            )
                        ),
                        bool_is_true(
                            release.get(
                                "probability_calibration_reselected",
                                False,
                            )
                        ),
                    ]
                ),
            },
            {
                "check": "no_strategy_reselection",
                "passed": not bool_is_true(
                    release.get(
                        "trading_strategy_reselected",
                        False,
                    )
                ),
            },
            {
                "check": "all_tables_nonempty",
                "passed": all(
                    not frame.empty
                    for frame in [
                        model_table,
                        calibration_table,
                        categorical_table,
                        market_table,
                        trading_table,
                        uncertainty_table,
                        claims,
                    ]
                ),
            },
            {
                "check": "at_least_one_figure_created",
                "passed": len(
                    figures
                ) >= 1,
            },
        ]
    )

    checks_path = (
        OUTPUT
        / "16_thesis_evidence_integrity_checks.csv"
    )

    checks.to_csv(
        checks_path,
        index=False,
    )

    if not checks[
        "passed"
    ].astype(bool).all():
        raise RuntimeError(
            "Notebook 16 integrity checks failed:\n"
            + checks.loc[
                ~checks[
                    "passed"
                ].astype(bool)
            ].to_string(
                index=False
            )
        )

    previous_created = None

    if MANIFEST_PATH.exists():
        try:
            previous_created = load_json(
                MANIFEST_PATH
            ).get(
                "created_utc"
            )
        except Exception:
            previous_created = None

    manifest = {
        "status": (
            "THESIS_EVIDENCE_PACKAGE_COMPLETE"
        ),
        "created_utc": (
            previous_created
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "release_manifest": relative(
            SOURCES[
                "release_manifest"
            ]
        ),
        "release_commit": release.get(
            "audited_commit"
        ),
        "selected_model": selected_model,
        "selected_family": selected_family,
        "selected_continuous_scale": selected_scale,
        "selected_probability_mixing_lambda": selected_lambda,
        "model_reselected": False,
        "continuous_calibration_reselected": False,
        "probability_calibration_reselected": False,
        "trading_strategy_reselected": False,
        "table_count": 7,
        "figure_count": len(
            figures
        ),
        "output_file_count": len(
            inventory
        ),
        "all_integrity_checks_passed": True,
        "key_results_path": relative(
            key_results_path
        ),
        "report_markdown_path": relative(
            report_md_path
        ),
        "report_latex_path": relative(
            report_tex_path
        ),
        "inventory_path": relative(
            inventory_path
        ),
        "next_stage": (
            "integrate the locked evidence into the dissertation"
        ),
    }

    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 84)
    print("NOTEBOOK 16 THESIS EVIDENCE PACKAGE COMPLETE")
    print("=" * 84)
    print()
    print("Status:", manifest["status"])
    print("Selected model:", selected_model)
    print("Selected family:", selected_family)
    print("Raw mean date CRPS:", raw_crps)
    print("Selected mean date CRPS:", selected_crps)
    print(
        "Relative CRPS reduction:",
        f"{100.0 * reduction:.2f}%",
    )
    print("Continuous scale:", selected_scale)
    print("Probability mixing lambda:", selected_lambda)
    print("Thesis tables:", manifest["table_count"])
    print("Figures:", manifest["figure_count"])
    print("Output files:", manifest["output_file_count"])
    print()
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
