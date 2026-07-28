# Phase 6: Chronological Gaussian-Process Training Design

## Purpose

Phase 6 defines the training and validation structure for the
Gaussian-process residual models.

No model is fitted in this phase.

## Response variable

For target date \(d\) and decision rule \(r\), the response is

\[
R_{d,r}
=
T_d^{\mathrm{HKO}}
-
\widehat T_{d,r}^{\mathrm{det}}.
\]

The Gaussian process therefore models systematic errors in the
deterministic forecast rather than the temperature level directly.

## Training and validation dates

The 730 weather-only dates are divided as follows:

- the first 365 dates form the initial training period;
- the next 91 dates form validation block 1;
- the next 91 dates form validation block 2;
- the next 91 dates form validation block 3;
- the final 92 dates form validation block 4.

The training period expands after each validation block. Earlier
validation dates may therefore enter the training data of a later fold,
but no date enters training before its own validation prediction has
been produced.

Every date in the second year appears in exactly one validation block.

## Why this design is used

A full annual cycle is available before the first validation block.
This gives the initial model observations from every season.

The four consecutive validation blocks then assess whether the model
continues to perform as time advances. The design respects chronology
and avoids using future residuals when producing a validation
prediction.

## Gaussian-process inputs

The four inputs are:

1. elapsed calendar time in years;
2. annual sine;
3. annual cosine;
4. deterministic daily maximum-temperature forecast.

Calendar time allows gradual change across the two-year period. The
sine and cosine terms represent annual seasonality without a break
between December and January. The deterministic forecast allows the
residual distribution to vary with the forecast temperature level.

A separate model will be fitted for each decision rule. The rule labels
are therefore not treated as continuous numerical inputs.

## Standardisation

For every fold and decision rule, feature means and standard deviations
are estimated using the training rows only. The same values are then
used to transform that fold's validation rows.

This prevents validation information from affecting the model inputs.

## Candidate covariance kernels

The next modelling phase will compare:

- the squared-exponential, or RBF, covariance kernel;
- the Matérn covariance kernel with smoothness parameter \(3/2\).

These are covariance kernels for Gaussian-process regression. They are
not probability kernels over temperature events.

## Evidential boundary

Phase 6 does not access market prices or Polymarket outcomes. It does
not fit a Gaussian process, estimate kernel parameters, select a model,
calibrate event probabilities or calculate trading returns.

## Principal outputs

The raw design panel is:

outputs/v2/diagnostics/06_gp_raw_design_panel.csv

The fold-specific standardised matrix is:

outputs/v2/diagnostics/06_gp_fold_matrix_panel.csv

The fold definitions are:

outputs/v2/diagnostics/06_gp_fold_summary.csv

## Next stage

Phase 7 fits the rule-specific RBF and Matérn Gaussian-process residual
models within the four certified chronological folds and constructs
out-of-fold predictive distributions.
