# 20e single locked final chronological holdout evaluation

## Status

This is the designated first and only evaluation on the frozen final holdout. No specification, feature, hyperparameter, calibration, or split may be changed in response to these results.

## Frozen procedure

- CatBoost feature set: `market_only`
- CatBoost candidate: `cb_d3_lr03_l2_8`
- Calibration: `platt`
- Development end: `2026-05-21`
- Holdout start: `2026-05-22`
- Holdout end: `2026-05-31`

## Exact common-support binary scores

| model                     |   n_rows |   n_dates |   outcome_rate |   mean_brier |   mean_log_score |
|:--------------------------|---------:|----------:|---------------:|-------------:|-----------------:|
| ecmwf_bias_adaptive_sigma |      440 |        10 |      0.0909091 |    0.0512793 |         0.15947  |
| market                    |      440 |        10 |      0.0909091 |    0.0531816 |         0.164882 |
| ecmwf_bias_fixed_sigma    |      440 |        10 |      0.0909091 |    0.0547747 |         0.175551 |
| catboost_platt            |      440 |        10 |      0.0909091 |    0.0803644 |         0.258198 |
| ecmwf_raw                 |      440 |        10 |      0.0909091 |    0.0828321 |         0.283755 |
| catboost_raw              |      440 |        10 |      0.0909091 |    0.107384  |         0.325867 |

## Paired date-level bootstrap comparisons

| metric    | model_a        | model_b                   |   n_dates |   mean_difference_a_minus_b |   bootstrap_ci_2_5 |   bootstrap_ci_97_5 |
|:----------|:---------------|:--------------------------|----------:|----------------------------:|-------------------:|--------------------:|
| brier     | catboost_platt | catboost_raw              |        10 |                 -0.0270197  |        -0.0405614  |          -0.0128427 |
| log_score | catboost_platt | catboost_raw              |        10 |                 -0.0676697  |        -0.111289   |          -0.0253213 |
| brier     | catboost_platt | ecmwf_bias_adaptive_sigma |        10 |                  0.0290851  |         0.00541957 |           0.0564353 |
| log_score | catboost_platt | ecmwf_bias_adaptive_sigma |        10 |                  0.0987282  |         0.04007    |           0.166764  |
| brier     | catboost_platt | ecmwf_bias_fixed_sigma    |        10 |                  0.0255896  |         0.00177175 |           0.0524412 |
| log_score | catboost_platt | ecmwf_bias_fixed_sigma    |        10 |                  0.0826473  |         0.025805   |           0.149331  |
| brier     | catboost_platt | ecmwf_raw                 |        10 |                 -0.00246777 |        -0.0268956  |           0.024009  |
| log_score | catboost_platt | ecmwf_raw                 |        10 |                 -0.0255568  |        -0.0958767  |           0.0523387 |
| brier     | catboost_platt | market                    |        10 |                  0.0271827  |         0.00711384 |           0.0505505 |
| log_score | catboost_platt | market                    |        10 |                  0.0933156  |         0.0458314  |           0.150111  |

Negative Platt-CatBoost-minus-benchmark differences favour Platt-calibrated CatBoost.

## Event-book coherence and categorical scores

| model                     |   n_books |   mean_abs_book_probability_error |   median_abs_book_probability_error |   mean_normalised_categorical_log_score |   mean_normalised_multiclass_brier |
|:--------------------------|----------:|----------------------------------:|------------------------------------:|----------------------------------------:|-----------------------------------:|
| ecmwf_bias_adaptive_sigma |        40 |                       2.16493e-16 |                         2.22045e-16 |                                 1.0476  |                           0.564072 |
| market                    |        40 |                       0.0392875   |                         0.0395      |                                 1.09135 |                           0.585087 |
| ecmwf_bias_fixed_sigma    |        40 |                       3.10862e-16 |                         3.33067e-16 |                                 1.19402 |                           0.602522 |
| catboost_raw              |        40 |                       1.31514     |                         1.38084     |                                 1.36673 |                           0.688678 |
| catboost_platt            |        40 |                       0.970528    |                         0.985088    |                                 1.50338 |                           0.720118 |
| ecmwf_raw                 |        40 |                       3.83027e-16 |                         3.33067e-16 |                                 2.16878 |                           0.911153 |

Binary scores use raw contract probabilities. Categorical scores use probabilities normalised within each complete event book.

## Integrity checks

| check                                  | passed   | detail                                                                                                                                         |
|:---------------------------------------|:---------|:-----------------------------------------------------------------------------------------------------------------------------------------------|
| matrix_nonempty                        | True     | rows=1975                                                                                                                                      |
| development_nonempty                   | True     | rows=1535                                                                                                                                      |
| holdout_nonempty                       | True     | rows=440                                                                                                                                       |
| development_precedes_holdout           | True     | development_end=2026-05-21, holdout_start=2026-05-22                                                                                           |
| holdout_dates_exactly_frozen           | True     | dates=10                                                                                                                                       |
| frozen_catboost_manifest_used          | True     | feature_set=market_only, candidate=cb_d3_lr03_l2_8                                                                                             |
| frozen_platt_calibration_used          | True     | method=platt                                                                                                                                   |
| platt_fit_uses_development_oof_only    | True     | oof_dates=22                                                                                                                                   |
| holdout_predictions_present            | True     | missing=0                                                                                                                                      |
| holdout_probabilities_in_unit_interval | True     | checked all probability columns                                                                                                                |
| common_support_nonempty                | True     | rows=2640, models=6                                                                                                                            |
| common_support_keys_unique             | True     | duplicates=0                                                                                                                                   |
| all_models_same_common_support         | True     | {'catboost_platt': 440, 'catboost_raw': 440, 'ecmwf_bias_adaptive_sigma': 440, 'ecmwf_bias_fixed_sigma': 440, 'ecmwf_raw': 440, 'market': 440} |
| scored_books_have_one_winner           | True     | books=240                                                                                                                                      |
| normalised_books_sum_to_one            | True     | checked                                                                                                                                        |
| single_locked_holdout_evaluation       | True     | 20e is designated as the one locked final evaluation                                                                                           |

## Interpretation rule

These holdout results are confirmatory. Subsequent robustness analysis may vary assumptions transparently, but must not retroactively redefine the primary model or primary holdout result.
