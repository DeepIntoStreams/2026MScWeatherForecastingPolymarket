
#!/usr/bin/env python3
"""
18a_hko_certified_upper_tail_price_panel.py

Build a market-price panel for the formally certified Hong Kong upper-tail
Polymarket contracts identified in 17l.

Input:
  data/processed/17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv

Outputs:
  data/raw/polymarket_clob_price_history_18a/*.json
  data/processed/18a_hko_certified_upper_tail_market_price_panel.csv
  data/processed/18a_hko_certified_upper_tail_price_coverage_summary.csv
  docs/research_outputs/18a_hko_certified_upper_tail_price_panel_report.md

Important interpretation:
  The CLOB /prices-history endpoint returns historical price observations for
  a token. These are used as market-implied probability observations for
  empirical comparison. They are not, by themselves, a guaranteed executable
  bid/ask trading series.
"""

from __future__ import annotations

import ast
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

CLOB_BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"

INPUT_PATH = "data/processed/17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv"
OUT_PRICE_PANEL = "data/processed/18a_hko_certified_upper_tail_market_price_panel.csv"
OUT_COVERAGE = "data/processed/18a_hko_certified_upper_tail_price_coverage_summary.csv"
OUT_REPORT = "docs/research_outputs/18a_hko_certified_upper_tail_price_panel_report.md"
RAW_PRICE_DIR = "data/raw/polymarket_clob_price_history_18a"
RAW_GAMMA_DIR = "data/raw/polymarket_gamma_market_refetch_18a"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "UCL-MSc-dissertation-weather-polymarket/18a academic research",
})


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Find repository root by walking up to .git."""
    start = (start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return start


REPO = find_repo_root()
DATA_PROCESSED = REPO / "data" / "processed"
RAW_PRICE_PATH = REPO / RAW_PRICE_DIR
RAW_GAMMA_PATH = REPO / RAW_GAMMA_DIR
REPORT_PATH = REPO / "docs" / "research_outputs"

for p in [DATA_PROCESSED, RAW_PRICE_PATH, RAW_GAMMA_PATH, REPORT_PATH]:
    p.mkdir(parents=True, exist_ok=True)


def safe_slug(x: Any) -> str:
    s = str(x) if pd.notna(x) else "missing"
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")
    return s[:180] or "missing"


def parse_jsonish(value: Any) -> Any:
    """Parse JSON/Python-list-like strings robustly."""
    if value is None:
        return None
    if isinstance(value, (list, dict, tuple)):
        return value
    if isinstance(value, float) and math.isnan(value):
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    try:
        return ast.literal_eval(s)
    except Exception:
        pass
    # Sometimes token IDs are comma-separated.
    if "," in s and not s.startswith("http"):
        return [x.strip().strip("'\"") for x in s.split(",") if x.strip()]
    return s


def as_list(value: Any) -> List[Any]:
    parsed = parse_jsonish(value)
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, tuple):
        return list(parsed)
    return [parsed]


def norm_outcome(x: Any) -> str:
    return str(x).strip().lower()


def load_raw_json_path(row: pd.Series, col: str) -> Optional[Dict[str, Any]]:
    if col not in row or pd.isna(row[col]):
        return None
    p = Path(str(row[col]))
    if not p.is_absolute():
        p = REPO / p
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def gamma_get_market(market_id: Any = None, market_slug: Any = None) -> Optional[Dict[str, Any]]:
    """Best-effort Gamma market refetch.

    Gamma endpoint conventions can vary. We therefore try direct market ID
    and query-filter forms. The 18a panel does not depend on this if the 17l
    file already contains clobTokenIds or raw JSON paths.
    """
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    if pd.notna(market_id):
        mid = str(market_id)
        candidates.append((f"/markets/{mid}", {}))
        candidates.append(("/markets", {"id": mid}))
    if pd.notna(market_slug):
        slug = str(market_slug)
        candidates.append(("/markets", {"slug": slug}))

    for path, params in candidates:
        try:
            r = SESSION.get(f"{GAMMA_BASE}{path}", params=params, timeout=30)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data:
                return data[0]
            if isinstance(data, dict):
                if "markets" in data and isinstance(data["markets"], list) and data["markets"]:
                    return data["markets"][0]
                if "data" in data and isinstance(data["data"], list) and data["data"]:
                    return data["data"][0]
                return data
        except Exception:
            continue
    return None


def extract_yes_token_from_object(obj: Dict[str, Any]) -> Tuple[Optional[str], str, Dict[str, Any]]:
    """Extract YES token ID from a Gamma market object or simplified market-like object."""
    if not isinstance(obj, dict):
        return None, "not_dict", {}

    debug: Dict[str, Any] = {}

    # Common Gamma fields: outcomes + clobTokenIds as JSON strings/lists.
    outcome_values = []
    for key in ["outcomes", "outcomeLabels", "outcome_labels"]:
        if key in obj:
            outcome_values = as_list(obj.get(key))
            if outcome_values:
                debug["outcomes_source"] = key
                break

    token_values = []
    for key in ["clobTokenIds", "clob_token_ids", "tokenIds", "token_ids"]:
        if key in obj:
            token_values = as_list(obj.get(key))
            if token_values:
                debug["tokens_source"] = key
                break

    if outcome_values and token_values and len(outcome_values) == len(token_values):
        for out, tok in zip(outcome_values, token_values):
            if norm_outcome(out) == "yes":
                return str(tok), "matched_outcomes_to_clobTokenIds", debug
        # Binary markets normally have Yes first. Do not use this unless outcome names are obvious.
        if len(token_values) == 2 and {norm_outcome(x) for x in outcome_values} == {"yes", "no"}:
            idx = [norm_outcome(x) for x in outcome_values].index("yes")
            return str(token_values[idx]), "matched_binary_yes_no", debug

    # CLOB simplified market style: tokens is a list of dicts.
    for key in ["tokens", "market_tokens"]:
        toks = obj.get(key)
        if isinstance(toks, list):
            for t in toks:
                if isinstance(t, dict) and norm_outcome(t.get("outcome")) == "yes":
                    token = t.get("token_id") or t.get("asset_id") or t.get("id")
                    if token:
                        return str(token), f"matched_{key}_yes", {**debug, "tokens_source": key}

    # Fallback: if exactly two token values exist and no outcome labels are available, assume first is YES.
    # We keep the extraction method explicit so this can be audited later.
    if len(token_values) == 2 and not outcome_values:
        return str(token_values[0]), "fallback_first_of_two_tokens_no_outcome_labels", debug

    return None, "no_yes_token_identified", debug


def extract_yes_token(row: pd.Series) -> Tuple[Optional[str], str, Dict[str, Any]]:
    """Try all available evidence to identify the YES token ID."""
    # Direct row fields first.
    row_obj = row.to_dict()
    token, method, debug = extract_yes_token_from_object(row_obj)
    if token:
        return token, f"row_{method}", debug

    # Raw market JSON from 17l.
    raw = load_raw_json_path(row, "raw_market_json_path")
    if raw:
        token, method, debug = extract_yes_token_from_object(raw)
        if token:
            return token, f"raw_market_json_{method}", debug

    # Gamma refetch if needed.
    fetched = gamma_get_market(row.get("market_id"), row.get("market_slug"))
    if fetched:
        raw_name = safe_slug(row.get("market_slug") or row.get("market_id")) + ".json"
        raw_path = RAW_GAMMA_PATH / raw_name
        raw_path.write_text(json.dumps(fetched, indent=2, sort_keys=True), encoding="utf-8")
        token, method, debug = extract_yes_token_from_object(fetched)
        if token:
            return token, f"gamma_refetch_{method}", {**debug, "gamma_refetch_path": str(raw_path.relative_to(REPO))}

    return None, "failed_all_token_extraction_routes", {}


def parse_timestamp(x: Any) -> Optional[pd.Timestamp]:
    if x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x):
        return None
    try:
        ts = pd.to_datetime(x, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts
    except Exception:
        return None


def event_window(row: pd.Series) -> Tuple[Optional[int], Optional[int], str]:
    """Choose a broad but finite retrieval window.

    Price history endpoint can be called without start/end. However, a bounded
    window is gentler and easier to audit. We use createdAt when available;
    otherwise event_date minus 10 days. End is max(closedTime/endDate/event_date+2d).
    """
    start_candidates = [
        parse_timestamp(row.get("createdAt")),
        parse_timestamp(row.get("created_at")),
    ]
    end_candidates = [
        parse_timestamp(row.get("closedTime")),
        parse_timestamp(row.get("closed_time")),
        parse_timestamp(row.get("endDate")),
        parse_timestamp(row.get("end_date")),
    ]
    event_date = parse_timestamp(row.get("event_date"))
    if event_date is not None:
        event_start = event_date - pd.Timedelta(days=10)
        event_end = event_date + pd.Timedelta(days=3)
        start_candidates.append(event_start)
        end_candidates.append(event_end)

    starts = [x for x in start_candidates if x is not None]
    ends = [x for x in end_candidates if x is not None]

    start = min(starts) if starts else None
    end = max(ends) if ends else None

    if start is not None and end is not None and start >= end:
        end = start + pd.Timedelta(days=14)

    note = "bounded_by_created_or_event_date"
    return (
        int(start.timestamp()) if start is not None else None,
        int(end.timestamp()) if end is not None else None,
        note,
    )


def clob_prices_history(token_id: str, start_ts: Optional[int], end_ts: Optional[int], fidelity: int = 1) -> Dict[str, Any]:
    """Retrieve CLOB price history with retries.

    The public endpoint returns a JSON object with a history array of {t, p}.
    """
    attempts = []
    # Preferred bounded all interval.
    params: Dict[str, Any] = {"market": token_id, "interval": "all", "fidelity": fidelity}
    if start_ts is not None:
        params["startTs"] = int(start_ts)
    if end_ts is not None:
        params["endTs"] = int(end_ts)
    attempts.append(params)

    # Fallback without interval.
    params2: Dict[str, Any] = {"market": token_id, "fidelity": fidelity}
    if start_ts is not None:
        params2["startTs"] = int(start_ts)
    if end_ts is not None:
        params2["endTs"] = int(end_ts)
    attempts.append(params2)

    # Last fallback unbounded all.
    attempts.append({"market": token_id, "interval": "all", "fidelity": fidelity})

    last_error: Optional[str] = None
    for params in attempts:
        for attempt in range(4):
            try:
                r = SESSION.get(f"{CLOB_BASE}/prices-history", params=params, timeout=45)
                if r.status_code in {429, 502, 503, 504}:
                    time.sleep(2.0 + attempt * 2.0)
                    continue
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, dict):
                    data = {"history": data}
                data["_request_params"] = params
                return data
            except Exception as e:
                last_error = repr(e)
                time.sleep(1.0 + attempt * 1.5)
    return {"history": [], "_error": last_error, "_request_params": attempts[-1]}


def main() -> None:
    input_path = REPO / INPUT_PATH
    if not input_path.exists():
        raise SystemExit(f"Missing certified universe input: {input_path}")

    universe = pd.read_csv(input_path)
    if universe.empty:
        raise SystemExit("Certified universe is empty. Stop before querying price history.")

    print("Repository root:", REPO)
    print("Certified universe input:", input_path)
    print("Certified universe shape:", universe.shape)

    all_price_rows: List[Dict[str, Any]] = []
    coverage_rows: List[Dict[str, Any]] = []

    for i, row in universe.iterrows():
        event_slug = str(row.get("event_slug", f"row{i}"))
        market_slug = str(row.get("market_slug", f"market{i}"))
        threshold = row.get("threshold_K")
        contract_id = row.get("certified_contract_id") or f"{event_slug}__K{threshold}"

        print(f"\n[{i+1}/{len(universe)}] {contract_id}")
        yes_token, token_method, token_debug = extract_yes_token(row)
        print("YES token method:", token_method)
        print("YES token:", yes_token)

        coverage = {
            "event_date": row.get("event_date"),
            "threshold_K": threshold,
            "event_slug": event_slug,
            "market_slug": market_slug,
            "market_id": row.get("market_id"),
            "certified_contract_id": contract_id,
            "final_certification_status": row.get("final_certification_status"),
            "yes_token_id": yes_token,
            "yes_token_extraction_method": token_method,
            "yes_token_extraction_debug": json.dumps(token_debug, sort_keys=True),
            "price_history_status": None,
            "price_history_count": 0,
            "first_price_timestamp_utc": None,
            "last_price_timestamp_utc": None,
            "price_history_error": None,
            "raw_price_history_path": None,
            "window_start_ts": None,
            "window_end_ts": None,
            "window_note": None,
        }

        if not yes_token:
            coverage["price_history_status"] = "no_yes_token"
            coverage_rows.append(coverage)
            continue

        start_ts, end_ts, window_note = event_window(row)
        coverage["window_start_ts"] = start_ts
        coverage["window_end_ts"] = end_ts
        coverage["window_note"] = window_note

        data = clob_prices_history(yes_token, start_ts, end_ts, fidelity=1)
        raw_name = f"{safe_slug(contract_id)}__{safe_slug(yes_token)}.json"
        raw_path = RAW_PRICE_PATH / raw_name
        raw_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        coverage["raw_price_history_path"] = str(raw_path.relative_to(REPO))

        hist = data.get("history") or []
        if not isinstance(hist, list):
            hist = []

        if data.get("_error"):
            coverage["price_history_error"] = data.get("_error")

        if not hist:
            coverage["price_history_status"] = "empty_history" if not data.get("_error") else "error_or_empty_history"
            coverage_rows.append(coverage)
            print("Price history: 0 rows")
            time.sleep(0.4)
            continue

        for h in hist:
            if not isinstance(h, dict):
                continue
            t = h.get("t")
            p = h.get("p")
            try:
                timestamp = pd.to_datetime(int(float(t)), unit="s", utc=True)
            except Exception:
                timestamp = pd.NaT
            try:
                price = float(p)
            except Exception:
                price = math.nan

            all_price_rows.append({
                "event_date": row.get("event_date"),
                "threshold_K": threshold,
                "event_slug": event_slug,
                "market_slug": market_slug,
                "market_id": row.get("market_id"),
                "market_question": row.get("market_question"),
                "market_title": row.get("market_title"),
                "outcome_label_text": row.get("outcome_label_text"),
                "certified_contract_id": contract_id,
                "final_certification_status": row.get("final_certification_status"),
                "certification_reason": row.get("certification_reason"),
                "yes_token_id": yes_token,
                "yes_token_extraction_method": token_method,
                "price_timestamp_unix": t,
                "price_timestamp_utc": timestamp.isoformat() if not pd.isna(timestamp) else None,
                "yes_price": price,
                "raw_history_point": json.dumps(h, sort_keys=True),
                "raw_price_history_path": str(raw_path.relative_to(REPO)),
                "volume": row.get("volume"),
                "liquidity": row.get("liquidity"),
                "closed": row.get("closed"),
                "active": row.get("active"),
                "createdAt": row.get("createdAt"),
                "endDate": row.get("endDate"),
                "resolutionSource": row.get("resolutionSource"),
            })

        coverage["price_history_status"] = "ok"
        coverage["price_history_count"] = len(hist)
        ts_values = [r["price_timestamp_utc"] for r in all_price_rows if r["certified_contract_id"] == contract_id and r["price_timestamp_utc"]]
        if ts_values:
            coverage["first_price_timestamp_utc"] = min(ts_values)
            coverage["last_price_timestamp_utc"] = max(ts_values)
        coverage_rows.append(coverage)
        print("Price history rows:", len(hist))
        time.sleep(0.6)

    price_panel = pd.DataFrame(all_price_rows)
    coverage_df = pd.DataFrame(coverage_rows)

    if not price_panel.empty:
        price_panel["price_timestamp_utc"] = pd.to_datetime(price_panel["price_timestamp_utc"], utc=True, errors="coerce")
        price_panel = price_panel.sort_values([
            "event_date", "threshold_K", "certified_contract_id", "price_timestamp_utc"
        ]).reset_index(drop=True)
        # Keep valid probability-like prices only; preserve invalid rows nowhere.
        price_panel = price_panel[price_panel["yes_price"].between(0, 1, inclusive="both")].reset_index(drop=True)

    out_panel = REPO / OUT_PRICE_PANEL
    out_cov = REPO / OUT_COVERAGE
    price_panel.to_csv(out_panel, index=False)
    coverage_df.to_csv(out_cov, index=False)

    # Markdown report.
    report_lines = []
    report_lines.append("# 18a Hong Kong certified upper-tail market price panel")
    report_lines.append("")
    report_lines.append(f"Run time UTC: {datetime.now(timezone.utc).isoformat()}")
    report_lines.append("")
    report_lines.append("## Inputs")
    report_lines.append(f"- Certified universe: `{INPUT_PATH}`")
    report_lines.append(f"- Number of certified contracts: {len(universe)}")
    report_lines.append("")
    report_lines.append("## Outputs")
    report_lines.append(f"- Price panel: `{OUT_PRICE_PANEL}`")
    report_lines.append(f"- Coverage summary: `{OUT_COVERAGE}`")
    report_lines.append(f"- Raw CLOB history JSON directory: `{RAW_PRICE_DIR}`")
    report_lines.append("")
    report_lines.append("## Coverage")
    if not coverage_df.empty:
        report_lines.append(coverage_df["price_history_status"].value_counts(dropna=False).to_string())
    else:
        report_lines.append("No coverage rows produced.")
    report_lines.append("")
    report_lines.append("## Interpretation note")
    report_lines.append(
        "The CLOB price-history observations are used as market-implied probability observations "
        "for empirical comparison. They should not be described as a fully executable trading "
        "series unless a separate bid/ask and liquidity execution audit is performed."
    )
    report_lines.append("")
    if not price_panel.empty:
        report_lines.append("## Panel summary")
        report_lines.append(f"- Price rows: {len(price_panel)}")
        report_lines.append(f"- Unique contracts with prices: {price_panel['certified_contract_id'].nunique()}")
        report_lines.append(f"- First timestamp: {price_panel['price_timestamp_utc'].min()}")
        report_lines.append(f"- Last timestamp: {price_panel['price_timestamp_utc'].max()}")
    else:
        report_lines.append("## Panel summary")
        report_lines.append("No price rows were retrieved.")

    report_path = REPO / OUT_REPORT
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\nSaved price panel:", out_panel)
    print("Price panel shape:", price_panel.shape)
    print("Saved coverage summary:", out_cov)
    print("Coverage shape:", coverage_df.shape)
    print("Saved report:", report_path)
    print("\nCoverage counts:")
    if not coverage_df.empty:
        print(coverage_df["price_history_status"].value_counts(dropna=False))
    if not price_panel.empty:
        print("\nPrice rows by contract:")
        print(price_panel.groupby(["event_date", "threshold_K", "certified_contract_id"]).size())


if __name__ == "__main__":
    main()
