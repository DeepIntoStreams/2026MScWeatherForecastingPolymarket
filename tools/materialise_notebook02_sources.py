#!/usr/bin/env python3
"""Recover and materialise deterministic weather sources for Notebook 02."""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


ROOT = Path.cwd()
HOME = Path.home()
ARCHIVE_BRANCH = "archive/17j-plus-18n-18y-20260726"

BUNDLE_ROOT = (
    ROOT
    / "data"
    / "interim"
    / "notebook02_sources"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "02_weather_source_bundle_manifest.json"
)

AUDIT_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_weather_source_bundle_audit.csv"
)

SCHEMA_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_weather_source_schema_inventory.csv"
)

DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "NOTEBOOK_02_SOURCE_BUNDLE.md"
)

MAX_BYTES = 180 * 1024 * 1024

REQUIRED_ROLES = {
    "hourly_forecasts",
    "daily_max_forecasts",
    "request_plan",
    "fetch_inventory",
}

OPTIONAL_ROLES = {
    "integrity_checks",
    "issues",
}

TARGET_DATE_PRIORITY = (
    "target_date",
    "event_date",
    "forecast_target_date",
    "target_local_date",
    "local_target_date",
    "target_day",
    "valid_date",
    "date",
)

VALID_TIME_PRIORITY = (
    "valid_time_utc",
    "forecast_valid_time_utc",
    "valid_datetime_utc",
    "forecast_time_utc",
    "valid_time",
    "forecast_time",
    "datetime",
    "time",
)

TEMPERATURE_PRIORITY = (
    "temperature_2m_c",
    "temperature_c",
    "forecast_temperature_c",
    "t2m_c",
    "temperature_2m",
    "forecast_tmax_c",
    "forecast_daily_max_c",
    "daily_max_forecast_c",
)

RELEVANT_KEYWORDS = (
    "18q",
    "19a",
    "june",
    "ecmwf",
    "single_run",
    "forecast",
    "hourly",
    "daily_max",
    "request_plan",
    "fetch_inventory",
    "integrity",
    "issue",
    "review_bundle",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalise(value: Any) -> str:
    text = str(value).strip().lower()
    text = text.replace("°", "")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    counts: Dict[str, int] = {}
    columns: List[str] = []

    for column in result.columns:
        base = normalise(column) or "unnamed"
        count = counts.get(base, 0)
        counts[base] = count + 1
        columns.append(
            base if count == 0 else f"{base}_{count + 1}"
        )

    result.columns = columns
    return result


def safe_filename(source: str) -> str:
    member = source.split("::")[-1]
    name = Path(member).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)

    if not name.lower().endswith(".csv"):
        name += ".csv"

    return name


def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
    )
    return result.stdout


def parse_csv(payload: bytes) -> Optional[pd.DataFrame]:
    for kwargs in (
        {},
        {"encoding": "utf-8-sig"},
        {"encoding": "latin-1"},
    ):
        try:
            frame = pd.read_csv(
                io.BytesIO(payload),
                low_memory=False,
                **kwargs,
            )

            if not frame.empty:
                return normalise_columns(frame)

        except Exception:
            continue

    return None


def role_from_source(
    source: str,
    frame: pd.DataFrame,
) -> Optional[str]:
    lower = source.lower()
    columns = set(frame.columns)

    if (
        "hourly_forecast" in lower
        or "single_run_hourly" in lower
        or (
            "hourly" in lower
            and "forecast" in lower
        )
    ):
        return "hourly_forecasts"

    if (
        "daily_max_forecast" in lower
        or "single_run_daily_max" in lower
        or (
            "daily_max" in lower
            and "forecast" in lower
        )
    ):
        return "daily_max_forecasts"

    if "request_plan" in lower:
        return "request_plan"

    if "fetch_inventory" in lower:
        return "fetch_inventory"

    if "integrity" in lower:
        return "integrity_checks"

    if "issue" in lower:
        return "issues"

    has_valid_time = any(
        column in columns
        for column in VALID_TIME_PRIORITY
    )

    has_temperature = any(
        column in columns
        for column in TEMPERATURE_PRIORITY
    )

    has_daily_max = any(
        token in column
        for column in columns
        for token in (
            "daily_max",
            "tmax",
            "maximum_temperature",
        )
    )

    if has_valid_time and has_temperature and len(frame) >= 24:
        return "hourly_forecasts"

    if has_daily_max and has_temperature:
        return "daily_max_forecasts"

    return None


