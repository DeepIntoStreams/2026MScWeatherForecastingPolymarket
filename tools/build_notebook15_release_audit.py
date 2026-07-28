from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "edward-final-empirical-2026"

ROOT_MANIFEST = (
    ROOT
    / "data/manifests/"
    "14_final_empirical_synthesis_manifest.json"
)

TEST_SUMMARY = (
    ROOT
    / "outputs/diagnostics/"
    "15_full_test_suite_summary.csv"
)

OUTPUTS = {
    "lineage": (
        ROOT
        / "outputs/diagnostics/"
        "15_lineage_manifest_audit.csv"
    ),
    "hashes": (
        ROOT
        / "outputs/diagnostics/"
        "15_lineage_hash_verification.csv"
    ),
    "notebooks": (
        ROOT
        / "outputs/diagnostics/"
        "15_notebook_execution_audit.csv"
    ),
    "environment": (
        ROOT
        / "outputs/diagnostics/"
        "15_environment_inventory.csv"
    ),
    "integrity": (
        ROOT
        / "outputs/diagnostics/"
        "15_release_integrity_checks.csv"
    ),
    "tracked": (
        ROOT
        / "outputs/final_tables/"
        "15_tracked_file_inventory.csv"
    ),
    "summary": (
        ROOT
        / "outputs/final_tables/"
        "15_reproducibility_release_summary.csv"
    ),
}

MANIFEST_OUTPUT = (
    ROOT
    / "data/manifests/"
    "15_reproducibility_release_manifest.json"
)

EXPECTED_STAGE15_CHANGES = {
    "Makefile",
    "config/reproducibility_release_spec.yaml",
    "data/manifests/15_reproducibility_release_manifest.json",
    "docs/MIGRATION_STATUS.md",
    "docs/NOTEBOOK_15_REPRODUCIBILITY_RELEASE_AUDIT.md",
    "notebooks/final/15_reproducibility_release_audit.ipynb",
    "outputs/diagnostics/15_environment_inventory.csv",
    "outputs/diagnostics/15_full_test_suite_summary.csv",
    "outputs/diagnostics/15_lineage_hash_verification.csv",
    "outputs/diagnostics/15_lineage_manifest_audit.csv",
    "outputs/diagnostics/15_notebook_execution_audit.csv",
    "outputs/diagnostics/15_release_integrity_checks.csv",
    "outputs/final_tables/15_reproducibility_release_summary.csv",
    "outputs/final_tables/15_tracked_file_inventory.csv",
    "tests/test_notebook15_release_audit.py",
    "tools/build_notebook15_release_audit.py",
}


def run_git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_csv(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_csv(
        path,
        index=False,
        float_format="%.12g",
    )


def status_paths() -> list[str]:
    completed = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "-z",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )

    records = completed.stdout.split(b"\x00")
    result: list[str] = []
    index = 0

    while index < len(records):
        record = records[index]

        if not record:
            index += 1
            continue

        decoded = record.decode(
            "utf-8",
            errors="surrogateescape",
        )

        if len(decoded) < 4:
            raise RuntimeError(
                "Malformed git-status record: "
                + repr(decoded)
            )

        status = decoded[:2]
        path = decoded[3:]

        if (
            "R" in status
            or "C" in status
        ):
            index += 1

            if index >= len(records):
                raise RuntimeError(
                    "Rename or copy status lacks "
                    "its second path."
                )

            path = records[index].decode(
                "utf-8",
                errors="surrogateescape",
            )

        result.append(path)
        index += 1

    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def verifiable_repository_path(
    value: str,
) -> bool:
    return not (
        Path(value).is_absolute()
        or "://" in value
        or value.startswith("local:")
    )


