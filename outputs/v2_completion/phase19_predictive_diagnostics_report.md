# Phase 19 Predictive Diagnostics and Residual Structure

## Status

PASSED

## Purpose

Phase 18 showed that the Matérn-3/2 GP has lower aggregate CRPS than the static Gaussian benchmark, but its advantage varies across chronological blocks and its fitted hyperparameters move across folds. Phase 19 therefore evaluates whether the predictive distributions are calibrated and sharp, and whether standardised residuals retain temporal, cross-rule or conditional variance structure.

## Certified support

- Validation dates: 365 consecutive days.
- Decision rules: 4.
- GP families: RBF and Matérn-3/2.
- Validation rows: 2,920.
- Chronological validation blocks: 4.
- Every date-rule key contains both GP families.
- June outcomes and market prices are absent from every diagnostic.

## Code-to-output reconciliation

- Reconciliation checks passed: 8.
- Maximum Gaussian quantile reconstruction error: 2.056e-10.
- Stored predictive quantiles, PIT values, standardised residuals and available central-coverage indicators were independently reconstructed from the predictive mean and standard deviation.

## Overall central-interval calibration

| Model | Nominal | Empirical | Error | 95% lower | 95% upper | Mean width (°C) |
|---|---|---|---|---|---|---|
| RBF GP | 0.50000 | 0.44247 | -0.05753 | -0.10000 | -0.01370 | 1.93813 |
| RBF GP | 0.80000 | 0.76781 | -0.03219 | -0.06918 | 0.00342 | 3.68251 |
| RBF GP | 0.90000 | 0.86918 | -0.03082 | -0.06096 | -0.00274 | 4.72645 |
| Matérn-3/2 GP | 0.50000 | 0.46027 | -0.03973 | -0.08288 | 0.00411 | 1.96242 |
| Matérn-3/2 GP | 0.80000 | 0.78288 | -0.01712 | -0.05274 | 0.01781 | 3.72867 |
| Matérn-3/2 GP | 0.90000 | 0.88082 | -0.01918 | -0.04795 | 0.00822 | 4.78569 |

Coverage uncertainty intervals resample complete target dates 10,000 times. Negative coverage error means undercoverage.

## Overall quantile calibration

| Model | Integrated absolute error | RMSE | Maximum absolute error | Mean signed error |
|---|---|---|---|---|
| Matérn-3/2 GP | 0.01559 | 0.01883 | 0.03247 | 0.01244 |
| RBF GP | 0.02304 | 0.02852 | 0.05603 | 0.01921 |

The complete 1% to 99% reliability curves are stored in `phase19_quantile_calibration.csv`. Rule-specific curves are retained rather than inferred from the aggregate result.

## Probability integral transform diagnostics

| Model | Mean PIT | PIT variance | KS statistic | CvM statistic | 10-bin chi-square |
|---|---|---|---|---|---|
| RBF GP | 0.48090 | 0.09218 | 0.05697 | 1.16864 | 28.43836 |
| Matérn-3/2 GP | 0.48758 | 0.08916 | 0.03431 | 0.51140 | 14.10959 |

For a calibrated continuous predictive distribution the PIT reference mean is 0.5 and the reference variance is 1/12. The reported goodness-of-fit p-values use nominal independent-row reference distributions and are not interpreted as definitive tests because rules share target dates and the dates may be serially dependent.

## Standardised residual shape

| Model | Mean | SD | RMSE | Skewness | Excess kurtosis |
|---|---|---|---|---|---|
| RBF GP | -0.07449 | 1.03053 | 1.03181 | -0.01001 | -0.13838 |
| Matérn-3/2 GP | -0.05081 | 1.00496 | 1.00487 | -0.03659 | -0.08512 |

A correctly centred and scaled Gaussian predictive distribution has standardised-residual mean zero, variance one and approximately Gaussian tail shape. Rule and block decompositions are stored separately.

## Residual dependence

| Model | Residual lag-1 | 95% lower | 95% upper | Squared-residual lag-1 | 95% lower | 95% upper |
|---|---|---|---|---|---|---|
| RBF GP | 0.51476 | 0.32711 | 0.52365 | 0.21411 | 0.06124 | 0.29057 |
| Matérn-3/2 GP | 0.50645 | 0.31934 | 0.51493 | 0.22976 | 0.06949 | 0.30758 |

Lag-one uncertainty uses a circular moving-block bootstrap with 7-day blocks and 5,000 replications. Full residual, absolute-residual and squared-residual autocorrelation functions through lag 14 are stored in `phase19_autocorrelation.csv`.

## Remaining conditional variance structure

| Model | Auxiliary R² | Joint Wald | df | Cluster-robust p-value |
|---|---|---|---|---|
| RBF GP | 0.02116 | 14.04781 | 10 | 0.17082 |
| Matérn-3/2 GP | 0.02710 | 23.20617 | 10 | 0.01001 |

The auxiliary regression uses squared standardised residuals as the response. Covariates comprise standardised predictive mean and its square, standardised predictive standard deviation and its square, calendar time, seasonal sine and cosine terms, and decision-rule indicators. Covariance estimates cluster observations by target date. This tests for remaining conditional second-moment structure after dividing errors by the GP predictive standard deviation.

Quartile diagnostics in `phase19_heteroskedasticity_quartiles.csv` report residual scale and 90% coverage across predictive-uncertainty, predictive-mean and deterministic-forecast strata.

## Interpretation

Calibration and sharpness must be interpreted jointly. Narrower predictive distributions are not preferable when they materially undercover realised temperatures. Likewise, an aggregate CRPS advantage does not establish that the standardised residual sequence is independent or conditionally homoskedastic.

Phase 19 therefore separates four questions: whether nominal probabilities agree with empirical frequencies; how concentrated the predictive distributions are; whether residual location and scale resemble the Gaussian reference; and whether residual or squared-residual structure remains across dates, rules and forecast regimes.

## Closed Phase 14 gaps

- G10: predictive calibration and sharpness.
- G11: residual dependence and heteroskedasticity.

## Evidential boundary

Phase 19 does not refit or select a GP, alter any Phase 7 prediction, use June outcomes, use market prices or impute missing forecasts. Bootstrap intervals resample target dates, and lag-one dependence intervals use seven-day moving blocks. Nominal PIT and Ljung-Box p-values are retained only as familiar descriptive references; substantive conclusions should rely on effect sizes, block-bootstrap intervals, rule and block decompositions, and the date-cluster-robust auxiliary variance analysis.
