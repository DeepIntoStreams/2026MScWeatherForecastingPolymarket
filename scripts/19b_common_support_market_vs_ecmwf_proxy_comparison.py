#!/usr/bin/env python3
"""
19b common-support market versus ECMWF proxy comparison.

Compares Polymarket probabilities from 18l with ECMWF proxy probabilities
from 19a on exactly common contract-date-decision rows. The ECMWF proxy is
only a deterministic single-run bridge, not a calibrated ensemble forecast.
"""
from __future__ import annotations

import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

EPS = 1e-6
DECISION_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]


def repo_root() -> Path:
    p = Path.cwd().resolve()
    for q in [p] + list(p.parents):
        if (q / ".git").exists() and (q / "data").exists():
            return q
    return Path(__file__).resolve().parents[1]


REPO = repo_root()
PROCESSED = REPO / "data" / "processed"
DOCS = REPO / "docs" / "research_outputs"
FIGS = REPO / "figures" / "19b_common_support_market_vs_ecmwf"
BUNDLES = REPO / "data" / "review_bundles"
for p in [PROCESSED, DOCS, FIGS, BUNDLES]:
    p.mkdir(parents=True, exist_ok=True)


def read_auto(name: str, required: bool = True) -> pd.DataFrame:
    for suffix in [".csv", ".csv.gz"]:
        p = PROCESSED / f"{name}{suffix}"
        if p.exists():
            print(f"Loaded {p.relative_to(REPO)}")
            return pd.read_csv(p, low_memory=False)
    if required:
        raise FileNotFoundError(f"Missing {name}.csv or {name}.csv.gz in data/processed")
    return pd.DataFrame()


def num(x):
    return pd.to_numeric(x, errors="coerce")


def token_clean(x):
    return x.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def logloss(y, p):
    y = num(y)
    p = num(p).clip(EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def brier(y, p):
    return (num(p) - num(y)) ** 2


def md_table(df: pd.DataFrame, n: int | None = None) -> str:
    if df is None or df.empty:
        return "_No rows._"
    d = df.copy()
    if n is not None:
        d = d.head(n)
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda z: "" if pd.isna(z) else f"{z:.6g}")
    return d.to_markdown(index=False)


def order_decision(df: pd.DataFrame) -> pd.DataFrame:
    if "decision_rule" in df.columns:
        df["decision_rule"] = pd.Categorical(df["decision_rule"], categories=DECISION_ORDER, ordered=True)
        df = df.sort_values("decision_rule")
        df["decision_rule"] = df["decision_rule"].astype(str)
    return df


def agg_binary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    g = df.groupby(group_cols, dropna=False, observed=False)
    out = g.agg(
        n=("Y_event_int", "size"),
        market_mean_brier=("brier_market_common", "mean"),
        ecmwf_mean_brier=("brier_ecmwf_common", "mean"),
        market_mean_log_score=("log_market_common", "mean"),
        ecmwf_mean_log_score=("log_ecmwf_common", "mean"),
        market_median_brier=("brier_market_common", "median"),
        ecmwf_median_brier=("brier_ecmwf_common", "median"),
        market_median_log_score=("log_market_common", "median"),
        ecmwf_median_log_score=("log_ecmwf_common", "median"),
        mean_p_market=("p_market", "mean"),
        mean_p_ecmwf_proxy=("p_ecmwf_proxy", "mean"),
        outcome_rate=("Y_event_int", "mean"),
        market_minus_ecmwf_brier=("delta_brier_market_minus_ecmwf", "mean"),
        market_minus_ecmwf_log_score=("delta_log_market_minus_ecmwf", "mean"),
    ).reset_index()
    out["brier_winner"] = np.where(out["market_mean_brier"] <= out["ecmwf_mean_brier"], "market", "ecmwf_proxy")
    out["log_score_winner"] = np.where(out["market_mean_log_score"] <= out["ecmwf_mean_log_score"], "market", "ecmwf_proxy")
    return order_decision(out)


