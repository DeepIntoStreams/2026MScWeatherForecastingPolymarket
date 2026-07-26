# Notebook 00–01 Archive Source Audit

Archive branch: `archive/17j-plus-18n-18y-20260726`

Approved historical notebooks inspected: **23**

No historical notebook or output has been copied into the clean branch.

## Approved notebook sources

| Historical source | Destination | Functions/classes found |
|---|---|---|
| `notebooks/17j_hko_polymarket_upper_tail_metadata_and_resolution_audit.ipynb` | 01 | as_list_from_field; classify_rule_family; clob_price_history; decide; extract_events_from_response; extract_yes_token_id; fetch_event_by_slug; fetch_events_keyset; fetch_events_offset; field_mentions_k; find_repo_root; flatten_text; gamma_get; get_historical_file; list_historical_versions; maybe_json; normalise_label; numeric_close; parse_event_date; parse_threshold_from_text; read_hko_clmmaxt; safe_get; strip_market_context; terminal_yes_from_outcome_prices; to_float |
| `notebooks/17k_hko_upper_tail_certification_dossier.ipynb` | 01 | approx_equal; boundary_metadata_certifies; coerce_bool; extract_rule_text; extract_version_times; fetch_gamma_market; field_has_infinity; first_present; get_historical_file; get_latest_hko_daily_max; get_market_id; infer_market_date; is_strict_hko_family_text; list_historical_versions; load_17j_tail_rows; main; maybe_float; normalise_columns; parse_hko_daily_max_csv; parse_threshold_from_text; pick; reconstruct_first_available_hko_value; repo_root; request_json; request_text; safe_filename; written_confirmation_certifies |
| `notebooks/17l_hko_contract_rule_text_certification.ipynb` | 01 | build_evidence_excerpt; certify_row; contains_any; counts_md; discover_hk_events; extract_markets_from_event; extract_tail_threshold; find_first_patterns; find_repo_root; gamma_get; looks_upper_tail; normalise_events_response; normalise_text; parse_event_date_from_slug_or_text; rec; reply_confirms_endpoint_convention; safe_slug; save_json; sha256_text; textify; try_get_json; try_get_text |
| `notebooks/18a_hko_certified_upper_tail_price_panel.ipynb` | 01 | No named functions |
| `notebooks/18b_hko_certified_upper_tail_outcome_and_decision_panel.ipynb` | 01 | find_repo_root |
| `notebooks/18c_hko_daily_extract_outcome_reconciliation.ipynb` | 01 | _find_col; _normalise_text; candidate_daily_extract_urls; extract_daily_max_from_table; fetch_daily_extract_month; find_repo_root; flatten_columns; looks_like_day_series; parse_hko_clmmaxt |
| `notebooks/18d_hko_daily_extract_source_discovery.ipynb` | 01 | choose_best_outcome; fetch_url; find_col; find_repo_root; identify_year_month_day_value_columns; normalise_text; parse_daily_extract_tables_from_html; parse_date_value_csv; safe_filename |
| `notebooks/18e_hko_historical_market_hko_alignment_to_20260531.ipynb` | 01 | No named functions |
| `notebooks/18f_hko_metob_polymarket_historical_panel_to_20260531.ipynb` | 01 | build_decision_panel; build_hko_targets; build_price_panel; build_report; build_validation_panels; date_range; extract_threshold_from_label; fetch_gamma_event_by_slug; fetch_polymarket_page; fetch_price_history; fetch_text; flatten_columns; get_yes_token_id; is_lower_tail_label; is_upper_tail_label; main; market_label_text; normalise_text; parse_event_markets; parse_hko_clmmaxt_fallback; parse_hko_tables_from_html; parse_jsonish; parse_numeric_value; parse_price_history; parse_token_ids; parse_web_outcomes; safe_name; score_decisions; slug_for_date; sweep_polymarket_events; write_json |
| `notebooks/18i_hko_empirical_baseline_reporting.ipynb` | 01 | No named functions |
| `notebooks/18j_gamma_metadata_settlement_family_audit.ipynb` | 01 | No named functions |
| `notebooks/18j_v2_fix_contract_event_parsing.ipynb` | 01 | No named functions |
| `notebooks/18j_v2_fix_contract_event_parsing_COMPLETE.ipynb` | 01 | No named functions |
| `notebooks/18k_full_hko_contract_event_target_panel.ipynb` | 01 | No named functions |
| `notebooks/18k_full_hko_contract_event_target_panel_FIX.ipynb` | 01 | No named functions |
| `notebooks/18k_full_hko_contract_event_target_panel_FIX2.ipynb` | 01 | No named functions |
| `notebooks/18l_full_hko_contract_event_clob_price_recovery.ipynb` | 01 | No named functions |
| `notebooks/18n_june_2026_contract_event_audit.ipynb` | 01 | candidate_slugs; combined_event_text; discover_event; extract_tokens; fetch_event_by_slug; label_payload; ordinal; parse_contract_label; parse_jsonish_list; request_json; safe_bool; safe_int; scalar_text; sha256_file; source_evidence; title_date_match; validate_book |
| `notebooks/18o_june_2026_hko_realised_outcomes.ipynb` | 01 | clean_numeric_text; fetch_and_archive; find_column; find_index; flatten_column; normalise_json_field_name; parse_daily_extract_html; parse_hko_csv; parse_temperature; realised_yes; records_from_hko_json; sha256_bytes; sha256_file; visit |
| `notebooks/18sA_canonical_source_adapters.ipynb` | 00 | _self_test_mapped_common_keyset; block; candidates; canonical_market; canonical_target; canonical_weather; cutoff; etype; event_type_from_text; identifier_candidates; ids; load_valid; mapped_common_keyset; member; norm; numeric_alias_series; parse_datetime_aliases; pbool; pick; read; row_validator; sha; target_validator; temperature_label; temperature_reference_series; v |
| `notebooks/18sB_expanded_sample_freeze.ipynb` | 00 | add_check; decision_cutoff_hkt; parse_bool; sha256_file |
| `notebooks/18uA_chronological_partition_and_folds.ipynb` | 00 | add_check; evaluation_block; parse_bool; sha256_file; verify_manifest |
| `notebooks/18uB_model_specific_freeze_support.ipynb` | 00 | add_check; date_balanced_weights; json_default; parse_bool; scope_rule; sha256_file; verify_manifest |

