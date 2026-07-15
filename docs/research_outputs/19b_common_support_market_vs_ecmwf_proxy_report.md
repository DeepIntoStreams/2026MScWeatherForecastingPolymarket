# 19b common-support market versus ECMWF proxy comparison

Generated: `2026-07-15 00:23:57 UTC`

## Purpose

This step compares Polymarket-implied probabilities against the temporary ECMWF single-run Gaussian probability proxy on exactly common contract-date-decision rows.

## Methodological status

The ECMWF proxy is a deterministic point-forecast bridge, not a calibrated ensemble or AIFS probability. It is suitable as a first forecast-side baseline and a pipeline test.

## Main result

- Common contract-decision rows: `2635`
- Unique event dates: `67`
- Event-book categorical rows: `241`
- Event-book categorical ready rows: `236`
- Issue rows: `5`

## Binary common-support score by decision rule

| decision_rule   |   n |   market_mean_brier |   ecmwf_mean_brier |   market_mean_log_score |   ecmwf_mean_log_score |   market_median_brier |   ecmwf_median_brier |   market_median_log_score |   ecmwf_median_log_score |   mean_p_market |   mean_p_ecmwf_proxy |   outcome_rate |   market_minus_ecmwf_brier |   market_minus_ecmwf_log_score | brier_winner   | log_score_winner   |
|:----------------|----:|--------------------:|-------------------:|------------------------:|-----------------------:|----------------------:|---------------------:|--------------------------:|-------------------------:|----------------:|---------------------:|---------------:|---------------------------:|-------------------------------:|:---------------|:-------------------|
| 24h_prior       | 624 |           0.06818   |          0.0833175 |                0.215771 |               0.289234 |           0.000297625 |           0.00300136 |                0.0174005  |                0.0563425 |       0.0966683 |            0.091234  |      0.0929487 |                 -0.0151376 |                     -0.0734622 | market         | market             |
| 12h_prior       | 670 |           0.0657832 |          0.0833926 |                0.211461 |               0.29633  |           0.000280625 |           0.00338486 |                0.0168919  |                0.059848  |       0.0966351 |            0.0910386 |      0.0910448 |                 -0.0176093 |                     -0.0848696 | market         | market             |
| 6h_prior        | 648 |           0.0646408 |          0.081009  |                0.205653 |               0.279356 |           6.4e-05     |           0.00300136 |                0.00803217 |                0.0563425 |       0.0948827 |            0.0910451 |      0.0910494 |                 -0.0163682 |                     -0.0737028 | market         | market             |
| event_day_open  | 693 |           0.0659487 |          0.0815212 |                0.206661 |               0.282818 |           2.025e-05   |           0.00300136 |                0.00451016 |                0.0563425 |       0.0948651 |            0.0909091 |      0.0909091 |                 -0.0155725 |                     -0.0761573 | market         | market             |

## Binary common-support score by decision rule and event type

