# Initial Scope Memo — 12 June 2026

## Project title

Weather Forecasting and Polymarket Trading

## Proposed initial scope

The project will begin with temperature-based Polymarket contracts, focusing on city-level daily maximum or minimum temperature events. The initial empirical scope will be deliberately narrow and data-dependent. Candidate cities include London, New York and Hong Kong, subject to market availability, settlement-source clarity and weather-data availability.

The first stage of the project will not attempt to train a full global weather foundation model from scratch. Instead, the core focus will be on building a robust post-processing framework that converts available weather forecasts into calibrated local temperature probabilities, which can then be compared with Polymarket-implied probabilities.

## Core research question

Can post-processed weather forecasts generate calibrated probabilities for Polymarket temperature contracts, and do discrepancies between model-implied probabilities and market-implied probabilities contain useful predictive or trading information?

This can be divided into three sub-questions:

1. How can continuous weather forecasts be converted into probabilities for binary or multi-outcome temperature contracts?
2. How do forecast-implied probabilities compare with Polymarket-implied probabilities across cities, lead times and contract types?
3. Can systematic discrepancies between model probabilities and market prices support simple paper-trading strategies?

## Methodology pipeline

The proposed empirical pipeline is:

weather forecast data
→ city-level post-processing
→ predictive temperature distribution
→ binary or multi-outcome contract probabilities
→ comparison with Polymarket-implied probabilities
→ scoring-rule and calibration analysis
→ paper-trading backtest.

For a binary threshold contract, the event can be written as:

Y = 1{T > threshold}

where T is the realised city-level temperature. If a forecast or post-processed model provides a predictive distribution for T, the model-implied probability is:

P(Y = 1) = P(T > threshold)

For multi-outcome temperature-bin contracts, each bin probability can be obtained from the predictive temperature distribution.

## Initial post-processing idea

A first baseline model may use a city-specific calibration equation:

T_obs = alpha_c + beta_c T_forecast + error

where T_obs is the realised temperature for city c, T_forecast is the raw forecast, and the residual error distribution is used to convert point forecasts into probabilities.

Possible extensions include lead-time-specific calibration, combining global and local forecast sources, quantile regression, CatBoost-based post-processing, or graph-based global-local modelling if the data supports it.

## Evaluation framework

The probability forecasts will be evaluated using:

* Brier score;
* log score;
* calibration and reliability diagrams;
* lead-time analysis;
* comparison between model-implied and market-implied probabilities;
* simple paper-trading backtests using expected-value signals.

The trading component will be treated as paper trading only. A simple rule is to buy YES only when the model probability exceeds the executable market price by a sufficiently large buffer to account for spread, slippage and model uncertainty.

## Data requirements

The project requires four main data components:

1. Polymarket market metadata: market question, city, event date, threshold or outcome bins, token IDs, close time and resolution rules.
2. Polymarket price data: market-implied probabilities, price history, bid-ask spreads, liquidity and trading activity where available.
3. Weather forecast data: 2m temperature forecasts with issue time, valid time and lead time.
4. Realised temperature data: ideally matching the exact source used for Polymarket settlement.

## Immediate feasibility checks

Before finalising the empirical scope, the next tasks are:

1. Build a small Polymarket market-universe table for temperature contracts.
2. Check whether historical prices and order-book data are accessible.
3. Identify the exact resolution source for several temperature contracts.
4. Test weather forecast data access for at least one city.
5. Build one complete mini-pipeline for one temperature contract.

## Key questions for supervisors

1. Is the narrowed focus on temperature-based Polymarket contracts appropriate?
2. Should the main novelty be the post-processing layer rather than training a global weather model from scratch?
3. Which forecast sources should be prioritised for 2m temperature?
4. Should the realised temperature source strictly match the Polymarket settlement source?
5. Is a city-specific calibration model a suitable first baseline?
6. What level of mathematical rigour is expected for the probability-conversion and trading framework?
7. By the next meeting, should the main output be a data audit, API demo, baseline model, or literature review?
