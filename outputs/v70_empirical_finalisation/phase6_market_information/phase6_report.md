# Phase 6 — Market Comparison and Information Content

Generated: `2026-08-01T02:05:56.144160+00:00`

## Overall status: **PASSED**

## Provenance

```json
{
  "bootstrap_replications": 10000,
  "bootstrap_seed": 20260804,
  "exact_support_keys": "outputs/v70_empirical_finalisation/phase1_evidence_recovery/phase1_master_exact_support_keys.csv",
  "exact_support_keys_sha256": "4709ab8f71bab3dc5d949c06e26090eda7d7600e09424fada3d163d297a0ad0c",
  "frozen_commit": "1b0900086c315588b0dc41225e41c2b5f2189bfa",
  "frozen_exact_support_panel": "outputs/v2_completion/phase20_exact_common_support_event_panel.csv",
  "frozen_exact_support_panel_sha256": "73261a14cf4338ff68bbc6402eaada0bdaeb906bc360bf70411054a09b98b189",
  "frozen_exact_support_role": "authoritative selected-Matern, outcomes, event order and normalised market exact-support books",
  "frozen_ref": "v2-empirical-complete",
  "frozen_tag_object": "5d48edb55074f4018d842482bab9f7bf4ab1c01e",
  "generated_utc": "2026-08-01T02:05:48.548552+00:00",
  "interpretation_boundary": "The phase compares realised forecast losses and describes co-movement between market prices and forecast revisions. It does not identify a causal market response to a particular weather observation, and it does not interpret lower market loss as proof of market efficiency.",
  "moving_block_lengths": [
    3,
    5,
    7
  ],
  "raw_market_probability_inventory": "outputs/v70_empirical_finalisation/phase1_evidence_recovery/phase1_canonical_existing_event_books.csv.gz",
  "raw_market_probability_inventory_sha256": "4cfccb175646b68f2542877df7cc885da330664492cf13c7116aff8c5dd58609",
  "raw_market_probability_role": "true unnormalised market_probability_raw values for binary scores",
  "reconstructed_event_books": "outputs/v70_empirical_finalisation/phase1_evidence_recovery/phase1_reconstructed_raw_static_event_books.csv.gz",
  "reconstructed_event_books_sha256": "990fd417094e1ddf3ef0fafee4829bef182365faa5d645e465fdc5315d125401",
  "working_branch": "edward-v70-empirical-finalisation",
  "working_commit": "14fd19dcb333f4883890d347904d231f25a50491"
}
```

## Integrity checks

| check                                         | passed   | critical   | detail                                                                                                                            |
|:----------------------------------------------|:---------|:-----------|:----------------------------------------------------------------------------------------------------------------------------------|
| phase1_dependency                             | True     | True       | critical_failures=0                                                                                                               |
| phase2_dependency                             | True     | True       | critical_failures=0                                                                                                               |
| phase3_dependency                             | True     | True       | critical_failures=0                                                                                                               |
| phase4_dependency                             | True     | True       | critical_failures=0                                                                                                               |
| phase5_dependency                             | True     | True       | critical_failures=0                                                                                                               |
| exact_support_key_count                       | True     | True       | keys=350                                                                                                                          |
| exact_support_date_count                      | True     | True       | dates=97                                                                                                                          |
| required_models_present                       | True     | True       | models=['market', 'matern', 'raw', 'static']                                                                                      |
| event_rows_per_model                          | True     | True       | counts={'market': 3850, 'matern': 3850, 'raw': 3850, 'static': 3850}                                                              |
| events_per_book                               | True     | True       | bad_events=0; bad_rows=0                                                                                                          |
| one_winner_per_book                           | True     | True       | minimum=1.000000000000; maximum=1.000000000000                                                                                    |
| probabilities_finite_bounded                  | True     | True       | minimum=0.000000000000; maximum=1.000000000000                                                                                    |
| normalised_books_sum_to_one                   | True     | True       | maximum_error=2.220e-16                                                                                                           |
| books_per_model                               | True     | True       | counts={'market': 350, 'matern': 350, 'raw': 350, 'static': 350}                                                                  |
| development_date_count                        | True     | True       | counts={'development': 67, 'june_external': 30}                                                                                   |
| june_external_date_count                      | True     | True       | counts={'development': 67, 'june_external': 30}                                                                                   |
| unique_event_keys                             | True     | True       | duplicates=0                                                                                                                      |
| raw_market_probability_rows_recovered         | True     | True       | rows=3850                                                                                                                         |
| raw_market_probability_books_recovered        | True     | True       | books=350                                                                                                                         |
| raw_market_normalisation_reconciles           | True     | True       | maximum_error=1.110e-16                                                                                                           |
| raw_market_books_not_pre_normalised           | True     | True       | mean_sum=1.045380; minimum_sum=0.869000; maximum_sum=1.300000                                                                     |
| june_reference_binary_brier                   | True     | True       | calculated=0.009323867; reference=0.009323867; difference=-3.469e-18                                                              |
| june_reference_binary_log                     | True     | True       | calculated=0.038628062; reference=0.038628062; difference=0.000e+00                                                               |
| june_reference_categorical_log                | True     | True       | calculated=0.357342206; reference=0.357342206; difference=-3.886e-16                                                              |
| june_reference_multiclass_brier               | True     | True       | calculated=0.101709592; reference=0.101709592; difference=0.000e+00                                                               |
| legacy_june_binary_brier_reference_registered | True     | False      | authoritative=0.009323867; legacy=0.009246327; difference=7.754e-05; status=legacy_value_differs_from_authoritative_recomputation |
| book_score_rows                               | True     | True       | rows=1400                                                                                                                         |
| date_score_rows                               | True     | True       | rows=388                                                                                                                          |
| score_metrics_complete                        | True     | True       | metrics=['binary_brier', 'binary_log', 'categorical_log', 'multiclass_brier']                                                     |
| score_bootstrap_methods                       | True     | True       | methods=['circular_moving_block', 'ordinary_date']                                                                                |
| score_moving_block_lengths                    | True     | True       |                                                                                                                                   |
| disagreement_rows                             | True     | True       | rows=350                                                                                                                          |
| transition_panels_nonempty                    | True     | True       | event_rows=3586; book_rows=326                                                                                                    |
| transition_probability_mass_conserved         | True     | True       |                                                                                                                                   |
| market_age_registered                         | True     | False      | available=False; coverage=0.000000                                                                                                |
| figures_created                               | True     | True       | figures=7                                                                                                                         |

