# %% [markdown]
# # 18c HKO Daily Extract outcome reconciliation replacement
#
# This notebook replaces the previous `18c` notebook. It is deliberately fail-safe:
#
# 1. it loads the formally certified Hong Kong upper-tail universe;
# 2. it retrieves official HKO realised daily maximum temperature values from the HKO Daily Extract route where possible;
# 3. it falls back to the HKO CLMMAXT monthly open-data file where available;
# 4. it never crashes merely because one source is unavailable;
# 5. it creates an official-HKO scoring-ready panel only where the realised HKO value is observed.
#
# The key principle is that official HKO outcomes are required for final scoring. Polymarket resolution outcomes may be useful for provisional checks, but they are not used as official realised weather outcomes in this notebook.

# %%
from __future__ import annotations

import json
import re
import time
from io import StringIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

# %%
def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / ".git").exists() or (p / "data").exists() or (p / "notebooks").exists():
            return p
    return start

ROOT = find_repo_root()
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"
RAW_HKO_DIR = DATA_RAW / "hko_daily_extract_18c"

for p in [DATA_RAW, DATA_PROCESSED, REPORTS, RAW_HKO_DIR]:
    p.mkdir(parents=True, exist_ok=True)

print("Repository root:", ROOT)

# %%
CERT_PATH = DATA_PROCESSED / "17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv"
DECISION_PATH = DATA_PROCESSED / "18b_hko_certified_upper_tail_decision_panel.csv"

if not CERT_PATH.exists():
    raise FileNotFoundError(f"Missing certified universe: {CERT_PATH}")

cert = pd.read_csv(CERT_PATH)

if "event_date" not in cert.columns:
    raise ValueError("Certified universe must contain event_date.")

cert["event_date"] = pd.to_datetime(cert["event_date"], errors="coerce").dt.date
cert["threshold_K"] = pd.to_numeric(cert["threshold_K"], errors="coerce")

print("Certified universe shape:", cert.shape)
display_cols = [c for c in ["event_date", "threshold_K", "event_slug", "market_slug", "market_id"] if c in cert.columns]
print(cert[display_cols].to_string(index=False))

# %%
def _normalise_text(x) -> str:
    return re.sub(r"\s+", " ", str(x)).strip().lower()

def _find_col(cols: Iterable, required: list[str], forbidden: list[str] | None = None):
    forbidden = forbidden or []
    for c in cols:
        s = _normalise_text(c)
        if all(t.lower() in s for t in required) and not any(f.lower() in s for f in forbidden):
            return c
    return None

def looks_like_day_series(s: pd.Series) -> bool:
    nums = pd.to_numeric(s, errors="coerce")
    if nums.notna().sum() < 5:
        return False
    valid = nums.dropna().between(1, 31).mean()
    return valid > 0.85

