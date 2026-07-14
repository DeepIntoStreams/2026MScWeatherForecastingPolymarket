#!/usr/bin/env python3
"""
18m full HKO market-only baseline diagnostics and figures.

This script reads the 18l full HKO contract-event market panels and produces
supervisor-ready summaries, event-book diagnostics, categorical market-only scores,
figures, and a review bundle.

It is designed to be run from the repository root:
    python3 scripts/18m_full_hko_market_only_baseline_diagnostics.py
"""

from __future__ import annotations

import math
import zipfile
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


DECISION_RULE_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]
EPS = 1e-6


def find_repo_root() -> Path:
    """Find repository root robustly from notebook, scripts, or repo root."""
    here = Path.cwd().resolve()
    candidates = [here] + list(here.parents)
    for p in candidates:
        if (p / ".git").exists() and (p / "data").exists():
            return p
    for p in candidates:
        if (p / "data" / "processed").exists():
            return p
    return here


ROOT = find_repo_root()
DATA = ROOT / "data" / "processed"
DOCS = ROOT / "docs" / "research_outputs"
FIGS = ROOT / "figures" / "18m_market_only_baseline"
BUNDLES = ROOT / "data" / "review_bundles"

for d in [DATA, DOCS, FIGS, BUNDLES]:
    d.mkdir(parents=True, exist_ok=True)


def first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None


def read_table_required(stem: str) -> pd.DataFrame:
    p = first_existing([
        DATA / f"{stem}.csv",
        DATA / f"{stem}.csv.gz",
    ])
    if p is None:
        raise FileNotFoundError(
            f"Missing required table {stem}.csv or {stem}.csv.gz in {DATA}"
        )
    print(f"Loaded {p.relative_to(ROOT)}")
    return pd.read_csv(p, low_memory=False)


def read_table_optional(stem: str) -> pd.DataFrame:
    p = first_existing([
        DATA / f"{stem}.csv",
        DATA / f"{stem}.csv.gz",
    ])
    if p is None:
        print(f"Optional table not found: {stem}")
        return pd.DataFrame()
    print(f"Loaded {p.relative_to(ROOT)}")
    return pd.read_csv(p, low_memory=False)


def order_rules(df: pd.DataFrame, col: str = "decision_rule") -> pd.DataFrame:
    if col in df.columns:
        df[col] = pd.Categorical(df[col], categories=DECISION_RULE_ORDER, ordered=True)
        return df.sort_values(col).reset_index(drop=True)
    return df


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def safe_clip(x: pd.Series | np.ndarray, eps: float = EPS) -> pd.Series | np.ndarray:
    return np.clip(x, eps, 1.0 - eps)


def dataframe_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_No rows._"
    show = df.head(max_rows).copy()
    for c in show.columns:
        if pd.api.types.is_float_dtype(show[c]):
            show[c] = show[c].map(lambda x: "" if pd.isna(x) else f"{x:.6g}")
    try:
        return show.to_markdown(index=False)
    except Exception:
        return "```text\n" + show.to_string(index=False) + "\n```"


