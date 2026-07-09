from pathlib import Path
import json
import re
import time
import requests
import numpy as np
import pandas as pd

ROOT = Path.cwd()
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "polymarket_clob_price_history_18h"
REPORTS = ROOT / "docs" / "research_outputs"

RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

INPUT = PROCESSED / "18f_hko_upper_tail_threshold_contracts_20260313_20260531.csv"

OUT_DIAG = PROCESSED / "18h_clob_narrow_window_diagnostics_20260313_20260531.csv"
OUT_OBS = PROCESSED / "18h_hko_upper_tail_narrow_window_price_observations_20260313_20260531.csv"
OUT_DECISION = PROCESSED / "18h_hko_upper_tail_no_lookahead_decision_panel_20260313_20260531.csv"
OUT_SCORE = PROCESSED / "18h_hko_upper_tail_scoring_ready_market_panel_20260313_20260531.csv"
OUT_SUMMARY = PROCESSED / "18h_hko_upper_tail_market_only_score_summary_20260313_20260531.csv"
OUT_REPORT = REPORTS / "18h_clob_narrow_window_decision_price_repair_report.md"

EPS = 1e-6

def clean_token(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s.endswith(".0") and s.replace(".", "", 1).isdigit():
        s = s[:-2]
    return s

def safe_name(s):
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(s))
    return s[:180]

def parse_history(payload):
    data = payload.get("json", payload)
    hist = None

    if isinstance(data, dict):
        for k in ["history", "prices", "data"]:
            if isinstance(data.get(k), list):
                hist = data[k]
                break
    elif isinstance(data, list):
        hist = data

    if not hist:
        return pd.DataFrame(columns=["price_timestamp_utc", "p_market"])

    rows = []
    for item in hist:
        if not isinstance(item, dict):
            continue

        t = item.get("t", item.get("timestamp", item.get("time", item.get("ts"))))
        p = item.get("p", item.get("price", item.get("value")))

        ts = pd.to_datetime(t, unit="s", utc=True, errors="coerce")
        if pd.isna(ts):
            ts = pd.to_datetime(t, unit="ms", utc=True, errors="coerce")
        if pd.isna(ts):
            ts = pd.to_datetime(t, utc=True, errors="coerce")

        price = pd.to_numeric(p, errors="coerce")

        if pd.notna(ts) and pd.notna(price):
            rows.append({
                "price_timestamp_utc": ts,
                "p_market": float(price),
            })

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["price_timestamp_utc", "p_market"])

    return out.drop_duplicates(["price_timestamp_utc", "p_market"]).sort_values("price_timestamp_utc").reset_index(drop=True)

def event_midnight_hkt(event_date):
    return pd.Timestamp(pd.to_datetime(event_date).date()).tz_localize("Asia/Hong_Kong")

def unix_seconds(ts):
    return int(pd.Timestamp(ts).timestamp())

