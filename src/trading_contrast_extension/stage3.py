from __future__ import annotations

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd
from scipy.stats import norm

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.trading_contrast_extension import stage2 as s2


ROOT = Path(".")
S2 = ROOT / "outputs/trading_contrast_extension/stage2"
OUT = ROOT / "outputs/trading_contrast_extension/stage3"
OUT.mkdir(parents=True, exist_ok=True)

CANONICAL = (
    S2 / "canonical_four_model_event_panel.csv.gz"
)
FIXED_DAILY = (
    S2 / "fixed_strategy_daily_ledger.csv"
)
FIXED_POS = (
    S2 / "fixed_strategy_position_ledger.csv"
)
TAEC_DAILY = (
    S2 / "taec11_daily_ledger.csv"
)
TAEC_POS = (
    S2 / "taec11_position_ledger.csv.gz"
)
CHECKPOINTS = (
    S2 / "market_checkpoint_panel.csv"
)
RBF_PARAMS = (
    S2 / "explicit_rbf_predictive_parameters.csv"
)
EVENT_SOURCE = (
    ROOT
    / "data/processed/final_pipeline/market/"
    / "exact_common_event_panel.csv.gz"
)

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

PERIODS = [
    "market_development",
    "external_validation",
]

PRIMARY_H = 0.25
GREEK_STEPS = [
    0.25,
    0.5,
    1.0,
]

STRESS_SHIFTS = [
    -1.0,
    -0.5,
    -0.25,
    0.0,
    0.25,
    0.5,
    1.0,
]

FIXED_COST = 0.01
TAEC_COST = 0.02
FIXED_THRESHOLD = 0.15


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


def collapse_one(
    x: pd.DataFrame,
    column: str,
) -> pd.DataFrame:
    y = x[
        [
            "event_date",
            "decision_rule",
            column,
        ]
    ].copy()

    y[column] = pd.to_numeric(
        y[column],
        errors="coerce",
    )

    def one(s: pd.Series) -> float:
        vals = s.dropna().unique()

        if len(vals) == 0:
            return np.nan

        if len(vals) > 1:
            spread = float(
                np.max(vals)
                - np.min(vals)
            )

            if spread > 1e-10:
                raise RuntimeError(
                    f"{column}: multiple values within one date/rule."
                )

        return float(vals[0])

    return (
        y.groupby(
            [
                "event_date",
                "decision_rule",
            ],
            as_index=False,
        )
        .agg(
            **{
                column: (
                    column,
                    one,
                )
            }
        )
    )


def load_predictive_params() -> dict[str, pd.DataFrame]:
    source = pd.read_csv(
        EVENT_SOURCE
    )
    source = s2.normalize_date_rule(
        source
    )

    required = [
        "raw_temperature_c",
        "static_mean_c",
        "static_sd_c",
        "selected_gp_mean_c",
        "selected_gp_sd_c",
    ]

    missing = [
        c
        for c in required
        if c not in source.columns
    ]

    if missing:
        raise RuntimeError(
            "Missing frozen predictive parameter columns: "
            + repr(missing)
        )

    raw = collapse_one(
        source,
        "raw_temperature_c",
    ).rename(
        columns={
            "raw_temperature_c":
                "mean_c",
        }
    )

    raw["sd_c"] = np.nan

    static_mean = collapse_one(
        source,
        "static_mean_c",
    )
    static_sd = collapse_one(
        source,
        "static_sd_c",
    )

    static = static_mean.merge(
        static_sd,
        on=[
            "event_date",
            "decision_rule",
        ],
        how="inner",
        validate="one_to_one",
    ).rename(
        columns={
            "static_mean_c": "mean_c",
            "static_sd_c": "sd_c",
        }
    )

    matern_mean = collapse_one(
        source,
        "selected_gp_mean_c",
    )
    matern_sd = collapse_one(
        source,
        "selected_gp_sd_c",
    )

    matern = matern_mean.merge(
        matern_sd,
        on=[
            "event_date",
            "decision_rule",
        ],
        how="inner",
        validate="one_to_one",
    ).rename(
        columns={
            "selected_gp_mean_c":
                "mean_c",
            "selected_gp_sd_c":
                "sd_c",
        }
    )

    rbf = pd.read_csv(
        RBF_PARAMS
    )

    required_rbf = {
        "event_date",
        "decision_rule",
        "mean_c",
        "sd_c",
    }

    if not required_rbf.issubset(
        rbf.columns
    ):
        raise RuntimeError(
            "Explicit RBF parameter file has incomplete schema."
        )

    for model, pars in {
        "raw": raw,
        "static": static,
        "rbf": rbf,
        "matern32": matern,
    }.items():
        if pars.duplicated(
            [
                "event_date",
                "decision_rule",
            ]
        ).any():
            raise RuntimeError(
                f"{model}: duplicate predictive-law keys."
            )

        if model != "raw":
            if (
                pars["sd_c"].isna().any()
                or (
                    pd.to_numeric(
                        pars["sd_c"],
                        errors="coerce",
                    )
                    <= 0
                ).any()
            ):
                raise RuntimeError(
                    f"{model}: invalid predictive standard deviation."
                )

    return {
        "raw": raw,
        "static": static,
        "rbf": rbf,
        "matern32": matern,
    }


def shifted_probabilities(
    panel: pd.DataFrame,
    model: str,
    params: dict[str, pd.DataFrame],
    shift_c: float,
) -> pd.Series:
    p = params[model][
        [
            "event_date",
            "decision_rule",
            "mean_c",
            "sd_c",
        ]
    ].copy()

    merged = panel[
        [
            "event_date",
            "decision_rule",
            "event_lower_c",
            "event_upper_c",
        ]
    ].merge(
        p,
        on=[
            "event_date",
            "decision_rule",
        ],
        how="left",
        validate="many_to_one",
    )

    if merged["mean_c"].isna().any():
        raise RuntimeError(
            f"{model}: predictive mean missing after join."
        )

    mean = (
        merged["mean_c"].to_numpy(float)
        + float(shift_c)
    )

    lower = merged[
        "event_lower_c"
    ].to_numpy(float)

    upper = merged[
        "event_upper_c"
    ].to_numpy(float)

    if model == "raw":
        probs = (
            (mean >= lower)
            & (mean < upper)
        ).astype(float)
    else:
        sd = merged[
            "sd_c"
        ].to_numpy(float)

        probs = (
            norm.cdf(
                (upper - mean)
                / sd
            )
            - norm.cdf(
                (lower - mean)
                / sd
            )
        )

    return pd.Series(
        probs,
        index=panel.index,
        dtype=float,
    )


