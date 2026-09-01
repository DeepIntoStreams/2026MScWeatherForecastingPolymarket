# MSc Weather Forecasting and Polymarket

## Final reproducible empirical branch

This branch contains the final empirical pipeline accompanying the MSc Financial
Mathematics dissertation.

**Authoritative empirical period**

- weather history: 16 March 2024 to 15 March 2026;
- market development: 16 March 2026 to 30 June 2026;
- untouched external validation: 1 July 2026 to 31 August 2026.

## Core empirical sequence

HKO observations
→ ECMWF deterministic forecasts
→ forecast residuals
→ Static Gaussian / GP post-processing
→ eleven-contract temperature probabilities
→ Polymarket comparison
→ market-development selection
→ untouched July-August validation
→ simple trading attribution
→ robustness
→ thesis-ready tables and figures.

## Authoritative locations

- empirical contract: `config/final_empirical_config.json`
- code: `src/final_pipeline/`
- methodology: `docs/final_pipeline/methodology.md`
- data dictionary: `docs/final_pipeline/data_dictionary.md`
- reproducibility: `docs/final_pipeline/reproducibility.md`
- generated outputs: `outputs/final_pipeline/`

Older repository material is retained only as historical/audit evidence while the
final implementation is rebuilt. It is not an authoritative input into the submitted
March-August results.

See `docs/final_pipeline/authoritative_scope.md` for the precise source policy.

<!-- FINAL_PIPELINE_ENTRY_START -->

## Final March--August MSc empirical pipeline

The authoritative dissertation empirical implementation is on branch
`final-march-august-reproducible-pipeline`.

Current release state: **RELEASE_CANDIDATE_PENDING_2026_08_31_SETTLEMENT**.

Examiner entry point:

`docs/final_pipeline/EXAMINER_README.md`

One-command audit replay:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

The final empirical source hierarchy is:

1. `outputs/final_pipeline/thesis/generated/numbers.tex`
2. `outputs/final_pipeline/thesis/tables/`
3. `outputs/final_pipeline/reporting/final_thesis_claims_register.csv`
4. authoritative CSV/JSON outputs under `outputs/final_pipeline/`
5. pipeline implementation under `src/final_pipeline/`

Do not use historical branches or obsolete pre-final outputs as thesis
numerical sources.

<!-- FINAL_PIPELINE_ENTRY_END -->
