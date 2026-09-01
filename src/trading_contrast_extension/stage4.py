from __future__ import annotations

from itertools import combinations
from pathlib import Path
import hashlib
import json
import math

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(".")
S2 = ROOT / "outputs/trading_contrast_extension/stage2"
S3 = ROOT / "outputs/trading_contrast_extension/stage3"
OUT = ROOT / "outputs/trading_contrast_extension/stage4"
OUT.mkdir(parents=True, exist_ok=True)

FIXED_DAILY = S2 / "fixed_strategy_daily_ledger.csv"
TAEC_DAILY = S2 / "taec11_daily_ledger.csv"
TAEC_POS = S2 / "taec11_position_ledger.csv.gz"
STAGE3_RISK = S3 / "portfolio_risk_performance_summary.csv"

MODELS = [
    "raw",
    "static",
    "rbf",
    "matern32",
]

STRATEGIES = [
    "fixed_settlement",
    "taec11",
]

EXTERNAL = "external_validation"
BLOCK_LENGTH = 7
BOOTSTRAP_REPS = 10000
ALPHA = 0.05
BASE_SEED = 20260901


def as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s

    return (
        s.astype(str)
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "yes",
                "y",
            }
        )
    )


def seed_for(label: str) -> int:
    digest = hashlib.sha256(
        f"{BASE_SEED}|{label}".encode("utf-8")
    ).digest()

    return int.from_bytes(
        digest[:4],
        byteorder="big",
        signed=False,
    )


def ordinary_indices(
    n: int,
    reps: int,
    label: str,
) -> np.ndarray:
    rng = np.random.default_rng(
        seed_for(
            "ordinary|" + label
        )
    )

    return rng.integers(
        0,
        n,
        size=(
            reps,
            n,
        ),
    )


def moving_block_indices(
    n: int,
    block_length: int,
    reps: int,
    label: str,
) -> np.ndarray:
    if n < block_length:
        raise RuntimeError(
            "Sample shorter than moving-block length."
        )

    rng = np.random.default_rng(
        seed_for(
            "mbb|" + label
        )
    )

    blocks_needed = int(
        math.ceil(
            n / block_length
        )
    )

    max_start = (
        n
        - block_length
    )

    starts = rng.integers(
        0,
        max_start + 1,
        size=(
            reps,
            blocks_needed,
        ),
    )

    offsets = np.arange(
        block_length
    )

    idx = (
        starts[
            ...,
            None
        ]
        + offsets
    ).reshape(
        reps,
        -1,
    )

    return idx[
        :,
        :n,
    ]


def percentile_interval(
    values: np.ndarray,
    alpha: float = ALPHA,
) -> tuple[float, float]:
    finite = values[
        np.isfinite(
            values
        )
    ]

    if len(
        finite
    ) == 0:
        return (
            np.nan,
            np.nan,
        )

    return (
        float(
            np.quantile(
                finite,
                alpha / 2,
            )
        ),
        float(
            np.quantile(
                finite,
                1 - alpha / 2,
            )
        ),
    )


def mean_test(
    x: np.ndarray,
    label: str,
    method: str,
) -> dict[str, float]:
    x = np.asarray(
        x,
        dtype=float,
    )

    n = len(
        x
    )

    if method == "mbb":
        idx = moving_block_indices(
            n,
            BLOCK_LENGTH,
            BOOTSTRAP_REPS,
            label,
        )
    elif method == "ordinary":
        idx = ordinary_indices(
            n,
            BOOTSTRAP_REPS,
            label,
        )
    else:
        raise ValueError(
            method
        )

    observed_mean = float(
        np.mean(
            x
        )
    )

    boot_means = np.mean(
        x[
            idx
        ],
        axis=1,
    )

    centered = (
        x
        - observed_mean
    )

    null_means = np.mean(
        centered[
            idx
        ],
        axis=1,
    )

    # Invert the same centred two-sided bootstrap null distribution used
    # for the test. This keeps the 95% interval and p-value coherent.
    critical = float(
        np.quantile(
            np.abs(
                null_means
            ),
            1.0 - ALPHA,
        )
    )

    ci_mean = (
        observed_mean
        - critical,
        observed_mean
        + critical,
    )

    p_two = (
        1
        + int(
            np.sum(
                np.abs(
                    null_means
                )
                >= abs(
                    observed_mean
                )
                - 1e-15
            )
        )
    ) / (
        BOOTSTRAP_REPS
        + 1
    )

    p_positive = (
        1
        + int(
            np.sum(
                null_means
                >= observed_mean
                - 1e-15
            )
        )
    ) / (
        BOOTSTRAP_REPS
        + 1
    )

    p_negative = (
        1
        + int(
            np.sum(
                null_means
                <= observed_mean
                + 1e-15
            )
        )
    ) / (
        BOOTSTRAP_REPS
        + 1
    )

    return {
        "n_dates":
            int(
                n
            ),
        "observed_mean":
            observed_mean,
        "observed_total":
            float(
                np.sum(
                    x
                )
            ),
        "ci95_mean_lower":
            ci_mean[
                0
            ],
        "ci95_mean_upper":
            ci_mean[
                1
            ],
        "ci95_total_lower":
            ci_mean[
                0
            ]
            * n,
        "ci95_total_upper":
            ci_mean[
                1
            ]
            * n,
        "p_two_sided":
            float(
                min(
                    1.0,
                    p_two,
                )
            ),
        "p_one_sided_positive":
            float(
                min(
                    1.0,
                    p_positive,
                )
            ),
        "p_one_sided_negative":
            float(
                min(
                    1.0,
                    p_negative,
                )
            ),
    }


