# 21a simple edge-based trading simulation

## Status

This trading layer uses the frozen 20e locked final-holdout probabilities and does not alter the forecasting specification.

## Prespecified rule

- threshold grid: [0.0, 0.02, 0.05, 0.1]
- primary threshold: 0.05
- trade cost per contract: 0.0
- position size: one unit per trade

## Execution assumptions

The observed Polymarket YES probability is used as a frictionless execution proxy. The simulation excludes bid-ask spread, fees, slippage, liquidity constraints, partial fills, market impact, capital limits, and position netting.

## Primary standalone model × decision-rule strategies

| model                     | decision_rule   |   threshold |   n_opportunities |   n_dates |   n_trades |   n_yes_trades |   n_no_trades |   trade_rate |   mean_absolute_edge_all |   mean_absolute_edge_trades |   total_net_pnl |   mean_net_pnl_per_opportunity |   mean_net_pnl_per_trade |   median_net_pnl_per_trade |   hit_rate_trades | strategy_scope           |
|:--------------------------|:----------------|------------:|------------------:|----------:|-----------:|---------------:|--------------:|-------------:|-------------------------:|----------------------------:|----------------:|-------------------------------:|-------------------------:|---------------------------:|------------------:|:-------------------------|
| ecmwf_bias_fixed_sigma    | 24h_prior       |        0.05 |               110 |        10 |         25 |             10 |            15 |     0.227273 |                0.02911   |                   0.0974214 |          2.4515 |                     0.0222864  |               0.09806    |                    0.215   |         0.6       | standalone_decision_rule |
| catboost_platt            | 6h_prior        |        0.05 |               110 |        10 |         51 |             47 |             4 |     0.463636 |                0.104841  |                   0.190811  |          2.186  |                     0.0198727  |               0.0428627  |                   -0.025   |         0.176471  | standalone_decision_rule |
| ecmwf_bias_adaptive_sigma | 24h_prior       |        0.05 |               110 |        10 |         22 |              9 |            13 |     0.2      |                0.0246872 |                   0.0918569 |          2.05   |                     0.0186364  |               0.0931818  |                    0.2125  |         0.636364  | standalone_decision_rule |
| ecmwf_bias_adaptive_sigma | event_day_open  |        0.05 |               110 |        10 |         30 |             16 |            14 |     0.272727 |                0.0452317 |                   0.151622  |          1.6165 |                     0.0146955  |               0.0538833  |                   -0.0645  |         0.366667  | standalone_decision_rule |
| ecmwf_bias_adaptive_sigma | 6h_prior        |        0.05 |               110 |        10 |         34 |             18 |            16 |     0.309091 |                0.0531523 |                   0.159162  |          1.101  |                     0.0100091  |               0.0323824  |                   -0.029   |         0.382353  | standalone_decision_rule |
| catboost_raw              | event_day_open  |        0.05 |               110 |        10 |         43 |             38 |             5 |     0.390909 |                0.118403  |                   0.282239  |          1.0845 |                     0.00985909 |               0.0252209  |                   -0.06    |         0.255814  | standalone_decision_rule |
| ecmwf_bias_fixed_sigma    | 12h_prior       |        0.05 |               110 |        10 |         30 |             15 |            15 |     0.272727 |                0.0410946 |                   0.127695  |          1.0645 |                     0.00967727 |               0.0354833  |                   -0.01375 |         0.433333  | standalone_decision_rule |
| ecmwf_bias_fixed_sigma    | 6h_prior        |        0.05 |               110 |        10 |         41 |             25 |            16 |     0.372727 |                0.0560912 |                   0.139427  |          1.0115 |                     0.00919545 |               0.0246707  |                   -0.03    |         0.292683  | standalone_decision_rule |
| ecmwf_bias_adaptive_sigma | 12h_prior       |        0.05 |               110 |        10 |         32 |             16 |            16 |     0.290909 |                0.0400911 |                   0.12356   |          0.971  |                     0.00882727 |               0.0303437  |                   -0.03    |         0.46875   | standalone_decision_rule |
| ecmwf_bias_fixed_sigma    | event_day_open  |        0.05 |               110 |        10 |         41 |             25 |            16 |     0.372727 |                0.052286  |                   0.130298  |          0.6055 |                     0.00550455 |               0.0147683  |                   -0.02    |         0.268293  | standalone_decision_rule |
| catboost_platt            | event_day_open  |        0.05 |               110 |        10 |         50 |             44 |             6 |     0.454545 |                0.102364  |                   0.186357  |          0.364  |                     0.00330909 |               0.00728    |                   -0.0175  |         0.14      | standalone_decision_rule |
| catboost_raw              | 6h_prior        |        0.05 |               110 |        10 |         43 |             40 |             3 |     0.390909 |                0.127519  |                   0.308838  |          0.1685 |                     0.00153182 |               0.0039186  |                   -0.065   |         0.209302  | standalone_decision_rule |
| ecmwf_raw                 | 6h_prior        |        0.05 |               110 |        10 |         60 |             38 |            22 |     0.545455 |                0.112672  |                   0.199852  |          0.142  |                     0.00129091 |               0.00236667 |                   -0.00375 |         0.25      | standalone_decision_rule |
| ecmwf_raw                 | event_day_open  |        0.05 |               110 |        10 |         56 |             36 |            20 |     0.509091 |                0.113358  |                   0.214333  |         -0.7265 |                    -0.00660455 |              -0.0129732  |                   -0.00275 |         0.214286  | standalone_decision_rule |
| ecmwf_raw                 | 24h_prior       |        0.05 |               110 |        10 |         53 |             29 |            24 |     0.481818 |                0.0876972 |                   0.17053   |         -1.313  |                    -0.0119364  |              -0.0247736  |                   -0.0075  |         0.301887  | standalone_decision_rule |
| catboost_raw              | 24h_prior       |        0.05 |               110 |        10 |         46 |             41 |             5 |     0.418182 |                0.120315  |                   0.271311  |         -1.493  |                    -0.0135727  |              -0.0324565  |                   -0.085   |         0.23913   | standalone_decision_rule |
| catboost_raw              | 12h_prior       |        0.05 |               110 |        10 |         44 |             42 |             2 |     0.4      |                0.12441   |                   0.293815  |         -1.962  |                    -0.0178364  |              -0.0445909  |                   -0.0725  |         0.181818  | standalone_decision_rule |
| ecmwf_raw                 | 12h_prior       |        0.05 |               110 |        10 |         59 |             34 |            25 |     0.536364 |                0.0998983 |                   0.179277  |         -2.0805 |                    -0.0189136  |              -0.0352627  |                   -0.0075  |         0.271186  | standalone_decision_rule |
| catboost_platt            | 24h_prior       |        0.05 |               110 |        10 |         49 |             45 |             4 |     0.445455 |                0.092396  |                   0.169659  |         -2.0885 |                    -0.0189864  |              -0.0426224  |                   -0.039   |         0.122449  | standalone_decision_rule |
| catboost_platt            | 12h_prior       |        0.05 |               110 |        10 |         51 |             46 |             5 |     0.463636 |                0.0999295 |                   0.178108  |         -3.2535 |                    -0.0295773  |              -0.0637941  |                   -0.055   |         0.0980392 | standalone_decision_rule |

