# Phase 9 GP Contract-Event Probability Audit

## Status

PASSED

## Probability construction

For each forecast-supported date and decision rule, the Phase 8
Gaussian-process predictive distribution is treated as a Gaussian
temperature distribution with mean `gp_temperature_mean_c` and
standard deviation `gp_temperature_std_c`.

For a canonical contract event with interval
`[lower_bound_c, upper_bound_c)`, the event probability equals the
corresponding Gaussian CDF interval mass.

## Certified support

- Settlement and market universe: 103 dates.
- Canonical contract rows: 1133.
- Forecast-supported dates: 102.
- Forecast-supported date-rule rows: 375.
- Contract-event probability rows: 4125.
- Weather-plus-market training dates: 72.
- June out-of-sample validation dates: 30.
- Unsupported date-rule rows: 37.
- No missing forecasts were imputed.

## Integrity

- All daily contract books form complete interval partitions: yes.
- All date-rule probability masses sum to one: yes.
- Maximum absolute probability-mass error:
  0.
- Exactly one realised Yes event occurs on every settlement date: yes.
- Duplicate contract-event probability keys: 0.

## Overall proper scores

- Mean binary Brier score:
  0.06664735.
- Mean binary log score:
  0.21621827.
- Mean categorical log score:
  1.53611577.
- Mean multiclass Brier score:
  0.73312081.
- Mean continuous CRPS:
  0.64254297 degrees Celsius.
- Mean GP absolute error:
  0.88111502 degrees Celsius.

## June out-of-sample proper scores

- Mean binary Brier score:
  0.06793796.
- Mean binary log score:
  0.22272225.
- Mean categorical log score:
  1.59453885.
- Mean multiclass Brier score:
  0.74731751.
- Mean continuous CRPS:
  0.61501747 degrees Celsius.
- Mean GP absolute error:
  0.80092935 degrees Celsius.

## Evidential boundary

No market price was used. June data were not used to refit the GP,
select a kernel, or impute a missing forecast. June is evaluated only
after the Phase 8 model and support rules were fixed.
