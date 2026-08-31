from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Final empirical target period
# ---------------------------------------------------------------------------

START_DATE = date(2024, 3, 16)
END_DATE = date(2026, 8, 31)

HISTORICAL_REFERENCE_START = date(2024, 3, 16)
HISTORICAL_REFERENCE_END = date(2026, 3, 15)

HONG_KONG_TZ = ZoneInfo("Asia/Hong_Kong")


# ---------------------------------------------------------------------------
# Official HKO sources
# ---------------------------------------------------------------------------

CLMMAXT_API = (
    "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php"
)

CLMMAXT_DATA_TYPE = "CLMMAXT"
CLMMAXT_STATION = "HKO"

DAILY_EXTRACT_ANNUAL_URL = (
    "https://www.hko.gov.hk/cis/dailyExtract/"
    "dailyExtract_2026.xml"
)

DAILY_EXTRACT_MONTHLY_URL = (
    "https://www.hko.gov.hk/cis/dailyExtract/"
    "dailyExtract_202608.xml"
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RAW_DIR = Path("data/raw/hko")
PROCESSED_DIR = Path("data/processed/final_pipeline")
AUDIT_DIR = Path("outputs/final_pipeline/audit")

CANONICAL_CSV = (
    PROCESSED_DIR / "hko_daily_max_temperature.csv"
)

SUMMARY_JSON = (
    AUDIT_DIR / "hko_summary.json"
)

CHECKS_CSV = (
    AUDIT_DIR / "hko_integrity_checks.csv"
)

PROVENANCE_CSV = (
    AUDIT_DIR / "hko_provenance.csv"
)

RECONCILIATION_CSV = (
    AUDIT_DIR / "hko_overlap_reconciliation.csv"
)

SOURCE_OVERLAP_CSV = (
    AUDIT_DIR / "hko_source_overlap.csv"
)

OLD_PANEL = Path(
    "outputs/v2/diagnostics/"
    "05_weather_only_forecast_residual_panel.csv"
)


@dataclass(frozen=True)
class HKORecord:
    target_date: date
    hko_daily_max_c: float
    source_system: str
    source_url: str
    source_period: str


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def request_bytes(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "UCL-MSc-Financial-Mathematics-"
                "Dissertation-Reproducibility/1.0"
        },
    )

    with urllib.request.urlopen(
        req,
        timeout=90,
    ) as response:
        return response.read()


# ===========================================================================
# CLMMAXT HISTORICAL ARCHIVE
# ===========================================================================


def normalise_field_name(value: Any) -> str:
    text = str(value).strip().lower()

    text = (
        text.replace("（", "(")
        .replace("）", ")")
        .replace("℃", "c")
        .replace("°c", "c")
    )

    text = re.sub(r"\s+", " ", text)
    text = re.sub(
        r"[^0-9a-z\u4e00-\u9fff]+",
        "",
        text,
    )

    return text


def extract_field_name(field: Any) -> str:
    if isinstance(field, str):
        return field

    if isinstance(field, dict):
        for key in (
            "name",
            "Name",
            "field",
            "Field",
            "fieldName",
            "label",
            "Label",
            "description",
            "Description",
        ):
            value = field.get(key)

            if isinstance(value, str) and value.strip():
                return value

        strings = [
            value
            for value in field.values()
            if isinstance(value, str) and value.strip()
        ]

        if strings:
            return strings[0]

    return str(field)


def extract_field_names(
    payload: dict[str, Any],
) -> list[str]:
    fields = payload.get("fields")

    if not isinstance(fields, list):
        raise RuntimeError(
            "CLMMAXT response lacks list-valued 'fields'."
        )

    return [
        extract_field_name(field)
        for field in fields
    ]


def locate_field(
    names: list[str],
    candidates: tuple[str, ...],
) -> int:
    normalised_names = [
        normalise_field_name(name)
        for name in names
    ]

    normalised_candidates = [
        normalise_field_name(candidate)
        for candidate in candidates
    ]

    for candidate in normalised_candidates:
        for i, name in enumerate(normalised_names):
            if name == candidate:
                return i

    for candidate in normalised_candidates:
        for i, name in enumerate(normalised_names):
            if candidate and candidate in name:
                return i

    raise RuntimeError(
        "Unable to locate HKO field.\n"
        f"Candidates: {candidates}\n"
        f"Available: {names}"
    )


