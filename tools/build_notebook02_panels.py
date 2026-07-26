#!/usr/bin/env python3
"""Construct deterministic forecast panels for canonical Notebook 02."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


ROOT = Path.cwd()
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from weather_polymarket.forecast_adapter import (
    DATE_ALIASES,
    DAILY_MAXIMUM_ALIASES,
    DECISION_TIME_ALIASES,
    HOURLY_TEMPERATURE_ALIASES,
    ISSUE_TIME_ALIASES,
    REQUEST_ID_ALIASES,
    RULE_ALIASES,
    RUN_ID_ALIASES,
    VALID_TIME_ALIASES,
    first_column,
    infer_rule_from_source,
    normalise_columns,
    normalise_rule,
    plausible_dates,
    source_preference,
    temperature_to_celsius,
    utc_datetimes,
)


BUNDLE_ROOT = (
    ROOT
    / "data"
    / "interim"
    / "notebook02_sources"
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

SELECTED_FORECAST_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_selected_deterministic_forecast_panel.csv"
)

REQUEST_PLAN_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_standardised_request_plan.csv"
)

ADMISSION_AUDIT_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_forecast_admission_audit.csv"
)

RECONCILIATION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_hourly_daily_reconciliation.csv"
)

SOURCE_SCHEMA_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_panel_source_schema_audit.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_panel_construction_summary.json"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "02_panel_construction_manifest.json"
)

VALID_RULES = {
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def read_tables(role: str) -> List[tuple[str, pd.DataFrame]]:
    directory = BUNDLE_ROOT / role

    if not directory.exists():
        return []

    tables: List[tuple[str, pd.DataFrame]] = []

    for path in sorted(directory.glob("*.csv")):
        try:
            frame = pd.read_csv(
                path,
                low_memory=False,
            )
        except Exception:
            continue

        if frame.empty:
            continue

        tables.append(
            (
                str(path.relative_to(ROOT)),
                normalise_columns(frame),
            )
        )

    return tables


def value_series(
    frame: pd.DataFrame,
    aliases: Iterable[str],
    default: Any = pd.NA,
) -> pd.Series:
    column = first_column(
        frame.columns,
        aliases,
    )

    if column is None:
        return pd.Series(
            [default] * len(frame),
            index=frame.index,
            dtype="object",
        )

    return frame[column]


def serialise_timestamp(
    series: pd.Series,
) -> pd.Series:
    return series.dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _plausible_utc_times(
    series: pd.Series,
) -> pd.Series:
    parsed = pd.to_datetime(
        series,
        errors="coerce",
        utc=True,
    )

    plausible = (
        parsed.dt.year.between(
            2025,
            2027,
        )
    )

    return parsed.where(plausible)


def _best_datetime_column(
    frame: pd.DataFrame,
    role: str,
) -> Optional[str]:
    positive = {
        "issue": (
            "issue",
            "init",
            "initial",
            "run_time",
            "origin",
            "reference_time",
            "selected_run",
            "forecast_run",
        ),
        "decision": (
            "decision",
            "cutoff",
            "as_of",
            "deadline",
            "request_time",
        ),
        "valid": (
            "valid",
            "forecast_time",
            "valid_time",
            "forecast_valid",
        ),
    }[role]

    negative = {
        "issue": (
            "valid",
            "decision",
            "cutoff",
            "retrieved",
            "created",
        ),
        "decision": (
            "valid",
            "issue",
            "init",
            "retrieved",
            "created",
        ),
        "valid": (
            "issue",
            "init",
            "decision",
            "cutoff",
            "retrieved",
            "created",
        ),
    }[role]

    candidates = []

    for column in frame.columns:
        name = str(column).lower()

        parsed = _plausible_utc_times(
            frame[column]
        )

        ratio = float(
            parsed.notna().mean()
        )

        if ratio < 0.20:
            continue

        score = ratio * 100.0

        for token in positive:
            if token in name:
                score += 60.0

        for token in negative:
            if token in name:
                score -= 80.0

        if role == "issue":
            if name in {
                "forecast_init_utc",
                "forecast_init_time_utc",
                "init_time_utc",
                "selected_init_utc",
                "issue_time_utc",
                "forecast_issue_time_utc",
            }:
                score += 150.0

        if role == "decision":
            if name in {
                "decision_time_utc",
                "decision_timestamp_utc",
                "cutoff_time_utc",
                "as_of_utc",
            }:
                score += 150.0

        if role == "valid":
            if name in {
                "valid_time_utc",
                "forecast_valid_time_utc",
                "forecast_time_utc",
            }:
                score += 150.0

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


def _best_date_column(
    frame: pd.DataFrame,
) -> Optional[str]:
    candidates = []

    for column in frame.columns:
        name = str(column).lower()

        if (
            "date" not in name
            and "day" not in name
        ):
            continue

        parsed = pd.to_datetime(
            frame[column],
            errors="coerce",
        )

        plausible = (
            parsed.dt.year.between(
                2025,
                2027,
            )
        )

        ratio = float(
            plausible.mean()
        )

        if ratio < 0.20:
            continue

        score = ratio * 100.0

        priorities = (
            ("target_date", 150.0),
            ("event_date", 140.0),
            ("settlement_date", 130.0),
            ("forecast_target", 120.0),
            ("target_day", 110.0),
            ("valid_date", 60.0),
            ("date", 20.0),
        )

        for token, value in priorities:
            if token in name:
                score += value

        for token in (
            "issue",
            "decision",
            "init",
            "created",
            "retrieved",
        ):
            if token in name:
                score -= 100.0

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


def _best_rule_column(
    frame: pd.DataFrame,
) -> Optional[str]:
    candidates = []

    for column in frame.columns:
        mapped = frame[column].map(
            normalise_rule
        )

        ratio = float(
            mapped.notna().mean()
        )

        if ratio == 0.0:
            continue

        name = str(column).lower()
        score = ratio * 100.0

        if name == "decision_rule":
            score += 150.0
        elif "rule" in name:
            score += 100.0
        elif "decision" in name:
            score += 50.0

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


def _best_identifier_column(
    frame: pd.DataFrame,
    kind: str,
) -> Optional[str]:
    if kind == "request":
        preferred = (
            "request_id",
            "forecast_request_id",
            "request_key",
        )
    else:
        preferred = (
            "run_id",
            "forecast_run_id",
            "selected_run_id",
        )

    for column in preferred:
        if column in frame.columns:
            return column

    for column in frame.columns:
        name = str(column).lower()

        if kind == "request":
            if "request" in name and (
                "id" in name
                or "key" in name
            ):
                return column
        else:
            if "run" in name and "id" in name:
                return column

    return None


def _best_temperature_column(
    frame: pd.DataFrame,
) -> Optional[str]:
    for column in HOURLY_TEMPERATURE_ALIASES:
        if column in frame.columns:
            return column

    candidates = []

    for column in frame.columns:
        name = str(column).lower()

        if not any(
            token in name
            for token in (
                "temperature",
                "temp",
                "t2m",
            )
        ):
            continue

        if any(
            token in name
            for token in (
                "max",
                "min",
                "residual",
                "error",
                "threshold",
                "bound",
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

        if "temperature_2m" in name:
            score += 150.0
        elif "t2m" in name:
            score += 130.0
        elif "temperature" in name:
            score += 100.0

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


def standardise_request_plans() -> pd.DataFrame:
    rows = []
    mapping_rows = []

    for source, frame in read_tables(
        "request_plan"
    ):
        date_column = _best_date_column(
            frame
        )

        rule_column = _best_rule_column(
            frame
        )

        issue_column = _best_datetime_column(
            frame,
            "issue",
        )

        decision_column = _best_datetime_column(
            frame,
            "decision",
        )

        request_column = _best_identifier_column(
            frame,
            "request",
        )

        mapping_rows.append(
            {
                "role": "request_plan",
                "source": source,
                "date_column": (
                    date_column or ""
                ),
                "rule_column": (
                    rule_column or ""
                ),
                "request_column": (
                    request_column or ""
                ),
                "issue_column": (
                    issue_column or ""
                ),
                "decision_column": (
                    decision_column or ""
                ),
            }
        )

        if date_column is None:
            continue

        standardised = pd.DataFrame(
            index=frame.index
        )

        standardised["target_date"] = (
            pd.to_datetime(
                frame[date_column],
                errors="coerce",
            ).dt.strftime(
                "%Y-%m-%d"
            )
        )

        if rule_column is not None:
            standardised[
                "decision_rule"
            ] = frame[rule_column].map(
                normalise_rule
            )
        else:
            standardised[
                "decision_rule"
            ] = infer_rule_from_source(
                source
            )

        if request_column is not None:
            standardised[
                "request_id"
            ] = (
                frame[request_column]
                .astype(str)
                .replace(
                    {
                        "nan": "",
                        "None": "",
                    }
                )
            )
        else:
            standardised[
                "request_id"
            ] = ""

        if issue_column is not None:
            standardised[
                "planned_issue_time_utc"
            ] = _plausible_utc_times(
                frame[issue_column]
            )
        else:
            standardised[
                "planned_issue_time_utc"
            ] = pd.NaT

        if decision_column is not None:
            standardised[
                "decision_time_utc"
            ] = _plausible_utc_times(
                frame[decision_column]
            )
        else:
            standardised[
                "decision_time_utc"
            ] = pd.NaT

        standardised["source"] = source
        standardised[
            "source_preference"
        ] = source_preference(
            source
        )

        standardised = standardised.loc[
            standardised[
                "target_date"
            ].notna()
            & standardised[
                "decision_rule"
            ].isin(VALID_RULES)
        ].copy()

        if not standardised.empty:
            rows.append(
                standardised
            )

    if not rows:
        raise RuntimeError(
            "No request-plan rows could be standardised."
        )

    requests = pd.concat(
        rows,
        ignore_index=True,
    )

    requests[
        "_timestamp_completeness"
    ] = (
        requests[
            "planned_issue_time_utc"
        ].notna().astype(int)
        + requests[
            "decision_time_utc"
        ].notna().astype(int)
    )

    requests = requests.sort_values(
        [
            "target_date",
            "decision_rule",
            "_timestamp_completeness",
            "decision_time_utc",
            "source_preference",
        ],
        ascending=[
            True,
            True,
            False,
            False,
            False,
        ],
        na_position="last",
    )

    requests = requests.drop_duplicates(
        [
            "target_date",
            "decision_rule",
        ],
        keep="first",
    ).drop(
        columns=[
            "_timestamp_completeness",
        ]
    ).reset_index(
        drop=True
    )

    mapping_path = (
        ROOT
        / "outputs"
        / "diagnostics"
        / "02_request_timestamp_mapping.csv"
    )

    mapping_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame(
        mapping_rows
    ).to_csv(
        mapping_path,
        index=False,
    )

    issue_coverage = float(
        requests[
            "planned_issue_time_utc"
        ].notna().mean()
    )

    decision_coverage = float(
        requests[
            "decision_time_utc"
        ].notna().mean()
    )

    if issue_coverage == 0.0:
        raise RuntimeError(
            "Request plans contain no detected issue times."
        )

    if decision_coverage == 0.0:
        raise RuntimeError(
            "Request plans contain no detected decision times."
        )

    print(
        "Standardised request-plan rows:",
        len(requests),
    )

    print(
        "Request issue-time coverage:",
        f"{issue_coverage:.3f}",
    )

    print(
        "Request decision-time coverage:",
        f"{decision_coverage:.3f}",
    )

    return requests


def request_lookup(
    requests: pd.DataFrame,
) -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[tuple[str, str], Dict[str, Any]],
]:
    by_id: Dict[str, Dict[str, Any]] = {}
    by_key: Dict[
        tuple[str, str],
        Dict[str, Any],
    ] = {}

    for row in requests.to_dict(
        orient="records"
    ):
        request_id = str(
            row.get(
                "request_id",
                "",
            )
        ).strip()

        if request_id:
            by_id[request_id] = row

        by_key[
            (
                row["target_date"],
                row["decision_rule"],
            )
        ] = row

    return by_id, by_key


def standardise_hourly(
    requests: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    request_times = requests[
        [
            "target_date",
            "decision_rule",
            "request_id",
            "planned_issue_time_utc",
            "decision_time_utc",
        ]
    ].rename(
        columns={
            "request_id": (
                "request_id_from_plan"
            ),
            "decision_time_utc": (
                "decision_time_from_plan"
            ),
        }
    )

    standardised_rows = []
    schema_rows = []

    for source, frame in read_tables(
        "hourly_forecasts"
    ):
        valid_column = _best_datetime_column(
            frame,
            "valid",
        )

        temperature_column = (
            _best_temperature_column(
                frame
            )
        )

        date_column = _best_date_column(
            frame
        )

        rule_column = _best_rule_column(
            frame
        )

        issue_column = _best_datetime_column(
            frame,
            "issue",
        )

        decision_column = _best_datetime_column(
            frame,
            "decision",
        )

        request_column = _best_identifier_column(
            frame,
            "request",
        )

        run_column = _best_identifier_column(
            frame,
            "run",
        )

        schema_row = {
            "role": "hourly_forecasts",
            "source": source,
            "date_column": (
                date_column or ""
            ),
            "rule_column": (
                rule_column or ""
            ),
            "request_column": (
                request_column or ""
            ),
            "run_column": (
                run_column or ""
            ),
            "issue_column": (
                issue_column or ""
            ),
            "decision_column": (
                decision_column or ""
            ),
            "valid_column": (
                valid_column or ""
            ),
            "temperature_column": (
                temperature_column or ""
            ),
        }

        if (
            valid_column is None
            or temperature_column is None
        ):
            schema_row["status"] = (
                "REJECTED_SCHEMA"
            )

            schema_rows.append(
                schema_row
            )

            continue

        valid_utc = _plausible_utc_times(
            frame[valid_column]
        )

        valid_hkt = valid_utc.dt.tz_convert(
            "Asia/Hong_Kong"
        )

        temperature, unit_basis = (
            temperature_to_celsius(
                frame[
                    temperature_column
                ]
            )
        )

        if date_column is not None:
            target_date = (
                pd.to_datetime(
                    frame[date_column],
                    errors="coerce",
                ).dt.strftime(
                    "%Y-%m-%d"
                )
            )
        else:
            target_date = (
                valid_hkt.dt.strftime(
                    "%Y-%m-%d"
                )
            )

        if rule_column is not None:
            decision_rule = (
                frame[rule_column].map(
                    normalise_rule
                )
            )
        else:
            decision_rule = pd.Series(
                [
                    infer_rule_from_source(
                        source
                    )
                ]
                * len(frame),
                index=frame.index,
            )

        if request_column is not None:
            request_id = (
                frame[request_column]
                .astype(str)
                .replace(
                    {
                        "nan": "",
                        "None": "",
                    }
                )
            )
        else:
            request_id = pd.Series(
                [""] * len(frame),
                index=frame.index,
            )

        if run_column is not None:
            run_id = (
                frame[run_column]
                .astype(str)
                .replace(
                    {
                        "nan": "",
                        "None": "",
                    }
                )
            )
        else:
            run_id = pd.Series(
                [""] * len(frame),
                index=frame.index,
            )

        if issue_column is not None:
            issue_time = _plausible_utc_times(
                frame[issue_column]
            )
        else:
            issue_time = pd.Series(
                pd.NaT,
                index=frame.index,
                dtype="datetime64[ns, UTC]",
            )

        if decision_column is not None:
            decision_time = (
                _plausible_utc_times(
                    frame[
                        decision_column
                    ]
                )
            )
        else:
            decision_time = pd.Series(
                pd.NaT,
                index=frame.index,
                dtype="datetime64[ns, UTC]",
            )

        standardised = pd.DataFrame(
            {
                "target_date": (
                    target_date
                ),
                "decision_rule": (
                    decision_rule
                ),
                "request_id": request_id,
                "run_id": run_id,
                "forecast_issue_time_utc": (
                    issue_time
                ),
                "decision_time_utc": (
                    decision_time
                ),
                "valid_time_utc": (
                    valid_utc
                ),
                "valid_time_hkt": (
                    valid_hkt
                ),
                "temperature_c": (
                    temperature
                ),
                "temperature_unit_basis": (
                    unit_basis
                ),
                "source": source,
                "source_preference": (
                    source_preference(
                        source
                    )
                ),
            }
        )

        standardised = standardised.merge(
            request_times,
            on=[
                "target_date",
                "decision_rule",
            ],
            how="left",
            validate="many_to_one",
        )

        standardised[
            "forecast_issue_time_utc"
        ] = standardised[
            "forecast_issue_time_utc"
        ].where(
            standardised[
                "forecast_issue_time_utc"
            ].notna(),
            standardised[
                "planned_issue_time_utc"
            ],
        )

        standardised[
            "decision_time_utc"
        ] = standardised[
            "decision_time_utc"
        ].where(
            standardised[
                "decision_time_utc"
            ].notna(),
            standardised[
                "decision_time_from_plan"
            ],
        )

        blank_request = (
            standardised[
                "request_id"
            ]
            .astype(str)
            .str.strip()
            .isin(
                {
                    "",
                    "nan",
                    "None",
                }
            )
        )

        standardised.loc[
            blank_request,
            "request_id",
        ] = standardised.loc[
            blank_request,
            "request_id_from_plan",
        ]

        standardised = standardised.drop(
            columns=[
                "request_id_from_plan",
                "planned_issue_time_utc",
                "decision_time_from_plan",
            ]
        )

        standardised = standardised.loc[
            standardised[
                "target_date"
            ].notna()
            & standardised[
                "decision_rule"
            ].isin(VALID_RULES)
            & standardised[
                "valid_time_utc"
            ].notna()
            & standardised[
                "temperature_c"
            ].notna()
        ].copy()

        schema_row["status"] = (
            "ADMITTED_SCHEMA"
            if not standardised.empty
            else "NO_USABLE_ROWS"
        )

        schema_row[
            "standardised_rows"
        ] = len(standardised)

        schema_row[
            "issue_time_coverage_after_merge"
        ] = (
            float(
                standardised[
                    "forecast_issue_time_utc"
                ].notna().mean()
            )
            if not standardised.empty
            else 0.0
        )

        schema_row[
            "decision_time_coverage_after_merge"
        ] = (
            float(
                standardised[
                    "decision_time_utc"
                ].notna().mean()
            )
            if not standardised.empty
            else 0.0
        )

        schema_rows.append(
            schema_row
        )

        if not standardised.empty:
            standardised_rows.append(
                standardised
            )

    if not standardised_rows:
        raise RuntimeError(
            "No hourly source produced usable rows."
        )

    hourly = pd.concat(
        standardised_rows,
        ignore_index=True,
    )

    issue_coverage = float(
        hourly[
            "forecast_issue_time_utc"
        ].notna().mean()
    )

    decision_coverage = float(
        hourly[
            "decision_time_utc"
        ].notna().mean()
    )

    print(
        "Standardised hourly rows:",
        len(hourly),
    )

    print(
        "Hourly issue-time coverage after request merge:",
        f"{issue_coverage:.3f}",
    )

    print(
        "Hourly decision-time coverage after request merge:",
        f"{decision_coverage:.3f}",
    )

    if issue_coverage == 0.0:
        raise RuntimeError(
            "Hourly rows still contain no issue times after request merge."
        )

    if decision_coverage == 0.0:
        raise RuntimeError(
            "Hourly rows still contain no decision times after request merge."
        )

    return (
        hourly,
        pd.DataFrame(
            schema_rows
        ),
    )


def construct_hourly_candidates(
    hourly: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Construct one candidate path for each source, target date,
    decision rule and forecast issue time.

    This grouping is supported by the exact admission audit. A request ID is
    retained as provenance but is not treated as the run-level grouping key.
    """

    frame = hourly.copy()

    frame["forecast_issue_time_utc"] = pd.to_datetime(
        frame["forecast_issue_time_utc"],
        errors="coerce",
        utc=True,
    )

    frame["decision_time_utc"] = pd.to_datetime(
        frame["decision_time_utc"],
        errors="coerce",
        utc=True,
    )

    frame["valid_time_utc"] = pd.to_datetime(
        frame["valid_time_utc"],
        errors="coerce",
        utc=True,
    )

    frame["valid_time_hkt"] = pd.to_datetime(
        frame["valid_time_hkt"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert("Asia/Hong_Kong")

    audit_rows = []
    candidate_rows = []

    group_columns = [
        "source",
        "target_date",
        "decision_rule",
        "forecast_issue_time_utc",
    ]

    for keys, group in frame.groupby(
        group_columns,
        dropna=False,
        sort=False,
    ):
        (
            source,
            target_date,
            decision_rule,
            issue_time,
        ) = keys

        source = str(source)
        target_date = (
            ""
            if pd.isna(target_date)
            else str(target_date)
        )

        decision_rule = (
            ""
            if pd.isna(decision_rule)
            else str(decision_rule)
        )

        reasons = []

        if not target_date:
            reasons.append("missing_target_date")

        if decision_rule not in VALID_RULES:
            reasons.append("invalid_decision_rule")

        if pd.isna(issue_time):
            reasons.append("missing_issue_time")

        decision_values = (
            group["decision_time_utc"]
            .dropna()
            .drop_duplicates()
            .sort_values()
        )

        if decision_values.empty:
            decision_time = pd.NaT
            reasons.append("missing_decision_time")
        else:
            decision_time = decision_values.iloc[-1]

            if len(decision_values) > 1:
                reasons.append(
                    "multiple_decision_times_within_candidate"
                )

        if (
            pd.notna(issue_time)
            and pd.notna(decision_time)
            and issue_time > decision_time
        ):
            reasons.append(
                "issue_time_after_decision_time"
            )

        local_day = group.loc[
            group["valid_time_hkt"].notna()
            & group["temperature_c"].notna()
        ].copy()

        if target_date:
            local_day = local_day.loc[
                local_day["valid_time_hkt"]
                .dt.strftime("%Y-%m-%d")
                == target_date
            ].copy()

        local_day["valid_hour_hkt"] = (
            local_day["valid_time_hkt"]
            .dt.floor("h")
        )

        hourly_conflicts = (
            local_day.groupby(
                "valid_hour_hkt"
            )["temperature_c"]
            .nunique(dropna=True)
        )

        conflicting_hours = int(
            (hourly_conflicts > 1).sum()
        )

        if conflicting_hours > 0:
            reasons.append(
                "conflicting_temperature_for_same_hour"
            )

        # Identical duplicate rows do not create additional hourly support.
        local_day = local_day.sort_values(
            [
                "valid_hour_hkt",
                "valid_time_utc",
                "source_preference",
            ]
        ).drop_duplicates(
            "valid_hour_hkt",
            keep="last",
        )

        unique_local_hours = int(
            local_day["valid_hour_hkt"].nunique()
        )

        if unique_local_hours != 24:
            reasons.append(
                f"local_hour_count_{unique_local_hours}"
            )

        if not local_day.empty:
            earliest_local_hour = (
                local_day["valid_hour_hkt"].min()
            )

            latest_local_hour = (
                local_day["valid_hour_hkt"].max()
            )
        else:
            earliest_local_hour = pd.NaT
            latest_local_hour = pd.NaT

        forecast_daily_max_c = (
            float(
                local_day["temperature_c"].max()
            )
            if (
                unique_local_hours == 24
                and conflicting_hours == 0
            )
            else np.nan
        )

        request_ids = sorted(
            {
                value
                for value in (
                    group["request_id"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                )
                if value
                and value.lower()
                not in {
                    "nan",
                    "none",
                    "nat",
                }
            }
        )

        run_ids = sorted(
            {
                value
                for value in (
                    group["run_id"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                )
                if value
                and value.lower()
                not in {
                    "nan",
                    "none",
                    "nat",
                }
            }
        )

        source_preference_value = float(
            pd.to_numeric(
                group["source_preference"],
                errors="coerce",
            ).max()
        )

        admitted = len(reasons) == 0

        row = {
            "source": source,
            "grouping_definition": (
                "source_target_date_decision_rule_issue_time"
            ),
            "target_date": target_date,
            "decision_rule": decision_rule,
            "request_id": (
                request_ids[0]
                if len(request_ids) == 1
                else ";".join(request_ids)
            ),
            "run_id": (
                run_ids[0]
                if len(run_ids) == 1
                else ";".join(run_ids)
            ),
            "forecast_issue_time_utc": issue_time,
            "decision_time_utc": decision_time,
            "source_rows": int(len(group)),
            "target_day_rows": int(len(local_day)),
            "unique_local_hours": unique_local_hours,
            "conflicting_hours": conflicting_hours,
            "earliest_valid_hour_hkt": earliest_local_hour,
            "latest_valid_hour_hkt": latest_local_hour,
            "forecast_daily_max_c": forecast_daily_max_c,
            "source_preference": source_preference_value,
            "status": (
                "ADMITTED"
                if admitted
                else "REJECTED"
            ),
            "reason": ";".join(reasons),
        }

        audit_rows.append(row)

        if admitted:
            candidate_rows.append(row.copy())

    audit = pd.DataFrame(audit_rows)
    candidates = pd.DataFrame(candidate_rows)

    if candidates.empty:
        reason_counts = (
            audit.loc[
                audit["status"] == "REJECTED",
                "reason",
            ]
            .value_counts()
            .head(20)
            .to_dict()
        )

        raise RuntimeError(
            "No date-rule-issue forecast path was admitted. "
            f"Leading rejection patterns: {reason_counts}"
        )

    candidates["forecast_issue_time_utc"] = pd.to_datetime(
        candidates["forecast_issue_time_utc"],
        errors="raise",
        utc=True,
    )

    candidates["decision_time_utc"] = pd.to_datetime(
        candidates["decision_time_utc"],
        errors="raise",
        utc=True,
    )

    # The admissible forecast for a date and decision rule is the latest
    # candidate issued no later than the decision time. Source preference is
    # used only to break ties at an identical issue time.
    candidates = candidates.sort_values(
        [
            "target_date",
            "decision_rule",
            "forecast_issue_time_utc",
            "source_preference",
            "source",
        ],
        ascending=[
            True,
            True,
            False,
            False,
            True,
        ],
    )

    selected = candidates.drop_duplicates(
        [
            "target_date",
            "decision_rule",
        ],
        keep="first",
    ).reset_index(drop=True)

    selected["selection_rule"] = (
        "latest_admissible_issue_time_then_source_preference"
    )

    if not selected["unique_local_hours"].eq(24).all():
        raise RuntimeError(
            "A selected forecast path does not contain 24 local hours."
        )

    if not (
        selected["forecast_issue_time_utc"]
        <= selected["decision_time_utc"]
    ).all():
        raise RuntimeError(
            "A selected forecast was issued after its decision time."
        )

    if selected[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "Duplicate selected date-rule forecasts remain."
        )

    return selected, audit


def standardise_daily_maximum(
    requests: pd.DataFrame,
) -> pd.DataFrame:
    by_id, by_key = request_lookup(
        requests
    )

    rows = []

    for source, frame in read_tables(
        "daily_max_forecasts"
    ):
        forecast_column = first_column(
            frame.columns,
            DAILY_MAXIMUM_ALIASES,
        )

        date_column = first_column(
            frame.columns,
            DATE_ALIASES,
        )

        if (
            forecast_column is None
            or date_column is None
        ):
            continue

        rule_column = first_column(
            frame.columns,
            RULE_ALIASES,
        )

        request_column = first_column(
            frame.columns,
            REQUEST_ID_ALIASES,
        )

        issue_column = first_column(
            frame.columns,
            ISSUE_TIME_ALIASES,
        )

        forecast, unit_basis = (
            temperature_to_celsius(
                frame[
                    forecast_column
                ]
            )
        )

        target_date = plausible_dates(
            frame[date_column]
        )

        if rule_column is not None:
            decision_rule = frame[
                rule_column
            ].map(normalise_rule)
        else:
            decision_rule = pd.Series(
                [
                    infer_rule_from_source(
                        source
                    )
                ]
                * len(frame),
                index=frame.index,
            )

        request_id = (
            frame[request_column]
            .astype(str)
            .replace(
                {
                    "nan": "",
                    "None": "",
                }
            )
            if request_column is not None
            else pd.Series(
                [""] * len(frame),
                index=frame.index,
            )
        )

        issue_time = (
            utc_datetimes(
                frame[issue_column]
            )
            if issue_column is not None
            else pd.Series(
                pd.NaT,
                index=frame.index,
                dtype="datetime64[ns, UTC]",
            )
        )

        standardised = pd.DataFrame(
            {
                "target_date": target_date,
                "decision_rule": decision_rule,
                "request_id": request_id,
                "daily_table_forecast_c": (
                    forecast
                ),
                "forecast_issue_time_utc": (
                    issue_time
                ),
                "temperature_unit_basis": (
                    unit_basis
                ),
                "daily_source": source,
                "daily_source_preference": (
                    source_preference(
                        source
                    )
                ),
            }
        )

        for index, row in standardised.iterrows():
            request = None

            request_identifier = str(
                row["request_id"]
            ).strip()

            if request_identifier:
                request = by_id.get(
                    request_identifier
                )

            if request is None and (
                pd.notna(
                    row["target_date"]
                )
                and row[
                    "decision_rule"
                ] in VALID_RULES
            ):
                request = by_key.get(
                    (
                        str(
                            row[
                                "target_date"
                            ]
                        ),
                        str(
                            row[
                                "decision_rule"
                            ]
                        ),
                    )
                )

            if request is None:
                continue

            if standardised.at[
                index,
                "decision_rule",
            ] not in VALID_RULES:
                standardised.at[
                    index,
                    "decision_rule",
                ] = request[
                    "decision_rule"
                ]

            if pd.isna(
                standardised.at[
                    index,
                    "forecast_issue_time_utc",
                ]
            ):
                standardised.at[
                    index,
                    "forecast_issue_time_utc",
                ] = pd.to_datetime(
                    request[
                        "planned_issue_time_utc"
                    ],
                    errors="coerce",
                    utc=True,
                )

        standardised = standardised.loc[
            standardised[
                "target_date"
            ].notna()
            & standardised[
                "decision_rule"
            ].isin(VALID_RULES)
            & standardised[
                "daily_table_forecast_c"
            ].notna()
        ].copy()

        rows.append(standardised)

    if not rows:
        return pd.DataFrame(
            columns=[
                "target_date",
                "decision_rule",
                "daily_table_forecast_c",
                "daily_source",
            ]
        )

    daily = pd.concat(
        rows,
        ignore_index=True,
    )

    daily[
        "forecast_issue_time_utc"
    ] = pd.to_datetime(
        daily[
            "forecast_issue_time_utc"
        ],
        errors="coerce",
        utc=True,
    )

    daily = daily.sort_values(
        [
            "target_date",
            "decision_rule",
            "forecast_issue_time_utc",
            "daily_source_preference",
        ],
        ascending=[
            True,
            True,
            False,
            False,
        ],
    )

    daily = daily.drop_duplicates(
        [
            "target_date",
            "decision_rule",
        ],
        keep="first",
    )

    return daily.reset_index(
        drop=True
    )


def build_panels() -> Dict[str, Any]:
    requests = standardise_request_plans()

    hourly, schema_audit = (
        standardise_hourly(
            requests
        )
    )

    selected, admission_audit = (
        construct_hourly_candidates(
            hourly
        )
    )

    daily = standardise_daily_maximum(
        requests
    )

    reconciliation = selected.merge(
        daily[
            [
                "target_date",
                "decision_rule",
                "daily_table_forecast_c",
                "daily_source",
            ]
        ],
        on=[
            "target_date",
            "decision_rule",
        ],
        how="left",
    )

    reconciliation[
        "absolute_difference_c"
    ] = (
        reconciliation[
            "forecast_daily_max_c"
        ]
        - reconciliation[
            "daily_table_forecast_c"
        ]
    ).abs()

    reconciliation[
        "reconciliation_status"
    ] = np.select(
        [
            reconciliation[
                "daily_table_forecast_c"
            ].isna(),
            reconciliation[
                "absolute_difference_c"
            ]
            <= 0.15,
        ],
        [
            "DAILY_TABLE_NOT_AVAILABLE",
            "AGREES_WITHIN_0_15C",
        ],
        default="DIFFERENCE_EXCEEDS_0_15C",
    )

    hko = pd.read_csv(
        HKO_PATH
    )

    hko["target_date"] = (
        pd.to_datetime(
            hko["event_date"],
            errors="raise",
        ).dt.strftime(
            "%Y-%m-%d"
        )
    )

    hko[
        "hko_daily_max_c"
    ] = pd.to_numeric(
        hko[
            "hko_daily_max_c"
        ],
        errors="raise",
    )

    market_contracts = pd.read_csv(
        CONTRACT_PATH
    )

    market_dates = set(
        pd.to_datetime(
            market_contracts[
                "event_date"
            ],
            errors="raise",
        ).dt.strftime(
            "%Y-%m-%d"
        )
    )

    selected[
        "forecast_issue_time_utc"
    ] = selected[
        "forecast_issue_time_utc"
    ].dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    selected[
        "decision_time_utc"
    ] = selected[
        "decision_time_utc"
    ].dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    training = selected.merge(
        hko[
            [
                "target_date",
                "hko_daily_max_c",
            ]
        ],
        on="target_date",
        how="inner",
    )

    training["residual_c"] = (
        training[
            "hko_daily_max_c"
        ]
        - training[
            "forecast_daily_max_c"
        ]
    )

    training[
        "has_certified_polymarket_market"
    ] = training[
        "target_date"
    ].isin(
        market_dates
    )

    evaluation = training.loc[
        training[
            "has_certified_polymarket_market"
        ]
    ].copy()

    if training.empty:
        raise RuntimeError(
            "The weather training panel is empty."
        )

    if evaluation.empty:
        raise RuntimeError(
            "The market evaluation forecast panel is empty."
        )

    issue_times = pd.to_datetime(
        training[
            "forecast_issue_time_utc"
        ],
        utc=True,
    )

    decision_times = pd.to_datetime(
        training[
            "decision_time_utc"
        ],
        utc=True,
    )

    if not (
        issue_times <= decision_times
    ).all():
        raise RuntimeError(
            "The admitted panel contains a forecast issued after its decision time."
        )

    if not training[
        "unique_local_hours"
    ].eq(24).all():
        raise RuntimeError(
            "The admitted panel contains an incomplete Hong Kong local day."
        )

    if training[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "The training panel contains duplicate date-rule rows."
        )

    if evaluation[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "The evaluation panel contains duplicate date-rule rows."
        )

    if (
        training[
            "target_date"
        ].max()
        < "2026-06-30"
    ):
        raise RuntimeError(
            "The admitted weather panel does not reach 30 June 2026."
        )

    return {
        "requests": requests,
        "selected": selected,
        "training": training,
        "evaluation": evaluation,
        "admission_audit": admission_audit,
        "reconciliation": reconciliation,
        "schema_audit": schema_audit,
        "market_date_count": len(
            market_dates
        ),
    }


def write_outputs(
    result: Dict[str, Any],
) -> None:
    for path in (
        TRAINING_PATH,
        EVALUATION_PATH,
        SELECTED_FORECAST_PATH,
        REQUEST_PLAN_PATH,
        ADMISSION_AUDIT_PATH,
        RECONCILIATION_PATH,
        SOURCE_SCHEMA_PATH,
        SUMMARY_PATH,
        MANIFEST_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    result["requests"].to_csv(
        REQUEST_PLAN_PATH,
        index=False,
    )

    result["selected"].to_csv(
        SELECTED_FORECAST_PATH,
        index=False,
    )

    result["training"].to_csv(
        TRAINING_PATH,
        index=False,
    )

    result["evaluation"].to_csv(
        EVALUATION_PATH,
        index=False,
    )

    result[
        "admission_audit"
    ].to_csv(
        ADMISSION_AUDIT_PATH,
        index=False,
    )

    result[
        "reconciliation"
    ].to_csv(
        RECONCILIATION_PATH,
        index=False,
    )

    result[
        "schema_audit"
    ].to_csv(
        SOURCE_SCHEMA_PATH,
        index=False,
    )

    training = result["training"]
    evaluation = result["evaluation"]
    reconciliation = result[
        "reconciliation"
    ]
    admission = result[
        "admission_audit"
    ]

    all_training_dates = set(
        training[
            "target_date"
        ]
    )

    market_evaluation_dates = set(
        evaluation[
            "target_date"
        ]
    )

    weather_only_dates = sorted(
        all_training_dates
        - market_evaluation_dates
    )

    summary = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "NOTEBOOK02_PANELS_READY",
        "request_rows": int(
            len(result["requests"])
        ),
        "hourly_groups_audited": int(
            len(admission)
        ),
        "hourly_groups_admitted_before_deduplication": int(
            (
                admission["status"]
                == "ADMITTED"
            ).sum()
        ),
        "selected_forecast_rows": int(
            len(result["selected"])
        ),
        "weather_training_rows": int(
            len(training)
        ),
        "weather_training_dates": int(
            training[
                "target_date"
            ].nunique()
        ),
        "weather_training_start": str(
            training[
                "target_date"
            ].min()
        ),
        "weather_training_end": str(
            training[
                "target_date"
            ].max()
        ),
        "market_evaluation_rows": int(
            len(evaluation)
        ),
        "market_evaluation_dates_with_forecasts": int(
            evaluation[
                "target_date"
            ].nunique()
        ),
        "certified_market_dates_available": int(
            result[
                "market_date_count"
            ]
        ),
        "weather_only_training_dates": int(
            len(weather_only_dates)
        ),
        "weather_only_training_date_list": (
            weather_only_dates
        ),
        "decision_rules_present": sorted(
            training[
                "decision_rule"
            ].unique()
        ),
        "all_admitted_paths_have_24_local_hours": bool(
            training[
                "unique_local_hours"
            ].eq(24).all()
        ),
        "all_issue_times_not_later_than_decision_times": True,
        "reconciled_rows": int(
            reconciliation[
                "daily_table_forecast_c"
            ].notna().sum()
        ),
        "reconciled_within_0_15c": int(
            (
                reconciliation[
                    "reconciliation_status"
                ]
                == "AGREES_WITHIN_0_15C"
            ).sum()
        ),
        "reconciliation_difference_exceeds_0_15c": int(
            (
                reconciliation[
                    "reconciliation_status"
                ]
                == "DIFFERENCE_EXCEEDS_0_15C"
            ).sum()
        ),
        "training_requires_market": False,
        "evaluation_requires_market": True,
        "forecast_definition": (
            "maximum of 24 unique hourly temperatures "
            "over the Hong Kong local target day"
        ),
    }

    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        **summary,
        "inputs": {
            str(
                HKO_PATH.relative_to(
                    ROOT
                )
            ): {
                "sha256": sha256_file(
                    HKO_PATH
                ),
            },
            str(
                CONTRACT_PATH.relative_to(
                    ROOT
                )
            ): {
                "sha256": sha256_file(
                    CONTRACT_PATH
                ),
            },
            "data/manifests/02_weather_source_bundle_manifest.json": {
                "sha256": sha256_file(
                    ROOT
                    / "data"
                    / "manifests"
                    / "02_weather_source_bundle_manifest.json"
                ),
            },
        },
        "outputs": {
            str(
                TRAINING_PATH.relative_to(
                    ROOT
                )
            ): {
                "sha256": sha256_file(
                    TRAINING_PATH
                ),
                "rows": len(training),
            },
            str(
                EVALUATION_PATH.relative_to(
                    ROOT
                )
            ): {
                "sha256": sha256_file(
                    EVALUATION_PATH
                ),
                "rows": len(evaluation),
            },
            str(
                SELECTED_FORECAST_PATH.relative_to(
                    ROOT
                )
            ): {
                "sha256": sha256_file(
                    SELECTED_FORECAST_PATH
                ),
                "rows": len(
                    result["selected"]
                ),
            },
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

    print()
    print("============================================================")
    print(" NOTEBOOK 02 PANELS READY")
    print("============================================================")
    print()
    print(
        "Weather training rows:",
        summary[
            "weather_training_rows"
        ],
    )
    print(
        "Weather training dates:",
        summary[
            "weather_training_dates"
        ],
    )
    print(
        "Weather training period:",
        summary[
            "weather_training_start"
        ],
        "to",
        summary[
            "weather_training_end"
        ],
    )
    print(
        "Market evaluation rows:",
        summary[
            "market_evaluation_rows"
        ],
    )
    print(
        "Market evaluation dates with forecasts:",
        summary[
            "market_evaluation_dates_with_forecasts"
        ],
    )
    print(
        "Certified market dates available:",
        summary[
            "certified_market_dates_available"
        ],
    )
    print(
        "Weather-only training dates:",
        summary[
            "weather_only_training_dates"
        ],
    )
    print(
        "Decision rules:",
        ", ".join(
            summary[
                "decision_rules_present"
            ]
        ),
    )
    print(
        "Paths with 24 HKT hours:",
        summary[
            "all_admitted_paths_have_24_local_hours"
        ],
    )
    print(
        "Issue times no later than decisions:",
        summary[
            "all_issue_times_not_later_than_decision_times"
        ],
    )
    print(
        "Daily maximum reconciliations:",
        summary[
            "reconciled_rows"
        ],
    )
    print(
        "Reconciliations within 0.15 C:",
        summary[
            "reconciled_within_0_15c"
        ],
    )
    print()
    print(f"Summary: {SUMMARY_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    result = build_panels()
    write_outputs(result)
