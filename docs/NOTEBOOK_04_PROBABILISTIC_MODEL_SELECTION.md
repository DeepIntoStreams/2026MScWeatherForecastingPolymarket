# Notebook 04 Probabilistic Model Selection

## Objective

Notebook 04 selects a probabilistic post-processing specification for the HKO
daily maximum temperature.

The statistical target is the conditional distribution of the future HKO
daily maximum given information available at the applicable decision time.

## Candidate families

Nine numerical candidates represent five conceptual model families.

### Raw deterministic forecast

The deterministic forecast is represented by a point mass. This is the naive
benchmark.

### Mean residual correction

The mean historical residual is added to the deterministic forecast.

The pooled version uses all training residuals. The rule-specific version uses
only residuals from the same decision rule.

These remain point forecasts represented as degenerate distributions.

### Empirical residual distribution

The empirical residual distribution is shifted by the deterministic forecast.

This directly converts a deterministic forecast into a predictive distribution
without imposing a parametric residual law.

Pooled and rule-specific variants are compared.

### Gaussian process residual model

A Gaussian process is a Bayesian probability model over an unknown residual
function.

The input is standardised calendar time. A separate model is fitted for each
decision rule.

The covariance function is:

constant covariance multiplied by either an RBF or Matérn 3/2 covariance,
plus a white-noise covariance term.

The RBF covariance assumes a very smooth latent residual function. The
Matérn 3/2 covariance permits rougher variation. They are alternative prior
smoothness assumptions.

These covariance kernels must not be confused with probability kernels over
temperature-event sets.

### CatBoost quantile regression

CatBoost directly estimates five conditional residual quantiles.

The five estimated quantiles are interpolated onto the 99-quantile grid.
The pooled version includes a decision-rule code. The rule-specific version
fits a separate model for each rule.

CatBoost is included as a flexible nonlinear comparator rather than as the
default preferred model.

## Expanding out-of-fold construction

For each development fold:

1. all training dates precede all validation dates;
2. all rows from one settlement date remain together;
3. only warm-up and earlier development outcomes enter model fitting;
4. holdout and external outcomes remain inaccessible.

## CRPS

The continuous ranked probability score evaluates the complete predictive
distribution.

It has the same physical unit as the target temperature. It rewards both
concentration and calibration.

For a predictive quantile function Q and outcome y:

CRPS equals twice the integral over probability level tau of the quantile loss
of y minus Q(tau).

The implementation approximates this integral on the 99 equally spaced
quantile levels from 0.01 to 0.99.

## Primary aggregation

CRPS is first calculated for each available date-rule observation.

The scores are then averaged within settlement date. The primary model score
is the mean of these date-level values. This gives each settlement date equal
weight and respects the declared uncertainty unit.

## Parsimony rule

The strict score winner is the candidate with the smallest mean date-level
CRPS.

The final selected model uses a paired one-standard-error rule:

1. calculate each candidate's date-level CRPS difference from the strict
   winner;
2. calculate the standard error of that paired difference;
3. retain candidates whose mean difference is no greater than one standard
   error;
4. select the least complex candidate among those retained.

This is a model-selection rule, not a formal statistical-significance claim.

## Evidential boundary

Notebook 04 selects the probabilistic specification only.

It does not evaluate:

- the locked holdout;
- June temporal transfer;
- probability calibration;
- market-price comparison;
- trading profitability.

Those stages begin only after the selected specification is recorded.
