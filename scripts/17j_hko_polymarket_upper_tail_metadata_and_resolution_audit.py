# %% [markdown]
#
# # 17j Hong Kong Polymarket upper-tail metadata and resolution audit
#
# Purpose: certify whether a restricted Hong Kong Polymarket temperature-market subset can be treated as direct threshold contracts of the form
#
# \[
# Z^{\mathrm{tail}}_{d,K}=\mathbf{1}\{T^{\mathrm{HKO}}_d\ge K\}.
# \]
#
# This notebook is fail-closed: it does **not** certify a market merely because its page label says “or higher”. It checks the actual Gamma metadata, the HKO realised maximum temperature, the resolved terminal outcome, source-family wording, volume/liquidity, and possible boundary fields such as `lowerBound`, `upperBound`, `groupItemThreshold`, and `groupItemRange`.
#
# Expected outputs:
#
# - `data/processed/17j_hko_polymarket_hko_interior_floor_summary.csv`
# - `data/processed/17j_hko_polymarket_hko_upper_tail_summary.csv`
# - `data/processed/17j_hko_polymarket_hko_upper_tail_boundary_brackets.csv`
# - `data/processed/17j_hko_polymarket_hko_tail_admissibility_decision.csv`
# - raw/interim snapshots for reproducibility.
#
# Run this from the dissertation repository root with live internet access.

# %%

# 0. Imports and paths
import json
import math
import re
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import requests

ROOT = Path.cwd()
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports" / "audit"

for p in [DATA_RAW, DATA_INTERIM, DATA_PROCESSED, REPORTS]:
    p.mkdir(parents=True, exist_ok=True)

RUN_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN_TS


# %% [markdown]
#
# ## 1. Configuration
#
# `KNOWN_EVENT_SLUGS` contains high-value reference pages already identified during manual review. The broad search/pagination cells below also try to discover additional Hong Kong markets automatically.

# %%

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

KNOWN_EVENT_SLUGS = [
    "highest-temperature-in-hong-kong-on-may-26-2026",
    "highest-temperature-in-hong-kong-on-june-8-2026",
    "highest-temperature-in-hong-kong-on-july-9-2026",
]

SEARCH_QUERIES = [
    "Hong Kong highest temperature",
    "Hong Kong temperature HKO",
    "Hong Kong Daily Extract Absolute Daily Max",
    "highest temperature in Hong Kong",
]

# Set this to True only if Gamma terminal outcome fields are insufficient.
# It will make extra CLOB price-history calls for token IDs.
FETCH_CLOB_HISTORY_FOR_TERMINAL_PRICE = False

# Minimum activity threshold for direct probability use. Keep low for audit, raise later for market panel.
MIN_VOLUME_FOR_ADMISSIBLE = 1e-9

HKO_MAX_TEMP_URL = (
    "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php"
    "?dataType=CLMMAXT&rformat=csv&station=HKO"
)

KNOWN_EVENT_URLS = [f"https://polymarket.com/event/{slug}" for slug in KNOWN_EVENT_SLUGS]
KNOWN_EVENT_URLS


# %%

# 2. Utility functions

def safe_get(url, params=None, timeout=30, max_retries=3, sleep=0.5):
    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(sleep * (2 ** attempt))
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            time.sleep(sleep * (2 ** attempt))
    raise last_err


def gamma_get(path, params=None):
    url = f"{GAMMA_BASE}{path}"
    r = safe_get(url, params=params)
    return r.json()


def maybe_json(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, (list, dict)):
        return x
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return x
    return x


def to_float(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)
    s = str(x).strip().replace(",", "")
    if s.lower() in {"", "none", "null", "nan", "n/a"}:
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def flatten_text(*xs):
    parts = []
    for x in xs:
        if x is None:
            continue
        if isinstance(x, (dict, list)):
            parts.append(json.dumps(x, ensure_ascii=False))
        else:
            parts.append(str(x))
    return "\n".join(parts)


def strip_market_context(text):
    """Remove common non-binding AI market-context material while preserving resolution/rules text where possible."""
    if not isinstance(text, str):
        return ""
    markers = [
        "Market Context",
        "This market context",
        "The market context",
        "AI-generated",
        "This context was generated",
    ]
    cleaned = text
    for m in markers:
        idx = cleaned.lower().find(m.lower())
        if idx >= 0:
            cleaned = cleaned[:idx]
    return cleaned.strip()


def normalise_label(s):
    if s is None:
        return ""
    s = str(s)
    s = s.replace("℃", "°C")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_threshold_from_text(text):
    """Return (threshold, kind) where kind is 'upper_tail', 'lower_tail', 'interior', or None."""
    s = normalise_label(text)
    low = s.lower()

    # Examples: "33°C or higher", "33 C or higher", "33° or higher"
    m = re.search(r"(?<!\d)(-?\d+(?:\.\d+)?)\s*(?:°\s*)?c?\s*or\s*higher", low, flags=re.I)
    if m:
        return float(m.group(1)), "upper_tail"

    # Examples: "30°C or below", "30 C or lower"
    m = re.search(r"(?<!\d)(-?\d+(?:\.\d+)?)\s*(?:°\s*)?c?\s*or\s*(?:below|lower)", low, flags=re.I)
    if m:
        return float(m.group(1)), "lower_tail"

    # Interior category: exact label like "32°C". Do not use when sentence contains a date.
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(?:°\s*)?c\s*", low, flags=re.I)
    if m:
        return float(m.group(1)), "interior"

    return np.nan, None


