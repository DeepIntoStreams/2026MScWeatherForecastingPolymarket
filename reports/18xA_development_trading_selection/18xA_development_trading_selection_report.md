# 18xA development-frozen trading strategy selection

**PASS**

The observed pre-cutoff YES price is a fill proxy rather than a contemporaneous bid or ask. The strategy buys one YES share in the highest-edge contract of a complete eleven-contract book.

| Role | Candidate | Variant | Rule | Threshold | Development net PnL at 0.01 cost |
|---|---|---|---|---:|---:|
| GAUSSIAN_PROCESS_FAMILY | gp_matern32_rule | CALIBRATED | 24h_prior | 0.08 | 4.1825 |
| PRIMARY_OVERALL | pooled_empirical_residual | CALIBRATED | event_day_open | 0.08 | 7.1200 |
| TREE_FAMILY | catboost_quantile_pooled | CALIBRATED | 12h_prior | 0.04 | 4.9580 |
