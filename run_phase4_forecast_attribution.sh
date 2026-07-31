#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
FROZEN_REF="v2-empirical-complete"
WORKTREE="/tmp/2026MScWeatherForecastingPolymarket_v2_frozen_phase4"
PHASE1="outputs/v70_empirical_finalisation/phase1_evidence_recovery"
PHASE2="outputs/v70_empirical_finalisation/phase2_settlement_error"
PHASE3="outputs/v70_empirical_finalisation/phase3_information_arrival"
OUT="outputs/v70_empirical_finalisation/phase4_forecast_attribution"
SPEC="config/v70/phase4_forecast_attribution_spec.json"
SCRIPT="tools/v70_empirical_finalisation/build_phase4_forecast_attribution.py"

cleanup_phase4_worktree() {
  git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$WORKTREE"
}
trap cleanup_phase4_worktree EXIT

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat

printf '\n============================================================================================\n'
printf 'PHASE 4 — FULL RAW-STATIC-RBF-MATÉRN FORECAST ATTRIBUTION\n'
printf '============================================================================================\n\n'

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
]
for name, path in checks:
    if not path.is_file():
        raise SystemExit(f"ERROR: {name} dependency is missing: {path}")
    frame = pd.read_csv(path)
    failed = frame[
        frame["critical"].astype(bool)
        & ~frame["passed"].astype(bool)
    ]
    if not failed.empty:
        print(failed.to_string(index=False))
        raise SystemExit(f"ERROR: {name} contains critical failures.")
    print(f"{name} dependency check: PASSED")
PY

git fetch --all --tags --prune
git rev-parse --verify "$FROZEN_REF^{commit}" >/dev/null

cleanup_phase4_worktree
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
  2>&1 | tee /tmp/phase4_forecast_attribution.log
STATUS=${PIPESTATUS[0]}
set -e

cleanup_phase4_worktree
trap - EXIT

printf '\n============================================================================================\n'
printf 'PHASE 4 OUTPUTS\n'
printf '============================================================================================\n\n'

if [[ -d "$OUT" ]]; then
  find "$OUT" -maxdepth 2 -type f -print | sort
fi

printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  printf '\nPhase 4 failed. Do not commit generated outputs.\n'
  if [[ -f "$OUT/phase4_review_bundle.zip" ]]; then
    printf 'Upload: %s/phase4_review_bundle.zip\n' "$OUT"
  else
    printf 'Upload /tmp/phase4_forecast_attribution.log and any generated files.\n'
  fi
  exit "$STATUS"
fi

printf '\nPhase 4 passed. Inspect before committing:\n'
printf '  %s/phase4_report.md\n' "$OUT"
printf '  %s/phase4_review_bundle.zip\n' "$OUT"
