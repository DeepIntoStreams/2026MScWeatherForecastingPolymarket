#!/usr/bin/env bash
set -eo pipefail

MODE="${1:-run}"

if [ "$MODE" != "run" ] && [ "$MODE" != "audit" ]; then
    echo "Usage: $0 [run|audit]"
    exit 1
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TMP_BEFORE="$(mktemp)"
TMP_AFTER="$(mktemp)"
trap 'rm -f "$TMP_BEFORE" "$TMP_AFTER"' EXIT

semantic_manifest () {
    python3 - "$1" <<'PY'
from pathlib import Path
import gzip
import hashlib
import sys

out = Path("outputs/trading_contrast_extension")
target = Path(sys.argv[1])

roots = [
    out / "stage2",
    out / "stage3",
    out / "stage4",
    out / "stage5",
]

rows = []

for root in roots:
    if not root.exists():
        continue

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        rel = path.as_posix()

        if path.suffix == ".gz":
            with gzip.open(path, "rb") as f:
                data = f.read()
        else:
            data = path.read_bytes()

        rows.append(
            (
                rel,
                hashlib.sha256(data).hexdigest(),
            )
        )

target.write_text(
    "".join(
        f"{sha}  {path}\n"
        for path, sha in rows
    )
)
PY
}

if [ "$MODE" = "audit" ]; then
    semantic_manifest "$TMP_BEFORE"
fi

python3 -m src.trading_contrast_extension.stage2_corrected_rebuild
python3 -m src.trading_contrast_extension.stage3
python3 -m src.trading_contrast_extension.stage4
python3 -m src.trading_contrast_extension.stage5

python3 tests/trading_contrast_extension/test_stage2.py
python3 tests/trading_contrast_extension/test_stage3.py
python3 tests/trading_contrast_extension/test_stage4.py
python3 tests/trading_contrast_extension/test_stage5.py
python3 tests/trading_contrast_extension/test_stage6.py

if [ "$MODE" = "audit" ]; then
    semantic_manifest "$TMP_AFTER"

    if ! diff -u "$TMP_BEFORE" "$TMP_AFTER"; then
        echo "ERROR: semantic output manifest changed under replay."
        exit 1
    fi

    # Compressed files may have container-level gzip metadata differences.
    # All non-gzip tracked outputs must remain byte-identical.
    DIRTY_NON_GZIP="$(
        git status --porcelain \
        | sed 's/^...//' \
        | grep '^outputs/trading_contrast_extension/' \
        | grep -vE '\.gz$' \
        | grep -v '^outputs/trading_contrast_extension/release/' \
        || true
    )"

    if [ -n "$DIRTY_NON_GZIP" ]; then
        echo "ERROR: non-gzip extension outputs changed under replay:"
        echo "$DIRTY_NON_GZIP"
        exit 1
    fi

    echo "PASS: semantic clean-clone replay is deterministic."
fi

echo "PASS: trading contrast extension reproduction completed."
