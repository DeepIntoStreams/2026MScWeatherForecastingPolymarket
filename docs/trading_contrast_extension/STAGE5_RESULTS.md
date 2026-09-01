# Final trading contrast extension — Stage 5

## Status

`PASS`

## Purpose

Stage 5 is a robustness and reality-check layer. It does not retune either strategy on external data. The frozen TAEC threshold remains 0.02 and the primary inferential block length remains seven common-support settlement-date observations.

## External transaction-cost break-even

```
   empirical_period         strategy    model  positions  gross_pre_cost_pnl  baseline_cost_per_position  baseline_net_pnl  break_even_cost_per_position  baseline_cost_minus_break_even  baseline_cost_exceeds_break_even
external_validation fixed_settlement matern32         12              2.5710                        0.01            2.4510                      0.214250                       -0.204250                             False
external_validation fixed_settlement      raw         61              1.0070                        0.01            0.3970                      0.016508                       -0.006508                             False
external_validation fixed_settlement      rbf         14              2.4210                        0.01            2.2810                      0.172929                       -0.162929                             False
external_validation fixed_settlement   static         14              2.4210                        0.01            2.2810                      0.172929                       -0.162929                             False
external_validation           taec11 matern32        383              2.3050                        0.02           -5.3550                      0.006018                        0.013982                              True
external_validation           taec11      raw        365              1.0390                        0.02           -6.2610                      0.002847                        0.017153                              True
external_validation           taec11      rbf        387              1.7065                        0.02           -6.0335                      0.004410                        0.015590                              True
external_validation           taec11   static        380              2.2505                        0.02           -5.3495                      0.005922                        0.014078                              True
```

## Diagnostic TAEC threshold sensitivity

```
   model  threshold  positions  gross_pre_cost_pnl  total_cost  net_pnl  is_frozen_baseline_threshold
     raw      0.010        399              1.1175        7.98  -6.8625                         False
  static      0.010        454              2.0570        9.08  -7.0230                         False
     rbf      0.010        457              2.1330        9.14  -7.0070                         False
matern32      0.010        460              1.9910        9.20  -7.2090                         False
     raw      0.015        377              1.1475        7.54  -6.3925                         False
  static      0.015        426              2.2830        8.52  -6.2370                         False
     rbf      0.015        422              2.2495        8.44  -6.1905                         False
matern32      0.015        423              1.9155        8.46  -6.5445                         False
     raw      0.020        365              1.0390        7.30  -6.2610                          True
  static      0.020        380              2.2505        7.60  -5.3495                          True
     rbf      0.020        387              1.7065        7.74  -6.0335                          True
matern32      0.020        383              2.3050        7.66  -5.3550                          True
     raw      0.025        355              0.9590        7.10  -6.1410                         False
  static      0.025        356              1.9930        7.12  -5.1270                         False
     rbf      0.025        358              2.1560        7.16  -5.0040                         False
matern32      0.025        355              2.2685        7.10  -4.8315                         False
     raw      0.030        342              0.9080        6.84  -5.9320                         False
  static      0.030        330              2.0550        6.60  -4.5450                         False
     rbf      0.030        332              2.1800        6.64  -4.4600                         False
matern32      0.030        331              2.1785        6.62  -4.4415                         False
     raw      0.040        327              0.6190        6.54  -5.9210                         False
  static      0.040        282              2.2935        5.64  -3.3465                         False
     rbf      0.040        282              2.4645        5.64  -3.1755                         False
matern32      0.040        289              2.2500        5.78  -3.5300                         False
     raw      0.050        301              0.6390        6.02  -5.3810                         False
  static      0.050        251              2.9005        5.02  -2.1195                         False
     rbf      0.050        252              2.7400        5.04  -2.3000                         False
matern32      0.050        248              3.0605        4.96  -1.8995                         False
     raw      0.075        267              0.7140        5.34  -4.6260                         False
  static      0.075        188              3.5010        3.76  -0.2590                         False
     rbf      0.075        188              3.6785        3.76  -0.0815                         False
matern32      0.075        184              3.7175        3.68   0.0375                         False
     raw      0.100        251              1.2950        5.02  -3.7250                         False
  static      0.100        134              3.3690        2.68   0.6890                         False
     rbf      0.100        134              3.3090        2.68   0.6290                         False
matern32      0.100        134              3.3060        2.68   0.6260                         False
     raw      0.150        215              1.1685        4.30  -3.1315                         False
  static      0.150         64              1.6040        1.28   0.3240                         False
     rbf      0.150         69              1.8090        1.38   0.4290                         False
matern32      0.150         63              1.7310        1.26   0.4710                         False
```

