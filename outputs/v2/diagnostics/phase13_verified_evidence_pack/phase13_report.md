# Phase 13 Verified Evidence Pack

## Status

PASSED

## Objective

Consolidate the verified empirical findings from Phases 9–12 into thesis-ready summary tables and a single evidence-pack report.

## Source diagnostics

- phase9: `outputs/v2/diagnostics/phase9_gp_event_probabilities`
  - report: `outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_report.md`
  - manifest: `outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_manifest.json`
- phase10: `outputs/v2/diagnostics/phase10_gp_market_comparison`
  - report: `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_report.md`
  - manifest: `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_manifest.json`
- phase11: `outputs/v2/diagnostics/phase11_frozen_value_gap_trading`
  - report: `outputs/v2/diagnostics/phase11_frozen_value_gap_trading/phase11_report.md`
  - manifest: `outputs/v2/diagnostics/phase11_frozen_value_gap_trading/phase11_manifest.json`
- phase12: `outputs/v2/diagnostics/phase12_robustness_attribution`
  - report: `outputs/v2/diagnostics/phase12_robustness_attribution/phase12_report.md`
  - manifest: `outputs/v2/diagnostics/phase12_robustness_attribution/phase12_manifest.json`

## Consolidated empirical summary

### Phase 9: GP contract-event probability construction

- Forecast-supported dates: 102.
- Forecast-supported date-rule rows: 375.
- June mean binary Brier score: 0.06793796.
- June mean binary log score: 0.22272225.
- June mean continuous CRPS: 0.61501747 degrees Celsius.

### Phase 10: GP versus Polymarket exact-common-support comparison

- Complete common-support dates: 97.
- Complete common-support date-rule books: 350.
- Complete common-support contract-event rows: 3850.
- June paired score differences (`GP score minus Polymarket score`):
  - Mean binary Brier: 0.009324 with 95% bootstrap interval [0.003825, 0.014640] over 30 dates.
  - Mean binary log: 0.038628 with 95% bootstrap interval [0.022004, 0.054204] over 30 dates.
  - Categorical log: 0.357342 with 95% bootstrap interval [0.214437, 0.492830] over 30 dates.
  - Multiclass Brier: 0.10171 with 95% bootstrap interval [0.043014, 0.158161] over 30 dates.

### Phase 11: Frozen value-gap trading

- Primary decision rule: event_day_open.
- Frozen value-gap threshold: 0.12.
- June trades at the reference cost: 16.
- Total June net PnL at the reference cost: 0.0235.
- Bootstrap probability that total June net PnL is positive: 0.4705.

### Phase 12: Robustness, attribution and synthesis

- Post-hoc June rank: 13 out of 104 rule-threshold candidates.
- Post-hoc total June net PnL: 0.0235.
- Post-hoc mean date net PnL: 0.000783.
- Post-hoc return on committed capital: 0.024066.

## Final thesis-facing synthesis

1. The two-year Matérn GP produced coherent contract-event probabilities and materially improved the credibility of the weather-only probabilistic construction.
2. On the exact complete-book intersection, June Polymarket prices achieved lower binary and categorical proper scores than the GP on all four primary comparisons.
3. The frozen value-gap strategy produced only a small positive June point estimate at the reference transaction cost, with weak uncertainty support.
4. The Phase 12 synthesis further weakens any claim of a stable trading edge.

## Evidential boundary

- phase9: No market price was used. June data were not used to refit the GP, select a kernel, or impute missing forecasts.
- phase10: The comparison concerns only the exact complete-book intersection. Results outside this intersection are not inferred or imputed.
- phase11: The trading exercise is a frozen historical simulation, not evidence of live executable arbitrage.
- phase12: This remains a historical simulation. It does not establish live executability, future profitability or causal market efficiency. Recorded prices may not represent obtainable fills. Queue priority, partial execution, market impact, capital competition across simultaneous contracts and operational latency are outside the empirical design.  No missing forecast or price was imputed. No June observation was used to change the frozen strategy.

## Output files

- `phase13_evidential_boundaries.csv`
- `phase13_key_metrics_long.csv`
- `phase13_main_results_table.csv`
- `phase13_phase10_june_calibration.csv`
- `phase13_phase10_june_paired_results.csv`
- `phase13_phase10_training_paired_results.csv`
- `phase13_phase11_cost_sensitivity.csv`
- `phase13_phase11_frozen_strategies.csv`
- `phase13_phase12_summary.csv`
- `phase13_phase9_summary.csv`
- `phase13_source_inventory.csv`