# %%
def parse_hko_clmmaxt() -> pd.DataFrame:
    """
    Robust parser for HKO CLMMAXT daily maximum temperature file.
    Handles bilingual columns such as:
    '#年/Year', '月/Month', '日/Day', '數值/Value', '數據完整性/data Completeness'.

    Returns event_date and hko_tmax_C.
    If the source is unavailable or only available up to an old month, the function still returns safely.
    """
    url = (
        "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php"
        "?dataType=CLMMAXT&rformat=csv&station=HKO"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        text = r.text
        (RAW_HKO_DIR / "hko_clmmaxt_raw.csv").write_text(text, encoding="utf-8")
    except Exception as e:
        print("WARNING: CLMMAXT download failed:", repr(e))
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source"])

    best = None
    for skip in range(0, 12):
        try:
            df_try = pd.read_csv(StringIO(text), skiprows=skip)
        except Exception:
            continue
        cols_l = [_normalise_text(c) for c in df_try.columns]
        has_date = any("year" in c or "年" in c for c in cols_l) and any("month" in c or "月" in c for c in cols_l)
        has_value = any(("value" in c or "數值" in c) and "complete" not in c and "完整" not in c for c in cols_l)
        if has_date and has_value:
            best = df_try
            break

    if best is None:
        print("WARNING: could not locate CLMMAXT header row.")
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source"])

    df = best.copy()
    print("CLMMAXT raw columns:", df.columns.tolist())

    year_col = _find_col(df.columns, ["year"]) or _find_col(df.columns, ["年"])
    month_col = _find_col(df.columns, ["month"]) or _find_col(df.columns, ["月"])
    day_col = _find_col(df.columns, ["day"]) or _find_col(df.columns, ["日"])
    value_col = (
        _find_col(df.columns, ["value"], forbidden=["complete", "completeness"])
        or _find_col(df.columns, ["數值"], forbidden=["完整", "完整性"])
    )

    if not all([year_col, month_col, day_col, value_col]):
        print("WARNING: Could not identify all CLMMAXT date/value columns.")
        print("Detected:", {"year": year_col, "month": month_col, "day": day_col, "value": value_col})
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source"])

    date_df = df[[year_col, month_col, day_col]].rename(
        columns={year_col: "year", month_col: "month", day_col: "day"}
    )

    out = pd.DataFrame({
        "event_date": pd.to_datetime(date_df, errors="coerce").dt.date,
        "hko_tmax_C": pd.to_numeric(df[value_col], errors="coerce"),
        "hko_source": "official_hko_clmmaxt_monthly_open_data",
    })

    out = out.dropna(subset=["event_date", "hko_tmax_C"]).drop_duplicates("event_date")
    out = out.sort_values("event_date").reset_index(drop=True)

    print("CLMMAXT parsed rows:", len(out))
    if len(out):
        print("CLMMAXT date range:", out["event_date"].min(), "to", out["event_date"].max())

    return out

# %%
def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [" ".join([str(x) for x in tup if str(x) != "nan"]).strip() for tup in out.columns]
    else:
        out.columns = [str(c).strip() for c in out.columns]
    return out

def extract_daily_max_from_table(df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    """
    Try two HKO Daily Extract table layouts:
    A. row-per-day tables with a day/date column and a maximum-temperature column.
    B. transposed tables where one row is maximum temperature and columns are days.
    """
    df = flatten_columns(df)
    if df.empty:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source_detail"])

    df = df.dropna(axis=1, how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Layout A: day rows.
    day_col = None
    for c in df.columns:
        c_l = _normalise_text(c)
        if c_l in {"day", "date", "日", "日期"} or "day" in c_l or "date" in c_l:
            if looks_like_day_series(df[c]):
                day_col = c
                break
    if day_col is None:
        for c in df.columns:
            if looks_like_day_series(df[c]):
                day_col = c
                break

    max_col = None
    for c in df.columns:
        s = _normalise_text(c)
        if ("max" in s or "maximum" in s or "最高" in s) and ("temp" in s or "temperature" in s or "氣溫" in s or "air" in s):
            if c != day_col:
                max_col = c
                break

    if day_col is not None and max_col is None:
        candidates = []
        for c in df.columns:
            if c == day_col:
                continue
            vals = pd.to_numeric(df[c], errors="coerce")
            if vals.notna().sum() >= 5:
                plausible = vals.dropna().between(0, 45).mean() if vals.notna().sum() else 0
                if plausible > 0.8:
                    candidates.append((c, vals.notna().sum(), vals.mean()))
        if candidates:
            candidates_sorted = sorted(
                candidates,
                key=lambda x: (("max" in _normalise_text(x[0]) or "最高" in _normalise_text(x[0])), x[2]),
                reverse=True,
            )
            max_col = candidates_sorted[0][0]

    if day_col is not None and max_col is not None:
        tmp = pd.DataFrame({
            "day": pd.to_numeric(df[day_col], errors="coerce"),
            "hko_tmax_C": pd.to_numeric(df[max_col], errors="coerce"),
        }).dropna()
        tmp["event_date"] = pd.to_datetime(
            {"year": year, "month": month, "day": tmp["day"].astype(int)},
            errors="coerce",
        ).dt.date
        tmp["hko_source_detail"] = f"daily_extract_row_layout::{max_col}"
        return tmp[["event_date", "hko_tmax_C", "hko_source_detail"]].dropna().drop_duplicates("event_date")

    # Layout B: transposed table.
    str_df = df.astype(str)
    label_cols = list(df.columns[:3])
    matching_rows = []
    for idx, row in str_df.iterrows():
        row_head = " ".join(str(row[c]) for c in label_cols if c in row.index)
        row_all = " ".join(str(x) for x in row.values[:5])
        text = _normalise_text(row_head + " " + row_all)
        if ("max" in text or "maximum" in text or "最高" in text) and ("temp" in text or "temperature" in text or "氣溫" in text or "air" in text):
            matching_rows.append(idx)

    for idx in matching_rows:
        row = df.loc[idx]
        records = []
        for c in df.columns:
            day_match = re.search(r"(?<!\\d)([1-9]|[12]\\d|3[01])(?!\\d)", str(c))
            if not day_match:
                continue
            day = int(day_match.group(1))
            val = pd.to_numeric(pd.Series([row[c]]), errors="coerce").iloc[0]
            if pd.notna(val) and 0 <= float(val) <= 45:
                records.append({"day": day, "hko_tmax_C": float(val)})
        if len(records) >= 5:
            tmp = pd.DataFrame(records)
            tmp["event_date"] = pd.to_datetime(
                {"year": year, "month": month, "day": tmp["day"].astype(int)},
                errors="coerce",
            ).dt.date
            tmp["hko_source_detail"] = "daily_extract_transposed_layout"
            return tmp[["event_date", "hko_tmax_C", "hko_source_detail"]].dropna().drop_duplicates("event_date")

    return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source_detail"])

# %%
def candidate_daily_extract_urls(year: int, month: int) -> list[str]:
    m1 = str(int(month))
    m2 = f"{int(month):02d}"
    return [
        f"https://www.hko.gov.hk/en/cis/dailyExtract.htm?y={year}&m={m1}",
        f"https://www.hko.gov.hk/en/cis/dailyExtract.htm?y={year}&m={m2}",
        f"https://www.hko.gov.hk/en/cis/dailyExtract_e.htm?y={year}&m={m1}",
        f"https://www.hko.gov.hk/en/wxinfo/pastwx/dailyExtract.htm?y={year}&m={m1}",
        f"https://www.weather.gov.hk/en/cis/dailyExtract.htm?y={year}&m={m1}",
    ]

def fetch_daily_extract_month(year: int, month: int) -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0 academic research; UCL MSc dissertation",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    debug_rows = []

    for url in candidate_daily_extract_urls(year, month):
        try:
            r = requests.get(url, headers=headers, timeout=30)
            status = r.status_code
            text = r.text
            debug_rows.append({"url": url, "status": status, "bytes": len(text)})
            if status != 200 or len(text) < 500:
                continue

            html_path = RAW_HKO_DIR / f"hko_daily_extract_{year}_{month:02d}_{abs(hash(url))}.html"
            html_path.write_text(text, encoding="utf-8", errors="ignore")

            try:
                tables = pd.read_html(StringIO(text))
            except Exception as e:
                debug_rows[-1]["read_html_error"] = repr(e)
                continue

            print(f"Daily Extract candidate {url}: {len(tables)} tables")

            for i, table in enumerate(tables):
                parsed = extract_daily_max_from_table(table, year, month)
                if len(parsed):
                    parsed["hko_source"] = "official_hko_daily_extract"
                    parsed["hko_source_url"] = url
                    parsed["hko_source_table_index"] = i
                    parsed["hko_raw_html_path"] = str(html_path.relative_to(ROOT))
                    print(f"Parsed Daily Extract {year}-{month:02d} from table {i}: {len(parsed)} rows")
                    return parsed

        except Exception as e:
            debug_rows.append({"url": url, "status": "exception", "error": repr(e)})
            continue
        finally:
            time.sleep(0.5)

    debug_path = RAW_HKO_DIR / f"hko_daily_extract_{year}_{month:02d}_debug.json"
    debug_path.write_text(json.dumps(debug_rows, indent=2), encoding="utf-8")
    print(f"WARNING: no Daily Extract parsed for {year}-{month:02d}; debug saved to {debug_path.relative_to(ROOT)}")
    return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source", "hko_source_url", "hko_source_table_index", "hko_raw_html_path", "hko_source_detail"])

# %%
# Retrieve realised values.

clm = parse_hko_clmmaxt()
print("\nCLMMAXT parsed rows:", len(clm))

months_needed = sorted({(d.year, d.month) for d in cert["event_date"].dropna()})
daily_frames = []
for year, month in months_needed:
    daily_frames.append(fetch_daily_extract_month(year, month))

daily = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
if len(daily):
    daily = daily.drop_duplicates("event_date").sort_values("event_date").reset_index(drop=True)

print("\nDaily Extract parsed rows:", len(daily))
if len(daily):
    print(daily[["event_date", "hko_tmax_C", "hko_source", "hko_source_detail"]].head(40).to_string(index=False))

# %%
# Build official HKO outcome table for certified event dates.

event_rows = cert[["event_date", "threshold_K", "event_slug", "market_slug"]].drop_duplicates().copy()

official_sources = []
if len(daily):
    d = daily.copy()
    d["source_priority"] = 1
    official_sources.append(d)
if len(clm):
    c = clm.copy()
    c["hko_source_detail"] = "clmmaxt_monthly_file"
    c["hko_source_url"] = ""
    c["hko_source_table_index"] = np.nan
    c["hko_raw_html_path"] = ""
    c["source_priority"] = 2
    official_sources.append(c)

if official_sources:
    official = pd.concat(official_sources, ignore_index=True, sort=False)
    official["event_date"] = pd.to_datetime(official["event_date"], errors="coerce").dt.date
    official["hko_tmax_C"] = pd.to_numeric(official["hko_tmax_C"], errors="coerce")
    official = (
        official.dropna(subset=["event_date", "hko_tmax_C"])
        .sort_values(["event_date", "source_priority"])
        .drop_duplicates("event_date", keep="first")
        .reset_index(drop=True)
    )
else:
    official = pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source", "hko_source_detail", "hko_source_url", "hko_raw_html_path"])

outcomes = event_rows.merge(official, on="event_date", how="left")
outcomes["hko_outcome_available_18c"] = outcomes["hko_tmax_C"].notna()
outcomes["Y_ge_K_official_18c"] = np.where(
    outcomes["hko_outcome_available_18c"],
    (outcomes["hko_tmax_C"] >= outcomes["threshold_K"]).astype(int),
    np.nan,
)

outcomes_path = DATA_PROCESSED / "18c_hko_daily_extract_event_outcomes.csv"
outcomes.to_csv(outcomes_path, index=False)

print("\n18c event outcome table:")
show_cols = [c for c in ["event_date", "threshold_K", "hko_tmax_C", "Y_ge_K_official_18c", "hko_source", "hko_source_detail", "event_slug"] if c in outcomes.columns]
print(outcomes[show_cols].to_string(index=False))
print("\nEvent outcomes with official HKO value:", int(outcomes["hko_outcome_available_18c"].sum()), "/", len(outcomes))
print("Saved:", outcomes_path.relative_to(ROOT))

# %%
# Reconcile with 18b no-lookahead decision panel.

if DECISION_PATH.exists():
    decision = pd.read_csv(DECISION_PATH)
    print("\n18b decision panel shape:", decision.shape)

    if "event_date" in decision.columns:
        decision["event_date"] = pd.to_datetime(decision["event_date"], errors="coerce").dt.date
    if "threshold_K" in decision.columns:
        decision["threshold_K"] = pd.to_numeric(decision["threshold_K"], errors="coerce")

    merge_cols = [c for c in ["event_date", "threshold_K", "event_slug", "market_slug"] if c in decision.columns and c in outcomes.columns]
    recon = decision.merge(
        outcomes[[*merge_cols, "hko_tmax_C", "Y_ge_K_official_18c", "hko_outcome_available_18c", "hko_source", "hko_source_detail"]],
        on=merge_cols,
        how="left",
        suffixes=("", "_18c"),
    )

    recon["Y_ge_K"] = recon["Y_ge_K_official_18c"]
    recon["official_hko_outcome_available"] = recon["hko_outcome_available_18c"].fillna(False).astype(bool)

    no_lookahead = recon["no_lookahead_valid"].fillna(False).astype(bool) if "no_lookahead_valid" in recon.columns else pd.Series(True, index=recon.index)
    if "decision_price_available" in recon.columns:
        price_available = recon["decision_price_available"].fillna(False).astype(bool)
    elif "yes_price" in recon.columns:
        price_available = recon["yes_price"].notna()
    else:
        price_available = pd.Series(False, index=recon.index)
    outcome_available = recon["official_hko_outcome_available"]

    scoring_ready = recon[no_lookahead & price_available & outcome_available].copy()

    recon_path = DATA_PROCESSED / "18c_hko_daily_extract_reconciled_decision_panel.csv"
    score_path = DATA_PROCESSED / "18c_hko_daily_extract_scoring_ready_panel.csv"

    recon.to_csv(recon_path, index=False)
    scoring_ready.to_csv(score_path, index=False)

    print("\nReconciled decision panel shape:", recon.shape)
    print("Scoring-ready official HKO panel shape:", scoring_ready.shape)
    print("Saved:", recon_path.relative_to(ROOT))
    print("Saved:", score_path.relative_to(ROOT))

    if len(scoring_ready):
        cols = [c for c in ["event_date", "threshold_K", "decision_rule", "yes_price", "hko_tmax_C", "Y_ge_K", "hko_source", "market_slug"] if c in scoring_ready.columns]
        print("\nScoring-ready official HKO rows:")
        print(scoring_ready[cols].to_string(index=False))
else:
    print("\nWARNING: 18b decision panel not found; outcome table only was created.")
    recon = pd.DataFrame()
    scoring_ready = pd.DataFrame()

# %%
# Write report.

report = []
report.append("# 18c HKO Daily Extract outcome reconciliation report\n")
report.append(f"Certified universe rows: {len(cert)}\n")
report.append(f"CLMMAXT parsed rows: {len(clm)}\n")
report.append(f"HKO Daily Extract parsed rows: {len(daily)}\n")
report.append(f"Event outcomes with official HKO value: {int(outcomes['hko_outcome_available_18c'].sum())} / {len(outcomes)}\n")
report.append(f"Reconciled decision panel rows: {len(recon)}\n")
report.append(f"Official HKO scoring-ready rows: {len(scoring_ready)}\n")

report.append("\n## Certified event outcomes\n")
report_cols = [c for c in ["event_date", "threshold_K", "hko_tmax_C", "Y_ge_K_official_18c", "hko_source", "hko_source_detail", "event_slug"] if c in outcomes.columns]
report.append(outcomes[report_cols].to_markdown(index=False))

report.append("\n\n## Interpretation\n")
if len(scoring_ready):
    report.append("At least one certified upper-tail contract now has an official HKO realised outcome and a no-lookahead market decision price. The corresponding rows may be used for official-HKO market probability scoring.")
else:
    report.append("No strict official-HKO scoring rows are available yet. The certified market-price panel remains valid, but final scoring requires official HKO Daily Extract outcomes for the retained event dates.")

report_path = REPORTS / "18c_hko_daily_extract_outcome_reconciliation_report.md"
report_path.write_text("\n".join(report), encoding="utf-8")
print("Saved report:", report_path.relative_to(ROOT))
