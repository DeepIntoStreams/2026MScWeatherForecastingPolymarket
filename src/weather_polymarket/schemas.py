"""Canonical table schemas for the clean empirical pipeline."""

from __future__ import annotations

CONTRACT_DEFINITION_COLUMNS = (
    "event_date",
    "event_id",
    "event_index",
    "contract_id",
    "token_id",
    "event_label",
    "lower_bound_c",
    "upper_bound_c",
    "lower_closed",
    "upper_closed",
    "settlement_source",
    "metadata_retrieved_utc",
)

HKO_DAILY_MAX_COLUMNS = (
    "event_date",
    "hko_daily_max_c",
    "source_reference",
    "source_retrieved_utc",
    "outcome_admissible_utc",
    "availability_basis",
)


def missing_columns(
    actual_columns,
    required_columns,
):
    actual = set(actual_columns)
    return [
        column
        for column in required_columns
        if column not in actual
    ]
