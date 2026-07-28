from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

CORE_ENGINE_PATH = (
    ROOT
    / "tools/v2/retrieve_two_year_core_requests.py"
)

NETWORK_SPEC_PATH = (
    ROOT
    / "config/v2/two_year_retrieval_spec.json"
)

REPAIR_SPEC_PATH = (
    ROOT
    / "config/v2/two_year_repair_spec.json"
)

REPAIR_PLAN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03a_two_year_repair_request_plan.csv"
)

CORE_LEDGER_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03_two_year_core_retrieval_ledger.csv"
)

REPAIR_LEDGER_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03b_two_year_repair_retrieval_ledger.csv"
)

REPAIR_DAILY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03b_two_year_repair_daily_availability.csv"
)

REPAIR_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03b_two_year_repair_retrieval_summary.csv"
)

RUN_INVENTORY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03b_two_year_complete_run_inventory.csv"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "03b_two_year_repair_integrity_checks.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "03b_two_year_repair_retrieval_manifest.json"
)

RAW_CACHE_ROOT = (
    ROOT
    / "data/raw/v2/open_meteo_single_runs_two_year"
)


def load_core_module():
    specification = importlib.util.spec_from_file_location(
        "phase4_core_retrieval",
        CORE_ENGINE_PATH,
    )

    if specification is None or specification.loader is None:
        raise RuntimeError(
            "Unable to load the Phase 4 core retrieval module."
        )

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    return module


