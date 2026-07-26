#!/usr/bin/env python3
"""Inspect archived notebooks and build the final migration register."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


ARCHIVE_BRANCH = "archive/17j-plus-18n-18y-20260726"
EXPECTED_NOTEBOOK_COUNT = 72


@dataclass(frozen=True)
class MigrationDecision:
    status: str
    canonical_notebook: str
    canonical_module: str
    action: str
    rationale: str


def run_git(*args: str, text: bool = True):
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def archive_paths() -> List[str]:
    output = run_git(
        "ls-tree",
        "-r",
        "--name-only",
        ARCHIVE_BRANCH,
    )

    return sorted(
        line.strip()
        for line in output.splitlines()
        if line.startswith("notebooks/")
        and line.endswith(".ipynb")
    )


def load_notebook(path: str) -> Dict:
    payload = run_git(
        "show",
        f"{ARCHIVE_BRANCH}:{path}",
        text=False,
    )

    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not parse archived notebook: {path}"
        ) from exc


def first_heading(notebook: Dict) -> str:
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue

        source = "".join(cell.get("source", []))

        for line in source.splitlines():
            cleaned = line.strip()

            if cleaned.startswith("#"):
                return cleaned.lstrip("#").strip()[:200]

    return ""


def extract_imports(notebook: Dict) -> List[str]:
    modules = set()

    import_pattern = re.compile(
        r"^\s*import\s+([A-Za-z_][A-Za-z0-9_\.]*)",
        re.MULTILINE,
    )

    from_pattern = re.compile(
        r"^\s*from\s+([A-Za-z_][A-Za-z0-9_\.]*)\s+import",
        re.MULTILINE,
    )

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue

        source = "".join(cell.get("source", []))

        for match in import_pattern.finditer(source):
            modules.add(match.group(1).split(".")[0])

        for match in from_pattern.finditer(source):
            modules.add(match.group(1).split(".")[0])

    return sorted(modules)


def notebook_profile(notebook: Dict) -> Dict[str, int]:
    cells = notebook.get("cells", [])

    code_cells = [
        cell for cell in cells
        if cell.get("cell_type") == "code"
    ]

    markdown_cells = [
        cell for cell in cells
        if cell.get("cell_type") == "markdown"
    ]

    cells_with_outputs = sum(
        bool(cell.get("outputs"))
        for cell in code_cells
    )

    executed_cells = sum(
        cell.get("execution_count") is not None
        for cell in code_cells
    )

    return {
        "total_cells": len(cells),
        "code_cells": len(code_cells),
        "markdown_cells": len(markdown_cells),
        "executed_code_cells": executed_cells,
        "cells_with_outputs": cells_with_outputs,
    }


def starts_with_stage(stem: str, stages: Sequence[str]) -> bool:
    return any(stem.startswith(stage) for stage in stages)


def decide(filename: str) -> MigrationDecision:
    stem = Path(filename).stem
    lower = stem.lower()

    # ------------------------------------------------------------------
    # Early abandoned or superseded research directions
    # ------------------------------------------------------------------

    early_prefix = re.match(r"^(\d{2})_", stem)

    if early_prefix and 1 <= int(early_prefix.group(1)) <= 15:
        return MigrationDecision(
            status="ARCHIVE_ONLY",
            canonical_notebook="None",
            canonical_module="None",
            action="Do not migrate",
            rationale=(
                "Early API exploration, threshold classification, "
                "single-market analysis, preliminary scoring or obsolete "
                "trading work."
            ),
        )

    if any(
        token in lower
        for token in (
            "earth2",
            "earth_2",
            "aifs_availability",
            "aifs_output_check",
        )
    ):
        return MigrationDecision(
            status="DEFERRED_REFERENCE",
            canonical_notebook="None",
            canonical_module="None",
            action="Retain on archive branch",
            rationale=(
                "External forecast feasibility work is not part of the "
                "current core empirical design."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 00: configuration, adapters, sample and design control
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "18sA_",
            "18sB_",
            "18uA_",
            "18uB_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="00",
            canonical_module="config.py / manifest.py",
            action=(
                "Extract source adapters, sample declarations, temporal "
                "fold rules and manifest logic."
            ),
            rationale=(
                "Defines the canonical sample, information chronology and "
                "model-support controls used throughout the clean pipeline."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 01: HKO settlement and event certification
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "17j_",
            "17k_",
            "17l_",
            "18a_",
            "18b_",
            "18c_",
            "18d_",
            "18e_",
            "18f_",
            "18h_",
            "18i_",
            "18j_",
            "18k_",
            "18n_",
            "18o_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="01",
            canonical_module="settlement.py / hko_source.py",
            action=(
                "Extract only the latest source retrieval, event parsing, "
                "one-decimal settlement and integrity checks."
            ),
            rationale=(
                "Supports the final certified HKO settlement target and "
                "eleven-event book."
            ),
        )

    # Baseline output notebooks are useful only for reconciliation.
    if starts_with_stage(stem, ("18g_", "18m_")):
        return MigrationDecision(
            status="REFERENCE_ONLY",
            canonical_notebook="09",
            canonical_module="reporting.py",
            action="Use only as a regression benchmark",
            rationale=(
                "Contains historical reporting outputs rather than the "
                "canonical source construction."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 02: weather training panel
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "18q_",
            "18tA_",
            "18tB_",
            "19a_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="02",
            canonical_module="availability.py / weather_panel.py",
            action=(
                "Extract forecast issue-time selection, HKT path checks, "
                "HKO outcome admissibility and residual construction."
            ),
            rationale=(
                "Builds the expanded forecast-HKO training panel, including "
                "dates without Polymarket contracts."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 03: market evaluation panel
    # ------------------------------------------------------------------

    if starts_with_stage(stem, ("18p_",)):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="03",
            canonical_module="market_panel.py",
            action=(
                "Extract final as-of price recovery, raw YES value, record "
                "age and complete-book checks."
            ),
            rationale=(
                "Constructs the market panel required for categorical "
                "evaluation and reduced-form trading."
            ),
        )

    if starts_with_stage(stem, ("18r_",)):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="03 and 07",
            canonical_module="market_panel.py / inference.py",
            action=(
                "Extract support-key construction into Notebook 03 and "
                "comparison logic into Notebook 07."
            ),
            rationale=(
                "Links the weather and market panels on exact common support."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 04: GP theory-to-code audit
    # ------------------------------------------------------------------

    if starts_with_stage(stem, ("18vB1_",)):
        return MigrationDecision(
            status="MIGRATE_AND_AUDIT",
            canonical_notebook="04 and 05",
            canonical_module="gaussian_process.py",
            action=(
                "Migrate GP implementation only after auditing scaling, "
                "kernel composition, noise, jitter and predictive variance."
            ),
            rationale=(
                "This is the principal historical source for the GPR code, "
                "but it cannot be accepted without direct matrix "
                "reconciliation."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 05: model fitting and chronological selection
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "18vA_",
            "18vB2_",
            "18vC_",
            "18vD_",
            "20a_",
            "20b_",
            "20c_",
            "20e_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="05",
            canonical_module=(
                "residual_models.py / catboost_quantiles.py / scoring.py"
            ),
            action=(
                "Extract final feature construction, temporal OOF fitting, "
                "common-support scoring and selection logic."
            ),
            rationale=(
                "Implements the five-family comparison under the final "
                "chronological CRPS design."
            ),
        )

    # Earlier ECMWF proxy correction work is retained only as provenance.
    if starts_with_stage(stem, ("19c_",)):
        return MigrationDecision(
            status="REFERENCE_ONLY",
            canonical_notebook="05",
            canonical_module="None",
            action="Use only for historical reconciliation",
            rationale=(
                "Earlier Gaussian proxy correction was superseded by the "
                "current residual-distribution hierarchy."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 06: quantiles and probability adjustment
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "18wA_",
            "18wB_",
            "18wC_",
            "20d_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="06",
            canonical_module="event_mapping.py / probability_adjustment.py",
            action=(
                "Extract the 99-quantile mapping, coherence checks, "
                "dispersion adjustment and probability regularisation."
            ),
            rationale=(
                "Creates the final coherent eleven-event probability books."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 07: external comparison and inference
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "18wD_",
            "19b_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="07",
            canonical_module="inference.py",
            action=(
                "Extract exact-common-book comparison logic. Replace the old "
                "period design with the final August external design and add "
                "paired date-level inference."
            ),
            rationale=(
                "Supports continuous external CRPS and weather-versus-market "
                "probability evaluation."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 08: final trading and PnL
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "18xA_",
            "18xB_",
            "18xC_",
            "18xD_",
            "21a_",
            "21b_",
            "21c_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="08",
            canonical_module="trading.py",
            action=(
                "Consolidate development selection, one-share simulation, "
                "cost sensitivity, record-age sensitivity and date bootstrap "
                "into one implementation."
            ),
            rationale=(
                "Replaces multiple historical trading notebooks with the "
                "single final thesis strategy."
            ),
        )

    # ------------------------------------------------------------------
    # Notebook 09: reporting and final reconciliation
    # ------------------------------------------------------------------

    if starts_with_stage(
        stem,
        (
            "18yA_",
            "18yB_",
            "21d_",
            "21e_",
        ),
    ):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="09",
            canonical_module="reporting.py",
            action=(
                "Extract table, figure, integrity and numerical reconciliation "
                "logic. Do not migrate old final numbers."
            ),
            rationale=(
                "Generates the final thesis outputs from the September "
                "empirical release."
            ),
        )

    # ------------------------------------------------------------------
    # Broad content-aware fallbacks for any historical naming variants
    # ------------------------------------------------------------------

    if any(token in lower for token in ("settlement", "resolution", "hko_contract")):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="01",
            canonical_module="settlement.py",
            action="Inspect and extract only non-duplicated certification logic",
            rationale="Filename indicates settlement or contract certification.",
        )

    if any(token in lower for token in ("forecast_ingestion", "open_meteo", "ecmwf_single")):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="02",
            canonical_module="weather_panel.py",
            action="Inspect and extract compatible forecast construction logic",
            rationale="Filename indicates deterministic weather ingestion.",
        )

    if any(token in lower for token in ("clob", "market_price_recovery")):
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="03",
            canonical_module="market_panel.py",
            action="Inspect and extract final market-record logic",
            rationale="Filename indicates historical market construction.",
        )

    if "trading" in lower or "pnl" in lower:
        return MigrationDecision(
            status="MIGRATE_LOGIC",
            canonical_notebook="08",
            canonical_module="trading.py",
            action="Consolidate only currently valid trading logic",
            rationale="Filename indicates trading or PnL analysis.",
        )

    if any(token in lower for token in ("thesis", "synthesis", "freeze", "release")):
        return MigrationDecision(
            status="REFERENCE_ONLY",
            canonical_notebook="09",
            canonical_module="reporting.py",
            action="Use for reconciliation, not as a numerical source",
            rationale="Filename indicates historical reporting or release output.",
        )

    return MigrationDecision(
        status="MANUAL_REVIEW",
        canonical_notebook="Unassigned",
        canonical_module="Unassigned",
        action="Inspect manually before migration",
        rationale="No safe automatic classification rule matched.",
    )


def flatten_text(notebook: Dict) -> str:
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
    )


def main() -> None:
    paths = archive_paths()

    if len(paths) != EXPECTED_NOTEBOOK_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_NOTEBOOK_COUNT} notebooks, found {len(paths)}."
        )

    rows = []

    for index, path in enumerate(paths, start=1):
        notebook = load_notebook(path)
        profile = notebook_profile(notebook)
        imports = extract_imports(notebook)
        decision = decide(Path(path).name)

        raw_size = len(
            run_git(
                "show",
                f"{ARCHIVE_BRANCH}:{path}",
                text=False,
            )
        )

        rows.append(
            {
                "inventory_index": index,
                "historical_path": path,
                "filename": Path(path).name,
                "size_bytes": raw_size,
                "first_heading": first_heading(notebook),
                **profile,
                "top_level_imports": "; ".join(imports),
                "status": decision.status,
                "canonical_notebook": decision.canonical_notebook,
                "canonical_module": decision.canonical_module,
                "migration_action": decision.action,
                "rationale": decision.rationale,
            }
        )

    docs = Path("docs")
    docs.mkdir(parents=True, exist_ok=True)

    csv_path = docs / "HISTORICAL_NOTEBOOK_INVENTORY.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)

    json_path = docs / "HISTORICAL_NOTEBOOK_INVENTORY.json"
    json_path.write_text(
        json.dumps(rows, indent=2) + "\n",
        encoding="utf-8",
    )

    status_counts = Counter(row["status"] for row in rows)
    destination_counts = Counter(
        row["canonical_notebook"] for row in rows
    )

    review_rows = [
        row for row in rows
        if row["status"] == "MANUAL_REVIEW"
    ]

    migration_lines = [
        "# Exact Historical Notebook Migration Map",
        "",
        f"Archive branch: `{ARCHIVE_BRANCH}`",
        "",
        f"Historical notebooks inspected: **{len(rows)}**",
        "",
        "## Decision summary",
        "",
    ]

    for status, count in sorted(status_counts.items()):
        migration_lines.append(f"- {status}: **{count}**")

    migration_lines.extend(
        [
            "",
            "## Canonical destination summary",
            "",
        ]
    )

    for destination, count in sorted(destination_counts.items()):
        migration_lines.append(
            f"- Notebook {destination}: **{count}** historical sources"
        )

    migration_lines.extend(
        [
            "",
            "## Notebook-level decisions",
            "",
            "| Historical notebook | Decision | Final destination | Action |",
            "|---|---|---|---|",
        ]
    )

    for row in rows:
        action = row["migration_action"].replace("|", "\\|")
        migration_lines.append(
            f"| `{row['filename']}` | "
            f"{row['status']} | "
            f"{row['canonical_notebook']} | "
            f"{action} |"
        )

    migration_lines.extend(
        [
            "",
            "## Migration rules",
            "",
            "1. Historical notebooks are never copied wholesale.",
            "2. Reusable logic moves into `src/weather_polymarket/`.",
            "3. Canonical notebooks call reusable modules.",
            "4. Historical output cells and old headline values are not migrated.",
            "5. Current source provenance and integrity checks are retained.",
            "6. Duplicate notebook generations are consolidated.",
            "7. GP code enters the clean pipeline only after Notebook 04 audit.",
            "8. August results must not influence development choices.",
            "",
        ]
    )

    if review_rows:
        migration_lines.extend(
            [
                "## Manual review still required",
                "",
            ]
        )

        for row in review_rows:
            migration_lines.append(
                f"- `{row['historical_path']}`"
            )
    else:
        migration_lines.extend(
            [
                "## Classification completion",
                "",
                "All 72 notebooks received an explicit migration decision.",
                "",
            ]
        )

    migration_path = docs / "HISTORICAL_NOTEBOOK_MIGRATION_MAP.md"
    migration_path.write_text(
        "\n".join(migration_lines) + "\n",
        encoding="utf-8",
    )

    sources_by_destination = defaultdict(list)

    for row in rows:
        destination = row["canonical_notebook"]

        if destination not in {"None", "Unassigned"}:
            for part in destination.split(" and "):
                sources_by_destination[part].append(row["filename"])

    specifications = {
        "00": (
            "Project configuration and manifest",
            "Declared dates, source registry, model registry, seeds, "
            "environment, temporal folds and run manifest.",
            "Configuration and manifest files; no empirical result.",
        ),
        "01": (
            "HKO settlement and event certification",
            "Official HKO outcome, event boundaries, one-decimal settlement "
            "and exactly-one-winner tests.",
            "Certified contract-event panel and settlement manifest.",
        ),
        "02": (
            "Weather training panel",
            "Historically admissible deterministic forecasts, complete HKT "
            "paths, HKO outcomes, residuals and product metadata.",
            "Expanded forecast-HKO training panel and admission manifest.",
        ),
        "03": (
            "Market evaluation panel",
            "Certified contracts, historical market records, record age, raw "
            "YES values and normalised complete books.",
            "Exact market evaluation panel and support manifest.",
        ),
        "04": (
            "Gaussian-process implementation audit",
            "Exact estimator, transformations, covariance, noise, jitter, "
            "variance semantics and direct matrix reproduction.",
            "Passed GP audit report and unit-test evidence.",
        ),
        "05": (
            "Model fitting and selection",
            "Five-family chronological OOF predictions on exact common "
            "support.",
            "Selected continuous model and development diagnostics.",
        ),
        "06": (
            "Quantiles, event probabilities and adjustment",
            "Ninety-nine quantiles, monotone repair, event mapping, dispersion "
            "adjustment and probability regularisation.",
            "Locked coherent probability specification.",
        ),
        "07": (
            "External evaluation and paired inference",
            "External continuous CRPS, market comparison and settlement-date "
            "bootstrap.",
            "External score tables and paired uncertainty.",
        ),
        "08": (
            "Final trading and PnL",
            "Development-selected rule and threshold, one-share external "
            "simulation and focused sensitivities.",
            "Final trading evidence and bootstrap report.",
        ),
        "09": (
            "Thesis tables, figures and audit",
            "Generate final outputs from one empirical release and reconcile "
            "every thesis number.",
            "Tables, figures, hashes and numerical audit.",
        ),
    }

    spec_lines = [
        "# Canonical Notebook Build Specification",
        "",
        "This document defines what each final notebook owns and which archived "
        "notebooks may supply logic.",
        "",
    ]

    for number in [f"{value:02d}" for value in range(10)]:
        title, responsibility, output = specifications[number]

        spec_lines.extend(
            [
                f"## Notebook {number} — {title}",
                "",
                f"**Responsibility:** {responsibility}",
                "",
                f"**Required output:** {output}",
                "",
                "**Permitted historical sources:**",
                "",
            ]
        )

        sources = sorted(set(sources_by_destination.get(number, [])))

        if sources:
            spec_lines.extend(
                f"- `{source}`" for source in sources
            )
        else:
            spec_lines.append(
                "- No historical notebook is automatically admitted."
            )

        spec_lines.extend(
            [
                "",
                "**Prohibited migration:**",
                "",
                "- old output cells;",
                "- old headline numbers;",
                "- duplicated helper functions;",
                "- superseded sample dates;",
                "- undocumented manual edits;",
                "",
            ]
        )

    spec_path = docs / "CANONICAL_NOTEBOOK_BUILD_SPEC.md"
    spec_path.write_text(
        "\n".join(spec_lines) + "\n",
        encoding="utf-8",
    )

    order_lines = [
        "# Migration Execution Order",
        "",
        "The migration is performed in dependency order.",
        "",
        "1. Notebook 00: configuration, source registry and manifests.",
        "2. Notebook 01: settlement and event certification.",
        "3. Notebook 02: weather training panel.",
        "4. Notebook 03: market evaluation panel.",
        "5. Notebook 04: GP code audit.",
        "6. Notebook 05: model fitting and selection.",
        "7. Notebook 06: probability construction and adjustment.",
        "8. Notebook 07: external evaluation and inference.",
        "9. Notebook 08: final trading and PnL.",
        "10. Notebook 09: tables, figures and numerical audit.",
        "",
        "No downstream notebook begins until the upstream data and integrity "
        "tests it depends on have passed.",
        "",
        "## Immediate next migration",
        "",
        "The next implementation task is Notebook 00 followed by Notebook 01.",
        "Only the latest valid configuration, source-adapter and settlement "
        "logic identified in the migration map should be extracted.",
        "",
    ]

    order_path = docs / "MIGRATION_EXECUTION_ORDER.md"
    order_path.write_text(
        "\n".join(order_lines),
        encoding="utf-8",
    )

    status_path = docs / "MIGRATION_STATUS.md"
    status_path.write_text(
        "\n".join(
            [
                "# Historical Notebook Migration Status",
                "",
                f"Archive branch: `{ARCHIVE_BRANCH}`",
                "",
                f"Historical notebooks inspected: **{len(rows)}**",
                "",
                "## Current state",
                "",
                "- Complete notebook inventory: complete.",
                "- Structural notebook inspection: complete.",
                "- Automatic migration classification: complete.",
                (
                    "- Manual review items: "
                    f"**{len(review_rows)}**."
                ),
                "- Historical notebooks copied into clean branch: **0**.",
                "",
                "## Next action",
                "",
                "Build canonical Notebook 00 and Notebook 01 by extracting only "
                "the approved logic listed in the migration map.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("Created:")
    print(f"  {csv_path}")
    print(f"  {json_path}")
    print(f"  {migration_path}")
    print(f"  {spec_path}")
    print(f"  {order_path}")
    print(f"  {status_path}")
    print()
    print(f"Notebook count: {len(rows)}")

    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")

    print(f"MANUAL_REVIEW: {len(review_rows)}")


if __name__ == "__main__":
    main()
