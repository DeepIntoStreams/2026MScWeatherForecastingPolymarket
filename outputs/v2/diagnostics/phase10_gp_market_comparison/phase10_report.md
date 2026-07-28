# Phase 10 Exact-Common-Support GP versus Polymarket Comparison

## Status

PASSED

## Comparison design

The comparison uses only complete contract books for which every
canonical contract has both a Phase 9 GP probability and a valid
Polymarket decision price. No missing forecast or market price is
imputed.

Binary Brier and binary log scores use the raw Polymarket Yes price.
Categorical log and multiclass Brier scores use Polymarket prices
normalised within each complete contract book. GP probabilities already
sum to one.

Every paired difference is defined as:

`GP score minus Polymarket score`.

A negative value therefore means that the GP has the lower proper score.

## Selected market-price source

- Path: `data/interim/notebook02_sources/daily_max_forecasts/07_18s_expanded_exact_common_support_panel.csv`.
- Price column: `p_market`.
- Decision-rule column: `decision_rule`.
- Matching strategy: `normalised_event_label`.

## Exact common support

- Phase 9 GP-supported dates:
  102.
- Phase 9 GP-supported date-rule books:
  375.
- Complete common-support dates:
  97.
- Complete common-support date-rule books:
  350.
- Complete common-support contract-event rows:
  3850.
- Weather-plus-market training dates:
  67.
- June out-of-sample validation dates:
  30.

## June out-of-sample paired results

| Metric | GP | Polymarket | Difference | 95% bootstrap interval | Dates |
|---|---:|---:|---:|---:|---:|
| Mean binary Brier | 0.068198 | 0.058874 | 0.009324 | [0.003825, 0.014640] | 30 |
| Mean binary log | 0.225029 | 0.186401 | 0.038628 | [0.022004, 0.054204] | 30 |
| Categorical log | 1.618265 | 1.260923 | 0.357342 | [0.214437, 0.492830] | 30 |
| Multiclass Brier | 0.750180 | 0.648471 | 0.101710 | [0.043014, 0.158161] | 30 |

The intervals above are percentile intervals from
10,000
date-level bootstrap replications. They are descriptive uncertainty
intervals for the realised paired score differences.

## Weather-plus-market training-period paired results

| Metric | GP | Polymarket | Difference | 95% bootstrap interval | Dates |
|---|---:|---:|---:|---:|---:|
| Mean binary Brier | 0.065969 | 0.067283 | -0.001314 | [-0.006167, 0.003434] | 67 |
| Mean binary log | 0.212410 | 0.215482 | -0.003073 | [-0.020121, 0.013388] | 67 |
| Categorical log | 1.501522 | 1.519731 | -0.018209 | [-0.173263, 0.125242] | 67 |
| Multiclass Brier | 0.725658 | 0.738361 | -0.012703 | [-0.064421, 0.040248] | 67 |

## June calibration diagnostics

| Model | Event rows | ECE | MCE | Brier | Calibration bias |
|---|---:|---:|---:|---:|---:|
| GP | 1254 | 0.031382 | 0.531411 | 0.067359 | -0.000000 |
| Polymarket | 1254 | 0.043484 | 0.385000 | 0.057253 | 0.002798 |

## Integrity

- Duplicate exact-common-support event keys: 0.
- Every complete book contains exactly one realised Yes event.
- GP probabilities sum to one within every book.
- Normalised Polymarket probabilities sum to one within every book.
- All four decision rules have June common-support observations.
- Market prices were not used to fit or select the GP.
- June observations were not used to refit or select a model.

## Evidential boundary

The comparison concerns only the exact complete-book intersection.
Its sample size is therefore smaller than either the standalone GP
evaluation or the standalone market evaluation. Results outside this
intersection are not inferred or imputed.
