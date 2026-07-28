# Phase 4F: HKO Daily Maximum Temperature

## Purpose

Phase 4F retrieves and certifies the Hong Kong Observatory daily
maximum temperature observations required for the two-year
weather-only training period.

## Source

The source is the Hong Kong Observatory Open Data API:

- data type: `CLMMAXT`;
- station: `HKO`;
- return format: JSON;
- quantity: daily maximum air temperature in degrees Celsius.

## Training boundary

The dates are obtained from the certified Phase 4E weather-only
decision-support panel.

Only those 730 dates are retained in the training panel. Rows returned
by the source before or after the weather-only training interval are
recorded separately and are not used.

## Evidential boundary

This phase accesses HKO observations because they are the response
variable for weather-only model training.

It does not access:

- market prices;
- Polymarket settlement outcomes;
- trading returns.

It does not fit or select a model, calibration parameter, decision rule
or trading strategy.

## Principal output

```text
outputs/v2/diagnostics/04f_hko_daily_max_training_panel.csv

This panel contains exactly one HKO daily maximum temperature for each
of the 730 weather-only training dates.

## Next stage

The next stage joins these observations to the 2,920 historical
forecast rows and constructs forecast residuals separately for the four
decision rules.
