# 18wD locked holdout and June probability evaluation

**PASS**

## Model-only support

| Block | Books per candidate and variant |
|---|---:|
| Internal holdout | 40 |
| June external test | 119 |

## Exact market-common support

| Block | Books | Contract rows |
|---|---:|---:|
| Internal holdout | 40 | 440 |
| June external test | 114 | 1,254 |

## Exact-common categorical scores

| Candidate | Variant | Block | Model log | Market log | Model minus market | Model Brier | Market Brier |
|---|---|---|---:|---:|---:|---:|---:|
| catboost_quantile_pooled | CALIBRATED | EXTERNAL_TEST | 3.203871 | 1.260923 | 1.942949 | 1.081487 | 0.648471 |
| catboost_quantile_pooled | CALIBRATED | INTERNAL_HOLDOUT | 3.548893 | 1.091350 | 2.457544 | 1.081541 | 0.585087 |
| catboost_quantile_pooled | UNCALIBRATED | EXTERNAL_TEST | 21.846419 | 1.260923 | 20.585496 | 1.449981 | 0.648471 |
| catboost_quantile_pooled | UNCALIBRATED | INTERNAL_HOLDOUT | 24.289809 | 1.091350 | 23.198459 | 1.403204 | 0.585087 |
| gp_matern32_rule | CALIBRATED | EXTERNAL_TEST | 1.615497 | 1.260923 | 0.354574 | 0.750062 | 0.648471 |
| gp_matern32_rule | CALIBRATED | INTERNAL_HOLDOUT | 1.240250 | 1.091350 | 0.148900 | 0.616519 | 0.585087 |
| gp_matern32_rule | UNCALIBRATED | EXTERNAL_TEST | 2.076144 | 1.260923 | 0.815221 | 0.728580 | 0.648471 |
| gp_matern32_rule | UNCALIBRATED | INTERNAL_HOLDOUT | 1.063872 | 1.091350 | -0.027477 | 0.575212 | 0.585087 |
| pooled_empirical_residual | CALIBRATED | EXTERNAL_TEST | 1.893650 | 1.260923 | 0.632727 | 0.726371 | 0.648471 |
| pooled_empirical_residual | CALIBRATED | INTERNAL_HOLDOUT | 1.133471 | 1.091350 | 0.042122 | 0.583328 | 0.585087 |
| pooled_empirical_residual | UNCALIBRATED | EXTERNAL_TEST | 1.878778 | 1.260923 | 0.617855 | 0.726545 | 0.648471 |
| pooled_empirical_residual | UNCALIBRATED | INTERNAL_HOLDOUT | 1.020407 | 1.091350 | -0.070943 | 0.549168 | 0.585087 |

## Figures

Eight thesis-ready figures use concise labels and separate internal-holdout and June panels. Restricted categorical-log axes retain annotated actual values for CatBoost outliers.

The mechanically outcome-blind 18wA-C chain and its source inventories were verified before outcomes or market information were loaded. Trading remains deferred.
