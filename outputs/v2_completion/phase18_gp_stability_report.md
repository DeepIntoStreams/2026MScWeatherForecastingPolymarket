# Phase 18 Rule and Validation-Block GP Stability

## Status

PASSED

## Purpose

Phase 16 established the aggregate ordering of the raw point forecast, static Gaussian correction, RBF GP and Matérn-3/2 GP. Phase 18 tests whether that ordering is concentrated in a single decision rule or validation period and reconciles fold-specific GP hyperparameters with the saved full-history Matérn models.

## Exact comparison support

- Validation dates: 365.
- Decision rules: 4.
- Chronological validation blocks: 4.
- Models: raw point, static Gaussian, RBF GP and Matérn-3/2 GP.
- Model rows: 5,840.
- Every date-rule key contains all four models.
- Paired uncertainty intervals resample target dates 10,000 times.

## Exact replay of the 32 Phase 7 fold fits

The fold-specific fitted model objects were not persisted in Phase 7. Phase 18 therefore reruns the original Phase 7 source in an isolated temporary copy of the repository while instrumenting scikit-learn's GaussianProcessRegressor.fit method. The replay does not alter the certified repository outputs.

- Replayed fold models: 32.
- Reconciled numeric prediction columns: 119.
- Maximum absolute replay-versus-certified prediction discrepancy: 0.000e+00.
- Every replayed fit is mapped one-to-one to a certified fold, rule and kernel through its training-response hash and recorded date range.
- Hyperparameter stability is reported only after the replay reproduces the frozen Phase 7 predictions within the stated numerical tolerances.

## Overall paired results

- Matérn-3/2 minus static Gaussian CRPS: -0.048415 °C with 95% date-bootstrap interval [-0.070800, -0.026407].
- Matérn-3/2 minus RBF CRPS: -0.014221 °C with 95% date-bootstrap interval [-0.020771, -0.007946].
- Every difference is first-model minus second-model CRPS; negative favours the first model.

## Matérn-3/2 improvement over the static Gaussian benchmark by rule

| Decision rule | Mean difference (°C) | 95% lower | 95% upper |
|---|---|---|---|
| 24h_prior | -0.03109 | -0.04740 | -0.01550 |
| 12h_prior | -0.05459 | -0.08001 | -0.02857 |
| 6h_prior | -0.04746 | -0.07377 | -0.02187 |
| event_day_open | -0.06051 | -0.08715 | -0.03407 |

## Matérn-3/2 improvement over the static Gaussian benchmark by validation block

| Validation block | Mean difference (°C) | 95% lower | 95% upper |
|---|---|---|---|
| fold_01 | 0.03480 | 0.01065 | 0.05994 |
| fold_02 | -0.06124 | -0.09412 | -0.03030 |
| fold_03 | -0.04147 | -0.10621 | 0.01826 |
| fold_04 | -0.12491 | -0.16330 | -0.08871 |

## Stability counts

- Matérn-3/2 has lower mean CRPS than static Gaussian in 4 of 4 decision rules.
- Matérn-3/2 has lower mean CRPS than static Gaussian in 3 of 4 validation blocks.
- Matérn-3/2 has lower mean CRPS than static Gaussian in 12 of 16 rule-by-block cells.
- Matérn-3/2 has lower mean CRPS than RBF in 10 of 16 rule-by-block cells.
- Matérn-3/2 is the lowest-CRPS model in 9 of 16 cells, with mean rank 1.625.

These counts are descriptive stability diagnostics. A cell-level sign does not by itself establish independent statistical evidence because blocks and decision rules share target dates and underlying weather conditions.

## GP hyperparameter stability

- Fold models reconciled: 32, comprising two kernel families, four rules and four chronological folds.
- Saved full-history models reconciled: 4 selected Matérn-3/2 models.
- Largest rule-specific Matérn length-scale coefficient of variation across folds: 0.412958.
- Largest rule-specific Matérn WhiteKernel-noise coefficient of variation across folds: 0.064230.
- Full-history Matérn length scale lies within the corresponding four-fold range for 1 of 4 rules.
- Full-history Matérn noise level lies within the corresponding four-fold range for 1 of 4 rules.
- Exact fold and full-fit values are stored in the Phase 18 hyperparameter registries; no rounded report value is used for calculation.

## Interpretation

The GP contribution should not be described only through the aggregate Phase 16 mean. Phase 18 separates performance by decision rule and chronological block, showing where the Matérn improvement over static correction is persistent and where it weakens or reverses. This is the appropriate evidential basis for claiming conditional residual structure rather than merely a better aggregate average.

Fold-to-fold movement in the fitted signal variance, length scale and WhiteKernel noise quantifies estimation sensitivity. The comparison with the four saved full-history models shows whether the final fitted parameters are consistent with the ranges observed under chronological validation.

## Closed Phase 14 gaps

- G08: rule and validation-block model results.
- G09: GP hyperparameter stability.

## Evidential boundary

Phase 18 does not refit, reselect or modify any certified GP. June observations and market prices do not enter the weather-only model comparison. Bootstrap intervals use target dates as the resampling unit and remain descriptive under the current serial-dependence assumptions. Predictive coverage, calibration, heteroskedasticity and residual dependence are reserved for Phase 19.
