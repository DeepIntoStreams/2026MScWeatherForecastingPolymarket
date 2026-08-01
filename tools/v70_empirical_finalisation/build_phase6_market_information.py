#!/usr/bin/env python3
"""
Phase 6: exact-support market comparison and information-content analysis.

The phase is read-only with respect to all forecasting models. It combines the
accepted Phase 1 exact-support probability books for raw, static, selected
Matérn and Polymarket, then:

1. certifies common support and probability-book coherence;
2. computes book-level and settlement-date-balanced proper scores;
3. compares weather procedures with the market on development, June external
   and full exact support;
4. applies ordinary settlement-date and circular moving-block inference;
5. quantifies market-versus-Matérn disagreement;
6. measures market and forecast revisions across decision rules;
7. tests descriptive co-movement with date-clustered regression;
8. recovers market-record age and stale-record sensitivity when timestamps are
   available;
9. creates thesis-ready tables, figures, report, manifest and review bundle.

Sign convention for score comparisons:
    model_minus_market = model loss - market loss.
Positive values mean the market had lower realised loss.

The analysis is descriptive and predictive, not causal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    raise RuntimeError("matplotlib is required") from exc

try:
    from scipy import stats
except Exception as exc:  # pragma: no cover
    raise RuntimeError("scipy is required") from exc


MODEL_ORDER = ["raw", "static", "matern", "market"]
MODEL_LABELS = {
    "raw": "Raw point law",
    "static": "Static Gaussian",
    "matern": "Matérn-3/2 GP",
    "market": "Polymarket",
}
RULE_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]
RULE_LABELS = {
    "24h_prior": "24h prior",
    "12h_prior": "12h prior",
    "6h_prior": "6h prior",
    "event_day_open": "Event-day open",
}
METRIC_LABELS = {
    "binary_brier": "Binary Brier",
    "binary_log": "Binary log",
    "categorical_log": "Categorical log",
    "multiclass_brier": "Multiclass Brier",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed\nSTDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "1": True,
            "yes": True,
            "passed": True,
            "false": False,
            "0": False,
            "no": False,
            "failed": False,
        })
        .fillna(False)
        .astype(bool)
    )


def dependency_check(path: Path, label: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing={path}"
    frame = pd.read_csv(path)
    if not {"critical", "passed"}.issubset(frame.columns):
        return False, f"{label} table lacks critical/passed columns"
    failed = frame.loc[
        bool_series(frame["critical"]) & ~bool_series(frame["passed"])
    ]
    return failed.empty, f"critical_failures={len(failed)}"


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".gz" or path.name.endswith(".csv.gz"):
        return pd.read_csv(path, compression="gzip", low_memory=False)
    return pd.read_csv(path, low_memory=False)


def normalise_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")


def normalise_model(value: Any) -> str:
    text = normalise_name(value)
    if "market" in text or "polymarket" in text:
        return "market"
    if "matern" in text or "mat32" in text or text in {
        "gp",
        "selected_gp",
        "selected",
        "weather_gp",
    }:
        return "matern"
    if "static" in text:
        return "static"
    if "raw" in text or "point" in text or "deterministic" in text:
        return "raw"
    return text


def normalise_rule(value: Any) -> str:
    text = normalise_name(value)
    aliases = {
        "24h": "24h_prior",
        "24hr": "24h_prior",
        "24h_prior": "24h_prior",
        "twenty_four_h_prior": "24h_prior",
        "12h": "12h_prior",
        "12hr": "12h_prior",
        "12h_prior": "12h_prior",
        "6h": "6h_prior",
        "6hr": "6h_prior",
        "6h_prior": "6h_prior",
        "open": "event_day_open",
        "event_open": "event_day_open",
        "event_day_open": "event_day_open",
        "day_open": "event_day_open",
    }
    if text in aliases:
        return aliases[text]
    if "24" in text and "prior" in text:
        return "24h_prior"
    if "12" in text and "prior" in text:
        return "12h_prior"
    if "6" in text and "prior" in text:
        return "6h_prior"
    if "open" in text:
        return "event_day_open"
    return text


def resolve_column(
    frame: pd.DataFrame,
    candidates: Sequence[str],
    required: bool = False,
) -> str | None:
    lookup = {normalise_name(column): column for column in frame.columns}
    for candidate in candidates:
        key = normalise_name(candidate)
        if key in lookup:
            return lookup[key]
    if required:
        raise KeyError(
            f"None of {list(candidates)} found. Columns={list(frame.columns)}"
        )
    return None


def parse_event_order_from_label(label: Any) -> float:
    text = str(label).strip().lower()
    if not text or text == "nan":
        return np.nan
    if "below" in text or "under" in text or text.startswith("<"):
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group()) - 1000.0 if match else -1000.0
    if "above" in text or "over" in text or "+" in text or ">=" in text:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group()) + 1000.0 if match else 1000.0
    numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
    if numbers:
        return float(numbers[0])
    return np.nan


def wide_probability_columns(frame: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for column in frame.columns:
        key = normalise_name(column)
        probability_like = any(
            token in key
            for token in ["prob", "probability", "event_p", "p_event"]
        )
        if not probability_like:
            continue
        model = normalise_model(key)
        if model in MODEL_ORDER:
            mapping[model] = column
    return mapping


def standardise_event_books(
    frame: pd.DataFrame,
    source_name: str,
) -> pd.DataFrame:
    date_col = resolve_column(
        frame,
        ["target_date", "settlement_date", "trade_date", "date"],
        required=True,
    )
    rule_col = resolve_column(
        frame,
        ["decision_rule", "rule", "decision_time_rule"],
        required=True,
    )
    model_col = resolve_column(
        frame,
        ["model", "forecast_model", "probability_model", "source_model"],
    )
    probability_col = resolve_column(
        frame,
        [
            "event_probability",
            "probability",
            "probability_raw",
            "model_probability",
            "forecast_probability",
            "selected_probability",
            "p_event",
            "p",
        ],
    )
    normalised_col = resolve_column(
        frame,
        [
            "normalised_probability",
            "normalized_probability",
            "probability_normalised",
            "probability_normalized",
            "categorical_probability",
        ],
    )
    outcome_col = resolve_column(
        frame,
        [
            "event_outcome",
            "outcome",
            "realised",
            "realized",
            "is_winner",
            "winner",
            "y",
            "label",
        ],
    )
    event_order_col = resolve_column(
        frame,
        [
            "event_order",
            "event_index",
            "event_rank",
            "contract_index",
            "bucket_index",
            "outcome_index",
        ],
    )
    event_label_col = resolve_column(
        frame,
        [
            "event_label",
            "event_key",
            "contract_label",
            "outcome_label",
            "market_outcome",
            "bucket_label",
        ],
    )
    lower_col = resolve_column(
        frame,
        [
            "event_lower_bound_c",
            "event_lower_c",
            "lower_bound_c",
            "lower_bound",
            "lower_c",
            "event_lower",
        ],
    )
    upper_col = resolve_column(
        frame,
        [
            "event_upper_bound_c",
            "event_upper_c",
            "upper_bound_c",
            "upper_bound",
            "upper_c",
            "event_upper",
        ],
    )
    record_time_col = resolve_column(
        frame,
        [
            "selected_market_timestamp_utc",
            "market_record_timestamp_utc",
            "market_timestamp_utc",
            "record_timestamp_utc",
            "selected_timestamp_utc",
            "price_timestamp_utc",
            "timestamp_utc",
        ],
    )
    decision_time_col = resolve_column(
        frame,
        [
            "decision_time_utc",
            "decision_cutoff_utc",
            "cutoff_utc",
            "decision_timestamp_utc",
        ],
    )

    id_columns = [
        column
        for column in [
            date_col,
            rule_col,
            outcome_col,
            event_order_col,
            event_label_col,
            lower_col,
            upper_col,
            record_time_col,
            decision_time_col,
            normalised_col,
        ]
        if column is not None
    ]

    if model_col is not None and probability_col is not None:
        working = frame.copy()
        result = pd.DataFrame(
            {
                "target_date": working[date_col],
                "decision_rule": working[rule_col],
                "model": working[model_col],
                "probability_raw": working[probability_col],
            }
        )
        result["probability_source_normalised"] = (
            working[normalised_col]
            if normalised_col is not None
            else np.nan
        )
        for output, source in [
            ("outcome", outcome_col),
            ("event_order_source", event_order_col),
            ("event_label", event_label_col),
            ("event_lower_bound_c", lower_col),
            ("event_upper_bound_c", upper_col),
            ("market_record_timestamp_utc", record_time_col),
            ("decision_timestamp_utc", decision_time_col),
        ]:
            result[output] = working[source] if source is not None else np.nan
    else:
        wide = wide_probability_columns(frame)
        if not wide:
            raise ValueError(
                f"{source_name}: could not identify long or wide probability "
                f"columns. Columns={list(frame.columns)}"
            )
        pieces: list[pd.DataFrame] = []
        for model, column in wide.items():
            piece = pd.DataFrame(
                {
                    "target_date": frame[date_col],
                    "decision_rule": frame[rule_col],
                    "model": model,
                    "probability_raw": frame[column],
                }
            )
            for output, source in [
                ("outcome", outcome_col),
                ("event_order_source", event_order_col),
                ("event_label", event_label_col),
                ("event_lower_bound_c", lower_col),
                ("event_upper_bound_c", upper_col),
                ("market_record_timestamp_utc", record_time_col),
                ("decision_timestamp_utc", decision_time_col),
            ]:
                piece[output] = frame[source] if source is not None else np.nan
            pieces.append(piece)
        result = pd.concat(pieces, ignore_index=True)
        result["probability_source_normalised"] = np.nan

    result["target_date"] = pd.to_datetime(
        result["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    result["decision_rule"] = result["decision_rule"].map(normalise_rule)
    result["model"] = result["model"].map(normalise_model)
    result["probability_raw"] = pd.to_numeric(
        result["probability_raw"], errors="coerce"
    )
    result["probability_source_normalised"] = pd.to_numeric(
        result["probability_source_normalised"], errors="coerce"
    )
    result["outcome"] = pd.to_numeric(result["outcome"], errors="coerce")
    result["event_order_source"] = pd.to_numeric(
        result["event_order_source"], errors="coerce"
    )
    result["event_lower_bound_c"] = pd.to_numeric(
        result["event_lower_bound_c"], errors="coerce"
    )
    result["event_upper_bound_c"] = pd.to_numeric(
        result["event_upper_bound_c"], errors="coerce"
    )

    order = result["event_order_source"].copy()
    if order.isna().all() and result["event_lower_bound_c"].notna().any():
        order = result["event_lower_bound_c"]
    if order.isna().all() and result["event_label"].notna().any():
        order = result["event_label"].map(parse_event_order_from_label)
    result["_event_sort_value"] = order
    if result["_event_sort_value"].isna().any():
        missing_groups = (
            result.loc[result["_event_sort_value"].isna()]
            [["target_date", "decision_rule", "model"]]
            .drop_duplicates()
        )
        if not missing_groups.empty:
            raise ValueError(
                f"{source_name}: event ordering unavailable for "
                f"{len(missing_groups)} books"
            )

    result["event_order"] = (
        result.groupby(["target_date", "decision_rule", "model"])[
            "_event_sort_value"
        ]
        .rank(method="dense")
        .astype("Int64")
    )
    result["source_file"] = source_name
    return result.drop(columns=["_event_sort_value"])


def standardise_frozen_exact_support_panel(
    frame: pd.DataFrame,
    source_name: str,
) -> pd.DataFrame:
    # Convert the frozen Phase 20 exact-support panel to canonical long form.
    #
    # market_source_probability is the raw market value used by binary
    # scores. market_probability is the within-book normalised market value
    # used by categorical scores.
    required = {
        "target_date",
        "decision_rule",
        "gp_probability",
        "market_source_probability",
        "market_probability",
        "realised_yes",
        "contract_rank",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"{source_name}: missing frozen exact-support columns {missing}; "
            f"columns={list(frame.columns)}"
        )

    event_label = (
        frame["event_key"]
        if "event_key" in frame.columns
        else frame["event_label"]
    )
    lower_bound = (
        frame["lower_bound"]
        if "lower_bound" in frame.columns
        else pd.Series(np.nan, index=frame.index)
    )
    upper_bound = (
        frame["upper_bound"]
        if "upper_bound" in frame.columns
        else pd.Series(np.nan, index=frame.index)
    )

    common = pd.DataFrame({
        "target_date": pd.to_datetime(
            frame["target_date"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d"),
        "decision_rule": frame["decision_rule"].map(normalise_rule),
        "outcome": pd.to_numeric(
            frame["realised_yes"],
            errors="coerce",
        ),
        "event_order_source": pd.to_numeric(
            frame["contract_rank"],
            errors="coerce",
        ),
        "event_label": event_label,
        "event_lower_bound_c": pd.to_numeric(
            lower_bound,
            errors="coerce",
        ),
        "event_upper_bound_c": pd.to_numeric(
            upper_bound,
            errors="coerce",
        ),
        "market_record_timestamp_utc": np.nan,
        "decision_timestamp_utc": np.nan,
    })

    matern = common.copy()
    matern["model"] = "matern"
    matern["probability_raw"] = pd.to_numeric(
        frame["gp_probability"],
        errors="coerce",
    )
    matern["probability_source_normalised"] = matern[
        "probability_raw"
    ]

    market = common.copy()
    market["model"] = "market"
    market["probability_raw"] = pd.to_numeric(
        frame["market_source_probability"],
        errors="coerce",
    )
    market["probability_source_normalised"] = pd.to_numeric(
        frame["market_probability"],
        errors="coerce",
    )

    result = pd.concat([matern, market], ignore_index=True)
    result["event_order"] = pd.to_numeric(
        result["event_order_source"],
        errors="coerce",
    ).astype("Int64")
    result["source_file"] = source_name

    invalid = (
        result["target_date"].isna()
        | ~result["decision_rule"].isin(RULE_ORDER)
        | result["event_order"].isna()
        | result["probability_raw"].isna()
        | result["outcome"].isna()
    )
    if invalid.any():
        sample = result.loc[invalid].head(5).to_dict("records")
        raise ValueError(
            f"{source_name}: invalid canonical rows={int(invalid.sum())}; "
            f"sample={sample}"
        )

    return result


def standardise_exact_keys(frame: pd.DataFrame) -> pd.DataFrame:
    date_col = resolve_column(
        frame,
        ["target_date", "settlement_date", "trade_date", "date"],
        required=True,
    )
    rule_col = resolve_column(
        frame,
        ["decision_rule", "rule", "decision_time_rule"],
        required=True,
    )
    result = pd.DataFrame(
        {
            "target_date": pd.to_datetime(
                frame[date_col], errors="coerce"
            ).dt.strftime("%Y-%m-%d"),
            "decision_rule": frame[rule_col].map(normalise_rule),
        }
    )
    return result.drop_duplicates().sort_values(
        ["target_date", "decision_rule"]
    )


def derive_cutoff_utc(
    target_dates: pd.Series,
    rules: pd.Series,
) -> pd.Series:
    target = pd.to_datetime(target_dates, errors="coerce")
    hour_offset = rules.map(
        {
            "24h_prior": -24.0,
            "12h_prior": -12.0,
            "6h_prior": -6.0,
            "event_day_open": 0.0,
        }
    )
    local_midnight = target.dt.tz_localize(
        "Asia/Hong_Kong",
        ambiguous="NaT",
        nonexistent="NaT",
    )
    local_cutoff = local_midnight + pd.to_timedelta(
        hour_offset, unit="h"
    )
    return local_cutoff.dt.tz_convert("UTC")


def assign_split(target_dates: pd.Series) -> pd.Series:
    dates = pd.to_datetime(target_dates, errors="coerce")
    return np.where(
        dates.dt.month == 6,
        "june_external",
        "development",
    )


def prepare_canonical_panel(
    existing: pd.DataFrame,
    reconstructed: pd.DataFrame,
    exact_keys: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    combined = pd.concat([existing, reconstructed], ignore_index=True)
    combined = combined.loc[
        combined["model"].isin(config["expected"]["required_models"])
    ].copy()
    combined = combined.merge(
        exact_keys.assign(_exact_support=True),
        on=["target_date", "decision_rule"],
        how="inner",
        validate="many_to_one",
    )

    key = ["target_date", "decision_rule", "model", "event_order"]
    duplicates = combined.duplicated(key, keep=False)
    duplicate_audit_rows: list[dict[str, Any]] = []
    if duplicates.any():
        for values, group in combined.loc[duplicates].groupby(key):
            probabilities = group["probability_raw"].dropna().to_numpy()
            consistent = (
                len(probabilities) > 0
                and float(np.max(probabilities) - np.min(probabilities))
                <= float(config["numerical_tolerance"])
            )
            duplicate_audit_rows.append(
                {
                    "target_date": values[0],
                    "decision_rule": values[1],
                    "model": values[2],
                    "event_order": values[3],
                    "rows": len(group),
                    "probability_range": (
                        float(np.max(probabilities) - np.min(probabilities))
                        if len(probabilities) else np.nan
                    ),
                    "consistent": consistent,
                    "sources": "|".join(
                        sorted(group["source_file"].astype(str).unique())
                    ),
                }
            )
        inconsistent = [
            row for row in duplicate_audit_rows if not row["consistent"]
        ]
        if inconsistent:
            raise ValueError(
                f"Inconsistent duplicate event probabilities: "
                f"{inconsistent[:5]}"
            )
        source_priority = {
            "phase1_canonical_existing_event_books.csv.gz": 0,
            "phase1_reconstructed_raw_static_event_books.csv.gz": 1,
        }
        combined["_source_priority"] = combined["source_file"].map(
            source_priority
        ).fillna(9)
        combined = (
            combined.sort_values("_source_priority")
            .drop_duplicates(key, keep="first")
            .drop(columns="_source_priority")
        )

    outcome_reference = (
        combined.loc[combined["outcome"].notna(), [
            "target_date",
            "decision_rule",
            "event_order",
            "outcome",
        ]]
        .groupby(
            ["target_date", "decision_rule", "event_order"],
            as_index=False,
        )["outcome"]
        .mean()
    )
    combined = combined.drop(columns=["outcome"]).merge(
        outcome_reference,
        on=["target_date", "decision_rule", "event_order"],
        how="left",
        validate="many_to_one",
    )

    timestamp_reference = (
        combined.loc[
            combined["market_record_timestamp_utc"].notna(),
            [
                "target_date",
                "decision_rule",
                "market_record_timestamp_utc",
            ],
        ]
        .drop_duplicates(["target_date", "decision_rule"])
    )
    combined = combined.drop(
        columns=["market_record_timestamp_utc"]
    ).merge(
        timestamp_reference,
        on=["target_date", "decision_rule"],
        how="left",
        validate="many_to_one",
    )

    decision_reference = (
        combined.loc[
            combined["decision_timestamp_utc"].notna(),
            ["target_date", "decision_rule", "decision_timestamp_utc"],
        ]
        .drop_duplicates(["target_date", "decision_rule"])
    )
    combined = combined.drop(columns=["decision_timestamp_utc"]).merge(
        decision_reference,
        on=["target_date", "decision_rule"],
        how="left",
        validate="many_to_one",
    )

    combined["probability_raw"] = pd.to_numeric(
        combined["probability_raw"], errors="coerce"
    )
    combined["outcome"] = pd.to_numeric(
        combined["outcome"], errors="coerce"
    )
    combined["book_probability_sum_raw"] = (
        combined.groupby(
            ["target_date", "decision_rule", "model"]
        )["probability_raw"]
        .transform("sum")
    )
    combined["probability_normalised"] = (
        combined["probability_raw"]
        / combined["book_probability_sum_raw"]
    )
    combined["split"] = assign_split(combined["target_date"])
    combined["rule_order"] = combined["decision_rule"].map(
        {rule: index for index, rule in enumerate(RULE_ORDER)}
    )
    combined["model_order"] = combined["model"].map(
        {model: index for index, model in enumerate(MODEL_ORDER)}
    )
    combined = combined.sort_values(
        [
            "target_date",
            "rule_order",
            "model_order",
            "event_order",
        ]
    ).reset_index(drop=True)
    return combined, pd.DataFrame(duplicate_audit_rows)


def validate_panel(
    panel: pd.DataFrame,
    exact_keys: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    expected = config["expected"]
    tolerance = float(config["numerical_tolerance"])
    checks: list[dict[str, Any]] = []

    def add(check: str, passed: bool, detail: str, critical: bool = True):
        checks.append({
            "check": check,
            "passed": bool(passed),
            "critical": bool(critical),
            "detail": detail,
        })

    add(
        "exact_support_key_count",
        len(exact_keys) == expected["exact_support_books"],
        f"keys={len(exact_keys)}",
    )
    add(
        "exact_support_date_count",
        exact_keys["target_date"].nunique()
        == expected["exact_support_dates"],
        f"dates={exact_keys['target_date'].nunique()}",
    )
    add(
        "required_models_present",
        set(panel["model"].unique())
        == set(expected["required_models"]),
        f"models={sorted(panel['model'].unique())}",
    )

    counts = panel.groupby("model").size().to_dict()
    add(
        "event_rows_per_model",
        all(
            counts.get(model, 0) == expected["event_rows_per_model"]
            for model in expected["required_models"]
        ),
        f"counts={counts}",
    )

    books = panel.groupby(
        ["target_date", "decision_rule", "model"]
    ).agg(
        events=("event_order", "nunique"),
        rows=("event_order", "size"),
        winners=("outcome", "sum"),
        probability_sum_raw=("probability_raw", "sum"),
        probability_sum_normalised=("probability_normalised", "sum"),
    ).reset_index()
    add(
        "events_per_book",
        bool(
            (books["events"] == expected["events_per_book"]).all()
            and (books["rows"] == expected["events_per_book"]).all()
        ),
        (
            f"bad_events="
            f"{int((books['events'] != expected['events_per_book']).sum())}; "
            f"bad_rows="
            f"{int((books['rows'] != expected['events_per_book']).sum())}"
        ),
    )
    add(
        "one_winner_per_book",
        bool(np.allclose(books["winners"], 1.0, atol=tolerance)),
        (
            f"minimum={books['winners'].min():.12f}; "
            f"maximum={books['winners'].max():.12f}"
        ),
    )
    add(
        "probabilities_finite_bounded",
        bool(
            np.isfinite(panel["probability_raw"]).all()
            and (panel["probability_raw"] >= -tolerance).all()
            and (panel["probability_raw"] <= 1.0 + tolerance).all()
        ),
        (
            f"minimum={panel['probability_raw'].min():.12f}; "
            f"maximum={panel['probability_raw'].max():.12f}"
        ),
    )
    add(
        "normalised_books_sum_to_one",
        bool(
            np.allclose(
                books["probability_sum_normalised"],
                1.0,
                atol=tolerance,
            )
        ),
        (
            f"maximum_error="
            f"{float((books['probability_sum_normalised'] - 1.0).abs().max()):.3e}"
        ),
    )
    model_books = (
        books.groupby("model")[["target_date", "decision_rule"]]
        .size()
        .to_dict()
    )
    add(
        "books_per_model",
        all(
            model_books.get(model, 0) == expected["exact_support_books"]
            for model in expected["required_models"]
        ),
        f"counts={model_books}",
    )

    split_dates = (
        panel[["target_date", "split"]]
        .drop_duplicates()
        .groupby("split")
        .size()
        .to_dict()
    )
    add(
        "development_date_count",
        split_dates.get("development", 0)
        == expected["development_dates"],
        f"counts={split_dates}",
    )
    add(
        "june_external_date_count",
        split_dates.get("june_external", 0)
        == expected["june_external_dates"],
        f"counts={split_dates}",
    )

    duplicate_keys = int(
        panel.duplicated(
            ["target_date", "decision_rule", "model", "event_order"]
        ).sum()
    )
    add(
        "unique_event_keys",
        duplicate_keys == 0,
        f"duplicates={duplicate_keys}",
    )
    return pd.DataFrame(checks)


def score_books(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    eps = float(config["probability_clip"])
    rows: list[dict[str, Any]] = []
    for keys, group in panel.groupby(
        ["target_date", "decision_rule", "model", "split"],
        sort=False,
    ):
        p_raw = group["probability_raw"].to_numpy(dtype=float)
        p_cat = group["probability_normalised"].to_numpy(dtype=float)
        y = group["outcome"].to_numpy(dtype=float)
        p_binary = np.clip(p_raw, eps, 1.0 - eps)
        p_categorical = np.clip(p_cat, eps, 1.0)
        winner_probability_raw = float(np.sum(y * p_raw))
        winner_probability_cat = float(np.sum(y * p_cat))
        binary_brier = float(np.mean((p_raw - y) ** 2))
        binary_log = float(
            np.mean(
                -(
                    y * np.log(p_binary)
                    + (1.0 - y) * np.log(1.0 - p_binary)
                )
            )
        )
        categorical_log = float(-np.sum(y * np.log(p_categorical)))
        multiclass_brier = float(np.sum((p_cat - y) ** 2))
        expected_rank = float(
            np.sum(
                group["event_order"].to_numpy(dtype=float) * p_cat
            )
        )
        modal_rank = int(
            group.loc[
                group["probability_normalised"].idxmax(),
                "event_order",
            ]
        )
        realised_rank = int(
            group.loc[group["outcome"].idxmax(), "event_order"]
        )
        rows.append({
            "target_date": keys[0],
            "decision_rule": keys[1],
            "model": keys[2],
            "split": keys[3],
            "events": len(group),
            "probability_sum_raw": float(np.sum(p_raw)),
            "binary_brier": binary_brier,
            "binary_log": binary_log,
            "categorical_log": categorical_log,
            "multiclass_brier": multiclass_brier,
            "realised_event_probability_raw": winner_probability_raw,
            "realised_event_probability_normalised": winner_probability_cat,
            "expected_event_rank": expected_rank,
            "modal_event_rank": modal_rank,
            "realised_event_rank": realised_rank,
        })
    return pd.DataFrame(rows)


def aggregate_date_scores(
    book_scores: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    metrics = config["score_metrics"]
    named = {
        metric: pd.NamedAgg(column=metric, aggfunc="mean")
        for metric in metrics
    }
    named.update({
        "books": pd.NamedAgg(column="decision_rule", aggfunc="nunique"),
        "mean_realised_event_probability_normalised": pd.NamedAgg(
            column="realised_event_probability_normalised",
            aggfunc="mean",
        ),
    })
    return (
        book_scores.groupby(
            ["target_date", "model", "split"],
            as_index=False,
        )
        .agg(**named)
        .sort_values(["target_date", "model"])
    )


def build_score_comparison_panel(
    date_scores: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    metrics = config["score_metrics"]
    market = date_scores.loc[
        date_scores["model"] == "market",
        ["target_date", "split", *metrics],
    ].copy()
    market = market.rename(
        columns={metric: f"market_{metric}" for metric in metrics}
    )
    rows: list[pd.DataFrame] = []
    for model in ["raw", "static", "matern"]:
        frame = date_scores.loc[
            date_scores["model"] == model,
            ["target_date", "split", *metrics],
        ].copy()
        frame = frame.merge(
            market,
            on=["target_date", "split"],
            how="inner",
            validate="one_to_one",
        )
        frame["model"] = model
        for metric in metrics:
            frame[f"model_minus_market_{metric}"] = (
                frame[metric] - frame[f"market_{metric}"]
            )
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def ordinary_indices(
    n: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    return rng.integers(0, n, size=(replications, n), dtype=np.int64)


def moving_block_indices(
    n: int,
    block_length: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if n <= 0 or block_length <= 0:
        raise ValueError("n and block_length must be positive")
    blocks_needed = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(replications, blocks_needed))
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % n
    return indices.reshape(replications, -1)[:, :n]


def percentile_interval(
    values: np.ndarray,
    confidence: float,
) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    alpha = 1.0 - confidence
    return (
        float(np.quantile(finite, alpha / 2.0)),
        float(np.quantile(finite, 1.0 - alpha / 2.0)),
    )


def bootstrap_mean_differences(
    frame: pd.DataFrame,
    value_columns: Sequence[str],
    config: Mapping[str, Any],
    scope_type: str,
    scope_value: str,
    model: str,
    split: str,
    seed_offset: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = frame.sort_values("target_date").reset_index(drop=True)
    values = frame[list(value_columns)].to_numpy(dtype=float)
    n, k = values.shape
    reps = int(config["bootstrap"]["replications"])
    confidence = float(config["bootstrap"]["confidence_level"])
    chunk_size = int(config["bootstrap"]["chunk_size"])
    base_seed = int(config["bootstrap"]["seed"]) + seed_offset
    methods: list[tuple[str, int | None]] = [("ordinary_date", None)]
    methods.extend(
        ("circular_moving_block", int(block))
        for block in config["bootstrap"]["moving_block_lengths"]
        if n >= max(3, int(block))
    )
    point = values.mean(axis=0)
    centred = values - point[None, :]
    interval_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []

    for method_index, (method, block) in enumerate(methods):
        local_seed = base_seed + method_index * 100
        rng = np.random.default_rng(local_seed)
        parts: list[np.ndarray] = []
        null_parts: list[np.ndarray] = []
        completed = 0
        while completed < reps:
            current = min(chunk_size, reps - completed)
            if method == "ordinary_date":
                indices = ordinary_indices(n, current, rng)
            else:
                assert block is not None
                indices = moving_block_indices(n, block, current, rng)
            parts.append(values[indices, :].mean(axis=1))
            null_parts.append(centred[indices, :].mean(axis=1))
            completed += current
        distribution = np.concatenate(parts, axis=0)
        null_distribution = np.concatenate(null_parts, axis=0)
        for column_index, column in enumerate(value_columns):
            metric = column.replace("model_minus_market_", "")
            lower, upper = percentile_interval(
                distribution[:, column_index],
                confidence,
            )
            p_value = float(
                (
                    1
                    + np.sum(
                        np.abs(null_distribution[:, column_index])
                        >= abs(point[column_index])
                    )
                )
                / (reps + 1)
            )
            interval_rows.append({
                "scope_type": scope_type,
                "scope_value": scope_value,
                "split": split,
                "model": model,
                "benchmark": "market",
                "metric": metric,
                "dates": n,
                "point_model_minus_market": float(point[column_index]),
                "bootstrap_method": method,
                "block_length_days": block,
                "bootstrap_lower_95": lower,
                "bootstrap_upper_95": upper,
                "bootstrap_replications": reps,
                "seed": local_seed,
                "bootstrap_unit": "settlement_date",
            })
            test_rows.append({
                "scope_type": scope_type,
                "scope_value": scope_value,
                "split": split,
                "model": model,
                "benchmark": "market",
                "metric": metric,
                "dates": n,
                "null_hypothesis": "mean_model_minus_market_equals_zero",
                "observed_mean": float(point[column_index]),
                "bootstrap_method": method,
                "block_length_days": block,
                "two_sided_centred_bootstrap_p_value": p_value,
                "bootstrap_replications": reps,
                "seed": local_seed,
            })
    return pd.DataFrame(interval_rows), pd.DataFrame(test_rows)


def score_inference(
    comparison_panel: pd.DataFrame,
    book_scores: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = config["score_metrics"]
    value_columns = [
        f"model_minus_market_{metric}" for metric in metrics
    ]
    interval_frames: list[pd.DataFrame] = []
    test_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    seed_counter = 0

    all_frame = comparison_panel.copy()
    all_frame["split_for_analysis"] = "all_exact_support"
    expanded = pd.concat(
        [
            comparison_panel.assign(
                split_for_analysis=comparison_panel["split"]
            ),
            all_frame,
        ],
        ignore_index=True,
    )
    for (model, split), group in expanded.groupby(
        ["model", "split_for_analysis"],
        sort=False,
    ):
        for metric, column in zip(metrics, value_columns):
            values = group[column].to_numpy(dtype=float)
            summary_rows.append({
                "scope_type": "overall",
                "scope_value": "all_rules",
                "split": split,
                "model": model,
                "benchmark": "market",
                "metric": metric,
                "dates": len(group),
                "mean_model_minus_market": float(np.mean(values)),
                "median_model_minus_market": float(np.median(values)),
                "model_better_fraction": float(np.mean(values < 0.0)),
                "market_better_fraction": float(np.mean(values > 0.0)),
            })
        intervals, tests = bootstrap_mean_differences(
            group,
            value_columns,
            config,
            "overall",
            "all_rules",
            model,
            split,
            seed_counter,
        )
        interval_frames.append(intervals)
        test_frames.append(tests)
        seed_counter += 1000

    market_books = book_scores.loc[
        book_scores["model"] == "market"
    ]
    for model in ["raw", "static", "matern"]:
        model_books = book_scores.loc[
            book_scores["model"] == model
        ]
        merged = model_books.merge(
            market_books[
                ["target_date", "decision_rule", "split", *metrics]
            ],
            on=["target_date", "decision_rule", "split"],
            how="inner",
            validate="one_to_one",
            suffixes=("_model", "_market"),
        )
        for metric in metrics:
            merged[f"model_minus_market_{metric}"] = (
                merged[f"{metric}_model"]
                - merged[f"{metric}_market"]
            )
        for rule in RULE_ORDER:
            rule_frame = merged.loc[
                merged["decision_rule"] == rule
            ].copy()
            for split in [
                "development",
                "june_external",
                "all_exact_support",
            ]:
                subset = (
                    rule_frame
                    if split == "all_exact_support"
                    else rule_frame.loc[rule_frame["split"] == split]
                )
                if subset.empty:
                    continue
                for metric, column in zip(metrics, value_columns):
                    values = subset[column].to_numpy(dtype=float)
                    summary_rows.append({
                        "scope_type": "decision_rule",
                        "scope_value": rule,
                        "split": split,
                        "model": model,
                        "benchmark": "market",
                        "metric": metric,
                        "dates": len(subset),
                        "mean_model_minus_market": float(np.mean(values)),
                        "median_model_minus_market": float(np.median(values)),
                        "model_better_fraction": float(np.mean(values < 0.0)),
                        "market_better_fraction": float(np.mean(values > 0.0)),
                    })
                intervals, tests = bootstrap_mean_differences(
                    subset,
                    value_columns,
                    config,
                    "decision_rule",
                    rule,
                    model,
                    split,
                    seed_counter,
                )
                interval_frames.append(intervals)
                test_frames.append(tests)
                seed_counter += 1000

    return (
        pd.DataFrame(summary_rows),
        pd.concat(interval_frames, ignore_index=True),
        pd.concat(test_frames, ignore_index=True),
    )


def build_disagreement_panel(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    selected = panel.loc[
        panel["model"].isin(["matern", "market"])
    ].copy()
    pivot = selected.pivot(
        index=[
            "target_date",
            "decision_rule",
            "split",
            "event_order",
            "outcome",
        ],
        columns="model",
        values="probability_normalised",
    ).reset_index()
    if pivot[["matern", "market"]].isna().any().any():
        raise ValueError("Incomplete Matérn-market event probability pivot")

    rows: list[dict[str, Any]] = []
    for keys, group in pivot.groupby(
        ["target_date", "decision_rule", "split"],
        sort=False,
    ):
        p_m = group["matern"].to_numpy(dtype=float)
        p_q = group["market"].to_numpy(dtype=float)
        y = group["outcome"].to_numpy(dtype=float)
        ranks = group["event_order"].to_numpy(dtype=float)
        winner = int(np.argmax(y))
        winner_m = float(p_m[winner])
        winner_q = float(p_q[winner])
        winner_term = float((winner_m - 1.0) ** 2 - (winner_q - 1.0) ** 2)
        loser_mask = np.arange(len(y)) != winner
        loser_term = float(
            np.sum(p_m[loser_mask] ** 2 - p_q[loser_mask] ** 2)
        )
        rows.append({
            "target_date": keys[0],
            "decision_rule": keys[1],
            "split": keys[2],
            "total_variation_market_matern": float(
                0.5 * np.sum(np.abs(p_q - p_m))
            ),
            "expected_rank_market_minus_matern": float(
                np.sum(ranks * p_q) - np.sum(ranks * p_m)
            ),
            "modal_disagreement": int(np.argmax(p_q) != np.argmax(p_m)),
            "realised_event_probability_market": winner_q,
            "realised_event_probability_matern": winner_m,
            "realised_event_probability_market_minus_matern": (
                winner_q - winner_m
            ),
            "categorical_log_matern_minus_market": float(
                -np.log(max(winner_m, 1e-12))
                + np.log(max(winner_q, 1e-12))
            ),
            "multiclass_brier_winner_component_matern_minus_market": winner_term,
            "multiclass_brier_nonwinner_component_matern_minus_market": loser_term,
            "multiclass_brier_total_matern_minus_market": winner_term + loser_term,
        })
    return pd.DataFrame(rows)


def bootstrap_generic_metrics(
    frame: pd.DataFrame,
    metrics: Sequence[str],
    config: Mapping[str, Any],
    group_fields: Mapping[str, Any],
    seed_offset: int,
) -> pd.DataFrame:
    frame = frame.sort_values("target_date").reset_index(drop=True)
    values = frame[list(metrics)].to_numpy(dtype=float)
    n = len(frame)
    reps = int(config["bootstrap"]["replications"])
    confidence = float(config["bootstrap"]["confidence_level"])
    chunk_size = int(config["bootstrap"]["chunk_size"])
    methods: list[tuple[str, int | None]] = [("ordinary_date", None)]
    methods.extend(
        ("circular_moving_block", int(block))
        for block in config["bootstrap"]["moving_block_lengths"]
        if n >= max(3, int(block))
    )
    rows: list[dict[str, Any]] = []
    point = values.mean(axis=0)
    for method_index, (method, block) in enumerate(methods):
        local_seed = int(config["bootstrap"]["seed"]) + seed_offset + method_index * 100
        rng = np.random.default_rng(local_seed)
        parts: list[np.ndarray] = []
        completed = 0
        while completed < reps:
            current = min(chunk_size, reps - completed)
            if method == "ordinary_date":
                indices = ordinary_indices(n, current, rng)
            else:
                assert block is not None
                indices = moving_block_indices(n, block, current, rng)
            parts.append(values[indices, :].mean(axis=1))
            completed += current
        distribution = np.concatenate(parts, axis=0)
        for index, metric in enumerate(metrics):
            lower, upper = percentile_interval(
                distribution[:, index], confidence
            )
            rows.append({
                **dict(group_fields),
                "metric": metric,
                "dates": n,
                "point_estimate": float(point[index]),
                "bootstrap_method": method,
                "block_length_days": block,
                "bootstrap_lower_95": lower,
                "bootstrap_upper_95": upper,
                "bootstrap_replications": reps,
                "seed": local_seed,
            })
    return pd.DataFrame(rows)


def disagreement_analysis(
    disagreement: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = [
        "total_variation_market_matern",
        "expected_rank_market_minus_matern",
        "modal_disagreement",
        "realised_event_probability_market_minus_matern",
        "categorical_log_matern_minus_market",
        "multiclass_brier_winner_component_matern_minus_market",
        "multiclass_brier_nonwinner_component_matern_minus_market",
        "multiclass_brier_total_matern_minus_market",
    ]
    summary_rows: list[dict[str, Any]] = []
    interval_frames: list[pd.DataFrame] = []
    seed_counter = 200000

    for split in ["development", "june_external", "all_exact_support"]:
        subset = (
            disagreement
            if split == "all_exact_support"
            else disagreement.loc[disagreement["split"] == split]
        )
        date_level = subset.groupby("target_date", as_index=False)[
            metrics
        ].mean()
        for metric in metrics:
            summary_rows.append({
                "scope_type": "overall",
                "scope_value": "all_rules",
                "split": split,
                "metric": metric,
                "dates": len(date_level),
                "mean": float(date_level[metric].mean()),
                "median": float(date_level[metric].median()),
                "q10": float(date_level[metric].quantile(0.10)),
                "q90": float(date_level[metric].quantile(0.90)),
            })
        interval_frames.append(
            bootstrap_generic_metrics(
                date_level,
                metrics,
                config,
                {
                    "scope_type": "overall",
                    "scope_value": "all_rules",
                    "split": split,
                },
                seed_counter,
            )
        )
        seed_counter += 1000

    for rule in RULE_ORDER:
        rule_frame = disagreement.loc[
            disagreement["decision_rule"] == rule
        ]
        for split in ["development", "june_external", "all_exact_support"]:
            subset = (
                rule_frame
                if split == "all_exact_support"
                else rule_frame.loc[rule_frame["split"] == split]
            )
            if subset.empty:
                continue
            for metric in metrics:
                summary_rows.append({
                    "scope_type": "decision_rule",
                    "scope_value": rule,
                    "split": split,
                    "metric": metric,
                    "dates": len(subset),
                    "mean": float(subset[metric].mean()),
                    "median": float(subset[metric].median()),
                    "q10": float(subset[metric].quantile(0.10)),
                    "q90": float(subset[metric].quantile(0.90)),
                })
            interval_frames.append(
                bootstrap_generic_metrics(
                    subset,
                    metrics,
                    config,
                    {
                        "scope_type": "decision_rule",
                        "scope_value": rule,
                        "split": split,
                    },
                    seed_counter,
                )
            )
            seed_counter += 1000

    return (
        pd.DataFrame(summary_rows),
        pd.concat(interval_frames, ignore_index=True),
    )


def build_transition_panels(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = panel.loc[
        panel["model"].isin(["market", "matern"])
    ].copy()
    pivot = selected.pivot(
        index=[
            "target_date",
            "split",
            "decision_rule",
            "event_order",
            "outcome",
        ],
        columns="model",
        values="probability_normalised",
    ).reset_index()
    event_rows: list[dict[str, Any]] = []
    book_rows: list[dict[str, Any]] = []

    for transition_order, transition in enumerate(
        config["transitions"], start=1
    ):
        early = pivot.loc[
            pivot["decision_rule"] == transition["early_rule"]
        ].copy()
        late = pivot.loc[
            pivot["decision_rule"] == transition["late_rule"]
        ].copy()
        merged = early.merge(
            late,
            on=["target_date", "split", "event_order"],
            how="inner",
            validate="one_to_one",
            suffixes=("_early", "_late"),
        )
        if merged.empty:
            continue
        outcome = merged["outcome_early"].combine_first(
            merged["outcome_late"]
        )
        merged["outcome"] = outcome
        merged["delta_market"] = (
            merged["market_late"] - merged["market_early"]
        )
        merged["delta_matern"] = (
            merged["matern_late"] - merged["matern_early"]
        )
        merged["same_direction_nonzero"] = np.where(
            (np.abs(merged["delta_market"]) > 1e-12)
            & (np.abs(merged["delta_matern"]) > 1e-12),
            np.sign(merged["delta_market"])
            == np.sign(merged["delta_matern"]),
            np.nan,
        )
        merged["transition_order"] = transition_order
        merged["transition"] = transition["transition"]
        merged["transition_family"] = transition["transition_family"]
        merged["early_rule"] = transition["early_rule"]
        merged["late_rule"] = transition["late_rule"]
        event_rows.extend(
            merged[
                [
                    "target_date",
                    "split",
                    "transition_order",
                    "transition",
                    "transition_family",
                    "early_rule",
                    "late_rule",
                    "event_order",
                    "outcome",
                    "market_early",
                    "market_late",
                    "matern_early",
                    "matern_late",
                    "delta_market",
                    "delta_matern",
                    "same_direction_nonzero",
                ]
            ].to_dict("records")
        )

        for keys, group in merged.groupby(
            ["target_date", "split"], sort=False
        ):
            dm = group["delta_market"].to_numpy(dtype=float)
            dg = group["delta_matern"].to_numpy(dtype=float)
            market_early = group["market_early"].to_numpy(dtype=float)
            market_late = group["market_late"].to_numpy(dtype=float)
            matern_late = group["matern_late"].to_numpy(dtype=float)
            y = group["outcome"].to_numpy(dtype=float)
            denominator = float(
                np.sqrt(np.sum(dm ** 2) * np.sum(dg ** 2))
            )
            cosine = (
                float(np.sum(dm * dg) / denominator)
                if denominator > 0 else np.nan
            )
            signs = group["same_direction_nonzero"].dropna().astype(float)
            book_rows.append({
                "target_date": keys[0],
                "split": keys[1],
                "transition_order": transition_order,
                "transition": transition["transition"],
                "transition_family": transition["transition_family"],
                "early_rule": transition["early_rule"],
                "late_rule": transition["late_rule"],
                "events": len(group),
                "market_update_total_variation": float(
                    0.5 * np.sum(np.abs(dm))
                ),
                "matern_update_total_variation": float(
                    0.5 * np.sum(np.abs(dg))
                ),
                "update_dot_product": float(np.sum(dm * dg)),
                "update_cosine_similarity": cosine,
                "event_sign_alignment_fraction": (
                    float(signs.mean()) if len(signs) else np.nan
                ),
                "realised_probability_change_market": float(
                    np.sum(y * dm)
                ),
                "realised_probability_change_matern": float(
                    np.sum(y * dg)
                ),
                "distance_to_updated_matern_before": float(
                    0.5 * np.sum(np.abs(market_early - matern_late))
                ),
                "distance_to_updated_matern_after": float(
                    0.5 * np.sum(np.abs(market_late - matern_late))
                ),
                "market_movement_towards_updated_matern": float(
                    0.5 * np.sum(np.abs(market_early - matern_late))
                    - 0.5 * np.sum(np.abs(market_late - matern_late))
                ),
            })
    return pd.DataFrame(event_rows), pd.DataFrame(book_rows)


def cluster_robust_regression(
    x: np.ndarray,
    y: np.ndarray,
    clusters: Sequence[Any],
) -> dict[str, float]:
    x_array = np.asarray(x, dtype=float)
    y_array = np.asarray(y, dtype=float)
    cluster_array = np.asarray(clusters)
    mask = np.isfinite(x_array) & np.isfinite(y_array)
    x_array = x_array[mask]
    y_array = y_array[mask]
    cluster_array = cluster_array[mask]
    design = np.column_stack([np.ones(len(x_array)), x_array])
    xtx_inv = np.linalg.pinv(design.T @ design)
    beta = xtx_inv @ design.T @ y_array
    residuals = y_array - design @ beta
    meat = np.zeros((2, 2), dtype=float)
    unique_clusters = pd.unique(cluster_array)
    for cluster in unique_clusters:
        index = cluster_array == cluster
        score = design[index].T @ residuals[index]
        meat += np.outer(score, score)
    n = len(y_array)
    k = design.shape[1]
    g = len(unique_clusters)
    correction = (
        (g / (g - 1.0)) * ((n - 1.0) / (n - k))
        if g > 1 and n > k else 1.0
    )
    covariance = correction * xtx_inv @ meat @ xtx_inv
    standard_errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    t_value = (
        float(beta[1] / standard_errors[1])
        if standard_errors[1] > 0 else np.nan
    )
    p_value = (
        float(2.0 * stats.t.sf(abs(t_value), df=max(g - 1, 1)))
        if np.isfinite(t_value) else np.nan
    )
    fitted = design @ beta
    total = float(np.sum((y_array - np.mean(y_array)) ** 2))
    residual_sum = float(np.sum((y_array - fitted) ** 2))
    return {
        "observations": n,
        "date_clusters": g,
        "intercept": float(beta[0]),
        "slope_delta_market_on_delta_matern": float(beta[1]),
        "cluster_robust_slope_standard_error": float(standard_errors[1]),
        "cluster_robust_t_value": t_value,
        "cluster_robust_p_value": p_value,
        "r_squared": float(1.0 - residual_sum / total) if total > 0 else np.nan,
    }


def transition_analysis(
    event_panel: pd.DataFrame,
    book_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = [
        "market_update_total_variation",
        "matern_update_total_variation",
        "update_cosine_similarity",
        "event_sign_alignment_fraction",
        "realised_probability_change_market",
        "realised_probability_change_matern",
        "market_movement_towards_updated_matern",
    ]
    summary_rows: list[dict[str, Any]] = []
    interval_frames: list[pd.DataFrame] = []
    regression_rows: list[dict[str, Any]] = []
    seed_counter = 300000

    for transition in book_panel["transition"].drop_duplicates():
        transition_books = book_panel.loc[
            book_panel["transition"] == transition
        ]
        transition_events = event_panel.loc[
            event_panel["transition"] == transition
        ]
        for split in ["development", "june_external", "all_exact_support"]:
            books = (
                transition_books
                if split == "all_exact_support"
                else transition_books.loc[
                    transition_books["split"] == split
                ]
            )
            events = (
                transition_events
                if split == "all_exact_support"
                else transition_events.loc[
                    transition_events["split"] == split
                ]
            )
            if books.empty or events.empty:
                continue
            for metric in metrics:
                summary_rows.append({
                    "transition": transition,
                    "split": split,
                    "metric": metric,
                    "dates": len(books),
                    "mean": float(books[metric].mean()),
                    "median": float(books[metric].median()),
                    "q10": float(books[metric].quantile(0.10)),
                    "q90": float(books[metric].quantile(0.90)),
                })
            interval_frames.append(
                bootstrap_generic_metrics(
                    books,
                    metrics,
                    config,
                    {
                        "transition": transition,
                        "split": split,
                    },
                    seed_counter,
                )
            )
            seed_counter += 1000
            regression = cluster_robust_regression(
                events["delta_matern"].to_numpy(dtype=float),
                events["delta_market"].to_numpy(dtype=float),
                events["target_date"].astype(str).to_numpy(),
            )
            regression_rows.append({
                "transition": transition,
                "split": split,
                **regression,
                "interpretation": (
                    "Descriptive event-level co-movement with settlement-date "
                    "clustered standard errors; not a causal response estimate."
                ),
            })
    return (
        pd.DataFrame(summary_rows),
        pd.concat(interval_frames, ignore_index=True),
        pd.DataFrame(regression_rows),
    )


def market_age_analysis(
    panel: pd.DataFrame,
    book_scores: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    market = panel.loc[
        panel["model"] == "market",
        [
            "target_date",
            "decision_rule",
            "split",
            "market_record_timestamp_utc",
            "decision_timestamp_utc",
        ],
    ].drop_duplicates(["target_date", "decision_rule"])

    market["market_record_timestamp_utc"] = pd.to_datetime(
        market["market_record_timestamp_utc"],
        errors="coerce",
        utc=True,
    )
    market["decision_timestamp_utc"] = pd.to_datetime(
        market["decision_timestamp_utc"],
        errors="coerce",
        utc=True,
    )
    derived_cutoff = derive_cutoff_utc(
        market["target_date"],
        market["decision_rule"],
    )
    market["decision_timestamp_effective_utc"] = (
        market["decision_timestamp_utc"].combine_first(derived_cutoff)
    )
    market["market_record_age_hours"] = (
        (
            market["decision_timestamp_effective_utc"]
            - market["market_record_timestamp_utc"]
        ).dt.total_seconds()
        / 3600.0
    )
    available = market["market_record_age_hours"].notna()
    market["age_available"] = available
    thresholds = list(
        map(float, config["market_age_stale_threshold_hours"])
    )
    for threshold in thresholds:
        market[f"older_than_{threshold:g}h"] = (
            market["market_record_age_hours"] > threshold
        )

    summary_rows: list[dict[str, Any]] = []
    if available.any():
        for split in ["development", "june_external", "all_exact_support"]:
            split_frame = (
                market
                if split == "all_exact_support"
                else market.loc[market["split"] == split]
            )
            for rule in ["all_rules", *RULE_ORDER]:
                group = (
                    split_frame
                    if rule == "all_rules"
                    else split_frame.loc[
                        split_frame["decision_rule"] == rule
                    ]
                )
                values = group["market_record_age_hours"].dropna()
                if values.empty:
                    continue
                row = {
                    "split": split,
                    "scope": rule,
                    "books": len(group),
                    "books_with_age": len(values),
                    "coverage_fraction": len(values) / len(group),
                    "mean_age_hours": float(values.mean()),
                    "median_age_hours": float(values.median()),
                    "q90_age_hours": float(values.quantile(0.90)),
                    "maximum_age_hours": float(values.max()),
                }
                for threshold in thresholds:
                    row[f"fraction_older_than_{threshold:g}h"] = float(
                        (values > threshold).mean()
                    )
                summary_rows.append(row)

    sensitivity_rows: list[dict[str, Any]] = []
    if available.any():
        market_scores = book_scores.loc[
            book_scores["model"] == "market"
        ].merge(
            market[
                [
                    "target_date",
                    "decision_rule",
                    "market_record_age_hours",
                ]
            ],
            on=["target_date", "decision_rule"],
            how="left",
            validate="one_to_one",
        )
        metrics = config["score_metrics"]
        for threshold in thresholds:
            retained = market_scores.loc[
                market_scores["market_record_age_hours"].notna()
                & (
                    market_scores["market_record_age_hours"]
                    <= threshold
                )
            ]
            for split in [
                "development",
                "june_external",
                "all_exact_support",
            ]:
                group = (
                    retained
                    if split == "all_exact_support"
                    else retained.loc[retained["split"] == split]
                )
                if group.empty:
                    continue
                date_scores = group.groupby("target_date", as_index=False)[
                    metrics
                ].mean()
                for metric in metrics:
                    sensitivity_rows.append({
                        "maximum_record_age_hours": threshold,
                        "split": split,
                        "retained_books": len(group),
                        "retained_dates": len(date_scores),
                        "metric": metric,
                        "market_mean_date_score": float(
                            date_scores[metric].mean()
                        ),
                    })

    status = pd.DataFrame([{
        "market_age_available": bool(available.any()),
        "books": len(market),
        "books_with_age": int(available.sum()),
        "coverage_fraction": float(available.mean()),
        "timestamp_columns_present": bool(
            panel["market_record_timestamp_utc"].notna().any()
        ),
        "decision_cutoff_source": (
            "source timestamp where available; otherwise deterministic rule cutoff"
        ),
    }])
    return market, pd.DataFrame(summary_rows), pd.DataFrame(sensitivity_rows), status


def make_figures(
    score_summary: pd.DataFrame,
    comparison_panel: pd.DataFrame,
    disagreement: pd.DataFrame,
    transition_summary: pd.DataFrame,
    transition_books: pd.DataFrame,
    book_scores: pd.DataFrame,
    market_age: pd.DataFrame,
    output_dir: Path,
    dpi: int,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    registry: list[dict[str, Any]] = []

    # 1. June external score differences.
    june = score_summary.loc[
        (score_summary["scope_type"] == "overall")
        & (score_summary["split"] == "june_external")
        & (score_summary["model"] == "matern")
    ].set_index("metric").reindex(list(METRIC_LABELS))
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    ax.bar(
        [METRIC_LABELS[m] for m in june.index],
        june["mean_model_minus_market"],
    )
    ax.axhline(0.0, linewidth=1)
    ax.set_ylabel("Matérn loss minus market loss")
    ax.set_title("June external exact-support comparison")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    path = output_dir / "phase6_figure_june_score_differences.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main-text candidate: June market advantage under four scores",
    })

    # 2. Paired categorical-log differences.
    data = []
    labels = []
    for model in ["raw", "static", "matern"]:
        for split in ["development", "june_external"]:
            values = comparison_panel.loc[
                (comparison_panel["model"] == model)
                & (comparison_panel["split"] == split),
                "model_minus_market_categorical_log",
            ].to_numpy()
            data.append(values)
            labels.append(f"{model}\n{split}")
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    ax.boxplot(data, labels=labels, showfliers=True)
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_ylabel("Model minus market categorical log loss")
    ax.set_title("Paired settlement-date loss differences")
    fig.tight_layout()
    path = output_dir / "phase6_figure_paired_categorical_log_differences.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Appendix candidate: development versus June loss distributions",
    })

    # 3. Total-variation disagreement by rule.
    tv_data = [
        disagreement.loc[
            disagreement["decision_rule"] == rule,
            "total_variation_market_matern",
        ].to_numpy()
        for rule in RULE_ORDER
    ]
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    ax.boxplot(
        tv_data,
        labels=[RULE_LABELS[r] for r in RULE_ORDER],
        showfliers=True,
    )
    ax.set_ylabel("Total variation distance")
    ax.set_title("Matérn–market probability-book disagreement")
    fig.tight_layout()
    path = output_dir / "phase6_figure_total_variation_by_rule.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: probability-book disagreement",
    })

    # 4. Realised-event probability scatter.
    fig, ax = plt.subplots(figsize=(6.3, 6.0))
    ax.scatter(
        disagreement["realised_event_probability_matern"],
        disagreement["realised_event_probability_market"],
        s=14,
        alpha=0.45,
    )
    ax.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", linewidth=1)
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("Matérn realised-event probability")
    ax.set_ylabel("Market realised-event probability")
    ax.set_title("Probability assigned to the realised event")
    fig.tight_layout()
    path = output_dir / "phase6_figure_realised_probability_scatter.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: source of categorical-score difference",
    })

    # 5. Expected-rank shift through time.
    rank = (
        disagreement.groupby(["target_date", "split"], as_index=False)[
            "expected_rank_market_minus_matern"
        ].mean()
        .sort_values("target_date")
    )
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.plot(
        pd.to_datetime(rank["target_date"]),
        rank["expected_rank_market_minus_matern"],
        marker="o",
        markersize=3,
        linewidth=1,
    )
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Settlement date")
    ax.set_ylabel("Market expected rank minus Matérn expected rank")
    ax.set_title("Direction of market–model disagreement")
    fig.tight_layout()
    path = output_dir / "phase6_figure_expected_rank_shift_over_time.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Appendix candidate: market probability shifts towards warmer events",
    })

    # 6. Market movement towards updated Matérn.
    movement = transition_summary.loc[
        (transition_summary["split"] == "all_exact_support")
        & (
            transition_summary["metric"]
            == "market_movement_towards_updated_matern"
        )
    ].copy()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.bar(
        movement["transition"],
        movement["mean"],
    )
    ax.axhline(0.0, linewidth=1)
    ax.set_ylabel("Reduction in TV distance to updated Matérn")
    ax.set_title("Market movement relative to forecast revision")
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    path = output_dir / "phase6_figure_market_movement_towards_update.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: descriptive market-update alignment",
    })

    # 7. Market raw probability sum or record age.
    age_values = market_age["market_record_age_hours"].dropna()
    if not age_values.empty:
        age_data = [
            market_age.loc[
                market_age["decision_rule"] == rule,
                "market_record_age_hours",
            ].dropna().to_numpy()
            for rule in RULE_ORDER
        ]
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        ax.boxplot(
            age_data,
            labels=[RULE_LABELS[r] for r in RULE_ORDER],
            showfliers=True,
        )
        ax.set_ylabel("Selected market-record age (hours)")
        ax.set_title("Market-record freshness by decision rule")
        filename = "phase6_figure_market_record_age.pdf"
        purpose = "Appendix candidate: selected-record freshness"
    else:
        market_books = book_scores.loc[
            book_scores["model"] == "market"
        ]
        data = [
            market_books.loc[
                market_books["decision_rule"] == rule,
                "probability_sum_raw",
            ].to_numpy()
            for rule in RULE_ORDER
        ]
        fig, ax = plt.subplots(figsize=(8.2, 5.0))
        ax.boxplot(
            data,
            labels=[RULE_LABELS[r] for r in RULE_ORDER],
            showfliers=True,
        )
        ax.axhline(1.0, linestyle="--", linewidth=1)
        ax.set_ylabel("Raw market probability sum")
        ax.set_title("Market-book overround and underround")
        filename = "phase6_figure_market_probability_sum.pdf"
        purpose = "Appendix candidate: raw market-book normalisation"
    fig.tight_layout()
    path = output_dir / filename
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    registry.append({"figure": path.name, "purpose": purpose})

    return pd.DataFrame(registry)


def thesis_candidate_summary(
    score_summary: pd.DataFrame,
    score_intervals: pd.DataFrame,
    disagreement_summary: pd.DataFrame,
    transition_summary: pd.DataFrame,
    market_age_status: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric in METRIC_LABELS:
        point = score_summary.loc[
            (score_summary["scope_type"] == "overall")
            & (score_summary["split"] == "june_external")
            & (score_summary["model"] == "matern")
            & (score_summary["metric"] == metric)
        ].iloc[0]
        interval = score_intervals.loc[
            (score_intervals["scope_type"] == "overall")
            & (score_intervals["split"] == "june_external")
            & (score_intervals["model"] == "matern")
            & (score_intervals["metric"] == metric)
            & (
                score_intervals["bootstrap_method"]
                == "ordinary_date"
            )
        ].iloc[0]
        rows.append({
            "candidate_id": f"P6_JUNE_{metric.upper()}",
            "quantity": f"June Matérn minus market {METRIC_LABELS[metric]}",
            "point_estimate": point["mean_model_minus_market"],
            "lower_95": interval["bootstrap_lower_95"],
            "upper_95": interval["bootstrap_upper_95"],
            "preferred_location": "Results exact-support market comparison",
        })

    for split in ["development", "june_external"]:
        for metric in [
            "total_variation_market_matern",
            "expected_rank_market_minus_matern",
            "realised_event_probability_market_minus_matern",
        ]:
            point = disagreement_summary.loc[
                (disagreement_summary["scope_type"] == "overall")
                & (disagreement_summary["split"] == split)
                & (disagreement_summary["metric"] == metric)
            ].iloc[0]
            rows.append({
                "candidate_id": f"P6_{split.upper()}_{metric.upper()}",
                "quantity": f"{split} {metric}",
                "point_estimate": point["mean"],
                "preferred_location": "Results disagreement interpretation",
            })

    movement = transition_summary.loc[
        (transition_summary["split"] == "all_exact_support")
        & (
            transition_summary["metric"]
            == "market_movement_towards_updated_matern"
        )
    ]
    for _, row in movement.iterrows():
        rows.append({
            "candidate_id": f"P6_MOVE_{str(row['transition']).upper()}",
            "quantity": (
                f"{row['transition']} mean market movement towards "
                "updated Matérn"
            ),
            "point_estimate": row["mean"],
            "preferred_location": "Appendix or discussion",
        })

    rows.append({
        "candidate_id": "P6_MARKET_AGE_STATUS",
        "quantity": "market-record age coverage fraction",
        "point_estimate": market_age_status[
            "coverage_fraction"
        ].iloc[0],
        "preferred_location": "Reproducibility register",
    })
    return pd.DataFrame(rows)


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    score_summary: pd.DataFrame,
    score_intervals: pd.DataFrame,
    disagreement_summary: pd.DataFrame,
    transition_summary: pd.DataFrame,
    regressions: pd.DataFrame,
    market_age_summary: pd.DataFrame,
    config: Mapping[str, Any],
) -> None:
    failures = checks.loc[
        bool_series(checks["critical"])
        & ~bool_series(checks["passed"])
    ]
    status = "PASSED" if failures.empty else "FAILED"
    lines = [
        "# Phase 6 — Market Comparison and Information Content",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"## Overall status: **{status}**",
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(dict(provenance), indent=2, sort_keys=True),
        "```",
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Interpretation boundary",
        "",
        config["interpretation_boundary"],
        "",
        "## June external Matérn-versus-market comparison",
        "",
    ]

    for metric in config["score_metrics"]:
        point = score_summary.loc[
            (score_summary["scope_type"] == "overall")
            & (score_summary["split"] == "june_external")
            & (score_summary["model"] == "matern")
            & (score_summary["metric"] == metric)
        ].iloc[0]
        ordinary = score_intervals.loc[
            (score_intervals["scope_type"] == "overall")
            & (score_intervals["split"] == "june_external")
            & (score_intervals["model"] == "matern")
            & (score_intervals["metric"] == metric)
            & (
                score_intervals["bootstrap_method"]
                == "ordinary_date"
            )
        ].iloc[0]
        lines.append(
            f"- **{METRIC_LABELS[metric]}:** model minus market "
            f"{point['mean_model_minus_market']:.6f}; 95% date-bootstrap "
            f"interval [{ordinary['bootstrap_lower_95']:.6f}, "
            f"{ordinary['bootstrap_upper_95']:.6f}]."
        )

    lines.extend([
        "",
        "Positive differences mean that Polymarket had lower realised loss. "
        "The comparison is restricted to identical settlement dates, decision "
        "rules and eleven-event books.",
        "",
        "## Development versus external interpretation",
        "",
        score_summary.loc[
            (score_summary["scope_type"] == "overall")
            & (score_summary["model"] == "matern")
        ][
            [
                "split",
                "metric",
                "dates",
                "mean_model_minus_market",
                "model_better_fraction",
                "market_better_fraction",
            ]
        ].to_markdown(index=False),
        "",
        "## Probability-book disagreement",
        "",
        disagreement_summary.loc[
            (disagreement_summary["scope_type"] == "overall")
            & (
                disagreement_summary["metric"].isin([
                    "total_variation_market_matern",
                    "expected_rank_market_minus_matern",
                    "modal_disagreement",
                    "realised_event_probability_market_minus_matern",
                ])
            )
        ][
            ["split", "metric", "dates", "mean", "median", "q10", "q90"]
        ].to_markdown(index=False),
        "",
        "A positive expected-rank shift means that the market places relatively "
        "more probability on warmer-ranked events than the selected Matérn law. "
        "A positive realised-event probability difference means that the market "
        "assigns more probability to the event that ultimately settles Yes.",
        "",
        "## Forecast revisions and market movement",
        "",
        transition_summary.loc[
            (transition_summary["split"] == "all_exact_support")
            & (
                transition_summary["metric"].isin([
                    "market_update_total_variation",
                    "matern_update_total_variation",
                    "update_cosine_similarity",
                    "market_movement_towards_updated_matern",
                ])
            )
        ][
            ["transition", "metric", "dates", "mean", "median", "q10", "q90"]
        ].to_markdown(index=False),
        "",
        regressions.loc[
            regressions["split"] == "all_exact_support"
        ][
            [
                "transition",
                "observations",
                "date_clusters",
                "slope_delta_market_on_delta_matern",
                "cluster_robust_slope_standard_error",
                "cluster_robust_p_value",
                "r_squared",
            ]
        ].to_markdown(index=False),
        "",
        "These regressions describe co-movement. Forecast cycle, lead time and "
        "other public information change jointly, so the slope is not a causal "
        "market-response coefficient.",
        "",
        "## Market-record age",
        "",
    ])
    if market_age_summary.empty:
        lines.append(
            "Selected market-record timestamps were not recoverable from the "
            "canonical book panel. The missing summary is registered explicitly."
        )
    else:
        lines.append(market_age_summary.to_markdown(index=False))

    lines.extend([
        "",
        "## Thesis use",
        "",
        "- Main text: June external Matérn-versus-market score differences and intervals.",
        "- Main text: one compact disagreement table explaining the realised-event probability gap.",
        "- Discussion or appendix: transition co-movement and market movement towards the updated model.",
        "- Appendix: full rule-level score matrix, moving-block intervals, score decomposition and market-book normalisation.",
        "- Do not say that the market is efficient, that it causally absorbs the GP forecast, or that lower realised loss guarantees tradable profit.",
        "",
    ])
    (out / "phase6_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    records: list[dict[str, Any]] = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase6_manifest.json",
            "phase6_review_bundle.zip",
        }:
            records.append({
                "relative_path": path.relative_to(out).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    (out / "phase6_manifest.json").write_text(
        json.dumps({
            "phase": "phase6_market_information_content",
            "generated_utc": utc_now(),
            "provenance": dict(provenance),
            "files": records,
        }, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase6_review_bundle.zip"
    with zipfile.ZipFile(
        bundle,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                archive.write(
                    path,
                    path.relative_to(out).as_posix(),
                )


def self_test() -> None:
    assert normalise_model("Matérn-3/2 GP") == "matern"
    assert normalise_model("Polymarket") == "market"
    assert normalise_rule("event day open") == "event_day_open"
    assert normalise_rule("24h prior") == "24h_prior"

    rng = np.random.default_rng(123)
    assert ordinary_indices(20, 7, rng).shape == (7, 20)
    rng = np.random.default_rng(123)
    moving = moving_block_indices(20, 5, 7, rng)
    assert moving.shape == (7, 20)
    assert moving.min() >= 0 and moving.max() < 20

    x = np.repeat(np.arange(10, dtype=float), 2)
    y = 1.0 + 0.5 * x
    clusters = np.repeat(np.arange(10), 2)
    regression = cluster_robust_regression(x, y, clusters)
    assert abs(regression["slope_delta_market_on_delta_matern"] - 0.5) < 1e-12

    long_without_normalised = pd.DataFrame({
        "target_date": ["2026-06-01"] * 11,
        "decision_rule": ["event_day_open"] * 11,
        "model": ["market"] * 11,
        "event_order": list(range(1, 12)),
        "event_probability": [1 / 11] * 11,
        "outcome": [0] * 5 + [1] + [0] * 5,
    })
    standardised_long = standardise_event_books(
        long_without_normalised,
        "self_test_long_without_normalised.csv",
    )
    assert "probability_source_normalised" in standardised_long.columns
    assert standardised_long[
        "probability_source_normalised"
    ].isna().all()
    assert len(standardised_long) == 11

    frozen_wide = pd.DataFrame({
        "target_date": ["2026-06-01"] * 11,
        "decision_rule": ["event_day_open"] * 11,
        "gp_probability": [1 / 11] * 11,
        "market_source_probability": [0.09] * 11,
        "market_probability": [1 / 11] * 11,
        "realised_yes": [0] * 5 + [1] + [0] * 5,
        "lower_bound": [-np.inf] + list(range(15, 24)) + [24],
        "upper_bound": [15] + list(range(16, 25)) + [np.inf],
        "event_key": [f"event_{index}" for index in range(1, 12)],
        "contract_rank": list(range(1, 12)),
    })
    frozen_long = standardise_frozen_exact_support_panel(
        frozen_wide,
        "self_test_phase20_exact.csv",
    )
    assert len(frozen_long) == 22
    assert set(frozen_long["model"]) == {"matern", "market"}
    assert frozen_long["event_order"].notna().all()
    assert frozen_long["outcome"].sum() == 2
    market_rows = frozen_long.loc[
        frozen_long["model"] == "market"
    ]
    assert np.allclose(
        market_rows["probability_raw"],
        0.09,
    )
    assert np.allclose(
        market_rows["probability_source_normalised"],
        1 / 11,
    )

    synthetic = pd.DataFrame({
        "target_date": ["2026-06-01"] * 22,
        "decision_rule": ["event_day_open"] * 22,
        "model": ["market"] * 11 + ["matern"] * 11,
        "event_order": list(range(1, 12)) * 2,
        "probability_raw": [1 / 11] * 22,
        "outcome": ([0] * 5 + [1] + [0] * 5) * 2,
        "split": ["june_external"] * 22,
        "probability_normalised": [1 / 11] * 22,
    })
    scores = score_books(
        synthetic,
        {"probability_clip": 1e-12},
    )
    assert len(scores) == 2
    assert np.isfinite(scores[list(METRIC_LABELS)].to_numpy()).all()

    print("SELF-TEST: PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--frozen-root", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    if any(
        value is None
        for value in [
            args.repo_root,
            args.frozen_root,
            args.spec,
            args.output_root,
        ]
    ):
        raise SystemExit(
            "--repo-root, --frozen-root, --spec and --output-root are required"
        )

    repo_root = args.repo_root.resolve()
    frozen_root = args.frozen_root.resolve()
    spec_path = (repo_root / args.spec).resolve()
    out = (repo_root / args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    figures_dir = out / "figures"

    config = json.loads(spec_path.read_text(encoding="utf-8"))
    inputs = config["input_paths"]

    dependency_rows: list[dict[str, Any]] = []
    for label, key in [
        ("Phase 1", "phase1_completion"),
        ("Phase 2", "phase2_integrity"),
        ("Phase 3", "phase3_integrity"),
        ("Phase 4", "phase4_integrity"),
        ("Phase 5", "phase5_integrity"),
    ]:
        passed, detail = dependency_check(repo_root / inputs[key], label)
        dependency_rows.append({
            "check": f"{label.lower().replace(' ', '')}_dependency",
            "passed": passed,
            "critical": True,
            "detail": detail,
        })

    frozen_exact_path = (
        frozen_root / inputs["frozen_exact_support_panel"]
    )
    reconstructed_path = repo_root / inputs[
        "phase1_reconstructed_event_books"
    ]
    exact_keys_path = repo_root / inputs["phase1_exact_support_keys"]
    for path in [
        frozen_exact_path,
        reconstructed_path,
        exact_keys_path,
    ]:
        if not path.is_file():
            raise FileNotFoundError(path)

    provenance = {
        "generated_utc": utc_now(),
        "working_branch": git(repo_root, "branch", "--show-current"),
        "working_commit": git(repo_root, "rev-parse", "HEAD"),
        "frozen_ref": config["frozen_ref"],
        "frozen_tag_object": git(repo_root, "rev-parse", config["frozen_ref"]),
        "frozen_commit": git(
            repo_root,
            "rev-parse",
            f"{config['frozen_ref']}^{{commit}}",
        ),
        "frozen_exact_support_panel": inputs[
            "frozen_exact_support_panel"
        ],
        "frozen_exact_support_panel_sha256": sha256_file(
            frozen_exact_path
        ),
        "frozen_exact_support_role": (
            "authoritative selected-Matern and market exact-support books"
        ),
        "reconstructed_event_books": inputs[
            "phase1_reconstructed_event_books"
        ],
        "reconstructed_event_books_sha256": sha256_file(
            reconstructed_path
        ),
        "exact_support_keys": inputs["phase1_exact_support_keys"],
        "exact_support_keys_sha256": sha256_file(exact_keys_path),
        "bootstrap_replications": config["bootstrap"]["replications"],
        "bootstrap_seed": config["bootstrap"]["seed"],
        "moving_block_lengths": config["bootstrap"][
            "moving_block_lengths"
        ],
        "interpretation_boundary": config[
            "interpretation_boundary"
        ],
    }
    (out / "phase6_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    frozen_exact_raw = read_table(frozen_exact_path)
    reconstructed_raw = read_table(reconstructed_path)
    exact_keys_raw = read_table(exact_keys_path)

    source_inventory = pd.DataFrame([
        {
            "source": "frozen_exact_support_panel",
            "path": inputs["frozen_exact_support_panel"],
            "rows": len(frozen_exact_raw),
            "columns": len(frozen_exact_raw.columns),
            "column_names": "|".join(
                map(str, frozen_exact_raw.columns)
            ),
        },
        {
            "source": "reconstructed_event_books",
            "path": inputs["phase1_reconstructed_event_books"],
            "rows": len(reconstructed_raw),
            "columns": len(reconstructed_raw.columns),
            "column_names": "|".join(map(str, reconstructed_raw.columns)),
        },
        {
            "source": "exact_support_keys",
            "path": inputs["phase1_exact_support_keys"],
            "rows": len(exact_keys_raw),
            "columns": len(exact_keys_raw.columns),
            "column_names": "|".join(map(str, exact_keys_raw.columns)),
        },
    ])
    source_inventory.to_csv(
        out / "phase6_source_inventory.csv",
        index=False,
    )

    existing = standardise_frozen_exact_support_panel(
        frozen_exact_raw,
        frozen_exact_path.name,
    )
    reconstructed = standardise_event_books(
        reconstructed_raw,
        reconstructed_path.name,
    )
    exact_keys = standardise_exact_keys(exact_keys_raw)

    panel, duplicate_audit = prepare_canonical_panel(
        existing,
        reconstructed,
        exact_keys,
        config,
    )
    duplicate_audit.to_csv(
        out / "phase6_duplicate_resolution_audit.csv",
        index=False,
    )
    panel.to_csv(
        out / "phase6_exact_support_event_panel.csv.gz",
        index=False,
        compression="gzip",
    )

    panel_checks = validate_panel(panel, exact_keys, config)
    initial_checks = pd.concat(
        [pd.DataFrame(dependency_rows), panel_checks],
        ignore_index=True,
    )
    initial_checks.to_csv(
        out / "phase6_integrity_checks.csv",
        index=False,
    )
    failures = initial_checks.loc[
        bool_series(initial_checks["critical"])
        & ~bool_series(initial_checks["passed"])
    ]
    if not failures.empty:
        print(initial_checks.to_string(index=False))
        raise RuntimeError("Phase 6 input checks failed")

    book_scores = score_books(panel, config)
    book_scores.to_csv(
        out / "phase6_book_score_panel.csv",
        index=False,
    )
    date_scores = aggregate_date_scores(book_scores, config)
    date_scores.to_csv(
        out / "phase6_date_balanced_score_panel.csv",
        index=False,
    )
    comparison_panel = build_score_comparison_panel(
        date_scores,
        config,
    )
    comparison_panel.to_csv(
        out / "phase6_date_score_comparison_panel.csv",
        index=False,
    )
    score_summary, score_intervals, score_tests = score_inference(
        comparison_panel,
        book_scores,
        config,
    )
    score_summary.to_csv(
        out / "phase6_score_comparison_summary.csv",
        index=False,
    )
    score_intervals.to_csv(
        out / "phase6_score_bootstrap_intervals.csv",
        index=False,
    )
    score_tests.to_csv(
        out / "phase6_score_bootstrap_tests.csv",
        index=False,
    )

    disagreement = build_disagreement_panel(panel)
    disagreement.to_csv(
        out / "phase6_matern_market_disagreement_panel.csv",
        index=False,
    )
    disagreement_summary, disagreement_intervals = (
        disagreement_analysis(disagreement, config)
    )
    disagreement_summary.to_csv(
        out / "phase6_disagreement_summary.csv",
        index=False,
    )
    disagreement_intervals.to_csv(
        out / "phase6_disagreement_bootstrap_intervals.csv",
        index=False,
    )

    event_transitions, book_transitions = build_transition_panels(
        panel,
        config,
    )
    event_transitions.to_csv(
        out / "phase6_event_transition_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    book_transitions.to_csv(
        out / "phase6_book_transition_panel.csv",
        index=False,
    )
    transition_summary, transition_intervals, regressions = (
        transition_analysis(
            event_transitions,
            book_transitions,
            config,
        )
    )
    transition_summary.to_csv(
        out / "phase6_transition_summary.csv",
        index=False,
    )
    transition_intervals.to_csv(
        out / "phase6_transition_bootstrap_intervals.csv",
        index=False,
    )
    regressions.to_csv(
        out / "phase6_market_update_regressions.csv",
        index=False,
    )

    (
        market_age,
        market_age_summary,
        market_age_sensitivity,
        market_age_status,
    ) = market_age_analysis(panel, book_scores, config)
    market_age.to_csv(
        out / "phase6_market_record_age_panel.csv",
        index=False,
    )
    market_age_summary.to_csv(
        out / "phase6_market_record_age_summary.csv",
        index=False,
    )
    market_age_sensitivity.to_csv(
        out / "phase6_market_record_age_sensitivity.csv",
        index=False,
    )
    market_age_status.to_csv(
        out / "phase6_market_record_age_status.csv",
        index=False,
    )

    figure_registry = make_figures(
        score_summary,
        comparison_panel,
        disagreement,
        transition_summary,
        book_transitions,
        book_scores,
        market_age,
        figures_dir,
        int(config["figure_dpi"]),
    )
    figure_registry.to_csv(
        out / "phase6_figure_registry.csv",
        index=False,
    )

    candidate_summary = thesis_candidate_summary(
        score_summary,
        score_intervals,
        disagreement_summary,
        transition_summary,
        market_age_status,
    )
    candidate_summary.to_csv(
        out / "phase6_thesis_candidate_summary.csv",
        index=False,
    )

    reference_checks: list[dict[str, Any]] = []
    for metric, expected_value in config[
        "june_reference_model_minus_market"
    ].items():
        row = score_summary.loc[
            (score_summary["scope_type"] == "overall")
            & (score_summary["split"] == "june_external")
            & (score_summary["model"] == "matern")
            & (score_summary["metric"] == metric)
        ]
        if row.empty:
            reference_checks.append({
                "check": f"june_reference_{metric}",
                "passed": False,
                "critical": True,
                "detail": "summary row missing",
            })
        else:
            calculated = float(row["mean_model_minus_market"].iloc[0])
            reference_checks.append({
                "check": f"june_reference_{metric}",
                "passed": abs(calculated - float(expected_value))
                <= float(config["reference_tolerance"]),
                "critical": True,
                "detail": (
                    f"calculated={calculated:.9f}; "
                    f"reference={float(expected_value):.9f}; "
                    f"difference={calculated-float(expected_value):.3e}"
                ),
            })

    output_checks = [
        {
            "check": "book_score_rows",
            "passed": len(book_scores)
            == config["expected"]["exact_support_books"]
            * len(config["expected"]["required_models"]),
            "critical": True,
            "detail": f"rows={len(book_scores)}",
        },
        {
            "check": "date_score_rows",
            "passed": len(date_scores)
            == config["expected"]["exact_support_dates"]
            * len(config["expected"]["required_models"]),
            "critical": True,
            "detail": f"rows={len(date_scores)}",
        },
        {
            "check": "score_metrics_complete",
            "passed": set(score_summary["metric"].unique())
            == set(config["score_metrics"]),
            "critical": True,
            "detail": f"metrics={sorted(score_summary['metric'].unique())}",
        },
        {
            "check": "score_bootstrap_methods",
            "passed": set(score_intervals["bootstrap_method"].unique())
            == {"ordinary_date", "circular_moving_block"},
            "critical": True,
            "detail": (
                f"methods={sorted(score_intervals['bootstrap_method'].unique())}"
            ),
        },
        {
            "check": "score_moving_block_lengths",
            "passed": set(
                score_intervals.loc[
                    score_intervals["bootstrap_method"]
                    == "circular_moving_block",
                    "block_length_days",
                ].dropna().astype(int).unique()
            )
            == set(config["bootstrap"]["moving_block_lengths"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "disagreement_rows",
            "passed": len(disagreement)
            == config["expected"]["exact_support_books"],
            "critical": True,
            "detail": f"rows={len(disagreement)}",
        },
        {
            "check": "transition_panels_nonempty",
            "passed": not event_transitions.empty
            and not book_transitions.empty,
            "critical": True,
            "detail": (
                f"event_rows={len(event_transitions)}; "
                f"book_rows={len(book_transitions)}"
            ),
        },
        {
            "check": "transition_probability_mass_conserved",
            "passed": bool(
                np.allclose(
                    event_transitions.groupby(
                        ["target_date", "transition"]
                    )["delta_market"].sum(),
                    0.0,
                    atol=config["numerical_tolerance"],
                )
                and np.allclose(
                    event_transitions.groupby(
                        ["target_date", "transition"]
                    )["delta_matern"].sum(),
                    0.0,
                    atol=config["numerical_tolerance"],
                )
            ),
            "critical": True,
            "detail": "",
        },
        {
            "check": "market_age_registered",
            "passed": True,
            "critical": False,
            "detail": (
                f"available={bool(market_age_status['market_age_available'].iloc[0])}; "
                f"coverage={float(market_age_status['coverage_fraction'].iloc[0]):.6f}"
            ),
        },
        {
            "check": "figures_created",
            "passed": len(figure_registry) == 7
            and all(
                (figures_dir / name).is_file()
                for name in figure_registry["figure"]
            ),
            "critical": True,
            "detail": f"figures={len(figure_registry)}",
        },
    ]

    all_checks = pd.concat(
        [
            initial_checks,
            pd.DataFrame(reference_checks),
            pd.DataFrame(output_checks),
        ],
        ignore_index=True,
    )
    all_checks.to_csv(
        out / "phase6_integrity_checks.csv",
        index=False,
    )

    write_report(
        out,
        provenance,
        all_checks,
        score_summary,
        score_intervals,
        disagreement_summary,
        transition_summary,
        regressions,
        market_age_summary,
        config,
    )
    build_manifest(out, provenance)
    make_review_bundle(out)

    final_failures = all_checks.loc[
        bool_series(all_checks["critical"])
        & ~bool_series(all_checks["passed"])
    ]
    print("=" * 96)
    print("PHASE 6 — MARKET COMPARISON AND INFORMATION CONTENT")
    print("=" * 96)
    print(all_checks.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase6_review_bundle.zip'}")
    if final_failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print(final_failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
