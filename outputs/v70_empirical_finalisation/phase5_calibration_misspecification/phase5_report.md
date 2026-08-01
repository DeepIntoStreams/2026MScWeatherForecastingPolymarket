# Phase 5 — Calibration and GP Misspecification

Generated: `2026-07-31T23:56:24.935992+00:00`

## Overall status: **PASSED**

## Provenance

```json
{
  "bootstrap_replications": 10000,
  "bootstrap_seed": 20260803,
  "frozen_commit": "1b0900086c315588b0dc41225e41c2b5f2189bfa",
  "frozen_ref": "v2-empirical-complete",
  "frozen_tag_object": "5d48edb55074f4018d842482bab9f7bf4ab1c01e",
  "generated_utc": "2026-07-31T23:56:03.408935+00:00",
  "interpretation_boundary": "The diagnostics assess the adequacy of the frozen Gaussian predictive law. They do not trigger model reselection, refitting, a new covariance search, or any use of market outcomes in weather-model estimation.",
  "moving_block_lengths": [
    3,
    5,
    7,
    14
  ],
  "phase19_source_hashes": {
    "phase19_autocorrelation.csv": "fb2c48e8c6e7c88d671a632f1a951dcfdcaa0d10717b86ac832e85a460667eb4",
    "phase19_coverage_summary.csv": "f3ada723671d45501918e7a9ac5d482db0aecc001dd4f57aab6c80918b8d3dc5",
    "phase19_cross_rule_residual_correlations.csv": "e854ca20a80fde1a9e6190014d28ce8b5d69c5cbcf3f82c72a61186376cbccec",
    "phase19_dependence_summary.csv": "6772fdc55d800262e48c0fd80ad15edc421c368e38603b1fb87c3676bfe82b11",
    "phase19_heteroskedasticity_quartiles.csv": "d395798040cd19e849aabf679358af521a4a41fcebda1b827f3be0824228f2d5",
    "phase19_pit_histogram.csv": "d7b42ac64978a36b31da0ce4b4085a1a29e979153fe0e53ab6861e0d7b76fbf4",
    "phase19_pit_summary.csv": "33916bd0c436d34ee96646e028ad483c86245db4cf13dd3847fd883d43c5a04b",
    "phase19_quantile_calibration.csv": "c2503dab44afa690e2d71e391dd22db0daa973a1173154e411388e7542e467aa",
    "phase19_quantile_calibration_summary.csv": "eb4058e09dfa29d1470d9f86ba4368ad9616d16f2c41820faf2a9481682bd36e",
    "phase19_reconciliation_checks.csv": "83da2f160f645bb06c5de4be7177c37799afee0d454818c17c0c2fa2ad6fe11d",
    "phase19_sharpness_summary.csv": "a9f795967e49802b5324c6a0ea60cbd30cb24072979188c7b261c0df7a0a6aba",
    "phase19_standardised_residual_summary.csv": "fa816688352250ccb0e016aa93f408ee62ac197d5a17e138cecd1b90a1c116ca",
    "phase19_variance_regression_coefficients.csv": "6a39d81a5040393cd977516d82a17c2c08a88681d3f91df19413bdeb01d780c1",
    "phase19_variance_regression_summary.csv": "809a27bbfec9141ddf82e9fa7ca72f9628db7ee58ccee058bbb6833da9570e1f"
  },
  "phase3_loss_panel": "outputs/v70_empirical_finalisation/phase3_information_arrival/phase3_validation_probabilistic_loss_panel.csv.gz",
  "phase3_loss_panel_sha256": "2e4f568baf38722591844aa9d83ca468cfca88a9b8cbaa53b299f12051d8b7cf",
  "working_branch": "edward-v70-empirical-finalisation",
  "working_commit": "53ab58adba2395b2ac86df66b62a92855fddae7f"
}
```

## Integrity checks

