from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
import time as time_module

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


# =============================================================================
# FINAL EMPIRICAL SPECIFICATION
# =============================================================================

START_DATE = date(2024, 3, 16)
END_DATE = date(2026, 8, 31)

HISTORICAL_AUDIT_END = date(2026, 3, 15)
MARKET_START = date(2026, 3, 16)
EXTERNAL_START = date(2026, 7, 1)

HKT = ZoneInfo("Asia/Hong_Kong")
UTC = timezone.utc

LATITUDE = 22.3019444444
LONGITUDE = 114.1741666667

MODEL = "ecmwf_ifs"
VARIABLE = "temperature_2m"

# Final dissertation methodology.
AVAILABILITY_DELAY_HOURS = 6

# Exact established Open-Meteo request construction used by the
# certified V2 acquisition.
CELL_SELECTION = "land"
FORECAST_HOURS = 240

# Frozen historical acquisition inventory. This identifies which
# runs formed the certified historical archive; it does not provide
# forecast values to the new processed panel.
LEGACY_INVENTORY_PATH = Path(
    "outputs/v2/diagnostics/"
    "03b_two_year_complete_run_inventory.csv"
)

HISTORICAL_RUN_CUTOFF = datetime(
    2026, 3, 15, 23, 59,
    tzinfo=UTC,
)

SINGLE_RUNS_ENDPOINT = (
    "https://single-runs-api.open-meteo.com/v1/forecast"
)

FORECAST_DAYS = 10

# Post-28/08 final implementation:
#
#   core cycles:   00, 12 UTC
#   repair cycles: 06, 18 UTC
#
# A repair cycle is consulted only if the corresponding latest core
# candidate cannot provide a valid 24-hour local-day path.
CORE_CYCLES = (0, 12)
REPAIR_CYCLES = (6, 18)

# All ECMWF deterministic cycles admitted by the final pipeline.
#
# Forecast selection is chronological:
# search backward through 00/06/12/18 UTC runs and choose the latest
# run issued no later than the decision cutoff that supplies a complete
# 24-hour Hong Kong local-day forecast path.
ALL_CYCLES = (0, 6, 12, 18)

# Historical audited data occasionally require fallback by more than one day.
# Seven days is intentionally generous; the algorithm always chooses the
# latest valid run, so extending the search horizon cannot alter a selection
# when a newer valid candidate exists.
MAX_FALLBACK_HOURS = 168


DECISION_RULES = {
    "24h_prior": {
        "order": 1,
        "offset_hours": -24,
    },
    "12h_prior": {
        "order": 2,
        "offset_hours": -12,
    },
    "6h_prior": {
        "order": 3,
        "offset_hours": -6,
    },
    "event_day_open": {
        "order": 4,
        "offset_hours": 0,
    },
}

RAW_DIR = Path("data/raw/ecmwf_final_v85")
PROCESSED_DIR = Path("data/processed/final_pipeline")
AUDIT_DIR = Path("outputs/final_pipeline/audit")

REQUEST_PLAN_CSV = (
    PROCESSED_DIR / "ecmwf_request_plan.csv"
)

FORECAST_PANEL_CSV = (
    PROCESSED_DIR / "ecmwf_deterministic_forecasts.csv"
)

FETCH_INVENTORY_CSV = (
    AUDIT_DIR / "ecmwf_fetch_inventory.csv"
)

UNSUPPORTED_CSV = (
    AUDIT_DIR / "ecmwf_unsupported_keys.csv"
)

RECONCILIATION_CSV = (
    AUDIT_DIR / "ecmwf_historical_reconciliation.csv"
)

CHECKS_CSV = (
    AUDIT_DIR / "ecmwf_integrity_checks.csv"
)

SUMMARY_JSON = (
    AUDIT_DIR / "ecmwf_summary.json"
)

OLD_WEATHER_PANEL = Path(
    "outputs/v2/diagnostics/"
    "05_weather_only_forecast_residual_panel.csv"
)


