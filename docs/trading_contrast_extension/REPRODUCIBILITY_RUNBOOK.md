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

## Clean-generated-state replay requirement

The final clean-clone audit recreates the repository state that existed immediately before Stage 2 was first run: Stage 1 remains available, while generated Stage 2-6/thesis/release outputs are temporarily removed from the Stage-2 discovery surface.

This is necessary because the Stage-2 builder performs repository-aware schema discovery. Replaying it while its own later generated CSV outputs are still present can create a self-discovery feedback path and alter regenerated artefacts even though all scientific acceptance tests continue to pass.

The replay therefore records the committed Stage 2-5 semantic manifest, temporarily preserves closure artefacts, removes post-Stage-1 generated extension outputs, rebuilds Stage 2 with the explicit frozen RBF provenance repair, reruns Stages 3-5, restores the closure artefacts, reruns all regression tests, and requires the Stage 2-5 semantic manifest to match the committed release.

This is a release-engineering safeguard only. It changes no model, probability, strategy, threshold, cost assumption, statistical test or thesis result.
