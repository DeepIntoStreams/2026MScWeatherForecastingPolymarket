# Main empirical pipeline

The main March to August analysis is organised under `src/final_pipeline/`, with configuration, scripts, documentation and outputs in the corresponding `final_pipeline` directories.

## Suggested reading order

1. `config/final_empirical_config.json`
2. `docs/final_pipeline/methodology.md`
3. `docs/final_pipeline/weather_models.md`
4. `docs/final_pipeline/market_books.md`
5. `docs/final_pipeline/trading.md`
6. `docs/final_pipeline/synthesis.md`

## Reproduction

The recorded version is tagged `msc-final-pipeline-final`.

```bash
git checkout msc-final-pipeline-final
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

The main numerical outputs are stored in:

```text
outputs/final_pipeline/thesis/generated/numbers.tex
outputs/final_pipeline/thesis/tables/
outputs/final_pipeline/reporting/final_thesis_claims_register.csv
```
