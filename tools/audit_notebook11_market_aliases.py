from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

CANONICAL_PATH = (
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

MODEL_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "10_locked_event_probability_outcome_panel.csv"
)

CSV_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_market_alias_difference_audit.csv"
)

JSON_OUTPUT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "11_market_alias_difference_audit.json"
)


def normalise_rule(series: pd.Series) -> pd.Series:
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


def bound_token(value: object) -> str:
    if pd.isna(value):
        return "*"

    return f"{float(value):.6f}"


def prepare(
    frame: pd.DataFrame,
    *,
    date_column: str,
    rule_column: str,
    source_name: str,
) -> pd.DataFrame:
    required = [
        date_column,
        rule_column,
        "lower_bound_c",
        "upper_bound_c",
        "p_market",
    ]

    missing = [
        column
        for column in required
        if column not in frame.columns
    ]

    if missing:
        raise RuntimeError(
            f"{source_name} is missing: "
            + ", ".join(missing)
        )

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

    result["p_market"] = pd.to_numeric(
        result["p_market"],
        errors="coerce",
    )

    return result


for path in (
    CANONICAL_PATH,
    CORROBORATING_PATH,
    MODEL_PATH,
):
    if not path.exists():
        raise FileNotFoundError(
            f"Required file is missing: {path}"
        )

canonical_raw = pd.read_csv(
    CANONICAL_PATH,
    low_memory=False,
)

corroborating_raw = pd.read_csv(
    CORROBORATING_PATH,
    low_memory=False,
)

model = pd.read_csv(
    MODEL_PATH,
    low_memory=False,
)

canonical = prepare(
    canonical_raw,
    date_column="event_date",
    rule_column="decision_rule",
    source_name="canonical market source",
)

corroborating_date_candidates = [
    column
    for column in (
        "event_date",
        "contract_date",
        "original_event_date",
    )
    if column in corroborating_raw.columns
]

corroborating_rule_candidates = [
    column
    for column in (
        "decision_rule",
        "rule",
    )
    if column in corroborating_raw.columns
]

if not corroborating_date_candidates:
    raise RuntimeError(
        "No usable corroborating date column."
    )

if not corroborating_rule_candidates:
    raise RuntimeError(
        "No usable corroborating rule column."
    )

corroborating = prepare(
    corroborating_raw,
    date_column=corroborating_date_candidates[0],
    rule_column=corroborating_rule_candidates[0],
    source_name="corroborating market source",
)

