#!/usr/bin/env python3
"""Run chronological out-of-fold probabilistic model selection."""

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
    QUANTILE_LEVELS,
    approximate_crps,
    empirical_quantiles,
    pooled_catboost_quantiles,
    quantile_columns,
    rule_specific_catboost_quantiles,
    rule_specific_gp_quantiles,
)


PANEL_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_chronological_design_panel.csv"
)

CONFIG_PATH = (
    ROOT
    / "config"
    / "probabilistic_model_spec.yaml"
)

PREDICTION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_oof_model_predictions.csv"
)

SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_oof_score_panel.csv"
)

DATE_SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_date_level_score_panel.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_candidate_score_summary.csv"
)

FOLD_SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_candidate_score_by_fold.csv"
)

RULE_SCORE_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_candidate_score_by_rule.csv"
)

FIT_LOG_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_model_fit_log.csv"
)

COMMON_SUPPORT_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "04_common_support_panel.csv"
)

FINAL_TABLE_PATH = (
    ROOT
    / "outputs"
    / "final_tables"
    / "04_candidate_score_summary.csv"
)

FIGURE_PNG_PATH = (
    ROOT
    / "outputs"
    / "final_figures"
    / "04_oof_crps_by_model.png"
)

FIGURE_PDF_PATH = (
    ROOT
    / "outputs"
    / "final_figures"
    / "04_oof_crps_by_model.pdf"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "04_model_selection_manifest.json"
)


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def prediction_frame(
    validation: pd.DataFrame,
    candidate: str,
    quantile_values: np.ndarray,
    fold: int,
) -> pd.DataFrame:
    values = np.asarray(
        quantile_values,
        dtype=float,
    )

    if values.shape != (
        len(validation),
        len(
            QUANTILE_LEVELS
        ),
    ):
        raise ValueError(
            f"Unexpected prediction shape for {candidate}: "
            f"{values.shape}"
        )

    result = validation[
        [
            "target_date",
            "decision_rule",
            "forecast_daily_max_c",
            "hko_daily_max_c",
            "chronology_block",
        ]
    ].copy()

    result[
        "development_fold"
    ] = int(
        fold
    )

    result[
        "row_id"
    ] = (
        result[
            "target_date"
        ].astype(str)
        + "|"
        + result[
            "decision_rule"
        ].astype(str)
    )

    result[
        "candidate_model"
    ] = candidate

    result[
        "available"
    ] = np.isfinite(
        values
    ).all(
        axis=1
    )

    for index, column in enumerate(
        quantile_columns()
    ):
        result[
            column
        ] = values[
            :,
            index,
        ]

    return result.loc[
        result[
            "available"
        ]
    ].copy()


def base_fit_log(
    candidate: str,
    fold: int,
    training: pd.DataFrame,
    validation: pd.DataFrame,
) -> dict[str, Any]:
    return {
        "candidate_model": candidate,
        "fold": int(fold),
        "scope": "pooled",
        "training_rows": len(training),
        "training_dates": int(
            training[
                "target_date"
            ].nunique()
        ),
        "training_start": (
            training[
                "target_date"
            ].min()
        ),
        "training_end": (
            training[
                "target_date"
            ].max()
        ),
        "validation_rows": len(
            validation
        ),
        "validation_dates": int(
            validation[
                "target_date"
            ].nunique()
        ),
        "validation_start": (
            validation[
                "target_date"
            ].min()
        ),
        "validation_end": (
            validation[
                "target_date"
            ].max()
        ),
        "status": "OK",
        "warning_count": 0,
        "learned_kernel": "",
        "message": "",
    }


def attach_complex_log_fields(
    log: dict[str, Any],
    candidate: str,
    fold: int,
    training: pd.DataFrame,
    validation: pd.DataFrame,
) -> dict[str, Any]:
    result = base_fit_log(
        candidate,
        fold,
        training,
        validation,
    )

    result.update(
        log
    )

    result[
        "candidate_model"
    ] = candidate

    result[
        "fold"
    ] = int(
        fold
    )

    return result


