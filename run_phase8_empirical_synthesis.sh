#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
SPEC="config/v70/phase8_empirical_synthesis_spec.json"
SCRIPT="tools/v70_empirical_finalisation/build_phase8_empirical_synthesis.py"
OUT="outputs/v70_empirical_finalisation/phase8_empirical_synthesis"

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat

printf '\n================================================================================================\n'
printf 'PHASE 8 — FINAL EMPIRICAL SYNTHESIS\n'
printf '================================================================================================\n\n'

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
  printf 'ERROR: expected branch %s but found %s\n' "$BRANCH" "$CURRENT_BRANCH"
  return 1 2>/dev/null || true
fi

if [[ -n "$(git status --short)" ]]; then
  printf 'ERROR: working tree is not clean. No files were changed.\n'
  git status --short
  return 1 2>/dev/null || true
fi

python -m py_compile "$SCRIPT"
python "$SCRIPT" --self-test

rm -rf "$OUT"

set +e
python "$SCRIPT" \
  --repo-root "$REPO" \
  --spec "$SPEC" \
  --output-root "$OUT" \
  2>&1 | tee /tmp/phase8_empirical_synthesis.log
STATUS=${PIPESTATUS[0]}
set -e

printf '\n================================================================================================\n'
printf 'PHASE 8 OUTPUTS\n'
printf '================================================================================================\n\n'

if [[ -d "$OUT" ]]; then
  find "$OUT" -maxdepth 2 -type f -print | sort
fi

printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  printf '\nPhase 8 failed. Do not commit generated outputs.\n'
  if [[ -f "$OUT/phase8_review_bundle.zip" ]]; then
    printf 'Upload: %s/phase8_review_bundle.zip\n' "$OUT"
  else
    printf 'Upload /tmp/phase8_empirical_synthesis.log and generated files.\n'
  fi
  return "$STATUS" 2>/dev/null || true
fi

printf '\nPhase 8 passed. Inspect before committing:\n'
printf '  %s/phase8_report.md\n' "$OUT"
printf '  %s/phase8_integrity_checks.csv\n' "$OUT"
printf '  %s/phase8_claims_register.csv\n' "$OUT"
printf '  %s/phase8_review_bundle.zip\n' "$OUT"
