#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path.cwd()
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"
FIGURES = ROOT / "figures" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

MAIN_ROLE = "formally_certified_upper_tail_threshold"
EPS = 1e-6

DECISION_ORDER = [
    "last_price_before_24h_prior",
    "last_price_before_12h_prior",
    "last_price_before_6h_prior",
    "last_price_before_event_day_hkt",
]
DECISION_LABELS = {
    "last_price_before_24h_prior": "24h prior",
    "last_price_before_12h_prior": "12h prior",
    "last_price_before_6h_prior": "6h prior",
    "last_price_before_event_day_hkt": "Event-day open",
}


def safe_table(df: pd.DataFrame) -> str:
    """Return a markdown table when tabulate is available, otherwise a plain aligned table."""
    try:
        return df.to_markdown(index=False)
    except Exception:
        return "\n```text\n" + df.to_string(index=False) + "\n```"

INPUTS = {
    "hko_targets": PROCESSED / "18f_hko_daily_extract_targets_20260301_20260531.csv",
    "event_sweep": PROCESSED / "18f_polymarket_event_sweep_20260313_20260531.csv",
    "child_markets": PROCESSED / "18f_polymarket_child_markets_20260313_20260531.csv",
    "floor_validation": PROCESSED / "18f_hko_polymarket_floor_validation_panel_20260313_20260531.csv",
    "upper_tail": PROCESSED / "18f_hko_upper_tail_threshold_contracts_20260313_20260531.csv",
    "price_obs": PROCESSED / "18h_hko_upper_tail_narrow_window_price_observations_20260313_20260531.csv",
    "decision_panel": PROCESSED / "18h_hko_upper_tail_no_lookahead_decision_panel_20260313_20260531.csv",
    "scoring_ready": PROCESSED / "18h_hko_upper_tail_scoring_ready_market_panel_20260313_20260531.csv",
    "score_summary": PROCESSED / "18h_hko_upper_tail_market_only_score_summary_20260313_20260531.csv",
    "diagnostics": PROCESSED / "18h_clob_narrow_window_diagnostics_20260313_20260531.csv",
}

OUTPUTS = {
    "main_scoring_panel": PROCESSED / "18i_hko_main_scoring_panel_formally_certified.csv",
    "main_score_summary": PROCESSED / "18i_hko_main_market_only_score_summary.csv",
    "coverage_summary": PROCESSED / "18i_hko_empirical_coverage_summary.csv",
    "integrity_checks": PROCESSED / "18i_hko_empirical_integrity_checks.csv",
    "monthly_summary": PROCESSED / "18i_hko_monthly_contract_summary.csv",
    "decision_rule_summary": PROCESSED / "18i_hko_decision_rule_operational_summary.csv",
    "report": REPORTS / "18i_hko_empirical_baseline_report.md",
}

FIGURE_PATHS = {
    "brier": FIGURES / "18i_hko_market_brier_by_decision_rule.png",
    "log_score": FIGURES / "18i_hko_market_log_score_by_decision_rule.png",
    "price_staleness": FIGURES / "18i_hko_price_staleness_by_decision_rule.png",
    "monthly_coverage": FIGURES / "18i_hko_monthly_coverage.png",
    "probability_histogram": FIGURES / "18i_hko_market_probability_histogram.png",
}


def read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        if required:
            raise FileNotFoundError(f"Missing or empty required input: {path}")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        if required:
            raise
        return pd.DataFrame()


def recompute_scores(score: pd.DataFrame) -> pd.DataFrame:
    score = score.copy()
    score["p_market"] = pd.to_numeric(score["p_market"], errors="coerce")
    score["Y_ge_K"] = pd.to_numeric(score["Y_ge_K"], errors="coerce")
    score = score.dropna(subset=["p_market", "Y_ge_K"]).copy()
    score["p_market"] = score["p_market"].clip(0, 1)
    score["p_clipped"] = score["p_market"].clip(EPS, 1 - EPS)
    score["brier_market"] = (score["p_market"] - score["Y_ge_K"]) ** 2
    score["log_score_market"] = -(
        score["Y_ge_K"] * np.log(score["p_clipped"])
        + (1 - score["Y_ge_K"]) * np.log(1 - score["p_clipped"])
    )
    return score


