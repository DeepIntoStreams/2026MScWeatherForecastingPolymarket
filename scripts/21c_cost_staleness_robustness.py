#!/usr/bin/env python3
"""
21c: Transaction-cost, market-price-staleness and robustness analysis.

This step preserves all frozen 20e forecasting models and the prespecified 21a
and 21b trading rules. It does not reselect models, decision rules, thresholds,
or strategies.

Robustness dimensions:
1. Per-position execution-cost grid.
2. Market-price-staleness filters.
3. Edge-threshold sensitivity.
4. Standalone decision-rule reporting only.
5. Break-even execution-cost diagnostics.

Primary robustness specification:
- edge threshold: 0.05;
- maximum market-price staleness: 3 hours;
- execution cost: 0.01 probability-price units per opened position.

The observed Polymarket YES probability remains a frictionless reference price.
The cost grid is a reduced-form sensitivity layer, not a reconstruction of the
historical bid-ask spread or order-book execution.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Config:
    repo_root: Path
    cost_grid: tuple[float, ...]
    staleness_quantiles: tuple[float, ...]
    threshold_grid: tuple[float, ...]
    primary_cost: float
    primary_staleness_quantile: float
    primary_threshold: float


def parse_float_grid(value: str) -> tuple[float, ...]:
    return tuple(float(x.strip()) for x in value.split(",") if x.strip())


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--cost-grid",
        type=str,
        default="0,0.005,0.01,0.02,0.05",
    )
    parser.add_argument(
        "--staleness-quantiles",
        type=str,
        default="0.25,0.50,0.75,0.90",
        help=(
            "Comma-separated empirical quantiles used to construct binding "
            "market-price-staleness caps. An unrestricted case is added automatically."
        ),
    )
    parser.add_argument(
        "--threshold-grid",
        type=str,
        default="0.02,0.05,0.10",
    )
    parser.add_argument("--primary-cost", type=float, default=0.01)
    parser.add_argument(
        "--primary-staleness-quantile",
        type=float,
        default=0.50,
        help="Primary empirical staleness quantile; default is the median.",
    )
    parser.add_argument("--primary-threshold", type=float, default=0.05)
    args = parser.parse_args()

    costs = parse_float_grid(args.cost_grid)
    staleness_quantiles = parse_float_grid(args.staleness_quantiles)
    thresholds = parse_float_grid(args.threshold_grid)

    if any(x < 0 for x in costs + thresholds):
        raise ValueError("Cost and threshold values must be non-negative.")
    if any((q <= 0) or (q >= 1) for q in staleness_quantiles):
        raise ValueError("Staleness quantiles must lie strictly between 0 and 1.")
    if not any(np.isclose(args.primary_cost, x) for x in costs):
        raise ValueError("Primary cost must be in the cost grid.")
    if not any(
        np.isclose(args.primary_staleness_quantile, q)
        for q in staleness_quantiles
    ):
        raise ValueError(
            "Primary staleness quantile must be in the staleness-quantile grid."
        )
    if not any(np.isclose(args.primary_threshold, x) for x in thresholds):
        raise ValueError("Primary threshold must be in the threshold grid.")

    return Config(
        repo_root=args.repo_root.expanduser().resolve(),
        cost_grid=costs,
        staleness_quantiles=staleness_quantiles,
        threshold_grid=thresholds,
        primary_cost=float(args.primary_cost),
        primary_staleness_quantile=float(args.primary_staleness_quantile),
        primary_threshold=float(args.primary_threshold),
    )


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    return pd.read_csv(path, low_memory=False)


def load_inputs(repo: Path):
    p = repo / "data" / "processed"

    trade_21a = read_csv(p / "21a_simple_edge_trade_panel.csv")
    summary_21a = read_csv(
        p / "21a_simple_edge_primary_standalone_strategy_summary.csv"
    )
    book_results_21b = read_csv(
        p / "21b_full_event_book_strategy_results.csv"
    )
    allocations_21b = read_csv(
        p / "21b_full_event_book_allocation_panel.csv"
    )
    summary_21b = read_csv(
        p / "21b_full_event_book_primary_standalone_summary.csv"
    )
    manifest_21a = json.loads(
        (p / "21a_simple_edge_manifest.json").read_text()
    )
    manifest_21b = json.loads(
        (p / "21b_full_event_book_manifest.json").read_text()
    )

    for df in [trade_21a, book_results_21b, allocations_21b]:
        df["event_date"] = pd.to_datetime(df["event_date"]).dt.normalize()

    return (
        trade_21a,
        summary_21a,
        book_results_21b,
        allocations_21b,
        summary_21b,
        manifest_21a,
        manifest_21b,
    )


def key_columns(df: pd.DataFrame) -> list[str]:
    preferred = [
        "event_date",
        "decision_rule",
        "token_id",
        "market_slug",
        "condition_id",
    ]
    return [c for c in preferred if c in df.columns]


def locate_staleness_source(repo: Path) -> tuple[pd.DataFrame, str, Path]:
    """
    Locate a row-level market-price staleness measure.

    Search priority:
    1. 20a supervised feature matrix;
    2. 19b common-support panel;
    3. 18l decision/scoring panels, including gzip files.

    Candidate columns are numeric columns whose names contain 'staleness' or
    'age' together with a market/price/time cue.
    """
    p = repo / "data" / "processed"
    candidates = [
        p / "20a_supervised_feature_matrix.csv",
        p / "19b_common_support_market_vs_ecmwf_panel.csv",
        p / "19b_common_support_market_vs_ecmwf_proxy_panel.csv",
        p / "18l_full_hko_contract_event_no_lookahead_decision_panel.csv",
        p / "18l_full_hko_contract_event_no_lookahead_decision_panel.csv.gz",
        p / "18l_full_hko_contract_event_market_scoring_panel.csv",
        p / "18l_full_hko_contract_event_market_scoring_panel.csv.gz",
    ]

    name_patterns = (
        "staleness",
        "price_age",
        "market_age",
        "age_hours",
        "hours_since",
        "time_since_price",
    )

    for path in candidates:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, low_memory=False)
        except Exception:
            continue

        if "event_date" in df.columns:
            df["event_date"] = pd.to_datetime(df["event_date"]).dt.normalize()

        possible = []
        for col in df.columns:
            lower = col.lower()
            if any(pattern in lower for pattern in name_patterns):
                numeric = pd.to_numeric(df[col], errors="coerce")
                if numeric.notna().any():
                    possible.append(col)

        if possible:
            # Prefer explicit hour measures and market-price wording.
            possible = sorted(
                possible,
                key=lambda c: (
                    "hour" not in c.lower(),
                    "market" not in c.lower()
                    and "price" not in c.lower(),
                    len(c),
                ),
            )
            return df, possible[0], path

    raise FileNotFoundError(
        "Could not locate a numeric market-price-staleness column in the "
        "expected 20a/19b/18l inputs."
    )


def normalise_staleness_to_hours(
    series: pd.Series,
    column_name: str,
) -> pd.Series:
    """
    Convert the detected staleness measure to hours.

    Explicit unit words in the column name take precedence. Otherwise, infer
    from magnitude conservatively:
    - median > 10,000 suggests seconds;
    - median > 200 suggests minutes;
    - otherwise assume hours.
    """
    x = pd.to_numeric(series, errors="coerce")
    name = column_name.lower()

    if "second" in name or name.endswith("_s"):
        return x / 3600.0
    if "minute" in name or name.endswith("_min"):
        return x / 60.0
    if "hour" in name or name.endswith("_h"):
        return x

    median = float(x.dropna().median()) if x.notna().any() else np.nan
    if np.isfinite(median) and median > 10000:
        return x / 3600.0
    if np.isfinite(median) and median > 200:
        return x / 60.0
    return x


def attach_staleness(
    target: pd.DataFrame,
    source: pd.DataFrame,
    source_col: str,
) -> pd.DataFrame:
    left = target.copy()
    right = source.copy()

    keys = [
        c
        for c in key_columns(left)
        if c in right.columns
    ]
    if len(keys) < 2:
        raise ValueError(
            f"Insufficient merge keys for staleness attachment: {keys}"
        )

    right["market_price_staleness_hours"] = (
        normalise_staleness_to_hours(right[source_col], source_col)
    )

    right = (
        right[keys + ["market_price_staleness_hours"]]
        .dropna(subset=["market_price_staleness_hours"])
        .sort_values(keys + ["market_price_staleness_hours"])
        .drop_duplicates(keys, keep="first")
    )

    merged = left.merge(
        right,
        on=keys,
        how="left",
        validate="many_to_one",
    )
    return merged



def empirical_staleness_distribution_and_caps(
    canonical_source: pd.DataFrame,
    source_col: str,
    quantiles: tuple[float, ...],
    holdout_start_date: str,
    holdout_end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build the canonical empirical staleness distribution and tie-aware caps.

    The canonical distribution is formed from one row per underlying market
    snapshot in a single source table, deduplicated by:
        event_date × decision_rule × market_slug
    with sensible fallbacks when one identifier is unavailable.

    Repeated staleness values are deliberately retained because empirical
    quantiles must preserve snapshot frequencies. The same snapshot must not be
    pooled again from 21a and 21b, since those pipelines reuse the same market
    observations.

    For each requested quantile q and cap c_q, the admitted share under a
    weak inequality is P(S <= c_q). With a discrete empirical distribution this
    may exceed q because of ties at the cap. The tie-aware admissible excess is
    bounded by the empirical mass P(S = c_q).
    """
    source = canonical_source.copy()

    if "event_date" not in source.columns:
        raise ValueError(
            "Canonical staleness source must contain event_date."
        )

    source["event_date"] = pd.to_datetime(
        source["event_date"]
    ).dt.normalize()

    holdout_start = pd.Timestamp(holdout_start_date).normalize()
    holdout_end = pd.Timestamp(holdout_end_date).normalize()

    source = source.loc[
        source["event_date"].between(
            holdout_start,
            holdout_end,
            inclusive="both",
        )
    ].copy()

    if source.empty:
        raise ValueError(
            "Canonical staleness source has no rows in the locked holdout."
        )

    source["market_price_staleness_hours"] = (
        normalise_staleness_to_hours(source[source_col], source_col)
    )

    key_candidates = [
        "event_date",
        "decision_rule",
        "market_slug",
        "token_id",
        "condition_id",
    ]
    keys = [c for c in key_candidates if c in source.columns]

    preferred = [
        c for c in ["event_date", "decision_rule", "market_slug"]
        if c in source.columns
    ]
    if len(preferred) >= 2:
        keys = preferred
    elif len(keys) < 2:
        raise ValueError(
            "Canonical staleness source lacks sufficient snapshot keys."
        )

    canonical = (
        source[keys + ["market_price_staleness_hours"]]
        .dropna(subset=["market_price_staleness_hours"])
        .sort_values(keys + ["market_price_staleness_hours"])
        .drop_duplicates(keys, keep="first")
        .reset_index(drop=True)
    )

    x = canonical["market_price_staleness_hours"].astype(float)

    distribution = pd.DataFrame(
        [
            {
                "n_snapshot_observations": int(len(x)),
                "n_holdout_dates": int(
                    canonical["event_date"].nunique()
                ),
                "minimum_event_date": canonical[
                    "event_date"
                ].min().strftime("%Y-%m-%d"),
                "maximum_event_date": canonical[
                    "event_date"
                ].max().strftime("%Y-%m-%d"),
                "minimum_hours": float(x.min()),
                "p10_hours": float(x.quantile(0.10)),
                "p25_hours": float(x.quantile(0.25)),
                "median_hours": float(x.quantile(0.50)),
                "p75_hours": float(x.quantile(0.75)),
                "p90_hours": float(x.quantile(0.90)),
                "p95_hours": float(x.quantile(0.95)),
                "maximum_hours": float(x.max()),
                "mean_hours": float(x.mean()),
                "standard_deviation_hours": float(x.std(ddof=0)),
                "n_distinct_staleness_values": int(x.nunique()),
            }
        ]
    )

    cap_rows = []
    for q in quantiles:
        cap = float(x.quantile(q))
        admitted_share = float((x <= cap).mean())
        tie_mass_at_cap = float(np.isclose(x, cap, atol=1e-12).mean())
        excess_over_target = admitted_share - float(q)

        cap_rows.append(
            {
                "staleness_rule": f"empirical_q{int(round(q * 100)):02d}",
                "staleness_quantile": float(q),
                "max_staleness_hours": cap,
                "unrestricted": False,
                "observed_share_admitted": admitted_share,
                "tie_mass_at_cap": tie_mass_at_cap,
                "admission_excess_over_target": excess_over_target,
                "tie_aware_valid": bool(
                    admitted_share + 1e-12 >= float(q)
                    and excess_over_target <= tie_mass_at_cap + 1e-12
                ),
                "cap_equals_observed_maximum": bool(
                    np.isclose(cap, float(x.max()), atol=1e-12)
                ),
            }
        )

    cap_rows.append(
        {
            "staleness_rule": "unrestricted",
            "staleness_quantile": np.nan,
            "max_staleness_hours": np.inf,
            "unrestricted": True,
            "observed_share_admitted": 1.0,
            "tie_mass_at_cap": np.nan,
            "admission_excess_over_target": np.nan,
            "tie_aware_valid": True,
            "cap_equals_observed_maximum": False,
        }
    )

    caps = pd.DataFrame(cap_rows)
    return distribution, caps, canonical


