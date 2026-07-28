# Phase 11 Frozen Value-Gap Trading Evaluation

## Status

PASSED

## Strategy definition

For each target date and decision rule, the strategy identifies the
single contract with the largest value gap

`GP event probability minus raw Polymarket Yes price`.

A long Yes trade is executed only when this maximum gap is at least the
frozen rule-specific threshold. At most one Yes share is purchased in
each date-rule contract book.

The gross one-share PnL is

`realised Yes payoff minus entry price`.

Net PnL additionally deducts the stated transaction cost per share.

Decision rules are evaluated as separate deployment strategies. The
reported primary strategy does not combine sequential trades from
different decision rules on the same target date.

## Frozen selection procedure

All thresholds and the primary deployment rule were selected using only
the March-May weather-plus-market period.

For each decision rule:

1. Thresholds from
   0.00
   to
   0.25
   were evaluated in increments of
   0.01.
2. Selection used a transaction cost of
   0.010 per share.
3. Thresholds ordinarily required at least
   10
   training trades.
4. The largest threshold within one standard error of the best
   training mean date PnL was frozen.
5. The primary decision rule maximised training mean date PnL minus one
   standard error after rule-specific threshold selection.

June outcomes were not used at any selection stage.

## Frozen strategies

| Decision rule | Frozen threshold | Training trades | Training total net PnL | Selection score | Primary |
|---|---:|---:|---:|---:|---|
| 12h_prior | 0.170 | 10 | 0.498000 | -0.007844 | no |
| 24h_prior | 0.130 | 19 | 2.668000 | 0.013121 | no |
| 6h_prior | 0.120 | 34 | 1.230500 | -0.009026 | no |
| event_day_open | 0.120 | 42 | 4.495000 | 0.032297 | yes |

## Primary strategy

- Decision rule: `event_day_open`.
- Frozen value-gap threshold: 0.120.
- Stake convention: one Yes share.
- June dates evaluated:
  30.
- June trades at the reference cost:
  16.

## June transaction-cost sensitivity

| Cost | Dates | Trades | Total net PnL | Mean date PnL | Return on capital | Win rate | Max drawdown |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 30 | 16 | 0.183500 | 0.006117 | 0.2247 | 0.0625 | 0.666500 |
| 0.005 | 30 | 16 | 0.103500 | 0.003450 | 0.1154 | 0.0625 | 0.731500 |
| 0.010 | 30 | 16 | 0.023500 | 0.000783 | 0.0241 | 0.0625 | 0.796500 |
| 0.020 | 30 | 16 | -0.136500 | -0.004550 | -0.1201 | 0.0625 | 0.926500 |

## Primary June uncertainty at the reference cost

At a transaction cost of 0.010 per share:

- Total net PnL:
  0.023500.
- Mean net PnL per June date:
  0.000783.
- Return on committed capital:
  0.024066
  if capital was committed.
- Maximum drawdown:
  0.796500.
- Date-level bootstrap interval for total June net PnL:
  [-1.228025,
   2.178500].
- Bootstrap probability that total June net PnL is positive:
  0.4705.
- The bootstrap interval includes zero.

## Evidential boundary

This is a frozen historical trading simulation, not evidence of
realisable live execution. It assumes settlement at the binary payoff,
uses one-share positions, and represents transaction frictions through
the stated cost scenarios. It does not model queue position, partial
fills, slippage beyond the cost allowance, market impact, capital
constraints across simultaneous markets, or the operational ability to
trade at every recorded decision price.

No missing forecast or market price was imputed. No incomplete contract
book was traded. June was evaluated once after the threshold and primary
decision rule had been fixed.
