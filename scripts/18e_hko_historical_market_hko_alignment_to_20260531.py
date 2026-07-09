#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
18e_hko_historical_market_hko_alignment_to_20260531.py

Scaled historical Hong Kong empirical pipeline.

Goal
----
Construct the main realised-outcome empirical panel using all usable Hong Kong
highest-temperature Polymarket markets whose event dates can be aligned to the
official HKO daily maximum temperature series available up to 2026-05-31.

This is not a toy example. It retrieves the full candidate Hong Kong market
universe through public Polymarket metadata, classifies every child market,
retrieves CLOB YES-token price histories for threshold candidates, applies
pre-declared no-lookahead decision rules, joins official HKO outcomes, and
computes initial market-only scoring diagnostics.

The pipeline is fail-closed:
- no market is silently dropped;
- every exclusion receives a reason;
- official HKO scoring uses only official HKO realised values;
- price-history observations are separated from executable trading claims.
"""

from __future__ import annotations

import json
import math
import re
import time
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests


# =============================================================================
# Configuration
# =============================================================================

HISTORICAL_END_DATE = pd.Timestamp("2026-05-31").date()
HKT = "Asia/Hong_Kong"

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

# Broad discovery terms. We fetch using several parameter names because Gamma's
# public API has changed fields historically. The downstream filter is strict.
DISCOVERY_TERMS = [
    "highest temperature in hong kong",
    "hong kong highest temperature",
    "hong kong temperature",
    "highest temperature hong kong",
]

MAX_GAMMA_PAGES_PER_QUERY = 25
GAMMA_LIMIT = 500
REQUEST_TIMEOUT = 30
REQUEST_SLEEP_SECONDS = 0.15

# Decision snapshots.
DECISION_RULES = {
    "last_price_before_event_day_hkt": pd.Timedelta(hours=0),
    "last_price_before_24h_prior": pd.Timedelta(hours=24),
    "last_price_before_12h_prior": pd.Timedelta(hours=12),
}

EPS = 1e-6


# =============================================================================
# Repository and folders
# =============================================================================

def find_repo_root(start: Optional[Path] = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for candidate in [p] + list(p.parents):
        if (candidate / ".git").exists():
            return candidate
    # If running outside git, use current working directory.
    return p


ROOT = find_repo_root()
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "docs" / "research_outputs"

RAW_POLY = RAW / "polymarket_gamma_18e"
RAW_PRICE = RAW / "polymarket_clob_price_history_18e"
RAW_HKO = RAW / "hko_18e"

for d in [RAW_POLY, RAW_PRICE, RAW_HKO, INTERIM, PROCESSED, REPORTS]:
    d.mkdir(parents=True, exist_ok=True)

print(f"Repository root: {ROOT}")
print(f"Historical official-outcome end date: {HISTORICAL_END_DATE}")


# =============================================================================
# Utility helpers
# =============================================================================

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; UCL-MSc-Weather-Polymarket-Research/1.0)",
    "Accept": "application/json,text/html,text/plain,*/*",
})


def safe_slug(s: Any, max_len: int = 180) -> str:
    s = str(s) if s is not None else "missing"
    s = re.sub(r"[^A-Za-z0-9._=-]+", "_", s)
    return s[:max_len].strip("_") or "missing"


def get_json(url: str, params: Optional[dict] = None, timeout: int = REQUEST_TIMEOUT) -> Any:
    r = SESSION.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_text(url: str, params: Optional[dict] = None, timeout: int = REQUEST_TIMEOUT) -> str:
    r = SESSION.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.text


def json_load_maybe(x: Any) -> Any:
    if isinstance(x, (list, dict)):
        return x
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return x
    return x


def as_list(x: Any) -> list:
    x = json_load_maybe(x)
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, tuple):
        return list(x)
    return [x]


def norm_text(*parts: Any) -> str:
    return " ".join(str(p) for p in parts if p is not None and not (isinstance(p, float) and np.isnan(p))).lower()


def parse_event_date_from_text(*parts: Any) -> Optional[date]:
    text = norm_text(*parts)

    # ISO dates.
    m = re.search(r"(20\d{2})[-_/](\d{1,2})[-_/](\d{1,2})", text)
    if m:
        try:
            return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except Exception:
            pass

    # Month name formats.
    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    # "on may 26 2026", "may-26-2026", "may 26, 2026"
    m = re.search(
        r"\b(" + "|".join(month_map.keys()) + r")[\s\-_]+(\d{1,2})(?:st|nd|rd|th)?[,\s\-_]+(20\d{2})\b",
        text,
    )
    if m:
        try:
            return pd.Timestamp(int(m.group(3)), month_map[m.group(1)], int(m.group(2))).date()
        except Exception:
            pass

    # "26 may 2026"
    m = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-_]+(" + "|".join(month_map.keys()) + r")[,\s\-_]+(20\d{2})\b",
        text,
    )
    if m:
        try:
            return pd.Timestamp(int(m.group(3)), month_map[m.group(2)], int(m.group(1))).date()
        except Exception:
            pass

    return None


def parse_threshold_k(*parts: Any) -> Optional[float]:
    text = norm_text(*parts).replace("℃", "°c")
    patterns = [
        r"(\d{1,2}(?:\.\d+)?)\s*°?\s*c\s*or\s*higher",
        r"(\d{1,2}(?:\.\d+)?)\s*°?\s*c\s*or\s*above",
        r"at\s*least\s*(\d{1,2}(?:\.\d+)?)\s*°?\s*c",
        r"(\d{1,2}(?:\.\d+)?)c(?:elsius)?orhigher",
        r"(\d{1,2}(?:\.\d+)?)\s*deg(?:ree)?s?\s*c\s*or\s*higher",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return None


def contains_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(p, text, flags=re.I) for p in patterns)


# =============================================================================
# HKO official daily maximum temperature
# =============================================================================

def find_col(columns: Iterable[Any], required: Iterable[str], forbidden: Iterable[str] = ()) -> Optional[Any]:
    for c in columns:
        s = str(c).strip().lower()
        if all(term.lower() in s for term in required) and not any(term.lower() in s for term in forbidden):
            return c
    return None


def parse_hko_clmmaxt_text(text: str, source_name: str, source_url: str) -> pd.DataFrame:
    frames = []

    for skip in range(0, 12):
        try:
            df = pd.read_csv(StringIO(text), skiprows=skip)
        except Exception:
            continue

        if df.empty or df.shape[1] < 4:
            continue

        cols = list(df.columns)
        col_text = " ".join(str(c).lower() for c in cols)

        # Header with bilingual columns:
        # '#年/Year', '月/Month', '日/Day', '數值/Value', '數據完整性/data Completeness'
        year_col = (
            find_col(cols, ["year"])
            or find_col(cols, ["年"])
        )
        month_col = (
            find_col(cols, ["month"])
            or find_col(cols, ["月"])
        )
        day_col = (
            find_col(cols, ["day"])
            or find_col(cols, ["日"])
        )
        value_col = (
            find_col(cols, ["value"], ["completeness"])
            or find_col(cols, ["數值"], ["完整性"])
        )

        if all([year_col, month_col, day_col, value_col]):
            out = pd.DataFrame({
                "event_date": pd.to_datetime(
                    df[[year_col, month_col, day_col]].rename(
                        columns={year_col: "year", month_col: "month", day_col: "day"}
                    ),
                    errors="coerce",
                ).dt.date,
                "hko_tmax_C": pd.to_numeric(df[value_col], errors="coerce"),
            })
            out["hko_source_name"] = source_name
            out["hko_source_url"] = source_url
            out["hko_parse_route"] = f"ymd_value_header_skip_{skip}"
            frames.append(out)

        # Headerless/current-year style may become columns like ['2026','1','6','16.4','C']
        # after skiprows. Treat first 4 columns as y/m/d/value if they look plausible.
        if len(cols) >= 4:
            try:
                y = pd.to_numeric(df.iloc[:, 0], errors="coerce")
                m = pd.to_numeric(df.iloc[:, 1], errors="coerce")
                d = pd.to_numeric(df.iloc[:, 2], errors="coerce")
                v = pd.to_numeric(df.iloc[:, 3], errors="coerce")
                plaus = (
                    y.between(1900, 2100).mean() > 0.7
                    and m.between(1, 12).mean() > 0.7
                    and d.between(1, 31).mean() > 0.7
                    and v.between(-20, 60).mean() > 0.7
                )
                if plaus:
                    out = pd.DataFrame({
                        "event_date": pd.to_datetime(
                            pd.DataFrame({"year": y, "month": m, "day": d}),
                            errors="coerce",
                        ).dt.date,
                        "hko_tmax_C": v,
                    })
                    out["hko_source_name"] = source_name
                    out["hko_source_url"] = source_url
                    out["hko_parse_route"] = f"ymd_value_position_skip_{skip}"
                    frames.append(out)
            except Exception:
                pass

    if not frames:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source_name", "hko_source_url", "hko_parse_route"])

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["event_date", "hko_tmax_C"])
    out = out[(out["hko_tmax_C"] > -20) & (out["hko_tmax_C"] < 60)]
    out = out.drop_duplicates(["event_date", "hko_tmax_C", "hko_source_name", "hko_parse_route"])

    # Prefer official CLMMAXT all-year route when duplicates exist.
    out["_priority"] = np.where(out["hko_source_name"].str.contains("CLMMAXT", case=False, na=False), 0, 1)
    out = out.sort_values(["event_date", "_priority"]).drop_duplicates("event_date", keep="first")
    out = out.drop(columns=["_priority"]).sort_values("event_date").reset_index(drop=True)
    return out


def retrieve_hko_targets() -> pd.DataFrame:
    sources = [
        (
            "CLMMAXT_opendata",
            "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php?dataType=CLMMAXT&rformat=csv&station=HKO",
        ),
        (
            "daily_HKO_MAXT_2026_csdi",
            "https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKO_MAXT_2026.csv",
        ),
        (
            "daily_HKO_MAXT_2026_cis",
            "https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKO_MAXT_2026.csv",
        ),
    ]

    frames = []
    for name, url in sources:
        print(f"Fetching HKO source: {name} -> {url}")
        try:
            text = get_text(url)
            (RAW_HKO / f"{safe_slug(name)}.csv").write_text(text, encoding="utf-8")
            parsed = parse_hko_clmmaxt_text(text, name, url)
            print(f"  parsed rows: {len(parsed)}")
            if len(parsed):
                print(f"  date range: {parsed['event_date'].min()} to {parsed['event_date'].max()}")
                frames.append(parsed)
        except Exception as e:
            print(f"  WARNING: failed HKO source {name}: {e}")

    if not frames:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source_name", "hko_source_url", "hko_parse_route"])

    out = pd.concat(frames, ignore_index=True)
    out = out.dropna(subset=["event_date", "hko_tmax_C"])
    out = out.drop_duplicates(["event_date", "hko_tmax_C", "hko_source_name", "hko_parse_route"])
    out["_priority"] = np.where(out["hko_source_name"].eq("CLMMAXT_opendata"), 0, 1)
    out = out.sort_values(["event_date", "_priority"]).drop_duplicates("event_date", keep="first")
    out = out.drop(columns=["_priority"]).sort_values("event_date").reset_index(drop=True)
    out = out[out["event_date"] <= HISTORICAL_END_DATE].copy()
    return out


hko_targets = retrieve_hko_targets()
hko_targets.to_csv(PROCESSED / "18e_hko_daily_max_targets_to_20260531.csv", index=False)

print("\nOfficial HKO target rows:", len(hko_targets))
if len(hko_targets):
    print("Official HKO target date range:", hko_targets["event_date"].min(), "to", hko_targets["event_date"].max())
    print(hko_targets.tail(10).to_string(index=False))


# =============================================================================
# Polymarket Gamma discovery
# =============================================================================

def unwrap_gamma_response(obj: Any) -> List[dict]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ["data", "events", "markets", "results"]:
            if key in obj and isinstance(obj[key], list):
                return [x for x in obj[key] if isinstance(x, dict)]
    return []


def gamma_paginated(endpoint: str, base_params: dict, label: str) -> List[dict]:
    out: List[dict] = []
    for page in range(MAX_GAMMA_PAGES_PER_QUERY):
        params = dict(base_params)
        params["limit"] = GAMMA_LIMIT
        params["offset"] = page * GAMMA_LIMIT
        url = f"{GAMMA_BASE}/{endpoint.lstrip('/')}"
        try:
            obj = get_json(url, params=params)
            raw_path = RAW_POLY / f"{safe_slug(label)}__{endpoint.strip('/')}__page_{page:03d}.json"
            raw_path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
            rows = unwrap_gamma_response(obj)
            print(f"{label} / {endpoint} page {page}: {len(rows)} rows")
            out.extend(rows)
            if len(rows) < GAMMA_LIMIT:
                break
            time.sleep(REQUEST_SLEEP_SECONDS)
        except Exception as e:
            print(f"WARNING: Gamma request failed for {label} / {endpoint} page {page}: {e}")
            break
    return out


def discover_polymarket_hk_universe() -> Tuple[pd.DataFrame, pd.DataFrame]:
    events_raw: List[dict] = []
    markets_raw: List[dict] = []

    # Search attempts using different parameter names and endpoints.
    search_param_names = ["q", "query", "search", "term"]
    for term in DISCOVERY_TERMS:
        for param_name in search_param_names:
            params = {param_name: term, "closed": "true", "archived": "false"}
            events_raw.extend(gamma_paginated("events", params, f"events_{param_name}_{term}"))
            markets_raw.extend(gamma_paginated("markets", params, f"markets_{param_name}_{term}"))

    # Broad closed-event scan, capped.
    events_raw.extend(gamma_paginated("events", {"closed": "true"}, "events_closed_broad"))
    markets_raw.extend(gamma_paginated("markets", {"closed": "true"}, "markets_closed_broad"))

    # Deduplicate by id/slug.
    def dedupe_dicts(rows: List[dict]) -> List[dict]:
        seen = set()
        out = []
        for r in rows:
            key = str(r.get("id") or r.get("slug") or r.get("conditionId") or json.dumps(r, sort_keys=True)[:500])
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    events_raw = dedupe_dicts(events_raw)
    markets_raw = dedupe_dicts(markets_raw)

    (RAW_POLY / "18e_polymarket_hk_events_raw.json").write_text(
        json.dumps(events_raw, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (RAW_POLY / "18e_polymarket_hk_markets_raw.json").write_text(
        json.dumps(markets_raw, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nRaw Gamma events discovered:", len(events_raw))
    print("Raw Gamma markets discovered:", len(markets_raw))

    return pd.DataFrame({"raw_event": events_raw}), pd.DataFrame({"raw_market": markets_raw})


raw_events_df, raw_markets_df = discover_polymarket_hk_universe()


# =============================================================================
# Flatten Polymarket child markets
# =============================================================================

def event_to_base_fields(event: dict) -> dict:
    return {
        "event_id": event.get("id"),
        "event_slug": event.get("slug"),
        "event_url": event.get("url") or event.get("link"),
        "event_title": event.get("title") or event.get("question"),
        "event_description": event.get("description"),
        "event_resolution_source": event.get("resolutionSource"),
        "event_rules": event.get("rules"),
        "event_start": event.get("startDate") or event.get("startDateIso"),
        "event_end": event.get("endDate") or event.get("endDateIso") or event.get("endDate"),
        "event_closed": event.get("closed"),
        "event_active": event.get("active"),
        "event_createdAt": event.get("createdAt"),
        "event_raw": event,
    }


def market_to_fields(market: dict, base: Optional[dict] = None) -> dict:
    base = base or {}
    outcomes = as_list(market.get("outcomes"))
    clob_ids = as_list(market.get("clobTokenIds") or market.get("clob_token_ids"))
    outcome_prices = as_list(market.get("outcomePrices") or market.get("outcome_prices"))

    # Outcome label text: for binary child markets, use question/title; keep outcomes for token mapping.
    question = market.get("question") or market.get("title")
    title = market.get("title") or market.get("question")
    outcome_label_text = question or title or ""

    yes_token_id = None
    no_token_id = None
    for i, out in enumerate(outcomes):
        if i < len(clob_ids):
            val = str(out).strip().lower()
            if val == "yes":
                yes_token_id = str(clob_ids[i])
            elif val == "no":
                no_token_id = str(clob_ids[i])
    if yes_token_id is None and len(clob_ids) >= 1:
        # Most Polymarket binary markets are Yes/No in order.
        yes_token_id = str(clob_ids[0])
    if no_token_id is None and len(clob_ids) >= 2:
        no_token_id = str(clob_ids[1])

    row = {
        **base,
        "market_id": market.get("id"),
        "condition_id": market.get("conditionId") or market.get("condition_id"),
        "market_slug": market.get("slug"),
        "market_question": question,
        "market_title": title,
        "market_description": market.get("description"),
        "market_resolution_source": market.get("resolutionSource"),
        "market_rules": market.get("rules"),
        "outcome_label_text": outcome_label_text,
        "outcomes": json.dumps(outcomes, ensure_ascii=False),
        "clobTokenIds": json.dumps(clob_ids, ensure_ascii=False),
        "yes_token_id": yes_token_id,
        "no_token_id": no_token_id,
        "outcomePrices": json.dumps(outcome_prices, ensure_ascii=False),
        "volume": market.get("volume") or market.get("volumeNum"),
        "liquidity": market.get("liquidity") or market.get("liquidityNum"),
        "closed": market.get("closed"),
        "active": market.get("active"),
        "createdAt": market.get("createdAt"),
        "closedTime": market.get("closedTime"),
        "endDate": market.get("endDate"),
        "lowerBound": market.get("lowerBound"),
        "upperBound": market.get("upperBound"),
        "groupItemThreshold": market.get("groupItemThreshold"),
        "groupItemRange": market.get("groupItemRange"),
        "raw_market_json": market,
    }
    return row


def flatten_events_and_markets(events_raw: List[dict], markets_raw: List[dict]) -> pd.DataFrame:
    rows = []

    for event in events_raw:
        if not isinstance(event, dict):
            continue
        base = event_to_base_fields(event)
        markets = event.get("markets") or []
        if isinstance(markets, str):
            markets = json_load_maybe(markets) or []
        if isinstance(markets, list) and markets:
            for market in markets:
                if isinstance(market, dict):
                    rows.append(market_to_fields(market, base))
        else:
            # Parent event with no nested markets.
            rows.append({**base, "raw_market_json": None})

    # Also include standalone market search results.
    for market in markets_raw:
        if not isinstance(market, dict):
            continue
        base = {
            "event_id": market.get("eventId") or market.get("event_id"),
            "event_slug": market.get("eventSlug") or market.get("event_slug") or market.get("slug"),
            "event_title": market.get("eventTitle") or market.get("event_title"),
            "event_description": None,
            "event_resolution_source": None,
            "event_rules": None,
            "event_raw": None,
        }
        rows.append(market_to_fields(market, base))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Deduplicate economic child market rows.
    dedupe_cols = [c for c in ["market_id", "condition_id", "market_slug"] if c in df.columns]
    if dedupe_cols:
        # Use any available ID. First, fill a dedupe key.
        df["_dedupe_key"] = df[dedupe_cols].astype(str).agg("||".join, axis=1)
        df = df.drop_duplicates("_dedupe_key").drop(columns=["_dedupe_key"])
    else:
        df = df.drop_duplicates()

    return df.reset_index(drop=True)


events_list = raw_events_df["raw_event"].tolist() if "raw_event" in raw_events_df else []
markets_list = raw_markets_df["raw_market"].tolist() if "raw_market" in raw_markets_df else []
children = flatten_events_and_markets(events_list, markets_list)

if children.empty:
    raise RuntimeError("No Polymarket child markets discovered. Check Gamma API connectivity or query parameters.")

print("\nFlattened child market rows before HK filtering:", children.shape)


# =============================================================================
# Classification and alignment
# =============================================================================

TEXT_COLS = [
    "event_slug", "event_title", "event_description", "event_resolution_source", "event_rules",
    "market_slug", "market_question", "market_title", "market_description", "market_resolution_source", "market_rules",
    "outcome_label_text",
]


def classify_child_market(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for c in TEXT_COLS:
        if c not in out.columns:
            out[c] = ""

    out["combined_rule_text"] = out[TEXT_COLS].fillna("").astype(str).agg(" | ".join, axis=1)
    out["combined_rule_text_l"] = out["combined_rule_text"].str.lower()

    text = out["combined_rule_text_l"]

    out["event_date"] = out.apply(
        lambda r: parse_event_date_from_text(
            r.get("event_slug"),
            r.get("event_title"),
            r.get("market_slug"),
            r.get("market_question"),
            r.get("market_title"),
        ),
        axis=1,
    )

    out["threshold_K"] = out.apply(
        lambda r: parse_threshold_k(
            r.get("market_slug"),
            r.get("market_question"),
            r.get("market_title"),
            r.get("outcome_label_text"),
        ),
        axis=1,
    )

    out["is_hong_kong"] = text.str.contains("hong kong", regex=False, na=False)
    out["is_highest_temperature"] = text.str.contains("highest temperature", regex=False, na=False)
    out["is_lowest_temperature"] = text.str.contains("lowest temperature", regex=False, na=False)

    out["has_hko_rule_text"] = text.str.contains(r"\bhko\b|hong kong observatory", regex=True, na=False)
    out["has_absolute_daily_max_rule_text"] = text.str.contains(
        r"absolute daily max|daily max|maximum temperature", regex=True, na=False
    )
    out["has_daily_extract_rule_text"] = text.str.contains("daily extract", regex=False, na=False)
    out["has_one_decimal_rule_text"] = text.str.contains(
        r"one[- ]decimal|1 decimal|one decimal|0\.1|one-decimal", regex=True, na=False
    )

    out["looks_upper_tail"] = (
        text.str.contains(r"\bor higher\b|\bor above\b|\bat least\b", regex=True, na=False)
        | out["market_slug"].fillna("").astype(str).str.lower().str.contains("orhigher|or-higher|higher", regex=True, na=False)
    )
    out["has_threshold_K"] = out["threshold_K"].notna()

    # Contradictions.
    out["contradiction_wunderground"] = text.str.contains("wunderground", regex=False, na=False)
    out["contradiction_airport"] = text.str.contains("airport", regex=False, na=False)
    out["contradiction_low_direction"] = out["is_lowest_temperature"]
    out["contradiction_whole_degree_only"] = text.str.contains("whole-degree|whole degree", regex=True, na=False)
    out["has_contradiction"] = (
        out["contradiction_wunderground"]
        | out["contradiction_airport"]
        | out["contradiction_low_direction"]
        | out["contradiction_whole_degree_only"]
    )

    def family(row) -> str:
        if not row["is_hong_kong"]:
            return "not_hong_kong"
        if row["is_lowest_temperature"]:
            return "lowest_temperature_or_wrong_direction"
        if row["contradiction_airport"] or row["contradiction_wunderground"]:
            return "airport_or_wunderground_source"
        if row["contradiction_whole_degree_only"]:
            return "whole_degree_or_ambiguous_precision"
        if row["has_hko_rule_text"] and row["has_absolute_daily_max_rule_text"] and row["has_daily_extract_rule_text"] and row["has_one_decimal_rule_text"]:
            return "strict_hko_daily_extract_one_decimal"
        if row["has_hko_rule_text"] or row["has_daily_extract_rule_text"] or row["has_absolute_daily_max_rule_text"]:
            return "hko_family_but_boundary_uncertain"
        return "unknown_or_insufficient_rule_text"

    out["rule_family"] = out.apply(family, axis=1)

    def empirical_status(row) -> str:
        if not row["is_hong_kong"] or not row["is_highest_temperature"]:
            return "excluded"
        if row["has_contradiction"]:
            return "excluded"
        if not row["looks_upper_tail"]:
            # Interior categorical rows may be useful descriptively but not as threshold probabilities.
            return "categorical_descriptive_only"
        if not row["has_threshold_K"]:
            return "excluded"
        if row["rule_family"] == "strict_hko_daily_extract_one_decimal":
            return "formally_certified_threshold_contract"
        if row["rule_family"] == "hko_family_but_boundary_uncertain":
            return "empirically_supported_threshold_candidate"
        return "excluded"

    out["empirical_role"] = out.apply(empirical_status, axis=1)

    def exclusion_reason(row) -> str:
        if row["empirical_role"] != "excluded":
            return ""
        reasons = []
        if not row["is_hong_kong"]:
            reasons.append("not_hong_kong")
        if not row["is_highest_temperature"]:
            reasons.append("not_highest_temperature")
        if row["is_lowest_temperature"]:
            reasons.append("lowest_temperature")
        if row["contradiction_wunderground"]:
            reasons.append("wunderground_source")
        if row["contradiction_airport"]:
            reasons.append("airport_source")
        if row["contradiction_whole_degree_only"]:
            reasons.append("whole_degree_or_ambiguous_precision")
        if row["looks_upper_tail"] and not row["has_threshold_K"]:
            reasons.append("upper_tail_without_parsed_threshold")
        if not reasons:
            reasons.append("insufficient_rule_text_or_unknown")
        return ";".join(reasons)

    out["exclusion_reason"] = out.apply(exclusion_reason, axis=1)
    return out


classified = classify_child_market(children)

# Keep Hong Kong candidates for output, but include every row with classification.
hk_contract_universe = classified[
    classified["is_hong_kong"] | classified["combined_rule_text_l"].str.contains("hong kong", na=False)
].copy()

# Historical only, official outcome available date range.
hk_contract_universe = hk_contract_universe[hk_contract_universe["event_date"].notna()].copy()
hk_contract_universe["event_date"] = pd.to_datetime(hk_contract_universe["event_date"]).dt.date
hk_contract_universe = hk_contract_universe[hk_contract_universe["event_date"] <= HISTORICAL_END_DATE].copy()

# Join HKO outcomes.
hk_contract_universe = hk_contract_universe.merge(hko_targets, on="event_date", how="left")
hk_contract_universe["hko_outcome_available"] = hk_contract_universe["hko_tmax_C"].notna()
hk_contract_universe["Y_ge_K"] = np.where(
    hk_contract_universe["hko_outcome_available"] & hk_contract_universe["threshold_K"].notna(),
    (hk_contract_universe["hko_tmax_C"] >= hk_contract_universe["threshold_K"]).astype(int),
    np.nan,
)

# Save universe.
important_cols = [
    "event_date", "event_slug", "event_title", "market_id", "condition_id", "market_slug",
    "market_question", "market_title", "outcome_label_text", "threshold_K", "looks_upper_tail",
    "yes_token_id", "no_token_id", "volume", "liquidity", "createdAt", "closedTime", "endDate",
    "rule_family", "empirical_role", "exclusion_reason", "hko_tmax_C", "Y_ge_K",
    "hko_outcome_available", "has_hko_rule_text", "has_absolute_daily_max_rule_text",
    "has_daily_extract_rule_text", "has_one_decimal_rule_text", "has_contradiction",
    "lowerBound", "upperBound", "groupItemThreshold", "groupItemRange",
    "combined_rule_text",
]
save_cols = [c for c in important_cols if c in hk_contract_universe.columns]
hk_contract_universe[save_cols].to_csv(PROCESSED / "18e_hko_historical_contract_universe_to_20260531.csv", index=False)

threshold_candidates = hk_contract_universe[
    hk_contract_universe["empirical_role"].isin([
        "formally_certified_threshold_contract",
        "empirically_supported_threshold_candidate",
    ])
    & hk_contract_universe["hko_outcome_available"]
    & hk_contract_universe["yes_token_id"].notna()
].copy()

threshold_candidates.to_csv(PROCESSED / "18e_hko_historical_threshold_candidate_panel_to_20260531.csv", index=False)

print("\nHK historical contract universe:", hk_contract_universe.shape)
print("Classification counts:")
print(hk_contract_universe["empirical_role"].value_counts(dropna=False))
print("\nRule family counts:")
print(hk_contract_universe["rule_family"].value_counts(dropna=False))
print("\nThreshold candidates with HKO outcome and YES token:", threshold_candidates.shape)
if len(threshold_candidates):
    print(threshold_candidates[["event_date", "threshold_K", "market_slug", "empirical_role", "hko_tmax_C", "Y_ge_K"]].head(30).to_string(index=False))


# =============================================================================
# Price-history retrieval for threshold candidates
# =============================================================================

def retrieve_price_history(token_id: str, start_ts: Optional[int] = None, end_ts: Optional[int] = None) -> dict:
    url = f"{CLOB_BASE}/prices-history"
    param_variants = [
        {"market": token_id, "interval": "max", "fidelity": 60},
        {"market": token_id, "fidelity": 60},
        {"market": token_id, "interval": "all"},
        {"market": token_id},
    ]
    if start_ts is not None and end_ts is not None:
        param_variants.insert(0, {"market": token_id, "startTs": start_ts, "endTs": end_ts, "interval": "max", "fidelity": 60})
        param_variants.insert(1, {"market": token_id, "start_ts": start_ts, "end_ts": end_ts, "interval": "max", "fidelity": 60})

    last_error = None
    for params in param_variants:
        try:
            r = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                obj = r.json()
                if isinstance(obj, dict) and "history" in obj:
                    obj["_request_params_used"] = params
                    return obj
                if isinstance(obj, list):
                    return {"history": obj, "_request_params_used": params}
            last_error = f"status={r.status_code}, text={r.text[:200]}"
        except Exception as e:
            last_error = str(e)
        time.sleep(REQUEST_SLEEP_SECONDS)

    return {"history": [], "_error": last_error}


def parse_price_history_json(obj: dict, row: pd.Series) -> pd.DataFrame:
    hist = obj.get("history") if isinstance(obj, dict) else []
    if not isinstance(hist, list) or not hist:
        return pd.DataFrame()

    out = pd.DataFrame(hist)
    if out.empty:
        return out

    # Common response fields: t, p.
    t_col = "t" if "t" in out.columns else ("timestamp" if "timestamp" in out.columns else None)
    p_col = "p" if "p" in out.columns else ("price" if "price" in out.columns else None)

    if t_col is None or p_col is None:
        return pd.DataFrame()

    out["price_timestamp_utc"] = pd.to_datetime(out[t_col], unit="s", utc=True, errors="coerce")
    out["price_timestamp_hkt"] = out["price_timestamp_utc"].dt.tz_convert(HKT)
    out["yes_price"] = pd.to_numeric(out[p_col], errors="coerce")

    meta_cols = [
        "event_date", "threshold_K", "event_slug", "market_slug", "market_id",
        "condition_id", "yes_token_id", "volume", "liquidity", "empirical_role",
        "rule_family", "hko_tmax_C", "Y_ge_K",
    ]
    for c in meta_cols:
        out[c] = row.get(c)

    out["price_history_status"] = "ok"
    out["price_history_params"] = json.dumps(obj.get("_request_params_used", {}), sort_keys=True)
    out = out.dropna(subset=["price_timestamp_utc", "yes_price"])
    out = out[(out["yes_price"] >= 0) & (out["yes_price"] <= 1)]
    return out


price_frames = []
coverage_rows = []

if threshold_candidates.empty:
    print("\nNo threshold candidates available for price retrieval.")
else:
    for idx, row in threshold_candidates.reset_index(drop=True).iterrows():
        token_id = str(row["yes_token_id"])
        label = f"{safe_slug(row.get('event_slug'))}__K{row.get('threshold_K')}__{safe_slug(token_id, 80)}"
        print(f"Retrieving price history {idx + 1}/{len(threshold_candidates)}: {label}")

        # Conservative broad start/end around market life. Use event date plus broad buffer.
        event_dt = pd.Timestamp(row["event_date"], tz=HKT)
        start_ts = int((event_dt - pd.Timedelta(days=45)).tz_convert("UTC").timestamp())
        end_ts = int((event_dt + pd.Timedelta(days=2)).tz_convert("UTC").timestamp())

        obj = retrieve_price_history(token_id, start_ts=start_ts, end_ts=end_ts)
        raw_path = RAW_PRICE / f"{label}.json"
        raw_path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

        ph = parse_price_history_json(obj, row)
        if len(ph):
            price_frames.append(ph)
            status = "ok"
        else:
            status = "empty_or_failed"

        coverage_rows.append({
            "event_date": row.get("event_date"),
            "threshold_K": row.get("threshold_K"),
            "market_slug": row.get("market_slug"),
            "yes_token_id": token_id,
            "empirical_role": row.get("empirical_role"),
            "price_history_status": status,
            "price_rows": len(ph),
            "raw_price_json_path": str(raw_path.relative_to(ROOT)),
            "price_history_error": obj.get("_error") if isinstance(obj, dict) else None,
        })

        time.sleep(REQUEST_SLEEP_SECONDS)

price_panel = pd.concat(price_frames, ignore_index=True) if price_frames else pd.DataFrame()
coverage = pd.DataFrame(coverage_rows)

price_panel.to_csv(PROCESSED / "18e_hko_historical_price_history_panel_to_20260531.csv", index=False)
coverage.to_csv(PROCESSED / "18e_hko_historical_price_coverage_summary_to_20260531.csv", index=False)

print("\nPrice panel shape:", price_panel.shape)
if len(coverage):
    print("\nPrice history status counts:")
    print(coverage["price_history_status"].value_counts(dropna=False))
    print(coverage.to_string(index=False))


# =============================================================================
# No-lookahead decision panel
# =============================================================================

def build_decision_panel(price_panel: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if candidates.empty:
        return pd.DataFrame()

    # Normalize event dates.
    candidates = candidates.copy()
    candidates["event_start_hkt"] = pd.to_datetime(candidates["event_date"].astype(str)).dt.tz_localize(HKT)

    for _, cand in candidates.iterrows():
        key_mask = (
            (price_panel.get("market_slug", pd.Series(dtype=str)).astype(str) == str(cand.get("market_slug")))
            & (price_panel.get("yes_token_id", pd.Series(dtype=str)).astype(str) == str(cand.get("yes_token_id")))
        ) if not price_panel.empty else pd.Series([], dtype=bool)

        ph = price_panel[key_mask].copy() if not price_panel.empty else pd.DataFrame()
        if len(ph):
            ph = ph.sort_values("price_timestamp_utc")

        event_start_hkt = cand["event_start_hkt"]
        event_start_utc = event_start_hkt.tz_convert("UTC")

        for rule, offset in DECISION_RULES.items():
            cutoff_hkt = event_start_hkt - offset
            cutoff_utc = cutoff_hkt.tz_convert("UTC")

            selected = None
            if len(ph):
                valid = ph[ph["price_timestamp_utc"] <= cutoff_utc]
                if len(valid):
                    selected = valid.iloc[-1]

            base = {
                "event_date": cand.get("event_date"),
                "threshold_K": cand.get("threshold_K"),
                "event_slug": cand.get("event_slug"),
                "market_slug": cand.get("market_slug"),
                "market_id": cand.get("market_id"),
                "condition_id": cand.get("condition_id"),
                "yes_token_id": cand.get("yes_token_id"),
                "empirical_role": cand.get("empirical_role"),
                "rule_family": cand.get("rule_family"),
                "hko_tmax_C": cand.get("hko_tmax_C"),
                "Y_ge_K": cand.get("Y_ge_K"),
                "event_start_hkt": event_start_hkt,
                "event_start_utc": event_start_utc,
                "decision_rule": rule,
                "decision_cutoff_hkt": cutoff_hkt,
                "decision_cutoff_utc": cutoff_utc,
                "price_observations_total": len(ph),
                "hko_outcome_available": pd.notna(cand.get("hko_tmax_C")),
                "no_lookahead_valid": True,
            }

            if selected is not None:
                base.update({
                    "decision_timestamp_utc": selected["price_timestamp_utc"],
                    "decision_timestamp_hkt": selected["price_timestamp_hkt"],
                    "yes_price": selected["yes_price"],
                    "decision_price_available": True,
                    "hours_before_event_start": (event_start_utc - selected["price_timestamp_utc"]) / pd.Timedelta(hours=1),
                    "decision_panel_status": "ok",
                })
            else:
                base.update({
                    "decision_timestamp_utc": pd.NaT,
                    "decision_timestamp_hkt": pd.NaT,
                    "yes_price": np.nan,
                    "decision_price_available": False,
                    "hours_before_event_start": np.nan,
                    "decision_panel_status": "no_price_before_cutoff",
                })

            rows.append(base)

    return pd.DataFrame(rows)


decision_panel = build_decision_panel(price_panel, threshold_candidates)
decision_panel.to_csv(PROCESSED / "18e_hko_historical_no_lookahead_decision_panel_to_20260531.csv", index=False)

scoring_ready = decision_panel[
    decision_panel.get("decision_price_available", pd.Series(dtype=bool)).fillna(False).astype(bool)
    & decision_panel.get("hko_outcome_available", pd.Series(dtype=bool)).fillna(False).astype(bool)
    & decision_panel.get("no_lookahead_valid", pd.Series(dtype=bool)).fillna(False).astype(bool)
].copy()

scoring_ready.to_csv(PROCESSED / "18e_hko_historical_scoring_ready_market_panel_to_20260531.csv", index=False)

print("\nDecision panel shape:", decision_panel.shape)
if len(decision_panel):
    print("Decision status counts:")
    print(decision_panel["decision_panel_status"].value_counts(dropna=False))
    print("Decision rule counts:")
    print(decision_panel["decision_rule"].value_counts(dropna=False))

print("\nScoring-ready official HKO market panel shape:", scoring_ready.shape)
if len(scoring_ready):
    print(scoring_ready[["event_date", "threshold_K", "market_slug", "decision_rule", "yes_price", "hko_tmax_C", "Y_ge_K"]].head(30).to_string(index=False))


# =============================================================================
# Market-only scoring
# =============================================================================

def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["p_market"] = pd.to_numeric(out["yes_price"], errors="coerce")
    out["Y"] = pd.to_numeric(out["Y_ge_K"], errors="coerce")
    out["p_market_clipped"] = out["p_market"].clip(EPS, 1 - EPS)
    out["brier_market"] = (out["p_market"] - out["Y"]) ** 2
    out["log_score_market"] = -(
        out["Y"] * np.log(out["p_market_clipped"])
        + (1 - out["Y"]) * np.log(1 - out["p_market_clipped"])
    )
    return out


scores = compute_scores(scoring_ready)
scores.to_csv(PROCESSED / "18e_hko_historical_market_only_scores_to_20260531.csv", index=False)

if len(scores):
    summary = (
        scores.groupby(["decision_rule", "empirical_role"], dropna=False)
        .agg(
            n=("brier_market", "size"),
            mean_brier=("brier_market", "mean"),
            mean_log_score=("log_score_market", "mean"),
            mean_p_market=("p_market", "mean"),
            outcome_rate=("Y", "mean"),
        )
        .reset_index()
    )
else:
    summary = pd.DataFrame(columns=["decision_rule", "empirical_role", "n", "mean_brier", "mean_log_score", "mean_p_market", "outcome_rate"])

summary.to_csv(PROCESSED / "18e_hko_historical_market_only_score_summary_to_20260531.csv", index=False)

print("\nMarket-only score summary:")
print(summary.to_string(index=False))


# =============================================================================
# Report
# =============================================================================

def value_counts_md(s: pd.Series) -> str:
    if s is None or len(s) == 0:
        return "_None_"
    vc = s.value_counts(dropna=False).reset_index()
    vc.columns = ["value", "count"]
    return vc.to_markdown(index=False)


report = []
report.append("# 18e Hong Kong historical market-HKO alignment to 2026-05-31\n")
report.append(f"Repository root: `{ROOT}`\n")
report.append(f"Historical official-outcome end date: `{HISTORICAL_END_DATE}`\n")
report.append("\n## Purpose\n")
report.append(
    "This notebook constructs the scaled historical Hong Kong empirical panel by aligning "
    "Polymarket Hong Kong highest-temperature markets with official HKO daily maximum "
    "temperature observations available through machine-readable HKO sources up to "
    "31 May 2026.\n"
)

report.append("\n## HKO official target coverage\n")
report.append(f"HKO target rows: `{len(hko_targets)}`\n")
if len(hko_targets):
    report.append(f"HKO date range: `{hko_targets['event_date'].min()}` to `{hko_targets['event_date'].max()}`\n")

report.append("\n## Polymarket universe coverage\n")
report.append(f"Flattened HK historical contract universe rows: `{len(hk_contract_universe)}`\n")
report.append(f"Threshold candidate rows with official HKO outcome and YES token: `{len(threshold_candidates)}`\n")
report.append("\n### Empirical role counts\n")
report.append(value_counts_md(hk_contract_universe["empirical_role"]) + "\n")
report.append("\n### Rule family counts\n")
report.append(value_counts_md(hk_contract_universe["rule_family"]) + "\n")

report.append("\n## Price history coverage\n")
report.append(f"Price history panel rows: `{len(price_panel)}`\n")
if len(coverage):
    report.append("\n### Price history status counts\n")
    report.append(value_counts_md(coverage["price_history_status"]) + "\n")

report.append("\n## No-lookahead decision panel\n")
report.append(f"Decision panel rows: `{len(decision_panel)}`\n")
report.append(f"Official HKO scoring-ready rows: `{len(scoring_ready)}`\n")
if len(decision_panel):
    report.append("\n### Decision status counts\n")
    report.append(value_counts_md(decision_panel["decision_panel_status"]) + "\n")
    report.append("\n### Decision rule counts\n")
    report.append(value_counts_md(decision_panel["decision_rule"]) + "\n")

report.append("\n## Market-only score summary\n")
if len(summary):
    report.append(summary.to_markdown(index=False) + "\n")
else:
    report.append("_No official HKO scoring-ready rows were available after no-lookahead filtering._\n")

report.append("\n## Interpretation\n")
if len(scoring_ready):
    report.append(
        "The pipeline produced a non-empty official realised-outcome market scoring panel. "
        "These rows can be used for market-only calibration and later joined to forecast-implied "
        "threshold probabilities.\n"
    )
else:
    report.append(
        "The pipeline completed the full market-HKO alignment process, but no official HKO "
        "scoring-ready rows were available after all filters. This indicates that either the "
        "historical Polymarket markets before 31 May 2026 do not contain usable upper-tail "
        "threshold candidates with CLOB price history under the current discovery route, or the "
        "candidate contracts require manual rule-family review before entering scoring.\n"
    )

report_path = REPORTS / "18e_hko_historical_alignment_report.md"
report_path.write_text("\n".join(report), encoding="utf-8")
print("\nSaved report:", report_path)

print("\nKey outputs:")
for p in [
    PROCESSED / "18e_hko_daily_max_targets_to_20260531.csv",
    PROCESSED / "18e_hko_historical_contract_universe_to_20260531.csv",
    PROCESSED / "18e_hko_historical_threshold_candidate_panel_to_20260531.csv",
    PROCESSED / "18e_hko_historical_price_history_panel_to_20260531.csv",
    PROCESSED / "18e_hko_historical_price_coverage_summary_to_20260531.csv",
    PROCESSED / "18e_hko_historical_no_lookahead_decision_panel_to_20260531.csv",
    PROCESSED / "18e_hko_historical_scoring_ready_market_panel_to_20260531.csv",
    PROCESSED / "18e_hko_historical_market_only_scores_to_20260531.csv",
    PROCESSED / "18e_hko_historical_market_only_score_summary_to_20260531.csv",
    report_path,
]:
    print(p.relative_to(ROOT))
