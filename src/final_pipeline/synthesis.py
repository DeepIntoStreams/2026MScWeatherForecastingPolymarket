from __future__ import annotations

import hashlib
import json
import math
import sys

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# =============================================================================
# FROZEN INPUTS
# =============================================================================

WEATHER_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "weather_models_summary.json"
)

WEATHER_ATTRIBUTION = Path(
    "outputs/final_pipeline/weather/models/"
    "weather_model_attribution_summary.csv"
)

MARKET_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "market_stage_summary.json"
)

MARKET_TV = Path(
    "outputs/final_pipeline/market/"
    "total_variation_summary.csv"
)

MARKET_SCORES = Path(
    "outputs/final_pipeline/market/"
    "exact_support_score_summary.csv"
)

MARKET_BOOTSTRAP = Path(
    "outputs/final_pipeline/market/"
    "paired_score_bootstrap.csv"
)

POOL_SELECTION = Path(
    "outputs/final_pipeline/market/"
    "convex_pool_selection.json"
)

TRADING_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "trading_stage_summary.json"
)

TRADING_POLICY = Path(
    "outputs/final_pipeline/trading/"
    "selected_trading_policy.json"
)

TRADING_RISK = Path(
    "outputs/final_pipeline/trading/"
    "trading_risk_summary.csv"
)

TRADING_BOOTSTRAP = Path(
    "outputs/final_pipeline/trading/"
    "trading_bootstrap_summary.csv"
)

TRADING_LEDGERS = Path(
    "data/processed/final_pipeline/trading/"
    "fixed_policy_ledgers.csv"
)

COMMON_RULE = Path(
    "outputs/final_pipeline/trading/"
    "common_rule_selection_sensitivity.csv"
)

COST_SENSITIVITY = Path(
    "outputs/final_pipeline/trading/"
    "selected_gp_cost_sensitivity.csv"
)

STRESS = Path(
    "outputs/final_pipeline/trading/"
    "selected_gp_full_strategy_mean_shocks.csv"
)

FINITE_SLOPES = Path(
    "outputs/final_pipeline/trading/"
    "selected_gp_portfolio_finite_slopes.csv"
)

ERROR_BINS = Path(
    "outputs/final_pipeline/trading/"
    "forecast_error_pnl_bins.csv"
)

SPEARMAN = Path(
    "outputs/final_pipeline/trading/"
    "forecast_risk_spearman_summary.csv"
)

MASTER_CONFIG = Path(
    "config/final_empirical_config.json"
)

CORE_FILES = [
    WEATHER_SUMMARY,
    MARKET_SUMMARY,
    TRADING_SUMMARY,
    MARKET_TV,
    MARKET_SCORES,
    MARKET_BOOTSTRAP,
    POOL_SELECTION,
    TRADING_POLICY,
    TRADING_RISK,
    TRADING_BOOTSTRAP,
    TRADING_LEDGERS,
    COMMON_RULE,
    COST_SENSITIVITY,
    STRESS,
    FINITE_SLOPES,
    ERROR_BINS,
    SPEARMAN,
    MASTER_CONFIG,
]


# =============================================================================
# OUTPUTS
# =============================================================================

PROCESSED = Path(
    "data/processed/final_pipeline/synthesis"
)

OUTPUT = Path(
    "outputs/final_pipeline/synthesis"
)

AUDIT = Path(
    "outputs/final_pipeline/audit"
)

RULE_SUPPORT = OUTPUT / "rule_support_robustness.csv"

THRESHOLD_DIAGNOSTIC = (
    PROCESSED
    / "external_threshold_neighbourhood.csv"
)

MONTHLY_STABILITY = (
    PROCESSED
    / "external_monthly_method_performance.csv"
)

LEAVE_ONE_OUT = (
    PROCESSED
    / "external_gp_leave_one_trade_out.csv"
)

TOP_WINNER_REMOVAL = (
    OUTPUT
    / "external_gp_top_winner_removal.csv"
)

BOOTSTRAP_INTERPRETATION = (
    OUTPUT
    / "bootstrap_interpretation.csv"
)

COST_SUMMARY = (
    OUTPUT
    / "cost_robustness_summary.csv"
)

FORECAST_RISK_SYNTHESIS = (
    OUTPUT
    / "forecast_risk_synthesis.csv"
)

GENERALISATION = (
    OUTPUT
    / "development_external_stability.csv"
)

CROSS_STAGE = (
    OUTPUT
    / "cross_stage_attribution.csv"
)

RESULT_LEDGER = (
    OUTPUT
    / "final_result_ledger.csv"
)

EVIDENCE_REGISTER = (
    OUTPUT
    / "thesis_evidence_register.csv"
)

OUTPUT_MANIFEST = (
    OUTPUT
    / "thesis_output_manifest.csv"
)

PENDING_STATUS = (
    OUTPUT
    / "pending_target_status.json"
)

REPRO_MANIFEST = (
    OUTPUT
    / "reproducibility_manifest.csv"
)

SUMMARY_JSON = (
    AUDIT
    / "synthesis_stage_summary.json"
)

CHECKS_CSV = (
    AUDIT
    / "synthesis_stage_integrity_checks.csv"
)

THRESHOLD_FIGURE = (
    OUTPUT
    / "external_threshold_neighbourhood.png"
)

MONTHLY_FIGURE = (
    OUTPUT
    / "external_monthly_pnl.png"
)

CROSS_STAGE_FIGURE = (
    OUTPUT
    / "cross_stage_static_share.png"
)

HANDOFF_MD = Path(
    "docs/final_pipeline/"
    "thesis_evidence_handoff.md"
)

REFRESH_MD = Path(
    "docs/final_pipeline/"
    "aug31_refresh_protocol.md"
)


REFERENCE_COST = 0.01
SELECTED_SOURCE = "selected_gp"
EXTERNAL_PERIOD = "external_validation"
DEVELOPMENT_PERIOD = "market_development"

THRESHOLDS = np.round(
    np.arange(
        0.00,
        0.251,
        0.01,
    ),
    2,
)


# =============================================================================
# HELPERS
# =============================================================================


def read_json(
    path: Path,
):
    return json.loads(
        path.read_text()
    )


