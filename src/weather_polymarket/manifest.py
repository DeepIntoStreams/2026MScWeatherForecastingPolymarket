"""Create deterministic environment and file manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def package_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def collect_environment_manifest(
    repo_root: Path,
    packages: Iterable[str],
) -> Dict[str, Any]:
    status = _git(repo_root, "status", "--porcelain")

    config_paths = [
        repo_root / "config" / "analysis.yaml",
        repo_root / "config" / "models.yaml",
        repo_root / "config" / "data_sources.yaml",
    ]

    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "branch": _git(
                repo_root,
                "branch",
                "--show-current",
            ),
            "commit": _git(
                repo_root,
                "rev-parse",
                "HEAD",
            ),
            "working_tree_clean": status == "",
            "status_porcelain": status.splitlines(),
        },
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "packages": {
            package: package_version(package)
            for package in packages
        },
        "configuration_files": {
            str(path.relative_to(repo_root)): {
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in config_paths
        },
    }


def write_json_atomic(
    path: Path,
    payload: Dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(path)