## Repeated function and class names

- `find_repo_root`: 5 historical notebooks
- `sha256_file`: 5 historical notebooks
- `normalise_text`: 3 historical notebooks
- `parse_bool`: 3 historical notebooks
- `add_check`: 3 historical notebooks
- `gamma_get`: 2 historical notebooks
- `parse_threshold_from_text`: 2 historical notebooks
- `fetch_event_by_slug`: 2 historical notebooks
- `list_historical_versions`: 2 historical notebooks
- `get_historical_file`: 2 historical notebooks
- `request_json`: 2 historical notebooks
- `pick`: 2 historical notebooks
- `safe_filename`: 2 historical notebooks
- `main`: 2 historical notebooks
- `flatten_columns`: 2 historical notebooks
- `verify_manifest`: 2 historical notebooks

## Frequently imported packages

- `pathlib`: 21
- `pandas`: 15
- `IPython`: 13
- `json`: 12
- `__future__`: 11
- `datetime`: 10
- `numpy`: 10
- `re`: 9
- `typing`: 9
- `requests`: 8
- `time`: 8
- `hashlib`: 7
- `sys`: 7
- `io`: 6
- `os`: 6
- `platform`: 6
- `math`: 5
- `urllib`: 3
- `dataclasses`: 3
- `subprocess`: 2
- `zoneinfo`: 2
- `html`: 1
- `runpy`: 1
- `calendar`: 1
- `csv`: 1

## Candidate archived source and data files