| check                                                  | passed   | critical   | detail                                                                                                                                                                                                                                              |
|:-------------------------------------------------------|:---------|:-----------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| phase1_dependency                                      | True     | True       | critical_failures=0                                                                                                                                                                                                                                 |
| phase2_dependency                                      | True     | True       | critical_failures=0                                                                                                                                                                                                                                 |
| phase3_dependency                                      | True     | True       | critical_failures=0                                                                                                                                                                                                                                 |
| phase4_dependency                                      | True     | True       | critical_failures=0                                                                                                                                                                                                                                 |
| loss_panel_required_columns                            | True     | True       | missing=[]                                                                                                                                                                                                                                          |
| gp_expected_rows                                       | True     | True       | rows=2920                                                                                                                                                                                                                                           |
| gp_expected_dates                                      | True     | True       | dates=365                                                                                                                                                                                                                                           |
| gp_expected_models                                     | True     | True       | models=['matern', 'rbf']                                                                                                                                                                                                                            |
| gp_expected_rules                                      | True     | True       | rules=['12h_prior', '24h_prior', '6h_prior', 'event_day_open']                                                                                                                                                                                      |
| rows_per_model                                         | True     | True       | counts={'matern': 1460, 'rbf': 1460}                                                                                                                                                                                                                |
| rows_per_rule_model                                    | True     | True       | counts={('matern', '12h_prior'): 365, ('matern', '24h_prior'): 365, ('matern', '6h_prior'): 365, ('matern', 'event_day_open'): 365, ('rbf', '12h_prior'): 365, ('rbf', '24h_prior'): 365, ('rbf', '6h_prior'): 365, ('rbf', 'event_day_open'): 365} |
| gp_unique_keys                                         | True     | True       | duplicates=0                                                                                                                                                                                                                                        |
| gp_numeric_finite                                      | True     | True       |                                                                                                                                                                                                                                                     |
| gp_predictive_sd_positive                              | True     | True       | minimum_sd=1.209151014                                                                                                                                                                                                                              |
| gp_crps_nonnegative                                    | True     | True       | minimum_crps=0.287894229                                                                                                                                                                                                                            |
| all_phase19_files_loaded                               | True     | True       | files=14                                                                                                                                                                                                                                            |
| frozen_phase19_reconciliation_passed                   | True     | True       | schema=status; statuses=['PASSED']; status_failures=0; numerical_rows=8; numerical_failures=0; failed=0                                                                                                                                             |
| phase19_variance_regression_rows                       | True     | True       | rows=2                                                                                                                                                                                                                                              |
| phase19_variance_coefficient_rows                      | True     | True       | rows=22                                                                                                                                                                                                                                             |
| reference_rbf_integrated_absolute_calibration_error    | True     | True       | calculated=0.02303999; reference=0.02304000                                                                                                                                                                                                         |
| reference_rbf_root_mean_squared_calibration_error      | True     | True       | calculated=0.02851606; reference=0.02852000                                                                                                                                                                                                         |
| reference_rbf_maximum_absolute_calibration_error       | True     | True       | calculated=0.05602740; reference=0.05603000                                                                                                                                                                                                         |
| reference_rbf_mean_signed_calibration_error            | True     | True       | calculated=0.01921267; reference=0.01921000                                                                                                                                                                                                         |
| reference_rbf_mean_pit                                 | True     | True       | calculated=0.48089561; reference=0.48090000                                                                                                                                                                                                         |
| reference_rbf_variance_pit                             | True     | True       | calculated=0.09218008; reference=0.09218000                                                                                                                                                                                                         |
| reference_rbf_z_mean                                   | True     | True       | calculated=-0.07449412; reference=-0.07449000                                                                                                                                                                                                       |
| reference_rbf_z_standard_deviation                     | True     | True       | calculated=1.03052681; reference=1.03053000                                                                                                                                                                                                         |
| reference_rbf_z_rmse                                   | True     | True       | calculated=1.03180683; reference=1.03181000                                                                                                                                                                                                         |
| reference_rbf_z_skewness                               | True     | True       | calculated=-0.01000549; reference=-0.01001000                                                                                                                                                                                                       |
| reference_rbf_z_excess_kurtosis                        | True     | True       | calculated=-0.13838071; reference=-0.13838000                                                                                                                                                                                                       |
| reference_matern_integrated_absolute_calibration_error | True     | True       | calculated=0.01558876; reference=0.01559000                                                                                                                                                                                                         |
| reference_matern_root_mean_squared_calibration_error   | True     | True       | calculated=0.01882551; reference=0.01883000                                                                                                                                                                                                         |
| reference_matern_maximum_absolute_calibration_error    | True     | True       | calculated=0.03246575; reference=0.03247000                                                                                                                                                                                                         |
| reference_matern_mean_signed_calibration_error         | True     | True       | calculated=0.01243946; reference=0.01244000                                                                                                                                                                                                         |
| reference_matern_mean_pit                              | True     | True       | calculated=0.48757695; reference=0.48758000                                                                                                                                                                                                         |
| reference_matern_variance_pit                          | True     | True       | calculated=0.08915746; reference=0.08916000                                                                                                                                                                                                         |
| reference_matern_z_mean                                | True     | True       | calculated=-0.05080692; reference=-0.05081000                                                                                                                                                                                                       |
| reference_matern_z_standard_deviation                  | True     | True       | calculated=1.00496420; reference=1.00496000                                                                                                                                                                                                         |
| reference_matern_z_rmse                                | True     | True       | calculated=1.00487183; reference=1.00487000                                                                                                                                                                                                         |
| reference_matern_z_skewness                            | True     | True       | calculated=-0.03659126; reference=-0.03659000                                                                                                                                                                                                       |
| reference_matern_z_excess_kurtosis                     | True     | True       | calculated=-0.08512126; reference=-0.08512000                                                                                                                                                                                                       |
| reference_matern_variance_r_squared                    | True     | True       | calculated=0.02709584; reference=0.02710000                                                                                                                                                                                                         |
| reference_matern_variance_wald                         | True     | True       | calculated=23.20617431; reference=23.20617000                                                                                                                                                                                                       |
| reference_matern_variance_df                           | True     | True       | calculated=10; reference=10                                                                                                                                                                                                                         |
| reference_matern_variance_p_value                      | True     | True       | calculated=0.01001061; reference=0.01001000                                                                                                                                                                                                         |
| diagnostic_panel_rows                                  | True     | True       | rows=2920                                                                                                                                                                                                                                           |
| selected_matern_rows                                   | True     | True       | rows=1460                                                                                                                                                                                                                                           |
| coverage_bootstrap_methods                             | True     | True       | methods=['circular_moving_block', 'ordinary_date']                                                                                                                                                                                                  |
| coverage_block_lengths                                 | True     | True       |                                                                                                                                                                                                                                                     |
| dependence_block_lengths                               | True     | True       |                                                                                                                                                                                                                                                     |
| dependence_lag_pair_bootstrap_method                   | True     | True       | methods=['circular_moving_block_lag_pairs']                                                                                                                                                                                                         |
| dependence_interval_finite                             | True     | True       |                                                                                                                                                                                                                                                     |
| quantile_grid_complete                                 | True     | True       |                                                                                                                                                                                                                                                     |
| variance_coefficients_complete                         | True     | True       | rows=22                                                                                                                                                                                                                                             |
| figures_created                                        | True     | True       | figures=7                                                                                                                                                                                                                                           |
| coverage_reconciliation_review_register                | True     | False      | coverage_rows_requiring_review=0                                                                                                                                                                                                                    |