## Interpretation boundary

The phase compares realised forecast losses and describes co-movement between market prices and forecast revisions. It does not identify a causal market response to a particular weather observation, and it does not interpret lower market loss as proof of market efficiency.

## June external Matérn-versus-market comparison

- **Binary Brier:** model minus market 0.009324; 95% date-bootstrap interval [0.003808, 0.014558].
- **Binary log:** model minus market 0.038628; 95% date-bootstrap interval [0.021931, 0.054179].
- **Categorical log:** model minus market 0.357342; 95% date-bootstrap interval [0.212037, 0.493912].
- **Multiclass Brier:** model minus market 0.101710; 95% date-bootstrap interval [0.042318, 0.158117].

Positive differences mean that Polymarket had lower realised loss. The comparison is restricted to identical settlement dates, decision rules and eleven-event books.

## Development versus external interpretation

| split             | metric           |   dates |   mean_model_minus_market |   model_better_fraction |   market_better_fraction |
|:------------------|:-----------------|--------:|--------------------------:|------------------------:|-------------------------:|
| development       | binary_brier     |      67 |               -0.00131419 |                0.477612 |                 0.522388 |
| development       | binary_log       |      67 |               -0.00307298 |                0.38806  |                 0.61194  |
| development       | categorical_log  |      67 |               -0.018209   |                0.38806  |                 0.61194  |
| development       | multiclass_brier |      67 |               -0.0127033  |                0.492537 |                 0.507463 |
| june_external     | binary_brier     |      30 |                0.00932387 |                0.166667 |                 0.833333 |
| june_external     | binary_log       |      30 |                0.0386281  |                0.166667 |                 0.833333 |
| june_external     | categorical_log  |      30 |                0.357342   |                0.133333 |                 0.866667 |
| june_external     | multiclass_brier |      30 |                0.10171    |                0.166667 |                 0.833333 |
| all_exact_support | binary_brier     |      97 |                0.00197593 |                0.381443 |                 0.618557 |
| all_exact_support | binary_log       |      97 |                0.00982425 |                0.319588 |                 0.680412 |
| all_exact_support | categorical_log  |      97 |                0.0979409  |                0.309278 |                 0.690722 |
| all_exact_support | multiclass_brier |      97 |                0.0226821  |                0.391753 |                 0.608247 |

## Probability-book disagreement

| split             | metric                                         |   dates |      mean |    median |        q10 |      q90 |
|:------------------|:-----------------------------------------------|--------:|----------:|----------:|-----------:|---------:|
| development       | total_variation_market_matern                  |      67 | 0.290671  | 0.295612  |  0.182785  | 0.390925 |
| development       | expected_rank_market_minus_matern              |      67 | 0.41461   | 0.479682  | -0.468854  | 1.16621  |
| development       | modal_disagreement                             |      67 | 0.573383  | 0.666667  |  0         | 1        |
| development       | realised_event_probability_market_minus_matern |      67 | 0.0302973 | 0.0470725 | -0.135696  | 0.16793  |
| june_external     | total_variation_market_matern                  |      30 | 0.278613  | 0.288706  |  0.184998  | 0.374168 |
| june_external     | expected_rank_market_minus_matern              |      30 | 0.474392  | 0.34606   | -0.116952  | 1.09218  |
| june_external     | modal_disagreement                             |      30 | 0.616667  | 0.5       |  0.25      | 1        |
| june_external     | realised_event_probability_market_minus_matern |      30 | 0.0945036 | 0.105613  | -0.0319084 | 0.195979 |
| all_exact_support | total_variation_market_matern                  |      97 | 0.286942  | 0.295241  |  0.184872  | 0.386836 |
| all_exact_support | expected_rank_market_minus_matern              |      97 | 0.4331    | 0.472229  | -0.273071  | 1.16208  |
| all_exact_support | modal_disagreement                             |      97 | 0.58677   | 0.666667  |  0         | 1        |
| all_exact_support | realised_event_probability_market_minus_matern |      97 | 0.0501549 | 0.0606584 | -0.117938  | 0.181229 |

