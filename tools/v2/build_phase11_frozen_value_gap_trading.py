#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
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
      "phase11_frozen_value_gap_trading_spec.json"
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


def maximum_drawdown(
    date_pnl: np.ndarray,
) -> float:
    pnl = np.asarray(
        date_pnl,
        dtype=float,
    )

    cumulative = np.concatenate(
        [
            np.array([0.0]),
            np.cumsum(pnl),
        ]
    )

    running_peak = np.maximum.accumulate(
        cumulative
    )

    drawdown = (
        running_peak
        - cumulative
    )

    return float(
        np.max(
            drawdown
        )
    )


def strategy_date_panel(
    candidate_books: pd.DataFrame,
    threshold: float,
    transaction_cost: float,
) -> pd.DataFrame:
    panel = candidate_books.copy()

    panel[
        "frozen_threshold"
    ] = float(
        threshold
    )

    panel[
        "transaction_cost_per_share"
    ] = float(
        transaction_cost
    )

    panel[
        "trade_executed"
    ] = (
        panel[
            "gross_value_gap"
        ]
        .ge(
            float(
                threshold
            )
        )
    )

    trade_indicator = panel[
        "trade_executed"
    ].astype(
        float
    )

    panel[
        "gross_pnl"
    ] = trade_indicator * (
        panel[
            "realised_yes"
        ]
        - panel[
            "market_probability_raw"
        ]
    )

    panel[
        "transaction_cost"
    ] = (
        trade_indicator
        * float(
            transaction_cost
        )
    )

    panel[
        "net_pnl"
    ] = (
        panel[
            "gross_pnl"
        ]
        - panel[
            "transaction_cost"
        ]
    )

    panel[
        "capital_committed"
    ] = trade_indicator * (
        panel[
            "market_probability_raw"
        ]
        + float(
            transaction_cost
        )
    )

    panel[
        "winning_trade"
    ] = (
        panel[
            "trade_executed"
        ]
        & panel[
            "net_pnl"
        ].gt(
            0.0
        )
    )

    panel[
        "losing_trade"
    ] = (
        panel[
            "trade_executed"
        ]
        & panel[
            "net_pnl"
        ].lt(
            0.0
        )
    )

    panel = panel.sort_values(
        [
            "target_date",
            "decision_rule",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    panel[
        "cumulative_net_pnl"
    ] = panel[
        "net_pnl"
    ].cumsum()

    return panel


def performance_summary(
    panel: pd.DataFrame,
) -> dict[str, Any]:
    dates = int(
        panel[
            "target_date"
        ].nunique()
    )

    trades = panel.loc[
        panel[
            "trade_executed"
        ]
    ].copy()

    trade_count = int(
        len(
            trades
        )
    )

    total_net_pnl = float(
        panel[
            "net_pnl"
        ].sum()
    )

    total_gross_pnl = float(
        panel[
            "gross_pnl"
        ].sum()
    )

    total_cost = float(
        panel[
            "transaction_cost"
        ].sum()
    )

    total_capital = float(
        panel[
            "capital_committed"
        ].sum()
    )

    mean_date_pnl = float(
        panel[
            "net_pnl"
        ].mean()
    )

    if dates > 1:
        standard_deviation = float(
            panel[
                "net_pnl"
            ].std(
                ddof=1
            )
        )
    else:
        standard_deviation = 0.0

    standard_error = (
        standard_deviation
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

        mean_traded_gap = float(
            trades[
                "gross_value_gap"
            ].mean()
        )

        mean_entry_price = float(
            trades[
                "market_probability_raw"
            ].mean()
        )

        mean_gp_probability = float(
            trades[
                "gp_event_probability"
            ].mean()
        )
    else:
        win_rate = np.nan
        mean_trade_pnl = np.nan
        median_trade_pnl = np.nan
        mean_traded_gap = np.nan
        mean_entry_price = np.nan
        mean_gp_probability = np.nan

    return_on_capital = (
        total_net_pnl
        / total_capital
        if total_capital > 0.0
        else np.nan
    )

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
                panel[
                    "winning_trade"
                ].sum()
            ),
        "losing_trades":
            int(
                panel[
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
            standard_deviation,
        "standard_error_date_net_pnl":
            standard_error,
        "mean_trade_net_pnl":
            mean_trade_pnl,
        "median_trade_net_pnl":
            median_trade_pnl,
        "total_capital_committed":
            total_capital,
        "return_on_committed_capital":
            return_on_capital,
        "maximum_drawdown":
            maximum_drawdown(
                panel[
                    "net_pnl"
                ].to_numpy(
                    dtype=float
                )
            ),
        "mean_traded_value_gap":
            mean_traded_gap,
        "mean_entry_price":
            mean_entry_price,
        "mean_gp_probability":
            mean_gp_probability,
    }


def bootstrap_pnl(
    panel: pd.DataFrame,
    repetitions: int,
    confidence_level: float,
    seed: int,
) -> dict[str, float]:
    date_pnl = (
        panel.groupby(
            "target_date",
            as_index=False,
        )[
            "net_pnl"
        ]
        .sum()
        .sort_values(
            "target_date",
            kind="stable",
        )[
            "net_pnl"
        ]
        .to_numpy(
            dtype=float
        )
    )

    observations = len(
        date_pnl
    )

    if observations == 0:
        return {
            "bootstrap_mean_ci_lower":
                np.nan,
            "bootstrap_mean_ci_upper":
                np.nan,
            "bootstrap_total_ci_lower":
                np.nan,
            "bootstrap_total_ci_upper":
                np.nan,
            "bootstrap_probability_total_positive":
                np.nan,
        }

    if observations == 1:
        value = float(
            date_pnl[0]
        )

        return {
            "bootstrap_mean_ci_lower":
                value,
            "bootstrap_mean_ci_upper":
                value,
            "bootstrap_total_ci_lower":
                value,
            "bootstrap_total_ci_upper":
                value,
            "bootstrap_probability_total_positive":
                float(
                    value > 0.0
                ),
        }

    rng = np.random.default_rng(
        seed
    )

    indices = rng.integers(
        0,
        observations,
        size=(
            repetitions,
            observations,
        ),
    )

    resampled_means = date_pnl[
        indices
    ].mean(
        axis=1
    )

    resampled_totals = (
        resampled_means
        * observations
    )

    alpha = (
        1.0
        - confidence_level
    ) / 2.0

    mean_lower, mean_upper = (
        np.quantile(
            resampled_means,
            [
                alpha,
                1.0 - alpha,
            ],
        )
    )

    total_lower, total_upper = (
        np.quantile(
            resampled_totals,
            [
                alpha,
                1.0 - alpha,
            ],
        )
    )

    return {
        "bootstrap_mean_ci_lower":
            float(
                mean_lower
            ),
        "bootstrap_mean_ci_upper":
            float(
                mean_upper
            ),
        "bootstrap_total_ci_lower":
            float(
                total_lower
            ),
        "bootstrap_total_ci_upper":
            float(
                total_upper
            ),
        "bootstrap_probability_total_positive":
            float(
                np.mean(
                    resampled_totals
                    > 0.0
                )
            ),
    }


def build_candidate_books(
    events: pd.DataFrame,
) -> pd.DataFrame:
    panel = events.copy()

    panel[
        "gross_value_gap"
    ] = (
        panel[
            "gp_event_probability"
        ]
        - panel[
            "market_probability_raw"
        ]
    )

    panel[
        "contract_key_sort"
    ] = panel[
        "contract_key"
    ].astype(
        str
    )

    panel = panel.sort_values(
        [
            "target_date",
            "decision_rule",
            "gross_value_gap",
            "gp_event_probability",
            "contract_key_sort",
        ],
        ascending=[
            True,
            True,
            False,
            False,
            True,
        ],
        kind="stable",
    )

    candidate_books = (
        panel.drop_duplicates(
            [
                "target_date",
                "decision_rule",
            ],
            keep="first",
        )
        .drop(
            columns=[
                "contract_key_sort",
            ]
        )
        .reset_index(drop=True)
    )

    expected_books = (
        events[
            [
                "target_date",
                "decision_rule",
            ]
        ]
        .drop_duplicates()
        .shape[0]
    )

    if len(candidate_books) != expected_books:
        raise RuntimeError(
            "Candidate-book construction did not "
            "produce one row per date-rule book."
        )

    return candidate_books


def training_threshold_grid(
    candidate_books: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    threshold_specification = (
        specification[
            "threshold_selection"
        ]
    )

    minimum = float(
        threshold_specification[
            "threshold_minimum"
        ]
    )

    maximum = float(
        threshold_specification[
            "threshold_maximum"
        ]
    )

    increment = float(
        threshold_specification[
            "threshold_increment"
        ]
    )

    threshold_count = int(
        round(
            (
                maximum - minimum
            )
            / increment
        )
    ) + 1

    thresholds = np.round(
        np.linspace(
            minimum,
            maximum,
            threshold_count,
        ),
        10,
    )

    reference_cost = float(
        threshold_specification[
            "reference_transaction_cost"
        ]
    )

    training = candidate_books.loc[
        candidate_books[
            "sample_period"
        ].eq(
            specification[
                "periods"
            ][
                "strategy_selection_period"
            ]
        )
    ].copy()

    rows: list[
        dict[str, Any]
    ] = []

    for decision_rule in specification[
        "decision_rules"
    ]:
        rule_panel = training.loc[
            training[
                "decision_rule"
            ].eq(
                decision_rule
            )
        ].copy()

        if rule_panel.empty:
            raise RuntimeError(
                "No strategy-selection observations "
                f"exist for {decision_rule}."
            )

        for threshold in thresholds:
            evaluated = strategy_date_panel(
                rule_panel,
                float(
                    threshold
                ),
                reference_cost,
            )

            metrics = performance_summary(
                evaluated
            )

            rows.append(
                {
                    "sample_period":
                        "weather_plus_market_training",
                    "decision_rule":
                        decision_rule,
                    "threshold":
                        float(
                            threshold
                        ),
                    "transaction_cost_per_share":
                        reference_cost,
                    **metrics,
                }
            )

    result = pd.DataFrame(
        rows
    )

    return result.sort_values(
        [
            "decision_rule",
            "threshold",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )


def select_thresholds(
    grid: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    minimum_training_trades = int(
        specification[
            "threshold_selection"
        ][
            "minimum_training_trades"
        ]
    )

    rows: list[
        dict[str, Any]
    ] = []

    for decision_rule in specification[
        "decision_rules"
    ]:
        rule_grid = grid.loc[
            grid[
                "decision_rule"
            ].eq(
                decision_rule
            )
        ].copy()

        eligible = rule_grid.loc[
            rule_grid[
                "trade_count"
            ].ge(
                minimum_training_trades
            )
        ].copy()

        minimum_trade_constraint_relaxed = False

        if eligible.empty:
            maximum_trade_count = int(
                rule_grid[
                    "trade_count"
                ].max()
            )

            eligible = rule_grid.loc[
                rule_grid[
                    "trade_count"
                ].eq(
                    maximum_trade_count
                )
            ].copy()

            minimum_trade_constraint_relaxed = True

        best_row = eligible.sort_values(
            [
                "mean_date_net_pnl",
                "threshold",
            ],
            ascending=[
                False,
                False,
            ],
            kind="stable",
        ).iloc[0]

        best_mean = float(
            best_row[
                "mean_date_net_pnl"
            ]
        )

        best_standard_error = float(
            best_row[
                "standard_error_date_net_pnl"
            ]
        )

        one_standard_error_cutoff = (
            best_mean
            - best_standard_error
        )

        within_one_standard_error = (
            eligible.loc[
                eligible[
                    "mean_date_net_pnl"
                ].ge(
                    one_standard_error_cutoff
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
        )

        selected = (
            within_one_standard_error.iloc[0]
        )

        conservative_selection_score = (
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
                    decision_rule,
                "selected_threshold":
                    float(
                        selected[
                            "threshold"
                        ]
                    ),
                "best_mean_threshold":
                    float(
                        best_row[
                            "threshold"
                        ]
                    ),
                "best_mean_date_net_pnl":
                    best_mean,
                "best_mean_standard_error":
                    best_standard_error,
                "one_standard_error_cutoff":
                    one_standard_error_cutoff,
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
                "selected_training_trade_frequency":
                    float(
                        selected[
                            "trade_frequency"
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
                "selected_training_return_on_capital":
                    float(
                        selected[
                            "return_on_committed_capital"
                        ]
                    )
                    if pd.notna(
                        selected[
                            "return_on_committed_capital"
                        ]
                    )
                    else np.nan,
                "primary_rule_selection_score":
                    conservative_selection_score,
                "minimum_training_trade_constraint":
                    minimum_training_trades,
                "minimum_trade_constraint_relaxed":
                    minimum_trade_constraint_relaxed,
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

    return selection.sort_values(
        "decision_rule",
        kind="stable",
    ).reset_index(
        drop=True
    )


def frozen_strategy_results(
    candidate_books: pd.DataFrame,
    selection: pd.DataFrame,
    specification: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    performance_rows: list[
        dict[str, Any]
    ] = []

    ledger_parts: list[
        pd.DataFrame
    ] = []

    primary_parts: list[
        pd.DataFrame
    ] = []

    primary_rule = selection.loc[
        selection[
            "selected_primary_decision_rule"
        ],
        "decision_rule",
    ].iloc[0]

    reference_cost = float(
        specification[
            "threshold_selection"
        ][
            "reference_transaction_cost"
        ]
    )

    for _, selection_row in selection.iterrows():
        decision_rule = str(
            selection_row[
                "decision_rule"
            ]
        )

        threshold = float(
            selection_row[
                "selected_threshold"
            ]
        )

        rule_panel = candidate_books.loc[
            candidate_books[
                "decision_rule"
            ].eq(
                decision_rule
            )
        ].copy()

        for sample_period in [
            specification[
                "periods"
            ][
                "strategy_selection_period"
            ],
            specification[
                "periods"
            ][
                "out_of_sample_validation_period"
            ],
        ]:
            split_panel = rule_panel.loc[
                rule_panel[
                    "sample_period"
                ].eq(
                    sample_period
                )
            ].copy()

            if split_panel.empty:
                raise RuntimeError(
                    "Missing frozen-strategy split for "
                    f"{decision_rule}: {sample_period}."
                )

            for cost in specification[
                "transaction_cost_scenarios"
            ]:
                evaluated = strategy_date_panel(
                    split_panel,
                    threshold,
                    float(
                        cost
                    ),
                )

                metrics = performance_summary(
                    evaluated
                )

                performance_rows.append(
                    {
                        "sample_period":
                            sample_period,
                        "decision_rule":
                            decision_rule,
                        "selected_primary_decision_rule":
                            decision_rule
                            == primary_rule,
                        "frozen_threshold":
                            threshold,
                        "transaction_cost_per_share":
                            float(
                                cost
                            ),
                        **metrics,
                    }
                )

                if math.isclose(
                    float(
                        cost
                    ),
                    reference_cost,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    ledger = evaluated.copy()

                    ledger[
                        "selected_primary_decision_rule"
                    ] = (
                        decision_rule
                        == primary_rule
                    )

                    ledger_parts.append(
                        ledger
                    )

                if decision_rule == primary_rule:
                    primary_parts.append(
                        evaluated.copy()
                    )

    performance = pd.DataFrame(
        performance_rows
    )

    ledger = pd.concat(
        ledger_parts,
        ignore_index=True,
    )

    primary_panel = pd.concat(
        primary_parts,
        ignore_index=True,
    )

    return (
        performance,
        ledger,
        primary_panel,
    )


def bootstrap_summary(
    candidate_books: pd.DataFrame,
    selection: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    repetitions = int(
        specification[
            "uncertainty"
        ][
            "bootstrap_repetitions"
        ]
    )

    confidence_level = float(
        specification[
            "uncertainty"
        ][
            "confidence_level"
        ]
    )

    base_seed = int(
        specification[
            "uncertainty"
        ][
            "bootstrap_seed"
        ]
    )

    primary_rule = selection.loc[
        selection[
            "selected_primary_decision_rule"
        ],
        "decision_rule",
    ].iloc[0]

    rows: list[
        dict[str, Any]
    ] = []

    counter = 0

    for _, selection_row in selection.iterrows():
        decision_rule = str(
            selection_row[
                "decision_rule"
            ]
        )

        threshold = float(
            selection_row[
                "selected_threshold"
            ]
        )

        rule_panel = candidate_books.loc[
            candidate_books[
                "decision_rule"
            ].eq(
                decision_rule
            )
        ]

        for sample_period in [
            specification[
                "periods"
            ][
                "strategy_selection_period"
            ],
            specification[
                "periods"
            ][
                "out_of_sample_validation_period"
            ],
        ]:
            split_panel = rule_panel.loc[
                rule_panel[
                    "sample_period"
                ].eq(
                    sample_period
                )
            ]

            for cost in specification[
                "transaction_cost_scenarios"
            ]:
                counter += 1

                evaluated = strategy_date_panel(
                    split_panel,
                    threshold,
                    float(
                        cost
                    ),
                )

                metrics = performance_summary(
                    evaluated
                )

                bootstrap = bootstrap_pnl(
                    evaluated,
                    repetitions,
                    confidence_level,
                    base_seed
                    + counter
                    * 1009,
                )

                rows.append(
                    {
                        "sample_period":
                            sample_period,
                        "decision_rule":
                            decision_rule,
                        "selected_primary_decision_rule":
                            decision_rule
                            == primary_rule,
                        "frozen_threshold":
                            threshold,
                        "transaction_cost_per_share":
                            float(
                                cost
                            ),
                        "dates":
                            metrics[
                                "dates"
                            ],
                        "trade_count":
                            metrics[
                                "trade_count"
                            ],
                        "total_net_pnl":
                            metrics[
                                "total_net_pnl"
                            ],
                        "mean_date_net_pnl":
                            metrics[
                                "mean_date_net_pnl"
                            ],
                        **bootstrap,
                    }
                )

    return pd.DataFrame(
        rows
    )


def create_figures(
    output_directory: Path,
    grid: pd.DataFrame,
    selection: pd.DataFrame,
    primary_panel: pd.DataFrame,
    specification: dict[str, Any],
) -> list[str]:
    figure_files: list[str] = []

    reference_cost = float(
        specification[
            "threshold_selection"
        ][
            "reference_transaction_cost"
        ]
    )

    threshold_figure_name = (
        "phase11_training_threshold_selection.png"
    )

    threshold_figure_path = (
        output_directory
        / threshold_figure_name
    )

    figure, axis = plt.subplots(
        figsize=(
            9.0,
            6.0,
        )
    )

    for decision_rule, group in grid.groupby(
        "decision_rule",
        sort=False,
    ):
        axis.plot(
            group[
                "threshold"
            ],
            group[
                "mean_date_net_pnl"
            ],
            marker="o",
            markersize=3,
            label=decision_rule,
        )

        selected_threshold = float(
            selection.loc[
                selection[
                    "decision_rule"
                ].eq(
                    decision_rule
                ),
                "selected_threshold",
            ].iloc[0]
        )

        selected_mean = float(
            group.loc[
                group[
                    "threshold"
                ].eq(
                    selected_threshold
                ),
                "mean_date_net_pnl",
            ].iloc[0]
        )

        axis.scatter(
            [
                selected_threshold
            ],
            [
                selected_mean
            ],
            s=70,
        )

    axis.axhline(
        0.0,
        linestyle="--",
    )

    axis.set_xlabel(
        "Gross GP-minus-market threshold"
    )

    axis.set_ylabel(
        "Mean net PnL per available date"
    )

    axis.set_title(
        "March-May threshold selection at "
        f"{reference_cost:.3f} cost per share"
    )

    axis.legend()

    figure.tight_layout()

    figure.savefig(
        threshold_figure_path,
        dpi=180,
    )

    plt.close(
        figure
    )

    figure_files.append(
        threshold_figure_name
    )

    primary_rule = selection.loc[
        selection[
            "selected_primary_decision_rule"
        ],
        "decision_rule",
    ].iloc[0]

    june_panel = primary_panel.loc[
        primary_panel[
            "sample_period"
        ].eq(
            specification[
                "periods"
            ][
                "out_of_sample_validation_period"
            ]
        )
    ].copy()

    cumulative_figure_name = (
        "phase11_primary_june_cumulative_pnl.png"
    )

    cumulative_figure_path = (
        output_directory
        / cumulative_figure_name
    )

    figure, axis = plt.subplots(
        figsize=(
            9.0,
            6.0,
        )
    )

    for cost, group in june_panel.groupby(
        "transaction_cost_per_share",
        sort=True,
    ):
        ordered = group.sort_values(
            "target_date",
            kind="stable",
        )

        axis.plot(
            ordered[
                "target_date"
            ],
            ordered[
                "net_pnl"
            ].cumsum(),
            marker="o",
            markersize=3,
            label=(
                f"Cost {cost:.3f}"
            ),
        )

    axis.axhline(
        0.0,
        linestyle="--",
    )

    axis.set_xlabel(
        "June target date"
    )

    axis.set_ylabel(
        "Cumulative net PnL, one-share convention"
    )

    axis.set_title(
        "Frozen primary strategy: "
        + str(
            primary_rule
        )
    )

    axis.legend()

    figure.autofmt_xdate()
    figure.tight_layout()

    figure.savefig(
        cumulative_figure_path,
        dpi=180,
    )

    plt.close(
        figure
    )

    figure_files.append(
        cumulative_figure_name
    )

    gap_figure_name = (
        "phase11_primary_june_value_gap_outcomes.png"
    )

    gap_figure_path = (
        output_directory
        / gap_figure_name
    )

    reference_panel = june_panel.loc[
        np.isclose(
            june_panel[
                "transaction_cost_per_share"
            ],
            reference_cost,
            atol=1e-12,
            rtol=0.0,
        )
    ].copy()

    figure, axis = plt.subplots(
        figsize=(
            8.0,
            6.0,
        )
    )

    axis.scatter(
        reference_panel[
            "gross_value_gap"
        ],
        reference_panel[
            "net_pnl"
        ],
    )

    frozen_threshold = float(
        selection.loc[
            selection[
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
        label="Frozen threshold",
    )

    axis.axhline(
        0.0,
        linestyle="--",
    )

    axis.set_xlabel(
        "Maximum GP-minus-market gap in book"
    )

    axis.set_ylabel(
        "Net PnL at reference cost"
    )

    axis.set_title(
        "June candidate gaps and realised PnL"
    )

    axis.legend()

    figure.tight_layout()

    figure.savefig(
        gap_figure_path,
        dpi=180,
    )

    plt.close(
        figure
    )

    figure_files.append(
        gap_figure_name
    )

    return figure_files


def report_performance_table(
    frame: pd.DataFrame,
) -> str:
    if frame.empty:
        return "No observations."

    lines = [
        "| Cost | Dates | Trades | Total net PnL | Mean date PnL | Return on capital | Win rate | Max drawdown |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for _, row in frame.iterrows():
        return_on_capital = (
            f"{row['return_on_committed_capital']:.4f}"
            if pd.notna(
                row[
                    "return_on_committed_capital"
                ]
            )
            else "NA"
        )

        win_rate = (
            f"{row['win_rate']:.4f}"
            if pd.notna(
                row[
                    "win_rate"
                ]
            )
            else "NA"
        )

        lines.append(
            "| "
            + f"{row['transaction_cost_per_share']:.3f}"
            + " | "
            + str(
                int(
                    row[
                        "dates"
                    ]
                )
            )
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
            + f"{row['mean_date_net_pnl']:.6f}"
            + " | "
            + return_on_capital
            + " | "
            + win_rate
            + " | "
            + f"{row['maximum_drawdown']:.6f}"
            + " |"
        )

    return "\n".join(
        lines
    )


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

    phase10_manifest_path = (
        ROOT
        / specification[
            "inputs"
        ][
            "phase10_manifest"
        ]
    )

    phase10_event_path = (
        ROOT
        / specification[
            "inputs"
        ][
            "phase10_event_panel"
        ]
    )

    phase10_manifest = load_json(
        phase10_manifest_path
    )

    if phase10_manifest.get(
        "status"
    ) != "passed":
        raise RuntimeError(
            "Phase 10 manifest does not report passed."
        )

    events = pd.read_csv(
        phase10_event_path,
        low_memory=False,
    )

    required_columns = {
        "target_date",
        "decision_rule",
        "contract_key",
        "event_label",
        "gp_event_probability",
        "market_probability_raw",
        "realised_yes",
        "sample_period",
    }

    missing_columns = (
        required_columns
        - set(
            events.columns
        )
    )

    if missing_columns:
        raise RuntimeError(
            "Phase 10 event panel is missing: "
            + ", ".join(
                sorted(
                    missing_columns
                )
            )
        )

    events[
        "target_date"
    ] = parse_dates(
        events[
            "target_date"
        ]
    )

    for column in [
        "gp_event_probability",
        "market_probability_raw",
        "realised_yes",
    ]:
        events[
            column
        ] = pd.to_numeric(
            events[
                column
            ],
            errors="raise",
        ).astype(
            float
        )

    if not events[
        "gp_event_probability"
    ].between(
        0.0,
        1.0,
    ).all():
        raise RuntimeError(
            "Invalid GP event probabilities."
        )

    if not events[
        "market_probability_raw"
    ].between(
        0.0,
        1.0,
    ).all():
        raise RuntimeError(
            "Invalid raw market probabilities."
        )

    if not events[
        "realised_yes"
    ].isin(
        [
            0.0,
            1.0,
        ]
    ).all():
        raise RuntimeError(
            "Invalid realised outcomes."
        )

    allowed_periods = {
        specification[
            "periods"
        ][
            "strategy_selection_period"
        ],
        specification[
            "periods"
        ][
            "out_of_sample_validation_period"
        ],
    }

    if not set(
        events[
            "sample_period"
        ].unique()
    ).issubset(
        allowed_periods
    ):
        raise RuntimeError(
            "Unexpected sample-period labels."
        )

    june_start = pd.Timestamp(
        specification[
            "periods"
        ][
            "out_of_sample_start"
        ]
    )

    june_end = pd.Timestamp(
        specification[
            "periods"
        ][
            "out_of_sample_end"
        ]
    )

    june_rows = events.loc[
        events[
            "sample_period"
        ].eq(
            specification[
                "periods"
            ][
                "out_of_sample_validation_period"
            ]
        )
    ]

    if not june_rows[
        "target_date"
    ].between(
        june_start,
        june_end,
    ).all():
        raise RuntimeError(
            "Out-of-sample rows are not confined to June."
        )

    training_rows = events.loc[
        events[
            "sample_period"
        ].eq(
            specification[
                "periods"
            ][
                "strategy_selection_period"
            ]
        )
    ]

    if not training_rows[
        "target_date"
    ].le(
        pd.Timestamp(
            specification[
                "periods"
            ][
                "strategy_selection_end"
            ]
        )
    ).all():
        raise RuntimeError(
            "Strategy-selection rows extend beyond May."
        )

    candidate_books = build_candidate_books(
        events
    )

    grid = training_threshold_grid(
        candidate_books,
        specification,
    )

    selection = select_thresholds(
        grid,
        specification,
    )

    (
        performance,
        reference_cost_ledger,
        primary_panel,
    ) = frozen_strategy_results(
        candidate_books,
        selection,
        specification,
    )

    bootstrap = bootstrap_summary(
        candidate_books,
        selection,
        specification,
    )

    primary_rule = selection.loc[
        selection[
            "selected_primary_decision_rule"
        ],
        "decision_rule",
    ].iloc[0]

    primary_threshold = float(
        selection.loc[
            selection[
                "selected_primary_decision_rule"
            ],
            "selected_threshold",
        ].iloc[0]
    )

    primary_june_performance = (
        performance.loc[
            performance[
                "selected_primary_decision_rule"
            ]
            & performance[
                "sample_period"
            ].eq(
                specification[
                    "periods"
                ][
                    "out_of_sample_validation_period"
                ]
            )
        ]
        .sort_values(
            "transaction_cost_per_share",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if (
        primary_june_performance[
            "dates"
        ].min()
        != primary_june_performance[
            "dates"
        ].max()
    ):
        raise RuntimeError(
            "Primary June cost scenarios do not use "
            "identical date support."
        )

    primary_june_bootstrap = (
        bootstrap.loc[
            bootstrap[
                "selected_primary_decision_rule"
            ]
            & bootstrap[
                "sample_period"
            ].eq(
                specification[
                    "periods"
                ][
                    "out_of_sample_validation_period"
                ]
            )
        ]
        .sort_values(
            "transaction_cost_per_share",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    output_target = (
        ROOT
        / specification[
            "output_directory"
        ]
    )

    stage_root = Path(
        tempfile.mkdtemp(
            prefix="phase11_frozen_trading_"
        )
    )

    stage_output = (
        stage_root
        / "phase11_frozen_value_gap_trading"
    )

    stage_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        candidate_books.to_csv(
            stage_output
            / "phase11_candidate_contract_by_date_rule.csv",
            index=False,
        )

        grid.to_csv(
            stage_output
            / "phase11_training_threshold_grid.csv",
            index=False,
        )

        selection.to_csv(
            stage_output
            / "phase11_frozen_strategy_selection.csv",
            index=False,
        )

        performance.to_csv(
            stage_output
            / "phase11_frozen_strategy_performance.csv",
            index=False,
        )

        reference_cost_ledger.to_csv(
            stage_output
            / "phase11_reference_cost_trade_ledger.csv",
            index=False,
        )

        primary_panel.to_csv(
            stage_output
            / "phase11_primary_strategy_date_panel.csv",
            index=False,
        )

        bootstrap.to_csv(
            stage_output
            / "phase11_date_bootstrap_summary.csv",
            index=False,
        )

        primary_june_performance.to_csv(
            stage_output
            / "phase11_primary_june_cost_sensitivity.csv",
            index=False,
        )

        primary_june_bootstrap.to_csv(
            stage_output
            / "phase11_primary_june_bootstrap.csv",
            index=False,
        )

        support_summary = (
            candidate_books.groupby(
                [
                    "sample_period",
                    "decision_rule",
                ],
                as_index=False,
            )
            .agg(
                dates=(
                    "target_date",
                    "nunique",
                ),
                candidate_books=(
                    "contract_key",
                    "size",
                ),
                mean_maximum_value_gap=(
                    "gross_value_gap",
                    "mean",
                ),
                median_maximum_value_gap=(
                    "gross_value_gap",
                    "median",
                ),
                positive_gap_books=(
                    "gross_value_gap",
                    lambda values:
                    int(
                        values.gt(
                            0.0
                        ).sum()
                    ),
                ),
            )
        )

        support_summary.to_csv(
            stage_output
            / "phase11_support_summary.csv",
            index=False,
        )

        figure_files = create_figures(
            stage_output,
            grid,
            selection,
            primary_panel,
            specification,
        )

        reference_cost = float(
            specification[
                "threshold_selection"
            ][
                "reference_transaction_cost"
            ]
        )

        reference_june = (
            primary_june_performance.loc[
                np.isclose(
                    primary_june_performance[
                        "transaction_cost_per_share"
                    ],
                    reference_cost,
                    atol=1e-12,
                    rtol=0.0,
                )
            ].iloc[0]
        )

        reference_bootstrap = (
            primary_june_bootstrap.loc[
                np.isclose(
                    primary_june_bootstrap[
                        "transaction_cost_per_share"
                    ],
                    reference_cost,
                    atol=1e-12,
                    rtol=0.0,
                )
            ].iloc[0]
        )

        manifest = {
            "phase": 11,
            "status": "passed",
            "strategy": {
                "direction":
                    "long_yes_only",
                "stake":
                    "one Yes share",
                "candidate":
                    "largest GP-minus-market gap "
                    "within each date-rule book",
                "maximum_trades_per_date_rule_book":
                    1,
                "primary_decision_rule":
                    str(
                        primary_rule
                    ),
                "primary_frozen_threshold":
                    primary_threshold,
                "reference_transaction_cost":
                    reference_cost,
            },
            "selection": {
                "selection_period":
                    "weather_plus_market_training",
                "selection_period_maximum_date":
                    str(
                        training_rows[
                            "target_date"
                        ].max().date()
                    ),
                "june_used_for_threshold_selection":
                    False,
                "june_used_for_rule_selection":
                    False,
                "threshold_method":
                    specification[
                        "threshold_selection"
                    ][
                        "rule_specific_threshold_method"
                    ],
                "primary_rule_method":
                    specification[
                        "threshold_selection"
                    ][
                        "primary_rule_method"
                    ],
            },
            "inputs": {
                "phase10_manifest": {
                    "path":
                        str(
                            phase10_manifest_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            phase10_manifest_path
                        ),
                },
                "phase10_event_panel": {
                    "path":
                        str(
                            phase10_event_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            phase10_event_path
                        ),
                },
            },
            "counts": {
                "training_candidate_dates":
                    int(
                        candidate_books.loc[
                            candidate_books[
                                "sample_period"
                            ].eq(
                                specification[
                                    "periods"
                                ][
                                    "strategy_selection_period"
                                ]
                            ),
                            "target_date",
                        ].nunique()
                    ),
                "june_candidate_dates":
                    int(
                        candidate_books.loc[
                            candidate_books[
                                "sample_period"
                            ].eq(
                                specification[
                                    "periods"
                                ][
                                    "out_of_sample_validation_period"
                                ]
                            ),
                            "target_date",
                        ].nunique()
                    ),
                "candidate_date_rule_books":
                    int(
                        len(
                            candidate_books
                        )
                    ),
                "threshold_grid_rows":
                    int(
                        len(
                            grid
                        )
                    ),
                "frozen_rule_strategies":
                    int(
                        len(
                            selection
                        )
                    ),
                "primary_june_dates":
                    int(
                        reference_june[
                            "dates"
                        ]
                    ),
                "primary_june_trades_at_reference_cost":
                    int(
                        reference_june[
                            "trade_count"
                        ]
                    ),
            },
            "primary_june_reference_cost_result": {
                "transaction_cost_per_share":
                    reference_cost,
                "total_net_pnl":
                    float(
                        reference_june[
                            "total_net_pnl"
                        ]
                    ),
                "mean_date_net_pnl":
                    float(
                        reference_june[
                            "mean_date_net_pnl"
                        ]
                    ),
                "return_on_committed_capital":
                    float(
                        reference_june[
                            "return_on_committed_capital"
                        ]
                    )
                    if pd.notna(
                        reference_june[
                            "return_on_committed_capital"
                        ]
                    )
                    else None,
                "maximum_drawdown":
                    float(
                        reference_june[
                            "maximum_drawdown"
                        ]
                    ),
                "bootstrap_total_ci_lower":
                    float(
                        reference_bootstrap[
                            "bootstrap_total_ci_lower"
                        ]
                    ),
                "bootstrap_total_ci_upper":
                    float(
                        reference_bootstrap[
                            "bootstrap_total_ci_upper"
                        ]
                    ),
                "bootstrap_probability_total_positive":
                    float(
                        reference_bootstrap[
                            "bootstrap_probability_total_positive"
                        ]
                    ),
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
            / "phase11_manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        selection_lines = [
            "| Decision rule | Frozen threshold | Training trades | Training total net PnL | Selection score | Primary |",
            "|---|---:|---:|---:|---:|---|",
        ]

        for _, row in selection.iterrows():
            selection_lines.append(
                "| "
                + str(
                    row[
                        "decision_rule"
                    ]
                )
                + " | "
                + f"{row['selected_threshold']:.3f}"
                + " | "
                + str(
                    int(
                        row[
                            "selected_training_trades"
                        ]
                    )
                )
                + " | "
                + f"{row['selected_training_total_net_pnl']:.6f}"
                + " | "
                + f"{row['primary_rule_selection_score']:.6f}"
                + " | "
                + (
                    "yes"
                    if bool(
                        row[
                            "selected_primary_decision_rule"
                        ]
                    )
                    else "no"
                )
                + " |"
            )

        bootstrap_interpretation = (
            "entirely above zero"
            if reference_bootstrap[
                "bootstrap_total_ci_lower"
            ] > 0.0
            else (
                "entirely below zero"
                if reference_bootstrap[
                    "bootstrap_total_ci_upper"
                ] < 0.0
                else "includes zero"
            )
        )

        report = f"""# Phase 11 Frozen Value-Gap Trading Evaluation

## Status

PASSED

## Strategy definition

For each target date and decision rule, the strategy identifies the
single contract with the largest value gap

`GP event probability minus raw Polymarket Yes price`.

A long Yes trade is executed only when this maximum gap is at least the
frozen rule-specific threshold. At most one Yes share is purchased in
each date-rule contract book.

The gross one-share PnL is

`realised Yes payoff minus entry price`.

Net PnL additionally deducts the stated transaction cost per share.

Decision rules are evaluated as separate deployment strategies. The
reported primary strategy does not combine sequential trades from
different decision rules on the same target date.

## Frozen selection procedure

All thresholds and the primary deployment rule were selected using only
the March-May weather-plus-market period.

For each decision rule:

1. Thresholds from
   {specification['threshold_selection']['threshold_minimum']:.2f}
   to
   {specification['threshold_selection']['threshold_maximum']:.2f}
   were evaluated in increments of
   {specification['threshold_selection']['threshold_increment']:.2f}.
2. Selection used a transaction cost of
   {reference_cost:.3f} per share.
3. Thresholds ordinarily required at least
   {specification['threshold_selection']['minimum_training_trades']}
   training trades.
4. The largest threshold within one standard error of the best
   training mean date PnL was frozen.
5. The primary decision rule maximised training mean date PnL minus one
   standard error after rule-specific threshold selection.

June outcomes were not used at any selection stage.

## Frozen strategies

{chr(10).join(selection_lines)}

## Primary strategy

- Decision rule: `{primary_rule}`.
- Frozen value-gap threshold: {primary_threshold:.3f}.
- Stake convention: one Yes share.
- June dates evaluated:
  {int(reference_june['dates'])}.
- June trades at the reference cost:
  {int(reference_june['trade_count'])}.

## June transaction-cost sensitivity

{report_performance_table(primary_june_performance)}

## Primary June uncertainty at the reference cost

At a transaction cost of {reference_cost:.3f} per share:

- Total net PnL:
  {reference_june['total_net_pnl']:.6f}.
- Mean net PnL per June date:
  {reference_june['mean_date_net_pnl']:.6f}.
- Return on committed capital:
  {reference_june['return_on_committed_capital']:.6f}
  if capital was committed.
- Maximum drawdown:
  {reference_june['maximum_drawdown']:.6f}.
- Date-level bootstrap interval for total June net PnL:
  [{reference_bootstrap['bootstrap_total_ci_lower']:.6f},
   {reference_bootstrap['bootstrap_total_ci_upper']:.6f}].
- Bootstrap probability that total June net PnL is positive:
  {reference_bootstrap['bootstrap_probability_total_positive']:.4f}.
- The bootstrap interval {bootstrap_interpretation}.

## Evidential boundary

This is a frozen historical trading simulation, not evidence of
realisable live execution. It assumes settlement at the binary payoff,
uses one-share positions, and represents transaction frictions through
the stated cost scenarios. It does not model queue position, partial
fills, slippage beyond the cost allowance, market impact, capital
constraints across simultaneous markets, or the operational ability to
trade at every recorded decision price.

No missing forecast or market price was imputed. No incomplete contract
book was traded. June was evaluated once after the threshold and primary
decision rule had been fixed.
"""

        (
            stage_output
            / "phase11_report.md"
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
            "=" * 72
        )
        print(
            "PHASE 11 FROZEN VALUE-GAP TRADING: PASSED"
        )
        print(
            "=" * 72
        )
        print(
            "Primary decision rule:",
            primary_rule,
        )
        print(
            "Frozen threshold:",
            primary_threshold,
        )
        print(
            "Reference cost:",
            reference_cost,
        )
        print(
            "June dates:",
            int(
                reference_june[
                    "dates"
                ]
            ),
        )
        print(
            "June trades:",
            int(
                reference_june[
                    "trade_count"
                ]
            ),
        )
        print(
            "June total net PnL:",
            float(
                reference_june[
                    "total_net_pnl"
                ]
            ),
        )
        print(
            "June return on capital:",
            reference_june[
                "return_on_committed_capital"
            ],
        )
        print(
            "June bootstrap total PnL interval:",
            (
                float(
                    reference_bootstrap[
                        "bootstrap_total_ci_lower"
                    ]
                ),
                float(
                    reference_bootstrap[
                        "bootstrap_total_ci_upper"
                    ]
                ),
            ),
        )
        print(
            "Output:",
            output_target.relative_to(
                ROOT
            ),
        )
        print(
            "=" * 72
        )

    finally:
        if stage_root.exists():
            shutil.rmtree(
                stage_root,
                ignore_errors=True,
            )


if __name__ == "__main__":
    main()
