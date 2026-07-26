# Notebook 01 Real Source Migration

The archive was inspected structurally rather than by filename alone.

The contract source must produce complete eleven-event daily partitions. The
HKO source must produce one official one-decimal daily maximum per date. The
selected pair must contain at least seventy common dates and must assign
exactly one winning event on every retained date.

Canonical derived inputs remain local:

- `data/interim/canonical_contract_definitions.csv`
- `data/interim/hko_daily_max.csv`

Versioned evidence includes:

- source schema audit;
- selected archive paths;
- source and canonical-file hashes;
- date-level certification;
- executed Notebook 01.

Forecast-time HKO admissibility is not claimed by Notebook 01. It is handled
in Notebook 02.