A positive expected-rank shift means that the market places relatively more probability on warmer-ranked events than the selected Matérn law. A positive realised-event probability difference means that the market assigns more probability to the event that ultimately settles Yes.

## Forecast revisions and market movement

| transition   | metric                                 |   dates |        mean |      median |        q10 |       q90 |
|:-------------|:---------------------------------------|--------:|------------:|------------:|-----------:|----------:|
| 24h_to_12h   | market_update_total_variation          |      77 |  0.0948178  |  0.0944356  |  0.0449341 | 0.151926  |
| 24h_to_12h   | matern_update_total_variation          |      77 |  0.12977    |  0.103784   |  0.0167225 | 0.314998  |
| 24h_to_12h   | update_cosine_similarity               |      77 |  0.162687   |  0.225594   | -0.565482  | 0.687691  |
| 24h_to_12h   | market_movement_towards_updated_matern |      77 | -0.00931598 | -0.00915049 | -0.0891009 | 0.0528871 |
| 12h_to_6h    | market_update_total_variation          |      84 |  0.138769   |  0.121374   |  0.0512282 | 0.225839  |
| 12h_to_6h    | matern_update_total_variation          |      84 |  0.110371   |  0.0720803  |  0.0269032 | 0.240512  |
| 12h_to_6h    | update_cosine_similarity               |      84 | -0.0117399  | -0.0174669  | -0.658414  | 0.711852  |
| 12h_to_6h    | market_movement_towards_updated_matern |      84 | -0.0415838  | -0.041293   | -0.155861  | 0.0550687 |
| 6h_to_open   | market_update_total_variation          |      85 |  0.104905   |  0.0861531  |  0.0345585 | 0.17983   |
| 6h_to_open   | matern_update_total_variation          |      85 |  0.132779   |  0.105847   |  0.0377708 | 0.278072  |
| 6h_to_open   | update_cosine_similarity               |      85 |  0.028254   |  0.100738   | -0.660688  | 0.571821  |
| 6h_to_open   | market_movement_towards_updated_matern |      85 | -0.0284819  | -0.0213271  | -0.125704  | 0.0419292 |
| 24h_to_open  | market_update_total_variation          |      80 |  0.218478   |  0.204762   |  0.112499  | 0.328857  |
| 24h_to_open  | matern_update_total_variation          |      80 |  0.146404   |  0.106921   |  0.0444795 | 0.286284  |
| 24h_to_open  | update_cosine_similarity               |      80 |  0.217355   |  0.380085   | -0.611037  | 0.759394  |
| 24h_to_open  | market_movement_towards_updated_matern |      80 | -0.0741866  | -0.0764698  | -0.217517  | 0.0867765 |

| transition   |   observations |   date_clusters |   slope_delta_market_on_delta_matern |   cluster_robust_slope_standard_error |   cluster_robust_p_value |   r_squared |
|:-------------|---------------:|----------------:|-------------------------------------:|--------------------------------------:|-------------------------:|------------:|
| 24h_to_12h   |            847 |              77 |                            0.0989266 |                             0.0333559 |                0.0040328 | 0.017976    |
| 12h_to_6h    |            924 |              84 |                           -0.0251988 |                             0.0789448 |                0.75038   | 0.000318255 |
| 6h_to_open   |            935 |              85 |                           -0.0235281 |                             0.0651985 |                0.719103  | 0.000629079 |
| 24h_to_open  |            880 |              80 |                            0.106962  |                             0.115419  |                0.356889  | 0.00424945  |

These regressions describe co-movement. Forecast cycle, lead time and other public information change jointly, so the slope is not a causal market-response coefficient.

## Market-record age

Selected market-record timestamps were not recoverable from the canonical book panel. The missing summary is registered explicitly.

## Thesis use

- Main text: June external Matérn-versus-market score differences and intervals.
- Main text: one compact disagreement table explaining the realised-event probability gap.
- Discussion or appendix: transition co-movement and market movement towards the updated model.
- Appendix: full rule-level score matrix, moving-block intervals, score decomposition and market-book normalisation.
- Do not say that the market is efficient, that it causally absorbs the GP forecast, or that lower realised loss guarantees tradable profit.
