# 18m full HKO market-only baseline diagnostics

Generated from repository root: `/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket`

## Purpose

This step converts the 18l full Hong Kong HKO contract-event CLOB recovery into supervisor-ready market-only diagnostics. It keeps the binary contract-level scoring baseline, adds event-book probability diagnostics, and adds categorical scores for the daily contract book in which exactly one contract should resolve Yes.

## Input status

- Contract-level scoring rows: `2921`
- Decision-panel rows: `2921`
- Event-book decision snapshots: `267`
- Categorical score-ready event-book snapshots: `267`
- Upstream 18l missing-decision-price rows: `291`

## Binary market-only score by decision rule

| decision_rule   |   n |   mean_brier |   median_brier |   mean_log_score |   median_log_score |   mean_p_market |   outcome_rate |   median_staleness_hours |   p95_staleness_hours |
|:----------------|----:|-------------:|---------------:|-----------------:|-------------------:|----------------:|---------------:|-------------------------:|----------------------:|
| 24h_prior       | 679 |    0.0686781 |      0.0004    |         0.218455 |         0.0202027  |       0.0974138 |      0.0927835 |                 0.9975   |               5.98475 |
| 12h_prior       | 747 |    0.0651585 |      0.000324  |         0.20997  |         0.018164   |       0.0969076 |      0.0910308 |                 0.997778 |               5.68836 |
| 6h_prior        | 747 |    0.065719  |      9.025e-05 |         0.210624 |         0.00954541 |       0.0952256 |      0.0910308 |                 0.997778 |               3.69372 |
| event_day_open  | 748 |    0.0659736 |      3.025e-05 |         0.207559 |         0.00551518 |       0.0955501 |      0.0909091 |                 0.9975   |               6.64574 |

## Event-book categorical score by decision rule

| decision_rule   |   n_books |   full_book_rate |   mean_total_book_probability |   median_total_book_probability |   mean_abs_book_probability_error |   median_winning_probability_raw |   median_winning_probability_normalised |   mean_raw_categorical_log_score |   mean_normalised_categorical_log_score |   mean_raw_multiclass_brier |   mean_normalised_multiclass_brier |   median_max_staleness_hours |
|:----------------|----------:|-----------------:|------------------------------:|--------------------------------:|----------------------------------:|---------------------------------:|----------------------------------------:|---------------------------------:|----------------------------------------:|----------------------------:|-----------------------------------:|-----------------------------:|
| 24h_prior       |        63 |         0.952381 |                       1.0499  |                         1.0525  |                         0.0970794 |                           0.275  |                                0.249538 |                          1.45426 |                                 1.49029 |                    0.740197 |                           0.72795  |                     0.998889 |
| 12h_prior       |        68 |         0.985294 |                       1.06456 |                         1.05475 |                         0.0688382 |                           0.285  |                                0.269648 |                          1.41336 |                                 1.47443 |                    0.715785 |                           0.714819 |                     0.999028 |
| 6h_prior        |        68 |         0.985294 |                       1.04608 |                         1.03525 |                         0.0537426 |                           0.3125 |                                0.294446 |                          1.43536 |                                 1.47905 |                    0.721942 |                           0.719752 |                     0.998889 |
| event_day_open  |        68 |         1        |                       1.05105 |                         1.03625 |                         0.0635368 |                           0.29   |                                0.297766 |                          1.39613 |                                 1.44303 |                    0.72571  |                           0.721229 |                     0.998889 |

## Supervisor key table

| decision_rule   |   n |   mean_brier |   median_brier |   mean_log_score |   median_log_score |   mean_p_market |   outcome_rate |   median_staleness_hours |   p95_staleness_hours |   n_books |   mean_normalised_categorical_log_score |   mean_normalised_multiclass_brier |   mean_abs_book_probability_error |   median_winning_probability_normalised |
|:----------------|----:|-------------:|---------------:|-----------------:|-------------------:|----------------:|---------------:|-------------------------:|----------------------:|----------:|----------------------------------------:|-----------------------------------:|----------------------------------:|----------------------------------------:|
| 24h_prior       | 679 |    0.0686781 |      0.0004    |         0.218455 |         0.0202027  |       0.0974138 |      0.0927835 |                 0.9975   |               5.98475 |        63 |                                 1.49029 |                           0.72795  |                         0.0970794 |                                0.249538 |
| 12h_prior       | 747 |    0.0651585 |      0.000324  |         0.20997  |         0.018164   |       0.0969076 |      0.0910308 |                 0.997778 |               5.68836 |        68 |                                 1.47443 |                           0.714819 |                         0.0688382 |                                0.269648 |
| 6h_prior        | 747 |    0.065719  |      9.025e-05 |         0.210624 |         0.00954541 |       0.0952256 |      0.0910308 |                 0.997778 |               3.69372 |        68 |                                 1.47905 |                           0.719752 |                         0.0537426 |                                0.294446 |
| event_day_open  | 748 |    0.0659736 |      3.025e-05 |         0.207559 |         0.00551518 |       0.0955501 |      0.0909091 |                 0.9975   |               6.64574 |        68 |                                 1.44303 |                           0.721229 |                         0.0635368 |                                0.297766 |

