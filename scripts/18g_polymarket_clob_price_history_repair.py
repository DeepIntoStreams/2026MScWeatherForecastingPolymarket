from pathlib import Path
import json
import re
import time
import requests
import numpy as np
import pandas as pd

ROOT = Path.cwd()
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "polymarket_clob_price_history_18g"
REPORTS = ROOT / "docs" / "research_outputs"

RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

INPUT = PROCESSED / "18f_hko_upper_tail_threshold_contracts_20260313_20260531.csv"

OUT_DIAGNOSTICS = PROCESSED / "18g_clob_price_history_diagnostics_20260313_20260531.csv"
OUT_PRICE = PROCESSED / "18g_hko_upper_tail_price_history_panel_20260313_20260531.csv"
OUT_DECISION = PROCESSED / "18g_hko_upper_tail_no_lookahead_decision_panel_20260313_20260531.csv"
OUT_SCORE = PROCESSED / "18g_hko_upper_tail_scoring_ready_market_panel_20260313_20260531.csv"
OUT_SUMMARY = PROCESSED / "18g_hko_upper_tail_market_only_score_summary_20260313_20260531.csv"
OUT_REPORT = REPORTS / "18g_polymarket_clob_price_history_repair_report.md"

EPS = 1e-6

def clean_token(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s.endswith(".0") and s.replace(".", "", 1).isdigit():
        s = s[:-2]
    return s

def safe_name(*parts):
    s = "__".join(str(p) for p in parts if p is not None)
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
    return s[:180]

def event_midnight_hkt(event_date):
    return pd.Timestamp(event_date).tz_localize("Asia/Hong_Kong")

def unix_seconds(ts):
    return int(pd.Timestamp(ts).timestamp())

def parse_history(wrapper):
    data = wrapper.get("json", wrapper)
    hist = None

    if isinstance(data, dict):
        for key in ["history", "prices", "data"]:
            if isinstance(data.get(key), list):
                hist = data[key]
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

    out = out.drop_duplicates(["price_timestamp_utc", "p_market"])
    out = out.sort_values("price_timestamp_utc").reset_index(drop=True)
    return out

def query_prices_history(token_id, event_slug, threshold_K, event_date):
    base = "https://clob.polymarket.com/prices-history"

    token_id = clean_token(token_id)
    event_date = pd.to_datetime(event_date).date()

    midnight = event_midnight_hkt(event_date)
    windows = [
        ("no_window", None, None),
        ("event_minus_60d_to_plus_2d", midnight - pd.Timedelta(days=60), midnight + pd.Timedelta(days=2)),
        ("event_minus_30d_to_plus_2d", midnight - pd.Timedelta(days=30), midnight + pd.Timedelta(days=2)),
        ("event_minus_14d_to_plus_2d", midnight - pd.Timedelta(days=14), midnight + pd.Timedelta(days=2)),
        ("march1_to_june1", pd.Timestamp("2026-03-01", tz="Asia/Hong_Kong"), pd.Timestamp("2026-06-01", tz="Asia/Hong_Kong")),
    ]

    intervals = [
        ("all", 60),
        ("max", 60),
        ("1d", 60),
        ("6h", 60),
        ("1h", 60),
        ("1m", 60),
        ("1m", 1),
    ]

    diagnostics = []
    best = pd.DataFrame()
    best_wrapper = None
    best_raw_path = None

    for window_name, start, end in windows:
        for interval, fidelity in intervals:
            params = {
                "market": token_id,
                "interval": interval,
                "fidelity": fidelity,
            }
            if start is not None:
                params["startTs"] = unix_seconds(start.tz_convert("UTC"))
            if end is not None:
                params["endTs"] = unix_seconds(end.tz_convert("UTC"))

            raw_path = RAW / f"{safe_name(event_slug, 'K' + str(threshold_K), token_id[:24], window_name, interval, fidelity)}.json"

            try:
                r = requests.get(base, params=params, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                text = r.text
                try:
                    j = r.json()
                except Exception:
                    j = None

                wrapper = {
                    "request_url": r.url,
                    "status_code": r.status_code,
                    "params": params,
                    "text_preview": text[:1000],
                    "json": j,
                }
                raw_path.write_text(json.dumps(wrapper, ensure_ascii=False), encoding="utf-8")

                hist = parse_history(wrapper)

                diagnostics.append({
                    "event_date": event_date,
                    "event_slug": event_slug,
                    "threshold_K": threshold_K,
                    "yes_token_id": token_id,
                    "window_name": window_name,
                    "interval": interval,
                    "fidelity": fidelity,
                    "status_code": r.status_code,
                    "history_rows": len(hist),
                    "raw_path": str(raw_path.relative_to(ROOT)),
                    "request_url": r.url,
                    "text_preview": text[:250],
                })

                if len(hist) > len(best):
                    best = hist.copy()
                    best_wrapper = wrapper
                    best_raw_path = raw_path

                if len(hist) > 0:
                    return best, diagnostics, best_wrapper, best_raw_path

            except Exception as e:
                wrapper = {
                    "error": str(e),
                    "params": params,
                }
                raw_path.write_text(json.dumps(wrapper, ensure_ascii=False), encoding="utf-8")
                diagnostics.append({
                    "event_date": event_date,
                    "event_slug": event_slug,
                    "threshold_K": threshold_K,
                    "yes_token_id": token_id,
                    "window_name": window_name,
                    "interval": interval,
                    "fidelity": fidelity,
                    "status_code": "exception",
                    "history_rows": 0,
                    "raw_path": str(raw_path.relative_to(ROOT)),
                    "request_url": "",
                    "text_preview": str(e)[:250],
                })

            time.sleep(0.15)

    return best, diagnostics, best_wrapper, best_raw_path

def make_decision_panel(price_panel):
    if price_panel.empty:
        return pd.DataFrame()

    rows = []
    keys = [
        "event_date",
        "threshold_K",
        "event_slug",
        "market_slug",
        "yes_token_id",
    ]

    for key, g in price_panel.groupby(keys, dropna=False):
        event_date = pd.to_datetime(key[0]).date()
        midnight = event_midnight_hkt(event_date)

        cutoffs = {
            "last_price_before_event_day_hkt": midnight.tz_convert("UTC"),
            "last_price_before_24h_prior": (midnight - pd.Timedelta(hours=24)).tz_convert("UTC"),
            "last_price_before_12h_prior": (midnight - pd.Timedelta(hours=12)).tz_convert("UTC"),
            "last_price_before_6h_prior": (midnight - pd.Timedelta(hours=6)).tz_convert("UTC"),
        }

        g = g.sort_values("price_timestamp_utc").copy()
        g["price_timestamp_utc"] = pd.to_datetime(g["price_timestamp_utc"], utc=True, errors="coerce")
        g = g.dropna(subset=["price_timestamp_utc", "p_market"])

        for rule, cutoff in cutoffs.items():
            eligible = g[g["price_timestamp_utc"] <= cutoff]
            if eligible.empty:
                continue

            last = eligible.iloc[-1].to_dict()
            last["decision_rule"] = rule
            last["decision_cutoff_utc"] = cutoff
            last["decision_timestamp_utc"] = last["price_timestamp_utc"]
            last["price_staleness_hours"] = (cutoff - last["price_timestamp_utc"]).total_seconds() / 3600
            rows.append(last)

    return pd.DataFrame(rows)

def score_decisions(decision):
    if decision.empty:
        return pd.DataFrame(), pd.DataFrame(columns=[
            "decision_rule",
            "empirical_role",
            "n",
            "mean_brier",
            "mean_log_score",
            "mean_p_market",
            "outcome_rate",
        ])

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
            "decision_rule",
            "empirical_role",
            "n",
            "mean_brier",
            "mean_log_score",
            "mean_p_market",
            "outcome_rate",
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

up = pd.read_csv(INPUT)
print("Input upper-tail panel:", up.shape)
print("Columns:", list(up.columns))

required = ["event_date", "threshold_K", "market_slug", "yes_token_id", "hko_tmax_C", "Y_ge_K"]
missing = [c for c in required if c not in up.columns]
if missing:
    raise SystemExit(f"Missing required columns from 18f upper-tail panel: {missing}")

up["yes_token_id"] = up["yes_token_id"].map(clean_token)
up = up[up["yes_token_id"].notna() & up["yes_token_id"].astype(str).str.len().gt(10)].copy()
up = up.drop_duplicates(["event_date", "threshold_K", "market_slug", "yes_token_id"]).reset_index(drop=True)

print("Unique upper-tail contracts with YES token:", up.shape)
if "empirical_role" in up.columns:
    print("Empirical role counts:")
    print(up["empirical_role"].value_counts(dropna=False))

all_diag = []
all_price = []

for i, row in up.iterrows():
    print(f"\n[{i+1}/{len(up)}] {row['event_date']} K={row['threshold_K']} {row['market_slug']}")
    hist, diag, wrapper, raw_path = query_prices_history(
        token_id=row["yes_token_id"],
        event_slug=row.get("event_slug", row.get("market_slug", "")),
        threshold_K=row["threshold_K"],
        event_date=row["event_date"],
    )

    all_diag.extend(diag)

    if hist.empty:
        print("  no history recovered")
        continue

    print("  history rows:", len(hist), "first:", hist["price_timestamp_utc"].min(), "last:", hist["price_timestamp_utc"].max())

    for c in [
        "event_date",
        "threshold_K",
        "event_slug",
        "market_slug",
        "market_id",
        "market_question",
        "outcome_label_text",
        "yes_token_id",
        "hko_tmax_C",
        "Y_ge_K",
        "empirical_role",
    ]:
        if c in row.index:
            hist[c] = row[c]

    hist["successful_raw_path"] = str(raw_path.relative_to(ROOT)) if raw_path else ""
    all_price.append(hist)

diag_df = pd.DataFrame(all_diag)
diag_df.to_csv(OUT_DIAGNOSTICS, index=False)

price_panel = pd.concat(all_price, ignore_index=True) if all_price else pd.DataFrame()
price_panel.to_csv(OUT_PRICE, index=False)

decision = make_decision_panel(price_panel)
decision.to_csv(OUT_DECISION, index=False)

score, summary = score_decisions(decision)
score.to_csv(OUT_SCORE, index=False)
summary.to_csv(OUT_SUMMARY, index=False)

print("\n=== 18g outputs ===")
print("Diagnostics:", diag_df.shape, OUT_DIAGNOSTICS)
print("Price panel:", price_panel.shape, OUT_PRICE)
print("Decision panel:", decision.shape, OUT_DECISION)
print("Scoring-ready panel:", score.shape, OUT_SCORE)
print("Score summary:", summary.shape, OUT_SUMMARY)

print("\n=== Diagnostics status counts ===")
if not diag_df.empty:
    print(diag_df.groupby(["status_code", "interval"], dropna=False)["history_rows"].agg(["count", "max", "sum"]).reset_index().to_string(index=False))
    print("\nBest diagnostics by contract:")
    best = diag_df.sort_values("history_rows", ascending=False).groupby(["event_date", "threshold_K", "market_slug"], dropna=False).head(1)
    show = [c for c in ["event_date", "threshold_K", "market_slug", "yes_token_id", "status_code", "window_name", "interval", "fidelity", "history_rows", "text_preview"] if c in best.columns]
    print(best[show].head(80).to_string(index=False))

print("\n=== Score summary ===")
print(summary.to_string(index=False))

report = []
report.append("# 18g Polymarket CLOB price-history repair\n")
report.append(f"Input upper-tail contracts with YES token: `{len(up)}`\n")
report.append(f"Diagnostic query rows: `{len(diag_df)}`\n")
report.append(f"Recovered price-history rows: `{len(price_panel)}`\n")
report.append(f"No-lookahead decision rows: `{len(decision)}`\n")
report.append(f"Scoring-ready rows: `{len(score)}`\n")

report.append("\n## Endpoint diagnostic summary\n")
if not diag_df.empty:
    endpoint_summary = (
        diag_df.groupby(["status_code", "interval"], dropna=False)["history_rows"]
        .agg(["count", "max", "sum"])
        .reset_index()
    )
    report.append(endpoint_summary.to_markdown(index=False))
else:
    report.append("_No diagnostics produced._")

report.append("\n\n## Market-only score summary\n")
if len(summary):
    report.append(summary.to_markdown(index=False))
else:
    report.append("_No scoreable rows._")

report.append("\n\n## Interpretation\n")
if len(score):
    report.append("The CLOB price-history repair recovered historical market prices and produced a no-lookahead market-only scoring panel.")
elif len(price_panel):
    report.append("The repair recovered price-history observations, but none passed the no-lookahead decision cutoffs. Further work should inspect timestamp ranges.")
else:
    report.append("No CLOB price-history observations were recovered for the 18f certified upper-tail token IDs across the tested endpoint variants. This suggests either an endpoint availability limitation for these resolved weather markets or an unresolved asset-id mapping problem. The certified contract-outcome panel remains valid, but historical trading/scoring requires another price source or manual historical-price reconstruction.")

OUT_REPORT.write_text("\n".join(report), encoding="utf-8")
print("\nSaved report:", OUT_REPORT)