def first_existing(
    columns: Iterable[str],
    priorities: Iterable[str],
) -> str:
    available = set(columns)

    for column in priorities:
        if column in available:
            return column

    return ""


def parse_target_dates(
    frame: pd.DataFrame,
) -> Tuple[str, pd.Series]:
    column = first_existing(
        frame.columns,
        TARGET_DATE_PRIORITY,
    )

    if column:
        parsed = pd.to_datetime(
            frame[column],
            errors="coerce",
        )

        if parsed.notna().any():
            return (
                column,
                parsed.dt.strftime("%Y-%m-%d"),
            )

    best_column = ""
    best_dates = pd.Series(
        pd.NA,
        index=frame.index,
        dtype="object",
    )
    best_count = 0

    for candidate in frame.columns:
        if "date" not in candidate and "day" not in candidate:
            continue

        parsed = pd.to_datetime(
            frame[candidate],
            errors="coerce",
        )

        count = int(parsed.dt.date.nunique())

        if count > best_count:
            best_count = count
            best_column = candidate
            best_dates = parsed.dt.strftime("%Y-%m-%d")

    return best_column, best_dates


def parse_valid_hkt(
    frame: pd.DataFrame,
) -> Tuple[str, pd.Series]:
    column = first_existing(
        frame.columns,
        VALID_TIME_PRIORITY,
    )

    candidates = (
        [column]
        if column
        else [
            candidate
            for candidate in frame.columns
            if (
                "valid" in candidate
                or "forecast_time" in candidate
                or candidate.endswith("_time")
                or candidate.endswith("_datetime")
            )
        ]
    )

    best_column = ""
    best_values = pd.Series(
        pd.NaT,
        index=frame.index,
        dtype="datetime64[ns, Asia/Hong_Kong]",
    )
    best_count = 0

    for candidate in dict.fromkeys(candidates):
        parsed = pd.to_datetime(
            frame[candidate],
            errors="coerce",
            utc=True,
        )

        count = int(parsed.notna().sum())

        if count > best_count:
            best_count = count
            best_column = candidate
            best_values = parsed.dt.tz_convert(
                "Asia/Hong_Kong"
            )

    return best_column, best_values


def source_priority(
    source: str,
) -> float:
    lower = source.lower()
    score = 0.0

    priorities = (
        ("18q", 100000.0),
        ("june_2026", 90000.0),
        ("local:", 50000.0),
        ("19a", 40000.0),
        ("single_run", 30000.0),
        ("processed", 10000.0),
        ("review_bundle", 5000.0),
        ("git:", 1000.0),
    )

    for token, value in priorities:
        if token in lower:
            score += value

    return score


