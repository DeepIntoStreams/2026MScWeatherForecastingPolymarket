# Phase 22 Discussion Evidence

## Main substantive interpretation

The central contribution is not that a sophisticated model defeats a prediction
market. It is that a carefully specified residual GP converts a deterministic
weather forecast into a coherent local predictive distribution, materially
improves both the raw forecast and a static Gaussian correction, and permits a
disciplined comparison with market probabilities.

The static benchmark is crucial to this interpretation. Without it, the GP gain
could be attributed merely to correcting a large local deterministic bias and
adding residual variance. With the benchmark included, the thesis can separate
three effects: raw forecast error, simple local Gaussian correction and
conditional nonlinear residual modelling.

## Why the market still performs better

Polymarket can reflect information absent from the weather-only feature set,
including newer weather updates, alternative forecasts, local observations,
participant judgement and contract-specific attention. The discrepancy analysis
shows systematic reallocations across the contract book, but it cannot establish
which information channel causes them. The thesis should frame the market result
as evidence that the weather-only model is informationally incomplete, not as a
proof of strong-form market efficiency.

## Why forecast combination does not rescue the GP claim

The selected pool weight is unstable and the June oracle favours the market
alone. A pooled forecast that improves on the weaker GP but loses to the market
does not demonstrate robust complementarity. This is still valuable: it answers
the previously open methodological question and prevents an unsupported claim
from remaining in the dissertation.

## Predictive limitations

The Matern model's undercoverage, serial dependence and remaining conditional
variance structure show that a Gaussian residual law with the current features
is an approximation. These diagnostics motivate future work on richer dynamic
covariates, non-Gaussian likelihoods, time-varying covariance or state-space
post-processing. They should not be used to introduce several additional models
into the present thesis. The distinction-level response is to analyse the chosen
model deeply and state precisely where it fails.

## Trading interpretation

The trading exercise remains secondary. A small positive historical point
estimate with wide uncertainty, cost sensitivity and omitted execution frictions
does not establish a stable trading edge. The market-comparison and forecast-
combination results make this caution even more important.

## Scope discipline

CatBoost and broad ensemble modelling should remain brief contextual or appendix
material. Restoring them as parallel main pipelines would dilute the mathematical
development and empirical depth now achieved for deterministic post-processing,
the static Gaussian benchmark, GP construction, diagnostics, market comparison
and combination.
