#!/usr/bin/env python3
"""Evaluate locked continuous predictive distributions."""

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
from scipy.stats import t


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


CONFIG_PATH = (
    ROOT
    / "config"
    / "continuous_evaluation_spec.yaml"
)

MODEL_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "04_model_selection_manifest.json"
)

CALIBRATION_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "05_continuous_calibration_manifest.json"
)

PREDICTION_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "06_locked_prediction_manifest.json"
)

CHRONOLOGY_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_chronological_design_panel.csv"
)

UNCALIBRATED_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "06_locked_uncalibrated_predictions.csv"
)

CALIBRATED_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "06_locked_calibrated_predictions.csv"
)

PREDICTION_OUTCOME_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "07_continuous_prediction_and_outcome_panel.csv"
)

SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "07_continuous_score_panel.csv"
)

DATE_SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "07_continuous_date_score_panel.csv"
)

BLOCK_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "07_continuous_block_summary.csv"
)

PAIRWISE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "07_continuous_pairwise_comparison.csv"
)

RULE_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "07_continuous_rule_summary.csv"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "07_continuous_integrity_checks.csv"
)

FINAL_BLOCK_PATH = (
    ROOT
    / "outputs"
    / "final_tables"
    / "07_continuous_block_summary.csv"
)

FINAL_PAIRWISE_PATH = (
    ROOT
    / "outputs"
    / "final_tables"
    / "07_continuous_pairwise_comparison.csv"
)

FINAL_RULE_PATH = (
    ROOT
    / "outputs"
    / "final_tables"
    / "07_continuous_rule_summary.csv"
)

CRPS_FIGURE_PNG = (
    ROOT
    / "outputs"
    / "final_figures"
    / "07_continuous_crps_by_block.png"
)

CRPS_FIGURE_PDF = (
    ROOT
    / "outputs"
    / "final_figures"
    / "07_continuous_crps_by_block.pdf"
)

COVERAGE_FIGURE_PNG = (
    ROOT
    / "outputs"
    / "final_figures"
    / "07_interval_coverage_by_block.png"
)

COVERAGE_FIGURE_PDF = (
    ROOT
    / "outputs"
    / "final_figures"
    / "07_interval_coverage_by_block.pdf"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "07_continuous_evaluation_manifest.json"
)


VARIANT_ORDER = [
    "raw_deterministic",
    "selected_uncalibrated",
    "selected_calibrated",
]

VARIANT_DISPLAY = {
    "raw_deterministic": "Raw deterministic",
    "selected_uncalibrated": "Selected uncalibrated",
    "selected_calibrated": "Selected calibrated",
}

