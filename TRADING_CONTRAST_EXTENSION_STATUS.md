# Trading strategy comparison

The trading strategy comparison is complete.

It compares the conservative and multi-contract strategies using the Raw deterministic forecast, Static Gaussian Model, RBF GP and Matérn-3/2 GP probabilities. The external evaluation period is not used to refit the weather models or reselect the conservative strategy.

The comparison includes trading ledgers, performance and risk measures, statistical inference, transaction cost analysis and sensitivity checks.

The recorded version is tagged:

```text
msc-trading-contrast-extension-final
```

The corresponding check is:

```bash
git checkout msc-trading-contrast-extension-final
bash scripts/trading_contrast_extension/reproduce_extension.sh audit
```
