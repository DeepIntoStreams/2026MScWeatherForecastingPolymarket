"""Canonical adapter for eleven-event contract definitions."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from .schemas import (
    CONTRACT_DEFINITION_COLUMNS,
    missing_columns,
)
from .settlement import EventInterval, validate_partition


def _optional_float(value) -> Optional[float]:
    if pd.isna(value) or str(value).strip() == "":
        return None
    return float(value)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(int(value))

    text = str(value).strip().lower()

    if text in {"true", "1", "yes", "y"}:
        return True

    if text in {"false", "0", "no", "n"}:
        return False

    raise ValueError(f"Cannot interpret Boolean value: {value!r}")


def intervals_for_date(group: pd.DataFrame) -> List[EventInterval]:
    intervals = [
        EventInterval(
            event_id=str(row.event_id),
            lower_c=_optional_float(row.lower_bound_c),
            upper_c=_optional_float(row.upper_bound_c),
            lower_closed=_as_bool(row.lower_closed),
            upper_closed=_as_bool(row.upper_closed),
        )
        for row in group.itertuples(index=False)
    ]

    return validate_partition(intervals, expected_count=11)


def load_contract_definitions(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing canonical contract input: {path}"
        )

    frame = pd.read_csv(path)

    missing = missing_columns(
        frame.columns,
        CONTRACT_DEFINITION_COLUMNS,
    )

    if missing:
        raise ValueError(
            "Contract input is missing columns: "
            + ", ".join(missing)
        )

    frame["event_date"] = pd.to_datetime(
        frame["event_date"],
        errors="raise",
    ).dt.date

    frame["event_index"] = pd.to_numeric(
        frame["event_index"],
        errors="raise",
    ).astype(int)

    if frame.duplicated(
        ["event_date", "event_id"],
        keep=False,
    ).any():
        raise ValueError("Duplicate date-event identifiers detected.")

    for event_date, group in frame.groupby("event_date"):
        if len(group) != 11:
            raise ValueError(
                f"{event_date} contains {len(group)} events."
            )

        intervals_for_date(group)

    return frame.sort_values(
        ["event_date", "event_index"]
    ).reset_index(drop=True)