@dataclass
class RunPayload:
    run_init_utc: datetime
    success: bool
    payload: dict[str, Any] | None
    cache_path: str
    source_origin: str
    http_status: str
    error: str
    n_hourly_rows: int


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def iso_utc(dt: datetime) -> str:
    return (
        dt.astimezone(UTC)
        .isoformat()
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


# =============================================================================
# DECISION TIMES
# =============================================================================


def target_midnight_hkt(
    target: date,
) -> datetime:
    return datetime.combine(
        target,
        time(0, 0),
        tzinfo=HKT,
    )


def decision_time(
    target: date,
    rule: str,
) -> datetime:
    return (
        target_midnight_hkt(target)
        + timedelta(
            hours=DECISION_RULES[
                rule
            ]["offset_hours"]
        )
    )


def latest_cycle_before(
    cutoff_utc: datetime,
    cycles: tuple[int, ...],
) -> datetime:
    """
    Latest designated cycle at or before the decision time.
    """
    candidates = []

    for day_shift in range(0, 3):
        candidate_date = (
            cutoff_utc.date()
            - timedelta(days=day_shift)
        )

        for hour in cycles:
            dt = datetime.combine(
                candidate_date,
                time(hour, 0),
                tzinfo=UTC,
            )

            if dt <= cutoff_utc:
                candidates.append(dt)

    if not candidates:
        raise RuntimeError(
            "No candidate cycle found."
        )

    return max(candidates)



def candidate_runs_before(
    cutoff_utc: datetime,
    max_fallback_hours: int = MAX_FALLBACK_HOURS,
) -> list[datetime]:
    """
    Return admissible ECMWF cycles in strict reverse chronological order.

    Candidate cycles are 00, 06, 12 and 18 UTC. Every candidate satisfies

        run_init_utc <= decision_time_utc.

    The first candidate providing a complete Hong Kong local-day path is
    selected.
    """
    earliest = (
        cutoff_utc
        - timedelta(
            hours=max_fallback_hours
        )
    )

    candidates: list[datetime] = []

    current_date = cutoff_utc.date()

    while True:
        day_candidates = [
            datetime.combine(
                current_date,
                time(hour, 0),
                tzinfo=UTC,
            )
            for hour in ALL_CYCLES
        ]

        for run in day_candidates:
            if (
                earliest
                <= run
                <= cutoff_utc
            ):
                candidates.append(run)

        if (
            datetime.combine(
                current_date,
                time(0, 0),
                tzinfo=UTC,
            )
            < earliest
        ):
            break

        current_date -= timedelta(days=1)

    return sorted(
        set(candidates),
        reverse=True,
    )


# =============================================================================
# CACHE DISCOVERY
# =============================================================================


RUN_PATTERNS = [
    re.compile(
        r"ecmwf_ifs_(\d{8})_(\d{2})"
    ),
    re.compile(
        r"ecmwf_ifs_hko_(\d{8})T(\d{2})00Z"
    ),
    re.compile(
        r"ecmwf_ifs_(\d{8})T(\d{2})00Z"
    ),
]


def run_from_filename(
    path: Path,
) -> datetime | None:
    name = path.name

    for pattern in RUN_PATTERNS:
        m = pattern.search(name)

        if not m:
            continue

        try:
            d = datetime.strptime(
                m.group(1),
                "%Y%m%d",
            ).date()

            hour = int(
                m.group(2)
            )

            return datetime.combine(
                d,
                time(hour, 0),
                tzinfo=UTC,
            )

        except Exception:
            continue

    return None


def legacy_cache_index() -> dict[datetime, Path]:
    """
    Return the frozen certified V2 historical run inventory.

    This is an acquisition-design snapshot, not a processed forecast
    result. It prevents incidental raw files that were never admitted
    to the certified archive from changing the historical candidate set.
    """
    if not LEGACY_INVENTORY_PATH.exists():
        raise RuntimeError(
            "Certified V2 complete-run inventory is missing: "
            f"{LEGACY_INVENTORY_PATH}"
        )

    result: dict[datetime, Path] = {}

    with LEGACY_INVENTORY_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        required = {
            "run_init_utc",
            "cache_path",
        }

        missing = (
            required
            - set(reader.fieldnames or [])
        )

        if missing:
            raise RuntimeError(
                "Historical inventory lacks columns: "
                f"{sorted(missing)}"
            )

        for row in reader:
            run = parse_utc(
                row["run_init_utc"]
            )

            source = Path(
                row["cache_path"]
            )

            # If a repeated initialisation exists, retaining either
            # response is sufficient because the run is the empirical
            # information unit; downstream reconciliation verifies its
            # actual daily maximum.
            result[run] = source

    return result


def canonical_cache_path(
    run: datetime,
) -> Path:
    return (
        RAW_DIR
        / f"{run.year:04d}"
        / f"{run.month:02d}"
        / (
            "ecmwf_ifs_"
            f"{run:%Y%m%d_%H}"
            ".json.gz"
        )
    )


def read_json_file(
    path: Path,
) -> dict[str, Any]:
    if str(path).endswith(".gz"):
        with gzip.open(
            path,
            "rt",
            encoding="utf-8",
        ) as f:
            obj = json.load(f)

    else:
        obj = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    if not isinstance(obj, dict):
        raise RuntimeError(
            f"Unexpected JSON type: {path}"
        )

    return obj


def validate_open_meteo_payload(
    payload: dict[str, Any],
) -> int:
    hourly = payload.get("hourly")

    if not isinstance(hourly, dict):
        raise RuntimeError(
            "Open-Meteo payload lacks hourly object."
        )

    times = hourly.get("time")
    temps = hourly.get(VARIABLE)

    if not isinstance(times, list):
        raise RuntimeError(
            "Payload lacks hourly time list."
        )

    if not isinstance(temps, list):
        raise RuntimeError(
            "Payload lacks temperature_2m list."
        )

    if len(times) != len(temps):
        raise RuntimeError(
            "Hourly time/temperature lengths differ."
        )

    return len(times)


def copy_legacy_cache(
    source: Path,
    destination: Path,
):
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if str(source).endswith(".gz"):
        shutil.copy2(
            source,
            destination,
        )
        return

    raw = source.read_bytes()

    buffer = io.BytesIO()

    with gzip.GzipFile(
        fileobj=buffer,
        mode="wb",
        mtime=0,
    ) as gz:
        gz.write(raw)

    destination.write_bytes(
        buffer.getvalue()
    )


# =============================================================================
# OPEN-METEO FETCH
# =============================================================================


def request_url(
    run: datetime,
) -> str:
    from urllib.parse import urlencode

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "run": run.strftime(
            "%Y-%m-%dT%H:00"
        ),
        "hourly": VARIABLE,
        "models": MODEL,
        "timezone": "Asia/Hong_Kong",
        "temperature_unit": "celsius",
        "cell_selection": CELL_SELECTION,
        "forecast_hours": FORECAST_HOURS,
    }

    return (
        SINGLE_RUNS_ENDPOINT
        + "?"
        + urlencode(params)
    )


