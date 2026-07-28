# Phase 5: Two-Year Weather-Only Forecast Residuals

## Purpose

Phase 5 joins the certified deterministic forecast panel to the
certified Hong Kong Observatory daily maximum-temperature observations.

## Residual definition

For target date \(d\) and decision rule \(r\), the residual is

\[
R_{d,r}
=
T_d^{\mathrm{HKO}}
-
\widehat T_{d,r}^{\mathrm{det}}.
\]

A positive residual means that the deterministic forecast was below the
realised HKO daily maximum. A negative residual means that the forecast
was above the realised maximum.

The forecast error is defined using the opposite sign:

\[
E_{d,r}
=
\widehat T_{d,r}^{\mathrm{det}}
-
T_d^{\mathrm{HKO}}
=
-R_{d,r}.
\]

## Sample

The certified panel contains:

- 730 weather-only training dates;
- four decision rules for each date;
- 2,920 date-rule observations;
- no missing deterministic forecasts;
- no missing HKO observations.

## Seasonal variables

The panel contains a calendar-day index, day of year, and annual sine
and cosine terms. These variables support later Gaussian-process model
construction. No model is fitted in Phase 5.

## Evidential boundary

Phase 5 does not access market prices or Polymarket outcomes. It does
not fit or select a forecasting model, select calibration parameters,
choose a decision rule or calculate trading returns.

## Principal output

The principal residual panel is stored at:

outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv

## Next stage

Phase 6 defines the chronological weather-only training design and
constructs the Gaussian-process covariate matrices.
