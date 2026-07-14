from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
import math
import re
import zipfile
from typing import Any, Iterable, Optional, Tuple

import pandas as pd

ROOT = Path.cwd()
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "research_outputs"
BUNDLES = ROOT / "data" / "review_bundles"

PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)
BUNDLES.mkdir(parents=True, exist_ok=True)

INPUT_AUDIT = PROCESSED / "18j_gamma_metadata_settlement_family_audit.csv"

OUT_AUDIT = PROCESSED / "18j_v2_gamma_metadata_settlement_family_audit_fixed.csv"
OUT_UNIVERSE = PROCESSED / "18j_v2_full_hko_contract_event_universe.csv"
OUT_EXCLUDED = PROCESSED / "18j_v2_excluded_or_ambiguous_hk_contracts.csv"
OUT_FAMILY_SUMMARY = PROCESSED / "18j_v2_settlement_family_summary.csv"
OUT_EVENT_TYPE_SUMMARY = PROCESSED / "18j_v2_contract_event_type_summary.csv"
OUT_DATE_SUMMARY = PROCESSED / "18j_v2_contract_date_summary.csv"
OUT_MARCH13 = PROCESSED / "18j_v2_march13_settlement_family_audit.csv"
OUT_VALIDATION = PROCESSED / "18j_v2_parsing_validation_checks.csv"
OUT_REPORT = REPORTS / "18j_v2_contract_event_parsing_fix_report.md"
OUT_ZIP = BUNDLES / "18j_v2_review_bundle.zip"

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def norm(x: Any) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).strip()


def first_nonempty(values: Iterable[Any]) -> str:
    for v in values:
        s = norm(v)
        if s and s.lower() not in {"nan", "none", "null"}:
            return s
    return ""


def parse_contract_date_from_text(text: str, fallback_year: Optional[int] = None) -> str:
    s = norm(text).lower().replace("'26", " 2026")

    # Primary: Polymarket slug pattern.
    m = re.search(
        r"highest-temperature-in-hong-kong-on-"
        r"(january|february|march|april|may|june|july|august|september|october|november|december)"
        r"[-\s_]+(\d{1,2})[-\s_,]+(20\d{2})",
        s,
    )
    if m:
        mon, day, year = m.groups()
        return f"{int(year):04d}-{MONTHS[mon]:02d}-{int(day):02d}"

    # Natural language with explicit year.
    m = re.search(
        r"\bon\s+"
        r"(january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})",
        s,
    )
    if m:
        mon, day, year = m.groups()
        return f"{int(year):04d}-{MONTHS[mon]:02d}-{int(day):02d}"

    # Natural language without year; infer from fallback if supplied.
    m = re.search(
        r"\bon\s+"
        r"(january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+(\d{1,2})(?:st|nd|rd|th)?\b",
        s,
    )
    if m and fallback_year:
        mon, day = m.groups()
        return f"{int(fallback_year):04d}-{MONTHS[mon]:02d}-{int(day):02d}"

    # ISO fallback.
    m = re.search(r"(20\d{2})[-_/](\d{1,2})[-_/](\d{1,2})", s)
    if m:
        year, month, day = m.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    return ""


def infer_year_from_row(row: pd.Series) -> Optional[int]:
    for c in ["market_slug", "event_slug", "event_date", "evidence_text", "market_question"]:
        if c in row.index:
            m = re.search(r"20\d{2}", norm(row.get(c)))
            if m:
                return int(m.group(0))
    return 2026


def parse_contract_date(row: pd.Series) -> str:
    year = infer_year_from_row(row)
    # Prefer market-level fields, then event-level. Existing event_date can be close/resolve date and is intentionally late.
    fields = ["market_slug", "market_question", "group_item_title", "market_title", "event_slug", "event_title", "evidence_text", "event_date"]
    for f in fields:
        if f in row.index:
            d = parse_contract_date_from_text(norm(row.get(f)), fallback_year=year)
            if d:
                return d
    return ""


def parse_label_text(row: pd.Series) -> str:
    # The temperature boundary must come from the visible outcome label/question/slug, not groupItemThreshold.
    return first_nonempty([
        row.get("group_item_title", ""),
        row.get("market_question", ""),
        row.get("market_title", ""),
        row.get("market_slug", ""),
        row.get("outcomes", ""),
    ])


