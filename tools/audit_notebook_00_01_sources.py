#!/usr/bin/env python3
"""Inspect, but do not migrate, archived sources for Notebooks 00 and 01."""

from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


ARCHIVE_BRANCH = "archive/17j-plus-18n-18y-20260726"
INVENTORY_PATH = Path("docs/HISTORICAL_NOTEBOOK_INVENTORY.csv")


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
    )
    return result.stdout


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8", errors="replace")


def load_inventory() -> List[Dict[str, str]]:
    with INVENTORY_PATH.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_archived_notebook(path: str) -> Dict[str, Any]:
    payload = git_bytes(
        "show",
        f"{ARCHIVE_BRANCH}:{path}",
    )
    return json.loads(payload.decode("utf-8"))


def code_cells(notebook: Dict[str, Any]) -> Iterable[str]:
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "code":
            yield "".join(cell.get("source", []))


def markdown_headings(notebook: Dict[str, Any]) -> List[str]:
    headings: List[str] = []

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue

        for line in "".join(cell.get("source", [])).splitlines():
            stripped = line.strip()

            if stripped.startswith("#"):
                headings.append(stripped.lstrip("#").strip())

    return headings[:20]


def function_names(source: str) -> Set[str]:
    names: Set[str] = set()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)

    return names


def imported_modules(source: str) -> Set[str]:
    modules: Set[str] = set()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return modules

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])

    return modules


def likely_paths_and_urls(source: str) -> Set[str]:
    candidates: Set[str] = set()

    string_pattern = re.compile(
        r"""['"]([^'"]{4,300})['"]"""
    )

    extensions = (
        ".csv",
        ".json",
        ".parquet",
        ".pkl",
        ".pickle",
        ".zip",
        ".md",
        ".yaml",
        ".yml",
    )

    for value in string_pattern.findall(source):
        lower = value.lower()

        if (
            value.startswith(("http://", "https://"))
            or "/" in value and lower.endswith(extensions)
            or lower.endswith(extensions)
        ):
            candidates.add(value)

    return candidates


def relevant_archive_files() -> List[Dict[str, str]]:
    paths = git_text(
        "ls-tree",
        "-r",
        "--name-only",
        ARCHIVE_BRANCH,
    ).splitlines()

    keywords = (
        "hko",
        "settlement",
        "contract",
        "event",
        "gamma",
        "resolution",
        "manifest",
        "config",
        "sample",
        "fold",
        "availability",
    )

    relevant = []

    for path in paths:
        lower = path.lower()

        if path.endswith(".ipynb"):
            continue

        if not any(keyword in lower for keyword in keywords):
            continue

        try:
            size_text = git_text(
                "cat-file",
                "-s",
                f"{ARCHIVE_BRANCH}:{path}",
            ).strip()
        except subprocess.CalledProcessError:
            size_text = ""

        relevant.append(
            {
                "path": path,
                "size_bytes": size_text,
            }
        )

    return relevant


def main() -> None:
    inventory = load_inventory()

    approved = [
        row
        for row in inventory
        if row["status"] in {"MIGRATE_LOGIC", "MIGRATE_AND_AUDIT"}
        and any(
            target in row["canonical_notebook"].split(" and ")
            for target in ("00", "01")
        )
    ]

    notebook_rows: List[Dict[str, str]] = []
    all_functions: Counter[str] = Counter()
    all_imports: Counter[str] = Counter()
    all_paths: Counter[str] = Counter()

    for row in approved:
        path = row["historical_path"]
        notebook = load_archived_notebook(path)

        functions: Set[str] = set()
        imports: Set[str] = set()
        paths_and_urls: Set[str] = set()

        for source in code_cells(notebook):
            functions.update(function_names(source))
            imports.update(imported_modules(source))
            paths_and_urls.update(likely_paths_and_urls(source))

        all_functions.update(functions)
        all_imports.update(imports)
        all_paths.update(paths_and_urls)

        notebook_rows.append(
            {
                "historical_path": path,
                "canonical_notebook": row["canonical_notebook"],
                "status": row["status"],
                "headings": " | ".join(markdown_headings(notebook)),
                "functions_and_classes": "; ".join(sorted(functions)),
                "imports": "; ".join(sorted(imports)),
                "paths_and_urls": "; ".join(sorted(paths_and_urls)),
            }
        )

    output_csv = Path("docs/NOTEBOOK_00_01_ARCHIVE_SOURCE_AUDIT.csv")

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(notebook_rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(notebook_rows)

    archive_files = relevant_archive_files()

    lines = [
        "# Notebook 00–01 Archive Source Audit",
        "",
        f"Archive branch: `{ARCHIVE_BRANCH}`",
        "",
        f"Approved historical notebooks inspected: **{len(notebook_rows)}**",
        "",
        "No historical notebook or output has been copied into the clean branch.",
        "",
        "## Approved notebook sources",
        "",
        "| Historical source | Destination | Functions/classes found |",
        "|---|---|---|",
    ]

    for row in notebook_rows:
        names = row["functions_and_classes"] or "No named functions"
        names = names.replace("|", "\\|")

        lines.append(
            f"| `{row['historical_path']}` | "
            f"{row['canonical_notebook']} | "
            f"{names} |"
        )

    lines.extend(
        [
            "",
            "## Repeated function and class names",
            "",
        ]
    )

    repeated_functions = [
        (name, count)
        for name, count in all_functions.most_common()
        if count >= 2
    ]

    if repeated_functions:
        for name, count in repeated_functions:
            lines.append(f"- `{name}`: {count} historical notebooks")
    else:
        lines.append("- No repeated named functions were identified.")

    lines.extend(
        [
            "",
            "## Frequently imported packages",
            "",
        ]
    )

    for name, count in all_imports.most_common(30):
        lines.append(f"- `{name}`: {count}")

    lines.extend(
        [
            "",
            "## Candidate archived source and data files",
            "",
            "| Path | Size in bytes |",
            "|---|---:|",
        ]
    )

    for item in archive_files:
        lines.append(
            f"| `{item['path']}` | {item['size_bytes']} |"
        )

    lines.extend(
        [
            "",
            "## Migration decision",
            "",
            "Notebook 00 receives only:",
            "",
            "- configuration declarations;",
            "- run-manifest logic;",
            "- source-registry logic;",
            "- chronological design declarations.",
            "",
            "Notebook 01 receives only:",
            "",
            "- official HKO source handling;",
            "- final event-boundary parsing;",
            "- one-decimal settlement classification;",
            "- exactly-one-winner integrity checks.",
            "",
            "Old output cells, sample counts, figures and headline results are "
            "not migrated.",
            "",
        ]
    )

    output_md = Path("docs/NOTEBOOK_00_01_ARCHIVE_SOURCE_AUDIT.md")
    output_md.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(f"Approved archived notebooks inspected: {len(notebook_rows)}")
    print(f"Candidate archived files inspected: {len(archive_files)}")
    print(f"Wrote: {output_csv}")
    print(f"Wrote: {output_md}")


if __name__ == "__main__":
    main()
