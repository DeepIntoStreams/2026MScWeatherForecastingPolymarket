# Phase 8 — Final Empirical Synthesis

Generated: `2026-08-01T03:45:47.175928+00:00`

## Overall status: **PASSED**

## Purpose

Phase 8 consolidates the completed Phase 1–7 evidence into one audited, thesis-ready package. It performs no refitting, model selection, support imputation or June-based tuning.

## Provenance

```json
{
  "generated_utc": "2026-08-01T03:45:46.856773+00:00",
  "no_refit": true,
  "phase_roots": {
    "phase1": "outputs/v70_empirical_finalisation/phase1_evidence_recovery",
    "phase2": "outputs/v70_empirical_finalisation/phase2_settlement_error",
    "phase3": "outputs/v70_empirical_finalisation/phase3_information_arrival",
    "phase4": "outputs/v70_empirical_finalisation/phase4_forecast_attribution",
    "phase5": "outputs/v70_empirical_finalisation/phase5_calibration_misspecification",
    "phase6": "outputs/v70_empirical_finalisation/phase6_market_information",
    "phase7": "outputs/v70_empirical_finalisation/phase7_trading_sensitivity"
  },
  "remote_alignment": "0\t1",
  "working_branch": "edward-v70-empirical-finalisation",
  "working_commit": "63534484fad31eb8becc71be11d6669fca257d21"
}
```

## Binding no-refit boundary

- Do not refit the GP.
- Do not alter the selected Matérn kernel.
- Do not reselect the pool weight.
- Do not reselect the trading rule or threshold using June.
- Do not impute missing forecast or market support.
- Do not introduce a new model family into the frozen comparison.

## Cross-phase integrity

| check                                     | passed   | critical   | detail                                                                                                                                          |
|:------------------------------------------|:---------|:-----------|:------------------------------------------------------------------------------------------------------------------------------------------------|
| all_phase_dependencies                    | True     | True       | critical_rows=14                                                                                                                                |
| all_phase_manifests                       | True     | True       | phases_passed=7/7                                                                                                                               |
| candidate_ids_unique                      | True     | True       | rows=72; unique_ids=72                                                                                                                          |
| support_weather_rows                      | True     | True       | calculated=2920; reference=2920                                                                                                                 |
| support_weather_dates                     | True     | True       | calculated=730; reference=730                                                                                                                   |
| support_market_predictions_unique_keys    | True     | True       | calculated=375; reference=375                                                                                                                   |
| support_phase10_exact_support_rows        | True     | True       | calculated=3850; reference=3850                                                                                                                 |
| support_phase10_exact_support_dates       | True     | True       | calculated=97; reference=97                                                                                                                     |
| support_phase11_trade_ledger_rows         | True     | True       | calculated=350; reference=350                                                                                                                   |
| reference_p4_mean_raw                     | True     | True       | calculated=1.745684932; reference=1.745685000                                                                                                   |
| reference_p4_mean_static                  | True     | True       | calculated=0.911754550; reference=0.911755000                                                                                                   |
| reference_p4_mean_rbf                     | True     | True       | calculated=0.877561468; reference=0.877561000                                                                                                   |
| reference_p4_mean_matern                  | True     | True       | calculated=0.863339999; reference=0.863340000                                                                                                   |
| reference_p4_contrast_matern_minus_static | True     | True       | calculated=-0.048414551; reference=-0.048415000                                                                                                 |
| reference_p4_contrast_matern_minus_rbf    | True     | True       | calculated=-0.014221469; reference=-0.014221000                                                                                                 |
| reference_p6_june_binary_brier            | True     | True       | calculated=0.009323867; reference=0.009323867                                                                                                   |
| reference_p6_june_binary_log              | True     | True       | calculated=0.038628062; reference=0.038628062                                                                                                   |
| reference_p6_june_categorical_log         | True     | True       | calculated=0.357342206; reference=0.357342206                                                                                                   |
| reference_p6_june_multiclass_brier        | True     | True       | calculated=0.101709592; reference=0.101709592                                                                                                   |
| reference_p7_june_trade_count             | True     | True       | calculated=16.000000000; reference=16.000000000                                                                                                 |
| reference_p7_june_winning_trades          | True     | True       | calculated=1.000000000; reference=1.000000000                                                                                                   |
| reference_p7_june_total_net_pnl           | True     | True       | calculated=0.023500000; reference=0.023500000                                                                                                   |
| reference_p7_attr_raw                     | True     | True       | calculated=-1.807500000; reference=-1.807500000                                                                                                 |
| reference_p7_attr_static                  | True     | True       | calculated=0.023500000; reference=0.023500000                                                                                                   |
| reference_p7_attr_matern                  | True     | True       | calculated=0.023500000; reference=0.023500000                                                                                                   |
| forecast_loss_ladder                      | True     | True       | raw_static_rbf_matern=[1.7456849315068492, 0.9117545500469532, 0.8775614684388354, 0.8633399989586301]                                          |
| june_market_advantage_all_scores          | True     | True       | all four point estimates and ordinary lower bounds exceed zero                                                                                  |
| june_pnl_interval_contains_zero           | True     | True       | interval=(-1.232025, 2.1705375)                                                                                                                 |
| june_static_equals_matern_fixed_policy    | True     | True       | static=0.023500000; matern=0.023500000                                                                                                          |
| figure_shortlist_complete                 | True     | True       | figures=7/7                                                                                                                                     |
| market_age_limitation_registered          | True     | False      | rows=1; columns=['market_age_available', 'books', 'books_with_age', 'coverage_fraction', 'timestamp_columns_present', 'decision_cutoff_source'] |
| market_period_hko_limitation_registered   | True     | False      | rows_with_exact_hko=0                                                                                                                           |

