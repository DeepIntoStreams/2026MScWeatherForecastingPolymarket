#!/usr/bin/env python3
"""
18j Gamma metadata settlement-family audit.

Classifies Hong Kong Polymarket temperature contracts into HKO Daily Extract
one-decimal, Wunderground / airport, ambiguous, or other settlement families.
It writes CSV outputs, a markdown report, and a zip bundle for upload/inspection.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import time
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent

RAW_DIR = ROOT / "data" / "raw" / "polymarket_gamma_18j"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"
BUNDLES = ROOT / "data" / "review_bundles"
for d in [RAW_DIR, PROCESSED, REPORTS, BUNDLES]:
    d.mkdir(parents=True, exist_ok=True)

GAMMA_BASE = "https://gamma-api.polymarket.com"

OUT_AUDIT = PROCESSED / "18j_gamma_metadata_settlement_family_audit.csv"
OUT_UNIVERSE = PROCESSED / "18j_full_hko_contract_event_universe_preliminary.csv"
OUT_EXCLUDED = PROCESSED / "18j_excluded_or_ambiguous_hk_contracts.csv"
OUT_FAMILY_SUMMARY = PROCESSED / "18j_settlement_family_summary.csv"
OUT_EVENT_TYPE_SUMMARY = PROCESSED / "18j_contract_event_type_summary.csv"
OUT_MARCH13 = PROCESSED / "18j_march13_settlement_family_audit.csv"
OUT_REPORT = REPORTS / "18j_gamma_metadata_settlement_family_audit_report.md"
OUT_BUNDLE = BUNDLES / "18j_review_bundle.zip"

PREFERRED_INPUTS = [
    "data/processed/18f_polymarket_event_sweep_20260313_20260531.csv",
    "data/processed/18f_polymarket_child_markets_20260313_20260531.csv",
    "data/processed/18f_hko_polymarket_floor_validation_panel_20260313_20260531.csv",
    "data/processed/18f_hko_upper_tail_threshold_contracts_20260313_20260531.csv",
    "data/processed/18h_hko_upper_tail_no_lookahead_decision_panel_20260313_20260531.csv",
    "data/processed/18h_hko_upper_tail_scoring_ready_market_panel_20260313_20260531.csv",
    "data/processed/18i_hko_main_scoring_panel_formally_certified.csv",
]

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
}


def normalise(x: Any) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    if isinstance(x, (dict, list)):
        return json.dumps(x, ensure_ascii=False, sort_keys=True)
    s = str(x).strip()
    return "" if s.lower() in {"", "nan", "none", "null"} else s


def first_present(row: pd.Series, cols: Iterable[str]) -> str:
    for c in cols:
        if c in row.index:
            v = normalise(row.get(c))
            if v:
                return v
    return ""


def read_input(path: str) -> pd.DataFrame:
    p = ROOT / path
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p, dtype=str)
        df["source_file"] = path
        return df
    except Exception as e:
        print(f"[WARN] Could not read {path}: {e}")
        return pd.DataFrame()


def extract_event_slug(slug: str) -> str:
    s = normalise(slug)
    m = re.search(r"(highest-temperature-in-hong-kong-on-[a-z]+-\d{1,2}-\d{4})", s)
    return m.group(1) if m else s


def extract_date(*vals: str) -> str:
    text = " ".join(normalise(v) for v in vals).lower()
    iso = re.search(r"(20\d{2})[-_/](\d{1,2})[-_/](\d{1,2})", text)
    if iso:
        y, m, d = iso.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    m = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december)[-\s_]+(\d{1,2})[-\s_,]+(20\d{2})",
        text,
    )
    if m:
        mon, day, year = m.groups()
        return f"{int(year):04d}-{int(MONTHS[mon]):02d}-{int(day):02d}"
    return ""


def cache_name(prefix: str, endpoint: str, params: Dict[str, Any]) -> Path:
    payload = json.dumps({"endpoint": endpoint, "params": params}, sort_keys=True)
    h = hashlib.sha256(payload.encode()).hexdigest()[:16]
    safe = re.sub(r"[^A-Za-z0-9_.=-]+", "_", prefix)[:150]
    return RAW_DIR / f"{safe}_{h}.json"


def gamma_get(endpoint: str, params: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    p = cache_name(prefix, endpoint, params)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    result = {
        "url": f"{GAMMA_BASE}{endpoint}",
        "params": params,
        "status_code": None,
        "json": None,
        "text_preview": "",
        "error": "",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        r = requests.get(result["url"], params=params, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        result["status_code"] = r.status_code
        result["text_preview"] = r.text[:1500]
        try:
            result["json"] = r.json()
        except Exception:
            result["json"] = None
    except Exception as e:
        result["error"] = str(e)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(0.12)
    return result


def unwrap_items(obj: Any) -> List[Dict[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ["data", "events", "markets", "items", "results"]:
            val = obj.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        return [obj]
    return []


def local_record(row: pd.Series) -> Dict[str, Any]:
    market_slug = first_present(row, ["market_slug", "slug", "condition_slug", "question_slug"])
    event_slug = first_present(row, ["event_slug", "parent_event_slug", "eventSlug"])
    if not event_slug:
        event_slug = extract_event_slug(market_slug)
    event_date = first_present(row, ["event_date", "date", "local_date", "d"])
    if not event_date:
        event_date = extract_date(event_slug, market_slug)
    yes_token = first_present(row, ["yes_token_id", "clob_token_id", "token_id", "asset_id"])
    clob_ids = first_present(row, ["clobTokenIds", "clob_token_ids"]) or yes_token
    return {
        "record_source": f"local:{first_present(row, ['source_file'])}",
        "event_id": first_present(row, ["event_id", "eventId"]),
        "event_slug": event_slug,
        "event_title": first_present(row, ["event_title", "title"]),
        "event_date": event_date,
        "event_description": first_present(row, ["event_description"]),
        "event_rules": first_present(row, ["event_rules", "rules_text", "rule_text", "rules"]),
        "event_resolution_source": first_present(row, ["event_resolution_source", "resolutionSource"]),
        "market_id": first_present(row, ["market_id", "condition_id", "conditionId", "id"]),
        "market_slug": market_slug,
        "market_question": first_present(row, ["market_question", "question", "market_title"]),
        "market_title": first_present(row, ["market_title", "outcome_label_text", "outcome_label", "title"]),
        "market_description": first_present(row, ["market_description", "description"]),
        "market_rules": first_present(row, ["market_rules", "rules", "rules_text", "rule_text"]),
        "market_resolution_source": first_present(row, ["market_resolution_source", "resolutionSource"]),
        "group_item_title": first_present(row, ["groupItemTitle", "group_item_title", "outcome_label_text", "outcome_label"]),
        "group_item_threshold": first_present(row, ["groupItemThreshold", "group_item_threshold", "threshold_K", "K"]),
        "group_item_range": first_present(row, ["groupItemRange", "group_item_range"]),
        "lower_bound": first_present(row, ["lowerBound", "lower_bound"]),
        "upper_bound": first_present(row, ["upperBound", "upper_bound"]),
        "outcomes": first_present(row, ["outcomes", "outcome_label_text", "outcome_label"]),
        "clob_token_ids": clob_ids,
        "tokens": "",
        "hko_tmax_C": first_present(row, ["hko_tmax_C", "T_HKO", "tmax_C"]),
        "Y_ge_K": first_present(row, ["Y_ge_K", "Y_event", "outcome"]),
    }


def flatten_market(m: Dict[str, Any], source: str, parent_only: bool = False) -> Dict[str, Any]:
    r: Dict[str, Any] = {} if parent_only else {
        "record_source": source,
        "event_id": normalise(m.get("eventId") or m.get("event_id")),
        "event_slug": normalise(m.get("eventSlug") or m.get("event_slug")),
        "event_title": normalise(m.get("eventTitle") or m.get("event_title")),
        "event_date": extract_date(normalise(m.get("eventSlug") or m.get("event_slug")), normalise(m.get("slug")), normalise(m.get("question"))),
    }
    r.update({
        "market_id": normalise(m.get("id")),
        "market_slug": normalise(m.get("slug")),
        "market_question": normalise(m.get("question")),
        "market_title": normalise(m.get("title")),
        "market_description": normalise(m.get("description")),
        "market_rules": normalise(m.get("rules")),
        "market_resolution_source": normalise(m.get("resolutionSource")),
        "group_item_title": normalise(m.get("groupItemTitle")),
        "group_item_threshold": normalise(m.get("groupItemThreshold")),
        "group_item_range": normalise(m.get("groupItemRange")),
        "lower_bound": normalise(m.get("lowerBound")),
        "upper_bound": normalise(m.get("upperBound")),
        "outcomes": normalise(m.get("outcomes")),
        "clob_token_ids": normalise(m.get("clobTokenIds")),
        "tokens": normalise(m.get("tokens")),
        "market_raw": normalise(m),
    })
    return r


def flatten_event(e: Dict[str, Any], source: str) -> List[Dict[str, Any]]:
    event_slug = normalise(e.get("slug") or e.get("eventSlug"))
    event_title = normalise(e.get("title") or e.get("question") or e.get("name"))
    base = {
        "record_source": source,
        "event_id": normalise(e.get("id") or e.get("eventId")),
        "event_slug": event_slug,
        "event_title": event_title,
        "event_date": extract_date(event_slug, event_title, normalise(e)),
        "event_description": normalise(e.get("description")),
        "event_rules": normalise(e.get("rules")),
        "event_resolution_source": normalise(e.get("resolutionSource")),
        "api_event_raw": normalise(e),
    }
    markets: List[Dict[str, Any]] = []
    for key in ["markets", "market", "childMarkets"]:
        val = e.get(key)
        if isinstance(val, list):
            markets.extend([x for x in val if isinstance(x, dict)])
        elif isinstance(val, dict):
            markets.append(val)
    if not markets:
        return [base]
    rows = []
    for m in markets:
        r = dict(base)
        r.update(flatten_market(m, source, parent_only=True))
        rows.append(r)
    return rows


def evidence_text(row: pd.Series) -> str:
    cols = [
        "event_slug", "event_title", "event_description", "event_rules", "event_resolution_source",
        "market_slug", "market_question", "market_title", "market_description", "market_rules",
        "market_resolution_source", "group_item_title", "group_item_threshold", "group_item_range",
        "lower_bound", "upper_bound", "outcomes", "api_event_raw", "market_raw",
    ]
    return " || ".join(normalise(row.get(c)) for c in cols if c in row.index and normalise(row.get(c)))


def classify_family(text: str) -> Tuple[str, str, int, int]:
    t = f" {text.lower()} "
    hko_terms = [
        "hong kong observatory", "(hko)", " hko ", "daily extract", "absolute daily max",
        "absolute daily maximum", "absolute daily min", "absolute daily minimum", "one decimal", "1 decimal", "deg. c", "weather.gov.hk",
    ]
    wg_terms = ["wunderground", "weather underground", "hong kong international airport", "international airport station", "airport station", "vhhh"]
    hko_score = sum(term in t for term in hko_terms)
    wg_score = sum(term in t for term in wg_terms)
    if hko_score >= 2 and wg_score == 0:
        return "HKO_Daily_Extract_one_decimal", "HKO Daily Extract evidence present; no Wunderground/airport evidence detected.", hko_score, wg_score
    if hko_score >= 3 and wg_score > 0:
        return "mixed_or_conflicting", "Both HKO and Wunderground/airport evidence detected; manual review required.", hko_score, wg_score
    if wg_score > 0 and hko_score < 3:
        return "Wunderground_or_airport", "Wunderground/airport evidence detected without sufficient HKO evidence.", hko_score, wg_score
    if hko_score == 1:
        return "possible_HKO_needs_review", "Weak HKO evidence detected; not enough for headline admissibility.", hko_score, wg_score
    return "ambiguous_or_unknown", "Insufficient settlement-source evidence.", hko_score, wg_score


def num(x: Any) -> Optional[float]:
    s = normalise(x)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def temp_num(text: str) -> Optional[float]:
    t = str(text).lower()
    pats = [
        r"(\d+(?:\.\d+)?)\s*°\s*c", r"(\d+(?:\.\d+)?)\s*deg(?:ree)?s?\s*c",
        r"(\d+(?:\.\d+)?)c(?:orhigher|orlower|orbelow|orabove)",
        r"-(\d+(?:\.\d+)?)c(?:orhigher|orlower|orbelow|orabove)?(?:-|$)", r"\b(\d{1,2}(?:\.\d+)?)\b",
    ]
    for pat in pats:
        m = re.search(pat, t)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return None


def classify_event(row: pd.Series) -> Tuple[str, str, float, str, str]:
    label = " ".join(normalise(row.get(c)) for c in ["group_item_title", "market_title", "market_question", "outcomes", "market_slug"] if c in row.index).lower()
    lb = num(row.get("lower_bound", "")); ub = num(row.get("upper_bound", "")); gt = num(row.get("group_item_threshold", ""))
    threshold = gt if gt is not None else (lb if lb is not None else temp_num(label))
    upper = any(x in label for x in ["or higher", "or above", "or more", "at least", "greater than or equal", "≥", "orhigher", "or-higher"])
    lower = any(x in label for x in ["or lower", "or below", "or less", "at most", "less than or equal", "≤", "orlower", "orbelow", "or-lower", "or-below"])
    if upper and threshold is not None:
        return "upper_tail", f"[{threshold:g}, infinity)", threshold, str(threshold), ""
    if lower and threshold is not None:
        return "lower_tail", f"(-infinity, {threshold:g}]", threshold, "", str(threshold)
    if lb is not None and ub is not None and ub > lb:
        if abs((ub - lb) - 1.0) < 1e-8:
            return "interior_bin", f"[{lb:g}, {ub:g})", lb, str(lb), str(ub)
        return "bounded_interval", f"[{lb:g}, {ub:g})", lb, str(lb), str(ub)
    if threshold is not None and not upper and not lower:
        return "interior_bin", f"[{threshold:g}, {threshold + 1:g})", threshold, str(threshold), str(threshold + 1.0)
    return "unknown", "", float("nan"), "", ""


def token_ids(x: Any) -> List[str]:
    s = normalise(x)
    if not s:
        return []
    try:
        val = json.loads(s)
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        if isinstance(val, dict):
            return [str(val[k]) for k in ["token_id", "tokenId", "asset_id", "assetId"] if k in val]
    except Exception:
        pass
    found = re.findall(r"\d{10,}", s)
    return found if found else [s]


def select_yes_token(row: pd.Series) -> str:
    ids: List[str] = []
    for col in ["clob_token_ids", "tokens", "yes_token_id", "token_id", "asset_id"]:
        if col in row.index:
            ids.extend(token_ids(row.get(col)))
    ids = [x for x in ids if x and x.lower() not in {"nan", "none", "null"}]
    return ids[0] if ids else ""


def dedupe_key(row: pd.Series) -> str:
    for c in ["market_slug", "market_id"]:
        v = normalise(row.get(c, ""))
        if v:
            return f"{c}:{v}"
    return "|".join(normalise(row.get(c, "")) for c in ["event_date", "event_slug", "group_item_title", "market_question", "event_set"])


def md_table(df: pd.DataFrame, cols: List[str], max_rows: int = 50) -> str:
    if df.empty:
        return "_No rows._"
    cols = [c for c in cols if c in df.columns]
    d = df[cols].head(max_rows).fillna("")
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in d.iterrows():
        out.append("| " + " | ".join(str(r[c]).replace("\n", " ")[:140] for c in cols) + " |")
    return "\n".join(out)


def bundle(paths: List[Path]) -> None:
    if OUT_BUNDLE.exists():
        OUT_BUNDLE.unlink()
    with zipfile.ZipFile(OUT_BUNDLE, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if p.exists():
                zf.write(p, arcname=str(p.relative_to(ROOT)))


def main() -> None:
    print(f"Repository root: {ROOT}")
    frames = [read_input(p) for p in PREFERRED_INPUTS]
    local = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else pd.DataFrame()
    if local.empty:
        raise SystemExit("No local 18f/18h/18i inputs found. Run earlier pipeline first.")
    local_df = pd.DataFrame([local_record(r) for _, r in local.iterrows()])
    event_slugs = sorted({extract_event_slug(s) for s in local_df["event_slug"].astype(str) if s and s.lower() != "nan"})
    market_slugs = sorted({s for s in local_df["market_slug"].astype(str) if s and s.lower() != "nan"})
    print(f"Local rows loaded: {len(local)}")
    print(f"Unique event slugs: {len(event_slugs)}")
    print(f"Unique market slugs: {len(market_slugs)}")

    api_records: List[Dict[str, Any]] = []
    print("\nFetching Gamma event metadata...")
    for i, slug in enumerate(event_slugs, 1):
        print(f"  event {i}/{len(event_slugs)}: {slug}")
        for params in [{"slug": slug}, {"slug": slug, "closed": "true"}, {"slug": slug, "archived": "true"}]:
            items = unwrap_items(gamma_get("/events", params, prefix=f"event_{slug}").get("json"))
            if items:
                for item in items:
                    api_records.extend(flatten_event(item, "api:/events"))
                break
    print("\nFetching Gamma market metadata...")
    for i, slug in enumerate(market_slugs, 1):
        print(f"  market {i}/{len(market_slugs)}: {slug}")
        for params in [{"slug": slug}, {"slug": slug, "closed": "true"}, {"slug": slug, "archived": "true"}]:
            items = unwrap_items(gamma_get("/markets", params, prefix=f"market_{slug}").get("json"))
            if items:
                for item in items:
                    api_records.append(flatten_market(item, "api:/markets"))
                break
    api_df = pd.DataFrame(api_records)
    print(f"API metadata records recovered: {len(api_df)}")

    combined = pd.concat([local_df, api_df], ignore_index=True, sort=False) if not api_df.empty else local_df.copy()
    expected = ["record_source", "event_id", "event_slug", "event_title", "event_date", "event_description", "event_rules", "event_resolution_source", "market_id", "market_slug", "market_question", "market_title", "market_description", "market_rules", "market_resolution_source", "group_item_title", "group_item_threshold", "group_item_range", "lower_bound", "upper_bound", "outcomes", "clob_token_ids", "tokens", "hko_tmax_C", "Y_ge_K", "api_event_raw", "market_raw"]
    for c in expected:
        if c not in combined.columns:
            combined[c] = ""
    combined["event_date"] = combined.apply(lambda r: normalise(r.get("event_date")) or extract_date(r.get("event_slug", ""), r.get("market_slug", ""), r.get("market_question", ""), r.get("event_title", "")), axis=1)
    combined["evidence_text"] = combined.apply(evidence_text, axis=1)

    fam = combined["evidence_text"].map(classify_family)
    combined["settlement_family"] = [x[0] for x in fam]
    combined["settlement_family_reason"] = [x[1] for x in fam]
    combined["hko_evidence_score"] = [x[2] for x in fam]
    combined["wunderground_airport_evidence_score"] = [x[3] for x in fam]
    ev = combined.apply(classify_event, axis=1)
    combined["contract_event_type"] = [x[0] for x in ev]
    combined["event_set"] = [x[1] for x in ev]
    combined["parsed_threshold_or_bin"] = [x[2] for x in ev]
    combined["event_lower_bound"] = [x[3] for x in ev]
    combined["event_upper_bound"] = [x[4] for x in ev]
    combined["selected_yes_token_id"] = combined.apply(select_yes_token, axis=1)
    combined["token_id_valid"] = combined["selected_yes_token_id"].astype(str).str.len().gt(20)
    combined["admissible_hko_event_contract"] = combined["settlement_family"].eq("HKO_Daily_Extract_one_decimal") & combined["contract_event_type"].isin(["upper_tail", "interior_bin"]) & combined["token_id_valid"]
    combined["dedupe_key"] = combined.apply(dedupe_key, axis=1)
    combined["_api_pri"] = combined["record_source"].astype(str).str.startswith("api:").map({True: 0, False: 1})
    combined["_fam_pri"] = combined["settlement_family"].map({"HKO_Daily_Extract_one_decimal": 0, "Wunderground_or_airport": 1, "mixed_or_conflicting": 2, "possible_HKO_needs_review": 3, "ambiguous_or_unknown": 4}).fillna(9)
    combined["_type_pri"] = combined["contract_event_type"].map({"upper_tail": 0, "interior_bin": 1, "bounded_interval": 2, "lower_tail": 3, "unknown": 4}).fillna(9)
    deduped = combined.sort_values(["dedupe_key", "admissible_hko_event_contract", "_fam_pri", "_type_pri", "_api_pri", "hko_evidence_score"], ascending=[True, False, True, True, True, False]).drop_duplicates("dedupe_key", keep="first").drop(columns=["_api_pri", "_fam_pri", "_type_pri"]).reset_index(drop=True)

    keep = ["record_source", "event_date", "event_slug", "market_slug", "market_id", "market_question", "market_title", "group_item_title", "group_item_threshold", "lower_bound", "upper_bound", "settlement_family", "settlement_family_reason", "hko_evidence_score", "wunderground_airport_evidence_score", "contract_event_type", "event_set", "parsed_threshold_or_bin", "event_lower_bound", "event_upper_bound", "selected_yes_token_id", "token_id_valid", "admissible_hko_event_contract", "hko_tmax_C", "Y_ge_K", "evidence_text"]
    audit = deduped[[c for c in keep if c in deduped.columns]].copy()
    universe = audit[audit["admissible_hko_event_contract"]].copy()
    excluded = audit[~audit["admissible_hko_event_contract"]].copy()
    family_summary = audit.groupby("settlement_family", dropna=False).agg(contracts=("settlement_family", "size"), admissible_hko_event_contracts=("admissible_hko_event_contract", "sum"), token_valid=("token_id_valid", "sum")).reset_index().sort_values(["admissible_hko_event_contracts", "contracts"], ascending=False)
    event_type_summary = audit.groupby(["contract_event_type", "settlement_family"], dropna=False).agg(contracts=("contract_event_type", "size"), admissible_hko_event_contracts=("admissible_hko_event_contract", "sum")).reset_index().sort_values(["admissible_hko_event_contracts", "contracts"], ascending=False)
    march13 = audit[audit["event_date"].astype(str).eq("2026-03-13")].copy()

    audit.to_csv(OUT_AUDIT, index=False)
    universe.to_csv(OUT_UNIVERSE, index=False)
    excluded.to_csv(OUT_EXCLUDED, index=False)
    family_summary.to_csv(OUT_FAMILY_SUMMARY, index=False)
    event_type_summary.to_csv(OUT_EVENT_TYPE_SUMMARY, index=False)
    march13.to_csv(OUT_MARCH13, index=False)

    report = []
    report.append("# 18j Gamma metadata settlement-family audit\n")
    report.append(f"Generated: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`\n")
    report.append("## Purpose\n")
    report.append("This audit classifies Hong Kong Polymarket temperature contracts by settlement family before expanding the frozen 18i upper-tail baseline to a full HKO contract-event universe. The headline family is HKO Daily Extract one-decimal. Wunderground, airport, ambiguous and other settlement mechanisms are excluded from the main Hong Kong empirical sample.\n")
    report.append("## Input coverage\n")
    report.append(f"- Local processed rows loaded: `{len(local)}`\n")
    report.append(f"- Unique local event slugs: `{len(event_slugs)}`\n")
    report.append(f"- Unique local market slugs: `{len(market_slugs)}`\n")
    report.append(f"- API metadata records recovered: `{len(api_df)}`\n")
    report.append(f"- Deduplicated audited contract rows: `{len(audit)}`\n")
    report.append(f"- Preliminary admissible HKO event-contract rows: `{len(universe)}`\n")
    report.append("\n## Settlement-family summary\n")
    report.append(md_table(family_summary, family_summary.columns.tolist(), 50))
    report.append("\n\n## Contract-event-type summary\n")
    report.append(md_table(event_type_summary, event_type_summary.columns.tolist(), 80))
    report.append("\n\n## March 13 audit\n")
    report.append("The March 13 rows are singled out because external review suggested that some early Hong Kong markets may belong to a Wunderground / airport settlement family rather than the HKO Daily Extract one-decimal family.\n")
    report.append(md_table(march13, ["event_date", "market_slug", "market_question", "group_item_title", "settlement_family", "contract_event_type", "event_set", "admissible_hko_event_contract", "settlement_family_reason"], 60))
    report.append("\n\n## Preliminary admissible HKO contract-event universe preview\n")
    report.append(md_table(universe, ["event_date", "market_slug", "market_question", "group_item_title", "contract_event_type", "event_set", "settlement_family", "selected_yes_token_id"], 80))
    report.append("\n\n## Interpretation\n")
    if len(universe):
        report.append("The audit identifies a non-empty preliminary set of admissible HKO Daily Extract one-decimal event contracts. These may include both upper-tail contracts and interior-bin contracts where metadata or rule evidence supports the interpretation. This supports the updated empirical direction: Hong Kong can be expanded from an upper-tail-only pilot into a full contract-event framework, provided settlement-family filtering is enforced before scoring, postprocessing and trading simulation.\n")
    else:
        report.append("The strict automated audit did not identify admissible HKO event contracts. Manual review of the evidence-text columns is required before enlarging the empirical sample.\n")
    OUT_REPORT.write_text("\n".join(report).rstrip() + "\n", encoding="utf-8")

    outputs = [OUT_AUDIT, OUT_UNIVERSE, OUT_EXCLUDED, OUT_FAMILY_SUMMARY, OUT_EVENT_TYPE_SUMMARY, OUT_MARCH13, OUT_REPORT]
    bundle(outputs)

    print("\n=== 18j outputs ===")
    for p in outputs + [OUT_BUNDLE]:
        if p.suffix == ".csv":
            print(f"{p.relative_to(ROOT)}: {pd.read_csv(p).shape}")
        else:
            print(f"{p.relative_to(ROOT)}: FOUND")
    print("\n=== Settlement-family summary ===")
    print(family_summary.to_string(index=False))
    print("\n=== Contract-event-type summary ===")
    print(event_type_summary.to_string(index=False))
    print("\n=== March 13 audit ===")
    if march13.empty:
        print("No March 13 rows in audited set.")
    else:
        cols = [c for c in ["event_date", "market_slug", "market_question", "group_item_title", "settlement_family", "contract_event_type", "event_set", "admissible_hko_event_contract", "settlement_family_reason"] if c in march13.columns]
        print(march13[cols].to_string(index=False))
    print("\n=== Preliminary admissible HKO universe preview ===")
    if universe.empty:
        print("No admissible HKO event contracts detected.")
    else:
        cols = [c for c in ["event_date", "market_slug", "market_question", "group_item_title", "contract_event_type", "event_set", "settlement_family", "selected_yes_token_id"] if c in universe.columns]
        print(universe[cols].head(80).to_string(index=False))
    print(f"\nReview bundle written: {OUT_BUNDLE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
