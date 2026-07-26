# 18wA coherent contract-event probability mapping

**PASS**

Each predictive distribution is mapped using 99 equally weighted HKO quantile particles. Every particle belongs to exactly one certified event and every model book sums to one.

## Development uncalibrated scores

| Candidate | Books | Categorical log | Multiclass Brier | Zero winner probabilities |
|---|---:|---:|---:|---:|
| catboost_quantile_pooled | 136 | 9.017854 | 0.829272 | 44 |
| gp_matern32_rule | 136 | 2.292783 | 0.777329 | 4 |
| pooled_empirical_residual | 136 | 2.238408 | 0.751244 | 4 |

The blind probability panel contains no realised outcome or market variable.