These threshold variants are diagnostic only. The best ex-post threshold is not promoted into a new trading rule.

## Open-only exit sensitivity

```
   empirical_period    model  positions  baseline_early_exit_net_pnl  open_only_net_pnl  open_only_minus_baseline  open_only_gross_pre_cost_pnl                                                                 execution_interpretation
external_validation matern32        383                      -5.3550            -3.7490              1.606000e+00                        3.9110 All baseline TAEC positions are forced to event-day-open exit; no early target-hit exit.
external_validation      raw        365                      -6.2610            -6.2610             -8.528334e-16                        1.0390 All baseline TAEC positions are forced to event-day-open exit; no early target-hit exit.
external_validation      rbf        387                      -6.0335            -4.5135              1.520000e+00                        3.2265 All baseline TAEC positions are forced to event-day-open exit; no early target-hit exit.
external_validation   static        380                      -5.3495            -3.6155              1.734000e+00                        3.9845 All baseline TAEC positions are forced to event-day-open exit; no early target-hit exit.
```

Because historical executable bid/ask quotes are unavailable, TAEC remains a snapshot-price mark-to-market study rather than a fill-level backtest. The cost grid and open-only exit counterfactual quantify sensitivity to this limitation without claiming to eliminate it.

## Seven-observation support deletion: TAEC minus Fixed

```
   model  baseline_taec_minus_fixed  min_after_deleting_any_7_observation_block  max_after_deleting_any_7_observation_block  taec_remains_worse_for_every_deletion_window
     raw                    -6.6580                                     -6.9370                                     -4.3235                                          True
  static                    -7.6305                                     -8.9985                                     -5.0490                                          True
     rbf                    -8.3145                                     -9.5775                                     -5.6945                                          True
matern32                    -7.8060                                     -9.0190                                     -5.4160                                          True
```

## Moving-block-length sensitivity

```
           contrast    model  min_p_value  max_p_value  significant_block_lengths  total_block_lengths  all_block_lengths_same_sign
fixed_profitability matern32     0.007399     0.112389                          2                    5                         True
fixed_profitability      raw     0.851715     0.876912                          0                    5                         True
fixed_profitability      rbf     0.006399     0.118188                          2                    5                         True
fixed_profitability   static     0.007599     0.114389                          2                    5                         True
precost_convergence matern32     0.169983     0.319868                          0                    5                         True
precost_convergence      raw     0.495250     0.592841                          0                    5                         True
precost_convergence      rbf     0.358664     0.474753                          0                    5                         True
precost_convergence   static     0.239076     0.366463                          0                    5                         True
   taec_minus_fixed matern32     0.000200     0.002000                          5                    5                         True
   taec_minus_fixed      raw     0.000100     0.002200                          5                    5                         True
   taec_minus_fixed      rbf     0.000200     0.001700                          5                    5                         True
   taec_minus_fixed   static     0.000100     0.004600                          5                    5                         True
```

The Stage-4 seven-observation block remains the primary procedure. Alternative block lengths are a robustness diagnostic only.

## Temperature perturbation robustness

```
        strategy    model  baseline_total_pnl  local_plus_minus_0_25_min_pnl  local_plus_minus_0_25_max_pnl  local_sign_preserved  plus_minus_1_min_pnl  plus_minus_1_max_pnl  mean_local_position_jaccard  min_local_position_jaccard
fixed_settlement matern32              2.4510                         2.2810                         2.5270                  True               -0.4725                0.5800                     0.886905                    0.857143
fixed_settlement      raw              0.3970                        -1.6890                         1.5030                 False               -2.0990                3.3990                     0.659559                    0.525000
fixed_settlement      rbf              2.2810                         1.2185                         2.5270                  True               -0.4475                0.5800                     0.726190                    0.666667
fixed_settlement   static              2.2810                         2.0960                         2.4510                  True               -0.6695                0.5450                     0.866071                    0.857143
          taec11 matern32             -5.3550                        -5.4495                        -5.3675                  True               -7.2190               -4.8425                     0.847373                    0.846336
          taec11      raw             -6.2610                        -7.2905                        -5.7740                  True               -8.1265               -6.6350                     0.880820                    0.830424
          taec11      rbf             -6.0335                        -5.5305                        -5.2245                  True               -7.3040               -4.4645                     0.832126                    0.830918
          taec11   static             -5.3495                        -5.9100                        -5.1645                  True               -7.4270               -4.3840                     0.828908                    0.828431
```

## Next stage

Stage 6 performs final thesis-value pruning, examiner-facing reproducibility audit, submission-ready numerical handoff and release closure. No new empirical strategy or model will be introduced after Stage 5.
