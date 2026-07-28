from __future__ import annotations

import hashlib
import json
import urllib.parse
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
    "two_year_request_plan_spec.json"
)

PHASE2_MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "01_single_runs_pilot_manifest.json"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "02_two_year_request_plan_manifest.json"
)

PLAN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_request_plan.csv"
)

CORE_PLAN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_core_request_plan.csv"
)

SUPPLEMENTARY_PLAN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_supplementary_request_plan.csv"
)

SUPPORT_MAP_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_training_target_support_map.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_request_plan_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "02_two_year_request_plan_integrity_checks.csv"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def date_sequence(
    start: date,
    end: date,
) -> list[date]:
    dates: list[date] = []
    current = start

    while current <= end:
        dates.append(current)
        current += timedelta(days=1)

    return dates


def add_check(
    records: list[dict[str, Any]],
    name: str,
    required: bool,
    passed: bool,
    detail: Any,
) -> None:
    records.append(
        {
            "check": name,
            "required": required,
            "passed": bool(passed),
            "detail": str(detail),
        }
    )


def main() -> None:
    spec = json.loads(
        SPEC_PATH.read_text(
            encoding="utf-8"
        )
    )

    phase2 = json.loads(
        PHASE2_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    if (
        phase2.get("phase_status")
        != "PHASE2_COMPLETE"
    ):
        raise RuntimeError(
            "Phase 2 is not complete."
        )

    if not phase2.get(
        "pilot_approved",
        False,
    ):
        raise RuntimeError(
            "Phase 2 source pilot is not approved."
        )

    training_start = parse_date(
        spec["weather_only_training_start"]
    )

    training_end = parse_date(
        spec["weather_only_training_end"]
    )

    request_start = parse_date(
        spec["request_initialisation_start"]
    )

    request_end = parse_date(
        spec["request_initialisation_end"]
    )

    market_training_start = parse_date(
        spec["weather_plus_market_training_start"]
    )

    validation_start = parse_date(
        spec["out_of_sample_validation_start"]
    )

    training_dates = date_sequence(
        training_start,
        training_end,
    )

    request_dates = date_sequence(
        request_start,
        request_end,
    )

    core_cycles = [
        int(value)
        for value in spec["core_cycles_utc"]
    ]

    supplementary_cycles = [
        int(value)
        for value in spec[
            "supplementary_cycles_utc"
        ]
    ]

    all_cycles = sorted(
        core_cycles
        + supplementary_cycles
    )

    plan_records: list[dict[str, Any]] = []

    for run_date in request_dates:
        if run_date < training_start:
            run_period = "support_buffer"
        else:
            run_period = "weather_only_training"

        for cycle in all_cycles:
            run_datetime = datetime.combine(
                run_date,
                time(
                    hour=cycle,
                    minute=0,
                ),
                tzinfo=timezone.utc,
            )

            run_parameter = (
                f"{run_date.isoformat()}"
                f"T{cycle:02d}:00"
            )

            cycle_role = (
                "core"
                if cycle in core_cycles
                else "supplementary"
            )

            retrieval_selected = (
                cycle in core_cycles
            )

            parameters = {
                "latitude": spec["latitude"],
                "longitude": spec["longitude"],
                "run": run_parameter,
                "hourly": spec[
                    "hourly_variable"
                ],
                "models": spec["model"],
                "timezone": spec["timezone"],
                "temperature_unit": spec[
                    "temperature_unit"
                ],
                "cell_selection": spec[
                    "cell_selection"
                ],
                "forecast_hours": spec[
                    "forecast_hours"
                ],
            }

            request_url = (
                spec["endpoint"]
                + "?"
                + urllib.parse.urlencode(
                    parameters
                )
            )

            forecast_start_hkt = (
                run_datetime
                + timedelta(hours=8)
            )

            forecast_end_hkt = (
                forecast_start_hkt
                + timedelta(
                    hours=(
                        int(
                            spec[
                                "forecast_hours"
                            ]
                        )
                        - 1
                    )
                )
            )

            cache_path = (
                "data/raw/v2/"
                "open_meteo_single_runs_two_year/"
                f"{run_date:%Y}/"
                f"{run_date:%m}/"
                "ecmwf_ifs_"
                f"{run_date:%Y%m%d}_"
                f"{cycle:02d}.json"
            )

            plan_records.append(
                {
                    "request_id": (
                        "ifs_"
                        f"{run_date:%Y%m%d}_"
                        f"{cycle:02d}"
                    ),
                    "run_date": (
                        run_date.isoformat()
                    ),
                    "run_init_utc": (
                        run_datetime.isoformat()
                    ),
                    "run_parameter": (
                        run_parameter
                    ),
                    "cycle_utc": cycle,
                    "cycle_role": cycle_role,
                    "retrieval_selected": (
                        retrieval_selected
                    ),
                    "required_for_core_design": (
                        retrieval_selected
                    ),
                    "run_period": run_period,
                    "weather_only_training_start": (
                        training_start.isoformat()
                    ),
                    "weather_only_training_end": (
                        training_end.isoformat()
                    ),
                    "forecast_start_hkt": (
                        forecast_start_hkt.isoformat()
                    ),
                    "forecast_end_hkt": (
                        forecast_end_hkt.isoformat()
                    ),
                    "first_local_date_covered": (
                        forecast_start_hkt.date()
                        .isoformat()
                    ),
                    "last_local_date_covered": (
                        forecast_end_hkt.date()
                        .isoformat()
                    ),
                    "forecast_hours": int(
                        spec["forecast_hours"]
                    ),
                    "model": spec["model"],
                    "hourly_variable": spec[
                        "hourly_variable"
                    ],
                    "timezone": spec["timezone"],
                    "temperature_unit": spec[
                        "temperature_unit"
                    ],
                    "cell_selection": spec[
                        "cell_selection"
                    ],
                    "latitude": float(
                        spec["latitude"]
                    ),
                    "longitude": float(
                        spec["longitude"]
                    ),
                    "endpoint": spec["endpoint"],
                    "request_url": request_url,
                    "cache_path": cache_path,
                    "request_status": "PLANNED",
                    "network_request_made": False,
                    "market_price_accessed": False,
                    "outcome_accessed": False,
                }
            )

    plan = pd.DataFrame(plan_records)

    plan = plan.sort_values(
        [
            "run_date",
            "cycle_utc",
        ],
        kind="stable",
    ).reset_index(drop=True)

    core_plan = plan.loc[
        plan["retrieval_selected"]
    ].copy()

    supplementary_plan = plan.loc[
        ~plan["retrieval_selected"]
    ].copy()

    support_records: list[
        dict[str, Any]
    ] = []

    core_lookup = {
        (
            date.fromisoformat(
                row.run_date
            ),
            int(row.cycle_utc),
        ): row.request_id
        for row in core_plan.itertuples(
            index=False
        )
    }

    for target_date in training_dates:
        support_dates = [
            target_date
            - timedelta(days=2),
            target_date
            - timedelta(days=1),
            target_date,
        ]

        support_ids: list[str] = []

        for support_date in support_dates:
            for cycle in core_cycles:
                request_id = core_lookup.get(
                    (
                        support_date,
                        cycle,
                    )
                )

                if request_id is not None:
                    support_ids.append(
                        request_id
                    )

        support_records.append(
            {
                "target_date": (
                    target_date.isoformat()
                ),
                "target_period": (
                    "weather_only_training"
                ),
                "earliest_support_run_date": (
                    support_dates[0]
                    .isoformat()
                ),
                "latest_support_run_date": (
                    support_dates[-1]
                    .isoformat()
                ),
                "expected_core_support_requests": 6,
                "available_core_support_requests": (
                    len(support_ids)
                ),
                "support_complete": (
                    len(support_ids) == 6
                ),
                "core_request_ids": (
                    ";".join(support_ids)
                ),
                "market_price_accessed": False,
                "outcome_accessed": False,
            }
        )

    support_map = pd.DataFrame(
        support_records
    )

    summary = (
        plan.groupby(
            [
                "run_period",
                "cycle_role",
                "retrieval_selected",
            ],
            as_index=False,
        )
        .agg(
            request_rows=(
                "request_id",
                "size",
            ),
            request_dates=(
                "run_date",
                "nunique",
            ),
            cycles=(
                "cycle_utc",
                "nunique",
            ),
        )
        .sort_values(
            [
                "run_period",
                "cycle_role",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    checks: list[dict[str, Any]] = []

    expected_training_dates = (
        training_end
        - training_start
    ).days + 1

    expected_request_dates = (
        request_end
        - request_start
    ).days + 1

    expected_core_rows = (
        expected_request_dates
        * len(core_cycles)
    )

    expected_supplementary_rows = (
        expected_request_dates
        * len(supplementary_cycles)
    )

    expected_total_rows = (
        expected_core_rows
        + expected_supplementary_rows
    )

    add_check(
        checks,
        "phase2_complete",
        True,
        (
            phase2.get("phase_status")
            == "PHASE2_COMPLETE"
        ),
        phase2.get("phase_status"),
    )

    add_check(
        checks,
        "phase2_pilot_approved",
        True,
        bool(
            phase2.get(
                "pilot_approved",
                False,
            )
        ),
        phase2.get("status"),
    )

    add_check(
        checks,
        "training_date_count",
        True,
        (
            len(training_dates)
            == expected_training_dates
            == 730
        ),
        len(training_dates),
    )

    add_check(
        checks,
        "request_date_count",
        True,
        (
            len(request_dates)
            == expected_request_dates
            == 732
        ),
        len(request_dates),
    )

    add_check(
        checks,
        "total_request_rows",
        True,
        (
            len(plan)
            == expected_total_rows
            == 2928
        ),
        len(plan),
    )

    add_check(
        checks,
        "selected_core_request_rows",
        True,
        (
            len(core_plan)
            == expected_core_rows
            == 1464
        ),
        len(core_plan),
    )

    add_check(
        checks,
        "supplementary_request_rows",
        True,
        (
            len(supplementary_plan)
            == expected_supplementary_rows
            == 1464
        ),
        len(supplementary_plan),
    )

    add_check(
        checks,
        "request_ids_unique",
        True,
        bool(
            plan["request_id"].is_unique
        ),
        plan["request_id"].nunique(),
    )

    add_check(
        checks,
        "run_initialisations_unique",
        True,
        bool(
            plan["run_init_utc"].is_unique
        ),
        plan["run_init_utc"].nunique(),
    )

    add_check(
        checks,
        "request_urls_unique",
        True,
        bool(
            plan["request_url"].is_unique
        ),
        plan["request_url"].nunique(),
    )

    observed_core_cycles = sorted(
        core_plan["cycle_utc"]
        .astype(int)
        .unique()
        .tolist()
    )

    add_check(
        checks,
        "core_cycles_are_00_and_12",
        True,
        observed_core_cycles == [0, 12],
        observed_core_cycles,
    )

    observed_supplementary_cycles = (
        sorted(
            supplementary_plan[
                "cycle_utc"
            ]
            .astype(int)
            .unique()
            .tolist()
        )
    )

    add_check(
        checks,
        "supplementary_cycles_are_06_and_18",
        True,
        (
            observed_supplementary_cycles
            == [6, 18]
        ),
        observed_supplementary_cycles,
    )

    selected_cycles_per_date = (
        core_plan.groupby(
            "run_date"
        )["cycle_utc"]
        .nunique()
    )

    add_check(
        checks,
        "two_core_cycles_per_request_date",
        True,
        bool(
            selected_cycles_per_date
            .eq(2)
            .all()
        ),
        (
            f"min={selected_cycles_per_date.min()}, "
            f"max={selected_cycles_per_date.max()}"
        ),
    )

    all_cycles_per_date = (
        plan.groupby(
            "run_date"
        )["cycle_utc"]
        .nunique()
    )

    add_check(
        checks,
        "four_documented_cycles_per_request_date",
        True,
        bool(
            all_cycles_per_date
            .eq(4)
            .all()
        ),
        (
            f"min={all_cycles_per_date.min()}, "
            f"max={all_cycles_per_date.max()}"
        ),
    )

    add_check(
        checks,
        "support_map_has_all_training_dates",
        True,
        (
            len(support_map)
            == len(training_dates)
        ),
        len(support_map),
    )

    add_check(
        checks,
        "every_training_date_has_six_core_support_requests",
        True,
        bool(
            support_map[
                "support_complete"
            ].all()
        ),
        (
            support_map[
                "available_core_support_requests"
            ]
            .value_counts()
            .sort_index()
            .to_dict()
        ),
    )

    plan_run_dates = pd.to_datetime(
        plan["run_date"],
        errors="coerce",
    ).dt.date

    add_check(
        checks,
        "no_market_training_initialisations_in_plan",
        True,
        bool(
            (
                plan_run_dates
                < market_training_start
            ).all()
        ),
        plan_run_dates.max(),
    )

    add_check(
        checks,
        "no_validation_initialisations_in_plan",
        True,
        bool(
            (
                plan_run_dates
                < validation_start
            ).all()
        ),
        plan_run_dates.max(),
    )

    add_check(
        checks,
        "network_requests_not_made",
        True,
        bool(
            ~plan[
                "network_request_made"
            ].astype(bool).any()
        ),
        int(
            plan[
                "network_request_made"
            ].astype(bool).sum()
        ),
    )

    add_check(
        checks,
        "market_prices_not_accessed",
        True,
        bool(
            ~plan[
                "market_price_accessed"
            ].astype(bool).any()
        ),
        0,
    )

    add_check(
        checks,
        "outcomes_not_accessed",
        True,
        bool(
            ~plan[
                "outcome_accessed"
            ].astype(bool).any()
        ),
        0,
    )

    add_check(
        checks,
        "supplementary_cycles_not_selected",
        True,
        bool(
            ~supplementary_plan[
                "retrieval_selected"
            ].astype(bool).any()
        ),
        int(
            supplementary_plan[
                "retrieval_selected"
            ].astype(bool).sum()
        ),
    )

    checks_panel = pd.DataFrame(
        checks
    )

    required_failed = checks_panel.loc[
        checks_panel["required"]
        & ~checks_panel["passed"]
    ]

    if not required_failed.empty:
        raise RuntimeError(
            "Phase 3 request-plan checks failed:\n"
            + required_failed.to_string(
                index=False
            )
        )

    for path in [
        PLAN_PATH,
        CORE_PLAN_PATH,
        SUPPLEMENTARY_PLAN_PATH,
        SUPPORT_MAP_PATH,
        SUMMARY_PATH,
        CHECKS_PATH,
    ]:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    plan.to_csv(
        PLAN_PATH,
        index=False,
    )

    core_plan.to_csv(
        CORE_PLAN_PATH,
        index=False,
    )

    supplementary_plan.to_csv(
        SUPPLEMENTARY_PLAN_PATH,
        index=False,
    )

    support_map.to_csv(
        SUPPORT_MAP_PATH,
        index=False,
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
    )

    checks_panel.to_csv(
        CHECKS_PATH,
        index=False,
    )

    output_paths = [
        PLAN_PATH,
        CORE_PLAN_PATH,
        SUPPLEMENTARY_PLAN_PATH,
        SUPPORT_MAP_PATH,
        SUMMARY_PATH,
        CHECKS_PATH,
    ]

    manifest = {
        "phase": 3,
        "status": (
            "TWO_YEAR_REQUEST_PLAN_CERTIFIED"
        ),
        "phase_status": "PHASE3_COMPLETE",

        "weather_only_training_start": (
            training_start.isoformat()
        ),
        "weather_only_training_end": (
            training_end.isoformat()
        ),
        "weather_only_training_dates": (
            len(training_dates)
        ),

        "request_initialisation_start": (
            request_start.isoformat()
        ),
        "request_initialisation_end": (
            request_end.isoformat()
        ),
        "request_initialisation_dates": (
            len(request_dates)
        ),

        "support_buffer_days": int(
            spec[
                "request_support_buffer_days"
            ]
        ),

        "core_cycles_utc": core_cycles,

        "supplementary_cycles_utc": (
            supplementary_cycles
        ),

        "total_planned_requests": len(plan),

        "selected_core_requests": (
            len(core_plan)
        ),

        "supplementary_planned_requests": (
            len(supplementary_plan)
        ),

        "training_target_support_rows": (
            len(support_map)
        ),

        "all_training_targets_supported": bool(
            support_map[
                "support_complete"
            ].all()
        ),

        "network_requests_made": False,

        "market_prices_accessed": False,
        "realised_outcomes_accessed": False,
        "model_fitted": False,
        "model_selected": False,
        "continuous_calibration_selected": False,
        "probability_calibration_selected": False,
        "categorical_scores_calculated": False,
        "trading_strategy_selected": False,
        "trading_returns_calculated": False,

        "weather_plus_market_training_start": (
            spec[
                "weather_plus_market_training_start"
            ]
        ),

        "weather_plus_market_training_end": (
            spec[
                "weather_plus_market_training_end"
            ]
        ),

        "out_of_sample_validation_start": (
            spec[
                "out_of_sample_validation_start"
            ]
        ),

        "out_of_sample_validation_end": (
            spec[
                "out_of_sample_validation_end"
            ]
        ),

        "future_july_extension_planned": (
            bool(
                spec[
                    "future_july_extension_planned"
                ]
            )
        ),

        "future_july_extension_included_now": (
            False
        ),

        "bulk_retrieval_policy": (
            "Retrieve only the 00 and 12 UTC "
            "core requests in the next phase."
        ),

        "supplementary_cycle_policy": (
            "The 06 and 18 UTC requests are "
            "documented but are not selected "
            "for bulk retrieval."
        ),

        "downstream_target_filter_required": (
            True
        ),

        "phase2_manifest": str(
            PHASE2_MANIFEST_PATH.relative_to(
                ROOT
            )
        ),

        "phase2_manifest_sha256": sha256(
            PHASE2_MANIFEST_PATH
        ),

        "specification": str(
            SPEC_PATH.relative_to(ROOT)
        ),

        "specification_sha256": sha256(
            SPEC_PATH
        ),

        "output_paths": [
            str(path.relative_to(ROOT))
            for path in output_paths
        ],

        "output_hashes": {
            str(path.relative_to(ROOT)): (
                sha256(path)
            )
            for path in output_paths
        },

        "required_integrity_checks": int(
            checks_panel["required"].sum()
        ),

        "required_integrity_checks_passed": (
            int(
                checks_panel.loc[
                    checks_panel["required"],
                    "passed",
                ].sum()
            )
        ),

        "next_stage": (
            "Retrieve and certify the selected "
            "00 and 12 UTC historical requests."
        ),
    }

    MANIFEST_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
    print("PHASE 3 TWO-YEAR REQUEST PLAN")
    print("=" * 76)

    print(
        "Status:",
        manifest["status"],
    )

    print(
        "Weather only training dates:",
        manifest[
            "weather_only_training_dates"
        ],
    )

    print(
        "Request initialisation dates:",
        manifest[
            "request_initialisation_dates"
        ],
    )

    print(
        "Selected core requests:",
        manifest[
            "selected_core_requests"
        ],
    )

    print(
        "Supplementary requests:",
        manifest[
            "supplementary_planned_requests"
        ],
    )

    print(
        "Total plan rows:",
        manifest[
            "total_planned_requests"
        ],
    )

    print(
        "Training targets supported:",
        manifest[
            "training_target_support_rows"
        ],
    )

    print(
        "All target support complete:",
        manifest[
            "all_training_targets_supported"
        ],
    )

    print()
    print("Request-plan summary:")

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print("Integrity checks:")

    print(
        checks_panel.to_string(
            index=False
        )
    )

    print()
    print(
        "PHASE 3 REQUEST PLAN: CERTIFIED"
    )


if __name__ == "__main__":
    main()