## Weather and forecast attribution

| result                                          |   estimate |    lower_95 |    upper_95 | direction_convention                    | interpretation                                                                                    | evidence_id                     |
|:------------------------------------------------|-----------:|------------:|------------:|:----------------------------------------|:--------------------------------------------------------------------------------------------------|:--------------------------------|
| Mean HKO-minus-deterministic residual (°C)      |  1.42966   |   1.32736   |   1.53092   | positive means HKO is warmer            | The deterministic forecast is systematically colder than the HKO settlement maximum.              | P2_MEAN                         |
| Proportion of deterministic forecasts below HKO |  0.824658  |   0.799658  |   0.84863   |                                         | The cold discrepancy occurs on a large majority of date-rule observations.                        | P2_UNDER                        |
| 24h-to-open MAE improvement (°C)                |  0.104247  |   0.050137  |   0.159182  | positive means later forecast is better | Later information modestly improves point accuracy while the settlement discrepancy persists.     | P3_ENDPOINT_MAE                 |
| Raw point mean date CRPS                        |  1.74568   | nan         | nan         |                                         | Uncorrected deterministic benchmark.                                                              | P4_MEAN_RAW                     |
| Static Gaussian mean date CRPS                  |  0.911755  | nan         | nan         |                                         | Most of the raw-to-Matérn improvement is achieved by local rule-specific correction.              | P4_MEAN_STATIC                  |
| RBF GP mean date CRPS                           |  0.877561  | nan         | nan         |                                         | Conditional GP structure adds a smaller refinement.                                               | P4_MEAN_RBF                     |
| Matérn-3/2 GP mean date CRPS                    |  0.86334   | nan         | nan         |                                         | Best retained weather-only predictive law.                                                        | P4_MEAN_MATERN                  |
| Matérn minus static paired CRPS                 | -0.0484146 |  -0.0699685 |  -0.0273388 | negative favours Matérn                 | Negative values favour Matérn; the incremental improvement is smaller than the static correction. | P4_CONTRAST_MATERN_MINUS_STATIC |
| Matérn minus RBF paired CRPS                    | -0.0142215 |  -0.0205288 |  -0.0079037 | negative favours Matérn                 | Negative values favour Matérn; the kernel increment is modest.                                    | P4_CONTRAST_MATERN_MINUS_RBF    |

The final forecasting story is deliberately narrow: the raw deterministic forecast has a large local settlement discrepancy; the static rule-specific Gaussian law captures most of the gain; RBF and Matérn conditional structure provide smaller refinements.

## Distributional adequacy

| result                                            |   estimate |    lower_95 |   upper_95 | direction_convention   | interpretation                                                   | evidence_id      |
|:--------------------------------------------------|-----------:|------------:|-----------:|:-----------------------|:-----------------------------------------------------------------|:-----------------|
| Empirical 50% central coverage                    |  0.460274  | nan         | nan        |                        | Close to but below nominal coverage.                             | P5_COVERAGE_50   |
| Empirical 80% central coverage                    |  0.782877  | nan         | nan        |                        | Mild undercoverage.                                              | P5_COVERAGE_80   |
| Empirical 90% central coverage                    |  0.880822  | nan         | nan        |                        | Mild undercoverage.                                              | P5_COVERAGE_90   |
| Lag-one standardised-residual correlation         |  0.509768  |   0.398188  |   0.587808 |                        | Residual serial dependence remains after postprocessing.         | P5_LAG1_Z        |
| Lag-one squared-standardised-residual correlation |  0.238256  |   0.0992232 |   0.347825 |                        | Conditional scale dependence remains.                            | P5_LAG1_Z2       |
| Conditional-variance joint p-value                |  0.0100106 | nan         | nan        |                        | The homoskedastic Gaussian observation law remains misspecified. | P5_VARIANCE_WALD |

