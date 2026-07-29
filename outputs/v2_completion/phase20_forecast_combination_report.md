# Phase 20 Forecast Combination and GP-Market Discrepancy

## Status

PASSED

## Purpose

Phase 10 deliberately compared the weather-only GP and Polymarket as separate information sources. It did not estimate a model-market combination because no development-only weight-selection protocol had yet been defined. Phase 20 closes that gap by defining a coherent convex probability pool, selecting its single weight only on the March-May weather-plus-market development period, and evaluating the fixed pool on June.

The phase also studies the structure of GP-market disagreement rather than treating the proper-score difference as a single number.

## Certified support

- Exact-common-support dates: 97.
- Complete date-rule books: 350.
- Contract-event rows: 3850.
- Development dates used for weight selection: 67.
- June out-of-sample dates: 30.
- No missing GP forecast, market price or contract event was imputed.
- The GP models remain fixed; market prices never enter GP fitting.

## Forecast-combination definition

For contract event j in a complete date-rule book, the pooled probability is

`q_j(w) = w p_GP,j + (1-w) p_market,j`,

where both input vectors are coherent complete-book probability distributions and `w` lies in `[0,1]`. Convex pooling therefore preserves non-negativity and unit total probability mass.

The primary weight minimises development-period categorical log score on a 0.001 grid. Book scores are first averaged within target date and target dates then receive equal weight. June outcomes are excluded from weight selection.

## Selected combination weight

- Selected GP weight: 0.489.
- Selected market weight: 0.511.
- Bootstrap median GP weight: 0.484.
- Bootstrap 95% GP-weight interval: [0.148, 0.827].
- Post-hoc June oracle GP weight: 0.000. This value is diagnostic and was not used for the primary evaluation.

Rule-specific development optima are reported as diagnostics only. They are not combined into the primary June forecast because that would introduce four tuned weights into a relatively short development sample.

## June out-of-sample scores

| Model | Binary Brier | Binary log | Categorical log | Multiclass Brier |
|---|---|---|---|---|
| gp | 0.068198 | 0.225029 | 1.618265 | 0.750180 |
| market_normalised | 0.058952 | 0.186395 | 1.260923 | 0.648471 |
| equal_50_50_pool | 0.061991 | 0.200679 | 1.394333 | 0.681905 |
| development_selected_pool | 0.061890 | 0.200273 | 1.390610 | 0.680794 |
| june_oracle_pool_post_hoc | 0.058952 | 0.186395 | 1.260923 | 0.648471 |

These Phase 20 binary scores use the normalised market book distribution for all models so that the convex pool remains coherent. They are therefore not replacements for Phase 10's raw-price binary market scores.

## June paired differences for the development-selected pool

| Comparator | Metric | Pool minus comparator | 95% lower | 95% upper |
|---|---|---|---|---|
| gp | binary_brier | -0.006308 | -0.009011 | -0.003492 |
| gp | binary_log | -0.024757 | -0.033344 | -0.016094 |
| gp | categorical_log | -0.227655 | -0.308104 | -0.152393 |
| gp | multiclass_brier | -0.069386 | -0.098868 | -0.038782 |
| market_normalised | binary_brier | 0.002939 | 0.000302 | 0.005408 |
| market_normalised | binary_log | 0.013878 | 0.005988 | 0.020953 |
| market_normalised | categorical_log | 0.129687 | 0.060254 | 0.189087 |
| market_normalised | multiclass_brier | 0.032324 | 0.003127 | 0.059410 |

Every difference is the development-selected pool score minus the comparator score. Negative values favour the pool. Intervals resample complete June target dates 10,000 times.

## Systematic GP-market discrepancy

| Period | Metric | Mean | 95% lower | 95% upper |
|---|---|---|---|---|
| june_out_of_sample | expected_rank_shift_market_minus_gp | 0.474392 | 0.294679 | 0.652406 |
| weather_plus_market_development | expected_rank_shift_market_minus_gp | 0.414610 | 0.270052 | 0.556293 |
| june_out_of_sample | mode_disagreement | 0.616667 | 0.516667 | 0.716667 |
| weather_plus_market_development | mode_disagreement | 0.573383 | 0.485075 | 0.661692 |
| june_out_of_sample | realised_probability_difference_gp_minus_market | -0.094504 | -0.124450 | -0.063767 |
| weather_plus_market_development | realised_probability_difference_gp_minus_market | -0.030297 | -0.058477 | -0.002009 |
| june_out_of_sample | total_variation_distance | 0.278613 | 0.250773 | 0.306576 |
| weather_plus_market_development | total_variation_distance | 0.290671 | 0.270839 | 0.310696 |

Total-variation distance measures the fraction of probability mass that must be moved to transform one complete-book distribution into the other. Expected-rank shift is positive when Polymarket places relatively more probability on higher-temperature contracts than the GP. Mode disagreement records whether the two sources select different modal contracts. Realised-event probability difference is GP probability minus market probability on the eventual winning event.

Event-level summaries align every contract by signed rank relative to the GP modal contract. The centred log-ratio statistic measures relative market-versus-GP reallocation within the simplex and removes a common book-level normalisation term.

## Discrepancy regression

Two descriptive auxiliary regressions use expected-rank shift and total-variation distance as responses. Covariates comprise a June indicator, calendar time, decision-rule indicators and an available temperature-level measure. Covariance estimates cluster observations by target date. These regressions test whether disagreement varies systematically with observable book characteristics; they do not establish a causal market-information channel.

## Interpretation

The combination exercise answers whether the GP and market contain complementary out-of-sample information under a deliberately low-dimensional rule. A pooled forecast is supported only when its fixed June score improves on both inputs with economically and statistically meaningful paired differences. A development-period optimum alone is not evidence of complementarity.

The discrepancy analysis explains how the two distributions differ. In particular, signed rank and upper-mass shifts reveal whether the market systematically moves probability towards warmer or cooler contracts relative to the weather-only GP. This is directly relevant because the deterministic forecast exhibited a persistent local underforecasting bias before post-processing.

## Closed Phase 14 gaps

- G13: systematic GP-market discrepancy structure.
- G14: forecast combination.

## Evidential boundary

Phase 20 does not refit the GP, use June outcomes for weight selection, impute missing forecasts or market prices, or claim that Polymarket discrepancies causally identify private information. The primary pool has one globally selected weight. Rule-specific weights and the June oracle weight are explicitly post-hoc diagnostics. All comparisons use the exact complete-book intersection and date-level resampling.
