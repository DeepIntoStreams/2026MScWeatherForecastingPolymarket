# Notebook 02 Weather Source Audit

This audit identifies the deterministic weather files available for construction of the expanded training panel.

Tables inspected: **542**

## Required source roles

### Hourly Forecasts

- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/19a_hko_ecmwf_single_run_hourly_forecasts.csv`: 48480 rows, 88 dates, 2026-03-14 to 2026-06-09.
- `git:archive/17j-plus-18n-18y-20260726:data/processed/19a_hko_ecmwf_single_run_hourly_forecasts.csv`: 48480 rows, 88 dates, 2026-03-14 to 2026-06-09.

### Daily Max Forecasts

- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/19a_hko_ecmwf_single_run_daily_max_forecasts.csv`: 292 rows, 73 dates, 2026-03-16 to 2026-05-31.
- `git:archive/17j-plus-18n-18y-20260726:data/processed/19a_hko_ecmwf_single_run_daily_max_forecasts.csv`: 292 rows, 73 dates, 2026-03-16 to 2026-05-31.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18q_june_2026_ecmwf_single_run_forecasts/18q_june_2026_daily_max_forecasts.csv`: 120 rows, 30 dates, 2026-06-01 to 2026-06-30.

### Request Plan

- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/19a_hko_ecmwf_single_run_request_plan.csv`: 292 rows, 73 dates, 2026-03-16 to 2026-05-31.
- `git:archive/17j-plus-18n-18y-20260726:data/processed/19a_hko_ecmwf_single_run_request_plan.csv`: 292 rows, 73 dates, 2026-03-16 to 2026-05-31.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18q_june_2026_ecmwf_single_run_forecasts/18q_june_2026_weather_request_plan.csv`: 120 rows, 30 dates, 2026-06-01 to 2026-06-30.

### Fetch Inventory

- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18p_june_2026_clob_market_price_recovery/18p_june_2026_clob_fetch_inventory.csv`: 330 rows, 30 dates, 2026-06-01 to 2026-06-30.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/19a_hko_ecmwf_single_run_fetch_inventory.csv`: 224 rows, 0 dates,  to .
- `git:archive/17j-plus-18n-18y-20260726:data/processed/19a_hko_ecmwf_single_run_fetch_inventory.csv`: 224 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18q_june_2026_ecmwf_single_run_forecasts/18q_june_2026_unique_run_fetch_inventory.csv`: 91 rows, 0 dates,  to .

### Integrity Checks

- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/21c_integrity_checks.csv`: 30 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18r_june_2026_market_weather_common_support/18r_june_2026_integrity_checks.csv`: 24 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18uB_model_specific_freeze_support/18uB_integrity_checks.csv`: 20 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/21a_simple_edge_integrity_checks.csv`: 19 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/21b_full_event_book_integrity_checks.csv`: 19 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18yB_thesis_output_freeze/18yB_integrity_checks.csv`: 19 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/20a_integrity_checks.csv`: 18 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/20e_locked_holdout_integrity_checks.csv`: 16 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18s_expanded_march_june_canonical_sample/18s_expanded_integrity_checks.csv`: 16 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18uA_chronological_partition_and_folds/18uA_integrity_checks.csv`: 16 rows, 0 dates,  to .

### Issues

- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/19a_hko_ecmwf_forecast_issues.csv`: 57 rows, 16 dates, 2026-03-16 to 2026-04-02.
- `git:archive/17j-plus-18n-18y-20260726:data/processed/19a_hko_ecmwf_forecast_issues.csv`: 57 rows, 16 dates, 2026-03-16 to 2026-04-02.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18l_clob_recovery_issues.csv`: 291 rows, 13 dates, 2026-03-16 to 2026-05-21.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/19c_issues.csv`: 9 rows, 4 dates, 2026-03-16 to 2026-03-22.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/19b_common_support_issues.csv`: 5 rows, 4 dates, 2026-04-14 to 2026-04-18.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18q_june_2026_ecmwf_single_run_forecasts/18q_june_2026_weather_issues.csv`: 2 rows, 1 dates, 2026-06-24 to 2026-06-24.
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/20a_issues.csv`: 11 rows, 0 dates,  to .
- `local:/Users/edwardlee/Desktop/2026MScWeatherForecastingPolymarket/data/processed/18o_june_2026_hko_realised_outcomes/18o_june_2026_outcome_issues.csv`: 1 rows, 0 dates,  to .

## Notebook 02 admission rules

A forecast row is admitted only when:

1. the model product and cycle are declared;
2. the forecast issue time precedes the decision time;
3. the full Hong Kong local day contains 24 unique hours;
4. no later forecast is substituted for a missing run;
5. the HKO outcome is used only as the supervised target;
6. the settlement date remains the uncertainty unit;
7. training and market evaluation samples are recorded separately.

The inventory does not itself admit any forecast row.
