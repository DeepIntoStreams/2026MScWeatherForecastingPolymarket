# Final empirical methodology

## Research sequence

The empirical study is deliberately organised around seven questions:

1. How accurate is raw deterministic ECMWF for the HKO settlement target?
2. Is the ECMWF-to-HKO residual systematic and does it vary by decision time?
3. How much does a simple static Gaussian settlement correction achieve?
4. Does a conditional Matérn-3/2 GP add useful information beyond the static correction?
5. How do the resulting weather probabilities compare with Polymarket?
6. Does improved probabilistic forecasting translate into trading value?
7. Do the market and trading conclusions generalise to untouched July-August data?

## Data allocation

Weather modelling is conducted exclusively using observations preceding the
Polymarket evaluation period:

- 16 March 2024 to 15 March 2025: initial weather estimation;
- 16 March 2025 to 15 March 2026: chronological weather validation;
- all 730 dates: final pre-market weather fit after model selection.

The market period is split into:

- 16 March 2026 to 30 June 2026: market development;
- 1 July 2026 to 31 August 2026: untouched external market validation.

March-August remains entirely forward evidence for the weather model because no
weather outcome after 15 March 2026 enters weather-model fitting.

## Core model hierarchy

The main presentation is:

Raw ECMWF -> Static Gaussian correction -> Matérn-3/2 GP.

RBF GP is retained as a weather-only covariance benchmark during model selection,
but is not automatically propagated through every downstream analysis.

## Statistical discipline

- chronological rather than random weather validation;
- CRPS as primary predictive-distribution selection criterion;
- HKO settlement date as primary inferential/resampling unit;
- raw Polymarket YES prices for binary scoring and trading signals;
- normalised eleven-event Polymarket books for categorical scoring;
- no July-August information may influence market-policy selection.

## Complexity rule

Additional methods are included only when they materially improve identification,
interpretation or robustness.

Exploratory outputs may be generated freely during research, but they enter the
submitted thesis only when they materially support or qualify the core empirical
story.
