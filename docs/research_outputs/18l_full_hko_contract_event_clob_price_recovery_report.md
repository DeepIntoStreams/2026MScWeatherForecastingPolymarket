# 18l full HKO contract-event CLOB price recovery

Generated: `2026-07-14 23:09:35 UTC`

## Purpose

This step extends the previous upper-tail CLOB price recovery to the full repaired Hong Kong HKO contract-event book. It uses the 18k realised target panel, retrieves historical prices for each certified YES token, constructs no-lookahead decision snapshots, and computes market-only Brier and log scores.

## Main result

- Input target rows: `803`

- Unique event dates: `73`

- Unique YES tokens: `803`

- Price-history observation rows: `28326`

- No-lookahead decision rows: `2921`

- Scoring-ready rows: `2921`

- Missing decision-price issue rows: `291`


## CLOB recovery diagnostics

| fetch_source   |   status_code | attempt_label         | has_history   |   contracts |
|:---------------|--------------:|:----------------------|:--------------|------------:|
| api            |           200 | window_7d_fidelity_60 | False         |          55 |
| api            |           200 | window_7d_fidelity_60 | True          |         748 |

## Integrity checks

| check                             | passed   | detail               |
|:----------------------------------|:---------|:---------------------|
| target_panel_nonempty             | True     | target rows=803      |
| target_rows_have_binary_payoff    | True     | bad rows=0           |
| target_rows_have_yes_tokens       | True     | missing tokens=0     |
| price_history_nonempty            | True     | price rows=28326     |
| decision_panel_nonempty           | True     | decision rows=2921   |
| scoring_panel_nonempty            | True     | scoring rows=2921    |
| no_lookahead_decision_timestamps  | True     | violations=0         |
| probabilities_in_unit_interval    | True     | bad probabilities=0  |
| non_negative_staleness            | True     | negative staleness=0 |
| missing_price_issue_table_written | True     | issue rows=291       |

## Market-only score summary

| decision_rule   | contract_event_type_v2   |   n |   mean_brier |   mean_log_score |   median_staleness_hours |   mean_p_market |   outcome_rate |
|:----------------|:-------------------------|----:|-------------:|-----------------:|-------------------------:|----------------:|---------------:|
| 12h_prior       | ALL                      | 747 |  0.0651585   |      0.20997     |                 0.997778 |     0.0969076   |      0.0910308 |
| 24h_prior       | ALL                      | 679 |  0.0686781   |      0.218455    |                 0.9975   |     0.0974138   |      0.0927835 |
| 6h_prior        | ALL                      | 747 |  0.065719    |      0.210624    |                 0.997778 |     0.0952256   |      0.0910308 |
| event_day_open  | ALL                      | 748 |  0.0659736   |      0.207559    |                 0.9975   |     0.0955501   |      0.0909091 |
| 12h_prior       | interior_bin             | 611 |  0.0713579   |      0.228524    |                 0.997778 |     0.0996669   |      0.0932897 |
| 12h_prior       | lower_tail_endpoint      |  68 |  2.05846e-05 |      0.00184139  |                 0.997917 |     0.00183088  |      0         |
| 12h_prior       | upper_tail               |  68 |  0.0745929   |      0.251379    |                 0.997778 |     0.167191    |      0.161765  |
| 24h_prior       | interior_bin             | 556 |  0.0743942   |      0.234347    |                 0.9975   |     0.100967    |      0.0971223 |
| 24h_prior       | lower_tail_endpoint      |  62 |  6.44355e-06 |      0.00213226  |                 0.9975   |     0.00212903  |      0         |
| 24h_prior       | upper_tail               |  61 |  0.0863749   |      0.293474    |                 0.9975   |     0.161877    |      0.147541  |
| 6h_prior        | interior_bin             | 611 |  0.0728315   |      0.231722    |                 0.997778 |     0.0977848   |      0.0932897 |
| 6h_prior        | lower_tail_endpoint      |  68 |  1.82353e-06 |      0.00108915  |                 0.997778 |     0.00108824  |      0         |
| 6h_prior        | upper_tail               |  68 |  0.0675284   |      0.230587    |                 0.997778 |     0.166368    |      0.161765  |
| event_day_open  | interior_bin             | 612 |  0.0722809   |      0.224752    |                 0.997778 |     0.0972933   |      0.0931373 |
| event_day_open  | lower_tail_endpoint      |  68 |  1.11765e-06 |      0.000809383 |                 0.997639 |     0.000808824 |      0         |
| event_day_open  | upper_tail               |  68 |  0.0751804   |      0.259569    |                 0.9975   |     0.174603    |      0.161765  |

