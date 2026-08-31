from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import warnings

from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scipy import stats
from scipy.stats import norm

from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (
    ConstantKernel,
    Matern,
    RBF,
    WhiteKernel,
)
from sklearn.preprocessing import StandardScaler


# =============================================================================
# FROZEN DESIGN
# =============================================================================

WEATHER_START = pd.Timestamp("2024-03-16")
INITIAL_TRAIN_END = pd.Timestamp("2025-03-15")
VALIDATION_START = pd.Timestamp("2025-03-16")
WEATHER_END = pd.Timestamp("2026-03-15")

MARKET_START = pd.Timestamp("2026-03-16")
DEVELOPMENT_END = pd.Timestamp("2026-06-30")
EXTERNAL_START = pd.Timestamp("2026-07-01")
FINAL_END = pd.Timestamp("2026-08-31")

RULE_ORDER = [
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
]

BLOCK_SIZES = [91, 91, 91, 92]

FEATURE_COLUMNS = [
    "calendar_time_years",
    "seasonal_sin_exact",
    "seasonal_cos_exact",
    "forecast_daily_max_c",
]

KERNELS = [
    "rbf",
    "matern32",
]

JITTER = 1e-8

CONSTANT_INITIAL = 1.0
CONSTANT_BOUNDS = (1e-2, 1e2)

LENGTH_INITIAL = 1.0
LENGTH_BOUNDS = (0.05, 10.0)

NOISE_INITIAL = 0.25
NOISE_BOUNDS = (1e-3, 10.0)

RANDOM_STATE = 20260721
BOOTSTRAP_SEED = 20260731
BOOTSTRAP_REPS = 10000

MOVING_BLOCK_LENGTHS = [3, 5, 7]

INTERVAL_LEVELS = [
    0.50,
    0.80,
    0.90,
    0.95,
]


# =============================================================================
# PATHS
# =============================================================================

MASTER_PANEL = Path(
    "data/processed/final_pipeline/"
    "weather_residual_panel.csv"
)

RESIDUAL_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "residual_panel_summary.json"
)

PROCESSED_DIR = Path(
    "data/processed/final_pipeline/"
    "weather_models"
)

OUTPUT_DIR = Path(
    "outputs/final_pipeline/weather/models"
)

AUDIT_DIR = Path(
    "outputs/final_pipeline/audit"
)

VALIDATION_PANEL = (
    PROCESSED_DIR
    / "chronological_validation_predictions.csv"
)

DATE_LOSSES = (
    PROCESSED_DIR
    / "chronological_validation_date_losses.csv"
)

FULL_PERIOD_PREDICTIONS = (
    PROCESSED_DIR
    / "frozen_weather_model_predictions_mar_aug.csv"
)

FIT_LEDGER = (
    OUTPUT_DIR
    / "gp_fit_ledger.csv"
)

ATTRIBUTION_SUMMARY = (
    OUTPUT_DIR
    / "weather_model_attribution_summary.csv"
)

RULE_BLOCK_SUMMARY = (
    OUTPUT_DIR
    / "weather_model_rule_block_crps.csv"
)

BOOTSTRAP_SUMMARY = (
    OUTPUT_DIR
    / "weather_model_bootstrap_intervals.csv"
)

RULE_INFERENCE = (
    OUTPUT_DIR
    / "decision_rule_pairwise_inference.csv"
)

COVERAGE_SUMMARY = (
    OUTPUT_DIR
    / "selected_gp_coverage_summary.csv"
)

RESIDUAL_DIAGNOSTICS = (
    OUTPUT_DIR
    / "selected_gp_standardised_residual_diagnostics.csv"
)

FULL_FIT_LEDGER = (
    OUTPUT_DIR
    / "full_history_fit_ledger.csv"
)

MARKET_SCORE_SUMMARY = (
    OUTPUT_DIR
    / "frozen_weather_model_continuous_scores.csv"
)

SELECTION_JSON = (
    OUTPUT_DIR
    / "weather_kernel_selection.json"
)

VARIANCE_AUDIT_JSON = (
    AUDIT_DIR
    / "gp_predictive_variance_audit.json"
)

SUMMARY_JSON = (
    AUDIT_DIR
    / "weather_models_summary.json"
)

CHECKS_CSV = (
    AUDIT_DIR
    / "weather_models_integrity_checks.csv"
)

ATTRIBUTION_FIGURE = (
    OUTPUT_DIR
    / "chronological_crps_attribution.png"
)

BLOCK_FIGURE = (
    OUTPUT_DIR
    / "chronological_block_crps.png"
)

PIT_FIGURE = (
    OUTPUT_DIR
    / "selected_gp_pit_histogram.png"
)

QQ_FIGURE = (
    OUTPUT_DIR
    / "selected_gp_normal_qq.png"
)

COVERAGE_FIGURE = (
    OUTPUT_DIR
    / "selected_gp_coverage.png"
)


# =============================================================================
# UTILITIES
# =============================================================================


def sha256_file(
    path: Path,
) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def parse_bool(
    series: pd.Series,
) -> pd.Series:
    if series.dtype == bool:
        return series

    mapping = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
    }

    out = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map(mapping)
    )

    if out.isna().any():
        raise RuntimeError(
            "Unable to parse boolean column."
        )

    return out.astype(bool)


def gaussian_crps(
    y,
    mu,
    sigma,
):
    y = np.asarray(
        y,
        dtype=float,
    )

    mu = np.asarray(
        mu,
        dtype=float,
    )

    sigma = np.asarray(
        sigma,
        dtype=float,
    )

    if np.any(
        sigma <= 0
    ):
        raise RuntimeError(
            "Gaussian CRPS received non-positive sigma."
        )

    z = (
        y - mu
    ) / sigma

    return sigma * (
        z
        * (
            2.0
            * norm.cdf(z)
            - 1.0
        )
        + 2.0
        * norm.pdf(z)
        - 1.0
        / math.sqrt(
            math.pi
        )
    )


def exact_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    d = pd.to_datetime(
        df["target_date"]
    )

    calendar_time_years = (
        (
            d
            - WEATHER_START
        ).dt.days
        / 365.2425
    )

    seasonal_position = (
        d.dt.dayofyear
        - 1
    ) / 365.2425

    result = pd.DataFrame(
        {
            "calendar_time_years":
                calendar_time_years,

            "seasonal_sin_exact":
                np.sin(
                    2.0
                    * np.pi
                    * seasonal_position
                ),

            "seasonal_cos_exact":
                np.cos(
                    2.0
                    * np.pi
                    * seasonal_position
                ),

            "forecast_daily_max_c":
                pd.to_numeric(
                    df[
                        "forecast_daily_max_c"
                    ],
                    errors="raise",
                ),
        },
        index=df.index,
    )

    return result


def extract_gp_parameters(
    gpr,
):
    fitted = gpr.kernel_

    signal = fitted.k1
    white = fitted.k2

    constant = float(
        signal.k1.constant_value
    )

    length_scale = float(
        np.asarray(
            signal.k2.length_scale
        ).reshape(-1)[0]
    )

    noise = float(
        white.noise_level
    )

    return {
        "signal_variance":
            constant,

        "signal_std":
            math.sqrt(
                constant
            ),

        "length_scale":
            length_scale,

        "white_noise_variance":
            noise,
    }


def close_to_bound(
    value,
    lower,
    upper,
    relative_tol=0.01,
):
    lower_near = (
        value
        <= lower
        * (
            1.0
            + relative_tol
        )
    )

    upper_near = (
        value
        >= upper
        * (
            1.0
            - relative_tol
        )
    )

    return bool(
        lower_near
        or upper_near
    )


def make_kernel(
    family: str,
):
    if family == "rbf":
        covariance = RBF(
            length_scale=
                LENGTH_INITIAL,

            length_scale_bounds=
                LENGTH_BOUNDS,
        )

    elif family == "matern32":
        covariance = Matern(
            length_scale=
                LENGTH_INITIAL,

            length_scale_bounds=
                LENGTH_BOUNDS,

            nu=1.5,
        )

    else:
        raise ValueError(
            family
        )

    return (
        ConstantKernel(
            constant_value=
                CONSTANT_INITIAL,

            constant_value_bounds=
                CONSTANT_BOUNDS,
        )
        * covariance
        + WhiteKernel(
            noise_level=
                NOISE_INITIAL,

            noise_level_bounds=
                NOISE_BOUNDS,
        )
    )


# =============================================================================
# GP FITTING
# =============================================================================


