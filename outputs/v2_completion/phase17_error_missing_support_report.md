# Phase 17 Rule-Specific Deterministic Error and Missing Support

## Status

PASSED

## Connection to Phase 16

Phase 16 established that the static rule-specific Gaussian correction materially improves on the raw deterministic forecast, and that the Matérn-3/2 GP improves further on the static correction. Phase 17 now identifies how the raw deterministic errors differ across decision rules and documents exactly where the 37 market-period forecast keys are unavailable.

## Deterministic-error definition

For target date `d` and decision rule `r`, the deterministic error is

`e_{d,r} = HKO realised daily maximum - deterministic forecast daily maximum`.

A positive value therefore means that the deterministic forecast underpredicted the realised HKO maximum.

## Rule-specific results over the 730-date weather-only period

| Decision rule | Mean error (°C) | MAE (°C) | RMSE (°C) | SD (°C) | Underforecast rate |
|---|---|---|---|---|---|
| 24h_prior | 1.4444 | 1.7359 | 2.1172 | 1.5491 | 0.8041 |
| 12h_prior | 1.4227 | 1.6742 | 2.0509 | 1.4782 | 0.8288 |
| 6h_prior | 1.4336 | 1.6785 | 2.0538 | 1.4718 | 0.8315 |
| event_day_open | 1.4179 | 1.6316 | 1.9868 | 1.3927 | 0.8342 |

- Lowest MAE: `event_day_open` at 1.631644 °C.
- Highest MAE: `24h_prior` at 1.735890 °C.
- Largest mean underprediction: `24h_prior` at 1.444384 °C.
- Rule-specific bootstrap intervals, quantiles, tail shape and accuracy rates are stored in `phase17_rule_error_summary.csv`.

## Matched rule comparisons

Each pairwise comparison uses the same 730 target dates. Signed-error differences measure relative bias; absolute-error differences measure relative accuracy. Negative absolute-error differences favour the first rule.

| First rule | Second rule | Signed difference (°C) | Absolute-error difference (°C) | 95% lower | 95% upper |
|---|---|---|---|---|---|
| 24h_prior | 12h_prior | 0.0216 | 0.0616 | 0.0148 | 0.1075 |
| 24h_prior | 6h_prior | 0.0108 | 0.0574 | 0.0115 | 0.1033 |
| 24h_prior | event_day_open | 0.0264 | 0.1042 | 0.0518 | 0.1571 |
| 12h_prior | 6h_prior | -0.0108 | -0.0042 | -0.0163 | 0.0075 |
| 12h_prior | event_day_open | 0.0048 | 0.0426 | -0.0021 | 0.0864 |
| 6h_prior | event_day_open | 0.0156 | 0.0468 | 0.0021 | 0.0901 |

## Error-structure decomposition

- Target-date component: 91.9340% of total deterministic-error sum of squares.
- Decision-rule component: 0.0048%.
- Date-by-rule interaction and remaining cell variation: 8.0612%.
- This is a descriptive balanced decomposition. It does not treat the interaction term as an independently replicated error variance.
- Pearson and Spearman cross-rule correlations are in `phase17_rule_error_correlations.csv`.
- Friedman rank diagnostics are reported only descriptively because serial dependence across dates is examined later.

## Validation-block stability

- The 365 chronological validation dates are divided into the same four blocks used for GP validation.
- Sixteen rule-by-block deterministic-error summaries are stored in `phase17_error_by_validation_block.csv`.
- These results provide the raw-forecast component needed for the joint model and validation-block comparison in Phase 18.

## Exact missing-support accounting

- Settlement and market dates: 103.
- Theoretical date-rule keys: 412.
- Certified supported date-rule keys: 375 across 102 dates.
- Unsupported date-rule keys: 37.
- Unsupported development-period keys: 36.
- Unsupported June keys: 1.
- Dates with complete four-rule forecast absence: 1.
- Dates with partial rule-specific absence: 16.
- Dates with any certified forecast support: 102.
- Dates with complete four-rule support: 86.
- Every derived missing key exactly matches the Phase 8 missing-support registry.
- No missing forecast has been imputed.

## Missing-key classification

Every unsupported key is classified by date, rule, sample period, complete-date versus partial-rule absence, documented Phase 8 reason text and broad technical reason category. The full registry is `phase17_missing_key_registry.csv`; aggregated patterns are in `phase17_missing_pattern_summary.csv`.

The classification does not claim that the missingness is statistically random. Forecast accuracy cannot be observed for a key whose deterministic forecast is absent. Phase 17 therefore reports the operational missingness structure and preserves exact common support rather than attempting to estimate unavailable errors.

## Thesis-facing interpretation

The Phase 16 gain from raw point forecast to static Gaussian correction is consistent with a substantial systematic local error in the deterministic forecast. Phase 17 separates the part shared by all rules on a target date from smaller rule-specific and date-by-rule components. This provides the empirical rationale for rule-specific residual post-processing while avoiding the stronger claim that decision lead time alone explains all residual variation.

The 37 unsupported market-period keys are an archive and support limitation, not observations to be reconstructed statistically. Model, market and trading comparisons must continue to use explicitly defined common-support samples.

## Closed Phase 14 gaps

- G07: rule-specific deterministic error.
- G12: missing forecast support.

## Evidential boundary

Phase 17 does not refit a GP, alter the frozen Phase 16 comparison or introduce a forecast imputation rule. Bootstrap intervals resample target dates and are descriptive under the current dependence assumptions. More detailed dependence, coverage and heteroskedasticity diagnostics remain for Phase 19.
