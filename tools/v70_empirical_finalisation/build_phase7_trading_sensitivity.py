#!/usr/bin/env python3
"""
Phase 7: trading sensitivity, attribution and risk analysis.

Core frozen strategy
--------------------
For each settlement date and decision rule:
1. compute model probability minus raw market YES probability for every event;
2. choose the event with the largest positive gap;
3. buy one YES share when the largest gap is at least h;
4. realise PnL = Y - market_price - transaction_cost.

The development period selects a threshold separately within each rule by a
one-standard-error rule, then selects the rule by the selected policy's
mean-minus-standard-error score. The pre-designated June period is external.

The phase additionally:
- maps threshold and transaction-cost surfaces;
- reports volatility-adjusted and drawdown statistics;
- compares raw, static and Matérn trading signals;
- bootstraps total PnL and PnL attribution by settlement date;
- quantifies concentration and leave-one-date-out fragility;
- links deterministic and GP forecast errors to trade outcomes;
- computes Gaussian event-probability delta and gamma with respect to the
  predictive mean;
- reruns the frozen rule under mean shifts from -1°C to +1°C;
- separates smooth probability sensitivity from discontinuous trade selection.

All market entry prices are the recovered raw market YES values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    raise RuntimeError("matplotlib is required") from exc

try:
    from scipy import stats
except Exception as exc:  # pragma: no cover
    raise RuntimeError("scipy is required") from exc


MODEL_ORDER = ["raw", "static", "matern"]
RULE_ORDER = [
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
]
RULE_LABELS = {
    "24h_prior": "24h prior",
    "12h_prior": "12h prior",
    "6h_prior": "6h prior",
    "event_day_open": "Event-day open",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed\nSTDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "1": True,
            "yes": True,
            "passed": True,
            "false": False,
            "0": False,
            "no": False,
            "failed": False,
        })
        .fillna(False)
        .astype(bool)
    )


def dependency_check(path: Path, label: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing={path}"
    frame = pd.read_csv(path)
    if not {"critical", "passed"}.issubset(frame.columns):
        return False, f"{label} table lacks critical/passed columns"
    failed = frame.loc[
        bool_series(frame["critical"])
        & ~bool_series(frame["passed"])
    ]
    return failed.empty, f"critical_failures={len(failed)}"


def threshold_grid(config: Mapping[str, Any]) -> np.ndarray:
    grid = config["threshold_grid"]
    return np.round(
        np.arange(
            float(grid["start"]),
            float(grid["stop"]) + 0.5 * float(grid["step"]),
            float(grid["step"]),
        ),
        10,
    )


def ordinary_indices(
    n: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    return rng.integers(0, n, size=(replications, n), dtype=np.int64)


def moving_block_indices(
    n: int,
    block_length: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if n <= 0 or block_length <= 0:
        raise ValueError("n and block_length must be positive")
    blocks_needed = int(math.ceil(n / block_length))
    starts = rng.integers(
        0,
        n,
        size=(replications, blocks_needed),
    )
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (
        starts[:, :, None] + offsets[None, None, :]
    ) % n
    return indices.reshape(replications, -1)[:, :n]


def percentile_interval(
    values: np.ndarray,
    confidence: float,
) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    alpha = 1.0 - confidence
    return (
        float(np.quantile(finite, alpha / 2.0)),
        float(np.quantile(finite, 1.0 - alpha / 2.0)),
    )


def max_drawdown(pnl: Sequence[float]) -> float:
    values = np.asarray(pnl, dtype=float)
    if values.size == 0:
        return 0.0
    cumulative = np.cumsum(values)
    running_peak = np.maximum.accumulate(
        np.concatenate([[0.0], cumulative])
    )[1:]
    drawdown = cumulative - running_peak
    return float(abs(np.min(drawdown)))


def safe_ratio(numerator: float, denominator: float) -> float:
    if not np.isfinite(denominator) or abs(denominator) <= 1e-15:
        return np.nan
    return float(numerator / denominator)


def strategy_metrics(
    frame: pd.DataFrame,
    trade_mask: np.ndarray,
    cost: float,
) -> dict[str, float]:
    ordered = frame.sort_values("target_date").reset_index(drop=True)
    mask = np.asarray(trade_mask, dtype=bool)
    if len(mask) != len(ordered):
        raise ValueError("trade mask length mismatch")

    gross = np.where(
        mask,
        ordered["outcome"].to_numpy(dtype=float)
        - ordered["market_probability_raw"].to_numpy(dtype=float),
        0.0,
    )
    net = gross - np.where(mask, float(cost), 0.0)
    entry_cash = np.where(
        mask,
        ordered["market_probability_raw"].to_numpy(dtype=float)
        + float(cost),
        0.0,
    )
    trade_pnl = net[mask]
    positive = trade_pnl[trade_pnl > 0.0]
    negative = trade_pnl[trade_pnl < 0.0]
    daily_sd = float(np.std(net, ddof=1)) if len(net) > 1 else np.nan
    downside_deviation = float(
        np.sqrt(np.mean(np.minimum(net, 0.0) ** 2))
    ) if len(net) else np.nan
    total_turnover = float(np.sum(entry_cash))
    total_net = float(np.sum(net))
    total_gross = float(np.sum(gross))
    trade_count = int(mask.sum())

    return {
        "support_dates": int(len(ordered)),
        "trade_count": trade_count,
        "no_trade_dates": int(len(ordered) - trade_count),
        "winning_trades": int(np.sum(trade_pnl > 0.0)),
        "losing_trades": int(np.sum(trade_pnl < 0.0)),
        "flat_trades": int(np.sum(np.isclose(trade_pnl, 0.0))),
        "hit_rate": (
            float(np.mean(trade_pnl > 0.0))
            if trade_count else np.nan
        ),
        "total_gross_pnl": total_gross,
        "total_transaction_cost": float(cost * trade_count),
        "total_net_pnl": total_net,
        "mean_daily_net_pnl": float(np.mean(net)),
        "standard_error_daily_net_pnl": (
            float(np.std(net, ddof=1) / np.sqrt(len(net)))
            if len(net) > 1 else np.nan
        ),
        "daily_pnl_standard_deviation": daily_sd,
        "downside_deviation": downside_deviation,
        "mean_to_volatility_ratio": safe_ratio(
            float(np.mean(net)), daily_sd
        ),
        "mean_to_downside_ratio": safe_ratio(
            float(np.mean(net)), downside_deviation
        ),
        "mean_trade_net_pnl": (
            float(np.mean(trade_pnl)) if trade_count else np.nan
        ),
        "median_trade_net_pnl": (
            float(np.median(trade_pnl)) if trade_count else np.nan
        ),
        "minimum_trade_net_pnl": (
            float(np.min(trade_pnl)) if trade_count else np.nan
        ),
        "maximum_trade_net_pnl": (
            float(np.max(trade_pnl)) if trade_count else np.nan
        ),
        "total_entry_cash": total_turnover,
        "return_on_entry_cash": safe_ratio(
            total_net, total_turnover
        ),
        "profit_factor": safe_ratio(
            float(np.sum(positive)),
            abs(float(np.sum(negative))),
        ),
        "maximum_drawdown": max_drawdown(net),
        "break_even_cost_per_trade": (
            safe_ratio(total_gross, trade_count)
            if trade_count else np.nan
        ),
    }


def validate_phase6_panel(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    expected = config["expected"]
    checks: list[dict[str, Any]] = []

    def add(check: str, passed: bool, detail: str, critical: bool = True):
        checks.append({
            "check": check,
            "passed": bool(passed),
            "critical": bool(critical),
            "detail": detail,
        })

    required = {
        "target_date",
        "decision_rule",
        "event_order",
        "event_lower_bound_c",
        "event_upper_bound_c",
        "model",
        "probability_raw",
        "probability_normalised",
        "outcome",
        "split",
    }
    missing = sorted(required - set(panel.columns))
    add(
        "phase6_required_columns",
        not missing,
        f"missing={missing}",
    )
    if missing:
        return pd.DataFrame(checks)

    add(
        "phase6_event_rows",
        len(panel) == expected["event_rows"],
        f"rows={len(panel)}",
    )
    add(
        "phase6_exact_dates",
        panel["target_date"].nunique()
        == expected["exact_support_dates"],
        f"dates={panel['target_date'].nunique()}",
    )
    add(
        "phase6_models",
        set(panel["model"].unique())
        == {"raw", "static", "matern", "market"},
        f"models={sorted(panel['model'].unique())}",
    )
    book_counts = (
        panel.groupby("model")[
            ["target_date", "decision_rule"]
        ]
        .apply(lambda x: len(x.drop_duplicates()))
        .to_dict()
    )
    add(
        "phase6_books_per_model",
        all(
            book_counts.get(model, 0)
            == expected["exact_support_books"]
            for model in ["raw", "static", "matern", "market"]
        ),
        f"counts={book_counts}",
    )
    market = panel.loc[panel["model"] == "market"]
    raw_sums = (
        market.groupby(["target_date", "decision_rule"])[
            "probability_raw"
        ].sum()
    )
    add(
        "market_raw_values_not_pre_normalised",
        bool(
            np.max(np.abs(raw_sums.to_numpy(dtype=float) - 1.0))
            > 1e-4
        ),
        (
            f"mean_sum={raw_sums.mean():.6f}; "
            f"minimum_sum={raw_sums.min():.6f}; "
            f"maximum_sum={raw_sums.max():.6f}"
        ),
    )
    return pd.DataFrame(checks)


def build_candidate_panel(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    # Use only the certified event key in the probability pivot. Descriptive
    # metadata can legitimately be absent for reconstructed raw/static rows.
    stable_index = [
        "target_date",
        "decision_rule",
        "split",
        "event_order",
    ]
    missing_stable = [
        column for column in stable_index if column not in panel.columns
    ]
    if missing_stable:
        raise ValueError(
            f"Candidate panel missing stable key columns: {missing_stable}"
        )

    duplicate_counts = (
        panel.groupby(stable_index + ["model"], dropna=False)
        .size()
    )
    if int((duplicate_counts != 1).sum()) > 0:
        bad = duplicate_counts.loc[duplicate_counts != 1]
        raise ValueError(
            "Candidate probability panel is not unique on the certified "
            f"event-model key. Bad keys={len(bad)}"
        )

    probability_pivot = panel.pivot(
        index=stable_index,
        columns="model",
        values=[
            "probability_raw",
            "probability_normalised",
        ],
    )
    probability_pivot.columns = [
        f"{quantity}_{model}"
        for quantity, model in probability_pivot.columns
    ]
    probability_pivot = probability_pivot.reset_index()

    metadata_columns = [
        column
        for column in [
            "event_label",
            "event_lower_bound_c",
            "event_upper_bound_c",
            "outcome",
        ]
        if column in panel.columns
    ]

    metadata_rows: list[dict[str, Any]] = []
    for key_values, group in panel.groupby(
        stable_index,
        sort=False,
        dropna=False,
    ):
        row = {
            column: value
            for column, value in zip(stable_index, key_values)
        }
        for column in metadata_columns:
            nonmissing = group[column].dropna()
            unique_values = pd.unique(nonmissing)
            if len(unique_values) > 1:
                numeric = pd.to_numeric(
                    pd.Series(unique_values),
                    errors="coerce",
                )
                if (
                    numeric.notna().all()
                    and float(numeric.max() - numeric.min())
                    <= float(config["numerical_tolerance"])
                ):
                    row[column] = float(numeric.iloc[0])
                else:
                    raise ValueError(
                        "Inconsistent event metadata on certified key "
                        f"{row}: column={column}; "
                        f"values={list(unique_values)}"
                    )
            elif len(unique_values) == 1:
                row[column] = unique_values[0]
            else:
                row[column] = np.nan
        metadata_rows.append(row)

    metadata = pd.DataFrame(metadata_rows)
    pivot = probability_pivot.merge(
        metadata,
        on=stable_index,
        how="left",
        validate="one_to_one",
    )

    required = [
        "probability_raw_market",
        "probability_normalised_market",
        "probability_normalised_raw",
        "probability_normalised_static",
        "probability_normalised_matern",
    ]
    missing = [column for column in required if column not in pivot.columns]
    if missing:
        raise ValueError(f"Candidate pivot missing columns: {missing}")

    bad_nonfinite: dict[str, int] = {}
    for column in required:
        values = pd.to_numeric(
            pivot[column],
            errors="coerce",
        ).to_numpy(dtype=float)
        count = int((~np.isfinite(values)).sum())
        if count > 0:
            bad_nonfinite[column] = count
    if bad_nonfinite:
        raise ValueError(
            "Candidate pivot contains non-finite probabilities: "
            f"{bad_nonfinite}"
        )

    pieces: list[pd.DataFrame] = []
    for model in MODEL_ORDER:
        frame = pivot.copy()
        frame["signal_model"] = model
        frame["model_probability"] = frame[
            f"probability_normalised_{model}"
        ]
        frame["market_probability_raw"] = frame[
            "probability_raw_market"
        ]
        frame["market_probability_normalised"] = frame[
            "probability_normalised_market"
        ]
        frame["signal_gap"] = (
            frame["model_probability"]
            - frame["market_probability_raw"]
        )

        if not np.isfinite(
            frame["signal_gap"].to_numpy(dtype=float)
        ).all():
            raise ValueError(
                f"Non-finite signal gaps remain for model={model}"
            )

        selected_index = (
            frame.groupby(
                ["target_date", "decision_rule"],
                sort=False,
            )["signal_gap"]
            .idxmax()
        )
        if selected_index.isna().any():
            raise ValueError(
                f"Could not select a candidate event for model={model}; "
                f"books_with_missing_selection="
                f"{int(selected_index.isna().sum())}"
            )

        selected = frame.loc[
            selected_index.astype(int).to_numpy()
        ].copy()
        selected["gross_pnl_if_traded"] = (
            selected["outcome"]
            - selected["market_probability_raw"]
        )
        selected["model_implied_gross_edge"] = selected["signal_gap"]
        pieces.append(selected)

    result = pd.concat(pieces, ignore_index=True)
    result["rule_order"] = result["decision_rule"].map(
        {rule: position for position, rule in enumerate(RULE_ORDER)}
    )
    result["model_order"] = result["signal_model"].map(
        {model: position for position, model in enumerate(MODEL_ORDER)}
    )
    return result.sort_values(
        ["model_order", "target_date", "rule_order"]
    ).reset_index(drop=True)

def build_threshold_cost_surface(
    candidates: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    thresholds = threshold_grid(config)
    costs = list(map(float, config["transaction_cost_grid"]))

    for (model, split, rule), group in candidates.groupby(
        ["signal_model", "split", "decision_rule"],
        sort=False,
    ):
        ordered = group.sort_values("target_date").reset_index(drop=True)
        gap = ordered["signal_gap"].to_numpy(dtype=float)
        for threshold in thresholds:
            trade_mask = gap >= float(threshold)
            for cost in costs:
                metrics = strategy_metrics(
                    ordered,
                    trade_mask,
                    cost,
                )
                rows.append({
                    "signal_model": model,
                    "split": split,
                    "decision_rule": rule,
                    "threshold": float(threshold),
                    "transaction_cost": cost,
                    **metrics,
                })
    return pd.DataFrame(rows)


def select_development_policies(
    surface: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cost = float(config["expected"]["selected_cost"])
    minimum = int(config["minimum_development_trades"])
    rows: list[dict[str, Any]] = []

    development = surface.loc[
        (surface["split"] == "development")
        & np.isclose(surface["transaction_cost"], cost)
    ].copy()

    for model in MODEL_ORDER:
        model_frame = development.loc[
            development["signal_model"] == model
        ]
        for rule in RULE_ORDER:
            rule_frame = model_frame.loc[
                model_frame["decision_rule"] == rule
            ].copy()
            eligible = rule_frame.loc[
                rule_frame["trade_count"] >= minimum
            ].copy()
            if eligible.empty:
                rows.append({
                    "signal_model": model,
                    "decision_rule": rule,
                    "status": "no_threshold_meets_minimum_trades",
                })
                continue
            best = eligible.sort_values(
                ["mean_daily_net_pnl", "threshold"],
                ascending=[False, False],
            ).iloc[0]
            cutoff = (
                float(best["mean_daily_net_pnl"])
                - float(best["standard_error_daily_net_pnl"])
            )
            one_se = eligible.loc[
                eligible["mean_daily_net_pnl"] >= cutoff
            ].sort_values("threshold")
            selected = one_se.iloc[-1]
            rows.append({
                "signal_model": model,
                "decision_rule": rule,
                "status": "selected",
                "best_threshold_by_mean": float(best["threshold"]),
                "best_mean_daily_net_pnl": float(
                    best["mean_daily_net_pnl"]
                ),
                "best_standard_error": float(
                    best["standard_error_daily_net_pnl"]
                ),
                "one_standard_error_cutoff": cutoff,
                "selected_threshold": float(selected["threshold"]),
                "selected_trade_count": int(selected["trade_count"]),
                "selected_total_net_pnl": float(
                    selected["total_net_pnl"]
                ),
                "selected_mean_daily_net_pnl": float(
                    selected["mean_daily_net_pnl"]
                ),
                "selected_standard_error": float(
                    selected["standard_error_daily_net_pnl"]
                ),
                "selected_rule_score_mean_minus_se": float(
                    selected["mean_daily_net_pnl"]
                    - selected["standard_error_daily_net_pnl"]
                ),
                "transaction_cost": cost,
                "minimum_development_trades": minimum,
            })

    rule_selection = pd.DataFrame(rows)
    model_rows: list[dict[str, Any]] = []
    selected_rules = rule_selection.loc[
        rule_selection["status"] == "selected"
    ]
    for model in MODEL_ORDER:
        model_table = selected_rules.loc[
            selected_rules["signal_model"] == model
        ]
        if model_table.empty:
            continue
        chosen = model_table.sort_values(
            [
                "selected_rule_score_mean_minus_se",
                "selected_mean_daily_net_pnl",
                "decision_rule",
            ],
            ascending=[False, False, True],
        ).iloc[0]
        model_rows.append({
            "signal_model": model,
            "selected_rule": chosen["decision_rule"],
            "selected_threshold": chosen["selected_threshold"],
            "transaction_cost": chosen["transaction_cost"],
            "development_trade_count": chosen[
                "selected_trade_count"
            ],
            "development_total_net_pnl": chosen[
                "selected_total_net_pnl"
            ],
            "development_mean_daily_net_pnl": chosen[
                "selected_mean_daily_net_pnl"
            ],
            "development_standard_error": chosen[
                "selected_standard_error"
            ],
            "selection_score_mean_minus_se": chosen[
                "selected_rule_score_mean_minus_se"
            ],
        })
    return rule_selection, pd.DataFrame(model_rows)


def materialise_policy(
    candidates: pd.DataFrame,
    model: str,
    rule: str,
    threshold: float,
    cost: float,
) -> pd.DataFrame:
    frame = candidates.loc[
        (candidates["signal_model"] == model)
        & (candidates["decision_rule"] == rule)
    ].copy()
    frame = frame.sort_values("target_date").reset_index(drop=True)
    frame["threshold"] = float(threshold)
    frame["transaction_cost"] = float(cost)
    frame["trade"] = frame["signal_gap"] >= float(threshold)
    frame["gross_pnl"] = np.where(
        frame["trade"],
        frame["outcome"] - frame["market_probability_raw"],
        0.0,
    )
    frame["net_pnl"] = (
        frame["gross_pnl"]
        - np.where(frame["trade"], float(cost), 0.0)
    )
    frame["entry_cash"] = np.where(
        frame["trade"],
        frame["market_probability_raw"] + float(cost),
        0.0,
    )
    frame["model_implied_expected_net_payoff"] = np.where(
        frame["trade"],
        frame["signal_gap"] - float(cost),
        0.0,
    )
    frame["realised_minus_model_expected"] = np.where(
        frame["trade"],
        frame["outcome"] - frame["model_probability"],
        0.0,
    )
    frame["cumulative_net_pnl"] = frame.groupby("split")[
        "net_pnl"
    ].cumsum()
    frame["running_peak"] = frame.groupby("split")[
        "cumulative_net_pnl"
    ].cummax().clip(lower=0.0)
    frame["drawdown"] = (
        frame["cumulative_net_pnl"] - frame["running_peak"]
    )
    return frame


def policy_summary(
    policy_panel: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for split, group in policy_panel.groupby("split", sort=False):
        metrics = strategy_metrics(
            group,
            group["trade"].to_numpy(dtype=bool),
            float(group["transaction_cost"].iloc[0]),
        )
        rows.append({
            "signal_model": group["signal_model"].iloc[0],
            "decision_rule": group["decision_rule"].iloc[0],
            "threshold": group["threshold"].iloc[0],
            "transaction_cost": group[
                "transaction_cost"
            ].iloc[0],
            "split": split,
            **metrics,
        })
    return pd.DataFrame(rows)


def bootstrap_policy_pnl(
    policy_panel: pd.DataFrame,
    config: Mapping[str, Any],
    label_fields: Mapping[str, Any],
    seed_offset: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = policy_panel.sort_values("target_date").reset_index(drop=True)
    values = ordered["net_pnl"].to_numpy(dtype=float)
    n = len(values)
    reps = int(config["bootstrap"]["replications"])
    chunk = int(config["bootstrap"]["chunk_size"])
    confidence = float(config["bootstrap"]["confidence_level"])
    methods: list[tuple[str, int | None]] = [("ordinary_date", None)]
    methods.extend(
        ("circular_moving_block", int(block))
        for block in config["bootstrap"]["moving_block_lengths"]
        if n >= int(block)
    )
    rows: list[dict[str, Any]] = []
    distributions: list[pd.DataFrame] = []

    for method_index, (method, block) in enumerate(methods):
        seed = (
            int(config["bootstrap"]["seed"])
            + seed_offset
            + method_index * 100
        )
        rng = np.random.default_rng(seed)
        total_parts: list[np.ndarray] = []
        completed = 0
        while completed < reps:
            current = min(chunk, reps - completed)
            if method == "ordinary_date":
                indices = ordinary_indices(n, current, rng)
            else:
                assert block is not None
                indices = moving_block_indices(
                    n, block, current, rng
                )
            total_parts.append(values[indices].sum(axis=1))
            completed += current
        total_distribution = np.concatenate(total_parts)
        mean_distribution = total_distribution / n
        total_lower, total_upper = percentile_interval(
            total_distribution, confidence
        )
        mean_lower, mean_upper = percentile_interval(
            mean_distribution, confidence
        )
        rows.append({
            **dict(label_fields),
            "dates": n,
            "point_total_net_pnl": float(values.sum()),
            "point_mean_daily_net_pnl": float(values.mean()),
            "bootstrap_method": method,
            "block_length_days": block,
            "total_pnl_lower_95": total_lower,
            "total_pnl_upper_95": total_upper,
            "mean_daily_pnl_lower_95": mean_lower,
            "mean_daily_pnl_upper_95": mean_upper,
            "positive_total_pnl_fraction": float(
                np.mean(total_distribution > 0.0)
            ),
            "nonnegative_total_pnl_fraction": float(
                np.mean(total_distribution >= 0.0)
            ),
            "bootstrap_replications": reps,
            "seed": seed,
            "bootstrap_unit": "settlement_date",
        })
        if method == "ordinary_date":
            distributions.append(pd.DataFrame({
                "replication": np.arange(1, reps + 1),
                "total_net_pnl": total_distribution,
                "mean_daily_net_pnl": mean_distribution,
                **{
                    key: value
                    for key, value in label_fields.items()
                },
            }))
    return pd.DataFrame(rows), pd.concat(
        distributions, ignore_index=True
    )


def cost_sensitivity_for_policy(
    candidates: pd.DataFrame,
    model: str,
    rule: str,
    threshold: float,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    frame = candidates.loc[
        (candidates["signal_model"] == model)
        & (candidates["decision_rule"] == rule)
    ].copy()
    trade_mask = (
        frame["signal_gap"].to_numpy(dtype=float)
        >= float(threshold)
    )
    for split, group in frame.groupby("split", sort=False):
        group = group.sort_values("target_date")
        mask = (
            group["signal_gap"].to_numpy(dtype=float)
            >= float(threshold)
        )
        for cost in config["transaction_cost_grid"]:
            rows.append({
                "signal_model": model,
                "decision_rule": rule,
                "threshold": float(threshold),
                "split": split,
                "transaction_cost": float(cost),
                **strategy_metrics(group, mask, float(cost)),
            })
    return pd.DataFrame(rows)


def fixed_policy_model_attribution(
    candidates: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rule = config["expected"]["selected_rule"]
    threshold = float(config["expected"]["selected_threshold"])
    cost = float(config["expected"]["selected_cost"])
    panels: list[pd.DataFrame] = []
    summaries: list[pd.DataFrame] = []

    for model in MODEL_ORDER:
        panel = materialise_policy(
            candidates, model, rule, threshold, cost
        )
        panels.append(panel)
        summaries.append(policy_summary(panel))

    all_panels = pd.concat(panels, ignore_index=True)
    all_summaries = pd.concat(summaries, ignore_index=True)

    wide = all_panels.pivot_table(
        index=["target_date", "split"],
        columns="signal_model",
        values=[
            "net_pnl",
            "trade",
            "event_order",
            "signal_gap",
        ],
        aggfunc="first",
    )
    wide.columns = [
        f"{quantity}_{model}"
        for quantity, model in wide.columns
    ]
    wide = wide.reset_index()
    wide["static_minus_raw_net_pnl"] = (
        wide["net_pnl_static"] - wide["net_pnl_raw"]
    )
    wide["matern_minus_static_net_pnl"] = (
        wide["net_pnl_matern"] - wide["net_pnl_static"]
    )
    wide["matern_minus_raw_net_pnl"] = (
        wide["net_pnl_matern"] - wide["net_pnl_raw"]
    )
    wide["static_changes_trade_decision"] = (
        wide["trade_static"] != wide["trade_raw"]
    )
    wide["matern_changes_trade_decision_vs_static"] = (
        wide["trade_matern"] != wide["trade_static"]
    )
    wide["static_changes_selected_event"] = (
        wide["event_order_static"] != wide["event_order_raw"]
    )
    wide["matern_changes_selected_event_vs_static"] = (
        wide["event_order_matern"] != wide["event_order_static"]
    )
    return all_panels, all_summaries, wide


def bootstrap_attribution(
    attribution_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    contrasts = [
        "static_minus_raw_net_pnl",
        "matern_minus_static_net_pnl",
        "matern_minus_raw_net_pnl",
    ]
    rows: list[pd.DataFrame] = []
    seed_offset = 400000
    for split, group in attribution_panel.groupby("split", sort=False):
        for contrast in contrasts:
            pseudo = pd.DataFrame({
                "target_date": group["target_date"],
                "net_pnl": group[contrast],
            })
            intervals, _ = bootstrap_policy_pnl(
                pseudo,
                config,
                {
                    "split": split,
                    "contrast": contrast,
                },
                seed_offset,
            )
            rows.append(intervals)
            seed_offset += 1000
    return pd.concat(rows, ignore_index=True)


def trade_concentration(
    policy_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = policy_panel.loc[
        policy_panel["trade"]
    ].copy().sort_values("target_date")
    rows: list[dict[str, Any]] = []
    influence_rows: list[dict[str, Any]] = []

    for split, group in trades.groupby("split", sort=False):
        pnl = group["net_pnl"].to_numpy(dtype=float)
        abs_pnl = np.abs(pnl)
        total_abs = float(abs_pnl.sum())
        ordered_abs = np.sort(abs_pnl)[::-1]
        total = float(pnl.sum())
        positive = float(pnl[pnl > 0].sum())
        negative = float(pnl[pnl < 0].sum())
        row = {
            "split": split,
            "trades": len(group),
            "total_net_pnl": total,
            "positive_contribution": positive,
            "negative_contribution": negative,
            "absolute_contribution_total": total_abs,
            "absolute_contribution_hhi": (
                float(np.sum((abs_pnl / total_abs) ** 2))
                if total_abs > 0 else np.nan
            ),
            "effective_number_of_contributing_trades": (
                float(1.0 / np.sum((abs_pnl / total_abs) ** 2))
                if total_abs > 0 else np.nan
            ),
        }
        for top in [1, 3, 5, 10]:
            row[f"top_{top}_absolute_contribution_share"] = (
                float(ordered_abs[:top].sum() / total_abs)
                if total_abs > 0 else np.nan
            )
        rows.append(row)

        for _, trade in group.iterrows():
            remaining = total - float(trade["net_pnl"])
            influence_rows.append({
                "split": split,
                "omitted_target_date": trade["target_date"],
                "omitted_event_order": trade["event_order"],
                "omitted_outcome": trade["outcome"],
                "omitted_net_pnl": trade["net_pnl"],
                "remaining_total_net_pnl": remaining,
                "sign_preserved": (
                    np.sign(remaining) == np.sign(total)
                    if not np.isclose(total, 0.0) else np.nan
                ),
            })
    return pd.DataFrame(rows), pd.DataFrame(influence_rows)


def prepare_weather_panel(
    market_predictions: pd.DataFrame,
    validation_panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepare the market-period predictive law and register HKO availability.

    The Phase 8 mean and scale are authoritative for probability perturbation.
    Exact HKO values are used only when genuinely available. No settlement-bin
    midpoint or other proxy is substituted for a missing realised temperature.
    """
    required_market = {
        "target_date",
        "decision_rule",
        "forecast_daily_max_c",
        "gp_temperature_mean_c",
        "gp_temperature_std_c",
    }
    missing_market = sorted(
        required_market - set(market_predictions.columns)
    )
    if missing_market:
        raise ValueError(
            f"Phase 8 market prediction panel missing {missing_market}"
        )

    market = market_predictions.copy()
    market["target_date"] = pd.to_datetime(
        market["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    market_columns = [
        "target_date",
        "decision_rule",
        "forecast_daily_max_c",
        "gp_temperature_mean_c",
        "gp_temperature_std_c",
    ]

    market_hko_candidates = [
        "hko_daily_max_c",
        "realised_hko_daily_max_c",
        "realized_hko_daily_max_c",
        "observed_daily_max_c",
        "actual_daily_max_c",
    ]
    market_hko_column = next(
        (
            column
            for column in market_hko_candidates
            if column in market.columns
        ),
        None,
    )
    if market_hko_column is not None:
        market_columns.append(market_hko_column)

    market = market[market_columns].drop_duplicates(
        ["target_date", "decision_rule"]
    )
    market = market.rename(columns={
        "gp_temperature_mean_c": "temperature_predictive_mean_c",
        "gp_temperature_std_c": "predictive_standard_deviation_c",
    })
    if (
        market_hko_column is not None
        and market_hko_column != "hko_daily_max_c"
    ):
        market = market.rename(columns={
            market_hko_column: "hko_daily_max_c",
        })

    validation = validation_panel.copy()
    validation["target_date"] = pd.to_datetime(
        validation["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    validation_hko_candidates = [
        "hko_daily_max_c",
        "realised_hko_daily_max_c",
        "realized_hko_daily_max_c",
        "observed_daily_max_c",
        "actual_daily_max_c",
    ]
    validation_hko_column = next(
        (
            column
            for column in validation_hko_candidates
            if column in validation.columns
        ),
        None,
    )

    validation_columns = ["target_date", "decision_rule"]
    if validation_hko_column is not None:
        validation_columns.append(validation_hko_column)
    if "forecast_daily_max_c" in validation.columns:
        validation_columns.append("forecast_daily_max_c")

    validation = validation[
        validation_columns
    ].drop_duplicates(["target_date", "decision_rule"])
    rename_validation: dict[str, str] = {}
    if (
        validation_hko_column is not None
        and validation_hko_column != "hko_daily_max_c"
    ):
        rename_validation[
            validation_hko_column
        ] = "hko_daily_max_c"
    if "forecast_daily_max_c" in validation.columns:
        rename_validation[
            "forecast_daily_max_c"
        ] = "validation_forecast_daily_max_c"
    validation = validation.rename(columns=rename_validation)

    if "hko_daily_max_c" in market.columns:
        market = market.rename(columns={
            "hko_daily_max_c": "market_panel_hko_daily_max_c",
        })

    result = market.merge(
        validation,
        on=["target_date", "decision_rule"],
        how="left",
        validate="one_to_one",
    )

    if "market_panel_hko_daily_max_c" in result.columns:
        market_hko = pd.to_numeric(
            result["market_panel_hko_daily_max_c"],
            errors="coerce",
        )
        validation_hko = (
            pd.to_numeric(
                result["hko_daily_max_c"],
                errors="coerce",
            )
            if "hko_daily_max_c" in result.columns
            else pd.Series(np.nan, index=result.index)
        )
        result["hko_daily_max_c"] = (
            market_hko.combine_first(validation_hko)
        )
        result["realised_hko_source"] = np.select(
            [market_hko.notna(), validation_hko.notna()],
            [
                "phase8_market_prediction_panel",
                "phase5_validation_panel",
            ],
            default="unavailable",
        )
    elif "hko_daily_max_c" not in result.columns:
        result["hko_daily_max_c"] = np.nan
        result["realised_hko_source"] = "unavailable"
    else:
        result["realised_hko_source"] = np.where(
            pd.to_numeric(
                result["hko_daily_max_c"],
                errors="coerce",
            ).notna(),
            "phase5_validation_panel",
            "unavailable",
        )

    numeric = [
        "forecast_daily_max_c",
        "temperature_predictive_mean_c",
        "predictive_standard_deviation_c",
        "hko_daily_max_c",
    ]
    if "validation_forecast_daily_max_c" in result.columns:
        numeric.append("validation_forecast_daily_max_c")
    for column in numeric:
        result[column] = pd.to_numeric(
            result[column], errors="coerce"
        )

    result["realised_hko_available"] = (
        result["hko_daily_max_c"].notna()
    )

    if "validation_forecast_daily_max_c" in result.columns:
        result["forecast_daily_max_crosscheck_difference_c"] = (
            result["forecast_daily_max_c"]
            - result["validation_forecast_daily_max_c"]
        )
    else:
        result["forecast_daily_max_crosscheck_difference_c"] = np.nan

    result["deterministic_forecast_error_c"] = (
        result["hko_daily_max_c"]
        - result["forecast_daily_max_c"]
    )
    result["matern_mean_error_c"] = (
        result["hko_daily_max_c"]
        - result["temperature_predictive_mean_c"]
    )
    result["standardised_matern_error"] = (
        result["matern_mean_error_c"]
        / result["predictive_standard_deviation_c"]
    )

    return result

def normal_cdf(value: np.ndarray) -> np.ndarray:
    return stats.norm.cdf(value)


def normal_pdf(value: np.ndarray) -> np.ndarray:
    return stats.norm.pdf(value)


def gaussian_event_probability(
    lower: np.ndarray,
    upper: np.ndarray,
    mean: np.ndarray,
    sd: np.ndarray,
) -> np.ndarray:
    z_upper = (upper - mean) / sd
    z_lower = (lower - mean) / sd
    return normal_cdf(z_upper) - normal_cdf(z_lower)


def gaussian_event_delta(
    lower: np.ndarray,
    upper: np.ndarray,
    mean: np.ndarray,
    sd: np.ndarray,
) -> np.ndarray:
    z_lower = (lower - mean) / sd
    z_upper = (upper - mean) / sd
    return (
        normal_pdf(z_lower) - normal_pdf(z_upper)
    ) / sd


def gaussian_event_gamma(
    lower: np.ndarray,
    upper: np.ndarray,
    mean: np.ndarray,
    sd: np.ndarray,
) -> np.ndarray:
    z_lower = (lower - mean) / sd
    z_upper = (upper - mean) / sd
    lower_term = np.where(
        np.isfinite(z_lower),
        z_lower * normal_pdf(z_lower),
        0.0,
    )
    upper_term = np.where(
        np.isfinite(z_upper),
        z_upper * normal_pdf(z_upper),
        0.0,
    )
    return (lower_term - upper_term) / (sd ** 2)


def build_probability_sensitivity_panel(
    phase6_panel: pd.DataFrame,
    weather: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event = phase6_panel.loc[
        phase6_panel["model"].isin(["matern", "market"])
    ].copy()
    market = event.loc[
        event["model"] == "market",
        [
            "target_date",
            "decision_rule",
            "event_order",
            "probability_raw",
            "outcome",
            "split",
        ],
    ].rename(columns={
        "probability_raw": "market_probability_raw",
    })
    matern = event.loc[
        event["model"] == "matern",
        [
            "target_date",
            "decision_rule",
            "event_order",
            "event_label",
            "event_lower_bound_c",
            "event_upper_bound_c",
            "probability_normalised",
        ],
    ].rename(columns={
        "probability_normalised": "matern_probability_frozen",
    })
    joined = matern.merge(
        market,
        on=["target_date", "decision_rule", "event_order"],
        how="inner",
        validate="one_to_one",
    ).merge(
        weather,
        on=["target_date", "decision_rule"],
        how="left",
        validate="many_to_one",
    )

    if joined[
        [
            "temperature_predictive_mean_c",
            "predictive_standard_deviation_c",
        ]
    ].isna().any().any():
        missing = joined.loc[
            joined["temperature_predictive_mean_c"].isna(),
            ["target_date", "decision_rule"],
        ].drop_duplicates()
        raise ValueError(
            f"Weather join missing {len(missing)} exact-support books"
        )

    lower = joined["event_lower_bound_c"].to_numpy(dtype=float)
    upper = joined["event_upper_bound_c"].to_numpy(dtype=float)
    mean = joined[
        "temperature_predictive_mean_c"
    ].to_numpy(dtype=float)
    sd = joined[
        "predictive_standard_deviation_c"
    ].to_numpy(dtype=float)

    joined["probability_recomputed_at_zero_shift"] = (
        gaussian_event_probability(lower, upper, mean, sd)
    )
    joined["probability_zero_shift_absolute_error"] = np.abs(
        joined["probability_recomputed_at_zero_shift"]
        - joined["matern_probability_frozen"]
    )
    joined["probability_delta_per_c"] = gaussian_event_delta(
        lower, upper, mean, sd
    )
    joined["probability_gamma_per_c2"] = gaussian_event_gamma(
        lower, upper, mean, sd
    )
    joined["event_midpoint_c"] = np.where(
        np.isfinite(lower) & np.isfinite(upper),
        0.5 * (lower + upper),
        np.nan,
    )
    joined["event_midpoint_minus_predictive_mean_c"] = (
        joined["event_midpoint_c"]
        - joined["temperature_predictive_mean_c"]
    )

    shift_rows: list[pd.DataFrame] = []
    for shift in map(float, config["mean_shift_grid_c"]):
        shifted = joined[
            [
                "target_date",
                "decision_rule",
                "event_order",
                "event_label",
                "event_lower_bound_c",
                "event_upper_bound_c",
                "outcome",
                "split",
                "market_probability_raw",
            ]
        ].copy()
        shifted["mean_shift_c"] = shift
        shifted["shifted_matern_probability"] = (
            gaussian_event_probability(
                lower,
                upper,
                mean + shift,
                sd,
            )
        )
        shifted["shifted_signal_gap"] = (
            shifted["shifted_matern_probability"]
            - shifted["market_probability_raw"]
        )
        shift_rows.append(shifted)

    shifted_event = pd.concat(shift_rows, ignore_index=True)
    selected_index = shifted_event.groupby(
        [
            "mean_shift_c",
            "target_date",
            "decision_rule",
        ],
        sort=False,
    )["shifted_signal_gap"].idxmax()
    shifted_candidates = shifted_event.loc[selected_index].copy()

    base = shifted_candidates.loc[
        np.isclose(shifted_candidates["mean_shift_c"], 0.0),
        [
            "target_date",
            "decision_rule",
            "event_order",
            "shifted_signal_gap",
        ],
    ].rename(columns={
        "event_order": "base_event_order",
        "shifted_signal_gap": "base_signal_gap",
    })
    shifted_candidates = shifted_candidates.merge(
        base,
        on=["target_date", "decision_rule"],
        how="left",
        validate="many_to_one",
    )
    shifted_candidates["selected_event_changed_vs_zero"] = (
        shifted_candidates["event_order"]
        != shifted_candidates["base_event_order"]
    )
    return joined, shifted_event, shifted_candidates


def mean_shift_strategy_sensitivity(
    shifted_candidates: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rule = config["expected"]["selected_rule"]
    threshold = float(config["expected"]["selected_threshold"])
    cost = float(config["expected"]["selected_cost"])
    rows: list[dict[str, Any]] = []
    panel_rows: list[pd.DataFrame] = []

    selected_rule = shifted_candidates.loc[
        shifted_candidates["decision_rule"] == rule
    ].copy()
    zero = selected_rule.loc[
        np.isclose(selected_rule["mean_shift_c"], 0.0),
        ["target_date", "shifted_signal_gap"],
    ].rename(columns={
        "shifted_signal_gap": "zero_signal_gap",
    })
    zero["zero_trade"] = zero["zero_signal_gap"] >= threshold

    for (shift, split), group in selected_rule.groupby(
        ["mean_shift_c", "split"],
        sort=False,
    ):
        group = group.sort_values("target_date").merge(
            zero,
            on="target_date",
            how="left",
            validate="one_to_one",
        )
        group["trade"] = (
            group["shifted_signal_gap"] >= threshold
        )
        group["net_pnl"] = np.where(
            group["trade"],
            group["outcome"]
            - group["market_probability_raw"]
            - cost,
            0.0,
        )
        group["trade_decision_changed_vs_zero"] = (
            group["trade"] != group["zero_trade"]
        )
        metrics = strategy_metrics(
            group.rename(columns={
                "shifted_signal_gap": "signal_gap",
            }),
            group["trade"].to_numpy(dtype=bool),
            cost,
        )
        rows.append({
            "mean_shift_c": float(shift),
            "split": split,
            "signal_model": "matern_shifted_mean",
            "decision_rule": rule,
            "threshold": threshold,
            "transaction_cost": cost,
            "selected_event_switch_fraction": float(
                group["selected_event_changed_vs_zero"].mean()
            ),
            "trade_decision_switch_fraction": float(
                group["trade_decision_changed_vs_zero"].mean()
            ),
            **metrics,
        })
        panel_rows.append(group)
    return pd.DataFrame(rows), pd.concat(
        panel_rows, ignore_index=True
    )


def finite_difference_pnl_sensitivity(
    shift_summary: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for split in shift_summary["split"].unique():
        table = shift_summary.loc[
            shift_summary["split"] == split
        ].set_index("mean_shift_c")
        for step in map(float, config["finite_difference_steps_c"]):
            if step not in table.index or -step not in table.index:
                continue
            plus = table.loc[step]
            minus = table.loc[-step]
            rows.append({
                "split": split,
                "finite_difference_step_c": step,
                "central_pnl_slope_per_c": float(
                    (
                        plus["total_net_pnl"]
                        - minus["total_net_pnl"]
                    )
                    / (2.0 * step)
                ),
                "trade_count_plus": int(plus["trade_count"]),
                "trade_count_minus": int(minus["trade_count"]),
                "selected_event_switch_fraction_plus": float(
                    plus["selected_event_switch_fraction"]
                ),
                "selected_event_switch_fraction_minus": float(
                    minus["selected_event_switch_fraction"]
                ),
                "interpretation": (
                    "Finite perturbation slope of a discontinuous "
                    "threshold strategy; not a classical derivative."
                ),
            })
    return pd.DataFrame(rows)


def enrich_selected_trade_panel(
    selected_policy: pd.DataFrame,
    weather: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> pd.DataFrame:
    event_sensitivity = sensitivity[
        [
            "target_date",
            "decision_rule",
            "event_order",
            "probability_delta_per_c",
            "probability_gamma_per_c2",
            "event_midpoint_minus_predictive_mean_c",
            "probability_zero_shift_absolute_error",
        ]
    ]
    enriched = selected_policy.merge(
        weather,
        on=["target_date", "decision_rule"],
        how="left",
        validate="many_to_one",
    ).merge(
        event_sensitivity,
        on=["target_date", "decision_rule", "event_order"],
        how="left",
        validate="many_to_one",
    )
    return enriched


def subgroup_trade_attribution(
    enriched_policy: pd.DataFrame,
) -> pd.DataFrame:
    trade = enriched_policy.loc[
        enriched_policy["trade"]
    ].copy()
    rows: list[dict[str, Any]] = []
    variables = {
        "signal_gap": "signal_gap",
        "market_entry_price": "market_probability_raw",
        "absolute_deterministic_error": "deterministic_forecast_error_c",
        "absolute_matern_mean_error": "matern_mean_error_c",
        "absolute_probability_delta": "probability_delta_per_c",
    }
    for output_name, column in variables.items():
        if column not in trade.columns or trade[column].isna().all():
            continue
        values = (
            trade[column].abs()
            if "absolute" in output_name
            else trade[column]
        )
        ranked = values.rank(method="first")
        trade[f"quartile_{output_name}"] = pd.qcut(
            ranked,
            q=min(4, len(trade)),
            labels=False,
            duplicates="drop",
        )
        for (split, quartile), group in trade.groupby(
            ["split", f"quartile_{output_name}"],
            dropna=True,
        ):
            rows.append({
                "stratification": output_name,
                "split": split,
                "quartile": int(quartile) + 1,
                "trades": len(group),
                "mean_stratification_value": float(
                    (
                        group[column].abs()
                        if "absolute" in output_name
                        else group[column]
                    ).mean()
                ),
                "total_net_pnl": float(group["net_pnl"].sum()),
                "mean_net_pnl": float(group["net_pnl"].mean()),
                "hit_rate": float(
                    np.mean(group["net_pnl"] > 0.0)
                ),
            })
    return pd.DataFrame(rows)


def error_pnl_relationships(
    enriched_policy: pd.DataFrame,
) -> pd.DataFrame:
    trade = enriched_policy.loc[
        enriched_policy["trade"]
    ].copy()
    rows: list[dict[str, Any]] = []
    predictors = [
        "deterministic_forecast_error_c",
        "matern_mean_error_c",
        "signal_gap",
        "market_probability_raw",
        "probability_delta_per_c",
        "probability_gamma_per_c2",
    ]
    for split, group in trade.groupby("split", sort=False):
        for predictor in predictors:
            valid = group[[predictor, "net_pnl"]].dropna()
            if len(valid) < 3:
                continue
            pearson = stats.pearsonr(
                valid[predictor], valid["net_pnl"]
            )
            spearman = stats.spearmanr(
                valid[predictor], valid["net_pnl"]
            )
            rows.append({
                "split": split,
                "predictor": predictor,
                "trades": len(valid),
                "pearson_correlation": float(pearson.statistic),
                "pearson_nominal_p_value": float(pearson.pvalue),
                "spearman_correlation": float(spearman.statistic),
                "spearman_nominal_p_value": float(spearman.pvalue),
                "interpretation": (
                    "Descriptive small-sample association; not causal "
                    "and not adjusted for threshold selection."
                ),
            })
    return pd.DataFrame(rows)


def model_specific_external_summary(
    candidates: pd.DataFrame,
    selected_models: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    panels: list[pd.DataFrame] = []
    summaries: list[pd.DataFrame] = []
    for _, policy in selected_models.iterrows():
        panel = materialise_policy(
            candidates,
            policy["signal_model"],
            policy["selected_rule"],
            float(policy["selected_threshold"]),
            float(policy["transaction_cost"]),
        )
        panels.append(panel)
        summaries.append(policy_summary(panel))
    return (
        pd.concat(summaries, ignore_index=True),
        pd.concat(panels, ignore_index=True),
    )


def make_figures(
    selected_policy: pd.DataFrame,
    surface: pd.DataFrame,
    rule_selection: pd.DataFrame,
    attribution_summary: pd.DataFrame,
    shift_summary: pd.DataFrame,
    enriched: pd.DataFrame,
    output_dir: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    dpi = int(config["figure_dpi"])
    registry: list[dict[str, Any]] = []

    # 1. June equity curve.
    june = selected_policy.loc[
        selected_policy["split"] == "june_external"
    ].sort_values("target_date")
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.plot(
        pd.to_datetime(june["target_date"]),
        june["cumulative_net_pnl"],
        marker="o",
        markersize=4,
    )
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_ylabel("Cumulative net PnL")
    ax.set_xlabel("Settlement date")
    ax.set_title("External June PnL of the frozen trading rule")
    fig.tight_layout()
    path = output_dir / "phase7_figure_june_equity_curve.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main-text candidate: June path dependence and concentration",
    })

    # 2. Threshold-cost heatmap.
    june_surface = surface.loc[
        (surface["signal_model"] == "matern")
        & (surface["split"] == "june_external")
        & (
            surface["decision_rule"]
            == config["expected"]["selected_rule"]
        )
    ]
    heat = june_surface.pivot(
        index="transaction_cost",
        columns="threshold",
        values="total_net_pnl",
    ).sort_index()
    fig, ax = plt.subplots(figsize=(10.0, 5.2))
    image = ax.imshow(
        heat.to_numpy(),
        aspect="auto",
        origin="lower",
    )
    ax.set_yticks(range(len(heat.index)))
    ax.set_yticklabels(
        [f"{value:.3f}" for value in heat.index]
    )
    tick_positions = np.linspace(
        0, len(heat.columns) - 1, 6
    ).round().astype(int)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(
        [f"{heat.columns[position]:.2f}" for position in tick_positions]
    )
    ax.set_xlabel("Gap threshold")
    ax.set_ylabel("Transaction cost")
    ax.set_title("June net PnL sensitivity surface")
    fig.colorbar(image, ax=ax, label="Total net PnL")
    fig.tight_layout()
    path = output_dir / "phase7_figure_threshold_cost_surface.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: threshold and cost fragility",
    })

    # 3. Development threshold curve.
    development = surface.loc[
        (surface["signal_model"] == "matern")
        & (surface["split"] == "development")
        & (
            surface["decision_rule"]
            == config["expected"]["selected_rule"]
        )
        & np.isclose(
            surface["transaction_cost"],
            config["expected"]["selected_cost"],
        )
    ].sort_values("threshold")
    selected_threshold = float(
        config["expected"]["selected_threshold"]
    )
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    ax.plot(
        development["threshold"],
        development["mean_daily_net_pnl"],
        marker="o",
        markersize=3,
    )
    ax.fill_between(
        development["threshold"],
        development["mean_daily_net_pnl"]
        - development["standard_error_daily_net_pnl"],
        development["mean_daily_net_pnl"]
        + development["standard_error_daily_net_pnl"],
        alpha=0.2,
    )
    ax.axvline(
        selected_threshold,
        linestyle="--",
        linewidth=1,
    )
    ax.set_xlabel("Gap threshold")
    ax.set_ylabel("Mean development daily net PnL")
    ax.set_title("One-standard-error threshold selection")
    fig.tight_layout()
    path = output_dir / "phase7_figure_development_threshold_selection.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Appendix candidate: development-only policy selection",
    })

    # 4. Model attribution.
    june_attr = attribution_summary.loc[
        attribution_summary["split"] == "june_external"
    ].set_index("signal_model").reindex(MODEL_ORDER)
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.bar(
        june_attr.index,
        june_attr["total_net_pnl"],
    )
    ax.axhline(0.0, linewidth=1)
    ax.set_ylabel("June total net PnL")
    ax.set_title("Common-policy trading attribution by forecast signal")
    fig.tight_layout()
    path = output_dir / "phase7_figure_model_pnl_attribution.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main-text candidate: raw, static and Matérn trading attribution",
    })

    # 5. June trade waterfall.
    trades = june.loc[june["trade"]].copy()
    trades = trades.sort_values("net_pnl")
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.bar(
        range(len(trades)),
        trades["net_pnl"],
    )
    ax.axhline(0.0, linewidth=1)
    ax.set_xlabel("June trades sorted by realised net PnL")
    ax.set_ylabel("Net PnL")
    ax.set_title("Concentration of June trading outcomes")
    fig.tight_layout()
    path = output_dir / "phase7_figure_june_trade_waterfall.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: one-winner concentration",
    })

    # 6. Mean-shift sensitivity.
    shift_june = shift_summary.loc[
        shift_summary["split"] == "june_external"
    ].sort_values("mean_shift_c")
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(
        shift_june["mean_shift_c"],
        shift_june["total_net_pnl"],
        marker="o",
    )
    ax.axhline(0.0, linewidth=1)
    ax.axvline(0.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Perturbation to predictive mean (°C)")
    ax.set_ylabel("June total net PnL")
    ax.set_title("Nonlinear PnL sensitivity to temperature-mean shifts")
    fig.tight_layout()
    path = output_dir / "phase7_figure_mean_shift_pnl_sensitivity.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main-text candidate: Wei Pan delta-like sensitivity",
    })

    # 7. Probability delta and contract location.
    event = enriched.loc[
        enriched["signal_model"] == "matern"
    ].copy()
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ax.scatter(
        event["event_midpoint_minus_predictive_mean_c"],
        event["probability_delta_per_c"],
        s=15,
        alpha=0.5,
    )
    ax.axhline(0.0, linewidth=1)
    ax.axvline(0.0, linewidth=1)
    ax.set_xlabel("Selected event midpoint minus predictive mean (°C)")
    ax.set_ylabel("Event-probability delta per °C")
    ax.set_title("Local probability sensitivity of selected contracts")
    fig.tight_layout()
    path = output_dir / "phase7_figure_probability_delta.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Appendix candidate: analytic probability sensitivity",
    })

    return pd.DataFrame(registry)


