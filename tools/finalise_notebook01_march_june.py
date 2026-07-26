#!/usr/bin/env python3
"""Append audited June contracts and recovered HKO outcomes."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd


ROOT = Path.cwd()

ARCHIVE_BRANCH = "archive/17j-plus-18n-18y-20260726"

MIGRATION_MODULE_PATH = (
    ROOT
    / "tools"
    / "migrate_notebook01_real_sources.py"
)

BASE_CONTRACT_PATH = (
    ROOT
    / "data"
    / "interim"
    / "canonical_contract_definitions.csv"
)

BASE_HKO_PATH = (
    ROOT
    / "data"
    / "interim"
    / "hko_daily_max.csv"
)

RECOVERED_JUNE_HKO_PATH = (
    ROOT
    / "data"
    / "interim"
    / "june_hko_daily_max_recovered.csv"
)

SOURCE_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "01_source_migration_manifest.json"
)

RECOVERY_REPORT_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "01_june_hko_recovery_report.json"
)

CONTRACT_AUDIT_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "01_june_contract_candidate_audit.csv"
)

MERGE_REPORT_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "01_march_june_source_merge_report.json"
)

EXPECTED_JUNE_DATES = set(
    pd.date_range(
        "2026-06-01",
        "2026-06-30",
        freq="D",
    ).strftime("%Y-%m-%d")
)

EXPECTED_BASE_DATES = 73
EXPECTED_BASE_ROWS = 803
EXPECTED_FINAL_DATES = 103
EXPECTED_FINAL_ROWS = 1133

MAX_BYTES = 150 * 1024 * 1024


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "notebook01_source_migration",
        MIGRATION_MODULE_PATH,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Could not create the source-migration module specification."
        )

    module = importlib.util.module_from_spec(spec)

    # Required by Python 3.12 dataclasses during dynamic import.
    sys.modules[spec.name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise

    return module


def canonical_dates(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()

    result["event_date"] = pd.to_datetime(
        result["event_date"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    return result


def source_priority(source: str) -> float:
    lower = source.lower()
    score = 0.0

    priorities = (
        ("18n_june_2026_contract_event_audit", 100000.0),
        ("18n", 90000.0),
        ("june_2026_contract", 80000.0),
        ("contract_event_audit", 70000.0),
        ("contract_event", 50000.0),
        ("certified", 20000.0),
        ("local:", 10000.0),
        ("review_bundle", 5000.0),
        ("git:", 1000.0),
    )

    for token, value in priorities:
        if token in lower:
            score += value

    return score


def local_candidate_paths() -> List[Path]:
    roots = [
        ROOT / "data",
        ROOT / "review_bundles",
        ROOT / "notebooks" / "data",
    ]

    keywords = (
        "18n",
        "june",
        "contract",
        "event",
        "audit",
        "review_bundle",
    )

    paths: List[Path] = []

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts:
                continue

            if path.suffix.lower() not in {
                ".csv",
                ".json",
                ".zip",
            }:
                continue

            lower = str(path).lower()

            if not all(
                token in lower
                for token in ("june",)
            ) and "18n" not in lower:
                continue

            if not any(
                token in lower
                for token in keywords
            ):
                continue

            paths.append(path)

    return sorted(set(paths))


def local_tables(
    module,
) -> List[Any]:
    tables: List[Any] = []

    for path in local_candidate_paths():
        if path.stat().st_size > MAX_BYTES:
            continue

        payload = path.read_bytes()
        source = f"local:{path.resolve()}"
        lower = path.name.lower()

        if lower.endswith(".csv"):
            frame = module.read_csv_payload(payload)

            if frame is not None:
                tables.append(
                    module.Table(
                        source=source,
                        frame=frame,
                        source_sha256=sha256_bytes(payload),
                    )
                )

        elif lower.endswith(".json"):
            tables.extend(
                module.tables_from_json(
                    source,
                    payload,
                )
            )

        elif lower.endswith(".zip"):
            try:
                archive = zipfile.ZipFile(
                    io.BytesIO(payload)
                )
            except zipfile.BadZipFile:
                continue

            with archive:
                for member in archive.infolist():
                    if (
                        member.is_dir()
                        or member.file_size > MAX_BYTES
                    ):
                        continue

                    member_lower = member.filename.lower()

                    if not member_lower.endswith(
                        (".csv", ".json")
                    ):
                        continue

                    try:
                        member_payload = archive.read(member)
                    except Exception:
                        continue

                    member_source = (
                        f"{source}::{member.filename}"
                    )

                    if member_lower.endswith(".csv"):
                        frame = module.read_csv_payload(
                            member_payload
                        )

                        if frame is not None:
                            tables.append(
                                module.Table(
                                    source=member_source,
                                    frame=frame,
                                    source_sha256=sha256_bytes(
                                        member_payload
                                    ),
                                )
                            )
                    else:
                        tables.extend(
                            module.tables_from_json(
                                member_source,
                                member_payload,
                            )
                        )

    return tables


def june_contract_subset(
    candidate,
) -> pd.DataFrame | None:
    frame = canonical_dates(
        candidate.frame
    )

    june = frame.loc[
        frame["event_date"].isin(
            EXPECTED_JUNE_DATES
        )
    ].copy()

    if set(june["event_date"]) != EXPECTED_JUNE_DATES:
        return None

    if len(june) != 330:
        return None

    sizes = june.groupby(
        "event_date"
    ).size()

    if not sizes.eq(11).all():
        return None

    if june.duplicated(
        ["event_date", "event_id"],
        keep=False,
    ).any():
        return None

    return june.sort_values(
        ["event_date", "event_index"]
    ).reset_index(drop=True)


def validate_june_contracts_and_hko(
    module,
    contracts: pd.DataFrame,
    hko: pd.DataFrame,
) -> pd.DataFrame:
    if set(hko["event_date"]) != EXPECTED_JUNE_DATES:
        raise ValueError(
            "Recovered HKO table does not contain all 30 June dates."
        )

    if len(hko) != 30:
        raise ValueError(
            "Recovered HKO table does not contain exactly 30 rows."
        )

    if hko["event_date"].duplicated().any():
        raise ValueError(
            "Recovered HKO table contains duplicate dates."
        )

    temperature_map = dict(
        zip(
            hko["event_date"],
            hko["hko_daily_max_c"],
        )
    )

    date_rows = []

    for event_date in sorted(
        EXPECTED_JUNE_DATES
    ):
        group = contracts.loc[
            contracts["event_date"] == event_date
        ].copy()

        if len(group) != 11:
            raise ValueError(
                f"{event_date} contains {len(group)} events."
            )

        temperature = float(
            temperature_map[event_date]
        )

        winner_index = module.classify(
            group,
            temperature,
        )

        date_rows.append(
            {
                "event_date": event_date,
                "hko_daily_max_c": temperature,
                "event_count": len(group),
                "winning_event_id": str(
                    group.loc[
                        winner_index,
                        "event_id",
                    ]
                ),
                "winner_count": 1,
            }
        )

    result = pd.DataFrame(date_rows)

    if not result["event_count"].eq(11).all():
        raise ValueError(
            "June contract event-count validation failed."
        )

    if not result["winner_count"].eq(1).all():
        raise ValueError(
            "June winner validation failed."
        )

    return result


def main() -> None:
    module = load_migration_module()

    base_contracts = canonical_dates(
        pd.read_csv(BASE_CONTRACT_PATH)
    )

    base_hko = canonical_dates(
        pd.read_csv(BASE_HKO_PATH)
    )

    recovered_hko = canonical_dates(
        pd.read_csv(
            RECOVERED_JUNE_HKO_PATH
        )
    )

    if (
        base_contracts["event_date"].nunique()
        == EXPECTED_FINAL_DATES
        and len(base_contracts)
        == EXPECTED_FINAL_ROWS
        and base_hko["event_date"].nunique()
        == EXPECTED_FINAL_DATES
    ):
        print(
            "The canonical March-June source panel "
            "is already complete."
        )
        return

    if (
        base_contracts["event_date"].nunique()
        != EXPECTED_BASE_DATES
        or len(base_contracts) != EXPECTED_BASE_ROWS
    ):
        raise RuntimeError(
            "The current contract panel is not "
            "the expected 73-date March-May base."
        )

    if (
        base_hko["event_date"].nunique()
        != EXPECTED_BASE_DATES
        or len(base_hko) != EXPECTED_BASE_DATES
    ):
        raise RuntimeError(
            "The current HKO table is not "
            "the expected 73-date March-May base."
        )

    if set(recovered_hko["event_date"]) != EXPECTED_JUNE_DATES:
        raise RuntimeError(
            "The recovered HKO table does not contain "
            "the exact June date set."
        )

    all_tables = []

    print("Loading local June contract candidates...")

    all_tables.extend(
        local_tables(module)
    )

    print("Loading preserved Git archive candidates...")

    all_tables.extend(
        module.load_archive_tables()
    )

    unique_tables = {}
    for table in all_tables:
        key = (
            table.source,
            table.source_sha256,
        )
        unique_tables[key] = table

    contract_candidates = []
    audit_rows: List[Dict[str, Any]] = []

    for table in unique_tables.values():
        try:
            candidate = (
                module.build_contract_candidate(
                    table
                )
            )
        except Exception as exc:
            audit_rows.append(
                {
                    "source": table.source,
                    "status": "PARSER_ERROR",
                    "june_dates": 0,
                    "june_rows": 0,
                    "score": 0.0,
                    "reason": str(exc),
                }
            )
            continue

        if candidate is None:
            continue

        june = june_contract_subset(
            candidate
        )

        if june is None:
            audit_rows.append(
                {
                    "source": candidate.source,
                    "status": "INCOMPLETE_JUNE_PANEL",
                    "june_dates": int(
                        canonical_dates(
                            candidate.frame
                        )
                        .loc[
                            lambda frame: frame[
                                "event_date"
                            ].isin(EXPECTED_JUNE_DATES)
                        ]["event_date"]
                        .nunique()
                    ),
                    "june_rows": int(
                        canonical_dates(
                            candidate.frame
                        )
                        .loc[
                            lambda frame: frame[
                                "event_date"
                            ].isin(EXPECTED_JUNE_DATES)
                        ]
                        .shape[0]
                    ),
                    "score": float(candidate.score),
                    "reason": (
                        "Does not contain 30 complete "
                        "eleven-event June books."
                    ),
                }
            )
            continue

        score = (
            float(candidate.score)
            + source_priority(
                candidate.source
            )
        )

        try:
            june_by_date = (
                validate_june_contracts_and_hko(
                    module,
                    june,
                    recovered_hko,
                )
            )
        except Exception as exc:
            audit_rows.append(
                {
                    "source": candidate.source,
                    "status": "WINNER_VALIDATION_FAILED",
                    "june_dates": 30,
                    "june_rows": 330,
                    "score": score,
                    "reason": str(exc),
                }
            )
            continue

        audit_rows.append(
            {
                "source": candidate.source,
                "status": "PASSED",
                "june_dates": 30,
                "june_rows": 330,
                "score": score,
                "reason": "",
            }
        )

        contract_candidates.append(
            (
                score,
                candidate,
                june,
                june_by_date,
            )
        )

    CONTRACT_AUDIT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame(audit_rows).sort_values(
        ["status", "score"],
        ascending=[True, False],
    ).to_csv(
        CONTRACT_AUDIT_PATH,
        index=False,
    )

    if not contract_candidates:
        raise RuntimeError(
            "No complete June contract source passed "
            "the recovered HKO one-winner validation. "
            "See the contract candidate audit."
        )

    contract_candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    (
        _,
        selected_candidate,
        june_contracts,
        june_by_date,
    ) = contract_candidates[0]

    if not set(
        base_contracts.columns
    ).issubset(
        june_contracts.columns
    ):
        missing = sorted(
            set(base_contracts.columns)
            - set(june_contracts.columns)
        )

        raise RuntimeError(
            "June contract source is missing canonical columns: "
            + ", ".join(missing)
        )

    june_contracts = june_contracts[
        base_contracts.columns
    ].copy()

    if not set(
        base_hko.columns
    ).issubset(
        recovered_hko.columns
    ):
        missing = sorted(
            set(base_hko.columns)
            - set(recovered_hko.columns)
        )

        raise RuntimeError(
            "Recovered June HKO source is missing columns: "
            + ", ".join(missing)
        )

    recovered_hko = recovered_hko[
        base_hko.columns
    ].copy()

    if set(base_contracts["event_date"]) & EXPECTED_JUNE_DATES:
        raise RuntimeError(
            "The March-May contract base already contains June dates."
        )

    if set(base_hko["event_date"]) & EXPECTED_JUNE_DATES:
        raise RuntimeError(
            "The March-May HKO base already contains June dates."
        )

    merged_contracts = pd.concat(
        [
            base_contracts,
            june_contracts,
        ],
        ignore_index=True,
    ).sort_values(
        ["event_date", "event_index"]
    ).reset_index(drop=True)

    merged_hko = pd.concat(
        [
            base_hko,
            recovered_hko,
        ],
        ignore_index=True,
    ).sort_values(
        "event_date"
    ).reset_index(drop=True)

    if (
        merged_contracts[
            "event_date"
        ].nunique()
        != EXPECTED_FINAL_DATES
    ):
        raise RuntimeError(
            "Merged contract panel does not contain 103 dates."
        )

    if len(merged_contracts) != EXPECTED_FINAL_ROWS:
        raise RuntimeError(
            "Merged contract panel does not contain 1,133 rows."
        )

    if not (
        merged_contracts.groupby(
            "event_date"
        ).size()
        == 11
    ).all():
        raise RuntimeError(
            "At least one merged date does not contain eleven events."
        )

    if merged_contracts.duplicated(
        ["event_date", "event_id"],
        keep=False,
    ).any():
        raise RuntimeError(
            "Merged contract panel contains duplicate date-event keys."
        )

    if (
        merged_hko[
            "event_date"
        ].nunique()
        != EXPECTED_FINAL_DATES
        or len(merged_hko)
        != EXPECTED_FINAL_DATES
    ):
        raise RuntimeError(
            "Merged HKO table does not contain one row "
            "for each of the 103 dates."
        )

    if merged_hko["event_date"].duplicated().any():
        raise RuntimeError(
            "Merged HKO table contains duplicate dates."
        )

    BASE_CONTRACT_PATH.write_text(
        merged_contracts.to_csv(
            index=False
        ),
        encoding="utf-8",
    )

    BASE_HKO_PATH.write_text(
        merged_hko.to_csv(
            index=False,
            float_format="%.1f",
        ),
        encoding="utf-8",
    )

    source_manifest = json.loads(
        SOURCE_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    recovery_report = json.loads(
        RECOVERY_REPORT_PATH.read_text(
            encoding="utf-8"
        )
    )

    prior_contract_source = (
        source_manifest[
            "selected_contract_source"
        ]["source"]
    )

    prior_hko_source = (
        source_manifest[
            "selected_hko_source"
        ]["source"]
    )

    source_manifest["created_utc"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    source_manifest["source_components"] = {
        "contract_sources": [
            {
                "period": "2026-03-16_to_2026-05-31",
                "source": prior_contract_source,
            },
            {
                "period": "2026-06-01_to_2026-06-30",
                "source": selected_candidate.source,
                "source_sha256": (
                    selected_candidate.source_sha256
                ),
            },
        ],
        "hko_sources": [
            {
                "period": "2026-03-16_to_2026-05-31",
                "source": prior_hko_source,
            },
            {
                "period": "2026-06-01_to_2026-06-30",
                "source": recovery_report[
                    "selected_source"
                ],
                "source_sha256": recovery_report[
                    "selected_source_sha256"
                ],
            },
        ],
    }

    source_manifest[
        "selected_contract_source"
    ]["source"] = (
        f"{prior_contract_source}; "
        f"{selected_candidate.source}"
    )

    source_manifest[
        "selected_hko_source"
    ]["source"] = (
        f"{prior_hko_source}; "
        f"{recovery_report['selected_source']}"
    )

    source_manifest["selected_pair"] = {
        "common_dates": EXPECTED_FINAL_DATES,
        "start_date": "2026-03-16",
        "end_date": "2026-06-30",
        "contract_rows": EXPECTED_FINAL_ROWS,
        "hko_rows": EXPECTED_FINAL_DATES,
        "all_dates_have_11_events": True,
        "all_dates_have_one_winner": True,
    }

    source_manifest["june_extension"] = {
        "status": "JUNE_EXTENSION_CERTIFIED",
        "contract_source": (
            selected_candidate.source
        ),
        "hko_source": recovery_report[
            "selected_source"
        ],
        "june_dates": 30,
        "june_contract_rows": 330,
        "june_hko_rows": 30,
        "june_start": "2026-06-01",
        "june_end": "2026-06-30",
    }

    source_manifest["canonical_outputs"] = {
        str(
            BASE_CONTRACT_PATH.relative_to(
                ROOT
            )
        ): {
            "sha256": sha256_file(
                BASE_CONTRACT_PATH
            ),
            "rows": EXPECTED_FINAL_ROWS,
        },
        str(
            BASE_HKO_PATH.relative_to(
                ROOT
            )
        ): {
            "sha256": sha256_file(
                BASE_HKO_PATH
            ),
            "rows": EXPECTED_FINAL_DATES,
        },
    }

    SOURCE_MANIFEST_PATH.write_text(
        json.dumps(
            source_manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    merge_report = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "MARCH_JUNE_SOURCE_PANEL_READY",
        "base_dates": EXPECTED_BASE_DATES,
        "june_dates_added": 30,
        "final_dates": EXPECTED_FINAL_DATES,
        "final_contract_rows": EXPECTED_FINAL_ROWS,
        "final_hko_rows": EXPECTED_FINAL_DATES,
        "start_date": "2026-03-16",
        "end_date": "2026-06-30",
        "all_dates_have_11_events": True,
        "all_dates_have_one_winner": True,
        "june_contract_source": (
            selected_candidate.source
        ),
        "june_hko_source": recovery_report[
            "selected_source"
        ],
        "june_date_certification": (
            june_by_date.to_dict(
                orient="records"
            )
        ),
        "canonical_contract_sha256": (
            sha256_file(
                BASE_CONTRACT_PATH
            )
        ),
        "canonical_hko_sha256": (
            sha256_file(
                BASE_HKO_PATH
            )
        ),
    }

    MERGE_REPORT_PATH.write_text(
        json.dumps(
            merge_report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("============================================================")
    print(" MARCH-JUNE SOURCE PANEL COMPLETED")
    print("============================================================")
    print()
    print("June contract source:")
    print(f"  {selected_candidate.source}")
    print("June HKO source:")
    print(
        f"  {recovery_report['selected_source']}"
    )
    print("Final settlement dates:")
    print("  103")
    print("Final contract rows:")
    print("  1133")
    print("Final HKO rows:")
    print("  103")
    print("Date range:")
    print("  2026-03-16 to 2026-06-30")
    print("June contract audit:")
    print(f"  {CONTRACT_AUDIT_PATH}")
    print("Merge report:")
    print(f"  {MERGE_REPORT_PATH}")


if __name__ == "__main__":
    main()
