# 18i Hong Kong empirical baseline report

This report consolidates the successful 18f official-outcome construction and 18h narrow-window CLOB price recovery into a dissertation-facing empirical baseline.

The main empirical sample is restricted to `empirical_role = formally_certified_upper_tail_threshold`; exploratory candidate rows are excluded from the headline result.

## Coverage summary

| metric                                  | value      | note                                                                 |
|:----------------------------------------|:-----------|:---------------------------------------------------------------------|
| hko_rows                                | 92         | Official HKO Daily Extract / metob maximum-temperature observations. |
| hko_start_date                          | 2026-03-01 |                                                                      |
| hko_end_date                            | 2026-05-31 |                                                                      |
| polymarket_event_slugs_swept            | 80         | Deterministic daily Hong Kong highest-temperature event slugs.       |
| gamma_events_found                      | 75         |                                                                      |
| web_pages_found                         | 75         |                                                                      |
| flattened_child_market_rows             | 821        |                                                                      |
| upper_tail_threshold_rows               | 75         |                                                                      |
| formally_certified_upper_tail_rows      | 73         |                                                                      |
| non_certified_upper_tail_candidate_rows | 2          |                                                                      |
| price_observation_rows                  | 753        | Recovered CLOB narrow-window price observations.                     |
| no_lookahead_decision_rows              | 273        | Rows after no-lookahead price cutoffs.                               |
| scoring_ready_rows                      | 273        | Rows with market probability and realised HKO binary outcome.        |
| main_formally_certified_scoring_rows    | 265        |                                                                      |
| clob_diagnostic_endpoint_attempts       | 603        |                                                                      |
| diagnostic_attempts_with_history        | 273        |                                                                      |

## Main market-only score summary

| decision_rule                   | decision_label   |   n |   mean_brier |   median_brier |   mean_log_score |   median_log_score |   mean_p_market |   median_p_market |   outcome_rate |   median_price_staleness_hours |   max_price_staleness_hours |
|:--------------------------------|:-----------------|----:|-------------:|---------------:|-----------------:|-------------------:|----------------:|------------------:|---------------:|-------------------------------:|----------------------------:|
| last_price_before_24h_prior     | 24h prior        |  61 |    0.0863749 |      0.013225  |         0.293474 |          0.122168  |        0.161877 |           0.105   |       0.147541 |                       0.9975   |                     7.98528 |
| last_price_before_12h_prior     | 12h prior        |  68 |    0.0745929 |      0.0085625 |         0.251379 |          0.0970655 |        0.167191 |           0.0925  |       0.161765 |                       0.997778 |                    19.9853  |
| last_price_before_6h_prior      | 6h prior         |  68 |    0.0675284 |      0.005625  |         0.230587 |          0.0779615 |        0.166368 |           0.075   |       0.161765 |                       0.997778 |                    12.9872  |
| last_price_before_event_day_hkt | Event-day open   |  68 |    0.0751804 |      0.0049    |         0.259569 |          0.0725707 |        0.174603 |           0.06725 |       0.161765 |                       0.9975   |                    18.9872  |

The lowest mean Brier score is obtained by `last_price_before_6h_prior` with mean Brier score `0.067528` over `68` rows. The lowest mean log score is obtained by `last_price_before_6h_prior` with mean log score `0.230587` over `68` rows.

## Operational decision-rule summary

| decision_rule                   |   n |   unique_contracts |   median_staleness_hours |   mean_staleness_hours |   max_staleness_hours |   mean_price_query_lookback_hours | decision_label   |
|:--------------------------------|----:|-------------------:|-------------------------:|-----------------------:|----------------------:|----------------------------------:|:-----------------|
| last_price_before_24h_prior     |  61 |                 61 |                 0.9975   |                1.41941 |               7.98528 |                           3.44262 | 24h prior        |
| last_price_before_12h_prior     |  68 |                 68 |                 0.997778 |                1.86079 |              19.9853  |                           3.83824 | 12h prior        |
| last_price_before_6h_prior      |  68 |                 68 |                 0.997778 |                1.58138 |              12.9872  |                           3.70588 | 6h prior         |
| last_price_before_event_day_hkt |  68 |                 68 |                 0.9975   |                1.91972 |              18.9872  |                           4.41176 | Event-day open   |

## Monthly coverage

| month   |   upper_tail_contracts |   formally_certified_contracts |   mean_threshold_K |   hko_outcome_rate |   formally_certified_scoring_rows |   scoring_unique_contracts |   mean_brier |   mean_log_score |
|:--------|-----------------------:|-------------------------------:|-------------------:|-------------------:|----------------------------------:|---------------------------:|-------------:|-----------------:|
| 2026-03 |                     16 |                             14 |            27.1875 |          0.3125    |                                43 |                         11 |    0.153819  |         0.504826 |
| 2026-04 |                     30 |                             30 |            29.7667 |          0.0666667 |                               116 |                         30 |    0.0295002 |         0.124811 |
| 2026-05 |                     29 |                             29 |            30.8966 |          0.241379  |                               106 |                         27 |    0.0944261 |         0.303214 |

## Integrity checks

| check                            | passed   | detail                                       |
|:---------------------------------|:---------|:---------------------------------------------|
| main_role_present                | True     | formally_certified_upper_tail_threshold      |
| probabilities_in_unit_interval   | True     | All p_market values should lie in [0,1].     |
| binary_outcomes                  | True     | All Y_ge_K values should be binary.          |
| non_negative_scores              | True     | Brier and log scores should be non-negative. |
| no_lookahead_timestamps          | True     | Max decision minus cutoff seconds: -3541.0   |
| formal_certified_subset_nonempty | True     | Formal upper-tail rows: 73                   |

## Figures

- `brier`: `figures/reports/18i_hko_market_brier_by_decision_rule.png`
- `log_score`: `figures/reports/18i_hko_market_log_score_by_decision_rule.png`
- `price_staleness`: `figures/reports/18i_hko_price_staleness_by_decision_rule.png`
- `monthly_coverage`: `figures/reports/18i_hko_monthly_coverage.png`
- `probability_histogram`: `figures/reports/18i_hko_market_probability_histogram.png`

## Dissertation-facing interpretation

Hong Kong is now usable as the primary empirical baseline. The official-outcome side is based on HKO Daily Extract / metob maximum-temperature observations, and the market side is based on deterministic Polymarket event slug retrieval and narrow-window CLOB price recovery. For the formally certified upper-tail subset, the best market-only decision rule by mean Brier score is `last_price_before_6h_prior`, with `n = 68`, mean Brier score `0.067528`, mean log score `0.230587`, mean market probability `0.166368`, and outcome rate `0.161765`. This table should be used as the market-only benchmark before adding forecast-implied probabilities from AI/weather sources.

## Recommended next step

Use this 18i baseline as the fixed HK market-only benchmark. The next modelling step is to build forecast-implied threshold probabilities for the same `(event_date, threshold_K)` rows and compare Brier/log scores against the market-only probabilities under identical no-lookahead decision rules.