def summarise_scores(score: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "decision_rule", "decision_label", "n", "mean_brier", "median_brier",
        "mean_log_score", "median_log_score", "mean_p_market", "median_p_market",
        "outcome_rate", "median_price_staleness_hours", "max_price_staleness_hours",
    ]
    if score.empty:
        return pd.DataFrame(columns=columns)

    summary = (
        score.groupby("decision_rule", dropna=False)
        .agg(
            n=("brier_market", "size"),
            mean_brier=("brier_market", "mean"),
            median_brier=("brier_market", "median"),
            mean_log_score=("log_score_market", "mean"),
            median_log_score=("log_score_market", "median"),
            mean_p_market=("p_market", "mean"),
            median_p_market=("p_market", "median"),
            outcome_rate=("Y_ge_K", "mean"),
            median_price_staleness_hours=("price_staleness_hours", "median"),
            max_price_staleness_hours=("price_staleness_hours", "max"),
        )
        .reset_index()
    )
    summary["decision_label"] = summary["decision_rule"].map(DECISION_LABELS).fillna(summary["decision_rule"])
    order_map = {rule: i for i, rule in enumerate(DECISION_ORDER)}
    summary["_order"] = summary["decision_rule"].map(order_map).fillna(99)
    summary = summary.sort_values(["_order", "decision_rule"]).drop(columns=["_order"]).reset_index(drop=True)
    return summary[columns]


def metric_rows(hko, event_sweep, child, upper_tail, price_obs, decision, score, diagnostics):
    rows = []

    def add(metric, value, note=""):
        rows.append({"metric": metric, "value": value, "note": note})

    add("hko_rows", len(hko), "Official HKO Daily Extract / metob maximum-temperature observations.")
    if len(hko) and "event_date" in hko.columns:
        dates = pd.to_datetime(hko["event_date"], errors="coerce").dropna()
        if len(dates):
            add("hko_start_date", dates.min().date(), "")
            add("hko_end_date", dates.max().date(), "")

    add("polymarket_event_slugs_swept", len(event_sweep), "Deterministic daily Hong Kong highest-temperature event slugs.")
    if "event_found_gamma" in event_sweep.columns:
        add("gamma_events_found", int(pd.to_numeric(event_sweep["event_found_gamma"], errors="coerce").fillna(0).sum()), "")
    if "event_found_web" in event_sweep.columns:
        add("web_pages_found", int(pd.to_numeric(event_sweep["event_found_web"], errors="coerce").fillna(0).sum()), "")

    add("flattened_child_market_rows", len(child), "")
    add("upper_tail_threshold_rows", len(upper_tail), "")
    if "empirical_role" in upper_tail.columns:
        add("formally_certified_upper_tail_rows", int((upper_tail["empirical_role"] == MAIN_ROLE).sum()), "")
        add("non_certified_upper_tail_candidate_rows", int((upper_tail["empirical_role"] != MAIN_ROLE).sum()), "")

    add("price_observation_rows", len(price_obs), "Recovered CLOB narrow-window price observations.")
    add("no_lookahead_decision_rows", len(decision), "Rows after no-lookahead price cutoffs.")
    add("scoring_ready_rows", len(score), "Rows with market probability and realised HKO binary outcome.")
    if "empirical_role" in score.columns:
        add("main_formally_certified_scoring_rows", int((score["empirical_role"] == MAIN_ROLE).sum()), "")

    if len(diagnostics):
        add("clob_diagnostic_endpoint_attempts", len(diagnostics), "")
        if "history_rows" in diagnostics.columns:
            add("diagnostic_attempts_with_history", int((pd.to_numeric(diagnostics["history_rows"], errors="coerce").fillna(0) > 0).sum()), "")

    return pd.DataFrame(rows)