def parse_float(value: Any) -> float | None:
    if value is None:
        return None

    text = str(value).strip()

    if text.lower() in {
        "",
        "-",
        "--",
        "---",
        "***",
        "n/a",
        "na",
        "null",
        "none",
    }:
        return None

    # Preserve legitimate signed decimal numbers even if
    # the web source later adds a footnote marker.
    match = re.search(
        r"[-+]?\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return None

    return float(match.group(0))


def build_clmmaxt_url(year: int) -> str:
    query = urllib.parse.urlencode(
        {
            "dataType": CLMMAXT_DATA_TYPE,
            "lang": "en",
            "rformat": "json",
            "station": CLMMAXT_STATION,
            "year": year,
        }
    )

    return f"{CLMMAXT_API}?{query}"


def fetch_clmmaxt(
    year: int,
    refresh: bool,
) -> tuple[Path, str, int]:
    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    url = build_clmmaxt_url(year)

    path = RAW_DIR / f"clmmaxt_{year}.json.gz"

    if path.exists() and not refresh:
        return (
            path,
            url,
            path.stat().st_size,
        )

    raw = request_bytes(url)

    # Validate source before caching.
    json.loads(
        raw.decode("utf-8")
    )

    buffer = io.BytesIO()

    # Deterministic gzip header.
    with gzip.GzipFile(
        fileobj=buffer,
        mode="wb",
        mtime=0,
    ) as gz:
        gz.write(raw)

    compressed = buffer.getvalue()

    path.write_bytes(compressed)

    return (
        path,
        url,
        len(compressed),
    )


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(
        path,
        "rt",
        encoding="utf-8",
    ) as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Unexpected payload type in {path}"
        )

    return payload


def parse_clmmaxt(
    payload: dict[str, Any],
    year_requested: int,
    source_url: str,
) -> list[HKORecord]:
    names = extract_field_names(payload)

    data = payload.get("data")

    if not isinstance(data, list):
        raise RuntimeError(
            "CLMMAXT response lacks list-valued 'data'."
        )

    year_i = locate_field(
        names,
        ("Year", "年"),
    )

    month_i = locate_field(
        names,
        ("Month", "月"),
    )

    day_i = locate_field(
        names,
        ("Day", "日"),
    )

    max_i = locate_field(
        names,
        (
            "Temperature(C)",
            "Temperature",
            "Max Temperature",
            "Maximum Temperature",
            "Value",
            "數值",
            "数值",
        ),
    )

    records: list[HKORecord] = []

    for row_number, row in enumerate(
        data,
        start=1,
    ):
        if not isinstance(row, list):
            raise RuntimeError(
                f"CLMMAXT row {row_number} is not a list."
            )

        required = max(
            year_i,
            month_i,
            day_i,
            max_i,
        )

        if len(row) <= required:
            raise RuntimeError(
                f"CLMMAXT row {row_number} is too short."
            )

        try:
            target = date(
                int(str(row[year_i]).strip()),
                int(str(row[month_i]).strip()),
                int(str(row[day_i]).strip()),
            )
        except Exception as exc:
            raise RuntimeError(
                f"Invalid date in CLMMAXT row {row_number}."
            ) from exc

        value = parse_float(
            row[max_i]
        )

        if value is None:
            continue

        records.append(
            HKORecord(
                target_date=target,
                hko_daily_max_c=value,
                source_system=
                    "HKO_CLMMAXT_OPEN_DATA",
                source_url=source_url,
                source_period=str(year_requested),
            )
        )

    return records


# ===========================================================================
# DAILY EXTRACT CURRENT-MONTH SUPPLEMENT
# ===========================================================================


