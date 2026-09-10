# Reproducibility runbook

From the repository root:

```bash
git checkout msc-trading-contrast-extension-final
bash scripts/trading_contrast_extension/reproduce_extension.sh audit
```

The script reconstructs the trading comparison outputs, runs the corresponding tests and checks the generated results against the recorded version.

Some internal filenames retain earlier development labels. `fixed` refers to the conservative strategy and `taec` refers to the multi-contract strategy. These filenames are retained so that the recorded output paths remain unchanged.

The check does not refit the weather models or use the external evaluation period to reselect the conservative strategy.

After checking the tagged version, return to the current repository view with:

```bash
git switch main
```