def monthly_summary(upper_tail: pd.DataFrame, score: pd.DataFrame) -> pd.DataFrame:
    parts = []

    if len(upper_tail):
        u = upper_tail.copy()
        u["event_date_dt"] = pd.to_datetime(u["event_date"], errors="coerce")
        u["month"] = u["event_date_dt"].dt.to_period("M").astype(str)
        u["threshold_K"] = pd.to_numeric(u.get("threshold_K"), errors="coerce")
        u["Y_ge_K"] = pd.to_numeric(u.get("Y_ge_K"), errors="coerce")
        part = (
            u.groupby("month")
            .agg(
                upper_tail_contracts=("market_slug", "size"),
                formally_certified_contracts=("empirical_role", lambda s: int((s == MAIN_ROLE).sum())),
                mean_threshold_K=("threshold_K", "mean"),
                hko_outcome_rate=("Y_ge_K", "mean"),
            )
            .reset_index()
        )
        parts.append(part)

    if len(score):
        s = score.copy()
        s = s[s["empirical_role"] == MAIN_ROLE].copy() if "empirical_role" in s.columns else s
        s["event_date_dt"] = pd.to_datetime(s["event_date"], errors="coerce")
        s["month"] = s["event_date_dt"].dt.to_period("M").astype(str)
        part = (
            s.groupby("month")
            .agg(
                formally_certified_scoring_rows=("market_slug", "size"),
                scoring_unique_contracts=("market_slug", "nunique"),
                mean_brier=("brier_market", "mean"),
                mean_log_score=("log_score_market", "mean"),
            )
            .reset_index()
        )
        parts.append(part)

    if not parts:
        return pd.DataFrame()

    out = parts[0]
    for part in parts[1:]:
        out = out.merge(part, on="month", how="outer")
    return out.sort_values("month").reset_index(drop=True)


def integrity_checks(score: pd.DataFrame, upper_tail: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def check(name, passed, detail):
        rows.append({"check": name, "passed": bool(passed), "detail": detail})

    check("main_role_present", "empirical_role" in score.columns and (score["empirical_role"] == MAIN_ROLE).any(), MAIN_ROLE)
    check("probabilities_in_unit_interval", len(score) == 0 or pd.to_numeric(score["p_market"], errors="coerce").between(0, 1).all(), "All p_market values should lie in [0,1].")
    check("binary_outcomes", len(score) == 0 or set(pd.to_numeric(score["Y_ge_K"], errors="coerce").dropna().unique()).issubset({0, 1}), "All Y_ge_K values should be binary.")
    check("non_negative_scores", len(score) == 0 or ((pd.to_numeric(score["brier_market"], errors="coerce") >= 0).all() and (pd.to_numeric(score["log_score_market"], errors="coerce") >= 0).all()), "Brier and log scores should be non-negative.")

    if {"decision_timestamp_utc", "decision_cutoff_utc"}.issubset(score.columns):
        ts = pd.to_datetime(score["decision_timestamp_utc"], utc=True, errors="coerce")
        cut = pd.to_datetime(score["decision_cutoff_utc"], utc=True, errors="coerce")
        ok = (ts <= cut).fillna(False).all()
        max_violation = (ts - cut).dt.total_seconds().max()
        check("no_lookahead_timestamps", ok, f"Max decision minus cutoff seconds: {max_violation}")

    if "empirical_role" in upper_tail.columns:
        formal_count = int((upper_tail["empirical_role"] == MAIN_ROLE).sum())
        check("formal_certified_subset_nonempty", formal_count > 0, f"Formal upper-tail rows: {formal_count}")

    return pd.DataFrame(rows)


def decision_rule_operational_summary(score: pd.DataFrame) -> pd.DataFrame:
    if score.empty:
        return pd.DataFrame()

    out = (
        score.groupby("decision_rule", dropna=False)
        .agg(
            n=("market_slug", "size"),
            unique_contracts=("market_slug", "nunique"),
            median_staleness_hours=("price_staleness_hours", "median"),
            mean_staleness_hours=("price_staleness_hours", "mean"),
            max_staleness_hours=("price_staleness_hours", "max"),
        )
        .reset_index()
    )
    if "price_query_lookback_hours" in score.columns:
        lookback = score.groupby("decision_rule")["price_query_lookback_hours"].mean().reset_index(name="mean_price_query_lookback_hours")
        out = out.merge(lookback, on="decision_rule", how="left")
    out["decision_label"] = out["decision_rule"].map(DECISION_LABELS).fillna(out["decision_rule"])
    order_map = {rule: i for i, rule in enumerate(DECISION_ORDER)}
    out["_order"] = out["decision_rule"].map(order_map).fillna(99)
    return out.sort_values(["_order", "decision_rule"]).drop(columns=["_order"]).reset_index(drop=True)


def make_figures(summary: pd.DataFrame, main_score: pd.DataFrame, monthly: pd.DataFrame):
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"Matplotlib unavailable; figures skipped: {exc}")
        return

    if not summary.empty:
        x = summary["decision_label"].tolist()

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar(x, summary["mean_brier"])
        ax.set_title("Market-only Brier score by no-lookahead decision rule")
        ax.set_xlabel("Decision rule")
        ax.set_ylabel("Mean Brier score")
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        fig.savefig(FIGURE_PATHS["brier"], dpi=200)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar(x, summary["mean_log_score"])
        ax.set_title("Market-only log score by no-lookahead decision rule")
        ax.set_xlabel("Decision rule")
        ax.set_ylabel("Mean log score")
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        fig.savefig(FIGURE_PATHS["log_score"], dpi=200)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar(x, summary["median_price_staleness_hours"])
        ax.set_title("Median price staleness by no-lookahead decision rule")
        ax.set_xlabel("Decision rule")
        ax.set_ylabel("Median staleness, hours")
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        fig.savefig(FIGURE_PATHS["price_staleness"], dpi=200)
        plt.close(fig)

    if not main_score.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(pd.to_numeric(main_score["p_market"], errors="coerce").dropna(), bins=20)
        ax.set_title("Distribution of no-lookahead market-implied probabilities")
        ax.set_xlabel("Market probability")
        ax.set_ylabel("Count")
        fig.tight_layout()
        fig.savefig(FIGURE_PATHS["probability_histogram"], dpi=200)
        plt.close(fig)

    if not monthly.empty and "formally_certified_scoring_rows" in monthly.columns:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(monthly["month"].astype(str), monthly["formally_certified_scoring_rows"].fillna(0))
        ax.set_title("Formally certified scoring rows by month")
        ax.set_xlabel("Month")
        ax.set_ylabel("Scoring rows")
        ax.tick_params(axis="x", rotation=20)
        fig.tight_layout()
        fig.savefig(FIGURE_PATHS["monthly_coverage"], dpi=200)
        plt.close(fig)


