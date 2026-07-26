# Canonical Data Schemas

## Contract definitions

Target:

`data/interim/canonical_contract_definitions.csv`

Required columns:

- `event_date`
- `event_id`
- `event_index`
- `contract_id`
- `token_id`
- `event_label`
- `lower_bound_c`
- `upper_bound_c`
- `lower_closed`
- `upper_closed`
- `settlement_source`
- `metadata_retrieved_utc`

## HKO daily maximum

Target:

`data/interim/hko_daily_max.csv`

Required columns:

- `event_date`
- `hko_daily_max_c`
- `source_reference`
- `source_retrieved_utc`
- `outcome_admissible_utc`
- `availability_basis`

## Certified event book

Target:

`data/processed/certified_event_books.csv`

It combines the contract definitions with the official HKO outcome and adds:

- `realised_yes`
- `certification_status`
- `certification_reason`

Every retained date must contain exactly eleven events and exactly one
realised YES outcome.