def thesis_candidate_summary(
    selected_summary: pd.DataFrame,
    bootstrap: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    concentration: pd.DataFrame,
    shift_summary: pd.DataFrame,
    attribution_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    june = selected_summary.loc[
        selected_summary["split"] == "june_external"
    ].iloc[0]
    ordinary = bootstrap.loc[
        (bootstrap["split"] == "june_external")
        & (bootstrap["bootstrap_method"] == "ordinary_date")
    ].iloc[0]
    for quantity in [
        "trade_count",
        "winning_trades",
        "total_gross_pnl",
        "total_net_pnl",
        "return_on_entry_cash",
        "maximum_drawdown",
        "break_even_cost_per_trade",
    ]:
        rows.append({
            "candidate_id": f"P7_JUNE_{quantity.upper()}",
            "quantity": quantity,
            "point_estimate": june[quantity],
            "lower_95": (
                ordinary["total_pnl_lower_95"]
                if quantity == "total_net_pnl"
                else np.nan
            ),
            "upper_95": (
                ordinary["total_pnl_upper_95"]
                if quantity == "total_net_pnl"
                else np.nan
            ),
            "preferred_location": "Results trading sensitivity",
        })

    conc = concentration.loc[
        concentration["split"] == "june_external"
    ].iloc[0]
    rows.append({
        "candidate_id": "P7_JUNE_TOP1_CONCENTRATION",
        "quantity": "top one absolute PnL contribution share",
        "point_estimate": conc[
            "top_1_absolute_contribution_share"
        ],
        "preferred_location": "Results risk attribution",
    })

    for _, record in cost_sensitivity.loc[
        cost_sensitivity["split"] == "june_external"
    ].iterrows():
        rows.append({
            "candidate_id": (
                f"P7_COST_{record['transaction_cost']:.4f}"
                .replace(".", "_")
            ),
            "quantity": (
                f"June total net PnL at cost "
                f"{record['transaction_cost']:.4f}"
            ),
            "point_estimate": record["total_net_pnl"],
            "preferred_location": "Results cost sensitivity",
        })

    for _, record in shift_summary.loc[
        shift_summary["split"] == "june_external"
    ].iterrows():
        rows.append({
            "candidate_id": (
                f"P7_SHIFT_{record['mean_shift_c']:+.2f}"
                .replace("+", "P")
                .replace("-", "M")
                .replace(".", "_")
            ),
            "quantity": (
                f"June net PnL under "
                f"{record['mean_shift_c']:+.2f}°C mean shift"
            ),
            "point_estimate": record["total_net_pnl"],
            "secondary_value": record["trade_count"],
            "secondary_quantity": "trade count",
            "preferred_location": "Results sensitivity or appendix",
        })

    for _, record in attribution_summary.loc[
        attribution_summary["split"] == "june_external"
    ].iterrows():
        rows.append({
            "candidate_id": (
                f"P7_ATTR_{str(record['signal_model']).upper()}"
            ),
            "quantity": (
                f"June common-policy PnL using "
                f"{record['signal_model']} signal"
            ),
            "point_estimate": record["total_net_pnl"],
            "secondary_value": record["trade_count"],
            "secondary_quantity": "trade count",
            "preferred_location": "Results trading attribution",
        })
    return pd.DataFrame(rows)


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    selected_models: pd.DataFrame,
    selected_summary: pd.DataFrame,
    bootstrap: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    attribution_summary: pd.DataFrame,
    concentration: pd.DataFrame,
    shift_summary: pd.DataFrame,
    finite_difference: pd.DataFrame,
    config: Mapping[str, Any],
) -> None:
    failures = checks.loc[
        bool_series(checks["critical"])
        & ~bool_series(checks["passed"])
    ]
    status = "PASSED" if failures.empty else "FAILED"
    june = selected_summary.loc[
        selected_summary["split"] == "june_external"
    ].iloc[0]
    development = selected_summary.loc[
        selected_summary["split"] == "development"
    ].iloc[0]
    lines = [
        "# Phase 7 — Trading Sensitivity and PnL Attribution",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"## Overall status: **{status}**",
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(dict(provenance), indent=2, sort_keys=True),
        "```",
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Interpretation boundary",
        "",
        config["interpretation_boundary"],
        "",
        "## Development-selected policy",
        "",
        selected_models.to_markdown(index=False),
        "",
        (
            "The selected Matérn policy is event-day open with gap threshold "
            f"{config['expected']['selected_threshold']:.2f} and one-cent "
            "transaction cost. The threshold is selected only from March–May."
        ),
        "",
        "## Frozen-policy performance",
        "",
        selected_summary.to_markdown(index=False),
        "",
        (
            f"June has {int(june['trade_count'])} trades and "
            f"{int(june['winning_trades'])} winning trade. Gross PnL is "
            f"{june['total_gross_pnl']:.6f}; net PnL at one cent is "
            f"{june['total_net_pnl']:.6f}; break-even cost is "
            f"{june['break_even_cost_per_trade']:.6f}."
        ),
        "",
        "## Dependence-robust uncertainty",
        "",
        bootstrap.to_markdown(index=False),
        "",
        "The total-PnL interval includes zero. The positive point estimate is "
        "therefore not robust evidence of executable profitability.",
        "",
        "## Cost sensitivity",
        "",
        cost_sensitivity.loc[
            cost_sensitivity["split"] == "june_external"
        ][
            [
                "transaction_cost",
                "trade_count",
                "total_gross_pnl",
                "total_net_pnl",
                "return_on_entry_cash",
                "maximum_drawdown",
            ]
        ].to_markdown(index=False),
        "",
        "## Trading attribution",
        "",
        attribution_summary.to_markdown(index=False),
        "",
        "This common-policy comparison isolates the effect of replacing the raw "
        "signal by static settlement correction and then by conditional Matérn "
        "post-processing. It is not a causal decomposition.",
        "",
        "## Concentration",
        "",
        concentration.to_markdown(index=False),
        "",
        "## Exact market-period HKO availability",
        "",
        (
            "Exact realised HKO temperatures are used only when present in an "
            "authoritative input panel. Where they are unavailable, Phase 7 "
            "does not manufacture a midpoint proxy. The probability delta, "
            "gamma, mean-shift strategy and realised contract PnL remain fully "
            "identified from the predictive law, event bounds, market prices "
            "and certified settlement outcomes."
        ),
        "",
        "## Temperature-mean perturbation",
        "",
        shift_summary.to_markdown(index=False),
        "",
        finite_difference.to_markdown(index=False),
        "",
        "The probability delta is smooth, but the one-share strategy is not. "
        "Small mean changes can switch the selected contract or cross the "
        "threshold, so the reported PnL slope is a finite perturbation measure "
        "rather than a classical derivative.",
        "",
        "## Thesis use",
        "",
        "- Main text: selected rule, June point estimate, uncertainty interval and cost reversal.",
        "- Main text: raw/static/Matérn common-policy attribution.",
        "- Main text or appendix: mean-shift PnL sensitivity requested from a risk-management perspective.",
        "- Appendix: full threshold-cost surface, block bootstrap, concentration, error quartiles and model-specific policies.",
        "- State explicitly that predictive information, market outperformance and trading profitability are distinct claims.",
        "",
    ]
    (out / "phase7_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    records: list[dict[str, Any]] = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase7_manifest.json",
            "phase7_review_bundle.zip",
        }:
            records.append({
                "relative_path": path.relative_to(out).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    (out / "phase7_manifest.json").write_text(
        json.dumps({
            "phase": "phase7_trading_sensitivity_and_attribution",
            "generated_utc": utc_now(),
            "provenance": dict(provenance),
            "files": records,
        }, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase7_review_bundle.zip"
    with zipfile.ZipFile(
        bundle,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                archive.write(
                    path,
                    path.relative_to(out).as_posix(),
                )


def self_test() -> None:
    assert np.allclose(
        threshold_grid({
            "threshold_grid": {
                "start": 0.0,
                "stop": 0.25,
                "step": 0.01,
            }
        }),
        np.round(np.arange(0.0, 0.251, 0.01), 2),
    )

    asymmetric_rows: list[dict[str, Any]] = []
    for model in ["raw", "static", "matern", "market"]:
        for event_order in range(1, 4):
            asymmetric_rows.append({
                "target_date": "2026-06-01",
                "decision_rule": "event_day_open",
                "split": "june_external",
                "event_order": event_order,
                "event_label": (
                    f"event_{event_order}"
                    if model in {"matern", "market"}
                    else np.nan
                ),
                "event_lower_bound_c": float(event_order - 1),
                "event_upper_bound_c": float(event_order),
                "outcome": 1.0 if event_order == 2 else 0.0,
                "model": model,
                "probability_raw": (
                    [0.2, 0.5, 0.3][event_order - 1]
                    if model == "market"
                    else [0.1, 0.6, 0.3][event_order - 1]
                ),
                "probability_normalised": {
                    "raw": [0.1, 0.6, 0.3],
                    "static": [0.15, 0.55, 0.3],
                    "matern": [0.2, 0.65, 0.15],
                    "market": [0.2, 0.5, 0.3],
                }[model][event_order - 1],
            })
    asymmetric_panel = pd.DataFrame(asymmetric_rows)
    asymmetric_candidates = build_candidate_panel(
        asymmetric_panel,
        {"numerical_tolerance": 1e-10},
    )
    assert len(asymmetric_candidates) == 3
    assert set(asymmetric_candidates["signal_model"]) == {
        "raw",
        "static",
        "matern",
    }
    assert asymmetric_candidates["signal_gap"].notna().all()
    assert (
        asymmetric_candidates.loc[
            asymmetric_candidates["signal_model"] == "matern",
            "event_order",
        ].iloc[0]
        == 2
    )

    market_predictions = pd.DataFrame({
        "target_date": ["2026-06-01", "2026-06-02"],
        "decision_rule": ["event_day_open", "event_day_open"],
        "forecast_daily_max_c": [30.0, 31.0],
        "gp_temperature_mean_c": [30.5, 31.5],
        "gp_temperature_std_c": [1.2, 1.3],
    })
    nonoverlapping_validation = pd.DataFrame({
        "target_date": ["2026-03-01"],
        "decision_rule": ["event_day_open"],
        "hko_daily_max_c": [25.0],
        "forecast_daily_max_c": [24.5],
    })
    prepared = prepare_weather_panel(
        market_predictions,
        nonoverlapping_validation,
    )
    assert len(prepared) == 2
    assert prepared["hko_daily_max_c"].isna().all()
    assert not prepared["realised_hko_available"].any()
    assert prepared["temperature_predictive_mean_c"].notna().all()

    market_predictions_with_hko = market_predictions.copy()
    market_predictions_with_hko["hko_daily_max_c"] = [30.2, 31.4]
    prepared_with_hko = prepare_weather_panel(
        market_predictions_with_hko,
        nonoverlapping_validation,
    )
    assert prepared_with_hko["realised_hko_available"].all()
    assert np.allclose(
        prepared_with_hko["hko_daily_max_c"],
        [30.2, 31.4],
    )

    synthetic = pd.DataFrame({
        "target_date": [f"2026-06-{day:02d}" for day in range(1, 6)],
        "outcome": [0, 1, 0, 0, 1],
        "market_probability_raw": [0.1, 0.2, 0.05, 0.4, 0.3],
    })
    mask = np.array([True, True, False, True, False])
    metrics = strategy_metrics(synthetic, mask, 0.01)
    expected = (
        (-0.1 - 0.01)
        + (0.8 - 0.01)
        + (-0.4 - 0.01)
    )
    assert abs(metrics["total_net_pnl"] - expected) < 1e-12
    assert metrics["trade_count"] == 3

    lower = np.array([-np.inf, 19.0, 20.0])
    upper = np.array([19.0, 20.0, np.inf])
    mean = np.array([20.0, 20.0, 20.0])
    sd = np.array([1.0, 1.0, 1.0])
    probability = gaussian_event_probability(lower, upper, mean, sd)
    assert abs(probability.sum() - 1.0) < 1e-12
    delta = gaussian_event_delta(lower, upper, mean, sd)
    assert abs(delta.sum()) < 1e-12

    rng = np.random.default_rng(123)
    assert ordinary_indices(20, 5, rng).shape == (5, 20)
    rng = np.random.default_rng(123)
    assert moving_block_indices(20, 5, 5, rng).shape == (5, 20)

    print("SELF-TEST: PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    if any(
        value is None
        for value in [
            args.repo_root,
            args.spec,
            args.output_root,
        ]
    ):
        raise SystemExit(
            "--repo-root, --spec and --output-root are required"
        )

    repo_root = args.repo_root.resolve()
    spec_path = (repo_root / args.spec).resolve()
    out = (repo_root / args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    figures_dir = out / "figures"
    config = json.loads(spec_path.read_text(encoding="utf-8"))
    inputs = config["input_paths"]

    dependency_rows: list[dict[str, Any]] = []
    for label, key in [
        ("Phase 1", "phase1_completion"),
        ("Phase 2", "phase2_integrity"),
        ("Phase 3", "phase3_integrity"),
        ("Phase 4", "phase4_integrity"),
        ("Phase 5", "phase5_integrity"),
        ("Phase 6", "phase6_integrity"),
    ]:
        passed, detail = dependency_check(
            repo_root / inputs[key],
            label,
        )
        dependency_rows.append({
            "check": f"{label.lower().replace(' ', '')}_dependency",
            "passed": passed,
            "critical": True,
            "detail": detail,
        })

    phase6_path = repo_root / inputs["phase6_exact_support_panel"]
    validation_path = repo_root / inputs["phase5_selected_matern_panel"]
    market_prediction_path = (
        repo_root / inputs["phase8_market_period_predictions"]
    )
    for path in [
        phase6_path,
        validation_path,
        market_prediction_path,
    ]:
        if not path.is_file():
            raise FileNotFoundError(path)

    provenance = {
        "generated_utc": utc_now(),
        "working_branch": git(repo_root, "branch", "--show-current"),
        "working_commit": git(repo_root, "rev-parse", "HEAD"),
        "phase6_exact_support_panel": inputs[
            "phase6_exact_support_panel"
        ],
        "phase6_exact_support_panel_sha256": sha256_file(phase6_path),
        "phase5_selected_matern_panel": inputs[
            "phase5_selected_matern_panel"
        ],
        "phase5_selected_matern_panel_sha256": sha256_file(
            validation_path
        ),
        "phase8_market_period_predictions": inputs[
            "phase8_market_period_predictions"
        ],
        "phase8_market_period_predictions_sha256": sha256_file(
            market_prediction_path
        ),
        "bootstrap_replications": config["bootstrap"]["replications"],
        "bootstrap_seed": config["bootstrap"]["seed"],
        "moving_block_lengths": config["bootstrap"][
            "moving_block_lengths"
        ],
        "interpretation_boundary": config[
            "interpretation_boundary"
        ],
    }
    (out / "phase7_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    panel = pd.read_csv(
        phase6_path,
        compression="gzip",
        low_memory=False,
    )
    validation_raw = pd.read_csv(
        validation_path,
        compression="gzip",
        low_memory=False,
    )
    market_prediction_raw = pd.read_csv(
        market_prediction_path,
        low_memory=False,
    )
    panel["target_date"] = pd.to_datetime(
        panel["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    panel["probability_raw"] = pd.to_numeric(
        panel["probability_raw"], errors="coerce"
    )
    panel["probability_normalised"] = pd.to_numeric(
        panel["probability_normalised"], errors="coerce"
    )
    panel["outcome"] = pd.to_numeric(
        panel["outcome"], errors="coerce"
    )
    panel["event_lower_bound_c"] = pd.to_numeric(
        panel["event_lower_bound_c"], errors="coerce"
    )
    panel["event_upper_bound_c"] = pd.to_numeric(
        panel["event_upper_bound_c"], errors="coerce"
    )

    panel_checks = validate_phase6_panel(panel, config)
    initial_checks = pd.concat(
        [pd.DataFrame(dependency_rows), panel_checks],
        ignore_index=True,
    )
    initial_checks.to_csv(
        out / "phase7_integrity_checks.csv",
        index=False,
    )
    failures = initial_checks.loc[
        bool_series(initial_checks["critical"])
        & ~bool_series(initial_checks["passed"])
    ]
    if not failures.empty:
        print(initial_checks.to_string(index=False))
        raise RuntimeError("Phase 7 input checks failed")

    weather = prepare_weather_panel(
        market_prediction_raw,
        validation_raw,
    )
    weather.to_csv(
        out / "phase7_market_period_predictive_law_panel.csv",
        index=False,
    )
    pd.DataFrame([{
        "market_prediction_rows": len(weather),
        "rows_with_exact_hko": int(
            weather["realised_hko_available"].sum()
        ),
        "coverage_fraction": float(
            weather["realised_hko_available"].mean()
        ),
        "sources": "|".join(
            sorted(
                weather["realised_hko_source"]
                .astype(str)
                .unique()
            )
        ),
        "exact_error_analysis_available": bool(
            weather["realised_hko_available"].any()
        ),
        "interpretation": (
            "Exact temperature-error diagnostics are computed only where "
            "an actual HKO value is present. No interval midpoint proxy is used."
        ),
    }]).to_csv(
        out / "phase7_market_period_hko_availability.csv",
        index=False,
    )
    candidates = build_candidate_panel(panel, config)
    candidates.to_csv(
        out / "phase7_candidate_trade_panel.csv.gz",
        index=False,
        compression="gzip",
    )

    surface = build_threshold_cost_surface(candidates, config)
    surface.to_csv(
        out / "phase7_threshold_cost_surface.csv.gz",
        index=False,
        compression="gzip",
    )

    rule_selection, selected_models = select_development_policies(
        surface,
        config,
    )
    rule_selection.to_csv(
        out / "phase7_development_rule_threshold_selection.csv",
        index=False,
    )
    selected_models.to_csv(
        out / "phase7_model_specific_selected_policies.csv",
        index=False,
    )

    selected = selected_models.loc[
        selected_models["signal_model"]
        == config["expected"]["selected_model"]
    ].iloc[0]
    selected_policy = materialise_policy(
        candidates,
        selected["signal_model"],
        selected["selected_rule"],
        float(selected["selected_threshold"]),
        float(selected["transaction_cost"]),
    )
    selected_policy.to_csv(
        out / "phase7_selected_policy_daily_panel.csv",
        index=False,
    )
    selected_summary = policy_summary(selected_policy)
    selected_summary.to_csv(
        out / "phase7_selected_policy_summary.csv",
        index=False,
    )

    bootstrap_frames: list[pd.DataFrame] = []
    distribution_frames: list[pd.DataFrame] = []
    seed_offset = 0
    for split, group in selected_policy.groupby("split", sort=False):
        intervals, distribution = bootstrap_policy_pnl(
            group,
            config,
            {
                "signal_model": selected["signal_model"],
                "decision_rule": selected["selected_rule"],
                "threshold": selected["selected_threshold"],
                "transaction_cost": selected["transaction_cost"],
                "split": split,
            },
            seed_offset,
        )
        bootstrap_frames.append(intervals)
        distribution_frames.append(distribution)
        seed_offset += 1000
    bootstrap = pd.concat(bootstrap_frames, ignore_index=True)
    bootstrap.to_csv(
        out / "phase7_selected_policy_bootstrap_intervals.csv",
        index=False,
    )
    pd.concat(distribution_frames, ignore_index=True).to_csv(
        out / "phase7_selected_policy_ordinary_bootstrap_distribution.csv.gz",
        index=False,
        compression="gzip",
    )

    cost_sensitivity = cost_sensitivity_for_policy(
        candidates,
        selected["signal_model"],
        selected["selected_rule"],
        float(selected["selected_threshold"]),
        config,
    )
    cost_sensitivity.to_csv(
        out / "phase7_selected_policy_cost_sensitivity.csv",
        index=False,
    )

    common_panels, attribution_summary, attribution_panel = (
        fixed_policy_model_attribution(candidates, config)
    )
    common_panels.to_csv(
        out / "phase7_common_policy_model_panels.csv.gz",
        index=False,
        compression="gzip",
    )
    attribution_summary.to_csv(
        out / "phase7_common_policy_model_summary.csv",
        index=False,
    )
    attribution_panel.to_csv(
        out / "phase7_common_policy_attribution_panel.csv",
        index=False,
    )
    attribution_bootstrap = bootstrap_attribution(
        attribution_panel,
        config,
    )
    attribution_bootstrap.to_csv(
        out / "phase7_common_policy_attribution_bootstrap.csv",
        index=False,
    )

    model_specific_summary, model_specific_panels = (
        model_specific_external_summary(candidates, selected_models)
    )
    model_specific_summary.to_csv(
        out / "phase7_model_specific_external_summary.csv",
        index=False,
    )
    model_specific_panels.to_csv(
        out / "phase7_model_specific_policy_panels.csv.gz",
        index=False,
        compression="gzip",
    )

    concentration, influence = trade_concentration(selected_policy)
    concentration.to_csv(
        out / "phase7_trade_concentration_summary.csv",
        index=False,
    )
    influence.to_csv(
        out / "phase7_leave_one_trade_out_influence.csv",
        index=False,
    )

    (
        probability_sensitivity,
        shifted_events,
        shifted_candidates,
    ) = build_probability_sensitivity_panel(
        panel,
        weather,
        config,
    )
    probability_sensitivity.to_csv(
        out / "phase7_probability_delta_gamma_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    shifted_events.to_csv(
        out / "phase7_shifted_event_probability_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    shifted_candidates.to_csv(
        out / "phase7_shifted_candidate_panel.csv.gz",
        index=False,
        compression="gzip",
    )

    shift_summary, shift_policy_panel = (
        mean_shift_strategy_sensitivity(
            shifted_candidates,
            config,
        )
    )
    shift_summary.to_csv(
        out / "phase7_mean_shift_strategy_sensitivity.csv",
        index=False,
    )
    shift_policy_panel.to_csv(
        out / "phase7_mean_shift_policy_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    finite_difference = finite_difference_pnl_sensitivity(
        shift_summary,
        config,
    )
    finite_difference.to_csv(
        out / "phase7_finite_difference_pnl_sensitivity.csv",
        index=False,
    )

    enriched = enrich_selected_trade_panel(
        selected_policy,
        weather,
        probability_sensitivity,
    )
    enriched.to_csv(
        out / "phase7_selected_policy_error_sensitivity_panel.csv",
        index=False,
    )
    subgroup = subgroup_trade_attribution(enriched)
    subgroup.to_csv(
        out / "phase7_trade_subgroup_attribution.csv",
        index=False,
    )
    relationships = error_pnl_relationships(enriched)
    relationships.to_csv(
        out / "phase7_error_pnl_relationships.csv",
        index=False,
    )

    figure_registry = make_figures(
        selected_policy,
        surface,
        rule_selection,
        attribution_summary,
        shift_summary,
        enriched,
        figures_dir,
        config,
    )
    figure_registry.to_csv(
        out / "phase7_figure_registry.csv",
        index=False,
    )

    candidate_summary = thesis_candidate_summary(
        selected_summary,
        bootstrap,
        cost_sensitivity,
        concentration,
        shift_summary,
        attribution_summary,
    )
    candidate_summary.to_csv(
        out / "phase7_thesis_candidate_summary.csv",
        index=False,
    )

    expected = config["expected"]
    selected_row = selected_models.loc[
        selected_models["signal_model"] == "matern"
    ].iloc[0]
    june = selected_summary.loc[
        selected_summary["split"] == "june_external"
    ].iloc[0]
    zero_shift_error = float(
        probability_sensitivity[
            "probability_zero_shift_absolute_error"
        ].max()
    )
    reference_checks: list[dict[str, Any]] = [
        {
            "check": "candidate_rows",
            "passed": len(candidates)
            == expected["candidate_rows"],
            "critical": True,
            "detail": f"rows={len(candidates)}",
        },
        {
            "check": "development_selects_event_day_open",
            "passed": selected_row["selected_rule"]
            == expected["selected_rule"],
            "critical": True,
            "detail": (
                f"calculated={selected_row['selected_rule']}; "
                f"reference={expected['selected_rule']}"
            ),
        },
        {
            "check": "development_selects_threshold_012",
            "passed": abs(
                float(selected_row["selected_threshold"])
                - float(expected["selected_threshold"])
            ) <= 1e-12,
            "critical": True,
            "detail": (
                f"calculated={float(selected_row['selected_threshold']):.6f}"
            ),
        },
        {
            "check": "june_selected_trade_count",
            "passed": int(june["trade_count"])
            == expected["june_selected_trades"],
            "critical": True,
            "detail": f"calculated={int(june['trade_count'])}",
        },
        {
            "check": "june_selected_winning_trades",
            "passed": int(june["winning_trades"])
            == expected["june_selected_winning_trades"],
            "critical": True,
            "detail": f"calculated={int(june['winning_trades'])}",
        },
        {
            "check": "june_selected_gross_pnl",
            "passed": abs(
                float(june["total_gross_pnl"])
                - expected["june_selected_gross_pnl"]
            ) <= 1e-12,
            "critical": True,
            "detail": (
                f"calculated={float(june['total_gross_pnl']):.9f}"
            ),
        },
        {
            "check": "june_selected_net_pnl",
            "passed": abs(
                float(june["total_net_pnl"])
                - expected["june_selected_net_pnl"]
            ) <= 1e-12,
            "critical": True,
            "detail": (
                f"calculated={float(june['total_net_pnl']):.9f}"
            ),
        },
        {
            "check": "june_break_even_cost",
            "passed": abs(
                float(june["break_even_cost_per_trade"])
                - expected["june_break_even_cost"]
            ) <= 1e-12,
            "critical": True,
            "detail": (
                f"calculated="
                f"{float(june['break_even_cost_per_trade']):.9f}"
            ),
        },
        {
            "check": "zero_shift_reproduces_frozen_matern_probabilities",
            "passed": zero_shift_error
            <= float(config["probability_reconciliation_tolerance"]),
            "critical": True,
            "detail": f"maximum_error={zero_shift_error:.3e}",
        },
    ]

    for cost_text, reference in config[
        "reference_cost_sensitivity"
    ].items():
        cost = float(cost_text)
        row = cost_sensitivity.loc[
            (cost_sensitivity["split"] == "june_external")
            & np.isclose(
                cost_sensitivity["transaction_cost"], cost
            )
        ].iloc[0]
        calculated = float(row["total_net_pnl"])
        reference_checks.append({
            "check": (
                f"june_cost_sensitivity_{cost:.4f}"
                .replace(".", "_")
            ),
            "passed": abs(calculated - float(reference)) <= 1e-12,
            "critical": True,
            "detail": (
                f"calculated={calculated:.9f}; "
                f"reference={float(reference):.9f}"
            ),
        })

    ordinary_june = bootstrap.loc[
        (bootstrap["split"] == "june_external")
        & (bootstrap["bootstrap_method"] == "ordinary_date")
    ].iloc[0]
    output_checks = [
        {
            "check": "market_period_predictive_law_join_complete",
            "passed": len(
                probability_sensitivity[
                    ["target_date", "decision_rule"]
                ].drop_duplicates()
            )
            == expected["exact_support_books"],
            "critical": True,
            "detail": (
                f"books="
                f"{len(probability_sensitivity[['target_date','decision_rule']].drop_duplicates())}"
            ),
        },
        {
            "check": "market_period_hko_availability_registered",
            "passed": True,
            "critical": False,
            "detail": (
                f"available_rows={int(weather['realised_hko_available'].sum())}; "
                f"total_rows={len(weather)}; "
                f"sources={sorted(weather['realised_hko_source'].astype(str).unique())}"
            ),
        },
        {
            "check": "deterministic_forecast_crosscheck",
            "passed": bool(
                weather[
                    "forecast_daily_max_crosscheck_difference_c"
                ].dropna().empty
                or (
                    weather[
                        "forecast_daily_max_crosscheck_difference_c"
                    ].dropna().abs().max()
                    <= 1e-10
                )
            ),
            "critical": True,
            "detail": (
                "maximum_difference="
                f"{weather['forecast_daily_max_crosscheck_difference_c'].dropna().abs().max() if not weather['forecast_daily_max_crosscheck_difference_c'].dropna().empty else float('nan'):.3e}"
            ),
        },
        {
            "check": "threshold_cost_surface_complete",
            "passed": not surface.empty
            and set(surface["signal_model"].unique())
            == set(MODEL_ORDER),
            "critical": True,
            "detail": f"rows={len(surface)}",
        },
        {
            "check": "pnl_bootstrap_methods",
            "passed": set(bootstrap["bootstrap_method"].unique())
            == {"ordinary_date", "circular_moving_block"},
            "critical": True,
            "detail": (
                f"methods="
                f"{sorted(bootstrap['bootstrap_method'].unique())}"
            ),
        },
        {
            "check": "june_pnl_interval_contains_zero",
            "passed": bool(
                ordinary_june["total_pnl_lower_95"] <= 0.0
                <= ordinary_june["total_pnl_upper_95"]
            ),
            "critical": True,
            "detail": (
                f"interval=[{ordinary_june['total_pnl_lower_95']:.6f},"
                f"{ordinary_june['total_pnl_upper_95']:.6f}]"
            ),
        },
        {
            "check": "mean_shift_grid_complete",
            "passed": set(
                shift_summary["mean_shift_c"].round(6).unique()
            )
            == set(
                np.round(config["mean_shift_grid_c"], 6)
            ),
            "critical": True,
            "detail": (
                f"shifts={sorted(shift_summary['mean_shift_c'].unique())}"
            ),
        },
        {
            "check": "attribution_models_complete",
            "passed": set(
                attribution_summary["signal_model"].unique()
            )
            == set(MODEL_ORDER),
            "critical": True,
            "detail": (
                f"models="
                f"{sorted(attribution_summary['signal_model'].unique())}"
            ),
        },
        {
            "check": "figures_created",
            "passed": len(figure_registry) == 7
            and all(
                (figures_dir / name).is_file()
                for name in figure_registry["figure"]
            ),
            "critical": True,
            "detail": f"figures={len(figure_registry)}",
        },
    ]

    all_checks = pd.concat(
        [
            initial_checks,
            pd.DataFrame(reference_checks),
            pd.DataFrame(output_checks),
        ],
        ignore_index=True,
    )
    all_checks.to_csv(
        out / "phase7_integrity_checks.csv",
        index=False,
    )

    write_report(
        out,
        provenance,
        all_checks,
        selected_models,
        selected_summary,
        bootstrap,
        cost_sensitivity,
        attribution_summary,
        concentration,
        shift_summary,
        finite_difference,
        config,
    )
    build_manifest(out, provenance)
    make_review_bundle(out)

    final_failures = all_checks.loc[
        bool_series(all_checks["critical"])
        & ~bool_series(all_checks["passed"])
    ]
    print("=" * 96)
    print("PHASE 7 — TRADING SENSITIVITY AND PNL ATTRIBUTION")
    print("=" * 96)
    print(all_checks.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase7_review_bundle.zip'}")
    if final_failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print(final_failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