def inspect_table(
    source: str,
    payload: bytes,
    frame: pd.DataFrame,
) -> Optional[Dict[str, Any]]:
    role = role_from_source(
        source,
        frame,
    )

    if role is None:
        return None

    date_column, target_dates = parse_target_dates(
        frame
    )

    valid_time_column, valid_hkt = parse_valid_hkt(
        frame
    )

    derived_hkt_dates = pd.Series(
        pd.NA,
        index=frame.index,
        dtype="object",
    )

    if valid_hkt.notna().any():
        derived_hkt_dates = valid_hkt.dt.strftime(
            "%Y-%m-%d"
        )

    if target_dates.notna().sum() == 0:
        final_dates = derived_hkt_dates
        coverage_basis = "valid_time_converted_to_hkt"
    else:
        final_dates = target_dates
        coverage_basis = "declared_target_date"

    date_set = set(
        final_dates.dropna().astype(str)
    )

    complete_dates: set[str] = set()

    if role == "hourly_forecasts" and valid_hkt.notna().any():
        audit = pd.DataFrame(
            {
                "target_date": final_dates,
                "valid_hkt_hour": valid_hkt.dt.floor("h"),
            }
        ).dropna()

        hour_counts = (
            audit.groupby("target_date")[
                "valid_hkt_hour"
            ]
            .nunique()
        )

        complete_dates = set(
            hour_counts.loc[
                hour_counts >= 24
            ].index.astype(str)
        )

    elif role == "daily_max_forecasts":
        complete_dates = set(date_set)

    temperature_columns = [
        column
        for column in frame.columns
        if (
            column in TEMPERATURE_PRIORITY
            or any(
                token in column
                for token in (
                    "temperature",
                    "tmax",
                    "daily_max",
                    "temp_2m",
                )
            )
        )
    ]

    june_dates = {
        date
        for date in date_set
        if "2026-06-01" <= date <= "2026-06-30"
    }

    complete_june_dates = {
        date
        for date in complete_dates
        if "2026-06-01" <= date <= "2026-06-30"
    }

    return {
        "source": source,
        "payload": payload,
        "frame": frame,
        "role": role,
        "sha256": sha256_bytes(payload),
        "rows": len(frame),
        "columns": len(frame.columns),
        "date_column": date_column,
        "valid_time_column": valid_time_column,
        "coverage_basis": coverage_basis,
        "dates": date_set,
        "complete_dates": complete_dates,
        "start_date": min(date_set) if date_set else "",
        "end_date": max(date_set) if date_set else "",
        "complete_start_date": (
            min(complete_dates)
            if complete_dates
            else ""
        ),
        "complete_end_date": (
            max(complete_dates)
            if complete_dates
            else ""
        ),
        "june_dates": june_dates,
        "complete_june_dates": complete_june_dates,
        "temperature_columns": temperature_columns,
        "score": (
            len(complete_dates) * 1_000_000.0
            + len(date_set) * 100_000.0
            + len(june_dates) * 50_000.0
            + len(frame)
            + source_priority(source)
        ),
    }


def local_roots() -> List[Path]:
    roots = [
        ROOT / "data",
        ROOT / "review_bundles",
        ROOT / "notebooks" / "data",
        ROOT / "notebooks" / "data" / "review_bundles",
    ]

    roots.extend(
        sorted(
            HOME.glob(
                "Desktop/"
                "2026MScWeatherForecastingPolymarket_local_archive_*"
            )
        )
    )

    return [
        root
        for root in roots
        if root.exists()
    ]


def relevant(
    value: str,
) -> bool:
    lower = value.lower()

    return any(
        keyword in lower
        for keyword in RELEVANT_KEYWORDS
    )


