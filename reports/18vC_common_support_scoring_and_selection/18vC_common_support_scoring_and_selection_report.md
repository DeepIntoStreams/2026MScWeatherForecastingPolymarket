# 18vC common OOF scoring and selection

**PASS**

- Candidates: 9
- Common selection rows: 136
- Common selection dates: 36

## Candidate scores

| Rank | Candidate | Family | Scope | CRPS | MAE | RMSE | 80% coverage |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | pooled_empirical_residual | BASELINE | POOLED | 0.711253 | 1.001912 | 1.223199 | 0.652778 |
| 2 | rule_empirical_residual | BASELINE | RULE_SPECIFIC | 0.723767 | 0.995948 | 1.224350 | 0.638889 |
| 3 | gp_matern32_rule | GAUSSIAN_PROCESS | RULE_SPECIFIC | 0.740041 | 1.021607 | 1.252387 | 0.611111 |
| 4 | gp_rbf_rule | GAUSSIAN_PROCESS | RULE_SPECIFIC | 0.743968 | 1.028708 | 1.259107 | 0.618056 |
| 5 | catboost_quantile_pooled | TREE | POOLED | 0.759924 | 0.964574 | 1.237288 | 0.423611 |
| 6 | rule_mean_residual | BASELINE | RULE_SPECIFIC | 0.996357 | 0.996357 | 1.224671 | 0.000000 |
| 7 | pooled_mean_residual | BASELINE | POOLED | 1.002211 | 1.002211 | 1.223580 | 0.000000 |
| 8 | catboost_quantile_rule | TREE | RULE_SPECIFIC | 1.035653 | 1.126208 | 1.450308 | 0.104167 |
| 9 | raw_deterministic | RAW | POOLED | 1.849306 | 1.849306 | 2.102297 | 0.000000 |

## Development-only winners

- Baseline: pooled_empirical_residual
- Gaussian process: gp_matern32_rule
- Tree: catboost_quantile_pooled
- Overall: pooled_empirical_residual

The common-candidate OOF support is now frozen. No holdout or external outcome was used.
