# Phase 16 Raw and Static Gaussian Benchmarks

## Status

PASSED

## Why the static benchmark was previously absent

Phases 7 and 8 were originally constructed to compare RBF and Matérn-3/2 Gaussian-process covariance families. The static rule-specific Gaussian law was introduced later as the required attribution benchmark, but no same-support chronological output had yet been generated. Phase 16 now fits that benchmark on the identical expanding histories and validation observations rather than inferring or imputing a result.

## Chronological comparison design

- Validation dates: 365.
- Decision rules: 4.
- Model rows: 5,840.
- Models: raw point forecast, static Gaussian, RBF GP and Matérn-3/2 GP.
- Static moments are estimated separately by rule and fold from earlier weather-only residuals.
- Raw point CRPS equals absolute temperature error.
- All Gaussian models are evaluated with closed-form Gaussian CRPS.
- Every aggregate score gives each target date one unit of weight.
- Paired uncertainty intervals resample target dates 10,000 times.

## Overall mean date CRPS

- Raw point forecast: 1.745684932 degrees Celsius.
- Static Gaussian: 0.911754550 degrees Celsius.
- RBF GP, analytical CRPS: 0.877561468 degrees Celsius.
- Matérn-3/2 GP, analytical CRPS: 0.863339999 degrees Celsius.
- RBF GP, frozen legacy Phase 7 CRPS: 0.877561468 degrees Celsius.
- Matérn-3/2 GP, frozen legacy Phase 7 CRPS: 0.863339999 degrees Celsius.

## Main paired attribution results

- Static minus raw: -0.833930381 with 95% date-bootstrap interval [-0.946081103, -0.722088774].
- Matérn-3/2 minus static: -0.048414551 with 95% date-bootstrap interval [-0.070800095, -0.026406623].
- Matérn-3/2 minus RBF: -0.014221469 with 95% date-bootstrap interval [-0.020771434, -0.007946326].
- Every difference is first-model CRPS minus second-model CRPS; negative is better for the first model.

## Interpretation

The static Gaussian correction improves on the raw deterministic point forecast under mean date CRPS.

The Matérn-3/2 GP improves on the static Gaussian correction under mean date CRPS, so conditional residual structure adds descriptive predictive value.

Rule-specific results are stored in `phase16_model_scores_by_rule.csv`; validation-block results are stored in `phase16_model_scores_by_block.csv`. Phase 18 will analyse their stability in depth rather than overinterpreting the aggregate score alone.

## Event-score aggregation reconciliation

- The certified Phase 9 headline scores used equal date-rule-book weighting.
- Because some market-period dates lack one or more decision-rule forecasts, equal book weighting differs slightly from equal target-date weighting.
- Phase 16 preserves the certified Phase 9 row under `phase9_legacy_forecast_supported` and separately reports the completion programme's date-balanced forecast-supported scores.
- This difference is an aggregation convention, not a change to any probability or outcome.

## Full-history static event probabilities

- Four rule-specific static Gaussian laws were estimated from 730 weather-only dates each.
- They were applied to 375 forecast-supported date-rule books over 102 dates.
- The resulting 4,125 contract-event probabilities sum to one within every book.
- A 350-book, 97-date exact-common-support static panel was also created for later market attribution.
- No market price or June outcome was used to estimate the static model.

## Closed Phase 14 gaps

- G01: static Gaussian chronological benchmark.
- G02: raw point forecast chronological benchmark.

## Evidential boundary

Phase 16 does not alter the certified Phase 7 or Phase 8 GP models. The raw and static comparators use the same chronological validation support as the two saved GP families. The full-history static market-period law uses only the 730-date weather history. Market prices are used only to identify the already certified exact-common-support subset for secondary score comparison.
