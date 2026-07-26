# 18q June 2026 ECMWF IFS single-run forecast ingestion

Generated at UTC: `2026-07-21T04:59:00.893049+00:00`

## Overall judgement

**USABLE_WITH_LIMITATIONS**

## Method

The latest ECMWF IFS run satisfying the conservative availability condition `run initialisation + 6 hours <= decision time` was selected for each date-rule request.

The Open-Meteo Single Runs API was queried at the fixed Hong Kong Observatory coordinates using hourly two-metre temperature in Asia/Hong_Kong time. The event-day maximum is the maximum of the 24 local hourly values.

No elevation override, observation substitution, later-run replacement or Gaussian probability bridge was used.

## Sample flow

- Input June dates: 30
- Input certified contracts: 330
- Date-rule requests: 120
- Unique selected runs: 91
- Successful run fetches: 91
- Successfully parsed runs: 90
- Unique-run hourly rows: 21600
- Request-level hourly rows: 2856
- Ready daily maximum forecasts: 119
- Unready daily maximum forecasts: 1
- Issue rows: 2

## Forecast error by decision rule

| Rule | Ready dates | Mean forecast maximum | Mean HKO maximum | Mean error | MAE | RMSE | Underforecast rate | Exact contract hit rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 24h_prior | 30 | 29.360000 | 31.173333 | -1.813333 | 1.873333 | 2.097935 | 0.933333 | 0.033333 |
| 12h_prior | 30 | 29.423333 | 31.173333 | -1.750000 | 1.750000 | 1.923105 | 1.000000 | 0.100000 |
| 6h_prior | 29 | 29.462069 | 31.117241 | -1.655172 | 1.758621 | 1.978854 | 0.931034 | 0.103448 |
| event_day_open | 30 | 29.516667 | 31.173333 | -1.656667 | 1.750000 | 2.011384 | 0.966667 | 0.066667 |

## Availability by decision rule

| Rule | Requests | Ready | Missing |
|---|---:|---:|---:|
| 24h_prior | 30 | 30 | 0 |
| 12h_prior | 30 | 30 | 0 |
| 6h_prior | 30 | 29 | 1 |
| event_day_open | 30 | 30 | 0 |

## Integrity checks

| Check | Passed | Blocking | Detail |
|---|---|---|---|
| request_plan_has_120_date_rule_rows | True | True | rows=120 |
| request_plan_has_91_unique_runs | True | True | unique_runs=91 |
| selected_runs_are_admissible_at_cutoff | True | True | violations=0 |
| selected_runs_use_six_hour_cycles | True | True | hours=0,6,18 |
| fetch_inventory_has_91_rows | True | True | rows=91 |
| raw_archive_has_91_files | True | True | files=91 |
| daily_max_panel_has_120_rows | True | True | rows=120 |
| daily_max_keys_are_unique | True | True | duplicates=0 |
| successful_fetches_have_parsed_paths | False | False | successful_fetches=91; parsed_successfully=90 |
| at_least_one_ready_date_rule_path | True | False | ready=119 |
| ready_paths_have_24_local_hours | True | True | bad_ready_paths=0 |
| ready_paths_have_finite_daily_maxima | True | True | bad_ready_maxima=0 |
| ready_paths_select_one_contract | True | True | bad_books=0 |
| no_gaussian_bridge_columns | True | True | deterministic membership only |

## Downstream use

Only ready date-rule rows may enter the expanded market-versus-weather common-support panel. The deterministic forecast maximum is an input to subsequent local residual post-processing; it is not itself treated as a calibrated probability distribution.
