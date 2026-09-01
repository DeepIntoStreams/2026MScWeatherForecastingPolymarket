# Reproducibility runbook — trading contrast extension

From the repository root on branch `final-trading-contrast-extension`:

```bash
bash scripts/trading_contrast_extension/reproduce_extension.sh audit
```

The replay performs:

1. the canonical Stage-2 construction;
2. the explicit frozen-RBF provenance repair;
3. a corrected Stage-2 ledger rebuild;
4. Stage-3 performance/risk/Greek analytics;
5. Stage-4 dependence-aware inference;
6. Stage-5 robustness/reality checks;
7. Stage-2/3/4/5/6 regression tests.

Compressed CSV files are compared semantically after decompression so gzip container metadata cannot create a false reproducibility failure. Non-compressed tracked outputs must remain byte-identical.

Stage 1 is a frozen preregistration/protocol stage and is verified rather than re-estimated.

No external-validation result is allowed to reselect the fixed policy, TAEC threshold, primary block length, weather kernel or original final-pipeline selectors.
