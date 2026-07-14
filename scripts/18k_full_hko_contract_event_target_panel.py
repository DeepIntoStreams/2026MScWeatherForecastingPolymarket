#!/usr/bin/env python3
"""
18k_full_hko_contract_event_target_panel.py

Builds the full Hong Kong HKO Daily Extract contract-event target panel from
18j v2. This joins the repaired admissible contract-event universe to official
HKO realised daily maximum-temperature observations and computes the realised
binary payoff Y_{d,E} for every certified HKO event contract.

This script is intentionally defensive:
- it locates the repository root whether run from repo root or notebooks/;
- it searches several possible HKO outcome files from the earlier pipeline;
- it treats 18j v2 event bounds as authoritative after the parsing fix;
- it validates that each date's event book forms a coherent partition and
  that exactly one contract resolves Yes per date.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
import math
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


def find_repo_root() -> Path:
    """Return repo root from current path, even if run inside notebooks/."""
    here = Path.cwd().resolve()
    candidates = [here] + list(here.parents)
    for p in candidates:
        if (p / "data").exists() and (p / "scripts").exists():
            return p
    # Fallback for first-time runs from notebooks/ before scripts exists.
    for p in candidates:
        if p.name == "2026MScWeatherForecastingPolymarket":
            return p
    return here


ROOT = find_repo_root()
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"
BUNDLE_DIR = ROOT / "data" / "review_bundles"

PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)
BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

IN_UNIVERSE = PROCESSED / "18j_v2_full_hko_contract_event_universe.csv"

HKO_CANDIDATES = [
    PROCESSED / "18f_hko_daily_extract_targets_20260301_20260531.csv",
    PROCESSED / "18f_hko_polymarket_floor_validation_panel_20260313_20260531.csv",
    PROCESSED / "18f_hko_upper_tail_threshold_contracts_20260313_20260531.csv",
    PROCESSED / "18h_hko_upper_tail_scoring_ready_market_panel_20260313_20260531.csv",
    PROCESSED / "18i_hko_main_scoring_panel_formally_certified.csv",
]

OUT_PANEL = PROCESSED / "18k_full_hko_contract_event_target_panel.csv"
OUT_HKO_USED = PROCESSED / "18k_hko_realised_outcomes_used.csv"
OUT_DATE_SUMMARY = PROCESSED / "18k_hko_contract_event_date_resolution_summary.csv"
OUT_EVENT_TYPE_SUMMARY = PROCESSED / "18k_hko_contract_event_type_target_summary.csv"
OUT_INTEGRITY = PROCESSED / "18k_hko_contract_event_integrity_checks.csv"
OUT_ISSUES = PROCESSED / "18k_hko_contract_event_target_issues.csv"
OUT_REPORT = REPORTS / "18k_full_hko_contract_event_target_panel_report.md"
OUT_BUNDLE = BUNDLE_DIR / "18k_review_bundle.zip"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False)


def normalise_date_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.strftime("%Y-%m-%d")


def coerce_float_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def first_existing_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def clean_text(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).strip()


def infer_hko_targets_from_file(path: Path) -> pd.DataFrame:
    """Read a prior pipeline file and extract event_date + hko_tmax_C."""
    df = read_csv(path)
    if df.empty:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source_file"])

    date_col = first_existing_col(df, [
        "event_date", "contract_date", "date", "local_date", "hko_date", "observation_date", "d"
    ])
    t_col = first_existing_col(df, [
        "hko_tmax_C", "T_HKO", "tmax_C", "daily_max_C", "absolute_daily_max_C",
        "Absolute Daily Max (deg. C)", "absolute_daily_max", "max_temp_C",
    ])

    if date_col is None or t_col is None:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source_file"])

    out = pd.DataFrame({
        "event_date": normalise_date_series(df[date_col]),
        "hko_tmax_C": coerce_float_series(df[t_col]),
        "hko_source_file": str(path.relative_to(ROOT)),
    })
    out = out.dropna(subset=["event_date", "hko_tmax_C"])
    out = out.drop_duplicates(["event_date", "hko_tmax_C", "hko_source_file"]).reset_index(drop=True)
    return out


def load_hko_targets() -> pd.DataFrame:
    frames = []
    for p in HKO_CANDIDATES:
        if p.exists():
            extracted = infer_hko_targets_from_file(p)
            if not extracted.empty:
                frames.append(extracted)
                print(f"Loaded HKO targets from {p.relative_to(ROOT)}: {extracted.shape}")
            else:
                print(f"Found but could not extract HKO targets from {p.relative_to(ROOT)}")
        else:
            print(f"HKO candidate missing: {p.relative_to(ROOT)}")

    if not frames:
        raise SystemExit(
            "No usable HKO realised outcome file found. Expected one of: "
            + ", ".join(str(p.relative_to(ROOT)) for p in HKO_CANDIDATES)
        )

    all_hko = pd.concat(frames, ignore_index=True)
    all_hko["event_date"] = normalise_date_series(all_hko["event_date"])
    all_hko["hko_tmax_C"] = pd.to_numeric(all_hko["hko_tmax_C"], errors="coerce")
    all_hko = all_hko.dropna(subset=["event_date", "hko_tmax_C"])

    # If the same date appears multiple times with same value, combine source file names.
    grouped = (
        all_hko.groupby("event_date", dropna=False)
        .agg(
            hko_tmax_C=("hko_tmax_C", "first"),
            hko_tmax_min_C=("hko_tmax_C", "min"),
            hko_tmax_max_C=("hko_tmax_C", "max"),
            n_source_rows=("hko_tmax_C", "size"),
            hko_source_files=("hko_source_file", lambda x: "; ".join(sorted(set(map(str, x)))))
        )
        .reset_index()
    )
    grouped["hko_value_conflict"] = (grouped["hko_tmax_min_C"] != grouped["hko_tmax_max_C"])
    return grouped


def compute_y_event(row: pd.Series) -> Tuple[float, str]:
    t = row.get("hko_tmax_C")
    typ = clean_text(row.get("contract_event_type_v2"))
    lb = row.get("event_lower_bound_C")
    ub = row.get("event_upper_bound_C")

    if pd.isna(t):
        return np.nan, "missing_hko_tmax"
    t = float(t)

    lb_num = pd.to_numeric(pd.Series([lb]), errors="coerce").iloc[0]
    ub_num = pd.to_numeric(pd.Series([ub]), errors="coerce").iloc[0]

    if typ == "upper_tail":
        if pd.isna(lb_num):
            return np.nan, "missing_lower_bound_for_upper_tail"
        return float(t >= float(lb_num)), f"T_HKO >= {float(lb_num):g}"

    if typ == "interior_bin":
        if pd.isna(lb_num) or pd.isna(ub_num):
            return np.nan, "missing_bound_for_interior_bin"
        return float((t >= float(lb_num)) and (t < float(ub_num))), f"{float(lb_num):g} <= T_HKO < {float(ub_num):g}"

    if typ == "lower_tail_endpoint":
        if pd.isna(ub_num):
            return np.nan, "missing_upper_bound_for_lower_endpoint"
        return float(t < float(ub_num)), f"T_HKO < {float(ub_num):g}"

    return np.nan, f"unsupported_contract_event_type:{typ}"


def finite_or_inf(x, default: float) -> float:
    v = pd.to_numeric(pd.Series([x]), errors="coerce").iloc[0]
    if pd.isna(v):
        return default
    return float(v)


def check_date_partition(g: pd.DataFrame) -> Dict[str, object]:
    """Check event sets form one contiguous partition of R for a date."""
    intervals = []
    for _, r in g.iterrows():
        typ = clean_text(r.get("contract_event_type_v2"))
        lb = finite_or_inf(r.get("event_lower_bound_C"), -math.inf if typ == "lower_tail_endpoint" else math.nan)
        ub = finite_or_inf(r.get("event_upper_bound_C"), math.inf if typ == "upper_tail" else math.nan)
        intervals.append((lb, ub, typ, clean_text(r.get("market_slug"))))

    intervals = sorted(intervals, key=lambda z: (z[0], z[1]))
    has_lower = any(math.isinf(lb) and lb < 0 for lb, _, _, _ in intervals)
    has_upper = any(math.isinf(ub) and ub > 0 for _, ub, _, _ in intervals)

    gaps = []
    overlaps = []
    for i in range(len(intervals) - 1):
        lb1, ub1, typ1, slug1 = intervals[i]
        lb2, ub2, typ2, slug2 = intervals[i + 1]
        if not (math.isfinite(ub1) and math.isfinite(lb2)):
            continue
        if abs(ub1 - lb2) > 1e-8:
            if ub1 < lb2:
                gaps.append(f"gap {ub1:g} to {lb2:g}")
            else:
                overlaps.append(f"overlap {lb2:g} to {ub1:g}")

    return {
        "has_lower_endpoint": has_lower,
        "has_upper_endpoint": has_upper,
        "n_intervals": len(intervals),
        "partition_has_gap": bool(gaps),
        "partition_has_overlap": bool(overlaps),
        "partition_gap_detail": "; ".join(gaps),
        "partition_overlap_detail": "; ".join(overlaps),
    }


def bool_to_pass(x: bool) -> str:
    return "PASS" if bool(x) else "FAIL"


def md_table(df: pd.DataFrame, cols: Optional[List[str]] = None, max_rows: int = 50) -> str:
    if df.empty:
        return "_No rows._"
    d = df.copy()
    if cols is not None:
        cols = [c for c in cols if c in d.columns]
        d = d[cols]
    d = d.head(max_rows).fillna("")
    cols = d.columns.tolist()
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = []
    for _, r in d.iterrows():
        rows.append("| " + " | ".join(str(r[c]).replace("\n", " ")[:160] for c in cols) + " |")
    return "\n".join([header, sep] + rows)


def make_bundle(paths: List[Path]) -> None:
    if OUT_BUNDLE.exists():
        OUT_BUNDLE.unlink()
    with zipfile.ZipFile(OUT_BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            if p.exists():
                z.write(p, arcname=str(p.relative_to(ROOT)))


def main() -> None:
    print(f"Repository root: {ROOT}")
    if not IN_UNIVERSE.exists():
        raise SystemExit(f"Missing input file: {IN_UNIVERSE}. Run 18j v2 first.")

    universe = read_csv(IN_UNIVERSE)
    print(f"18j v2 universe loaded: {universe.shape}")

    # Keep only admissible HKO rows from v2.
    if "admissible_hko_event_contract_v2" not in universe.columns:
        raise SystemExit("18j v2 universe lacks admissible_hko_event_contract_v2 column.")

    admissible = universe[universe["admissible_hko_event_contract_v2"].astype(str).str.lower().isin(["true", "1", "yes"])].copy()
    print(f"Admissible HKO contract-event rows: {admissible.shape}")

    required = ["event_date", "contract_event_type_v2", "event_lower_bound_C", "event_upper_bound_C", "event_set_v2", "market_slug", "selected_yes_token_id"]
    missing = [c for c in required if c not in admissible.columns]
    if missing:
        raise SystemExit(f"Missing required columns in 18j v2 universe: {missing}")

    admissible["event_date"] = normalise_date_series(admissible["event_date"])
    admissible["event_lower_bound_C"] = pd.to_numeric(admissible["event_lower_bound_C"], errors="coerce")
    admissible["event_upper_bound_C"] = pd.to_numeric(admissible["event_upper_bound_C"], errors="coerce")
    admissible["label_temperature_C"] = pd.to_numeric(admissible.get("label_temperature_C", np.nan), errors="coerce")

    hko = load_hko_targets()
    print(f"HKO realised target dates loaded: {hko.shape}")

    hko.to_csv(OUT_HKO_USED, index=False)

    panel = admissible.merge(hko, on="event_date", how="left", suffixes=("", "_hko"))
    panel["hko_tmax_C"] = pd.to_numeric(panel["hko_tmax_C"], errors="coerce")

    y = panel.apply(compute_y_event, axis=1)
    panel["Y_event"] = [a for a, _ in y]
    panel["realised_event_condition"] = [b for _, b in y]
    panel["Y_event_int"] = pd.to_numeric(panel["Y_event"], errors="coerce").astype("Int64")

    panel["target_panel_ready"] = (
        panel["hko_tmax_C"].notna()
        & panel["Y_event"].notna()
        & panel["selected_yes_token_id"].astype(str).str.len().gt(20)
    )

    # Date-level resolution and partition checks.
    date_rows = []
    for d, g in panel.groupby("event_date", dropna=False):
        part = check_date_partition(g)
        yes_count = int(pd.to_numeric(g["Y_event"], errors="coerce").fillna(0).sum())
        date_rows.append({
            "event_date": d,
            "n_contracts": len(g),
            "hko_tmax_C": pd.to_numeric(g["hko_tmax_C"], errors="coerce").dropna().iloc[0] if pd.to_numeric(g["hko_tmax_C"], errors="coerce").notna().any() else np.nan,
            "yes_count": yes_count,
            "exactly_one_yes": yes_count == 1,
            "target_rows_ready": int(g["target_panel_ready"].sum()),
            "n_lower_tail_endpoint": int((g["contract_event_type_v2"] == "lower_tail_endpoint").sum()),
            "n_interior_bin": int((g["contract_event_type_v2"] == "interior_bin").sum()),
            "n_upper_tail": int((g["contract_event_type_v2"] == "upper_tail").sum()),
            **part,
        })

    date_summary = pd.DataFrame(date_rows).sort_values("event_date").reset_index(drop=True)
    date_summary["date_book_valid"] = (
        date_summary["exactly_one_yes"]
        & date_summary["has_lower_endpoint"]
        & date_summary["has_upper_endpoint"]
        & ~date_summary["partition_has_gap"]
        & ~date_summary["partition_has_overlap"]
        & (date_summary["n_contracts"] >= 3)
    )

    event_type_summary = (
        panel.groupby("contract_event_type_v2", dropna=False)
        .agg(
            rows=("contract_event_type_v2", "size"),
            ready_rows=("target_panel_ready", "sum"),
            yes_rows=("Y_event", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            outcome_rate=("Y_event", lambda s: float(pd.to_numeric(s, errors="coerce").mean()) if pd.to_numeric(s, errors="coerce").notna().any() else np.nan),
            unique_dates=("event_date", "nunique"),
        )
        .reset_index()
        .sort_values(["ready_rows", "rows"], ascending=False)
    )

    issues = panel[
        (~panel["target_panel_ready"])
        | panel["hko_value_conflict"].fillna(False).astype(bool)
    ].copy()

    bad_dates = date_summary[~date_summary["date_book_valid"]].copy()
    if not bad_dates.empty:
        # Add all rows for bad dates to issue file.
        issues = pd.concat([issues, panel[panel["event_date"].isin(bad_dates["event_date"])].copy()], ignore_index=True)
        issues = issues.drop_duplicates(subset=["event_date", "market_slug", "selected_yes_token_id"], keep="first")

    checks = []
    checks.append({"check": "input_universe_nonempty", "passed": len(universe) > 0, "detail": f"input rows={len(universe)}"})
    checks.append({"check": "admissible_universe_nonempty", "passed": len(admissible) > 0, "detail": f"admissible rows={len(admissible)}"})
    checks.append({"check": "all_admissible_have_hko_value", "passed": panel["hko_tmax_C"].notna().all(), "detail": f"missing HKO rows={int(panel['hko_tmax_C'].isna().sum())}"})
    checks.append({"check": "all_admissible_have_binary_payoff", "passed": panel["Y_event"].notna().all() and set(pd.to_numeric(panel["Y_event"], errors="coerce").dropna().unique()).issubset({0.0, 1.0}), "detail": f"missing Y rows={int(panel['Y_event'].isna().sum())}"})
    checks.append({"check": "all_dates_exactly_one_yes", "passed": bool(date_summary["exactly_one_yes"].all()), "detail": f"bad dates={int((~date_summary['exactly_one_yes']).sum())}"})
    checks.append({"check": "all_dates_have_partition_endpoints", "passed": bool((date_summary["has_lower_endpoint"] & date_summary["has_upper_endpoint"]).all()), "detail": f"missing endpoint dates={int((~(date_summary['has_lower_endpoint'] & date_summary['has_upper_endpoint'])).sum())}"})
    checks.append({"check": "no_partition_gaps_or_overlaps", "passed": bool((~date_summary["partition_has_gap"] & ~date_summary["partition_has_overlap"]).all()), "detail": f"gap dates={int(date_summary['partition_has_gap'].sum())}; overlap dates={int(date_summary['partition_has_overlap'].sum())}"})
    checks.append({"check": "no_hko_value_conflicts", "passed": bool(~hko["hko_value_conflict"].any()), "detail": f"conflict dates={int(hko['hko_value_conflict'].sum())}"})
    checks.append({"check": "target_panel_ready_nonempty", "passed": bool(panel["target_panel_ready"].any()), "detail": f"ready rows={int(panel['target_panel_ready'].sum())}"})
    integrity = pd.DataFrame(checks)

    # Save outputs.
    panel.to_csv(OUT_PANEL, index=False)
    date_summary.to_csv(OUT_DATE_SUMMARY, index=False)
    event_type_summary.to_csv(OUT_EVENT_TYPE_SUMMARY, index=False)
    integrity.to_csv(OUT_INTEGRITY, index=False)
    issues.to_csv(OUT_ISSUES, index=False)

    # Report.
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report = []
    report.append("# 18k full HKO contract-event target panel\n")
    report.append(f"Generated: `{timestamp}`\n")
    report.append("## Purpose\n")
    report.append(
        "This step converts the repaired 18j v2 HKO contract-event universe into a realised target panel. It joins each certified HKO Daily Extract one-decimal contract to the official HKO daily maximum temperature and computes the realised binary payoff for upper-tail, interior-bin and lower-endpoint contracts.\n"
    )
    report.append("## Main result\n")
    report.append(f"- Input 18j v2 universe rows: `{len(universe)}`\n")
    report.append(f"- Admissible HKO event-contract rows: `{len(admissible)}`\n")
    report.append(f"- Target-panel rows: `{len(panel)}`\n")
    report.append(f"- Ready target-panel rows: `{int(panel['target_panel_ready'].sum())}`\n")
    report.append(f"- Unique event dates: `{panel['event_date'].nunique()}`\n")
    report.append(f"- Dates with exactly one Yes contract: `{int(date_summary['exactly_one_yes'].sum())}` / `{len(date_summary)}`\n")
    report.append(f"- Dates passing full event-book validity: `{int(date_summary['date_book_valid'].sum())}` / `{len(date_summary)}`\n")

    report.append("\n## Integrity checks\n")
    report.append(md_table(integrity, max_rows=20))

    report.append("\n\n## Event-type target summary\n")
    report.append(md_table(event_type_summary, max_rows=20))

    report.append("\n\n## Date-level resolution summary preview\n")
    report.append(md_table(date_summary, max_rows=40))

    report.append("\n\n## Target-panel preview\n")
    report.append(md_table(panel, cols=[
        "event_date", "market_slug", "group_item_title", "contract_event_type_v2",
        "event_set_v2", "event_condition_v2", "hko_tmax_C", "Y_event_int",
        "selected_yes_token_id",
    ], max_rows=50))

    if not issues.empty:
        report.append("\n\n## Issues requiring review\n")
        report.append(f"Issue rows: `{len(issues)}`\n")
        report.append(md_table(issues, cols=[
            "event_date", "market_slug", "group_item_title", "contract_event_type_v2",
            "event_set_v2", "hko_tmax_C", "Y_event", "realised_event_condition",
            "target_panel_ready", "hko_value_conflict",
        ], max_rows=50))
    else:
        report.append("\n\n## Issues requiring review\n")
        report.append("_No target-panel issues detected._\n")

    report.append("\n## Interpretation\n")
    if bool(integrity["passed"].all()):
        report.append(
            "The 18k target panel passes all automated checks. This supports using the full certified HKO Daily Extract one-decimal contract-event universe as the main Hong Kong empirical target panel for market scoring, forecast alignment, supervised postprocessing and trading simulation.\n"
        )
    else:
        report.append(
            "The 18k target panel was created, but at least one automated check failed. Inspect the issue file before using this panel for downstream scoring or modelling.\n"
        )

    report.append("\n## Output files\n")
    for p in [OUT_PANEL, OUT_HKO_USED, OUT_DATE_SUMMARY, OUT_EVENT_TYPE_SUMMARY, OUT_INTEGRITY, OUT_ISSUES, OUT_REPORT, OUT_BUNDLE]:
        report.append(f"- `{p.relative_to(ROOT)}`\n")

    OUT_REPORT.write_text("\n".join(report), encoding="utf-8")

    make_bundle([OUT_PANEL, OUT_HKO_USED, OUT_DATE_SUMMARY, OUT_EVENT_TYPE_SUMMARY, OUT_INTEGRITY, OUT_ISSUES, OUT_REPORT])

    # Console output.
    print("\n=== 18k outputs ===")
    for p in [OUT_PANEL, OUT_HKO_USED, OUT_DATE_SUMMARY, OUT_EVENT_TYPE_SUMMARY, OUT_INTEGRITY, OUT_ISSUES, OUT_REPORT, OUT_BUNDLE]:
        if p.exists():
            if p.suffix == ".csv":
                try:
                    df = pd.read_csv(p)
                    print(f"{p.relative_to(ROOT)}: {df.shape}")
                except Exception:
                    print(f"{p.relative_to(ROOT)}: FOUND")
            else:
                print(f"{p.relative_to(ROOT)}: FOUND")
        else:
            print(f"{p.relative_to(ROOT)}: MISSING")

    print("\n=== Integrity checks ===")
    print(integrity.to_string(index=False))

    print("\n=== Event-type target summary ===")
    print(event_type_summary.to_string(index=False))

    print("\n=== Date summary preview ===")
    print(date_summary.head(40).to_string(index=False))

    print("\n=== Target panel preview ===")
    cols = [c for c in [
        "event_date", "market_slug", "group_item_title", "contract_event_type_v2", "event_set_v2", "hko_tmax_C", "Y_event_int"
    ] if c in panel.columns]
    print(panel[cols].head(80).to_string(index=False))

    print(f"\nReview bundle: {OUT_BUNDLE}")


if __name__ == "__main__":
    main()