| decision_rule   | contract_event_type_v2   |   n |   market_mean_brier |   ecmwf_mean_brier |   market_mean_log_score |   ecmwf_mean_log_score |   market_median_brier |   ecmwf_median_brier |   market_median_log_score |   ecmwf_median_log_score |   mean_p_market |   mean_p_ecmwf_proxy |   outcome_rate |   market_minus_ecmwf_brier |   market_minus_ecmwf_log_score | brier_winner   | log_score_winner   |
|:----------------|:-------------------------|----:|--------------------:|-------------------:|------------------------:|-----------------------:|----------------------:|---------------------:|--------------------------:|-------------------------:|----------------:|---------------------:|---------------:|---------------------------:|-------------------------------:|:---------------|:-------------------|
| 24h_prior       | interior_bin             | 511 |         0.0754341   |        0.0928994   |             0.235309    |             0.325082   |           0.000576    |          0.010311    |               0.0242927   |              0.107076    |     0.0997622   |           0.105339   |      0.0998043 |               -0.0174652   |                   -0.0897733   | market         | market             |
| 24h_prior       | lower_tail_endpoint      |  57 |         6.03509e-06 |        4.93524e-05 |             0.00203811  |             0.00204617 |           2.25e-06    |          5.23424e-09 |               0.00150113  |              7.23507e-05 |     0.00203509  |           0.00202084 |      0         |               -4.33173e-05 |                   -8.05841e-06 | market         | market             |
| 24h_prior       | upper_tail               |  56 |         0.0713771   |        0.0806386   |             0.255039    |             0.254427   |           0.013225    |          0.000193306 |               0.122168    |              0.014001    |     0.164759    |           0.0533318  |      0.125     |               -0.00926157  |                    0.00061126  | market         | ecmwf_proxy        |
| 12h_prior       | interior_bin             | 548 |         0.0734573   |        0.0921356   |             0.234229    |             0.329496   |           0.000564125 |          0.010311    |               0.0240366   |              0.107076    |     0.101078    |           0.105984   |      0.0967153 |               -0.0186783   |                   -0.0952671   | market         | market             |
| 12h_prior       | lower_tail_endpoint      |  61 |         2.21475e-05 |        0.000193145 |             0.00176541  |             0.0041509  |           1e-06       |          8.92668e-09 |               0.0010005   |              9.44856e-05 |     0.0017541   |           0.00405023 |      0         |               -0.000170997 |                   -0.00238549  | market         | market             |
| 12h_prior       | upper_tail               |  61 |         0.0626036   |        0.0880482   |             0.21662     |             0.290566   |           0.005625    |          0.000137014 |               0.0779615   |              0.0117743   |     0.151598    |           0.0437659  |      0.131148  |               -0.0254446   |                   -0.0739461   | market         | market             |
| 6h_prior        | interior_bin             | 530 |         0.0730251   |        0.0889359   |             0.230214    |             0.3074     |           0.0001105   |          0.00857603  |               0.0105556   |              0.0971794   |     0.0982292   |           0.104496   |      0.0962264 |               -0.0159108   |                   -0.0771861   | market         | market             |
| 6h_prior        | lower_tail_endpoint      |  59 |         1.49153e-06 |        0.000928521 |             0.000966849 |             0.00571508 |           2.5e-07     |          5.23424e-09 |               0.000500125 |              7.23507e-05 |     0.000966102 |           0.00516531 |      0         |               -0.00092703  |                   -0.00474823  | market         | market             |
| 6h_prior        | upper_tail               |  59 |         0.0539629   |        0.0898815   |             0.189711    |             0.301077   |           0.00216225  |          0.000193306 |               0.0476159   |              0.014001    |     0.158737    |           0.0560913  |      0.135593  |               -0.0359187   |                   -0.111366    | market         | market             |
| event_day_open  | interior_bin             | 567 |         0.0728667   |        0.0887611   |             0.225116    |             0.30955    |           3.025e-05   |          0.00857603  |               0.00551518  |              0.0971794   |     0.0970203   |           0.105516   |      0.0952381 |               -0.0158944   |                   -0.0844341   | market         | market             |
| event_day_open  | lower_tail_endpoint      |  63 |         7.5e-07     |        6.44706e-05 |             0.000706725 |             0.00224346 |           2.5e-07     |          3.04335e-09 |               0.000500125 |              5.51681e-05 |     0.000706349 |           0.00221014 |      0         |               -6.37206e-05 |                   -0.00153673  | market         | market             |
| event_day_open  | upper_tail               |  63 |         0.069635    |        0.0978189   |             0.246517    |             0.322804   |           0.00416025  |          0.00027056  |               0.0666741   |              0.0165855   |     0.169627    |           0.0481428  |      0.142857  |               -0.0281838   |                   -0.076287    | market         | market             |

## Event-book categorical common-support score by decision rule

