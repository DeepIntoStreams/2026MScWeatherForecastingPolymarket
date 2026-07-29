# START HERE: Version 2 Thesis-Writing Handover

## Status

PASSED

## Authoritative reading order

1. `phase23_final_freeze/phase23_thesis_handover.md`
2. `phase22_thesis_evidence_pack/phase22_empirical_instruction_book.md`
3. `phase23_final_freeze/phase23_frozen_key_metrics.csv`
4. `phase23_final_freeze/phase23_validation_checks.csv`
5. `phase23_final_freeze/phase23_frozen_file_inventory.csv`

## Final identifiers

- Branch: `edward-v2-gp-depth-completion`
- Empirical freeze commit: `1b0900086c315588b0dc41225e41c2b5f2189bfa`
- Empirical freeze tag: `v2-empirical-complete`
- Phase 23 checks: 13 passed
- Frozen key metrics: 23
- Closed empirical gaps: G01-G17
- Open empirical gaps: 0

## Central thesis focus

The main contribution is the rigorous conversion of deterministic IFS daily-maximum forecasts into local probabilistic forecasts using rule-specific static Gaussian correction and Gaussian process regression. CatBoost and broad machine-learning ensembles remain secondary and must not dilute the central mathematical argument.

## Final empirical story

1. The deterministic forecast contains substantial systematic local error.
2. Static Gaussian correction materially improves the raw point forecast.
3. The Matern-3/2 GP improves further in aggregate and across all four decision rules, but not in every chronological block.
4. Calibration remains imperfect, with undercoverage, serial dependence and remaining conditional-variance structure.
5. On June exact common support, Polymarket outperforms the weather-only GP.
6. The development-selected convex pool improves on the GP but not on the market.
7. The evidence does not establish live arbitrage, model dominance or causal private information.

## Mandatory boundaries

- Preserve chronological separation and exact common support.
- Use target date as the uncertainty unit.
- Do not impute missing forecasts or market prices.
- Do not tune on June outcomes.
- Do not alter frozen metrics.
- Do not claim GP dominance over Polymarket.
- Do not claim the pool dominates both inputs.
- Do not restore CatBoost as a major thesis strand.
