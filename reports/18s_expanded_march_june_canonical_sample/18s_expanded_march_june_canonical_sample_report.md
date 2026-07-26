# 18s expanded March–June canonical sample freeze

**PASS**

## Pipeline structure

The release is divided into an 18sA schema-adapter stage and an 18sB aggregation-and-freeze stage.

## Frozen empirical universe

- Certified contracts: 1,133
- Certified dates: 103
- Contract-decision candidates: 4,532
- Market-ready rows: 4,186
- Weather-ready rows: 4,125
- Exact common-support rows: 3,889
- Common-support date-rule groups: 355
- Complete common-support books: 350
- Complete-book contract rows: 3,850
- Explicit support exclusions: 643

## Sample blocks

| Block | Contracts | Dates | Common rows | Complete books |
|---|---:|---:|---:|---:|
| March-May baseline | 803 | 73 | 2,635 | 236 |
| June external extension | 330 | 30 | 1,254 | 114 |
| **Total** | **1,133** | **103** | **3,889** | **350** |

## Support by decision rule

| Rule | Candidate | Market ready | Weather ready | Common rows | Common groups | Complete books |
|---|---:|---:|---:|---:|---:|---:|
| 24h_prior | 1133 | 976 | 1056 | 921 | 85 | 82 |
| 12h_prior | 1133 | 1055 | 1023 | 978 | 89 | 88 |
| 6h_prior | 1133 | 1077 | 1001 | 967 | 88 | 87 |
| event_day_open | 1133 | 1078 | 1045 | 1023 | 93 | 93 |

## Market binary scores on exact support

| Rule | n | Mean Brier | Mean log score |
|---|---:|---:|---:|
| 24h_prior | 921 | 0.06512791 | 0.20553391 |
| 12h_prior | 978 | 0.06356412 | 0.20303841 |
| 6h_prior | 967 | 0.06179428 | 0.19634249 |
| event_day_open | 1023 | 0.06265904 | 0.19721388 |

## Complete-book diagnostics

| Rule | Books | Normalised categorical log | Normalised multiclass Brier | Modal-set winner rate | Deterministic bin hit rate |
|---|---:|---:|---:|---:|---:|
| 24h_prior | 82 | 1.413647 | 0.711064 | 0.390244 | 0.060976 |
| 12h_prior | 88 | 1.406852 | 0.697627 | 0.397727 | 0.113636 |
| 6h_prior | 87 | 1.348701 | 0.676846 | 0.505747 | 0.126437 |
| event_day_open | 93 | 1.355432 | 0.686579 | 0.462366 | 0.075269 |

## Methodological boundary

No Gaussian-bridge probability or artificial ensemble feature is retained. The final modelling split and historical HKO outcome-publication admissibility remain deliberately unassigned.
