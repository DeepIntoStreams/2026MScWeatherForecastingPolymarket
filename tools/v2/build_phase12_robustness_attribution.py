#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
      "phase12_robustness_attribution_spec.json"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def parse_dates(series: pd.Series) -> pd.Series:
    return (
        pd.to_datetime(
            series,
            errors="raise",
            format="mixed",
            utc=True,
        )
        .dt.tz_convert(None)
        .dt.normalize()
    )


def boolean_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(
        series.dtype
    ):
        return series.astype(bool)

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "1.0",
                "yes",
            }
        )
    )


def maximum_drawdown(
    date_pnl: np.ndarray,
) -> float:
    values = np.asarray(
        date_pnl,
        dtype=float,
    )

    cumulative = np.concatenate(
        [
            np.array([0.0]),
            np.cumsum(values),
        ]
    )

    running_peak = np.maximum.accumulate(
        cumulative
    )

    return float(
        np.max(
            running_peak
            - cumulative
        )
    )


def evaluate_strategy(
    candidate_panel: pd.DataFrame,
    threshold: float,
    transaction_cost: float,
) -> pd.DataFrame:
    result = candidate_panel.copy()

    result[
        "evaluated_threshold"
    ] = float(
        threshold
    )

    result[
        "transaction_cost_per_share"
    ] = float(
        transaction_cost
    )

    result[
        "trade_executed"
    ] = result[
        "gross_value_gap"
    ].ge(
        float(
            threshold
        )
    )

    trade = result[
        "trade_executed"
    ].astype(
        float
    )

    result[
        "gross_pnl"
    ] = trade * (
        result[
            "realised_yes"
        ]
        - result[
            "market_probability_raw"
        ]
    )

    result[
        "transaction_cost"
    ] = (
        trade
        * float(
            transaction_cost
        )
    )

    result[
        "net_pnl"
    ] = (
        result[
            "gross_pnl"
        ]
        - result[
            "transaction_cost"
        ]
    )

    result[
        "capital_committed"
    ] = trade * (
        result[
            "market_probability_raw"
        ]
        + float(
            transaction_cost
        )
    )

    result[
        "winning_trade"
    ] = (
        result[
            "trade_executed"
        ]
        & result[
            "net_pnl"
        ].gt(
            0.0
        )
    )

    result[
        "losing_trade"
    ] = (
        result[
            "trade_executed"
        ]
        & result[
            "net_pnl"
        ].lt(
            0.0
        )
    )

    return result.sort_values(
        [
            "target_date",
            "decision_rule",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )


def performance(
    evaluated: pd.DataFrame,
) -> dict[str, Any]:
    dates = int(
        evaluated[
            "target_date"
        ].nunique()
    )

    trades = evaluated.loc[
        evaluated[
            "trade_executed"
        ]
    ]

    trade_count = int(
        len(
            trades
        )
    )

    total_gross_pnl = float(
        evaluated[
            "gross_pnl"
        ].sum()
    )

    total_net_pnl = float(
        evaluated[
            "net_pnl"
        ].sum()
    )

    total_cost = float(
        evaluated[
            "transaction_cost"
        ].sum()
    )

    total_capital = float(
        evaluated[
            "capital_committed"
        ].sum()
    )

    mean_date_pnl = float(
        evaluated[
            "net_pnl"
        ].mean()
    )

    date_standard_deviation = (
        float(
            evaluated[
                "net_pnl"
            ].std(
                ddof=1
            )
        )
        if dates > 1
        else 0.0
    )

    date_standard_error = (
        date_standard_deviation
        / math.sqrt(
            dates
        )
        if dates > 0
        else np.nan
    )

    if trade_count > 0:
        win_rate = float(
            trades[
                "winning_trade"
            ].mean()
        )

        mean_trade_pnl = float(
            trades[
                "net_pnl"
            ].mean()
        )

        median_trade_pnl = float(
            trades[
                "net_pnl"
            ].median()
        )
    else:
        win_rate = np.nan
        mean_trade_pnl = np.nan
        median_trade_pnl = np.nan

    return {
        "dates":
            dates,
        "trade_count":
            trade_count,
        "trade_frequency":
            (
                trade_count / dates
                if dates > 0
                else np.nan
            ),
        "winning_trades":
            int(
                evaluated[
                    "winning_trade"
                ].sum()
            ),
        "losing_trades":
            int(
                evaluated[
                    "losing_trade"
                ].sum()
            ),
        "win_rate":
            win_rate,
        "total_gross_pnl":
            total_gross_pnl,
        "total_transaction_cost":
            total_cost,
        "total_net_pnl":
            total_net_pnl,
        "mean_date_net_pnl":
            mean_date_pnl,
        "standard_deviation_date_net_pnl":
            date_standard_deviation,
        "standard_error_date_net_pnl":
            date_standard_error,
        "mean_trade_net_pnl":
            mean_trade_pnl,
        "median_trade_net_pnl":
            median_trade_pnl,
        "total_capital_committed":
            total_capital,
        "return_on_committed_capital":
            (
                total_net_pnl
                / total_capital
                if total_capital > 0.0
                else np.nan
            ),
        "maximum_drawdown":
            maximum_drawdown(
                evaluated[
                    "net_pnl"
                ].to_numpy(
                    dtype=float
                )
            ),
    }


def build_threshold_grid(
    candidates: pd.DataFrame,
    thresholds: np.ndarray,
    reference_cost: float,
    selection_period: str,
    rules: list[str],
) -> pd.DataFrame:
    training = candidates.loc[
        candidates[
            "sample_period"
        ].eq(
            selection_period
        )
    ]

    rows: list[
        dict[str, Any]
    ] = []

    for rule in rules:
        rule_panel = training.loc[
            training[
                "decision_rule"
            ].eq(
                rule
            )
        ]

        if rule_panel.empty:
            raise RuntimeError(
                "No training candidates exist for "
                f"{rule}."
            )

        for threshold in thresholds:
            evaluated = evaluate_strategy(
                rule_panel,
                float(
                    threshold
                ),
                reference_cost,
            )

            rows.append(
                {
                    "decision_rule":
                        rule,
                    "threshold":
                        float(
                            threshold
                        ),
                    "transaction_cost_per_share":
                        reference_cost,
                    **performance(
                        evaluated
                    ),
                }
            )

    return pd.DataFrame(
        rows
    )


def select_from_grid(
    grid: pd.DataFrame,
    rules: list[str],
    minimum_trades: int,
) -> pd.DataFrame:
    rows: list[
        dict[str, Any]
    ] = []

    for rule in rules:
        rule_grid = grid.loc[
            grid[
                "decision_rule"
            ].eq(
                rule
            )
        ].copy()

        eligible = rule_grid.loc[
            rule_grid[
                "trade_count"
            ].ge(
                minimum_trades
            )
        ].copy()

        relaxed = False

        if eligible.empty:
            maximum_trades = int(
                rule_grid[
                    "trade_count"
                ].max()
            )

            eligible = rule_grid.loc[
                rule_grid[
                    "trade_count"
                ].eq(
                    maximum_trades
                )
            ].copy()

            relaxed = True

        best = (
            eligible.sort_values(
                [
                    "mean_date_net_pnl",
                    "threshold",
                ],
                ascending=[
                    False,
                    False,
                ],
                kind="stable",
            )
            .iloc[0]
        )

        cutoff = (
            float(
                best[
                    "mean_date_net_pnl"
                ]
            )
            - float(
                best[
                    "standard_error_date_net_pnl"
                ]
            )
        )

        selected = (
            eligible.loc[
                eligible[
                    "mean_date_net_pnl"
                ].ge(
                    cutoff
                )
            ]
            .sort_values(
                [
                    "threshold",
                    "mean_date_net_pnl",
                ],
                ascending=[
                    False,
                    False,
                ],
                kind="stable",
            )
            .iloc[0]
        )

        selection_score = (
            float(
                selected[
                    "mean_date_net_pnl"
                ]
            )
            - float(
                selected[
                    "standard_error_date_net_pnl"
                ]
            )
        )

        rows.append(
            {
                "decision_rule":
                    rule,
                "selected_threshold":
                    float(
                        selected[
                            "threshold"
                        ]
                    ),
                "selected_training_dates":
                    int(
                        selected[
                            "dates"
                        ]
                    ),
                "selected_training_trades":
                    int(
                        selected[
                            "trade_count"
                        ]
                    ),
                "selected_training_total_net_pnl":
                    float(
                        selected[
                            "total_net_pnl"
                        ]
                    ),
                "selected_training_mean_date_net_pnl":
                    float(
                        selected[
                            "mean_date_net_pnl"
                        ]
                    ),
                "selected_training_standard_error":
                    float(
                        selected[
                            "standard_error_date_net_pnl"
                        ]
                    ),
                "primary_rule_selection_score":
                    selection_score,
                "minimum_trade_constraint_relaxed":
                    relaxed,
            }
        )

    selection = pd.DataFrame(
        rows
    )

    primary_index = (
        selection.sort_values(
            [
                "primary_rule_selection_score",
                "selected_training_mean_date_net_pnl",
                "selected_training_trades",
                "selected_threshold",
            ],
            ascending=[
                False,
                False,
                False,
                False,
            ],
            kind="stable",
        )
        .index[0]
    )

    selection[
        "selected_primary_decision_rule"
    ] = False

    selection.loc[
        primary_index,
        "selected_primary_decision_rule",
    ] = True

    return selection


def threshold_neighbourhood(
    candidates: pd.DataFrame,
    frozen_selection: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    robustness = specification[
        "robustness"
    ]

    reference_cost = float(
        robustness[
            "reference_transaction_cost"
        ]
    )

    minimum = float(
        robustness[
            "minimum_threshold"
        ]
    )

    maximum = float(
        robustness[
            "maximum_threshold"
        ]
    )

    offsets = [
        float(value)
        for value in robustness[
            "threshold_neighbourhood_offsets"
        ]
    ]

    rows: list[
        dict[str, Any]
    ] = []

    for _, selection_row in (
        frozen_selection.iterrows()
    ):
        rule = str(
            selection_row[
                "decision_rule"
            ]
        )

        frozen_threshold = float(
            selection_row[
                "selected_threshold"
            ]
        )

        thresholds = sorted(
            {
                round(
                    min(
                        maximum,
                        max(
                            minimum,
                            frozen_threshold
                            + offset,
                        ),
                    ),
                    10,
                )
                for offset in offsets
            }
        )

        rule_panel = candidates.loc[
            candidates[
                "decision_rule"
            ].eq(
                rule
            )
        ]

        for sample_period in [
            specification[
                "sample_periods"
            ][
                "strategy_selection"
            ],
            specification[
                "sample_periods"
            ][
                "out_of_sample_validation"
            ],
        ]:
            split = rule_panel.loc[
                rule_panel[
                    "sample_period"
                ].eq(
                    sample_period
                )
            ]

            for threshold in thresholds:
                evaluated = evaluate_strategy(
                    split,
                    threshold,
                    reference_cost,
                )

                rows.append(
                    {
                        "sample_period":
                            sample_period,
                        "decision_rule":
                            rule,
                        "threshold":
                            threshold,
                        "offset_from_frozen":
                            threshold
                            - frozen_threshold,
                        "frozen_threshold":
                            frozen_threshold,
                        "is_frozen_threshold":
                            math.isclose(
                                threshold,
                                frozen_threshold,
                                abs_tol=1e-12,
                                rel_tol=0.0,
                            ),
                        "transaction_cost_per_share":
                            reference_cost,
                        **performance(
                            evaluated
                        ),
                    }
                )

    return pd.DataFrame(
        rows
    )


def leave_one_date_out_selection(
    candidates: pd.DataFrame,
    thresholds: np.ndarray,
    frozen_selection: pd.DataFrame,
    specification: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    selection_period = specification[
        "sample_periods"
    ][
        "strategy_selection"
    ]

    reference_cost = float(
        specification[
            "robustness"
        ][
            "reference_transaction_cost"
        ]
    )

    minimum_trades = int(
        specification[
            "robustness"
        ][
            "minimum_training_trades"
        ]
    )

    rules = specification[
        "decision_rules"
    ]

    training = candidates.loc[
        candidates[
            "sample_period"
        ].eq(
            selection_period
        )
    ].copy()

    training_dates = sorted(
        training[
            "target_date"
        ].unique()
    )

    rows: list[
        dict[str, Any]
    ] = []

    for omitted_date in training_dates:
        reduced = training.loc[
            training[
                "target_date"
            ].ne(
                omitted_date
            )
        ].copy()

        reduced[
            "sample_period"
        ] = selection_period

        grid = build_threshold_grid(
            reduced,
            thresholds,
            reference_cost,
            selection_period,
            rules,
        )

        selected = select_from_grid(
            grid,
            rules,
            minimum_trades,
        )

        primary_rule = selected.loc[
            selected[
                "selected_primary_decision_rule"
            ],
            "decision_rule",
        ].iloc[0]

        for _, selected_row in (
            selected.iterrows()
        ):
            rule = str(
                selected_row[
                    "decision_rule"
                ]
            )

            frozen_threshold = float(
                frozen_selection.loc[
                    frozen_selection[
                        "decision_rule"
                    ].eq(
                        rule
                    ),
                    "selected_threshold",
                ].iloc[0]
            )

            rows.append(
                {
                    "omitted_target_date":
                        pd.Timestamp(
                            omitted_date
                        ),
                    "decision_rule":
                        rule,
                    "selected_threshold":
                        float(
                            selected_row[
                                "selected_threshold"
                            ]
                        ),
                    "full_sample_frozen_threshold":
                        frozen_threshold,
                    "threshold_change":
                        float(
                            selected_row[
                                "selected_threshold"
                            ]
                        )
                        - frozen_threshold,
                    "selected_primary_rule":
                        primary_rule,
                    "rule_is_primary":
                        rule
                        == primary_rule,
                    "selection_score":
                        float(
                            selected_row[
                                "primary_rule_selection_score"
                            ]
                        ),
                    "training_dates_after_omission":
                        int(
                            selected_row[
                                "selected_training_dates"
                            ]
                        ),
                    "training_trades_after_omission":
                        int(
                            selected_row[
                                "selected_training_trades"
                            ]
                        ),
                }
            )

    paths = pd.DataFrame(
        rows
    )

    summary_rows: list[
        dict[str, Any]
    ] = []

    full_primary_rule = (
        frozen_selection.loc[
            boolean_series(
                frozen_selection[
                    "selected_primary_decision_rule"
                ]
            ),
            "decision_rule",
        ].iloc[0]
    )

    for rule in rules:
        group = paths.loc[
            paths[
                "decision_rule"
            ].eq(
                rule
            )
        ]

        frozen_threshold = float(
            group[
                "full_sample_frozen_threshold"
            ].iloc[0]
        )

        summary_rows.append(
            {
                "decision_rule":
                    rule,
                "omissions":
                    len(
                        group
                    ),
                "full_sample_frozen_threshold":
                    frozen_threshold,
                "mean_leave_one_out_threshold":
                    float(
                        group[
                            "selected_threshold"
                        ].mean()
                    ),
                "median_leave_one_out_threshold":
                    float(
                        group[
                            "selected_threshold"
                        ].median()
                    ),
                "minimum_leave_one_out_threshold":
                    float(
                        group[
                            "selected_threshold"
                        ].min()
                    ),
                "maximum_leave_one_out_threshold":
                    float(
                        group[
                            "selected_threshold"
                        ].max()
                    ),
                "standard_deviation_leave_one_out_threshold":
                    float(
                        group[
                            "selected_threshold"
                        ].std(
                            ddof=1
                        )
                    ),
                "frozen_threshold_reselection_fraction":
                    float(
                        np.isclose(
                            group[
                                "selected_threshold"
                            ],
                            frozen_threshold,
                            atol=1e-12,
                            rtol=0.0,
                        ).mean()
                    ),
                "rule_selected_primary_fraction":
                    float(
                        group[
                            "rule_is_primary"
                        ].mean()
                    ),
                "full_sample_primary_rule":
                    rule
                    == full_primary_rule,
                "full_primary_rule_reselected_fraction":
                    float(
                        group[
                            "selected_primary_rule"
                        ].eq(
                            full_primary_rule
                        ).mean()
                    ),
            }
        )

    return (
        paths,
        pd.DataFrame(
            summary_rows
        ),
    )


def fine_cost_sensitivity(
    candidates: pd.DataFrame,
    frozen_selection: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    robustness = specification[
        "robustness"
    ]

    primary = frozen_selection.loc[
        boolean_series(
            frozen_selection[
                "selected_primary_decision_rule"
            ]
        )
    ].iloc[0]

    primary_rule = str(
        primary[
            "decision_rule"
        ]
    )

    threshold = float(
        primary[
            "selected_threshold"
        ]
    )

    minimum = float(
        robustness[
            "fine_cost_minimum"
        ]
    )

    maximum = float(
        robustness[
            "fine_cost_maximum"
        ]
    )

    increment = float(
        robustness[
            "fine_cost_increment"
        ]
    )

    count = int(
        round(
            (
                maximum - minimum
            )
            / increment
        )
    ) + 1

    costs = np.round(
        np.linspace(
            minimum,
            maximum,
            count,
        ),
        10,
    )

    rows: list[
        dict[str, Any]
    ] = []

    primary_panel = candidates.loc[
        candidates[
            "decision_rule"
        ].eq(
            primary_rule
        )
    ]

    for sample_period in [
        specification[
            "sample_periods"
        ][
            "strategy_selection"
        ],
        specification[
            "sample_periods"
        ][
            "out_of_sample_validation"
        ],
    ]:
        split = primary_panel.loc[
            primary_panel[
                "sample_period"
            ].eq(
                sample_period
            )
        ]

        zero_cost = evaluate_strategy(
            split,
            threshold,
            0.0,
        )

        trade_count = int(
            zero_cost[
                "trade_executed"
            ].sum()
        )

        total_gross_pnl = float(
            zero_cost[
                "gross_pnl"
            ].sum()
        )

        break_even_cost = (
            total_gross_pnl
            / trade_count
            if trade_count > 0
            else np.nan
        )

        for cost in costs:
            evaluated = evaluate_strategy(
                split,
                threshold,
                float(
                    cost
                ),
            )

            rows.append(
                {
                    "sample_period":
                        sample_period,
                    "decision_rule":
                        primary_rule,
                    "frozen_threshold":
                        threshold,
                    "transaction_cost_per_share":
                        float(
                            cost
                        ),
                    "analytical_break_even_cost":
                        break_even_cost,
                    **performance(
                        evaluated
                    ),
                }
            )

    return pd.DataFrame(
        rows
    )


def derive_event_type(
    frame: pd.DataFrame,
) -> pd.Series:
    if (
        "event_type"
        in frame.columns
    ):
        supplied = (
            frame[
                "event_type"
            ]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        valid = supplied.isin(
            {
                "lower_tail",
                "interior",
                "upper_tail",
            }
        )

        result = supplied.where(
            valid
        )
    else:
        result = pd.Series(
            pd.NA,
            index=frame.index,
            dtype="object",
        )

    lower = pd.to_numeric(
        frame[
            "lower_bound_c"
        ],
        errors="coerce",
    )

    upper = pd.to_numeric(
        frame[
            "upper_bound_c"
        ],
        errors="coerce",
    )

    result = result.where(
        result.notna(),
        np.where(
            np.isneginf(
                lower
            ),
            "lower_tail",
            np.where(
                np.isposinf(
                    upper
                ),
                "upper_tail",
                "interior",
            ),
        ),
    )

    return result


def observed_temperature_column(
    frame: pd.DataFrame,
) -> str:
    candidates = [
        "observed_temperature_c",
        "hko_daily_max_c",
        "hko_absolute_daily_max_c",
        "realised_temperature_c",
        "realized_temperature_c",
        "actual_daily_max_c",
    ]

    for column in candidates:
        if column in frame.columns:
            return column

    raise RuntimeError(
        "No observed-temperature column exists "
        "for temperature-bucket attribution."
    )


def primary_trade_panel(
    candidates: pd.DataFrame,
    frozen_selection: pd.DataFrame,
    specification: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    dict[str, float],
]:
    primary = frozen_selection.loc[
        boolean_series(
            frozen_selection[
                "selected_primary_decision_rule"
            ]
        )
    ].iloc[0]

    primary_rule = str(
        primary[
            "decision_rule"
        ]
    )

    threshold = float(
        primary[
            "selected_threshold"
        ]
    )

    cost = float(
        specification[
            "robustness"
        ][
            "reference_transaction_cost"
        ]
    )

    panel = candidates.loc[
        candidates[
            "decision_rule"
        ].eq(
            primary_rule
        )
    ].copy()

    panel[
        "event_type_attribution"
    ] = derive_event_type(
        panel
    )

    temperature_column = (
        observed_temperature_column(
            panel
        )
    )

    panel[
        "observed_temperature_attribution_c"
    ] = pd.to_numeric(
        panel[
            temperature_column
        ],
        errors="raise",
    )

    training_temperatures = (
        panel.loc[
            panel[
                "sample_period"
            ].eq(
                specification[
                    "sample_periods"
                ][
                    "strategy_selection"
                ]
            ),
            [
                "target_date",
                "observed_temperature_attribution_c",
            ],
        ]
        .drop_duplicates(
            "target_date"
        )[
            "observed_temperature_attribution_c"
        ]
    )

    lower_tercile = float(
        training_temperatures.quantile(
            1.0 / 3.0
        )
    )

    upper_tercile = float(
        training_temperatures.quantile(
            2.0 / 3.0
        )
    )

    panel[
        "temperature_bucket"
    ] = pd.cut(
        panel[
            "observed_temperature_attribution_c"
        ],
        bins=[
            -np.inf,
            lower_tercile,
            upper_tercile,
            np.inf,
        ],
        labels=[
            "cool",
            "middle",
            "hot",
        ],
        include_lowest=True,
        right=True,
    ).astype(
        str
    )

    evaluated = evaluate_strategy(
        panel,
        threshold,
        cost,
    )

    return (
        evaluated,
        {
            "training_lower_tercile_c":
                lower_tercile,
            "training_upper_tercile_c":
                upper_tercile,
        },
    )


def attribution_summary(
    evaluated: pd.DataFrame,
    group_column: str,
) -> pd.DataFrame:
    rows: list[
        dict[str, Any]
    ] = []

    for sample_period in sorted(
        evaluated[
            "sample_period"
        ].unique()
    ):
        split = evaluated.loc[
            evaluated[
                "sample_period"
            ].eq(
                sample_period
            )
        ]

        for group_value, group in split.groupby(
            group_column,
            dropna=False,
            sort=True,
        ):
            metrics = performance(
                group
            )

            rows.append(
                {
                    "sample_period":
                        sample_period,
                    "attribution_dimension":
                        group_column,
                    "attribution_group":
                        str(
                            group_value
                        ),
                    "available_dates":
                        int(
                            group[
                                "target_date"
                            ].nunique()
                        ),
                    **metrics,
                }
            )

    return pd.DataFrame(
        rows
    )


def trade_contribution_analysis(
    evaluated: pd.DataFrame,
    specification: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    june = evaluated.loc[
        evaluated[
            "sample_period"
        ].eq(
            specification[
                "sample_periods"
            ][
                "out_of_sample_validation"
            ]
        )
        & evaluated[
            "trade_executed"
        ]
    ].copy()

    if june.empty:
        raise RuntimeError(
            "The frozen primary strategy produced "
            "no June trades."
        )

    june = june.sort_values(
        [
            "net_pnl",
            "target_date",
        ],
        ascending=[
            False,
            True,
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    june[
        "pnl_rank_descending"
    ] = (
        np.arange(
            len(
                june
            )
        )
        + 1
    )

    total_pnl = float(
        june[
            "net_pnl"
        ].sum()
    )

    total_absolute_pnl = float(
        june[
            "net_pnl"
        ].abs().sum()
    )

    june[
        "cumulative_net_pnl_descending"
    ] = june[
        "net_pnl"
    ].cumsum()

    june[
        "absolute_pnl_share"
    ] = (
        june[
            "net_pnl"
        ].abs()
        / total_absolute_pnl
        if total_absolute_pnl > 0.0
        else np.nan
    )

    june[
        "leave_one_trade_out_total_pnl"
    ] = (
        total_pnl
        - june[
            "net_pnl"
        ]
    )

    positive_pnl = june.loc[
        june[
            "net_pnl"
        ].gt(
            0.0
        ),
        "net_pnl",
    ]

    positive_total = float(
        positive_pnl.sum()
    )

    largest_positive_share = (
        float(
            positive_pnl.max()
            / positive_total
        )
        if positive_total > 0.0
        else np.nan
    )

    hhi_absolute = (
        float(
            np.square(
                june[
                    "absolute_pnl_share"
                ]
            ).sum()
        )
        if total_absolute_pnl > 0.0
        else np.nan
    )

    summary = pd.DataFrame(
        [
            {
                "sample_period":
                    "out_of_sample_validation",
                "trade_count":
                    len(
                        june
                    ),
                "total_net_pnl":
                    total_pnl,
                "total_absolute_pnl":
                    total_absolute_pnl,
                "winning_trades":
                    int(
                        june[
                            "net_pnl"
                        ].gt(
                            0.0
                        ).sum()
                    ),
                "losing_trades":
                    int(
                        june[
                            "net_pnl"
                        ].lt(
                            0.0
                        ).sum()
                    ),
                "largest_winning_trade":
                    float(
                        june[
                            "net_pnl"
                        ].max()
                    ),
                "largest_losing_trade":
                    float(
                        june[
                            "net_pnl"
                        ].min()
                    ),
                "largest_positive_contribution_share":
                    largest_positive_share,
                "largest_absolute_contribution_share":
                    float(
                        june[
                            "absolute_pnl_share"
                        ].max()
                    ),
                "absolute_pnl_herfindahl":
                    hhi_absolute,
                "minimum_leave_one_trade_out_total_pnl":
                    float(
                        june[
                            "leave_one_trade_out_total_pnl"
                        ].min()
                    ),
                "maximum_leave_one_trade_out_total_pnl":
                    float(
                        june[
                            "leave_one_trade_out_total_pnl"
                        ].max()
                    ),
                "positive_without_best_trade":
                    bool(
                        june[
                            "leave_one_trade_out_total_pnl"
                        ].iloc[0]
                        > 0.0
                    ),
            }
        ]
    )

    return june, summary


def decision_rule_dependence(
    candidates: pd.DataFrame,
    frozen_selection: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    reference_cost = float(
        specification[
            "robustness"
        ][
            "reference_transaction_cost"
        ]
    )

    thresholds = {
        str(row["decision_rule"]):
            float(
                row[
                    "selected_threshold"
                ]
            )
        for _, row
        in frozen_selection.iterrows()
    }

    evaluated_parts: list[
        pd.DataFrame
    ] = []

    for rule, threshold in thresholds.items():
        rule_panel = candidates.loc[
            candidates[
                "decision_rule"
            ].eq(
                rule
            )
        ]

        evaluated_parts.append(
            evaluate_strategy(
                rule_panel,
                threshold,
                reference_cost,
            )
        )

    evaluated = pd.concat(
        evaluated_parts,
        ignore_index=True,
    )

    rows: list[
        dict[str, Any]
    ] = []

    rules = specification[
        "decision_rules"
    ]

    for sample_period in [
        specification[
            "sample_periods"
        ][
            "strategy_selection"
        ],
        specification[
            "sample_periods"
        ][
            "out_of_sample_validation"
        ],
        "all_period",
    ]:
        if sample_period == "all_period":
            split = evaluated.copy()
        else:
            split = evaluated.loc[
                evaluated[
                    "sample_period"
                ].eq(
                    sample_period
                )
            ]

        for first_rule, second_rule in combinations(
            rules,
            2,
        ):
            first = split.loc[
                split[
                    "decision_rule"
                ].eq(
                    first_rule
                ),
                [
                    "target_date",
                    "gross_value_gap",
                    "trade_executed",
                    "net_pnl",
                    "contract_key",
                ],
            ].rename(
                columns={
                    "gross_value_gap":
                        "first_gap",
                    "trade_executed":
                        "first_trade",
                    "net_pnl":
                        "first_pnl",
                    "contract_key":
                        "first_contract",
                }
            )

            second = split.loc[
                split[
                    "decision_rule"
                ].eq(
                    second_rule
                ),
                [
                    "target_date",
                    "gross_value_gap",
                    "trade_executed",
                    "net_pnl",
                    "contract_key",
                ],
            ].rename(
                columns={
                    "gross_value_gap":
                        "second_gap",
                    "trade_executed":
                        "second_trade",
                    "net_pnl":
                        "second_pnl",
                    "contract_key":
                        "second_contract",
                }
            )

            paired = first.merge(
                second,
                on="target_date",
                how="inner",
                validate="one_to_one",
            )

            if paired.empty:
                continue

            def correlation(
                left: pd.Series,
                right: pd.Series,
            ) -> float:
                if (
                    left.nunique()
                    < 2
                    or right.nunique()
                    < 2
                ):
                    return np.nan

                return float(
                    left.corr(
                        right
                    )
                )

            both_trade = (
                paired[
                    "first_trade"
                ].astype(bool)
                & paired[
                    "second_trade"
                ].astype(bool)
            )

            either_trade = (
                paired[
                    "first_trade"
                ].astype(bool)
                | paired[
                    "second_trade"
                ].astype(bool)
            )

            rows.append(
                {
                    "sample_period":
                        sample_period,
                    "first_decision_rule":
                        first_rule,
                    "second_decision_rule":
                        second_rule,
                    "overlapping_dates":
                        len(
                            paired
                        ),
                    "value_gap_correlation":
                        correlation(
                            paired[
                                "first_gap"
                            ],
                            paired[
                                "second_gap"
                            ],
                        ),
                    "trade_signal_correlation":
                        correlation(
                            paired[
                                "first_trade"
                            ].astype(float),
                            paired[
                                "second_trade"
                            ].astype(float),
                        ),
                    "net_pnl_correlation":
                        correlation(
                            paired[
                                "first_pnl"
                            ],
                            paired[
                                "second_pnl"
                            ],
                        ),
                    "same_candidate_contract_fraction":
                        float(
                            paired[
                                "first_contract"
                            ].astype(str)
                            .eq(
                                paired[
                                    "second_contract"
                                ].astype(str)
                            )
                            .mean()
                        ),
                    "both_trade_fraction":
                        float(
                            both_trade.mean()
                        ),
                    "either_trade_fraction":
                        float(
                            either_trade.mean()
                        ),
                    "same_contract_when_both_trade_fraction":
                        (
                            float(
                                paired.loc[
                                    both_trade,
                                    "first_contract",
                                ]
                                .astype(str)
                                .eq(
                                    paired.loc[
                                        both_trade,
                                        "second_contract",
                                    ].astype(str)
                                )
                                .mean()
                            )
                            if both_trade.any()
                            else np.nan
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


def strategy_surface(
    candidates: pd.DataFrame,
    thresholds: np.ndarray,
    reference_cost: float,
    sample_period: str,
    rules: list[str],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    dates = sorted(
        candidates.loc[
            candidates[
                "sample_period"
            ].eq(
                sample_period
            ),
            "target_date",
        ].unique()
    )

    date_index = pd.Index(
        dates,
        name="target_date",
    )

    columns: dict[
        str,
        pd.Series,
    ] = {}

    summary_rows: list[
        dict[str, Any]
    ] = []

    for rule in rules:
        rule_panel = candidates.loc[
            candidates[
                "sample_period"
            ].eq(
                sample_period
            )
            & candidates[
                "decision_rule"
            ].eq(
                rule
            )
        ]

        for threshold in thresholds:
            evaluated = evaluate_strategy(
                rule_panel,
                float(
                    threshold
                ),
                reference_cost,
            )

            strategy_id = (
                rule
                + "|threshold="
                + f"{float(threshold):.3f}"
            )

            date_returns = (
                evaluated.set_index(
                    "target_date"
                )[
                    "net_pnl"
                ]
                .reindex(
                    date_index,
                    fill_value=0.0,
                )
                .astype(float)
            )

            columns[
                strategy_id
            ] = date_returns

            summary_rows.append(
                {
                    "sample_period":
                        sample_period,
                    "strategy_id":
                        strategy_id,
                    "decision_rule":
                        rule,
                    "threshold":
                        float(
                            threshold
                        ),
                    "calendar_dates":
                        len(
                            date_index
                        ),
                    "available_rule_dates":
                        evaluated[
                            "target_date"
                        ].nunique(),
                    "trade_count":
                        int(
                            evaluated[
                                "trade_executed"
                            ].sum()
                        ),
                    "total_net_pnl_calendar":
                        float(
                            date_returns.sum()
                        ),
                    "mean_date_net_pnl_calendar":
                        float(
                            date_returns.mean()
                        ),
                    "standard_error_calendar":
                        float(
                            date_returns.std(
                                ddof=1
                            )
                            / math.sqrt(
                                len(
                                    date_returns
                                )
                            )
                        )
                        if len(
                            date_returns
                        ) > 1
                        else 0.0,
                }
            )

    matrix = pd.DataFrame(
        columns,
        index=date_index,
    )

    return (
        pd.DataFrame(
            summary_rows
        ),
        matrix,
    )


def multiple_strategy_adjustment(
    training_surface: pd.DataFrame,
    training_matrix: pd.DataFrame,
    frozen_selection: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    adjustment = specification[
        "multiple_strategy_adjustment"
    ]

    repetitions = int(
        adjustment[
            "bootstrap_repetitions"
        ]
    )

    confidence_level = float(
        adjustment[
            "confidence_level"
        ]
    )

    seed = int(
        adjustment[
            "bootstrap_seed"
        ]
    )

    observed_means = (
        training_matrix.mean(
            axis=0
        )
    )

    best_strategy_id = str(
        observed_means.idxmax()
    )

    observed_maximum_mean = float(
        observed_means.max()
    )

    centred = (
        training_matrix
        - observed_means
    ).to_numpy(
        dtype=float
    )

    number_of_dates = centred.shape[0]

    rng = np.random.default_rng(
        seed
    )

    batch_size = 250
    bootstrap_maxima: list[
        np.ndarray
    ] = []

    completed = 0

    while completed < repetitions:
        current_batch = min(
            batch_size,
            repetitions
            - completed,
        )

        indices = rng.integers(
            0,
            number_of_dates,
            size=(
                current_batch,
                number_of_dates,
            ),
        )

        sampled = centred[
            indices,
            :
        ].mean(
            axis=1
        )

        bootstrap_maxima.append(
            sampled.max(
                axis=1
            )
        )

        completed += current_batch

    maximum_distribution = np.concatenate(
        bootstrap_maxima
    )

    p_value = float(
        (
            1
            + np.sum(
                maximum_distribution
                >= observed_maximum_mean
            )
        )
        / (
            repetitions + 1
        )
    )

    critical_value = float(
        np.quantile(
            maximum_distribution,
            confidence_level,
        )
    )

    primary = frozen_selection.loc[
        boolean_series(
            frozen_selection[
                "selected_primary_decision_rule"
            ]
        )
    ].iloc[0]

    frozen_strategy_id = (
        str(
            primary[
                "decision_rule"
            ]
        )
        + "|threshold="
        + f"{float(primary['selected_threshold']):.3f}"
    )

    if frozen_strategy_id not in training_matrix.columns:
        raise RuntimeError(
            "The frozen Phase 11 primary strategy is "
            "missing from the multiple-strategy matrix."
        )

    frozen_mean = float(
        training_matrix[
            frozen_strategy_id
        ].mean()
    )

    centred_frozen = (
        training_matrix[
            frozen_strategy_id
        ]
        - frozen_mean
    ).to_numpy(
        dtype=float
    )

    frozen_bootstrap_means: list[
        np.ndarray
    ] = []

    rng_frozen = np.random.default_rng(
        seed + 8191
    )

    completed = 0

    while completed < repetitions:
        current_batch = min(
            1000,
            repetitions
            - completed,
        )

        indices = rng_frozen.integers(
            0,
            number_of_dates,
            size=(
                current_batch,
                number_of_dates,
            ),
        )

        frozen_bootstrap_means.append(
            centred_frozen[
                indices
            ].mean(
                axis=1
            )
        )

        completed += current_batch

    frozen_distribution = np.concatenate(
        frozen_bootstrap_means
    )

    frozen_unadjusted_p_value = float(
        (
            1
            + np.sum(
                frozen_distribution
                >= frozen_mean
            )
        )
        / (
            repetitions + 1
        )
    )

    best_row = training_surface.loc[
        training_surface[
            "strategy_id"
        ].eq(
            best_strategy_id
        )
    ].iloc[0]

    frozen_row = training_surface.loc[
        training_surface[
            "strategy_id"
        ].eq(
            frozen_strategy_id
        )
    ].iloc[0]

    return pd.DataFrame(
        [
            {
                "candidate_strategies":
                    training_matrix.shape[1],
                "training_calendar_dates":
                    training_matrix.shape[0],
                "best_observed_strategy_id":
                    best_strategy_id,
                "best_observed_decision_rule":
                    best_row[
                        "decision_rule"
                    ],
                "best_observed_threshold":
                    float(
                        best_row[
                            "threshold"
                        ]
                    ),
                "best_observed_mean_date_pnl":
                    observed_maximum_mean,
                "multiple_strategy_bootstrap_critical_value":
                    critical_value,
                "multiple_strategy_adjusted_p_value":
                    p_value,
                "frozen_primary_strategy_id":
                    frozen_strategy_id,
                "frozen_primary_mean_date_pnl":
                    frozen_mean,
                "frozen_primary_unadjusted_p_value":
                    frozen_unadjusted_p_value,
                "frozen_primary_training_trade_count":
                    int(
                        frozen_row[
                            "trade_count"
                        ]
                    ),
                "selection_adjusted_evidence_positive":
                    bool(
                        observed_maximum_mean
                        > critical_value
                    ),
            }
        ]
    )


def june_ex_post_surface(
    surface: pd.DataFrame,
    frozen_selection: pd.DataFrame,
) -> pd.DataFrame:
    result = surface.copy()

    primary = frozen_selection.loc[
        boolean_series(
            frozen_selection[
                "selected_primary_decision_rule"
            ]
        )
    ].iloc[0]

    frozen_id = (
        str(
            primary[
                "decision_rule"
            ]
        )
        + "|threshold="
        + f"{float(primary['selected_threshold']):.3f}"
    )

    result[
        "is_phase11_frozen_primary"
    ] = result[
        "strategy_id"
    ].eq(
        frozen_id
    )

    result[
        "ex_post_rank_by_june_mean_pnl"
    ] = result[
        "mean_date_net_pnl_calendar"
    ].rank(
        ascending=False,
        method="min",
    ).astype(int)

    result[
        "diagnostic_only_not_used_for_selection"
    ] = True

    return result.sort_values(
        "ex_post_rank_by_june_mean_pnl",
        kind="stable",
    ).reset_index(
        drop=True
    )


def create_figures(
    output_directory: Path,
    neighbourhood: pd.DataFrame,
    loo_paths: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    trade_contributions: pd.DataFrame,
    frozen_selection: pd.DataFrame,
    specification: dict[str, Any],
) -> list[str]:
    figure_files: list[
        str
    ] = []

    primary_rule = frozen_selection.loc[
        boolean_series(
            frozen_selection[
                "selected_primary_decision_rule"
            ]
        ),
        "decision_rule",
    ].iloc[0]

    june_neighbourhood = neighbourhood.loc[
        neighbourhood[
            "decision_rule"
        ].eq(
            primary_rule
        )
        & neighbourhood[
            "sample_period"
        ].eq(
            specification[
                "sample_periods"
            ][
                "out_of_sample_validation"
            ]
        )
    ].sort_values(
        "threshold"
    )

    figure_name = (
        "phase12_primary_threshold_neighbourhood.png"
    )

    figure, axis = plt.subplots(
        figsize=(
            8.5,
            5.5,
        )
    )

    axis.plot(
        june_neighbourhood[
            "threshold"
        ],
        june_neighbourhood[
            "total_net_pnl"
        ],
        marker="o",
    )

    frozen_threshold = float(
        frozen_selection.loc[
            frozen_selection[
                "decision_rule"
            ].eq(
                primary_rule
            ),
            "selected_threshold",
        ].iloc[0]
    )

    axis.axvline(
        frozen_threshold,
        linestyle="--",
        label="Frozen Phase 11 threshold",
    )

    axis.axhline(
        0.0,
        linestyle="--",
    )

    axis.set_xlabel(
        "Value-gap threshold"
    )

    axis.set_ylabel(
        "June total net PnL"
    )

    axis.set_title(
        "June threshold neighbourhood: "
        + str(
            primary_rule
        )
    )

    axis.legend()
    figure.tight_layout()

    figure.savefig(
        output_directory
        / figure_name,
        dpi=180,
    )

    plt.close(
        figure
    )

    figure_files.append(
        figure_name
    )

    figure_name = (
        "phase12_leave_one_date_out_thresholds.png"
    )

    figure, axis = plt.subplots(
        figsize=(
            9.0,
            6.0,
        )
    )

    rules = specification[
        "decision_rules"
    ]

    positions = np.arange(
        len(
            rules
        )
    )

    data = [
        loo_paths.loc[
            loo_paths[
                "decision_rule"
            ].eq(
                rule
            ),
            "selected_threshold",
        ].to_numpy(
            dtype=float
        )
        for rule in rules
    ]

    axis.boxplot(
        data,
        labels=rules,
    )

    for position, rule in zip(
        positions,
        rules,
    ):
        threshold = float(
            frozen_selection.loc[
                frozen_selection[
                    "decision_rule"
                ].eq(
                    rule
                ),
                "selected_threshold",
            ].iloc[0]
        )

        axis.scatter(
            [
                position + 1
            ],
            [
                threshold
            ],
            s=70,
            label=(
                "Full-sample threshold"
                if position == 0
                else None
            ),
        )

    axis.set_ylabel(
        "Selected threshold"
    )

    axis.set_title(
        "Leave-one-date-out threshold stability"
    )

    axis.legend()
    figure.tight_layout()

    figure.savefig(
        output_directory
        / figure_name,
        dpi=180,
    )

    plt.close(
        figure
    )

    figure_files.append(
        figure_name
    )

    june_costs = cost_sensitivity.loc[
        cost_sensitivity[
            "sample_period"
        ].eq(
            specification[
                "sample_periods"
            ][
                "out_of_sample_validation"
            ]
        )
    ].sort_values(
        "transaction_cost_per_share"
    )

    figure_name = (
        "phase12_primary_fine_cost_sensitivity.png"
    )

    figure, axis = plt.subplots(
        figsize=(
            8.5,
            5.5,
        )
    )

    axis.plot(
        june_costs[
            "transaction_cost_per_share"
        ],
        june_costs[
            "total_net_pnl"
        ],
        marker="o",
    )

    axis.axhline(
        0.0,
        linestyle="--",
    )

    break_even = float(
        june_costs[
            "analytical_break_even_cost"
        ].iloc[0]
    )

    if np.isfinite(
        break_even
    ):
        axis.axvline(
            break_even,
            linestyle="--",
            label=(
                "Analytical break-even cost"
            ),
        )

    axis.set_xlabel(
        "Transaction cost per share"
    )

    axis.set_ylabel(
        "June total net PnL"
    )

    axis.set_title(
        "Frozen primary strategy cost sensitivity"
    )

    axis.legend()
    figure.tight_layout()

    figure.savefig(
        output_directory
        / figure_name,
        dpi=180,
    )

    plt.close(
        figure
    )

    figure_files.append(
        figure_name
    )

    figure_name = (
        "phase12_june_trade_contributions.png"
    )

    ordered = trade_contributions.sort_values(
        "target_date",
        kind="stable",
    )

    figure, axis = plt.subplots(
        figsize=(
            10.0,
            5.8,
        )
    )

    axis.bar(
        ordered[
            "target_date"
        ].dt.strftime(
            "%d-%b"
        ),
        ordered[
            "net_pnl"
        ],
    )

    axis.axhline(
        0.0,
        linestyle="--",
    )

    axis.set_xlabel(
        "June trade date"
    )

    axis.set_ylabel(
        "Net PnL"
    )

    axis.set_title(
        "Frozen primary strategy trade contributions"
    )

    axis.tick_params(
        axis="x",
        rotation=60,
    )

    figure.tight_layout()

    figure.savefig(
        output_directory
        / figure_name,
        dpi=180,
    )

    plt.close(
        figure
    )

    figure_files.append(
        figure_name
    )

    return figure_files


def atomic_replace_directory(
    staged: Path,
    target: Path,
) -> None:
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if target.exists():
        shutil.rmtree(
            target
        )

    shutil.move(
        str(staged),
        str(target),
    )


def main() -> None:
    specification = load_json(
        SPEC_PATH
    )

    input_paths = {
        name:
            ROOT / relative_path
        for name, relative_path
        in specification[
            "inputs"
        ].items()
    }

    phase11_manifest = load_json(
        input_paths[
            "phase11_manifest"
        ]
    )

    if phase11_manifest.get(
        "status"
    ) != "passed":
        raise RuntimeError(
            "Phase 11 manifest does not report passed."
        )

    candidates = pd.read_csv(
        input_paths[
            "phase11_candidates"
        ],
        low_memory=False,
    )

    phase11_grid = pd.read_csv(
        input_paths[
            "phase11_training_grid"
        ],
        low_memory=False,
    )

    frozen_selection = pd.read_csv(
        input_paths[
            "phase11_selection"
        ],
        low_memory=False,
    )

    phase11_performance = pd.read_csv(
        input_paths[
            "phase11_performance"
        ],
        low_memory=False,
    )

    phase10_paired = pd.read_csv(
        input_paths[
            "phase10_paired_summary"
        ],
        low_memory=False,
    )

    phase9_scores = pd.read_csv(
        input_paths[
            "phase9_score_summary"
        ],
        low_memory=False,
    )

    candidates[
        "target_date"
    ] = parse_dates(
        candidates[
            "target_date"
        ]
    )

    required_candidate_columns = {
        "target_date",
        "decision_rule",
        "contract_key",
        "event_label",
        "lower_bound_c",
        "upper_bound_c",
        "gp_event_probability",
        "market_probability_raw",
        "realised_yes",
        "sample_period",
        "gross_value_gap",
    }

    missing_candidate_columns = (
        required_candidate_columns
        - set(
            candidates.columns
        )
    )

    if missing_candidate_columns:
        raise RuntimeError(
            "Phase 11 candidate panel is missing: "
            + ", ".join(
                sorted(
                    missing_candidate_columns
                )
            )
        )

    numeric_candidate_columns = [
        "lower_bound_c",
        "upper_bound_c",
        "gp_event_probability",
        "market_probability_raw",
        "realised_yes",
        "gross_value_gap",
    ]

    for column in numeric_candidate_columns:
        candidates[
            column
        ] = pd.to_numeric(
            candidates[
                column
            ],
            errors="raise",
        ).astype(
            float
        )

    if candidates[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "The Phase 11 candidate panel contains "
            "duplicate date-rule books."
        )

    primary_flags = boolean_series(
        frozen_selection[
            "selected_primary_decision_rule"
        ]
    )

    if int(
        primary_flags.sum()
    ) != 1:
        raise RuntimeError(
            "Phase 11 does not contain exactly one "
            "primary decision rule."
        )

    frozen_primary_rule = str(
        frozen_selection.loc[
            primary_flags,
            "decision_rule",
        ].iloc[0]
    )

    frozen_primary_threshold = float(
        frozen_selection.loc[
            primary_flags,
            "selected_threshold",
        ].iloc[0]
    )

    if (
        frozen_primary_rule
        != phase11_manifest[
            "strategy"
        ][
            "primary_decision_rule"
        ]
        or not math.isclose(
            frozen_primary_threshold,
            float(
                phase11_manifest[
                    "strategy"
                ][
                    "primary_frozen_threshold"
                ]
            ),
            abs_tol=1e-12,
            rel_tol=0.0,
        )
    ):
        raise RuntimeError(
            "Phase 11 selection and manifest disagree."
        )

    thresholds = np.sort(
        pd.to_numeric(
            phase11_grid[
                "threshold"
            ],
            errors="raise",
        ).unique()
    )

    reference_cost = float(
        specification[
            "robustness"
        ][
            "reference_transaction_cost"
        ]
    )

    reproduced_grid = build_threshold_grid(
        candidates,
        thresholds,
        reference_cost,
        specification[
            "sample_periods"
        ][
            "strategy_selection"
        ],
        specification[
            "decision_rules"
        ],
    )

    reproduced_selection = select_from_grid(
        reproduced_grid,
        specification[
            "decision_rules"
        ],
        int(
            specification[
                "robustness"
            ][
                "minimum_training_trades"
            ]
        ),
    )

    comparison = frozen_selection[
        [
            "decision_rule",
            "selected_threshold",
        ]
    ].merge(
        reproduced_selection[
            [
                "decision_rule",
                "selected_threshold",
            ]
        ],
        on="decision_rule",
        suffixes=(
            "_phase11",
            "_reproduced",
        ),
        validate="one_to_one",
    )

    if not np.isclose(
        comparison[
            "selected_threshold_phase11"
        ],
        comparison[
            "selected_threshold_reproduced"
        ],
        atol=1e-12,
        rtol=0.0,
    ).all():
        raise RuntimeError(
            "Phase 12 could not reproduce the Phase 11 "
            "frozen thresholds."
        )

    reproduced_primary = reproduced_selection.loc[
        reproduced_selection[
            "selected_primary_decision_rule"
        ],
        "decision_rule",
    ].iloc[0]

    if reproduced_primary != frozen_primary_rule:
        raise RuntimeError(
            "Phase 12 could not reproduce the Phase 11 "
            "primary decision rule."
        )

    neighbourhood = threshold_neighbourhood(
        candidates,
        frozen_selection,
        specification,
    )

    (
        loo_paths,
        loo_summary,
    ) = leave_one_date_out_selection(
        candidates,
        thresholds,
        frozen_selection,
        specification,
    )

    cost_sensitivity = fine_cost_sensitivity(
        candidates,
        frozen_selection,
        specification,
    )

    (
        primary_evaluated,
        temperature_cutoffs,
    ) = primary_trade_panel(
        candidates,
        frozen_selection,
        specification,
    )

    event_type_attribution = (
        attribution_summary(
            primary_evaluated,
            "event_type_attribution",
        )
    )

    temperature_attribution = (
        attribution_summary(
            primary_evaluated,
            "temperature_bucket",
        )
    )

    (
        trade_contributions,
        trade_concentration,
    ) = trade_contribution_analysis(
        primary_evaluated,
        specification,
    )

    dependence = decision_rule_dependence(
        candidates,
        frozen_selection,
        specification,
    )

    training_surface, training_matrix = (
        strategy_surface(
            candidates,
            thresholds,
            reference_cost,
            specification[
                "sample_periods"
            ][
                "strategy_selection"
            ],
            specification[
                "decision_rules"
            ],
        )
    )

    selection_adjustment = (
        multiple_strategy_adjustment(
            training_surface,
            training_matrix,
            frozen_selection,
            specification,
        )
    )

    june_surface, _ = strategy_surface(
        candidates,
        thresholds,
        reference_cost,
        specification[
            "sample_periods"
        ][
            "out_of_sample_validation"
        ],
        specification[
            "decision_rules"
        ],
    )

    june_surface = june_ex_post_surface(
        june_surface,
        frozen_selection,
    )

    output_target = (
        ROOT
        / specification[
            "output_directory"
        ]
    )

    stage_root = Path(
        tempfile.mkdtemp(
            prefix="phase12_robustness_"
        )
    )

    stage_output = (
        stage_root
        / "phase12_robustness_attribution"
    )

    stage_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        neighbourhood.to_csv(
            stage_output
            / "phase12_threshold_neighbourhood.csv",
            index=False,
        )

        loo_paths.to_csv(
            stage_output
            / "phase12_leave_one_date_out_selection_paths.csv",
            index=False,
        )

        loo_summary.to_csv(
            stage_output
            / "phase12_leave_one_date_out_selection_summary.csv",
            index=False,
        )

        cost_sensitivity.to_csv(
            stage_output
            / "phase12_fine_transaction_cost_sensitivity.csv",
            index=False,
        )

        primary_evaluated.to_csv(
            stage_output
            / "phase12_primary_strategy_attribution_panel.csv",
            index=False,
        )

        event_type_attribution.to_csv(
            stage_output
            / "phase12_event_type_attribution.csv",
            index=False,
        )

        temperature_attribution.to_csv(
            stage_output
            / "phase12_temperature_bucket_attribution.csv",
            index=False,
        )

        trade_contributions.to_csv(
            stage_output
            / "phase12_june_trade_contributions.csv",
            index=False,
        )

        trade_concentration.to_csv(
            stage_output
            / "phase12_june_trade_concentration_summary.csv",
            index=False,
        )

        dependence.to_csv(
            stage_output
            / "phase12_decision_rule_dependence.csv",
            index=False,
        )

        training_surface.to_csv(
            stage_output
            / "phase12_training_strategy_surface.csv",
            index=False,
        )

        selection_adjustment.to_csv(
            stage_output
            / "phase12_multiple_strategy_adjustment.csv",
            index=False,
        )

        june_surface.to_csv(
            stage_output
            / "phase12_june_ex_post_strategy_surface.csv",
            index=False,
        )

        figure_files = create_figures(
            stage_output,
            neighbourhood,
            loo_paths,
            cost_sensitivity,
            trade_contributions,
            frozen_selection,
            specification,
        )

        primary_loo = loo_summary.loc[
            loo_summary[
                "decision_rule"
            ].eq(
                frozen_primary_rule
            )
        ].iloc[0]

        june_costs = cost_sensitivity.loc[
            cost_sensitivity[
                "sample_period"
            ].eq(
                specification[
                    "sample_periods"
                ][
                    "out_of_sample_validation"
                ]
            )
        ].sort_values(
            "transaction_cost_per_share"
        )

        june_break_even_cost = float(
            june_costs[
                "analytical_break_even_cost"
            ].iloc[0]
        )

        reference_june = june_costs.loc[
            np.isclose(
                june_costs[
                    "transaction_cost_per_share"
                ],
                reference_cost,
                atol=1e-12,
                rtol=0.0,
            )
        ].iloc[0]

        concentration = (
            trade_concentration.iloc[0]
        )

        adjustment = (
            selection_adjustment.iloc[0]
        )

        frozen_june_surface = (
            june_surface.loc[
                june_surface[
                    "is_phase11_frozen_primary"
                ]
            ].iloc[0]
        )

        june_phase10 = phase10_paired.loc[
            phase10_paired[
                "sample_period"
            ].eq(
                "out_of_sample_validation"
            )
            & phase10_paired[
                "decision_rule"
            ].eq(
                "all_rules"
            )
            & phase10_paired[
                "metric"
            ].isin(
                [
                    "binary_brier_raw",
                    "binary_log_raw",
                    "categorical_log",
                    "multiclass_brier",
                ]
            )
        ].copy()

        phase9_june = phase9_scores.loc[
            phase9_scores[
                "sample_period"
            ].eq(
                "out_of_sample_validation"
            )
            & phase9_scores[
                "decision_rule"
            ].eq(
                "all_rules"
            )
        ].copy()

        primary_rule_reselection_fraction = float(
            primary_loo[
                "full_primary_rule_reselected_fraction"
            ]
        )

        threshold_reselection_fraction = float(
            primary_loo[
                "frozen_threshold_reselection_fraction"
            ]
        )

        manifest = {
            "phase": 12,
            "status": "passed",
            "frozen_strategy": {
                "decision_rule":
                    frozen_primary_rule,
                "threshold":
                    frozen_primary_threshold,
                "reference_transaction_cost":
                    reference_cost,
                "altered_in_phase12":
                    False,
            },
            "robustness": {
                "training_dates_omitted_individually":
                    int(
                        loo_paths[
                            "omitted_target_date"
                        ].nunique()
                    ),
                "primary_threshold_reselection_fraction":
                    threshold_reselection_fraction,
                "primary_rule_reselection_fraction":
                    primary_rule_reselection_fraction,
                "primary_threshold_leave_one_out_minimum":
                    float(
                        primary_loo[
                            "minimum_leave_one_out_threshold"
                        ]
                    ),
                "primary_threshold_leave_one_out_maximum":
                    float(
                        primary_loo[
                            "maximum_leave_one_out_threshold"
                        ]
                    ),
                "june_analytical_break_even_cost":
                    june_break_even_cost,
            },
            "trade_concentration": {
                "june_trade_count":
                    int(
                        concentration[
                            "trade_count"
                        ]
                    ),
                "winning_trades":
                    int(
                        concentration[
                            "winning_trades"
                        ]
                    ),
                "largest_positive_contribution_share":
                    float(
                        concentration[
                            "largest_positive_contribution_share"
                        ]
                    ),
                "largest_absolute_contribution_share":
                    float(
                        concentration[
                            "largest_absolute_contribution_share"
                        ]
                    ),
                "absolute_pnl_herfindahl":
                    float(
                        concentration[
                            "absolute_pnl_herfindahl"
                        ]
                    ),
                "positive_without_best_trade":
                    bool(
                        concentration[
                            "positive_without_best_trade"
                        ]
                    ),
            },
            "multiple_strategy_adjustment": {
                "candidate_strategies":
                    int(
                        adjustment[
                            "candidate_strategies"
                        ]
                    ),
                "best_observed_strategy":
                    str(
                        adjustment[
                            "best_observed_strategy_id"
                        ]
                    ),
                "best_observed_mean_date_pnl":
                    float(
                        adjustment[
                            "best_observed_mean_date_pnl"
                        ]
                    ),
                "adjusted_p_value":
                    float(
                        adjustment[
                            "multiple_strategy_adjusted_p_value"
                        ]
                    ),
                "selection_adjusted_evidence_positive":
                    bool(
                        adjustment[
                            "selection_adjusted_evidence_positive"
                        ]
                    ),
            },
            "june_primary_result": {
                "dates":
                    int(
                        reference_june[
                            "dates"
                        ]
                    ),
                "trades":
                    int(
                        reference_june[
                            "trade_count"
                        ]
                    ),
                "total_net_pnl":
                    float(
                        reference_june[
                            "total_net_pnl"
                        ]
                    ),
                "return_on_committed_capital":
                    float(
                        reference_june[
                            "return_on_committed_capital"
                        ]
                    ),
                "maximum_drawdown":
                    float(
                        reference_june[
                            "maximum_drawdown"
                        ]
                    ),
                "ex_post_rank_among_rule_threshold_candidates":
                    int(
                        frozen_june_surface[
                            "ex_post_rank_by_june_mean_pnl"
                        ]
                    ),
                "ex_post_candidate_strategies":
                    int(
                        len(
                            june_surface
                        )
                    ),
            },
            "temperature_bucket_cutoffs": {
                key:
                    float(value)
                for key, value
                in temperature_cutoffs.items()
            },
            "inputs": {
                name: {
                    "path":
                        str(
                            path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            path
                        ),
                }
                for name, path
                in input_paths.items()
            },
            "figures":
                figure_files,
            "restrictions":
                specification[
                    "restrictions"
                ],
        }

        (
            stage_output
            / "phase12_manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        phase10_lines = [
            "| Metric | GP | Polymarket | GP minus market | 95% bootstrap interval |",
            "|---|---:|---:|---:|---:|",
        ]

        for _, row in june_phase10.iterrows():
            phase10_lines.append(
                "| "
                + str(
                    row[
                        "metric_label"
                    ]
                )
                + " | "
                + f"{row['mean_gp_score']:.6f}"
                + " | "
                + f"{row['mean_market_score']:.6f}"
                + " | "
                + f"{row['mean_difference_gp_minus_market']:.6f}"
                + " | ["
                + f"{row['bootstrap_ci_lower']:.6f}"
                + ", "
                + f"{row['bootstrap_ci_upper']:.6f}"
                + "] |"
            )

        loo_lines = [
            "| Decision rule | Frozen threshold | LODO minimum | LODO maximum | Same-threshold fraction | Primary-rule fraction |",
            "|---|---:|---:|---:|---:|---:|",
        ]

        for _, row in loo_summary.iterrows():
            loo_lines.append(
                "| "
                + str(
                    row[
                        "decision_rule"
                    ]
                )
                + " | "
                + f"{row['full_sample_frozen_threshold']:.3f}"
                + " | "
                + f"{row['minimum_leave_one_out_threshold']:.3f}"
                + " | "
                + f"{row['maximum_leave_one_out_threshold']:.3f}"
                + " | "
                + f"{row['frozen_threshold_reselection_fraction']:.3f}"
                + " | "
                + f"{row['rule_selected_primary_fraction']:.3f}"
                + " |"
            )

        cost_lines = [
            "| Cost | Trades | Total net PnL | Return on capital | Maximum drawdown |",
            "|---:|---:|---:|---:|---:|",
        ]

        for _, row in june_costs.iterrows():
            cost_lines.append(
                "| "
                + f"{row['transaction_cost_per_share']:.4f}"
                + " | "
                + str(
                    int(
                        row[
                            "trade_count"
                        ]
                    )
                )
                + " | "
                + f"{row['total_net_pnl']:.6f}"
                + " | "
                + f"{row['return_on_committed_capital']:.6f}"
                + " | "
                + f"{row['maximum_drawdown']:.6f}"
                + " |"
            )

        phase9_text = ""

        if not phase9_june.empty:
            row = phase9_june.iloc[0]

            phase9_text = f"""
The standalone June GP evaluation produced:

- Mean binary Brier score:
  {row['mean_binary_brier']:.6f}.
- Mean binary log score:
  {row['mean_binary_log']:.6f}.
- Mean categorical log score:
  {row['mean_categorical_log']:.6f}.
- Mean multiclass Brier score:
  {row['mean_multiclass_brier']:.6f}.
- Mean continuous CRPS:
  {row['mean_continuous_crps_c']:.6f} degrees Celsius.
- Mean GP absolute error:
  {row['mean_gp_absolute_error_c']:.6f} degrees Celsius.
"""

        report = f"""# Phase 12 Robustness, Attribution and Final Empirical Synthesis

## Status

PASSED

## Evidential design

Phase 12 does not alter the Phase 11 strategy. The primary decision rule
remains `{frozen_primary_rule}`, the value-gap threshold remains
{frozen_primary_threshold:.3f}, and the reference transaction cost
remains {reference_cost:.3f} per Yes share.

All threshold and rule-selection robustness exercises use only the
March-May strategy-selection period. June is used only for evaluation,
attribution and explicitly labelled post-hoc sensitivity analysis.

## Reproduction of Phase 11

The Phase 11 threshold grid and one-standard-error selection procedure
were reproduced from the saved candidate contract panel. All four
frozen thresholds and the primary decision rule were recovered exactly.

## Leave-one-date-out selection stability

Each March-May target date was omitted in turn. Thresholds and the
primary decision rule were then reselected from the remaining dates.

{chr(10).join(loo_lines)}

For the frozen primary rule:

- Fraction of omissions that reproduced the exact frozen threshold:
  {threshold_reselection_fraction:.3f}.
- Fraction of omissions that retained the same primary decision rule:
  {primary_rule_reselection_fraction:.3f}.
- Leave-one-date-out threshold range:
  [{primary_loo['minimum_leave_one_out_threshold']:.3f},
   {primary_loo['maximum_leave_one_out_threshold']:.3f}].

These diagnostics quantify how strongly the selected specification
depends on individual March-May dates.

## Multiple-strategy adjustment

The search considered
{int(adjustment['candidate_strategies'])}
rule-threshold strategies. Dates were resampled jointly across all
strategies after each strategy return series had been centred, thereby
preserving cross-strategy dependence.

- Best observed training strategy:
  `{adjustment['best_observed_strategy_id']}`.
- Best observed mean date PnL:
  {adjustment['best_observed_mean_date_pnl']:.6f}.
- Selection-adjusted bootstrap critical value:
  {adjustment['multiple_strategy_bootstrap_critical_value']:.6f}.
- Selection-adjusted p-value:
  {adjustment['multiple_strategy_adjusted_p_value']:.4f}.
- Selection-adjusted evidence of a positive strategy mean:
  {'yes' if bool(adjustment['selection_adjusted_evidence_positive']) else 'no'}.

This adjustment addresses the optimism created by examining multiple
decision rules and thresholds before selecting one strategy.

## June cost robustness

The frozen primary strategy has an analytical June break-even
transaction cost of approximately
{june_break_even_cost:.6f}
per share.

{chr(10).join(cost_lines)}

The strategy therefore has only a narrow cost margin. Its sign changes
once transaction costs exceed the realised gross profit per trade.

## June trade concentration

At the reference cost:

- Trades:
  {int(concentration['trade_count'])}.
- Winning trades:
  {int(concentration['winning_trades'])}.
- Losing trades:
  {int(concentration['losing_trades'])}.
- Largest winning trade:
  {concentration['largest_winning_trade']:.6f}.
- Largest losing trade:
  {concentration['largest_losing_trade']:.6f}.
- Largest positive contribution as a share of all positive PnL:
  {concentration['largest_positive_contribution_share']:.4f}.
- Largest absolute contribution share:
  {concentration['largest_absolute_contribution_share']:.4f}.
- Absolute-PnL Herfindahl index:
  {concentration['absolute_pnl_herfindahl']:.4f}.
- Total PnL remains positive after removing the best trade:
  {'yes' if bool(concentration['positive_without_best_trade']) else 'no'}.

The concentration diagnostics are essential because an infrequent
long-Yes strategy can show a positive aggregate result despite most
individual trades losing.

## Event and temperature attribution

Event-type attribution separates lower-tail, interior and upper-tail
contracts. Temperature attribution uses March-May observed-temperature
terciles fixed before June:

- Cool to middle boundary:
  {temperature_cutoffs['training_lower_tercile_c']:.4f} degrees Celsius.
- Middle to hot boundary:
  {temperature_cutoffs['training_upper_tercile_c']:.4f} degrees Celsius.

The complete group-level results are recorded in
`phase12_event_type_attribution.csv` and
`phase12_temperature_bucket_attribution.csv`.

## Dependence across decision rules

The pairwise audit records value-gap correlations, trade-signal
correlations, PnL correlations, simultaneous-trade frequencies and the
frequency with which two decision rules select the same contract.

These results must not be interpreted as four independent strategy
experiments. Forecasts, contract books and realised temperatures are
shared across rules, creating substantial dependence.

## June proper-score comparison

On the 30-date June exact common support, the Phase 10 paired results
were:

{chr(10).join(phase10_lines)}

All reported differences are GP score minus Polymarket score. Positive
differences therefore favour Polymarket.
{phase9_text}
## Frozen June trading result

At the reference cost of {reference_cost:.3f} per share:

- Dates:
  {int(reference_june['dates'])}.
- Trades:
  {int(reference_june['trade_count'])}.
- Total net PnL:
  {reference_june['total_net_pnl']:.6f}.
- Mean date net PnL:
  {reference_june['mean_date_net_pnl']:.6f}.
- Return on committed capital:
  {reference_june['return_on_committed_capital']:.6f}.
- Maximum drawdown:
  {reference_june['maximum_drawdown']:.6f}.
- Post-hoc June rank among the
  {len(june_surface)}
  rule-threshold candidates:
  {int(frozen_june_surface['ex_post_rank_by_june_mean_pnl'])}.

The post-hoc rank is diagnostic only. It was not used to replace,
retune or improve the frozen Phase 11 strategy.

## Final empirical synthesis

The two-year weather-only residual sample allowed a materially more
credible GP construction than the original short-sample Gaussian
bridge. The Matérn 3/2 GP produced coherent full predictive
distributions and exact contract-event probabilities.

Nevertheless, June Polymarket prices achieved lower binary and
categorical proper scores on the exact complete-book intersection.
This indicates that the market incorporated information not captured
by the deterministic forecast and weather-only GP post-processing.

The frozen value-gap strategy produced a slightly positive June point
estimate at the reference cost, but the result was economically small,
highly uncertain, cost-sensitive and concentrated in infrequent
winning contracts. Threshold instability, multiple-strategy searching
and dependence across decision rules further weaken any claim of a
persistent trading advantage.

The defensible conclusion is therefore not that the GP generated a
reliable arbitrage strategy. Rather:

1. Weather-only GP post-processing can construct coherent probabilistic
   forecasts from deterministic weather forecasts.
2. Those probabilities were competitive in parts of the development
   sample but were inferior to Polymarket prices in June on all four
   primary proper-score comparisons.
3. Apparent value gaps did not translate into statistically or
   economically robust out-of-sample trading profits.
4. Market-price information remains valuable beyond the weather-only
   forecasting signal.

## Evidential boundary

This remains a historical simulation. It does not establish live
executability, future profitability or causal market efficiency.
Recorded prices may not represent obtainable fills. Queue priority,
partial execution, market impact, capital competition across
simultaneous contracts and operational latency are outside the
empirical design.

No missing forecast or price was imputed. No June observation was used
to change the frozen strategy.
"""

        (
            stage_output
            / "phase12_report.md"
        ).write_text(
            report,
            encoding="utf-8",
        )

        atomic_replace_directory(
            stage_output,
            output_target,
        )

        print()
        print(
            "=" * 76
        )
        print(
            "PHASE 12 ROBUSTNESS AND SYNTHESIS: PASSED"
        )
        print(
            "=" * 76
        )
        print(
            "Frozen primary rule:",
            frozen_primary_rule,
        )
        print(
            "Frozen threshold:",
            frozen_primary_threshold,
        )
        print(
            "Training dates omitted individually:",
            loo_paths[
                "omitted_target_date"
            ].nunique(),
        )
        print(
            "Exact primary-threshold reselection fraction:",
            threshold_reselection_fraction,
        )
        print(
            "Primary-rule reselection fraction:",
            primary_rule_reselection_fraction,
        )
        print(
            "Candidate rule-threshold strategies:",
            int(
                adjustment[
                    "candidate_strategies"
                ]
            ),
        )
        print(
            "Multiple-strategy adjusted p-value:",
            float(
                adjustment[
                    "multiple_strategy_adjusted_p_value"
                ]
            ),
        )
        print(
            "June break-even transaction cost:",
            june_break_even_cost,
        )
        print(
            "June total net PnL at reference cost:",
            float(
                reference_june[
                    "total_net_pnl"
                ]
            ),
        )
        print(
            "Positive after removing best trade:",
            bool(
                concentration[
                    "positive_without_best_trade"
                ]
            ),
        )
        print(
            "Output:",
            output_target.relative_to(
                ROOT
            ),
        )
        print(
            "=" * 76
        )

    finally:
        if stage_root.exists():
            shutil.rmtree(
                stage_root,
                ignore_errors=True,
            )


if __name__ == "__main__":
    main()
