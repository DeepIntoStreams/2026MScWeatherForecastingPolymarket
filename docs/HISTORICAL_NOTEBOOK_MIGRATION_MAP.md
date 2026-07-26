# Exact Historical Notebook Migration Map

Archive branch: `archive/17j-plus-18n-18y-20260726`

Historical notebooks inspected: **72**

## Decision summary

- ARCHIVE_ONLY: **15**
- MIGRATE_AND_AUDIT: **1**
- MIGRATE_LOGIC: **54**
- REFERENCE_ONLY: **2**

## Canonical destination summary

- Notebook 00: **4** historical sources
- Notebook 01: **19** historical sources
- Notebook 02: **4** historical sources
- Notebook 03: **1** historical sources
- Notebook 03 and 07: **1** historical sources
- Notebook 04 and 05: **1** historical sources
- Notebook 05: **9** historical sources
- Notebook 06: **4** historical sources
- Notebook 07: **2** historical sources
- Notebook 08: **7** historical sources
- Notebook 09: **5** historical sources
- Notebook None: **15** historical sources

## Notebook-level decisions

| Historical notebook | Decision | Final destination | Action |
|---|---|---|---|
| `01_polymarket_api_exploration.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `02_weather_data_exploration.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `03_single_market_mini_pipeline.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `04_aifs_ecmwf_output_check.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `05_nvidia_earth2_availability_check.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `06_nvidia_earth2_colab_feasibility.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `07_hko_settlement_source_retrieval.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `08_time_alignment_and_lead_time_framework.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `09_threshold_classification_dataset.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `10_baseline_threshold_classifier.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `11_raw_weather_forecast_benchmark.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `12_market_model_probability_discrepancy.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `13_probability_scoring_and_calibration.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `14_binary_trading_strategy_diagnostics.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `15_robustness_checks.ipynb` | ARCHIVE_ONLY | None | Do not migrate |
| `17j_hko_polymarket_upper_tail_metadata_and_resolution_audit.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `17k_hko_upper_tail_certification_dossier.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `17l_hko_contract_rule_text_certification.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18a_hko_certified_upper_tail_price_panel.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18b_hko_certified_upper_tail_outcome_and_decision_panel.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18c_hko_daily_extract_outcome_reconciliation.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18d_hko_daily_extract_source_discovery.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18e_hko_historical_market_hko_alignment_to_20260531.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18f_hko_metob_polymarket_historical_panel_to_20260531.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18i_hko_empirical_baseline_reporting.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18j_gamma_metadata_settlement_family_audit.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18j_v2_fix_contract_event_parsing.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18j_v2_fix_contract_event_parsing_COMPLETE.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18k_full_hko_contract_event_target_panel.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18k_full_hko_contract_event_target_panel_FIX.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18k_full_hko_contract_event_target_panel_FIX2.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18l_full_hko_contract_event_clob_price_recovery.ipynb` | MIGRATE_LOGIC | 01 | Inspect and extract only non-duplicated certification logic |
| `18m_full_hko_market_only_baseline_diagnostics.ipynb` | REFERENCE_ONLY | 09 | Use only as a regression benchmark |
| `18n_june_2026_contract_event_audit.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18o_june_2026_hko_realised_outcomes.ipynb` | MIGRATE_LOGIC | 01 | Extract only the latest source retrieval, event parsing, one-decimal settlement and integrity checks. |
| `18p_june_2026_clob_market_price_recovery.ipynb` | MIGRATE_LOGIC | 03 | Extract final as-of price recovery, raw YES value, record age and complete-book checks. |
| `18q_june_2026_ecmwf_single_run_forecasts.ipynb` | MIGRATE_LOGIC | 02 | Extract forecast issue-time selection, HKT path checks, HKO outcome admissibility and residual construction. |
| `18r_june_2026_market_weather_common_support.ipynb` | MIGRATE_LOGIC | 03 and 07 | Extract support-key construction into Notebook 03 and comparison logic into Notebook 07. |
| `18sA_canonical_source_adapters.ipynb` | MIGRATE_LOGIC | 00 | Extract source adapters, sample declarations, temporal fold rules and manifest logic. |
| `18sB_expanded_sample_freeze.ipynb` | MIGRATE_LOGIC | 00 | Extract source adapters, sample declarations, temporal fold rules and manifest logic. |
| `18tA_hko_publication_availability.ipynb` | MIGRATE_LOGIC | 02 | Extract forecast issue-time selection, HKT path checks, HKO outcome admissibility and residual construction. |
| `18tB_admissible_historical_information_sets.ipynb` | MIGRATE_LOGIC | 02 | Extract forecast issue-time selection, HKT path checks, HKO outcome admissibility and residual construction. |
| `18uA_chronological_partition_and_folds.ipynb` | MIGRATE_LOGIC | 00 | Extract source adapters, sample declarations, temporal fold rules and manifest logic. |
| `18uB_model_specific_freeze_support.ipynb` | MIGRATE_LOGIC | 00 | Extract source adapters, sample declarations, temporal fold rules and manifest logic. |
| `18vA_residual_model_design_and_features.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `18vB1_baseline_gp_temporal_oof.ipynb` | MIGRATE_AND_AUDIT | 04 and 05 | Migrate GP implementation only after auditing scaling, kernel composition, noise, jitter and predictive variance. |
| `18vB2_tree_temporal_oof.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `18vC_common_support_scoring_and_selection.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `18vD_selected_models_blind_predictions.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `18wA_contract_probability_mapping.ipynb` | MIGRATE_LOGIC | 06 | Extract the 99-quantile mapping, coherence checks, dispersion adjustment and probability regularisation. |
| `18wB_development_probability_calibration.ipynb` | MIGRATE_LOGIC | 06 | Extract the 99-quantile mapping, coherence checks, dispersion adjustment and probability regularisation. |
| `18wC_blind_calibrated_probability_release.ipynb` | MIGRATE_LOGIC | 06 | Extract the 99-quantile mapping, coherence checks, dispersion adjustment and probability regularisation. |
| `18wD_holdout_external_probability_evaluation.ipynb` | MIGRATE_LOGIC | 07 | Extract exact-common-book comparison logic. Replace the old period design with the final August external design and add paired date-level inference. |
| `18xA_development_trading_selection.ipynb` | MIGRATE_LOGIC | 08 | Consolidate development selection, one-share simulation, cost sensitivity, record-age sensitivity and date bootstrap into one implementation. |
| `18xB_blind_trading_signal_release.ipynb` | MIGRATE_LOGIC | 08 | Consolidate development selection, one-share simulation, cost sensitivity, record-age sensitivity and date bootstrap into one implementation. |
| `18xC_controlled_unblinding_trading_simulation.ipynb` | MIGRATE_LOGIC | 08 | Consolidate development selection, one-share simulation, cost sensitivity, record-age sensitivity and date bootstrap into one implementation. |
| `18xD_trading_robustness_and_figures.ipynb` | MIGRATE_LOGIC | 08 | Consolidate development selection, one-share simulation, cost sensitivity, record-age sensitivity and date bootstrap into one implementation. |
| `18yA_final_empirical_synthesis.ipynb` | MIGRATE_LOGIC | 09 | Extract table, figure, integrity and numerical reconciliation logic. Do not migrate old final numbers. |
| `18yB_thesis_output_freeze.ipynb` | MIGRATE_LOGIC | 09 | Extract table, figure, integrity and numerical reconciliation logic. Do not migrate old final numbers. |
| `19a_hko_open_meteo_ecmwf_single_run_forecast_ingestion.ipynb` | MIGRATE_LOGIC | 02 | Extract forecast issue-time selection, HKT path checks, HKO outcome admissibility and residual construction. |
| `19b_common_support_market_vs_ecmwf_proxy_comparison.ipynb` | MIGRATE_LOGIC | 07 | Extract exact-common-book comparison logic. Replace the old period design with the final August external design and add paired date-level inference. |
| `19c_ecmwf_proxy_bias_scale_calibration.ipynb` | REFERENCE_ONLY | 05 | Use only for historical reconciliation |
| `20a_supervised_feature_matrix.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `20b_validation_design.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `20c_catboost_postprocessing.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `20d_calibration_coherence.ipynb` | MIGRATE_LOGIC | 06 | Extract the 99-quantile mapping, coherence checks, dispersion adjustment and probability regularisation. |
| `20e_locked_holdout_evaluation.ipynb` | MIGRATE_LOGIC | 05 | Extract final feature construction, temporal OOF fitting, common-support scoring and selection logic. |
| `21a_simple_edge_trading.ipynb` | MIGRATE_LOGIC | 08 | Consolidate development selection, one-share simulation, cost sensitivity, record-age sensitivity and date bootstrap into one implementation. |
| `21b_full_event_book_trading.ipynb` | MIGRATE_LOGIC | 08 | Consolidate development selection, one-share simulation, cost sensitivity, record-age sensitivity and date bootstrap into one implementation. |
| `21c_cost_staleness_robustness.ipynb` | MIGRATE_LOGIC | 08 | Consolidate development selection, one-share simulation, cost sensitivity, record-age sensitivity and date bootstrap into one implementation. |
| `21d_dissertation_ready_empirical.ipynb` | MIGRATE_LOGIC | 09 | Extract table, figure, integrity and numerical reconciliation logic. Do not migrate old final numbers. |
| `21e_freeze_final_empirical_release.ipynb` | MIGRATE_LOGIC | 09 | Extract table, figure, integrity and numerical reconciliation logic. Do not migrate old final numbers. |

## Migration rules

1. Historical notebooks are never copied wholesale.
2. Reusable logic moves into `src/weather_polymarket/`.
3. Canonical notebooks call reusable modules.
4. Historical output cells and old headline values are not migrated.
5. Current source provenance and integrity checks are retained.
6. Duplicate notebook generations are consolidated.
7. GP code enters the clean pipeline only after Notebook 04 audit.
8. August results must not influence development choices.

## Classification completion

All 72 notebooks received an explicit migration decision.