The selected Matérn law is useful but not fully specified: mild undercoverage, residual serial dependence and conditional-variance structure remain.

## Exact-support market comparison

| result                                               |   estimate |     lower_95 |    upper_95 | direction_convention                        | interpretation                                                      | evidence_id                                                     |
|:-----------------------------------------------------|-----------:|-------------:|------------:|:--------------------------------------------|:--------------------------------------------------------------------|:----------------------------------------------------------------|
| June Matérn minus market binary Brier                | 0.00932387 |   0.00380828 |   0.0145581 | positive favours market                     | Positive values indicate lower realised market loss.                | P6_JUNE_BINARY_BRIER                                            |
| June Matérn minus market binary log                  | 0.0386281  |   0.0219311  |   0.0541788 | positive favours market                     | Positive values indicate lower realised market loss.                | P6_JUNE_BINARY_LOG                                              |
| June Matérn minus market categorical log             | 0.357342   |   0.212037   |   0.493912  | positive favours market                     | Positive values indicate lower realised market loss.                | P6_JUNE_CATEGORICAL_LOG                                         |
| June Matérn minus market multiclass Brier            | 0.10171    |   0.0423182  |   0.158117  | positive favours market                     | Positive values indicate lower realised market loss.                | P6_JUNE_MULTICLASS_BRIER                                        |
| June market-Matérn total variation                   | 0.278613   | nan          | nan         |                                             | The two probability books differ materially.                        | P6_JUNE_EXTERNAL_TOTAL_VARIATION_MARKET_MATERN                  |
| June expected-rank shift, market minus Matérn        | 0.474392   | nan          | nan         | positive means warmer market rank           | Positive values indicate a warmer market distribution.              | P6_JUNE_EXTERNAL_EXPECTED_RANK_MARKET_MINUS_MATERN              |
| June realised-event probability, market minus Matérn | 0.0945036  | nan          | nan         | positive favours market realised-event mass | The market assigned more probability to the event that settled Yes. | P6_JUNE_EXTERNAL_REALISED_EVENT_PROBABILITY_MARKET_MINUS_MATERN |

The June result is an external exact-support comparison. It does not imply that the market universally dominates the weather model outside this period.

## Trading and forecast-risk sensitivity

| result                                     |   estimate |   lower_95 |   upper_95 | direction_convention   | interpretation                                                                    | evidence_id                       |
|:-------------------------------------------|-----------:|-----------:|-----------:|:-----------------------|:----------------------------------------------------------------------------------|:----------------------------------|
| June executed trades                       | 16         |  nan       |  nan       |                        | Frozen event-day-open policy at h=0.12.                                           | P7_JUNE_TRADE_COUNT               |
| June winning trades                        |  1         |  nan       |  nan       |                        | The result is concentrated in one profitable trade.                               | P7_JUNE_WINNING_TRADES            |
| June net PnL at one-cent cost              |  0.0235    |   -1.23202 |    2.17054 |                        | The point estimate is slightly positive, but its interval includes zero widely.   | P7_JUNE_TOTAL_NET_PNL             |
| June return on entry cash                  |  0.0240655 |  nan       |  nan       |                        | A descriptive historical ratio, not evidence of executable return.                | P7_JUNE_RETURN_ON_ENTRY_CASH      |
| June maximum drawdown                      |  0.7965    |  nan       |  nan       |                        | Chronological date-level path risk.                                               | P7_JUNE_MAXIMUM_DRAWDOWN          |
| June break-even cost per trade             |  0.0114687 |  nan       |  nan       |                        | The apparent edge disappears above approximately 1.15 cents per trade.            | P7_JUNE_BREAK_EVEN_COST_PER_TRADE |
| Largest-trade absolute contribution share  |  0.506363  |  nan       |  nan       |                        | The PnL is highly concentrated.                                                   | P7_JUNE_TOP1_CONCENTRATION        |
| June common-policy PnL using raw signal    | -1.8075    |  nan       |  nan       |                        | Raw deterministic probabilities perform poorly under the fixed policy.            | P7_ATTR_RAW                       |
| June common-policy PnL using static signal |  0.0235    |  nan       |  nan       |                        | Static local settlement correction closes the realised raw-to-Matérn trading gap. | P7_ATTR_STATIC                    |
| June common-policy PnL using Matérn signal |  0.0235    |  nan       |  nan       |                        | No incremental June PnL over static under the fixed policy.                       | P7_ATTR_MATERN                    |

