# Final data dictionary

## HKO

Source: Hong Kong Observatory Daily Extract.

Primary variable:
- official Absolute Daily Maximum Temperature;
- degrees Celsius;
- retained at one-decimal precision.

Roles:
- weather-model response;
- Polymarket settlement outcome.

Final required date range:
- 16 March 2024 to 31 August 2026.

## ECMWF

Forecast system:
- deterministic ECMWF IFS.

Delivery/retrieval interface:
- Open-Meteo historical/archive forecast interface.

Primary variable:
- 2-m temperature.

Derived variable:
- Hong Kong-local deterministic daily maximum temperature.

Decision rules:
- 24h;
- 12h;
- 6h;
- event-day open.

Final required date range:
- 16 March 2024 to 31 August 2026.

## Polymarket metadata

Source:
- Gamma metadata.

Roles:
- event identification;
- contract geometry;
- token identification;
- settlement-source certification.

Required period:
- 16 March 2026 to 31 August 2026.

## Polymarket prices

Source:
- CLOB historical YES-token price histories.

Roles:
- market probability benchmark;
- weather-market comparison;
- convex pooling;
- reduced-form trading entry proxy.

Both raw event-level YES prices and normalised eleven-event categorical books are
retained because they serve different scoring purposes.

Required period:
- 16 March 2026 to 31 August 2026.
