# Phase 14 Baseline Freeze and Empirical Gap Register

## Status

PASSED

## Certified starting boundary

- Base branch: `edward-v2-two-year-weather-gp`.
- Phase 13 commit: `626a7dc4bc746c0dc897db13d949882cace725fa`.
- Protected tag: `v2-phase13-certified`.
- Completion branch: `edward-v2-gp-depth-completion`.
- Source files inventoried and hashed: 132.
- Open empirical gaps registered: 17.

## Independently reconciled support counts

- weather_only_dates: 730 — PASSED — source `outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv`.
- weather_only_date_rule_rows: 2920 — PASSED — source `outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv`.
- decision_rules: 4 — PASSED — source `outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv`.
- chronological_validation_dates: 365 — PASSED — source `outputs/v2/diagnostics/07_gp_validation_predictions.csv`.
- initial_training_dates: 365 — PASSED — source `outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv|outputs/v2/diagnostics/07_gp_validation_predictions.csv`.
- settlement_market_dates: 103 — PASSED — source `data/processed/18s_expanded_march_june_canonical_sample/18s_expanded_certified_contract_outcome_panel.csv`.
- canonical_contract_rows: 1133 — PASSED — source `data/processed/18s_expanded_march_june_canonical_sample/18s_expanded_certified_contract_outcome_panel.csv`.
- forecast_supported_dates: 102 — PASSED — source `outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_gp_contract_event_probability_panel.csv`.
- forecast_supported_date_rule_rows: 375 — PASSED — source `outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_gp_contract_event_probability_panel.csv`.
- theoretical_market_date_rule_rows: 412 — PASSED — source `data/processed/18s_expanded_march_june_canonical_sample/18s_expanded_certified_contract_outcome_panel.csv`.
- unsupported_date_rule_rows: 37 — PASSED — source `outputs/v2/diagnostics/phase9_gp_event_probabilities/phase9_gp_contract_event_probability_panel.csv`.
- exact_common_support_dates: 97 — PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv`.
- exact_common_support_date_rule_books: 350 — PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv`.
- exact_common_support_event_rows: 3850 — PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv`.
- weather_plus_market_development_dates: 67 — PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv`.
- june_external_dates: 30 — PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_exact_common_support_event_panel.csv`.

## Phase 8-13 headline evidence

- phase7_rbf_mean_date_crps_c: PASSED — source `outputs/v2/diagnostics/07_gp_validation_predictions.csv`.
- phase7_matern32_mean_date_crps_c: PASSED — source `outputs/v2/diagnostics/07_gp_validation_predictions.csv`.
- phase9_binary_brier: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_key_metrics_long.csv`.
- phase9_binary_log: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_key_metrics_long.csv`.
- phase9_categorical_log: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_key_metrics_long.csv`.
- phase9_multiclass_brier: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_key_metrics_long.csv`.
- phase9_continuous_crps_c: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_key_metrics_long.csv`.
- phase9_absolute_error_c: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_key_metrics_long.csv`.
- phase10_june_binary_brier_difference: PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_report.md`.
- phase10_june_binary_log_difference: PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_report.md`.
- phase10_june_categorical_log_difference: PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_report.md`.
- phase10_june_multiclass_brier_difference: PASSED — source `outputs/v2/diagnostics/phase10_gp_market_comparison/phase10_report.md`.
- phase11_selected_threshold: PASSED — source `data/processed/17l_all_formally_certified_rows_for_manual_inspection.csv`.
- phase11_june_trades: PASSED — source `data/processed/17l_all_formally_certified_rows_for_manual_inspection.csv`.
- phase11_june_net_pnl_cost_0_01: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_key_metrics_long.csv`.
- phase12_probability_positive_total_pnl: PASSED — source `outputs/v2/diagnostics/phase11_frozen_value_gap_trading/phase11_manifest.json`.
- phase12_summary_file_present: PASSED — source `outputs/v2/diagnostics/phase12_robustness_attribution/phase12_june_trade_concentration_summary.csv|outputs/v2/diagnostics/phase12_robustness_attribution/phase12_leave_one_date_out_selection_summary.csv|outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_phase12_summary.csv`.
- phase13_report_status: PASSED — source `outputs/v2/diagnostics/phase13_verified_evidence_pack/phase13_report.md`.

## Empirical completion boundary

The following work remains open and is deliberately not inferred or imputed:

- G01: Static Gaussian chronological benchmark — OPEN.
- G02: Raw point forecast chronological benchmark — OPEN.
- G03: Exact feature formulas and scaling — OPEN.
- G04: Exact response transformation — OPEN.
- G05: Observation noise, WhiteKernel and jitter — OPEN.
- G06: Gaussian CRPS implementation — OPEN.
- G07: Rule-specific deterministic error — OPEN.
- G08: Rule and validation-block model results — OPEN.
- G09: GP hyperparameter stability — OPEN.
- G10: Predictive calibration and sharpness — OPEN.
- G11: Residual dependence and heteroskedasticity — OPEN.
- G12: Missing forecast support — OPEN.
- G13: Systematic GP-market discrepancy structure — OPEN.
- G14: Forecast combination — OPEN.
- G15: Clean-environment reproducibility — OPEN.
- G16: Consolidated thesis evidence pack — OPEN.
- G17: Independent final freeze — OPEN.

## Integrity statement

Phase 14 creates only new Version 2 completion configuration, tooling and outputs. It does not alter any certified Phase 1-13 file. All later phases must preserve the Phase 13 weather, market and trading evidence unless a documented defect is established.