The one-cent PnL point estimate is slightly positive but has a wide interval containing zero, reverses at modestly higher costs and is concentrated. Static correction accounts for the realised June raw-to-Matérn trading improvement under the fixed policy.

## Supported claims register

| claim_id   | domain               | status                          | safe_thesis_wording                                                                                                                                                            | prohibited_overstatement                                                                                                   |
|:-----------|:---------------------|:--------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------|
| C01        | settlement_error     | supported                       | The deterministic IFS local-day maximum exhibits a persistent cold discrepancy relative to the HKO settlement maximum.                                                         | Do not identify the discrepancy as a proven physical model bias or a single causal mechanism.                              |
| C02        | forecast_attribution | supported                       | Most of the distributional improvement is attributable to rule-specific local settlement correction, with a smaller increment from conditional Matérn GP structure.            | Do not claim that the GP is the dominant source of skill.                                                                  |
| C03        | information_arrival  | supported_with_scope            | Later forecasts modestly improve accuracy over the retained one-day decision window.                                                                                           | Do not claim that later information removes the structural settlement discrepancy or identify causal information channels. |
| C04        | calibration          | supported_with_limitation       | The selected predictive law is broadly useful but mildly underdispersed and retains serial and conditional-variance misspecification.                                          | Do not describe the Gaussian GP law as fully calibrated or conditionally well specified.                                   |
| C05        | market_comparison    | supported_on_june_exact_support | On the pre-designated June exact support, Polymarket has lower realised loss than the selected Matérn law under all four retained proper scores.                               | Do not claim universal market dominance outside the 30-date June external period.                                          |
| C06        | market_information   | supported_descriptively         | The market produces materially different probability books, shifts mass towards warmer-ranked outcomes and assigns more probability to the realised event in June.             | Do not assert which private information or causal mechanism generated the market advantage.                                |
| C07        | trading              | not_robust                      | The one-cent historical point estimate is slightly positive, but it is statistically uncertain, cost-sensitive and highly concentrated.                                        | Do not claim a persistent, scalable or executable trading edge.                                                            |
| C08        | trading_attribution  | supported_under_fixed_policy    | Under the fixed June policy, static settlement correction accounts for the realised raw-to-Matérn PnL improvement, while the Matérn refinement adds no incremental June PnL.   | Do not infer that Matérn has no forecasting value or no value under every trading rule.                                    |
| C09        | forecast_risk        | supported_as_stress_test        | Strategy PnL responds nonlinearly to predictive-mean shocks because contract selection and threshold activation are discrete.                                                  | Do not call the finite perturbation a globally smooth portfolio delta or a causal response to actual forecast releases.    |
| C10        | overall_contribution | supported                       | The contribution is a settlement-aware attribution framework linking local forecast correction, coherent event probabilities, market comparison and forecast-risk sensitivity. | Do not present the dissertation as proposing a new GP theorem or a profitable trading system.                              |

## Limitations register

| limitation_id   | area                 | status                     | evidence                                     | description                                                                                                                                                                                 | required_thesis_action                                                                                      |
|:----------------|:---------------------|:---------------------------|:---------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------|
| L01             | market_timing        | unavailable                | P6_MARKET_AGE_STATUS                         | Selected market-record timestamps are absent from the retained exact-support panels, so book-age and stale-record sensitivity cannot be reported without a separate data-recovery exercise. | State the limitation; do not fabricate contemporaneity or execution claims.                                 |
| L02             | market_period_hko    | unavailable                | phase7_market_period_hko_availability.csv    | Exact market-period HKO temperatures are unavailable in the current Phase 7 evidence path.                                                                                                  | Do not report exact temperature-error-to-PnL regressions; retain probability and PnL perturbation analysis. |
| L03             | dependence           | remaining_misspecification | P5_LAG1_Z|P5_LAG1_Z2                         | Residual and squared-residual serial dependence remains.                                                                                                                                    | Use date and moving-block uncertainty and avoid IID claims.                                                 |
| L04             | conditional_variance | remaining_misspecification | P5_VARIANCE_WALD                             | The observation-noise variance is homoskedastic within each rule, while diagnostics indicate conditional variance structure.                                                                | Describe the selected GP as a useful approximation, not a fully specified conditional law.                  |
| L05             | external_sample      | small_sample               | 30 June settlement dates                     | The external market and trading conclusions rely on 30 June dates.                                                                                                                          | Emphasise uncertainty and avoid universal generalisation.                                                   |
| L06             | execution            | not_observed               | historical market records                    | Bid-ask spread, depth, fill probability, market impact and fees beyond the stylised per-trade cost are not observed.                                                                        | Describe the backtest as a reduced-form historical decision evaluation, not an executable strategy.         |
| L07             | forecast_source      | interface_dependency       | Open-Meteo Single Runs delivery of ECMWF IFS | The deterministic IFS path is obtained through a third-party historical delivery interface rather than a direct ECMWF archive.                                                              | Document source lineage and avoid claiming direct ENS or AIFS archive access.                               |
| L08             | support              | exact_support_restriction  | 375 supported keys and 350 complete books    | Thirty-seven theoretical market date-rule keys lack certified forecast support and are not imputed.                                                                                         | Report exact-support counts and preserve the no-imputation rule.                                            |
| L09             | causality            | descriptive_only           | Phase 3 and Phase 6 transition analyses      | Observed forecast and market revisions do not identify causal forecast-release effects.                                                                                                     | Use descriptive information-arrival language.                                                               |

