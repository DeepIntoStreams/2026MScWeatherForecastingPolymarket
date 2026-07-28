# Final Empirical Results Register

## Locked probabilistic model

The selected probabilistic model is `pooled_empirical_residual`, belonging to
the `empirical_residual` family. Selection was conducted using
date-grouped out-of-fold CRPS on the development period.

Mean date CRPS decreased from 1.922368 for the raw deterministic
forecast to 0.732178 for the selected model. This is a
relative reduction of 61.91%.

## Calibration

The locked continuous dispersion scale is 1.25. The
locked uniform event-probability mixing parameter is 0.01.
Neither value was reselected using the May holdout or June external
evaluation block.

## Evaluation tables

The thesis-ready categorical evaluation table is:

`outputs/thesis/16_categorical_evaluation_table.csv`

The exact-common-support model and market comparison is:

`outputs/thesis/16_market_comparison_table.csv`

The locked reduced-form trading evaluation is:

`outputs/thesis/16_trading_evaluation_table.csv`

The settlement-date uncertainty results are:

`outputs/thesis/16_uncertainty_table.csv`

## Evidential limits

The evidence is finite-sample and block-specific. It does not establish
universal model superiority, population-level statistical significance,
market inefficiency or executable profitability. The implemented
forecast source is deterministic IFS with probabilistic post-processing;
the empirical release does not claim an implemented AIFS ENS, ECMWF ENS
or Earth-2 experiment.
