# HKO daily maximum temperature

## Target

The empirical settlement variable is the Hong Kong Observatory's official
Absolute Daily Maximum Temperature at the Hong Kong Observatory.

Values are retained at the official one-decimal Celsius precision.

## Period

16 March 2024 through 31 August 2026 inclusive.

The target interval contains 899 calendar dates.

## Historical source

Historical observations are independently reacquired from the HKO Open Data API:

- data type: `CLMMAXT`;
- station: `HKO`;
- variable: Daily Maximum Temperature.

## Current-year Daily Extract

The HKO Climate Information Service Daily Extract webpage uses two official
machine-readable forms:

- `dailyExtract_YYYY.xml`;
- `dailyExtract_YYYYMM.xml`.

The webpage uses the YYYYMM file only while a requested month is in
daily-update mode; otherwise it uses the YYYY file.

The final pipeline therefore checks the official current-year file first and
uses the current-month form as a fallback. A source is accepted only when it is
valid JSON and contains a non-empty August 2026 block.

Within the HKO Daily Extract structure:

- `dayData[k][0]` is Day;
- `dayData[k][2]` is Absolute Daily Maximum Temperature.

## Source reconciliation

If the historical CLMMAXT source and Daily Extract both contain the same date,
their maximum-temperature observations must agree exactly.

Any disagreement causes the empirical pipeline to stop.

## Current-day protection

A value for the still-running Hong Kong calendar day is never accepted as a
final daily settlement observation.

Hence, while 31 August is still underway, the valid intermediate state is:

- 898 observations;
- only 31 August missing;
- status `PENDING_FINAL_DATE`.

The final thesis release requires:

- 899 observations;
- no missing dates;
- status `COMPLETE`.

## Historical audit

The independently rebuilt HKO target series is reconciled against the previously
audited Version-2 weather panel for 16 March 2024 through 15 March 2026.

The expected audit result is:

- 730 distinct dates;
- zero mismatches.

Historical files are audit references only and do not supply observations to
the final canonical series.
