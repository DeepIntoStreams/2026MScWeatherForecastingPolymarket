#!/usr/bin/env python3
"""Generate canonical Notebooks 00 and 01."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


def markdown(text: str):
    return nbf.v4.new_markdown_cell(
        dedent(text).strip()
    )


def code(text: str):
    return nbf.v4.new_code_cell(
        dedent(text).strip()
    )


def write_notebook(
    path: Path,
    cells,
) -> None:
    notebook = nbf.v4.new_notebook()

    notebook["cells"] = cells
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    nbf.write(
        notebook,
        path,
    )


root = Path.cwd()

write_notebook(
    root
    / "notebooks"
    / "final"
    / "00_project_configuration_and_manifest.ipynb",
    [
        markdown(
            """
            # 00 — Project Configuration and Manifest

            This notebook records the declared empirical design, Git state,
            configuration hashes and software environment before any model is
            fitted.

            It does not produce a research result.
            """
        ),
        code(
            """
            from pathlib import Path
            import sys

            def locate_repository(start: Path) -> Path:
                current = start.resolve()

                for candidate in (current, *current.parents):
                    if (candidate / "config" / "analysis.yaml").exists():
                        return candidate

                raise FileNotFoundError("Repository root not found.")

            ROOT = locate_repository(Path.cwd())
            SRC = ROOT / "src"

            if str(SRC) not in sys.path:
                sys.path.insert(0, str(SRC))

            print(f"Repository root: {ROOT}")
            """
        ),
        code(
            """
            from weather_polymarket.config import load_project_config

            CONFIG = load_project_config(ROOT)
            ANALYSIS = CONFIG["analysis"]

            print("Decision rules:")

            for rule in ANALYSIS["decision_rules"]:
                print(f"  - {rule}")

            print(
                "\\nDevelopment end:",
                ANALYSIS["dates"]["development_end"],
            )

            print(
                "Requested external period:",
                ANALYSIS["dates"]["external_start"],
                "to",
                ANALYSIS["dates"]["external_end_requested"],
            )

            print(
                "Uncertainty unit:",
                ANALYSIS["project"]["uncertainty_unit"],
            )
            """
        ),
        code(
            """
            from weather_polymarket.manifest import (
                collect_environment_manifest,
                write_json_atomic,
            )

            packages = [
                "numpy",
                "pandas",
                "scipy",
                "scikit-learn",
                "catboost",
                "matplotlib",
                "PyYAML",
                "nbformat",
                "nbconvert",
            ]

            manifest = collect_environment_manifest(
                repo_root=ROOT,
                packages=packages,
            )

            manifest["declared_analysis"] = ANALYSIS

            manifest_path = (
                ROOT
                / "data"
                / "manifests"
                / "00_project_environment_manifest.json"
            )

            write_json_atomic(
                manifest_path,
                manifest,
            )

            print(
                f"Manifest written to: {manifest_path}"
            )

            print(
                "Working tree clean when recorded:",
                manifest["repository"]["working_tree_clean"],
            )
            """
        ),
        markdown(
            """
            ## Interpretation

            A change to the configuration, source registry, model registry or
            software environment changes the recorded manifest. The manifest
            therefore identifies the declared design associated with later
            empirical outputs.
            """
        ),
    ],
)

write_notebook(
    root
    / "notebooks"
    / "final"
    / "01_hko_settlement_and_event_certification.ipynb",
    [
        markdown(
            """
            # 01 — HKO Settlement and Event Certification

            This notebook owns the official HKO settlement variable, contract
            boundaries, one-decimal classification and exactly-one-winner
            integrity checks.

            The present stage validates the canonical certification engine.
            Real source certification begins after the final HKO and contract
            source adapters are migrated.
            """
        ),
        code(
            """
            from pathlib import Path
            import json
            import sys
            from datetime import datetime, timezone

            def locate_repository(start: Path) -> Path:
                current = start.resolve()

                for candidate in (current, *current.parents):
                    if (candidate / "config" / "analysis.yaml").exists():
                        return candidate

                raise FileNotFoundError("Repository root not found.")

            ROOT = locate_repository(Path.cwd())
            SRC = ROOT / "src"

            if str(SRC) not in sys.path:
                sys.path.insert(0, str(SRC))

            print(f"Repository root: {ROOT}")
            """
        ),
        code(
            """
            from weather_polymarket.settlement import (
                build_standard_11_event_book,
                classify_temperature,
                validate_partition,
            )

            event_book = build_standard_11_event_book(
                lower_cut_c=25,
                upper_cut_c=34,
            )

            validate_partition(
                event_book,
                expected_count=11,
            )

            boundary_examples = {
                24.9: "below_25",
                25.0: "25_to_26",
                30.9: "30_to_31",
                31.0: "31_to_32",
                34.0: "34_or_higher",
            }

            for temperature_c, expected_event in boundary_examples.items():
                actual_event = classify_temperature(
                    event_book,
                    temperature_c,
                ).event_id

                assert actual_event == expected_event

                print(
                    f"{temperature_c:.1f} C -> {actual_event}"
                )

            print(
                "\\nSynthetic event-boundary certification passed."
            )
            """
        ),
        code(
            """
            expected_inputs = {
                "contract_definitions": (
                    ROOT
                    / "data"
                    / "interim"
                    / "canonical_contract_definitions.csv"
                ),
                "hko_daily_max": (
                    ROOT
                    / "data"
                    / "interim"
                    / "hko_daily_max.csv"
                ),
            }

            input_status = {
                name: path.exists()
                for name, path in expected_inputs.items()
            }

            readiness_status = (
                "READY_FOR_REAL_DATA_CERTIFICATION"
                if all(input_status.values())
                else "SOURCE_ADAPTER_MIGRATION_PENDING"
            )

            readiness = {
                "created_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "status": readiness_status,
                "synthetic_boundary_tests_passed": True,
                "expected_inputs": {
                    name: {
                        "path": str(path),
                        "exists": input_status[name],
                    }
                    for name, path in expected_inputs.items()
                },
                "settlement_convention": {
                    "lower_tail": "(-infinity, k+1)",
                    "interior": "[k, k+1)",
                    "upper_tail": "[K, infinity)",
                    "round_hko_to_integer": False,
                },
            }

            report_path = (
                ROOT
                / "outputs"
                / "diagnostics"
                / "01_settlement_certification_readiness.json"
            )

            report_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            report_path.write_text(
                json.dumps(
                    readiness,
                    indent=2,
                )
                + "\\n",
                encoding="utf-8",
            )

            print(
                f"Readiness status: {readiness_status}"
            )

            print(
                f"Diagnostic report: {report_path}"
            )
            """
        ),
        markdown(
            """
            ## Evidential boundary

            Passing the synthetic checks proves that the clean implementation
            follows the stated half-open event convention. It does not yet
            certify the real contract books. Real certification requires the
            admitted HKO and Polymarket source inputs.
            """
        ),
    ],
)

print("Created canonical Notebook 00.")
print("Created canonical Notebook 01.")
