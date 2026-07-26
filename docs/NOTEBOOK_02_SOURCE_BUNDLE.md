# Notebook 02 Weather Source Bundle

Status: `NOTEBOOK02_SOURCE_BUNDLE_READY`

The earlier materialisation attempt omitted CSV files contained inside the preserved June review bundles. This version searches ordinary files and ZIP members across the current repository, local archives and the preserved Git archive.

## Sample separation

The weather training panel requires a historically available deterministic forecast and its later HKO outcome. It does not require a corresponding Polymarket market.

The market evaluation panel requires an audited market, a certified event book, a deterministic forecast and the HKO outcome. Model and market scores are computed only on exact common support.

## Forecast path rule

Hourly forecasts are converted to Asia/Hong_Kong time. A complete candidate local-day path requires 24 unique local hours. Exact run grouping and issue-time admission are applied by the next Notebook 02 adapter; this source bundle records the available raw evidence.

## Source coverage

### Daily Max Forecasts

- Unique files: 42
- Total rows: 186628
- Earliest date: 1884-01-01
- Latest date: 2026-06-30
- Latest date with at least 24 recorded local hours: 2026-06-30
- Maximum June dates in one file: 30
- Maximum complete June dates in one file: 30

### Fetch Inventory

- Unique files: 3
- Total rows: 645
- Earliest date: 1970-01-01
- Latest date: 2026-06-30
- Latest date with at least 24 recorded local hours: nan
- Maximum June dates in one file: 30
- Maximum complete June dates in one file: 0

### Hourly Forecasts

- Unique files: 8
- Total rows: 73120
- Earliest date: 2026-03-14
- Latest date: 2026-07-09
- Latest date with at least 24 recorded local hours: 2026-07-08
- Maximum June dates in one file: 30
- Maximum complete June dates in one file: 30

### Integrity Checks

- Unique files: 45
- Total rows: 545
- Earliest date: nan
- Latest date: nan
- Latest date with at least 24 recorded local hours: nan
- Maximum June dates in one file: 0
- Maximum complete June dates in one file: 0

### Issues

- Unique files: 7
- Total rows: 376
- Earliest date: 2026-03-16
- Latest date: 2026-06-24
- Latest date with at least 24 recorded local hours: nan
- Maximum June dates in one file: 1
- Maximum complete June dates in one file: 0

### Request Plan

- Unique files: 2
- Total rows: 412
- Earliest date: 2026-03-16
- Latest date: 2026-06-30
- Latest date with at least 24 recorded local hours: nan
- Maximum June dates in one file: 30
- Maximum complete June dates in one file: 0
