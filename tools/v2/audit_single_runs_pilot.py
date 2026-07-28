from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
    "single_runs_pilot_spec.json"
)

SOURCE_PANEL_PATH = (
    ROOT
    / "data/processed/"
    "02_chronological_design_panel.csv"
)

RAW_DIR = (
    ROOT
    / "data/raw/v2/"
    "open_meteo_single_runs_pilot"
)

INTERIM_DIR = ROOT / "data/interim/v2"
PROCESSED_DIR = ROOT / "data/processed/v2"
DIAGNOSTIC_DIR = ROOT / "outputs/v2/diagnostics"
MANIFEST_DIR = ROOT / "data/manifests/v2"

REQUEST_PLAN_PATH = (
    INTERIM_DIR
    / "01_single_runs_pilot_request_plan.csv"
)

PROBE_RESULTS_PATH = (
    DIAGNOSTIC_DIR
    / "01_single_runs_archive_probe_results.csv"
)

OVERLAP_RESULTS_PATH = (
    PROCESSED_DIR
    / "01_single_runs_overlap_reconstruction.csv"
)

OVERLAP_SUMMARY_PATH = (
    DIAGNOSTIC_DIR
    / "01_single_runs_overlap_summary.csv"
)

INTEGRITY_CHECKS_PATH = (
    DIAGNOSTIC_DIR
    / "01_single_runs_pilot_integrity_checks.csv"
)

MANIFEST_PATH = (
    MANIFEST_DIR
    / "01_single_runs_pilot_manifest.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {
        "true",
        "1",
    }