def parse_temperature_from_label(label: str) -> Optional[float]:
    s = norm(label).lower()
    if not s:
        return None

    # Label text: "21°C", "30°C or higher", "20°C or below".
    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*°\s*c", s)
    if m:
        return float(m.group(1))

    # Plain deg C text.
    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*(?:deg\.?\s*c|degrees?\s*celsius|celsius)", s)
    if m:
        return float(m.group(1))

    # Slug endpoints: 30corhigher, 20corbelow, 21c.
    m = re.search(r"(?:^|[-_])(\d{1,2}(?:\.\d+)?)c(?:orhigher|orabove|orbelow|orlower)?(?:[-_]|$)", s)
    if m:
        return float(m.group(1))

    # As a last resort use a number near C wording only, not arbitrary ordinal fields.
    m = re.search(r"\b(\d{1,2}(?:\.\d+)?)\b\s*(?:c\b|degrees?\b|temperature)", s)
    if m:
        return float(m.group(1))

    return None


def classify_contract_event(row: pd.Series) -> Tuple[str, str, Optional[float], float, float, str, str]:
    label = parse_label_text(row)
    slug = norm(row.get("market_slug", ""))
    question = norm(row.get("market_question", ""))
    text = " ".join([label, slug, question]).lower()
    k = parse_temperature_from_label(label)
    if k is None:
        k = parse_temperature_from_label(slug)
    if k is None:
        return "unknown", "", None, math.nan, math.nan, "", "Could not parse Celsius label from market label/question/slug."

    # Upper endpoint: exact threshold [K, infinity).
    if any(x in text for x in ["or higher", "or above", "or more", "at least", "corhigher", "corabove"]):
        return (
            "upper_tail",
            f"[{k:g}, infinity)",
            k,
            k,
            math.inf,
            f"T_HKO >= {k:g}",
            "Parsed from visible Celsius label; groupItemThreshold ignored as an ordinal index.",
        )

    # Lower endpoint in the floor-bin family. The rules say the market resolves to the temperature range that contains
    # the one-decimal HKO value. Hence "K°C or below" covers the K-bin and all lower bins: T < K+1.
    if any(x in text for x in ["or below", "or lower", "or less", "at most", "corbelow", "corlower"]):
        return (
            "lower_tail_endpoint",
            f"(-infinity, {k + 1:g})",
            k,
            -math.inf,
            k + 1.0,
            f"T_HKO < {k + 1:g}",
            "Lower endpoint interpreted under HKO one-decimal floor-bin convention: K°C or below means the K-bin and lower bins.",
        )

    # Interior single-degree bin: [k, k+1).
    return (
        "interior_bin",
        f"[{k:g}, {k + 1:g})",
        k,
        k,
        k + 1.0,
        f"{k:g} <= T_HKO < {k + 1:g}",
        "Interior bin interpreted under HKO one-decimal floor-bin convention.",
    )


def compute_y_event(t: Any, lower: float, upper: float) -> str:
    try:
        x = float(t)
        if math.isnan(x):
            return ""
    except Exception:
        return ""
    lower_ok = True if math.isinf(lower) and lower < 0 else x >= lower
    upper_ok = True if math.isinf(upper) and upper > 0 else x < upper
    return str(int(lower_ok and upper_ok))


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    d = df.head(max_rows).copy().fillna("")
    cols = list(d.columns)
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in d.iterrows():
        out.append("| " + " | ".join(str(r[c]).replace("\n", " ")[:150] for c in cols) + " |")
    return "\n".join(out)


