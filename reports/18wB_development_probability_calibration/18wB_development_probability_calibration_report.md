# 18wB development-only probability calibration

**PASS**

## Selected parameters

| Candidate | Scale | Uniform smoothing | Development log | Development Brier |
|---|---:|---:|---:|---:|
| catboost_quantile_pooled | 2.00 | 0.100 | 1.625374 | 0.747230 |
| gp_matern32_rule | 1.50 | 0.000 | 1.542982 | 0.749762 |
| pooled_empirical_residual | 1.25 | 0.000 | 1.522599 | 0.740922 |

All parameters were fitted and selected using the common development OOF support only. No holdout, June or market outcome was loaded.
