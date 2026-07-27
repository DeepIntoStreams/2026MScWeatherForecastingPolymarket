# Notebook 06 Locked Predictive Distributions

## Purpose

Notebook 06 generates predictive distributions for the holdout and June
external periods after model and calibration selection have been completed.

The notebook does not calculate forecast scores.

## Locked inputs

Two previous decisions are treated as fixed:

1. the probabilistic model selected in Notebook 04;
2. the continuous dispersion scale selected in Notebook 05.

Neither decision is reconsidered in Notebook 06.

## Final fitting sample

The locked model is fitted using all available observations from:

- the warm-up block;
- the development validation block.

Holdout and external outcomes do not enter fitting.

The model is not refitted after holdout outcomes become available.

## Prediction sample

Predictions are generated for:

- the ten-date holdout block;
- the thirty-date June external block.

The resulting prediction panel contains 159 date-rule observations over forty
settlement dates.

## Quantile representation

Each prediction is represented by 99 quantiles from 0.01 to 0.99.

The locked dispersion scale is applied around the predictive median:

\[
\widetilde Q(\tau)
=
Q(0.5)
+
s\{Q(\tau)-Q(0.5)\}.
\]

The predictive median remains unchanged.

## Prediction files

Two files are retained:

- the locked uncalibrated predictive distributions;
- the locked continuously calibrated predictive distributions.

Neither file contains realised temperatures, residuals, forecast scores,
market prices or trading returns.

## Gaussian process warnings

When the locked model is a Gaussian process, convergence warnings and learned
kernel parameters are recorded in the final fit log.

A convergence warning does not automatically invalidate a fit, but it must be
reported and interpreted in the dissertation.

## Evidential boundary

Notebook 06 performs prediction only.

It does not calculate:

- CRPS;
- coverage or sharpness results;
- event probabilities;
- categorical scores;
- comparisons with Polymarket;
- trading returns.

Those analyses begin only after the locked prediction files have been written.