def curl_fetch(
    url: str,
) -> tuple[
    int,
    bytes,
    str,
]:
    """
    Returns:
        HTTP status,
        response body,
        diagnostic string.
    """
    last_diag = ""

    for attempt in range(1, 4):
        result = subprocess.run(
            [
                "curl",
                "-L",
                "--silent",
                "--show-error",
                "--max-time",
                "90",
                "--write-out",
                "\n__HTTP__:%{http_code}",
                url,
            ],
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            last_diag = (
                f"curl_exit={result.returncode}; "
                + result.stderr.decode(
                    "utf-8",
                    errors="replace",
                ).strip()
            )

            if attempt < 3:
                time_module.sleep(
                    1.0 * attempt
                )
                continue

            return (
                0,
                b"",
                last_diag,
            )

        marker = b"\n__HTTP__:"

        if marker not in result.stdout:
            return (
                0,
                b"",
                "missing_http_marker",
            )

        body, status_raw = (
            result.stdout.rsplit(
                marker,
                1,
            )
        )

        try:
            status = int(
                status_raw.decode(
                    "ascii"
                ).strip()
            )

        except Exception:
            status = 0

        if status == 200:
            return (
                status,
                body,
                "ok",
            )

        # 400 means an unavailable archived run and should not
        # be retried.
        if status == 400:
            return (
                status,
                body,
                "run_unavailable",
            )

        last_diag = (
            f"http_status={status}"
        )

        if (
            status == 429
            or 500 <= status <= 599
        ) and attempt < 3:
            time_module.sleep(
                2.0 * attempt
            )
            continue

        return (
            status,
            body,
            last_diag,
        )

    return (
        0,
        b"",
        last_diag,
    )


# =============================================================================
# RUN STORE
# =============================================================================


class RunStore:
    def __init__(
        self,
        refresh_new: bool,
    ):
        self.refresh_new = (
            refresh_new
        )

        self.legacy = (
            legacy_cache_index()
        )

        self.memo: dict[
            datetime,
            RunPayload,
        ] = {}

        self.inventory_rows = []

    def get(
        self,
        run: datetime,
    ) -> RunPayload:
        if run in self.memo:
            return self.memo[run]

        cache = canonical_cache_path(run)

        historical_run = (
            run <= HISTORICAL_RUN_CUTOFF
        )

        # ---------------------------------------------------------
        # Historical archive eligibility gate
        # ---------------------------------------------------------

        if (
            historical_run
            and run not in self.legacy
        ):
            result = RunPayload(
                run_init_utc=run,
                success=False,
                payload=None,
                cache_path="",
                source_origin=
                    "historical_not_in_certified_inventory",
                http_status="not_requested",
                error=
                    "run_not_in_certified_v2_inventory",
                n_hourly_rows=0,
            )

            self._record(result)
            return result

        # ---------------------------------------------------------
        # Historical certified raw source
        # ---------------------------------------------------------

        if (
            historical_run
            and run in self.legacy
        ):
            source = self.legacy[run]

            if source.exists():
                try:
                    payload = read_json_file(
                        source
                    )

                    n = validate_open_meteo_payload(
                        payload
                    )

                    cache.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    copy_legacy_cache(
                        source,
                        cache,
                    )

                    result = RunPayload(
                        run_init_utc=run,
                        success=True,
                        payload=payload,
                        cache_path=str(cache),
                        source_origin=
                            "certified_v2_raw_archive",
                        http_status="cache",
                        error="",
                        n_hourly_rows=n,
                    )

                    self._record(result)
                    return result

                except Exception:
                    # If the historical raw object is damaged or absent,
                    # reacquire the SAME frozen run initialisation below.
                    pass

        # ---------------------------------------------------------
        # Final-pipeline cache
        # ---------------------------------------------------------

        if (
            cache.exists()
            and not self.refresh_new
        ):
            try:
                payload = read_json_file(
                    cache
                )

                n = validate_open_meteo_payload(
                    payload
                )

                result = RunPayload(
                    run_init_utc=run,
                    success=True,
                    payload=payload,
                    cache_path=str(cache),
                    source_origin=
                        (
                            "historical_reacquired_cache"
                            if historical_run
                            else "final_extension_cache"
                        ),
                    http_status="cache",
                    error="",
                    n_hourly_rows=n,
                )

                self._record(result)
                return result

            except Exception:
                cache.unlink(
                    missing_ok=True
                )

        # ---------------------------------------------------------
        # Independent API retrieval
        # ---------------------------------------------------------

        url = request_url(run)

        (
            status,
            raw,
            diag,
        ) = curl_fetch(url)

        if status != 200:
            result = RunPayload(
                run_init_utc=run,
                success=False,
                payload=None,
                cache_path="",
                source_origin=
                    (
                        "historical_reacquisition"
                        if historical_run
                        else "open_meteo_extension_api"
                    ),
                http_status=str(status),
                error=diag,
                n_hourly_rows=0,
            )

            self._record(result)
            return result

        try:
            payload = json.loads(
                raw.decode("utf-8")
            )

            if not isinstance(
                payload,
                dict,
            ):
                raise RuntimeError(
                    "top-level JSON is not object"
                )

            n = validate_open_meteo_payload(
                payload
            )

        except Exception as exc:
            result = RunPayload(
                run_init_utc=run,
                success=False,
                payload=None,
                cache_path="",
                source_origin=
                    "open_meteo_api",
                http_status=str(status),
                error=(
                    "invalid_payload: "
                    + str(exc)
                ),
                n_hourly_rows=0,
            )

            self._record(result)
            return result

        cache.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        buffer = io.BytesIO()

        with gzip.GzipFile(
            fileobj=buffer,
            mode="wb",
            mtime=0,
        ) as gz:
            gz.write(raw)

        cache.write_bytes(
            buffer.getvalue()
        )

        result = RunPayload(
            run_init_utc=run,
            success=True,
            payload=payload,
            cache_path=str(cache),
            source_origin=
                (
                    "historical_reacquisition"
                    if historical_run
                    else "open_meteo_extension_api"
                ),
            http_status=str(status),
            error="",
            n_hourly_rows=n,
        )

        self._record(result)
        return result

    def _record(
        self,
        result: RunPayload,
    ):
        self.memo[
            result.run_init_utc
        ] = result

        self.inventory_rows.append(
            {
                "run_init_utc":
                    iso_utc(
                        result.run_init_utc
                    ),
                "cycle_utc":
                    result.run_init_utc.hour,
                "success":
                    result.success,
                "source_origin":
                    result.source_origin,
                "http_status":
                    result.http_status,
                "n_hourly_rows":
                    result.n_hourly_rows,
                "cache_path":
                    result.cache_path,
                "error":
                    result.error,
            }
        )


# =============================================================================
# LOCAL-DAY EXTRACTION
# =============================================================================


def parse_local_time(
    value: Any,
) -> datetime:
    text = str(value)

    dt = datetime.fromisoformat(
        text
    )

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=HKT
        )
    else:
        dt = dt.astimezone(
            HKT
        )

    return dt