| Path | Size in bytes |
|---|---:|
| `archive_manifest/README.md` | 478 |
| `archive_manifest/full_file_inventory.txt` | 1105565 |
| `archive_manifest/notebook_inventory.txt` | 3856 |
| `archive_manifest/pre_archive_status.txt` | 3197 |
| `archive_manifest/tracked_files_before_archive.txt` | 22402 |
| `archive_manifest/untracked_files_before_archive.txt` | 6846 |
| `data/manual/18w_outcome_free_contract_definitions/18w_outcome_free_contract_definition_metadata.json` | 1274 |
| `data/manual/18w_outcome_free_contract_definitions/18w_outcome_free_contract_definition_panel.csv` | 526902 |
| `data/processed/17l_hko_contract_rule_text_certification_decision.csv` | 14365718 |
| `data/processed/17l_hko_highest_upper_tail_formally_certified_subset.csv` | 717559 |
| `data/processed/17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv` | 446185 |
| `data/processed/18d_hko_current_year_maxt_all_parsed_debug.csv` | 55666 |
| `data/processed/18d_hko_current_year_maxt_target_matches_debug.csv` | 168 |
| `data/processed/18d_hko_daily_extract_html_all_parsed_debug.csv` | 74 |
| `data/processed/18d_hko_daily_extract_html_target_matches_debug.csv` | 202 |
| `data/processed/18f_hko_daily_extract_targets_20260301_20260531.csv` | 15380 |
| `data/processed/18f_hko_polymarket_floor_validation_panel_20260313_20260531.csv` | 2948815 |
| `data/processed/18f_hko_upper_tail_threshold_contracts_20260313_20260531.csv` | 274153 |
| `data/processed/18f_polymarket_event_sweep_20260313_20260531.csv` | 17905 |
| `data/processed/18h_hko_upper_tail_market_only_score_summary_20260313_20260531.csv` | 1131 |
| `data/processed/18h_hko_upper_tail_narrow_window_price_observations_20260313_20260531.csv` | 1211298 |
| `data/processed/18h_hko_upper_tail_no_lookahead_decision_panel_20260313_20260531.csv` | 1075875 |
| `data/processed/18h_hko_upper_tail_scoring_ready_market_panel_20260313_20260531.csv` | 1087050 |
| `data/processed/18i_hko_decision_rule_operational_summary.csv` | 601 |
| `data/processed/18i_hko_empirical_coverage_summary.csv` | 784 |
| `data/processed/18i_hko_empirical_integrity_checks.csv` | 426 |
| `data/processed/18i_hko_main_market_only_score_summary.csv` | 954 |
| `data/processed/18i_hko_main_scoring_panel_formally_certified.csv` | 1049730 |
| `data/processed/18i_hko_monthly_contract_summary.csv` | 445 |
| `data/processed/18k_full_hko_contract_event_target_panel.csv` | 44150657 |
| `data/processed/18k_hko_contract_event_date_resolution_summary.csv` | 5171 |
| `data/processed/18k_hko_contract_event_integrity_checks.csv` | 493 |
| `data/processed/18k_hko_contract_event_target_issues.csv` | 1162 |
| `data/processed/18k_hko_contract_event_type_target_summary.csv` | 196 |
| `data/processed/18k_hko_realised_outcomes_used.csv` | 31537 |
| `data/processed/18m_binary_market_score_by_decision_rule_and_event_type.csv` | 1557 |
| `data/processed/18m_event_book_categorical_score_by_decision_rule.csv` | 1142 |
| `data/processed/18m_event_book_categorical_score_panel.csv` | 54906 |
| `data/processed/19a_hko_ecmwf_contract_event_probability_panel.csv.gz` | 16733333 |
| `data/processed/19a_hko_ecmwf_forecast_integrity_checks.csv` | 614 |
| `data/processed/19a_hko_ecmwf_forecast_issues.csv` | 16290 |
| `data/processed/19a_hko_ecmwf_probability_score_summary.csv` | 3767 |
| `data/processed/19a_hko_ecmwf_single_run_daily_max_forecasts.csv` | 79213 |
| `data/processed/19a_hko_ecmwf_single_run_fetch_inventory.csv` | 143317 |
| `data/processed/19a_hko_ecmwf_single_run_hourly_forecasts.csv` | 5728286 |
| `data/processed/19a_hko_ecmwf_single_run_request_plan.csv` | 34332 |
| `data/processed/19b_common_support_binary_score_by_event_type.csv` | 3888 |
| `data/processed/19c_binary_score_by_event_type.csv` | 6882 |
| `data/processed/20a_output_manifest.csv` | 1520 |
| `data/processed/20b_cv_fold_summary.csv` | 731 |
| `data/processed/20b_split_manifest.json` | 394 |
| `data/processed/20c_selected_model_manifest.json` | 1093 |
| `data/processed/20d_calibration_coherence_manifest.json` | 656 |
| `data/processed/20d_event_book_metrics.csv` | 34078 |
| `data/processed/20d_event_book_probability_panel.csv` | 867497 |
| `data/processed/20d_event_book_score_summary.csv` | 658 |
| `data/processed/20e_locked_holdout_event_book_metrics.csv` | 29811 |
| `data/processed/20e_locked_holdout_event_book_probability_panel.csv` | 686209 |
| `data/processed/20e_locked_holdout_event_book_score_summary.csv` | 740 |
| `data/processed/20e_locked_holdout_manifest.json` | 1040 |
| `data/processed/21a_simple_edge_manifest.json` | 1359 |
| `data/processed/21b_full_event_book_allocation_panel.csv` | 2757001 |
| `data/processed/21b_full_event_book_daily_pnl.csv` | 158402 |
| `data/processed/21b_full_event_book_integrity_checks.csv` | 1011 |
| `data/processed/21b_full_event_book_inventory.csv` | 15674 |
| `data/processed/21b_full_event_book_issues.csv` | 20 |
| `data/processed/21b_full_event_book_manifest.json` | 1221 |
| `data/processed/21b_full_event_book_pooled_diagnostic.csv` | 4922 |
| `data/processed/21b_full_event_book_primary_standalone_summary.csv` | 6958 |
| `data/processed/21b_full_event_book_probability_panel.csv` | 554480 |
| `data/processed/21b_full_event_book_standalone_summary.csv` | 20916 |
| `data/processed/21b_full_event_book_strategy_results.csv` | 297444 |
| `data/processed/21c_cost_staleness_manifest.json` | 1636 |
| `data/processed/21d_manifest.json` | 1465 |
| `data/processed/baseline_freezes/18i_hko_empirical_baseline_v1_manifest.csv` | 3547 |
| `data/releases/hko_empirical_release_v1/21e_release_file_index.csv` | 31865 |
| `data/releases/hko_empirical_release_v1/21e_release_integrity_checks.csv` | 3956 |
| `data/releases/hko_empirical_release_v1/21e_release_integrity_summary.csv` | 746 |
| `data/releases/hko_empirical_release_v1/21e_release_issues.csv` | 20 |
| `data/releases/hko_empirical_release_v1/21e_release_manifest.json` | 1120 |
| `docs/ai_weather_model_output_availability_audit.md` | 16859 |
| `docs/research_outputs/17k_hko_upper_tail_certification_report.md` | 1074 |
| `docs/research_outputs/17l_hko_contract_rule_text_certification_report.md` | 1993 |
| `docs/research_outputs/18a_hko_certified_upper_tail_price_panel_report.md` | 997 |
| `docs/research_outputs/18c_hko_daily_extract_outcome_reconciliation_report.md` | 1630 |
| `docs/research_outputs/18d_hko_daily_extract_source_discovery_report.md` | 9647 |
| `docs/research_outputs/18e0_hko_historical_seed_discovery_report.md` | 6268 |
| `docs/research_outputs/18e_hko_historical_alignment_report.md` | 1564 |
| `docs/research_outputs/18f_hko_metob_polymarket_historical_panel_report.md` | 9233 |
| `docs/research_outputs/18i_hko_empirical_baseline_report.md` | 8979 |
| `docs/research_outputs/18i_hko_empirical_baseline_v1_freeze_report.md` | 2593 |
| `docs/research_outputs/18j_gamma_metadata_settlement_family_audit_report.md` | 25604 |
| `docs/research_outputs/18j_v2_contract_event_parsing_fix_report.md` | 26286 |
| `docs/research_outputs/18k_full_hko_contract_event_target_panel_report.md` | 18279 |
| `docs/research_outputs/18l_full_hko_contract_event_clob_price_recovery_report.md` | 39071 |
| `docs/research_outputs/18m_full_hko_market_only_baseline_report.md` | 12260 |
| `docs/research_outputs/19a_hko_ecmwf_single_run_forecast_ingestion_report.md` | 61621 |
| `docs/research_outputs/21b_full_event_book_trading_report.md` | 62623 |
| `docs/resolution_rules_audit.md` | 7889 |
| `figures/20a_supervised_feature_matrix/20a_target_prevalence_by_event_type.png` | 70650 |
| `figures/20d_calibration_coherence/20d_event_book_categorical_log.png` | 90286 |
| `figures/21a_simple_edge_trading/21a_cumulative_net_pnl_event_day_open.png` | 187937 |
| `figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_12h_prior.png` | 171117 |
| `figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_24h_prior.png` | 169580 |
| `figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_6h_prior.png` | 163254 |
| `figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_event_day_open.png` | 176457 |
| `figures/21b_full_event_book_trading/21b_proportional_positive_edge_standalone_total_pnl.png` | 233010 |
| `figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_12h_prior.png` | 143285 |
| `figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_24h_prior.png` | 162619 |
| `figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_6h_prior.png` | 155304 |
| `figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_event_day_open.png` | 152233 |
| `figures/21b_full_event_book_trading/21b_single_best_edge_standalone_total_pnl.png` | 226479 |
| `figures/reports/18i_hko_market_brier_by_decision_rule.png` | 69655 |
| `figures/reports/18i_hko_market_log_score_by_decision_rule.png` | 71836 |
| `figures/reports/18i_hko_market_probability_histogram.png` | 42155 |
| `figures/reports/18i_hko_monthly_coverage.png` | 46655 |
| `figures/reports/18i_hko_price_staleness_by_decision_rule.png` | 70666 |
| `reports/18n_june_2026_contract_event_audit/18n_june_2026_contract_event_audit_report.md` | 3006 |
| `reports/18o_june_2026_hko_realised_outcomes/18o_june_2026_hko_realised_outcome_report.md` | 3127 |
| `reports/18s_expanded_march_june_canonical_sample/18s_expanded_march_june_canonical_sample_report.md` | 2140 |
| `reports/18tA_hko_publication_availability/18tA_hko_publication_availability_report.md` | 944 |
| `reports/18uA_chronological_partition_and_folds/18uA_chronological_partition_and_folds_report.md` | 957 |
| `reports/18wA_contract_probability_mapping/18wA_contract_probability_mapping_report.md` | 644 |
| `reports/18yB_thesis_output_freeze/figures/18yB_sample_support_flow.png` | 58582 |
| `scripts/17j_hko_polymarket_upper_tail_metadata_and_resolution_audit.py` | 43209 |
| `scripts/17k_hko_upper_tail_certification_dossier.py` | 32479 |
| `scripts/17l_hko_contract_rule_text_certification.py` | 32517 |
| `scripts/18a_hko_certified_upper_tail_price_panel.py` | 21589 |
| `scripts/18b_hko_certified_upper_tail_outcome_and_decision_panel.py` | 19812 |
| `scripts/18c_hko_daily_extract_outcome_reconciliation.py` | 20282 |
| `scripts/18d_hko_daily_extract_source_discovery.py` | 24414 |
| `scripts/18e_hko_historical_market_hko_alignment_to_20260531.py` | 38339 |
| `scripts/18f_hko_metob_polymarket_historical_panel_to_20260531.py` | 41363 |
| `scripts/18i_hko_empirical_baseline_reporting.py` | 21661 |
| `scripts/18j_gamma_metadata_settlement_family_audit.py` | 28232 |
| `scripts/18j_v2_fix_contract_event_parsing.py` | 21385 |
| `scripts/18j_v2_fix_contract_event_parsing_COMPLETE.py` | 22530 |
| `scripts/18k_full_hko_contract_event_target_panel.py` | 21760 |
| `scripts/18k_full_hko_contract_event_target_panel_FIX.py` | 22086 |
| `scripts/18k_full_hko_contract_event_target_panel_FIX2.py` | 22681 |
| `scripts/18l_full_hko_contract_event_clob_price_recovery.py` | 34665 |
| `scripts/18m_full_hko_market_only_baseline_diagnostics.py` | 24777 |
| `scripts/19a_hko_open_meteo_ecmwf_single_run_forecast_ingestion.py` | 37620 |
| `scripts/21b_full_event_book_trading.py` | 29390 |

## Migration decision

Notebook 00 receives only:

- configuration declarations;
- run-manifest logic;
- source-registry logic;
- chronological design declarations.

Notebook 01 receives only:

- official HKO source handling;
- final event-boundary parsing;
- one-decimal settlement classification;
- exactly-one-winner integrity checks.

Old output cells, sample counts, figures and headline results are not migrated.

