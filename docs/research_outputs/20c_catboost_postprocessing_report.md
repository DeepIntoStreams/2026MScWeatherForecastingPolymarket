# 20c compact CatBoost post-processing, corrected benchmark comparison

## Purpose

This step compares compact CatBoost probability models using the frozen 20b expanding-window folds. The final chronological holdout remains sealed.

## Best CatBoost development-set specification

- Feature set: `market_only`
- Candidate: `cb_d3_lr03_l2_8`
- Mean date-level Brier: `0.07585552`
- Mean date-level log score: `0.25998360`

Selection rule: lowest mean date-level Brier score, followed by mean date-level log score, then contract-level Brier and log score as deterministic tie-breakers.

## Full specification ranking

| feature_set      | candidate_id     |   n_rows |   outcome_rate |   mean_brier |   mean_log_score |   n_dates |   mean_date_brier |   median_date_brier |   mean_date_log_score |   median_date_log_score |   overall_rank | selected   |
|:-----------------|:-----------------|---------:|---------------:|-------------:|-----------------:|----------:|------------------:|--------------------:|----------------------:|------------------------:|---------------:|:-----------|
| market_only      | cb_d3_lr03_l2_8  |      935 |      0.0909091 |    0.0759878 |         0.25676  |        22 |         0.0758555 |           0.0796581 |              0.259984 |                0.252752 |              1 | True       |
| market_only      | cb_d3_lr05_l2_12 |      935 |      0.0909091 |    0.0773847 |         0.261735 |        22 |         0.0772805 |           0.0827919 |              0.264651 |                0.246564 |              2 | False      |
| combined         | cb_d3_lr05_l2_12 |      935 |      0.0909091 |    0.0773264 |         0.256193 |        22 |         0.0773184 |           0.0743879 |              0.258888 |                0.22221  |              3 | False      |
| combined_no_book | cb_d3_lr05_l2_12 |      935 |      0.0909091 |    0.0776599 |         0.251626 |        22 |         0.077443  |           0.0729135 |              0.253686 |                0.223557 |              4 | False      |
| combined_no_book | cb_d3_lr03_l2_8  |      935 |      0.0909091 |    0.0782708 |         0.253503 |        22 |         0.0780545 |           0.0742828 |              0.255636 |                0.227123 |              5 | False      |
| combined         | cb_d4_lr03_l2_12 |      935 |      0.0909091 |    0.078109  |         0.25846  |        22 |         0.0780715 |           0.075186  |              0.261177 |                0.224832 |              6 | False      |
| combined         | cb_d3_lr03_l2_8  |      935 |      0.0909091 |    0.0782157 |         0.257477 |        22 |         0.0783561 |           0.0723436 |              0.260679 |                0.224418 |              7 | False      |
| combined_no_book | cb_d4_lr03_l2_12 |      935 |      0.0909091 |    0.0802775 |         0.26442  |        22 |         0.0799898 |           0.0761786 |              0.266261 |                0.235055 |              8 | False      |
| market_only      | cb_d4_lr03_l2_12 |      935 |      0.0909091 |    0.081052  |         0.274741 |        22 |         0.080747  |           0.0919585 |              0.276791 |                0.284585 |              9 | False      |
| weather_only     | cb_d4_lr03_l2_12 |      935 |      0.0909091 |    0.0840911 |         0.281207 |        22 |         0.0846546 |           0.0815988 |              0.28435  |                0.235083 |             10 | False      |
| weather_only     | cb_d3_lr03_l2_8  |      935 |      0.0909091 |    0.0871816 |         0.294339 |        22 |         0.0877042 |           0.0874288 |              0.298045 |                0.259316 |             11 | False      |
| weather_only     | cb_d3_lr05_l2_12 |      935 |      0.0909091 |    0.0871512 |         0.295215 |        22 |         0.0877897 |           0.0873453 |              0.299203 |                0.25889  |             12 | False      |

## Best CatBoost specification versus direct probability benchmarks

