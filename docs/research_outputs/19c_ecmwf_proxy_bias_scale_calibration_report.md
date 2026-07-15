# 19c leakage-free ECMWF proxy bias and scale correction

Generated: `2026-07-15 01:28:19 UTC`

## Purpose

This step estimates Hong Kong local temperature bias and Gaussian residual scale using strictly prior event dates, then regenerates HKO contract-event probabilities out of sample.

## Methodological status

The source forecast remains a deterministic ECMWF IFS HRES point forecast obtained through the temporary Open-Meteo single-runs route. The corrected probabilities are expanding-window Gaussian post-processing proxies. They are not ECMWF ENS, AIFS ENS or calibrated AIFS-CRPS probabilities.

## Leakage-control design

- Parameters are estimated separately for each decision rule.
- A date becomes score-ready only after at least `14` admissible historical forecast dates.
- An HKO outcome is conservatively assumed usable only `24` hours after the end of its local day.
- Historical outcomes must be available no later than the current decision cutoff.
- All contracts from the same event date share the same temperature forecast and the same fitted parameters.
- Bias and scale are fitted on unique date-level forecast errors, not repeated contract rows.
- The additive correction is the negative expanding mean forecast error.
- The Gaussian scale is the expanding root-mean-square residual after bias correction, clipped ex ante to `[0.5, 3.0]` °C.
- The original raw proxy continues to use sigma `1.5` °C.
- Log scores use probability clipping epsilon `1e-06` only inside the logarithm.

## Sample

- Input 19a calibration-panel contract rows: `3212`
- Input 19b common-support contract rows: `2635`
- Unique 19a date-decision forecasts: `256`
- Out-of-sample date-decision forecasts: `193`
- Out-of-sample contract rows: `1975`

### Out-of-sample rows by decision rule

| decision_rule   |   n |
|:----------------|----:|
| 24h_prior       | 470 |
| 12h_prior       | 494 |
| 6h_prior        | 483 |
| event_day_open  | 528 |

## Expanding parameter summary

| decision_rule   |   mean_bias_correction_C |   final_bias_correction_C |   mean_sigma_used_C |   final_sigma_used_C |   n_scored_dates |
|:----------------|-------------------------:|--------------------------:|--------------------:|---------------------:|-----------------:|
| 12h_prior       |                  1.71156 |                   1.80833 |            1.0231   |              1.07444 |               47 |
| 24h_prior       |                  1.71476 |                   1.79683 |            0.930322 |              1.12743 |               50 |
| 6h_prior        |                  1.4933  |                   1.59492 |            0.97686  |              1.06507 |               46 |
| event_day_open  |                  1.60947 |                   1.68095 |            0.892896 |              0.9788  |               50 |

## Temperature error summary

| decision_rule   | model                            |   n_dates |   mean_error_C |    mae_C |   rmse_C |   median_error_C |
|:----------------|:---------------------------------|----------:|---------------:|---------:|---------:|-----------------:|
| 24h_prior       | ecmwf_raw_temperature            |        50 |      -1.852    | 1.936    |  2.21106 |        -1.95     |
| 24h_prior       | ecmwf_bias_corrected_temperature |        50 |      -0.137235 | 0.969432 |  1.23282 |        -0.252632 |
| 12h_prior       | ecmwf_raw_temperature            |        47 |      -1.92979  | 1.99362  |  2.251   |        -2.1      |
| 12h_prior       | ecmwf_bias_corrected_temperature |        47 |      -0.218231 | 0.962986 |  1.19837 |        -0.32     |
| 6h_prior        | ecmwf_raw_temperature            |        46 |      -1.72391  | 1.83696  |  2.0696  |        -1.9      |
| 6h_prior        | ecmwf_bias_corrected_temperature |        46 |      -0.230617 | 0.986001 |  1.18118 |        -0.400686 |
| event_day_open  | ecmwf_raw_temperature            |        50 |      -1.774    | 1.842    |  2.03612 |        -1.8      |
| event_day_open  | ecmwf_bias_corrected_temperature |        50 |      -0.164525 | 0.789787 |  1.02967 |        -0.116877 |

