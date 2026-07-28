# Phase 12 Robustness, Attribution and Final Empirical Synthesis

## Status

PASSED

## Evidential design

Phase 12 does not alter the Phase 11 strategy. The primary decision rule
remains `event_day_open`, the value-gap threshold remains
0.120, and the reference transaction cost
remains 0.010 per Yes share.

All threshold and rule-selection robustness exercises use only the
March-May strategy-selection period. June is used only for evaluation,
attribution and explicitly labelled post-hoc sensitivity analysis.

## Reproduction of Phase 11

The Phase 11 threshold grid and one-standard-error selection procedure
were reproduced from the saved candidate contract panel. All four
frozen thresholds and the primary decision rule were recovered exactly.

## Leave-one-date-out selection stability

Each March-May target date was omitted in turn. Thresholds and the
primary decision rule were then reselected from the remaining dates.

| Decision rule | Frozen threshold | LODO minimum | LODO maximum | Same-threshold fraction | Primary-rule fraction |
|---|---:|---:|---:|---:|---:|
| 24h_prior | 0.130 | 0.120 | 0.140 | 0.940 | 0.075 |
| 12h_prior | 0.170 | 0.160 | 0.170 | 0.851 | 0.000 |
| 6h_prior | 0.120 | 0.100 | 0.180 | 0.627 | 0.000 |
| event_day_open | 0.120 | 0.120 | 0.130 | 0.940 | 0.925 |

For the frozen primary rule:

- Fraction of omissions that reproduced the exact frozen threshold:
  0.940.
- Fraction of omissions that retained the same primary decision rule:
  0.925.
- Leave-one-date-out threshold range:
  [0.120,
   0.130].

These diagnostics quantify how strongly the selected specification
depends on individual March-May dates.

## Multiple-strategy adjustment

The search considered
104
rule-threshold strategies. Dates were resampled jointly across all
strategies after each strategy return series had been centred, thereby
preserving cross-strategy dependence.

- Best observed training strategy:
  `event_day_open|threshold=0.090`.
- Best observed mean date PnL:
  0.085552.
- Selection-adjusted bootstrap critical value:
  0.093384.
- Selection-adjusted p-value:
  0.0741.
- Selection-adjusted evidence of a positive strategy mean:
  no.

This adjustment addresses the optimism created by examining multiple
decision rules and thresholds before selecting one strategy.

## June cost robustness

The frozen primary strategy has an analytical June break-even
transaction cost of approximately
0.011469
per share.

| Cost | Trades | Total net PnL | Return on capital | Maximum drawdown |
|---:|---:|---:|---:|---:|
| 0.0000 | 16 | 0.183500 | 0.224740 | 0.666500 |
| 0.0025 | 16 | 0.143500 | 0.167542 | 0.699000 |
| 0.0050 | 16 | 0.103500 | 0.115449 | 0.731500 |
| 0.0075 | 16 | 0.063500 | 0.067806 | 0.764000 |
| 0.0100 | 16 | 0.023500 | 0.024066 | 0.796500 |
| 0.0125 | 16 | -0.016500 | -0.016232 | 0.829000 |
| 0.0150 | 16 | -0.056500 | -0.053478 | 0.861500 |
| 0.0175 | 16 | -0.096500 | -0.088007 | 0.894000 |
| 0.0200 | 16 | -0.136500 | -0.120106 | 0.926500 |
| 0.0225 | 16 | -0.176500 | -0.150021 | 0.959000 |
| 0.0250 | 16 | -0.216500 | -0.177970 | 0.991500 |
| 0.0275 | 16 | -0.256500 | -0.204138 | 1.024000 |
| 0.0300 | 16 | -0.296500 | -0.228693 | 1.056500 |

The strategy therefore has only a narrow cost margin. Its sign changes
once transaction costs exceed the realised gross profit per trade.

## June trade concentration

At the reference cost:

- Trades:
  16.
- Winning trades:
  1.
- Losing trades:
  15.
- Largest winning trade:
  0.935000.
- Largest losing trade:
  -0.105000.
- Largest positive contribution as a share of all positive PnL:
  1.0000.
- Largest absolute contribution share:
  0.5064.
