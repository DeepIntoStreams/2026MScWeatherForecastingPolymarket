# Phase 4 — Full Forecast Attribution

Generated: `2026-07-31T23:20:35.938729+00:00`

## Overall status: **PASSED**

## Provenance

```json
{
  "bootstrap_replications": 10000,
  "bootstrap_seed": 20260802,
  "frozen_commit": "1b0900086c315588b0dc41225e41c2b5f2189bfa",
  "frozen_ref": "v2-empirical-complete",
  "frozen_tag_object": "5d48edb55074f4018d842482bab9f7bf4ab1c01e",
  "generated_utc": "2026-07-31T23:20:23.646283+00:00",
  "interpretation_boundary": "The ordered raw-static-RBF-Mat\u00e9rn sequence is an empirical attribution device, not a structural or causal decomposition. RBF and Mat\u00e9rn are alternative covariance specifications rather than nested models.",
  "moving_block_lengths": [
    3,
    5,
    7
  ],
  "phase3_date_losses": "outputs/v70_empirical_finalisation/phase3_information_arrival/phase3_validation_date_level_model_losses.csv",
  "phase3_date_losses_sha256": "c233b6645ef92b2d0e05486bf65febfb709ab4a8d3ed48e41ff20be2824db83d",
  "phase3_loss_panel": "outputs/v70_empirical_finalisation/phase3_information_arrival/phase3_validation_probabilistic_loss_panel.csv.gz",
  "phase3_loss_panel_sha256": "2e4f568baf38722591844aa9d83ca468cfca88a9b8cbaa53b299f12051d8b7cf",
  "stationary_mean_block_lengths": [
    3,
    5,
    7
  ],
  "working_branch": "edward-v70-empirical-finalisation",
  "working_commit": "e689e275b541b3dec00a8edf66bca66bba86b2e9"
}
```

## Integrity checks

| check                                    | passed   | critical   | detail                                                                                                                                                                          |
|:-----------------------------------------|:---------|:-----------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| phase1_dependency                        | True     | True       | critical_failures=0                                                                                                                                                             |
| phase2_dependency                        | True     | True       | critical_failures=0                                                                                                                                                             |
| phase3_dependency                        | True     | True       | critical_failures=0                                                                                                                                                             |
| loss_panel_required_columns              | True     | True       | missing=[]                                                                                                                                                                      |
| date_loss_required_columns               | True     | True       | missing=[]                                                                                                                                                                      |
| loss_panel_expected_rows                 | True     | True       | rows=5840                                                                                                                                                                       |
| date_loss_expected_rows                  | True     | True       | rows=1460                                                                                                                                                                       |
| expected_dates                           | True     | True       | panel_dates=365; date_loss_dates=365                                                                                                                                            |
| expected_models                          | True     | True       | panel_models=['matern', 'raw', 'rbf', 'static']; date_models=['matern', 'raw', 'rbf', 'static']                                                                                 |
| expected_rules                           | True     | True       | rules=['12h_prior', '24h_prior', '6h_prior', 'event_day_open']                                                                                                                  |
| loss_panel_unique_keys                   | True     | True       | duplicates=0                                                                                                                                                                    |
| date_loss_unique_keys                    | True     | True       | duplicates=0                                                                                                                                                                    |
| four_rules_per_date_model                | True     | True       | bad_count_groups=0; bad_unique_groups=0                                                                                                                                         |
| crps_finite_nonnegative                  | True     | True       |                                                                                                                                                                                 |
| date_loss_reconciliation                 | True     | True       | max_error=8.882e-16                                                                                                                                                             |
| reference_mean_crps_raw                  | True     | True       | calculated=1.745684932; reference=1.745685000; difference=-6.849e-08                                                                                                            |
| reference_mean_crps_static               | True     | True       | calculated=0.911754550; reference=0.911755000; difference=-4.500e-07                                                                                                            |
| reference_mean_crps_rbf                  | True     | True       | calculated=0.877561468; reference=0.877561000; difference=4.684e-07                                                                                                             |
| reference_mean_crps_matern               | True     | True       | calculated=0.863339999; reference=0.863340000; difference=-1.041e-09                                                                                                            |
| phase3_phase16_crosscheck_passed         | True     | True       | rows=24; failed=0                                                                                                                                                               |
| validation_block_sizes                   | True     | True       | actual=[91, 91, 91, 92]; expected=[91, 91, 91, 92]                                                                                                                              |
| date_contrast_panel_rows                 | True     | True       | rows=2190                                                                                                                                                                       |
| rule_contrast_panel_rows                 | True     | True       | rows=8760                                                                                                                                                                       |
| contrast_sign_identity                   | True     | True       | max_error=0.000e+00                                                                                                                                                             |
| contrast_mean_reconciliation             | True     | True       | max_error=1.110e-16                                                                                                                                                             |
| ordinary_intervals_all_contrasts         | True     | True       | contrasts=['matern_minus_raw', 'matern_minus_rbf', 'matern_minus_static', 'rbf_minus_raw', 'rbf_minus_static', 'static_minus_raw']                                              |
| moving_block_lengths_all_primary         | True     | True       |                                                                                                                                                                                 |
| stationary_bootstrap_lengths_all_primary | True     | True       |                                                                                                                                                                                 |
| rule_interval_matrix_complete            | True     | True       |                                                                                                                                                                                 |
| block_interval_matrix_complete           | True     | True       |                                                                                                                                                                                 |
| ordered_attribution_reconciles           | True     | True       |                                                                                                                                                                                 |
| influence_all_contrasts                  | True     | True       |                                                                                                                                                                                 |
| subgroup_outputs_present                 | True     | True       | types=['decision_rule', 'deterministic_forecast_quartile', 'raw_absolute_error_quartile', 'season', 'static_correction_quartile', 'static_spread_quartile', 'validation_block'] |
| figures_created                          | True     | True       | figures=7                                                                                                                                                                       |

