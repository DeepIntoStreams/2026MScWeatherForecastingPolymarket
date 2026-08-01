# Phase 9 — Exploratory Trading Strategy Laboratory

Generated: `2026-08-01T05:00:55.727818+00:00`

## Overall status: **PASSED**

## Interpretation boundary

Phase 9 is post hoc exploratory research. June is no longer an untouched holdout for new strategy selection. Long-only trades use observed raw YES prices. Short positions are synthetic short-YES positions under parity and must not be described as executable long-NO trades unless actual NO prices are later recovered. The objective is to search aggressively but transparently for robust monetisable structure, not to conceal unsuccessful trials.

## Provenance

```json
{
  "exploratory": true,
  "frozen_tag": "v70-empirical-synthesis-complete",
  "frozen_tag_commit": "cf5146d6a11022178548cea6187e8d075b9d174d",
  "generated_utc": "2026-08-01T04:52:52.446306+00:00",
  "head_descends_from_frozen_tag": true,
  "interpretation_boundary": "Phase 9 is post hoc exploratory research. June is no longer an untouched holdout for new strategy selection. Long-only trades use observed raw YES prices. Short positions are synthetic short-YES positions under parity and must not be described as executable long-NO trades unless actual NO prices are later recovered. The objective is to search aggressively but transparently for robust monetisable structure, not to conceal unsuccessful trials.",
  "primary_cost": 0.01,
  "working_branch": "edward-v70-empirical-finalisation",
  "working_commit": "8b843942e705c678b2bfe35b20c43c626049e105"
}
```

## Nested chronological walk-forward

| objective     |   outer_test_dates |   dates |   total_net_pnl |   mean_daily_net_pnl |   daily_pnl_sd |      sharpe |   opportunity_annualised_sharpe |   probabilistic_sharpe_vs_zero |   maximum_drawdown |   expected_shortfall_5pct |   positive_date_fraction |   active_dates |   position_count |   mean_positions_per_active_date |   total_entry_cash |   return_on_entry_cash |   profit_factor_date_level |   positive_outer_blocks |
|:--------------|-------------------:|--------:|----------------:|---------------------:|---------------:|------------:|--------------------------------:|-------------------------------:|-------------------:|--------------------------:|-------------------------:|---------------:|-----------------:|---------------------------------:|-------------------:|-----------------------:|---------------------------:|------------------------:|
| robust_sharpe |                 60 |      60 |        3.63102  |           0.0605169  |       0.306571 |  0.1974     |                        3.77131  |                       0.923123 |            1.298   |                 -0.626667 |                 0.4      |             43 |              103 |                          2.39535 |            21.519  |             0.168735   |                   1.73815  |                       4 |
| pure_sharpe   |                 60 |      60 |       -0.135361 |          -0.00225602 |       0.304599 | -0.00740652 |                       -0.141501 |                       0.477235 |            3.51934 |                 -0.701667 |                 0.483333 |             53 |               84 |                          1.58491 |            20.4071 |            -0.00663304 |                   0.978295 |                       3 |
| mean_pnl      |                 60 |      60 |        8.323    |           0.138717   |       0.798221 |  0.173782   |                        3.32011  |                       0.92415  |            4.5945  |                 -0.746833 |                 0.416667 |             56 |              216 |                          3.85714 |            70.677  |             0.117761   |                   1.54618  |                       3 |

The pre-registered primary selector produced total outer PnL 3.631016 and settlement-date Sharpe 0.197400.

## Candidate hierarchy

| candidate_role                          | strategy_id   | selection_status                 |   sharpe |   total_net_pnl | execution_track              |
|:----------------------------------------|:--------------|:---------------------------------|---------:|----------------:|:-----------------------------|
| full_sample_oracle_best_sharpe          | S040541       | post_hoc_in_sample_only          | 0.404202 |        5.52     | includes_synthetic_short_yes |
| best_observed_price_long_only           | S063204       | post_hoc_in_sample_only          | 0.27355  |        9.128    | observed_yes_long_only       |
| primary_nested_walkforward_selector     |               | pre_registered_selector          | 0.1974   |        3.63102  | changes_by_outer_fold        |
| best_post_hoc_outer_selector            |               | post_hoc_selector_comparison     | 0.1974   |        3.63102  | changes_by_outer_fold        |
| future_candidate_after_full_exploration | S051784       | requires_new_external_validation | 0.120636 |        0.408452 | includes_synthetic_short_yes |

## Bootstrap uncertainty

| series                     | objective     | method                |   block_length |   point_total_pnl |   total_pnl_lower_95 |   total_pnl_upper_95 |   point_sharpe |   sharpe_lower_95 |   sharpe_upper_95 |   positive_total_fraction |   positive_sharpe_fraction |   replications |
|:---------------------------|:--------------|:----------------------|---------------:|------------------:|---------------------:|---------------------:|---------------:|------------------:|------------------:|--------------------------:|---------------------------:|---------------:|
| primary_nested_walkforward | robust_sharpe | ordinary_date         |            nan |           3.63102 |            -1.06245  |              8.14028 |         0.1974 |        -0.0544573 |          0.493334 |                    0.9359 |                     0.9359 |          10000 |
| primary_nested_walkforward | robust_sharpe | circular_moving_block |              3 |           3.63102 |            -1.06141  |              8.19327 |         0.1974 |        -0.0543688 |          0.503091 |                    0.9383 |                     0.9383 |          10000 |
| primary_nested_walkforward | robust_sharpe | circular_moving_block |              5 |           3.63102 |            -0.614292 |              7.81211 |         0.1974 |        -0.0322977 |          0.474514 |                    0.9526 |                     0.9526 |          10000 |
| primary_nested_walkforward | robust_sharpe | circular_moving_block |              7 |           3.63102 |            -0.342136 |              7.68358 |         0.1974 |        -0.0177113 |          0.476291 |                    0.9631 |                     0.9631 |          10000 |

