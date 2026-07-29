from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path.cwd()
CONFIG = ROOT / "config/v2_completion/phase24_thesis_handover_spec.json"
OUTPUT = ROOT / "outputs/v2_completion/phase24_thesis_writing_handover"
PACKAGE = OUTPUT / "package"
ZIP_PATH = OUTPUT / "phase24_thesis_writing_handover.zip"
PHASE22 = ROOT / "outputs/v2_completion/phase22_thesis_evidence_pack"
PHASE23 = ROOT / "outputs/v2_completion/phase23_final_freeze"
SUPPORT = [
    ROOT / "REPRODUCIBILITY_V2.md",
    ROOT / "environment-v2-completion.yml",
    ROOT / "requirements-v2-completion.txt",
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def require(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path.relative_to(ROOT)}")


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store", ".ipynb_checkpoints"),
    )


def main() -> None:
    for path in [PHASE22, PHASE23, *SUPPORT]:
        require(path)

    report23 = PHASE23 / "phase23_report.md"
    checks23 = PHASE23 / "phase23_validation_checks.csv"
    gaps23 = PHASE23 / "phase23_gap_closure_register.csv"
    metrics23 = PHASE23 / "phase23_frozen_key_metrics.csv"
    instruction22 = PHASE22 / "phase22_empirical_instruction_book.md"
    handover23 = PHASE23 / "phase23_thesis_handover.md"

    for path in [report23, checks23, gaps23, metrics23, instruction22, handover23]:
        require(path)

    if "## Status\n\nPASSED" not in report23.read_text(encoding="utf-8"):
        raise RuntimeError("Phase 23 report is not certified PASSED.")

    checks = read_csv(checks23)
    if len(checks) != 13 or any(r.get("status") != "PASSED" for r in checks):
        raise RuntimeError("Phase 23 validation registry is not exactly 13 passed checks.")

    gaps = read_csv(gaps23)
    if len(gaps) != 17 or any(r.get("status_after_phase23") != "CLOSED" for r in gaps):
        raise RuntimeError("Phase 23 gap register is not exactly 17 closed gaps.")

    metrics = read_csv(metrics23)
    if len(metrics) != 23 or any(r.get("freeze_status") != "FROZEN" for r in metrics):
        raise RuntimeError("Phase 23 metric registry is not exactly 23 frozen metrics.")

    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True)

    copy_tree(PHASE22, PACKAGE / "phase22_thesis_evidence_pack")
    copy_tree(PHASE23, PACKAGE / "phase23_final_freeze")

    support_dir = PACKAGE / "reproducibility_support"
    support_dir.mkdir()
    for source in SUPPORT:
        shutil.copy2(source, support_dir / source.name)

    empirical_sha = git("rev-list", "-n", "1", "v2-empirical-complete")
    branch = git("branch", "--show-current")

    start_here = f"""# START HERE: Version 2 Thesis-Writing Handover

## Status

PASSED

## Authoritative reading order

1. `phase23_final_freeze/phase23_thesis_handover.md`
2. `phase22_thesis_evidence_pack/phase22_empirical_instruction_book.md`
3. `phase23_final_freeze/phase23_frozen_key_metrics.csv`
4. `phase23_final_freeze/phase23_validation_checks.csv`
5. `phase23_final_freeze/phase23_frozen_file_inventory.csv`

## Final identifiers

- Branch: `{branch}`
- Empirical freeze commit: `{empirical_sha}`
- Empirical freeze tag: `v2-empirical-complete`
- Phase 23 checks: 13 passed
- Frozen key metrics: 23
- Closed empirical gaps: G01-G17
- Open empirical gaps: 0

## Central thesis focus

The main contribution is the rigorous conversion of deterministic IFS daily-maximum forecasts into local probabilistic forecasts using rule-specific static Gaussian correction and Gaussian process regression. CatBoost and broad machine-learning ensembles remain secondary and must not dilute the central mathematical argument.

## Final empirical story

1. The deterministic forecast contains substantial systematic local error.
2. Static Gaussian correction materially improves the raw point forecast.
3. The Matern-3/2 GP improves further in aggregate and across all four decision rules, but not in every chronological block.
4. Calibration remains imperfect, with undercoverage, serial dependence and remaining conditional-variance structure.
5. On June exact common support, Polymarket outperforms the weather-only GP.
6. The development-selected convex pool improves on the GP but not on the market.
7. The evidence does not establish live arbitrage, model dominance or causal private information.

## Mandatory boundaries

- Preserve chronological separation and exact common support.
- Use target date as the uncertainty unit.
- Do not impute missing forecasts or market prices.
- Do not tune on June outcomes.
- Do not alter frozen metrics.
- Do not claim GP dominance over Polymarket.
- Do not claim the pool dominates both inputs.
- Do not restore CatBoost as a major thesis strand.
"""
    (PACKAGE / "START_HERE.md").write_text(start_here, encoding="utf-8", newline="\n")

    package_files = sorted(p for p in PACKAGE.rglob("*") if p.is_file())
    forbidden = [
        p for p in package_files
        if "__pycache__" in p.parts
        or ".ipynb_checkpoints" in p.parts
        or p.suffix.lower() in {".pyc", ".pyo", ".joblib", ".pkl", ".pickle"}
    ]
    if forbidden:
        raise RuntimeError("Forbidden runtime or fitted-model files entered the package.")

    manifest_rows = [
        {
            "relative_path": str(p.relative_to(PACKAGE)),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
            "status": "PASSED",
        }
        for p in package_files
    ]
    write_csv(PACKAGE / "FILE_MANIFEST.csv", manifest_rows, ["relative_path", "bytes", "sha256", "status"])

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(x for x in PACKAGE.rglob("*") if x.is_file()):
            z.write(p, p.relative_to(PACKAGE))

    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        if z.testzip() is not None:
            raise RuntimeError("ZIP integrity test failed.")
        names = set(z.namelist())

    required_members = {
        "START_HERE.md",
        "FILE_MANIFEST.csv",
        "phase22_thesis_evidence_pack/phase22_empirical_instruction_book.md",
        "phase23_final_freeze/phase23_thesis_handover.md",
        "phase23_final_freeze/phase23_frozen_key_metrics.csv",
    }
    missing = required_members - names
    if missing:
        raise RuntimeError("Required ZIP members are missing: " + ", ".join(sorted(missing)))
    if ZIP_PATH.stat().st_size > 25 * 1024 * 1024:
        raise RuntimeError("Handover ZIP exceeds 25 MiB.")

    checks24 = [
        ["H01", "Phase 23 report", "PASSED", "PASSED"],
        ["H02", "Phase 23 validation checks", "PASSED", "13 passed"],
        ["H03", "Phase 23 gaps", "PASSED", "17 closed"],
        ["H04", "Phase 23 frozen metrics", "PASSED", "23 frozen"],
        ["H05", "Runtime/model exclusions", "PASSED", "0 forbidden"],
        ["H06", "ZIP integrity", "PASSED", f"{len(names)} members"],
        ["H07", "Required package members", "PASSED", "all present"],
    ]
    write_csv(
        OUTPUT / "phase24_validation_checks.csv",
        [dict(check_id=a, description=b, status=c, observed=d) for a, b, c, d in checks24],
        ["check_id", "description", "status", "observed"],
    )

    message = """# Message for the Dedicated Overleaf Thesis-Writing Chat

Read `START_HERE.md`, then the Phase 23 handover, then the Phase 22 empirical instruction book. Treat all Phase 23 metrics and evidential boundaries as frozen. The thesis should focus narrowly and rigorously on deterministic IFS post-processing, static Gaussian correction and Gaussian process regression. CatBoost and broad ensemble methods are secondary only. Select the strongest evidence rather than inserting every diagnostic mechanically.
"""
    (OUTPUT / "phase24_message_to_overleaf_chat.md").write_text(message, encoding="utf-8", newline="\n")

    report = f"""# Phase 24 Thesis-Writing Handover and Archive

## Status

PASSED

## Starting boundary

- Empirical freeze commit: `{empirical_sha}`.
- Empirical freeze tag: `v2-empirical-complete`.
- Phase 23 checks revalidated: 13.
- Frozen metrics revalidated: 23.
- Empirical gaps revalidated: 17 closed, 0 open.

## Result

A lightweight thesis-writing ZIP was created containing the complete Phase 22 evidence pack, the Phase 23 final freeze pack, reproducibility support files, a START_HERE guide and a checksum manifest. No fitted model, raw data, Python bytecode or notebook checkpoint was included.

## Non-empirical boundary

Phase 24 does not alter the empirical freeze. It creates only a writing and archive handover.

## Main output

`outputs/v2_completion/phase24_thesis_writing_handover/phase24_thesis_writing_handover.zip`
"""
    (OUTPUT / "phase24_report.md").write_text(report, encoding="utf-8", newline="\n")

    spec = {
        "phase": 24,
        "title": "Thesis-writing handover and archive",
        "status": "PASSED",
        "non_empirical_phase": True,
        "source_branch": branch,
        "empirical_freeze_commit": empirical_sha,
        "empirical_freeze_tag": "v2-empirical-complete",
        "handover_tag": "v2-thesis-handover-ready",
        "validation_checks": 7,
        "zip_relative_path": str(ZIP_PATH.relative_to(ROOT)),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
    }
    CONFIG.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    outputs = sorted(p for p in OUTPUT.rglob("*") if p.is_file() and p.name != "phase24_manifest.json")
    manifest = {
        "phase": 24,
        "status": "PASSED",
        "empirical_freeze_commit": empirical_sha,
        "outputs": [
            {"relative_path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in outputs
        ],
        "config": {
            "relative_path": str(CONFIG.relative_to(ROOT)),
            "bytes": CONFIG.stat().st_size,
            "sha256": sha256(CONFIG),
        },
    }
    (OUTPUT / "phase24_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print("PHASE24_STATUS=PASSED")
    print("PHASE24_VALIDATION_CHECKS=7")
    print(f"PHASE24_ZIP_BYTES={ZIP_PATH.stat().st_size}")
    print(f"PHASE24_ZIP_SHA256={sha256(ZIP_PATH)}")
    print(f"PHASE24_ZIP={ZIP_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
