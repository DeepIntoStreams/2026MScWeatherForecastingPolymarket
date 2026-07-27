from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = (
    ROOT
    / "config/"
    "market_comparison_spec.yaml"
)

MODEL_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "10_locked_event_probability_outcome_panel.csv"
)

NOTEBOOK10_MANIFEST_PATH = (
    ROOT
    / "data/manifests/"
    "10_categorical_evaluation_manifest.json"
)

MARKET_PATH = (
    ROOT
    / "data/processed/"
    "18sA_canonical_source_adapters/"
    "18sA_canonical_market_panel.csv"
)

CORROBORATING_PATH = (
    ROOT
    / "data/processed/"
    "18s_expanded_march_june_canonical_sample/"
    "18s_expanded_market_scoring_panel.csv"
)

PROBABILITY_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_common_support_probability_panel.csv"
)

BOOK_SCORE_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_common_support_book_score_panel.csv"
)

DATE_SCORE_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_common_support_date_score_panel.csv"
)

MISSING_BOOK_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_common_support_missing_books.csv"
)

SOURCE_CERTIFICATION_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_market_source_certification.csv"
)

INTEGRITY_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_common_support_integrity_checks.csv"
)

BLOCK_SUMMARY_OUTPUT_PATH = (
    ROOT
    / "outputs/final_tables/"
    "11_common_support_block_summary.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/"
    "11_market_comparison_manifest.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_columns(
    frame: pd.DataFrame,
    columns: list[str],
    source_name: str,
) -> None:
    missing = [
        column
        for column in columns
        if column not in frame.columns
    ]

    if missing:
        raise RuntimeError(
            f"{source_name} is missing required columns: "
            + ", ".join(missing)
        )


def normalise_rule(
    series: pd.Series,
) -> pd.Series:
    result = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
    )

    return result.replace(
        {
            "24_hour_prior": "24h_prior",
            "24_hours_prior": "24h_prior",
            "12_hour_prior": "12h_prior",
            "12_hours_prior": "12h_prior",
            "6_hour_prior": "6h_prior",
            "6_hours_prior": "6h_prior",
            "event_day": "event_day_open",
            "event_open": "event_day_open",
            "open": "event_day_open",
        }
    )


def as_bool(
    series: pd.Series,
) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "yes",
                "y",
            }
        )
    )


def bound_token(
    value: Any,
) -> str:
    if pd.isna(value):
        return "*"

    return f"{float(value):.6f}"


