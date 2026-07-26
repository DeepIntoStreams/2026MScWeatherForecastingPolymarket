"""Adapters for deterministic forecast paths used by Notebook 02."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd


DATE_ALIASES = (
    "target_date",
    "event_date",
    "forecast_target_date",
    "target_local_date",
    "local_target_date",
    "settlement_date",
    "market_date",
    "valid_date",
    "date",
)

RULE_ALIASES = (
    "decision_rule",
    "rule",
    "decision_point",
    "decision_label",
    "cutoff_rule",
)

REQUEST_ID_ALIASES = (
    "request_id",
    "forecast_request_id",
    "request_key",
)

RUN_ID_ALIASES = (
    "run_id",
    "forecast_run_id",
    "selected_run_id",
)

ISSUE_TIME_ALIASES = (
    "forecast_init_utc",
    "forecast_init_time_utc",
    "init_time_utc",
    "initialisation_time_utc",
    "initialization_time_utc",
    "selected_init_utc",
    "selected_run_utc",
    "model_run_utc",
    "run_time_utc",
    "issue_time_utc",
    "forecast_issue_time_utc",
)

DECISION_TIME_ALIASES = (
    "decision_time_utc",
    "decision_timestamp_utc",
    "cutoff_time_utc",
    "as_of_utc",
    "request_time_utc",
)

VALID_TIME_ALIASES = (
    "valid_time_utc",
    "forecast_valid_time_utc",
    "valid_datetime_utc",
    "forecast_time_utc",
    "valid_time",
    "forecast_time",
    "time_utc",
    "datetime_utc",
    "datetime",
)

HOURLY_TEMPERATURE_ALIASES = (
    "temperature_2m_c",
    "temperature_c",
    "forecast_temperature_c",
    "temp_c",
    "t2m_c",
    "temperature_2m",
)

DAILY_MAXIMUM_ALIASES = (
    "forecast_daily_max_c",
    "daily_max_forecast_c",
    "forecast_tmax_c",
    "predicted_tmax_c",
    "tmax_forecast_c",
    "forecast_max_c",
    "daily_max_c",
    "max_temperature_c",
    "temperature_2m_max",
    "temperature_max",
)


def normalise_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("°", "")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    seen: dict[str, int] = {}
    columns: list[str] = []

    for column in result.columns:
        base = normalise_name(column) or "unnamed"
        count = seen.get(base, 0)
        seen[base] = count + 1

        columns.append(
            base if count == 0 else f"{base}_{count + 1}"
        )

    result.columns = columns
    return result


def first_column(
    columns: Iterable[str],
    aliases: Iterable[str],
) -> Optional[str]:
    available = set(columns)

    for alias in aliases:
        if alias in available:
            return alias

    return None


def plausible_dates(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(
        series,
        errors="coerce",
    )

    formatted = parsed.dt.strftime("%Y-%m-%d")

    plausible = formatted.between(
        "2025-01-01",
        "2027-12-31",
    )

    return formatted.where(plausible)


def utc_datetimes(series: pd.Series) -> pd.Series:
    return pd.to_datetime(
        series,
        errors="coerce",
        utc=True,
    )


def normalise_rule(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None

    text = normalise_name(value)

    if not text:
        return None

    if (
        "24h" in text
        or "24_hour" in text
        or text in {"24", "day_before"}
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
        or "market_open" in text
        or text in {"open", "event_open"}
    ):
        return "event_day_open"

    return None


def infer_rule_from_source(source: str) -> Optional[str]:
    return normalise_rule(
        Path(source).name
    )


def temperature_to_celsius(
    series: pd.Series,
) -> tuple[pd.Series, str]:
    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    finite = numeric.dropna()

    if finite.empty:
        return numeric, "unknown"

    median = float(finite.median())

    if median > 150.0:
        return numeric - 273.15, "kelvin_converted_to_celsius"

    return numeric, "celsius"


def source_preference(source: str) -> float:
    lower = source.lower()
    score = 0.0

    priorities = (
        ("18q", 1000.0),
        ("june_2026", 900.0),
        ("19a", 800.0),
        ("single_run", 700.0),
        ("local", 300.0),
        ("processed", 100.0),
    )

    for token, value in priorities:
        if token in lower:
            score += value

    return score