| model                     |   n_rows |   n_dates |   mean_brier |   mean_log_score | catboost_beats_any_direct_brier   | catboost_beats_any_direct_log   |
|:--------------------------|---------:|----------:|-------------:|-----------------:|:----------------------------------|:--------------------------------|
| ecmwf_bias_fixed_sigma    |      935 |        22 |    0.0667722 |         0.213935 | True                              | True                            |
| ecmwf_bias_adaptive_sigma |      935 |        22 |    0.0695568 |         0.221023 | True                              | True                            |
| market                    |      935 |        22 |    0.0720863 |         0.231525 | True                              | True                            |
| catboost_selected         |      935 |        22 |    0.0759878 |         0.25676  | True                              | True                            |
| ecmwf_raw                 |      935 |        22 |    0.0813612 |         0.293473 | True                              | True                            |

## Paired date-clustered bootstrap comparisons

| metric    | model_a           | model_b                   |   n_dates |   mean_difference_a_minus_b |   bootstrap_ci_2_5 |   bootstrap_ci_97_5 | lower_is_better   |
|:----------|:------------------|:--------------------------|----------:|----------------------------:|-------------------:|--------------------:|:------------------|
| brier     | catboost_selected | market                    |        22 |                  0.00370441 |       -0.004155    |          0.0116645  | True              |
| log_score | catboost_selected | market                    |        22 |                  0.0263466  |       -0.00723981  |          0.06266    | True              |
| brier     | catboost_selected | ecmwf_raw                 |        22 |                 -0.00505174 |       -0.0202194   |          0.00963958 | True              |
| log_score | catboost_selected | ecmwf_raw                 |        22 |                 -0.0326838  |       -0.106132    |          0.0466443  | True              |
| brier     | catboost_selected | ecmwf_bias_fixed_sigma    |        22 |                  0.00931033 |       -0.00111477  |          0.0191066  | True              |
| log_score | catboost_selected | ecmwf_bias_fixed_sigma    |        22 |                  0.0461638  |       -0.000210005 |          0.100733   | True              |
| brier     | catboost_selected | ecmwf_bias_adaptive_sigma |        22 |                  0.00633709 |       -0.00661757  |          0.0185655  | True              |
| log_score | catboost_selected | ecmwf_bias_adaptive_sigma |        22 |                  0.0377246  |       -0.0121099   |          0.0910633  | True              |

A negative CatBoost-minus-benchmark difference favours CatBoost because lower proper scores are better.

**Overall benchmark conclusion:** at least one direct probability benchmark outperforms the best CatBoost specification on the development out-of-fold sample.

## Integrity checks

| check                                  | passed   | detail                                                                                                                                                      |
|:---------------------------------------|:---------|:------------------------------------------------------------------------------------------------------------------------------------------------------------|
| matrix_nonempty                        | True     | rows=1975                                                                                                                                                   |
| oof_nonempty                           | True     | rows=11220                                                                                                                                                  |
| final_holdout_absent_from_oof          | True     | holdout_overlap=0                                                                                                                                           |
| oof_dates_subset_of_development        | True     | oof_dates=22                                                                                                                                                |
| oof_probabilities_present              | True     | missing=0                                                                                                                                                   |
| oof_probabilities_in_unit_interval     | True     | checked selected probabilities                                                                                                                              |
| oof_keys_unique                        | True     | duplicates=0                                                                                                                                                |
| binary_target_valid                    | True     | bad=0                                                                                                                                                       |
| ranking_nonempty                       | True     | rows=12                                                                                                                                                     |
| exactly_one_selected_specification     | True     | selected=1                                                                                                                                                  |
| benchmark_panel_nonempty               | True     | rows=4675                                                                                                                                                   |
| all_expected_direct_benchmarks_present | True     | missing=none                                                                                                                                                |
| resolved_benchmark_columns_recorded    | True     | {"ecmwf_bias_adaptive_sigma": "p_ecmwf_bias_scale", "ecmwf_bias_fixed_sigma": "p_ecmwf_bias_fixed_sigma", "ecmwf_raw": "p_ecmwf_raw", "market": "p_market"} |
| holdout_never_scored                   | True     | final holdout remains sealed                                                                                                                                |
| cv_train_precedes_validation           | True     | all folds chronological                                                                                                                                     |

## Methodological status

The selected specification is the best model only within the pre-declared CatBoost candidate set. It is not described as the best overall probability forecast unless it also beats every direct probability benchmark. The 20c probabilities are out-of-fold development predictions. They are not yet probability-calibrated and are not yet forced to satisfy daily event-book coherence. Both tasks are deferred to 20d. The final holdout must remain untouched until the 20d procedure is frozen.