## Pooled diagnostic only

The following table pools decision rules only as a descriptive diagnostic and is not an implementable portfolio.

| model                     |   threshold |   n_opportunities |   n_dates |   n_decision_rules |   n_trades |   trade_rate |   total_net_pnl |   mean_net_pnl_per_opportunity |   mean_net_pnl_per_trade |   hit_rate_trades | is_primary_threshold   | strategy_scope                               |
|:--------------------------|------------:|------------------:|----------:|-------------------:|-----------:|-------------:|----------------:|-------------------------------:|-------------------------:|------------------:|:-----------------------|:---------------------------------------------|
| catboost_platt            |        0.05 |               440 |        10 |                  4 |        201 |     0.456818 |         -2.792  |                    -0.00634545 |               -0.0138905 |          0.134328 | True                   | pooled_across_decision_rules_diagnostic_only |
| catboost_raw              |        0.05 |               440 |        10 |                  4 |        176 |     0.4      |         -2.202  |                    -0.00500455 |               -0.0125114 |          0.221591 | True                   | pooled_across_decision_rules_diagnostic_only |
| ecmwf_bias_adaptive_sigma |        0.05 |               440 |        10 |                  4 |        118 |     0.268182 |          5.7385 |                     0.013042   |                0.0486314 |          0.449153 | True                   | pooled_across_decision_rules_diagnostic_only |
| ecmwf_bias_fixed_sigma    |        0.05 |               440 |        10 |                  4 |        137 |     0.311364 |          5.133  |                     0.0116659  |                0.0374672 |          0.372263 | True                   | pooled_across_decision_rules_diagnostic_only |
| ecmwf_raw                 |        0.05 |               440 |        10 |                  4 |        228 |     0.518182 |         -3.978  |                    -0.00904091 |               -0.0174474 |          0.258772 | True                   | pooled_across_decision_rules_diagnostic_only |

