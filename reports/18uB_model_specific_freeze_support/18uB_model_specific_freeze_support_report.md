# 18uB model-specific freeze support

**PASS**

## Model-specific holdout freezes

| Scope | Freeze UTC | OOF rows | Selection rows | Fit rows | Holdout rows | External rows |
|---|---|---:|---:|---:|---:|---:|
| pooled_all_rules | 2026-05-20 16:00:00+00:00 | 144 | 136 | 208 | 40 | 119 |
| rule_specific_24h_prior | 2026-05-20 16:00:00+00:00 | 38 | 36 | 54 | 10 | 30 |
| rule_specific_12h_prior | 2026-05-21 04:00:00+00:00 | 35 | 33 | 51 | 10 | 30 |
| rule_specific_6h_prior | 2026-05-21 10:00:00+00:00 | 35 | 34 | 51 | 10 | 29 |
| rule_specific_event_day_open | 2026-05-21 16:00:00+00:00 | 36 | 35 | 54 | 10 | 30 |

## Frozen safeguards

- Every fold training date strictly precedes its first validation date.
- Every fold training label is available by the earliest applicable validation decision.
- Holdout and external labels are excluded from selection, fitting and calibration support.
- June receives the identical pre-holdout fit in the primary external evaluation.

## Deferred choices

GP kernel, tree specification, feature family, score hierarchy, calibrator and trading threshold remain unselected.
