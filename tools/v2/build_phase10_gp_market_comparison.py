#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import t as student_t
from scipy.stats import ttest_1samp


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
      "phase10_gp_market_comparison_spec.json"
)

DATE_COLUMNS = [
    "target_date",
    "event_date",
    "contract_date",
    "settlement_date",
    "date",
    "market_date",
]

RULE_COLUMNS = [
    "decision_rule",
    "current_decision_rule",
    "decision_time_rule",
    "snapshot_rule",
    "rule",
]

IDENTIFIER_COLUMNS = [
    "contract_key",
    "source_contract_id",
    "condition_id",
    "contract_id",
    "market_id",
    "token_id",
    "event_id",
    "market_slug",
    "slug",
    "ticker",
]

LABEL_COLUMNS = [
    "event_label",
    "contract_label",
    "outcome_label",
    "market_question",
    "question",
    "title",
    "event_name",
    "contract_name",
    "market_title",
]

LOWER_BOUND_COLUMNS = [
    "lower_bound_c",
    "event_lower_bound_c",
    "contract_lower_bound_c",
    "temperature_lower_bound_c",
    "lower_threshold_c",
    "threshold_lower_c",
    "bucket_lower_c",
    "bin_lower_c",
    "range_lower_c",
    "lower_c",
    "lower_bound",
]

UPPER_BOUND_COLUMNS = [
    "upper_bound_c",
    "event_upper_bound_c",
    "contract_upper_bound_c",
    "temperature_upper_bound_c",
    "upper_threshold_c",
    "threshold_upper_c",
    "bucket_upper_c",
    "bin_upper_c",
    "range_upper_c",
    "upper_c",
    "upper_bound",
]

PRICE_COLUMN_PRIORITY = [
    "market_probability",
    "market_probability_raw",
    "polymarket_probability",
    "polymarket_yes_probability",
    "market_implied_probability",
    "decision_probability",
    "decision_yes_probability",
    "decision_price",
    "decision_yes_price",
    "market_yes_price",
    "yes_token_price",
    "yes_probability",
    "probability_yes",
    "yes_price",
    "selected_price",
    "snapshot_price",
    "current_price",
    "market_price",
    "mid_price",
    "yes_mid_price",
    "price",
    "probability",
    "p_market",
    "p_mkt",
]

RULE_ALIASES = {
    "24h": "24h_prior",
    "24hr": "24h_prior",
    "24_hour": "24h_prior",
    "24_hours": "24h_prior",
    "24hprior": "24h_prior",
    "24_hours_prior": "24h_prior",
    "12h": "12h_prior",
    "12hr": "12h_prior",
    "12_hour": "12h_prior",
    "12_hours": "12h_prior",
    "12hprior": "12h_prior",
    "12_hours_prior": "12h_prior",
    "6h": "6h_prior",
    "6hr": "6h_prior",
    "6_hour": "6h_prior",
    "6_hours": "6h_prior",
    "6hprior": "6h_prior",
    "6_hours_prior": "6h_prior",
    "open": "event_day_open",
    "event_open": "event_day_open",
    "eventdayopen": "event_day_open",
    "event_day": "event_day_open",
    "event_day_opening": "event_day_open",
}

EXCLUDED_PRICE_FRAGMENTS = [
    "brier",
    "log_score",
    "loss",
    "outcome",
    "realised",
    "realized",
    "gp_",
    "ecmwf",
    "catboost",
    "lightgbm",
    "forecast_probability",
    "model_probability",
    "available",
    "availability",
    "missing",
    "valid",
    "validity",
    "flag",
    "check",
    "present",
    "status",
    "usable",
    "ready",
    "success",
    "failed",
    "failure",
    "issue",
]

MARKET_PATH_HINTS = [
    "market",
    "price",
    "polymarket",
    "decision",
    "18l",
    "18m",
]

METRICS = {
    "binary_brier_raw": {
        "gp": "gp_binary_brier_mean",
        "market": "market_binary_brier_raw_mean",
        "label": "Mean binary Brier",
        "primary": True
    },
    "binary_log_raw": {
        "gp": "gp_binary_log_mean",
        "market": "market_binary_log_raw_mean",
        "label": "Mean binary log",
        "primary": True
    },
    "categorical_log": {
        "gp": "gp_categorical_log",
        "market": "market_categorical_log",
        "label": "Categorical log",
        "primary": True
    },
    "multiclass_brier": {
        "gp": "gp_multiclass_brier",
        "market": "market_multiclass_brier",
        "label": "Multiclass Brier",
        "primary": True
    },
    "binary_brier_normalised": {
        "gp": "gp_binary_brier_mean",
        "market": "market_binary_brier_normalised_mean",
        "label": "Mean binary Brier, normalised market",
        "primary": False
    },
    "binary_log_normalised": {
        "gp": "gp_binary_log_mean",
        "market": "market_binary_log_normalised_mean",
        "label": "Mean binary log, normalised market",
        "primary": False
    }
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def first_existing(
    columns: pd.Index,
    candidates: list[str],
) -> str | None:
    return next(
        (
            column
            for column in candidates
            if column in columns
        ),
        None,
    )


def parse_dates(series: pd.Series) -> pd.Series:
    return (
        pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
            utc=True,
        )
        .dt.tz_convert(None)
        .dt.normalize()
    )


def normalise_rules(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
        .replace(RULE_ALIASES)
    )


def normalise_identifier(series: pd.Series) -> pd.Series:
    result = (
        series.astype(str)
        .str.strip()
        .str.lower()
    )

    result = result.str.replace(
        r"^(\d+)\.0$",
        r"\1",
        regex=True,
    )

    result = result.mask(
        result.isin(
            {
                "",
                "nan",
                "none",
                "<na>",
                "null",
            }
        )
    )

    return result


def normalise_label(series: pd.Series) -> pd.Series:
    result = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(
            r"\s+",
            " ",
            regex=True,
        )
    )

    return result.mask(
        result.isin(
            {
                "",
                "nan",
                "none",
                "<na>",
                "null",
            }
        )
    )


def coerce_bound(series: pd.Series) -> pd.Series:
    text = (
        series.astype(str)
        .str.strip()
        .str.lower()
    )

    values = pd.to_numeric(
        text,
        errors="coerce",
    )

    values.loc[
        text.isin(
            {
                "-inf",
                "-infinity",
                "negative_infinity",
            }
        )
    ] = -np.inf

    values.loc[
        text.isin(
            {
                "inf",
                "+inf",
                "infinity",
                "+infinity",
                "positive_infinity",
            }
        )
    ] = np.inf

    return values


def parse_label_bounds(
    value: object,
) -> tuple[float, float]:
    if value is None:
        return np.nan, np.nan

    text = str(value).strip().lower()

    if not text:
        return np.nan, np.nan

    text = (
        text.replace("℃", "°c")
        .replace("degrees celsius", "°c")
        .replace("degree celsius", "°c")
        .replace("degrees c", "°c")
        .replace("degree c", "°c")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )

    number = r"(-?\d+(?:\.\d+)?)"

    interval_patterns = [
        (
            rf"between\s+{number}"
            rf"\s*(?:°\s*c|c)?"
            rf"\s+(?:and|to)\s+{number}"
            rf"\s*(?:°\s*c|c)"
        ),
        (
            rf"{number}"
            rf"\s*(?:°\s*c|c)?"
            rf"\s*(?:-|to)\s*{number}"
            rf"\s*(?:°\s*c|c)"
        ),
    ]

    for pattern in interval_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            lower = float(match.group(1))
            upper = float(match.group(2))

            if upper > lower:
                return lower, upper

    upper_tail = re.search(
        rf"{number}\s*(?:°\s*c|c)"
        rf"\s*(?:or\s+)?"
        rf"(?:higher|above|more|\+)",
        text,
        flags=re.IGNORECASE,
    )

    if upper_tail:
        return (
            float(upper_tail.group(1)),
            np.inf,
        )

    lower_tail = re.search(
        rf"{number}\s*(?:°\s*c|c)"
        rf"\s*(?:or\s+)?"
        rf"(?:lower|below|less)",
        text,
        flags=re.IGNORECASE,
    )

    if lower_tail:
        labelled_maximum = float(
            lower_tail.group(1)
        )

        return (
            -np.inf,
            labelled_maximum + 1.0,
        )

    below_boundary = re.search(
        rf"(?:below|under|less\s+than)"
        rf"\s*{number}\s*(?:°\s*c|c)",
        text,
        flags=re.IGNORECASE,
    )

    if below_boundary:
        return (
            -np.inf,
            float(below_boundary.group(1)),
        )

    above_boundary = re.search(
        rf"(?:above|over|more\s+than|higher\s+than)"
        rf"\s*{number}\s*(?:°\s*c|c)",
        text,
        flags=re.IGNORECASE,
    )

    if above_boundary:
        return (
            float(above_boundary.group(1)),
            np.inf,
        )

    single_values = re.findall(
        rf"{number}\s*(?:°\s*c|c)",
        text,
        flags=re.IGNORECASE,
    )

    if len(single_values) == 1:
        lower = float(single_values[0])
        return lower, lower + 1.0

    return np.nan, np.nan


def rule_from_wide_column(
    column: str,
) -> str | None:
    name = column.lower()

    if not any(
        fragment in name
        for fragment in [
            "price",
            "prob",
            "yes",
            "market",
        ]
    ):
        return None

    if "24h" in name or "24_hour" in name:
        return "24h_prior"

    if "12h" in name or "12_hour" in name:
        return "12h_prior"

    if (
        re.search(
            r"(^|[^0-9])6h",
            name,
        )
        or "6_hour" in name
    ):
        return "6h_prior"

    if (
        "event_day_open" in name
        or "event_open" in name
        or "opening" in name
        or re.search(
            r"(^|_)open($|_)",
            name,
        )
    ):
        return "event_day_open"

    return None