## Gaussian interval calibration summary

| decision_rule   | model                  |   n_dates |   mean_standardised_error |   std_standardised_error |   mean_sigma_C |   coverage_50 |   coverage_80 |   coverage_90 |
|:----------------|:-----------------------|----------:|--------------------------:|-------------------------:|---------------:|--------------:|--------------:|--------------:|
| 24h_prior       | ecmwf_bias_fixed_sigma |        50 |                -0.0914901 |                 0.816773 |       1.5      |      0.58     |      0.88     |      0.96     |
| 24h_prior       | ecmwf_bias_scale       |        50 |                -0.177908  |                 1.31455  |       0.930322 |      0.4      |      0.68     |      0.74     |
| 12h_prior       | ecmwf_bias_fixed_sigma |        47 |                -0.145487  |                 0.785554 |       1.5      |      0.595745 |      0.87234  |      1        |
| 12h_prior       | ecmwf_bias_scale       |        47 |                -0.218072  |                 1.17057  |       1.0231   |      0.425532 |      0.638298 |      0.765957 |
| 6h_prior        | ecmwf_bias_fixed_sigma |        46 |                -0.153745  |                 0.772297 |       1.5      |      0.5      |      0.913043 |      1        |
| 6h_prior        | ecmwf_bias_scale       |        46 |                -0.237536  |                 1.24035  |       0.97686  |      0.369565 |      0.673913 |      0.782609 |
| event_day_open  | ecmwf_bias_fixed_sigma |        50 |                -0.109683  |                 0.677625 |       1.5      |      0.68     |      0.92     |      0.98     |
| event_day_open  | ecmwf_bias_scale       |        50 |                -0.195388  |                 1.1535   |       0.892896 |      0.5      |      0.76     |      0.78     |

## Binary common-support score summary

| decision_rule   | model                  | model_label                     |   n |   mean_brier |   mean_log_score |   median_brier |   median_log_score |   mean_probability |   outcome_rate |   brier_rank_within_rule |   log_rank_within_rule |
|:----------------|:-----------------------|:--------------------------------|----:|-------------:|-----------------:|---------------:|-------------------:|-------------------:|---------------:|-------------------------:|-----------------------:|
| 24h_prior       | market                 | Market                          | 470 |    0.0682025 |         0.214388 |    0.0001825   |         0.0135921  |          0.0952926 |      0.093617  |                        3 |                      3 |
| 24h_prior       | ecmwf_raw              | ECMWF raw proxy                 | 470 |    0.0855388 |         0.301525 |    0.00300216  |         0.0563503  |          0.0913405 |      0.093617  |                        4 |                      4 |
| 24h_prior       | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 | 470 |    0.0673316 |         0.213515 |    0.00101249  |         0.0323361  |          0.0904758 |      0.093617  |                        2 |                      2 |
| 24h_prior       | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  | 470 |    0.0666556 |         0.210936 |    1.34777e-06 |         0.00115914 |          0.090774  |      0.093617  |                        1 |                      1 |
| 12h_prior       | market                 | Market                          | 494 |    0.0649575 |         0.208599 |    0.00011025  |         0.0105555  |          0.0946984 |      0.0910931 |                        1 |                      1 |
| 12h_prior       | ecmwf_raw              | ECMWF raw proxy                 | 494 |    0.0842451 |         0.306047 |    0.00376675  |         0.063338   |          0.0910848 |      0.0910931 |                        4 |                      4 |
| 12h_prior       | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 | 494 |    0.0649818 |         0.208887 |    0.00109519  |         0.0336528  |          0.0910928 |      0.0910931 |                        2 |                      3 |
| 12h_prior       | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  | 494 |    0.0656465 |         0.208818 |    1.81102e-05 |         0.00426468 |          0.0910931 |      0.0910931 |                        3 |                      2 |
| 6h_prior        | market                 | Market                          | 483 |    0.0649904 |         0.207071 |    4.225e-05   |         0.00652122 |          0.0940818 |      0.0910973 |                        1 |                      1 |
| 6h_prior        | ecmwf_raw              | ECMWF raw proxy                 | 483 |    0.0820888 |         0.288043 |    0.00300136  |         0.0563425  |          0.0910915 |      0.0910973 |                        4 |                      4 |
| 6h_prior        | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 | 483 |    0.0661067 |         0.2106   |    0.00105925  |         0.0330875  |          0.091097  |      0.0910973 |                        2 |                      2 |
| 6h_prior        | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  | 483 |    0.0678299 |         0.217192 |    6.26856e-06 |         0.00250685 |          0.0910973 |      0.0910973 |                        3 |                      3 |
| event_day_open  | market                 | Market                          | 528 |    0.0640202 |         0.198893 |    1.6e-05     |         0.00400802 |          0.0942519 |      0.0909091 |                        3 |                      2 |
| event_day_open  | ecmwf_raw              | ECMWF raw proxy                 | 528 |    0.0822973 |         0.288425 |    0.00376675  |         0.063338   |          0.0909091 |      0.0909091 |                        4 |                      4 |
| event_day_open  | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 | 528 |    0.0632692 |         0.203803 |    0.00133472  |         0.0372178  |          0.0909091 |      0.0909091 |                        2 |                      3 |
| event_day_open  | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  | 528 |    0.061106  |         0.197323 |    2.45462e-06 |         0.00156735 |          0.0909091 |      0.0909091 |                        1 |                      1 |

