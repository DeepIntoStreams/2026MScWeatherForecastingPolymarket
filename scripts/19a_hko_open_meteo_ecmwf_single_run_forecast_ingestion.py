#!/usr/bin/env python3
"""
19a HKO forecast-side ingestion via Open-Meteo Single Runs API.

Purpose
-------
This script starts the forecast-side empirical pipeline after the 18j-18m market baseline.
It retrieves historical individual ECMWF IFS HRES model runs for the Hong Kong Observatory
contract dates, aligns each run to the no-lookahead decision cutoffs, converts the point
2m-temperature forecast into HKO local-day maximum forecasts, and creates a temporary
probability panel for each HKO contract-event row.

Important methodological note
-----------------------------
This is a forecast-ingestion and deterministic-to-probability bridge, not the final
probabilistic AI/ensemble model. The source is the Open-Meteo Single Runs API, which
serves archived individual ECMWF IFS HRES runs as JSON. The final dissertation should
label this clearly as a third-party archived ECMWF IFS point-forecast source. It is useful
for immediate no-lookahead model-side backtesting while direct ECMWF archive/AIFS-ENS
access is pending.

Outputs
-------
- data/processed/19a_hko_ecmwf_single_run_request_plan.csv
- data/processed/19a_hko_ecmwf_single_run_fetch_inventory.csv
- data/processed/19a_hko_ecmwf_single_run_hourly_forecasts.csv
- data/processed/19a_hko_ecmwf_single_run_daily_max_forecasts.csv
- data/processed/19a_hko_ecmwf_contract_event_probability_panel.csv
- data/processed/19a_hko_ecmwf_probability_score_summary.csv
- data/processed/19a_hko_ecmwf_forecast_integrity_checks.csv
- data/processed/19a_hko_ecmwf_forecast_issues.csv
- docs/research_outputs/19a_hko_ecmwf_single_run_forecast_ingestion_report.md
- data/review_bundles/19a_review_bundle.zip
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import requests
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'requests'. Install with: python3 -m pip install requests"
    ) from exc


# -----------------------------
# Configuration
# -----------------------------

SCRIPT_NAME = "19a_hko_open_meteo_ecmwf_single_run_forecast_ingestion.py"
BASE_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
OPEN_METEO_MODEL = "ecmwf_ifs"  # ECMWF IFS HRES 9km in Single Runs API.

# Approximate Hong Kong Observatory headquarters / King's Park area point.
# This is not the official HKO station observation itself; it is a model gridpoint/proxy.
HKO_LAT = float(os.environ.get("HKO_FORECAST_LAT", "22.302219"))
HKO_LON = float(os.environ.get("HKO_FORECAST_LON", "114.174637"))
HKO_TIMEZONE = "Asia/Hong_Kong"

# Conservative availability delay: global runs usually become available several hours after initialisation.
# This preserves no-lookahead by only using runs whose assumed availability time is before the decision cutoff.
AVAILABILITY_DELAY_HOURS = int(os.environ.get("FORECAST_AVAILABILITY_DELAY_HOURS", "6"))

# Temporary Gaussian uncertainty bridge around deterministic local-day maximum.
# This is intentionally labelled as a temporary baseline, not a final calibrated ensemble probability.
SIGMA_C = float(os.environ.get("FORECAST_PROXY_SIGMA_C", "1.5"))
EPS = 1e-6
REQUEST_SLEEP_SECONDS = float(os.environ.get("OPEN_METEO_REQUEST_SLEEP_SECONDS", "0.12"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("OPEN_METEO_TIMEOUT_SECONDS", "60"))
MAX_RETRIES = int(os.environ.get("OPEN_METEO_MAX_RETRIES", "3"))

# Request a rich enough feature set now; downstream steps can decide which columns to use.
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
]

DECISION_RULE_OFFSETS_HOURS = {
    "24h_prior": -24,
    "12h_prior": -12,
    "6h_prior": -6,
    "event_day_open": 0,
}


# -----------------------------
# Helpers
# -----------------------------

def find_repo_root() -> Path:
    p = Path.cwd().resolve()
    if p.name == "notebooks":
        return p.parent
    for cand in [p] + list(p.parents):
        if (cand / ".git").exists() or (cand / "data" / "processed").exists():
            return cand
    return p


def ensure_dirs(root: Path) -> Dict[str, Path]:
    dirs = {
        "processed": root / "data" / "processed",
        "raw": root / "data" / "raw" / "forecast_open_meteo_single_runs_19a",
        "docs": root / "docs" / "research_outputs",
        "bundles": root / "data" / "review_bundles",
        "logs": root / "logs",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def read_csv_safely(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Missing required input file: {path}")
    return pd.read_csv(path, **kwargs)


def parse_float_from_text(text: Any) -> Optional[float]:
    s = "" if pd.isna(text) else str(text)
    # Handles labels such as "30°C", "30C", "30°C or higher", "15corbelow" via title/question where possible.
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°\s*)?[Cc]\b", s)
    if not m:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*c(?:orhigher|orbelow)?\b", s.lower())
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def finite_or_none(x: Any) -> Optional[float]:
    try:
        if pd.isna(x):
            return None
        v = float(x)
        if math.isfinite(v):
            return v
        return None
    except Exception:
        return None


def infer_contract_bounds(row: pd.Series) -> Tuple[float, float, str]:
    etype = str(row.get("contract_event_type_v2", "")).strip()

    label_temp = finite_or_none(row.get("label_temperature_C"))
    if label_temp is None:
        for col in ["group_item_title", "market_question", "market_slug", "event_set_v2"]:
            label_temp = parse_float_from_text(row.get(col))
            if label_temp is not None:
                break

    if label_temp is None:
        return (np.nan, np.nan, "missing_label_temperature")

    if etype == "upper_tail":
        return (label_temp, np.inf, f"T_HKO >= {label_temp:g}")
    if etype == "lower_tail_endpoint":
        upper = label_temp + 1.0
        return (-np.inf, upper, f"T_HKO < {upper:g}")
    if etype == "interior_bin":
        upper = label_temp + 1.0
        return (label_temp, upper, f"{label_temp:g} <= T_HKO < {upper:g}")

    return (np.nan, np.nan, f"unsupported_event_type:{etype}")


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def event_probability_from_mu(mu: float, lower: float, upper: float, sigma: float) -> float:
    if not math.isfinite(mu) or not math.isfinite(sigma) or sigma <= 0:
        return np.nan
    if math.isinf(lower) and lower < 0 and math.isinf(upper) and upper > 0:
        return 1.0
    if math.isinf(lower) and lower < 0:
        return normal_cdf((upper - mu) / sigma)
    if math.isinf(upper) and upper > 0:
        return 1.0 - normal_cdf((lower - mu) / sigma)
    return normal_cdf((upper - mu) / sigma) - normal_cdf((lower - mu) / sigma)


def event_hard_indicator_from_mu(mu: float, lower: float, upper: float) -> float:
    if not math.isfinite(mu):
        return np.nan
    if math.isinf(lower) and lower < 0:
        return float(mu < upper)
    if math.isinf(upper) and upper > 0:
        return float(mu >= lower)
    return float((mu >= lower) and (mu < upper))


def hk_local_day_start_utc(event_date: date) -> datetime:
    # HKT is UTC+8 and has no daylight saving time. HKO settlement day is local calendar day.
    return datetime(event_date.year, event_date.month, event_date.day, 0, 0, tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)


def latest_6h_run_before_availability_cutoff(cutoff_utc: datetime, delay_hours: int) -> datetime:
    latest_init_allowed = cutoff_utc - timedelta(hours=delay_hours)
    latest_init_allowed = latest_init_allowed.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    # Round down to previous 6-hour synoptic cycle.
    hour = (latest_init_allowed.hour // 6) * 6
    return latest_init_allowed.replace(hour=hour)


def dt_to_run_string(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M")


def dt_to_compact(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")


def request_params(run_init_utc: datetime) -> Dict[str, Any]:
    return {
        "latitude": f"{HKO_LAT:.6f}",
        "longitude": f"{HKO_LON:.6f}",
        "run": dt_to_run_string(run_init_utc),
        "hourly": ",".join(HOURLY_VARIABLES),
        "models": OPEN_METEO_MODEL,
        "timezone": HKO_TIMEZONE,
        "forecast_days": 10,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "timeformat": "iso8601",
    }


def cache_path_for_run(raw_dir: Path, run_init_utc: datetime) -> Path:
    return raw_dir / f"open_meteo_single_run_{OPEN_METEO_MODEL}_hko_{dt_to_compact(run_init_utc)}.json"


def fetch_json_with_cache(raw_dir: Path, run_init_utc: datetime) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    params = request_params(run_init_utc)
    cache_path = cache_path_for_run(raw_dir, run_init_utc)
    request_url = BASE_URL + "?" + requests.compat.urlencode(params)

    inventory = {
        "run_init_utc": dt_to_run_string(run_init_utc),
        "model": OPEN_METEO_MODEL,
        "cache_path": str(cache_path),
        "request_url": request_url,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "used_cache": False,
        "status_code": None,
        "success": False,
        "error": "",
        "n_hourly_rows": 0,
    }

    if cache_path.exists() and cache_path.stat().st_size > 0:
        try:
            payload = json.loads(cache_path.read_text())
            n_hourly = len(payload.get("hourly", {}).get("time", []))
            inventory.update({"used_cache": True, "status_code": "cache", "success": n_hourly > 0, "n_hourly_rows": n_hourly})
            if n_hourly > 0:
                return payload, inventory
        except Exception as exc:
            inventory["error"] = f"cache_read_error:{exc}"

    last_error = ""
    status_code = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            status_code = r.status_code
            if r.status_code == 200:
                payload = r.json()
                n_hourly = len(payload.get("hourly", {}).get("time", []))
                cache_path.write_text(json.dumps(payload, indent=2))
                inventory.update({"status_code": status_code, "success": n_hourly > 0, "n_hourly_rows": n_hourly})
                return payload, inventory
            last_error = f"HTTP {r.status_code}: {r.text[:500]}"
        except Exception as exc:
            last_error = f"request_error_attempt_{attempt}:{exc}"
        time.sleep(min(2.0, 0.5 * attempt))

    inventory.update({"status_code": status_code, "success": False, "error": last_error})
    return None, inventory


def payload_to_hourly_df(payload: Dict[str, Any], run_init_utc: datetime) -> pd.DataFrame:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return pd.DataFrame()

    df = pd.DataFrame({"forecast_valid_time_local": pd.to_datetime(times)})
    for var in HOURLY_VARIABLES:
        values = hourly.get(var)
        if values is not None:
            df[var] = values
        else:
            # Some Open-Meteo responses add model suffixes if multiple models are requested.
            matching = [k for k in hourly.keys() if k.startswith(var)]
            if matching:
                df[var] = hourly[matching[0]]
            else:
                df[var] = np.nan

    df["run_init_utc"] = run_init_utc.astimezone(timezone.utc).isoformat()
    df["run_init_utc_str"] = dt_to_run_string(run_init_utc)
    df["model"] = OPEN_METEO_MODEL
    df["forecast_valid_date_hkt"] = df["forecast_valid_time_local"].dt.date.astype(str)
    df["forecast_valid_hour_hkt"] = df["forecast_valid_time_local"].dt.hour
    # Convert valid local time back to a timezone-aware UTC approximation for lead calculation.
    # Open-Meteo returns local ISO strings without offset when timezone is requested; HKT is UTC+8.
    valid_utc = df["forecast_valid_time_local"] - pd.Timedelta(hours=8)
    run_ts = pd.Timestamp(run_init_utc.astimezone(timezone.utc).replace(tzinfo=None))
    df["lead_hours_from_run_init"] = (valid_utc - run_ts).dt.total_seconds() / 3600.0
    return df


def make_request_plan(target: pd.DataFrame) -> pd.DataFrame:
    event_dates = sorted(pd.to_datetime(target["event_date"]).dt.date.unique())
    rows: List[Dict[str, Any]] = []
    for d in event_dates:
        local_start_utc = hk_local_day_start_utc(d)
        for rule, offset in DECISION_RULE_OFFSETS_HOURS.items():
            cutoff = local_start_utc + timedelta(hours=offset)
            run_init = latest_6h_run_before_availability_cutoff(cutoff, AVAILABILITY_DELAY_HOURS)
            rows.append(
                {
                    "event_date": d.isoformat(),
                    "decision_rule": rule,
                    "decision_cutoff_utc": cutoff.isoformat(),
                    "availability_delay_hours_assumed": AVAILABILITY_DELAY_HOURS,
                    "selected_run_init_utc": run_init.isoformat(),
                    "selected_run_available_utc_assumed": (run_init + timedelta(hours=AVAILABILITY_DELAY_HOURS)).isoformat(),
                    "selected_run_before_cutoff": (run_init + timedelta(hours=AVAILABILITY_DELAY_HOURS)) <= cutoff,
                    "model": OPEN_METEO_MODEL,
                }
            )
    return pd.DataFrame(rows)


def summarise_scores(prob_panel: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    if prob_panel.empty:
        return pd.DataFrame(rows)

    groupers = [("ALL", ["decision_rule"]), ("BY_TYPE", ["decision_rule", "contract_event_type_v2"])]
    for label, cols in groupers:
        grouped = prob_panel.dropna(subset=["p_ecmwf_proxy", "Y_event_int"]).groupby(cols, dropna=False)
        for key, g in grouped:
            if not isinstance(key, tuple):
                key = (key,)
            row = {col: val for col, val in zip(cols, key)}
            row.update(
                {
                    "summary_level": label,
                    "n": int(len(g)),
                    "mean_brier_ecmwf_proxy": float(g["brier_ecmwf_proxy"].mean()),
                    "mean_log_score_ecmwf_proxy": float(g["log_score_ecmwf_proxy"].mean()),
                    "mean_p_ecmwf_proxy": float(g["p_ecmwf_proxy"].mean()),
                    "outcome_rate": float(g["Y_event_int"].mean()),
                    "mean_forecast_daily_max_C": float(g["forecast_hko_daily_max_C"].mean()),
                    "mean_hko_tmax_C": float(g["hko_tmax_C"].mean()) if "hko_tmax_C" in g else np.nan,
                    "mean_temperature_error_C": float((g["forecast_hko_daily_max_C"] - g["hko_tmax_C"]).mean()) if "hko_tmax_C" in g else np.nan,
                    "mean_abs_temperature_error_C": float((g["forecast_hko_daily_max_C"] - g["hko_tmax_C"]).abs().mean()) if "hko_tmax_C" in g else np.nan,
                    "mean_brier_ecmwf_hard": float(g["brier_ecmwf_hard"].mean()),
                    "mean_log_score_ecmwf_hard": float(g["log_score_ecmwf_hard"].mean()),
                }
            )
            rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty:
        sort_cols = [c for c in ["summary_level", "decision_rule", "contract_event_type_v2"] if c in out.columns]
        out = out.sort_values(sort_cols).reset_index(drop=True)
    return out


def write_markdown_report(
    path: Path,
    target_rows: int,
    request_plan: pd.DataFrame,
    inventory: pd.DataFrame,
    hourly_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    prob_panel: pd.DataFrame,
    score_summary: pd.DataFrame,
    checks: pd.DataFrame,
    issues: pd.DataFrame,
) -> None:
    success_runs = int(inventory.get("success", pd.Series(dtype=bool)).fillna(False).sum()) if not inventory.empty else 0
    total_runs = int(len(inventory))
    score_all = score_summary[score_summary.get("summary_level", "") == "ALL"].copy() if not score_summary.empty else pd.DataFrame()

    lines: List[str] = []
    lines.append("# 19a HKO ECMWF single-run forecast ingestion\n")
    lines.append(f"Generated: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n")
    lines.append("## Purpose\n")
    lines.append(
        "This step starts the forecast-side empirical pipeline. It retrieves archived individual ECMWF IFS HRES model runs "
        "for the Hong Kong contract dates through the Open-Meteo Single Runs API, aligns each selected run to the no-lookahead "
        "decision cutoffs used in the market baseline, computes Hong Kong local-day maximum temperature forecasts, and maps those "
        "temperature forecasts into temporary contract-event probabilities.\n"
    )
    lines.append("## Methodological status\n")
    lines.append(
        "The source is a third-party archived ECMWF IFS HRES point-forecast API, not the final direct ECMWF MARS/AIFS-ENS route. "
        "The probability column `p_ecmwf_proxy` is a temporary Gaussian uncertainty bridge around the deterministic daily-maximum "
        f"forecast with sigma `{SIGMA_C}` degrees Celsius. It is suitable for pipeline testing and an initial deterministic model baseline, "
        "but it should not be described as a calibrated ensemble probability.\n"
    )
    lines.append("## Main result\n")
    lines.append(f"- Input 18k target rows: `{target_rows}`\n")
    lines.append(f"- Request-plan rows: `{len(request_plan)}`\n")
    lines.append(f"- Unique selected model runs: `{request_plan['selected_run_init_utc'].nunique() if not request_plan.empty else 0}`\n")
    lines.append(f"- Successfully fetched runs: `{success_runs}` / `{total_runs}`\n")
    lines.append(f"- Hourly forecast rows: `{len(hourly_df)}`\n")
    lines.append(f"- Daily maximum forecast rows: `{len(daily_df)}`\n")
    lines.append(f"- Contract-event probability rows: `{len(prob_panel)}`\n")
    ready_rows = int(prob_panel["p_ecmwf_proxy"].notna().sum()) if not prob_panel.empty and "p_ecmwf_proxy" in prob_panel else 0
    lines.append(f"- Probability-ready rows: `{ready_rows}`\n")
    lines.append(f"- Issue rows: `{len(issues)}`\n")

    lines.append("\n## Forecast score summary\n")
    if not score_all.empty:
        display_cols = [
            "decision_rule", "n", "mean_brier_ecmwf_proxy", "mean_log_score_ecmwf_proxy",
            "mean_p_ecmwf_proxy", "outcome_rate", "mean_forecast_daily_max_C", "mean_hko_tmax_C",
            "mean_temperature_error_C", "mean_abs_temperature_error_C",
        ]
        lines.append(score_all[[c for c in display_cols if c in score_all.columns]].to_markdown(index=False))
        lines.append("\n")
    else:
        lines.append("No score-ready rows were produced. Inspect the issue table and API inventory.\n")

    lines.append("\n## Integrity checks\n")
    lines.append(checks.to_markdown(index=False) if not checks.empty else "No checks written.")
    lines.append("\n")

    lines.append("\n## Request-plan preview\n")
    lines.append(request_plan.head(20).to_markdown(index=False) if not request_plan.empty else "No request plan rows.")
    lines.append("\n")

    lines.append("\n## Fetch inventory preview\n")
    inv_preview_cols = ["run_init_utc", "model", "used_cache", "status_code", "success", "n_hourly_rows", "error"]
    if not inventory.empty:
        lines.append(inventory[[c for c in inv_preview_cols if c in inventory.columns]].head(30).to_markdown(index=False))
    else:
        lines.append("No inventory rows.")
    lines.append("\n")

    lines.append("\n## Daily forecast preview\n")
    daily_preview_cols = [
        "event_date", "decision_rule", "selected_run_init_utc", "decision_cutoff_utc",
        "forecast_hko_daily_max_C", "n_hourly_values_for_event_day", "target_hko_tmax_C",
        "temperature_error_C", "abs_temperature_error_C",
    ]
    if not daily_df.empty:
        lines.append(daily_df[[c for c in daily_preview_cols if c in daily_df.columns]].head(40).to_markdown(index=False))
    else:
        lines.append("No daily forecast rows.")
    lines.append("\n")

    lines.append("\n## Issues requiring review\n")
    if not issues.empty:
        lines.append(f"Issue rows: `{len(issues)}`\n")
        lines.append(issues.head(50).to_markdown(index=False))
    else:
        lines.append("No issues detected by the automated checks.\n")

    lines.append("\n## Interpretation\n")
    if ready_rows > 0:
        lines.append(
            "The forecast-side ingestion layer is operational. The next step can compare `p_ecmwf_proxy` against Polymarket prices "
            "on common decision-rule support, then replace this temporary Gaussian bridge with ensemble-implied probabilities once "
            "AIFS/ENS member forecasts or another calibrated probabilistic route is available.\n"
        )
    else:
        lines.append(
            "The code path executed but did not produce probability-ready rows. This usually means the API calls failed, the selected run "
            "model name is unavailable, or the event dates were outside the archive. Inspect `19a_hko_ecmwf_single_run_fetch_inventory.csv` "
            "and `19a_hko_ecmwf_forecast_issues.csv`.\n"
        )

    lines.append("\n## Output files\n")
    for rel in [
        "data/processed/19a_hko_ecmwf_single_run_request_plan.csv",
        "data/processed/19a_hko_ecmwf_single_run_fetch_inventory.csv",
        "data/processed/19a_hko_ecmwf_single_run_hourly_forecasts.csv",
        "data/processed/19a_hko_ecmwf_single_run_daily_max_forecasts.csv",
        "data/processed/19a_hko_ecmwf_contract_event_probability_panel.csv",
        "data/processed/19a_hko_ecmwf_probability_score_summary.csv",
        "data/processed/19a_hko_ecmwf_forecast_integrity_checks.csv",
        "data/processed/19a_hko_ecmwf_forecast_issues.csv",
        "docs/research_outputs/19a_hko_ecmwf_single_run_forecast_ingestion_report.md",
        "data/review_bundles/19a_review_bundle.zip",
    ]:
        lines.append(f"- `{rel}`")

    path.write_text("\n".join(lines))


def write_bundle(bundle_path: Path, root: Path, files: Iterable[Path]) -> None:
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if f.exists():
                try:
                    arcname = str(f.relative_to(root))
                except ValueError:
                    arcname = f.name
                zf.write(f, arcname=arcname)


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    root = find_repo_root()
    os.chdir(root)
    dirs = ensure_dirs(root)
    print(f"Repository root: {root}")
    print(f"Open-Meteo model: {OPEN_METEO_MODEL}")
    print(f"HKO forecast point: lat={HKO_LAT}, lon={HKO_LON}")
    print(f"Assumed model-run availability delay: {AVAILABILITY_DELAY_HOURS} hours")

    target_path = dirs["processed"] / "18k_full_hko_contract_event_target_panel.csv"
    target = read_csv_safely(target_path)
    print(f"18k target rows loaded: {target.shape}")

    # Restrict to the ready HKO target panel.
    if "target_panel_ready" in target.columns:
        target_ready = target[target["target_panel_ready"].astype(str).str.lower().isin(["true", "1"] )].copy()
        if target_ready.empty:
            target_ready = target.copy()
    else:
        target_ready = target.copy()

    if "Y_event_int" not in target_ready.columns:
        if "Y_event" in target_ready.columns:
            target_ready["Y_event_int"] = target_ready["Y_event"]
        else:
            raise SystemExit("18k target panel is missing Y_event_int/Y_event.")
    target_ready["Y_event_int"] = pd.to_numeric(target_ready["Y_event_int"], errors="coerce")
    target_ready["event_date"] = pd.to_datetime(target_ready["event_date"]).dt.date.astype(str)

    # Infer numerical event bounds once.
    bounds = target_ready.apply(infer_contract_bounds, axis=1, result_type="expand")
    bounds.columns = ["event_lower_C", "event_upper_C", "event_condition_from_bounds"]
    target_ready = pd.concat([target_ready.reset_index(drop=True), bounds.reset_index(drop=True)], axis=1)

    bound_issue_mask = target_ready["event_lower_C"].isna() | target_ready["event_upper_C"].isna()
    bound_issues = target_ready.loc[bound_issue_mask, ["event_date", "market_slug", "group_item_title", "contract_event_type_v2", "event_condition_from_bounds"]].copy() if bound_issue_mask.any() else pd.DataFrame()
    if not bound_issues.empty:
        bound_issues.insert(0, "issue_type", "event_bound_parse_failed")

    request_plan = make_request_plan(target_ready)
    request_plan_path = dirs["processed"] / "19a_hko_ecmwf_single_run_request_plan.csv"
    request_plan.to_csv(request_plan_path, index=False)
    print(f"Request-plan rows: {len(request_plan)}")

    unique_runs = sorted(pd.to_datetime(request_plan["selected_run_init_utc"], utc=True).dt.to_pydatetime().tolist())
    # Remove duplicates while preserving sorted order.
    seen = set()
    unique_runs_dedup: List[datetime] = []
    for r in unique_runs:
        key = dt_to_run_string(r)
        if key not in seen:
            unique_runs_dedup.append(r)
            seen.add(key)
    print(f"Unique selected model runs: {len(unique_runs_dedup)}")

    inventory_rows: List[Dict[str, Any]] = []
    hourly_frames: List[pd.DataFrame] = []

    for idx, run_init in enumerate(unique_runs_dedup, start=1):
        print(f"Fetching run {idx}/{len(unique_runs_dedup)}: {dt_to_run_string(run_init)} UTC")
        payload, inv = fetch_json_with_cache(dirs["raw"], run_init)
        inventory_rows.append(inv)
        if payload is not None and inv.get("success"):
            hdf = payload_to_hourly_df(payload, run_init)
            if not hdf.empty:
                hourly_frames.append(hdf)
        time.sleep(REQUEST_SLEEP_SECONDS)

    inventory = pd.DataFrame(inventory_rows)
    inventory_path = dirs["processed"] / "19a_hko_ecmwf_single_run_fetch_inventory.csv"
    inventory.to_csv(inventory_path, index=False)

    hourly_df = pd.concat(hourly_frames, ignore_index=True) if hourly_frames else pd.DataFrame()
    hourly_path = dirs["processed"] / "19a_hko_ecmwf_single_run_hourly_forecasts.csv"
    hourly_df.to_csv(hourly_path, index=False)
    print(f"Hourly forecast rows: {len(hourly_df)}")

    # Daily max forecasts for each selected run and HKT date.
    if not hourly_df.empty and "temperature_2m" in hourly_df.columns:
        hourly_df["temperature_2m"] = pd.to_numeric(hourly_df["temperature_2m"], errors="coerce")
        daily_by_run = (
            hourly_df.dropna(subset=["temperature_2m"])
            .groupby(["run_init_utc", "run_init_utc_str", "forecast_valid_date_hkt", "model"], dropna=False)
            .agg(
                forecast_hko_daily_max_C=("temperature_2m", "max"),
                forecast_hko_daily_mean_C=("temperature_2m", "mean"),
                n_hourly_values_for_event_day=("temperature_2m", "size"),
                first_forecast_valid_time_local=("forecast_valid_time_local", "min"),
                last_forecast_valid_time_local=("forecast_valid_time_local", "max"),
                min_lead_hours_from_run_init=("lead_hours_from_run_init", "min"),
                max_lead_hours_from_run_init=("lead_hours_from_run_init", "max"),
            )
            .reset_index()
        )
    else:
        daily_by_run = pd.DataFrame()

    # Join request-plan event dates to the corresponding daily forecast from that selected run.
    if not daily_by_run.empty:
        req = request_plan.copy()
        req["run_init_utc_str"] = pd.to_datetime(req["selected_run_init_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M")
        daily_df = req.merge(
            daily_by_run,
            left_on=["run_init_utc_str", "event_date"],
            right_on=["run_init_utc_str", "forecast_valid_date_hkt"],
            how="left",
            suffixes=("", "_forecast"),
        )
    else:
        daily_df = request_plan.copy()
        daily_df["forecast_hko_daily_max_C"] = np.nan
        daily_df["n_hourly_values_for_event_day"] = 0

    # Add realised HKO daily max per event date for temperature-error diagnostics.
    realised = (
        target_ready[["event_date", "hko_tmax_C"]]
        .drop_duplicates("event_date")
        .copy()
        if "hko_tmax_C" in target_ready.columns
        else pd.DataFrame({"event_date": sorted(target_ready["event_date"].unique()), "hko_tmax_C": np.nan})
    )
    realised["hko_tmax_C"] = pd.to_numeric(realised["hko_tmax_C"], errors="coerce")
    daily_df = daily_df.merge(realised.rename(columns={"hko_tmax_C": "target_hko_tmax_C"}), on="event_date", how="left")
    daily_df["temperature_error_C"] = pd.to_numeric(daily_df.get("forecast_hko_daily_max_C"), errors="coerce") - pd.to_numeric(daily_df.get("target_hko_tmax_C"), errors="coerce")
    daily_df["abs_temperature_error_C"] = daily_df["temperature_error_C"].abs()
    daily_path = dirs["processed"] / "19a_hko_ecmwf_single_run_daily_max_forecasts.csv"
    daily_df.to_csv(daily_path, index=False)
    print(f"Daily max forecast rows: {len(daily_df)}")

    # Build contract-event probability panel.
    prob_panel = target_ready.merge(
        daily_df[
            [
                "event_date", "decision_rule", "decision_cutoff_utc", "selected_run_init_utc",
                "selected_run_available_utc_assumed", "selected_run_before_cutoff", "model",
                "forecast_hko_daily_max_C", "forecast_hko_daily_mean_C" if "forecast_hko_daily_mean_C" in daily_df.columns else "event_date",
                "n_hourly_values_for_event_day", "temperature_error_C", "abs_temperature_error_C",
            ]
        ].copy(),
        on="event_date",
        how="left",
        suffixes=("", "_forecast"),
    )
    # Clean accidental duplicate helper if forecast_hko_daily_mean_C missing.
    if "event_date_forecast" in prob_panel.columns:
        prob_panel = prob_panel.drop(columns=["event_date_forecast"])

    prob_panel["forecast_hko_daily_max_C"] = pd.to_numeric(prob_panel["forecast_hko_daily_max_C"], errors="coerce")
    prob_panel["p_ecmwf_proxy"] = [
        event_probability_from_mu(mu, lower, upper, SIGMA_C)
        for mu, lower, upper in zip(prob_panel["forecast_hko_daily_max_C"], prob_panel["event_lower_C"], prob_panel["event_upper_C"])
    ]
    prob_panel["p_ecmwf_proxy"] = pd.to_numeric(prob_panel["p_ecmwf_proxy"], errors="coerce").clip(0.0, 1.0)
    prob_panel["p_ecmwf_hard"] = [
        event_hard_indicator_from_mu(mu, lower, upper)
        for mu, lower, upper in zip(prob_panel["forecast_hko_daily_max_C"], prob_panel["event_lower_C"], prob_panel["event_upper_C"])
    ]
    prob_panel["Y_event_int"] = pd.to_numeric(prob_panel["Y_event_int"], errors="coerce")

    p_proxy_clip = prob_panel["p_ecmwf_proxy"].clip(EPS, 1.0 - EPS)
    p_hard_clip = pd.to_numeric(prob_panel["p_ecmwf_hard"], errors="coerce").clip(EPS, 1.0 - EPS)
    y = prob_panel["Y_event_int"]
    prob_panel["brier_ecmwf_proxy"] = (prob_panel["p_ecmwf_proxy"] - y) ** 2
    prob_panel["log_score_ecmwf_proxy"] = -(y * np.log(p_proxy_clip) + (1 - y) * np.log(1 - p_proxy_clip))
    prob_panel["brier_ecmwf_hard"] = (prob_panel["p_ecmwf_hard"] - y) ** 2
    prob_panel["log_score_ecmwf_hard"] = -(y * np.log(p_hard_clip) + (1 - y) * np.log(1 - p_hard_clip))
    prob_panel["forecast_proxy_sigma_C"] = SIGMA_C
    prob_panel["forecast_source"] = "open_meteo_single_runs_ecmwf_ifs_hres_9km"
    prob_panel["forecast_source_note"] = "third_party_archived_ecmwf_ifs_point_forecast_temporary_probability_bridge"

    prob_path = dirs["processed"] / "19a_hko_ecmwf_contract_event_probability_panel.csv"
    prob_panel.to_csv(prob_path, index=False)
    print(f"Contract-event probability rows: {len(prob_panel)}")

    score_summary = summarise_scores(prob_panel)
    score_path = dirs["processed"] / "19a_hko_ecmwf_probability_score_summary.csv"
    score_summary.to_csv(score_path, index=False)

    # Issues and integrity checks.
    issues: List[pd.DataFrame] = []
    if not bound_issues.empty:
        issues.append(bound_issues)

    failed_inventory = inventory[~inventory["success"].fillna(False)].copy() if not inventory.empty and "success" in inventory.columns else pd.DataFrame()
    if not failed_inventory.empty:
        fetch_issues = failed_inventory[["run_init_utc", "model", "status_code", "error", "request_url"]].copy()
        fetch_issues.insert(0, "issue_type", "forecast_run_fetch_failed")
        issues.append(fetch_issues)

    missing_daily = daily_df[daily_df["forecast_hko_daily_max_C"].isna()].copy() if "forecast_hko_daily_max_C" in daily_df.columns else pd.DataFrame()
    if not missing_daily.empty:
        daily_issues = missing_daily[["event_date", "decision_rule", "selected_run_init_utc", "decision_cutoff_utc"]].copy()
        daily_issues.insert(0, "issue_type", "missing_daily_max_for_event_date")
        issues.append(daily_issues)

    no_lookahead_violations = request_plan[~request_plan["selected_run_before_cutoff"].astype(bool)].copy()
    if not no_lookahead_violations.empty:
        nlk = no_lookahead_violations[["event_date", "decision_rule", "decision_cutoff_utc", "selected_run_init_utc", "selected_run_available_utc_assumed"]].copy()
        nlk.insert(0, "issue_type", "forecast_run_after_decision_cutoff")
        issues.append(nlk)

    issue_df = pd.concat(issues, ignore_index=True, sort=False) if issues else pd.DataFrame(columns=["issue_type"])
    issue_path = dirs["processed"] / "19a_hko_ecmwf_forecast_issues.csv"
    issue_df.to_csv(issue_path, index=False)

    def check_row(name: str, passed: bool, detail: str) -> Dict[str, Any]:
        return {"check": name, "passed": bool(passed), "detail": detail}

    ready_prob_rows = int(prob_panel["p_ecmwf_proxy"].notna().sum()) if not prob_panel.empty else 0
    bad_probs = int(((prob_panel["p_ecmwf_proxy"] < 0) | (prob_panel["p_ecmwf_proxy"] > 1)).sum()) if not prob_panel.empty else 0
    checks = pd.DataFrame(
        [
            check_row("target_panel_nonempty", len(target_ready) > 0, f"target rows={len(target_ready)}"),
            check_row("request_plan_nonempty", len(request_plan) > 0, f"request rows={len(request_plan)}"),
            check_row("selected_runs_before_cutoff", bool(request_plan["selected_run_before_cutoff"].all()) if not request_plan.empty else False, f"violations={len(no_lookahead_violations)}"),
            check_row("fetch_inventory_nonempty", len(inventory) > 0, f"inventory rows={len(inventory)}"),
            check_row("some_runs_fetched_successfully", int(inventory.get("success", pd.Series(dtype=bool)).fillna(False).sum()) > 0 if not inventory.empty else False, f"success={int(inventory.get('success', pd.Series(dtype=bool)).fillna(False).sum()) if not inventory.empty else 0}"),
            check_row("hourly_forecast_nonempty", len(hourly_df) > 0, f"hourly rows={len(hourly_df)}"),
            check_row("daily_max_forecast_nonempty", len(daily_df.dropna(subset=["forecast_hko_daily_max_C"])) > 0 if "forecast_hko_daily_max_C" in daily_df.columns else False, f"ready daily rows={int(daily_df.get('forecast_hko_daily_max_C', pd.Series(dtype=float)).notna().sum()) if not daily_df.empty else 0}"),
            check_row("probability_panel_nonempty", len(prob_panel) > 0, f"probability rows={len(prob_panel)}"),
            check_row("probability_ready_rows_nonempty", ready_prob_rows > 0, f"ready probability rows={ready_prob_rows}"),
            check_row("probabilities_in_unit_interval", bad_probs == 0, f"bad probabilities={bad_probs}"),
            check_row("target_rows_have_binary_payoff", int(prob_panel["Y_event_int"].isna().sum()) == 0 if not prob_panel.empty else False, f"missing Y={int(prob_panel['Y_event_int'].isna().sum()) if not prob_panel.empty else 0}"),
            check_row("issue_table_written", issue_path.exists(), f"issue rows={len(issue_df)}"),
        ]
    )
    checks_path = dirs["processed"] / "19a_hko_ecmwf_forecast_integrity_checks.csv"
    checks.to_csv(checks_path, index=False)

    report_path = dirs["docs"] / "19a_hko_ecmwf_single_run_forecast_ingestion_report.md"
    write_markdown_report(
        report_path,
        target_rows=len(target_ready),
        request_plan=request_plan,
        inventory=inventory,
        hourly_df=hourly_df,
        daily_df=daily_df,
        prob_panel=prob_panel,
        score_summary=score_summary,
        checks=checks,
        issues=issue_df,
    )

    bundle_path = dirs["bundles"] / "19a_review_bundle.zip"
    files = [
        request_plan_path,
        inventory_path,
        hourly_path,
        daily_path,
        prob_path,
        score_path,
        checks_path,
        issue_path,
        report_path,
    ]
    write_bundle(bundle_path, root, files)

    print("\n19a complete.")
    print(f"Report: {report_path}")
    print(f"Review bundle: {bundle_path}")
    print("Integrity checks:")
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