def build_predictions(
    panel: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    random_seed = int(
        config[
            "random_seed"
        ]
    )

    minimum_rows = int(
        config[
            "validation"
        ][
            "minimum_rule_training_rows"
        ]
    )

    development = panel.loc[
        panel[
            "chronology_block"
        ].eq(
            "development_validation"
        )
    ].copy()

    folds = sorted(
        development[
            "development_fold"
        ]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    if folds != [
        1,
        2,
        3,
        4,
    ]:
        raise RuntimeError(
            f"Expected folds 1–4; found {folds}."
        )

    prediction_frames = []
    fit_logs = []

    for fold in folds:
        validation = (
            development.loc[
                development[
                    "development_fold"
                ].astype(int).eq(
                    fold
                )
            ]
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

        validation_start = (
            validation[
                "target_date"
            ].min()
        )

        training = (
            panel.loc[
                panel[
                    "chronology_block"
                ].isin(
                    [
                        "warmup_training",
                        "development_validation",
                    ]
                )
                & panel[
                    "target_date"
                ].lt(
                    validation_start
                )
            ]
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

        if training.empty:
            raise RuntimeError(
                f"Fold {fold} has no training rows."
            )

        if not (
            training[
                "target_date"
            ].max()
            < validation[
                "target_date"
            ].min()
        ):
            raise RuntimeError(
                f"Fold {fold} violates chronology."
            )

        if not validation[
            "chronology_block"
        ].eq(
            "development_validation"
        ).all():
            raise RuntimeError(
                "Non-development rows entered validation."
            )

        forecast = pd.to_numeric(
            validation[
                "forecast_daily_max_c"
            ],
            errors="raise",
        ).to_numpy(
            dtype=float
        )

        residual = pd.to_numeric(
            training[
                "residual_c"
            ],
            errors="raise",
        ).to_numpy(
            dtype=float
        )

        # 1. Raw deterministic benchmark.
        raw_quantiles = np.repeat(
            forecast.reshape(
                -1,
                1,
            ),
            len(
                QUANTILE_LEVELS
            ),
            axis=1,
        )

        prediction_frames.append(
            prediction_frame(
                validation,
                "raw_deterministic",
                raw_quantiles,
                fold,
            )
        )

        fit_logs.append(
            base_fit_log(
                "raw_deterministic",
                fold,
                training,
                validation,
            )
        )

        # 2. Pooled mean residual correction.
        pooled_mean = float(
            np.mean(
                residual
            )
        )

        pooled_mean_quantiles = (
            np.repeat(
                (
                    forecast
                    + pooled_mean
                ).reshape(
                    -1,
                    1,
                ),
                len(
                    QUANTILE_LEVELS
                ),
                axis=1,
            )
        )

        prediction_frames.append(
            prediction_frame(
                validation,
                "pooled_mean_residual",
                pooled_mean_quantiles,
                fold,
            )
        )

        pooled_mean_log = base_fit_log(
            "pooled_mean_residual",
            fold,
            training,
            validation,
        )

        pooled_mean_log[
            "message"
        ] = (
            f"mean_residual={pooled_mean:.10f}"
        )

        fit_logs.append(
            pooled_mean_log
        )

        # 3. Rule-specific mean residual correction.
        rule_mean_quantiles = np.full(
            (
                len(validation),
                len(
                    QUANTILE_LEVELS
                ),
            ),
            np.nan,
            dtype=float,
        )

        for rule in sorted(
            validation[
                "decision_rule"
            ].unique()
        ):
            validation_mask = (
                validation[
                    "decision_rule"
                ].eq(
                    rule
                )
            )

            positions = np.flatnonzero(
                validation_mask.to_numpy()
            )

            training_rule = (
                training.loc[
                    training[
                        "decision_rule"
                    ].eq(
                        rule
                    )
                ]
            )

            log = base_fit_log(
                "rule_mean_residual",
                fold,
                training,
                validation,
            )

            log[
                "scope"
            ] = rule

            log[
                "training_rows"
            ] = len(
                training_rule
            )

            log[
                "validation_rows"
            ] = len(
                positions
            )

            if len(
                training_rule
            ) < minimum_rows:
                log[
                    "status"
                ] = (
                    "INSUFFICIENT_RULE_TRAINING_ROWS"
                )

                log[
                    "message"
                ] = (
                    f"Required {minimum_rows}; "
                    f"found {len(training_rule)}."
                )

                fit_logs.append(
                    log
                )

                continue

            mean_residual = float(
                training_rule[
                    "residual_c"
                ].mean()
            )

            values = (
                forecast[
                    positions
                ]
                + mean_residual
            )

            rule_mean_quantiles[
                positions,
                :,
            ] = np.repeat(
                values.reshape(
                    -1,
                    1,
                ),
                len(
                    QUANTILE_LEVELS
                ),
                axis=1,
            )

            log[
                "message"
            ] = (
                f"mean_residual={mean_residual:.10f}"
            )

            fit_logs.append(
                log
            )

        prediction_frames.append(
            prediction_frame(
                validation,
                "rule_mean_residual",
                rule_mean_quantiles,
                fold,
            )
        )

        # 4. Pooled empirical residual distribution.
        pooled_residual_quantiles = (
            empirical_quantiles(
                residual
            )
        )

        pooled_empirical = (
            forecast.reshape(
                -1,
                1,
            )
            + pooled_residual_quantiles.reshape(
                1,
                -1,
            )
        )

        prediction_frames.append(
            prediction_frame(
                validation,
                "pooled_empirical_residual",
                pooled_empirical,
                fold,
            )
        )

        fit_logs.append(
            base_fit_log(
                "pooled_empirical_residual",
                fold,
                training,
                validation,
            )
        )

        # 5. Rule-specific empirical residual distribution.
        rule_empirical = np.full(
            (
                len(validation),
                len(
                    QUANTILE_LEVELS
                ),
            ),
            np.nan,
            dtype=float,
        )

        for rule in sorted(
            validation[
                "decision_rule"
            ].unique()
        ):
            validation_mask = (
                validation[
                    "decision_rule"
                ].eq(
                    rule
                )
            )

            positions = np.flatnonzero(
                validation_mask.to_numpy()
            )

            training_rule = (
                training.loc[
                    training[
                        "decision_rule"
                    ].eq(
                        rule
                    )
                ]
            )

            log = base_fit_log(
                "rule_empirical_residual",
                fold,
                training,
                validation,
            )

            log[
                "scope"
            ] = rule

            log[
                "training_rows"
            ] = len(
                training_rule
            )

            log[
                "validation_rows"
            ] = len(
                positions
            )

            if len(
                training_rule
            ) < minimum_rows:
                log[
                    "status"
                ] = (
                    "INSUFFICIENT_RULE_TRAINING_ROWS"
                )

                log[
                    "message"
                ] = (
                    f"Required {minimum_rows}; "
                    f"found {len(training_rule)}."
                )

                fit_logs.append(
                    log
                )

                continue

            residual_quantiles = (
                empirical_quantiles(
                    training_rule[
                        "residual_c"
                    ].to_numpy(
                        dtype=float
                    )
                )
            )

            rule_empirical[
                positions,
                :,
            ] = (
                forecast[
                    positions
                ].reshape(
                    -1,
                    1,
                )
                + residual_quantiles.reshape(
                    1,
                    -1,
                )
            )

            fit_logs.append(
                log
            )

        prediction_frames.append(
            prediction_frame(
                validation,
                "rule_empirical_residual",
                rule_empirical,
                fold,
            )
        )

        # 6. Rule-specific GP with RBF covariance.
        gp_rbf, gp_rbf_logs = (
            rule_specific_gp_quantiles(
                training=training,
                validation=validation,
                covariance="rbf",
                minimum_rows=minimum_rows,
                random_seed=random_seed,
            )
        )

        prediction_frames.append(
            prediction_frame(
                validation,
                "rule_gp_rbf",
                gp_rbf,
                fold,
            )
        )

        fit_logs.extend(
            [
                attach_complex_log_fields(
                    log,
                    "rule_gp_rbf",
                    fold,
                    training,
                    validation,
                )
                for log in gp_rbf_logs
            ]
        )

        # 7. Rule-specific GP with Matern 3/2 covariance.
        gp_matern, gp_matern_logs = (
            rule_specific_gp_quantiles(
                training=training,
                validation=validation,
                covariance="matern32",
                minimum_rows=minimum_rows,
                random_seed=random_seed,
            )
        )

        prediction_frames.append(
            prediction_frame(
                validation,
                "rule_gp_matern32",
                gp_matern,
                fold,
            )
        )

        fit_logs.extend(
            [
                attach_complex_log_fields(
                    log,
                    "rule_gp_matern32",
                    fold,
                    training,
                    validation,
                )
                for log in gp_matern_logs
            ]
        )

        # 8. Pooled CatBoost quantile regression.
        pooled_catboost, pooled_catboost_log = (
            pooled_catboost_quantiles(
                training=training,
                validation=validation,
                random_seed=random_seed,
            )
        )

        prediction_frames.append(
            prediction_frame(
                validation,
                "pooled_catboost_quantile",
                pooled_catboost,
                fold,
            )
        )

        fit_logs.append(
            attach_complex_log_fields(
                pooled_catboost_log,
                "pooled_catboost_quantile",
                fold,
                training,
                validation,
            )
        )

        # 9. Rule-specific CatBoost quantile regression.
        rule_catboost, rule_catboost_logs = (
            rule_specific_catboost_quantiles(
                training=training,
                validation=validation,
                minimum_rows=minimum_rows,
                random_seed=random_seed,
            )
        )

        prediction_frames.append(
            prediction_frame(
                validation,
                "rule_catboost_quantile",
                rule_catboost,
                fold,
            )
        )

        fit_logs.extend(
            [
                attach_complex_log_fields(
                    log,
                    "rule_catboost_quantile",
                    fold,
                    training,
                    validation,
                )
                for log in rule_catboost_logs
            ]
        )

    predictions = pd.concat(
        prediction_frames,
        ignore_index=True,
    )

    fit_log = pd.DataFrame(
        fit_logs
    )

    return (
        predictions,
        fit_log,
    )


def score_predictions(
    predictions: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    candidate_spec = (
        config[
            "candidates"
        ]
    )

    candidate_names = [
        candidate["name"]
        for candidate in candidate_spec
    ]

    expected = set(
        candidate_names
    )

    observed = set(
        predictions[
            "candidate_model"
        ].unique()
    )

    if observed != expected:
        raise RuntimeError(
            "Candidate output set does not match the declared specification. "
            f"Expected {sorted(expected)}; found {sorted(observed)}."
        )

    support_sets = {
        candidate: set(
            predictions.loc[
                predictions[
                    "candidate_model"
                ].eq(
                    candidate
                ),
                "row_id",
            ]
        )
        for candidate in candidate_names
    }

    common_support = set.intersection(
        *support_sets.values()
    )

    common_predictions = (
        predictions.loc[
            predictions[
                "row_id"
            ].isin(
                common_support
            )
        ]
        .copy()
        .sort_values(
            [
                "candidate_model",
                "target_date",
                "decision_rule",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    common_rows = len(
        common_support
    )

    common_dates = int(
        common_predictions[
            "target_date"
        ].nunique()
    )

    minimum_rows = int(
        config[
            "validation"
        ][
            "minimum_common_support_rows"
        ]
    )

    minimum_dates = int(
        config[
            "validation"
        ][
            "minimum_common_support_dates"
        ]
    )

    if common_rows < minimum_rows:
        raise RuntimeError(
            f"Common support has only {common_rows} rows; "
            f"at least {minimum_rows} are required."
        )

    if common_dates < minimum_dates:
        raise RuntimeError(
            f"Common support has only {common_dates} dates; "
            f"at least {minimum_dates} are required."
        )

    if not common_predictions[
        "chronology_block"
    ].eq(
        "development_validation"
    ).all():
        raise RuntimeError(
            "A non-development row entered model scoring."
        )

    q_columns = (
        quantile_columns()
    )

    quantile_matrix = (
        common_predictions[
            q_columns
        ].to_numpy(
            dtype=float
        )
    )

    if not np.isfinite(
        quantile_matrix
    ).all():
        raise RuntimeError(
            "A common-support quantile prediction is non-finite."
        )

    if not (
        np.diff(
            quantile_matrix,
            axis=1,
        )
        >= -1.0e-10
    ).all():
        raise RuntimeError(
            "A candidate produced crossing quantiles."
        )

    outcomes = pd.to_numeric(
        common_predictions[
            "hko_daily_max_c"
        ],
        errors="raise",
    ).to_numpy(
        dtype=float
    )

    common_predictions[
        "crps_99q"
    ] = approximate_crps(
        outcomes,
        quantile_matrix,
    )

    q10 = (
        common_predictions[
            "q_10"
        ].to_numpy(
            dtype=float
        )
    )

    q50 = (
        common_predictions[
            "q_50"
        ].to_numpy(
            dtype=float
        )
    )

    q90 = (
        common_predictions[
            "q_90"
        ].to_numpy(
            dtype=float
        )
    )

    common_predictions[
        "central_80_covered"
    ] = (
        (
            outcomes >= q10
        )
        & (
            outcomes <= q90
        )
    )

    common_predictions[
        "central_80_width_c"
    ] = q90 - q10

    common_predictions[
        "median_absolute_error_c"
    ] = np.abs(
        outcomes - q50
    )

    score_panel = common_predictions[
        [
            "row_id",
            "target_date",
            "decision_rule",
            "development_fold",
            "chronology_block",
            "candidate_model",
            "forecast_daily_max_c",
            "hko_daily_max_c",
            "crps_99q",
            "central_80_covered",
            "central_80_width_c",
            "median_absolute_error_c",
        ]
    ].copy()

    date_scores = (
        score_panel.groupby(
            [
                "candidate_model",
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
            date_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            date_80_width_c=(
                "central_80_width_c",
                "mean",
            ),
        )
    )

    available_counts = (
        predictions.groupby(
            "candidate_model"
        )
        .agg(
            available_oof_rows=(
                "row_id",
                "nunique",
            ),
            available_oof_dates=(
                "target_date",
                "nunique",
            ),
        )
        .reset_index()
    )

    summary = (
        date_scores.groupby(
            "candidate_model"
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
            common_support_dates=(
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
            summary[
                "common_support_dates"
            ]
        )
    )

    row_summary = (
        score_panel.groupby(
            "candidate_model"
        )
        .agg(
            mean_row_crps=(
                "crps_99q",
                "mean",
            ),
            common_support_rows=(
                "row_id",
                "size",
            ),
            empirical_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            mean_80_interval_width_c=(
                "central_80_width_c",
                "mean",
            ),
            mean_median_absolute_error_c=(
                "median_absolute_error_c",
                "mean",
            ),
        )
        .reset_index()
    )

    summary = (
        summary.merge(
            row_summary,
            on="candidate_model",
            how="left",
            validate="one_to_one",
        )
        .merge(
            available_counts,
            on="candidate_model",
            how="left",
            validate="one_to_one",
        )
    )

    metadata = pd.DataFrame(
        [
            {
                "candidate_model": (
                    candidate["name"]
                ),
                "family": (
                    candidate["family"]
                ),
                "complexity_rank": int(
                    candidate[
                        "complexity_rank"
                    ]
                ),
                "display_name": (
                    candidate[
                        "display_name"
                    ]
                ),
                "candidate_order": (
                    index
                ),
            }
            for index, candidate in enumerate(
                candidate_spec
            )
        ]
    )

    summary = summary.merge(
        metadata,
        on="candidate_model",
        how="left",
        validate="one_to_one",
    )

    strict_winner = str(
        summary.sort_values(
            [
                "mean_date_crps",
                "complexity_rank",
                "candidate_order",
            ]
        ).iloc[0][
            "candidate_model"
        ]
    )

    date_pivot = date_scores.pivot(
        index="target_date",
        columns="candidate_model",
        values="date_crps",
    )

    paired_rows = []

    for candidate in candidate_names:
        difference = (
            date_pivot[
                candidate
            ]
            - date_pivot[
                strict_winner
            ]
        ).dropna()

        mean_difference = float(
            difference.mean()
        )

        if len(
            difference
        ) > 1:
            standard_error = float(
                difference.std(
                    ddof=1
                )
                / math.sqrt(
                    len(
                        difference
                    )
                )
            )
        else:
            standard_error = 0.0

        within_one_standard_error = bool(
            mean_difference
            <= (
                standard_error
                + 1.0e-12
            )
        )

        paired_rows.append(
            {
                "candidate_model": (
                    candidate
                ),
                "paired_difference_from_strict_winner": (
                    mean_difference
                ),
                "paired_difference_standard_error": (
                    standard_error
                ),
                "within_one_standard_error": (
                    within_one_standard_error
                ),
            }
        )

    summary = summary.merge(
        pd.DataFrame(
            paired_rows
        ),
        on="candidate_model",
        how="left",
        validate="one_to_one",
    )

    selected_row = (
        summary.loc[
            summary[
                "within_one_standard_error"
            ]
        ]
        .sort_values(
            [
                "complexity_rank",
                "candidate_order",
                "mean_date_crps",
            ]
        )
        .iloc[0]
    )

    selected_model = str(
        selected_row[
            "candidate_model"
        ]
    )

    raw_score = float(
        summary.loc[
            summary[
                "candidate_model"
            ].eq(
                "raw_deterministic"
            ),
            "mean_date_crps",
        ].iloc[0]
    )

    summary[
        "relative_crps_reduction_vs_raw"
    ] = (
        1.0
        - summary[
            "mean_date_crps"
        ]
        / raw_score
    )

    summary[
        "strict_crps_winner"
    ] = summary[
        "candidate_model"
    ].eq(
        strict_winner
    )

    summary[
        "parsimonious_selected_model"
    ] = summary[
        "candidate_model"
    ].eq(
        selected_model
    )

    summary = summary.sort_values(
        [
            "mean_date_crps",
            "complexity_rank",
            "candidate_order",
        ]
    ).reset_index(
        drop=True
    )

    fold_scores = (
        score_panel.groupby(
            [
                "candidate_model",
                "development_fold",
            ],
            as_index=False,
        )
        .agg(
            mean_crps=(
                "crps_99q",
                "mean",
            ),
            rows=(
                "row_id",
                "size",
            ),
            dates=(
                "target_date",
                "nunique",
            ),
        )
    )

    rule_scores = (
        score_panel.groupby(
            [
                "candidate_model",
                "decision_rule",
            ],
            as_index=False,
        )
        .agg(
            mean_crps=(
                "crps_99q",
                "mean",
            ),
            rows=(
                "row_id",
                "size",
            ),
            dates=(
                "target_date",
                "nunique",
            ),
        )
    )

    common_support_panel = (
        score_panel[
            [
                "row_id",
                "target_date",
                "decision_rule",
                "development_fold",
            ]
        ]
        .drop_duplicates()
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
        "strict_crps_winner": (
            strict_winner
        ),
        "selected_model": (
            selected_model
        ),
        "selected_family": str(
            selected_row[
                "family"
            ]
        ),
        "selected_complexity_rank": int(
            selected_row[
                "complexity_rank"
            ]
        ),
        "selected_mean_date_crps": float(
            selected_row[
                "mean_date_crps"
            ]
        ),
        "raw_mean_date_crps": (
            raw_score
        ),
        "selected_relative_crps_reduction_vs_raw": float(
            1.0
            - selected_row[
                "mean_date_crps"
            ]
            / raw_score
        ),
        "common_support_rows": (
            common_rows
        ),
        "common_support_dates": (
            common_dates
        ),
    }

    return (
        common_predictions,
        score_panel,
        date_scores,
        summary,
        fold_scores,
        rule_scores,
        common_support_panel,
        selection,
    )


def create_figure(
    summary: pd.DataFrame,
) -> None:
    figure_data = (
        summary.sort_values(
            "mean_date_crps",
            ascending=True,
        )
        .reset_index(
            drop=True
        )
    )

    figure, axis = plt.subplots(
        figsize=(
            10,
            6,
        )
    )

    axis.barh(
        figure_data[
            "display_name"
        ],
        figure_data[
            "mean_date_crps"
        ],
        xerr=figure_data[
            "standard_error_date_crps"
        ],
        capsize=3,
    )

    axis.invert_yaxis()

    axis.set_xlabel(
        "Mean date-level CRPS"
    )

    axis.set_ylabel(
        "Candidate specification"
    )

    axis.set_title(
        "Chronological out-of-fold probabilistic forecast comparison"
    )

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

    plt.close(
        figure
    )


def main() -> None:
    config = yaml.safe_load(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    panel = pd.read_csv(
        PANEL_PATH,
        low_memory=False,
    )

    panel[
        "target_date"
    ] = pd.to_datetime(
        panel[
            "target_date"
        ],
        errors="raise",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    panel[
        "development_fold"
    ] = pd.to_numeric(
        panel[
            "development_fold"
        ],
        errors="coerce",
    )

    if not set(
        panel[
            "chronology_block"
        ].unique()
    ).issuperset(
        {
            "warmup_training",
            "development_validation",
            "holdout",
            "external_test",
        }
    ):
        raise RuntimeError(
            "The chronological panel does not contain all declared blocks."
        )

    locked = panel[
        "chronology_block"
    ].isin(
        [
            "holdout",
            "external_test",
        ]
    )

    if panel.loc[
        locked,
        "outcome_may_influence_model_choice",
    ].astype(bool).any():
        raise RuntimeError(
            "A locked outcome is incorrectly marked as available for selection."
        )

    predictions, fit_log = (
        build_predictions(
            panel,
            config,
        )
    )

    (
        common_predictions,
        score_panel,
        date_scores,
        summary,
        fold_scores,
        rule_scores,
        common_support_panel,
        selection,
    ) = score_predictions(
        predictions,
        config,
    )

    for path in (
        PREDICTION_PATH,
        SCORE_PATH,
        DATE_SCORE_PATH,
        SUMMARY_PATH,
        FOLD_SCORE_PATH,
        RULE_SCORE_PATH,
        FIT_LOG_PATH,
        COMMON_SUPPORT_PATH,
        FINAL_TABLE_PATH,
        FIGURE_PNG_PATH,
        FIGURE_PDF_PATH,
        MANIFEST_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    predictions.to_csv(
        PREDICTION_PATH,
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

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
    )

    summary.to_csv(
        FINAL_TABLE_PATH,
        index=False,
    )

    fold_scores.to_csv(
        FOLD_SCORE_PATH,
        index=False,
    )

    rule_scores.to_csv(
        RULE_SCORE_PATH,
        index=False,
    )

    fit_log.to_csv(
        FIT_LOG_PATH,
        index=False,
    )

    common_support_panel.to_csv(
        COMMON_SUPPORT_PATH,
        index=False,
    )

    create_figure(
        summary
    )

    candidate_support = (
        predictions.groupby(
            "candidate_model"
        )
        .agg(
            available_rows=(
                "row_id",
                "nunique",
            ),
            available_dates=(
                "target_date",
                "nunique",
            ),
        )
        .reset_index()
        .to_dict(
            orient="records"
        )
    )

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "DEVELOPMENT_MODEL_SELECTION_COMPLETE"
        ),
        "selection_locked": True,
        "strict_crps_winner": (
            selection[
                "strict_crps_winner"
            ]
        ),
        "selected_model": (
            selection[
                "selected_model"
            ]
        ),
        "selected_family": (
            selection[
                "selected_family"
            ]
        ),
        "selected_complexity_rank": (
            selection[
                "selected_complexity_rank"
            ]
        ),
        "selected_mean_date_crps": (
            selection[
                "selected_mean_date_crps"
            ]
        ),
        "raw_mean_date_crps": (
            selection[
                "raw_mean_date_crps"
            ]
        ),
        "selected_relative_crps_reduction_vs_raw": (
            selection[
                "selected_relative_crps_reduction_vs_raw"
            ]
        ),
        "common_support_rows": (
            selection[
                "common_support_rows"
            ]
        ),
        "common_support_dates": (
            selection[
                "common_support_dates"
            ]
        ),
        "candidate_count": 9,
        "quantile_count": 99,
        "development_fold_count": 4,
        "score": (
            "99-quantile approximation to CRPS"
        ),
        "selection_rule": (
            "paired one-standard-error parsimony rule"
        ),
        "holdout_accessed": False,
        "external_test_accessed": False,
        "holdout_or_external_outcome_used_for_selection": False,
        "candidate_support": (
            candidate_support
        ),
        "input_hashes": {
            str(
                PANEL_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                PANEL_PATH
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
                SUMMARY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                SUMMARY_PATH
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
    print("=" * 80)
    print(" PROBABILISTIC OOF MODEL SELECTION COMPLETE")
    print("=" * 80)
    print()
    print(
        "Development folds:",
        manifest[
            "development_fold_count"
        ],
    )
    print(
        "Candidate specifications:",
        manifest[
            "candidate_count"
        ],
    )
    print(
        "Quantiles per prediction:",
        manifest[
            "quantile_count"
        ],
    )
    print(
        "Common support rows:",
        manifest[
            "common_support_rows"
        ],
    )
    print(
        "Common support dates:",
        manifest[
            "common_support_dates"
        ],
    )
    print()
    print("Candidate ranking:")
    print(
        summary[
            [
                "candidate_model",
                "family",
                "mean_date_crps",
                "standard_error_date_crps",
                "relative_crps_reduction_vs_raw",
                "available_oof_rows",
                "within_one_standard_error",
                "strict_crps_winner",
                "parsimonious_selected_model",
            ]
        ].to_string(
            index=False
        )
    )
    print()
    print(
        "Strict CRPS winner:",
        manifest[
            "strict_crps_winner"
        ],
    )
    print(
        "Parsimonious selected model:",
        manifest[
            "selected_model"
        ],
    )
    print(
        "Selected family:",
        manifest[
            "selected_family"
        ],
    )
    print(
        "Selected mean date-level CRPS:",
        manifest[
            "selected_mean_date_crps"
        ],
    )
    print(
        "Selected CRPS reduction versus raw:",
        manifest[
            "selected_relative_crps_reduction_vs_raw"
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
    print()
    print(
        "Next stage: fit the locked selected specification using "
        "warm-up plus development data, then evaluate the untouched "
        "holdout and June blocks."
    )


if __name__ == "__main__":
    main()