| decision_rule   |   n_books |   market_mean_total_book_probability |   ecmwf_mean_total_book_probability |   market_mean_abs_book_probability_error |   ecmwf_mean_abs_book_probability_error |   market_median_winning_probability_normalised |   ecmwf_median_winning_probability_normalised |   market_normalised_categorical_log_score |   ecmwf_normalised_categorical_log_score |   market_normalised_multiclass_brier |   ecmwf_normalised_multiclass_brier |   market_minus_ecmwf_normalised_log |   market_minus_ecmwf_normalised_brier | normalised_categorical_log_winner   | normalised_multiclass_brier_winner   |
|:----------------|----------:|-------------------------------------:|------------------------------------:|-----------------------------------------:|----------------------------------------:|-----------------------------------------------:|----------------------------------------------:|------------------------------------------:|-----------------------------------------:|-------------------------------------:|------------------------------------:|------------------------------------:|--------------------------------------:|:------------------------------------|:-------------------------------------|
| 24h_prior       |        55 |                              1.06729 |                                   1 |                                0.0705455 |                             4.54182e-16 |                                       0.249538 |                                      0.120525 |                                   1.50397 |                                  2.19815 |                             0.741986 |                            0.902117 |                           -0.694179 |                             -0.160131 | market                              | market                               |
| 12h_prior       |        60 |                              1.06098 |                                   1 |                                0.0658333 |                             4.29286e-16 |                                       0.27239  |                                      0.110865 |                                   1.48518 |                                  2.2704  |                             0.72058  |                            0.912117 |                           -0.78522  |                             -0.191537 | market                              | market                               |
| 6h_prior        |        58 |                              1.03919 |                                   1 |                                0.0476034 |                             4.49832e-16 |                                       0.308074 |                                      0.146991 |                                   1.42937 |                                  2.10041 |                             0.706354 |                            0.885554 |                           -0.671032 |                             -0.1792   | market                              | market                               |
| event_day_open  |        63 |                              1.04352 |                                   1 |                                0.0543889 |                             4.22942e-16 |                                       0.295827 |                                      0.140622 |                                   1.43431 |                                  2.16401 |                             0.721503 |                            0.896733 |                           -0.729699 |                             -0.175231 | market                              | market                               |

## Decision-rule rankings

| metric                           | decision_rule   |   market_value |   ecmwf_proxy_value | winner   |   winning_value | lower_better   |   rank |
|:---------------------------------|:----------------|---------------:|--------------------:|:---------|----------------:|:---------------|-------:|
| binary_mean_brier                | 6h_prior        |      0.0646408 |           0.081009  | market   |       0.0646408 | True           |      1 |
| binary_mean_brier                | 12h_prior       |      0.0657832 |           0.0833926 | market   |       0.0657832 | True           |      2 |
| binary_mean_brier                | event_day_open  |      0.0659487 |           0.0815212 | market   |       0.0659487 | True           |      3 |
| binary_mean_brier                | 24h_prior       |      0.06818   |           0.0833175 | market   |       0.06818   | True           |      4 |
| binary_mean_log_score            | 6h_prior        |      0.205653  |           0.279356  | market   |       0.205653  | True           |      1 |
| binary_mean_log_score            | event_day_open  |      0.206661  |           0.282818  | market   |       0.206661  | True           |      2 |
| binary_mean_log_score            | 12h_prior       |      0.211461  |           0.29633   | market   |       0.211461  | True           |      3 |
| binary_mean_log_score            | 24h_prior       |      0.215771  |           0.289234  | market   |       0.215771  | True           |      4 |
| normalised_categorical_log_score | 6h_prior        |      1.42937   |           2.10041   | market   |       1.42937   | True           |      1 |
| normalised_categorical_log_score | event_day_open  |      1.43431   |           2.16401   | market   |       1.43431   | True           |      2 |
| normalised_categorical_log_score | 12h_prior       |      1.48518   |           2.2704    | market   |       1.48518   | True           |      3 |
| normalised_categorical_log_score | 24h_prior       |      1.50397   |           2.19815   | market   |       1.50397   | True           |      4 |
| normalised_multiclass_brier      | 6h_prior        |      0.706354  |           0.885554  | market   |       0.706354  | True           |      1 |
| normalised_multiclass_brier      | 12h_prior       |      0.72058   |           0.912117  | market   |       0.72058   | True           |      2 |
| normalised_multiclass_brier      | event_day_open  |      0.721503  |           0.896733  | market   |       0.721503  | True           |      3 |
| normalised_multiclass_brier      | 24h_prior       |      0.741986  |           0.902117  | market   |       0.741986  | True           |      4 |