def fit_gp(
    train: pd.DataFrame,
    family: str,
):
    if len(train) < 50:
        raise RuntimeError(
            "GP training sample unexpectedly small."
        )

    X_raw = exact_features(
        train
    )[FEATURE_COLUMNS].to_numpy(
        dtype=float
    )

    y = train[
        "residual_c"
    ].to_numpy(
        dtype=float
    )

    x_scaler = StandardScaler(
        with_mean=True,
        with_std=True,
    )

    X = x_scaler.fit_transform(
        X_raw
    )

    y_mean = float(
        np.mean(y)
    )

    y_scale = float(
        np.std(
            y,
            ddof=0,
        )
    )

    if not np.isfinite(
        y_scale
    ) or y_scale <= 0:
        raise RuntimeError(
            "Invalid response scale."
        )

    y_std = (
        y - y_mean
    ) / y_scale

    kernel = make_kernel(
        family
    )

    gpr = GaussianProcessRegressor(
        kernel=kernel,
        alpha=JITTER,
        optimizer="fmin_l_bfgs_b",
        n_restarts_optimizer=0,
        normalize_y=False,
        random_state=
            RANDOM_STATE,
    )

    warning_messages = []

    with warnings.catch_warnings(
        record=True
    ) as caught:

        warnings.simplefilter(
            "always"
        )

        gpr.fit(
            X,
            y_std,
        )

        for w in caught:
            warning_messages.append(
                str(
                    w.message
                )
            )

    params = extract_gp_parameters(
        gpr
    )

    params[
        "constant_near_bound"
    ] = close_to_bound(
        params[
            "signal_variance"
        ],
        CONSTANT_BOUNDS[0],
        CONSTANT_BOUNDS[1],
    )

    params[
        "length_near_bound"
    ] = close_to_bound(
        params[
            "length_scale"
        ],
        LENGTH_BOUNDS[0],
        LENGTH_BOUNDS[1],
    )

    params[
        "noise_near_bound"
    ] = close_to_bound(
        params[
            "white_noise_variance"
        ],
        NOISE_BOUNDS[0],
        NOISE_BOUNDS[1],
    )

    return {
        "family":
            family,

        "x_scaler":
            x_scaler,

        "y_mean":
            y_mean,

        "y_scale":
            y_scale,

        "gpr":
            gpr,

        "X_train_scaled":
            X,

        "parameters":
            params,

        "log_marginal_likelihood":
            float(
                gpr.log_marginal_likelihood_value_
            ),

        "warnings":
            warning_messages,
    }


def gp_predict(
    bundle,
    test: pd.DataFrame,
):
    X_raw = exact_features(
        test
    )[FEATURE_COLUMNS].to_numpy(
        dtype=float
    )

    X = bundle[
        "x_scaler"
    ].transform(
        X_raw
    )

    (
        mean_std,
        sd_std,
    ) = bundle[
        "gpr"
    ].predict(
        X,
        return_std=True,
    )

    mean_residual = (
        bundle[
            "y_mean"
        ]
        + bundle[
            "y_scale"
        ]
        * mean_std
    )

    sd_residual = (
        bundle[
            "y_scale"
        ]
        * sd_std
    )

    settlement_mean = (
        test[
            "forecast_daily_max_c"
        ].to_numpy(
            dtype=float
        )
        + mean_residual
    )

    return {
        "X_scaled":
            X,

        "residual_mean_c":
            mean_residual,

        "residual_sd_c":
            sd_residual,

        "settlement_mean_c":
            settlement_mean,

        "settlement_sd_c":
            sd_residual,
    }


# =============================================================================
# STATIC GAUSSIAN
# =============================================================================


def static_parameters(
    train: pd.DataFrame,
):
    y = train[
        "residual_c"
    ].to_numpy(
        dtype=float
    )

    mean = float(
        np.mean(y)
    )

    # Gaussian MLE scale, matching the population-standardisation
    # convention used by StandardScaler.
    sd = float(
        np.std(
            y,
            ddof=0,
        )
    )

    if not np.isfinite(
        sd
    ) or sd <= 0:
        raise RuntimeError(
            "Invalid static Gaussian scale."
        )

    return (
        mean,
        sd,
    )


# =============================================================================
# DATA
# =============================================================================


def load_panel():
    if not MASTER_PANEL.exists():
        raise RuntimeError(
            f"Missing {MASTER_PANEL}"
        )

    panel = pd.read_csv(
        MASTER_PANEL
    )

    panel[
        "target_date"
    ] = pd.to_datetime(
        panel[
            "target_date"
        ]
    )

    panel[
        "residual_usable"
    ] = parse_bool(
        panel[
            "residual_usable"
        ]
    )

    panel[
        "support_available"
    ] = parse_bool(
        panel[
            "support_available"
        ]
    )

    panel[
        "hko_available"
    ] = parse_bool(
        panel[
            "hko_available"
        ]
    )

    return panel


def calendar_blocks():
    dates = pd.date_range(
        VALIDATION_START,
        WEATHER_END,
        freq="D",
    )

    if len(dates) != 365:
        raise RuntimeError(
            "Validation calendar must contain 365 dates."
        )

    blocks = []

    start = 0

    for i, size in enumerate(
        BLOCK_SIZES,
        start=1,
    ):
        subset = dates[
            start:
            start + size
        ]

        blocks.append(
            {
                "block":
                    i,

                "start":
                    subset[0],

                "end":
                    subset[-1],

                "calendar_dates":
                    len(subset),
            }
        )

        start += size

    if start != 365:
        raise RuntimeError(
            "Block partition does not total 365."
        )

    return blocks


# =============================================================================
# CHRONOLOGICAL VALIDATION
# =============================================================================


