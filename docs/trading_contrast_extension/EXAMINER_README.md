# Trading contrast extension — examiner guide

This directory documents one final exploratory trading extension to the certified March-August empirical pipeline.

The original 102-step empirical release remains unchanged. The extension compares the frozen conservative trading policy with a deliberately aggressive two-sided multi-contract strategy (TAEC-11) across Raw, Static Gaussian, RBF GP and Matérn-3/2 GP probabilities.

## What should be read first

1. `FINAL_THESIS_HANDOFF.md`
2. `STAGE3_RESULTS.md`
3. `STAGE4_RESULTS.md`
4. `STAGE5_RESULTS.md`

The thesis-ready numerical source is:

`outputs/trading_contrast_extension/thesis/generated/numbers.tex`

## Main empirical interpretation

The conservative fixed strategy remains the primary policy. TAEC-11 is an exploratory contrast only.

On the external common support, TAEC-11 is materially worse than the fixed policy for every forecast model. This difference remains resolved under the dependence-aware moving-block/Holm inference and robust to seven-observation support deletion and alternative block lengths.

TAEC-11 has positive pre-cost signed convergence point estimates for all four models, but these are not statistically resolved. Its baseline 0.02 round-trip cost is well above the empirical break-even cost for every model.

## Important caveats

TAEC-11 uses Polymarket probability snapshots as mark-to-market prices. Historical executable bid/ask fills are unavailable, so it must not be described as a fill-level or live-trading backtest.

The Greek-like quantities are finite-difference sensitivities to predictive-temperature perturbations. They are forecast-risk diagnostics, not Black-Scholes option Greeks.

Alternative thresholds, costs, block lengths and perturbations are robustness diagnostics only. External data are never used to replace the frozen policy.