def audit_lineage() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    queue: deque[Path] = deque(
        [ROOT_MANIFEST]
    )

    visited: set[Path] = set()
    manifest_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []

    while queue:
        manifest_path = queue.popleft().resolve()

        if manifest_path in visited:
            continue

        visited.add(manifest_path)

        if not manifest_path.exists():
            raise FileNotFoundError(
                manifest_path
            )

        manifest = load_json(
            manifest_path
        )

        status = str(
            manifest.get(
                "status",
                "",
            )
        )

        manifest_rows.append(
            {
                "manifest_path": relative(
                    manifest_path
                ),
                "status": status,
                "bad_status_token": any(
                    token in status.upper()
                    for token in [
                        "FAILED",
                        "ERROR",
                        "BLOCKED",
                    ]
                ),
                "selected_model": manifest.get(
                    "selected_model"
                ),
                "selected_family": manifest.get(
                    "selected_family"
                ),
            }
        )

        for hash_group in [
            "input_hashes",
            "output_hashes",
        ]:
            mapping = manifest.get(
                hash_group,
                {}
            )

            if not isinstance(
                mapping,
                dict,
            ):
                continue

            for declared_path, expected_hash in mapping.items():
                declared_path = str(
                    declared_path
                )

                verifiable = verifiable_repository_path(
                    declared_path
                )

                exists = False
                actual_hash = None
                hash_matches = None

                if verifiable:
                    path = (
                        ROOT
                        / declared_path
                    )

                    exists = path.exists()

                    if exists and path.is_file():
                        actual_hash = sha256(
                            path
                        )

                        hash_matches = (
                            actual_hash
                            == str(
                                expected_hash
                            )
                        )

                    if (
                        exists
                        and declared_path.startswith(
                            "data/manifests/"
                        )
                        and declared_path.endswith(
                            ".json"
                        )
                    ):
                        queue.append(
                            path
                        )

                hash_rows.append(
                    {
                        "declaring_manifest": relative(
                            manifest_path
                        ),
                        "hash_group": hash_group,
                        "declared_path": declared_path,
                        "verifiable_repository_path": verifiable,
                        "exists": exists,
                        "expected_sha256": expected_hash,
                        "actual_sha256": actual_hash,
                        "hash_matches": hash_matches,
                    }
                )

    return (
        pd.DataFrame(
            manifest_rows
        ).sort_values(
            "manifest_path"
        ),
        pd.DataFrame(
            hash_rows
        ).sort_values(
            [
                "declaring_manifest",
                "hash_group",
                "declared_path",
            ]
        ),
    )


def audit_notebooks() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for path in sorted(
        (
            ROOT
            / "notebooks/final"
        ).glob("*.ipynb")
    ):
        match = re.match(
            r"^(\d{2})_",
            path.name,
        )

        if not match:
            continue

        number = int(
            match.group(1)
        )

        if number > 14:
            continue

        notebook = nbformat.read(
            path,
            as_version=4,
        )

        code_cells = [
            cell
            for cell in notebook.cells
            if cell.cell_type == "code"
        ]

        error_outputs = [
            output
            for cell in code_cells
            for output in cell.get(
                "outputs",
                [],
            )
            if output.get(
                "output_type"
            ) == "error"
        ]

        executed_cells = sum(
            cell.execution_count
            is not None
            for cell in code_cells
        )

        rows.append(
            {
                "notebook_number": number,
                "path": relative(
                    path
                ),
                "code_cells": len(
                    code_cells
                ),
                "executed_code_cells": executed_cells,
                "unexecuted_code_cells": (
                    len(code_cells)
                    - executed_cells
                ),
                "error_outputs": len(
                    error_outputs
                ),
                "execution_complete": (
                    len(code_cells) > 0
                    and executed_cells
                    == len(code_cells)
                    and len(error_outputs) == 0
                ),
            }
        )

    return pd.DataFrame(
        rows
    ).sort_values(
        [
            "notebook_number",
            "path",
        ]
    )


