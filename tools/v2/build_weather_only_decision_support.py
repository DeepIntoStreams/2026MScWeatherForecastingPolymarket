from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

TARGET_MAP_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_training_target_support_map.csv"
)

RUN_INVENTORY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03b_two_year_complete_run_inventory.csv"
)

VERSION1_DESIGN_PATH = (
    ROOT
    / "data/processed/"
    "02_chronological_design_panel.csv"
)

SPEC_PATH = (
    ROOT
    / "config/v2/"
    "weather_only_decision_support_spec.json"
)

RULE_CLOCK_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_decision_rule_clock_audit.csv"
)

RUN_DAY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_historical_run_local_day_panel.csv.gz"
)

ELIGIBLE_CANDIDATE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_eligible_run_candidates.csv.gz"
)

SUPPORT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_decision_support_panel.csv"
)

MISSING_SUPPORT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_missing_support.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_support_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_support_integrity_checks.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "04_weather_only_decision_support_manifest.json"
)


DECISION_RULE_ORDER = [
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
]

EXPECTED_TARGET_DATES = 730
EXPECTED_DECISION_RULES = 4
EXPECTED_SKELETON_ROWS = (
    EXPECTED_TARGET_DATES
    * EXPECTED_DECISION_RULES
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def atomic_write_bytes(
    path: Path,
    content: bytes,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_bytes(content)
    os.replace(temporary, path)


def write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    atomic_write_bytes(
        path,
        (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
    )


def write_csv(
    panel: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    panel.to_csv(
        temporary,
        index=False,
    )

    os.replace(
        temporary,
        path,
    )


def write_gzip_csv(
    panel: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    panel.to_csv(
        temporary,
        index=False,
        compression={
            "method": "gzip",
            "compresslevel": 9,
            "mtime": 0,
        },
    )

    os.replace(
        temporary,
        path,
    )


def normalise_open_meteo_times(
    values: list[object],
) -> pd.DatetimeIndex:
    """Return all Open-Meteo times in Asia/Hong_Kong time.

    Historical cache files legitimately contain both timezone-free
    local timestamps and timezone-aware timestamps. Timezone-free
    values are interpreted as Hong Kong local time. Timezone-aware
    values are converted to Hong Kong local time.
    """
    normalised: list[pd.Timestamp] = []

    for position, value in enumerate(values):
        try:
            timestamp = pd.Timestamp(value)
        except Exception as exc:
            raise ValueError(
                "Unable to parse Open-Meteo timestamp "
                f"at position {position}: {value!r}"
            ) from exc

        if pd.isna(timestamp):
            raise ValueError(
                "Open-Meteo timestamp is missing "
                f"at position {position}."
            )

        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(
                "Asia/Hong_Kong"
            )
        else:
            timestamp = timestamp.tz_convert(
                "Asia/Hong_Kong"
            )

        normalised.append(timestamp)

    result = pd.DatetimeIndex(normalised)

    if result.hasnans:
        raise ValueError(
            "Normalised Open-Meteo times contain NaT."
        )

    if str(result.tz) != "Asia/Hong_Kong":
        raise ValueError(
            "Normalised timestamps do not use "
            "Asia/Hong_Kong time."
        )

    return result


def detect_column(
    panel: pd.DataFrame,
    candidates: list[str],
    description: str,
) -> str:
    available = [
        column
        for column in candidates
        if column in panel.columns
    ]

    if len(available) == 1:
        return available[0]

    if len(available) > 1:
        for preferred in candidates:
            if preferred in available:
                return preferred

    raise RuntimeError(
        f"Unable to identify {description}. "
        f"Available columns: {list(panel.columns)}"
    )


def load_target_dates() -> pd.DataFrame:
    source = pd.read_csv(
        TARGET_MAP_PATH
    )

    date_column = detect_column(
        source,
        [
            "target_date",
            "forecast_target_date",
            "event_date",
            "date",
        ],
        "the weather-only target-date column",
    )

    dates = pd.DataFrame(
        {
            "target_date": pd.to_datetime(
                source[date_column],
                errors="raise", format="mixed",
            )
            .dt.normalize()
            .drop_duplicates()
            .sort_values()
        }
    ).reset_index(drop=True)

    if len(dates) != EXPECTED_TARGET_DATES:
        raise RuntimeError(
            "Expected exactly "
            f"{EXPECTED_TARGET_DATES} target dates, "
            f"found {len(dates)}."
        )

    expected_sequence = pd.date_range(
        dates["target_date"].min(),
        dates["target_date"].max(),
        freq="D",
    )

    if len(expected_sequence) != EXPECTED_TARGET_DATES:
        raise RuntimeError(
            "The target-date interval is not a "
            "continuous 730-day period."
        )

    if not dates["target_date"].reset_index(
        drop=True
    ).equals(
        pd.Series(
            expected_sequence,
            name="target_date",
        )
    ):
        raise RuntimeError(
            "The target dates contain a gap or duplicate."
        )

    return dates


def infer_decision_rule_clocks() -> pd.DataFrame:
    panel = pd.read_csv(
        VERSION1_DESIGN_PATH
    )

    required_columns = {
        "target_date",
        "decision_rule",
        "decision_time_utc",
    }

    missing = sorted(
        required_columns
        - set(panel.columns)
    )

    if missing:
        raise RuntimeError(
            "Version 1 design panel is missing: "
            + ", ".join(missing)
        )

    panel = panel.loc[
        panel["decision_rule"].isin(
            DECISION_RULE_ORDER
        )
    ].copy()

    panel["target_date"] = pd.to_datetime(
        panel["target_date"],
        errors="raise", format="mixed",
    ).dt.normalize()

    panel["decision_time_utc"] = pd.to_datetime(
        panel["decision_time_utc"],
        errors="raise", format="mixed",
        utc=True,
    )

    panel["decision_time_hkt"] = (
        panel["decision_time_utc"]
        .dt.tz_convert("Asia/Hong_Kong")
    )

    target_midnight_hkt = (
        panel["target_date"]
        .dt.tz_localize(
            "Asia/Hong_Kong"
        )
    )

    panel["decision_offset_hours"] = (
        (
            panel["decision_time_hkt"]
            - target_midnight_hkt
        )
        .dt.total_seconds()
        .div(3600.0)
        .round(6)
    )

    records = []

    for rule in DECISION_RULE_ORDER:
        group = panel.loc[
            panel["decision_rule"].eq(rule)
        ].copy()

        if group.empty:
            raise RuntimeError(
                f"No Version 1 observations exist for {rule}."
            )

        counts = (
            group["decision_offset_hours"]
            .value_counts()
            .sort_values(
                ascending=False
            )
        )

        selected_offset = float(
            counts.index[0]
        )

        selected_count = int(
            counts.iloc[0]
        )

        share = (
            selected_count
            / len(group)
        )

        if share < 0.95:
            raise RuntimeError(
                f"The inferred decision time for {rule} "
                "is not sufficiently stable. "
                f"Modal share: {share:.3f}"
            )

        local_example = (
            pd.Timestamp("2026-01-01")
            .tz_localize(
                "Asia/Hong_Kong"
            )
            + pd.Timedelta(
                hours=selected_offset
            )
        )

        records.append(
            {
                "decision_rule": rule,
                "decision_rule_order": (
                    DECISION_RULE_ORDER.index(rule)
                ),
                "decision_offset_hours": (
                    selected_offset
                ),
                "source_rows": len(group),
                "modal_rows": selected_count,
                "modal_share": share,
                "example_local_decision_time": (
                    local_example.isoformat()
                ),
                "source": str(
                    VERSION1_DESIGN_PATH.relative_to(
                        ROOT
                    )
                ),
            }
        )

    audit = pd.DataFrame(records)

    if audit["decision_rule"].nunique() != 4:
        raise RuntimeError(
            "Exactly four decision-rule clocks "
            "were not recovered."
        )

    return audit


def read_run_local_days(
    inventory: pd.DataFrame,
    target_dates: set[str],
) -> pd.DataFrame:
    required_columns = {
        "request_id",
        "run_init_utc",
        "cycle_utc",
        "cache_path",
        "inventory_source",
    }

    missing = sorted(
        required_columns
        - set(inventory.columns)
    )

    if missing:
        raise RuntimeError(
            "Run inventory is missing columns: "
            + ", ".join(missing)
        )

    if len(inventory) != 1391:
        raise RuntimeError(
            "Expected 1,391 successful runs, "
            f"found {len(inventory)}."
        )

    if not inventory[
        "request_id"
    ].astype(str).is_unique:
        raise RuntimeError(
            "The successful-run inventory "
            "contains duplicate request IDs."
        )

    frames = []
    missing_cache = []
    invalid_cache = []

    for row in inventory.itertuples(
        index=False
    ):
        cache_path = (
            ROOT
            / str(row.cache_path)
        )

        if not cache_path.exists():
            missing_cache.append(
                str(cache_path)
            )
            continue

        try:
            compressed = (
                cache_path.read_bytes()
            )

            body = gzip.decompress(
                compressed
            )

            payload = json.loads(
                body.decode("utf-8")
            )

            if payload.get("timezone") != (
                "Asia/Hong_Kong"
            ):
                raise ValueError(
                    "Unexpected timezone: "
                    f"{payload.get('timezone')!r}"
                )

            hourly = payload.get("hourly")

            if not isinstance(
                hourly,
                dict,
            ):
                raise ValueError(
                    "Missing hourly object."
                )

            times = hourly.get("time")
            temperatures = (
                hourly.get(
                    "temperature_2m"
                )
            )

            if not isinstance(
                times,
                list,
            ):
                raise ValueError(
                    "Missing hourly times."
                )

            if not isinstance(
                temperatures,
                list,
            ):
                raise ValueError(
                    "Missing hourly temperatures."
                )

            if len(times) != len(
                temperatures
            ):
                raise ValueError(
                    "Hourly arrays have "
                    "different lengths."
                )

            hourly_panel = pd.DataFrame(
                {
                    "valid_time_hkt": (
                        normalise_open_meteo_times(
                            times
                        )
                    ),
                    "temperature_2m_c": (
                        pd.to_numeric(
                            temperatures,
                            errors="coerce",
                        )
                    ),
                }
            )

            hourly_panel[
                "target_date"
            ] = (
                hourly_panel[
                    "valid_time_hkt"
                ]
                .dt.date
                .astype(str)
            )

            hourly_panel[
                "local_hour"
            ] = (
                hourly_panel[
                    "valid_time_hkt"
                ].dt.hour
            )

            hourly_panel = (
                hourly_panel.loc[
                    hourly_panel[
                        "target_date"
                    ].isin(
                        target_dates
                    )
                ]
                .copy()
            )

            if hourly_panel.empty:
                continue

            daily = (
                hourly_panel.groupby(
                    "target_date",
                    as_index=False,
                )
                .agg(
                    hourly_rows=(
                        "valid_time_hkt",
                        "size",
                    ),
                    unique_local_hours=(
                        "local_hour",
                        "nunique",
                    ),
                    nonmissing_temperature_rows=(
                        "temperature_2m_c",
                        "count",
                    ),
                    forecast_daily_max_c=(
                        "temperature_2m_c",
                        "max",
                    ),
                    forecast_daily_min_c=(
                        "temperature_2m_c",
                        "min",
                    ),
                    forecast_daily_mean_c=(
                        "temperature_2m_c",
                        "mean",
                    ),
                )
            )

            daily[
                "complete_local_day"
            ] = (
                daily["hourly_rows"].eq(24)
                & daily[
                    "unique_local_hours"
                ].eq(24)
                & daily[
                    "nonmissing_temperature_rows"
                ].eq(24)
            )

            daily = daily.loc[
                daily[
                    "complete_local_day"
                ]
            ].copy()

            if daily.empty:
                continue

            daily.insert(
                0,
                "request_id",
                str(row.request_id),
            )

            daily.insert(
                1,
                "run_init_utc",
                str(row.run_init_utc),
            )

            daily.insert(
                2,
                "cycle_utc",
                int(row.cycle_utc),
            )

            daily.insert(
                3,
                "inventory_source",
                str(row.inventory_source),
            )

            daily["cache_path"] = str(
                row.cache_path
            )

            frames.append(daily)

        except Exception as exc:
            invalid_cache.append(
                {
                    "request_id": str(
                        row.request_id
                    ),
                    "cache_path": str(
                        row.cache_path
                    ),
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

    if missing_cache:
        raise RuntimeError(
            "Successful inventory entries have "
            "missing cache files:\n"
            + "\n".join(
                missing_cache[:20]
            )
        )

    if invalid_cache:
        preview = pd.DataFrame(
            invalid_cache
        ).head(20)

        raise RuntimeError(
            "Successful inventory cache validation "
            "failed:\n"
            + preview.to_string(
                index=False
            )
        )

    if not frames:
        raise RuntimeError(
            "No complete historical local-day "
            "forecasts were reconstructed."
        )

    result = pd.concat(
        frames,
        ignore_index=True,
    )

    result["target_date"] = (
        pd.to_datetime(
            result["target_date"],
            errors="raise", format="mixed",
        ).dt.normalize()
    )

    result["run_init_utc"] = (
        pd.to_datetime(
            result["run_init_utc"],
            errors="raise", format="mixed",
            utc=True,
        )
    )

    result = (
        result.sort_values(
            [
                "target_date",
                "run_init_utc",
                "request_id",
            ],
            kind="stable",
        )
        .drop_duplicates(
            [
                "request_id",
                "target_date",
            ],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return result


def construct_support(
    target_dates: pd.DataFrame,
    rule_clocks: pd.DataFrame,
    run_days: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    skeleton = (
        target_dates.assign(
            join_key=1
        )
        .merge(
            rule_clocks[
                [
                    "decision_rule",
                    "decision_rule_order",
                    "decision_offset_hours",
                ]
            ].assign(
                join_key=1
            ),
            on="join_key",
            how="inner",
            validate="many_to_many",
        )
        .drop(
            columns="join_key"
        )
    )

    if len(skeleton) != (
        EXPECTED_SKELETON_ROWS
    ):
        raise RuntimeError(
            "The target-date and decision-rule "
            "skeleton has the wrong size."
        )

    skeleton[
        "target_midnight_hkt"
    ] = (
        skeleton[
            "target_date"
        ]
        .dt.tz_localize(
            "Asia/Hong_Kong"
        )
    )

    skeleton[
        "decision_time_hkt"
    ] = (
        skeleton[
            "target_midnight_hkt"
        ]
        + pd.to_timedelta(
            skeleton[
                "decision_offset_hours"
            ],
            unit="h",
        )
    )

    skeleton[
        "decision_time_utc"
    ] = (
        skeleton[
            "decision_time_hkt"
        ]
        .dt.tz_convert("UTC")
    )

    candidates = skeleton.merge(
        run_days,
        on="target_date",
        how="left",
        validate="many_to_many",
    )

    candidates[
        "issued_before_decision"
    ] = (
        candidates[
            "run_init_utc"
        ].notna()
        & (
            candidates[
                "run_init_utc"
            ]
            <= candidates[
                "decision_time_utc"
            ]
        )
    )

    eligible = candidates.loc[
        candidates[
            "issued_before_decision"
        ]
    ].copy()

    eligible[
        "run_age_hours_at_decision"
    ] = (
        (
            eligible[
                "decision_time_utc"
            ]
            - eligible[
                "run_init_utc"
            ]
        )
        .dt.total_seconds()
        .div(3600.0)
    )

    if (
        eligible[
            "run_age_hours_at_decision"
        ]
        .lt(-1e-9)
        .any()
    ):
        raise RuntimeError(
            "A candidate run was issued after "
            "its decision time."
        )

    eligible = eligible.sort_values(
        [
            "target_date",
            "decision_rule_order",
            "run_init_utc",
            "cycle_utc",
        ],
        ascending=[
            True,
            True,
            False,
            False,
        ],
        kind="stable",
    )

    selected = (
        eligible.drop_duplicates(
            [
                "target_date",
                "decision_rule",
            ],
            keep="first",
        )
        .copy()
    )

    selected[
        "support_available"
    ] = True

    selected[
        "selection_rule"
    ] = (
        "latest available complete-day forecast "
        "issued no later than the decision time"
    )

    selected[
        "market_price_accessed"
    ] = False

    selected[
        "outcome_accessed"
    ] = False

    selected[
        "model_fitted"
    ] = False

    selected[
        "model_selected"
    ] = False

    selected[
        "used_for_weather_only_training"
    ] = True

    supported_keys = selected[
        [
            "target_date",
            "decision_rule",
        ]
    ].copy()

    missing = skeleton.merge(
        supported_keys.assign(
            support_available=True
        ),
        on=[
            "target_date",
            "decision_rule",
        ],
        how="left",
        validate="one_to_one",
    )

    missing = missing.loc[
        missing[
            "support_available"
        ].isna()
    ].copy()

    missing[
        "support_available"
    ] = False

    missing[
        "missing_reason"
    ] = (
        "no complete local-day forecast was "
        "issued before the decision time"
    )

    return selected, missing, eligible


def main() -> None:
    target_dates = load_target_dates()
    rule_clocks = infer_decision_rule_clocks()

    inventory = pd.read_csv(
        RUN_INVENTORY_PATH
    )

    target_date_strings = set(
        target_dates[
            "target_date"
        ].dt.date.astype(str)
    )

    run_days = read_run_local_days(
        inventory,
        target_date_strings,
    )

    selected, missing, eligible = (
        construct_support(
            target_dates,
            rule_clocks,
            run_days,
        )
    )

    selected = selected.sort_values(
        [
            "target_date",
            "decision_rule_order",
        ],
        kind="stable",
    ).reset_index(drop=True)

    missing = missing.sort_values(
        [
            "target_date",
            "decision_rule_order",
        ],
        kind="stable",
    ).reset_index(drop=True)

    summary = (
        selected.groupby(
            [
                "decision_rule",
                "decision_rule_order",
            ],
            as_index=False,
        )
        .agg(
            supported_rows=(
                "target_date",
                "size",
            ),
            supported_dates=(
                "target_date",
                "nunique",
            ),
            minimum_target_date=(
                "target_date",
                "min",
            ),
            maximum_target_date=(
                "target_date",
                "max",
            ),
            mean_run_age_hours=(
                "run_age_hours_at_decision",
                "mean",
            ),
            median_run_age_hours=(
                "run_age_hours_at_decision",
                "median",
            ),
            maximum_run_age_hours=(
                "run_age_hours_at_decision",
                "max",
            ),
            distinct_selected_runs=(
                "request_id",
                "nunique",
            ),
        )
        .sort_values(
            "decision_rule_order"
        )
    )

    summary[
        "expected_dates"
    ] = EXPECTED_TARGET_DATES

    summary[
        "missing_dates"
    ] = (
        summary["expected_dates"]
        - summary["supported_dates"]
    )

    summary[
        "support_share"
    ] = (
        summary["supported_dates"]
        / summary["expected_dates"]
    )

    summary[
        "minimum_target_date"
    ] = (
        pd.to_datetime(
            summary[
                "minimum_target_date"
            ]
        )
        .dt.date
        .astype(str)
    )

    summary[
        "maximum_target_date"
    ] = (
        pd.to_datetime(
            summary[
                "maximum_target_date"
            ]
        )
        .dt.date
        .astype(str)
    )

    selected_key_unique = (
        not selected.duplicated(
            [
                "target_date",
                "decision_rule",
            ]
        ).any()
    )

    all_before_decision = (
        (
            selected[
                "run_init_utc"
            ]
            <= selected[
                "decision_time_utc"
            ]
        ).all()
    )

    selected_complete_days = (
        selected[
            "complete_local_day"
        ].astype(bool).all()
    )

    supported_plus_missing = (
        len(selected)
        + len(missing)
    )

    checks = pd.DataFrame(
        [
            {
                "check": "target_date_count",
                "required": True,
                "passed": (
                    len(target_dates)
                    == EXPECTED_TARGET_DATES
                ),
                "detail": len(target_dates),
            },
            {
                "check": "decision_rule_count",
                "required": True,
                "passed": (
                    rule_clocks[
                        "decision_rule"
                    ].nunique()
                    == EXPECTED_DECISION_RULES
                ),
                "detail": (
                    rule_clocks[
                        "decision_rule"
                    ].nunique()
                ),
            },
            {
                "check": "skeleton_row_count",
                "required": True,
                "passed": (
                    supported_plus_missing
                    == EXPECTED_SKELETON_ROWS
                ),
                "detail": supported_plus_missing,
            },
            {
                "check": "selected_keys_unique",
                "required": True,
                "passed": selected_key_unique,
                "detail": len(selected),
            },
            {
                "check": "all_selected_runs_before_decision",
                "required": True,
                "passed": all_before_decision,
                "detail": bool(
                    all_before_decision
                ),
            },
            {
                "check": "all_selected_runs_complete_local_day",
                "required": True,
                "passed": selected_complete_days,
                "detail": bool(
                    selected_complete_days
                ),
            },
            {
                "check": "run_inventory_count",
                "required": True,
                "passed": (
                    len(inventory) == 1391
                ),
                "detail": len(inventory),
            },
            {
                "check": "market_prices_not_accessed",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "outcomes_not_accessed",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "model_not_fitted",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "model_not_selected",
                "required": True,
                "passed": True,
                "detail": False,
            },
        ]
    )

    required_failed = checks.loc[
        checks["required"]
        & ~checks["passed"]
    ]

    if not required_failed.empty:
        raise RuntimeError(
            "Required weather-only support checks "
            "failed:\n"
            + required_failed.to_string(
                index=False
            )
        )

    SPEC_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    specification = {
        "phase": 4,
        "subphase": "4E",
        "status": (
            "WEATHER_ONLY_DECISION_SUPPORT_DECLARED"
        ),
        "timezone": "Asia/Hong_Kong",
        "weather_only_target_dates": (
            EXPECTED_TARGET_DATES
        ),
        "decision_rules": (
            DECISION_RULE_ORDER
        ),
        "decision_rule_selection": (
            "latest available complete-day forecast "
            "issued no later than the decision time"
        ),
        "decision_time_source": str(
            VERSION1_DESIGN_PATH.relative_to(
                ROOT
            )
        ),
        "run_inventory_source": str(
            RUN_INVENTORY_PATH.relative_to(
                ROOT
            )
        ),
        "target_date_source": str(
            TARGET_MAP_PATH.relative_to(
                ROOT
            )
        ),
        "market_prices_accessed": False,
        "realised_outcomes_accessed": False,
        "model_fitted": False,
        "model_selected": False,
        "calibration_selected": False,
        "trading_returns_calculated": False,
    }

    write_json(
        SPEC_PATH,
        specification,
    )

    write_csv(
        rule_clocks,
        RULE_CLOCK_PATH,
    )

    write_gzip_csv(
        run_days,
        RUN_DAY_PATH,
    )

    write_gzip_csv(
        eligible,
        ELIGIBLE_CANDIDATE_PATH,
    )

    write_csv(
        selected,
        SUPPORT_PATH,
    )

    write_csv(
        missing,
        MISSING_SUPPORT_PATH,
    )

    write_csv(
        summary,
        SUMMARY_PATH,
    )

    write_csv(
        checks,
        CHECKS_PATH,
    )

    output_paths = [
        SPEC_PATH,
        RULE_CLOCK_PATH,
        RUN_DAY_PATH,
        ELIGIBLE_CANDIDATE_PATH,
        SUPPORT_PATH,
        MISSING_SUPPORT_PATH,
        SUMMARY_PATH,
        CHECKS_PATH,
    ]

    manifest = {
        "phase": 4,
        "subphase": "4E",
        "phase_status": (
            "PHASE4_WEATHER_ONLY_SUPPORT_COMPLETE"
        ),
        "status": (
            "WEATHER_ONLY_DECISION_SUPPORT_CONSTRUCTED"
        ),
        "created_utc": utc_now(),
        "weather_only_target_dates": (
            EXPECTED_TARGET_DATES
        ),
        "decision_rules": (
            EXPECTED_DECISION_RULES
        ),
        "expected_target_rule_rows": (
            EXPECTED_SKELETON_ROWS
        ),
        "successful_run_inventory_rows": (
            len(inventory)
        ),
        "complete_run_local_day_rows": (
            len(run_days)
        ),
        "eligible_run_candidate_rows": (
            len(eligible)
        ),
        "supported_target_rule_rows": (
            len(selected)
        ),
        "missing_target_rule_rows": (
            len(missing)
        ),
        "supported_target_rule_share": (
            len(selected)
            / EXPECTED_SKELETON_ROWS
        ),
        "supported_dates_any_rule": int(
            selected[
                "target_date"
            ].nunique()
        ),
        "selected_runs": int(
            selected[
                "request_id"
            ].nunique()
        ),
        "decision_rule_offsets_hours": {
            str(row.decision_rule): float(
                row.decision_offset_hours
            )
            for row in (
                rule_clocks.itertuples(
                    index=False
                )
            )
        },
        "information_time_verified": True,
        "market_prices_accessed": False,
        "realised_outcomes_accessed": False,
        "model_fitted": False,
        "model_selected": False,
        "continuous_calibration_selected": False,
        "probability_calibration_selected": False,
        "categorical_scores_calculated": False,
        "trading_strategy_selected": False,
        "trading_returns_calculated": False,
        "output_paths": [
            str(path.relative_to(ROOT))
            for path in output_paths
        ],
        "output_hashes": {
            str(path.relative_to(ROOT)): (
                sha256_file(path)
            )
            for path in output_paths
        },
        "next_stage": (
            "Retrieve and certify HKO daily maximum "
            "temperatures for the weather-only period, "
            "then construct forecast residuals."
        ),
    }

    write_json(
        MANIFEST_PATH,
        manifest,
    )

    print()
    print("=" * 78)
    print("PHASE 4E WEATHER-ONLY SUPPORT COMPLETE")
    print("=" * 78)
    print(
        "Weather-only target dates:",
        EXPECTED_TARGET_DATES,
    )
    print(
        "Decision rules:",
        EXPECTED_DECISION_RULES,
    )
    print(
        "Expected target-rule rows:",
        EXPECTED_SKELETON_ROWS,
    )
    print(
        "Successful historical runs:",
        len(inventory),
    )
    print(
        "Complete run-local-day rows:",
        len(run_days),
    )
    print(
        "Eligible run candidates:",
        len(eligible),
    )
    print(
        "Supported target-rule rows:",
        len(selected),
    )
    print(
        "Missing target-rule rows:",
        len(missing),
    )
    print(
        "Support share:",
        f"{len(selected) / EXPECTED_SKELETON_ROWS:.2%}",
    )
    print()
    print("Decision-rule support:")
    print(
        summary[
            [
                "decision_rule",
                "supported_dates",
                "missing_dates",
                "support_share",
                "median_run_age_hours",
                "distinct_selected_runs",
            ]
        ].to_string(
            index=False
        )
    )
    print()
    print("Information-time checks: PASSED")
    print("Market prices accessed: False")
    print("Outcomes accessed: False")
    print("Model fitted or selected: False")


if __name__ == "__main__":
    main()