def sharpe(
    x: np.ndarray,
) -> float:
    x = np.asarray(
        x,
        dtype=float,
    )

    if len(
        x
    ) <= 1:
        return np.nan

    sd = float(
        np.std(
            x,
            ddof=1,
        )
    )

    if sd <= 1e-15:
        return np.nan

    return float(
        np.mean(
            x
        )
        / sd
    )


def sortino(
    x: np.ndarray,
) -> float:
    x = np.asarray(
        x,
        dtype=float,
    )

    downside = np.minimum(
        x,
        0.0,
    )

    dev = float(
        np.sqrt(
            np.mean(
                downside ** 2
            )
        )
    )

    if dev <= 1e-15:
        return np.nan

    return float(
        np.mean(
            x
        )
        / dev
    )


def max_drawdown(
    x: np.ndarray,
) -> float:
    cumulative = np.cumsum(
        np.asarray(
            x,
            dtype=float,
        )
    )

    wealth = np.concatenate(
        [
            np.array(
                [0.0]
            ),
            cumulative,
        ]
    )

    peak = np.maximum.accumulate(
        wealth
    )

    return float(
        np.max(
            peak
            - wealth
        )
    )


def portfolio_metrics(
    pnl: np.ndarray,
    capital: np.ndarray,
) -> dict[str, float]:
    pnl = np.asarray(
        pnl,
        dtype=float,
    )

    capital = np.asarray(
        capital,
        dtype=float,
    )

    q05 = float(
        np.quantile(
            pnl,
            0.05,
        )
    )

    tail = pnl[
        pnl
        <= q05
        + 1e-15
    ]

    total_capital = float(
        np.sum(
            capital
        )
    )

    total_pnl = float(
        np.sum(
            pnl
        )
    )

    return {
        "total_net_pnl":
            total_pnl,
        "mean_daily_pnl":
            float(
                np.mean(
                    pnl
                )
            ),
        "daily_pnl_sd":
            float(
                np.std(
                    pnl,
                    ddof=1,
                )
            ),
        "nonannualised_sharpe":
            sharpe(
                pnl
            ),
        "sortino":
            sortino(
                pnl
            ),
        "empirical_var95_loss":
            max(
                0.0,
                -q05,
            ),
        "empirical_expected_shortfall95_loss":
            max(
                0.0,
                -float(
                    np.mean(
                        tail
                    )
                ),
            ),
        "maximum_drawdown":
            max_drawdown(
                pnl
            ),
        "roi_on_entry_capital":
            (
                total_pnl
                / total_capital
                if total_capital
                > 1e-15
                else np.nan
            ),
    }


def bootstrap_metric_intervals(
    pnl: np.ndarray,
    capital: np.ndarray,
    label: str,
    method: str,
) -> list[dict[str, object]]:
    pnl = np.asarray(
        pnl,
        dtype=float,
    )

    capital = np.asarray(
        capital,
        dtype=float,
    )

    n = len(
        pnl
    )

    if method == "mbb":
        idx = moving_block_indices(
            n,
            BLOCK_LENGTH,
            BOOTSTRAP_REPS,
            label,
        )
    elif method == "ordinary":
        idx = ordinary_indices(
            n,
            BOOTSTRAP_REPS,
            label,
        )
    else:
        raise ValueError(
            method
        )

    observed = portfolio_metrics(
        pnl,
        capital,
    )

    metric_names = list(
        observed
    )

    draws = {
        name: np.empty(
            BOOTSTRAP_REPS,
            dtype=float,
        )
        for name in metric_names
    }

    for i in range(
        BOOTSTRAP_REPS
    ):
        m = portfolio_metrics(
            pnl[
                idx[
                    i
                ]
            ],
            capital[
                idx[
                    i
                ]
            ],
        )

        for name in metric_names:
            draws[
                name
            ][
                i
            ] = m[
                name
            ]

    rows = []

    for name in metric_names:
        lo, hi = percentile_interval(
            draws[
                name
            ]
        )

        rows.append(
            {
                "metric":
                    name,
                "bootstrap_method":
                    method,
                "observed":
                    observed[
                        name
                    ],
                "ci95_lower":
                    lo,
                "ci95_upper":
                    hi,
            }
        )

    return rows


def paired_sharpe_difference(
    x: np.ndarray,
    y: np.ndarray,
    label: str,
    method: str,
) -> dict[str, float]:
    x = np.asarray(
        x,
        dtype=float,
    )
    y = np.asarray(
        y,
        dtype=float,
    )

    if len(
        x
    ) != len(
        y
    ):
        raise RuntimeError(
            "Paired Sharpe comparison length mismatch."
        )

    n = len(
        x
    )

    if method == "mbb":
        idx = moving_block_indices(
            n,
            BLOCK_LENGTH,
            BOOTSTRAP_REPS,
            label,
        )
    else:
        idx = ordinary_indices(
            n,
            BOOTSTRAP_REPS,
            label,
        )

    observed = (
        sharpe(
            x
        )
        - sharpe(
            y
        )
    )

    draws = np.empty(
        BOOTSTRAP_REPS,
        dtype=float,
    )

    for i in range(
        BOOTSTRAP_REPS
    ):
        ii = idx[
            i
        ]

        draws[
            i
        ] = (
            sharpe(
                x[
                    ii
                ]
            )
            - sharpe(
                y[
                    ii
                ]
            )
        )

    lo, hi = percentile_interval(
        draws
    )

    finite = draws[
        np.isfinite(
            draws
        )
    ]

    p_lower = (
        1
        + int(
            np.sum(
                finite
                <= 0
            )
        )
    ) / (
        len(
            finite
        )
        + 1
    )

    p_upper = (
        1
        + int(
            np.sum(
                finite
                >= 0
            )
        )
    ) / (
        len(
            finite
        )
        + 1
    )

    p_two = min(
        1.0,
        2.0
        * min(
            p_lower,
            p_upper,
        ),
    )

    return {
        "observed_sharpe_difference":
            float(
                observed
            ),
        "ci95_lower":
            lo,
        "ci95_upper":
            hi,
        "p_two_sided":
            float(
                p_two
            ),
    }


