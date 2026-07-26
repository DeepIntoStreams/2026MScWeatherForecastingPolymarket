# 18e Hong Kong historical market--HKO alignment to 2026-05-31

Repository root: `/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket`

Historical official-outcome end date: `2026-05-31`


## HKO official target coverage

HKO target rows: `49459`

HKO date range: `1884-01-01` to `2026-05-31`


## Polymarket universe coverage

Raw Gamma events discovered: `75`

Flattened child rows: `821`

Historical contract universe rows: `821`

Threshold candidate rows with official HKO outcome and YES token: `73`


### Empirical role counts

| empirical_role                        |   count |
|:--------------------------------------|--------:|
| categorical_descriptive_only          |     730 |
| formally_certified_threshold_contract |      73 |
| excluded                              |      18 |


### Rule family counts

| rule_family                          |   count |
|:-------------------------------------|--------:|
| strict_hko_daily_extract_one_decimal |     803 |
| airport_or_wunderground_source       |      18 |


## Price history coverage

Price history panel rows: `0`


## No-lookahead decision panel

Decision panel rows: `0`

Official HKO scoring-ready rows: `0`


## Market-only score summary

_No official HKO scoring-ready rows were available after filtering._


## Interpretation

The scaled retrieval found Hong Kong historical contracts but no official-HKO scoring-ready rows after threshold, token, price and no-lookahead filters. The exclusion table should be inspected before deciding whether to loosen rule-family requirements.