## Interpretation boundary

The diagnostics assess the adequacy of the frozen Gaussian predictive law. They do not trigger model reselection, refitting, a new covariance search, or any use of market outcomes in weather-model estimation.

## Selected Matérn coverage and sharpness

|   nominal_coverage |   empirical_coverage |   coverage_error |   mean_interval_width_c |   median_interval_width_c |
|-------------------:|---------------------:|-----------------:|------------------------:|--------------------------:|
|                0.5 |             0.460274 |       -0.039726  |                 1.96242 |                   1.97483 |
|                0.8 |             0.782877 |       -0.0171233 |                 3.72867 |                   3.75224 |
|                0.9 |             0.880822 |       -0.0191781 |                 4.78569 |                   4.81595 |

Ordinary and circular moving-block intervals are stored for every coverage level, both overall and by decision rule.

## Marginal calibration

The 1%-99% quantile-calibration integrated absolute error is **0.015589**, RMSE is **0.018826**, maximum absolute error is **0.032466**, and mean signed error is **0.012439**.

Mean PIT is **0.487577** and PIT variance is **0.089157**, against uniform references 0.5 and 0.083333.

## Standardised residuals

Using the settlement-date mean across the four decision rules, the standardised residual has mean **-0.050807**, standard deviation **1.004964**, RMSE **1.004872**, skewness **-0.036591** and excess kurtosis **-0.085121**.