## Decision-rule rankings

| metric                               | decision_rule   |     value |   rank | lower_better   |
|:-------------------------------------|:----------------|----------:|-------:|:---------------|
| binary_mean_brier                    | 12h_prior       | 0.0651585 |      1 | True           |
| binary_mean_brier                    | 6h_prior        | 0.065719  |      2 | True           |
| binary_mean_brier                    | event_day_open  | 0.0659736 |      3 | True           |
| binary_mean_brier                    | 24h_prior       | 0.0686781 |      4 | True           |
| binary_mean_log_score                | event_day_open  | 0.207559  |      1 | True           |
| binary_mean_log_score                | 12h_prior       | 0.20997   |      2 | True           |
| binary_mean_log_score                | 6h_prior        | 0.210624  |      3 | True           |
| binary_mean_log_score                | 24h_prior       | 0.218455  |      4 | True           |
| book_coherence_absolute_error        | 6h_prior        | 0.0537426 |      1 | True           |
| book_coherence_absolute_error        | event_day_open  | 0.0635368 |      2 | True           |
| book_coherence_absolute_error        | 12h_prior       | 0.0688382 |      3 | True           |
| book_coherence_absolute_error        | 24h_prior       | 0.0970794 |      4 | True           |
| median_normalised_winner_probability | event_day_open  | 0.297766  |      1 | False          |
| median_normalised_winner_probability | 6h_prior        | 0.294446  |      2 | False          |
| median_normalised_winner_probability | 12h_prior       | 0.269648  |      3 | False          |
| median_normalised_winner_probability | 24h_prior       | 0.249538  |      4 | False          |
| normalised_categorical_log_score     | event_day_open  | 1.44303   |      1 | True           |
| normalised_categorical_log_score     | 12h_prior       | 1.47443   |      2 | True           |
| normalised_categorical_log_score     | 6h_prior        | 1.47905   |      3 | True           |
| normalised_categorical_log_score     | 24h_prior       | 1.49029   |      4 | True           |
| normalised_multiclass_brier          | 12h_prior       | 0.714819  |      1 | True           |
| normalised_multiclass_brier          | 6h_prior        | 0.719752  |      2 | True           |
| normalised_multiclass_brier          | event_day_open  | 0.721229  |      3 | True           |
| normalised_multiclass_brier          | 24h_prior       | 0.72795   |      4 | True           |

## Integrity checks

| check                                    | passed   | detail                               |
|:-----------------------------------------|:---------|:-------------------------------------|
| scoring_panel_nonempty                   | True     | rows=2921                            |
| decision_panel_nonempty                  | True     | rows=2921                            |
| book_metrics_nonempty                    | True     | rows=267                             |
| categorical_summary_nonempty             | True     | rows=4                               |
| probabilities_in_unit_interval           | True     | bad_probabilities=0                  |
| non_negative_staleness                   | True     | negative_staleness=0                 |
| categorical_scored_books_have_one_winner | True     | bad_scored_books=0; unscored_books=0 |
| some_full_books_observed                 | True     | full_book_rate=0.9813                |
| upstream_18l_integrity_checks_passed     | True     | failed_18l_checks=0                  |

## Interpretation

The binary contract-level score remains the appropriate direct extension of the earlier threshold-contract evaluation, because every listed contract is a separate binary Polymarket outcome. The event-book categorical score is an additional diagnostic that uses the fact that the HKO categorical family forms a daily partition of the realised temperature space. The normalised categorical score is useful for checking what the market believed conditional on the listed contract book, while the raw book probability diagnostics show whether listed YES prices summed materially above or below one.

Best binary Brier decision rule: `12h_prior`.

Best binary log-score decision rule: `event_day_open`.

Best normalised categorical log-score decision rule: `event_day_open`.

Best normalised multiclass Brier decision rule: `12h_prior`.

## Figures

- `figures/18m_market_only_baseline/18m_binary_brier_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_binary_log_score_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_normalised_categorical_log_score_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_normalised_multiclass_brier_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_book_probability_error_boxplot_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_normalised_winning_probability_boxplot_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_price_staleness_boxplot_by_decision_rule.png`
- `figures/18m_market_only_baseline/18m_market_probability_histogram_by_outcome.png`

## Output files

- `data/processed/18m_binary_market_score_by_decision_rule.csv`
- `data/processed/18m_binary_market_score_by_decision_rule_and_event_type.csv`
- `data/processed/18m_event_book_categorical_score_panel.csv`
- `data/processed/18m_event_book_categorical_score_by_decision_rule.csv`
- `data/processed/18m_supervisor_market_only_key_table.csv`
- `data/processed/18m_market_only_decision_rule_rankings.csv`
- `data/processed/18m_market_only_integrity_checks.csv`
- `docs/research_outputs/18m_full_hko_market_only_baseline_report.md`
- `data/review_bundles/18m_review_bundle.zip`
