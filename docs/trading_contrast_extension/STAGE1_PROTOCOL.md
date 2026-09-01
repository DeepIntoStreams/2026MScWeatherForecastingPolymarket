# Final trading contrast extension — Stage 1

## Status

`PASS`

## Purpose

This extension is isolated from the certified 102-step empirical release.
The final tag remains unchanged.

The extension compares Raw, Static Gaussian, RBF GP and Matérn-3/2 GP under:

1. conservative fixed settlement;
2. TAEC-11 two-sided all-edge pre-event convergence.

## Methodological guard

No weather model is refitted and no strategy parameter is selected using
July-August results. TAEC-11 is explicitly exploratory because it was
conceived after observing the core March-August study.

## Execution tier

`B_SNAPSHOT_PRICE_PROXY`

No complete bid/ask candidate was detected, but authoritative market probability/price snapshots exist. TAEC can be implemented as a conservative mark-to-market convergence backtest with 0.01 cost per execution (0.02 round trip), explicitly labelled as a snapshot-price execution proxy.

## Greek-like risk

Probability Delta and Gamma are defined with respect to local temperature
perturbations and aggregated into portfolio net/gross exposures. They are
forecast-risk sensitivities rather than Black-Scholes Greeks.

## Inference

The date is the sampling unit. The primary uncertainty method is a seven-day
moving-block bootstrap, ordinary date bootstrap is secondary, and Holm
correction is used within each pre-specified test family.

## Next stage

Build the canonical four-model probability panel and both strategy ledgers,
while reproducing the existing fixed Raw/Static/Matérn results exactly before
accepting any new RBF or TAEC result.