def tracked_file_inventory() -> pd.DataFrame:
    output = subprocess.run(
        [
            "git",
            "ls-tree",
            "-r",
            "-l",
            "HEAD",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout

    rows: list[dict[str, Any]] = []

    pattern = re.compile(
        r"^(\d+)\s+(\w+)\s+([0-9a-f]+)\s+(\S+)\t(.+)$"
    )

    for line in output.splitlines():
        match = pattern.match(
            line
        )

        if not match:
            continue

        mode, object_type, blob_sha, size, path = (
            match.groups()
        )

        rows.append(
            {
                "path": path,
                "git_mode": mode,
                "object_type": object_type,
                "git_blob_sha": blob_sha,
                "bytes": (
                    None
                    if size == "-"
                    else int(size)
                ),
            }
        )

    return pd.DataFrame(
        rows
    ).sort_values(
        "path"
    )


def environment_inventory() -> pd.DataFrame:
    packages = [
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "catboost",
        "jupyter",
        "nbformat",
        "PyYAML",
    ]

    rows = [
        {
            "component": "python",
            "version": platform.python_version(),
        },
        {
            "component": "platform",
            "version": platform.platform(),
        },
    ]

    for package in packages:
        try:
            version = importlib.metadata.version(
                package
            )
        except importlib.metadata.PackageNotFoundError:
            version = "NOT_INSTALLED"

        rows.append(
            {
                "component": package,
                "version": version,
            }
        )

    return pd.DataFrame(
        rows
    )


def main() -> None:
    if not ROOT_MANIFEST.exists():
        raise FileNotFoundError(
            ROOT_MANIFEST
        )

    if not TEST_SUMMARY.exists():
        raise FileNotFoundError(
            TEST_SUMMARY
        )

    branch = run_git(
        "branch",
        "--show-current",
    )

    local_head = run_git(
        "rev-parse",
        "HEAD",
    )

    remote_head = run_git(
        "rev-parse",
        f"origin/{BRANCH}",
    )

    dirty_paths = status_paths()

    unexpected_dirty = sorted(
        set(dirty_paths)
        - EXPECTED_STAGE15_CHANGES
    )

    lineage, hashes = audit_lineage()
    notebooks = audit_notebooks()
    tracked = tracked_file_inventory()
    environment = environment_inventory()
    tests = pd.read_csv(
        TEST_SUMMARY
    )

    root_manifest = load_json(
        ROOT_MANIFEST
    )

    required_numbers = set(
        range(
            0,
            15,
        )
    )

    observed_numbers = set(
        notebooks[
            "notebook_number"
        ].astype(int)
    )

    duplicate_numbers = (
        notebooks[
            "notebook_number"
        ].duplicated(
            keep=False
        )
    )

    verifiable_hashes = hashes.loc[
        hashes[
            "verifiable_repository_path"
        ].astype(bool)
    ]

    selection_flags = {
        "model_reselected": root_manifest.get(
            "model_reselected",
            False,
        ),
        "continuous_calibration_reselected": root_manifest.get(
            "continuous_calibration_reselected",
            False,
        ),
        "probability_calibration_reselected": root_manifest.get(
            "probability_calibration_reselected",
            False,
        ),
        "trading_strategy_reselected": root_manifest.get(
            "trading_strategy_reselected",
            False,
        ),
        "holdout_used_for_selection": root_manifest.get(
            "holdout_used_for_selection",
            False,
        ),
        "external_test_used_for_selection": root_manifest.get(
            "external_test_used_for_selection",
            False,
        ),
    }

    checks = pd.DataFrame(
        [
            {
                "check": "correct_branch",
                "passed": branch == BRANCH,
                "detail": branch,
            },
            {
                "check": "local_remote_commits_aligned",
                "passed": local_head == remote_head,
                "detail": local_head,
            },
            {
                "check": "no_unexpected_working_tree_changes",
                "passed": not unexpected_dirty,
                "detail": ";".join(
                    unexpected_dirty
                ),
            },
            {
                "check": "root_manifest_complete",
                "passed": (
                    root_manifest.get(
                        "status"
                    )
                    == "FINAL_EMPIRICAL_SYNTHESIS_COMPLETE"
                ),
                "detail": str(
                    root_manifest.get(
                        "status"
                    )
                ),
            },
            {
                "check": "lineage_contains_no_failure_status",
                "passed": not lineage[
                    "bad_status_token"
                ].astype(bool).any(),
                "detail": str(
                    len(lineage)
                ),
            },
            {
                "check": "all_verifiable_lineage_files_exist",
                "passed": verifiable_hashes[
                    "exists"
                ].astype(bool).all(),
                "detail": str(
                    len(
                        verifiable_hashes
                    )
                ),
            },
            {
                "check": "all_lineage_hashes_match",
                "passed": verifiable_hashes[
                    "hash_matches"
                ].fillna(False).astype(bool).all(),
                "detail": str(
                    len(
                        verifiable_hashes
                    )
                ),
            },
            {
                "check": "canonical_notebooks_00_to_14_present",
                "passed": (
                    observed_numbers
                    == required_numbers
                    and not duplicate_numbers.any()
                ),
                "detail": ",".join(
                    f"{number:02d}"
                    for number in sorted(
                        observed_numbers
                    )
                ),
            },
            {
                "check": "canonical_notebooks_executed_without_errors",
                "passed": (
                    len(notebooks) == 15
                    and notebooks[
                        "execution_complete"
                    ].astype(bool).all()
                ),
                "detail": str(
                    len(notebooks)
                ),
            },
            {
                "check": "full_repository_test_suite_passed",
                "passed": tests[
                    "passed"
                ].astype(str).str.lower().isin(
                    {"true", "1"}
                ).all(),
                "detail": str(
                    tests[
                        "test_count"
                    ].iloc[0]
                ),
            },
            {
                "check": "locked_selection_lineage_unchanged",
                "passed": not any(
                    bool(value)
                    for value in selection_flags.values()
                ),
                "detail": json.dumps(
                    selection_flags,
                    sort_keys=True,
                ),
            },
            {
                "check": "tracked_parent_commit_inventory_nonempty",
                "passed": not tracked.empty,
                "detail": str(
                    len(tracked)
                ),
            },
        ]
    )

    if not checks[
        "passed"
    ].astype(bool).all():
        failed = checks.loc[
            ~checks[
                "passed"
            ].astype(bool)
        ]

        raise RuntimeError(
            "Notebook 15 release checks failed:\n"
            + failed.to_string(
                index=False
            )
        )

    summary = checks.copy()
    summary.insert(
        0,
        "audited_commit",
        local_head,
    )

    for frame, path in [
        (lineage, OUTPUTS["lineage"]),
        (hashes, OUTPUTS["hashes"]),
        (notebooks, OUTPUTS["notebooks"]),
        (environment, OUTPUTS["environment"]),
        (checks, OUTPUTS["integrity"]),
        (tracked, OUTPUTS["tracked"]),
        (summary, OUTPUTS["summary"]),
    ]:
        write_csv(
            frame,
            path,
        )

    previous_created = None

    if MANIFEST_OUTPUT.exists():
        try:
            previous_created = load_json(
                MANIFEST_OUTPUT
            ).get(
                "created_utc"
            )
        except Exception:
            previous_created = None

    output_hashes = {
        relative(path): sha256(
            path
        )
        for path in [
            *OUTPUTS.values(),
            TEST_SUMMARY,
        ]
    }

    manifest = {
        "status": "FINAL_EMPIRICAL_RELEASE_CERTIFIED",
        "created_utc": (
            previous_created
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "branch": branch,
        "audited_commit": local_head,
        "remote_commit": remote_head,
        "local_remote_commits_aligned": (
            local_head == remote_head
        ),
        "root_manifest": relative(
            ROOT_MANIFEST
        ),
        "root_manifest_sha256": sha256(
            ROOT_MANIFEST
        ),
        "lineage_manifest_count": len(
            lineage
        ),
        "lineage_hash_check_count": len(
            verifiable_hashes
        ),
        "canonical_notebook_count": len(
            notebooks
        ),
        "canonical_notebook_range": "00-14",
        "tracked_parent_commit_file_count": len(
            tracked
        ),
        "full_test_suite_passed": True,
        "full_test_count": (
            None
            if pd.isna(
                tests[
                    "test_count"
                ].iloc[0]
            )
            else int(
                tests[
                    "test_count"
                ].iloc[0]
            )
        ),
        "selected_model": root_manifest.get(
            "selected_model"
        ),
        "selected_family": root_manifest.get(
            "selected_family"
        ),
        "selected_continuous_scale": root_manifest.get(
            "selected_continuous_scale"
        ),
        "selected_probability_mixing_lambda": root_manifest.get(
            "selected_probability_mixing_lambda"
        ),
        "model_reselected": False,
        "continuous_calibration_reselected": False,
        "probability_calibration_reselected": False,
        "trading_strategy_reselected": False,
        "holdout_used_for_selection": False,
        "external_test_used_for_selection": False,
        "all_release_checks_passed": True,
        "release_ready": True,
        "output_hashes": output_hashes,
        "next_stage": (
            "thesis table extraction and final empirical reporting"
        ),
    }

    MANIFEST_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MANIFEST_OUTPUT.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print("NOTEBOOK 15 REPRODUCIBILITY RELEASE AUDIT COMPLETE")
    print("=" * 80)
    print()
    print("Status:", manifest["status"])
    print("Audited commit:", manifest["audited_commit"])
    print("Lineage manifests:", manifest["lineage_manifest_count"])
    print("Verified hashes:", manifest["lineage_hash_check_count"])
    print("Canonical notebooks:", manifest["canonical_notebook_count"])
    print("Tracked files:", manifest["tracked_parent_commit_file_count"])
    print("Full tests:", manifest["full_test_count"])
    print("Release ready:", manifest["release_ready"])
    print()
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
