# Weather Forecasting and Polymarket Trading

This repository contains the code and outputs used for the empirical analysis in my MSc Financial Mathematics dissertation.

The analysis uses Hong Kong Observatory daily maximum temperature observations, ECMWF deterministic forecasts and historical Polymarket prices. The weather history covers 16 March 2024 to 15 March 2026. The market development period covers 16 March to 30 June 2026, followed by external evaluation from 1 July to 31 August 2026.

## Repository structure

The final weather, market comparison and trading pipeline is contained in:

```text
config/final_empirical_config.json
src/final_pipeline/
scripts/final_pipeline/
outputs/final_pipeline/
docs/final_pipeline/
```

The additional comparison between the conservative and multi-contract trading strategies is contained in:

```text
config/trading_contrast_extension/
src/trading_contrast_extension/
scripts/trading_contrast_extension/
outputs/trading_contrast_extension/
docs/trading_contrast_extension/
```

Supporting files used by the final analysis are stored under `data/`, `models/`, `environment/` and `tests/`.

The remaining notebooks, tools and earlier phase scripts record earlier stages of the project and are not required to reproduce the reported results.

## Environment

The Python environment is recorded in:

```text
environment-v2-completion.yml
requirements-v2-completion.txt
```

Using Conda:

```bash
conda env create -f environment-v2-completion.yml
conda activate 2026-msc-weather-v2
```

## Reproducing the reported results

The exact recorded versions are kept as Git tags.

For the main March to August pipeline:

```bash
git checkout msc-final-pipeline-final
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

For the trading strategy comparison:

```bash
git checkout msc-trading-contrast-extension-final
bash scripts/trading_contrast_extension/reproduce_extension.sh audit
```

A full rebuild of the main pipeline is available from the first tag:

```bash
git checkout msc-final-pipeline-final
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The full rebuild may require access to the original external data sources. Return to the current repository view with:

```bash
git switch main
```

## Main outputs

The main numerical outputs are stored in:

```text
outputs/final_pipeline/thesis/generated/numbers.tex
outputs/final_pipeline/thesis/tables/
outputs/final_pipeline/reporting/final_thesis_claims_register.csv
outputs/trading_contrast_extension/thesis/
```

Further figures, tables and intermediate outputs are stored under the corresponding output directories.

## Data sources

The analysis uses Hong Kong Observatory observations, ECMWF forecast data and historical Polymarket market data. Some source data may be subject to the terms of the original provider.

## Version references

The two main empirical versions used in the dissertation are:

```text
msc-final-pipeline-final
msc-trading-contrast-extension-final
```

The first records the completed March to August empirical pipeline. The second records the completed trading strategy comparison.
