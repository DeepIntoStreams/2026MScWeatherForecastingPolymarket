# 18tB admissible historical information sets

**PASS**

## Frozen objects

- Current date-rule decisions: 412
- Current decisions with a deterministic weather path: 375
- Historical residual observations: 375
- Admissible all-rule history pairs: 66,575
- Admissible same-rule history pairs: 16,638

## Admissibility rule

A historical date strictly precedes the current settlement date, its canonical HKO publication time is no later than the current decision cut-off, and its weather run was available by its own historical cut-off.

## Support by current decision rule

| Rule | Decisions | Prediction eligible | Any same-rule history | At least 8 | At least 14 | At least 16 | Median history | Maximum history |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 24h_prior | 103 | 96 | 95 | 87 | 80 | 78 | 44.0 | 91 |
| 12h_prior | 103 | 93 | 92 | 80 | 75 | 75 | 44.0 | 88 |
| 6h_prior | 103 | 91 | 89 | 80 | 75 | 74 | 44.0 | 89 |
| event_day_open | 103 | 95 | 93 | 81 | 80 | 76 | 46.0 | 93 |

## Methodological boundary

The residual history uses only HKO outcomes and deterministic weather forecasts. Market prices, contract probabilities, the archived Gaussian bridge and the current outcome are excluded.

Threshold flags are descriptive. The final minimum history threshold, model specification and chronological split remain unassigned.