## Integrity checks

| check                                 | passed   | detail               |
|:--------------------------------------|:---------|:---------------------|
| market_input_nonempty                 | True     | rows=2921            |
| ecmwf_input_nonempty                  | True     | rows=3212            |
| common_support_nonempty               | True     | rows=2635            |
| common_rows_have_probabilities        | True     | missing=0            |
| common_probabilities_in_unit_interval | True     | checked both sources |
| common_rows_have_binary_outcome       | True     | bad=0                |
| market_ecmwf_outcomes_match           | True     | mismatches=0         |
| binary_summary_nonempty               | True     | rows=4               |
| categorical_panel_nonempty            | True     | rows=241             |
| some_categorical_books_ready          | True     | ready=236            |
| issue_table_written                   | True     | issue rows=5         |

## Interpretation

A negative value in `market_minus_ecmwf_brier` or `market_minus_ecmwf_log_score` means the market has the lower score and therefore performs better on common support. If the market beats this ECMWF proxy, the correct interpretation is not that weather forecasts are uninformative; it means this uncalibrated deterministic-to-Gaussian bridge has not yet caught up with market prices. The next step should add local bias correction and calibration.

## Issues requiring review

| issue_type                 | event_date   | decision_rule   | detail                |   n_contracts_common |   expected_n_contracts |   n_yes |
|:---------------------------|:-------------|:----------------|:----------------------|---------------------:|-----------------------:|--------:|
| categorical_book_not_ready | 2026-04-14   | 24h_prior       | common=7 expected=11  |                    7 |                     11 |       1 |
| categorical_book_not_ready | 2026-04-17   | 24h_prior       | common=6 expected=11  |                    6 |                     11 |       1 |
| categorical_book_not_ready | 2026-04-18   | 24h_prior       | common=6 expected=11  |                    6 |                     11 |       1 |
| categorical_book_not_ready | 2026-04-16   | 12h_prior       | common=10 expected=11 |                   10 |                     11 |       1 |
| categorical_book_not_ready | 2026-04-16   | 6h_prior        | common=10 expected=11 |                   10 |                     11 |       1 |

## Figures

- `figures/19b_common_support_market_vs_ecmwf/19b_binary_brier_market_vs_ecmwf.png`
- `figures/19b_common_support_market_vs_ecmwf/19b_binary_log_market_vs_ecmwf.png`
- `figures/19b_common_support_market_vs_ecmwf/19b_normalised_categorical_log_market_vs_ecmwf.png`
- `figures/19b_common_support_market_vs_ecmwf/19b_normalised_multiclass_brier_market_vs_ecmwf.png`
- `figures/19b_common_support_market_vs_ecmwf/19b_probability_scatter_market_vs_ecmwf.png`
- `figures/19b_common_support_market_vs_ecmwf/19b_paired_log_score_difference_boxplot.png`

## Output files

- `data/processed/19b_common_support_market_vs_ecmwf_panel.csv`
- `data/processed/19b_common_support_binary_score_summary.csv`
- `data/processed/19b_common_support_binary_score_by_event_type.csv`
- `data/processed/19b_common_support_score_differences_by_date.csv`
- `data/processed/19b_common_support_categorical_book_score_panel.csv`
- `data/processed/19b_common_support_categorical_score_summary.csv`
- `data/processed/19b_common_support_decision_rule_rankings.csv`
- `data/processed/19b_common_support_integrity_checks.csv`
- `data/processed/19b_common_support_issues.csv`
- `docs/research_outputs/19b_common_support_market_vs_ecmwf_proxy_report.md`
- `data/review_bundles/19b_review_bundle.zip`
