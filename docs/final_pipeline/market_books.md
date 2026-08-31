# Final Polymarket event-book and probability-comparison stage

## Scope

This stage begins only after the weather model has been selected and frozen.

It performs:

1. Polymarket market discovery;
2. contract-event certification;
3. official HKO target construction;
4. historical YES-token price recovery;
5. four no-look-ahead decision snapshots;
6. market-only scoring;
7. weather-distribution to event-probability mapping;
8. exact common-support construction;
9. proper-score comparison;
10. total-variation reconciliation;
11. development-only convex-pool selection;
12. external July-August evaluation;
13. settlement-date paired inference.

No trading policy is selected here.

## Contract-event convention

Each certified HKO book contains eleven mutually exclusive events:

- lower endpoint:
  `k°C or below` -> `(-infinity, k+1)`;
- interior:
  `k°C` -> `[k,k+1)`;
- upper tail:
  `K°C or higher` -> `[K,infinity)`.

The HKO one-decimal value is used directly.

There is no nearest-integer rounding.

Contract date is parsed from visible market slug/question/event metadata.
The Gamma closing or resolution date is not treated as the contract date.

The Celsius event boundary is parsed from visible market labels/questions/slugs.
`groupItemThreshold` is retained only as metadata because historical audits showed that
it can be an ordinal group index rather than a Celsius threshold.

## Market discovery

Market metadata are obtained from the Polymarket Gamma `/events/keyset` endpoint.

Both closed and active markets are queried so that the 31 August market can be
represented even if its final settlement has not yet occurred.

A settlement date is admitted only if the HKO Daily Extract family forms a complete
eleven-contract partition with:

- one lower endpoint;
- nine interior one-degree bins;
- one upper tail;
- eleven valid YES-token IDs.

Incomplete or ambiguous dates are not filled.

## CLOB historical prices

Historical YES-token observations are obtained from the Polymarket CLOB
`/prices-history` endpoint.

The final reconstruction retains the established historical convention:

- seven-day retrieval window;
- 60-minute fidelity;
- YES token as the queried asset;
- explicit request cache.

For each contract c and decision cutoff tau, the selected observation is

    t* = max{t : t <= tau}.

If no recovered record exists by the cutoff, the cell remains missing.

A later observation is never substituted.

Record age is

    tau - t* >= 0.

It records the age of the recovered historical observation and is not interpreted as a
bid-ask spread, executable quote age or liquidity measure.

## Four decision rules

Decision cutoffs are:

- 24 hours prior;
- 12 hours prior;
- 6 hours prior;
- event-day open.

All cutoffs are defined in Hong Kong local time and converted to UTC.

## Market probability treatment

Binary contract-level Brier and log scores use the raw Polymarket event-level YES value.

For complete-book categorical evaluation,

    p_market_normalised_j
      =
      p_market_raw_j
      /
      sum_k p_market_raw_k.

Categorical log, multiclass Brier and total variation use this normalised eleven-event
market book.

Raw YES values are not described as a coherent probability partition when their sum
differs from one.

## Weather event probabilities

Three weather representations are carried into the market comparison.

### Raw deterministic book

The deterministic temperature forecast maps to exactly one of the eleven events,
producing a one-hot probability book.

### Static Gaussian

The frozen static settlement law is mapped analytically through the event boundaries.

### Selected GP

The weather-selected GP distribution from the weather-history experiment is mapped
analytically through the same boundaries.

For an interior event [a,b),

    p = Phi((b-mu)/sigma) - Phi((a-mu)/sigma),

with the natural one-sided limits for lower and upper tails.

Every weather event book must sum to one within numerical tolerance.

## Exact common support

A date-rule book enters direct weather-market comparison only when:

1. the certified eleven-contract Polymarket book exists;
2. all eleven historical decision-time market values exist;
3. the frozen weather distribution exists;
4. all eleven weather event probabilities exist.

Proper-score evaluation additionally requires the official HKO realised settlement.

Incomplete market books and unsupported weather forecasts are never imputed.

## Date balancing

Binary event scores are first averaged across the eleven contracts within a date-rule
book.

Book losses are then averaged across available complete decision rules on the date.

The reported aggregate is the arithmetic mean across settlement dates.

Categorical losses are balanced analogously at date level.

This prevents a date with more complete rule support from receiving mechanically larger
weight.

## Total variation

For weather book p and normalised market book q,

    TV(p,q) = 0.5 * sum_j |p_j-q_j|.

The raw-distance closure statistic is

    C_m = 1 - TV_m / TV_raw.

Total variation is descriptive proximity only.

Closeness to the market is not treated as evidence that the market is the true
probability law.

## Final empirical split

The market-period split is frozen as:

- development:
  16 March 2026 through 30 June 2026;
- external validation:
  1 July 2026 through 31 August 2026.

No July-August score or outcome enters model or pool selection.

## Convex pool

The selected GP book and normalised market book are combined as

    q(w) = w p_GP + (1-w) p_market.

The GP weight is searched on

    {0, 0.001, ..., 1}.

The selected weight minimises date-balanced categorical log loss using March-June
development data only.

It is then frozen for July-August evaluation.

The weight is not selected by trading PnL and is not interpreted as an information share.

## Paired uncertainty

Method comparisons use settlement date as the resampling unit.

The stage reports:

- ordinary date bootstrap;
- circular moving-block bootstrap with block length seven;
- 10,000 replications.

The resampling keeps rules and contracts belonging to one settlement outcome together.

## Evidence boundary

This stage answers whether settlement-aware weather probabilities:

1. become closer to Polymarket;
2. achieve lower realised proper scores than market probabilities;
3. benefit from forecast combination;
4. retain their conclusions on July-August external data.

Trading profitability is deliberately deferred to the next pipeline stage.

### Chronological certification of duplicate event books

Multiple Gamma parent events can occasionally describe the same HKO
highest-temperature settlement date. The pipeline does not choose between
such books from present-day slug appearance, market identifiers, or the
current API ordering, since those criteria could encode hindsight.

The ordinary case is unchanged: if the HKO candidates for a date already
form one valid eleven-event partition, that partition is certified directly.

Chronological resolution is invoked only when the date-level candidates do
not themselves form one unique eleven-event partition. Each parent event is
then checked separately. A parent book is eligible only if (i) it is itself
a complete eleven-event HKO partition and (ii) its parent event had been
created by event-day open, the latest of the four analysed decision cutoffs.
If exactly one parent book is eligible, it is retained. If none or more than
one are eligible, the date remains excluded.

This date-level rule does not relax the no-look-ahead requirement at earlier
decision times. The 24-hour, 12-hour, 6-hour and event-day-open market
snapshots continue to use only price observations recorded no later than
their own decision cutoff.

For 19 May 2026, two complete highest-temperature parent books are visible
in the present Gamma representation. Parent event 493669 was created on
17 May and is therefore contemporaneously admissible. Parent event 503637
was created only after event-day open and is inadmissible for all four
historical decision rules. The earlier parent book is consequently retained
without using slug prefixes or later market outcomes.

No exact Gamma parent event or binary market was recovered for 20 March
2026 or 31 March 2026. These two dates are treated as genuine market-
coverage gaps and are not imputed.
