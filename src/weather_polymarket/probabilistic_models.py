"""Probabilistic post-processing models used by Notebook 04."""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
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


QUANTILE_LEVELS = np.round(
    np.arange(
        0.01,
        1.00,
        0.01,
    ),
    2,
)

BASE_CATBOOST_LEVELS = np.array(
    [
        0.05,
        0.25,
        0.50,
        0.75,
        0.95,
    ],
    dtype=float,
)

RULE_CODES = {
    "24h_prior": 0.0,
    "12h_prior": 1.0,
    "6h_prior": 2.0,
    "event_day_open": 3.0,
}


def quantile_columns() -> list[str]:
    """Return the canonical 99 quantile column names."""

    return [
        f"q_{int(round(float(level) * 100)):02d}"
        for level in QUANTILE_LEVELS
    ]


def ensure_monotone(
    values: np.ndarray,
) -> np.ndarray:
    """Ensure non-decreasing quantiles along each prediction row."""

    array = np.asarray(
        values,
        dtype=float,
    )

    if array.ndim != 2:
        raise ValueError(
            "Quantile predictions must be a two-dimensional array."
        )

    return np.maximum.accumulate(
        array,
        axis=1,
    )


def empirical_quantiles(
    residuals: np.ndarray,
) -> np.ndarray:
    """Return the 99 empirical residual quantiles."""

    values = np.asarray(
        residuals,
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    if values.size == 0:
        raise ValueError(
            "No finite residuals were supplied."
        )

    return np.quantile(
        values,
        QUANTILE_LEVELS,
        method="linear",
    )


def interpolate_quantiles(
    base_predictions: np.ndarray,
) -> np.ndarray:
    """
    Interpolate CatBoost's five quantiles to the 99-quantile grid.

    NumPy interpolation uses constant extension beyond the two endpoint
    quantiles, which is the declared endpoint rule.
    """

    base = np.asarray(
        base_predictions,
        dtype=float,
    )

    if base.ndim == 1:
        base = base.reshape(
            -1,
            len(
                BASE_CATBOOST_LEVELS
            ),
        )

    if base.shape[1] != len(
        BASE_CATBOOST_LEVELS
    ):
        raise ValueError(
            "Unexpected CatBoost quantile prediction shape."
        )

    base = ensure_monotone(
        base
    )

    result = np.vstack(
        [
            np.interp(
                QUANTILE_LEVELS,
                BASE_CATBOOST_LEVELS,
                row,
            )
            for row in base
        ]
    )

    return ensure_monotone(
        result
    )


def approximate_crps(
    outcomes: np.ndarray,
    quantiles: np.ndarray,
) -> np.ndarray:
    r"""
    Approximate CRPS through the quantile representation.

    CRPS(F,y) = 2 \int_0^1 rho_tau(y - F^{-1}(tau)) d tau.

    The integral is approximated on the equally spaced 0.01,...,0.99 grid.
    """

    y = np.asarray(
        outcomes,
        dtype=float,
    ).reshape(
        -1,
        1,
    )

    q = np.asarray(
        quantiles,
        dtype=float,
    )

    if q.shape != (
        y.shape[0],
        len(
            QUANTILE_LEVELS
        ),
    ):
        raise ValueError(
            "Outcome and quantile dimensions do not agree."
        )

    error = y - q

    pinball = error * (
        QUANTILE_LEVELS.reshape(
            1,
            -1,
        )
        - (
            error < 0.0
        ).astype(float)
    )

    return 2.0 * np.mean(
        pinball,
        axis=1,
    )


def calendar_features(
    frame: pd.DataFrame,
    include_rule: bool,
) -> np.ndarray:
    """Construct the deliberately small CatBoost feature set."""

    dates = pd.to_datetime(
        frame[
            "target_date"
        ],
        errors="raise",
    )

    origin = pd.Timestamp(
        "2026-03-16"
    )

    day_index = (
        dates - origin
    ).dt.days.astype(float)

    day_of_year = (
        dates.dt.dayofyear.astype(float)
    )

    features = [
        pd.to_numeric(
            frame[
                "forecast_daily_max_c"
            ],
            errors="raise",
        ).to_numpy(
            dtype=float
        ),
        day_index.to_numpy(
            dtype=float
        ),
        np.sin(
            2.0
            * np.pi
            * day_of_year.to_numpy(
                dtype=float
            )
            / 365.25
        ),
        np.cos(
            2.0
            * np.pi
            * day_of_year.to_numpy(
                dtype=float
            )
            / 365.25
        ),
    ]

    if include_rule:
        rule_code = (
            frame[
                "decision_rule"
            ]
            .map(
                RULE_CODES
            )
        )

        if rule_code.isna().any():
            raise ValueError(
                "An unknown decision rule was encountered."
            )

        features.append(
            rule_code.to_numpy(
                dtype=float
            )
        )

    return np.column_stack(
        features
    )


def day_index(
    frame: pd.DataFrame,
) -> np.ndarray:
    """Return the one-dimensional calendar input used by the GP."""

    dates = pd.to_datetime(
        frame[
            "target_date"
        ],
        errors="raise",
    )

    origin = pd.Timestamp(
        "2026-03-16"
    )

    values = (
        dates - origin
    ).dt.days.to_numpy(
        dtype=float
    )

    return values.reshape(
        -1,
        1,
    )


def rule_specific_gp_quantiles(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    covariance: str,
    minimum_rows: int,
    random_seed: int,
) -> tuple[
    np.ndarray,
    list[dict[str, Any]],
]:
    """Fit separate Gaussian-process residual models by decision rule."""

    predictions = np.full(
        (
            len(validation),
            len(
                QUANTILE_LEVELS
            ),
        ),
        np.nan,
        dtype=float,
    )

    log_rows: list[
        dict[str, Any]
    ] = []

    normal_scores = norm.ppf(
        QUANTILE_LEVELS
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

        validation_positions = np.flatnonzero(
            validation_mask.to_numpy()
        )

        validation_rule = validation.loc[
            validation_mask
        ].copy()

        training_rule = training.loc[
            training[
                "decision_rule"
            ].eq(
                rule
            )
        ].copy()

        log: dict[str, Any] = {
            "component": (
                "gaussian_process"
            ),
            "scope": rule,
            "covariance": covariance,
            "training_rows": len(
                training_rule
            ),
            "validation_rows": len(
                validation_rule
            ),
            "status": "",
            "warning_count": 0,
            "learned_kernel": "",
            "message": "",
        }

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

            log_rows.append(
                log
            )

            continue

        scaler = StandardScaler()

        x_train = scaler.fit_transform(
            day_index(
                training_rule
            )
        )

        x_validation = (
            scaler.transform(
                day_index(
                    validation_rule
                )
            )
        )

        y_train = pd.to_numeric(
            training_rule[
                "residual_c"
            ],
            errors="raise",
        ).to_numpy(
            dtype=float
        )

        if covariance == "rbf":
            smoothness_kernel = RBF(
                length_scale=1.0,
                length_scale_bounds=(
                    0.05,
                    10.0,
                ),
            )

        elif covariance == "matern32":
            smoothness_kernel = Matern(
                length_scale=1.0,
                length_scale_bounds=(
                    0.05,
                    10.0,
                ),
                nu=1.5,
            )

        else:
            raise ValueError(
                f"Unknown covariance: {covariance}"
            )

        kernel = (
            ConstantKernel(
                constant_value=1.0,
                constant_value_bounds=(
                    0.01,
                    100.0,
                ),
            )
            * smoothness_kernel
            + WhiteKernel(
                noise_level=0.25,
                noise_level_bounds=(
                    0.001,
                    10.0,
                ),
            )
        )

        model = GaussianProcessRegressor(
            kernel=kernel,
            alpha=1.0e-8,
            normalize_y=True,
            n_restarts_optimizer=0,
            random_state=random_seed,
        )

        try:
            with warnings.catch_warnings(
                record=True
            ) as caught:
                warnings.simplefilter(
                    "always",
                    category=ConvergenceWarning,
                )

                model.fit(
                    x_train,
                    y_train,
                )

                mean, standard_deviation = (
                    model.predict(
                        x_validation,
                        return_std=True,
                    )
                )

            standard_deviation = np.maximum(
                standard_deviation,
                1.0e-8,
            )

            residual_quantiles = (
                mean.reshape(
                    -1,
                    1,
                )
                + standard_deviation.reshape(
                    -1,
                    1,
                )
                * normal_scores.reshape(
                    1,
                    -1,
                )
            )

            forecast = pd.to_numeric(
                validation_rule[
                    "forecast_daily_max_c"
                ],
                errors="raise",
            ).to_numpy(
                dtype=float
            )

            predictions[
                validation_positions,
                :,
            ] = (
                forecast.reshape(
                    -1,
                    1,
                )
                + residual_quantiles
            )

            predictions[
                validation_positions,
                :,
            ] = ensure_monotone(
                predictions[
                    validation_positions,
                    :,
                ]
            )

            log[
                "status"
            ] = "OK"

            log[
                "warning_count"
            ] = len(
                caught
            )

            log[
                "learned_kernel"
            ] = str(
                model.kernel_
            )

        except Exception as exc:
            log[
                "status"
            ] = "FIT_FAILED"

            log[
                "message"
            ] = (
                f"{type(exc).__name__}: {exc}"
            )

        log_rows.append(
            log
        )

    return (
        predictions,
        log_rows,
    )


def pooled_catboost_quantiles(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    random_seed: int,
) -> tuple[
    np.ndarray,
    dict[str, Any],
]:
    """Fit one pooled CatBoost residual quantile model."""

    model = CatBoostRegressor(
        loss_function=(
            "MultiQuantile:"
            "alpha=0.05,0.25,0.50,0.75,0.95"
        ),
        iterations=250,
        depth=3,
        learning_rate=0.03,
        l2_leaf_reg=8.0,
        bootstrap_type="No",
        random_strength=0.0,
        random_seed=random_seed,
        thread_count=1,
        verbose=False,
        allow_writing_files=False,
    )

    x_train = calendar_features(
        training,
        include_rule=True,
    )

    x_validation = calendar_features(
        validation,
        include_rule=True,
    )

    y_train = pd.to_numeric(
        training[
            "residual_c"
        ],
        errors="raise",
    ).to_numpy(
        dtype=float
    )

    log: dict[str, Any] = {
        "component": (
            "catboost_quantile"
        ),
        "scope": "pooled",
        "training_rows": len(
            training
        ),
        "validation_rows": len(
            validation
        ),
        "status": "",
        "message": "",
    }

    try:
        model.fit(
            x_train,
            y_train,
        )

        base_predictions = np.asarray(
            model.predict(
                x_validation
            ),
            dtype=float,
        )

        residual_quantiles = (
            interpolate_quantiles(
                base_predictions
            )
        )

        forecast = pd.to_numeric(
            validation[
                "forecast_daily_max_c"
            ],
            errors="raise",
        ).to_numpy(
            dtype=float
        )

        predictions = (
            forecast.reshape(
                -1,
                1,
            )
            + residual_quantiles
        )

        log[
            "status"
        ] = "OK"

        return (
            ensure_monotone(
                predictions
            ),
            log,
        )

    except Exception as exc:
        log[
            "status"
        ] = "FIT_FAILED"

        log[
            "message"
        ] = (
            f"{type(exc).__name__}: {exc}"
        )

        return (
            np.full(
                (
                    len(validation),
                    len(
                        QUANTILE_LEVELS
                    ),
                ),
                np.nan,
                dtype=float,
            ),
            log,
        )


def rule_specific_catboost_quantiles(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    minimum_rows: int,
    random_seed: int,
) -> tuple[
    np.ndarray,
    list[dict[str, Any]],
]:
    """Fit separate CatBoost residual quantile models by decision rule."""

    predictions = np.full(
        (
            len(validation),
            len(
                QUANTILE_LEVELS
            ),
        ),
        np.nan,
        dtype=float,
    )

    logs: list[
        dict[str, Any]
    ] = []

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

        validation_rule = validation.loc[
            validation_mask
        ].copy()

        training_rule = training.loc[
            training[
                "decision_rule"
            ].eq(
                rule
            )
        ].copy()

        log: dict[str, Any] = {
            "component": (
                "catboost_quantile"
            ),
            "scope": rule,
            "training_rows": len(
                training_rule
            ),
            "validation_rows": len(
                validation_rule
            ),
            "status": "",
            "message": "",
        }

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

            logs.append(
                log
            )

            continue

        model = CatBoostRegressor(
            loss_function=(
                "MultiQuantile:"
                "alpha=0.05,0.25,0.50,0.75,0.95"
            ),
            iterations=250,
            depth=3,
            learning_rate=0.03,
            l2_leaf_reg=8.0,
            bootstrap_type="No",
            random_strength=0.0,
            random_seed=random_seed,
            thread_count=1,
            verbose=False,
            allow_writing_files=False,
        )

        try:
            model.fit(
                calendar_features(
                    training_rule,
                    include_rule=False,
                ),
                pd.to_numeric(
                    training_rule[
                        "residual_c"
                    ],
                    errors="raise",
                ).to_numpy(
                    dtype=float
                ),
            )

            base_predictions = np.asarray(
                model.predict(
                    calendar_features(
                        validation_rule,
                        include_rule=False,
                    )
                ),
                dtype=float,
            )

            residual_quantiles = (
                interpolate_quantiles(
                    base_predictions
                )
            )

            forecast = pd.to_numeric(
                validation_rule[
                    "forecast_daily_max_c"
                ],
                errors="raise",
            ).to_numpy(
                dtype=float
            )

            predictions[
                positions,
                :,
            ] = (
                forecast.reshape(
                    -1,
                    1,
                )
                + residual_quantiles
            )

            predictions[
                positions,
                :,
            ] = ensure_monotone(
                predictions[
                    positions,
                    :,
                ]
            )

            log[
                "status"
            ] = "OK"

        except Exception as exc:
            log[
                "status"
            ] = "FIT_FAILED"

            log[
                "message"
            ] = (
                f"{type(exc).__name__}: {exc}"
            )

        logs.append(
            log
        )

    return (
        predictions,
        logs,
    )
