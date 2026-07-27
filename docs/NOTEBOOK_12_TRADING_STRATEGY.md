# Notebook 12: Development-Selected Trading Strategy

## Purpose

Notebook 12 selects a simple long-YES trading rule using development data and
evaluates the locked strategy separately on the holdout and June external
blocks.

## Inputs

- Development probabilities:
  `outputs/diagnostics/09_development_regularised_event_probability_panel.csv`
- Locked evaluation probabilities:
  `outputs/diagnostics/09_locked_regularised_event_probability_panel.csv`
- Canonical raw market prices:
  `data/processed/18sA_canonical_source_adapters/18sA_canonical_market_panel.csv`
- Certified outcomes:
  `data/processed/certified_event_books.csv`

## Development support

- Complete common-support dates:
  36
- Balanced four-rule dates:
  29
- Balanced books:
  116
- Balanced event rows:
  1276

Only dates with complete books for all four decision rules enter strategy
selection.

## Strategy

- Direction: buy YES only
- Maximum positions per settlement date: one
- Selection cost per trade: 0.01
- Minimum development trades: 8
- Strict development winner:
  `6h_prior__tau_0.030`
- Selected strategy:
  `24h_prior__tau_0.075`
- Selected decision rule:
  `24h_prior`
- Selected edge threshold:
  `0.075`
- Development trade count:
  25
- Development mean date net payoff:
  0.12000000

## Selection rule

The strict winner maximises mean settlement-date net payoff on development
data.

The final strategy applies a paired one-standard-error rule and prefers a
larger edge threshold when its development performance remains within one
paired standard error of the strict winner.

## Chronological discipline

- Holdout used for strategy selection: no
- June external data used for strategy selection: no
- Weather model reselected: no
- Continuous calibration reselected: no
- Probability calibration reselected: no
- Strategy refitted before June: no

## Evaluation results

chronology_block  calendar_dates  market_supported_dates  market_unsupported_dates    selected_strategy selected_rule  edge_threshold  cost_per_trade  trade_count  trade_share_all_calendar_dates  cumulative_gross_payoff  cumulative_net_payoff  mean_calendar_date_net_payoff  standard_error_calendar_date_net_payoff  mean_supported_date_net_payoff  trade_win_share  maximum_drawdown_net_payoff
         holdout              10                      10                         0 24h_prior__tau_0.075     24h_prior           0.075            0.01            4                        0.400000                   0.6045                 0.5645                       0.056450                                 0.076965                        0.056450         0.500000                       -0.325
   external_test              30                      27                         3 24h_prior__tau_0.075     24h_prior           0.075            0.01           26                        0.866667                  -0.3210                -0.5810                      -0.019367                                 0.047537                       -0.021519         0.115385                       -1.122

## Price convention

Raw Polymarket prices are used for trading. The categorically normalised prices
from Notebook 11 are not used.

## Interpretation

The exercise is reduced form. It does not model order-book depth, spread
crossing, partial fills, latency or market impact. Results therefore do not
establish executable profitability.
