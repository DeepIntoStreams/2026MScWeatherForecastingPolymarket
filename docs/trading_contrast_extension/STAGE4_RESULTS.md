# Final trading contrast extension — Stage 4

## Status

`PASS`

## Inferential status

This extension remains exploratory because TAEC-11 was conceived after the core March-August empirical study had been observed. Statistical inference is therefore used to quantify uncertainty and compare the two frozen strategy families, not to retroactively label the extension as a pristine confirmatory holdout experiment.

The external settlement date is the sampling unit. The primary dependence-aware procedure is a 7-consecutive-common-support-date moving-block bootstrap with 10,000 replications. Ordinary settlement-date resampling is retained as a dependence sensitivity check. Holm family-wise correction is applied within each pre-specified inferential family.

## External portfolio profitability

```
        strategy    model  mbb_observed_total  mbb_ci95_total_lower  mbb_ci95_total_upper  mbb_p_two_sided  holm_p_two_sided  holm_reject_5pct  dependence_sensitive_5pct
fixed_settlement      raw              0.3970             -4.230512              4.263200         0.872913          0.872913             False                      False
fixed_settlement   static              2.2810              0.267975              5.077013         0.085791          0.315968             False                      False
fixed_settlement      rbf              2.2810              0.262500              5.064025         0.081892          0.315968             False                      False
fixed_settlement matern32              2.4510              0.460987              5.249512         0.078992          0.315968             False                      False
          taec11      raw             -6.2610             -9.762525             -3.307338         0.000100          0.000800              True                      False
          taec11   static             -5.3495             -8.393537              0.127087         0.029297          0.146485             False                      False
          taec11      rbf             -6.0335             -8.859675             -0.910938         0.008899          0.062294             False                      False
          taec11 matern32             -5.3550             -8.317075             -0.436988         0.016398          0.098390             False                      False
```

## TAEC minus Fixed

```
   model  mbb_observed_total  mbb_ci95_total_lower  mbb_ci95_total_upper  mbb_p_two_sided  holm_p_two_sided  holm_reject_5pct
     raw             -6.6580             -9.684038             -3.223000           0.0002            0.0008              True
  static             -7.6305            -11.082762             -2.175987           0.0025            0.0040              True
     rbf             -8.3145            -11.681038             -2.945463           0.0011            0.0033              True
matern32             -7.8060            -11.253000             -2.754850           0.0020            0.0040              True
```

## Risk-adjusted Sharpe comparison

```
   model  mbb_observed_sharpe_difference  mbb_ci95_lower  mbb_ci95_upper  mbb_p_two_sided  holm_p_two_sided  holm_reject_5pct
     raw                       -0.509262       -0.816648       -0.270801         0.000600          0.002400              True
  static                       -0.502161       -0.770551       -0.129366         0.019598          0.049795              True
     rbf                       -0.555115       -0.818767       -0.166386         0.019798          0.049795              True
matern32                       -0.537050       -0.809347       -0.167254         0.016598          0.049795              True
```

## TAEC pre-cost convergence

```
   model  mbb_observed_total  mbb_ci95_total_lower  mbb_ci95_total_upper  mbb_p_two_sided  holm_p_two_sided  holm_reject_5pct
     raw              1.0390             -2.366637              4.076262         0.545045               1.0             False
  static              2.2505             -0.795000              7.710512         0.348365               1.0             False
     rbf              1.7065             -0.999062              6.993025         0.456254               1.0             False
matern32              2.3050             -0.581012              7.449562         0.309269               1.0             False
```

## Claims register