def validation_stage(
    panel: pd.DataFrame,
):
    weather = panel[
        (
            panel[
                "target_date"
            ]
            >= WEATHER_START
        )
        & (
            panel[
                "target_date"
            ]
            <= WEATHER_END
        )
        & panel[
            "residual_usable"
        ]
    ].copy()

    blocks = calendar_blocks()

    prediction_rows = []
    fit_rows = []
    fit_objects = {}

    for block in blocks:
        block_id = block[
            "block"
        ]

        block_start = block[
            "start"
        ]

        block_end = block[
            "end"
        ]

        for rule in RULE_ORDER:
            train = weather[
                (
                    weather[
                        "decision_rule"
                    ]
                    == rule
                )
                & (
                    weather[
                        "target_date"
                    ]
                    < block_start
                )
            ].copy()

            val = weather[
                (
                    weather[
                        "decision_rule"
                    ]
                    == rule
                )
                & (
                    weather[
                        "target_date"
                    ]
                    >= block_start
                )
                & (
                    weather[
                        "target_date"
                    ]
                    <= block_end
                )
            ].copy()

            train = train.sort_values(
                "target_date"
            )

            val = val.sort_values(
                "target_date"
            )

            if train.empty:
                raise RuntimeError(
                    f"No training data for {rule} block {block_id}"
                )

            static_mean, static_sd = (
                static_parameters(
                    train
                )
            )

            bundles = {}

            for family in KERNELS:
                bundle = fit_gp(
                    train,
                    family,
                )

                bundles[
                    family
                ] = bundle

                fit_objects[
                    (
                        block_id,
                        rule,
                        family,
                    )
                ] = bundle

                pars = bundle[
                    "parameters"
                ]

                fit_rows.append(
                    {
                        "fit_stage":
                            "chronological_validation",

                        "block":
                            block_id,

                        "decision_rule":
                            rule,

                        "kernel_family":
                            family,

                        "train_start":
                            train[
                                "target_date"
                            ].min().strftime(
                                "%Y-%m-%d"
                            ),

                        "train_end":
                            train[
                                "target_date"
                            ].max().strftime(
                                "%Y-%m-%d"
                            ),

                        "train_rows":
                            len(train),

                        "validation_start":
                            block_start.strftime(
                                "%Y-%m-%d"
                            ),

                        "validation_end":
                            block_end.strftime(
                                "%Y-%m-%d"
                            ),

                        "validation_calendar_dates":
                            block[
                                "calendar_dates"
                            ],

                        "validation_usable_rows":
                            len(val),

                        "response_mean_c":
                            bundle[
                                "y_mean"
                            ],

                        "response_scale_c":
                            bundle[
                                "y_scale"
                            ],

                        "feature_means":
                            json.dumps(
                                bundle[
                                    "x_scaler"
                                ].mean_.tolist()
                            ),

                        "feature_scales":
                            json.dumps(
                                bundle[
                                    "x_scaler"
                                ].scale_.tolist()
                            ),

                        "signal_variance":
                            pars[
                                "signal_variance"
                            ],

                        "signal_std":
                            pars[
                                "signal_std"
                            ],

                        "length_scale":
                            pars[
                                "length_scale"
                            ],

                        "white_noise_variance":
                            pars[
                                "white_noise_variance"
                            ],

                        "constant_near_bound":
                            pars[
                                "constant_near_bound"
                            ],

                        "length_near_bound":
                            pars[
                                "length_near_bound"
                            ],

                        "noise_near_bound":
                            pars[
                                "noise_near_bound"
                            ],

                        "log_marginal_likelihood":
                            bundle[
                                "log_marginal_likelihood"
                            ],

                        "warning_count":
                            len(
                                bundle[
                                    "warnings"
                                ]
                            ),

                        "warnings":
                            " || ".join(
                                bundle[
                                    "warnings"
                                ]
                            ),

                        "jitter":
                            JITTER,

                        "n_restarts_optimizer":
                            0,
                    }
                )

            if val.empty:
                continue

            rbf = gp_predict(
                bundles["rbf"],
                val,
            )

            matern = gp_predict(
                bundles["matern32"],
                val,
            )

            forecast = val[
                "forecast_daily_max_c"
            ].to_numpy(
                dtype=float
            )

            truth = val[
                "hko_daily_max_c"
            ].to_numpy(
                dtype=float
            )

            static_temp_mean = (
                forecast
                + static_mean
            )

            static_temp_sd = (
                np.full(
                    len(val),
                    static_sd,
                    dtype=float,
                )
            )

            raw_crps = np.abs(
                truth
                - forecast
            )

            static_crps = (
                gaussian_crps(
                    truth,
                    static_temp_mean,
                    static_temp_sd,
                )
            )

            rbf_crps = (
                gaussian_crps(
                    truth,
                    rbf[
                        "settlement_mean_c"
                    ],
                    rbf[
                        "settlement_sd_c"
                    ],
                )
            )

            matern_crps = (
                gaussian_crps(
                    truth,
                    matern[
                        "settlement_mean_c"
                    ],
                    matern[
                        "settlement_sd_c"
                    ],
                )
            )

            for i, (
                idx,
                source_row,
            ) in enumerate(
                val.iterrows()
            ):
                prediction_rows.append(
                    {
                        "target_date":
                            source_row[
                                "target_date"
                            ].strftime(
                                "%Y-%m-%d"
                            ),

                        "decision_rule":
                            rule,

                        "validation_block":
                            block_id,

                        "training_rows":
                            len(train),

                        "training_last_date":
                            train[
                                "target_date"
                            ].max().strftime(
                                "%Y-%m-%d"
                            ),

                        "forecast_daily_max_c":
                            forecast[i],

                        "hko_daily_max_c":
                            truth[i],

                        "residual_c":
                            source_row[
                                "residual_c"
                            ],

                        "raw_mean_c":
                            forecast[i],

                        "raw_crps_c":
                            raw_crps[i],

                        "static_residual_mean_c":
                            static_mean,

                        "static_residual_sd_c":
                            static_sd,

                        "static_mean_c":
                            static_temp_mean[i],

                        "static_sd_c":
                            static_temp_sd[i],

                        "static_crps_c":
                            static_crps[i],

                        "rbf_mean_c":
                            rbf[
                                "settlement_mean_c"
                            ][i],

                        "rbf_sd_c":
                            rbf[
                                "settlement_sd_c"
                            ][i],

                        "rbf_crps_c":
                            rbf_crps[i],

                        "rbf_z":
                            (
                                truth[i]
                                - rbf[
                                    "settlement_mean_c"
                                ][i]
                            )
                            / rbf[
                                "settlement_sd_c"
                            ][i],

                        "rbf_pit":
                            norm.cdf(
                                truth[i],
                                loc=rbf[
                                    "settlement_mean_c"
                                ][i],
                                scale=rbf[
                                    "settlement_sd_c"
                                ][i],
                            ),

                        "matern_mean_c":
                            matern[
                                "settlement_mean_c"
                            ][i],

                        "matern_sd_c":
                            matern[
                                "settlement_sd_c"
                            ][i],

                        "matern_crps_c":
                            matern_crps[i],

                        "matern_z":
                            (
                                truth[i]
                                - matern[
                                    "settlement_mean_c"
                                ][i]
                            )
                            / matern[
                                "settlement_sd_c"
                            ][i],

                        "matern_pit":
                            norm.cdf(
                                truth[i],
                                loc=matern[
                                    "settlement_mean_c"
                                ][i],
                                scale=matern[
                                    "settlement_sd_c"
                                ][i],
                            ),
                    }
                )

    predictions = pd.DataFrame(
        prediction_rows
    )

    fits = pd.DataFrame(
        fit_rows
    )

    return (
        predictions,
        fits,
        fit_objects,
        blocks,
    )


# =============================================================================
# DATE-BALANCED SCORING
# =============================================================================


def build_date_losses(
    predictions: pd.DataFrame,
):
    model_cols = {
        "raw":
            "raw_crps_c",

        "static":
            "static_crps_c",

        "rbf":
            "rbf_crps_c",

        "matern32":
            "matern_crps_c",
    }

    rows = []

    for target_date, x in (
        predictions.groupby(
            "target_date",
            sort=True,
        )
    ):
        row = {
            "target_date":
                target_date,

            "rules_available":
                int(
                    x[
                        "decision_rule"
                    ].nunique()
                ),

            "validation_block":
                int(
                    x[
                        "validation_block"
                    ].iloc[0]
                ),
        }

        for model, col in (
            model_cols.items()
        ):
            row[
                f"{model}_date_crps_c"
            ] = float(
                x[col].mean()
            )

        rows.append(row)

    return pd.DataFrame(
        rows
    )


def attribution_summary(
    date_losses: pd.DataFrame,
):
    means = {}

    for model in [
        "raw",
        "static",
        "rbf",
        "matern32",
    ]:
        means[model] = float(
            date_losses[
                f"{model}_date_crps_c"
            ].mean()
        )

    selected = min(
        ["rbf", "matern32"],
        key=lambda m:
            means[m],
    )

    raw_to_selected = (
        means["raw"]
        - means[selected]
    )

    if abs(
        raw_to_selected
    ) > 1e-12:
        raw_static_share = (
            (
                means["raw"]
                - means["static"]
            )
            / raw_to_selected
        )

        static_rbf_share = (
            (
                means["static"]
                - means["rbf"]
            )
            / raw_to_selected
        )

        rbf_matern_share = (
            (
                means["rbf"]
                - means["matern32"]
            )
            / raw_to_selected
        )

    else:
        raw_static_share = np.nan
        static_rbf_share = np.nan
        rbf_matern_share = np.nan

    rows = []

    for model in [
        "raw",
        "static",
        "rbf",
        "matern32",
    ]:
        rows.append(
            {
                "model":
                    model,

                "mean_date_crps_c":
                    means[model],

                "selected_gp":
                    model
                    == selected,
            }
        )

    return (
        pd.DataFrame(rows),
        selected,
        means,
        {
            "raw_static_share_of_raw_to_selected":
                raw_static_share,

            "static_rbf_share_of_raw_to_selected":
                static_rbf_share,

            "rbf_matern_share_of_raw_to_selected":
                rbf_matern_share,
        },
    )


