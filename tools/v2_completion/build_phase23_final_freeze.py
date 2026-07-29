from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

ROOT = Path.cwd()
CONFIG_PATH = ROOT / "config/v2_completion/phase23_final_freeze_spec.json"
OUTPUT_DIR = ROOT / "outputs/v2_completion/phase23_final_freeze"

PHASE22_DIR = ROOT / "outputs/v2_completion/phase22_thesis_evidence_pack"
PHASE22_SPEC = ROOT / "config/v2_completion/phase22_thesis_evidence_pack_spec.json"
PHASE22_MANIFEST = PHASE22_DIR / "phase22_manifest.json"
PHASE22_REPORT = PHASE22_DIR / "phase22_report.md"
PHASE22_GAPS = PHASE22_DIR / "phase22_gap_closure_register.csv"
PHASE22_METRICS = PHASE22_DIR / "phase22_key_metrics.csv"
PHASE22_CLAIMS = PHASE22_DIR / "phase22_claim_register.csv"
PHASE22_BOUNDARIES = PHASE22_DIR / "phase22_evidential_boundaries.csv"
PHASE22_SOURCE_INVENTORY = PHASE22_DIR / "phase22_source_inventory.csv"

PHASE21_COMPARISON = ROOT / "outputs/v2_completion/phase21_artifact_comparison.csv"
PHASE21_REPORT_CANDIDATES = (
    ROOT / "outputs/v2_completion",
    ROOT / "outputs/v2/diagnostics",
)

REPRO_DOCS = [
    ROOT / "REPRODUCIBILITY_V2.md",
    ROOT / "environment-v2-completion.yml",
    ROOT / "requirements-v2-completion.txt",
]

CANONICAL_INPUT = (
    ROOT
    / "data/processed/18s_expanded_march_june_canonical_sample"
    / "18s_expanded_certified_contract_outcome_panel.csv"
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", errors="strict", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"Missing {label}: {path.relative_to(ROOT)}")


def tracked(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path.relative_to(ROOT))],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def is_runtime_artifact(path: Path) -> bool:
    """Return True for generated local files that must not enter the freeze."""
    relative = path.relative_to(ROOT)
    parts = set(relative.parts)
    name = path.name.lower()
    suffix = path.suffix.lower()

    return (
        "__pycache__" in parts
        or ".ipynb_checkpoints" in parts
        or suffix in {".pyc", ".pyo"}
        or name in {".ds_store"}
    )


def find_phase21_report() -> Path:
    candidates: list[Path] = []
    for base in PHASE21_REPORT_CANDIDATES:
        if not base.exists():
            continue
        candidates.extend(
            path
            for path in base.rglob("*.md")
            if "phase21" in path.name.lower()
            and "report" in path.name.lower()
        )
    if not candidates:
        raise RuntimeError("Phase 21 report was not found.")
    candidates.sort(key=lambda path: (len(str(path)), str(path)))
    return candidates[0]


