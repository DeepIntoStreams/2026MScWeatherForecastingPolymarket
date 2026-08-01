#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
TAG="v70-empirical-synthesis-complete"
SPEC="config/v70/phase9_exploratory_trading_spec.json"
SCRIPT="tools/v70_empirical_finalisation/build_phase9_exploratory_trading.py"
OUT="outputs/v70_empirical_finalisation/phase9_exploratory_trading"

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat
export PYTHONPATH="$REPO/tools/v70_empirical_finalisation:${PYTHONPATH:-}"

printf '\n====================================================================================================\n'
printf 'PHASE 9 — EXPLORATORY TRADING STRATEGY LABORATORY\n'
printf '====================================================================================================\n\n'

if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
  echo "ERROR: expected branch $BRANCH"
  exit 1
fi
if [[ -n "$(git status --short)" ]]; then
  echo "ERROR: working tree is not clean."
  git status --short
  exit 1
fi
if ! git merge-base --is-ancestor "$TAG" HEAD; then
  echo "ERROR: current HEAD does not descend from $TAG"
  exit 1
fi

python -m py_compile \
  tools/v70_empirical_finalisation/phase9_core.py \
  tools/v70_empirical_finalisation/phase9_search.py \
  "$SCRIPT"
python "$SCRIPT" --self-test

rm -rf "$OUT"

set +e
python "$SCRIPT" \
  --repo-root "$REPO" \
  --spec "$SPEC" \
  --output-root "$OUT" \
  2>&1 | tee /tmp/phase9_exploratory_trading.log
STATUS=${PIPESTATUS[0]}
set -e

printf '\n====================================================================================================\n'
printf 'PHASE 9 OUTPUTS\n'
printf '====================================================================================================\n\n'
if [[ -d "$OUT" ]]; then
  find "$OUT" -maxdepth 2 -type f -print | sort
fi
printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  echo
  echo "Phase 9 failed. Do not commit generated outputs."
  if [[ -f "$OUT/phase9_review_bundle.zip" ]]; then
    echo "Upload: $OUT/phase9_review_bundle.zip"
  else
    echo "Upload /tmp/phase9_exploratory_trading.log and generated files."
  fi
  exit "$STATUS"
fi

echo
echo "Phase 9 passed. Inspect before committing:"
echo "  $OUT/phase9_report.md"
echo "  $OUT/phase9_integrity_checks.csv"
echo "  $OUT/phase9_outer_walkforward_summary.csv"
echo "  $OUT/phase9_sharpe_leaderboard.csv"
echo "  $OUT/phase9_review_bundle.zip"
