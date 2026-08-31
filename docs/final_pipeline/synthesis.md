# Final robustness and empirical-synthesis stage

## Purpose

Steps 56–70 do not introduce a new forecast model or trading strategy.

The upstream weather, market and trading procedures are frozen before this
stage begins.

The purpose is to distinguish:

1. core findings that remain stable across the empirical chain;
2. robustness diagnostics that should be disclosed;
3. exploratory findings that belong only in an appendix;
4. quantities that should not be promoted as primary thesis claims.

## Step 56 — decision-rule support composition

The primary trading policy is not reselected.

The prespecified selection procedure uses each rule's own complete
development support.

A separate diagnostic compares the four rules on the intersection of dates
where all four decision-rule books are available.

If this diagnostic favours a different rule, the difference is treated as a
support-composition caveat rather than a reason to revise the frozen policy.

## Step 57 — external threshold neighbourhood

For the already selected GP contract on each external date, the activation
threshold is varied descriptively over the original threshold grid.

This is not an external re-optimisation.

The frozen threshold remains 0.15 regardless of which external threshold has
the highest realised PnL.

## Step 58 — July/August stability

The frozen raw, static and GP ledgers are summarised separately for July and
August.

No monthly parameter or threshold is selected.

## Step 59 — concentration

The external GP result is subjected to:

- leave-one-executed-trade-out accounting;
- sequential removal of the largest positive trades.

These diagnostics disclose whether the headline PnL is dependent on one or
two unusually successful positions.

## Step 60 — bootstrap interpretation

Ordinary date and seven-date circular-block bootstrap intervals are placed
side by side.

A finding is labelled:

- positive under both;
- negative under both;
- dependence-sensitive;
- unresolved.

The classification is descriptive and does not manufacture a single
preferred inferential answer.

## Step 61 — cost robustness

The existing implementation-cost experiment is summarised.

The one-cent reference cost remains the baseline.

The gross-PnL break-even cost is a reduced-form diagnostic and is not an
estimate of historical executable bid/ask cost or trading capacity.

## Step 62 — forecast-risk synthesis

The existing analytical probability delta/gamma, predictive-mean stress,
finite portfolio slopes, forecast-error bins and exploratory Spearman
associations are consolidated.

No additional PnL regression is fitted.

Nominal exploratory p-values are not treated as multiple-testing-adjusted
confirmatory evidence.

## Step 63 — development/external stability

Development and external values are placed side by side for:

- total-variation gap closure;
- proper scores;
- fixed-policy PnL and volatility-adjusted performance.

This is a stability description rather than another model-selection stage.

## Step 64 — cross-stage attribution

The raw/static/selected-GP sequence is compared across three distinct layers:

1. continuous weather CRPS;
2. weather-to-market total variation;
3. fixed-policy net PnL.

The statistic

    static share of raw-to-GP improvement

is calculated with the metric's natural direction.

Values near one mean that the simpler static probabilistic correction
captures most of the improvement associated with moving from the raw
deterministic forecast to the selected GP.

Values above one mean that the static correction slightly exceeds the GP on
that particular metric.

The statistic is an attribution ratio, not a causal decomposition.

## Steps 65–67 — thesis evidence control

One authoritative result ledger records the headline numbers and source
files.

A second evidence register determines whether a finding is recommended for:

- main text;
- appendix;
- discussion/caveat;
- or not as a primary claim.

A figure/table manifest prevents the final thesis from becoming overloaded
with diagnostics that add little to the core argument.

## Step 68 — 31 August refresh gate

The unresolved 31 August HKO outcome is treated as a pending external target.

When it becomes available, only target-dependent external metrics may
change.

The following remain frozen:

- selected GP kernel;
- March–June pool weight;
- selected trading rule;
- selected trading threshold;
- reference trading cost;
- event definitions and timing rules.

## Step 69 — reproducibility manifest

Critical source, configuration and output files are hashed with SHA-256.

The final packaging stage will later add final Git/tag metadata.

## Step 70 — acceptance gate

The synthesis stage passes only if:

- all three upstream empirical stages pass;
- frozen selections are unchanged;
- diagnostic recalculations reconcile exactly with upstream totals;
- all required reproducibility files exist;
- external diagnostics have not replaced the frozen development policy.
