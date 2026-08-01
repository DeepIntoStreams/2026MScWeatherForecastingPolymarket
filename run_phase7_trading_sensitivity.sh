#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
OUT="outputs/v70_empirical_finalisation/phase7_trading_sensitivity"
SPEC="config/v70/phase7_trading_sensitivity_spec.json"
SCRIPT="tools/v70_empirical_finalisation/build_phase7_trading_sensitivity.py"

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat

printf '\n================================================================================================\n'
printf 'PHASE 7 — TRADING SENSITIVITY AND PNL ATTRIBUTION\n'
printf '================================================================================================\n\n'

if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
  printf 'ERROR: expected branch %s but found %s\n' \
    "$BRANCH" "$(git branch --show-current)"
  exit 1
fi

if [[ -n "$(git status --short)" ]]; then
  printf 'ERROR: working tree is not clean. No files were changed.\n'
  git status --short
  exit 1
fi

python - <<'PY'
from pathlib import Path
import pandas as pd

def as_bool(series):
    if str(series.dtype) == "bool":
        return series.fillna(False)
    return (
        series.astype(str).str.strip().str.lower()
        .map({
            "true": True, "1": True, "yes": True, "passed": True,
            "false": False, "0": False, "no": False, "failed": False,
        })
        .fillna(False)
        .astype(bool)
    )

checks = [
    (
        "Phase 1",
        Path("outputs/v70_empirical_finalisation/phase1_evidence_recovery/phase1_completion_status.csv"),
    ),
    (
        "Phase 2",
        Path("outputs/v70_empirical_finalisation/phase2_settlement_error/phase2_integrity_checks.csv"),
    ),
    (
        "Phase 3",
        Path("outputs/v70_empirical_finalisation/phase3_information_arrival/phase3_integrity_checks.csv"),
    ),
    (
        "Phase 4",
        Path("outputs/v70_empirical_finalisation/phase4_forecast_attribution/phase4_integrity_checks.csv"),
    ),
    (
        "Phase 5",
        Path("outputs/v70_empirical_finalisation/phase5_calibration_misspecification/phase5_integrity_checks.csv"),
    ),
    (
        "Phase 6",
        Path("outputs/v70_empirical_finalisation/phase6_market_information/phase6_integrity_checks.csv"),
    ),
]
for name, path in checks:
    if not path.is_file():
        raise SystemExit(f"ERROR: {name} dependency is missing: {path}")
    frame = pd.read_csv(path)
    if not {"critical", "passed"}.issubset(frame.columns):
        raise SystemExit(f"ERROR: {name} dependency table is malformed.")
    failed = frame[as_bool(frame["critical"]) & ~as_bool(frame["passed"])]
    if not failed.empty:
        print(failed.to_string(index=False))
        raise SystemExit(f"ERROR: {name} contains critical failures.")
    print(f"{name} dependency check: PASSED")
PY

python -m py_compile "$SCRIPT"
python "$SCRIPT" --self-test

rm -rf "$OUT"

set +e
python "$SCRIPT" \
  --repo-root "$REPO" \
  --spec "$SPEC" \
  --output-root "$OUT" \
  2>&1 | tee /tmp/phase7_trading_sensitivity.log
STATUS=${PIPESTATUS[0]}
set -e

printf '\n================================================================================================\n'
printf 'PHASE 7 OUTPUTS\n'
printf '================================================================================================\n\n'

if [[ -d "$OUT" ]]; then
  find "$OUT" -maxdepth 2 -type f -print | sort
fi

printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  printf '\nPhase 7 failed. Do not commit generated outputs.\n'
  if [[ -f "$OUT/phase7_review_bundle.zip" ]]; then
    printf 'Upload: %s/phase7_review_bundle.zip\n' "$OUT"
  else
    printf 'Upload /tmp/phase7_trading_sensitivity.log and generated files.\n'
  fi
  exit "$STATUS"
fi

printf '\nPhase 7 passed. Inspect before committing:\n'
printf '  %s/phase7_report.md\n' "$OUT"
printf '  %s/phase7_integrity_checks.csv\n' "$OUT"
printf '  %s/phase7_review_bundle.zip\n' "$OUT"
