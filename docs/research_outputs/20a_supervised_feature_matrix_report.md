# 20a supervised market-weather feature matrix

## Purpose

Construct a leakage-controlled, date-grouped feature matrix for the later tree-based supervised post-processing stage. No predictive model is fitted in this step.

## Inputs

- `data/processed/19c_common_support_calibrated_probability_panel.csv`
- `data/processed/19c_categorical_book_score_panel.csv`
- `data/processed/19c_integrity_checks.csv`

## Main result

- Supervised rows: `1975`
- Unique event dates and date groups: `48`
- Unique contract-date-decision keys: `1975`
- Predictors in the complete feature dictionary: `77`
- Combined-model eligible rows: `1975`
- Complete-book combined eligible rows: `1936`

## Row counts by decision rule

| decision_rule   |   n_rows |
|:----------------|---------:|
| 24h_prior       |      470 |
| 12h_prior       |      494 |
| 6h_prior        |      483 |
| event_day_open  |      528 |

## Row counts by contract-event type

| contract_event_type_v2   |   n_rows |
|:-------------------------|---------:|
| lower_tail_endpoint      |      180 |
| interior_bin             |     1616 |
| upper_tail               |      179 |

## Predictor families

| family      |   n_features |
|:------------|-------------:|
| book        |           28 |
| interaction |            9 |
| market      |            3 |
| structural  |           14 |
| temporal    |            6 |
| weather     |           17 |

## Model feature sets

| model feature set | number of predictors |
|:--|--:|
| weather_only | 58 |
| market_only | 30 |
| combined | 77 |
| combined_no_book | 49 |

The `weather_only`, `market_only`, `combined`, and `combined_no_book` lists are stored in `data/processed/20a_model_feature_sets.json`. All contracts from the same HKO settlement date share one `date_group_id`; 20b must split by this group rather than by row.

## Leakage control

Only the realised binary target is retained as an outcome column. Upstream Brier scores, log scores, realised temperature errors, winning-contract probabilities, and other outcome-derived diagnostics are excluded from the predictor dictionary. The expanding ECMWF bias and scale features inherit the strict historical training rule verified in 19c.

## Book features

Book-normalised probabilities, ranks, entropy, totals, and gaps are observable at the decision cutoff. They are retained as optional predictors. The `combined_no_book` feature set provides a conservative specification that avoids reliance on complete event-book support.

## Integrity checks

| check                                      | passed   | detail                                                            |
|:-------------------------------------------|:---------|:------------------------------------------------------------------|
| upstream_19c_checks_passed                 | True     | passed=14/14                                                      |
| source_panel_nonempty                      | True     | rows=2635                                                         |
| calibration_ready_matrix_nonempty          | True     | rows=1975                                                         |
| unique_contract_date_decision_key          | True     | duplicates=0                                                      |
| binary_target                              | True     | bad=0                                                             |
| source_probabilities_in_unit_interval      | True     | bad=0                                                             |
| no_infinite_numeric_features               | True     | infinite=0                                                        |
| one_date_group_per_event_date              | True     | bad_dates=0                                                       |
| one_event_date_per_date_group              | True     | bad_groups=0                                                      |
| calibration_training_strictly_historical   | True     | bad_rows=0                                                        |
| selected_forecast_run_no_later_than_cutoff | True     | bad_rows=0                                                        |
| no_outcome_derived_predictors              | True     | forbidden=[]                                                      |
| all_declared_features_present              | True     | missing=[]                                                        |
| weather_feature_set_nonempty               | True     | n=58                                                              |
| market_feature_set_nonempty                | True     | n=30                                                              |
| combined_feature_set_nonempty              | True     | n=77                                                              |
| all_expected_decision_rules_present        | True     | observed=['12h_prior', '24h_prior', '6h_prior', 'event_day_open'] |
| all_expected_event_types_present           | True     | observed=['interior_bin', 'lower_tail_endpoint', 'upper_tail']    |

## Issues and expected missingness

| issue_type                      | feature                            | detail                                                                                           |   n_rows |     share |
|:--------------------------------|:-----------------------------------|:-------------------------------------------------------------------------------------------------|---------:|----------:|
| feature_missingness             | event_midpoint_C                   | Midpoint of a bounded event interval; missing for tail events.                                   |      359 | 0.181772  |
| feature_missingness             | event_width_C                      | Width of a bounded event interval; missing for tail events.                                      |      359 | 0.181772  |
| feature_missingness             | event_lower_C_finite               | Finite lower event boundary in degrees Celsius; missing for a lower tail.                        |      180 | 0.0911392 |
| feature_missingness             | corrected_forecast_minus_lower_C   | Corrected forecast minus finite lower event boundary.                                            |      180 | 0.0911392 |
| feature_missingness             | raw_forecast_minus_lower_C         | Raw forecast minus finite lower event boundary.                                                  |      180 | 0.0911392 |
| feature_missingness             | standardised_corrected_minus_lower | Corrected lower-bound margin divided by sigma.                                                   |      180 | 0.0911392 |
| feature_missingness             | event_upper_C_finite               | Finite upper event boundary in degrees Celsius; missing for an upper tail.                       |      179 | 0.0906329 |
| feature_missingness             | standardised_upper_minus_corrected | Corrected upper-bound margin divided by sigma.                                                   |      179 | 0.0906329 |
| feature_missingness             | upper_minus_corrected_forecast_C   | Finite upper event boundary minus corrected forecast.                                            |      179 | 0.0906329 |
| feature_missingness             | upper_minus_raw_forecast_C         | Finite upper event boundary minus raw forecast.                                                  |      179 | 0.0906329 |
| incomplete_common_support_books |                                    | Book-normalised features should be treated cautiously or omitted for these date-decision groups. |        5 | 0.0276243 |

## Outputs

- `data/processed/20a_supervised_feature_matrix.csv`
- `data/processed/20a_feature_dictionary.csv`
- `data/processed/20a_model_feature_sets.json`
- `data/processed/20a_date_group_summary.csv`
- `data/processed/20a_feature_missingness_summary.csv`
- `data/processed/20a_integrity_checks.csv`
- `data/processed/20a_issues.csv`
- `figures/20a_supervised_feature_matrix/20a_rows_by_decision_rule.png`
- `figures/20a_supervised_feature_matrix/20a_target_prevalence_by_event_type.png`
- `figures/20a_supervised_feature_matrix/20a_feature_missingness_top20.png`
- `figures/20a_supervised_feature_matrix/20a_core_predictor_correlation.png`
