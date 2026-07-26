# Notebook 02 Support and Chronology

## Statistical support

The certified market universe contains 103 dates and 412 possible date-rule
combinations.

The verified deterministic forecast panel contains 375 combinations over 102
dates.

Thirty-six historical requests lack an independently verified complete hourly
forecast path. One June combination is also unavailable.

## Chronological design

The calendar boundaries are declared before fitting probabilistic candidates:

- warm-up training: dates no later than 11 April 2026;
- development validation: 12 April to 21 May 2026;
- holdout: 22 May to 31 May 2026;
- external test: 1 June to 30 June 2026.

The actual number of available dates in each block is calculated from the
verified panel rather than assumed from the complete calendar.

## Development validation

Available development dates are divided into four consecutive folds of
approximately equal size.

For each fold:

1. all training dates precede the validation dates;
2. the settlement date is the uncertainty unit;
3. all decision-rule rows for one date remain together;
4. candidate continuous distributions are compared by CRPS.

## Locked periods

Holdout and external outcomes cannot affect model selection, calibration or
the trading rule.

The model fitted before the holdout is transferred to June without refitting
after the holdout outcomes are observed.

## Later data

July and August observations may be added as a later external temporal
extension. They cannot retroactively alter a model selected from the declared
development period.
