# 18yA final empirical synthesis

**PASS**

## Release-chain audit

- Verified upstream release stages: 18
- Verified upstream manifest entries: 234
- Verified upstream integrity checks: 193
- Upstream issue rows: 0

## Final sample

- Certified settlement dates: 103
- Certified contracts: 1,133
- Exact market-weather common rows: 3,889
- Complete common-support books: 350

## Model selection

- Overall and baseline winner: pooled_empirical_residual
- Gaussian-process winner: gp_matern32_rule
- Tree winner: catboost_quantile_pooled
- Empirical CRPS reduction relative to raw forecast: 61.5%

## Probability evaluation

- Holdout empirical uncalibrated categorical log: 1.020407
- Holdout normalised-market categorical log: 1.091350
- June normalised-market categorical log: 1.260923
- June best model categorical log: 1.615497 (Matérn-3/2 GP (Calibrated))

## Trading evaluation

- Primary holdout net PnL: 0.2625
- Primary June net PnL: -1.4925
- Primary holdout maximum drawdown: -0.5725
- Primary June maximum drawdown: -1.4925

## Evidential boundary

The ten-date holdout is descriptive. June is the principal external out-of-time block. No model, calibration or trading selection is rerun in 18yA.
