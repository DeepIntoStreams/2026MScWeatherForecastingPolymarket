#!/usr/bin/env python3
"""
Phase 1: recover and certify row-level evidence from the frozen Version 2 release.

This phase is intentionally read-only with respect to frozen sources. It:
1. inventories frozen files and schemas;
2. builds canonical master-key tables;
3. recovers GP implementation and fitted-model evidence;
4. reconstructs raw and static event books;
5. canonicalises existing coherent GP/event-book outputs;
6. checks support, uniqueness, probability mass and provenance;
7. writes a review bundle and a strict completion report.

It does not refit or reselect the frozen weather model, pool weight or trading policy.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import sys
import textwrap
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np
import pandas as pd

try:
    from scipy.stats import norm
except Exception as exc:  # pragma: no cover
    raise RuntimeError("scipy is required for Gaussian event mapping") from exc


DATE_CANDIDATES = [
    "target_date", "event_date", "settlement_date", "date", "target_day"
]
RULE_CANDIDATES = [
    "decision_rule", "rule", "decision_time_rule", "forecast_rule"
]
MODEL_CANDIDATES = [
    "model", "model_name", "candidate_model", "selected_model",
    "forecast_model", "method", "procedure", "source"
]
EVENT_CANDIDATES = [
    "event_index", "event_order", "event_rank", "event_id",
    "contract_event_index", "contract_id"
]
PROBABILITY_CANDIDATES = [
    "event_probability", "probability", "p_model", "p_gp",
    "gp_probability", "raw_event_probability", "probability_regularised",
    "probability_regularized", "forecast_probability",
    "p_static", "p_rbf", "p_matern", "p_raw"
]
DETERMINISTIC_CANDIDATES = [
    "forecast_daily_max_c", "deterministic_daily_max_c",
    "forecast_max_c", "deterministic_forecast_c",
    "forecast_tmax_c", "ifs_daily_max_c", "selected_daily_max_c",
    "forecast_daily_max_C"
]
HKO_CANDIDATES = [
    "hko_daily_max_c", "hko_tmax_c", "target_c",
    "observed_daily_max_c", "hko_daily_max_C"
]
LOWER_CANDIDATES = [
    "lower_bound_c", "event_lower_c", "lower", "lower_bound"
]
UPPER_CANDIDATES = [
    "upper_bound_c", "event_upper_c", "upper", "upper_bound"
]
LOWER_CLOSED_CANDIDATES = [
    "lower_closed", "lower_inclusive"
]
UPPER_CLOSED_CANDIDATES = [
    "upper_closed", "upper_inclusive"
]
TRADE_CANDIDATES = [
    "trade", "trade_indicator", "executed", "is_trade", "trade_executed"
]
PNL_CANDIDATES = [
    "net_pnl", "pnl", "realised_pnl", "realized_pnl", "date_pnl"
]

KEYWORD_RE = re.compile(
    r"ConstantKernel|Matern|RBF|WhiteKernel|GaussianProcessRegressor|"
    r"constant_value_bounds|length_scale_bounds|noise_level_bounds|"
    r"n_restarts_optimizer|normalize_y|optimizer|alpha|"
    r"log_marginal_likelihood|ConvergenceWarning|kernel_",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed:\nSTDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def choose(columns: Iterable[str], candidates: Sequence[str]) -> str | None:
    lookup = {str(c).lower(): str(c) for c in columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def infer_model_from_path(path: Path) -> str | None:
    s = path.as_posix().lower()
    patterns = [
        ("matern", "matern"),
        ("mat32", "matern"),
        ("rbf", "rbf"),
        ("static", "static"),
        ("raw", "raw"),
        ("pool", "pool"),
        ("market", "market"),
        ("gp", "matern"),
    ]
    for token, label in patterns:
        if token in s:
            return label
    return None


def normalise_model_name(value: Any) -> str:
    s = str(value).strip().lower()
    if "matern" in s or "mat32" in s:
        return "matern"
    if "rbf" in s:
        return "rbf"
    if "static" in s or "gaussian_residual" in s:
        return "static"
    if "raw" in s or "point" in s or "deterministic" in s:
        return "raw"
    if "pool" in s or "blend" in s or "convex" in s:
        return "pool"
    if "market" in s or "polymarket" in s:
        return "market"
    if s in {"gp", "selected_gp", "selected"}:
        return "matern"
    return s


def read_table(path: Path, nrows: int | None = None) -> pd.DataFrame:
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".csv") or suffixes.endswith(".csv.gz"):
        return pd.read_csv(path, nrows=nrows, low_memory=False)
    if suffixes.endswith(".json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return pd.json_normalize(data)
        if isinstance(data, dict):
            return pd.json_normalize(data)
    raise ValueError(f"Unsupported table format: {path}")


def count_csv_rows(path: Path) -> int:
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def safe_date_summary(series: pd.Series) -> tuple[str | None, str | None, int]:
    parsed = pd.to_datetime(series, errors="coerce")
    valid = parsed.dropna()
    if valid.empty:
        return None, None, 0
    return (
        valid.min().isoformat(),
        valid.max().isoformat(),
        int(valid.dt.normalize().nunique()),
    )


def source_role(path: Path) -> str:
    s = path.as_posix().lower()
    rules = [
        ("phase23", "final_freeze"),
        ("phase22", "thesis_evidence_pack"),
        ("phase21", "clean_replay"),
        ("phase20", "forecast_combination_discrepancy"),
        ("phase19", "predictive_diagnostics"),
        ("phase18", "rule_block_stability"),
        ("phase17", "deterministic_error_support"),
        ("phase16", "raw_static_benchmarks"),
        ("phase15", "gp_code_math_reconciliation"),
        ("phase13", "verified_evidence_pack"),
        ("phase12", "trading_robustness"),
        ("phase11", "trading_ledger"),
        ("phase10", "exact_market_comparison"),
        ("phase9", "event_probability_books"),
        ("phase8", "full_history_predictions"),
        ("07_", "gp_validation_predictions"),
        ("06_", "gp_fold_matrix"),
        ("05_", "weather_residual_panel"),
        ("manifest", "manifest"),
        ("model", "model_artifact"),
        ("trade", "trading"),
        ("market", "market"),
        ("probab", "probability"),
        ("residual", "residual"),
    ]
    for token, role in rules:
        if token in s:
            return role
    return "other"


def iter_source_files(root: Path, priority_paths: Mapping[str, str]) -> list[Path]:
    roots: list[Path] = []
    for rel in priority_paths.values():
        p = root / rel
        if p.exists():
            roots.append(p)
    files: set[Path] = set()
    for item in roots:
        if item.is_file():
            files.add(item.resolve())
        elif item.is_dir():
            for p in item.rglob("*"):
                if p.is_file():
                    files.add(p.resolve())
    # Include configs, tools and model artifacts needed for implementation recovery.
    for rel in ["config/v2", "tools/v2", "models/v2", "tests/v2_completion"]:
        p = root / rel
        if p.exists():
            for f in p.rglob("*"):
                if f.is_file():
                    files.add(f.resolve())
    return sorted(files)


def inventory_files(root: Path, files: Sequence[Path]) -> pd.DataFrame:
    rows = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        rows.append(
            {
                "relative_path": rel,
                "role": source_role(path),
                "suffix": "".join(path.suffixes).lower(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return pd.DataFrame(rows)


def inventory_schemas(root: Path, files: Sequence[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in files:
        suffixes = "".join(path.suffixes).lower()
        if not (suffixes.endswith(".csv") or suffixes.endswith(".csv.gz") or suffixes.endswith(".json")):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            sample = read_table(path, nrows=5000)
            if suffixes.endswith(".csv") or suffixes.endswith(".csv.gz"):
                row_count = count_csv_rows(path)
            else:
                full = read_table(path)
                row_count = len(full)
            date_col = choose(sample.columns, DATE_CANDIDATES)
            rule_col = choose(sample.columns, RULE_CANDIDATES)
            model_col = choose(sample.columns, MODEL_CANDIDATES)
            event_col = choose(sample.columns, EVENT_CANDIDATES)
            min_date = max_date = None
            date_count = 0
            if date_col:
                min_date, max_date, date_count = safe_date_summary(sample[date_col])
            rows.append(
                {
                    "relative_path": rel,
                    "status": "READABLE",
                    "row_count": int(row_count),
                    "column_count": int(len(sample.columns)),
                    "columns": "|".join(map(str, sample.columns)),
                    "date_column": date_col or "",
                    "rule_column": rule_col or "",
                    "model_column": model_col or "",
                    "event_column": event_col or "",
                    "sample_min_date": min_date or "",
                    "sample_max_date": max_date or "",
                    "sample_distinct_dates": date_count,
                    "sample_distinct_rules": (
                        int(sample[rule_col].nunique(dropna=True)) if rule_col else 0
                    ),
                    "sample_distinct_models": (
                        int(sample[model_col].nunique(dropna=True)) if model_col else 0
                    ),
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "relative_path": rel,
                    "status": "UNREADABLE",
                    "row_count": np.nan,
                    "column_count": np.nan,
                    "columns": "",
                    "date_column": "",
                    "rule_column": "",
                    "model_column": "",
                    "event_column": "",
                    "sample_min_date": "",
                    "sample_max_date": "",
                    "sample_distinct_dates": 0,
                    "sample_distinct_rules": 0,
                    "sample_distinct_models": 0,
                    "error": repr(exc),
                }
            )
    return pd.DataFrame(rows)


def find_file(root: Path, exact_rel: str) -> Path | None:
    p = root / exact_rel
    return p if p.is_file() else None


def canonical_date_rule(
    df: pd.DataFrame,
    source_path: str,
    include_event: bool = False,
) -> pd.DataFrame:
    date_col = choose(df.columns, DATE_CANDIDATES)
    rule_col = choose(df.columns, RULE_CANDIDATES)
    if not date_col or not rule_col:
        raise ValueError(f"Missing date/rule columns in {source_path}")
    out = pd.DataFrame(
        {
            "settlement_date": pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d"),
            "decision_rule": df[rule_col].astype(str),
        }
    )
    if include_event:
        event_col = choose(df.columns, EVENT_CANDIDATES)
        if not event_col:
            raise ValueError(f"Missing event column in {source_path}")
        out["event_key"] = df[event_col].astype(str)
    out["source_path"] = source_path
    return out


def write_key_table(
    source_root: Path,
    source_file: Path | None,
    output_path: Path,
    include_event: bool = False,
) -> tuple[dict[str, Any], pd.DataFrame | None]:
    if source_file is None:
        return {"status": "MISSING", "source_path": ""}, None
    df = read_table(source_file)
    keys = canonical_date_rule(
        df,
        source_file.relative_to(source_root).as_posix(),
        include_event=include_event,
    )
    subset = ["settlement_date", "decision_rule"] + (["event_key"] if include_event else [])
    duplicated = keys.duplicated(subset).sum()
    unique = keys.drop_duplicates(subset).sort_values(subset)
    unique.to_csv(output_path, index=False)
    return (
        {
            "status": "FOUND",
            "source_path": source_file.relative_to(source_root).as_posix(),
            "rows": len(df),
            "unique_keys": len(unique),
            "duplicate_keys": int(duplicated),
            "dates": int(unique["settlement_date"].nunique()),
            "rules": int(unique["decision_rule"].nunique()),
        },
        unique,
    )


def best_csv_candidate(
    root: Path,
    files: Sequence[Path],
    required_tokens: Sequence[str],
    target_rows: int | None = None,
) -> Path | None:
    candidates: list[tuple[float, Path]] = []
    for path in files:
        s = path.relative_to(root).as_posix().lower()
        suffixes = "".join(path.suffixes).lower()
        if not (suffixes.endswith(".csv") or suffixes.endswith(".csv.gz")):
            continue
        if not all(token.lower() in s for token in required_tokens):
            continue
        score = 0.0
        try:
            rows = count_csv_rows(path)
            if target_rows is not None:
                score -= abs(rows - target_rows)
                if rows == target_rows:
                    score += 10000
            if "panel" in s:
                score += 100
            if "summary" in s:
                score -= 50
            if "manifest" in s:
                score -= 100
        except Exception:
            pass
        candidates.append((score, path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: (x[0], x[1].as_posix()), reverse=True)[0][1]


def find_event_candidates(root: Path, files: Sequence[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in files:
        suffixes = "".join(path.suffixes).lower()
        if not (suffixes.endswith(".csv") or suffixes.endswith(".csv.gz")):
            continue
        try:
            sample = read_table(path, nrows=5000)
        except Exception:
            continue
        date_col = choose(sample.columns, DATE_CANDIDATES)
        rule_col = choose(sample.columns, RULE_CANDIDATES)
        event_col = choose(sample.columns, EVENT_CANDIDATES)
        model_col = choose(sample.columns, MODEL_CANDIDATES)
        prob_cols = [
            c for c in sample.columns
            if str(c).lower() in {x.lower() for x in PROBABILITY_CANDIDATES}
            or ("probab" in str(c).lower() and "total" not in str(c).lower())
        ]
        if not (date_col and rule_col and event_col and prob_cols):
            continue
        for prob_col in prob_cols:
            rows.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "row_count": count_csv_rows(path),
                    "date_column": date_col,
                    "rule_column": rule_col,
                    "event_column": event_col,
                    "model_column": model_col or "",
                    "probability_column": prob_col,
                    "inferred_model": infer_model_from_path(path) or "",
                }
            )
    return pd.DataFrame(rows)


def canonicalise_existing_event_books(
    source_root: Path,
    candidates: pd.DataFrame,
    output_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    checks: list[dict[str, Any]] = []
    for row in candidates.to_dict("records"):
        path = source_root / row["relative_path"]
        try:
            df = read_table(path)
            date_col = row["date_column"]
            rule_col = row["rule_column"]
            event_col = row["event_column"]
            prob_col = row["probability_column"]
            model_col = row["model_column"] or None
            out = pd.DataFrame(
                {
                    "settlement_date": pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d"),
                    "decision_rule": df[rule_col].astype(str),
                    "event_key": df[event_col].astype(str),
                    "probability": pd.to_numeric(df[prob_col], errors="coerce"),
                }
            )
            if model_col:
                out["model"] = df[model_col].map(normalise_model_name)
            else:
                out["model"] = row["inferred_model"] or "unknown"
            block_col = choose(df.columns, ["chronology_block", "period", "sample_period"])
            if block_col:
                out["period"] = df[block_col].astype(str)
            else:
                out["period"] = ""
            out["source_path"] = row["relative_path"]
            out["source_probability_column"] = prob_col
            valid = out.dropna(subset=["settlement_date", "probability"]).copy()
            frames.append(valid)

            grouped = valid.groupby(
                ["settlement_date", "decision_rule", "model"], dropna=False
            )["probability"].agg(["count", "sum", "min", "max"]).reset_index()
            checks.append(
                {
                    "relative_path": row["relative_path"],
                    "probability_column": prob_col,
                    "rows": len(valid),
                    "books": len(grouped),
                    "books_with_11_events": int((grouped["count"] == 11).sum()),
                    "books_mass_close_1": int(np.isclose(grouped["sum"], 1.0, atol=1e-8).sum()),
                    "probabilities_in_unit_interval": bool(
                        ((valid["probability"] >= -1e-12) & (valid["probability"] <= 1 + 1e-12)).all()
                    ),
                    "max_mass_error": float((grouped["sum"] - 1.0).abs().max()) if len(grouped) else np.nan,
                    "status": "READABLE",
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "relative_path": row["relative_path"],
                    "probability_column": row["probability_column"],
                    "rows": 0,
                    "books": 0,
                    "books_with_11_events": 0,
                    "books_mass_close_1": 0,
                    "probabilities_in_unit_interval": False,
                    "max_mass_error": np.nan,
                    "status": f"FAILED: {exc!r}",
                }
            )
    canonical = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not canonical.empty:
        canonical.to_csv(output_path, index=False, compression="gzip")
    return canonical, pd.DataFrame(checks)


def find_certified_events(root: Path, files: Sequence[Path]) -> Path | None:
    preferred = root / "data/processed/certified_event_books.csv"
    if preferred.is_file():
        return preferred
    candidates = [
        p for p in files
        if "certified_event" in p.name.lower()
        and "".join(p.suffixes).lower() in {".csv", ".csv.gz"}
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_size, reverse=True)[0]


def interval_membership(
    value: float,
    lower: float | None,
    upper: float | None,
    lower_closed: bool,
    upper_closed: bool,
) -> bool:
    if lower is not None and not math.isnan(lower):
        if value < lower or (value == lower and not lower_closed):
            return False
    if upper is not None and not math.isnan(upper):
        if value > upper or (value == upper and not upper_closed):
            return False
    return True


def reconstruct_raw_static_books(
    source_root: Path,
    weather_path: Path | None,
    market_prediction_path: Path | None,
    certified_events_path: Path | None,
    output_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    checks: list[dict[str, Any]] = []
    if not (weather_path and market_prediction_path and certified_events_path):
        missing = [
            name for name, p in [
                ("weather_residual_panel", weather_path),
                ("market_predictions", market_prediction_path),
                ("certified_events", certified_events_path),
            ] if p is None
        ]
        return pd.DataFrame(), pd.DataFrame([{
            "check": "raw_static_reconstruction_inputs",
            "passed": False,
            "detail": f"missing: {', '.join(missing)}"
        }])

    weather = read_table(weather_path)
    market = read_table(market_prediction_path)
    events = read_table(certified_events_path)

    weather_date = choose(weather.columns, DATE_CANDIDATES)
    weather_rule = choose(weather.columns, RULE_CANDIDATES)
    det_w = choose(weather.columns, DETERMINISTIC_CANDIDATES)
    hko_w = choose(weather.columns, HKO_CANDIDATES)
    market_date = choose(market.columns, DATE_CANDIDATES)
    market_rule = choose(market.columns, RULE_CANDIDATES)
    det_m = choose(market.columns, DETERMINISTIC_CANDIDATES)
    event_date = choose(events.columns, DATE_CANDIDATES)
    event_key = choose(events.columns, EVENT_CANDIDATES)
    lower_col = choose(events.columns, LOWER_CANDIDATES)
    upper_col = choose(events.columns, UPPER_CANDIDATES)
    lower_closed_col = choose(events.columns, LOWER_CLOSED_CANDIDATES)
    upper_closed_col = choose(events.columns, UPPER_CLOSED_CANDIDATES)

    required = {
        "weather_date": weather_date, "weather_rule": weather_rule,
        "weather_deterministic": det_w, "weather_hko": hko_w,
        "market_date": market_date, "market_rule": market_rule,
        "market_deterministic": det_m, "event_date": event_date,
        "event_key": event_key, "lower": lower_col, "upper": upper_col,
    }
    missing_cols = [k for k, v in required.items() if v is None]
    if missing_cols:
        return pd.DataFrame(), pd.DataFrame([{
            "check": "raw_static_reconstruction_columns",
            "passed": False,
            "detail": f"missing semantic columns: {missing_cols}"
        }])

    w = weather[[weather_date, weather_rule, det_w, hko_w]].copy()
    w["settlement_date"] = pd.to_datetime(w[weather_date], errors="coerce").dt.strftime("%Y-%m-%d")
    w["decision_rule"] = w[weather_rule].astype(str)
    w["residual"] = pd.to_numeric(w[hko_w], errors="coerce") - pd.to_numeric(w[det_w], errors="coerce")
    stats = w.groupby("decision_rule")["residual"].agg(["count", "mean", "std"]).reset_index()
    stats = stats.rename(columns={"mean": "static_bias", "std": "static_sd"})

    m = market[[market_date, market_rule, det_m]].copy()
    m["settlement_date"] = pd.to_datetime(m[market_date], errors="coerce").dt.strftime("%Y-%m-%d")
    m["decision_rule"] = m[market_rule].astype(str)
    m["deterministic_forecast_c"] = pd.to_numeric(m[det_m], errors="coerce")
    m = m.merge(stats, on="decision_rule", how="left", validate="many_to_one")

    e = events.copy()
    e["settlement_date"] = pd.to_datetime(e[event_date], errors="coerce").dt.strftime("%Y-%m-%d")
    e["event_key"] = e[event_key].astype(str)
    e["lower"] = pd.to_numeric(e[lower_col], errors="coerce")
    e["upper"] = pd.to_numeric(e[upper_col], errors="coerce")
    if lower_closed_col:
        e["lower_closed"] = e[lower_closed_col].fillna(False).astype(bool)
    else:
        e["lower_closed"] = True
    if upper_closed_col:
        e["upper_closed"] = e[upper_closed_col].fillna(False).astype(bool)
    else:
        e["upper_closed"] = False

    merged = m.merge(
        e[["settlement_date", "event_key", "lower", "upper", "lower_closed", "upper_closed"]],
        on="settlement_date",
        how="inner",
        validate="many_to_many",
    )
    rows: list[dict[str, Any]] = []
    for rec in merged.to_dict("records"):
        x = float(rec["deterministic_forecast_c"])
        lower = rec["lower"]
        upper = rec["upper"]
        lower_val = None if pd.isna(lower) else float(lower)
        upper_val = None if pd.isna(upper) else float(upper)
        raw_p = 1.0 if interval_membership(
            x, lower_val, upper_val, bool(rec["lower_closed"]), bool(rec["upper_closed"])
        ) else 0.0

        mu = x + float(rec["static_bias"])
        sd = float(rec["static_sd"])
        lower_cdf = 0.0 if lower_val is None else norm.cdf((lower_val - mu) / sd)
        upper_cdf = 1.0 if upper_val is None else norm.cdf((upper_val - mu) / sd)
        static_p = max(min(upper_cdf - lower_cdf, 1.0), 0.0)

        base = {
            "settlement_date": rec["settlement_date"],
            "decision_rule": rec["decision_rule"],
            "event_key": rec["event_key"],
            "deterministic_forecast_c": x,
            "event_lower_c": lower_val,
            "event_upper_c": upper_val,
        }
        rows.append({**base, "model": "raw", "probability": raw_p})
        rows.append({
            **base, "model": "static", "probability": static_p,
            "predictive_mean_c": mu, "predictive_sd_c": sd,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out.to_csv(output_path, index=False, compression="gzip")
        grouped = out.groupby(
            ["settlement_date", "decision_rule", "model"]
        )["probability"].agg(["count", "sum", "min", "max"]).reset_index()
        checks.extend([
            {
                "check": "raw_static_books_nonempty",
                "passed": True,
                "detail": f"rows={len(out)}, books={len(grouped)}",
            },
            {
                "check": "raw_static_11_events_per_book",
                "passed": bool((grouped["count"] == 11).all()),
                "detail": f"bad_books={int((grouped['count'] != 11).sum())}",
            },
            {
                "check": "raw_static_mass_closure",
                "passed": bool(np.isclose(grouped["sum"], 1.0, atol=1e-8).all()),
                "detail": f"max_error={float((grouped['sum'] - 1).abs().max()):.3e}",
            },
            {
                "check": "raw_static_probabilities_unit_interval",
                "passed": bool(
                    ((out["probability"] >= -1e-12) & (out["probability"] <= 1 + 1e-12)).all()
                ),
                "detail": "",
            },
        ])
    return out, pd.DataFrame(checks)


def collect_text_evidence(root: Path, files: Sequence[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    allowed = {".py", ".json", ".md", ".txt", ".ipynb", ".yml", ".yaml"}
    for path in files:
        if path.suffix.lower() not in allowed:
            continue
        if path.stat().st_size > 20_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if KEYWORD_RE.search(line):
                rows.append(
                    {
                        "relative_path": path.relative_to(root).as_posix(),
                        "line_number": line_number,
                        "text": line[:2000],
                    }
                )
    return pd.DataFrame(rows)


def flatten_model_evidence(
    obj: Any,
    source_path: str,
    object_name: str = "root",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    visited: set[int] = set()

    def walk(current: Any, name: str, depth: int) -> None:
        if depth > 6 or id(current) in visited:
            return
        visited.add(id(current))
        cls = type(current).__name__
        if hasattr(current, "kernel_") or "GaussianProcessRegressor" in cls:
            rec: dict[str, Any] = {
                "source_path": source_path,
                "object_name": name,
                "class_name": cls,
            }
            for attr in [
                "kernel_", "kernel", "optimizer", "n_restarts_optimizer",
                "alpha", "normalize_y", "log_marginal_likelihood_value_",
                "random_state",
            ]:
                if hasattr(current, attr):
                    try:
                        rec[attr] = repr(getattr(current, attr))
                    except Exception:
                        rec[attr] = "<unreadable>"
            try:
                params = current.get_params(deep=True)
                for key in [
                    "kernel__k1__constant_value",
                    "kernel__k1__constant_value_bounds",
                    "kernel__k2__length_scale",
                    "kernel__k2__length_scale_bounds",
                    "kernel__k2__noise_level",
                    "kernel__k2__noise_level_bounds",
                    "n_restarts_optimizer",
                    "alpha",
                    "normalize_y",
                    "optimizer",
                ]:
                    if key in params:
                        rec[f"param::{key}"] = repr(params[key])
            except Exception:
                pass
            rows.append(rec)
        if hasattr(current, "named_steps"):
            for step_name, step in current.named_steps.items():
                walk(step, f"{name}.named_steps[{step_name}]", depth + 1)
        if isinstance(current, Mapping):
            for key, value in current.items():
                walk(value, f"{name}[{key!r}]", depth + 1)
        elif isinstance(current, (list, tuple)):
            for idx, value in enumerate(current):
                walk(value, f"{name}[{idx}]", depth + 1)
    walk(obj, object_name, 0)
    return rows


def load_model_registry(root: Path, files: Sequence[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    model_files = [
        p for p in files
        if "".join(p.suffixes).lower() in {".pkl", ".pickle", ".joblib"}
    ]
    for path in model_files:
        rel = path.relative_to(root).as_posix()
        try:
            if path.suffix.lower() == ".joblib":
                import joblib
                obj = joblib.load(path)
            else:
                with path.open("rb") as handle:
                    obj = pickle.load(handle)
            extracted = flatten_model_evidence(obj, rel)
            if extracted:
                rows.extend(extracted)
            else:
                rows.append({
                    "source_path": rel,
                    "object_name": "root",
                    "class_name": type(obj).__name__,
                    "status": "loaded_no_gp_object_found",
                })
        except Exception as exc:
            rows.append({
                "source_path": rel,
                "object_name": "",
                "class_name": "",
                "status": f"load_failed: {exc!r}",
            })
    return pd.DataFrame(rows)


def completion_rows(
    expected: Mapping[str, Any],
    weather_summary: Mapping[str, Any],
    market_summary: Mapping[str, Any],
    event_summary: Mapping[str, Any],
    exact_summary: Mapping[str, Any],
    gp_text: pd.DataFrame,
    gp_models: pd.DataFrame,
    reconstructed: pd.DataFrame,
    canonical_existing: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(item: str, passed: bool, detail: str, critical: bool = True) -> None:
        rows.append({
            "item": item, "passed": bool(passed),
            "critical": bool(critical), "detail": detail,
        })

    add(
        "weather residual panel",
        weather_summary.get("status") == "FOUND"
        and weather_summary.get("rows") == expected["weather_rows"]
        and weather_summary.get("dates") == expected["weather_dates"]
        and weather_summary.get("rules") == expected["decision_rules"]
        and weather_summary.get("duplicate_keys") == 0,
        json.dumps(dict(weather_summary), sort_keys=True),
    )
    add(
        "market prediction keys",
        market_summary.get("status") == "FOUND"
        and market_summary.get("unique_keys") == expected["market_prediction_keys"]
        and market_summary.get("duplicate_keys") == 0,
        json.dumps(dict(market_summary), sort_keys=True),
    )
    add(
        "phase9 event probability panel",
        event_summary.get("status") == "FOUND"
        and event_summary.get("rows") == expected["phase9_event_rows"],
        json.dumps(dict(event_summary), sort_keys=True),
    )
    add(
        "phase10 exact support panel",
        exact_summary.get("status") == "FOUND"
        and exact_summary.get("rows") == expected["phase10_event_rows"],
        json.dumps(dict(exact_summary), sort_keys=True),
    )
    add(
        "GP implementation text evidence",
        not gp_text.empty,
        f"matching lines={len(gp_text)}",
    )
    add(
        "serialised GP model evidence",
        not gp_models.empty and (
            gp_models.get("class_name", pd.Series(dtype=str))
            .astype(str).str.contains("GaussianProcessRegressor").any()
            or gp_models.astype(str).apply(
                lambda s: s.str.contains("Matern|RBF|WhiteKernel", case=False, regex=True)
            ).any().any()
        ),
        f"registry rows={len(gp_models)}",
        critical=False,
    )
    models_reconstructed = (
        set(reconstructed["model"].dropna().unique()) if not reconstructed.empty else set()
    )
    add(
        "raw event-book reconstruction",
        "raw" in models_reconstructed,
        f"models={sorted(models_reconstructed)}",
    )
    add(
        "static event-book reconstruction",
        "static" in models_reconstructed,
        f"models={sorted(models_reconstructed)}",
    )
    existing_models = (
        set(canonical_existing["model"].dropna().unique())
        if not canonical_existing.empty else set()
    )
    add(
        "existing coherent GP/event-book evidence",
        bool(existing_models & {"matern", "rbf"}),
        f"models={sorted(existing_models)}",
    )
    add(
        "RBF full-history market book recovered",
        "rbf" in existing_models or "rbf" in models_reconstructed,
        f"models={sorted(existing_models | models_reconstructed)}",
        critical=False,
    )
    return pd.DataFrame(rows)


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    completion: pd.DataFrame,
    weather_summary: Mapping[str, Any],
    market_summary: Mapping[str, Any],
    event_summary: Mapping[str, Any],
    exact_summary: Mapping[str, Any],
    event_checks: pd.DataFrame,
    raw_static_checks: pd.DataFrame,
) -> None:
    critical_failures = completion.loc[
        completion["critical"] & ~completion["passed"]
    ]
    overall = "PASSED" if critical_failures.empty else "FAILED"
    lines = [
        "# Phase 1 — Complete Row-Level Evidence Recovery",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"## Overall status: **{overall}**",
        "",
        "The phase is read-only with respect to the frozen source tag. "
        "It inventories evidence, certifies master keys, recovers GP implementation "
        "evidence, reconstructs raw/static event books and canonicalises existing "
        "event-probability outputs.",
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(dict(provenance), indent=2, sort_keys=True),
        "```",
        "",
        "## Completion register",
        "",
        completion.to_markdown(index=False),
        "",
        "## Master-key summaries",
        "",
        "### Weather residual panel",
        "",
        "```json",
        json.dumps(dict(weather_summary), indent=2, sort_keys=True),
        "```",
        "",
        "### Market-period forecast keys",
        "",
        "```json",
        json.dumps(dict(market_summary), indent=2, sort_keys=True),
        "```",
        "",
        "### Phase 9 event rows",
        "",
        "```json",
        json.dumps(dict(event_summary), indent=2, sort_keys=True),
        "```",
        "",
        "### Phase 10 exact-support rows",
        "",
        "```json",
        json.dumps(dict(exact_summary), indent=2, sort_keys=True),
        "```",
        "",
        "## Existing event-book checks",
        "",
        event_checks.to_markdown(index=False) if not event_checks.empty else "_No candidate event panels found._",
        "",
        "## Raw/static reconstruction checks",
        "",
        raw_static_checks.to_markdown(index=False) if not raw_static_checks.empty else "_No reconstruction checks._",
        "",
        "## Interpretation boundary",
        "",
        "- This phase does not reselect or refit the frozen Matérn model.",
        "- Raw and static event books are deterministic reconstructions from frozen inputs.",
        "- Existing RBF or Matérn books are canonicalised only when found in frozen outputs.",
        "- A missing full-history RBF market book is recorded as a non-critical recovery gap; "
        "it must not be silently approximated with a different GP specification.",
        "",
    ]
    (out / "phase1_report.md").write_text("\n".join(lines), encoding="utf-8")


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {"phase1_manifest.json", "phase1_review_bundle.zip"}:
            files.append({
                "relative_path": path.relative_to(out).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    manifest = {
        "phase": "phase1_evidence_recovery",
        "generated_utc": utc_now(),
        "provenance": dict(provenance),
        "files": files,
    }
    (out / "phase1_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase1_review_bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                zf.write(path, path.relative_to(out).as_posix())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    frozen_root = args.frozen_root.resolve()
    out = (repo_root / args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec = json.loads((repo_root / args.spec).read_text(encoding="utf-8"))
    priority = spec["priority_paths"]
    expected = spec["expected"]

    provenance = {
        "generated_utc": utc_now(),
        "repo_root": str(repo_root),
        "working_branch": git(repo_root, "branch", "--show-current"),
        "working_head": git(repo_root, "rev-parse", "HEAD"),
        "frozen_ref": spec["frozen_ref"],
        "frozen_head": git(repo_root, "rev-parse", spec["frozen_ref"]),
        "frozen_root": str(frozen_root),
        "working_tree_clean_before_phase": git(repo_root, "status", "--short") == "",
    }
    (out / "phase1_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )

    files = iter_source_files(frozen_root, priority)
    file_inventory = inventory_files(frozen_root, files)
    file_inventory.to_csv(out / "phase1_file_inventory.csv", index=False)
    schema_inventory = inventory_schemas(frozen_root, files)
    schema_inventory.to_csv(out / "phase1_schema_inventory.csv", index=False)

    weather_file = find_file(frozen_root, priority["weather_residual_panel"])
    market_file = find_file(frozen_root, priority["phase8_market_predictions"])
    phase9_file = best_csv_candidate(
        frozen_root, files, ["phase9"], target_rows=expected["phase9_event_rows"]
    )
    phase10_file = best_csv_candidate(
        frozen_root, files, ["phase10"], target_rows=expected["phase10_event_rows"]
    )
    phase11_file = best_csv_candidate(
        frozen_root, files, ["phase11", "ledger"], target_rows=None
    )

    weather_summary, _ = write_key_table(
        frozen_root, weather_file,
        out / "phase1_master_weather_keys.csv", include_event=False
    )
    market_summary, _ = write_key_table(
        frozen_root, market_file,
        out / "phase1_master_market_prediction_keys.csv", include_event=False
    )
    event_summary, _ = write_key_table(
        frozen_root, phase9_file,
        out / "phase1_master_event_book_keys.csv", include_event=True
    )
    exact_summary, _ = write_key_table(
        frozen_root, phase10_file,
        out / "phase1_master_exact_support_keys.csv", include_event=True
    )
    trade_summary, _ = write_key_table(
        frozen_root, phase11_file,
        out / "phase1_master_trade_date_keys.csv", include_event=False
    )

    key_summary = pd.DataFrame([
        {"object": "weather", **weather_summary},
        {"object": "market_predictions", **market_summary},
        {"object": "phase9_event_books", **event_summary},
        {"object": "phase10_exact_support", **exact_summary},
        {"object": "phase11_trade_ledger", **trade_summary},
    ])
    key_summary.to_csv(out / "phase1_master_key_summary.csv", index=False)

    event_candidates = find_event_candidates(frozen_root, files)
    event_candidates.to_csv(out / "phase1_event_book_candidate_inventory.csv", index=False)
    canonical_existing, event_checks = canonicalise_existing_event_books(
        frozen_root,
        event_candidates,
        out / "phase1_canonical_existing_event_books.csv.gz",
    )
    event_checks.to_csv(out / "phase1_event_book_integrity_checks.csv", index=False)

    certified_events = find_certified_events(frozen_root, files)
    reconstructed, raw_static_checks = reconstruct_raw_static_books(
        frozen_root,
        weather_file,
        market_file,
        certified_events,
        out / "phase1_reconstructed_raw_static_event_books.csv.gz",
    )
    raw_static_checks.to_csv(
        out / "phase1_raw_static_event_book_checks.csv", index=False
    )

    gp_text = collect_text_evidence(frozen_root, files)
    gp_text.to_csv(out / "phase1_gp_text_evidence.csv", index=False)
    gp_models = load_model_registry(frozen_root, files)
    gp_models.to_csv(out / "phase1_gp_model_registry.csv", index=False)

    completion = completion_rows(
        expected,
        weather_summary,
        market_summary,
        event_summary,
        exact_summary,
        gp_text,
        gp_models,
        reconstructed,
        canonical_existing,
    )
    completion.to_csv(out / "phase1_completion_status.csv", index=False)

    write_report(
        out,
        provenance,
        completion,
        weather_summary,
        market_summary,
        event_summary,
        exact_summary,
        event_checks,
        raw_static_checks,
    )
    build_manifest(out, provenance)
    make_review_bundle(out)

    critical_failures = completion.loc[
        completion["critical"] & ~completion["passed"]
    ]
    print("=" * 78)
    print("PHASE 1 EVIDENCE RECOVERY")
    print("=" * 78)
    print(completion.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase1_review_bundle.zip'}")
    if critical_failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print("Critical failures:")
    print(critical_failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
