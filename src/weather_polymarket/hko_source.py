"""Canonical adapter for HKO daily maximum temperatures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schemas import HKO_DAILY_MAX_COLUMNS, missing_columns


def load_hko_daily_max(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing canonical HKO input: {path}")

    frame = pd.read_csv(path)

    missing = missing_columns(frame.columns, HKO_DAILY_MAX_COLUMNS)

    if missing:
        raise ValueError(
            "HKO input is missing columns: " + ", ".join(missing)
        )

    frame["event_date"] = pd.to_datetime(
        frame["event_date"],
        errors="raise",
    ).dt.date

    frame["hko_daily_max_c"] = pd.to_numeric(
        frame["hko_daily_max_c"],
        errors="raise",
    )

    if frame["event_date"].duplicated().any():
        raise ValueError("HKO input contains duplicate dates.")

    one_decimal = frame["hko_daily_max_c"].map(
        lambda value: abs(
            float(value) * 10 - round(float(value) * 10)
        ) < 1e-8
    )

    if not one_decimal.all():
        raise ValueError("HKO outcomes must be recorded to one decimal.")

    return frame.sort_values("event_date").reset_index(drop=True)