def holm_adjust(
    pvalues: pd.Series,
) -> pd.Series:
    p = pd.to_numeric(
        pvalues,
        errors="raise",
    ).to_numpy(
        dtype=float
    )

    m = len(
        p
    )

    order = np.argsort(
        p
    )

    adjusted = np.empty(
        m,
        dtype=float,
    )

    running = 0.0

    for rank, idx in enumerate(
        order
    ):
        multiplier = (
            m
            - rank
        )

        value = min(
            1.0,
            multiplier
            * p[
                idx
            ],
        )

        running = max(
            running,
            value,
        )

        adjusted[
            idx
        ] = running

    return pd.Series(
        adjusted,
        index=pvalues.index,
    )


def common_external_panel() -> pd.DataFrame:
    fixed = pd.read_csv(
        FIXED_DAILY
    )

    taec = pd.read_csv(
        TAEC_DAILY
    )

    fixed[
        "strategy"
    ] = "fixed_settlement"

    taec[
        "strategy"
    ] = "taec11"

    columns = [
        "event_date",
        "empirical_period",
        "strategy",
        "model",
        "net_pnl",
        "entry_capital",
        "positions",
        "active",
    ]

    x = pd.concat(
        [
            fixed[
                columns
            ],
            taec[
                columns
            ],
        ],
        ignore_index=True,
    )

    x = x.loc[
        x[
            "empirical_period"
        ]
        == EXTERNAL
    ].copy()

    x[
        "event_date"
    ] = pd.to_datetime(
        x[
            "event_date"
        ],
        errors="raise",
    )

    x[
        "active"
    ] = as_bool(
        x[
            "active"
        ]
    )

    duplicate = x.duplicated(
        [
            "event_date",
            "strategy",
            "model",
        ]
    )

    if duplicate.any():
        raise RuntimeError(
            "Duplicate common-support daily portfolio keys."
        )

    expected_dates = None

    for strategy in STRATEGIES:
        for model in MODELS:
            dates = set(
                x.loc[
                    (
                        x[
                            "strategy"
                        ]
                        == strategy
                    )
                    & (
                        x[
                            "model"
                        ]
                        == model
                    ),
                    "event_date",
                ]
            )

            if len(
                dates
            ) != 61:
                raise RuntimeError(
                    f"{strategy}/{model}: expected 61 external dates."
                )

            if expected_dates is None:
                expected_dates = dates
            elif dates != expected_dates:
                raise RuntimeError(
                    "External portfolio date sets are not identical."
                )

    return x.sort_values(
        [
            "event_date",
            "strategy",
            "model",
        ]
    ).reset_index(
        drop=True
    )


def get_series(
    panel: pd.DataFrame,
    strategy: str,
    model: str,
    column: str = "net_pnl",
) -> pd.Series:
    x = (
        panel.loc[
            (
                panel[
                    "strategy"
                ]
                == strategy
            )
            & (
                panel[
                    "model"
                ]
                == model
            ),
            [
                "event_date",
                column,
            ],
        ]
        .sort_values(
            "event_date"
        )
        .set_index(
            "event_date"
        )[
            column
        ]
    )

    return x