def rule_block_summary(
    predictions,
):
    model_cols = {
        "raw":
            "raw_crps_c",

        "static":
            "static_crps_c",

        "rbf":
            "rbf_crps_c",

        "matern32":
            "matern_crps_c",
    }

    rows = []

    for (
        block,
        rule,
    ), x in predictions.groupby(
        [
            "validation_block",
            "decision_rule",
        ],
        sort=True,
    ):
        for model, col in (
            model_cols.items()
        ):
            rows.append(
                {
                    "validation_block":
                        int(block),

                    "decision_rule":
                        rule,

                    "model":
                        model,

                    "n":
                        int(len(x)),

                    "mean_crps_c":
                        float(
                            x[col].mean()
                        ),
                }
            )

    # Rule-only aggregate.
    for rule, x in predictions.groupby(
        "decision_rule",
        sort=True,
    ):
        for model, col in (
            model_cols.items()
        ):
            rows.append(
                {
                    "validation_block":
                        "ALL",

                    "decision_rule":
                        rule,

                    "model":
                        model,

                    "n":
                        int(len(x)),

                    "mean_crps_c":
                        float(
                            x[col].mean()
                        ),
                }
            )

    # Block-only date-balanced aggregate.
    date_losses = build_date_losses(
        predictions
    )

    for block, x in date_losses.groupby(
        "validation_block"
    ):
        for model in [
            "raw",
            "static",
            "rbf",
            "matern32",
        ]:
            rows.append(
                {
                    "validation_block":
                        int(block),

                    "decision_rule":
                        "DATE_BALANCED_ALL_RULES",

                    "model":
                        model,

                    "n":
                        int(len(x)),

                    "mean_crps_c":
                        float(
                            x[
                                f"{model}_date_crps_c"
                            ].mean()
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# BOOTSTRAP
# =============================================================================


def circular_block_indices(
    n,
    block_length,
    reps,
    rng,
):
    number_blocks = int(
        math.ceil(
            n
            / block_length
        )
    )

    starts = rng.integers(
        0,
        n,
        size=(
            reps,
            number_blocks,
        ),
    )

    offsets = np.arange(
        block_length
    )

    idx = (
        starts[
            :,
            :,
            None,
        ]
        + offsets[
            None,
            None,
            :,
        ]
    ) % n

    idx = idx.reshape(
        reps,
        -1,
    )

    return idx[
        :,
        :n,
    ]


def percentile_interval(
    x,
):
    return (
        float(
            np.quantile(
                x,
                0.025,
            )
        ),
        float(
            np.quantile(
                x,
                0.975,
            )
        ),
    )


def bootstrap_contrasts(
    date_losses,
    selected,
):
    ordered = date_losses.sort_values(
        "target_date"
    ).reset_index(
        drop=True
    )

    contrasts = {
        "static_minus_raw":
            (
                ordered[
                    "static_date_crps_c"
                ]
                - ordered[
                    "raw_date_crps_c"
                ]
            ).to_numpy(),

        "rbf_minus_static":
            (
                ordered[
                    "rbf_date_crps_c"
                ]
                - ordered[
                    "static_date_crps_c"
                ]
            ).to_numpy(),

        "matern_minus_static":
            (
                ordered[
                    "matern32_date_crps_c"
                ]
                - ordered[
                    "static_date_crps_c"
                ]
            ).to_numpy(),

        "matern_minus_rbf":
            (
                ordered[
                    "matern32_date_crps_c"
                ]
                - ordered[
                    "rbf_date_crps_c"
                ]
            ).to_numpy(),

        "selected_minus_static":
            (
                ordered[
                    f"{selected}_date_crps_c"
                ]
                - ordered[
                    "static_date_crps_c"
                ]
            ).to_numpy(),

        "selected_minus_raw":
            (
                ordered[
                    f"{selected}_date_crps_c"
                ]
                - ordered[
                    "raw_date_crps_c"
                ]
            ).to_numpy(),
    }

    n = len(
        ordered
    )

    rows = []

    rng = np.random.default_rng(
        BOOTSTRAP_SEED
    )

    ordinary_idx = rng.integers(
        0,
        n,
        size=(
            BOOTSTRAP_REPS,
            n,
        ),
    )

    for name, diff in (
        contrasts.items()
    ):
        boot = diff[
            ordinary_idx
        ].mean(
            axis=1
        )

        lower, upper = (
            percentile_interval(
                boot
            )
        )

        rows.append(
            {
                "contrast":
                    name,

                "bootstrap":
                    "ordinary_date",

                "block_length":
                    "",

                "n_dates":
                    n,

                "observed_mean_difference_c":
                    float(
                        np.mean(diff)
                    ),

                "lower_95_c":
                    lower,

                "upper_95_c":
                    upper,

                "replications":
                    BOOTSTRAP_REPS,

                "seed":
                    BOOTSTRAP_SEED,
            }
        )

    for b in MOVING_BLOCK_LENGTHS:
        rng_b = np.random.default_rng(
            BOOTSTRAP_SEED
            + b
        )

        idx = circular_block_indices(
            n,
            b,
            BOOTSTRAP_REPS,
            rng_b,
        )

        for name, diff in (
            contrasts.items()
        ):
            boot = diff[
                idx
            ].mean(
                axis=1
            )

            lower, upper = (
                percentile_interval(
                    boot
                )
            )

            rows.append(
                {
                    "contrast":
                        name,

                    "bootstrap":
                        "circular_moving_block",

                    "block_length":
                        b,

                    "n_dates":
                        n,

                    "observed_mean_difference_c":
                        float(
                            np.mean(diff)
                        ),

                    "lower_95_c":
                        lower,

                    "upper_95_c":
                        upper,

                    "replications":
                        BOOTSTRAP_REPS,

                    "seed":
                        BOOTSTRAP_SEED
                        + b,
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# RULE PAIRWISE INFERENCE
# =============================================================================


def pairwise_rule_inference(
    predictions,
    selected,
):
    # Kernel-family identifiers and prediction-column prefixes are
    # deliberately distinct:
    #
    #   rbf       -> rbf_crps_c
    #   matern32  -> matern_crps_c
    #
    # Never construct this column by string interpolation because
    # "matern32_crps_c" is not part of the certified output schema.
    selected_crps_columns = {
        "rbf": "rbf_crps_c",
        "matern32": "matern_crps_c",
    }

    if selected not in selected_crps_columns:
        raise RuntimeError(
            f"Unknown selected kernel: {selected}"
        )

    selected_col = (
        selected_crps_columns[
            selected
        ]
    )

    losses = {
        "raw_absolute_error":
            "raw_crps_c",

        "selected_gp_crps":
            selected_col,
    }

    rows = []

    for loss_name, loss_col in (
        losses.items()
    ):
        pivot = predictions.pivot(
            index="target_date",
            columns="decision_rule",
            values=loss_col,
        )

        for (
            rule_a,
            rule_b,
        ) in combinations(
            RULE_ORDER,
            2,
        ):
            common = pivot[
                [
                    rule_a,
                    rule_b,
                ]
            ].dropna()

            diff = (
                common[
                    rule_a
                ]
                - common[
                    rule_b
                ]
            ).to_numpy(
                dtype=float
            )

            n = len(diff)

            if n < 20:
                continue

            rng = np.random.default_rng(
                BOOTSTRAP_SEED
                + 100
                + RULE_ORDER.index(
                    rule_a
                )
                * 10
                + RULE_ORDER.index(
                    rule_b
                )
            )

            idx = rng.integers(
                0,
                n,
                size=(
                    BOOTSTRAP_REPS,
                    n,
                ),
            )

            ordinary = diff[
                idx
            ].mean(
                axis=1
            )

            ordinary_low, ordinary_high = (
                percentile_interval(
                    ordinary
                )
            )

            rng_block = (
                np.random.default_rng(
                    BOOTSTRAP_SEED
                    + 700
                    + RULE_ORDER.index(
                        rule_a
                    )
                    * 10
                    + RULE_ORDER.index(
                        rule_b
                    )
                )
            )

            b_idx = circular_block_indices(
                n,
                7,
                BOOTSTRAP_REPS,
                rng_block,
            )

            mb = diff[
                b_idx
            ].mean(
                axis=1
            )

            mb_low, mb_high = (
                percentile_interval(
                    mb
                )
            )

            rows.append(
                {
                    "loss":
                        loss_name,

                    "rule_a":
                        rule_a,

                    "rule_b":
                        rule_b,

                    "common_dates":
                        n,

                    "mean_a_minus_b_c":
                        float(
                            diff.mean()
                        ),

                    "ordinary_lower_95_c":
                        ordinary_low,

                    "ordinary_upper_95_c":
                        ordinary_high,

                    "block7_lower_95_c":
                        mb_low,

                    "block7_upper_95_c":
                        mb_high,
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# SELECTED GP DIAGNOSTICS
# =============================================================================


def selected_diagnostics(
    predictions,
    selected,
):
    prefix = (
        "rbf"
        if selected == "rbf"
        else "matern"
    )

    mean_col = (
        f"{prefix}_mean_c"
    )

    sd_col = (
        f"{prefix}_sd_c"
    )

    z_col = (
        f"{prefix}_z"
    )

    pit_col = (
        f"{prefix}_pit"
    )

    coverage_rows = []

    strata = [
        (
            "overall",
            "ALL",
            predictions,
        )
    ]

    for rule in RULE_ORDER:
        strata.append(
            (
                "rule",
                rule,
                predictions[
                    predictions[
                        "decision_rule"
                    ]
                    == rule
                ],
            )
        )

    for block in sorted(
        predictions[
            "validation_block"
        ].unique()
    ):
        strata.append(
            (
                "block",
                str(block),
                predictions[
                    predictions[
                        "validation_block"
                    ]
                    == block
                ],
            )
        )

    for (
        stratum_type,
        stratum,
        x,
    ) in strata:
        truth = x[
            "hko_daily_max_c"
        ].to_numpy(
            dtype=float
        )

        mu = x[
            mean_col
        ].to_numpy(
            dtype=float
        )

        sd = x[
            sd_col
        ].to_numpy(
            dtype=float
        )

        for level in INTERVAL_LEVELS:
            q = norm.ppf(
                0.5
                + level
                / 2.0
            )

            lower = (
                mu
                - q * sd
            )

            upper = (
                mu
                + q * sd
            )

            coverage = np.mean(
                (
                    truth
                    >= lower
                )
                & (
                    truth
                    <= upper
                )
            )

            width = np.mean(
                upper
                - lower
            )

            coverage_rows.append(
                {
                    "stratum_type":
                        stratum_type,

                    "stratum":
                        stratum,

                    "nominal_coverage":
                        level,

                    "n":
                        int(len(x)),

                    "empirical_coverage":
                        float(
                            coverage
                        ),

                    "mean_interval_width_c":
                        float(
                            width
                        ),

                    "coverage_minus_nominal":
                        float(
                            coverage
                            - level
                        ),
                }
            )

    diag_rows = []

    all_z = predictions[
        z_col
    ].to_numpy(
        dtype=float
    )

    diag_rows.append(
        {
            "scope":
                "pooled_rows",

            "decision_rule":
                "ALL",

            "n":
                len(all_z),

            "mean_z":
                float(
                    np.mean(
                        all_z
                    )
                ),

            "variance_z":
                float(
                    np.var(
                        all_z,
                        ddof=1,
                    )
                ),

            "skew_z":
                float(
                    stats.skew(
                        all_z,
                        bias=False,
                    )
                ),

            "excess_kurtosis_z":
                float(
                    stats.kurtosis(
                        all_z,
                        fisher=True,
                        bias=False,
                    )
                ),

            "lag1_z":
                np.nan,

            "lag1_z_squared":
                np.nan,
        }
    )

    for rule in RULE_ORDER:
        x = predictions[
            predictions[
                "decision_rule"
            ]
            == rule
        ].sort_values(
            "target_date"
        )

        z = x[
            z_col
        ].to_numpy(
            dtype=float
        )

        if len(z) >= 3:
            lag1 = np.corrcoef(
                z[:-1],
                z[1:],
            )[0, 1]

            lag1_sq = np.corrcoef(
                z[:-1] ** 2,
                z[1:] ** 2,
            )[0, 1]

        else:
            lag1 = np.nan
            lag1_sq = np.nan

        diag_rows.append(
            {
                "scope":
                    "rule",

                "decision_rule":
                    rule,

                "n":
                    len(z),

                "mean_z":
                    float(
                        np.mean(z)
                    ),

                "variance_z":
                    float(
                        np.var(
                            z,
                            ddof=1,
                        )
                    ),

                "skew_z":
                    float(
                        stats.skew(
                            z,
                            bias=False,
                        )
                    ),

                "excess_kurtosis_z":
                    float(
                        stats.kurtosis(
                            z,
                            fisher=True,
                            bias=False,
                        )
                    ),

                "lag1_z":
                    float(
                        lag1
                    ),

                "lag1_z_squared":
                    float(
                        lag1_sq
                    ),
            }
        )

    return (
        pd.DataFrame(
            coverage_rows
        ),
        pd.DataFrame(
            diag_rows
        ),
        z_col,
        pit_col,
    )


# =============================================================================
# MANUAL GP VARIANCE AUDIT
# =============================================================================


def variance_audit(
    bundle,
    test_row: pd.DataFrame,
):
    X_raw = exact_features(
        test_row
    )[FEATURE_COLUMNS].to_numpy(
        dtype=float
    )

    X_test = bundle[
        "x_scaler"
    ].transform(
        X_raw
    )

    X_train = bundle[
        "X_train_scaled"
    ]

    gpr = bundle[
        "gpr"
    ]

    fitted_kernel = (
        gpr.kernel_
    )

    K_y = (
        fitted_kernel(
            X_train
        )
        + JITTER
        * np.eye(
            len(
                X_train
            )
        )
    )

    k_star = fitted_kernel(
        X_test,
        X_train,
    )

    solve = np.linalg.solve(
        K_y,
        k_star.T,
    )

    k_ss_observation = float(
        fitted_kernel.diag(
            X_test
        )[0]
    )

    signal_kernel = (
        fitted_kernel.k1
    )

    k_ss_latent = float(
        signal_kernel.diag(
            X_test
        )[0]
    )

    correction = float(
        k_star
        @ solve
    )

    manual_observation_var_std = (
        k_ss_observation
        - correction
    )

    manual_latent_var_std = (
        k_ss_latent
        - correction
    )

    (
        software_mean,
        software_sd,
    ) = gpr.predict(
        X_test,
        return_std=True,
    )

    software_var_std = float(
        software_sd[0] ** 2
    )

    noise = float(
        fitted_kernel.k2.noise_level
    )

    y_scale_squared = (
        bundle[
            "y_scale"
        ]
        ** 2
    )

    return {
        "software_observation_variance_standardised":
            software_var_std,

        "manual_observation_variance_standardised":
            manual_observation_var_std,

        "manual_latent_variance_standardised":
            manual_latent_var_std,

        "white_noise_variance_standardised":
            noise,

        "observation_minus_latent_standardised":
            (
                manual_observation_var_std
                - manual_latent_var_std
            ),

        "software_minus_manual_observation":
            (
                software_var_std
                - manual_observation_var_std
            ),

        "noise_identity_error":
            (
                (
                    manual_observation_var_std
                    - manual_latent_var_std
                )
                - noise
            ),

        "software_observation_variance_celsius":
            (
                software_var_std
                * y_scale_squared
            ),

        "manual_observation_variance_celsius":
            (
                manual_observation_var_std
                * y_scale_squared
            ),

        "manual_latent_variance_celsius":
            (
                manual_latent_var_std
                * y_scale_squared
            ),

        "white_noise_variance_celsius":
            (
                noise
                * y_scale_squared
            ),
    }


# =============================================================================
# FULL WEATHER-HISTORY FIT AND MARCH–AUGUST PREDICTION
# =============================================================================


def full_history_stage(
    panel,
    selected,
):
    history = panel[
        (
            panel[
                "target_date"
            ]
            >= WEATHER_START
        )
        & (
            panel[
                "target_date"
            ]
            <= WEATHER_END
        )
        & panel[
            "residual_usable"
        ]
    ].copy()

    future = panel[
        (
            panel[
                "target_date"
            ]
            >= MARKET_START
        )
        & (
            panel[
                "target_date"
            ]
            <= FINAL_END
        )
        & panel[
            "support_available"
        ]
    ].copy()

    prediction_rows = []
    fit_rows = []
    full_bundles = {}

    for rule in RULE_ORDER:
        train = history[
            history[
                "decision_rule"
            ]
            == rule
        ].copy().sort_values(
            "target_date"
        )

        test = future[
            future[
                "decision_rule"
            ]
            == rule
        ].copy().sort_values(
            "target_date"
        )

        if train.empty:
            raise RuntimeError(
                f"Missing full-history train {rule}"
            )

        static_mean, static_sd = (
            static_parameters(
                train
            )
        )

        bundles = {}

        for family in KERNELS:
            bundle = fit_gp(
                train,
                family,
            )

            bundles[
                family
            ] = bundle

            full_bundles[
                (
                    rule,
                    family,
                )
            ] = bundle

            pars = bundle[
                "parameters"
            ]

            fit_rows.append(
                {
                    "decision_rule":
                        rule,

                    "kernel_family":
                        family,

                    "selected_kernel":
                        family
                        == selected,

                    "train_start":
                        train[
                            "target_date"
                        ].min().strftime(
                            "%Y-%m-%d"
                        ),

                    "train_end":
                        train[
                            "target_date"
                        ].max().strftime(
                            "%Y-%m-%d"
                        ),

                    "train_rows":
                        len(train),

                    "response_mean_c":
                        bundle[
                            "y_mean"
                        ],

                    "response_scale_c":
                        bundle[
                            "y_scale"
                        ],

                    "static_residual_mean_c":
                        static_mean,

                    "static_residual_sd_c":
                        static_sd,

                    "feature_means":
                        json.dumps(
                            bundle[
                                "x_scaler"
                            ].mean_.tolist()
                        ),

                    "feature_scales":
                        json.dumps(
                            bundle[
                                "x_scaler"
                            ].scale_.tolist()
                        ),

                    "signal_variance":
                        pars[
                            "signal_variance"
                        ],

                    "signal_std":
                        pars[
                            "signal_std"
                        ],

                    "length_scale":
                        pars[
                            "length_scale"
                        ],

                    "white_noise_variance":
                        pars[
                            "white_noise_variance"
                        ],

                    "constant_near_bound":
                        pars[
                            "constant_near_bound"
                        ],

                    "length_near_bound":
                        pars[
                            "length_near_bound"
                        ],

                    "noise_near_bound":
                        pars[
                            "noise_near_bound"
                        ],

                    "log_marginal_likelihood":
                        bundle[
                            "log_marginal_likelihood"
                        ],

                    "warning_count":
                        len(
                            bundle[
                                "warnings"
                            ]
                        ),

                    "warnings":
                        " || ".join(
                            bundle[
                                "warnings"
                            ]
                        ),
                }
            )

        rbf = gp_predict(
            bundles["rbf"],
            test,
        )

        matern = gp_predict(
            bundles["matern32"],
            test,
        )

        forecast = test[
            "forecast_daily_max_c"
        ].to_numpy(
            dtype=float
        )

        hko = test[
            "hko_daily_max_c"
        ].to_numpy(
            dtype=float
        )

        static_temp_mean = (
            forecast
            + static_mean
        )

        static_temp_sd = np.full(
            len(test),
            static_sd,
            dtype=float,
        )

        for i, (
            idx,
            source_row,
        ) in enumerate(
            test.iterrows()
        ):
            hko_value = (
                None
                if pd.isna(
                    source_row[
                        "hko_daily_max_c"
                    ]
                )
                else float(
                    source_row[
                        "hko_daily_max_c"
                    ]
                )
            )

            row = {
                "target_date":
                    source_row[
                        "target_date"
                    ].strftime(
                        "%Y-%m-%d"
                    ),

                "decision_rule":
                    rule,

                "empirical_period":
                    source_row[
                        "empirical_period"
                    ],

                "forecast_daily_max_c":
                    forecast[i],

                "hko_daily_max_c":
                    hko_value,

                "hko_available":
                    bool(
                        source_row[
                            "hko_available"
                        ]
                    ),

                "raw_mean_c":
                    forecast[i],

                "raw_sd_c":
                    0.0,

                "static_mean_c":
                    static_temp_mean[i],

                "static_sd_c":
                    static_temp_sd[i],

                "rbf_mean_c":
                    rbf[
                        "settlement_mean_c"
                    ][i],

                "rbf_sd_c":
                    rbf[
                        "settlement_sd_c"
                    ][i],

                "matern_mean_c":
                    matern[
                        "settlement_mean_c"
                    ][i],

                "matern_sd_c":
                    matern[
                        "settlement_sd_c"
                    ][i],

                "selected_kernel":
                    selected,
            }

            if selected == "rbf":
                row[
                    "selected_gp_mean_c"
                ] = rbf[
                    "settlement_mean_c"
                ][i]

                row[
                    "selected_gp_sd_c"
                ] = rbf[
                    "settlement_sd_c"
                ][i]

            else:
                row[
                    "selected_gp_mean_c"
                ] = matern[
                    "settlement_mean_c"
                ][i]

                row[
                    "selected_gp_sd_c"
                ] = matern[
                    "settlement_sd_c"
                ][i]

            if hko_value is not None:
                row[
                    "raw_crps_c"
                ] = abs(
                    hko_value
                    - forecast[i]
                )

                row[
                    "static_crps_c"
                ] = float(
                    gaussian_crps(
                        [hko_value],
                        [
                            static_temp_mean[i]
                        ],
                        [
                            static_temp_sd[i]
                        ],
                    )[0]
                )

                row[
                    "rbf_crps_c"
                ] = float(
                    gaussian_crps(
                        [hko_value],
                        [
                            rbf[
                                "settlement_mean_c"
                            ][i]
                        ],
                        [
                            rbf[
                                "settlement_sd_c"
                            ][i]
                        ],
                    )[0]
                )

                row[
                    "matern_crps_c"
                ] = float(
                    gaussian_crps(
                        [hko_value],
                        [
                            matern[
                                "settlement_mean_c"
                            ][i]
                        ],
                        [
                            matern[
                                "settlement_sd_c"
                            ][i]
                        ],
                    )[0]
                )

                selected_mean = row[
                    "selected_gp_mean_c"
                ]

                selected_sd = row[
                    "selected_gp_sd_c"
                ]

                row[
                    "selected_gp_crps_c"
                ] = float(
                    gaussian_crps(
                        [hko_value],
                        [selected_mean],
                        [selected_sd],
                    )[0]
                )

                row[
                    "selected_gp_z"
                ] = (
                    hko_value
                    - selected_mean
                ) / selected_sd

                row[
                    "selected_gp_pit"
                ] = norm.cdf(
                    hko_value,
                    loc=selected_mean,
                    scale=selected_sd,
                )

            else:
                for col in [
                    "raw_crps_c",
                    "static_crps_c",
                    "rbf_crps_c",
                    "matern_crps_c",
                    "selected_gp_crps_c",
                    "selected_gp_z",
                    "selected_gp_pit",
                ]:
                    row[col] = np.nan

            prediction_rows.append(
                row
            )

    return (
        pd.DataFrame(
            prediction_rows
        ),
        pd.DataFrame(
            fit_rows
        ),
        full_bundles,
    )


def future_score_summary(
    predictions,
):
    model_cols = {
        "raw":
            "raw_crps_c",

        "static":
            "static_crps_c",

        "rbf":
            "rbf_crps_c",

        "matern32":
            "matern_crps_c",

        "selected_gp":
            "selected_gp_crps_c",
    }

    rows = []

    period_masks = {
        "market_development":
            predictions[
                "empirical_period"
            ]
            == "market_development",

        "external_validation":
            predictions[
                "empirical_period"
            ]
            == "external_validation",

        "market_mar_aug":
            predictions[
                "empirical_period"
            ].isin(
                [
                    "market_development",
                    "external_validation",
                ]
            ),
    }

    for period, mask in (
        period_masks.items()
    ):
        p = predictions[
            mask
        ].copy()

        scored = p[
            p[
                "hko_available"
            ]
        ].copy()

        for model, col in (
            model_cols.items()
        ):
            if col not in scored:
                continue

            rows.append(
                {
                    "analysis_period":
                        period,

                    "decision_rule":
                        "DATE_BALANCED_ALL_RULES",

                    "model":
                        model,

                    "rows":
                        int(
                            scored[
                                col
                            ].notna().sum()
                        ),

                    "dates":
                        int(
                            scored[
                                "target_date"
                            ].nunique()
                        ),

                    "mean_crps_c":
                        float(
                            scored.groupby(
                                "target_date"
                            )[col]
                            .mean()
                            .mean()
                        )
                        if len(
                            scored
                        )
                        else np.nan,
                }
            )

        for rule in RULE_ORDER:
            x = scored[
                scored[
                    "decision_rule"
                ]
                == rule
            ]

            for model, col in (
                model_cols.items()
            ):
                if col not in x:
                    continue

                rows.append(
                    {
                        "analysis_period":
                            period,

                        "decision_rule":
                            rule,

                        "model":
                            model,

                        "rows":
                            int(
                                x[
                                    col
                                ].notna().sum()
                            ),

                        "dates":
                            int(
                                x[
                                    "target_date"
                                ].nunique()
                            ),

                        "mean_crps_c":
                            float(
                                x[
                                    col
                                ].mean()
                            )
                            if len(x)
                            else np.nan,
                    }
                )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# FIGURES
# =============================================================================


def make_figures(
    attribution,
    rule_block,
    predictions,
    selected,
    coverage,
):
    # Attribution.
    fig, ax = plt.subplots(
        figsize=(8, 5)
    )

    ax.bar(
        attribution[
            "model"
        ],
        attribution[
            "mean_date_crps_c"
        ],
    )

    ax.set_ylabel(
        "Mean date-balanced CRPS (°C)"
    )

    ax.set_title(
        "Chronological weather-model attribution"
    )

    fig.tight_layout()

    fig.savefig(
        ATTRIBUTION_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    # Block CRPS.
    fig, ax = plt.subplots(
        figsize=(9, 5)
    )

    x = rule_block[
        rule_block[
            "decision_rule"
        ]
        == "DATE_BALANCED_ALL_RULES"
    ].copy()

    for model in [
        "raw",
        "static",
        "rbf",
        "matern32",
    ]:
        z = x[
            x[
                "model"
            ]
            == model
        ]

        ax.plot(
            z[
                "validation_block"
            ].astype(int),
            z[
                "mean_crps_c"
            ],
            marker="o",
            label=model,
        )

    ax.set_xlabel(
        "Chronological validation block"
    )

    ax.set_ylabel(
        "Date-balanced CRPS (°C)"
    )

    ax.set_title(
        "Weather-model performance by chronological block"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        BLOCK_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    prefix = (
        "rbf"
        if selected
        == "rbf"
        else "matern"
    )

    # PIT.
    fig, ax = plt.subplots(
        figsize=(7, 5)
    )

    ax.hist(
        predictions[
            f"{prefix}_pit"
        ],
        bins=np.linspace(
            0,
            1,
            11,
        ),
        edgecolor="black",
    )

    ax.set_xlabel(
        "Probability integral transform"
    )

    ax.set_ylabel(
        "Count"
    )

    ax.set_title(
        f"Selected GP PIT: {selected}"
    )

    fig.tight_layout()

    fig.savefig(
        PIT_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    # QQ.
    z = predictions[
        f"{prefix}_z"
    ].to_numpy(
        dtype=float
    )

    theoretical, ordered = (
        stats.probplot(
            z,
            dist="norm",
            fit=False,
        )
    )

    fig, ax = plt.subplots(
        figsize=(6, 6)
    )

    ax.scatter(
        theoretical,
        ordered,
        s=12,
    )

    lo = min(
        np.min(theoretical),
        np.min(ordered),
    )

    hi = max(
        np.max(theoretical),
        np.max(ordered),
    )

    ax.plot(
        [lo, hi],
        [lo, hi],
        linestyle="--",
    )

    ax.set_xlabel(
        "Theoretical normal quantile"
    )

    ax.set_ylabel(
        "Observed standardised residual quantile"
    )

    ax.set_title(
        f"Selected GP normal Q–Q: {selected}"
    )

    fig.tight_layout()

    fig.savefig(
        QQ_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)

    # Coverage.
    overall = coverage[
        (
            coverage[
                "stratum_type"
            ]
            == "overall"
        )
    ].copy()

    fig, ax = plt.subplots(
        figsize=(6, 5)
    )

    ax.plot(
        overall[
            "nominal_coverage"
        ],
        overall[
            "empirical_coverage"
        ],
        marker="o",
        label="Empirical",
    )

    ax.plot(
        [0.45, 1.0],
        [0.45, 1.0],
        linestyle="--",
        label="Nominal",
    )

    ax.set_xlabel(
        "Nominal coverage"
    )

    ax.set_ylabel(
        "Empirical coverage"
    )

    ax.set_title(
        "Selected GP predictive-interval coverage"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        COVERAGE_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)


# =============================================================================
# INTEGRITY CHECKS
# =============================================================================


def integrity_checks(
    panel,
    predictions,
    fits,
    date_losses,
    attribution,
    selected,
    variance_audit_result,
    full_predictions,
    full_fits,
    coverage,
):
    checks = []

    validation_calendar = pd.date_range(
        VALIDATION_START,
        WEATHER_END,
        freq="D",
    )

    weather_usable = panel[
        (
            panel[
                "target_date"
            ]
            >= WEATHER_START
        )
        & (
            panel[
                "target_date"
            ]
            <= WEATHER_END
        )
        & panel[
            "residual_usable"
        ]
    ]

    validation_usable = weather_usable[
        weather_usable[
            "target_date"
        ]
        >= VALIDATION_START
    ]

    checks.extend(
        [
            {
                "check":
                    "validation_calendar_dates",
                "passed":
                    len(
                        validation_calendar
                    )
                    == 365,
                "observed":
                    len(
                        validation_calendar
                    ),
                "expected":
                    365,
                "notes":
                    "",
            },

            {
                "check":
                    "validation_prediction_rows_equal_usable_rows",
                "passed":
                    len(
                        predictions
                    )
                    == len(
                        validation_usable
                    ),
                "observed":
                    len(
                        predictions
                    ),
                "expected":
                    len(
                        validation_usable
                    ),
                "notes":
                    "same support for raw/static/RBF/Matérn",
            },

            {
                "check":
                    "validation_unique_date_rule_keys",
                "passed":
                    not predictions[
                        [
                            "target_date",
                            "decision_rule",
                        ]
                    ].duplicated().any(),
                "observed":
                    int(
                        predictions[
                            [
                                "target_date",
                                "decision_rule",
                            ]
                        ].duplicated().sum()
                    ),
                "expected":
                    0,
                "notes":
                    "",
            },

            {
                "check":
                    "validation_gp_fit_count",
                "passed":
                    len(fits)
                    == 32,
                "observed":
                    len(fits),
                "expected":
                    32,
                "notes":
                    "4 blocks x 4 rules x 2 kernels",
            },

            {
                "check":
                    "training_precedes_validation",
                "passed":
                    all(
                        pd.Timestamp(
                            row[
                                "train_end"
                            ]
                        )
                        < pd.Timestamp(
                            row[
                                "validation_start"
                            ]
                        )
                        for _, row
                        in fits.iterrows()
                    ),
                "observed":
                    int(
                        all(
                            pd.Timestamp(
                                row[
                                    "train_end"
                                ]
                            )
                            < pd.Timestamp(
                                row[
                                    "validation_start"
                                ]
                            )
                            for _, row
                            in fits.iterrows()
                        )
                    ),
                "expected":
                    1,
                "notes":
                    "",
            },

            {
                "check":
                    "date_loss_rows_match_dates_with_validation_support",
                "passed":
                    len(date_losses)
                    == predictions[
                        "target_date"
                    ].nunique(),
                "observed":
                    len(date_losses),
                "expected":
                    predictions[
                        "target_date"
                    ].nunique(),
                "notes":
                    "",
            },

            {
                "check":
                    "selected_kernel_is_gp_candidate",
                "passed":
                    selected
                    in KERNELS,
                "observed":
                    selected,
                "expected":
                    "rbf or matern32",
                "notes":
                    "selected only by weather-history date-balanced CRPS",
            },

            {
                "check":
                    "raw_crps_equals_absolute_error",
                "passed":
                    np.max(
                        np.abs(
                            predictions[
                                "raw_crps_c"
                            ]
                            - np.abs(
                                predictions[
                                    "hko_daily_max_c"
                                ]
                                - predictions[
                                    "forecast_daily_max_c"
                                ]
                            )
                        )
                    )
                    < 1e-10,
                "observed":
                    float(
                        np.max(
                            np.abs(
                                predictions[
                                    "raw_crps_c"
                                ]
                                - np.abs(
                                    predictions[
                                        "hko_daily_max_c"
                                    ]
                                    - predictions[
                                        "forecast_daily_max_c"
                                    ]
                                )
                            )
                        )
                    ),
                "expected":
                    0,
                "notes":
                    "Dirac forecast CRPS identity",
            },

            {
                "check":
                    "all_gaussian_sds_positive",
                "passed":
                    (
                        predictions[
                            [
                                "static_sd_c",
                                "rbf_sd_c",
                                "matern_sd_c",
                            ]
                        ]
                        > 0
                    ).all().all(),
                "observed":
                    int(
                        (
                            predictions[
                                [
                                    "static_sd_c",
                                    "rbf_sd_c",
                                    "matern_sd_c",
                                ]
                            ]
                            > 0
                        ).all().all()
                    ),
                "expected":
                    1,
                "notes":
                    "",
            },

            {
                "check":
                    "variance_software_manual_match",
                "passed":
                    abs(
                        variance_audit_result[
                            "software_minus_manual_observation"
                        ]
                    )
                    < 1e-8,
                "observed":
                    variance_audit_result[
                        "software_minus_manual_observation"
                    ],
                "expected":
                    0,
                "notes":
                    "",
            },

            {
                "check":
                    "white_noise_enters_once",
                "passed":
                    abs(
                        variance_audit_result[
                            "noise_identity_error"
                        ]
                    )
                    < 1e-8,
                "observed":
                    variance_audit_result[
                        "noise_identity_error"
                    ],
                "expected":
                    0,
                "notes":
                    "observation variance - latent variance = WhiteKernel variance",
            },

            {
                "check":
                    "full_history_fit_count",
                "passed":
                    len(
                        full_fits
                    )
                    == 8,
                "observed":
                    len(
                        full_fits
                    ),
                "expected":
                    8,
                "notes":
                    "4 rules x 2 kernels",
            },

            {
                "check":
                    "full_predictions_match_supported_mar_aug",
                "passed":
                    len(
                        full_predictions
                    )
                    == int(
                        (
                            panel[
                                "support_available"
                            ]
                            & (
                                panel[
                                    "target_date"
                                ]
                                >= MARKET_START
                            )
                            & (
                                panel[
                                    "target_date"
                                ]
                                <= FINAL_END
                            )
                        ).sum()
                    ),
                "observed":
                    len(
                        full_predictions
                    ),
                "expected":
                    int(
                        (
                            panel[
                                "support_available"
                            ]
                            & (
                                panel[
                                    "target_date"
                                ]
                                >= MARKET_START
                            )
                            & (
                                panel[
                                    "target_date"
                                ]
                                <= FINAL_END
                            )
                        ).sum()
                    ),
                "notes":
                    "no unsupported forecast is imputed",
            },

            {
                "check":
                    "external_forecast_distributions_complete",
                "passed":
                    len(
                        full_predictions[
                            full_predictions[
                                "empirical_period"
                            ]
                            == "external_validation"
                        ]
                    )
                    == 248,
                "observed":
                    len(
                        full_predictions[
                            full_predictions[
                                "empirical_period"
                            ]
                            == "external_validation"
                        ]
                    ),
                "expected":
                    248,
                "notes":
                    "forecast distributions exist even while 31 Aug HKO target is pending",
            },

            {
                "check":
                    "coverage_levels_complete",
                "passed":
                    set(
                        coverage.loc[
                            coverage[
                                "stratum_type"
                            ]
                            == "overall",
                            "nominal_coverage",
                        ].round(2)
                    )
                    == {
                        0.50,
                        0.80,
                        0.90,
                        0.95,
                    },
                "observed":
                    len(
                        coverage.loc[
                            coverage[
                                "stratum_type"
                            ]
                            == "overall"
                        ]
                    ),
                "expected":
                    4,
                "notes":
                    "",
            },
        ]
    )

    status = (
        "PASS"
        if all(
            row[
                "passed"
            ]
            for row in checks
        )
        else "FAILED"
    )

    return (
        pd.DataFrame(
            checks
        ),
        status,
    )


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    panel = load_panel()

    (
        predictions,
        fits,
        fit_objects,
        blocks,
    ) = validation_stage(
        panel
    )

    date_losses = (
        build_date_losses(
            predictions
        )
    )

    (
        attribution,
        selected,
        validation_means,
        attribution_shares,
    ) = attribution_summary(
        date_losses
    )

    rule_block = (
        rule_block_summary(
            predictions
        )
    )

    bootstrap = (
        bootstrap_contrasts(
            date_losses,
            selected,
        )
    )

    rule_inference = (
        pairwise_rule_inference(
            predictions,
            selected,
        )
    )

    (
        coverage,
        residual_diagnostics,
        selected_z_col,
        selected_pit_col,
    ) = selected_diagnostics(
        predictions,
        selected,
    )

    # Manual variance audit using the final chronological validation fit
    # for the 24h rule and selected covariance.
    final_block = max(
        b["block"]
        for b in blocks
    )

    audit_bundle = (
        fit_objects[
            (
                final_block,
                "24h_prior",
                selected,
            )
        ]
    )

    audit_test = panel[
        (
            panel[
                "target_date"
            ]
            >= blocks[-1][
                "start"
            ]
        )
        & (
            panel[
                "target_date"
            ]
            <= blocks[-1][
                "end"
            ]
        )
        & (
            panel[
                "decision_rule"
            ]
            == "24h_prior"
        )
        & panel[
            "residual_usable"
        ]
    ].sort_values(
        "target_date"
    ).head(1)

    if audit_test.empty:
        raise RuntimeError(
            "No variance-audit test row."
        )

    variance_result = (
        variance_audit(
            audit_bundle,
            audit_test,
        )
    )

    (
        full_predictions,
        full_fits,
        full_bundles,
    ) = full_history_stage(
        panel,
        selected,
    )

    market_scores = (
        future_score_summary(
            full_predictions
        )
    )

    (
        checks,
        status,
    ) = integrity_checks(
        panel,
        predictions,
        fits,
        date_losses,
        attribution,
        selected,
        variance_result,
        full_predictions,
        full_fits,
        coverage,
    )

    # -------------------------------------------------------------------------
    # Write artefacts
    # -------------------------------------------------------------------------

    predictions.to_csv(
        VALIDATION_PANEL,
        index=False,
        float_format="%.10f",
    )

    date_losses.to_csv(
        DATE_LOSSES,
        index=False,
        float_format="%.10f",
    )

    fits.to_csv(
        FIT_LEDGER,
        index=False,
        float_format="%.10f",
    )

    attribution.to_csv(
        ATTRIBUTION_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    rule_block.to_csv(
        RULE_BLOCK_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    bootstrap.to_csv(
        BOOTSTRAP_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    rule_inference.to_csv(
        RULE_INFERENCE,
        index=False,
        float_format="%.10f",
    )

    coverage.to_csv(
        COVERAGE_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    residual_diagnostics.to_csv(
        RESIDUAL_DIAGNOSTICS,
        index=False,
        float_format="%.10f",
    )

    full_predictions.to_csv(
        FULL_PERIOD_PREDICTIONS,
        index=False,
        float_format="%.10f",
    )

    full_fits.to_csv(
        FULL_FIT_LEDGER,
        index=False,
        float_format="%.10f",
    )

    market_scores.to_csv(
        MARKET_SCORE_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    VARIANCE_AUDIT_JSON.write_text(
        json.dumps(
            variance_result,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    selection = {
        "selection_source":
            "weather_history_chronological_validation_only",

        "selection_criterion":
            "mean date-balanced closed-form Gaussian CRPS",

        "validation_calendar_start":
            VALIDATION_START.strftime(
                "%Y-%m-%d"
            ),

        "validation_calendar_end":
            WEATHER_END.strftime(
                "%Y-%m-%d"
            ),

        "validation_calendar_dates":
            365,

        "block_sizes":
            BLOCK_SIZES,

        "mean_date_crps_c":
            validation_means,

        "selected_kernel":
            selected,

        "external_validation_used_for_selection":
            False,

        "market_prices_used_for_selection":
            False,

        "trading_pnl_used_for_selection":
            False,

        "attribution_shares":
            attribution_shares,
    }

    SELECTION_JSON.write_text(
        json.dumps(
            selection,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    checks.to_csv(
        CHECKS_CSV,
        index=False,
    )

    make_figures(
        attribution,
        rule_block,
        predictions,
        selected,
        coverage,
    )

    external_scored_rows = int(
        (
            (
                full_predictions[
                    "empirical_period"
                ]
                == "external_validation"
            )
            & full_predictions[
                "hko_available"
            ]
        ).sum()
    )

    summary = {
        "status":
            status,

        "weather_model_stage":
            "steps_16_23",

        "initial_training_calendar_dates":
            365,

        "validation_calendar_dates":
            365,

        "validation_block_sizes":
            BLOCK_SIZES,

        "validation_prediction_rows":
            int(
                len(
                    predictions
                )
            ),

        "validation_dates_with_support":
            int(
                predictions[
                    "target_date"
                ].nunique()
            ),

        "validation_gp_fits":
            int(
                len(fits)
            ),

        "candidate_kernels":
            KERNELS,

        "selected_kernel":
            selected,

        "mean_date_crps_c":
            validation_means,

        "attribution_shares":
            attribution_shares,

        "bootstrap_replications":
            BOOTSTRAP_REPS,

        "moving_block_lengths":
            MOVING_BLOCK_LENGTHS,

        "feature_columns":
            FEATURE_COLUMNS,

        "feature_formula":
            {
                "calendar_time_years":
                    "days since 2024-03-16 / 365.2425",

                "seasonal_position":
                    "(Gregorian day-of-year - 1) / 365.2425",

                "seasonal_sin_exact":
                    "sin(2*pi*seasonal_position)",

                "seasonal_cos_exact":
                    "cos(2*pi*seasonal_position)",

                "forecast_daily_max_c":
                    "admissible ECMWF HKT local-day maximum",
            },

        "input_standardisation":
            "rule-specific StandardScaler fitted on current training history only",

        "response_standardisation":
            "training residual mean and population standard deviation fitted on current training history only",

        "static_gaussian_scale":
            "training residual population standard deviation (Gaussian MLE convention)",

        "gp_estimator":
            "sklearn GaussianProcessRegressor",

        "constant_initial":
            CONSTANT_INITIAL,

        "constant_bounds":
            CONSTANT_BOUNDS,

        "length_initial":
            LENGTH_INITIAL,

        "length_bounds":
            LENGTH_BOUNDS,

        "noise_initial":
            NOISE_INITIAL,

        "noise_bounds":
            NOISE_BOUNDS,

        "jitter":
            JITTER,

        "optimizer":
            "fmin_l_bfgs_b",

        "optimizer_restarts":
            0,

        "random_state":
            RANDOM_STATE,

        "predictive_variance":
            "future-observation variance; WhiteKernel included once",

        "crps":
            "closed-form Gaussian CRPS",

        "full_history_gp_fits":
            int(
                len(
                    full_fits
                )
            ),

        "frozen_mar_aug_prediction_rows":
            int(
                len(
                    full_predictions
                )
            ),

        "external_forecast_distribution_rows":
            int(
                (
                    full_predictions[
                        "empirical_period"
                    ]
                    == "external_validation"
                ).sum()
            ),

        "external_scored_rows_currently":
            external_scored_rows,

        "august_31_target_pending":
            bool(
                (
                    (
                        full_predictions[
                            "target_date"
                        ]
                        == "2026-08-31"
                    )
                    & (
                        ~full_predictions[
                            "hko_available"
                        ]
                    )
                ).any()
            ),

        "validation_predictions_sha256":
            sha256_file(
                VALIDATION_PANEL
            ),

        "frozen_predictions_sha256":
            sha256_file(
                FULL_PERIOD_PREDICTIONS
            ),

        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(
        "status="
        + status
    )

    print(
        "validation_prediction_rows="
        + str(
            len(
                predictions
            )
        )
    )

    print(
        "validation_dates_with_support="
        + str(
            predictions[
                "target_date"
            ].nunique()
        )
    )

    print(
        "gp_validation_fits="
        + str(
            len(fits)
        )
    )

    print(
        "raw_mean_date_crps="
        + f"{validation_means['raw']:.10f}"
    )

    print(
        "static_mean_date_crps="
        + f"{validation_means['static']:.10f}"
    )

    print(
        "rbf_mean_date_crps="
        + f"{validation_means['rbf']:.10f}"
    )

    print(
        "matern_mean_date_crps="
        + f"{validation_means['matern32']:.10f}"
    )

    print(
        "selected_kernel="
        + selected
    )

    print(
        "full_prediction_rows="
        + str(
            len(
                full_predictions
            )
        )
    )

    print(
        "external_distribution_rows="
        + str(
            (
                full_predictions[
                    "empirical_period"
                ]
                == "external_validation"
            ).sum()
        )
    )

    if status != "PASS":
        failed = checks[
            ~checks[
                "passed"
            ]
        ]

        print(
            "failed_checks="
            + failed.to_json(
                orient="records"
            )
        )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
