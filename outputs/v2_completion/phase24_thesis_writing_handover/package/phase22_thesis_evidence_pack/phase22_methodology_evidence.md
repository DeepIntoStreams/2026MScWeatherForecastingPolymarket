# Phase 22 Methodology Evidence

## Central empirical design

The empirical study should be written as a single chronological argument rather
than as a collection of unrelated forecasting experiments. A deterministic IFS
daily-maximum forecast is first aligned to the HKO settlement target. Its local
error is estimated from a two-year weather-only history. A rule-specific static
Gaussian correction provides the deliberately simple probabilistic benchmark.
A Gaussian process then models conditional residual structure using exactly the
feature construction, affine scaling, response transformation, observation-noise
convention and analytical Gaussian CRPS implementation reconciled in Phase 15.

The chronological validation sample contains 365 target dates, four decision
rules and four validation blocks. Raw point, static Gaussian, RBF GP and
Matern-3/2 GP predictions are evaluated on the same date-rule support. Target
date is the uncertainty and aggregation unit. This prevents four decision-rule
forecasts from being treated as four independent weather realisations.

## Data and support

The weather-only residual panel contains 730 dates and 2,920 date-rule rows.
The market and settlement universe contains 103 dates and 412 theoretical
date-rule keys. Deterministic forecast support is available for 375 keys across
102 dates. The 37 missing keys are retained as explicit archive/support
limitations and are never statistically reconstructed.

Market comparison, forecast combination and trading must therefore use the
certified exact complete-book intersection. The exact-common-support sample
contains 97 dates, 350 date-rule books and 3,850 contract-event rows. The
development period contains 67 dates and June contains 30 out-of-sample dates.

## Static probabilistic benchmark

For each decision rule, the static benchmark estimates a residual mean and
standard deviation using only the training dates available before the relevant
validation block. The deterministic forecast is shifted by the estimated local
mean error and combined with the estimated residual scale to form a Gaussian
predictive distribution. This benchmark is essential: it separates the benefit
of simple local bias-and-scale correction from the incremental contribution of
the GP.

## Gaussian-process construction

The GP should be defined at the residual level. The response is the observed HKO
daily maximum minus the deterministic forecast daily maximum. The four raw
features are calendar time, seasonal sine, seasonal cosine and deterministic
forecast daily maximum. Phase 15 verifies the exact calendar origin, 365.2425-day
year convention, seasonal position, affine feature transformation, response
normalisation and saved scikit-learn estimator configuration.

The fitted covariance is a signal kernel plus WhiteKernel observation noise.
The saved predictive standard deviation includes observation noise exactly once.
The analytical Gaussian CRPS is used for every continuous-distribution
comparison. The Matern-3/2 and RBF families are compared chronologically; the
Matern family is retained because it has the lower mean date CRPS.

## Model-market comparison and forecast combination

The weather-only GP and Polymarket are first compared as separate information
sources on exact common support. Market probabilities are normalised within each
complete contract book for categorical scoring. A single convex-pool weight is
then selected only on the 67-date development period by minimising date-balanced
categorical log score on a 0.001 grid. The selected weight is frozen before June.
Rule-specific weights and the June oracle weight are diagnostics only.

## Reproducibility

Phase 21 replays Phases 15-20 from commit `c5150fdd576f3757fcd374307367d19503fe9de9` in a clean temporary
clone and environment. Six phases are replayed and 116 artifacts are compared.
All comparisons pass and the maximum finite numerical discrepancy is zero.
This is stronger evidence than merely recording package versions: it demonstrates
that the committed code, frozen inputs and environment specification regenerate
the recorded completion results.
