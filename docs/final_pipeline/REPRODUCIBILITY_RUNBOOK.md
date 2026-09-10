# Reproducibility runbook

## Main check

From the repository root:

```bash
git checkout msc-final-pipeline-final
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

This checks the recorded configuration, generated outputs and tests without reselecting models or trading parameters.

## Full rebuild

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The main stage order is:

1. HKO target construction;
2. ECMWF deterministic forecast reconstruction;
3. residual panel construction;
4. probabilistic weather modelling;
5. Polymarket contract and probability construction;
6. scoring and market comparison;
7. conservative trading and forecast sensitivity analysis;
8. synthesis and reporting;
9. final checks.

The full rebuild may require access to the original external data sources.

After checking the tagged version, return to the current repository view with:

```bash
git switch main
```
