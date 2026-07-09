#!/usr/bin/env python3
"""
18f HKO Daily Extract + deterministic Polymarket Hong Kong historical panel.

This script builds a scaled March--May 2026 Hong Kong temperature market panel by:
1. retrieving official HKO daily maximum temperature observations from the monthly Daily Extract/metob pages where possible, with CLMMAXT as an official fallback;
2. sweeping deterministic Polymarket event slugs from 13 March 2026 to 31 May 2026;
3. flattening binary child markets and identifying upper-tail K deg C or higher contracts;
4. joining market metadata to HKO realised outcomes under the floor-bin interpretation;
5. retrieving CLOB YES-token historical prices for upper-tail contracts;
6. producing no-lookahead decision snapshots and market-only Brier/log scores.

The script is intentionally fail-closed: it saves all diagnostics and does not pretend that
missing prices or missing event metadata are valid observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import calendar
import json
import math
import re
import time

import numpy as np
import pandas as pd
import requests

ROOT = Path.cwd()
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"
LOGS = ROOT / "logs"

RAW_HKO = RAW / "hko_daily_extract_18f"
RAW_GAMMA = RAW / "polymarket_gamma_18f"
RAW_WEB = RAW / "polymarket_web_18f"
RAW_PRICE = RAW / "polymarket_clob_price_history_18f"

for p in [RAW_HKO, RAW_GAMMA, RAW_WEB, RAW_PRICE, PROCESSED, REPORTS, LOGS]:
    p.mkdir(parents=True, exist_ok=True)

START_DATE = pd.Timestamp("2026-03-13").date()
END_DATE = pd.Timestamp("2026-05-31").date()
HKO_MONTHS = [(2026, 3), (2026, 4), (2026, 5)]
EPS = 1e-6
REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 Chrome/127 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

MONTH_NAME = {m: calendar.month_name[m].lower() for m in range(1, 13)}
MONTH_LOOKUP = {calendar.month_name[m].lower(): m for m in range(1, 13)}
MONTH_LOOKUP.update({calendar.month_abbr[m].lower(): m for m in range(1, 13)})


def normalise_text(x: Any) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip()


def slug_for_date(d: pd.Timestamp | pd.Timestamp.date) -> str:
    ts = pd.Timestamp(d)
    return f"highest-temperature-in-hong-kong-on-{calendar.month_name[ts.month].lower()}-{ts.day}-2026"


def date_range(start: pd.Timestamp.date, end: pd.Timestamp.date) -> List[pd.Timestamp.date]:
    return [d.date() for d in pd.date_range(start, end, freq="D")]


def safe_name(s: str, n: int = 160) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(s))[:n].strip("_") or "unnamed"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_text(url: str, raw_path: Optional[Path] = None) -> Optional[str]:
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        status = r.status_code
        text = r.text
        if raw_path is not None:
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(text, encoding="utf-8", errors="ignore")
        if status == 200 and text:
            return text
        return None
    except Exception as e:
        if raw_path is not None:
            raw_path.write_text(f"FETCH_ERROR: {e}\nURL: {url}", encoding="utf-8", errors="ignore")
        return None


# ---------------------------------------------------------------------------
# HKO extraction
# ---------------------------------------------------------------------------


def flatten_columns(cols: Iterable[Any]) -> List[str]:
    out: List[str] = []
    for c in cols:
        if isinstance(c, tuple):
            val = " ".join([normalise_text(x) for x in c if not str(x).startswith("Unnamed")])
        else:
            val = normalise_text(c)
        out.append(val)
    return out


def parse_numeric_value(x: Any) -> Optional[float]:
    if pd.isna(x):
        return None
    s = str(x).strip()
    s = s.replace("−", "-")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def parse_hko_tables_from_html(html: str, year: int, month: int, source_url: str, source_label: str) -> pd.DataFrame:
    """Try multiple table layouts for Daily Extract/metob pages."""
    frames: List[pd.DataFrame] = []
    try:
        tables = pd.read_html(StringIO(html))
    except Exception:
        tables = []

    for table_index, df0 in enumerate(tables):
        if df0.empty:
            continue

        df = df0.copy()
        df.columns = flatten_columns(df.columns)
        # Drop fully empty rows/columns.
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue

        cols = list(df.columns)
        low_cols = {c: c.lower() for c in cols}

        day_col = None
        for c in cols:
            lc = low_cols[c]
            if lc in {"day", "date", "day/month", "hkt day/month"} or "day" == lc.strip():
                day_col = c
                break
        if day_col is None:
            # Often the first column is the day number even if the header is unclear.
            first = cols[0]
            vals = pd.to_numeric(df[first], errors="coerce")
            if vals.between(1, 31).sum() >= min(10, len(df)):
                day_col = first

        if day_col is None:
            continue

        # Prefer columns that clearly identify maximum air temperature.
        tmax_col = None
        tmean_col = None
        tmin_col = None
        for c in cols:
            lc = low_cols[c]
            if c == day_col:
                continue
            if ("max" in lc or "maximum" in lc) and ("temp" in lc or "air" in lc or "temperature" in lc):
                tmax_col = c
                break
        if tmax_col is None:
            # Some HKO tables have short headers where consecutive cols are max, mean, min.
            numeric_cols = []
            for c in cols:
                if c == day_col:
                    continue
                vals = df[c].map(parse_numeric_value).dropna()
                if len(vals) >= min(10, len(df) // 2) and vals.between(-10, 45).mean() > 0.6:
                    numeric_cols.append(c)
            if numeric_cols:
                tmax_col = numeric_cols[0]
                if len(numeric_cols) > 1:
                    tmean_col = numeric_cols[1]
                if len(numeric_cols) > 2:
                    tmin_col = numeric_cols[2]

        # Try to locate mean/min if not assigned.
        for c in cols:
            lc = low_cols[c]
            if c == day_col or c == tmax_col:
                continue
            if tmean_col is None and ("mean" in lc or "average" in lc) and ("temp" in lc or "air" in lc):
                tmean_col = c
            if tmin_col is None and ("min" in lc or "minimum" in lc) and ("temp" in lc or "air" in lc):
                tmin_col = c

        if tmax_col is None:
            continue

        rows = []
        for _, row in df.iterrows():
            day_val = parse_numeric_value(row.get(day_col))
            if day_val is None:
                continue
            day = int(day_val)
            if day < 1 or day > calendar.monthrange(year, month)[1]:
                continue
            tmax = parse_numeric_value(row.get(tmax_col))
            if tmax is None:
                continue
            if not (-10 <= tmax <= 45):
                continue
            event_date = pd.Timestamp(year=year, month=month, day=day).date()
            rows.append({
                "event_date": event_date,
                "hko_tmax_C": tmax,
                "hko_tmean_C": parse_numeric_value(row.get(tmean_col)) if tmean_col is not None else np.nan,
                "hko_tmin_C": parse_numeric_value(row.get(tmin_col)) if tmin_col is not None else np.nan,
                "hko_source_url": source_url,
                "hko_source_label": source_label,
                "hko_parse_route": f"read_html_table_{table_index}",
                "hko_day_column": day_col,
                "hko_tmax_column": tmax_col,
            })
        if rows:
            frames.append(pd.DataFrame(rows))

    if frames:
        out = pd.concat(frames, ignore_index=True)
        out = out.sort_values(["event_date", "hko_source_label"]).drop_duplicates("event_date", keep="first")
        return out.reset_index(drop=True)

    return pd.DataFrame(columns=[
        "event_date", "hko_tmax_C", "hko_tmean_C", "hko_tmin_C", "hko_source_url",
        "hko_source_label", "hko_parse_route", "hko_day_column", "hko_tmax_column",
    ])


def parse_hko_clmmaxt_fallback() -> pd.DataFrame:
    """Official HKO daily maximum temperature fallback used only when Daily Extract tables cannot be parsed."""
    candidates = [
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
    frames: List[pd.DataFrame] = []
    for label, url in candidates:
        raw_path = RAW_HKO / f"{safe_name(label)}.csv"
        text = fetch_text(url, raw_path)
        if not text:
            continue
        for skip in range(0, 16):
            try:
                df = pd.read_csv(StringIO(text), skiprows=skip)
            except Exception:
                continue
            if df.empty or df.shape[1] < 3:
                continue
            cols = list(df.columns)
            low = {c: str(c).lower() for c in cols}
            y = next((c for c in cols if "year" in low[c] or "年" in low[c]), None)
            m = next((c for c in cols if "month" in low[c] or "月" in low[c]), None)
            d = next((c for c in cols if "day" in low[c] or "日" in low[c]), None)
            v = next((c for c in cols if ("value" in low[c] or "數值" in low[c] or "maxt" in low[c]) and "complete" not in low[c] and "完整" not in low[c]), None)
            if all([y, m, d, v]):
                dates = pd.to_datetime(
                    df[[y, m, d]].rename(columns={y: "year", m: "month", d: "day"}),
                    errors="coerce",
                )
                out = pd.DataFrame({
                    "event_date": dates.dt.date,
                    "hko_tmax_C": pd.to_numeric(df[v], errors="coerce"),
                    "hko_tmean_C": np.nan,
                    "hko_tmin_C": np.nan,
                    "hko_source_url": url,
                    "hko_source_label": label,
                    "hko_parse_route": f"clmmaxt_fallback_skip_{skip}",
                    "hko_day_column": d,
                    "hko_tmax_column": v,
                })
                out = out.dropna(subset=["event_date", "hko_tmax_C"])
                if len(out):
                    frames.append(out)
                    break
    if not frames:
        return pd.DataFrame(columns=[
            "event_date", "hko_tmax_C", "hko_tmean_C", "hko_tmin_C", "hko_source_url",
            "hko_source_label", "hko_parse_route", "hko_day_column", "hko_tmax_column",
        ])
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["event_date", "hko_source_label"]).drop_duplicates("event_date", keep="first")
    return out.reset_index(drop=True)


def build_hko_targets() -> pd.DataFrame:
    month_frames: List[pd.DataFrame] = []
    for year, month in HKO_MONTHS:
        source_urls = [
            ("metob_plain", f"https://www.hko.gov.hk/wxinfo/pastwx/metob{year}{month:02d}.htm"),
            ("metob_en", f"https://www.hko.gov.hk/en/wxinfo/pastwx/metob{year}{month:02d}.htm"),
            ("daily_extract_en", f"https://www.hko.gov.hk/en/cis/dailyExtract.htm?m={month}&y={year}"),
            ("daily_extract_plain", f"https://www.hko.gov.hk/cis/dailyExtract.htm?m={month}&y={year}"),
        ]
        month_outs = []
        for label, url in source_urls:
            raw_path = RAW_HKO / f"18f_hko_{label}_{year}{month:02d}.html"
            html = fetch_text(url, raw_path)
            if not html:
                continue
            parsed = parse_hko_tables_from_html(html, year, month, url, label)
            print(f"HKO {label} {year}-{month:02d}: parsed {len(parsed)} rows")
            if len(parsed):
                month_outs.append(parsed)
        if month_outs:
            mdf = pd.concat(month_outs, ignore_index=True).sort_values(["event_date", "hko_parse_route"])
            mdf = mdf.drop_duplicates("event_date", keep="first")
            month_frames.append(mdf)

    if month_frames:
        hko = pd.concat(month_frames, ignore_index=True)
    else:
        hko = pd.DataFrame()

    fallback = parse_hko_clmmaxt_fallback()
    fallback = fallback[(fallback["event_date"] >= pd.Timestamp("2026-03-01").date()) & (fallback["event_date"] <= END_DATE)].copy()

    if hko.empty:
        hko = fallback.copy()
    else:
        # Fill missing March-May days using official CLMMAXT fallback, but keep Daily Extract/metob as first source.
        have = set(hko["event_date"])
        fill = fallback[~fallback["event_date"].isin(have)].copy()
        if len(fill):
            hko = pd.concat([hko, fill], ignore_index=True)

    hko = hko[(hko["event_date"] >= pd.Timestamp("2026-03-01").date()) & (hko["event_date"] <= END_DATE)].copy()
    hko = hko.sort_values("event_date").drop_duplicates("event_date", keep="first").reset_index(drop=True)
    hko["hko_floor_bin_K"] = np.floor(hko["hko_tmax_C"].astype(float)).astype(int)
    return hko


# ---------------------------------------------------------------------------
# Polymarket/Gamma extraction
# ---------------------------------------------------------------------------


def fetch_gamma_event_by_slug(slug: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
    raw_path = RAW_GAMMA / f"event_{safe_name(slug)}.json"
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        meta = {"slug": slug, "url": url, "status_code": r.status_code}
        if r.status_code == 200 and r.text.strip():
            try:
                data = r.json()
                write_json(raw_path, data)
                return data if isinstance(data, dict) else None, meta
            except Exception as e:
                raw_path.write_text(r.text, encoding="utf-8", errors="ignore")
                meta["json_error"] = str(e)
                return None, meta
        raw_path.write_text(r.text or "", encoding="utf-8", errors="ignore")
        return None, meta
    except Exception as e:
        meta = {"slug": slug, "url": url, "error": str(e)}
        write_json(raw_path, meta)
        return None, meta


def fetch_polymarket_page(slug: str) -> Tuple[Optional[str], Dict[str, Any]]:
    url = f"https://polymarket.com/event/{slug}"
    raw_path = RAW_WEB / f"event_{safe_name(slug)}.html"
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        meta = {"slug": slug, "url": url, "status_code": r.status_code, "n_bytes": len(r.text or "")}
        raw_path.write_text(r.text or "", encoding="utf-8", errors="ignore")
        if r.status_code == 200 and r.text:
            return r.text, meta
        return None, meta
    except Exception as e:
        meta = {"slug": slug, "url": url, "error": str(e)}
        raw_path.write_text(json.dumps(meta), encoding="utf-8")
        return None, meta


def parse_jsonish(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (list, dict)):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        x = json.loads(s)
        if isinstance(x, str):
            try:
                return json.loads(x)
            except Exception:
                return x
        return x
    except Exception:
        return value


def parse_token_ids(value: Any) -> List[str]:
    x = parse_jsonish(value)
    ids: List[str] = []
    if isinstance(x, list):
        for item in x:
            ids.extend(parse_token_ids(item))
    elif isinstance(x, dict):
        for item in x.values():
            ids.extend(parse_token_ids(item))
    elif x is not None:
        s = str(x)
        ids.extend(re.findall(r"\d{20,}", s))
    # preserve order, unique
    seen = set()
    out = []
    for token in ids:
        if token not in seen:
            out.append(token)
            seen.add(token)
    return out


def get_yes_token_id(market: Dict[str, Any]) -> Optional[str]:
    for key in ["yes_token_id", "yesTokenId", "yes_token", "token_id"]:
        if key in market and market.get(key):
            ids = parse_token_ids(market.get(key))
            return ids[0] if ids else str(market.get(key))
    ids = parse_token_ids(market.get("clobTokenIds"))
    if ids:
        return ids[0]
    return None


def market_label_text(market: Dict[str, Any]) -> str:
    parts = []
    for key in ["outcome", "groupItemTitle", "title", "question", "description", "slug"]:
        val = market.get(key)
        if val:
            parts.append(str(val))
    return " | ".join(parts)


def extract_threshold_from_label(text: str) -> Optional[float]:
    s = str(text).replace("℃", "°C")
    patterns = [
        r"(\d{1,2}(?:\.\d+)?)\s*°?\s*C\s*(?:or\s*higher|or-higher|orhigher)",
        r"be\s+(\d{1,2}(?:\.\d+)?)\s*°?\s*C\s*(?:or\s+higher|or-higher|orhigher)",
        r"(\d{1,2}(?:\.\d+)?)\s*degrees?\s*(?:celsius)?\s*(?:or\s*higher|or-higher|orhigher)",
    ]
    for pat in patterns:
        m = re.search(pat, s, re.I)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    # Interior category fallback.
    m = re.search(r"(?:^|\b)(\d{1,2}(?:\.\d+)?)\s*°?\s*C(?:\b|$)", s, re.I)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    return None


def is_upper_tail_label(text: str) -> bool:
    s = str(text).lower().replace(" ", "")
    return "orhigher" in s


def is_lower_tail_label(text: str) -> bool:
    s = str(text).lower().replace(" ", "")
    return "orbelow" in s


def parse_event_markets(event: Dict[str, Any], event_date: pd.Timestamp.date, slug: str) -> List[Dict[str, Any]]:
    markets = event.get("markets") or []
    if isinstance(markets, str):
        markets = parse_jsonish(markets) or []
    if not isinstance(markets, list):
        markets = []

    event_description = normalise_text(event.get("description"))
    event_resolution_source = normalise_text(event.get("resolutionSource"))
    rule_text = " ".join([event_description, event_resolution_source])

    rows: List[Dict[str, Any]] = []
    for m in markets:
        if not isinstance(m, dict):
            continue
        label = market_label_text(m)
        question = normalise_text(m.get("question"))
        title = normalise_text(m.get("title"))
        mdesc = normalise_text(m.get("description"))
        combined = " ".join([label, question, title, mdesc, rule_text])
        threshold = extract_threshold_from_label(combined)
        yes_token = get_yes_token_id(m)

        outcomes = parse_jsonish(m.get("outcomes"))
        outcome_prices = parse_jsonish(m.get("outcomePrices"))
        resolved_outcome = m.get("resolvedOutcome") or m.get("outcome") or m.get("winningOutcome")

        rows.append({
            "event_date": event_date,
            "event_slug": slug,
            "event_title": event.get("title"),
            "event_id": event.get("id"),
            "event_url": f"https://polymarket.com/event/{slug}",
            "market_id": m.get("id"),
            "market_slug": m.get("slug"),
            "market_question": question,
            "market_title": title,
            "outcome_label_text": label,
            "threshold_K": threshold,
            "looks_upper_tail": is_upper_tail_label(combined),
            "looks_lower_tail": is_lower_tail_label(combined),
            "yes_token_id": yes_token,
            "clobTokenIds": m.get("clobTokenIds"),
            "outcomes": outcomes,
            "outcomePrices": outcome_prices,
            "resolvedOutcome": resolved_outcome,
            "closed": m.get("closed"),
            "active": m.get("active"),
            "volume": m.get("volume"),
            "liquidity": m.get("liquidity"),
            "createdAt": m.get("createdAt"),
            "endDate": m.get("endDate") or event.get("endDate"),
            "rule_text": rule_text,
            "event_description": event_description,
            "event_resolutionSource": event_resolution_source,
            "gamma_fetch_status": "found",
        })
    return rows


def parse_web_outcomes(html: str, event_date: pd.Timestamp.date, slug: str) -> List[Dict[str, Any]]:
    """Fallback parsing from rendered/static Polymarket text; no token ids."""
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"\s+", " ", text)
    rows: List[Dict[str, Any]] = []
    # Extract visible outcomes around things like 30°C Yes / 32°C or higher No.
    for m in re.finditer(r"(\d{1,2}\s*°C(?:\s*or\s*higher|\s*or\s*below)?)\s+(?:\$[\d,]+\s*Vol\.\s*)?(Yes|No)", text, re.I):
        label = normalise_text(m.group(1))
        final = normalise_text(m.group(2))
        threshold = extract_threshold_from_label(label)
        rows.append({
            "event_date": event_date,
            "event_slug": slug,
            "event_title": None,
            "event_id": None,
            "event_url": f"https://polymarket.com/event/{slug}",
            "market_id": None,
            "market_slug": None,
            "market_question": None,
            "market_title": None,
            "outcome_label_text": label,
            "threshold_K": threshold,
            "looks_upper_tail": is_upper_tail_label(label),
            "looks_lower_tail": is_lower_tail_label(label),
            "yes_token_id": None,
            "clobTokenIds": None,
            "outcomes": None,
            "outcomePrices": None,
            "resolvedOutcome": final,
            "closed": None,
            "active": None,
            "volume": None,
            "liquidity": None,
            "createdAt": None,
            "endDate": None,
            "rule_text": text[:3000],
            "event_description": None,
            "event_resolutionSource": None,
            "gamma_fetch_status": "web_fallback",
        })
    return rows


def sweep_polymarket_events() -> Tuple[pd.DataFrame, pd.DataFrame]:
    event_rows: List[Dict[str, Any]] = []
    child_rows: List[Dict[str, Any]] = []

    for event_date in date_range(START_DATE, END_DATE):
        slug = slug_for_date(event_date)
        event, gamma_meta = fetch_gamma_event_by_slug(slug)
        html, web_meta = fetch_polymarket_page(slug)

        event_status = {
            "event_date": event_date,
            "event_slug": slug,
            "event_url": f"https://polymarket.com/event/{slug}",
            "gamma_status_code": gamma_meta.get("status_code"),
            "gamma_error": gamma_meta.get("error") or gamma_meta.get("json_error"),
            "web_status_code": web_meta.get("status_code"),
            "web_n_bytes": web_meta.get("n_bytes"),
            "event_found_gamma": bool(event),
            "event_found_web": bool(html),
        }

        rows = []
        if event:
            rows = parse_event_markets(event, event_date, slug)
            event_status.update({
                "event_title": event.get("title"),
                "event_id": event.get("id"),
                "n_gamma_markets": len(event.get("markets") or []),
            })
        if not rows and html:
            rows = parse_web_outcomes(html, event_date, slug)
            event_status["n_web_outcomes"] = len(rows)

        event_status["flattened_child_rows"] = len(rows)
        event_rows.append(event_status)
        child_rows.extend(rows)
        print(f"{event_date} {slug}: gamma={event_status['event_found_gamma']} web={event_status['event_found_web']} child_rows={len(rows)}")
        time.sleep(0.15)

    events = pd.DataFrame(event_rows)
    children = pd.DataFrame(child_rows)
    return events, children


# ---------------------------------------------------------------------------
# Validation, prices and scoring
# ---------------------------------------------------------------------------


def build_validation_panels(children: pd.DataFrame, hko: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if children.empty:
        empty = pd.DataFrame()
        return empty, empty

    out = children.copy()
    out["event_date"] = pd.to_datetime(out["event_date"]).dt.date
    out = out.merge(hko[["event_date", "hko_tmax_C", "hko_floor_bin_K", "hko_source_label", "hko_source_url", "hko_parse_route"]], on="event_date", how="left")
    out["hko_outcome_available"] = out["hko_tmax_C"].notna()
    out["threshold_K"] = pd.to_numeric(out["threshold_K"], errors="coerce")

    out["Y_ge_K"] = np.where(out["hko_outcome_available"] & out["threshold_K"].notna(), (out["hko_tmax_C"] >= out["threshold_K"]).astype(int), np.nan)
    out["Y_floor_bin_K"] = np.where(out["hko_outcome_available"] & out["threshold_K"].notna(), (out["hko_floor_bin_K"] == out["threshold_K"]).astype(int), np.nan)

    # Public rule text indicators.
    text = (
        out.get("rule_text", pd.Series(index=out.index, dtype=str)).fillna("") + " "
        + out.get("event_description", pd.Series(index=out.index, dtype=str)).fillna("") + " "
        + out.get("market_question", pd.Series(index=out.index, dtype=str)).fillna("") + " "
        + out.get("outcome_label_text", pd.Series(index=out.index, dtype=str)).fillna("")
    ).str.lower()
    out["has_hko_rule_text"] = text.str.contains("hong kong observatory|hko", regex=True, na=False)
    out["has_absolute_daily_max_rule_text"] = text.str.contains("absolute daily max", regex=False, na=False)
    out["has_daily_extract_rule_text"] = text.str.contains("daily extract", regex=False, na=False)
    out["has_one_decimal_rule_text"] = text.str.contains("one decimal|9.1|decimal place", regex=True, na=False)
    out["has_later_revision_exclusion"] = text.str.contains("revision|revisions|initially published|finalized|finalised", regex=True, na=False)
    out["is_hko_highest_temp_family"] = text.str.contains("highest temperature", regex=False, na=False) & (out["has_hko_rule_text"] | text.str.contains("hong kong", regex=False, na=False))

    out["empirical_role"] = "excluded_or_descriptive"
    out.loc[out["looks_upper_tail"].fillna(False) & out["hko_outcome_available"].fillna(False), "empirical_role"] = "upper_tail_threshold_candidate"
    out.loc[
        out["looks_upper_tail"].fillna(False)
        & out["hko_outcome_available"].fillna(False)
        & out["has_hko_rule_text"].fillna(False)
        & out["has_absolute_daily_max_rule_text"].fillna(False)
        & out["has_daily_extract_rule_text"].fillna(False)
        & out["has_one_decimal_rule_text"].fillna(False),
        "empirical_role",
    ] = "formally_certified_upper_tail_threshold"

    category_panel = out.copy()
    upper_tail = out[
        out["looks_upper_tail"].fillna(False)
        & out["hko_outcome_available"].fillna(False)
        & out["threshold_K"].notna()
    ].copy()
    upper_tail = upper_tail.sort_values(["event_date", "threshold_K", "market_slug"], na_position="last").drop_duplicates(
        subset=["event_date", "threshold_K", "market_slug", "yes_token_id"], keep="first"
    )
    return category_panel, upper_tail


def fetch_price_history(token_id: str, event_slug: str, threshold_K: float) -> Tuple[Dict[str, Any], Path]:
    token_id = str(token_id)
    raw_path = RAW_PRICE / f"{safe_name(event_slug)}__K{str(threshold_K).replace('.', 'p')}__{token_id[:20]}.json"
    if raw_path.exists() and raw_path.stat().st_size > 0:
        try:
            return json.loads(raw_path.read_text(encoding="utf-8")), raw_path
        except Exception:
            pass

    url = "https://clob.polymarket.com/prices-history"
    attempts = [
        {"market": token_id, "interval": "max", "fidelity": 60},
        {"market": token_id, "interval": "1m", "fidelity": 60},
        {"market": token_id, "interval": "1w", "fidelity": 60},
    ]
    last: Dict[str, Any] = {}
    for params in attempts:
        try:
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers=HEADERS)
            last = {"status_code": r.status_code, "url": r.url, "text": (r.text or "")[:2000]}
            if r.status_code == 200:
                data = r.json()
                wrapper = {"request_url": r.url, "params": params, "response": data}
                write_json(raw_path, wrapper)
                time.sleep(0.20)
                return wrapper, raw_path
        except Exception as e:
            last = {"error": str(e), "params": params}
        time.sleep(0.25)
    wrapper = {"error": "price_history_fetch_failed", "last": last}
    write_json(raw_path, wrapper)
    return wrapper, raw_path


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

    rows = []
    for x in hist:
        if not isinstance(x, dict):
            continue
        t = x.get("t", x.get("timestamp", x.get("time")))
        p = x.get("p", x.get("price", x.get("value")))
        if t is None or p is None:
            continue
        try:
            t_float = float(t)
            if t_float > 1e12:
                ts = pd.to_datetime(t_float, unit="ms", utc=True)
            else:
                ts = pd.to_datetime(t_float, unit="s", utc=True)
        except Exception:
            ts = pd.to_datetime(t, errors="coerce", utc=True)
        price = pd.to_numeric(p, errors="coerce")
        if pd.notna(ts) and pd.notna(price):
            rows.append({"price_timestamp_utc": ts, "p_market": float(price)})
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["price_timestamp_utc", "p_market"])
    return out.drop_duplicates(["price_timestamp_utc", "p_market"]).sort_values("price_timestamp_utc").reset_index(drop=True)


def build_price_panel(upper_tail: pd.DataFrame) -> pd.DataFrame:
    if upper_tail.empty:
        return pd.DataFrame()
    rows: List[pd.DataFrame] = []
    contracts = upper_tail[upper_tail["yes_token_id"].notna()].drop_duplicates(["event_date", "threshold_K", "event_slug", "yes_token_id"])
    print("Upper-tail contracts with YES token for CLOB retrieval:", len(contracts))
    for _, row in contracts.iterrows():
        wrapper, raw_path = fetch_price_history(str(row["yes_token_id"]), str(row["event_slug"]), float(row["threshold_K"]))
        hist = parse_price_history(wrapper)
        if hist.empty:
            continue
        for c in [
            "event_date", "threshold_K", "event_slug", "event_url", "market_slug", "market_id",
            "market_question", "outcome_label_text", "yes_token_id", "hko_tmax_C", "hko_floor_bin_K",
            "Y_ge_K", "empirical_role", "volume", "liquidity", "createdAt", "endDate",
        ]:
            hist[c] = row.get(c)
        hist["raw_price_json_path"] = str(raw_path.relative_to(ROOT))
        rows.append(hist)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    out["price_timestamp_hkt"] = pd.to_datetime(out["price_timestamp_utc"], utc=True).dt.tz_convert("Asia/Hong_Kong")
    return out


def build_decision_panel(price_panel: pd.DataFrame) -> pd.DataFrame:
    if price_panel.empty:
        return pd.DataFrame()
    rows = []
    keys = ["event_date", "threshold_K", "event_slug", "market_slug", "yes_token_id"]
    for key, g in price_panel.groupby(keys, dropna=False):
        g = g.sort_values("price_timestamp_utc").copy()
        event_date = pd.to_datetime(key[0]).date()
        midnight_hkt = pd.Timestamp(event_date).tz_localize("Asia/Hong_Kong")
        cutoffs = {
            "last_price_before_event_day_hkt": midnight_hkt.tz_convert("UTC"),
            "last_price_before_24h_prior": (midnight_hkt - pd.Timedelta(hours=24)).tz_convert("UTC"),
            "last_price_before_12h_prior": (midnight_hkt - pd.Timedelta(hours=12)).tz_convert("UTC"),
            "last_price_before_close_proxy": (midnight_hkt + pd.Timedelta(hours=24)).tz_convert("UTC"),
        }
        for rule, cutoff in cutoffs.items():
            gg = g[g["price_timestamp_utc"] <= cutoff]
            if gg.empty:
                continue
            last = gg.iloc[-1].to_dict()
            last["decision_rule"] = rule
            last["decision_cutoff_utc"] = cutoff
            last["decision_timestamp_utc"] = last["price_timestamp_utc"]
            last["price_staleness_hours"] = (cutoff - last["price_timestamp_utc"]).total_seconds() / 3600
            rows.append(last)
    return pd.DataFrame(rows)


def score_decisions(decision: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if decision.empty:
        return pd.DataFrame(), pd.DataFrame(columns=[
            "decision_rule", "empirical_role", "n", "mean_brier", "mean_log_score", "mean_p_market", "outcome_rate"
        ])
    out = decision.copy()
    out["p_market"] = pd.to_numeric(out["p_market"], errors="coerce")
    out["Y_ge_K"] = pd.to_numeric(out["Y_ge_K"], errors="coerce")
    out = out.dropna(subset=["p_market", "Y_ge_K"]).copy()
    out["p_clipped"] = out["p_market"].clip(EPS, 1 - EPS)
    out["brier_market"] = (out["p_market"] - out["Y_ge_K"]) ** 2
    out["log_score_market"] = -(out["Y_ge_K"] * np.log(out["p_clipped"]) + (1 - out["Y_ge_K"]) * np.log(1 - out["p_clipped"]))
    if out.empty:
        summary = pd.DataFrame(columns=[
            "decision_rule", "empirical_role", "n", "mean_brier", "mean_log_score", "mean_p_market", "outcome_rate"
        ])
    else:
        summary = out.groupby(["decision_rule", "empirical_role"], dropna=False).agg(
            n=("brier_market", "size"),
            mean_brier=("brier_market", "mean"),
            mean_log_score=("log_score_market", "mean"),
            mean_p_market=("p_market", "mean"),
            outcome_rate=("Y_ge_K", "mean"),
        ).reset_index()
    return out, summary


def build_report(hko: pd.DataFrame, events: pd.DataFrame, children: pd.DataFrame, category: pd.DataFrame, upper_tail: pd.DataFrame, price: pd.DataFrame, decision: pd.DataFrame, scoring: pd.DataFrame, score_summary: pd.DataFrame) -> str:
    report: List[str] = []
    report.append("# 18f HKO Daily Extract and Polymarket historical panel to 2026-05-31\n")
    report.append("## Purpose\n")
    report.append("This pipeline constructs the March to May 2026 Hong Kong highest-temperature market panel by joining official HKO Daily Extract / metob maximum-temperature observations to deterministic Polymarket event slugs.\n")
    report.append("## Coverage\n")
    report.append(f"HKO rows: `{len(hko)}`\n")
    if len(hko):
        report.append(f"HKO date range: `{hko['event_date'].min()}` to `{hko['event_date'].max()}`\n")
        report.append("\n### HKO source labels\n")
        report.append(hko["hko_source_label"].value_counts(dropna=False).to_markdown())
        report.append("\n")
    report.append(f"Polymarket event slugs swept: `{len(events)}`\n")
    if len(events):
        report.append(f"Gamma events found: `{int(events['event_found_gamma'].sum())}`\n")
        report.append(f"Web pages found: `{int(events['event_found_web'].sum())}`\n")
    report.append(f"Flattened child markets: `{len(children)}`\n")
    report.append(f"Category validation rows: `{len(category)}`\n")
    report.append(f"Upper-tail threshold rows: `{len(upper_tail)}`\n")
    report.append(f"Price history rows: `{len(price)}`\n")
    report.append(f"No-lookahead decision rows: `{len(decision)}`\n")
    report.append(f"Scoring-ready rows: `{len(scoring)}`\n")

    if len(upper_tail):
        report.append("\n## Upper-tail empirical role counts\n")
        report.append(upper_tail["empirical_role"].value_counts(dropna=False).to_markdown())
        report.append("\n\n## Upper-tail sample preview\n")
        cols = [c for c in ["event_date", "threshold_K", "market_slug", "yes_token_id", "hko_tmax_C", "Y_ge_K", "empirical_role"] if c in upper_tail.columns]
        report.append(upper_tail[cols].head(30).to_markdown(index=False))

    report.append("\n## Market-only score summary\n")
    if len(score_summary):
        report.append(score_summary.to_markdown(index=False))
    else:
        report.append("_No scoreable rows after price-history and decision-time filtering._")

    report.append("\n## Interpretation\n")
    if len(scoring):
        report.append("The pipeline produced a non-empty realised-outcome market panel. The strict no-lookahead rules should be used for scoring; the close-proxy rule is retained only as a descriptive coverage check.")
    elif len(upper_tail):
        report.append("The pipeline produced official HKO-aligned upper-tail contracts, but no scoreable decision-price rows. The remaining bottleneck is CLOB historical price availability for the recovered YES tokens.")
    else:
        report.append("The pipeline did not recover upper-tail threshold contracts. Inspect the event sweep and child-market files before using this sample in the dissertation.")
    return "\n".join(report)


def main() -> None:
    print("Repository root:", ROOT)
    print("18f date window:", START_DATE, "to", END_DATE)

    hko = build_hko_targets()
    hko_path = PROCESSED / "18f_hko_daily_extract_targets_20260301_20260531.csv"
    hko.to_csv(hko_path, index=False)
    print("\nHKO targets:", hko.shape)
    if len(hko):
        print(hko.tail(10).to_string(index=False))

    events, children = sweep_polymarket_events()
    events_path = PROCESSED / "18f_polymarket_event_sweep_20260313_20260531.csv"
    children_path = PROCESSED / "18f_polymarket_child_markets_20260313_20260531.csv"
    events.to_csv(events_path, index=False)
    children.to_csv(children_path, index=False)
    print("\nPolymarket events:", events.shape)
    print("Polymarket child markets:", children.shape)

    category, upper_tail = build_validation_panels(children, hko)
    category_path = PROCESSED / "18f_hko_polymarket_floor_validation_panel_20260313_20260531.csv"
    upper_path = PROCESSED / "18f_hko_upper_tail_threshold_contracts_20260313_20260531.csv"
    category.to_csv(category_path, index=False)
    upper_tail.to_csv(upper_path, index=False)
    print("\nCategory validation panel:", category.shape)
    print("Upper-tail threshold panel:", upper_tail.shape)
    if len(upper_tail):
        print(upper_tail[["event_date", "threshold_K", "market_slug", "yes_token_id", "hko_tmax_C", "Y_ge_K", "empirical_role"]].head(80).to_string(index=False))

    price = build_price_panel(upper_tail)
    price_path = PROCESSED / "18f_hko_upper_tail_price_history_panel_20260313_20260531.csv"
    price.to_csv(price_path, index=False)
    print("\nPrice history panel:", price.shape)

    decision = build_decision_panel(price)
    decision_path = PROCESSED / "18f_hko_upper_tail_no_lookahead_decision_panel_20260313_20260531.csv"
    decision.to_csv(decision_path, index=False)
    print("Decision panel:", decision.shape)
    if len(decision):
        print(decision[["event_date", "threshold_K", "market_slug", "decision_rule", "p_market", "Y_ge_K", "price_staleness_hours"]].head(80).to_string(index=False))

    scoring, summary = score_decisions(decision)
    scoring_path = PROCESSED / "18f_hko_upper_tail_scoring_ready_market_panel_20260313_20260531.csv"
    summary_path = PROCESSED / "18f_hko_upper_tail_market_only_score_summary_20260313_20260531.csv"
    scoring.to_csv(scoring_path, index=False)
    summary.to_csv(summary_path, index=False)
    print("Scoring-ready panel:", scoring.shape)
    print("\nMarket-only score summary:")
    print(summary.to_string(index=False))

    report = build_report(hko, events, children, category, upper_tail, price, decision, scoring, summary)
    report_path = REPORTS / "18f_hko_metob_polymarket_historical_panel_report.md"
    report_path.write_text(report, encoding="utf-8")

    print("\nSaved key outputs:")
    for p in [
        hko_path, events_path, children_path, category_path, upper_path,
        price_path, decision_path, scoring_path, summary_path, report_path,
    ]:
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
