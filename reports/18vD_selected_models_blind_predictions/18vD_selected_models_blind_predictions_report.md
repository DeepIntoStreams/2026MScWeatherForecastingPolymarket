# 18vD selected-model blind predictions

**PASS**

## Selected candidates

| Candidate | Family | Scope | Roles |
|---|---|---|---|
| catboost_quantile_pooled | TREE | POOLED | selected_tree |
| gp_matern32_rule | GAUSSIAN_PROCESS | RULE_SPECIFIC | selected_gaussian_process |
| pooled_empirical_residual | BASELINE | POOLED | selected_baseline|selected_overall |

## Blind prediction support

- Total candidate-date-rule predictions: 477
- Internal holdout rows per candidate: 40
- June external rows per candidate: 119

## Leakage boundary

The output contains no realised HKO outcome, realised residual, contract outcome or market field.
June uses the identical pre-holdout fit; there is no refit on internal-holdout labels.

Contract-event probability mapping and holdout/June scoring remain pending.
