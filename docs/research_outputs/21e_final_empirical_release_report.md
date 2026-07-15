# Final Hong Kong empirical release freeze

## Release identity

- release name: `hko_empirical_release_v1`
- branch: `edward-17j-hko-upper-tail-audit`
- commit: `63bf40d3e6911773fad9afbcf7ac089cc7282a55`
- commit subject: `Add dissertation-ready empirical consolidation`
- generated at UTC: `2026-07-15T06:05:10.907958+00:00`

## Scope

This release freezes the completed Hong Kong empirical pipeline from market settlement and price recovery through forecast comparison, leakage-free post-processing, locked-holdout evaluation, trading simulation, robustness analysis, and dissertation-ready consolidation.

The release does not claim that historical executable spreads, fees, slippage, market impact, liquidity constraints, partial fills, or capital limits were fully reconstructed. Trading outputs remain hypothetical reduced-form simulations.

## Consolidated empirical headline

| block                              | metric                                        |     value | model_or_source                                   | decision_rule   | sample                          |
|:-----------------------------------|:----------------------------------------------|----------:|:--------------------------------------------------|:----------------|:--------------------------------|
| Market baseline                    | Best binary Brier                             | 0.0651585 | Polymarket                                        | 12h_prior       | full available HKO market panel |
| Market baseline                    | Best binary log score                         | 0.207559  | Polymarket                                        | event_day_open  | full available HKO market panel |
| Common-support forecast comparison | Largest market Brier advantage over raw ECMWF | 0.0176093 | Polymarket versus raw ECMWF proxy                 | 12h_prior       | exact common support            |
| Locked holdout forecasting         | Best holdout Brier                            | 0.0459589 | ecmwf_bias_adaptive_sigma                         | event_day_open  | 22–31 May 2026 locked holdout   |
| Frictionless trading               | Best primary standalone PnL                   | 2.4515    | 21a: ecmwf_bias_fixed_sigma, binary_contract_edge | 24h_prior       | 22–31 May 2026 locked holdout   |
| Robustness trading                 | Best cost-and-staleness adjusted PnL          | 2.201     | 21a: ecmwf_bias_fixed_sigma, binary_contract_edge | 12h_prior       | 22–31 May 2026 locked holdout   |

## Integrity status

| step   | integrity_file                                          |   checks_passed |   checks_total | all_checks_passed   | file_present   |
|:-------|:--------------------------------------------------------|----------------:|---------------:|:--------------------|:---------------|
| 18m    | data/processed/18m_market_only_integrity_checks.csv     |               9 |              9 | True                | True           |
| 19b    | data/processed/19b_common_support_integrity_checks.csv  |              11 |             11 | True                | True           |
| 19c    | data/processed/19c_integrity_checks.csv                 |              14 |             14 | True                | True           |
| 20b    | data/processed/20b_integrity_checks.csv                 |              14 |             14 | True                | True           |
| 20d    | data/processed/20d_integrity_checks.csv                 |              13 |             13 | True                | True           |
| 20e    | data/processed/20e_locked_holdout_integrity_checks.csv  |              16 |             16 | True                | True           |
| 21a    | data/processed/21a_simple_edge_integrity_checks.csv     |              19 |             19 | True                | True           |
| 21b    | data/processed/21b_full_event_book_integrity_checks.csv |              19 |             19 | True                | True           |
| 21c    | data/processed/21c_integrity_checks.csv                 |              30 |             30 | True                | True           |
| 21d    | data/processed/21d_integrity_checks.csv                 |              10 |             10 | True                | True           |

## Release completeness

- indexed artefacts: 233
- indexed bytes: 463132484
- missing core artefacts: []
- resolved historical core artefacts: {'20a_supervised_feature_matrix': 'data/processed/20a_supervised_feature_matrix.csv'}
- all recorded integrity checks pass: True
- repository clean apart from permitted untracked local files: True

## Reproducibility statement

Every indexed artefact is recorded by repository-relative path, byte size, and SHA-256 digest. The release can therefore be audited against the exact Git commit and regenerated empirical outputs.

## Indexed artefacts