def candidate_paths() -> list[Path]:
    roots = [
        ROOT / "data/processed",
        ROOT / "data/interim",
        ROOT / "outputs",
        ROOT / "artifacts",
    ]

    paths: list[Path] = []

    for search_root in roots:
        if not search_root.exists():
            continue

        for pattern in [
            "*.csv",
            "*.csv.gz",
        ]:
            for path in search_root.rglob(pattern):
                lower = str(path).lower()

                if any(
                    fragment in lower
                    for fragment in [
                        "phase8_clean_gp",
                        "phase9_gp_event_probabilities",
                        "phase10_gp_market_comparison",
                    ]
                ):
                    continue

                if not any(
                    hint in lower
                    for hint in MARKET_PATH_HINTS
                ):
                    continue

                try:
                    if path.stat().st_size > 250_000_000:
                        continue
                except OSError:
                    continue

                paths.append(path)

    return sorted(set(paths))


def detected_price_columns(
    columns: pd.Index,
) -> list[str]:
    result: list[str] = []

    for preferred in PRICE_COLUMN_PRIORITY:
        if preferred in columns:
            result.append(preferred)

    for column in columns:
        lower = column.lower()

        if column in result:
            continue

        if any(
            fragment in lower
            for fragment in EXCLUDED_PRICE_FRAGMENTS
        ):
            continue

        if (
            any(
                fragment in lower
                for fragment in [
                    "market",
                    "price",
                    "prob",
                ]
            )
            and any(
                fragment in lower
                for fragment in [
                    "yes",
                    "market",
                    "decision",
                    "snapshot",
                    "mid",
                    "price",
                ]
            )
        ):
            result.append(column)

    return result


def convert_price(
    series: pd.Series,
    column_name: str,
) -> pd.Series:
    """Convert a genuine probability column to floating point.

    Boolean columns and availability or integrity indicators are
    rejected rather than interpreted as probabilities equal to zero
    or one.
    """

    lower = column_name.lower()

    indicator_fragments = {
        "available",
        "availability",
        "missing",
        "valid",
        "validity",
        "flag",
        "check",
        "present",
        "status",
        "usable",
        "ready",
        "success",
        "failed",
        "failure",
        "issue",
    }

    if pd.api.types.is_bool_dtype(
        series.dtype
    ):
        return pd.Series(
            np.nan,
            index=series.index,
            dtype=float,
        )

    if any(
        fragment in lower
        for fragment in indicator_fragments
    ):
        return pd.Series(
            np.nan,
            index=series.index,
            dtype=float,
        )

    values = pd.to_numeric(
        series,
        errors="coerce",
    )

    values = values.astype(
        float
    )

    if (
        "percent" in lower
        or "percentage" in lower
        or re.search(
            r"(^|_)pct($|_)",
            lower,
        )
    ):
        values = values / 100.0

    values = values.where(
        np.isfinite(values)
    )

    return values


def build_candidate_frames(
    path: Path,
    expected_rules: list[str],
    minimum_date: pd.Timestamp,
    maximum_date: pd.Timestamp,
) -> list[
    tuple[
        dict[str, Any],
        pd.DataFrame,
    ]
]:
    try:
        header = pd.read_csv(
            path,
            nrows=0,
        ).columns
    except Exception:
        return []

    date_column = first_existing(
        header,
        DATE_COLUMNS,
    )

    if date_column is None:
        return []

    rule_column = first_existing(
        header,
        RULE_COLUMNS,
    )

    price_columns = detected_price_columns(
        header
    )

    wide_rule_prices = {
        column: rule_from_wide_column(column)
        for column in header
    }

    wide_rule_prices = {
        column: rule
        for column, rule in wide_rule_prices.items()
        if rule is not None
    }

    if (
        not price_columns
        and not wide_rule_prices
    ):
        return []

    try:
        raw = pd.read_csv(
            path,
            low_memory=False,
        )
    except Exception:
        return []

    identifier_columns = [
        column
        for column in IDENTIFIER_COLUMNS
        if column in raw.columns
    ]

    label_column = first_existing(
        raw.columns,
        LABEL_COLUMNS,
    )

    lower_column = first_existing(
        raw.columns,
        LOWER_BOUND_COLUMNS,
    )

    upper_column = first_existing(
        raw.columns,
        UPPER_BOUND_COLUMNS,
    )

    frames: list[
        tuple[
            dict[str, Any],
            pd.DataFrame,
        ]
    ] = []

    def base_frame() -> pd.DataFrame:
        frame = pd.DataFrame(
            {
                "target_date":
                    parse_dates(
                        raw[date_column]
                    ),
            }
        )

        for identifier in identifier_columns:
            frame[
                f"id::{identifier}"
            ] = normalise_identifier(
                raw[identifier]
            )

        if label_column is not None:
            frame[
                "label_normalised"
            ] = normalise_label(
                raw[label_column]
            )
        else:
            frame[
                "label_normalised"
            ] = pd.NA

        if lower_column is not None:
            frame[
                "lower_bound_c"
            ] = coerce_bound(
                raw[lower_column]
            )
        else:
            frame[
                "lower_bound_c"
            ] = np.nan

        if upper_column is not None:
            frame[
                "upper_bound_c"
            ] = coerce_bound(
                raw[upper_column]
            )
        else:
            frame[
                "upper_bound_c"
            ] = np.nan

        if label_column is not None:
            parsed = raw[
                label_column
            ].apply(
                parse_label_bounds
            )

            parsed_lower = parsed.apply(
                lambda item: item[0]
            )

            parsed_upper = parsed.apply(
                lambda item: item[1]
            )

            frame[
                "lower_bound_c"
            ] = frame[
                "lower_bound_c"
            ].where(
                frame[
                    "lower_bound_c"
                ].notna(),
                parsed_lower,
            )

            frame[
                "upper_bound_c"
            ] = frame[
                "upper_bound_c"
            ].where(
                frame[
                    "upper_bound_c"
                ].notna(),
                parsed_upper,
            )

        return frame

    if rule_column is not None:
        for price_column in price_columns:
            frame = base_frame()

            frame[
                "decision_rule"
            ] = normalise_rules(
                raw[rule_column]
            )

            frame[
                "market_probability_raw"
            ] = convert_price(
                raw[price_column],
                price_column,
            )

            frame = frame.loc[
                frame[
                    "target_date"
                ].between(
                    minimum_date,
                    maximum_date,
                )
                & frame[
                    "decision_rule"
                ].isin(
                    expected_rules
                )
                & np.isfinite(
                    frame[
                        "market_probability_raw"
                    ]
                )
                & frame[
                    "market_probability_raw"
                ].between(
                    0.0,
                    1.0,
                )
            ].copy()

            if frame.empty:
                continue

            frames.append(
                (
                    {
                        "path": path,
                        "date_column": date_column,
                        "rule_column": rule_column,
                        "price_column": price_column,
                        "format": "long",
                        "identifier_columns":
                            identifier_columns,
                        "label_column": label_column,
                        "lower_column": lower_column,
                        "upper_column": upper_column,
                    },
                    frame,
                )
            )

    if rule_column is None and wide_rule_prices:
        for price_column, decision_rule in (
            wide_rule_prices.items()
        ):
            frame = base_frame()

            frame[
                "decision_rule"
            ] = decision_rule

            frame[
                "market_probability_raw"
            ] = convert_price(
                raw[price_column],
                price_column,
            )

            frame = frame.loc[
                frame[
                    "target_date"
                ].between(
                    minimum_date,
                    maximum_date,
                )
                & np.isfinite(
                    frame[
                        "market_probability_raw"
                    ]
                )
                & frame[
                    "market_probability_raw"
                ].between(
                    0.0,
                    1.0,
                )
            ].copy()

            if frame.empty:
                continue

            frames.append(
                (
                    {
                        "path": path,
                        "date_column": date_column,
                        "rule_column": None,
                        "price_column": price_column,
                        "format": "wide",
                        "wide_rule": decision_rule,
                        "identifier_columns":
                            identifier_columns,
                        "label_column": label_column,
                        "lower_column": lower_column,
                        "upper_column": upper_column,
                    },
                    frame,
                )
            )

    return frames


def path_bonus(path: Path) -> int:
    lower = str(path).lower()

    bonus = 0

    bonus += 80 if "18l" in lower else 0
    bonus += 50 if "decision" in lower else 0
    bonus += 40 if "recovery" in lower else 0
    bonus += 25 if "market" in lower else 0
    bonus += 20 if "price" in lower else 0
    bonus += 10 if "polymarket" in lower else 0

    bonus -= 80 if "summary" in lower else 0
    bonus -= 60 if "score" in lower else 0
    bonus -= 40 if "diagnostic" in lower else 0

    return bonus