## Event-book snapshot summary preview

| event_date   | decision_rule   |   n_price_snapshots |   n_yes_contracts |   total_book_market_probability |   winning_contract_market_probability |   book_probability_error_vs_one |   max_price_staleness_hours |
|:-------------|:----------------|--------------------:|------------------:|--------------------------------:|--------------------------------------:|--------------------------------:|----------------------------:|
| 2026-03-18   | 12h_prior       |                  11 |                 1 |                          1.3    |                                0.225  |                          0.3    |                    0.992778 |
| 2026-03-18   | 6h_prior        |                  11 |                 1 |                          0.999  |                                0.11   |                         -0.001  |                    0.9925   |
| 2026-03-18   | event_day_open  |                  11 |                 1 |                          1.433  |                                0.275  |                          0.433  |                    0.991667 |
| 2026-03-19   | 12h_prior       |                  11 |                 1 |                          1.2245 |                                0.155  |                          0.2245 |                    0.9925   |
| 2026-03-19   | 24h_prior       |                  11 |                 1 |                          1.529  |                                0.1    |                          0.529  |                    0.991667 |
| 2026-03-19   | 6h_prior        |                  11 |                 1 |                          1.1575 |                                0.37   |                          0.1575 |                    0.990278 |
| 2026-03-19   | event_day_open  |                  11 |                 1 |                          0.918  |                                0.285  |                         -0.082  |                    1.9875   |
| 2026-03-21   | 12h_prior       |                  11 |                 1 |                          1.0985 |                                0.0705 |                          0.0985 |                    1.98472  |
| 2026-03-21   | 24h_prior       |                  11 |                 1 |                          1.1795 |                                0.0895 |                          0.1795 |                    0.9925   |
| 2026-03-21   | 6h_prior        |                  11 |                 1 |                          1.0725 |                                0.0175 |                          0.0725 |                    0.993056 |
| 2026-03-21   | event_day_open  |                  11 |                 1 |                          1.1055 |                                0.0485 |                          0.1055 |                    0.991944 |
| 2026-03-22   | 12h_prior       |                  11 |                 1 |                          1.154  |                                0.315  |                          0.154  |                    0.9925   |
| 2026-03-22   | 24h_prior       |                  11 |                 1 |                          1.0785 |                                0.345  |                          0.0785 |                    0.990833 |
| 2026-03-22   | 6h_prior        |                  11 |                 1 |                          1.084  |                                0.305  |                          0.084  |                    0.992778 |
| 2026-03-22   | event_day_open  |                  11 |                 1 |                          1.152  |                                0.215  |                          0.152  |                    1.98472  |
| 2026-03-23   | 12h_prior       |                  11 |                 1 |                          1.223  |                                0.335  |                          0.223  |                    0.994722 |
| 2026-03-23   | 24h_prior       |                  11 |                 1 |                          1.171  |                                0.25   |                          0.171  |                    1.985    |
| 2026-03-23   | 6h_prior        |                  11 |                 1 |                          1.06   |                                0.47   |                          0.06   |                    0.994722 |
| 2026-03-23   | event_day_open  |                  11 |                 1 |                          1.2955 |                                0.41   |                          0.2955 |                    0.995    |
| 2026-03-24   | 12h_prior       |                  11 |                 1 |                          1.143  |                                0.285  |                          0.143  |                    0.992222 |
| 2026-03-24   | 24h_prior       |                  11 |                 1 |                          1.055  |                                0.185  |                          0.055  |                    0.993889 |
| 2026-03-24   | 6h_prior        |                  11 |                 1 |                          0.9835 |                                0.235  |                         -0.0165 |                    0.989722 |
| 2026-03-24   | event_day_open  |                  11 |                 1 |                          1.0495 |                                0.285  |                          0.0495 |                    0.994444 |
| 2026-03-25   | 12h_prior       |                  11 |                 1 |                          1.048  |                                0.69   |                          0.048  |                    0.994444 |
| 2026-03-25   | 24h_prior       |                  11 |                 1 |                          1.1505 |                                0.555  |                          0.1505 |                    0.995278 |
| 2026-03-25   | 6h_prior        |                  11 |                 1 |                          1.028  |                                0.755  |                          0.028  |                    0.994167 |
| 2026-03-25   | event_day_open  |                  11 |                 1 |                          1.089  |                                0.59   |                          0.089  |                    0.993889 |
| 2026-03-26   | 12h_prior       |                  11 |                 1 |                          1.0665 |                                0.475  |                          0.0665 |                    0.994444 |
| 2026-03-26   | 24h_prior       |                  11 |                 1 |                          1.0525 |                                0.335  |                          0.0525 |                    0.994167 |
| 2026-03-26   | 6h_prior        |                  11 |                 1 |                          1.033  |                                0.09   |                          0.033  |                    0.993889 |
| 2026-03-26   | event_day_open  |                  11 |                 1 |                          0.9815 |                                0.0335 |                         -0.0185 |                    0.993333 |
| 2026-03-27   | 12h_prior       |                  11 |                 1 |                          1.1075 |                                0.185  |                          0.1075 |                    0.991667 |
| 2026-03-27   | 24h_prior       |                  11 |                 1 |                          0.972  |                                0.125  |                         -0.028  |                    0.991667 |
| 2026-03-27   | 6h_prior        |                  11 |                 1 |                          1.136  |                                0.08   |                          0.136  |                    0.993056 |
| 2026-03-27   | event_day_open  |                  11 |                 1 |                          1.05   |                                0.0175 |                          0.05   |                    0.992222 |
| 2026-03-28   | 12h_prior       |                  11 |                 1 |                          1.0255 |                                0.38   |                          0.0255 |                    0.9925   |
| 2026-03-28   | 24h_prior       |                  11 |                 1 |                          1.1085 |                                0.32   |                          0.1085 |                    0.993333 |
| 2026-03-28   | 6h_prior        |                  11 |                 1 |                          1.027  |                                0.315  |                          0.027  |                    0.992778 |
| 2026-03-28   | event_day_open  |                  11 |                 1 |                          1.0515 |                                0.32   |                          0.0515 |                    0.993611 |
| 2026-03-29   | 12h_prior       |                  11 |                 1 |                          1.0295 |                                0.11   |                          0.0295 |                    0.991944 |