| relative_path                                                                                       |   size_bytes | sha256                                                           | suffix   |
|:----------------------------------------------------------------------------------------------------|-------------:|:-----------------------------------------------------------------|:---------|
| data/processed/18j_v2_contract_date_summary.csv                                                     |         1539 | 556f11f46e24ec7f7830bea406b282c7d258b9e23dd3ae82e7d2b8b6c183fe6e | .csv     |
| data/processed/18j_v2_contract_event_type_summary.csv                                               |          402 | 96dec635653cda0c5586a99e4df7602fe74cff4aa0269b59062c10b887081c4b | .csv     |
| data/processed/18j_v2_excluded_or_ambiguous_hk_contracts.csv                                        |       907986 | e9e2f387797e706514dde38bb8ca8db65d428e18b8773d6950aebdaabffefadb | .csv     |
| data/processed/18j_v2_full_hko_contract_event_universe.csv                                          |     43814237 | bf258b6d419873c602f117840ecbddd179e8b1c8c2f1acc96241e452e807ecfa | .csv     |
| data/processed/18j_v2_gamma_metadata_settlement_family_audit_fixed.csv                              |     44721244 | 3879111d01234cab838ad5c1acabca9be82d258d66feb12461d93281a0be88d5 | .csv     |
| data/processed/18j_v2_march13_settlement_family_audit.csv                                           |       432652 | adccaf79b4646b009af21b1224c6a8bde2921f2eafe78878dd9b94cde5e5ac41 | .csv     |
| data/processed/18j_v2_parsing_validation_checks.csv                                                 |          448 | 009175a29303f22d2555cfbd6d39121226b2e6284b40554cba4729b3519b732c | .csv     |
| data/processed/18j_v2_settlement_family_summary.csv                                                 |          233 | 64084879331c5d3c4b1d0ee8eee273b7666149690f0848b3e482397089446f07 | .csv     |
| data/processed/18k_full_hko_contract_event_target_panel.csv                                         |     44150657 | 3406749f8a8633798aa2365aa92fafd3f8e8fbec47dd83513aeff77fb60d69b1 | .csv     |
| data/processed/18k_hko_contract_event_date_resolution_summary.csv                                   |         5171 | 4a8e9aed6fbdc41cdb4d9f3d32c590b22ae9d2d08380f3f3005ec068ce8aae30 | .csv     |
| data/processed/18k_hko_contract_event_integrity_checks.csv                                          |          493 | fcd193dc8660f4c81472d7d4183883fa8bee3404f75969e417bd8e082cbbee7a | .csv     |
| data/processed/18k_hko_contract_event_target_issues.csv                                             |         1162 | 52fdbf0ec660f076433f237b87b83c61ab89a9ff45d245451b2b5a4ee34a4eef | .csv     |
| data/processed/18k_hko_contract_event_type_target_summary.csv                                       |          196 | c9d60bc940daefa1674491912c0b93ae2d3c6a9f268860419335567c8ac643c9 | .csv     |
| data/processed/18k_hko_realised_outcomes_used.csv                                                   |        31537 | 32cd099699cb6aeb415f5dd382f2f424f043d1532a0c7e5e73bd281a9d5bf7b2 | .csv     |
| data/processed/18l_full_hko_contract_event_market_scoring_panel.csv.gz                              |     15099976 | dbcc4a31348fcedc82407165ae6d19f9d34eb521a4e07ec20db559eb85d34fea | .csv.gz  |
| data/processed/18l_full_hko_contract_event_no_lookahead_decision_panel.csv.gz                       |     15040053 | eb16d9b4f63d47fbab51a03ca1a772025da18b8f3c9ea286a87424e88c13fd17 | .csv.gz  |
| data/processed/18m_binary_market_score_by_decision_rule.csv                                         |          766 | b48240d5dffac3fdd2ef1bf8ab3d0dc4a8d6a862a2bc97914d2ef1f4b8f81d87 | .csv     |
| data/processed/18m_binary_market_score_by_decision_rule_and_event_type.csv                          |         1557 | fe04d658c870e819101fc73c0b39f933495e81003ad2b37636507ed59342dcaf | .csv     |
| data/processed/18m_event_book_categorical_score_by_decision_rule.csv                                |         1142 | a3a88cb270771eb8d9081b305f7653bdbed86e3bb8c4ca4b30ceff535c1d15b5 | .csv     |
| data/processed/18m_event_book_categorical_score_panel.csv                                           |        54906 | 2534f027165daa58d18608263e305a70243e0e4cc6a3aa734f00ed1e4b287f9a | .csv     |
| data/processed/18m_market_only_decision_rule_rankings.csv                                           |         1622 | 5f348a677df6534f5443a316336ff5b27688a4bb621af7d0ca612f840bc4996d | .csv     |
| data/processed/18m_market_only_integrity_checks.csv                                                 |          476 | ce3da5a696e1a74f6a42f21c0e3a2b14bdcff5f1b5364fed017871b078402654 | .csv     |
| data/processed/18m_supervisor_market_only_key_table.csv                                             |         1237 | d23af1999555dc2cdf9657baf2e413abf6416243d46bdaadbc3f5f302534b144 | .csv     |
| data/processed/19a_hko_ecmwf_contract_event_probability_panel.csv                                   |    177840485 | 4a228d56f949db7acfaf9b67996c5d3803e05e28d7015da8bb1d2b47e71ed56b | .csv     |
| data/processed/19a_hko_ecmwf_contract_event_probability_panel.csv.gz                                |     16733333 | c54b3fc87d52d98257dc070be272ae091c4f1fe21412a29391adcb8068534329 | .csv.gz  |
| data/processed/19a_hko_ecmwf_forecast_integrity_checks.csv                                          |          614 | f49d44f29548e96b4b7994da7616950d000b16dd8cc50f927d86d1e120360397 | .csv     |
| data/processed/19a_hko_ecmwf_forecast_issues.csv                                                    |        16290 | f76a401a4e7496f30e10c23f90c147f162fce32c0a5d1ea8eb639e78b2d18ddb | .csv     |
| data/processed/19a_hko_ecmwf_probability_score_summary.csv                                          |         3767 | 4247d356e2de834768bbd219fba7ca64f7deff81e2d865f1055c2e5278b8b391 | .csv     |
| data/processed/19a_hko_ecmwf_single_run_daily_max_forecasts.csv                                     |        79213 | 8b7c29a9fe44ce49f052463a38f763865554262212ca3781f965c3a24735fac6 | .csv     |
| data/processed/19a_hko_ecmwf_single_run_fetch_inventory.csv                                         |       143317 | ecf6aeae4f5e02399010c481a9b8f9ef1765fa774b7a128fdf70e4afd1184c97 | .csv     |
| data/processed/19a_hko_ecmwf_single_run_hourly_forecasts.csv                                        |      5728286 | daee56b048ba029e06d81d32da6385b7e24bb7341030a30523475ba1e4e24063 | .csv     |
| data/processed/19a_hko_ecmwf_single_run_request_plan.csv                                            |        34332 | 12baa6eed66ea850a5ec57472586a5885167ab902a2f37b7b3e69a9664788b69 | .csv     |
| data/processed/19b_common_support_binary_score_by_event_type.csv                                    |         3888 | fb778f67ffae02b9023316f16575585800f7dadebbde3fad3ad30bf7ae672bf4 | .csv     |
| data/processed/19b_common_support_binary_score_summary.csv                                          |         1475 | abcb769c4436d2d9a83fa58f77704c4f1c5fde99eb77fe2156598dcf01d52c34 | .csv     |
| data/processed/19b_common_support_categorical_book_score_panel.csv                                  |        69497 | ee197be66fa8d9695d5e67dc9e7cfcc1829ca80422aad62d8560eb00857563b0 | .csv     |
| data/processed/19b_common_support_categorical_score_summary.csv                                     |         1596 | 8be96d76c08596a88247e05c214d8ad2669f3bb12bbe0249171c9534647fb416 | .csv     |
| data/processed/19b_common_support_decision_rule_rankings.csv                                        |         1804 | 6fc9613b9cf72e9b91c3d879b3a2fb46a186f9a7b9806d7494fe0a73003db566 | .csv     |
| data/processed/19b_common_support_integrity_checks.csv                                              |          490 | 56bd9c73aaf56c266d6f12cda191ea59a67ac0d18c28494bf0a20672f5fb9de1 | .csv     |
| data/processed/19b_common_support_issues.csv                                                        |          482 | ed04d73676346cbd67bd79e26e8f6cdfa83620a5ae5c91f3d577e438a5a2fee4 | .csv     |
| data/processed/19b_common_support_market_vs_ecmwf_panel.csv                                         |      2407794 | c00f06bd3f32e3e73c8ee616340e69e70c2e2f5930cbbd994039de7515eefb86 | .csv     |
| data/processed/19b_common_support_score_differences_by_date.csv                                     |        16755 | 523df02867079f7c19c15b7ad04454942dfb9db8103c3e8e346c45c55d3a13c3 | .csv     |
| data/processed/19c_binary_score_by_event_type.csv                                                   |         6882 | 8ab8d35ea0ba711a23bb2811f3bac02450db8b10b40319bb2534d0ab48659f55 | .csv     |
| data/processed/19c_binary_score_summary.csv                                                         |         2961 | bf7ee0758db1b523cc5002b307847bcde2dfa6eebe909ebc56fdbb3354e7e6fc | .csv     |
| data/processed/19c_categorical_book_score_panel.csv                                                 |        88090 | e8c6a6bf345cd8759e2f1240031668048a32da759bbacf025a2d5d6910533c8c | .csv     |
| data/processed/19c_categorical_score_summary.csv                                                    |         2588 | 823755fa91a8296d980eaf83c8e549227c0a0bf557ece6fc8b3057ab3c9a39b2 | .csv     |
| data/processed/19c_common_support_calibrated_probability_panel.csv                                  |      3157153 | 2bddd2e8a3e71a7ce30be6d74acff52b485365a0a96ef3ee01f6f489e5eca8c3 | .csv     |
| data/processed/19c_date_level_score_panel.csv                                                       |        33739 | 81f8c19ae5b1f302094fa7237848dbcace1ae1f62f35524c695fc8010ac24dea | .csv     |
| data/processed/19c_decision_rule_rankings.csv                                                       |         4844 | 6e47c38f1832e5ee411ebe5630ad27eda1446fd8ed3a7f97ef522abaf8d272bd | .csv     |
| data/processed/19c_expanding_bias_scale_parameter_path.csv                                          |        62451 | 370006826940c5e15e800b6d1d345c78f06f5fbe4ac8eff653a88741c45c5a7f | .csv     |
| data/processed/19c_gaussian_calibration_summary.csv                                                 |         1043 | bfca4e0e0e304687a24b42bc618c42a8350475ca3ed649a14269c72b292c4036 | .csv     |
| data/processed/19c_integrity_checks.csv                                                             |          826 | 8b0f0ed9357a096bbbc993a2715d318a14910707b02c2e2e5b21d7f1e16159c4 | .csv     |
| data/processed/19c_issues.csv                                                                       |          972 | f5a0b047d2d36221a593982eaa7f41d65c23a5cac2b0851e0d5127827dfbbb7a | .csv     |
| data/processed/19c_paired_date_level_comparisons.csv                                                |         3760 | 10a92108af03609e5f139aeac38b1e859aee0c44cbc783224776b936d032011c | .csv     |
| data/processed/19c_temperature_error_summary.csv                                                    |         1024 | 591b4073347cf353b7fe8959fd452578658e397b08e7e9962daebe22274315cd | .csv     |
| data/processed/20a_date_group_summary.csv                                                           |         2615 | b2332c30559f3707105ca3ec63dafe6291ad52f05bbc299ef1cde1c149d20bf7 | .csv     |
| data/processed/20a_feature_dictionary.csv                                                           |         9808 | 9bef7d7a5c942c65129381e619af1fb69eaa3dd836233d2a9f6de6834f0d8d31 | .csv     |
| data/processed/20a_feature_missingness_summary.csv                                                  |         8324 | b643091a071a6429febf45143d1feb552c6c25b114e1e6d48045309c1abc1151 | .csv     |
| data/processed/20a_integrity_checks.csv                                                             |          956 | b849dfd215e226fb05432dcb7f2b44b378521dcf5b407f255e37a5058450408c | .csv     |
| data/processed/20a_issues.csv                                                                       |         1465 | 6dde3b0c82a490065480287f0b61238cd1c180ef3332ff9e184c31503c7d6724 | .csv     |
| data/processed/20a_output_manifest.csv                                                              |         1520 | 8a1519f86f9c36355b31c77eb47b1184483a3a483c6479c5b1237bc7c6cbaa39 | .csv     |
| data/processed/20a_supervised_feature_matrix.csv                                                    |      2684448 | 7ca1fc78221d38209f2a4a17664f2803fb260d4cf2e2ea835f6f33fd13938849 | .csv     |
| data/processed/20b_cv_date_assignments.csv                                                          |        10611 | 0604a902de8a865d75c77b9e38d8f5b9806e68267004bcace8a51fa7ea67d9ba | .csv     |
| data/processed/20b_cv_fold_summary.csv                                                              |          731 | b8cd4bc0feaac1c87e2fba9ab64b34c5ba619ad0742099d36cab983661d83dd9 | .csv     |
| data/processed/20b_cv_row_assignment_panel.csv                                                      |      8683232 | 3f8f785245adce709bffe9417fcca6f4940bcffea9614831406d93a4bce60f88 | .csv     |
| data/processed/20b_date_partition_assignments.csv                                                   |         3047 | c59152a81dc231d05378cbc42edc598731edf2530ec8f09dc56201de72fa7335 | .csv     |
| data/processed/20b_final_partition_summary.csv                                                      |          209 | af55a820dd49eade1d341fb015a3338abf1fbe24f49ff5ac157402fb649f3657 | .csv     |
| data/processed/20b_integrity_checks.csv                                                             |          774 | aa27ff8d352d5f9f7f4cc3d75cb845d4823fe2362e99b9ac37bfbd993d2266d9 | .csv     |
| data/processed/20b_issues.csv                                                                       |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/20b_supervised_row_partition_assignments.csv                                         |      2669765 | 70e83df065af1bc175edcc1bb781e3098e2c3e880bf2b5ad6fb69129b6680881 | .csv     |
| data/processed/20c_catboost_fit_inventory.csv                                                       |         3391 | 671277c5ff60330239964f760bd6b942a3690468798667ac8eb6861382be27d1 | .csv     |
| data/processed/20c_catboost_oof_probability_panel.csv                                               |      2994295 | 7d17ad68cf863c208e54f23ef725e3df31871c8d3db3d2416d88342f8df56ee0 | .csv     |
| data/processed/20c_integrity_checks.csv                                                             |          866 | 9e4b4d663d1cf12b7b5e06d0f7518fa8953ebbf6c489f66816c4cb0d5d441147 | .csv     |
| data/processed/20c_issues.csv                                                                       |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/20c_model_specification_ranking.csv                                                  |         2368 | 8d0a5475ade1c11872398dfc2030735008229f683069f42ffe580ad2add66830 | .csv     |
| data/processed/20c_oof_date_level_score_panel.csv                                                   |        27269 | 63952654200da1ada84c5cd092f725445f5de3b7e98d669dfd8ef3459de79917 | .csv     |
| data/processed/20c_oof_row_score_summary.csv                                                        |         1227 | 32eec3829c2eb4d56a5e36f9fa3a6e0029f4cb5c99ad734f2d2fceabe4c7db11 | .csv     |
| data/processed/20c_paired_date_level_comparisons.csv                                                |         1023 | fcb5285ef6e33b8aef58c11bceda723226c69e3668d0cba215ab6e07b5064c58 | .csv     |
| data/processed/20c_selected_model_benchmark_date_panel.csv                                          |         7465 | e22f6c68bdff6eb595e641a4d0a5e439731766fa44b0943eea3413068f2a9876 | .csv     |
| data/processed/20c_selected_model_benchmark_panel.csv                                               |       868727 | 2fc56942738c04bd461b539ff0e2eae273f315a95c3f51dc60f6eda2df199e4f | .csv     |
| data/processed/20c_selected_model_benchmark_summary.csv                                             |          475 | ae94855552dbdc2444da43efe5a7e3fe09c27ae9a15de5ef223d4eb021f50af6 | .csv     |
| data/processed/20c_selected_model_feature_importance.csv                                            |         2206 | 30a5a96d1741b38c27df65bf582f7e545bbd812097fc4f94a2d1d8da141f7eb4 | .csv     |
| data/processed/20c_selected_model_manifest.json                                                     |         1093 | 2aeabfc03c69b8abdd94b0619ac122892f766ea1c4df2e987c836449d5d4999e | .json    |
| data/processed/20d_calibration_date_level_scores.csv                                                |         3333 | 2ea04b21c927b9d23852ed30ced071556d3e68148513d12edd2b280e975adccd | .csv     |
| data/processed/20d_calibration_extreme_probability_diagnostics.csv                                  |          386 | 9462d1d9f2473337ad8c8e50c794c991c9b702113267bd019be026782ea3210f | .csv     |
| data/processed/20d_calibration_fit_inventory.csv                                                    |         1906 | abd05b19eff1a8ad714f9fe86429e9d359f77d586c60acaf57a7cd42dbb8b26f | .csv     |
| data/processed/20d_calibration_method_summary.csv                                                   |         1263 | 23922dea539182452f965012db6e877e8d00d6d5880ae157915ffdcbd1c94e45 | .csv     |
| data/processed/20d_common_support_binary_score_summary.csv                                          |          365 | 53bd8f9d1a141a6dcb3f39caf74102b71b75a3afa70d87c789e7903a3bb7c36d | .csv     |
| data/processed/20d_common_support_model_probability_panel.csv                                       |       488438 | 45870a03bf7b7e9b28e0b323dbdbab9b553e0b25d36f6fe5dad72786bc6d085c | .csv     |
| data/processed/20d_event_book_metrics.csv                                                           |        34078 | a22396ddf17f3df80d00168a620852f36914444f1575e7239d84c327a1ba1dea | .csv     |
| data/processed/20d_event_book_probability_panel.csv                                                 |       867497 | 6bab5c08d5b708e4e4d3847d5183374cec58bbaf0303ba2c0c71fb1f588fe650 | .csv     |
| data/processed/20d_event_book_score_summary.csv                                                     |          658 | c3cbdfe489580953bf0eda7297ec51cb40672222272d7c16327808d046c1c6d2 | .csv     |
| data/processed/20d_expanding_calibration_probability_panel.csv                                      |       860967 | f5f7aef5fb07b3c3bc227aceba367550167ea5d6a073d75025a209bd7c00f858 | .csv     |
| data/processed/20d_integrity_checks.csv                                                             |          706 | 8ec13455343d02123eb89551e52092dac39e2d98bb805f56ddb9bba7abc4243e | .csv     |
| data/processed/20d_issues.csv                                                                       |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/20d_paired_date_level_comparisons.csv                                                |          973 | 9fa42bdb8bd38268f939baba87ea5fea577aa0ad90b2a6724f28a2173a568b40 | .csv     |
| data/processed/20d_reliability_selected_calibration.csv                                             |          461 | c2cb5bf71d62748803f88cd1971f6883f2c37aaf001bd57c896d7cbcafeebba3 | .csv     |
| data/processed/20d_reliability_uncalibrated.csv                                                     |          535 | 35c3de7e56f4379efa7b666c989780e42978c679f373c2e12bbb52d4331ae59c | .csv     |
| data/processed/20d_selected_calibrated_probability_panel.csv                                        |       244647 | 9b34283a594eb1b497d8ac9ee6e268214add9dd205467cf2b1b62ff13d62379d | .csv     |
| data/processed/20e_locked_holdout_binary_score_summary.csv                                          |          554 | 835e62ad97053f88b600928a113742988f16d0d5845346beb68128e1493fa49f | .csv     |
| data/processed/20e_locked_holdout_common_support_panel.csv                                          |       440915 | a4a8c6627dbd0ffe3f29a5194c90b9dc506a9a0610c1b266f53852d82fa3d34a | .csv     |
| data/processed/20e_locked_holdout_event_book_metrics.csv                                            |        29811 | 6c67e18303fbe3e0aee88fb364c21c321914dd9c2940e6ec337589545300129c | .csv     |
| data/processed/20e_locked_holdout_event_book_probability_panel.csv                                  |       686209 | 5176a79db48bf8b4e2847940aaa101ebf30df31b18d0a7ce58c54101088c80ee | .csv     |
| data/processed/20e_locked_holdout_event_book_score_summary.csv                                      |          740 | 5919df43e10d849d1df70e045e28580579294ae3f1ce9d4b2eeeaafcb8416865 | .csv     |
| data/processed/20e_locked_holdout_integrity_checks.csv                                              |         1012 | fcd4c82f03f721b51599085481ffe009a6af84947d0b86e9394a0652756da0b6 | .csv     |
| data/processed/20e_locked_holdout_issues.csv                                                        |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/20e_locked_holdout_long_model_panel.csv                                              |       440915 | f4efd8d8d4d04e1e070d1f1be71dcefb3991e0fbd357e718b56030bbb429d76f | .csv     |
| data/processed/20e_locked_holdout_manifest.json                                                     |         1040 | f4021f271247a700b6550e6afa731891e5b9220a96aa54894daa41dc0351d493 | .json    |
| data/processed/20e_locked_holdout_paired_date_comparisons.csv                                       |         1135 | 99b3a0ed9b3c7dfde2c60e439eb93d36ea39a4ebc339541f07e4ab31569674b0 | .csv     |
| data/processed/20e_locked_holdout_prediction_panel.csv                                              |        90041 | 14e59f88bb1aeaad103dba3a3f8ac251f1d108ece1bbebdbf17477404a624106 | .csv     |
| data/processed/21a_simple_edge_daily_pnl.csv                                                        |        69759 | f5b48187460464fb5160d0cf71194009adc6f7d626062f0c52e55390a5fc7a6b | .csv     |
| data/processed/21a_simple_edge_integrity_checks.csv                                                 |         1056 | 2c7deba9a8fa8ff46953329fffc51155c05ed4468c112b36c5fb3976582638ec | .csv     |
| data/processed/21a_simple_edge_issues.csv                                                           |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/21a_simple_edge_manifest.json                                                        |         1359 | 701b38e3c78b217fc80bf33642ac772b83ff9bc22d36cf873ae57cd74c4d2129 | .json    |
| data/processed/21a_simple_edge_primary_pooled_diagnostic.csv                                        |         1109 | 74685a5cce723764e2bbf384e04b722e6a508e9e3a3921b2529d737915370c63 | .csv     |
| data/processed/21a_simple_edge_primary_standalone_strategy_summary.csv                              |         4535 | ffd18186b3894378d5f9de855f502a5072192ba994d32ab344e01e4ec6716802 | .csv     |
| data/processed/21a_simple_edge_strategy_summary.csv                                                 |        15176 | 5205e718b98b46e3998eb145ab523c2a29d7d3ff941c5b9a027262769cae3f69 | .csv     |
| data/processed/21a_simple_edge_threshold_summary.csv                                                |         2875 | cf5cf1f382ba760f6be140d4391558464c17e20cf87204aa608218a590d41eed | .csv     |
| data/processed/21a_simple_edge_trade_panel.csv                                                      |      1812240 | 0e07509098d49794ef0f0fe4d2edee700afab111cf611119da5feebd608c801d | .csv     |
| data/processed/21b_full_event_book_allocation_panel.csv                                             |      2757001 | 6216b5284a5769bdd26fa9cecac81f7d4f250dafff3939045a5ed87f16bb277b | .csv     |
| data/processed/21b_full_event_book_daily_pnl.csv                                                    |       158402 | 700ac37804e23031ca8ecac307595273514f57d84c39e03f6eb092a8da8d1856 | .csv     |
| data/processed/21b_full_event_book_integrity_checks.csv                                             |         1011 | 8a3b76174dd4d454d2a088c5d86e61154c49ea27cd030ceb356a41c2c2ee397e | .csv     |
| data/processed/21b_full_event_book_inventory.csv                                                    |        15674 | f14c1403eb233cfb1a143d9854295be68236db8587b3897ae13471db5edb0394 | .csv     |
| data/processed/21b_full_event_book_issues.csv                                                       |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/21b_full_event_book_manifest.json                                                    |         1221 | 830f8974a9245a0eb2bc80354189d89f06d79f941bad8a719a7b1461618a8499 | .json    |
| data/processed/21b_full_event_book_pooled_diagnostic.csv                                            |         4922 | 984ba51d39e42330af84ac02c03df173bb04302e82829f40f12c6ab94f45821c | .csv     |
| data/processed/21b_full_event_book_primary_standalone_summary.csv                                   |         6958 | 225f1111c73cc5f9b1821907e3c7ab05c74f028969ac44be25a95ff30b7883be | .csv     |
| data/processed/21b_full_event_book_probability_panel.csv                                            |       554480 | 12c44c8cbf7e2dbe565ab933af6ceec807f45a5f7318841ad9f920af9bb63df8 | .csv     |
| data/processed/21b_full_event_book_standalone_summary.csv                                           |        20916 | 2653608c2d6c5c465e8aa2a5c9fe9f0292370a325ef2736db5d1797088e0db48 | .csv     |
| data/processed/21b_full_event_book_strategy_results.csv                                             |       297444 | 058eb09e64a387be639a0d0ad68b682d5243bfc80055bb9ce2a9e6c80b39bd0b | .csv     |
| data/processed/21c_21a_cost_staleness_summary.csv                                                   |       240815 | d3add380679ff4f6d15e64c12a181e70df5b6cff3d33ad0c6f799ffe353310d9 | .csv     |
| data/processed/21c_21a_cost_staleness_trade_panel.csv                                               |     46286228 | 7533dde1cb224914f77c323d4e0642237379187196001609cfbc39b97a6b2676 | .csv     |
| data/processed/21c_21b_cost_staleness_book_panel.csv                                                |      8196223 | d7c5d494e303d78432b6d88a8d40cacc269173ec68f472ff8ac8df5443a8d137 | .csv     |
| data/processed/21c_21b_cost_staleness_summary.csv                                                   |       456225 | beb48796760e9d105abc992336eef26b05099d60fd7689a392e6bbf7def05d23 | .csv     |
| data/processed/21c_break_even_cost_summary.csv                                                      |        23482 | f109527538d2a1411aa1ea9984d8e622b9ea9908c72657b549b46de66545037a | .csv     |
| data/processed/21c_canonical_staleness_snapshots.csv                                                |        41199 | df56ccb62fca74cf225130ca8022e52499232c4262392a3e643a48a0b3569b01 | .csv     |
| data/processed/21c_cost_staleness_manifest.json                                                     |         1636 | 6563c3f81821b88768c4c9a40f11d88eed80ee16171da8e375bc814d4497aef4 | .json    |
| data/processed/21c_empirical_staleness_caps.csv                                                     |          646 | 9ecee2a773f9bd93083e95943276e00cc16fb7fa6ebf0f810d23da1260cfaaa4 | .csv     |
| data/processed/21c_integrity_checks.csv                                                             |         3573 | aa886e456f750fb84e83115c1dfe047b0258c269859622f1288f004de8f37fc5 | .csv     |
| data/processed/21c_issues.csv                                                                       |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/21c_primary_robustness_summary.csv                                                   |        13199 | a859f208791216122e85d30fd02b6ae1957c12857a9a562488b975cd3d62e0ad | .csv     |
| data/processed/21c_staleness_distribution_summary.csv                                               |          446 | 501ee2ea45191251ba104fb7a150a85ed575f479e622eec49144cf53c839902f | .csv     |
| data/processed/21d_common_support_forecast_table.csv                                                |          696 | 375cf4de985ee7af6832cc98e37bd3ed3986467eb8d043c6c09cd013fe41f6ad | .csv     |
| data/processed/21d_corrected_ecmwf_table.csv                                                        |         1048 | aadcaba17be383aa6be791846e8c629c52cbc72cc37845dc148fbe8cf022b4c9 | .csv     |
| data/processed/21d_empirical_headline.csv                                                           |          889 | 491ca43aae7d7e0e3447da0bf7257e94496820b233dfbdeac7555e9a588cf311 | .csv     |
| data/processed/21d_integrity_checks.csv                                                             |         1612 | 8cef120e7cc32495135aa996309afb8bccdddc48792008dcaf119c14c33b1ab0 | .csv     |
| data/processed/21d_issues.csv                                                                       |           20 | 8a2e599a3f31afd6c786c5958b273f92e4ca1513847ad539aa21233d70155035 | .csv     |
| data/processed/21d_locked_holdout_model_table.csv                                                   |         2905 | f4240ddca00919e36f599da8501897952477fcff0d1b9f422de21e34d9dbd454 | .csv     |
| data/processed/21d_manifest.json                                                                    |         1465 | 149668b872835ef017e265ae4af8eeeb700c752163ebe202c1c8bccc61e9ddc6 | .json    |
| data/processed/21d_market_baseline_table.csv                                                        |          473 | 2b4055bd7d590915511c52873cbaf4d17f64ba6311c44f04dd064fe8a1b87cf2 | .csv     |
| data/processed/21d_pipeline_integrity_summary.csv                                                   |          518 | 3303e7f2bdacf86722c938dabaca8ee5620851b8b9e8644691c54e4b0b7087f1 | .csv     |
| data/processed/21d_primary_robustness_table.csv                                                     |        13015 | 5a2ccf2bb7905fdcca661d135dd3162d8cf82ae63e8a799ed89798eac4a22fef | .csv     |
| data/processed/21d_primary_trading_table.csv                                                        |        13732 | 51e649bc337e8c1ec2162fa3ab29583921d7dbd70d61168945e85eb617123f73 | .csv     |
| docs/research_outputs/18m_full_hko_market_only_baseline_report.md                                   |        12260 | 93c84d806865a2949073b1d30c2899e8ad4df8154d8ec11ee7a9c83790f1dcd1 | .md      |
| docs/research_outputs/19b_common_support_market_vs_ecmwf_proxy_report.md                            |        18990 | 3e4e7009795877a2be1a728f5e616da6afecc89ca89a6619792f6d685d6354c8 | .md      |
| docs/research_outputs/19c_ecmwf_proxy_bias_scale_calibration_report.md                              |        31111 | b749c6793ab737f6be995f5863b61f2aba7eae9ef3fe1f186354894ef3f31404 | .md      |
| docs/research_outputs/20a_supervised_feature_matrix_report.md                                       |         8253 | 3d797b96bf664e14dcfe58a2c709737298e0627a4ef92a060a185b529dfca562 | .md      |
| docs/research_outputs/20b_validation_design_report.md                                               |         5420 | 1f40036fd1213cc4c755af9a3a5a1ba0e97fa00897be04ac4d4e5de7db91d3a7 | .md      |
| docs/research_outputs/20c_catboost_postprocessing_report.md                                         |        11214 | fd1413def2b152b94c63c7b184319712b983fda99b8f2566c7196795ae29a146 | .md      |
| docs/research_outputs/20d_calibration_coherence_report.md                                           |         8974 | 5209c74040f9fc9505cb78cbcd8ef5d1a84408e2bbb573eaf472381d9dab204f | .md      |
| docs/research_outputs/20e_locked_holdout_evaluation_report.md                                       |         8758 | 4c4d5bc177417e4242e7dc03ad58f96795add766031f9317110f5a5a8fecc162 | .md      |
| docs/research_outputs/21a_simple_edge_trading_report.md                                             |        20280 | 7cf818fa568998af9fca006503bd7397eb7a809b99b1e9a190674062499f9dba | .md      |
| docs/research_outputs/21b_full_event_book_trading_report.md                                         |        62623 | 354c7df0705de7914d4b8eefa623346293a3a9f871c7dd3ec90053940e00a13b | .md      |
| docs/research_outputs/21c_cost_staleness_robustness_report.md                                       |       102450 | a85b7d46290b08fd1057cba0069a5976ed49e7160921c9c2b2a1015e28e12ee8 | .md      |
| docs/research_outputs/21d_consolidated_empirical_report.md                                          |        58107 | d245ccb871249af84a174be54645b5ab51ae4d8e8d9fde97a39131cfb23be904 | .md      |
| figures/18m_market_only_baseline/18m_binary_brier_by_decision_rule.png                              |        58798 | db66708a0c521c04f329733f924b8df2c51f0b8bca55e93ee4a2941044d5a54a | .png     |
| figures/18m_market_only_baseline/18m_binary_log_score_by_decision_rule.png                          |        53865 | 0f8a89b8573cd163c5af2e04bcee1d6ef02ab9c1017d390df5ebeeecda1b73b4 | .png     |
| figures/18m_market_only_baseline/18m_book_probability_error_boxplot_by_decision_rule.png            |        58816 | f03be168f5ba8bd62f8e61567b6f124790ed544e80ad1f52e352aa96a50dfbdd | .png     |
| figures/18m_market_only_baseline/18m_market_probability_histogram_by_outcome.png                    |        46280 | 84cec12214a3a4a8dece5de4b6a7fee7d2d926751f469fba105b6d8a7b9c1a28 | .png     |
| figures/18m_market_only_baseline/18m_normalised_categorical_log_score_by_decision_rule.png          |        60389 | 894401a4ae3965270cf473e68d7f8bfcb19807f08c813b27f62bf7b6fb2d171c | .png     |
| figures/18m_market_only_baseline/18m_normalised_multiclass_brier_by_decision_rule.png               |        59850 | 833a91feb4ab7a634b405a5ee10b26f1f8ef48007aa7112536d40b04ec8c676f | .png     |
| figures/18m_market_only_baseline/18m_normalised_winning_probability_boxplot_by_decision_rule.png    |        61367 | a52be6fab9702ae9c795cf37b63e6afbda347812bd9543068a36d06bf9bdd99c | .png     |
| figures/18m_market_only_baseline/18m_price_staleness_boxplot_by_decision_rule.png                   |        64091 | 5c3cb885ddb73158bbca113f4eb2ace397aa8d3163ec59e2624ec17be7834778 | .png     |
| figures/19b_common_support_market_vs_ecmwf/19b_binary_brier_market_vs_ecmwf.png                     |        59441 | 8c2a6841d607613b3a83d325676557122cb94bd02261912b1fcfcb46bcca6cfe | .png     |
| figures/19b_common_support_market_vs_ecmwf/19b_binary_log_market_vs_ecmwf.png                       |        57145 | 3a90e7967789034b05788c93ce0b84b6244a974d9fec344e93f6d50d54017957 | .png     |
| figures/19b_common_support_market_vs_ecmwf/19b_normalised_categorical_log_market_vs_ecmwf.png       |        52638 | d92275c655c1576d52070fd10dbe19fe680d37f3ce708f167db5e4568436dd4d | .png     |
| figures/19b_common_support_market_vs_ecmwf/19b_normalised_multiclass_brier_market_vs_ecmwf.png      |        52750 | 799e9f82d370841a4975ad317369defb5d675f91c1a32b4169b2b533f9002ec7 | .png     |
| figures/19b_common_support_market_vs_ecmwf/19b_paired_log_score_difference_boxplot.png              |        47705 | 4c48e43633f644f8ddaf87bc1fc30500476bc9563fb11447b1d2033432bad2be | .png     |
| figures/19b_common_support_market_vs_ecmwf/19b_probability_scatter_market_vs_ecmwf.png              |       148126 | ec2c157851dc745c93007043b297b01b795b3b88ecd1f446c2462c6a1cb08c18 | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_binary_brier_model_comparison.png                |        95800 | 9affb8aca8d5b84b5e10390bfc3df81eeebb761dff36ab8ac49bbb79dc3b9dc6 | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_binary_log_model_comparison.png                  |        92090 | 7ee1065823b0219cf41acfe93be3a72c1e8a4bd27627871ff0aad3ebc64bb49a | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_expanding_bias_correction_path.png               |       212042 | 0b06b530125364f3e043f7d1c44590f5779f2e875bb7849abeafa9044466af5a | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_expanding_sigma_path.png                         |       168362 | 46792e03cd50f658c7473df69be06ad2a7980b244eedc0f8e7543bc6db61948d | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_normalised_categorical_log_model_comparison.png  |        91458 | 58c7dd0c88d89d65f52f0202f5d903cad0f5adc8b21cf92b75fc95a04e7e0c75 | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_normalised_multiclass_brier_model_comparison.png |        88831 | 9d63ffbcc24aa1ad4355ebdff21fc1853a9488351093394a1bced75b464ad739 | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_paired_log_score_improvement_bootstrap.png       |       126246 | 3599803b41b2f8cb94b229d38ce0fe5fafd3df38bb42c42d181af143bf93f4a9 | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_temperature_mae_raw_vs_corrected.png             |        77351 | 4fcff481476b3846156a83e31e0d134ccedafd3f10f4bbb01db3670e3776b8b3 | .png     |
| figures/19c_ecmwf_proxy_bias_scale_calibration/19c_temperature_mean_error_raw_vs_corrected.png      |        78712 | aab2f8512b2aec82efbc0ef016ff7437fb9c48a989a92e21b366924f40cea0e5 | .png     |
| figures/20a_supervised_feature_matrix/20a_core_predictor_correlation.png                            |       156562 | 34a34643fb29b145e91bff3217909f7dc51486f8a4580532e861ec320d01ce80 | .png     |
| figures/20a_supervised_feature_matrix/20a_feature_missingness_top20.png                             |        93344 | cf852caf44ee57f94efed6811d960ffedd929d1380be087f51fe9a22ea6ab964 | .png     |
| figures/20a_supervised_feature_matrix/20a_rows_by_decision_rule.png                                 |        54864 | 3a4fed386cda8f5151b429d1a7133a8112062f20496259ce792ea2d663129311 | .png     |
| figures/20a_supervised_feature_matrix/20a_target_prevalence_by_event_type.png                       |        70650 | d2b85685a3a5f19a01ceccd5b64dfef97eed540210be389389b69e403c756624 | .png     |
| figures/20b_validation_design/20b_date_level_target_prevalence.png                                  |        76038 | 5835d8d254df03f09aaa388d8f4f0a6da831fd2f166bc320f3ad64613eedbe2e | .png     |
| figures/20b_validation_design/20b_expanding_window_validation_blocks.png                            |        46781 | b9c1192447f077a024ffe8e41bf25ae24903cf8bd5e50c5bd3e331b47dfdf4a5 | .png     |
| figures/20b_validation_design/20b_final_chronological_partition.png                                 |        43481 | 85b0e46f2a3a9d867af2fb7645abf7b2789768e9f3595b45a328d002a9dd5ee0 | .png     |
| figures/20c_catboost_postprocessing/20c_oof_specification_brier_ranking.png                         |        89909 | 6f71d3635ea1902c025d909b5f44dcf1b2de3254abc406a5cab20300ff74cd57 | .png     |
| figures/20c_catboost_postprocessing/20c_paired_log_score_bootstrap.png                              |       111939 | e90ab3c15b1d4fba476767c86c3391434e9e88815e8106b177e6c8bfe1816f80 | .png     |
| figures/20c_catboost_postprocessing/20c_selected_model_feature_importance_top20.png                 |       142935 | c013e06cd2b0f56d1ec0e082a9fd45dd0d18e94764c7faab77db24bc28495808 | .png     |
| figures/20c_catboost_postprocessing/20c_selected_model_vs_benchmarks_brier.png                      |        99442 | 1f46a843625b34ca75834e54123c9a134eb006367aff55e0aeed3ec258aa0c3c | .png     |
| figures/20c_catboost_postprocessing/20c_selected_model_vs_benchmarks_log.png                        |        95891 | 74abb89dd2f66a424acfd425ae8196c9c78c3a67744b4a241a58245751e3e8c7 | .png     |
| figures/20d_calibration_coherence/20d_calibration_method_brier.png                                  |        47982 | 0968cbef438f2aa8628064b7cef2d52744d51f3543a05151ce82c10034ea1442 | .png     |
| figures/20d_calibration_coherence/20d_event_book_categorical_log.png                                |        90286 | 74f61458f656b4d0932758015ec0fdaad255f95bfb37da457fa841f550a86024 | .png     |
| figures/20d_calibration_coherence/20d_model_brier_comparison.png                                    |        94882 | 9262bc4aa3a007fba35b342081ed7c0b22260317f34c517ccb27f7e76ad00edb | .png     |
| figures/20d_calibration_coherence/20d_reliability_comparison.png                                    |       119373 | 12bde168faacf0e886444bd0ba3f8ba7a187b226e3823f0addc48a5cd8fde7da | .png     |
| figures/20e_locked_holdout/20e_holdout_brier_comparison.png                                         |        91376 | efaaeb18661ca33d5a1a715a77df50cbc08237e60c80caf3d57d0190e9952920 | .png     |
| figures/20e_locked_holdout/20e_holdout_categorical_log_comparison.png                               |        92045 | 9808adfbbb2543b6e9d3f2199fe75bc1592907b14e22b83623c731060f93752d | .png     |
| figures/20e_locked_holdout/20e_holdout_log_score_comparison.png                                     |        94361 | c9798a42006784f7b413b8bef653b2011a6902e5b51afdff33c82fec5532ee63 | .png     |
| figures/20e_locked_holdout/20e_holdout_paired_log_score_bootstrap.png                               |       132162 | 9b2471eceb44a9e9ff5d7e541e06d9c4825bce1fc042fd20a0cfd16ca0b911ac | .png     |
| figures/21a_simple_edge_trading/21a_cumulative_net_pnl_12h_prior.png                                |       165771 | 8ccf9ec5c68e14ec51632c7d71b48ce9c3056a862a37f637d285aea849504efe | .png     |
| figures/21a_simple_edge_trading/21a_cumulative_net_pnl_24h_prior.png                                |       160966 | 829c18880d4ff1444aa49a6e1bab4d935774cc8a4bd10b96551ab239fbd13d8e | .png     |
| figures/21a_simple_edge_trading/21a_cumulative_net_pnl_6h_prior.png                                 |       189507 | 264b53ef3f8e06f761d635e1c471c1ac7fc0b71a1efc597a496a9d334c4b2c2d | .png     |
| figures/21a_simple_edge_trading/21a_cumulative_net_pnl_event_day_open.png                           |       187937 | 281e3e9370af26e26c7c4fc942f40198dd14ca22e4377f9cc0a47169ea700377 | .png     |
| figures/21a_simple_edge_trading/21a_standalone_mean_net_pnl_per_trade.png                           |       229127 | b99f02827cefdc857b963c5b8c56bfa28979c321f50f449515e22971f677e67c | .png     |
| figures/21a_simple_edge_trading/21a_standalone_total_net_pnl_primary_threshold.png                  |       215144 | 0189b0c9a3b7b9f0ceceaa301281c1cd350a206627bf78994502255d06ce085d | .png     |
| figures/21a_simple_edge_trading/21a_standalone_trade_counts.png                                     |       218909 | a338845e07bf318ad50cbd11f8633b446cbcef62a3f73ee1b5d33d045db96a20 | .png     |
| figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_12h_prior.png         |       171117 | 3ce574c8e221ed21b4047f655ab90c172c3340a5c6bbb7db37888540938b1654 | .png     |
| figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_24h_prior.png         |       169580 | 9d5977e3df48281be5ee57aed952a1b728934276a7bb0bb25f02782ff129b189 | .png     |
| figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_6h_prior.png          |       163254 | 0b06ca9e979f457f5432ae23ccd3ee0c500b3f43d15b4dca67ff621458874729 | .png     |
| figures/21b_full_event_book_trading/21b_proportional_positive_edge_cumulative_event_day_open.png    |       176457 | 794ca10eaafd3ee69cbd740e8cdb32d5d90c20574230c6fbc27327abc1478dbd | .png     |
| figures/21b_full_event_book_trading/21b_proportional_positive_edge_standalone_total_pnl.png         |       233010 | b57beda0d94394bc3f8341b9b5e3c8eec6b3aba0961c1b0a92d0b13b94590c7f | .png     |
| figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_12h_prior.png                   |       143285 | a3da8ed51f8564d922f97dad518e1c1b81cc19b01047cd7c67ad74b22b06aabb | .png     |
| figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_24h_prior.png                   |       162619 | 21f8470cc992021b18bdf07c22413206071eade0b0226c64d8dba3eb07048ed0 | .png     |
| figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_6h_prior.png                    |       155304 | 11f0b45bdc4743c816ed18b48bb71912acaaaf4281145c512ed7d479ffe18e95 | .png     |
| figures/21b_full_event_book_trading/21b_single_best_edge_cumulative_event_day_open.png              |       152233 | 893292c9816e31f87562181eda9f1d3bb7c2271054bcad8ea4b67b2b301116be | .png     |
| figures/21b_full_event_book_trading/21b_single_best_edge_standalone_total_pnl.png                   |       226479 | 0bb3cdff1eac2329eea6f22f84028e50676455cbcafff25534b28a440f0147a4 | .png     |
| figures/21c_cost_staleness_robustness/21c_21a_cost_sensitivity.png                                  |       233130 | bd2b27954b949ab9197f9bcf91fcc8a71007419407d4a2545995f6f222f3633b | .png     |
| figures/21c_cost_staleness_robustness/21c_21a_staleness_sensitivity.png                             |       170233 | 82756ab5b765fbd0da7d1b9ab9d9187c8c46e097f249381ed19f2bf8aac71c8e | .png     |
| figures/21c_cost_staleness_robustness/21c_21b_cost_sensitivity.png                                  |       209627 | 8aa9c2c21ffcc052af105577a7c8c2d716be9ecd704fe56d2c4d496183ac0f94 | .png     |
| figures/21c_cost_staleness_robustness/21c_21b_staleness_sensitivity.png                             |       176942 | 3eb8d4b1ddce9f5e6b2e6c66e9f2ac12e6ef2de274f69cbd30a615feddea95a9 | .png     |
| figures/21c_cost_staleness_robustness/21c_primary_robust_total_pnl.png                              |       649773 | f657be07c1cfecedb39a617673086b7bba3f29d61a356076e5dd308d1c33b659 | .png     |
| figures/21d_dissertation_ready_empirical/21d_common_support_brier.png                               |        70611 | 442741a38ace10e108816299b1131cec8fd559b60996a92bdfbd1ef08c094f6e | .png     |
| figures/21d_dissertation_ready_empirical/21d_locked_holdout_brier_ranking.png                       |       122346 | bd32024f8af6b6e31f5a5b8853f4b26adb9f87290bfa08c73d272b75e45853ca | .png     |
| figures/21d_dissertation_ready_empirical/21d_primary_robustness_headline.png                        |       174330 | b4a1f15b05c04260813ef38bd59d6893ea9a20b58be151508273776a4d836780 | .png     |
| figures/21d_dissertation_ready_empirical/21d_primary_trading_headline.png                           |       167636 | 0a4b42d7ea71cadf53d780ae526921447889619fc078946846cbaec19c4b1b87 | .png     |