def save_bar(df: pd.DataFrame, x: str, y: str, title: str, ylabel: str, path: Path) -> None:
    plot_df = order_rules(df.copy(), x)
    plt.figure(figsize=(8, 4.8))
    plt.bar(plot_df[x].astype(str), plot_df[y])
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel("")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def save_boxplot(df: pd.DataFrame, value: str, title: str, ylabel: str, path: Path) -> None:
    groups = []
    labels = []
    for rule in DECISION_RULE_ORDER:
        vals = df.loc[df["decision_rule"].astype(str).eq(rule), value].dropna().astype(float).values
        if len(vals):
            groups.append(vals)
            labels.append(rule)
    plt.figure(figsize=(8, 4.8))
    if groups:
        plt.boxplot(groups, labels=labels, showfliers=False)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel("")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def save_hist_by_outcome(scoring: pd.DataFrame, path: Path) -> None:
    plt.figure(figsize=(8, 4.8))
    for outcome in [0, 1]:
        vals = scoring.loc[scoring["Y_event_int"].eq(outcome), "p_market"].dropna().astype(float)
        if len(vals):
            plt.hist(vals, bins=30, alpha=0.55, label=f"Y={outcome}")
    plt.title("Market probabilities by realised outcome")
    plt.xlabel("Market-implied probability")
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def main() -> None:
    print(f"Repository root: {ROOT}")

    scoring = read_table_required("18l_full_hko_contract_event_market_scoring_panel")
    decision = read_table_required("18l_full_hko_contract_event_no_lookahead_decision_panel")
    score_summary_18l = read_table_required("18l_full_hko_contract_event_market_score_summary")
    book_18l = read_table_required("18l_full_hko_contract_event_book_snapshot_summary")
    diagnostics_18l = read_table_optional("18l_clob_recovery_diagnostics")
    integrity_18l = read_table_optional("18l_clob_recovery_integrity_checks")
    issues_18l = read_table_optional("18l_clob_recovery_issues")
    target = read_table_optional("18k_full_hko_contract_event_target_panel")

    for df in [scoring, decision]:
        if "event_date" in df.columns:
            df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date.astype(str)
        for c in ["p_market", "Y_event_int", "brier_market", "log_score_market", "price_staleness_hours"]:
            if c in df.columns:
                df[c] = to_num(df[c])

    if "Y_event_int" not in decision.columns and "Y_event" in decision.columns:
        decision["Y_event_int"] = to_num(decision["Y_event"]).round()
    if "Y_event_int" not in scoring.columns and "Y_event" in scoring.columns:
        scoring["Y_event_int"] = to_num(scoring["Y_event"]).round()

    # Expected number of contracts per event date, from the realised target panel if available.
    if not target.empty and "event_date" in target.columns:
        target["event_date"] = pd.to_datetime(target["event_date"], errors="coerce").dt.date.astype(str)
        expected_by_date = (
            target.groupby("event_date")
            .size()
            .rename("expected_contracts")
            .reset_index()
        )
    else:
        expected_by_date = (
            decision.groupby("event_date")
            .size()
            .groupby(level=0)
            .max()
            .rename("expected_contracts")
            .reset_index()
        )

    # Enhanced binary score summaries.
    binary_by_rule = (
        scoring.groupby("decision_rule", dropna=False)
        .agg(
            n=("p_market", "size"),
            mean_brier=("brier_market", "mean"),
            median_brier=("brier_market", "median"),
            mean_log_score=("log_score_market", "mean"),
            median_log_score=("log_score_market", "median"),
            mean_p_market=("p_market", "mean"),
            outcome_rate=("Y_event_int", "mean"),
            median_staleness_hours=("price_staleness_hours", "median"),
            p95_staleness_hours=("price_staleness_hours", lambda x: np.nanpercentile(x, 95) if len(x.dropna()) else np.nan),
        )
        .reset_index()
    )
    binary_by_rule = order_rules(binary_by_rule)

    binary_by_rule_type = (
        scoring.groupby(["decision_rule", "contract_event_type_v2"], dropna=False)
        .agg(
            n=("p_market", "size"),
            mean_brier=("brier_market", "mean"),
            mean_log_score=("log_score_market", "mean"),
            mean_p_market=("p_market", "mean"),
            outcome_rate=("Y_event_int", "mean"),
            median_staleness_hours=("price_staleness_hours", "median"),
        )
        .reset_index()
    )
    binary_by_rule_type = order_rules(binary_by_rule_type)

    # Event-book categorical diagnostics. These are the natural scores for a complete
    # daily categorical market where exactly one contract should resolve Yes.
    book_rows = []
    for (event_date, rule), g in decision.groupby(["event_date", "decision_rule"], dropna=False):
        gg = g.copy()
        gg["p_market"] = to_num(gg["p_market"])
        gg["Y_event_int"] = to_num(gg["Y_event_int"])
        p = gg["p_market"].astype(float).to_numpy()
        y = gg["Y_event_int"].fillna(0).astype(float).to_numpy()
        valid = np.isfinite(p) & np.isfinite(y)
        p = p[valid]
        y = y[valid]

        total = float(np.nansum(p)) if len(p) else np.nan
        yes_count = int(np.nansum(y)) if len(y) else 0
        winning_p = float(np.nansum(p[y == 1])) if len(p) else np.nan
        max_stale = float(np.nanmax(to_num(gg["price_staleness_hours"]))) if "price_staleness_hours" in gg.columns and gg["price_staleness_hours"].notna().any() else np.nan
        n_snap = int(len(p))

        if np.isfinite(total) and total > 0:
            p_norm = p / total
            winning_p_norm = winning_p / total
            normalised_categorical_log_score = -math.log(float(np.clip(winning_p_norm, EPS, 1.0 - EPS)))
            normalised_multiclass_brier = float(np.nansum((p_norm - y) ** 2))
        else:
            winning_p_norm = np.nan
            normalised_categorical_log_score = np.nan
            normalised_multiclass_brier = np.nan

        raw_categorical_log_score = -math.log(float(np.clip(winning_p, EPS, 1.0 - EPS))) if np.isfinite(winning_p) else np.nan
        raw_multiclass_brier = float(np.nansum((p - y) ** 2)) if len(p) else np.nan

        book_rows.append(
            {
                "event_date": event_date,
                "decision_rule": str(rule),
                "n_price_snapshots": n_snap,
                "n_yes_contracts": yes_count,
                "total_book_market_probability": total,
                "winning_contract_market_probability": winning_p,
                "winning_contract_market_probability_normalised": winning_p_norm,
                "book_probability_error_vs_one": total - 1.0 if np.isfinite(total) else np.nan,
                "absolute_book_probability_error_vs_one": abs(total - 1.0) if np.isfinite(total) else np.nan,
                "raw_categorical_log_score": raw_categorical_log_score,
                "normalised_categorical_log_score": normalised_categorical_log_score,
                "raw_multiclass_brier": raw_multiclass_brier,
                "normalised_multiclass_brier": normalised_multiclass_brier,
                "max_price_staleness_hours": max_stale,
            }
        )

    book_metrics = pd.DataFrame(book_rows)
    book_metrics = book_metrics.merge(expected_by_date, on="event_date", how="left")
    book_metrics["full_book_observed"] = book_metrics["n_price_snapshots"].eq(book_metrics["expected_contracts"])
    book_metrics["categorical_score_ready"] = (
        book_metrics["n_yes_contracts"].eq(1)
        & book_metrics["winning_contract_market_probability"].notna()
        & book_metrics["total_book_market_probability"].gt(0)
    )
    book_metrics = order_rules(book_metrics)

    categorical_by_rule = (
        book_metrics.loc[book_metrics["categorical_score_ready"]]
        .groupby("decision_rule", dropna=False)
        .agg(
            n_books=("event_date", "size"),
            full_book_rate=("full_book_observed", "mean"),
            mean_total_book_probability=("total_book_market_probability", "mean"),
            median_total_book_probability=("total_book_market_probability", "median"),
            mean_abs_book_probability_error=("absolute_book_probability_error_vs_one", "mean"),
            median_winning_probability_raw=("winning_contract_market_probability", "median"),
            median_winning_probability_normalised=("winning_contract_market_probability_normalised", "median"),
            mean_raw_categorical_log_score=("raw_categorical_log_score", "mean"),
            mean_normalised_categorical_log_score=("normalised_categorical_log_score", "mean"),
            mean_raw_multiclass_brier=("raw_multiclass_brier", "mean"),
            mean_normalised_multiclass_brier=("normalised_multiclass_brier", "mean"),
            median_max_staleness_hours=("max_price_staleness_hours", "median"),
        )
        .reset_index()
    )
    categorical_by_rule = order_rules(categorical_by_rule)

    # Compare binary and categorical results in one compact supervisor table.
    supervisor_key_table = binary_by_rule.merge(
        categorical_by_rule[
            [
                "decision_rule",
                "n_books",
                "mean_normalised_categorical_log_score",
                "mean_normalised_multiclass_brier",
                "mean_abs_book_probability_error",
                "median_winning_probability_normalised",
            ]
        ],
        on="decision_rule",
        how="left",
    )

    # Decision-rule rankings.
    ranking_rows = []
    metrics = [
        ("binary_mean_brier", binary_by_rule, "mean_brier", True),
        ("binary_mean_log_score", binary_by_rule, "mean_log_score", True),
        ("normalised_categorical_log_score", categorical_by_rule, "mean_normalised_categorical_log_score", True),
        ("normalised_multiclass_brier", categorical_by_rule, "mean_normalised_multiclass_brier", True),
        ("book_coherence_absolute_error", categorical_by_rule, "mean_abs_book_probability_error", True),
        ("median_normalised_winner_probability", categorical_by_rule, "median_winning_probability_normalised", False),
    ]
    for metric_name, df, col, lower_better in metrics:
        if df.empty or col not in df.columns:
            continue
        temp = df[["decision_rule", col]].dropna().copy()
        temp["metric"] = metric_name
        temp["lower_better"] = lower_better
        temp["rank"] = temp[col].rank(method="min", ascending=lower_better).astype(int)
        temp = temp.rename(columns={col: "value"})
        ranking_rows.append(temp[["metric", "decision_rule", "value", "rank", "lower_better"]])
    rankings = pd.concat(ranking_rows, ignore_index=True) if ranking_rows else pd.DataFrame()

    # Integrity checks for 18m.
    checks = []
    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    check("scoring_panel_nonempty", len(scoring) > 0, f"rows={len(scoring)}")
    check("decision_panel_nonempty", len(decision) > 0, f"rows={len(decision)}")
    check("book_metrics_nonempty", len(book_metrics) > 0, f"rows={len(book_metrics)}")
    check("categorical_summary_nonempty", len(categorical_by_rule) > 0, f"rows={len(categorical_by_rule)}")
    if "p_market" in scoring.columns:
        bad_prob = int((scoring["p_market"].dropna().lt(0) | scoring["p_market"].dropna().gt(1)).sum())
        check("probabilities_in_unit_interval", bad_prob == 0, f"bad_probabilities={bad_prob}")
    if "price_staleness_hours" in scoring.columns:
        neg_stale = int(scoring["price_staleness_hours"].dropna().lt(0).sum())
        check("non_negative_staleness", neg_stale == 0, f"negative_staleness={neg_stale}")
    if "n_yes_contracts" in book_metrics.columns and "categorical_score_ready" in book_metrics.columns:
        bad_scored_yes = int((book_metrics.loc[book_metrics["categorical_score_ready"], "n_yes_contracts"] != 1).sum())
        not_score_ready = int((~book_metrics["categorical_score_ready"]).sum())
        check("categorical_scored_books_have_one_winner", bad_scored_yes == 0, f"bad_scored_books={bad_scored_yes}; unscored_books={not_score_ready}")
    if "expected_contracts" in book_metrics.columns:
        full_rate = float(book_metrics["full_book_observed"].mean()) if len(book_metrics) else np.nan
        check("some_full_books_observed", full_rate > 0, f"full_book_rate={full_rate:.4f}")
    if not integrity_18l.empty and {"passed"}.issubset(integrity_18l.columns):
        failed_18l = int((integrity_18l["passed"].astype(str).str.lower() != "true").sum())
        check("upstream_18l_integrity_checks_passed", failed_18l == 0, f"failed_18l_checks={failed_18l}")

    integrity = pd.DataFrame(checks)

    # Save tables.
    outputs = {}
    def save_csv(df: pd.DataFrame, name: str) -> Path:
        path = DATA / name
        df.to_csv(path, index=False)
        outputs[name] = path
        print(f"Wrote {path.relative_to(ROOT)} ({len(df)} rows)")
        return path

    save_csv(binary_by_rule, "18m_binary_market_score_by_decision_rule.csv")
    save_csv(binary_by_rule_type, "18m_binary_market_score_by_decision_rule_and_event_type.csv")
    save_csv(book_metrics, "18m_event_book_categorical_score_panel.csv")
    save_csv(categorical_by_rule, "18m_event_book_categorical_score_by_decision_rule.csv")
    save_csv(supervisor_key_table, "18m_supervisor_market_only_key_table.csv")
    save_csv(rankings, "18m_market_only_decision_rule_rankings.csv")
    save_csv(integrity, "18m_market_only_integrity_checks.csv")

    # Figures.
    figures = {}
    all_binary = binary_by_rule.copy()
    save_bar(all_binary, "decision_rule", "mean_brier", "Binary market Brier score by decision rule", "Mean Brier score", FIGS / "18m_binary_brier_by_decision_rule.png")
    figures["18m_binary_brier_by_decision_rule.png"] = FIGS / "18m_binary_brier_by_decision_rule.png"
    save_bar(all_binary, "decision_rule", "mean_log_score", "Binary market log score by decision rule", "Mean log score", FIGS / "18m_binary_log_score_by_decision_rule.png")
    figures["18m_binary_log_score_by_decision_rule.png"] = FIGS / "18m_binary_log_score_by_decision_rule.png"

    if not categorical_by_rule.empty:
        save_bar(categorical_by_rule, "decision_rule", "mean_normalised_categorical_log_score", "Normalised categorical log score by decision rule", "Mean categorical log score", FIGS / "18m_normalised_categorical_log_score_by_decision_rule.png")
        figures["18m_normalised_categorical_log_score_by_decision_rule.png"] = FIGS / "18m_normalised_categorical_log_score_by_decision_rule.png"
        save_bar(categorical_by_rule, "decision_rule", "mean_normalised_multiclass_brier", "Normalised multiclass Brier score by decision rule", "Mean multiclass Brier score", FIGS / "18m_normalised_multiclass_brier_by_decision_rule.png")
        figures["18m_normalised_multiclass_brier_by_decision_rule.png"] = FIGS / "18m_normalised_multiclass_brier_by_decision_rule.png"

    save_boxplot(book_metrics, "book_probability_error_vs_one", "Book probability error relative to one", "Total book probability minus one", FIGS / "18m_book_probability_error_boxplot_by_decision_rule.png")
    figures["18m_book_probability_error_boxplot_by_decision_rule.png"] = FIGS / "18m_book_probability_error_boxplot_by_decision_rule.png"
    save_boxplot(book_metrics, "winning_contract_market_probability_normalised", "Normalised winning-contract probability", "Normalised winning probability", FIGS / "18m_normalised_winning_probability_boxplot_by_decision_rule.png")
    figures["18m_normalised_winning_probability_boxplot_by_decision_rule.png"] = FIGS / "18m_normalised_winning_probability_boxplot_by_decision_rule.png"
    save_boxplot(scoring, "price_staleness_hours", "Price staleness by decision rule", "Staleness, hours", FIGS / "18m_price_staleness_boxplot_by_decision_rule.png")
    figures["18m_price_staleness_boxplot_by_decision_rule.png"] = FIGS / "18m_price_staleness_boxplot_by_decision_rule.png"
    save_hist_by_outcome(scoring, FIGS / "18m_market_probability_histogram_by_outcome.png")
    figures["18m_market_probability_histogram_by_outcome.png"] = FIGS / "18m_market_probability_histogram_by_outcome.png"

    # Report.
    best_binary_brier = binary_by_rule.sort_values("mean_brier").head(1)
    best_binary_log = binary_by_rule.sort_values("mean_log_score").head(1)
    best_cat_log = categorical_by_rule.sort_values("mean_normalised_categorical_log_score").head(1) if not categorical_by_rule.empty else pd.DataFrame()
    best_cat_brier = categorical_by_rule.sort_values("mean_normalised_multiclass_brier").head(1) if not categorical_by_rule.empty else pd.DataFrame()

    report = f"""# 18m full HKO market-only baseline diagnostics

Generated from repository root: `{ROOT}`

## Purpose

This step converts the 18l full Hong Kong HKO contract-event CLOB recovery into supervisor-ready market-only diagnostics. It keeps the binary contract-level scoring baseline, adds event-book probability diagnostics, and adds categorical scores for the daily contract book in which exactly one contract should resolve Yes.

## Input status

- Contract-level scoring rows: `{len(scoring)}`
- Decision-panel rows: `{len(decision)}`
- Event-book decision snapshots: `{len(book_metrics)}`
- Categorical score-ready event-book snapshots: `{int(book_metrics["categorical_score_ready"].sum()) if "categorical_score_ready" in book_metrics.columns else 0}`
- Upstream 18l missing-decision-price rows: `{len(issues_18l) if not issues_18l.empty else 0}`

## Binary market-only score by decision rule

{dataframe_to_markdown(binary_by_rule)}

## Event-book categorical score by decision rule

{dataframe_to_markdown(categorical_by_rule)}

## Supervisor key table

{dataframe_to_markdown(supervisor_key_table)}

## Decision-rule rankings

{dataframe_to_markdown(rankings.sort_values(["metric", "rank"]) if not rankings.empty else rankings)}

## Integrity checks

{dataframe_to_markdown(integrity)}

## Interpretation

The binary contract-level score remains the appropriate direct extension of the earlier threshold-contract evaluation, because every listed contract is a separate binary Polymarket outcome. The event-book categorical score is an additional diagnostic that uses the fact that the HKO categorical family forms a daily partition of the realised temperature space. The normalised categorical score is useful for checking what the market believed conditional on the listed contract book, while the raw book probability diagnostics show whether listed YES prices summed materially above or below one.

Best binary Brier decision rule: `{best_binary_brier["decision_rule"].astype(str).iloc[0] if len(best_binary_brier) else "NA"}`.

Best binary log-score decision rule: `{best_binary_log["decision_rule"].astype(str).iloc[0] if len(best_binary_log) else "NA"}`.

Best normalised categorical log-score decision rule: `{best_cat_log["decision_rule"].astype(str).iloc[0] if len(best_cat_log) else "NA"}`.

Best normalised multiclass Brier decision rule: `{best_cat_brier["decision_rule"].astype(str).iloc[0] if len(best_cat_brier) else "NA"}`.

## Figures

- `figures/18m_market_only_baseline/18m_binary_brier_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_binary_log_score_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_normalised_categorical_log_score_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_normalised_multiclass_brier_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_book_probability_error_boxplot_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_normalised_winning_probability_boxplot_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_price_staleness_boxplot_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_market_probability_histogram_by_outcome.png`

## Output files

- `data/processed/18m_binary_market_score_by_decision_rule.csv`
- `data/processed/18m_binary_market_score_by_decision_rule_and_event_type.csv`
- `data/processed/18m_event_book_categorical_score_panel.csv`
- `data/processed/18m_event_book_categorical_score_by_decision_rule.csv`
- `data/processed/18m_supervisor_market_only_key_table.csv`
- `data/processed/18m_market_only_decision_rule_rankings.csv`
- `data/processed/18m_market_only_integrity_checks.csv`
- `docs/research_outputs/18m_full_hko_market_only_baseline_report.md`
- `data/review_bundles/18m_review_bundle.zip`
"""

    report_path = DOCS / "18m_full_hko_market_only_baseline_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Wrote {report_path.relative_to(ROOT)}")

    # Bundle.
    bundle_path = BUNDLES / "18m_review_bundle.zip"
    bundle_members = list(outputs.values()) + [report_path] + list(figures.values())
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in bundle_members:
            if p.exists():
                zf.write(p, arcname=str(p.relative_to(ROOT)))
    print(f"Wrote {bundle_path.relative_to(ROOT)}")

    print("\n18m complete.")
    print(f"Review bundle: {bundle_path}")


if __name__ == "__main__":
    main()
