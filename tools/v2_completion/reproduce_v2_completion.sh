#!/usr/bin/env bash
set +u
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 -B \
    tools/v2_completion/build_phase21_reproducibility.py

python3 -m unittest discover \
    -s tests/v2_completion \
    -p 'test_phase21_*.py' \
    -v