## Decision-panel preview

| event_date   | market_slug                                                 | group_item_title   | contract_event_type_v2   | decision_rule   |   p_market |   Y_event_int |   brier_market |   log_score_market |   price_staleness_hours |
|:-------------|:------------------------------------------------------------|:-------------------|:-------------------------|:----------------|-----------:|--------------:|---------------:|-------------------:|------------------------:|
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-20corbelow | 20°C or below      | lower_tail_endpoint      | 24h_prior       |     0.0015 |             0 |     2.25e-06   |        0.00150113  |                0.989722 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-20corbelow | 20°C or below      | lower_tail_endpoint      | 12h_prior       |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                0.985278 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-20corbelow | 20°C or below      | lower_tail_endpoint      | 6h_prior        |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                0.987778 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-20corbelow | 20°C or below      | lower_tail_endpoint      | event_day_open  |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                0.997778 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-21c        | 21°C               | interior_bin             | 24h_prior       |     0.0015 |             0 |     2.25e-06   |        0.00150113  |                0.983889 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-21c        | 21°C               | interior_bin             | 12h_prior       |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                2.98583  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-21c        | 21°C               | interior_bin             | 6h_prior        |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                1.98667  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-21c        | 21°C               | interior_bin             | event_day_open  |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                0.989444 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-22c        | 22°C               | interior_bin             | 24h_prior       |     0.007  |             0 |     4.9e-05    |        0.00702461  |                5.985    |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-22c        | 22°C               | interior_bin             | 12h_prior       |     0.002  |             0 |     4e-06      |        0.002002    |                5.98389  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-22c        | 22°C               | interior_bin             | 6h_prior        |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                4.98417  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-22c        | 22°C               | interior_bin             | event_day_open  |     0.0005 |             0 |     2.5e-07    |        0.000500125 |               10.9842   |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-23c        | 23°C               | interior_bin             | 24h_prior       |     0.0165 |             0 |     0.00027225 |        0.0166376   |                4.98472  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-23c        | 23°C               | interior_bin             | 12h_prior       |     0.0015 |             0 |     2.25e-06   |        0.00150113  |                2.98472  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-23c        | 23°C               | interior_bin             | 6h_prior        |     0.0015 |             0 |     2.25e-06   |        0.00150113  |                1.98417  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-23c        | 23°C               | interior_bin             | event_day_open  |     0.0005 |             0 |     2.5e-07    |        0.000500125 |                0.985    |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-24c        | 24°C               | interior_bin             | 24h_prior       |     0.031  |             0 |     0.000961   |        0.0314907   |                0.985833 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-24c        | 24°C               | interior_bin             | 12h_prior       |     0.0435 |             0 |     0.00189225 |        0.0444745   |                1.98361  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-24c        | 24°C               | interior_bin             | 6h_prior        |     0.0185 |             0 |     0.00034225 |        0.0186733   |                0.984444 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-24c        | 24°C               | interior_bin             | event_day_open  |     0.0025 |             0 |     6.25e-06   |        0.00250313  |                0.992222 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-25c        | 25°C               | interior_bin             | 24h_prior       |     0.065  |             0 |     0.004225   |        0.0672087   |                5.98556  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-25c        | 25°C               | interior_bin             | 12h_prior       |     0.1545 |             0 |     0.0238702  |        0.167827    |                2.98361  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-25c        | 25°C               | interior_bin             | 6h_prior        |     0.1715 |             0 |     0.0294123  |        0.188138    |                4.98444  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-25c        | 25°C               | interior_bin             | event_day_open  |     0.1715 |             0 |     0.0294123  |        0.188138    |               10.9844   |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-26c        | 26°C               | interior_bin             | 24h_prior       |     0.19   |             0 |     0.0361     |        0.210721    |                0.986667 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-26c        | 26°C               | interior_bin             | 12h_prior       |     0.18   |             0 |     0.0324     |        0.198451    |                1.98417  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-26c        | 26°C               | interior_bin             | 6h_prior        |     0.205  |             0 |     0.042025   |        0.229413    |                0.985278 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-26c        | 26°C               | interior_bin             | event_day_open  |     0.265  |             0 |     0.070225   |        0.307885    |                0.993611 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-27c        | 27°C               | interior_bin             | 24h_prior       |     0.335  |             1 |     0.442225   |        1.09362     |                0.988333 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-27c        | 27°C               | interior_bin             | 12h_prior       |     0.28   |             1 |     0.5184     |        1.27297     |                0.983889 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-27c        | 27°C               | interior_bin             | 6h_prior        |     0.315  |             1 |     0.469225   |        1.15518     |                0.986389 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-27c        | 27°C               | interior_bin             | event_day_open  |     0.355  |             1 |     0.416025   |        1.03564     |                0.995556 |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-28c        | 28°C               | interior_bin             | 24h_prior       |     0.29   |             0 |     0.0841     |        0.34249     |                5.98472  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-28c        | 28°C               | interior_bin             | 12h_prior       |     0.3    |             0 |     0.09       |        0.356675    |                5.98361  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-28c        | 28°C               | interior_bin             | 6h_prior        |     0.31   |             0 |     0.0961     |        0.371064    |                4.98389  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-28c        | 28°C               | interior_bin             | event_day_open  |     0.31   |             0 |     0.0961     |        0.371064    |               10.9839   |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-29c        | 29°C               | interior_bin             | 24h_prior       |     0.11   |             0 |     0.0121     |        0.116534    |                4.98472  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-29c        | 29°C               | interior_bin             | 12h_prior       |     0.07   |             0 |     0.0049     |        0.0725707   |                2.98472  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-29c        | 29°C               | interior_bin             | 6h_prior        |     0.07   |             0 |     0.0049     |        0.0725707   |                1.98444  |
| 2026-04-01   | highest-temperature-in-hong-kong-on-april-1-2026-29c        | 29°C               | interior_bin             | event_day_open  |     0.065  |             0 |     0.004225   |        0.0672087   |                0.985278 |