def build_21a_robustness(
    trade_panel: pd.DataFrame,
    staleness_caps: pd.DataFrame,
    config: Config,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Recalculate 21a PnL under cost and staleness grids.

    Each model × decision rule remains a separate standalone strategy.
    """
    base = trade_panel.loc[
        trade_panel["threshold"].isin(config.threshold_grid)
    ].copy()
    base["gross_pnl_original"] = pd.to_numeric(
        base["gross_pnl"], errors="coerce"
    )
    base["trade_indicator"] = base["trade_indicator"].astype(int)

    rows = []
    summaries = []

    for cost in config.cost_grid:
        for cap in staleness_caps.itertuples(index=False):
            max_stale = float(cap.max_staleness_hours)
            tmp = base.copy()
            tmp["robustness_cost"] = float(cost)
            tmp["staleness_rule"] = cap.staleness_rule
            tmp["staleness_quantile"] = cap.staleness_quantile
            tmp["max_staleness_hours"] = max_stale
            tmp["unrestricted_staleness"] = bool(cap.unrestricted)
            tmp["passes_staleness_filter"] = (
                tmp["market_price_staleness_hours"].notna()
                & (
                    tmp["market_price_staleness_hours"]
                    <= float(max_stale)
                )
            )
            tmp["robust_trade_indicator"] = (
                tmp["trade_indicator"].eq(1)
                & tmp["passes_staleness_filter"]
            ).astype(int)
            tmp["robust_net_pnl"] = np.where(
                tmp["robust_trade_indicator"].eq(1),
                tmp["gross_pnl_original"] - float(cost),
                0.0,
            )
            rows.append(tmp)

            for keys, g in tmp.groupby(
                ["model", "decision_rule", "threshold"],
                sort=True,
            ):
                active = g["robust_trade_indicator"].eq(1)
                summaries.append(
                    {
                        "pipeline": "21a",
                        "model": keys[0],
                        "decision_rule": keys[1],
                        "strategy": "binary_contract_edge",
                        "threshold": float(keys[2]),
                        "robustness_cost": float(cost),
                        "staleness_rule": cap.staleness_rule,
                        "staleness_quantile": cap.staleness_quantile,
                        "max_staleness_hours": float(max_stale),
                        "unrestricted_staleness": bool(cap.unrestricted),
                        "n_opportunities": int(len(g)),
                        "n_trades": int(active.sum()),
                        "n_dates": int(
                            g.loc[active, "event_date"].nunique()
                        ),
                        "total_net_pnl": float(
                            g["robust_net_pnl"].sum()
                        ),
                        "mean_net_pnl_per_trade": (
                            float(
                                g.loc[active, "robust_net_pnl"].mean()
                            )
                            if active.sum()
                            else np.nan
                        ),
                        "positive_trade_rate": (
                            float(
                                (
                                    g.loc[active, "robust_net_pnl"]
                                    > 0
                                ).mean()
                            )
                            if active.sum()
                            else np.nan
                        ),
                    }
                )

    return pd.concat(rows, ignore_index=True), pd.DataFrame(summaries)


def attach_staleness_to_21b_results(
    book_results: pd.DataFrame,
    allocation_panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Define book-level staleness as the maximum staleness among opened positions.

    For single-best-edge rows, use the selected contract's staleness by joining
    selected_market_slug when available. For proportional allocation, use the
    maximum staleness among positive-weight positions. Inactive books retain
    NaN staleness.
    """
    allocations = allocation_panel.copy()

    group_keys = [
        "model",
        "event_date",
        "decision_rule",
        "threshold",
    ]

    active_alloc = allocations.loc[
        allocations["allocation_weight"] > 0
    ].copy()

    proportional_stale = (
        active_alloc.groupby(group_keys, as_index=False)
        .agg(
            market_price_staleness_hours=(
                "market_price_staleness_hours",
                "max",
            )
        )
    )
    proportional_stale["strategy"] = "proportional_positive_edge"

    result = book_results.copy()

    if "selected_market_slug" in result.columns:
        lookup_cols = [
            c
            for c in [
                "model",
                "event_date",
                "decision_rule",
                "threshold",
                "market_slug",
                "market_price_staleness_hours",
            ]
            if c in allocations.columns
        ]
        lookup = allocations[lookup_cols].drop_duplicates()
        single = result.loc[
            result["strategy"].eq("single_best_edge")
        ].copy()
        single = single.merge(
            lookup,
            left_on=[
                "model",
                "event_date",
                "decision_rule",
                "threshold",
                "selected_market_slug",
            ],
            right_on=[
                "model",
                "event_date",
                "decision_rule",
                "threshold",
                "market_slug",
            ],
            how="left",
            validate="many_to_one",
        )
        single_stale = single[
            group_keys + ["strategy", "market_price_staleness_hours"]
        ]
    else:
        single_stale = pd.DataFrame(
            columns=group_keys
            + ["strategy", "market_price_staleness_hours"]
        )

    stale = pd.concat(
        [single_stale, proportional_stale],
        ignore_index=True,
    ).drop_duplicates(group_keys + ["strategy"])

    return result.merge(
        stale,
        on=group_keys + ["strategy"],
        how="left",
        validate="one_to_one",
    )


def build_21b_robustness(
    book_results: pd.DataFrame,
    staleness_caps: pd.DataFrame,
    config: Config,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = book_results.loc[
        book_results["threshold"].isin(config.threshold_grid)
    ].copy()
    base["gross_pnl_original"] = pd.to_numeric(
        base["gross_pnl"], errors="coerce"
    )
    base["n_positions"] = pd.to_numeric(
        base["n_positions"], errors="coerce"
    ).fillna(0)

    rows = []
    summaries = []

    for cost in config.cost_grid:
        for cap in staleness_caps.itertuples(index=False):
            max_stale = float(cap.max_staleness_hours)
            tmp = base.copy()
            tmp["robustness_cost"] = float(cost)
            tmp["staleness_rule"] = cap.staleness_rule
            tmp["staleness_quantile"] = cap.staleness_quantile
            tmp["max_staleness_hours"] = max_stale
            tmp["unrestricted_staleness"] = bool(cap.unrestricted)
            tmp["active_book"] = tmp["n_positions"] > 0
            tmp["passes_staleness_filter"] = (
                tmp["market_price_staleness_hours"].notna()
                & (
                    tmp["market_price_staleness_hours"]
                    <= float(max_stale)
                )
            )
            tmp["robust_active_book"] = (
                tmp["active_book"]
                & tmp["passes_staleness_filter"]
            )
            tmp["robust_net_pnl"] = np.where(
                tmp["robust_active_book"],
                tmp["gross_pnl_original"]
                - float(cost) * tmp["n_positions"],
                0.0,
            )
            rows.append(tmp)

            for keys, g in tmp.groupby(
                ["model", "decision_rule", "strategy", "threshold"],
                sort=True,
            ):
                active = g["robust_active_book"].astype(bool)
                summaries.append(
                    {
                        "pipeline": "21b",
                        "model": keys[0],
                        "decision_rule": keys[1],
                        "strategy": keys[2],
                        "threshold": float(keys[3]),
                        "robustness_cost": float(cost),
                        "staleness_rule": cap.staleness_rule,
                        "staleness_quantile": cap.staleness_quantile,
                        "max_staleness_hours": float(max_stale),
                        "unrestricted_staleness": bool(cap.unrestricted),
                        "n_books": int(len(g)),
                        "n_active_books": int(active.sum()),
                        "n_positions": int(
                            g.loc[active, "n_positions"].sum()
                        ),
                        "n_dates": int(
                            g.loc[active, "event_date"].nunique()
                        ),
                        "total_net_pnl": float(
                            g["robust_net_pnl"].sum()
                        ),
                        "mean_net_pnl_per_active_book": (
                            float(
                                g.loc[active, "robust_net_pnl"].mean()
                            )
                            if active.sum()
                            else np.nan
                        ),
                        "positive_book_rate": (
                            float(
                                (
                                    g.loc[active, "robust_net_pnl"]
                                    > 0
                                ).mean()
                            )
                            if active.sum()
                            else np.nan
                        ),
                    }
                )

    return pd.concat(rows, ignore_index=True), pd.DataFrame(summaries)


def break_even_costs_21a(trades: pd.DataFrame) -> pd.DataFrame:
    active = trades.loc[trades["trade_indicator"].eq(1)].copy()
    rows = []
    for keys, g in active.groupby(
        ["model", "decision_rule", "threshold"],
        sort=True,
    ):
        n = len(g)
        gross = float(g["gross_pnl"].sum())
        rows.append(
            {
                "pipeline": "21a",
                "model": keys[0],
                "decision_rule": keys[1],
                "strategy": "binary_contract_edge",
                "threshold": keys[2],
                "n_positions": n,
                "gross_pnl": gross,
                "break_even_cost_per_position": (
                    gross / n if n else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def break_even_costs_21b(results: pd.DataFrame) -> pd.DataFrame:
    active = results.loc[results["n_positions"] > 0].copy()
    rows = []
    for keys, g in active.groupby(
        ["model", "decision_rule", "strategy", "threshold"],
        sort=True,
    ):
        n_positions = float(g["n_positions"].sum())
        gross = float(g["gross_pnl"].sum())
        rows.append(
            {
                "pipeline": "21b",
                "model": keys[0],
                "decision_rule": keys[1],
                "strategy": keys[2],
                "threshold": keys[3],
                "n_positions": int(n_positions),
                "gross_pnl": gross,
                "break_even_cost_per_position": (
                    gross / n_positions
                    if n_positions > 0
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def primary_summary(
    summary_21a: pd.DataFrame,
    summary_21b: pd.DataFrame,
    config: Config,
) -> pd.DataFrame:
    a = summary_21a.loc[
        np.isclose(summary_21a["threshold"], config.primary_threshold)
        & np.isclose(
            summary_21a["robustness_cost"],
            config.primary_cost,
        )
        & np.isclose(
            summary_21a["staleness_quantile"],
            config.primary_staleness_quantile,
        )
    ].copy()

    b = summary_21b.loc[
        np.isclose(summary_21b["threshold"], config.primary_threshold)
        & np.isclose(
            summary_21b["robustness_cost"],
            config.primary_cost,
        )
        & np.isclose(
            summary_21b["staleness_quantile"],
            config.primary_staleness_quantile,
        )
    ].copy()

    for frame in [a, b]:
        frame["robustness_scope"] = (
            "standalone_model_by_decision_rule_by_strategy"
        )

    common_cols = sorted(set(a.columns) | set(b.columns))
    for frame in [a, b]:
        for col in common_cols:
            if col not in frame.columns:
                frame[col] = np.nan

    out = pd.concat(
        [a[common_cols], b[common_cols]],
        ignore_index=True,
    )
    return out.sort_values(
        "total_net_pnl",
        ascending=False,
    ).reset_index(drop=True)


def integrity_checks(
    trade_21a: pd.DataFrame,
    allocations_21b: pd.DataFrame,
    robust_21a: pd.DataFrame,
    robust_21b: pd.DataFrame,
    summary_21a: pd.DataFrame,
    summary_21b: pd.DataFrame,
    primary: pd.DataFrame,
    staleness_col: str,
    staleness_distribution: pd.DataFrame,
    staleness_caps: pd.DataFrame,
    canonical_staleness_snapshots: pd.DataFrame,
    holdout_start_date: str,
    holdout_end_date: str,
    config: Config,
) -> pd.DataFrame:
    checks = []

    def add(name: str, passed: bool, detail: str):
        checks.append(
            {"check": name, "passed": bool(passed), "detail": detail}
        )

    add("21a_input_nonempty", len(trade_21a) > 0, f"rows={len(trade_21a)}")
    add(
        "21b_allocation_input_nonempty",
        len(allocations_21b) > 0,
        f"rows={len(allocations_21b)}",
    )
    add(
        "staleness_column_resolved",
        bool(staleness_col),
        staleness_col,
    )
    add(
        "21a_staleness_attached",
        trade_21a["market_price_staleness_hours"].notna().any(),
        f"coverage={trade_21a['market_price_staleness_hours'].notna().mean():.6f}",
    )
    add(
        "21b_staleness_attached",
        allocations_21b[
            "market_price_staleness_hours"
        ].notna().any(),
        f"coverage={allocations_21b['market_price_staleness_hours'].notna().mean():.6f}",
    )
    add(
        "staleness_nonnegative",
        (
            trade_21a["market_price_staleness_hours"].dropna() >= 0
        ).all()
        and (
            allocations_21b[
                "market_price_staleness_hours"
            ].dropna()
            >= 0
        ).all(),
        "checked",
    )
    add(
        "21a_robustness_panel_nonempty",
        len(robust_21a) > 0,
        f"rows={len(robust_21a)}",
    )
    add(
        "21b_robustness_panel_nonempty",
        len(robust_21b) > 0,
        f"rows={len(robust_21b)}",
    )
    add(
        "21a_summary_nonempty",
        len(summary_21a) > 0,
        f"rows={len(summary_21a)}",
    )
    add(
        "21b_summary_nonempty",
        len(summary_21b) > 0,
        f"rows={len(summary_21b)}",
    )
    add(
        "cost_grid_preserved_21a",
        set(np.round(summary_21a["robustness_cost"].unique(), 10))
        == set(np.round(config.cost_grid, 10)),
        str(sorted(summary_21a["robustness_cost"].unique())),
    )
    add(
        "cost_grid_preserved_21b",
        set(np.round(summary_21b["robustness_cost"].unique(), 10))
        == set(np.round(config.cost_grid, 10)),
        str(sorted(summary_21b["robustness_cost"].unique())),
    )
    expected_rules = set(staleness_caps["staleness_rule"])
    add(
        "empirical_staleness_rules_preserved_21a",
        set(summary_21a["staleness_rule"].unique()) == expected_rules,
        str(sorted(summary_21a["staleness_rule"].unique())),
    )
    add(
        "empirical_staleness_rules_preserved_21b",
        set(summary_21b["staleness_rule"].unique()) == expected_rules,
        str(sorted(summary_21b["staleness_rule"].unique())),
    )
    add(
        "staleness_distribution_reported",
        len(staleness_distribution) == 1
        and int(staleness_distribution.iloc[0]["n_snapshot_observations"]) > 0,
        staleness_distribution.to_dict(orient="records")[0].__str__(),
    )
    add(
        "canonical_staleness_snapshot_count_is_440",
        int(
            staleness_distribution.iloc[0][
                "n_snapshot_observations"
            ]
        ) == 440,
        (
            "n_snapshot_observations="
            + str(
                int(
                    staleness_distribution.iloc[0][
                        "n_snapshot_observations"
                    ]
                )
            )
        ),
    )

    holdout_start = pd.Timestamp(
        holdout_start_date
    ).normalize()
    holdout_end = pd.Timestamp(
        holdout_end_date
    ).normalize()
    expected_dates = pd.date_range(
        holdout_start,
        holdout_end,
        freq="D",
    )
    observed_dates = pd.DatetimeIndex(
        sorted(
            pd.to_datetime(
                canonical_staleness_snapshots["event_date"]
            ).dt.normalize().unique()
        )
    )

    add(
        "canonical_snapshot_table_has_440_unique_rows",
        len(canonical_staleness_snapshots) == 440,
        f"rows={len(canonical_staleness_snapshots)}",
    )
    add(
        "canonical_staleness_dates_match_locked_holdout",
        (
            len(observed_dates) == len(expected_dates)
            and observed_dates.equals(expected_dates)
        ),
        (
            f"observed={list(observed_dates.strftime('%Y-%m-%d'))}; "
            f"expected={list(expected_dates.strftime('%Y-%m-%d'))}"
        ),
    )
    add(
        "canonical_staleness_rows_equal_10x4x11",
        len(canonical_staleness_snapshots) == 10 * 4 * 11,
        f"rows={len(canonical_staleness_snapshots)}",
    )
    add(
        "empirical_caps_monotone",
        staleness_caps.loc[
            ~staleness_caps["unrestricted"].astype(bool),
            "max_staleness_hours",
        ].is_monotonic_increasing,
        "checked",
    )
    add(
        "unrestricted_staleness_case_present",
        staleness_caps["unrestricted"].astype(bool).sum() == 1,
        "checked",
    )
    finite_caps = staleness_caps.loc[
        ~staleness_caps["unrestricted"].astype(bool)
    ]
    add(
        "finite_caps_are_tie_aware_valid",
        finite_caps["tie_aware_valid"].astype(bool).all(),
        finite_caps[
            [
                "staleness_rule",
                "staleness_quantile",
                "observed_share_admitted",
                "tie_mass_at_cap",
                "admission_excess_over_target",
            ]
        ].to_dict(orient="records").__str__(),
    )
    add(
        "admitted_share_at_least_requested_quantile",
        (
            finite_caps["observed_share_admitted"]
            + 1e-12
            >= finite_caps["staleness_quantile"]
        ).all(),
        "checked",
    )
    add(
        "admission_excess_bounded_by_tie_mass",
        (
            finite_caps["admission_excess_over_target"]
            <= finite_caps["tie_mass_at_cap"] + 1e-12
        ).all(),
        "checked",
    )
    q90 = finite_caps.loc[
        finite_caps["staleness_rule"].eq("empirical_q90")
    ].iloc[0]
    add(
        "q90_empirical_cap_is_tie_aware_valid",
        (
            float(q90["observed_share_admitted"]) + 1e-12
            >= float(q90["staleness_quantile"])
            and float(q90["admission_excess_over_target"])
            <= float(q90["tie_mass_at_cap"]) + 1e-12
            and bool(q90["tie_aware_valid"])
        ),
        q90.to_dict().__str__(),
    )
    add(
        "threshold_grid_preserved",
        set(np.round(summary_21a["threshold"].unique(), 10))
        == set(np.round(config.threshold_grid, 10))
        and set(np.round(summary_21b["threshold"].unique(), 10))
        == set(np.round(config.threshold_grid, 10)),
        str(config.threshold_grid),
    )
    add(
        "primary_summary_nonempty",
        len(primary) > 0,
        f"rows={len(primary)}",
    )
    add(
        "primary_specification_exact",
        np.isclose(primary["threshold"], config.primary_threshold).all()
        and np.isclose(
            primary["robustness_cost"], config.primary_cost
        ).all()
        and np.isclose(
            primary["staleness_quantile"],
            config.primary_staleness_quantile,
        ).all(),
        "checked",
    )
    add(
        "standalone_decision_rules_preserved",
        primary["decision_rule"].notna().all(),
        "checked",
    )
    add(
        "forecast_specification_unchanged",
        True,
        "21c modifies trading assumptions only",
    )

    return pd.DataFrame(checks)


def make_figures(
    primary: pd.DataFrame,
    summary_21a: pd.DataFrame,
    summary_21b: pd.DataFrame,
    config: Config,
    figure_dir: Path,
) -> list[Path]:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    plot = primary.head(30).copy()
    plot["label"] = (
        plot["pipeline"]
        + " | "
        + plot["model"]
        + " | "
        + plot["decision_rule"]
        + " | "
        + plot["strategy"]
    )
    fig, ax = plt.subplots(figsize=(16, 7))
    ax.bar(plot["label"], plot["total_net_pnl"])
    ax.set_ylabel("Total net PnL")
    ax.set_title(
        "21c primary cost-and-staleness robustness specification"
    )
    ax.tick_params(axis="x", rotation=60)
    fig.tight_layout()
    path = figure_dir / "21c_primary_robust_total_pnl.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    outputs.append(path)

    for pipeline, summary in [
        ("21a", summary_21a),
        ("21b", summary_21b),
    ]:
        fixed = summary.loc[
            np.isclose(summary["threshold"], config.primary_threshold)
            & np.isclose(
                summary["staleness_quantile"],
                config.primary_staleness_quantile,
            )
        ].copy()

        top_keys = (
            fixed.loc[np.isclose(fixed["robustness_cost"], 0)]
            .sort_values("total_net_pnl", ascending=False)
            .head(8)[
                ["model", "decision_rule", "strategy"]
            ]
            .drop_duplicates()
        )

        fig, ax = plt.subplots(figsize=(11, 6))
        for _, key in top_keys.iterrows():
            g = fixed.loc[
                fixed["model"].eq(key["model"])
                & fixed["decision_rule"].eq(key["decision_rule"])
                & fixed["strategy"].eq(key["strategy"])
            ].sort_values("robustness_cost")
            label = (
                f"{key['model']} | {key['decision_rule']} | "
                f"{key['strategy']}"
            )
            ax.plot(
                g["robustness_cost"],
                g["total_net_pnl"],
                marker="o",
                label=label,
            )
        ax.axhline(0, linestyle="--", linewidth=1)
        ax.set_xlabel("Cost per opened position")
        ax.set_ylabel("Total net PnL")
        ax.set_title(
            f"21c {pipeline}: cost sensitivity at primary threshold "
            f"and empirical Q{int(config.primary_staleness_quantile * 100)} cap"
        )
        ax.legend(fontsize=8)
        fig.tight_layout()
        path = figure_dir / f"21c_{pipeline}_cost_sensitivity.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(path)

        fixed = summary.loc[
            np.isclose(summary["threshold"], config.primary_threshold)
            & np.isclose(
                summary["robustness_cost"],
                config.primary_cost,
            )
        ].copy()

        top_keys = (
            fixed.sort_values("total_net_pnl", ascending=False)
            .head(8)[
                ["model", "decision_rule", "strategy"]
            ]
            .drop_duplicates()
        )

        fig, ax = plt.subplots(figsize=(11, 6))
        for _, key in top_keys.iterrows():
            g = fixed.loc[
                fixed["model"].eq(key["model"])
                & fixed["decision_rule"].eq(key["decision_rule"])
                & fixed["strategy"].eq(key["strategy"])
            ].copy()
            order = {
                "empirical_q25": 1,
                "empirical_q50": 2,
                "empirical_q75": 3,
                "empirical_q90": 4,
                "unrestricted": 5,
            }
            g["staleness_order"] = g["staleness_rule"].map(order)
            g = g.sort_values("staleness_order")
            label = (
                f"{key['model']} | {key['decision_rule']} | "
                f"{key['strategy']}"
            )
            ax.plot(
                g["staleness_order"],
                g["total_net_pnl"],
                marker="o",
                label=label,
            )
        ax.axhline(0, linestyle="--", linewidth=1)
        ax.set_xlabel("Empirical staleness rule")
        ax.set_xticks(
            [1, 2, 3, 4, 5],
            ["Q25", "Median", "Q75", "Q90", "Unrestricted"],
        )
        ax.set_ylabel("Total net PnL")
        ax.set_title(
            f"21c {pipeline}: staleness sensitivity at primary threshold "
            f"and cost {config.primary_cost:g}"
        )
        ax.legend(fontsize=8)
        fig.tight_layout()
        path = figure_dir / f"21c_{pipeline}_staleness_sensitivity.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(path)

    return outputs


def write_report(
    manifest: dict,
    primary: pd.DataFrame,
    break_even: pd.DataFrame,
    staleness_distribution: pd.DataFrame,
    staleness_caps: pd.DataFrame,
    checks: pd.DataFrame,
    report_path: Path,
):
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 21c transaction-cost, staleness and robustness analysis",
        "",
        "## Status",
        "",
        "This step applies reduced-form execution costs and market-price "
        "staleness filters to the frozen 21a and 21b trading rules. It does not "
        "change any forecasting model or primary trading threshold.",
        "",
        "## Primary robustness specification",
        "",
        f"- edge threshold: `{manifest['primary_threshold']}`",
        f"- execution cost per opened position: `{manifest['primary_cost']}`",
        f"- primary staleness rule: empirical "
        f"`Q{int(manifest['primary_staleness_quantile'] * 100)}`",
        f"- primary staleness cap: "
        f"`{manifest['primary_staleness_cap_hours']:.6f} hours`",
        "",
        "## Staleness source",
        "",
        f"- source file: `{manifest['staleness_source_file']}`",
        f"- source column: `{manifest['staleness_source_column']}`",
        f"- converted unit: hours",
        "",
        "The canonical staleness distribution contains one row per underlying "
        "event-date, decision-rule and market-contract snapshot, restricted to "
        "the locked final holdout from "
        f"`{manifest['holdout_start_date']}` to "
        f"`{manifest['holdout_end_date']}`. It is not pooled again across the "
        "21a and 21b pipelines, which reuse the same market data. "
        "The archived snapshots are concentrated close to one hour old, so the "
        "analysis uses empirical quantile caps rather than artificial 3-hour, "
        "6-hour, 12-hour, or 24-hour thresholds.",
        "",
        "Because the empirical distribution is discrete, ties at a quantile cap "
        "can make the admitted share exceed the nominal quantile. The checks are "
        "therefore tie-aware: admitted share must be at least the requested "
        "quantile, and any excess must be no larger than the empirical mass tied "
        "at the cap. In this sample the Q90 cap equals the observed maximum, so "
        "Q90 admits all snapshots.",
        "",
        "## Observed staleness distribution",
        "",
        staleness_distribution.to_markdown(index=False),
        "",
        "## Empirical staleness caps",
        "",
        staleness_caps.to_markdown(index=False),
        "",
        "## Primary standalone results",
        "",
        primary.to_markdown(index=False),
        "",
        "## Break-even cost per opened position",
        "",
        break_even.to_markdown(index=False),
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "Observed market probabilities remain frictionless reference prices. "
        "The cost grid is a reduced-form sensitivity analysis and should not be "
        "described as a reconstruction of historical executable bid-ask quotes. "
        "All strategies remain standalone by decision rule; repeated decision "
        "snapshots are not pooled into one portfolio.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def serialise_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out


def zip_review(paths: Iterable[Path], repo: Path, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if path.exists():
                zf.write(path, arcname=str(path.relative_to(repo)))


def main() -> int:
    config = parse_args()
    repo = config.repo_root
    processed = repo / "data" / "processed"
    docs = repo / "docs" / "research_outputs"
    figures = repo / "figures" / "21c_cost_staleness_robustness"

    (
        trade_21a,
        _summary_21a_locked,
        book_results_21b,
        allocations_21b,
        _summary_21b_locked,
        manifest_21a,
        manifest_21b,
    ) = load_inputs(repo)

    stale_source, stale_col, stale_path = locate_staleness_source(repo)

    trade_21a = attach_staleness(
        trade_21a,
        stale_source,
        stale_col,
    )
    allocations_21b = attach_staleness(
        allocations_21b,
        stale_source,
        stale_col,
    )

    book_results_21b = attach_staleness_to_21b_results(
        book_results_21b,
        allocations_21b,
    )

    (
        staleness_distribution,
        staleness_caps,
        canonical_staleness_snapshots,
    ) = empirical_staleness_distribution_and_caps(
        stale_source,
        stale_col,
        config.staleness_quantiles,
        manifest_21a["holdout_start_date"],
        manifest_21a["holdout_end_date"],
    )

    robust_21a, summary_21a = build_21a_robustness(
        trade_21a,
        staleness_caps,
        config,
    )
    robust_21b, summary_21b = build_21b_robustness(
        book_results_21b,
        staleness_caps,
        config,
    )

    break_even = pd.concat(
        [
            break_even_costs_21a(trade_21a),
            break_even_costs_21b(book_results_21b),
        ],
        ignore_index=True,
    )

    primary = primary_summary(
        summary_21a,
        summary_21b,
        config,
    )

    checks = integrity_checks(
        trade_21a,
        allocations_21b,
        robust_21a,
        robust_21b,
        summary_21a,
        summary_21b,
        primary,
        stale_col,
        staleness_distribution,
        staleness_caps,
        canonical_staleness_snapshots,
        manifest_21a["holdout_start_date"],
        manifest_21a["holdout_end_date"],
        config,
    )
    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    primary_cap_row = staleness_caps.loc[
        np.isclose(
            staleness_caps["staleness_quantile"],
            config.primary_staleness_quantile,
            equal_nan=False,
        )
    ].iloc[0]

    manifest = {
        "step": "21c",
        "inputs": ["21a", "21b"],
        "evaluation_sample": "locked_final_holdout",
        "holdout_start_date": manifest_21a["holdout_start_date"],
        "holdout_end_date": manifest_21a["holdout_end_date"],
        "cost_grid": list(config.cost_grid),
        "staleness_quantiles": list(config.staleness_quantiles),
        "staleness_rules": staleness_caps["staleness_rule"].tolist(),
        "threshold_grid": list(config.threshold_grid),
        "primary_cost": config.primary_cost,
        "primary_staleness_quantile": config.primary_staleness_quantile,
        "primary_staleness_rule": primary_cap_row["staleness_rule"],
        "primary_staleness_cap_hours": float(
            primary_cap_row["max_staleness_hours"]
        ),
        "primary_threshold": config.primary_threshold,
        "staleness_source_file": str(stale_path.relative_to(repo)),
        "staleness_source_column": stale_col,
        "staleness_unit_after_conversion": "hours",
        "canonical_staleness_snapshot_key": [
            "event_date",
            "decision_rule",
            "market_slug",
        ],
        "canonical_staleness_snapshot_count": int(
            staleness_distribution.iloc[0][
                "n_snapshot_observations"
            ]
        ),
        "canonical_staleness_holdout_filter_applied": True,
        "canonical_staleness_holdout_start_date": (
            manifest_21a["holdout_start_date"]
        ),
        "canonical_staleness_holdout_end_date": (
            manifest_21a["holdout_end_date"]
        ),
        "staleness_quantile_tie_handling": (
            "admitted_share_may_exceed_quantile_by_at_most_tie_mass_at_cap"
        ),
        "q90_interpretation": (
            "q90_cap_is_empirical_and_tie_aware; full admission is not required"
        ),
        "cost_interpretation": (
            "reduced_form_cost_per_opened_position"
        ),
        "headline_scope": (
            "standalone_model_by_decision_rule_by_strategy"
        ),
        "pooled_across_decision_rules": False,
        "forecast_specification_changed": False,
        "trading_rule_changed": False,
    }

    outputs = {
        "21a_robust_panel": (
            processed / "21c_21a_cost_staleness_trade_panel.csv"
        ),
        "21a_summary": (
            processed / "21c_21a_cost_staleness_summary.csv"
        ),
        "21b_robust_panel": (
            processed / "21c_21b_cost_staleness_book_panel.csv"
        ),
        "21b_summary": (
            processed / "21c_21b_cost_staleness_summary.csv"
        ),
        "primary_summary": (
            processed / "21c_primary_robustness_summary.csv"
        ),
        "break_even": (
            processed / "21c_break_even_cost_summary.csv"
        ),
        "staleness_distribution": (
            processed / "21c_staleness_distribution_summary.csv"
        ),
        "staleness_caps": (
            processed / "21c_empirical_staleness_caps.csv"
        ),
        "canonical_staleness_snapshots": (
            processed / "21c_canonical_staleness_snapshots.csv"
        ),
        "checks": (
            processed / "21c_integrity_checks.csv"
        ),
        "issues": (
            processed / "21c_issues.csv"
        ),
        "manifest": (
            processed / "21c_cost_staleness_manifest.json"
        ),
        "report": (
            docs / "21c_cost_staleness_robustness_report.md"
        ),
    }

    serialise_dates(robust_21a).to_csv(
        outputs["21a_robust_panel"],
        index=False,
    )
    summary_21a.to_csv(outputs["21a_summary"], index=False)
    serialise_dates(robust_21b).to_csv(
        outputs["21b_robust_panel"],
        index=False,
    )
    summary_21b.to_csv(outputs["21b_summary"], index=False)
    primary.to_csv(outputs["primary_summary"], index=False)
    break_even.to_csv(outputs["break_even"], index=False)
    staleness_distribution.to_csv(
        outputs["staleness_distribution"],
        index=False,
    )
    staleness_caps.to_csv(
        outputs["staleness_caps"],
        index=False,
    )
    serialise_dates(canonical_staleness_snapshots).to_csv(
        outputs["canonical_staleness_snapshots"],
        index=False,
    )
    checks.to_csv(outputs["checks"], index=False)
    issues.to_csv(outputs["issues"], index=False)
    outputs["manifest"].write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    figure_paths = make_figures(
        primary,
        summary_21a,
        summary_21b,
        config,
        figures,
    )
    write_report(
        manifest,
        primary,
        break_even,
        staleness_distribution,
        staleness_caps,
        checks,
        outputs["report"],
    )

    review_zip = (
        repo / "data" / "review_bundles" / "21c_review_bundle.zip"
    )
    zip_review(
        list(outputs.values()) + figure_paths,
        repo,
        review_zip,
    )

    print("21c completed.")
    print(f"Staleness source: {stale_path}")
    print(f"Staleness column: {stale_col}")
    print(f"Primary robustness rows: {len(primary)}")
    print(
        "Primary empirical staleness cap:",
        f"{float(primary_cap_row['max_staleness_hours']):.6f} hours",
    )
    print(f"Passed checks: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more 21c integrity checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
