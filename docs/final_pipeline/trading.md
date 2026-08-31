# Final fixed-policy trading and forecast-risk stage

## Scope

Steps 38–55 begin only after the weather model, event mapping, market
history and exact common support have been frozen.

The stage asks whether the weather-market probability disagreement has
economic value under one transparent reduced-form policy and how forecast
error propagates through contract probabilities and trading decisions.

It does not search a large strategy universe.

## Trading signal

The primary signal uses the selected weather-only GP probability and the raw
historical Polymarket YES record:

    g[d,r,j] = p_GP[d,r,j] - p_market_raw[d,r,j].

The convex weather-market pool is not used as a trading signal.

Raw and static probabilities are used later only for fixed-policy
attribution.

## Contract choice

For a given date and decision rule, select the event with the largest
model-minus-market gap.

Equal gaps are resolved using the lowest certified event rank.

At most one long-YES share may be held per settlement date.

## Development-only threshold selection

Candidate thresholds are

    H = {0, 0.01, ..., 0.25}.

For each decision rule, every settlement date with a complete exact-support
book and observed target enters the development PnL series.

No-trade dates contribute zero PnL.

A threshold is eligible only if it executes at least ten development trades.

For each rule:

1. find the maximum mean daily development PnL;
2. if several thresholds attain the same maximum, take the largest;
3. calculate the ordinary standard error of mean daily PnL at that best
   threshold;
4. retain every eligible threshold whose mean is at least

       best mean - SE(best);

5. choose the largest retained threshold.

The selected decision rule maximises

    mean(h*) - SE(h*)

under the fixed tie order:

    24h, 12h, 6h, event-day open.

This is a finite-sample conservative selection convention, not a confidence
interval.

The primary rule selection uses each decision rule's own complete
development support, matching the prespecified policy design.

A separate non-selection diagnostic repeats the threshold calculations on
the intersection of dates with all four rule books to disclose any support-
composition sensitivity.

## Reference trading cost and payoff

The historical YES value is a reduced-form entry proxy rather than an
executable bid/ask quote.

A one-cent reference cost per executed long-YES share is imposed:

    kappa = 0.01.

The signal threshold is applied to the probability gap:

    trade = 1{g >= h}.

For an executed position,

    gross PnL = Y - p_market_raw,

    net PnL = Y - p_market_raw - kappa.

The one-cent cost is a transparent reference convention rather than an
estimate of historical spread, fees or slippage.

## Frozen external attribution

Once rule and threshold have been selected from 16 March through
30 June, they are frozen for 1 July through 31 August.

The policy is then applied separately to:

- raw deterministic event probabilities;
- the static Gaussian correction;
- the selected GP probabilities.

Raw and static probabilities are not re-optimised.

Consequently the raw-static-GP comparison changes only the probability
source while preserving the selected decision rule, threshold, market entry
records and reference cost.

## Risk statistics

All eligible settled dates enter date-level PnL, including zero-PnL no-trade
dates.

The stage reports:

- total gross and net PnL;
- mean and sample standard deviation of daily PnL;
- non-annualised settlement-date Sharpe;
- a clearly labelled descriptive sqrt(365) Sharpe;
- downside deviation relative to zero;
- empirical 5% expected shortfall;
- trade and hit rates;
- average win and loss;
- profit factor;
- maximum drawdown;
- aggregate entry cash;
- return on entry cash;
- break-even cost per executed trade;
- top-one and top-two absolute-PnL concentration.

The non-annualised settlement-date Sharpe is the principal
volatility-adjusted statistic.

## Uncertainty

Uncertainty uses settlement date as the resampling unit.

The stage reports 10,000-replication:

- ordinary date bootstrap;
- circular moving-block bootstrap with block length seven.

Intervals are produced for method-level PnL, mean PnL and Sharpe, and for
paired static-minus-raw, GP-minus-static and GP-minus-raw date-level PnL
contrasts.

## Cost sensitivity

The selected GP policy's selected contracts and activation decisions are held
fixed while the per-trade cost is varied.

The cost experiment therefore measures implementation-cost exposure rather
than reoptimising the trading policy.

## Probability delta and gamma

For a fitted Gaussian settlement law N(mu,sigma^2), local event-probability
sensitivity is evaluated analytically.

For an interior interval [a,b),

    p = Phi((b-mu)/sigma) - Phi((a-mu)/sigma),

    dp/dmu
      =
      [phi((a-mu)/sigma)-phi((b-mu)/sigma)] / sigma,

    d2p/dmu2
      =
      [za phi(za)-zb phi(zb)] / sigma^2,

where

    za=(a-mu)/sigma,
    zb=(b-mu)/sigma.

The corresponding one-sided formulas are used for the lower and upper tail
events.

Analytical delta is checked against central finite differences.

## Decision-boundary diagnostics

For each external settlement date the selected GP policy records:

- probability gap;
- threshold margin;
- gap between the best and second-best contract;
- distance from the predictive mean to the nearest event-book boundary;
- distance to the selected contract's nearest finite boundary;
- selected-contract probability delta and gamma.

These quantities identify locations where smooth probability changes can
become non-smooth economic decisions.

## Predictive-mean stress

The empirical stress is deliberately reduced-form.

For shift delta,

    N(mu,sigma^2)
      ->
    N(mu+delta,sigma^2).

Predictive scale, fitted parameters, historical information, market records,
decision rule, threshold and reference cost remain fixed.

It does not perturb the deterministic ECMWF feature and rerun the GP.

Two objects are reported.

First, the baseline selected contract is held fixed and its probability,
gap and model-implied net value are recomputed. This is the smooth
fixed-contract sensitivity.

Second, the entire strategy is re-evaluated, allowing the selected event and
trade/no-trade activation to change. This generates the economically
relevant piecewise response.

The stress grid runs from -2°C to +2°C in 0.1°C increments and additionally
contains +/-0.25°C so central finite portfolio slopes can be reported.

These finite portfolio slopes are not classical deltas.

## Forecast error and realised PnL

On settled July-August dates, the final panel retains:

- raw signed and absolute temperature errors;
- selected-GP predictive-mean signed and absolute errors;
- model-market probability gap;
- threshold and selection margins;
- event-boundary distance;
- probability delta and gamma;
- realised date PnL.

The analysis reports error bins and Spearman associations only.

No complex PnL regression is fitted.

## Pending 31 August settlement

A trading decision can be recorded without a realised outcome.

Dates whose HKO settlement remains unavailable are retained as pending
decision records but excluded from realised PnL, Sharpe, bootstrap and
forecast-error statistics.

When the official HKO target becomes available, the target may be refreshed
and the downstream outputs rerun. March-June policy selection remains
unchanged because 31 August belongs to external validation.