def enumerate_tables() -> List[
    Tuple[str, bytes, pd.DataFrame]
]:
    tables: List[
        Tuple[str, bytes, pd.DataFrame]
    ] = []

    seen_sources = set()

    def admit_csv(
        source: str,
        payload: bytes,
    ) -> None:
        if source in seen_sources:
            return

        seen_sources.add(source)

        if len(payload) > MAX_BYTES:
            return

        frame = parse_csv(payload)

        if frame is not None:
            tables.append(
                (
                    source,
                    payload,
                    frame,
                )
            )

    def inspect_zip(
        source: str,
        payload: bytes,
    ) -> None:
        try:
            archive = zipfile.ZipFile(
                io.BytesIO(payload)
            )
        except zipfile.BadZipFile:
            return

        with archive:
            for member in archive.infolist():
                if (
                    member.is_dir()
                    or member.file_size > MAX_BYTES
                ):
                    continue

                if not member.filename.lower().endswith(".csv"):
                    continue

                if not relevant(
                    f"{source}::{member.filename}"
                ):
                    continue

                try:
                    member_payload = archive.read(member)
                except Exception:
                    continue

                admit_csv(
                    f"{source}::{member.filename}",
                    member_payload,
                )

    for root in local_roots():
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            if "notebook02_sources" in path.parts:
                continue

            lower = str(path).lower()

            if not relevant(lower):
                continue

            if path.suffix.lower() not in {
                ".csv",
                ".zip",
            }:
                continue

            if path.stat().st_size > MAX_BYTES:
                continue

            try:
                payload = path.read_bytes()
            except OSError:
                continue

            source = f"local:{path.resolve()}"

            if path.suffix.lower() == ".zip":
                inspect_zip(source, payload)
            else:
                admit_csv(source, payload)

    archive_paths = git_text(
        "ls-tree",
        "-r",
        "--name-only",
        ARCHIVE_BRANCH,
    ).splitlines()

    for path in archive_paths:
        if not relevant(path):
            continue

        if not path.lower().endswith(
            (".csv", ".zip")
        ):
            continue

        try:
            size = int(
                git_text(
                    "cat-file",
                    "-s",
                    f"{ARCHIVE_BRANCH}:{path}",
                ).strip()
            )
        except Exception:
            continue

        if size > MAX_BYTES:
            continue

        try:
            payload = git_bytes(
                "show",
                f"{ARCHIVE_BRANCH}:{path}",
            )
        except Exception:
            continue

        source = (
            f"git:{ARCHIVE_BRANCH}:{path}"
        )

        if path.lower().endswith(".zip"):
            inspect_zip(source, payload)
        else:
            admit_csv(source, payload)

    return tables