def sha256_file(
    path: Path,
):
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
    series: pd.Series,
):
    if series.dtype == bool:
        return series

    x = (
        series.astype(str)
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

    if x.isna().any():
        raise RuntimeError(
            "Boolean conversion failed."
        )

    return x.astype(
        bool
    )


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

    cumulative = np.r_[
        0.0,
        np.cumsum(
            x
        ),
    ]

    peak = np.maximum.accumulate(
        cumulative
    )

    return float(
        (
            peak
            - cumulative
        ).max()
    )


def isclose(
    a,
    b,
    atol=1e-10,
):
    return bool(
        math.isclose(
            float(
                a
            ),
            float(
                b
            ),
            abs_tol=atol,
            rel_tol=0.0,
        )
    )


def get_row(
    frame,
    **filters,
):
    x = frame.copy()

    for col, value in (
        filters.items()
    ):
        x = x[
            x[
                col
            ]
            .astype(str)
            == str(
                value
            )
        ]

    if len(
        x
    ) != 1:
        raise RuntimeError(
            "Expected exactly one row for "
            + repr(
                filters
            )
            + f"; found {len(x)}"
        )

    return x.iloc[
        0
    ]


def lookup_stress(
    stress,
    shift,
):
    x = stress[
        np.isclose(
            stress[
                "mean_shift_c"
            ],
            float(
                shift
            ),
            atol=1e-12,
        )
    ]

    if len(
        x
    ) != 1:
        raise RuntimeError(
            f"Missing stress shift {shift}."
        )

    return x.iloc[
        0
    ]


def add_ledger(
    rows,
    *,
    result_id,
    stage,
    period,
    metric,
    value,
    units,
    direction,
    source_file,
    note="",
):
    rows.append(
        {
            "result_id":
                result_id,

            "stage":
                stage,

            "period":
                period,

            "metric":
                metric,

            "value":
                value,

            "units":
                units,

            "direction":
                direction,

            "source_file":
                str(
                    source_file
                ),

            "note":
                note,
        }
    )


# =============================================================================
# STEP 56 — SUPPORT-COMPOSITION ROBUSTNESS
# =============================================================================


def build_rule_support_robustness(
    policy,
    common,
):
    primary_rule = policy[
        "selected_rule"
    ]

    primary_records = pd.DataFrame(
        policy[
            "rule_level_selection_results"
        ]
    )

    primary_best = primary_records.sort_values(
        [
            "h_star_conservative_score",
            "rule_order",
        ]
        if "rule_order" in primary_records.columns
        else [
            "h_star_conservative_score",
        ],
        ascending=[
            False,
            True,
        ]
        if "rule_order" in primary_records.columns
        else [
            False,
        ],
    )

    # The policy itself is authoritative if ordering metadata were omitted
    # from the JSON records.
    primary_row = get_row(
        primary_records,
        decision_rule=
            primary_rule,
    )

    common_sorted = common.sort_values(
        [
            "h_star_conservative_score",
        ],
        ascending=False,
    )

    common_best = common_sorted.iloc[
        0
    ]

    rows = [
        {
            "selection_basis":
                "prespecified_rule_specific_support",

            "selected_rule":
                primary_rule,

            "selected_threshold":
                float(
                    primary_row[
                        "h_star"
                    ]
                ),

            "conservative_score":
                float(
                    primary_row[
                        "h_star_conservative_score"
                    ]
                ),

            "development_dates":
                int(
                    primary_row[
                        "development_dates"
                    ]
                ),

            "changes_frozen_policy":
                False,

            "interpretation":
                (
                    "Primary frozen policy; each rule uses its "
                    "own complete development support."
                ),
        },
        {
            "selection_basis":
                "common_all_rule_dates_diagnostic",

            "selected_rule":
                str(
                    common_best[
                        "decision_rule"
                    ]
                ),

            "selected_threshold":
                float(
                    common_best[
                        "h_star"
                    ]
                ),

            "conservative_score":
                float(
                    common_best[
                        "h_star_conservative_score"
                    ]
                ),

            "development_dates":
                int(
                    common_best[
                        "development_dates"
                    ]
                ),

            "changes_frozen_policy":
                False,

            "interpretation":
                (
                    "Non-selection robustness diagnostic on the "
                    "intersection of dates supporting all four rules."
                ),
        },
    ]

    result = pd.DataFrame(
        rows
    )

    result[
        "rule_selection_support_sensitive"
    ] = (
        result[
            "selected_rule"
        ]
        .nunique()
        > 1
    )

    return result


# =============================================================================
# STEP 57 — EXTERNAL THRESHOLD NEIGHBOURHOOD
# =============================================================================


def external_threshold_diagnostic(
    ledgers,
    selected_threshold,
):
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
            == SELECTED_SOURCE
        )
    ].copy()

    x[
        "target_available"
    ] = as_bool(
        x[
            "target_available"
        ]
    )

    settled = x[
        x[
            "target_available"
        ]
    ].sort_values(
        "event_date"
    )

    rows = []

    for h in THRESHOLDS:
        trade = (
            settled[
                "probability_gap"
            ]
            >= (
                h
                - 1e-12
            )
        )

        pnl = np.where(
            trade,
            (
                settled[
                    "Y"
                ]
                - settled[
                    "market_raw_yes"
                ]
                - REFERENCE_COST
            ),
            0.0,
        )

        rows.append(
            {
                "threshold":
                    float(
                        h
                    ),

                "settled_dates":
                    len(
                        settled
                    ),

                "trade_count":
                    int(
                        trade.sum()
                    ),

                "trade_rate":
                    float(
                        trade.mean()
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

                "is_frozen_selected_threshold":
                    isclose(
                        h,
                        selected_threshold,
                    ),

                "within_0_05_of_selected":
                    (
                        abs(
                            float(
                                h
                            )
                            - float(
                                selected_threshold
                            )
                        )
                        <= 0.0500001
                    ),

                "used_for_selection":
                    False,
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 58 — MONTHLY EXTERNAL STABILITY
# =============================================================================


def external_monthly_stability(
    ledgers,
):
    x = ledgers[
        ledgers[
            "empirical_period"
        ]
        == EXTERNAL_PERIOD
    ].copy()

    x[
        "target_available"
    ] = as_bool(
        x[
            "target_available"
        ]
    )

    x = x[
        x[
            "target_available"
        ]
    ]

    x[
        "event_date"
    ] = pd.to_datetime(
        x[
            "event_date"
        ]
    )

    x[
        "month"
    ] = x[
        "event_date"
    ].dt.strftime(
        "%Y-%m"
    )

    rows = []

    for (
        source,
        month,
    ), group in x.groupby(
        [
            "probability_source",
            "month",
        ]
    ):
        group = group.sort_values(
            "event_date"
        )

        pnl = group[
            "net_pnl"
        ].to_numpy(
            dtype=float
        )

        rows.append(
            {
                "probability_source":
                    source,

                "month":
                    month,

                "settled_dates":
                    len(
                        group
                    ),

                "trade_count":
                    int(
                        as_bool(
                            group[
                                "trade"
                            ]
                        ).sum()
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
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 59 — TRADE-CONCENTRATION ROBUSTNESS
# =============================================================================


def concentration_diagnostics(
    ledgers,
):
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
            == SELECTED_SOURCE
        )
    ].copy()

    x[
        "target_available"
    ] = as_bool(
        x[
            "target_available"
        ]
    )

    x[
        "trade"
    ] = as_bool(
        x[
            "trade"
        ]
    )

    settled = x[
        x[
            "target_available"
        ]
    ].sort_values(
        "event_date"
    )

    trades = settled[
        settled[
            "trade"
        ]
    ].copy()

    baseline = float(
        settled[
            "net_pnl"
        ].sum()
    )

    loo_rows = []

    for _, row in trades.iterrows():
        remaining = (
            baseline
            - float(
                row[
                    "net_pnl"
                ]
            )
        )

        loo_rows.append(
            {
                "removed_event_date":
                    row[
                        "event_date"
                    ],

                "removed_market_id":
                    row[
                        "market_id"
                    ],

                "removed_trade_pnl":
                    float(
                        row[
                            "net_pnl"
                        ]
                    ),

                "baseline_total_net_pnl":
                    baseline,

                "remaining_total_net_pnl":
                    remaining,

                "remaining_positive":
                    (
                        remaining
                        > 0
                    ),
            }
        )

    loo = pd.DataFrame(
        loo_rows
    ).sort_values(
        "remaining_total_net_pnl"
    )

    positive = trades[
        trades[
            "net_pnl"
        ]
        > 0
    ].sort_values(
        "net_pnl",
        ascending=False,
    )

    top_rows = [
        {
            "largest_positive_trades_removed":
                0,

            "removed_positive_pnl":
                0.0,

            "remaining_total_net_pnl":
                baseline,

            "remaining_share_of_baseline":
                1.0,
        }
    ]

    removed = 0.0

    for k in range(
        1,
        min(
            3,
            len(
                positive
            ),
        )
        + 1,
    ):
        removed += float(
            positive.iloc[
                k - 1
            ][
                "net_pnl"
            ]
        )

        remaining = (
            baseline
            - removed
        )

        top_rows.append(
            {
                "largest_positive_trades_removed":
                    k,

                "removed_positive_pnl":
                    removed,

                "remaining_total_net_pnl":
                    remaining,

                "remaining_share_of_baseline":
                    (
                        remaining
                        / baseline
                        if abs(
                            baseline
                        )
                        > 1e-12
                        else np.nan
                    ),
            }
        )

    return (
        loo,
        pd.DataFrame(
            top_rows
        ),
    )


# =============================================================================
# STEP 60 — BOOTSTRAP RECONCILIATION
# =============================================================================


def classify_intervals(
    point,
    ordinary_lower,
    ordinary_upper,
    block_lower,
    block_upper,
):
    ordinary_positive = (
        ordinary_lower
        > 0
    )

    block_positive = (
        block_lower
        > 0
    )

    ordinary_negative = (
        ordinary_upper
        < 0
    )

    block_negative = (
        block_upper
        < 0
    )

    if (
        ordinary_positive
        and block_positive
    ):
        return (
            "positive_under_both",
            "Positive under ordinary and block bootstrap.",
        )

    if (
        ordinary_negative
        and block_negative
    ):
        return (
            "negative_under_both",
            "Negative under ordinary and block bootstrap.",
        )

    if (
        ordinary_positive
        != block_positive
        or ordinary_negative
        != block_negative
    ):
        return (
            "dependence_sensitive",
            (
                "Inferential conclusion changes with the "
                "resampling treatment of serial dependence."
            ),
        )

    return (
        "unresolved",
        (
            "Point estimate has a direction, but both "
            "interval treatments do not exclude zero."
        ),
    )


def bootstrap_reconciliation(
    bootstrap,
):
    x = bootstrap[
        bootstrap[
            "analysis_period"
        ]
        == EXTERNAL_PERIOD
    ].copy()

    keys = [
        (
            "method_level",
            "selected_gp",
            "",
        ),
        (
            "paired_pnl_difference",
            "static",
            "raw",
        ),
        (
            "paired_pnl_difference",
            "selected_gp",
            "static",
        ),
        (
            "paired_pnl_difference",
            "selected_gp",
            "raw",
        ),
    ]

    rows = []

    for (
        estimand,
        source_a,
        source_b,
    ) in keys:
        group = x[
            (
                x[
                    "estimand"
                ]
                == estimand
            )
            & (
                x[
                    "source_a"
                ]
                .fillna("")
                .astype(str)
                == source_a
            )
            & (
                x[
                    "source_b"
                ]
                .fillna("")
                .astype(str)
                == source_b
            )
        ]

        if len(
            group
        ) != 2:
            raise RuntimeError(
                "Bootstrap reconciliation missing pair: "
                + repr(
                    (
                        estimand,
                        source_a,
                        source_b,
                    )
                )
            )

        ordinary = get_row(
            group,
            bootstrap=
                "ordinary_date",
        )

        block = get_row(
            group,
            bootstrap=
                "circular_block7",
        )

        classification, wording = (
            classify_intervals(
                float(
                    ordinary[
                        "point_total_pnl"
                    ]
                ),
                float(
                    ordinary[
                        "total_pnl_lower_95"
                    ]
                ),
                float(
                    ordinary[
                        "total_pnl_upper_95"
                    ]
                ),
                float(
                    block[
                        "total_pnl_lower_95"
                    ]
                ),
                float(
                    block[
                        "total_pnl_upper_95"
                    ]
                ),
            )
        )

        rows.append(
            {
                "estimand":
                    estimand,

                "source_a":
                    source_a,

                "source_b":
                    source_b,

                "point_total_pnl":
                    float(
                        ordinary[
                            "point_total_pnl"
                        ]
                    ),

                "ordinary_lower_95":
                    float(
                        ordinary[
                            "total_pnl_lower_95"
                        ]
                    ),

                "ordinary_upper_95":
                    float(
                        ordinary[
                            "total_pnl_upper_95"
                        ]
                    ),

                "block7_lower_95":
                    float(
                        block[
                            "total_pnl_lower_95"
                        ]
                    ),

                "block7_upper_95":
                    float(
                        block[
                            "total_pnl_upper_95"
                        ]
                    ),

                "classification":
                    classification,

                "safe_interpretation":
                    wording,
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 61 — COST ROBUSTNESS
# =============================================================================


def build_cost_summary(
    cost,
    risk,
):
    baseline = cost[
        np.isclose(
            cost[
                "cost_per_trade"
            ],
            REFERENCE_COST,
            atol=1e-12,
        )
    ].iloc[
        0
    ]

    maximum = cost.sort_values(
        "cost_per_trade"
    ).iloc[
        -1
    ]

    gp = get_row(
        risk,
        analysis_period=
            EXTERNAL_PERIOD,
        probability_source=
            SELECTED_SOURCE,
    )

    break_even = float(
        gp[
            "break_even_cost_per_trade"
        ]
    )

    return pd.DataFrame(
        [
            {
                "baseline_reference_cost":
                    REFERENCE_COST,

                "baseline_total_net_pnl":
                    float(
                        baseline[
                            "total_net_pnl"
                        ]
                    ),

                "maximum_tested_cost":
                    float(
                        maximum[
                            "cost_per_trade"
                        ]
                    ),

                "pnl_at_maximum_tested_cost":
                    float(
                        maximum[
                            "total_net_pnl"
                        ]
                    ),

                "positive_at_maximum_tested_cost":
                    (
                        float(
                            maximum[
                                "total_net_pnl"
                            ]
                        )
                        > 0
                    ),

                "gross_break_even_cost_per_trade":
                    break_even,

                "maximum_tested_cost_fraction_of_break_even":
                    (
                        float(
                            maximum[
                                "cost_per_trade"
                            ]
                        )
                        / break_even
                        if break_even > 0
                        else np.nan
                    ),

                "interpretation":
                    (
                        "Reduced-form implementation-cost sensitivity; "
                        "not evidence about realised historical spreads "
                        "or executable capacity."
                    ),
            }
        ]
    )


# =============================================================================
# STEP 62 — FORECAST-RISK SYNTHESIS
# =============================================================================


def build_forecast_risk_synthesis(
    stress,
    slopes,
    error_bins,
    spearman,
):
    rows = []

    for shift in [
        -1.0,
        -0.5,
        -0.25,
        -0.10,
        0.0,
        0.10,
        0.25,
        0.5,
        1.0,
    ]:
        row = lookup_stress(
            stress,
            shift,
        )

        rows.append(
            {
                "diagnostic":
                    "full_strategy_mean_shift",

                "setting":
                    shift,

                "value":
                    float(
                        row[
                            "total_net_pnl"
                        ]
                    ),

                "secondary_value":
                    float(
                        row[
                            "activation_switch_fraction"
                        ]
                    ),

                "interpretation":
                    (
                        "Total net PnL; secondary value is "
                        "activation-switch fraction."
                    ),
            }
        )

    for _, row in slopes.iterrows():
        rows.append(
            {
                "diagnostic":
                    "finite_portfolio_slope",

                "setting":
                    float(
                        row[
                            "central_step_c"
                        ]
                    ),

                "value":
                    float(
                        row[
                            "finite_total_pnl_slope_per_c"
                        ]
                    ),

                "secondary_value":
                    np.nan,

                "interpretation":
                    (
                        "Central finite PnL slope; not a "
                        "classical global delta."
                    ),
            }
        )

    ordered_bins = error_bins.copy()

    for i, row in (
        ordered_bins.reset_index(
            drop=True
        )
        .iterrows()
    ):
        rows.append(
            {
                "diagnostic":
                    "absolute_gp_error_bin",

                "setting":
                    i + 1,

                "value":
                    float(
                        row[
                            "total_pnl"
                        ]
                    ),

                "secondary_value":
                    float(
                        row[
                            "mean_absolute_gp_error_c"
                        ]
                    ),

                "interpretation":
                    (
                        "Total PnL by ascending absolute GP "
                        "mean-error quartile."
                    ),
            }
        )

    gp_abs = spearman[
        (
            spearman[
                "sample"
            ]
            == "all_settled_dates"
        )
        & (
            spearman[
                "variable"
            ]
            == "absolute_gp_mean_error_c"
        )
    ]

    if len(
        gp_abs
    ) == 1:
        row = gp_abs.iloc[
            0
        ]

        rows.append(
            {
                "diagnostic":
                    "exploratory_spearman_abs_gp_error_vs_pnl",

                "setting":
                    int(
                        row[
                            "n"
                        ]
                    ),

                "value":
                    float(
                        row[
                            "spearman_rho"
                        ]
                    ),

                "secondary_value":
                    float(
                        row[
                            "nominal_p_value"
                        ]
                    ),

                "interpretation":
                    (
                        "Exploratory association only; nominal "
                        "p-value is not multiplicity-adjusted."
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 63 — DEVELOPMENT / EXTERNAL STABILITY
# =============================================================================


def build_generalisation_stability(
    tv,
    scores,
    risk,
):
    rows = []

    for source in [
        "static",
        "selected_gp",
    ]:
        dev = get_row(
            tv,
            analysis_period=
                DEVELOPMENT_PERIOD,
            source=
                source,
        )

        ext = get_row(
            tv,
            analysis_period=
                EXTERNAL_PERIOD,
            source=
                source,
        )

        rows.append(
            {
                "domain":
                    "market_probability_distance",

                "metric":
                    "raw_distance_closure",

                "source":
                    source,

                "development":
                    float(
                        dev[
                            "raw_distance_closure"
                        ]
                    ),

                "external":
                    float(
                        ext[
                            "raw_distance_closure"
                        ]
                    ),

                "external_minus_development":
                    (
                        float(
                            ext[
                                "raw_distance_closure"
                            ]
                        )
                        - float(
                            dev[
                                "raw_distance_closure"
                            ]
                        )
                    ),

                "direction":
                    "higher_better",
            }
        )

    for metric in [
        "categorical_log",
        "multiclass_brier",
    ]:
        for source in [
            "static",
            "selected_gp",
            "market",
            "pool",
        ]:
            dev = get_row(
                scores,
                analysis_period=
                    DEVELOPMENT_PERIOD,
                source=
                    source,
            )

            ext = get_row(
                scores,
                analysis_period=
                    EXTERNAL_PERIOD,
                source=
                    source,
            )

            rows.append(
                {
                    "domain":
                        "proper_scores",

                    "metric":
                        metric,

                    "source":
                        source,

                    "development":
                        float(
                            dev[
                                metric
                            ]
                        ),

                    "external":
                        float(
                            ext[
                                metric
                            ]
                        ),

                    "external_minus_development":
                        (
                            float(
                                ext[
                                    metric
                                ]
                            )
                            - float(
                                dev[
                                    metric
                                ]
                            )
                        ),

                    "direction":
                        "lower_better",
                }
            )

    for metric in [
        "total_net_pnl",
        "mean_daily_net_pnl",
        "settlement_date_sharpe",
    ]:
        for source in [
            "raw",
            "static",
            "selected_gp",
        ]:
            dev = get_row(
                risk,
                analysis_period=
                    DEVELOPMENT_PERIOD,
                probability_source=
                    source,
            )

            ext = get_row(
                risk,
                analysis_period=
                    EXTERNAL_PERIOD,
                probability_source=
                    source,
            )

            rows.append(
                {
                    "domain":
                        "trading",

                    "metric":
                        metric,

                    "source":
                        source,

                    "development":
                        float(
                            dev[
                                metric
                            ]
                        ),

                    "external":
                        float(
                            ext[
                                metric
                            ]
                        ),

                    "external_minus_development":
                        (
                            float(
                                ext[
                                    metric
                                ]
                            )
                            - float(
                                dev[
                                    metric
                                ]
                            )
                        ),

                    "direction":
                        "higher_better",
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 64 — CROSS-STAGE ATTRIBUTION
# =============================================================================


def improvement_share(
    raw,
    static,
    gp,
    *,
    direction,
):
    if direction == "lower_better":
        denominator = (
            raw
            - gp
        )

        numerator = (
            raw
            - static
        )

    elif direction == "higher_better":
        denominator = (
            gp
            - raw
        )

        numerator = (
            static
            - raw
        )

    else:
        raise ValueError(
            direction
        )

    if abs(
        denominator
    ) < 1e-12:
        return np.nan

    return float(
        numerator
        / denominator
    )


def build_cross_stage_attribution(
    weather_summary,
    tv,
    risk,
):
    crps = weather_summary[
        "mean_date_crps_c"
    ]

    weather_raw = float(
        crps[
            "raw"
        ]
    )

    weather_static = float(
        crps[
            "static"
        ]
    )

    weather_gp = float(
        crps[
            weather_summary[
                "selected_kernel"
            ]
        ]
    )

    tv_raw = float(
        get_row(
            tv,
            analysis_period=
                EXTERNAL_PERIOD,
            source=
                "raw",
        )[
            "date_balanced_tv"
        ]
    )

    tv_static = float(
        get_row(
            tv,
            analysis_period=
                EXTERNAL_PERIOD,
            source=
                "static",
        )[
            "date_balanced_tv"
        ]
    )

    tv_gp = float(
        get_row(
            tv,
            analysis_period=
                EXTERNAL_PERIOD,
            source=
                "selected_gp",
        )[
            "date_balanced_tv"
        ]
    )

    pnl_raw = float(
        get_row(
            risk,
            analysis_period=
                EXTERNAL_PERIOD,
            probability_source=
                "raw",
        )[
            "total_net_pnl"
        ]
    )

    pnl_static = float(
        get_row(
            risk,
            analysis_period=
                EXTERNAL_PERIOD,
            probability_source=
                "static",
        )[
            "total_net_pnl"
        ]
    )

    pnl_gp = float(
        get_row(
            risk,
            analysis_period=
                EXTERNAL_PERIOD,
            probability_source=
                "selected_gp",
        )[
            "total_net_pnl"
        ]
    )

    rows = [
        {
            "domain":
                "weather_continuous_crps",

            "period":
                "weather_history_chronological_validation",

            "raw":
                weather_raw,

            "static":
                weather_static,

            "selected_gp":
                weather_gp,

            "direction":
                "lower_better",

            "static_share_of_raw_to_gp_improvement":
                improvement_share(
                    weather_raw,
                    weather_static,
                    weather_gp,
                    direction=
                        "lower_better",
                ),
        },
        {
            "domain":
                "weather_market_total_variation",

            "period":
                EXTERNAL_PERIOD,

            "raw":
                tv_raw,

            "static":
                tv_static,

            "selected_gp":
                tv_gp,

            "direction":
                "lower_better",

            "static_share_of_raw_to_gp_improvement":
                improvement_share(
                    tv_raw,
                    tv_static,
                    tv_gp,
                    direction=
                        "lower_better",
                ),
        },
        {
            "domain":
                "fixed_policy_net_pnl",

            "period":
                EXTERNAL_PERIOD,

            "raw":
                pnl_raw,

            "static":
                pnl_static,

            "selected_gp":
                pnl_gp,

            "direction":
                "higher_better",

            "static_share_of_raw_to_gp_improvement":
                improvement_share(
                    pnl_raw,
                    pnl_static,
                    pnl_gp,
                    direction=
                        "higher_better",
                ),
        },
    ]

    x = pd.DataFrame(
        rows
    )

    x[
        "static_captures_at_least_90pct"
    ] = (
        x[
            "static_share_of_raw_to_gp_improvement"
        ]
        >= 0.90
    )

    x[
        "interpretation"
    ] = np.where(
        x[
            "static_share_of_raw_to_gp_improvement"
        ]
        > 1.0,
        (
            "Static correction slightly exceeds the selected GP "
            "on this metric."
        ),
        (
            "Static correction captures most of the raw-to-GP "
            "improvement."
        ),
    )

    return x


# =============================================================================
# STEPS 65–66 — RESULT LEDGER + EVIDENCE REGISTER
# =============================================================================


def build_result_ledger(
    weather_summary,
    market_summary,
    pool,
    tv,
    scores,
    market_boot,
    policy,
    risk,
    trading_boot,
    rule_support,
    threshold_diag,
    monthly,
    top_removal,
    cost_summary,
    risk_synthesis,
):
    rows = []

    crps = weather_summary[
        "mean_date_crps_c"
    ]

    add_ledger(
        rows,
        result_id="W01",
        stage="weather",
        period="historical_chronological_validation",
        metric="raw_mean_date_crps",
        value=float(
            crps[
                "raw"
            ]
        ),
        units="degC",
        direction="lower_better",
        source_file=WEATHER_SUMMARY,
    )

    add_ledger(
        rows,
        result_id="W02",
        stage="weather",
        period="historical_chronological_validation",
        metric="static_mean_date_crps",
        value=float(
            crps[
                "static"
            ]
        ),
        units="degC",
        direction="lower_better",
        source_file=WEATHER_SUMMARY,
    )

    selected_kernel = weather_summary[
        "selected_kernel"
    ]

    add_ledger(
        rows,
        result_id="W03",
        stage="weather",
        period="historical_chronological_validation",
        metric="selected_gp_mean_date_crps",
        value=float(
            crps[
                selected_kernel
            ]
        ),
        units="degC",
        direction="lower_better",
        source_file=WEATHER_SUMMARY,
        note=
            f"Selected kernel={selected_kernel}",
    )

    add_ledger(
        rows,
        result_id="W04",
        stage="weather",
        period="historical_chronological_validation",
        metric="static_share_raw_to_gp_crps_improvement",
        value=float(
            weather_summary[
                "attribution_shares"
            ][
                "raw_static_share_of_raw_to_selected"
            ]
        ),
        units="share",
        direction="higher_better",
        source_file=WEATHER_SUMMARY,
    )

    add_ledger(
        rows,
        result_id="M01",
        stage="market",
        period="march_august",
        metric="certified_market_dates",
        value=float(
            market_summary[
                "certified_market_dates"
            ]
        ),
        units="dates",
        direction="descriptive",
        source_file=MARKET_SUMMARY,
    )

    add_ledger(
        rows,
        result_id="M02",
        stage="market",
        period="march_august",
        metric="exact_common_dates",
        value=float(
            market_summary[
                "exact_common_dates"
            ]
        ),
        units="dates",
        direction="descriptive",
        source_file=MARKET_SUMMARY,
    )

    add_ledger(
        rows,
        result_id="M03",
        stage="market",
        period="development",
        metric="convex_pool_gp_weight",
        value=float(
            pool[
                "weight_gp"
            ]
        ),
        units="weight",
        direction="descriptive",
        source_file=POOL_SELECTION,
        note=
            "Selected on March-June categorical log loss only.",
    )

    for rid, source in [
        (
            "M04",
            "raw",
        ),
        (
            "M05",
            "static",
        ),
        (
            "M06",
            "selected_gp",
        ),
    ]:
        row = get_row(
            tv,
            analysis_period=
                EXTERNAL_PERIOD,
            source=
                source,
        )

        add_ledger(
            rows,
            result_id=rid,
            stage="market",
            period="external",
            metric=
                f"{source}_date_balanced_total_variation",
            value=float(
                row[
                    "date_balanced_tv"
                ]
            ),
            units="probability",
            direction="lower_better",
            source_file=MARKET_TV,
        )

    for rid, source in [
        (
            "M07",
            "static",
        ),
        (
            "M08",
            "selected_gp",
        ),
        (
            "M09",
            "market",
        ),
        (
            "M10",
            "pool",
        ),
    ]:
        row = get_row(
            scores,
            analysis_period=
                EXTERNAL_PERIOD,
            source=
                source,
        )

        add_ledger(
            rows,
            result_id=rid,
            stage="market",
            period="external",
            metric=
                f"{source}_categorical_log",
            value=float(
                row[
                    "categorical_log"
                ]
            ),
            units="loss",
            direction="lower_better",
            source_file=MARKET_SCORES,
        )

    pool_market = market_boot[
        (
            market_boot[
                "analysis_period"
            ]
            == EXTERNAL_PERIOD
        )
        & (
            market_boot[
                "metric"
            ]
            == "categorical_log"
        )
        & (
            market_boot[
                "source_a"
            ]
            == "pool"
        )
        & (
            market_boot[
                "source_b"
            ]
            == "market"
        )
    ]

    if len(
        pool_market
    ) == 1:
        pm = pool_market.iloc[
            0
        ]

        add_ledger(
            rows,
            result_id="M11",
            stage="market",
            period="external",
            metric=
                "pool_minus_market_categorical_log",
            value=float(
                pm[
                    "mean_a_minus_b"
                ]
            ),
            units="loss_difference",
            direction="lower_better",
            source_file=MARKET_BOOTSTRAP,
            note=(
                "Block7 95% interval "
                f"[{float(pm['block7_lower_95']):.6f},"
                f" {float(pm['block7_upper_95']):.6f}]"
            ),
        )

    add_ledger(
        rows,
        result_id="T01",
        stage="trading",
        period="development",
        metric="selected_rule",
        value=np.nan,
        units="category",
        direction="descriptive",
        source_file=TRADING_POLICY,
        note=str(
            policy[
                "selected_rule"
            ]
        ),
    )

    add_ledger(
        rows,
        result_id="T02",
        stage="trading",
        period="development",
        metric="selected_threshold",
        value=float(
            policy[
                "selected_threshold"
            ]
        ),
        units="probability",
        direction="descriptive",
        source_file=TRADING_POLICY,
    )

    ext_risk = {}

    for source in [
        "raw",
        "static",
        "selected_gp",
    ]:
        ext_risk[
            source
        ] = get_row(
            risk,
            analysis_period=
                EXTERNAL_PERIOD,
            probability_source=
                source,
        )

    for rid, source in [
        (
            "T03",
            "raw",
        ),
        (
            "T04",
            "static",
        ),
        (
            "T05",
            "selected_gp",
        ),
    ]:
        add_ledger(
            rows,
            result_id=rid,
            stage="trading",
            period="external",
            metric=
                f"{source}_total_net_pnl",
            value=float(
                ext_risk[
                    source
                ][
                    "total_net_pnl"
                ]
            ),
            units="pnl_per_one_share_policy",
            direction="higher_better",
            source_file=TRADING_RISK,
        )

    add_ledger(
        rows,
        result_id="T06",
        stage="trading",
        period="external",
        metric="selected_gp_trade_count",
        value=float(
            ext_risk[
                "selected_gp"
            ][
                "trade_count"
            ]
        ),
        units="trades",
        direction="descriptive",
        source_file=TRADING_RISK,
    )

    add_ledger(
        rows,
        result_id="T07",
        stage="trading",
        period="external",
        metric="selected_gp_settlement_date_sharpe",
        value=float(
            ext_risk[
                "selected_gp"
            ][
                "settlement_date_sharpe"
            ]
        ),
        units="nonannualised_ratio",
        direction="higher_better",
        source_file=TRADING_RISK,
    )

    add_ledger(
        rows,
        result_id="T08",
        stage="trading",
        period="external",
        metric="selected_gp_maximum_drawdown",
        value=float(
            ext_risk[
                "selected_gp"
            ][
                "maximum_drawdown"
            ]
        ),
        units="pnl",
        direction="lower_better",
        source_file=TRADING_RISK,
    )

    add_ledger(
        rows,
        result_id="T09",
        stage="trading",
        period="external",
        metric="static_share_raw_to_gp_pnl_improvement",
        value=(
            (
                float(
                    ext_risk[
                        "static"
                    ][
                        "total_net_pnl"
                    ]
                )
                - float(
                    ext_risk[
                        "raw"
                    ][
                        "total_net_pnl"
                    ]
                )
            )
            /
            (
                float(
                    ext_risk[
                        "selected_gp"
                    ][
                        "total_net_pnl"
                    ]
                )
                - float(
                    ext_risk[
                        "raw"
                    ][
                        "total_net_pnl"
                    ]
                )
            )
        ),
        units="share",
        direction="higher_better",
        source_file=TRADING_RISK,
    )

    gp_boot = trading_boot[
        (
            trading_boot[
                "analysis_period"
            ]
            == EXTERNAL_PERIOD
        )
        & (
            trading_boot[
                "estimand"
            ]
            == "method_level"
        )
        & (
            trading_boot[
                "source_a"
            ]
            == "selected_gp"
        )
    ]

    for rid, bootstrap_name in [
        (
            "T10",
            "ordinary_date",
        ),
        (
            "T11",
            "circular_block7",
        ),
    ]:
        row = get_row(
            gp_boot,
            bootstrap=
                bootstrap_name,
        )

        add_ledger(
            rows,
            result_id=rid,
            stage="trading",
            period="external",
            metric=
                f"selected_gp_total_pnl_{bootstrap_name}_lower95",
            value=float(
                row[
                    "total_pnl_lower_95"
                ]
            ),
            units="pnl",
            direction="diagnostic",
            source_file=TRADING_BOOTSTRAP,
            note=(
                f"Upper95={float(row['total_pnl_upper_95']):.6f}"
            ),
        )

    add_ledger(
        rows,
        result_id="T12",
        stage="trading",
        period="external",
        metric="gross_break_even_cost_per_trade",
        value=float(
            cost_summary.iloc[
                0
            ][
                "gross_break_even_cost_per_trade"
            ]
        ),
        units="probability_price",
        direction="descriptive",
        source_file=COST_SUMMARY,
        note=
            "Reduced-form price-proxy experiment.",
    )

    common_row = rule_support[
        rule_support[
            "selection_basis"
        ]
        == "common_all_rule_dates_diagnostic"
    ].iloc[
        0
    ]

    add_ledger(
        rows,
        result_id="R01",
        stage="robustness",
        period="development",
        metric="common_support_best_rule",
        value=np.nan,
        units="category",
        direction="diagnostic",
        source_file=RULE_SUPPORT,
        note=str(
            common_row[
                "selected_rule"
            ]
        ),
    )

    neighbourhood = threshold_diag[
        threshold_diag[
            "within_0_05_of_selected"
        ]
    ]

    add_ledger(
        rows,
        result_id="R02",
        stage="robustness",
        period="external",
        metric=
            "threshold_plusminus_005_min_total_net_pnl",
        value=float(
            neighbourhood[
                "total_net_pnl"
            ].min()
        ),
        units="pnl",
        direction="diagnostic",
        source_file=THRESHOLD_DIAGNOSTIC,
    )

    add_ledger(
        rows,
        result_id="R03",
        stage="robustness",
        period="external",
        metric=
            "threshold_plusminus_005_max_total_net_pnl",
        value=float(
            neighbourhood[
                "total_net_pnl"
            ].max()
        ),
        units="pnl",
        direction="diagnostic",
        source_file=THRESHOLD_DIAGNOSTIC,
    )

    for month in sorted(
        monthly[
            "month"
        ].unique()
    ):
        row = get_row(
            monthly,
            probability_source=
                SELECTED_SOURCE,
            month=
                month,
        )

        add_ledger(
            rows,
            result_id=
                "R_MONTH_"
                + month.replace(
                    "-",
                    "_",
                ),
            stage="robustness",
            period=month,
            metric="selected_gp_monthly_net_pnl",
            value=float(
                row[
                    "total_net_pnl"
                ]
            ),
            units="pnl",
            direction="diagnostic",
            source_file=MONTHLY_STABILITY,
        )

    for _, row in (
        top_removal.iterrows()
    ):
        k = int(
            row[
                "largest_positive_trades_removed"
            ]
        )

        add_ledger(
            rows,
            result_id=
                f"R_TOP{k}",
            stage="robustness",
            period="external",
            metric=
                f"pnl_after_removing_top_{k}_positive_trades",
            value=float(
                row[
                    "remaining_total_net_pnl"
                ]
            ),
            units="pnl",
            direction="diagnostic",
            source_file=TOP_WINNER_REMOVAL,
        )

    abs_error = risk_synthesis[
        risk_synthesis[
            "diagnostic"
        ]
        == "exploratory_spearman_abs_gp_error_vs_pnl"
    ]

    if len(
        abs_error
    ) == 1:
        row = abs_error.iloc[
            0
        ]

        add_ledger(
            rows,
            result_id="R04",
            stage="forecast_risk",
            period="external",
            metric="spearman_abs_gp_error_vs_pnl",
            value=float(
                row[
                    "value"
                ]
            ),
            units="rho",
            direction="diagnostic",
            source_file=FORECAST_RISK_SYNTHESIS,
            note=(
                "Exploratory; nominal p="
                f"{float(row['secondary_value']):.6f}; "
                "not multiplicity-adjusted."
            ),
        )

    return pd.DataFrame(
        rows
    )


def build_evidence_register(
    result_ledger,
    bootstrap_interpretation,
    rule_support,
    cross_stage,
    top_removal,
    pending_dates,
):
    # Dynamic values.
    def value(
        result_id,
    ):
        x = result_ledger[
            result_ledger[
                "result_id"
            ]
            == result_id
        ]

        if len(
            x
        ) != 1:
            return np.nan

        return float(
            x.iloc[
                0
            ][
                "value"
            ]
        )

    weather_share = float(
        cross_stage[
            cross_stage[
                "domain"
            ]
            == "weather_continuous_crps"
        ].iloc[
            0
        ][
            "static_share_of_raw_to_gp_improvement"
        ]
    )

    tv_share = float(
        cross_stage[
            cross_stage[
                "domain"
            ]
            == "weather_market_total_variation"
        ].iloc[
            0
        ][
            "static_share_of_raw_to_gp_improvement"
        ]
    )

    pnl_share = float(
        cross_stage[
            cross_stage[
                "domain"
            ]
            == "fixed_policy_net_pnl"
        ].iloc[
            0
        ][
            "static_share_of_raw_to_gp_improvement"
        ]
    )

    primary = rule_support.iloc[
        0
    ]

    common = rule_support.iloc[
        1
    ]

    gp_boot = bootstrap_interpretation[
        (
            bootstrap_interpretation[
                "estimand"
            ]
            == "method_level"
        )
        & (
            bootstrap_interpretation[
                "source_a"
            ]
            == "selected_gp"
        )
    ].iloc[
        0
    ]

    top1_remaining = float(
        top_removal[
            top_removal[
                "largest_positive_trades_removed"
            ]
            == 1
        ].iloc[
            0
        ][
            "remaining_total_net_pnl"
        ]
    )

    top2_remaining = float(
        top_removal[
            top_removal[
                "largest_positive_trades_removed"
            ]
            == 2
        ].iloc[
            0
        ][
            "remaining_total_net_pnl"
        ]
    )

    rows = [
        {
            "claim_id":
                "C01",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "Converting the deterministic forecast into a "
                    "probabilistic distribution explains most of the "
                    "weather-model gain; the static Gaussian accounts "
                    f"for {100*weather_share:.1f}% of the raw-to-selected-"
                    "GP CRPS improvement."
                ),

            "caveat":
                (
                    "This is an attribution ratio within the specified "
                    "weather models, not a causal decomposition."
                ),

            "evidence":
                "W01-W04",
        },
        {
            "claim_id":
                "C02",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "On July-August market books, the static correction "
                    "is at least as close to Polymarket as the selected "
                    f"GP in total variation; its raw-to-GP improvement "
                    f"share is {100*tv_share:.1f}%."
                ),

            "caveat":
                (
                    "Total variation measures probability-book distance, "
                    "not forecast correctness."
                ),

            "evidence":
                "M04-M06",
        },
        {
            "claim_id":
                "C03",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "The development-selected convex pool assigns "
                    "18.8% weight to the GP and 81.2% to Polymarket."
                ),

            "caveat":
                (
                    "The weight is a proper-score optimum within the "
                    "restricted convex-pool family and is not an "
                    "information-share decomposition."
                ),

            "evidence":
                "M03",
        },
        {
            "claim_id":
                "C04",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "The convex pool has the lowest external categorical "
                    "log-loss point estimate, but its advantage over "
                    "Polymarket is not statistically resolved."
                ),

            "caveat":
                (
                    "Do not claim that the pool significantly beats "
                    "Polymarket."
                ),

            "evidence":
                "M07-M11",
        },
        {
            "claim_id":
                "C05",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "The frozen trading policy uses the 24-hour decision "
                    "rule and a 0.15 GP-minus-raw-market probability-gap "
                    "threshold selected using March-June only."
                ),

            "caveat":
                (
                    "Rule choice is support-sensitive in the common-date "
                    "diagnostic and should not be described as an "
                    "intrinsically optimal forecast horizon."
                ),

            "evidence":
                "T01-T02,R01",
        },
        {
            "claim_id":
                "C06",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "Across the currently settled July-August sample, "
                    f"the frozen selected-GP policy earns {value('T05'):.3f} "
                    "net PnL from 12 trades with a non-annualised "
                    f"settlement-date Sharpe of {value('T07'):.3f}."
                ),

            "caveat":
                (
                    "Historical YES records are reduced-form entry proxies; "
                    "31 August remains pending in the current run."
                ),

            "evidence":
                "T05-T08",
        },
        {
            "claim_id":
                "C07",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "The simple static probabilistic correction accounts "
                    f"for {100*pnl_share:.1f}% of the raw-to-GP external "
                    "PnL improvement under the frozen policy."
                ),

            "caveat":
                (
                    "This is fixed-policy attribution: raw and static "
                    "signals are not separately re-optimised."
                ),

            "evidence":
                "T03-T05,T09",
        },
        {
            "claim_id":
                "C08",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "The external GP PnL point estimate is positive, but "
                    "inferential strength depends on temporal-resampling "
                    f"assumptions: {gp_boot['classification']}."
                ),

            "caveat":
                (
                    "Do not write a blanket claim of statistically "
                    "significant profitability."
                ),

            "evidence":
                "T10-T11",
        },
        {
            "claim_id":
                "C09",

            "recommended_location":
                "main_text",

            "priority":
                "core",

            "safe_claim":
                (
                    "Temperature perturbations transmit nonlinearly into "
                    "strategy PnL because smooth event-probability changes "
                    "interact with contract selection and the discrete "
                    "trading threshold."
                ),

            "caveat":
                (
                    "Finite portfolio slopes are stress sensitivities, "
                    "not a single global classical delta."
                ),

            "evidence":
                "forecast-risk stress and finite-slope outputs",
        },
        {
            "claim_id":
                "C10",

            "recommended_location":
                "main_text_or_discussion",

            "priority":
                "important_caveat",

            "safe_claim":
                (
                    f"The prespecified rule-specific-support procedure "
                    f"selects {primary['selected_rule']}, whereas the "
                    f"common-date diagnostic favours "
                    f"{common['selected_rule']}; rule selection therefore "
                    "shows some support-composition sensitivity."
                ),

            "caveat":
                (
                    "The common-support result is diagnostic and does not "
                    "replace the frozen policy."
                ),

            "evidence":
                "rule_support_robustness.csv",
        },
        {
            "claim_id":
                "C11",

            "recommended_location":
                "appendix",

            "priority":
                "robustness",

            "safe_claim":
                (
                    "External PnL remains "
                    f"{top1_remaining:.3f} after removing the largest "
                    "positive trade and "
                    f"{top2_remaining:.3f} after removing the two largest."
                ),

            "caveat":
                (
                    "The strategy still has only a small number of trades; "
                    "this diagnostic does not solve the small-sample issue."
                ),

            "evidence":
                "external_gp_top_winner_removal.csv",
        },
        {
            "claim_id":
                "C12",

            "recommended_location":
                "appendix",

            "priority":
                "robustness",

            "safe_claim":
                (
                    "Nearby external threshold performance is reported "
                    "descriptively without reselecting the policy."
                ),

            "caveat":
                (
                    "External thresholds must never be used to choose a "
                    "replacement for h=0.15."
                ),

            "evidence":
                "external_threshold_neighbourhood.csv",
        },
        {
            "claim_id":
                "C13",

            "recommended_location":
                "appendix",

            "priority":
                "robustness",

            "safe_claim":
                (
                    "July and August fixed-policy results are reported "
                    "separately to disclose calendar concentration."
                ),

            "caveat":
                (
                    "Monthly subsamples are descriptive and small."
                ),

            "evidence":
                "external_monthly_method_performance.csv",
        },
        {
            "claim_id":
                "C14",

            "recommended_location":
                "appendix_or_discussion",

            "priority":
                "diagnostic",

            "safe_claim":
                (
                    "Larger realised GP mean errors are associated with "
                    "worse date-level PnL in exploratory diagnostics."
                ),

            "caveat":
                (
                    "Spearman p-values are nominal and unadjusted; do not "
                    "present them as confirmatory multiple-testing evidence."
                ),

            "evidence":
                "forecast_error_pnl_bins.csv; forecast_risk_spearman_summary.csv",
        },
        {
            "claim_id":
                "C15",

            "recommended_location":
                "do_not_use_as_primary_claim",

            "priority":
                "avoid_overstatement",

            "safe_claim":
                (
                    "The sqrt(365)-scaled Sharpe may be shown only as an "
                    "explicitly descriptive scaling if retained at all."
                ),

            "caveat":
                (
                    "Use the non-annualised settlement-date Sharpe as the "
                    "principal volatility-adjusted statistic."
                ),

            "evidence":
                "trading_risk_summary.csv",
        },
        {
            "claim_id":
                "C16",

            "recommended_location":
                "do_not_use_as_primary_claim",

            "priority":
                "avoid_overstatement",

            "safe_claim":
                (
                    "Return-on-entry-cash is a reduced-form diagnostic, "
                    "not an executable portfolio return."
                ),

            "caveat":
                (
                    "No historical bid/ask, slippage, capacity or full "
                    "capital-accounting model is available."
                ),

            "evidence":
                "trading_risk_summary.csv",
        },
    ]

    if pending_dates:
        rows.append(
            {
                "claim_id":
                    "C17",

                "recommended_location":
                    "temporary_results_note",

                "priority":
                    "pending_refresh",

                "safe_claim":
                    (
                        "Current external realised-score and PnL results "
                        "exclude the unresolved 31 August settlement."
                    ),

                "caveat":
                    (
                        "Refresh once the official HKO Daily Extract target "
                        "is available; do not reselect any development-only "
                        "choice."
                    ),

                "evidence":
                    "pending_target_status.json",
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 67 — OUTPUT SHORTLIST
# =============================================================================


def build_output_manifest():
    rows = [
        (
            "main_text",
            "weather",
            "outputs/final_pipeline/weather/models/chronological_crps_attribution.png",
            "Weather-model attribution: deterministic to probabilistic correction.",
        ),
        (
            "appendix",
            "weather",
            "outputs/final_pipeline/weather/models/selected_gp_coverage.png",
            "Selected-GP calibration/coverage diagnostic.",
        ),
        (
            "appendix",
            "weather",
            "outputs/final_pipeline/weather/models/selected_gp_pit_histogram.png",
            "Selected-GP PIT diagnostic.",
        ),
        (
            "main_text",
            "market",
            "outputs/final_pipeline/market/total_variation_by_period.png",
            "Raw/static/GP probability-book distance from Polymarket.",
        ),
        (
            "main_text",
            "market",
            "outputs/final_pipeline/market/external_proper_scores.png",
            "External proper-score comparison.",
        ),
        (
            "appendix",
            "market",
            "outputs/final_pipeline/market/market_book_probability_sum.png",
            "Market-book normalisation diagnostic.",
        ),
        (
            "main_text",
            "trading",
            "outputs/final_pipeline/trading/external_cumulative_pnl_attribution.png",
            "Frozen raw/static/GP PnL attribution.",
        ),
        (
            "main_text",
            "trading",
            "outputs/final_pipeline/trading/external_predictive_mean_stress.png",
            "Nonlinear forecast-risk transmission.",
        ),
        (
            "appendix",
            "trading",
            "outputs/final_pipeline/trading/development_threshold_selection.png",
            "Development-only threshold/rule selection.",
        ),
        (
            "appendix",
            "trading",
            "outputs/final_pipeline/trading/external_forecast_error_vs_pnl.png",
            "Exploratory error-to-PnL diagnostic.",
        ),
        (
            "appendix",
            "synthesis",
            str(
                THRESHOLD_FIGURE
            ),
            "External threshold neighbourhood; diagnostic only.",
        ),
        (
            "appendix",
            "synthesis",
            str(
                MONTHLY_FIGURE
            ),
            "July/August calendar stability.",
        ),
        (
            "main_text_candidate",
            "synthesis",
            str(
                CROSS_STAGE_FIGURE
            ),
            "Share of raw-to-GP improvement captured by the static correction.",
        ),
    ]

    frame = pd.DataFrame(
        rows,
        columns=[
            "recommended_location",
            "stage",
            "path",
            "purpose",
        ],
    )

    frame[
        "exists"
    ] = frame[
        "path"
    ].map(
        lambda p:
            Path(
                p
            ).exists()
    )

    return frame


# =============================================================================
# STEP 68 — PENDING TARGET STATUS
# =============================================================================


def build_pending_status(
    weather_summary,
    market_summary,
    trading_summary,
    policy,
    pool,
):
    pending = list(
        trading_summary.get(
            "external_pending_target_dates",
            [],
        )
    )

    return {
        "status":
            (
                "PENDING_EXTERNAL_TARGET"
                if pending
                else "COMPLETE"
            ),

        "pending_dates":
            pending,

        "august_31_weather_target_pending":
            bool(
                weather_summary.get(
                    "august_31_target_pending",
                    False,
                )
            ),

        "market_score_ready_dates":
            market_summary.get(
                "score_ready_dates"
            ),

        "frozen_weather_kernel":
            weather_summary[
                "selected_kernel"
            ],

        "frozen_pool_weight_gp":
            pool[
                "weight_gp"
            ],

        "frozen_trading_rule":
            policy[
                "selected_rule"
            ],

        "frozen_trading_threshold":
            policy[
                "selected_threshold"
            ],

        "development_reselection_allowed_after_refresh":
            False,

        "external_metrics_allowed_to_update":
            True,

        "refresh_principle":
            (
                "When official HKO settlement becomes available, "
                "refresh the target and rerun downstream scoring/"
                "trading/synthesis only. Weather-kernel selection, "
                "March-June pool selection and March-June trading "
                "policy remain frozen."
            ),
    }


# =============================================================================
# STEP 69 — REPRODUCIBILITY MANIFEST
# =============================================================================


def build_reproducibility_manifest():
    rows = []

    roles = {
        str(
            WEATHER_SUMMARY
        ):
            "weather_stage_authoritative_summary",

        str(
            MARKET_SUMMARY
        ):
            "market_stage_authoritative_summary",

        str(
            TRADING_SUMMARY
        ):
            "trading_stage_authoritative_summary",

        str(
            MARKET_TV
        ):
            "market_total_variation",

        str(
            MARKET_SCORES
        ):
            "market_proper_scores",

        str(
            MARKET_BOOTSTRAP
        ):
            "market_paired_inference",

        str(
            POOL_SELECTION
        ):
            "development_pool_selection",

        str(
            TRADING_POLICY
        ):
            "development_trading_policy",

        str(
            TRADING_RISK
        ):
            "fixed_policy_risk_metrics",

        str(
            TRADING_BOOTSTRAP
        ):
            "trading_inference",

        str(
            TRADING_LEDGERS
        ):
            "fixed_policy_date_ledger",

        str(
            MASTER_CONFIG
        ):
            "master_empirical_contract",
    }

    additional = [
        Path(
            "src/final_pipeline/hko.py"
        ),
        Path(
            "src/final_pipeline/ecmwf.py"
        ),
        Path(
            "src/final_pipeline/weather_models.py"
        ),
        Path(
            "src/final_pipeline/market_books.py"
        ),
        Path(
            "src/final_pipeline/trading.py"
        ),
        Path(
            "tests/final_pipeline/test_weather_models.py"
        ),
        Path(
            "tests/final_pipeline/test_market_books.py"
        ),
        Path(
            "tests/final_pipeline/test_trading.py"
        ),
    ]

    paths = list(
        dict.fromkeys(
            CORE_FILES
            + additional
        )
    )

    for path in paths:
        exists = path.exists()

        rows.append(
            {
                "path":
                    str(
                        path
                    ),

                "exists":
                    exists,

                "bytes":
                    (
                        path.stat().st_size
                        if exists
                        else np.nan
                    ),

                "sha256":
                    (
                        sha256_file(
                            path
                        )
                        if exists
                        else ""
                    ),

                "role":
                    roles.get(
                        str(
                            path
                        ),
                        (
                            "pipeline_code_or_test"
                            if (
                                str(
                                    path
                                ).startswith(
                                    "src/"
                                )
                                or str(
                                    path
                                ).startswith(
                                    "tests/"
                                )
                            )
                            else "supporting_empirical_artifact"
                        ),
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# FIGURES
# =============================================================================


def make_figures(
    threshold_diag,
    monthly,
    cross_stage,
    selected_threshold,
):
    # Threshold neighbourhood.
    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    x = threshold_diag[
        threshold_diag[
            "within_0_05_of_selected"
        ]
    ]

    ax.plot(
        x[
            "threshold"
        ],
        x[
            "total_net_pnl"
        ],
        marker="o",
    )

    ax.axvline(
        selected_threshold,
        linestyle="--",
    )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.set_xlabel(
        "Diagnostic probability-gap threshold"
    )

    ax.set_ylabel(
        "External total net PnL"
    )

    ax.set_title(
        "External threshold neighbourhood around the frozen policy"
    )

    fig.tight_layout()

    fig.savefig(
        THRESHOLD_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    # Monthly method PnL.
    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    pivot = monthly.pivot(
        index="month",
        columns="probability_source",
        values="total_net_pnl",
    )

    pivot.plot(
        kind="bar",
        ax=ax,
    )

    ax.axhline(
        0.0,
        linewidth=1,
    )

    ax.set_xlabel(
        "External month"
    )

    ax.set_ylabel(
        "Total net PnL"
    )

    ax.set_title(
        "July–August fixed-policy stability"
    )

    fig.tight_layout()

    fig.savefig(
        MONTHLY_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )

    # Cross-stage static share.
    fig, ax = plt.subplots(
        figsize=(
            8,
            5,
        )
    )

    x = cross_stage.copy()

    labels = [
        "Weather CRPS",
        "Market TV",
        "Trading PnL",
    ]

    values = (
        100.0
        * x[
            "static_share_of_raw_to_gp_improvement"
        ].to_numpy(
            dtype=float
        )
    )

    ax.bar(
        labels,
        values,
    )

    ax.axhline(
        100.0,
        linestyle="--",
    )

    ax.set_ylabel(
        "Static share of raw-to-GP improvement (%)"
    )

    ax.set_title(
        "How much of the raw-to-GP gain is captured by the simple correction?"
    )

    fig.tight_layout()

    fig.savefig(
        CROSS_STAGE_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(
        fig
    )


# =============================================================================
# DOCUMENT HANDOFF
# =============================================================================


def write_handoff(
    weather_summary,
    market_summary,
    pool,
    policy,
    risk,
    cross_stage,
    bootstrap_interpretation,
    rule_support,
    top_removal,
    pending_status,
):
    gp = get_row(
        risk,
        analysis_period=
            EXTERNAL_PERIOD,
        probability_source=
            "selected_gp",
    )

    static = get_row(
        risk,
        analysis_period=
            EXTERNAL_PERIOD,
        probability_source=
            "static",
    )

    raw = get_row(
        risk,
        analysis_period=
            EXTERNAL_PERIOD,
        probability_source=
            "raw",
    )

    weather_share = float(
        cross_stage.iloc[
            0
        ][
            "static_share_of_raw_to_gp_improvement"
        ]
    )

    market_share = float(
        cross_stage.iloc[
            1
        ][
            "static_share_of_raw_to_gp_improvement"
        ]
    )

    trading_share = float(
        cross_stage.iloc[
            2
        ][
            "static_share_of_raw_to_gp_improvement"
        ]
    )

    gp_boot = bootstrap_interpretation[
        (
            bootstrap_interpretation[
                "estimand"
            ]
            == "method_level"
        )
        & (
            bootstrap_interpretation[
                "source_a"
            ]
            == "selected_gp"
        )
    ].iloc[
        0
    ]

    primary = rule_support.iloc[
        0
    ]

    common = rule_support.iloc[
        1
    ]

    top1 = top_removal[
        top_removal[
            "largest_positive_trades_removed"
        ]
        == 1
    ].iloc[
        0
    ]

    top2 = top_removal[
        top_removal[
            "largest_positive_trades_removed"
        ]
        == 2
    ].iloc[
        0
    ]

    text = f"""# Final empirical evidence handoff

This document is generated from the frozen March–August empirical pipeline.
It is a writing aid, not an additional empirical model.

## Frozen upstream choices

- Selected weather kernel: `{weather_summary['selected_kernel']}`.
- Development-selected pool: GP weight `{pool['weight_gp']:.3f}`, market weight `{pool['weight_market']:.3f}`.
- Trading probability signal: selected GP minus raw event-level Polymarket YES value.
- Frozen trading rule: `{policy['selected_rule']}`.
- Frozen trading threshold: `{policy['selected_threshold']:.2f}`.
- Reference cost: `{policy['reference_cost_per_share']:.2f}` per executed long-YES share.
- July–August information was not used for weather-kernel, pool or trading-policy selection.

## Core empirical narrative

1. **Most weather-model improvement comes from probabilistic conversion.**
   The static Gaussian captures `{100*weather_share:.1f}%` of the raw-to-selected-GP CRPS improvement.

2. **The same pattern survives at the probability-book level.**
   On external July–August total variation, the static correction captures
   `{100*market_share:.1f}%` of the raw-to-GP improvement. A value above
   100% means the static book is slightly closer to Polymarket than the GP book.

3. **The market still contains complementary information.**
   The convex pool uses only `{100*pool['weight_gp']:.1f}%` GP and
   `{100*pool['weight_market']:.1f}%` market weight. The pool has the best
   external proper-score point estimates, but the pool–market advantage is
   not statistically resolved.

4. **The economic attribution is consistent with the forecasting attribution.**
   External fixed-policy net PnL is `{float(raw['total_net_pnl']):.3f}` for raw,
   `{float(static['total_net_pnl']):.3f}` for static and
   `{float(gp['total_net_pnl']):.3f}` for the selected GP. The static
   correction therefore accounts for `{100*trading_share:.1f}%` of the
   raw-to-GP PnL improvement.

5. **The frozen GP policy is positive in point estimate but inference must be qualified.**
   It executes `{int(gp['trade_count'])}` trades over
   `{int(gp['eligible_settled_dates'])}` currently settled external dates,
   producing net PnL `{float(gp['total_net_pnl']):.3f}` and non-annualised
   settlement-date Sharpe `{float(gp['settlement_date_sharpe']):.3f}`.
   The ordinary bootstrap interval is
   `[{float(gp_boot['ordinary_lower_95']):.3f}, {float(gp_boot['ordinary_upper_95']):.3f}]`;
   the block-7 interval is
   `[{float(gp_boot['block7_lower_95']):.3f}, {float(gp_boot['block7_upper_95']):.3f}]`.
   This is classified as `{gp_boot['classification']}`.

6. **Rule selection has a support-composition caveat.**
   The prespecified procedure selects `{primary['selected_rule']}` on its own
   complete support, while the common-date diagnostic favours
   `{common['selected_rule']}`. The frozen policy is not changed.

7. **PnL is concentrated, but not entirely in one winning trade.**
   After removing the largest positive trade, external net PnL is
   `{float(top1['remaining_total_net_pnl']):.3f}`; after removing the two
   largest positive trades it is `{float(top2['remaining_total_net_pnl']):.3f}`.

8. **Forecast-risk transmission is nonlinear.**
   Smooth Gaussian probability sensitivities interact with event boundaries,
   argmax contract choice and the threshold activation rule. Portfolio finite
   slopes therefore vary with perturbation size and must not be interpreted as
   one global classical delta.

## Writing discipline

Main text should prioritise:

- raw → static → GP attribution;
- market complementarity and the development-selected pool;
- external fixed-policy attribution;
- non-annualised volatility-adjusted performance;
- ordinary versus block-bootstrap disagreement;
- nonlinear forecast-error → probability → decision → PnL transmission;
- the support-composition caveat.

Appendix material should contain:

- full threshold-neighbourhood grid;
- July/August month split;
- leave-one-trade-out concentration;
- full cost grid;
- complete perturbation grid;
- PIT/QQ/coverage diagnostics;
- exploratory Spearman table.

Do not make primary claims from:

- sqrt(365)-scaled Sharpe;
- return on entry cash;
- unadjusted exploratory correlation p-values;
- any external threshold that looks better than the frozen 0.15 threshold;
- the common-support 12h diagnostic as a replacement policy.

## Current 31 August status

`{pending_status['status']}`

Pending dates: `{pending_status['pending_dates']}`.

When the official target is available, update the target and rerun downstream
scores/trading/synthesis. Do not reselect the weather kernel, pool weight,
decision rule or threshold.
"""

    HANDOFF_MD.write_text(
        text
    )


def write_refresh_protocol(
    pending_status,
):
    text = """# 31 August HKO refresh protocol

This protocol is used only after the official HKO Daily Extract settlement
for 31 August 2026 becomes available.

The refresh is an external-target completion, not a new model-selection
exercise.

## Frozen quantities that must not be reselected

- weather kernel: Matérn-3/2;
- pool selection period: March–June;
- trading rule: 24h prior;
- trading threshold: 0.15;
- reference trading cost: 0.01;
- event definitions and decision-time rules.

## Refresh sequence

1. Refresh/certify the HKO target series using the existing HKO module.
2. Verify that the HKO audit contains the 31 August target and no unexpected
   missing dates.
3. Rerun the frozen weather-model module only to update target-dependent
   external scoring/diagnostics.
4. Rerun the market-book module using cached/recovered market histories.
5. Verify that the development-selected pool weight remains 0.188.
6. Rerun the trading module.
7. Verify that the selected rule remains `24h_prior` and threshold remains
   `0.15`.
8. Rerun the synthesis module.
9. Compare the before/after external scores and PnL and document the exact
   effect of adding the final settlement date.
10. Commit the refresh separately so the audit trail remains explicit.

## Prohibited behaviour

Do not use the 31 August outcome to:

- select another GP kernel;
- alter the convex-pool weight;
- choose another trading decision rule;
- choose another probability-gap threshold;
- introduce a new trading strategy.

The only legitimate changes are target-dependent external metrics and files
whose hashes necessarily change because the final realised outcome has been
added.
"""

    REFRESH_MD.write_text(
        text
    )


# =============================================================================
# STEP 70 — AUDIT
# =============================================================================


def build_checks(
    weather_summary,
    market_summary,
    trading_summary,
    pool,
    policy,
    rule_support,
    threshold_diag,
    monthly,
    loo,
    top_removal,
    bootstrap_interpretation,
    cost_summary,
    cross_stage,
    manifest,
    output_manifest,
    pending_status,
):
    checks = []

    def add(
        name,
        passed,
        observed,
        expected,
        note="",
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

                "note":
                    note,
            }
        )

    add(
        "weather_stage_pass",
        (
            weather_summary[
                "status"
            ]
            == "PASS"
        ),
        weather_summary[
            "status"
        ],
        "PASS",
    )

    add(
        "market_stage_pass",
        (
            market_summary[
                "status"
            ]
            == "PASS"
        ),
        market_summary[
            "status"
        ],
        "PASS",
    )

    add(
        "trading_stage_pass",
        (
            trading_summary[
                "status"
            ]
            == "PASS"
        ),
        trading_summary[
            "status"
        ],
        "PASS",
    )

    add(
        "weather_kernel_frozen_matern32",
        (
            weather_summary[
                "selected_kernel"
            ]
            == "matern32"
        ),
        weather_summary[
            "selected_kernel"
        ],
        "matern32",
    )

    add(
        "pool_weight_frozen_0188",
        isclose(
            pool[
                "weight_gp"
            ],
            0.188,
            atol=1e-12,
        ),
        pool[
            "weight_gp"
        ],
        0.188,
    )

    add(
        "trading_rule_frozen_24h",
        (
            policy[
                "selected_rule"
            ]
            == "24h_prior"
        ),
        policy[
            "selected_rule"
        ],
        "24h_prior",
    )

    add(
        "trading_threshold_frozen_015",
        isclose(
            policy[
                "selected_threshold"
            ],
            0.15,
            atol=1e-12,
        ),
        policy[
            "selected_threshold"
        ],
        0.15,
    )

    add(
        "external_not_used_for_selection",
        (
            policy[
                "external_data_used_for_selection"
            ]
            is False
            and pool[
                "external_validation_used"
            ]
            is False
        ),
        (
            policy[
                "external_data_used_for_selection"
            ],
            pool[
                "external_validation_used"
            ],
        ),
        (
            False,
            False,
        ),
    )

    baseline = threshold_diag[
        threshold_diag[
            "is_frozen_selected_threshold"
        ]
    ]

    add(
        "threshold_diagnostic_contains_one_frozen_baseline",
        (
            len(
                baseline
            )
            == 1
        ),
        len(
            baseline
        ),
        1,
    )

    if len(
        baseline
    ) == 1:
        add(
            "threshold_diagnostic_baseline_matches_trading_summary",
            isclose(
                baseline.iloc[
                    0
                ][
                    "total_net_pnl"
                ],
                trading_summary[
                    "external_selected_gp"
                ][
                    "total_net_pnl"
                ],
            ),
            baseline.iloc[
                0
            ][
                "total_net_pnl"
            ],
            trading_summary[
                "external_selected_gp"
            ][
                "total_net_pnl"
            ],
        )

    for source in [
        "raw",
        "static",
        "selected_gp",
    ]:
        month_total = float(
            monthly[
                monthly[
                    "probability_source"
                ]
                == source
            ][
                "total_net_pnl"
            ].sum()
        )

        expected = float(
            trading_summary[
                (
                    "external_selected_gp"
                    if source
                    == "selected_gp"
                    else (
                        "external_static"
                        if source
                        == "static"
                        else "external_raw"
                    )
                )
            ][
                "total_net_pnl"
            ]
        )

        add(
            f"monthly_{source}_sums_to_external_total",
            isclose(
                month_total,
                expected,
            ),
            month_total,
            expected,
        )

    baseline_pnl = float(
        trading_summary[
            "external_selected_gp"
        ][
            "total_net_pnl"
        ]
    )

    if len(
        loo
    ):
        expected_remaining = (
            baseline_pnl
            - loo[
                "removed_trade_pnl"
            ]
        )

        add(
            "leave_one_out_identity",
            bool(
                np.allclose(
                    loo[
                        "remaining_total_net_pnl"
                    ],
                    expected_remaining,
                    atol=1e-10,
                )
            ),
            int(
                np.allclose(
                    loo[
                        "remaining_total_net_pnl"
                    ],
                    expected_remaining,
                    atol=1e-10,
                )
            ),
            1,
        )

    add(
        "top_removal_baseline_matches_external_gp",
        isclose(
            top_removal.iloc[
                0
            ][
                "remaining_total_net_pnl"
            ],
            baseline_pnl,
        ),
        top_removal.iloc[
            0
        ][
            "remaining_total_net_pnl"
        ],
        baseline_pnl,
    )

    add(
        "bootstrap_reconciliation_contains_gp_method",
        bool(
            (
                (
                    bootstrap_interpretation[
                        "estimand"
                    ]
                    == "method_level"
                )
                & (
                    bootstrap_interpretation[
                        "source_a"
                    ]
                    == "selected_gp"
                )
            ).any()
        ),
        int(
            (
                (
                    bootstrap_interpretation[
                        "estimand"
                    ]
                    == "method_level"
                )
                & (
                    bootstrap_interpretation[
                        "source_a"
                    ]
                    == "selected_gp"
                )
            ).sum()
        ),
        1,
    )

    add(
        "cost_baseline_matches_external_gp",
        isclose(
            cost_summary.iloc[
                0
            ][
                "baseline_total_net_pnl"
            ],
            baseline_pnl,
        ),
        cost_summary.iloc[
            0
        ][
            "baseline_total_net_pnl"
        ],
        baseline_pnl,
    )

    add(
        "static_captures_at_least_90pct_in_all_three_domains",
        bool(
            cross_stage[
                "static_captures_at_least_90pct"
            ].all()
        ),
        int(
            cross_stage[
                "static_captures_at_least_90pct"
            ].sum()
        ),
        len(
            cross_stage
        ),
        (
            "Cross-stage synthesis only; this does not mean "
            "the static model dominates every individual metric."
        ),
    )

    add(
        "reproducibility_manifest_all_files_exist",
        bool(
            manifest[
                "exists"
            ].all()
        ),
        int(
            manifest[
                "exists"
            ].sum()
        ),
        len(
            manifest
        ),
    )

    add(
        "thesis_output_manifest_main_files_exist",
        bool(
            output_manifest.loc[
                output_manifest[
                    "recommended_location"
                ].isin(
                    [
                        "main_text",
                        "main_text_candidate",
                    ]
                ),
                "exists",
            ].all()
        ),
        int(
            output_manifest.loc[
                output_manifest[
                    "recommended_location"
                ].isin(
                    [
                        "main_text",
                        "main_text_candidate",
                    ]
                ),
                "exists",
            ].sum()
        ),
        int(
            output_manifest[
                "recommended_location"
            ]
            .isin(
                [
                    "main_text",
                    "main_text_candidate",
                ]
            )
            .sum()
        ),
    )

    valid_pending = (
        pending_status[
            "pending_dates"
        ]
        in (
            [],
            [
                "2026-08-31"
            ],
        )
    )

    add(
        "pending_target_status_is_expected",
        valid_pending,
        pending_status[
            "pending_dates"
        ],
        "[] or ['2026-08-31']",
    )

    add(
        "support_diagnostic_does_not_change_policy",
        bool(
            (
                rule_support[
                    "changes_frozen_policy"
                ]
                == False
            ).all()
        ),
        int(
            (
                rule_support[
                    "changes_frozen_policy"
                ]
                == False
            ).sum()
        ),
        len(
            rule_support
        ),
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

    missing = [
        str(
            p
        )
        for p in CORE_FILES
        if not p.exists()
    ]

    if missing:
        raise RuntimeError(
            "Missing frozen synthesis inputs:\n"
            + "\n".join(
                missing
            )
        )

    weather_summary = read_json(
        WEATHER_SUMMARY
    )

    market_summary = read_json(
        MARKET_SUMMARY
    )

    trading_summary = read_json(
        TRADING_SUMMARY
    )

    pool = read_json(
        POOL_SELECTION
    )

    policy = read_json(
        TRADING_POLICY
    )

    tv = pd.read_csv(
        MARKET_TV
    )

    scores = pd.read_csv(
        MARKET_SCORES
    )

    market_boot = pd.read_csv(
        MARKET_BOOTSTRAP
    )

    risk = pd.read_csv(
        TRADING_RISK
    )

    trading_boot = pd.read_csv(
        TRADING_BOOTSTRAP
    )

    ledgers = pd.read_csv(
        TRADING_LEDGERS
    )

    common = pd.read_csv(
        COMMON_RULE
    )

    cost = pd.read_csv(
        COST_SENSITIVITY
    )

    stress = pd.read_csv(
        STRESS
    )

    slopes = pd.read_csv(
        FINITE_SLOPES
    )

    error_bins = pd.read_csv(
        ERROR_BINS
    )

    spearman = pd.read_csv(
        SPEARMAN
    )

    # -------------------------------------------------------------------------
    # Step 56
    # -------------------------------------------------------------------------

    print(
        "Step 56: rule-support robustness..."
    )

    rule_support = (
        build_rule_support_robustness(
            policy,
            common,
        )
    )

    rule_support.to_csv(
        RULE_SUPPORT,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 57
    # -------------------------------------------------------------------------

    print(
        "Step 57: external threshold-neighbourhood diagnostic..."
    )

    threshold_diag = (
        external_threshold_diagnostic(
            ledgers,
            policy[
                "selected_threshold"
            ],
        )
    )

    threshold_diag.to_csv(
        THRESHOLD_DIAGNOSTIC,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 58
    # -------------------------------------------------------------------------

    print(
        "Step 58: July-versus-August stability..."
    )

    monthly = (
        external_monthly_stability(
            ledgers
        )
    )

    monthly.to_csv(
        MONTHLY_STABILITY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 59
    # -------------------------------------------------------------------------

    print(
        "Step 59: trade-concentration robustness..."
    )

    (
        loo,
        top_removal,
    ) = concentration_diagnostics(
        ledgers
    )

    loo.to_csv(
        LEAVE_ONE_OUT,
        index=False,
        float_format="%.10f",
    )

    top_removal.to_csv(
        TOP_WINNER_REMOVAL,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 60
    # -------------------------------------------------------------------------

    print(
        "Step 60: ordinary/block bootstrap reconciliation..."
    )

    bootstrap_interpretation = (
        bootstrap_reconciliation(
            trading_boot
        )
    )

    bootstrap_interpretation.to_csv(
        BOOTSTRAP_INTERPRETATION,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 61
    # -------------------------------------------------------------------------

    print(
        "Step 61: cost-robustness synthesis..."
    )

    cost_summary = (
        build_cost_summary(
            cost,
            risk,
        )
    )

    cost_summary.to_csv(
        COST_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 62
    # -------------------------------------------------------------------------

    print(
        "Step 62: forecast-risk synthesis..."
    )

    risk_synthesis = (
        build_forecast_risk_synthesis(
            stress,
            slopes,
            error_bins,
            spearman,
        )
    )

    risk_synthesis.to_csv(
        FORECAST_RISK_SYNTHESIS,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 63
    # -------------------------------------------------------------------------

    print(
        "Step 63: development/external stability audit..."
    )

    generalisation = (
        build_generalisation_stability(
            tv,
            scores,
            risk,
        )
    )

    generalisation.to_csv(
        GENERALISATION,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 64
    # -------------------------------------------------------------------------

    print(
        "Step 64: cross-stage attribution synthesis..."
    )

    cross_stage = (
        build_cross_stage_attribution(
            weather_summary,
            tv,
            risk,
        )
    )

    cross_stage.to_csv(
        CROSS_STAGE,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 68 status is needed for evidence register.
    # -------------------------------------------------------------------------

    pending_status = (
        build_pending_status(
            weather_summary,
            market_summary,
            trading_summary,
            policy,
            pool,
        )
    )

    PENDING_STATUS.write_text(
        json.dumps(
            pending_status,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    # -------------------------------------------------------------------------
    # Step 65
    # -------------------------------------------------------------------------

    print(
        "Step 65: authoritative final result ledger..."
    )

    result_ledger = (
        build_result_ledger(
            weather_summary,
            market_summary,
            pool,
            tv,
            scores,
            market_boot,
            policy,
            risk,
            trading_boot,
            rule_support,
            threshold_diag,
            monthly,
            top_removal,
            cost_summary,
            risk_synthesis,
        )
    )

    result_ledger.to_csv(
        RESULT_LEDGER,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Step 66
    # -------------------------------------------------------------------------

    print(
        "Step 66: thesis evidence register..."
    )

    evidence = (
        build_evidence_register(
            result_ledger,
            bootstrap_interpretation,
            rule_support,
            cross_stage,
            top_removal,
            pending_status[
                "pending_dates"
            ],
        )
    )

    evidence.to_csv(
        EVIDENCE_REGISTER,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 67
    # -------------------------------------------------------------------------

    print(
        "Step 67: figure/table shortlist..."
    )

    make_figures(
        threshold_diag,
        monthly,
        cross_stage,
        policy[
            "selected_threshold"
        ],
    )

    output_manifest = (
        build_output_manifest()
    )

    output_manifest.to_csv(
        OUTPUT_MANIFEST,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 68
    # -------------------------------------------------------------------------

    print(
        "Step 68: 31-August pending-target gate..."
    )

    write_refresh_protocol(
        pending_status
    )

    # -------------------------------------------------------------------------
    # Step 69
    # -------------------------------------------------------------------------

    print(
        "Step 69: reproducibility manifest and thesis handoff..."
    )

    manifest = (
        build_reproducibility_manifest()
    )

    manifest.to_csv(
        REPRO_MANIFEST,
        index=False,
    )

    write_handoff(
        weather_summary,
        market_summary,
        pool,
        policy,
        risk,
        cross_stage,
        bootstrap_interpretation,
        rule_support,
        top_removal,
        pending_status,
    )

    # -------------------------------------------------------------------------
    # Step 70
    # -------------------------------------------------------------------------

    print(
        "Step 70: final synthesis audit..."
    )

    (
        checks,
        status,
    ) = build_checks(
        weather_summary,
        market_summary,
        trading_summary,
        pool,
        policy,
        rule_support,
        threshold_diag,
        monthly,
        loo,
        top_removal,
        bootstrap_interpretation,
        cost_summary,
        cross_stage,
        manifest,
        output_manifest,
        pending_status,
    )

    checks.to_csv(
        CHECKS_CSV,
        index=False,
    )

    cross_map = dict(
        zip(
            cross_stage[
                "domain"
            ],
            cross_stage[
                "static_share_of_raw_to_gp_improvement"
            ],
        )
    )

    gp_risk = get_row(
        risk,
        analysis_period=
            EXTERNAL_PERIOD,
        probability_source=
            "selected_gp",
    )

    primary_rule = rule_support.iloc[
        0
    ]

    common_rule = rule_support.iloc[
        1
    ]

    neighbourhood = threshold_diag[
        threshold_diag[
            "within_0_05_of_selected"
        ]
    ]

    summary = {
        "status":
            status,

        "stage":
            "steps_56_70",

        "upstream_steps_1_55_frozen":
            True,

        "weather_kernel":
            weather_summary[
                "selected_kernel"
            ],

        "pool_weight_gp":
            pool[
                "weight_gp"
            ],

        "trading_rule":
            policy[
                "selected_rule"
            ],

        "trading_threshold":
            policy[
                "selected_threshold"
            ],

        "primary_rule_selection":
            str(
                primary_rule[
                    "selected_rule"
                ]
            ),

        "common_support_rule_diagnostic":
            str(
                common_rule[
                    "selected_rule"
                ]
            ),

        "rule_selection_support_sensitive":
            bool(
                rule_support[
                    "rule_selection_support_sensitive"
                ].iloc[
                    0
                ]
            ),

        "external_gp_net_pnl_currently":
            float(
                gp_risk[
                    "total_net_pnl"
                ]
            ),

        "external_gp_trades_currently":
            int(
                gp_risk[
                    "trade_count"
                ]
            ),

        "external_gp_settlement_date_sharpe":
            float(
                gp_risk[
                    "settlement_date_sharpe"
                ]
            ),

        "external_threshold_neighbourhood_min_pnl":
            float(
                neighbourhood[
                    "total_net_pnl"
                ].min()
            ),

        "external_threshold_neighbourhood_max_pnl":
            float(
                neighbourhood[
                    "total_net_pnl"
                ].max()
            ),

        "weather_static_share_raw_to_gp_improvement":
            float(
                cross_map[
                    "weather_continuous_crps"
                ]
            ),

        "market_tv_static_share_raw_to_gp_improvement":
            float(
                cross_map[
                    "weather_market_total_variation"
                ]
            ),

        "trading_static_share_raw_to_gp_improvement":
            float(
                cross_map[
                    "fixed_policy_net_pnl"
                ]
            ),

        "pending_external_target_dates":
            pending_status[
                "pending_dates"
            ],

        "development_reselection_after_pending_target":
            False,

        "result_ledger_sha256":
            sha256_file(
                RESULT_LEDGER
            ),

        "evidence_register_sha256":
            sha256_file(
                EVIDENCE_REGISTER
            ),

        "reproducibility_manifest_sha256":
            sha256_file(
                REPRO_MANIFEST
            ),
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print(
        "status=",
        status,
    )

    print(
        "primary_rule=",
        summary[
            "primary_rule_selection"
        ],
    )

    print(
        "common_support_rule=",
        summary[
            "common_support_rule_diagnostic"
        ],
    )

    print(
        "weather_static_share=",
        summary[
            "weather_static_share_raw_to_gp_improvement"
        ],
    )

    print(
        "market_tv_static_share=",
        summary[
            "market_tv_static_share_raw_to_gp_improvement"
        ],
    )

    print(
        "trading_static_share=",
        summary[
            "trading_static_share_raw_to_gp_improvement"
        ],
    )

    print(
        "pending=",
        summary[
            "pending_external_target_dates"
        ],
    )

    if status != "PASS":
        print()
        print(
            checks[
                ~checks[
                    "passed"
                ]
            ].to_string(
                index=False
            )
        )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