model_dates = set(
    pd.to_datetime(
        model["target_date"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")
)

canonical = canonical.loc[
    canonical["_date"].isin(model_dates)
].copy()

corroborating = corroborating.loc[
    corroborating["_date"].isin(model_dates)
].copy()

key_columns = [
    "_date",
    "_rule",
    "_event_key",
]

canonical_duplicate_keys = int(
    canonical.duplicated(
        key_columns
    ).sum()
)

corroborating_duplicate_keys = int(
    corroborating.duplicated(
        key_columns
    ).sum()
)

canonical_book_sizes = canonical.groupby(
    "_book_key"
).size()

corroborating_book_sizes = corroborating.groupby(
    "_book_key"
).size()

canonical_prices_valid = bool(
    canonical["p_market"].notna().all()
    and canonical["p_market"]
    .between(
        0.0,
        1.0,
        inclusive="both",
    )
    .all()
)

canonical_books_complete = bool(
    canonical_book_sizes.eq(11).all()
)

canonical_certified = bool(
    canonical_duplicate_keys == 0
    and canonical_prices_valid
    and canonical_books_complete
    and canonical["_date"].nunique() > 0
    and canonical["_book_key"].nunique() > 0
)

comparison = canonical[
    key_columns + ["p_market"]
].merge(
    corroborating[
        key_columns + ["p_market"]
    ],
    on=key_columns,
    how="outer",
    suffixes=(
        "_canonical",
        "_corroborating",
    ),
    indicator=True,
    validate="one_to_one",
)

comparison[
    "absolute_price_difference"
] = (
    comparison["p_market_canonical"]
    - comparison["p_market_corroborating"]
).abs()

comparison[
    "price_exactly_equal"
] = (
    comparison["_merge"].eq("both")
    & comparison[
        "absolute_price_difference"
    ].fillna(np.inf).le(1.0e-12)
)

both = comparison.loc[
    comparison["_merge"].eq("both")
].copy()

canonical_only = int(
    comparison["_merge"]
    .eq("left_only")
    .sum()
)

corroborating_only = int(
    comparison["_merge"]
    .eq("right_only")
    .sum()
)

differing_prices = int(
    (
        both[
            "absolute_price_difference"
        ]
        > 1.0e-12
    ).sum()
)

maximum_price_difference = (
    float(
        both[
            "absolute_price_difference"
        ].max()
    )
    if not both.empty
    else None
)

mean_price_difference = (
    float(
        both[
            "absolute_price_difference"
        ].mean()
    )
    if not both.empty
    else None
)

exact_equivalence = bool(
    canonical_only == 0
    and corroborating_only == 0
    and differing_prices == 0
)

audit = {
    "status": (
        "CANONICAL_SOURCE_CERTIFIED_WITH_ALIAS_AUDIT"
        if canonical_certified
        else "CANONICAL_SOURCE_CERTIFICATION_FAILED"
    ),
    "canonical_source": str(
        CANONICAL_PATH.relative_to(ROOT)
    ),
    "corroborating_source": str(
        CORROBORATING_PATH.relative_to(ROOT)
    ),
    "canonical_source_is_authoritative": True,
    "corroborating_source_is_diagnostic_only": True,
    "canonical_source_certified": canonical_certified,
    "canonical_rows": int(len(canonical)),
    "canonical_dates": int(
        canonical["_date"].nunique()
    ),
    "canonical_books": int(
        canonical["_book_key"].nunique()
    ),
    "canonical_decision_rules": int(
        canonical["_rule"].nunique()
    ),
    "canonical_duplicate_event_keys": (
        canonical_duplicate_keys
    ),
    "canonical_all_books_have_eleven_events": (
        canonical_books_complete
    ),
    "canonical_prices_in_unit_interval": (
        canonical_prices_valid
    ),
    "corroborating_rows": int(
        len(corroborating)
    ),
    "corroborating_dates": int(
        corroborating["_date"].nunique()
    ),
    "corroborating_books": int(
        corroborating["_book_key"].nunique()
    ),
    "corroborating_duplicate_event_keys": (
        corroborating_duplicate_keys
    ),
    "common_event_keys": int(
        len(both)
    ),
    "canonical_only_event_keys": (
        canonical_only
    ),
    "corroborating_only_event_keys": (
        corroborating_only
    ),
    "differing_common_prices": (
        differing_prices
    ),
    "maximum_absolute_price_difference": (
        maximum_price_difference
    ),
    "mean_absolute_price_difference": (
        mean_price_difference
    ),
    "exact_alias_equivalence": (
        exact_equivalence
    ),
    "exact_alias_equivalence_required": False,
    "decision": (
        "Use the canonical 18sA adapter. "
        "Retain the expanded panel only as "
        "non-binding corroborating evidence."
    ),
}

CSV_OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

pd.DataFrame(
    [
        {
            "canonical_source": (
                audit["canonical_source"]
            ),
            "corroborating_source": (
                audit["corroborating_source"]
            ),
            "canonical_source_certified": (
                audit[
                    "canonical_source_certified"
                ]
            ),
            "canonical_rows": (
                audit["canonical_rows"]
            ),
            "canonical_dates": (
                audit["canonical_dates"]
            ),
            "canonical_books": (
                audit["canonical_books"]
            ),
            "canonical_duplicate_event_keys": (
                audit[
                    "canonical_duplicate_event_keys"
                ]
            ),
            "canonical_all_books_have_eleven_events": (
                audit[
                    "canonical_all_books_have_eleven_events"
                ]
            ),
            "canonical_prices_in_unit_interval": (
                audit[
                    "canonical_prices_in_unit_interval"
                ]
            ),
            "common_event_keys": (
                audit["common_event_keys"]
            ),
            "canonical_only_event_keys": (
                audit[
                    "canonical_only_event_keys"
                ]
            ),
            "corroborating_only_event_keys": (
                audit[
                    "corroborating_only_event_keys"
                ]
            ),
            "differing_common_prices": (
                audit[
                    "differing_common_prices"
                ]
            ),
            "maximum_absolute_price_difference": (
                audit[
                    "maximum_absolute_price_difference"
                ]
            ),
            "exact_alias_equivalence": (
                audit[
                    "exact_alias_equivalence"
                ]
            ),
            "exact_alias_equivalence_required": False,
        }
    ]
).to_csv(
    CSV_OUTPUT_PATH,
    index=False,
)

JSON_OUTPUT_PATH.write_text(
    json.dumps(
        audit,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

print()
print("=" * 88)
print("NOTEBOOK 11 MARKET-ALIAS FORENSIC AUDIT")
print("=" * 88)
print()
print(
    "Canonical source certified:",
    canonical_certified,
)
print(
    "Canonical rows:",
    audit["canonical_rows"],
)
print(
    "Canonical dates:",
    audit["canonical_dates"],
)
print(
    "Canonical books:",
    audit["canonical_books"],
)
print(
    "Canonical duplicate event keys:",
    canonical_duplicate_keys,
)
print(
    "Canonical books contain eleven events:",
    canonical_books_complete,
)
print(
    "Canonical prices lie in [0,1]:",
    canonical_prices_valid,
)
print()
print(
    "Common event keys:",
    audit["common_event_keys"],
)
print(
    "Canonical-only event keys:",
    canonical_only,
)
print(
    "Corroborating-only event keys:",
    corroborating_only,
)
print(
    "Differing common prices:",
    differing_prices,
)
print(
    "Maximum absolute price difference:",
    maximum_price_difference,
)
print(
    "Exact alias equivalence:",
    exact_equivalence,
)
print(
    "Exact alias equivalence required:",
    False,
)
print()
print("Decision:")
print(audit["decision"])
print()
print("CSV audit:", CSV_OUTPUT_PATH)
print("JSON audit:", JSON_OUTPUT_PATH)

if not canonical_certified:
    raise RuntimeError(
        "The canonical market source failed "
        "independent certification."
    )
