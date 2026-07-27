# Notebook 05 Continuous Distribution Calibration

## Purpose

Notebook 05 determines whether the predictive distribution selected in
Notebook 04 requires a simple dispersion adjustment.

Only development out-of-fold predictions are used. Holdout and external-test
outcomes remain inaccessible.

## Transformation

Let \(Q(\tau)\) be the predictive quantile at probability level \(\tau\), and
let \(m=Q(0.5)\) be the predictive median.

For a positive dispersion scale \(s\), define

\[
\widetilde Q_s(\tau)
=
m+s\{Q(\tau)-m\}.
\]

When \(s<1\), the distribution contracts around its median. When \(s>1\), the
distribution expands. When \(s=1\), the original distribution is unchanged.

## Why this transformation is used

The transformation has four useful properties.

1. It changes only predictive dispersion.
2. It leaves the predictive median unchanged.
3. It preserves quantile order for every positive scale.
4. It introduces only one transparent calibration parameter.

This is preferable to a high-dimensional calibration procedure given the
number of available development dates.

## Candidate scales

Seven scales are declared before selection:

\[
0.50,\ 0.75,\ 1.00,\ 1.25,\ 1.50,\ 1.75,\ 2.00.
\]

The grid includes substantial contraction, the identity transformation and
substantial expansion without introducing fine tuning.

## Selection

The primary score is mean date-level CRPS.

The strict winner is the scale with the smallest mean date-level CRPS.

A paired one-standard-error rule is then applied. Among scales whose paired
date-level CRPS difference from the strict winner is no greater than one
standard error, the scale closest to one is selected.

This rule favours the original predictive distribution unless the development
evidence supports a material adjustment.

It is a model-selection rule rather than a formal statistical-significance
test.

## Secondary diagnostics

Empirical coverage and average width are reported for central 50 per cent,
80 per cent and 90 per cent intervals.

These diagnostics help interpret underdispersion or overdispersion, but they
do not determine the selected scale. CRPS remains the single proper scoring
criterion used for selection.

## Separation from event-probability calibration

This stage calibrates the continuous temperature distribution.

Any later regularisation of probabilities over the eleven-event Polymarket
partition is a separate operation. The two procedures must not be described as
one undifferentiated calibration step.

## Evidential boundary

Notebook 05 does not access:

- holdout outcomes;
- June external-test outcomes;
- Polymarket prices;
- trading returns.

The selected dispersion scale is locked before those stages begin.
