# 18xC controlled-unblinding trading simulation

**PASS**

| Strategy | Block | Trades | Net PnL at 0.01 cost | Return on capital | Hit rate | Max drawdown |
|---|---|---:|---:|---:|---:|---:|
| GAUSSIAN_PROCESS_FAMILY | EXTERNAL_TEST | 22 | -1.0630 | -0.5153 | 0.0455 | -1.1975 |
| GAUSSIAN_PROCESS_FAMILY | INTERNAL_HOLDOUT | 5 | 0.5165 | 0.3482 | 0.4000 | -0.3730 |
| PRIMARY_OVERALL | EXTERNAL_TEST | 26 | -1.4925 | -0.5988 | 0.0385 | -1.4925 |
| PRIMARY_OVERALL | INTERNAL_HOLDOUT | 7 | 0.2625 | 0.3559 | 0.1429 | -0.5725 |
| TREE_FAMILY | EXTERNAL_TEST | 28 | -1.9275 | -1.0000 | 0.0000 | -1.9275 |
| TREE_FAMILY | INTERNAL_HOLDOUT | 9 | -0.5505 | -1.0000 | 0.0000 | -0.5505 |

The primary empirical strategy is profitable on the ten-date internal holdout but loses on the June external block. The GP family shows the same sign reversal, while the tree family is negative in both blocks.
