#!/usr/bin/env python3
"""Discover and migrate real HKO and contract sources from the archive."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


ARCHIVE_BRANCH = "archive/17j-plus-18n-18y-20260726"
MIN_COMMON_DATES = 70
MAX_FILE_BYTES = 150 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 100 * 1024 * 1024


@dataclass
class Table:
    source: str
    frame: pd.DataFrame
    source_sha256: str


@dataclass
class ContractCandidate:
    source: str
    frame: pd.DataFrame
    source_sha256: str
    date_column: str
    label_column: str
    lower_column: str
    upper_column: str
    valid_dates: int
    rows: int
    score: float


@dataclass
class HkoCandidate:
    source: str
    frame: pd.DataFrame
    source_sha256: str
    date_column: str
    temperature_column: str
    valid_dates: int
    rows: int
    score: float


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
    )
    return result.stdout


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8", errors="replace")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalise_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("°", "")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    counts: Dict[str, int] = {}
    names: List[str] = []

    for column in result.columns:
        base = normalise_name(column) or "unnamed"
        count = counts.get(base, 0)
        counts[base] = count + 1
        names.append(base if count == 0 else f"{base}_{count + 1}")

    result.columns = names
    return result


def parse_dates(series: pd.Series) -> pd.Series:
    values = series.copy()

    numeric = pd.to_numeric(values, errors="coerce")

    if numeric.notna().mean() > 0.8:
        plausible_yyyymmdd = numeric.between(
            19000101,
            21001231,
        )

        if plausible_yyyymmdd.mean() > 0.8:
            values = numeric.round().astype("Int64").astype(str)

    return pd.to_datetime(
        values,
        errors="coerce",
    ).dt.date


def detect_date_column(frame: pd.DataFrame) -> Optional[str]:
    """Choose the date field producing the strongest daily panel structure."""

    best: Optional[Tuple[float, str]] = None

    for column in frame.columns:
        name = column.lower()

        if not (
            "date" in name
            or name in {"day", "target_day", "settlement_day"}
        ):
            continue

        parsed = parse_dates(frame[column])
        valid = parsed.notna()
        ratio = float(valid.mean())

        if ratio < 0.40:
            continue

        counts = parsed.loc[valid].value_counts()

        dates_with_11_rows = int((counts == 11).sum())
        distinct_dates = int(counts.index.nunique())

        name_score = 0.0
        name_score += 12.0 if name == "event_date" else 0.0
        name_score += 10.0 if name == "settlement_date" else 0.0
        name_score += 8.0 if name == "target_date" else 0.0
        name_score += 6.0 if name == "original_event_date" else 0.0
        name_score += 4.0 if "hko" in name else 0.0

        score = (
            dates_with_11_rows * 10000.0
            + distinct_dates * 100.0
            + ratio * 10.0
            + name_score
        )

        if best is None or score > best[0]:
            best = (score, column)

    return None if best is None else best[1]


def optional_float(value: Any) -> Optional[float]:
    if pd.isna(value):
        return None

    text = str(value).strip().lower()

    if text in {
        "",
        "none",
        "nan",
        "-inf",
        "-infinity",
        "inf",
        "+inf",
        "infinity",
        "+infinity",
    }:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def parse_interval_label(
    value: Any,
) -> Optional[Tuple[Optional[float], Optional[float]]]:
    if pd.isna(value):
        return None

    text = str(value).lower()
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("≤", "<=")
    text = text.replace("≥", ">=")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("°c", "")
    text = text.replace("°", "")
    text = text.replace("degrees celsius", "")
    text = text.replace("degree celsius", "")
    text = re.sub(r"\s+", " ", text).strip()

    numbers = [
        float(number)
        for number in re.findall(r"-?\d+(?:\.\d+)?", text)
    ]

    if not numbers:
        return None

    if any(
        phrase in text
        for phrase in (
            "or below",
            "or lower",
            "and below",
            "and lower",
        )
    ):
        return None, numbers[0] + 1.0

    if any(
        phrase in text
        for phrase in (
            "below",
            "under",
            "less than",
        )
    ) or text.startswith("<"):
        return None, numbers[0]

    if any(
        phrase in text
        for phrase in (
            "or above",
            "or higher",
            "and above",
            "and higher",
            "at least",
        )
    ):
        return numbers[0], None

    if any(
        phrase in text
        for phrase in (
            "above",
            "over",
            "greater than",
        )
    ) or text.startswith(">"):
        return numbers[0], None

    if len(numbers) >= 2:
        lower = min(numbers[0], numbers[1])
        upper = max(numbers[0], numbers[1])

        if math.isclose(lower, upper):
            upper = lower + 1.0

        return lower, upper

    # A single integer bucket such as "30 C" represents [30,31).
    return numbers[0], numbers[0] + 1.0


def find_column(
    columns: Iterable[str],
    exact: Sequence[str],
    required_tokens: Sequence[str] = (),
    preferred_tokens: Sequence[str] = (),
    forbidden_tokens: Sequence[str] = (),
) -> Optional[str]:
    column_list = list(columns)

    for name in exact:
        if name in column_list:
            return name

    best: Optional[Tuple[float, str]] = None

    for column in column_list:
        lower = column.lower()

        if any(token in lower for token in forbidden_tokens):
            continue

        if required_tokens and not any(
            token in lower for token in required_tokens
        ):
            continue

        score = sum(
            1.0 for token in preferred_tokens if token in lower
        )

        if best is None or score > best[0]:
            best = (score, column)

    return None if best is None else best[1]


def detect_label_column(frame: pd.DataFrame) -> Optional[str]:
    preferred = (
        "event_label",
        "contract_label",
        "outcome_label",
        "bucket_label",
        "canonical_label",
        "display_label",
        "question",
        "title",
        "outcome",
        "name",
    )

    candidates: List[str] = []

    for column in preferred:
        if column in frame.columns:
            candidates.append(column)

    for column in frame.columns:
        lower = column.lower()

        if any(
            token in lower
            for token in (
                "label",
                "question",
                "title",
                "bucket",
                "outcome_name",
                "contract_name",
            )
        ):
            candidates.append(column)

    best: Optional[Tuple[float, str]] = None

    for column in dict.fromkeys(candidates):
        sample = frame[column].dropna().head(1000)

        if sample.empty:
            continue

        parsed = sample.map(parse_interval_label)
        ratio = float(parsed.notna().mean())
        unique = int(sample.astype(str).nunique())

        score = ratio * 100.0 + min(unique, 20)

        if ratio >= 0.30 and (
            best is None or score > best[0]
        ):
            best = (score, column)

    return None if best is None else best[1]


def detect_bound_column(
    frame: pd.DataFrame,
    side: str,
) -> Optional[str]:
    exact = (
        f"{side}_bound_c",
        f"{side}_c",
        f"event_{side}_c",
        f"contract_{side}_c",
        f"bucket_{side}_c",
        f"{side}_temperature_c",
        f"{side}_threshold_c",
    )

    for column in exact:
        if column in frame.columns:
            return column

    side_tokens = (
        ("lower", "minimum", "min")
        if side == "lower"
        else ("upper", "maximum", "max")
    )

    best: Optional[Tuple[float, str]] = None

    for column in frame.columns:
        lower = column.lower()

        if not any(token in lower for token in side_tokens):
            continue

        if not any(
            token in lower
            for token in (
                "bound",
                "bucket",
                "event",
                "contract",
                "threshold",
                "temperature",
                "temp",
            )
        ):
            continue

        if any(
            token in lower
            for token in (
                "forecast",
                "prediction",
                "error",
                "score",
                "probability",
                "price",
                "hko_daily",
            )
        ):
            continue

        numeric = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        ratio = float(numeric.notna().mean())

        # Tail-bound columns legitimately contain missing values.
        if ratio < 0.05:
            continue

        score = ratio * 100.0
        score += 10.0 if "bound" in lower else 0.0
        score += 5.0 if "event" in lower else 0.0

        if best is None or score > best[0]:
            best = (score, column)

    return None if best is None else best[1]


def detect_hko_temperature_column(
    frame: pd.DataFrame,
    date_column: str,
) -> Optional[str]:
    exact = (
        "hko_daily_max_c",
        "hko_daily_max",
        "hko_max_c",
        "hko_max",
        "hko_temperature_c",
        "realised_temperature_c",
        "realized_temperature_c",
        "observed_temperature_c",
        "actual_temperature_c",
        "settlement_temperature_c",
    )

    for column in exact:
        if column in frame.columns:
            return column

    best: Optional[Tuple[float, str]] = None

    for column in frame.columns:
        if column == date_column:
            continue

        name = column.lower()

        if any(
            token in name
            for token in (
                "forecast",
                "predicted",
                "prediction",
                "ecmwf",
                "model",
                "residual",
                "error",
                "probability",
                "price",
                "threshold",
                "bound",
            )
        ):
            continue

        name_score = 0.0
        name_score += 12.0 if "hko" in name else 0.0
        name_score += 7.0 if "daily_max" in name else 0.0
        name_score += 5.0 if "temperature" in name else 0.0
        name_score += 4.0 if "temp" in name else 0.0
        name_score += 4.0 if "realised" in name else 0.0
        name_score += 4.0 if "realized" in name else 0.0
        name_score += 4.0 if "observed" in name else 0.0
        name_score += 4.0 if "actual" in name else 0.0
        name_score += 3.0 if "settlement" in name else 0.0
        name_score += 3.0 if "max" in name else 0.0

        if name_score < 7.0:
            continue

        numeric = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        plausible = numeric.between(-10.0, 50.0)
        ratio = float(plausible.mean())

        if ratio < 0.40:
            continue

        score = ratio * 100.0 + name_score

        if best is None or score > best[0]:
            best = (score, column)

    return None if best is None else best[1]


def path_priority(source: str) -> float:
    lower = source.lower()
    score = 0.0

    priorities = (
        ("21e_release", 120.0),
        ("21b_full_event_book", 110.0),
        ("18y", 90.0),
        ("18s", 80.0),
        ("18n", 70.0),
        ("18o", 70.0),
        ("certified", 60.0),
        ("final", 50.0),
        ("release", 40.0),
        ("processed", 20.0),
        ("review_bundle", -10.0),
    )

    for token, value in priorities:
        if token in lower:
            score += value

    return score


def validate_partition_rows(group: pd.DataFrame) -> bool:
    """Validate one eleven-event partition using DataFrame columns directly."""

    if len(group) != 11:
        return False

    rows: List[Tuple[Optional[float], Optional[float]]] = []

    for lower_raw, upper_raw in zip(
        group["_lower_bound_c"],
        group["_upper_bound_c"],
    ):
        rows.append(
            (
                optional_float(lower_raw),
                optional_float(upper_raw),
            )
        )

    rows.sort(
        key=lambda pair: (
            -math.inf if pair[0] is None else float(pair[0])
        )
    )

    if rows[0][0] is not None:
        return False

    if rows[-1][1] is not None:
        return False

    for lower, upper in rows:
        if (
            lower is not None
            and upper is not None
            and lower >= upper
        ):
            return False

    for left, right in zip(rows[:-1], rows[1:]):
        if left[1] is None or right[0] is None:
            return False

        if not math.isclose(
            float(left[1]),
            float(right[0]),
            abs_tol=1e-8,
        ):
            return False

    return True


def derive_intervals(
    frame: pd.DataFrame,
    label_column: Optional[str],
    lower_column: Optional[str],
    upper_column: Optional[str],
) -> pd.DataFrame:
    """Derive canonical interval boundaries without named-tuple renaming."""

    result = frame.copy()
    lowers: List[Optional[float]] = []
    uppers: List[Optional[float]] = []

    for _, row in result.iterrows():
        lower = (
            optional_float(row.get(lower_column))
            if lower_column
            else None
        )

        upper = (
            optional_float(row.get(upper_column))
            if upper_column
            else None
        )

        parsed = (
            parse_interval_label(row.get(label_column))
            if label_column
            else None
        )

        if lower_column is None and upper_column is None:
            if parsed is None:
                lowers.append(None)
                uppers.append(None)
                continue

            lower, upper = parsed

        elif lower is None and upper is None and parsed is not None:
            lower, upper = parsed

        lowers.append(lower)
        uppers.append(upper)

    result["_lower_bound_c"] = lowers
    result["_upper_bound_c"] = uppers

    return result.loc[
        result["_lower_bound_c"].notna()
        | result["_upper_bound_c"].notna()
    ].copy()


def detect_identity_column(
    frame: pd.DataFrame,
    exact: Sequence[str],
    tokens: Sequence[str],
) -> Optional[str]:
    for column in exact:
        if column in frame.columns:
            return column

    best: Optional[Tuple[int, str]] = None

    for column in frame.columns:
        lower = column.lower()

        if not any(token in lower for token in tokens):
            continue

        unique = int(frame[column].astype(str).nunique())

        if best is None or unique > best[0]:
            best = (unique, column)

    return None if best is None else best[1]


def build_contract_candidate(
    table: Table,
) -> Optional[ContractCandidate]:
    frame = table.frame.copy()
    date_column = detect_date_column(frame)

    if date_column is None:
        return None

    label_column = detect_label_column(frame)
    lower_column = detect_bound_column(frame, "lower")
    upper_column = detect_bound_column(frame, "upper")

    if (
        label_column is None
        and lower_column is None
        and upper_column is None
    ):
        return None

    frame["_event_date"] = parse_dates(frame[date_column])
    frame = frame.loc[frame["_event_date"].notna()].copy()

    if frame.empty:
        return None

    frame = derive_intervals(
        frame,
        label_column,
        lower_column,
        upper_column,
    )

    if frame.empty:
        return None

    frame = frame.drop_duplicates(
        subset=[
            "_event_date",
            "_lower_bound_c",
            "_upper_bound_c",
        ],
        keep="first",
    )

    valid_groups = []

    for event_date, group in frame.groupby("_event_date"):
        if validate_partition_rows(group):
            valid_groups.append(group.copy())

    if not valid_groups:
        return None

    frame = pd.concat(valid_groups, ignore_index=True)

    event_id_column = detect_identity_column(
        frame,
        (
            "event_id",
            "outcome_id",
            "event_key",
            "contract_event_id",
        ),
        ("event_id", "outcome_id", "event_key"),
    )

    contract_id_column = detect_identity_column(
        frame,
        (
            "contract_id",
            "market_id",
            "condition_id",
            "conditionid",
            "market_slug",
            "slug",
        ),
        (
            "contract_id",
            "market_id",
            "condition_id",
            "slug",
        ),
    )

    token_id_column = detect_identity_column(
        frame,
        (
            "token_id",
            "yes_token_id",
            "clob_token_id",
            "asset_id",
        ),
        ("token_id", "asset_id"),
    )

    canonical_groups = []

    for event_date, group in frame.groupby("_event_date"):
        group = group.copy()

        group["_sort_lower"] = group["_lower_bound_c"].map(
            lambda value: (
                -math.inf if pd.isna(value) else float(value)
            )
        )

        group = group.sort_values(
            "_sort_lower",
            kind="stable",
        ).reset_index(drop=True)

        raw_event_ids = (
            group[event_id_column].astype(str)
            if event_id_column
            else pd.Series([""] * len(group))
        )

        event_ids_are_usable = (
            raw_event_ids.nunique() == 11
            and not raw_event_ids.str.lower().isin(
                {"", "nan", "none"}
            ).any()
        )

        event_ids = (
            raw_event_ids.tolist()
            if event_ids_are_usable
            else [
                f"{event_date}_event_{index:02d}"
                for index in range(11)
            ]
        )

        labels = (
            group[label_column].astype(str).tolist()
            if label_column
            else event_ids
        )

        contract_ids = (
            group[contract_id_column]
            .fillna("")
            .astype(str)
            .tolist()
            if contract_id_column
            else [""] * 11
        )

        token_ids = (
            group[token_id_column]
            .fillna("")
            .astype(str)
            .tolist()
            if token_id_column
            else [""] * 11
        )

        canonical_groups.append(
            pd.DataFrame(
                {
                    "event_date": [str(event_date)] * 11,
                    "event_id": event_ids,
                    "event_index": list(range(11)),
                    "contract_id": contract_ids,
                    "token_id": token_ids,
                    "event_label": labels,
                    "lower_bound_c": group[
                        "_lower_bound_c"
                    ].tolist(),
                    "upper_bound_c": group[
                        "_upper_bound_c"
                    ].tolist(),
                    "lower_closed": [True] * 11,
                    "upper_closed": [False] * 11,
                    "settlement_source": [
                        "Hong Kong Observatory Daily Extract"
                    ]
                    * 11,
                    "metadata_retrieved_utc": [
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                    ]
                    * 11,
                }
            )
        )

    canonical = pd.concat(
        canonical_groups,
        ignore_index=True,
    )

    valid_dates = int(
        canonical["event_date"].nunique()
    )

    identifier_score = 0.0
    identifier_score += 30.0 if contract_id_column else 0.0
    identifier_score += 30.0 if token_id_column else 0.0
    identifier_score += 20.0 if event_id_column else 0.0
    identifier_score += 20.0 if label_column else 0.0

    score = (
        valid_dates * 10000.0
        + identifier_score
        + path_priority(table.source)
    )

    return ContractCandidate(
        source=table.source,
        frame=canonical,
        source_sha256=table.source_sha256,
        date_column=date_column,
        label_column=label_column or "",
        lower_column=lower_column or "",
        upper_column=upper_column or "",
        valid_dates=valid_dates,
        rows=len(canonical),
        score=score,
    )


def build_hko_candidate(
    table: Table,
) -> Optional[HkoCandidate]:
    frame = table.frame.copy()
    date_column = detect_date_column(frame)

    if date_column is None:
        return None

    temperature_column = detect_hko_temperature_column(
        frame,
        date_column,
    )

    if temperature_column is None:
        return None

    dates = parse_dates(frame[date_column])
    temperatures = pd.to_numeric(
        frame[temperature_column],
        errors="coerce",
    )

    candidate = pd.DataFrame(
        {
            "event_date": dates,
            "hko_daily_max_c": temperatures,
        }
    )

    candidate = candidate.loc[
        candidate["event_date"].notna()
        & candidate["hko_daily_max_c"].between(
            -10.0,
            50.0,
        )
    ].copy()

    if candidate.empty:
        return None

    conflicts = (
        candidate.groupby("event_date")[
            "hko_daily_max_c"
        ]
        .nunique()
    )

    if (conflicts > 1).any():
        return None

    candidate = candidate.drop_duplicates(
        subset=["event_date"],
        keep="first",
    ).sort_values("event_date")

    valid_dates = int(
        candidate["event_date"].nunique()
    )

    if valid_dates < 5:
        return None

    canonical = pd.DataFrame(
        {
            "event_date": candidate[
                "event_date"
            ].astype(str),
            "hko_daily_max_c": candidate[
                "hko_daily_max_c"
            ].astype(float),
            "source_reference": [table.source] * len(candidate),
            "source_retrieved_utc": [
                datetime.now(timezone.utc).isoformat()
            ]
            * len(candidate),
            "outcome_admissible_utc": [""] * len(candidate),
            "availability_basis": [
                (
                    "Historical HKO outcome source. "
                    "Forecast-time admissibility is audited in Notebook 02."
                )
            ]
            * len(candidate),
        }
    )

    score = (
        valid_dates * 10000.0
        + path_priority(table.source)
    )

    return HkoCandidate(
        source=table.source,
        frame=canonical,
        source_sha256=table.source_sha256,
        date_column=date_column,
        temperature_column=temperature_column,
        valid_dates=valid_dates,
        rows=len(canonical),
        score=score,
    )


def classify(
    group: pd.DataFrame,
    temperature: float,
) -> int:
    winners = []

    for index, row in group.iterrows():
        lower = optional_float(row["lower_bound_c"])
        upper = optional_float(row["upper_bound_c"])

        lower_ok = True if lower is None else temperature >= lower
        upper_ok = True if upper is None else temperature < upper

        if lower_ok and upper_ok:
            winners.append(index)

    if len(winners) != 1:
        raise ValueError(
            f"Temperature {temperature} belongs to "
            f"{len(winners)} events."
        )

    return winners[0]


def validate_pair(
    contract: ContractCandidate,
    hko: HkoCandidate,
) -> Dict[str, Any]:
    contracts = contract.frame.copy()
    outcomes = hko.frame.copy()

    common_dates = sorted(
        set(contracts["event_date"])
        & set(outcomes["event_date"])
    )

    if len(common_dates) < MIN_COMMON_DATES:
        raise ValueError(
            f"Only {len(common_dates)} common dates."
        )

    contracts = contracts.loc[
        contracts["event_date"].isin(common_dates)
    ].copy()

    outcomes = outcomes.loc[
        outcomes["event_date"].isin(common_dates)
    ].copy()

    temperature_map = dict(
        zip(
            outcomes["event_date"],
            outcomes["hko_daily_max_c"],
        )
    )

    preview_rows = []

    for event_date, group in contracts.groupby("event_date"):
        if len(group) != 11:
            raise ValueError(
                f"{event_date} has {len(group)} events."
            )

        temperature = float(
            temperature_map[event_date]
        )

        winner_index = classify(
            group,
            temperature,
        )

        preview_rows.append(
            {
                "event_date": event_date,
                "hko_daily_max_c": temperature,
                "winning_event_id": str(
                    group.loc[winner_index, "event_id"]
                ),
            }
        )

    end_date = max(common_dates)

    return {
        "contracts": contracts,
        "hko": outcomes,
        "common_dates": len(common_dates),
        "start_date": min(common_dates),
        "end_date": end_date,
        "preview": preview_rows,
        "pair_score": (
            len(common_dates) * 1_000_000_000
            + pd.Timestamp(end_date).toordinal() * 1_000_000
            + contract.score
            + hko.score
        ),
    }


def read_csv_payload(
    payload: bytes,
) -> Optional[pd.DataFrame]:
    attempts = (
        {},
        {"encoding": "utf-8-sig"},
        {"encoding": "latin-1"},
    )

    for kwargs in attempts:
        try:
            frame = pd.read_csv(
                io.BytesIO(payload),
                low_memory=False,
                **kwargs,
            )

            if not frame.empty:
                return normalise_columns(frame)

        except Exception:
            continue

    return None


def tables_from_json(
    source: str,
    payload: bytes,
) -> List[Table]:
    try:
        parsed = json.loads(
            payload.decode("utf-8")
        )
    except Exception:
        return []

    objects: List[Any] = []

    if isinstance(parsed, list):
        objects.append(parsed)

    elif isinstance(parsed, dict):
        for key in (
            "data",
            "rows",
            "records",
            "results",
            "events",
            "contracts",
            "outcomes",
            "markets",
        ):
            value = parsed.get(key)

            if isinstance(value, list):
                objects.append(value)

    tables: List[Table] = []

    for index, obj in enumerate(objects, start=1):
        try:
            frame = pd.DataFrame(obj)
        except Exception:
            continue

        if frame.empty:
            continue

        tables.append(
            Table(
                source=f"{source}::json_table_{index}",
                frame=normalise_columns(frame),
                source_sha256=sha256_bytes(payload),
            )
        )

    return tables


def load_archive_tables() -> List[Table]:
    paths = git_text(
        "ls-tree",
        "-r",
        "--name-only",
        ARCHIVE_BRANCH,
    ).splitlines()

    extensions = (".csv", ".json", ".zip")

    keywords = (
        "hko",
        "contract",
        "event",
        "settlement",
        "outcome",
        "certified",
        "full_event_book",
        "release",
        "review_bundle",
    )

    candidates = [
        path
        for path in paths
        if path.lower().endswith(extensions)
        and any(
            keyword in path.lower()
            for keyword in keywords
        )
    ]

    tables: List[Table] = []

    for index, path in enumerate(
        sorted(candidates),
        start=1,
    ):
        print(
            f"[{index:03d}/{len(candidates):03d}] "
            f"Inspecting {path}",
            flush=True,
        )

        try:
            size = int(
                git_text(
                    "cat-file",
                    "-s",
                    f"{ARCHIVE_BRANCH}:{path}",
                ).strip()
            )
        except Exception:
            continue

        if size > MAX_FILE_BYTES:
            continue

        try:
            payload = git_bytes(
                "show",
                f"{ARCHIVE_BRANCH}:{path}",
            )
        except Exception:
            continue

        lower = path.lower()

        if lower.endswith(".csv"):
            frame = read_csv_payload(payload)

            if frame is not None:
                tables.append(
                    Table(
                        source=path,
                        frame=frame,
                        source_sha256=sha256_bytes(payload),
                    )
                )

        elif lower.endswith(".json"):
            tables.extend(
                tables_from_json(
                    path,
                    payload,
                )
            )

        elif lower.endswith(".zip"):
            try:
                archive = zipfile.ZipFile(
                    io.BytesIO(payload)
                )
            except zipfile.BadZipFile:
                continue

            with archive:
                for member in archive.infolist():
                    if (
                        member.is_dir()
                        or member.file_size > MAX_ZIP_MEMBER_BYTES
                    ):
                        continue

                    member_name = member.filename
                    member_lower = member_name.lower()

                    if not member_lower.endswith(
                        (".csv", ".json")
                    ):
                        continue

                    try:
                        member_payload = archive.read(member)
                    except Exception:
                        continue

                    member_source = (
                        f"{path}::{member_name}"
                    )

                    if member_lower.endswith(".csv"):
                        frame = read_csv_payload(
                            member_payload
                        )

                        if frame is not None:
                            tables.append(
                                Table(
                                    source=member_source,
                                    frame=frame,
                                    source_sha256=sha256_bytes(
                                        member_payload
                                    ),
                                )
                            )

                    else:
                        tables.extend(
                            tables_from_json(
                                member_source,
                                member_payload,
                            )
                        )

    return tables


def main() -> None:
    tables = load_archive_tables()

    contract_candidates: List[ContractCandidate] = []
    hko_candidates: List[HkoCandidate] = []

    for table in tables:
        try:
            contract = build_contract_candidate(table)

            if contract is not None:
                contract_candidates.append(contract)
        except Exception:
            pass

        try:
            hko = build_hko_candidate(table)

            if hko is not None:
                hko_candidates.append(hko)
        except Exception:
            pass

    contract_candidates.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    hko_candidates.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    audit_rows: List[Dict[str, Any]] = []

    for rank, item in enumerate(
        contract_candidates,
        start=1,
    ):
        audit_rows.append(
            {
                "candidate_type": "contract",
                "rank": rank,
                "source": item.source,
                "valid_dates": item.valid_dates,
                "rows": item.rows,
                "date_column": item.date_column,
                "temperature_column": "",
                "label_column": item.label_column,
                "lower_column": item.lower_column,
                "upper_column": item.upper_column,
                "score": item.score,
            }
        )

    for rank, item in enumerate(
        hko_candidates,
        start=1,
    ):
        audit_rows.append(
            {
                "candidate_type": "hko",
                "rank": rank,
                "source": item.source,
                "valid_dates": item.valid_dates,
                "rows": item.rows,
                "date_column": item.date_column,
                "temperature_column": item.temperature_column,
                "label_column": "",
                "lower_column": "",
                "upper_column": "",
                "score": item.score,
            }
        )

    diagnostics = Path("outputs/diagnostics")
    diagnostics.mkdir(parents=True, exist_ok=True)

    audit_path = (
        diagnostics
        / "01_source_schema_audit.csv"
    )

    pd.DataFrame(audit_rows).to_csv(
        audit_path,
        index=False,
    )

    if not contract_candidates:
        raise RuntimeError(
            "No structurally valid eleven-event contract table was found. "
            "See outputs/diagnostics/01_source_schema_audit.csv."
        )

    if not hko_candidates:
        raise RuntimeError(
            "No structurally valid HKO outcome table was found. "
            "See outputs/diagnostics/01_source_schema_audit.csv."
        )

    valid_pairs = []

    for contract in contract_candidates[:30]:
        for hko in hko_candidates[:30]:
            try:
                validation = validate_pair(
                    contract,
                    hko,
                )
            except Exception:
                continue

            valid_pairs.append(
                (
                    validation["pair_score"],
                    contract,
                    hko,
                    validation,
                )
            )

    if not valid_pairs:
        raise RuntimeError(
            "Candidate sources were found, but no pair passed the "
            f"{MIN_COMMON_DATES}-date, eleven-event and one-winner tests. "
            "See outputs/diagnostics/01_source_schema_audit.csv."
        )

    valid_pairs.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    _, contract, hko, validation = valid_pairs[0]

    contract_output = Path(
        "data/interim/"
        "canonical_contract_definitions.csv"
    )

    hko_output = Path(
        "data/interim/hko_daily_max.csv"
    )

    contract_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    validation["contracts"].to_csv(
        contract_output,
        index=False,
    )

    validation["hko"].to_csv(
        hko_output,
        index=False,
    )

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "archive_branch": ARCHIVE_BRANCH,
        "tables_inspected": len(tables),
        "contract_candidates_found": len(
            contract_candidates
        ),
        "hko_candidates_found": len(
            hko_candidates
        ),
        "selected_contract_source": {
            "source": contract.source,
            "source_sha256": contract.source_sha256,
            "date_column": contract.date_column,
            "label_column": contract.label_column,
            "lower_column": contract.lower_column,
            "upper_column": contract.upper_column,
            "valid_dates_before_pairing": (
                contract.valid_dates
            ),
        },
        "selected_hko_source": {
            "source": hko.source,
            "source_sha256": hko.source_sha256,
            "date_column": hko.date_column,
            "temperature_column": (
                hko.temperature_column
            ),
            "valid_dates_before_pairing": (
                hko.valid_dates
            ),
        },
        "selected_pair": {
            "common_dates": validation[
                "common_dates"
            ],
            "start_date": validation["start_date"],
            "end_date": validation["end_date"],
            "contract_rows": len(
                validation["contracts"]
            ),
            "hko_rows": len(validation["hko"]),
            "all_dates_have_11_events": True,
            "all_dates_have_one_winner": True,
        },
        "canonical_outputs": {
            str(contract_output): {
                "sha256": sha256_file(
                    contract_output
                ),
                "rows": len(
                    validation["contracts"]
                ),
            },
            str(hko_output): {
                "sha256": sha256_file(
                    hko_output
                ),
                "rows": len(validation["hko"]),
            },
        },
    }

    manifest_path = Path(
        "data/manifests/"
        "01_source_migration_manifest.json"
    )

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    selection_report = {
        "status": "REAL_SOURCES_MIGRATED",
        "contract_source": contract.source,
        "hko_source": hko.source,
        **manifest["selected_pair"],
    }

    selection_path = (
        diagnostics
        / "01_source_selection_report.json"
    )

    selection_path.write_text(
        json.dumps(
            selection_report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("REAL SOURCE MIGRATION PASSED")
    print("Contract source:")
    print(f"  {contract.source}")
    print("HKO source:")
    print(f"  {hko.source}")
    print(
        "Common certified dates:",
        validation["common_dates"],
    )
    print(
        "Date range:",
        validation["start_date"],
        "to",
        validation["end_date"],
    )
    print(
        "Contract rows:",
        len(validation["contracts"]),
    )
    print("HKO rows:", len(validation["hko"]))
    print(f"Manifest: {manifest_path}")
    print(f"Schema audit: {audit_path}")
    print(f"Selection report: {selection_path}")


if __name__ == "__main__":
    main()
