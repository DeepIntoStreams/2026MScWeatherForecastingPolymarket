# Notebook 07 Locked Continuous Evaluation

## Purpose

Notebook 07 evaluates the continuous predictive distributions generated in
Notebook 06.

All model and calibration decisions were made before the holdout and June
outcomes were joined.

## Forecasts compared

Three forecasts are evaluated.

### Raw deterministic forecast

The deterministic forecast is represented as a point mass. Its CRPS is equal
to its absolute error.

### Selected uncalibrated distribution

This is the probabilistic model selected through the chronological
development out-of-fold comparison before continuous dispersion scaling.

### Selected calibrated distribution

This is the same selected model after applying the dispersion scale selected
in Notebook 05.

## Evaluation blocks

Results are reported separately for:

- the ten-date holdout block;
- the thirty-date June external block.

The two blocks are not pooled into one headline score because they serve
different empirical purposes.

The holdout measures performance immediately after development. The June block
measures transfer into a later month without model refitting.

## Primary score

The primary measure is the continuous ranked probability score.

Each predictive distribution is represented by 99 quantiles. The CRPS integral
is approximated from those quantiles.

Scores are calculated in three stages:

1. calculate CRPS for every date and decision-rule observation;
2. average the four rule-level scores within settlement date;
3. average the date-level values within each evaluation block.

This ensures that settlement date, rather than contract row, remains the
primary uncertainty unit.

## Secondary diagnostics

The following quantities are reported:

- predictive median absolute error;
- predictive median bias;
- empirical coverage of central 50 per cent intervals;
- empirical coverage of central 80 per cent intervals;
- empirical coverage of central 90 per cent intervals;
- average width of each interval.

Coverage and width are interpreted jointly. High coverage obtained through
very wide intervals does not necessarily represent useful concentration.

## Paired comparisons

Three date-level comparisons are made:

1. selected uncalibrated distribution against the raw forecast;
2. selected calibrated distribution against the raw forecast;
3. selected calibrated distribution against the uncalibrated distribution.

The paired difference is defined as left forecast CRPS minus right forecast
CRPS. A negative value favours the left forecast.

A two-sided 95 per cent interval is calculated using the standard error of the
date-level paired differences.

The interval is descriptive. It is not presented as a formal significance
test because the dates may be serially dependent and the holdout contains only
ten observations.

## Interpretation of calibration

Calibration is judged out of sample by comparing the calibrated and
uncalibrated versions of the same locked model.

An improvement on development data does not guarantee an improvement on the
holdout or June block. Any deterioration must be reported rather than hidden
through retrospective recalibration.

## Evidential boundary

Notebook 07 evaluates the continuous temperature distribution only.

It does not:

- reconstruct event probabilities;
- access Polymarket prices;
- compare the forecast with the market;
- select a trading rule;
- report trading returns.

These tasks occur only after the continuous forecast evaluation has been
completed.
