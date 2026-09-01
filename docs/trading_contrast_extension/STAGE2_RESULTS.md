# Final trading contrast extension — Stage 2

## Status

`PASS`

## Four-model probability panel

The canonical panel contains frozen Raw, Static Gaussian, RBF GP and Matérn-3/2 GP event probabilities together with raw Polymarket YES snapshots. No model is refitted.

## Conservative fixed strategy

The certified 24h-prior, h=0.15, one-YES-contract settlement strategy is applied identically across all four models. Existing Raw, Static and Matérn results must reproduce before new results are accepted.

## TAEC-11

The aggressive strategy freezes the 24h model probability, enters all two-sided discrepancies larger than 0.02, checks convergence at 12h and 6h, and forces remaining positions out at event-day open. PnL is snapshot-price mark-to-market convergence PnL and contains no settlement outcome term.

## Fixed summary

```
   empirical_period    model  dates  active_dates  positions  total_net_pnl  total_entry_capital
external_validation matern32     61            12         12         2.4510               0.5490
external_validation      raw     61            61         61         0.3970               7.6030
external_validation      rbf     61            14         14         2.2810               0.7190
external_validation   static     61            14         14         2.2810               0.7190
 market_development matern32     90            15         15         2.4715               1.5285
 market_development      raw     90            90         90        -8.2065              13.2065
 market_development      rbf     90            14         14         2.0060               1.9940
 market_development   static     90            14         14         2.0060               1.9940
```

## TAEC summary

```
   empirical_period    model  dates  active_dates  positions  yes_positions  no_positions  total_net_pnl  total_entry_capital  mean_gap_closed_fraction  target_hit_positions  forced_open_positions
external_validation matern32     61            61        383            211           172        -5.3550             140.2765                 -0.012067                    75                    308
external_validation      raw     61            61        365             61           304        -6.2610             258.8905                  0.024590                     0                    365
external_validation      rbf     61            61        380            206           174        -5.3495             142.8515                 -0.010112                    72                    308
external_validation   static     61            61        380            206           174        -5.3495             142.8515                 -0.010112                    72                    308
 market_development matern32     90            90        515            272           243        -5.2965             200.7290                  0.155316                   117                    398
 market_development      raw     90            90        500             90           410       -11.6640             346.3015                  0.039766                     0                    500
 market_development      rbf     90            90        502            260           242        -4.2160             201.4970                  0.134309                   125                    377
 market_development   static     90            90        502            260           242        -4.2160             201.4970                  0.134309                   125                    377
```

## Baseline reproduction

```
   model              period benchmark_source  expected_pnl  observed_pnl  absolute_difference  passed
     raw external_validation      numbers.tex         0.397         0.397         2.775558e-16    True
  static external_validation      numbers.tex         2.281         2.281         0.000000e+00    True
matern32 external_validation      numbers.tex         2.451         2.451         0.000000e+00    True
```

## Next stage

Compute performance, capital-efficiency, downside-risk, drawdown, concentration, convergence and Greek-like Delta/Gamma analytics for all eight model-strategy portfolios.