def manifest_output_map(manifest: dict) -> dict[str, str]:
    return {
        str(item["relative_path"]): str(item["sha256"])
        for item in manifest.get("outputs", [])
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    phase22_commit = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    commit_time = git("show", "-s", "--format=%cI", "HEAD")

    required = [
        PHASE22_SPEC,
        PHASE22_MANIFEST,
        PHASE22_REPORT,
        PHASE22_GAPS,
        PHASE22_METRICS,
        PHASE22_CLAIMS,
        PHASE22_BOUNDARIES,
        PHASE22_SOURCE_INVENTORY,
        PHASE21_COMPARISON,
        CANONICAL_INPUT,
        *REPRO_DOCS,
    ]
    for path in required:
        require_file(path, "required Phase 23 input")

    phase21_report = find_phase21_report()
    require_file(phase21_report, "Phase 21 report")

    checks: list[dict] = []

    def record(
        check_id: str,
        description: str,
        status: str,
        observed: str,
        expected: str,
        evidence: str,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "description": description,
                "status": status,
                "observed": observed,
                "expected": expected,
                "evidence": evidence,
            }
        )
        if status != "PASSED":
            raise RuntimeError(
                f"{check_id} failed: {description}; "
                f"observed={observed}; expected={expected}"
            )

    phase22_spec = json.loads(PHASE22_SPEC.read_text(encoding="utf-8"))
    record(
        "F01",
        "Phase 22 specification status",
        "PASSED" if phase22_spec.get("status") == "PASSED" else "FAILED",
        str(phase22_spec.get("status")),
        "PASSED",
        str(PHASE22_SPEC.relative_to(ROOT)),
    )

    report_text = PHASE22_REPORT.read_text(encoding="utf-8", errors="strict")
    record(
        "F02",
        "Phase 22 report status",
        "PASSED" if "## Status\n\nPASSED" in report_text else "FAILED",
        "PASSED" if "PASSED" in report_text else "not found",
        "PASSED",
        str(PHASE22_REPORT.relative_to(ROOT)),
    )

    phase22_manifest = json.loads(PHASE22_MANIFEST.read_text(encoding="utf-8"))
    output_hashes = manifest_output_map(phase22_manifest)
    manifest_failures: list[str] = []

    for relative, expected_hash in output_hashes.items():
        path = ROOT / relative
        if not path.is_file():
            manifest_failures.append(f"missing:{relative}")
            continue
        observed_hash = sha256(path)
        if observed_hash != expected_hash:
            manifest_failures.append(f"hash:{relative}")

    config_meta = phase22_manifest.get("config", {})
    config_relative = str(config_meta.get("relative_path", ""))
    config_expected = str(config_meta.get("sha256", ""))
    if not config_relative or not config_expected:
        manifest_failures.append("config metadata absent")
    else:
        config_path = ROOT / config_relative
        if not config_path.is_file():
            manifest_failures.append(f"missing:{config_relative}")
        elif sha256(config_path) != config_expected:
            manifest_failures.append(f"hash:{config_relative}")

    record(
        "F03",
        "Phase 22 manifest hashes",
        "PASSED" if not manifest_failures else "FAILED",
        "0 failures" if not manifest_failures else "; ".join(manifest_failures[:8]),
        "0 failures",
        str(PHASE22_MANIFEST.relative_to(ROOT)),
    )

    source_inventory_all = read_csv(PHASE22_SOURCE_INVENTORY)
    source_inventory: list[dict[str, str]] = []
    excluded_runtime_rows: list[dict[str, str]] = []

    for row in source_inventory_all:
        relative = row.get("relative_path", "")
        path = ROOT / relative
        if is_runtime_artifact(path):
            excluded_runtime_rows.append(row)
        else:
            source_inventory.append(row)

    source_failures: list[str] = []
    for row in source_inventory:
        relative = row.get("relative_path", "")
        expected_hash = row.get("sha256", "")
        path = ROOT / relative
        if not path.is_file():
            source_failures.append(f"missing:{relative}")
            continue
        if sha256(path) != expected_hash:
            source_failures.append(f"hash:{relative}")

    expected_sources = len(source_inventory)

    record(
        "F04",
        "Phase 14-21 substantive source-inventory reconciliation",
        "PASSED" if not source_failures else "FAILED",
        (
            f"{len(source_inventory)} substantive files, "
            f"{len(excluded_runtime_rows)} runtime artifacts excluded, "
            "0 failures"
            if not source_failures
            else "; ".join(source_failures[:8])
        ),
        (
            f"{expected_sources} substantive files, "
            f"{len(excluded_runtime_rows)} runtime artifacts excluded, "
            "0 failures"
        ),
        str(PHASE22_SOURCE_INVENTORY.relative_to(ROOT)),
    )

    phase21_rows = read_csv(PHASE21_COMPARISON)
    phase21_failures = [
        row
        for row in phase21_rows
        if row.get("status", "").upper() != "PASSED"
    ]
    record(
        "F05",
        "Phase 21 clean-environment artifact comparisons",
        (
            "PASSED"
            if len(phase21_rows) == 116 and not phase21_failures
            else "FAILED"
        ),
        f"{len(phase21_rows)} compared, {len(phase21_failures)} failed",
        "116 compared, 0 failed",
        str(PHASE21_COMPARISON.relative_to(ROOT)),
    )

    phase21_text = phase21_report.read_text(encoding="utf-8", errors="strict")
    phase21_pass = (
        "PASSED" in phase21_text.upper()
        and (
            "116" in phase21_text
            or "ARTIFACTS_COMPARED=116" in phase21_text
        )
    )
    record(
        "F06",
        "Phase 21 report certification",
        "PASSED" if phase21_pass else "FAILED",
        "PASSED with 116 artifact comparisons" if phase21_pass else "not certified",
        "PASSED with 116 artifact comparisons",
        str(phase21_report.relative_to(ROOT)),
    )

    metric_rows = read_csv(PHASE22_METRICS)
    expected_metrics = int(
        phase22_spec.get("counts", {}).get("key_metrics", len(metric_rows))
    )
    unverified_metrics = [
        row
        for row in metric_rows
        if row.get("status", "").upper() != "VERIFIED"
    ]
    record(
        "F07",
        "Phase 22 key-metric registry",
        (
            "PASSED"
            if len(metric_rows) == expected_metrics and not unverified_metrics
            else "FAILED"
        ),
        f"{len(metric_rows)} metrics, {len(unverified_metrics)} unverified",
        f"{expected_metrics} metrics, 0 unverified",
        str(PHASE22_METRICS.relative_to(ROOT)),
    )

    claim_rows = read_csv(PHASE22_CLAIMS)
    boundary_rows = read_csv(PHASE22_BOUNDARIES)
    expected_claims = int(
        phase22_spec.get("counts", {}).get("claims", len(claim_rows))
    )
    expected_boundaries = int(
        phase22_spec.get("counts", {}).get(
            "evidential_boundaries",
            len(boundary_rows),
        )
    )
    record(
        "F08",
        "Claim and evidential-boundary registries",
        (
            "PASSED"
            if len(claim_rows) == expected_claims
            and len(boundary_rows) == expected_boundaries
            else "FAILED"
        ),
        f"{len(claim_rows)} claims, {len(boundary_rows)} boundaries",
        f"{expected_claims} claims, {expected_boundaries} boundaries",
        (
            f"{PHASE22_CLAIMS.relative_to(ROOT)};"
            f"{PHASE22_BOUNDARIES.relative_to(ROOT)}"
        ),
    )

    gap_rows = read_csv(PHASE22_GAPS)
    gap_status = {
        row.get("gap_id", ""): row.get("status_after_phase22", "")
        for row in gap_rows
    }
    expected_phase22_gaps = {
        **{f"G{number:02d}": "CLOSED" for number in range(1, 17)},
        "G17": "OPEN",
    }
    gap_ok = gap_status == expected_phase22_gaps
    record(
        "F09",
        "Phase 22 gap boundary",
        "PASSED" if gap_ok else "FAILED",
        json.dumps(gap_status, sort_keys=True),
        json.dumps(expected_phase22_gaps, sort_keys=True),
        str(PHASE22_GAPS.relative_to(ROOT)),
    )

    support_constraints = phase22_spec.get("design_constraints", {})
    required_constraints = {
        "no_model_refit": True,
        "no_kernel_reselection": True,
        "no_missing_forecast_imputation": True,
        "june_not_used_for_development": True,
        "exact_common_support_preserved": True,
        "date_is_uncertainty_unit": True,
    }
    constraint_ok = all(
        support_constraints.get(key) is value
        for key, value in required_constraints.items()
    )
    record(
        "F10",
        "Frozen empirical-design constraints",
        "PASSED" if constraint_ok else "FAILED",
        json.dumps(support_constraints, sort_keys=True),
        json.dumps(required_constraints, sort_keys=True),
        str(PHASE22_SPEC.relative_to(ROOT)),
    )

    reproducibility_failures: list[str] = []
    for path in [*REPRO_DOCS, CANONICAL_INPUT]:
        if not tracked(path):
            reproducibility_failures.append(
                f"untracked:{path.relative_to(ROOT)}"
            )

    record(
        "F11",
        "Reproducibility documents and frozen canonical input are tracked",
        "PASSED" if not reproducibility_failures else "FAILED",
        (
            "all tracked"
            if not reproducibility_failures
            else "; ".join(reproducibility_failures)
        ),
        "all tracked",
        (
            ";".join(str(path.relative_to(ROOT)) for path in REPRO_DOCS)
            + ";"
            + str(CANONICAL_INPUT.relative_to(ROOT))
        ),
    )

    source_commit_matches = (
        phase22_spec.get("source_commit") == phase22_manifest.get("source_commit")
    )
    record(
        "F12",
        "Phase 22 source-commit consistency",
        "PASSED" if source_commit_matches else "FAILED",
        (
            f"spec={phase22_spec.get('source_commit')};"
            f"manifest={phase22_manifest.get('source_commit')}"
        ),
        "matching source commits",
        (
            f"{PHASE22_SPEC.relative_to(ROOT)};"
            f"{PHASE22_MANIFEST.relative_to(ROOT)}"
        ),
    )

    final_gap_rows: list[dict] = []
    for number in range(1, 18):
        gap_id = f"G{number:02d}"
        previous = gap_status.get(gap_id, "")
        if gap_id == "G17":
            description = "Independent final freeze"
            closing_phase = 23
            closure_evidence = (
                "Phase 23 independently reconciles the Phase 22 manifest, "
                "source inventory, key metrics, claims, boundaries and the "
                "Phase 21 clean replay before freezing the empirical branch."
            )
        else:
            matching = [
                row for row in gap_rows if row.get("gap_id") == gap_id
            ]
            description = (
                matching[0].get("description", "")
                if matching
                else f"Previously closed gap {gap_id}"
            )
            closing_phase = (
                int(matching[0].get("closing_phase", "0") or 0)
                if matching
                else 0
            )
            closure_evidence = (
                matching[0].get("evidence_report", "")
                if matching
                else ""
            )

        final_gap_rows.append(
            {
                "gap_id": gap_id,
                "description": description,
                "status_before_phase23": previous,
                "status_after_phase23": "CLOSED",
                "closing_phase": closing_phase,
                "closure_evidence": closure_evidence,
            }
        )

    frozen_paths: set[Path] = set()

    for row in source_inventory:
        path = ROOT / row["relative_path"]
        if not is_runtime_artifact(path):
            frozen_paths.add(path)

    frozen_paths.update(
        path
        for path in PHASE22_DIR.rglob("*")
        if path.is_file()
    )
    frozen_paths.update(
        {
            PHASE22_SPEC,
            PHASE21_COMPARISON,
            phase21_report,
            CANONICAL_INPUT,
            *REPRO_DOCS,
            ROOT / "tools/v2_completion/build_phase22_thesis_evidence_pack.py",
            ROOT / "tests/v2_completion/test_phase22_evidence_pack.py",
        }
    )

    inventory_rows: list[dict] = []
    untracked_frozen: list[str] = []

    for path in sorted(
        frozen_paths,
        key=lambda item: str(item.relative_to(ROOT)),
    ):
        if not path.is_file():
            raise RuntimeError(
                f"Frozen file is missing: {path.relative_to(ROOT)}"
            )

        is_tracked = tracked(path)
        if not is_tracked:
            untracked_frozen.append(str(path.relative_to(ROOT)))

        relative = str(path.relative_to(ROOT))
        phase_match = re.search(r"phase(\d+)", relative.lower())
        phase = int(phase_match.group(1)) if phase_match else ""

        inventory_rows.append(
            {
                "phase": phase,
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "tracked": str(is_tracked),
                "freeze_role": (
                    "phase22_evidence_pack"
                    if str(path).startswith(str(PHASE22_DIR))
                    else "certified_source_or_reproducibility_input"
                ),
                "status": "PASSED" if is_tracked else "FAILED",
            }
        )

    record(
        "F13",
        "All substantive frozen files are committed before the final freeze",
        "PASSED" if not untracked_frozen else "FAILED",
        (
            f"{len(inventory_rows)} tracked files"
            if not untracked_frozen
            else "; ".join(untracked_frozen[:10])
        ),
        "all frozen files tracked",
        "phase23_frozen_file_inventory.csv",
    )

    write_csv(
        OUTPUT_DIR / "phase23_validation_checks.csv",
        checks,
        [
            "check_id",
            "description",
            "status",
            "observed",
            "expected",
            "evidence",
        ],
    )
    write_csv(
        OUTPUT_DIR / "phase23_gap_closure_register.csv",
        final_gap_rows,
        [
            "gap_id",
            "description",
            "status_before_phase23",
            "status_after_phase23",
            "closing_phase",
            "closure_evidence",
        ],
    )
    write_csv(
        OUTPUT_DIR / "phase23_frozen_file_inventory.csv",
        inventory_rows,
        [
            "phase",
            "relative_path",
            "bytes",
            "sha256",
            "tracked",
            "freeze_role",
            "status",
        ],
    )

    frozen_metric_rows = []
    for row in metric_rows:
        frozen_metric_rows.append(
            {
                **row,
                "phase22_registry_sha256": sha256(PHASE22_METRICS),
                "phase23_source_commit": phase22_commit,
                "freeze_status": "FROZEN",
            }
        )
    write_csv(
        OUTPUT_DIR / "phase23_frozen_key_metrics.csv",
        frozen_metric_rows,
        [
            *list(metric_rows[0].keys()),
            "phase22_registry_sha256",
            "phase23_source_commit",
            "freeze_status",
        ],
    )

    headline = {
        row["metric"]: row["value"]
        for row in metric_rows
    }

    release_notes = f"""# Version 2 Empirical Completion Release Notes

## Status

PASSED

## Freeze boundary

The Version 2 empirical programme is frozen from source commit
`{phase22_commit}` on branch `{branch}`. Phase 23 independently verifies the
Phase 22 evidence pack and the Phase 21 clean replay before creating the final
freeze commit and annotated tag.

## Final closed scope

All empirical gaps G01-G17 are closed. The completed scope comprises:

1. exact GP code-to-mathematics reconciliation;
2. raw deterministic and static Gaussian chronological benchmarks;
3. deterministic-error and missing-support analysis;
4. rule and validation-block GP stability;
5. calibration, sharpness, dependence and conditional-variance diagnostics;
6. exact-common-support GP-market comparison;
7. development-selected convex forecast combination;
8. clean-environment reproducibility;
9. consolidated thesis evidence and final independent freeze.

## Headline empirical results

- Raw point mean date CRPS:
  {headline.get("Raw point mean date CRPS", "see frozen registry")}.
- Static Gaussian mean date CRPS:
  {headline.get("Static Gaussian mean date CRPS", "see frozen registry")}.
- Matern-3/2 GP mean date CRPS:
  {headline.get("Matern 3/2 GP mean date CRPS", "see frozen registry")}.
- Matern-3/2 minus static Gaussian CRPS:
  {headline.get("Matern 3/2 minus static Gaussian CRPS", "see frozen registry")}.
- Selected development-period GP combination weight:
  {headline.get("Selected GP combination weight", "see frozen registry")}.
- Post-hoc June oracle GP weight:
  {headline.get("Post-hoc June oracle GP weight", "see frozen registry")}.

## Reproducibility result

Phases 15-20 replay successfully in a clean environment. The certified Phase 21
registry contains 116 passed artifact comparisons and zero failed comparisons.

## Interpretation boundary

The final empirical conclusion is not that the GP dominates Polymarket or
establishes arbitrage. The GP materially improves raw and static weather
benchmarks, but Polymarket performs better on June exact common support. The
development-selected pool improves on the GP but not on the market.
"""

    thesis_handover = f"""# Final Empirical Handover for Thesis Writing

## Authoritative writing source

Use:

`outputs/v2_completion/phase22_thesis_evidence_pack/phase22_empirical_instruction_book.md`

as the detailed empirical instruction book.

Use:

`outputs/v2_completion/phase23_final_freeze/phase23_frozen_key_metrics.csv`

for final headline values and:

`outputs/v2_completion/phase23_final_freeze/phase23_frozen_file_inventory.csv`

for exact source tracing.

## Final thesis story

The study converts deterministic IFS daily-maximum forecasts into local
probabilistic forecasts for Hong Kong temperature contracts. A rule-specific
static Gaussian benchmark isolates simple local bias-and-scale correction. A
Matern-3/2 GP then models conditional residual structure and improves on that
benchmark in aggregate and across all four decision rules, though not in every
chronological block.

Predictive diagnostics show that the GP is useful rather than fully adequate:
undercoverage, serial dependence and remaining conditional-variance structure
persist. On June exact common support, Polymarket outperforms the weather-only
GP. A development-selected convex pool improves on the GP but not the market.
This supports a careful conclusion about model value, limitations and market
information rather than a claim of forecast or trading dominance.

## Mandatory boundaries

- Do not impute missing forecasts or market prices.
- Do not use June outcomes for model, kernel, combination-weight or trading-rule
  selection.
- Do not treat four decision rules on one date as independent weather outcomes.
- Do not claim the GP dominates Polymarket.
- Do not claim the convex pool dominates both inputs.
- Do not infer causal private information from GP-market disagreement.
- Do not claim live-executable arbitrage.
- Do not restore CatBoost or broad ensemble modelling as a central contribution.

## Reproducibility sentence

A clean-environment replay regenerated Phases 15-20 and compared 116 artifacts,
all of which passed, with zero maximum finite numerical discrepancy.

## Final release identifiers

- Source branch before the Phase 23 commit: `{branch}`.
- Phase 22 source commit: `{phase22_commit}`.
- Intended final annotated tag: `v2-empirical-complete`.
"""

    (OUTPUT_DIR / "phase23_release_notes.md").write_text(
        release_notes,
        encoding="utf-8",
        newline="\n",
    )
    (OUTPUT_DIR / "phase23_thesis_handover.md").write_text(
        thesis_handover,
        encoding="utf-8",
        newline="\n",
    )

    report = f"""# Phase 23 Independent Final Empirical Freeze

## Status

PASSED

## Starting boundary

- Branch: `{branch}`.
- Phase 22 commit: `{phase22_commit}`.
- Phase 22 commit time: `{commit_time}`.
- Independent validation checks: {len(checks)}.
- Frozen files inventoried: {len(inventory_rows)}.
- Frozen key metrics: {len(metric_rows)}.

## Independent validation result

Phase 23 verifies:

1. the Phase 22 specification and report status;
2. every Phase 22 manifest hash;
3. every Phase 14-21 source-inventory hash;
4. all 116 Phase 21 clean-environment artifact comparisons;
5. the Phase 22 key-metric, claim and evidential-boundary registries;
6. the exact support and chronology constraints;
7. the tracked reproducibility documents and canonical frozen input;
8. the full frozen-file inventory.

All checks pass.

## Gap status

- G01-G17: CLOSED.
- Remaining empirical gaps: 0.

## Final empirical boundary

The empirical pipeline is now frozen. Later thesis writing may select, condense
and rearrange the certified evidence, but it must not silently refit models,
change support, tune on June, impute missing forecasts, or revise headline
results without opening a separately documented empirical version.

## Final release

After this report is committed, the annotated tag `v2-empirical-complete` marks
the final Version 2 empirical release.
"""

    (OUTPUT_DIR / "phase23_report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    checksums_path = OUTPUT_DIR / "phase23_checksums.sha256"
    checksum_lines = [
        f"{row['sha256']}  {row['relative_path']}"
        for row in inventory_rows
    ]
    checksums_path.write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    config = {
        "phase": 23,
        "title": "Independent final empirical freeze",
        "status": "PASSED",
        "source_branch": branch,
        "phase22_commit": phase22_commit,
        "phase22_commit_time": commit_time,
        "final_tag": "v2-empirical-complete",
        "validation": {
            "checks": len(checks),
            "failed_checks": 0,
            "phase21_artifacts_compared": len(phase21_rows),
            "phase21_failed_comparisons": len(phase21_failures),
            "phase22_source_files_reconciled": len(source_inventory),
            "phase23_frozen_files": len(inventory_rows),
            "frozen_key_metrics": len(metric_rows),
        },
        "gaps": {
            "closed": 17,
            "open": 0,
        },
        "design_constraints": required_constraints,
        "no_new_empirical_estimation": True,
    }
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    output_files = sorted(
        path
        for path in OUTPUT_DIR.iterdir()
        if path.is_file()
        and path.name != "phase23_manifest.json"
    )
    manifest = {
        "phase": 23,
        "status": "PASSED",
        "phase22_commit": phase22_commit,
        "outputs": [
            {
                "relative_path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in output_files
        ],
        "config": {
            "relative_path": str(CONFIG_PATH.relative_to(ROOT)),
            "bytes": CONFIG_PATH.stat().st_size,
            "sha256": sha256(CONFIG_PATH),
        },
    }
    (OUTPUT_DIR / "phase23_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("PHASE23_STATUS=PASSED")
    print(f"PHASE23_VALIDATION_CHECKS={len(checks)}")
    print("PHASE23_FAILED_CHECKS=0")
    print(f"PHASE23_FROZEN_FILES={len(inventory_rows)}")
    print(f"PHASE23_FROZEN_KEY_METRICS={len(metric_rows)}")
    print("PHASE23_CLOSED_GAPS=17")
    print("PHASE23_OPEN_GAPS=0")
    print("PHASE23_FINAL_TAG=v2-empirical-complete")


if __name__ == "__main__":
    main()
