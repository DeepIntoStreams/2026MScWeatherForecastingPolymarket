# 18r June 2026 market–weather exact common support

Generated at UTC: `2026-07-21T17:24:18.866329+00:00`

## Overall judgement

**PASS**

## Exact support definition

A contract-rule row is retained only when a verified Polymarket price is available at or before the decision cut-off and the selected issue-time-admissible ECMWF run contains all 24 non-missing Hong Kong local event-day hours.

The exact join key is `event_date × market_id × decision_rule`. No missing value is imputed and no later market price or weather run is substituted.

## Sample flow

- Candidate contract-rule rows: 1320
- Market-price-ready rows: 1265
- Weather-path-ready rows: 1309
- Exact common-support rows: 1254
- Excluded rows: 66
- Complete common-support books: 114
- Market-price-missing rows: 55
- Weather-path-not-ready rows: 11
- Joint missing rows: 0

## Support by decision rule

| Rule | Candidate rows | Market ready | Weather ready | Common rows | Common books | Excluded dates |
|---|---:|---:|---:|---:|---:|---|
| 24h_prior | 330 | 297 | 330 | 297 | 27 | 2026-06-06|2026-06-07|2026-06-08 |
| 12h_prior | 330 | 308 | 330 | 308 | 28 | 2026-06-06|2026-06-07 |
| 6h_prior | 330 | 330 | 319 | 319 | 29 | 2026-06-24 |
| event_day_open | 330 | 330 | 330 | 330 | 30 |  |

## Market binary scores on exact support

| Rule | n | Mean Brier | Mean log score |
|---|---:|---:|---:|
| 24h_prior | 297 | 0.05871549 | 0.18402499 |
| 12h_prior | 308 | 0.05873689 | 0.18471691 |
| 6h_prior | 319 | 0.05601205 | 0.17742889 |
| event_day_open | 330 | 0.05575073 | 0.17737592 |

## Complete-book diagnostics

| Rule | Books | Mean normalised categorical log | Mean normalised multiclass Brier | Market modal contains winner | Modal tie rate | Deterministic bin hit |
|---|---:|---:|---:|---:|---:|---:|
| 24h_prior | 27 | 1.229658 | 0.648074 | 0.518519 | 0.037037 | 0.000000 |
| 12h_prior | 28 | 1.239007 | 0.648440 | 0.500000 | 0.000000 | 0.071429 |
| 6h_prior | 29 | 1.187355 | 0.617830 | 0.551724 | 0.000000 | 0.103448 |
| event_day_open | 30 | 1.189793 | 0.613239 | 0.633333 | 0.033333 | 0.066667 |

## Deterministic weather errors on exact support

| Rule | Dates | Mean error °C | MAE °C | RMSE °C | Underforecast rate |
|---|---:|---:|---:|---:|---:|
| 24h_prior | 27 | -1.774074 | 1.833333 | 2.016139 | 0.962963 |
| 12h_prior | 28 | -1.746429 | 1.746429 | 1.889539 | 1.000000 |
| 6h_prior | 29 | -1.655172 | 1.758621 | 1.978854 | 0.931034 |
| event_day_open | 30 | -1.656667 | 1.750000 | 2.011384 | 0.966667 |

## Interpretation

The market probabilities are scored only on rows that also have an admissible complete deterministic forecast path. Market probabilities are normalised only for complete-book distributional diagnostics; raw prices remain preserved.

Where multiple contracts share the highest market probability, the modal set is retained explicitly. Modal hit and overlap metrics are tie-aware; no market-ID tie-break is used.

The deterministic forecast is evaluated as a point forecast through temperature error and selected-bin accuracy. It is not assigned a probabilistic score and no Gaussian bridge or artificial ensemble feature is introduced.

This exact support is the canonical June input for subsequent local residual post-processing and expanded-sample freezing.
