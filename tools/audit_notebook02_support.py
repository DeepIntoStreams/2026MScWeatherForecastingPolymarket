#!/usr/bin/env python3
"""Audit Notebook 02 support before probabilistic model fitting."""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

import pandas as pd
import yaml


ROOT = Path.cwd()
HOME = Path.home()

RULES = (
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
)

ARCHIVE_BRANCH = (
    "archive/17j-plus-18n-18y-20260726"
)

REQUEST_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_standardised_request_plan.csv"
)

SELECTED_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_selected_deterministic_forecast_panel.csv"
)

TRAINING_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_weather_training_panel.csv"
)

EVALUATION_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_market_evaluation_forecast_panel.csv"
)

ADMISSION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_forecast_admission_audit.csv"
)

HKO_PATH = (
    ROOT
    / "data"
    / "interim"
    / "hko_daily_max.csv"
)

CONTRACT_PATH = (
    ROOT
    / "data"
    / "interim"
    / "canonical_contract_definitions.csv"
)

SOURCE_BUNDLE_ROOT = (
    ROOT
    / "data"
    / "interim"
    / "notebook02_sources"
)

SUPPORT_MATRIX_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_date_rule_support_matrix.csv"
)

GAP_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_support_gap_summary.csv"
)

EXTENSION_INVENTORY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_extension_source_inventory.csv"
)

EXTENSION_KEYS_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_source_level_extension_candidate_keys.csv"
)

HKO_INVENTORY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_hko_extension_candidate_inventory.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "02_support_and_chronology_manifest.json"
)

CHRONOLOGY_PATH = (
    ROOT
    / "config"
    / "chronology_policy.yaml"
)

DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "NOTEBOOK_02_SUPPORT_AND_CHRONOLOGY.md"
)

MAX_SOURCE_BYTES = 100 * 1024 * 1024


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def normalise_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("°", "")
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    ).strip("_")


