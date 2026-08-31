# 31 August HKO refresh protocol

This protocol is used only after the official HKO Daily Extract settlement
for 31 August 2026 becomes available.

The refresh is an external-target completion, not a new model-selection
exercise.

## Frozen quantities that must not be reselected

- weather kernel: Matérn-3/2;
- pool selection period: March–June;
- trading rule: 24h prior;
- trading threshold: 0.15;
- reference trading cost: 0.01;
- event definitions and decision-time rules.

## Refresh sequence

1. Refresh/certify the HKO target series using the existing HKO module.
2. Verify that the HKO audit contains the 31 August target and no unexpected
   missing dates.
3. Rerun the frozen weather-model module only to update target-dependent
   external scoring/diagnostics.
4. Rerun the market-book module using cached/recovered market histories.
5. Verify that the development-selected pool weight remains 0.188.
6. Rerun the trading module.
7. Verify that the selected rule remains `24h_prior` and threshold remains
   `0.15`.
8. Rerun the synthesis module.
9. Compare the before/after external scores and PnL and document the exact
   effect of adding the final settlement date.
10. Commit the refresh separately so the audit trail remains explicit.

## Prohibited behaviour

Do not use the 31 August outcome to:

- select another GP kernel;
- alter the convex-pool weight;
- choose another trading decision rule;
- choose another probability-gap threshold;
- introduce a new trading strategy.

The only legitimate changes are target-dependent external metrics and files
whose hashes necessarily change because the final realised outcome has been
added.
