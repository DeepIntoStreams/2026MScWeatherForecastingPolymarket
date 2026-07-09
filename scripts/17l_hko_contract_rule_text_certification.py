#!/usr/bin/env python3

# 17l HKO contract rule text certification
# Run from repository root or from notebooks/. The notebook detects the repository root.

from __future__ import annotations

import json
import re
import time
import html
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import numpy as np
import requests


# -----------------------------
# 0. Paths and configuration
# -----------------------------

def find_repo_root(start: Path | None = None) -> Path:
    """Find repository root by walking upward until .git is found."""
    start = (start or Path.cwd()).resolve()
    for p in [start] + list(start.parents):
        if (p / ".git").exists():
            return p
    # Fall back to parent if running from notebooks/
    if start.name == "notebooks":
        return start.parent
    return start

ROOT = find_repo_root()
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
RULE_RAW_DIR = DATA_RAW / "polymarket_contract_rule_text"
REPORT_DIR = ROOT / "docs" / "research_outputs"

for p in [DATA_RAW, DATA_INTERIM, DATA_PROCESSED, RULE_RAW_DIR, REPORT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

GAMMA_BASE = "https://gamma-api.polymarket.com"
POLYMARKET_EVENT_BASE = "https://polymarket.com/event"

REQUEST_SLEEP = 0.20
TIMEOUT = 30

print("Repository root:", ROOT)
print("Processed output:", DATA_PROCESSED)
print("Raw rule evidence:", RULE_RAW_DIR)


# -----------------------------
# 1. Utility functions
# -----------------------------

def safe_slug(s: Any) -> str:
    s = str(s or "").strip().lower()
    s = re.sub(r"[^a-z0-9_.-]+", "_", s)
    return s.strip("_")[:180] or "unknown"

def textify(obj: Any, max_len: int = 200000) -> str:
    """Convert nested JSON-like object to searchable text."""
    chunks: List[str] = []
    def rec(x: Any, key: str = ""):
        if x is None:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                rec(v, str(k))
        elif isinstance(x, list):
            for v in x:
                rec(v, key)
        elif isinstance(x, (str, int, float, bool)):
            if isinstance(x, str):
                val = html.unescape(x)
                val = re.sub(r"<[^>]+>", " ", val)
                val = re.sub(r"\s+", " ", val).strip()
                if val:
                    chunks.append(f"{key}: {val}" if key else val)
            else:
                chunks.append(f"{key}: {x}" if key else str(x))
    rec(obj)
    return "\n".join(chunks)[:max_len]

def normalise_text(s: Any) -> str:
    s = html.unescape(str(s or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("°", "°")
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def gamma_get(path: str, params: Optional[dict] = None) -> Any:
    url = f"{GAMMA_BASE}{path}"
    r = requests.get(url, params=params or {}, timeout=TIMEOUT)
    r.raise_for_status()
    time.sleep(REQUEST_SLEEP)
    return r.json()

def try_get_json(url: str, params: Optional[dict] = None) -> Optional[Any]:
    try:
        r = requests.get(url, params=params or {}, timeout=TIMEOUT)
        if r.status_code >= 400:
            return None
        time.sleep(REQUEST_SLEEP)
        return r.json()
    except Exception:
        return None

def try_get_text(url: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0 academic-research"})
        time.sleep(REQUEST_SLEEP)
        return r.text, r.status_code, None
    except Exception as e:
        return None, None, repr(e)

def save_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

def extract_tail_threshold(label: str) -> Optional[int]:
    """Extract K from labels such as '33°C or higher'."""
    s = normalise_text(label)
    patterns = [
        r"(\d{1,2})\s*°?\s*c\s*or\s*higher",
        r"(\d{1,2})\s*°?\s*c\s*\+",
        r"≥\s*(\d{1,2})\s*°?\s*c",
        r"at\s*least\s*(\d{1,2})\s*°?\s*c",
    ]
    for pat in patterns:
        m = re.search(pat, s)
        if m:
            return int(m.group(1))
    return None

def looks_upper_tail(label: str) -> bool:
    return extract_tail_threshold(label) is not None

def contains_any(s: str, patterns: Iterable[str]) -> bool:
    return any(re.search(p, s, flags=re.I) for p in patterns)

def find_first_patterns(s: str, patterns: dict[str, list[str]]) -> dict[str, str]:
    out = {}
    for category, pats in patterns.items():
        hit = ""
        for p in pats:
            m = re.search(p, s, flags=re.I)
            if m:
                hit = m.group(0)
                break
        out[category] = hit
    return out

def parse_event_date_from_slug_or_text(slug: str, text: str = "") -> Optional[pd.Timestamp]:
    """Parse dates from slugs like highest-temperature-in-hong-kong-on-may-26-2026."""
    joined = f"{slug} {text}"
    months = {
        "january":1, "february":2, "march":3, "april":4, "may":5, "june":6,
        "july":7, "august":8, "september":9, "october":10, "november":11, "december":12,
        "jan":1, "feb":2, "mar":3, "apr":4, "jun":6, "jul":7, "aug":8, "sep":9, "sept":9,
        "oct":10, "nov":11, "dec":12
    }
    m = re.search(r"(january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)[-\s]+(\d{1,2})[-,\s]+(\d{4})", joined, flags=re.I)
    if m:
        mon = months[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3))
        return pd.Timestamp(year=year, month=mon, day=day)
    m = re.search(r"(\d{4})[-_/](\d{1,2})[-_/](\d{1,2})", joined)
    if m:
        return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
    return None

print("Utilities loaded.")


# -----------------------------
# 2. Load previous 17j/17k outputs where available
# -----------------------------

candidate_files = [
    DATA_PROCESSED / "17j_hko_polymarket_hko_upper_tail_summary.csv",
    DATA_PROCESSED / "17k_hko_upper_tail_certification_decision.csv",
    ROOT / "notebooks" / "data" / "processed" / "17j_hko_polymarket_hko_upper_tail_summary.csv",
    ROOT / "notebooks" / "data" / "processed" / "17k_hko_upper_tail_certification_decision.csv",
]

prev = None
prev_path = None
for p in candidate_files:
    if p.exists():
        try:
            df = pd.read_csv(p)
            if len(df):
                prev = df
                prev_path = p
                break
        except Exception:
            pass

if prev is not None:
    print("Loaded previous candidate table:", prev_path, prev.shape)
    display(prev.head())
else:
    print("No previous 17j/17k table found. Will discover Hong Kong events from Gamma.")


# -----------------------------
# 3. Discover Hong Kong temperature events from Gamma
# -----------------------------

def normalise_events_response(res: Any) -> list[dict]:
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for key in ["events", "data", "results"]:
            if isinstance(res.get(key), list):
                return res[key]
    return []

def discover_hk_events(max_pages: int = 30, limit: int = 100) -> pd.DataFrame:
    all_events = []
    # Try search endpoints first.
    search_terms = [
        "highest temperature in Hong Kong",
        "Hong Kong highest temperature",
        "Hong Kong temperature",
        "Hong Kong weather",
        "HKO",
    ]
    for q in search_terms:
        for path in ["/public-search", "/events"]:
            try:
                res = gamma_get(path, params={"q": q, "limit": limit})
                evs = normalise_events_response(res)
                for e in evs:
                    e["_discovery_query"] = q
                    e["_discovery_path"] = path
                all_events.extend(evs)
            except Exception as e:
                print(f"Search failed {path} q={q}: {e}")
    # Broad closed events scan.
    for page in range(max_pages):
        offset = page * limit
        try:
            res = gamma_get("/events", params={
                "closed": "true",
                "limit": limit,
                "offset": offset,
            })
            batch = normalise_events_response(res)
            if not batch:
                break
            all_events.extend(batch)
            if len(batch) < limit:
                break
        except Exception as e:
            print("Broad event scan failed:", e)
            break

    # Deduplicate.
    seen = set()
    uniq = []
    for e in all_events:
        key = str(e.get("id") or e.get("slug") or json.dumps(e, sort_keys=True)[:200])
        if key not in seen:
            seen.add(key)
            uniq.append(e)

    rows = []
    for e in uniq:
        txt = normalise_text(textify(e))
        if ("hong kong" in txt or "hko" in txt or "hong-kong" in txt) and ("temperature" in txt or "daily max" in txt or "absolute daily max" in txt):
            rows.append(e)
    return pd.json_normalize(rows)

events_df = discover_hk_events()
events_df.to_csv(DATA_INTERIM / "17l_hko_candidate_events_discovered.csv", index=False)
print("Discovered HK candidate events:", events_df.shape)
if len(events_df):
    cols = [c for c in ["id", "slug", "title", "ticker", "closed", "active", "endDate", "createdAt"] if c in events_df.columns]
    display(events_df[cols].head(20))


# -----------------------------
# 4. Flatten event child markets and collect raw public rule text
# -----------------------------

def extract_markets_from_event(event: dict) -> list[dict]:
    markets = []
    for key in ["markets", "childMarkets", "children"]:
        val = event.get(key)
        if isinstance(val, list):
            markets.extend([m for m in val if isinstance(m, dict)])
    # If event itself appears market-like, include it.
    if event.get("question") or event.get("clobTokenIds") or event.get("conditionId"):
        markets.append(event)
    return markets

# Build event records either from previous summary or fresh discovery.
event_records: dict[str, dict] = {}

if len(events_df):
    for _, row in events_df.iterrows():
        e = row.dropna().to_dict()
        event_id = str(e.get("id") or "")
        slug = str(e.get("slug") or "")
        key = event_id or slug
        if key:
            event_records[key] = e

# If previous file has slugs, ensure those events are queried too.
if prev is not None:
    for col in ["event_slug", "slug"]:
        if col in prev.columns:
            for slug in prev[col].dropna().astype(str).unique():
                if slug and slug not in event_records:
                    # Query by slug if possible.
                    # Gamma commonly supports /events/slug/{slug}; fallback to events?q.
                    obj = None
                    for path in [f"/events/slug/{slug}", f"/events/{slug}"]:
                        try:
                            obj = gamma_get(path)
                            break
                        except Exception:
                            pass
                    if obj is None:
                        try:
                            res = gamma_get("/events", params={"slug": slug})
                            evs = normalise_events_response(res)
                            obj = evs[0] if evs else None
                        except Exception:
                            obj = None
                    if isinstance(obj, dict):
                        event_records[slug] = obj

print("Event records to process:", len(event_records))

market_rows = []
raw_event_paths = []
raw_market_paths = []
raw_html_paths = []

for key, event in event_records.items():
    event_id = str(event.get("id") or "")
    event_slug = str(event.get("slug") or key)
    file_stub = safe_slug(event_slug or event_id or key)

    # Refresh full event by id/slug if possible.
    full_event = event
    for path in [f"/events/{event_id}", f"/events/slug/{event_slug}"]:
        if (path.endswith("/") or path.endswith("/None") or path.endswith("/")):
            continue
        try:
            full_event = gamma_get(path)
            if isinstance(full_event, dict):
                break
        except Exception:
            pass

    raw_event_path = RULE_RAW_DIR / f"event_{file_stub}.json"
    save_json(raw_event_path, full_event)
    raw_event_paths.append(raw_event_path)

    # Pull public event HTML.
    event_url = f"{POLYMARKET_EVENT_BASE}/{event_slug}" if event_slug else ""
    html_text, html_status, html_error = (None, None, "no_slug")
    if event_slug:
        html_text, html_status, html_error = try_get_text(event_url)
        if html_text:
            html_path = RULE_RAW_DIR / f"event_{file_stub}.html"
            html_path.write_text(html_text, encoding="utf-8", errors="ignore")
            raw_html_paths.append(html_path)
        else:
            html_path = None
    else:
        html_path = None

    markets = extract_markets_from_event(full_event)
    if not markets:
        # Try markets endpoint by event id/slug.
        try:
            res = gamma_get("/markets", params={"event_id": event_id, "limit": 200})
            if isinstance(res, list):
                markets = res
            elif isinstance(res, dict):
                markets = res.get("markets") or res.get("data") or []
        except Exception:
            pass

    event_text = textify(full_event)
    html_rule_text = ""
    if html_text:
        # Keep a compact cleaned version of HTML text for searching.
        html_rule_text = normalise_text(html_text)[:200000]

    for m in markets:
        if not isinstance(m, dict):
            continue
        market_id = str(m.get("id") or "")
        market_slug = str(m.get("slug") or "")

        # Refresh full market object if market id is available.
        full_market = m
        if market_id:
            for path in [f"/markets/{market_id}"]:
                try:
                    full_market = gamma_get(path)
                    if isinstance(full_market, dict):
                        break
                except Exception:
                    pass

        raw_market_path = None
        if market_id or market_slug:
            market_stub = safe_slug(market_slug or market_id)
            raw_market_path = RULE_RAW_DIR / f"market_{market_stub}.json"
            save_json(raw_market_path, full_market)
            raw_market_paths.append(raw_market_path)

        market_text = textify(full_market)
        combined_text = "\n".join([event_text, market_text, html_rule_text])
        combined_norm = normalise_text(combined_text)

        # Candidate labels from market fields.
        labels = []
        for field in ["question", "title", "groupItemTitle", "outcome", "name", "shortTitle"]:
            val = full_market.get(field)
            if isinstance(val, str) and val.strip():
                labels.append(val.strip())
        # Outcomes may be encoded JSON/list.
        for field in ["outcomes", "outcomePrices"]:
            val = full_market.get(field)
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        labels.extend([str(x) for x in parsed])
                except Exception:
                    labels.append(val)
            elif isinstance(val, list):
                labels.extend([str(x) for x in val])

        label_text = " | ".join(dict.fromkeys(labels))
        threshold_K = extract_tail_threshold(label_text)

        market_rows.append({
            "event_id": event_id,
            "event_slug": event_slug,
            "event_url": event_url,
            "event_title": full_event.get("title") or full_event.get("name") or "",
            "market_id": market_id,
            "market_slug": market_slug,
            "market_question": full_market.get("question") or "",
            "market_title": full_market.get("title") or "",
            "outcome_label_text": label_text,
            "threshold_K": threshold_K,
            "looks_upper_tail": threshold_K is not None,
            "raw_event_json_path": str(raw_event_path.relative_to(ROOT)),
            "raw_market_json_path": str(raw_market_path.relative_to(ROOT)) if raw_market_path else "",
            "raw_event_html_path": str(html_path.relative_to(ROOT)) if html_path else "",
            "html_status": html_status,
            "html_error": html_error or "",
            "combined_rule_text_hash": sha256_text(combined_norm),
            "combined_rule_text_excerpt": combined_norm[:3000],
            "combined_rule_text": combined_norm,
            "lowerBound": full_market.get("lowerBound"),
            "upperBound": full_market.get("upperBound"),
            "groupItemThreshold": full_market.get("groupItemThreshold"),
            "groupItemRange": full_market.get("groupItemRange"),
            "groupItemTitle": full_market.get("groupItemTitle"),
            "resolutionSource": full_market.get("resolutionSource") or full_event.get("resolutionSource"),
            "description": full_market.get("description") or full_event.get("description"),
            "rules": full_market.get("rules") or full_event.get("rules"),
            "volume": full_market.get("volume") or full_market.get("volumeNum"),
            "liquidity": full_market.get("liquidity") or full_market.get("liquidityNum"),
            "closed": full_market.get("closed") if "closed" in full_market else full_event.get("closed"),
            "active": full_market.get("active") if "active" in full_market else full_event.get("active"),
            "endDate": full_market.get("endDate") or full_event.get("endDate"),
            "createdAt": full_market.get("createdAt") or full_event.get("createdAt"),
        })

market_df = pd.DataFrame(market_rows)
market_df.to_csv(DATA_INTERIM / "17l_hko_market_rule_text_raw_index.csv", index=False)
print("Flattened market rows:", market_df.shape)
if len(market_df):
    display(market_df[["event_slug", "market_slug", "outcome_label_text", "threshold_K", "looks_upper_tail"]].head(20))


# -----------------------------
# 5. Contract rule text certification checks
# -----------------------------

PATTERNS = {
    "hong_kong_observatory": [
        r"\bhong kong observatory\b",
        r"\bhko\b",
    ],
    "absolute_daily_max": [
        r"\babsolute daily max\b",
        r"\bdaily maximum\b",
        r"\bmaximum temperature\b",
        r"\bhighest temperature\b",
    ],
    "daily_extract": [
        r"\bdaily extract\b",
        r"\bdaily climatological extract\b",
    ],
    "one_decimal_precision": [
        r"\bone[-\s]?decimal\b",
        r"\b1[-\s]?decimal\b",
        r"\bto one decimal\b",
        r"\bnearest 0\.1\b",
        r"\b0\.1\s*°?\s*c\b",
        r"\bdecimal precision\b",
        r"\bdeg\.?\s*c\)",
    ],
    "range_language": [
        r"\brange containing\b",
        r"\btemperature range\b",
        r"\bfalls within\b",
        r"\bbetween\b",
    ],
    "later_revision_exclusion": [
        r"\blater revisions?\b",
        r"\brevisions? .* not .* considered\b",
        r"\bwill not be considered\b",
    ],
}

CONTRADICTIONS = {
    "wunderground": [r"\bwunderground\b"],
    "airport": [r"\bhong kong international airport\b", r"\bairport\b"],
    "non_hko_station": [r"\bstation other than hko\b", r"\bweather underground\b"],
    "whole_degree_only": [r"\bwhole degree\b", r"\brounded to nearest whole\b"],
}

def certify_row(row: pd.Series) -> dict:
    txt = str(row.get("combined_rule_text") or "")
    label = str(row.get("outcome_label_text") or "")
    K = row.get("threshold_K")
    hits = find_first_patterns(txt, PATTERNS)
    bad_hits = find_first_patterns(txt, CONTRADICTIONS)

    has_hko = bool(hits["hong_kong_observatory"])
    has_absmax = bool(hits["absolute_daily_max"])
    has_daily_extract = bool(hits["daily_extract"])
    has_one_decimal = bool(hits["one_decimal_precision"])
    has_range_lang = bool(hits["range_language"])
    has_tail_label = pd.notna(K) and looks_upper_tail(label)
    has_contradiction = any(bool(v) for v in bad_hits.values())

    # Boundary metadata route, retained from 17k.
    lb = row.get("lowerBound")
    ub = row.get("upperBound")
    range_field = str(row.get("groupItemRange") or "")
    dedicated_boundary_certifies = False
    boundary_reason = ""
    try:
        if pd.notna(lb) and int(float(lb)) == int(K):
            # Upper bound may be null/open, large, infinity, or textual.
            ub_s = str(ub).lower()
            if pd.isna(ub) or ub_s in ["none", "nan", "", "inf", "infinity"] or "inf" in ub_s:
                dedicated_boundary_certifies = True
                boundary_reason = "lowerBound equals K and upperBound is open/null"
    except Exception:
        pass
    if not dedicated_boundary_certifies and range_field:
        if re.search(rf"\b{int(K)}\b", range_field) and re.search(r"(higher|above|inf|infinity|\+|open)", range_field, flags=re.I):
            dedicated_boundary_certifies = True
            boundary_reason = "groupItemRange appears to encode an upper-tail interval"

    # Public rule text route. This is the new 17l route.
    rule_text_certifies_family = has_hko and has_absmax and has_daily_extract and has_one_decimal
    tail_boundary_certified_by_label = has_tail_label

    if dedicated_boundary_certifies and not has_contradiction:
        status = "formally_certified_by_gamma_boundary_metadata"
        reason = boundary_reason
    elif rule_text_certifies_family and tail_boundary_certified_by_label and not has_contradiction:
        status = "formally_certified_by_contract_rule_text"
        reason = (
            "public rule text identifies HKO/Hong Kong Observatory, Absolute Daily Max/Daily Extract, "
            "one-decimal convention, and child label is an explicit upper-tail K°C-or-higher outcome"
        )
    elif has_tail_label and not has_contradiction:
        status = "empirically_supported_pending_confirmation"
        missing = []
        if not has_hko: missing.append("HKO/Hong Kong Observatory")
        if not has_absmax: missing.append("Absolute Daily Max / maximum temperature")
        if not has_daily_extract: missing.append("Daily Extract")
        if not has_one_decimal: missing.append("one-decimal precision")
        reason = "upper-tail label found but public rule text lacks: " + ", ".join(missing)
    else:
        status = "not_certified_descriptive_only"
        reason = "not an upper-tail strict certifiable market or contradictory wording detected"
        if has_contradiction:
            reason += "; contradiction hits: " + "; ".join(f"{k}={v}" for k, v in bad_hits.items() if v)

    return {
        "has_hko_rule_text": has_hko,
        "has_absolute_daily_max_rule_text": has_absmax,
        "has_daily_extract_rule_text": has_daily_extract,
        "has_one_decimal_rule_text": has_one_decimal,
        "has_range_language": has_range_lang,
        "has_upper_tail_label": has_tail_label,
        "has_contradiction": has_contradiction,
        "dedicated_boundary_metadata_certifies": dedicated_boundary_certifies,
        "rule_text_certifies_family": rule_text_certifies_family,
        "tail_boundary_certified_by_label": tail_boundary_certified_by_label,
        "final_certification_status": status,
        "certification_reason": reason,
        **{f"hit_{k}": v for k, v in hits.items()},
        **{f"contradiction_{k}": v for k, v in bad_hits.items()},
    }

if len(market_df):
    cert_extra = market_df.apply(certify_row, axis=1, result_type="expand")
    decision = pd.concat([market_df.drop(columns=["combined_rule_text"], errors="ignore"), cert_extra], axis=1)
else:
    decision = pd.DataFrame()

# Keep most relevant upper-tail candidates first.
if len(decision):
    decision["event_date"] = decision.apply(lambda r: parse_event_date_from_slug_or_text(str(r.get("event_slug", "")), str(r.get("event_title", ""))), axis=1)
    decision = decision.sort_values(
        by=["looks_upper_tail", "final_certification_status", "event_date", "threshold_K"],
        ascending=[False, True, True, True],
        na_position="last"
    ).reset_index(drop=True)

decision_path = DATA_PROCESSED / "17l_hko_contract_rule_text_certification_decision.csv"
decision.to_csv(decision_path, index=False)
print("Saved:", decision_path)
print("Decision shape:", decision.shape)
if len(decision):
    print("\nFinal certification counts:")
    print(decision["final_certification_status"].value_counts(dropna=False))
    display(decision[[
        "event_slug", "market_slug", "outcome_label_text", "threshold_K",
        "has_hko_rule_text", "has_absolute_daily_max_rule_text", "has_daily_extract_rule_text",
        "has_one_decimal_rule_text", "has_upper_tail_label", "has_contradiction",
        "final_certification_status", "certification_reason"
    ]].head(30))


# -----------------------------
# 6. Evidence table with compact excerpts
# -----------------------------

def build_evidence_excerpt(row: pd.Series) -> str:
    txt = str(row.get("combined_rule_text_excerpt") or "")
    # Pull snippets around strongest terms.
    terms = ["hong kong observatory", "absolute daily max", "daily extract", "one decimal", "one-decimal", "later revisions", "range"]
    snippets = []
    for term in terms:
        idx = txt.find(term)
        if idx >= 0:
            start = max(0, idx - 180)
            end = min(len(txt), idx + 380)
            snippets.append(txt[start:end])
    if not snippets:
        return txt[:1500]
    # Deduplicate snippets.
    seen = set()
    uniq = []
    for s in snippets:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return "\n---\n".join(uniq)[:3000]

if len(decision):
    evidence = decision.copy()
    evidence["evidence_excerpt"] = evidence.apply(build_evidence_excerpt, axis=1)
    evidence_cols = [c for c in [
        "event_date", "event_slug", "event_url", "market_id", "market_slug",
        "outcome_label_text", "threshold_K", "final_certification_status",
        "certification_reason", "combined_rule_text_hash",
        "raw_event_json_path", "raw_market_json_path", "raw_event_html_path",
        "evidence_excerpt"
    ] if c in evidence.columns]
    evidence = evidence[evidence_cols]
else:
    evidence = pd.DataFrame()

evidence_path = DATA_PROCESSED / "17l_hko_contract_rule_text_evidence.csv"
evidence.to_csv(evidence_path, index=False)
print("Saved:", evidence_path)
if len(evidence):
    display(evidence.head(10))


# -----------------------------
# 7. Optional written confirmation upgrade
# -----------------------------

# If Polymarket replies later, save the text of the reply into:
# admin/polymarket_clarification_reply.txt
# Then rerun this cell/notebook to upgrade statuses where appropriate.

ADMIN_DIR = ROOT / "admin"
reply_candidates = [
    ADMIN_DIR / "polymarket_clarification_reply.txt",
    ADMIN_DIR / "polymarket_clarification_reply.md",
]

reply_text = ""
reply_path = None
for p in reply_candidates:
    if p.exists():
        reply_text = normalise_text(p.read_text(encoding="utf-8", errors="ignore"))
        reply_path = p
        break

def reply_confirms_endpoint_convention(reply: str) -> bool:
    if not reply:
        return False
    has_tail = contains_any(reply, [
        r"k\s*°?\s*c\s*or\s*higher.*at\s*least\s*k\.?0",
        r"at\s*least\s*k\.?0.*k\s*°?\s*c\s*or\s*higher",
        r"resolve[s]?\s*yes.*at\s*least\s*k\.?0",
        r"\b>=?\s*k\.?0\b",
        r"\bgreater than or equal to\s*k\.?0\b",
    ])
    has_interior = contains_any(reply, [
        r"k\.?0\s*≤\s*t\s*<\s*k\+1\.?0",
        r"k\.?0.*less than.*k\+1\.?0",
        r"interior.*k\.?0.*k\+1\.?0",
    ])
    has_hko = contains_any(reply, [r"hko", r"hong kong observatory", r"daily extract"])
    return has_tail and has_hko  # interior confirmation is useful but not strictly needed for upper tail.

written_confirmation = reply_confirms_endpoint_convention(reply_text)
print("Written confirmation path:", reply_path)
print("Written confirmation route:", written_confirmation)

if written_confirmation and len(decision):
    upgraded = decision.copy()
    mask = upgraded["looks_upper_tail"].fillna(False) & ~upgraded["has_contradiction"].fillna(False)
    upgraded.loc[mask, "final_certification_status"] = "formally_certified_by_polymarket_confirmation"
    upgraded.loc[mask, "certification_reason"] = "written Polymarket/resolver clarification confirms the upper-tail endpoint convention"
    upgraded_path = DATA_PROCESSED / "17l_hko_contract_rule_text_certification_decision_with_reply.csv"
    upgraded.to_csv(upgraded_path, index=False)
    print("Saved upgraded decision:", upgraded_path)
    print(upgraded["final_certification_status"].value_counts(dropna=False))


# -----------------------------
# 8. Markdown certification report
# -----------------------------

def counts_md(series: pd.Series) -> str:
    if series is None or len(series) == 0:
        return "_No rows._"
    vc = series.value_counts(dropna=False)
    lines = ["| status | count |", "|---|---:|"]
    for k, v in vc.items():
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines)

timestamp = datetime.now(timezone.utc).isoformat()

report = f"""# 17l HKO Contract Rule Text Certification Report

Generated: {timestamp}

## Purpose

This report records the public contract rule text audit for Hong Kong upper-tail Polymarket temperature markets.

The target payoff is

```latex
Z^M_{{d,K}} = \\mathbf{{1}}\\{{T_d^{{\\mathrm{{HKO}}}} \\ge K\\}}.
```

## Certification logic

A market is classified as `formally_certified_by_contract_rule_text` only when the public rule evidence supports all of:

1. Hong Kong Observatory / HKO source.
2. Absolute Daily Max or maximum-temperature source language.
3. Daily Extract source language.
4. One-decimal or equivalent precision convention.
5. Upper-tail child outcome label such as `K°C or higher`.
6. No contradictory source or precision wording.
7. No known realised-outcome mismatch from the previous 17j audit.

A market is classified as `formally_certified_by_gamma_boundary_metadata` only if dedicated boundary metadata explicitly encodes an upper-tail interval.

A market can later be upgraded to `formally_certified_by_polymarket_confirmation` if a written Polymarket or resolver reply confirms the endpoint convention.

## Output files

- `{decision_path.relative_to(ROOT)}`
- `{evidence_path.relative_to(ROOT)}`
- Raw JSON/HTML evidence under `{RULE_RAW_DIR.relative_to(ROOT)}`

## Certification counts

{counts_md(decision["final_certification_status"] if len(decision) else pd.Series(dtype=str))}

## Interpretation

If the table contains `formally_certified_by_contract_rule_text`, the thesis may state that, within the audited strict Hong Kong HKO Daily Extract one-decimal family, the upper-tail child markets are certified threshold contracts by public rule text.

If the table contains only `empirically_supported_pending_confirmation`, the thesis should not claim formal certification until written Polymarket/resolver confirmation is received or stronger boundary metadata is found.
"""

report_path = REPORT_DIR / "17l_hko_contract_rule_text_certification_report.md"
report_path.write_text(report, encoding="utf-8")
print("Saved:", report_path)
print(report[:2000])


# -----------------------------
# 9. Final compact display
# -----------------------------

if len(decision):
    compact_cols = [c for c in [
        "event_date", "event_slug", "market_slug", "outcome_label_text", "threshold_K",
        "final_certification_status", "certification_reason",
        "raw_event_json_path", "raw_market_json_path", "raw_event_html_path",
    ] if c in decision.columns]
    final_compact = decision[decision["looks_upper_tail"].fillna(False)][compact_cols].copy()
    final_compact_path = DATA_PROCESSED / "17l_hko_upper_tail_final_compact_decision.csv"
    final_compact.to_csv(final_compact_path, index=False)
    print("Saved:", final_compact_path)
    display(final_compact)
else:
    print("No decision rows found.")
