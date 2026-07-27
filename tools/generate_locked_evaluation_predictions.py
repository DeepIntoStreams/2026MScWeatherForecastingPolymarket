#!/usr/bin/env python3
"""Generate locked holdout and external predictive distributions."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    empirical_quantiles,
    pooled_catboost_quantiles,
    quantile_columns,
    rule_specific_catboost_quantiles,
    rule_specific_gp_quantiles,
)


MODEL_CONFIG_PATH = (
    ROOT
    / "config"
    / "probabilistic_model_spec.yaml"
)

PREDICTION_CONFIG_PATH = (
    ROOT
    / "config"
    / "locked_prediction_spec.yaml"
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

DETERMINISTIC_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_selected_deterministic_forecast_panel.csv"
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

FIT_LOG_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "06_locked_prediction_fit_log.csv"
)

BLOCK_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "06_locked_prediction_block_summary.csv"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "06_locked_prediction_integrity_checks.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "06_locked_prediction_manifest.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


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
            "The dispersion scale must be positive."
        )

    median = values[
        :,
        49,
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
            49,
        ],
        values[
            :,
            49,
        ],
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Calibration changed the predictive median."
        )

    if not (
        np.diff(
            calibrated,
            axis=1,
        )
        >= -1.0e-10
    ).all():
        raise RuntimeError(
            "Calibration produced crossing quantiles."
        )

    return calibrated


def prediction_base(
    frame: pd.DataFrame,
    selected_model: str,
    selected_family: str,
    scale: float,
) -> pd.DataFrame:
    result = frame[
        [
            "target_date",
            "decision_rule",
            "chronology_block",
            "forecast_daily_max_c",
            "forecast_issue_time_utc",
            "decision_time_utc",
            "unique_local_hours",
            "source_period",
        ]
    ].copy()

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
        "selected_model"
    ] = selected_model

    result[
        "selected_family"
    ] = selected_family

    result[
        "dispersion_scale"
    ] = float(scale)

    result[
        "prediction_locked"
    ] = True

    return result


def fit_selected_model(
    selected_model: str,
    selected_family: str,
    training: pd.DataFrame,
    prediction: pd.DataFrame,
    model_config: dict[str, Any],
) -> tuple[
    np.ndarray,
    pd.DataFrame,
]:
    random_seed = int(
        model_config[
            "random_seed"
        ]
    )

    minimum_rows = int(
        model_config[
            "validation"
        ][
            "minimum_rule_training_rows"
        ]
    )

    forecast = pd.to_numeric(
        prediction[
            "forecast_daily_max_c"
        ],
        errors="raise",
    ).to_numpy(
        dtype=float
    )

    logs: list[
        dict[str, Any]
    ] = []

    if selected_model == "pooled_empirical_residual":
        residual_quantiles = empirical_quantiles(
            training[
                "residual_c"
            ].to_numpy(
                dtype=float
            )
        )

        quantiles = (
            forecast.reshape(
                -1,
                1,
            )
            + residual_quantiles.reshape(
                1,
                -1,
            )
        )

        logs.append(
            {
                "candidate_model": selected_model,
                "component": "empirical_residual",
                "scope": "pooled",
                "training_rows": len(training),
                "training_dates": int(
                    training[
                        "target_date"
                    ].nunique()
                ),
                "prediction_rows": len(prediction),
                "status": "OK",
                "warning_count": 0,
                "learned_kernel": "",
                "message": (
                    "Ninety-nine empirical residual quantiles "
                    "estimated from the full pre-holdout sample."
                ),
            }
        )

    elif selected_model == "rule_empirical_residual":
        quantiles = np.full(
            (
                len(prediction),
                len(
                    QUANTILE_LEVELS
                ),
            ),
            np.nan,
            dtype=float,
        )

        for rule in sorted(
            prediction[
                "decision_rule"
            ].unique()
        ):
            prediction_mask = (
                prediction[
                    "decision_rule"
                ].eq(
                    rule
                )
            )

            positions = np.flatnonzero(
                prediction_mask.to_numpy()
            )

            training_rule = training.loc[
                training[
                    "decision_rule"
                ].eq(
                    rule
                )
            ].copy()

            if len(training_rule) < minimum_rows:
                raise RuntimeError(
                    f"Rule {rule} has only {len(training_rule)} "
                    f"training rows; {minimum_rows} are required."
                )

            residual_quantiles = empirical_quantiles(
                training_rule[
                    "residual_c"
                ].to_numpy(
                    dtype=float
                )
            )

            quantiles[
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

            logs.append(
                {
                    "candidate_model": selected_model,
                    "component": "empirical_residual",
                    "scope": rule,
                    "training_rows": len(training_rule),
                    "training_dates": int(
                        training_rule[
                            "target_date"
                        ].nunique()
                    ),
                    "prediction_rows": len(positions),
                    "status": "OK",
                    "warning_count": 0,
                    "learned_kernel": "",
                    "message": (
                        "Rule-specific empirical residual "
                        "quantiles estimated."
                    ),
                }
            )

    elif selected_model == "rule_gp_rbf":
        quantiles, gp_logs = (
            rule_specific_gp_quantiles(
                training=training,
                validation=prediction,
                covariance="rbf",
                minimum_rows=minimum_rows,
                random_seed=random_seed,
            )
        )

        for log in gp_logs:
            logs.append(
                {
                    "candidate_model": selected_model,
                    "component": log.get(
                        "component",
                        "gaussian_process",
                    ),
                    "scope": log.get(
                        "scope",
                        "",
                    ),
                    "training_rows": log.get(
                        "training_rows",
                        0,
                    ),
                    "training_dates": int(
                        training.loc[
                            training[
                                "decision_rule"
                            ].eq(
                                log.get(
                                    "scope",
                                    "",
                                )
                            ),
                            "target_date",
                        ].nunique()
                    ),
                    "prediction_rows": log.get(
                        "validation_rows",
                        0,
                    ),
                    "status": log.get(
                        "status",
                        "",
                    ),
                    "warning_count": log.get(
                        "warning_count",
                        0,
                    ),
                    "learned_kernel": log.get(
                        "learned_kernel",
                        "",
                    ),
                    "message": log.get(
                        "message",
                        "",
                    ),
                }
            )

    elif selected_model == "rule_gp_matern32":
        quantiles, gp_logs = (
            rule_specific_gp_quantiles(
                training=training,
                validation=prediction,
                covariance="matern32",
                minimum_rows=minimum_rows,
                random_seed=random_seed,
            )
        )

        for log in gp_logs:
            logs.append(
                {
                    "candidate_model": selected_model,
                    "component": log.get(
                        "component",
                        "gaussian_process",
                    ),
                    "scope": log.get(
                        "scope",
                        "",
                    ),
                    "training_rows": log.get(
                        "training_rows",
                        0,
                    ),
                    "training_dates": int(
                        training.loc[
                            training[
                                "decision_rule"
                            ].eq(
                                log.get(
                                    "scope",
                                    "",
                                )
                            ),
                            "target_date",
                        ].nunique()
                    ),
                    "prediction_rows": log.get(
                        "validation_rows",
                        0,
                    ),
                    "status": log.get(
                        "status",
                        "",
                    ),
                    "warning_count": log.get(
                        "warning_count",
                        0,
                    ),
                    "learned_kernel": log.get(
                        "learned_kernel",
                        "",
                    ),
                    "message": log.get(
                        "message",
                        "",
                    ),
                }
            )

    elif selected_model == "pooled_catboost_quantile":
        quantiles, catboost_log = (
            pooled_catboost_quantiles(
                training=training,
                validation=prediction,
                random_seed=random_seed,
            )
        )

        logs.append(
            {
                "candidate_model": selected_model,
                "component": "catboost_quantile",
                "scope": "pooled",
                "training_rows": len(training),
                "training_dates": int(
                    training[
                        "target_date"
                    ].nunique()
                ),
                "prediction_rows": len(prediction),
                "status": catboost_log.get(
                    "status",
                    "",
                ),
                "warning_count": 0,
                "learned_kernel": "",
                "message": catboost_log.get(
                    "message",
                    "",
                ),
            }
        )

    elif selected_model == "rule_catboost_quantile":
        quantiles, catboost_logs = (
            rule_specific_catboost_quantiles(
                training=training,
                validation=prediction,
                minimum_rows=minimum_rows,
                random_seed=random_seed,
            )
        )

        for log in catboost_logs:
            logs.append(
                {
                    "candidate_model": selected_model,
                    "component": "catboost_quantile",
                    "scope": log.get(
                        "scope",
                        "",
                    ),
                    "training_rows": log.get(
                        "training_rows",
                        0,
                    ),
                    "training_dates": int(
                        training.loc[
                            training[
                                "decision_rule"
                            ].eq(
                                log.get(
                                    "scope",
                                    "",
                                )
                            ),
                            "target_date",
                        ].nunique()
                    ),
                    "prediction_rows": log.get(
                        "validation_rows",
                        0,
                    ),
                    "status": log.get(
                        "status",
                        "",
                    ),
                    "warning_count": 0,
                    "learned_kernel": "",
                    "message": log.get(
                        "message",
                        "",
                    ),
                }
            )

    else:
        raise RuntimeError(
            "Unsupported locked model for continuous prediction: "
            f"{selected_model}."
        )

    quantiles = np.asarray(
        quantiles,
        dtype=float,
    )

    if quantiles.shape != (
        len(prediction),
        99,
    ):
        raise RuntimeError(
            "The locked model returned an unexpected "
            f"prediction shape: {quantiles.shape}."
        )

    if not np.isfinite(
        quantiles
    ).all():
        raise RuntimeError(
            "The locked model produced non-finite quantiles."
        )

    quantiles = np.maximum.accumulate(
        quantiles,
        axis=1,
    )

    fit_log = pd.DataFrame(
        logs
    )

    if fit_log.empty:
        raise RuntimeError(
            "The locked model produced no fit log."
        )

    if not fit_log[
        "status"
    ].astype(str).eq(
        "OK"
    ).all():
        failed = fit_log.loc[
            ~fit_log[
                "status"
            ].astype(str).eq(
                "OK"
            )
        ]

        raise RuntimeError(
            "One or more locked model fits failed:\n"
            + failed.to_string(
                index=False
            )
        )

    return quantiles, fit_log


def main() -> None:
    model_config = yaml.safe_load(
        MODEL_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    prediction_config = yaml.safe_load(
        PREDICTION_CONFIG_PATH.read_text(
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

    if not model_manifest[
        "selection_locked"
    ]:
        raise RuntimeError(
            "Model selection is not locked."
        )

    if not calibration_manifest[
        "calibration_locked"
    ]:
        raise RuntimeError(
            "Continuous calibration is not locked."
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

    if selected_family in {
        "raw",
        "mean_residual",
    }:
        raise RuntimeError(
            "The locked model is distributionally degenerate."
        )

    deterministic_columns = [
        "target_date",
        "decision_rule",
        "forecast_daily_max_c",
        "forecast_issue_time_utc",
        "decision_time_utc",
        "unique_local_hours",
        "source_period",
    ]

    deterministic = pd.read_csv(
        DETERMINISTIC_PATH,
        usecols=deterministic_columns,
        low_memory=False,
    )

    chronology_columns = [
        "target_date",
        "decision_rule",
        "chronology_block",
        "development_fold",
        "forecast_daily_max_c",
        "residual_c",
    ]

    chronology = pd.read_csv(
        CHRONOLOGY_PATH,
        usecols=chronology_columns,
        low_memory=False,
    )

    for frame in (
        deterministic,
        chronology,
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

    if deterministic[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "The deterministic panel duplicates a date-rule key."
        )

    if chronology[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "The chronology panel duplicates a date-rule key."
        )

    chronology_metadata = chronology[
        [
            "target_date",
            "decision_rule",
            "chronology_block",
            "development_fold",
        ]
    ].copy()

    prediction_source = deterministic.merge(
        chronology_metadata,
        on=[
            "target_date",
            "decision_rule",
        ],
        how="inner",
        validate="one_to_one",
    )

    prediction_blocks = set(
        prediction_config[
            "prediction"
        ][
            "blocks"
        ]
    )

    prediction = (
        prediction_source.loc[
            prediction_source[
                "chronology_block"
            ].isin(
                prediction_blocks
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

    training_blocks = set(
        prediction_config[
            "training"
        ][
            "permitted_blocks"
        ]
    )

    training = (
        chronology.loc[
            chronology[
                "chronology_block"
            ].isin(
                training_blocks
            ),
            [
                "target_date",
                "decision_rule",
                "forecast_daily_max_c",
                "residual_c",
                "chronology_block",
            ],
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
            "The locked final fit has no training observations."
        )

    if prediction.empty:
        raise RuntimeError(
            "No locked prediction observations were found."
        )

    if not training[
        "chronology_block"
    ].isin(
        training_blocks
    ).all():
        raise RuntimeError(
            "A prohibited block entered final model fitting."
        )

    if not prediction[
        "chronology_block"
    ].isin(
        prediction_blocks
    ).all():
        raise RuntimeError(
            "A non-evaluation block entered locked prediction."
        )

    training_end = training[
        "target_date"
    ].max()

    holdout_start = prediction.loc[
        prediction[
            "chronology_block"
        ].eq(
            "holdout"
        ),
        "target_date",
    ].min()

    if not (
        training_end
        < holdout_start
    ):
        raise RuntimeError(
            "Final training does not end before the holdout."
        )

    if len(training) != 216:
        raise RuntimeError(
            f"Expected 216 pre-holdout training rows; found {len(training)}."
        )

    if training[
        "target_date"
    ].nunique() != 62:
        raise RuntimeError(
            "Expected 62 pre-holdout training dates."
        )

    if len(prediction) != 159:
        raise RuntimeError(
            f"Expected 159 locked prediction rows; found {len(prediction)}."
        )

    if prediction[
        "target_date"
    ].nunique() != 40:
        raise RuntimeError(
            "Expected 40 locked prediction dates."
        )

    holdout_rows = int(
        prediction[
            "chronology_block"
        ].eq(
            "holdout"
        ).sum()
    )

    external_rows = int(
        prediction[
            "chronology_block"
        ].eq(
            "external_test"
        ).sum()
    )

    if holdout_rows != 40:
        raise RuntimeError(
            f"Expected 40 holdout rows; found {holdout_rows}."
        )

    if external_rows != 119:
        raise RuntimeError(
            f"Expected 119 external rows; found {external_rows}."
        )

    issue_time = pd.to_datetime(
        prediction[
            "forecast_issue_time_utc"
        ],
        errors="raise",
        utc=True,
    )

    decision_time = pd.to_datetime(
        prediction[
            "decision_time_utc"
        ],
        errors="raise",
        utc=True,
    )

    if not (
        issue_time
        <= decision_time
    ).all():
        raise RuntimeError(
            "A locked forecast was issued after its decision time."
        )

    if not prediction[
        "unique_local_hours"
    ].eq(24).all():
        raise RuntimeError(
            "A locked forecast path lacks 24 Hong Kong local hours."
        )

    uncalibrated_quantiles, fit_log = (
        fit_selected_model(
            selected_model=selected_model,
            selected_family=selected_family,
            training=training,
            prediction=prediction,
            model_config=model_config,
        )
    )

    calibrated_quantiles = apply_dispersion_scale(
        uncalibrated_quantiles,
        selected_scale,
    )

    base = prediction_base(
        prediction,
        selected_model,
        selected_family,
        selected_scale,
    )

    uncalibrated = base.copy()
    calibrated = base.copy()

    q_columns = quantile_columns()

    for index, column in enumerate(
        q_columns
    ):
        uncalibrated[
            column
        ] = uncalibrated_quantiles[
            :,
            index,
        ]

        calibrated[
            column
        ] = calibrated_quantiles[
            :,
            index,
        ]

    uncalibrated[
        "continuous_calibration_applied"
    ] = False

    calibrated[
        "continuous_calibration_applied"
    ] = bool(
        not math.isclose(
            selected_scale,
            1.0,
            abs_tol=1.0e-12,
        )
    )

    prohibited_fragments = (
        "hko_daily_max",
        "residual",
        "outcome",
        "realised",
        "realized",
        "crps",
        "brier",
        "log_score",
        "pnl",
        "profit",
        "market_price",
    )

    for output_name, frame in (
        (
            "uncalibrated",
            uncalibrated,
        ),
        (
            "calibrated",
            calibrated,
        ),
    ):
        prohibited = [
            column
            for column in frame.columns
            if any(
                fragment in column.lower()
                for fragment in prohibited_fragments
            )
        ]

        if prohibited:
            raise RuntimeError(
                f"{output_name} prediction output contains "
                "prohibited evaluation fields: "
                + ", ".join(
                    prohibited
                )
            )

    uncalibrated_values = uncalibrated[
        q_columns
    ].to_numpy(
        dtype=float
    )

    calibrated_values = calibrated[
        q_columns
    ].to_numpy(
        dtype=float
    )

    if not np.isfinite(
        calibrated_values
    ).all():
        raise RuntimeError(
            "Calibrated predictions contain non-finite values."
        )

    if not (
        np.diff(
            calibrated_values,
            axis=1,
        )
        >= -1.0e-10
    ).all():
        raise RuntimeError(
            "Calibrated predictions contain crossing quantiles."
        )

    maximum_median_change = float(
        np.max(
            np.abs(
                uncalibrated_values[
                    :,
                    49,
                ]
                - calibrated_values[
                    :,
                    49,
                ]
            )
        )
    )

    if maximum_median_change > 1.0e-12:
        raise RuntimeError(
            "Locked calibration changed the predictive median."
        )

    positive_80_width_share = float(
        (
            calibrated_values[
                :,
                89,
            ]
            - calibrated_values[
                :,
                9,
            ]
            > 1.0e-10
        ).mean()
    )

    if positive_80_width_share < 0.99:
        raise RuntimeError(
            "The locked distribution is degenerate on too many rows."
        )

    fit_log[
        "training_start"
    ] = training[
        "target_date"
    ].min()

    fit_log[
        "training_end"
    ] = training[
        "target_date"
    ].max()

    fit_log[
        "selected_family"
    ] = selected_family

    fit_log[
        "dispersion_scale"
    ] = selected_scale

    block_summary = (
        calibrated.groupby(
            "chronology_block"
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
            start_date=(
                "target_date",
                "min",
            ),
            end_date=(
                "target_date",
                "max",
            ),
            decision_rules=(
                "decision_rule",
                "nunique",
            ),
        )
        .reset_index()
        .sort_values(
            "start_date"
        )
    )

    checks = pd.DataFrame(
        [
            {
                "check": "training_rows_equal_216",
                "passed": len(training) == 216,
                "value": len(training),
            },
            {
                "check": "training_dates_equal_62",
                "passed": (
                    training[
                        "target_date"
                    ].nunique()
                    == 62
                ),
                "value": (
                    training[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "prediction_rows_equal_159",
                "passed": len(calibrated) == 159,
                "value": len(calibrated),
            },
            {
                "check": "prediction_dates_equal_40",
                "passed": (
                    calibrated[
                        "target_date"
                    ].nunique()
                    == 40
                ),
                "value": (
                    calibrated[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "holdout_rows_equal_40",
                "passed": holdout_rows == 40,
                "value": holdout_rows,
            },
            {
                "check": "external_rows_equal_119",
                "passed": external_rows == 119,
                "value": external_rows,
            },
            {
                "check": "training_precedes_holdout",
                "passed": training_end < holdout_start,
                "value": (
                    f"{training_end} < {holdout_start}"
                ),
            },
            {
                "check": "all_forecasts_available_by_decision",
                "passed": bool(
                    (
                        issue_time
                        <= decision_time
                    ).all()
                ),
                "value": True,
            },
            {
                "check": "all_paths_have_24_local_hours",
                "passed": bool(
                    prediction[
                        "unique_local_hours"
                    ].eq(24).all()
                ),
                "value": True,
            },
            {
                "check": "quantiles_finite",
                "passed": bool(
                    np.isfinite(
                        calibrated_values
                    ).all()
                ),
                "value": True,
            },
            {
                "check": "quantiles_monotone",
                "passed": bool(
                    (
                        np.diff(
                            calibrated_values,
                            axis=1,
                        )
                        >= -1.0e-10
                    ).all()
                ),
                "value": True,
            },
            {
                "check": "predictive_median_preserved",
                "passed": (
                    maximum_median_change
                    <= 1.0e-12
                ),
                "value": maximum_median_change,
            },
            {
                "check": "no_outcome_or_score_columns",
                "passed": True,
                "value": True,
            },
            {
                "check": "all_final_model_fits_ok",
                "passed": bool(
                    fit_log[
                        "status"
                    ].astype(str).eq(
                        "OK"
                    ).all()
                ),
                "value": True,
            },
        ]
    )

    if not checks[
        "passed"
    ].all():
        raise RuntimeError(
            "One or more locked prediction integrity checks failed."
        )

    for path in (
        UNCALIBRATED_PATH,
        CALIBRATED_PATH,
        FIT_LOG_PATH,
        BLOCK_SUMMARY_PATH,
        INTEGRITY_PATH,
        MANIFEST_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    uncalibrated.to_csv(
        UNCALIBRATED_PATH,
        index=False,
    )

    calibrated.to_csv(
        CALIBRATED_PATH,
        index=False,
    )

    fit_log.to_csv(
        FIT_LOG_PATH,
        index=False,
    )

    block_summary.to_csv(
        BLOCK_SUMMARY_PATH,
        index=False,
    )

    checks.to_csv(
        INTEGRITY_PATH,
        index=False,
    )

    warning_count = int(
        pd.to_numeric(
            fit_log[
                "warning_count"
            ],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "LOCKED_HOLDOUT_AND_EXTERNAL_PREDICTIONS_GENERATED"
        ),
        "predictions_locked": True,
        "selected_model": selected_model,
        "selected_family": selected_family,
        "selected_dispersion_scale": selected_scale,
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
        "prediction_rows": len(calibrated),
        "prediction_dates": int(
            calibrated[
                "target_date"
            ].nunique()
        ),
        "holdout_rows": holdout_rows,
        "holdout_dates": int(
            calibrated.loc[
                calibrated[
                    "chronology_block"
                ].eq(
                    "holdout"
                ),
                "target_date",
            ].nunique()
        ),
        "external_test_rows": external_rows,
        "external_test_dates": int(
            calibrated.loc[
                calibrated[
                    "chronology_block"
                ].eq(
                    "external_test"
                ),
                "target_date",
            ].nunique()
        ),
        "quantile_count": 99,
        "maximum_predictive_median_change_c": (
            maximum_median_change
        ),
        "positive_central_80_width_share": (
            positive_80_width_share
        ),
        "final_fit_warning_count": warning_count,
        "final_fit_non_ok_records": int(
            (
                ~fit_log[
                    "status"
                ].astype(str).eq(
                    "OK"
                )
            ).sum()
        ),
        "holdout_outcomes_used_for_fit": False,
        "external_test_outcomes_used_for_fit": False,
        "holdout_outcomes_in_prediction_file": False,
        "external_outcomes_in_prediction_file": False,
        "continuous_scores_calculated": False,
        "event_probabilities_calculated": False,
        "market_data_accessed": False,
        "trading_returns_calculated": False,
        "refit_after_holdout": False,
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
                DETERMINISTIC_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                DETERMINISTIC_PATH
            ),
            str(
                CHRONOLOGY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CHRONOLOGY_PATH
            ),
            str(
                PREDICTION_CONFIG_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                PREDICTION_CONFIG_PATH
            ),
        },
        "output_hashes": {
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
                FIT_LOG_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                FIT_LOG_PATH
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
    print(" LOCKED HOLDOUT AND EXTERNAL PREDICTIONS GENERATED")
    print("=" * 84)
    print()
    print("Selected model:", selected_model)
    print("Selected family:", selected_family)
    print("Locked dispersion scale:", selected_scale)
    print()
    print("Training rows:", len(training))
    print(
        "Training dates:",
        training[
            "target_date"
        ].nunique(),
    )
    print(
        "Training period:",
        training[
            "target_date"
        ].min(),
        "to",
        training[
            "target_date"
        ].max(),
    )
    print()
    print("Prediction rows:", len(calibrated))
    print(
        "Prediction dates:",
        calibrated[
            "target_date"
        ].nunique(),
    )
    print("Holdout rows:", holdout_rows)
    print("External-test rows:", external_rows)
    print()
    print(
        "Maximum predictive median change:",
        maximum_median_change,
    )
    print(
        "Positive central 80% width share:",
        positive_80_width_share,
    )
    print(
        "Final fit warnings:",
        warning_count,
    )
    print()
    print("Prediction block summary:")
    print(
        block_summary.to_string(
            index=False
        )
    )
    print()
    print(
        "Holdout outcomes used for fit:",
        False,
    )
    print(
        "External outcomes used for fit:",
        False,
    )
    print(
        "Continuous scores calculated:",
        False,
    )
    print(
        "Event probabilities calculated:",
        False,
    )
    print(
        "Market data accessed:",
        False,
    )
    print(
        "Trading returns calculated:",
        False,
    )
    print()
    print(
        "Next stage: join realised outcomes only after these "
        "prediction files are locked, then evaluate holdout and "
        "external continuous-distribution performance."
    )


if __name__ == "__main__":
    main()
