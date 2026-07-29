# Version 2 Empirical Completion Release Notes

## Status

PASSED

## Freeze boundary

The Version 2 empirical programme is frozen from source commit
`45e9e51300e53bb2e0b637085d41650041e95cde` on branch `edward-v2-gp-depth-completion`. Phase 23 independently verifies the
Phase 22 evidence pack and the Phase 21 clean replay before creating the final
freeze commit and annotated tag.

## Final closed scope

All empirical gaps G01-G17 are closed. The completed scope comprises:

1. exact GP code-to-mathematics reconciliation;
2. raw deterministic and static Gaussian chronological benchmarks;
3. deterministic-error and missing-support analysis;
4. rule and validation-block GP stability;
5. calibration, sharpness, dependence and conditional-variance diagnostics;
6. exact-common-support GP-market comparison;
7. development-selected convex forecast combination;
8. clean-environment reproducibility;
9. consolidated thesis evidence and final independent freeze.

## Headline empirical results

- Raw point mean date CRPS:
  1.745684932.
- Static Gaussian mean date CRPS:
  0.911754550.
- Matern-3/2 GP mean date CRPS:
  0.863339999.
- Matern-3/2 minus static Gaussian CRPS:
  -0.048414551.
- Selected development-period GP combination weight:
  0.489.
- Post-hoc June oracle GP weight:
  0.000.

## Reproducibility result

Phases 15-20 replay successfully in a clean environment. The certified Phase 21
registry contains 116 passed artifact comparisons and zero failed comparisons.

## Interpretation boundary

The final empirical conclusion is not that the GP dominates Polymarket or
establishes arbitrage. The GP materially improves raw and static weather
benchmarks, but Polymarket performs better on June exact common support. The
development-selected pool improves on the GP but not on the market.