### Best binary Brier model within each decision rule

| decision_rule   | model            |   n |   mean_brier |   mean_log_score |
|:----------------|:-----------------|----:|-------------:|-----------------:|
| 12h_prior       | market           | 494 |    0.0649575 |         0.208599 |
| 24h_prior       | ecmwf_bias_scale | 470 |    0.0666556 |         0.210936 |
| 6h_prior        | market           | 483 |    0.0649904 |         0.207071 |
| event_day_open  | ecmwf_bias_scale | 528 |    0.061106  |         0.197323 |

## Event-book categorical score summary

| decision_rule   | model                  | model_label                     |   n_books |   mean_total_book_probability |   mean_abs_book_probability_error |   median_winning_probability_normalised |   mean_normalised_categorical_log_score |   mean_normalised_multiclass_brier |   categorical_log_rank_within_rule |   multiclass_brier_rank_within_rule |
|:----------------|:-----------------------|:--------------------------------|----------:|------------------------------:|----------------------------------:|----------------------------------------:|----------------------------------------:|-----------------------------------:|-----------------------------------:|------------------------------------:|
| 24h_prior       | market                 | Market                          |        41 |                       1.05287 |                       0.0558659   |                                0.275315 |                                 1.48616 |                           0.737485 |                                  3 |                                   3 |
| 24h_prior       | ecmwf_raw              | ECMWF raw proxy                 |        41 |                       1       |                       4.60336e-16 |                                0.120525 |                                 2.31587 |                           0.922671 |                                  4 |                                   4 |
| 24h_prior       | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 |        41 |                       1       |                       8.12358e-18 |                                0.239102 |                                 1.4732  |                           0.724487 |                                  2 |                                   2 |
| 24h_prior       | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  |        41 |                       1       |                       1.08314e-17 |                                0.291658 |                                 1.45125 |                           0.720686 |                                  1 |                                   1 |
| 12h_prior       | market                 | Market                          |        44 |                       1.03851 |                       0.045125    |                                0.310506 |                                 1.46328 |                           0.709067 |                                  3 |                                   3 |
| 12h_prior       | ecmwf_raw              | ECMWF raw proxy                 |        44 |                       1       |                       4.1381e-16  |                                0.106204 |                                 2.364   |                           0.919798 |                                  4 |                                   4 |
| 12h_prior       | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 |        44 |                       1       |                       1.00929e-17 |                                0.239301 |                                 1.46218 |                           0.709055 |                                  2 |                                   2 |
| 12h_prior       | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  |        44 |                       1       |                       5.04647e-18 |                                0.304439 |                                 1.42829 |                           0.708954 |                                  1 |                                   1 |
| 6h_prior        | market                 | Market                          |        43 |                       1.02862 |                       0.0312907   |                                0.35461  |                                 1.44515 |                           0.705591 |                                  1 |                                   1 |
| 6h_prior        | ecmwf_raw              | ECMWF raw proxy                 |        43 |                       1       |                       4.49253e-16 |                                0.120525 |                                 2.18196 |                           0.895749 |                                  4 |                                   4 |
| 6h_prior        | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 |        43 |                       1       |                       5.16383e-18 |                                0.240755 |                                 1.46902 |                           0.721401 |                                  2 |                                   2 |
| 6h_prior        | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  |        43 |                       1       |                       1.80734e-17 |                                0.266525 |                                 1.48004 |                           0.730924 |                                  3 |                                   3 |
| event_day_open  | market                 | Market                          |        48 |                       1.03677 |                       0.0459375   |                                0.34797  |                                 1.36857 |                           0.700309 |                                  1 |                                   3 |
| event_day_open  | ecmwf_raw              | ECMWF raw proxy                 |        48 |                       1       |                       4.23273e-16 |                                0.135544 |                                 2.2215  |                           0.90527  |                                  4 |                                   4 |
| event_day_open  | ecmwf_bias_fixed_sigma | ECMWF bias corrected, sigma=1.5 |        48 |                       1       |                       6.93889e-18 |                                0.249383 |                                 1.43089 |                           0.695961 |                                  3 |                                   2 |
| event_day_open  | ecmwf_bias_scale       | ECMWF bias-and-scale corrected  |        48 |                       1       |                       6.93889e-18 |                                0.353717 |                                 1.3811  |                           0.672166 |                                  2 |                                   1 |

