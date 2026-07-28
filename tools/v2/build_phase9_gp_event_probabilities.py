#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
      "phase9_gp_event_probability_spec.json"
)

DATE_COLUMNS = [
    "target_date",
    "event_date",
    "contract_date",
    "settlement_date",
    "date",
]

CONTRACT_ID_COLUMNS = [
    "contract_key",
    "condition_id",
    "contract_id",
    "market_id",
    "token_id",
    "event_id",
    "market_slug",
    "slug",
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

EVENT_TYPE_COLUMNS = [
    "event_type",
    "event_family",
    "contract_event_type",
    "bucket_type",
    "interval_type",
    "tail_type",
]

LOWER_BOUND_COLUMNS = [
    "event_lower_bound_c",
    "lower_bound_c",
    "lower_bound_inclusive_c",
    "event_lower_c",
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
    "event_upper_bound_c",
    "upper_bound_c",
    "upper_bound_exclusive_c",
    "event_upper_c",
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

THRESHOLD_COLUMNS = [
    "event_threshold_c",
    "threshold_c",
    "temperature_threshold_c",
    "contract_threshold_c",
    "threshold",
]

OUTCOME_COLUMNS = [
    "realised_yes",
    "realized_yes",
    "outcome_yes",
    "event_outcome",
    "settlement_outcome",
    "resolved_yes",
    "is_winner",
    "settled_yes",
    "outcome",
    "target",
    "y",
]

OBSERVED_COLUMNS = [
    "hko_absolute_daily_max_c",
    "hko_daily_max_c",
    "realised_hko_daily_max_c",
    "realized_hko_daily_max_c",
    "observed_daily_max_c",
    "actual_daily_max_c",
    "realised_temperature_c",
    "realized_temperature_c",
    "settlement_temperature_c",
    "observed_temperature_c",
    "hko_max_c",
    "daily_max_temperature_c",
]

RULE_ALIASES = {
    "24h": "24h_prior",
    "24hr": "24h_prior",
    "24hprior": "24h_prior",
    "12h": "12h_prior",
    "12hr": "12h_prior",
    "12hprior": "12h_prior",
    "6h": "6h_prior",
    "6hr": "6h_prior",
    "6hprior": "6h_prior",
    "open": "event_day_open",
    "event_open": "event_day_open",
    "eventdayopen": "event_day_open",
    "event_day": "event_day_open",
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


def parse_dates(
    series: pd.Series,
) -> pd.Series:
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


def normalise_rules(
    series: pd.Series,
) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(
            "-",
            "_",
            regex=False,
        )
        .str.replace(
            " ",
            "_",
            regex=False,
        )
        .replace(
            RULE_ALIASES
        )
    )


def coerce_bound(
    series: pd.Series,
) -> pd.Series:
    text = (
        series.astype(str)
        .str.strip()
        .str.lower()
    )

    result = pd.to_numeric(
        text,
        errors="coerce",
    )

    negative_infinity = text.isin(
        {
            "-inf",
            "-infinity",
            "-infinite",
            "negative_infinity",
            "none_lower",
        }
    )

    positive_infinity = text.isin(
        {
            "inf",
            "+inf",
            "infinity",
            "+infinity",
            "infinite",
            "positive_infinity",
            "none_upper",
        }
    )

    result.loc[
        negative_infinity
    ] = -np.inf

    result.loc[
        positive_infinity
    ] = np.inf

    return result


def canonical_event_type(
    series: pd.Series,
) -> pd.Series:
    text = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(
            "-",
            "_",
            regex=False,
        )
        .str.replace(
            " ",
            "_",
            regex=False,
        )
    )

    result = pd.Series(
        pd.NA,
        index=series.index,
        dtype="object",
    )

    result.loc[
        text.str.contains(
            r"lower|below|under|less",
            regex=True,
            na=False,
        )
    ] = "lower_tail"

    result.loc[
        text.str.contains(
            r"upper|above|higher|more",
            regex=True,
            na=False,
        )
    ] = "upper_tail"

    result.loc[
        text.str.contains(
            r"interior|range|between|bucket|interval",
            regex=True,
            na=False,
        )
    ] = "interior"

    return result


def parse_label_bounds(
    value: object,
) -> tuple[
    float,
    float,
    str | None,
]:
    if value is None:
        return (
            np.nan,
            np.nan,
            None,
        )

    text = str(value).strip().lower()

    if not text:
        return (
            np.nan,
            np.nan,
            None,
        )

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

    patterns = [
        (
            rf"between\s+{number}"
            rf"\s*(?:°\s*c|c)?"
            rf"\s+(?:and|to)\s+{number}"
            rf"\s*(?:°\s*c|c)",
            "interior",
        ),
        (
            rf"{number}"
            rf"\s*(?:°\s*c|c)?"
            rf"\s*(?:-|to)\s*{number}"
            rf"\s*(?:°\s*c|c)",
            "interior",
        ),
    ]

    for pattern, event_type in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            lower = float(
                match.group(1)
            )

            upper = float(
                match.group(2)
            )

            if upper > lower:
                return (
                    lower,
                    upper,
                    event_type,
                )

    upper_tail = re.search(
        rf"{number}\s*(?:°\s*c|c)"
        rf"\s*(?:or\s+)?"
        rf"(?:higher|above|more|\+)",
        text,
        flags=re.IGNORECASE,
    )

    if upper_tail:
        return (
            float(
                upper_tail.group(1)
            ),
            np.inf,
            "upper_tail",
        )

    lower_tail_discrete = re.search(
        rf"{number}\s*(?:°\s*c|c)"
        rf"\s*(?:or\s+)?"
        rf"(?:lower|below|less)",
        text,
        flags=re.IGNORECASE,
    )

    if lower_tail_discrete:
        labelled_maximum = float(
            lower_tail_discrete.group(1)
        )

        return (
            -np.inf,
            labelled_maximum + 1.0,
            "lower_tail",
        )

    lower_tail_boundary = re.search(
        rf"(?:below|under|less\s+than)"
        rf"\s*{number}\s*(?:°\s*c|c)",
        text,
        flags=re.IGNORECASE,
    )

    if lower_tail_boundary:
        return (
            -np.inf,
            float(
                lower_tail_boundary.group(1)
            ),
            "lower_tail",
        )

    upper_tail_boundary = re.search(
        rf"(?:above|over|more\s+than|higher\s+than)"
        rf"\s*{number}\s*(?:°\s*c|c)",
        text,
        flags=re.IGNORECASE,
    )

    if upper_tail_boundary:
        return (
            float(
                upper_tail_boundary.group(1)
            ),
            np.inf,
            "upper_tail",
        )

    temperature_values = [
        float(value)
        for value in re.findall(
            rf"{number}\s*(?:°\s*c|c)",
            text,
            flags=re.IGNORECASE,
        )
    ]

    if len(temperature_values) == 1:
        lower = temperature_values[0]

        return (
            lower,
            lower + 1.0,
            "interior",
        )

    return (
        np.nan,
        np.nan,
        None,
    )


def parse_binary_outcome(
    series: pd.Series,
) -> pd.Series:
    result = pd.to_numeric(
        series,
        errors="coerce",
    )

    valid_numeric = result.isin(
        [0.0, 1.0]
    )

    result.loc[
        ~valid_numeric
    ] = np.nan

    text = (
        series.astype(str)
        .str.strip()
        .str.lower()
    )

    positive = text.isin(
        {
            "yes",
            "true",
            "won",
            "winner",
            "resolved_yes",
            "settled_yes",
            "1",
            "1.0",
        }
    )

    negative = text.isin(
        {
            "no",
            "false",
            "lost",
            "loser",
            "resolved_no",
            "settled_no",
            "0",
            "0.0",
        }
    )

    result.loc[positive] = 1.0
    result.loc[negative] = 0.0

    return result


def normal_crps(
    mean: np.ndarray,
    standard_deviation: np.ndarray,
    observed: np.ndarray,
) -> np.ndarray:
    z = (
        observed - mean
    ) / standard_deviation

    return standard_deviation * (
        z
        * (
            2.0 * norm.cdf(z)
            - 1.0
        )
        + 2.0 * norm.pdf(z)
        - 1.0 / math.sqrt(math.pi)
    )


def validate_contract_partition(
    contracts: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[
        dict[str, Any]
    ] = []

    for target_date, group in contracts.groupby(
        "target_date",
        sort=True,
    ):
        ordered = group.sort_values(
            [
                "lower_bound_c",
                "upper_bound_c",
            ],
            kind="stable",
        )

        lower = ordered[
            "lower_bound_c"
        ].to_numpy(
            dtype=float
        )

        upper = ordered[
            "upper_bound_c"
        ].to_numpy(
            dtype=float
        )

        starts_at_negative_infinity = bool(
            np.isneginf(
                lower[0]
            )
        )

        ends_at_positive_infinity = bool(
            np.isposinf(
                upper[-1]
            )
        )

        adjacent = True

        if len(ordered) > 1:
            adjacent = bool(
                np.allclose(
                    upper[:-1],
                    lower[1:],
                    atol=1e-10,
                    rtol=0.0,
                )
            )

        no_invalid_intervals = bool(
            np.all(
                lower < upper
            )
        )

        passed = (
            starts_at_negative_infinity
            and ends_at_positive_infinity
            and adjacent
            and no_invalid_intervals
        )

        rows.append(
            {
                "target_date":
                    target_date,
                "contract_count":
                    len(ordered),
                "starts_at_negative_infinity":
                    starts_at_negative_infinity,
                "ends_at_positive_infinity":
                    ends_at_positive_infinity,
                "adjacent_boundaries":
                    adjacent,
                "valid_interval_order":
                    no_invalid_intervals,
                "partition_passed":
                    passed,
            }
        )

    return pd.DataFrame(rows)


def build_summary(
    event_panel: pd.DataFrame,
    date_rule_scores: pd.DataFrame,
) -> pd.DataFrame:
    summary_rows: list[
        dict[str, Any]
    ] = []

    split_values = [
        "weather_plus_market_training",
        "out_of_sample_validation",
        "all_period",
    ]

    rule_values = sorted(
        date_rule_scores[
            "decision_rule"
        ].unique()
    ) + [
        "all_rules"
    ]

    for split_value in split_values:
        if split_value == "all_period":
            event_split = event_panel
            score_split = date_rule_scores
        else:
            event_split = event_panel.loc[
                event_panel[
                    "sample_period"
                ].eq(
                    split_value
                )
            ]

            score_split = (
                date_rule_scores.loc[
                    date_rule_scores[
                        "sample_period"
                    ].eq(
                        split_value
                    )
                ]
            )

        for rule_value in rule_values:
            if rule_value == "all_rules":
                event_group = event_split
                score_group = score_split
            else:
                event_group = event_split.loc[
                    event_split[
                        "decision_rule"
                    ].eq(
                        rule_value
                    )
                ]

                score_group = score_split.loc[
                    score_split[
                        "decision_rule"
                    ].eq(
                        rule_value
                    )
                ]

            if event_group.empty or score_group.empty:
                continue

            summary_rows.append(
                {
                    "sample_period":
                        split_value,
                    "decision_rule":
                        rule_value,
                    "dates":
                        int(
                            score_group[
                                "target_date"
                            ].nunique()
                        ),
                    "date_rule_rows":
                        int(
                            len(
                                score_group
                            )
                        ),
                    "contract_event_rows":
                        int(
                            len(
                                event_group
                            )
                        ),
                    "mean_binary_brier":
                        float(
                            event_group[
                                "binary_brier"
                            ].mean()
                        ),
                    "mean_binary_log":
                        float(
                            event_group[
                                "binary_log"
                            ].mean()
                        ),
                    "mean_categorical_log":
                        float(
                            score_group[
                                "categorical_log"
                            ].mean()
                        ),
                    "mean_multiclass_brier":
                        float(
                            score_group[
                                "multiclass_brier"
                            ].mean()
                        ),
                    "mean_continuous_crps_c":
                        float(
                            score_group[
                                "continuous_crps_c"
                            ].mean()
                        ),
                    "mean_gp_absolute_error_c":
                        float(
                            score_group[
                                "gp_absolute_error_c"
                            ].mean()
                        ),
                    "mean_gp_error_c":
                        float(
                            score_group[
                                "gp_error_c"
                            ].mean()
                        ),
                    "pit_mean":
                        float(
                            score_group[
                                "pit"
                            ].mean()
                        ),
                    "coverage_50":
                        float(
                            score_group[
                                "covered_50"
                            ].mean()
                        ),
                    "coverage_80":
                        float(
                            score_group[
                                "covered_80"
                            ].mean()
                        ),
                    "coverage_90":
                        float(
                            score_group[
                                "covered_90"
                            ].mean()
                        ),
                    "coverage_95":
                        float(
                            score_group[
                                "covered_95"
                            ].mean()
                        ),
                }
            )

    return pd.DataFrame(
        summary_rows
    )


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


def main() -> None:
    specification = load_json(
        SPEC_PATH
    )

    phase8_manifest_path = (
        ROOT
        / specification[
            "inputs"
        ][
            "phase8_manifest"
        ]
    )

    prediction_path = (
        ROOT
        / specification[
            "inputs"
        ][
            "phase8_predictions"
        ]
    )

    phase8_manifest = load_json(
        phase8_manifest_path
    )

    if phase8_manifest.get(
        "status"
    ) != "passed":
        raise RuntimeError(
            "Phase 8 manifest does not report passed."
        )

    settlement_input = (
        phase8_manifest[
            "inputs"
        ][
            "settlement_universe"
        ]
    )

    contract_source = (
        ROOT
        / settlement_input[
            "path"
        ]
    )

    if not contract_source.exists():
        raise FileNotFoundError(
            contract_source
        )

    predictions = pd.read_csv(
        prediction_path,
        low_memory=False,
    )

    predictions[
        "target_date"
    ] = parse_dates(
        predictions[
            "target_date"
        ]
    )

    predictions[
        "decision_rule"
    ] = normalise_rules(
        predictions[
            "decision_rule"
        ]
    )

    required_prediction_columns = {
        "target_date",
        "decision_rule",
        "forecast_daily_max_c",
        "gp_temperature_mean_c",
        "gp_temperature_std_c",
    }

    missing_prediction_columns = (
        required_prediction_columns
        - set(
            predictions.columns
        )
    )

    if missing_prediction_columns:
        raise RuntimeError(
            "Phase 8 prediction panel is missing: "
            + ", ".join(
                sorted(
                    missing_prediction_columns
                )
            )
        )

    expected = specification[
        "expected_support"
    ]

    if (
        predictions[
            "target_date"
        ].nunique()
        != expected[
            "forecast_supported_dates"
        ]
        or len(predictions)
        != expected[
            "forecast_supported_date_rule_rows"
        ]
    ):
        raise RuntimeError(
            "Phase 8 prediction support count mismatch."
        )

    if predictions[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "Duplicate date-rule keys exist "
            "in Phase 8 predictions."
        )

    contract_raw = pd.read_csv(
        contract_source,
        low_memory=False,
    )

    date_column = first_existing(
        contract_raw.columns,
        DATE_COLUMNS,
    )

    contract_id_column = first_existing(
        contract_raw.columns,
        CONTRACT_ID_COLUMNS,
    )

    label_column = first_existing(
        contract_raw.columns,
        LABEL_COLUMNS,
    )

    event_type_column = first_existing(
        contract_raw.columns,
        EVENT_TYPE_COLUMNS,
    )

    lower_column = first_existing(
        contract_raw.columns,
        LOWER_BOUND_COLUMNS,
    )

    upper_column = first_existing(
        contract_raw.columns,
        UPPER_BOUND_COLUMNS,
    )

    threshold_column = first_existing(
        contract_raw.columns,
        THRESHOLD_COLUMNS,
    )

    outcome_column = first_existing(
        contract_raw.columns,
        OUTCOME_COLUMNS,
    )

    observed_column = first_existing(
        contract_raw.columns,
        OBSERVED_COLUMNS,
    )

    if date_column is None:
        raise RuntimeError(
            "No date column was found in "
            "the certified contract panel."
        )

    target_date = parse_dates(
        contract_raw[
            date_column
        ]
    )

    periods = specification[
        "periods"
    ]

    market_start = pd.Timestamp(
        periods[
            "market_period_start"
        ]
    )

    training_end = pd.Timestamp(
        periods[
            "weather_plus_market_training_end"
        ]
    )

    validation_start = pd.Timestamp(
        periods[
            "out_of_sample_validation_start"
        ]
    )

    validation_end = pd.Timestamp(
        periods[
            "out_of_sample_validation_end"
        ]
    )

    canonical = pd.DataFrame(
        {
            "target_date":
                target_date,
        }
    )

    if contract_id_column is not None:
        canonical[
            "source_contract_id"
        ] = (
            contract_raw[
                contract_id_column
            ]
            .astype(str)
            .str.strip()
        )
    else:
        canonical[
            "source_contract_id"
        ] = pd.NA

    if label_column is not None:
        canonical[
            "event_label"
        ] = (
            contract_raw[
                label_column
            ]
            .astype(str)
            .str.strip()
        )
    else:
        canonical[
            "event_label"
        ] = pd.NA

    if event_type_column is not None:
        canonical[
            "source_event_type"
        ] = canonical_event_type(
            contract_raw[
                event_type_column
            ]
        )
    else:
        canonical[
            "source_event_type"
        ] = pd.NA

    if lower_column is not None:
        canonical[
            "lower_bound_c"
        ] = coerce_bound(
            contract_raw[
                lower_column
            ]
        )
    else:
        canonical[
            "lower_bound_c"
        ] = np.nan

    if upper_column is not None:
        canonical[
            "upper_bound_c"
        ] = coerce_bound(
            contract_raw[
                upper_column
            ]
        )
    else:
        canonical[
            "upper_bound_c"
        ] = np.nan

    parsed_bounds = canonical[
        "event_label"
    ].apply(
        parse_label_bounds
    )

    parsed_lower = parsed_bounds.apply(
        lambda item: item[0]
    )

    parsed_upper = parsed_bounds.apply(
        lambda item: item[1]
    )

    parsed_type = parsed_bounds.apply(
        lambda item: item[2]
    )

    canonical[
        "lower_bound_c"
    ] = canonical[
        "lower_bound_c"
    ].where(
        canonical[
            "lower_bound_c"
        ].notna(),
        parsed_lower,
    )

    canonical[
        "upper_bound_c"
    ] = canonical[
        "upper_bound_c"
    ].where(
        canonical[
            "upper_bound_c"
        ].notna(),
        parsed_upper,
    )

    canonical[
        "event_type"
    ] = canonical[
        "source_event_type"
    ].where(
        canonical[
            "source_event_type"
        ].notna(),
        parsed_type,
    )

    if threshold_column is not None:
        threshold = pd.to_numeric(
            contract_raw[
                threshold_column
            ],
            errors="coerce",
        )

        lower_tail = canonical[
            "event_type"
        ].eq(
            "lower_tail"
        )

        upper_tail = canonical[
            "event_type"
        ].eq(
            "upper_tail"
        )

        canonical.loc[
            lower_tail
            & canonical[
                "lower_bound_c"
            ].isna(),
            "lower_bound_c",
        ] = -np.inf

        canonical.loc[
            lower_tail
            & canonical[
                "upper_bound_c"
            ].isna(),
            "upper_bound_c",
        ] = threshold.loc[
            lower_tail
        ]

        canonical.loc[
            upper_tail
            & canonical[
                "lower_bound_c"
            ].isna(),
            "lower_bound_c",
        ] = threshold.loc[
            upper_tail
        ]

        canonical.loc[
            upper_tail
            & canonical[
                "upper_bound_c"
            ].isna(),
            "upper_bound_c",
        ] = np.inf

    canonical.loc[
        canonical[
            "event_type"
        ].eq(
            "lower_tail"
        )
        & canonical[
            "lower_bound_c"
        ].isna(),
        "lower_bound_c",
    ] = -np.inf

    canonical.loc[
        canonical[
            "event_type"
        ].eq(
            "upper_tail"
        )
        & canonical[
            "upper_bound_c"
        ].isna(),
        "upper_bound_c",
    ] = np.inf

    derived_type = pd.Series(
        pd.NA,
        index=canonical.index,
        dtype="object",
    )

    derived_type.loc[
        np.isneginf(
            canonical[
                "lower_bound_c"
            ]
        )
        & np.isfinite(
            canonical[
                "upper_bound_c"
            ]
        )
    ] = "lower_tail"

    derived_type.loc[
        np.isfinite(
            canonical[
                "lower_bound_c"
            ]
        )
        & np.isposinf(
            canonical[
                "upper_bound_c"
            ]
        )
    ] = "upper_tail"

    derived_type.loc[
        np.isfinite(
            canonical[
                "lower_bound_c"
            ]
        )
        & np.isfinite(
            canonical[
                "upper_bound_c"
            ]
        )
    ] = "interior"

    canonical[
        "event_type"
    ] = canonical[
        "event_type"
    ].where(
        canonical[
            "event_type"
        ].notna(),
        derived_type,
    )

    if observed_column is not None:
        canonical[
            "observed_temperature_c"
        ] = pd.to_numeric(
            contract_raw[
                observed_column
            ],
            errors="coerce",
        )
    else:
        canonical[
            "observed_temperature_c"
        ] = np.nan

    if outcome_column is not None:
        canonical[
            "provided_outcome"
        ] = parse_binary_outcome(
            contract_raw[
                outcome_column
            ]
        )
    else:
        canonical[
            "provided_outcome"
        ] = np.nan

    canonical = canonical.loc[
        canonical[
            "target_date"
        ].between(
            market_start,
            validation_end,
        )
    ].copy()

    missing_bounds = canonical.loc[
        canonical[
            "lower_bound_c"
        ].isna()
        | canonical[
            "upper_bound_c"
        ].isna()
    ]

    if not missing_bounds.empty:
        diagnostic_columns = [
            "target_date",
            "source_contract_id",
            "event_label",
            "source_event_type",
            "lower_bound_c",
            "upper_bound_c",
        ]

        raise RuntimeError(
            "Could not derive event bounds for "
            f"{len(missing_bounds)} rows. Examples:\n"
            + missing_bounds[
                diagnostic_columns
            ]
            .head(20)
            .to_string(
                index=False
            )
        )

    invalid_intervals = canonical.loc[
        ~(
            canonical[
                "lower_bound_c"
            ]
            < canonical[
                "upper_bound_c"
            ]
        )
    ]

    if not invalid_intervals.empty:
        raise RuntimeError(
            "Invalid event intervals were detected."
        )

    generated_key = (
        canonical[
            "target_date"
        ].dt.strftime(
            "%Y-%m-%d"
        )
        + "|"
        + canonical[
            "lower_bound_c"
        ].astype(str)
        + "|"
        + canonical[
            "upper_bound_c"
        ].astype(str)
    )

    canonical[
        "contract_key"
    ] = canonical[
        "source_contract_id"
    ].where(
        canonical[
            "source_contract_id"
        ].notna()
        & canonical[
            "source_contract_id"
        ].ne("")
        & canonical[
            "source_contract_id"
        ].ne("nan"),
        generated_key,
    )

    interval_conflicts = (
        canonical.groupby(
            [
                "target_date",
                "contract_key",
            ]
        )[
            [
                "lower_bound_c",
                "upper_bound_c",
            ]
        ]
        .nunique(
            dropna=False
        )
    )

    if interval_conflicts.gt(1).any().any():
        raise RuntimeError(
            "Conflicting event bounds exist "
            "within a contract key."
        )

    canonical = (
        canonical.sort_values(
            [
                "target_date",
                "lower_bound_c",
                "upper_bound_c",
                "contract_key",
            ],
            kind="stable",
        )
        .drop_duplicates(
            [
                "target_date",
                "contract_key",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    # PHASE9_SCALAR_OBSERVED_COUNT_FIX
    observed_value_counts = (
        canonical.groupby(
            "target_date"
        )[
            "observed_temperature_c"
        ]
        .nunique(
            dropna=True
        )
    )

    inconsistent_observed = (
        observed_value_counts.gt(1)
    )

    if inconsistent_observed.any():
        raise RuntimeError(
            "Conflicting observed temperatures exist "
            "within at least one date."
        )

    canonical[
        "derived_outcome"
    ] = np.where(
        canonical[
            "observed_temperature_c"
        ].notna(),
        (
            canonical[
                "observed_temperature_c"
            ].ge(
                canonical[
                    "lower_bound_c"
                ]
            )
            & canonical[
                "observed_temperature_c"
            ].lt(
                canonical[
                    "upper_bound_c"
                ]
            )
        ).astype(float),
        np.nan,
    )

    outcome_conflict = (
        canonical[
            "provided_outcome"
        ].notna()
        & canonical[
            "derived_outcome"
        ].notna()
        & canonical[
            "provided_outcome"
        ].ne(
            canonical[
                "derived_outcome"
            ]
        )
    )

    if outcome_conflict.any():
        raise RuntimeError(
            "Provided outcomes conflict with outcomes "
            "derived from the observed temperature."
        )

    canonical[
        "realised_yes"
    ] = canonical[
        "provided_outcome"
    ].where(
        canonical[
            "provided_outcome"
        ].notna(),
        canonical[
            "derived_outcome"
        ],
    )

    if canonical[
        "realised_yes"
    ].isna().any():
        raise RuntimeError(
            "Certified contract outcomes are incomplete."
        )

    if canonical[
        "observed_temperature_c"
    ].isna().any():
        raise RuntimeError(
            "Observed temperatures are incomplete; "
            "continuous CRPS cannot be calculated."
        )

    yes_by_date = (
        canonical.groupby(
            "target_date"
        )[
            "realised_yes"
        ].sum()
    )

    if not yes_by_date.eq(1.0).all():
        raise RuntimeError(
            "Each settlement date must contain "
            "exactly one realised Yes event."
        )

    if (
        canonical[
            "target_date"
        ].nunique()
        != expected[
            "settlement_market_universe_dates"
        ]
    ):
        raise RuntimeError(
            "Certified contract panel does not contain "
            "103 settlement dates."
        )

    partition_checks = (
        validate_contract_partition(
            canonical
        )
    )

    if not partition_checks[
        "partition_passed"
    ].all():
        failing = partition_checks.loc[
            ~partition_checks[
                "partition_passed"
            ]
        ]

        raise RuntimeError(
            "The event book does not form a complete "
            "partition on all dates:\n"
            + failing.to_string(
                index=False
            )
        )

    prediction_columns = [
        "target_date",
        "decision_rule",
        "forecast_daily_max_c",
        "gp_temperature_mean_c",
        "gp_temperature_std_c",
    ]

    event_panel = canonical.merge(
        predictions[
            prediction_columns
        ],
        on="target_date",
        how="inner",
        validate="many_to_many",
    )

    if event_panel.empty:
        raise RuntimeError(
            "The contract and prediction panels "
            "have no common dates."
        )

    standard_deviation = event_panel[
        "gp_temperature_std_c"
    ].to_numpy(
        dtype=float
    )

    if (
        ~np.isfinite(
            standard_deviation
        )
    ).any() or (
        standard_deviation <= 0.0
    ).any():
        raise RuntimeError(
            "Non-positive or non-finite GP "
            "standard deviations were found."
        )

    mean = event_panel[
        "gp_temperature_mean_c"
    ].to_numpy(
        dtype=float
    )

    lower = event_panel[
        "lower_bound_c"
    ].to_numpy(
        dtype=float
    )

    upper = event_panel[
        "upper_bound_c"
    ].to_numpy(
        dtype=float
    )

    lower_cdf = norm.cdf(
        (
            lower - mean
        )
        / standard_deviation
    )

    upper_cdf = norm.cdf(
        (
            upper - mean
        )
        / standard_deviation
    )

    probability = np.clip(
        upper_cdf - lower_cdf,
        0.0,
        1.0,
    )

    event_panel[
        "gp_event_probability"
    ] = probability

    event_panel[
        "sample_period"
    ] = np.where(
        event_panel[
            "target_date"
        ].le(
            training_end
        ),
        "weather_plus_market_training",
        "out_of_sample_validation",
    )

    epsilon = float(
        specification[
            "scoring"
        ][
            "probability_clip"
        ]
    )

    clipped_probability = np.clip(
        probability,
        epsilon,
        1.0 - epsilon,
    )

    realised = event_panel[
        "realised_yes"
    ].to_numpy(
        dtype=float
    )

    event_panel[
        "binary_brier"
    ] = (
        probability - realised
    ) ** 2

    event_panel[
        "binary_log"
    ] = -(
        realised
        * np.log(
            clipped_probability
        )
        + (
            1.0 - realised
        )
        * np.log(
            1.0
            - clipped_probability
        )
    )

    mass_checks = (
        event_panel.groupby(
            [
                "target_date",
                "decision_rule",
            ],
            as_index=False,
        )
        .agg(
            event_count=(
                "contract_key",
                "nunique",
            ),
            probability_mass=(
                "gp_event_probability",
                "sum",
            ),
            realised_yes_count=(
                "realised_yes",
                "sum",
            ),
        )
    )

    mass_checks[
        "absolute_mass_error"
    ] = (
        mass_checks[
            "probability_mass"
        ]
        - 1.0
    ).abs()

    mass_checks[
        "mass_check_passed"
    ] = (
        mass_checks[
            "absolute_mass_error"
        ]
        .le(
            1e-8
        )
        & mass_checks[
            "realised_yes_count"
        ].eq(
            1.0
        )
    )

    if not mass_checks[
        "mass_check_passed"
    ].all():
        failing = mass_checks.loc[
            ~mass_checks[
                "mass_check_passed"
            ]
        ]

        raise RuntimeError(
            "Contract probability mass checks failed:\n"
            + failing.head(20).to_string(
                index=False
            )
        )

    yes_probability = (
        event_panel.loc[
            event_panel[
                "realised_yes"
            ].eq(
                1.0
            ),
            [
                "target_date",
                "decision_rule",
                "gp_event_probability",
            ],
        ]
        .rename(
            columns={
                "gp_event_probability":
                    "realised_event_probability",
            }
        )
    )

    multiclass = (
        event_panel.groupby(
            [
                "target_date",
                "decision_rule",
            ],
            as_index=False,
        )
        .agg(
            multiclass_brier=(
                "binary_brier",
                "sum",
            )
        )
    )

    observed_daily = (
        canonical.groupby(
            "target_date",
            as_index=False,
        )
        .agg(
            observed_temperature_c=(
                "observed_temperature_c",
                "first",
            )
        )
    )

    date_rule_scores = (
        predictions[
            prediction_columns
        ]
        .merge(
            observed_daily,
            on="target_date",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            yes_probability,
            on=[
                "target_date",
                "decision_rule",
            ],
            how="inner",
            validate="one_to_one",
        )
        .merge(
            multiclass,
            on=[
                "target_date",
                "decision_rule",
            ],
            how="inner",
            validate="one_to_one",
        )
    )

    date_rule_scores[
        "sample_period"
    ] = np.where(
        date_rule_scores[
            "target_date"
        ].le(
            training_end
        ),
        "weather_plus_market_training",
        "out_of_sample_validation",
    )

    realised_event_probability = (
        date_rule_scores[
            "realised_event_probability"
        ].to_numpy(
            dtype=float
        )
    )

    date_rule_scores[
        "categorical_log"
    ] = -np.log(
        np.clip(
            realised_event_probability,
            epsilon,
            1.0,
        )
    )

    score_mean = date_rule_scores[
        "gp_temperature_mean_c"
    ].to_numpy(
        dtype=float
    )

    score_standard_deviation = (
        date_rule_scores[
            "gp_temperature_std_c"
        ].to_numpy(
            dtype=float
        )
    )

    score_observed = date_rule_scores[
        "observed_temperature_c"
    ].to_numpy(
        dtype=float
    )

    date_rule_scores[
        "continuous_crps_c"
    ] = normal_crps(
        score_mean,
        score_standard_deviation,
        score_observed,
    )

    date_rule_scores[
        "gp_error_c"
    ] = (
        score_mean - score_observed
    )

    date_rule_scores[
        "gp_absolute_error_c"
    ] = np.abs(
        date_rule_scores[
            "gp_error_c"
        ]
    )

    date_rule_scores[
        "pit"
    ] = norm.cdf(
        (
            score_observed - score_mean
        )
        / score_standard_deviation
    )

    for coverage in [
        0.50,
        0.80,
        0.90,
        0.95,
    ]:
        alpha = (
            1.0 - coverage
        ) / 2.0

        lower_quantile = (
            score_mean
            + score_standard_deviation
            * norm.ppf(
                alpha
            )
        )

        upper_quantile = (
            score_mean
            + score_standard_deviation
            * norm.ppf(
                1.0 - alpha
            )
        )

        suffix = int(
            coverage * 100
        )

        date_rule_scores[
            f"covered_{suffix}"
        ] = (
            score_observed
            >= lower_quantile
        ) & (
            score_observed
            <= upper_quantile
        )

    training_dates = (
        date_rule_scores.loc[
            date_rule_scores[
                "sample_period"
            ].eq(
                "weather_plus_market_training"
            ),
            "target_date",
        ].nunique()
    )

    validation_dates = (
        date_rule_scores.loc[
            date_rule_scores[
                "sample_period"
            ].eq(
                "out_of_sample_validation"
            ),
            "target_date",
        ].nunique()
    )

    if (
        training_dates
        != expected[
            "weather_plus_market_training_dates"
        ]
    ):
        raise RuntimeError(
            "Phase 9 training support does not "
            f"contain 72 dates; found {training_dates}."
        )

    if (
        validation_dates
        != expected[
            "out_of_sample_validation_dates"
        ]
    ):
        raise RuntimeError(
            "Phase 9 validation support does not "
            f"contain 30 dates; found {validation_dates}."
        )

    rules = specification[
        "decision_rules"
    ]

    theoretical_contract_rule = (
        canonical.assign(
            _cross_key=1
        )
        .merge(
            pd.DataFrame(
                {
                    "decision_rule":
                        rules,
                    "_cross_key":
                        1,
                }
            ),
            on="_cross_key",
            how="inner",
        )
        .drop(
            columns=[
                "_cross_key",
            ]
        )
    )

    supported_keys = predictions[
        [
            "target_date",
            "decision_rule",
        ]
    ].assign(
        forecast_supported=True
    )

    unsupported_contract_rule = (
        theoretical_contract_rule.merge(
            supported_keys,
            on=[
                "target_date",
                "decision_rule",
            ],
            how="left",
            validate="many_to_one",
        )
        .loc[
            lambda frame:
            frame[
                "forecast_supported"
            ].isna()
        ]
        .drop(
            columns=[
                "forecast_supported",
            ]
        )
        .reset_index(drop=True)
    )

    unsupported_date_rule_count = (
        unsupported_contract_rule[
            [
                "target_date",
                "decision_rule",
            ]
        ]
        .drop_duplicates()
        .shape[0]
    )

    if (
        unsupported_date_rule_count
        != expected[
            "missing_forecast_date_rule_rows"
        ]
    ):
        raise RuntimeError(
            "Unsupported date-rule count mismatch: "
            f"found {unsupported_date_rule_count}."
        )

    summary = build_summary(
        event_panel,
        date_rule_scores,
    )

    output_target = (
        ROOT
        / specification[
            "output_directory"
        ]
    )

    stage_root = Path(
        tempfile.mkdtemp(
            prefix="phase9_gp_event_"
        )
    )

    stage_output = (
        stage_root
        / "phase9_gp_event_probabilities"
    )

    stage_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        event_panel = event_panel.sort_values(
            [
                "target_date",
                "decision_rule",
                "lower_bound_c",
                "upper_bound_c",
                "contract_key",
            ],
            kind="stable",
        ).reset_index(
            drop=True
        )

        date_rule_scores = (
            date_rule_scores.sort_values(
                [
                    "target_date",
                    "decision_rule",
                ],
                kind="stable",
            )
            .reset_index(drop=True)
        )

        event_panel.to_csv(
            stage_output
            / "phase9_gp_contract_event_probability_panel.csv",
            index=False,
        )

        event_panel.loc[
            event_panel[
                "sample_period"
            ].eq(
                "weather_plus_market_training"
            )
        ].to_csv(
            stage_output
            / "phase9_weather_plus_market_event_panel.csv",
            index=False,
        )

        event_panel.loc[
            event_panel[
                "sample_period"
            ].eq(
                "out_of_sample_validation"
            )
        ].to_csv(
            stage_output
            / "phase9_june_out_of_sample_event_panel.csv",
            index=False,
        )

        date_rule_scores.to_csv(
            stage_output
            / "phase9_date_rule_score_panel.csv",
            index=False,
        )

        summary.to_csv(
            stage_output
            / "phase9_score_summary.csv",
            index=False,
        )

        mass_checks.to_csv(
            stage_output
            / "phase9_probability_mass_checks.csv",
            index=False,
        )

        partition_checks.to_csv(
            stage_output
            / "phase9_contract_partition_checks.csv",
            index=False,
        )

        unsupported_contract_rule.to_csv(
            stage_output
            / "phase9_unsupported_contract_rule_panel.csv",
            index=False,
        )

        detected_columns = {
            "date_column":
                date_column,
            "contract_id_column":
                contract_id_column,
            "label_column":
                label_column,
            "event_type_column":
                event_type_column,
            "lower_bound_column":
                lower_column,
            "upper_bound_column":
                upper_column,
            "threshold_column":
                threshold_column,
            "outcome_column":
                outcome_column,
            "observed_temperature_column":
                observed_column,
        }

        manifest = {
            "phase": 9,
            "status": "passed",
            "method": {
                "temperature_distribution":
                    "Gaussian",
                "location":
                    "phase8_gp_temperature_mean_c",
                "scale":
                    "phase8_gp_temperature_std_c",
                "event_probability":
                    "normal_cdf_interval_mass",
                "continuous_score":
                    "normal_crps",
                "probability_support":
                    "exact_common_support",
                "interval_convention":
                    "[lower_bound_c, upper_bound_c)",
            },
            "inputs": {
                "phase8_manifest": {
                    "path":
                        str(
                            phase8_manifest_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            phase8_manifest_path
                        ),
                },
                "phase8_predictions": {
                    "path":
                        str(
                            prediction_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            prediction_path
                        ),
                },
                "certified_contract_panel": {
                    "path":
                        str(
                            contract_source.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256(
                            contract_source
                        ),
                    "detected_columns":
                        detected_columns,
                },
            },
            "counts": {
                "settlement_market_universe_dates":
                    int(
                        canonical[
                            "target_date"
                        ].nunique()
                    ),
                "certified_contract_rows":
                    int(
                        len(
                            canonical
                        )
                    ),
                "forecast_supported_dates":
                    int(
                        event_panel[
                            "target_date"
                        ].nunique()
                    ),
                "forecast_supported_date_rule_rows":
                    int(
                        date_rule_scores.shape[0]
                    ),
                "contract_event_probability_rows":
                    int(
                        len(
                            event_panel
                        )
                    ),
                "weather_plus_market_training_dates":
                    int(
                        training_dates
                    ),
                "weather_plus_market_event_rows":
                    int(
                        event_panel.loc[
                            event_panel[
                                "sample_period"
                            ].eq(
                                "weather_plus_market_training"
                            )
                        ].shape[0]
                    ),
                "out_of_sample_validation_dates":
                    int(
                        validation_dates
                    ),
                "out_of_sample_validation_event_rows":
                    int(
                        event_panel.loc[
                            event_panel[
                                "sample_period"
                            ].eq(
                                "out_of_sample_validation"
                            )
                        ].shape[0]
                    ),
                "unsupported_date_rule_rows":
                    int(
                        unsupported_date_rule_count
                    ),
                "unsupported_contract_rule_rows":
                    int(
                        len(
                            unsupported_contract_rule
                        )
                    ),
            },
            "integrity": {
                "all_contract_books_partition_real_line":
                    bool(
                        partition_checks[
                            "partition_passed"
                        ].all()
                    ),
                "all_probability_masses_sum_to_one":
                    bool(
                        mass_checks[
                            "mass_check_passed"
                        ].all()
                    ),
                "maximum_absolute_mass_error":
                    float(
                        mass_checks[
                            "absolute_mass_error"
                        ].max()
                    ),
                "exactly_one_realised_yes_per_date":
                    bool(
                        yes_by_date.eq(
                            1.0
                        ).all()
                    ),
                "duplicate_event_probability_keys":
                    int(
                        event_panel.duplicated(
                            [
                                "target_date",
                                "decision_rule",
                                "contract_key",
                            ]
                        ).sum()
                    ),
            },
            "restrictions":
                specification[
                    "restrictions"
                ],
        }

        (
            stage_output
            / "phase9_manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        overall = summary.loc[
            summary[
                "sample_period"
            ].eq(
                "all_period"
            )
            & summary[
                "decision_rule"
            ].eq(
                "all_rules"
            )
        ].iloc[0]

        june_overall = summary.loc[
            summary[
                "sample_period"
            ].eq(
                "out_of_sample_validation"
            )
            & summary[
                "decision_rule"
            ].eq(
                "all_rules"
            )
        ].iloc[0]

        report = f"""# Phase 9 GP Contract-Event Probability Audit

## Status

PASSED

## Probability construction

For each forecast-supported date and decision rule, the Phase 8
Gaussian-process predictive distribution is treated as a Gaussian
temperature distribution with mean `gp_temperature_mean_c` and
standard deviation `gp_temperature_std_c`.

For a canonical contract event with interval
`[lower_bound_c, upper_bound_c)`, the event probability equals the
corresponding Gaussian CDF interval mass.

## Certified support

- Settlement and market universe: {canonical['target_date'].nunique()} dates.
- Canonical contract rows: {len(canonical)}.
- Forecast-supported dates: {event_panel['target_date'].nunique()}.
- Forecast-supported date-rule rows: {len(date_rule_scores)}.
- Contract-event probability rows: {len(event_panel)}.
- Weather-plus-market training dates: {training_dates}.
- June out-of-sample validation dates: {validation_dates}.
- Unsupported date-rule rows: {unsupported_date_rule_count}.
- No missing forecasts were imputed.

## Integrity

- All daily contract books form complete interval partitions: yes.
- All date-rule probability masses sum to one: yes.
- Maximum absolute probability-mass error:
  {mass_checks['absolute_mass_error'].max():.12g}.
- Exactly one realised Yes event occurs on every settlement date: yes.
- Duplicate contract-event probability keys: 0.

## Overall proper scores

- Mean binary Brier score:
  {overall['mean_binary_brier']:.8f}.
- Mean binary log score:
  {overall['mean_binary_log']:.8f}.
- Mean categorical log score:
  {overall['mean_categorical_log']:.8f}.
- Mean multiclass Brier score:
  {overall['mean_multiclass_brier']:.8f}.
- Mean continuous CRPS:
  {overall['mean_continuous_crps_c']:.8f} degrees Celsius.
- Mean GP absolute error:
  {overall['mean_gp_absolute_error_c']:.8f} degrees Celsius.

## June out-of-sample proper scores

- Mean binary Brier score:
  {june_overall['mean_binary_brier']:.8f}.
- Mean binary log score:
  {june_overall['mean_binary_log']:.8f}.
- Mean categorical log score:
  {june_overall['mean_categorical_log']:.8f}.
- Mean multiclass Brier score:
  {june_overall['mean_multiclass_brier']:.8f}.
- Mean continuous CRPS:
  {june_overall['mean_continuous_crps_c']:.8f} degrees Celsius.
- Mean GP absolute error:
  {june_overall['mean_gp_absolute_error_c']:.8f} degrees Celsius.

## Evidential boundary

No market price was used. June data were not used to refit the GP,
select a kernel, or impute a missing forecast. June is evaluated only
after the Phase 8 model and support rules were fixed.
"""

        (
            stage_output
            / "phase9_report.md"
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
            "PHASE 9 GP EVENT PROBABILITIES: PASSED"
        )
        print(
            "=" * 72
        )
        print(
            "Contract source:",
            contract_source.relative_to(
                ROOT
            ),
        )
        print(
            "Detected columns:",
            detected_columns,
        )
        print(
            "Settlement dates:",
            canonical[
                "target_date"
            ].nunique(),
        )
        print(
            "Canonical contract rows:",
            len(canonical),
        )
        print(
            "Forecast-supported dates:",
            event_panel[
                "target_date"
            ].nunique(),
        )
        print(
            "Date-rule score rows:",
            len(date_rule_scores),
        )
        print(
            "Contract-event probability rows:",
            len(event_panel),
        )
        print(
            "Training dates:",
            training_dates,
        )
        print(
            "June validation dates:",
            validation_dates,
        )
        print(
            "Maximum probability-mass error:",
            mass_checks[
                "absolute_mass_error"
            ].max(),
        )
        print(
            "No market prices were used."
        )
        print(
            "No missing forecast was imputed."
        )
        print(
            "=" * 72
        )
        print(
            "Outputs:",
            output_target.relative_to(
                ROOT
            ),
        )

    finally:
        if stage_root.exists():
            shutil.rmtree(
                stage_root,
                ignore_errors=True,
            )


if __name__ == "__main__":
    main()