def parse_event_date(text):
    s = str(text or "")
    # English: on May 26, 2026
    m = re.search(r"on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})", s)
    if m:
        dt = pd.to_datetime(m.group(1), errors="coerce")
        if pd.notna(dt):
            return pd.Timestamp(dt).date().isoformat()
    # Slug style: on-may-26-2026
    m = re.search(r"on-([a-z]+)-(\d{1,2})-(\d{4})", s.lower())
    if m:
        dt = pd.to_datetime(f"{m.group(1)} {m.group(2)}, {m.group(3)}", errors="coerce")
        if pd.notna(dt):
            return pd.Timestamp(dt).date().isoformat()
    return None


def numeric_close(a, b, tol=1e-8):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def field_mentions_k(value, K):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    if isinstance(value, (int, float, np.integer, np.floating)):
        return numeric_close(value, K)
    s = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
    # Match K or K.0 as a standalone number.
    pattern = rf"(?<!\d){re.escape(str(int(K) if float(K).is_integer() else K))}(?:\.0+)?(?!\d)"
    return bool(re.search(pattern, s))


def as_list_from_field(x):
    y = maybe_json(x)
    if y is None:
        return []
    if isinstance(y, list):
        return y
    if isinstance(y, dict):
        return list(y.values())
    return [y]


def terminal_yes_from_outcome_prices(outcomes, outcome_prices):
    """Infer terminal Yes outcome from outcomePrices if possible. Returns True/False/None."""
    outs = as_list_from_field(outcomes)
    prices = as_list_from_field(outcome_prices)
    if not outs or not prices or len(outs) != len(prices):
        return None
    norm_outs = [str(o).strip().lower() for o in outs]
    nums = [to_float(p) for p in prices]
    if "yes" not in norm_outs or "no" not in norm_outs:
        return None
    yi, ni = norm_outs.index("yes"), norm_outs.index("no")
    yp, np_ = nums[yi], nums[ni]
    if np.isnan(yp) or np.isnan(np_):
        return None
    if yp >= 0.99 and np_ <= 0.01:
        return True
    if yp <= 0.01 and np_ >= 0.99:
        return False
    # unresolved or non-terminal
    return None


def classify_rule_family(text):
    t = str(text or "").lower()
    has_hko = ("hong kong observatory" in t) or re.search(r"hko", t) is not None
    has_abs = "absolute daily max" in t or "daily max" in t
    has_extract = "daily extract" in t
    has_one_dec = "one-decimal" in t or "one decimal" in t or "one (1) decimal" in t or "to one decimal" in t
    bad_wunderground = "wunderground" in t
    bad_airport = "international airport" in t or "airport station" in t or "hong kong airport" in t
    if has_hko and has_abs and has_extract and has_one_dec:
        return "hko_daily_extract_one_decimal"
    if bad_wunderground or bad_airport:
        return "excluded_non_hko_or_airport_wunderground"
    if has_hko:
        return "hko_but_not_full_daily_extract_one_decimal"
    return "unknown_or_other"


# %% [markdown]
#
# ## 3. Download and standardise HKO official daily maximum temperature
#
# This gives the realised target. The Polymarket audit compares terminal outcomes against this realised HKO maximum. First-publication historical-file verification is treated separately below as a later robustness/certification layer.

# %%

# 3.1 Download current HKO daily maximum temperature CSV
r = safe_get(HKO_MAX_TEMP_URL)
raw_hko_text = r.text
raw_hko_path = DATA_RAW / f"hko_CLMMAXT_HKO_current_{RUN_TS}.csv"
raw_hko_path.write_text(raw_hko_text, encoding="utf-8")
print(raw_hko_text[:1000])
print("Saved:", raw_hko_path)


# %%

# 3.2 Robust parser for HKO CSV

