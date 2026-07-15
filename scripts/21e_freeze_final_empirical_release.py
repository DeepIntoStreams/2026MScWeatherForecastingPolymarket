#!/usr/bin/env python3
"""
21e: Freeze the final Hong Kong empirical release.

This step does not alter any empirical calculation. It records:
- the exact Git commit and branch;
- the declared empirical source steps;
- the final headline results from 21d;
- the integrity status of all source blocks;
- SHA-256 hashes and sizes of the core release artefacts;
- repository-relative paths only;
- a reproducible release index and supervisor-facing freeze report.

The script deliberately excludes:
- local backups;
- logs;
- review bundles;
- temporary files;
- untracked historical repair scripts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


DECLARED_STEPS = [
    "18m",
    "19b",
    "19c",
    "20a",
    "20b",
    "20c",
    "20d",
    "20e",
    "21a",
    "21b",
    "21c",
    "21d",
]

CORE_RELEASE_FILES = [
    "data/processed/18m_supervisor_market_only_key_table.csv",
    "data/processed/18m_market_only_integrity_checks.csv",
    "data/processed/19b_common_support_binary_score_summary.csv",
    "data/processed/19b_common_support_integrity_checks.csv",
    "data/processed/19c_integrity_checks.csv",
    "data/processed/20b_integrity_checks.csv",
    "data/processed/20c_selected_model_manifest.json",
    "data/processed/20d_integrity_checks.csv",
    "data/processed/20e_locked_holdout_integrity_checks.csv",
    "data/processed/20e_locked_holdout_long_model_panel.csv",
    "data/processed/21a_simple_edge_integrity_checks.csv",
    "data/processed/21b_full_event_book_integrity_checks.csv",
    "data/processed/21c_integrity_checks.csv",
    "data/processed/21d_empirical_headline.csv",
    "data/processed/21d_locked_holdout_model_table.csv",
    "data/processed/21d_primary_trading_table.csv",
    "data/processed/21d_primary_robustness_table.csv",
    "data/processed/21d_pipeline_integrity_summary.csv",
    "data/processed/21d_integrity_checks.csv",
    "data/processed/21d_manifest.json",
    "docs/research_outputs/21d_consolidated_empirical_report.md",
    "figures/21d_dissertation_ready_empirical/21d_common_support_brier.png",
    "figures/21d_dissertation_ready_empirical/21d_locked_holdout_brier_ranking.png",
    "figures/21d_dissertation_ready_empirical/21d_primary_trading_headline.png",
    "figures/21d_dissertation_ready_empirical/21d_primary_robustness_headline.png",
]

CORE_RELEASE_ALTERNATIVES = {
    "20a_supervised_feature_matrix": [
        "data/processed/20a_supervised_feature_matrix.csv",
        "data/processed/20a_supervised_feature_matrix.csv.gz",
        "data/processed/20a_feature_matrix.csv",
        "data/processed/20a_feature_matrix.csv.gz",
        "data/processed/20a_supervised_feature_matrix_manifest.json",
        "data/processed/20a_manifest.json",
        "data/processed/20a_integrity_checks.csv",
        "docs/research_outputs/20a_supervised_feature_matrix_report.md",
    ],
}


OPTIONAL_RELEASE_GLOBS = [
    "data/processed/18j_v2*.csv",
    "data/processed/18k*.csv",
    "data/processed/18l*.csv.gz",
    "data/processed/18m*.csv",
    "data/processed/19a*.csv",
    "data/processed/19a*.csv.gz",
    "data/processed/19b*.csv",
    "data/processed/19c*.csv",
    "data/processed/20a*.csv",
    "data/processed/20b*.csv",
    "data/processed/20c*.csv",
    "data/processed/20c*.json",
    "data/processed/20d*.csv",
    "data/processed/20e*.csv",
    "data/processed/20e*.json",
    "data/processed/21a*.csv",
    "data/processed/21a*.json",
    "data/processed/21b*.csv",
    "data/processed/21b*.json",
    "data/processed/21c*.csv",
    "data/processed/21c*.json",
    "data/processed/21d*.csv",
    "data/processed/21d*.json",
    "docs/research_outputs/18m*.md",
    "docs/research_outputs/19b*.md",
    "docs/research_outputs/19c*.md",
    "docs/research_outputs/20a*.md",
    "docs/research_outputs/20b*.md",
    "docs/research_outputs/20c*.md",
    "docs/research_outputs/20d*.md",
    "docs/research_outputs/20e*.md",
    "docs/research_outputs/21a*.md",
    "docs/research_outputs/21b*.md",
    "docs/research_outputs/21c*.md",
    "docs/research_outputs/21d*.md",
    "figures/18m*/*.png",
    "figures/19b*/*.png",
    "figures/19c*/*.png",
    "figures/20a*/*.png",
    "figures/20b*/*.png",
    "figures/20c*/*.png",
    "figures/20d*/*.png",
    "figures/20e*/*.png",
    "figures/21a*/*.png",
    "figures/21b*/*.png",
    "figures/21c*/*.png",
    "figures/21d*/*.png",
]

EXCLUDED_PATH_TERMS = [
    "backup",
    "review_bundle",
    "/logs/",
    ".DS_Store",
    "__pycache__",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--release-name",
        default="hko_empirical_release_v1",
    )
    return parser.parse_args()


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_release_files(
    repo: Path,
) -> tuple[list[Path], list[str], dict[str, str]]:
    """
    Collect release artefacts and resolve historical filename alternatives.

    Every ordinary core path must exist. For each named alternative group,
    at least one candidate must exist; the first candidate in preference order
    is recorded as the resolved canonical artefact.
    """
    files: set[Path] = set()
    missing_core: list[str] = []
    resolved_alternatives: dict[str, str] = {}

    for relative in CORE_RELEASE_FILES:
        path = repo / relative

        if path.exists():
            files.add(path)
        else:
            missing_core.append(relative)

    for group_name, candidates in CORE_RELEASE_ALTERNATIVES.items():
        selected = None

        for relative in candidates:
            path = repo / relative

            if path.exists():
                selected = path
                break

        if selected is None:
            missing_core.append(
                group_name
                + ": none of "
                + str(candidates)
            )
        else:
            files.add(selected)
            resolved_alternatives[group_name] = str(
                selected.relative_to(repo)
            )

    for pattern in OPTIONAL_RELEASE_GLOBS:
        for path in repo.glob(pattern):
            if not path.is_file():
                continue

            relative = str(path.relative_to(repo))

            if any(
                term in relative
                for term in EXCLUDED_PATH_TERMS
            ):
                continue

            files.add(path)

    ordered = sorted(
        files,
        key=lambda p: str(p.relative_to(repo)),
    )

    return (
        ordered,
        missing_core,
        resolved_alternatives,
    )


def file_index(repo: Path, files: Iterable[Path]) -> pd.DataFrame:
    rows = []
    for path in files:
        stat = path.stat()
        rows.append(
            {
                "relative_path": str(path.relative_to(repo)),
                "size_bytes": int(stat.st_size),
                "sha256": sha256_file(path),
                "suffix": "".join(path.suffixes),
            }
        )
    return pd.DataFrame(rows)


def check_integrity_file(path: Path) -> tuple[int, int, bool]:
    frame = pd.read_csv(path, low_memory=False)
    if "passed" not in frame.columns:
        raise ValueError(f"Integrity file lacks passed column: {path}")
    passed = frame["passed"].astype(bool)
    return int(passed.sum()), int(len(frame)), bool(passed.all())


def build_integrity_summary(repo: Path) -> pd.DataFrame:
    paths = [
        ("18m", "data/processed/18m_market_only_integrity_checks.csv"),
        ("19b", "data/processed/19b_common_support_integrity_checks.csv"),
        ("19c", "data/processed/19c_integrity_checks.csv"),
        ("20b", "data/processed/20b_integrity_checks.csv"),
        ("20d", "data/processed/20d_integrity_checks.csv"),
        ("20e", "data/processed/20e_locked_holdout_integrity_checks.csv"),
        ("21a", "data/processed/21a_simple_edge_integrity_checks.csv"),
        ("21b", "data/processed/21b_full_event_book_integrity_checks.csv"),
        ("21c", "data/processed/21c_integrity_checks.csv"),
        ("21d", "data/processed/21d_integrity_checks.csv"),
    ]

    rows = []
    for step, relative in paths:
        path = repo / relative
        if not path.exists():
            rows.append(
                {
                    "step": step,
                    "integrity_file": relative,
                    "checks_passed": 0,
                    "checks_total": 0,
                    "all_checks_passed": False,
                    "file_present": False,
                }
            )
            continue

        checks_passed, checks_total, all_passed = check_integrity_file(path)
        rows.append(
            {
                "step": step,
                "integrity_file": relative,
                "checks_passed": checks_passed,
                "checks_total": checks_total,
                "all_checks_passed": all_passed,
                "file_present": True,
            }
        )

    return pd.DataFrame(rows)


def write_report(
    report_path: Path,
    manifest: dict,
    headline: pd.DataFrame,
    integrity: pd.DataFrame,
    release_index: pd.DataFrame,
):
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Final Hong Kong empirical release freeze",
        "",
        "## Release identity",
        "",
        f"- release name: `{manifest['release_name']}`",
        f"- branch: `{manifest['git_branch']}`",
        f"- commit: `{manifest['git_commit']}`",
        f"- commit subject: `{manifest['git_commit_subject']}`",
        f"- generated at UTC: `{manifest['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "This release freezes the completed Hong Kong empirical pipeline from "
        "market settlement and price recovery through forecast comparison, "
        "leakage-free post-processing, locked-holdout evaluation, trading "
        "simulation, robustness analysis, and dissertation-ready consolidation.",
        "",
        "The release does not claim that historical executable spreads, fees, "
        "slippage, market impact, liquidity constraints, partial fills, or "
        "capital limits were fully reconstructed. Trading outputs remain "
        "hypothetical reduced-form simulations.",
        "",
        "## Consolidated empirical headline",
        "",
        headline.to_markdown(index=False),
        "",
        "## Integrity status",
        "",
        integrity.to_markdown(index=False),
        "",
        "## Release completeness",
        "",
        f"- indexed artefacts: {manifest['indexed_file_count']}",
        f"- indexed bytes: {manifest['indexed_total_bytes']}",
        f"- missing core artefacts: {manifest['missing_core_files']}",
        f"- resolved historical core artefacts: "
        f"{manifest['resolved_core_alternatives']}",
        f"- all recorded integrity checks pass: "
        f"{manifest['all_recorded_integrity_checks_pass']}",
        f"- repository clean apart from permitted untracked local files: "
        f"{manifest['tracked_worktree_clean']}",
        "",
        "## Reproducibility statement",
        "",
        "Every indexed artefact is recorded by repository-relative path, byte "
        "size, and SHA-256 digest. The release can therefore be audited against "
        "the exact Git commit and regenerated empirical outputs.",
        "",
        "## Indexed artefacts",
        "",
        release_index.to_markdown(index=False),
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_zip(repo: Path, paths: Iterable[Path], output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if path.exists():
                zf.write(path, arcname=str(path.relative_to(repo)))


def main() -> int:
    args = parse_args()
    repo = args.repo_root.expanduser().resolve()

    branch = run_git(repo, "branch", "--show-current")
    commit = run_git(repo, "rev-parse", "HEAD")
    commit_subject = run_git(repo, "log", "-1", "--pretty=%s")
    tracked_status = run_git(repo, "status", "--short", "--untracked-files=no")
    tracked_worktree_clean = tracked_status == ""

    headline_path = repo / "data/processed/21d_empirical_headline.csv"
    if not headline_path.exists():
        raise FileNotFoundError(f"Missing 21d headline: {headline_path}")
    headline = pd.read_csv(headline_path, low_memory=False)

    integrity = build_integrity_summary(repo)
    all_integrity = bool(
        integrity["file_present"].astype(bool).all()
        and integrity["all_checks_passed"].astype(bool).all()
    )

    (
        release_files,
        missing_core,
        resolved_core_alternatives,
    ) = collect_release_files(repo)
    release_index = file_index(repo, release_files)

    release_dir = repo / "data" / "releases" / args.release_name
    release_dir.mkdir(parents=True, exist_ok=True)

    index_path = release_dir / "21e_release_file_index.csv"
    integrity_path = release_dir / "21e_release_integrity_summary.csv"
    manifest_path = release_dir / "21e_release_manifest.json"
    report_path = (
        repo
        / "docs"
        / "research_outputs"
        / "21e_final_empirical_release_report.md"
    )
    checks_path = release_dir / "21e_release_integrity_checks.csv"
    issues_path = release_dir / "21e_release_issues.csv"

    release_index.to_csv(index_path, index=False)
    integrity.to_csv(integrity_path, index=False)

    checks = pd.DataFrame(
        [
            {
                "check": "git_branch_expected",
                "passed": branch == "edward-17j-hko-upper-tail-audit",
                "detail": branch,
            },
            {
                "check": "tracked_worktree_clean",
                "passed": tracked_worktree_clean,
                "detail": tracked_status or "clean",
            },
            {
                "check": "21d_headline_nonempty",
                "passed": not headline.empty,
                "detail": f"rows={len(headline)}",
            },
            {
                "check": "all_recorded_integrity_files_present",
                "passed": integrity["file_present"].astype(bool).all(),
                "detail": integrity.to_dict(orient="records").__str__(),
            },
            {
                "check": "all_recorded_integrity_checks_pass",
                "passed": all_integrity,
                "detail": integrity.to_dict(orient="records").__str__(),
            },
            {
                "check": "no_missing_core_release_files",
                "passed": len(missing_core) == 0,
                "detail": str(missing_core),
            },
            {
                "check": "release_index_nonempty",
                "passed": not release_index.empty,
                "detail": f"rows={len(release_index)}",
            },
            {
                "check": "release_paths_are_repository_relative",
                "passed": (
                    not release_index["relative_path"]
                    .astype(str)
                    .str.startswith("/")
                    .any()
                ),
                "detail": "checked",
            },
            {
                "check": "release_hashes_are_sha256",
                "passed": release_index["sha256"].astype(str).str.len().eq(64).all(),
                "detail": "checked",
            },
            {
                "check": "release_excludes_backups_logs_and_review_bundles",
                "passed": not release_index["relative_path"].astype(str).str.contains(
                    "backup|review_bundle|/logs/",
                    regex=True,
                ).any(),
                "detail": "checked",
            },
        ]
    )

    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    manifest = {
        "step": "21e",
        "release_name": args.release_name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_branch": branch,
        "git_commit": commit,
        "git_commit_subject": commit_subject,
        "declared_steps": DECLARED_STEPS,
        "headline_source": "data/processed/21d_empirical_headline.csv",
        "indexed_file_count": int(len(release_index)),
        "indexed_total_bytes": int(release_index["size_bytes"].sum()),
        "missing_core_files": missing_core,
        "resolved_core_alternatives": (
            resolved_core_alternatives
        ),
        "tracked_worktree_clean": tracked_worktree_clean,
        "all_recorded_integrity_checks_pass": all_integrity,
        "forecast_specification_changed": False,
        "calibration_specification_changed": False,
        "validation_design_changed": False,
        "trading_specification_changed": False,
        "hash_algorithm": "SHA-256",
        "paths_are_repository_relative": True,
        "release_is_a_freeze_not_a_new_model": True,
    }

    checks.to_csv(checks_path, index=False)
    issues.to_csv(issues_path, index=False)
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    write_report(
        report_path,
        manifest,
        headline,
        integrity,
        release_index,
    )

    review_zip = repo / "data" / "review_bundles" / "21e_review_bundle.zip"
    build_zip(
        repo,
        [
            index_path,
            integrity_path,
            manifest_path,
            checks_path,
            issues_path,
            report_path,
            headline_path,
            repo / "data/processed/21d_manifest.json",
            repo / "data/processed/21d_integrity_checks.csv",
        ],
        review_zip,
    )

    print("21e completed.")
    print(f"Release name: {args.release_name}")
    print(f"Git commit: {commit}")
    print(f"Indexed files: {len(release_index)}")
    print(f"Checks passed: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more 21e checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