def local_day_stats(
    payload: dict[str, Any],
    target: date,
) -> dict[str, Any]:
    hourly = payload["hourly"]

    times = hourly["time"]
    temps = hourly[VARIABLE]

    rows = []

    for t, temp_value in zip(
        times,
        temps,
    ):
        dt = parse_local_time(t)

        if dt.date() != target:
            continue

        try:
            value = (
                None
                if temp_value is None
                else float(temp_value)
            )

        except Exception:
            value = None

        rows.append(
            (
                dt,
                value,
            )
        )

    hours = [
        dt.hour
        for dt, _ in rows
    ]

    values = [
        value
        for _, value in rows
        if value is not None
        and math.isfinite(value)
    ]

    complete = (
        len(rows) == 24
        and len(set(hours)) == 24
        and set(hours) == set(range(24))
        and len(values) == 24
    )

    return {
        "hourly_rows":
            len(rows),
        "unique_local_hours":
            len(set(hours)),
        "nonmissing_temperature_rows":
            len(values),
        "hours_00_to_23":
            set(hours)
            == set(range(24)),
        "complete_local_day":
            complete,
        "forecast_daily_max_c":
            (
                max(values)
                if complete
                else None
            ),
        "forecast_daily_min_c":
            (
                min(values)
                if complete
                else None
            ),
        "forecast_daily_mean_c":
            (
                sum(values)
                / len(values)
                if complete
                else None
            ),
    }


# =============================================================================
# HISTORICAL METHOD-STRUCTURE AUDIT
# =============================================================================


def load_old_panel():
    if not OLD_WEATHER_PANEL.exists():
        raise RuntimeError(
            "Required historical audit panel missing: "
            f"{OLD_WEATHER_PANEL}"
        )

    rows = []

    with OLD_WEATHER_PANEL.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append(row)

    return rows


def parse_utc(value: str) -> datetime:
    text = value.strip()

    if text.endswith("Z"):
        text = (
            text[:-1]
            + "+00:00"
        )

    dt = datetime.fromisoformat(
        text
    )

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=UTC
        )

    return dt.astimezone(
        UTC
    )


def historical_policy_preflight(
    old_rows,
):
    """
    Audit the historical run-age/cycle structure.

    The previous audited panel is used only to establish that every selected
    run:

    1. was issued no later than the decision cutoff;
    2. belongs to an admitted 00/06/12/18 UTC cycle;
    3. falls within the final backward-search horizon.

    It is NOT used to choose a run in the rebuilt pipeline.
    """
    counts = Counter()
    exceptions = []
    ages = []

    for row in old_rows:
        target = date.fromisoformat(
            row["target_date"][:10]
        )

        if target > HISTORICAL_AUDIT_END:
            continue

        rule = row[
            "decision_rule"
        ]

        cutoff = decision_time(
            target,
            rule,
        ).astimezone(UTC)

        selected = parse_utc(
            row["run_init_utc"]
        )

        age_hours = (
            cutoff
            - selected
        ).total_seconds() / 3600

        ages.append(age_hours)

        valid = True
        reasons = []

        if selected > cutoff:
            valid = False
            reasons.append(
                "issued_after_cutoff"
            )

        if selected.hour not in ALL_CYCLES:
            valid = False
            reasons.append(
                "inadmissible_cycle"
            )

        if age_hours < 0:
            valid = False
            reasons.append(
                "negative_age"
            )

        if age_hours > MAX_FALLBACK_HOURS:
            valid = False
            reasons.append(
                "beyond_search_horizon"
            )

        if valid:
            counts[
                f"cycle_{selected.hour:02d}"
            ] += 1

        else:
            counts["invalid"] += 1

            if len(exceptions) < 50:
                exceptions.append(
                    {
                        "target_date":
                            target.isoformat(),
                        "decision_rule":
                            rule,
                        "cutoff":
                            iso_utc(cutoff),
                        "selected":
                            iso_utc(selected),
                        "age_hours":
                            age_hours,
                        "reasons":
                            reasons,
                    }
                )

    summary = {
        "cycle_counts":
            dict(counts),
        "minimum_run_age_hours":
            min(ages) if ages else None,
        "maximum_run_age_hours":
            max(ages) if ages else None,
        "mean_run_age_hours":
            (
                sum(ages) / len(ages)
                if ages
                else None
            ),
        "invalid_rows":
            counts["invalid"],
    }

    return (
        summary,
        exceptions,
    )


