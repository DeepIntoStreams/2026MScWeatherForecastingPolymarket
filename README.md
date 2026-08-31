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
