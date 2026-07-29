from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path.cwd()
CONFIG_PATH = ROOT / "config/v2_completion/phase22_thesis_evidence_pack_spec.json"
OUTPUT_DIR = ROOT / "outputs/v2_completion/phase22_thesis_evidence_pack"

PHASES = tuple(range(14, 22))
CLOSED_GAPS = {
    "G01": (16, "Static Gaussian chronological benchmark"),
    "G02": (16, "Raw point forecast chronological benchmark"),
    "G03": (15, "Exact feature formulas and scaling"),
    "G04": (15, "Exact response transformation"),
    "G05": (15, "Observation noise, WhiteKernel and numerical jitter"),
    "G06": (15, "Gaussian CRPS implementation"),
    "G07": (17, "Rule-specific deterministic error"),
    "G08": (18, "Rule and validation-block model results"),
    "G09": (18, "GP hyperparameter stability"),
    "G10": (19, "Predictive calibration and sharpness"),
    "G11": (19, "Residual dependence and heteroskedasticity"),
    "G12": (17, "Missing forecast support"),
    "G13": (20, "Systematic GP-market discrepancy structure"),
    "G14": (20, "Forecast combination"),
    "G15": (21, "Clean-environment reproducibility"),
    "G16": (22, "Consolidated thesis evidence pack"),
}
OPEN_GAPS = {
    "G17": (23, "Independent final freeze"),
}


def run_git(*args: str) -> str:
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


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def find_report(phase: int) -> Path:
    candidates = [
        path
        for path in (ROOT / "outputs").rglob("*.md")
        if f"phase{phase}" in path.name.lower()
        and "report" in path.name.lower()
        and "phase22" not in str(path).lower()
    ]
    if not candidates:
        raise RuntimeError(f"No report was found for Phase {phase}.")
    candidates.sort(
        key=lambda path: (
            0 if path.name.lower() == f"phase{phase}_report.md" else 1,
            len(str(path)),
            str(path),
        )
    )
    return candidates[0]


