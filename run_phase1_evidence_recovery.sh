#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
FROZEN_REF="v2-empirical-complete"
WORKTREE="/tmp/2026MScWeatherForecastingPolymarket_v2_frozen"
OUT="outputs/v70_empirical_finalisation/phase1_evidence_recovery"

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat

printf '\n============================================================\n'
printf 'PHASE 1 — COMPLETE ROW-LEVEL EVIDENCE RECOVERY\n'
printf '============================================================\n\n'

if [[ -n "$(git status --short)" ]]; then
  printf 'ERROR: working tree is not clean. No files were changed.\n'
  git status --short
  exit 1
fi

git fetch --all --tags --prune

git rev-parse --verify "$FROZEN_REF^{commit}" >/dev/null

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
else
  git switch -c "$BRANCH" "$FROZEN_REF"
fi

if [[ -n "$(git status --short)" ]]; then
  printf 'ERROR: working tree became non-clean after branch switch.\n'
  git status --short
  exit 1
fi

if [[ -d "$WORKTREE" ]]; then
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$WORKTREE"
fi
git worktree add --detach "$WORKTREE" "$FROZEN_REF"

python -m py_compile \
  tools/v70_empirical_finalisation/build_phase1_evidence_recovery.py

python tools/v70_empirical_finalisation/build_phase1_evidence_recovery.py \
  --repo-root "$REPO" \
  --frozen-root "$WORKTREE" \
  --spec config/v70/phase1_evidence_recovery_spec.json \
  --output-root "$OUT" \
  2>&1 | tee /tmp/phase1_evidence_recovery.log

STATUS=${PIPESTATUS[0]}

git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true

printf '\n============================================================\n'
printf 'PHASE 1 OUTPUTS\n'
printf '============================================================\n\n'

find "$OUT" -maxdepth 1 -type f -print | sort
printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  printf '\nPhase 1 failed. Do not commit. Upload:\n'
  printf '  %s/phase1_review_bundle.zip\n' "$OUT"
  exit "$STATUS"
fi

printf '\nPhase 1 passed. Inspect the report before committing:\n'
printf '  %s/phase1_report.md\n' "$OUT"
printf '  %s/phase1_review_bundle.zip\n' "$OUT"