def fetch_run(
    spec: dict,
    run_text: str,
) -> tuple[dict | None, str | None, Path]:
    filename = (
        run_text
        .replace("-", "")
        .replace(":", "")
        + ".json"
    )

    cache_path = RAW_DIR / filename

    if cache_path.exists():
        payload = json.loads(
            cache_path.read_text(
                encoding="utf-8"
            )
        )

        return payload, None, cache_path

    parameters = {
        "latitude": spec["latitude"],
        "longitude": spec["longitude"],
        "run": run_text,
        "hourly": spec["hourly_variable"],
        "models": spec["model"],
        "timezone": spec["timezone"],
        "temperature_unit": "celsius",
        "cell_selection": spec["cell_selection"],
        "forecast_hours": spec["forecast_hours"],
    }

    request_url = (
        spec["endpoint"]
        + "?"
        + urllib.parse.urlencode(parameters)
    )

    last_error = None

    for attempt in range(1, 5):
        try:
            request = urllib.request.Request(
                request_url,
                headers={
                    "User-Agent":
                    "UCL-MSc-weather-study/2.0"
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=180,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            if (
                "hourly" not in payload
                or "time"
                not in payload["hourly"]
                or "temperature_2m"
                not in payload["hourly"]
            ):
                raise RuntimeError(
                    "The API response does not "
                    "contain hourly temperature data."
                )

            cache_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            time.sleep(0.25)

            return payload, None, cache_path

        except Exception as error:
            last_error = (
                f"{type(error).__name__}: "
                f"{error}"
            )

            if attempt < 4:
                time.sleep(
                    2 * attempt
                )

    return None, last_error, cache_path


def hourly_frame(
    payload: dict,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "local_time": pd.to_datetime(
                payload["hourly"]["time"],
                errors="coerce",
            ),
            "temperature_2m_c": pd.to_numeric(
                payload["hourly"][
                    "temperature_2m"
                ],
                errors="coerce",
            ),
        }
    ).dropna(
        subset=["local_time"]
    )


def select_spaced_dates(
    eligible_dates: list[pd.Timestamp],
    count: int,
) -> list[pd.Timestamp]:
    if len(eligible_dates) < count:
        raise RuntimeError(
            f"Only {len(eligible_dates)} "
            f"eligible overlap dates exist; "
            f"{count} are required."
        )

    if count == 1:
        return [eligible_dates[0]]

    indices = [
        round(
            index
            * (len(eligible_dates) - 1)
            / (count - 1)
        )
        for index in range(count)
    ]

    selected = []

    for index in indices:
        date = eligible_dates[index]

        if date not in selected:
            selected.append(date)

    for date in eligible_dates:
        if len(selected) >= count:
            break

        if date not in selected:
            selected.append(date)

    return sorted(
        selected[:count]
    )


def build_overlap_plan(
    spec: dict,
) -> pd.DataFrame:
    panel = pd.read_csv(
        SOURCE_PANEL_PATH
    )

    required_columns = [
        "target_date",
        "decision_rule",
        "forecast_issue_time_utc",
        "decision_time_utc",
        "forecast_daily_max_c",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in panel.columns
    ]

    if missing_columns:
        raise RuntimeError(
            "The source panel is missing: "
            + ", ".join(missing_columns)
        )

    panel["target_date"] = pd.to_datetime(
        panel["target_date"],
        errors="coerce",
    ).dt.normalize()

    panel[
        "forecast_issue_time_utc"
    ] = pd.to_datetime(
        panel["forecast_issue_time_utc"],
        errors="coerce",
        utc=True,
    )

    panel[
        "decision_time_utc"
    ] = pd.to_datetime(
        panel["decision_time_utc"],
        errors="coerce",
        utc=True,
    )

    panel[
        "forecast_daily_max_c"
    ] = pd.to_numeric(
        panel["forecast_daily_max_c"],
        errors="coerce",
    )

    overlap_start = pd.Timestamp(
        spec["overlap_start"]
    )

    overlap_end = pd.Timestamp(
        spec["overlap_end"]
    )

    rules = spec["decision_rules"]

    subset = panel.loc[
        panel["target_date"].between(
            overlap_start,
            overlap_end,
        )
        & panel["decision_rule"].isin(
            rules
        )
    ].dropna(
        subset=[
            "forecast_issue_time_utc",
            "decision_time_utc",
            "forecast_daily_max_c",
        ]
    )

    eligible_dates = (
        subset.groupby(
            "target_date"
        )["decision_rule"]
        .nunique()
        .loc[
            lambda values:
            values.eq(len(rules))
        ]
        .index
        .tolist()
    )

    eligible_dates = sorted(
        eligible_dates
    )

    selected_dates = select_spaced_dates(
        eligible_dates,
        spec["overlap_date_count"],
    )

    selected = (
        subset.loc[
            subset["target_date"].isin(
                selected_dates
            )
        ]
        .drop_duplicates(
            [
                "target_date",
                "decision_rule",
            ]
        )
        .copy()
    )

    expected_rows = (
        spec["overlap_date_count"]
        * len(rules)
    )

    if len(selected) != expected_rows:
        raise RuntimeError(
            f"The overlap plan has "
            f"{len(selected)} rows; "
            f"{expected_rows} were expected."
        )

    valid_cycle = (
        selected[
            "forecast_issue_time_utc"
        ]
        .dt.hour
        .isin([0, 6, 12, 18])
        &
        selected[
            "forecast_issue_time_utc"
        ]
        .dt.minute
        .eq(0)
    )

    if not valid_cycle.all():
        invalid = selected.loc[
            ~valid_cycle,
            [
                "target_date",
                "decision_rule",
                "forecast_issue_time_utc",
            ],
        ]

        raise RuntimeError(
            "At least one existing forecast "
            "timestamp is not a valid IFS cycle:\n"
            + invalid.to_string(
                index=False
            )
        )

    rule_order = {
        rule: index
        for index, rule
        in enumerate(rules)
    }

    selected["_rule_order"] = (
        selected["decision_rule"]
        .map(rule_order)
    )

    selected = selected.sort_values(
        [
            "target_date",
            "_rule_order",
        ]
    )

    plan = pd.DataFrame(
        {
            "request_id": range(
                1,
                len(selected) + 1,
            ),
            "target_date": (
                selected["target_date"]
                .dt.strftime("%Y-%m-%d")
            ),
            "decision_rule": (
                selected["decision_rule"]
                .astype(str)
            ),
            "run_init_utc": (
                selected[
                    "forecast_issue_time_utc"
                ]
                .dt.strftime(
                    "%Y-%m-%dT%H:%M"
                )
            ),
            "decision_time_utc": (
                selected[
                    "decision_time_utc"
                ]
                .dt.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            ),
            "existing_forecast_daily_max_c": (
                selected[
                    "forecast_daily_max_c"
                ]
                .astype(float)
            ),
        }
    )

    assumed_available = (
        pd.to_datetime(
            plan["run_init_utc"],
            utc=True,
        )
        + pd.to_timedelta(
            spec[
                "availability_delay_hours"
            ],
            unit="h",
        )
    )

    plan[
        "assumed_available_utc"
    ] = assumed_available.dt.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    plan[
        "available_before_decision"
    ] = (
        assumed_available
        <= pd.to_datetime(
            plan["decision_time_utc"],
            utc=True,
        )
    )

    return plan


def main() -> None:
    for directory in [
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        DIAGNOSTIC_DIR,
        MANIFEST_DIR,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    spec = json.loads(
        SPEC_PATH.read_text(
            encoding="utf-8"
        )
    )

    request_plan = build_overlap_plan(
        spec
    )

    request_plan.to_csv(
        REQUEST_PLAN_PATH,
        index=False,
    )

    probe_records = []

    for run_text in spec[
        "archive_probe_runs"
    ]:
        payload, error, cache_path = fetch_run(
            spec,
            run_text,
        )

        if payload is None:
            probe_records.append(
                {
                    "run_init_utc":
                    run_text,
                    "request_succeeded":
                    False,
                    "hourly_rows":
                    0,
                    "returned_timezone":
                    None,
                    "returned_latitude":
                    None,
                    "returned_longitude":
                    None,
                    "cache_path":
                    str(
                        cache_path.relative_to(
                            ROOT
                        )
                    ),
                    "error":
                    error,
                }
            )

            continue

        frame = hourly_frame(
            payload
        )

        probe_records.append(
            {
                "run_init_utc":
                run_text,
                "request_succeeded":
                True,
                "hourly_rows":
                len(frame),
                "returned_timezone":
                payload.get("timezone"),
                "returned_latitude":
                payload.get("latitude"),
                "returned_longitude":
                payload.get("longitude"),
                "cache_path":
                str(
                    cache_path.relative_to(
                        ROOT
                    )
                ),
                "error":
                None,
            }
        )

    probes = pd.DataFrame(
        probe_records
    )

    probes.to_csv(
        PROBE_RESULTS_PATH,
        index=False,
    )

    overlap_records = []

    payload_cache = {}

    for row in request_plan.itertuples(
        index=False
    ):
        if (
            row.run_init_utc
            not in payload_cache
        ):
            payload_cache[
                row.run_init_utc
            ] = fetch_run(
                spec,
                row.run_init_utc,
            )

        payload, error, cache_path = (
            payload_cache[
                row.run_init_utc
            ]
        )

        target_hours = pd.DataFrame()

        if payload is not None:
            frame = hourly_frame(
                payload
            )

            target_hours = frame.loc[
                frame[
                    "local_time"
                ]
                .dt.strftime("%Y-%m-%d")
                .eq(row.target_date)
            ]

        if (
            not target_hours.empty
            and target_hours[
                "temperature_2m_c"
            ].notna().any()
        ):
            reconstructed_max = float(
                target_hours[
                    "temperature_2m_c"
                ].max()
            )
        else:
            reconstructed_max = float(
                "nan"
            )

        difference = (
            reconstructed_max
            - row.existing_forecast_daily_max_c
        )

        overlap_records.append(
            {
                "request_id":
                row.request_id,
                "target_date":
                row.target_date,
                "decision_rule":
                row.decision_rule,
                "run_init_utc":
                row.run_init_utc,
                "decision_time_utc":
                row.decision_time_utc,
                "assumed_available_utc":
                row.assumed_available_utc,
                "available_before_decision":
                row.available_before_decision,
                "request_succeeded":
                payload is not None,
                "local_hour_count":
                len(target_hours),
                "existing_forecast_daily_max_c":
                row.existing_forecast_daily_max_c,
                "reconstructed_daily_max_c":
                reconstructed_max,
                "difference_new_minus_existing_c":
                difference,
                "absolute_difference_c":
                abs(difference),
                "returned_timezone":
                (
                    payload.get("timezone")
                    if payload is not None
                    else None
                ),
                "raw_path":
                str(
                    cache_path.relative_to(
                        ROOT
                    )
                ),
                "error":
                error,
            }
        )

    overlap = pd.DataFrame(
        overlap_records
    )

    overlap.to_csv(
        OVERLAP_RESULTS_PATH,
        index=False,
    )

    differences = pd.to_numeric(
        overlap[
            "absolute_difference_c"
        ],
        errors="coerce",
    ).dropna()

    if differences.empty:
        mean_difference = None
        median_difference = None
        maximum_difference = None
    else:
        mean_difference = float(
            differences.mean()
        )

        median_difference = float(
            differences.median()
        )

        maximum_difference = float(
            differences.max()
        )

    summary = pd.DataFrame(
        [
            {
                "overlap_dates":
                overlap[
                    "target_date"
                ].nunique(),
                "overlap_rows":
                len(overlap),
                "successful_rows":
                int(
                    overlap[
                        "request_succeeded"
                    ].sum()
                ),
                "complete_24_hour_rows":
                int(
                    overlap[
                        "local_hour_count"
                    ]
                    .eq(24)
                    .sum()
                ),
                "availability_pass_rows":
                int(
                    overlap[
                        "available_before_decision"
                    ].sum()
                ),
                "mean_absolute_difference_c":
                mean_difference,
                "median_absolute_difference_c":
                median_difference,
                "maximum_absolute_difference_c":
                maximum_difference,
            }
        ]
    )

    summary.to_csv(
        OVERLAP_SUMMARY_PATH,
        index=False,
    )

    tolerance = spec[
        "diagnostic_tolerances"
    ]

    core_checks = [
        {
            "check":
            "archive_probe_requests",
            "required":
            True,
            "passed":
            bool(
                probes[
                    "request_succeeded"
                ].all()
            ),
            "detail":
            (
                f"{int(probes['request_succeeded'].sum())}"
                f"/{len(probes)}"
            ),
        },
        {
            "check":
            "overlap_requests",
            "required":
            True,
            "passed":
            bool(
                overlap[
                    "request_succeeded"
                ].all()
            ),
            "detail":
            (
                f"{int(overlap['request_succeeded'].sum())}"
                f"/{len(overlap)}"
            ),
        },
        {
            "check":
            "target_dates_have_24_local_hours",
            "required":
            True,
            "passed":
            bool(
                overlap[
                    "local_hour_count"
                ]
                .eq(24)
                .all()
            ),
            "detail":
            (
                f"{int(overlap['local_hour_count'].eq(24).sum())}"
                f"/{len(overlap)}"
            ),
        },
        {
            "check":
            "runs_available_before_decisions",
            "required":
            True,
            "passed":
            bool(
                overlap[
                    "available_before_decision"
                ].all()
            ),
            "detail":
            (
                f"{int(overlap['available_before_decision'].sum())}"
                f"/{len(overlap)}"
            ),
        },
        {
            "check":
            "returned_timezone",
            "required":
            True,
            "passed":
            bool(
                overlap[
                    "returned_timezone"
                ]
                .eq(
                    spec["timezone"]
                )
                .all()
            ),
            "detail":
            ",".join(
                sorted(
                    overlap[
                        "returned_timezone"
                    ]
                    .dropna()
                    .astype(str)
                    .unique()
                )
            ),
        },
        {
            "check":
            "median_overlap_difference",
            "required":
            False,
            "passed":
            bool(
                median_difference
                is not None
                and median_difference
                <= tolerance[
                    "median_absolute_difference_c"
                ]
            ),
            "detail":
            (
                f"{median_difference:.6f}"
                if median_difference is not None
                else "missing"
            ),
        },
        {
            "check":
            "maximum_overlap_difference",
            "required":
            False,
            "passed":
            bool(
                maximum_difference
                is not None
                and maximum_difference
                <= tolerance[
                    "maximum_absolute_difference_c"
                ]
            ),
            "detail":
            (
                f"{maximum_difference:.6f}"
                if maximum_difference is not None
                else "missing"
            ),
        },
    ]

    checks = pd.DataFrame(
        core_checks
    )

    checks.to_csv(
        INTEGRITY_CHECKS_PATH,
        index=False,
    )

    required_checks = checks.loc[
        checks["required"]
    ]

    pilot_approved = bool(
        required_checks[
            "passed"
        ].all()
    )

    diagnostic_differences_pass = bool(
        checks.loc[
            ~checks["required"],
            "passed",
        ].all()
    )

    if not pilot_approved:
        status = (
            "SINGLE_RUNS_PILOT_REVIEW_REQUIRED"
        )
    elif diagnostic_differences_pass:
        status = (
            "SINGLE_RUNS_PILOT_APPROVED"
        )
    else:
        status = (
            "SINGLE_RUNS_PILOT_APPROVED_"
            "WITH_OVERLAP_DIFFERENCES"
        )

    output_paths = [
        REQUEST_PLAN_PATH,
        PROBE_RESULTS_PATH,
        OVERLAP_RESULTS_PATH,
        OVERLAP_SUMMARY_PATH,
        INTEGRITY_CHECKS_PATH,
    ]

    manifest = {
        "status":
        status,
        "pilot_approved":
        pilot_approved,
        "overlap_differences_are_diagnostic":
        True,
        "source":
        "Open-Meteo Single Runs API",
        "model":
        spec["model"],
        "location": {
            "station":
            spec["station"],
            "latitude":
            spec["latitude"],
            "longitude":
            spec["longitude"],
        },
        "availability_delay_hours":
        spec["availability_delay_hours"],
        "archive_probe_runs":
        len(probes),
        "successful_archive_probe_runs":
        int(
            probes[
                "request_succeeded"
            ].sum()
        ),
        "overlap_dates":
        int(
            overlap[
                "target_date"
            ].nunique()
        ),
        "overlap_rows":
        len(overlap),
        "successful_overlap_rows":
        int(
            overlap[
                "request_succeeded"
            ].sum()
        ),
        "complete_24_hour_rows":
        int(
            overlap[
                "local_hour_count"
            ]
            .eq(24)
            .sum()
        ),
        "median_absolute_difference_c":
        median_difference,
        "maximum_absolute_difference_c":
        maximum_difference,
        "all_required_checks_passed":
        pilot_approved,
        "market_prices_accessed":
        False,
        "realised_outcomes_accessed":
        False,
        "model_fitted":
        False,
        "model_selected":
        False,
        "version_1_modified":
        False,
        "raw_cache_file_count":
        len(
            list(
                RAW_DIR.glob(
                    "*.json"
                )
            )
        ),
        "output_hashes": {
            str(
                path.relative_to(ROOT)
            ):
            sha256(path)
            for path in output_paths
        },
        "next_stage": (
            "Construct the complete two-year "
            "weather-only request plan."
            if pilot_approved
            else
            "Inspect and repair the pilot "
            "before full retrieval."
        ),
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

    print("=" * 76)
    print(
        "PHASE 2 OPEN-METEO "
        "SINGLE RUNS PILOT"
    )
    print("=" * 76)
    print(
        "Status:",
        status,
    )
    print(
        "Archive probes:",
        (
            f"{manifest['successful_archive_probe_runs']}"
            f"/{len(probes)}"
        ),
    )
    print(
        "Overlap rows:",
        (
            f"{manifest['successful_overlap_rows']}"
            f"/{len(overlap)}"
        ),
    )
    print(
        "Complete target days:",
        (
            f"{manifest['complete_24_hour_rows']}"
            f"/{len(overlap)}"
        ),
    )
    print(
        "Median absolute difference:",
        median_difference,
    )
    print(
        "Maximum absolute difference:",
        maximum_difference,
    )
    print()
    print(
        checks.to_string(
            index=False
        )
    )
    print()
    print(
        "Manifest:",
        MANIFEST_PATH.relative_to(
            ROOT
        ),
    )


if __name__ == "__main__":
    main()
