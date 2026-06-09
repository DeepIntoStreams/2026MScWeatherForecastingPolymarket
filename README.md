# Weather Forecasting and Polymarket Trading

This repository contains code, notes and project materials for the MSc Financial Mathematics project on weather forecasting and Polymarket trading.

## Project aim

The project studies how weather forecast information can be converted into probabilistic trading signals for weather-related prediction markets, with an initial focus on temperature-based Polymarket contracts.

The current proposed direction is to focus on city-level temperature contracts, such as daily maximum or minimum temperature events. The project will compare model-implied probabilities derived from weather forecasts with market-implied probabilities from Polymarket prices. The empirical analysis will use proper scoring rules, calibration analysis and simple paper-trading backtests.

## Initial research direction

The initial empirical pipeline is:

1. Collect Polymarket weather-contract data.
2. Identify contract rules, outcome definitions and settlement sources.
3. Collect relevant weather forecast and realised temperature data.
4. Convert weather forecasts into predictive temperature distributions.
5. Convert these distributions into binary or multi-outcome contract probabilities.
6. Compare model-implied probabilities with Polymarket-implied probabilities.
7. Evaluate forecast quality using Brier score, log score and calibration analysis.
8. Test simple paper-trading strategies based on model-market probability discrepancies.

## Initial scope

The first working scope is deliberately narrow and data-dependent:

- Weather variable: 2m temperature.
- Market type: Polymarket temperature contracts.
- Contract type: daily maximum or minimum temperature; threshold or temperature-bin contracts.
- Candidate cities: London, New York, Hong Kong, subject to data availability.
- Main technical focus: probabilistic post-processing from forecast data to contract probabilities.

The scope may expand later to additional cities, multiple forecast sources, graph-based global-local models, or weather-related energy-market applications if data availability and project timing permit.

## Repository structure

```text
data/
  raw/              # Raw local data files, not committed to GitHub
  processed/        # Processed local data files, not committed to GitHub

notebooks/          # Exploratory notebooks and prototypes
src/                # Reusable Python functions and modules
literature_notes/   # Paper summaries and literature matrix
meeting_notes/      # Supervisor meeting notes and project planning
docs/               # Project memos and written planning documents
outputs/            # Local generated outputs, plots and tables, not committed
```

## Current tasks

1. Audit Polymarket temperature-market data availability.
2. Check available historical and real-time Polymarket price/order-book data.
3. Identify realised temperature sources used for contract settlement.
4. Audit weather forecast sources for 2m temperature and lead-time consistency.
5. Build one complete mini-pipeline for a single temperature contract.
6. Prepare narrowed scope and data-feasibility notes before the next supervisor meetings.
