#!/usr/bin/env python3
"""Inventory deterministic weather files needed by Notebook 02."""

from __future__ import annotations

import io
import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


ROOT = Path.cwd()
ARCHIVE_BRANCH = "archive/17j-plus-18n-18y-20260726"
MAX_BYTES = 150 * 1024 * 1024

OUTPUT_CSV = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "02_weather_source_inventory.csv"
)

OUTPUT_MD = (
    ROOT
    / "docs"
    / "NOTEBOOK_02_SOURCE_AUDIT.md"
)


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


def normalise(value: Any) -> str:
    text = str(value).strip().lower()
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    ).strip("_")


def read_csv(payload: bytes) -> pd.DataFrame | None:
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

            if frame.empty:
                continue

            frame.columns = [
                normalise(column)
                for column in frame.columns
            ]

            return frame

        except Exception:
            continue

    return None


def classify_role(source: str) -> str:
    lower = source.lower()

    if "hourly_forecast" in lower:
        return "hourly_forecasts"

    if "daily_max_forecast" in lower:
        return "daily_max_forecasts"

    if "request_plan" in lower:
        return "request_plan"

    if "fetch_inventory" in lower:
        return "fetch_inventory"

    if "integrity" in lower:
        return "integrity_checks"

    if "issue" in lower:
        return "issues"

    if "availability" in lower:
        return "availability"

    return "other_weather_source"


def inspect_table(
    source: str,
    frame: pd.DataFrame,
) -> Dict[str, Any]:
    date_columns = [
        column
        for column in frame.columns
        if "date" in column
        or column in {
            "target_day",
            "valid_day",
        }
    ]

    datetime_columns = [
        column
        for column in frame.columns
        if any(
            token in column
            for token in (
                "time",
                "datetime",
                "issued",
                "init",
                "valid",
                "retrieved",
            )
        )
    ]

    best_date_column = ""
    start_date = ""
    end_date = ""
    distinct_dates = 0

    for column in date_columns:
        parsed = pd.to_datetime(
            frame[column],
            errors="coerce",
        )

        count = int(
            parsed.dt.date.nunique()
        )

        if count > distinct_dates:
            distinct_dates = count
            best_date_column = column

            if parsed.notna().any():
                start_date = str(
                    parsed.min().date()
                )

                end_date = str(
                    parsed.max().date()
                )

    temperature_columns = [
        column
        for column in frame.columns
        if any(
            token in column
            for token in (
                "temperature",
                "temp",
                "tmax",
                "daily_max",
            )
        )
    ]

    decision_rule_columns = [
        column
        for column in frame.columns
        if "decision_rule" in column
        or column == "rule"
    ]

    return {
        "source": source,
        "role": classify_role(source),
        "rows": len(frame),
        "columns": len(frame.columns),
        "best_date_column": best_date_column,
        "distinct_dates": distinct_dates,
        "start_date": start_date,
        "end_date": end_date,
        "datetime_columns": "; ".join(
            datetime_columns
        ),
        "temperature_columns": "; ".join(
            temperature_columns
        ),
        "decision_rule_columns": "; ".join(
            decision_rule_columns
        ),
        "all_columns": "; ".join(
            frame.columns
        ),
    }


def main() -> None:
    rows: List[Dict[str, Any]] = []
    seen = set()

    local_roots = [
        ROOT / "data",
        ROOT / "review_bundles",
    ]

    keywords = (
        "19a",
        "ecmwf",
        "single_run",
        "forecast",
        "hourly",
        "daily_max",
        "request_plan",
        "fetch_inventory",
    )

    for local_root in local_roots:
        if not local_root.exists():
            continue

        for path in local_root.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            if path.suffix.lower() != ".csv":
                continue

            lower = str(path).lower()

            if not any(
                keyword in lower
                for keyword in keywords
            ):
                continue

            if path.stat().st_size > MAX_BYTES:
                continue

            source = f"local:{path.resolve()}"

            if source in seen:
                continue

            seen.add(source)

            frame = read_csv(
                path.read_bytes()
            )

            if frame is not None:
                rows.append(
                    inspect_table(
                        source,
                        frame,
                    )
                )

    archive_paths = git_text(
        "ls-tree",
        "-r",
        "--name-only",
        ARCHIVE_BRANCH,
    ).splitlines()

    for path in archive_paths:
        lower = path.lower()

        if not lower.endswith(".csv"):
            continue

        if not any(
            keyword in lower
            for keyword in keywords
        ):
            continue

        source = (
            f"git:{ARCHIVE_BRANCH}:{path}"
        )

        if source in seen:
            continue

        seen.add(source)

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

        frame = read_csv(payload)

        if frame is not None:
            rows.append(
                inspect_table(
                    source,
                    frame,
                )
            )

    if not rows:
        raise RuntimeError(
            "No deterministic weather-source tables were found."
        )

    inventory = pd.DataFrame(rows).sort_values(
        [
            "role",
            "distinct_dates",
            "rows",
        ],
        ascending=[
            True,
            False,
            False,
        ],
    )

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_MD.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    inventory.to_csv(
        OUTPUT_CSV,
        index=False,
    )

    preferred_roles = (
        "hourly_forecasts",
        "daily_max_forecasts",
        "request_plan",
        "fetch_inventory",
        "integrity_checks",
        "issues",
    )

    lines = [
        "# Notebook 02 Weather Source Audit",
        "",
        (
            "This audit identifies the deterministic weather files "
            "available for construction of the expanded training panel."
        ),
        "",
        f"Tables inspected: **{len(inventory)}**",
        "",
        "## Required source roles",
        "",
    ]

    for role in preferred_roles:
        subset = inventory.loc[
            inventory["role"] == role
        ]

        lines.append(
            f"### {role.replace('_', ' ').title()}"
        )

        lines.append("")

        if subset.empty:
            lines.append(
                "No candidate was found."
            )
            lines.append("")
            continue

        for row in subset.head(10).itertuples(
            index=False
        ):
            lines.append(
                f"- `{row.source}`: "
                f"{row.rows} rows, "
                f"{row.distinct_dates} dates, "
                f"{row.start_date} to {row.end_date}."
            )

        lines.append("")

    lines.extend(
        [
            "## Notebook 02 admission rules",
            "",
            "A forecast row is admitted only when:",
            "",
            "1. the model product and cycle are declared;",
            "2. the forecast issue time precedes the decision time;",
            "3. the full Hong Kong local day contains 24 unique hours;",
            "4. no later forecast is substituted for a missing run;",
            "5. the HKO outcome is used only as the supervised target;",
            "6. the settlement date remains the uncertainty unit;",
            "7. training and market evaluation samples are recorded separately.",
            "",
            "The inventory does not itself admit any forecast row.",
            "",
        ]
    )

    OUTPUT_MD.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("NOTEBOOK 02 SOURCE AUDIT COMPLETE")
    print("Tables inspected:", len(inventory))
    print("Inventory:", OUTPUT_CSV)
    print("Documentation:", OUTPUT_MD)

    for role in preferred_roles:
        count = int(
            (
                inventory["role"]
                == role
            ).sum()
        )

        print(f"{role}: {count}")


if __name__ == "__main__":
    main()