def book_scores(g: pd.DataFrame, expected_n: int | None) -> dict:
    r = {"n_contracts_common": len(g), "expected_n_contracts": expected_n, "n_yes": float(num(g["Y_event_int"]).sum())}
    if expected_n is not None and len(g) != expected_n:
        r.update(book_ready=False, book_issue=f"common={len(g)} expected={expected_n}")
        return r
    if r["n_yes"] != 1:
        r.update(book_ready=False, book_issue=f"yes_count={r['n_yes']}")
        return r
    y = num(g["Y_event_int"]).to_numpy(float)
    pm = num(g["p_market"]).to_numpy(float)
    pe = num(g["p_ecmwf_proxy"]).to_numpy(float)
    sm, se = np.nansum(pm), np.nansum(pe)
    if sm <= 0 or se <= 0 or not np.isfinite(sm) or not np.isfinite(se):
        r.update(book_ready=False, book_issue="bad probability sum")
        return r
    im = pm / sm
    ie = pe / se
    w = int(np.where(y == 1)[0][0])
    r.update(
        book_ready=True,
        book_issue="",
        market_total_book_probability=sm,
        ecmwf_total_book_probability=se,
        market_abs_book_probability_error=abs(sm - 1),
        ecmwf_abs_book_probability_error=abs(se - 1),
        market_winning_probability_raw=pm[w],
        ecmwf_winning_probability_raw=pe[w],
        market_winning_probability_normalised=im[w],
        ecmwf_winning_probability_normalised=ie[w],
        market_normalised_categorical_log_score=-math.log(float(np.clip(im[w], EPS, 1 - EPS))),
        ecmwf_normalised_categorical_log_score=-math.log(float(np.clip(ie[w], EPS, 1 - EPS))),
        market_normalised_multiclass_brier=float(np.nansum((im - y) ** 2)),
        ecmwf_normalised_multiclass_brier=float(np.nansum((ie - y) ** 2)),
    )
    r["delta_norm_log_market_minus_ecmwf"] = r["market_normalised_categorical_log_score"] - r["ecmwf_normalised_categorical_log_score"]
    r["delta_norm_brier_market_minus_ecmwf"] = r["market_normalised_multiclass_brier"] - r["ecmwf_normalised_multiclass_brier"]
    return r


def make_figures(binary: pd.DataFrame, cats: pd.DataFrame, common: pd.DataFrame) -> list[Path]:
    import matplotlib.pyplot as plt
    made = []

    def bar(df, a, b, title, ylabel, fname):
        x = np.arange(len(df))
        width = 0.36
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(x - width / 2, df[a], width, label="Market")
        ax.bar(x + width / 2, df[b], width, label="ECMWF proxy")
        ax.set_xticks(x)
        ax.set_xticklabels(df["decision_rule"], rotation=25, ha="right")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.legend()
        fig.tight_layout()
        out = FIGS / fname
        fig.savefig(out, dpi=160)
        plt.close(fig)
        made.append(out)

    bar(binary, "market_mean_brier", "ecmwf_mean_brier", "Common-support binary Brier", "Mean Brier score", "19b_binary_brier_market_vs_ecmwf.png")
    bar(binary, "market_mean_log_score", "ecmwf_mean_log_score", "Common-support binary log score", "Mean log score", "19b_binary_log_market_vs_ecmwf.png")

    if not cats.empty:
        bar(cats, "market_normalised_categorical_log_score", "ecmwf_normalised_categorical_log_score", "Normalised categorical log score", "Mean log score", "19b_normalised_categorical_log_market_vs_ecmwf.png")
        bar(cats, "market_normalised_multiclass_brier", "ecmwf_normalised_multiclass_brier", "Normalised multiclass Brier", "Mean multiclass Brier", "19b_normalised_multiclass_brier_market_vs_ecmwf.png")

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(common["p_market"], common["p_ecmwf_proxy"], s=12, alpha=0.35)
    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1)
    ax.set_xlabel("Polymarket implied probability")
    ax.set_ylabel("ECMWF proxy probability")
    ax.set_title("Common-support probability scatter")
    fig.tight_layout()
    out = FIGS / "19b_probability_scatter_market_vs_ecmwf.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    made.append(out)

    order = [d for d in DECISION_ORDER if d in set(common["decision_rule"])]
    data = [common.loc[common["decision_rule"] == d, "delta_log_market_minus_ecmwf"].dropna() for d in order]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot(data, labels=order, showfliers=False)
    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_ylabel("Market log score minus ECMWF proxy log score")
    ax.set_title("Paired log-score difference by decision rule")
    fig.tight_layout()
    out = FIGS / "19b_paired_log_score_difference_boxplot.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    made.append(out)

    return made


