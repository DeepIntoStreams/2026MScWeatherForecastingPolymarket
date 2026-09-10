# Main empirical pipeline

The main empirical pipeline is complete through 31 August 2026.

The reported configuration uses:

- Matérn-3/2 as the selected Gaussian process kernel;
- linear probability pool weights of 0.188 for the Gaussian process and 0.812 for Polymarket;
- the 24-hour decision rule for the conservative trading strategy;
- a probability gap threshold of 0.15;
- a reference transaction cost of 0.01 per share.

The recorded version is tagged:

```text
msc-final-pipeline-final
```

The corresponding check is:

```bash
git checkout msc-final-pipeline-final
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```
