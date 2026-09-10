# Trading strategy comparison

This directory contains the additional comparison between the conservative and multi-contract trading strategies.

Both strategies are evaluated using the Raw deterministic forecast, Static Gaussian Model, RBF GP and Matérn-3/2 GP probabilities. The conservative strategy remains the main trading specification used in the dissertation, while the multi-contract strategy provides a broader comparison of trading behaviour and transaction cost sensitivity.

## Main files

1. `STAGE2_RESULTS.md`
2. `STAGE3_RESULTS.md`
3. `STAGE4_RESULTS.md`
4. `STAGE5_RESULTS.md`

The main generated outputs are stored under:

```text
outputs/trading_contrast_extension/
```

## Reproduction

The recorded version is tagged `msc-trading-contrast-extension-final`.

```bash
git checkout msc-trading-contrast-extension-final
bash scripts/trading_contrast_extension/reproduce_extension.sh audit
```

Historical executable bid and ask fills are not available. The multi-contract results therefore use recorded Polymarket probability snapshots as the price proxy.

The reported temperature sensitivities are finite difference measures based on shifts in the predictive temperature distribution.