def main() -> None:
    if not INPUT_AUDIT.exists():
        raise SystemExit(f"Missing input audit file: {INPUT_AUDIT}. Run 18j first.")

    df = pd.read_csv(INPUT_AUDIT, dtype=str)
    original_rows = len(df)
    df["original_event_date"] = df.get("event_date", "")

    df["contract_date"] = df.apply(parse_contract_date, axis=1)
    df["event_date"] = df["contract_date"]
    df["visible_contract_label"] = df.apply(parse_label_text, axis=1)

    parsed = df.apply(classify_contract_event, axis=1)
    df["contract_event_type_v2"] = [x[0] for x in parsed]
    df["event_set_v2"] = [x[1] for x in parsed]
    df["label_temperature_C"] = [x[2] for x in parsed]
    df["event_lower_bound_C"] = [x[3] for x in parsed]
    df["event_upper_bound_C"] = [x[4] for x in parsed]
    df["event_condition_v2"] = [x[5] for x in parsed]
    df["event_parsing_reason_v2"] = [x[6] for x in parsed]

    # Keep old parser fields for audit, but do not use them downstream.
    df["old_contract_event_type"] = df.get("contract_event_type", "")
    df["old_event_set"] = df.get("event_set", "")
    df["old_parsed_threshold_or_bin"] = df.get("parsed_threshold_or_bin", "")
    df["old_event_lower_bound"] = df.get("event_lower_bound", "")
    df["old_event_upper_bound"] = df.get("event_upper_bound", "")

    # Recompute support flags. The full HKO event-contract universe now includes lower endpoints too.
    df["is_hko_daily_extract_family_v2"] = df["settlement_family"].eq("HKO_Daily_Extract_one_decimal")
    df["is_supported_contract_event_type_v2"] = df["contract_event_type_v2"].isin([
        "lower_tail_endpoint", "interior_bin", "upper_tail"
    ])
    df["token_id_valid_v2"] = df.get("selected_yes_token_id", "").fillna("").astype(str).str.len().gt(20)
    df["admissible_hko_event_contract_v2"] = (
        df["is_hko_daily_extract_family_v2"]
        & df["is_supported_contract_event_type_v2"]
        & df["token_id_valid_v2"]
        & df["contract_date"].astype(str).str.match(r"20\d{2}-\d{2}-\d{2}")
        & df["label_temperature_C"].notna()
    )

    # Optional outcome if HKO value already exists; many metadata rows may not have HKO value yet.
    df["Y_event_v2"] = [
        compute_y_event(t, lo, hi)
        for t, lo, hi in zip(df.get("hko_tmax_C", ""), df["event_lower_bound_C"], df["event_upper_bound_C"])
    ]

    # Sanity checks.
    df["date_was_corrected"] = df["original_event_date"].astype(str).ne(df["event_date"].astype(str))
    df["event_set_was_corrected"] = df["old_event_set"].astype(str).ne(df["event_set_v2"].astype(str))
    df["group_item_threshold_is_ordinal_not_celsius"] = False
    if "group_item_threshold" in df.columns:
        g = pd.to_numeric(df["group_item_threshold"], errors="coerce")
        k = pd.to_numeric(df["label_temperature_C"], errors="coerce")
        df["group_item_threshold_is_ordinal_not_celsius"] = g.notna() & k.notna() & (abs(g - k) > 1e-8)

    # Validation issue tags.
    issues = []
    for _, r in df.iterrows():
        row_issues = []
        if r["contract_date"] == "":
            row_issues.append("missing_contract_date")
        if pd.isna(r["label_temperature_C"]):
            row_issues.append("missing_label_temperature")
        else:
            try:
                temp = float(r["label_temperature_C"])
                if temp < 0 or temp > 50:
                    row_issues.append("temperature_outside_plausible_C_range")
            except Exception:
                row_issues.append("invalid_temperature")
        if r["settlement_family"] == "HKO_Daily_Extract_one_decimal" and r["contract_event_type_v2"] == "unknown":
            row_issues.append("hko_row_unknown_event_type")
        issues.append(";".join(row_issues))
    df["v2_validation_issues"] = issues

    # Column order: put corrected fields early.
    front = [
        "record_source", "original_event_date", "event_date", "contract_date", "event_slug", "market_slug",
        "market_question", "group_item_title", "visible_contract_label", "settlement_family",
        "settlement_family_reason", "contract_event_type_v2", "event_set_v2", "event_condition_v2",
        "label_temperature_C", "event_lower_bound_C", "event_upper_bound_C",
        "selected_yes_token_id", "token_id_valid_v2", "admissible_hko_event_contract_v2",
        "hko_tmax_C", "Y_event_v2", "old_contract_event_type", "old_event_set", "group_item_threshold",
        "group_item_threshold_is_ordinal_not_celsius", "date_was_corrected", "event_set_was_corrected",
        "v2_validation_issues", "evidence_text",
    ]
    cols = [c for c in front if c in df.columns] + [c for c in df.columns if c not in front]
    df = df[cols]

    universe = df[df["admissible_hko_event_contract_v2"]].copy()
    excluded = df[~df["admissible_hko_event_contract_v2"]].copy()

    family_summary = (
        df.groupby("settlement_family", dropna=False)
        .agg(
            contracts=("settlement_family", "size"),
            admissible_hko_event_contracts_v2=("admissible_hko_event_contract_v2", "sum"),
            token_valid_v2=("token_id_valid_v2", "sum"),
            date_corrected=("date_was_corrected", "sum"),
            event_set_corrected=("event_set_was_corrected", "sum"),
        )
        .reset_index()
        .sort_values(["admissible_hko_event_contracts_v2", "contracts"], ascending=False)
    )

    event_type_summary = (
        df.groupby(["contract_event_type_v2", "settlement_family"], dropna=False)
        .agg(
            contracts=("contract_event_type_v2", "size"),
            admissible_hko_event_contracts_v2=("admissible_hko_event_contract_v2", "sum"),
        )
        .reset_index()
        .sort_values(["admissible_hko_event_contracts_v2", "contracts"], ascending=False)
    )

    date_summary = (
        universe.groupby("event_date", dropna=False)
        .agg(
            admissible_contracts=("admissible_hko_event_contract_v2", "sum"),
            lower_tail_endpoints=("contract_event_type_v2", lambda s: int((s == "lower_tail_endpoint").sum())),
            interior_bins=("contract_event_type_v2", lambda s: int((s == "interior_bin").sum())),
            upper_tails=("contract_event_type_v2", lambda s: int((s == "upper_tail").sum())),
        )
        .reset_index()
        .sort_values("event_date")
    )

    march13 = df[df["event_date"].eq("2026-03-13")].copy()

    validation = pd.DataFrame({
        "check": [
            "input_rows",
            "v2_audited_rows",
            "v2_admissible_hko_event_contract_rows",
            "v2_hko_lower_tail_endpoint_rows",
            "v2_hko_interior_bin_rows",
            "v2_hko_upper_tail_rows",
            "rows_with_corrected_dates",
            "rows_with_corrected_event_sets",
            "rows_where_groupItemThreshold_is_ordinal_not_celsius",
            "admissible_rows_with_validation_issues",
            "march13_rows_after_contract_date_fix",
            "march13_hko_admissible_rows",
            "march13_wunderground_airport_rows",
        ],
        "value": [
            original_rows,
            len(df),
            int(df["admissible_hko_event_contract_v2"].sum()),
            int(((df["settlement_family"] == "HKO_Daily_Extract_one_decimal") & (df["contract_event_type_v2"] == "lower_tail_endpoint")).sum()),
            int(((df["settlement_family"] == "HKO_Daily_Extract_one_decimal") & (df["contract_event_type_v2"] == "interior_bin")).sum()),
            int(((df["settlement_family"] == "HKO_Daily_Extract_one_decimal") & (df["contract_event_type_v2"] == "upper_tail")).sum()),
            int(df["date_was_corrected"].sum()),
            int(df["event_set_was_corrected"].sum()),
            int(df["group_item_threshold_is_ordinal_not_celsius"].sum()),
            int((df["admissible_hko_event_contract_v2"] & df["v2_validation_issues"].astype(str).ne("")).sum()),
            len(march13),
            int((march13["settlement_family"] == "HKO_Daily_Extract_one_decimal").sum()),
            int((march13["settlement_family"] == "Wunderground_or_airport").sum()),
        ],
    })

    # Save.
    df.to_csv(OUT_AUDIT, index=False)
    universe.to_csv(OUT_UNIVERSE, index=False)
    excluded.to_csv(OUT_EXCLUDED, index=False)
    family_summary.to_csv(OUT_FAMILY_SUMMARY, index=False)
    event_type_summary.to_csv(OUT_EVENT_TYPE_SUMMARY, index=False)
    date_summary.to_csv(OUT_DATE_SUMMARY, index=False)
    march13.to_csv(OUT_MARCH13, index=False)
    validation.to_csv(OUT_VALIDATION, index=False)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    report = []
    report.append("# 18j v2 contract-event parsing fix\n")
    report.append(f"Generated: `{timestamp}`\n")
    report.append("## Purpose\n")
    report.append(
        "This patch fixes the two parsing errors found in the first 18j output. The first 18j correctly identified a large HKO Daily Extract one-decimal family, but it used `groupItemThreshold` as if it were the Celsius boundary and sometimes used closing/resolution dates instead of the contract date. In this v2 output, Celsius boundaries are parsed from visible labels, questions and slugs, while the contract date is parsed from the market slug/question. `groupItemThreshold` is retained only as metadata because it is often an ordinal group index.\n"
    )
    report.append("## Correct event-set convention\n")
    report.append("- `K°C or higher` is mapped to `[K, infinity)`, i.e. `T_HKO >= K`.\n")
    report.append("- Interior `k°C` is mapped to `[k, k+1)`, i.e. `k <= T_HKO < k+1`.\n")
    report.append("- Lower endpoint `k°C or below` is mapped to `(-infinity, k+1)` under the HKO one-decimal floor-bin family, because the market rule states that the outcome is the temperature range containing the one-decimal HKO value.\n")
    report.append("## Validation checks\n")
    report.append(md_table(validation, max_rows=50))
    report.append("\n\n## Settlement-family summary\n")
    report.append(md_table(family_summary, max_rows=50))
    report.append("\n\n## Contract-event-type summary\n")
    report.append(md_table(event_type_summary, max_rows=80))
    report.append("\n\n## Contract-date summary preview\n")
    report.append(md_table(date_summary, max_rows=40))
    report.append("\n\n## March 13 audit after date fix\n")
    march_cols = [
        "event_date", "market_slug", "market_question", "group_item_title", "settlement_family",
        "contract_event_type_v2", "event_set_v2", "event_condition_v2", "admissible_hko_event_contract_v2",
        "settlement_family_reason",
    ]
    report.append(md_table(march13[[c for c in march_cols if c in march13.columns]], max_rows=50))
    report.append("\n\n## Admissible HKO contract-event universe preview\n")
    prev_cols = [
        "event_date", "market_slug", "market_question", "group_item_title", "settlement_family",
        "contract_event_type_v2", "event_set_v2", "event_condition_v2", "selected_yes_token_id",
    ]
    report.append(md_table(universe[[c for c in prev_cols if c in universe.columns]], max_rows=60))
    report.append("\n\n## Interpretation\n")
    report.append(
        "The v2 audit should be used as the repaired 18j output. The HKO Daily Extract one-decimal family is large enough to support the updated full Hong Kong contract-event framework. The main empirical universe should be built from the admissible HKO rows in `18j_v2_full_hko_contract_event_universe.csv`, not from the original preliminary 18j universe. Non-HKO rows, including Wunderground / airport rows, remain excluded from the headline Hong Kong analysis.\n"
    )
    OUT_REPORT.write_text("\n".join(report).rstrip() + "\n", encoding="utf-8")

    # Zip review bundle.
    bundle_files = [
        OUT_AUDIT, OUT_UNIVERSE, OUT_EXCLUDED, OUT_FAMILY_SUMMARY, OUT_EVENT_TYPE_SUMMARY,
        OUT_DATE_SUMMARY, OUT_MARCH13, OUT_VALIDATION, OUT_REPORT,
    ]
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in bundle_files:
            if p.exists():
                zf.write(p, p.relative_to(ROOT))

    print("\n=== 18j v2 outputs ===")
    for p in bundle_files + [OUT_ZIP]:
        if p.suffix == ".csv":
            d = pd.read_csv(p)
            print(f"{p.relative_to(ROOT)}: {d.shape}")
        else:
            print(f"{p.relative_to(ROOT)}: FOUND")

    print("\n=== Validation checks ===")
    print(validation.to_string(index=False))
    print("\n=== Settlement-family summary ===")
    print(family_summary.to_string(index=False))
    print("\n=== Contract-event-type summary ===")
    print(event_type_summary.to_string(index=False))
    print("\n=== March 13 audit after date fix ===")
    if march13.empty:
        print("No March 13 rows after date fix.")
    else:
        cols = [c for c in march_cols if c in march13.columns]
        print(march13[cols].to_string(index=False))
    print("\n=== Admissible HKO universe preview ===")
    if universe.empty:
        print("No admissible HKO event contracts.")
    else:
        cols = [c for c in prev_cols if c in universe.columns]
        print(universe[cols].head(80).to_string(index=False))


if __name__ == "__main__":
    main()
