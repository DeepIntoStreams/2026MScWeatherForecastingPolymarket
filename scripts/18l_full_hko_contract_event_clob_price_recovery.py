#!/usr/bin/env python3
"""
18l full HKO contract-event CLOB price recovery.

This script extends the earlier upper-tail price recovery to the full repaired
Hong Kong HKO contract-event book produced by 18k. It retrieves historical CLOB
prices for every admissible YES token in the 18k realised target panel, builds
strict no-lookahead decision snapshots, computes market-only Brier/log scores,
and writes a compact review bundle for inspection.

Run from the repository root, or from notebooks/. The script auto-detects the
root by searching for data/processed/18k_full_hko_contract_event_target_panel.csv.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import requests
except Exception as exc:  # pragma: no cover
    raise SystemExit("The requests package is required. Install it or use an environment that has requests.") from exc


SCRIPT_NAME = "18l_full_hko_contract_event_clob_price_recovery"
CLOB_URL = "https://clob.polymarket.com/prices-history"
HKT = "Asia/Hong_Kong"
EPS = 1e-12

DEFAULT_DECISION_RULES = {
    "24h_prior": -24,
    "12h_prior": -12,
    "6h_prior": -6,
    "event_day_open": 0,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UCL MSc dissertation research; no trading execution)",
    "Accept": "application/json,text/plain,*/*",
}


def find_repo_root() -> Path:
    """Find the repository root from cwd, parent dirs, or common Mac Desktop path."""
    candidates: List[Path] = []
    cwd = Path.cwd().resolve()
    candidates.extend([cwd] + list(cwd.parents))
    home = Path.home()
    candidates.extend([
        home / "Desktop" / "2026MScWeatherForecastingPolymarket",
        home / "2026MScWeatherForecastingPolymarket",
    ])
    marker = Path("data/processed/18k_full_hko_contract_event_target_panel.csv")
    for c in candidates:
        if (c / marker).exists():
            return c
    raise SystemExit(
        "Could not find repo root. Expected data/processed/18k_full_hko_contract_event_target_panel.csv. "
        "Run 18k FIX2 first, then rerun this script from the repository root."
    )


ROOT = find_repo_root()
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
RAW = DATA / "raw"
REPORTS = ROOT / "docs" / "research_outputs"
BUNDLES = DATA / "review_bundles"
RAW_PRICE_DIR = RAW / "polymarket_clob_price_history_18l"
LOG_DIR = ROOT / "logs"

for d in [PROCESSED, RAW_PRICE_DIR, REPORTS, BUNDLES, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def safe_name(s: Any, max_len: int = 120) -> str:
    text = "" if s is None else str(s)
    text = re.sub(r"[^A-Za-z0-9._=-]+", "_", text).strip("_")
    return text[:max_len] or "missing"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def as_bool(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if pd.isna(x):
        return False
    return str(x).strip().lower() in {"true", "1", "yes", "y"}


def as_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def normalise_probability(p: Any) -> float:
    """Convert CLOB price to a probability in [0,1] when possible."""
    v = as_float(p)
    if not np.isfinite(v):
        return float("nan")
    # Defensive: some APIs or CSV exports may use cents.
    if 1.0 < v <= 100.0:
        v = v / 100.0
    return float(v)


def parse_price_history(wrapper: Dict[str, Any]) -> pd.DataFrame:
    data = wrapper.get("response", wrapper)
    hist = None
    if isinstance(data, dict):
        for key in ["history", "prices", "data"]:
            if isinstance(data.get(key), list):
                hist = data.get(key)
                break
    elif isinstance(data, list):
        hist = data
    if not hist:
        return pd.DataFrame(columns=["price_timestamp_utc", "p_market"])

    rows: List[Dict[str, Any]] = []
    for item in hist:
        if not isinstance(item, dict):
            continue
        t = item.get("t", item.get("timestamp", item.get("time")))
        p = item.get("p", item.get("price", item.get("value")))
        if t is None or p is None:
            continue
        try:
            tf = float(t)
            if tf > 1e12:
                ts = pd.to_datetime(tf, unit="ms", utc=True)
            else:
                ts = pd.to_datetime(tf, unit="s", utc=True)
        except Exception:
            ts = pd.to_datetime(t, errors="coerce", utc=True)
        price = normalise_probability(p)
        if pd.notna(ts) and np.isfinite(price):
            rows.append({
                "price_timestamp_utc": ts,
                "p_market": price,
                "raw_price_value": p,
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["price_timestamp_utc", "p_market", "raw_price_value"])
    out = out.drop_duplicates(subset=["price_timestamp_utc", "p_market"]).sort_values("price_timestamp_utc")
    return out.reset_index(drop=True)


def load_target_panel() -> pd.DataFrame:
    path = PROCESSED / "18k_full_hko_contract_event_target_panel.csv"
    if not path.exists():
        raise SystemExit(f"Missing input: {path.relative_to(ROOT)}. Run 18k FIX2 first.")
    df = pd.read_csv(path, dtype=str, low_memory=False)
    print(f"Loaded 18k target panel: {df.shape}")

    # Defensive fix if an older 18k CSV has populated hko_tmax_C_hko but blank hko_tmax_C.
    if "hko_tmax_C" not in df.columns:
        df["hko_tmax_C"] = np.nan
    if "hko_tmax_C_hko" in df.columns:
        hko_primary = pd.to_numeric(df["hko_tmax_C"], errors="coerce")
        hko_backup = pd.to_numeric(df["hko_tmax_C_hko"], errors="coerce")
        df["hko_tmax_C"] = hko_primary.where(hko_primary.notna(), hko_backup)
    else:
        df["hko_tmax_C"] = pd.to_numeric(df["hko_tmax_C"], errors="coerce")

    for col in ["event_lower_bound_C", "event_upper_bound_C", "label_temperature_C"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Compute realised payoff if not already present or if missing.
    if "Y_event_int" not in df.columns:
        df["Y_event_int"] = np.nan
    y_existing = pd.to_numeric(df["Y_event_int"], errors="coerce")
    if y_existing.isna().any():
        y_calc = compute_event_payoff(df)
        df["Y_event_int"] = y_existing.where(y_existing.notna(), y_calc)
    df["Y_event_int"] = pd.to_numeric(df["Y_event_int"], errors="coerce")

    if "target_panel_ready" not in df.columns:
        df["target_panel_ready"] = False
    ready = df["hko_tmax_C"].notna() & df["Y_event_int"].isin([0, 1])
    # Keep original if it is stricter, but do not let string blanks block fixed values.
    df["target_panel_ready_18l"] = ready

    token_col = "selected_yes_token_id"
    if token_col not in df.columns:
        raise SystemExit("Input panel lacks selected_yes_token_id, so CLOB recovery cannot proceed.")
    df[token_col] = df[token_col].astype(str).str.strip()
    df.loc[df[token_col].isin(["", "nan", "None", "<NA>"]), token_col] = np.nan

    admissible = df[df["target_panel_ready_18l"] & df[token_col].notna()].copy()
    if admissible.empty:
        raise SystemExit(
            "No target-panel-ready rows with YES tokens. Inspect 18k output before CLOB recovery."
        )
    print(f"18l admissible target rows with YES token: {len(admissible)}")
    return admissible.reset_index(drop=True)


def compute_event_payoff(df: pd.DataFrame) -> pd.Series:
    t = pd.to_numeric(df.get("hko_tmax_C"), errors="coerce")
    lb = pd.to_numeric(df.get("event_lower_bound_C"), errors="coerce") if "event_lower_bound_C" in df else pd.Series(np.nan, index=df.index)
    ub = pd.to_numeric(df.get("event_upper_bound_C"), errors="coerce") if "event_upper_bound_C" in df else pd.Series(np.nan, index=df.index)
    typ = df.get("contract_event_type_v2", pd.Series("", index=df.index)).astype(str)

    y = pd.Series(np.nan, index=df.index, dtype="float64")
    lower_mask = typ.eq("lower_tail_endpoint") & t.notna() & ub.notna()
    interior_mask = typ.eq("interior_bin") & t.notna() & lb.notna() & ub.notna()
    upper_mask = typ.eq("upper_tail") & t.notna() & lb.notna()

    y.loc[lower_mask] = (t.loc[lower_mask] < ub.loc[lower_mask]).astype(int)
    y.loc[interior_mask] = ((t.loc[interior_mask] >= lb.loc[interior_mask]) & (t.loc[interior_mask] < ub.loc[interior_mask])).astype(int)
    y.loc[upper_mask] = (t.loc[upper_mask] >= lb.loc[upper_mask]).astype(int)
    return y


def decision_cutoffs_for_date(event_date: str, rules: Dict[str, int]) -> Dict[str, pd.Timestamp]:
    d = pd.to_datetime(event_date).date()
    event_open_hkt = pd.Timestamp(d).tz_localize(HKT)
    out: Dict[str, pd.Timestamp] = {}
    for rule, offset_hours in rules.items():
        out[rule] = (event_open_hkt + pd.Timedelta(hours=offset_hours)).tz_convert("UTC")
    return out


def fetch_clob_history(
    token_id: str,
    event_date: str,
    market_slug: str,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
    force: bool,
    request_timeout: int,
    sleep_seconds: float,
) -> Tuple[Dict[str, Any], Path, Dict[str, Any]]:
    token_id = str(token_id)
    start_ts = int(start_utc.timestamp())
    end_ts = int(end_utc.timestamp())
    cache_name = f"{safe_name(event_date)}__{safe_name(market_slug, 80)}__{token_id[:18]}__{start_ts}_{end_ts}.json"
    raw_path = RAW_PRICE_DIR / cache_name

    if raw_path.exists() and raw_path.stat().st_size > 0 and not force:
        try:
            wrapper = json.loads(raw_path.read_text(encoding="utf-8"))
            diag = {
                "token_id": token_id,
                "event_date": event_date,
                "market_slug": market_slug,
                "raw_price_json_path": str(raw_path.relative_to(ROOT)),
                "fetch_source": "cache",
                "status_code": wrapper.get("status_code", wrapper.get("last", {}).get("status_code")),
                "attempt_label": wrapper.get("attempt_label"),
                "history_points": len(parse_price_history(wrapper)),
                "error": wrapper.get("error", ""),
            }
            return wrapper, raw_path, diag
        except Exception:
            pass

    attempts: List[Tuple[str, Dict[str, Any]]] = [
        ("window_7d_fidelity_60", {"market": token_id, "startTs": start_ts, "endTs": end_ts, "fidelity": 60}),
        ("window_7d_fidelity_15", {"market": token_id, "startTs": start_ts, "endTs": end_ts, "fidelity": 15}),
        ("window_7d_fidelity_5", {"market": token_id, "startTs": start_ts, "endTs": end_ts, "fidelity": 5}),
        ("fallback_interval_1w", {"market": token_id, "interval": "1w", "fidelity": 60}),
    ]

    last: Dict[str, Any] = {}
    for label, params in attempts:
        try:
            r = requests.get(CLOB_URL, params=params, timeout=request_timeout, headers=HEADERS)
            text = (r.text or "")[:4000]
            last = {"attempt_label": label, "status_code": r.status_code, "url": r.url, "text": text}
            if r.status_code == 200:
                try:
                    response = r.json()
                except Exception:
                    response = {"raw_text": text}
                wrapper = {
                    "request_url": r.url,
                    "params": params,
                    "attempt_label": label,
                    "status_code": r.status_code,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "response": response,
                }
                write_json(raw_path, wrapper)
                hist = parse_price_history(wrapper)
                diag = {
                    "token_id": token_id,
                    "event_date": event_date,
                    "market_slug": market_slug,
                    "raw_price_json_path": str(raw_path.relative_to(ROOT)),
                    "fetch_source": "api",
                    "status_code": r.status_code,
                    "attempt_label": label,
                    "history_points": len(hist),
                    "error": "",
                }
                time.sleep(sleep_seconds)
                return wrapper, raw_path, diag
        except Exception as exc:
            last = {"attempt_label": label, "error": str(exc)}
        time.sleep(sleep_seconds)

    wrapper = {
        "error": "price_history_fetch_failed",
        "last": last,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(raw_path, wrapper)
    diag = {
        "token_id": token_id,
        "event_date": event_date,
        "market_slug": market_slug,
        "raw_price_json_path": str(raw_path.relative_to(ROOT)),
        "fetch_source": "api_failed",
        "status_code": last.get("status_code"),
        "attempt_label": last.get("attempt_label"),
        "history_points": 0,
        "error": last.get("error", last.get("text", "price_history_fetch_failed"))[:1000],
    }
    return wrapper, raw_path, diag


def build_price_history_panel(target: pd.DataFrame, args: argparse.Namespace) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows: List[pd.DataFrame] = []
    diagnostics: List[Dict[str, Any]] = []

    contracts = target.drop_duplicates(subset=["event_date", "market_slug", "selected_yes_token_id"]).copy()
    if args.max_contracts is not None and args.max_contracts > 0:
        contracts = contracts.head(args.max_contracts).copy()
    print(f"CLOB contracts to retrieve: {len(contracts)}")

    for i, row in contracts.iterrows():
        event_date = str(row["event_date"])
        market_slug = str(row.get("market_slug", ""))
        token_id = str(row["selected_yes_token_id"])
        cutoffs = decision_cutoffs_for_date(event_date, DEFAULT_DECISION_RULES)
        end_utc = max(cutoffs.values())
        start_utc = end_utc - pd.Timedelta(hours=args.lookback_hours)

        wrapper, raw_path, diag = fetch_clob_history(
            token_id=token_id,
            event_date=event_date,
            market_slug=market_slug,
            start_utc=start_utc,
            end_utc=end_utc,
            force=args.force_refetch,
            request_timeout=args.request_timeout,
            sleep_seconds=args.sleep_seconds,
        )
        diagnostics.append(diag)
        hist = parse_price_history(wrapper)
        if not hist.empty:
            hist["event_date"] = row.get("event_date")
            hist["market_slug"] = row.get("market_slug")
            hist["market_question"] = row.get("market_question")
            hist["group_item_title"] = row.get("group_item_title")
            hist["contract_event_type_v2"] = row.get("contract_event_type_v2")
            hist["event_set_v2"] = row.get("event_set_v2")
            hist["event_lower_bound_C"] = row.get("event_lower_bound_C")
            hist["event_upper_bound_C"] = row.get("event_upper_bound_C")
            hist["selected_yes_token_id"] = token_id
            hist["hko_tmax_C"] = row.get("hko_tmax_C")
            hist["Y_event_int"] = row.get("Y_event_int")
            hist["raw_price_json_path"] = str(raw_path.relative_to(ROOT))
            hist["price_timestamp_hkt"] = pd.to_datetime(hist["price_timestamp_utc"], utc=True).dt.tz_convert(HKT)
            rows.append(hist)

        if (len(diagnostics) % 25) == 0 or len(diagnostics) == len(contracts):
            recovered = sum(int(d.get("history_points", 0) or 0) > 0 for d in diagnostics)
            print(f"  retrieved {len(diagnostics)}/{len(contracts)} contracts; non-empty histories={recovered}")

    price = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not price.empty:
        price["price_timestamp_utc"] = pd.to_datetime(price["price_timestamp_utc"], utc=True)
        price = price.drop_duplicates(subset=["selected_yes_token_id", "price_timestamp_utc", "p_market"]).sort_values(
            ["event_date", "market_slug", "price_timestamp_utc"]
        ).reset_index(drop=True)
    diag_df = pd.DataFrame(diagnostics)
    return price, diag_df


def build_decision_panel(target: pd.DataFrame, price: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    if price.empty:
        for _, row in target.iterrows():
            for rule, cutoff in decision_cutoffs_for_date(str(row["event_date"]), DEFAULT_DECISION_RULES).items():
                missing.append({
                    "issue_type": "missing_decision_price",
                    "event_date": row.get("event_date"),
                    "market_slug": row.get("market_slug"),
                    "group_item_title": row.get("group_item_title"),
                    "selected_yes_token_id": row.get("selected_yes_token_id"),
                    "decision_rule": rule,
                    "decision_cutoff_utc": cutoff,
                    "detail": "No price history recovered for this token/window.",
                })
        return pd.DataFrame(rows), pd.DataFrame(missing)

    price = price.copy()
    price["price_timestamp_utc"] = pd.to_datetime(price["price_timestamp_utc"], utc=True)

    price_groups = {
        str(k): g.sort_values("price_timestamp_utc").copy()
        for k, g in price.groupby("selected_yes_token_id", dropna=False)
    }

    for _, row in target.iterrows():
        token = str(row["selected_yes_token_id"])
        g = price_groups.get(token)
        cutoffs = decision_cutoffs_for_date(str(row["event_date"]), DEFAULT_DECISION_RULES)
        for rule, cutoff in cutoffs.items():
            selected = None
            if g is not None and not g.empty:
                gg = g[g["price_timestamp_utc"] <= cutoff]
                if not gg.empty:
                    selected = gg.iloc[-1]
            if selected is None:
                missing.append({
                    "issue_type": "missing_decision_price",
                    "event_date": row.get("event_date"),
                    "market_slug": row.get("market_slug"),
                    "group_item_title": row.get("group_item_title"),
                    "selected_yes_token_id": token,
                    "decision_rule": rule,
                    "decision_cutoff_utc": cutoff,
                    "detail": "No price point at or before the decision cutoff within the recovered history window.",
                })
                continue
            staleness_hours = (cutoff - selected["price_timestamp_utc"]).total_seconds() / 3600.0
            rec = row.to_dict()
            rec.update({
                "decision_rule": rule,
                "decision_cutoff_utc": cutoff,
                "decision_cutoff_hkt": cutoff.tz_convert(HKT),
                "decision_price_timestamp_utc": selected["price_timestamp_utc"],
                "decision_price_timestamp_hkt": selected["price_timestamp_utc"].tz_convert(HKT),
                "price_staleness_hours": staleness_hours,
                "p_market": normalise_probability(selected["p_market"]),
                "raw_price_value": selected.get("raw_price_value"),
                "raw_price_json_path": selected.get("raw_price_json_path"),
            })
            rows.append(rec)

    decision = pd.DataFrame(rows)
    issues = pd.DataFrame(missing)
    return decision, issues


def score_decision_panel(decision: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if decision.empty:
        empty_summary = pd.DataFrame(columns=["decision_rule", "contract_event_type_v2", "n", "mean_brier", "mean_log_score"])
        return decision.copy(), empty_summary, pd.DataFrame()

    out = decision.copy()
    out["p_market"] = pd.to_numeric(out["p_market"], errors="coerce")
    out["Y_event_int"] = pd.to_numeric(out["Y_event_int"], errors="coerce")
    out = out.dropna(subset=["p_market", "Y_event_int"]).copy()
    out["p_market"] = out["p_market"].clip(0.0, 1.0)
    out["p_clipped"] = out["p_market"].clip(EPS, 1 - EPS)
    out["brier_market"] = (out["p_market"] - out["Y_event_int"]) ** 2
    out["log_score_market"] = -(
        out["Y_event_int"] * np.log(out["p_clipped"]) +
        (1 - out["Y_event_int"]) * np.log(1 - out["p_clipped"])
    )
    out["market_prob_times_outcome"] = out["p_market"] * out["Y_event_int"]

    summary = out.groupby(["decision_rule", "contract_event_type_v2"], dropna=False).agg(
        n=("brier_market", "size"),
        mean_brier=("brier_market", "mean"),
        mean_log_score=("log_score_market", "mean"),
        median_staleness_hours=("price_staleness_hours", "median"),
        mean_p_market=("p_market", "mean"),
        outcome_rate=("Y_event_int", "mean"),
    ).reset_index()

    all_summary = out.groupby(["decision_rule"], dropna=False).agg(
        n=("brier_market", "size"),
        mean_brier=("brier_market", "mean"),
        mean_log_score=("log_score_market", "mean"),
        median_staleness_hours=("price_staleness_hours", "median"),
        mean_p_market=("p_market", "mean"),
        outcome_rate=("Y_event_int", "mean"),
    ).reset_index()
    all_summary["contract_event_type_v2"] = "ALL"
    summary = pd.concat([all_summary[summary.columns], summary], ignore_index=True)

    book = out.groupby(["event_date", "decision_rule"], dropna=False).agg(
        n_price_snapshots=("p_market", "size"),
        n_yes_contracts=("Y_event_int", "sum"),
        total_book_market_probability=("p_market", "sum"),
        winning_contract_market_probability=("market_prob_times_outcome", "sum"),
        mean_price_staleness_hours=("price_staleness_hours", "mean"),
        max_price_staleness_hours=("price_staleness_hours", "max"),
    ).reset_index()

    # Add total contracts per date/rule from scoring rows; target-panel completeness is handled in report/integrity.
    book["book_probability_error_vs_one"] = book["total_book_market_probability"] - 1.0
    book["exactly_one_yes_in_priced_book"] = book["n_yes_contracts"].eq(1)
    return out, summary, book


def build_integrity_checks(target: pd.DataFrame, price: pd.DataFrame, decision: pd.DataFrame, scoring: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    checks: List[Dict[str, Any]] = []
    def add(check: str, passed: bool, detail: str) -> None:
        checks.append({"check": check, "passed": bool(passed), "detail": detail})

    add("target_panel_nonempty", len(target) > 0, f"target rows={len(target)}")
    add("target_rows_have_binary_payoff", target["Y_event_int"].isin([0, 1]).all(), f"bad rows={(~target['Y_event_int'].isin([0,1])).sum()}")
    add("target_rows_have_yes_tokens", target["selected_yes_token_id"].notna().all(), f"missing tokens={target['selected_yes_token_id'].isna().sum()}")
    add("price_history_nonempty", len(price) > 0, f"price rows={len(price)}")
    add("decision_panel_nonempty", len(decision) > 0, f"decision rows={len(decision)}")
    add("scoring_panel_nonempty", len(scoring) > 0, f"scoring rows={len(scoring)}")
    if len(decision):
        cutoff = pd.to_datetime(decision["decision_cutoff_utc"], utc=True)
        ts = pd.to_datetime(decision["decision_price_timestamp_utc"], utc=True)
        no_lookahead = (ts <= cutoff).all()
        add("no_lookahead_decision_timestamps", no_lookahead, f"violations={(ts > cutoff).sum()}")
        p = pd.to_numeric(decision["p_market"], errors="coerce")
        add("probabilities_in_unit_interval", p.between(0, 1).all(), f"bad probabilities={(~p.between(0,1)).sum()}")
        stale = pd.to_numeric(decision["price_staleness_hours"], errors="coerce")
        add("non_negative_staleness", (stale >= -1e-9).all(), f"negative staleness={(stale < -1e-9).sum()}")
    else:
        add("no_lookahead_decision_timestamps", False, "decision panel empty")
        add("probabilities_in_unit_interval", False, "decision panel empty")
        add("non_negative_staleness", False, "decision panel empty")
    add("missing_price_issue_table_written", issues is not None, f"issue rows={len(issues)}")
    return pd.DataFrame(checks)


def md_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df is None or df.empty:
        return "_No rows._"
    tmp = df.head(max_rows).copy()
    # Convert timestamps and nullable types to strings for stable markdown rendering.
    for c in tmp.columns:
        if pd.api.types.is_datetime64_any_dtype(tmp[c]) or str(tmp[c].dtype).startswith("datetime"):
            tmp[c] = tmp[c].astype(str)
    return tmp.to_markdown(index=False)


def build_report(
    target: pd.DataFrame,
    price: pd.DataFrame,
    diagnostics: pd.DataFrame,
    decision: pd.DataFrame,
    scoring: pd.DataFrame,
    score_summary: pd.DataFrame,
    book_summary: pd.DataFrame,
    integrity: pd.DataFrame,
    issues: pd.DataFrame,
) -> str:
    lines: List[str] = []
    lines.append("# 18l full HKO contract-event CLOB price recovery\n")
    lines.append(f"Generated: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n")
    lines.append("## Purpose\n")
    lines.append(
        "This step extends the previous upper-tail CLOB price recovery to the full repaired Hong Kong HKO contract-event book. "
        "It uses the 18k realised target panel, retrieves historical prices for each certified YES token, constructs no-lookahead decision snapshots, and computes market-only Brier and log scores.\n"
    )
    lines.append("## Main result\n")
    lines.append(f"- Input target rows: `{len(target)}`\n")
    lines.append(f"- Unique event dates: `{target['event_date'].nunique() if 'event_date' in target else 0}`\n")
    lines.append(f"- Unique YES tokens: `{target['selected_yes_token_id'].nunique() if 'selected_yes_token_id' in target else 0}`\n")
    lines.append(f"- Price-history observation rows: `{len(price)}`\n")
    lines.append(f"- No-lookahead decision rows: `{len(decision)}`\n")
    lines.append(f"- Scoring-ready rows: `{len(scoring)}`\n")
    lines.append(f"- Missing decision-price issue rows: `{len(issues)}`\n")

    if len(diagnostics):
        lines.append("\n## CLOB recovery diagnostics\n")
        diag_summary = diagnostics.copy()
        if "history_points" in diag_summary:
            diag_summary["has_history"] = pd.to_numeric(diag_summary["history_points"], errors="coerce").fillna(0).gt(0)
        cols = [c for c in ["fetch_source", "status_code", "attempt_label", "has_history"] if c in diag_summary.columns]
        if cols:
            grouped = diag_summary.groupby(cols, dropna=False).size().reset_index(name="contracts")
            lines.append(md_table(grouped, 50))

    lines.append("\n## Integrity checks\n")
    lines.append(md_table(integrity, 50))

    lines.append("\n## Market-only score summary\n")
    lines.append(md_table(score_summary, 80))

    lines.append("\n## Event-book snapshot summary preview\n")
    cols = [c for c in [
        "event_date", "decision_rule", "n_price_snapshots", "n_yes_contracts", "total_book_market_probability",
        "winning_contract_market_probability", "book_probability_error_vs_one", "max_price_staleness_hours"
    ] if c in book_summary.columns]
    lines.append(md_table(book_summary[cols] if cols else book_summary, 40))

    lines.append("\n## Decision-panel preview\n")
    cols = [c for c in [
        "event_date", "market_slug", "group_item_title", "contract_event_type_v2", "decision_rule",
        "p_market", "Y_event_int", "brier_market", "log_score_market", "price_staleness_hours"
    ] if c in scoring.columns]
    lines.append(md_table(scoring[cols] if cols else scoring, 40))

    lines.append("\n## Issues requiring review\n")
    lines.append(f"Issue rows: `{len(issues)}`\n")
    lines.append(md_table(issues, 40))

    lines.append("\n## Interpretation\n")
    passed_all = len(integrity) and integrity["passed"].astype(bool).all()
    if passed_all:
        lines.append(
            "The full HKO contract-event price recovery passed all automated checks. The scoring panel may be used as the market-only baseline for the full Hong Kong event-book analysis."
        )
    elif len(scoring):
        lines.append(
            "The step produced a non-empty no-lookahead scoring panel, but at least one automated check failed or some decision-price snapshots are missing. Use the scoring rows with the reported coverage limitations and inspect the issue table before downstream modelling."
        )
    else:
        lines.append(
            "The step did not recover scoreable decision-price rows. The target panel remains valid, but price-history recovery must be repaired before market scoring or trading simulation."
        )

    lines.append("\n## Output files\n")
    for p in output_paths():
        lines.append(f"- `{p.relative_to(ROOT)}`\n")
    return "\n".join(lines)


def output_paths() -> List[Path]:
    return [
        PROCESSED / "18l_full_hko_contract_event_price_history_panel.csv",
        PROCESSED / "18l_full_hko_contract_event_no_lookahead_decision_panel.csv",
        PROCESSED / "18l_full_hko_contract_event_market_scoring_panel.csv",
        PROCESSED / "18l_full_hko_contract_event_market_score_summary.csv",
        PROCESSED / "18l_full_hko_contract_event_book_snapshot_summary.csv",
        PROCESSED / "18l_clob_recovery_diagnostics.csv",
        PROCESSED / "18l_clob_recovery_integrity_checks.csv",
        PROCESSED / "18l_clob_recovery_issues.csv",
        REPORTS / "18l_full_hko_contract_event_clob_price_recovery_report.md",
        BUNDLES / "18l_review_bundle.zip",
    ]


def write_bundle(paths: List[Path], bundle_path: Path) -> None:
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if p.exists() and p != bundle_path:
                zf.write(p, arcname=str(p.relative_to(ROOT)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover full HKO contract-event CLOB prices and no-lookahead scoring snapshots.")
    parser.add_argument("--lookback-hours", type=int, default=168, help="Lookback window ending at event-day open, in hours. Default: 168 (7 days).")
    parser.add_argument("--sleep-seconds", type=float, default=0.15, help="Pause between API calls. Default: 0.15 seconds.")
    parser.add_argument("--request-timeout", type=int, default=20, help="HTTP request timeout in seconds. Default: 20.")
    parser.add_argument("--force-refetch", action="store_true", help="Ignore cached raw CLOB JSON files and refetch.")
    parser.add_argument("--max-contracts", type=int, default=None, help="Optional small test limit. Omit for the full 803-row panel.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Repository root:", ROOT)
    print("Output raw price cache:", RAW_PRICE_DIR.relative_to(ROOT))
    print("Lookback hours:", args.lookback_hours)

    target = load_target_panel()
    price, diagnostics = build_price_history_panel(target, args)
    decision, missing_issues = build_decision_panel(target, price)
    scoring, score_summary, book_summary = score_decision_panel(decision)

    # Additional issue rows for explicit violations.
    violation_rows: List[pd.DataFrame] = []
    if len(decision):
        ts = pd.to_datetime(decision["decision_price_timestamp_utc"], utc=True)
        cutoff = pd.to_datetime(decision["decision_cutoff_utc"], utc=True)
        bad = decision[ts > cutoff].copy()
        if len(bad):
            bad["issue_type"] = "lookahead_violation"
            bad["detail"] = "Decision price timestamp is after cutoff."
            violation_rows.append(bad[["issue_type", "event_date", "market_slug", "group_item_title", "selected_yes_token_id", "decision_rule", "decision_cutoff_utc", "detail"]])
        p = pd.to_numeric(decision["p_market"], errors="coerce")
        badp = decision[~p.between(0, 1)].copy()
        if len(badp):
            badp["issue_type"] = "invalid_probability"
            badp["detail"] = "Market price could not be interpreted as a probability in [0,1]."
            violation_rows.append(badp[["issue_type", "event_date", "market_slug", "group_item_title", "selected_yes_token_id", "decision_rule", "decision_cutoff_utc", "detail"]])
    issues = pd.concat([missing_issues] + violation_rows, ignore_index=True) if violation_rows or len(missing_issues) else pd.DataFrame(columns=[
        "issue_type", "event_date", "market_slug", "group_item_title", "selected_yes_token_id", "decision_rule", "decision_cutoff_utc", "detail"
    ])

    integrity = build_integrity_checks(target, price, decision, scoring, issues)

    price_path = PROCESSED / "18l_full_hko_contract_event_price_history_panel.csv"
    decision_path = PROCESSED / "18l_full_hko_contract_event_no_lookahead_decision_panel.csv"
    scoring_path = PROCESSED / "18l_full_hko_contract_event_market_scoring_panel.csv"
    summary_path = PROCESSED / "18l_full_hko_contract_event_market_score_summary.csv"
    book_path = PROCESSED / "18l_full_hko_contract_event_book_snapshot_summary.csv"
    diag_path = PROCESSED / "18l_clob_recovery_diagnostics.csv"
    integrity_path = PROCESSED / "18l_clob_recovery_integrity_checks.csv"
    issues_path = PROCESSED / "18l_clob_recovery_issues.csv"
    report_path = REPORTS / "18l_full_hko_contract_event_clob_price_recovery_report.md"
    bundle_path = BUNDLES / "18l_review_bundle.zip"

    price.to_csv(price_path, index=False)
    decision.to_csv(decision_path, index=False)
    scoring.to_csv(scoring_path, index=False)
    score_summary.to_csv(summary_path, index=False)
    book_summary.to_csv(book_path, index=False)
    diagnostics.to_csv(diag_path, index=False)
    integrity.to_csv(integrity_path, index=False)
    issues.to_csv(issues_path, index=False)

    report = build_report(target, price, diagnostics, decision, scoring, score_summary, book_summary, integrity, issues)
    report_path.write_text(report, encoding="utf-8")

    write_bundle([
        price_path,
        decision_path,
        scoring_path,
        summary_path,
        book_path,
        diag_path,
        integrity_path,
        issues_path,
        report_path,
    ], bundle_path)

    print("\nSaved outputs:")
    for p in output_paths():
        if p.exists():
            print(" ", p.relative_to(ROOT), f"({p.stat().st_size:,} bytes)")
    print("\n18l complete. Upload data/review_bundles/18l_review_bundle.zip for inspection.")


if __name__ == "__main__":
    main()