def request_price_window(token_id, event_slug, threshold_K, decision_rule, cutoff_utc, lookback_hours, interval, fidelity):
    start_utc = cutoff_utc - pd.Timedelta(hours=lookback_hours)

    params = {
        "market": str(token_id),
        "interval": interval,
        "fidelity": fidelity,
        "startTs": unix_seconds(start_utc),
        "endTs": unix_seconds(cutoff_utc),
    }

    raw_name = safe_name(
        f"{event_slug}__K{threshold_K}__{str(token_id)[:24]}__{decision_rule}__lb{lookback_hours}h__{interval}__fid{fidelity}.json"
    )
    raw_path = RAW / raw_name

    try:
        r = requests.get(
            "https://clob.polymarket.com/prices-history",
            params=params,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        text = r.text
        try:
            j = r.json()
        except Exception:
            j = None

        payload = {
            "request_url": r.url,
            "status_code": r.status_code,
            "params": params,
            "text_preview": text[:1000],
            "json": j,
        }
        raw_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        hist = parse_history(payload)

        diag = {
            "event_slug": event_slug,
            "threshold_K": threshold_K,
            "yes_token_id": str(token_id),
            "decision_rule": decision_rule,
            "cutoff_utc": cutoff_utc,
            "lookback_hours": lookback_hours,
            "interval": interval,
            "fidelity": fidelity,
            "status_code": r.status_code,
            "history_rows": len(hist),
            "raw_path": str(raw_path.relative_to(ROOT)),
            "request_url": r.url,
            "text_preview": text[:300],
        }

        return hist, diag

    except Exception as e:
        payload = {
            "error": str(e),
            "params": params,
        }
        raw_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        diag = {
            "event_slug": event_slug,
            "threshold_K": threshold_K,
            "yes_token_id": str(token_id),
            "decision_rule": decision_rule,
            "cutoff_utc": cutoff_utc,
            "lookback_hours": lookback_hours,
            "interval": interval,
            "fidelity": fidelity,
            "status_code": "exception",
            "history_rows": 0,
            "raw_path": str(raw_path.relative_to(ROOT)),
            "request_url": "",
            "text_preview": str(e)[:300],
        }
        return pd.DataFrame(columns=["price_timestamp_utc", "p_market"]), diag

def score_decisions(decision):
    if decision.empty:
        empty_summary = pd.DataFrame(columns=[
            "decision_rule", "empirical_role", "n", "mean_brier",
            "mean_log_score", "mean_p_market", "outcome_rate"
        ])
        return decision.copy(), empty_summary

    out = decision.copy()
    out["p_market"] = pd.to_numeric(out["p_market"], errors="coerce")
    out["Y_ge_K"] = pd.to_numeric(out["Y_ge_K"], errors="coerce")
    out = out.dropna(subset=["p_market", "Y_ge_K"]).copy()

    out["p_market"] = out["p_market"].clip(0, 1)
    out["p_clipped"] = out["p_market"].clip(EPS, 1 - EPS)
    out["brier_market"] = (out["p_market"] - out["Y_ge_K"]) ** 2
    out["log_score_market"] = -(
        out["Y_ge_K"] * np.log(out["p_clipped"])
        + (1 - out["Y_ge_K"]) * np.log(1 - out["p_clipped"])
    )

    if out.empty:
        summary = pd.DataFrame(columns=[
            "decision_rule", "empirical_role", "n", "mean_brier",
            "mean_log_score", "mean_p_market", "outcome_rate"
        ])
    else:
        summary = (
            out.groupby(["decision_rule", "empirical_role"], dropna=False)
            .agg(
                n=("brier_market", "size"),
                mean_brier=("brier_market", "mean"),
                mean_log_score=("log_score_market", "mean"),
                mean_p_market=("p_market", "mean"),
                outcome_rate=("Y_ge_K", "mean"),
            )
            .reset_index()
        )

    return out, summary

if not INPUT.exists():
    raise SystemExit(f"Missing input file: {INPUT}")

up = pd.read_csv(INPUT, dtype=str)
print("Input upper-tail panel:", up.shape)

required = ["event_date", "threshold_K", "market_slug", "yes_token_id", "hko_tmax_C", "Y_ge_K"]
missing = [c for c in required if c not in up.columns]
if missing:
    raise SystemExit(f"Missing required columns: {missing}")

up["yes_token_id"] = up["yes_token_id"].map(clean_token)
up["threshold_K"] = pd.to_numeric(up["threshold_K"], errors="coerce")
up["hko_tmax_C"] = pd.to_numeric(up["hko_tmax_C"], errors="coerce")
up["Y_ge_K"] = pd.to_numeric(up["Y_ge_K"], errors="coerce")

up = up[
    up["yes_token_id"].astype(str).str.len().gt(20)
    & up["threshold_K"].notna()
    & up["hko_tmax_C"].notna()
    & up["Y_ge_K"].notna()
].copy()

if "empirical_role" not in up.columns:
    up["empirical_role"] = "upper_tail_threshold_candidate"

up = up.drop_duplicates(["event_date", "threshold_K", "market_slug", "yes_token_id"]).reset_index(drop=True)

print("Contracts available for narrow-window repair:", up.shape)
print(up[["event_date", "threshold_K", "market_slug", "yes_token_id", "hko_tmax_C", "Y_ge_K", "empirical_role"]].head(20).to_string(index=False))

decision_rules = {
    "last_price_before_event_day_hkt": 0,
    "last_price_before_24h_prior": 24,
    "last_price_before_12h_prior": 12,
    "last_price_before_6h_prior": 6,
}

lookback_hours_grid = [3, 12, 24]
query_grid = [
    ("1m", 60),
    ("1h", 60),
    ("6h", 60),
]

diagnostics = []
observations = []
decisions = []

for i, row in up.iterrows():
    event_date = pd.to_datetime(row["event_date"]).date()
    midnight = event_midnight_hkt(event_date)
    event_slug = row.get("event_slug", row.get("market_slug", ""))

    print(f"\n[{i+1}/{len(up)}] {event_date} K={row['threshold_K']} {row['market_slug']}")

    for decision_rule, hours_before_midnight in decision_rules.items():
        cutoff_utc = (midnight - pd.Timedelta(hours=hours_before_midnight)).tz_convert("UTC")

        found_decision = None

        for lookback_hours in lookback_hours_grid:
            if found_decision is not None:
                break

            for interval, fidelity in query_grid:
                hist, diag = request_price_window(
                    token_id=row["yes_token_id"],
                    event_slug=event_slug,
                    threshold_K=row["threshold_K"],
                    decision_rule=decision_rule,
                    cutoff_utc=cutoff_utc,
                    lookback_hours=lookback_hours,
                    interval=interval,
                    fidelity=fidelity,
                )
                diagnostics.append(diag)

                if not hist.empty:
                    hist = hist.copy()
                    hist["price_timestamp_utc"] = pd.to_datetime(hist["price_timestamp_utc"], utc=True, errors="coerce")
                    hist = hist.dropna(subset=["price_timestamp_utc", "p_market"])
                    eligible = hist[hist["price_timestamp_utc"] <= cutoff_utc].copy()

                    for c in [
                        "event_date", "threshold_K", "event_slug", "market_slug",
                        "market_id", "market_question", "outcome_label_text",
                        "yes_token_id", "hko_tmax_C", "Y_ge_K", "empirical_role"
                    ]:
                        if c in row.index:
                            hist[c] = row[c]

                    hist["decision_rule_probe"] = decision_rule
                    hist["lookback_hours"] = lookback_hours
                    hist["interval"] = interval
                    hist["fidelity"] = fidelity
                    hist["raw_path"] = diag["raw_path"]
                    observations.append(hist)

                    if not eligible.empty:
                        last = eligible.sort_values("price_timestamp_utc").iloc[-1].to_dict()

                        decision = row.to_dict()
                        decision.update({
                            "decision_rule": decision_rule,
                            "decision_cutoff_utc": cutoff_utc,
                            "decision_timestamp_utc": last["price_timestamp_utc"],
                            "p_market": float(last["p_market"]),
                            "price_staleness_hours": (cutoff_utc - last["price_timestamp_utc"]).total_seconds() / 3600,
                            "price_query_lookback_hours": lookback_hours,
                            "price_query_interval": interval,
                            "price_query_fidelity": fidelity,
                            "price_query_raw_path": diag["raw_path"],
                        })

                        found_decision = decision
                        decisions.append(decision)
                        print(f"  {decision_rule}: recovered p={decision['p_market']:.6f}, stale={decision['price_staleness_hours']:.2f}h")
                        break

                time.sleep(0.12)

        if found_decision is None:
            print(f"  {decision_rule}: no price recovered")

diag_df = pd.DataFrame(diagnostics)
obs_df = pd.concat(observations, ignore_index=True) if observations else pd.DataFrame()
decision_df = pd.DataFrame(decisions)

diag_df.to_csv(OUT_DIAG, index=False)
obs_df.to_csv(OUT_OBS, index=False)
decision_df.to_csv(OUT_DECISION, index=False)

score_df, summary_df = score_decisions(decision_df)
score_df.to_csv(OUT_SCORE, index=False)
summary_df.to_csv(OUT_SUMMARY, index=False)

print("\n=== 18h outputs ===")
print("Diagnostics:", diag_df.shape, OUT_DIAG)
print("Price observations:", obs_df.shape, OUT_OBS)
print("Decision panel:", decision_df.shape, OUT_DECISION)
print("Scoring-ready panel:", score_df.shape, OUT_SCORE)
print("Score summary:", summary_df.shape, OUT_SUMMARY)

print("\n=== Diagnostics status counts ===")
if not diag_df.empty:
    print(
        diag_df.groupby(["status_code", "interval", "lookback_hours"], dropna=False)["history_rows"]
        .agg(["count", "max", "sum"])
        .reset_index()
        .to_string(index=False)
    )

print("\n=== Best endpoint attempts ===")
if not diag_df.empty:
    best = diag_df.sort_values("history_rows", ascending=False).head(40)
    cols = [
        "event_slug", "threshold_K", "decision_rule", "status_code",
        "lookback_hours", "interval", "fidelity", "history_rows", "text_preview"
    ]
    cols = [c for c in cols if c in best.columns]
    print(best[cols].to_string(index=False))

print("\n=== Market-only score summary ===")
print(summary_df.to_string(index=False))

report = []
report.append("# 18h CLOB narrow-window decision-price repair\n")
report.append(f"Input contracts: `{len(up)}`\n")
report.append(f"Diagnostic endpoint attempts: `{len(diag_df)}`\n")
report.append(f"Recovered price observation rows: `{len(obs_df)}`\n")
report.append(f"No-lookahead decision rows: `{len(decision_df)}`\n")
report.append(f"Scoring-ready rows: `{len(score_df)}`\n")

report.append("\n## Endpoint diagnostic summary\n")
if len(diag_df):
    s = (
        diag_df.groupby(["status_code", "interval", "lookback_hours"], dropna=False)["history_rows"]
        .agg(["count", "max", "sum"])
        .reset_index()
    )
    report.append(s.to_markdown(index=False))
else:
    report.append("_No diagnostics produced._")

report.append("\n\n## Market-only score summary\n")
if len(summary_df):
    report.append(summary_df.to_markdown(index=False))
else:
    report.append("_No scoreable rows._")

report.append("\n\n## Interpretation\n")
if len(score_df):
    report.append("The narrow-window repair recovered historical CLOB observations around no-lookahead decision times and produced a market-only scoring panel.")
elif len(obs_df):
    report.append("The narrow-window repair recovered some CLOB observations, but no observations were available before the no-lookahead cutoffs.")
else:
    report.append("The narrow-window repair recovered no historical CLOB observations. Together with the previous long-window diagnostic, this suggests that the public CLOB price-history endpoint may not expose historical observations for these resolved Hong Kong weather contracts, or that the asset mapping requires an alternative Polymarket data source.")

OUT_REPORT.write_text("\n".join(report), encoding="utf-8")
print("\nSaved report:", OUT_REPORT)