def build_report(coverage, main_summary, monthly, integrity, decision_ops):
    report = []
    report.append("# 18i Hong Kong empirical baseline report\n")
    report.append("This report consolidates the successful 18f official-outcome construction and 18h narrow-window CLOB price recovery into a dissertation-facing empirical baseline.\n")
    report.append("The main empirical sample is restricted to `empirical_role = formally_certified_upper_tail_threshold`; exploratory candidate rows are excluded from the headline result.\n")

    report.append("## Coverage summary\n")
    report.append(safe_table(coverage) if not coverage.empty else "_No coverage summary available._")
    report.append("")

    report.append("## Main market-only score summary\n")
    if main_summary.empty:
        report.append("_No formally certified scoring rows were available._\n")
    else:
        report.append(safe_table(main_summary))
        report.append("")
        best_brier = main_summary.sort_values(["mean_brier", "mean_log_score"]).iloc[0]
        best_log = main_summary.sort_values(["mean_log_score", "mean_brier"]).iloc[0]
        report.append(
            f"The lowest mean Brier score is obtained by `{best_brier['decision_rule']}` "
            f"with mean Brier score `{best_brier['mean_brier']:.6f}` over `{int(best_brier['n'])}` rows. "
            f"The lowest mean log score is obtained by `{best_log['decision_rule']}` "
            f"with mean log score `{best_log['mean_log_score']:.6f}` over `{int(best_log['n'])}` rows.\n"
        )

    report.append("## Operational decision-rule summary\n")
    report.append(safe_table(decision_ops) if not decision_ops.empty else "_No operational decision-rule summary available._")
    report.append("")

    report.append("## Monthly coverage\n")
    report.append(safe_table(monthly) if not monthly.empty else "_No monthly summary available._")
    report.append("")

    report.append("## Integrity checks\n")
    report.append(safe_table(integrity) if not integrity.empty else "_No integrity checks available._")
    report.append("")

    report.append("## Figures\n")
    for name, path in FIGURE_PATHS.items():
        if path.exists():
            report.append(f"- `{name}`: `{path.relative_to(ROOT)}`")
    report.append("")

    report.append("## Dissertation-facing interpretation\n")
    if not main_summary.empty:
        best = main_summary.sort_values(["mean_brier", "mean_log_score"]).iloc[0]
        report.append(
            "Hong Kong is now usable as the primary empirical baseline. The official-outcome side is based on HKO Daily Extract / metob maximum-temperature observations, "
            "and the market side is based on deterministic Polymarket event slug retrieval and narrow-window CLOB price recovery. "
            f"For the formally certified upper-tail subset, the best market-only decision rule by mean Brier score is `{best['decision_rule']}`, "
            f"with `n = {int(best['n'])}`, mean Brier score `{best['mean_brier']:.6f}`, mean log score `{best['mean_log_score']:.6f}`, "
            f"mean market probability `{best['mean_p_market']:.6f}`, and outcome rate `{best['outcome_rate']:.6f}`. "
            "This table should be used as the market-only benchmark before adding forecast-implied probabilities from AI/weather sources.\n"
        )

    report.append("## Recommended next step\n")
    report.append("Use this 18i baseline as the fixed HK market-only benchmark. The next modelling step is to build forecast-implied threshold probabilities for the same `(event_date, threshold_K)` rows and compare Brier/log scores against the market-only probabilities under identical no-lookahead decision rules.\n")
    return "\n".join(report)


