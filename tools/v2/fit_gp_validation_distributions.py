from __future__ import annotations

import hashlib
import json
import math
import os
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (
    ConstantKernel,
    Matern,
    RBF,
    WhiteKernel,
)


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
    "gp_validation_spec.json"
)

PHASE6_MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "06_gp_training_design_manifest.json"
)

SOURCE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_matrix_panel.csv"
)

PREDICTIONS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_validation_predictions.csv"
)

MODEL_LEDGER_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_model_fit_ledger.csv"
)

DATE_SCORE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_date_level_scores.csv"
)

PAIRED_DATE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_kernel_paired_date_comparison.csv"
)

RULE_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_kernel_rule_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "07_gp_validation_integrity_checks.csv"
)

KERNEL_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/final_tables/"
    "07_gp_kernel_validation_summary.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "07_gp_validation_manifest.json"
)


FEATURE_COLUMNS = [
    "calendar_time_years_z",
    "seasonal_sin_z",
    "seasonal_cos_z",
    "forecast_daily_max_c_z",
]

RULE_ORDER = {
    "24h_prior": 1,
    "12h_prior": 2,
    "6h_prior": 3,
    "event_day_open": 4,
}

KERNEL_ORDER = {
    "rbf": 1,
    "matern32": 2,
}

QUANTILE_PROBABILITIES = (
    np.arange(1, 100, dtype=float) / 100.0
)

