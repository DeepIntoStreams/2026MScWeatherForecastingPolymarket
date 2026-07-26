# 18uA chronological partition and folds

**PASS**

## Frozen date blocks

| Block | Dates | Date-rule rows | Model-ready rows | Contract cells |
|---|---:|---:|---:|---:|
| DEVELOPMENT | 38 | 152 | 144 | 1584 |
| EXTERNAL_TEST | 30 | 120 | 119 | 1309 |
| HISTORY_ONLY_WARMUP | 25 | 100 | 0 | 0 |
| INTERNAL_HOLDOUT | 10 | 40 | 40 | 440 |

## Development folds

| Fold | Start | End | Dates | Date-rule rows | Contract cells |
|---:|---|---|---:|---:|---:|
| 1 | 2026-04-12 | 2026-04-21 | 10 | 32 | 352 |
| 2 | 2026-04-22 | 2026-05-01 | 10 | 40 | 440 |
| 3 | 2026-05-02 | 2026-05-10 | 9 | 36 | 396 |
| 4 | 2026-05-11 | 2026-05-21 | 9 | 36 | 396 |

## Frozen boundary

The minimum same-rule history is sixteen. The internal holdout is 22-31 May and the external test is 1-30 June. Neither block may be used for model, calibrator or threshold selection.

Model family, score hierarchy, GP kernel, tree specification and calibration variant remain unselected.