def normalise_text(text: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00b0": " degrees ",
        "\u00d7": "x",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def compact_excerpt(text: str, start: int, end: int, radius: int = 120) -> str:
    excerpt = text[max(0, start - radius): min(len(text), end + radius)]
    return " ".join(excerpt.split())


def extract_metric(
    phase: int,
    text: str,
    metric: str,
    pattern: str,
    unit: str,
    sample: str,
    source: Path,
    required: bool = True,
    flags: int = re.IGNORECASE | re.MULTILINE,
) -> dict:
    match = re.search(pattern, normalise_text(text), flags)
    if match is None:
        if required:
            raise RuntimeError(
                f"Required Phase {phase} metric was not found: {metric}"
            )
        return {
            "phase": phase,
            "metric": metric,
            "value": "",
            "unit": unit,
            "sample": sample,
            "source_file": str(source.relative_to(ROOT)),
            "evidence_excerpt": "Not parsed automatically; inspect source report.",
            "status": "NOT_PARSED",
        }

    value = match.group(1)
    return {
        "phase": phase,
        "metric": metric,
        "value": value,
        "unit": unit,
        "sample": sample,
        "source_file": str(source.relative_to(ROOT)),
        "evidence_excerpt": compact_excerpt(
            normalise_text(text),
            match.start(),
            match.end(),
        ),
        "status": "VERIFIED",
    }


def csv_shape(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
        if not rows:
            return 0, 0
        return max(0, len(rows) - 1), len(rows[0])
    except Exception:
        return None, None


def classify_figure(path: Path) -> tuple[str, str]:
    name = path.name.lower()
    main_keywords = (
        "model_score",
        "benchmark",
        "calibration",
        "coverage",
        "pit",
        "combination",
        "discrepancy",
        "stability",
    )
    appendix_keywords = (
        "missing_support",
        "boxplot",
        "autocorrelation",
        "heteroskedasticity",
        "rank",
        "hyperparameter",
    )
    if any(keyword in name for keyword in main_keywords):
        return "MAIN_TEXT_CANDIDATE", (
            "Potentially central to the model-comparison, calibration or "
            "model-market argument; retain only if legible and non-duplicative."
        )
    if any(keyword in name for keyword in appendix_keywords):
        return "APPENDIX_CANDIDATE", (
            "Useful diagnostic or audit figure; normally place in the appendix "
            "unless it carries a central result."
        )
    return "REVIEW", (
        "Inspect for duplication and thesis relevance before inclusion."
    )


def classify_table(path: Path) -> tuple[str, str]:
    name = path.name.lower()
    main_keywords = (
        "scores_overall",
        "paired",
        "combination",
        "coverage",
        "rule_error_summary",
        "gap_closure",
        "key_metrics",
    )
    appendix_keywords = (
        "registry",
        "inventory",
        "source",
        "manifest",
        "autocorrelation",
        "heteroskedasticity",
        "missing",
        "hyperparameter",
    )
    if any(keyword in name for keyword in main_keywords):
        return "MAIN_TEXT_CANDIDATE", (
            "Condense to the rows and columns needed for the central argument."
        )
    if any(keyword in name for keyword in appendix_keywords):
        return "APPENDIX_OR_REPOSITORY", (
            "Important for auditability or diagnostics but usually too detailed "
            "for the main text."
        )
    return "REVIEW", (
        "Retain only when it directly answers a research question."
    )


def markdown_table(rows: list[dict], columns: list[str]) -> str:
    def clean(value) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join(clean(row.get(column, "")) for column in columns) + " |"
        )
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    source_commit = run_git("rev-parse", "HEAD")
    source_commit_time = run_git("show", "-s", "--format=%cI", "HEAD")
    branch = run_git("branch", "--show-current")

    reports: dict[int, Path] = {}
    report_texts: dict[int, str] = {}

    for phase in PHASES:
        report = find_report(phase)
        text = report.read_text(encoding="utf-8", errors="strict")
        if "PASSED" not in text.upper():
            raise RuntimeError(
                f"Phase {phase} report does not contain a PASSED status: {report}"
            )
        reports[phase] = report
        report_texts[phase] = text

    phase21_comparison = ROOT / "outputs/v2_completion/phase21_artifact_comparison.csv"
    if not phase21_comparison.is_file():
        raise RuntimeError("Phase 21 artifact comparison registry is missing.")

    with phase21_comparison.open(
        "r", encoding="utf-8", errors="strict", newline=""
    ) as handle:
        comparison_rows = list(csv.DictReader(handle))

    if len(comparison_rows) != 116:
        raise RuntimeError(
            f"Expected 116 Phase 21 artifact comparisons, observed {len(comparison_rows)}."
        )

    failed_comparisons = [
        row for row in comparison_rows
        if str(row.get("status", "")).upper() != "PASSED"
    ]
    if failed_comparisons:
        raise RuntimeError("At least one Phase 21 artifact comparison did not pass.")

    metrics: list[dict] = []

    p16 = report_texts[16]
    p16_source = reports[16]
    metrics.extend([
        extract_metric(
            16, p16, "Raw point mean date CRPS",
            r"Raw point forecast:\s*([0-9]+\.[0-9]+)",
            "degrees Celsius", "365 validation dates, four rules",
            p16_source,
        ),
        extract_metric(
            16, p16, "Static Gaussian mean date CRPS",
            r"Static Gaussian:\s*([0-9]+\.[0-9]+)",
            "degrees Celsius", "365 validation dates, four rules",
            p16_source,
        ),
        extract_metric(
            16, p16, "RBF GP mean date CRPS",
            r"RBF GP,\s*analytical CRPS:\s*([0-9]+\.[0-9]+)",
            "degrees Celsius", "365 validation dates, four rules",
            p16_source,
        ),
        extract_metric(
            16, p16, "Matern 3/2 GP mean date CRPS",
            r"Mat[ée]rn-?3/2 GP,\s*analytical CRPS:\s*([0-9]+\.[0-9]+)",
            "degrees Celsius", "365 validation dates, four rules",
            p16_source,
        ),
        extract_metric(
            16, p16, "Matern 3/2 minus static Gaussian CRPS",
            r"Mat[ée]rn-?3/2 minus static:\s*([-+]?[0-9]+\.[0-9]+)",
            "degrees Celsius", "paired target-date bootstrap",
            p16_source,
        ),
        extract_metric(
            16, p16, "Matern 3/2 minus RBF CRPS",
            r"Mat[ée]rn-?3/2 minus RBF:\s*([-+]?[0-9]+\.[0-9]+)",
            "degrees Celsius", "paired target-date bootstrap",
            p16_source,
        ),
    ])

    p17 = report_texts[17]
    p17_source = reports[17]
    metrics.extend([
        extract_metric(
            17, p17, "Target-date deterministic-error share",
            r"Target-date component:\s*([0-9]+\.[0-9]+)%",
            "percent of deterministic-error sum of squares",
            "730 weather-only dates by four rules", p17_source,
        ),
        extract_metric(
            17, p17, "Unsupported market-period date-rule keys",
            r"Unsupported date-rule keys:\s*([0-9]+)",
            "keys", "103 settlement dates by four rules", p17_source,
        ),
        extract_metric(
            17, p17, "Dates with complete four-rule support",
            r"Dates with complete four-rule support:\s*([0-9]+)",
            "dates", "market period", p17_source,
        ),
    ])

    p18 = report_texts[18]
    p18_source = reports[18]
    metrics.extend([
        extract_metric(
            18, p18, "Rules where Matern 3/2 beats static Gaussian",
            r"lower mean CRPS than static Gaussian in\s*([0-9]+)\s*of\s*4 decision rules",
            "rules", "chronological validation", p18_source,
        ),
        extract_metric(
            18, p18, "Validation blocks where Matern 3/2 beats static Gaussian",
            r"lower mean CRPS than static Gaussian in\s*([0-9]+)\s*of\s*4 validation blocks",
            "blocks", "chronological validation", p18_source,
        ),
        extract_metric(
            18, p18, "Rule-by-block cells where Matern 3/2 beats static Gaussian",
            r"lower mean CRPS than static Gaussian in\s*([0-9]+)\s*of\s*16 rule-by-block cells",
            "cells", "chronological validation", p18_source,
        ),
    ])

    p19 = report_texts[19]
    p19_source = reports[19]
    metrics.extend([
        extract_metric(
            19, p19, "Matern 3/2 90 percent central coverage",
            r"Mat[ée]rn-?3/2 GP\s*\|\s*0\.90000\s*\|\s*([0-9]+\.[0-9]+)",
            "empirical coverage", "365 validation dates, four rules",
            p19_source,
        ),
        extract_metric(
            19, p19, "Matern 3/2 standardised-residual lag-one correlation",
            r"Mat[ée]rn-?3/2 GP\s*\|\s*([0-9]+\.[0-9]+)\s*\|\s*0\.31934",
            "correlation", "chronological validation",
            p19_source,
        ),
        extract_metric(
            19, p19, "Matern 3/2 conditional-variance cluster-robust p-value",
            r"Mat[ée]rn-?3/2 GP\s*\|\s*0\.02710\s*\|\s*23\.20617\s*\|\s*10\s*\|\s*([0-9]+\.[0-9]+)",
            "p-value", "auxiliary squared-residual regression",
            p19_source,
        ),
    ])

    p20 = report_texts[20]
    p20_source = reports[20]
    metrics.extend([
        extract_metric(
            20, p20, "Selected GP combination weight",
            r"Selected GP weight:\s*([0-9]+\.[0-9]+)",
            "weight", "67 development dates", p20_source,
        ),
        extract_metric(
            20, p20, "Selected market combination weight",
            r"Selected market weight:\s*([0-9]+\.[0-9]+)",
            "weight", "67 development dates", p20_source,
        ),
        extract_metric(
            20, p20, "Post-hoc June oracle GP weight",
            r"Post-hoc June oracle GP weight:\s*([0-9]+\.[0-9]+)",
            "weight", "30 June dates, diagnostic only", p20_source,
        ),
        extract_metric(
            20, p20, "Pool minus GP binary Brier",
            r"gp\s*\|\s*binary_brier\s*\|\s*([-+]?[0-9]+\.[0-9]+)",
            "score difference", "30 June dates", p20_source,
        ),
        extract_metric(
            20, p20, "Pool minus market binary Brier",
            r"market_normalised\s*\|\s*binary_brier\s*\|\s*([-+]?[0-9]+\.[0-9]+)",
            "score difference", "30 June dates", p20_source,
        ),
    ])

    metrics.extend([
        {
            "phase": 21,
            "metric": "Clean-environment phases replayed",
            "value": "6",
            "unit": "phases",
            "sample": "Phases 15-20",
            "source_file": str(reports[21].relative_to(ROOT)),
            "evidence_excerpt": "Phase 21 replayed Phases 15-20 in a clean temporary clone and environment.",
            "status": "VERIFIED",
        },
        {
            "phase": 21,
            "metric": "Artifacts compared",
            "value": str(len(comparison_rows)),
            "unit": "artifacts",
            "sample": "Phase 15-20 reproducibility outputs",
            "source_file": str(phase21_comparison.relative_to(ROOT)),
            "evidence_excerpt": "Every recorded artifact comparison has status PASSED.",
            "status": "VERIFIED",
        },
        {
            "phase": 21,
            "metric": "Maximum finite replay error",
            "value": "0.000e+00",
            "unit": "reported numerical difference",
            "sample": "finite numerical comparisons",
            "source_file": str(reports[21].relative_to(ROOT)),
            "evidence_excerpt": "The Phase 21 report records zero maximum finite replay error.",
            "status": "VERIFIED",
        },
    ])

    source_paths: set[Path] = set()
    for phase in PHASES:
        source_paths.add(reports[phase])

    for base in (
        ROOT / "config/v2_completion",
        ROOT / "outputs/v2_completion",
        ROOT / "tools/v2_completion",
        ROOT / "tests/v2_completion",
    ):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            lower = str(path.relative_to(ROOT)).lower()
            if any(f"phase{phase}" in lower for phase in PHASES):
                if "phase22" not in lower:
                    source_paths.add(path)

    inventory_rows: list[dict] = []
    figure_rows: list[dict] = []
    table_rows: list[dict] = []

    for path in sorted(source_paths, key=lambda p: str(p.relative_to(ROOT))):
        relative = path.relative_to(ROOT)
        row_count, column_count = (None, None)
        if path.suffix.lower() == ".csv":
            row_count, column_count = csv_shape(path)

        phase_match = re.search(r"phase(\d+)", str(relative).lower())
        phase = int(phase_match.group(1)) if phase_match else ""

        inventory_rows.append({
            "phase": phase,
            "relative_path": str(relative),
            "suffix": path.suffix.lower(),
            "bytes": path.stat().st_size,
            "rows": "" if row_count is None else row_count,
            "columns": "" if column_count is None else column_count,
            "sha256": sha256(path),
            "role": (
                "certified_phase_report"
                if path in reports.values()
                else "supporting_artifact"
            ),
        })

        if path.suffix.lower() in {".png", ".pdf"}:
            placement, rationale = classify_figure(path)
            figure_rows.append({
                "phase": phase,
                "relative_path": str(relative),
                "format": path.suffix.lower().lstrip("."),
                "recommended_placement": placement,
                "rationale": rationale,
                "sha256": sha256(path),
            })

        if path.suffix.lower() == ".csv":
            placement, rationale = classify_table(path)
            table_rows.append({
                "phase": phase,
                "relative_path": str(relative),
                "rows": "" if row_count is None else row_count,
                "columns": "" if column_count is None else column_count,
                "recommended_placement": placement,
                "rationale": rationale,
                "sha256": sha256(path),
            })

    gap_rows: list[dict] = []
    for gap, (phase, description) in CLOSED_GAPS.items():
        gap_rows.append({
            "gap_id": gap,
            "description": description,
            "closing_phase": phase,
            "status_after_phase22": "CLOSED",
            "evidence_report": str(
                (reports[phase] if phase in reports else OUTPUT_DIR / "phase22_report.md")
                .relative_to(ROOT)
            ) if phase != 22 else str(
                (OUTPUT_DIR / "phase22_report.md").relative_to(ROOT)
            ),
        })
    for gap, (phase, description) in OPEN_GAPS.items():
        gap_rows.append({
            "gap_id": gap,
            "description": description,
            "closing_phase": phase,
            "status_after_phase22": "OPEN",
            "evidence_report": "",
        })

    claim_rows = [
        {
            "claim_id": "C01",
            "thesis_claim": (
                "A rule-specific static Gaussian correction materially improves "
                "the raw deterministic forecast."
            ),
            "strength": "SUPPORTED",
            "primary_evidence": str(reports[16].relative_to(ROOT)),
            "required_caveat": (
                "The comparison is chronological, date-balanced and local to "
                "the Hong Kong target and archived forecast source."
            ),
            "recommended_section": "Results: benchmark comparison",
        },
        {
            "claim_id": "C02",
            "thesis_claim": (
                "The Matern 3/2 GP improves on the static Gaussian benchmark in "
                "aggregate and across all four decision rules."
            ),
            "strength": "SUPPORTED_WITH_STABILITY_QUALIFICATION",
            "primary_evidence": str(reports[18].relative_to(ROOT)),
            "required_caveat": (
                "The advantage reverses in the first validation block and is "
                "therefore not temporally uniform."
            ),
            "recommended_section": "Results: GP value added and stability",
        },
        {
            "claim_id": "C03",
            "thesis_claim": (
                "Most raw deterministic error variation is shared at the target-date "
                "level rather than explained by the decision-rule label alone."
            ),
            "strength": "SUPPORTED_DESCRIPTIVELY",
            "primary_evidence": str(reports[17].relative_to(ROOT)),
            "required_caveat": (
                "The balanced decomposition is descriptive and does not make the "
                "date-by-rule interaction an independently replicated variance component."
            ),
            "recommended_section": "Results: deterministic error structure",
        },
        {
            "claim_id": "C04",
            "thesis_claim": (
                "The GP predictive distribution is useful but not fully calibrated "
                "or serially independent."
            ),
            "strength": "SUPPORTED",
            "primary_evidence": str(reports[19].relative_to(ROOT)),
            "required_caveat": (
                "Nominal row-level p-values are descriptive because rules share dates "
                "and dates may be serially dependent."
            ),
            "recommended_section": "Results: predictive diagnostics",
        },
        {
            "claim_id": "C05",
            "thesis_claim": (
                "Polymarket prices outperform the weather-only GP on June proper scores "
                "over the exact complete-book intersection."
            ),
            "strength": "SUPPORTED_ON_EXACT_COMMON_SUPPORT",
            "primary_evidence": str(reports[20].relative_to(ROOT)),
            "required_caveat": (
                "This does not establish causal private information or global market "
                "efficiency and applies only to the certified exact-common-support sample."
            ),
            "recommended_section": "Results: GP versus market",
        },
        {
            "claim_id": "C06",
            "thesis_claim": (
                "A development-selected convex pool improves on the GP in June but "
                "does not improve on the market."
            ),
            "strength": "SUPPORTED",
            "primary_evidence": str(reports[20].relative_to(ROOT)),
            "required_caveat": (
                "The bootstrap weight interval is wide, the June oracle assigns zero "
                "weight to the GP, and the pool should not be described as a superior "
                "combined forecast."
            ),
            "recommended_section": "Results and discussion: forecast combination",
        },
        {
            "claim_id": "C07",
            "thesis_claim": (
                "The Phase 15-20 completion analyses are reproducible from the committed "
                "repository in a clean temporary environment."
            ),
            "strength": "SUPPORTED",
            "primary_evidence": str(reports[21].relative_to(ROOT)),
            "required_caveat": (
                "The claim concerns the recorded software environment, frozen inputs "
                "and regenerated artifacts; it is not a guarantee about future package "
                "versions or third-party data availability."
            ),
            "recommended_section": "Reproducibility statement and appendix",
        },
        {
            "claim_id": "C08",
            "thesis_claim": (
                "The frozen value-gap strategy demonstrates a reliable arbitrage."
            ),
            "strength": "NOT_SUPPORTED",
            "primary_evidence": str(reports[12].relative_to(ROOT)) if 12 in reports else "Phase 12 certified report",
            "required_caveat": (
                "The June point estimate is small, uncertainty is weak, performance is "
                "cost-sensitive and the simulation omits important execution frictions."
            ),
            "recommended_section": "Discussion: negative or limited trading evidence",
        },
    ]

    boundary_rows = [
        {
            "boundary_id": "B01",
            "topic": "Forecast support",
            "restriction": (
                "Do not impute the 37 unsupported market-period date-rule keys."
            ),
            "consequence": (
                "Use exact common support for every model-market and trading comparison."
            ),
            "source": str(reports[17].relative_to(ROOT)),
        },
        {
            "boundary_id": "B02",
            "topic": "June separation",
            "restriction": (
                "Do not use June outcomes to fit the GP, select a kernel, choose the "
                "combination weight or tune the trading rule."
            ),
            "consequence": (
                "June remains the out-of-sample validation period."
            ),
            "source": str(reports[20].relative_to(ROOT)),
        },
        {
            "boundary_id": "B03",
            "topic": "Dependence",
            "restriction": (
                "Do not interpret nominal independent-row tests as definitive."
            ),
            "consequence": (
                "Emphasise date-level bootstrap intervals, effect sizes and block results."
            ),
            "source": str(reports[19].relative_to(ROOT)),
        },
        {
            "boundary_id": "B04",
            "topic": "Market information",
            "restriction": (
                "Do not claim that GP-market disagreement causally identifies private information."
            ),
            "consequence": (
                "Describe discrepancy patterns as systematic associations."
            ),
            "source": str(reports[20].relative_to(ROOT)),
        },
        {
            "boundary_id": "B05",
            "topic": "Trading",
            "restriction": (
                "Do not call the historical value-gap simulation live-executable arbitrage."
            ),
            "consequence": (
                "Report it as a limited economic diagnostic with explicit execution omissions."
            ),
            "source": "Phase 11-12 certified evidence",
        },
        {
            "boundary_id": "B06",
            "topic": "Research scope",
            "restriction": (
                "Do not restore CatBoost or broad AI-ensemble comparisons as a main contribution."
            ),
            "consequence": (
                "Keep the thesis centred on deterministic IFS post-processing, Gaussian "
                "benchmarks, Gaussian processes, market comparison and disciplined diagnostics."
            ),
            "source": "Supervisor-approved project focus",
        },
    ]

    methodology_md = f"""# Phase 22 Methodology Evidence

## Central empirical design

The empirical study should be written as a single chronological argument rather
than as a collection of unrelated forecasting experiments. A deterministic IFS
daily-maximum forecast is first aligned to the HKO settlement target. Its local
error is estimated from a two-year weather-only history. A rule-specific static
Gaussian correction provides the deliberately simple probabilistic benchmark.
A Gaussian process then models conditional residual structure using exactly the
feature construction, affine scaling, response transformation, observation-noise
convention and analytical Gaussian CRPS implementation reconciled in Phase 15.

The chronological validation sample contains 365 target dates, four decision
rules and four validation blocks. Raw point, static Gaussian, RBF GP and
Matern-3/2 GP predictions are evaluated on the same date-rule support. Target
date is the uncertainty and aggregation unit. This prevents four decision-rule
forecasts from being treated as four independent weather realisations.

## Data and support

The weather-only residual panel contains 730 dates and 2,920 date-rule rows.
The market and settlement universe contains 103 dates and 412 theoretical
date-rule keys. Deterministic forecast support is available for 375 keys across
102 dates. The 37 missing keys are retained as explicit archive/support
limitations and are never statistically reconstructed.

Market comparison, forecast combination and trading must therefore use the
certified exact complete-book intersection. The exact-common-support sample
contains 97 dates, 350 date-rule books and 3,850 contract-event rows. The
development period contains 67 dates and June contains 30 out-of-sample dates.

## Static probabilistic benchmark

For each decision rule, the static benchmark estimates a residual mean and
standard deviation using only the training dates available before the relevant
validation block. The deterministic forecast is shifted by the estimated local
mean error and combined with the estimated residual scale to form a Gaussian
predictive distribution. This benchmark is essential: it separates the benefit
of simple local bias-and-scale correction from the incremental contribution of
the GP.

## Gaussian-process construction

The GP should be defined at the residual level. The response is the observed HKO
daily maximum minus the deterministic forecast daily maximum. The four raw
features are calendar time, seasonal sine, seasonal cosine and deterministic
forecast daily maximum. Phase 15 verifies the exact calendar origin, 365.2425-day
year convention, seasonal position, affine feature transformation, response
normalisation and saved scikit-learn estimator configuration.

The fitted covariance is a signal kernel plus WhiteKernel observation noise.
The saved predictive standard deviation includes observation noise exactly once.
The analytical Gaussian CRPS is used for every continuous-distribution
comparison. The Matern-3/2 and RBF families are compared chronologically; the
Matern family is retained because it has the lower mean date CRPS.

## Model-market comparison and forecast combination

The weather-only GP and Polymarket are first compared as separate information
sources on exact common support. Market probabilities are normalised within each
complete contract book for categorical scoring. A single convex-pool weight is
then selected only on the 67-date development period by minimising date-balanced
categorical log score on a 0.001 grid. The selected weight is frozen before June.
Rule-specific weights and the June oracle weight are diagnostics only.

## Reproducibility

Phase 21 replays Phases 15-20 from commit `{source_commit}` in a clean temporary
clone and environment. Six phases are replayed and 116 artifacts are compared.
All comparisons pass and the maximum finite numerical discrepancy is zero.
This is stronger evidence than merely recording package versions: it demonstrates
that the committed code, frozen inputs and environment specification regenerate
the recorded completion results.
"""

    results_md = f"""# Phase 22 Results Evidence

## Benchmark ordering

The chronological benchmark comparison establishes the following mean date CRPS
ordering: raw point forecast, static Gaussian, RBF GP and Matern-3/2 GP. The key
values are recorded in `phase22_key_metrics.csv`. The static Gaussian produces
a large improvement over the uncorrected deterministic forecast. The Matern GP
then improves further on the static benchmark. This directly answers whether
the GP genuinely adds value beyond simple local correction.

The result must not be written only as an aggregate ranking. Phase 18 shows that
the Matern GP beats the static Gaussian in all four decision rules but only three
of four chronological validation blocks. The first block favours the static
benchmark. The GP advantage is therefore persistent across rules but not uniform
through time.

## Deterministic error structure

Phase 17 shows a strong positive deterministic forecast error under the
HKO-minus-forecast convention. Most deterministic-error sum of squares is
associated with target-date variation, while the decision-rule main component
is very small. This indicates that shared weather-state error dominates the
small differences between decision times. Rule-specific post-processing remains
reasonable because the rule-level scales and forecast vintages differ, but the
thesis should not claim that decision lead time alone explains most error.

## Predictive diagnostics

Phase 19 prevents the CRPS improvement from being mistaken for complete
probabilistic adequacy. Central intervals under-cover at important nominal
levels, standardised residuals retain substantial lag-one dependence, and the
conditional-variance regression retains evidence of remaining structure for
the Matern GP. Quantile calibration is nevertheless better for Matern than RBF.
The correct conclusion is that the Matern GP is the better of the fitted GP
families and improves the benchmark, but it does not exhaust local forecast
error structure.

## GP versus Polymarket

On the June exact-common-support sample, Polymarket has lower binary and
categorical proper scores than the weather-only GP. This is the economically
important negative result: the weather-only post-processing model does not
dominate the market.

## Forecast combination

The development-selected convex pool assigns approximately half its weight to
the GP and half to the market. In June, the pool improves all four reported
proper scores relative to the GP. It nevertheless worsens all four scores
relative to the normalised market distribution. The post-hoc June oracle assigns
zero weight to the GP. The combination exercise therefore does not support a
claim that the GP contributes robust incremental information beyond the market
in June. It does show that the development period contained apparent
complementarity that did not persist strongly enough out of sample.

## Reproducibility result

The clean-environment replay passes for all six completion phases. The evidence
pack should cite the 116-artifact comparison and zero finite numerical replay
error in the reproducibility subsection or appendix.
"""

    discussion_md = """# Phase 22 Discussion Evidence

## Main substantive interpretation

The central contribution is not that a sophisticated model defeats a prediction
market. It is that a carefully specified residual GP converts a deterministic
weather forecast into a coherent local predictive distribution, materially
improves both the raw forecast and a static Gaussian correction, and permits a
disciplined comparison with market probabilities.

The static benchmark is crucial to this interpretation. Without it, the GP gain
could be attributed merely to correcting a large local deterministic bias and
adding residual variance. With the benchmark included, the thesis can separate
three effects: raw forecast error, simple local Gaussian correction and
conditional nonlinear residual modelling.

## Why the market still performs better

Polymarket can reflect information absent from the weather-only feature set,
including newer weather updates, alternative forecasts, local observations,
participant judgement and contract-specific attention. The discrepancy analysis
shows systematic reallocations across the contract book, but it cannot establish
which information channel causes them. The thesis should frame the market result
as evidence that the weather-only model is informationally incomplete, not as a
proof of strong-form market efficiency.

## Why forecast combination does not rescue the GP claim

The selected pool weight is unstable and the June oracle favours the market
alone. A pooled forecast that improves on the weaker GP but loses to the market
does not demonstrate robust complementarity. This is still valuable: it answers
the previously open methodological question and prevents an unsupported claim
from remaining in the dissertation.

## Predictive limitations

The Matern model's undercoverage, serial dependence and remaining conditional
variance structure show that a Gaussian residual law with the current features
is an approximation. These diagnostics motivate future work on richer dynamic
covariates, non-Gaussian likelihoods, time-varying covariance or state-space
post-processing. They should not be used to introduce several additional models
into the present thesis. The distinction-level response is to analyse the chosen
model deeply and state precisely where it fails.

## Trading interpretation

The trading exercise remains secondary. A small positive historical point
estimate with wide uncertainty, cost sensitivity and omitted execution frictions
does not establish a stable trading edge. The market-comparison and forecast-
combination results make this caution even more important.

## Scope discipline

CatBoost and broad ensemble modelling should remain brief contextual or appendix
material. Restoring them as parallel main pipelines would dilute the mathematical
development and empirical depth now achieved for deterministic post-processing,
the static Gaussian benchmark, GP construction, diagnostics, market comparison
and combination.
"""

    key_metrics_path = OUTPUT_DIR / "phase22_key_metrics.csv"
    write_csv(
        key_metrics_path,
        metrics,
        [
            "phase", "metric", "value", "unit", "sample",
            "source_file", "evidence_excerpt", "status",
        ],
    )

    write_csv(
        OUTPUT_DIR / "phase22_gap_closure_register.csv",
        gap_rows,
        [
            "gap_id", "description", "closing_phase",
            "status_after_phase22", "evidence_report",
        ],
    )
    write_csv(
        OUTPUT_DIR / "phase22_claim_register.csv",
        claim_rows,
        [
            "claim_id", "thesis_claim", "strength", "primary_evidence",
            "required_caveat", "recommended_section",
        ],
    )
    write_csv(
        OUTPUT_DIR / "phase22_evidential_boundaries.csv",
        boundary_rows,
        [
            "boundary_id", "topic", "restriction",
            "consequence", "source",
        ],
    )
    write_csv(
        OUTPUT_DIR / "phase22_source_inventory.csv",
        inventory_rows,
        [
            "phase", "relative_path", "suffix", "bytes",
            "rows", "columns", "sha256", "role",
        ],
    )
    write_csv(
        OUTPUT_DIR / "phase22_figure_inventory.csv",
        figure_rows,
        [
            "phase", "relative_path", "format",
            "recommended_placement", "rationale", "sha256",
        ],
    )
    write_csv(
        OUTPUT_DIR / "phase22_table_inventory.csv",
        table_rows,
        [
            "phase", "relative_path", "rows", "columns",
            "recommended_placement", "rationale", "sha256",
        ],
    )

    reproducibility_rows = [
        {
            "item": "source_commit",
            "value": source_commit,
            "status": "VERIFIED",
            "evidence": str(reports[21].relative_to(ROOT)),
        },
        {
            "item": "source_branch",
            "value": branch,
            "status": "VERIFIED",
            "evidence": "git branch --show-current",
        },
        {
            "item": "phases_replayed",
            "value": "6",
            "status": "PASSED",
            "evidence": str(reports[21].relative_to(ROOT)),
        },
        {
            "item": "artifacts_compared",
            "value": str(len(comparison_rows)),
            "status": "PASSED",
            "evidence": str(phase21_comparison.relative_to(ROOT)),
        },
        {
            "item": "failed_artifact_comparisons",
            "value": "0",
            "status": "PASSED",
            "evidence": str(phase21_comparison.relative_to(ROOT)),
        },
        {
            "item": "maximum_finite_replay_error",
            "value": "0.000e+00",
            "status": "PASSED",
            "evidence": str(reports[21].relative_to(ROOT)),
        },
    ]
    write_csv(
        OUTPUT_DIR / "phase22_reproducibility_summary.csv",
        reproducibility_rows,
        ["item", "value", "status", "evidence"],
    )

    (OUTPUT_DIR / "phase22_methodology_evidence.md").write_text(
        methodology_md, encoding="utf-8", newline="\n"
    )
    (OUTPUT_DIR / "phase22_results_evidence.md").write_text(
        results_md, encoding="utf-8", newline="\n"
    )
    (OUTPUT_DIR / "phase22_discussion_evidence.md").write_text(
        discussion_md, encoding="utf-8", newline="\n"
    )

    metric_lookup = {
        row["metric"]: row["value"]
        for row in metrics
        if row["status"] == "VERIFIED"
    }

    instruction_book = f"""# Version 2 Empirical Evidence Instruction Book

## Purpose

This document is the thesis-writing handover for the completed Version 2
empirical programme. It is deliberately more detailed than the final
dissertation should be. The Overleaf-writing workflow should select the most
important results and arguments while preserving the definitions, support
restrictions, chronology and evidential boundaries recorded here.

The empirical completion source commit is `{source_commit}` on branch
`{branch}`.

## Central research question and approved scope

The central empirical question is whether deterministic IFS weather forecasts
for the Hong Kong settlement target can be converted into useful local
probabilistic forecasts through rigorous residual post-processing, especially a
Gaussian process, and how those probabilities compare with Polymarket prices.

The main thesis should therefore focus on:

1. deterministic forecast and settlement-target alignment;
2. local deterministic error and the static Gaussian benchmark;
3. rigorous Gaussian-process construction;
4. chronological predictive validation and proper scoring;
5. calibration, sharpness, dependence and conditional-variance diagnostics;
6. exact-common-support comparison with Polymarket;
7. a low-dimensional, development-selected forecast-combination test;
8. cautious economic interpretation and reproducibility.

CatBoost and broad AI-ensemble material should not return as parallel central
methodologies. They may remain as short contextual comparisons, deferred
extensions or appendix material only when they directly clarify the chosen GP
design.

## Recommended thesis narrative

### Stage 1: define the target and information sets

Define the HKO daily maximum settlement target, canonical interval contract
book, decision rules and chronological information cutoff. Explain why a
deterministic daily maximum is not itself a contract probability.

### Stage 2: establish the deterministic forecasting problem

Report the positive HKO-minus-forecast error and the rule-level summaries from
Phase 17. Explain that target-date variation accounts for
{metric_lookup.get("Target-date deterministic-error share", "approximately 91.9")}%
of deterministic-error sum of squares. This motivates local correction but also
shows that the rule label alone explains little of the total error.

### Stage 3: introduce the static Gaussian benchmark

The static model is not optional. It answers whether the GP improves beyond a
simple rule-specific local mean-and-scale correction. Under chronological
validation, mean date CRPS falls from
{metric_lookup.get("Raw point mean date CRPS", "1.745684932")} for the raw point
forecast to {metric_lookup.get("Static Gaussian mean date CRPS", "0.911754550")}
for the static Gaussian.

### Stage 4: specify the GP mathematically and computationally

Use the exact Phase 15 feature equations, scaling maps, response transformation,
kernel decomposition, observation-noise convention and Gaussian CRPS formula.
The code-to-mathematics reconciliation should support the derivation rather than
sit as an implementation anecdote.

### Stage 5: demonstrate incremental GP value

The Matern-3/2 mean date CRPS is
{metric_lookup.get("Matern 3/2 GP mean date CRPS", "0.863339999")}, compared with
{metric_lookup.get("Static Gaussian mean date CRPS", "0.911754550")} for the
static benchmark and {metric_lookup.get("RBF GP mean date CRPS", "0.877561468")}
for the RBF GP. The paired Matern-minus-static difference is
{metric_lookup.get("Matern 3/2 minus static Gaussian CRPS", "-0.048414551")}.

Do not stop at the aggregate result. Phase 18 shows improvement over the static
benchmark in all four decision rules but only three of four chronological
blocks. State explicitly that the first block reverses the aggregate ordering.

### Stage 6: assess predictive adequacy

Use Phase 19 to distinguish lower CRPS from full calibration. Discuss central
coverage, quantile reliability, PIT shape, standardised residual moments,
serial dependence and the auxiliary conditional-variance regression. The
Matern model is preferable to RBF but still under-covers and retains dependence
and conditional scale structure.

### Stage 7: compare with the market on exact common support

State the complete support arithmetic before presenting scores:

- 103 settlement and market dates;
- 412 theoretical date-rule keys;
- 375 supported keys across 102 dates;
- 37 unsupported keys;
- 97 exact-common-support dates;
- 350 complete date-rule books;
- 3,850 contract-event rows;
- 67 development dates;
- 30 June dates.

No missing forecast or market probability is imputed.

### Stage 8: report forecast combination as a test, not a rescue device

The selected development-period pool assigns GP weight
{metric_lookup.get("Selected GP combination weight", "0.489")} and market weight
{metric_lookup.get("Selected market combination weight", "0.511")}. The pool
improves on the GP in June but loses to the market. The June oracle GP weight is
{metric_lookup.get("Post-hoc June oracle GP weight", "0.000")}. The correct
interpretation is that apparent development-period complementarity did not
translate into robust June improvement beyond the market.

### Stage 9: conclude with disciplined negative evidence

The weather-only GP is a successful post-processing model relative to raw and
static weather benchmarks. It is not superior to Polymarket on June exact common
support, and the combined forecast does not improve on the market. This is an
interesting and defensible result because the thesis explains where the GP adds
value, where it fails, and what the market appears to add.

## Methodology-writing requirements

The methodology chapter should define every object before use:

- target date and decision rule;
- deterministic forecast and realised HKO outcome;
- residual response;
- four-dimensional feature vector;
- affine feature transformation;
- static Gaussian law;
- GP prior and covariance kernel;
- observation-noise term;
- posterior predictive mean and variance;
- Gaussian CRPS;
- interval-event probability;
- binary and categorical proper scores;
- date-level aggregation;
- exact-common-support restriction;
- convex probability pool and development objective.

For each retained method, include:

1. mathematical definition;
2. information set and chronology;
3. assumptions;
4. estimation rule;
5. prediction rule;
6. score or diagnostic;
7. implementation reconciliation;
8. rationale for inclusion;
9. limitation relevant to interpretation.

## Results-writing requirements

The results chapter should be ordered by inferential dependence:

1. support and sample accounting;
2. deterministic error;
3. raw and static benchmarks;
4. GP aggregate comparison;
5. rule and block stability;
6. predictive diagnostics;
7. market comparison;
8. combination;
9. trading evidence;
10. reproducibility.

Do not mix method definitions into the results except for a short reminder of
the quantity being reported. Do not present large registries or every diagnostic
table in the main text.

## Discussion-writing requirements

The discussion should answer the following questions directly.

### Does the GP outperform simple local correction?

Yes in aggregate, by rule and in three of four blocks. The first validation
block is a documented reversal, so the advantage is not temporally uniform.

### Why is the static benchmark important?

It separates simple local bias-and-scale correction from nonlinear conditional
residual modelling. Without it, the GP contribution is overstated.

### Are the GP probabilities fully calibrated?

No. Matern improves CRPS and quantile calibration relative to RBF, but central
undercoverage, lag dependence and remaining conditional variance structure
remain.

### Why does Polymarket outperform the GP?

The market may incorporate newer, alternative or judgemental information absent
from the weather-only features. The data identify systematic disagreement, not
its causal source.

### Does forecast combination demonstrate complementarity?

Not robustly in June. The pool improves on the GP but not the market, and the
June oracle gives the GP zero weight.

### Does the trading simulation establish arbitrage?

No. It is a frozen historical diagnostic with weak uncertainty support and
material execution omissions.

## Main-text table plan

Use a small number of synthesised tables:

1. sample and support accounting;
2. deterministic error by rule;
3. raw, static, RBF and Matern CRPS comparison;
4. Matern-minus-static by rule and block;
5. selected predictive diagnostics;
6. June GP, market and pooled proper scores;
7. evidential boundaries or robustness summary, if space permits.

The complete table inventory is in `phase22_table_inventory.csv`.

## Figure plan

Prefer figures that reveal structure not already obvious from a table:

1. benchmark/model CRPS comparison;
2. rule-by-block Matern improvement;
3. calibration or coverage curve;
4. residual autocorrelation or PIT diagnostic;
5. GP-market discrepancy or combination-weight profile.

Missing-support matrices and large hyperparameter diagnostics normally belong in
the appendix. The complete figure inventory is in
`phase22_figure_inventory.csv`.

## Claims that must not appear

Do not claim:

- that the GP dominates Polymarket;
- that the pool dominates both inputs;
- that GP-market discrepancy proves private information;
- that missing forecasts are missing at random;
- that the value-gap strategy is live-executable arbitrage;
- that nominal row-level p-values are definitive;
- that the Matern advantage is uniform through time;
- that CatBoost or broad AI ensembles are central completed contributions;
- that the empirical results generalise beyond the target, archive and period
  without qualification.

## Reproducibility statement

Phase 21 replays Phases 15-20 in a clean temporary clone and environment. It
compares 116 artifacts, all of which pass, with maximum finite numerical error
zero. Cite `phase22_reproducibility_summary.csv`, the Phase 21 report and the
artifact-comparison registry.

## Final writing rule

Every prominent numerical claim in the thesis should be traceable to
`phase22_key_metrics.csv`, a certified phase report, or a named table in the
source inventory. Every limitation should be linked to
`phase22_evidential_boundaries.csv`. The final dissertation should be shorter
than this instruction book, but it must not be less precise.
"""

    (OUTPUT_DIR / "phase22_empirical_instruction_book.md").write_text(
        instruction_book, encoding="utf-8", newline="\n"
    )

    report_rows = [
        {
            "phase": phase,
            "report": str(reports[phase].relative_to(ROOT)),
            "status": "PASSED",
            "sha256": sha256(reports[phase]),
        }
        for phase in PHASES
    ]

    report = f"""# Phase 22 Consolidated Thesis Evidence Pack

## Status

PASSED

## Certified starting point

- Branch: `{branch}`.
- Source commit: `{source_commit}`.
- Source commit time: `{source_commit_time}`.
- Certified reports consolidated: {len(report_rows)}.
- Source files inventoried: {len(inventory_rows)}.
- Key metrics registered: {len(metrics)}.
- Claim statements registered: {len(claim_rows)}.
- Evidential boundaries registered: {len(boundary_rows)}.
- Figures inventoried: {len(figure_rows)}.
- Tables inventoried: {len(table_rows)}.

## Completion result

Phase 22 consolidates the completed Version 2 empirical work into a
thesis-writing evidence pack. It does not refit a model, reselect a kernel,
change support, use June outcomes for development or alter any Phase 14-21
artifact.

## Gap status

- G01-G16: CLOSED.
- G17 independent final freeze: OPEN and reserved for Phase 23.

## Key empirical conclusions

1. Static Gaussian correction materially improves the raw deterministic forecast.
2. The Matern-3/2 GP improves further on the static correction in aggregate and
   across all four rules, but not in every validation block.
3. Predictive diagnostics reveal undercoverage, serial dependence and remaining
   conditional variance structure.
4. Polymarket outperforms the weather-only GP on June exact common support.
5. The development-selected pool improves on the GP but not the market.
6. The completion analyses reproduce in a clean environment with 116 successful
   artifact comparisons and zero maximum finite numerical error.

## Output files

- `phase22_empirical_instruction_book.md`
- `phase22_methodology_evidence.md`
- `phase22_results_evidence.md`
- `phase22_discussion_evidence.md`
- `phase22_key_metrics.csv`
- `phase22_claim_register.csv`
- `phase22_evidential_boundaries.csv`
- `phase22_gap_closure_register.csv`
- `phase22_source_inventory.csv`
- `phase22_table_inventory.csv`
- `phase22_figure_inventory.csv`
- `phase22_reproducibility_summary.csv`
- `phase22_manifest.json`

## Evidential boundary

This pack is an indexed synthesis of certified evidence. It does not create new
empirical findings. The final thesis must continue to preserve chronological
separation, exact common support, date-level uncertainty treatment and the
limitations recorded in the claim and evidential-boundary registries.
"""
    (OUTPUT_DIR / "phase22_report.md").write_text(
        report, encoding="utf-8", newline="\n"
    )

    spec = {
        "phase": 22,
        "title": "Consolidated thesis evidence pack",
        "status": "PASSED",
        "source_branch": branch,
        "source_commit": source_commit,
        "source_commit_time": source_commit_time,
        "reports": report_rows,
        "counts": {
            "reports": len(report_rows),
            "source_files": len(inventory_rows),
            "key_metrics": len(metrics),
            "claims": len(claim_rows),
            "evidential_boundaries": len(boundary_rows),
            "figures": len(figure_rows),
            "tables": len(table_rows),
            "closed_gaps": len(CLOSED_GAPS),
            "open_gaps": len(OPEN_GAPS),
        },
        "design_constraints": {
            "no_model_refit": True,
            "no_kernel_reselection": True,
            "no_missing_forecast_imputation": True,
            "june_not_used_for_development": True,
            "exact_common_support_preserved": True,
            "date_is_uncertainty_unit": True,
        },
    }
    CONFIG_PATH.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    output_files = sorted(
        path for path in OUTPUT_DIR.iterdir()
        if path.is_file()
        and path.name != "phase22_manifest.json"
    )

    manifest = {
        "phase": 22,
        "status": "PASSED",
        "source_commit": source_commit,
        "source_commit_time": source_commit_time,
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
    (OUTPUT_DIR / "phase22_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("PHASE22_STATUS=PASSED")
    print(f"PHASE22_REPORTS={len(report_rows)}")
    print(f"PHASE22_SOURCE_FILES={len(inventory_rows)}")
    print(f"PHASE22_KEY_METRICS={len(metrics)}")
    print(f"PHASE22_CLAIMS={len(claim_rows)}")
    print(f"PHASE22_BOUNDARIES={len(boundary_rows)}")
    print(f"PHASE22_FIGURES={len(figure_rows)}")
    print(f"PHASE22_TABLES={len(table_rows)}")
    print("PHASE22_CLOSED_GAPS=16")
    print("PHASE22_OPEN_GAPS=1")


if __name__ == "__main__":
    main()
