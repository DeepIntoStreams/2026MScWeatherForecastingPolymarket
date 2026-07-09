
# 18c HKO Daily Extract outcome reconciliation
# Purpose:
#   Retrieve HKO realised daily maximum temperature outcomes for the formally certified
#   Hong Kong upper-tail contracts. This upgrades the provisional 18b panel from
#   Polymarket-resolution proxy outcomes to official HKO Daily Extract / CLMMAXT outcomes.
#
# Main outputs:
#   data/processed/18c_hko_daily_extract_event_outcomes.csv
#   data/processed/18c_hko_daily_extract_reconciled_decision_panel.csv
#   data/processed/18c_hko_daily_extract_scoring_ready_panel.csv
#   docs/research_outputs/18c_hko_daily_extract_outcome_reconciliation_report.md

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# ----------------------------
# Repository root detection
# ----------------------------

def find_repo_root(start: Path | None = None) -> Path:
    start = Path.cwd() if start is None else start
    for p in [start, *start.parents]:
        if (p / ".git").exists() or (p / "notebooks").exists():
            return p
    return start

ROOT = find_repo_root()
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"

for p in [DATA_RAW, DATA_INTERIM, DATA_PROCESSED, REPORTS]:
    p.mkdir(parents=True, exist_ok=True)

print("Repository root:", ROOT)

CERT_PATH = DATA_PROCESSED / "17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv"
DECISION_PATH = DATA_PROCESSED / "18b_hko_certified_upper_tail_decision_panel.csv"

if not CERT_PATH.exists():
    raise FileNotFoundError(f"Missing certified universe: {CERT_PATH}")

if not DECISION_PATH.exists():
    raise FileNotFoundError(f"Missing 18b decision panel: {DECISION_PATH}")

cert = pd.read_csv(CERT_PATH)
decision = pd.read_csv(DECISION_PATH)

cert["event_date"] = pd.to_datetime(cert["event_date"]).dt.date
cert["threshold_K"] = pd.to_numeric(cert["threshold_K"], errors="coerce")

print("Certified universe shape:", cert.shape)
print(cert[["event_date", "threshold_K", "event_slug", "market_slug"]].to_string(index=False))

# ----------------------------
# Utility functions
# ----------------------------

def safe_float(x: Any) -> float:
    if pd.isna(x):
        return np.nan
    s = str(x).strip()
    if not s or s in {"--", "-", "M", "Trace", "trace", "nan"}:
        return np.nan
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s:
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def normalise_col(c: Any) -> str:
    if isinstance(c, tuple):
        parts = [str(x) for x in c if str(x) != "nan"]
        c = " ".join(parts)
    c = str(c)
    c = re.sub(r"\s+", " ", c).strip()
    return c


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [normalise_col(c) for c in out.columns]
    return out