def read_hko_clmmaxt(raw_text):
    candidates = []
    for skip in range(0, 20):
        try:
            df = pd.read_csv(StringIO(raw_text), skiprows=skip)
            if df.shape[1] >= 2 and df.shape[0] > 10:
                candidates.append((skip, df))
        except Exception:
            pass
    if not candidates:
        raise ValueError("Could not parse HKO CSV with skiprows 0..19")

    best = None
    best_score = -1
    for skip, df in candidates:
        cols = [str(c).strip().lower() for c in df.columns]
        score = 0
        score += sum(any(tok in c for tok in ["year", "month", "day", "date", "time"]) for c in cols)
        score += sum(any(tok in c for tok in ["temp", "temperature", "value", "data"]) for c in cols)
        if score > best_score:
            best_score = score
            best = (skip, df)
    skip, df = best
    print("Selected skiprows:", skip)
    print("Raw columns:", list(df.columns))

    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Date construction
    date_col = None
    for c in df.columns:
        if c in {"date", "data_date", "day"} or "date" in c:
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().sum() > len(df) * 0.5:
                date_col = c
                df["date"] = parsed.dt.date.astype(str)
                break

    if date_col is None:
        # Try year/month/day columns by name
        year_cols = [c for c in df.columns if "year" in c or c in {"yr", "yyyy", "年"}]
        month_cols = [c for c in df.columns if "month" in c or c in {"mon", "mm", "月"}]
        day_cols = [c for c in df.columns if "day" in c or c in {"dd", "日"}]
        if year_cols and month_cols and day_cols:
            y, m, d = year_cols[0], month_cols[0], day_cols[0]
            df["date"] = pd.to_datetime(
                dict(year=pd.to_numeric(df[y], errors="coerce"),
                     month=pd.to_numeric(df[m], errors="coerce"),
                     day=pd.to_numeric(df[d], errors="coerce")),
                errors="coerce"
            ).dt.date.astype(str)
        else:
            # Fallback: assume first three numeric columns are y/m/d
            num_cols = []
            for c in df.columns:
                s = pd.to_numeric(df[c], errors="coerce")
                if s.notna().sum() > len(df) * 0.5:
                    num_cols.append(c)
            if len(num_cols) >= 4:
                y, m, d = num_cols[0], num_cols[1], num_cols[2]
                df["date"] = pd.to_datetime(
                    dict(year=pd.to_numeric(df[y], errors="coerce"),
                         month=pd.to_numeric(df[m], errors="coerce"),
                         day=pd.to_numeric(df[d], errors="coerce")),
                    errors="coerce"
                ).dt.date.astype(str)
            else:
                raise ValueError("Could not identify HKO date columns")

    # Temperature column. Prefer named maximum/value columns, otherwise final numeric column.
    temp_candidates = []
    for c in df.columns:
        if c == "date":
            continue
        lc = c.lower()
        if any(tok in lc for tok in ["max", "maximum", "temp", "temperature", "value", "data", "氣溫", "數值"]):
            temp_candidates.append(c)
    if not temp_candidates:
        numeric_cols = []
        for c in df.columns:
            if c == "date":
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() > len(df) * 0.5:
                numeric_cols.append(c)
        temp_candidates = numeric_cols[-1:]
    if not temp_candidates:
        raise ValueError("Could not identify HKO temperature/value column")

    temp_col = temp_candidates[-1]
    out = df[["date", temp_col]].copy()
    out = out.rename(columns={temp_col: "hko_tmax_C"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date.astype(str)
    out["hko_tmax_C"] = pd.to_numeric(out["hko_tmax_C"], errors="coerce")
    out = out.dropna(subset=["date", "hko_tmax_C"]).drop_duplicates("date", keep="last")
    out = out.sort_values("date").reset_index(drop=True)
    return out

hko = read_hko_clmmaxt(raw_hko_text)
hko.to_csv(DATA_PROCESSED / "hko_daily_max_temperature_targets.csv", index=False)
hko.tail(20)


# %% [markdown]
#
# ## 4. Retrieve Polymarket Hong Kong event and child-market metadata
#
# The notebook uses three complementary routes:
#
# 1. known event slugs from manual review;
# 2. public search queries;
# 3. broad event pagination followed by local filtering.
#
# If any route fails because Polymarket changes a non-core endpoint, the other routes should still provide enough data for the audit.

# %%

# 4.1 Event retrieval helpers

def extract_events_from_response(obj):
    """Extract plausible event objects from common Gamma response shapes."""
    events = []
    if obj is None:
        return events
    if isinstance(obj, list):
        for item in obj:
            events.extend(extract_events_from_response(item))
        return events
    if isinstance(obj, dict):
        if "events" in obj and isinstance(obj["events"], list):
            events.extend(obj["events"])
        # Direct event object
        if ("slug" in obj and ("markets" in obj or "title" in obj or "event" in obj)):
            events.append(obj)
        # Search result wrappers
        for key in ["results", "data", "items"]:
            if key in obj and isinstance(obj[key], list):
                for item in obj[key]:
                    events.extend(extract_events_from_response(item))
        # Nested event in result
        if "event" in obj and isinstance(obj["event"], dict):
            events.extend(extract_events_from_response(obj["event"]))
    return events


def fetch_event_by_slug(slug):
    attempts = []
    # Known Gamma patterns. Keep all because endpoint variants have changed over time.
    for path, params in [
        (f"/events/slug/{slug}", None),
        ("/events", {"slug": slug}),
        ("/events", {"slugs": slug}),
    ]:
        try:
            obj = gamma_get(path, params=params)
            evs = extract_events_from_response(obj)
            if evs:
                return evs[0], {"path": path, "params": params, "status": "ok"}
            attempts.append({"path": path, "params": params, "status": "no_event", "raw_type": str(type(obj))})
        except Exception as e:
            attempts.append({"path": path, "params": params, "status": "error", "error": repr(e)})
    return None, {"attempts": attempts, "status": "failed"}

known_events = []
known_logs = []
for slug in KNOWN_EVENT_SLUGS:
    ev, log = fetch_event_by_slug(slug)
    known_logs.append({"slug": slug, "log": log})
    if ev:
        known_events.append(ev)
    time.sleep(0.2)

print("Known events fetched:", len(known_events))
Path(DATA_RAW / f"polymarket_known_event_fetch_logs_{RUN_TS}.json").write_text(json.dumps(known_logs, indent=2), encoding="utf-8")


# %%

# 4.2 Public search discovery
search_events = []
search_logs = []
for q in SEARCH_QUERIES:
    for path, params in [
        ("/public-search", {"q": q}),
        ("/events", {"q": q, "limit": 100}),
        ("/markets", {"q": q, "limit": 100}),
    ]:
        try:
            obj = gamma_get(path, params=params)
            evs = extract_events_from_response(obj)
            search_events.extend(evs)
            search_logs.append({"q": q, "path": path, "params": params, "n_events": len(evs), "status": "ok"})
        except Exception as e:
            search_logs.append({"q": q, "path": path, "params": params, "status": "error", "error": repr(e)})
        time.sleep(0.2)

print("Search events extracted:", len(search_events))
(DATA_RAW / f"polymarket_search_logs_{RUN_TS}.json").write_text(json.dumps(search_logs, indent=2), encoding="utf-8")


# %%

# 4.3 Broad event pagination, then local filter. Safe to stop early if too slow.

def fetch_events_keyset(max_pages=25, limit=100):
    out = []
    logs = []
    cursor = None
    for page in range(max_pages):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        try:
            obj = gamma_get("/events/pagination", params=params)
            batch = obj.get("events", []) if isinstance(obj, dict) else []
            out.extend(batch)
            cursor = obj.get("next_cursor") if isinstance(obj, dict) else None
            logs.append({"page": page, "n": len(batch), "cursor_next": bool(cursor), "status": "ok"})
            if not cursor or not batch:
                break
        except Exception as e:
            logs.append({"page": page, "status": "error", "error": repr(e)})
            break
        time.sleep(0.2)
    return out, logs


def fetch_events_offset(max_pages=25, limit=100):
    out = []
    logs = []
    for page in range(max_pages):
        params = {"limit": limit, "offset": page * limit}
        try:
            obj = gamma_get("/events", params=params)
            if isinstance(obj, dict) and "events" in obj:
                batch = obj["events"]
            elif isinstance(obj, list):
                batch = obj
            else:
                batch = []
            out.extend(batch)
            logs.append({"page": page, "n": len(batch), "status": "ok"})
            if len(batch) < limit:
                break
        except Exception as e:
            logs.append({"page": page, "status": "error", "error": repr(e)})
            break
        time.sleep(0.2)
    return out, logs

broad_events_1, broad_logs_1 = fetch_events_keyset(max_pages=10, limit=100)
broad_events_2, broad_logs_2 = fetch_events_offset(max_pages=10, limit=100)

print("Broad keyset events:", len(broad_events_1), "Broad offset events:", len(broad_events_2))
(DATA_RAW / f"polymarket_broad_event_logs_{RUN_TS}.json").write_text(
    json.dumps({"keyset": broad_logs_1, "offset": broad_logs_2}, indent=2), encoding="utf-8"
)


# %%

# 4.4 Combine and filter Hong Kong temperature events
all_events = known_events + search_events + broad_events_1 + broad_events_2

# Deduplicate by slug or id
seen = set()
dedup_events = []
for ev in all_events:
    key = ev.get("slug") or ev.get("id") or json.dumps(ev, sort_keys=True)[:200]
    if key not in seen:
        seen.add(key)
        dedup_events.append(ev)

with open(DATA_RAW / f"polymarket_all_candidate_events_raw_{RUN_TS}.json", "w", encoding="utf-8") as f:
    json.dump(dedup_events, f, ensure_ascii=False, indent=2)

rows = []
for ev in dedup_events:
    text = flatten_text(ev.get("title"), ev.get("slug"), ev.get("description"), ev.get("markets"), ev)
    tl = text.lower()
    rows.append({
        "event_id": ev.get("id"),
        "event_slug": ev.get("slug"),
        "event_title": ev.get("title") or ev.get("name") or ev.get("question"),
        "n_markets": len(ev.get("markets", []) or []),
        "contains_hong_kong": "hong kong" in tl,
        "contains_temperature": "temperature" in tl or "°c" in tl or " c " in tl,
        "contains_hko": "hong kong observatory" in tl or re.search(r"hko", tl) is not None,
        "contains_daily_extract": "daily extract" in tl,
        "contains_absolute_daily_max": "absolute daily max" in tl,
        "text_preview": text[:1000],
    })

events_index = pd.DataFrame(rows)
hk_events_index = events_index[
    events_index["contains_hong_kong"] &
    (events_index["contains_temperature"] | events_index["contains_hko"] | events_index["contains_daily_extract"])
].copy()

hk_events_index.to_csv(DATA_INTERIM / f"17j_candidate_hong_kong_events_index_{RUN_TS}.csv", index=False)
print("Total events:", len(events_index), "HK candidate events:", len(hk_events_index))
hk_events_index[["event_slug", "event_title", "n_markets", "contains_hko", "contains_daily_extract", "contains_absolute_daily_max"]].head(50)


# %% [markdown]
#
# ## 5. Flatten child markets and classify rule families
#
# This is the core metadata table. It preserves both raw and cleaned rule text. Do not manually edit this output; make manual exclusions only by adding decision rules later.

# %%

# 5. Flatten event -> child market rows
hk_event_slugs = set(hk_events_index["event_slug"].dropna().astype(str))
hk_events = [ev for ev in dedup_events if str(ev.get("slug")) in hk_event_slugs]

market_rows = []
for ev in hk_events:
    ev_text = flatten_text(ev.get("title"), ev.get("slug"), ev.get("description"))
    ev_date = parse_event_date(ev.get("slug")) or parse_event_date(ev.get("title")) or parse_event_date(ev_text)
    markets = ev.get("markets") or []
    if not isinstance(markets, list):
        continue
    for m in markets:
        if not isinstance(m, dict):
            continue
        q = m.get("question") or m.get("title") or m.get("groupItemTitle") or ""
        desc_raw = m.get("description") or ev.get("description") or ""
        desc_clean = strip_market_context(desc_raw)
        combined = flatten_text(ev_text, q, desc_clean, m.get("resolutionSource"), m.get("rules"))
        K, kind = parse_threshold_from_text(q)
        if kind is None:
            # Sometimes the group item title carries the outcome label.
            K, kind = parse_threshold_from_text(m.get("groupItemTitle"))
        if kind is None:
            # Sometimes only the outcome label appears in metadata.
            K, kind = parse_threshold_from_text(flatten_text(m.get("shortOutcomes"), m.get("outcomes")))

        outcomes = maybe_json(m.get("outcomes"))
        outcome_prices = maybe_json(m.get("outcomePrices"))
        clob_ids = maybe_json(m.get("clobTokenIds"))
        terminal_yes = terminal_yes_from_outcome_prices(outcomes, outcome_prices)

        rule_family = classify_rule_family(combined)
        volume = to_float(m.get("volumeNum", m.get("volume")))
        liquidity = to_float(m.get("liquidityNum", m.get("liquidity")))

        meta_explicit_K = False
        for fld in ["lowerBound", "upperBound", "groupItemThreshold", "groupItemRange", "groupItemTitle", "xAxisValue", "yAxisValue"]:
            if not np.isnan(K) and field_mentions_k(m.get(fld), K):
                meta_explicit_K = True

        market_rows.append({
            "run_ts": RUN_TS,
            "event_id": ev.get("id"),
            "event_slug": ev.get("slug"),
            "event_title": ev.get("title") or ev.get("name") or ev.get("question"),
            "event_date": ev_date,
            "market_id": m.get("id"),
            "market_slug": m.get("slug"),
            "question": q,
            "outcome_label_raw": m.get("groupItemTitle") or q,
            "parsed_threshold_K": K,
            "parsed_kind": kind,
            "rule_family": rule_family,
            "resolutionSource": m.get("resolutionSource"),
            "description_raw": desc_raw,
            "description_clean": desc_clean,
            "lowerBound": m.get("lowerBound"),
            "upperBound": m.get("upperBound"),
            "groupItemThreshold": m.get("groupItemThreshold"),
            "groupItemRange": m.get("groupItemRange"),
            "groupItemTitle": m.get("groupItemTitle"),
            "metadata_mentions_K_in_boundary_fields": meta_explicit_K,
            "outcomes": json.dumps(outcomes, ensure_ascii=False) if not isinstance(outcomes, str) else outcomes,
            "outcomePrices": json.dumps(outcome_prices, ensure_ascii=False) if not isinstance(outcome_prices, str) else outcome_prices,
            "terminal_yes_from_outcomePrices": terminal_yes,
            "clobTokenIds": json.dumps(clob_ids, ensure_ascii=False) if not isinstance(clob_ids, str) else clob_ids,
            "volume": volume,
            "liquidity": liquidity,
            "active": m.get("active"),
            "closed": m.get("closed"),
            "archived": m.get("archived"),
            "createdAt": m.get("createdAt"),
            "updatedAt": m.get("updatedAt"),
            "closedTime": m.get("closedTime"),
            "umaEndDate": m.get("umaEndDate"),
            "umaResolutionStatus": m.get("umaResolutionStatus"),
            "raw_market_json": json.dumps(m, ensure_ascii=False),
        })

markets = pd.DataFrame(market_rows)
markets.to_csv(DATA_INTERIM / f"17j_hk_child_markets_flat_{RUN_TS}.csv", index=False)
print(markets.shape)
markets[["event_date", "event_slug", "question", "parsed_threshold_K", "parsed_kind", "rule_family", "terminal_yes_from_outcomePrices", "volume", "metadata_mentions_K_in_boundary_fields"]].head(100)


# %%

# 5.2 Strict retained family and explicit exclusions
markets["exclude_reason"] = ""
markets.loc[markets["rule_family"] != "hko_daily_extract_one_decimal", "exclude_reason"] += "not_strict_hko_daily_extract_one_decimal;"
markets.loc[markets["parsed_kind"].isna(), "exclude_reason"] += "could_not_parse_outcome_kind;"
markets.loc[markets["event_date"].isna(), "exclude_reason"] += "could_not_parse_event_date;"
markets.loc[markets["volume"].fillna(0) <= MIN_VOLUME_FOR_ADMISSIBLE, "exclude_reason"] += "zero_or_missing_volume;"
markets.loc[markets["terminal_yes_from_outcomePrices"].isna(), "exclude_reason"] += "terminal_outcome_not_inferred_from_outcomePrices;"

strict = markets[markets["rule_family"] == "hko_daily_extract_one_decimal"].copy()
strict.to_csv(DATA_INTERIM / f"17j_hko_daily_extract_one_decimal_child_markets_{RUN_TS}.csv", index=False)

print("All child markets:", len(markets))
print("Strict HKO Daily Extract one-decimal child markets:", len(strict))
print(markets["rule_family"].value_counts(dropna=False))


# %% [markdown]
#
# ## 6. Merge with HKO values and test realised payoff parity
#
# For each child market with date and threshold, compare observed terminal YES/NO with the expected payoff under HKO floor-bin semantics.

# %%

# 6. Merge strict child markets with HKO realised daily max
strict2 = strict.merge(hko, left_on="event_date", right_on="date", how="left")
strict2 = strict2.drop(columns=["date"], errors="ignore")

strict2["floor_label"] = np.floor(strict2["hko_tmax_C"]).astype("float")
strict2["nearest_label"] = np.floor(strict2["hko_tmax_C"] + 0.5).astype("float")
strict2["ceiling_label"] = np.ceil(strict2["hko_tmax_C"]).astype("float")

strict2["expected_yes_floor"] = np.nan
mask_tail = strict2["parsed_kind"].eq("upper_tail") & strict2["parsed_threshold_K"].notna() & strict2["hko_tmax_C"].notna()
strict2.loc[mask_tail, "expected_yes_floor"] = strict2.loc[mask_tail, "hko_tmax_C"] >= strict2.loc[mask_tail, "parsed_threshold_K"]

mask_int = strict2["parsed_kind"].eq("interior") & strict2["parsed_threshold_K"].notna() & strict2["hko_tmax_C"].notna()
strict2.loc[mask_int, "expected_yes_floor"] = (
    (strict2.loc[mask_int, "hko_tmax_C"] >= strict2.loc[mask_int, "parsed_threshold_K"]) &
    (strict2.loc[mask_int, "hko_tmax_C"] < strict2.loc[mask_int, "parsed_threshold_K"] + 1.0)
)

mask_lower = strict2["parsed_kind"].eq("lower_tail") & strict2["parsed_threshold_K"].notna() & strict2["hko_tmax_C"].notna()
strict2.loc[mask_lower, "expected_yes_floor"] = strict2.loc[mask_lower, "hko_tmax_C"] < (strict2.loc[mask_lower, "parsed_threshold_K"] + 1.0)

strict2["matches_floor_expected"] = strict2["terminal_yes_from_outcomePrices"].astype("object") == strict2["expected_yes_floor"].astype("object")
strict2.loc[strict2["terminal_yes_from_outcomePrices"].isna() | strict2["expected_yes_floor"].isna(), "matches_floor_expected"] = np.nan

strict2.to_csv(DATA_INTERIM / f"17j_strict_hko_child_markets_with_hko_parity_{RUN_TS}.csv", index=False)
strict2[["event_date", "question", "parsed_kind", "parsed_threshold_K", "hko_tmax_C", "terminal_yes_from_outcomePrices", "expected_yes_floor", "matches_floor_expected", "volume", "metadata_mentions_K_in_boundary_fields"]].head(100)


# %%

# 6.2 Interior floor-summary: does the terminal interior winner match floor, nearest, or ceiling?
interior = strict2[strict2["parsed_kind"].eq("interior")].copy()
interior_yes = interior[interior["terminal_yes_from_outcomePrices"].eq(True)].copy()

interior_summary = interior_yes[[
    "event_date", "event_slug", "market_slug", "question", "parsed_threshold_K", "hko_tmax_C",
    "floor_label", "nearest_label", "ceiling_label", "volume", "liquidity", "rule_family"
]].copy()
interior_summary = interior_summary.rename(columns={"parsed_threshold_K": "resolved_interior_label_k"})
interior_summary["matches_floor_label"] = interior_summary["resolved_interior_label_k"] == interior_summary["floor_label"]
interior_summary["matches_nearest_label"] = interior_summary["resolved_interior_label_k"] == interior_summary["nearest_label"]
interior_summary["matches_ceiling_label"] = interior_summary["resolved_interior_label_k"] == interior_summary["ceiling_label"]

out_path = DATA_PROCESSED / "17j_hko_polymarket_hko_interior_floor_summary.csv"
interior_summary.to_csv(out_path, index=False)
print("Saved", out_path)
interior_summary


# %%

# 6.3 Upper-tail summary
upper_tail = strict2[strict2["parsed_kind"].eq("upper_tail")].copy()
upper_tail["expected_tail_event_Y_ge_K"] = upper_tail["hko_tmax_C"] >= upper_tail["parsed_threshold_K"]
upper_tail["observed_tail_yes"] = upper_tail["terminal_yes_from_outcomePrices"]
upper_tail["tail_matches_hko_threshold"] = upper_tail["observed_tail_yes"].astype("object") == upper_tail["expected_tail_event_Y_ge_K"].astype("object")
upper_tail.loc[upper_tail["observed_tail_yes"].isna() | upper_tail["expected_tail_event_Y_ge_K"].isna(), "tail_matches_hko_threshold"] = np.nan

upper_tail_summary = upper_tail[[
    "event_date", "event_slug", "market_slug", "question", "parsed_threshold_K", "hko_tmax_C",
    "observed_tail_yes", "expected_tail_event_Y_ge_K", "tail_matches_hko_threshold",
    "metadata_mentions_K_in_boundary_fields", "lowerBound", "upperBound", "groupItemThreshold", "groupItemRange",
    "volume", "liquidity", "closedTime", "umaResolutionStatus", "rule_family", "exclude_reason",
    "clobTokenIds",
]].copy()
upper_tail_summary = upper_tail_summary.rename(columns={"parsed_threshold_K": "threshold_K"})
out_path = DATA_PROCESSED / "17j_hko_polymarket_hko_upper_tail_summary.csv"
upper_tail_summary.to_csv(out_path, index=False)
print("Saved", out_path)
upper_tail_summary.head(100)


# %% [markdown]
#
# ## 7. Boundary-bracket audit
#
# For each threshold \(K\), observed No outcomes imply the true lower boundary \(b_K\) is greater than that realised value. Observed Yes outcomes imply \(b_K\le T\). The empirical bracket is therefore
#
# \[
# \max\{T_i: 	ext{tail No}\}< b_K \le \min\{T_i: 	ext{tail Yes}\}.
# \]
#
# The exact one-decimal grid boundary is identified only if the closest observed No is \(K-0.1\) and the closest observed Yes is \(K.0\). In practice we may only get strong support rather than exact identification.

# %%

# 7. Boundary brackets for each upper-tail threshold
bracket_rows = []
for K, g in upper_tail.dropna(subset=["parsed_threshold_K", "hko_tmax_C"]).groupby("parsed_threshold_K"):
    yes_vals = g.loc[g["observed_tail_yes"].eq(True), "hko_tmax_C"].dropna().tolist()
    no_vals = g.loc[g["observed_tail_yes"].eq(False), "hko_tmax_C"].dropna().tolist()
    max_no = max(no_vals) if no_vals else np.nan
    min_yes = min(yes_vals) if yes_vals else np.nan
    consistent_with_K = True
    if yes_vals and min_yes < K - 1e-9:
        consistent_with_K = False
    if no_vals and max_no >= K - 1e-9:
        consistent_with_K = False
    exact_grid_identified = (not np.isnan(max_no) and not np.isnan(min_yes) and numeric_close(max_no, K - 0.1, tol=1e-8) and numeric_close(min_yes, K, tol=1e-8))
    bracket_rows.append({
        "threshold_K": K,
        "n_tail_markets": len(g),
        "n_observed_yes": len(yes_vals),
        "n_observed_no": len(no_vals),
        "max_hko_value_with_tail_no": max_no,
        "min_hko_value_with_tail_yes": min_yes,
        "implied_boundary_bracket": f"({max_no}, {min_yes}]" if not (np.isnan(max_no) and np.isnan(min_yes)) else "unidentified",
        "consistent_with_lower_boundary_K": consistent_with_K,
        "exact_one_decimal_grid_boundary_identified": exact_grid_identified,
        "metadata_explicit_in_any_child": bool(g["metadata_mentions_K_in_boundary_fields"].fillna(False).any()),
        "all_terminal_outcomes_match_HKO_threshold": bool(g["tail_matches_hko_threshold"].dropna().all()) if g["tail_matches_hko_threshold"].notna().any() else False,
        "event_dates": ",".join(sorted(g["event_date"].dropna().astype(str).unique())),
    })

boundary_brackets = pd.DataFrame(bracket_rows).sort_values("threshold_K") if bracket_rows else pd.DataFrame()
out_path = DATA_PROCESSED / "17j_hko_polymarket_hko_upper_tail_boundary_brackets.csv"
boundary_brackets.to_csv(out_path, index=False)
print("Saved", out_path)
boundary_brackets


# %% [markdown]
#
# ## 8. Fail-closed admissibility decision
#
# Decision rule:
#
# - `admissible`: strict HKO one-decimal family, positive activity, terminal outcome matches HKO threshold, and boundary metadata explicitly supports threshold \(K\).
# - `empirically_supported_pending_confirmation`: strict family, positive activity, terminal outcome matches HKO threshold, but boundary metadata is not explicit.
# - `descriptive_only`: strict family exists, but there is missing/zero volume, missing terminal outcome, missing HKO value, or insufficient audit information.
# - `excluded`: non-strict rule family or realised payoff mismatch.

# %%

# 8. Admissibility decision
ad = upper_tail_summary.copy()

def decide(row):
    reasons = []
    if row.get("rule_family") != "hko_daily_extract_one_decimal":
        return "excluded", "not strict HKO Daily Extract one-decimal family"
    if pd.isna(row.get("threshold_K")):
        return "excluded", "threshold K not parsed"
    if pd.isna(row.get("hko_tmax_C")):
        return "descriptive_only", "HKO realised max missing"
    if pd.isna(row.get("observed_tail_yes")):
        return "descriptive_only", "terminal Yes/No outcome not inferred"
    if bool(row.get("tail_matches_hko_threshold")) is False:
        return "excluded", "tail payoff mismatches HKO threshold event"
    if to_float(row.get("volume")) <= MIN_VOLUME_FOR_ADMISSIBLE:
        return "descriptive_only", "zero or missing volume; exclude from price-based empirical work"
    if bool(row.get("metadata_mentions_K_in_boundary_fields")):
        return "admissible", "explicit boundary/threshold metadata plus realised parity"
    return "empirically_supported_pending_confirmation", "realised parity supports threshold semantics but metadata not explicit"

if len(ad):
    decisions = ad.apply(decide, axis=1, result_type="expand")
    ad["admissibility_status"] = decisions[0]
    ad["admissibility_reason"] = decisions[1]
else:
    ad["admissibility_status"] = []
    ad["admissibility_reason"] = []

out_path = DATA_PROCESSED / "17j_hko_polymarket_hko_tail_admissibility_decision.csv"
ad.to_csv(out_path, index=False)
print("Saved", out_path)
print(ad["admissibility_status"].value_counts(dropna=False) if len(ad) else "No upper-tail rows")
ad[["event_date", "threshold_K", "hko_tmax_C", "observed_tail_yes", "tail_matches_hko_threshold", "metadata_mentions_K_in_boundary_fields", "volume", "admissibility_status", "admissibility_reason", "market_slug"]].head(200)


# %% [markdown]
#
# ## 9. Optional: CLOB price-history terminal check
#
# Use this only if Gamma terminal outcome fields are insufficient. This cell is not a trading backtest. It only attempts to read final historical prices for the YES token as an additional terminal-outcome proxy.

# %%

# 9. Optional CLOB terminal price check

def extract_yes_token_id(clobTokenIds, outcomes):
    ids = as_list_from_field(clobTokenIds)
    outs = [str(o).strip().lower() for o in as_list_from_field(outcomes)]
    if len(ids) == 2 and len(outs) == 2 and "yes" in outs:
        return str(ids[outs.index("yes")])
    if len(ids) == 2:
        return str(ids[0])  # common ordering is Yes, No, but treat as fallback only
    return None


def clob_price_history(token_id, fidelity=1440):
    params = {"market": token_id, "fidelity": fidelity}
    return gamma_get.__globals__["safe_get"](f"{CLOB_BASE}/prices-history", params=params).json()

if FETCH_CLOB_HISTORY_FOR_TERMINAL_PRICE and len(upper_tail):
    checks = []
    for _, row in upper_tail.iterrows():
        token = extract_yes_token_id(row.get("clobTokenIds"), row.get("outcomes"))
        if not token:
            continue
        try:
            hist = clob_price_history(token, fidelity=1440).get("history", [])
            last = hist[-1] if hist else {}
            checks.append({
                "market_slug": row.get("market_slug"),
                "yes_token_id": token,
                "last_price_time": last.get("t"),
                "last_yes_price": last.get("p"),
                "n_history_points": len(hist),
            })
        except Exception as e:
            checks.append({"market_slug": row.get("market_slug"), "yes_token_id": token, "error": repr(e)})
        time.sleep(0.2)
    clob_check = pd.DataFrame(checks)
    clob_check.to_csv(DATA_INTERIM / f"17j_optional_clob_terminal_price_check_{RUN_TS}.csv", index=False)
    display(clob_check.head(50))
else:
    print("Skipped. Set FETCH_CLOB_HISTORY_FOR_TERMINAL_PRICE=True if needed.")


# %% [markdown]
#
# ## 10. Optional: DATA.GOV.HK historical archive version hooks
#
# This is mainly Step 4, not Step 3. It is included here as a ready hook because Polymarket rule text may exclude later revisions. Use it after the child-market audit has identified the retained dates. DATA.GOV.HK’s historical archive API can list file versions and retrieve a specified historical file version.

# %%

# 10. DATA.GOV.HK historical archive hooks. Run after checking retained dates.
DATA_GOV_HK_LIST_VERSIONS = "https://app.data.gov.hk/v1/historical-archive/list-file-versions"
DATA_GOV_HK_GET_FILE = "https://app.data.gov.hk/v1/historical-archive/get-file"


def list_historical_versions(file_url, start_yyyymmdd, end_yyyymmdd):
    params = {"url": file_url, "start": start_yyyymmdd, "end": end_yyyymmdd}
    r = safe_get(DATA_GOV_HK_LIST_VERSIONS, params=params)
    return r.json()


def get_historical_file(file_url, time_yyyymmdd):
    # follows redirect automatically
    params = {"url": file_url, "time": time_yyyymmdd}
    r = safe_get(DATA_GOV_HK_GET_FILE, params=params)
    return r.text

# Example only. Uncomment after Step 3 output is inspected.
# versions = list_historical_versions(HKO_MAX_TEMP_URL, "20260501", "20260715")
# (DATA_INTERIM / f"hko_historical_versions_{RUN_TS}.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
# versions
print("Historical archive helpers defined. Use in Step 4 after the 17j audit output is inspected.")


# %% [markdown]
#
# ## 11. One-page audit summary for thesis notes
#
# This final cell writes a short machine-generated summary. Do not paste it directly into the thesis without reading the CSV outputs and checking exclusions.

# %%

# 11. Write a short audit summary
summary_lines = []
summary_lines.append(f"17j audit run timestamp: {RUN_TS}")
summary_lines.append(f"Raw candidate events extracted: {len(dedup_events)}")
summary_lines.append(f"Hong Kong candidate events: {len(hk_events_index)}")
summary_lines.append(f"Flattened child markets: {len(markets)}")
summary_lines.append(f"Strict HKO Daily Extract one-decimal child markets: {len(strict)}")
summary_lines.append("")
summary_lines.append("Rule-family counts:")
summary_lines.append(str(markets["rule_family"].value_counts(dropna=False)))
summary_lines.append("")
if len(ad):
    summary_lines.append("Upper-tail admissibility counts:")
    summary_lines.append(str(ad["admissibility_status"].value_counts(dropna=False)))
    summary_lines.append("")
    n_mismatch = int((ad["tail_matches_hko_threshold"] == False).sum())
    summary_lines.append(f"Upper-tail realised payoff mismatches in strict family: {n_mismatch}")
else:
    summary_lines.append("No upper-tail rows found in strict family.")

summary_text = "\n".join(summary_lines)
summary_path = REPORTS / f"17j_hk_upper_tail_audit_summary_{RUN_TS}.txt"
summary_path.write_text(summary_text, encoding="utf-8")
print(summary_text)
print("\nSaved:", summary_path)