## Dependence

### standardised_residual

Lag-one correlation: **0.509768**. Circular moving-block lag-pair 95% intervals: b=3: [0.409418, 0.581212]; b=5: [0.402928, 0.583331]; b=7: [0.398188, 0.587808]; b=14: [0.382218, 0.594036].

### squared_standardised_residual

Lag-one correlation: **0.238256**. Circular moving-block lag-pair 95% intervals: b=3: [0.119640, 0.357091]; b=5: [0.106448, 0.357229]; b=7: [0.099223, 0.347825]; b=14: [0.102339, 0.345015].

## Conditional variance

The frozen date-clustered auxiliary regression reports R² **0.027096**, joint Wald statistic **23.206174** on 10 non-intercept restrictions, with p-value **0.010011**.

The explanatory power is small, but the test detects remaining feature-related conditional-variance structure.

## Frozen/direct reconciliation

| domain                | model   | metric                                |   direct_value |   frozen_phase19_value |   difference | status   |
|:----------------------|:--------|:--------------------------------------|---------------:|-----------------------:|-------------:|:---------|
| coverage              | rbf     | coverage_0.50                         |      0.442466  |              0.442466  |  5.55112e-17 | matched  |
| coverage              | rbf     | mean_width_0.50                       |      1.93813   |              1.93813   | -7.14184e-12 | matched  |
| coverage              | rbf     | coverage_0.80                         |      0.767808  |              0.767808  |  0           | matched  |
| coverage              | rbf     | mean_width_0.80                       |      3.68251   |              3.68251   | -9.22551e-12 | matched  |
| coverage              | rbf     | coverage_0.90                         |      0.869178  |              0.869178  |  0           | matched  |
| coverage              | rbf     | mean_width_0.90                       |      4.72645   |              4.72645   | -1.49383e-11 | matched  |
| coverage              | matern  | coverage_0.50                         |      0.460274  |              0.460274  |  0           | matched  |
| coverage              | matern  | mean_width_0.50                       |      1.96242   |              1.96242   |  2.79998e-13 | matched  |
| coverage              | matern  | coverage_0.80                         |      0.782877  |              0.782877  |  0           | matched  |
| coverage              | matern  | mean_width_0.80                       |      3.72867   |              3.72867   |  2.51621e-12 | matched  |
| coverage              | matern  | coverage_0.90                         |      0.880822  |              0.880822  |  0           | matched  |
| coverage              | matern  | mean_width_0.90                       |      4.78569   |              4.78569   |  2.5171e-12  | matched  |
| quantile_calibration  | rbf     | integrated_absolute_calibration_error |      0.02304   |              0.02304   |  9.02056e-17 | matched  |
| quantile_calibration  | rbf     | root_mean_squared_calibration_error   |      0.0285161 |              0.0285161 |  6.59195e-17 | matched  |
| quantile_calibration  | rbf     | maximum_absolute_calibration_error    |      0.0560274 |              0.0560274 |  4.85723e-17 | matched  |
| quantile_calibration  | rbf     | mean_signed_calibration_error         |      0.0192127 |              0.0192127 |  4.85723e-17 | matched  |
| quantile_calibration  | matern  | integrated_absolute_calibration_error |      0.0155888 |              0.0155888 |  4.33681e-17 | matched  |
| quantile_calibration  | matern  | root_mean_squared_calibration_error   |      0.0188255 |              0.0188255 |  4.16334e-17 | matched  |
| quantile_calibration  | matern  | maximum_absolute_calibration_error    |      0.0324658 |              0.0324658 |  4.85723e-17 | matched  |
| quantile_calibration  | matern  | mean_signed_calibration_error         |      0.0124395 |              0.0124395 |  2.60209e-17 | matched  |
| pit                   | rbf     | mean_pit                              |      0.480896  |              0.480896  |  0           | matched  |
| pit                   | rbf     | variance_pit                          |      0.0921801 |              0.0921801 |  1.38778e-17 | matched  |
| pit                   | rbf     | ks_statistic                          |      0.0569712 |              0.0569712 |  7.63278e-17 | matched  |
| pit                   | rbf     | cramer_von_mises_statistic            |      1.16864   |              1.16864   |  0           | matched  |
| pit                   | rbf     | ten_bin_chi_square                    |     28.4384    |             28.4384    |  0           | matched  |
| pit                   | matern  | mean_pit                              |      0.487577  |              0.487577  |  5.55112e-17 | matched  |
| pit                   | matern  | variance_pit                          |      0.0891575 |              0.0891575 |  8.32667e-17 | matched  |
| pit                   | matern  | ks_statistic                          |      0.0343071 |              0.0343071 |  1.38778e-17 | matched  |
| pit                   | matern  | cramer_von_mises_statistic            |      0.511398  |              0.511398  |  0           | matched  |
| pit                   | matern  | ten_bin_chi_square                    |     14.1096    |             14.1096    |  0           | matched  |
| standardised_residual | rbf     | mean                                  |     -0.0744941 |             -0.0744941 | -5.55112e-17 | matched  |
| standardised_residual | rbf     | standard_deviation                    |      1.03053   |              1.03053   |  0           | matched  |
| standardised_residual | rbf     | rmse                                  |      1.03181   |              1.03181   |  0           | matched  |
| standardised_residual | rbf     | skewness                              |     -0.0100055 |             -0.0100055 | -2.08167e-17 | matched  |
| standardised_residual | rbf     | excess_kurtosis                       |     -0.138381  |             -0.138381  | -9.71445e-16 | matched  |
| standardised_residual | matern  | mean                                  |     -0.0508069 |             -0.0508069 | -1.38778e-17 | matched  |
| standardised_residual | matern  | standard_deviation                    |      1.00496   |              1.00496   |  0           | matched  |
| standardised_residual | matern  | rmse                                  |      1.00487   |              1.00487   |  2.22045e-16 | matched  |
| standardised_residual | matern  | skewness                              |     -0.0365913 |             -0.0365913 |  0           | matched  |
| standardised_residual | matern  | excess_kurtosis                       |     -0.0851213 |             -0.0851213 |  0           | matched  |

Rows marked `review_required` are preserved as an audit item. The phase does not silently replace a frozen value with a direct recalculation.

## Thesis use

- Main text: one compact adequacy table with coverage, width, quantile error, lag-one dependence and variance-regression evidence.
- Main text: at most one coverage or residual-dependence figure.
- Appendix: PIT histogram, Q-Q plot, full ACFs, rule-level intervals and coefficient table.
- Archive: all 1%-99% calibration points, block-length sensitivities and quartile diagnostics.
- Interpret the law as useful but misspecified; do not claim exact Gaussian calibration.