def _curl_json_candidate(
    url: str,
) -> tuple[dict[str, Any] | None, bytes | None, str]:
    """
    Retrieve one official HKO Daily Extract candidate.

    Returns:
        (JSON payload or None,
         raw bytes or None,
         diagnostic string)
    """
    result = subprocess.run(
        [
            "curl",
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            "90",
            "--write-out",
            "\\n__HTTP_STATUS__:%{http_code}",
            url,
        ],
        check=False,
        capture_output=True,
    )

    if result.returncode != 0:
        return (
            None,
            None,
            (
                f"curl_exit={result.returncode}; "
                + result.stderr.decode(
                    "utf-8",
                    errors="replace",
                ).strip()
            ),
        )

    raw = result.stdout

    marker = b"\n__HTTP_STATUS__:"

    if marker not in raw:
        return (
            None,
            None,
            "curl response lacks HTTP status marker",
        )

    body, status_bytes = raw.rsplit(
        marker,
        1,
    )

    status = status_bytes.decode(
        "ascii",
        errors="replace",
    ).strip()

    if status != "200":
        return (
            None,
            None,
            f"http_status={status}",
        )

    try:
        payload = json.loads(
            body.decode(
                "utf-8",
                errors="strict",
            )
        )
    except Exception as exc:
        return (
            None,
            None,
            f"http_status=200 but invalid JSON: {exc}",
        )

    if not isinstance(payload, dict):
        return (
            None,
            None,
            "valid JSON but top level is not an object",
        )

    return (
        payload,
        body,
        "http_status=200; valid_json",
    )


def _payload_contains_august(
    payload: dict[str, Any],
) -> bool:
    stn = payload.get("stn")

    if not isinstance(stn, dict):
        return False

    data = stn.get("data")

    if not isinstance(data, list):
        return False

    for block in data:
        if not isinstance(block, dict):
            continue

        try:
            month = int(
                str(
                    block.get("month")
                ).strip()
            )
        except Exception:
            continue

        if month != 8:
            continue

        day_data = block.get(
            "dayData"
        )

        return (
            isinstance(day_data, list)
            and len(day_data) > 0
        )

    return False