def collapse_matched_prices(
    matched: pd.DataFrame,
) -> pd.DataFrame | None:
    """Collapse repeated observations only when prices agree."""

    key_columns = [
        "target_date",
        "decision_rule",
        "contract_key",
    ]

    working = matched.copy()

    working[
        "market_probability_raw"
    ] = pd.to_numeric(
        working[
            "market_probability_raw"
        ],
        errors="coerce",
    ).astype(
        float
    )

    working = working.loc[
        working[
            "market_probability_raw"
        ].notna()
        & np.isfinite(
            working[
                "market_probability_raw"
            ]
        )
        & working[
            "market_probability_raw"
        ].between(
            0.0,
            1.0,
        )
    ].copy()

    if working.empty:
        return None

    conflict_check = (
        working.groupby(
            key_columns
        )[
            "market_probability_raw"
        ]
        .agg(
            minimum="min",
            maximum="max",
            observations="size",
        )
        .reset_index()
    )

    minimum = pd.to_numeric(
        conflict_check[
            "minimum"
        ],
        errors="coerce",
    ).astype(
        float
    )

    maximum = pd.to_numeric(
        conflict_check[
            "maximum"
        ],
        errors="coerce",
    ).astype(
        float
    )

    if (
        minimum.isna().any()
        or maximum.isna().any()
        or not np.isfinite(
            minimum
        ).all()
        or not np.isfinite(
            maximum
        ).all()
    ):
        return None

    conflicts = (
        maximum - minimum
    ).abs().gt(
        1e-10
    )

    if conflicts.any():
        return None

    collapsed = (
        working.sort_values(
            key_columns,
            kind="stable",
        )
        .drop_duplicates(
            key_columns,
            keep="first",
        )
        [
            key_columns
            + [
                "market_probability_raw",
            ]
        ]
        .reset_index(drop=True)
    )

    return collapsed


def evaluate_match(
    canonical: pd.DataFrame,
    matched: pd.DataFrame,
) -> dict[str, int]:
    key_columns = [
        "target_date",
        "decision_rule",
        "contract_key",
    ]

    matched = matched.drop_duplicates(
        key_columns
    )

    expected_counts = (
        canonical.groupby(
            [
                "target_date",
                "decision_rule",
            ]
        )
        .size()
        .rename(
            "expected_event_count"
        )
    )

    matched_counts = (
        matched.groupby(
            [
                "target_date",
                "decision_rule",
            ]
        )
        .size()
        .rename(
            "matched_event_count"
        )
    )

    counts = pd.concat(
        [
            expected_counts,
            matched_counts,
        ],
        axis=1,
    ).fillna(
        0
    )

    complete = counts.loc[
        counts[
            "matched_event_count"
        ].eq(
            counts[
                "expected_event_count"
            ]
        )
        & counts[
            "expected_event_count"
        ].gt(0)
    ]

    return {
        "matched_rows":
            int(
                len(matched)
            ),
        "matched_date_rule_books":
            int(
                len(matched_counts)
            ),
        "complete_books":
            int(
                len(complete)
            ),
        "complete_dates":
            int(
                complete.reset_index()[
                    "target_date"
                ].nunique()
            ),
    }


def matching_strategies(
    canonical: pd.DataFrame,
    candidate: pd.DataFrame,
    metadata: dict[str, Any],
) -> list[
    tuple[
        str,
        pd.DataFrame,
    ]
]:
    strategies: list[
        tuple[
            str,
            pd.DataFrame,
        ]
    ] = []

    base_columns = [
        "target_date",
        "decision_rule",
        "contract_key",
    ]

    for source_column in [
        "source_contract_id_normalised",
        "contract_key_normalised",
    ]:
        if source_column not in canonical.columns:
            continue

        for identifier in metadata[
            "identifier_columns"
        ]:
            candidate_column = (
                f"id::{identifier}"
            )

            if candidate_column not in candidate.columns:
                continue

            left = canonical[
                base_columns
                + [
                    source_column,
                ]
            ].dropna(
                subset=[
                    source_column,
                ]
            )

            right = candidate[
                [
                    "target_date",
                    "decision_rule",
                    candidate_column,
                    "market_probability_raw",
                ]
            ].dropna(
                subset=[
                    candidate_column,
                ]
            )

            merged = left.merge(
                right,
                left_on=[
                    "target_date",
                    "decision_rule",
                    source_column,
                ],
                right_on=[
                    "target_date",
                    "decision_rule",
                    candidate_column,
                ],
                how="inner",
            )

            collapsed = collapse_matched_prices(
                merged[
                    base_columns
                    + [
                        "market_probability_raw",
                    ]
                ]
            )

            if collapsed is not None:
                strategies.append(
                    (
                        f"{source_column}"
                        f"_to_{identifier}",
                        collapsed,
                    )
                )

    if (
        "label_normalised" in candidate.columns
        and "event_label_normalised"
        in canonical.columns
    ):
        left = canonical[
            base_columns
            + [
                "event_label_normalised",
            ]
        ].dropna(
            subset=[
                "event_label_normalised",
            ]
        )

        right = candidate[
            [
                "target_date",
                "decision_rule",
                "label_normalised",
                "market_probability_raw",
            ]
        ].dropna(
            subset=[
                "label_normalised",
            ]
        )

        merged = left.merge(
            right,
            left_on=[
                "target_date",
                "decision_rule",
                "event_label_normalised",
            ],
            right_on=[
                "target_date",
                "decision_rule",
                "label_normalised",
            ],
            how="inner",
        )

        collapsed = collapse_matched_prices(
            merged[
                base_columns
                + [
                    "market_probability_raw",
                ]
            ]
        )

        if collapsed is not None:
            strategies.append(
                (
                    "normalised_event_label",
                    collapsed,
                )
            )

    if (
        candidate[
            "lower_bound_c"
        ].notna().any()
        and candidate[
            "upper_bound_c"
        ].notna().any()
    ):
        left = canonical[
            base_columns
            + [
                "lower_key",
                "upper_key",
            ]
        ]

        right = candidate[
            [
                "target_date",
                "decision_rule",
                "lower_bound_c",
                "upper_bound_c",
                "market_probability_raw",
            ]
        ].copy()

        right[
            "lower_key"
        ] = right[
            "lower_bound_c"
        ].round(8)

        right[
            "upper_key"
        ] = right[
            "upper_bound_c"
        ].round(8)

        right = right.dropna(
            subset=[
                "lower_key",
                "upper_key",
            ]
        )

        merged = left.merge(
            right[
                [
                    "target_date",
                    "decision_rule",
                    "lower_key",
                    "upper_key",
                    "market_probability_raw",
                ]
            ],
            on=[
                "target_date",
                "decision_rule",
                "lower_key",
                "upper_key",
            ],
            how="inner",
        )

        collapsed = collapse_matched_prices(
            merged[
                base_columns
                + [
                    "market_probability_raw",
                ]
            ]
        )

        if collapsed is not None:
            strategies.append(
                (
                    "canonical_event_bounds",
                    collapsed,
                )
            )

    return strategies


def discover_market_source(
    canonical: pd.DataFrame,
    expected_rules: list[str],
) -> tuple[
    dict[str, Any],
    pd.DataFrame,
    pd.DataFrame,
]:
    minimum_date = canonical[
        "target_date"
    ].min()

    maximum_date = canonical[
        "target_date"
    ].max()

    audit_rows: list[
        dict[str, Any]
    ] = []

    successful: list[
        tuple[
            tuple[int, int, int, int],
            dict[str, Any],
            pd.DataFrame,
        ]
    ] = []

    paths = candidate_paths()

    if not paths:
        raise RuntimeError(
            "No market-price CSV candidates were found."
        )

    for path in paths:
        candidate_frames = build_candidate_frames(
            path,
            expected_rules,
            minimum_date,
            maximum_date,
        )

        if not candidate_frames:
            continue

        for metadata, candidate in candidate_frames:
            strategies = matching_strategies(
                canonical,
                candidate,
                metadata,
            )

            if not strategies:
                audit_rows.append(
                    {
                        "path":
                            str(
                                path.relative_to(
                                    ROOT
                                )
                            ),
                        "price_column":
                            metadata[
                                "price_column"
                            ],
                        "format":
                            metadata[
                                "format"
                            ],
                        "matching_strategy":
                            "none",
                        "candidate_valid_rows":
                            len(candidate),
                        "matched_rows":
                            0,
                        "complete_books":
                            0,
                        "complete_dates":
                            0,
                        "path_bonus":
                            path_bonus(path),
                        "selected":
                            False,
                        "status":
                            "no_valid_match",
                    }
                )
                continue

            for strategy_name, matched in strategies:
                evaluation = evaluate_match(
                    canonical,
                    matched,
                )

                row = {
                    "path":
                        str(
                            path.relative_to(
                                ROOT
                            )
                        ),
                    "price_column":
                        metadata[
                            "price_column"
                        ],
                    "date_column":
                        metadata[
                            "date_column"
                        ],
                    "rule_column":
                        metadata[
                            "rule_column"
                        ],
                    "format":
                        metadata[
                            "format"
                        ],
                    "matching_strategy":
                        strategy_name,
                    "candidate_valid_rows":
                        len(candidate),
                    "matched_rows":
                        evaluation[
                            "matched_rows"
                        ],
                    "matched_date_rule_books":
                        evaluation[
                            "matched_date_rule_books"
                        ],
                    "complete_books":
                        evaluation[
                            "complete_books"
                        ],
                    "complete_dates":
                        evaluation[
                            "complete_dates"
                        ],
                    "path_bonus":
                        path_bonus(path),
                    "selected":
                        False,
                    "status":
                        "evaluated",
                }

                audit_rows.append(row)

                ranking = (
                    evaluation[
                        "complete_books"
                    ],
                    evaluation[
                        "matched_rows"
                    ],
                    evaluation[
                        "complete_dates"
                    ],
                    path_bonus(path),
                )

                successful.append(
                    (
                        ranking,
                        {
                            **metadata,
                            "matching_strategy":
                                strategy_name,
                            "evaluation":
                                evaluation,
                        },
                        matched,
                    )
                )

    if not successful:
        raise RuntimeError(
            "No market-price candidate could be matched "
            "to the Phase 9 contract events."
        )

    successful.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    _, selected_metadata, selected_matches = (
        successful[0]
    )

    if (
        selected_metadata[
            "evaluation"
        ][
            "complete_books"
        ]
        < 10
    ):
        raise RuntimeError(
            "The best market-price source produced fewer "
            "than 10 complete common-support books."
        )

    selected_path = str(
        selected_metadata[
            "path"
        ].relative_to(
            ROOT
        )
    )

    for row in audit_rows:
        if (
            row["path"] == selected_path
            and row[
                "price_column"
            ]
            == selected_metadata[
                "price_column"
            ]
            and row[
                "matching_strategy"
            ]
            == selected_metadata[
                "matching_strategy"
            ]
        ):
            row["selected"] = True
            row["status"] = "selected"

    audit = pd.DataFrame(
        audit_rows
    )

    if not audit.empty:
        audit = audit.sort_values(
            [
                "complete_books",
                "matched_rows",
                "path_bonus",
            ],
            ascending=[
                False,
                False,
                False,
            ],
            kind="stable",
        ).reset_index(
            drop=True
        )

    return (
        selected_metadata,
        selected_matches,
        audit,
    )


