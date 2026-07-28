# Phase 2: Open-Meteo Single Runs Source Pilot

## Purpose

Phase 2 determines whether historical ECMWF IFS forecasts obtained
through Open-Meteo Single Runs can support the expanded weather-only
training sample.

The phase concerns source availability and forecast reconstruction only.
It does not fit a probabilistic model or evaluate market performance.

## Historical cycle coverage

The archive-boundary audit shows that the 00 and 12 UTC initialisation
cycles are available consistently across the tested early archive
window.

The 06 and 18 UTC cycles are not complete across the same period.
They are therefore supplementary rather than required historical
training cycles.

The empirical design consequently uses:

- 00 UTC as a core historical cycle;
- 12 UTC as a core historical cycle;
- 06 UTC where available;
- 18 UTC where available.

Four-cycle completeness is not assumed.

## Reconstruction audit

Five dates with complete support for all four decision rules were
selected from 12 April to 21 May 2026.

The audit produced:

- five target dates;
- four decision rules per date;
- twenty date-rule reconstructions;
- twenty successful API requests;
- twenty complete Hong Kong local days;
- twenty forecasts available before their corresponding decisions.

The reconstructed daily maximum temperatures matched the certified
Version 1 forecast values exactly. Both the median and maximum absolute
difference were 0.0 degrees Celsius.

## Evidential boundary

Phase 2 did not:

- access Polymarket prices;
- use realised market outcomes;
- fit or select a probabilistic model;
- calculate categorical scores;
- select a trading rule;
- calculate trading returns;
- alter the certified Version 1 release.

## Decision

The Single Runs source is approved for construction of the complete
two-year weather-only request plan.

The next phase must measure date-by-date and cycle-by-cycle availability
before downloading the full historical sample.