def main():
    print("Repository root:", ROOT)

    hko = read_csv(INPUTS["hko_targets"])
    event_sweep = read_csv(INPUTS["event_sweep"])
    child = read_csv(INPUTS["child_markets"])
    _floor = read_csv(INPUTS["floor_validation"], required=False)
    upper_tail = read_csv(INPUTS["upper_tail"])
    price_obs = read_csv(INPUTS["price_obs"])
    decision = read_csv(INPUTS["decision_panel"])
    score = read_csv(INPUTS["scoring_ready"])
    _score_summary_existing = read_csv(INPUTS["score_summary"], required=False)
    diagnostics = read_csv(INPUTS["diagnostics"], required=False)

    for df in [hko, event_sweep, child, upper_tail, price_obs, decision, score, diagnostics]:
        if "event_date" in df.columns:
            df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date

    score = recompute_scores(score)

    if "empirical_role" not in score.columns:
        raise ValueError("18h scoring-ready file has no empirical_role column; cannot define formal main sample.")

    main_score = score[score["empirical_role"] == MAIN_ROLE].copy()
    main_score = main_score.sort_values(["event_date", "threshold_K", "market_slug", "decision_rule"]).reset_index(drop=True)

    main_summary = summarise_scores(main_score)
    coverage = metric_rows(hko, event_sweep, child, upper_tail, price_obs, decision, score, diagnostics)
    monthly = monthly_summary(upper_tail, score)
    integrity = integrity_checks(score, upper_tail)
    decision_ops = decision_rule_operational_summary(main_score)

    main_score.to_csv(OUTPUTS["main_scoring_panel"], index=False)
    main_summary.to_csv(OUTPUTS["main_score_summary"], index=False)
    coverage.to_csv(OUTPUTS["coverage_summary"], index=False)
    monthly.to_csv(OUTPUTS["monthly_summary"], index=False)
    integrity.to_csv(OUTPUTS["integrity_checks"], index=False)
    decision_ops.to_csv(OUTPUTS["decision_rule_summary"], index=False)

    make_figures(main_summary, main_score, monthly)

    report_text = build_report(coverage, main_summary, monthly, integrity, decision_ops)
    OUTPUTS["report"].write_text(report_text, encoding="utf-8")

    print("\n=== 18i outputs ===")
    for name, path in OUTPUTS.items():
        if path.exists():
            if path.suffix == ".csv":
                df = pd.read_csv(path)
                print(f"{name}: {df.shape} | {path.relative_to(ROOT)}")
            else:
                print(f"{name}: FOUND | {path.relative_to(ROOT)}")

    print("\n=== 18i figures ===")
    for name, path in FIGURE_PATHS.items():
        print(f"{name}: {'FOUND' if path.exists() else 'MISSING'} | {path.relative_to(ROOT)}")

    print("\n=== Main formally certified score summary ===")
    print(main_summary.to_string(index=False))

    print("\n=== Integrity checks ===")
    print(integrity.to_string(index=False))

    print("\n=== 18i report preview ===")
    print(report_text[:5000])


if __name__ == "__main__":
    main()