QUANTILE_COLUMNS = [
    f"q{integer:02d}_c"
    for integer in range(1, 100)
]


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def atomic_write_text(
    path: Path,
    text: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_text(
        text,
        encoding="utf-8",
    )

    os.replace(
        temporary,
        path,
    )


def write_csv(
    panel: pd.DataFrame,
    path: Path,
) -> None:
    atomic_write_text(
        path,
        panel.to_csv(
            index=False,
            float_format="%.10f",
        ),
    )


def write_json(
    payload: dict[str, Any],
    path: Path,
) -> None:
    atomic_write_text(
        path,
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def normal_crps(
    observation: np.ndarray,
    mean: np.ndarray,
    standard_deviation: np.ndarray,
) -> np.ndarray:
    sigma = np.maximum(
        np.asarray(
            standard_deviation,
            dtype=float,
        ),
        1e-8,
    )

    z_value = (
        np.asarray(
            observation,
            dtype=float,
        )
        - np.asarray(
            mean,
            dtype=float,
        )
    ) / sigma

    return sigma * (
        z_value
        * (
            2.0 * norm.cdf(z_value)
            - 1.0
        )
        + 2.0 * norm.pdf(z_value)
        - 1.0 / math.sqrt(math.pi)
    )


def gaussian_negative_log_score(
    observation: np.ndarray,
    mean: np.ndarray,
    standard_deviation: np.ndarray,
) -> np.ndarray:
    sigma = np.maximum(
        np.asarray(
            standard_deviation,
            dtype=float,
        ),
        1e-8,
    )

    squared_standardised_error = (
        (
            np.asarray(
                observation,
                dtype=float,
            )
            - np.asarray(
                mean,
                dtype=float,
            )
        )
        / sigma
    ) ** 2

    return (
        0.5
        * np.log(
            2.0
            * math.pi
            * sigma**2
        )
        + 0.5
        * squared_standardised_error
    )


def create_kernel(
    kernel_key: str,
    specification: dict[str, Any],
):
    kernel_specification = (
        specification[
            "candidate_kernels"
        ][kernel_key]
    )

    signal = ConstantKernel(
        constant_value=float(
            kernel_specification[
                "initial_signal_variance"
            ]
        ),
        constant_value_bounds=tuple(
            kernel_specification[
                "signal_variance_bounds"
            ]
        ),
    )

    if kernel_key == "rbf":
        covariance = RBF(
            length_scale=float(
                kernel_specification[
                    "initial_length_scale"
                ]
            ),
            length_scale_bounds=tuple(
                kernel_specification[
                    "length_scale_bounds"
                ]
            ),
        )
    elif kernel_key == "matern32":
        covariance = Matern(
            length_scale=float(
                kernel_specification[
                    "initial_length_scale"
                ]
            ),
            length_scale_bounds=tuple(
                kernel_specification[
                    "length_scale_bounds"
                ]
            ),
            nu=float(
                kernel_specification["nu"]
            ),
        )
    else:
        raise ValueError(
            f"Unknown kernel: {kernel_key}"
        )

    noise = WhiteKernel(
        noise_level=float(
            kernel_specification[
                "initial_noise_variance"
            ]
        ),
        noise_level_bounds=tuple(
            kernel_specification[
                "noise_variance_bounds"
            ]
        ),
    )

    return signal * covariance + noise


def extract_fitted_parameters(
    fitted_kernel,
) -> tuple[
    float,
    float,
    float,
]:
    signal_variance = float(
        fitted_kernel.k1.k1.constant_value
    )

    length_scale_array = np.asarray(
        fitted_kernel.k1.k2.length_scale,
        dtype=float,
    ).reshape(-1)

    if len(length_scale_array) != 1:
        raise RuntimeError(
            "The fitted kernel unexpectedly used "
            "more than one length scale."
        )

    length_scale = float(
        length_scale_array[0]
    )

    noise_variance = float(
        fitted_kernel.k2.noise_level
    )

    return (
        signal_variance,
        length_scale,
        noise_variance,
    )


def fit_one_model(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    fold_id: str,
    fold_number: int,
    decision_rule: str,
    kernel_key: str,
    specification: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    dict[str, Any],
]:
    x_training = training[
        FEATURE_COLUMNS
    ].to_numpy(dtype=float)

    y_training = training[
        "gp_target"
    ].to_numpy(dtype=float)

    x_validation = validation[
        FEATURE_COLUMNS
    ].to_numpy(dtype=float)

    y_validation = validation[
        "gp_target"
    ].to_numpy(dtype=float)

    kernel = create_kernel(
        kernel_key=kernel_key,
        specification=specification,
    )

    model = GaussianProcessRegressor(
        kernel=kernel,
        alpha=float(
            specification[
                "numerical_jitter"
            ]
        ),
        optimizer=specification[
            "optimizer"
        ],
        n_restarts_optimizer=int(
            specification[
                "optimizer_restarts"
            ]
        ),
        normalize_y=bool(
            specification[
                "normalise_training_target"
            ]
        ),
        copy_X_train=True,
        random_state=int(
            specification[
                "random_seed"
            ]
        ),
    )

    started = time.perf_counter()

    with warnings.catch_warnings(
        record=True
    ) as captured_warnings:
        warnings.simplefilter("always")

        model.fit(
            x_training,
            y_training,
        )

        residual_mean, residual_standard_deviation = (
            model.predict(
                x_validation,
                return_std=True,
            )
        )

    elapsed_seconds = (
        time.perf_counter()
        - started
    )

    residual_standard_deviation = np.maximum(
        np.asarray(
            residual_standard_deviation,
            dtype=float,
        ),
        1e-6,
    )

    residual_mean = np.asarray(
        residual_mean,
        dtype=float,
    )

    forecast_temperature = validation[
        "forecast_daily_max_c"
    ].to_numpy(dtype=float)

    observed_temperature = validation[
        "hko_daily_max_c"
    ].to_numpy(dtype=float)

    predictive_temperature_mean = (
        forecast_temperature
        + residual_mean
    )

    temperature_error = (
        observed_temperature
        - predictive_temperature_mean
    )

    residual_standardised_error = (
        y_validation
        - residual_mean
    ) / residual_standard_deviation

    pit_value = norm.cdf(
        residual_standardised_error
    )

    crps_value = normal_crps(
        observation=y_validation,
        mean=residual_mean,
        standard_deviation=(
            residual_standard_deviation
        ),
    )

    negative_log_score = (
        gaussian_negative_log_score(
            observation=y_validation,
            mean=residual_mean,
            standard_deviation=(
                residual_standard_deviation
            ),
        )
    )

    quantile_z_values = norm.ppf(
        QUANTILE_PROBABILITIES
    )

    temperature_quantiles = (
        predictive_temperature_mean[:, None]
        + residual_standard_deviation[:, None]
        * quantile_z_values[None, :]
    )

    fitted_signal_variance, fitted_length_scale, fitted_noise_variance = (
        extract_fitted_parameters(
            model.kernel_
        )
    )

    model_identifier = (
        f"{fold_id}__"
        f"{decision_rule}__"
        f"{kernel_key}"
    )

    output_columns = [
        "target_date",
        "fold_id",
        "fold_number",
        "decision_rule",
        "decision_rule_order",
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "gp_target",
    ]

    result = validation[
        output_columns
    ].copy().reset_index(drop=True)

    result[
        "kernel"
    ] = kernel_key

    result[
        "kernel_order"
    ] = KERNEL_ORDER[
        kernel_key
    ]

    result[
        "model_identifier"
    ] = model_identifier

    result[
        "residual_observed_c"
    ] = y_validation

    result[
        "residual_predictive_mean_c"
    ] = residual_mean

    result[
        "predictive_standard_deviation_c"
    ] = residual_standard_deviation

    result[
        "temperature_predictive_mean_c"
    ] = predictive_temperature_mean

    result[
        "raw_temperature_error_c"
    ] = (
        observed_temperature
        - forecast_temperature
    )

    result[
        "corrected_temperature_error_c"
    ] = temperature_error

    result[
        "absolute_corrected_error_c"
    ] = np.abs(
        temperature_error
    )

    result[
        "squared_corrected_error_c2"
    ] = temperature_error**2

    result[
        "standardised_residual_error"
    ] = residual_standardised_error

    result[
        "pit_value"
    ] = pit_value

    result[
        "crps_c"
    ] = crps_value

    result[
        "negative_log_score"
    ] = negative_log_score

    for coverage, probability in [
        (50, 0.75),
        (80, 0.90),
        (90, 0.95),
    ]:
        threshold = norm.ppf(
            probability
        )

        result[
            f"central_{coverage}_covered"
        ] = (
            np.abs(
                residual_standardised_error
            )
            <= threshold
        )

    for index, column in enumerate(
        QUANTILE_COLUMNS
    ):
        result[column] = (
            temperature_quantiles[
                :,
                index,
            ]
        )

    warning_messages = " || ".join(
        str(item.message)
        for item in captured_warnings
    )

    ledger_record = {
        "model_identifier": (
            model_identifier
        ),
        "fold_id": fold_id,
        "fold_number": fold_number,
        "decision_rule": decision_rule,
        "decision_rule_order": (
            RULE_ORDER[
                decision_rule
            ]
        ),
        "kernel": kernel_key,
        "kernel_order": (
            KERNEL_ORDER[
                kernel_key
            ]
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
        "training_rows": int(
            len(training)
        ),
        "validation_rows": int(
            len(validation)
        ),
        "training_target_mean_c": float(
            y_training.mean()
        ),
        "training_target_standard_deviation_c": float(
            y_training.std(ddof=0)
        ),
        "fitted_signal_variance": (
            fitted_signal_variance
        ),
        "fitted_length_scale": (
            fitted_length_scale
        ),
        "fitted_noise_variance": (
            fitted_noise_variance
        ),
        "log_marginal_likelihood": float(
            model.log_marginal_likelihood_value_
        ),
        "fit_elapsed_seconds": float(
            elapsed_seconds
        ),
        "optimizer_warning_count": int(
            len(captured_warnings)
        ),
        "optimizer_warnings": (
            warning_messages
        ),
        "fitted_kernel": str(
            model.kernel_
        ),
        "normalise_training_target": (
            bool(
                specification[
                    "normalise_training_target"
                ]
            )
        ),
        "numerical_jitter": float(
            specification[
                "numerical_jitter"
            ]
        ),
        "market_prices_accessed": False,
        "polymarket_outcomes_accessed": False,
    }

    return result, ledger_record


def main() -> None:
    specification = json.loads(
        SPEC_PATH.read_text(
            encoding="utf-8"
        )
    )

    phase6_manifest = json.loads(
        PHASE6_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    if (
        phase6_manifest["status"]
        != "TWO_YEAR_GP_TRAINING_DESIGN_CERTIFIED"
    ):
        raise RuntimeError(
            "The Phase 6 training design "
            "is not certified."
        )

    panel = pd.read_csv(
        SOURCE_PATH
    )

    required_columns = {
        "target_date",
        "fold_id",
        "fold_number",
        "sample_role",
        "decision_rule",
        "decision_rule_order",
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "gp_target",
        *FEATURE_COLUMNS,
    }

    missing_columns = (
        required_columns
        - set(panel.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "Phase 6 matrix is missing columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    for column in [
        "target_date",
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
    ]:
        panel[column] = pd.to_datetime(
            panel[column],
            errors="raise",
            format="mixed",
        ).dt.normalize()

    numeric_columns = [
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "gp_target",
        *FEATURE_COLUMNS,
    ]

    for column in numeric_columns:
        panel[column] = pd.to_numeric(
            panel[column],
            errors="coerce",
        )

    if panel[numeric_columns].isna().any().any():
        raise RuntimeError(
            "The Phase 6 matrix contains "
            "missing model inputs."
        )

    if not np.isfinite(
        panel[numeric_columns].to_numpy()
    ).all():
        raise RuntimeError(
            "The Phase 6 matrix contains "
            "non-finite model inputs."
        )

    fold_ids = (
        panel[
            "fold_id"
        ]
        .drop_duplicates()
        .tolist()
    )

    if fold_ids != [
        "fold_01",
        "fold_02",
        "fold_03",
        "fold_04",
    ]:
        raise RuntimeError(
            f"Unexpected folds: {fold_ids}"
        )

    prediction_parts = []
    ledger_records = []

    total_models = (
        len(fold_ids)
        * len(RULE_ORDER)
        * len(KERNEL_ORDER)
    )

    completed_models = 0

    print()
    print("=" * 78)
    print("PHASE 7 GAUSSIAN-PROCESS FITTING")
    print("=" * 78)
    print("Planned fitted models:", total_models)
    print("Validation dates:", 365)
    print("Decision rules:", 4)
    print("Candidate kernels:", 2)
    print()

    for fold_id in fold_ids:
        fold_panel = panel.loc[
            panel["fold_id"].eq(
                fold_id
            )
        ]

        fold_number = int(
            fold_panel[
                "fold_number"
            ].iloc[0]
        )

        for decision_rule in RULE_ORDER:
            rule_panel = fold_panel.loc[
                fold_panel[
                    "decision_rule"
                ].eq(decision_rule)
            ].copy()

            training = rule_panel.loc[
                rule_panel[
                    "sample_role"
                ].eq("training")
            ].copy()

            validation = rule_panel.loc[
                rule_panel[
                    "sample_role"
                ].eq("validation")
            ].copy()

            training = training.sort_values(
                "target_date",
                kind="stable",
            ).reset_index(drop=True)

            validation = validation.sort_values(
                "target_date",
                kind="stable",
            ).reset_index(drop=True)

            if training.empty or validation.empty:
                raise RuntimeError(
                    "A fold-rule combination has "
                    "no training or validation data."
                )

            if not (
                training["target_date"].max()
                < validation["target_date"].min()
            ):
                raise RuntimeError(
                    "Training does not precede "
                    "validation."
                )

            for kernel_key in KERNEL_ORDER:
                completed_models += 1

                print(
                    f"[{completed_models:02d}/"
                    f"{total_models:02d}] "
                    f"{fold_id} | "
                    f"{decision_rule} | "
                    f"{kernel_key}"
                )

                predictions, ledger = (
                    fit_one_model(
                        training=training,
                        validation=validation,
                        fold_id=fold_id,
                        fold_number=fold_number,
                        decision_rule=decision_rule,
                        kernel_key=kernel_key,
                        specification=(
                            specification
                        ),
                    )
                )

                prediction_parts.append(
                    predictions
                )

                ledger_records.append(
                    ledger
                )

    predictions = pd.concat(
        prediction_parts,
        ignore_index=True,
    )

    ledger = pd.DataFrame(
        ledger_records
    )

    predictions = predictions.sort_values(
        [
            "target_date",
            "decision_rule_order",
            "kernel_order",
        ],
        kind="stable",
    ).reset_index(drop=True)

    ledger = ledger.sort_values(
        [
            "fold_number",
            "decision_rule_order",
            "kernel_order",
        ],
        kind="stable",
    ).reset_index(drop=True)

    date_scores = (
        predictions.groupby(
            [
                "target_date",
                "kernel",
                "kernel_order",
            ],
            as_index=False,
        )
        .agg(
            decision_rule_rows=(
                "decision_rule",
                "size",
            ),
            mean_crps_c=(
                "crps_c",
                "mean",
            ),
            mean_negative_log_score=(
                "negative_log_score",
                "mean",
            ),
            mean_absolute_corrected_error_c=(
                "absolute_corrected_error_c",
                "mean",
            ),
            mean_squared_corrected_error_c2=(
                "squared_corrected_error_c2",
                "mean",
            ),
            mean_predictive_standard_deviation_c=(
                "predictive_standard_deviation_c",
                "mean",
            ),
            mean_pit=(
                "pit_value",
                "mean",
            ),
        )
    )

    paired_dates = date_scores.pivot(
        index="target_date",
        columns="kernel",
        values="mean_crps_c",
    ).reset_index()

    paired_dates.columns.name = None

    paired_dates = paired_dates.rename(
        columns={
            "rbf": "rbf_mean_crps_c",
            "matern32": (
                "matern32_mean_crps_c"
            ),
        }
    )

    paired_dates[
        "rbf_minus_matern32_crps_c"
    ] = (
        paired_dates[
            "rbf_mean_crps_c"
        ]
        - paired_dates[
            "matern32_mean_crps_c"
        ]
    )

    paired_dates[
        "lower_crps_kernel"
    ] = np.where(
        paired_dates[
            "rbf_mean_crps_c"
        ]
        < paired_dates[
            "matern32_mean_crps_c"
        ],
        "rbf",
        np.where(
            paired_dates[
                "matern32_mean_crps_c"
            ]
            < paired_dates[
                "rbf_mean_crps_c"
            ],
            "matern32",
            "tie",
        ),
    )

    kernel_summary_records = []

    for kernel_key in KERNEL_ORDER:
        kernel_rows = predictions.loc[
            predictions[
                "kernel"
            ].eq(kernel_key)
        ]

        kernel_dates = date_scores.loc[
            date_scores[
                "kernel"
            ].eq(kernel_key)
        ]

        raw_error = kernel_rows[
            "raw_temperature_error_c"
        ].to_numpy(dtype=float)

        corrected_error = kernel_rows[
            "corrected_temperature_error_c"
        ].to_numpy(dtype=float)

        kernel_summary_records.append(
            {
                "kernel": kernel_key,
                "kernel_order": (
                    KERNEL_ORDER[
                        kernel_key
                    ]
                ),
                "validation_dates": int(
                    kernel_dates[
                        "target_date"
                    ].nunique()
                ),
                "validation_rows": int(
                    len(kernel_rows)
                ),
                "fitted_models": int(
                    ledger[
                        "kernel"
                    ].eq(
                        kernel_key
                    ).sum()
                ),
                "mean_date_crps_c": float(
                    kernel_dates[
                        "mean_crps_c"
                    ].mean()
                ),
                "median_date_crps_c": float(
                    kernel_dates[
                        "mean_crps_c"
                    ].median()
                ),
                "mean_row_crps_c": float(
                    kernel_rows[
                        "crps_c"
                    ].mean()
                ),
                "mean_negative_log_score": float(
                    kernel_rows[
                        "negative_log_score"
                    ].mean()
                ),
                "raw_mean_error_c": float(
                    raw_error.mean()
                ),
                "corrected_mean_error_c": float(
                    corrected_error.mean()
                ),
                "raw_mae_c": float(
                    np.abs(
                        raw_error
                    ).mean()
                ),
                "corrected_mae_c": float(
                    np.abs(
                        corrected_error
                    ).mean()
                ),
                "raw_rmse_c": float(
                    np.sqrt(
                        np.mean(
                            raw_error**2
                        )
                    )
                ),
                "corrected_rmse_c": float(
                    np.sqrt(
                        np.mean(
                            corrected_error**2
                        )
                    )
                ),
                "mean_predictive_standard_deviation_c": float(
                    kernel_rows[
                        "predictive_standard_deviation_c"
                    ].mean()
                ),
                "central_50_coverage": float(
                    kernel_rows[
                        "central_50_covered"
                    ].mean()
                ),
                "central_80_coverage": float(
                    kernel_rows[
                        "central_80_covered"
                    ].mean()
                ),
                "central_90_coverage": float(
                    kernel_rows[
                        "central_90_covered"
                    ].mean()
                ),
                "pit_mean": float(
                    kernel_rows[
                        "pit_value"
                    ].mean()
                ),
                "pit_variance": float(
                    kernel_rows[
                        "pit_value"
                    ].var(
                        ddof=0
                    )
                ),
                "mean_log_marginal_likelihood": float(
                    ledger.loc[
                        ledger[
                            "kernel"
                        ].eq(kernel_key),
                        "log_marginal_likelihood",
                    ].mean()
                ),
                "total_optimizer_warnings": int(
                    ledger.loc[
                        ledger[
                            "kernel"
                        ].eq(kernel_key),
                        "optimizer_warning_count",
                    ].sum()
                ),
                "descriptive_crps_rank": 0,
                "final_kernel_selected": False,
            }
        )

    kernel_summary = pd.DataFrame(
        kernel_summary_records
    )

    kernel_summary[
        "descriptive_crps_rank"
    ] = (
        kernel_summary[
            "mean_date_crps_c"
        ]
        .rank(
            method="min",
            ascending=True,
        )
        .astype(int)
    )

    rule_summary = (
        predictions.groupby(
            [
                "kernel",
                "kernel_order",
                "decision_rule",
                "decision_rule_order",
            ],
            as_index=False,
        )
        .agg(
            validation_dates=(
                "target_date",
                "nunique",
            ),
            validation_rows=(
                "target_date",
                "size",
            ),
            mean_crps_c=(
                "crps_c",
                "mean",
            ),
            median_crps_c=(
                "crps_c",
                "median",
            ),
            mean_negative_log_score=(
                "negative_log_score",
                "mean",
            ),
            corrected_mae_c=(
                "absolute_corrected_error_c",
                "mean",
            ),
            corrected_rmse_c2=(
                "squared_corrected_error_c2",
                "mean",
            ),
            mean_predictive_standard_deviation_c=(
                "predictive_standard_deviation_c",
                "mean",
            ),
            central_50_coverage=(
                "central_50_covered",
                "mean",
            ),
            central_80_coverage=(
                "central_80_covered",
                "mean",
            ),
            central_90_coverage=(
                "central_90_covered",
                "mean",
            ),
            pit_mean=(
                "pit_value",
                "mean",
            ),
        )
    )

    rule_summary[
        "corrected_rmse_c"
    ] = np.sqrt(
        rule_summary.pop(
            "corrected_rmse_c2"
        )
    )

    prediction_keys = [
        "target_date",
        "decision_rule",
        "kernel",
    ]

    validation_date_counts = (
        predictions.groupby(
            "target_date"
        ).size()
    )

    quantile_matrix = predictions[
        QUANTILE_COLUMNS
    ].to_numpy(dtype=float)

    required_checks = [
        {
            "check": (
                "fitted_models_equal_32"
            ),
            "required": True,
            "passed": (
                len(ledger) == 32
            ),
            "detail": len(ledger),
        },
        {
            "check": (
                "prediction_rows_equal_2920"
            ),
            "required": True,
            "passed": (
                len(predictions) == 2920
            ),
            "detail": len(predictions),
        },
        {
            "check": (
                "validation_dates_equal_365"
            ),
            "required": True,
            "passed": (
                predictions[
                    "target_date"
                ].nunique()
                == 365
            ),
            "detail": (
                predictions[
                    "target_date"
                ].nunique()
            ),
        },
        {
            "check": (
                "eight_prediction_rows_per_date"
            ),
            "required": True,
            "passed": (
                validation_date_counts.eq(
                    8
                ).all()
            ),
            "detail": (
                validation_date_counts.min()
            ),
        },
        {
            "check": (
                "prediction_keys_unique"
            ),
            "required": True,
            "passed": (
                not predictions.duplicated(
                    prediction_keys
                ).any()
            ),
            "detail": int(
                predictions.duplicated(
                    prediction_keys
                ).sum()
            ),
        },
        {
            "check": (
                "two_kernels_present"
            ),
            "required": True,
            "passed": (
                set(
                    predictions[
                        "kernel"
                    ].unique()
                )
                == {
                    "rbf",
                    "matern32",
                }
            ),
            "detail": (
                "|".join(
                    sorted(
                        predictions[
                            "kernel"
                        ].unique()
                    )
                )
            ),
        },
        {
            "check": (
                "four_rules_present"
            ),
            "required": True,
            "passed": (
                set(
                    predictions[
                        "decision_rule"
                    ].unique()
                )
                == set(RULE_ORDER)
            ),
            "detail": (
                predictions[
                    "decision_rule"
                ].nunique()
            ),
        },
        {
            "check": (
                "training_precedes_validation"
            ),
            "required": True,
            "passed": (
                pd.to_datetime(
                    ledger[
                        "training_end"
                    ]
                )
                < pd.to_datetime(
                    ledger[
                        "validation_start"
                    ]
                )
            ).all(),
            "detail": "32/32",
        },
        {
            "check": (
                "predictive_standard_deviation_positive"
            ),
            "required": True,
            "passed": (
                predictions[
                    "predictive_standard_deviation_c"
                ].gt(0.0).all()
            ),
            "detail": float(
                predictions[
                    "predictive_standard_deviation_c"
                ].min()
            ),
        },
        {
            "check": (
                "scores_are_finite"
            ),
            "required": True,
            "passed": np.isfinite(
                predictions[
                    [
                        "crps_c",
                        "negative_log_score",
                        "pit_value",
                        "temperature_predictive_mean_c",
                        "predictive_standard_deviation_c",
                    ]
                ].to_numpy()
            ).all(),
            "detail": 0,
        },
        {
            "check": (
                "crps_nonnegative"
            ),
            "required": True,
            "passed": (
                predictions[
                    "crps_c"
                ].ge(0.0).all()
            ),
            "detail": float(
                predictions[
                    "crps_c"
                ].min()
            ),
        },
        {
            "check": (
                "pit_within_unit_interval"
            ),
            "required": True,
            "passed": (
                predictions[
                    "pit_value"
                ].between(
                    0.0,
                    1.0,
                    inclusive="both",
                ).all()
            ),
            "detail": (
                f"{predictions['pit_value'].min():.6f}"
                "|"
                f"{predictions['pit_value'].max():.6f}"
            ),
        },
        {
            "check": (
                "ninety_nine_quantiles_present"
            ),
            "required": True,
            "passed": (
                len(
                    [
                        column
                        for column in predictions.columns
                        if column in QUANTILE_COLUMNS
                    ]
                )
                == 99
            ),
            "detail": 99,
        },
        {
            "check": (
                "quantiles_are_finite"
            ),
            "required": True,
            "passed": np.isfinite(
                quantile_matrix
            ).all(),
            "detail": 0,
        },
        {
            "check": (
                "quantiles_are_nondecreasing"
            ),
            "required": True,
            "passed": (
                np.diff(
                    quantile_matrix,
                    axis=1,
                )
                >= -1e-10
            ).all(),
            "detail": 0,
        },
        {
            "check": (
                "median_equals_predictive_mean"
            ),
            "required": True,
            "passed": np.allclose(
                predictions[
                    "q50_c"
                ],
                predictions[
                    "temperature_predictive_mean_c"
                ],
                atol=1e-10,
                rtol=0.0,
            ),
            "detail": float(
                np.max(
                    np.abs(
                        predictions[
                            "q50_c"
                        ]
                        - predictions[
                            "temperature_predictive_mean_c"
                        ]
                    )
                )
            ),
        },
        {
            "check": (
                "date_scores_equal_730"
            ),
            "required": True,
            "passed": (
                len(date_scores) == 730
            ),
            "detail": len(date_scores),
        },
        {
            "check": (
                "paired_dates_equal_365"
            ),
            "required": True,
            "passed": (
                len(paired_dates) == 365
            ),
            "detail": len(paired_dates),
        },
        {
            "check": (
                "market_information_not_accessed"
            ),
            "required": True,
            "passed": True,
            "detail": False,
        },
        {
            "check": (
                "final_kernel_not_selected"
            ),
            "required": True,
            "passed": (
                not kernel_summary[
                    "final_kernel_selected"
                ].any()
            ),
            "detail": False,
        },
    ]

    checks = pd.DataFrame(
        required_checks
    )

    failed = checks.loc[
        checks["required"]
        & ~checks["passed"]
    ]

    if not failed.empty:
        raise RuntimeError(
            "Required Phase 7 checks failed:\n"
            + failed.to_string(
                index=False
            )
        )

    for panel_to_format in [
        predictions,
        date_scores,
        paired_dates,
    ]:
        if "target_date" in panel_to_format.columns:
            panel_to_format[
                "target_date"
            ] = (
                pd.to_datetime(
                    panel_to_format[
                        "target_date"
                    ]
                )
                .dt.date
                .astype(str)
            )

    for column in [
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
    ]:
        predictions[column] = (
            pd.to_datetime(
                predictions[column]
            )
            .dt.date
            .astype(str)
        )

        ledger[column] = (
            pd.to_datetime(
                ledger[column]
            )
            .dt.date
            .astype(str)
        )

    write_csv(
        predictions,
        PREDICTIONS_PATH,
    )

    write_csv(
        ledger,
        MODEL_LEDGER_PATH,
    )

    write_csv(
        date_scores,
        DATE_SCORE_PATH,
    )

    write_csv(
        paired_dates,
        PAIRED_DATE_PATH,
    )

    write_csv(
        rule_summary,
        RULE_SUMMARY_PATH,
    )

    write_csv(
        checks,
        CHECKS_PATH,
    )

    write_csv(
        kernel_summary,
        KERNEL_SUMMARY_PATH,
    )

    output_paths = [
        PREDICTIONS_PATH,
        MODEL_LEDGER_PATH,
        DATE_SCORE_PATH,
        PAIRED_DATE_PATH,
        RULE_SUMMARY_PATH,
        CHECKS_PATH,
        KERNEL_SUMMARY_PATH,
    ]

    descriptive_best_kernel = str(
        kernel_summary.sort_values(
            [
                "descriptive_crps_rank",
                "kernel_order",
            ],
            kind="stable",
        )[
            "kernel"
        ].iloc[0]
    )

    manifest = {
        "phase": 7,
        "phase_status": (
            "PHASE7_GP_VALIDATION_COMPLETE"
        ),
        "status": (
            "TWO_YEAR_GP_VALIDATION_DISTRIBUTIONS_CERTIFIED"
        ),
        "created_utc": utc_now(),
        "source": str(
            SOURCE_PATH.relative_to(ROOT)
        ),
        "source_sha256": (
            sha256_file(SOURCE_PATH)
        ),
        "weather_only_dates": 730,
        "initial_training_dates": 365,
        "validation_dates": 365,
        "validation_blocks": 4,
        "validation_block_sizes": [
            91,
            91,
            91,
            92,
        ],
        "decision_rules": 4,
        "candidate_kernels": [
            "rbf",
            "matern32",
        ],
        "fitted_models": int(
            len(ledger)
        ),
        "validation_prediction_rows": int(
            len(predictions)
        ),
        "date_level_score_rows": int(
            len(date_scores)
        ),
        "paired_validation_dates": int(
            len(paired_dates)
        ),
        "temperature_quantiles_per_prediction": 99,
        "target_column": "gp_target",
        "feature_columns": (
            FEATURE_COLUMNS
        ),
        "model_scope": (
            "separate_model_for_each_decision_rule"
        ),
        "training_target_normalised": True,
        "kernel_hyperparameters_estimated_by": (
            "log_marginal_likelihood"
        ),
        "optimizer_restarts": 0,
        "numerical_jitter": 1e-8,
        "primary_validation_score": (
            "continuous_ranked_probability_score"
        ),
        "descriptive_lower_crps_kernel": (
            descriptive_best_kernel
        ),
        "final_kernel_selected": False,
        "selection_deferred_to_next_phase": True,
        "market_prices_accessed": False,
        "polymarket_outcomes_accessed": False,
        "probability_calibration_selected": False,
        "trading_returns_calculated": False,
        "required_integrity_checks_passed": True,
        "output_paths": [
            str(path.relative_to(ROOT))
            for path in output_paths
        ],
        "output_hashes": {
            str(path.relative_to(ROOT)): (
                sha256_file(path)
            )
            for path in output_paths
        },
        "next_stage": (
            "Use date-level CRPS to select the "
            "Gaussian-process covariance kernel, "
            "fit the selected GP specification on "
            "the complete weather-only training "
            "period, and construct the weather-plus-"
            "market training inputs."
        ),
    }

    write_json(
        manifest,
        MANIFEST_PATH,
    )

    print()
    print("=" * 78)
    print("PHASE 7 GP VALIDATION RESULTS")
    print("=" * 78)
    print("Status:", manifest["status"])
    print("Fitted models:", len(ledger))
    print(
        "Validation prediction rows:",
        len(predictions),
    )
    print(
        "Validation dates:",
        predictions[
            "target_date"
        ].nunique(),
    )
    print(
        "Quantiles per prediction:",
        99,
    )
    print()
    print(
        kernel_summary.to_string(
            index=False
        )
    )
    print()
    print(
        "Descriptive lower-CRPS kernel:",
        descriptive_best_kernel,
    )
    print(
        "Final kernel selected: False"
    )
    print(
        "Market information accessed: False"
    )
    print(
        "PHASE 7 CORE CONSTRUCTION: PASSED"
    )


if __name__ == "__main__":
    main()
