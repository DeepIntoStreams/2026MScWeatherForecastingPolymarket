# ECMWF deterministic forecast construction

## Purpose

This module reconstructs the deterministic ECMWF input used by the final
March–August empirical pipeline.

The forecasting model is ECMWF IFS. Open-Meteo Single Runs is the historical
delivery interface.

## Location and field

The request uses the established HKO-location specification from the certified
V2 acquisition:

- latitude: 22.3019444444;
- longitude: 114.1741666667;
- timezone: Asia/Hong_Kong;
- model: `ecmwf_ifs`;
- hourly variable: `temperature_2m`;
- temperature unit: Celsius;
- cell selection: land;
- forecast horizon: 240 hours.

## Forecast-time rules

The four Hong Kong decision times are:

- 24h prior: 00:00 HKT on d-1;
- 12h prior: 12:00 HKT on d-1;
- 6h prior: 18:00 HKT on d-1;
- event-day open: 00:00 HKT on d.

## Six-hour interface-availability allowance

The final dissertation methodology freezes a six-hour interface-availability
allowance.

For forecast issue s and decision time tau, eligibility requires:

    s + 6 hours <= tau.

The allowance is applied before forecast selection.

## Core and repair cycles

The primary forecast for each date-rule pair is the latest eligible 00 UTC or
12 UTC core issue after imposing the six-hour interface-availability allowance.

Only that operationally latest core candidate is attempted as the primary
forecast.

If the primary core issue is unavailable or does not contain a complete Hong
Kong target-day path, the latest eligible 06 UTC or 18 UTC issue is attempted
as a repair.

If neither candidate supplies a valid path, the date-rule key is unsupported.

The implementation does not keep moving backwards through increasingly old
core forecasts. This prevents stale forecasts from manufacturing support and
preserves the no-imputation principle.


## Complete local-day path

The target-day path must contain:

- exactly 24 hourly rows;
- exactly 24 distinct Hong Kong local hours;
- hours 00 through 23 exactly once;
- no missing two-metre temperature.

The deterministic forecast is the maximum of these 24 retained hourly values.

It is an hourly-sampled model maximum, not a continuous-time physical maximum.

## Historical archive and final rebuild

For 16 March 2024–15 March 2026, the certified V2 run inventory is used as the
frozen historical acquisition universe. This is an archive/provenance object:
it specifies which raw run initialisations were successfully retained. Forecast
values are reconstructed again from the raw ECMWF/Open-Meteo responses.

For the March–August extension, new requests use the same interface geometry.
00/12 UTC cycles are primary. 06/18 UTC requests are generated only if required
to recover a missing valid core path.

## Reconciliation with the earlier V2 panel

The earlier V2 production selector admitted a run when its run initialisation
was no later than the decision time. The final dissertation methodology instead
freezes the documented six-hour interface-availability allowance.

Consequently the old 2,920-row V2 forecast panel is retained as a diagnostic
comparison, not an exact-match acceptance target.

The final pipeline reports:

- how many historical run selections change;
- how many daily maxima change;
- the distribution of the resulting forecast differences.

This is intentional methodological reconciliation rather than silent
back-fitting to old outputs.

## Acceptance criteria

The final Steps 8–11 stage requires:

- 899 target dates;
- four forecast-time keys per target;
- unique date–forecast-time keys;
- no selected issue after its decision time;
- no violation of the six-hour availability allowance;
- complete 24-hour HKT paths for every supported forecast;
- complete historical reconciliation diagnostics;
- no imputation of unsupported forecasts.
