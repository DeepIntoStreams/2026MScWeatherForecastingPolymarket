# 20d out-of-fold calibration and event-book coherence

## Purpose

This step calibrates the best 20c CatBoost specification using only prior development OOF dates, then evaluates binary proper scores and complete-book categorical diagnostics. The final chronological holdout remains sealed.

## Selected robust calibration method

`platt`

Selection rule: methods with more than 5% of probabilities at the clipping bounds are rejected. Among admissible methods, mean date-level log score is primary and mean date-level Brier is secondary.

## Calibration-method comparison

| calibration_method   |   n_rows |   mean_brier |   mean_log_score |   n_dates |   mean_date_brier |   mean_date_log_score |   worst_date_log_score |   worst_row_log_score |   n_probabilities |   n_at_lower_clip |   n_at_upper_clip |   share_at_clip_bounds |   share_below_0_001 |   share_above_0_999 |   minimum_probability |   maximum_probability | passes_extreme_probability_guard   | selection_reason                                                                          |   calibration_rank | selected   |
|:---------------------|---------:|-------------:|-----------------:|----------:|------------------:|----------------------:|-----------------------:|----------------------:|------------------:|------------------:|------------------:|-----------------------:|--------------------:|--------------------:|----------------------:|----------------------:|:-----------------------------------|:------------------------------------------------------------------------------------------|-------------------:|:-----------|
| platt                |      594 |    0.074984  |         0.267873 |        14 |         0.0756244 |              0.272354 |               0.526932 |               4.90926 |               594 |                 0 |                 0 |                0       |            0        |                   0 |           0.00281752  |              0.729266 | True                               | Admissible methods ranked by mean date-level log score first, then mean date-level Brier. |                  1 | True       |
| identity             |      594 |    0.0797326 |         0.287545 |        14 |         0.0803002 |              0.294776 |               0.721674 |               6.88382 |               594 |                 0 |                 0 |                0       |            0.111111 |                   0 |           0.000531525 |              0.915293 | True                               | Admissible methods ranked by mean date-level log score first, then mean date-level Brier. |                  2 | False      |
| isotonic             |      594 |    0.0747661 |         0.371903 |        14 |         0.0755841 |              0.387693 |               1.38103  |              13.8155  |               594 |               100 |                 0 |                0.16835 |            0.16835  |                   0 |           1e-06       |              0.75     | False                              | Admissible methods ranked by mean date-level log score first, then mean date-level Brier. |                  3 | False      |

## Calibrated CatBoost versus direct probability benchmarks

| model                     |   n_rows |   n_dates |   mean_brier |   mean_log_score |
|:--------------------------|---------:|----------:|-------------:|-----------------:|
| ecmwf_bias_fixed_sigma    |      594 |        14 |    0.0670441 |         0.215313 |
| ecmwf_bias_adaptive_sigma |      594 |        14 |    0.0695786 |         0.225495 |
| catboost_calibrated       |      594 |        14 |    0.074984  |         0.267873 |
| market                    |      594 |        14 |    0.0762167 |         0.249389 |
| ecmwf_raw                 |      594 |        14 |    0.0817109 |         0.292783 |

## Paired date-clustered bootstrap comparisons

| metric    | model_a             | model_b                   |   n_dates |   mean_difference_a_minus_b |   bootstrap_ci_2_5 |   bootstrap_ci_97_5 |
|:----------|:--------------------|:--------------------------|----------:|----------------------------:|-------------------:|--------------------:|
| brier     | catboost_calibrated | ecmwf_bias_adaptive_sigma |        14 |                  0.00488195 |        -0.00858986 |          0.0177263  |
| log_score | catboost_calibrated | ecmwf_bias_adaptive_sigma |        14 |                  0.0413468  |        -0.0148105  |          0.0947127  |
| brier     | catboost_calibrated | ecmwf_bias_fixed_sigma    |        14 |                  0.00782414 |        -0.00137169 |          0.0167137  |
| log_score | catboost_calibrated | ecmwf_bias_fixed_sigma    |        14 |                  0.0540156  |         0.0129212  |          0.100423   |
| brier     | catboost_calibrated | ecmwf_raw                 |        14 |                 -0.00615501 |        -0.0209258  |          0.00894792 |
| log_score | catboost_calibrated | ecmwf_raw                 |        14 |                 -0.0221465  |        -0.099687   |          0.0562691  |
| brier     | catboost_calibrated | market                    |        14 |                 -0.00166908 |        -0.010157   |          0.00744893 |
| log_score | catboost_calibrated | market                    |        14 |                  0.0170424  |        -0.016006   |          0.050704   |

Negative calibrated-CatBoost-minus-benchmark differences favour calibrated CatBoost.

## Event-book coherence and categorical scores

| book_model                |   n_books |   mean_abs_book_probability_error |   median_abs_book_probability_error |   mean_normalised_categorical_log_score |   mean_normalised_multiclass_brier |
|:--------------------------|----------:|----------------------------------:|------------------------------------:|----------------------------------------:|-----------------------------------:|
| ecmwf_bias_fixed_sigma    |        54 |                       3.74186e-16 |                         4.44089e-16 |                                 1.52219 |                           0.737485 |
| ecmwf_bias_adaptive_sigma |        54 |                       2.40548e-16 |                         2.22045e-16 |                                 1.6092  |                           0.765364 |
| market                    |        54 |                       0.0489444   |                         0.0485      |                                 1.83246 |                           0.830076 |
| catboost_calibrated       |        54 |                       0.142968    |                         0.11259     |                                 2.03683 |                           0.832689 |
| ecmwf_raw                 |        54 |                       4.19418e-16 |                         4.44089e-16 |                                 2.27459 |                           0.89882  |

Raw binary probabilities are scored directly at contract level. For categorical event-book diagnostics, probabilities are normalised within complete daily books.

## Integrity checks

| check                                          | passed   | detail                               |
|:-----------------------------------------------|:---------|:-------------------------------------|
| selected_oof_nonempty                          | True     | rows=935                             |
| calibration_panel_nonempty                     | True     | rows=2123                            |
| selected_calibrated_nonempty                   | True     | rows=594                             |
| exactly_one_calibration_method_selected        | True     | selected=1                           |
| calibrated_probabilities_in_unit_interval      | True     | checked                              |
| selected_calibration_extreme_probability_guard | True     | clip_share=0.000000, maximum=0.05    |
| calibration_uses_prior_dates_only              | True     | expanding-date design                |
| common_support_nonempty                        | True     | rows=2970, models=5                  |
| common_support_keys_unique                     | True     | duplicates=0                         |
| book_panel_nonempty                            | True     | rows=2970                            |
| scored_books_have_one_winner                   | True     | scored_books=270                     |
| normalised_books_sum_to_one                    | True     | checked scored books                 |
| final_holdout_still_sealed                     | True     | 20d reads development OOF files only |

## Methodological status

The isotonic method is retained as a diagnostic but cannot be selected when it produces excessive clipping or materially unstable log-score behaviour. 20d freezes the calibration and coherence procedure on development OOF data. No final-holdout score is reported here. The next locked step may train on all development dates and evaluate exactly once on the final chronological holdout.
