# Final empirical evidence handoff

This document is generated from the frozen March–August empirical pipeline.
It is a writing aid, not an additional empirical model.

## Frozen upstream choices

- Selected weather kernel: `matern32`.
- Development-selected pool: GP weight `0.188`, market weight `0.812`.
- Trading probability signal: selected GP minus raw event-level Polymarket YES value.
- Frozen trading rule: `24h_prior`.
- Frozen trading threshold: `0.15`.
- Reference cost: `0.01` per executed long-YES share.
- July–August information was not used for weather-kernel, pool or trading-policy selection.

## Core empirical narrative

1. **Most weather-model improvement comes from probabilistic conversion.**
   The static Gaussian captures `95.8%` of the raw-to-selected-GP CRPS improvement.

2. **The same pattern survives at the probability-book level.**
   On external July–August total variation, the static correction captures
   `100.4%` of the raw-to-GP improvement. A value above
   100% means the static book is slightly closer to Polymarket than the GP book.

3. **The market still contains complementary information.**
   The convex pool uses only `18.8%` GP and
   `81.2%` market weight. The pool has the best
   external proper-score point estimates, but the pool–market advantage is
   not statistically resolved.

4. **The economic attribution is consistent with the forecasting attribution.**
   External fixed-policy net PnL is `-0.298` for raw,
   `2.281` for static and
   `2.451` for the selected GP. The static
   correction therefore accounts for `93.8%` of the
   raw-to-GP PnL improvement.

5. **The frozen GP policy is positive in point estimate but inference must be qualified.**
   It executes `12` trades over
   `60` currently settled external dates,
   producing net PnL `2.451` and non-annualised
   settlement-date Sharpe `0.194`.
   The ordinary bootstrap interval is
   `[-0.381, 6.161]`;
   the block-7 interval is
   `[0.302, 5.162]`.
   This is classified as `dependence_sensitive`.

6. **Rule selection has a support-composition caveat.**
   The prespecified procedure selects `24h_prior` on its own
   complete support, while the common-date diagnostic favours
   `12h_prior`. The frozen policy is not changed.

7. **PnL is concentrated, but not entirely in one winning trade.**
   After removing the largest positive trade, external net PnL is
   `1.472`; after removing the two
   largest positive trades it is `0.527`.

8. **Forecast-risk transmission is nonlinear.**
   Smooth Gaussian probability sensitivities interact with event boundaries,
   argmax contract choice and the threshold activation rule. Portfolio finite
   slopes therefore vary with perturbation size and must not be interpreted as
   one global classical delta.

## Writing discipline

Main text should prioritise:

- raw → static → GP attribution;
- market complementarity and the development-selected pool;
- external fixed-policy attribution;
- non-annualised volatility-adjusted performance;
- ordinary versus block-bootstrap disagreement;
- nonlinear forecast-error → probability → decision → PnL transmission;
- the support-composition caveat.

Appendix material should contain:

- full threshold-neighbourhood grid;
- July/August month split;
- leave-one-trade-out concentration;
- full cost grid;
- complete perturbation grid;
- PIT/QQ/coverage diagnostics;
- exploratory Spearman table.

Do not make primary claims from:

- sqrt(365)-scaled Sharpe;
- return on entry cash;
- unadjusted exploratory correlation p-values;
- any external threshold that looks better than the frozen 0.15 threshold;
- the common-support 12h diagnostic as a replacement policy.

## Current 31 August status

`PENDING_EXTERNAL_TARGET`

Pending dates: `['2026-08-31']`.

When the official target is available, update the target and rerun downstream
scores/trading/synthesis. Do not reselect the weather kernel, pool weight,
decision rule or threshold.
