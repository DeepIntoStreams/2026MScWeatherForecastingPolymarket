# 18n June 2026 Hong Kong contract-event audit

Generated at UTC: `2026-07-21T01:45:15.333065+00:00`

## Overall judgement

**PASS**

## Sample flow

- Requested June dates: 30
- Events found: 30
- PASS dates: 30
- REVIEW dates: 0
- FAIL dates: 0
- Contract rows retrieved: 330
- Contract rows belonging to PASS dates: 330
- Issue rows: 0

## Date-level audit

| Date | Found | Markets | Lower | Interior | Upper | Partition | Tokens | Status | Issues |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2026-06-01 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-02 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-03 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-04 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-05 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-06 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-07 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-08 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-09 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-10 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-11 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-12 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-13 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-14 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-15 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-16 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-17 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-18 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-19 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-20 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-21 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-22 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-23 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-24 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-25 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-26 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-27 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-28 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-29 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |
| 2026-06-30 | True | 11 | 1 | 9 | 1 | True | True | PASS |  |

## Acceptance rule

A date passes only when an exact June Hong Kong event is found; the event text evidences the HKO Daily Extract, Absolute Daily Maximum Temperature and one-decimal settlement convention; exactly eleven labels are parseable; the event sets comprise one lower endpoint, nine contiguous one-degree interior bins and one upper tail; and every contract has YES and NO CLOB token identifiers.

## Downstream use

Only PASS dates may proceed to the June realised-outcome, market-history and deterministic-weather extensions. REVIEW dates require manual source inspection. FAIL dates remain excluded.
