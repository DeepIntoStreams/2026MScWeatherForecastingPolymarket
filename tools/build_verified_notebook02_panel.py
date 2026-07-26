#!/usr/bin/env python3
"""Build the verified March-June deterministic forecast panel."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml


ROOT = Path.cwd()

PROPOSAL_PATH = Path(
    "/tmp/02_pre_june_recovery_proposal.json"
)

CANDIDATE_PATH = Path(
    "/tmp/02_pre_june_recovery_candidate_groups.csv"
)

COLUMN_AUDIT_PATH = Path(
    "/tmp/02_daily_forecast_column_audit.csv"
)

JUNE_PATH = (
    ROOT
    / "data"
    / "interim"
    / "notebook02_june_selected_forecast_panel.csv"
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

CHRONOLOGY_PANEL_PATH = (
    ROOT
    / "data"
    / "processed"
    / "02_chronological_design_panel.csv"
)

HISTORICAL_PANEL_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_verified_historical_forecast_panel.csv"
)

RECONCILIATION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_historical_daily_hourly_reconciliation.csv"
)

SUPPORT_MATRIX_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_date_rule_support_matrix.csv"
)

SUPPORT_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_full_support_summary.json"
)

PANEL_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_panel_construction_summary.json"
)

BLOCK_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "03_chronology_block_summary.csv"
)

FOLD_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "03_development_fold_summary.csv"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "03_chronology_integrity_checks.csv"
)

FORENSIC_DECISION_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "02_verified_historical_forecast_decision.json"
)

PANEL_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "02_verified_full_panel_manifest.json"
)

CHRONOLOGY_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "03_chronology_manifest.json"
)

CHRONOLOGY_POLICY_PATH = (
    ROOT
    / "config"
    / "chronology_policy.yaml"
)

VALID_RULES = (
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
)


def normalise_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("°", "")

    return re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    ).strip("_")


def normalise_frame(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str]]:
    result = frame.copy()

    seen: dict[str, int] = {}
    columns: list[str] = []
    originals: dict[str, str] = {}

    for original in result.columns:
        base = normalise_name(
            original
        ) or "unnamed"

        count = seen.get(
            base,
            0,
        )

        seen[base] = count + 1

        normalised = (
            base
            if count == 0
            else f"{base}_{count + 1}"
        )

        columns.append(normalised)
        originals[normalised] = str(original)

    result.columns = columns

    return result, originals


def read_table(
    path: Path,
) -> tuple[pd.DataFrame, dict[str, str]]:
    return normalise_frame(
        pd.read_csv(
            path,
            low_memory=False,
        )
    )


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


def parse_date(
    series: pd.Series,
) -> pd.Series:
    try:
        parsed = pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
        )
    except (TypeError, ValueError):
        parsed = pd.to_datetime(
            series,
            errors="coerce",
        )

    return parsed.dt.strftime(
        "%Y-%m-%d"
    )


def parse_utc(
    series: pd.Series,
) -> pd.Series:
    try:
        return pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
            utc=True,
        )
    except (TypeError, ValueError):
        return pd.to_datetime(
            series,
            errors="coerce",
            utc=True,
        )


def to_celsius(
    series: pd.Series,
) -> pd.Series:
    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    finite = numeric.dropna()

    if (
        not finite.empty
        and float(
            finite.median()
        )
        > 150.0
    ):
        numeric = numeric - 273.15

    return numeric


def bool_mask(
    series: pd.Series,
) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "yes",
            }
        )
    )


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def find_column(
    columns: list[str],
    priorities: tuple[str, ...],
) -> str:
    for candidate in priorities:
        if candidate in columns:
            return candidate

    raise RuntimeError(
        "None of the required columns was found: "
        + ", ".join(priorities)
    )


def select_verified_forecast_column(
    audit: pd.DataFrame,
) -> dict[str, Any]:
    for column in (
        "strict_hourly_match",
        "forecast_named",
        "exact_hko_column",
    ):
        audit[column] = bool_mask(
            audit[column]
        )

    eligible = audit.loc[
        audit[
            "strict_hourly_match"
        ]
        & audit[
            "forecast_named"
        ]
        & ~audit[
            "exact_hko_column"
        ]
        & audit[
            "hourly_overlap_rows"
        ].ge(250)
    ].copy()

    if eligible.empty:
        raise RuntimeError(
            "No forecast-labelled column exactly matches "
            "the independently reconstructed hourly forecasts."
        )

    eligible = eligible.sort_values(
        [
            "hourly_mae_c",
            "hourly_max_absolute_error_c",
            "hourly_overlap_rows",
        ],
        ascending=[
            True,
            True,
            False,
        ],
    )

    selected = eligible.iloc[0].to_dict()

    if not math.isclose(
        float(
            selected["hourly_mae_c"]
        ),
        0.0,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            "The selected historical forecast column does not "
            "match the hourly reconstruction exactly."
        )

    if int(
        selected[
            "historical_date_rule_keys"
        ]
    ) != 256:
        raise RuntimeError(
            "The selected historical forecast column must contain "
            "exactly 256 verified keys."
        )

    return selected


def build_historical_panel() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    proposal = json.loads(
        PROPOSAL_PATH.read_text(
            encoding="utf-8"
        )
    )

    audit = pd.read_csv(
        COLUMN_AUDIT_PATH,
        low_memory=False,
    )

    selected_audit = (
        select_verified_forecast_column(
            audit
        )
    )

    selected_normalised = str(
        selected_audit[
            "normalised_column"
        ]
    )

    selected_original = str(
        selected_audit[
            "original_column"
        ]
    )

    if not selected_normalised.startswith(
        "forecast_"
    ):
        raise RuntimeError(
            "The verified column is not explicitly forecast-labelled."
        )

    daily_definition = proposal[
        "detected_columns"
    ][
        "historical_daily_maximum"
    ]

    daily_path = (
        ROOT
        / daily_definition["path"]
    )

    daily, originals = read_table(
        daily_path
    )

    date_column = normalise_name(
        daily_definition[
            "target_date_column"
        ]
    )

    rule_column = normalise_name(
        daily_definition[
            "decision_rule_column"
        ]
    )

    if selected_normalised not in daily.columns:
        raise RuntimeError(
            f"Verified forecast column is absent: {selected_normalised}"
        )

    daily_panel = pd.DataFrame(
        {
            "target_date": parse_date(
                daily[
                    date_column
                ]
            ),
            "decision_rule": (
                daily[
                    rule_column
                ].map(
                    normalise_rule
                )
            ),
            "daily_stored_forecast_c": (
                to_celsius(
                    daily[
                        selected_normalised
                    ]
                )
            ),
        }
    )

    daily_panel = daily_panel.loc[
        daily_panel[
            "target_date"
        ].notna()
        & daily_panel[
            "decision_rule"
        ].isin(
            VALID_RULES
        )
        & daily_panel[
            "daily_stored_forecast_c"
        ].notna()
        & daily_panel[
            "target_date"
        ].lt(
            "2026-06-01"
        )
    ].copy()

    value_conflicts = (
        daily_panel.groupby(
            [
                "target_date",
                "decision_rule",
            ]
        )[
            "daily_stored_forecast_c"
        ]
        .nunique()
    )

    if value_conflicts.gt(1).any():
        raise RuntimeError(
            "The verified daily forecast column conflicts "
            "within a date-rule key."
        )

    daily_panel = (
        daily_panel.groupby(
            [
                "target_date",
                "decision_rule",
            ],
            as_index=False,
        )[
            "daily_stored_forecast_c"
        ]
        .first()
    )

    candidates, _ = read_table(
        CANDIDATE_PATH
    )

    if (
        "hourly_reconstructed_max_c"
        not in candidates.columns
        and "forecast_daily_max_c"
        in candidates.columns
    ):
        candidates = candidates.rename(
            columns={
                "forecast_daily_max_c":
                "hourly_reconstructed_max_c"
            }
        )

    required = [
        "target_date",
        "decision_rule",
        "join_initialisation",
        "decision_cutoff_utc",
        "join_resolution",
        "recoverable",
        "unique_local_hours",
        "hourly_reconstructed_max_c",
    ]

    missing = [
        column
        for column in required
        if column not in candidates.columns
    ]

    if missing:
        raise RuntimeError(
            "Hourly reconstruction table is missing: "
            + ", ".join(missing)
        )

    candidates[
        "target_date"
    ] = parse_date(
        candidates[
            "target_date"
        ]
    )

    candidates[
        "decision_rule"
    ] = candidates[
        "decision_rule"
    ].map(
        normalise_rule
    )

    candidates[
        "forecast_issue_time_utc"
    ] = parse_utc(
        candidates[
            "join_initialisation"
        ]
    )

    candidates[
        "decision_time_utc"
    ] = parse_utc(
        candidates[
            "decision_cutoff_utc"
        ]
    )

    candidates[
        "hourly_reconstructed_max_c"
    ] = to_celsius(
        candidates[
            "hourly_reconstructed_max_c"
        ]
    )

    candidates[
        "recoverable_boolean"
    ] = bool_mask(
        candidates[
            "recoverable"
        ]
    )

    hourly = candidates.loc[
        candidates[
            "join_resolution"
        ].astype(str).eq(
            "exact"
        )
        & candidates[
            "recoverable_boolean"
        ],
        [
            "target_date",
            "decision_rule",
            "forecast_issue_time_utc",
            "decision_time_utc",
            "unique_local_hours",
            "hourly_reconstructed_max_c",
        ],
    ].copy()

    hourly = hourly.drop_duplicates(
        [
            "target_date",
            "decision_rule",
        ]
    )

    if len(hourly) != 256:
        raise RuntimeError(
            f"Expected 256 verified historical paths; found {len(hourly)}."
        )

    if hourly[
        "target_date"
    ].nunique() != 72:
        raise RuntimeError(
            "Expected 72 historical dates with verified paths."
        )

    if not hourly[
        "unique_local_hours"
    ].eq(24).all():
        raise RuntimeError(
            "A verified historical path lacks 24 local hours."
        )

    if not (
        hourly[
            "forecast_issue_time_utc"
        ]
        <= hourly[
            "decision_time_utc"
        ]
    ).all():
        raise RuntimeError(
            "A verified historical forecast violates the "
            "information-time condition."
        )

    reconciliation = hourly.merge(
        daily_panel,
        on=[
            "target_date",
            "decision_rule",
        ],
        how="left",
        validate="one_to_one",
    )

    if reconciliation[
        "daily_stored_forecast_c"
    ].isna().any():
        raise RuntimeError(
            "A verified hourly path has no stored daily forecast."
        )

    reconciliation[
        "absolute_difference_c"
    ] = (
        reconciliation[
            "hourly_reconstructed_max_c"
        ]
        - reconciliation[
            "daily_stored_forecast_c"
        ]
    ).abs()

    if not reconciliation[
        "absolute_difference_c"
    ].le(1e-9).all():
        raise RuntimeError(
            "The stored daily forecast does not exactly equal "
            "the reconstructed hourly maximum."
        )

    historical = pd.DataFrame(
        {
            "target_date": (
                reconciliation[
                    "target_date"
                ]
            ),
            "decision_rule": (
                reconciliation[
                    "decision_rule"
                ]
            ),
            "forecast_daily_max_c": (
                reconciliation[
                    "hourly_reconstructed_max_c"
                ]
            ),
            "forecast_issue_time_utc": (
                reconciliation[
                    "forecast_issue_time_utc"
                ]
            ),
            "decision_time_utc": (
                reconciliation[
                    "decision_time_utc"
                ]
            ),
            "unique_local_hours": (
                reconciliation[
                    "unique_local_hours"
                ]
            ),
            "source_period": (
                "historical_march_may"
            ),
            "forecast_value_source": (
                "reconstructed_complete_hourly_path"
            ),
            "daily_forecast_column": (
                selected_original
            ),
            "daily_forecast_corroborated": (
                True
            ),
            "information_time_verified": (
                True
            ),
        }
    )

    decision = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "USE_256_INDEPENDENTLY_VERIFIED_HISTORICAL_ROWS"
        ),
        "selected_forecast_column": (
            selected_original
        ),
        "selected_forecast_normalised_column": (
            selected_normalised
        ),
        "daily_source": str(
            daily_path.relative_to(
                ROOT
            )
        ),
        "historical_rows_retained": 256,
        "historical_dates_retained": 72,
        "historical_request_rows_not_promoted": 36,
        "hourly_overlap_rows": int(
            selected_audit[
                "hourly_overlap_rows"
            ]
        ),
        "hourly_mae_c": float(
            selected_audit[
                "hourly_mae_c"
            ]
        ),
        "hourly_max_absolute_error_c": float(
            selected_audit[
                "hourly_max_absolute_error_c"
            ]
        ),
        "hko_mae_c": float(
            selected_audit[
                "hko_mae_c"
            ]
        ),
        "exact_hko_share": float(
            selected_audit[
                "exact_hko_share"
            ]
        ),
        "false_negative_reason": (
            "The earlier audit treated every column name containing "
            "'hko' as an outcome. Here 'hko' identifies the forecast "
            "location and the column is explicitly forecast-labelled."
        ),
        "automatic_292_row_historical_panel_permitted": (
            False
        ),
    }

    return (
        historical,
        reconciliation,
        decision,
    )


def build_june_panel() -> pd.DataFrame:
    june, _ = read_table(
        JUNE_PATH
    )

    required = [
        "target_date",
        "decision_rule",
        "forecast_daily_max_c",
        "forecast_issue_time_utc",
        "decision_time_utc",
        "unique_local_hours",
    ]

    missing = [
        column
        for column in required
        if column not in june.columns
    ]

    if missing:
        raise RuntimeError(
            "The preserved June panel is missing: "
            + ", ".join(missing)
        )

    june[
        "target_date"
    ] = parse_date(
        june[
            "target_date"
        ]
    )

    june[
        "decision_rule"
    ] = june[
        "decision_rule"
    ].map(
        normalise_rule
    )

    june[
        "forecast_daily_max_c"
    ] = to_celsius(
        june[
            "forecast_daily_max_c"
        ]
    )

    june[
        "forecast_issue_time_utc"
    ] = parse_utc(
        june[
            "forecast_issue_time_utc"
        ]
    )

    june[
        "decision_time_utc"
    ] = parse_utc(
        june[
            "decision_time_utc"
        ]
    )

    if len(june) != 119:
        raise RuntimeError(
            "The preserved June panel must contain 119 rows."
        )

    if june[
        "target_date"
    ].nunique() != 30:
        raise RuntimeError(
            "The preserved June panel must contain 30 dates."
        )

    if not june[
        "unique_local_hours"
    ].eq(24).all():
        raise RuntimeError(
            "A June path lacks 24 local hours."
        )

    if not (
        june[
            "forecast_issue_time_utc"
        ]
        <= june[
            "decision_time_utc"
        ]
    ).all():
        raise RuntimeError(
            "A June forecast violates the information-time condition."
        )

    result = pd.DataFrame(
        {
            "target_date": (
                june[
                    "target_date"
                ]
            ),
            "decision_rule": (
                june[
                    "decision_rule"
                ]
            ),
            "forecast_daily_max_c": (
                june[
                    "forecast_daily_max_c"
                ]
            ),
            "forecast_issue_time_utc": (
                june[
                    "forecast_issue_time_utc"
                ]
            ),
            "decision_time_utc": (
                june[
                    "decision_time_utc"
                ]
            ),
            "unique_local_hours": (
                june[
                    "unique_local_hours"
                ]
            ),
            "source_period": (
                "june_external"
            ),
            "forecast_value_source": (
                "reconstructed_complete_hourly_path"
            ),
            "daily_forecast_column": (
                ""
            ),
            "daily_forecast_corroborated": (
                True
            ),
            "information_time_verified": (
                True
            ),
        }
    )

    return result


def load_hko() -> pd.DataFrame:
    hko, _ = read_table(
        HKO_PATH
    )

    date_column = find_column(
        list(hko.columns),
        (
            "target_date",
            "event_date",
            "original_event_date",
            "date",
        ),
    )

    value_column = find_column(
        list(hko.columns),
        (
            "hko_daily_max_c",
            "hko_tmax_c",
            "hko_tmax",
            "daily_max_c",
        ),
    )

    result = pd.DataFrame(
        {
            "target_date": parse_date(
                hko[
                    date_column
                ]
            ),
            "hko_daily_max_c": (
                to_celsius(
                    hko[
                        value_column
                    ]
                )
            ),
        }
    ).dropna()

    conflicts = (
        result.groupby(
            "target_date"
        )[
            "hko_daily_max_c"
        ]
        .nunique()
    )

    if conflicts.gt(1).any():
        raise RuntimeError(
            "HKO outcomes conflict within a date."
        )

    return result.drop_duplicates(
        "target_date"
    )


def load_certified_dates() -> list[str]:
    contracts, _ = read_table(
        CONTRACT_PATH
    )

    date_column = find_column(
        list(contracts.columns),
        (
            "event_date",
            "original_event_date",
            "target_date",
        ),
    )

    dates = sorted(
        parse_date(
            contracts[
                date_column
            ]
        )
        .dropna()
        .unique()
    )

    if len(dates) != 103:
        raise RuntimeError(
            f"Expected 103 certified dates; found {len(dates)}."
        )

    return dates


def assign_chronology(
    panel: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    result = panel.copy()

    dates = pd.to_datetime(
        result[
            "target_date"
        ],
        errors="raise",
    )

    result[
        "chronology_block"
    ] = np.select(
        [
            dates.le(
                "2026-04-11"
            ),
            dates.between(
                "2026-04-12",
                "2026-05-21",
            ),
            dates.between(
                "2026-05-22",
                "2026-05-31",
            ),
            dates.between(
                "2026-06-01",
                "2026-06-30",
            ),
        ],
        [
            "warmup_training",
            "development_validation",
            "holdout",
            "external_test",
        ],
        default="UNASSIGNED",
    )

    if result[
        "chronology_block"
    ].eq(
        "UNASSIGNED"
    ).any():
        raise RuntimeError(
            "A date was not assigned to a chronological block."
        )

    result[
        "development_fold"
    ] = pd.NA

    development_dates = sorted(
        result.loc[
            result[
                "chronology_block"
            ].eq(
                "development_validation"
            ),
            "target_date",
        ].unique()
    )

    if len(
        development_dates
    ) < 30:
        raise RuntimeError(
            "Fewer than 30 development dates remain."
        )

    fold_arrays = np.array_split(
        np.array(
            development_dates,
            dtype=object,
        ),
        4,
    )

    fold_map = {}

    for fold_number, values in enumerate(
        fold_arrays,
        start=1,
    ):
        for value in values.tolist():
            fold_map[value] = fold_number

    development_mask = result[
        "chronology_block"
    ].eq(
        "development_validation"
    )

    result.loc[
        development_mask,
        "development_fold",
    ] = result.loc[
        development_mask,
        "target_date",
    ].map(
        fold_map
    )

    result[
        "outcome_may_influence_model_choice"
    ] = result[
        "chronology_block"
    ].isin(
        [
            "warmup_training",
            "development_validation",
        ]
    )

    result[
        "used_in_final_fit_before_holdout"
    ] = result[
        "chronology_block"
    ].isin(
        [
            "warmup_training",
            "development_validation",
        ]
    )

    result[
        "used_to_refit_before_external_test"
    ] = False

    block_summary = (
        result[
            [
                "target_date",
                "chronology_block",
            ]
        ]
        .drop_duplicates()
        .groupby(
            "chronology_block"
        )
        .agg(
            dates=(
                "target_date",
                "nunique",
            ),
            start_date=(
                "target_date",
                "min",
            ),
            end_date=(
                "target_date",
                "max",
            ),
        )
        .reset_index()
        .sort_values(
            "start_date"
        )
    )

    block_rows = (
        result.groupby(
            "chronology_block"
        )
        .size()
        .rename(
            "date_rule_rows"
        )
        .reset_index()
    )

    block_summary = block_summary.merge(
        block_rows,
        on="chronology_block",
        how="left",
        validate="one_to_one",
    )

    block_counts = dict(
        zip(
            block_summary[
                "chronology_block"
            ],
            block_summary[
                "dates"
            ],
        )
    )

    if block_counts.get(
        "warmup_training",
        0,
    ) < 20:
        raise RuntimeError(
            "The warm-up block contains fewer than 20 dates."
        )

    if block_counts.get(
        "development_validation",
        0,
    ) < 30:
        raise RuntimeError(
            "The development block contains fewer than 30 dates."
        )

    if block_counts.get(
        "holdout",
        0,
    ) < 8:
        raise RuntimeError(
            "The holdout contains fewer than eight dates."
        )

    if block_counts.get(
        "external_test",
        0,
    ) != 30:
        raise RuntimeError(
            "The external test must contain all 30 June dates."
        )

    fold_rows = []

    warmup_dates = sorted(
        result.loc[
            result[
                "chronology_block"
            ].eq(
                "warmup_training"
            ),
            "target_date",
        ].unique()
    )

    prior_dates = list(
        warmup_dates
    )

    for fold_number, validation_dates in enumerate(
        fold_arrays,
        start=1,
    ):
        validation = validation_dates.tolist()

        fold_rows.append(
            {
                "fold": fold_number,
                "training_dates": len(
                    prior_dates
                ),
                "training_start": (
                    prior_dates[0]
                ),
                "training_end": (
                    prior_dates[-1]
                ),
                "validation_dates": len(
                    validation
                ),
                "validation_start": (
                    validation[0]
                ),
                "validation_end": (
                    validation[-1]
                ),
                "date_sets_disjoint": (
                    set(
                        prior_dates
                    ).isdisjoint(
                        validation
                    )
                ),
                "training_precedes_validation": (
                    prior_dates[-1]
                    < validation[0]
                ),
            }
        )

        prior_dates.extend(
            validation
        )

    fold_summary = pd.DataFrame(
        fold_rows
    )

    if not fold_summary[
        "date_sets_disjoint"
    ].all():
        raise RuntimeError(
            "A development fold overlaps its training dates."
        )

    if not fold_summary[
        "training_precedes_validation"
    ].all():
        raise RuntimeError(
            "A validation fold is not strictly later than training."
        )

    return (
        result,
        block_summary,
        fold_summary,
    )


def main() -> None:
    (
        historical,
        reconciliation,
        forensic_decision,
    ) = build_historical_panel()

    june = build_june_panel()

    selected = pd.concat(
        [
            historical,
            june,
        ],
        ignore_index=True,
    ).sort_values(
        [
            "target_date",
            "decision_rule",
        ]
    ).reset_index(
        drop=True
    )

    if len(selected) != 375:
        raise RuntimeError(
            f"Expected 375 verified rows; found {len(selected)}."
        )

    if selected[
        "target_date"
    ].nunique() != 102:
        raise RuntimeError(
            "Expected 102 dates with at least one verified forecast."
        )

    if selected[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "The combined panel duplicates a date-rule key."
        )

    if not (
        selected[
            "forecast_issue_time_utc"
        ]
        <= selected[
            "decision_time_utc"
        ]
    ).all():
        raise RuntimeError(
            "The combined panel contains lookahead."
        )

    if not selected[
        "unique_local_hours"
    ].eq(24).all():
        raise RuntimeError(
            "A retained forecast does not contain 24 local hours."
        )

    hko = load_hko()

    training = selected.merge(
        hko,
        on="target_date",
        how="inner",
        validate="many_to_one",
    )

    if len(training) != 375:
        raise RuntimeError(
            "A verified forecast has no HKO outcome."
        )

    training[
        "residual_c"
    ] = (
        training[
            "hko_daily_max_c"
        ]
        - training[
            "forecast_daily_max_c"
        ]
    )

    certified_dates = (
        load_certified_dates()
    )

    training[
        "has_certified_market"
    ] = training[
        "target_date"
    ].isin(
        certified_dates
    )

    evaluation = training.loc[
        training[
            "has_certified_market"
        ]
    ].copy()

    if len(evaluation) != 375:
        raise RuntimeError(
            "A retained weather row lacks a certified market date."
        )

    (
        chronological,
        block_summary,
        fold_summary,
    ) = assign_chronology(
        training
    )

    evaluation = evaluation.merge(
        chronological[
            [
                "target_date",
                "decision_rule",
                "chronology_block",
                "development_fold",
                "outcome_may_influence_model_choice",
                "used_in_final_fit_before_holdout",
                "used_to_refit_before_external_test",
            ]
        ],
        on=[
            "target_date",
            "decision_rule",
        ],
        how="left",
        validate="one_to_one",
    )

    universe = (
        pd.MultiIndex.from_product(
            [
                certified_dates,
                VALID_RULES,
            ],
            names=[
                "target_date",
                "decision_rule",
            ],
        )
        .to_frame(
            index=False
        )
    )

    present = selected[
        [
            "target_date",
            "decision_rule",
            "source_period",
            "forecast_value_source",
        ]
    ].copy()

    present[
        "forecast_present"
    ] = True

    support = universe.merge(
        present,
        on=[
            "target_date",
            "decision_rule",
        ],
        how="left",
        validate="one_to_one",
    )

    support[
        "forecast_present"
    ] = support[
        "forecast_present"
    ].fillna(False)

    support[
        "support_status"
    ] = np.where(
        support[
            "forecast_present"
        ],
        "VERIFIED_FORECAST_AVAILABLE",
        np.where(
            support[
                "target_date"
            ].lt(
                "2026-06-01"
            ),
            "NO_INDEPENDENTLY_VERIFIED_HISTORICAL_PATH",
            "NO_ADMISSIBLE_JUNE_PATH",
        ),
    )

    missing_rows = int(
        (
            ~support[
                "forecast_present"
            ]
        ).sum()
    )

    if missing_rows != 37:
        raise RuntimeError(
            f"Expected 37 unsupported date-rule keys; found {missing_rows}."
        )

    unsupported_historical = int(
        (
            support[
                "target_date"
            ].lt(
                "2026-06-01"
            )
            & ~support[
                "forecast_present"
            ]
        ).sum()
    )

    unsupported_june = int(
        (
            support[
                "target_date"
            ].ge(
                "2026-06-01"
            )
            & ~support[
                "forecast_present"
            ]
        ).sum()
    )

    if unsupported_historical != 36:
        raise RuntimeError(
            "Expected 36 unsupported historical request rows."
        )

    if unsupported_june != 1:
        raise RuntimeError(
            "Expected one unsupported June date-rule row."
        )

    integrity = pd.DataFrame(
        [
            {
                "check": "selected_rows_equal_375",
                "passed": len(selected) == 375,
                "value": len(selected),
            },
            {
                "check": "selected_dates_equal_102",
                "passed": (
                    selected[
                        "target_date"
                    ].nunique()
                    == 102
                ),
                "value": (
                    selected[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "historical_rows_equal_256",
                "passed": len(historical) == 256,
                "value": len(historical),
            },
            {
                "check": "june_rows_equal_119",
                "passed": len(june) == 119,
                "value": len(june),
            },
            {
                "check": "daily_hourly_reconciliation_exact",
                "passed": (
                    reconciliation[
                        "absolute_difference_c"
                    ].le(1e-9).all()
                ),
                "value": float(
                    reconciliation[
                        "absolute_difference_c"
                    ].max()
                ),
            },
            {
                "check": "all_paths_have_24_local_hours",
                "passed": (
                    selected[
                        "unique_local_hours"
                    ].eq(24).all()
                ),
                "value": True,
            },
            {
                "check": "all_forecasts_available_by_decision",
                "passed": (
                    (
                        selected[
                            "forecast_issue_time_utc"
                        ]
                        <= selected[
                            "decision_time_utc"
                        ]
                    ).all()
                ),
                "value": True,
            },
            {
                "check": "unsupported_historical_rows_equal_36",
                "passed": (
                    unsupported_historical
                    == 36
                ),
                "value": unsupported_historical,
            },
            {
                "check": "unsupported_june_rows_equal_1",
                "passed": (
                    unsupported_june
                    == 1
                ),
                "value": unsupported_june,
            },
        ]
    )

    if not integrity[
        "passed"
    ].all():
        raise RuntimeError(
            "One or more final integrity checks failed."
        )

    for path in (
        SELECTED_PATH,
        TRAINING_PATH,
        EVALUATION_PATH,
        CHRONOLOGY_PANEL_PATH,
        HISTORICAL_PANEL_PATH,
        RECONCILIATION_PATH,
        SUPPORT_MATRIX_PATH,
        SUPPORT_SUMMARY_PATH,
        PANEL_SUMMARY_PATH,
        BLOCK_SUMMARY_PATH,
        FOLD_SUMMARY_PATH,
        INTEGRITY_PATH,
        FORENSIC_DECISION_PATH,
        PANEL_MANIFEST_PATH,
        CHRONOLOGY_MANIFEST_PATH,
        CHRONOLOGY_POLICY_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    serialised_selected = (
        selected.copy()
    )

    for column in (
        "forecast_issue_time_utc",
        "decision_time_utc",
    ):
        serialised_selected[
            column
        ] = serialised_selected[
            column
        ].dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    serialised_training = (
        chronological.copy()
    )

    for column in (
        "forecast_issue_time_utc",
        "decision_time_utc",
    ):
        serialised_training[
            column
        ] = serialised_training[
            column
        ].dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    serialised_evaluation = (
        evaluation.copy()
    )

    for column in (
        "forecast_issue_time_utc",
        "decision_time_utc",
    ):
        serialised_evaluation[
            column
        ] = serialised_evaluation[
            column
        ].dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    serialised_selected.to_csv(
        SELECTED_PATH,
        index=False,
    )

    serialised_training.to_csv(
        TRAINING_PATH,
        index=False,
    )

    serialised_evaluation.to_csv(
        EVALUATION_PATH,
        index=False,
    )

    serialised_training.to_csv(
        CHRONOLOGY_PANEL_PATH,
        index=False,
    )

    historical.to_csv(
        HISTORICAL_PANEL_PATH,
        index=False,
    )

    reconciliation.to_csv(
        RECONCILIATION_PATH,
        index=False,
    )

    support.to_csv(
        SUPPORT_MATRIX_PATH,
        index=False,
    )

    block_summary.to_csv(
        BLOCK_SUMMARY_PATH,
        index=False,
    )

    fold_summary.to_csv(
        FOLD_SUMMARY_PATH,
        index=False,
    )

    integrity.to_csv(
        INTEGRITY_PATH,
        index=False,
    )

    FORENSIC_DECISION_PATH.write_text(
        json.dumps(
            forensic_decision,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    block_records = (
        block_summary.to_dict(
            orient="records"
        )
    )

    fold_records = (
        fold_summary.to_dict(
            orient="records"
        )
    )

    summary = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "NOTEBOOK02_VERIFIED_PANEL_READY"
        ),
        "selected_forecast_rows": 375,
        "weather_training_rows": 375,
        "weather_training_dates": 102,
        "weather_training_start": (
            serialised_training[
                "target_date"
            ].min()
        ),
        "weather_training_end": (
            serialised_training[
                "target_date"
            ].max()
        ),
        "market_evaluation_rows": 375,
        "market_evaluation_dates_with_forecasts": 102,
        "certified_market_dates_available": 103,
        "historical_verified_rows": 256,
        "historical_verified_dates": 72,
        "historical_unverified_request_rows_excluded": 36,
        "june_verified_rows": 119,
        "june_dates": 30,
        "unsupported_date_rule_rows": 37,
        "unsupported_historical_date_rule_rows": 36,
        "unsupported_june_date_rule_rows": 1,
        "all_paths_have_24_local_hours": True,
        "all_issue_times_not_later_than_decision_times": True,
        "daily_hourly_reconciliation_max_difference_c": 0.0,
        "chronology_status": (
            "CHRONOLOGY_ASSIGNED"
        ),
        "model_fitting_permitted": True,
        "random_split_permitted": False,
        "development_fold_count": 4,
        "chronology_blocks": block_records,
    }

    SUPPORT_SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    PANEL_SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    chronology_policy = {
        "status": "CHRONOLOGY_ASSIGNED",
        "model_fitting_permitted": True,
        "uncertainty_unit": "settlement_date",
        "random_split_permitted": False,
        "available_settlement_dates": 102,
        "certified_market_dates": 103,
        "blocks": block_records,
        "development_folds": fold_records,
        "selection_protocol": {
            "primary_continuous_distribution_score": (
                "date-grouped expanding out-of-fold CRPS"
            ),
            "warmup_outcomes_may_influence_selection": True,
            "development_outcomes_may_influence_selection": True,
            "holdout_outcomes_may_influence_selection": False,
            "external_outcomes_may_influence_selection": False,
            "final_fit_before_holdout": (
                "all available warmup and development dates"
            ),
            "refit_after_holdout_before_external_test": False,
            "external_model_identical_to_holdout_model": True,
        },
        "future_extension": {
            "july_august_may_be_appended": True,
            "role": "additional external temporal extension",
            "may_retroactively_change_model_selection": False,
        },
    }

    CHRONOLOGY_POLICY_PATH.write_text(
        yaml.safe_dump(
            chronology_policy,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    panel_manifest = {
        **summary,
        "forensic_decision": forensic_decision,
        "inputs": {
            str(
                HKO_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                HKO_PATH
            ),
            str(
                CONTRACT_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CONTRACT_PATH
            ),
            str(
                JUNE_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                JUNE_PATH
            ),
        },
        "outputs": {
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
        },
    }

    PANEL_MANIFEST_PATH.write_text(
        json.dumps(
            panel_manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    chronology_manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "CHRONOLOGY_ASSIGNED",
        "model_fitting_permitted": True,
        "available_dates": 102,
        "block_summary": block_records,
        "development_folds": fold_records,
        "selection_criterion": (
            "date-grouped expanding out-of-fold CRPS"
        ),
        "holdout_locked": True,
        "external_test_locked": True,
        "refit_before_external_test": False,
        "integrity_checks_passed": bool(
            integrity[
                "passed"
            ].all()
        ),
    }

    CHRONOLOGY_MANIFEST_PATH.write_text(
        json.dumps(
            chronology_manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print(" VERIFIED NOTEBOOK 02 PANEL READY")
    print("=" * 72)
    print()
    print("Selected rows:", len(selected))
    print(
        "Selected dates:",
        selected[
            "target_date"
        ].nunique(),
    )
    print("Historical verified rows:", len(historical))
    print(
        "Historical verified dates:",
        historical[
            "target_date"
        ].nunique(),
    )
    print("June verified rows:", len(june))
    print(
        "Unsupported historical requests excluded:",
        unsupported_historical,
    )
    print(
        "Unsupported June keys:",
        unsupported_june,
    )
    print(
        "Daily-hourly maximum discrepancy:",
        float(
            reconciliation[
                "absolute_difference_c"
            ].max()
        ),
    )
    print()
    print("Chronological blocks:")
    print(
        block_summary.to_string(
            index=False
        )
    )
    print()
    print("Development folds:")
    print(
        fold_summary.to_string(
            index=False
        )
    )
    print()
    print("Model fitting permitted:", True)


if __name__ == "__main__":
    main()
