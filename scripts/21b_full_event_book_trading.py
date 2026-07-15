#!/usr/bin/env python3
"""
21b: Full Hong Kong event-book trading simulation.

This step preserves the frozen 20e forecasting models and treats each
event-date × decision-rule contract book as a mutually exclusive portfolio.

For every complete daily book:
1. Raw model probabilities and raw market YES prices are normalised within book.
2. Normalised edge is q_model - q_market.
3. Two prespecified strategies are evaluated:
   a. single_best_edge:
      buy one YES contract with the largest positive normalised edge when that
      edge exceeds the threshold;
   b. proportional_positive_edge:
      distribute one unit of stake across all contracts whose positive
      normalised edge exceeds the threshold, in proportion to that edge.

Execution uses the observed raw market YES price as a frictionless proxy.
No fees, spread, slippage, liquidity limits, partial fills, market impact,
capital constraints, or dynamic position netting are modelled.

Primary threshold: 0.05.
Sensitivity thresholds: 0.00, 0.02, 0.10.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Config:
    repo_root: Path
    thresholds: tuple[float, ...]
    primary_threshold: float
    trade_cost_per_position: float


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--thresholds",
        type=str,
        default="0,0.02,0.05,0.10",
    )
    parser.add_argument("--primary-threshold", type=float, default=0.05)
    parser.add_argument("--trade-cost-per-position", type=float, default=0.0)
    args = parser.parse_args()

    thresholds = tuple(float(x.strip()) for x in args.thresholds.split(",") if x.strip())
    if any(t < 0 for t in thresholds):
        raise ValueError("Thresholds must be non-negative.")
    if not any(np.isclose(args.primary_threshold, t) for t in thresholds):
        raise ValueError("Primary threshold must be in the threshold grid.")
    if args.trade_cost_per_position < 0:
        raise ValueError("Trade cost must be non-negative.")

    return Config(
        repo_root=args.repo_root.expanduser().resolve(),
        thresholds=thresholds,
        primary_threshold=float(args.primary_threshold),
        trade_cost_per_position=float(args.trade_cost_per_position),
    )


def load_input(repo: Path) -> tuple[pd.DataFrame, dict]:
    processed = repo / "data" / "processed"
    panel_path = processed / "20e_locked_holdout_prediction_panel.csv"
    manifest_path = processed / "20e_locked_holdout_manifest.json"

    if not panel_path.exists():
        raise FileNotFoundError(f"Missing input: {panel_path}")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing input: {manifest_path}")

    panel = pd.read_csv(panel_path, low_memory=False)
    panel["event_date"] = pd.to_datetime(panel["event_date"]).dt.normalize()
    manifest = json.loads(manifest_path.read_text())
    return panel, manifest


def probability_columns(panel: pd.DataFrame) -> dict[str, str]:
    mapping = {
        "catboost_raw": "p_catboost_raw_holdout",
        "catboost_platt": "p_catboost_platt_holdout",
        "ecmwf_raw": "p_ecmwf_raw",
        "ecmwf_bias_fixed_sigma": "p_ecmwf_bias_fixed_sigma",
        "ecmwf_bias_adaptive_sigma": "p_ecmwf_bias_adaptive_sigma",
    }
    missing = {k: v for k, v in mapping.items() if v not in panel.columns}
    if missing:
        raise ValueError(f"Missing model probability columns: {missing}")
    if "p_market" not in panel.columns:
        raise ValueError("Input panel lacks p_market.")
    return mapping


def construct_complete_books(
    panel: pd.DataFrame,
    model_cols: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    id_cols = [
        c for c in [
            "event_date",
            "date_group_id",
            "decision_rule",
            "market_slug",
            "condition_id",
            "token_id",
            "contract_event_type_v2",
            "target_Y_event",
        ]
        if c in panel.columns
    ]

    rows = []
    inventory = []

    for model, col in model_cols.items():
        tmp = panel[id_cols].copy()
        tmp["model"] = model
        tmp["p_market_raw"] = pd.to_numeric(panel["p_market"], errors="coerce")
        tmp["p_model_raw"] = pd.to_numeric(panel[col], errors="coerce")

        for (event_date, decision_rule), book in tmp.groupby(
            ["event_date", "decision_rule"], sort=True
        ):
            b = book.copy()
            valid = (
                b["p_market_raw"].notna().all()
                and b["p_model_raw"].notna().all()
                and b["p_market_raw"].between(0, 1).all()
                and b["p_model_raw"].between(0, 1).all()
            )
            n_winners = int(b["target_Y_event"].sum())
            market_sum = float(b["p_market_raw"].sum()) if valid else np.nan
            model_sum = float(b["p_model_raw"].sum()) if valid else np.nan
            complete = bool(
                valid
                and len(b) > 1
                and n_winners == 1
                and market_sum > 0
                and model_sum > 0
            )

            inventory.append(
                {
                    "model": model,
                    "event_date": event_date,
                    "decision_rule": decision_rule,
                    "n_contracts": len(b),
                    "n_winners": n_winners,
                    "market_probability_sum_raw": market_sum,
                    "model_probability_sum_raw": model_sum,
                    "complete_book": complete,
                }
            )

            if not complete:
                continue

            b["q_market"] = b["p_market_raw"] / market_sum
            b["q_model"] = b["p_model_raw"] / model_sum
            b["normalised_edge"] = b["q_model"] - b["q_market"]
            b["absolute_normalised_edge"] = b["normalised_edge"].abs()
            b["market_probability_sum_raw"] = market_sum
            b["model_probability_sum_raw"] = model_sum
            b["book_n_contracts"] = len(b)
            rows.append(b)

    if not rows:
        raise RuntimeError("No complete event books available.")

    books = pd.concat(rows, ignore_index=True)
    inventory_df = pd.DataFrame(inventory)
    return books, inventory_df


def simulate_single_best_edge(
    books: pd.DataFrame,
    threshold: float,
    trade_cost: float,
) -> pd.DataFrame:
    rows = []
    group_cols = ["model", "event_date", "decision_rule"]

    for keys, book in books.groupby(group_cols, sort=True):
        b = book.sort_values(
            ["normalised_edge", "p_market_raw"],
            ascending=[False, True],
        ).copy()
        top = b.iloc[0]
        trade = bool(float(top["normalised_edge"]) >= threshold)

        pnl = (
            float(top["target_Y_event"]) - float(top["p_market_raw"]) - trade_cost
            if trade
            else 0.0
        )

        rows.append(
            {
                "model": keys[0],
                "event_date": keys[1],
                "decision_rule": keys[2],
                "strategy": "single_best_edge",
                "threshold": float(threshold),
                "n_contracts": len(b),
                "n_positions": int(trade),
                "stake_sum": float(trade),
                "selected_market_slug": top.get("market_slug"),
                "selected_contract_event_type": top.get("contract_event_type_v2"),
                "selected_q_market": float(top["q_market"]),
                "selected_q_model": float(top["q_model"]),
                "selected_normalised_edge": float(top["normalised_edge"]),
                "selected_market_price_raw": float(top["p_market_raw"]),
                "selected_target": int(top["target_Y_event"]),
                "gross_pnl": (
                    float(top["target_Y_event"]) - float(top["p_market_raw"])
                    if trade
                    else 0.0
                ),
                "net_pnl": pnl,
                "winning_contract_selected": int(
                    trade and int(top["target_Y_event"]) == 1
                ),
            }
        )

    return pd.DataFrame(rows)


def simulate_proportional_positive_edge(
    books: pd.DataFrame,
    threshold: float,
    trade_cost: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    book_rows = []
    allocation_rows = []
    group_cols = ["model", "event_date", "decision_rule"]

    for keys, book in books.groupby(group_cols, sort=True):
        b = book.copy()
        eligible = b["normalised_edge"] >= threshold
        positive = b.loc[eligible].copy()

        if positive.empty:
            weights = pd.Series(0.0, index=b.index)
        else:
            edge_total = float(positive["normalised_edge"].sum())
            weights = pd.Series(0.0, index=b.index)
            if edge_total > 0:
                weights.loc[positive.index] = (
                    positive["normalised_edge"] / edge_total
                )

        b["allocation_weight"] = weights
        b["position_indicator"] = (b["allocation_weight"] > 0).astype(int)
        b["gross_pnl_component"] = (
            b["allocation_weight"]
            * (b["target_Y_event"] - b["p_market_raw"])
        )
        b["net_pnl_component"] = (
            b["gross_pnl_component"]
            - trade_cost * b["position_indicator"]
        )
        b["strategy"] = "proportional_positive_edge"
        b["threshold"] = float(threshold)
        allocation_rows.append(b)

        book_rows.append(
            {
                "model": keys[0],
                "event_date": keys[1],
                "decision_rule": keys[2],
                "strategy": "proportional_positive_edge",
                "threshold": float(threshold),
                "n_contracts": len(b),
                "n_positions": int(b["position_indicator"].sum()),
                "stake_sum": float(b["allocation_weight"].sum()),
                "gross_pnl": float(b["gross_pnl_component"].sum()),
                "net_pnl": float(b["net_pnl_component"].sum()),
                "winning_contract_weight": float(
                    b.loc[
                        b["target_Y_event"].astype(int).eq(1),
                        "allocation_weight",
                    ].sum()
                ),
                "mean_selected_normalised_edge": (
                    float(
                        b.loc[
                            b["position_indicator"].eq(1),
                            "normalised_edge",
                        ].mean()
                    )
                    if b["position_indicator"].sum()
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(book_rows), pd.concat(allocation_rows, ignore_index=True)


def simulate_all(
    books: pd.DataFrame,
    thresholds: tuple[float, ...],
    trade_cost: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    book_results = []
    allocations = []

    for threshold in thresholds:
        single = simulate_single_best_edge(books, threshold, trade_cost)
        proportional, allocation = simulate_proportional_positive_edge(
            books, threshold, trade_cost
        )
        book_results.extend([single, proportional])
        allocations.append(allocation)

    return (
        pd.concat(book_results, ignore_index=True),
        pd.concat(allocations, ignore_index=True),
    )


def standalone_summary(book_results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["model", "decision_rule", "strategy", "threshold"]

    for keys, g in book_results.groupby(group_cols, sort=True):
        active = g["n_positions"] > 0
        rows.append(
            {
                "model": keys[0],
                "decision_rule": keys[1],
                "strategy": keys[2],
                "threshold": keys[3],
                "n_books": int(len(g)),
                "n_active_books": int(active.sum()),
                "n_positions": int(g["n_positions"].sum()),
                "total_stake": float(g["stake_sum"].sum()),
                "total_net_pnl": float(g["net_pnl"].sum()),
                "mean_net_pnl_per_book": float(g["net_pnl"].mean()),
                "mean_net_pnl_per_active_book": (
                    float(g.loc[active, "net_pnl"].mean())
                    if active.sum()
                    else np.nan
                ),
                "positive_pnl_book_rate": (
                    float((g.loc[active, "net_pnl"] > 0).mean())
                    if active.sum()
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["threshold", "strategy", "total_net_pnl"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def pooled_diagnostic(book_results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["model", "strategy", "threshold"]

    for keys, g in book_results.groupby(group_cols, sort=True):
        active = g["n_positions"] > 0
        rows.append(
            {
                "model": keys[0],
                "strategy": keys[1],
                "threshold": keys[2],
                "n_books_across_decision_rules": int(len(g)),
                "n_active_books_across_decision_rules": int(active.sum()),
                "n_positions_across_decision_rules": int(g["n_positions"].sum()),
                "total_net_pnl_across_decision_rules": float(g["net_pnl"].sum()),
                "diagnostic_scope": (
                    "pooled_across_decision_rules_not_single_portfolio"
                ),
            }
        )

    return pd.DataFrame(rows)


def daily_pnl(book_results: pd.DataFrame) -> pd.DataFrame:
    daily = (
        book_results.groupby(
            ["model", "decision_rule", "strategy", "threshold", "event_date"],
            as_index=False,
        )
        .agg(
            n_positions=("n_positions", "sum"),
            total_stake=("stake_sum", "sum"),
            net_pnl=("net_pnl", "sum"),
        )
        .sort_values(
            ["model", "decision_rule", "strategy", "threshold", "event_date"]
        )
    )
    daily["cumulative_net_pnl"] = daily.groupby(
        ["model", "decision_rule", "strategy", "threshold"]
    )["net_pnl"].cumsum()
    return daily


def integrity_checks(
    source_panel: pd.DataFrame,
    books: pd.DataFrame,
    inventory: pd.DataFrame,
    book_results: pd.DataFrame,
    allocations: pd.DataFrame,
    standalone: pd.DataFrame,
    pooled: pd.DataFrame,
    config: Config,
) -> pd.DataFrame:
    checks = []

    def add(name: str, passed: bool, detail: str):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    add("source_panel_nonempty", len(source_panel) > 0, f"rows={len(source_panel)}")
    add("complete_books_nonempty", len(books) > 0, f"rows={len(books)}")
    add(
        "complete_book_inventory_nonempty",
        len(inventory) > 0,
        f"rows={len(inventory)}",
    )
    add(
        "all_used_books_have_one_winner",
        (
            books.groupby(["model", "event_date", "decision_rule"])[
                "target_Y_event"
            ].sum()
            == 1
        ).all(),
        "checked",
    )
    add(
        "normalised_market_books_sum_to_one",
        np.allclose(
            books.groupby(["model", "event_date", "decision_rule"])[
                "q_market"
            ].sum(),
            1.0,
            atol=1e-9,
        ),
        "checked",
    )
    add(
        "normalised_model_books_sum_to_one",
        np.allclose(
            books.groupby(["model", "event_date", "decision_rule"])[
                "q_model"
            ].sum(),
            1.0,
            atol=1e-9,
        ),
        "checked",
    )
    add(
        "normalised_edges_sum_to_zero",
        np.allclose(
            books.groupby(["model", "event_date", "decision_rule"])[
                "normalised_edge"
            ].sum(),
            0.0,
            atol=1e-9,
        ),
        "checked",
    )
    add(
        "book_results_nonempty",
        len(book_results) > 0,
        f"rows={len(book_results)}",
    )
    add(
        "strategies_exactly_prespecified",
        set(book_results["strategy"])
        == {"single_best_edge", "proportional_positive_edge"},
        str(sorted(set(book_results["strategy"]))),
    )
    add(
        "threshold_grid_preserved",
        set(np.round(book_results["threshold"].unique(), 10))
        == set(np.round(np.asarray(config.thresholds), 10)),
        str(sorted(book_results["threshold"].unique())),
    )
    add(
        "single_best_has_at_most_one_position",
        (
            book_results.loc[
                book_results["strategy"].eq("single_best_edge"),
                "n_positions",
            ]
            <= 1
        ).all(),
        "checked",
    )
    proportional = book_results["strategy"].eq("proportional_positive_edge")
    add(
        "proportional_stake_is_zero_or_one",
        np.all(
            np.isclose(
                book_results.loc[proportional, "stake_sum"],
                0.0,
            )
            | np.isclose(
                book_results.loc[proportional, "stake_sum"],
                1.0,
            )
        ),
        "checked",
    )
    add(
        "allocation_weights_nonnegative",
        (allocations["allocation_weight"] >= 0).all(),
        "checked",
    )
    add(
        "allocation_weights_match_book_stake",
        np.allclose(
            allocations.groupby(
                ["model", "event_date", "decision_rule", "threshold"]
            )["allocation_weight"].sum().sort_index(),
            book_results.loc[
                book_results["strategy"].eq("proportional_positive_edge")
            ]
            .set_index(
                ["model", "event_date", "decision_rule", "threshold"]
            )["stake_sum"]
            .sort_index(),
            atol=1e-9,
        ),
        "checked",
    )
    add(
        "standalone_summary_preserves_decision_rule",
        standalone["decision_rule"].notna().all(),
        f"rows={len(standalone)}",
    )
    add(
        "pooled_table_labelled_diagnostic",
        pooled["diagnostic_scope"]
        .eq("pooled_across_decision_rules_not_single_portfolio")
        .all(),
        f"rows={len(pooled)}",
    )
    add(
        "primary_threshold_present",
        any(np.isclose(config.primary_threshold, t) for t in config.thresholds),
        f"primary={config.primary_threshold}",
    )
    add(
        "holdout_dates_preserved",
        books["event_date"].nunique() == source_panel["event_date"].nunique(),
        f"dates={books['event_date'].nunique()}",
    )
    add(
        "model_count_expected",
        books["model"].nunique() == 5,
        str(sorted(books["model"].unique())),
    )

    return pd.DataFrame(checks)


def make_figures(
    standalone_primary: pd.DataFrame,
    daily_primary: pd.DataFrame,
    figure_dir: Path,
) -> list[Path]:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    for strategy, group in standalone_primary.groupby("strategy"):
        plot = group.sort_values("total_net_pnl", ascending=False).copy()
        plot["label"] = plot["model"] + " | " + plot["decision_rule"]

        fig, ax = plt.subplots(figsize=(14, 6))
        ax.bar(plot["label"], plot["total_net_pnl"])
        ax.set_ylabel("Total net PnL")
        ax.set_title(
            f"21b {strategy}: standalone book strategies at primary threshold"
        )
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        path = figure_dir / f"21b_{strategy}_standalone_total_pnl.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(path)

    for (strategy, decision_rule), group in daily_primary.groupby(
        ["strategy", "decision_rule"]
    ):
        fig, ax = plt.subplots(figsize=(10, 5))
        for model, g in group.groupby("model"):
            ax.plot(
                g["event_date"],
                g["cumulative_net_pnl"],
                marker="o",
                label=model,
            )
        ax.set_ylabel("Cumulative net PnL")
        ax.set_title(
            f"21b {strategy}, standalone {decision_rule} book strategy"
        )
        ax.legend()
        fig.autofmt_xdate()
        fig.tight_layout()
        path = figure_dir / (
            f"21b_{strategy}_cumulative_{decision_rule}.png"
        )
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(path)

    return outputs


def write_report(
    manifest: dict,
    standalone_primary: pd.DataFrame,
    pooled_primary: pd.DataFrame,
    standalone_all: pd.DataFrame,
    checks: pd.DataFrame,
    report_path: Path,
):
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 21b full Hong Kong event-book trading simulation",
        "",
        "## Status",
        "",
        "This step applies the frozen 20e model probabilities to complete, mutually "
        "exclusive Hong Kong event books. It does not change any forecasting model.",
        "",
        "## Probability construction",
        "",
        "Raw market and model contract probabilities are normalised within each "
        "event-date and decision-rule book. Trading edges are computed as the "
        "difference between normalised model and normalised market probabilities.",
        "",
        "## Prespecified strategies",
        "",
        "1. `single_best_edge`: buy one YES contract with the largest positive "
        "normalised edge when that edge exceeds the threshold.",
        "2. `proportional_positive_edge`: allocate one unit of total stake across "
        "all contracts whose positive normalised edge exceeds the threshold, "
        "proportionally to edge size.",
        "",
        f"Primary threshold: `{manifest['primary_threshold']}`.",
        "",
        "## Execution assumptions",
        "",
        "Observed market YES prices are used as frictionless execution proxies. "
        "The simulation excludes bid-ask spread, fees, slippage, liquidity "
        "constraints, partial fills, market impact, capital limits, and dynamic "
        "position netting.",
        "",
        "## Primary headline: standalone decision-rule strategies",
        "",
        standalone_primary.to_markdown(index=False),
        "",
        "## Pooled primary-threshold diagnostic",
        "",
        "The next table pools repeated decision snapshots only as a diagnostic. "
        "It is not one implementable portfolio.",
        "",
        pooled_primary.to_markdown(index=False),
        "",
        "## Full threshold sensitivity",
        "",
        standalone_all.to_markdown(index=False),
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Interpretation rule",
        "",
        "Results are hypothetical and based on ten settlement dates. The five "
        "percentage point threshold is primary; alternative thresholds are "
        "sensitivity diagnostics.",
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
    figures = repo / "figures" / "21b_full_event_book_trading"

    source_panel, manifest_20e = load_input(repo)
    model_cols = probability_columns(source_panel)

    books, inventory = construct_complete_books(source_panel, model_cols)
    book_results, allocations = simulate_all(
        books,
        config.thresholds,
        config.trade_cost_per_position,
    )

    standalone = standalone_summary(book_results)
    pooled = pooled_diagnostic(book_results)
    daily = daily_pnl(book_results)

    standalone_primary = standalone.loc[
        np.isclose(standalone["threshold"], config.primary_threshold)
    ].copy()
    standalone_primary["strategy_scope"] = "standalone_decision_rule_book_strategy"

    pooled_primary = pooled.loc[
        np.isclose(pooled["threshold"], config.primary_threshold)
    ].copy()

    daily_primary = daily.loc[
        np.isclose(daily["threshold"], config.primary_threshold)
    ].copy()

    checks = integrity_checks(
        source_panel,
        books,
        inventory,
        book_results,
        allocations,
        standalone,
        pooled,
        config,
    )
    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    manifest = {
        "step": "21b",
        "input_step": "20e",
        "evaluation_sample": "locked_final_holdout",
        "holdout_start_date": manifest_20e["holdout_start_date"],
        "holdout_end_date": manifest_20e["holdout_end_date"],
        "n_holdout_dates": int(source_panel["event_date"].nunique()),
        "n_source_rows": int(len(source_panel)),
        "models": model_cols,
        "threshold_grid": list(config.thresholds),
        "primary_threshold": config.primary_threshold,
        "trade_cost_per_position": config.trade_cost_per_position,
        "strategies": [
            "single_best_edge",
            "proportional_positive_edge",
        ],
        "book_normalisation": "within_event_date_decision_rule",
        "headline_scope": "standalone_model_by_decision_rule_by_strategy",
        "pooled_across_decision_rules_is_diagnostic_only": True,
        "execution_price_assumption": (
            "observed_market_yes_probability_as_frictionless_proxy"
        ),
        "excluded_execution_frictions": [
            "bid_ask_spread",
            "fees",
            "slippage",
            "liquidity_constraints",
            "partial_fills",
            "market_impact",
            "capital_limits",
            "dynamic_position_netting",
        ],
        "forecast_specification_changed": False,
    }

    outputs = {
        "book_panel": processed / "21b_full_event_book_probability_panel.csv",
        "book_inventory": processed / "21b_full_event_book_inventory.csv",
        "book_results": processed / "21b_full_event_book_strategy_results.csv",
        "allocation_panel": processed / "21b_full_event_book_allocation_panel.csv",
        "standalone_summary": processed / "21b_full_event_book_standalone_summary.csv",
        "primary_standalone": processed / "21b_full_event_book_primary_standalone_summary.csv",
        "pooled_diagnostic": processed / "21b_full_event_book_pooled_diagnostic.csv",
        "daily_pnl": processed / "21b_full_event_book_daily_pnl.csv",
        "checks": processed / "21b_full_event_book_integrity_checks.csv",
        "issues": processed / "21b_full_event_book_issues.csv",
        "manifest": processed / "21b_full_event_book_manifest.json",
        "report": docs / "21b_full_event_book_trading_report.md",
    }

    serialise_dates(books).to_csv(outputs["book_panel"], index=False)
    serialise_dates(inventory).to_csv(outputs["book_inventory"], index=False)
    serialise_dates(book_results).to_csv(outputs["book_results"], index=False)
    serialise_dates(allocations).to_csv(outputs["allocation_panel"], index=False)
    standalone.to_csv(outputs["standalone_summary"], index=False)
    standalone_primary.to_csv(outputs["primary_standalone"], index=False)
    pooled.to_csv(outputs["pooled_diagnostic"], index=False)
    serialise_dates(daily).to_csv(outputs["daily_pnl"], index=False)
    checks.to_csv(outputs["checks"], index=False)
    issues.to_csv(outputs["issues"], index=False)
    outputs["manifest"].write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    figure_paths = make_figures(
        standalone_primary,
        daily_primary,
        figures,
    )
    write_report(
        manifest,
        standalone_primary,
        pooled_primary,
        standalone,
        checks,
        outputs["report"],
    )

    review_zip = repo / "data" / "review_bundles" / "21b_review_bundle.zip"
    zip_review(list(outputs.values()) + figure_paths, repo, review_zip)

    print("21b completed.")
    print(f"Complete book rows: {len(books)}")
    print(f"Book strategy result rows: {len(book_results)}")
    print(f"Passed checks: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more 21b integrity checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
