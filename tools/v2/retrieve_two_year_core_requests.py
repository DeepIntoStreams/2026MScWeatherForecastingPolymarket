from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = ROOT / "config/v2/two_year_retrieval_spec.json"
PHASE3_MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/02_two_year_request_plan_manifest.json"
)
PLAN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/02_two_year_core_request_plan.csv"
)

RAW_CACHE_ROOT = (
    ROOT
    / "data/raw/v2/open_meteo_single_runs_two_year"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/03_two_year_core_retrieval_manifest.json"
)

LEDGER_PATH = (
    ROOT
    / "outputs/v2/diagnostics/03_two_year_core_retrieval_ledger.csv"
)

HOURLY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/03_two_year_hourly_panel.csv.gz"
)

DAILY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/03_two_year_daily_run_summary.csv.gz"
)

SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/03_two_year_retrieval_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/03_two_year_retrieval_integrity_checks.csv"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1"})
    )


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(
        path,
        (
            json.dumps(payload, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8"),
    )


def write_csv(panel: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")

    if path.suffix == ".gz":
        panel.to_csv(
            temporary,
            index=False,
            compression={
                "method": "gzip",
                "compresslevel": 9,
                "mtime": 0,
            },
        )
    else:
        panel.to_csv(temporary, index=False)

    os.replace(temporary, path)


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    phase3 = json.loads(
        PHASE3_MANIFEST_PATH.read_text(encoding="utf-8")
    )

    plan = pd.read_csv(PLAN_PATH)

    if "retrieval_selected" in plan.columns:
        plan = plan.loc[
            as_bool(plan["retrieval_selected"])
        ].copy()

    required_columns = {
        "request_id",
        "run_init_utc",
        "cycle_utc",
        "request_url",
        "cache_path",
    }

    missing = sorted(required_columns - set(plan.columns))

    if missing:
        raise RuntimeError(
            "Request plan is missing columns: "
            + ", ".join(missing)
        )

    plan["cycle_utc"] = pd.to_numeric(
        plan["cycle_utc"],
        errors="raise",
    ).astype(int)

    plan = (
        plan.sort_values(
            ["run_init_utc", "cycle_utc"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    return spec, phase3, plan


def validate_plan(
    spec: dict[str, Any],
    phase3: dict[str, Any],
    plan: pd.DataFrame,
) -> None:
    assert phase3["phase_status"] == "PHASE3_COMPLETE"
    assert phase3["status"] == "TWO_YEAR_REQUEST_PLAN_CERTIFIED"
    assert spec["phase"] == 4
    assert spec["status"] == "CORE_RETRIEVAL_DECLARED"

    expected_requests = int(spec["expected_requests"])

    if len(plan) != expected_requests:
        raise RuntimeError(
            f"Expected {expected_requests} requests, "
            f"found {len(plan)}."
        )

    if not plan["request_id"].astype(str).is_unique:
        raise RuntimeError("Request identifiers are not unique.")

    observed_cycles = sorted(plan["cycle_utc"].unique().tolist())

    if observed_cycles != [0, 12]:
        raise RuntimeError(
            f"Unexpected selected cycles: {observed_cycles}"
        )

    if plan["request_url"].isna().any():
        raise RuntimeError("A request URL is missing.")

    if plan["cache_path"].isna().any():
        raise RuntimeError("A cache path is missing.")


def cache_path(relative_value: str) -> Path:
    relative = Path(str(relative_value))

    if relative.suffix == ".json":
        relative = relative.with_suffix(".json.gz")

    path = ROOT / relative

    try:
        path.relative_to(RAW_CACHE_ROOT)
    except ValueError as exc:
        raise RuntimeError(
            f"Cache path is outside the approved directory: {path}"
        ) from exc

    return path


def validate_payload(
    payload: dict[str, Any],
    expected_hours: int,
    timezone_name: str,
) -> dict[str, Any]:
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
        raise ValueError("Missing temperature list.")

    if len(times) != expected_hours:
        raise ValueError(
            f"Expected {expected_hours} hours, found {len(times)}."
        )

    if len(temperatures) != expected_hours:
        raise ValueError(
            "Time and temperature lengths differ."
        )

    numeric = pd.to_numeric(
        pd.Series(temperatures),
        errors="coerce",
    )

    if numeric.isna().any():
        raise ValueError("Temperature response contains missing values.")

    parsed_times = pd.to_datetime(times, errors="raise")

    if parsed_times.duplicated().any():
        raise ValueError("Duplicate valid times in response.")

    returned_timezone = payload.get("timezone")

    if returned_timezone != timezone_name:
        raise ValueError(
            "Unexpected timezone: "
            f"{returned_timezone!r}"
        )

    return {
        "hourly_rows": len(times),
        "first_time": str(times[0]),
        "last_time": str(times[-1]),
        "returned_timezone": returned_timezone,
        "returned_latitude": payload.get("latitude"),
        "returned_longitude": payload.get("longitude"),
        "returned_elevation": payload.get("elevation"),
    }


def read_cache(
    path: Path,
    expected_hours: int,
    timezone_name: str,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    compressed = path.read_bytes()
    body = gzip.decompress(compressed)
    payload = json.loads(body.decode("utf-8"))

    metrics = validate_payload(
        payload,
        expected_hours,
        timezone_name,
    )

    return body, payload, metrics


def fetch(
    url: str,
    spec: dict[str, Any],
) -> tuple[bytes, int]:
    maximum_attempts = int(spec["maximum_attempts"])
    timeout_seconds = int(spec["request_timeout_seconds"])
    base_delay = float(spec["base_retry_delay_seconds"])
    pacing = float(spec["minimum_seconds_between_requests"])

    retryable_statuses = {
        int(value)
        for value in spec["retryable_http_statuses"]
    }

    last_error: Exception | None = None

    for attempt in range(1, maximum_attempts + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": str(spec["user_agent"]),
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                body = response.read()
                status = int(response.getcode())

            if status != 200:
                raise RuntimeError(
                    f"Unexpected HTTP status {status}."
                )

            time.sleep(pacing)
            return body, attempt

        except urllib.error.HTTPError as exc:
            last_error = exc

            if exc.code not in retryable_statuses:
                detail = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )[:500]

                raise RuntimeError(
                    f"HTTP {exc.code}: {detail}"
                ) from exc

        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
        ) as exc:
            last_error = exc

        if attempt < maximum_attempts:
            delay = base_delay * (2 ** (attempt - 1))

            print(
                f"Retry {attempt}/{maximum_attempts} "
                f"after {delay:.1f} seconds: {last_error!r}",
                flush=True,
            )

            time.sleep(delay)

    raise RuntimeError(
        "Request failed after all attempts: "
        f"{last_error!r}"
    )


def retrieve(
    spec: dict[str, Any],
    plan: pd.DataFrame,
) -> pd.DataFrame:
    expected_hours = int(spec["expected_hours_per_request"])
    timezone_name = str(spec["timezone"])
    checkpoint_every = int(spec["checkpoint_every_requests"])

    records: list[dict[str, Any]] = []

    for position, row in enumerate(
        plan.itertuples(index=False),
        start=1,
    ):
        path = cache_path(str(row.cache_path))
        path.parent.mkdir(parents=True, exist_ok=True)

        body: bytes | None = None
        metrics: dict[str, Any] = {}
        status = ""
        attempts = 0
        error = ""
        network_retrieved = False
        cache_reused = False

        if path.exists():
            try:
                body, _, metrics = read_cache(
                    path,
                    expected_hours,
                    timezone_name,
                )

                status = "CACHED_VALID"
                cache_reused = True

            except Exception as exc:
                print(
                    "Removing invalid cache:",
                    path,
                    repr(exc),
                    flush=True,
                )

                path.unlink(missing_ok=True)

        if body is None:
            try:
                body, attempts = fetch(
                    str(row.request_url),
                    spec,
                )

                payload = json.loads(body.decode("utf-8"))

                metrics = validate_payload(
                    payload,
                    expected_hours,
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

        run_date = getattr(row, "run_date", None)
        cycle_role = getattr(row, "cycle_role", "core")
        model = getattr(row, "model", spec.get("model"))

        records.append(
            {
                "request_id": str(row.request_id),
                "run_date": run_date,
                "run_init_utc": str(row.run_init_utc),
                "cycle_utc": int(row.cycle_utc),
                "cycle_role": cycle_role,
                "model": model,
                "request_url": str(row.request_url),
                "cache_path": str(path.relative_to(ROOT)),
                "status": status,
                "attempts": attempts,
                "network_retrieved": network_retrieved,
                "cache_reused": cache_reused,
                "response_sha256": (
                    sha256_bytes(body)
                    if body is not None
                    else None
                ),
                "compressed_file_sha256": (
                    sha256_file(path)
                    if path.exists()
                    else None
                ),
                "compressed_file_bytes": (
                    path.stat().st_size
                    if path.exists()
                    else 0
                ),
                "hourly_rows": metrics.get("hourly_rows", 0),
                "first_time": metrics.get("first_time"),
                "last_time": metrics.get("last_time"),
                "returned_timezone": metrics.get(
                    "returned_timezone"
                ),
                "returned_latitude": metrics.get(
                    "returned_latitude"
                ),
                "returned_longitude": metrics.get(
                    "returned_longitude"
                ),
                "returned_elevation": metrics.get(
                    "returned_elevation"
                ),
                "error": error,
                "market_price_accessed": False,
                "outcome_accessed": False,
            }
        )

        if (
            position % checkpoint_every == 0
            or position == len(plan)
        ):
            checkpoint = pd.DataFrame(records)
            write_csv(checkpoint, LEDGER_PATH)

            status_counts = (
                checkpoint["status"]
                .value_counts()
                .to_dict()
            )

            print(
                f"[{position}/{len(plan)}] {status_counts}",
                flush=True,
            )

    return pd.DataFrame(records)


def build_hourly(
    ledger: pd.DataFrame,
    spec: dict[str, Any],
) -> pd.DataFrame:
    timezone_name = str(spec["timezone"])
    local_timezone = ZoneInfo(timezone_name)
    frames: list[pd.DataFrame] = []

    for position, row in enumerate(
        ledger.itertuples(index=False),
        start=1,
    ):
        path = ROOT / str(row.cache_path)

        body = gzip.decompress(path.read_bytes())
        payload = json.loads(body.decode("utf-8"))

        times = payload["hourly"]["time"]

        temperatures = pd.to_numeric(
            pd.Series(
                payload["hourly"]["temperature_2m"]
            ),
            errors="raise",
        )

        local_index = pd.DatetimeIndex(
            pd.to_datetime(times, errors="raise")
        )

        if local_index.tz is None:
            local_index = local_index.tz_localize(
                local_timezone
            )
        else:
            local_index = local_index.tz_convert(
                local_timezone
            )

        utc_index = local_index.tz_convert("UTC")

        run_init = pd.Timestamp(row.run_init_utc)

        if run_init.tzinfo is None:
            run_init = run_init.tz_localize("UTC")
        else:
            run_init = run_init.tz_convert("UTC")

        lead_hours = (
            (utc_index - run_init)
            / pd.Timedelta(hours=1)
        ).astype(int)

        frame = pd.DataFrame(
            {
                "request_id": row.request_id,
                "run_date": row.run_date,
                "run_init_utc": row.run_init_utc,
                "cycle_utc": int(row.cycle_utc),
                "cycle_role": row.cycle_role,
                "model": row.model,
                "valid_time_hkt": [
                    value.isoformat()
                    for value in local_index.to_pydatetime()
                ],
                "valid_time_utc": [
                    value.isoformat()
                    for value in utc_index.to_pydatetime()
                ],
                "target_local_date": [
                    value.date().isoformat()
                    for value in local_index.to_pydatetime()
                ],
                "local_hour": local_index.hour,
                "lead_hours": lead_hours,
                "temperature_2m_c": temperatures.to_numpy(),
                "source_response_sha256": row.response_sha256,
                "returned_timezone": row.returned_timezone,
                "market_price_accessed": False,
                "outcome_accessed": False,
            }
        )

        frames.append(frame)

        if position % 100 == 0 or position == len(ledger):
            print(
                f"Hourly construction: {position}/{len(ledger)}",
                flush=True,
            )

    return pd.concat(frames, ignore_index=True)


def certify(
    spec: dict[str, Any],
    phase3: dict[str, Any],
    ledger: pd.DataFrame,
) -> None:
    failed = ledger.loc[ledger["status"].eq("FAILED")].copy()

    if not failed.empty:
        manifest = {
            "phase": 4,
            "phase_status": "PHASE4_INCOMPLETE",
            "status": "CORE_RETRIEVAL_INCOMPLETE",
            "expected_requests": int(spec["expected_requests"]),
            "successful_requests": int(len(ledger) - len(failed)),
            "failed_requests": int(len(failed)),
            "failed_request_ids": failed[
                "request_id"
            ].astype(str).tolist(),
            "ledger": str(LEDGER_PATH.relative_to(ROOT)),
            "next_action": (
                "Rerun the same retrieval command. "
                "Valid cache files will be reused."
            ),
        }

        write_json(MANIFEST_PATH, manifest)

        print(
            failed[
                ["request_id", "run_init_utc", "error"]
            ].to_string(index=False)
        )

        raise RuntimeError(
            f"{len(failed)} requests remain unsuccessful."
        )

    hourly = build_hourly(ledger, spec)

    daily = (
        hourly.groupby(
            [
                "request_id",
                "run_date",
                "run_init_utc",
                "cycle_utc",
                "cycle_role",
                "model",
                "target_local_date",
                "source_response_sha256",
            ],
            as_index=False,
        )
        .agg(
            local_hour_count=("valid_time_hkt", "size"),
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
            minimum_lead_hours=("lead_hours", "min"),
            maximum_lead_hours=("lead_hours", "max"),
        )
        .sort_values(
            ["run_init_utc", "target_local_date"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    daily["complete_local_day"] = (
        daily["local_hour_count"].eq(24)
        & daily["nonmissing_temperature_rows"].eq(24)
    )

    daily["market_price_accessed"] = False
    daily["outcome_accessed"] = False

    expected_requests = int(spec["expected_requests"])
    expected_hourly_rows = int(spec["expected_hourly_rows"])
    expected_daily_rows = (
        expected_requests
        * int(spec["expected_daily_rows_per_request"])
    )
    expected_complete_days = (
        expected_requests
        * int(spec["expected_complete_local_days_per_request"])
    )

    hourly_counts = hourly.groupby("request_id").size()
    daily_counts = daily.groupby("request_id").size()

    complete_counts = (
        daily.loc[daily["complete_local_day"]]
        .groupby("request_id")
        .size()
        .reindex(
            ledger["request_id"],
            fill_value=0,
        )
    )

    checks = pd.DataFrame(
        [
            {
                "check": "phase3_complete",
                "required": True,
                "passed": (
                    phase3["phase_status"] == "PHASE3_COMPLETE"
                ),
                "detail": phase3["phase_status"],
            },
            {
                "check": "request_count",
                "required": True,
                "passed": len(ledger) == expected_requests,
                "detail": len(ledger),
            },
            {
                "check": "all_requests_valid",
                "required": True,
                "passed": ledger["status"].isin(
                    ["DOWNLOADED_VALID", "CACHED_VALID"]
                ).all(),
                "detail": ledger["status"].value_counts().to_dict(),
            },
            {
                "check": "hourly_row_count",
                "required": True,
                "passed": len(hourly) == expected_hourly_rows,
                "detail": len(hourly),
            },
            {
                "check": "240_hours_per_request",
                "required": True,
                "passed": hourly_counts.eq(240).all(),
                "detail": (
                    f"min={hourly_counts.min()}, "
                    f"max={hourly_counts.max()}"
                ),
            },
            {
                "check": "daily_row_count",
                "required": True,
                "passed": len(daily) == expected_daily_rows,
                "detail": len(daily),
            },
            {
                "check": "eleven_dates_per_request",
                "required": True,
                "passed": daily_counts.eq(11).all(),
                "detail": (
                    f"min={daily_counts.min()}, "
                    f"max={daily_counts.max()}"
                ),
            },
            {
                "check": "nine_complete_dates_per_request",
                "required": True,
                "passed": complete_counts.eq(9).all(),
                "detail": (
                    f"min={complete_counts.min()}, "
                    f"max={complete_counts.max()}"
                ),
            },
            {
                "check": "complete_local_day_total",
                "required": True,
                "passed": (
                    int(daily["complete_local_day"].sum())
                    == expected_complete_days
                ),
                "detail": int(
                    daily["complete_local_day"].sum()
                ),
            },
            {
                "check": "temperatures_nonmissing",
                "required": True,
                "passed": hourly[
                    "temperature_2m_c"
                ].notna().all(),
                "detail": int(
                    hourly["temperature_2m_c"].notna().sum()
                ),
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
        checks["required"] & ~checks["passed"]
    ]

    if not required_failed.empty:
        raise RuntimeError(
            "Required integrity checks failed:\n"
            + required_failed.to_string(index=False)
        )

    summary = (
        ledger.groupby("cycle_utc", as_index=False)
        .agg(
            requests=("request_id", "size"),
            downloaded=("network_retrieved", "sum"),
            cache_reused=("cache_reused", "sum"),
            compressed_file_bytes=(
                "compressed_file_bytes",
                "sum",
            ),
            first_run_init_utc=("run_init_utc", "min"),
            last_run_init_utc=("run_init_utc", "max"),
        )
    )

    write_csv(ledger, LEDGER_PATH)
    write_csv(hourly, HOURLY_PATH)
    write_csv(daily, DAILY_PATH)
    write_csv(summary, SUMMARY_PATH)
    write_csv(checks, CHECKS_PATH)

    hash_material = "\n".join(
        f"{row.request_id},{row.response_sha256}"
        for row in ledger.sort_values(
            "request_id",
            kind="stable",
        ).itertuples(index=False)
    ).encode("utf-8")

    output_paths = [
        LEDGER_PATH,
        HOURLY_PATH,
        DAILY_PATH,
        SUMMARY_PATH,
        CHECKS_PATH,
    ]

    manifest = {
        "phase": 4,
        "phase_status": "PHASE4_COMPLETE",
        "status": "TWO_YEAR_CORE_RETRIEVAL_CERTIFIED",
        "created_utc": utc_now(),
        "expected_requests": expected_requests,
        "successful_requests": len(ledger),
        "failed_requests": 0,
        "core_cycles_utc": [0, 12],
        "hourly_rows": len(hourly),
        "hourly_rows_per_request": 240,
        "daily_run_rows": len(daily),
        "complete_local_day_rows": int(
            daily["complete_local_day"].sum()
        ),
        "raw_cache_directory": str(
            RAW_CACHE_ROOT.relative_to(ROOT)
        ),
        "raw_cache_file_count": len(ledger),
        "raw_cache_committed_to_git": False,
        "raw_cache_sha256_root": sha256_bytes(hash_material),
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
            "Construct the two-year forecast-target panel "
            "and join the HKO observations."
        ),
    }

    write_json(MANIFEST_PATH, manifest)

    print()
    print("=" * 78)
    print("PHASE 4 CORE RETRIEVAL CERTIFIED")
    print("=" * 78)
    print("Successful requests:", len(ledger))
    print("Hourly rows:", len(hourly))
    print("Daily run rows:", len(daily))
    print(
        "Complete local-day rows:",
        int(daily["complete_local_day"].sum()),
    )
    print("Market prices accessed: False")
    print("Outcomes accessed: False")
    print("Model fitted: False")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check-plan",
        action="store_true",
        help="Validate the request plan without network access.",
    )

    arguments = parser.parse_args()

    spec, phase3, plan = load_inputs()
    validate_plan(spec, phase3, plan)

    if arguments.check_plan:
        print("Phase 3 status:", phase3["status"])
        print("Request-plan rows:", len(plan))
        print(
            "Selected cycles:",
            sorted(plan["cycle_utc"].unique().tolist()),
        )
        print("Network requests made: False")
        print("REQUEST-PLAN PREFLIGHT: PASSED")
        return

    ledger = retrieve(spec, plan)
    certify(spec, phase3, ledger)


if __name__ == "__main__":
    main()
