# Notebook 09: Event Probability Calibration

## Purpose

Notebook 09 selects and locks the uniform mixing parameter applied to the
eleven-event probability vectors.

The pooled empirical residual model and continuous dispersion scale of 1.25
were selected in earlier notebooks. Neither choice is reconsidered here.

## Development source

Selection uses the calibrated out-of-fold predictions in:

`outputs/diagnostics/05_selected_oof_calibrated_predictions.csv`

The source contains 152 forecasts over 38 development dates, four decision
rules per date and 99 calibrated quantiles per forecast.

Continuous calibration therefore precedes event probability calibration.

## Event probabilities

The 99 quantiles are interpreted as equally weighted deterministic particles.
They are assigned to the certified eleven-event partition using the recorded
contract boundaries.

For event \(j\),

\[
\widehat p_j=\frac{N_j}{99},
\]

where \(N_j\) is the number of particles assigned to that event.

The particles approximate the predictive distribution. They are not treated
as independent random draws.

## Uniform mixing

For \(\lambda\in[0,1]\),

\[
\widehat p_j^{(\lambda)}
=
(1-\lambda)\widehat p_j+\frac{\lambda}{11},
\qquad j=1,\ldots,11.
\]

This transformation preserves the unit probability sum. A positive value of
\(\lambda\) also removes exact zero probabilities.

The candidate grid is

\[
\lambda\in\{0.00,0.01,\ldots,1.00\}.
\]

## Selection rule

Categorical log score is the primary criterion. Multiclass Brier score is a
secondary diagnostic.

Scores are averaged across the four decision rules within each settlement
date. The 38 settlement dates are the uncertainty units.

The strict development winner is \(\lambda=0.02\). The smallest value within
one standard error of this winner is \(\lambda=0.01\), which is therefore
selected.

This retains 99 per cent of the original event probability vector and
introduces only limited regularisation.

## Locked application

The selected value is applied unchanged to the ten-date holdout block and the
thirty-date June external block.

The locked output contains 159 probability books and 1,749 event probability
rows over 40 dates.

## Evidential boundary

Notebook 09 does not use holdout or June outcomes for selection. It does not
calculate holdout or June scores, access market prices or calculate trading
returns.

These operations are reserved for later notebooks.
