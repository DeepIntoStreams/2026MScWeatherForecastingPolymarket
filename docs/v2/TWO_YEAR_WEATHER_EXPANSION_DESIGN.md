# Version 2 Two-Year Weather Expansion

## Objective

Version 2 expands the local weather post-processing study using
approximately two years of historical deterministic ECMWF IFS
forecasts.

The earlier empirical release remains valid. Version 2 is an
expanded analysis rather than a repair.

## Periods

Weather-only training period:

`14 March 2024 to 15 March 2026`

Weather plus market training period:

`16 March 2026 to 31 May 2026`

June out-of-sample validation:

`1 June 2026 to 30 June 2026`

July out-of-sample validation:

`1 July 2026 to 31 July 2026`

## Main models

The central models are the raw deterministic forecast, mean
residual correction, empirical residual distribution and Gaussian
process regression.

Existing CatBoost and ensemble-related work is retained pending
supervisor advice but is not expanded during historical data
retrieval.

## Excluded additions

ERA5, direct ECMWF Open Data ingestion, MARS dependency, additional
global models, additional cities and advanced trading machinery are
excluded from the active empirical plan.

## Preservation rule

Version 1 notebooks, manifests and outputs cannot be overwritten.
Version 2 uses separate versioned paths.