def profitability_family(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for strategy in STRATEGIES:
        for model in MODELS:
            x = get_series(
                panel,
                strategy,
                model,
            )

            mbb = mean_test(
                x.to_numpy(
                    float
                ),
                f"profitability|{strategy}|{model}",
                "mbb",
            )

            ordinary = mean_test(
                x.to_numpy(
                    float
                ),
                f"profitability|{strategy}|{model}",
                "ordinary",
            )

            rows.append(
                {
                    "family":
                        "portfolio_profitability",
                    "strategy":
                        strategy,
                    "model":
                        model,
                    "comparison":
                        f"{strategy}:{model} vs 0",
                    **{
                        f"mbb_{k}": v
                        for k, v in mbb.items()
                    },
                    **{
                        f"ordinary_{k}": v
                        for k, v in ordinary.items()
                    },
                }
            )

    out = pd.DataFrame(
        rows
    )

    out[
        "holm_p_two_sided"
    ] = holm_adjust(
        out[
            "mbb_p_two_sided"
        ]
    )

    out[
        "holm_reject_5pct"
    ] = (
        out[
            "holm_p_two_sided"
        ]
        < ALPHA
    )

    out[
        "dependence_sensitive_5pct"
    ] = (
        (
            out[
                "mbb_p_two_sided"
            ]
            < ALPHA
        )
        != (
            out[
                "ordinary_p_two_sided"
            ]
            < ALPHA
        )
    )

    return out


def within_strategy_family(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for strategy in STRATEGIES:
        for model_a, model_b in combinations(
            MODELS,
            2,
        ):
            a = get_series(
                panel,
                strategy,
                model_a,
            )

            b = get_series(
                panel,
                strategy,
                model_b,
            )

            if not a.index.equals(
                b.index
            ):
                raise RuntimeError(
                    "Pairwise model dates are not aligned."
                )

            d = (
                a
                - b
            ).to_numpy(
                float
            )

            mbb = mean_test(
                d,
                f"within|{strategy}|{model_a}|{model_b}",
                "mbb",
            )

            ordinary = mean_test(
                d,
                f"within|{strategy}|{model_a}|{model_b}",
                "ordinary",
            )

            rows.append(
                {
                    "family":
                        "within_strategy_model_pairwise",
                    "holm_subfamily":
                        strategy,
                    "strategy":
                        strategy,
                    "model_a":
                        model_a,
                    "model_b":
                        model_b,
                    "comparison":
                        f"{model_a} - {model_b}",
                    **{
                        f"mbb_{k}": v
                        for k, v in mbb.items()
                    },
                    **{
                        f"ordinary_{k}": v
                        for k, v in ordinary.items()
                    },
                }
            )

    out = pd.DataFrame(
        rows
    )

    out[
        "holm_p_two_sided"
    ] = np.nan

    for strategy, idx in out.groupby(
        "holm_subfamily"
    ).groups.items():
        out.loc[
            idx,
            "holm_p_two_sided",
        ] = holm_adjust(
            out.loc[
                idx,
                "mbb_p_two_sided",
            ]
        )

    out[
        "holm_reject_5pct"
    ] = (
        out[
            "holm_p_two_sided"
        ]
        < ALPHA
    )

    out[
        "dependence_sensitive_5pct"
    ] = (
        (
            out[
                "mbb_p_two_sided"
            ]
            < ALPHA
        )
        != (
            out[
                "ordinary_p_two_sided"
            ]
            < ALPHA
        )
    )

    return out


def strategy_difference_family(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for model in MODELS:
        taec = get_series(
            panel,
            "taec11",
            model,
        )

        fixed = get_series(
            panel,
            "fixed_settlement",
            model,
        )

        if not taec.index.equals(
            fixed.index
        ):
            raise RuntimeError(
                "TAEC/fixed dates are not aligned."
            )

        d = (
            taec
            - fixed
        ).to_numpy(
            float
        )

        mbb = mean_test(
            d,
            f"strategy|{model}",
            "mbb",
        )

        ordinary = mean_test(
            d,
            f"strategy|{model}",
            "ordinary",
        )

        rows.append(
            {
                "family":
                    "taec_minus_fixed_by_model",
                "model":
                    model,
                "comparison":
                    f"TAEC - Fixed ({model})",
                **{
                    f"mbb_{k}": v
                    for k, v in mbb.items()
                },
                **{
                    f"ordinary_{k}": v
                    for k, v in ordinary.items()
                },
            }
        )

    out = pd.DataFrame(
        rows
    )

    out[
        "holm_p_two_sided"
    ] = holm_adjust(
        out[
            "mbb_p_two_sided"
        ]
    )

    out[
        "holm_reject_5pct"
    ] = (
        out[
            "holm_p_two_sided"
        ]
        < ALPHA
    )

    out[
        "dependence_sensitive_5pct"
    ] = (
        (
            out[
                "mbb_p_two_sided"
            ]
            < ALPHA
        )
        != (
            out[
                "ordinary_p_two_sided"
            ]
            < ALPHA
        )
    )

    return out


def sharpe_difference_family(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for model in MODELS:
        taec = get_series(
            panel,
            "taec11",
            model,
        )

        fixed = get_series(
            panel,
            "fixed_settlement",
            model,
        )

        if not taec.index.equals(
            fixed.index
        ):
            raise RuntimeError(
                "Sharpe comparison dates are not aligned."
            )

        mbb = paired_sharpe_difference(
            taec.to_numpy(
                float
            ),
            fixed.to_numpy(
                float
            ),
            f"sharpe|{model}",
            "mbb",
        )

        ordinary = paired_sharpe_difference(
            taec.to_numpy(
                float
            ),
            fixed.to_numpy(
                float
            ),
            f"sharpe|{model}",
            "ordinary",
        )

        rows.append(
            {
                "family":
                    "risk_adjusted_sharpe_difference",
                "model":
                    model,
                "comparison":
                    f"Sharpe(TAEC) - Sharpe(Fixed), {model}",
                **{
                    f"mbb_{k}": v
                    for k, v in mbb.items()
                },
                **{
                    f"ordinary_{k}": v
                    for k, v in ordinary.items()
                },
            }
        )

    out = pd.DataFrame(
        rows
    )

    out[
        "holm_p_two_sided"
    ] = holm_adjust(
        out[
            "mbb_p_two_sided"
        ]
    )

    out[
        "holm_reject_5pct"
    ] = (
        out[
            "holm_p_two_sided"
        ]
        < ALPHA
    )

    out[
        "dependence_sensitive_5pct"
    ] = (
        (
            out[
                "mbb_p_two_sided"
            ]
            < ALPHA
        )
        != (
            out[
                "ordinary_p_two_sided"
            ]
            < ALPHA
        )
    )

    return out


def convergence_family(
    panel: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    pos = pd.read_csv(
        TAEC_POS
    )

    pos = pos.loc[
        pos[
            "empirical_period"
        ]
        == EXTERNAL
    ].copy()

    pos[
        "event_date"
    ] = pd.to_datetime(
        pos[
            "event_date"
        ],
        errors="raise",
    )

    dates = (
        panel[
            [
                "event_date",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            "event_date"
        )
    )

    daily_frames = []
    rows = []

    for model in MODELS:
        gross = (
            pos.loc[
                pos[
                    "model"
                ]
                == model
            ]
            .groupby(
                "event_date",
                as_index=False,
            )
            .agg(
                signed_convergence_pnl=(
                    "signed_market_move_toward_model",
                    "sum",
                ),
                position_count=(
                    "contract_key",
                    "size",
                ),
                transaction_cost=(
                    "round_trip_cost",
                    "sum",
                ),
                net_pnl=(
                    "net_pnl",
                    "sum",
                ),
            )
        )

        d = dates.merge(
            gross,
            on="event_date",
            how="left",
            validate="one_to_one",
        )

        for c in [
            "signed_convergence_pnl",
            "position_count",
            "transaction_cost",
            "net_pnl",
        ]:
            d[
                c
            ] = d[
                c
            ].fillna(
                0.0
            )

        d[
            "model"
        ] = model

        if not np.allclose(
            d[
                "signed_convergence_pnl"
            ]
            - d[
                "transaction_cost"
            ],
            d[
                "net_pnl"
            ],
            atol=1e-12,
        ):
            raise RuntimeError(
                f"{model}: TAEC gross convergence - cost != net PnL."
            )

        daily_frames.append(
            d
        )

        x = d[
            "signed_convergence_pnl"
        ].to_numpy(
            float
        )

        mbb = mean_test(
            x,
            f"convergence|{model}",
            "mbb",
        )

        ordinary = mean_test(
            x,
            f"convergence|{model}",
            "ordinary",
        )

        rows.append(
            {
                "family":
                    "market_convergence",
                "model":
                    model,
                "comparison":
                    f"TAEC signed pre-cost convergence ({model}) vs 0",
                **{
                    f"mbb_{k}": v
                    for k, v in mbb.items()
                },
                **{
                    f"ordinary_{k}": v
                    for k, v in ordinary.items()
                },
            }
        )

    out = pd.DataFrame(
        rows
    )

    out[
        "holm_p_two_sided"
    ] = holm_adjust(
        out[
            "mbb_p_two_sided"
        ]
    )

    out[
        "holm_reject_5pct"
    ] = (
        out[
            "holm_p_two_sided"
        ]
        < ALPHA
    )

    out[
        "dependence_sensitive_5pct"
    ] = (
        (
            out[
                "mbb_p_two_sided"
            ]
            < ALPHA
        )
        != (
            out[
                "ordinary_p_two_sided"
            ]
            < ALPHA
        )
    )

    return (
        out,
        pd.concat(
            daily_frames,
            ignore_index=True,
        ),
    )


def risk_intervals(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for strategy in STRATEGIES:
        for model in MODELS:
            x = (
                panel.loc[
                    (
                        panel[
                            "strategy"
                        ]
                        == strategy
                    )
                    & (
                        panel[
                            "model"
                        ]
                        == model
                    )
                ]
                .sort_values(
                    "event_date"
                )
            )

            pnl = x[
                "net_pnl"
            ].to_numpy(
                float
            )

            capital = x[
                "entry_capital"
            ].to_numpy(
                float
            )

            for method in [
                "mbb",
                "ordinary",
            ]:
                metrics = bootstrap_metric_intervals(
                    pnl,
                    capital,
                    f"risk|{strategy}|{model}|{method}",
                    method,
                )

                for metric in metrics:
                    rows.append(
                        {
                            "empirical_period":
                                EXTERNAL,
                            "strategy":
                                strategy,
                            "model":
                                model,
                            **metric,
                        }
                    )

    return pd.DataFrame(
        rows
    )


def interpretation(
    row: pd.Series,
    estimate_col: str,
) -> str:
    estimate = float(
        row[
            estimate_col
        ]
    )

    primary_reject = bool(
        row[
            "holm_reject_5pct"
        ]
    )

    dependence_sensitive = bool(
        row[
            "dependence_sensitive_5pct"
        ]
    )

    direction = (
        "positive"
        if estimate > 0
        else "negative"
    )

    if (
        primary_reject
        and dependence_sensitive
    ):
        return (
            f"The primary 7-date moving-block bootstrap with Holm correction "
            f"indicates a {direction} effect, but the conclusion is "
            "dependence-sensitive because the ordinary-bootstrap significance "
            "classification differs."
        )

    if dependence_sensitive:
        return (
            "Not statistically resolved under the primary moving-block/Holm "
            "procedure; inference is dependence-sensitive because the ordinary "
            "bootstrap significance classification differs."
        )

    if primary_reject:
        return (
            f"Statistically resolved {direction} effect under the "
            "7-date moving-block bootstrap after Holm correction."
        )

    return (
        "Not statistically resolved under the 7-date moving-block "
        "bootstrap after Holm correction."
    )


def claims_register(
    profitability: pd.DataFrame,
    pairwise: pd.DataFrame,
    strategy_diff: pd.DataFrame,
    sharpe_diff: pd.DataFrame,
    convergence: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for _, r in profitability.iterrows():
        rows.append(
            {
                "family":
                    r[
                        "family"
                    ],
                "comparison":
                    r[
                        "comparison"
                    ],
                "estimate":
                    r[
                        "mbb_observed_total"
                    ],
                "estimate_type":
                    "total external net PnL",
                "mbb_ci95_lower":
                    r[
                        "mbb_ci95_total_lower"
                    ],
                "mbb_ci95_upper":
                    r[
                        "mbb_ci95_total_upper"
                    ],
                "mbb_p_two_sided":
                    r[
                        "mbb_p_two_sided"
                    ],
                "holm_p":
                    r[
                        "holm_p_two_sided"
                    ],
                "holm_reject_5pct":
                    r[
                        "holm_reject_5pct"
                    ],
                "dependence_sensitive_5pct":
                    r[
                        "dependence_sensitive_5pct"
                    ],
                "interpretation":
                    interpretation(
                        r,
                        "mbb_observed_total",
                    ),
            }
        )

    for frame, estimate_col, estimate_type in [
        (
            pairwise,
            "mbb_observed_total",
            "paired total PnL difference",
        ),
        (
            strategy_diff,
            "mbb_observed_total",
            "paired TAEC-minus-Fixed total PnL",
        ),
        (
            convergence,
            "mbb_observed_total",
            "TAEC pre-cost signed convergence total",
        ),
    ]:
        for _, r in frame.iterrows():
            comparison = str(
                r[
                    "comparison"
                ]
            )

            if (
                r[
                    "family"
                ]
                == "within_strategy_model_pairwise"
            ):
                comparison = (
                    f"{r['strategy']}: "
                    + comparison
                )

            rows.append(
                {
                    "family":
                        r[
                            "family"
                        ],
                    "comparison":
                        comparison,
                    "estimate":
                        r[
                            estimate_col
                        ],
                    "estimate_type":
                        estimate_type,
                    "mbb_ci95_lower":
                        r[
                            "mbb_ci95_total_lower"
                        ],
                    "mbb_ci95_upper":
                        r[
                            "mbb_ci95_total_upper"
                        ],
                    "mbb_p_two_sided":
                        r[
                            "mbb_p_two_sided"
                        ],
                    "holm_p":
                        r[
                            "holm_p_two_sided"
                        ],
                    "holm_reject_5pct":
                        r[
                            "holm_reject_5pct"
                        ],
                    "dependence_sensitive_5pct":
                        r[
                            "dependence_sensitive_5pct"
                        ],
                    "interpretation":
                        interpretation(
                            r,
                            estimate_col,
                        ),
                }
            )

    for _, r in sharpe_diff.iterrows():
        rows.append(
            {
                "family":
                    r[
                        "family"
                    ],
                "comparison":
                    r[
                        "comparison"
                    ],
                "estimate":
                    r[
                        "mbb_observed_sharpe_difference"
                    ],
                "estimate_type":
                    "nonannualised Sharpe difference",
                "mbb_ci95_lower":
                    r[
                        "mbb_ci95_lower"
                    ],
                "mbb_ci95_upper":
                    r[
                        "mbb_ci95_upper"
                    ],
                "mbb_p_two_sided":
                    r[
                        "mbb_p_two_sided"
                    ],
                "holm_p":
                    r[
                        "holm_p_two_sided"
                    ],
                "holm_reject_5pct":
                    r[
                        "holm_reject_5pct"
                    ],
                "dependence_sensitive_5pct":
                    r[
                        "dependence_sensitive_5pct"
                    ],
                "interpretation":
                    interpretation(
                        r,
                        "mbb_observed_sharpe_difference",
                    ),
            }
        )

    out = pd.DataFrame(
        rows
    )

    out[
        "inference_status"
    ] = "EXPLORATORY_EXTENSION"

    out[
        "sampling_unit"
    ] = "settlement_date"

    out[
        "primary_dependence_method"
    ] = "7-consecutive-common-support-date moving-block bootstrap"

    return out


def figures(
    profitability: pd.DataFrame,
    strategy_diff: pd.DataFrame,
    convergence: pd.DataFrame,
) -> None:
    p = profitability.copy()

    p[
        "portfolio"
    ] = (
        p[
            "strategy"
        ]
        + ":"
        + p[
            "model"
        ]
    )

    y = np.arange(
        len(
            p
        )
    )

    estimate = p[
        "mbb_observed_total"
    ].to_numpy(
        float
    )

    lower = p[
        "mbb_ci95_total_lower"
    ].to_numpy(
        float
    )

    upper = p[
        "mbb_ci95_total_upper"
    ].to_numpy(
        float
    )

    fig, ax = plt.subplots(
        figsize=(
            9,
            6,
        )
    )

    ax.errorbar(
        estimate,
        y,
        xerr=np.vstack(
            [
                estimate
                - lower,
                upper
                - estimate,
            ]
        ),
        fmt="o",
        capsize=3,
    )

    ax.axvline(
        0.0,
        linewidth=1,
    )

    ax.set_yticks(
        y
    )

    ax.set_yticklabels(
        p[
            "portfolio"
        ]
    )

    ax.set_xlabel(
        "External total net PnL"
    )

    ax.set_title(
        "External portfolio profitability: 95% moving-block bootstrap intervals"
    )

    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_profitability_mbb_intervals.png",
        dpi=180,
    )

    plt.close(
        fig
    )

    s = strategy_diff.copy()

    y = np.arange(
        len(
            s
        )
    )

    estimate = s[
        "mbb_observed_total"
    ].to_numpy(
        float
    )

    lower = s[
        "mbb_ci95_total_lower"
    ].to_numpy(
        float
    )

    upper = s[
        "mbb_ci95_total_upper"
    ].to_numpy(
        float
    )

    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    ax.errorbar(
        estimate,
        y,
        xerr=np.vstack(
            [
                estimate
                - lower,
                upper
                - estimate,
            ]
        ),
        fmt="o",
        capsize=3,
    )

    ax.axvline(
        0.0,
        linewidth=1,
    )

    ax.set_yticks(
        y
    )

    ax.set_yticklabels(
        s[
            "model"
        ]
    )

    ax.set_xlabel(
        "TAEC minus Fixed external total PnL"
    )

    ax.set_title(
        "Aggressive-minus-conservative strategy contrast"
    )

    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_taec_minus_fixed_mbb_intervals.png",
        dpi=180,
    )

    plt.close(
        fig
    )

    c = convergence.copy()

    y = np.arange(
        len(
            c
        )
    )

    estimate = c[
        "mbb_observed_total"
    ].to_numpy(
        float
    )

    lower = c[
        "mbb_ci95_total_lower"
    ].to_numpy(
        float
    )

    upper = c[
        "mbb_ci95_total_upper"
    ].to_numpy(
        float
    )

    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    ax.errorbar(
        estimate,
        y,
        xerr=np.vstack(
            [
                estimate
                - lower,
                upper
                - estimate,
            ]
        ),
        fmt="o",
        capsize=3,
    )

    ax.axvline(
        0.0,
        linewidth=1,
    )

    ax.set_yticks(
        y
    )

    ax.set_yticklabels(
        c[
            "model"
        ]
    )

    ax.set_xlabel(
        "Pre-cost signed convergence PnL"
    )

    ax.set_title(
        "TAEC market-convergence evidence before transaction costs"
    )

    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_taec_precost_convergence_mbb_intervals.png",
        dpi=180,
    )

    plt.close(
        fig
    )


def main() -> None:
    panel = common_external_panel()

    panel.to_csv(
        OUT
        / "external_common_support_daily_panel.csv",
        index=False,
    )

    profitability = profitability_family(
        panel
    )

    pairwise = within_strategy_family(
        panel
    )

    strategy_diff = strategy_difference_family(
        panel
    )

    sharpe_diff = sharpe_difference_family(
        panel
    )

    convergence, convergence_daily = convergence_family(
        panel
    )

    risk_ci = risk_intervals(
        panel
    )

    profitability.to_csv(
        OUT
        / "portfolio_profitability_inference.csv",
        index=False,
    )

    pairwise.to_csv(
        OUT
        / "within_strategy_model_pairwise_inference.csv",
        index=False,
    )

    strategy_diff.to_csv(
        OUT
        / "taec_vs_fixed_inference.csv",
        index=False,
    )

    sharpe_diff.to_csv(
        OUT
        / "sharpe_strategy_difference_inference.csv",
        index=False,
    )

    convergence.to_csv(
        OUT
        / "market_convergence_inference.csv",
        index=False,
    )

    convergence_daily.to_csv(
        OUT
        / "taec_daily_precost_convergence_panel.csv",
        index=False,
    )

    risk_ci.to_csv(
        OUT
        / "risk_metric_bootstrap_intervals.csv",
        index=False,
    )

    claims = claims_register(
        profitability,
        pairwise,
        strategy_diff,
        sharpe_diff,
        convergence,
    )

    claims.to_csv(
        OUT
        / "stage4_inference_claims_register.csv",
        index=False,
    )

    figures(
        profitability,
        strategy_diff,
        convergence,
    )

    # Cross-check Stage-3 risk point estimates.
    stage3 = pd.read_csv(
        STAGE3_RISK
    )

    stage3 = stage3.loc[
        stage3[
            "empirical_period"
        ]
        == EXTERNAL
    ].copy()

    point = (
        risk_ci.loc[
            risk_ci[
                "bootstrap_method"
            ]
            == "mbb",
            [
                "strategy",
                "model",
                "metric",
                "observed",
            ],
        ]
        .pivot_table(
            index=[
                "strategy",
                "model",
            ],
            columns="metric",
            values="observed",
            aggfunc="first",
        )
        .reset_index()
    )

    reconciliation_rows = []

    for _, r in stage3.iterrows():
        p = point.loc[
            (
                point[
                    "strategy"
                ]
                == r[
                    "strategy"
                ]
            )
            & (
                point[
                    "model"
                ]
                == r[
                    "model"
                ]
            )
        ]

        if len(
            p
        ) != 1:
            raise RuntimeError(
                "Risk point-estimate reconciliation key failure."
            )

        p = p.iloc[
            0
        ]

        for metric in [
            "total_net_pnl",
            "daily_pnl_sd",
            "nonannualised_sharpe",
            "sortino",
            "empirical_var95_loss",
            "empirical_expected_shortfall95_loss",
            "maximum_drawdown",
            "roi_on_entry_capital",
        ]:
            observed = float(
                p[
                    metric
                ]
            )

            expected = float(
                r[
                    metric
                ]
            )

            reconciliation_rows.append(
                {
                    "strategy":
                        r[
                            "strategy"
                        ],
                    "model":
                        r[
                            "model"
                        ],
                    "metric":
                        metric,
                    "stage4_observed":
                        observed,
                    "stage3_observed":
                        expected,
                    "absolute_difference":
                        abs(
                            observed
                            - expected
                        ),
                    "passed":
                        bool(
                            abs(
                                observed
                                - expected
                            )
                            <= 1e-10
                        ),
                }
            )

    reconciliation = pd.DataFrame(
        reconciliation_rows
    )

    reconciliation.to_csv(
        OUT
        / "stage3_stage4_risk_reconciliation.csv",
        index=False,
    )

    if not reconciliation[
        "passed"
    ].all():
        raise RuntimeError(
            "Stage-4 point estimates do not reproduce Stage 3."
        )

    checks = []

    def add(
        check: str,
        passed: bool,
        observed: object,
        expected: object,
        note: str = "",
    ) -> None:
        checks.append(
            {
                "check":
                    check,
                "passed":
                    bool(
                        passed
                    ),
                "observed":
                    observed,
                "expected":
                    expected,
                "note":
                    note,
            }
        )

    add(
        "external_common_support_61_dates",
        panel[
            "event_date"
        ].nunique()
        == 61,
        int(
            panel[
                "event_date"
            ].nunique()
        ),
        61,
    )

    add(
        "external_common_support_8_portfolios",
        len(
            panel
        )
        == 61
        * 8,
        len(
            panel
        ),
        488,
    )

    add(
        "bootstrap_reps",
        BOOTSTRAP_REPS
        == 10000,
        BOOTSTRAP_REPS,
        10000,
    )

    add(
        "block_length",
        BLOCK_LENGTH
        == 7,
        BLOCK_LENGTH,
        7,
        (
            "Seven consecutive common-support settlement-date observations; "
            "one missing external calendar date is not imputed."
        ),
    )

    add(
        "profitability_family_size",
        len(
            profitability
        )
        == 8,
        len(
            profitability
        ),
        8,
    )

    sizes = (
        pairwise.groupby(
            "holm_subfamily"
        )
        .size()
        .to_dict()
    )

    add(
        "within_strategy_pairwise_family_sizes",
        sizes
        == {
            "fixed_settlement":
                6,
            "taec11":
                6,
        },
        sizes,
        {
            "fixed_settlement":
                6,
            "taec11":
                6,
        },
    )

    add(
        "taec_fixed_family_size",
        len(
            strategy_diff
        )
        == 4,
        len(
            strategy_diff
        ),
        4,
    )

    add(
        "sharpe_family_size",
        len(
            sharpe_diff
        )
        == 4,
        len(
            sharpe_diff
        ),
        4,
    )

    add(
        "convergence_family_size",
        len(
            convergence
        )
        == 4,
        len(
            convergence
        ),
        4,
    )

    add(
        "holm_adjusted_probabilities_valid",
        bool(
            pd.concat(
                [
                    profitability[
                        "holm_p_two_sided"
                    ],
                    pairwise[
                        "holm_p_two_sided"
                    ],
                    strategy_diff[
                        "holm_p_two_sided"
                    ],
                    sharpe_diff[
                        "holm_p_two_sided"
                    ],
                    convergence[
                        "holm_p_two_sided"
                    ],
                ],
                ignore_index=True,
            )
            .between(
                0,
                1,
            )
            .all()
        ),
        "all",
        "[0,1]",
    )

    add(
        "stage3_point_estimate_reconciliation",
        bool(
            reconciliation[
                "passed"
            ].all()
        ),
        float(
            reconciliation[
                "absolute_difference"
            ].max()
        ),
        "<=1e-10",
    )

    stage_checks = pd.DataFrame(
        checks
    )

    stage_checks.to_csv(
        OUT
        / "stage4_integrity_checks.csv",
        index=False,
    )

    status = (
        "PASS"
        if stage_checks[
            "passed"
        ].all()
        else "FAILED"
    )

    resolved = claims.loc[
        claims[
            "holm_reject_5pct"
        ]
    ].copy()

    dependence_sensitive = claims.loc[
        claims[
            "dependence_sensitive_5pct"
        ]
    ].copy()

    summary = {
        "status":
            status,
        "stage":
            4,
        "stage_name":
            (
                "common_support_bootstrap_inference_"
                "and_multiplicity_control"
            ),
        "inference_status":
            "EXPLORATORY_EXTENSION",
        "external_common_support_dates":
            61,
        "sampling_unit":
            "settlement_date",
        "primary_method":
            (
                "7-consecutive-common-support-date moving-block bootstrap"
            ),
        "secondary_method":
            "ordinary settlement-date bootstrap",
        "bootstrap_repetitions":
            BOOTSTRAP_REPS,
        "confidence_level":
            0.95,
        "mean_test_interval_method":
            (
                "95% symmetric centred-bootstrap interval obtained by "
                "inverting the same two-sided null distribution used for "
                "the corresponding mean test"
            ),
        "multiplicity":
            (
                "Holm family-wise correction within each pre-specified family; "
                "the two within-strategy model families are corrected separately."
            ),
        "tail_metric_policy":
            (
                "VaR, expected shortfall and maximum drawdown receive bootstrap "
                "uncertainty intervals but no conventional significance claims."
            ),
        "resolved_after_holm":
            resolved[
                [
                    "family",
                    "comparison",
                    "estimate",
                    "holm_p",
                    "interpretation",
                ]
            ].to_dict(
                orient="records"
            ),
        "dependence_sensitive_claims":
            dependence_sensitive[
                [
                    "family",
                    "comparison",
                    "estimate",
                    "mbb_p_two_sided",
                    "holm_p",
                    "interpretation",
                ]
            ].to_dict(
                orient="records"
            ),
        "next_stage":
            (
                "cost, concentration, support, execution-proxy and perturbation "
                "robustness; then thesis-value pruning"
            ),
    }

    (
        OUT
        / "stage4_summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )

    print()
    print(
        "==================================================================="
    )
    print(
        " PORTFOLIO PROFITABILITY INFERENCE"
    )
    print(
        "==================================================================="
    )
    print(
        profitability[
            [
                "strategy",
                "model",
                "mbb_observed_total",
                "mbb_ci95_total_lower",
                "mbb_ci95_total_upper",
                "mbb_p_two_sided",
                "holm_p_two_sided",
                "holm_reject_5pct",
                "ordinary_p_two_sided",
                "dependence_sensitive_5pct",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "==================================================================="
    )
    print(
        " TAEC MINUS FIXED"
    )
    print(
        "==================================================================="
    )
    print(
        strategy_diff[
            [
                "model",
                "mbb_observed_total",
                "mbb_ci95_total_lower",
                "mbb_ci95_total_upper",
                "mbb_p_two_sided",
                "holm_p_two_sided",
                "holm_reject_5pct",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "==================================================================="
    )
    print(
        " PRE-COST MARKET CONVERGENCE"
    )
    print(
        "==================================================================="
    )
    print(
        convergence[
            [
                "model",
                "mbb_observed_total",
                "mbb_ci95_total_lower",
                "mbb_ci95_total_upper",
                "mbb_p_two_sided",
                "holm_p_two_sided",
                "holm_reject_5pct",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "==================================================================="
    )
    print(
        " SHARPE STRATEGY DIFFERENCES"
    )
    print(
        "==================================================================="
    )
    print(
        sharpe_diff[
            [
                "model",
                "mbb_observed_sharpe_difference",
                "mbb_ci95_lower",
                "mbb_ci95_upper",
                "mbb_p_two_sided",
                "holm_p_two_sided",
                "holm_reject_5pct",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "INTEGRITY CHECKS"
    )
    print(
        stage_checks.to_string(
            index=False
        )
    )

    if status != "PASS":
        raise RuntimeError(
            "Stage 4 acceptance gate failed."
        )


if __name__ == "__main__":
    main()
