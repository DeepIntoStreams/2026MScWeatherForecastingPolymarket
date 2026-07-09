# 18h CLOB narrow-window decision-price repair

Input contracts: `75`

Diagnostic endpoint attempts: `603`

Recovered price observation rows: `753`

No-lookahead decision rows: `273`

Scoring-ready rows: `273`


## Endpoint diagnostic summary

|   status_code | interval   |   lookback_hours |   count |   max |   sum |
|--------------:|:-----------|-----------------:|--------:|------:|------:|
|           200 | 1h         |                3 |      50 |     0 |     0 |
|           200 | 1h         |               12 |      33 |     0 |     0 |
|           200 | 1h         |               24 |      27 |     0 |     0 |
|           200 | 1m         |                3 |     300 |     3 |   685 |
|           200 | 1m         |               12 |      50 |     8 |    48 |
|           200 | 1m         |               24 |      33 |     8 |    20 |
|           200 | 6h         |                3 |      50 |     0 |     0 |
|           200 | 6h         |               12 |      33 |     0 |     0 |
|           200 | 6h         |               24 |      27 |     0 |     0 |


## Market-only score summary

| decision_rule                   | empirical_role                          |   n |   mean_brier |   mean_log_score |   mean_p_market |   outcome_rate |
|:--------------------------------|:----------------------------------------|----:|-------------:|-----------------:|----------------:|---------------:|
| last_price_before_12h_prior     | formally_certified_upper_tail_threshold |  68 |    0.0745929 |         0.251379 |        0.167191 |       0.161765 |
| last_price_before_12h_prior     | upper_tail_threshold_candidate          |   2 |    0.451575  |         1.41808  |        0.1465   |       0.5      |
| last_price_before_24h_prior     | formally_certified_upper_tail_threshold |  61 |    0.0863749 |         0.293474 |        0.161877 |       0.147541 |
| last_price_before_24h_prior     | upper_tail_threshold_candidate          |   2 |    0.437725  |         1.3845   |        0.05     |       0.5      |
| last_price_before_6h_prior      | formally_certified_upper_tail_threshold |  68 |    0.0675284 |         0.230587 |        0.166368 |       0.161765 |
| last_price_before_6h_prior      | upper_tail_threshold_candidate          |   2 |    0.434425  |         1.35622  |        0.095    |       0.5      |
| last_price_before_event_day_hkt | formally_certified_upper_tail_threshold |  68 |    0.0751804 |         0.259569 |        0.174603 |       0.161765 |
| last_price_before_event_day_hkt | upper_tail_threshold_candidate          |   2 |    0.428191  |         1.30908  |        0.05125  |       0.5      |


## Interpretation

The narrow-window repair recovered historical CLOB observations around no-lookahead decision times and produced a market-only scoring panel.