#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
FROZEN_REF="v2-empirical-complete"
WORKTREE="/tmp/2026MScWeatherForecastingPolymarket_v2_frozen_phase2"
PHASE1="outputs/v70_empirical_finalisation/phase1_evidence_recovery"
OUT="outputs/v70_empirical_finalisation/phase2_settlement_error"
SPEC="config/v70/phase2_settlement_error_spec.json"
SCRIPT="tools/v70_empirical_finalisation/build_phase2_settlement_error.py"

cleanup_phase2_worktree() {
  git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$WORKTREE"
}
trap cleanup_phase2_worktree EXIT

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat

printf '\n================================================================================\n'
printf 'PHASE 2 — SETTLEMENT APPROXIMATION-ERROR ANALYSIS\n'
printf '================================================================================\n\n'

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

if [[ ! -f "$PHASE1/phase1_completion_status.csv" ]]; then
  printf 'ERROR: accepted Phase 1 outputs are missing.\n'
  exit 1
fi

python - <<'PY'
import pandas as pd
p = "outputs/v70_empirical_finalisation/phase1_evidence_recovery/phase1_completion_status.csv"
d = pd.read_csv(p)
failed = d[d["critical"].astype(bool) & ~d["passed"].astype(bool)]
if not failed.empty:
    print(failed.to_string(index=False))
    raise SystemExit("ERROR: Phase 1 contains critical failures.")
print("Phase 1 dependency check: PASSED")
PY

git fetch --all --tags --prune
git rev-parse --verify "$FROZEN_REF^{commit}" >/dev/null

cleanup_phase2_worktree
git worktree add --detach "$WORKTREE" "$FROZEN_REF"

python -m py_compile "$SCRIPT"
python "$SCRIPT" --self-test

rm -rf "$OUT"

set +e
python "$SCRIPT" \
  --repo-root "$REPO" \
  --frozen-root "$WORKTREE" \
  --phase1-root "$REPO/$PHASE1" \
  --spec "$SPEC" \
  --output-root "$OUT" \
  2>&1 | tee /tmp/phase2_settlement_error.log
STATUS=${PIPESTATUS[0]}
set -e

cleanup_phase2_worktree
trap - EXIT

printf '\n================================================================================\n'
printf 'PHASE 2 OUTPUTS\n'
printf '================================================================================\n\n'

if [[ -d "$OUT" ]]; then
  find "$OUT" -maxdepth 2 -type f -print | sort
fi

printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  printf '\nPhase 2 failed. Do not commit generated outputs.\n'
  if [[ -f "$OUT/phase2_review_bundle.zip" ]]; then
    printf 'Upload: %s/phase2_review_bundle.zip\n' "$OUT"
  else
    printf 'Upload /tmp/phase2_settlement_error.log and any generated files.\n'
  fi
  exit "$STATUS"
fi

printf '\nPhase 2 passed. Inspect before committing:\n'
printf '  %s/phase2_report.md\n' "$OUT"
printf '  %s/phase2_review_bundle.zip\n' "$OUT"
