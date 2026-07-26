# Notebook 02 Support and Chronology Audit

Status: `SUPPORT_EXPANSION_REQUIRED`

## Current empirical support

- Weather training rows: 119.
- Weather training dates: 30.
- Training period: 2026-06-01 to 2026-06-30.
- Market evaluation rows: 119.
- Market evaluation dates: 30.
- Weather-only training dates: 0.

The software architecture separates model training from market evaluation, but the current realised date sets are identical. The empirical separation requested by the supervisors has therefore not yet been achieved.

## June support gap

- 2026-06-24, `6h_prior`: `NO_HOURLY_CANDIDATE_GROUP`; candidate groups=0; maximum local hours=0; reasons=not recorded.

## Earlier and later support

The source inventory tests only whether the request, hourly forecast and HKO sources contain the same date-rule keys. This is a recovery signal, not proof that a path is admissible.

- Source-level pre-June candidate dates: 0.
- Source-level June candidate dates: 30.
- Source-level post-June candidate dates with existing HKO outcomes: 0.
- Post-June HKO dates found in preserved local or Git sources: 4.

## Chronology decision

No training, development, holdout or external-test dates are assigned at this stage. Assigning them from a single 30-day month would create an arbitrary and weak validation design.

Model fitting remains blocked until:

1. an earlier weather-training period is recovered or acquired;
2. a later untouched period can be reserved;
3. the split dates are declared before fitting;
4. date-grouped chronological validation can be implemented.

The formal gate is recorded in:

`config/chronology_policy.yaml`
