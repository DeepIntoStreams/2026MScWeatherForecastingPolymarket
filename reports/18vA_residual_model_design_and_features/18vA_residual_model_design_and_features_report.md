# 18vA residual-model design and features

**PASS**

## Candidate set

| Candidate | Family | Scope | Distribution |
|---|---|---|---|
| raw_deterministic | RAW | POOLED | DEGENERATE |
| pooled_mean_residual | BASELINE | POOLED | DEGENERATE |
| rule_mean_residual | BASELINE | RULE_SPECIFIC | DEGENERATE |
| pooled_empirical_residual | BASELINE | POOLED | EMPIRICAL_QUANTILES |
| rule_empirical_residual | BASELINE | RULE_SPECIFIC | EMPIRICAL_QUANTILES |
| gp_rbf_rule | GAUSSIAN_PROCESS | RULE_SPECIFIC | GAUSSIAN_QUANTILES |
| gp_matern32_rule | GAUSSIAN_PROCESS | RULE_SPECIFIC | GAUSSIAN_QUANTILES |
| catboost_quantile_pooled | TREE | POOLED | INTERPOLATED_QUANTILES |
| catboost_quantile_rule | TREE | RULE_SPECIFIC | INTERPOLATED_QUANTILES |

## Frozen panels

- Development labelled date-rule rows: 144
- Blind internal-holdout rows: 40
- Blind external rows: 119

## Selection hierarchy

Primary: date-balanced mean CRPS on the common freeze-admissible development OOF support.
Secondary: date-balanced mean absolute error. Tertiary: lower pre-frozen complexity rank.

## Exclusions

No market, artificial ensemble or fixed Gaussian bridge feature is used. Holdout and external outcomes are absent from the blind feature panel.
