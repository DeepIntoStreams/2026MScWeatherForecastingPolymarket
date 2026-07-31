# Phase 2 — Settlement Approximation-Error Analysis

Generated: `2026-07-31T22:31:06.488120+00:00`

## Overall status: **PASSED**

## Provenance

```json
{
  "bootstrap_replications": 10000,
  "bootstrap_seed": 20260731,
  "frozen_commit": "1b0900086c315588b0dc41225e41c2b5f2189bfa",
  "frozen_ref": "v2-empirical-complete",
  "frozen_tag_object": "5d48edb55074f4018d842482bab9f7bf4ab1c01e",
  "generated_utc": "2026-07-31T22:30:59.481552+00:00",
  "moving_block_lengths": [
    3,
    5,
    7
  ],
  "phase1_root": "outputs/v70_empirical_finalisation/phase1_evidence_recovery",
  "weather_input": "outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv",
  "weather_input_sha256": "14425a244abe9374c8c7a97feef68b08be54fe48a3aa1e2b43ea41b515e9ee48",
  "working_branch": "edward-v70-empirical-finalisation",
  "working_commit": "78889d25c1c41c5e43173e8e281ca2888e83a5d1"
}
```

## Integrity checks

| check                              | passed   | critical   | detail                                                                                                                                                          |
|:-----------------------------------|:---------|:-----------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| required_columns                   | True     | True       | missing=[]                                                                                                                                                      |
| expected_rows                      | True     | True       | rows=2920                                                                                                                                                       |
| expected_dates                     | True     | True       | dates=730                                                                                                                                                       |
| expected_rules                     | True     | True       | rules=['12h_prior', '24h_prior', '6h_prior', 'event_day_open']                                                                                                  |
| rows_per_rule                      | True     | True       | counts={'24h_prior': 730, '12h_prior': 730, '6h_prior': 730, 'event_day_open': 730}                                                                             |
| unique_date_rule_keys              | True     | True       | duplicate_keys=0                                                                                                                                                |
| residual_identity                  | True     | True       | max_absolute_error=8.882e-16                                                                                                                                    |
| forecast_error_identity            | True     | True       | max_absolute_error=8.882e-16                                                                                                                                    |
| absolute_error_identity            | True     | True       | max_absolute_error=0.000e+00                                                                                                                                    |
| squared_error_identity             | True     | True       | max_absolute_error=7.105e-15                                                                                                                                    |
| all_support_available              | True     | True       | false_rows=0                                                                                                                                                    |
| all_complete_local_day             | True     | True       | false_rows=0                                                                                                                                                    |
| all_issued_before_decision         | True     | True       | false_rows=0                                                                                                                                                    |
| no_market_price_accessed           | True     | True       | true_rows=0                                                                                                                                                     |
| no_outcome_accessed                | True     | True       | true_rows=0                                                                                                                                                     |
| no_model_fitted                    | True     | True       | true_rows=0                                                                                                                                                     |
| no_model_selected                  | True     | True       | true_rows=0                                                                                                                                                     |
| no_calibration_selected            | True     | True       | true_rows=0                                                                                                                                                     |
| no_trading_returns_calculated      | True     | True       | true_rows=0                                                                                                                                                     |
| phase1_critical_checks_passed      | True     | True       | critical_failures=0                                                                                                                                             |
| phase1_static_parameter_crosscheck | True     | True       | max_abs_bias_difference=2.887e-15; max_abs_sd_difference=8.882e-16; max_within_rule_bias_spread=1.066e-14; max_within_rule_sd_spread=0.000e+00; failed_rules=[] |
| bootstrap_methods_present          | True     | True       | methods=['circular_moving_block', 'ordinary_date']                                                                                                              |
| moving_block_lengths_present       | True     | True       |                                                                                                                                                                 |
| all_primary_scopes_present         | True     | True       | scopes=['12h_prior', '24h_prior', '6h_prior', 'event_day_open', 'pooled_all_rules']                                                                             |
| phase17_crosscheck                 | True     | True       | max_abs_difference=2.220e-16                                                                                                                                    |
| figures_created                    | True     | True       | figures=7                                                                                                                                                       |

## Headline descriptive evidence

The pooled HKO-minus-deterministic residual is **1.429658°C**, with residual standard deviation **1.473250°C**, median **1.400000°C**, and mean absolute error **1.680068°C**.

The ordinary settlement-date bootstrap 95% interval for the pooled mean is [1.327363, 1.530925]°C. The centred two-sided bootstrap p-value for a zero mean is 9.999e-05.

The deterministic forecast is below the HKO settlement value on **82.47%** of date-rule rows; the ordinary date-bootstrap interval is [79.97%, 84.86%].

## Gaussian adequacy

The largest pooled practical tail-probability discrepancy between the empirical residual distribution and its fitted Gaussian is -0.035164 for `absolute_residual_above_threshold` at 1.00°C.

Normality-test p-values are descriptive only because location and scale are estimated from the same residual sample and four rule observations share each settlement date.

## Influence

The maximum leave-one-date-out change in the pooled mean is 0.006647°C, attained when omitting 2025-05-11.

## Scope and interpretation

- The phase measures settlement approximation error; it does not assess causal model bias.
- Pooled uncertainty resamples settlement dates and preserves all four rules together.
- Circular moving blocks with lengths 3, 5 and 7 assess short-range temporal sensitivity.
- The static Gaussian comparison is descriptive and uses full-history residual moments.
- No market information, model selection, calibration selection or trading return enters this phase.