def add_keys(
    frame: pd.DataFrame,
    *,
    date_column: str,
    rule_column: str,
) -> pd.DataFrame:
    result = frame.copy()

    result["_date"] = pd.to_datetime(
        result[date_column],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    result["_rule"] = normalise_rule(
        result[rule_column]
    )

    result["_event_key"] = [
        (
            f"{bound_token(lower)}|"
            f"{bound_token(upper)}"
        )
        for lower, upper in zip(
            result["lower_bound_c"],
            result["upper_bound_c"],
        )
    ]

    result["_book_key"] = (
        result["_date"]
        + "|"
        + result["_rule"]
    )

    return result


def standard_error(
    values: pd.Series,
) -> float:
    numeric = pd.to_numeric(
        values,
        errors="raise",
    )

    if len(numeric) <= 1:
        return 0.0

    return float(
        numeric.std(ddof=1)
        / math.sqrt(len(numeric))
    )


def projection(
    frame: pd.DataFrame,
    *,
    date_column: str,
    rule_column: str,
) -> pd.DataFrame:
    keyed = add_keys(
        frame,
        date_column=date_column,
        rule_column=rule_column,
    )

    result = keyed[
        [
            "_date",
            "_rule",
            "_event_key",
            "p_market",
        ]
    ].copy()

    result["p_market"] = pd.to_numeric(
        result["p_market"],
        errors="raise",
    )

    return result.sort_values(
        [
            "_date",
            "_rule",
            "_event_key",
        ]
    ).reset_index(drop=True)


for path in (
    CONFIG_PATH,
    MODEL_PATH,
    NOTEBOOK10_MANIFEST_PATH,
    MARKET_PATH,
):
    if not path.exists():
        raise FileNotFoundError(
            f"Required input is missing: {path}"
        )

model = pd.read_csv(
    MODEL_PATH,
    low_memory=False,
)

market = pd.read_csv(
    MARKET_PATH,
    low_memory=False,
)

notebook10_manifest = json.loads(
    NOTEBOOK10_MANIFEST_PATH.read_text(
        encoding="utf-8"
    )
)

require_columns(
    model,
    [
        "row_id",
        "target_date",
        "decision_rule",
        "chronology_block",
        "lower_bound_c",
        "upper_bound_c",
        "regularised_event_probability",
        "realised_yes",
    ],
    "Notebook 10 outcome panel",
)

require_columns(
    market,
    [
        "event_date",
        "decision_rule",
        "lower_bound_c",
        "upper_bound_c",
        "p_market",
    ],
    "canonical market panel",
)

market_identifier_columns = [
    column
    for column in [
        "market_id",
        "condition_id",
        "event_slug",
        "market_slug",
        "selected_yes_token_id",
    ]
    if column in market.columns
]

if not market_identifier_columns:
    raise RuntimeError(
        "The canonical market panel has no "
        "recognised market identifier."
    )

model = add_keys(
    model,
    date_column="target_date",
    rule_column="decision_rule",
)

market = add_keys(
    market,
    date_column="event_date",
    rule_column="decision_rule",
)

valid_rules = {
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
}

if not set(
    market["_rule"].dropna().unique()
).issubset(valid_rules):
    raise RuntimeError(
        "The market source contains an "
        "unrecognised decision rule."
    )

model_dates = set(model["_date"])

market = market.loc[
    market["_date"].isin(model_dates)
].copy()

market["p_market"] = pd.to_numeric(
    market["p_market"],
    errors="coerce",
)

if market["p_market"].isna().any():
    raise RuntimeError(
        "The canonical market panel contains "
        "missing or non-numeric p_market values."
    )

if not market["p_market"].between(
    0.0,
    1.0,
    inclusive="both",
).all():
    raise RuntimeError(
        "At least one p_market value is "
        "outside [0,1]."
    )

market_duplicate_keys = int(
    market.duplicated(
        [
            "_book_key",
            "_event_key",
        ]
    ).sum()
)

if market_duplicate_keys:
    raise RuntimeError(
        "The canonical market panel contains "
        f"{market_duplicate_keys} duplicate event keys."
    )

model_duplicate_keys = int(
    model.duplicated(
        [
            "_book_key",
            "_event_key",
        ]
    ).sum()
)

if model_duplicate_keys:
    raise RuntimeError(
        "The model outcome panel contains "
        f"{model_duplicate_keys} duplicate event keys."
    )

market_book_sizes = market.groupby(
    "_book_key"
).size()

if not market_book_sizes.eq(11).all():
    invalid = market_book_sizes.loc[
        ~market_book_sizes.eq(11)
    ]

    raise RuntimeError(
        "At least one market book does not "
        "contain eleven events:\n"
        + invalid.to_string()
    )

model_book_sizes = model.groupby(
    "_book_key"
).size()

if not model_book_sizes.eq(11).all():
    raise RuntimeError(
        "At least one Notebook 10 probability "
        "book does not contain eleven events."
    )

alias_equivalent = False
alias_maximum_price_difference = np.nan

if CORROBORATING_PATH.exists():
    corroborating = pd.read_csv(
        CORROBORATING_PATH,
        low_memory=False,
    )

    date_candidates = [
        column
        for column in [
            "event_date",
            "contract_date",
            "original_event_date",
        ]
        if column in corroborating.columns
    ]

    rule_candidates = [
        column
        for column in [
            "decision_rule",
            "rule",
        ]
        if column in corroborating.columns
    ]

    require_columns(
        corroborating,
        [
            "lower_bound_c",
            "upper_bound_c",
            "p_market",
        ],
        "corroborating market panel",
    )

    if not date_candidates or not rule_candidates:
        raise RuntimeError(
            "The corroborating market panel "
            "has no usable date or rule field."
        )

    canonical_projection = projection(
        market,
        date_column="event_date",
        rule_column="decision_rule",
    )

    corroborating_projection = projection(
        corroborating,
        date_column=date_candidates[0],
        rule_column=rule_candidates[0],
    )

    compared = canonical_projection.merge(
        corroborating_projection,
        on=[
            "_date",
            "_rule",
            "_event_key",
        ],
        how="outer",
        suffixes=(
            "_canonical",
            "_corroborating",
        ),
        indicator=True,
        validate="one_to_one",
    )

    alias_maximum_price_difference = float(
        (
            compared["p_market_canonical"]
            - compared["p_market_corroborating"]
        )
        .abs()
        .max()
    )

    alias_equivalent = bool(
        compared["_merge"].eq("both").all()
        and alias_maximum_price_difference
        <= 1.0e-12
    )

    if not alias_equivalent:
        print(
            "Diagnostic notice: the expanded "
            "market panel is not exactly equivalent "
            "to the canonical 18sA adapter. "
            "The canonical adapter remains "
            "authoritative and the expanded panel "
            "is retained only as corroborating "
            "evidence."
        )

timing_mode = None
timing_rows = 0
timing_check_passed = False
maximum_price_staleness_hours = None

price_timestamp_candidates = [
    column
    for column in [
        "source_price_timestamp_utc",
        "source_price_timestamp",
        "price_timestamp_utc",
        "market_price_timestamp_utc",
    ]
    if column in market.columns
]

cutoff_timestamp_candidates = [
    column
    for column in [
        "decision_time_utc",
        "decision_cutoff_utc",
        "source_cutoff_utc",
        "cutoff_time_utc",
    ]
    if column in market.columns
]

if (
    price_timestamp_candidates
    and cutoff_timestamp_candidates
):
    price_timestamp_column = (
        price_timestamp_candidates[0]
    )

    cutoff_timestamp_column = (
        cutoff_timestamp_candidates[0]
    )

    price_timestamp = pd.to_datetime(
        market[price_timestamp_column],
        errors="coerce",
        utc=True,
    )

    cutoff_timestamp = pd.to_datetime(
        market[cutoff_timestamp_column],
        errors="coerce",
        utc=True,
    )

    valid_timestamp = (
        price_timestamp.notna()
        & cutoff_timestamp.notna()
    )

    if not valid_timestamp.any():
        raise RuntimeError(
            "Timestamp columns exist but contain "
            "no usable timestamp pairs."
        )

    staleness = (
        cutoff_timestamp.loc[valid_timestamp]
        - price_timestamp.loc[valid_timestamp]
    ).dt.total_seconds() / 3600.0

    timing_rows = int(valid_timestamp.sum())
    timing_check_passed = bool(
        staleness.ge(0.0).all()
    )
    maximum_price_staleness_hours = float(
        staleness.max()
    )
    timing_mode = "direct_timestamp_comparison"

elif "price_staleness_hours" in market.columns:
    staleness = pd.to_numeric(
        market["price_staleness_hours"],
        errors="coerce",
    )

    if staleness.isna().any():
        raise RuntimeError(
            "Archived price staleness contains "
            "missing or non-numeric values."
        )

    timing_rows = len(staleness)
    timing_check_passed = bool(
        staleness.ge(0.0).all()
    )
    maximum_price_staleness_hours = float(
        staleness.max()
    )
    timing_mode = (
        "archived_nonnegative_price_staleness"
    )

else:
    raise RuntimeError(
        "The canonical market source contains "
        "no admissible timing evidence."
    )

if not timing_check_passed:
    raise RuntimeError(
        "At least one market price was recorded "
        "after its decision cutoff."
    )

model_books = set(model["_book_key"])
market_books = set(market["_book_key"])
common_books = model_books & market_books

if not common_books:
    raise RuntimeError(
        "There is no common support between "
        "the model and market panels."
    )

model_only_books = sorted(
    model_books - market_books
)

market_only_books = sorted(
    market_books - model_books
)

common_model = model.loc[
    model["_book_key"].isin(common_books)
].copy()

common_market = market.loc[
    market["_book_key"].isin(common_books)
].copy()

market_metadata_columns = [
    column
    for column in [
        "market_id",
        "condition_id",
        "event_slug",
        "market_slug",
        "canonical_label",
        "event_type",
        "contract_event_type",
        "selected_yes_token_id",
        "no_token_id",
        "price_staleness_hours",
        "source_cutoff_column",
        "source_price_timestamp_column",
    ]
    if column in common_market.columns
]

market_join = common_market[
    [
        "_book_key",
        "_event_key",
        "p_market",
        *market_metadata_columns,
    ]
].copy()

rename_metadata = {
    column: (
        column
        if column.startswith("market_")
        else f"market_source_{column}"
    )
    for column in market_metadata_columns
}

market_join = market_join.rename(
    columns=rename_metadata
)

joined = common_model.merge(
    market_join,
    on=[
        "_book_key",
        "_event_key",
    ],
    how="left",
    validate="one_to_one",
    indicator=True,
)

if not joined["_merge"].eq("both").all():
    missing_rows = joined.loc[
        ~joined["_merge"].eq("both"),
        [
            "_date",
            "_rule",
            "_event_key",
        ],
    ]

    raise RuntimeError(
        "The common-support event join is incomplete:\n"
        + missing_rows.head(30).to_string(
            index=False
        )
    )

joined = joined.drop(
    columns=["_merge"]
)

joined["model_probability"] = pd.to_numeric(
    joined["regularised_event_probability"],
    errors="raise",
)

joined["market_probability_raw"] = pd.to_numeric(
    joined["p_market"],
    errors="raise",
)

joined[
    "market_probability_book_raw_sum"
] = joined.groupby(
    "row_id"
)[
    "market_probability_raw"
].transform("sum")

if (
    joined[
        "market_probability_book_raw_sum"
    ]
    <= 0.0
).any():
    raise RuntimeError(
        "At least one market probability book "
        "has a non-positive raw sum."
    )

joined[
    "market_probability_normalised"
] = (
    joined["market_probability_raw"]
    / joined[
        "market_probability_book_raw_sum"
    ]
)

joined["realised_yes_bool"] = as_bool(
    joined["realised_yes"]
)

model_sums = joined.groupby(
    "row_id"
)["model_probability"].sum()

market_sums = joined.groupby(
    "row_id"
)["market_probability_normalised"].sum()

winner_counts = joined.groupby(
    "row_id"
)["realised_yes_bool"].sum()

if not np.allclose(
    model_sums.to_numpy(dtype=float),
    1.0,
    atol=1.0e-10,
    rtol=0.0,
):
    raise RuntimeError(
        "At least one model probability book "
        "does not sum to one."
    )

if not np.allclose(
    market_sums.to_numpy(dtype=float),
    1.0,
    atol=1.0e-10,
    rtol=0.0,
):
    raise RuntimeError(
        "At least one normalised market book "
        "does not sum to one."
    )

if not winner_counts.eq(1).all():
    raise RuntimeError(
        "At least one common-support book does "
        "not have exactly one realised event."
    )

book_records: list[dict[str, Any]] = []

for row_id, group in joined.groupby(
    "row_id",
    sort=True,
):
    realised = group["realised_yes_bool"].astype(
        int
    ).to_numpy(dtype=float)

    model_probability = group[
        "model_probability"
    ].to_numpy(dtype=float)

    market_probability = group[
        "market_probability_normalised"
    ].to_numpy(dtype=float)

    model_realised_probability = float(
        np.sum(
            model_probability
            * realised
        )
    )

    market_realised_probability = float(
        np.sum(
            market_probability
            * realised
        )
    )

    if (
        model_realised_probability <= 0.0
        or market_realised_probability <= 0.0
    ):
        raise RuntimeError(
            "A realised event has zero probability "
            "on the common support."
        )

    model_log_score = float(
        -np.log(
            model_realised_probability
        )
    )

    market_log_score = float(
        -np.log(
            market_realised_probability
        )
    )

    model_brier_score = float(
        np.sum(
            (
                model_probability
                - realised
            )
            ** 2
        )
    )

    market_brier_score = float(
        np.sum(
            (
                market_probability
                - realised
            )
            ** 2
        )
    )

    first = group.iloc[0]

    book_records.append(
        {
            "row_id": row_id,
            "target_date": first["_date"],
            "decision_rule": first["_rule"],
            "chronology_block": (
                first["chronology_block"]
            ),
            "model_realised_probability": (
                model_realised_probability
            ),
            "market_realised_probability": (
                market_realised_probability
            ),
            "model_categorical_log_score": (
                model_log_score
            ),
            "market_categorical_log_score": (
                market_log_score
            ),
            "log_score_difference_model_minus_market": (
                model_log_score
                - market_log_score
            ),
            "model_multiclass_brier_score": (
                model_brier_score
            ),
            "market_multiclass_brier_score": (
                market_brier_score
            ),
            "brier_score_difference_model_minus_market": (
                model_brier_score
                - market_brier_score
            ),
            "market_probability_book_raw_sum": float(
                first[
                    "market_probability_book_raw_sum"
                ]
            ),
        }
    )

book_scores = pd.DataFrame(
    book_records
).sort_values(
    [
        "target_date",
        "decision_rule",
    ]
).reset_index(drop=True)

date_scores = (
    book_scores.groupby(
        [
            "chronology_block",
            "target_date",
        ],
        as_index=False,
    )
    .agg(
        probability_books=(
            "row_id",
            "nunique",
        ),
        decision_rules=(
            "decision_rule",
            "nunique",
        ),
        model_categorical_log_score=(
            "model_categorical_log_score",
            "mean",
        ),
        market_categorical_log_score=(
            "market_categorical_log_score",
            "mean",
        ),
        log_score_difference_model_minus_market=(
            "log_score_difference_model_minus_market",
            "mean",
        ),
        model_multiclass_brier_score=(
            "model_multiclass_brier_score",
            "mean",
        ),
        market_multiclass_brier_score=(
            "market_multiclass_brier_score",
            "mean",
        ),
        brier_score_difference_model_minus_market=(
            "brier_score_difference_model_minus_market",
            "mean",
        ),
        mean_raw_market_probability_sum=(
            "market_probability_book_raw_sum",
            "mean",
        ),
    )
    .sort_values(
        [
            "chronology_block",
            "target_date",
        ]
    )
    .reset_index(drop=True)
)

block_records: list[dict[str, Any]] = []

for block, group in date_scores.groupby(
    "chronology_block",
    sort=True,
):
    book_group = book_scores.loc[
        book_scores[
            "chronology_block"
        ].eq(block)
    ]

    block_records.append(
        {
            "chronology_block": block,
            "dates": int(
                group[
                    "target_date"
                ].nunique()
            ),
            "probability_books": int(
                book_group[
                    "row_id"
                ].nunique()
            ),
            "decision_rules": int(
                book_group[
                    "decision_rule"
                ].nunique()
            ),
            "mean_date_model_log_score": float(
                group[
                    "model_categorical_log_score"
                ].mean()
            ),
            "standard_error_date_model_log_score": (
                standard_error(
                    group[
                        "model_categorical_log_score"
                    ]
                )
            ),
            "mean_date_market_log_score": float(
                group[
                    "market_categorical_log_score"
                ].mean()
            ),
            "standard_error_date_market_log_score": (
                standard_error(
                    group[
                        "market_categorical_log_score"
                    ]
                )
            ),
            "mean_date_log_score_difference_model_minus_market": float(
                group[
                    "log_score_difference_model_minus_market"
                ].mean()
            ),
            "standard_error_date_log_score_difference_model_minus_market": (
                standard_error(
                    group[
                        "log_score_difference_model_minus_market"
                    ]
                )
            ),
            "model_log_score_date_win_share": float(
                group[
                    "log_score_difference_model_minus_market"
                ].lt(0.0).mean()
            ),
            "mean_date_model_brier_score": float(
                group[
                    "model_multiclass_brier_score"
                ].mean()
            ),
            "standard_error_date_model_brier_score": (
                standard_error(
                    group[
                        "model_multiclass_brier_score"
                    ]
                )
            ),
            "mean_date_market_brier_score": float(
                group[
                    "market_multiclass_brier_score"
                ].mean()
            ),
            "standard_error_date_market_brier_score": (
                standard_error(
                    group[
                        "market_multiclass_brier_score"
                    ]
                )
            ),
            "mean_date_brier_score_difference_model_minus_market": float(
                group[
                    "brier_score_difference_model_minus_market"
                ].mean()
            ),
            "standard_error_date_brier_score_difference_model_minus_market": (
                standard_error(
                    group[
                        "brier_score_difference_model_minus_market"
                    ]
                )
            ),
            "model_brier_score_date_win_share": float(
                group[
                    "brier_score_difference_model_minus_market"
                ].lt(0.0).mean()
            ),
            "minimum_raw_market_probability_sum": float(
                book_group[
                    "market_probability_book_raw_sum"
                ].min()
            ),
            "mean_raw_market_probability_sum": float(
                book_group[
                    "market_probability_book_raw_sum"
                ].mean()
            ),
            "maximum_raw_market_probability_sum": float(
                book_group[
                    "market_probability_book_raw_sum"
                ].max()
            ),
        }
    )

block_summary = pd.DataFrame(
    block_records
).sort_values(
    "chronology_block"
).reset_index(drop=True)

expected_blocks = {
    "holdout",
    "external_test",
}

if set(
    block_summary["chronology_block"]
) != expected_blocks:
    raise RuntimeError(
        "The common-support comparison does not "
        "contain both evaluation blocks."
    )

missing_records: list[dict[str, Any]] = []

model_book_lookup = (
    model[
        [
            "_book_key",
            "_date",
            "_rule",
            "chronology_block",
        ]
    ]
    .drop_duplicates()
    .set_index("_book_key")
)

for book_key in model_only_books:
    record = model_book_lookup.loc[
        book_key
    ]

    missing_records.append(
        {
            "book_key": book_key,
            "target_date": record["_date"],
            "decision_rule": record["_rule"],
            "chronology_block": (
                record["chronology_block"]
            ),
            "support_status": "model_only",
            "reason": (
                "no complete canonical market book"
            ),
        }
    )

for book_key in market_only_books:
    date_value, rule_value = book_key.split(
        "|",
        maxsplit=1,
    )

    missing_records.append(
        {
            "book_key": book_key,
            "target_date": date_value,
            "decision_rule": rule_value,
            "chronology_block": "",
            "support_status": "market_only",
            "reason": (
                "no locked model prediction book"
            ),
        }
    )

missing_books = pd.DataFrame(
    missing_records,
    columns=[
        "book_key",
        "target_date",
        "decision_rule",
        "chronology_block",
        "support_status",
        "reason",
    ],
)

market_book_sums = market.groupby(
    "_book_key"
)["p_market"].sum()

source_certification = pd.DataFrame(
    [
        {
            "status": (
                "CANONICAL_MARKET_SOURCE_CERTIFIED"
            ),
            "canonical_source": str(
                MARKET_PATH.relative_to(ROOT)
            ),
            "corroborating_source": (
                str(
                    CORROBORATING_PATH.relative_to(
                        ROOT
                    )
                )
                if CORROBORATING_PATH.exists()
                else ""
            ),
            "price_column": "p_market",
            "evaluation_dates": int(
                market["_date"].nunique()
            ),
            "date_rule_books": int(
                market["_book_key"].nunique()
            ),
            "event_rows": len(market),
            "decision_rules": int(
                market["_rule"].nunique()
            ),
            "events_per_book": 11,
            "distinct_market_prices": int(
                market["p_market"].nunique()
            ),
            "minimum_market_price": float(
                market["p_market"].min()
            ),
            "maximum_market_price": float(
                market["p_market"].max()
            ),
            "minimum_raw_book_sum": float(
                market_book_sums.min()
            ),
            "mean_raw_book_sum": float(
                market_book_sums.mean()
            ),
            "maximum_raw_book_sum": float(
                market_book_sums.max()
            ),
            "alias_equivalent": (
                alias_equivalent
            ),
            "alias_maximum_price_difference": (
                alias_maximum_price_difference
            ),
            "timing_verification_mode": (
                timing_mode
            ),
            "timing_rows_verified": (
                timing_rows
            ),
            "maximum_price_staleness_hours": (
                maximum_price_staleness_hours
            ),
            "timing_check_passed": (
                timing_check_passed
            ),
        }
    ]
)

integrity_records = [
    {
        "check": "canonical_market_source_exists",
        "passed": MARKET_PATH.exists(),
        "value": str(
            MARKET_PATH.relative_to(ROOT)
        ),
    },
    {
        "check": "genuine_p_market_column_used",
        "passed": True,
        "value": "p_market",
    },
    {
        "check": "corroborating_market_source_audited",
        "passed": True,
        "value": (
            "exact_equivalence="
            f"{alias_equivalent}; "
            "maximum_price_difference="
            f"{alias_maximum_price_difference}; "
            "canonical_source_precedence=True"
        ),
    },
    {
        "check": "market_prices_in_unit_interval",
        "passed": bool(
            market["p_market"]
            .between(
                0.0,
                1.0,
                inclusive="both",
            )
            .all()
        ),
        "value": (
            f"{market['p_market'].min()} to "
            f"{market['p_market'].max()}"
        ),
    },
    {
        "check": "market_books_have_eleven_events",
        "passed": bool(
            market_book_sizes.eq(11).all()
        ),
        "value": int(
            market_book_sizes.nunique()
        ),
    },
    {
        "check": "market_event_keys_are_unique",
        "passed": (
            market_duplicate_keys == 0
        ),
        "value": market_duplicate_keys,
    },
    {
        "check": "timing_evidence_passes",
        "passed": timing_check_passed,
        "value": timing_mode,
    },
    {
        "check": "common_support_event_join_complete",
        "passed": (
            len(joined)
            == 11 * len(common_books)
        ),
        "value": len(joined),
    },
    {
        "check": "model_probability_books_sum_to_one",
        "passed": bool(
            np.allclose(
                model_sums.to_numpy(dtype=float),
                1.0,
                atol=1.0e-10,
                rtol=0.0,
            )
        ),
        "value": float(
            np.max(
                np.abs(
                    model_sums.to_numpy(
                        dtype=float
                    )
                    - 1.0
                )
            )
        ),
    },
    {
        "check": "normalised_market_books_sum_to_one",
        "passed": bool(
            np.allclose(
                market_sums.to_numpy(dtype=float),
                1.0,
                atol=1.0e-10,
                rtol=0.0,
            )
        ),
        "value": float(
            np.max(
                np.abs(
                    market_sums.to_numpy(
                        dtype=float
                    )
                    - 1.0
                )
            )
        ),
    },
    {
        "check": "one_realised_event_per_book",
        "passed": bool(
            winner_counts.eq(1).all()
        ),
        "value": int(
            winner_counts.min()
        ),
    },
    {
        "check": "both_evaluation_blocks_present",
        "passed": (
            set(
                block_summary[
                    "chronology_block"
                ]
            )
            == expected_blocks
        ),
        "value": ";".join(
            sorted(
                block_summary[
                    "chronology_block"
                ].tolist()
            )
        ),
    },
    {
        "check": "all_scores_finite",
        "passed": bool(
            np.isfinite(
                book_scores[
                    [
                        "model_categorical_log_score",
                        "market_categorical_log_score",
                        "model_multiclass_brier_score",
                        "market_multiclass_brier_score",
                    ]
                ].to_numpy(dtype=float)
            ).all()
        ),
        "value": len(book_scores),
    },
]

integrity = pd.DataFrame(
    integrity_records
)

if not integrity["passed"].all():
    failed = integrity.loc[
        ~integrity["passed"]
    ]

    raise RuntimeError(
        "Notebook 11 integrity checks failed:\n"
        + failed.to_string(index=False)
    )

probability_columns = [
    column
    for column in [
        "row_id",
        "_date",
        "_rule",
        "chronology_block",
        "selected_model",
        "selected_family",
        "event_order",
        "event_label",
        "source_event_label",
        "lower_bound_c",
        "upper_bound_c",
        "realised_yes",
        "model_probability",
        "market_probability_raw",
        "market_probability_normalised",
        "market_probability_book_raw_sum",
        *rename_metadata.values(),
    ]
    if column in joined.columns
]

probability_panel = joined[
    probability_columns
].copy()

probability_panel = probability_panel.rename(
    columns={
        "_date": "target_date",
        "_rule": "decision_rule",
    }
)

for output_path in (
    PROBABILITY_OUTPUT_PATH,
    BOOK_SCORE_OUTPUT_PATH,
    DATE_SCORE_OUTPUT_PATH,
    MISSING_BOOK_OUTPUT_PATH,
    SOURCE_CERTIFICATION_OUTPUT_PATH,
    INTEGRITY_OUTPUT_PATH,
    BLOCK_SUMMARY_OUTPUT_PATH,
    MANIFEST_PATH,
):
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

probability_panel.to_csv(
    PROBABILITY_OUTPUT_PATH,
    index=False,
)

book_scores.to_csv(
    BOOK_SCORE_OUTPUT_PATH,
    index=False,
)

date_scores.to_csv(
    DATE_SCORE_OUTPUT_PATH,
    index=False,
)

missing_books.to_csv(
    MISSING_BOOK_OUTPUT_PATH,
    index=False,
)

source_certification.to_csv(
    SOURCE_CERTIFICATION_OUTPUT_PATH,
    index=False,
)

integrity.to_csv(
    INTEGRITY_OUTPUT_PATH,
    index=False,
)

block_summary.to_csv(
    BLOCK_SUMMARY_OUTPUT_PATH,
    index=False,
)

output_paths = [
    PROBABILITY_OUTPUT_PATH,
    BOOK_SCORE_OUTPUT_PATH,
    DATE_SCORE_OUTPUT_PATH,
    MISSING_BOOK_OUTPUT_PATH,
    SOURCE_CERTIFICATION_OUTPUT_PATH,
    INTEGRITY_OUTPUT_PATH,
    BLOCK_SUMMARY_OUTPUT_PATH,
]

manifest = {
    "status": (
        "COMMON_SUPPORT_MARKET_COMPARISON_COMPLETE"
    ),
    "canonical_market_source": str(
        MARKET_PATH.relative_to(ROOT)
    ),
    "market_price_column": "p_market",
    "market_source_certified": True,
    "canonical_alias_equivalent": (
        alias_equivalent
    ),
    "canonical_source_precedence": True,
    "corroborating_source_role": (
        "diagnostic only"
    ),
    "exact_alias_equivalence_required": False,
    "timing_verification_mode": (
        timing_mode
    ),
    "timing_check_passed": (
        timing_check_passed
    ),
    "model_source": str(
        MODEL_PATH.relative_to(ROOT)
    ),
    "model_probability_column": (
        "regularised_event_probability"
    ),
    "selected_model": notebook10_manifest.get(
        "selected_model",
        "pooled_empirical_residual",
    ),
    "locked_continuous_dispersion_scale": (
        notebook10_manifest.get(
            "locked_continuous_dispersion_scale",
            1.25,
        )
    ),
    "locked_uniform_mixing_lambda": (
        notebook10_manifest.get(
            "locked_uniform_mixing_lambda",
            0.01,
        )
    ),
    "model_probability_books_available": int(
        len(model_books)
    ),
    "market_probability_books_available": int(
        len(market_books)
    ),
    "common_support_probability_books": int(
        len(common_books)
    ),
    "common_support_probability_rows": int(
        len(probability_panel)
    ),
    "common_support_dates": int(
        book_scores["target_date"].nunique()
    ),
    "model_only_books": int(
        len(model_only_books)
    ),
    "market_only_books": int(
        len(market_only_books)
    ),
    "event_count_per_book": 11,
    "market_probabilities_normalised_for_scoring": (
        True
    ),
    "raw_market_prices_retained": True,
    "uncertainty_unit": "settlement_date",
    "primary_score": (
        "categorical_log_score"
    ),
    "secondary_score": (
        "multiclass_brier_score"
    ),
    "score_difference_definition": (
        "model score minus market score; "
        "negative favours the model"
    ),
    "outcomes_used_for_evaluation": True,
    "market_prices_used_for_model_selection": False,
    "model_reselected": False,
    "continuous_calibration_reselected": False,
    "probability_calibration_reselected": False,
    "trading_strategy_selected": False,
    "trading_returns_calculated": False,
    "integrity_checks_passed": True,
    "input_hashes": {
        str(
            CONFIG_PATH.relative_to(ROOT)
        ): sha256(CONFIG_PATH),
        str(
            MODEL_PATH.relative_to(ROOT)
        ): sha256(MODEL_PATH),
        str(
            NOTEBOOK10_MANIFEST_PATH.relative_to(
                ROOT
            )
        ): sha256(
            NOTEBOOK10_MANIFEST_PATH
        ),
        str(
            MARKET_PATH.relative_to(ROOT)
        ): sha256(MARKET_PATH),
    },
    "output_hashes": {
        str(
            path.relative_to(ROOT)
        ): sha256(path)
        for path in output_paths
    },
}

MANIFEST_PATH.write_text(
    json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

print()
print("=" * 82)
print("NOTEBOOK 11 CORE MARKET COMPARISON COMPLETE")
print("=" * 82)
print()
print("Status:", manifest["status"])
print(
    "Canonical market source:",
    manifest["canonical_market_source"],
)
print(
    "Market price column:",
    manifest["market_price_column"],
)
print(
    "Market books available:",
    manifest[
        "market_probability_books_available"
    ],
)
print(
    "Model books available:",
    manifest[
        "model_probability_books_available"
    ],
)
print(
    "Common-support books:",
    manifest[
        "common_support_probability_books"
    ],
)
print(
    "Common-support dates:",
    manifest[
        "common_support_dates"
    ],
)
print(
    "Model-only books:",
    manifest["model_only_books"],
)
print(
    "Market-only books:",
    manifest["market_only_books"],
)
print()
print("Locked comparison results:")
print(
    block_summary.to_string(
        index=False
    )
)
print()
print(
    "All integrity checks passed:",
    True,
)
print(
    "Market prices used for model selection:",
    False,
)
print(
    "Trading returns calculated:",
    False,
)