```
                         family                                       comparison  estimate                          estimate_type  mbb_ci95_lower  mbb_ci95_upper  mbb_p_two_sided   holm_p  holm_reject_5pct  dependence_sensitive_5pct                                                                                        interpretation      inference_status   sampling_unit                                primary_dependence_method
        portfolio_profitability                        fixed_settlement:raw vs 0  0.397000                 total external net PnL       -4.230512        4.263200         0.872913 0.872913             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
        portfolio_profitability                     fixed_settlement:static vs 0  2.281000                 total external net PnL        0.267975        5.077013         0.085791 0.315968             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
        portfolio_profitability                        fixed_settlement:rbf vs 0  2.281000                 total external net PnL        0.262500        5.064025         0.081892 0.315968             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
        portfolio_profitability                   fixed_settlement:matern32 vs 0  2.451000                 total external net PnL        0.460987        5.249512         0.078992 0.315968             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
        portfolio_profitability                                  taec11:raw vs 0 -6.261000                 total external net PnL       -9.762525       -3.307338         0.000100 0.000800              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
        portfolio_profitability                               taec11:static vs 0 -5.349500                 total external net PnL       -8.393537        0.127087         0.029297 0.146485             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
        portfolio_profitability                                  taec11:rbf vs 0 -6.033500                 total external net PnL       -8.859675       -0.910938         0.008899 0.062294             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
        portfolio_profitability                             taec11:matern32 vs 0 -5.355000                 total external net PnL       -8.317075       -0.436988         0.016398 0.098390             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                     raw - static -1.884000            paired total PnL difference       -8.523038        3.030137         0.559244 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                        raw - rbf -1.884000            paired total PnL difference       -8.671312        2.958038         0.569443 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                   raw - matern32 -2.054000            paired total PnL difference       -8.757663        2.970075         0.528647 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                     static - rbf  0.000000            paired total PnL difference        0.000000        0.000000         1.000000 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                static - matern32 -0.170000            paired total PnL difference       -0.425000        0.000000         0.238476 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                   rbf - matern32 -0.170000            paired total PnL difference       -0.425000        0.000000         0.238076 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                     raw - static -0.911500            paired total PnL difference       -6.903612        2.678088         0.750625 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                        raw - rbf -0.227500            paired total PnL difference       -5.989587        2.975162         0.937806 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                   raw - matern32 -0.906000            paired total PnL difference       -6.667063        2.514525         0.736226 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                     static - rbf  0.684000            paired total PnL difference        0.279000        1.210000         0.006999 0.041996              True                      False Statistically resolved positive effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                static - matern32  0.005500            paired total PnL difference       -0.272512        0.643512         0.989001 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
 within_strategy_model_pairwise                                   rbf - matern32 -0.678500            paired total PnL difference       -1.050000       -0.060500         0.012599 0.062994             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
      taec_minus_fixed_by_model                               TAEC - Fixed (raw) -6.658000      paired TAEC-minus-Fixed total PnL       -9.684038       -3.223000         0.000200 0.000800              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
      taec_minus_fixed_by_model                            TAEC - Fixed (static) -7.630500      paired TAEC-minus-Fixed total PnL      -11.082762       -2.175987         0.002500 0.004000              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
      taec_minus_fixed_by_model                               TAEC - Fixed (rbf) -8.314500      paired TAEC-minus-Fixed total PnL      -11.681038       -2.945463         0.001100 0.003300              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
      taec_minus_fixed_by_model                          TAEC - Fixed (matern32) -7.806000      paired TAEC-minus-Fixed total PnL      -11.253000       -2.754850         0.002000 0.004000              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
             market_convergence      TAEC signed pre-cost convergence (raw) vs 0  1.039000 TAEC pre-cost signed convergence total       -2.366637        4.076262         0.545045 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
             market_convergence   TAEC signed pre-cost convergence (static) vs 0  2.250500 TAEC pre-cost signed convergence total       -0.795000        7.710512         0.348365 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
             market_convergence      TAEC signed pre-cost convergence (rbf) vs 0  1.706500 TAEC pre-cost signed convergence total       -0.999062        6.993025         0.456254 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
             market_convergence TAEC signed pre-cost convergence (matern32) vs 0  2.305000 TAEC pre-cost signed convergence total       -0.581012        7.449562         0.309269 1.000000             False                      False             Not statistically resolved under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
risk_adjusted_sharpe_difference                Sharpe(TAEC) - Sharpe(Fixed), raw -0.509262        nonannualised Sharpe difference       -0.816648       -0.270801         0.000600 0.002400              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
risk_adjusted_sharpe_difference             Sharpe(TAEC) - Sharpe(Fixed), static -0.502161        nonannualised Sharpe difference       -0.770551       -0.129366         0.019598 0.049795              True                       True Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
risk_adjusted_sharpe_difference                Sharpe(TAEC) - Sharpe(Fixed), rbf -0.555115        nonannualised Sharpe difference       -0.818767       -0.166386         0.019798 0.049795              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
risk_adjusted_sharpe_difference           Sharpe(TAEC) - Sharpe(Fixed), matern32 -0.537050        nonannualised Sharpe difference       -0.809347       -0.167254         0.016598 0.049795              True                      False Statistically resolved negative effect under the 7-date moving-block bootstrap after Holm correction. EXPLORATORY_EXTENSION settlement_date 7-consecutive-common-support-date moving-block bootstrap
```

## Tail-risk guard

VaR, expected shortfall and maximum drawdown are accompanied by bootstrap uncertainty intervals, but Stage 4 does not manufacture conventional significance tests for these unstable tail functionals in a 61-date sample.

## Next stage

Stage 5 examines transaction-cost break-even levels, concentration, support, execution-proxy sensitivity and robustness of the aggressive-strategy findings before the final thesis-value pruning and release audit.
