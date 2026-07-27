#!/usr/bin/env python3
"""Select a median-preserving dispersion scale on development OOF data."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


ROOT = Path.cwd()
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(
        0,
        str(SRC),
    )

from weather_polymarket.probabilistic_models import (  # noqa: E402
    approximate_crps,
    quantile_columns,
)


MODEL_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "04_model_selection_manifest.json"
)

MODEL_PREDICTION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_oof_model_predictions.csv"
)

MODEL_FIT_LOG_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_model_fit_log.csv"
)

CALIBRATION_CONFIG_PATH = (
    ROOT
    / "config"
    / "continuous_calibration_spec.yaml"
)

CANDIDATE_PREDICTION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "05_calibration_candidate_predictions.csv"
)

SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "05_calibration_score_panel.csv"
)

DATE_SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "05_calibration_date_score_panel.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "05_calibration_candidate_summary.csv"
)

SELECTED_PREDICTION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "05_selected_oof_calibrated_predictions.csv"
)

FINAL_TABLE_PATH = (
    ROOT
    / "outputs"
    / "final_tables"
    / "05_calibration_candidate_summary.csv"
)

FIGURE_PNG_PATH = (
    ROOT
    / "outputs"
    / "final_figures"
    / "05_calibration_crps_by_scale.png"
)

FIGURE_PDF_PATH = (
    ROOT
    / "outputs"
    / "final_figures"
    / "05_calibration_crps_by_scale.pdf"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "05_continuous_calibration_manifest.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def as_boolean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "yes",
            }
        )
    )


def apply_dispersion_scale(
    quantiles: np.ndarray,
    scale: float,
) -> np.ndarray:
    values = np.asarray(
        quantiles,
        dtype=float,
    )

    if values.ndim != 2:
        raise ValueError(
            "Quantile predictions must be two-dimensional."
        )

    if not np.isfinite(values).all():
        raise ValueError(
            "Quantile predictions contain non-finite values."
        )

    if scale <= 0.0:
        raise ValueError(
            "The dispersion scale must be strictly positive."
        )

    median_index = 49

    median = values[
        :,
        median_index,
    ].reshape(
        -1,
        1,
    )

    calibrated = (
        median
        + float(scale)
        * (
            values - median
        )
    )

    calibrated = np.maximum.accumulate(
        calibrated,
        axis=1,
    )

    if not np.allclose(
        calibrated[
            :,
            median_index,
        ],
        values[
            :,
            median_index,
        ],
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Dispersion scaling changed the predictive median."
        )

    if not (
        np.diff(
            calibrated,
            axis=1,
        )
        >= -1.0e-10
    ).all():
        raise RuntimeError(
            "Dispersion scaling produced crossing quantiles."
        )

    return calibrated


def interval_diagnostics(
    outcomes: np.ndarray,
    quantiles: np.ndarray,
) -> dict[str, np.ndarray]:
    y = np.asarray(
        outcomes,
        dtype=float,
    )

    q = np.asarray(
        quantiles,
        dtype=float,
    )

    intervals = {
        "50": (
            24,
            74,
        ),
        "80": (
            9,
            89,
        ),
        "90": (
            4,
            94,
        ),
    }

    result: dict[
        str,
        np.ndarray,
    ] = {}

    for label, (
        lower_index,
        upper_index,
    ) in intervals.items():
        lower = q[
            :,
            lower_index,
        ]

        upper = q[
            :,
            upper_index,
        ]

        result[
            f"central_{label}_covered"
        ] = (
            (y >= lower)
            & (y <= upper)
        )

        result[
            f"central_{label}_width_c"
        ] = upper - lower

    result[
        "median_absolute_error_c"
    ] = np.abs(
        y
        - q[
            :,
            49,
        ]
    )

    return result


def construct_candidates(
    selected_predictions: pd.DataFrame,
    scales: list[float],
) -> pd.DataFrame:
    q_columns = quantile_columns()

    raw_quantiles = (
        selected_predictions[
            q_columns
        ].to_numpy(
            dtype=float
        )
    )

    outcomes = pd.to_numeric(
        selected_predictions[
            "hko_daily_max_c"
        ],
        errors="raise",
    ).to_numpy(
        dtype=float
    )

    frames = []

    for scale in scales:
        calibrated = apply_dispersion_scale(
            raw_quantiles,
            scale,
        )

        result = selected_predictions[
            [
                "row_id",
                "target_date",
                "decision_rule",
                "development_fold",
                "chronology_block",
                "candidate_model",
                "forecast_daily_max_c",
                "hko_daily_max_c",
            ]
        ].copy()

        result[
            "dispersion_scale"
        ] = float(scale)

        result[
            "is_identity_scale"
        ] = math.isclose(
            float(scale),
            1.0,
            abs_tol=1.0e-12,
        )

        for index, column in enumerate(
            q_columns
        ):
            result[column] = calibrated[
                :,
                index,
            ]

        result[
            "crps_99q"
        ] = approximate_crps(
            outcomes,
            calibrated,
        )

        diagnostics = interval_diagnostics(
            outcomes,
            calibrated,
        )

        for name, values in diagnostics.items():
            result[name] = values

        frames.append(result)

    return pd.concat(
        frames,
        ignore_index=True,
    )


def select_scale(
    candidate_predictions: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    date_scores = (
        candidate_predictions.groupby(
            [
                "dispersion_scale",
                "target_date",
            ],
            as_index=False,
        )
        .agg(
            date_crps=(
                "crps_99q",
                "mean",
            ),
            date_rows=(
                "row_id",
                "size",
            ),
            date_50_coverage=(
                "central_50_covered",
                "mean",
            ),
            date_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            date_90_coverage=(
                "central_90_covered",
                "mean",
            ),
        )
    )

    summary = (
        date_scores.groupby(
            "dispersion_scale"
        )
        .agg(
            mean_date_crps=(
                "date_crps",
                "mean",
            ),
            standard_deviation_date_crps=(
                "date_crps",
                "std",
            ),
            median_date_crps=(
                "date_crps",
                "median",
            ),
            dates=(
                "target_date",
                "nunique",
            ),
        )
        .reset_index()
    )

    summary[
        "standard_error_date_crps"
    ] = (
        summary[
            "standard_deviation_date_crps"
        ]
        / np.sqrt(
            summary["dates"]
        )
    )

    row_summary = (
        candidate_predictions.groupby(
            "dispersion_scale"
        )
        .agg(
            rows=(
                "row_id",
                "size",
            ),
            mean_row_crps=(
                "crps_99q",
                "mean",
            ),
            empirical_50_coverage=(
                "central_50_covered",
                "mean",
            ),
            empirical_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            empirical_90_coverage=(
                "central_90_covered",
                "mean",
            ),
            mean_50_width_c=(
                "central_50_width_c",
                "mean",
            ),
            mean_80_width_c=(
                "central_80_width_c",
                "mean",
            ),
            mean_90_width_c=(
                "central_90_width_c",
                "mean",
            ),
            mean_median_absolute_error_c=(
                "median_absolute_error_c",
                "mean",
            ),
        )
        .reset_index()
    )

    summary = summary.merge(
        row_summary,
        on="dispersion_scale",
        how="left",
        validate="one_to_one",
    )

    strict_row = summary.sort_values(
        [
            "mean_date_crps",
            "dispersion_scale",
        ]
    ).iloc[0]

    strict_scale = float(
        strict_row[
            "dispersion_scale"
        ]
    )

    pivot = date_scores.pivot(
        index="target_date",
        columns="dispersion_scale",
        values="date_crps",
    )

    paired_rows = []

    for scale in sorted(
        summary[
            "dispersion_scale"
        ].astype(float)
    ):
        difference = (
            pivot[scale]
            - pivot[strict_scale]
        ).dropna()

        mean_difference = float(
            difference.mean()
        )

        if len(difference) > 1:
            standard_error = float(
                difference.std(
                    ddof=1
                )
                / math.sqrt(
                    len(difference)
                )
            )
        else:
            standard_error = 0.0

        paired_rows.append(
            {
                "dispersion_scale": scale,
                "paired_difference_from_strict_winner": (
                    mean_difference
                ),
                "paired_difference_standard_error": (
                    standard_error
                ),
                "within_one_standard_error": bool(
                    mean_difference
                    <= standard_error
                    + 1.0e-12
                ),
            }
        )

    summary = summary.merge(
        pd.DataFrame(
            paired_rows
        ),
        on="dispersion_scale",
        how="left",
        validate="one_to_one",
    )

    summary[
        "distance_from_identity"
    ] = (
        summary[
            "dispersion_scale"
        ]
        - 1.0
    ).abs()

    selected_row = (
        summary.loc[
            summary[
                "within_one_standard_error"
            ]
        ]
        .sort_values(
            [
                "distance_from_identity",
                "mean_date_crps",
                "dispersion_scale",
            ]
        )
        .iloc[0]
    )

    selected_scale = float(
        selected_row[
            "dispersion_scale"
        ]
    )

    identity_score = float(
        summary.loc[
            np.isclose(
                summary[
                    "dispersion_scale"
                ],
                1.0,
            ),
            "mean_date_crps",
        ].iloc[0]
    )

    summary[
        "relative_crps_change_vs_identity"
    ] = (
        1.0
        - summary[
            "mean_date_crps"
        ]
        / identity_score
    )

    summary[
        "strict_crps_winner"
    ] = np.isclose(
        summary[
            "dispersion_scale"
        ],
        strict_scale,
    )

    summary[
        "selected_scale"
    ] = np.isclose(
        summary[
            "dispersion_scale"
        ],
        selected_scale,
    )

    summary = summary.sort_values(
        "dispersion_scale"
    ).reset_index(
        drop=True
    )

    selected_predictions = (
        candidate_predictions.loc[
            np.isclose(
                candidate_predictions[
                    "dispersion_scale"
                ],
                selected_scale,
            )
        ]
        .copy()
        .sort_values(
            [
                "target_date",
                "decision_rule",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    selection = {
        "strict_crps_winner_scale": (
            strict_scale
        ),
        "strict_crps_winner_mean_date_crps": float(
            strict_row[
                "mean_date_crps"
            ]
        ),
        "selected_scale": (
            selected_scale
        ),
        "selected_mean_date_crps": float(
            selected_row[
                "mean_date_crps"
            ]
        ),
        "identity_mean_date_crps": (
            identity_score
        ),
        "selected_relative_crps_change_vs_identity": float(
            1.0
            - selected_row[
                "mean_date_crps"
            ]
            / identity_score
        ),
        "calibration_applied": (
            not math.isclose(
                selected_scale,
                1.0,
                abs_tol=1.0e-12,
            )
        ),
        "selected_within_one_standard_error": bool(
            selected_row[
                "within_one_standard_error"
            ]
        ),
        "selected_distance_from_identity": float(
            selected_row[
                "distance_from_identity"
            ]
        ),
    }

    return (
        date_scores,
        summary,
        selected_predictions,
        selection,
    )


def create_figure(
    summary: pd.DataFrame,
) -> None:
    figure_data = summary.sort_values(
        "dispersion_scale"
    )

    figure, axis = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    axis.errorbar(
        figure_data[
            "dispersion_scale"
        ],
        figure_data[
            "mean_date_crps"
        ],
        yerr=figure_data[
            "standard_error_date_crps"
        ],
        marker="o",
        capsize=3,
    )

    selected = figure_data.loc[
        figure_data[
            "selected_scale"
        ].astype(bool)
    ]

    axis.scatter(
        selected[
            "dispersion_scale"
        ],
        selected[
            "mean_date_crps"
        ],
        marker="s",
        s=80,
        label="Selected scale",
    )

    axis.axvline(
        1.0,
        linestyle="--",
        label="Identity scale",
    )

    axis.set_xlabel(
        "Median-preserving dispersion scale"
    )

    axis.set_ylabel(
        "Mean date-level CRPS"
    )

    axis.set_title(
        "Development-only continuous distribution calibration"
    )

    axis.legend()

    figure.tight_layout()

    figure.savefig(
        FIGURE_PNG_PATH,
        dpi=200,
        bbox_inches="tight",
    )

    figure.savefig(
        FIGURE_PDF_PATH,
        bbox_inches="tight",
    )

    plt.close(figure)


def main() -> None:
    model_manifest = json.loads(
        MODEL_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    calibration_config = yaml.safe_load(
        CALIBRATION_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    selected_model = str(
        model_manifest[
            "selected_model"
        ]
    )

    selected_family = str(
        model_manifest[
            "selected_family"
        ]
    )

    if selected_family in {
        "raw",
        "mean_residual",
    }:
        raise RuntimeError(
            "The locked model is distributionally degenerate."
        )

    if model_manifest[
        "holdout_accessed"
    ]:
        raise RuntimeError(
            "Notebook 04 records prior holdout access."
        )

    if model_manifest[
        "external_test_accessed"
    ]:
        raise RuntimeError(
            "Notebook 04 records prior external-test access."
        )

    predictions = pd.read_csv(
        MODEL_PREDICTION_PATH,
        low_memory=False,
    )

    selected_predictions = (
        predictions.loc[
            predictions[
                "candidate_model"
            ].eq(
                selected_model
            )
        ]
        .copy()
        .sort_values(
            [
                "target_date",
                "decision_rule",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    if selected_predictions.empty:
        raise RuntimeError(
            "No OOF predictions exist for the locked selected model."
        )

    if not selected_predictions[
        "chronology_block"
    ].eq(
        "development_validation"
    ).all():
        raise RuntimeError(
            "A non-development observation entered calibration."
        )

    if selected_predictions[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "Selected OOF predictions duplicate a date-rule key."
        )

    q_columns = quantile_columns()

    missing_quantiles = [
        column
        for column in q_columns
        if column not in selected_predictions.columns
    ]

    if missing_quantiles:
        raise RuntimeError(
            "Selected predictions are missing quantiles: "
            + ", ".join(
                missing_quantiles
            )
        )

    raw_quantiles = selected_predictions[
        q_columns
    ].to_numpy(
        dtype=float
    )

    if not np.isfinite(
        raw_quantiles
    ).all():
        raise RuntimeError(
            "Selected OOF quantiles contain non-finite values."
        )

    if not (
        np.diff(
            raw_quantiles,
            axis=1,
        )
        >= -1.0e-10
    ).all():
        raise RuntimeError(
            "Selected OOF quantiles are not monotone."
        )

    positive_width_share = float(
        (
            raw_quantiles[
                :,
                89,
            ]
            - raw_quantiles[
                :,
                9,
            ]
            > 1.0e-10
        ).mean()
    )

    if positive_width_share < 0.99:
        raise RuntimeError(
            "The selected model does not provide a non-degenerate "
            "predictive distribution on almost all rows."
        )

    scales = [
        float(value)
        for value in calibration_config[
            "candidate_scales"
        ]
    ]

    if 1.0 not in scales:
        raise RuntimeError(
            "The identity scale must be included."
        )

    if len(scales) != len(set(scales)):
        raise RuntimeError(
            "Candidate calibration scales are duplicated."
        )

    candidate_predictions = construct_candidates(
        selected_predictions,
        scales,
    )

    (
        date_scores,
        summary,
        selected_calibrated,
        selection,
    ) = select_scale(
        candidate_predictions
    )

    q50_raw = (
        selected_predictions.set_index(
            "row_id"
        )[
            "q_50"
        ]
    )

    q50_calibrated = (
        selected_calibrated.set_index(
            "row_id"
        )[
            "q_50"
        ]
    )

    q50_calibrated = q50_calibrated.loc[
        q50_raw.index
    ]

    maximum_median_change = float(
        np.max(
            np.abs(
                q50_raw.to_numpy(
                    dtype=float
                )
                - q50_calibrated.to_numpy(
                    dtype=float
                )
            )
        )
    )

    if maximum_median_change > 1.0e-12:
        raise RuntimeError(
            "The selected calibration changed a predictive median."
        )

    fit_log = pd.read_csv(
        MODEL_FIT_LOG_PATH,
        low_memory=False,
    )

    selected_fit_log = fit_log.loc[
        fit_log[
            "candidate_model"
        ].eq(
            selected_model
        )
    ].copy()

    if "warning_count" in selected_fit_log.columns:
        selected_warning_count = int(
            pd.to_numeric(
                selected_fit_log[
                    "warning_count"
                ],
                errors="coerce",
            )
            .fillna(0)
            .sum()
        )
    else:
        selected_warning_count = 0

    selected_non_ok_fit_records = int(
        (
            ~selected_fit_log[
                "status"
            ].astype(str).eq(
                "OK"
            )
        ).sum()
    )

    if selected_non_ok_fit_records > 0:
        raise RuntimeError(
            "The locked selected model contains non-OK OOF fit records."
        )

    for path in (
        CANDIDATE_PREDICTION_PATH,
        SCORE_PATH,
        DATE_SCORE_PATH,
        SUMMARY_PATH,
        SELECTED_PREDICTION_PATH,
        FINAL_TABLE_PATH,
        FIGURE_PNG_PATH,
        FIGURE_PDF_PATH,
        MANIFEST_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    candidate_predictions.to_csv(
        CANDIDATE_PREDICTION_PATH,
        index=False,
    )

    score_columns = [
        "row_id",
        "target_date",
        "decision_rule",
        "development_fold",
        "chronology_block",
        "candidate_model",
        "dispersion_scale",
        "is_identity_scale",
        "crps_99q",
        "central_50_covered",
        "central_50_width_c",
        "central_80_covered",
        "central_80_width_c",
        "central_90_covered",
        "central_90_width_c",
        "median_absolute_error_c",
    ]

    candidate_predictions[
        score_columns
    ].to_csv(
        SCORE_PATH,
        index=False,
    )

    date_scores.to_csv(
        DATE_SCORE_PATH,
        index=False,
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
    )

    summary.to_csv(
        FINAL_TABLE_PATH,
        index=False,
    )

    selected_calibrated.to_csv(
        SELECTED_PREDICTION_PATH,
        index=False,
    )

    create_figure(summary)

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "DEVELOPMENT_CONTINUOUS_CALIBRATION_COMPLETE"
        ),
        "calibration_locked": True,
        "selected_model": (
            selected_model
        ),
        "selected_family": (
            selected_family
        ),
        "transformation": (
            "median_preserving_dispersion_scaling"
        ),
        "candidate_scales": scales,
        "candidate_scale_count": len(scales),
        "development_rows": int(
            selected_predictions.shape[0]
        ),
        "development_dates": int(
            selected_predictions[
                "target_date"
            ].nunique()
        ),
        "development_rules": int(
            selected_predictions[
                "decision_rule"
            ].nunique()
        ),
        "strict_crps_winner_scale": (
            selection[
                "strict_crps_winner_scale"
            ]
        ),
        "strict_crps_winner_mean_date_crps": (
            selection[
                "strict_crps_winner_mean_date_crps"
            ]
        ),
        "selected_scale": (
            selection[
                "selected_scale"
            ]
        ),
        "selected_mean_date_crps": (
            selection[
                "selected_mean_date_crps"
            ]
        ),
        "identity_mean_date_crps": (
            selection[
                "identity_mean_date_crps"
            ]
        ),
        "selected_relative_crps_change_vs_identity": (
            selection[
                "selected_relative_crps_change_vs_identity"
            ]
        ),
        "calibration_applied": (
            selection[
                "calibration_applied"
            ]
        ),
        "selected_within_one_standard_error": (
            selection[
                "selected_within_one_standard_error"
            ]
        ),
        "maximum_predictive_median_change_c": (
            maximum_median_change
        ),
        "positive_raw_80_interval_width_share": (
            positive_width_share
        ),
        "selected_model_fit_warning_count": (
            selected_warning_count
        ),
        "selected_model_non_ok_fit_records": (
            selected_non_ok_fit_records
        ),
        "primary_score": (
            "99-quantile date-grouped mean CRPS"
        ),
        "selection_rule": (
            "paired one-standard-error preference for scale closest to one"
        ),
        "coverage_used_for_selection": False,
        "interval_width_used_for_selection": False,
        "holdout_accessed": False,
        "external_test_accessed": False,
        "market_data_accessed": False,
        "event_probability_regularisation_applied": False,
        "input_hashes": {
            str(
                MODEL_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                MODEL_MANIFEST_PATH
            ),
            str(
                MODEL_PREDICTION_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                MODEL_PREDICTION_PATH
            ),
            str(
                CALIBRATION_CONFIG_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CALIBRATION_CONFIG_PATH
            ),
        },
        "output_hashes": {
            str(
                SUMMARY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                SUMMARY_PATH
            ),
            str(
                SELECTED_PREDICTION_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                SELECTED_PREDICTION_PATH
            ),
        },
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 84)
    print(" DEVELOPMENT CONTINUOUS CALIBRATION COMPLETE")
    print("=" * 84)
    print()
    print("Selected model:", selected_model)
    print("Selected family:", selected_family)
    print(
        "Development rows:",
        manifest[
            "development_rows"
        ],
    )
    print(
        "Development dates:",
        manifest[
            "development_dates"
        ],
    )
    print()
    print(
        summary[
            [
                "dispersion_scale",
                "mean_date_crps",
                "standard_error_date_crps",
                "empirical_50_coverage",
                "empirical_80_coverage",
                "empirical_90_coverage",
                "mean_80_width_c",
                "relative_crps_change_vs_identity",
                "within_one_standard_error",
                "strict_crps_winner",
                "selected_scale",
            ]
        ].to_string(
            index=False
        )
    )
    print()
    print(
        "Strict CRPS winner scale:",
        manifest[
            "strict_crps_winner_scale"
        ],
    )
    print(
        "Selected parsimonious scale:",
        manifest[
            "selected_scale"
        ],
    )
    print(
        "Calibration applied:",
        manifest[
            "calibration_applied"
        ],
    )
    print(
        "Identity mean date CRPS:",
        manifest[
            "identity_mean_date_crps"
        ],
    )
    print(
        "Selected mean date CRPS:",
        manifest[
            "selected_mean_date_crps"
        ],
    )
    print(
        "Selected change versus identity:",
        manifest[
            "selected_relative_crps_change_vs_identity"
        ],
    )
    print(
        "Maximum median change:",
        manifest[
            "maximum_predictive_median_change_c"
        ],
    )
    print(
        "Selected-model fit warnings:",
        manifest[
            "selected_model_fit_warning_count"
        ],
    )
    print()
    print(
        "Holdout accessed:",
        manifest[
            "holdout_accessed"
        ],
    )
    print(
        "External test accessed:",
        manifest[
            "external_test_accessed"
        ],
    )
    print(
        "Market data accessed:",
        manifest[
            "market_data_accessed"
        ],
    )
    print()
    print(
        "Next stage: fit the locked model on warm-up plus development "
        "data, apply the locked scale, and generate untouched holdout "
        "and June predictive distributions."
    )


if __name__ == "__main__":
    main()