def build_complete_common_support(
    canonical: pd.DataFrame,
    matched_prices: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    book_columns = [
        "target_date",
        "decision_rule",
    ]

    event_key_columns = (
        book_columns
        + [
            "contract_key",
        ]
    )

    expected_counts = (
        canonical.groupby(
            book_columns
        )
        .size()
        .rename(
            "expected_event_count"
        )
        .reset_index()
    )

    matched_counts = (
        matched_prices.groupby(
            book_columns
        )
        .size()
        .rename(
            "matched_event_count"
        )
        .reset_index()
    )

    support = expected_counts.merge(
        matched_counts,
        on=book_columns,
        how="left",
    )

    support[
        "matched_event_count"
    ] = support[
        "matched_event_count"
    ].fillna(
        0
    ).astype(int)

    support[
        "complete_common_support"
    ] = (
        support[
            "matched_event_count"
        ].eq(
            support[
                "expected_event_count"
            ]
        )
        & support[
            "expected_event_count"
        ].gt(0)
    )

    complete_books = support.loc[
        support[
            "complete_common_support"
        ],
        book_columns,
    ]

    event_panel = canonical.merge(
        complete_books,
        on=book_columns,
        how="inner",
        validate="many_to_one",
    ).merge(
        matched_prices,
        on=event_key_columns,
        how="inner",
        validate="one_to_one",
    )

    event_panel = event_panel.sort_values(
        event_key_columns,
        kind="stable",
    ).reset_index(
        drop=True
    )

    return event_panel, support


def add_probabilities_and_scores(
    event_panel: pd.DataFrame,
    epsilon: float,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    book_columns = [
        "target_date",
        "decision_rule",
    ]

    raw_mass = (
        event_panel.groupby(
            book_columns
        )[
            "market_probability_raw"
        ]
        .transform(
            "sum"
        )
    )

    if (
        ~np.isfinite(raw_mass)
    ).any() or (
        raw_mass <= 0.0
    ).any():
        raise RuntimeError(
            "At least one complete market book has "
            "non-positive or non-finite price mass."
        )

    event_panel[
        "market_probability_mass_raw"
    ] = raw_mass

    event_panel[
        "market_probability_normalised"
    ] = (
        event_panel[
            "market_probability_raw"
        ]
        / raw_mass
    )

    gp_probability = event_panel[
        "gp_event_probability"
    ].to_numpy(
        dtype=float
    )

    market_raw = event_panel[
        "market_probability_raw"
    ].to_numpy(
        dtype=float
    )

    market_normalised = event_panel[
        "market_probability_normalised"
    ].to_numpy(
        dtype=float
    )

    realised = event_panel[
        "realised_yes"
    ].to_numpy(
        dtype=float
    )

    event_panel[
        "gp_binary_brier"
    ] = (
        gp_probability - realised
    ) ** 2

    event_panel[
        "market_binary_brier_raw"
    ] = (
        market_raw - realised
    ) ** 2

    event_panel[
        "market_binary_brier_normalised"
    ] = (
        market_normalised - realised
    ) ** 2

    def binary_log(
        probability: np.ndarray,
    ) -> np.ndarray:
        clipped = np.clip(
            probability,
            epsilon,
            1.0 - epsilon,
        )

        return -(
            realised
            * np.log(
                clipped
            )
            + (
                1.0 - realised
            )
            * np.log(
                1.0 - clipped
            )
        )

    event_panel[
        "gp_binary_log"
    ] = binary_log(
        gp_probability
    )

    event_panel[
        "market_binary_log_raw"
    ] = binary_log(
        market_raw
    )

    event_panel[
        "market_binary_log_normalised"
    ] = binary_log(
        market_normalised
    )

    date_rule_scores = (
        event_panel.groupby(
            book_columns,
            as_index=False,
        )
        .agg(
            sample_period=(
                "sample_period",
                "first",
            ),
            event_count=(
                "contract_key",
                "size",
            ),
            raw_market_probability_mass=(
                "market_probability_raw",
                "sum",
            ),
            gp_probability_mass=(
                "gp_event_probability",
                "sum",
            ),
            market_normalised_probability_mass=(
                "market_probability_normalised",
                "sum",
            ),
            realised_yes_count=(
                "realised_yes",
                "sum",
            ),
            gp_binary_brier_mean=(
                "gp_binary_brier",
                "mean",
            ),
            market_binary_brier_raw_mean=(
                "market_binary_brier_raw",
                "mean",
            ),
            market_binary_brier_normalised_mean=(
                "market_binary_brier_normalised",
                "mean",
            ),
            gp_binary_log_mean=(
                "gp_binary_log",
                "mean",
            ),
            market_binary_log_raw_mean=(
                "market_binary_log_raw",
                "mean",
            ),
            market_binary_log_normalised_mean=(
                "market_binary_log_normalised",
                "mean",
            ),
            gp_multiclass_brier=(
                "gp_binary_brier",
                "sum",
            ),
            market_multiclass_brier=(
                "market_binary_brier_normalised",
                "sum",
            ),
        )
    )

    realised_rows = event_panel.loc[
        event_panel[
            "realised_yes"
        ].eq(
            1.0
        ),
        book_columns
        + [
            "gp_event_probability",
            "market_probability_normalised",
        ],
    ].copy()

    realised_rows[
        "gp_categorical_log"
    ] = -np.log(
        np.clip(
            realised_rows[
                "gp_event_probability"
            ],
            epsilon,
            1.0,
        )
    )

    realised_rows[
        "market_categorical_log"
    ] = -np.log(
        np.clip(
            realised_rows[
                "market_probability_normalised"
            ],
            epsilon,
            1.0,
        )
    )

    date_rule_scores = (
        date_rule_scores.merge(
            realised_rows[
                book_columns
                + [
                    "gp_categorical_log",
                    "market_categorical_log",
                ]
            ],
            on=book_columns,
            how="left",
            validate="one_to_one",
        )
    )

    for metric_name, columns in METRICS.items():
        difference_column = (
            f"{metric_name}_difference_gp_minus_market"
        )

        date_rule_scores[
            difference_column
        ] = (
            date_rule_scores[
                columns["gp"]
            ]
            - date_rule_scores[
                columns["market"]
            ]
        )

    return event_panel, date_rule_scores


def bootstrap_mean_interval(
    values: np.ndarray,
    repetitions: int,
    confidence_level: float,
    seed: int,
) -> tuple[float, float]:
    values = np.asarray(
        values,
        dtype=float,
    )

    values = values[
        np.isfinite(values)
    ]

    if len(values) == 0:
        return np.nan, np.nan

    if len(values) == 1:
        return float(values[0]), float(values[0])

    rng = np.random.default_rng(
        seed
    )

    indices = rng.integers(
        0,
        len(values),
        size=(
            repetitions,
            len(values),
        ),
    )

    means = values[
        indices
    ].mean(
        axis=1
    )

    alpha = (
        1.0 - confidence_level
    ) / 2.0

    lower, upper = np.quantile(
        means,
        [
            alpha,
            1.0 - alpha,
        ],
    )

    return float(lower), float(upper)


def paired_difference_summary(
    date_rule_scores: pd.DataFrame,
    specification: dict[str, Any],
) -> pd.DataFrame:
    design = specification[
        "comparison_design"
    ]

    repetitions = int(
        design[
            "bootstrap_repetitions"
        ]
    )

    confidence_level = float(
        design[
            "confidence_level"
        ]
    )

    base_seed = int(
        design[
            "bootstrap_seed"
        ]
    )

    splits = [
        "weather_plus_market_training",
        "out_of_sample_validation",
        "all_period",
    ]

    rules = (
        specification[
            "decision_rules"
        ]
        + [
            "all_rules",
        ]
    )

    rows: list[
        dict[str, Any]
    ] = []

    for split_name in splits:
        if split_name == "all_period":
            split_panel = date_rule_scores.copy()
        else:
            split_panel = date_rule_scores.loc[
                date_rule_scores[
                    "sample_period"
                ].eq(
                    split_name
                )
            ].copy()

        for rule_name in rules:
            if rule_name == "all_rules":
                selected = split_panel.copy()
            else:
                selected = split_panel.loc[
                    split_panel[
                        "decision_rule"
                    ].eq(
                        rule_name
                    )
                ].copy()

            if selected.empty:
                continue

            for metric_index, (
                metric_name,
                metric_specification,
            ) in enumerate(
                METRICS.items()
            ):
                gp_column = metric_specification[
                    "gp"
                ]

                market_column = (
                    metric_specification[
                        "market"
                    ]
                )

                if rule_name == "all_rules":
                    paired = (
                        selected.groupby(
                            "target_date",
                            as_index=False,
                        )
                        .agg(
                            gp_score=(
                                gp_column,
                                "mean",
                            ),
                            market_score=(
                                market_column,
                                "mean",
                            ),
                            rules_present=(
                                "decision_rule",
                                "nunique",
                            ),
                        )
                    )
                else:
                    paired = selected[
                        [
                            "target_date",
                            gp_column,
                            market_column,
                        ]
                    ].rename(
                        columns={
                            gp_column:
                                "gp_score",
                            market_column:
                                "market_score",
                        }
                    )

                    paired[
                        "rules_present"
                    ] = 1

                paired[
                    "difference"
                ] = (
                    paired[
                        "gp_score"
                    ]
                    - paired[
                        "market_score"
                    ]
                )

                differences = paired[
                    "difference"
                ].to_numpy(
                    dtype=float
                )

                differences = differences[
                    np.isfinite(
                        differences
                    )
                ]

                if len(differences) == 0:
                    continue

                seed_text = (
                    f"{split_name}|"
                    f"{rule_name}|"
                    f"{metric_name}"
                )

                seed_offset = sum(
                    (
                        index + 1
                    )
                    * ord(character)
                    for index, character
                    in enumerate(seed_text)
                )

                bootstrap_lower, bootstrap_upper = (
                    bootstrap_mean_interval(
                        differences,
                        repetitions,
                        confidence_level,
                        base_seed
                        + seed_offset
                        + metric_index,
                    )
                )

                sample_standard_deviation = (
                    float(
                        np.std(
                            differences,
                            ddof=1,
                        )
                    )
                    if len(differences) > 1
                    else 0.0
                )

                standard_error = (
                    sample_standard_deviation
                    / math.sqrt(
                        len(differences)
                    )
                    if len(differences) > 0
                    else np.nan
                )

                if len(differences) > 1:
                    critical = student_t.ppf(
                        (
                            1.0
                            + confidence_level
                        )
                        / 2.0,
                        df=(
                            len(differences)
                            - 1
                        ),
                    )

                    t_lower = (
                        float(
                            np.mean(
                                differences
                            )
                        )
                        - critical
                        * standard_error
                    )

                    t_upper = (
                        float(
                            np.mean(
                                differences
                            )
                        )
                        + critical
                        * standard_error
                    )

                    t_test = ttest_1samp(
                        differences,
                        popmean=0.0,
                        nan_policy="omit",
                    )

                    t_pvalue = float(
                        t_test.pvalue
                    )
                else:
                    t_lower = float(
                        differences[0]
                    )

                    t_upper = float(
                        differences[0]
                    )

                    t_pvalue = np.nan

                mean_difference = float(
                    np.mean(
                        differences
                    )
                )

                if bootstrap_upper < 0.0:
                    interpretation = (
                        "GP_lower_score"
                    )
                elif bootstrap_lower > 0.0:
                    interpretation = (
                        "Market_lower_score"
                    )
                else:
                    interpretation = (
                        "interval_includes_zero"
                    )

                rows.append(
                    {
                        "sample_period":
                            split_name,
                        "decision_rule":
                            rule_name,
                        "metric":
                            metric_name,
                        "metric_label":
                            metric_specification[
                                "label"
                            ],
                        "primary_metric":
                            metric_specification[
                                "primary"
                            ],
                        "dates":
                            int(
                                paired[
                                    "target_date"
                                ].nunique()
                            ),
                        "mean_rules_per_date":
                            float(
                                paired[
                                    "rules_present"
                                ].mean()
                            ),
                        "mean_gp_score":
                            float(
                                paired[
                                    "gp_score"
                                ].mean()
                            ),
                        "mean_market_score":
                            float(
                                paired[
                                    "market_score"
                                ].mean()
                            ),
                        "mean_difference_gp_minus_market":
                            mean_difference,
                        "median_difference_gp_minus_market":
                            float(
                                np.median(
                                    differences
                                )
                            ),
                        "standard_deviation_difference":
                            sample_standard_deviation,
                        "standard_error_difference":
                            standard_error,
                        "bootstrap_ci_lower":
                            bootstrap_lower,
                        "bootstrap_ci_upper":
                            bootstrap_upper,
                        "t_ci_lower":
                            t_lower,
                        "t_ci_upper":
                            t_upper,
                        "paired_t_pvalue":
                            t_pvalue,
                        "gp_lower_score_fraction":
                            float(
                                np.mean(
                                    differences
                                    < 0.0
                                )
                            ),
                        "market_lower_score_fraction":
                            float(
                                np.mean(
                                    differences
                                    > 0.0
                                )
                            ),
                        "tie_fraction":
                            float(
                                np.mean(
                                    np.isclose(
                                        differences,
                                        0.0,
                                        atol=1e-12,
                                    )
                                )
                            ),
                        "bootstrap_interpretation":
                            interpretation,
                    }
                )

    return pd.DataFrame(
        rows
    )


def logistic_calibration(
    probabilities: np.ndarray,
    outcomes: np.ndarray,
    epsilon: float,
) -> tuple[float, float, bool]:
    probability = np.clip(
        np.asarray(
            probabilities,
            dtype=float,
        ),
        epsilon,
        1.0 - epsilon,
    )

    outcome = np.asarray(
        outcomes,
        dtype=float,
    )

    if (
        len(probability) < 10
        or np.unique(
            outcome
        ).size < 2
    ):
        return np.nan, np.nan, False

    logit_probability = np.log(
        probability
        / (
            1.0 - probability
        )
    )

    def objective(
        parameters: np.ndarray,
    ) -> float:
        linear_predictor = (
            parameters[0]
            + parameters[1]
            * logit_probability
        )

        fitted = 1.0 / (
            1.0
            + np.exp(
                -np.clip(
                    linear_predictor,
                    -40.0,
                    40.0,
                )
            )
        )

        return float(
            -np.sum(
                outcome
                * np.log(
                    np.clip(
                        fitted,
                        epsilon,
                        1.0,
                    )
                )
                + (
                    1.0 - outcome
                )
                * np.log(
                    np.clip(
                        1.0 - fitted,
                        epsilon,
                        1.0,
                    )
                )
            )
        )

    result = minimize(
        objective,
        x0=np.array(
            [
                0.0,
                1.0,
            ]
        ),
        method="BFGS",
    )

    if not result.success:
        return np.nan, np.nan, False

    return (
        float(
            result.x[0]
        ),
        float(
            result.x[1]
        ),
        True,
    )


def calibration_diagnostics(
    event_panel: pd.DataFrame,
    specification: dict[str, Any],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    design = specification[
        "comparison_design"
    ]

    number_of_bins = int(
        design[
            "calibration_bins"
        ]
    )

    epsilon = float(
        design[
            "probability_clip"
        ]
    )

    models = {
        "gp":
            "gp_event_probability",
        "market_raw":
            "market_probability_raw",
        "market_normalised":
            "market_probability_normalised",
    }

    splits = [
        "weather_plus_market_training",
        "out_of_sample_validation",
        "all_period",
    ]

    rules = (
        specification[
            "decision_rules"
        ]
        + [
            "all_rules",
        ]
    )

    bin_rows: list[
        dict[str, Any]
    ] = []

    summary_rows: list[
        dict[str, Any]
    ] = []

    for split_name in splits:
        if split_name == "all_period":
            split_panel = event_panel.copy()
        else:
            split_panel = event_panel.loc[
                event_panel[
                    "sample_period"
                ].eq(
                    split_name
                )
            ].copy()

        for rule_name in rules:
            if rule_name == "all_rules":
                selected = split_panel.copy()
            else:
                selected = split_panel.loc[
                    split_panel[
                        "decision_rule"
                    ].eq(
                        rule_name
                    )
                ].copy()

            if selected.empty:
                continue

            outcomes = selected[
                "realised_yes"
            ].to_numpy(
                dtype=float
            )

            outcome_rate = float(
                np.mean(
                    outcomes
                )
            )

            for model_name, probability_column in (
                models.items()
            ):
                probabilities = selected[
                    probability_column
                ].to_numpy(
                    dtype=float
                )

                bin_index = np.minimum(
                    (
                        np.clip(
                            probabilities,
                            0.0,
                            1.0,
                        )
                        * number_of_bins
                    ).astype(int),
                    number_of_bins - 1,
                )

                calibration_table_rows: list[
                    dict[str, Any]
                ] = []

                for current_bin in range(
                    number_of_bins
                ):
                    mask = (
                        bin_index
                        == current_bin
                    )

                    count = int(
                        mask.sum()
                    )

                    bin_lower = (
                        current_bin
                        / number_of_bins
                    )

                    bin_upper = (
                        (
                            current_bin + 1
                        )
                        / number_of_bins
                    )

                    if count > 0:
                        mean_probability = float(
                            probabilities[
                                mask
                            ].mean()
                        )

                        empirical_frequency = float(
                            outcomes[
                                mask
                            ].mean()
                        )

                        absolute_gap = abs(
                            mean_probability
                            - empirical_frequency
                        )
                    else:
                        mean_probability = np.nan
                        empirical_frequency = np.nan
                        absolute_gap = np.nan

                    row = {
                        "sample_period":
                            split_name,
                        "decision_rule":
                            rule_name,
                        "model":
                            model_name,
                        "probability_column":
                            probability_column,
                        "bin_index":
                            current_bin,
                        "bin_lower":
                            bin_lower,
                        "bin_upper":
                            bin_upper,
                        "observations":
                            count,
                        "mean_probability":
                            mean_probability,
                        "empirical_frequency":
                            empirical_frequency,
                        "absolute_calibration_gap":
                            absolute_gap,
                    }

                    bin_rows.append(row)
                    calibration_table_rows.append(row)

                non_empty = [
                    row
                    for row in calibration_table_rows
                    if row[
                        "observations"
                    ] > 0
                ]

                total = len(
                    selected
                )

                ece = float(
                    sum(
                        row[
                            "observations"
                        ]
                        / total
                        * row[
                            "absolute_calibration_gap"
                        ]
                        for row in non_empty
                    )
                )

                mce = float(
                    max(
                        row[
                            "absolute_calibration_gap"
                        ]
                        for row in non_empty
                    )
                )

                reliability = float(
                    sum(
                        row[
                            "observations"
                        ]
                        / total
                        * (
                            row[
                                "mean_probability"
                            ]
                            - row[
                                "empirical_frequency"
                            ]
                        )
                        ** 2
                        for row in non_empty
                    )
                )

                resolution = float(
                    sum(
                        row[
                            "observations"
                        ]
                        / total
                        * (
                            row[
                                "empirical_frequency"
                            ]
                            - outcome_rate
                        )
                        ** 2
                        for row in non_empty
                    )
                )

                uncertainty = float(
                    outcome_rate
                    * (
                        1.0 - outcome_rate
                    )
                )

                direct_brier = float(
                    np.mean(
                        (
                            probabilities
                            - outcomes
                        )
                        ** 2
                    )
                )

                intercept, slope, calibration_fit = (
                    logistic_calibration(
                        probabilities,
                        outcomes,
                        epsilon,
                    )
                )

                summary_rows.append(
                    {
                        "sample_period":
                            split_name,
                        "decision_rule":
                            rule_name,
                        "model":
                            model_name,
                        "event_rows":
                            total,
                        "dates":
                            int(
                                selected[
                                    "target_date"
                                ].nunique()
                            ),
                        "mean_probability":
                            float(
                                probabilities.mean()
                            ),
                        "outcome_rate":
                            outcome_rate,
                        "calibration_bias":
                            float(
                                probabilities.mean()
                                - outcome_rate
                            ),
                        "expected_calibration_error":
                            ece,
                        "maximum_calibration_error":
                            mce,
                        "brier_score":
                            direct_brier,
                        "brier_reliability":
                            reliability,
                        "brier_resolution":
                            resolution,
                        "brier_uncertainty":
                            uncertainty,
                        "brier_decomposition":
                            reliability
                            - resolution
                            + uncertainty,
                        "logistic_calibration_intercept":
                            intercept,
                        "logistic_calibration_slope":
                            slope,
                        "logistic_calibration_fit_passed":
                            calibration_fit,
                    }
                )

    return (
        pd.DataFrame(
            bin_rows
        ),
        pd.DataFrame(
            summary_rows
        ),
    )


def support_audit(
    canonical: pd.DataFrame,
    matched_prices: pd.DataFrame,
    support: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[
        dict[str, Any]
    ] = []

    splits = [
        "weather_plus_market_training",
        "out_of_sample_validation",
        "all_period",
    ]

    rules = sorted(
        canonical[
            "decision_rule"
        ].unique()
    ) + [
        "all_rules",
    ]

    matched_books = (
        matched_prices[
            [
                "target_date",
                "decision_rule",
            ]
        ]
        .drop_duplicates()
    )

    for split_name in splits:
        if split_name == "all_period":
            canonical_split = canonical
            support_split = support
            matched_split = matched_books
        else:
            dates = canonical.loc[
                canonical[
                    "sample_period"
                ].eq(
                    split_name
                ),
                "target_date",
            ].drop_duplicates()

            canonical_split = canonical.loc[
                canonical[
                    "target_date"
                ].isin(
                    dates
                )
            ]

            support_split = support.loc[
                support[
                    "target_date"
                ].isin(
                    dates
                )
            ]

            matched_split = matched_books.loc[
                matched_books[
                    "target_date"
                ].isin(
                    dates
                )
            ]

        for rule_name in rules:
            if rule_name == "all_rules":
                current_canonical = canonical_split
                current_support = support_split
                current_matched = matched_split
            else:
                current_canonical = canonical_split.loc[
                    canonical_split[
                        "decision_rule"
                    ].eq(
                        rule_name
                    )
                ]

                current_support = support_split.loc[
                    support_split[
                        "decision_rule"
                    ].eq(
                        rule_name
                    )
                ]

                current_matched = matched_split.loc[
                    matched_split[
                        "decision_rule"
                    ].eq(
                        rule_name
                    )
                ]

            if current_canonical.empty:
                continue

            complete = current_support.loc[
                current_support[
                    "complete_common_support"
                ]
            ]

            incomplete = current_support.loc[
                ~current_support[
                    "complete_common_support"
                ]
            ]

            rows.append(
                {
                    "sample_period":
                        split_name,
                    "decision_rule":
                        rule_name,
                    "gp_supported_dates":
                        int(
                            current_canonical[
                                "target_date"
                            ].nunique()
                        ),
                    "gp_supported_date_rule_books":
                        int(
                            current_canonical[
                                [
                                    "target_date",
                                    "decision_rule",
                                ]
                            ]
                            .drop_duplicates()
                            .shape[0]
                        ),
                    "gp_supported_event_rows":
                        int(
                            len(
                                current_canonical
                            )
                        ),
                    "market_any_price_date_rule_books":
                        int(
                            len(
                                current_matched
                            )
                        ),
                    "complete_common_support_books":
                        int(
                            len(
                                complete
                            )
                        ),
                    "complete_common_support_dates":
                        int(
                            complete[
                                "target_date"
                            ].nunique()
                        ),
                    "incomplete_or_missing_books":
                        int(
                            len(
                                incomplete
                            )
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


def create_figures(
    output_directory: Path,
    calibration_bins: pd.DataFrame,
    paired_summary: pd.DataFrame,
) -> list[str]:
    figure_files: list[str] = []

    reliability = calibration_bins.loc[
        calibration_bins[
            "sample_period"
        ].eq(
            "out_of_sample_validation"
        )
        & calibration_bins[
            "decision_rule"
        ].eq(
            "all_rules"
        )
        & calibration_bins[
            "model"
        ].isin(
            [
                "gp",
                "market_raw",
            ]
        )
        & calibration_bins[
            "observations"
        ].gt(0)
    ]

    if not reliability.empty:
        figure_name = (
            "phase10_june_reliability_diagram.png"
        )

        figure_path = (
            output_directory
            / figure_name
        )

        figure, axis = plt.subplots(
            figsize=(
                7.0,
                6.0,
            )
        )

        axis.plot(
            [
                0.0,
                1.0,
            ],
            [
                0.0,
                1.0,
            ],
            linestyle="--",
            label="Perfect calibration",
        )

        for model_name, group in reliability.groupby(
            "model",
            sort=False,
        ):
            axis.plot(
                group[
                    "mean_probability"
                ],
                group[
                    "empirical_frequency"
                ],
                marker="o",
                label=(
                    "GP"
                    if model_name == "gp"
                    else "Polymarket"
                ),
            )

        axis.set_xlim(
            0.0,
            1.0,
        )

        axis.set_ylim(
            0.0,
            1.0,
        )

        axis.set_xlabel(
            "Mean predicted probability"
        )

        axis.set_ylabel(
            "Observed event frequency"
        )

        axis.set_title(
            "June out-of-sample reliability"
        )

        axis.legend()

        figure.tight_layout()

        figure.savefig(
            figure_path,
            dpi=180,
        )

        plt.close(
            figure
        )

        figure_files.append(
            figure_name
        )

    for metric_name, metric_specification in (
        METRICS.items()
    ):
        if not metric_specification[
            "primary"
        ]:
            continue

        plot_data = paired_summary.loc[
            paired_summary[
                "sample_period"
            ].eq(
                "out_of_sample_validation"
            )
            & paired_summary[
                "metric"
            ].eq(
                metric_name
            )
        ].copy()

        if plot_data.empty:
            continue

        rule_order = [
            "24h_prior",
            "12h_prior",
            "6h_prior",
            "event_day_open",
            "all_rules",
        ]

        plot_data[
            "order"
        ] = plot_data[
            "decision_rule"
        ].map(
            {
                rule: index
                for index, rule
                in enumerate(
                    rule_order
                )
            }
        )

        plot_data = plot_data.sort_values(
            "order"
        )

        y_positions = np.arange(
            len(
                plot_data
            )
        )

        mean_difference = plot_data[
            "mean_difference_gp_minus_market"
        ].to_numpy(
            dtype=float
        )

        lower_error = (
            mean_difference
            - plot_data[
                "bootstrap_ci_lower"
            ].to_numpy(
                dtype=float
            )
        )

        upper_error = (
            plot_data[
                "bootstrap_ci_upper"
            ].to_numpy(
                dtype=float
            )
            - mean_difference
        )

        figure_name = (
            "phase10_june_"
            + metric_name
            + "_paired_difference.png"
        )

        figure_path = (
            output_directory
            / figure_name
        )

        figure, axis = plt.subplots(
            figsize=(
                8.0,
                5.5,
            )
        )

        axis.errorbar(
            mean_difference,
            y_positions,
            xerr=np.vstack(
                [
                    lower_error,
                    upper_error,
                ]
            ),
            fmt="o",
            capsize=4,
        )

        axis.axvline(
            0.0,
            linestyle="--",
        )

        axis.set_yticks(
            y_positions,
            labels=plot_data[
                "decision_rule"
            ].tolist(),
        )

        axis.set_xlabel(
            "Paired score difference: GP minus Polymarket"
        )

        axis.set_title(
            "June out-of-sample: "
            + metric_specification[
                "label"
            ]
        )

        figure.tight_layout()

        figure.savefig(
            figure_path,
            dpi=180,
        )

        plt.close(
            figure
        )

        figure_files.append(
            figure_name
        )

    return figure_files


def atomic_replace_directory(
    staged: Path,
    target: Path,
) -> None:
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if target.exists():
        shutil.rmtree(
            target
        )

    shutil.move(
        str(staged),
        str(target),
    )


def report_table(
    frame: pd.DataFrame,
) -> str:
    if frame.empty:
        return "No observations."

    lines = [
        "| Metric | GP | Polymarket | Difference | 95% bootstrap interval | Dates |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for _, row in frame.iterrows():
        lines.append(
            "| "
            + str(
                row[
                    "metric_label"
                ]
            )
            + " | "
            + f"{row['mean_gp_score']:.6f}"
            + " | "
            + f"{row['mean_market_score']:.6f}"
            + " | "
            + f"{row['mean_difference_gp_minus_market']:.6f}"
            + " | ["
            + f"{row['bootstrap_ci_lower']:.6f}"
            + ", "
            + f"{row['bootstrap_ci_upper']:.6f}"
            + "] | "
            + str(
                int(
                    row[
                        "dates"
                    ]
                )
            )
            + " |"
        )

    return "\n".join(
        lines
    )


def main() -> None:
    warnings.filterwarnings(
        "ignore",
        category=pd.errors.PerformanceWarning,
    )

    specification = load_json(
        SPEC_PATH
    )

    phase9_manifest_path = (
        ROOT
        / specification[
            "inputs"
        ][
            "phase9_manifest"
        ]
    )

    phase9_event_path = (
        ROOT
        / specification[
            "inputs"
        ][
            "phase9_event_panel"
        ]
    )

    phase9_manifest = load_json(
        phase9_manifest_path
    )

    if phase9_manifest.get(
        "status"
    ) != "passed":
        raise RuntimeError(
            "Phase 9 manifest does not report passed."
        )

    canonical = pd.read_csv(
        phase9_event_path,
        low_memory=False,
    )

    required_columns = {
        "target_date",
        "decision_rule",
        "contract_key",
        "lower_bound_c",
        "upper_bound_c",
        "realised_yes",
        "gp_event_probability",
        "sample_period",
    }

    missing_columns = (
        required_columns
        - set(
            canonical.columns
        )
    )

    if missing_columns:
        raise RuntimeError(
            "Phase 9 event panel is missing: "
            + ", ".join(
                sorted(
                    missing_columns
                )
            )
        )

    canonical[
        "target_date"
    ] = parse_dates(
        canonical[
            "target_date"
        ]
    )

    canonical[
        "decision_rule"
    ] = normalise_rules(
        canonical[
            "decision_rule"
        ]
    )

    canonical[
        "contract_key"
    ] = canonical[
        "contract_key"
    ].astype(str)

    if (
        "source_contract_id"
        in canonical.columns
    ):
        canonical[
            "source_contract_id_normalised"
        ] = normalise_identifier(
            canonical[
                "source_contract_id"
            ]
        )
    else:
        canonical[
            "source_contract_id_normalised"
        ] = pd.NA

    canonical[
        "contract_key_normalised"
    ] = normalise_identifier(
        canonical[
            "contract_key"
        ]
    )

    if (
        "event_label"
        in canonical.columns
    ):
        canonical[
            "event_label_normalised"
        ] = normalise_label(
            canonical[
                "event_label"
            ]
        )
    else:
        canonical[
            "event_label_normalised"
        ] = pd.NA

    canonical[
        "lower_key"
    ] = pd.to_numeric(
        canonical[
            "lower_bound_c"
        ],
        errors="coerce",
    ).round(8)

    canonical[
        "upper_key"
    ] = pd.to_numeric(
        canonical[
            "upper_bound_c"
        ],
        errors="coerce",
    ).round(8)

    canonical[
        "realised_yes"
    ] = pd.to_numeric(
        canonical[
            "realised_yes"
        ],
        errors="raise",
    )

    canonical[
        "gp_event_probability"
    ] = pd.to_numeric(
        canonical[
            "gp_event_probability"
        ],
        errors="raise",
    )

    event_key_columns = [
        "target_date",
        "decision_rule",
        "contract_key",
    ]

    if canonical[
        event_key_columns
    ].duplicated().any():
        raise RuntimeError(
            "Duplicate Phase 9 contract-event keys found."
        )

    gp_mass = (
        canonical.groupby(
            [
                "target_date",
                "decision_rule",
            ]
        )[
            "gp_event_probability"
        ].sum()
    )

    if not np.allclose(
        gp_mass.to_numpy(
            dtype=float
        ),
        1.0,
        atol=1e-10,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Phase 9 GP probability masses do not sum "
            "to one."
        )

    selected_metadata, matched_prices, (
        candidate_audit
    ) = discover_market_source(
        canonical,
        specification[
            "decision_rules"
        ],
    )

    event_panel, support = (
        build_complete_common_support(
            canonical,
            matched_prices,
        )
    )

    if event_panel.empty:
        raise RuntimeError(
            "No complete common-support books were found."
        )

    event_panel, date_rule_scores = (
        add_probabilities_and_scores(
            event_panel,
            float(
                specification[
                    "comparison_design"
                ][
                    "probability_clip"
                ]
            ),
        )
    )

    mass_integrity = (
        date_rule_scores[
            "gp_probability_mass"
        ].sub(
            1.0
        ).abs().le(
            1e-10
        )
        & date_rule_scores[
            "market_normalised_probability_mass"
        ].sub(
            1.0
        ).abs().le(
            1e-10
        )
        & date_rule_scores[
            "realised_yes_count"
        ].eq(
            1.0
        )
    )

    if not mass_integrity.all():
        raise RuntimeError(
            "Common-support probability-mass or "
            "outcome integrity checks failed."
        )

    June_mask = date_rule_scores[
        "sample_period"
    ].eq(
        "out_of_sample_validation"
    )

    if not June_mask.any():
        raise RuntimeError(
            "No June complete common-support books exist."
        )

    for decision_rule in specification[
        "decision_rules"
    ]:
        rule_june_dates = date_rule_scores.loc[
            June_mask
            & date_rule_scores[
                "decision_rule"
            ].eq(
                decision_rule
            ),
            "target_date",
        ].nunique()

        if rule_june_dates == 0:
            raise RuntimeError(
                "No June complete common-support books "
                f"exist for {decision_rule}."
            )

    paired_summary = (
        paired_difference_summary(
            date_rule_scores,
            specification,
        )
    )

    calibration_bins, calibration_summary = (
        calibration_diagnostics(
            event_panel,
            specification,
        )
    )

    support_summary = support_audit(
        canonical,
        matched_prices,
        support,
    )

    selected_source_path = (
        selected_metadata[
            "path"
        ]
    )

    output_target = (
        ROOT
        / specification[
            "output_directory"
        ]
    )

    stage_root = Path(
        tempfile.mkdtemp(
            prefix="phase10_gp_market_"
        )
    )

    stage_output = (
        stage_root
        / "phase10_gp_market_comparison"
    )

    stage_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        event_panel.to_csv(
            stage_output
            / "phase10_exact_common_support_event_panel.csv",
            index=False,
        )

        date_rule_scores.to_csv(
            stage_output
            / "phase10_date_rule_paired_scores.csv",
            index=False,
        )

        paired_summary.to_csv(
            stage_output
            / "phase10_paired_difference_summary.csv",
            index=False,
        )

        calibration_bins.to_csv(
            stage_output
            / "phase10_calibration_bins.csv",
            index=False,
        )

        calibration_summary.to_csv(
            stage_output
            / "phase10_calibration_summary.csv",
            index=False,
        )

        support_summary.to_csv(
            stage_output
            / "phase10_support_audit.csv",
            index=False,
        )

        candidate_audit.to_csv(
            stage_output
            / "phase10_market_source_candidate_audit.csv",
            index=False,
        )

        incomplete_support = support.loc[
            ~support[
                "complete_common_support"
            ]
        ].copy()

        incomplete_support.to_csv(
            stage_output
            / "phase10_incomplete_or_missing_books.csv",
            index=False,
        )

        figure_files = create_figures(
            stage_output,
            calibration_bins,
            paired_summary,
        )

        split_counts = (
            date_rule_scores.groupby(
                "sample_period"
            )
            .agg(
                dates=(
                    "target_date",
                    "nunique",
                ),
                date_rule_books=(
                    "target_date",
                    "size",
                ),
            )
            .reset_index()
        )

        rule_counts = (
            date_rule_scores.groupby(
                [
                    "sample_period",
                    "decision_rule",
                ]
            )
            .agg(
                dates=(
                    "target_date",
                    "nunique",
                ),
                date_rule_books=(
                    "target_date",
                    "size",
                ),
                event_rows=(
                    "event_count",
                    "sum",
                ),
            )
            .reset_index()
        )

        split_counts.to_csv(
            stage_output
            / "phase10_split_counts.csv",
            index=False,
        )

        rule_counts.to_csv(
            stage_output
            / "phase10_rule_counts.csv",
            index=False,
        )

        manifest = {
            "phase": 10,
            "status": "passed",
            "comparison": {
                "common_support":
                    "complete contract books only",
                "paired_difference":
                    "GP score minus market score",
                "binary_market_probability":
                    "raw Yes price",
                "categorical_market_probability":
                    "within-book normalised Yes price",
                "uncertainty_unit":
                    "target_date",
                "bootstrap_repetitions":
                    specification[
                        "comparison_design"
                    ][
                        "bootstrap_repetitions"
                    ],
            },
            "inputs": {
                "phase9_manifest": {
                    "path":
                        str(
                            phase9_manifest_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            phase9_manifest_path
                        ),
                },
                "phase9_event_panel": {
                    "path":
                        str(
                            phase9_event_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            phase9_event_path
                        ),
                },
                "market_price_source": {
                    "path":
                        str(
                            selected_source_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            selected_source_path
                        ),
                    "date_column":
                        selected_metadata[
                            "date_column"
                        ],
                    "rule_column":
                        selected_metadata[
                            "rule_column"
                        ],
                    "price_column":
                        selected_metadata[
                            "price_column"
                        ],
                    "format":
                        selected_metadata[
                            "format"
                        ],
                    "matching_strategy":
                        selected_metadata[
                            "matching_strategy"
                        ],
                },
            },
            "counts": {
                "phase9_gp_supported_dates":
                    int(
                        canonical[
                            "target_date"
                        ].nunique()
                    ),
                "phase9_gp_supported_date_rule_books":
                    int(
                        canonical[
                            [
                                "target_date",
                                "decision_rule",
                            ]
                        ]
                        .drop_duplicates()
                        .shape[0]
                    ),
                "phase9_gp_supported_event_rows":
                    int(
                        len(
                            canonical
                        )
                    ),
                "matched_market_price_event_rows":
                    int(
                        len(
                            matched_prices
                        )
                    ),
                "complete_common_support_dates":
                    int(
                        event_panel[
                            "target_date"
                        ].nunique()
                    ),
                "complete_common_support_date_rule_books":
                    int(
                        len(
                            date_rule_scores
                        )
                    ),
                "complete_common_support_event_rows":
                    int(
                        len(
                            event_panel
                        )
                    ),
                "weather_plus_market_training_dates":
                    int(
                        date_rule_scores.loc[
                            date_rule_scores[
                                "sample_period"
                            ].eq(
                                "weather_plus_market_training"
                            ),
                            "target_date",
                        ].nunique()
                    ),
                "out_of_sample_validation_dates":
                    int(
                        date_rule_scores.loc[
                            date_rule_scores[
                                "sample_period"
                            ].eq(
                                "out_of_sample_validation"
                            ),
                            "target_date",
                        ].nunique()
                    ),
                "incomplete_or_missing_date_rule_books":
                    int(
                        len(
                            incomplete_support
                        )
                    ),
            },
            "integrity": {
                "duplicate_common_support_event_keys":
                    int(
                        event_panel.duplicated(
                            event_key_columns
                        ).sum()
                    ),
                "maximum_gp_probability_mass_error":
                    float(
                        date_rule_scores[
                            "gp_probability_mass"
                        ].sub(
                            1.0
                        ).abs().max()
                    ),
                "maximum_normalised_market_mass_error":
                    float(
                        date_rule_scores[
                            "market_normalised_probability_mass"
                        ].sub(
                            1.0
                        ).abs().max()
                    ),
                "exactly_one_realised_yes_in_every_book":
                    bool(
                        date_rule_scores[
                            "realised_yes_count"
                        ].eq(
                            1.0
                        ).all()
                    ),
                "all_four_rules_present_in_june":
                    True,
            },
            "figures":
                figure_files,
            "restrictions":
                specification[
                    "restrictions"
                ],
        }

        (
            stage_output
            / "phase10_manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        june_primary = paired_summary.loc[
            paired_summary[
                "sample_period"
            ].eq(
                "out_of_sample_validation"
            )
            & paired_summary[
                "decision_rule"
            ].eq(
                "all_rules"
            )
            & paired_summary[
                "primary_metric"
            ].eq(
                True
            )
        ].copy()

        training_primary = paired_summary.loc[
            paired_summary[
                "sample_period"
            ].eq(
                "weather_plus_market_training"
            )
            & paired_summary[
                "decision_rule"
            ].eq(
                "all_rules"
            )
            & paired_summary[
                "primary_metric"
            ].eq(
                True
            )
        ].copy()

        june_calibration = (
            calibration_summary.loc[
                calibration_summary[
                    "sample_period"
                ].eq(
                    "out_of_sample_validation"
                )
                & calibration_summary[
                    "decision_rule"
                ].eq(
                    "all_rules"
                )
                & calibration_summary[
                    "model"
                ].isin(
                    [
                        "gp",
                        "market_raw",
                    ]
                )
            ]
        )

        calibration_lines = [
            "| Model | Event rows | ECE | MCE | Brier | Calibration bias |",
            "|---|---:|---:|---:|---:|---:|",
        ]

        for _, row in june_calibration.iterrows():
            calibration_lines.append(
                "| "
                + (
                    "GP"
                    if row[
                        "model"
                    ] == "gp"
                    else "Polymarket"
                )
                + " | "
                + str(
                    int(
                        row[
                            "event_rows"
                        ]
                    )
                )
                + " | "
                + f"{row['expected_calibration_error']:.6f}"
                + " | "
                + f"{row['maximum_calibration_error']:.6f}"
                + " | "
                + f"{row['brier_score']:.6f}"
                + " | "
                + f"{row['calibration_bias']:.6f}"
                + " |"
            )

        report = f"""# Phase 10 Exact-Common-Support GP versus Polymarket Comparison

## Status

PASSED

## Comparison design

The comparison uses only complete contract books for which every
canonical contract has both a Phase 9 GP probability and a valid
Polymarket decision price. No missing forecast or market price is
imputed.

Binary Brier and binary log scores use the raw Polymarket Yes price.
Categorical log and multiclass Brier scores use Polymarket prices
normalised within each complete contract book. GP probabilities already
sum to one.

Every paired difference is defined as:

`GP score minus Polymarket score`.

A negative value therefore means that the GP has the lower proper score.

## Selected market-price source

- Path: `{selected_source_path.relative_to(ROOT)}`.
- Price column: `{selected_metadata['price_column']}`.
- Decision-rule column: `{selected_metadata['rule_column']}`.
- Matching strategy: `{selected_metadata['matching_strategy']}`.

## Exact common support

- Phase 9 GP-supported dates:
  {canonical['target_date'].nunique()}.
- Phase 9 GP-supported date-rule books:
  {canonical[['target_date', 'decision_rule']].drop_duplicates().shape[0]}.
- Complete common-support dates:
  {event_panel['target_date'].nunique()}.
- Complete common-support date-rule books:
  {len(date_rule_scores)}.
- Complete common-support contract-event rows:
  {len(event_panel)}.
- Weather-plus-market training dates:
  {date_rule_scores.loc[date_rule_scores['sample_period'].eq('weather_plus_market_training'), 'target_date'].nunique()}.
- June out-of-sample validation dates:
  {date_rule_scores.loc[date_rule_scores['sample_period'].eq('out_of_sample_validation'), 'target_date'].nunique()}.

## June out-of-sample paired results

{report_table(june_primary)}

The intervals above are percentile intervals from
{specification['comparison_design']['bootstrap_repetitions']:,}
date-level bootstrap replications. They are descriptive uncertainty
intervals for the realised paired score differences.

## Weather-plus-market training-period paired results

{report_table(training_primary)}

## June calibration diagnostics

{chr(10).join(calibration_lines)}

## Integrity

- Duplicate exact-common-support event keys: 0.
- Every complete book contains exactly one realised Yes event.
- GP probabilities sum to one within every book.
- Normalised Polymarket probabilities sum to one within every book.
- All four decision rules have June common-support observations.
- Market prices were not used to fit or select the GP.
- June observations were not used to refit or select a model.

## Evidential boundary

The comparison concerns only the exact complete-book intersection.
Its sample size is therefore smaller than either the standalone GP
evaluation or the standalone market evaluation. Results outside this
intersection are not inferred or imputed.
"""

        (
            stage_output
            / "phase10_report.md"
        ).write_text(
            report,
            encoding="utf-8",
        )

        atomic_replace_directory(
            stage_output,
            output_target,
        )

        print()
        print(
            "=" * 72
        )
        print(
            "PHASE 10 GP VERSUS POLYMARKET: PASSED"
        )
        print(
            "=" * 72
        )
        print(
            "Selected market source:",
            selected_source_path.relative_to(
                ROOT
            ),
        )
        print(
            "Price column:",
            selected_metadata[
                "price_column"
            ],
        )
        print(
            "Matching strategy:",
            selected_metadata[
                "matching_strategy"
            ],
        )
        print(
            "Complete common-support dates:",
            event_panel[
                "target_date"
            ].nunique(),
        )
        print(
            "Complete date-rule books:",
            len(
                date_rule_scores
            ),
        )
        print(
            "Common-support event rows:",
            len(
                event_panel
            ),
        )
        print(
            "Weather-plus-market dates:",
            date_rule_scores.loc[
                date_rule_scores[
                    "sample_period"
                ].eq(
                    "weather_plus_market_training"
                ),
                "target_date",
            ].nunique(),
        )
        print(
            "June dates:",
            date_rule_scores.loc[
                date_rule_scores[
                    "sample_period"
                ].eq(
                    "out_of_sample_validation"
                ),
                "target_date",
            ].nunique(),
        )
        print(
            "Output:",
            output_target.relative_to(
                ROOT
            ),
        )
        print(
            "=" * 72
        )

    finally:
        if stage_root.exists():
            shutil.rmtree(
                stage_root,
                ignore_errors=True,
            )


if __name__ == "__main__":
    main()
