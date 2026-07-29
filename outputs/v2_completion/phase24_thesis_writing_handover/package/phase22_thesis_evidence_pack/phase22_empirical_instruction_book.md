# Version 2 Empirical Evidence Instruction Book

## Purpose

This document is the thesis-writing handover for the completed Version 2
empirical programme. It is deliberately more detailed than the final
dissertation should be. The Overleaf-writing workflow should select the most
important results and arguments while preserving the definitions, support
restrictions, chronology and evidential boundaries recorded here.

The empirical completion source commit is `c5150fdd576f3757fcd374307367d19503fe9de9` on branch
`edward-v2-gp-depth-completion`.

## Central research question and approved scope

The central empirical question is whether deterministic IFS weather forecasts
for the Hong Kong settlement target can be converted into useful local
probabilistic forecasts through rigorous residual post-processing, especially a
Gaussian process, and how those probabilities compare with Polymarket prices.

The main thesis should therefore focus on:

1. deterministic forecast and settlement-target alignment;
2. local deterministic error and the static Gaussian benchmark;
3. rigorous Gaussian-process construction;
4. chronological predictive validation and proper scoring;
5. calibration, sharpness, dependence and conditional-variance diagnostics;
6. exact-common-support comparison with Polymarket;
7. a low-dimensional, development-selected forecast-combination test;
8. cautious economic interpretation and reproducibility.

CatBoost and broad AI-ensemble material should not return as parallel central
methodologies. They may remain as short contextual comparisons, deferred
extensions or appendix material only when they directly clarify the chosen GP
design.

## Recommended thesis narrative

### Stage 1: define the target and information sets

Define the HKO daily maximum settlement target, canonical interval contract
book, decision rules and chronological information cutoff. Explain why a
deterministic daily maximum is not itself a contract probability.

### Stage 2: establish the deterministic forecasting problem

Report the positive HKO-minus-forecast error and the rule-level summaries from
Phase 17. Explain that target-date variation accounts for
91.9340%
of deterministic-error sum of squares. This motivates local correction but also
shows that the rule label alone explains little of the total error.

### Stage 3: introduce the static Gaussian benchmark

The static model is not optional. It answers whether the GP improves beyond a
simple rule-specific local mean-and-scale correction. Under chronological
validation, mean date CRPS falls from
1.745684932 for the raw point
forecast to 0.911754550
for the static Gaussian.

### Stage 4: specify the GP mathematically and computationally

Use the exact Phase 15 feature equations, scaling maps, response transformation,
kernel decomposition, observation-noise convention and Gaussian CRPS formula.
The code-to-mathematics reconciliation should support the derivation rather than
sit as an implementation anecdote.

### Stage 5: demonstrate incremental GP value

The Matern-3/2 mean date CRPS is
0.863339999, compared with
0.911754550 for the
static benchmark and 0.877561468
for the RBF GP. The paired Matern-minus-static difference is
-0.048414551.

Do not stop at the aggregate result. Phase 18 shows improvement over the static
benchmark in all four decision rules but only three of four chronological
blocks. State explicitly that the first block reverses the aggregate ordering.

### Stage 6: assess predictive adequacy

Use Phase 19 to distinguish lower CRPS from full calibration. Discuss central
coverage, quantile reliability, PIT shape, standardised residual moments,
serial dependence and the auxiliary conditional-variance regression. The
Matern model is preferable to RBF but still under-covers and retains dependence
and conditional scale structure.

### Stage 7: compare with the market on exact common support

State the complete support arithmetic before presenting scores:

- 103 settlement and market dates;
- 412 theoretical date-rule keys;
- 375 supported keys across 102 dates;
- 37 unsupported keys;
- 97 exact-common-support dates;
- 350 complete date-rule books;
- 3,850 contract-event rows;
- 67 development dates;
- 30 June dates.

No missing forecast or market probability is imputed.

### Stage 8: report forecast combination as a test, not a rescue device

The selected development-period pool assigns GP weight
0.489 and market weight
0.511. The pool
improves on the GP in June but loses to the market. The June oracle GP weight is
0.000. The correct
interpretation is that apparent development-period complementarity did not
translate into robust June improvement beyond the market.

### Stage 9: conclude with disciplined negative evidence

