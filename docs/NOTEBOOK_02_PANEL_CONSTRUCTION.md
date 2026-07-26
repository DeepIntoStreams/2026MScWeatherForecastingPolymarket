# Notebook 02 Panel Construction

Notebook 02 constructs the deterministic forecast and HKO outcome panel used
by the probabilistic post-processing models.

## Historical forecast column

The archived field `forecast_hko_daily_max_C` is a deterministic forecast of
the daily maximum temperature at the HKO location. It is not the realised HKO
outcome.

An earlier automated audit incorrectly classified the field as an outcome
because its name contains `hko`. This interpretation is rejected because:

- the column is explicitly forecast-labelled;
- it matches all 256 independently reconstructed hourly maxima exactly;
- it does not equal the realised HKO outcome.

## Independent hourly verification

Each retained historical path contains 24 unique Hong Kong local forecast
hours. The maximum of those 24 values is equal to the stored daily forecast.

The historical reconciliation has:

- 256 date-rule rows;
- 72 settlement dates;
- zero mean absolute discrepancy;
- zero maximum absolute discrepancy.

## Evidential boundary

The historical request plan contains 292 requested date-rule combinations.
Only 256 have an independently verified complete hourly path.

The remaining 36 requests are excluded. They are not assigned forecast values
from the realised HKO target or from an unsupported proxy.

## June support

The certified June panel contains 119 verified date-rule observations over all
30 June dates. The missing combination is 24 June under the six-hour-prior
decision rule.

## Final panel

The combined verified panel contains:

- 256 March-May observations;
- 119 June observations;
- 375 date-rule observations;
- 102 settlement dates.

Every retained forecast was issued no later than the applicable decision time.