def fetch_daily_extract(
    refresh: bool,
) -> tuple[Path, str, int]:
    """
    Retrieve August 2026 from the official HKO Daily Extract system.

    HKO's webpage uses two possible source forms:

      dailyExtract_YYYY.xml
      dailyExtract_YYYYMM.xml

    The latter is only used by the webpage while a requested month is in
    daily-update mode. Once that month has entered the annual/current-year
    extract, the webpage uses the YYYY file.

    We therefore test the official annual file first and use the current-month
    file only as a fallback. A candidate is accepted only if it is valid JSON
    and contains a non-empty August block.
    """
    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = RAW_DIR / (
        "dailyExtract_august_2026.json"
    )

    meta_path = RAW_DIR / (
        "dailyExtract_august_2026_source.json"
    )

    if (
        path.exists()
        and meta_path.exists()
        and not refresh
    ):
        meta = json.loads(
            meta_path.read_text(
                encoding="utf-8"
            )
        )

        return (
            path,
            meta["selected_url"],
            path.stat().st_size,
        )

    candidates = [
        (
            "annual_current_year",
            DAILY_EXTRACT_ANNUAL_URL,
        ),
        (
            "monthly_daily_update",
            DAILY_EXTRACT_MONTHLY_URL,
        ),
    ]

    diagnostics = []

    for source_mode, url in candidates:
        (
            payload,
            raw,
            diagnostic,
        ) = _curl_json_candidate(url)

        row = {
            "source_mode":
                source_mode,
            "url":
                url,
            "transport":
                diagnostic,
            "contains_august":
                False,
        }

        if payload is None or raw is None:
            diagnostics.append(row)
            continue

        contains_august = (
            _payload_contains_august(
                payload
            )
        )

        row["contains_august"] = (
            contains_august
        )

        diagnostics.append(row)

        if not contains_august:
            continue

        path.write_bytes(raw)

        meta_path.write_text(
            json.dumps(
                {
                    "selected_mode":
                        source_mode,
                    "selected_url":
                        url,
                    "candidate_diagnostics":
                        diagnostics,
                    "selected_utc":
                        datetime.now(
                            timezone.utc
                        ).isoformat(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        return (
            path,
            url,
            len(raw),
        )

    raise RuntimeError(
        "No official HKO Daily Extract candidate "
        "returned a valid non-empty August 2026 block. "
        f"Diagnostics={json.dumps(diagnostics)}"
    )


def parse_daily_extract(
    payload: dict[str, Any],
    hk_today: date,
    source_url: str,
) -> tuple[list[HKORecord], list[date]]:
    stn = payload.get("stn")

    if not isinstance(stn, dict):
        raise RuntimeError(
            "Daily Extract payload lacks object 'stn'."
        )

    data = stn.get("data")

    if not isinstance(data, list):
        raise RuntimeError(
            "Daily Extract payload lacks list 'stn.data'."
        )

    month_block = None

    for block in data:
        if not isinstance(block, dict):
            continue

        try:
            month = int(
                str(block.get("month")).strip()
            )
        except Exception:
            continue

        if month == 8:
            month_block = block
            break

    if month_block is None:
        raise RuntimeError(
            "Daily Extract payload contains no August block."
        )

    day_data = month_block.get("dayData")

    if not isinstance(day_data, list):
        raise RuntimeError(
            "Daily Extract August block lacks dayData."
        )

    records: list[HKORecord] = []
    provisional_skipped: list[date] = []

    for row_number, row in enumerate(
        day_data,
        start=1,
    ):
        if not isinstance(row, list):
            continue

        # HKO webpage source proves:
        #   [0] = Day
        #   [1] = Mean Pressure
        #   [2] = Absolute Daily Max
        if len(row) < 3:
            continue

        day_match = re.match(
            r"\s*(\d{1,2})",
            str(row[0]),
        )

        if not day_match:
            # Summary/normal rows are ignored.
            continue

        day_number = int(
            day_match.group(1)
        )

        try:
            target = date(
                2026,
                8,
                day_number,
            )
        except ValueError:
            continue

        value = parse_float(
            row[2]
        )

        if value is None:
            continue

        # Never use a current-day value, even if HKO's
        # webpage happens to expose an intraday/provisional number.
        # A settlement-day target is accepted only after that
        # Hong Kong calendar day has ended.
        if target >= hk_today:
            provisional_skipped.append(
                target
            )
            continue

        records.append(
            HKORecord(
                target_date=target,
                hko_daily_max_c=value,
                source_system=
                    "HKO_DAILY_EXTRACT_CURRENT_MONTH",
                source_url=source_url,
                source_period="2026-08",
            )
        )

    return (
        records,
        provisional_skipped,
    )


# ===========================================================================
# HISTORICAL RECONCILIATION
# ===========================================================================


def load_old_reference() -> dict[date, float]:
    if not OLD_PANEL.exists():
        raise RuntimeError(
            "Historical audited weather panel not found: "
            f"{OLD_PANEL}"
        )

    values: dict[
        date,
        set[float],
    ] = defaultdict(set)

    with OLD_PANEL.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        required = {
            "target_date",
            "hko_daily_max_c",
        }

        missing = (
            required
            - set(reader.fieldnames or [])
        )

        if missing:
            raise RuntimeError(
                "Historical weather panel lacks columns: "
                f"{sorted(missing)}"
            )

        for row in reader:
            target = date.fromisoformat(
                row["target_date"][:10]
            )

            if (
                HISTORICAL_REFERENCE_START
                <= target
                <= HISTORICAL_REFERENCE_END
            ):
                values[target].add(
                    float(
                        row[
                            "hko_daily_max_c"
                        ]
                    )
                )

    result: dict[date, float] = {}

    for target, observed in values.items():
        if len(observed) != 1:
            raise RuntimeError(
                "Historical HKO values are internally "
                f"inconsistent for {target}: "
                f"{sorted(observed)}"
            )

        result[target] = next(
            iter(observed)
        )

    return result


# ===========================================================================
# OUTPUT WRITERS
# ===========================================================================


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
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


# ===========================================================================
# MAIN
# ===========================================================================


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-download all official HKO sources.",
    )

    args = parser.parse_args()

    hk_today = datetime.now(
        HONG_KONG_TZ
    ).date()

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    provenance: list[
        dict[str, Any]
    ] = []

    archive_records: list[
        HKORecord
    ] = []

    # -----------------------------------------------------------------------
    # A. Historical CLMMAXT archive
    # -----------------------------------------------------------------------

    for year in (
        2024,
        2025,
        2026,
    ):
        path, url, size = fetch_clmmaxt(
            year,
            args.refresh,
        )

        payload = load_gzip_json(
            path
        )

        parsed = parse_clmmaxt(
            payload,
            year,
            url,
        )

        archive_records.extend(
            parsed
        )

        provenance.append(
            {
                "source_system":
                    "HKO_CLMMAXT_OPEN_DATA",
                "source_period":
                    str(year),
                "source_url":
                    url,
                "cache_path":
                    str(path),
                "sha256":
                    sha256_file(path),
                "bytes":
                    size,
                "parsed_rows":
                    len(parsed),
                "retrieved_utc":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
            }
        )

    # -----------------------------------------------------------------------
    # B. Current-month Daily Extract
    # -----------------------------------------------------------------------

    daily_path, daily_url, daily_size = (
        fetch_daily_extract(
            args.refresh
        )
    )

    daily_payload = json.loads(
        daily_path.read_text(
            encoding="utf-8"
        )
    )

    (
        daily_records,
        provisional_skipped,
    ) = parse_daily_extract(
        daily_payload,
        hk_today,
        daily_url,
    )

    provenance.append(
        {
            "source_system":
                "HKO_DAILY_EXTRACT_CURRENT_MONTH",
            "source_period":
                "2026-08",
            "source_url":
                daily_url,
            "cache_path":
                str(daily_path),
            "sha256":
                sha256_file(daily_path),
            "bytes":
                daily_size,
            "parsed_rows":
                len(daily_records),
            "retrieved_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }
    )

    # -----------------------------------------------------------------------
    # C. Merge official sources with strict overlap validation
    # -----------------------------------------------------------------------

    final_by_date: dict[
        date,
        HKORecord,
    ] = {}

    archive_duplicates = []

    for record in archive_records:
        target = record.target_date

        if not (
            START_DATE
            <= target
            <= END_DATE
        ):
            continue

        existing = final_by_date.get(
            target
        )

        if existing is not None:
            archive_duplicates.append(
                target
            )

            if abs(
                existing.hko_daily_max_c
                - record.hko_daily_max_c
            ) > 1e-10:
                raise RuntimeError(
                    "Conflicting CLMMAXT values for "
                    f"{target}."
                )

            continue

        final_by_date[target] = record

    source_overlap_rows = []
    source_overlap_mismatches = []

    for record in daily_records:
        target = record.target_date

        if not (
            START_DATE
            <= target
            <= END_DATE
        ):
            continue

        existing = final_by_date.get(
            target
        )

        if existing is None:
            final_by_date[target] = record
            continue

        difference = (
            record.hko_daily_max_c
            - existing.hko_daily_max_c
        )

        matched = (
            abs(difference)
            < 1e-10
        )

        source_overlap_rows.append(
            {
                "target_date":
                    target.isoformat(),
                "clmmaxt_value_c":
                    f"{existing.hko_daily_max_c:.1f}",
                "daily_extract_value_c":
                    f"{record.hko_daily_max_c:.1f}",
                "difference_c":
                    f"{difference:.10f}",
                "exact_match":
                    matched,
            }
        )

        if not matched:
            source_overlap_mismatches.append(
                target
            )

    if source_overlap_mismatches:
        raise RuntimeError(
            "CLMMAXT and Daily Extract disagree on "
            f"{len(source_overlap_mismatches)} dates."
        )

    # -----------------------------------------------------------------------
    # D. Canonical final HKO table
    # -----------------------------------------------------------------------

    canonical_rows = []

    for target in sorted(final_by_date):
        record = final_by_date[target]

        canonical_rows.append(
            {
                "target_date":
                    target.isoformat(),
                "hko_daily_max_c":
                    f"{record.hko_daily_max_c:.1f}",
                "source_system":
                    record.source_system,
                "source_period":
                    record.source_period,
                "source_url":
                    record.source_url,
            }
        )

    write_csv(
        CANONICAL_CSV,
        [
            "target_date",
            "hko_daily_max_c",
            "source_system",
            "source_period",
            "source_url",
        ],
        canonical_rows,
    )

    # -----------------------------------------------------------------------
    # E. Reconcile against previously audited 730-date HKO history
    # -----------------------------------------------------------------------

    old_reference = (
        load_old_reference()
    )

    reconciliation_rows = []
    historical_mismatches = []

    for target in sorted(
        old_reference
    ):
        old_value = (
            old_reference[target]
        )

        current = (
            final_by_date.get(target)
        )

        new_value = (
            None
            if current is None
            else current.hko_daily_max_c
        )

        matched = (
            new_value is not None
            and abs(
                new_value
                - old_value
            ) < 1e-10
        )

        if not matched:
            historical_mismatches.append(
                target
            )

        reconciliation_rows.append(
            {
                "target_date":
                    target.isoformat(),
                "historical_hko_daily_max_c":
                    f"{old_value:.1f}",
                "reacquired_hko_daily_max_c":
                    (
                        ""
                        if new_value is None
                        else f"{new_value:.1f}"
                    ),
                "difference_c":
                    (
                        ""
                        if new_value is None
                        else
                        f"{new_value-old_value:.10f}"
                    ),
                "exact_match":
                    matched,
            }
        )

    write_csv(
        RECONCILIATION_CSV,
        [
            "target_date",
            "historical_hko_daily_max_c",
            "reacquired_hko_daily_max_c",
            "difference_c",
            "exact_match",
        ],
        reconciliation_rows,
    )

    write_csv(
        SOURCE_OVERLAP_CSV,
        [
            "target_date",
            "clmmaxt_value_c",
            "daily_extract_value_c",
            "difference_c",
            "exact_match",
        ],
        source_overlap_rows,
    )

    write_csv(
        PROVENANCE_CSV,
        [
            "source_system",
            "source_period",
            "source_url",
            "cache_path",
            "sha256",
            "bytes",
            "parsed_rows",
            "retrieved_utc",
        ],
        provenance,
    )

    # -----------------------------------------------------------------------
    # F. Integrity checks
    # -----------------------------------------------------------------------

    expected_dates = set(
        daterange(
            START_DATE,
            END_DATE,
        )
    )

    actual_dates = set(
        final_by_date
    )

    missing_dates = sorted(
        expected_dates
        - actual_dates
    )

    extra_dates = sorted(
        actual_dates
        - expected_dates
    )

    values = [
        record.hko_daily_max_c
        for record in
        final_by_date.values()
    ]

    one_decimal = all(
        abs(
            value * 10
            - round(value * 10)
        ) < 1e-8
        for value in values
    )

    plausible = all(
        -10.0 <= value <= 50.0
        for value in values
    )

    expected_reference_dates = set(
        daterange(
            HISTORICAL_REFERENCE_START,
            HISTORICAL_REFERENCE_END,
        )
    )

    historical_reference_complete = (
        set(old_reference)
        == expected_reference_dates
    )

    historical_exact = (
        historical_reference_complete
        and len(
            historical_mismatches
        ) == 0
    )

    # -----------------------------------------------------------
    # Completion status:
    #
    # COMPLETE:
    #   all 899 dates available.
    #
    # PENDING_FINAL_DATE:
    #   exactly 31 Aug is missing while that Hong Kong
    #   day has not yet completed.
    #
    # FAILED:
    #   anything else.
    # -----------------------------------------------------------

    if not missing_dates:
        status = "COMPLETE"

    elif (
        missing_dates == [END_DATE]
        and hk_today <= END_DATE
    ):
        status = "PENDING_FINAL_DATE"

    else:
        status = "FAILED"

    hard_checks = [
        (
            "expected_calendar_count",
            len(expected_dates) == 899,
            len(expected_dates),
            899,
        ),
        (
            "no_extra_dates",
            len(extra_dates) == 0,
            len(extra_dates),
            0,
        ),
        (
            "no_archive_duplicate_dates",
            len(archive_duplicates) == 0,
            len(archive_duplicates),
            0,
        ),
        (
            "one_decimal_precision",
            one_decimal,
            one_decimal,
            True,
        ),
        (
            "plausible_temperature_range",
            plausible,
            (
                f"{min(values):.1f} to "
                f"{max(values):.1f}"
                if values
                else "none"
            ),
            "-10 to 50 C",
        ),
        (
            "historical_reference_count",
            len(old_reference) == 730,
            len(old_reference),
            730,
        ),
        (
            "historical_overlap_exact",
            historical_exact,
            len(historical_mismatches),
            0,
        ),
        (
            "official_source_overlap_exact",
            len(source_overlap_mismatches) == 0,
            len(source_overlap_mismatches),
            0,
        ),
    ]

    checks_rows = []

    for (
        name,
        passed,
        observed,
        expected,
    ) in hard_checks:
        checks_rows.append(
            {
                "check": name,
                "passed": passed,
                "observed": observed,
                "expected": expected,
                "notes": "",
            }
        )

    checks_rows.append(
        {
            "check":
                "target_period_completeness",
            "passed":
                status in {
                    "COMPLETE",
                    "PENDING_FINAL_DATE",
                },
            "observed":
                len(final_by_date),
            "expected":
                (
                    899
                    if status == "COMPLETE"
                    else "898 while 31 Aug pending"
                ),
            "notes":
                ",".join(
                    d.isoformat()
                    for d in missing_dates
                ),
        }
    )

    write_csv(
        CHECKS_CSV,
        [
            "check",
            "passed",
            "observed",
            "expected",
            "notes",
        ],
        checks_rows,
    )

    hard_failure_names = [
        row["check"]
        for row in checks_rows
        if not row["passed"]
    ]

    if hard_failure_names:
        status = "FAILED"

    source_counts: dict[str, int] = (
        defaultdict(int)
    )

    for record in final_by_date.values():
        source_counts[
            record.source_system
        ] += 1

    summary = {
        "status": status,
        "hong_kong_run_date":
            hk_today.isoformat(),
        "dataset":
            "HKO Absolute Daily Maximum Temperature",
        "start_date":
            START_DATE.isoformat(),
        "end_date":
            END_DATE.isoformat(),
        "expected_calendar_dates":
            len(expected_dates),
        "observed_dates":
            len(final_by_date),
        "missing_dates": [
            d.isoformat()
            for d in missing_dates
        ],
        "first_observed_date":
            (
                min(final_by_date)
                .isoformat()
                if final_by_date
                else None
            ),
        "last_observed_date":
            (
                max(final_by_date)
                .isoformat()
                if final_by_date
                else None
            ),
        "minimum_temperature_c":
            (
                min(values)
                if values
                else None
            ),
        "maximum_temperature_c":
            (
                max(values)
                if values
                else None
            ),
        "source_counts":
            dict(source_counts),
        "daily_extract_accepted_rows":
            len(daily_records),
        "daily_extract_provisional_dates_skipped":
            [
                d.isoformat()
                for d in sorted(
                    set(
                        provisional_skipped
                    )
                )
            ],
        "historical_overlap_reference_dates":
            len(old_reference),
        "historical_overlap_mismatches":
            len(historical_mismatches),
        "official_source_overlap_dates":
            len(source_overlap_rows),
        "official_source_overlap_mismatches":
            len(source_overlap_mismatches),
        "canonical_csv":
            str(CANONICAL_CSV),
        "canonical_csv_sha256":
            sha256_file(
                CANONICAL_CSV
            ),
        "generated_utc":
            datetime.now(
                timezone.utc
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
        "observed_dates="
        + str(
            len(final_by_date)
        )
    )

    print(
        "missing_dates="
        + json.dumps(
            [
                d.isoformat()
                for d in missing_dates
            ]
        )
    )

    print(
        "daily_extract_rows="
        + str(
            len(daily_records)
        )
    )

    print(
        "historical_mismatches="
        + str(
            len(
                historical_mismatches
            )
        )
    )

    print(
        "source_overlap_mismatches="
        + str(
            len(
                source_overlap_mismatches
            )
        )
    )

    if status == "FAILED":
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