def probability_reconstruction_checks(
    canonical: pd.DataFrame,
    params: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = []

    for model in MODELS:
        reconstructed = shifted_probabilities(
            canonical,
            model,
            params,
            0.0,
        )

        observed = canonical[
            f"p_{model}"
        ].astype(float)

        diff = (
            reconstructed
            - observed
        ).abs()

        rows.append(
            {
                "model": model,
                "rows": int(
                    len(diff)
                ),
                "max_abs_error": float(
                    diff.max()
                ),
                "mean_abs_error": float(
                    diff.mean()
                ),
                "rows_error_gt_1e_8": int(
                    (
                        diff
                        > 1e-8
                    ).sum()
                ),
                "passed": bool(
                    float(
                        diff.max()
                    )
                    <= 1e-8
                ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    if not result["passed"].all():
        raise RuntimeError(
            "Frozen predictive-law reconstruction does not "
            "reproduce canonical probabilities:\n"
            + result.to_string(
                index=False
            )
        )

    return result


def max_drawdown_metrics(
    pnl: np.ndarray,
) -> tuple[float, int]:
    cumulative = np.cumsum(
        pnl
    )

    wealth = np.concatenate(
        [
            np.array([0.0]),
            cumulative,
        ]
    )

    running_peak = np.maximum.accumulate(
        wealth
    )

    drawdown = (
        running_peak
        - wealth
    )

    max_dd = float(
        np.max(drawdown)
    )

    duration = 0
    max_duration = 0

    for dd in drawdown[1:]:
        if dd > 1e-15:
            duration += 1
            max_duration = max(
                max_duration,
                duration,
            )
        else:
            duration = 0

    return (
        max_dd,
        int(max_duration),
    )


def safe_ratio(
    a: float,
    b: float,
) -> float:
    if abs(b) <= 1e-15:
        return np.nan

    return float(
        a / b
    )


def portfolio_position_tables() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    fixed = pd.read_csv(
        FIXED_POS
    )
    fixed["traded"] = as_bool(
        fixed["traded"]
    )

    fixed = fixed.loc[
        fixed["traded"]
    ].copy()

    fixed["strategy"] = (
        "fixed_settlement"
    )
    fixed["side"] = "YES"
    fixed[
        "transaction_cost"
    ] = FIXED_COST

    fixed[
        "entry_token_price"
    ] = pd.to_numeric(
        fixed[
            "market_entry_yes"
        ],
        errors="raise",
    )

    fixed[
        "exit_or_redemption_token_value"
    ] = pd.to_numeric(
        fixed[
            "realised_event"
        ],
        errors="raise",
    )

    fixed[
        "gross_cashflow_notional"
    ] = (
        fixed[
            "entry_token_price"
        ]
        + fixed[
            "exit_or_redemption_token_value"
        ]
    )

    taec = pd.read_csv(
        TAEC_POS
    )

    taec[
        "transaction_cost"
    ] = TAEC_COST

    taec[
        "entry_token_price"
    ] = np.where(
        taec["side"]
        == "YES",
        taec[
            "market_entry_yes_24h"
        ],
        1.0
        - taec[
            "market_entry_yes_24h"
        ],
    )

    taec[
        "exit_or_redemption_token_value"
    ] = np.where(
        taec["side"]
        == "YES",
        taec[
            "market_yes_exit"
        ],
        1.0
        - taec[
            "market_yes_exit"
        ],
    )

    taec[
        "gross_cashflow_notional"
    ] = (
        taec[
            "entry_token_price"
        ]
        + taec[
            "exit_or_redemption_token_value"
        ]
    )

    return fixed, taec


def combined_daily() -> pd.DataFrame:
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

    keep = [
        "event_date",
        "empirical_period",
        "strategy",
        "model",
        "active",
        "positions",
        "net_pnl",
        "entry_capital",
    ]

    all_daily = pd.concat(
        [
            fixed[keep],
            taec[keep],
        ],
        ignore_index=True,
    )

    all_daily[
        "event_date"
    ] = pd.to_datetime(
        all_daily[
            "event_date"
        ]
    )

    all_daily[
        "active"
    ] = as_bool(
        all_daily[
            "active"
        ]
    )

    return all_daily


def risk_table(
    daily: pd.DataFrame,
    fixed_pos: pd.DataFrame,
    taec_pos: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for (
        period,
        strategy,
        model,
    ), d in daily.groupby(
        [
            "empirical_period",
            "strategy",
            "model",
        ],
        sort=True,
    ):
        d = d.sort_values(
            "event_date"
        ).copy()

        p = (
            fixed_pos
            if strategy
            == "fixed_settlement"
            else taec_pos
        )

        p = p.loc[
            (
                p[
                    "empirical_period"
                ]
                == period
            )
            & (
                p[
                    "model"
                ]
                == model
            )
        ].copy()

        pnl = d[
            "net_pnl"
        ].to_numpy(float)

        total = float(
            pnl.sum()
        )

        mean = float(
            pnl.mean()
        )

        median = float(
            np.median(pnl)
        )

        sd = (
            float(
                np.std(
                    pnl,
                    ddof=1,
                )
            )
            if len(pnl) > 1
            else np.nan
        )

        sharpe = safe_ratio(
            mean,
            sd,
        )

        downside = np.minimum(
            pnl,
            0.0,
        )

        downside_dev = float(
            np.sqrt(
                np.mean(
                    downside ** 2
                )
            )
        )

        sortino = safe_ratio(
            mean,
            downside_dev,
        )

        q05 = float(
            np.quantile(
                pnl,
                0.05,
                method="linear",
            )
        )

        tail = pnl[
            pnl <= q05
            + 1e-15
        ]

        tail_mean = float(
            tail.mean()
        )

        var95_loss = max(
            0.0,
            -q05,
        )

        es95_loss = max(
            0.0,
            -tail_mean,
        )

        max_dd, dd_duration = (
            max_drawdown_metrics(
                pnl
            )
        )

        gross_profit = float(
            np.clip(
                pnl,
                0,
                None,
            ).sum()
        )

        gross_loss = float(
            np.clip(
                pnl,
                None,
                0,
            ).sum()
        )

        profit_factor = (
            np.inf
            if abs(
                gross_loss
            )
            <= 1e-15
            and gross_profit > 0
            else safe_ratio(
                gross_profit,
                abs(
                    gross_loss
                ),
            )
        )

        total_entry_capital = float(
            d[
                "entry_capital"
            ].sum()
        )

        roi = safe_ratio(
            total,
            total_entry_capital,
        )

        active = d.loc[
            d["active"]
        ]

        positive_daily = np.sort(
            pnl[
                pnl > 0
            ]
        )[::-1]

        top1_positive_share = (
            safe_ratio(
                float(
                    positive_daily[:1].sum()
                ),
                gross_profit,
            )
            if gross_profit > 0
            else np.nan
        )

        top3_positive_share = (
            safe_ratio(
                float(
                    positive_daily[:3].sum()
                ),
                gross_profit,
            )
            if gross_profit > 0
            else np.nan
        )

        abs_total = float(
            np.abs(pnl).sum()
        )

        top1_abs_share = safe_ratio(
            float(
                np.max(
                    np.abs(pnl)
                )
            ),
            abs_total,
        )

        position_count = int(
            len(p)
        )

        position_win_rate = (
            float(
                (
                    p[
                        "net_pnl"
                    ]
                    > 0
                ).mean()
            )
            if position_count
            else np.nan
        )

        mean_gain = (
            float(
                p.loc[
                    p[
                        "net_pnl"
                    ]
                    > 0,
                    "net_pnl",
                ].mean()
            )
            if (
                p[
                    "net_pnl"
                ]
                > 0
            ).any()
            else np.nan
        )

        mean_loss = (
            float(
                p.loc[
                    p[
                        "net_pnl"
                    ]
                    < 0,
                    "net_pnl",
                ].mean()
            )
            if (
                p[
                    "net_pnl"
                ]
                < 0
            ).any()
            else np.nan
        )

        yes_positions = int(
            (
                p[
                    "side"
                ]
                == "YES"
            ).sum()
        )

        no_positions = int(
            (
                p[
                    "side"
                ]
                == "NO"
            ).sum()
        )

        transaction_cost = float(
            p[
                "transaction_cost"
            ].sum()
        )

        gross_pre_cost_pnl = (
            total
            + transaction_cost
        )

        gross_notional = float(
            p[
                "gross_cashflow_notional"
            ].sum()
        )

        row = {
            "empirical_period":
                period,
            "strategy":
                strategy,
            "model":
                model,
            "dates":
                int(
                    d[
                        "event_date"
                    ].nunique()
                ),
            "active_dates":
                int(
                    d[
                        "active"
                    ].sum()
                ),
            "positions":
                position_count,
            "total_net_pnl":
                total,
            "gross_pre_cost_pnl":
                gross_pre_cost_pnl,
            "total_transaction_cost":
                transaction_cost,
            "transaction_cost_share_of_abs_gross_pre_cost_pnl":
                safe_ratio(
                    transaction_cost,
                    abs(
                        gross_pre_cost_pnl
                    ),
                ),
            "mean_daily_pnl":
                mean,
            "median_daily_pnl":
                median,
            "gross_profit_daily":
                gross_profit,
            "gross_loss_daily":
                gross_loss,
            "profit_factor_daily":
                profit_factor,
            "cumulative_entry_capital":
                total_entry_capital,
            "roi_on_entry_capital":
                roi,
            "mean_capital_per_active_date":
                (
                    float(
                        active[
                            "entry_capital"
                        ].mean()
                    )
                    if len(
                        active
                    )
                    else np.nan
                ),
            "max_capital_per_date":
                float(
                    d[
                        "entry_capital"
                    ].max()
                ),
            "gross_cashflow_notional":
                gross_notional,
            "daily_pnl_sd":
                sd,
            "nonannualised_sharpe":
                sharpe,
            "downside_deviation":
                downside_dev,
            "sortino":
                sortino,
            "pnl_quantile_05":
                q05,
            "empirical_var95_loss":
                var95_loss,
            "empirical_expected_shortfall95_loss":
                es95_loss,
            "worst_daily_loss":
                float(
                    pnl.min()
                ),
            "best_daily_pnl":
                float(
                    pnl.max()
                ),
            "maximum_drawdown":
                max_dd,
            "drawdown_duration_dates":
                dd_duration,
            "daily_win_rate":
                float(
                    (
                        pnl > 0
                    ).mean()
                ),
            "position_win_rate":
                position_win_rate,
            "mean_position_gain":
                mean_gain,
            "mean_position_loss":
                mean_loss,
            "mean_positions_per_active_date":
                (
                    float(
                        active[
                            "positions"
                        ].mean()
                    )
                    if len(
                        active
                    )
                    else 0.0
                ),
            "max_positions_per_date":
                int(
                    d[
                        "positions"
                    ].max()
                ),
            "yes_positions":
                yes_positions,
            "no_positions":
                no_positions,
            "yes_position_share":
                safe_ratio(
                    yes_positions,
                    position_count,
                ),
            "no_position_share":
                safe_ratio(
                    no_positions,
                    position_count,
                ),
            "top1_positive_day_share_of_gross_profit":
                top1_positive_share,
            "top3_positive_day_share_of_gross_profit":
                top3_positive_share,
            "top1_absolute_day_share_of_absolute_pnl":
                top1_abs_share,
            "largest_gross_exposure":
                float(
                    d[
                        "entry_capital"
                    ].max()
                ),
        }

        if strategy == "taec11":
            p[
                "target_hit"
            ] = as_bool(
                p[
                    "target_hit"
                ]
            )

            p[
                "forced_open_exit"
            ] = as_bool(
                p[
                    "forced_open_exit"
                ]
            )

            move = p[
                "signed_market_move_toward_model"
            ].to_numpy(float)

            row.update(
                {
                    "mean_gap_closed_fraction":
                        float(
                            p[
                                "gap_closed_fraction"
                            ].mean()
                        ),
                    "median_gap_closed_fraction":
                        float(
                            p[
                                "gap_closed_fraction"
                            ].median()
                        ),
                    "convergence_rate":
                        float(
                            (
                                move > 1e-15
                            ).mean()
                        ),
                    "divergence_rate":
                        float(
                            (
                                move < -1e-15
                            ).mean()
                        ),
                    "flat_move_rate":
                        float(
                            (
                                np.abs(
                                    move
                                )
                                <= 1e-15
                            ).mean()
                        ),
                    "mean_signed_market_move_toward_model":
                        float(
                            move.mean()
                        ),
                    "target_hit_rate":
                        float(
                            p[
                                "target_hit"
                            ].mean()
                        ),
                    "forced_open_exit_rate":
                        float(
                            p[
                                "forced_open_exit"
                            ].mean()
                        ),
                    "exit_12h_share":
                        float(
                            (
                                p[
                                    "exit_rule"
                                ]
                                == "12h_prior"
                            ).mean()
                        ),
                    "exit_6h_share":
                        float(
                            (
                                p[
                                    "exit_rule"
                                ]
                                == "6h_prior"
                            ).mean()
                        ),
                    "exit_open_share":
                        float(
                            (
                                p[
                                    "exit_rule"
                                ]
                                == "event_day_open"
                            ).mean()
                        ),
                }
            )
        else:
            for c in [
                "mean_gap_closed_fraction",
                "median_gap_closed_fraction",
                "convergence_rate",
                "divergence_rate",
                "flat_move_rate",
                "mean_signed_market_move_toward_model",
                "target_hit_rate",
                "forced_open_exit_rate",
                "exit_12h_share",
                "exit_6h_share",
                "exit_open_share",
            ]:
                row[c] = np.nan

        rows.append(
            row
        )

    return pd.DataFrame(
        rows
    )


def event_greeks(
    canonical: pd.DataFrame,
    params: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry = canonical.loc[
        canonical[
            "decision_rule"
        ]
        == "24h_prior"
    ].copy()

    rows = []
    mass_checks = []

    for model in MODELS:
        base = shifted_probabilities(
            entry,
            model,
            params,
            0.0,
        )

        for h in GREEK_STEPS:
            plus = shifted_probabilities(
                entry,
                model,
                params,
                h,
            )

            minus = shifted_probabilities(
                entry,
                model,
                params,
                -h,
            )

            delta = (
                plus
                - minus
            ) / (
                2.0
                * h
            )

            gamma = (
                plus
                - 2.0
                * base
                + minus
            ) / (
                h ** 2
            )

            z = entry[
                [
                    "event_date",
                    "empirical_period",
                    "contract_key",
                    "event_lower_c",
                    "event_upper_c",
                ]
            ].copy()

            z[
                "model"
            ] = model

            z[
                "temperature_step_c"
            ] = h

            z[
                "base_probability"
            ] = base.to_numpy()

            z[
                "probability_plus"
            ] = plus.to_numpy()

            z[
                "probability_minus"
            ] = minus.to_numpy()

            z[
                "probability_delta_per_c"
            ] = delta.to_numpy()

            z[
                "probability_gamma_per_c2"
            ] = gamma.to_numpy()

            rows.append(
                z
            )

            check = (
                z.groupby(
                    [
                        "event_date",
                        "empirical_period",
                    ]
                )
                .agg(
                    sum_delta=(
                        "probability_delta_per_c",
                        "sum",
                    ),
                    sum_gamma=(
                        "probability_gamma_per_c2",
                        "sum",
                    ),
                )
                .reset_index()
            )

            check[
                "model"
            ] = model

            check[
                "temperature_step_c"
            ] = h

            mass_checks.append(
                check
            )

    greeks = pd.concat(
        rows,
        ignore_index=True,
    )

    checks = pd.concat(
        mass_checks,
        ignore_index=True,
    )

    if (
        checks[
            "sum_delta"
        ].abs().max()
        > 1e-8
    ):
        raise RuntimeError(
            "Probability Delta mass does not sum to zero."
        )

    if (
        checks[
            "sum_gamma"
        ].abs().max()
        > 1e-8
    ):
        raise RuntimeError(
            "Probability Gamma mass does not sum to zero."
        )

    return greeks, checks


def portfolio_greeks(
    greeks: pd.DataFrame,
    daily: pd.DataFrame,
    fixed_pos: pd.DataFrame,
    taec_pos: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    g = greeks.loc[
        greeks[
            "temperature_step_c"
        ]
        == PRIMARY_H
    ].copy()

    position_frames = []

    f = fixed_pos[
        [
            "event_date",
            "empirical_period",
            "model",
            "contract_key",
            "side",
            "entry_capital",
        ]
    ].copy()

    f[
        "strategy"
    ] = "fixed_settlement"

    t = taec_pos[
        [
            "event_date",
            "empirical_period",
            "model",
            "contract_key",
            "side",
            "entry_capital",
        ]
    ].copy()

    t[
        "strategy"
    ] = "taec11"

    positions = pd.concat(
        [
            f,
            t,
        ],
        ignore_index=True,
    )

    joined = positions.merge(
        g[
            [
                "event_date",
                "empirical_period",
                "model",
                "contract_key",
                "probability_delta_per_c",
                "probability_gamma_per_c2",
            ]
        ],
        on=[
            "event_date",
            "empirical_period",
            "model",
            "contract_key",
        ],
        how="left",
        validate="many_to_one",
    )

    if (
        joined[
            "probability_delta_per_c"
        ].isna().any()
        or joined[
            "probability_gamma_per_c2"
        ].isna().any()
    ):
        raise RuntimeError(
            "Position-to-Greek join has missing values."
        )

    joined[
        "side_sign"
    ] = np.where(
        joined[
            "side"
        ]
        == "YES",
        1.0,
        -1.0,
    )

    joined[
        "position_delta_per_c"
    ] = (
        joined[
            "side_sign"
        ]
        * joined[
            "probability_delta_per_c"
        ]
    )

    joined[
        "position_gamma_per_c2"
    ] = (
        joined[
            "side_sign"
        ]
        * joined[
            "probability_gamma_per_c2"
        ]
    )

    joined[
        "abs_position_delta_per_c"
    ] = joined[
        "position_delta_per_c"
    ].abs()

    joined[
        "abs_position_gamma_per_c2"
    ] = joined[
        "position_gamma_per_c2"
    ].abs()

    agg = (
        joined.groupby(
            [
                "event_date",
                "empirical_period",
                "strategy",
                "model",
            ],
            as_index=False,
        )
        .agg(
            net_delta_per_c=(
                "position_delta_per_c",
                "sum",
            ),
            gross_abs_delta_per_c=(
                "abs_position_delta_per_c",
                "sum",
            ),
            net_gamma_per_c2=(
                "position_gamma_per_c2",
                "sum",
            ),
            gross_abs_gamma_per_c2=(
                "abs_position_gamma_per_c2",
                "sum",
            ),
        )
    )

    support = daily[
        [
            "event_date",
            "empirical_period",
            "strategy",
            "model",
            "entry_capital",
        ]
    ].copy()

    support[
        "event_date"
    ] = support[
        "event_date"
    ].dt.strftime(
        "%Y-%m-%d"
    )

    daily_greek = support.merge(
        agg,
        on=[
            "event_date",
            "empirical_period",
            "strategy",
            "model",
        ],
        how="left",
        validate="one_to_one",
    )

    fill = [
        "net_delta_per_c",
        "gross_abs_delta_per_c",
        "net_gamma_per_c2",
        "gross_abs_gamma_per_c2",
    ]

    daily_greek[
        fill
    ] = daily_greek[
        fill
    ].fillna(
        0.0
    )

    daily_greek[
        "gross_delta_per_unit_entry_capital"
    ] = np.where(
        daily_greek[
            "entry_capital"
        ]
        > 0,
        daily_greek[
            "gross_abs_delta_per_c"
        ]
        / daily_greek[
            "entry_capital"
        ],
        np.nan,
    )

    daily_greek[
        "gross_gamma_per_unit_entry_capital"
    ] = np.where(
        daily_greek[
            "entry_capital"
        ]
        > 0,
        daily_greek[
            "gross_abs_gamma_per_c2"
        ]
        / daily_greek[
            "entry_capital"
        ],
        np.nan,
    )

    summary = (
        daily_greek.groupby(
            [
                "empirical_period",
                "strategy",
                "model",
            ],
            as_index=False,
        )
        .agg(
            mean_net_delta_per_c=(
                "net_delta_per_c",
                "mean",
            ),
            mean_abs_net_delta_per_c=(
                "net_delta_per_c",
                lambda s: float(
                    np.abs(
                        s
                    ).mean()
                ),
            ),
            max_abs_net_delta_per_c=(
                "net_delta_per_c",
                lambda s: float(
                    np.abs(
                        s
                    ).max()
                ),
            ),
            mean_gross_abs_delta_per_c=(
                "gross_abs_delta_per_c",
                "mean",
            ),
            max_gross_abs_delta_per_c=(
                "gross_abs_delta_per_c",
                "max",
            ),
            mean_net_gamma_per_c2=(
                "net_gamma_per_c2",
                "mean",
            ),
            mean_abs_net_gamma_per_c2=(
                "net_gamma_per_c2",
                lambda s: float(
                    np.abs(
                        s
                    ).mean()
                ),
            ),
            max_abs_net_gamma_per_c2=(
                "net_gamma_per_c2",
                lambda s: float(
                    np.abs(
                        s
                    ).max()
                ),
            ),
            mean_gross_abs_gamma_per_c2=(
                "gross_abs_gamma_per_c2",
                "mean",
            ),
            max_gross_abs_gamma_per_c2=(
                "gross_abs_gamma_per_c2",
                "max",
            ),
            mean_gross_delta_per_unit_entry_capital=(
                "gross_delta_per_unit_entry_capital",
                "mean",
            ),
            mean_gross_gamma_per_unit_entry_capital=(
                "gross_gamma_per_unit_entry_capital",
                "mean",
            ),
        )
    )

    side_summary = (
        joined.groupby(
            [
                "empirical_period",
                "strategy",
                "model",
                "side",
            ],
            as_index=False,
        )
        .agg(
            positions=(
                "contract_key",
                "size",
            ),
            gross_abs_delta_per_c=(
                "abs_position_delta_per_c",
                "sum",
            ),
            net_delta_per_c=(
                "position_delta_per_c",
                "sum",
            ),
            gross_abs_gamma_per_c2=(
                "abs_position_gamma_per_c2",
                "sum",
            ),
            net_gamma_per_c2=(
                "position_gamma_per_c2",
                "sum",
            ),
        )
    )

    return (
        joined,
        daily_greek,
        summary,
        side_summary,
    )


def fixed_stress_positions(
    entry: pd.DataFrame,
    model: str,
    q: pd.Series,
) -> pd.DataFrame:
    z = entry[
        [
            "event_date",
            "empirical_period",
            "contract_key",
            "market_raw_yes",
            "realised_event",
        ]
    ].copy()

    z[
        "model_probability"
    ] = q.to_numpy()

    rows = []

    for (
        date,
        period,
    ), book in z.groupby(
        [
            "event_date",
            "empirical_period",
        ],
        sort=True,
    ):
        b = book.copy()

        b[
            "edge"
        ] = (
            b[
                "model_probability"
            ]
            - b[
                "market_raw_yes"
            ]
        )

        idx = b[
            "edge"
        ].idxmax()

        r = b.loc[
            idx
        ]

        traded = bool(
            float(
                r[
                    "edge"
                ]
            )
            > FIXED_THRESHOLD
        )

        rows.append(
            {
                "event_date": date,
                "empirical_period":
                    period,
                "model":
                    model,
                "contract_key":
                    r[
                        "contract_key"
                    ],
                "side":
                    (
                        "YES"
                        if traded
                        else "NO_TRADE"
                    ),
                "traded":
                    traded,
                "net_pnl":
                    (
                        float(
                            r[
                                "realised_event"
                            ]
                        )
                        - float(
                            r[
                                "market_raw_yes"
                            ]
                        )
                        - FIXED_COST
                        if traded
                        else 0.0
                    ),
                "entry_capital":
                    (
                        float(
                            r[
                                "market_raw_yes"
                            ]
                        )
                        + FIXED_COST
                        if traded
                        else 0.0
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def taec_stress_positions(
    entry: pd.DataFrame,
    checkpoints: pd.DataFrame,
    model: str,
    q: pd.Series,
) -> pd.DataFrame:
    model_entry = entry[
        [
            "event_date",
            "empirical_period",
            "contract_key",
        ]
    ].copy()

    model_entry[
        "q"
    ] = q.to_numpy()

    cp = checkpoints.loc[
        checkpoints[
            "taec_date_eligible"
        ]
    ].copy()

    z = cp.merge(
        model_entry,
        on=[
            "event_date",
            "empirical_period",
            "contract_key",
        ],
        how="inner",
        validate="one_to_one",
    )

    rows = []

    for r in z.to_dict(
        orient="records"
    ):
        qv = float(
            r["q"]
        )

        p24 = float(
            r["24h_prior"]
        )

        gap = (
            qv
            - p24
        )

        if abs(
            gap
        ) <= TAEC_COST:
            continue

        if gap > 0:
            side = "YES"
            sign = 1.0
        else:
            side = "NO"
            sign = -1.0

        exit_rule = None
        exit_price = None

        for rule in [
            "12h_prior",
            "6h_prior",
            "event_day_open",
        ]:
            pt = float(
                r[rule]
            )

            crossed = (
                pt >= qv
                if side
                == "YES"
                else pt <= qv
            )

            if crossed:
                exit_rule = rule
                exit_price = pt
                break

        if exit_rule is None:
            exit_rule = (
                "event_day_open"
            )
            exit_price = float(
                r[
                    "event_day_open"
                ]
            )

        pnl = (
            sign
            * (
                exit_price
                - p24
            )
            - TAEC_COST
        )

        entry_token = (
            p24
            if side == "YES"
            else 1.0 - p24
        )

        rows.append(
            {
                "event_date":
                    r[
                        "event_date"
                    ],
                "empirical_period":
                    r[
                        "empirical_period"
                    ],
                "model":
                    model,
                "contract_key":
                    r[
                        "contract_key"
                    ],
                "side":
                    side,
                "traded":
                    True,
                "exit_rule":
                    exit_rule,
                "net_pnl":
                    pnl,
                "entry_capital":
                    (
                        entry_token
                        + FIXED_COST
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def stress_engine(
    canonical: pd.DataFrame,
    params: dict[str, pd.DataFrame],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    entry = canonical.loc[
        canonical[
            "decision_rule"
        ]
        == "24h_prior"
    ].copy()

    checkpoints = pd.read_csv(
        CHECKPOINTS
    )

    summary_rows = []
    position_frames = []

    for shift in STRESS_SHIFTS:
        for model in MODELS:
            q = shifted_probabilities(
                entry,
                model,
                params,
                shift,
            )

            fixed = fixed_stress_positions(
                entry,
                model,
                q,
            )

            fixed[
                "temperature_shift_c"
            ] = shift

            fixed[
                "strategy"
            ] = "fixed_settlement"

            position_frames.append(
                fixed
            )

            taec = taec_stress_positions(
                entry,
                checkpoints,
                model,
                q,
            )

            taec[
                "temperature_shift_c"
            ] = shift

            taec[
                "strategy"
            ] = "taec11"

            position_frames.append(
                taec
            )

            for strategy, x in [
                (
                    "fixed_settlement",
                    fixed,
                ),
                (
                    "taec11",
                    taec,
                ),
            ]:
                for period in PERIODS:
                    xp = x.loc[
                        x[
                            "empirical_period"
                        ]
                        == period
                    ].copy()

                    if strategy == "fixed_settlement":
                        active_dates = int(
                            xp[
                                "traded"
                            ].sum()
                        )
                        positions = active_dates
                    else:
                        positions = int(
                            len(
                                xp
                            )
                        )
                        active_dates = int(
                            xp.loc[
                                xp[
                                    "traded"
                                ],
                                "event_date",
                            ].nunique()
                        )

                    summary_rows.append(
                        {
                            "empirical_period":
                                period,
                            "strategy":
                                strategy,
                            "model":
                                model,
                            "temperature_shift_c":
                                shift,
                            "positions":
                                positions,
                            "active_dates":
                                active_dates,
                            "total_net_pnl":
                                float(
                                    xp[
                                        "net_pnl"
                                    ].sum()
                                ),
                            "total_entry_capital":
                                float(
                                    xp[
                                        "entry_capital"
                                    ].sum()
                                ),
                        }
                    )

    summary = pd.DataFrame(
        summary_rows
    )

    positions = pd.concat(
        position_frames,
        ignore_index=True,
    )

    baseline = summary.loc[
        summary[
            "temperature_shift_c"
        ]
        == 0.0,
        [
            "empirical_period",
            "strategy",
            "model",
            "total_net_pnl",
            "positions",
        ],
    ].rename(
        columns={
            "total_net_pnl":
                "baseline_total_net_pnl",
            "positions":
                "baseline_positions",
        }
    )

    summary = summary.merge(
        baseline,
        on=[
            "empirical_period",
            "strategy",
            "model",
        ],
        how="left",
        validate="many_to_one",
    )

    summary[
        "pnl_change_from_zero_shift"
    ] = (
        summary[
            "total_net_pnl"
        ]
        - summary[
            "baseline_total_net_pnl"
        ]
    )

    summary[
        "position_change_from_zero_shift"
    ] = (
        summary[
            "positions"
        ]
        - summary[
            "baseline_positions"
        ]
    )

    instability_rows = []

    for (
        period,
        strategy,
        model,
    ), x in positions.groupby(
        [
            "empirical_period",
            "strategy",
            "model",
        ]
    ):
        base = x.loc[
            x[
                "temperature_shift_c"
            ]
            == 0.0
        ].copy()

        if strategy == "fixed_settlement":
            base = base.loc[
                base[
                    "traded"
                ]
            ]

        base_set = set(
            zip(
                base[
                    "event_date"
                ].astype(str),
                base[
                    "contract_key"
                ].astype(str),
                base[
                    "side"
                ].astype(str),
            )
        )

        for shift in STRESS_SHIFTS:
            y = x.loc[
                x[
                    "temperature_shift_c"
                ]
                == shift
            ].copy()

            if strategy == "fixed_settlement":
                y = y.loc[
                    y[
                        "traded"
                    ]
                ]

            current = set(
                zip(
                    y[
                        "event_date"
                    ].astype(str),
                    y[
                        "contract_key"
                    ].astype(str),
                    y[
                        "side"
                    ].astype(str),
                )
            )

            intersection = len(
                base_set
                & current
            )

            union = len(
                base_set
                | current
            )

            instability_rows.append(
                {
                    "empirical_period":
                        period,
                    "strategy":
                        strategy,
                    "model":
                        model,
                    "temperature_shift_c":
                        shift,
                    "baseline_positions":
                        len(
                            base_set
                        ),
                    "shifted_positions":
                        len(
                            current
                        ),
                    "shared_positions":
                        intersection,
                    "added_positions":
                        len(
                            current
                            - base_set
                        ),
                    "removed_positions":
                        len(
                            base_set
                            - current
                        ),
                    "position_set_jaccard":
                        (
                            intersection
                            / union
                            if union
                            else 1.0
                        ),
                }
            )

    instability = pd.DataFrame(
        instability_rows
    )

    sensitivity_rows = []

    for (
        period,
        strategy,
        model,
    ), x in summary.groupby(
        [
            "empirical_period",
            "strategy",
            "model",
        ]
    ):
        by_shift = {
            float(
                r[
                    "temperature_shift_c"
                ]
            ):
                float(
                    r[
                        "total_net_pnl"
                    ]
                )
            for _, r in x.iterrows()
        }

        base_pnl = by_shift[
            0.0
        ]

        for h in GREEK_STEPS:
            plus = by_shift[
                h
            ]
            minus = by_shift[
                -h
            ]

            sensitivity_rows.append(
                {
                    "empirical_period":
                        period,
                    "strategy":
                        strategy,
                    "model":
                        model,
                    "temperature_step_c":
                        h,
                    "baseline_total_net_pnl":
                        base_pnl,
                    "pnl_plus":
                        plus,
                    "pnl_minus":
                        minus,
                    "full_policy_pnl_delta_per_c":
                        (
                            plus
                            - minus
                        )
                        / (
                            2.0
                            * h
                        ),
                    "full_policy_pnl_gamma_per_c2":
                        (
                            plus
                            - 2.0
                            * base_pnl
                            + minus
                        )
                        / (
                            h ** 2
                        ),
                }
            )

    sensitivity = pd.DataFrame(
        sensitivity_rows
    )

    return (
        summary,
        instability,
        sensitivity,
    )


def figures(
    daily: pd.DataFrame,
    risk: pd.DataFrame,
    greek_summary: pd.DataFrame,
) -> None:
    ext = daily.loc[
        daily[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    for strategy in STRATEGIES:
        x = ext.loc[
            ext[
                "strategy"
            ]
            == strategy
        ].copy()

        fig, ax = plt.subplots(
            figsize=(
                9,
                5,
            )
        )

        for model in MODELS:
            m = (
                x.loc[
                    x[
                        "model"
                    ]
                    == model
                ]
                .sort_values(
                    "event_date"
                )
            )

            ax.plot(
                m[
                    "event_date"
                ],
                m[
                    "net_pnl"
                ].cumsum(),
                label=model,
            )

        ax.set_title(
            f"External cumulative PnL — {strategy}"
        )
        ax.set_xlabel(
            "Settlement date"
        )
        ax.set_ylabel(
            "Cumulative net PnL"
        )
        ax.legend()
        fig.autofmt_xdate()
        fig.tight_layout()

        fig.savefig(
            OUT
            / f"external_cumulative_pnl_{strategy}.png",
            dpi=180,
        )

        plt.close(
            fig
        )

    r = risk.loc[
        risk[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    for _, row in r.iterrows():
        ax.scatter(
            row[
                "daily_pnl_sd"
            ],
            row[
                "total_net_pnl"
            ],
        )

        ax.annotate(
            f"{row['strategy']}:{row['model']}",
            (
                row[
                    "daily_pnl_sd"
                ],
                row[
                    "total_net_pnl"
                ],
            ),
            fontsize=8,
        )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.set_title(
        "External risk-return comparison"
    )
    ax.set_xlabel(
        "Daily PnL standard deviation"
    )
    ax.set_ylabel(
        "Total net PnL"
    )
    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_risk_return_scatter.png",
        dpi=180,
    )

    plt.close(
        fig
    )

    g = greek_summary.loc[
        greek_summary[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    g[
        "portfolio"
    ] = (
        g[
            "strategy"
        ]
        + ":"
        + g[
            "model"
        ]
    )

    fig, ax = plt.subplots(
        figsize=(
            10,
            5,
        )
    )

    ax.bar(
        g[
            "portfolio"
        ],
        g[
            "mean_gross_abs_delta_per_c"
        ],
    )

    ax.set_title(
        "External mean gross probability Delta exposure"
    )
    ax.set_xlabel(
        "Portfolio"
    )
    ax.set_ylabel(
        "Mean gross |Delta| per degree C"
    )
    ax.tick_params(
        axis="x",
        rotation=45,
    )
    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_gross_probability_delta.png",
        dpi=180,
    )

    plt.close(
        fig
    )

    taec = r.loc[
        r[
            "strategy"
        ]
        == "taec11"
    ].copy()

    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    positions = np.arange(
        len(
            taec
        )
    )

    width = 0.35

    ax.bar(
        positions
        - width
        / 2,
        taec[
            "convergence_rate"
        ],
        width=width,
        label="positive move toward model",
    )

    ax.bar(
        positions
        + width
        / 2,
        taec[
            "forced_open_exit_rate"
        ],
        width=width,
        label="forced open exit",
    )

    ax.set_xticks(
        positions
    )

    ax.set_xticklabels(
        taec[
            "model"
        ]
    )

    ax.set_ylim(
        0,
        1,
    )

    ax.set_title(
        "External TAEC convergence diagnostics"
    )
    ax.set_ylabel(
        "Fraction of positions"
    )
    ax.legend()
    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_taec_convergence_diagnostics.png",
        dpi=180,
    )

    plt.close(
        fig
    )


def main() -> None:
    canonical = pd.read_csv(
        CANONICAL
    )

    params = load_predictive_params()

    reconstruction = (
        probability_reconstruction_checks(
            canonical,
            params,
        )
    )

    reconstruction.to_csv(
        OUT
        / "probability_reconstruction_checks.csv",
        index=False,
    )

    daily = combined_daily()

    fixed_pos, taec_pos = (
        portfolio_position_tables()
    )

    risk = risk_table(
        daily,
        fixed_pos,
        taec_pos,
    )

    risk.to_csv(
        OUT
        / "portfolio_risk_performance_summary.csv",
        index=False,
    )

    external_risk = risk.loc[
        risk[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    external_risk.to_csv(
        OUT
        / "external_eight_portfolio_risk_table.csv",
        index=False,
    )

    greeks, mass_checks = (
        event_greeks(
            canonical,
            params,
        )
    )

    greeks.to_csv(
        OUT
        / "event_probability_greeks.csv.gz",
        index=False,
        compression="gzip",
    )

    mass_checks.to_csv(
        OUT
        / "greek_probability_mass_checks.csv",
        index=False,
    )

    (
        position_greeks,
        daily_greeks,
        greek_summary,
        side_greeks,
    ) = portfolio_greeks(
        greeks,
        daily,
        fixed_pos,
        taec_pos,
    )

    position_greeks.to_csv(
        OUT
        / "position_greek_exposures.csv.gz",
        index=False,
        compression="gzip",
    )

    daily_greeks.to_csv(
        OUT
        / "daily_portfolio_greek_exposures.csv",
        index=False,
    )

    greek_summary.to_csv(
        OUT
        / "portfolio_greek_risk_summary.csv",
        index=False,
    )

    side_greeks.to_csv(
        OUT
        / "portfolio_greek_side_summary.csv",
        index=False,
    )

    (
        stress_summary,
        instability,
        pnl_sensitivity,
    ) = stress_engine(
        canonical,
        params,
    )

    stress_summary.to_csv(
        OUT
        / "temperature_stress_policy_summary.csv",
        index=False,
    )

    instability.to_csv(
        OUT
        / "temperature_stress_position_instability.csv",
        index=False,
    )

    pnl_sensitivity.to_csv(
        OUT
        / "policy_pnl_temperature_sensitivity.csv",
        index=False,
    )

    figures(
        daily,
        risk,
        greek_summary,
    )

    # Stage-2 PnL reconciliation.
    s2_fixed = pd.read_csv(
        S2
        / "fixed_strategy_stage2_summary.csv"
    )

    s2_taec = pd.read_csv(
        S2
        / "taec11_stage2_summary.csv"
    )

    s2_combined = pd.concat(
        [
            s2_fixed.assign(
                strategy="fixed_settlement"
            ),
            s2_taec.assign(
                strategy="taec11"
            ),
        ],
        ignore_index=True,
    )

    reconcile = risk.merge(
        s2_combined[
            [
                "empirical_period",
                "strategy",
                "model",
                "total_net_pnl",
            ]
        ].rename(
            columns={
                "total_net_pnl":
                    "stage2_total_net_pnl",
            }
        ),
        on=[
            "empirical_period",
            "strategy",
            "model",
        ],
        how="left",
        validate="one_to_one",
    )

    reconcile[
        "absolute_pnl_difference"
    ] = (
        reconcile[
            "total_net_pnl"
        ]
        - reconcile[
            "stage2_total_net_pnl"
        ]
    ).abs()

    reconcile[
        "passed"
    ] = (
        reconcile[
            "absolute_pnl_difference"
        ]
        <= 1e-10
    )

    reconcile[
        [
            "empirical_period",
            "strategy",
            "model",
            "total_net_pnl",
            "stage2_total_net_pnl",
            "absolute_pnl_difference",
            "passed",
        ]
    ].to_csv(
        OUT
        / "stage2_stage3_pnl_reconciliation.csv",
        index=False,
    )

    if not reconcile[
        "passed"
    ].all():
        raise RuntimeError(
            "Stage-3 risk table does not reconcile to Stage 2."
        )

    # Zero-shift stress must reproduce Stage-2 PnL.
    zero_stress = stress_summary.loc[
        stress_summary[
            "temperature_shift_c"
        ]
        == 0.0
    ].copy()

    zero_check = zero_stress.merge(
        risk[
            [
                "empirical_period",
                "strategy",
                "model",
                "total_net_pnl",
            ]
        ].rename(
            columns={
                "total_net_pnl":
                    "risk_total_net_pnl",
            }
        ),
        on=[
            "empirical_period",
            "strategy",
            "model",
        ],
        how="left",
        validate="one_to_one",
    )

    zero_check[
        "absolute_difference"
    ] = (
        zero_check[
            "total_net_pnl"
        ]
        - zero_check[
            "risk_total_net_pnl"
        ]
    ).abs()

    zero_check[
        "passed"
    ] = (
        zero_check[
            "absolute_difference"
        ]
        <= 1e-10
    )

    zero_check.to_csv(
        OUT
        / "zero_shift_policy_reproduction.csv",
        index=False,
    )

    if not zero_check[
        "passed"
    ].all():
        raise RuntimeError(
            "Zero-shift stress engine does not reproduce baseline policies."
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
                "check": check,
                "passed": bool(
                    passed
                ),
                "observed": observed,
                "expected": expected,
                "note": note,
            }
        )

    add(
        "probability_reconstruction",
        bool(
            reconstruction[
                "passed"
            ].all()
        ),
        reconstruction.to_dict(
            orient="records"
        ),
        "all models max error <= 1e-8",
    )

    add(
        "risk_rows_16",
        len(
            risk
        )
        == 16,
        len(
            risk
        ),
        16,
    )

    add(
        "external_eight_portfolios",
        len(
            external_risk
        )
        == 8,
        len(
            external_risk
        ),
        8,
    )

    add(
        "pnl_reconciliation",
        bool(
            reconcile[
                "passed"
            ].all()
        ),
        float(
            reconcile[
                "absolute_pnl_difference"
            ].max()
        ),
        "<=1e-10",
    )

    add(
        "greek_delta_mass_zero",
        float(
            mass_checks[
                "sum_delta"
            ].abs().max()
        )
        <= 1e-8,
        float(
            mass_checks[
                "sum_delta"
            ].abs().max()
        ),
        "<=1e-8",
    )

    add(
        "greek_gamma_mass_zero",
        float(
            mass_checks[
                "sum_gamma"
            ].abs().max()
        )
        <= 1e-8,
        float(
            mass_checks[
                "sum_gamma"
            ].abs().max()
        ),
        "<=1e-8",
    )

    add(
        "portfolio_greek_rows",
        len(
            greek_summary
        )
        == 16,
        len(
            greek_summary
        ),
        16,
    )

    add(
        "stress_shift_grid",
        sorted(
            stress_summary[
                "temperature_shift_c"
            ].unique().tolist()
        )
        == STRESS_SHIFTS,
        sorted(
            stress_summary[
                "temperature_shift_c"
            ].unique().tolist()
        ),
        STRESS_SHIFTS,
    )

    add(
        "zero_shift_reproduces_policy",
        bool(
            zero_check[
                "passed"
            ].all()
        ),
        float(
            zero_check[
                "absolute_difference"
            ].max()
        ),
        "<=1e-10",
    )

    add(
        "rbf_distinct_from_static",
        bool(
            (
                (
                    canonical[
                        "p_rbf"
                    ]
                    - canonical[
                        "p_static"
                    ]
                ).abs()
                > 1e-12
            ).any()
        ),
        float(
            (
                canonical[
                    "p_rbf"
                ]
                - canonical[
                    "p_static"
                ]
            ).abs().max()
        ),
        ">1e-12",
    )

    stage_checks = pd.DataFrame(
        checks
    )

    stage_checks.to_csv(
        OUT
        / "stage3_integrity_checks.csv",
        index=False,
    )

    status = (
        "PASS"
        if stage_checks[
            "passed"
        ].all()
        else "FAILED"
    )

    headline_columns = [
        "empirical_period",
        "strategy",
        "model",
        "total_net_pnl",
        "gross_pre_cost_pnl",
        "total_transaction_cost",
        "roi_on_entry_capital",
        "daily_pnl_sd",
        "nonannualised_sharpe",
        "sortino",
        "empirical_var95_loss",
        "empirical_expected_shortfall95_loss",
        "maximum_drawdown",
        "positions",
        "active_dates",
        "convergence_rate",
        "forced_open_exit_rate",
    ]

    headline = external_risk[
        headline_columns
    ].to_dict(
        orient="records"
    )

    ext_greek = greek_summary.loc[
        greek_summary[
            "empirical_period"
        ]
        == "external_validation"
    ].to_dict(
        orient="records"
    )

    ext_stress = pnl_sensitivity.loc[
        pnl_sensitivity[
            "empirical_period"
        ]
        == "external_validation"
    ].to_dict(
        orient="records"
    )

    summary = {
        "status":
            status,
        "stage":
            3,
        "stage_name":
            (
                "performance_risk_convergence_"
                "and_greek_like_analytics"
            ),
        "portfolios":
            8,
        "periods":
            PERIODS,
        "primary_greek_step_c":
            PRIMARY_H,
        "greek_robustness_steps_c":
            GREEK_STEPS,
        "temperature_stress_grid_c":
            STRESS_SHIFTS,
        "greek_interpretation":
            (
                "Finite-difference forecast-probability sensitivity "
                "to a local temperature-location perturbation; not "
                "Black-Scholes option Greeks."
            ),
        "external_headline":
            headline,
        "external_greek_summary":
            ext_greek,
        "external_policy_pnl_temperature_sensitivity":
            ext_stress,
        "next_stage":
            (
                "common-support moving-block bootstrap inference, "
                "multiplicity-adjusted model/strategy contrasts and "
                "market-convergence tests"
            ),
    }

    (
        OUT
        / "stage3_summary.json"
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
        " STAGE 3 EXTERNAL RISK / PERFORMANCE"
    )
    print(
        "==================================================================="
    )
    print(
        external_risk[
            [
                "strategy",
                "model",
                "total_net_pnl",
                "gross_pre_cost_pnl",
                "total_transaction_cost",
                "roi_on_entry_capital",
                "nonannualised_sharpe",
                "sortino",
                "empirical_var95_loss",
                "empirical_expected_shortfall95_loss",
                "maximum_drawdown",
                "positions",
                "convergence_rate",
                "forced_open_exit_rate",
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
        " STAGE 3 EXTERNAL GREEK-LIKE RISK"
    )
    print(
        "==================================================================="
    )
    print(
        greek_summary.loc[
            greek_summary[
                "empirical_period"
            ]
            == "external_validation"
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
            "Stage 3 acceptance gate failed."
        )


if __name__ == "__main__":
    main()
