# Phase 1 — Complete Row-Level Evidence Recovery

Generated: `2026-07-31T22:04:28.155002+00:00`

## Overall status: **PASSED**

The phase is read-only with respect to the frozen source tag. It inventories evidence, certifies master keys, recovers GP implementation evidence, reconstructs raw/static event books and canonicalises existing event-probability outputs.

## Provenance

```json
{
  "frozen_commit": "1b0900086c315588b0dc41225e41c2b5f2189bfa",
  "frozen_ref": "v2-empirical-complete",
  "frozen_root": "/private/tmp/2026MScWeatherForecastingPolymarket_v2_frozen",
  "frozen_tag_object": "5d48edb55074f4018d842482bab9f7bf4ab1c01e",
  "generated_utc": "2026-07-31T22:04:26.153081+00:00",
  "repo_root": "/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket",
  "working_branch": "edward-v70-empirical-finalisation",
  "working_head": "c0055d91a684a9bac33d429e18ad364c4f925233",
  "working_tree_clean_before_phase": true
}
```

## Completion register

| item                                     | passed   | critical   | detail                                                                                                                                                                                                                      |
|:-----------------------------------------|:---------|:-----------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| weather residual panel                   | True     | True       | {"dates": 730, "duplicate_keys": 0, "rows": 2920, "rules": 4, "source_path": "outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv", "status": "FOUND", "unique_keys": 2920}                                  |
| market prediction keys                   | True     | True       | {"dates": 102, "duplicate_keys": 0, "rows": 375, "rules": 4, "source_path": "data/processed/v2/phase8_clean_gp/phase8_gp_market_period_predictions.csv", "status": "FOUND", "unique_keys": 375}                             |
| phase9 event probability panel           | True     | True       | {"dates": 102, "duplicate_keys": 0, "rows": 4125, "rules": 4, "source_path": "outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_gp_contract_event_probability_panel.csv", "status": "FOUND", "unique_keys": 4125} |
| phase10 exact support panel              | True     | True       | {"dates": 97, "duplicate_keys": 0, "rows": 3850, "rules": 4, "source_path": "outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv", "status": "FOUND", "unique_keys": 3850}     |
| GP implementation text evidence          | True     | True       | matching lines=265                                                                                                                                                                                                          |
| serialised GP model evidence             | True     | False      | registry rows=4                                                                                                                                                                                                             |
| raw event-book reconstruction            | True     | True       | models=['raw', 'static']                                                                                                                                                                                                    |
| static event-book reconstruction         | True     | True       | models=['raw', 'static']                                                                                                                                                                                                    |
| existing coherent GP/event-book evidence | True     | True       | models=['market', 'matern']                                                                                                                                                                                                 |
| RBF full-history market book recovered   | False    | False      | models=['market', 'matern', 'raw', 'static']                                                                                                                                                                                |

## Master-key summaries

### Weather residual panel

```json
{
  "dates": 730,
  "duplicate_keys": 0,
  "rows": 2920,
  "rules": 4,
  "source_path": "outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv",
  "status": "FOUND",
  "unique_keys": 2920
}
```

### Market-period forecast keys

```json
{
  "dates": 102,
  "duplicate_keys": 0,
  "rows": 375,
  "rules": 4,
  "source_path": "data/processed/v2/phase8_clean_gp/phase8_gp_market_period_predictions.csv",
  "status": "FOUND",
  "unique_keys": 375
}
```

### Phase 9 event rows

```json
{
  "dates": 102,
  "duplicate_keys": 0,
  "rows": 4125,
  "rules": 4,
  "source_path": "outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_gp_contract_event_probability_panel.csv",
  "status": "FOUND",
  "unique_keys": 4125
}
```

### Phase 10 exact-support rows

```json
{
  "dates": 97,
  "duplicate_keys": 0,
  "rows": 3850,
  "rules": 4,
  "source_path": "outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv",
  "status": "FOUND",
  "unique_keys": 3850
}
```

## Existing event-book checks

| relative_path                                                                                       | probability_column            | event_key_strategy   |   rows |   books |   books_with_11_events |   books_mass_close_1 | probabilities_in_unit_interval   |   max_mass_error | status   |
|:----------------------------------------------------------------------------------------------------|:------------------------------|:---------------------|-------:|--------:|-----------------------:|---------------------:|:---------------------------------|-----------------:|:---------|
| outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv    | gp_event_probability          | event_label          |   3850 |     350 |                    350 |                  350 | True                             |      7.77156e-16 | READABLE |
| outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv    | market_probability_raw        | event_label          |   3850 |     350 |                    350 |                    0 | True                             |      0.3         | READABLE |
| outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv    | market_probability_normalised | event_label          |   3850 |     350 |                    350 |                  350 | True                             |      8.88178e-16 | READABLE |
| outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_gp_contract_event_probability_panel.csv | gp_event_probability          | event_label          |   4125 |     375 |                    375 |                  375 | True                             |      7.77156e-16 | READABLE |
| outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_june_out_of_sample_event_panel.csv      | gp_event_probability          | event_label          |   1309 |     119 |                    119 |                  119 | True                             |      7.77156e-16 | READABLE |
| outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_weather_plus_market_event_panel.csv     | gp_event_probability          | event_label          |   2816 |     256 |                    256 |                  256 | True                             |      6.66134e-16 | READABLE |
| outputs/v2_completion/phase20_event_discrepancy_panel.csv                                           | gp_probability                | event_key            |   3850 |     350 |                    350 |                  350 | True                             |      7.77156e-16 | READABLE |
| outputs/v2_completion/phase20_event_discrepancy_panel.csv                                           | market_source_probability     | event_key            |   3850 |     350 |                    350 |                  350 | True                             |      8.88178e-16 | READABLE |
| outputs/v2_completion/phase20_event_discrepancy_panel.csv                                           | market_probability            | event_key            |   3850 |     350 |                    350 |                  350 | True                             |      8.88178e-16 | READABLE |
| outputs/v2_completion/phase20_exact_common_support_event_panel.csv                                  | gp_probability                | event_key            |   3850 |     350 |                    350 |                  350 | True                             |      7.77156e-16 | READABLE |
| outputs/v2_completion/phase20_exact_common_support_event_panel.csv                                  | market_source_probability     | event_key            |   3850 |     350 |                    350 |                  350 | True                             |      8.88178e-16 | READABLE |
| outputs/v2_completion/phase20_exact_common_support_event_panel.csv                                  | market_probability            | event_key            |   3850 |     350 |                    350 |                  350 | True                             |      8.88178e-16 | READABLE |

## Raw/static reconstruction checks

| check                                  | passed   | detail                                          |
|:---------------------------------------|:---------|:------------------------------------------------|
| raw_static_books_nonempty              | True     | rows=8250, books=750                            |
| raw_static_expected_support            | True     | rows=8250 expected=8250; books=750 expected=750 |
| raw_static_11_events_per_book          | True     | bad_books=0                                     |
| raw_static_mass_closure                | True     | max_error=0.000e+00                             |
| raw_static_probabilities_unit_interval | True     |                                                 |

## Interpretation boundary

- This phase does not reselect or refit the frozen Matérn model.
- Raw and static event books are deterministic reconstructions from frozen inputs.
- Existing RBF or Matérn books are canonicalised only when found in frozen outputs.
- A missing full-history RBF market book is recorded as a non-critical recovery gap; it must not be silently approximated with a different GP specification.