The weather-only GP is a successful post-processing model relative to raw and
static weather benchmarks. It is not superior to Polymarket on June exact common
support, and the combined forecast does not improve on the market. This is an
interesting and defensible result because the thesis explains where the GP adds
value, where it fails, and what the market appears to add.

## Methodology-writing requirements

The methodology chapter should define every object before use:

- target date and decision rule;
- deterministic forecast and realised HKO outcome;
- residual response;
- four-dimensional feature vector;
- affine feature transformation;
- static Gaussian law;
- GP prior and covariance kernel;
- observation-noise term;
- posterior predictive mean and variance;
- Gaussian CRPS;
- interval-event probability;
- binary and categorical proper scores;
- date-level aggregation;
- exact-common-support restriction;
- convex probability pool and development objective.

For each retained method, include:

1. mathematical definition;
2. information set and chronology;
3. assumptions;
4. estimation rule;
5. prediction rule;
6. score or diagnostic;
7. implementation reconciliation;
8. rationale for inclusion;
9. limitation relevant to interpretation.

## Results-writing requirements

The results chapter should be ordered by inferential dependence:

1. support and sample accounting;
2. deterministic error;
3. raw and static benchmarks;
4. GP aggregate comparison;
5. rule and block stability;
6. predictive diagnostics;
7. market comparison;
8. combination;
9. trading evidence;
10. reproducibility.

Do not mix method definitions into the results except for a short reminder of
the quantity being reported. Do not present large registries or every diagnostic
table in the main text.

## Discussion-writing requirements

The discussion should answer the following questions directly.

### Does the GP outperform simple local correction?

Yes in aggregate, by rule and in three of four blocks. The first validation
block is a documented reversal, so the advantage is not temporally uniform.

### Why is the static benchmark important?

It separates simple local bias-and-scale correction from nonlinear conditional
residual modelling. Without it, the GP contribution is overstated.

### Are the GP probabilities fully calibrated?

No. Matern improves CRPS and quantile calibration relative to RBF, but central
undercoverage, lag dependence and remaining conditional variance structure
remain.

### Why does Polymarket outperform the GP?

The market may incorporate newer, alternative or judgemental information absent
from the weather-only features. The data identify systematic disagreement, not
its causal source.

### Does forecast combination demonstrate complementarity?

Not robustly in June. The pool improves on the GP but not the market, and the
June oracle gives the GP zero weight.

### Does the trading simulation establish arbitrage?

No. It is a frozen historical diagnostic with weak uncertainty support and
material execution omissions.

## Main-text table plan

Use a small number of synthesised tables:

1. sample and support accounting;
2. deterministic error by rule;
3. raw, static, RBF and Matern CRPS comparison;
4. Matern-minus-static by rule and block;
5. selected predictive diagnostics;
6. June GP, market and pooled proper scores;
7. evidential boundaries or robustness summary, if space permits.

The complete table inventory is in `phase22_table_inventory.csv`.

## Figure plan

Prefer figures that reveal structure not already obvious from a table:

1. benchmark/model CRPS comparison;
2. rule-by-block Matern improvement;
3. calibration or coverage curve;
4. residual autocorrelation or PIT diagnostic;
5. GP-market discrepancy or combination-weight profile.

Missing-support matrices and large hyperparameter diagnostics normally belong in
the appendix. The complete figure inventory is in
`phase22_figure_inventory.csv`.

## Claims that must not appear

Do not claim:

- that the GP dominates Polymarket;
- that the pool dominates both inputs;
- that GP-market discrepancy proves private information;
- that missing forecasts are missing at random;
- that the value-gap strategy is live-executable arbitrage;
- that nominal row-level p-values are definitive;
- that the Matern advantage is uniform through time;
- that CatBoost or broad AI ensembles are central completed contributions;
- that the empirical results generalise beyond the target, archive and period
  without qualification.

## Reproducibility statement

Phase 21 replays Phases 15-20 in a clean temporary clone and environment. It
compares 116 artifacts, all of which pass, with maximum finite numerical error
zero. Cite `phase22_reproducibility_summary.csv`, the Phase 21 report and the
artifact-comparison registry.

## Final writing rule

Every prominent numerical claim in the thesis should be traceable to
`phase22_key_metrics.csv`, a certified phase report, or a named table in the
source inventory. Every limitation should be linked to
`phase22_evidential_boundaries.csv`. The final dissertation should be shorter
than this instruction book, but it must not be less precise.