### Best categorical log-score model within each decision rule

| decision_rule   | model            |   n_books |   mean_normalised_categorical_log_score |   mean_normalised_multiclass_brier |
|:----------------|:-----------------|----------:|----------------------------------------:|-----------------------------------:|
| 12h_prior       | ecmwf_bias_scale |        44 |                                 1.42829 |                           0.708954 |
| 24h_prior       | ecmwf_bias_scale |        41 |                                 1.45125 |                           0.720686 |
| 6h_prior        | market           |        43 |                                 1.44515 |                           0.705591 |
| event_day_open  | market           |        48 |                                 1.36857 |                           0.700309 |

## Date-clustered paired comparisons

Differences are defined as `model_a - model_b`; negative values favour model A because lower scores are better. Confidence intervals resample event dates, not individual contracts.

| decision_rule   | metric   | model_a                | model_b          | difference_definition   |   n_dates |   mean_difference |   bootstrap_ci_2_5 |   bootstrap_ci_97_5 | lower_score_better   | favours_model_a   | favours_model_b   |
|:----------------|:---------|:-----------------------|:-----------------|:------------------------|----------:|------------------:|-------------------:|--------------------:|:---------------------|:------------------|:------------------|
| 24h_prior       | brier    | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.0182925   |        -0.0243826  |         -0.011545   | True                 | True              | False             |
| 24h_prior       | log      | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.0881548   |        -0.112453   |         -0.0609747  | True                 | True              | False             |
| 24h_prior       | brier    | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.0193088   |        -0.0271432  |         -0.0103374  | True                 | True              | False             |
| 24h_prior       | log      | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.0920349   |        -0.121197   |         -0.0576238  | True                 | True              | False             |
| 24h_prior       | brier    | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        44 |       0.00152186  |        -0.00555047 |          0.00839652 | True                 | False             | False             |
| 24h_prior       | log      | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        44 |       0.00380668  |        -0.0291668  |          0.0309998  | True                 | False             | False             |
| 12h_prior       | brier    | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        45 |      -0.0192735   |        -0.0250195  |         -0.0131257  | True                 | True              | False             |
| 12h_prior       | log      | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        45 |      -0.0973975   |        -0.120224   |         -0.0730953  | True                 | True              | False             |
| 12h_prior       | brier    | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        45 |      -0.0185429   |        -0.0255258  |         -0.0108826  | True                 | True              | False             |
| 12h_prior       | log      | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        45 |      -0.0971368   |        -0.119048   |         -0.072367   | True                 | True              | False             |
| 12h_prior       | brier    | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        45 |      -0.000780154 |        -0.0081973  |          0.00676006 | True                 | False             | False             |
| 12h_prior       | log      | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        45 |      -0.00065812  |        -0.0268168  |          0.0253588  | True                 | False             | False             |
| 6h_prior        | brier    | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.015995    |        -0.0213995  |         -0.00994592 | True                 | True              | False             |
| 6h_prior        | log      | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.077653    |        -0.0989412  |         -0.0544427  | True                 | True              | False             |
| 6h_prior        | brier    | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.014188    |        -0.0214909  |         -0.00614217 | True                 | True              | False             |
| 6h_prior        | log      | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        44 |      -0.0705358   |        -0.0969601  |         -0.0369932  | True                 | True              | False             |
| 6h_prior        | brier    | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        44 |      -0.00292268  |        -0.0130277  |          0.00690425 | True                 | False             | False             |
| 6h_prior        | log      | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        44 |      -0.0107111   |        -0.0486559  |          0.0258903  | True                 | False             | False             |
| event_day_open  | brier    | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        48 |      -0.0190281   |        -0.0237739  |         -0.0138018  | True                 | True              | False             |
| event_day_open  | log      | ecmwf_bias_fixed_sigma | ecmwf_raw        | model_a_minus_model_b   |        48 |      -0.0846211   |        -0.104404   |         -0.0640084  | True                 | True              | False             |
| event_day_open  | brier    | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        48 |      -0.0211912   |        -0.0276451  |         -0.0142111  | True                 | True              | False             |
| event_day_open  | log      | ecmwf_bias_scale       | ecmwf_raw        | model_a_minus_model_b   |        48 |      -0.0911019   |        -0.112723   |         -0.063676   | True                 | True              | False             |
| event_day_open  | brier    | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        48 |       0.00291415  |        -0.00679945 |          0.0118639  | True                 | False             | False             |
| event_day_open  | log      | market                 | ecmwf_bias_scale | model_a_minus_model_b   |        48 |       0.00157015  |        -0.027128   |          0.0294782  | True                 | False             | False             |

