# Final HKO–ECMWF residual panel

## Purpose

This stage joins the frozen deterministic ECMWF forecast panel to the official
HKO settlement target and creates the exact complete-case samples used by all
subsequent probabilistic post-processing.

No model is fitted in this stage.

## Residual convention

For target date d and forecast-time rule r,

    residual = HKO realised maximum - ECMWF deterministic forecast

or

    R_{d,r} = T_d - \hat T_{d,r}.

The conventional forecast error is therefore

    forecast error = forecast - realised value = -residual.

The raw deterministic diagnostics report both conventions explicitly.

## Empirical periods

The final non-overlapping split is frozen as follows.

### Weather-history training

16 March 2024 to 15 March 2026.

This period is weather-only. It precedes the market-development sample and is
the historical residual sample available to later weather post-processing.

### Market development

16 March 2026 to 30 June 2026.

June remains part of development.

This sample may be used for methodology selection and market/trading
development, but it is not part of the external July-August validation sample.

### External validation

1 July 2026 to 31 August 2026.

No information from this period may be used to select or tune a methodology
whose performance is reported as external validation.

## Admissibility

Every theoretical target-date / forecast-time key remains in the master panel.

A residual is usable if and only if:

1. the final ECMWF panel marks the forecast as supported;
2. the official HKO target is available;
3. the deterministic daily maximum is non-missing.

Unsupported forecasts are never imputed.

A target awaiting official settlement publication is retained but has no
residual until the HKO observation becomes available.

## GP-ready raw variables

The panel stores the four raw covariates later used by each forecast-time GP:

1. deterministic ECMWF daily maximum;
2. seasonal sine;
3. seasonal cosine;
4. calendar-day index.

The response is the HKO-minus-ECMWF residual.

These variables are not standardised at this stage. Standardisation must occur
inside the appropriate training fold to avoid information leakage.

## Raw deterministic diagnostics

The stage reports, separately by forecast time and empirical period:

- sample size;
- mean forecast and observation;
- residual mean;
- conventional forecast bias;
- MAE;
- RMSE;
- median absolute error;
- residual standard deviation;
- residual quantiles;
- maximum absolute error;
- forecast/observation correlation.

Monthly error summaries are also produced.

Pairwise forecast-time comparisons use common target dates only, preventing
different support composition from being mistaken for genuine forecast-time
performance differences.

## Current 31 August state

If HKO has not yet published the completed 31 August 2026 daily maximum, the
pipeline reports `PASS_PENDING_HKO_FINAL_DATE`.

This is not an imputed or provisional settlement value.

After HKO publication, rerunning the HKO stage followed by this residual stage
automatically converts the external-validation residual panel from 61 to
62 completed target dates.
