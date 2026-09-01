#!/usr/bin/env bash
set -eo pipefail

MODE="${1:-run}"

if [ "$MODE" != "run" ] && [ "$MODE" != "audit" ]; then
    echo "Usage: $0 [run|audit]"
    exit 1
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

EXT_OUT="outputs/trading_contrast_extension"
EXPECTED_MANIFEST="$EXT_OUT/release/stage2_5_clean_replay_semantic_manifest.sha256"

PRESERVE_DIR="$(mktemp -d)"
EXPECTED_SNAPSHOT="$(mktemp)"
ACTUAL_MANIFEST="$(mktemp)"

restore_preserved () {
    for name in stage6 thesis release; do
        if [ -e "$PRESERVE_DIR/$name" ]; then
            rm -rf "$EXT_OUT/$name"
            cp -a "$PRESERVE_DIR/$name" "$EXT_OUT/$name"
        fi
    done
}

cleanup () {
    restore_preserved || true
    rm -rf "$PRESERVE_DIR"
    rm -f "$EXPECTED_SNAPSHOT" "$ACTUAL_MANIFEST"
}

trap cleanup EXIT

semantic_manifest () {
    local target="$1"

    python3 - "$target" <<'PY'
from pathlib import Path
import gzip
import hashlib
import sys

target = Path(sys.argv[1])

roots = [
    Path("outputs/trading_contrast_extension/stage2"),
    Path("outputs/trading_contrast_extension/stage3"),
    Path("outputs/trading_contrast_extension/stage4"),
    Path("outputs/trading_contrast_extension/stage5"),
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
        f"{sha}  {rel}\n"
        for rel, sha in rows
    )
)
PY
}

if [ "$MODE" = "audit" ]; then
    if [ ! -f "$EXPECTED_MANIFEST" ]; then
        echo "ERROR: expected clean-replay semantic manifest is missing:"
        echo "$EXPECTED_MANIFEST"
        exit 1
    fi

    cp "$EXPECTED_MANIFEST" "$EXPECTED_SNAPSHOT"
fi

for name in stage6 thesis release; do
    if [ -e "$EXT_OUT/$name" ]; then
        cp -a "$EXT_OUT/$name" "$PRESERVE_DIR/$name"
    fi
done

rm -rf \
    "$EXT_OUT/stage2" \
    "$EXT_OUT/stage3" \
    "$EXT_OUT/stage4" \
    "$EXT_OUT/stage5" \
    "$EXT_OUT/stage6" \
    "$EXT_OUT/thesis" \
    "$EXT_OUT/release"

mkdir -p \
    "$EXT_OUT/stage2" \
    "$EXT_OUT/stage3" \
    "$EXT_OUT/stage4" \
    "$EXT_OUT/stage5"

echo "PASS: replay starts from Stage-1-only generated extension state."

python3 -m src.trading_contrast_extension.stage2_corrected_rebuild
python3 -m src.trading_contrast_extension.stage3
python3 -m src.trading_contrast_extension.stage4
python3 -m src.trading_contrast_extension.stage5

restore_preserved

python3 tests/trading_contrast_extension/test_stage2.py
python3 tests/trading_contrast_extension/test_stage3.py
python3 tests/trading_contrast_extension/test_stage4.py
python3 tests/trading_contrast_extension/test_stage5.py
python3 tests/trading_contrast_extension/test_stage6.py

if [ "$MODE" = "audit" ]; then
    semantic_manifest "$ACTUAL_MANIFEST"

    if ! diff -u "$EXPECTED_SNAPSHOT" "$ACTUAL_MANIFEST"; then
        echo "ERROR: regenerated Stage 2-5 semantic manifest does not match the canonical clean-replay manifest."
        exit 1
    fi

    if ! git diff --exit-code -- \
        "$EXT_OUT/stage2" \
        "$EXT_OUT/stage3" \
        "$EXT_OUT/stage4" \
        "$EXT_OUT/stage5"
    then
        echo "ERROR: a Git-tracked Stage 2-5 artefact changed under replay."
        exit 1
    fi

    echo "PASS: regenerated Stage 2-5 semantic universe matches the canonical clean-replay manifest."
    echo "PASS: all Git-tracked Stage 2-5 artefacts are byte-identical after replay."
fi

echo "PASS: trading contrast extension reproduction completed."