def parse_hko_clmmaxt() -> pd.DataFrame:
    """Parse HKO/Data.gov.hk daily maximum temperature all-year CSV.

    This source is monthly-updated and can lag recent certified contracts.
    """
    url = (
        "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php"
        "?dataType=CLMMAXT&rformat=csv&station=HKO"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    raw = r.text
    (DATA_RAW / "18c_hko_CLMMAXT_current.csv").write_text(raw, encoding="utf-8")

    # The CSV often has Chinese/English header variants. Try every small skiprows value.
    candidates = []
    for skip in range(0, 20):
        try:
            df = pd.read_csv(StringIO(raw), skiprows=skip)
            df = flatten_columns(df)
            cols_joined = " ".join(df.columns).lower()
            if ("date" in cols_joined or "年" in cols_joined or "year" in cols_joined) and (
                "value" in cols_joined or "數值" in cols_joined or "maximum" in cols_joined
            ):
                candidates.append((skip, df))
        except Exception:
            pass

    if not candidates:
        # Fall back to most plausible parse.
        df = pd.read_csv(StringIO(raw))
    else:
        # Prefer the candidate with the most rows and a value-like column.
        df = max(candidates, key=lambda x: len(x[1]))[1]

    df = flatten_columns(df)
    low_cols = {c: c.lower() for c in df.columns}

    # Identify date columns.
    date_col = None
    for c, lc in low_cols.items():
        if lc in {"date", "日期"} or "date" in lc or "日期" in lc:
            date_col = c
            break

    # Some files use Year/Month/Day columns.
    year_col = next((c for c, lc in low_cols.items() if lc in {"year", "年"} or lc == "年份"), None)
    month_col = next((c for c, lc in low_cols.items() if lc in {"month", "月"} or lc == "月份"), None)
    day_col = next((c for c, lc in low_cols.items() if lc in {"day", "日"} or lc == "日期"), None)

    # Identify value column. Avoid data-completeness columns.
    value_col = None
    preferred_patterns = [
        r"數值.*value",
        r"value",
        r"maximum.*temperature",
        r"daily maximum",
    ]
    excluded = ["complete", "completeness", "完整"]
    for pat in preferred_patterns:
        for c, lc in low_cols.items():
            if re.search(pat, lc) and not any(e in lc for e in excluded):
                value_col = c
                break
        if value_col:
            break

    if value_col is None:
        numeric_cols = []
        for c in df.columns:
            vals = pd.to_numeric(df[c], errors="coerce")
            if vals.notna().sum() > 100 and vals.between(-10, 45).mean() > 0.5:
                numeric_cols.append(c)
        if numeric_cols:
            value_col = numeric_cols[-1]

    if value_col is None:
        raise RuntimeError(f"Could not identify CLMMAXT value column. Columns: {df.columns.tolist()}")

    if date_col:
        dates = pd.to_datetime(df[date_col], errors="coerce")
    elif all(c is not None for c in [year_col, month_col, day_col]):
        dates = pd.to_datetime(
            df[[year_col, month_col, day_col]].rename(
                columns={year_col: "year", month_col: "month", day_col: "day"}
            ),
            errors="coerce",
        )
    else:
        raise RuntimeError(f"Could not identify CLMMAXT date columns. Columns: {df.columns.tolist()}")

    out = pd.DataFrame(
        {
            "event_date": dates.dt.date,
            "hko_tmax_C": df[value_col].map(safe_float),
            "hko_source": "CLMMAXT_monthly_open_data",
        }
    )
    out = out.dropna(subset=["event_date", "hko_tmax_C"]).drop_duplicates("event_date")
    out.to_csv(DATA_PROCESSED / "18c_hko_clmmaxt_current_parsed.csv", index=False)
    return out


def parse_hko_daily_extract_month(year: int, month: int) -> pd.DataFrame:
    """Parse HKO Daily Extract web page for a specific month.

    The table layout is not guaranteed, so this function saves raw HTML and all parsed tables
    for manual inspection if the heuristic fails.
    """
    url = f"https://www.hko.gov.hk/en/cis/dailyExtract.htm?m={month}&y={year}"
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    html = r.text

    raw_dir = DATA_RAW / "18c_hko_daily_extract_html"
    table_dir = DATA_RAW / "18c_hko_daily_extract_tables"
    raw_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    html_path = raw_dir / f"hko_daily_extract_{year}_{month:02d}.html"
    html_path.write_text(html, encoding="utf-8")

    try:
        tables = pd.read_html(StringIO(html))
    except Exception as e:
        print(f"No HTML tables parsed for {year}-{month:02d}: {e}")
        return pd.DataFrame(columns=["event_date", "hko_tmax_C", "hko_source", "daily_extract_url"])

    for i, tbl in enumerate(tables):
        flatten_columns(tbl).to_csv(table_dir / f"hko_daily_extract_{year}_{month:02d}_table_{i}.csv", index=False)

    parsed_candidates = []

    for i, tbl in enumerate(tables):
        df = flatten_columns(tbl)
        if df.empty:
            continue

        # Try to find a day/date column.
        day_col = None
        for c in df.columns:
            lc = c.lower()
            values = pd.to_numeric(df[c], errors="coerce")
            if "day" in lc or lc.strip() in {"date", "日"}:
                day_col = c
                break
            if values.dropna().between(1, 31).mean() > 0.8 and values.notna().sum() >= 10:
                day_col = c
                break

        # Try to find absolute daily maximum temperature column.
        max_col = None
        patterns = [
            r"absolute.*daily.*max",
            r"absolute.*max.*temp",
            r"max.*temp",
            r"maximum.*temp",
            r"daily.*max",
        ]
        for pat in patterns:
            for c in df.columns:
                lc = c.lower()
                if re.search(pat, lc) and "min" not in lc and "rain" not in lc:
                    vals = df[c].map(safe_float)
                    if vals.notna().sum() >= 1 and vals.between(-10, 45).mean() > 0.3:
                        max_col = c
                        break
            if max_col:
                break

        # If the column names are unhelpful, search numeric columns with plausible daily temp range.
        if max_col is None:
            plausible = []
            for c in df.columns:
                vals = df[c].map(safe_float)
                if vals.notna().sum() >= 5 and vals.between(10, 45).mean() > 0.5:
                    plausible.append((c, float(vals.mean(skipna=True))))
            # The absolute daily max is often among the higher mean temperature columns.
            if plausible:
                plausible_sorted = sorted(plausible, key=lambda x: x[1], reverse=True)
                max_col = plausible_sorted[0][0]

        if day_col is None or max_col is None:
            continue

        temp = pd.DataFrame()
        day_vals = pd.to_numeric(df[day_col], errors="coerce")
        temp_vals = df[max_col].map(safe_float)
        temp["day"] = day_vals
        temp["hko_tmax_C"] = temp_vals
        temp = temp.dropna(subset=["day", "hko_tmax_C"])
        temp["day"] = temp["day"].astype(int)
        temp = temp[temp["day"].between(1, 31)]

        if temp.empty:
            continue

        temp["event_date"] = pd.to_datetime(
            {
                "year": [year] * len(temp),
                "month": [month] * len(temp),
                "day": temp["day"].tolist(),
            },
            errors="coerce",
        ).dt.date

        temp["hko_source"] = "HKO_Daily_Extract_web_page"
        temp["daily_extract_url"] = url
        temp["daily_extract_table_index"] = i
        temp["daily_extract_day_col"] = day_col
        temp["daily_extract_max_col"] = max_col

        parsed_candidates.append(temp[[
            "event_date",
            "hko_tmax_C",
            "hko_source",
            "daily_extract_url",
            "daily_extract_table_index",
            "daily_extract_day_col",
            "daily_extract_max_col",
        ]])

    if not parsed_candidates:
        print(f"Could not identify Daily Extract max-temperature table for {year}-{month:02d}. Saved raw tables.")
        return pd.DataFrame(columns=[
            "event_date", "hko_tmax_C", "hko_source", "daily_extract_url",
            "daily_extract_table_index", "daily_extract_day_col", "daily_extract_max_col"
        ])

    # Choose candidate with the most daily rows.
    out = max(parsed_candidates, key=len).drop_duplicates("event_date")
    return out


# ----------------------------
# Retrieve realised values
# ----------------------------

clm = parse_hko_clmmaxt()
print("\nCLMMAXT parsed rows:", len(clm))
if len(clm):
    print("CLMMAXT date range:", clm["event_date"].min(), "to", clm["event_date"].max())

months = sorted({(d.year, d.month) for d in cert["event_date"]})
daily_extract_frames = []
for year, month in months:
    print(f"\nParsing HKO Daily Extract {year}-{month:02d}...")
    try:
        mdf = parse_hko_daily_extract_month(year, month)
        print("Rows parsed:", len(mdf))
        if len(mdf):
            print(mdf.head().to_string(index=False))
        daily_extract_frames.append(mdf)
    except Exception as e:
        print(f"Daily Extract parse failed for {year}-{month:02d}: {e}")

daily = pd.concat(daily_extract_frames, ignore_index=True) if daily_extract_frames else pd.DataFrame()
daily.to_csv(DATA_PROCESSED / "18c_hko_daily_extract_monthly_parsed.csv", index=False)

# Prefer Daily Extract, fallback to CLMMAXT.
event_dates = pd.DataFrame({"event_date": cert["event_date"].drop_duplicates()})
event_outcomes = event_dates.merge(daily, on="event_date", how="left")

fallback_cols = ["event_date", "hko_tmax_C", "hko_source"]
event_outcomes = event_outcomes.merge(
    clm[fallback_cols].rename(columns={"hko_tmax_C": "hko_tmax_C_clmmaxt", "hko_source": "hko_source_clmmaxt"}),
    on="event_date",
    how="left",
)

event_outcomes["hko_tmax_C_final"] = event_outcomes["hko_tmax_C"]
event_outcomes["hko_source_final"] = event_outcomes["hko_source"]

missing_daily = event_outcomes["hko_tmax_C_final"].isna()
event_outcomes.loc[missing_daily, "hko_tmax_C_final"] = event_outcomes.loc[missing_daily, "hko_tmax_C_clmmaxt"]
event_outcomes.loc[missing_daily, "hko_source_final"] = event_outcomes.loc[missing_daily, "hko_source_clmmaxt"]

# Mark future/pending based on HK current date.
if ZoneInfo is not None:
    today_hk = datetime.now(ZoneInfo("Asia/Hong_Kong")).date()
else:
    today_hk = datetime.utcnow().date()

event_outcomes["today_hk"] = str(today_hk)
event_outcomes["event_has_occurred"] = event_outcomes["event_date"].apply(lambda d: d <= today_hk)
event_outcomes["hko_outcome_available_18c"] = event_outcomes["hko_tmax_C_final"].notna()

outcomes = cert.merge(
    event_outcomes[["event_date", "hko_tmax_C_final", "hko_source_final", "hko_outcome_available_18c", "event_has_occurred", "today_hk"]],
    on="event_date",
    how="left",
)
outcomes["hko_tmax_C"] = pd.to_numeric(outcomes["hko_tmax_C_final"], errors="coerce")
outcomes["Y_ge_K"] = np.where(
    outcomes["hko_tmax_C"].notna(),
    (outcomes["hko_tmax_C"] >= outcomes["threshold_K"]).astype(int),
    np.nan,
)

outcomes_path = DATA_PROCESSED / "18c_hko_daily_extract_event_outcomes.csv"
outcomes.to_csv(outcomes_path, index=False)

print("\n18c event outcome table:")
show_cols = [
    "event_date", "threshold_K", "hko_tmax_C", "Y_ge_K", "hko_source_final",
    "hko_outcome_available_18c", "event_has_occurred", "market_slug"
]
print(outcomes[[c for c in show_cols if c in outcomes.columns]].to_string(index=False))
print("Saved:", outcomes_path)

# ----------------------------
# Reconcile 18b decision panel
# ----------------------------

decision["event_date"] = pd.to_datetime(decision["event_date"]).dt.date
decision["threshold_K"] = pd.to_numeric(decision["threshold_K"], errors="coerce")

merge_cols = ["event_date", "threshold_K"]
recon = decision.merge(
    outcomes[merge_cols + ["hko_tmax_C", "Y_ge_K", "hko_source_final", "hko_outcome_available_18c"]],
    on=merge_cols,
    how="left",
    suffixes=("", "_18c"),
)

# Prefer 18c official HKO values.
recon["hko_tmax_C"] = recon["hko_tmax_C_18c"] if "hko_tmax_C_18c" in recon.columns else recon["hko_tmax_C"]
recon["Y_ge_K"] = recon["Y_ge_K_18c"] if "Y_ge_K_18c" in recon.columns else recon["Y_ge_K"]
recon["outcome_source"] = np.where(
    recon["hko_outcome_available_18c"].fillna(False),
    recon["hko_source_final"],
    "missing_pending_hko_daily_extract"
)

recon_path = DATA_PROCESSED / "18c_hko_daily_extract_reconciled_decision_panel.csv"
recon.to_csv(recon_path, index=False)

# Scoring-ready: valid decision price and official HKO outcome.
valid_col = "no_lookahead_valid" if "no_lookahead_valid" in recon.columns else None
price_col = "decision_price_available" if "decision_price_available" in recon.columns else None

mask = recon["hko_outcome_available_18c"].fillna(False)
if valid_col:
    mask &= recon[valid_col].fillna(False)
if price_col:
    mask &= recon[price_col].fillna(False)

scoring = recon[mask].copy()
scoring_path = DATA_PROCESSED / "18c_hko_daily_extract_scoring_ready_panel.csv"
scoring.to_csv(scoring_path, index=False)

print("\nReconciled decision panel shape:", recon.shape)
print("Scoring-ready official HKO panel shape:", scoring.shape)
print("Saved:", recon_path)
print("Saved:", scoring_path)

if len(scoring):
    print("\nScoring-ready rows:")
    cols = [c for c in ["event_date", "threshold_K", "decision_rule", "yes_price", "hko_tmax_C", "Y_ge_K", "outcome_source"] if c in scoring.columns]
    print(scoring[cols].to_string(index=False))

# ----------------------------
# Report
# ----------------------------

report = []
report.append("# 18c HKO Daily Extract outcome reconciliation\n")
report.append(f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}\n")
report.append(f"Certified universe rows: {len(cert)}\n")
report.append(f"CLMMAXT parsed rows: {len(clm)}\n")
report.append(f"HKO Daily Extract parsed rows: {len(daily)}\n")
report.append(f"Event outcomes with official HKO value: {int(outcomes['hko_outcome_available_18c'].sum())} / {len(outcomes)}\n")
report.append(f"Reconciled decision panel rows: {len(recon)}\n")
report.append(f"Official HKO scoring-ready rows: {len(scoring)}\n")
report.append("\n## Event outcomes\n\n")
report.append(outcomes[[c for c in show_cols if c in outcomes.columns]].to_markdown(index=False))
report.append("\n\n## Interpretation\n\n")
if len(scoring):
    report.append("At least one certified upper-tail contract now has an official HKO realised outcome and a no-lookahead market decision price. The corresponding rows may be used for strict market-outcome scoring.\n")
else:
    report.append("No strict official-HKO scoring rows are available yet. The certified market-price panel remains valid, but final scoring must wait for HKO Daily Extract values or a successful historical-version reconstruction.\n")

report_path = REPORTS / "18c_hko_daily_extract_outcome_reconciliation_report.md"
report_path.write_text("\n".join(report), encoding="utf-8")
print("Saved report:", report_path)
