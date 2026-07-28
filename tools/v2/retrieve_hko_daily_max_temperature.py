from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
    "hko_daily_max_temperature_spec.json"
)

SUPPORT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_decision_support_panel.csv"
)

RAW_ROOT = (
    ROOT
    / "data/raw/v2/"
    "hko_daily_max_temperature"
)

SOURCE_INVENTORY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04f_hko_daily_max_source_inventory.csv"
)

TRAINING_PANEL_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04f_hko_daily_max_training_panel.csv"
)

EXCLUDED_ROWS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04f_hko_daily_max_excluded_rows.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04f_hko_daily_max_integrity_checks.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs/v2/final_tables/"
    "04f_hko_daily_max_summary.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "04f_hko_daily_max_manifest.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
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


def write_csv(panel: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(path.name + ".tmp")
    panel.to_csv(temporary, index=False)
    os.replace(temporary, path)


def normalise_field_name(value: object) -> str:
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def extract_field_names(payload: dict[str, Any]) -> list[str]:
    fields = payload.get("fields")

    if not isinstance(fields, list):
        raise RuntimeError(
            "The HKO response does not contain a fields list."
        )

    names = []

    for field in fields:
        if isinstance(field, dict):
            candidate = (
                field.get("name")
                or field.get("field")
                or field.get("title")
                or field.get("description")
            )

            if candidate is None:
                raise RuntimeError(
                    "An HKO field definition has no name."
                )

            names.append(str(candidate))
        else:
            names.append(str(field))

    return names


def locate_field(
    names: list[str],
    accepted: tuple[str, ...],
    description: str,
) -> int:
    normalised = [
        normalise_field_name(name)
        for name in names
    ]

    for accepted_name in accepted:
        target = normalise_field_name(accepted_name)

        if target in normalised:
            return normalised.index(target)

    for position, name in enumerate(normalised):
        if any(
            normalise_field_name(candidate) in name
            for candidate in accepted
        ):
            return position

    raise RuntimeError(
        f"Unable to identify the HKO {description} field. "
        f"Fields: {names}"
    )


def parse_hko_payload(
    payload: dict[str, Any],
    requested_year: int,
) -> pd.DataFrame:
    names = extract_field_names(payload)
    data = payload.get("data")

    if not isinstance(data, list):
        raise RuntimeError(
            "The HKO response does not contain a data list."
        )

    year_index = locate_field(
        names,
        ("Year",),
        "year",
    )

    month_index = locate_field(
        names,
        ("Month",),
        "month",
    )

    day_index = locate_field(
        names,
        ("Day",),
        "day",
    )

    temperature_index = locate_field(
        names,
        (
            "Temperature(C)",
            "Temperature",
            "Max Temperature",
            "Maximum Temperature",
            "Value",
            "數值",
            "數值 /Value",
        ),
        "temperature",
    )

    records = []

    for row_number, row in enumerate(data, start=1):
        if not isinstance(row, list):
            raise RuntimeError(
                "An HKO data row is not a list: "
                f"row {row_number}"
            )

        required_position = max(
            year_index,
            month_index,
            day_index,
            temperature_index,
        )

        if len(row) <= required_position:
            raise RuntimeError(
                "An HKO data row is shorter than its field list: "
                f"row {row_number}"
            )

        records.append(
            {
                "year": row[year_index],
                "month": row[month_index],
                "day": row[day_index],
                "hko_daily_max_c_raw": row[
                    temperature_index
                ],
            }
        )

    panel = pd.DataFrame(records)

    if panel.empty:
        raise RuntimeError(
            f"The HKO response for {requested_year} is empty."
        )

    panel["year"] = pd.to_numeric(
        panel["year"],
        errors="coerce",
    )

    panel["month"] = pd.to_numeric(
        panel["month"],
        errors="coerce",
    )

    panel["day"] = pd.to_numeric(
        panel["day"],
        errors="coerce",
    )

    panel["hko_daily_max_c"] = pd.to_numeric(
        panel["hko_daily_max_c_raw"]
        .astype(str)
        .str.strip()
        .replace(
            {
                "": None,
                "***": None,
                "---": None,
                "#": None,
                "N/A": None,
                "NA": None,
                "nan": None,
                "None": None,
            }
        ),
        errors="coerce",
    )

    invalid_calendar_rows = panel.loc[
        panel[["year", "month", "day"]]
        .isna()
        .any(axis=1)
    ]

    if not invalid_calendar_rows.empty:
        raise RuntimeError(
            "The HKO response contains invalid calendar fields:\n"
            + invalid_calendar_rows.head(20).to_string(index=False)
        )

    panel["year"] = panel["year"].astype(int)
    panel["month"] = panel["month"].astype(int)
    panel["day"] = panel["day"].astype(int)

    panel["target_date"] = pd.to_datetime(
        {
            "year": panel["year"],
            "month": panel["month"],
            "day": panel["day"],
        },
        errors="raise",
    ).dt.normalize()

    panel["requested_year"] = requested_year

    if not panel["year"].eq(requested_year).all():
        raise RuntimeError(
            f"The HKO response for {requested_year} "
            "contains rows from another year."
        )

    panel["station"] = "HKO"
    panel["station_name"] = "Hong Kong Observatory"
    panel["data_type"] = "CLMMAXT"
    panel["temperature_unit"] = "degrees Celsius"

    return panel


def validate_payload(
    payload: dict[str, Any],
    requested_year: int,
) -> pd.DataFrame:
    if not isinstance(payload, dict):
        raise RuntimeError(
            "The HKO response is not a JSON object."
        )

    if payload.get("error"):
        raise RuntimeError(
            "HKO API error: "
            + str(
                payload.get("reason")
                or payload.get("message")
                or payload
            )
        )

    return parse_hko_payload(
        payload,
        requested_year,
    )


def fetch_url(
    url: str,
    timeout_seconds: int,
    maximum_attempts: int,
    retry_wait_seconds: int,
) -> bytes:
    last_error: Exception | None = None

    for attempt in range(1, maximum_attempts + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "UCL-MSc-Weather-Polymarket-Research/2.0"
                ),
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                body = response.read()

            if not body:
                raise RuntimeError(
                    "The HKO API returned an empty response."
                )

            json.loads(body.decode("utf-8"))
            return body

        except Exception as exc:
            last_error = exc

            if attempt == maximum_attempts:
                break

            time.sleep(
                retry_wait_seconds * attempt
            )

    raise RuntimeError(
        f"HKO request failed after {maximum_attempts} attempts: "
        f"{last_error}"
    )


def load_cached_year(
    path: Path,
    requested_year: int,
) -> tuple[bytes, pd.DataFrame]:
    compressed = path.read_bytes()
    body = gzip.decompress(compressed)

    payload = json.loads(
        body.decode("utf-8")
    )

    panel = validate_payload(
        payload,
        requested_year,
    )

    return body, panel


def retrieve_year(
    year: int,
    specification: dict[str, Any],
    offline: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    parameters = {
        "dataType": specification["data_type"],
        "rformat": specification["return_format"],
        "station": specification["station"],
        "year": year,
    }

    url = (
        specification["base_url"]
        + "?"
        + urllib.parse.urlencode(parameters)
    )

    cache_path = (
        RAW_ROOT
        / f"hko_clmmaxt_{year}.json.gz"
    )

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_reused = False
    network_retrieved = False

    body: bytes | None = None
    panel: pd.DataFrame | None = None

    if cache_path.exists():
        try:
            body, panel = load_cached_year(
                cache_path,
                year,
            )

            cache_reused = True

        except Exception as exc:
            if offline:
                raise RuntimeError(
                    f"Invalid offline HKO cache for {year}: {exc}"
                ) from exc

            cache_path.unlink(missing_ok=True)

    if body is None or panel is None:
        if offline:
            raise RuntimeError(
                f"Offline HKO cache is missing for {year}: "
                f"{cache_path}"
            )

        body = fetch_url(
            url=url,
            timeout_seconds=int(
                specification[
                    "request_timeout_seconds"
                ]
            ),
            maximum_attempts=int(
                specification[
                    "maximum_attempts"
                ]
            ),
            retry_wait_seconds=int(
                specification[
                    "retry_wait_seconds"
                ]
            ),
        )

        payload = json.loads(
            body.decode("utf-8")
        )

        panel = validate_payload(
            payload,
            year,
        )

        compressed = gzip.compress(
            body,
            compresslevel=9,
            mtime=0,
        )

        atomic_write_bytes(
            cache_path,
            compressed,
        )

        network_retrieved = True

    source_record = {
        "requested_year": year,
        "request_url": url,
        "cache_path": str(
            cache_path.relative_to(ROOT)
        ),
        "source_rows": len(panel),
        "minimum_source_date": (
            panel["target_date"].min().date().isoformat()
        ),
        "maximum_source_date": (
            panel["target_date"].max().date().isoformat()
        ),
        "nonmissing_temperature_rows": int(
            panel["hko_daily_max_c"]
            .notna()
            .sum()
        ),
        "missing_temperature_rows": int(
            panel["hko_daily_max_c"]
            .isna()
            .sum()
        ),
        "network_retrieved": network_retrieved,
        "cache_reused": cache_reused,
        "response_sha256": sha256_bytes(body),
        "compressed_file_sha256": sha256_file(
            cache_path
        ),
        "compressed_file_bytes": (
            cache_path.stat().st_size
        ),
        "retrieval_status": (
            "DOWNLOADED_VALID"
            if network_retrieved
            else "CACHED_VALID"
        ),
    }

    return panel, source_record


def load_training_dates() -> pd.DataFrame:
    support = pd.read_csv(
        SUPPORT_PATH
    )

    if "target_date" not in support.columns:
        raise RuntimeError(
            "The Phase 4E support panel has no target_date column."
        )

    support["target_date"] = pd.to_datetime(
        support["target_date"],
        errors="raise",
        format="mixed",
    ).dt.normalize()

    dates = (
        support[["target_date"]]
        .drop_duplicates()
        .sort_values("target_date")
        .reset_index(drop=True)
    )

    if len(dates) != 730:
        raise RuntimeError(
            f"Expected 730 training dates, found {len(dates)}."
        )

    expected = pd.date_range(
        dates["target_date"].min(),
        dates["target_date"].max(),
        freq="D",
    )

    if len(expected) != 730:
        raise RuntimeError(
            "The weather-only training interval is not "
            "a continuous 730-day interval."
        )

    if not dates["target_date"].reset_index(
        drop=True
    ).equals(
        pd.Series(
            expected,
            name="target_date",
        )
    ):
        raise RuntimeError(
            "The weather-only training dates contain a gap."
        )

    return dates


def main(offline: bool) -> None:
    specification = json.loads(
        SPEC_PATH.read_text(
            encoding="utf-8"
        )
    )

    training_dates = load_training_dates()

    first_training_date = (
        training_dates["target_date"]
        .min()
    )

    last_training_date = (
        training_dates["target_date"]
        .max()
    )

    years = list(
        range(
            first_training_date.year,
            last_training_date.year + 1,
        )
    )

    source_panels = []
    source_records = []

    for year in years:
        panel, record = retrieve_year(
            year=year,
            specification=specification,
            offline=offline,
        )

        source_panels.append(panel)
        source_records.append(record)

        print(
            f"HKO {year}: {record['retrieval_status']}, "
            f"rows={record['source_rows']}",
            flush=True,
        )

    source = pd.concat(
        source_panels,
        ignore_index=True,
    )

    source = (
        source.sort_values(
            ["target_date", "requested_year"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    duplicate_dates = source.loc[
        source.duplicated(
            "target_date",
            keep=False,
        )
    ]

    if not duplicate_dates.empty:
        raise RuntimeError(
            "The combined HKO source contains duplicate dates:\n"
            + duplicate_dates.head(20).to_string(index=False)
        )

    training_date_set = set(
        training_dates[
            "target_date"
        ].tolist()
    )

    source["included_in_weather_only_training"] = (
        source["target_date"].isin(
            training_date_set
        )
    )

    excluded = source.loc[
        ~source[
            "included_in_weather_only_training"
        ]
    ].copy()

    selected_source = source.loc[
        source[
            "included_in_weather_only_training"
        ]
    ].copy()

    training_panel = training_dates.merge(
        selected_source[
            [
                "target_date",
                "hko_daily_max_c",
                "hko_daily_max_c_raw",
                "station",
                "station_name",
                "data_type",
                "temperature_unit",
                "requested_year",
            ]
        ],
        on="target_date",
        how="left",
        validate="one_to_one",
    )

    training_panel[
        "weather_only_training_period"
    ] = True

    training_panel[
        "weather_plus_market_training_period"
    ] = False

    training_panel[
        "out_of_sample_validation_period"
    ] = False

    training_panel[
        "market_price_accessed"
    ] = False

    training_panel[
        "polymarket_outcome_accessed"
    ] = False

    training_panel[
        "model_fitted"
    ] = False

    training_panel[
        "model_selected"
    ] = False

    missing_training_rows = training_panel.loc[
        training_panel[
            "hko_daily_max_c"
        ].isna()
    ]

    plausible_temperatures = (
        training_panel[
            "hko_daily_max_c"
        ]
        .between(
            -20.0,
            60.0,
            inclusive="both",
        )
        .all()
    )

    unique_training_dates = (
        training_panel[
            "target_date"
        ].is_unique
    )

    exact_training_dates = (
        len(training_panel) == 730
        and training_panel[
            "target_date"
        ].min()
        == first_training_date
        and training_panel[
            "target_date"
        ].max()
        == last_training_date
    )

    excluded_after_training = int(
        excluded[
            "target_date"
        ].gt(last_training_date)
        .sum()
    )

    excluded_before_training = int(
        excluded[
            "target_date"
        ].lt(first_training_date)
        .sum()
    )

    checks = pd.DataFrame(
        [
            {
                "check": "weather_only_training_date_count",
                "required": True,
                "passed": len(training_panel) == 730,
                "detail": len(training_panel),
            },
            {
                "check": "training_dates_unique",
                "required": True,
                "passed": unique_training_dates,
                "detail": (
                    training_panel[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "exact_training_date_interval",
                "required": True,
                "passed": exact_training_dates,
                "detail": (
                    f"{first_training_date.date()} "
                    f"to {last_training_date.date()}"
                ),
            },
            {
                "check": "all_training_temperatures_present",
                "required": True,
                "passed": missing_training_rows.empty,
                "detail": len(
                    missing_training_rows
                ),
            },
            {
                "check": "training_temperatures_plausible",
                "required": True,
                "passed": plausible_temperatures,
                "detail": (
                    f"{training_panel['hko_daily_max_c'].min():.1f} "
                    f"to "
                    f"{training_panel['hko_daily_max_c'].max():.1f}"
                ),
            },
            {
                "check": "source_years_complete",
                "required": True,
                "passed": (
                    sorted(
                        source[
                            "requested_year"
                        ].unique().tolist()
                    )
                    == years
                ),
                "detail": ",".join(
                    map(str, years)
                ),
            },
            {
                "check": "later_source_rows_excluded",
                "required": True,
                "passed": (
                    not training_panel[
                        "target_date"
                    ].gt(
                        last_training_date
                    ).any()
                ),
                "detail": (
                    excluded_after_training
                ),
            },
            {
                "check": "market_prices_not_accessed",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "polymarket_outcomes_not_accessed",
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
            "Required HKO checks failed:\n"
            + required_failed.to_string(index=False)
        )

    source_inventory = pd.DataFrame(
        source_records
    )

    summary = pd.DataFrame(
        [
            {
                "weather_only_training_dates": (
                    len(training_panel)
                ),
                "first_training_date": (
                    first_training_date.date().isoformat()
                ),
                "last_training_date": (
                    last_training_date.date().isoformat()
                ),
                "source_years": ",".join(
                    map(str, years)
                ),
                "minimum_hko_daily_max_c": float(
                    training_panel[
                        "hko_daily_max_c"
                    ].min()
                ),
                "mean_hko_daily_max_c": float(
                    training_panel[
                        "hko_daily_max_c"
                    ].mean()
                ),
                "maximum_hko_daily_max_c": float(
                    training_panel[
                        "hko_daily_max_c"
                    ].max()
                ),
                "missing_training_temperatures": int(
                    training_panel[
                        "hko_daily_max_c"
                    ].isna()
                    .sum()
                ),
                "source_rows_excluded_before_training": (
                    excluded_before_training
                ),
                "source_rows_excluded_after_training": (
                    excluded_after_training
                ),
                "market_prices_accessed": False,
                "polymarket_outcomes_accessed": False,
                "model_fitted": False,
                "model_selected": False,
            }
        ]
    )

    training_panel[
        "target_date"
    ] = (
        training_panel[
            "target_date"
        ].dt.date.astype(str)
    )

    excluded[
        "target_date"
    ] = (
        excluded[
            "target_date"
        ].dt.date.astype(str)
    )

    write_csv(
        source_inventory,
        SOURCE_INVENTORY_PATH,
    )

    write_csv(
        training_panel,
        TRAINING_PANEL_PATH,
    )

    write_csv(
        excluded,
        EXCLUDED_ROWS_PATH,
    )

    write_csv(
        checks,
        CHECKS_PATH,
    )

    write_csv(
        summary,
        SUMMARY_PATH,
    )

    output_paths = [
        SOURCE_INVENTORY_PATH,
        TRAINING_PANEL_PATH,
        EXCLUDED_ROWS_PATH,
        CHECKS_PATH,
        SUMMARY_PATH,
    ]

    raw_paths = [
        RAW_ROOT
        / f"hko_clmmaxt_{year}.json.gz"
        for year in years
    ]

    manifest = {
        "phase": 4,
        "subphase": "4F",
        "phase_status": (
            "PHASE4_HKO_TRAINING_OBSERVATIONS_COMPLETE"
        ),
        "status": (
            "HKO_DAILY_MAXIMUM_TRAINING_PANEL_CERTIFIED"
        ),
        "created_utc": utc_now(),
        "source_name": specification[
            "source_name"
        ],
        "source_data_type": specification[
            "data_type"
        ],
        "source_station": specification[
            "station"
        ],
        "source_years": years,
        "weather_only_training_dates": (
            len(training_panel)
        ),
        "first_training_date": (
            first_training_date.date().isoformat()
        ),
        "last_training_date": (
            last_training_date.date().isoformat()
        ),
        "missing_training_temperatures": int(
            training_panel[
                "hko_daily_max_c"
            ].isna()
            .sum()
        ),
        "source_rows_received": int(
            len(source)
        ),
        "source_rows_used": int(
            len(training_panel)
        ),
        "source_rows_excluded": int(
            len(excluded)
        ),
        "source_rows_excluded_before_training": (
            excluded_before_training
        ),
        "source_rows_excluded_after_training": (
            excluded_after_training
        ),
        "post_training_hko_rows_used": 0,
        "training_hko_observations_accessed": True,
        "market_prices_accessed": False,
        "polymarket_outcomes_accessed": False,
        "model_fitted": False,
        "model_selected": False,
        "continuous_calibration_selected": False,
        "probability_calibration_selected": False,
        "categorical_scores_calculated": False,
        "trading_strategy_selected": False,
        "trading_returns_calculated": False,
        "required_integrity_checks_passed": True,
        "raw_paths": [
            str(path.relative_to(ROOT))
            for path in raw_paths
        ],
        "raw_hashes": {
            str(path.relative_to(ROOT)): (
                sha256_file(path)
            )
            for path in raw_paths
        },
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
            "Join the certified HKO observations to the "
            "2,920 weather-only forecast rows and construct "
            "forecast residuals."
        ),
    }

    write_json(
        MANIFEST_PATH,
        manifest,
    )

    print()
    print("=" * 78)
    print("PHASE 4F HKO TRAINING PANEL COMPLETE")
    print("=" * 78)
    print(
        "Weather-only training dates:",
        len(training_panel),
    )
    print(
        "Training interval:",
        first_training_date.date(),
        "to",
        last_training_date.date(),
    )
    print("HKO source years:", years)
    print(
        "Missing HKO training temperatures:",
        int(
            training_panel[
                "hko_daily_max_c"
            ].isna()
            .sum()
        ),
    )
    print(
        "Source rows excluded before training:",
        excluded_before_training,
    )
    print(
        "Source rows excluded after training:",
        excluded_after_training,
    )
    print(
        "HKO maximum-temperature range:",
        f"{training_panel['hko_daily_max_c'].min():.1f}",
        "to",
        f"{training_panel['hko_daily_max_c'].max():.1f}",
        "degrees Celsius",
    )
    print("Training HKO observations accessed: True")
    print("Post-training HKO observations used: 0")
    print("Market prices accessed: False")
    print("Polymarket outcomes accessed: False")
    print("Model fitted or selected: False")


def cli() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Use only existing validated HKO cache files."
        ),
    )

    arguments = parser.parse_args()
    main(offline=arguments.offline)


if __name__ == "__main__":
    cli()
