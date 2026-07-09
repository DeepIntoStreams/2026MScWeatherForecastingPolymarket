
from __future__ import annotations

import re
import json
import time
from io import StringIO
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------

def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / ".git").exists() or (p / "data").exists() or (p / "notebooks").exists():
            return p
    return start

ROOT = find_repo_root()
DATA = ROOT / "data"
RAW = DATA / "raw" / "hko_source_discovery_18d"
INTERIM = DATA / "interim" / "18d_hko_source_discovery"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "docs" / "research_outputs"

for p in [RAW, INTERIM, PROCESSED, REPORTS]:
    p.mkdir(parents=True, exist_ok=True)

RUN_TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

print("Repository root:", ROOT)
print("Run timestamp:", RUN_TS)

# ---------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------

CERT_PATH = PROCESSED / "17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv"
DECISION_PATH = PROCESSED / "18b_hko_certified_upper_tail_decision_panel.csv"

if not CERT_PATH.exists():
    raise FileNotFoundError(f"Missing certified universe: {CERT_PATH}")

cert = pd.read_csv(CERT_PATH)
cert["event_date"] = pd.to_datetime(cert["event_date"]).dt.date

target_dates = sorted(cert["event_date"].dropna().unique())
target_years = sorted({d.year for d in target_dates})
target_months = sorted({(d.year, d.month) for d in target_dates})

print("Certified contracts:", cert.shape)
print(cert[[c for c in ["event_date", "threshold_K", "event_slug", "market_slug"] if c in cert.columns]].to_string(index=False))
print("Target dates:", target_dates)
print("Target months:", target_months)

# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X) "
        "MSc dissertation academic research; contact via UCL student if required"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml,text/csv,text/plain,*/*",
})

def safe_filename(s: str) -> str:
    s = re.sub(r"https?://", "", s)
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
    return s[:180]

def fetch_url(url: str, *, timeout: int = 30, sleep_s: float = 0.25) -> dict:
    """Fetch URL and save raw response. Returns diagnostic dictionary."""
    time.sleep(sleep_s)
    rec = {
        "url": url,
        "ok": False,
        "status_code": None,
        "content_type": None,
        "bytes": 0,
        "raw_path": None,
        "error": None,
    }
    try:
        r = SESSION.get(url, timeout=timeout)
        rec["status_code"] = r.status_code
        rec["content_type"] = r.headers.get("content-type", "")
        rec["bytes"] = len(r.content)
        rec["ok"] = 200 <= r.status_code < 300 and len(r.content) > 0

        ext = ".html"
        ctype = (rec["content_type"] or "").lower()
        if "csv" in ctype or url.lower().endswith(".csv"):
            ext = ".csv"
        elif "json" in ctype or url.lower().endswith(".json"):
            ext = ".json"
        elif "text" in ctype:
            ext = ".txt"

        raw_path = RAW / f"{safe_filename(url)}{ext}"
        raw_path.write_bytes(r.content)
        rec["raw_path"] = str(raw_path.relative_to(ROOT))
        rec["text_sample"] = r.text[:500].replace("\n", " ")
        return rec
    except Exception as e:
        rec["error"] = repr(e)
        return rec

def normalise_text(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())

def identify_year_month_day_value_columns(df: pd.DataFrame) -> tuple[str | None, str | None, str | None, str | None]:
    cols = list(df.columns)

    def find_col(candidates, forbidden=()):
        for c in cols:
            sc = normalise_text(c)
            if any(x in sc for x in candidates) and not any(f in sc for f in forbidden):
                return c
        return None

    year_col = find_col(["year", "年"])
    month_col = find_col(["month", "月"])
    day_col = find_col(["day", "日"])
    value_col = find_col(["value", "數值", "max", "maximum"], forbidden=["completeness", "完整性", "mean", "min", "minimum"])
    return year_col, month_col, day_col, value_col

def parse_date_value_csv(text: str, source_name: str) -> pd.DataFrame:
    """Parse CSV-like HKO sources into event_date,hko_tmax_C if possible."""
    candidates = []
    for skip in range(0, 12):
        try:
            df = pd.read_csv(StringIO(text), skiprows=skip)
            if df.shape[1] >= 2:
                candidates.append((skip, df))
        except Exception:
            pass

    parsed_frames = []
    for skip, df in candidates:
        year_col, month_col, day_col, value_col = identify_year_month_day_value_columns(df)

        if all([year_col, month_col, day_col, value_col]):
            out = pd.DataFrame({
                "event_date": pd.to_datetime(
                    df[[year_col, month_col, day_col]].rename(columns={year_col:"year", month_col:"month", day_col:"day"}),
                    errors="coerce",
                ).dt.date,
                "hko_tmax_C": pd.to_numeric(df[value_col], errors="coerce"),
            })
            out["parse_route"] = f"csv_y_m_d_value_skip_{skip}"
            out["source_name"] = source_name
            parsed_frames.append(out)

        # Alternative: single date column + value column
        date_cols = [c for c in df.columns if "date" in normalise_text(c) or "日期" in normalise_text(c)]
        val_cols = [
            c for c in df.columns
            if any(x in normalise_text(c) for x in ["value", "數值", "max", "maximum"])
            and not any(f in normalise_text(c) for f in ["completeness", "完整性", "mean", "min"])
        ]
        if date_cols and val_cols:
            out = pd.DataFrame({
                "event_date": pd.to_datetime(df[date_cols[0]], errors="coerce").dt.date,
                "hko_tmax_C": pd.to_numeric(df[val_cols[0]], errors="coerce"),
            })
            out["parse_route"] = f"csv_date_value_skip_{skip}"
            out["source_name"] = source_name
            parsed_frames.append(out)

    if not parsed_frames:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "parse_route", "source_name"])

    out = pd.concat(parsed_frames, ignore_index=True)
    out = out.dropna(subset=["event_date", "hko_tmax_C"])
    out = out.drop_duplicates(["event_date", "hko_tmax_C", "parse_route", "source_name"])
    return out

def parse_daily_extract_tables_from_html(html: str, source_name: str, year: int, month: int) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """Try multiple table layouts in HKO Daily Extract HTML."""
    try:
        tables = pd.read_html(StringIO(html))
    except Exception as e:
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "parse_route", "source_name"]), []

    # Save all tables for manual inspection.
    for i, t in enumerate(tables):
        table_path = INTERIM / f"{source_name}_table_{i}.csv"
        t.to_csv(table_path, index=False)

    parsed = []

    for ti, df in enumerate(tables):
        if df.empty:
            continue
        # Flatten MultiIndex columns if necessary.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(map(str, c)).strip() for c in df.columns.to_list()]

        # Route A: rows are days and columns contain absolute max.
        norm_cols = {c: normalise_text(c) for c in df.columns}
        day_cols = [c for c, s in norm_cols.items() if s in {"day", "date", "日期"} or "day" == s or "日" == s]
        max_cols = [
            c for c, s in norm_cols.items()
            if ("absolute" in s and "max" in s and "temp" in s)
            or ("max" in s and "temp" in s and "min" not in s and "mean" not in s)
            or ("最高" in s and "氣溫" in s)
        ]
        if day_cols and max_cols:
            tmp = pd.DataFrame({
                "day": pd.to_numeric(df[day_cols[0]], errors="coerce"),
                "hko_tmax_C": pd.to_numeric(df[max_cols[0]], errors="coerce"),
            })
            tmp["event_date"] = pd.to_datetime(dict(year=year, month=month, day=tmp["day"]), errors="coerce").dt.date
            tmp["parse_route"] = f"html_table_{ti}_rows_are_days"
            tmp["source_name"] = source_name
            parsed.append(tmp[["event_date", "hko_tmax_C", "parse_route", "source_name"]])

        # Route B: rows are variables and columns are days 1..31.
        first_col = df.columns[0]
        row_labels = df[first_col].map(normalise_text)
        max_row_mask = row_labels.str.contains("absolute", na=False) & row_labels.str.contains("max", na=False) & row_labels.str.contains("temp", na=False)
        max_row_mask |= row_labels.str.contains("maximum temperature", na=False)
        max_row_mask |= row_labels.str.contains("最高", na=False) & row_labels.str.contains("氣溫", na=False)

        if max_row_mask.any():
            row = df[max_row_mask].iloc[0]
            records = []
            for c in df.columns[1:]:
                sc = normalise_text(c)
                # day column labels can be 1, 01, 1.0, "1"
                day = None
                m = re.search(r"\b([0-3]?\d)\b", sc)
                if m:
                    try:
                        d = int(m.group(1))
                        if 1 <= d <= 31:
                            day = d
                    except Exception:
                        pass
                if day is None:
                    continue
                val = pd.to_numeric(pd.Series([row[c]]), errors="coerce").iloc[0]
                if pd.notna(val):
                    records.append({
                        "event_date": pd.Timestamp(year=year, month=month, day=day).date(),
                        "hko_tmax_C": float(val),
                        "parse_route": f"html_table_{ti}_variables_are_rows",
                        "source_name": source_name,
                    })
            if records:
                parsed.append(pd.DataFrame(records))

        # Route C: table already includes dates and many numeric fields; infer by row text.
        # Keep diagnostic route minimal to avoid false positives.

    if parsed:
        out = pd.concat(parsed, ignore_index=True)
        out = out.dropna(subset=["event_date", "hko_tmax_C"])
        out = out.drop_duplicates(["event_date", "hko_tmax_C", "parse_route", "source_name"])
    else:
        out = pd.DataFrame(columns=["event_date", "hko_tmax_C", "parse_route", "source_name"])

    return out, tables

# ---------------------------------------------------------------------
# Source route 1: known monthly CLMMAXT Open Data API fallback
# ---------------------------------------------------------------------

clm_url = "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php?dataType=CLMMAXT&rformat=csv&station=HKO"
clm_fetch = fetch_url(clm_url)
print("CLMMAXT fetch:", clm_fetch["status_code"], clm_fetch["bytes"], clm_fetch["content_type"])

clm_parsed = pd.DataFrame(columns=["event_date", "hko_tmax_C", "parse_route", "source_name"])
if clm_fetch["ok"] and clm_fetch["raw_path"]:
    clm_text = (ROOT / clm_fetch["raw_path"]).read_text(encoding="utf-8", errors="replace")
    clm_parsed = parse_date_value_csv(clm_text, "CLMMAXT_all_year_HKO")
print("CLMMAXT parsed rows:", len(clm_parsed))
if len(clm_parsed):
    print("CLMMAXT date range:", clm_parsed["event_date"].min(), "to", clm_parsed["event_date"].max())

# ---------------------------------------------------------------------
# Source route 2: candidate CSDI/current-year CSV endpoints
# ---------------------------------------------------------------------

candidate_urls = []
for y in target_years:
    station_codes = ["HKO", "KP", "HKA"]
    variable_codes = ["MAXT", "MAX_TEMP", "TMAX", "MXT"]
    base_patterns = [
        "https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_{station}_{var}_{year}.csv",
        "https://data.weather.gov.hk/weatherAPI/cis/csvfile/{station}/{year}/daily_{station}_{var}_{year}.csv",
        "https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/{year}/daily_{station}_{var}_{year}.csv",
    ]
    for station in station_codes:
        for var in variable_codes:
            for pat in base_patterns:
                candidate_urls.append(pat.format(station=station, var=var, year=y))

# Add known rainfall-like pattern as diagnostic, not used for Tmax.
for y in target_years:
    candidate_urls.append(f"https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/{y}/daily_HKO_RF_{y}.csv")

candidate_urls = list(dict.fromkeys(candidate_urls))

candidate_records = []
candidate_parsed = []
for url in candidate_urls:
    rec = fetch_url(url, sleep_s=0.1)
    candidate_records.append(rec)
    if rec["ok"] and rec["raw_path"] and rec["bytes"] > 40:
        raw_text = (ROOT / rec["raw_path"]).read_text(encoding="utf-8", errors="replace")
        parsed = parse_date_value_csv(raw_text, safe_filename(url))
        if len(parsed):
            parsed["url"] = url
            candidate_parsed.append(parsed)

candidate_df = pd.DataFrame(candidate_records)
candidate_df.to_csv(PROCESSED / "18d_hko_source_discovery_candidate_urls.csv", index=False)
print("Candidate URLs tested:", len(candidate_df))
print(candidate_df[["status_code", "bytes", "content_type", "url"]].sort_values(["status_code", "bytes"], ascending=[True, False]).head(20).to_string(index=False))

candidate_parsed_df = pd.concat(candidate_parsed, ignore_index=True) if candidate_parsed else pd.DataFrame(columns=["event_date", "hko_tmax_C", "parse_route", "source_name", "url"])
print("Candidate parsed rows:", len(candidate_parsed_df))

# ---------------------------------------------------------------------
# Source route 3: HKO Daily Extract HTML pages
# ---------------------------------------------------------------------

daily_extract_records = []
daily_extract_parsed = []
daily_extract_tables_summary = []

for y, m in target_months:
    urls = [
        f"https://www.hko.gov.hk/en/cis/dailyExtract.htm?m={m}&y={y}",
        f"https://www.hko.gov.hk/en/cis/dailyExtract.htm?m={m:02d}&y={y}",
        f"https://www.hko.gov.hk/tc/cis/dailyExtract.htm?m={m}&y={y}",
        f"https://www.hko.gov.hk/tc/cis/dailyExtract.htm?m={m:02d}&y={y}",
    ]
    for url in urls:
        rec = fetch_url(url, sleep_s=0.25)
        rec["year"] = y
        rec["month"] = m
        daily_extract_records.append(rec)

        if rec["ok"] and rec["raw_path"]:
            html = (ROOT / rec["raw_path"]).read_text(encoding="utf-8", errors="replace")
            source_name = f"daily_extract_{y}_{m:02d}_{'tc' if '/tc/' in url else 'en'}_{'02' if f'm={m:02d}' in url else 'plain'}"
            parsed, tables = parse_daily_extract_tables_from_html(html, source_name, y, m)
            if len(parsed):
                parsed["url"] = url
                daily_extract_parsed.append(parsed)
            daily_extract_tables_summary.append({
                "url": url,
                "source_name": source_name,
                "tables_found": len(tables),
                "parsed_rows": len(parsed),
                "raw_path": rec.get("raw_path"),
                "text_sample": rec.get("text_sample", ""),
            })

daily_extract_fetch_df = pd.DataFrame(daily_extract_records)
daily_extract_fetch_df.to_csv(PROCESSED / "18d_hko_daily_extract_fetch_attempts.csv", index=False)

daily_extract_tables_df = pd.DataFrame(daily_extract_tables_summary)
daily_extract_tables_df.to_csv(PROCESSED / "18d_hko_daily_extract_table_parse_summary.csv", index=False)

daily_extract_parsed_df = pd.concat(daily_extract_parsed, ignore_index=True) if daily_extract_parsed else pd.DataFrame(columns=["event_date", "hko_tmax_C", "parse_route", "source_name", "url"])
print("Daily Extract fetch attempts:", len(daily_extract_fetch_df))
print("Daily Extract parsed rows:", len(daily_extract_parsed_df))
if len(daily_extract_tables_df):
    print(daily_extract_tables_df[["url", "tables_found", "parsed_rows", "raw_path"]].to_string(index=False))

# ---------------------------------------------------------------------
# Combine all candidate observations and focus on target dates
# ---------------------------------------------------------------------

all_candidates = []
for name, frame in [
    ("clmmaxt", clm_parsed),
    ("candidate_csv", candidate_parsed_df),
    ("daily_extract_html", daily_extract_parsed_df),
]:
    if len(frame):
        tmp = frame.copy()
        tmp["source_route"] = name
        all_candidates.append(tmp)

all_obs = pd.concat(all_candidates, ignore_index=True) if all_candidates else pd.DataFrame(columns=["event_date", "hko_tmax_C", "parse_route", "source_name", "source_route"])
all_obs["event_date"] = pd.to_datetime(all_obs["event_date"], errors="coerce").dt.date
all_obs = all_obs.dropna(subset=["event_date", "hko_tmax_C"])
all_obs = all_obs.drop_duplicates(["event_date", "hko_tmax_C", "source_route", "parse_route", "source_name"])

all_obs.to_csv(PROCESSED / "18d_hko_daily_extract_source_discovery_results.csv", index=False)

target_df = pd.DataFrame({"event_date": target_dates})
target_candidates = target_df.merge(all_obs, on="event_date", how="left")
target_candidates["target_found"] = target_candidates["hko_tmax_C"].notna()

target_candidates.to_csv(PROCESSED / "18d_hko_event_outcome_candidates.csv", index=False)

print("\nTarget outcome candidates:")
print(target_candidates.to_string(index=False))
print("\nTargets found:", int(target_candidates["target_found"].sum()), "/", len(target_df))

# ---------------------------------------------------------------------
# If official outcomes were found, build a compact event-outcome file
# ---------------------------------------------------------------------

def choose_best_outcome(group: pd.DataFrame) -> pd.Series:
    # Priority: Daily Extract HTML, candidate current-year CSV, CLMMAXT.
    priorities = {"daily_extract_html": 0, "candidate_csv": 1, "clmmaxt": 2}
    g = group.copy()
    g["_priority"] = g["source_route"].map(priorities).fillna(99)
    g = g.sort_values(["_priority", "source_name", "parse_route"]).reset_index(drop=True)
    return g.iloc[0].drop(labels=["_priority"], errors="ignore")

found = target_candidates[target_candidates["target_found"]].copy()
if len(found):
    chosen = (
        found.groupby("event_date", as_index=False, group_keys=False)
        .apply(choose_best_outcome)
        .reset_index(drop=True)
    )
else:
    chosen = pd.DataFrame(columns=target_candidates.columns)

event_out = cert.merge(chosen[["event_date", "hko_tmax_C", "source_route", "parse_route", "source_name"]], on="event_date", how="left")
event_out["hko_outcome_available_18d"] = event_out["hko_tmax_C"].notna()
event_out["Y_ge_K_18d"] = np.where(
    event_out["hko_outcome_available_18d"],
    (pd.to_numeric(event_out["hko_tmax_C"], errors="coerce") >= pd.to_numeric(event_out["threshold_K"], errors="coerce")).astype(int),
    np.nan,
)

event_out_path = PROCESSED / "18d_hko_daily_extract_event_outcomes.csv"
event_out.to_csv(event_out_path, index=False)
print("\nChosen event outcomes:")
print(event_out[[c for c in ["event_date", "threshold_K", "hko_tmax_C", "Y_ge_K_18d", "source_route", "parse_route", "source_name"] if c in event_out.columns]].to_string(index=False))

# ---------------------------------------------------------------------
# Optional: create a reconciled decision panel if 18b exists
# ---------------------------------------------------------------------

if DECISION_PATH.exists():
    decision = pd.read_csv(DECISION_PATH)
    decision["event_date"] = pd.to_datetime(decision["event_date"], errors="coerce").dt.date
    recon = decision.merge(
        event_out[["event_date", "threshold_K", "hko_tmax_C", "Y_ge_K_18d", "hko_outcome_available_18d", "source_route", "parse_route", "source_name"]],
        on=["event_date", "threshold_K"],
        how="left",
        suffixes=("", "_18d"),
    )
    # Prefer 18d official outcome if available.
    recon["hko_tmax_C_official"] = recon["hko_tmax_C_18d"] if "hko_tmax_C_18d" in recon.columns else recon["hko_tmax_C"]
    recon["Y_ge_K_official"] = recon["Y_ge_K_18d"]
    recon["official_outcome_available"] = recon["hko_outcome_available_18d"].fillna(False).astype(bool)
    recon["strict_scoring_ready_18d"] = recon["official_outcome_available"] & recon["no_lookahead_valid"].fillna(False).astype(bool) & recon["decision_price_available"].fillna(False).astype(bool)

    recon_path = PROCESSED / "18d_hko_daily_extract_reconciled_decision_panel.csv"
    scoring_path = PROCESSED / "18d_hko_daily_extract_scoring_ready_panel.csv"
    recon.to_csv(recon_path, index=False)
    recon[recon["strict_scoring_ready_18d"]].to_csv(scoring_path, index=False)
    print("\nReconciled decision panel shape:", recon.shape)
    print("Strict official scoring-ready 18d shape:", recon[recon["strict_scoring_ready_18d"]].shape)
else:
    print("\n18b decision panel not found; skipping reconciliation.")

# ---------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------

report = []
report.append("# 18d HKO Daily Extract Source Discovery Report\n")
report.append(f"Run timestamp UTC: `{RUN_TS}`\n")
report.append(f"Certified contracts: `{len(cert)}`\n")
report.append(f"Target dates: `{', '.join(map(str, target_dates))}`\n")
report.append("\n## Source routes tested\n")
report.append("- CLMMAXT all-year HKO open-data endpoint.\n")
report.append("- Candidate current-year CSDI/CIS CSV endpoints for maximum temperature.\n")
report.append("- HKO Daily Extract HTML pages for each target month in English and Chinese.\n")
report.append("\n## Candidate URL summary\n")
report.append(candidate_df[["status_code", "bytes", "content_type", "url"]].head(40).to_markdown(index=False))
report.append("\n\n## Daily Extract parse summary\n")
if len(daily_extract_tables_df):
    report.append(daily_extract_tables_df[["url", "tables_found", "parsed_rows", "raw_path"]].to_markdown(index=False))
else:
    report.append("No Daily Extract pages were fetched successfully.\n")
report.append("\n\n## Target outcome candidates\n")
report.append(target_candidates.to_markdown(index=False))
report.append("\n\n## Chosen event outcomes\n")
report.append(event_out[[c for c in ["event_date", "threshold_K", "hko_tmax_C", "Y_ge_K_18d", "source_route", "parse_route", "source_name"] if c in event_out.columns]].to_markdown(index=False))
report.append("\n\n## Interpretation\n")
if event_out["hko_outcome_available_18d"].sum() > 0:
    report.append("At least one certified contract has an official HKO realised maximum temperature candidate. These rows can be used to update the strict official scoring panel, subject to manual inspection of the saved raw source files.\n")
else:
    report.append("No official HKO realised maximum temperature was recovered for the certified event dates. The certified market and price panels remain valid, but strict realised-weather scoring remains pending source discovery or later HKO publication.\n")

report_path = REPORTS / "18d_hko_daily_extract_source_discovery_report.md"
report_path.write_text("\n".join(report), encoding="utf-8")
print("\nSaved report:", report_path)
print("Saved outputs:")
for p in [
    PROCESSED / "18d_hko_source_discovery_candidate_urls.csv",
    PROCESSED / "18d_hko_daily_extract_fetch_attempts.csv",
    PROCESSED / "18d_hko_daily_extract_table_parse_summary.csv",
    PROCESSED / "18d_hko_daily_extract_source_discovery_results.csv",
    PROCESSED / "18d_hko_event_outcome_candidates.csv",
    PROCESSED / "18d_hko_daily_extract_event_outcomes.csv",
    PROCESSED / "18d_hko_daily_extract_reconciled_decision_panel.csv",
    PROCESSED / "18d_hko_daily_extract_scoring_ready_panel.csv",
    report_path,
]:
    if p.exists():
        print(" -", p.relative_to(ROOT))
