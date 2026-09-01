# March–June audit reconciliation

## Purpose

Original master-plan Steps 82–84 require the final March–August rebuild to
be reconciled against the previously audited empirical evidence.

This is not a requirement that every old number remain unchanged.

The previous empirical design used March–May for market development and June
for external evaluation. The final design uses March–June for development
and July–August for external validation.

Consequently the reconciliation separates:

- quantities that **must reproduce** because their sample and methodology are
  unchanged;
- quantities that are **expected to change** because the empirical allocation,
  support reconstruction or development selection changed;
- quantities that are **not directly comparable** because the evaluation
  period itself changed.

## Must-match quantities

- `weather_selected_kernel`: old `matern32`, current `matern32`, pass `True`.


## Expected changes

- `weather_raw_crps`: old `1.745685`, current `1.7856519742883377`. The two-year target calendar is retained, but the final pipeline rebuilt the deterministic ECMWF input panel under the certified chronological core-repair selection policy. The earlier raw CRPS is therefore a historical benchmark, not a must-match invariant.
- `weather_static_crps`: old `0.911755`, current `0.9454445048611128`. The target calendar is retained, but the deterministic forecast inputs feeding the residual distribution changed under the final certified ECMWF chronology. The earlier static CRPS is therefore expected to change.
- `weather_rbf_crps`: old `0.877561`, current `0.9194478416514682`. The final chronological weather reconstruction changed the underlying forecast-error panel. The earlier RBF CRPS is retained as a historical comparison rather than a must-match invariant.
- `weather_matern32_crps`: old `0.86334`, current `0.9089451169571919`. The final chronological weather reconstruction changed the underlying forecast-error panel. The earlier Matérn-3/2 CRPS is retained as a historical comparison; selection of Matérn-3/2 remains the invariant.
- `exact_common_dates`: old `97`, current `101`. Market reconstruction and chronology were rebuilt; June now belongs to development.
- `exact_common_books`: old `350`, current `389`. Improved market-event recovery and final March-June development support changed the exact common book inventory.
- `exact_common_event_rows`: old `3850`, current `4279`. Eleven-event books change mechanically with the rebuilt support inventory.
- `pool_weight_gp`: old `0.489`, current `0.188`. Old weight used March-May development. Final weight uses March-June development.
- `trading_rule`: old `event_day_open`, current `24h_prior`. Trading selection was rerun from zero on the final March-June development sample.
- `trading_threshold`: old `0.12`, current `0.15`. Threshold was reselected under the final March-June one-SE procedure.


## Interpretation

A changed pool weight, trading rule or trading threshold is not evidence of a
reproducibility failure because those selectors were deliberately rebuilt on
the new March–June development period.

A discrepancy in a quantity marked `must_match` is different: it blocks this
stage and must be investigated before any thesis-facing numbers are treated
as final.
