#!/usr/bin/env python3
"""
18b_hko_certified_upper_tail_outcome_and_decision_panel.py

Build a no-lookahead decision and outcome panel for the formally certified
Hong Kong upper-tail Polymarket contracts.

Inputs:
  data/processed/17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv
  data/processed/18a_hko_certified_upper_tail_market_price_panel.csv
  optional HKO target outputs from 17j, otherwise downloaded from HKO/Data.gov.hk

Outputs:
  data/raw/hko_daily_max_temperature_18b.csv
  data/processed/18b_hko_certified_upper_tail_decision_panel.csv
  data/processed/18b_hko_certified_upper_tail_scoring_ready_market_panel.csv
  data/processed/18b_hko_certified_upper_tail_outcome_status.csv
  docs/research_outputs/18b_hko_certified_upper_tail_decision_panel_report.md

Interpretation:
  This notebook/script turns 18a's historical price observations into a
  conservative no-lookahead decision panel. It does not claim executable trading
  yet. It selects the last observed YES price before pre-declared cutoffs such
  as event-day 00:00 HKT and 24 hours before that.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

HKO_MAX_TEMP_URL = (
    "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php"
    "?dataType=CLMMAXT&rformat=csv&station=HKO"
)

CERTIFIED_UNIVERSE_PATH = "data/processed/17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv"
PRICE_PANEL_PATH = "data/processed/18a_hko_certified_upper_tail_market_price_panel.csv"
HKO_TARGET_CANDIDATES = [
    "data/processed/17j_hko_daily_max_temperature_targets.csv",
    "data/processed/hko_daily_max_temperature_targets.csv",
    "data/processed/17b_hko_realised_daily_max.csv",
]
RAW_HKO_OUT = "data/raw/hko_daily_max_temperature_18b.csv"
OUT_DECISION_PANEL = "data/processed/18b_hko_certified_upper_tail_decision_panel.csv"
OUT_SCORING_READY = "data/processed/18b_hko_certified_upper_tail_scoring_ready_market_panel.csv"
OUT_OUTCOME_STATUS = "data/processed/18b_hko_certified_upper_tail_outcome_status.csv"
OUT_REPORT = "docs/research_outputs/18b_hko_certified_upper_tail_decision_panel_report.md"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "UCL-MSc-dissertation-weather-polymarket/18b academic research",
})


def find_repo_root(start: Optional[Path] = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return start


REPO = find_repo_root()
for p in [REPO / "data/raw", REPO / "data/processed", REPO / "docs/research_outputs"]:
    p.mkdir(parents=True, exist_ok=True)


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_col(columns: Iterable[str], include_terms: Iterable[str], exclude_terms: Iterable[str] = ()) -> Optional[str]:
    cols = list(columns)
    inc = [t.lower() for t in include_terms]
    exc = [t.lower() for t in exclude_terms]
    for c in cols:
        lc = str(c).lower()
        if all(t in lc for t in inc) and not any(t in lc for t in exc):
            return c
    return None


def parse_hko_csv_text(raw_text: str) -> pd.DataFrame:
    """Parse HKO daily maximum temperature CSV robustly.

    The CSV is normally bilingual and contains columns like 年/Year, 月/Month,
    日/Day and 數值/Value. The parser deliberately excludes data completeness
    columns so that it cannot repeat the earlier 17j mistake.
    """
    best: Optional[pd.DataFrame] = None
    debug: List[Tuple[int, Tuple[int, int], List[str]]] = []

    for skip in range(0, 30):
        try:
            df = pd.read_csv(StringIO(raw_text), skiprows=skip)
        except Exception:
            continue
        if df.empty or len(df.columns) < 2:
            continue
        df = normalise_columns(df)
        debug.append((skip, df.shape, list(df.columns[:8])))

        year_col = find_col(df.columns, ["year"]) or find_col(df.columns, ["年"])
        month_col = find_col(df.columns, ["month"]) or find_col(df.columns, ["月"])
        day_col = find_col(df.columns, ["day"]) or find_col(df.columns, ["日"])
        value_col = (
            find_col(df.columns, ["value"], ["complete", "completeness", "完整"])
            or find_col(df.columns, ["數值"], ["完整"])
        )

        if year_col and month_col and day_col and value_col:
            out = pd.DataFrame({
                "year": pd.to_numeric(df[year_col], errors="coerce"),
                "month": pd.to_numeric(df[month_col], errors="coerce"),
                "day": pd.to_numeric(df[day_col], errors="coerce"),
                "hko_tmax_C": pd.to_numeric(df[value_col], errors="coerce"),
            })
            out = out.dropna(subset=["year", "month", "day", "hko_tmax_C"]).copy()
            out["year"] = out["year"].astype(int)
            out["month"] = out["month"].astype(int)
            out["day"] = out["day"].astype(int)
            out["date"] = pd.to_datetime(out[["year", "month", "day"]], errors="coerce")
            out = out.dropna(subset=["date"]).copy()
            out = out[["date", "hko_tmax_C"]].sort_values("date").reset_index(drop=True)
            if not out.empty:
                best = out
                break

    if best is None or best.empty:
        msg = "Could not parse HKO daily maximum temperature CSV. Candidate headers:\n"
        msg += "\n".join(f"skip={s}, shape={sh}, cols={cols}" for s, sh, cols in debug[:20])
        raise RuntimeError(msg)

    return best


def load_or_download_hko_targets() -> Tuple[pd.DataFrame, str]:
    """Load existing HKO targets if present, otherwise download from HKO API.

    The current HKO open-data file may lag behind recent dates. The output keeps
    an explicit outcome_available flag downstream so missing realised values do
    not silently become failures.
    """
    frames: List[pd.DataFrame] = []
    sources: List[str] = []

    for rel in HKO_TARGET_CANDIDATES:
        path = REPO / rel
        if path.exists():
            try:
                df = pd.read_csv(path)
                if "date" in df.columns:
                    if "hko_tmax_C" not in df.columns:
                        possible = [c for c in df.columns if "tmax" in c.lower() or "max" in c.lower()]
                        if possible:
                            df = df.rename(columns={possible[0]: "hko_tmax_C"})
                    if "hko_tmax_C" in df.columns:
                        df = df[["date", "hko_tmax_C"]].copy()
                        df["date"] = pd.to_datetime(df["date"], errors="coerce")
                        df["hko_tmax_C"] = pd.to_numeric(df["hko_tmax_C"], errors="coerce")
                        df = df.dropna(subset=["date", "hko_tmax_C"])
                        if not df.empty:
                            frames.append(df)
                            sources.append(rel)
            except Exception:
                pass

    # Always try a fresh HKO download and combine it with existing targets.
    try:
        r = SESSION.get(HKO_MAX_TEMP_URL, timeout=45)
        r.raise_for_status()
        raw_text = r.text
        raw_path = REPO / RAW_HKO_OUT
        raw_path.write_text(raw_text, encoding="utf-8")
        fresh = parse_hko_csv_text(raw_text)
        frames.append(fresh)
        sources.append(RAW_HKO_OUT)
    except Exception as e:
        sources.append(f"fresh_download_failed:{repr(e)}")

    if not frames:
        raise SystemExit("No HKO target data available from existing files or fresh download.")

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["hko_tmax_C"] = pd.to_numeric(out["hko_tmax_C"], errors="coerce")
    out = out.dropna(subset=["date", "hko_tmax_C"])
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out, "; ".join(sources)


def hkt_midnight_utc(date_value: Any) -> pd.Timestamp:
    date = pd.to_datetime(date_value).date()
    # 00:00 HKT is 16:00 UTC on the previous date.
    return pd.Timestamp(date).tz_localize("Asia/Hong_Kong").tz_convert("UTC")


def decision_cutoffs(event_date: Any) -> Dict[str, pd.Timestamp]:
    event_start_utc = hkt_midnight_utc(event_date)
    return {
        "last_price_before_event_day_hkt": event_start_utc,
        "last_price_before_12h_prior": event_start_utc - pd.Timedelta(hours=12),
        "last_price_before_24h_prior": event_start_utc - pd.Timedelta(hours=24),
    }


def choose_last_price_before(prices: pd.DataFrame, cutoff: pd.Timestamp) -> Optional[pd.Series]:
    if prices.empty:
        return None
    eligible = prices[prices["price_timestamp_utc"] < cutoff].copy()
    if eligible.empty:
        return None
    eligible = eligible.sort_values("price_timestamp_utc")
    return eligible.iloc[-1]


def truth_value(tmax: Any, threshold: Any) -> Optional[int]:
    try:
        if pd.isna(tmax) or pd.isna(threshold):
            return None
        return int(float(tmax) >= float(threshold))
    except Exception:
        return None


def main() -> None:
    print("Repository root:", REPO)

    certified_path = REPO / CERTIFIED_UNIVERSE_PATH
    price_path = REPO / PRICE_PANEL_PATH

    if not certified_path.exists():
        raise SystemExit(f"Missing certified universe: {certified_path}")
    if not price_path.exists():
        raise SystemExit(f"Missing 18a price panel: {price_path}")

    certified = pd.read_csv(certified_path)
    prices = pd.read_csv(price_path)
    hko, hko_sources = load_or_download_hko_targets()

    print("Certified universe shape:", certified.shape)
    print("18a price panel shape:", prices.shape)
    print("HKO target shape:", hko.shape)
    if not hko.empty:
        print("HKO date range:", hko["date"].min().date(), "to", hko["date"].max().date())
    print("HKO sources:", hko_sources)

    if prices.empty:
        raise SystemExit("18a price panel is empty. Cannot build decision panel.")

    prices = prices.copy()
    prices["price_timestamp_utc"] = pd.to_datetime(prices["price_timestamp_utc"], utc=True, errors="coerce")
    prices["yes_price"] = pd.to_numeric(prices["yes_price"], errors="coerce")
    prices = prices.dropna(subset=["price_timestamp_utc", "yes_price"])
    prices = prices[prices["yes_price"].between(0, 1, inclusive="both")].copy()

    hko = hko.copy()
    hko["date"] = pd.to_datetime(hko["date"]).dt.date
    hko_map = dict(zip(hko["date"], hko["hko_tmax_C"]))

    rows: List[Dict[str, Any]] = []
    status_rows: List[Dict[str, Any]] = []

    for _, c in certified.iterrows():
        contract_id = c.get("certified_contract_id") or f"{c.get('event_slug')}__K{c.get('threshold_K')}"
        event_date = pd.to_datetime(c.get("event_date"), errors="coerce")
        if pd.isna(event_date):
            continue
        event_date_date = event_date.date()
        threshold = c.get("threshold_K")
        event_start_utc = hkt_midnight_utc(event_date)
        tmax = hko_map.get(event_date_date)
        y = truth_value(tmax, threshold)
        outcome_available = y is not None

        if "certified_contract_id" in prices.columns:
            psub = prices[prices["certified_contract_id"].astype(str) == str(contract_id)].copy()
        else:
            psub = prices[
                (prices.get("event_slug", pd.Series(index=prices.index, dtype=object)).astype(str) == str(c.get("event_slug")))
                & (pd.to_numeric(prices.get("threshold_K", pd.Series(index=prices.index)), errors="coerce") == float(threshold))
            ].copy()

        if psub.empty and "market_slug" in prices.columns:
            psub = prices[prices["market_slug"].astype(str) == str(c.get("market_slug"))].copy()

        status_rows.append({
            "event_date": event_date_date.isoformat(),
            "threshold_K": threshold,
            "certified_contract_id": contract_id,
            "event_slug": c.get("event_slug"),
            "market_slug": c.get("market_slug"),
            "market_id": c.get("market_id"),
            "hko_tmax_C": tmax,
            "Y_ge_K": y,
            "outcome_available": outcome_available,
            "price_observations_total": len(psub),
            "first_price_timestamp_utc": psub["price_timestamp_utc"].min().isoformat() if not psub.empty else None,
            "last_price_timestamp_utc": psub["price_timestamp_utc"].max().isoformat() if not psub.empty else None,
        })

        for rule, cutoff in decision_cutoffs(event_date).items():
            chosen = choose_last_price_before(psub, cutoff)
            row: Dict[str, Any] = {
                "event_date": event_date_date.isoformat(),
                "threshold_K": threshold,
                "event_slug": c.get("event_slug"),
                "market_slug": c.get("market_slug"),
                "market_id": c.get("market_id"),
                "market_question": c.get("market_question"),
                "outcome_label_text": c.get("outcome_label_text"),
                "certified_contract_id": contract_id,
                "final_certification_status": c.get("final_certification_status"),
                "certification_reason": c.get("certification_reason"),
                "event_start_hkt": pd.Timestamp(event_date_date).tz_localize("Asia/Hong_Kong").isoformat(),
                "event_start_utc": event_start_utc.isoformat(),
                "decision_rule": rule,
                "decision_cutoff_utc": cutoff.isoformat(),
                "price_observations_total": len(psub),
                "hko_tmax_C": tmax,
                "Y_ge_K": y,
                "outcome_available": outcome_available,
                "no_lookahead_valid": False,
                "decision_price_available": False,
                "decision_timestamp_utc": None,
                "yes_price": math.nan,
                "p_market": math.nan,
                "yes_token_id": None,
                "price_staleness_hours": math.nan,
                "hours_before_event_start": math.nan,
                "decision_panel_status": None,
                "trading_interpretation": "market_probability_observation_not_executable_backtest",
            }

            if chosen is None:
                row["decision_panel_status"] = "no_price_before_cutoff"
            else:
                ts = chosen["price_timestamp_utc"]
                price = float(chosen["yes_price"])
                row.update({
                    "no_lookahead_valid": bool(ts < cutoff),
                    "decision_price_available": True,
                    "decision_timestamp_utc": ts.isoformat(),
                    "yes_price": price,
                    "p_market": price,
                    "yes_token_id": chosen.get("yes_token_id"),
                    "price_staleness_hours": (cutoff - ts) / pd.Timedelta(hours=1),
                    "hours_before_event_start": (event_start_utc - ts) / pd.Timedelta(hours=1),
                    "decision_panel_status": "ok_missing_outcome" if not outcome_available else "ok_scoring_ready",
                })

            rows.append(row)

    decision = pd.DataFrame(rows)
    outcome_status = pd.DataFrame(status_rows)

    if not decision.empty:
        decision = decision.sort_values([
            "event_date", "threshold_K", "certified_contract_id", "decision_rule"
        ]).reset_index(drop=True)

    scoring_ready = decision[
        decision["no_lookahead_valid"].fillna(False)
        & decision["decision_price_available"].fillna(False)
        & decision["outcome_available"].fillna(False)
    ].copy()

    decision.to_csv(REPO / OUT_DECISION_PANEL, index=False)
    scoring_ready.to_csv(REPO / OUT_SCORING_READY, index=False)
    outcome_status.to_csv(REPO / OUT_OUTCOME_STATUS, index=False)

    report_lines: List[str] = []
    report_lines.append("# 18b Hong Kong certified upper-tail decision panel")
    report_lines.append("")
    report_lines.append(f"Run time UTC: {datetime.now(timezone.utc).isoformat()}")
    report_lines.append("")
    report_lines.append("## Inputs")
    report_lines.append(f"- Certified universe: `{CERTIFIED_UNIVERSE_PATH}`")
    report_lines.append(f"- Price panel: `{PRICE_PANEL_PATH}`")
    report_lines.append(f"- HKO sources: {hko_sources}")
    report_lines.append("")
    report_lines.append("## Outputs")
    report_lines.append(f"- Decision panel: `{OUT_DECISION_PANEL}`")
    report_lines.append(f"- Scoring-ready subset: `{OUT_SCORING_READY}`")
    report_lines.append(f"- Outcome status: `{OUT_OUTCOME_STATUS}`")
    report_lines.append("")
    report_lines.append("## Decision rules")
    report_lines.append("- `last_price_before_event_day_hkt`: last YES price before 00:00 HKT on the event date.")
    report_lines.append("- `last_price_before_12h_prior`: last YES price before 12 hours prior to event-day 00:00 HKT.")
    report_lines.append("- `last_price_before_24h_prior`: last YES price before 24 hours prior to event-day 00:00 HKT.")
    report_lines.append("")
    report_lines.append("## Counts")
    report_lines.append(f"Certified contracts: {len(certified)}")
    report_lines.append(f"Price observations: {len(prices)}")
    report_lines.append(f"Decision rows: {len(decision)}")
    report_lines.append(f"Scoring-ready rows: {len(scoring_ready)}")
    report_lines.append("")
    if not decision.empty:
        report_lines.append("Decision panel status counts:")
        report_lines.append("```text")
        report_lines.append(decision["decision_panel_status"].value_counts(dropna=False).to_string())
        report_lines.append("```")
        report_lines.append("")
        report_lines.append("Decision price availability by rule:")
        report_lines.append("```text")
        report_lines.append(decision.groupby("decision_rule")["decision_price_available"].sum().to_string())
        report_lines.append("```")
        report_lines.append("")
    if not outcome_status.empty:
        report_lines.append("Outcome availability:")
        report_lines.append("```text")
        report_lines.append(outcome_status["outcome_available"].value_counts(dropna=False).to_string())
        report_lines.append("```")
        report_lines.append("")
    report_lines.append("## Interpretation note")
    report_lines.append(
        "The decision panel is suitable for market-implied probability comparison under explicit "
        "no-lookahead timestamp rules. It is not yet a fully executable trading backtest because "
        "bid/ask availability and fill assumptions have not been audited."
    )

    (REPO / OUT_REPORT).write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\nSaved decision panel:", REPO / OUT_DECISION_PANEL)
    print("Saved scoring-ready subset:", REPO / OUT_SCORING_READY)
    print("Saved outcome status:", REPO / OUT_OUTCOME_STATUS)
    print("Saved report:", REPO / OUT_REPORT)
    print("\nDecision panel shape:", decision.shape)
    print("Scoring-ready shape:", scoring_ready.shape)
    print("Outcome status shape:", outcome_status.shape)
    if not decision.empty:
        print("\nDecision status counts:")
        print(decision["decision_panel_status"].value_counts(dropna=False))
        print("\nPrice availability by rule:")
        print(decision.groupby("decision_rule")["decision_price_available"].sum())
    if not outcome_status.empty:
        print("\nOutcome availability counts:")
        print(outcome_status["outcome_available"].value_counts(dropna=False))
        print("\nOutcome status preview:")
        print(outcome_status.to_string(index=False))


if __name__ == "__main__":
    main()
