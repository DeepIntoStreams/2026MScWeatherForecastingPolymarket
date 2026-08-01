#!/usr/bin/env bash
set +u
set -e
set -o pipefail

REPO="${HOME}/Desktop/2026MScWeatherForecastingPolymarket"
BRANCH="edward-v70-empirical-finalisation"
FROZEN_REF="v2-empirical-complete"
WORKTREE="/tmp/2026MScWeatherForecastingPolymarket_v2_frozen_phase6"
OUT="outputs/v70_empirical_finalisation/phase6_market_information"
SPEC="config/v70/phase6_market_information_spec.json"
SCRIPT="tools/v70_empirical_finalisation/build_phase6_market_information.py"

cleanup_phase6_worktree() {
  git -C "$REPO" worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$WORKTREE"
}
trap cleanup_phase6_worktree EXIT

cd "$REPO"
export GIT_PAGER=cat
export PAGER=cat

printf '\n================================================================================================\n'
printf 'PHASE 6 — MARKET COMPARISON AND INFORMATION CONTENT\n'
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

cleanup_phase6_worktree
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
  2>&1 | tee /tmp/phase6_market_information.log
STATUS=${PIPESTATUS[0]}
set -e

cleanup_phase6_worktree
trap - EXIT

printf '\n================================================================================================\n'
printf 'PHASE 6 OUTPUTS\n'
printf '================================================================================================\n\n'

if [[ -d "$OUT" ]]; then
  find "$OUT" -maxdepth 2 -type f -print | sort
fi

printf '\nRepository status:\n'
git status --short

if [[ "$STATUS" -ne 0 ]]; then
  printf '\nPhase 6 failed. Do not commit generated outputs.\n'
  if [[ -f "$OUT/phase6_review_bundle.zip" ]]; then
    printf 'Upload: %s/phase6_review_bundle.zip\n' "$OUT"
  else
    printf 'Upload /tmp/phase6_market_information.log and generated files.\n'
  fi
  exit "$STATUS"
fi

printf '\nPhase 6 passed. Inspect before committing:\n'
printf '  %s/phase6_report.md\n' "$OUT"
printf '  %s/phase6_integrity_checks.csv\n' "$OUT"
printf '  %s/phase6_review_bundle.zip\n' "$OUT"
