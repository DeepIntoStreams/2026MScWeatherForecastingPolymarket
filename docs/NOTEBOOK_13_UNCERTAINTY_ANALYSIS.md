# Notebook 13: Date-Level Uncertainty and Robustness Analysis

## Purpose

Notebook 13 quantifies finite-sample uncertainty around the empirical results
without changing any model or decision.

## Locked inputs

- Continuous evaluation:
  `outputs/diagnostics/07_continuous_prediction_and_outcome_panel.csv`
- Categorical weather evaluation:
  `outputs/diagnostics/10_locked_categorical_score_panel.csv`
- Model-market comparison:
  `outputs/diagnostics/11_common_support_book_score_panel.csv`
- Trading evaluation:
  `outputs/diagnostics/12_locked_trading_date_panel.csv`

## Uncertainty unit

The uncertainty unit is the settlement date.

Contracts and decision-rule observations belonging to the same date are not
treated as independent observations.

## Estimands

The analysis contains 6 estimands:

- continuous CRPS improvement;
- categorical log-score improvement after probability regularisation;
- categorical Brier-score improvement after probability regularisation;
- model-minus-market log-score improvement;
- model-minus-market Brier-score improvement;
- locked trading net payoff.

For loss scores, the effect is baseline loss minus comparator loss. Positive
values therefore favour the locked model. Trading uses realised net payoff
relative to no trade.

## Bootstrap

- Method: nonparametric settlement-date bootstrap
- Replicates: 20000
- Confidence level: 0.95
- Seed: 20260727

## Sign-flip diagnostic

- Method: paired settlement-date sign flip
- Exact enumeration up to:
  20 dates
- Monte Carlo repetitions:
  100000
- Seed: 20260728

The sign-flip result is a descriptive randomisation diagnostic rather than a
claim of population-level statistical significance.

## Main results

                                estimand                               estimand_label chronology_block  settlement_dates  mean_effect  standard_error  bootstrap_lower  bootstrap_upper  median_effect  positive_effect_share sign_flip_method  sign_flip_repetitions  sign_flip_two_sided_p_value                     positive_effect_interpretation
             continuous_crps_improvement                  Raw minus locked-model CRPS          holdout                10     1.411113        0.233908         0.938603         1.794626       1.526615               0.900000            exact                   1024                     0.003906    positive values favour the locked weather model
             continuous_crps_improvement                  Raw minus locked-model CRPS    external_test                30     1.196003        0.148831         0.900798         1.481071       1.214856               0.900000      monte_carlo                 100000                     0.000010    positive values favour the locked weather model
       categorical_log_score_improvement  Raw minus regularised categorical log score          holdout                10    -0.140714        0.146420        -0.388502         0.149661      -0.361607               0.300000            exact                   1024                     0.357422    positive values favour the locked weather model
       categorical_log_score_improvement  Raw minus regularised categorical log score    external_test                30    -0.521925        0.105034        -0.745918        -0.343338      -0.380720               0.033333      monte_carlo                 100000                     0.000010    positive values favour the locked weather model
           categorical_brier_improvement Raw minus regularised multiclass Brier score          holdout                10    -0.001090        0.000366        -0.001810        -0.000456      -0.000547               0.100000            exact                   1024                     0.003906    positive values favour the locked weather model
           categorical_brier_improvement Raw minus regularised multiclass Brier score    external_test                30    -0.000577        0.000239        -0.001016        -0.000097      -0.000714               0.266667      monte_carlo                 100000                     0.023090    positive values favour the locked weather model
model_minus_market_log_score_improvement     Market minus model categorical log score          holdout                10    -0.049364        0.115497        -0.246681         0.181087      -0.098505               0.400000            exact                   1024                     0.687500    positive values favour the locked weather model
model_minus_market_log_score_improvement     Market minus model categorical log score    external_test                30    -0.289732        0.088807        -0.470244        -0.132368      -0.325126               0.200000      monte_carlo                 100000                     0.000630    positive values favour the locked weather model
    model_minus_market_brier_improvement    Market minus model multiclass Brier score          holdout                10     0.000781        0.054870        -0.093496         0.109088      -0.050968               0.500000            exact                   1024                     0.992188    positive values favour the locked weather model
    model_minus_market_brier_improvement    Market minus model multiclass Brier score    external_test                30    -0.072339        0.028597        -0.125377        -0.015888      -0.113578               0.233333      monte_carlo                 100000                     0.017440    positive values favour the locked weather model
                      trading_net_payoff                   Locked strategy net payoff          holdout                10     0.056450        0.076965        -0.069550         0.210500       0.000000               0.200000            exact                   1024                     0.750000 positive values favour the locked trading strategy
                      trading_net_payoff                   Locked strategy net payoff    external_test                30    -0.019367        0.047537        -0.098783         0.078983      -0.095000               0.100000      monte_carlo                 100000                     0.686593 positive values favour the locked trading strategy

## Chronological discipline

- Weather model reselected: no
- Continuous calibration reselected: no
- Probability calibration reselected: no
- Trading strategy reselected: no
- Strategy refitted before the June block: no
- Holdout used for reselection: no
- June external block used for reselection: no

## Evidential boundary

The uncertainty calculations are descriptive finite-sample diagnostics. They do not establish population-level profitability, executable profitability or market inefficiency.

The reduced-form trading analysis does not model order-book depth, spread
crossing, partial fills, latency or market impact.
