# Final Empirical Handover for Thesis Writing

## Authoritative writing source

Use:

`outputs/v2_completion/phase22_thesis_evidence_pack/phase22_empirical_instruction_book.md`

as the detailed empirical instruction book.

Use:

`outputs/v2_completion/phase23_final_freeze/phase23_frozen_key_metrics.csv`

for final headline values and:

`outputs/v2_completion/phase23_final_freeze/phase23_frozen_file_inventory.csv`

for exact source tracing.

## Final thesis story

The study converts deterministic IFS daily-maximum forecasts into local
probabilistic forecasts for Hong Kong temperature contracts. A rule-specific
static Gaussian benchmark isolates simple local bias-and-scale correction. A
Matern-3/2 GP then models conditional residual structure and improves on that
benchmark in aggregate and across all four decision rules, though not in every
chronological block.

Predictive diagnostics show that the GP is useful rather than fully adequate:
undercoverage, serial dependence and remaining conditional-variance structure
persist. On June exact common support, Polymarket outperforms the weather-only
GP. A development-selected convex pool improves on the GP but not the market.
This supports a careful conclusion about model value, limitations and market
information rather than a claim of forecast or trading dominance.

## Mandatory boundaries

- Do not impute missing forecasts or market prices.
- Do not use June outcomes for model, kernel, combination-weight or trading-rule
  selection.
- Do not treat four decision rules on one date as independent weather outcomes.
- Do not claim the GP dominates Polymarket.
- Do not claim the convex pool dominates both inputs.
- Do not infer causal private information from GP-market disagreement.
- Do not claim live-executable arbitrage.
- Do not restore CatBoost or broad ensemble modelling as a central contribution.

## Reproducibility sentence

A clean-environment replay regenerated Phases 15-20 and compared 116 artifacts,
all of which passed, with zero maximum finite numerical discrepancy.

## Final release identifiers

- Source branch before the Phase 23 commit: `edward-v2-gp-depth-completion`.
- Phase 22 source commit: `45e9e51300e53bb2e0b637085d41650041e95cde`.
- Intended final annotated tag: `v2-empirical-complete`.
