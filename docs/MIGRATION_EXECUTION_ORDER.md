# Migration Execution Order

The migration is performed in dependency order.

1. Notebook 00: configuration, source registry and manifests.
2. Notebook 01: settlement and event certification.
3. Notebook 02: weather training panel.
4. Notebook 03: market evaluation panel.
5. Notebook 04: GP code audit.
6. Notebook 05: model fitting and selection.
7. Notebook 06: probability construction and adjustment.
8. Notebook 07: external evaluation and inference.
9. Notebook 08: final trading and PnL.
10. Notebook 09: tables, figures and numerical audit.

No downstream notebook begins until the upstream data and integrity tests it depends on have passed.

## Immediate next migration

The next implementation task is Notebook 00 followed by Notebook 01.
Only the latest valid configuration, source-adapter and settlement logic identified in the migration map should be extracted.