## Full threshold diagnostic

| model                     |   threshold |   n_opportunities |   n_dates |   n_decision_rules |   n_trades |   trade_rate |   total_net_pnl |   mean_net_pnl_per_opportunity |   mean_net_pnl_per_trade |   hit_rate_trades | is_primary_threshold   |
|:--------------------------|------------:|------------------:|----------:|-------------------:|-----------:|-------------:|----------------:|-------------------------------:|-------------------------:|------------------:|:-----------------------|
| catboost_platt            |        0    |               440 |        10 |                  4 |        440 |     1        |         -3.0015 |                   -0.00682159  |              -0.00682159 |         0.1       | False                  |
| catboost_raw              |        0    |               440 |        10 |                  4 |        440 |     1        |         -3.3155 |                   -0.00753523  |              -0.00753523 |         0.0977273 | False                  |
| ecmwf_bias_adaptive_sigma |        0    |               440 |        10 |                  4 |        440 |     1        |          6.0225 |                    0.0136875   |               0.0136875  |         0.706818  | False                  |
| ecmwf_bias_fixed_sigma    |        0    |               440 |        10 |                  4 |        440 |     1        |          2.6565 |                    0.0060375   |               0.0060375  |         0.531818  | False                  |
| ecmwf_raw                 |        0    |               440 |        10 |                  4 |        440 |     1        |         -3.8705 |                   -0.00879659  |              -0.00879659 |         0.359091  | False                  |
| catboost_platt            |        0.02 |               440 |        10 |                  4 |        374 |     0.85     |         -2.407  |                   -0.00547045  |              -0.00643583 |         0.0989305 | False                  |
| catboost_raw              |        0.02 |               440 |        10 |                  4 |        215 |     0.488636 |         -3.2755 |                   -0.00744432  |              -0.0152349  |         0.181395  | False                  |
| ecmwf_bias_adaptive_sigma |        0.02 |               440 |        10 |                  4 |        159 |     0.361364 |          5.1025 |                    0.0115966   |               0.0320912  |         0.440252  | False                  |
| ecmwf_bias_fixed_sigma    |        0.02 |               440 |        10 |                  4 |        186 |     0.422727 |          1.935  |                    0.00439773  |               0.0104032  |         0.317204  | False                  |
| ecmwf_raw                 |        0.02 |               440 |        10 |                  4 |        267 |     0.606818 |         -4.178  |                   -0.00949545  |              -0.0156479  |         0.2397    | False                  |
| catboost_platt            |        0.05 |               440 |        10 |                  4 |        201 |     0.456818 |         -2.792  |                   -0.00634545  |              -0.0138905  |         0.134328  | True                   |
| catboost_raw              |        0.05 |               440 |        10 |                  4 |        176 |     0.4      |         -2.202  |                   -0.00500455  |              -0.0125114  |         0.221591  | True                   |
| ecmwf_bias_adaptive_sigma |        0.05 |               440 |        10 |                  4 |        118 |     0.268182 |          5.7385 |                    0.013042    |               0.0486314  |         0.449153  | True                   |
| ecmwf_bias_fixed_sigma    |        0.05 |               440 |        10 |                  4 |        137 |     0.311364 |          5.133  |                    0.0116659   |               0.0374672  |         0.372263  | True                   |
| ecmwf_raw                 |        0.05 |               440 |        10 |                  4 |        228 |     0.518182 |         -3.978  |                   -0.00904091  |              -0.0174474  |         0.258772  | True                   |
| catboost_platt            |        0.1  |               440 |        10 |                  4 |        124 |     0.281818 |         -0.2645 |                   -0.000601136 |              -0.00213306 |         0.153226  | False                  |
| catboost_raw              |        0.1  |               440 |        10 |                  4 |        133 |     0.302273 |         -0.8065 |                   -0.00183295  |              -0.00606391 |         0.233083  | False                  |
| ecmwf_bias_adaptive_sigma |        0.1  |               440 |        10 |                  4 |         63 |     0.143182 |          8.607  |                    0.0195614   |               0.136619   |         0.52381   | False                  |
| ecmwf_bias_fixed_sigma    |        0.1  |               440 |        10 |                  4 |         84 |     0.190909 |          6.8795 |                    0.0156352   |               0.0818988  |         0.488095  | False                  |
| ecmwf_raw                 |        0.1  |               440 |        10 |                  4 |        174 |     0.395455 |         -5.055  |                   -0.0114886   |              -0.0290517  |         0.258621  | False                  |

