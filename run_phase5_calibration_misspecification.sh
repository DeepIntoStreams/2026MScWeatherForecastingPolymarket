#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
FROZEN_REF="v2-empirical-complete"
WORKTREE="/tmp/2026MScWeatherForecastingPolymarket_v2_frozen_phase5"
OUT="outputs/v70_empirical_finalisation/phase5_calibration_misspecification"
SPEC="config/v70/phase5_calibration_misspecification_spec.json"
SCRIPT="tools/v70_empirical_finalisation/build_phase5_calibration_misspecification.py"

cleanup_phase5_worktree() {
  git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$WORKTREE"
}
trap cleanup_phase5_worktree EXIT

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat

printf '\n================================================================================================\n'
printf 'PHASE 5 — CALIBRATION AND GP MISSPECIFICATION\n'
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

git fetch --all --tags --prune
git rev-parse --verify "$FROZEN_REF^{commit}" >/dev/null

cleanup_phase5_worktree
git worktree add --detach "$WORKTREE" "$FROZEN_REF"

python -m py_compile "$SCRIPT"
python "$SCRIPT" --self-test

rm -rf "$OUT"

set +e
python "$SCRIPT" \
  --repo-root "$REPO" \
  --frozen-root "$WORKTREE" \
  --spec "$SPEC" \
  --output-root "$OUT" \
  2>&1 | tee /tmp/phase5_calibration_misspecification.log
STATUS=${PIPESTATUS[0]}
set -e

cleanup_phase5_worktree
trap - EXIT

printf '\n================================================================================================\n'
printf 'PHASE 5 OUTPUTS\n'
printf '================================================================================================\n\n'

if [[ -d "$OUT" ]]; then
  find "$OUT" -maxdepth 3 -type f -print | sort
fi

printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  printf '\nPhase 5 failed. Do not commit generated outputs.\n'
  if [[ -f "$OUT/phase5_review_bundle.zip" ]]; then
    printf 'Upload: %s/phase5_review_bundle.zip\n' "$OUT"
  else
    printf 'Upload /tmp/phase5_calibration_misspecification.log and any generated files.\n'
  fi
  exit "$STATUS"
fi

printf '\nPhase 5 passed. Inspect before committing:\n'
printf '  %s/phase5_report.md\n' "$OUT"
printf '  %s/phase5_frozen_direct_reconciliation.csv\n' "$OUT"
printf '  %s/phase5_review_bundle.zip\n' "$OUT"
