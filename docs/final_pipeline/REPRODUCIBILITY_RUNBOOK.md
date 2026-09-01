# Reproducibility runbook

## Audit replay

From the repository root:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

This performs no model reselection and no data mutation. It rebuilds the
release metadata and runs all `tests/final_pipeline/test_*.py` tests.

## Full empirical rebuild

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The intended stage order is:

1. HKO target acquisition/certification;
2. ECMWF deterministic forecast reconstruction;
3. residual-panel construction;
4. probabilistic weather-model estimation;
5. Polymarket event-book reconstruction;
6. scoring and market comparison;
7. frozen-policy trading and forecast-risk analysis;
8. synthesis;
9. thesis reporting;
10. release verification.

Live endpoint availability can affect acquisition in a future rerun.
Development/external allocations and all methodological rules are frozen in
`config/final_empirical_config.json`.

## 31 August

If the final target is still pending, use:

```bash
bash scripts/final_pipeline/refresh_aug31.sh
```

The refresh must not change:

- Matérn-3/2 weather-kernel selection;
- GP pool weight 0.188;
- 24h_prior trading rule;
- threshold 0.15.
