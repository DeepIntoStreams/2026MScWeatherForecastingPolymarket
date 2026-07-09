#!/usr/bin/env python3
"""
18e v2: Scaled historical Hong Kong Polymarket--HKO alignment to 2026-05-31.

This replacement script fixes the main failure in v1: Gamma search queries returned generic
markets rather than Hong Kong markets. v2 uses deterministic event-slug probing over the
historical date range, with multiple endpoint fallbacks, then runs the full alignment pipeline.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import requests

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

# -----------------------------
# Configuration
# -----------------------------

HISTORICAL_END = pd.Timestamp("2026-05-31").date()
HISTORICAL_START = pd.Timestamp("2026-01-01").date()
REQUEST_SLEEP_SECONDS = 0.05
PRICE_REQUEST_SLEEP_SECONDS = 0.10

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UCL-MSc-dissertation-research/1.0)",
    "Accept": "application/json,text/html,*/*",
}

HK_TZ = ZoneInfo("Asia/Hong_Kong") if ZoneInfo else timezone(timedelta(hours=8))
UTC = timezone.utc

# -----------------------------
# Paths
# -----------------------------


def find_repo_root() -> Path:
    p = Path.cwd().resolve()
    for q in [p] + list(p.parents):
        if (q / ".git").exists() and (q / "notebooks").exists():
            return q
    return p


ROOT = find_repo_root()
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"
RAW_GAMMA = DATA_RAW / "polymarket_gamma_18e_v2"
RAW_PRICE = DATA_RAW / "polymarket_clob_price_history_18e_v2"
LOGS = ROOT / "logs"

for d in [DATA_RAW, DATA_PROCESSED, REPORTS, RAW_GAMMA, RAW_PRICE, LOGS]:
    d.mkdir(parents=True, exist_ok=True)


# -----------------------------
# General helpers
# -----------------------------


def safe_slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(s))[:220]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def parse_jsonish(x: Any) -> Any:
    if isinstance(x, (list, dict)):
        return x
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            # Sometimes stored as single-quoted list strings.
            try:
                import ast
                return ast.literal_eval(s)
            except Exception:
                return x
    return x


def norm_text(*xs: Any) -> str:
    return " ".join(str(x) for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))).lower()


def http_get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> tuple[int, Any, str]:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        text = r.text
        if r.status_code >= 400:
            return r.status_code, None, text[:500]
        try:
            return r.status_code, r.json(), text[:500]
        except Exception:
            return r.status_code, None, text[:500]
    except Exception as e:
        return -1, None, repr(e)


def flatten_event_response(obj: Any) -> list[dict[str, Any]]:
    """Convert possible Gamma event responses into a list of event dicts."""
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ["events", "data", "results", "items"]:
            if isinstance(obj.get(key), list):
                return [x for x in obj[key] if isinstance(x, dict)]
        # Event object itself.
        if any(k in obj for k in ["slug", "markets", "title", "id"]):
            return [obj]
    return []


# -----------------------------
# HKO target parser
# -----------------------------


def _find_col(cols: Iterable[Any], terms: list[str], forbidden: list[str] | None = None) -> Any | None:
    forbidden = forbidden or []
    for c in cols:
        s = str(c).strip().lower()
        if all(t.lower() in s for t in terms) and not any(f.lower() in s for f in forbidden):
            return c
    return None


def parse_hko_clmmaxt() -> pd.DataFrame:
    """Parse official HKO CLMMAXT daily maximum temperature dataset robustly."""
    urls = [
        "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php?dataType=CLMMAXT&rformat=csv&station=HKO",
        "https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKO_MAXT_2026.csv",
        "https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKO_MAXT_2026.csv",
    ]
    frames: list[pd.DataFrame] = []

    for source_i, url in enumerate(urls, start=1):
        label = ["CLMMAXT_opendata", "daily_HKO_MAXT_2026_csdi", "daily_HKO_MAXT_2026_cis"][source_i - 1]
        print(f"Fetching HKO source: {label} -> {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            print("  status:", r.status_code, "bytes:", len(r.content))
            if r.status_code >= 400:
                continue
            text = r.text
            (DATA_RAW / f"18e_v2_hko_{label}.csv").write_text(text, encoding="utf-8")
        except Exception as e:
            print("  failed:", e)
            continue

        for skip in range(0, 12):
            try:
                df = pd.read_csv(StringIO(text), skiprows=skip)
            except Exception:
                continue
            if df.empty or df.shape[1] < 2:
                continue

            cols = list(df.columns)
            year_col = _find_col(cols, ["year"]) or _find_col(cols, ["年"])
            month_col = _find_col(cols, ["month"]) or _find_col(cols, ["月"])
            day_col = _find_col(cols, ["day"]) or _find_col(cols, ["日"])
            value_col = (
                _find_col(cols, ["value"], ["completeness"])
                or _find_col(cols, ["數值"], ["完整性"])
                or _find_col(cols, ["maxt"], ["completeness"])
                or _find_col(cols, ["maximum"], ["completeness"])
            )

            # Route A: year/month/day/value columns.
            if all([year_col, month_col, day_col, value_col]):
                out = pd.DataFrame({
                    "event_date": pd.to_datetime(
                        df[[year_col, month_col, day_col]].rename(columns={year_col: "year", month_col: "month", day_col: "day"}),
                        errors="coerce",
                    ).dt.date,
                    "hko_tmax_C": pd.to_numeric(df[value_col], errors="coerce"),
                })
                out["hko_source_name"] = label
                out["hko_source_url"] = url
                out["hko_parse_route"] = f"ymd_value_header_skip_{skip}"
                frames.append(out)
                break

            # Route B: rows are year,month,day,value,unit but header is actually first data row.
            if df.shape[1] >= 4:
                tmp = df.copy()
                # Add original header values as a row, because sometimes skip offset makes header into data.
                try:
                    header_row = pd.DataFrame([list(df.columns)], columns=df.columns)
                    tmp = pd.concat([header_row, df], ignore_index=True)
                except Exception:
                    pass

                y = pd.to_numeric(tmp.iloc[:, 0], errors="coerce")
                m = pd.to_numeric(tmp.iloc[:, 1], errors="coerce")
                d = pd.to_numeric(tmp.iloc[:, 2], errors="coerce")
                v = pd.to_numeric(tmp.iloc[:, 3], errors="coerce")
                if y.notna().sum() > 10 and m.notna().sum() > 10 and d.notna().sum() > 10 and v.notna().sum() > 10:
                    out = pd.DataFrame({
                        "event_date": pd.to_datetime({"year": y, "month": m, "day": d}, errors="coerce").dt.date,
                        "hko_tmax_C": v,
                    })
                    out["hko_source_name"] = label
                    out["hko_source_url"] = url
                    out["hko_parse_route"] = f"positional_ymdv_skip_{skip}"
                    frames.append(out)
                    break

    if not frames:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source_name", "hko_source_url", "hko_parse_route"])

    hko = pd.concat(frames, ignore_index=True)
    hko = hko.dropna(subset=["event_date", "hko_tmax_C"])
    hko = hko.sort_values(["event_date", "hko_source_name"]).drop_duplicates("event_date", keep="first")
    hko = hko.sort_values("event_date").reset_index(drop=True)
    print("Official HKO target rows:", len(hko))
    if len(hko):
        print("Official HKO date range:", hko["event_date"].min(), "to", hko["event_date"].max())
        print(hko.tail(10).to_string(index=False))
    return hko


# -----------------------------
# Polymarket discovery
# -----------------------------


MONTH_SLUGS = [
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"
]


def candidate_slugs_for_date(d: date) -> list[str]:
    m = MONTH_SLUGS[d.month - 1]
    day = d.day
    y = d.year
    return [
        f"highest-temperature-in-hong-kong-on-{m}-{day}-{y}",
        f"highest-temperature-in-hong-kong-on-{m}-{day}",
        f"hong-kong-highest-temperature-on-{m}-{day}-{y}",
        f"what-will-the-highest-temperature-in-hong-kong-be-on-{m}-{day}-{y}",
        f"will-the-highest-temperature-in-hong-kong-be-on-{m}-{day}-{y}",
    ]


def fetch_event_by_slug(slug: str) -> list[dict[str, Any]]:
    endpoints = [
        (f"{GAMMA_BASE}/events/slug/{slug}", None),
        (f"{GAMMA_BASE}/events", {"slug": slug, "closed": "true"}),
        (f"{GAMMA_BASE}/events", {"slug": slug}),
    ]
    out: list[dict[str, Any]] = []
    for url, params in endpoints:
        status, obj, preview = http_get_json(url, params=params)
        if status == 200 and obj is not None:
            events = flatten_event_response(obj)
            if events:
                for ev in events:
                    ev.setdefault("_fetch_url", url)
                    ev.setdefault("_fetch_params", params)
                    ev.setdefault("_probe_slug", slug)
                out.extend(events)
                break
        time.sleep(REQUEST_SLEEP_SECONDS)
    return out


def gamma_search_fallback() -> list[dict[str, Any]]:
    """Fallback searches if direct slug probing is insufficient."""
    searches = [
        ("events", {"q": "highest temperature in hong kong", "closed": "true", "limit": 200, "offset": 0}),
        ("events", {"q": "hong kong temperature", "closed": "true", "limit": 200, "offset": 0}),
        ("markets", {"q": "highest temperature in hong kong", "closed": "true", "limit": 200, "offset": 0}),
        ("markets", {"q": "hong kong temperature", "closed": "true", "limit": 200, "offset": 0}),
    ]
    events: list[dict[str, Any]] = []
    for kind, params in searches:
        url = f"{GAMMA_BASE}/{kind}"
        status, obj, preview = http_get_json(url, params=params)
        print(f"fallback {kind} {params}: status={status}")
        if status == 200 and obj is not None:
            if kind == "events":
                rows = flatten_event_response(obj)
            else:
                rows = []
                # Markets may not include parent events. Treat each market as pseudo-event with one market.
                markets = flatten_event_response(obj)
                for m in markets:
                    rows.append({
                        "id": m.get("eventId") or m.get("event_id") or m.get("id"),
                        "slug": m.get("eventSlug") or m.get("event_slug") or m.get("slug"),
                        "title": m.get("eventTitle") or m.get("event_title") or m.get("title") or m.get("question"),
                        "markets": [m],
                        "_from_market_search": True,
                    })
            for ev in rows:
                ev.setdefault("_fallback_kind", kind)
                ev.setdefault("_fallback_params", params)
            events.extend(rows)
        time.sleep(REQUEST_SLEEP_SECONDS)
    return events


def discover_hk_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    d = HISTORICAL_START
    total_dates = 0
    while d <= HISTORICAL_END:
        total_dates += 1
        for slug in candidate_slugs_for_date(d):
            fetched = fetch_event_by_slug(slug)
            for ev in fetched:
                key = str(ev.get("id") or ev.get("slug") or json.dumps(ev, sort_keys=True)[:200])
                if key not in seen_keys:
                    seen_keys.add(key)
                    ev["_target_date_from_probe"] = str(d)
                    events.append(ev)
                    print("FOUND event:", d, ev.get("slug"), ev.get("title"))
            # If the main expected slug works, no need to try variants too much.
            if fetched and slug.startswith("highest-temperature-in-hong-kong-on-"):
                break
        if total_dates % 20 == 0:
            print(f"Probed dates through {d}; events found so far: {len(events)}")
        d += timedelta(days=1)

    fallback = gamma_search_fallback()
    for ev in fallback:
        text = norm_text(ev.get("slug"), ev.get("title"), ev.get("question"))
        if "hong kong" in text and "temperature" in text:
            key = str(ev.get("id") or ev.get("slug") or json.dumps(ev, sort_keys=True)[:200])
            if key not in seen_keys:
                seen_keys.add(key)
                events.append(ev)

    write_json(RAW_GAMMA / "18e_v2_polymarket_hk_events_raw.json", events)
    print("Raw Gamma HK events discovered:", len(events))
    return events


# -----------------------------
# Event / market parsing
# -----------------------------


def parse_event_date_from_text(*parts: Any) -> date | None:
    text = " ".join(str(p) for p in parts if p is not None).lower()
    # direct ISO
    m = re.search(r"(20\d{2})[-_/](\d{1,2})[-_/](\d{1,2})", text)
    if m:
        try:
            return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3))).date()
        except Exception:
            pass
    # month-day-year slug/text
    months = "|".join(MONTH_SLUGS)
    m = re.search(rf"\b({months})[-\s]+(\d{{1,2}})(?:st|nd|rd|th)?[-\s,]+(20\d{{2}})\b", text)
    if m:
        try:
            return pd.Timestamp(year=int(m.group(3)), month=MONTH_SLUGS.index(m.group(1)) + 1, day=int(m.group(2))).date()
        except Exception:
            pass
    # month-day, assume 2026.
    m = re.search(rf"\b({months})[-\s]+(\d{{1,2}})(?:st|nd|rd|th)?\b", text)
    if m:
        try:
            return pd.Timestamp(year=2026, month=MONTH_SLUGS.index(m.group(1)) + 1, day=int(m.group(2))).date()
        except Exception:
            pass
    return None


def parse_threshold_k(*parts: Any) -> float | None:
    text = " ".join(str(p) for p in parts if p is not None).lower()
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:°|degrees?|deg)?\s*c\s*(?:or\s*higher|or\s*above|and\s*above|or\s*more|\+)",
        r"(\d+(?:\.\d+)?)\s*c\s*or-higher",
        r"or-higher.*?(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)corhigher",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    # slug e.g. july-8-2026-35corhigher or 35c-or-higher
    m = re.search(r"-(\d+(?:\.\d+)?)c?orhigher\b", text)
    if m:
        return float(m.group(1))
    return None


def looks_upper_tail(*parts: Any) -> bool:
    text = " ".join(str(p) for p in parts if p is not None).lower()
    return bool(re.search(r"or\s*higher|or-higher|or\s*above|and\s*above|or\s*more", text))


def extract_yes_token_id(market: dict[str, Any]) -> tuple[str | None, str]:
    outcomes = parse_jsonish(market.get("outcomes"))
    token_ids = parse_jsonish(market.get("clobTokenIds") or market.get("clobTokenIDs") or market.get("clob_token_ids"))

    if isinstance(outcomes, str):
        outcomes = [x.strip() for x in outcomes.split(",")]
    if isinstance(token_ids, str):
        token_ids = [x.strip() for x in re.split(r"[,|]", token_ids) if x.strip()]

    if isinstance(outcomes, list) and isinstance(token_ids, list) and len(outcomes) == len(token_ids):
        for out, tok in zip(outcomes, token_ids):
            if str(out).strip().lower() == "yes":
                return str(tok), "matched_yes_outcome_to_clobTokenIds"
        if len(token_ids) == 2:
            return str(token_ids[0]), "fallback_first_binary_token"
    if isinstance(token_ids, list) and len(token_ids):
        return str(token_ids[0]), "fallback_first_token"
    return None, "no_clob_token_id_found"


def flatten_events(events: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ev in events:
        markets = ev.get("markets") or ev.get("Markets") or []
        if isinstance(markets, str):
            markets = parse_jsonish(markets) or []
        if isinstance(markets, dict):
            markets = [markets]
        if not isinstance(markets, list):
            markets = []

        if not markets:
            # Treat event itself as one market if it has market fields.
            markets = [ev]

        for mk in markets:
            if not isinstance(mk, dict):
                continue
            ev_slug = ev.get("slug") or mk.get("eventSlug") or mk.get("event_slug") or mk.get("slug")
            ev_title = ev.get("title") or ev.get("question") or mk.get("eventTitle") or mk.get("event_title")
            m_slug = mk.get("slug") or mk.get("marketSlug") or mk.get("market_slug")
            m_question = mk.get("question") or mk.get("title") or mk.get("marketQuestion")
            m_title = mk.get("title") or mk.get("question")
            description = mk.get("description") or ev.get("description") or ""
            rules = mk.get("rules") or ev.get("rules") or ""
            resolution_source = mk.get("resolutionSource") or ev.get("resolutionSource") or ""
            combined = norm_text(ev_slug, ev_title, m_slug, m_question, m_title, description, rules, resolution_source)
            event_date = parse_event_date_from_text(ev_slug, ev_title, m_slug, m_question, m_title, ev.get("_target_date_from_probe"))
            threshold_k = parse_threshold_k(m_slug, m_question, m_title)
            upper = looks_upper_tail(m_slug, m_question, m_title)
            yes_token_id, yes_token_method = extract_yes_token_id(mk)
            outcomes = parse_jsonish(mk.get("outcomes"))

            rows.append({
                "event_id": ev.get("id") or mk.get("eventId") or mk.get("event_id"),
                "event_slug": ev_slug,
                "event_title": ev_title,
                "event_date": event_date,
                "market_id": mk.get("id") or mk.get("conditionId") or mk.get("questionID"),
                "market_slug": m_slug,
                "market_question": m_question,
                "market_title": m_title,
                "outcome_label_text": " | ".join(map(str, outcomes)) if isinstance(outcomes, list) else str(outcomes),
                "threshold_K": threshold_k,
                "looks_upper_tail": upper,
                "yes_token_id": yes_token_id,
                "yes_token_method": yes_token_method,
                "volume": mk.get("volume") or mk.get("volumeNum"),
                "liquidity": mk.get("liquidity") or mk.get("liquidityNum"),
                "closed": mk.get("closed") or ev.get("closed"),
                "active": mk.get("active") or ev.get("active"),
                "createdAt": mk.get("createdAt") or ev.get("createdAt"),
                "endDate": mk.get("endDate") or ev.get("endDate"),
                "description": description,
                "rules": rules,
                "resolutionSource": resolution_source,
                "combined_rule_text": combined,
                "raw_event_json_path": str(RAW_GAMMA / "18e_v2_polymarket_hk_events_raw.json"),
            })
    df = pd.DataFrame(rows)
    if len(df):
        df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date
        df = df.drop_duplicates(["event_slug", "market_slug", "market_id", "threshold_K", "yes_token_id"]).reset_index(drop=True)
    print("Flattened child market rows:", df.shape)
    return df


def classify_contracts(df: pd.DataFrame, hko: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=list(df.columns) + ["rule_family", "empirical_role", "exclusion_reason", "hko_tmax_C", "hko_outcome_available", "Y_ge_K"])

    out = df.copy()
    text = out["combined_rule_text"].fillna("").astype(str).str.lower()
    out["has_hong_kong"] = text.str.contains("hong kong") | out["event_slug"].fillna("").astype(str).str.lower().str.contains("hong-kong")
    out["has_highest_temperature"] = text.str.contains("highest temperature") | out["event_slug"].fillna("").astype(str).str.lower().str.contains("highest-temperature")
    out["has_hko_rule_text"] = text.str.contains("hko|hong kong observatory", regex=True)
    out["has_absolute_daily_max_rule_text"] = text.str.contains("absolute daily max|daily max", regex=True)
    out["has_daily_extract_rule_text"] = text.str.contains("daily extract", regex=False)
    out["has_one_decimal_rule_text"] = text.str.contains("one-decimal|one decimal|1 decimal|one decimal place|0.1", regex=True)
    out["contradiction_wrong_direction"] = text.str.contains("lowest temperature")
    out["contradiction_airport_or_wunderground"] = text.str.contains("wunderground|airport|international airport")
    out["contradiction_whole_degree"] = text.str.contains("whole degree|integer degree|nearest degree")

    strict_hko = (
        out["has_hong_kong"]
        & out["has_highest_temperature"]
        & out["has_hko_rule_text"]
        & out["has_absolute_daily_max_rule_text"]
        & out["has_daily_extract_rule_text"]
        & out["has_one_decimal_rule_text"]
        & ~out["contradiction_wrong_direction"]
        & ~out["contradiction_airport_or_wunderground"]
        & ~out["contradiction_whole_degree"]
    )

    hko_family_looser = (
        out["has_hong_kong"]
        & out["has_highest_temperature"]
        & (out["has_hko_rule_text"] | text.str.contains("daily extract") | text.str.contains("absolute daily max"))
        & ~out["contradiction_wrong_direction"]
        & ~out["contradiction_airport_or_wunderground"]
    )

    out["rule_family"] = np.select(
        [strict_hko, hko_family_looser, out["contradiction_airport_or_wunderground"], out["contradiction_wrong_direction"]],
        ["strict_hko_daily_extract_one_decimal", "hko_family_but_boundary_uncertain", "airport_or_wunderground_source", "lowest_temperature_or_wrong_direction"],
        default="unknown_or_insufficient_rule_text",
    )

    out["empirical_role"] = np.select(
        [strict_hko & out["looks_upper_tail"].fillna(False), hko_family_looser & out["looks_upper_tail"].fillna(False), strict_hko & ~out["looks_upper_tail"].fillna(False)],
        ["formally_certified_threshold_contract", "empirically_supported_threshold_candidate", "categorical_descriptive_only"],
        default="excluded",
    )

    reasons = []
    for _, r in out.iterrows():
        if r["empirical_role"] != "excluded":
            reasons.append("")
        elif not bool(r.get("has_hong_kong")):
            reasons.append("not_hong_kong")
        elif bool(r.get("contradiction_wrong_direction")):
            reasons.append("lowest_temperature_wrong_direction")
        elif bool(r.get("contradiction_airport_or_wunderground")):
            reasons.append("non_hko_airport_or_wunderground")
        elif not bool(r.get("looks_upper_tail")):
            reasons.append("not_upper_tail_threshold")
        elif pd.isna(r.get("threshold_K")):
            reasons.append("threshold_not_parsed")
        else:
            reasons.append("insufficient_rule_text")
    out["exclusion_reason"] = reasons

    # Historical date filter and HKO join.
    out = out[pd.to_datetime(out["event_date"], errors="coerce").dt.date <= HISTORICAL_END].copy()
    hko_small = hko[["event_date", "hko_tmax_C", "hko_source_name", "hko_source_url", "hko_parse_route"]].drop_duplicates("event_date")
    out = out.merge(hko_small, on="event_date", how="left")
    out["hko_outcome_available"] = out["hko_tmax_C"].notna()
    out["Y_ge_K"] = np.where(
        out["hko_outcome_available"] & out["threshold_K"].notna(),
        (out["hko_tmax_C"] >= out["threshold_K"]).astype(int),
        np.nan,
    )
    return out.reset_index(drop=True)


# -----------------------------
# Price history and no-lookahead
# -----------------------------


def fetch_price_history(token_id: str, label: str) -> dict[str, Any]:
    params_list = [
        {"market": token_id, "interval": "max", "fidelity": 60},
        {"market": token_id, "interval": "all", "fidelity": 60},
        {"market": token_id, "fidelity": 60},
    ]
    for params in params_list:
        status, obj, preview = http_get_json(f"{CLOB_BASE}/prices-history", params=params, timeout=30)
        if status == 200 and obj is not None:
            out = {"status": status, "params": params, "response": obj}
            write_json(RAW_PRICE / f"{safe_slug(label)}__{token_id}.json", out)
            return out
        time.sleep(PRICE_REQUEST_SLEEP_SECONDS)
    out = {"status": "failed", "token_id": token_id}
    write_json(RAW_PRICE / f"{safe_slug(label)}__{token_id}__failed.json", out)
    return out


def normalise_price_history(resp: dict[str, Any], base_row: pd.Series) -> pd.DataFrame:
    if not resp or resp.get("status") == "failed":
        return pd.DataFrame()
    data = resp.get("response")
    hist = None
    if isinstance(data, dict):
        for key in ["history", "prices", "data"]:
            if isinstance(data.get(key), list):
                hist = data[key]
                break
    elif isinstance(data, list):
        hist = data
    if not hist:
        return pd.DataFrame()

    rows = []
    for item in hist:
        if not isinstance(item, dict):
            continue
        ts = item.get("t") or item.get("timestamp") or item.get("time") or item.get("x")
        price = item.get("p") or item.get("price") or item.get("value") or item.get("y")
        try:
            ts_num = float(ts)
            if ts_num > 10_000_000_000:
                ts_num = ts_num / 1000.0
            ts_utc = pd.to_datetime(ts_num, unit="s", utc=True)
        except Exception:
            ts_utc = pd.to_datetime(ts, utc=True, errors="coerce")
        rows.append({
            "event_date": base_row.get("event_date"),
            "threshold_K": base_row.get("threshold_K"),
            "event_slug": base_row.get("event_slug"),
            "market_slug": base_row.get("market_slug"),
            "market_id": base_row.get("market_id"),
            "yes_token_id": base_row.get("yes_token_id"),
            "price_timestamp_utc": ts_utc,
            "yes_price": pd.to_numeric(price, errors="coerce"),
            "empirical_role": base_row.get("empirical_role"),
            "rule_family": base_row.get("rule_family"),
            "hko_tmax_C": base_row.get("hko_tmax_C"),
            "Y_ge_K": base_row.get("Y_ge_K"),
        })
    out = pd.DataFrame(rows)
    out = out.dropna(subset=["price_timestamp_utc", "yes_price"])
    if len(out):
        out["price_timestamp_hkt"] = out["price_timestamp_utc"].dt.tz_convert(HK_TZ)
    return out


def retrieve_prices(candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panels: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, Any]] = []
    for i, row in candidates.reset_index(drop=True).iterrows():
        token_id = row.get("yes_token_id")
        label = f"{row.get('event_slug')}__K{row.get('threshold_K')}"
        if not token_id or str(token_id).lower() in {"nan", "none"}:
            coverage_rows.append({**row.to_dict(), "price_history_status": "missing_yes_token", "price_rows": 0})
            continue
        print(f"Fetching price history {i+1}/{len(candidates)}: {label}")
        resp = fetch_price_history(str(token_id), label)
        panel = normalise_price_history(resp, row)
        coverage_rows.append({**row.to_dict(), "price_history_status": "ok" if len(panel) else "empty", "price_rows": len(panel)})
        if len(panel):
            panels.append(panel)
        time.sleep(PRICE_REQUEST_SLEEP_SECONDS)
    price_panel = pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()
    coverage = pd.DataFrame(coverage_rows)
    return price_panel, coverage


def build_decision_panel(price_panel: pd.DataFrame) -> pd.DataFrame:
    if price_panel.empty:
        return pd.DataFrame()
    rows = []
    grouped = price_panel.sort_values("price_timestamp_utc").groupby(["event_slug", "market_slug", "threshold_K", "yes_token_id"], dropna=False)
    for key, g in grouped:
        first = g.iloc[0]
        ev_date = pd.to_datetime(first["event_date"]).date()
        event_start_hkt = pd.Timestamp(datetime(ev_date.year, ev_date.month, ev_date.day, 0, 0, tzinfo=HK_TZ))
        cutoffs = {
            "last_price_before_event_day_hkt": event_start_hkt,
            "last_price_before_24h_prior": event_start_hkt - pd.Timedelta(hours=24),
            "last_price_before_12h_prior": event_start_hkt - pd.Timedelta(hours=12),
        }
        for rule, cutoff_hkt in cutoffs.items():
            cutoff_utc = cutoff_hkt.tz_convert("UTC")
            eligible = g[g["price_timestamp_utc"] <= cutoff_utc]
            if eligible.empty:
                continue
            r = eligible.iloc[-1].to_dict()
            r.update({
                "decision_rule": rule,
                "decision_cutoff_hkt": cutoff_hkt,
                "decision_cutoff_utc": cutoff_utc,
                "decision_timestamp_utc": eligible.iloc[-1]["price_timestamp_utc"],
                "decision_timestamp_hkt": eligible.iloc[-1]["price_timestamp_hkt"],
                "p_market": eligible.iloc[-1]["yes_price"],
                "no_lookahead_valid": True,
                "hours_before_event_start": (event_start_hkt - eligible.iloc[-1]["price_timestamp_hkt"]) / pd.Timedelta(hours=1),
            })
            rows.append(r)
    out = pd.DataFrame(rows)
    return out


def score_market(decision: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if decision.empty:
        summary = pd.DataFrame(columns=["decision_rule", "empirical_role", "n", "mean_brier", "mean_log_score", "mean_p_market", "outcome_rate"])
        return decision, summary
    out = decision.copy()
    out = out[out["Y_ge_K"].notna() & out["p_market"].notna()].copy()
    if out.empty:
        summary = pd.DataFrame(columns=["decision_rule", "empirical_role", "n", "mean_brier", "mean_log_score", "mean_p_market", "outcome_rate"])
        return out, summary
    y = pd.to_numeric(out["Y_ge_K"], errors="coerce")
    p = pd.to_numeric(out["p_market"], errors="coerce").clip(1e-6, 1 - 1e-6)
    out["brier_market"] = (p - y) ** 2
    out["log_score_market"] = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    summary = out.groupby(["decision_rule", "empirical_role"], dropna=False).agg(
        n=("p_market", "size"),
        mean_brier=("brier_market", "mean"),
        mean_log_score=("log_score_market", "mean"),
        mean_p_market=("p_market", "mean"),
        outcome_rate=("Y_ge_K", "mean"),
    ).reset_index()
    return out, summary


# -----------------------------
# Main
# -----------------------------


def main() -> None:
    print("Repository root:", ROOT)
    print("Historical official-outcome end date:", HISTORICAL_END)

    hko = parse_hko_clmmaxt()
    hko = hko[pd.to_datetime(hko["event_date"], errors="coerce").dt.date <= HISTORICAL_END].copy()
    hko_out = DATA_PROCESSED / "18e_hko_daily_max_targets_to_20260531.csv"
    hko.to_csv(hko_out, index=False)

    events = discover_hk_events()
    child = flatten_events(events)
    child.to_csv(DATA_PROCESSED / "18e_v2_flattened_polymarket_children_debug.csv", index=False)

    universe = classify_contracts(child, hko)
    # Keep all historical rows, including excluded, for audit.
    contract_out = DATA_PROCESSED / "18e_hko_historical_contract_universe_to_20260531.csv"
    universe.to_csv(contract_out, index=False)

    print("\nHK historical contract universe:", universe.shape)
    if len(universe):
        print("Classification counts:")
        print(universe["empirical_role"].value_counts(dropna=False))
        print("Rule family counts:")
        print(universe["rule_family"].value_counts(dropna=False))
        print("Exclusion reason counts:")
        print(universe["exclusion_reason"].value_counts(dropna=False).head(20))

    candidates = universe[
        universe["empirical_role"].isin(["formally_certified_threshold_contract", "empirically_supported_threshold_candidate"])
        & universe["hko_outcome_available"].fillna(False)
        & universe["yes_token_id"].notna()
        & universe["threshold_K"].notna()
    ].copy()
    cand_out = DATA_PROCESSED / "18e_hko_historical_threshold_candidate_panel_to_20260531.csv"
    candidates.to_csv(cand_out, index=False)
    print("\nThreshold candidates with HKO outcome and YES token:", candidates.shape)

    if len(candidates):
        price_panel, coverage = retrieve_prices(candidates)
    else:
        print("No threshold candidates available for price retrieval.")
        price_panel, coverage = pd.DataFrame(), pd.DataFrame()

    price_out = DATA_PROCESSED / "18e_hko_historical_price_history_panel_to_20260531.csv"
    coverage_out = DATA_PROCESSED / "18e_hko_historical_price_coverage_summary_to_20260531.csv"
    price_panel.to_csv(price_out, index=False)
    coverage.to_csv(coverage_out, index=False)
    print("\nPrice panel shape:", price_panel.shape)

    decision = build_decision_panel(price_panel)
    decision_out = DATA_PROCESSED / "18e_hko_historical_no_lookahead_decision_panel_to_20260531.csv"
    decision.to_csv(decision_out, index=False)
    print("Decision panel shape:", decision.shape)

    scoring, summary = score_market(decision)
    scoring_out = DATA_PROCESSED / "18e_hko_historical_scoring_ready_market_panel_to_20260531.csv"
    scores_out = DATA_PROCESSED / "18e_hko_historical_market_only_scores_to_20260531.csv"
    summary_out = DATA_PROCESSED / "18e_hko_historical_market_only_score_summary_to_20260531.csv"
    scoring.to_csv(scoring_out, index=False)
    scoring.to_csv(scores_out, index=False)
    summary.to_csv(summary_out, index=False)
    print("\nScoring-ready official HKO market panel shape:", scoring.shape)
    print("Market-only score summary:")
    print(summary.to_string(index=False) if len(summary) else "Empty DataFrame")

    report = []
    report.append("# 18e Hong Kong historical market--HKO alignment to 2026-05-31\n")
    report.append(f"Repository root: `{ROOT}`\n")
    report.append(f"Historical official-outcome end date: `{HISTORICAL_END}`\n")
    report.append("\n## HKO official target coverage\n")
    report.append(f"HKO target rows: `{len(hko)}`\n")
    if len(hko):
        report.append(f"HKO date range: `{hko['event_date'].min()}` to `{hko['event_date'].max()}`\n")
    report.append("\n## Polymarket universe coverage\n")
    report.append(f"Raw Gamma events discovered: `{len(events)}`\n")
    report.append(f"Flattened child rows: `{len(child)}`\n")
    report.append(f"Historical contract universe rows: `{len(universe)}`\n")
    report.append(f"Threshold candidate rows with official HKO outcome and YES token: `{len(candidates)}`\n")
    if len(universe):
        report.append("\n### Empirical role counts\n")
        report.append(universe["empirical_role"].value_counts(dropna=False).to_markdown())
        report.append("\n\n### Rule family counts\n")
        report.append(universe["rule_family"].value_counts(dropna=False).to_markdown())
    report.append("\n\n## Price history coverage\n")
    report.append(f"Price history panel rows: `{len(price_panel)}`\n")
    report.append("\n## No-lookahead decision panel\n")
    report.append(f"Decision panel rows: `{len(decision)}`\n")
    report.append(f"Official HKO scoring-ready rows: `{len(scoring)}`\n")
    report.append("\n## Market-only score summary\n")
    report.append(summary.to_markdown(index=False) if len(summary) else "_No official HKO scoring-ready rows were available after filtering._")
    report.append("\n\n## Interpretation\n")
    if len(scoring):
        report.append("The scaled historical alignment produced an official-HKO scoring-ready market panel. This panel can be used for market-implied probability scoring before forecast probabilities are joined.\n")
    elif len(universe):
        report.append("The scaled retrieval found Hong Kong historical contracts but no official-HKO scoring-ready rows after threshold, token, price and no-lookahead filters. The exclusion table should be inspected before deciding whether to loosen rule-family requirements.\n")
    else:
        report.append("No Hong Kong historical contract universe survived discovery and filtering. This indicates that the direct slug discovery/search route did not recover usable historical Hong Kong markets up to 31 May 2026. Further retrieval should focus on archived Polymarket event slugs or existing earlier audit files.\n")
    report_path = REPORTS / "18e_hko_historical_alignment_report.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print("\nSaved report:", report_path)
    print("\nKey outputs:")
    for p in [hko_out, contract_out, cand_out, price_out, coverage_out, decision_out, scoring_out, scores_out, summary_out, report_path]:
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
