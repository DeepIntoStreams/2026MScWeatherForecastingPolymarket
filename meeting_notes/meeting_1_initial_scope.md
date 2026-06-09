# Meeting 1 — Initial Project Scope

## Project

Weather Forecasting and Polymarket Trading

## Main discussion points

The project is broad and should be narrowed at the start. The initial focus should be temperature-based Polymarket contracts, because these provide a clear mapping between weather forecasts and binary or multi-outcome prediction-market payoffs.

The project should not initially aim to train a full global weather foundation model from scratch. Instead, the first empirical contribution should be a robust post-processing framework that converts available weather forecasts into calibrated local temperature probabilities.

## Proposed initial direction

weather forecasts  
→ local post-processing  
→ predictive temperature distribution  
→ Polymarket contract probability  
→ comparison with market-implied probability  
→ scoring-rule and calibration analysis  
→ simple paper-trading backtest.

## Candidate empirical focus

- Weather variable: 2m temperature.
- Contract type: daily maximum or minimum temperature.
- Market type: binary threshold or multi-outcome temperature-bin contracts.
- Candidate cities: London, New York, Hong Kong, subject to data availability.
- Main data sources to investigate: Polymarket API, ECMWF, Met Office, Open-Meteo, Windy and other realised temperature sources used by contract settlement rules.

## Key data questions

1. Which Polymarket temperature markets are available?
2. Can historical price data and order-book information be retrieved?
3. What realised weather source does each contract use for settlement?
4. Can historical weather forecasts be obtained with correct issue time and lead time?
5. Can global forecast data be mapped to the relevant local station or city-level outcome?

## Immediate next steps

1. Build a small Polymarket market-universe table.
2. Test Polymarket API access for one or two temperature markets.
3. Check realised settlement sources for selected markets.
4. Test one weather forecast source for 2m temperature.
5. Prepare a narrowed scope memo before the next meeting.