## Integrity checks

| check                                         | passed   | detail                                               |
|:----------------------------------------------|:---------|:-----------------------------------------------------|
| common_input_nonempty                         | True     | rows=2635                                            |
| date_level_parameters_nonempty                | True     | rows=256                                             |
| some_out_of_sample_dates_ready                | True     | ready_date_rules=193                                 |
| training_uses_only_available_outcomes         | True     | last assumed outcome availability <= decision cutoff |
| training_uses_strictly_earlier_event_dates    | True     | training_end_date < event_date                       |
| corrected_probabilities_present_on_ready_rows | True     | ready_rows=1975                                      |
| all_ready_probabilities_in_unit_interval      | True     | checked all four models                              |
| adaptive_sigma_within_bounds                  | True     | bounds=[0.5,3.0]                                     |
| binary_summary_complete                       | True     | rows=16                                              |
| categorical_panel_nonempty                    | True     | rows=241                                             |
| some_categorical_books_ready                  | True     | ready=176                                            |
| categorical_ready_books_have_one_winner       | True     | checked ready books                                  |
| gaussian_complete_books_sum_to_one            | True     | raw and corrected Gaussian books                     |
| categorical_summary_complete                  | True     | rows=16                                              |

## Issues requiring review

| issue_type                 | decision_rule   |   n_warmup_date_rules | first_event_date   | last_warmup_event_date   | event_date   | detail                                       |   n_contracts_common |   expected_n_contracts |   n_yes |
|:---------------------------|:----------------|----------------------:|:-------------------|:-------------------------|:-------------|:---------------------------------------------|---------------------:|-----------------------:|--------:|
| calibration_warmup_summary | 12h_prior       |                    16 | 2026-03-18         | 2026-04-12               | nan          | nan                                          |                  nan |                    nan |     nan |
| calibration_warmup_summary | 24h_prior       |                    16 | 2026-03-16         | 2026-04-09               | nan          | nan                                          |                  nan |                    nan |     nan |
| calibration_warmup_summary | 6h_prior        |                    16 | 2026-03-17         | 2026-04-13               | nan          | nan                                          |                  nan |                    nan |     nan |
| calibration_warmup_summary | event_day_open  |                    15 | 2026-03-22         | 2026-04-09               | nan          | nan                                          |                  nan |                    nan |     nan |
| categorical_book_not_ready | 24h_prior       |                   nan | nan                | nan                      | 2026-04-18   | incomplete_common_book common=6 expected=11  |                    6 |                     11 |       1 |
| categorical_book_not_ready | 24h_prior       |                   nan | nan                | nan                      | 2026-04-17   | incomplete_common_book common=6 expected=11  |                    6 |                     11 |       1 |
| categorical_book_not_ready | 24h_prior       |                   nan | nan                | nan                      | 2026-04-14   | incomplete_common_book common=7 expected=11  |                    7 |                     11 |       1 |
| categorical_book_not_ready | 12h_prior       |                   nan | nan                | nan                      | 2026-04-16   | incomplete_common_book common=10 expected=11 |                   10 |                     11 |       1 |
| categorical_book_not_ready | 6h_prior        |                   nan | nan                | nan                      | 2026-04-16   | incomplete_common_book common=10 expected=11 |                   10 |                     11 |       1 |