def main() -> int:
    print(f"Repository root: {REPO}")
    market = read_auto("18l_full_hko_contract_event_market_scoring_panel")
    ecmwf = read_auto("19a_hko_ecmwf_contract_event_probability_panel")
    target = read_auto("18k_full_hko_contract_event_target_panel", required=False)

    for c in ["event_date", "decision_rule", "p_market"]:
        if c not in market.columns:
            raise ValueError(f"18l market panel missing {c}")
    for c in ["event_date", "decision_rule", "p_ecmwf_proxy"]:
        if c not in ecmwf.columns:
            raise ValueError(f"19a forecast panel missing {c}")

    market["event_date"] = pd.to_datetime(market["event_date"], errors="coerce").dt.date.astype(str)
    ecmwf["event_date"] = pd.to_datetime(ecmwf["event_date"], errors="coerce").dt.date.astype(str)
    market["decision_rule"] = market["decision_rule"].astype(str)
    ecmwf["decision_rule"] = ecmwf["decision_rule"].astype(str)

    if "selected_yes_token_id" in market.columns and "selected_yes_token_id" in ecmwf.columns:
        market["_join_token"] = token_clean(market["selected_yes_token_id"])
        ecmwf["_join_token"] = token_clean(ecmwf["selected_yes_token_id"])
        keys = ["event_date", "decision_rule", "_join_token"]
    else:
        keys = ["event_date", "decision_rule", "market_slug"]

    keep_m = [c for c in keys + ["market_slug", "group_item_title", "contract_event_type_v2", "event_set_v2", "selected_yes_token_id", "p_market", "Y_event_int", "hko_tmax_C", "price_staleness_hours"] if c in market.columns]
    keep_e = [c for c in keys + ["market_slug", "group_item_title", "contract_event_type_v2", "event_set_v2", "selected_yes_token_id", "p_ecmwf_proxy", "Y_event_int", "forecast_hko_daily_max_C", "target_hko_tmax_C", "temperature_error_C", "abs_temperature_error_C", "selected_run_init_utc", "decision_cutoff_utc"] if c in ecmwf.columns]
    ms = market[keep_m].drop_duplicates(keys)
    es = ecmwf[keep_e].drop_duplicates(keys)
    common = ms.merge(es, on=keys, how="inner", suffixes=("_market", "_ecmwf"), validate="one_to_one")

    for base in ["market_slug", "group_item_title", "contract_event_type_v2", "event_set_v2", "selected_yes_token_id"]:
        if base not in common.columns:
            if f"{base}_market" in common.columns:
                common[base] = common[f"{base}_market"]
            elif f"{base}_ecmwf" in common.columns:
                common[base] = common[f"{base}_ecmwf"]
    if "Y_event_int_market" in common.columns:
        common["Y_event_int"] = num(common["Y_event_int_market"])
        common["Y_mismatch"] = False
        if "Y_event_int_ecmwf" in common.columns:
            common["Y_mismatch"] = common["Y_event_int"] != num(common["Y_event_int_ecmwf"])
    elif "Y_event_int_ecmwf" in common.columns:
        common["Y_event_int"] = num(common["Y_event_int_ecmwf"])
        common["Y_mismatch"] = False
    elif "Y_event_int" in common.columns:
        common["Y_event_int"] = num(common["Y_event_int"])
        common["Y_mismatch"] = False
    else:
        raise ValueError("Cannot find Y_event_int after merge")

    common["p_market"] = num(common["p_market"])
    common["p_ecmwf_proxy"] = num(common["p_ecmwf_proxy"])
    common = common[common["p_market"].between(0, 1) & common["p_ecmwf_proxy"].between(0, 1) & common["Y_event_int"].isin([0, 1])].copy()
    common["brier_market_common"] = brier(common["Y_event_int"], common["p_market"])
    common["brier_ecmwf_common"] = brier(common["Y_event_int"], common["p_ecmwf_proxy"])
    common["log_market_common"] = logloss(common["Y_event_int"], common["p_market"])
    common["log_ecmwf_common"] = logloss(common["Y_event_int"], common["p_ecmwf_proxy"])
    common["delta_brier_market_minus_ecmwf"] = common["brier_market_common"] - common["brier_ecmwf_common"]
    common["delta_log_market_minus_ecmwf"] = common["log_market_common"] - common["log_ecmwf_common"]
    common = order_decision(common)

    common_path = PROCESSED / "19b_common_support_market_vs_ecmwf_panel.csv"
    common.to_csv(common_path, index=False)

    binary = agg_binary(common, ["decision_rule"])
    binary_path = PROCESSED / "19b_common_support_binary_score_summary.csv"
    binary.to_csv(binary_path, index=False)

    by_type = agg_binary(common, ["decision_rule", "contract_event_type_v2"]) if "contract_event_type_v2" in common.columns else pd.DataFrame()
    by_type_path = PROCESSED / "19b_common_support_binary_score_by_event_type.csv"
    by_type.to_csv(by_type_path, index=False)

    date_diff = common.groupby(["event_date", "decision_rule"], observed=False).agg(
        n=("Y_event_int", "size"),
        mean_delta_brier_market_minus_ecmwf=("delta_brier_market_minus_ecmwf", "mean"),
        mean_delta_log_market_minus_ecmwf=("delta_log_market_minus_ecmwf", "mean"),
        outcome_count=("Y_event_int", "sum"),
    ).reset_index()
    date_diff = order_decision(date_diff)
    date_diff_path = PROCESSED / "19b_common_support_score_differences_by_date.csv"
    date_diff.to_csv(date_diff_path, index=False)

    if not target.empty and "event_date" in target.columns:
        target["event_date"] = pd.to_datetime(target["event_date"], errors="coerce").dt.date.astype(str)
        expected = target.groupby("event_date").size().to_dict()
    else:
        expected = common.groupby("event_date").size().to_dict()

    cat_rows = []
    for (event_date, decision_rule), g in common.groupby(["event_date", "decision_rule"], dropna=False, observed=False):
        r = book_scores(g, int(expected.get(str(event_date))) if str(event_date) in expected else None)
        r["event_date"] = event_date
        r["decision_rule"] = decision_rule
        cat_rows.append(r)
    cat_panel = order_decision(pd.DataFrame(cat_rows))
    cat_panel_path = PROCESSED / "19b_common_support_categorical_book_score_panel.csv"
    cat_panel.to_csv(cat_panel_path, index=False)

    ready = cat_panel[cat_panel.get("book_ready", False) == True].copy() if not cat_panel.empty else pd.DataFrame()
    if not ready.empty:
        cats = ready.groupby("decision_rule", observed=False).agg(
            n_books=("book_ready", "size"),
            market_mean_total_book_probability=("market_total_book_probability", "mean"),
            ecmwf_mean_total_book_probability=("ecmwf_total_book_probability", "mean"),
            market_mean_abs_book_probability_error=("market_abs_book_probability_error", "mean"),
            ecmwf_mean_abs_book_probability_error=("ecmwf_abs_book_probability_error", "mean"),
            market_median_winning_probability_normalised=("market_winning_probability_normalised", "median"),
            ecmwf_median_winning_probability_normalised=("ecmwf_winning_probability_normalised", "median"),
            market_normalised_categorical_log_score=("market_normalised_categorical_log_score", "mean"),
            ecmwf_normalised_categorical_log_score=("ecmwf_normalised_categorical_log_score", "mean"),
            market_normalised_multiclass_brier=("market_normalised_multiclass_brier", "mean"),
            ecmwf_normalised_multiclass_brier=("ecmwf_normalised_multiclass_brier", "mean"),
            market_minus_ecmwf_normalised_log=("delta_norm_log_market_minus_ecmwf", "mean"),
            market_minus_ecmwf_normalised_brier=("delta_norm_brier_market_minus_ecmwf", "mean"),
        ).reset_index()
        cats["normalised_categorical_log_winner"] = np.where(cats["market_normalised_categorical_log_score"] <= cats["ecmwf_normalised_categorical_log_score"], "market", "ecmwf_proxy")
        cats["normalised_multiclass_brier_winner"] = np.where(cats["market_normalised_multiclass_brier"] <= cats["ecmwf_normalised_multiclass_brier"], "market", "ecmwf_proxy")
        cats = order_decision(cats)
    else:
        cats = pd.DataFrame()
    cats_path = PROCESSED / "19b_common_support_categorical_score_summary.csv"
    cats.to_csv(cats_path, index=False)

    ranking_rows = []
    for _, r in binary.iterrows():
        ranking_rows += [
            {"metric": "binary_mean_brier", "decision_rule": r["decision_rule"], "market_value": r["market_mean_brier"], "ecmwf_proxy_value": r["ecmwf_mean_brier"], "winner": r["brier_winner"], "winning_value": min(r["market_mean_brier"], r["ecmwf_mean_brier"]), "lower_better": True},
            {"metric": "binary_mean_log_score", "decision_rule": r["decision_rule"], "market_value": r["market_mean_log_score"], "ecmwf_proxy_value": r["ecmwf_mean_log_score"], "winner": r["log_score_winner"], "winning_value": min(r["market_mean_log_score"], r["ecmwf_mean_log_score"]), "lower_better": True},
        ]
    for _, r in cats.iterrows():
        ranking_rows += [
            {"metric": "normalised_categorical_log_score", "decision_rule": r["decision_rule"], "market_value": r["market_normalised_categorical_log_score"], "ecmwf_proxy_value": r["ecmwf_normalised_categorical_log_score"], "winner": r["normalised_categorical_log_winner"], "winning_value": min(r["market_normalised_categorical_log_score"], r["ecmwf_normalised_categorical_log_score"]), "lower_better": True},
            {"metric": "normalised_multiclass_brier", "decision_rule": r["decision_rule"], "market_value": r["market_normalised_multiclass_brier"], "ecmwf_proxy_value": r["ecmwf_normalised_multiclass_brier"], "winner": r["normalised_multiclass_brier_winner"], "winning_value": min(r["market_normalised_multiclass_brier"], r["ecmwf_normalised_multiclass_brier"]), "lower_better": True},
        ]
    rankings = pd.DataFrame(ranking_rows)
    if not rankings.empty:
        rankings["rank"] = rankings.groupby("metric")["winning_value"].rank(method="dense", ascending=True).astype(int)
        rankings = rankings.sort_values(["metric", "rank", "decision_rule"])
    rankings_path = PROCESSED / "19b_common_support_decision_rule_rankings.csv"
    rankings.to_csv(rankings_path, index=False)

    issues = []
    y_mis = int(common.get("Y_mismatch", pd.Series(dtype=bool)).sum())
    if y_mis:
        issues.append({"issue_type": "Y_event_mismatch", "detail": f"{y_mis} rows"})
    if not cat_panel.empty:
        for _, r in cat_panel[cat_panel.get("book_ready", False) != True].head(500).iterrows():
            issues.append({"issue_type": "categorical_book_not_ready", "event_date": r.get("event_date", ""), "decision_rule": r.get("decision_rule", ""), "detail": r.get("book_issue", ""), "n_contracts_common": r.get("n_contracts_common", ""), "expected_n_contracts": r.get("expected_n_contracts", ""), "n_yes": r.get("n_yes", "")})
    issues_df = pd.DataFrame(issues)
    issues_path = PROCESSED / "19b_common_support_issues.csv"
    issues_df.to_csv(issues_path, index=False)

    integrity = pd.DataFrame([
        {"check": "market_input_nonempty", "passed": len(market) > 0, "detail": f"rows={len(market)}"},
        {"check": "ecmwf_input_nonempty", "passed": len(ecmwf) > 0, "detail": f"rows={len(ecmwf)}"},
        {"check": "common_support_nonempty", "passed": len(common) > 0, "detail": f"rows={len(common)}"},
        {"check": "common_rows_have_probabilities", "passed": common[["p_market", "p_ecmwf_proxy"]].notna().all().all(), "detail": f"missing={int(common[['p_market','p_ecmwf_proxy']].isna().sum().sum())}"},
        {"check": "common_probabilities_in_unit_interval", "passed": bool(common["p_market"].between(0, 1).all() and common["p_ecmwf_proxy"].between(0, 1).all()), "detail": "checked both sources"},
        {"check": "common_rows_have_binary_outcome", "passed": bool(common["Y_event_int"].isin([0, 1]).all()), "detail": f"bad={int((~common['Y_event_int'].isin([0,1])).sum())}"},
        {"check": "market_ecmwf_outcomes_match", "passed": y_mis == 0, "detail": f"mismatches={y_mis}"},
        {"check": "binary_summary_nonempty", "passed": len(binary) > 0, "detail": f"rows={len(binary)}"},
        {"check": "categorical_panel_nonempty", "passed": len(cat_panel) > 0, "detail": f"rows={len(cat_panel)}"},
        {"check": "some_categorical_books_ready", "passed": int(cat_panel.get('book_ready', pd.Series(dtype=bool)).sum()) > 0 if not cat_panel.empty else False, "detail": f"ready={int(cat_panel.get('book_ready', pd.Series(dtype=bool)).sum()) if not cat_panel.empty else 0}"},
        {"check": "issue_table_written", "passed": True, "detail": f"issue rows={len(issues_df)}"},
    ])
    integrity_path = PROCESSED / "19b_common_support_integrity_checks.csv"
    integrity.to_csv(integrity_path, index=False)

    figs = make_figures(binary, cats, common)

    report_path = DOCS / "19b_common_support_market_vs_ecmwf_proxy_report.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    txt = [
        "# 19b common-support market versus ECMWF proxy comparison", "", f"Generated: `{now}`", "",
        "## Purpose", "", "This step compares Polymarket-implied probabilities against the temporary ECMWF single-run Gaussian probability proxy on exactly common contract-date-decision rows.", "",
        "## Methodological status", "", "The ECMWF proxy is a deterministic point-forecast bridge, not a calibrated ensemble or AIFS probability. It is suitable as a first forecast-side baseline and a pipeline test.", "",
        "## Main result", "", f"- Common contract-decision rows: `{len(common)}`", f"- Unique event dates: `{common['event_date'].nunique()}`", f"- Event-book categorical rows: `{len(cat_panel)}`", f"- Event-book categorical ready rows: `{int(cat_panel.get('book_ready', pd.Series(dtype=bool)).sum()) if not cat_panel.empty else 0}`", f"- Issue rows: `{len(issues_df)}`", "",
        "## Binary common-support score by decision rule", "", md_table(binary), "",
        "## Binary common-support score by decision rule and event type", "", md_table(by_type), "",
        "## Event-book categorical common-support score by decision rule", "", md_table(cats), "",
        "## Decision-rule rankings", "", md_table(rankings), "",
        "## Integrity checks", "", md_table(integrity), "",
        "## Interpretation", "", "A negative value in `market_minus_ecmwf_brier` or `market_minus_ecmwf_log_score` means the market has the lower score and therefore performs better on common support. If the market beats this ECMWF proxy, the correct interpretation is not that weather forecasts are uninformative; it means this uncalibrated deterministic-to-Gaussian bridge has not yet caught up with market prices. The next step should add local bias correction and calibration.", "",
        "## Issues requiring review", "", md_table(issues_df, 80), "",
        "## Figures", "",
    ]
    for f in figs:
        txt.append(f"- `{f.relative_to(REPO)}`")
    txt += ["", "## Output files", "", "- `data/processed/19b_common_support_market_vs_ecmwf_panel.csv`", "- `data/processed/19b_common_support_binary_score_summary.csv`", "- `data/processed/19b_common_support_binary_score_by_event_type.csv`", "- `data/processed/19b_common_support_score_differences_by_date.csv`", "- `data/processed/19b_common_support_categorical_book_score_panel.csv`", "- `data/processed/19b_common_support_categorical_score_summary.csv`", "- `data/processed/19b_common_support_decision_rule_rankings.csv`", "- `data/processed/19b_common_support_integrity_checks.csv`", "- `data/processed/19b_common_support_issues.csv`", "- `docs/research_outputs/19b_common_support_market_vs_ecmwf_proxy_report.md`", "- `data/review_bundles/19b_review_bundle.zip`", ""]
    report_path.write_text("\n".join(txt), encoding="utf-8")

    bundle = BUNDLES / "19b_review_bundle.zip"
    outputs = [common_path, binary_path, by_type_path, date_diff_path, cat_panel_path, cats_path, rankings_path, integrity_path, issues_path, report_path, *figs]
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in outputs:
            if p.exists():
                zf.write(p, arcname=str(p.relative_to(REPO)))

    print("\n19b complete")
    print(f"Common rows: {len(common)}")
    print(f"Ready categorical books: {int(cat_panel.get('book_ready', pd.Series(dtype=bool)).sum()) if not cat_panel.empty else 0}")
    print(f"Report: {report_path.relative_to(REPO)}")
    print(f"Review bundle: {bundle.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
