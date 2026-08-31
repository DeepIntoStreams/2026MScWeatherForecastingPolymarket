from __future__ import annotations

import hashlib
import json
import math
import sys

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scipy.stats import norm, spearmanr


# =============================================================================
# FROZEN INPUT / DESIGN
# =============================================================================

INPUT = Path(
    "data/processed/final_pipeline/market/"
    "exact_common_event_panel.csv.gz"
)

MARKET_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "market_stage_summary.json"
)

WEATHER_SELECTION = Path(
    "outputs/final_pipeline/weather/models/"
    "weather_kernel_selection.json"
)

DEVELOPMENT_PERIOD = "market_development"
EXTERNAL_PERIOD = "external_validation"

RULE_ORDER = [
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
]

THRESHOLD_GRID = np.round(
    np.arange(
        0.00,
        0.251,
        0.01,
    ),
    2,
)

MIN_DEVELOPMENT_TRADES = 10

REFERENCE_COST = 0.01

BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 20260831
BLOCK_LENGTH = 7

# Reduced-form fitted-mean shock.
BASE_SHOCK_GRID = np.round(
    np.arange(
        -2.0,
        2.0001,
        0.1,
    ),
    2,
)

SHOCK_GRID = np.array(
    sorted(
        set(
            BASE_SHOCK_GRID.tolist()
            + [
                -1.0,
                -0.5,
                -0.25,
                -0.10,
                0.0,
                0.10,
                0.25,
                0.5,
                1.0,
            ]
        )
    ),
    dtype=float,
)

COST_GRID = np.round(
    np.arange(
        0.0,
        0.05001,
        0.0025,
    ),
    4,
)

PROBABILITY_COLUMNS = {
    "raw":
        "p_raw",

    "static":
        "p_static",

    "selected_gp":
        "p_selected_gp",
}

METHOD_ORDER = [
    "raw",
    "static",
    "selected_gp",
]

EPS = 1e-12


# =============================================================================
# PATHS
# =============================================================================

PROCESSED = Path(
    "data/processed/final_pipeline/trading"
)

OUTPUT = Path(
    "outputs/final_pipeline/trading"
)

AUDIT = Path(
    "outputs/final_pipeline/audit"
)

DEVELOPMENT_CANDIDATES = (
    PROCESSED
    / "development_selected_contract_candidates.csv"
)

THRESHOLD_GRID_OUTPUT = (
    PROCESSED
    / "development_threshold_grid.csv"
)

COMMON_RULE_SENSITIVITY = (
    OUTPUT
    / "common_rule_selection_sensitivity.csv"
)

POLICY_JSON = (
    OUTPUT
    / "selected_trading_policy.json"
)

ALL_LEDGERS = (
    PROCESSED
    / "fixed_policy_ledgers.csv"
)

ATTRIBUTION_PANEL = (
    PROCESSED
    / "fixed_policy_attribution_panel.csv"
)

ATTRIBUTION_SUMMARY = (
    OUTPUT
    / "fixed_policy_attribution_summary.csv"
)

DECISION_OVERLAP = (
    OUTPUT
    / "fixed_policy_decision_overlap.csv"
)

RISK_SUMMARY = (
    OUTPUT
    / "trading_risk_summary.csv"
)

BOOTSTRAP_SUMMARY = (
    OUTPUT
    / "trading_bootstrap_summary.csv"
)

COST_SENSITIVITY = (
    OUTPUT
    / "selected_gp_cost_sensitivity.csv"
)

LOCAL_EVENT_SENSITIVITY = (
    PROCESSED
    / "selected_gp_local_event_sensitivity.csv.gz"
)

SELECTED_DATE_SENSITIVITY = (
    PROCESSED
    / "selected_gp_selected_contract_sensitivity.csv"
)

DERIVATIVE_VALIDATION = (
    OUTPUT
    / "probability_derivative_validation.csv"
)

FIXED_CONTRACT_SHOCKS = (
    PROCESSED
    / "selected_gp_fixed_contract_mean_shocks.csv.gz"
)

FULL_STRATEGY_SHOCKS = (
    OUTPUT
    / "selected_gp_full_strategy_mean_shocks.csv"
)

FINITE_SLOPES = (
    OUTPUT
    / "selected_gp_portfolio_finite_slopes.csv"
)

ERROR_PNL_PANEL = (
    PROCESSED
    / "forecast_error_pnl_panel.csv"
)

ERROR_BIN_SUMMARY = (
    OUTPUT
    / "forecast_error_pnl_bins.csv"
)

SPEARMAN_SUMMARY = (
    OUTPUT
    / "forecast_risk_spearman_summary.csv"
)

SUPPORT_SUMMARY = (
    OUTPUT
    / "trading_support_summary.csv"
)

SELECTION_FIGURE = (
    OUTPUT
    / "development_threshold_selection.png"
)

CUMULATIVE_FIGURE = (
    OUTPUT
    / "external_cumulative_pnl_attribution.png"
)

STRESS_FIGURE = (
    OUTPUT
    / "external_predictive_mean_stress.png"
)

ERROR_FIGURE = (
    OUTPUT
    / "external_forecast_error_vs_pnl.png"
)

SUMMARY_JSON = (
    AUDIT
    / "trading_stage_summary.json"
)

CHECKS_CSV = (
    AUDIT
    / "trading_stage_integrity_checks.csv"
)


# =============================================================================
# GENERAL HELPERS
# =============================================================================


def sha256_file(
    path: Path,
) -> str:
    h = hashlib.sha256()

    with path.open(
        "rb"
    ) as f:
        while True:
            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(
                block
            )

    return h.hexdigest()


def as_bool(
    s: pd.Series,
) -> pd.Series:
    if s.dtype == bool:
        return s

    result = (
        s.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
            }
        )
    )

    if result.isna().any():
        raise RuntimeError(
            "Boolean parse failure."
        )

    return result.astype(
        bool
    )


def safe_float(
    x,
):
    try:
        value = float(
            x
        )

        if np.isfinite(
            value
        ):
            return value

    except Exception:
        pass

    return np.nan


def sample_sharpe(
    values,
):
    x = np.asarray(
        values,
        dtype=float,
    )

    if len(
        x
    ) < 2:
        return np.nan

    sd = x.std(
        ddof=1
    )

    if (
        not np.isfinite(
            sd
        )
        or sd <= 0
    ):
        return np.nan

    return float(
        x.mean()
        / sd
    )


def maximum_drawdown(
    values,
):
    x = np.asarray(
        values,
        dtype=float,
    )

    if len(
        x
    ) == 0:
        return np.nan

    cumulative = np.cumsum(
        x
    )

    cumulative_with_origin = np.r_[
        0.0,
        cumulative,
    ]

    peaks = np.maximum.accumulate(
        cumulative_with_origin
    )

    drawdowns = (
        peaks
        - cumulative_with_origin
    )

    return float(
        drawdowns.max()
    )


def expected_shortfall_5(
    values,
):
    x = np.asarray(
        values,
        dtype=float,
    )

    if len(
        x
    ) == 0:
        return np.nan

    q = np.quantile(
        x,
        0.05,
    )

    tail = x[
        x <= q
    ]

    if len(
        tail
    ) == 0:
        return np.nan

    return float(
        tail.mean()
    )


