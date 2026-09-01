from __future__ import annotations

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
S4 = ROOT / "outputs/trading_contrast_extension/stage4"
OUT = ROOT / "outputs/trading_contrast_extension/stage5"
OUT.mkdir(parents=True, exist_ok=True)

CANONICAL = S2 / "canonical_four_model_event_panel.csv.gz"
CHECKPOINTS = S2 / "market_checkpoint_panel.csv"
FIXED_POS = S2 / "fixed_strategy_position_ledger.csv"
FIXED_DAILY = S2 / "fixed_strategy_daily_ledger.csv"
TAEC_POS = S2 / "taec11_position_ledger.csv.gz"
TAEC_DAILY = S2 / "taec11_daily_ledger.csv"
COMMON = S4 / "external_common_support_daily_panel.csv"
STRESS = S3 / "temperature_stress_policy_summary.csv"
INSTABILITY = S3 / "temperature_stress_position_instability.csv"

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

BASELINE_FIXED_COST = 0.01
BASELINE_TAEC_COST = 0.02

COST_GRID = [
    0.0,
    0.0025,
    0.005,
    0.0075,
    0.01,
    0.015,
    0.02,
    0.025,
    0.03,
    0.04,
    0.05,
]

TAEC_THRESHOLD_GRID = [
    0.01,
    0.015,
    0.02,
    0.025,
    0.03,
    0.04,
    0.05,
    0.075,
    0.10,
    0.15,
]

BLOCK_LENGTH_GRID = [
    3,
    5,
    7,
    10,
    14,
]

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


def safe_ratio(
    numerator: float,
    denominator: float,
) -> float:
    if abs(
        denominator
    ) <= 1e-15:
        return np.nan

    return float(
        numerator
        / denominator
    )


def sharpe(x: np.ndarray) -> float:
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


def seed_for(
    label: str,
) -> int:
    digest = hashlib.sha256(
        f"{BASE_SEED}|{label}".encode(
            "utf-8"
        )
    ).digest()

    return int.from_bytes(
        digest[:4],
        "big",
        signed=False,
    )


