# Phase 7: Gaussian-Process Validation Distributions

## Purpose

Phase 7 fits and evaluates two Gaussian-process residual models:

- the squared-exponential, or RBF, covariance kernel;
- the Matérn covariance kernel with smoothness parameter \(3/2\).

A separate model is fitted for each decision rule and each chronological
training fold.

## Forecast-error response

For target date \(d\) and decision rule \(r\), the response is

\[
R_{d,r}
=
T_d^{\mathrm{HKO}}
-
\widehat T_{d,r}^{\mathrm{det}}.
\]

For a new input \(x_*\), the Gaussian process produces

\[
R_*\mid \mathcal D
\sim
\mathcal N\left(
m_*(x_*),
s_*^2(x_*)
\right).
\]

The corresponding temperature distribution is

\[
T_*
\mid \mathcal D
\sim
\mathcal N\left(
\widehat T_*^{\mathrm{det}}+m_*(x_*),
s_*^2(x_*)
\right).
\]

## Covariance functions

The RBF covariance is

\[
k_{\mathrm{RBF}}(x,x')
=
\sigma_f^2
\exp\left(
-\frac{\lVert x-x'\rVert^2}{2\ell^2}
\right).
\]

The Matérn \(3/2\) covariance is

\[
k_{\mathrm{Mat32}}(x,x')
=
\sigma_f^2
\left(
1+\frac{\sqrt{3}\lVert x-x'\rVert}{\ell}
\right)
\exp\left(
-\frac{\sqrt{3}\lVert x-x'\rVert}{\ell}
\right).
\]

Both models include an estimated white-noise variance.

## Fitting design

There are:

- four chronological folds;
- four decision rules;
- two covariance kernels.

This gives 32 fitted Gaussian-process models.

Kernel parameters are estimated by maximising the Gaussian-process log
marginal likelihood using only the training rows of each fold. No future
validation residual enters model fitting.

The target is normalised internally using the corresponding training
sample. The four inputs have already been standardised using training
rows only in Phase 6.

## Validation distributions

The 365 validation dates produce:

- 1,460 date-rule forecasts per covariance kernel;
- 2,920 validation prediction rows in total;
- 99 temperature quantiles from the first to the ninety-ninth percentile
  for each prediction.

## Evaluation

CRPS is the primary continuous-distribution score. Additional diagnostics
include:

- negative log score;
- corrected point-forecast MAE and RMSE;
- probability integral transform values;
- 50%, 80% and 90% central interval coverage;
- date-level paired comparison of RBF and Matérn \(3/2\).

The settlement date remains the principal uncertainty unit. Kernel
comparisons are therefore also recorded after averaging the four decision
rules within each date.

## Evidential boundary

Phase 7 does not access market prices or Polymarket outcomes. It does
not select event-probability calibration parameters or trading rules.

The kernel summary gives a descriptive CRPS ranking, but final kernel
selection is deferred to the next phase.

## Principal outputs

The validation forecast distributions are stored in:

outputs/v2/diagnostics/07_gp_validation_predictions.csv

The fitted-model ledger is stored in:

outputs/v2/diagnostics/07_gp_model_fit_ledger.csv

The main kernel comparison is stored in:

outputs/v2/final_tables/07_gp_kernel_validation_summary.csv
