# Weather Forecasting and Polymarket Trading

This branch contains the clean empirical implementation supporting the final
MSc Financial Mathematics dissertation.

## Research questions

1. Can deterministic weather information be converted into a useful
   predictive distribution for the official HKO daily maximum?
2. Do the resulting event probabilities compete with the Polymarket book?
3. Does model–market disagreement produce persistent reduced-form trading
   value?

## Empirical design

- Weather training may use compatible forecast–HKO dates without Polymarket
  contracts.
- Model and probability choices are selected using pre-August chronological
  development data.
- August 2026 is reserved as the principal external evaluation period.
- Settlement date is the uncertainty and resampling unit.
- The final model families are raw deterministic, mean residual, empirical
  residual, Gaussian process regression and CatBoost quantile regression.

## Canonical workflow

The final reader-facing notebooks are maintained in `notebooks/final/`.

Reusable implementation belongs in `src/weather_polymarket/`.

Final thesis tables and figures are generated under `outputs/`.

## Historical work

The complete exploratory and superseded notebook history is preserved on:

`archive/17j-plus-18n-18y-20260726`

The historical branch is not required to understand or reproduce the final
analysis.

## Current status

The clean empirical rebuild has been initialised. Final numerical results
will be generated only after the Gaussian-process audit, expanded training
panel and locked August external evaluation are complete.