## Issues requiring review

Issue rows: `291`

| issue_type             | event_date   | market_slug                                                   | group_item_title   |                                                          selected_yes_token_id | decision_rule   | decision_cutoff_utc       | detail                                                                               |
|:-----------------------|:-------------|:--------------------------------------------------------------|:-------------------|-------------------------------------------------------------------------------:|:----------------|:--------------------------|:-------------------------------------------------------------------------------------|
| missing_decision_price | 2026-04-14   | highest-temperature-in-hong-kong-on-april-14-2026-23c         | 23°C               | 113207127978191097885229707545567156326206459658678095990961358545827439600369 | 24h_prior       | 2026-04-12 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-14   | highest-temperature-in-hong-kong-on-april-14-2026-24c         | 24°C               |   2328851494895717659133690267688489021646281569491861569206504975271186629895 | 24h_prior       | 2026-04-12 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-14   | highest-temperature-in-hong-kong-on-april-14-2026-26c         | 26°C               | 112889139991084195812349620505190241975235202968016305170084766813585327085701 | 24h_prior       | 2026-04-12 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-14   | highest-temperature-in-hong-kong-on-april-14-2026-30corhigher | 30°C or higher     |  37469154916892071384543381829218229217717740835071670577695636049083897627097 | 24h_prior       | 2026-04-12 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-20corbelow  | 20°C or below      | 107437801681083339073544275346332489372530686920612991917177688660589026285052 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-21c         | 21°C               |   5913641206172387752962597144057924402358239060171002371156135215423927584834 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-22c         | 22°C               |  24531645722845287611812986318132210832705352889438715580291989356631184026338 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-22c         | 22°C               |  24531645722845287611812986318132210832705352889438715580291989356631184026338 | 12h_prior       | 2026-04-15 04:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-22c         | 22°C               |  24531645722845287611812986318132210832705352889438715580291989356631184026338 | 6h_prior        | 2026-04-15 10:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-23c         | 23°C               |  91903937096889988385692177634143684361709747894120468684893410047829901955307 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-24c         | 24°C               |  34435461563748604642799907585194831510570022784617329493032325149774980841993 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-25c         | 25°C               |   5525050243761054467521962314594710839632041395683623770976821306042274383989 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-26c         | 26°C               | 104927466918490130770860889602449057946561824438896283963293421930540277011262 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-27c         | 27°C               |  44257849904292148716060129381998755183978924165497150254119649186580046120109 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-28c         | 28°C               | 113038927596348619456532270695268761744058501537797580547787732755648546356450 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-29c         | 29°C               | 107879621279143879080119755321860961453882763206109524172804879311021560328914 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-16   | highest-temperature-in-hong-kong-on-april-16-2026-30corhigher | 30°C or higher     |  48048433716477505707695293112722186926089578768950552705404097789580119706471 | 24h_prior       | 2026-04-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-17   | highest-temperature-in-hong-kong-on-april-17-2026-21corbelow  | 21°C or below      |  77061780706317654402101850969699917830338477228882325374024877186483852059808 | 24h_prior       | 2026-04-15 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-17   | highest-temperature-in-hong-kong-on-april-17-2026-22c         | 22°C               |  20008441658275738438097412842809301010691954435847936992450402401417749091309 | 24h_prior       | 2026-04-15 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-17   | highest-temperature-in-hong-kong-on-april-17-2026-27c         | 27°C               |  13113611667323185385406142085166788194052390205987424287815024597271735747472 | 24h_prior       | 2026-04-15 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-17   | highest-temperature-in-hong-kong-on-april-17-2026-29c         | 29°C               |  52943460668945658049683866594332408811709772847995718142094202987585536405444 | 24h_prior       | 2026-04-15 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-17   | highest-temperature-in-hong-kong-on-april-17-2026-30c         | 30°C               |  89201406097350451073696076240400788460300422556288703676394698330615978449264 | 24h_prior       | 2026-04-15 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-18   | highest-temperature-in-hong-kong-on-april-18-2026-24c         | 24°C               |  78872091096123904013882382241145197514349554348378637576017933515534426776431 | 24h_prior       | 2026-04-16 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-18   | highest-temperature-in-hong-kong-on-april-18-2026-25c         | 25°C               | 101880568357033525018620845471304996467821262515493304209784143811590094935008 | 24h_prior       | 2026-04-16 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-18   | highest-temperature-in-hong-kong-on-april-18-2026-29c         | 29°C               |  81962522574444305926309776770229900050478616693498160728727529516280674474722 | 24h_prior       | 2026-04-16 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-18   | highest-temperature-in-hong-kong-on-april-18-2026-30c         | 30°C               |  68644662605353726595201952994283071572447581601968250415866871142824183555444 | 24h_prior       | 2026-04-16 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-18   | highest-temperature-in-hong-kong-on-april-18-2026-31corhigher | 31°C or higher     |   3474367580288780672438083812437126303193794306223425403905998554309317001729 | 24h_prior       | 2026-04-16 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-15corbelow  | 15°C or below      |  96394190312334567473356531036091600606609538532694314104976217940793896861752 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-16c         | 16°C               |  39670300403790847696242152325992681789658441908801816523924156418938192717782 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-17c         | 17°C               | 108374954973335641875617237822126497277598770967804533225969513327290630092882 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-18c         | 18°C               |  86634081006768088679952772517484542165690893607224514816063694819285166969738 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-19c         | 19°C               |  49083698325663893355272711934566113188116438229862492912776096331085178689806 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-20c         | 20°C               |  30575220617318690608561489558960824453052744765369840465658337246499649048739 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-21c         | 21°C               |  62006899003238965865473005469486817359393482464489663688306374892150180866310 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-22c         | 22°C               |  29175966208431498342571459088074934988900563645466371498513699167612422372092 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-23c         | 23°C               |  70953357549837257926005976055218580091842441016996226274612474643045210981801 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-24c         | 24°C               |  99476611839931606930737592364209583628495445695100418696606993168892891923566 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-04-30   | highest-temperature-in-hong-kong-on-april-30-2026-25corhigher | 25°C or higher     |  58241419617790886405472393240074075849959303014587052885072747799842743410659 | 24h_prior       | 2026-04-28 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-03-16   | highest-temperature-in-hong-kong-on-march-16-2026-14corbelow  | 14°C or below      |  18417729625237348344675915135810781093247776356764996381548944727108053313255 | 24h_prior       | 2026-03-14 16:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |
| missing_decision_price | 2026-03-16   | highest-temperature-in-hong-kong-on-march-16-2026-14corbelow  | 14°C or below      |  18417729625237348344675915135810781093247776356764996381548944727108053313255 | 12h_prior       | 2026-03-15 04:00:00+00:00 | No price point at or before the decision cutoff within the recovered history window. |

## Interpretation

The full HKO contract-event price recovery passed all automated checks. The scoring panel may be used as the market-only baseline for the full Hong Kong event-book analysis.

## Output files

- `data/processed/18l_full_hko_contract_event_price_history_panel.csv`

- `data/processed/18l_full_hko_contract_event_no_lookahead_decision_panel.csv`

- `data/processed/18l_full_hko_contract_event_market_scoring_panel.csv`

- `data/processed/18l_full_hko_contract_event_market_score_summary.csv`

- `data/processed/18l_full_hko_contract_event_book_snapshot_summary.csv`

- `data/processed/18l_clob_recovery_diagnostics.csv`

- `data/processed/18l_clob_recovery_integrity_checks.csv`

- `data/processed/18l_clob_recovery_issues.csv`

- `docs/research_outputs/18l_full_hko_contract_event_clob_price_recovery_report.md`

- `data/review_bundles/18l_review_bundle.zip`