## Figure shortlist

| phase   | source_path                                                                                                               | destination_path                               | exists   | placement                 | purpose                                                                | sha256                                                           |
|:--------|:--------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------|:---------|:--------------------------|:-----------------------------------------------------------------------|:-----------------------------------------------------------------|
| phase2  | outputs/v70_empirical_finalisation/phase2_settlement_error/figures/phase2_figure_residual_histogram_gaussian.pdf          | figures/phase8_residual_distribution.pdf       | True     | appendix_or_main_if_space | Show the systematic settlement discrepancy and Gaussian approximation. | 663fac4017510ead78c405bae2e957d6299985cba15fdfb8e51beb0ead015f4d |
| phase4  | outputs/v70_empirical_finalisation/phase4_forecast_attribution/figures/phase4_figure_incremental_attribution.pdf          | figures/phase8_forecast_attribution.pdf        | True     | main                      | Show the dominant raw-to-static gain and smaller GP increments.        | c8a6a583fa7cbb2e2583e8bc11dcd250aef41c208caea12becefc68842569115 |
| phase5  | outputs/v70_empirical_finalisation/phase5_calibration_misspecification/figures/phase5_figure_selected_matern_coverage.pdf | figures/phase8_predictive_coverage.pdf         | True     | appendix_or_main_if_space | Show mild undercoverage of the selected predictive law.                | 5f57b5e41d65b3bff9a7b1a290ad522b4a0c87f0ffb7b25943a65cc540c64679 |
| phase6  | outputs/v70_empirical_finalisation/phase6_market_information/figures/phase6_figure_realised_probability_scatter.pdf       | figures/phase8_market_realised_probability.pdf | True     | main                      | Show how the market and Matérn law differ on realised-event mass.      | b4cd46cfcb6a6b6c34d2239a23fd7c8378f2f99947a85717673509badeb3ee6d |
| phase6  | outputs/v70_empirical_finalisation/phase6_market_information/figures/phase6_figure_total_variation_by_rule.pdf            | figures/phase8_market_total_variation.pdf      | True     | appendix                  | Show material probability-book disagreement across decision rules.     | 2029316e6a1461c024bd4c0a1101014f99d5cc7da96753b08a96d7b59ea16326 |
| phase7  | outputs/v70_empirical_finalisation/phase7_trading_sensitivity/figures/phase7_figure_mean_shift_pnl_sensitivity.pdf        | figures/phase8_mean_shift_pnl_sensitivity.pdf  | True     | main                      | Show Wei Pan's delta-like forecast-to-PnL sensitivity.                 | f718514c010f78e27f3fcf15352a7c517a9f197fcd693d709b6c20a0e8609e1d |
| phase7  | outputs/v70_empirical_finalisation/phase7_trading_sensitivity/figures/phase7_figure_june_trade_waterfall.pdf              | figures/phase8_june_trade_concentration.pdf    | True     | appendix                  | Show the concentration and fragility of the June PnL.                  | ef82e9eb468bc16b3c74af9779ca1c8b3a418f29e59e49898e6859543aae58e2 |

## Final empirical conclusion

The deterministic global forecast exhibits a substantial and persistent mismatch with the local HKO settlement quantity. A simple rule-specific Gaussian correction removes most of the distributional loss, while conditional Matérn GP structure adds a smaller but supported refinement. Polymarket remains stronger on the June exact-support event-book comparison. The mapping from forecast improvement to trading performance is nonlinear, cost-sensitive and insufficient to establish a robust executable edge.
