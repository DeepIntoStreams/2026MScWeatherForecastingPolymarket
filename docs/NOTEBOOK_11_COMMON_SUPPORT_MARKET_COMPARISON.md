# Notebook 11: Common-Support Market Comparison

## Purpose

Notebook 11 compares the locked weather-derived event probabilities with
Polymarket probabilities on exact common support.

## Canonical market source

The authoritative source is:

    data/processed/18sA_canonical_source_adapters/18sA_canonical_market_panel.csv

The certified historical market-price field is `p_market`.

The expanded market scoring panel is a derived diagnostic copy. Exact equality
with the canonical adapter is not required. The canonical adapter takes
precedence.

## Common support

- Model books available: 159
- Market books available: 155
- Common-support books: 154
- Common-support dates: 40
- Model-only books: 5
- Market-only books: 1

Only complete eleven-event books observed in both sources enter scoring.

## Probability treatment

Raw Polymarket prices are retained unchanged for the later trading analysis.

For categorical evaluation, the eleven prices within each event book are
divided by their sum.

## Scoring convention

Categorical log score is the primary score. Multiclass Brier score is the
secondary score.

The paired difference is model score minus market score. A negative difference
favours the weather-derived model.

Settlement date is the uncertainty unit.

## Holdout result

- Dates: 10
- Probability books: 40
- Mean model log score: 1.140714
- Mean market log score: 1.091350
- Mean model-minus-market log difference: 0.049364
- Mean model Brier score: 0.584306
- Mean market Brier score: 0.585087
- Mean model-minus-market Brier difference: -0.000781

## June external result

- Dates: 30
- Probability books: 114
- Mean model log score: 1.550654
- Mean market log score: 1.260923
- Mean model-minus-market log difference: 0.289732
- Mean model Brier score: 0.720809
- Mean market Brier score: 0.648471
- Mean model-minus-market Brier difference: 0.072339

## Interpretation

The market performs better under both categorical scores on the 30-date June
external block.

The 10-date holdout is closer. The market has the lower mean categorical log
score, while the mean multiclass Brier scores are approximately equal.

## Evidential boundary

Market prices did not influence model selection or either calibration stage.

Notebook 11 does not select a trading strategy and does not calculate trading
returns.
