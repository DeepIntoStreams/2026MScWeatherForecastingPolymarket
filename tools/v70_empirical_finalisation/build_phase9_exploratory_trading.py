#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:
    raise RuntimeError("matplotlib is required") from exc

from phase9_core import (
    as_bool,
    build_event_panel,
    dependency_check,
    evaluate_strategy,
    git,
    load_stability,
    read_phase6_panel,
    add_cross_rule_features,
    sha256_file,
    strategy_registry,
    summarise_daily,
    utc_now,
)
from phase9_search import (
    bootstrap_series,
    choose_candidates,
    deflated_sharpe_table,
    evaluate_registry,
    load_benchmark,
    nested_walkforward,
    pbo_cscv,
    reality_check,
)


def trade_concentration(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame([{
            "positions": 0,
            "winning_positions": 0,
            "losing_positions": 0,
            "total_weighted_net_pnl": 0.0,
            "top1_absolute_share": np.nan,
            "top5_absolute_share": np.nan,
            "top10_absolute_share": np.nan,
            "absolute_pnl_hhi": np.nan,
            "effective_contributing_positions": np.nan,
        }])
    pnl = trades["weighted_net_pnl"].to_numpy(float)
    absolute = np.abs(pnl)
    total = float(absolute.sum())
    sorted_abs = np.sort(absolute)[::-1]
    shares = absolute / total if total > 0 else np.zeros_like(absolute)
    hhi = float(np.sum(shares**2)) if total > 0 else np.nan
    return pd.DataFrame([{
        "positions": len(trades),
        "winning_positions": int(np.sum(pnl > 0)),
        "losing_positions": int(np.sum(pnl < 0)),
        "total_weighted_net_pnl": float(pnl.sum()),
        "top1_absolute_share": float(sorted_abs[:1].sum() / total) if total > 0 else np.nan,
        "top5_absolute_share": float(sorted_abs[:5].sum() / total) if total > 0 else np.nan,
        "top10_absolute_share": float(sorted_abs[:10].sum() / total) if total > 0 else np.nan,
        "absolute_pnl_hhi": hhi,
        "effective_contributing_positions": float(1.0 / hhi) if hhi > 0 else np.nan,
    }])


def cost_sensitivity(event, dates, strategy, config):
    rows = []
    ledgers = []
    for cost in config["cost_grid"]:
        result = evaluate_strategy(event, dates, strategy, float(cost), config, keep_trades=True)
        rows.append({
            "strategy_id": strategy["strategy_id"],
            "transaction_cost": float(cost),
            **summarise_daily(
                result.daily_pnl,
                result.daily_positions,
                result.daily_active,
                result.daily_entry_cash,
                float(config["tail_probability"]),
            ),
        })
        ledger = pd.DataFrame(result.trade_records)
        if not ledger.empty:
            ledger["transaction_cost"] = float(cost)
            ledgers.append(ledger)
    return pd.DataFrame(rows), pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()


def parameter_neighbourhood(full_results: pd.DataFrame, strategy: pd.Series) -> pd.DataFrame:
    mask = (
        (full_results["model"] == strategy["model"])
        & (full_results["decision_rule"] == strategy["decision_rule"])
        & (full_results["rule_filter"] == strategy["rule_filter"])
        & (full_results["side_mode"] == strategy["side_mode"])
        & (full_results["sizing_rule"] == strategy["sizing_rule"])
        & (full_results["ranking_signal"] == strategy["ranking_signal"])
        & (full_results["stability_filter"] == strategy["stability_filter"])
    )
    nearby = full_results.loc[mask].copy()
    nearby["threshold_distance"] = (
        nearby["edge_threshold"] - float(strategy["edge_threshold"])
    ).abs()
    nearby["top_k_distance"] = (
        nearby["top_k"] - int(strategy["top_k"])
    ).abs()
    return nearby.sort_values(
        ["threshold_distance", "top_k_distance", "sharpe"],
        ascending=[True, True, False],
    ).head(100)


def make_figures(
    out: Path,
    outer_daily: pd.DataFrame,
    outer_summary: pd.DataFrame,
    full_results: pd.DataFrame,
    cost_table: pd.DataFrame,
    block_table: pd.DataFrame,
    best_trades: pd.DataFrame,
    parameter_table: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    figure_dir = out / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    dpi = int(config["figure_dpi"])
    rows = []

    primary = config["primary_selection_objective"]
    daily = outer_daily.loc[
        outer_daily["objective"] == primary
    ].sort_values("target_date").copy()
    daily["cumulative"] = daily["daily_net_pnl"].cumsum()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(pd.to_datetime(daily["target_date"]), daily["cumulative"], marker="o", ms=3)
    ax.axhline(0, lw=1)
    ax.set_title("Nested walk-forward equity curve")
    ax.set_ylabel("Cumulative net PnL")
    ax.set_xlabel("Settlement date")
    fig.tight_layout()
    path = figure_dir / "phase9_nested_walkforward_equity.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    rows.append({"figure": path.name, "purpose": "Primary nested out-of-sample performance"})

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(outer_summary["objective"], outer_summary["sharpe"])
    ax.axhline(0, lw=1)
    ax.set_ylabel("Settlement-date Sharpe")
    ax.set_title("Walk-forward selector comparison")
    fig.tight_layout()
    path = figure_dir / "phase9_selector_sharpe.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    rows.append({"figure": path.name, "purpose": "Selector comparison"})

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(cost_table["transaction_cost"], cost_table["sharpe"], marker="o")
    ax.axhline(0, lw=1)
    ax.set_xlabel("Transaction cost per unit")
    ax.set_ylabel("Settlement-date Sharpe")
    ax.set_title("Best candidate Sharpe versus transaction cost")
    fig.tight_layout()
    path = figure_dir / "phase9_sharpe_cost_sensitivity.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    rows.append({"figure": path.name, "purpose": "Cost robustness"})

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(block_table["outer_fold"].astype(str), block_table["total_net_pnl"])
    ax.axhline(0, lw=1)
    ax.set_xlabel("Outer block")
    ax.set_ylabel("Net PnL")
    ax.set_title("Nested walk-forward PnL by outer block")
    fig.tight_layout()
    path = figure_dir / "phase9_outer_block_pnl.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    rows.append({"figure": path.name, "purpose": "Temporal stability"})

    frontier = full_results.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["sharpe", "maximum_drawdown"]
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(frontier["maximum_drawdown"], frontier["sharpe"], s=5, alpha=0.25)
    ax.set_xlabel("Maximum drawdown")
    ax.set_ylabel("Settlement-date Sharpe")
    ax.set_title("Strategy Sharpe–drawdown frontier")
    fig.tight_layout()
    path = figure_dir / "phase9_sharpe_drawdown_frontier.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    rows.append({"figure": path.name, "purpose": "Risk-return frontier"})

    if not best_trades.empty:
        ordered = best_trades.sort_values("weighted_net_pnl")
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar(range(len(ordered)), ordered["weighted_net_pnl"])
        ax.axhline(0, lw=1)
        ax.set_xlabel("Positions sorted by PnL")
        ax.set_ylabel("Weighted net PnL")
        ax.set_title("Best candidate PnL concentration")
        fig.tight_layout()
        path = figure_dir / "phase9_best_strategy_waterfall.pdf"
        fig.savefig(path, dpi=dpi)
        plt.close(fig)
        rows.append({"figure": path.name, "purpose": "Concentration and fragility"})

    fig, ax = plt.subplots(figsize=(8, 5))
    scatter = ax.scatter(
        parameter_table["edge_threshold"],
        parameter_table["sharpe"],
        c=parameter_table["top_k"],
        s=20,
        alpha=0.6,
    )
    ax.set_xlabel("Probability-edge threshold")
    ax.set_ylabel("Settlement-date Sharpe")
    ax.set_title("Local parameter stability")
    fig.colorbar(scatter, ax=ax, label="Top-k")
    fig.tight_layout()
    path = figure_dir / "phase9_parameter_stability.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    rows.append({"figure": path.name, "purpose": "Neighbourhood stability"})

    return pd.DataFrame(rows)


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase9_manifest.json", "phase9_review_bundle.zip"
        }:
            files.append({
                "relative_path": path.relative_to(out).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    (out / "phase9_manifest.json").write_text(
        json.dumps({
            "phase": "phase9_exploratory_trading_laboratory",
            "generated_utc": utc_now(),
            "provenance": dict(provenance),
            "files": files,
        }, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    target = out / "phase9_review_bundle.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != target:
                archive.write(path, path.relative_to(out).as_posix())


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    outer_summary: pd.DataFrame,
    candidates: pd.DataFrame,
    bootstrap: pd.DataFrame,
    dsr: pd.DataFrame,
    pbo: pd.DataFrame,
    reality: pd.DataFrame,
    concentration: pd.DataFrame,
    observed_synthetic: pd.DataFrame,
    config: Mapping[str, Any],
) -> None:
    failures = checks.loc[as_bool(checks["critical"]) & ~as_bool(checks["passed"])]
    status = "PASSED" if failures.empty else "FAILED"
    primary = outer_summary.loc[
        outer_summary["objective"] == config["primary_selection_objective"]
    ].iloc[0]
    lines = [
        "# Phase 9 — Exploratory Trading Strategy Laboratory",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"## Overall status: **{status}**",
        "",
        "## Interpretation boundary",
        "",
        config["interpretation_boundary"],
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(dict(provenance), indent=2, sort_keys=True),
        "```",
        "",
        "## Nested chronological walk-forward",
        "",
        outer_summary.to_markdown(index=False),
        "",
        (
            f"The pre-registered primary selector produced total outer PnL "
            f"{primary['total_net_pnl']:.6f} and settlement-date Sharpe "
            f"{primary['sharpe']:.6f}."
        ),
        "",
        "## Candidate hierarchy",
        "",
        candidates.to_markdown(index=False),
        "",
        "## Bootstrap uncertainty",
        "",
        bootstrap.to_markdown(index=False),
        "",
        "## Deflated Sharpe",
        "",
        dsr.head(20).to_markdown(index=False),
        "",
        "## Probability of backtest overfitting",
        "",
        pbo.to_markdown(index=False),
        "",
        "## Reality check",
        "",
        reality.to_markdown(index=False),
        "",
        "## Concentration",
        "",
        concentration.to_markdown(index=False),
        "",
        "## Observed long-only versus synthetic short-inclusive search",
        "",
        observed_synthetic.to_markdown(index=False),
        "",
        "## Thesis boundary",
        "",
        (
            "The thesis should retain Phase 9 only when nested walk-forward PnL and "
            "Sharpe are positive, multiple-testing diagnostics are credible, cost "
            "sensitivity is acceptable and concentration is not excessive. Any "
            "short-inclusive result remains synthetic."
        ),
        "",
    ]
    (out / "phase9_report.md").write_text("\n".join(lines), encoding="utf-8")


def self_test() -> None:
    from phase9_core import candidate_side, position_weights, sharpe_ratio
    x = np.array([0.1, -0.05, 0.02, 0.0, 0.03])
    assert np.isfinite(sharpe_ratio(x))
    q = np.array([0.6, 0.2])
    p = np.array([0.4, 0.3])
    side, edge = candidate_side(q, p, "long_short")
    assert side.tolist() == [1, -1]
    assert np.allclose(edge, [0.2, 0.1])
    weights = position_weights(
        q, p, side, edge, "equal_budget",
        {"position_caps": {
            "quarter_kelly_single_position_cap": 0.25,
            "quarter_kelly_daily_gross_cap": 1.0,
        }},
    )
    assert np.allclose(weights, [0.5, 0.5])
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
    if args.repo_root is None or args.spec is None or args.output_root is None:
        raise SystemExit("--repo-root, --spec and --output-root are required")

    repo = args.repo_root.resolve()
    config = json.loads((repo / args.spec).read_text(encoding="utf-8"))
    out = (repo / args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=True)

    current_branch = git(repo, "branch", "--show-current")
    tag_commit = git(repo, "rev-list", "-n", "1", config["frozen_tag"])
    head_commit = git(repo, "rev-parse", "HEAD")
    ancestor = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", tag_commit, head_commit],
        check=False,
    ).returncode == 0
    provenance = {
        "generated_utc": utc_now(),
        "working_branch": current_branch,
        "working_commit": head_commit,
        "frozen_tag": config["frozen_tag"],
        "frozen_tag_commit": tag_commit,
        "head_descends_from_frozen_tag": ancestor,
        "exploratory": True,
        "primary_cost": config["primary_cost"],
        "interpretation_boundary": config["interpretation_boundary"],
    }
    (out / "phase9_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )

    dependency_rows = []
    for label, key in [
        ("phase6", "phase6_integrity"),
        ("phase7", "phase7_integrity"),
        ("phase8", "phase8_integrity"),
        ("phase8_completion", "phase8_completion"),
    ]:
        passed, detail = dependency_check(repo / config["inputs"][key])
        dependency_rows.append({
            "check": f"{label}_dependency",
            "passed": passed,
            "critical": True,
            "detail": detail,
        })
    dependency_rows.extend([
        {
            "check": "working_branch",
            "passed": current_branch == config["working_branch"],
            "critical": True,
            "detail": f"current={current_branch}; expected={config['working_branch']}",
        },
        {
            "check": "frozen_tag_is_ancestor",
            "passed": ancestor,
            "critical": True,
            "detail": f"tag_commit={tag_commit}; head={head_commit}",
        },
    ])
    dependency = pd.DataFrame(dependency_rows)
    dependency.to_csv(out / "phase9_dependency_checks.csv", index=False)
    if not dependency["passed"].all():
        raise RuntimeError("Phase 9 dependency checks failed")

    panel = read_phase6_panel(repo / config["inputs"]["phase6_event_panel"])
    event = build_event_panel(panel, float(config["numerical_tolerance"]))
    event = add_cross_rule_features(event)
    event, stability_status = load_stability(
        repo / config["inputs"]["phase7_shifted_events"], event
    )
    event.to_csv(
        out / "phase9_trade_opportunity_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    stability_status.to_csv(out / "phase9_stability_input_status.csv", index=False)

    dates = sorted(event["target_date"].unique())
    if len(dates) != 97:
        raise ValueError(f"Expected 97 exact-support dates, got {len(dates)}")

    registry = strategy_registry(config)
    registry.to_csv(out / "phase9_strategy_registry.csv", index=False)
    print(f"Strategy universe: {len(registry):,}")

    pnl, positions, active, entry, full_results = evaluate_registry(
        event, registry, dates, config
    )
    full_results.to_csv(
        out / "phase9_all_strategy_results.csv.gz",
        index=False,
        compression="gzip",
    )
    np.savez_compressed(
        out / "phase9_strategy_daily_matrices.npz",
        strategy_id=registry["strategy_id"].to_numpy(),
        target_date=np.array(dates),
        pnl=pnl,
        positions=positions,
        active=active,
        entry_cash=entry,
    )

    outer_daily, inner_selection, outer_summary = nested_walkforward(
        pnl, positions, active, entry, registry, dates, config
    )
    outer_daily.to_csv(
        out / "phase9_outer_walkforward_daily_pnl.csv.gz",
        index=False,
        compression="gzip",
    )
    inner_selection.to_csv(
        out / "phase9_inner_selection_results.csv.gz",
        index=False,
        compression="gzip",
    )
    outer_summary.to_csv(out / "phase9_outer_walkforward_summary.csv", index=False)

    block_summary = (
        outer_daily.groupby(["objective", "outer_fold"])
        .agg(
            total_net_pnl=("daily_net_pnl", "sum"),
            mean_daily_net_pnl=("daily_net_pnl", "mean"),
            positions=("positions", "sum"),
            active_dates=("active", "sum"),
        )
        .reset_index()
    )
    sharpe_map = (
        outer_daily.groupby(["objective", "outer_fold"])["daily_net_pnl"]
        .apply(lambda x: float(x.mean() / x.std(ddof=1)) if x.std(ddof=1) > 1e-15 else 0.0)
        .rename("sharpe")
        .reset_index()
    )
    block_summary = block_summary.merge(sharpe_map, on=["objective", "outer_fold"], how="left")
    block_summary.to_csv(out / "phase9_block_stability.csv", index=False)

    primary = config["primary_selection_objective"]
    primary_daily = outer_daily.loc[
        outer_daily["objective"] == primary
    ].sort_values("target_date")
    bootstrap = bootstrap_series(
        primary_daily["daily_net_pnl"].to_numpy(float),
        config,
        {"series": "primary_nested_walkforward", "objective": primary},
    )
    bootstrap.to_csv(out / "phase9_outer_walkforward_bootstrap.csv", index=False)

    dsr = deflated_sharpe_table(full_results, pnl)
    dsr.to_csv(out / "phase9_deflated_sharpe.csv", index=False)
    pbo_summary, pbo_detail = pbo_cscv(pnl, full_results, config)
    pbo_summary.to_csv(out / "phase9_backtest_overfitting_probability.csv", index=False)
    pbo_detail.to_csv(
        out / "phase9_backtest_overfitting_detail.csv.gz",
        index=False,
        compression="gzip",
    )
    benchmark = load_benchmark(
        repo / config["inputs"]["phase7_benchmark_daily"], dates
    )
    reality = reality_check(pnl, full_results, benchmark, config)
    reality.to_csv(out / "phase9_reality_check_results.csv", index=False)

    candidates = choose_candidates(
        full_results, outer_summary, registry, pnl, positions, active, config
    )
    candidates.to_csv(out / "phase9_candidate_hierarchy.csv", index=False)

    role_ids = {
        role: candidates.loc[candidates["candidate_role"] == role, "strategy_id"].iloc[0]
        for role in [
            "full_sample_oracle_best_sharpe",
            "best_observed_price_long_only",
            "future_candidate_after_full_exploration",
        ]
    }
    trade_ledgers = []
    candidate_summaries = []
    for role, strategy_id in role_ids.items():
        strategy = registry.loc[registry["strategy_id"] == strategy_id].iloc[0]
        evaluation = evaluate_strategy(
            event, dates, strategy, float(config["primary_cost"]), config, keep_trades=True
        )
        ledger = pd.DataFrame(evaluation.trade_records)
        if not ledger.empty:
            ledger["candidate_role"] = role
            trade_ledgers.append(ledger)
        candidate_summaries.append({
            "candidate_role": role,
            "strategy_id": strategy_id,
            **strategy.to_dict(),
            **summarise_daily(
                evaluation.daily_pnl,
                evaluation.daily_positions,
                evaluation.daily_active,
                evaluation.daily_entry_cash,
                float(config["tail_probability"]),
            ),
        })
    candidate_trades = pd.concat(trade_ledgers, ignore_index=True) if trade_ledgers else pd.DataFrame()
    candidate_trades.to_csv(
        out / "phase9_candidate_trade_ledger.csv.gz",
        index=False,
        compression="gzip",
    )
    pd.DataFrame(candidate_summaries).to_csv(
        out / "phase9_candidate_strategy_summary.csv", index=False
    )

    oracle_id = role_ids["full_sample_oracle_best_sharpe"]
    oracle_strategy = registry.loc[registry["strategy_id"] == oracle_id].iloc[0]
    cost_table, cost_ledger = cost_sensitivity(event, dates, oracle_strategy, config)
    cost_table.to_csv(out / "phase9_cost_sensitivity.csv", index=False)
    cost_ledger.to_csv(
        out / "phase9_cost_sensitivity_trade_ledger.csv.gz",
        index=False,
        compression="gzip",
    )
    parameter_table = parameter_neighbourhood(full_results, oracle_strategy)
    parameter_table.to_csv(
        out / "phase9_best_strategy_parameter_sensitivity.csv", index=False
    )

    oracle_trades = candidate_trades.loc[
        candidate_trades["candidate_role"] == "full_sample_oracle_best_sharpe"
    ] if not candidate_trades.empty else pd.DataFrame()
    concentration = trade_concentration(oracle_trades)
    concentration.to_csv(out / "phase9_trade_concentration.csv", index=False)

    observed_rows = []
    for execution_track, group in full_results.groupby("execution_track", sort=False):
        best = (
            group.replace([np.inf, -np.inf], np.nan)
            .dropna(subset=["sharpe"])
            .sort_values(["sharpe", "total_net_pnl"], ascending=False)
            .head(1)
        )
        if not best.empty:
            observed_rows.append(best)
    observed_synthetic = pd.concat(observed_rows, ignore_index=True)
    observed_synthetic.to_csv(
        out / "phase9_observed_vs_synthetic_short_comparison.csv", index=False
    )

    leaderboard = (
        full_results.replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["sharpe"])
        .sort_values(["sharpe", "total_net_pnl"], ascending=False)
        .head(1000)
        .merge(
            dsr[[
                "strategy_id",
                "deflated_sharpe_probability",
                "expected_maximum_sharpe_under_trials",
            ]],
            on="strategy_id",
            how="left",
        )
    )
    leaderboard.to_csv(out / "phase9_sharpe_leaderboard.csv", index=False)

    figures = make_figures(
        out,
        outer_daily,
        outer_summary,
        full_results,
        cost_table,
        block_summary.loc[block_summary["objective"] == primary],
        oracle_trades,
        parameter_table,
        config,
    )
    figures.to_csv(out / "phase9_figure_registry.csv", index=False)

    primary_summary = outer_summary.loc[
        outer_summary["objective"] == primary
    ].iloc[0]
    oracle_summary = full_results.loc[
        full_results["strategy_id"] == oracle_id
    ].iloc[0]
    observed_id = role_ids["best_observed_price_long_only"]
    observed_summary = full_results.loc[
        full_results["strategy_id"] == observed_id
    ].iloc[0]

    claims = pd.DataFrame([
        {
            "claim_id": "P9_C01",
            "status": "supported_exploratory",
            "safe_wording": (
                f"The pre-registered nested walk-forward selector produced total net PnL "
                f"{primary_summary['total_net_pnl']:.6f} and settlement-date Sharpe "
                f"{primary_summary['sharpe']:.6f}."
            ),
            "restriction": "Post hoc Phase 9 extension; not untouched external validation.",
        },
        {
            "claim_id": "P9_C02",
            "status": "in_sample_upper_bound",
            "safe_wording": (
                f"The highest full-sample Sharpe among {len(registry):,} registered strategies "
                f"was {oracle_summary['sharpe']:.6f}."
            ),
            "restriction": "Must be accompanied by DSR, PBO and reality-check results.",
        },
        {
            "claim_id": "P9_C03",
            "status": "observed_price_track",
            "safe_wording": (
                f"The best long-only observed-price strategy had Sharpe "
                f"{observed_summary['sharpe']:.6f} and net PnL "
                f"{observed_summary['total_net_pnl']:.6f}."
            ),
            "restriction": "Still selected post hoc on the full sample.",
        },
        {
            "claim_id": "P9_C04",
            "status": "synthetic_short_boundary",
            "safe_wording": "Short-inclusive results use a synthetic short-YES payoff under parity.",
            "restriction": "Do not call these executable long-NO results.",
        },
    ])
    claims.to_csv(out / "phase9_claims_boundary.csv", index=False)

    checks = pd.concat([
        dependency,
        stability_status,
        pd.DataFrame([
            {
                "check": "strategy_registry_nonempty",
                "passed": len(registry) > 1000,
                "critical": True,
                "detail": f"strategies={len(registry)}",
            },
            {
                "check": "exact_support_dates",
                "passed": len(dates) == 97,
                "critical": True,
                "detail": f"dates={len(dates)}",
            },
            {
                "check": "outer_design_complete",
                "passed": len(primary_daily) == 60,
                "critical": True,
                "detail": f"outer_dates={len(primary_daily)}",
            },
            {
                "check": "all_strategies_retained",
                "passed": len(full_results) == len(registry),
                "critical": True,
                "detail": f"results={len(full_results)}; registry={len(registry)}",
            },
            {
                "check": "long_only_track_present",
                "passed": (full_results["execution_track"] == "observed_yes_long_only").any(),
                "critical": True,
                "detail": "observed-price long-only strategies retained",
            },
            {
                "check": "synthetic_short_track_labelled",
                "passed": (full_results["execution_track"] == "includes_synthetic_short_yes").any(),
                "critical": True,
                "detail": "synthetic short-inclusive strategies explicitly labelled",
            },
            {
                "check": "multiple_testing_outputs",
                "passed": not dsr.empty and not pbo_summary.empty and not reality.empty,
                "critical": True,
                "detail": "DSR, PBO and reality check generated",
            },
            {
                "check": "figures_created",
                "passed": len(figures) >= 6,
                "critical": True,
                "detail": f"figures={len(figures)}",
            },
        ]),
    ], ignore_index=True)
    checks.to_csv(out / "phase9_integrity_checks.csv", index=False)

    write_report(
        out,
        provenance,
        checks,
        outer_summary,
        candidates,
        bootstrap,
        dsr,
        pbo_summary,
        reality,
        concentration,
        observed_synthetic,
        config,
    )

    thesis_summary = pd.DataFrame([
        {
            "candidate_id": "P9_PRIMARY_OUTER_TOTAL_PNL",
            "quantity": "Primary nested walk-forward total net PnL",
            "point_estimate": primary_summary["total_net_pnl"],
            "preferred_location": "Appendix unless robust",
        },
        {
            "candidate_id": "P9_PRIMARY_OUTER_SHARPE",
            "quantity": "Primary nested walk-forward settlement-date Sharpe",
            "point_estimate": primary_summary["sharpe"],
            "preferred_location": "Appendix unless robust",
        },
        {
            "candidate_id": "P9_ORACLE_FULL_SAMPLE_SHARPE",
            "quantity": "Highest full-sample registered-strategy Sharpe",
            "point_estimate": oracle_summary["sharpe"],
            "preferred_location": "Exploratory appendix only",
        },
        {
            "candidate_id": "P9_PBO",
            "quantity": "Probability of backtest overfitting",
            "point_estimate": pbo_summary["pbo"].iloc[0],
            "preferred_location": "Appendix",
        },
        {
            "candidate_id": "P9_REALITY_CHECK_P",
            "quantity": "White reality-check p-value",
            "point_estimate": reality["white_reality_check_p_value"].iloc[0],
            "preferred_location": "Appendix",
        },
    ])
    thesis_summary.to_csv(out / "phase9_thesis_candidate_summary.csv", index=False)

    failures = checks.loc[as_bool(checks["critical"]) & ~as_bool(checks["passed"])]
    pd.DataFrame([{
        "phase": "phase9_exploratory_trading_laboratory",
        "passed": failures.empty,
        "critical_failures": len(failures),
        "strategy_count": len(registry),
        "primary_outer_total_pnl": primary_summary["total_net_pnl"],
        "primary_outer_sharpe": primary_summary["sharpe"],
        "oracle_full_sample_sharpe": oracle_summary["sharpe"],
        "exploratory": True,
        "frozen_phase1_8_unchanged": True,
        "generated_utc": utc_now(),
    }]).to_csv(out / "phase9_completion_status.csv", index=False)

    build_manifest(out, provenance)
    make_review_bundle(out)

    print("=" * 100)
    print("PHASE 9 — EXPLORATORY TRADING STRATEGY LABORATORY")
    print("=" * 100)
    print(checks.to_string(index=False))
    print()
    print("Primary nested walk-forward:")
    print(primary_summary.to_string())
    print()
    print(f"Full-sample oracle: {oracle_id}")
    print(oracle_summary[[
        "model", "decision_rule", "rule_filter", "side_mode", "top_k",
        "sizing_rule", "ranking_signal", "edge_threshold", "stability_filter",
        "execution_track", "total_net_pnl", "sharpe", "maximum_drawdown",
    ]].to_string())
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase9_review_bundle.zip'}")
    if failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print(failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