CORE = load_core_module()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(
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


def classify_failure(value: object) -> str:
    text = str(value).lower()

    if "requested model run is not available" in text:
        return "run_unavailable"

    if "no complete hong kong local day" in text:
        return "no_complete_local_day"

    if "missing hourly" in text:
        return "missing_hourly_object"

    if "time and temperature lengths differ" in text:
        return "malformed_hourly_response"

    if "http 400" in text:
        return "other_http_400"

    if "http 429" in text or "rate" in text:
        return "rate_limit"

    if "timeout" in text:
        return "timeout"

    if "urlerror" in text or "connection" in text:
        return "network_error"

    return "other"


def normalise_cache_path(value: object) -> Path:
    relative = Path(str(value))

    if relative.suffix == ".json":
        relative = relative.with_suffix(".json.gz")

    path = ROOT / relative

    try:
        path.relative_to(RAW_CACHE_ROOT)
    except ValueError as exc:
        raise RuntimeError(
            "Repair cache path lies outside the approved directory: "
            f"{path}"
        ) from exc

    return path


def validate_relaxed_payload(
    payload: dict[str, Any],
    timezone_name: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if payload.get("error"):
        raise ValueError(
            "API error: " + str(payload.get("reason"))
        )

    hourly = payload.get("hourly")

    if not isinstance(hourly, dict):
        raise ValueError("Missing hourly response object.")

    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")

    if not isinstance(times, list):
        raise ValueError("Missing hourly time list.")

    if not isinstance(temperatures, list):
        raise ValueError("Missing hourly temperature list.")

    if len(times) != len(temperatures):
        raise ValueError(
            "Time and temperature lengths differ."
        )

    if len(times) == 0:
        raise ValueError("The hourly response is empty.")

    returned_timezone = payload.get("timezone")

    if returned_timezone != timezone_name:
        raise ValueError(
            "Unexpected returned timezone: "
            f"{returned_timezone!r}"
        )

    parsed_times = pd.to_datetime(
        pd.Series(times),
        errors="raise",
    )

    numeric_temperatures = pd.to_numeric(
        pd.Series(temperatures),
        errors="coerce",
    )

    hourly_panel = pd.DataFrame(
        {
            "valid_time_hkt": parsed_times,
            "temperature_2m_c": numeric_temperatures,
        }
    )

    hourly_panel["target_local_date"] = (
        hourly_panel["valid_time_hkt"]
        .dt.date
        .astype(str)
    )

    hourly_panel["local_hour"] = (
        hourly_panel["valid_time_hkt"].dt.hour
    )

    daily = (
        hourly_panel.groupby(
            "target_local_date",
            as_index=False,
        )
        .agg(
            hourly_rows=("valid_time_hkt", "size"),
            unique_local_hours=("local_hour", "nunique"),
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

    daily["complete_local_day"] = (
        daily["hourly_rows"].eq(24)
        & daily["unique_local_hours"].eq(24)
        & daily["nonmissing_temperature_rows"].eq(24)
    )

    complete_dates = daily.loc[
        daily["complete_local_day"],
        "target_local_date",
    ].tolist()

    if not complete_dates:
        raise ValueError(
            "No complete Hong Kong local day is available."
        )

    metrics = {
        "hourly_rows": int(len(hourly_panel)),
        "nonmissing_temperature_rows": int(
            hourly_panel["temperature_2m_c"]
            .notna()
            .sum()
        ),
        "missing_temperature_rows": int(
            hourly_panel["temperature_2m_c"]
            .isna()
            .sum()
        ),
        "daily_rows": int(len(daily)),
        "complete_local_day_count": int(
            daily["complete_local_day"].sum()
        ),
        "first_complete_local_date": str(
            complete_dates[0]
        ),
        "last_complete_local_date": str(
            complete_dates[-1]
        ),
        "first_time": str(times[0]),
        "last_time": str(times[-1]),
        "returned_timezone": returned_timezone,
        "returned_latitude": payload.get("latitude"),
        "returned_longitude": payload.get("longitude"),
        "returned_elevation": payload.get("elevation"),
    }

    return metrics, daily


def read_cached_response(
    path: Path,
    timezone_name: str,
) -> tuple[bytes, dict[str, Any], pd.DataFrame]:
    compressed = path.read_bytes()
    body = gzip.decompress(compressed)

    payload = json.loads(
        body.decode("utf-8")
    )

    metrics, daily = validate_relaxed_payload(
        payload,
        timezone_name,
    )

    return body, metrics, daily


def load_inputs():
    network_spec = json.loads(
        NETWORK_SPEC_PATH.read_text(encoding="utf-8")
    )

    repair_spec = json.loads(
        REPAIR_SPEC_PATH.read_text(encoding="utf-8")
    )

    plan = pd.read_csv(REPAIR_PLAN_PATH)
    core_ledger = pd.read_csv(CORE_LEDGER_PATH)

    required_plan_columns = {
        "request_id",
        "run_init_utc",
        "cycle_utc",
        "request_url",
        "cache_path",
        "repair_role",
    }

    missing = sorted(
        required_plan_columns - set(plan.columns)
    )

    if missing:
        raise RuntimeError(
            "Repair plan is missing columns: "
            + ", ".join(missing)
        )

    if len(plan) != 288:
        raise RuntimeError(
            f"Expected 288 repair requests, found {len(plan)}."
        )

    if not plan["request_id"].astype(str).is_unique:
        raise RuntimeError(
            "Repair request identifiers are not unique."
        )

    role_counts = (
        plan["repair_role"]
        .value_counts()
        .to_dict()
    )

    expected_roles = {
        "core_partial_response_retry": 64,
        "supplementary_cycle_candidate": 224,
    }

    if role_counts != expected_roles:
        raise RuntimeError(
            "Unexpected repair-role counts.\n"
            f"Expected: {expected_roles}\n"
            f"Actual:   {role_counts}"
        )

    return network_spec, repair_spec, plan, core_ledger


def run_retrieval(
    network_spec: dict[str, Any],
    plan: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    timezone_name = str(network_spec["timezone"])
    checkpoint_every = int(
        network_spec.get(
            "checkpoint_every_requests",
            25,
        )
    )

    records: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []

    for position, row in enumerate(
        plan.itertuples(index=False),
        start=1,
    ):
        path = normalise_cache_path(row.cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        body: bytes | None = None
        metrics: dict[str, Any] = {}
        daily = pd.DataFrame()

        status = ""
        attempts = 0
        error = ""
        failure_type = ""

        cache_reused = False
        network_retrieved = False

        if path.exists():
            try:
                body, metrics, daily = read_cached_response(
                    path,
                    timezone_name,
                )

                status = "CACHED_VALID"
                cache_reused = True

            except Exception as exc:
                print(
                    "Removing invalid repair cache:",
                    path,
                    repr(exc),
                    flush=True,
                )

                path.unlink(missing_ok=True)

        if body is None:
            try:
                body, attempts = CORE.fetch(
                    str(row.request_url),
                    network_spec,
                )

                payload = json.loads(
                    body.decode("utf-8")
                )

                metrics, daily = validate_relaxed_payload(
                    payload,
                    timezone_name,
                )

                compressed = gzip.compress(
                    body,
                    compresslevel=9,
                    mtime=0,
                )

                atomic_write(path, compressed)

                status = "DOWNLOADED_VALID"
                network_retrieved = True

            except Exception as exc:
                status = "FAILED"
                error = f"{type(exc).__name__}: {exc}"
                failure_type = classify_failure(error)

        response_hash = (
            hashlib.sha256(body).hexdigest()
            if body is not None
            else None
        )

        compressed_hash = (
            sha256_file(path)
            if path.exists()
            else None
        )

        record = {
            "repair_order": getattr(
                row,
                "repair_order",
                position,
            ),
            "request_id": str(row.request_id),
            "run_date": getattr(row, "run_date", None),
            "run_init_utc": str(row.run_init_utc),
            "cycle_utc": int(row.cycle_utc),
            "repair_role": str(row.repair_role),
            "request_url": str(row.request_url),
            "cache_path": str(
                path.relative_to(ROOT)
            ),
            "status": status,
            "failure_type": failure_type,
            "attempts": attempts,
            "network_retrieved": network_retrieved,
            "cache_reused": cache_reused,
            "response_sha256": response_hash,
            "compressed_file_sha256": compressed_hash,
            "compressed_file_bytes": (
                path.stat().st_size
                if path.exists()
                else 0
            ),
            "hourly_rows": metrics.get(
                "hourly_rows",
                0,
            ),
            "nonmissing_temperature_rows": metrics.get(
                "nonmissing_temperature_rows",
                0,
            ),
            "missing_temperature_rows": metrics.get(
                "missing_temperature_rows",
                0,
            ),
            "daily_rows": metrics.get(
                "daily_rows",
                0,
            ),
            "complete_local_day_count": metrics.get(
                "complete_local_day_count",
                0,
            ),
            "first_complete_local_date": metrics.get(
                "first_complete_local_date"
            ),
            "last_complete_local_date": metrics.get(
                "last_complete_local_date"
            ),
            "returned_timezone": metrics.get(
                "returned_timezone"
            ),
            "error": error,
            "market_price_accessed": False,
            "outcome_accessed": False,
        }

        records.append(record)

        if status in {
            "CACHED_VALID",
            "DOWNLOADED_VALID",
        }:
            daily = daily.copy()

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
                "repair_role",
                str(row.repair_role),
            )

            daily["response_sha256"] = response_hash
            daily["market_price_accessed"] = False
            daily["outcome_accessed"] = False

            daily_frames.append(daily)

        if (
            position % checkpoint_every == 0
            or position == len(plan)
        ):
            checkpoint = pd.DataFrame(records)
            write_csv(
                checkpoint,
                REPAIR_LEDGER_PATH,
            )

            counts = (
                checkpoint["status"]
                .value_counts()
                .to_dict()
            )

            print(
                f"[{position}/{len(plan)}] {counts}",
                flush=True,
            )

    ledger = pd.DataFrame(records)

    if daily_frames:
        daily_panel = pd.concat(
            daily_frames,
            ignore_index=True,
        )
    else:
        daily_panel = pd.DataFrame()

    return ledger, daily_panel


def build_complete_inventory(
    core_ledger: pd.DataFrame,
    repair_ledger: pd.DataFrame,
) -> pd.DataFrame:
    core_success = core_ledger.loc[
        core_ledger["status"].isin(
            ["DOWNLOADED_VALID", "CACHED_VALID"]
        )
    ].copy()

    if len(core_success) != 1299:
        raise RuntimeError(
            "Expected 1299 successful original core responses, "
            f"found {len(core_success)}."
        )

    core_success["inventory_source"] = (
        "original_core_retrieval"
    )

    core_success["repair_role"] = (
        "original_core_cycle"
    )

    repair_success = repair_ledger.loc[
        repair_ledger["status"].isin(
            ["DOWNLOADED_VALID", "CACHED_VALID"]
        )
    ].copy()

    repair_success["inventory_source"] = (
        "repair_retrieval"
    )

    common_columns = [
        "request_id",
        "run_date",
        "run_init_utc",
        "cycle_utc",
        "repair_role",
        "inventory_source",
        "cache_path",
        "status",
        "response_sha256",
        "compressed_file_sha256",
        "compressed_file_bytes",
        "returned_timezone",
        "market_price_accessed",
        "outcome_accessed",
    ]

    for column in common_columns:
        if column not in core_success.columns:
            core_success[column] = None

        if column not in repair_success.columns:
            repair_success[column] = None

    inventory = pd.concat(
        [
            core_success[common_columns],
            repair_success[common_columns],
        ],
        ignore_index=True,
    )

    inventory = (
        inventory.sort_values(
            [
                "run_init_utc",
                "cycle_utc",
                "inventory_source",
            ],
            kind="stable",
        )
        .drop_duplicates(
            "request_id",
            keep="last",
        )
        .reset_index(drop=True)
    )

    if not inventory["request_id"].astype(str).is_unique:
        raise RuntimeError(
            "The complete run inventory is not unique."
        )

    return inventory


def certify() -> None:
    network_spec, repair_spec, plan, core_ledger = load_inputs()

    ledger, daily_panel = run_retrieval(
        network_spec,
        plan,
    )

    successful = ledger["status"].isin(
        ["DOWNLOADED_VALID", "CACHED_VALID"]
    )

    failed = ledger["status"].eq("FAILED")

    accounted = successful | failed

    if not accounted.all():
        raise RuntimeError(
            "At least one repair request is not accounted for."
        )

    if ledger["request_id"].astype(str).duplicated().any():
        raise RuntimeError(
            "The repair ledger contains duplicate request IDs."
        )

    failed_without_type = ledger.loc[
        failed
        & ledger["failure_type"]
        .astype(str)
        .str.strip()
        .eq("")
    ]

    if not failed_without_type.empty:
        raise RuntimeError(
            "A failed repair request has no failure classification."
        )

    successful_rows = ledger.loc[successful]

    if (
        successful_rows[
            "complete_local_day_count"
        ]
        .astype(int)
        .lt(1)
        .any()
    ):
        raise RuntimeError(
            "A retained repair response has no complete local day."
        )

    inventory = build_complete_inventory(
        core_ledger,
        ledger,
    )

    summary = (
        ledger.groupby(
            [
                "repair_role",
                "status",
                "failure_type",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            requests=("request_id", "size"),
            complete_local_days=(
                "complete_local_day_count",
                "sum",
            ),
            downloaded=("network_retrieved", "sum"),
            cache_reused=("cache_reused", "sum"),
        )
    )

    checks = pd.DataFrame(
        [
            {
                "check": "repair_request_count",
                "required": True,
                "passed": len(ledger) == 288,
                "detail": len(ledger),
            },
            {
                "check": "repair_request_ids_unique",
                "required": True,
                "passed": ledger[
                    "request_id"
                ].astype(str).is_unique,
                "detail": ledger[
                    "request_id"
                ].nunique(),
            },
            {
                "check": "all_repair_requests_accounted",
                "required": True,
                "passed": accounted.all(),
                "detail": int(accounted.sum()),
            },
            {
                "check": "successful_responses_have_complete_day",
                "required": True,
                "passed": successful_rows[
                    "complete_local_day_count"
                ].astype(int).ge(1).all(),
                "detail": int(successful.sum()),
            },
            {
                "check": "failed_responses_classified",
                "required": True,
                "passed": failed_without_type.empty,
                "detail": int(failed.sum()),
            },
            {
                "check": "original_core_success_count",
                "required": True,
                "passed": (
                    core_ledger["status"]
                    .isin(
                        [
                            "DOWNLOADED_VALID",
                            "CACHED_VALID",
                        ]
                    )
                    .sum()
                    == 1299
                ),
                "detail": int(
                    core_ledger["status"]
                    .isin(
                        [
                            "DOWNLOADED_VALID",
                            "CACHED_VALID",
                        ]
                    )
                    .sum()
                ),
            },
            {
                "check": "complete_inventory_unique",
                "required": True,
                "passed": inventory[
                    "request_id"
                ].astype(str).is_unique,
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
        ]
    )

    required_failed = checks.loc[
        checks["required"]
        & ~checks["passed"]
    ]

    if not required_failed.empty:
        raise RuntimeError(
            "Required Phase 4D2 checks failed:\n"
            + required_failed.to_string(index=False)
        )

    write_csv(
        ledger,
        REPAIR_LEDGER_PATH,
    )

    write_csv(
        daily_panel,
        REPAIR_DAILY_PATH,
    )

    write_csv(
        summary,
        REPAIR_SUMMARY_PATH,
    )

    write_csv(
        inventory,
        RUN_INVENTORY_PATH,
    )

    write_csv(
        checks,
        INTEGRITY_PATH,
    )

    output_paths = [
        REPAIR_LEDGER_PATH,
        REPAIR_DAILY_PATH,
        REPAIR_SUMMARY_PATH,
        RUN_INVENTORY_PATH,
        INTEGRITY_PATH,
    ]

    failure_counts = {
        str(key): int(value)
        for key, value in (
            ledger.loc[failed, "failure_type"]
            .value_counts()
            .items()
        )
    }

    success_role_counts = {
        str(key): int(value)
        for key, value in (
            ledger.loc[
                successful,
                "repair_role",
            ]
            .value_counts()
            .items()
        )
    }

    manifest = {
        "phase": 4,
        "subphase": "4D2",
        "phase_status": "PHASE4_REPAIR_RETRIEVAL_COMPLETE",
        "status": "TWO_YEAR_REPAIR_REQUESTS_ACCOUNTED",
        "created_utc": utc_now(),
        "planned_repair_requests": 288,
        "successful_repair_requests": int(
            successful.sum()
        ),
        "failed_repair_requests": int(
            failed.sum()
        ),
        "failure_type_counts": failure_counts,
        "successful_repair_role_counts": success_role_counts,
        "original_successful_core_requests": 1299,
        "complete_run_inventory_rows": int(
            len(inventory)
        ),
        "complete_run_inventory_unique": True,
        "successful_responses_require_complete_local_day": True,
        "unavailable_runs_permitted_when_recorded": True,
        "all_repair_requests_accounted": True,
        "raw_cache_committed_to_git": False,
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
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in output_paths
        },
        "next_stage": (
            "Construct target-date and decision-rule support "
            "from the complete historical run inventory."
        ),
    }

    write_json(
        MANIFEST_PATH,
        manifest,
    )

    print()
    print("=" * 78)
    print("PHASE 4D2 REPAIR RETRIEVAL COMPLETE")
    print("=" * 78)
    print("Planned repair requests:", len(ledger))
    print(
        "Successful repair requests:",
        int(successful.sum()),
    )
    print(
        "Failed repair requests:",
        int(failed.sum()),
    )
    print(
        "Failure types:",
        failure_counts,
    )
    print(
        "Successful repair roles:",
        success_role_counts,
    )
    print(
        "Complete run inventory:",
        len(inventory),
    )
    print("Market prices accessed: False")
    print("Outcomes accessed: False")
    print("Model fitted or selected: False")


def preflight() -> None:
    _, repair_spec, plan, core_ledger = load_inputs()

    assert repair_spec["total_repair_requests"] == 288
    assert len(plan) == 288

    assert (
        plan["repair_role"]
        .eq("core_partial_response_retry")
        .sum()
        == 64
    )

    assert (
        plan["repair_role"]
        .eq("supplementary_cycle_candidate")
        .sum()
        == 224
    )

    assert (
        core_ledger["status"]
        .isin(
            ["DOWNLOADED_VALID", "CACHED_VALID"]
        )
        .sum()
        == 1299
    )

    print("Repair-plan rows:", len(plan))
    print("Relaxed core retries: 64")
    print("Supplementary requests: 224")
    print("Existing successful core responses: 1299")
    print("Network requests made: False")
    print("PHASE 4D2 PREFLIGHT: PASSED")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check-plan",
        action="store_true",
    )

    arguments = parser.parse_args()

    if arguments.check_plan:
        preflight()
        return

    certify()


if __name__ == "__main__":
    main()