## Interpretation boundary

The ordered raw-static-RBF-Matérn sequence is an empirical attribution device, not a structural or causal decomposition. RBF and Matérn are alternative covariance specifications rather than nested models.

## Mean date CRPS sequence

Raw point: **1.745685**; static Gaussian: **0.911755**; RBF GP: **0.877561**; Matérn-3/2 GP: **0.863340**.

The ordered reductions are:

| stage         |   absolute_crps_reduction_c |   relative_reduction_from_previous |   share_of_total_raw_to_matern_reduction |
|:--------------|----------------------------:|-----------------------------------:|-----------------------------------------:|
| raw_to_static |                   0.83393   |                          0.47771   |                                0.94513   |
| static_to_rbf |                   0.0341931 |                          0.0375025 |                                0.0387525 |
| rbf_to_matern |                   0.0142215 |                          0.0162057 |                                0.0161178 |

## Primary paired contrasts

### static_minus_raw

Mean model-minus-benchmark loss difference: **-0.833930°C**. Negative values favour the first model.

Ordinary date-bootstrap 95% interval: [-0.946673, -0.720418]. The first model has lower loss on 70.41% of dates.

Circular moving-block intervals: b=3: [-0.988690, -0.675022]; b=5: [-1.020615, -0.646645]; b=7: [-1.041322, -0.628809].

The five largest absolute date contributions account for 2.72% of total absolute contrast mass. The maximum leave-one-date-out change in the mean is 0.004902°C.

### matern_minus_static

Mean model-minus-benchmark loss difference: **-0.048415°C**. Negative values favour the first model.

Ordinary date-bootstrap 95% interval: [-0.069969, -0.027339]. The first model has lower loss on 55.89% of dates.

Circular moving-block intervals: b=3: [-0.079751, -0.019028]; b=5: [-0.083311, -0.015017]; b=7: [-0.085095, -0.014263].

The five largest absolute date contributions account for 10.58% of total absolute contrast mass. The maximum leave-one-date-out change in the mean is 0.003116°C.

### matern_minus_rbf

Mean model-minus-benchmark loss difference: **-0.014221°C**. Negative values favour the first model.

Ordinary date-bootstrap 95% interval: [-0.020529, -0.007904]. The first model has lower loss on 56.71% of dates.

Circular moving-block intervals: b=3: [-0.022345, -0.006353]; b=5: [-0.023452, -0.005089]; b=7: [-0.024630, -0.004456].

The five largest absolute date contributions account for 7.94% of total absolute contrast mass. The maximum leave-one-date-out change in the mean is 0.000832°C.

## Temporal heterogeneity

| scope_value   |   mean_loss_difference_c |   model_better_fraction |
|:--------------|-------------------------:|------------------------:|
| block_1       |                0.0348001 |                0.296703 |
| block_2       |               -0.0612414 |                0.692308 |
| block_3       |               -0.0414655 |                0.483516 |
| block_4       |               -0.124911  |                0.76087  |

The block analysis is diagnostic. A block-level reversal does not invalidate the overall paired result, but it limits claims that conditional GP gains are uniform through time.

## Thesis use

- Main text: four-model CRPS sequence and the three primary paired contrasts.
- Main text or one compact figure: temporal block heterogeneity.
- Appendix: full rule-level interval matrix, stationary bootstrap and subgroup diagnostics.
- Empirical archive: all leave-one-date-out, extreme-date and concentration tables.
- Do not describe the ordered stages as a causal decomposition or claim that RBF is nested inside Matérn.