def main() -> None:
    BUNDLE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    if BUNDLE_ROOT.exists():
        shutil.rmtree(BUNDLE_ROOT)

    BUNDLE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidates: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []

    print("Searching ordinary files and ZIP review bundles...")

    tables = enumerate_tables()

    print("Tabular forecast sources inspected:", len(tables))

    for source, payload, frame in tables:
        candidate = inspect_table(
            source,
            payload,
            frame,
        )

        if candidate is None:
            continue

        candidates.append(candidate)

    if not candidates:
        raise RuntimeError(
            "No deterministic weather source candidates were found."
        )

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    role_hashes: Dict[str, set[str]] = defaultdict(set)
    selected_rows: List[Dict[str, Any]] = []
    schema_rows: List[Dict[str, Any]] = []

    for candidate in candidates:
        role = candidate["role"]
        duplicate = (
            candidate["sha256"]
            in role_hashes[role]
        )

        audit_rows.append(
            {
                "role": role,
                "source": candidate["source"],
                "status": (
                    "DUPLICATE_CONTENT"
                    if duplicate
                    else "MATERIALISED"
                ),
                "sha256": candidate["sha256"],
                "rows": candidate["rows"],
                "columns": candidate["columns"],
                "date_column": candidate["date_column"],
                "valid_time_column": candidate["valid_time_column"],
                "coverage_basis": candidate["coverage_basis"],
                "distinct_dates": len(candidate["dates"]),
                "complete_dates": len(
                    candidate["complete_dates"]
                ),
                "start_date": candidate["start_date"],
                "end_date": candidate["end_date"],
                "complete_start_date": candidate[
                    "complete_start_date"
                ],
                "complete_end_date": candidate[
                    "complete_end_date"
                ],
                "june_dates": len(
                    candidate["june_dates"]
                ),
                "complete_june_dates": len(
                    candidate["complete_june_dates"]
                ),
                "temperature_columns": "; ".join(
                    candidate["temperature_columns"]
                ),
                "score": candidate["score"],
            }
        )

        if duplicate:
            continue

        role_hashes[role].add(
            candidate["sha256"]
        )

        role_directory = (
            BUNDLE_ROOT
            / role
        )

        role_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        index = len(
            [
                row
                for row in selected_rows
                if row["role"] == role
            ]
        ) + 1

        destination = (
            role_directory
            / (
                f"{index:02d}_"
                f"{safe_filename(candidate['source'])}"
            )
        )

        destination.write_bytes(
            candidate["payload"]
        )

        selected_rows.append(
            {
                "role": role,
                "source": candidate["source"],
                "source_sha256": candidate["sha256"],
                "bundle_path": str(
                    destination.relative_to(ROOT)
                ),
                "bundle_sha256": sha256_file(
                    destination
                ),
                "rows": candidate["rows"],
                "columns": candidate["columns"],
                "date_column": candidate["date_column"],
                "valid_time_column": candidate["valid_time_column"],
                "coverage_basis": candidate["coverage_basis"],
                "distinct_dates": len(candidate["dates"]),
                "complete_dates": len(
                    candidate["complete_dates"]
                ),
                "start_date": candidate["start_date"],
                "end_date": candidate["end_date"],
                "complete_start_date": candidate[
                    "complete_start_date"
                ],
                "complete_end_date": candidate[
                    "complete_end_date"
                ],
                "june_dates": len(
                    candidate["june_dates"]
                ),
                "complete_june_dates": len(
                    candidate["complete_june_dates"]
                ),
                "temperature_columns": candidate[
                    "temperature_columns"
                ],
                "score": candidate["score"],
            }
        )

        for column in candidate["frame"].columns:
            series = candidate["frame"][column]

            schema_rows.append(
                {
                    "role": role,
                    "bundle_path": str(
                        destination.relative_to(ROOT)
                    ),
                    "source": candidate["source"],
                    "column": column,
                    "dtype": str(series.dtype),
                    "non_missing": int(
                        series.notna().sum()
                    ),
                    "unique_values": int(
                        series.nunique(
                            dropna=True
                        )
                    ),
                    "sample_values": " | ".join(
                        series.dropna()
                        .astype(str)
                        .drop_duplicates()
                        .head(5)
                        .tolist()
                    ),
                }
            )

    selected = pd.DataFrame(selected_rows)

    roles_found = set(selected["role"])

    missing_roles = sorted(
        REQUIRED_ROLES - roles_found
    )

    if missing_roles:
        raise RuntimeError(
            "Required weather source roles are missing: "
            + ", ".join(missing_roles)
        )

    hourly = selected.loc[
        selected["role"]
        == "hourly_forecasts"
    ]

    daily = selected.loc[
        selected["role"]
        == "daily_max_forecasts"
    ]

    june_hourly = hourly.loc[
        (
            hourly["end_date"] >= "2026-06-30"
        )
        | (
            hourly["complete_end_date"]
            >= "2026-06-30"
        )
    ]

    june_daily = daily.loc[
        daily["end_date"] >= "2026-06-30"
    ]

    if june_hourly.empty:
        raise RuntimeError(
            "ZIP-aware recovery still found no hourly forecast "
            "source reaching 30 June 2026."
        )

    if june_daily.empty:
        raise RuntimeError(
            "ZIP-aware recovery found no daily maximum forecast "
            "source reaching 30 June 2026."
        )

    AUDIT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame(audit_rows).sort_values(
        [
            "role",
            "status",
            "score",
        ],
        ascending=[
            True,
            True,
            False,
        ],
    ).to_csv(
        AUDIT_PATH,
        index=False,
    )

    pd.DataFrame(schema_rows).sort_values(
        [
            "role",
            "bundle_path",
            "column",
        ]
    ).to_csv(
        SCHEMA_PATH,
        index=False,
    )

    role_summary = {}

    for role, group in selected.groupby(
        "role",
        sort=True,
    ):
        role_summary[role] = {
            "unique_files": int(len(group)),
            "total_rows": int(
                group["rows"].sum()
            ),
            "earliest_date": str(
                group["start_date"]
                .replace("", pd.NA)
                .dropna()
                .min()
            ),
            "latest_date": str(
                group["end_date"]
                .replace("", pd.NA)
                .dropna()
                .max()
            ),
            "latest_complete_date": str(
                group["complete_end_date"]
                .replace("", pd.NA)
                .dropna()
                .max()
            ),
            "files_with_june_dates": int(
                (group["june_dates"] > 0).sum()
            ),
            "maximum_june_dates_in_one_file": int(
                group["june_dates"].max()
            ),
            "maximum_complete_june_dates_in_one_file": int(
                group["complete_june_dates"].max()
            ),
        }

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "NOTEBOOK02_SOURCE_BUNDLE_READY",
        "archive_branch": ARCHIVE_BRANCH,
        "tables_inspected": len(tables),
        "required_roles": sorted(
            REQUIRED_ROLES
        ),
        "optional_roles": sorted(
            OPTIONAL_ROLES
        ),
        "role_summary": role_summary,
        "materialised_sources": (
            selected.to_dict(
                orient="records"
            )
        ),
        "june_coverage": {
            "hourly_source_reaches_2026_06_30": True,
            "daily_max_source_reaches_2026_06_30": True,
            "hourly_sources_reaching_2026_06_30": (
                june_hourly[
                    "source"
                ].tolist()
            ),
            "daily_max_sources_reaching_2026_06_30": (
                june_daily[
                    "source"
                ].tolist()
            ),
        },
        "sample_design": {
            "weather_training_requires_market": False,
            "market_evaluation_requires_market": True,
            "required_hong_kong_local_hours": 24,
            "random_split_permitted": False,
            "uncertainty_unit": "settlement_date",
            "target": "hko_daily_max_c",
        },
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

    lines = [
        "# Notebook 02 Weather Source Bundle",
        "",
        "Status: `NOTEBOOK02_SOURCE_BUNDLE_READY`",
        "",
        "The earlier materialisation attempt omitted CSV files contained "
        "inside the preserved June review bundles. This version searches "
        "ordinary files and ZIP members across the current repository, "
        "local archives and the preserved Git archive.",
        "",
        "## Sample separation",
        "",
        "The weather training panel requires a historically available "
        "deterministic forecast and its later HKO outcome. It does not "
        "require a corresponding Polymarket market.",
        "",
        "The market evaluation panel requires an audited market, a certified "
        "event book, a deterministic forecast and the HKO outcome. Model and "
        "market scores are computed only on exact common support.",
        "",
        "## Forecast path rule",
        "",
        "Hourly forecasts are converted to Asia/Hong_Kong time. A complete "
        "candidate local-day path requires 24 unique local hours. Exact run "
        "grouping and issue-time admission are applied by the next Notebook "
        "02 adapter; this source bundle records the available raw evidence.",
        "",
        "## Source coverage",
        "",
    ]

    for role, summary in sorted(
        role_summary.items()
    ):
        lines.extend(
            [
                f"### {role.replace('_', ' ').title()}",
                "",
                f"- Unique files: {summary['unique_files']}",
                f"- Total rows: {summary['total_rows']}",
                f"- Earliest date: {summary['earliest_date']}",
                f"- Latest date: {summary['latest_date']}",
                (
                    "- Latest date with at least 24 recorded local hours: "
                    f"{summary['latest_complete_date']}"
                ),
                (
                    "- Maximum June dates in one file: "
                    f"{summary['maximum_june_dates_in_one_file']}"
                ),
                (
                    "- Maximum complete June dates in one file: "
                    f"{summary['maximum_complete_june_dates_in_one_file']}"
                ),
                "",
            ]
        )

    DOCUMENT_PATH.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print()
    print("============================================================")
    print(" NOTEBOOK 02 SOURCE BUNDLE READY")
    print("============================================================")
    print()
    print("Tables inspected:", len(tables))
    print("Unique materialised files:", len(selected))
    print()
    print("Hourly June sources:")

    for source in june_hourly["source"]:
        print(f"  {source}")

    print()
    print("Daily maximum June sources:")

    for source in june_daily["source"]:
        print(f"  {source}")

    print()
    print("Role summary:")

    for role, summary in sorted(
        role_summary.items()
    ):
        print(
            f"  {role}: "
            f"{summary['unique_files']} files, "
            f"{summary['earliest_date']} to "
            f"{summary['latest_date']}, "
            f"latest complete date "
            f"{summary['latest_complete_date']}"
        )

    print()
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Audit: {AUDIT_PATH}")
    print(f"Schema inventory: {SCHEMA_PATH}")
    print(f"Documentation: {DOCUMENT_PATH}")


if __name__ == "__main__":
    main()