BLOCK_ORDER = [
    "holdout",
    "external_test",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def validate_lineage(
    model_manifest: dict[str, Any],
    calibration_manifest: dict[str, Any],
    prediction_manifest: dict[str, Any],
) -> None:
    if not model_manifest[
        "selection_locked"
    ]:
        raise RuntimeError(
            "The probabilistic model is not locked."
        )

    if not calibration_manifest[
        "calibration_locked"
    ]:
        raise RuntimeError(
            "Continuous calibration is not locked."
        )

    if not prediction_manifest[
        "predictions_locked"
    ]:
        raise RuntimeError(
            "The holdout and external predictions are not locked."
        )

    selected_model = model_manifest[
        "selected_model"
    ]

    selected_family = model_manifest[
        "selected_family"
    ]

    selected_scale = float(
        calibration_manifest[
            "selected_scale"
        ]
    )

    if (
        calibration_manifest[
            "selected_model"
        ]
        != selected_model
    ):
        raise RuntimeError(
            "Model and calibration manifests disagree."
        )

    if (
        prediction_manifest[
            "selected_model"
        ]
        != selected_model
    ):
        raise RuntimeError(
            "Model and prediction manifests disagree."
        )

    if (
        prediction_manifest[
            "selected_family"
        ]
        != selected_family
    ):
        raise RuntimeError(
            "Family and prediction manifests disagree."
        )

    if not math.isclose(
        float(
            prediction_manifest[
                "selected_dispersion_scale"
            ]
        ),
        selected_scale,
        abs_tol=1.0e-12,
    ):
        raise RuntimeError(
            "Calibration and prediction manifests disagree."
        )

    forbidden_prior_actions = {
        "continuous_scores_calculated": False,
        "event_probabilities_calculated": False,
        "market_data_accessed": False,
        "trading_returns_calculated": False,
        "holdout_outcomes_used_for_fit": False,
        "external_test_outcomes_used_for_fit": False,
        "refit_after_holdout": False,
    }

    for field, required_value in forbidden_prior_actions.items():
        if (
            prediction_manifest[
                field
            ]
            is not required_value
        ):
            raise RuntimeError(
                f"Prediction manifest violates the evaluation boundary: "
                f"{field}={prediction_manifest[field]}."
            )


def load_outcomes() -> pd.DataFrame:
    chronology = pd.read_csv(
        CHRONOLOGY_PATH,
        usecols=[
            "target_date",
            "chronology_block",
            "hko_daily_max_c",
        ],
        low_memory=False,
    )

    chronology[
        "target_date"
    ] = pd.to_datetime(
        chronology[
            "target_date"
        ],
        errors="raise",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    chronology[
        "hko_daily_max_c"
    ] = pd.to_numeric(
        chronology[
            "hko_daily_max_c"
        ],
        errors="raise",
    )

    evaluation = chronology.loc[
        chronology[
            "chronology_block"
        ].isin(
            BLOCK_ORDER
        )
    ].copy()

    conflicts = (
        evaluation.groupby(
            "target_date"
        )[
            "hko_daily_max_c"
        ]
        .nunique(
            dropna=False
        )
    )

    conflicting_dates = conflicts.loc[
        conflicts.ne(1)
    ]

    if not conflicting_dates.empty:
        raise RuntimeError(
            "HKO outcomes are not unique within settlement date:\n"
            + conflicting_dates.to_string()
        )

    block_conflicts = (
        evaluation.groupby(
            "target_date"
        )[
            "chronology_block"
        ]
        .nunique(
            dropna=False
        )
    )

    if block_conflicts.ne(1).any():
        raise RuntimeError(
            "A settlement date belongs to more than one evaluation block."
        )

    outcomes = (
        evaluation[
            [
                "target_date",
                "chronology_block",
                "hko_daily_max_c",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            "target_date"
        )
        .reset_index(
            drop=True
        )
    )

    if len(outcomes) != 40:
        raise RuntimeError(
            f"Expected 40 realised evaluation dates; found {len(outcomes)}."
        )

    if outcomes[
        "hko_daily_max_c"
    ].isna().any():
        raise RuntimeError(
            "A realised evaluation outcome is missing."
        )

    holdout_dates = int(
        outcomes[
            "chronology_block"
        ].eq(
            "holdout"
        ).sum()
    )

    external_dates = int(
        outcomes[
            "chronology_block"
        ].eq(
            "external_test"
        ).sum()
    )

    if holdout_dates != 10:
        raise RuntimeError(
            f"Expected 10 holdout outcomes; found {holdout_dates}."
        )

    if external_dates != 30:
        raise RuntimeError(
            f"Expected 30 external outcomes; found {external_dates}."
        )

    return outcomes


def validate_prediction_pair(
    uncalibrated: pd.DataFrame,
    calibrated: pd.DataFrame,
) -> None:
    key_columns = [
        "row_id",
        "target_date",
        "decision_rule",
        "chronology_block",
    ]

    for name, frame in (
        (
            "uncalibrated",
            uncalibrated,
        ),
        (
            "calibrated",
            calibrated,
        ),
    ):
        if len(frame) != 159:
            raise RuntimeError(
                f"Expected 159 {name} rows; found {len(frame)}."
            )

        if frame[
            "row_id"
        ].duplicated().any():
            raise RuntimeError(
                f"The {name} prediction file duplicates row IDs."
            )

        if not frame[
            "chronology_block"
        ].isin(
            BLOCK_ORDER
        ).all():
            raise RuntimeError(
                f"The {name} prediction file contains an undeclared block."
            )

    left_keys = (
        uncalibrated[
            key_columns
        ]
        .sort_values(
            "row_id"
        )
        .reset_index(
            drop=True
        )
    )

    right_keys = (
        calibrated[
            key_columns
        ]
        .sort_values(
            "row_id"
        )
        .reset_index(
            drop=True
        )
    )

    if not left_keys.equals(
        right_keys
    ):
        raise RuntimeError(
            "Uncalibrated and calibrated prediction keys disagree."
        )

    shared_metadata = [
        "row_id",
        "forecast_daily_max_c",
        "forecast_issue_time_utc",
        "decision_time_utc",
        "unique_local_hours",
        "source_period",
        "selected_model",
        "selected_family",
        "dispersion_scale",
    ]

    left_metadata = (
        uncalibrated[
            shared_metadata
        ]
        .sort_values(
            "row_id"
        )
        .reset_index(
            drop=True
        )
    )

    right_metadata = (
        calibrated[
            shared_metadata
        ]
        .sort_values(
            "row_id"
        )
        .reset_index(
            drop=True
        )
    )

    if not left_metadata.equals(
        right_metadata
    ):
        raise RuntimeError(
            "Uncalibrated and calibrated prediction metadata disagree."
        )


def construct_variant_panel(
    uncalibrated: pd.DataFrame,
    calibrated: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> pd.DataFrame:
    q_columns = quantile_columns()

    for frame_name, frame in (
        (
            "uncalibrated",
            uncalibrated,
        ),
        (
            "calibrated",
            calibrated,
        ),
    ):
        missing = [
            column
            for column in q_columns
            if column not in frame.columns
        ]

        if missing:
            raise RuntimeError(
                f"The {frame_name} file is missing quantiles: "
                + ", ".join(
                    missing
                )
            )

        values = frame[
            q_columns
        ].to_numpy(
            dtype=float
        )

        if not np.isfinite(
            values
        ).all():
            raise RuntimeError(
                f"The {frame_name} quantiles contain non-finite values."
            )

        if not (
            np.diff(
                values,
                axis=1,
            )
            >= -1.0e-10
        ).all():
            raise RuntimeError(
                f"The {frame_name} quantiles are not monotone."
            )

    base_columns = [
        "row_id",
        "target_date",
        "decision_rule",
        "chronology_block",
        "forecast_daily_max_c",
        "selected_model",
        "selected_family",
        "dispersion_scale",
    ]

    raw = uncalibrated[
        base_columns
    ].copy()

    raw[
        "forecast_variant"
    ] = "raw_deterministic"

    raw[
        "forecast_variant_display"
    ] = VARIANT_DISPLAY[
        "raw_deterministic"
    ]

    raw_forecast = pd.to_numeric(
        raw[
            "forecast_daily_max_c"
        ],
        errors="raise",
    ).to_numpy(
        dtype=float
    )

    for column in q_columns:
        raw[column] = raw_forecast

    uncalibrated_variant = uncalibrated[
        base_columns
        + q_columns
    ].copy()

    uncalibrated_variant[
        "forecast_variant"
    ] = "selected_uncalibrated"

    uncalibrated_variant[
        "forecast_variant_display"
    ] = VARIANT_DISPLAY[
        "selected_uncalibrated"
    ]

    calibrated_variant = calibrated[
        base_columns
        + q_columns
    ].copy()

    calibrated_variant[
        "forecast_variant"
    ] = "selected_calibrated"

    calibrated_variant[
        "forecast_variant_display"
    ] = VARIANT_DISPLAY[
        "selected_calibrated"
    ]

    panel = pd.concat(
        [
            raw,
            uncalibrated_variant,
            calibrated_variant,
        ],
        ignore_index=True,
    )

    panel = panel.merge(
        outcomes[
            [
                "target_date",
                "hko_daily_max_c",
            ]
        ],
        on="target_date",
        how="left",
        validate="many_to_one",
    )

    if panel[
        "hko_daily_max_c"
    ].isna().any():
        missing_dates = sorted(
            panel.loc[
                panel[
                    "hko_daily_max_c"
                ].isna(),
                "target_date",
            ].unique()
        )

        raise RuntimeError(
            "Realised HKO outcomes are missing for: "
            + ", ".join(
                missing_dates
            )
        )

    if len(panel) != 477:
        raise RuntimeError(
            f"Expected 477 variant rows; found {len(panel)}."
        )

    expected_variants = set(
        VARIANT_ORDER
    )

    observed_variants = set(
        panel[
            "forecast_variant"
        ].unique()
    )

    if observed_variants != expected_variants:
        raise RuntimeError(
            "Forecast variant set is incomplete."
        )

    duplicate_keys = panel[
        [
            "row_id",
            "forecast_variant",
        ]
    ].duplicated()

    if duplicate_keys.any():
        raise RuntimeError(
            "The evaluation panel duplicates a row-variant key."
        )

    return (
        panel.sort_values(
            [
                "chronology_block",
                "target_date",
                "decision_rule",
                "forecast_variant",
            ]
        )
        .reset_index(
            drop=True
        )
    )


def calculate_scores(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    q_columns = quantile_columns()

    q = panel[
        q_columns
    ].to_numpy(
        dtype=float
    )

    y = pd.to_numeric(
        panel[
            "hko_daily_max_c"
        ],
        errors="raise",
    ).to_numpy(
        dtype=float
    )

    result = panel[
        [
            "row_id",
            "target_date",
            "decision_rule",
            "chronology_block",
            "forecast_variant",
            "forecast_variant_display",
            "selected_model",
            "selected_family",
            "dispersion_scale",
            "forecast_daily_max_c",
            "hko_daily_max_c",
        ]
    ].copy()

    result[
        "crps_99q"
    ] = approximate_crps(
        y,
        q,
    )

    result[
        "predictive_median_c"
    ] = q[
        :,
        49,
    ]

    result[
        "median_error_c"
    ] = (
        result[
            "predictive_median_c"
        ]
        - result[
            "hko_daily_max_c"
        ]
    )

    result[
        "median_absolute_error_c"
    ] = result[
        "median_error_c"
    ].abs()

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
            f"central_{label}_lower_c"
        ] = lower

        result[
            f"central_{label}_upper_c"
        ] = upper

        result[
            f"central_{label}_covered"
        ] = (
            (y >= lower)
            & (y <= upper)
        )

        result[
            f"central_{label}_width_c"
        ] = upper - lower

    if not np.isfinite(
        result[
            "crps_99q"
        ]
    ).all():
        raise RuntimeError(
            "A continuous score is non-finite."
        )

    if not result[
        "crps_99q"
    ].ge(0).all():
        raise RuntimeError(
            "A continuous score is negative."
        )

    raw = result.loc[
        result[
            "forecast_variant"
        ].eq(
            "raw_deterministic"
        )
    ].copy()

    raw_absolute_error = np.abs(
        raw[
            "hko_daily_max_c"
        ].to_numpy(
            dtype=float
        )
        - raw[
            "forecast_daily_max_c"
        ].to_numpy(
            dtype=float
        )
    )

    raw_crps = raw[
        "crps_99q"
    ].to_numpy(
        dtype=float
    )

    if not np.allclose(
        raw_crps,
        raw_absolute_error,
        atol=1.0e-10,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Raw point-mass CRPS does not equal absolute error."
        )

    return result


def create_date_scores(
    score_panel: pd.DataFrame,
) -> pd.DataFrame:
    date_scores = (
        score_panel.groupby(
            [
                "chronology_block",
                "forecast_variant",
                "forecast_variant_display",
                "target_date",
            ],
            as_index=False,
        )
        .agg(
            date_crps=(
                "crps_99q",
                "mean",
            ),
            date_median_mae_c=(
                "median_absolute_error_c",
                "mean",
            ),
            date_median_bias_c=(
                "median_error_c",
                "mean",
            ),
            date_50_coverage=(
                "central_50_covered",
                "mean",
            ),
            date_50_width_c=(
                "central_50_width_c",
                "mean",
            ),
            date_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            date_80_width_c=(
                "central_80_width_c",
                "mean",
            ),
            date_90_coverage=(
                "central_90_covered",
                "mean",
            ),
            date_90_width_c=(
                "central_90_width_c",
                "mean",
            ),
            date_rule_rows=(
                "row_id",
                "size",
            ),
        )
    )

    expected_date_counts = {
        "holdout": 10,
        "external_test": 30,
    }

    for block, expected_dates in expected_date_counts.items():
        observed = (
            date_scores.loc[
                date_scores[
                    "chronology_block"
                ].eq(
                    block
                )
            ]
            .groupby(
                "forecast_variant"
            )[
                "target_date"
            ]
            .nunique()
        )

        if not observed.eq(
            expected_dates
        ).all():
            raise RuntimeError(
                f"Unexpected date support in block {block}:\n"
                + observed.to_string()
            )

    return date_scores


def create_block_summary(
    date_scores: pd.DataFrame,
    score_panel: pd.DataFrame,
) -> pd.DataFrame:
    date_summary = (
        date_scores.groupby(
            [
                "chronology_block",
                "forecast_variant",
                "forecast_variant_display",
            ]
        )
        .agg(
            dates=(
                "target_date",
                "nunique",
            ),
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
            mean_date_median_mae_c=(
                "date_median_mae_c",
                "mean",
            ),
            mean_date_median_bias_c=(
                "date_median_bias_c",
                "mean",
            ),
        )
        .reset_index()
    )

    date_summary[
        "standard_error_date_crps"
    ] = (
        date_summary[
            "standard_deviation_date_crps"
        ]
        / np.sqrt(
            date_summary[
                "dates"
            ]
        )
    )

    row_summary = (
        score_panel.groupby(
            [
                "chronology_block",
                "forecast_variant",
                "forecast_variant_display",
            ]
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
            median_mae_c=(
                "median_absolute_error_c",
                "mean",
            ),
            median_bias_c=(
                "median_error_c",
                "mean",
            ),
            empirical_50_coverage=(
                "central_50_covered",
                "mean",
            ),
            mean_50_width_c=(
                "central_50_width_c",
                "mean",
            ),
            empirical_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            mean_80_width_c=(
                "central_80_width_c",
                "mean",
            ),
            empirical_90_coverage=(
                "central_90_covered",
                "mean",
            ),
            mean_90_width_c=(
                "central_90_width_c",
                "mean",
            ),
        )
        .reset_index()
    )

    summary = date_summary.merge(
        row_summary,
        on=[
            "chronology_block",
            "forecast_variant",
            "forecast_variant_display",
        ],
        how="left",
        validate="one_to_one",
    )

    raw_scores = (
        summary.loc[
            summary[
                "forecast_variant"
            ].eq(
                "raw_deterministic"
            ),
            [
                "chronology_block",
                "mean_date_crps",
            ],
        ]
        .rename(
            columns={
                "mean_date_crps": (
                    "raw_mean_date_crps"
                )
            }
        )
    )

    summary = summary.merge(
        raw_scores,
        on="chronology_block",
        how="left",
        validate="many_to_one",
    )

    summary[
        "relative_crps_reduction_vs_raw"
    ] = (
        1.0
        - summary[
            "mean_date_crps"
        ]
        / summary[
            "raw_mean_date_crps"
        ]
    )

    summary[
        "block_order"
    ] = summary[
        "chronology_block"
    ].map(
        {
            block: index
            for index, block in enumerate(
                BLOCK_ORDER
            )
        }
    )

    summary[
        "variant_order"
    ] = summary[
        "forecast_variant"
    ].map(
        {
            variant: index
            for index, variant in enumerate(
                VARIANT_ORDER
            )
        }
    )

    return (
        summary.sort_values(
            [
                "block_order",
                "variant_order",
            ]
        )
        .drop(
            columns=[
                "block_order",
                "variant_order",
            ]
        )
        .reset_index(
            drop=True
        )
    )


def create_pairwise_comparison(
    date_scores: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    comparisons = config[
        "paired_comparisons"
    ]

    rows = []

    for block in BLOCK_ORDER:
        block_scores = date_scores.loc[
            date_scores[
                "chronology_block"
            ].eq(
                block
            )
        ].pivot(
            index="target_date",
            columns="forecast_variant",
            values="date_crps",
        )

        for comparison in comparisons:
            left = str(
                comparison[
                    "left"
                ]
            )

            right = str(
                comparison[
                    "right"
                ]
            )

            paired = block_scores[
                [
                    left,
                    right,
                ]
            ].dropna()

            difference = (
                paired[
                    left
                ]
                - paired[
                    right
                ]
            )

            n_dates = len(
                difference
            )

            if n_dates < 2:
                raise RuntimeError(
                    "At least two paired dates are required."
                )

            mean_difference = float(
                difference.mean()
            )

            standard_deviation = float(
                difference.std(
                    ddof=1
                )
            )

            standard_error = float(
                standard_deviation
                / math.sqrt(
                    n_dates
                )
            )

            critical_value = float(
                t.ppf(
                    0.975,
                    df=n_dates - 1,
                )
            )

            lower = float(
                mean_difference
                - critical_value
                * standard_error
            )

            upper = float(
                mean_difference
                + critical_value
                * standard_error
            )

            left_better_share = float(
                (
                    difference < 0.0
                ).mean()
            )

            ties_share = float(
                np.isclose(
                    difference.to_numpy(
                        dtype=float
                    ),
                    0.0,
                    atol=1.0e-12,
                    rtol=0.0,
                ).mean()
            )

            rows.append(
                {
                    "chronology_block": block,
                    "left_variant": left,
                    "left_display": VARIANT_DISPLAY[
                        left
                    ],
                    "right_variant": right,
                    "right_display": VARIANT_DISPLAY[
                        right
                    ],
                    "difference_definition": (
                        "left_date_crps_minus_right_date_crps"
                    ),
                    "negative_difference_favours": (
                        "left"
                    ),
                    "paired_dates": n_dates,
                    "mean_paired_crps_difference": (
                        mean_difference
                    ),
                    "standard_deviation_paired_difference": (
                        standard_deviation
                    ),
                    "standard_error_paired_difference": (
                        standard_error
                    ),
                    "descriptive_95_interval_lower": (
                        lower
                    ),
                    "descriptive_95_interval_upper": (
                        upper
                    ),
                    "left_better_date_share": (
                        left_better_share
                    ),
                    "tie_date_share": (
                        ties_share
                    ),
                    "interval_excludes_zero": bool(
                        (lower > 0.0)
                        or (upper < 0.0)
                    ),
                    "formal_significance_claim_permitted": (
                        False
                    ),
                }
            )

    result = pd.DataFrame(
        rows
    )

    if len(result) != 6:
        raise RuntimeError(
            f"Expected six paired comparisons; found {len(result)}."
        )

    return result


def create_rule_summary(
    score_panel: pd.DataFrame,
) -> pd.DataFrame:
    result = (
        score_panel.groupby(
            [
                "chronology_block",
                "forecast_variant",
                "forecast_variant_display",
                "decision_rule",
            ]
        )
        .agg(
            rows=(
                "row_id",
                "size",
            ),
            dates=(
                "target_date",
                "nunique",
            ),
            mean_crps=(
                "crps_99q",
                "mean",
            ),
            median_mae_c=(
                "median_absolute_error_c",
                "mean",
            ),
            median_bias_c=(
                "median_error_c",
                "mean",
            ),
            empirical_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            mean_80_width_c=(
                "central_80_width_c",
                "mean",
            ),
        )
        .reset_index()
    )

    return result


def create_crps_figure(
    block_summary: pd.DataFrame,
) -> None:
    pivot = block_summary.pivot(
        index="chronology_block",
        columns="forecast_variant",
        values="mean_date_crps",
    ).reindex(
        BLOCK_ORDER
    )

    error = block_summary.pivot(
        index="chronology_block",
        columns="forecast_variant",
        values="standard_error_date_crps",
    ).reindex(
        BLOCK_ORDER
    )

    positions = np.arange(
        len(
            BLOCK_ORDER
        )
    )

    width = 0.24

    figure, axis = plt.subplots(
        figsize=(
            9,
            5.5,
        )
    )

    for index, variant in enumerate(
        VARIANT_ORDER
    ):
        axis.bar(
            positions
            + (
                index - 1
            )
            * width,
            pivot[
                variant
            ].to_numpy(),
            width,
            yerr=error[
                variant
            ].to_numpy(),
            capsize=3,
            label=VARIANT_DISPLAY[
                variant
            ],
        )

    axis.set_xticks(
        positions
    )

    axis.set_xticklabels(
        [
            "Holdout",
            "June external",
        ]
    )

    axis.set_ylabel(
        "Mean date-level CRPS"
    )

    axis.set_xlabel(
        "Evaluation block"
    )

    axis.set_title(
        "Locked continuous forecast performance"
    )

    axis.legend()

    figure.tight_layout()

    figure.savefig(
        CRPS_FIGURE_PNG,
        dpi=200,
        bbox_inches="tight",
    )

    figure.savefig(
        CRPS_FIGURE_PDF,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )


def create_coverage_figure(
    block_summary: pd.DataFrame,
) -> None:
    calibrated = (
        block_summary.loc[
            block_summary[
                "forecast_variant"
            ].eq(
                "selected_calibrated"
            )
        ]
        .set_index(
            "chronology_block"
        )
        .reindex(
            BLOCK_ORDER
        )
    )

    levels = np.array(
        [
            0.50,
            0.80,
            0.90,
        ]
    )

    figure, axis = plt.subplots(
        figsize=(
            8,
            5.5,
        )
    )

    for block, label in (
        (
            "holdout",
            "Holdout",
        ),
        (
            "external_test",
            "June external",
        ),
    ):
        observed = np.array(
            [
                calibrated.loc[
                    block,
                    "empirical_50_coverage",
                ],
                calibrated.loc[
                    block,
                    "empirical_80_coverage",
                ],
                calibrated.loc[
                    block,
                    "empirical_90_coverage",
                ],
            ],
            dtype=float,
        )

        axis.plot(
            levels,
            observed,
            marker="o",
            label=label,
        )

    axis.plot(
        levels,
        levels,
        linestyle="--",
        label="Nominal coverage",
    )

    axis.set_xlabel(
        "Nominal central interval coverage"
    )

    axis.set_ylabel(
        "Empirical coverage"
    )

    axis.set_title(
        "Coverage of the locked calibrated distribution"
    )

    axis.set_xlim(
        0.45,
        0.95,
    )

    axis.set_ylim(
        0.0,
        1.05,
    )

    axis.legend()

    figure.tight_layout()

    figure.savefig(
        COVERAGE_FIGURE_PNG,
        dpi=200,
        bbox_inches="tight",
    )

    figure.savefig(
        COVERAGE_FIGURE_PDF,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )


def main() -> None:
    config = yaml.safe_load(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    model_manifest = json.loads(
        MODEL_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    calibration_manifest = json.loads(
        CALIBRATION_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    prediction_manifest = json.loads(
        PREDICTION_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    validate_lineage(
        model_manifest,
        calibration_manifest,
        prediction_manifest,
    )

    uncalibrated = pd.read_csv(
        UNCALIBRATED_PATH,
        low_memory=False,
    )

    calibrated = pd.read_csv(
        CALIBRATED_PATH,
        low_memory=False,
    )

    for frame in (
        uncalibrated,
        calibrated,
    ):
        frame[
            "target_date"
        ] = pd.to_datetime(
            frame[
                "target_date"
            ],
            errors="raise",
        ).dt.strftime(
            "%Y-%m-%d"
        )

    validate_prediction_pair(
        uncalibrated,
        calibrated,
    )

    outcomes = load_outcomes()

    panel = construct_variant_panel(
        uncalibrated,
        calibrated,
        outcomes,
    )

    score_panel = calculate_scores(
        panel
    )

    date_scores = create_date_scores(
        score_panel
    )

    block_summary = create_block_summary(
        date_scores,
        score_panel,
    )

    pairwise = create_pairwise_comparison(
        date_scores,
        config,
    )

    rule_summary = create_rule_summary(
        score_panel
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

    selected_scale = float(
        calibration_manifest[
            "selected_scale"
        ]
    )

    checks = pd.DataFrame(
        [
            {
                "check": "model_selection_remained_locked",
                "passed": bool(
                    model_manifest[
                        "selection_locked"
                    ]
                ),
                "value": selected_model,
            },
            {
                "check": "calibration_remained_locked",
                "passed": bool(
                    calibration_manifest[
                        "calibration_locked"
                    ]
                ),
                "value": selected_scale,
            },
            {
                "check": "prediction_manifest_was_locked",
                "passed": bool(
                    prediction_manifest[
                        "predictions_locked"
                    ]
                ),
                "value": True,
            },
            {
                "check": "variant_rows_equal_477",
                "passed": len(panel) == 477,
                "value": len(panel),
            },
            {
                "check": "score_rows_equal_477",
                "passed": len(score_panel) == 477,
                "value": len(score_panel),
            },
            {
                "check": "evaluation_dates_equal_40",
                "passed": (
                    score_panel[
                        "target_date"
                    ].nunique()
                    == 40
                ),
                "value": (
                    score_panel[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "forecast_variants_equal_3",
                "passed": (
                    score_panel[
                        "forecast_variant"
                    ].nunique()
                    == 3
                ),
                "value": (
                    score_panel[
                        "forecast_variant"
                    ].nunique()
                ),
            },
            {
                "check": "all_outcomes_are_present",
                "passed": bool(
                    score_panel[
                        "hko_daily_max_c"
                    ].notna().all()
                ),
                "value": True,
            },
            {
                "check": "all_crps_values_are_finite",
                "passed": bool(
                    np.isfinite(
                        score_panel[
                            "crps_99q"
                        ]
                    ).all()
                ),
                "value": True,
            },
            {
                "check": "all_crps_values_are_non_negative",
                "passed": bool(
                    score_panel[
                        "crps_99q"
                    ].ge(0).all()
                ),
                "value": True,
            },
            {
                "check": "holdout_dates_equal_10",
                "passed": (
                    score_panel.loc[
                        score_panel[
                            "chronology_block"
                        ].eq(
                            "holdout"
                        ),
                        "target_date",
                    ].nunique()
                    == 10
                ),
                "value": (
                    score_panel.loc[
                        score_panel[
                            "chronology_block"
                        ].eq(
                            "holdout"
                        ),
                        "target_date",
                    ].nunique()
                ),
            },
            {
                "check": "external_dates_equal_30",
                "passed": (
                    score_panel.loc[
                        score_panel[
                            "chronology_block"
                        ].eq(
                            "external_test"
                        ),
                        "target_date",
                    ].nunique()
                    == 30
                ),
                "value": (
                    score_panel.loc[
                        score_panel[
                            "chronology_block"
                        ].eq(
                            "external_test"
                        ),
                        "target_date",
                    ].nunique()
                ),
            },
            {
                "check": "pairwise_comparisons_equal_6",
                "passed": len(pairwise) == 6,
                "value": len(pairwise),
            },
            {
                "check": "no_model_refit_occurred",
                "passed": True,
                "value": True,
            },
            {
                "check": "no_model_reselection_occurred",
                "passed": True,
                "value": True,
            },
            {
                "check": "no_calibration_reselection_occurred",
                "passed": True,
                "value": True,
            },
            {
                "check": "market_data_not_accessed",
                "passed": True,
                "value": True,
            },
            {
                "check": "trading_returns_not_calculated",
                "passed": True,
                "value": True,
            },
        ]
    )

    if not checks[
        "passed"
    ].all():
        failures = checks.loc[
            ~checks[
                "passed"
            ]
        ]

        raise RuntimeError(
            "Continuous evaluation integrity checks failed:\n"
            + failures.to_string(
                index=False
            )
        )

    for path in (
        PREDICTION_OUTCOME_PATH,
        SCORE_PATH,
        DATE_SCORE_PATH,
        BLOCK_SUMMARY_PATH,
        PAIRWISE_PATH,
        RULE_SUMMARY_PATH,
        INTEGRITY_PATH,
        FINAL_BLOCK_PATH,
        FINAL_PAIRWISE_PATH,
        FINAL_RULE_PATH,
        CRPS_FIGURE_PNG,
        CRPS_FIGURE_PDF,
        COVERAGE_FIGURE_PNG,
        COVERAGE_FIGURE_PDF,
        MANIFEST_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    panel.to_csv(
        PREDICTION_OUTCOME_PATH,
        index=False,
    )

    score_panel.to_csv(
        SCORE_PATH,
        index=False,
    )

    date_scores.to_csv(
        DATE_SCORE_PATH,
        index=False,
    )

    block_summary.to_csv(
        BLOCK_SUMMARY_PATH,
        index=False,
    )

    pairwise.to_csv(
        PAIRWISE_PATH,
        index=False,
    )

    rule_summary.to_csv(
        RULE_SUMMARY_PATH,
        index=False,
    )

    checks.to_csv(
        INTEGRITY_PATH,
        index=False,
    )

    block_summary.to_csv(
        FINAL_BLOCK_PATH,
        index=False,
    )

    pairwise.to_csv(
        FINAL_PAIRWISE_PATH,
        index=False,
    )

    rule_summary.to_csv(
        FINAL_RULE_PATH,
        index=False,
    )

    create_crps_figure(
        block_summary
    )

    create_coverage_figure(
        block_summary
    )

    calibrated_block_results = (
        block_summary.loc[
            block_summary[
                "forecast_variant"
            ].eq(
                "selected_calibrated"
            )
        ]
        .set_index(
            "chronology_block"
        )
    )

    uncalibrated_block_results = (
        block_summary.loc[
            block_summary[
                "forecast_variant"
            ].eq(
                "selected_uncalibrated"
            )
        ]
        .set_index(
            "chronology_block"
        )
    )

    raw_block_results = (
        block_summary.loc[
            block_summary[
                "forecast_variant"
            ].eq(
                "raw_deterministic"
            )
        ]
        .set_index(
            "chronology_block"
        )
    )

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "LOCKED_CONTINUOUS_EVALUATION_COMPLETE"
        ),
        "evaluation_locked": True,
        "selected_model": selected_model,
        "selected_family": selected_family,
        "selected_dispersion_scale": selected_scale,
        "forecast_variants": VARIANT_ORDER,
        "forecast_variant_count": 3,
        "score": (
            "99-quantile approximation to CRPS"
        ),
        "primary_uncertainty_unit": (
            "settlement_date"
        ),
        "evaluation_rows_per_variant": 159,
        "evaluation_dates": 40,
        "holdout_rows_per_variant": 40,
        "holdout_dates": 10,
        "external_test_rows_per_variant": 119,
        "external_test_dates": 30,
        "pairwise_comparison_count": 6,
        "holdout_results": {
            "raw_mean_date_crps": float(
                raw_block_results.loc[
                    "holdout",
                    "mean_date_crps",
                ]
            ),
            "uncalibrated_mean_date_crps": float(
                uncalibrated_block_results.loc[
                    "holdout",
                    "mean_date_crps",
                ]
            ),
            "calibrated_mean_date_crps": float(
                calibrated_block_results.loc[
                    "holdout",
                    "mean_date_crps",
                ]
            ),
            "calibrated_relative_reduction_vs_raw": float(
                calibrated_block_results.loc[
                    "holdout",
                    "relative_crps_reduction_vs_raw",
                ]
            ),
            "calibrated_median_mae_c": float(
                calibrated_block_results.loc[
                    "holdout",
                    "median_mae_c",
                ]
            ),
            "calibrated_median_bias_c": float(
                calibrated_block_results.loc[
                    "holdout",
                    "median_bias_c",
                ]
            ),
            "calibrated_80_coverage": float(
                calibrated_block_results.loc[
                    "holdout",
                    "empirical_80_coverage",
                ]
            ),
            "calibrated_80_width_c": float(
                calibrated_block_results.loc[
                    "holdout",
                    "mean_80_width_c",
                ]
            ),
        },
        "external_test_results": {
            "raw_mean_date_crps": float(
                raw_block_results.loc[
                    "external_test",
                    "mean_date_crps",
                ]
            ),
            "uncalibrated_mean_date_crps": float(
                uncalibrated_block_results.loc[
                    "external_test",
                    "mean_date_crps",
                ]
            ),
            "calibrated_mean_date_crps": float(
                calibrated_block_results.loc[
                    "external_test",
                    "mean_date_crps",
                ]
            ),
            "calibrated_relative_reduction_vs_raw": float(
                calibrated_block_results.loc[
                    "external_test",
                    "relative_crps_reduction_vs_raw",
                ]
            ),
            "calibrated_median_mae_c": float(
                calibrated_block_results.loc[
                    "external_test",
                    "median_mae_c",
                ]
            ),
            "calibrated_median_bias_c": float(
                calibrated_block_results.loc[
                    "external_test",
                    "median_bias_c",
                ]
            ),
            "calibrated_80_coverage": float(
                calibrated_block_results.loc[
                    "external_test",
                    "empirical_80_coverage",
                ]
            ),
            "calibrated_80_width_c": float(
                calibrated_block_results.loc[
                    "external_test",
                    "mean_80_width_c",
                ]
            ),
        },
        "model_refitted_during_evaluation": False,
        "model_reselected_during_evaluation": False,
        "calibration_reselected_during_evaluation": False,
        "event_probabilities_calculated": False,
        "market_data_accessed": False,
        "trading_returns_calculated": False,
        "formal_significance_claim_made": False,
        "paired_interval_interpretation": (
            "descriptive under settlement-date independence"
        ),
        "input_hashes": {
            str(
                MODEL_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                MODEL_MANIFEST_PATH
            ),
            str(
                CALIBRATION_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CALIBRATION_MANIFEST_PATH
            ),
            str(
                PREDICTION_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                PREDICTION_MANIFEST_PATH
            ),
            str(
                UNCALIBRATED_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                UNCALIBRATED_PATH
            ),
            str(
                CALIBRATED_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CALIBRATED_PATH
            ),
            str(
                CHRONOLOGY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CHRONOLOGY_PATH
            ),
            str(
                CONFIG_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CONFIG_PATH
            ),
        },
        "output_hashes": {
            str(
                SCORE_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                SCORE_PATH
            ),
            str(
                BLOCK_SUMMARY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                BLOCK_SUMMARY_PATH
            ),
            str(
                PAIRWISE_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                PAIRWISE_PATH
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
    print("=" * 92)
    print(" LOCKED CONTINUOUS EVALUATION COMPLETE")
    print("=" * 92)
    print()
    print("Selected model:", selected_model)
    print("Selected family:", selected_family)
    print("Locked dispersion scale:", selected_scale)
    print()
    print("Evaluation rows per variant:", 159)
    print("Evaluation dates:", 40)
    print("Holdout dates:", 10)
    print("External-test dates:", 30)
    print()
    print("Primary block summary:")
    print(
        block_summary[
            [
                "chronology_block",
                "forecast_variant",
                "mean_date_crps",
                "standard_error_date_crps",
                "relative_crps_reduction_vs_raw",
                "median_mae_c",
                "median_bias_c",
                "empirical_50_coverage",
                "empirical_80_coverage",
                "empirical_90_coverage",
                "mean_80_width_c",
            ]
        ].to_string(
            index=False
        )
    )
    print()
    print("Paired date-level comparisons:")
    print(
        pairwise[
            [
                "chronology_block",
                "left_variant",
                "right_variant",
                "paired_dates",
                "mean_paired_crps_difference",
                "descriptive_95_interval_lower",
                "descriptive_95_interval_upper",
                "left_better_date_share",
                "interval_excludes_zero",
            ]
        ].to_string(
            index=False
        )
    )
    print()
    print("Model refitted during evaluation:", False)
    print("Model reselected during evaluation:", False)
    print("Calibration reselected during evaluation:", False)
    print("Event probabilities calculated:", False)
    print("Market data accessed:", False)
    print("Trading returns calculated:", False)
    print("Formal significance claim made:", False)
    print()
    print(
        "Next stage: convert the locked calibrated temperature "
        "distributions into probabilities over the certified eleven-event "
        "partition, without using market prices."
    )


if __name__ == "__main__":
    main()
