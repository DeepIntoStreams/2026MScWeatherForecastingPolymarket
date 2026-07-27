# Notebook 10: Locked Categorical Evaluation

## Purpose

Notebook 10 evaluates the locked eleven-event probability forecasts against
certified HKO outcomes.

The selected model, continuous dispersion scale and probability mixing
parameter were fixed before the holdout and June outcomes were scored.

## Locked specification

The evaluated forecast uses:

- pooled empirical residual distribution;
- continuous dispersion scale of 1.25;
- 99 deterministic quantile particles;
- uniform probability mixing parameter of 0.01.

No component is reselected during this evaluation.

## Outcome join

Probability rows are joined to certified outcomes using settlement date and
the normalised source event label.

The mapping is independently verified by requiring

\[
\text{event order}=\text{certified event index}+1.
\]

All 1,749 probability rows join uniquely. Each of the 159 probability books
contains eleven events and exactly one realised event.

## Scores

The primary score is categorical log score. Multiclass Brier score is the
secondary score.

The four decision rules are averaged within each settlement date. Settlement
date is the uncertainty unit.

## Locked results

The ten-date holdout block contains 40 probability books. Its regularised mean
date log score is 1.140714. Its raw and regularised multiclass Brier scores are
0.583216 and 0.584306.

The thirty-date June external block contains 119 probability books. Its
regularised mean date log score is 1.513592. Its raw and regularised
multiclass Brier scores are 0.718773 and 0.719350.

One June forecast assigned zero raw probability to the realised event. Its raw
categorical log score is therefore infinite. The locked one per cent uniform
mixture makes all categorical log scores finite.

The Brier-score cost of regularisation is small: 0.001090 on holdout and
0.000577 in June.

## Evidential boundary

Notebook 10 uses realised HKO outcomes for evaluation only.

It does not reselect the model, the continuous dispersion scale or the
probability mixing parameter. It does not access market prices or calculate
trading returns.

The next stage is a common-support comparison between the locked forecast
probabilities and market probabilities.
