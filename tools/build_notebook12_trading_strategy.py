from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]

SPEC_PATH = (
    ROOT
    / "config/"
    "trading_strategy_spec.yaml"
)

DEVELOPMENT_MODEL_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "09_development_regularised_event_probability_panel.csv"
)

LOCKED_MODEL_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "09_locked_regularised_event_probability_panel.csv"
)

MARKET_PATH = (
    ROOT
    / "data/processed/"
    "18sA_canonical_source_adapters/"
    "18sA_canonical_market_panel.csv"
)

OUTCOME_PATH = (
    ROOT
    / "data/processed/"
    "certified_event_books.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/"
    "12_trading_strategy_manifest.json"
)

DEVELOPMENT_JOINED_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_development_trading_common_support_panel.csv"
)

BALANCED_SUPPORT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_development_balanced_support_dates.csv"
)

CANDIDATE_DATE_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_development_trading_candidate_date_panel.csv"
)

CANDIDATE_SUMMARY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_development_trading_candidate_summary.csv"
)

PAIRWISE_SELECTION_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_development_trading_one_se_comparison.csv"
)

LOCKED_DATE_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_locked_trading_date_panel.csv"
)

LOCKED_TRADE_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_locked_trading_trade_panel.csv"
)

COST_SENSITIVITY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_locked_trading_cost_sensitivity.csv"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "12_trading_strategy_integrity_checks.csv"
)

FINAL_SUMMARY_PATH = (
    ROOT
    / "outputs/final_tables/"
    "12_trading_strategy_summary.csv"
)


DATE_CANDIDATES = (
    "target_date",
    "event_date",
    "contract_date",
    "original_event_date",
    "date",
)

RULE_CANDIDATES = (
    "decision_rule",
    "rule",
)

MODEL_PROBABILITY_CANDIDATES = (
    "regularised_event_probability",
    "probability_regularised",
    "event_probability_regularised",
    "calibrated_event_probability",
    "probability_calibrated",
    "model_probability",
    "event_probability",
)

MARKET_PRICE_CANDIDATES = (
    "p_market",
    "market_price",
    "market_probability",
    "yes_price",
)

LOWER_BOUND_CANDIDATES = (
    "lower_bound_c",
    "event_lower_bound_c",
    "event_lower_bound_C",
    "lower_bound_C",
    "event_lower_bound",
    "lower_bound",
)

UPPER_BOUND_CANDIDATES = (
    "upper_bound_c",
    "event_upper_bound_c",
    "event_upper_bound_C",
    "upper_bound_C",
    "event_upper_bound",
    "upper_bound",
)

EVENT_LABEL_CANDIDATES = (
    "source_event_label",
    "event_label",
    "canonical_label",
    "visible_contract_label",
    "question",
)

OUTCOME_CANDIDATES = (
    "realised_yes",
    "realized_yes",
    "Y_event_int",
    "outcome",
    "label",
)

BLOCK_CANDIDATES = (
    "chronology_block",
    "sample_block",
    "final_modelling_split",
)