# =============================================================================
# MAIN RECONSTRUCTION
# =============================================================================


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--refresh-new",
        action="store_true",
        help=(
            "Refresh independently fetched final-cache runs. "
            "Certified legacy raw responses are still preferred "
            "where available."
        ),
    )

    args = parser.parse_args()

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------------------------------------------------------
    # A. Confirm previous audited selection fits the stated policy family
    # -------------------------------------------------------------------------

    old_rows = load_old_panel()

    if len(old_rows) != 2920:
        raise RuntimeError(
            "Historical weather panel must contain 2,920 rows; "
            f"found {len(old_rows)}."
        )

    (
        policy_summary,
        policy_exceptions,
    ) = historical_policy_preflight(
        old_rows
    )

    if policy_summary["invalid_rows"] != 0:
        raise RuntimeError(
            "Historical audited selections violate the final "
            "chronological candidate policy. "
            f"summary={policy_summary}; "
            f"exceptions={policy_exceptions}"
        )

    # -------------------------------------------------------------------------
    # B. Request plan + reconstruction
    # -------------------------------------------------------------------------

    store = RunStore(
        refresh_new=args.refresh_new
    )

    request_plan_rows = []
    forecast_rows = []
    unsupported_rows = []

    for target in daterange(
        START_DATE,
        END_DATE,
    ):
        for rule, spec in (
            DECISION_RULES.items()
        ):
            decision_hkt = (
                decision_time(
                    target,
                    rule,
                )
            )

            cutoff_utc = (
                decision_hkt
                .astimezone(UTC)
            )

            availability_cutoff_utc = (
                cutoff_utc
                - timedelta(
                    hours=
                        AVAILABILITY_DELAY_HOURS
                )
            )

            chronological_candidates = (
                candidate_runs_before(
                    availability_cutoff_utc
                )
            )

            core_candidates = [
                run
                for run in
                chronological_candidates
                if run.hour
                in CORE_CYCLES
            ]

            repair_candidates = [
                run
                for run in
                chronological_candidates
                if run.hour
                in REPAIR_CYCLES
            ]

            # Core archive is always preferred. Repair cycles are
            # considered only if no eligible core candidate supplies
            # a valid complete target-day path.
            candidates = (
                core_candidates
                + repair_candidates
            )

            for rank, run in enumerate(
                candidates,
                start=1,
            ):
                request_plan_rows.append(
                    {
                        "target_date":
                            target.isoformat(),
                        "decision_rule":
                            rule,
                        "decision_rule_order":
                            spec["order"],
                        "decision_offset_hours":
                            spec["offset_hours"],
                        "target_midnight_hkt":
                            target_midnight_hkt(
                                target
                            ).isoformat(),
                        "decision_time_hkt":
                            decision_hkt.isoformat(),
                        "decision_time_utc":
                            iso_utc(
                                cutoff_utc
                            ),
                        "candidate_tier":
                            (
                                "core"
                                if run.hour
                                in CORE_CYCLES
                                else "supplementary"
                            ),
                        "candidate_rank":
                            rank,
                        "candidate_run_init_utc":
                            iso_utc(run),
                        "candidate_cycle_utc":
                            run.hour,
                    }
                )

            selected_payload = None
            selected_stats = None
            selected_tier = None
            attempts = []

            selected_rank = None

            for rank, run in enumerate(
                candidates,
                start=1,
            ):
                tier = (
                    "core"
                    if run.hour
                    in CORE_CYCLES
                    else "supplementary"
                )

                result = store.get(run)

                attempt = {
                    "rank": rank,
                    "tier": tier,
                    "run": iso_utc(run),
                    "fetch_success":
                        result.success,
                    "error":
                        result.error,
                }

                if not result.success:
                    attempts.append(
                        attempt
                    )
                    continue

                stats = local_day_stats(
                    result.payload,
                    target,
                )

                attempt[
                    "complete_local_day"
                ] = stats[
                    "complete_local_day"
                ]

                attempts.append(
                    attempt
                )

                if not stats[
                    "complete_local_day"
                ]:
                    continue

                selected_payload = (
                    result
                )

                selected_stats = (
                    stats
                )

                selected_tier = tier
                selected_rank = rank

                break

            if (
                selected_payload is None
                or selected_stats is None
            ):
                reason = json.dumps(
                    attempts,
                    sort_keys=True,
                )

                row = {
                    "target_date":
                        target.isoformat(),
                    "decision_rule":
                        rule,
                    "decision_rule_order":
                        spec["order"],
                    "decision_offset_hours":
                        spec["offset_hours"],
                    "target_midnight_hkt":
                        target_midnight_hkt(
                            target
                        ).isoformat(),
                    "decision_time_hkt":
                        decision_hkt.isoformat(),
                    "decision_time_utc":
                        iso_utc(
                            cutoff_utc
                        ),
                    "selected_run_init_utc":
                        "",
                    "selected_cycle_utc":
                        "",
                    "selection_tier":
                        "",
                    "selected_candidate_rank":
                        "",
                    "run_age_hours_at_decision":
                        "",
                    "issued_before_decision":
                        False,
                    "hourly_rows":
                        0,
                    "unique_local_hours":
                        0,
                    "nonmissing_temperature_rows":
                        0,
                    "hours_00_to_23":
                        False,
                    "complete_local_day":
                        False,
                    "forecast_daily_max_c":
                        "",
                    "forecast_daily_min_c":
                        "",
                    "forecast_daily_mean_c":
                        "",
                    "support_available":
                        False,
                    "cache_path":
                        "",
                    "raw_source_origin":
                        "",
                    "selection_rule":
                        (
                            "latest eligible complete 00/12 UTC core run after "
                            "the six-hour availability allowance; 06/18 UTC "
                            "repair only if no valid core path exists"
                        ),
                    "unsupported_reason":
                        reason,
                }

                forecast_rows.append(
                    row
                )

                unsupported_rows.append(
                    row.copy()
                )

                continue

            selected_run = (
                selected_payload
                .run_init_utc
            )

            age_hours = (
                cutoff_utc
                - selected_run
            ).total_seconds() / 3600

            issued_before = (
                selected_run
                <= cutoff_utc
            )

            row = {
                "target_date":
                    target.isoformat(),
                "decision_rule":
                    rule,
                "decision_rule_order":
                    spec["order"],
                "decision_offset_hours":
                    spec["offset_hours"],
                "target_midnight_hkt":
                    target_midnight_hkt(
                        target
                    ).isoformat(),
                "decision_time_hkt":
                    decision_hkt.isoformat(),
                "decision_time_utc":
                    iso_utc(
                        cutoff_utc
                    ),
                "selected_run_init_utc":
                    iso_utc(
                        selected_run
                    ),
                "selected_cycle_utc":
                    selected_run.hour,
                "selection_tier":
                    selected_tier,
                "selected_candidate_rank":
                    selected_rank,
                "run_age_hours_at_decision":
                    f"{age_hours:.6f}",
                "issued_before_decision":
                    issued_before,
                "hourly_rows":
                    selected_stats[
                        "hourly_rows"
                    ],
                "unique_local_hours":
                    selected_stats[
                        "unique_local_hours"
                    ],
                "nonmissing_temperature_rows":
                    selected_stats[
                        "nonmissing_temperature_rows"
                    ],
                "hours_00_to_23":
                    selected_stats[
                        "hours_00_to_23"
                    ],
                "complete_local_day":
                    selected_stats[
                        "complete_local_day"
                    ],
                "forecast_daily_max_c":
                    (
                        f"{selected_stats['forecast_daily_max_c']:.10f}"
                    ),
                "forecast_daily_min_c":
                    (
                        f"{selected_stats['forecast_daily_min_c']:.10f}"
                    ),
                "forecast_daily_mean_c":
                    (
                        f"{selected_stats['forecast_daily_mean_c']:.10f}"
                    ),
                "support_available":
                    True,
                "cache_path":
                    selected_payload
                    .cache_path,
                "raw_source_origin":
                    selected_payload
                    .source_origin,
                "selection_rule":
                    (
                        "latest eligible complete 00/12 UTC core run after "
                        "the six-hour availability allowance; 06/18 UTC "
                        "repair only if no valid core path exists"
                    ),
                "unsupported_reason":
                    "",
            }

            forecast_rows.append(
                row
            )

    # -------------------------------------------------------------------------
    # C. Historical exact reconciliation against audited V2 output
    # -------------------------------------------------------------------------

    new_lookup = {
        (
            row["target_date"],
            row["decision_rule"],
        ): row
        for row in forecast_rows
    }

    historical_rows = [
        row
        for row in old_rows
        if (
            date.fromisoformat(
                row["target_date"][:10]
            )
            <= HISTORICAL_AUDIT_END
        )
    ]

    reconciliation = []
    mismatches = []

    for old in historical_rows:
        key = (
            old["target_date"][:10],
            old["decision_rule"],
        )

        new = new_lookup.get(key)

        if new is None:
            item = {
                "target_date": key[0],
                "decision_rule": key[1],
                "old_run_init_utc":
                    old["run_init_utc"],
                "new_run_init_utc": "",
                "old_forecast_daily_max_c":
                    old["forecast_daily_max_c"],
                "new_forecast_daily_max_c": "",
                "run_exact_match": False,
                "forecast_exact_match": False,
                "overall_match": False,
                "difference_c": "",
            }

            reconciliation.append(
                item
            )

            mismatches.append(
                item
            )

            continue

        old_run = parse_utc(
            old["run_init_utc"]
        )

        new_run = parse_utc(
            new[
                "selected_run_init_utc"
            ]
        ) if new[
            "selected_run_init_utc"
        ] else None

        old_value = float(
            old[
                "forecast_daily_max_c"
            ]
        )

        new_value = (
            float(
                new[
                    "forecast_daily_max_c"
                ]
            )
            if new[
                "forecast_daily_max_c"
            ]
            else None
        )

        run_match = (
            new_run is not None
            and old_run == new_run
        )

        forecast_match = (
            new_value is not None
            and abs(
                old_value
                - new_value
            ) < 1e-10
        )

        overall = (
            run_match
            and forecast_match
        )

        item = {
            "target_date":
                key[0],
            "decision_rule":
                key[1],
            "old_run_init_utc":
                iso_utc(old_run),
            "new_run_init_utc":
                (
                    ""
                    if new_run is None
                    else iso_utc(
                        new_run
                    )
                ),
            "old_forecast_daily_max_c":
                f"{old_value:.10f}",
            "new_forecast_daily_max_c":
                (
                    ""
                    if new_value is None
                    else f"{new_value:.10f}"
                ),
            "run_exact_match":
                run_match,
            "forecast_exact_match":
                forecast_match,
            "overall_match":
                overall,
            "difference_c":
                (
                    ""
                    if new_value is None
                    else (
                        f"{new_value-old_value:.10f}"
                    )
                ),
        }

        reconciliation.append(
            item
        )

        if not overall:
            mismatches.append(
                item
            )

    # -------------------------------------------------------------------------
    # D. Write outputs
    # -------------------------------------------------------------------------

    request_fields = [
        "target_date",
        "decision_rule",
        "decision_rule_order",
        "decision_offset_hours",
        "target_midnight_hkt",
        "decision_time_hkt",
        "decision_time_utc",
        "candidate_tier",
        "candidate_rank",
        "candidate_run_init_utc",
        "candidate_cycle_utc",
    ]

    forecast_fields = [
        "target_date",
        "decision_rule",
        "decision_rule_order",
        "decision_offset_hours",
        "target_midnight_hkt",
        "decision_time_hkt",
        "decision_time_utc",
        "selected_run_init_utc",
        "selected_cycle_utc",
        "selection_tier",
        "selected_candidate_rank",
        "run_age_hours_at_decision",
        "issued_before_decision",
        "hourly_rows",
        "unique_local_hours",
        "nonmissing_temperature_rows",
        "hours_00_to_23",
        "complete_local_day",
        "forecast_daily_max_c",
        "forecast_daily_min_c",
        "forecast_daily_mean_c",
        "support_available",
        "cache_path",
        "raw_source_origin",
        "selection_rule",
        "unsupported_reason",
    ]

    fetch_fields = [
        "run_init_utc",
        "cycle_utc",
        "success",
        "source_origin",
        "http_status",
        "n_hourly_rows",
        "cache_path",
        "error",
    ]

    reconciliation_fields = [
        "target_date",
        "decision_rule",
        "old_run_init_utc",
        "new_run_init_utc",
        "old_forecast_daily_max_c",
        "new_forecast_daily_max_c",
        "run_exact_match",
        "forecast_exact_match",
        "overall_match",
        "difference_c",
    ]

    write_csv(
        REQUEST_PLAN_CSV,
        request_fields,
        request_plan_rows,
    )

    write_csv(
        FORECAST_PANEL_CSV,
        forecast_fields,
        forecast_rows,
    )

    write_csv(
        FETCH_INVENTORY_CSV,
        fetch_fields,
        store.inventory_rows,
    )

    write_csv(
        UNSUPPORTED_CSV,
        forecast_fields,
        unsupported_rows,
    )

    write_csv(
        RECONCILIATION_CSV,
        reconciliation_fields,
        reconciliation,
    )

    # -------------------------------------------------------------------------
    # E. Integrity checks
    # -------------------------------------------------------------------------

    expected_keys = (
        len(
            list(
                daterange(
                    START_DATE,
                    END_DATE,
                )
            )
        )
        * len(
            DECISION_RULES
        )
    )

    keys = [
        (
            row["target_date"],
            row["decision_rule"],
        )
        for row in forecast_rows
    ]

    duplicate_keys = (
        len(keys)
        - len(set(keys))
    )

    supported = [
        row
        for row in forecast_rows
        if row[
            "support_available"
        ] is True
    ]

    no_lookahead_violations = [
        row
        for row in supported
        if not row[
            "issued_before_decision"
        ]
    ]

    availability_violations = [
        row
        for row in supported
        if (
            parse_utc(
                row[
                    "selected_run_init_utc"
                ]
            )
            + timedelta(
                hours=
                    AVAILABILITY_DELAY_HOURS
            )
            > parse_utc(
                row[
                    "decision_time_utc"
                ]
            )
        )
    ]

    local_day_violations = [
        row
        for row in supported
        if not (
            row[
                "complete_local_day"
            ]
            and int(
                row[
                    "hourly_rows"
                ]
            ) == 24
            and int(
                row[
                    "unique_local_hours"
                ]
            ) == 24
            and int(
                row[
                    "nonmissing_temperature_rows"
                ]
            ) == 24
            and row[
                "hours_00_to_23"
            ]
        )
    ]

    historical_new = [
        row
        for row in forecast_rows
        if (
            date.fromisoformat(
                row["target_date"]
            )
            <= HISTORICAL_AUDIT_END
        )
    ]

    historical_supported = [
        row
        for row in historical_new
        if row[
            "support_available"
        ] is True
    ]

    market_rows = [
        row
        for row in forecast_rows
        if (
            date.fromisoformat(
                row["target_date"]
            )
            >= MARKET_START
        )
    ]

    market_supported = [
        row
        for row in market_rows
        if row[
            "support_available"
        ] is True
    ]

    external_rows = [
        row
        for row in forecast_rows
        if (
            date.fromisoformat(
                row["target_date"]
            )
            >= EXTERNAL_START
        )
    ]

    external_supported = [
        row
        for row in external_rows
        if row[
            "support_available"
        ] is True
    ]

    supported_by_rule = Counter(
        row["decision_rule"]
        for row in supported
    )

    unsupported_by_rule = Counter(
        row["decision_rule"]
        for row in forecast_rows
        if not row[
            "support_available"
        ]
    )

    selected_tier = Counter(
        row["selection_tier"]
        for row in supported
    )

    unique_supported_dates_market = len(
        {
            row["target_date"]
            for row in market_supported
        }
    )

    unique_supported_dates_external = len(
        {
            row["target_date"]
            for row in external_supported
        }
    )

    checks = [
        {
            "check":
                "target_calendar_dates",
            "passed":
                (
                    len(
                        set(
                            row[
                                "target_date"
                            ]
                            for row in
                            forecast_rows
                        )
                    )
                    == 899
                ),
            "observed":
                len(
                    set(
                        row["target_date"]
                        for row in forecast_rows
                    )
                ),
            "expected":
                899,
            "notes":
                "",
        },
        {
            "check":
                "theoretical_date_rule_keys",
            "passed":
                len(forecast_rows)
                == expected_keys,
            "observed":
                len(forecast_rows),
            "expected":
                expected_keys,
            "notes":
                "",
        },
        {
            "check":
                "no_duplicate_date_rule_keys",
            "passed":
                duplicate_keys == 0,
            "observed":
                duplicate_keys,
            "expected":
                0,
            "notes":
                "",
        },
        {
            "check":
                "supported_runs_never_after_decision",
            "passed":
                len(
                    no_lookahead_violations
                ) == 0,
            "observed":
                len(
                    no_lookahead_violations
                ),
            "expected":
                0,
            "notes":
                "",
        },
        {
            "check":
                "six_hour_availability_allowance",
            "passed":
                len(
                    availability_violations
                ) == 0,
            "observed":
                len(
                    availability_violations
                ),
            "expected":
                0,
            "notes":
                "selected run issue time + 6h <= decision time",
        },
        {
            "check":
                "supported_paths_exactly_24_local_hours",
            "passed":
                len(
                    local_day_violations
                ) == 0,
            "observed":
                len(
                    local_day_violations
                ),
            "expected":
                0,
            "notes":
                "",
        },
        {
            "check":
                "historical_weather_support",
            "passed":
                len(
                    historical_supported
                ) == 2920,
            "observed":
                len(
                    historical_supported
                ),
            "expected":
                2920,
            "notes":
                (
                    "16 Mar 2024 to "
                    "15 Mar 2026"
                ),
        },
        {
            "check":
                "historical_reconciliation_count",
            "passed":
                len(
                    reconciliation
                ) == 2920,
            "observed":
                len(
                    reconciliation
                ),
            "expected":
                2920,
            "notes":
                "",
        },
        {
            "check":
                "historical_method_comparison_generated",
            "passed":
                len(
                    reconciliation
                ) == 2920,
            "observed":
                len(
                    reconciliation
                ),
            "expected":
                2920,
            "notes":
                (
                    "V2 differences are diagnostic only: "
                    "the final pipeline applies the frozen "
                    "six-hour availability allowance and "
                    "core-before-repair priority."
                ),
        },
        {
            "check":
                "unsupported_keys_have_explicit_reason",
            "passed":
                all(
                    bool(
                        row[
                            "unsupported_reason"
                        ]
                    )
                    for row in
                    unsupported_rows
                ),
            "observed":
                sum(
                    not bool(
                        row[
                            "unsupported_reason"
                        ]
                    )
                    for row in
                    unsupported_rows
                ),
            "expected":
                0,
            "notes":
                "",
        },
    ]

    write_csv(
        CHECKS_CSV,
        [
            "check",
            "passed",
            "observed",
            "expected",
            "notes",
        ],
        checks,
    )

    status = (
        "PASS"
        if all(
            row["passed"]
            for row in checks
        )
        else "FAILED"
    )

    summary = {
        "status":
            status,
        "source":
            "Open-Meteo Single Runs",
        "availability_delay_hours":
            AVAILABILITY_DELAY_HOURS,
        "cycle_priority":
            "00/12 core first; 06/18 repair only if no valid core path",
        "historical_v2_comparison_role":
            "diagnostic_only_not_acceptance_gate",

        "forecast_model":
            MODEL,
        "latitude":
            LATITUDE,
        "longitude":
            LONGITUDE,
        "timezone":
            "Asia/Hong_Kong",
        "hourly_variable":
            VARIABLE,
        "forecast_days":
            FORECAST_DAYS,
        "elevation_override":
            None,
        "start_date":
            START_DATE.isoformat(),
        "end_date":
            END_DATE.isoformat(),
        "target_dates":
            899,
        "theoretical_date_rule_keys":
            expected_keys,
        "supported_date_rule_keys":
            len(supported),
        "unsupported_date_rule_keys":
            len(
                unsupported_rows
            ),
        "supported_by_rule":
            dict(
                supported_by_rule
            ),
        "unsupported_by_rule":
            dict(
                unsupported_by_rule
            ),
        "selection_tier_counts":
            dict(
                selected_tier
            ),
        "historical_target_dates":
            730,
        "historical_date_rule_keys":
            len(
                historical_new
            ),
        "historical_supported_keys":
            len(
                historical_supported
            ),
        "historical_reconciliation_rows":
            len(
                reconciliation
            ),
        "historical_reconciliation_mismatches":
            len(
                mismatches
            ),
        "market_period_theoretical_keys":
            len(
                market_rows
            ),
        "market_period_supported_keys":
            len(
                market_supported
            ),
        "market_period_supported_dates":
            unique_supported_dates_market,
        "external_jul_aug_theoretical_keys":
            len(
                external_rows
            ),
        "external_jul_aug_supported_keys":
            len(
                external_supported
            ),
        "external_jul_aug_supported_dates":
            unique_supported_dates_external,
        "unique_runs_consulted":
            len(
                store.inventory_rows
            ),
        "successful_runs_consulted":
            sum(
                bool(
                    row["success"]
                )
                for row in
                store.inventory_rows
            ),
        "legacy_raw_cache_runs":
            sum(
                row[
                    "source_origin"
                ]
                == "legacy_raw_cache_copy"
                for row in
                store.inventory_rows
            ),
        "final_raw_cache_runs":
            sum(
                row[
                    "source_origin"
                ]
                == "final_raw_cache"
                for row in
                store.inventory_rows
            ),
        "open_meteo_api_runs":
            sum(
                row[
                    "source_origin"
                ]
                == "open_meteo_api"
                for row in
                store.inventory_rows
            ),
        "no_lookahead_violations":
            len(
                no_lookahead_violations
            ),
        "availability_allowance_violations":
            len(
                availability_violations
            ),

        "local_day_integrity_violations":
            len(
                local_day_violations
            ),
        "historical_policy_preflight":
            policy_summary,
        "request_plan_csv":
            str(
                REQUEST_PLAN_CSV
            ),
        "forecast_panel_csv":
            str(
                FORECAST_PANEL_CSV
            ),
        "forecast_panel_sha256":
            sha256_file(
                FORECAST_PANEL_CSV
            ),
        "generated_utc":
            datetime.now(
                UTC
            ).isoformat(),
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "status="
        + status
    )

    print(
        "targets=899"
    )

    print(
        "theoretical_keys="
        + str(
            expected_keys
        )
    )

    print(
        "supported_keys="
        + str(
            len(supported)
        )
    )

    print(
        "unsupported_keys="
        + str(
            len(
                unsupported_rows
            )
        )
    )

    print(
        "historical_support="
        + str(
            len(
                historical_supported
            )
        )
    )

    print(
        "historical_mismatches="
        + str(
            len(
                mismatches
            )
        )
    )

    print(
        "market_supported="
        + str(
            len(
                market_supported
            )
        )
    )

    print(
        "jul_aug_supported="
        + str(
            len(
                external_supported
            )
        )
    )

    if status != "PASS":
        if mismatches:
            print(
                "first_historical_mismatches="
                + json.dumps(
                    mismatches[:10]
                )
            )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
