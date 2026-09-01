#!/usr/bin/env bash
set -euo pipefail

echo "======================================================================"
echo " CONTROLLED 31-AUGUST EXTERNAL-TARGET REFRESH"
echo "======================================================================"

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: run the refresh only from a clean working tree."
    exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path

p = Path(
    "outputs/final_pipeline/synthesis/"
    "pending_target_status.json"
)

x = json.loads(
    p.read_text()
)

pending = x[
    "pending_dates"
]

if not pending:
    print(
        "No target is pending. Nothing to refresh."
    )
    raise SystemExit(10)

if pending != [
    "2026-08-31"
]:
    raise RuntimeError(
        f"Unexpected pending target set: {pending}"
    )

print(
    "PASS: only 2026-08-31 is pending."
)
PY

STATUS=$?

if [ "$STATUS" -eq 10 ]; then
    exit 0
fi

echo
echo "Refreshing official HKO target..."
python3 -m src.final_pipeline.hko --refresh

echo
echo "Recomputing target-dependent downstream outputs..."
python3 -m src.final_pipeline.residuals
python3 -m src.final_pipeline.weather_models
python3 -m src.final_pipeline.market_books
python3 -m src.final_pipeline.trading
python3 -m src.final_pipeline.synthesis
python3 -m src.final_pipeline.reporting
python3 -m src.final_pipeline.release

echo
echo "Verifying frozen development selections..."

python3 - <<'PY'
import json
import math
from pathlib import Path

p = Path(
    "outputs/final_pipeline/release/"
    "final_release_summary.json"
)

x = json.loads(
    p.read_text()
)

assert x[
    "weather_kernel"
] == "matern32"

assert math.isclose(
    x[
        "pool_weight_gp"
    ],
    0.188,
    abs_tol=1e-12,
)

assert x[
    "trading_rule"
] == "24h_prior"

assert math.isclose(
    x[
        "trading_threshold"
    ],
    0.15,
    abs_tol=1e-12,
)

pending = x[
    "pending_target_dates"
]

if pending:
    print(
        "31 August is still not available in the "
        "authoritative HKO pipeline."
    )

    print(
        "Pending:",
        pending,
    )

    raise SystemExit(3)

print(
    "PASS: 31 August settled and development selections remained frozen."
)
PY

for TEST in tests/final_pipeline/test_*.py; do
    python3 "$TEST"
done

echo
echo "Refresh complete."
echo "Review all changed target-dependent outputs before committing."
