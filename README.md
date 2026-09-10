# MSc Weather Forecasting and Polymarket

This repository contains the code and outputs used for the empirical analysis in my MSc Financial Mathematics dissertation.

The analysis uses Hong Kong Observatory daily maximum temperature observations, ECMWF deterministic forecasts and historical Polymarket prices. The weather history covers 16 March 2024 to 15 March 2026. The market development period covers 16 March to 30 June 2026, followed by external evaluation from 1 July to 31 August 2026.

## Main folders

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

Other directories contain earlier project work and are not needed to reproduce the final results.

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

## Reproduction

From the repository root, run the main pipeline checks with:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

Run the trading comparison checks with:

```bash
bash scripts/trading_contrast_extension/reproduce_extension.sh audit
```

A full rebuild of the main pipeline is available with:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The full rebuild may require access to the external data sources used in the project.

## Main outputs

The main dissertation outputs are stored in:

```text
outputs/final_pipeline/thesis/generated/numbers.tex
outputs/final_pipeline/thesis/tables/
outputs/final_pipeline/reporting/final_thesis_claims_register.csv
outputs/trading_contrast_extension/thesis/
```

Some trading output filenames retain earlier internal labels. `fixed` refers to the conservative strategy and `taec` refers to the multi-contract strategy.

## Version references

The main empirical versions are recorded by the following Git tags:

```text
msc-final-pipeline-final
msc-trading-contrast-extension-final
```

The first tag records the completed March to August empirical pipeline. The second records the completed trading comparison.