def normalise_columns(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()
    seen: Dict[str, int] = {}
    columns = []

    for column in result.columns:
        base = normalise_name(column) or "unnamed"
        count = seen.get(base, 0)
        seen[base] = count + 1

        columns.append(
            base
            if count == 0
            else f"{base}_{count + 1}"
        )

    result.columns = columns
    return result


def normalise_rule(
    value: Any,
) -> Optional[str]:
    if pd.isna(value):
        return None

    text = normalise_name(value)

    if (
        "24h" in text
        or "24_hour" in text
        or text == "24"
    ):
        return "24h_prior"

    if (
        "12h" in text
        or "12_hour" in text
        or text == "12"
    ):
        return "12h_prior"

    if (
        "6h" in text
        or "6_hour" in text
        or text == "6"
    ):
        return "6h_prior"

    if (
        "event_day_open" in text
        or "event_open" in text
        or "market_open" in text
        or text == "open"
    ):
        return "event_day_open"

    return None


def read_csv_bytes(
    payload: bytes,
) -> Optional[pd.DataFrame]:
    for kwargs in (
        {},
        {"encoding": "utf-8-sig"},
        {"encoding": "latin-1"},
    ):
        try:
            frame = pd.read_csv(
                io.BytesIO(payload),
                low_memory=False,
                **kwargs,
            )

            if not frame.empty:
                return normalise_columns(
                    frame
                )

        except Exception:
            continue

    return None


def read_csv_path(
    path: Path,
) -> pd.DataFrame:
    frame = pd.read_csv(
        path,
        low_memory=False,
    )

    return normalise_columns(
        frame
    )


def first_existing(
    columns: Iterable[str],
    priorities: Iterable[str],
) -> Optional[str]:
    available = set(columns)

    for column in priorities:
        if column in available:
            return column

    return None


def detect_date_series(
    frame: pd.DataFrame,
) -> Tuple[str, pd.Series]:
    exact = (
        "target_date",
        "event_date",
        "settlement_date",
        "forecast_target_date",
        "target_local_date",
        "local_target_date",
        "target_day",
        "valid_date",
        "date",
    )

    candidates = []

    for column in exact:
        if column in frame.columns:
            candidates.append(
                column
            )

    for column in frame.columns:
        if (
            "date" in column
            or column.endswith("_day")
        ):
            candidates.append(
                column
            )

    best_column = ""
    best_series = pd.Series(
        pd.NA,
        index=frame.index,
        dtype="object",
    )
    best_count = 0

    for column in dict.fromkeys(
        candidates
    ):
        parsed = pd.to_datetime(
            frame[column],
            errors="coerce",
        )

        formatted = parsed.dt.strftime(
            "%Y-%m-%d"
        )

        plausible = formatted.where(
            formatted.between(
                "2025-01-01",
                "2027-12-31",
            )
        )

        count = int(
            plausible.nunique(
                dropna=True
            )
        )

        if count > best_count:
            best_count = count
            best_column = column
            best_series = plausible

    if best_count > 0:
        return (
            best_column,
            best_series,
        )

    valid_priorities = (
        "valid_time_utc",
        "forecast_valid_time_utc",
        "forecast_time_utc",
        "valid_datetime_utc",
        "valid_time",
        "forecast_time",
        "datetime",
        "time",
    )

    valid_column = first_existing(
        frame.columns,
        valid_priorities,
    )

    if valid_column is not None:
        parsed = pd.to_datetime(
            frame[valid_column],
            errors="coerce",
            utc=True,
        )

        return (
            f"{valid_column}_converted_to_hkt",
            parsed.dt.tz_convert(
                "Asia/Hong_Kong"
            ).dt.strftime(
                "%Y-%m-%d"
            ),
        )

    return (
        "",
        best_series,
    )


def detect_rule_series(
    frame: pd.DataFrame,
    source: str,
) -> Tuple[str, pd.Series]:
    candidates = []

    for column in (
        "decision_rule",
        "rule",
        "decision_point",
        "decision_label",
        "cutoff_rule",
    ):
        if column in frame.columns:
            candidates.append(
                column
            )

    for column in frame.columns:
        if "rule" in column:
            candidates.append(
                column
            )

    for column in dict.fromkeys(
        candidates
    ):
        mapped = frame[column].map(
            normalise_rule
        )

        if mapped.notna().any():
            return (
                column,
                mapped,
            )

    inferred = normalise_rule(
        source
    )

    return (
        "source_name"
        if inferred is not None
        else "",
        pd.Series(
            [inferred] * len(frame),
            index=frame.index,
        ),
    )


def detect_timestamp_columns(
    frame: pd.DataFrame,
) -> Tuple[list[str], list[str]]:
    issue = []
    decision = []

    for column in frame.columns:
        name = column.lower()

        if any(
            token in name
            for token in (
                "issue",
                "init",
                "initial",
                "selected_run",
                "run_time",
                "reference_time",
            )
        ):
            issue.append(
                column
            )

        if any(
            token in name
            for token in (
                "decision",
                "cutoff",
                "as_of",
                "deadline",
            )
        ):
            decision.append(
                column
            )

    return (
        issue,
        decision,
    )


def canonical_date_column(
    frame: pd.DataFrame,
) -> str:
    for column in (
        "target_date",
        "event_date",
        "original_event_date",
    ):
        if column in frame.columns:
            return column

    raise ValueError(
        "No canonical date column found."
    )


def canonical_rule_column(
    frame: pd.DataFrame,
) -> str:
    for column in (
        "decision_rule",
        "rule",
    ):
        if column in frame.columns:
            return column

    raise ValueError(
        "No canonical rule column found."
    )


def canonicalise_keys(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()

    date_column = canonical_date_column(
        result
    )

    result["target_date"] = (
        pd.to_datetime(
            result[date_column],
            errors="raise",
        ).dt.strftime(
            "%Y-%m-%d"
        )
    )

    if "decision_rule" in result.columns:
        result[
            "decision_rule"
        ] = result[
            "decision_rule"
        ].map(
            normalise_rule
        )

    return result


def join_unique(
    values: Iterable[Any],
) -> str:
    cleaned = sorted(
        {
            str(value)
            for value in values
            if pd.notna(value)
            and str(value).strip()
            and str(value).lower()
            not in {
                "nan",
                "none",
            }
        }
    )

    return ";".join(
        cleaned
    )


def build_support_matrix() -> Tuple[
    pd.DataFrame,
    Dict[str, Any],
]:
    requests = canonicalise_keys(
        pd.read_csv(
            REQUEST_PATH,
            low_memory=False,
        )
    )

    selected = canonicalise_keys(
        pd.read_csv(
            SELECTED_PATH,
            low_memory=False,
        )
    )

    training = canonicalise_keys(
        pd.read_csv(
            TRAINING_PATH,
            low_memory=False,
        )
    )

    evaluation = canonicalise_keys(
        pd.read_csv(
            EVALUATION_PATH,
            low_memory=False,
        )
    )

    admission = canonicalise_keys(
        pd.read_csv(
            ADMISSION_PATH,
            low_memory=False,
        )
    )

    contracts = pd.read_csv(
        CONTRACT_PATH,
        low_memory=False,
    )

    contract_date_column = (
        canonical_date_column(
            contracts
        )
    )

    certified_dates = sorted(
        pd.to_datetime(
            contracts[
                contract_date_column
            ],
            errors="raise",
        ).dt.strftime(
            "%Y-%m-%d"
        ).unique()
    )

    universe = pd.MultiIndex.from_product(
        [
            certified_dates,
            RULES,
        ],
        names=[
            "target_date",
            "decision_rule",
        ],
    ).to_frame(
        index=False
    )

    request_keys = set(
        zip(
            requests["target_date"],
            requests["decision_rule"],
        )
    )

    selected_keys = set(
        zip(
            selected["target_date"],
            selected["decision_rule"],
        )
    )

    training_keys = set(
        zip(
            training["target_date"],
            training["decision_rule"],
        )
    )

    evaluation_keys = set(
        zip(
            evaluation["target_date"],
            evaluation["decision_rule"],
        )
    )

    admission_summary = (
        admission.groupby(
            [
                "target_date",
                "decision_rule",
            ],
            dropna=False,
        )
        .agg(
            candidate_groups=(
                "status",
                "size",
            ),
            admitted_groups=(
                "status",
                lambda series:
                int(
                    series.eq(
                        "ADMITTED"
                    ).sum()
                ),
            ),
            rejected_groups=(
                "status",
                lambda series:
                int(
                    series.eq(
                        "REJECTED"
                    ).sum()
                ),
            ),
            maximum_local_hours=(
                "unique_local_hours",
                "max",
            ),
            rejection_reasons=(
                "reason",
                join_unique,
            ),
            candidate_sources=(
                "source",
                join_unique,
            ),
        )
        .reset_index()
    )

    support = universe.merge(
        admission_summary,
        on=[
            "target_date",
            "decision_rule",
        ],
        how="left",
    )

    support[
        "request_present"
    ] = [
        (
            target_date,
            decision_rule,
        )
        in request_keys
        for target_date, decision_rule
        in zip(
            support["target_date"],
            support["decision_rule"],
        )
    ]

    support[
        "selected_forecast_present"
    ] = [
        (
            target_date,
            decision_rule,
        )
        in selected_keys
        for target_date, decision_rule
        in zip(
            support["target_date"],
            support["decision_rule"],
        )
    ]

    support[
        "training_row_present"
    ] = [
        (
            target_date,
            decision_rule,
        )
        in training_keys
        for target_date, decision_rule
        in zip(
            support["target_date"],
            support["decision_rule"],
        )
    ]

    support[
        "evaluation_row_present"
    ] = [
        (
            target_date,
            decision_rule,
        )
        in evaluation_keys
        for target_date, decision_rule
        in zip(
            support["target_date"],
            support["decision_rule"],
        )
    ]

    for column in (
        "candidate_groups",
        "admitted_groups",
        "rejected_groups",
        "maximum_local_hours",
    ):
        support[column] = (
            support[column]
            .fillna(0)
            .astype(int)
        )

    support[
        "rejection_reasons"
    ] = support[
        "rejection_reasons"
    ].fillna("")

    support[
        "candidate_sources"
    ] = support[
        "candidate_sources"
    ].fillna("")

    def classify(
        row: pd.Series,
    ) -> str:
        if row[
            "selected_forecast_present"
        ]:
            return "SELECTED_AND_ADMITTED"

        if not row[
            "request_present"
        ]:
            return "NO_STANDARDISED_REQUEST"

        if row[
            "candidate_groups"
        ] == 0:
            return "NO_HOURLY_CANDIDATE_GROUP"

        if row[
            "admitted_groups"
        ] == 0:
            reasons = (
                row[
                    "rejection_reasons"
                ]
                or "UNSPECIFIED_REJECTION"
            )

            return (
                "ALL_CANDIDATES_REJECTED:"
                + reasons
            )

        return (
            "ADMITTED_CANDIDATE_NOT_SELECTED"
        )

    support[
        "support_status"
    ] = support.apply(
        classify,
        axis=1,
    )

    support[
        "calendar_period"
    ] = pd.cut(
        pd.to_datetime(
            support["target_date"]
        ),
        bins=[
            pd.Timestamp(
                "2026-03-15"
            ),
            pd.Timestamp(
                "2026-05-31"
            ),
            pd.Timestamp(
                "2026-06-30"
            ),
            pd.Timestamp(
                "2026-08-31"
            ),
        ],
        labels=[
            "March-May",
            "June",
            "July-August",
        ],
        include_lowest=True,
    ).astype(str)

    support = support.sort_values(
        [
            "target_date",
            "decision_rule",
        ]
    ).reset_index(
        drop=True
    )

    support.to_csv(
        SUPPORT_MATRIX_PATH,
        index=False,
    )

    gap_summary = (
        support.groupby(
            [
                "calendar_period",
                "support_status",
            ],
            dropna=False,
        )
        .size()
        .reset_index(
            name="date_rule_rows"
        )
        .sort_values(
            [
                "calendar_period",
                "date_rule_rows",
            ],
            ascending=[
                True,
                False,
            ],
        )
    )

    gap_summary.to_csv(
        GAP_SUMMARY_PATH,
        index=False,
    )

    june = support.loc[
        support[
            "target_date"
        ].between(
            "2026-06-01",
            "2026-06-30",
        )
    ].copy()

    missing_june = june.loc[
        ~june[
            "selected_forecast_present"
        ]
    ].copy()

    statistics = {
        "certified_market_dates": (
            len(certified_dates)
        ),
        "expected_market_date_rule_rows": (
            len(support)
        ),
        "selected_market_date_rule_rows": int(
            support[
                "selected_forecast_present"
            ].sum()
        ),
        "missing_market_date_rule_rows": int(
            (
                ~support[
                    "selected_forecast_present"
                ]
            ).sum()
        ),
        "expected_june_date_rule_rows": (
            len(june)
        ),
        "selected_june_date_rule_rows": int(
            june[
                "selected_forecast_present"
            ].sum()
        ),
        "missing_june_date_rule_rows": int(
            len(missing_june)
        ),
        "missing_june_keys": (
            missing_june[
                [
                    "target_date",
                    "decision_rule",
                    "support_status",
                ]
            ].to_dict(
                orient="records"
            )
        ),
    }

    return (
        support,
        statistics,
    )


def role_for_path(
    path: Path,
) -> str:
    try:
        relative = path.relative_to(
            SOURCE_BUNDLE_ROOT
        )

        return relative.parts[0]
    except Exception:
        return "unknown"


def build_source_inventory() -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    Dict[str, Any],
]:
    rows = []
    key_rows = []

    for path in sorted(
        SOURCE_BUNDLE_ROOT.rglob(
            "*.csv"
        )
    ):
        try:
            frame = read_csv_path(
                path
            )
        except Exception as exc:
            rows.append(
                {
                    "role": role_for_path(
                        path
                    ),
                    "source": str(
                        path.relative_to(
                            ROOT
                        )
                    ),
                    "status": "READ_FAILED",
                    "reason": str(exc),
                }
            )

            continue

        source = str(
            path.relative_to(
                ROOT
            )
        )

        role = role_for_path(
            path
        )

        date_column, date_series = (
            detect_date_series(
                frame
            )
        )

        rule_column, rule_series = (
            detect_rule_series(
                frame,
                source,
            )
        )

        issue_columns, decision_columns = (
            detect_timestamp_columns(
                frame
            )
        )

        date_set = sorted(
            set(
                date_series.dropna()
                .astype(str)
            )
        )

        rule_set = sorted(
            set(
                rule_series.dropna()
                .astype(str)
            )
            & set(RULES)
        )

        if date_set and rule_set:
            for target_date in date_set:
                for decision_rule in rule_set:
                    key_rows.append(
                        {
                            "role": role,
                            "source": source,
                            "target_date": (
                                target_date
                            ),
                            "decision_rule": (
                                decision_rule
                            ),
                        }
                    )

        rows.append(
            {
                "role": role,
                "source": source,
                "status": "INSPECTED",
                "rows": len(frame),
                "columns": len(
                    frame.columns
                ),
                "date_column": date_column,
                "rule_column": rule_column,
                "issue_columns": ";".join(
                    issue_columns
                ),
                "decision_columns": (
                    ";".join(
                        decision_columns
                    )
                ),
                "distinct_dates": len(
                    date_set
                ),
                "start_date": (
                    date_set[0]
                    if date_set
                    else ""
                ),
                "end_date": (
                    date_set[-1]
                    if date_set
                    else ""
                ),
                "pre_june_dates": sum(
                    date < "2026-06-01"
                    for date in date_set
                ),
                "june_dates": sum(
                    "2026-06-01"
                    <= date
                    <= "2026-06-30"
                    for date in date_set
                ),
                "post_june_dates": sum(
                    date > "2026-06-30"
                    for date in date_set
                ),
                "rules": ";".join(
                    rule_set
                ),
            }
        )

    inventory = pd.DataFrame(
        rows
    )

    keys = pd.DataFrame(
        key_rows
    )

    inventory.to_csv(
        EXTENSION_INVENTORY_PATH,
        index=False,
    )

    if keys.empty:
        keys = pd.DataFrame(
            columns=[
                "role",
                "source",
                "target_date",
                "decision_rule",
            ]
        )

    keys.to_csv(
        EXTENSION_KEYS_PATH,
        index=False,
    )

    hko = pd.read_csv(
        HKO_PATH,
        low_memory=False,
    )

    hko_date_column = (
        canonical_date_column(
            hko
        )
    )

    hko_dates = set(
        pd.to_datetime(
            hko[
                hko_date_column
            ],
            errors="raise",
        ).dt.strftime(
            "%Y-%m-%d"
        )
    )

    request_keys = set(
        zip(
            keys.loc[
                keys["role"]
                == "request_plan",
                "target_date",
            ],
            keys.loc[
                keys["role"]
                == "request_plan",
                "decision_rule",
            ],
        )
    )

    hourly_keys = set(
        zip(
            keys.loc[
                keys["role"]
                == "hourly_forecasts",
                "target_date",
            ],
            keys.loc[
                keys["role"]
                == "hourly_forecasts",
                "decision_rule",
            ],
        )
    )

    hko_keys = {
        (
            target_date,
            decision_rule,
        )
        for target_date in hko_dates
        for decision_rule in RULES
    }

    source_level_keys = (
        request_keys
        & hourly_keys
        & hko_keys
    )

    source_level_pre_june = sorted(
        {
            target_date
            for (
                target_date,
                _
            )
            in source_level_keys
            if target_date
            < "2026-06-01"
        }
    )

    source_level_june = sorted(
        {
            target_date
            for (
                target_date,
                _
            )
            in source_level_keys
            if (
                "2026-06-01"
                <= target_date
                <= "2026-06-30"
            )
        }
    )

    source_level_post_june = sorted(
        {
            target_date
            for (
                target_date,
                _
            )
            in source_level_keys
            if target_date
            > "2026-06-30"
        }
    )

    statistics = {
        "source_files_inspected": int(
            len(inventory)
        ),
        "request_date_rule_keys": int(
            len(request_keys)
        ),
        "hourly_date_rule_keys": int(
            len(hourly_keys)
        ),
        "source_level_common_date_rule_keys": int(
            len(source_level_keys)
        ),
        "source_level_pre_june_dates": (
            source_level_pre_june
        ),
        "source_level_june_dates": (
            source_level_june
        ),
        "source_level_post_june_dates": (
            source_level_post_june
        ),
    }

    return (
        inventory,
        keys,
        statistics,
    )


def candidate_local_roots() -> list[Path]:
    roots = [
        ROOT / "data",
        ROOT / "review_bundles",
        ROOT
        / "notebooks"
        / "data",
    ]

    roots.extend(
        sorted(
            HOME.glob(
                "Desktop/"
                "2026MScWeatherForecastingPolymarket"
                "_local_archive_*"
            )
        )
    )

    return [
        root
        for root in roots
        if root.exists()
    ]


def hko_relevant_name(
    value: str,
) -> bool:
    lower = value.lower()

    return any(
        token in lower
        for token in (
            "hko",
            "daily_extract",
            "realised_outcome",
            "realized_outcome",
            "daily_max",
            "tmax",
        )
    )


def detect_temperature_column(
    frame: pd.DataFrame,
) -> Optional[str]:
    priorities = (
        "hko_daily_max_c",
        "hko_tmax_c",
        "hko_tmax",
        "hko_daily_max",
        "realised_temperature_c",
        "realized_temperature_c",
        "observed_temperature_c",
        "actual_temperature_c",
    )

    for column in priorities:
        if column in frame.columns:
            return column

    candidates = []

    for column in frame.columns:
        name = column.lower()

        if "forecast" in name:
            continue

        if not any(
            token in name
            for token in (
                "hko",
                "tmax",
                "daily_max",
                "temperature",
            )
        ):
            continue

        numeric = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        ratio = float(
            numeric.notna().mean()
        )

        if ratio < 0.20:
            continue

        score = ratio * 100.0

        if "hko" in name:
            score += 100.0

        if "tmax" in name:
            score += 80.0

        if "daily_max" in name:
            score += 70.0

        candidates.append(
            (
                score,
                column,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        reverse=True
    )

    return candidates[0][1]


def inspect_hko_payload(
    source: str,
    payload: bytes,
) -> Optional[Dict[str, Any]]:
    frame = read_csv_bytes(
        payload
    )

    if frame is None:
        return None

    date_column, date_series = (
        detect_date_series(
            frame
        )
    )

    temperature_column = (
        detect_temperature_column(
            frame
        )
    )

    if (
        not date_column
        or temperature_column is None
    ):
        return None

    temperature = pd.to_numeric(
        frame[
            temperature_column
        ],
        errors="coerce",
    )

    valid = pd.DataFrame(
        {
            "date": date_series,
            "temperature": (
                temperature
            ),
        }
    ).dropna()

    valid = valid.loc[
        valid[
            "temperature"
        ].between(
            -10.0,
            50.0,
        )
    ]

    dates = sorted(
        set(
            valid["date"].astype(str)
        )
    )

    if not dates:
        return None

    return {
        "source": source,
        "date_column": date_column,
        "temperature_column": (
            temperature_column
        ),
        "rows": len(frame),
        "valid_temperature_rows": (
            len(valid)
        ),
        "distinct_dates": len(dates),
        "start_date": dates[0],
        "end_date": dates[-1],
        "pre_june_dates": sum(
            date < "2026-06-01"
            for date in dates
        ),
        "june_dates": sum(
            "2026-06-01"
            <= date
            <= "2026-06-30"
            for date in dates
        ),
        "post_june_dates": sum(
            date > "2026-06-30"
            for date in dates
        ),
        "post_june_date_list": (
            ";".join(
                date
                for date in dates
                if date
                > "2026-06-30"
            )
        ),
    }


def inspect_zip_for_hko(
    source: str,
    payload: bytes,
) -> Iterator[Dict[str, Any]]:
    try:
        archive = zipfile.ZipFile(
            io.BytesIO(payload)
        )
    except zipfile.BadZipFile:
        return

    with archive:
        for member in archive.infolist():
            if (
                member.is_dir()
                or member.file_size
                > MAX_SOURCE_BYTES
            ):
                continue

            if not member.filename.lower().endswith(
                ".csv"
            ):
                continue

            if not hko_relevant_name(
                member.filename
            ):
                continue

            try:
                member_payload = (
                    archive.read(
                        member
                    )
                )
            except Exception:
                continue

            result = inspect_hko_payload(
                (
                    f"{source}::"
                    f"{member.filename}"
                ),
                member_payload,
            )

            if result is not None:
                yield result


def build_hko_inventory() -> Tuple[
    pd.DataFrame,
    Dict[str, Any],
]:
    rows = []
    seen = set()

    for root in candidate_local_roots():
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            if (
                "notebook02_sources"
                in path.parts
            ):
                continue

            if not hko_relevant_name(
                str(path)
            ):
                continue

            if path.suffix.lower() not in {
                ".csv",
                ".zip",
            }:
                continue

            if (
                path.stat().st_size
                > MAX_SOURCE_BYTES
            ):
                continue

            resolved = path.resolve()

            if resolved in seen:
                continue

            seen.add(
                resolved
            )

            try:
                payload = path.read_bytes()
            except OSError:
                continue

            source = (
                f"local:{resolved}"
            )

            if path.suffix.lower() == ".zip":
                rows.extend(
                    inspect_zip_for_hko(
                        source,
                        payload,
                    )
                )
            else:
                result = inspect_hko_payload(
                    source,
                    payload,
                )

                if result is not None:
                    rows.append(
                        result
                    )

    try:
        archive_paths = (
            subprocess.run(
                [
                    "git",
                    "ls-tree",
                    "-r",
                    "--name-only",
                    ARCHIVE_BRANCH,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout
            .splitlines()
        )
    except Exception:
        archive_paths = []

    for path in archive_paths:
        if not hko_relevant_name(
            path
        ):
            continue

        if not path.lower().endswith(
            (
                ".csv",
                ".zip",
            )
        ):
            continue

        try:
            size = int(
                subprocess.run(
                    [
                        "git",
                        "cat-file",
                        "-s",
                        (
                            f"{ARCHIVE_BRANCH}:"
                            f"{path}"
                        ),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            )
        except Exception:
            continue

        if size > MAX_SOURCE_BYTES:
            continue

        try:
            payload = subprocess.run(
                [
                    "git",
                    "show",
                    (
                        f"{ARCHIVE_BRANCH}:"
                        f"{path}"
                    ),
                ],
                check=True,
                capture_output=True,
            ).stdout
        except Exception:
            continue

        source = (
            f"git:{ARCHIVE_BRANCH}:"
            f"{path}"
        )

        if path.lower().endswith(
            ".zip"
        ):
            rows.extend(
                inspect_zip_for_hko(
                    source,
                    payload,
                )
            )
        else:
            result = inspect_hko_payload(
                source,
                payload,
            )

            if result is not None:
                rows.append(
                    result
                )

    inventory = pd.DataFrame(
        rows
    )

    if inventory.empty:
        inventory = pd.DataFrame(
            columns=[
                "source",
                "date_column",
                "temperature_column",
                "rows",
                "valid_temperature_rows",
                "distinct_dates",
                "start_date",
                "end_date",
                "pre_june_dates",
                "june_dates",
                "post_june_dates",
                "post_june_date_list",
            ]
        )
    else:
        inventory = inventory.sort_values(
            [
                "post_june_dates",
                "end_date",
                "distinct_dates",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        ).drop_duplicates(
            [
                "source",
                "date_column",
                "temperature_column",
            ]
        )

    inventory.to_csv(
        HKO_INVENTORY_PATH,
        index=False,
    )

    post_june_dates = sorted(
        {
            date
            for value in inventory[
                "post_june_date_list"
            ].fillna("")
            for date in str(value).split(
                ";"
            )
            if date
        }
    )

    statistics = {
        "hko_candidate_tables": int(
            len(inventory)
        ),
        "post_june_hko_dates_found": (
            post_june_dates
        ),
    }

    return (
        inventory,
        statistics,
    )


def main() -> None:
    for path in (
        SUPPORT_MATRIX_PATH,
        GAP_SUMMARY_PATH,
        EXTENSION_INVENTORY_PATH,
        EXTENSION_KEYS_PATH,
        HKO_INVENTORY_PATH,
        MANIFEST_PATH,
        CHRONOLOGY_PATH,
        DOCUMENT_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    (
        support,
        support_statistics,
    ) = build_support_matrix()

    (
        source_inventory,
        extension_keys,
        source_statistics,
    ) = build_source_inventory()

    (
        hko_inventory,
        hko_statistics,
    ) = build_hko_inventory()

    training = canonicalise_keys(
        pd.read_csv(
            TRAINING_PATH,
            low_memory=False,
        )
    )

    evaluation = canonicalise_keys(
        pd.read_csv(
            EVALUATION_PATH,
            low_memory=False,
        )
    )

    training_dates = sorted(
        training[
            "target_date"
        ].unique()
    )

    evaluation_dates = sorted(
        evaluation[
            "target_date"
        ].unique()
    )

    weather_only_dates = sorted(
        set(training_dates)
        - set(evaluation_dates)
    )

    chronology = {
        "status": (
            "BLOCKED_PENDING_SUPPORT_EXPANSION"
        ),
        "model_fitting_permitted": False,
        "reason": (
            "The current usable sample contains only June 2026, "
            "and the weather-training and market-evaluation date "
            "sets are identical."
        ),
        "current_support": {
            "weather_training_rows": int(
                len(training)
            ),
            "weather_training_dates": int(
                len(training_dates)
            ),
            "weather_training_start": (
                training_dates[0]
            ),
            "weather_training_end": (
                training_dates[-1]
            ),
            "market_evaluation_rows": int(
                len(evaluation)
            ),
            "market_evaluation_dates": int(
                len(evaluation_dates)
            ),
            "weather_only_training_dates": int(
                len(
                    weather_only_dates
                )
            ),
        },
        "principles": {
            "training_requires_market": (
                False
            ),
            "market_evaluation_requires_market": (
                True
            ),
            "random_split_permitted": (
                False
            ),
            "date_grouping_required": (
                True
            ),
            "chronological_blocks_required": (
                True
            ),
            "market_comparison_requires_exact_common_support": (
                True
            ),
            "external_test_must_remain_untouched_until_all_choices_are_locked": (
                True
            ),
        },
        "activation_conditions": [
            (
                "Recover or acquire a materially earlier forecast-HKO "
                "training period."
            ),
            (
                "Reserve a later contiguous period that is untouched "
                "during model and calibration selection."
            ),
            (
                "Record the exact split dates before fitting candidate "
                "probabilistic models."
            ),
            (
                "Ensure each selected rule has sufficient chronological "
                "support in the development calculations."
            ),
            (
                "Keep the settlement date as the uncertainty and "
                "resampling unit."
            ),
        ],
        "block_assignments": {
            "training": (
                "NOT_ASSIGNED"
            ),
            "development_validation": (
                "NOT_ASSIGNED"
            ),
            "holdout": (
                "NOT_ASSIGNED"
            ),
            "external_test": (
                "NOT_ASSIGNED"
            ),
        },
    }

    CHRONOLOGY_PATH.write_text(
        yaml.safe_dump(
            chronology,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "SUPPORT_EXPANSION_REQUIRED"
        ),
        "model_fitting_permitted": (
            False
        ),
        "support_statistics": (
            support_statistics
        ),
        "source_statistics": (
            source_statistics
        ),
        "hko_statistics": (
            hko_statistics
        ),
        "current_training": {
            "rows": int(
                len(training)
            ),
            "dates": int(
                len(training_dates)
            ),
            "start": (
                training_dates[0]
            ),
            "end": (
                training_dates[-1]
            ),
            "weather_only_dates": int(
                len(
                    weather_only_dates
                )
            ),
        },
        "current_evaluation": {
            "rows": int(
                len(evaluation)
            ),
            "dates": int(
                len(evaluation_dates)
            ),
            "start": (
                evaluation_dates[0]
            ),
            "end": (
                evaluation_dates[-1]
            ),
        },
        "chronology_status": chronology[
            "status"
        ],
        "inputs": {
            str(
                REQUEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                REQUEST_PATH
            ),
            str(
                SELECTED_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                SELECTED_PATH
            ),
            str(
                TRAINING_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                TRAINING_PATH
            ),
            str(
                EVALUATION_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                EVALUATION_PATH
            ),
            str(
                ADMISSION_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                ADMISSION_PATH
            ),
        },
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    missing_june = (
        support.loc[
            support[
                "target_date"
            ].between(
                "2026-06-01",
                "2026-06-30",
            )
            & ~support[
                "selected_forecast_present"
            ],
            [
                "target_date",
                "decision_rule",
                "support_status",
                "candidate_groups",
                "maximum_local_hours",
                "rejection_reasons",
            ],
        ]
    )

    lines = [
        "# Notebook 02 Support and Chronology Audit",
        "",
        "Status: `SUPPORT_EXPANSION_REQUIRED`",
        "",
        "## Current empirical support",
        "",
        (
            f"- Weather training rows: "
            f"{len(training)}."
        ),
        (
            f"- Weather training dates: "
            f"{len(training_dates)}."
        ),
        (
            f"- Training period: "
            f"{training_dates[0]} to "
            f"{training_dates[-1]}."
        ),
        (
            f"- Market evaluation rows: "
            f"{len(evaluation)}."
        ),
        (
            f"- Market evaluation dates: "
            f"{len(evaluation_dates)}."
        ),
        (
            f"- Weather-only training dates: "
            f"{len(weather_only_dates)}."
        ),
        "",
        (
            "The software architecture separates model training from "
            "market evaluation, but the current realised date sets are "
            "identical. The empirical separation requested by the "
            "supervisors has therefore not yet been achieved."
        ),
        "",
        "## June support gap",
        "",
    ]

    if missing_june.empty:
        lines.append(
            "All 120 June date-rule combinations are present."
        )
    else:
        for row in missing_june.itertuples(
            index=False
        ):
            lines.append(
                f"- {row.target_date}, "
                f"`{row.decision_rule}`: "
                f"`{row.support_status}`; "
                f"candidate groups={row.candidate_groups}; "
                f"maximum local hours="
                f"{row.maximum_local_hours}; "
                f"reasons="
                f"{row.rejection_reasons or 'not recorded'}."
            )

    lines.extend(
        [
            "",
            "## Earlier and later support",
            "",
            (
                "The source inventory tests only whether the request, "
                "hourly forecast and HKO sources contain the same date-rule "
                "keys. This is a recovery signal, not proof that a path is "
                "admissible."
            ),
            "",
            (
                f"- Source-level pre-June candidate dates: "
                f"{len(source_statistics['source_level_pre_june_dates'])}."
            ),
            (
                f"- Source-level June candidate dates: "
                f"{len(source_statistics['source_level_june_dates'])}."
            ),
            (
                f"- Source-level post-June candidate dates with existing "
                f"HKO outcomes: "
                f"{len(source_statistics['source_level_post_june_dates'])}."
            ),
            (
                f"- Post-June HKO dates found in preserved local or Git "
                f"sources: "
                f"{len(hko_statistics['post_june_hko_dates_found'])}."
            ),
            "",
            "## Chronology decision",
            "",
            (
                "No training, development, holdout or external-test dates "
                "are assigned at this stage. Assigning them from a single "
                "30-day month would create an arbitrary and weak validation "
                "design."
            ),
            "",
            "Model fitting remains blocked until:",
            "",
            "1. an earlier weather-training period is recovered or acquired;",
            "2. a later untouched period can be reserved;",
            "3. the split dates are declared before fitting;",
            "4. date-grouped chronological validation can be implemented.",
            "",
            "The formal gate is recorded in:",
            "",
            "`config/chronology_policy.yaml`",
            "",
        ]
    )

    DOCUMENT_PATH.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print(" NOTEBOOK 02 SUPPORT AUDIT COMPLETE")
    print("=" * 72)
    print()
    print(
        "Certified market dates:",
        support_statistics[
            "certified_market_dates"
        ],
    )
    print(
        "Expected market date-rule rows:",
        support_statistics[
            "expected_market_date_rule_rows"
        ],
    )
    print(
        "Selected date-rule rows:",
        support_statistics[
            "selected_market_date_rule_rows"
        ],
    )
    print(
        "Expected June date-rule rows:",
        support_statistics[
            "expected_june_date_rule_rows"
        ],
    )
    print(
        "Selected June date-rule rows:",
        support_statistics[
            "selected_june_date_rule_rows"
        ],
    )
    print(
        "Missing June date-rule rows:",
        support_statistics[
            "missing_june_date_rule_rows"
        ],
    )

    if not missing_june.empty:
        print()
        print("Missing June combinations:")

        for row in missing_june.itertuples(
            index=False
        ):
            print(
                " ",
                row.target_date,
                row.decision_rule,
                "->",
                row.support_status,
            )

    print()
    print(
        "Source-level pre-June candidate dates:",
        len(
            source_statistics[
                "source_level_pre_june_dates"
            ]
        ),
    )

    print(
        "Source-level post-June candidate dates "
        "with current HKO outcomes:",
        len(
            source_statistics[
                "source_level_post_june_dates"
            ]
        ),
    )

    print(
        "Post-June HKO dates found in preserved sources:",
        len(
            hko_statistics[
                "post_june_hko_dates_found"
            ]
        ),
    )

    print()
    print(
        "Chronology status:",
        chronology["status"],
    )

    print(
        "Model fitting permitted:",
        chronology[
            "model_fitting_permitted"
        ],
    )

    print()
    print(
        "Support matrix:",
        SUPPORT_MATRIX_PATH,
    )

    print(
        "Extension inventory:",
        EXTENSION_INVENTORY_PATH,
    )

    print(
        "HKO extension inventory:",
        HKO_INVENTORY_PATH,
    )

    print(
        "Chronology policy:",
        CHRONOLOGY_PATH,
    )

    print(
        "Manifest:",
        MANIFEST_PATH,
    )


if __name__ == "__main__":
    main()
