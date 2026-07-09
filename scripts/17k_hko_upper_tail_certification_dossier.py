#!/usr/bin/env python3
"""
17k_hko_upper_tail_certification_dossier.py

Fail-closed certification audit for Hong Kong Polymarket upper-tail temperature markets.

Purpose
-------
This script attempts to upgrade the Hong Kong HKO Daily Extract one-decimal upper-tail
contracts from empirically supported proxies to formally certified threshold contracts.
It never certifies a market from a title label alone.

Certification routes
--------------------
A market is formally certified only if at least one of these conditions is met:
  1. Dedicated Gamma metadata boundary fields explicitly encode the upper-tail boundary [K, infinity).
  2. A written Polymarket/resolver confirmation is supplied and manually recorded.

A market is observation-ready only if its HKO settlement value is available and agrees with the
recorded resolution. The HKO historical archive reconciliation is reported separately because
first-published/finalised values may differ from the latest CSV.

Run from the repository root:
    python3 scripts/17k_hko_upper_tail_certification_dossier.py

Expected previous input from 17j:
    data/processed/17j_hko_polymarket_hko_upper_tail_summary.csv
or  data/processed/17j_hko_polymarket_hko_tail_admissibility_decision.csv

Outputs:
    data/processed/17k_polymarket_raw_metadata_boundary_audit.csv
    data/processed/17k_hko_historical_archive_value_reconciliation.csv
    data/processed/17k_hko_upper_tail_certification_dossier.csv
    data/processed/17k_hko_upper_tail_certification_decision.csv
    docs/research_outputs/17k_hko_upper_tail_certification_report.md
    data/raw/polymarket_gamma_market_json/*.json
    data/raw/hko_historical_archive/*.csv
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd
import requests

GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_GOV_HK_HISTORY_BASE = "https://app.data.gov.hk/v1/historical-archive"
HKO_DAILY_MAX_URL = (
    "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php"
    "?dataType=CLMMAXT&rformat=csv&station=HKO"
)

# Optional. Paste a positive Polymarket/resolver confirmation here if received.
# Keep this empty unless you have written confirmation saved in admin/ or email.
POLYMARKET_RULE_CONFIRMATION_TEXT = """""".strip()

# Evidence threshold: if true, the script may classify strict-family upper-tail markets as formally
# certified if the written confirmation text is present and recognisable.
ALLOW_WRITTEN_CONFIRMATION_CERTIFICATION = True

# If true, a dedicated boundary field must explicitly encode K or [K, infinity).
# This is the strongest automatic route.
ALLOW_METADATA_CERTIFICATION = True

# Network settings
REQUEST_SLEEP_SECONDS = 0.25
REQUEST_TIMEOUT = 30


def repo_root() -> Path:
    """Find repository root from script/notebook location or cwd."""
    start = Path.cwd().resolve()
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    # Fallback: if run from notebooks, parent may be root.
    if start.name == "notebooks":
        return start.parent
    return start


ROOT = repo_root()
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DOCS_OUT = ROOT / "docs" / "research_outputs"
RAW_GAMMA_DIR = DATA_RAW / "polymarket_gamma_market_json"
RAW_HKO_HISTORY_DIR = DATA_RAW / "hko_historical_archive"

for d in [DATA_RAW, DATA_PROCESSED, DOCS_OUT, RAW_GAMMA_DIR, RAW_HKO_HISTORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def safe_filename(s: Any, max_len: int = 120) -> str:
    s = str(s or "")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")
    return s[:max_len] or "unknown"


def request_json(url: str, params: Optional[dict] = None, *, retries: int = 3) -> Any:
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code in {429, 500, 502, 503, 504}:
                time.sleep((attempt + 1) * 1.5)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep((attempt + 1) * 1.5)
    raise RuntimeError(f"Failed JSON request: {url} params={params} err={last_err}")


def request_text(url: str, params: Optional[dict] = None, *, retries: int = 3, follow_redirects: bool = True) -> str:
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, allow_redirects=follow_redirects)
            if r.status_code in {429, 500, 502, 503, 504}:
                time.sleep((attempt + 1) * 1.5)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            time.sleep((attempt + 1) * 1.5)
    raise RuntimeError(f"Failed text request: {url} params={params} err={last_err}")


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_hko_daily_max_csv(text: str) -> pd.DataFrame:
    """Parse HKO daily max CSV. Robust to bilingual column names."""
    candidates = []
    for skip in range(0, 15):
        try:
            df = pd.read_csv(StringIO(text), skiprows=skip)
            df = normalise_columns(df)
            cols = list(df.columns)
            has_year = any("Year" in c or "年" == c for c in cols)
            has_month = any("Month" in c or "月" == c for c in cols)
            has_day = any("Day" in c or "日" == c for c in cols)
            has_value = any("Value" in c or "數值" in c or "数值" in c for c in cols)
            if has_year and has_month and has_day and has_value:
                candidates.append((skip, df))
        except Exception:
            continue

    if not candidates:
        # Last attempt: maybe it already has English columns.
        df = pd.read_csv(StringIO(text))
        df = normalise_columns(df)
    else:
        # Prefer the one with more rows.
        df = max(candidates, key=lambda x: x[1].shape[0])[1]

    cols = list(df.columns)

    def pick(names: List[str], contains: List[str]) -> Optional[str]:
        for n in names:
            if n in cols:
                return n
        for c in cols:
            cc = c.lower()
            if any(k.lower() in cc for k in contains):
                return c
        return None

    year_col = pick(["Year", "年份", "年"], ["year", "年份"])
    month_col = pick(["Month", "月份", "月"], ["month", "月份"])
    day_col = pick(["Day", "日期", "日"], ["day", "日期"])
    # Important: choose actual value column, not data completeness.
    value_col = None
    for c in cols:
        if c.strip() in {"Value", "數值", "数值", "Value (deg. C)", "數值 (攝氏度)"}:
            value_col = c
            break
    if value_col is None:
        for c in cols:
            if ("value" in c.lower() or "數值" in c or "数值" in c) and "completeness" not in c.lower():
                value_col = c
                break

    missing = [name for name, col in [("year", year_col), ("month", month_col), ("day", day_col), ("value", value_col)] if col is None]
    if missing:
        raise ValueError(f"Could not identify HKO columns: missing {missing}; columns={cols}")

    out = df[[year_col, month_col, day_col, value_col]].copy()
    out.columns = ["year", "month", "day", "hko_tmax_C"]
    for c in ["year", "month", "day"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out["hko_tmax_C"] = pd.to_numeric(out["hko_tmax_C"], errors="coerce")
    out = out.dropna(subset=["year", "month", "day", "hko_tmax_C"])
    out["date"] = pd.to_datetime(dict(year=out["year"].astype(int), month=out["month"].astype(int), day=out["day"].astype(int)), errors="coerce")
    out = out.dropna(subset=["date"])
    out = out[["date", "hko_tmax_C"]].drop_duplicates("date", keep="last").sort_values("date")
    return out


def get_latest_hko_daily_max() -> pd.DataFrame:
    text = request_text(HKO_DAILY_MAX_URL)
    (DATA_RAW / "hko_daily_max_temperature_latest.csv").write_text(text, encoding="utf-8")
    hko = parse_hko_daily_max_csv(text)
    if hko.empty:
        raise RuntimeError("Parsed HKO latest daily max is empty; stop.")
    hko.to_csv(DATA_PROCESSED / "17k_hko_daily_max_latest_parsed.csv", index=False)
    return hko


def load_17j_tail_rows() -> pd.DataFrame:
    candidates = [
        DATA_PROCESSED / "17j_hko_polymarket_hko_upper_tail_summary.csv",
        DATA_PROCESSED / "17j_hko_polymarket_hko_tail_admissibility_decision.csv",
        ROOT / "notebooks" / "data" / "processed" / "17j_hko_polymarket_hko_upper_tail_summary.csv",
        ROOT / "notebooks" / "data" / "processed" / "17j_hko_polymarket_hko_tail_admissibility_decision.csv",
    ]
    for p in candidates:
        if p.exists():
            df = pd.read_csv(p)
            df["_source_file"] = str(p)
            print(f"Loaded 17j input: {p} shape={df.shape}")
            return df
    raise FileNotFoundError("No 17j upper-tail summary/decision CSV found. Run 17j first.")


def coerce_bool(x: Any) -> Optional[bool]:
    if pd.isna(x):
        return None
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def first_present(row: pd.Series, names: Iterable[str], default=None):
    for n in names:
        if n in row and not pd.isna(row[n]) and str(row[n]).strip() != "":
            return row[n]
    return default


def parse_threshold_from_text(text: Any) -> Optional[int]:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return None
    s = str(text)
    patterns = [
        r"(\d{1,2})\s*°\s*C\s*or\s*higher",
        r"(\d{1,2})\s*C\s*or\s*higher",
        r"(\d{1,2})\s*º\s*C\s*or\s*higher",
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.I)
        if m:
            return int(m.group(1))
    return None


def get_market_id(row: pd.Series) -> Optional[str]:
    return str(first_present(row, ["market_id", "id", "marketId", "marketId_x", "id_x"], "") or "").strip() or None


def fetch_gamma_market(market_id: str) -> Dict[str, Any]:
    url = f"{GAMMA_BASE}/markets/{market_id}"
    data = request_json(url)
    slug = safe_filename(data.get("slug") or market_id)
    out_path = RAW_GAMMA_DIR / f"market_{safe_filename(market_id)}_{slug}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    time.sleep(REQUEST_SLEEP_SECONDS)
    return data


def maybe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s == "" or s.lower() in {"none", "nan", "null"}:
        return None
    # Extract a number from strings like "33" or "33.0".
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def field_has_infinity(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    s = str(x).strip().lower()
    return s in {"", "none", "null", "nan", "inf", "infinity", "+inf", "+infinity", "∞"} or "infinity" in s or "∞" in s


def approx_equal(a: Optional[float], b: Optional[float], tol: float = 1e-9) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def boundary_metadata_certifies(market: Dict[str, Any], K: Optional[int]) -> Tuple[bool, str, Dict[str, Any]]:
    """Return whether dedicated metadata certifies [K, infinity). Do not certify from question/title alone."""
    if K is None:
        return False, "missing_threshold_K", {}

    fields = {
        "lowerBound": market.get("lowerBound"),
        "upperBound": market.get("upperBound"),
        "groupItemThreshold": market.get("groupItemThreshold"),
        "groupItemRange": market.get("groupItemRange"),
        "xAxisValue": market.get("xAxisValue"),
        "yAxisValue": market.get("yAxisValue"),
        "formatType": market.get("formatType"),
        "marketType": market.get("marketType"),
    }
    Kf = float(K)

    lb = maybe_float(fields["lowerBound"])
    ub = maybe_float(fields["upperBound"])
    if approx_equal(lb, Kf) and (field_has_infinity(fields["upperBound"]) or ub is None):
        return True, "dedicated_lowerBound_equals_K_and_upperBound_is_open", fields

    # groupItemRange may be a JSON-ish string/list/dict. Accept only if it clearly contains lower K and open/infinite upper.
    gir = fields.get("groupItemRange")
    if gir is not None and not (isinstance(gir, float) and math.isnan(gir)):
        try:
            parsed = json.loads(gir) if isinstance(gir, str) else gir
        except Exception:
            parsed = gir
        if isinstance(parsed, dict):
            glb = maybe_float(parsed.get("lower") or parsed.get("lowerBound") or parsed.get("min"))
            gub_raw = parsed.get("upper") or parsed.get("upperBound") or parsed.get("max")
            gub = maybe_float(gub_raw)
            if approx_equal(glb, Kf) and (field_has_infinity(gub_raw) or gub is None):
                return True, "groupItemRange_dict_encodes_K_to_infinity", fields
        elif isinstance(parsed, list) and len(parsed) >= 2:
            glb = maybe_float(parsed[0])
            gub = maybe_float(parsed[1])
            if approx_equal(glb, Kf) and (field_has_infinity(parsed[1]) or gub is None):
                return True, "groupItemRange_list_encodes_K_to_infinity", fields
        elif isinstance(parsed, str):
            s = parsed.lower()
            # Examples: "[33, infinity)", "33+", ">=33"
            if re.search(rf"\[?\s*{K}(?:\.0)?\s*,\s*(?:inf|infinity|∞)", s):
                return True, "groupItemRange_string_encodes_K_to_infinity", fields
            if re.search(rf">=\s*{K}(?:\.0)?", s) or re.search(rf"{K}(?:\.0)?\s*\+", s):
                return True, "groupItemRange_string_encodes_ge_K", fields

    # groupItemThreshold alone is accepted only if exactly K and market/question is upper-tail.
    git = maybe_float(fields.get("groupItemThreshold"))
    q = str(market.get("question") or market.get("title") or market.get("slug") or "")
    is_upper_tail_label = parse_threshold_from_text(q) == K
    if approx_equal(git, Kf) and is_upper_tail_label:
        return True, "groupItemThreshold_equals_K_for_upper_tail_market", fields

    return False, "no_dedicated_boundary_metadata_certification", fields


def written_confirmation_certifies(text: str) -> Tuple[bool, str]:
    if not text.strip():
        return False, "no_written_confirmation_supplied"
    t = re.sub(r"\s+", " ", text.strip().lower())
    # Require semantic markers. This intentionally does not rely on a weak yes/no alone.
    has_upper = (
        "or higher" in t
        and ("at least" in t or ">=" in t or "greater than or equal" in t)
        and ("k.0" in t or "k °c" in t or "k°c" in t or "k degrees" in t)
    )
    has_interior = (
        ("interior" in t or "label" in t)
        and ("< k+1" in t or "less than k+1" in t or "k+1.0" in t or "[k" in t)
    )
    if has_upper and has_interior:
        return True, "written_confirmation_contains_upper_tail_and_interior_endpoint_convention"
    if has_upper:
        return True, "written_confirmation_contains_upper_tail_ge_K_convention"
    return False, "written_confirmation_text_present_but_not_machine_recognised_manual_review_needed"


def extract_rule_text(market: Dict[str, Any]) -> str:
    parts = []
    for k in ["question", "title", "description", "resolutionSource", "rules", "additionalInfo", "clarification"]:
        v = market.get(k)
        if v:
            parts.append(f"[{k}] {v}")
    return "\n".join(parts)


def is_strict_hko_family_text(text: str) -> bool:
    s = text.lower()
    return (
        "hong kong" in s
        and ("hko" in s or "hong kong observatory" in s)
        and "absolute daily max" in s
        and "daily extract" in s
        and ("one decimal" in s or "one-decimal" in s or "1 decimal" in s)
    )


def infer_market_date(row: pd.Series, market: Optional[Dict[str, Any]] = None) -> Optional[pd.Timestamp]:
    for c in ["date", "market_date", "event_date", "target_date"]:
        if c in row and not pd.isna(row[c]):
            dt = pd.to_datetime(row[c], errors="coerce")
            if not pd.isna(dt):
                return dt.normalize()
    texts = []
    for c in ["event_slug", "market_slug", "question", "title", "slug"]:
        if c in row and not pd.isna(row[c]):
            texts.append(str(row[c]))
    if market:
        texts += [str(market.get(k) or "") for k in ["question", "slug", "title", "description"]]
    text = " ".join(texts).lower()
    # Patterns: on-may-26-2026, May 26 2026
    m = re.search(r"(?:on[-\s])?(january|february|march|april|may|june|july|august|september|october|november|december)[-\s]+(\d{1,2})[-\s,]+(20\d{2})", text, flags=re.I)
    if m:
        return pd.to_datetime(f"{m.group(1)} {m.group(2)} {m.group(3)}", errors="coerce").normalize()
    return None


def list_historical_versions(resource_url: str, start: str, end: str) -> Any:
    params = {"url": resource_url, "start": start, "end": end}
    return request_json(f"{DATA_GOV_HK_HISTORY_BASE}/list-file-versions", params=params)


def get_historical_file(resource_url: str, time_value: str) -> str:
    params = {"url": resource_url, "time": time_value}
    return request_text(f"{DATA_GOV_HK_HISTORY_BASE}/get-file", params=params, follow_redirects=True)


def extract_version_times(resp: Any) -> List[str]:
    """Robustly extract version timestamps from data.gov.hk historical API response."""
    if isinstance(resp, list):
        items = resp
    elif isinstance(resp, dict):
        for key in ["timestamps", "versions", "files", "results", "data", "file_versions"]:
            if key in resp and isinstance(resp[key], list):
                items = resp[key]
                break
        else:
            items = []
            # Some APIs may store under arbitrary first list value.
            for v in resp.values():
                if isinstance(v, list):
                    items = v
                    break
    else:
        items = []
    times = []
    for item in items:
        if isinstance(item, str):
            times.append(item)
        elif isinstance(item, dict):
            for k in ["time", "timestamp", "version", "date", "archive_time", "last_modified"]:
                if k in item and item[k]:
                    times.append(str(item[k]))
                    break
    # Deduplicate while preserving order
    seen = set()
    out = []
    for t in times:
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def reconstruct_first_available_hko_value(date: pd.Timestamp, latest_value: Optional[float]) -> Dict[str, Any]:
    """Attempt to find the earliest historical HKO file version after date that contains the target date."""
    if pd.isna(date):
        return {"hko_archive_status": "missing_date"}

    start_dt = date
    end_dt = date + pd.Timedelta(days=10)
    start = start_dt.strftime("%Y%m%d")
    end = end_dt.strftime("%Y%m%d")

    try:
        versions_resp = list_historical_versions(HKO_DAILY_MAX_URL, start, end)
        (RAW_HKO_HISTORY_DIR / f"versions_{date.strftime('%Y%m%d')}.json").write_text(
            json.dumps(versions_resp, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        times = extract_version_times(versions_resp)
    except Exception as e:
        return {"hko_archive_status": "list_versions_failed", "hko_archive_error": str(e)}

    if not times:
        return {"hko_archive_status": "no_versions_returned", "hko_archive_versions_count": 0}

    target_date = date.normalize()
    attempts = []
    for t in times:
        try:
            text = get_historical_file(HKO_DAILY_MAX_URL, t)
            out_file = RAW_HKO_HISTORY_DIR / f"hko_daily_max_{date.strftime('%Y%m%d')}_version_{safe_filename(t)}.csv"
            out_file.write_text(text, encoding="utf-8")
            parsed = parse_hko_daily_max_csv(text)
            hit = parsed[parsed["date"].dt.normalize() == target_date]
            attempts.append({"time": t, "parsed_rows": int(len(parsed)), "contains_target": bool(not hit.empty)})
            if not hit.empty:
                val = float(hit.iloc[-1]["hko_tmax_C"])
                revised = None if latest_value is None else (abs(float(latest_value) - val) > 1e-9)
                return {
                    "hko_archive_status": "first_historical_version_found",
                    "hko_archive_versions_count": len(times),
                    "hko_first_available_version_time": t,
                    "hko_first_available_value": val,
                    "hko_latest_value": latest_value,
                    "hko_latest_differs_from_first": revised,
                    "hko_raw_file": str(out_file.relative_to(ROOT)),
                }
        except Exception as e:
            attempts.append({"time": t, "error": str(e)})
            continue
    return {
        "hko_archive_status": "versions_found_but_target_not_contained",
        "hko_archive_versions_count": len(times),
        "hko_archive_attempts": json.dumps(attempts[:10], ensure_ascii=False),
        "hko_latest_value": latest_value,
    }


def main() -> None:
    print("Repository root:", ROOT)
    hko_latest = get_latest_hko_daily_max()
    print("Latest HKO parsed rows:", len(hko_latest), hko_latest["date"].min(), hko_latest["date"].max())

    tail = load_17j_tail_rows()
    if tail.empty:
        raise RuntimeError("17j tail rows are empty.")

    # Standardise useful columns.
    records = []
    market_cache: Dict[str, Dict[str, Any]] = {}
    written_ok, written_reason = written_confirmation_certifies(POLYMARKET_RULE_CONFIRMATION_TEXT)
    print("Written confirmation route:", written_ok, written_reason)

    for idx, row in tail.iterrows():
        market_id = get_market_id(row)
        market = {}
        fetch_error = None
        if market_id:
            try:
                market = fetch_gamma_market(market_id)
                market_cache[market_id] = market
            except Exception as e:
                fetch_error = str(e)
        else:
            fetch_error = "missing_market_id_in_17j_input"

        combined_text = "\n".join([
            str(row.get(c, "")) for c in ["question", "market_question", "market_slug", "event_slug", "description", "resolutionSource"] if c in row
        ])
        if market:
            combined_text += "\n" + extract_rule_text(market)

        K = first_present(row, ["threshold_K", "K", "tail_threshold", "threshold"], None)
        K = maybe_float(K)
        if K is not None:
            K = int(round(K))
        if K is None:
            K = parse_threshold_from_text(combined_text)

        date = infer_market_date(row, market)
        hko_value_latest = None
        if date is not None:
            hit = hko_latest[hko_latest["date"].dt.normalize() == date]
            if not hit.empty:
                hko_value_latest = float(hit.iloc[-1]["hko_tmax_C"])

        metadata_ok = False
        metadata_reason = "market_not_fetched"
        boundary_fields = {}
        if market:
            metadata_ok, metadata_reason, boundary_fields = boundary_metadata_certifies(market, K)

        strict_hko = is_strict_hko_family_text(combined_text)
        label_K = parse_threshold_from_text(combined_text)
        upper_tail_label = label_K is not None

        resolved = first_present(row, ["resolved_outcome", "tail_resolved_outcome", "outcome", "result", "resolved_yes"], None)
        resolved_bool = coerce_bool(resolved)
        # If resolved_outcome is a label rather than bool, infer if it contains Yes/No.
        if resolved_bool is None and resolved is not None:
            rs = str(resolved).lower()
            if "yes" in rs:
                resolved_bool = True
            elif "no" in rs:
                resolved_bool = False

        expected = None
        parity = None
        if hko_value_latest is not None and K is not None:
            expected = bool(hko_value_latest >= K)
            if resolved_bool is not None:
                parity = bool(expected == resolved_bool)

        # Historical archive: attempt only if date exists. This can be slow but strict.
        hko_archive = reconstruct_first_available_hko_value(date, hko_value_latest) if date is not None else {"hko_archive_status": "missing_date"}

        # Certification decision.
        rule_certified_by_metadata = bool(ALLOW_METADATA_CERTIFICATION and metadata_ok)
        rule_certified_by_written = bool(ALLOW_WRITTEN_CONFIRMATION_CERTIFICATION and written_ok)
        rule_certified = rule_certified_by_metadata or rule_certified_by_written

        if not strict_hko or not upper_tail_label:
            status = "not_certified_descriptive_only"
            reason = "not_strict_hko_upper_tail_family"
        elif rule_certified:
            status = "formally_certified_threshold_contract"
            reason = ";".join([
                r for r in [
                    "dedicated_gamma_boundary_metadata" if rule_certified_by_metadata else "",
                    "written_polymarket_or_resolver_confirmation" if rule_certified_by_written else "",
                ] if r
            ])
        elif parity is True:
            status = "empirically_supported_pending_confirmation"
            reason = "strict_family_realised_parity_matches_but_no_formal_boundary_evidence"
        else:
            status = "not_certified_descriptive_only"
            reason = "insufficient_or_missing_parity_and_no_formal_boundary_evidence"

        record = {
            "row_index_17j": idx,
            "market_id": market_id,
            "event_slug": first_present(row, ["event_slug", "eventSlug"], None),
            "market_slug": first_present(row, ["market_slug", "slug", "marketSlug"], market.get("slug") if market else None),
            "question": first_present(row, ["question", "market_question"], market.get("question") if market else None),
            "threshold_K": K,
            "market_date": date.date().isoformat() if date is not None and not pd.isna(date) else None,
            "strict_hko_daily_extract_one_decimal_family": strict_hko,
            "upper_tail_label_detected": upper_tail_label,
            "resolved_outcome_raw": resolved,
            "resolved_outcome_bool": resolved_bool,
            "hko_latest_value": hko_value_latest,
            "expected_threshold_outcome_latest_hko": expected,
            "realised_parity_latest_hko": parity,
            "metadata_certifies_boundary": rule_certified_by_metadata,
            "metadata_certification_reason": metadata_reason,
            "written_confirmation_certifies_rule": rule_certified_by_written,
            "written_confirmation_reason": written_reason,
            "gamma_fetch_error": fetch_error,
            "raw_gamma_json_path": None,
            "final_certification_status": status,
            "final_certification_reason": reason,
            **{f"gamma_{k}": v for k, v in boundary_fields.items()},
            **hko_archive,
        }

        if market_id and market_id in market_cache:
            slug = safe_filename(market_cache[market_id].get("slug") or market_id)
            raw_path = RAW_GAMMA_DIR / f"market_{safe_filename(market_id)}_{slug}.json"
            record["raw_gamma_json_path"] = str(raw_path.relative_to(ROOT)) if raw_path.exists() else None

        records.append(record)

    dossier = pd.DataFrame(records)
    boundary_cols = [
        "market_id", "market_slug", "question", "threshold_K", "strict_hko_daily_extract_one_decimal_family",
        "metadata_certifies_boundary", "metadata_certification_reason", "gamma_lowerBound", "gamma_upperBound",
        "gamma_groupItemThreshold", "gamma_groupItemRange", "gamma_xAxisValue", "gamma_yAxisValue", "raw_gamma_json_path"
    ]
    boundary_audit = dossier[[c for c in boundary_cols if c in dossier.columns]].copy()
    hko_cols = [
        "market_id", "market_slug", "threshold_K", "market_date", "hko_archive_status", "hko_first_available_version_time",
        "hko_first_available_value", "hko_latest_value", "hko_latest_differs_from_first", "hko_raw_file",
        "resolved_outcome_bool", "expected_threshold_outcome_latest_hko", "realised_parity_latest_hko"
    ]
    hko_recon = dossier[[c for c in hko_cols if c in dossier.columns]].copy()
    decision_cols = [
        "market_id", "market_slug", "question", "market_date", "threshold_K",
        "final_certification_status", "final_certification_reason",
        "metadata_certifies_boundary", "metadata_certification_reason",
        "written_confirmation_certifies_rule", "written_confirmation_reason",
        "hko_archive_status", "realised_parity_latest_hko", "raw_gamma_json_path"
    ]
    decision = dossier[[c for c in decision_cols if c in dossier.columns]].copy()

    boundary_audit.to_csv(DATA_PROCESSED / "17k_polymarket_raw_metadata_boundary_audit.csv", index=False)
    hko_recon.to_csv(DATA_PROCESSED / "17k_hko_historical_archive_value_reconciliation.csv", index=False)
    dossier.to_csv(DATA_PROCESSED / "17k_hko_upper_tail_certification_dossier.csv", index=False)
    decision.to_csv(DATA_PROCESSED / "17k_hko_upper_tail_certification_decision.csv", index=False)

    counts = decision["final_certification_status"].value_counts(dropna=False).to_dict() if not decision.empty else {}
    report = []
    report.append("# 17k Hong Kong Upper-Tail Certification Dossier")
    report.append("")
    report.append("This report is produced by `17k_hko_upper_tail_certification_dossier.py`.")
    report.append("")
    report.append("## Certification rule")
    report.append("")
    report.append("A strict-family Hong Kong upper-tail market is classified as formally certified only if dedicated Gamma metadata explicitly encodes the threshold boundary, or if written Polymarket/resolver confirmation is supplied. The audit does not certify a market from its title label alone.")
    report.append("")
    report.append("## Status counts")
    report.append("")
    for k, v in counts.items():
        report.append(f"- `{k}`: {v}")
    report.append("")
    report.append("## Written confirmation route")
    report.append(f"- recognised: `{written_ok}`")
    report.append(f"- reason: `{written_reason}`")
    report.append("")
    report.append("## Output files")
    report.append("")
    for p in [
        "data/processed/17k_polymarket_raw_metadata_boundary_audit.csv",
        "data/processed/17k_hko_historical_archive_value_reconciliation.csv",
        "data/processed/17k_hko_upper_tail_certification_dossier.csv",
        "data/processed/17k_hko_upper_tail_certification_decision.csv",
    ]:
        report.append(f"- `{p}`")
    report.append("")
    report.append("## Thesis wording gate")
    report.append("")
    if counts.get("formally_certified_threshold_contract", 0) > 0:
        report.append("At least one strict-family upper-tail market has passed the formal certification gate. Use the final decision CSV to restrict the market-probability panel to certified rows only.")
    else:
        report.append("No market has yet passed the formal certification gate. The correct thesis wording remains `empirically supported pending confirmation`, not `formally certified threshold contract`.")

    (DOCS_OUT / "17k_hko_upper_tail_certification_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print("\nFinal certification counts:")
    print(decision["final_certification_status"].value_counts(dropna=False))
    print("\nWrote outputs to:")
    print(DATA_PROCESSED / "17k_hko_upper_tail_certification_decision.csv")
    print(DOCS_OUT / "17k_hko_upper_tail_certification_report.md")


if __name__ == "__main__":
    main()