- Absolute-PnL Herfindahl index:
  0.2753.
- Total PnL remains positive after removing the best trade:
  no.

The concentration diagnostics are essential because an infrequent
long-Yes strategy can show a positive aggregate result despite most
individual trades losing.

## Event and temperature attribution

Event-type attribution separates lower-tail, interior and upper-tail
contracts. Temperature attribution uses March-May observed-temperature
terciles fixed before June:

- Cool to middle boundary:
  27.4000 degrees Celsius.
- Middle to hot boundary:
  29.2333 degrees Celsius.

The complete group-level results are recorded in
`phase12_event_type_attribution.csv` and
`phase12_temperature_bucket_attribution.csv`.

## Dependence across decision rules

The pairwise audit records value-gap correlations, trade-signal
correlations, PnL correlations, simultaneous-trade frequencies and the
frequency with which two decision rules select the same contract.

These results must not be interpreted as four independent strategy
experiments. Forecasts, contract books and realised temperatures are
shared across rules, creating substantial dependence.

## June proper-score comparison

On the 30-date June exact common support, the Phase 10 paired results
were:

| Metric | GP | Polymarket | GP minus market | 95% bootstrap interval |
|---|---:|---:|---:|---:|
| Mean binary Brier | 0.068198 | 0.058874 | 0.009324 | [0.003825, 0.014640] |
| Mean binary log | 0.225029 | 0.186401 | 0.038628 | [0.022004, 0.054204] |
| Categorical log | 1.618265 | 1.260923 | 0.357342 | [0.214437, 0.492830] |
| Multiclass Brier | 0.750180 | 0.648471 | 0.101710 | [0.043014, 0.158161] |

All reported differences are GP score minus Polymarket score. Positive
differences therefore favour Polymarket.

The standalone June GP evaluation produced:

- Mean binary Brier score:
  0.067938.
- Mean binary log score:
  0.222722.
- Mean categorical log score:
  1.594539.
- Mean multiclass Brier score:
  0.747318.
- Mean continuous CRPS:
  0.615017 degrees Celsius.
- Mean GP absolute error:
  0.800929 degrees Celsius.

## Frozen June trading result

At the reference cost of 0.010 per share:

- Dates:
  30.
- Trades:
  16.
- Total net PnL:
  0.023500.
- Mean date net PnL:
  0.000783.
- Return on committed capital:
  0.024066.
- Maximum drawdown:
  0.796500.
- Post-hoc June rank among the
  104
  rule-threshold candidates:
  13.

The post-hoc rank is diagnostic only. It was not used to replace,
retune or improve the frozen Phase 11 strategy.

## Final empirical synthesis

The two-year weather-only residual sample allowed a materially more
credible GP construction than the original short-sample Gaussian
bridge. The Matérn 3/2 GP produced coherent full predictive
distributions and exact contract-event probabilities.

Nevertheless, June Polymarket prices achieved lower binary and
categorical proper scores on the exact complete-book intersection.
This indicates that the market incorporated information not captured
by the deterministic forecast and weather-only GP post-processing.

The frozen value-gap strategy produced a slightly positive June point
estimate at the reference cost, but the result was economically small,
highly uncertain, cost-sensitive and concentrated in infrequent
winning contracts. Threshold instability, multiple-strategy searching
and dependence across decision rules further weaken any claim of a
persistent trading advantage.

The defensible conclusion is therefore not that the GP generated a
reliable arbitrage strategy. Rather:

1. Weather-only GP post-processing can construct coherent probabilistic
   forecasts from deterministic weather forecasts.
2. Those probabilities were competitive in parts of the development
   sample but were inferior to Polymarket prices in June on all four
   primary proper-score comparisons.
3. Apparent value gaps did not translate into statistically or
   economically robust out-of-sample trading profits.
4. Market-price information remains valuable beyond the weather-only
   forecasting signal.

## Evidential boundary

This remains a historical simulation. It does not establish live
executability, future profitability or causal market efficiency.
Recorded prices may not represent obtainable fills. Queue priority,
partial execution, market impact, capital competition across
simultaneous contracts and operational latency are outside the
empirical design.

No missing forecast or price was imputed. No June observation was used
to change the frozen strategy.
