from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INVENTORY = (
    ROOT
    / "data/manifests/v2/"
    "00_v1_protected_file_inventory.csv"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def main() -> None:
    with INVENTORY.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise RuntimeError(
            "Version 1 inventory is empty."
        )

    failures = []

    for row in rows:
        path = ROOT / row["path"]

        if not path.exists():
            failures.append(
                f"MISSING: {row['path']}"
            )
            continue

        actual = sha256(path)

        if actual != row["sha256"]:
            failures.append(
                f"HASH MISMATCH: {row['path']}"
            )

    print("=" * 72)
    print("VERSION 1 RELEASE PRESERVATION CHECK")
    print("=" * 72)
    print("Protected files checked:", len(rows))
    print("Failures:", len(failures))

    if failures:
        for failure in failures:
            print(failure)

        raise RuntimeError(
            "Certified Version 1 files have changed."
        )

    print()
    print(
        "VERSION 1 RELEASE REMAINS UNCHANGED: PASSED"
    )


if __name__ == "__main__":
    main()