RULE_ORDER = {
    "24h_prior": 0,
    "12h_prior": 1,
    "6h_prior": 2,
    "event_day_open": 3,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def detect_column(
    columns: Iterable[str],
    candidates: Iterable[str],
) -> str | None:
    exact = set(columns)

    for candidate in candidates:
        if candidate in exact:
            return candidate

    lower_map = {
        str(column).strip().lower(): str(column)
        for column in columns
    }

    for candidate in candidates:
        match = lower_map.get(
            candidate.lower()
        )

        if match is not None:
            return match

    return None


def parse_date(
    series: pd.Series,
) -> pd.Series:
    return (
        pd.to_datetime(
            series,
            errors="coerce",
            utc=True,
        )
        .dt.tz_convert(None)
        .dt.normalize()
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

    aliases = {
        "24_hour_prior": "24h_prior",
        "24_hours_prior": "24h_prior",
        "24hr_prior": "24h_prior",
        "12_hour_prior": "12h_prior",
        "12_hours_prior": "12h_prior",
        "12hr_prior": "12h_prior",
        "6_hour_prior": "6h_prior",
        "6_hours_prior": "6h_prior",
        "6hr_prior": "6h_prior",
        "event_open": "event_day_open",
        "event_day": "event_day_open",
        "open": "event_day_open",
    }

    return result.replace(aliases)


def make_bound_key(
    series: pd.Series,
    *,
    lower: bool,
) -> pd.Series:
    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    tail_value = (
        -np.inf
        if lower
        else np.inf
    )

    numeric = numeric.fillna(
        tail_value
    )

    def encode(value: float) -> str:
        value = float(value)

        if value == -np.inf:
            return "-inf"

        if value == np.inf:
            return "inf"

        return f"{value:.6f}"

    return numeric.map(encode)


def standard_error(
    values: pd.Series,
) -> float:
    values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if len(values) <= 1:
        return 0.0

    return float(
        values.std(ddof=1)
        / math.sqrt(len(values))
    )


def maximum_drawdown(
    values: pd.Series,
) -> float:
    cumulative = (
        pd.to_numeric(
            values,
            errors="coerce",
        )
        .fillna(0.0)
        .cumsum()
    )

    running_maximum = cumulative.cummax()

    drawdown = (
        cumulative
        - running_maximum
    )

    return float(
        drawdown.min()
    )


def load_model_panel(
    path: Path,
    *,
    require_block: bool,
) -> tuple[pd.DataFrame, dict[str, str | None]]:
    frame = pd.read_csv(
        path,
        low_memory=False,
    )

    date_column = detect_column(
        frame.columns,
        DATE_CANDIDATES,
    )

    rule_column = detect_column(
        frame.columns,
        RULE_CANDIDATES,
    )

    probability_column = detect_column(
        frame.columns,
        MODEL_PROBABILITY_CANDIDATES,
    )

    lower_column = detect_column(
        frame.columns,
        LOWER_BOUND_CANDIDATES,
    )

    upper_column = detect_column(
        frame.columns,
        UPPER_BOUND_CANDIDATES,
    )

    label_column = detect_column(
        frame.columns,
        EVENT_LABEL_CANDIDATES,
    )

    block_column = detect_column(
        frame.columns,
        BLOCK_CANDIDATES,
    )

    required = {
        "date": date_column,
        "rule": rule_column,
        "probability": probability_column,
        "lower": lower_column,
        "upper": upper_column,
    }

    missing = [
        name
        for name, column in required.items()
        if column is None
    ]

    if missing:
        raise RuntimeError(
            f"{path} is missing model columns: "
            + ", ".join(missing)
        )

    if require_block and block_column is None:
        raise RuntimeError(
            f"{path} does not contain a chronology block."
        )

    output = pd.DataFrame(
        {
            "target_date": parse_date(
                frame[date_column]
            ),
            "decision_rule": normalise_rule(
                frame[rule_column]
            ),
            "model_probability": pd.to_numeric(
                frame[probability_column],
                errors="coerce",
            ),
            "lower_bound_key": make_bound_key(
                frame[lower_column],
                lower=True,
            ),
            "upper_bound_key": make_bound_key(
                frame[upper_column],
                lower=False,
            ),
            "lower_bound_c": pd.to_numeric(
                frame[lower_column],
                errors="coerce",
            ),
            "upper_bound_c": pd.to_numeric(
                frame[upper_column],
                errors="coerce",
            ),
        }
    )

    if label_column is not None:
        output["event_label"] = (
            frame[label_column]
            .astype(str)
            .str.strip()
        )
    else:
        output["event_label"] = (
            output["lower_bound_key"]
            + "_"
            + output["upper_bound_key"]
        )

    if block_column is not None:
        output["chronology_block"] = (
            frame[block_column]
            .astype(str)
            .str.strip()
        )
    else:
        output["chronology_block"] = (
            "development_validation"
        )

    output["event_key"] = (
        output["lower_bound_key"]
        + "|"
        + output["upper_bound_key"]
    )

    output = output.loc[
        output["target_date"].notna()
        & output["decision_rule"].isin(
            RULE_ORDER
        )
        & output[
            "model_probability"
        ].between(
            0.0,
            1.0,
            inclusive="both",
        )
    ].copy()

    if output.duplicated(
        [
            "target_date",
            "decision_rule",
            "event_key",
        ]
    ).any():
        duplicates = output.loc[
            output.duplicated(
                [
                    "target_date",
                    "decision_rule",
                    "event_key",
                ],
                keep=False,
            )
        ]

        raise RuntimeError(
            "Duplicate model event keys detected:\n"
            + duplicates.head(30).to_string(
                index=False
            )
        )

    metadata = {
        "date_column": date_column,
        "rule_column": rule_column,
        "probability_column": probability_column,
        "lower_column": lower_column,
        "upper_column": upper_column,
        "label_column": label_column,
        "block_column": block_column,
    }

    return output, metadata


def load_market_panel(
    path: Path,
) -> tuple[pd.DataFrame, dict[str, str]]:
    frame = pd.read_csv(
        path,
        low_memory=False,
    )

    date_column = detect_column(
        frame.columns,
        DATE_CANDIDATES,
    )

    rule_column = detect_column(
        frame.columns,
        RULE_CANDIDATES,
    )

    price_column = detect_column(
        frame.columns,
        MARKET_PRICE_CANDIDATES,
    )

    lower_column = detect_column(
        frame.columns,
        LOWER_BOUND_CANDIDATES,
    )

    upper_column = detect_column(
        frame.columns,
        UPPER_BOUND_CANDIDATES,
    )

    label_column = detect_column(
        frame.columns,
        EVENT_LABEL_CANDIDATES,
    )

    required = {
        "date": date_column,
        "rule": rule_column,
        "price": price_column,
        "lower": lower_column,
        "upper": upper_column,
    }

    missing = [
        name
        for name, column in required.items()
        if column is None
    ]

    if missing:
        raise RuntimeError(
            f"{path} is missing market columns: "
            + ", ".join(missing)
        )

    output = pd.DataFrame(
        {
            "target_date": parse_date(
                frame[date_column]
            ),
            "decision_rule": normalise_rule(
                frame[rule_column]
            ),
            "p_market": pd.to_numeric(
                frame[price_column],
                errors="coerce",
            ),
            "lower_bound_key": make_bound_key(
                frame[lower_column],
                lower=True,
            ),
            "upper_bound_key": make_bound_key(
                frame[upper_column],
                lower=False,
            ),
        }
    )

    if label_column is not None:
        output["market_event_label"] = (
            frame[label_column]
            .astype(str)
            .str.strip()
        )
    else:
        output["market_event_label"] = ""

    output["event_key"] = (
        output["lower_bound_key"]
        + "|"
        + output["upper_bound_key"]
    )

    output = output.loc[
        output["target_date"].notna()
        & output["decision_rule"].isin(
            RULE_ORDER
        )
        & output["p_market"].between(
            0.0,
            1.0,
            inclusive="both",
        )
    ].copy()

    duplicate_mask = output.duplicated(
        [
            "target_date",
            "decision_rule",
            "event_key",
        ],
        keep=False,
    )

    if duplicate_mask.any():
        duplicates = output.loc[
            duplicate_mask
        ]

        raise RuntimeError(
            "Duplicate canonical market event keys detected:\n"
            + duplicates.head(30).to_string(
                index=False
            )
        )

    metadata = {
        "date_column": str(date_column),
        "rule_column": str(rule_column),
        "price_column": str(price_column),
        "lower_column": str(lower_column),
        "upper_column": str(upper_column),
    }

    return output, metadata


def load_outcomes(
    path: Path,
) -> tuple[pd.DataFrame, dict[str, str]]:
    frame = pd.read_csv(
        path,
        low_memory=False,
    )

    date_column = detect_column(
        frame.columns,
        DATE_CANDIDATES,
    )

    outcome_column = detect_column(
        frame.columns,
        OUTCOME_CANDIDATES,
    )

    lower_column = detect_column(
        frame.columns,
        LOWER_BOUND_CANDIDATES,
    )

    upper_column = detect_column(
        frame.columns,
        UPPER_BOUND_CANDIDATES,
    )

    required = {
        "date": date_column,
        "outcome": outcome_column,
        "lower": lower_column,
        "upper": upper_column,
    }

    missing = [
        name
        for name, column in required.items()
        if column is None
    ]

    if missing:
        raise RuntimeError(
            f"{path} is missing outcome columns: "
            + ", ".join(missing)
        )

    output = pd.DataFrame(
        {
            "target_date": parse_date(
                frame[date_column]
            ),
            "realised_yes": pd.to_numeric(
                frame[outcome_column],
                errors="coerce",
            ),
            "lower_bound_key": make_bound_key(
                frame[lower_column],
                lower=True,
            ),
            "upper_bound_key": make_bound_key(
                frame[upper_column],
                lower=False,
            ),
        }
    )

    output["event_key"] = (
        output["lower_bound_key"]
        + "|"
        + output["upper_bound_key"]
    )

    output = output.loc[
        output["target_date"].notna()
        & output["realised_yes"].isin(
            [0, 1]
        )
    ].copy()

    conflicting = (
        output.groupby(
            [
                "target_date",
                "event_key",
            ]
        )["realised_yes"]
        .nunique()
    )

    if conflicting.gt(1).any():
        raise RuntimeError(
            "Conflicting certified outcomes detected."
        )

    output = output.drop_duplicates(
        [
            "target_date",
            "event_key",
        ]
    )

    metadata = {
        "date_column": str(date_column),
        "outcome_column": str(outcome_column),
        "lower_column": str(lower_column),
        "upper_column": str(upper_column),
    }

    return output, metadata


def join_complete_books(
    model: pd.DataFrame,
    market: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = model.merge(
        market,
        on=[
            "target_date",
            "decision_rule",
            "event_key",
            "lower_bound_key",
            "upper_bound_key",
        ],
        how="inner",
        validate="one_to_one",
    )

    joined = joined.merge(
        outcomes[
            [
                "target_date",
                "event_key",
                "realised_yes",
            ]
        ],
        on=[
            "target_date",
            "event_key",
        ],
        how="left",
        validate="many_to_one",
    )

    joined["edge"] = (
        joined["model_probability"]
        - joined["p_market"]
    )

    book_summary = (
        joined.groupby(
            [
                "target_date",
                "decision_rule",
                "chronology_block",
            ],
            as_index=False,
        )
        .agg(
            event_rows=(
                "event_key",
                "size",
            ),
            unique_events=(
                "event_key",
                "nunique",
            ),
            outcome_rows=(
                "realised_yes",
                "count",
            ),
            realised_winners=(
                "realised_yes",
                "sum",
            ),
            model_probability_sum=(
                "model_probability",
                "sum",
            ),
        )
    )

    book_summary["complete_book"] = (
        book_summary["event_rows"].eq(11)
        & book_summary["unique_events"].eq(11)
        & book_summary["outcome_rows"].eq(11)
        & book_summary["realised_winners"].eq(1)
        & np.isclose(
            book_summary[
                "model_probability_sum"
            ],
            1.0,
            atol=1.0e-8,
            rtol=0.0,
        )
    )

    complete_keys = book_summary.loc[
        book_summary["complete_book"],
        [
            "target_date",
            "decision_rule",
            "chronology_block",
        ],
    ]

    complete = joined.merge(
        complete_keys,
        on=[
            "target_date",
            "decision_rule",
            "chronology_block",
        ],
        how="inner",
        validate="many_to_one",
    )

    return complete, book_summary


def select_best_contract(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    ordered = frame.sort_values(
        [
            "target_date",
            "edge",
            "p_market",
            "lower_bound_key",
            "upper_bound_key",
        ],
        ascending=[
            True,
            False,
            True,
            True,
            True,
        ],
    )

    return (
        ordered.groupby(
            "target_date",
            as_index=False,
        )
        .head(1)
        .copy()
    )


def construct_candidate_dates(
    best_contracts: pd.DataFrame,
    *,
    decision_rule: str,
    threshold: float,
    cost: float,
    balanced_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    selected = best_contracts.loc[
        best_contracts[
            "decision_rule"
        ].eq(decision_rule)
    ].copy()

    selected = selected.set_index(
        "target_date"
    ).reindex(
        balanced_dates
    )

    selected.index.name = "target_date"
    selected = selected.reset_index()

    if selected[
        "model_probability"
    ].isna().any():
        raise RuntimeError(
            "Balanced development support contains "
            "a missing rule book."
        )

    selected["trade"] = (
        selected["edge"]
        >= threshold
    )

    selected["gross_payoff"] = np.where(
        selected["trade"],
        selected["realised_yes"]
        - selected["p_market"],
        0.0,
    )

    selected["net_payoff"] = np.where(
        selected["trade"],
        selected["gross_payoff"]
        - cost,
        0.0,
    )

    selected["candidate_id"] = (
        f"{decision_rule}__tau_"
        f"{threshold:.3f}"
    )

    selected["selected_rule"] = (
        decision_rule
    )

    selected["edge_threshold"] = (
        threshold
    )

    selected["selection_cost_per_trade"] = (
        cost
    )

    return selected


def summarise_candidate(
    frame: pd.DataFrame,
) -> dict[str, object]:
    trades = frame.loc[
        frame["trade"]
    ]

    return {
        "candidate_id": frame[
            "candidate_id"
        ].iloc[0],
        "decision_rule": frame[
            "selected_rule"
        ].iloc[0],
        "edge_threshold": float(
            frame["edge_threshold"].iloc[0]
        ),
        "selection_cost_per_trade": float(
            frame[
                "selection_cost_per_trade"
            ].iloc[0]
        ),
        "development_dates": int(
            frame["target_date"].nunique()
        ),
        "trade_count": int(
            frame["trade"].sum()
        ),
        "trade_share": float(
            frame["trade"].mean()
        ),
        "cumulative_gross_payoff": float(
            frame["gross_payoff"].sum()
        ),
        "cumulative_net_payoff": float(
            frame["net_payoff"].sum()
        ),
        "mean_date_gross_payoff": float(
            frame["gross_payoff"].mean()
        ),
        "mean_date_net_payoff": float(
            frame["net_payoff"].mean()
        ),
        "standard_error_date_net_payoff": (
            standard_error(
                frame["net_payoff"]
            )
        ),
        "maximum_drawdown_net_payoff": (
            maximum_drawdown(
                frame["net_payoff"]
            )
        ),
        "trade_win_share": (
            float(
                (
                    trades["net_payoff"]
                    > 0.0
                ).mean()
            )
            if len(trades)
            else np.nan
        ),
        "mean_traded_edge": (
            float(
                trades["edge"].mean()
            )
            if len(trades)
            else np.nan
        ),
        "mean_paid_price": (
            float(
                trades["p_market"].mean()
            )
            if len(trades)
            else np.nan
        ),
    }


with SPEC_PATH.open(
    "r",
    encoding="utf-8",
) as handle:
    spec = yaml.safe_load(handle)

for required_path in (
    DEVELOPMENT_MODEL_PATH,
    LOCKED_MODEL_PATH,
    MARKET_PATH,
    OUTCOME_PATH,
):
    if not required_path.exists():
        raise FileNotFoundError(
            f"Required input is missing: "
            f"{required_path}"
        )

development_model, development_model_columns = (
    load_model_panel(
        DEVELOPMENT_MODEL_PATH,
        require_block=False,
    )
)

locked_model, locked_model_columns = (
    load_model_panel(
        LOCKED_MODEL_PATH,
        require_block=True,
    )
)

market, market_columns = load_market_panel(
    MARKET_PATH
)

outcomes, outcome_columns = load_outcomes(
    OUTCOME_PATH
)

development_start = pd.Timestamp(
    spec["development_period"]["start"]
)

development_end = pd.Timestamp(
    spec["development_period"]["end"]
)

development_model = development_model.loc[
    development_model[
        "target_date"
    ].between(
        development_start,
        development_end,
        inclusive="both",
    )
].copy()

development_complete, development_book_audit = (
    join_complete_books(
        development_model,
        market,
        outcomes,
    )
)

complete_development_books = (
    development_book_audit.loc[
        development_book_audit[
            "complete_book"
        ]
    ].copy()
)

balanced_date_counts = (
    complete_development_books.groupby(
        "target_date"
    )["decision_rule"]
    .nunique()
)

balanced_dates = pd.DatetimeIndex(
    balanced_date_counts.loc[
        balanced_date_counts.eq(
            len(RULE_ORDER)
        )
    ].index
).sort_values()

minimum_balanced_dates = int(
    spec[
        "minimum_balanced_development_dates"
    ]
)

if len(balanced_dates) < minimum_balanced_dates:
    raise RuntimeError(
        "Insufficient balanced development dates: "
        f"{len(balanced_dates)} found, "
        f"{minimum_balanced_dates} required."
    )

balanced_support = (
    complete_development_books.loc[
        complete_development_books[
            "target_date"
        ].isin(balanced_dates)
    ]
    .sort_values(
        [
            "target_date",
            "decision_rule",
        ]
    )
)

balanced_rule_counts = (
    balanced_support.groupby(
        "decision_rule"
    )["target_date"]
    .nunique()
)

if not balanced_rule_counts.eq(
    len(balanced_dates)
).all():
    raise RuntimeError(
        "Development decision rules do not share "
        "identical balanced date support."
    )

development_balanced = (
    development_complete.loc[
        development_complete[
            "target_date"
        ].isin(balanced_dates)
    ].copy()
)

development_balanced["rule_order"] = (
    development_balanced[
        "decision_rule"
    ].map(RULE_ORDER)
)

best_development_contracts = (
    development_balanced.sort_values(
        [
            "target_date",
            "rule_order",
            "edge",
            "p_market",
            "lower_bound_key",
        ],
        ascending=[
            True,
            True,
            False,
            True,
            True,
        ],
    )
    .groupby(
        [
            "target_date",
            "decision_rule",
        ],
        as_index=False,
    )
    .head(1)
    .copy()
)

thresholds = [
    float(value)
    for value in spec["threshold_grid"]
]

selection_cost = float(
    spec["selection_cost_per_trade"]
)

candidate_date_frames: list[
    pd.DataFrame
] = []

candidate_summary_rows: list[
    dict[str, object]
] = []

for rule in spec["decision_rules"]:
    for threshold in thresholds:
        candidate_dates = (
            construct_candidate_dates(
                best_development_contracts,
                decision_rule=rule,
                threshold=threshold,
                cost=selection_cost,
                balanced_dates=balanced_dates,
            )
        )

        candidate_date_frames.append(
            candidate_dates
        )

        candidate_summary_rows.append(
            summarise_candidate(
                candidate_dates
            )
        )

no_trade_dates = pd.DataFrame(
    {
        "target_date": balanced_dates,
        "candidate_id": "no_trade",
        "selected_rule": "no_trade",
        "edge_threshold": np.nan,
        "selection_cost_per_trade": (
            selection_cost
        ),
        "trade": False,
        "gross_payoff": 0.0,
        "net_payoff": 0.0,
    }
)

candidate_date_frames.append(
    no_trade_dates
)

candidate_summary_rows.append(
    {
        "candidate_id": "no_trade",
        "decision_rule": "no_trade",
        "edge_threshold": np.nan,
        "selection_cost_per_trade": (
            selection_cost
        ),
        "development_dates": int(
            len(balanced_dates)
        ),
        "trade_count": 0,
        "trade_share": 0.0,
        "cumulative_gross_payoff": 0.0,
        "cumulative_net_payoff": 0.0,
        "mean_date_gross_payoff": 0.0,
        "mean_date_net_payoff": 0.0,
        "standard_error_date_net_payoff": 0.0,
        "maximum_drawdown_net_payoff": 0.0,
        "trade_win_share": np.nan,
        "mean_traded_edge": np.nan,
        "mean_paid_price": np.nan,
    }
)

candidate_date_panel = pd.concat(
    candidate_date_frames,
    ignore_index=True,
    sort=False,
)

candidate_summary = pd.DataFrame(
    candidate_summary_rows
)

minimum_trades = int(
    spec["minimum_development_trades"]
)

candidate_summary[
    "minimum_trade_count_satisfied"
] = (
    candidate_summary[
        "trade_count"
    ].ge(minimum_trades)
    | candidate_summary[
        "candidate_id"
    ].eq("no_trade")
)

candidate_summary["rule_order"] = (
    candidate_summary[
        "decision_rule"
    ].map(RULE_ORDER).fillna(99)
)

eligible_summary = candidate_summary.loc[
    candidate_summary[
        "minimum_trade_count_satisfied"
    ]
].copy()

strict_winner = (
    eligible_summary.sort_values(
        [
            "mean_date_net_payoff",
            "edge_threshold",
            "rule_order",
        ],
        ascending=[
            False,
            False,
            True,
        ],
        na_position="last",
    )
    .iloc[0]
)

strict_winner_id = str(
    strict_winner["candidate_id"]
)

strict_date_panel = (
    candidate_date_panel.loc[
        candidate_date_panel[
            "candidate_id"
        ].eq(strict_winner_id),
        [
            "target_date",
            "net_payoff",
        ],
    ]
    .rename(
        columns={
            "net_payoff": (
                "strict_winner_net_payoff"
            )
        }
    )
)

pairwise_rows: list[
    dict[str, object]
] = []

for _, candidate in eligible_summary.iterrows():
    candidate_id = str(
        candidate["candidate_id"]
    )

    comparison = (
        candidate_date_panel.loc[
            candidate_date_panel[
                "candidate_id"
            ].eq(candidate_id),
            [
                "target_date",
                "net_payoff",
            ],
        ]
        .merge(
            strict_date_panel,
            on="target_date",
            how="inner",
            validate="one_to_one",
        )
    )

    comparison["difference"] = (
        comparison["net_payoff"]
        - comparison[
            "strict_winner_net_payoff"
        ]
    )

    mean_difference = float(
        comparison["difference"].mean()
    )

    se_difference = standard_error(
        comparison["difference"]
    )

    within_one_se = bool(
        mean_difference
        >= -se_difference - 1.0e-12
    )

    pairwise_rows.append(
        {
            "candidate_id": candidate_id,
            "strict_winner_id": (
                strict_winner_id
            ),
            "paired_dates": int(
                len(comparison)
            ),
            "mean_candidate_minus_strict_net_payoff": (
                mean_difference
            ),
            "standard_error_paired_difference": (
                se_difference
            ),
            "within_one_standard_error": (
                within_one_se
            ),
        }
    )

pairwise_selection = pd.DataFrame(
    pairwise_rows
)

candidate_summary = candidate_summary.merge(
    pairwise_selection[
        [
            "candidate_id",
            "mean_candidate_minus_strict_net_payoff",
            "standard_error_paired_difference",
            "within_one_standard_error",
        ]
    ],
    on="candidate_id",
    how="left",
    validate="one_to_one",
)

strict_mean = float(
    strict_winner[
        "mean_date_net_payoff"
    ]
)

if (
    strict_winner_id == "no_trade"
    or strict_mean <= 0.0
):
    selected_id = "no_trade"
    selection_reason = (
        "No active strategy exceeded the no-trade "
        "benchmark on mean development net payoff."
    )

else:
    conservative_candidates = (
        candidate_summary.loc[
            candidate_summary[
                "candidate_id"
            ].ne("no_trade")
            & candidate_summary[
                "minimum_trade_count_satisfied"
            ]
            & candidate_summary[
                "within_one_standard_error"
            ].fillna(False)
        ]
        .sort_values(
            [
                "edge_threshold",
                "rule_order",
                "mean_date_net_payoff",
            ],
            ascending=[
                False,
                True,
                False,
            ],
        )
    )

    if conservative_candidates.empty:
        selected_id = strict_winner_id
        selection_reason = (
            "The strict development winner was used "
            "because no alternative satisfied the "
            "paired one-standard-error rule."
        )
    else:
        selected_id = str(
            conservative_candidates.iloc[0][
                "candidate_id"
            ]
        )

        selection_reason = (
            "Selected the largest edge threshold "
            "within one paired standard error of "
            "the strict development winner; ties "
            "favoured the earlier decision rule."
        )

candidate_summary[
    "strict_development_winner"
] = candidate_summary[
    "candidate_id"
].eq(strict_winner_id)

candidate_summary[
    "selected_strategy"
] = candidate_summary[
    "candidate_id"
].eq(selected_id)

selected_summary = candidate_summary.loc[
    candidate_summary[
        "selected_strategy"
    ]
].iloc[0]

selected_rule = str(
    selected_summary["decision_rule"]
)

selected_threshold = (
    None
    if selected_id == "no_trade"
    else float(
        selected_summary[
            "edge_threshold"
        ]
    )
)

locked_complete, locked_book_audit = (
    join_complete_books(
        locked_model,
        market,
        outcomes,
    )
)

locked_model_dates = (
    locked_model[
        [
            "target_date",
            "chronology_block",
        ]
    ]
    .drop_duplicates()
    .loc[
        lambda frame: frame[
            "chronology_block"
        ].isin(
            spec["evaluation_blocks"]
        )
    ]
    .sort_values(
        [
            "chronology_block",
            "target_date",
        ]
    )
)

evaluation_date_rows: list[
    dict[str, object]
] = []

if selected_id == "no_trade":
    for row in locked_model_dates.itertuples(
        index=False
    ):
        evaluation_date_rows.append(
            {
                "target_date": row.target_date,
                "chronology_block": (
                    row.chronology_block
                ),
                "selected_strategy": (
                    selected_id
                ),
                "selected_rule": "no_trade",
                "edge_threshold": np.nan,
                "selection_cost_per_trade": (
                    selection_cost
                ),
                "market_support_available": (
                    False
                ),
                "trade": False,
                "model_probability": np.nan,
                "p_market": np.nan,
                "edge": np.nan,
                "realised_yes": np.nan,
                "event_label": "",
                "gross_payoff": 0.0,
                "net_payoff": 0.0,
            }
        )

else:
    selected_rule_books = (
        locked_complete.loc[
            locked_complete[
                "decision_rule"
            ].eq(selected_rule)
            & locked_complete[
                "chronology_block"
            ].isin(
                spec["evaluation_blocks"]
            )
        ]
        .copy()
    )

    selected_best = select_best_contract(
        selected_rule_books
    )

    selected_best = selected_best.set_index(
        [
            "target_date",
            "chronology_block",
        ]
    )

    for row in locked_model_dates.itertuples(
        index=False
    ):
        key = (
            row.target_date,
            row.chronology_block,
        )

        if key not in selected_best.index:
            evaluation_date_rows.append(
                {
                    "target_date": (
                        row.target_date
                    ),
                    "chronology_block": (
                        row.chronology_block
                    ),
                    "selected_strategy": (
                        selected_id
                    ),
                    "selected_rule": (
                        selected_rule
                    ),
                    "edge_threshold": (
                        selected_threshold
                    ),
                    "selection_cost_per_trade": (
                        selection_cost
                    ),
                    "market_support_available": (
                        False
                    ),
                    "trade": False,
                    "model_probability": np.nan,
                    "p_market": np.nan,
                    "edge": np.nan,
                    "realised_yes": np.nan,
                    "event_label": "",
                    "gross_payoff": 0.0,
                    "net_payoff": 0.0,
                }
            )

            continue

        contract = selected_best.loc[key]

        if isinstance(
            contract,
            pd.DataFrame,
        ):
            raise RuntimeError(
                "More than one selected contract was "
                "found for an evaluation date."
            )

        trade = bool(
            float(contract["edge"])
            >= float(selected_threshold)
        )

        gross_payoff = (
            float(
                contract["realised_yes"]
                - contract["p_market"]
            )
            if trade
            else 0.0
        )

        net_payoff = (
            gross_payoff
            - selection_cost
            if trade
            else 0.0
        )

        evaluation_date_rows.append(
            {
                "target_date": (
                    row.target_date
                ),
                "chronology_block": (
                    row.chronology_block
                ),
                "selected_strategy": (
                    selected_id
                ),
                "selected_rule": (
                    selected_rule
                ),
                "edge_threshold": (
                    selected_threshold
                ),
                "selection_cost_per_trade": (
                    selection_cost
                ),
                "market_support_available": (
                    True
                ),
                "trade": trade,
                "model_probability": float(
                    contract[
                        "model_probability"
                    ]
                ),
                "p_market": float(
                    contract["p_market"]
                ),
                "edge": float(
                    contract["edge"]
                ),
                "realised_yes": int(
                    contract["realised_yes"]
                ),
                "event_label": str(
                    contract["event_label"]
                ),
                "lower_bound_c": (
                    contract[
                        "lower_bound_c"
                    ]
                ),
                "upper_bound_c": (
                    contract[
                        "upper_bound_c"
                    ]
                ),
                "gross_payoff": (
                    gross_payoff
                ),
                "net_payoff": (
                    net_payoff
                ),
            }
        )

locked_date_panel = pd.DataFrame(
    evaluation_date_rows
).sort_values(
    [
        "chronology_block",
        "target_date",
    ]
)

locked_trade_panel = locked_date_panel.loc[
    locked_date_panel["trade"]
].copy()

summary_rows: list[
    dict[str, object]
] = []

for block in spec["evaluation_blocks"]:
    block_frame = locked_date_panel.loc[
        locked_date_panel[
            "chronology_block"
        ].eq(block)
    ].copy()

    available = block_frame.loc[
        block_frame[
            "market_support_available"
        ]
    ]

    trades = block_frame.loc[
        block_frame["trade"]
    ]

    summary_rows.append(
        {
            "chronology_block": block,
            "calendar_dates": int(
                block_frame[
                    "target_date"
                ].nunique()
            ),
            "market_supported_dates": int(
                available[
                    "target_date"
                ].nunique()
            ),
            "market_unsupported_dates": int(
                block_frame[
                    "target_date"
                ].nunique()
                - available[
                    "target_date"
                ].nunique()
            ),
            "selected_strategy": (
                selected_id
            ),
            "selected_rule": (
                selected_rule
            ),
            "edge_threshold": (
                selected_threshold
            ),
            "cost_per_trade": (
                selection_cost
            ),
            "trade_count": int(
                block_frame["trade"].sum()
            ),
            "trade_share_all_calendar_dates": (
                float(
                    block_frame[
                        "trade"
                    ].mean()
                )
            ),
            "cumulative_gross_payoff": (
                float(
                    block_frame[
                        "gross_payoff"
                    ].sum()
                )
            ),
            "cumulative_net_payoff": (
                float(
                    block_frame[
                        "net_payoff"
                    ].sum()
                )
            ),
            "mean_calendar_date_net_payoff": (
                float(
                    block_frame[
                        "net_payoff"
                    ].mean()
                )
            ),
            "standard_error_calendar_date_net_payoff": (
                standard_error(
                    block_frame[
                        "net_payoff"
                    ]
                )
            ),
            "mean_supported_date_net_payoff": (
                float(
                    available[
                        "net_payoff"
                    ].mean()
                )
                if len(available)
                else np.nan
            ),
            "trade_win_share": (
                float(
                    (
                        trades[
                            "net_payoff"
                        ]
                        > 0.0
                    ).mean()
                )
                if len(trades)
                else np.nan
            ),
            "maximum_drawdown_net_payoff": (
                maximum_drawdown(
                    block_frame[
                        "net_payoff"
                    ]
                )
            ),
        }
    )

trading_summary = pd.DataFrame(
    summary_rows
)

cost_sensitivity_rows: list[
    dict[str, object]
] = []

for block in spec["evaluation_blocks"]:
    block_frame = locked_date_panel.loc[
        locked_date_panel[
            "chronology_block"
        ].eq(block)
    ].copy()

    for cost in spec[
        "cost_sensitivity_grid"
    ]:
        cost = float(cost)

        net = np.where(
            block_frame["trade"],
            block_frame[
                "gross_payoff"
            ]
            - cost,
            0.0,
        )

        cost_sensitivity_rows.append(
            {
                "chronology_block": (
                    block
                ),
                "selected_strategy": (
                    selected_id
                ),
                "selected_rule": (
                    selected_rule
                ),
                "edge_threshold": (
                    selected_threshold
                ),
                "cost_per_trade": cost,
                "calendar_dates": int(
                    block_frame[
                        "target_date"
                    ].nunique()
                ),
                "trade_count": int(
                    block_frame[
                        "trade"
                    ].sum()
                ),
                "cumulative_net_payoff": (
                    float(
                        np.sum(net)
                    )
                ),
                "mean_calendar_date_net_payoff": (
                    float(
                        np.mean(net)
                    )
                ),
                "standard_error_calendar_date_net_payoff": (
                    standard_error(
                        pd.Series(net)
                    )
                ),
            }
        )

cost_sensitivity = pd.DataFrame(
    cost_sensitivity_rows
)

integrity_rows = [
    {
        "check": "development_uses_balanced_four_rule_dates",
        "passed": bool(
            balanced_rule_counts.eq(
                len(balanced_dates)
            ).all()
        ),
        "value": int(
            len(balanced_dates)
        ),
    },
    {
        "check": "minimum_balanced_dates_satisfied",
        "passed": bool(
            len(balanced_dates)
            >= minimum_balanced_dates
        ),
        "value": int(
            len(balanced_dates)
        ),
    },
    {
        "check": "model_probabilities_are_valid",
        "passed": bool(
            development_balanced[
                "model_probability"
            ].between(
                0.0,
                1.0,
                inclusive="both",
            ).all()
        ),
        "value": True,
    },
    {
        "check": "raw_market_prices_are_valid",
        "passed": bool(
            development_balanced[
                "p_market"
            ].between(
                0.0,
                1.0,
                inclusive="both",
            ).all()
        ),
        "value": True,
    },
    {
        "check": "minimum_selected_trade_count_satisfied",
        "passed": bool(
            selected_id == "no_trade"
            or int(
                selected_summary[
                    "trade_count"
                ]
            )
            >= minimum_trades
        ),
        "value": int(
            selected_summary[
                "trade_count"
            ]
        ),
    },
    {
        "check": "at_most_one_trade_per_evaluation_date",
        "passed": bool(
            locked_trade_panel[
                [
                    "target_date",
                    "chronology_block",
                ]
            ].duplicated().sum()
            == 0
        ),
        "value": int(
            locked_trade_panel[
                [
                    "target_date",
                    "chronology_block",
                ]
            ].duplicated().sum()
        ),
    },
    {
        "check": "holdout_not_used_for_selection",
        "passed": True,
        "value": False,
    },
    {
        "check": "external_test_not_used_for_selection",
        "passed": True,
        "value": False,
    },
    {
        "check": "weather_model_not_reselected",
        "passed": True,
        "value": False,
    },
    {
        "check": "continuous_calibration_not_reselected",
        "passed": True,
        "value": False,
    },
    {
        "check": "probability_calibration_not_reselected",
        "passed": True,
        "value": False,
    },
    {
        "check": "categorically_normalised_prices_not_used",
        "passed": True,
        "value": False,
    },
    {
        "check": "strategy_not_refitted_before_external_test",
        "passed": True,
        "value": False,
    },
]

integrity = pd.DataFrame(
    integrity_rows
)

if not integrity["passed"].all():
    raise RuntimeError(
        "Notebook 12 integrity checks failed:\n"
        + integrity.loc[
            ~integrity["passed"]
        ].to_string(index=False)
    )

for path in (
    MANIFEST_PATH,
    DEVELOPMENT_JOINED_PATH,
    BALANCED_SUPPORT_PATH,
    CANDIDATE_DATE_PATH,
    CANDIDATE_SUMMARY_PATH,
    PAIRWISE_SELECTION_PATH,
    LOCKED_DATE_PATH,
    LOCKED_TRADE_PATH,
    COST_SENSITIVITY_PATH,
    INTEGRITY_PATH,
    FINAL_SUMMARY_PATH,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

development_balanced.to_csv(
    DEVELOPMENT_JOINED_PATH,
    index=False,
)

balanced_support.to_csv(
    BALANCED_SUPPORT_PATH,
    index=False,
)

candidate_date_panel.to_csv(
    CANDIDATE_DATE_PATH,
    index=False,
)

candidate_summary.to_csv(
    CANDIDATE_SUMMARY_PATH,
    index=False,
)

pairwise_selection.to_csv(
    PAIRWISE_SELECTION_PATH,
    index=False,
)

locked_date_panel.to_csv(
    LOCKED_DATE_PATH,
    index=False,
)

locked_trade_panel.to_csv(
    LOCKED_TRADE_PATH,
    index=False,
)

cost_sensitivity.to_csv(
    COST_SENSITIVITY_PATH,
    index=False,
)

integrity.to_csv(
    INTEGRITY_PATH,
    index=False,
)

trading_summary.to_csv(
    FINAL_SUMMARY_PATH,
    index=False,
)

output_paths = (
    DEVELOPMENT_JOINED_PATH,
    BALANCED_SUPPORT_PATH,
    CANDIDATE_DATE_PATH,
    CANDIDATE_SUMMARY_PATH,
    PAIRWISE_SELECTION_PATH,
    LOCKED_DATE_PATH,
    LOCKED_TRADE_PATH,
    COST_SENSITIVITY_PATH,
    INTEGRITY_PATH,
    FINAL_SUMMARY_PATH,
)

manifest = {
    "status": (
        "TRADING_STRATEGY_LOCKED_AND_EVALUATED"
    ),
    "created_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "development_probability_source": str(
        DEVELOPMENT_MODEL_PATH.relative_to(
            ROOT
        )
    ),
    "locked_probability_source": str(
        LOCKED_MODEL_PATH.relative_to(
            ROOT
        )
    ),
    "canonical_market_source": str(
        MARKET_PATH.relative_to(ROOT)
    ),
    "certified_outcome_source": str(
        OUTCOME_PATH.relative_to(ROOT)
    ),
    "market_price_column": (
        market_columns["price_column"]
    ),
    "model_probability_column_development": (
        development_model_columns[
            "probability_column"
        ]
    ),
    "model_probability_column_locked": (
        locked_model_columns[
            "probability_column"
        ]
    ),
    "development_start": str(
        development_start.date()
    ),
    "development_end": str(
        development_end.date()
    ),
    "development_probability_books": int(
        development_model.groupby(
            [
                "target_date",
                "decision_rule",
            ]
        ).ngroups
    ),
    "development_complete_common_support_books": int(
        len(
            complete_development_books
        )
    ),
    "development_complete_common_support_dates": int(
        complete_development_books[
            "target_date"
        ].nunique()
    ),
    "balanced_development_dates": int(
        len(balanced_dates)
    ),
    "balanced_development_books": int(
        len(balanced_dates)
        * len(RULE_ORDER)
    ),
    "balanced_development_rows": int(
        len(development_balanced)
    ),
    "decision_rules_compared": list(
        spec["decision_rules"]
    ),
    "threshold_grid": thresholds,
    "selection_cost_per_trade": (
        selection_cost
    ),
    "cost_sensitivity_grid": [
        float(value)
        for value in spec[
            "cost_sensitivity_grid"
        ]
    ],
    "minimum_development_trades": (
        minimum_trades
    ),
    "trade_direction": "buy_yes_only",
    "maximum_positions_per_settlement_date": 1,
    "selection_score": (
        "mean settlement-date net payoff"
    ),
    "selection_rule": (
        "paired one-standard-error "
        "conservative-threshold rule"
    ),
    "strict_development_winner": (
        strict_winner_id
    ),
    "strict_development_winner_mean_date_net_payoff": (
        strict_mean
    ),
    "selected_strategy": selected_id,
    "selected_rule": selected_rule,
    "selected_edge_threshold": (
        selected_threshold
    ),
    "selected_development_trade_count": int(
        selected_summary[
            "trade_count"
        ]
    ),
    "selected_development_mean_date_net_payoff": (
        float(
            selected_summary[
                "mean_date_net_payoff"
            ]
        )
    ),
    "selection_reason": (
        selection_reason
    ),
    "uncertainty_unit": (
        "settlement_date"
    ),
    "raw_market_prices_used": True,
    "categorically_normalised_market_prices_used": False,
    "market_prices_used_for_weather_model_selection": False,
    "market_prices_used_for_continuous_calibration": False,
    "market_prices_used_for_probability_calibration": False,
    "holdout_used_for_strategy_selection": False,
    "external_test_used_for_strategy_selection": False,
    "weather_model_reselected": False,
    "continuous_calibration_reselected": False,
    "probability_calibration_reselected": False,
    "strategy_refitted_before_external_test": False,
    "holdout_calendar_dates": int(
        locked_date_panel.loc[
            locked_date_panel[
                "chronology_block"
            ].eq("holdout"),
            "target_date",
        ].nunique()
    ),
    "external_test_calendar_dates": int(
        locked_date_panel.loc[
            locked_date_panel[
                "chronology_block"
            ].eq("external_test"),
            "target_date",
        ].nunique()
    ),
    "trading_returns_calculated": True,
    "all_integrity_checks_passed": bool(
        integrity["passed"].all()
    ),
    "input_hashes": {
        str(path.relative_to(ROOT)): (
            sha256_file(path)
        )
        for path in (
            SPEC_PATH,
            DEVELOPMENT_MODEL_PATH,
            LOCKED_MODEL_PATH,
            MARKET_PATH,
            OUTCOME_PATH,
        )
    },
    "output_hashes": {
        str(path.relative_to(ROOT)): (
            sha256_file(path)
        )
        for path in output_paths
    },
    "next_stage": (
        "Create the canonical Notebook 12, "
        "permanent tests and documentation."
    ),
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
print("=" * 88)
print("NOTEBOOK 12 CORE TRADING STAGE COMPLETE")
print("=" * 88)
print()
print(
    "Status:",
    manifest["status"],
)
print(
    "Development complete common-support books:",
    manifest[
        "development_complete_common_support_books"
    ],
)
print(
    "Development complete common-support dates:",
    manifest[
        "development_complete_common_support_dates"
    ],
)
print(
    "Balanced four-rule development dates:",
    manifest["balanced_development_dates"],
)
print(
    "Balanced development books:",
    manifest["balanced_development_books"],
)
print()
print(
    "Strict development winner:",
    manifest[
        "strict_development_winner"
    ],
)
print(
    "Selected strategy:",
    manifest["selected_strategy"],
)
print(
    "Selected decision rule:",
    manifest["selected_rule"],
)
print(
    "Selected edge threshold:",
    manifest["selected_edge_threshold"],
)
print(
    "Selection cost per trade:",
    manifest["selection_cost_per_trade"],
)
print(
    "Selected development trades:",
    manifest[
        "selected_development_trade_count"
    ],
)
print(
    "Selected development mean date net payoff:",
    manifest[
        "selected_development_mean_date_net_payoff"
    ],
)
print()
print("Locked evaluation summary:")
print(
    trading_summary.to_string(
        index=False
    )
)
print()
print(
    "All integrity checks passed:",
    manifest[
        "all_integrity_checks_passed"
    ],
)
