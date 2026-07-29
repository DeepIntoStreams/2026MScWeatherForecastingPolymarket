# Phase 22 Results Evidence

## Benchmark ordering

The chronological benchmark comparison establishes the following mean date CRPS
ordering: raw point forecast, static Gaussian, RBF GP and Matern-3/2 GP. The key
values are recorded in `phase22_key_metrics.csv`. The static Gaussian produces
a large improvement over the uncorrected deterministic forecast. The Matern GP
then improves further on the static benchmark. This directly answers whether
the GP genuinely adds value beyond simple local correction.

The result must not be written only as an aggregate ranking. Phase 18 shows that
the Matern GP beats the static Gaussian in all four decision rules but only three
of four chronological validation blocks. The first block favours the static
benchmark. The GP advantage is therefore persistent across rules but not uniform
through time.

## Deterministic error structure

Phase 17 shows a strong positive deterministic forecast error under the
HKO-minus-forecast convention. Most deterministic-error sum of squares is
associated with target-date variation, while the decision-rule main component
is very small. This indicates that shared weather-state error dominates the
small differences between decision times. Rule-specific post-processing remains
reasonable because the rule-level scales and forecast vintages differ, but the
thesis should not claim that decision lead time alone explains most error.

## Predictive diagnostics

Phase 19 prevents the CRPS improvement from being mistaken for complete
probabilistic adequacy. Central intervals under-cover at important nominal
levels, standardised residuals retain substantial lag-one dependence, and the
conditional-variance regression retains evidence of remaining structure for
the Matern GP. Quantile calibration is nevertheless better for Matern than RBF.
The correct conclusion is that the Matern GP is the better of the fitted GP
families and improves the benchmark, but it does not exhaust local forecast
error structure.

## GP versus Polymarket

On the June exact-common-support sample, Polymarket has lower binary and
categorical proper scores than the weather-only GP. This is the economically
important negative result: the weather-only post-processing model does not
dominate the market.

## Forecast combination

The development-selected convex pool assigns approximately half its weight to
the GP and half to the market. In June, the pool improves all four reported
proper scores relative to the GP. It nevertheless worsens all four scores
relative to the normalised market distribution. The post-hoc June oracle assigns
zero weight to the GP. The combination exercise therefore does not support a
claim that the GP contributes robust incremental information beyond the market
in June. It does show that the development period contained apparent
complementarity that did not persist strongly enough out of sample.

## Reproducibility result

The clean-environment replay passes for all six completion phases. The evidence
pack should cite the 116-artifact comparison and zero finite numerical replay
error in the reproducibility subsection or appendix.