## Interpretation rule

A post-processed proxy improves on the raw proxy only when it achieves lower out-of-sample proper scores on the same rows. A lower temperature MAE by itself is not sufficient. The market comparison remains a paired common-support comparison and does not imply that deterministic ECMWF forecasts are intrinsically uninformative.

## Figures

- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_temperature_mean_error_raw_vs_corrected.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_temperature_mae_raw_vs_corrected.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_binary_brier_model_comparison.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_binary_log_model_comparison.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_normalised_categorical_log_model_comparison.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_normalised_multiclass_brier_model_comparison.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_expanding_bias_correction_path.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_expanding_sigma_path.png`
- `figures/19c_ecmwf_proxy_bias_scale_calibration/19c_paired_log_score_improvement_bootstrap.png`

## Output files

- `data/processed/19c_expanding_bias_scale_parameter_path.csv`
- `data/processed/19c_common_support_calibrated_probability_panel.csv`
- `data/processed/19c_temperature_error_summary.csv`
- `data/processed/19c_gaussian_calibration_summary.csv`
- `data/processed/19c_binary_score_summary.csv`
- `data/processed/19c_binary_score_by_event_type.csv`
- `data/processed/19c_date_level_score_panel.csv`
- `data/processed/19c_paired_date_level_comparisons.csv`
- `data/processed/19c_categorical_book_score_panel.csv`
- `data/processed/19c_categorical_score_summary.csv`
- `data/processed/19c_decision_rule_rankings.csv`
- `data/processed/19c_integrity_checks.csv`
- `data/processed/19c_issues.csv`