## Integrity checks

| check                                           | passed   | detail                                                                                                        |
|:------------------------------------------------|:---------|:--------------------------------------------------------------------------------------------------------------|
| prediction_panel_nonempty                       | True     | rows=440                                                                                                      |
| trade_panel_nonempty                            | True     | rows=8800                                                                                                     |
| primary_threshold_present                       | True     | primary_threshold=0.05                                                                                        |
| market_probability_in_unit_interval             | True     | checked                                                                                                       |
| model_and_market_probabilities_in_unit_interval | True     | checked                                                                                                       |
| positions_restricted_to_yes_no_flat             | True     | ['FLAT', 'NO', 'YES']                                                                                         |
| trade_indicator_matches_position                | True     | checked                                                                                                       |
| yes_no_positions_mutually_exclusive             | True     | checked                                                                                                       |
| yes_trade_pnl_formula_correct                   | True     | checked                                                                                                       |
| no_trade_pnl_formula_correct                    | True     | checked                                                                                                       |
| flat_trade_pnl_zero                             | True     | checked                                                                                                       |
| threshold_summary_nonempty                      | True     | rows=20                                                                                                       |
| daily_panel_nonempty                            | True     | rows=800                                                                                                      |
| threshold_grid_preserved                        | True     | observed=[0.0, 0.02, 0.05, 0.1]                                                                               |
| model_count_expected                            | True     | models=['catboost_platt', 'catboost_raw', 'ecmwf_bias_adaptive_sigma', 'ecmwf_bias_fixed_sigma', 'ecmwf_raw'] |
| holdout_dates_preserved                         | True     | dates=10                                                                                                      |
| primary_threshold_flag_correct                  | True     | flagged_rows=5                                                                                                |
| headline_strategies_keep_one_decision_rule      | True     | headline_rows=20                                                                                              |
| headline_does_not_pool_decision_rules           | True     | headline is model × decision-rule specific                                                                    |

## Interpretation

The five percentage point threshold is prespecified. Alternative thresholds are sensitivity diagnostics. Results are hypothetical and based on ten settlement dates.
