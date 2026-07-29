# Version 2 Reproducibility Instructions

## Clean replay

```bash
cd ~/Desktop/2026MScWeatherForecastingPolymarket
bash tools/v2_completion/reproduce_v2_completion.sh
```

The command creates a fresh local Git clone at the certified Phase 20 commit, creates a separate virtual environment, deletes the clone's generated Phase 15-20 artifacts, reruns the six empirical engines and tests, and compares the regenerated artifacts with the certified outputs.

## Dependencies

- `requirements-v2-completion.txt` pins the directly used Python packages.
- `environment-v2-completion.yml` provides a minimal Conda environment.
- `outputs/v2_completion/phase21_package_freeze.txt` records the complete replay package stack.
- `outputs/v2_completion/phase21_pip_check.txt` records dependency consistency.

## Frozen data boundary

The replay deliberately makes no live Open-Meteo, HKO or Polymarket request. The tracked and hashed historical panels are the frozen numerical inputs because remote archives and endpoints can change.

## Verification rules

CSV outputs are compared structurally and numerically. JSON specifications are compared after removing dynamic provenance fields. Markdown is compared after path and timestamp normalisation. PNG figures are compared at pixel level, while PDFs must regenerate as non-empty files.