## Deflated Sharpe

| strategy_id   |   sharpe |   expected_maximum_sharpe_under_trials |   deflated_sharpe_probability |   probabilistic_sharpe_vs_zero |   trials |
|:--------------|---------:|---------------------------------------:|------------------------------:|-------------------------------:|---------:|
| S040766       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040856       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040541       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040586       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040631       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040676       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040721       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040901       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040811       | 0.404202 |                               0.555118 |                    0.00500855 |                              1 |    94500 |
| S040991       | 0.398453 |                               0.555118 |                    0.00333566 |                              1 |    94500 |
| S040946       | 0.398453 |                               0.555118 |                    0.00333566 |                              1 |    94500 |
| S041036       | 0.398453 |                               0.555118 |                    0.00333566 |                              1 |    94500 |
| S042971       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |
| S041891       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |
| S042431       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |
| S042521       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |
| S043061       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |
| S041441       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |
| S042476       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |
| S041936       | 0.374639 |                               0.555118 |                    0.00154532 |                              1 |    94500 |

## Probability of backtest overfitting

|      pbo |   combinations |   strategies_considered |   slices |
|---------:|---------------:|------------------------:|---------:|
| 0.738095 |            252 |                     500 |       10 |

## Reality check

|   strategies_considered | benchmark              |   observed_max_mean_pnl_advantage |   moving_block_length |   bootstrap_replications |   white_reality_check_p_value | reject_no_superior_strategy_at_5pct   |
|------------------------:|:-----------------------|----------------------------------:|----------------------:|-------------------------:|------------------------------:|:--------------------------------------|
|                     100 | phase7_frozen_strategy |                         0.0103247 |                     5 |                     3000 |                      0.478667 | False                                 |

## Concentration

|   positions |   winning_positions |   losing_positions |   total_weighted_net_pnl |   top1_absolute_share |   top5_absolute_share |   top10_absolute_share |   absolute_pnl_hhi |   effective_contributing_positions |
|------------:|--------------------:|-------------------:|-------------------------:|----------------------:|----------------------:|-----------------------:|-------------------:|-----------------------------------:|
|          14 |                  14 |                  0 |                     5.52 |             0.0815217 |              0.402174 |               0.764493 |          0.0727591 |                             13.744 |

## Observed long-only versus synthetic short-inclusive search

| strategy_id   | model   | decision_rule   | rule_filter   | side_mode   |   top_k | sizing_rule   | ranking_signal   |   edge_threshold | stability_filter   | execution_track              |   complexity_score |   dates |   total_net_pnl |   mean_daily_net_pnl |   daily_pnl_sd |   sharpe |   opportunity_annualised_sharpe |   probabilistic_sharpe_vs_zero |   maximum_drawdown |   expected_shortfall_5pct |   positive_date_fraction |   active_dates |   position_count |   mean_positions_per_active_date |   total_entry_cash |   return_on_entry_cash |   profit_factor_date_level |   gross_pnl_before_cost |   break_even_cost_per_position |
|:--------------|:--------|:----------------|:--------------|:------------|--------:|:--------------|:-----------------|-----------------:|:-------------------|:-----------------------------|-------------------:|--------:|----------------:|---------------------:|---------------:|---------:|--------------------------------:|-------------------------------:|-------------------:|--------------------------:|-------------------------:|---------------:|-----------------:|---------------------------------:|-------------------:|-----------------------:|---------------------------:|------------------------:|-------------------------------:|
| S063204       | matern  | event_day_open  | none          | long_only   |       3 | one_share     | edge             |             0.08 | robust_0.25c       | observed_yes_long_only       |                  2 |      97 |           9.128 |            0.0941031 |       0.344007 | 0.27355  |                         5.22617 |                       0.999704 |              1.184 |                   -0.2455 |                 0.175258 |             67 |              109 |                          1.62687 |              7.872 |               1.15955  |                    2.91745 |                  10.218 |                      0.0937431 |
| S040541       | matern  | 24h_prior       | none          | short_only  |       1 | one_share     | edge             |             0.2  | robust_0.10c       | includes_synthetic_short_yes |                  1 |      97 |           5.52  |            0.0569072 |       0.140789 | 0.404202 |                         7.72226 |                       1        |              0     |                    0      |                 0.14433  |             14 |               14 |                          1       |              8.48  |               0.650943 |                  nan       |                   5.66  |                      0.404286  |

## Thesis boundary

The thesis should retain Phase 9 only when nested walk-forward PnL and Sharpe are positive, multiple-testing diagnostics are credible, cost sensitivity is acceptable and concentration is not excessive. Any short-inclusive result remains synthetic.