def moving_block_indices(
    n: int,
    block_length: int,
    reps: int,
    label: str,
) -> np.ndarray:
    if block_length > n:
        raise RuntimeError(
            "Block length exceeds sample length."
        )

    rng = np.random.default_rng(
        seed_for(
            label
        )
    )

    blocks_needed = int(
        math.ceil(
            n
            / block_length
        )
    )

    starts = rng.integers(
        0,
        n
        - block_length
        + 1,
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


def centered_mean_bootstrap(
    x: np.ndarray,
    block_length: int,
    label: str,
) -> dict[str, float]:
    x = np.asarray(
        x,
        dtype=float,
    )

    n = len(
        x
    )

    observed = float(
        np.mean(
            x
        )
    )

    idx = moving_block_indices(
        n,
        block_length,
        BOOTSTRAP_REPS,
        label,
    )

    centered = (
        x
        - observed
    )

    null_means = np.mean(
        centered[
            idx
        ],
        axis=1,
    )

    critical = float(
        np.quantile(
            np.abs(
                null_means
            ),
            1.0 - ALPHA,
        )
    )

    p = (
        1
        + int(
            np.sum(
                np.abs(
                    null_means
                )
                >= abs(
                    observed
                )
                - 1e-15
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
            observed,
        "observed_total":
            float(
                np.sum(
                    x
                )
            ),
        "ci95_total_lower":
            float(
                (
                    observed
                    - critical
                )
                * n
            ),
        "ci95_total_upper":
            float(
                (
                    observed
                    + critical
                )
                * n
            ),
        "p_two_sided":
            float(
                p
            ),
    }


def load_position_components() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    fixed = pd.read_csv(
        FIXED_POS
    )

    fixed[
        "traded"
    ] = as_bool(
        fixed[
            "traded"
        ]
    )

    fixed = fixed.loc[
        fixed[
            "traded"
        ]
    ].copy()

    fixed[
        "strategy"
    ] = "fixed_settlement"

    fixed[
        "gross_pre_cost_pnl"
    ] = (
        pd.to_numeric(
            fixed[
                "realised_event"
            ],
            errors="raise",
        )
        - pd.to_numeric(
            fixed[
                "market_entry_yes"
            ],
            errors="raise",
        )
    )

    fixed[
        "baseline_cost_per_position"
    ] = BASELINE_FIXED_COST

    taec = pd.read_csv(
        TAEC_POS
    )

    taec[
        "strategy"
    ] = "taec11"

    taec[
        "gross_pre_cost_pnl"
    ] = pd.to_numeric(
        taec[
            "signed_market_move_toward_model"
        ],
        errors="raise",
    )

    taec[
        "baseline_cost_per_position"
    ] = BASELINE_TAEC_COST

    return (
        fixed,
        taec,
    )


def cost_sensitivity(
    fixed: pd.DataFrame,
    taec: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    rows = []
    breaks = []

    for strategy, p in [
        (
            "fixed_settlement",
            fixed,
        ),
        (
            "taec11",
            taec,
        ),
    ]:
        baseline_cost = (
            BASELINE_FIXED_COST
            if strategy
            == "fixed_settlement"
            else BASELINE_TAEC_COST
        )

        for (
            period,
            model,
        ), x in p.groupby(
            [
                "empirical_period",
                "model",
            ]
        ):
            gross = float(
                x[
                    "gross_pre_cost_pnl"
                ].sum()
            )

            n = int(
                len(
                    x
                )
            )

            break_even = (
                gross
                / n
                if n > 0
                else np.nan
            )

            breaks.append(
                {
                    "empirical_period":
                        period,
                    "strategy":
                        strategy,
                    "model":
                        model,
                    "positions":
                        n,
                    "gross_pre_cost_pnl":
                        gross,
                    "baseline_cost_per_position":
                        baseline_cost,
                    "baseline_net_pnl":
                        (
                            gross
                            - baseline_cost
                            * n
                        ),
                    "break_even_cost_per_position":
                        break_even,
                    "baseline_cost_minus_break_even":
                        (
                            baseline_cost
                            - break_even
                        ),
                    "baseline_cost_exceeds_break_even":
                        bool(
                            baseline_cost
                            > break_even
                        ),
                }
            )

            for cost in COST_GRID:
                rows.append(
                    {
                        "empirical_period":
                            period,
                        "strategy":
                            strategy,
                        "model":
                            model,
                        "cost_per_position":
                            cost,
                        "positions":
                            n,
                        "gross_pre_cost_pnl":
                            gross,
                        "total_cost":
                            cost
                            * n,
                        "net_pnl":
                            gross
                            - cost
                            * n,
                        "is_frozen_baseline_cost":
                            bool(
                                abs(
                                    cost
                                    - baseline_cost
                                )
                                <= 1e-15
                            ),
                    }
                )

    return (
        pd.DataFrame(
            rows
        ),
        pd.DataFrame(
            breaks
        ),
    )


def taec_threshold_ledger(
    canonical: pd.DataFrame,
    checkpoints: pd.DataFrame,
    model: str,
    threshold: float,
) -> pd.DataFrame:
    entry = canonical.loc[
        canonical[
            "decision_rule"
        ]
        == "24h_prior",
        [
            "event_date",
            "empirical_period",
            "contract_key",
            f"p_{model}",
        ],
    ].copy()

    entry = entry.rename(
        columns={
            f"p_{model}":
                "model_probability",
        }
    )

    cp = checkpoints.loc[
        checkpoints[
            "taec_date_eligible"
        ]
    ].copy()

    z = cp.merge(
        entry,
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
        q = float(
            r[
                "model_probability"
            ]
        )

        p24 = float(
            r[
                "24h_prior"
            ]
        )

        gap = (
            q
            - p24
        )

        if abs(
            gap
        ) <= threshold:
            continue

        side = (
            "YES"
            if gap > 0
            else "NO"
        )

        sign = (
            1.0
            if side == "YES"
            else -1.0
        )

        exit_rule = None
        exit_price = None
        target_hit = False

        for rule in [
            "12h_prior",
            "6h_prior",
            "event_day_open",
        ]:
            pt = float(
                r[
                    rule
                ]
            )

            crossed = (
                pt >= q
                if side == "YES"
                else pt <= q
            )

            if crossed:
                exit_rule = rule
                exit_price = pt
                target_hit = True
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

        signed_move = (
            sign
            * (
                exit_price
                - p24
            )
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
                "threshold":
                    threshold,
                "side":
                    side,
                "target_hit":
                    target_hit,
                "exit_rule":
                    exit_rule,
                "initial_abs_gap":
                    abs(
                        gap
                    ),
                "signed_pre_cost_convergence":
                    signed_move,
                "net_pnl":
                    signed_move
                    - BASELINE_TAEC_COST,
            }
        )

    return pd.DataFrame(
        rows
    )


def threshold_sensitivity(
    canonical: pd.DataFrame,
    checkpoints: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    ledgers = []
    rows = []

    for threshold in TAEC_THRESHOLD_GRID:
        for model in MODELS:
            p = taec_threshold_ledger(
                canonical,
                checkpoints,
                model,
                threshold,
            )

            ledgers.append(
                p
            )

            for period in PERIODS:
                x = p.loc[
                    p[
                        "empirical_period"
                    ]
                    == period
                ].copy()

                rows.append(
                    {
                        "empirical_period":
                            period,
                        "model":
                            model,
                        "threshold":
                            threshold,
                        "positions":
                            int(
                                len(
                                    x
                                )
                            ),
                        "active_dates":
                            int(
                                x[
                                    "event_date"
                                ].nunique()
                            ),
                        "yes_positions":
                            int(
                                (
                                    x[
                                        "side"
                                    ]
                                    == "YES"
                                ).sum()
                            ),
                        "no_positions":
                            int(
                                (
                                    x[
                                        "side"
                                    ]
                                    == "NO"
                                ).sum()
                            ),
                        "target_hits":
                            int(
                                x[
                                    "target_hit"
                                ].sum()
                            ),
                        "gross_pre_cost_pnl":
                            float(
                                x[
                                    "signed_pre_cost_convergence"
                                ].sum()
                            ),
                        "total_cost":
                            float(
                                len(
                                    x
                                )
                                * BASELINE_TAEC_COST
                            ),
                        "net_pnl":
                            float(
                                x[
                                    "net_pnl"
                                ].sum()
                            ),
                        "is_frozen_baseline_threshold":
                            bool(
                                abs(
                                    threshold
                                    - BASELINE_TAEC_COST
                                )
                                <= 1e-15
                            ),
                        "diagnostic_only_no_reselection":
                            True,
                    }
                )

    ledger = pd.concat(
        ledgers,
        ignore_index=True,
    )

    return (
        pd.DataFrame(
            rows
        ),
        ledger,
    )


def open_only_execution(
    taec: pd.DataFrame,
    checkpoints: pd.DataFrame,
) -> pd.DataFrame:
    cp = checkpoints[
        [
            "event_date",
            "empirical_period",
            "contract_key",
            "event_day_open",
        ]
    ].copy()

    z = taec.merge(
        cp,
        on=[
            "event_date",
            "empirical_period",
            "contract_key",
        ],
        how="left",
        validate="many_to_one",
    )

    if z[
        "event_day_open"
    ].isna().any():
        raise RuntimeError(
            "Open-only execution join has missing market prices."
        )

    z[
        "side_sign"
    ] = np.where(
        z[
            "side"
        ]
        == "YES",
        1.0,
        -1.0,
    )

    z[
        "open_only_gross_pnl"
    ] = (
        z[
            "side_sign"
        ]
        * (
            z[
                "event_day_open"
            ]
            - z[
                "market_entry_yes_24h"
            ]
        )
    )

    z[
        "open_only_net_pnl"
    ] = (
        z[
            "open_only_gross_pnl"
        ]
        - BASELINE_TAEC_COST
    )

    rows = []

    for (
        period,
        model,
    ), x in z.groupby(
        [
            "empirical_period",
            "model",
        ]
    ):
        rows.append(
            {
                "empirical_period":
                    period,
                "model":
                    model,
                "positions":
                    int(
                        len(
                            x
                        )
                    ),
                "baseline_early_exit_net_pnl":
                    float(
                        x[
                            "net_pnl"
                        ].sum()
                    ),
                "open_only_net_pnl":
                    float(
                        x[
                            "open_only_net_pnl"
                        ].sum()
                    ),
                "open_only_minus_baseline":
                    float(
                        (
                            x[
                                "open_only_net_pnl"
                            ]
                            - x[
                                "net_pnl"
                            ]
                        ).sum()
                    ),
                "open_only_gross_pre_cost_pnl":
                    float(
                        x[
                            "open_only_gross_pnl"
                        ].sum()
                    ),
                "execution_interpretation":
                    (
                        "All baseline TAEC positions are forced to "
                        "event-day-open exit; no early target-hit exit."
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def common_daily_panel() -> pd.DataFrame:
    x = pd.read_csv(
        COMMON
    )

    x[
        "event_date"
    ] = pd.to_datetime(
        x[
            "event_date"
        ],
        errors="raise",
    )

    return x


def concentration_robustness(
    daily: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for (
        strategy,
        model,
    ), x in daily.groupby(
        [
            "strategy",
            "model",
        ]
    ):
        x = x.sort_values(
            "event_date"
        ).copy()

        pnl = x[
            "net_pnl"
        ].to_numpy(
            float
        )

        total = float(
            pnl.sum()
        )

        positive = np.sort(
            pnl[
                pnl > 0
            ]
        )[::-1]

        abs_pnl = np.abs(
            pnl
        )

        abs_sum = float(
            abs_pnl.sum()
        )

        hhi = (
            float(
                np.sum(
                    (
                        abs_pnl
                        / abs_sum
                    ) ** 2
                )
            )
            if abs_sum
            > 1e-15
            else np.nan
        )

        gross_profit = float(
            np.clip(
                pnl,
                0,
                None,
            ).sum()
        )

        top1_winner = (
            float(
                positive[
                    0
                ]
            )
            if len(
                positive
            )
            else 0.0
        )

        top3_winners = float(
            positive[
                :3
            ].sum()
        )

        leave_one_out = (
            total
            - pnl
        )

        rows.append(
            {
                "strategy":
                    strategy,
                "model":
                    model,
                "dates":
                    int(
                        len(
                            x
                        )
                    ),
                "baseline_total_pnl":
                    total,
                "gross_profit":
                    gross_profit,
                "top1_winner_pnl":
                    top1_winner,
                "top1_winner_share_of_gross_profit":
                    safe_ratio(
                        top1_winner,
                        gross_profit,
                    ),
                "top3_winners_pnl":
                    top3_winners,
                "top3_winner_share_of_gross_profit":
                    safe_ratio(
                        top3_winners,
                        gross_profit,
                    ),
                "pnl_after_removing_top1_winner":
                    total
                    - top1_winner,
                "pnl_after_removing_top3_winners":
                    total
                    - top3_winners,
                "pnl_after_removing_worst_day":
                    total
                    - float(
                        pnl.min()
                    ),
                "leave_one_date_out_min_total":
                    float(
                        leave_one_out.min()
                    ),
                "leave_one_date_out_max_total":
                    float(
                        leave_one_out.max()
                    ),
                "absolute_pnl_hhi":
                    hhi,
                "effective_number_of_abs_pnl_dates":
                    (
                        1.0
                        / hhi
                        if hhi
                        and hhi
                        > 0
                        else np.nan
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def monthly_stability(
    daily: pd.DataFrame,
) -> pd.DataFrame:
    x = daily.copy()

    x[
        "month"
    ] = x[
        "event_date"
    ].dt.to_period(
        "M"
    ).astype(
        str
    )

    rows = []

    for (
        month,
        strategy,
        model,
    ), g in x.groupby(
        [
            "month",
            "strategy",
            "model",
        ]
    ):
        rows.append(
            {
                "month":
                    month,
                "strategy":
                    strategy,
                "model":
                    model,
                "dates":
                    int(
                        len(
                            g
                        )
                    ),
                "active_dates":
                    int(
                        as_bool(
                            g[
                                "active"
                            ]
                        ).sum()
                    ),
                "positions":
                    int(
                        g[
                            "positions"
                        ].sum()
                    ),
                "total_net_pnl":
                    float(
                        g[
                            "net_pnl"
                        ].sum()
                    ),
                "mean_daily_pnl":
                    float(
                        g[
                            "net_pnl"
                        ].mean()
                    ),
                "nonannualised_sharpe":
                    sharpe(
                        g[
                            "net_pnl"
                        ].to_numpy(
                            float
                        )
                    ),
                "entry_capital":
                    float(
                        g[
                            "entry_capital"
                        ].sum()
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def seven_observation_deletion(
    daily: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    dates = sorted(
        daily[
            "event_date"
        ].unique()
    )

    if len(
        dates
    ) != 61:
        raise RuntimeError(
            "Expected exactly 61 external common-support dates."
        )

    windows = []

    for start in range(
        0,
        len(
            dates
        )
        - 7
        + 1,
    ):
        removed = set(
            dates[
                start:
                start
                + 7
            ]
        )

        windows.append(
            (
                start,
                removed,
            )
        )

    detail = []

    for (
        strategy,
        model,
    ), x in daily.groupby(
        [
            "strategy",
            "model",
        ]
    ):
        baseline = float(
            x[
                "net_pnl"
            ].sum()
        )

        for start, removed in windows:
            kept = x.loc[
                ~x[
                    "event_date"
                ].isin(
                    removed
                )
            ]

            detail.append(
                {
                    "strategy":
                        strategy,
                    "model":
                        model,
                    "window_start_index":
                        start,
                    "removed_first_date":
                        str(
                            pd.Timestamp(
                                min(
                                    removed
                                )
                            ).date()
                        ),
                    "removed_last_date":
                        str(
                            pd.Timestamp(
                                max(
                                    removed
                                )
                            ).date()
                        ),
                    "baseline_total_pnl":
                        baseline,
                    "remaining_total_pnl":
                        float(
                            kept[
                                "net_pnl"
                            ].sum()
                        ),
                }
            )

    detail = pd.DataFrame(
        detail
    )

    summary = (
        detail.groupby(
            [
                "strategy",
                "model",
            ],
            as_index=False,
        )
        .agg(
            baseline_total_pnl=(
                "baseline_total_pnl",
                "first",
            ),
            min_remaining_total_pnl=(
                "remaining_total_pnl",
                "min",
            ),
            max_remaining_total_pnl=(
                "remaining_total_pnl",
                "max",
            ),
            mean_remaining_total_pnl=(
                "remaining_total_pnl",
                "mean",
            ),
        )
    )

    summary[
        "baseline_sign_preserved_all_windows"
    ] = np.where(
        summary[
            "baseline_total_pnl"
        ]
        > 0,
        summary[
            "min_remaining_total_pnl"
        ]
        > 0,
        np.where(
            summary[
                "baseline_total_pnl"
            ]
            < 0,
            summary[
                "max_remaining_total_pnl"
            ]
            < 0,
            True,
        ),
    )

    return (
        detail,
        summary,
    )


def paired_deletion_contrast(
    daily: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    dates = sorted(
        daily[
            "event_date"
        ].unique()
    )

    for model in MODELS:
        fixed = (
            daily.loc[
                (
                    daily[
                        "strategy"
                    ]
                    == "fixed_settlement"
                )
                & (
                    daily[
                        "model"
                    ]
                    == model
                ),
                [
                    "event_date",
                    "net_pnl",
                ],
            ]
            .set_index(
                "event_date"
            )[
                "net_pnl"
            ]
        )

        taec = (
            daily.loc[
                (
                    daily[
                        "strategy"
                    ]
                    == "taec11"
                )
                & (
                    daily[
                        "model"
                    ]
                    == model
                ),
                [
                    "event_date",
                    "net_pnl",
                ],
            ]
            .set_index(
                "event_date"
            )[
                "net_pnl"
            ]
        )

        d = (
            taec
            - fixed
        ).reindex(
            dates
        )

        baseline = float(
            d.sum()
        )

        remaining = []

        for start in range(
            0,
            len(
                dates
            )
            - 7
            + 1,
        ):
            mask = np.ones(
                len(
                    dates
                ),
                dtype=bool,
            )

            mask[
                start:
                start
                + 7
            ] = False

            remaining.append(
                float(
                    d.to_numpy(
                        float
                    )[
                        mask
                    ].sum()
                )
            )

        rows.append(
            {
                "model":
                    model,
                "baseline_taec_minus_fixed":
                    baseline,
                "min_after_deleting_any_7_observation_block":
                    float(
                        np.min(
                            remaining
                        )
                    ),
                "max_after_deleting_any_7_observation_block":
                    float(
                        np.max(
                            remaining
                        )
                    ),
                "taec_remains_worse_for_every_deletion_window":
                    bool(
                        np.max(
                            remaining
                        )
                        < 0
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def block_length_sensitivity(
    daily: pd.DataFrame,
    taec_positions: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for model in MODELS:
        fixed = (
            daily.loc[
                (
                    daily[
                        "strategy"
                    ]
                    == "fixed_settlement"
                )
                & (
                    daily[
                        "model"
                    ]
                    == model
                )
            ]
            .sort_values(
                "event_date"
            )[
                "net_pnl"
            ]
            .to_numpy(
                float
            )
        )

        taec = (
            daily.loc[
                (
                    daily[
                        "strategy"
                    ]
                    == "taec11"
                )
                & (
                    daily[
                        "model"
                    ]
                    == model
                )
            ]
            .sort_values(
                "event_date"
            )[
                "net_pnl"
            ]
            .to_numpy(
                float
            )
        )

        p = taec_positions.loc[
            (
                taec_positions[
                    "empirical_period"
                ]
                == "external_validation"
            )
            & (
                taec_positions[
                    "model"
                ]
                == model
            )
        ].copy()

        p[
            "event_date"
        ] = pd.to_datetime(
            p[
                "event_date"
            ],
            errors="raise",
        )

        conv = (
            p.groupby(
                "event_date"
            )[
                "signed_market_move_toward_model"
            ]
            .sum()
            .reindex(
                sorted(
                    daily[
                        "event_date"
                    ].unique()
                ),
                fill_value=0.0,
            )
            .to_numpy(
                float
            )
        )

        series = {
            "taec_minus_fixed":
                taec
                - fixed,
            "fixed_profitability":
                fixed,
            "precost_convergence":
                conv,
        }

        for contrast, values in series.items():
            for block in BLOCK_LENGTH_GRID:
                result = centered_mean_bootstrap(
                    values,
                    block,
                    (
                        f"stage5|{contrast}|"
                        f"{model}|L={block}"
                    ),
                )

                rows.append(
                    {
                        "contrast":
                            contrast,
                        "model":
                            model,
                        "block_length":
                            block,
                        **result,
                        "reject_5pct_unadjusted":
                            bool(
                                result[
                                    "p_two_sided"
                                ]
                                < ALPHA
                            ),
                        "diagnostic_only_primary_block_remains_7":
                            True,
                    }
                )

    return pd.DataFrame(
        rows
    )


def block_length_summary(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    return (
        detail.groupby(
            [
                "contrast",
                "model",
            ],
            as_index=False,
        )
        .agg(
            min_p_value=(
                "p_two_sided",
                "min",
            ),
            max_p_value=(
                "p_two_sided",
                "max",
            ),
            significant_block_lengths=(
                "reject_5pct_unadjusted",
                "sum",
            ),
            total_block_lengths=(
                "block_length",
                "size",
            ),
            all_block_lengths_same_sign=(
                "observed_total",
                lambda s: bool(
                    (
                        np.asarray(
                            s
                        )
                        > 0
                    ).all()
                    or (
                        np.asarray(
                            s
                        )
                        < 0
                    ).all()
                ),
            ),
        )
    )


def perturbation_summary() -> pd.DataFrame:
    stress = pd.read_csv(
        STRESS
    )

    instability = pd.read_csv(
        INSTABILITY
    )

    stress = stress.loc[
        stress[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    instability = instability.loc[
        instability[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    rows = []

    for (
        strategy,
        model,
    ), x in stress.groupby(
        [
            "strategy",
            "model",
        ]
    ):
        baseline = float(
            x.loc[
                x[
                    "temperature_shift_c"
                ]
                == 0,
                "total_net_pnl",
            ].iloc[
                0
            ]
        )

        local = x.loc[
            x[
                "temperature_shift_c"
            ].isin(
                [
                    -0.25,
                    0.25,
                ]
            )
        ]

        full = x.loc[
            x[
                "temperature_shift_c"
            ].isin(
                [
                    -1.0,
                    1.0,
                ]
            )
        ]

        inst = instability.loc[
            (
                instability[
                    "strategy"
                ]
                == strategy
            )
            & (
                instability[
                    "model"
                ]
                == model
            )
            & (
                instability[
                    "temperature_shift_c"
                ].isin(
                    [
                        -0.25,
                        0.25,
                    ]
                )
            )
        ]

        rows.append(
            {
                "strategy":
                    strategy,
                "model":
                    model,
                "baseline_total_pnl":
                    baseline,
                "local_plus_minus_0_25_min_pnl":
                    float(
                        local[
                            "total_net_pnl"
                        ].min()
                    ),
                "local_plus_minus_0_25_max_pnl":
                    float(
                        local[
                            "total_net_pnl"
                        ].max()
                    ),
                "local_sign_preserved":
                    bool((((local["total_net_pnl"] * baseline) > 0).all()))
                    if abs(
                        baseline
                    )
                    > 1e-15
                    else False,
                "plus_minus_1_min_pnl":
                    float(
                        full[
                            "total_net_pnl"
                        ].min()
                    ),
                "plus_minus_1_max_pnl":
                    float(
                        full[
                            "total_net_pnl"
                        ].max()
                    ),
                "mean_local_position_jaccard":
                    float(
                        inst[
                            "position_set_jaccard"
                        ].mean()
                    ),
                "min_local_position_jaccard":
                    float(
                        inst[
                            "position_set_jaccard"
                        ].min()
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def figures(
    cost: pd.DataFrame,
    threshold: pd.DataFrame,
    deletion: pd.DataFrame,
    execution: pd.DataFrame,
) -> None:
    ext_cost = cost.loc[
        cost[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    fig, ax = plt.subplots(
        figsize=(
            9,
            5,
        )
    )

    for model in MODELS:
        x = ext_cost.loc[
            (
                ext_cost[
                    "strategy"
                ]
                == "taec11"
            )
            & (
                ext_cost[
                    "model"
                ]
                == model
            )
        ]

        ax.plot(
            x[
                "cost_per_position"
            ],
            x[
                "net_pnl"
            ],
            marker="o",
            label=model,
        )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.axvline(
        BASELINE_TAEC_COST,
        linewidth=1,
    )

    ax.set_title(
        "External TAEC effective round-trip cost sensitivity"
    )

    ax.set_xlabel(
        "Effective cost per position"
    )

    ax.set_ylabel(
        "Total net PnL"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_taec_cost_sensitivity.png",
        dpi=180,
    )

    plt.close(
        fig
    )

    ext_threshold = threshold.loc[
        threshold[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    fig, ax = plt.subplots(
        figsize=(
            9,
            5,
        )
    )

    for model in MODELS:
        x = ext_threshold.loc[
            ext_threshold[
                "model"
            ]
            == model
        ]

        ax.plot(
            x[
                "threshold"
            ],
            x[
                "net_pnl"
            ],
            marker="o",
            label=model,
        )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.axvline(
        BASELINE_TAEC_COST,
        linewidth=1,
    )

    ax.set_title(
        "Diagnostic TAEC discrepancy-threshold sensitivity"
    )

    ax.set_xlabel(
        "Absolute entry discrepancy threshold"
    )

    ax.set_ylabel(
        "External total net PnL"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_taec_threshold_sensitivity.png",
        dpi=180,
    )

    plt.close(
        fig
    )

    ext_execution = execution.loc[
        execution[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    labels = ext_execution[
        "model"
    ].tolist()

    x = np.arange(
        len(
            labels
        )
    )

    width = 0.35

    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    ax.bar(
        x
        - width
        / 2,
        ext_execution[
            "baseline_early_exit_net_pnl"
        ],
        width,
        label="baseline early-exit TAEC",
    )

    ax.bar(
        x
        + width
        / 2,
        ext_execution[
            "open_only_net_pnl"
        ],
        width,
        label="force all exits to event-day open",
    )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.set_xticks(
        x
    )

    ax.set_xticklabels(
        labels
    )

    ax.set_ylabel(
        "External total net PnL"
    )

    ax.set_title(
        "TAEC exit-timing execution sensitivity"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_taec_open_only_execution_sensitivity.png",
        dpi=180,
    )

    plt.close(
        fig
    )

    fig, ax = plt.subplots(
        figsize=(
            9,
            5,
        )
    )

    d = deletion.copy()

    positions = np.arange(
        len(
            d
        )
    )

    estimate = d[
        "baseline_total_pnl"
    ].to_numpy(
        float
    )

    lower = d[
        "min_remaining_total_pnl"
    ].to_numpy(
        float
    )

    upper = d[
        "max_remaining_total_pnl"
    ].to_numpy(
        float
    )

    ax.errorbar(
        estimate,
        positions,
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
        positions
    )

    ax.set_yticklabels(
        (
            d[
                "strategy"
            ]
            + ":"
            + d[
                "model"
            ]
        ).tolist()
    )

    ax.set_xlabel(
        "Total PnL after deleting any 7-observation block"
    )

    ax.set_title(
        "External support-deletion sensitivity"
    )

    fig.tight_layout()

    fig.savefig(
        OUT
        / "external_seven_observation_deletion_sensitivity.png",
        dpi=180,
    )

    plt.close(
        fig
    )


def main() -> None:
    canonical = pd.read_csv(
        CANONICAL
    )

    checkpoints = pd.read_csv(
        CHECKPOINTS
    )

    checkpoints[
        "taec_date_eligible"
    ] = as_bool(
        checkpoints[
            "taec_date_eligible"
        ]
    )

    fixed_pos, taec_pos = load_position_components()

    cost, break_even = cost_sensitivity(
        fixed_pos,
        taec_pos,
    )

    cost.to_csv(
        OUT
        / "transaction_cost_sensitivity.csv",
        index=False,
    )

    break_even.to_csv(
        OUT
        / "transaction_cost_break_even_summary.csv",
        index=False,
    )

    threshold, threshold_ledger = threshold_sensitivity(
        canonical,
        checkpoints,
    )

    threshold.to_csv(
        OUT
        / "taec_threshold_sensitivity.csv",
        index=False,
    )

    threshold_ledger.to_csv(
        OUT
        / "taec_threshold_position_ledger.csv.gz",
        index=False,
        compression="gzip",
    )

    execution = open_only_execution(
        taec_pos,
        checkpoints,
    )

    execution.to_csv(
        OUT
        / "taec_open_only_execution_sensitivity.csv",
        index=False,
    )

    daily = common_daily_panel()

    concentration = concentration_robustness(
        daily
    )

    concentration.to_csv(
        OUT
        / "external_concentration_robustness.csv",
        index=False,
    )

    monthly = monthly_stability(
        daily
    )

    monthly.to_csv(
        OUT
        / "external_monthly_stability.csv",
        index=False,
    )

    (
        deletion_detail,
        deletion_summary,
    ) = seven_observation_deletion(
        daily
    )

    deletion_detail.to_csv(
        OUT
        / "external_seven_observation_deletion_detail.csv",
        index=False,
    )

    deletion_summary.to_csv(
        OUT
        / "external_seven_observation_deletion_summary.csv",
        index=False,
    )

    paired_deletion = paired_deletion_contrast(
        daily
    )

    paired_deletion.to_csv(
        OUT
        / "taec_minus_fixed_seven_observation_deletion.csv",
        index=False,
    )

    block_detail = block_length_sensitivity(
        daily,
        taec_pos,
    )

    block_detail.to_csv(
        OUT
        / "moving_block_length_sensitivity.csv",
        index=False,
    )

    block_summary = block_length_summary(
        block_detail
    )

    block_summary.to_csv(
        OUT
        / "moving_block_length_sensitivity_summary.csv",
        index=False,
    )

    perturbation = perturbation_summary()

    perturbation.to_csv(
        OUT
        / "temperature_perturbation_robustness_summary.csv",
        index=False,
    )

    # Reconcile frozen baseline transaction costs to Stage 2.
    stage2_fixed = pd.read_csv(
        S2
        / "fixed_strategy_stage2_summary.csv"
    )

    stage2_taec = pd.read_csv(
        S2
        / "taec11_stage2_summary.csv"
    )

    baseline_cost_rows = cost.loc[
        cost[
            "is_frozen_baseline_cost"
        ]
    ].copy()

    reference = pd.concat(
        [
            stage2_fixed.assign(
                strategy="fixed_settlement"
            ),
            stage2_taec.assign(
                strategy="taec11"
            ),
        ],
        ignore_index=True,
    )

    reconciliation = baseline_cost_rows.merge(
        reference[
            [
                "empirical_period",
                "strategy",
                "model",
                "positions",
                "total_net_pnl",
            ]
        ].rename(
            columns={
                "positions":
                    "stage2_positions",
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

    reconciliation[
        "pnl_difference"
    ] = (
        reconciliation[
            "net_pnl"
        ]
        - reconciliation[
            "stage2_total_net_pnl"
        ]
    )

    reconciliation[
        "positions_match"
    ] = (
        reconciliation[
            "positions"
        ]
        == reconciliation[
            "stage2_positions"
        ]
    )

    reconciliation[
        "passed"
    ] = (
        reconciliation[
            "pnl_difference"
        ].abs()
        <= 1e-10
    ) & reconciliation[
        "positions_match"
    ]

    reconciliation.to_csv(
        OUT
        / "stage2_cost_baseline_reconciliation.csv",
        index=False,
    )

    if not reconciliation[
        "passed"
    ].all():
        raise RuntimeError(
            "Baseline cost engine does not reproduce Stage 2."
        )

    # Baseline threshold 0.02 must reproduce Stage-2 TAEC exactly.
    baseline_threshold = threshold.loc[
        threshold[
            "is_frozen_baseline_threshold"
        ]
    ].copy()

    threshold_reconciliation = (
        baseline_threshold.merge(
            stage2_taec[
                [
                    "empirical_period",
                    "model",
                    "positions",
                    "total_net_pnl",
                ]
            ].rename(
                columns={
                    "positions":
                        "stage2_positions",
                    "total_net_pnl":
                        "stage2_total_net_pnl",
                }
            ),
            on=[
                "empirical_period",
                "model",
            ],
            how="left",
            validate="one_to_one",
        )
    )

    threshold_reconciliation[
        "positions_match"
    ] = (
        threshold_reconciliation[
            "positions"
        ]
        == threshold_reconciliation[
            "stage2_positions"
        ]
    )

    threshold_reconciliation[
        "pnl_difference"
    ] = (
        threshold_reconciliation[
            "net_pnl"
        ]
        - threshold_reconciliation[
            "stage2_total_net_pnl"
        ]
    )

    threshold_reconciliation[
        "passed"
    ] = (
        threshold_reconciliation[
            "positions_match"
        ]
        & (
            threshold_reconciliation[
                "pnl_difference"
            ].abs()
            <= 1e-10
        )
    )

    threshold_reconciliation.to_csv(
        OUT
        / "stage2_taec_threshold_reconciliation.csv",
        index=False,
    )

    if not threshold_reconciliation[
        "passed"
    ].all():
        raise RuntimeError(
            "Baseline threshold engine does not reproduce Stage 2."
        )

    figures(
        cost,
        threshold,
        deletion_summary,
        execution,
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
        "baseline_cost_reproduction",
        bool(
            reconciliation[
                "passed"
            ].all()
        ),
        float(
            reconciliation[
                "pnl_difference"
            ].abs().max()
        ),
        "<=1e-10",
    )

    add(
        "baseline_threshold_reproduction",
        bool(
            threshold_reconciliation[
                "passed"
            ].all()
        ),
        float(
            threshold_reconciliation[
                "pnl_difference"
            ].abs().max()
        ),
        "<=1e-10",
    )

    add(
        "cost_grid_contains_baselines",
        (
            BASELINE_FIXED_COST
            in COST_GRID
            and BASELINE_TAEC_COST
            in COST_GRID
        ),
        COST_GRID,
        (
            BASELINE_FIXED_COST,
            BASELINE_TAEC_COST,
        ),
    )

    add(
        "threshold_grid_contains_frozen_baseline",
        BASELINE_TAEC_COST
        in TAEC_THRESHOLD_GRID,
        TAEC_THRESHOLD_GRID,
        BASELINE_TAEC_COST,
        "External threshold variants are diagnostic only and cannot replace the frozen 0.02 policy.",
    )

    add(
        "external_concentration_rows",
        len(
            concentration
        )
        == 8,
        len(
            concentration
        ),
        8,
    )

    add(
        "external_months",
        sorted(
            monthly[
                "month"
            ].unique().tolist()
        )
        == [
            "2026-07",
            "2026-08",
        ],
        sorted(
            monthly[
                "month"
            ].unique().tolist()
        ),
        [
            "2026-07",
            "2026-08",
        ],
    )

    add(
        "block_length_grid",
        sorted(
            block_detail[
                "block_length"
            ].unique().tolist()
        )
        == BLOCK_LENGTH_GRID,
        sorted(
            block_detail[
                "block_length"
            ].unique().tolist()
        ),
        BLOCK_LENGTH_GRID,
        "Primary Stage-4 block length remains 7; this is sensitivity analysis only.",
    )

    add(
        "paired_deletion_models",
        len(
            paired_deletion
        )
        == 4,
        len(
            paired_deletion
        ),
        4,
    )

    add(
        "perturbation_portfolios",
        len(
            perturbation
        )
        == 8,
        len(
            perturbation
        ),
        8,
    )

    stage_checks = pd.DataFrame(
        checks
    )

    stage_checks.to_csv(
        OUT
        / "stage5_integrity_checks.csv",
        index=False,
    )

    status = (
        "PASS"
        if stage_checks[
            "passed"
        ].all()
        else "FAILED"
    )

    external_break_even = break_even.loc[
        break_even[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    external_threshold = threshold.loc[
        threshold[
            "empirical_period"
        ]
        == "external_validation"
    ].copy()

    diagnostic_best_threshold = (
        external_threshold.sort_values(
            [
                "model",
                "net_pnl",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .groupby(
            "model",
            as_index=False,
        )
        .first()
    )

    summary = {
        "status":
            status,
        "stage":
            5,
        "stage_name":
            (
                "robustness_execution_reality_cost_"
                "concentration_and_support"
            ),
        "inference_status":
            "EXPLORATORY_EXTENSION",
        "frozen_policy_guards":
            {
                "taec_threshold":
                    BASELINE_TAEC_COST,
                "taec_round_trip_cost":
                    BASELINE_TAEC_COST,
                "fixed_cost":
                    BASELINE_FIXED_COST,
                "primary_bootstrap_block_length":
                    7,
                "external_diagnostics_may_reselect":
                    False,
            },
        "external_cost_break_even":
            external_break_even.to_dict(
                orient="records"
            ),
        "diagnostic_best_taec_thresholds_do_not_reselect_policy":
            diagnostic_best_threshold[
                [
                    "model",
                    "threshold",
                    "positions",
                    "net_pnl",
                ]
            ].to_dict(
                orient="records"
            ),
        "external_open_only_execution":
            execution.loc[
                execution[
                    "empirical_period"
                ]
                == "external_validation"
            ].to_dict(
                orient="records"
            ),
        "external_seven_observation_deletion":
            deletion_summary.to_dict(
                orient="records"
            ),
        "taec_minus_fixed_seven_observation_deletion":
            paired_deletion.to_dict(
                orient="records"
            ),
        "temperature_perturbation":
            perturbation.to_dict(
                orient="records"
            ),
        "execution_caveat":
            (
                "TAEC remains a snapshot-price mark-to-market study because "
                "historical executable bid/ask quotes are unavailable. Cost and "
                "open-only-exit sensitivity quantify, but cannot eliminate, this limitation."
            ),
        "next_stage":
            (
                "final thesis-value pruning, examiner-facing audit, "
                "reproducibility closure and submission-ready release"
            ),
    }

    (
        OUT
        / "stage5_summary.json"
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
        " EXTERNAL COST BREAK-EVEN"
    )
    print(
        "==================================================================="
    )
    print(
        external_break_even[
            [
                "strategy",
                "model",
                "positions",
                "gross_pre_cost_pnl",
                "baseline_cost_per_position",
                "baseline_net_pnl",
                "break_even_cost_per_position",
                "baseline_cost_exceeds_break_even",
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
        " EXTERNAL TAEC THRESHOLD SENSITIVITY"
    )
    print(
        "==================================================================="
    )
    print(
        external_threshold[
            [
                "model",
                "threshold",
                "positions",
                "gross_pre_cost_pnl",
                "total_cost",
                "net_pnl",
                "is_frozen_baseline_threshold",
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
        " OPEN-ONLY EXECUTION SENSITIVITY"
    )
    print(
        "==================================================================="
    )
    print(
        execution.loc[
            execution[
                "empirical_period"
            ]
            == "external_validation"
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "==================================================================="
    )
    print(
        " SUPPORT DELETION: TAEC MINUS FIXED"
    )
    print(
        "==================================================================="
    )
    print(
        paired_deletion.to_string(
            index=False
        )
    )

    print()
    print(
        "==================================================================="
    )
    print(
        " BLOCK-LENGTH ROBUSTNESS SUMMARY"
    )
    print(
        "==================================================================="
    )
    print(
        block_summary.to_string(
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
            "Stage 5 acceptance gate failed."
        )


if __name__ == "__main__":
    main()
