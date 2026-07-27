# Notebook 14: Final Empirical Synthesis

## Purpose

Notebook 14 consolidates the locked empirical evidence produced by
Notebooks 04 to 13. It does not fit a new model or reselect an
existing model, calibration parameter, decision rule or trading
strategy.

## Empirical lineage

The synthesis covers:

1. probabilistic model selection by date-grouped out-of-fold CRPS;
2. continuous dispersion calibration;
3. conversion of 99 quantile particles to the eleven-event book;
4. event-probability regularisation;
5. locked categorical evaluation;
6. exact-common-support comparison with Polymarket;
7. development-selected trading evaluation;
8. settlement-date uncertainty and rule-sensitivity analysis.

## Principal outputs

The primary numerical register is:

```text
outputs/final_tables/14_primary_empirical_results_register.csv

```

The thesis claim-boundary table is:

```text
outputs/final_tables/14_claim_boundary_table.csv
```

The detailed source, stage and integrity records are stored under:

```text
outputs/diagnostics/14_*.csv
```

## Evidential boundary

The results are finite-sample empirical comparisons. The market
comparison does not establish market inefficiency. The trading
analysis is a reduced-form one-share payoff calculation and does not
establish executable profitability. The bootstrap and sign-flip
results describe uncertainty in the available settlement dates and
do not establish universal population-level significance.

The empirical implementation uses deterministic IFS forecasts with
probabilistic post-processing. It does not claim implementation of
AIFS ENS, ECMWF ENS or NVIDIA Earth-2.
