# 18o June 2026 HKO realised-outcome report

Generated at UTC: `2026-07-21T04:19:44.610497+00:00`

## Overall judgement

**PASS_WITH_NONBLOCKING_SOURCE_WARNINGS**

## Outcome construction

Official daily maximum temperatures were obtained from the Hong Kong Observatory Open Data API for `CLMMAXT`, station `HKO`, and June 2026. The official Daily Extract and Monthly Weather Summary pages were archived as source evidence.

The one-decimal HKO value was used directly. No nearest-integer or nearest-bin rounding was applied.

## Sample flow

- Certified June dates received from 18n: 30
- Certified June contracts received from 18n: 330
- Official HKO daily maxima obtained: 30
- Contract outcome rows created: 330
- Winning contracts: 30
- Dates with exactly one winner: 30
- Date-level checks passed: 30
- Blocking issue rows: 0
- Non-blocking source warnings: 1

## Source cross-checks

- CSV–JSON API cross-check available: True
- CSV–JSON API cross-check passed: True
- Daily Extract table cross-check available: False
- Daily Extract table cross-check passed: None

## Winning contracts

| Date | HKO maximum | Winning label | Event type | Lower bound | Upper bound |
|---|---:|---|---|---:|---:|
| 2026-06-01 | 32.3 | 32°C | interior | 32.0 | 33.0 |
| 2026-06-02 | 33.3 | 33°C | interior | 33.0 | 34.0 |
| 2026-06-03 | 34.3 | 34°C or higher | upper | 34.0 |  |
| 2026-06-04 | 34.2 | 34°C or higher | upper | 34.0 |  |
| 2026-06-05 | 34.6 | 34°C | interior | 34.0 | 35.0 |
| 2026-06-06 | 30.4 | 30°C | interior | 30.0 | 31.0 |
| 2026-06-07 | 32.0 | 32°C | interior | 32.0 | 33.0 |
| 2026-06-08 | 30.9 | 30°C | interior | 30.0 | 31.0 |
| 2026-06-09 | 28.4 | 28°C | interior | 28.0 | 29.0 |
| 2026-06-10 | 28.6 | 28°C | interior | 28.0 | 29.0 |
| 2026-06-11 | 29.0 | 29°C | interior | 29.0 | 30.0 |
| 2026-06-12 | 30.4 | 30°C | interior | 30.0 | 31.0 |
| 2026-06-13 | 30.6 | 30°C | interior | 30.0 | 31.0 |
| 2026-06-14 | 29.5 | 29°C | interior | 29.0 | 30.0 |
| 2026-06-15 | 29.9 | 29°C | interior | 29.0 | 30.0 |
| 2026-06-16 | 27.1 | 27°C | interior | 27.0 | 28.0 |
| 2026-06-17 | 28.4 | 28°C | interior | 28.0 | 29.0 |
| 2026-06-18 | 29.0 | 29°C | interior | 29.0 | 30.0 |
| 2026-06-19 | 31.3 | 31°C | interior | 31.0 | 32.0 |
| 2026-06-20 | 31.5 | 31°C | interior | 31.0 | 32.0 |
| 2026-06-21 | 33.1 | 33°C | interior | 33.0 | 34.0 |
| 2026-06-22 | 33.0 | 33°C | interior | 33.0 | 34.0 |
| 2026-06-23 | 32.2 | 32°C | interior | 32.0 | 33.0 |
| 2026-06-24 | 32.8 | 32°C | interior | 32.0 | 33.0 |
| 2026-06-25 | 32.9 | 32°C | interior | 32.0 | 33.0 |
| 2026-06-26 | 31.6 | 31°C | interior | 31.0 | 32.0 |
| 2026-06-27 | 30.2 | 30°C | interior | 30.0 | 31.0 |
| 2026-06-28 | 30.0 | 30°C | interior | 30.0 | 31.0 |
| 2026-06-29 | 31.6 | 31°C | interior | 31.0 | 32.0 |
| 2026-06-30 | 32.1 | 32°C | interior | 32.0 | 33.0 |

## Event-set convention

- Upper tail: `[K, infinity)`.
- Interior label `k°C`: `[k, k+1)`.
- Lower endpoint `k°C or below`: `(-infinity, k+1)`.

Only dates passing the outcome audit may proceed to June market-history and deterministic-weather reconstruction.
