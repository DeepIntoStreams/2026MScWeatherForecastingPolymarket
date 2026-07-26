# Canonical Notebook Build Specification

This document defines what each final notebook owns and which archived notebooks may supply logic.

## Notebook 00 — Project configuration and manifest

**Responsibility:** Declared dates, source registry, model registry, seeds, environment, temporal folds and run manifest.

**Required output:** Configuration and manifest files; no empirical result.

**Permitted historical sources:**

- `18sA_canonical_source_adapters.ipynb`
- `18sB_expanded_sample_freeze.ipynb`
- `18uA_chronological_partition_and_folds.ipynb`
- `18uB_model_specific_freeze_support.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 01 — HKO settlement and event certification

**Responsibility:** Official HKO outcome, event boundaries, one-decimal settlement and exactly-one-winner tests.

**Required output:** Certified contract-event panel and settlement manifest.

**Permitted historical sources:**

- `17j_hko_polymarket_upper_tail_metadata_and_resolution_audit.ipynb`
- `17k_hko_upper_tail_certification_dossier.ipynb`
- `17l_hko_contract_rule_text_certification.ipynb`
- `18a_hko_certified_upper_tail_price_panel.ipynb`
- `18b_hko_certified_upper_tail_outcome_and_decision_panel.ipynb`
- `18c_hko_daily_extract_outcome_reconciliation.ipynb`
- `18d_hko_daily_extract_source_discovery.ipynb`
- `18e_hko_historical_market_hko_alignment_to_20260531.ipynb`
- `18f_hko_metob_polymarket_historical_panel_to_20260531.ipynb`
- `18i_hko_empirical_baseline_reporting.ipynb`
- `18j_gamma_metadata_settlement_family_audit.ipynb`
- `18j_v2_fix_contract_event_parsing.ipynb`
- `18j_v2_fix_contract_event_parsing_COMPLETE.ipynb`
- `18k_full_hko_contract_event_target_panel.ipynb`
- `18k_full_hko_contract_event_target_panel_FIX.ipynb`
- `18k_full_hko_contract_event_target_panel_FIX2.ipynb`
- `18l_full_hko_contract_event_clob_price_recovery.ipynb`
- `18n_june_2026_contract_event_audit.ipynb`
- `18o_june_2026_hko_realised_outcomes.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 02 — Weather training panel

**Responsibility:** Historically admissible deterministic forecasts, complete HKT paths, HKO outcomes, residuals and product metadata.

**Required output:** Expanded forecast-HKO training panel and admission manifest.

**Permitted historical sources:**

- `18q_june_2026_ecmwf_single_run_forecasts.ipynb`
- `18tA_hko_publication_availability.ipynb`
- `18tB_admissible_historical_information_sets.ipynb`
- `19a_hko_open_meteo_ecmwf_single_run_forecast_ingestion.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 03 — Market evaluation panel

**Responsibility:** Certified contracts, historical market records, record age, raw YES values and normalised complete books.

**Required output:** Exact market evaluation panel and support manifest.

**Permitted historical sources:**

- `18p_june_2026_clob_market_price_recovery.ipynb`
- `18r_june_2026_market_weather_common_support.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 04 — Gaussian-process implementation audit

**Responsibility:** Exact estimator, transformations, covariance, noise, jitter, variance semantics and direct matrix reproduction.

**Required output:** Passed GP audit report and unit-test evidence.

**Permitted historical sources:**

- `18vB1_baseline_gp_temporal_oof.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 05 — Model fitting and selection

**Responsibility:** Five-family chronological OOF predictions on exact common support.

**Required output:** Selected continuous model and development diagnostics.

**Permitted historical sources:**

- `18vA_residual_model_design_and_features.ipynb`
- `18vB1_baseline_gp_temporal_oof.ipynb`
- `18vB2_tree_temporal_oof.ipynb`
- `18vC_common_support_scoring_and_selection.ipynb`
- `18vD_selected_models_blind_predictions.ipynb`
- `19c_ecmwf_proxy_bias_scale_calibration.ipynb`
- `20a_supervised_feature_matrix.ipynb`
- `20b_validation_design.ipynb`
- `20c_catboost_postprocessing.ipynb`
- `20e_locked_holdout_evaluation.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 06 — Quantiles, event probabilities and adjustment

**Responsibility:** Ninety-nine quantiles, monotone repair, event mapping, dispersion adjustment and probability regularisation.

**Required output:** Locked coherent probability specification.

**Permitted historical sources:**

- `18wA_contract_probability_mapping.ipynb`
- `18wB_development_probability_calibration.ipynb`
- `18wC_blind_calibrated_probability_release.ipynb`
- `20d_calibration_coherence.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 07 — External evaluation and paired inference

**Responsibility:** External continuous CRPS, market comparison and settlement-date bootstrap.

**Required output:** External score tables and paired uncertainty.

**Permitted historical sources:**

- `18r_june_2026_market_weather_common_support.ipynb`
- `18wD_holdout_external_probability_evaluation.ipynb`
- `19b_common_support_market_vs_ecmwf_proxy_comparison.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 08 — Final trading and PnL

**Responsibility:** Development-selected rule and threshold, one-share external simulation and focused sensitivities.

**Required output:** Final trading evidence and bootstrap report.

**Permitted historical sources:**

- `18xA_development_trading_selection.ipynb`
- `18xB_blind_trading_signal_release.ipynb`
- `18xC_controlled_unblinding_trading_simulation.ipynb`
- `18xD_trading_robustness_and_figures.ipynb`
- `21a_simple_edge_trading.ipynb`
- `21b_full_event_book_trading.ipynb`
- `21c_cost_staleness_robustness.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

## Notebook 09 — Thesis tables, figures and audit

**Responsibility:** Generate final outputs from one empirical release and reconcile every thesis number.

**Required output:** Tables, figures, hashes and numerical audit.

**Permitted historical sources:**

- `18m_full_hko_market_only_baseline_diagnostics.ipynb`
- `18yA_final_empirical_synthesis.ipynb`
- `18yB_thesis_output_freeze.ipynb`
- `21d_dissertation_ready_empirical.ipynb`
- `21e_freeze_final_empirical_release.ipynb`

**Prohibited migration:**

- old output cells;
- old headline numbers;
- duplicated helper functions;
- superseded sample dates;
- undocumented manual edits;