def circular_block_indices(
    n,
    block_length,
    reps,
    rng,
):
    blocks = int(
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
            blocks,
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

    return idx.reshape(
        reps,
        -1,
    )[
        :,
        :n,
    ]


def bootstrap_indices(
    n,
    *,
    block,
    seed,
):
    rng = np.random.default_rng(
        seed
    )

    if block:
        return circular_block_indices(
            n,
            BLOCK_LENGTH,
            BOOTSTRAP_REPS,
            rng,
        )

    return rng.integers(
        0,
        n,
        size=(
            BOOTSTRAP_REPS,
            n,
        ),
    )


def quantile_interval(
    x,
):
    arr = np.asarray(
        x,
        dtype=float,
    )

    arr = arr[
        np.isfinite(
            arr
        )
    ]

    if len(
        arr
    ) == 0:
        return (
            np.nan,
            np.nan,
        )

    return (
        float(
            np.quantile(
                arr,
                0.025,
            )
        ),
        float(
            np.quantile(
                arr,
                0.975,
            )
        ),
    )


# =============================================================================
# INPUT VALIDATION
# =============================================================================


def load_panel():
    if not INPUT.exists():
        raise RuntimeError(
            f"Missing market panel: {INPUT}"
        )

    df = pd.read_csv(
        INPUT
    )

    required = [
        "event_date",
        "decision_rule",
        "empirical_period",
        "market_id",
        "event_rank",
        "group_item_title",
        "contract_event_type",
        "lower_bound_c",
        "upper_bound_c",
        "target_available",
        "Y",
        "hko_daily_max_c",
        "raw_temperature_c",
        "static_mean_c",
        "static_sd_c",
        "selected_gp_mean_c",
        "selected_gp_sd_c",
        "p_raw",
        "p_static",
        "p_selected_gp",
        "market_raw_yes",
        "market_normalised",
        "record_age_hours",
        "decision_cutoff_utc",
        "selected_price_timestamp_utc",
    ]

    missing = [
        c
        for c in required
        if c not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "Trading input missing columns: "
            + repr(
                missing
            )
        )

    df[
        "event_date"
    ] = pd.to_datetime(
        df[
            "event_date"
        ]
    )

    df[
        "target_available"
    ] = as_bool(
        df[
            "target_available"
        ]
    )

    if (
        df[
            [
                "event_date",
                "decision_rule",
                "market_id",
            ]
        ]
        .duplicated()
        .any()
    ):
        raise RuntimeError(
            "Duplicate event rows in exact common panel."
        )

    sizes = (
        df.groupby(
            [
                "event_date",
                "decision_rule",
            ]
        )
        .size()
    )

    if not sizes.eq(
        11
    ).all():
        raise RuntimeError(
            "Trading input contains incomplete event books."
        )

    if not (
        df[
            "market_raw_yes"
        ]
        .between(
            0.0,
            1.0,
        )
        .all()
    ):
        raise RuntimeError(
            "Trading input contains invalid market YES values."
        )

    for col in [
        "p_raw",
        "p_static",
        "p_selected_gp",
    ]:
        if not (
            df[
                col
            ]
            .between(
                0.0,
                1.0,
            )
            .all()
        ):
            raise RuntimeError(
                f"Invalid probability column: {col}"
            )

    return df.sort_values(
        [
            "event_date",
            "decision_rule",
            "event_rank",
        ]
    ).reset_index(
        drop=True
    )


# =============================================================================
# CONTRACT SELECTION + LEDGER
# =============================================================================


def select_contract_from_book(
    book,
    probability_col,
):
    g = book.copy()

    g[
        "_gap"
    ] = (
        g[
            probability_col
        ]
        - g[
            "market_raw_yes"
        ]
    )

    best_gap = float(
        g[
            "_gap"
        ].max()
    )

    tied = g[
        np.isclose(
            g[
                "_gap"
            ],
            best_gap,
            atol=1e-12,
            rtol=0.0,
        )
    ].sort_values(
        "event_rank"
    )

    row = tied.iloc[
        0
    ].copy()

    second = (
        g[
            "_gap"
        ]
        .sort_values(
            ascending=False
        )
        .iloc[
            1
        ]
        if len(
            g
        ) >= 2
        else np.nan
    )

    return (
        row,
        best_gap,
        float(
            second
        ),
    )


def base_candidates(
    panel,
    *,
    period,
    rule,
    source,
):
    probability_col = (
        PROBABILITY_COLUMNS[
            source
        ]
    )

    x = panel[
        (
            panel[
                "empirical_period"
            ]
            == period
        )
        & (
            panel[
                "decision_rule"
            ]
            == rule
        )
    ]

    rows = []

    for date, book in (
        x.groupby(
            "event_date",
            sort=True,
        )
    ):
        if len(
            book
        ) != 11:
            continue

        (
            chosen,
            top_gap,
            second_gap,
        ) = select_contract_from_book(
            book,
            probability_col,
        )

        target_available = bool(
            book[
                "target_available"
            ].iloc[0]
        )

        if (
            book[
                "target_available"
            ].nunique()
            != 1
        ):
            raise RuntimeError(
                "Target-availability inconsistency within book."
            )

        if (
            target_available
            and not math.isclose(
                float(
                    book[
                        "Y"
                    ].sum()
                ),
                1.0,
                abs_tol=1e-12,
            )
        ):
            raise RuntimeError(
                f"Invalid realised event book on {date}."
            )

        rows.append(
            {
                "event_date":
                    date,

                "empirical_period":
                    period,

                "decision_rule":
                    rule,

                "probability_source":
                    source,

                "probability_column":
                    probability_col,

                "market_id":
                    chosen[
                        "market_id"
                    ],

                "event_rank":
                    int(
                        chosen[
                            "event_rank"
                        ]
                    ),

                "group_item_title":
                    chosen[
                        "group_item_title"
                    ],

                "contract_event_type":
                    chosen[
                        "contract_event_type"
                    ],

                "lower_bound_c":
                    chosen[
                        "lower_bound_c"
                    ],

                "upper_bound_c":
                    chosen[
                        "upper_bound_c"
                    ],

                "model_probability":
                    float(
                        chosen[
                            probability_col
                        ]
                    ),

                "market_raw_yes":
                    float(
                        chosen[
                            "market_raw_yes"
                        ]
                    ),

                "probability_gap":
                    top_gap,

                "second_best_gap":
                    second_gap,

                "selection_margin":
                    (
                        top_gap
                        - second_gap
                    ),

                "target_available":
                    target_available,

                "Y":
                    (
                        float(
                            chosen[
                                "Y"
                            ]
                        )
                        if target_available
                        else np.nan
                    ),

                "hko_daily_max_c":
                    (
                        float(
                            chosen[
                                "hko_daily_max_c"
                            ]
                        )
                        if target_available
                        else np.nan
                    ),

                "raw_temperature_c":
                    float(
                        chosen[
                            "raw_temperature_c"
                        ]
                    ),

                "static_mean_c":
                    float(
                        chosen[
                            "static_mean_c"
                        ]
                    ),

                "static_sd_c":
                    float(
                        chosen[
                            "static_sd_c"
                        ]
                    ),

                "selected_gp_mean_c":
                    float(
                        chosen[
                            "selected_gp_mean_c"
                        ]
                    ),

                "selected_gp_sd_c":
                    float(
                        chosen[
                            "selected_gp_sd_c"
                        ]
                    ),

                "record_age_hours":
                    float(
                        chosen[
                            "record_age_hours"
                        ]
                    ),

                "decision_cutoff_utc":
                    chosen[
                        "decision_cutoff_utc"
                    ],

                "selected_price_timestamp_utc":
                    chosen[
                        "selected_price_timestamp_utc"
                    ],
            }
        )

    return pd.DataFrame(
        rows
    ).sort_values(
        "event_date"
    ).reset_index(
        drop=True
    )


def activate_candidates(
    candidates,
    *,
    threshold,
    cost,
):
    x = candidates.copy()

    x[
        "threshold"
    ] = float(
        threshold
    )

    x[
        "reference_cost"
    ] = float(
        cost
    )

    x[
        "trade"
    ] = (
        x[
            "probability_gap"
        ]
        >= (
            float(
                threshold
            )
            - EPS
        )
    )

    x[
        "threshold_margin"
    ] = (
        x[
            "probability_gap"
        ]
        - float(
            threshold
        )
    )

    # A no-trade payoff is known to be zero even if settlement is pending.
    x[
        "gross_pnl"
    ] = 0.0

    x[
        "net_pnl"
    ] = 0.0

    settled_trade = (
        x[
            "trade"
        ]
        & x[
            "target_available"
        ]
    )

    pending_trade = (
        x[
            "trade"
        ]
        & ~x[
            "target_available"
        ]
    )

    x.loc[
        settled_trade,
        "gross_pnl",
    ] = (
        x.loc[
            settled_trade,
            "Y",
        ]
        - x.loc[
            settled_trade,
            "market_raw_yes",
        ]
    )

    x.loc[
        settled_trade,
        "net_pnl",
    ] = (
        x.loc[
            settled_trade,
            "gross_pnl",
        ]
        - float(
            cost
        )
    )

    x.loc[
        pending_trade,
        [
            "gross_pnl",
            "net_pnl",
        ],
    ] = np.nan

    x[
        "entry_cash"
    ] = np.where(
        x[
            "trade"
        ],
        (
            x[
                "market_raw_yes"
            ]
            + float(
                cost
            )
        ),
        0.0,
    )

    return x


# =============================================================================
# STEP 40–42: DEVELOPMENT THRESHOLD / RULE SELECTION
# =============================================================================


def threshold_statistics(
    candidates,
    *,
    threshold,
    cost,
):
    x = activate_candidates(
        candidates,
        threshold=
            threshold,
        cost=
            cost,
    )

    x = x[
        x[
            "target_available"
        ]
    ]

    n = len(
        x
    )

    pnl = x[
        "net_pnl"
    ].to_numpy(
        dtype=float
    )

    trade_count = int(
        x[
            "trade"
        ].sum()
    )

    mean = (
        float(
            pnl.mean()
        )
        if n
        else np.nan
    )

    sd = (
        float(
            pnl.std(
                ddof=1
            )
        )
        if n >= 2
        else np.nan
    )

    se = (
        sd
        / math.sqrt(
            n
        )
        if (
            n >= 2
            and np.isfinite(
                sd
            )
        )
        else np.nan
    )

    return {
        "threshold":
            float(
                threshold
            ),

        "eligible_dates":
            n,

        "trade_count":
            trade_count,

        "trade_rate":
            (
                trade_count
                / n
                if n
                else np.nan
            ),

        "total_net_pnl":
            (
                float(
                    pnl.sum()
                )
                if n
                else np.nan
            ),

        "mean_daily_pnl":
            mean,

        "sample_sd_daily_pnl":
            sd,

        "se_mean_daily_pnl":
            se,

        "sample_sharpe":
            sample_sharpe(
                pnl
            ),
    }


def select_threshold_for_rule(
    candidates,
    *,
    cost,
):
    rows = [
        threshold_statistics(
            candidates,
            threshold=h,
            cost=cost,
        )
        for h in THRESHOLD_GRID
    ]

    grid = pd.DataFrame(
        rows
    )

    grid[
        "threshold_eligible"
    ] = (
        grid[
            "trade_count"
        ]
        >= MIN_DEVELOPMENT_TRADES
    )

    eligible = grid[
        grid[
            "threshold_eligible"
        ]
    ].copy()

    if eligible.empty:
        return (
            grid,
            None,
        )

    max_mean = float(
        eligible[
            "mean_daily_pnl"
        ].max()
    )

    best_candidates = eligible[
        np.isclose(
            eligible[
                "mean_daily_pnl"
            ],
            max_mean,
            atol=1e-14,
            rtol=0.0,
        )
    ]

    # Conservative deterministic tie-break:
    # largest threshold among equal maxima.
    h_best = float(
        best_candidates[
            "threshold"
        ].max()
    )

    best_row = eligible[
        np.isclose(
            eligible[
                "threshold"
            ],
            h_best,
            atol=1e-14,
        )
    ].iloc[0]

    se_best = float(
        best_row[
            "se_mean_daily_pnl"
        ]
    )

    one_se_cutoff = (
        float(
            best_row[
                "mean_daily_pnl"
            ]
        )
        - se_best
    )

    one_se = eligible[
        eligible[
            "mean_daily_pnl"
        ]
        >= (
            one_se_cutoff
            - EPS
        )
    ]

    h_star = float(
        one_se[
            "threshold"
        ].max()
    )

    selected = eligible[
        np.isclose(
            eligible[
                "threshold"
            ],
            h_star,
            atol=1e-14,
        )
    ].iloc[0]

    result = {
        "h_best":
            h_best,

        "best_mean_daily_pnl":
            float(
                best_row[
                    "mean_daily_pnl"
                ]
            ),

        "se_at_h_best":
            se_best,

        "one_se_cutoff":
            one_se_cutoff,

        "h_star":
            h_star,

        "h_star_mean_daily_pnl":
            float(
                selected[
                    "mean_daily_pnl"
                ]
            ),

        "h_star_se":
            float(
                selected[
                    "se_mean_daily_pnl"
                ]
            ),

        "h_star_conservative_score":
            (
                float(
                    selected[
                        "mean_daily_pnl"
                    ]
                )
                - float(
                    selected[
                        "se_mean_daily_pnl"
                    ]
                )
            ),

        "h_star_trade_count":
            int(
                selected[
                    "trade_count"
                ]
            ),

        "development_dates":
            int(
                selected[
                    "eligible_dates"
                ]
            ),
    }

    return (
        grid,
        result,
    )


def development_selection(
    panel,
):
    all_candidates = []
    all_grids = []
    rule_results = []

    candidate_by_rule = {}

    for rule in RULE_ORDER:
        candidates = base_candidates(
            panel,
            period=
                DEVELOPMENT_PERIOD,
            rule=
                rule,
            source=
                "selected_gp",
        )

        candidate_by_rule[
            rule
        ] = candidates

        all_candidates.append(
            candidates
        )

        (
            grid,
            result,
        ) = select_threshold_for_rule(
            candidates,
            cost=
                REFERENCE_COST,
        )

        grid[
            "decision_rule"
        ] = rule

        all_grids.append(
            grid
        )

        if result is not None:
            result[
                "decision_rule"
            ] = rule

            result[
                "rule_order"
            ] = (
                RULE_ORDER.index(
                    rule
                )
            )

            rule_results.append(
                result
            )

    if not rule_results:
        raise RuntimeError(
            "No rule has an eligible development threshold."
        )

    rule_df = pd.DataFrame(
        rule_results
    )

    best_score = float(
        rule_df[
            "h_star_conservative_score"
        ].max()
    )

    tied = rule_df[
        np.isclose(
            rule_df[
                "h_star_conservative_score"
            ],
            best_score,
            atol=1e-14,
            rtol=0.0,
        )
    ].sort_values(
        "rule_order"
    )

    selected = tied.iloc[
        0
    ]

    policy = {
        "selection_probability_source":
            "selected_gp",

        "selection_probability_column":
            "p_selected_gp",

        "market_entry_proxy":
            "raw event-level historical YES value",

        "development_period":
            "2026-03-16 to 2026-06-30",

        "external_period":
            "2026-07-01 to 2026-08-31",

        "threshold_grid":
            [
                float(
                    x
                )
                for x in THRESHOLD_GRID
            ],

        "minimum_development_trades":
            MIN_DEVELOPMENT_TRADES,

        "one_se_rule":
            (
                "For each decision rule: identify the largest "
                "threshold attaining the maximum mean daily "
                "development PnL; calculate its ordinary "
                "SE across eligible settlement dates including "
                "zero-PnL no-trade dates; retain all eligible "
                "thresholds whose mean PnL is at least "
                "best_mean-SE(best); choose the largest such "
                "threshold."
            ),

        "rule_selection":
            (
                "Choose the rule with the largest "
                "mean(h_star)-SE(h_star); ties use fixed order "
                "24h,12h,6h,event-day-open."
            ),

        "selected_rule":
            selected[
                "decision_rule"
            ],

        "selected_threshold":
            float(
                selected[
                    "h_star"
                ]
            ),

        "reference_cost_per_share":
            REFERENCE_COST,

        "one_long_yes_share_max_per_date":
            True,

        "equal_gap_tie_break":
            "lowest certified event_rank",

        "raw_static_reoptimised":
            False,

        "pool_used_for_trading":
            False,

        "external_data_used_for_selection":
            False,

        "selected_rule_development_dates":
            int(
                selected[
                    "development_dates"
                ]
            ),

        "selected_rule_development_trades":
            int(
                selected[
                    "h_star_trade_count"
                ]
            ),

        "selected_rule_conservative_score":
            float(
                selected[
                    "h_star_conservative_score"
                ]
            ),
    }

    return (
        pd.concat(
            all_candidates,
            ignore_index=True,
        ),
        pd.concat(
            all_grids,
            ignore_index=True,
        ),
        rule_df,
        candidate_by_rule,
        policy,
    )


def common_rule_selection_sensitivity(
    candidate_by_rule,
):
    date_sets = [
        set(
            x.loc[
                x[
                    "target_available"
                ],
                "event_date",
            ]
        )
        for x in candidate_by_rule.values()
    ]

    if not date_sets:
        return pd.DataFrame()

    common_dates = set.intersection(
        *date_sets
    )

    rows = []

    for rule in RULE_ORDER:
        x = candidate_by_rule[
            rule
        ]

        x = x[
            x[
                "event_date"
            ].isin(
                common_dates
            )
        ].copy()

        (
            grid,
            result,
        ) = select_threshold_for_rule(
            x,
            cost=
                REFERENCE_COST,
        )

        if result is None:
            continue

        rows.append(
            {
                "decision_rule":
                    rule,

                "common_all_rule_dates":
                    len(
                        common_dates
                    ),

                **result,
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 44–46: FROZEN POLICY ATTRIBUTION
# =============================================================================


def build_fixed_policy_ledgers(
    panel,
    policy,
):
    rows = []

    rule = policy[
        "selected_rule"
    ]

    threshold = policy[
        "selected_threshold"
    ]

    for period in [
        DEVELOPMENT_PERIOD,
        EXTERNAL_PERIOD,
    ]:
        for source in METHOD_ORDER:
            candidates = base_candidates(
                panel,
                period=
                    period,
                rule=
                    rule,
                source=
                    source,
            )

            ledger = activate_candidates(
                candidates,
                threshold=
                    threshold,
                cost=
                    REFERENCE_COST,
            )

            rows.append(
                ledger
            )

    return pd.concat(
        rows,
        ignore_index=True,
    )


def risk_statistics(
    ledger,
):
    x = ledger[
        ledger[
            "target_available"
        ]
    ].sort_values(
        "event_date"
    )

    pnl = x[
        "net_pnl"
    ].to_numpy(
        dtype=float
    )

    gross = x[
        "gross_pnl"
    ].to_numpy(
        dtype=float
    )

    trades = x[
        x[
            "trade"
        ]
    ]

    trade_pnl = trades[
        "net_pnl"
    ].to_numpy(
        dtype=float
    )

    positives = trade_pnl[
        trade_pnl > 0
    ]

    negatives = trade_pnl[
        trade_pnl < 0
    ]

    total_abs_trade_pnl = float(
        np.abs(
            trade_pnl
        ).sum()
    )

    sorted_abs = np.sort(
        np.abs(
            trade_pnl
        )
    )[
        ::-1
    ]

    top1 = (
        float(
            sorted_abs[
                0
            ]
            / total_abs_trade_pnl
        )
        if (
            len(
                sorted_abs
            )
            and total_abs_trade_pnl > 0
        )
        else np.nan
    )

    top2 = (
        float(
            sorted_abs[
                :2
            ].sum()
            / total_abs_trade_pnl
        )
        if (
            len(
                sorted_abs
            )
            and total_abs_trade_pnl > 0
        )
        else np.nan
    )

    aggregate_entry_cash = float(
        trades[
            "entry_cash"
        ].sum()
    )

    total_net = float(
        pnl.sum()
    )

    total_gross = float(
        gross.sum()
    )

    ntr = int(
        trades.shape[
            0
        ]
    )

    downside = np.minimum(
        pnl,
        0.0,
    )

    sample_sr = sample_sharpe(
        pnl
    )

    return {
        "eligible_settled_dates":
            len(
                x
            ),

        "trade_count":
            ntr,

        "trade_rate":
            (
                ntr
                / len(
                    x
                )
                if len(
                    x
                )
                else np.nan
            ),

        "winning_contract_count":
            int(
                (
                    trades[
                        "Y"
                    ]
                    == 1
                ).sum()
            ),

        "contract_hit_rate":
            (
                float(
                    (
                        trades[
                            "Y"
                        ]
                        == 1
                    ).mean()
                )
                if ntr
                else np.nan
            ),

        "net_win_rate":
            (
                float(
                    (
                        trades[
                            "net_pnl"
                        ]
                        > 0
                    ).mean()
                )
                if ntr
                else np.nan
            ),

        "total_gross_pnl":
            total_gross,

        "total_reference_cost":
            (
                ntr
                * REFERENCE_COST
            ),

        "total_net_pnl":
            total_net,

        "mean_daily_net_pnl":
            (
                float(
                    pnl.mean()
                )
                if len(
                    pnl
                )
                else np.nan
            ),

        "sample_sd_daily_net_pnl":
            (
                float(
                    pnl.std(
                        ddof=1
                    )
                )
                if len(
                    pnl
                ) >= 2
                else np.nan
            ),

        "settlement_date_sharpe":
            sample_sr,

        "sqrt365_descriptive_sharpe":
            (
                sample_sr
                * math.sqrt(
                    365.0
                )
                if np.isfinite(
                    sample_sr
                )
                else np.nan
            ),

        "downside_deviation_zero_target":
            (
                float(
                    np.sqrt(
                        np.mean(
                            downside ** 2
                        )
                    )
                )
                if len(
                    pnl
                )
                else np.nan
            ),

        "expected_shortfall_5pct":
            expected_shortfall_5(
                pnl
            ),

        "average_trade_pnl":
            (
                float(
                    trade_pnl.mean()
                )
                if ntr
                else np.nan
            ),

        "average_win":
            (
                float(
                    positives.mean()
                )
                if len(
                    positives
                )
                else np.nan
            ),

        "average_loss":
            (
                float(
                    negatives.mean()
                )
                if len(
                    negatives
                )
                else np.nan
            ),

        "largest_gain":
            (
                float(
                    trade_pnl.max()
                )
                if ntr
                else np.nan
            ),

        "largest_loss":
            (
                float(
                    trade_pnl.min()
                )
                if ntr
                else np.nan
            ),

        "profit_factor":
            (
                float(
                    positives.sum()
                    / abs(
                        negatives.sum()
                    )
                )
                if (
                    len(
                        positives
                    )
                    and len(
                        negatives
                    )
                    and abs(
                        negatives.sum()
                    )
                    > 0
                )
                else np.nan
            ),

        "maximum_drawdown":
            maximum_drawdown(
                pnl
            ),

        "aggregate_entry_cash":
            aggregate_entry_cash,

        "return_on_entry_cash":
            (
                total_net
                / aggregate_entry_cash
                if aggregate_entry_cash > 0
                else np.nan
            ),

        "break_even_cost_per_trade":
            (
                total_gross
                / ntr
                if ntr > 0
                else np.nan
            ),

        "top1_absolute_pnl_concentration":
            top1,

        "top2_absolute_pnl_concentration":
            top2,
    }


def build_risk_summary(
    ledgers,
):
    rows = []

    for (
        period,
        source,
    ), ledger in ledgers.groupby(
        [
            "empirical_period",
            "probability_source",
        ]
    ):
        rows.append(
            {
                "analysis_period":
                    period,

                "probability_source":
                    source,

                **risk_statistics(
                    ledger
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


def attribution_objects(
    ledgers,
):
    external = ledgers[
        ledgers[
            "empirical_period"
        ]
        == EXTERNAL_PERIOD
    ]

    method = {
        source:
            external[
                external[
                    "probability_source"
                ]
                == source
            ]
            .sort_values(
                "event_date"
            )
            .copy()
        for source in METHOD_ORDER
    }

    date_sets = [
        set(
            x[
                "event_date"
            ]
        )
        for x in method.values()
    ]

    common_dates = set.intersection(
        *date_sets
    )

    panels = []

    for source, x in method.items():
        y = x[
            x[
                "event_date"
            ].isin(
                common_dates
            )
        ][
            [
                "event_date",
                "target_available",
                "market_id",
                "event_rank",
                "group_item_title",
                "probability_gap",
                "trade",
                "gross_pnl",
                "net_pnl",
            ]
        ].copy()

        y = y.rename(
            columns={
                c:
                    (
                        c
                        if c
                        == "event_date"
                        else (
                            f"{source}_{c}"
                        )
                    )
                for c in y.columns
            }
        )

        panels.append(
            y
        )

    merged = panels[
        0
    ]

    for x in panels[
        1:
    ]:
        merged = merged.merge(
            x,
            on="event_date",
            how="inner",
            validate="one_to_one",
        )

    rows = []

    totals = {}

    for source in METHOD_ORDER:
        settled = merged[
            merged[
                f"{source}_target_available"
            ].astype(
                bool
            )
        ]

        totals[
            source
        ] = float(
            settled[
                f"{source}_net_pnl"
            ].sum()
        )

    raw = totals[
        "raw"
    ]

    static = totals[
        "static"
    ]

    gp = totals[
        "selected_gp"
    ]

    denominator = (
        gp
        - raw
    )

    closure = (
        (
            static
            - raw
        )
        / denominator
        if abs(
            denominator
        ) > EPS
        else np.nan
    )

    rows.extend(
        [
            {
                "quantity":
                    "external_net_pnl_raw",
                "value":
                    raw,
            },
            {
                "quantity":
                    "external_net_pnl_static",
                "value":
                    static,
            },
            {
                "quantity":
                    "external_net_pnl_selected_gp",
                "value":
                    gp,
            },
            {
                "quantity":
                    "static_minus_raw_external_net_pnl",
                "value":
                    (
                        static
                        - raw
                    ),
            },
            {
                "quantity":
                    "selected_gp_minus_static_external_net_pnl",
                "value":
                    (
                        gp
                        - static
                    ),
            },
            {
                "quantity":
                    "selected_gp_minus_raw_external_net_pnl",
                "value":
                    denominator,
            },
            {
                "quantity":
                    "raw_to_gp_pnl_gap_closed_by_static",
                "value":
                    closure,
            },
        ]
    )

    overlap_rows = []

    for left, right in [
        (
            "raw",
            "static",
        ),
        (
            "static",
            "selected_gp",
        ),
        (
            "raw",
            "selected_gp",
        ),
    ]:
        same_contract = (
            merged[
                f"{left}_event_rank"
            ]
            == merged[
                f"{right}_event_rank"
            ]
        )

        same_trade = (
            merged[
                f"{left}_trade"
            ]
            == merged[
                f"{right}_trade"
            ]
        )

        joint_abstain = (
            ~merged[
                f"{left}_trade"
            ].astype(
                bool
            )
            & ~merged[
                f"{right}_trade"
            ].astype(
                bool
            )
        )

        categories = np.select(
            [
                joint_abstain,
                (
                    same_contract
                    & same_trade
                ),
                (
                    same_contract
                    & ~same_trade
                ),
                ~same_contract,
            ],
            [
                "joint_abstention",
                "same_contract_same_activation",
                "same_contract_activation_diff",
                "different_selected_contract",
            ],
            default=
                "other",
        )

        counts = (
            pd.Series(
                categories
            )
            .value_counts()
        )

        for category, count in (
            counts.items()
        ):
            overlap_rows.append(
                {
                    "comparison":
                        (
                            left
                            + "_vs_"
                            + right
                        ),

                    "category":
                        category,

                    "dates":
                        int(
                            count
                        ),

                    "share":
                        float(
                            count
                            / len(
                                merged
                            )
                        ),
                }
            )

    return (
        merged,
        pd.DataFrame(
            rows
        ),
        pd.DataFrame(
            overlap_rows
        ),
    )


# =============================================================================
# STEP 48–49: BOOTSTRAP + COST SENSITIVITY
# =============================================================================


def bootstrap_one_series(
    values,
    *,
    block,
    seed,
):
    x = np.asarray(
        values,
        dtype=float,
    )

    n = len(
        x
    )

    if n < 2:
        return {}

    idx = bootstrap_indices(
        n,
        block=
            block,
        seed=
            seed,
    )

    sample = x[
        idx
    ]

    total = sample.sum(
        axis=1
    )

    mean = sample.mean(
        axis=1
    )

    sd = sample.std(
        axis=1,
        ddof=1,
    )

    sharpe = np.divide(
        mean,
        sd,
        out=np.full_like(
            mean,
            np.nan,
            dtype=float,
        ),
        where=
            sd > 0,
    )

    total_ci = quantile_interval(
        total
    )

    mean_ci = quantile_interval(
        mean
    )

    sharpe_ci = quantile_interval(
        sharpe
    )

    return {
        "n_dates":
            n,

        "total_pnl_lower_95":
            total_ci[
                0
            ],

        "total_pnl_upper_95":
            total_ci[
                1
            ],

        "mean_pnl_lower_95":
            mean_ci[
                0
            ],

        "mean_pnl_upper_95":
            mean_ci[
                1
            ],

        "sharpe_lower_95":
            sharpe_ci[
                0
            ],

        "sharpe_upper_95":
            sharpe_ci[
                1
            ],
    }


def build_bootstrap_summary(
    ledgers,
):
    rows = []
    seed_offset = 0

    for period in [
        DEVELOPMENT_PERIOD,
        EXTERNAL_PERIOD,
    ]:
        for source in METHOD_ORDER:
            x = ledgers[
                (
                    ledgers[
                        "empirical_period"
                    ]
                    == period
                )
                & (
                    ledgers[
                        "probability_source"
                    ]
                    == source
                )
                & (
                    ledgers[
                        "target_available"
                    ]
                )
            ].sort_values(
                "event_date"
            )

            values = x[
                "net_pnl"
            ].to_numpy(
                dtype=float
            )

            for block, name in [
                (
                    False,
                    "ordinary_date",
                ),
                (
                    True,
                    "circular_block7",
                ),
            ]:
                result = bootstrap_one_series(
                    values,
                    block=
                        block,
                    seed=
                        (
                            BOOTSTRAP_SEED
                            + seed_offset
                        ),
                )

                rows.append(
                    {
                        "analysis_period":
                            period,

                        "estimand":
                            "method_level",

                        "source_a":
                            source,

                        "source_b":
                            "",

                        "bootstrap":
                            name,

                        "point_total_pnl":
                            float(
                                values.sum()
                            ),

                        "point_mean_pnl":
                            float(
                                values.mean()
                            ),

                        "point_sharpe":
                            sample_sharpe(
                                values
                            ),

                        **result,
                    }
                )

                seed_offset += 1

    # Paired contrasts on identical selected-rule date support.
    for period in [
        DEVELOPMENT_PERIOD,
        EXTERNAL_PERIOD,
    ]:
        data = {}

        for source in METHOD_ORDER:
            x = ledgers[
                (
                    ledgers[
                        "empirical_period"
                    ]
                    == period
                )
                & (
                    ledgers[
                        "probability_source"
                    ]
                    == source
                )
                & (
                    ledgers[
                        "target_available"
                    ]
                )
            ][
                [
                    "event_date",
                    "net_pnl",
                ]
            ].rename(
                columns={
                    "net_pnl":
                        source
                }
            )

            data[
                source
            ] = x

        pair_base = data[
            "raw"
        ]

        for source in [
            "static",
            "selected_gp",
        ]:
            pair_base = pair_base.merge(
                data[
                    source
                ],
                on="event_date",
                how="inner",
                validate="one_to_one",
            )

        for a, b in [
            (
                "static",
                "raw",
            ),
            (
                "selected_gp",
                "static",
            ),
            (
                "selected_gp",
                "raw",
            ),
        ]:
            diff = (
                pair_base[
                    a
                ]
                - pair_base[
                    b
                ]
            ).to_numpy(
                dtype=float
            )

            for block, name in [
                (
                    False,
                    "ordinary_date",
                ),
                (
                    True,
                    "circular_block7",
                ),
            ]:
                result = bootstrap_one_series(
                    diff,
                    block=
                        block,
                    seed=
                        (
                            BOOTSTRAP_SEED
                            + 500
                            + seed_offset
                        ),
                )

                rows.append(
                    {
                        "analysis_period":
                            period,

                        "estimand":
                            "paired_pnl_difference",

                        "source_a":
                            a,

                        "source_b":
                            b,

                        "bootstrap":
                            name,

                        "point_total_pnl":
                            float(
                                diff.sum()
                            ),

                        "point_mean_pnl":
                            float(
                                diff.mean()
                            ),

                        "point_sharpe":
                            sample_sharpe(
                                diff
                            ),

                        **result,
                    }
                )

                seed_offset += 1

    return pd.DataFrame(
        rows
    )


def cost_sensitivity(
    gp_external_ledger,
):
    x = gp_external_ledger[
        gp_external_ledger[
            "target_available"
        ]
    ].sort_values(
        "event_date"
    )

    rows = []

    for cost in COST_GRID:
        pnl = np.where(
            x[
                "trade"
            ],
            (
                x[
                    "gross_pnl"
                ]
                - float(
                    cost
                )
            ),
            0.0,
        )

        entry_cash = np.where(
            x[
                "trade"
            ],
            (
                x[
                    "market_raw_yes"
                ]
                + float(
                    cost
                )
            ),
            0.0,
        )

        rows.append(
            {
                "cost_per_trade":
                    float(
                        cost
                    ),

                "settled_dates":
                    len(
                        x
                    ),

                "trade_count":
                    int(
                        x[
                            "trade"
                        ].sum()
                    ),

                "total_net_pnl":
                    float(
                        pnl.sum()
                    ),

                "mean_daily_pnl":
                    float(
                        pnl.mean()
                    ),

                "sample_sharpe":
                    sample_sharpe(
                        pnl
                    ),

                "maximum_drawdown":
                    maximum_drawdown(
                        pnl
                    ),

                "aggregate_entry_cash":
                    float(
                        entry_cash.sum()
                    ),

                "return_on_entry_cash":
                    (
                        float(
                            pnl.sum()
                            / entry_cash.sum()
                        )
                        if entry_cash.sum() > 0
                        else np.nan
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 50–52: GAUSSIAN DELTA/GAMMA + DECISION MARGINS
# =============================================================================


def gaussian_event_probability(
    mu,
    sigma,
    lower,
    upper,
):
    if sigma <= 0:
        raise RuntimeError(
            "Non-positive predictive sigma."
        )

    if np.isneginf(
        lower
    ):
        z = (
            upper
            - mu
        ) / sigma

        return float(
            norm.cdf(
                z
            )
        )

    if np.isposinf(
        upper
    ):
        z = (
            lower
            - mu
        ) / sigma

        return float(
            1.0
            - norm.cdf(
                z
            )
        )

    za = (
        lower
        - mu
    ) / sigma

    zb = (
        upper
        - mu
    ) / sigma

    return float(
        norm.cdf(
            zb
        )
        - norm.cdf(
            za
        )
    )


def gaussian_event_delta_gamma(
    mu,
    sigma,
    lower,
    upper,
):
    if sigma <= 0:
        raise RuntimeError(
            "Non-positive predictive sigma."
        )

    if np.isneginf(
        lower
    ):
        z = (
            upper
            - mu
        ) / sigma

        delta = (
            -norm.pdf(
                z
            )
            / sigma
        )

        gamma = (
            -z
            * norm.pdf(
                z
            )
            / (
                sigma ** 2
            )
        )

        return (
            float(
                delta
            ),
            float(
                gamma
            ),
        )

    if np.isposinf(
        upper
    ):
        z = (
            lower
            - mu
        ) / sigma

        delta = (
            norm.pdf(
                z
            )
            / sigma
        )

        gamma = (
            z
            * norm.pdf(
                z
            )
            / (
                sigma ** 2
            )
        )

        return (
            float(
                delta
            ),
            float(
                gamma
            ),
        )

    za = (
        lower
        - mu
    ) / sigma

    zb = (
        upper
        - mu
    ) / sigma

    delta = (
        norm.pdf(
            za
        )
        - norm.pdf(
            zb
        )
    ) / sigma

    gamma = (
        za
        * norm.pdf(
            za
        )
        - zb
        * norm.pdf(
            zb
        )
    ) / (
        sigma ** 2
    )

    return (
        float(
            delta
        ),
        float(
            gamma
        ),
    )


def derivative_panel(
    panel,
    policy,
    gp_external_ledger,
):
    rule = policy[
        "selected_rule"
    ]

    threshold = policy[
        "selected_threshold"
    ]

    x = panel[
        (
            panel[
                "empirical_period"
            ]
            == EXTERNAL_PERIOD
        )
        & (
            panel[
                "decision_rule"
            ]
            == rule
        )
    ].copy()

    rows = []
    validation = []

    finite_eps = 1e-5

    for _, row in x.iterrows():
        mu = float(
            row[
                "selected_gp_mean_c"
            ]
        )

        sigma = float(
            row[
                "selected_gp_sd_c"
            ]
        )

        lower = float(
            row[
                "lower_bound_c"
            ]
        )

        upper = float(
            row[
                "upper_bound_c"
            ]
        )

        p0 = gaussian_event_probability(
            mu,
            sigma,
            lower,
            upper,
        )

        (
            delta,
            gamma,
        ) = gaussian_event_delta_gamma(
            mu,
            sigma,
            lower,
            upper,
        )

        p_plus = gaussian_event_probability(
            (
                mu
                + finite_eps
            ),
            sigma,
            lower,
            upper,
        )

        p_minus = gaussian_event_probability(
            (
                mu
                - finite_eps
            ),
            sigma,
            lower,
            upper,
        )

        finite_delta = (
            p_plus
            - p_minus
        ) / (
            2
            * finite_eps
        )

        finite_gamma = (
            p_plus
            - 2
            * p0
            + p_minus
        ) / (
            finite_eps ** 2
        )

        validation.append(
            {
                "event_date":
                    row[
                        "event_date"
                    ],

                "event_rank":
                    row[
                        "event_rank"
                    ],

                "probability_reconstruction_error":
                    (
                        p0
                        - float(
                            row[
                                "p_selected_gp"
                            ]
                        )
                    ),

                "delta_error_vs_finite_difference":
                    (
                        delta
                        - finite_delta
                    ),

                "gamma_error_vs_finite_difference":
                    (
                        gamma
                        - finite_gamma
                    ),
            }
        )

        rows.append(
            {
                **row.to_dict(),

                "reconstructed_probability":
                    p0,

                "weather_delta_mu":
                    delta,

                "weather_gamma_mu":
                    gamma,

                "gp_market_gap":
                    (
                        p0
                        - float(
                            row[
                                "market_raw_yes"
                            ]
                        )
                    ),
            }
        )

    event_sensitivity = pd.DataFrame(
        rows
    )

    validation_df = pd.DataFrame(
        validation
    )

    selected_rows = []

    gp_map = (
        gp_external_ledger
        .set_index(
            "event_date"
        )
    )

    for date, book in (
        event_sensitivity.groupby(
            "event_date",
            sort=True,
        )
    ):
        ledger_row = gp_map.loc[
            date
        ]

        selected_rank = int(
            ledger_row[
                "event_rank"
            ]
        )

        selected = book[
            book[
                "event_rank"
            ]
            == selected_rank
        ].iloc[
            0
        ]

        finite_boundaries = []

        for value in (
            book[
                [
                    "lower_bound_c",
                    "upper_bound_c",
                ]
            ]
            .to_numpy()
            .ravel()
        ):
            if np.isfinite(
                value
            ):
                finite_boundaries.append(
                    float(
                        value
                    )
                )

        mu = float(
            selected[
                "selected_gp_mean_c"
            ]
        )

        nearest_boundary = (
            min(
                abs(
                    mu
                    - b
                )
                for b
                in finite_boundaries
            )
            if finite_boundaries
            else np.nan
        )

        selected_contract_bounds = [
            float(
                selected[
                    "lower_bound_c"
                ]
            ),
            float(
                selected[
                    "upper_bound_c"
                ]
            ),
        ]

        selected_contract_bounds = [
            b
            for b
            in selected_contract_bounds
            if np.isfinite(
                b
            )
        ]

        selected_boundary_distance = (
            min(
                abs(
                    mu
                    - b
                )
                for b
                in selected_contract_bounds
            )
            if selected_contract_bounds
            else np.nan
        )

        target_available = bool(
            ledger_row[
                "target_available"
            ]
        )

        hko = (
            float(
                ledger_row[
                    "hko_daily_max_c"
                ]
            )
            if target_available
            else np.nan
        )

        selected_rows.append(
            {
                "event_date":
                    date,

                "decision_rule":
                    policy[
                        "selected_rule"
                    ],

                "selected_threshold":
                    threshold,

                "event_rank":
                    selected_rank,

                "market_id":
                    selected[
                        "market_id"
                    ],

                "group_item_title":
                    selected[
                        "group_item_title"
                    ],

                "contract_event_type":
                    selected[
                        "contract_event_type"
                    ],

                "gp_probability":
                    float(
                        selected[
                            "p_selected_gp"
                        ]
                    ),

                "market_raw_yes":
                    float(
                        selected[
                            "market_raw_yes"
                        ]
                    ),

                "probability_gap":
                    float(
                        ledger_row[
                            "probability_gap"
                        ]
                    ),

                "threshold_margin":
                    float(
                        ledger_row[
                            "threshold_margin"
                        ]
                    ),

                "selection_margin":
                    float(
                        ledger_row[
                            "selection_margin"
                        ]
                    ),

                "nearest_book_boundary_distance_c":
                    nearest_boundary,

                "selected_contract_boundary_distance_c":
                    selected_boundary_distance,

                "selected_gp_mean_c":
                    mu,

                "selected_gp_sd_c":
                    float(
                        selected[
                            "selected_gp_sd_c"
                        ]
                    ),

                "weather_delta_mu":
                    float(
                        selected[
                            "weather_delta_mu"
                        ]
                    ),

                "weather_gamma_mu":
                    float(
                        selected[
                            "weather_gamma_mu"
                        ]
                    ),

                "trade":
                    bool(
                        ledger_row[
                            "trade"
                        ]
                    ),

                "target_available":
                    target_available,

                "Y":
                    (
                        float(
                            ledger_row[
                                "Y"
                            ]
                        )
                        if target_available
                        else np.nan
                    ),

                "gross_pnl":
                    (
                        float(
                            ledger_row[
                                "gross_pnl"
                            ]
                        )
                        if target_available
                        else np.nan
                    ),

                "net_pnl":
                    (
                        float(
                            ledger_row[
                                "net_pnl"
                            ]
                        )
                        if target_available
                        else np.nan
                    ),

                "hko_daily_max_c":
                    hko,

                "raw_temperature_c":
                    float(
                        ledger_row[
                            "raw_temperature_c"
                        ]
                    ),

                "signed_raw_temperature_error_c":
                    (
                        hko
                        - float(
                            ledger_row[
                                "raw_temperature_c"
                            ]
                        )
                        if target_available
                        else np.nan
                    ),

                "absolute_raw_temperature_error_c":
                    (
                        abs(
                            hko
                            - float(
                                ledger_row[
                                    "raw_temperature_c"
                                ]
                            )
                        )
                        if target_available
                        else np.nan
                    ),

                "signed_gp_mean_error_c":
                    (
                        hko
                        - mu
                        if target_available
                        else np.nan
                    ),

                "absolute_gp_mean_error_c":
                    (
                        abs(
                            hko
                            - mu
                        )
                        if target_available
                        else np.nan
                    ),
            }
        )

    return (
        event_sensitivity,
        pd.DataFrame(
            selected_rows
        ),
        validation_df,
    )


# =============================================================================
# STEP 53–54: MEAN SHOCKS + FORECAST ERROR -> PNL
# =============================================================================


def shocked_probabilities_for_book(
    book,
    delta,
):
    mu = float(
        book[
            "selected_gp_mean_c"
        ].iloc[0]
    )

    sigma = float(
        book[
            "selected_gp_sd_c"
        ].iloc[0]
    )

    probs = []

    for _, row in (
        book.sort_values(
            "event_rank"
        )
        .iterrows()
    ):
        probs.append(
            gaussian_event_probability(
                (
                    mu
                    + float(
                        delta
                    )
                ),
                sigma,
                float(
                    row[
                        "lower_bound_c"
                    ]
                ),
                float(
                    row[
                        "upper_bound_c"
                    ]
                ),
            )
        )

    probs = np.asarray(
        probs,
        dtype=float,
    )

    if abs(
        probs.sum()
        - 1.0
    ) > 1e-10:
        raise RuntimeError(
            "Shocked event book does not sum to one."
        )

    return probs


def fixed_contract_shocks(
    panel,
    policy,
    gp_external_ledger,
):
    rule = policy[
        "selected_rule"
    ]

    threshold = policy[
        "selected_threshold"
    ]

    external = panel[
        (
            panel[
                "empirical_period"
            ]
            == EXTERNAL_PERIOD
        )
        & (
            panel[
                "decision_rule"
            ]
            == rule
        )
    ].copy()

    ledger = (
        gp_external_ledger
        .set_index(
            "event_date"
        )
    )

    rows = []

    for date, book in (
        external.groupby(
            "event_date",
            sort=True,
        )
    ):
        baseline = ledger.loc[
            date
        ]

        rank = int(
            baseline[
                "event_rank"
            ]
        )

        contract = book[
            book[
                "event_rank"
            ]
            == rank
        ].iloc[
            0
        ]

        mu = float(
            contract[
                "selected_gp_mean_c"
            ]
        )

        sigma = float(
            contract[
                "selected_gp_sd_c"
            ]
        )

        lower = float(
            contract[
                "lower_bound_c"
            ]
        )

        upper = float(
            contract[
                "upper_bound_c"
            ]
        )

        market = float(
            contract[
                "market_raw_yes"
            ]
        )

        for delta in SHOCK_GRID:
            p = gaussian_event_probability(
                (
                    mu
                    + float(
                        delta
                    )
                ),
                sigma,
                lower,
                upper,
            )

            gap = (
                p
                - market
            )

            rows.append(
                {
                    "event_date":
                        date,

                    "mean_shift_c":
                        float(
                            delta
                        ),

                    "baseline_selected_event_rank":
                        rank,

                    "market_id":
                        contract[
                            "market_id"
                        ],

                    "group_item_title":
                        contract[
                            "group_item_title"
                        ],

                    "baseline_mean_c":
                        mu,

                    "predictive_sd_c":
                        sigma,

                    "shocked_mean_c":
                        (
                            mu
                            + float(
                                delta
                            )
                        ),

                    "fixed_contract_probability":
                        p,

                    "market_raw_yes":
                        market,

                    "fixed_contract_gap":
                        gap,

                    "fixed_contract_model_net_value":
                        (
                            gap
                            - REFERENCE_COST
                        ),

                    "fixed_contract_threshold_margin":
                        (
                            gap
                            - threshold
                        ),

                    "would_activate_fixed_contract":
                        (
                            gap
                            >= (
                                threshold
                                - EPS
                            )
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


def full_strategy_shocks(
    panel,
    policy,
    gp_external_ledger,
):
    rule = policy[
        "selected_rule"
    ]

    threshold = policy[
        "selected_threshold"
    ]

    external = panel[
        (
            panel[
                "empirical_period"
            ]
            == EXTERNAL_PERIOD
        )
        & (
            panel[
                "decision_rule"
            ]
            == rule
        )
    ].copy()

    baseline = (
        gp_external_ledger[
            [
                "event_date",
                "event_rank",
                "trade",
            ]
        ]
        .rename(
            columns={
                "event_rank":
                    "baseline_event_rank",

                "trade":
                    "baseline_trade",
            }
        )
        .set_index(
            "event_date"
        )
    )

    rows = []

    for delta in SHOCK_GRID:
        ledger_rows = []

        for date, book in (
            external.groupby(
                "event_date",
                sort=True,
            )
        ):
            ordered = book.sort_values(
                "event_rank"
            ).copy()

            probs = shocked_probabilities_for_book(
                ordered,
                delta,
            )

            ordered[
                "p_shock"
            ] = probs

            (
                selected,
                top_gap,
                second_gap,
            ) = select_contract_from_book(
                ordered,
                "p_shock",
            )

            trade = bool(
                top_gap
                >= (
                    threshold
                    - EPS
                )
            )

            target_available = bool(
                selected[
                    "target_available"
                ]
            )

            gross = np.nan
            net = np.nan

            if not trade:
                gross = 0.0
                net = 0.0

            elif target_available:
                gross = (
                    float(
                        selected[
                            "Y"
                        ]
                    )
                    - float(
                        selected[
                            "market_raw_yes"
                        ]
                    )
                )

                net = (
                    gross
                    - REFERENCE_COST
                )

            ledger_rows.append(
                {
                    "event_date":
                        date,

                    "event_rank":
                        int(
                            selected[
                                "event_rank"
                            ]
                        ),

                    "trade":
                        trade,

                    "target_available":
                        target_available,

                    "gross_pnl":
                        gross,

                    "net_pnl":
                        net,
                }
            )

        ledger = pd.DataFrame(
            ledger_rows
        ).sort_values(
            "event_date"
        )

        merged = ledger.join(
            baseline,
            on="event_date",
        )

        settled = merged[
            merged[
                "target_available"
            ]
        ]

        pnl = settled[
            "net_pnl"
        ].to_numpy(
            dtype=float
        )

        rows.append(
            {
                "mean_shift_c":
                    float(
                        delta
                    ),

                "all_external_decision_dates":
                    len(
                        merged
                    ),

                "settled_external_dates":
                    len(
                        settled
                    ),

                "trade_count":
                    int(
                        merged[
                            "trade"
                        ].sum()
                    ),

                "settled_trade_count":
                    int(
                        settled[
                            "trade"
                        ].sum()
                    ),

                "total_gross_pnl":
                    float(
                        settled[
                            "gross_pnl"
                        ].sum()
                    ),

                "total_net_pnl":
                    float(
                        pnl.sum()
                    ),

                "mean_daily_pnl":
                    float(
                        pnl.mean()
                    ),

                "sample_sharpe":
                    sample_sharpe(
                        pnl
                    ),

                "maximum_drawdown":
                    maximum_drawdown(
                        pnl
                    ),

                "selected_contract_switch_fraction":
                    float(
                        (
                            merged[
                                "event_rank"
                            ]
                            != merged[
                                "baseline_event_rank"
                            ]
                        ).mean()
                    ),

                "activation_switch_fraction":
                    float(
                        (
                            merged[
                                "trade"
                            ].astype(
                                bool
                            )
                            != merged[
                                "baseline_trade"
                            ].astype(
                                bool
                            )
                        ).mean()
                    ),
            }
        )

    result = pd.DataFrame(
        rows
    ).sort_values(
        "mean_shift_c"
    )

    return result


def finite_portfolio_slopes(
    stress,
):
    index = (
        stress.set_index(
            "mean_shift_c"
        )
    )

    rows = []

    for h in [
        0.10,
        0.25,
        0.50,
        1.00,
    ]:
        positive = index.loc[
            float(
                h
            ),
            "total_net_pnl",
        ]

        negative = index.loc[
            float(
                -h
            ),
            "total_net_pnl",
        ]

        rows.append(
            {
                "central_step_c":
                    h,

                "finite_total_pnl_slope_per_c":
                    float(
                        (
                            positive
                            - negative
                        )
                        / (
                            2.0
                            * h
                        )
                    ),

                "pnl_at_negative_shift":
                    float(
                        negative
                    ),

                "pnl_at_positive_shift":
                    float(
                        positive
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def forecast_error_diagnostics(
    selected_sensitivity,
):
    settled = selected_sensitivity[
        selected_sensitivity[
            "target_available"
        ]
    ].copy()

    settled[
        "absolute_gp_error_quartile"
    ] = pd.qcut(
        settled[
            "absolute_gp_mean_error_c"
        ],
        q=4,
        duplicates="drop",
    )

    bin_rows = []

    for label, group in (
        settled.groupby(
            "absolute_gp_error_quartile",
            observed=True,
        )
    ):
        bin_rows.append(
            {
                "absolute_gp_error_bin":
                    str(
                        label
                    ),

                "dates":
                    len(
                        group
                    ),

                "mean_absolute_gp_error_c":
                    float(
                        group[
                            "absolute_gp_mean_error_c"
                        ].mean()
                    ),

                "trade_rate":
                    float(
                        group[
                            "trade"
                        ].mean()
                    ),

                "mean_probability_gap":
                    float(
                        group[
                            "probability_gap"
                        ].mean()
                    ),

                "mean_daily_pnl":
                    float(
                        group[
                            "net_pnl"
                        ].mean()
                    ),

                "total_pnl":
                    float(
                        group[
                            "net_pnl"
                        ].sum()
                    ),
            }
        )

    correlations = []

    variables = [
        "signed_raw_temperature_error_c",
        "absolute_raw_temperature_error_c",
        "signed_gp_mean_error_c",
        "absolute_gp_mean_error_c",
        "probability_gap",
        "threshold_margin",
        "selection_margin",
        "nearest_book_boundary_distance_c",
        "weather_delta_mu",
        "weather_gamma_mu",
    ]

    for sample_name, sample in [
        (
            "all_settled_dates",
            settled,
        ),
        (
            "executed_trades_only",
            settled[
                settled[
                    "trade"
                ]
            ],
        ),
    ]:
        for variable in variables:
            pair = sample[
                [
                    variable,
                    "net_pnl",
                ]
            ].dropna()

            if len(
                pair
            ) < 3:
                rho = np.nan
                p = np.nan

            else:
                result = spearmanr(
                    pair[
                        variable
                    ],
                    pair[
                        "net_pnl"
                    ],
                )

                rho = float(
                    result.statistic
                )

                p = float(
                    result.pvalue
                )

            correlations.append(
                {
                    "sample":
                        sample_name,

                    "variable":
                        variable,

                    "n":
                        len(
                            pair
                        ),

                    "spearman_rho":
                        rho,

                    "nominal_p_value":
                        p,

                    "multiplicity_adjusted":
                        False,
                }
            )

    return (
        settled,
        pd.DataFrame(
            bin_rows
        ),
        pd.DataFrame(
            correlations
        ),
    )


# =============================================================================
# FIGURES
# =============================================================================


def make_figures(
    threshold_grid,
    policy,
    ledgers,
    stress,
    error_panel,
):
    # Threshold selection.
    fig, ax = plt.subplots(
        figsize=(
            9,
            5,
        )
    )

    for rule in RULE_ORDER:
        x = threshold_grid[
            threshold_grid[
                "decision_rule"
            ]
            == rule
        ]

        ax.plot(
            x[
                "threshold"
            ],
            x[
                "mean_daily_pnl"
            ],
            marker="o",
            markersize=3,
            label=rule,
        )

    ax.axvline(
        policy[
            "selected_threshold"
        ],
        linestyle="--",
    )

    ax.set_xlabel(
        "Probability-gap threshold"
    )

    ax.set_ylabel(
        "Development mean daily net PnL"
    )

    ax.set_title(
        "Development-only threshold and decision-rule selection"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        SELECTION_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    # External cumulative PnL.
    fig, ax = plt.subplots(
        figsize=(
            9,
            5,
        )
    )

    for source in METHOD_ORDER:
        x = ledgers[
            (
                ledgers[
                    "empirical_period"
                ]
                == EXTERNAL_PERIOD
            )
            & (
                ledgers[
                    "probability_source"
                ]
                == source
            )
            & (
                ledgers[
                    "target_available"
                ]
            )
        ].sort_values(
            "event_date"
        )

        ax.plot(
            x[
                "event_date"
            ],
            x[
                "net_pnl"
            ].cumsum(),
            label=source,
        )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.set_xlabel(
        "Settlement date"
    )

    ax.set_ylabel(
        "Cumulative net PnL"
    )

    ax.set_title(
        "Frozen-policy July–August attribution"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        CUMULATIVE_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    # Mean-shift stress.
    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    ax.plot(
        stress[
            "mean_shift_c"
        ],
        stress[
            "total_net_pnl"
        ],
        marker="o",
        markersize=3,
    )

    ax.axvline(
        0.0,
        linewidth=1,
    )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.set_xlabel(
        "Additive fitted-mean shift (°C)"
    )

    ax.set_ylabel(
        "External total net PnL"
    )

    ax.set_title(
        "Forecast-risk transmission through the fixed policy"
    )

    fig.tight_layout()

    fig.savefig(
        STRESS_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    # Forecast error vs date PnL.
    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    ax.scatter(
        error_panel[
            "absolute_gp_mean_error_c"
        ],
        error_panel[
            "net_pnl"
        ],
    )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.set_xlabel(
        "Absolute selected-GP predictive-mean error (°C)"
    )

    ax.set_ylabel(
        "Date-level net PnL"
    )

    ax.set_title(
        "Forecast error and realised fixed-policy PnL"
    )

    fig.tight_layout()

    fig.savefig(
        ERROR_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )


# =============================================================================
# SUPPORT / AUDIT
# =============================================================================


def support_summary(
    panel,
    policy,
    ledgers,
):
    rows = []

    selected_rule = policy[
        "selected_rule"
    ]

    for period in [
        DEVELOPMENT_PERIOD,
        EXTERNAL_PERIOD,
    ]:
        x = panel[
            panel[
                "empirical_period"
            ]
            == period
        ]

        selected = x[
            x[
                "decision_rule"
            ]
            == selected_rule
        ]

        selected_books = (
            selected[
                [
                    "event_date",
                    "decision_rule",
                ]
            ]
            .drop_duplicates()
        )

        selected_ledger = ledgers[
            (
                ledgers[
                    "empirical_period"
                ]
                == period
            )
            & (
                ledgers[
                    "probability_source"
                ]
                == "selected_gp"
            )
        ]

        rows.append(
            {
                "analysis_period":
                    period,

                "all_exact_books":
                    int(
                        x[
                            [
                                "event_date",
                                "decision_rule",
                            ]
                        ]
                        .drop_duplicates()
                        .shape[
                            0
                        ]
                    ),

                "all_exact_dates":
                    int(
                        x[
                            "event_date"
                        ].nunique()
                    ),

                "selected_rule":
                    selected_rule,

                "selected_rule_books":
                    len(
                        selected_books
                    ),

                "selected_rule_dates":
                    selected_books[
                        "event_date"
                    ].nunique(),

                "selected_rule_settled_dates":
                    int(
                        selected_ledger[
                            "target_available"
                        ].sum()
                    ),

                "selected_rule_pending_dates":
                    int(
                        (
                            ~selected_ledger[
                                "target_available"
                            ]
                        ).sum()
                    ),

                "selected_gp_trade_count_all_dates":
                    int(
                        selected_ledger[
                            "trade"
                        ].sum()
                    ),

                "selected_gp_settled_trade_count":
                    int(
                        selected_ledger.loc[
                            selected_ledger[
                                "target_available"
                            ],
                            "trade",
                        ].sum()
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def audit_checks(
    panel,
    policy,
    threshold_grid,
    ledgers,
    risk,
    stress,
    derivative_validation,
    cost,
):
    checks = []

    def add(
        name,
        passed,
        observed,
        expected,
        notes="",
    ):
        checks.append(
            {
                "check":
                    name,

                "passed":
                    bool(
                        passed
                    ),

                "observed":
                    observed,

                "expected":
                    expected,

                "notes":
                    notes,
            }
        )

    add(
        "input_books_are_11_events",
        (
            panel.groupby(
                [
                    "event_date",
                    "decision_rule",
                ]
            )
            .size()
            .eq(
                11
            )
            .all()
        ),
        int(
            panel.groupby(
                [
                    "event_date",
                    "decision_rule",
                ]
            )
            .size()
            .eq(
                11
            )
            .all()
        ),
        1,
    )

    add(
        "selection_uses_selected_gp",
        (
            policy[
                "selection_probability_source"
            ]
            == "selected_gp"
        ),
        policy[
            "selection_probability_source"
        ],
        "selected_gp",
    )

    add(
        "pool_not_used_for_trading",
        (
            policy[
                "pool_used_for_trading"
            ]
            is False
        ),
        policy[
            "pool_used_for_trading"
        ],
        False,
    )

    add(
        "external_not_used_for_policy_selection",
        (
            policy[
                "external_data_used_for_selection"
            ]
            is False
        ),
        policy[
            "external_data_used_for_selection"
        ],
        False,
    )

    add(
        "reference_cost_is_one_cent",
        math.isclose(
            policy[
                "reference_cost_per_share"
            ],
            0.01,
            abs_tol=1e-15,
        ),
        policy[
            "reference_cost_per_share"
        ],
        0.01,
    )

    add(
        "selected_threshold_on_grid",
        any(
            math.isclose(
                policy[
                    "selected_threshold"
                ],
                h,
                abs_tol=1e-14,
            )
            for h
            in THRESHOLD_GRID
        ),
        policy[
            "selected_threshold"
        ],
        "0.00,...,0.25",
    )

    selected_grid = threshold_grid[
        (
            threshold_grid[
                "decision_rule"
            ]
            == policy[
                "selected_rule"
            ]
        )
        & np.isclose(
            threshold_grid[
                "threshold"
            ],
            policy[
                "selected_threshold"
            ],
            atol=1e-14,
        )
    ]

    add(
        "selected_threshold_minimum_trades",
        (
            not selected_grid.empty
            and int(
                selected_grid.iloc[
                    0
                ][
                    "trade_count"
                ]
            )
            >= MIN_DEVELOPMENT_TRADES
        ),
        (
            int(
                selected_grid.iloc[
                    0
                ][
                    "trade_count"
                ]
            )
            if not selected_grid.empty
            else -1
        ),
        f">={MIN_DEVELOPMENT_TRADES}",
    )

    add(
        "one_ledger_row_per_date_method_period",
        (
            not ledgers[
                [
                    "event_date",
                    "empirical_period",
                    "probability_source",
                ]
            ]
            .duplicated()
            .any()
        ),
        int(
            ledgers[
                [
                    "event_date",
                    "empirical_period",
                    "probability_source",
                ]
            ]
            .duplicated()
            .sum()
        ),
        0,
    )

    pnl_identity = True

    settled_trade = ledgers[
        ledgers[
            "target_available"
        ]
        & ledgers[
            "trade"
        ]
    ]

    if len(
        settled_trade
    ):
        pnl_identity = bool(
            np.allclose(
                settled_trade[
                    "net_pnl"
                ],
                (
                    settled_trade[
                        "Y"
                    ]
                    - settled_trade[
                        "market_raw_yes"
                    ]
                    - REFERENCE_COST
                ),
                atol=1e-12,
            )
        )

    add(
        "trade_pnl_identity",
        pnl_identity,
        int(
            pnl_identity
        ),
        1,
    )

    external = ledgers[
        ledgers[
            "empirical_period"
        ]
        == EXTERNAL_PERIOD
    ]

    external_sets = [
        set(
            external.loc[
                external[
                    "probability_source"
                ]
                == source,
                "event_date",
            ]
        )
        for source
        in METHOD_ORDER
    ]

    same_support = (
        external_sets[
            0
        ]
        == external_sets[
            1
        ]
        == external_sets[
            2
        ]
    )

    add(
        "raw_static_gp_external_support_identical",
        same_support,
        int(
            same_support
        ),
        1,
    )

    zero_stress = stress[
        np.isclose(
            stress[
                "mean_shift_c"
            ],
            0.0,
            atol=1e-14,
        )
    ]

    gp_external_risk = risk[
        (
            risk[
                "analysis_period"
            ]
            == EXTERNAL_PERIOD
        )
        & (
            risk[
                "probability_source"
            ]
            == "selected_gp"
        )
    ]

    zero_matches = (
        not zero_stress.empty
        and not gp_external_risk.empty
        and math.isclose(
            float(
                zero_stress.iloc[
                    0
                ][
                    "total_net_pnl"
                ]
            ),
            float(
                gp_external_risk.iloc[
                    0
                ][
                    "total_net_pnl"
                ]
            ),
            abs_tol=1e-10,
        )
    )

    add(
        "zero_mean_stress_matches_baseline_gp_pnl",
        zero_matches,
        (
            float(
                zero_stress.iloc[
                    0
                ][
                    "total_net_pnl"
                ]
            )
            if not zero_stress.empty
            else np.nan
        ),
        (
            float(
                gp_external_risk.iloc[
                    0
                ][
                    "total_net_pnl"
                ]
            )
            if not gp_external_risk.empty
            else np.nan
        ),
    )

    max_prob_error = float(
        derivative_validation[
            "probability_reconstruction_error"
        ]
        .abs()
        .max()
    )

    max_delta_error = float(
        derivative_validation[
            "delta_error_vs_finite_difference"
        ]
        .abs()
        .max()
    )

    add(
        "gp_probability_reconstruction",
        (
            max_prob_error
            < 1e-10
        ),
        max_prob_error,
        "<1e-10",
    )

    add(
        "analytic_delta_matches_finite_difference",
        (
            max_delta_error
            < 1e-7
        ),
        max_delta_error,
        "<1e-7",
    )

    baseline_cost = cost[
        np.isclose(
            cost[
                "cost_per_trade"
            ],
            REFERENCE_COST,
            atol=1e-14,
        )
    ]

    cost_matches = (
        not baseline_cost.empty
        and not gp_external_risk.empty
        and math.isclose(
            float(
                baseline_cost.iloc[
                    0
                ][
                    "total_net_pnl"
                ]
            ),
            float(
                gp_external_risk.iloc[
                    0
                ][
                    "total_net_pnl"
                ]
            ),
            abs_tol=1e-10,
        )
    )

    add(
        "one_cent_cost_sensitivity_matches_baseline",
        cost_matches,
        int(
            cost_matches
        ),
        1,
    )

    status = (
        "PASS"
        if all(
            x[
                "passed"
            ]
            for x
            in checks
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
    PROCESSED.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT.mkdir(
        parents=True,
        exist_ok=True,
    )

    panel = load_panel()

    # -------------------------------------------------------------------------
    # Step 38: exact trading panel
    # -------------------------------------------------------------------------

    print(
        "Step 38: certifying exact trading input..."
    )

    # -------------------------------------------------------------------------
    # Step 39: selected-GP model-minus-market candidates
    # -------------------------------------------------------------------------

    print(
        "Step 39: constructing model-minus-raw-market gap candidates..."
    )

    # -------------------------------------------------------------------------
    # Steps 40-42: threshold, one-SE, rule selection
    # -------------------------------------------------------------------------

    print(
        "Steps 40-42: March-June threshold/rule selection..."
    )

    (
        development_candidates,
        threshold_grid,
        rule_results,
        candidate_by_rule,
        policy,
    ) = development_selection(
        panel
    )

    development_candidates.to_csv(
        DEVELOPMENT_CANDIDATES,
        index=False,
    )

    threshold_grid.to_csv(
        THRESHOLD_GRID_OUTPUT,
        index=False,
        float_format="%.10f",
    )

    common_sensitivity = (
        common_rule_selection_sensitivity(
            candidate_by_rule
        )
    )

    common_sensitivity.to_csv(
        COMMON_RULE_SENSITIVITY,
        index=False,
        float_format="%.10f",
    )

    policy[
        "rule_level_selection_results"
    ] = rule_results[
        [
            "decision_rule",
            "development_dates",
            "h_best",
            "best_mean_daily_pnl",
            "se_at_h_best",
            "one_se_cutoff",
            "h_star",
            "h_star_mean_daily_pnl",
            "h_star_se",
            "h_star_conservative_score",
            "h_star_trade_count",
        ]
    ].to_dict(
        orient="records"
    )

    POLICY_JSON.write_text(
        json.dumps(
            policy,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(
        "Selected policy:",
        policy[
            "selected_rule"
        ],
        "threshold=",
        policy[
            "selected_threshold"
        ],
    )

    # -------------------------------------------------------------------------
    # Steps 43-46: fixed policy + attribution
    # -------------------------------------------------------------------------

    print(
        "Steps 43-46: freezing policy and building raw/static/GP attribution..."
    )

    ledgers = build_fixed_policy_ledgers(
        panel,
        policy,
    )

    ledgers.to_csv(
        ALL_LEDGERS,
        index=False,
        float_format="%.10f",
    )

    risk = build_risk_summary(
        ledgers
    )

    risk.to_csv(
        RISK_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    (
        attribution_panel,
        attribution_summary,
        decision_overlap,
    ) = attribution_objects(
        ledgers
    )

    attribution_panel.to_csv(
        ATTRIBUTION_PANEL,
        index=False,
        float_format="%.10f",
    )

    attribution_summary.to_csv(
        ATTRIBUTION_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    decision_overlap.to_csv(
        DECISION_OVERLAP,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Steps 47-48: risk-adjusted performance + bootstrap
    # -------------------------------------------------------------------------

    print(
        "Steps 47-48: risk metrics and date/block bootstrap..."
    )

    bootstrap = build_bootstrap_summary(
        ledgers
    )

    bootstrap.to_csv(
        BOOTSTRAP_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 49: cost sensitivity
    # -------------------------------------------------------------------------

    print(
        "Step 49: selected-GP cost sensitivity..."
    )

    gp_external_ledger = ledgers[
        (
            ledgers[
                "empirical_period"
            ]
            == EXTERNAL_PERIOD
        )
        & (
            ledgers[
                "probability_source"
            ]
            == "selected_gp"
        )
    ].copy()

    cost = cost_sensitivity(
        gp_external_ledger
    )

    cost.to_csv(
        COST_SENSITIVITY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Steps 50-52: local delta/gamma and decision margins
    # -------------------------------------------------------------------------

    print(
        "Steps 50-52: probability delta/gamma and boundary margins..."
    )

    (
        local_event_sensitivity,
        selected_sensitivity,
        derivative_validation,
    ) = derivative_panel(
        panel,
        policy,
        gp_external_ledger,
    )

    local_event_sensitivity.to_csv(
        LOCAL_EVENT_SENSITIVITY,
        index=False,
        compression="gzip",
    )

    selected_sensitivity.to_csv(
        SELECTED_DATE_SENSITIVITY,
        index=False,
        float_format="%.10f",
    )

    derivative_validation.to_csv(
        DERIVATIVE_VALIDATION,
        index=False,
        float_format="%.12f",
    )

    # -------------------------------------------------------------------------
    # Step 53: fixed-contract mean shocks
    # -------------------------------------------------------------------------

    print(
        "Step 53: fixed-contract predictive-mean shocks..."
    )

    fixed_shocks = fixed_contract_shocks(
        panel,
        policy,
        gp_external_ledger,
    )

    fixed_shocks.to_csv(
        FIXED_CONTRACT_SHOCKS,
        index=False,
        compression="gzip",
    )

    # -------------------------------------------------------------------------
    # Step 54: full-strategy shock + realised forecast-error/PnL
    # -------------------------------------------------------------------------

    print(
        "Step 54: full-strategy mean shocks and forecast-error/PnL diagnostics..."
    )

    stress = full_strategy_shocks(
        panel,
        policy,
        gp_external_ledger,
    )

    stress.to_csv(
        FULL_STRATEGY_SHOCKS,
        index=False,
        float_format="%.10f",
    )

    slopes = finite_portfolio_slopes(
        stress
    )

    slopes.to_csv(
        FINITE_SLOPES,
        index=False,
        float_format="%.10f",
    )

    (
        error_panel,
        error_bins,
        correlations,
    ) = forecast_error_diagnostics(
        selected_sensitivity
    )

    error_panel.to_csv(
        ERROR_PNL_PANEL,
        index=False,
        float_format="%.10f",
    )

    error_bins.to_csv(
        ERROR_BIN_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    correlations.to_csv(
        SPEARMAN_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 55: support, figures, audit
    # -------------------------------------------------------------------------

    print(
        "Step 55: final trading-stage certification..."
    )

    support = support_summary(
        panel,
        policy,
        ledgers,
    )

    support.to_csv(
        SUPPORT_SUMMARY,
        index=False,
    )

    make_figures(
        threshold_grid,
        policy,
        ledgers,
        stress,
        error_panel,
    )

    (
        checks,
        status,
    ) = audit_checks(
        panel,
        policy,
        threshold_grid,
        ledgers,
        risk,
        stress,
        derivative_validation,
        cost,
    )

    checks.to_csv(
        CHECKS_CSV,
        index=False,
    )

    external_risk = risk[
        risk[
            "analysis_period"
        ]
        == EXTERNAL_PERIOD
    ]

    def risk_row(
        source,
    ):
        row = external_risk[
            external_risk[
                "probability_source"
            ]
            == source
        ]

        if row.empty:
            return {}

        return row.iloc[
            0
        ].to_dict()

    gp_risk = risk_row(
        "selected_gp"
    )

    raw_risk = risk_row(
        "raw"
    )

    static_risk = risk_row(
        "static"
    )

    attr = dict(
        zip(
            attribution_summary[
                "quantity"
            ],
            attribution_summary[
                "value"
            ],
        )
    )

    pending = (
        gp_external_ledger.loc[
            ~gp_external_ledger[
                "target_available"
            ],
            "event_date",
        ]
        .dt.strftime(
            "%Y-%m-%d"
        )
        .tolist()
    )

    weather_kernel = ""

    if WEATHER_SELECTION.exists():
        weather_kernel = json.loads(
            WEATHER_SELECTION.read_text()
        ).get(
            "selected_kernel",
            "",
        )

    summary = {
        "status":
            status,

        "stage":
            "steps_38_55",

        "selected_weather_kernel":
            weather_kernel,

        "trading_probability_source":
            "selected_gp",

        "trading_market_probability":
            "raw event-level YES record",

        "convex_pool_used_for_trading":
            False,

        "development_start":
            "2026-03-16",

        "development_end":
            "2026-06-30",

        "external_start":
            "2026-07-01",

        "external_end":
            "2026-08-31",

        "selected_rule":
            policy[
                "selected_rule"
            ],

        "selected_threshold":
            policy[
                "selected_threshold"
            ],

        "reference_cost_per_trade":
            REFERENCE_COST,

        "minimum_development_trades":
            MIN_DEVELOPMENT_TRADES,

        "external_pending_target_dates":
            pending,

        "external_raw":
            raw_risk,

        "external_static":
            static_risk,

        "external_selected_gp":
            gp_risk,

        "external_static_minus_raw_net_pnl":
            attr.get(
                "static_minus_raw_external_net_pnl"
            ),

        "external_gp_minus_static_net_pnl":
            attr.get(
                "selected_gp_minus_static_external_net_pnl"
            ),

        "external_gp_minus_raw_net_pnl":
            attr.get(
                "selected_gp_minus_raw_external_net_pnl"
            ),

        "external_raw_to_gp_pnl_gap_closed_by_static":
            attr.get(
                "raw_to_gp_pnl_gap_closed_by_static"
            ),

        "bootstrap_reps":
            BOOTSTRAP_REPS,

        "moving_block_length":
            BLOCK_LENGTH,

        "shock_grid_min_c":
            float(
                SHOCK_GRID.min()
            ),

        "shock_grid_max_c":
            float(
                SHOCK_GRID.max()
            ),

        "stress_definition":
            (
                "additive shift to selected-GP fitted settlement-law "
                "mean; predictive scale, fitted parameters, market "
                "records, selected rule, threshold and reference cost fixed"
            ),

        "input_sha256":
            sha256_file(
                INPUT
            ),

        "fixed_policy_ledger_sha256":
            sha256_file(
                ALL_LEDGERS
            ),

        "selected_contract_sensitivity_sha256":
            sha256_file(
                SELECTED_DATE_SENSITIVITY
            ),
    }

    SUMMARY_JSON.write_text(
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
        "status=",
        status,
    )

    print(
        "selected_rule=",
        policy[
            "selected_rule"
        ],
    )

    print(
        "selected_threshold=",
        policy[
            "selected_threshold"
        ],
    )

    print(
        "external_settled_dates=",
        gp_risk.get(
            "eligible_settled_dates"
        ),
    )

    print(
        "external_gp_trades=",
        gp_risk.get(
            "trade_count"
        ),
    )

    print(
        "external_gp_net_pnl=",
        gp_risk.get(
            "total_net_pnl"
        ),
    )

    print(
        "external_gp_sharpe=",
        gp_risk.get(
            "settlement_date_sharpe"
        ),
    )

    print(
        "pending_external_dates=",
        pending,
    )

    if status != "PASS":
        failed = checks[
            ~checks[
                "passed"
            ]
        ]

        print(
            failed.to_string(
                index=False
            )
        )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
