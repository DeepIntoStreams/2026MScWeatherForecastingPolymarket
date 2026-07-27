# Notebook 08 Locked Event Probabilities

## Purpose

Notebook 08 converts the locked calibrated temperature distributions into
probabilities over the certified eleven-event temperature partition.

No realised outcome or market price enters this construction.

## Event partition

For each settlement date, the eleven events form a partition of the real line.

The boundary convention is left closed and right open:

\[
[a,b).
\]

The lowest event is unbounded below, and the highest event is unbounded above.
A value equal to an interval boundary therefore enters the event beginning at
that boundary.

This convention is consistent with the floor-style interpretation of the
certified temperature contracts.

## Quantile particles

Each predictive distribution is represented by the 99 quantiles

\[
Q(0.01),Q(0.02),\ldots,Q(0.99).
\]

These values are treated as equally weighted deterministic quadrature
particles. They are not independent random draws from the predictive
distribution.

For event \(A_j\), the raw event probability is

\[
\widehat p_j
=
\frac{1}{99}
\sum_{m=1}^{99}
\mathbf 1
\{Q(m/100)\in A_j\}.
\]

Every quantile particle must belong to exactly one event.

## Probability resolution

Every probability is a multiple of

\[
\frac{1}{99}.
\]

Consequently, the finest positive probability is approximately 0.0101.

This discretisation is a consequence of the retained 99-quantile
representation. It is not sampling error from a Monte Carlo procedure.

## Zero probabilities

An event containing no quantile particle receives probability zero.

Zero probabilities are retained in Notebook  particle receives probability zero.

Zero probabilities are retained in Notebook08 because this notebook performs
only the deterministic mapping from the continuous distribution to the event
partition.

No clipping, additive constant or uniform probability mixing is introduced
without a separately declared calibration step.

## Probability sums

The eleven probabilities sum exactly to one because:

1. the event book partitions the real line;
2. every particle is assigned exactly once;
3. each particle has weight \(1/99\).

No further renormalisation should be required.

## Static contract information

The event definitions are required because they specify the temperature
partition.

This does not constitute the use of market prices. No bid, ask, spread,
liquidity or transaction information is accessed.

## Evidential boundary

Notebook 08 does not:

- use realised HKO temperatures;
- calculate categorical log score or Brier score;
- choose probability regularisation;
- access Polymarket prices;
- compare the forecast with the market;
- calculate trading returns.

The following notebook may select a simple uniform mixing parameter using
development out-of-fold predictions only.
