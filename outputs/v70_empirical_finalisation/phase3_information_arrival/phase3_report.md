# Phase 3 — Information Arrival and Forecast Revision

Generated: `2026-07-31T23:02:35.010325+00:00`

## Overall status: **PASSED**

## Provenance

```json
{
  "bootstrap_replications": 10000,
  "bootstrap_seed": 20260801,
  "frozen_commit": "1b0900086c315588b0dc41225e41c2b5f2189bfa",
  "frozen_ref": "v2-empirical-complete",
  "frozen_tag_object": "5d48edb55074f4018d842482bab9f7bf4ab1c01e",
  "generated_utc": "2026-07-31T23:02:25.039961+00:00",
  "gp_validation_input": "outputs/v2/diagnostics/07_gp_validation_predictions.csv",
  "gp_validation_sha256": "6cf36d253393d4a752096a79b9113648bd74b69ed12f0e970c8c39346cbbf33e",
  "interpretation_boundary": "The phase measures forecast revisions between historically admissible decision rules. It does not identify the causal effect of any specific new observation, because issue cycle, forecast state and elapsed lead time change jointly.",
  "moving_block_lengths": [
    3,
    5,
    7
  ],
  "static_registry_input": "outputs/v2_completion/phase16_static_parameter_registry.csv",
  "static_registry_sha256": "671d894138a36cbb529b212c5f6afb23133f9398629e6c5383de2b2839bb8a89",
  "weather_input": "outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv",
  "weather_sha256": "14425a244abe9374c8c7a97feef68b08be54fe48a3aa1e2b43ea41b515e9ee48",
  "working_branch": "edward-v70-empirical-finalisation",
  "working_commit": "46b50a3a75a932f12c2316cea754d90fda30205a"
}
```

## Integrity checks

| check                                      | passed   | critical   | detail                                                                              |
|:-------------------------------------------|:---------|:-----------|:------------------------------------------------------------------------------------|
| weather_required_columns                   | True     | True       | missing=[]                                                                          |
| gp_required_columns                        | True     | True       | missing=[]                                                                          |
| static_registry_required_columns           | True     | True       | missing=[]                                                                          |
| weather_expected_rows                      | True     | True       | rows=2920                                                                           |
| weather_expected_dates                     | True     | True       | dates=730                                                                           |
| weather_expected_rules                     | True     | True       | rules=['12h_prior', '24h_prior', '6h_prior', 'event_day_open']                      |
| weather_rows_per_rule                      | True     | True       | counts={'24h_prior': 730, '12h_prior': 730, '6h_prior': 730, 'event_day_open': 730} |
| weather_unique_keys                        | True     | True       | duplicates=0                                                                        |
| weather_residual_identity                  | True     | True       | max_error=8.882e-16                                                                 |
| weather_all_support_available              | True     | True       | false_rows=0                                                                        |
| weather_all_complete_local_day             | True     | True       | false_rows=0                                                                        |
| weather_all_issued_before_decision         | True     | True       | false_rows=0                                                                        |
| weather_no_market_price_accessed           | True     | True       | true_rows=0                                                                         |
| weather_no_outcome_accessed                | True     | True       | true_rows=0                                                                         |
| weather_no_model_fitted                    | True     | True       | true_rows=0                                                                         |
| weather_no_model_selected                  | True     | True       | true_rows=0                                                                         |
| weather_no_calibration_selected            | True     | True       | true_rows=0                                                                         |
| weather_no_trading_returns_calculated      | True     | True       | true_rows=0                                                                         |
| gp_expected_rows                           | True     | True       | rows=2920                                                                           |
| gp_expected_dates                          | True     | True       | dates=365                                                                           |
| gp_expected_rules                          | True     | True       | rules=['12h_prior', '24h_prior', '6h_prior', 'event_day_open']                      |
| gp_expected_kernels                        | True     | True       | kernels=['matern', 'rbf']                                                           |
| gp_unique_date_rule_kernel                 | True     | True       | duplicates=0                                                                        |
| gp_residual_identity                       | True     | True       | max_error=5.773e-15                                                                 |
| gp_crps_finite_nonnegative                 | True     | True       |                                                                                     |
| gp_sd_finite_positive                      | True     | True       |                                                                                     |
| phase1_dependency                          | True     | True       | critical_failures=0                                                                 |
| phase2_dependency                          | True     | True       | critical_failures=0                                                                 |
| deterministic_transition_rows              | True     | True       | rows=4380                                                                           |
| deterministic_transition_identity          | True     | True       | max_error=8.882e-16                                                                 |
| probabilistic_loss_rows                    | True     | True       | rows=5840                                                                           |
| phase16_loss_crosscheck                    | True     | True       | max_abs_difference=5.886e-11                                                        |
| gp_mean_shift_reconciliation               | True     | True       | max_error=1.177e-14                                                                 |
| directional_bootstrap_point_reconciliation | True     | True       |                                                                                     |
| rule_path_sample_sizes_explicit            | True     | True       | deterministic_dates=[730]; probabilistic_dates=[365]                                |
| bootstrap_methods_present                  | True     | True       |                                                                                     |
| moving_block_lengths_present               | True     | True       |                                                                                     |
| figures_created                            | True     | True       | figures=7                                                                           |

## Interpretation boundary

The phase measures forecast revisions between historically admissible decision rules. It does not identify the causal effect of any specific new observation, because issue cycle, forecast state and elapsed lead time change jointly.

The phase therefore reports paired forecast revisions, not a causal estimate of the value of one newly observed meteorological variable.

## Deterministic 24h-to-open result

Across 730 dates, the mean deterministic forecast revision is 0.026438°C and the mean absolute revision is 0.606438°C.

The mean reduction in absolute settlement error is 0.104247°C, with an ordinary date-bootstrap 95% interval [0.050137, 0.159182]°C.

The later forecast improves absolute error on 51.51% of dates and worsens it on 38.36%.

Among the 648 non-zero revisions for which a correction direction is defined, 63.89% move towards the eventual HKO settlement value.

## Out-of-sample CRPS revision

- **Raw point:** mean earlier-minus-later CRPS 0.142740°C; 95% interval [0.065205, 0.220548].
- **Static Gaussian:** mean earlier-minus-later CRPS 0.107868°C; 95% interval [0.057301, 0.157822].
- **RBF GP:** mean earlier-minus-later CRPS 0.130461°C; 95% interval [0.079723, 0.182362].
- **Matérn-3/2 GP:** mean earlier-minus-later CRPS 0.137289°C; 95% interval [0.087522, 0.188238].

Positive CRPS improvement means that the later decision rule has lower loss. These comparisons use only the 365-date chronological validation year and reproduce the frozen Phase 16 losses.

## GP distribution revision

- **RBF GP:** mean absolute predictive-mean shift 0.676604°C; mean absolute conditional residual-correction revision 0.160198°C; mean absolute predictive-SD change 0.141206°C.
- **Matérn-3/2 GP:** mean absolute predictive-mean shift 0.684553°C; mean absolute conditional residual-correction revision 0.260994°C; mean absolute predictive-SD change 0.123547°C.

## Thesis use

- Use the rule-level error path and the 24h-to-open paired estimate if material.
- Retain adjacent-transition heterogeneity and nonparametric tests in the appendix.
- Use GP shift decomposition to explain how the predictive law changes, not to claim causal assimilation.
- Do not interpret a small average revision as absence of new information; date-level changes can offset in the mean.
- Do not infer that later rules must always be better. Proper-score changes are empirical and model-specific.
