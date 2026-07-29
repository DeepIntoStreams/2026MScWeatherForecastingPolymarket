from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/v2_completion"
FIG = OUT / "phase20_figures"
CONFIG = ROOT / "config/v2_completion"

COMMON_PATH = (
    ROOT
    / "outputs/v2/diagnostics/phase10_gp_market_comparison/"
    / "phase10_exact_common_support_event_panel.csv"
)
PHASE10_REPORT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/phase10_gp_market_comparison/"
    / "phase10_report.md"
)
PHASE19_SPEC_PATH = (
    ROOT
    / "config/v2_completion/"
    / "phase19_predictive_diagnostics_spec.json"
)
PHASE19_REPORT_PATH = (
    ROOT
    / "outputs/v2_completion/"
    / "phase19_predictive_diagnostics_report.md"
)

REQUIRED_PATHS = [
    COMMON_PATH,
    PHASE10_REPORT_PATH,
    PHASE19_SPEC_PATH,
    PHASE19_REPORT_PATH,
]

EXPECTED_ROWS = 3850
EXPECTED_DATES = 97
EXPECTED_BOOKS = 350
EXPECTED_DEVELOPMENT_DATES = 67
EXPECTED_JUNE_DATES = 30

RULE_ORDER = [
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
]
RULE_LABELS = {
    "24h_prior": "24h prior",
    "12h_prior": "12h prior",
    "6h_prior": "6h prior",
    "event_day_open": "event-day open",
}

WEIGHT_GRID = np.round(np.linspace(0.0, 1.0, 1001), 3)
PRIMARY_SELECTION_METRIC = "categorical_log"
WEIGHT_BOOTSTRAP_REPLICATIONS = 5000
DATE_BOOTSTRAP_REPLICATIONS = 10000
BOOTSTRAP_SEED = 20260729
PROBABILITY_FLOOR = 1e-12
NUMERICAL_TOLERANCE = 1e-8


def fail(message: str) -> None:
    raise RuntimeError(message)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def find_column(
    columns: Iterable[str],
    exact: Iterable[str] = (),
    contains_all: Iterable[str] = (),
    contains_any: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> str | None:
    cols = list(columns)
    lower = {column.lower(): column for column in cols}

    for name in exact:
        if name.lower() in lower:
            return lower[name.lower()]

    candidates: list[tuple[int, int, str]] = []
    for column in cols:
        lowered = column.lower()
        if any(token.lower() in lowered for token in exclude):
            continue
        if contains_all and not all(
            token.lower() in lowered for token in contains_all
        ):
            continue
        if contains_any and not any(
            token.lower() in lowered for token in contains_any
        ):
            continue

        score = (
            10
            * sum(
                token.lower() in lowered
                for token in contains_all
            )
            + 2
            * sum(
                token.lower() in lowered
                for token in contains_any
            )
        )
        candidates.append((-score, len(column), column))

    if not candidates:
        return None

    candidates.sort()
    return candidates[0][2]


def normalise_rule(value: Any) -> str:
    text = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    aliases = {
        "24h": "24h_prior",
        "24hr": "24h_prior",
        "24_hours_prior": "24h_prior",
        "12h": "12h_prior",
        "12hr": "12h_prior",
        "12_hours_prior": "12h_prior",
        "6h": "6h_prior",
        "6hr": "6h_prior",
        "6_hours_prior": "6h_prior",
        "open": "event_day_open",
        "eventdayopen": "event_day_open",
        "event_day": "event_day_open",
    }
    return aliases.get(text, text)


def numeric_probability_candidates(
    frame: pd.DataFrame,
    tokens: tuple[str, ...],
) -> list[str]:
    candidates: list[str] = []

    for column in frame.columns:
        lowered = column.lower()
        if not any(token in lowered for token in tokens):
            continue
        if any(
            token in lowered
            for token in (
                "brier",
                "log",
                "score",
                "error",
                "difference",
                "outcome",
                "realised",
                "realized",
                "covered",
                "coverage",
                "rank",
                "weight",
            )
        ):
            continue

        values = pd.to_numeric(
            frame[column],
            errors="coerce",
        )
        if values.notna().mean() < 0.99:
            continue
        finite = values[np.isfinite(values)]
        if finite.empty:
            continue
        if (
            float(finite.min()) < -1e-10
            or float(finite.max()) > 1.0 + 1e-10
        ):
            continue
        candidates.append(column)

    return candidates


def probability_candidate_audit(
    frame: pd.DataFrame,
    book_keys: list[str],
    candidates: list[str],
    source: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for column in candidates:
        values = pd.to_numeric(
            frame[column],
            errors="coerce",
        )
        sums = (
            frame.assign(_probability=values)
            .groupby(book_keys, sort=False)["_probability"]
            .sum()
        )
        rows.append(
            {
                "source": source,
                "column": column,
                "rows": int(values.notna().sum()),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
                "mean_book_sum": float(sums.mean()),
                "maximum_absolute_book_sum_error": float(
                    np.max(np.abs(sums.to_numpy(dtype=float) - 1.0))
                ),
                "mean_absolute_book_sum_error": float(
                    np.mean(np.abs(sums.to_numpy(dtype=float) - 1.0))
                ),
                "name_contains_normalised": bool(
                    any(
                        token in column.lower()
                        for token in (
                            "normalised",
                            "normalized",
                            "book_probability",
                            "categorical",
                        )
                    )
                ),
                "name_contains_raw": bool(
                    "raw" in column.lower()
                ),
            }
        )

    return pd.DataFrame(rows)


def choose_gp_probability(
    frame: pd.DataFrame,
    book_keys: list[str],
) -> tuple[str, pd.DataFrame]:
    candidates = numeric_probability_candidates(
        frame,
        ("gp", "gaussian"),
    )
    audit = probability_candidate_audit(
        frame,
        book_keys,
        candidates,
        source="gp",
    )
    if audit.empty:
        fail("Could not identify any valid GP probability column.")

    coherent = audit.loc[
        audit["maximum_absolute_book_sum_error"] <= 1e-6
    ].copy()
    if coherent.empty:
        fail(
            "No candidate GP probability column sums to one within "
            "complete contract books."
        )

    coherent["priority"] = coherent["column"].map(
        lambda column: (
            0
            if column.lower()
            in {
                "gp_event_probability",
                "gp_probability",
                "p_gp",
            }
            else 1
        )
    )
    coherent = coherent.sort_values(
        [
            "priority",
            "maximum_absolute_book_sum_error",
            "mean_absolute_book_sum_error",
            "column",
        ],
        kind="stable",
    )
    return str(coherent.iloc[0]["column"]), audit


def choose_market_probability(
    frame: pd.DataFrame,
    book_keys: list[str],
) -> tuple[str, bool, pd.DataFrame]:
    candidates = numeric_probability_candidates(
        frame,
        ("market", "polymarket", "p_market", "price"),
    )
    audit = probability_candidate_audit(
        frame,
        book_keys,
        candidates,
        source="market",
    )
    if audit.empty:
        fail("Could not identify any valid market probability or price column.")

    coherent = audit.loc[
        audit["maximum_absolute_book_sum_error"] <= 1e-6
    ].copy()

    if not coherent.empty:
        coherent["priority"] = coherent.apply(
            lambda row: (
                0
                if row["name_contains_normalised"]
                else (
                    2
                    if row["name_contains_raw"]
                    else 1
                )
            ),
            axis=1,
        )
        coherent = coherent.sort_values(
            [
                "priority",
                "maximum_absolute_book_sum_error",
                "mean_absolute_book_sum_error",
                "column",
            ],
            kind="stable",
        )
        return str(coherent.iloc[0]["column"]), False, audit

    audit = audit.copy()
    audit["priority"] = audit.apply(
        lambda row: (
            0
            if row["name_contains_raw"]
            else 1
        ),
        axis=1,
    )
    audit = audit.sort_values(
        [
            "priority",
            "mean_absolute_book_sum_error",
            "column",
        ],
        kind="stable",
    )
    return str(audit.iloc[0]["column"]), True, audit


def choose_outcome_column(
    frame: pd.DataFrame,
    book_keys: list[str],
) -> tuple[str, pd.DataFrame]:
    explicit = [
        "outcome",
        "event_outcome",
        "realised_outcome",
        "realized_outcome",
        "y",
        "is_winner",
        "realised_yes",
        "realized_yes",
    ]
    candidates: list[str] = []

    for column in frame.columns:
        lowered = column.lower()
        if (
            lowered in explicit
            or any(
                token in lowered
                for token in (
                    "outcome",
                    "realised",
                    "realized",
                    "winner",
                )
            )
        ):
            values = pd.to_numeric(
                frame[column],
                errors="coerce",
            )
            unique = set(
                values.dropna().astype(float).unique().tolist()
            )
            if values.notna().mean() >= 0.99 and unique <= {0.0, 1.0}:
                candidates.append(column)

    rows: list[dict[str, Any]] = []
    for column in candidates:
        values = pd.to_numeric(
            frame[column],
            errors="raise",
        )
        sums = (
            frame.assign(_outcome=values)
            .groupby(book_keys, sort=False)["_outcome"]
            .sum()
        )
        rows.append(
            {
                "column": column,
                "books": int(len(sums)),
                "minimum_book_yes_count": float(sums.min()),
                "maximum_book_yes_count": float(sums.max()),
                "all_books_exactly_one_yes": bool(
                    np.allclose(
                        sums.to_numpy(dtype=float),
                        1.0,
                        atol=0.0,
                        rtol=0.0,
                    )
                ),
            }
        )

    audit = pd.DataFrame(rows)
    valid = audit.loc[
        audit["all_books_exactly_one_yes"]
    ].copy()
    if valid.empty:
        fail(
            "Could not identify a binary outcome column with exactly "
            "one realised Yes event in every complete contract book."
        )

    valid["priority"] = valid["column"].map(
        lambda column: (
            explicit.index(column.lower())
            if column.lower() in explicit
            else len(explicit)
        )
    )
    valid = valid.sort_values(
        ["priority", "column"],
        kind="stable",
    )
    return str(valid.iloc[0]["column"]), audit


def parse_label_sort_key(value: Any) -> tuple[float, float, str]:
    text = str(value).strip().lower()
    numbers = [
        float(token)
        for token in re.findall(r"-?\d+(?:\.\d+)?", text)
    ]

    if any(
        token in text
        for token in ("below", "under", "<=", "< ")
    ):
        upper = numbers[0] if numbers else -1e8
        return (-1e9, upper, text)

    if any(
        token in text
        for token in ("above", "over", ">=", "> ")
    ):
        lower = numbers[0] if numbers else 1e8
        return (lower, 1e9, text)

    if len(numbers) >= 2:
        return (min(numbers[0], numbers[1]), max(numbers[0], numbers[1]), text)
    if len(numbers) == 1:
        return (numbers[0], numbers[0], text)
    return (math.nan, math.nan, text)


def discover_columns(
    raw: pd.DataFrame,
) -> tuple[dict[str, str], pd.DataFrame, pd.DataFrame]:
    columns = list(raw.columns)
    date_column = find_column(
        columns,
        exact=["target_date", "event_date", "date"],
    )
    rule_column = find_column(
        columns,
        exact=["decision_rule", "rule"],
    )
    if not date_column or not rule_column:
        fail(
            "Could not identify target-date and decision-rule columns. "
            f"Available columns: {columns}"
        )

    provisional = pd.DataFrame(
        {
            "_date": pd.to_datetime(
                raw[date_column],
                errors="raise",
            ).dt.normalize(),
            "_rule": raw[rule_column].map(normalise_rule),
        }
    )
    book_keys = ["_date", "_rule"]
    working = raw.copy()
    working["_date"] = provisional["_date"]
    working["_rule"] = provisional["_rule"]

    gp_column, gp_audit = choose_gp_probability(
        working,
        book_keys,
    )
    (
        market_column,
        market_requires_normalisation,
        market_audit,
    ) = choose_market_probability(
        working,
        book_keys,
    )
    outcome_column, outcome_audit = choose_outcome_column(
        working,
        book_keys,
    )

    mapping: dict[str, str] = {
        "date": date_column,
        "rule": rule_column,
        "gp_probability": gp_column,
        "market_source_probability": market_column,
        "outcome": outcome_column,
    }

    optional = {
        "event_order": find_column(
            columns,
            exact=[
                "event_order",
                "contract_order",
                "interval_order",
                "event_rank",
                "contract_rank",
            ],
            contains_all=["order"],
            contains_any=["event", "contract", "interval"],
        ),
        "lower_bound": find_column(
            columns,
            exact=[
                "lower_bound_c",
                "event_lower_bound_c",
                "contract_lower_bound_c",
                "lower_c",
            ],
            contains_all=["lower", "bound"],
            exclude=["probability"],
        ),
        "upper_bound": find_column(
            columns,
            exact=[
                "upper_bound_c",
                "event_upper_bound_c",
                "contract_upper_bound_c",
                "upper_c",
            ],
            contains_all=["upper", "bound"],
            exclude=["probability"],
        ),
        "event_label": find_column(
            columns,
            exact=[
                "event_label",
                "contract_label",
                "event_name",
                "contract_name",
                "label",
                "question",
            ],
            contains_any=["label", "question", "event_name", "contract_name"],
            exclude=["decision_rule"],
        ),
        "event_key": find_column(
            columns,
            exact=[
                "event_id",
                "contract_id",
                "event_key",
                "contract_key",
                "condition_id",
                "token_id",
            ],
            contains_any=["event_id", "contract_id", "condition_id"],
        ),
        "forecast_daily_max_c": find_column(
            columns,
            exact=["forecast_daily_max_c"],
            contains_all=["forecast", "daily", "max"],
        ),
        "gp_temperature_mean_c": find_column(
            columns,
            exact=[
                "gp_temperature_mean_c",
                "temperature_predictive_mean_c",
            ],
            contains_all=["temperature", "mean"],
            contains_any=["gp", "predictive"],
        ),
    }

    for key, value in optional.items():
        if value is not None:
            mapping[key] = value

    probability_audit = pd.concat(
        [gp_audit, market_audit],
        ignore_index=True,
    )
    probability_audit["selected"] = (
        (
            (probability_audit["source"] == "gp")
            & (probability_audit["column"] == gp_column)
        )
        | (
            (probability_audit["source"] == "market")
            & (
                probability_audit["column"]
                == market_column
            )
        )
    )
    probability_audit["market_normalisation_applied"] = (
        probability_audit["source"].eq("market")
        & probability_audit["selected"]
        & market_requires_normalisation
    )

    outcome_audit["selected"] = (
        outcome_audit["column"] == outcome_column
    )

    mapping["market_requires_normalisation"] = str(
        market_requires_normalisation
    )

    return mapping, probability_audit, outcome_audit


def prepare_panel(
    raw: pd.DataFrame,
    columns: dict[str, str],
) -> pd.DataFrame:
    panel = pd.DataFrame(
        {
            "source_row_id": np.arange(len(raw), dtype=int),
            "target_date": pd.to_datetime(
                raw[columns["date"]],
                errors="raise",
            ).dt.normalize(),
            "decision_rule": raw[columns["rule"]].map(normalise_rule),
            "gp_probability": pd.to_numeric(
                raw[columns["gp_probability"]],
                errors="raise",
            ),
            "market_source_probability": pd.to_numeric(
                raw[columns["market_source_probability"]],
                errors="raise",
            ),
            "realised_yes": pd.to_numeric(
                raw[columns["outcome"]],
                errors="raise",
            ).astype(int),
        }
    )

    for key in (
        "event_order",
        "lower_bound",
        "upper_bound",
        "event_label",
        "event_key",
        "forecast_daily_max_c",
        "gp_temperature_mean_c",
    ):
        if key in columns:
            if key in {
                "event_order",
                "lower_bound",
                "upper_bound",
                "forecast_daily_max_c",
                "gp_temperature_mean_c",
            }:
                panel[key] = pd.to_numeric(
                    raw[columns[key]],
                    errors="coerce",
                )
            else:
                panel[key] = raw[columns[key]].astype(str)

    if len(panel) != EXPECTED_ROWS:
        fail(
            f"Expected {EXPECTED_ROWS} exact-common-support rows; "
            f"found {len(panel)}."
        )

    if set(panel["decision_rule"]) != set(RULE_ORDER):
        fail(
            "Exact-common-support panel does not contain the four "
            "certified decision rules."
        )

    panel["book_key"] = (
        panel["target_date"].dt.strftime("%Y-%m-%d")
        + "|"
        + panel["decision_rule"]
    )

    if panel["target_date"].nunique() != EXPECTED_DATES:
        fail(
            f"Expected {EXPECTED_DATES} exact-common-support dates; "
            f"found {panel['target_date'].nunique()}."
        )

    if panel["book_key"].nunique() != EXPECTED_BOOKS:
        fail(
            f"Expected {EXPECTED_BOOKS} exact-common-support books; "
            f"found {panel['book_key'].nunique()}."
        )

    if set(panel["realised_yes"].unique()) != {0, 1}:
        fail("Outcome column is not binary.")

    yes_counts = panel.groupby("book_key")["realised_yes"].sum()
    if not (yes_counts == 1).all():
        fail("Every exact-common-support book must contain exactly one Yes.")

    gp_sums = panel.groupby("book_key")["gp_probability"].sum()
    if float(np.max(np.abs(gp_sums - 1.0))) > 1e-6:
        fail("Selected GP probabilities do not sum to one within every book.")

    market_requires_normalisation = (
        columns["market_requires_normalisation"] == "True"
    )
    if market_requires_normalisation:
        market_sums = panel.groupby(
            "book_key"
        )["market_source_probability"].transform("sum")
        if (market_sums <= 0).any():
            fail("At least one market book has non-positive total price mass.")
        panel["market_probability"] = (
            panel["market_source_probability"]
            / market_sums
        )
    else:
        panel["market_probability"] = panel[
            "market_source_probability"
        ]

    market_sums = panel.groupby("book_key")["market_probability"].sum()
    if float(np.max(np.abs(market_sums - 1.0))) > 1e-8:
        fail(
            "Normalised market probabilities do not sum to one "
            "within every book."
        )

    for column in ("gp_probability", "market_probability"):
        if (
            panel[column].isna().any()
            or not np.isfinite(
                panel[column].to_numpy(dtype=float)
            ).all()
            or (panel[column] < -1e-12).any()
            or (panel[column] > 1.0 + 1e-12).any()
        ):
            fail(f"Invalid values in {column}.")

    panel["sample_period"] = np.where(
        panel["target_date"].dt.month == 6,
        "june_out_of_sample",
        "weather_plus_market_development",
    )

    development_dates = panel.loc[
        panel["sample_period"]
        == "weather_plus_market_development",
        "target_date",
    ].nunique()
    june_dates = panel.loc[
        panel["sample_period"] == "june_out_of_sample",
        "target_date",
    ].nunique()

    if development_dates != EXPECTED_DEVELOPMENT_DATES:
        fail(
            f"Expected {EXPECTED_DEVELOPMENT_DATES} development dates; "
            f"found {development_dates}."
        )
    if june_dates != EXPECTED_JUNE_DATES:
        fail(
            f"Expected {EXPECTED_JUNE_DATES} June dates; "
            f"found {june_dates}."
        )

    panel = add_contract_order(panel)

    if panel.duplicated(
        ["target_date", "decision_rule", "contract_rank"]
    ).any():
        fail("Contract ordering is not unique within at least one book.")

    panel["gp_modal_rank"] = (
        panel.sort_values(
            [
                "book_key",
                "gp_probability",
                "contract_rank",
            ],
            ascending=[True, False, True],
            kind="stable",
        )
        .groupby("book_key", sort=False)["contract_rank"]
        .transform("first")
    )
    # The transform above is indexed to the sorted frame. Re-map explicitly.
    gp_modes = (
        panel.sort_values(
            [
                "book_key",
                "gp_probability",
                "contract_rank",
            ],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop_duplicates("book_key")
        .set_index("book_key")["contract_rank"]
    )
    market_modes = (
        panel.sort_values(
            [
                "book_key",
                "market_probability",
                "contract_rank",
            ],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop_duplicates("book_key")
        .set_index("book_key")["contract_rank"]
    )
    panel["gp_modal_rank"] = panel["book_key"].map(gp_modes).astype(int)
    panel["market_modal_rank"] = (
        panel["book_key"].map(market_modes).astype(int)
    )
    panel["signed_rank_from_gp_mode"] = (
        panel["contract_rank"] - panel["gp_modal_rank"]
    )

    return panel.sort_values(
        ["target_date", "decision_rule", "contract_rank"],
        kind="stable",
    ).reset_index(drop=True)


def add_contract_order(panel: pd.DataFrame) -> pd.DataFrame:
    working = panel.copy()

    if "event_order" in working.columns:
        order = pd.to_numeric(
            working["event_order"],
            errors="coerce",
        )
        if order.notna().all():
            working["_sort_primary"] = order
            working["_sort_secondary"] = order
        else:
            working.drop(columns=["event_order"], inplace=True)

    if "_sort_primary" not in working.columns:
        if (
            "lower_bound" in working.columns
            and "upper_bound" in working.columns
        ):
            lower = pd.to_numeric(
                working["lower_bound"],
                errors="coerce",
            )
            upper = pd.to_numeric(
                working["upper_bound"],
                errors="coerce",
            )
            working["_sort_primary"] = lower.fillna(-1e9)
            working["_sort_secondary"] = upper.fillna(1e9)
        elif "event_label" in working.columns:
            parsed = working["event_label"].map(parse_label_sort_key)
            working["_sort_primary"] = [
                value[0] for value in parsed
            ]
            working["_sort_secondary"] = [
                value[1] for value in parsed
            ]
            if (
                working["_sort_primary"].isna().any()
                or working["_sort_secondary"].isna().any()
            ):
                fail(
                    "Could not derive a complete canonical contract "
                    "ordering from event labels."
                )
        else:
            fail(
                "Could not identify event order, interval bounds or "
                "event labels for contract-rank diagnostics."
            )

    tie_breaker = (
        working["event_label"]
        if "event_label" in working.columns
        else working["source_row_id"].astype(str)
    )
    working["_sort_label"] = tie_breaker.astype(str)

    working = working.sort_values(
        [
            "book_key",
            "_sort_primary",
            "_sort_secondary",
            "_sort_label",
            "source_row_id",
        ],
        kind="stable",
    )
    working["contract_rank"] = (
        working.groupby("book_key", sort=False).cumcount() + 1
    )

    duplicated_sort = working.duplicated(
        [
            "book_key",
            "_sort_primary",
            "_sort_secondary",
            "_sort_label",
        ],
        keep=False,
    )
    if duplicated_sort.any():
        duplicate_rows = working.loc[
            duplicated_sort,
            [
                "book_key",
                "_sort_primary",
                "_sort_secondary",
                "_sort_label",
                "source_row_id",
            ],
        ]
        write_csv(
            OUT / "phase20_contract_order_tie_audit.csv",
            duplicate_rows,
        )

    return working.drop(
        columns=[
            "_sort_primary",
            "_sort_secondary",
            "_sort_label",
        ]
    )


class ScoreDesign:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame.reset_index(drop=True).copy()
        self.book_codes, self.book_labels = pd.factorize(
            self.frame["book_key"],
            sort=True,
        )
        self.date_codes_event, self.date_labels = pd.factorize(
            self.frame["target_date"],
            sort=True,
        )
        self.book_count = len(self.book_labels)
        self.date_count = len(self.date_labels)

        self.book_event_counts = np.bincount(
            self.book_codes,
            minlength=self.book_count,
        ).astype(float)

        first_rows = (
            self.frame.assign(_book_code=self.book_codes)
            .sort_values(
                ["_book_code", "contract_rank"],
                kind="stable",
            )
            .drop_duplicates("_book_code")
            .sort_values("_book_code")
        )
        date_lookup = {
            value: index
            for index, value in enumerate(self.date_labels)
        }
        self.book_date_codes = np.array(
            [
                date_lookup[value]
                for value in first_rows["target_date"]
            ],
            dtype=int,
        )
        self.date_book_counts = np.bincount(
            self.book_date_codes,
            minlength=self.date_count,
        ).astype(float)

        if np.any(self.book_event_counts <= 0):
            fail("Empty contract book encountered in score design.")
        if np.any(self.date_book_counts <= 0):
            fail("Empty target date encountered in score design.")

        self.outcome = self.frame["realised_yes"].to_numpy(dtype=float)

    def score(
        self,
        probabilities: np.ndarray,
    ) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
        q = np.asarray(probabilities, dtype=float)
        if len(q) != len(self.frame):
            fail("Probability vector length does not match score panel.")
        if np.any(~np.isfinite(q)):
            fail("Non-finite probability supplied to score calculation.")
        if np.any(q < -1e-12) or np.any(q > 1.0 + 1e-12):
            fail("Probability supplied to score calculation lies outside [0,1].")

        q = np.clip(q, 0.0, 1.0)
        q_safe = np.clip(
            q,
            PROBABILITY_FLOOR,
            1.0 - PROBABILITY_FLOOR,
        )

        binary_brier_event = (q - self.outcome) ** 2
        binary_log_event = -(
            self.outcome * np.log(q_safe)
            + (1.0 - self.outcome) * np.log(1.0 - q_safe)
        )
        categorical_log_event = -self.outcome * np.log(q_safe)
        multiclass_brier_event = (q - self.outcome) ** 2

        def book_sum(values: np.ndarray) -> np.ndarray:
            return np.bincount(
                self.book_codes,
                weights=values,
                minlength=self.book_count,
            )

        book_scores = pd.DataFrame(
            {
                "book_key": self.book_labels,
                "date_code": self.book_date_codes,
                "binary_brier": (
                    book_sum(binary_brier_event)
                    / self.book_event_counts
                ),
                "binary_log": (
                    book_sum(binary_log_event)
                    / self.book_event_counts
                ),
                "categorical_log": book_sum(
                    categorical_log_event
                ),
                "multiclass_brier": book_sum(
                    multiclass_brier_event
                ),
            }
        )
        date_scores = pd.DataFrame(
            {
                "target_date": pd.to_datetime(self.date_labels),
            }
        )
        metrics = [
            "binary_brier",
            "binary_log",
            "categorical_log",
            "multiclass_brier",
        ]
        for metric in metrics:
            date_scores[metric] = (
                np.bincount(
                    self.book_date_codes,
                    weights=book_scores[metric].to_numpy(dtype=float),
                    minlength=self.date_count,
                )
                / self.date_book_counts
            )

        summary = {
            metric: float(date_scores[metric].mean())
            for metric in metrics
        }
        return summary, book_scores, date_scores


def stable_seed(*parts: Any) -> int:
    text = "|".join(str(part) for part in parts)
    return BOOTSTRAP_SEED + sum(
        (index + 1) * ord(character)
        for index, character in enumerate(text)
    ) % 1_000_000


def choose_weight(
    grid: pd.DataFrame,
    metric: str,
) -> float:
    minimum = float(grid[metric].min())
    candidates = grid.loc[
        np.isclose(
            grid[metric],
            minimum,
            atol=1e-14,
            rtol=0.0,
        )
    ].copy()
    candidates["distance_from_half"] = np.abs(
        candidates["gp_weight"] - 0.5
    )
    candidates = candidates.sort_values(
        ["distance_from_half", "gp_weight"],
        ascending=[True, False],
        kind="stable",
    )
    return float(candidates.iloc[0]["gp_weight"])


def build_weight_grid(
    development: pd.DataFrame,
) -> tuple[pd.DataFrame, np.ndarray, list[pd.Timestamp]]:
    design = ScoreDesign(development)
    gp = development["gp_probability"].to_numpy(dtype=float)
    market = development["market_probability"].to_numpy(dtype=float)

    rows: list[dict[str, Any]] = []
    date_metric_matrix = np.empty(
        (design.date_count, len(WEIGHT_GRID)),
        dtype=float,
    )

    for index, weight in enumerate(WEIGHT_GRID):
        probability = weight * gp + (1.0 - weight) * market
        summary, _, date_scores = design.score(probability)
        rows.append(
            {
                "gp_weight": float(weight),
                "market_weight": float(1.0 - weight),
                **summary,
                "development_dates": int(design.date_count),
                "development_books": int(design.book_count),
                "probability_pool": (
                    "convex linear pool of coherent GP and "
                    "normalised market book probabilities"
                ),
            }
        )
        date_metric_matrix[:, index] = date_scores[
            PRIMARY_SELECTION_METRIC
        ].to_numpy(dtype=float)

    grid = pd.DataFrame(rows)
    return (
        grid,
        date_metric_matrix,
        [
            pd.Timestamp(value)
            for value in design.date_labels
        ],
    )


def bootstrap_weight_selection(
    date_metric_matrix: np.ndarray,
    dates: list[pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_dates, n_weights = date_metric_matrix.shape
    if n_dates != EXPECTED_DEVELOPMENT_DATES:
        fail(
            "Weight-bootstrap matrix does not contain the certified "
            "67 development dates."
        )
    if n_weights != len(WEIGHT_GRID):
        fail("Weight-bootstrap matrix does not match the weight grid.")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    counts = rng.multinomial(
        n_dates,
        np.full(n_dates, 1.0 / n_dates),
        size=WEIGHT_BOOTSTRAP_REPLICATIONS,
    )
    objectives = counts @ date_metric_matrix / n_dates
    selected_indices = np.argmin(objectives, axis=1)
    selected_weights = WEIGHT_GRID[selected_indices]

    replicates = pd.DataFrame(
        {
            "replication": np.arange(
                1,
                WEIGHT_BOOTSTRAP_REPLICATIONS + 1,
            ),
            "selected_gp_weight": selected_weights,
            "selected_market_weight": 1.0 - selected_weights,
            "minimum_bootstrap_categorical_log": objectives[
                np.arange(WEIGHT_BOOTSTRAP_REPLICATIONS),
                selected_indices,
            ],
        }
    )

    summary = pd.DataFrame(
        [
            {
                "replications": WEIGHT_BOOTSTRAP_REPLICATIONS,
                "bootstrap_unit": "target_date",
                "development_dates": n_dates,
                "median_gp_weight": float(
                    np.median(selected_weights)
                ),
                "mean_gp_weight": float(
                    np.mean(selected_weights)
                ),
                "lower_95_gp_weight": float(
                    np.quantile(selected_weights, 0.025)
                ),
                "upper_95_gp_weight": float(
                    np.quantile(selected_weights, 0.975)
                ),
                "probability_gp_weight_zero": float(
                    np.mean(selected_weights == 0.0)
                ),
                "probability_gp_weight_one": float(
                    np.mean(selected_weights == 1.0)
                ),
                "unique_selected_weights": int(
                    pd.Series(selected_weights).nunique()
                ),
                "seed": BOOTSTRAP_SEED,
                "development_date_start": str(min(dates).date()),
                "development_date_end": str(max(dates).date()),
            }
        ]
    )
    return replicates, summary


def score_model(
    frame: pd.DataFrame,
    probability: np.ndarray,
    model: str,
    sample_period: str,
    selected_using: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    design = ScoreDesign(frame)
    summary, _, date_scores = design.score(probability)
    date_scores = date_scores.copy()
    date_scores["model"] = model
    date_scores["sample_period"] = sample_period
    return (
        {
            "sample_period": sample_period,
            "model": model,
            "dates": int(design.date_count),
            "books": int(design.book_count),
            **summary,
            "selected_using": selected_using,
            "score_aggregation": (
                "book score averaged within target date, then "
                "target dates equally weighted"
            ),
        },
        date_scores,
    )


def paired_bootstrap_interval(
    differences: np.ndarray,
    seed: int,
) -> tuple[float, float, float, float]:
    values = np.asarray(differences, dtype=float)
    if len(values) < 2 or np.any(~np.isfinite(values)):
        fail("Invalid paired date-level difference vector.")

    rng = np.random.default_rng(seed)
    counts = rng.multinomial(
        len(values),
        np.full(len(values), 1.0 / len(values)),
        size=DATE_BOOTSTRAP_REPLICATIONS,
    )
    means = counts @ values / len(values)

    return (
        float(values.mean()),
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
        float(np.mean(means < 0.0)),
    )


def build_score_outputs(
    panel: pd.DataFrame,
    selected_weight: float,
    oracle_june_weight: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    date_frames: list[pd.DataFrame] = []

    probability_models = {
        "gp": lambda frame: frame[
            "gp_probability"
        ].to_numpy(dtype=float),
        "market_normalised": lambda frame: frame[
            "market_probability"
        ].to_numpy(dtype=float),
        "equal_50_50_pool": lambda frame: (
            0.5
            * frame["gp_probability"].to_numpy(dtype=float)
            + 0.5
            * frame["market_probability"].to_numpy(dtype=float)
        ),
        "development_selected_pool": lambda frame: (
            selected_weight
            * frame["gp_probability"].to_numpy(dtype=float)
            + (1.0 - selected_weight)
            * frame["market_probability"].to_numpy(dtype=float)
        ),
        "june_oracle_pool_post_hoc": lambda frame: (
            oracle_june_weight
            * frame["gp_probability"].to_numpy(dtype=float)
            + (1.0 - oracle_june_weight)
            * frame["market_probability"].to_numpy(dtype=float)
        ),
    }

    for sample_period in (
        "weather_plus_market_development",
        "june_out_of_sample",
    ):
        frame = panel.loc[
            panel["sample_period"] == sample_period
        ].copy()

        for model, function in probability_models.items():
            if (
                model == "june_oracle_pool_post_hoc"
                and sample_period
                != "june_out_of_sample"
            ):
                continue

            if model == "development_selected_pool":
                selected_using = (
                    "minimum development-period date-balanced "
                    "categorical log score"
                )
            elif model == "june_oracle_pool_post_hoc":
                selected_using = (
                    "minimum June date-balanced categorical log "
                    "score; diagnostic only"
                )
            else:
                selected_using = "not estimated"

            summary, date_scores = score_model(
                frame,
                function(frame),
                model=model,
                sample_period=sample_period,
                selected_using=selected_using,
            )
            summary_rows.append(summary)
            date_frames.append(date_scores)

    score_summary = pd.DataFrame(summary_rows)
    date_score_panel = pd.concat(
        date_frames,
        ignore_index=True,
    )

    june = date_score_panel.loc[
        date_score_panel["sample_period"] == "june_out_of_sample"
    ]
    paired_rows: list[dict[str, Any]] = []

    comparisons = [
        ("development_selected_pool", "gp"),
        ("development_selected_pool", "market_normalised"),
        ("equal_50_50_pool", "gp"),
        ("equal_50_50_pool", "market_normalised"),
    ]
    metrics = [
        "binary_brier",
        "binary_log",
        "categorical_log",
        "multiclass_brier",
    ]

    for first, second in comparisons:
        first_frame = june.loc[
            june["model"] == first
        ].set_index("target_date")
        second_frame = june.loc[
            june["model"] == second
        ].set_index("target_date")

        if not first_frame.index.equals(second_frame.index):
            fail(
                "June date-level score panels are not exactly paired."
            )

        for metric in metrics:
            differences = (
                first_frame[metric] - second_frame[metric]
            ).to_numpy(dtype=float)
            mean, lower, upper, probability_negative = (
                paired_bootstrap_interval(
                    differences,
                    seed=stable_seed(
                        "june_paired",
                        first,
                        second,
                        metric,
                    ),
                )
            )
            paired_rows.append(
                {
                    "first_model": first,
                    "second_model": second,
                    "metric": metric,
                    "difference_definition": (
                        "first model score minus second model score"
                    ),
                    "mean_difference": mean,
                    "bootstrap_lower_95": lower,
                    "bootstrap_upper_95": upper,
                    "bootstrap_probability_difference_below_zero": (
                        probability_negative
                    ),
                    "dates": int(len(differences)),
                    "bootstrap_replications": (
                        DATE_BOOTSTRAP_REPLICATIONS
                    ),
                    "bootstrap_unit": "target_date",
                    "negative_difference_favours": first,
                }
            )

    paired = pd.DataFrame(paired_rows)

    if len(score_summary) != 9:
        fail(
            f"Expected nine score-summary rows; "
            f"found {len(score_summary)}."
        )
    if len(paired) != 16:
        fail(
            f"Expected 16 June paired-difference rows; "
            f"found {len(paired)}."
        )

    return score_summary, date_score_panel, paired


def rule_specific_weights(
    development: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for rule in RULE_ORDER:
        frame = development.loc[
            development["decision_rule"] == rule
        ].copy()
        design = ScoreDesign(frame)
        gp = frame["gp_probability"].to_numpy(dtype=float)
        market = frame["market_probability"].to_numpy(dtype=float)

        metric_rows: list[dict[str, float]] = []
        for weight in WEIGHT_GRID:
            probability = (
                weight * gp
                + (1.0 - weight) * market
            )
            summary, _, _ = design.score(probability)
            metric_rows.append(
                {
                    "gp_weight": float(weight),
                    **summary,
                }
            )
        grid = pd.DataFrame(metric_rows)
        selected = choose_weight(
            grid,
            PRIMARY_SELECTION_METRIC,
        )
        selected_row = grid.loc[
            grid["gp_weight"] == selected
        ].iloc[0]

        rows.append(
            {
                "decision_rule": rule,
                "development_dates": int(design.date_count),
                "development_books": int(design.book_count),
                "selected_gp_weight": selected,
                "selected_market_weight": 1.0 - selected,
                "selected_categorical_log": float(
                    selected_row["categorical_log"]
                ),
                "gp_only_categorical_log": float(
                    grid.loc[
                        grid["gp_weight"] == 1.0,
                        "categorical_log",
                    ].iloc[0]
                ),
                "market_only_categorical_log": float(
                    grid.loc[
                        grid["gp_weight"] == 0.0,
                        "categorical_log",
                    ].iloc[0]
                ),
                "status": (
                    "diagnostic only; not used for primary June pool"
                ),
            }
        )

    return pd.DataFrame(rows)


def jensen_shannon(
    first: np.ndarray,
    second: np.ndarray,
) -> float:
    p = np.clip(
        np.asarray(first, dtype=float),
        PROBABILITY_FLOOR,
        1.0,
    )
    q = np.clip(
        np.asarray(second, dtype=float),
        PROBABILITY_FLOOR,
        1.0,
    )
    p = p / p.sum()
    q = q / q.sum()
    midpoint = 0.5 * (p + q)
    return float(
        0.5 * np.sum(p * np.log(p / midpoint))
        + 0.5 * np.sum(q * np.log(q / midpoint))
    )


def build_discrepancy_panels(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    event = panel.copy()
    event["gp_minus_market_probability"] = (
        event["gp_probability"]
        - event["market_probability"]
    )
    event["market_minus_gp_probability"] = (
        -event["gp_minus_market_probability"]
    )
    event["absolute_probability_gap"] = np.abs(
        event["gp_minus_market_probability"]
    )
    event["log_ratio_market_to_gp"] = np.log(
        np.clip(
            event["market_probability"],
            PROBABILITY_FLOOR,
            1.0,
        )
        / np.clip(
            event["gp_probability"],
            PROBABILITY_FLOOR,
            1.0,
        )
    )
    event["clr_log_ratio_market_minus_gp"] = (
        event["log_ratio_market_to_gp"]
        - event.groupby("book_key")[
            "log_ratio_market_to_gp"
        ].transform("mean")
    )

    def rank_bucket(value: int) -> str:
        if value <= -3:
            return "<=-3"
        if value >= 3:
            return ">=3"
        return str(int(value))

    event["signed_rank_bucket"] = event[
        "signed_rank_from_gp_mode"
    ].map(rank_bucket)

    book_rows: list[dict[str, Any]] = []

    for book_key, group in event.groupby(
        "book_key",
        sort=True,
    ):
        group = group.sort_values("contract_rank")
        p = group["gp_probability"].to_numpy(dtype=float)
        q = group["market_probability"].to_numpy(dtype=float)
        rank = group["contract_rank"].to_numpy(dtype=float)
        gp_mode = int(group["gp_modal_rank"].iloc[0])
        market_mode = int(group["market_modal_rank"].iloc[0])
        realised_row = group.loc[group["realised_yes"] == 1].iloc[0]

        upper_mask = rank > gp_mode
        lower_mask = rank < gp_mode

        row: dict[str, Any] = {
            "book_key": book_key,
            "target_date": group["target_date"].iloc[0],
            "decision_rule": group["decision_rule"].iloc[0],
            "sample_period": group["sample_period"].iloc[0],
            "contracts": int(len(group)),
            "total_variation_distance": float(
                0.5 * np.sum(np.abs(p - q))
            ),
            "jensen_shannon_divergence": jensen_shannon(p, q),
            "maximum_absolute_probability_gap": float(
                np.max(np.abs(p - q))
            ),
            "gp_modal_rank": gp_mode,
            "market_modal_rank": market_mode,
            "modal_rank_shift_market_minus_gp": (
                market_mode - gp_mode
            ),
            "mode_disagreement": int(market_mode != gp_mode),
            "gp_expected_contract_rank": float(
                np.sum(rank * p)
            ),
            "market_expected_contract_rank": float(
                np.sum(rank * q)
            ),
            "expected_rank_shift_market_minus_gp": float(
                np.sum(rank * q) - np.sum(rank * p)
            ),
            "market_upper_mass_shift_relative_to_gp_mode": float(
                np.sum(q[upper_mask]) - np.sum(p[upper_mask])
            ),
            "market_lower_mass_shift_relative_to_gp_mode": float(
                np.sum(q[lower_mask]) - np.sum(p[lower_mask])
            ),
            "gp_probability_realised_event": float(
                realised_row["gp_probability"]
            ),
            "market_probability_realised_event": float(
                realised_row["market_probability"]
            ),
            "realised_probability_difference_gp_minus_market": float(
                realised_row["gp_probability"]
                - realised_row["market_probability"]
            ),
            "realised_rank_from_gp_mode": int(
                realised_row["signed_rank_from_gp_mode"]
            ),
        }

        for optional in (
            "forecast_daily_max_c",
            "gp_temperature_mean_c",
        ):
            if optional in group.columns:
                values = group[optional].dropna().unique()
                if len(values) == 1:
                    row[optional] = float(values[0])
                elif len(values) > 1:
                    fail(
                        f"{optional} is not constant within book "
                        f"{book_key}."
                    )

        book_rows.append(row)

    books = pd.DataFrame(book_rows)
    if len(books) != EXPECTED_BOOKS:
        fail(
            f"Expected {EXPECTED_BOOKS} book discrepancy rows; "
            f"found {len(books)}."
        )

    return event, books


def bootstrap_group_mean(
    frame: pd.DataFrame,
    value_column: str,
    seed: int,
) -> tuple[float, float, float]:
    date_values = (
        frame.groupby("target_date", as_index=False)[value_column]
        .mean()
        .sort_values("target_date")
    )
    values = date_values[value_column].to_numpy(dtype=float)
    mean, lower, upper, _ = paired_bootstrap_interval(
        values,
        seed=seed,
    )
    return mean, lower, upper


def build_book_discrepancy_summary(
    books: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metrics = [
        "total_variation_distance",
        "jensen_shannon_divergence",
        "maximum_absolute_probability_gap",
        "expected_rank_shift_market_minus_gp",
        "modal_rank_shift_market_minus_gp",
        "mode_disagreement",
        "market_upper_mass_shift_relative_to_gp_mode",
        "market_lower_mass_shift_relative_to_gp_mode",
        "realised_probability_difference_gp_minus_market",
    ]

    scopes: list[tuple[str, str, pd.DataFrame]] = [
        ("overall", "all", books),
    ]
    for period, group in books.groupby(
        "sample_period",
        sort=True,
    ):
        scopes.append(("sample_period", str(period), group))
    for rule, group in books.groupby(
        "decision_rule",
        sort=True,
    ):
        scopes.append(("decision_rule", str(rule), group))
    for (period, rule), group in books.groupby(
        ["sample_period", "decision_rule"],
        sort=True,
    ):
        scopes.append(
            (
                "sample_period_by_rule",
                f"{period}|{rule}",
                group,
            )
        )

    for scope, scope_value, group in scopes:
        for metric in metrics:
            mean, lower, upper = bootstrap_group_mean(
                group,
                metric,
                seed=stable_seed(
                    "book_discrepancy",
                    scope,
                    scope_value,
                    metric,
                ),
            )
            rows.append(
                {
                    "scope": scope,
                    "scope_value": scope_value,
                    "metric": metric,
                    "books": int(len(group)),
                    "dates": int(group["target_date"].nunique()),
                    "mean": mean,
                    "bootstrap_lower_95": lower,
                    "bootstrap_upper_95": upper,
                    "bootstrap_replications": (
                        DATE_BOOTSTRAP_REPLICATIONS
                    ),
                    "bootstrap_unit": "target_date",
                }
            )

    result = pd.DataFrame(rows)
    expected_scopes = 1 + 2 + 4 + 8
    if len(result) != expected_scopes * len(metrics):
        fail(
            "Unexpected book-discrepancy summary dimensions."
        )
    return result


def build_rank_discrepancy_summary(
    event: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metrics = [
        "gp_minus_market_probability",
        "clr_log_ratio_market_minus_gp",
    ]

    for (
        period,
        rule,
        bucket,
    ), group in event.groupby(
        [
            "sample_period",
            "decision_rule",
            "signed_rank_bucket",
        ],
        sort=True,
    ):
        for metric in metrics:
            mean, lower, upper = bootstrap_group_mean(
                group,
                metric,
                seed=stable_seed(
                    "rank_discrepancy",
                    period,
                    rule,
                    bucket,
                    metric,
                ),
            )
            rows.append(
                {
                    "sample_period": period,
                    "decision_rule": rule,
                    "signed_rank_bucket": bucket,
                    "metric": metric,
                    "event_rows": int(len(group)),
                    "books": int(group["book_key"].nunique()),
                    "dates": int(group["target_date"].nunique()),
                    "mean": mean,
                    "bootstrap_lower_95": lower,
                    "bootstrap_upper_95": upper,
                    "bootstrap_replications": (
                        DATE_BOOTSTRAP_REPLICATIONS
                    ),
                    "bootstrap_unit": "target_date",
                }
            )

    return pd.DataFrame(rows)


def standardise(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    sd = float(array.std(ddof=0))
    if sd <= 0:
        fail("Cannot standardise a constant regression variable.")
    return (array - array.mean()) / sd


def cluster_robust_ols(
    y: np.ndarray,
    x: np.ndarray,
    clusters: np.ndarray,
) -> dict[str, Any]:
    y_array = np.asarray(y, dtype=float)
    x_array = np.asarray(x, dtype=float)
    cluster_array = np.asarray(clusters)

    n, k = x_array.shape
    if np.linalg.matrix_rank(x_array) < k:
        fail("Discrepancy-regression design matrix is rank deficient.")

    xtx_inverse = np.linalg.inv(x_array.T @ x_array)
    beta = xtx_inverse @ x_array.T @ y_array
    residual = y_array - x_array @ beta

    unique_clusters = pd.unique(cluster_array)
    g = len(unique_clusters)
    if g <= k:
        fail("Too few date clusters for discrepancy regression.")

    meat = np.zeros((k, k), dtype=float)
    for cluster in unique_clusters:
        mask = cluster_array == cluster
        score = x_array[mask].T @ residual[mask]
        meat += np.outer(score, score)

    correction = (
        (g / (g - 1.0))
        * ((n - 1.0) / (n - k))
    )
    covariance = (
        correction
        * xtx_inverse
        @ meat
        @ xtx_inverse
    )
    standard_errors = np.sqrt(
        np.maximum(np.diag(covariance), 0.0)
    )
    z_statistics = np.divide(
        beta,
        standard_errors,
        out=np.full_like(beta, np.nan),
        where=standard_errors > 0,
    )
    p_values = 2.0 * stats.norm.sf(np.abs(z_statistics))

    tss = float(np.sum((y_array - y_array.mean()) ** 2))
    rss = float(np.sum(residual**2))
    r_squared = 1.0 - rss / tss if tss > 0 else math.nan

    restriction = np.eye(k)[1:, :]
    restricted_beta = restriction @ beta
    restricted_covariance = (
        restriction
        @ covariance
        @ restriction.T
    )
    wald = float(
        restricted_beta.T
        @ np.linalg.pinv(restricted_covariance)
        @ restricted_beta
    )
    df = k - 1
    wald_p = float(stats.chi2.sf(wald, df))

    return {
        "beta": beta,
        "standard_errors": standard_errors,
        "z_statistics": z_statistics,
        "p_values": p_values,
        "n": n,
        "k": k,
        "clusters": g,
        "r_squared": r_squared,
        "wald": wald,
        "wald_df": df,
        "wald_p": wald_p,
    }


def build_discrepancy_regressions(
    books: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = books.sort_values(
        ["target_date", "decision_rule"],
        kind="stable",
    ).copy()
    working["june_indicator"] = (
        working["sample_period"] == "june_out_of_sample"
    ).astype(float)
    working["time_z"] = standardise(
        (
            working["target_date"]
            - working["target_date"].min()
        ).dt.days.to_numpy(dtype=float)
    )

    temperature_source = None
    for candidate in (
        "gp_temperature_mean_c",
        "forecast_daily_max_c",
    ):
        if (
            candidate in working.columns
            and working[candidate].notna().all()
            and working[candidate].nunique() > 1
        ):
            temperature_source = candidate
            break

    names = [
        "intercept",
        "june_indicator",
        "time_z",
        "rule_12h_prior",
        "rule_6h_prior",
        "rule_event_day_open",
    ]
    columns = [
        np.ones(len(working)),
        working["june_indicator"].to_numpy(dtype=float),
        working["time_z"].to_numpy(dtype=float),
        (
            working["decision_rule"] == "12h_prior"
        ).to_numpy(dtype=float),
        (
            working["decision_rule"] == "6h_prior"
        ).to_numpy(dtype=float),
        (
            working["decision_rule"] == "event_day_open"
        ).to_numpy(dtype=float),
    ]

    if temperature_source is not None:
        names.append("temperature_level_z")
        columns.append(
            standardise(
                working[temperature_source].to_numpy(dtype=float)
            )
        )

    x = np.column_stack(columns)
    responses = [
        "expected_rank_shift_market_minus_gp",
        "total_variation_distance",
    ]

    coefficient_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for response in responses:
        fit = cluster_robust_ols(
            working[response].to_numpy(dtype=float),
            x,
            clusters=working["target_date"].to_numpy(),
        )

        for index, term in enumerate(names):
            coefficient_rows.append(
                {
                    "response": response,
                    "term": term,
                    "coefficient": float(fit["beta"][index]),
                    "date_cluster_robust_standard_error": float(
                        fit["standard_errors"][index]
                    ),
                    "z_statistic": float(
                        fit["z_statistics"][index]
                    ),
                    "two_sided_normal_p_value": float(
                        fit["p_values"][index]
                    ),
                    "rows": int(fit["n"]),
                    "date_clusters": int(fit["clusters"]),
                    "reference_rule": "24h_prior",
                    "temperature_source": (
                        temperature_source
                        if temperature_source is not None
                        else "not available"
                    ),
                }
            )

        summary_rows.append(
            {
                "response": response,
                "rows": int(fit["n"]),
                "date_clusters": int(fit["clusters"]),
                "parameters": int(fit["k"]),
                "r_squared": float(fit["r_squared"]),
                "joint_non_intercept_wald_statistic": float(
                    fit["wald"]
                ),
                "joint_non_intercept_degrees_freedom": int(
                    fit["wald_df"]
                ),
                "joint_non_intercept_cluster_robust_p_value": float(
                    fit["wald_p"]
                ),
                "temperature_source": (
                    temperature_source
                    if temperature_source is not None
                    else "not available"
                ),
                "inference": (
                    "target-date cluster-robust asymptotic "
                    "normal and chi-square reference"
                ),
            }
        )

    return (
        pd.DataFrame(coefficient_rows),
        pd.DataFrame(summary_rows),
    )


def create_figures(
    weight_grid: pd.DataFrame,
    score_summary: pd.DataFrame,
    book_summary: pd.DataFrame,
    rank_summary: pd.DataFrame,
    weight_replicates: pd.DataFrame,
) -> list[Path]:
    FIG.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    selected_weight = choose_weight(
        weight_grid,
        PRIMARY_SELECTION_METRIC,
    )
    figure, axis = plt.subplots(figsize=(8.0, 5.0))
    axis.plot(
        weight_grid["gp_weight"],
        weight_grid[PRIMARY_SELECTION_METRIC],
    )
    axis.axvline(
        selected_weight,
        linestyle="--",
        label=f"Selected GP weight = {selected_weight:.3f}",
    )
    axis.set_xlabel("GP weight in convex pool")
    axis.set_ylabel("Development mean categorical log score")
    axis.set_title("Development-period forecast-combination objective")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase20_weight_objective.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8.0, 5.0))
    axis.hist(
        weight_replicates["selected_gp_weight"],
        bins=np.linspace(0, 1, 41),
    )
    axis.axvline(selected_weight, linestyle="--")
    axis.set_xlabel("Bootstrap-selected GP weight")
    axis.set_ylabel("Replications")
    axis.set_title("Target-date bootstrap stability of combination weight")
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase20_weight_bootstrap.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    june = score_summary.loc[
        score_summary["sample_period"] == "june_out_of_sample"
    ].copy()
    model_order = [
        "gp",
        "market_normalised",
        "equal_50_50_pool",
        "development_selected_pool",
    ]
    june = june.set_index("model").reindex(model_order).reset_index()
    figure, axis = plt.subplots(figsize=(8.5, 5.0))
    axis.bar(
        june["model"],
        june["categorical_log"],
    )
    axis.set_ylabel("June mean categorical log score")
    axis.set_title("June out-of-sample proper-score comparison")
    axis.tick_params(axis="x", rotation=20)
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase20_june_score_comparison.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    tv = book_summary.loc[
        (
            book_summary["scope"]
            == "sample_period_by_rule"
        )
        & (
            book_summary["metric"]
            == "total_variation_distance"
        )
    ].copy()
    tv[["sample_period", "decision_rule"]] = (
        tv["scope_value"].str.split(
            "|",
            expand=True,
        )
    )
    figure, axis = plt.subplots(figsize=(9.0, 5.0))
    x = np.arange(len(RULE_ORDER))
    width = 0.35
    for offset, period in zip(
        (-width / 2.0, width / 2.0),
        [
            "weather_plus_market_development",
            "june_out_of_sample",
        ],
    ):
        group = (
            tv.loc[tv["sample_period"] == period]
            .set_index("decision_rule")
            .reindex(RULE_ORDER)
        )
        axis.bar(
            x + offset,
            group["mean"],
            width=width,
            label=period,
        )
    axis.set_xticks(x)
    axis.set_xticklabels([RULE_LABELS[rule] for rule in RULE_ORDER])
    axis.set_ylabel("Mean total-variation distance")
    axis.set_title("GP-market distributional disagreement by rule")
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase20_total_variation_by_rule.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    rank = rank_summary.loc[
        (
            rank_summary["metric"]
            == "gp_minus_market_probability"
        )
        & (
            rank_summary["decision_rule"]
            == "event_day_open"
        )
    ].copy()
    bucket_order = ["<=-3", "-2", "-1", "0", "1", "2", ">=3"]
    figure, axis = plt.subplots(figsize=(9.0, 5.0))
    for period in (
        "weather_plus_market_development",
        "june_out_of_sample",
    ):
        group = (
            rank.loc[rank["sample_period"] == period]
            .set_index("signed_rank_bucket")
            .reindex(bucket_order)
        )
        axis.plot(
            bucket_order,
            group["mean"],
            marker="o",
            label=period,
        )
    axis.axhline(0.0, linestyle="--")
    axis.set_xlabel("Contract rank relative to GP modal contract")
    axis.set_ylabel("Mean GP probability minus market probability")
    axis.set_title("Event-day-open probability discrepancy around the GP mode")
    axis.legend()
    axis.grid(alpha=0.3)
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase20_rank_discrepancy_event_day_open.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    return paths


def markdown_table(
    frame: pd.DataFrame,
    columns: list[str],
    headers: list[str],
    decimals: int = 5,
) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for _, row in frame.iterrows():
        values: list[str] = []
        for column in columns:
            value = row[column]
            if isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.{decimals}f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def main() -> None:
    for path in REQUIRED_PATHS:
        if not path.exists():
            fail(f"Required Phase 20 input is missing: {rel(path)}")

    phase19_spec = json.loads(
        PHASE19_SPEC_PATH.read_text(encoding="utf-8")
    )
    if phase19_spec.get("status") != "PASSED":
        fail("Phase 19 specification is not certified as PASSED.")

    raw = pd.read_csv(COMMON_PATH)
    columns, probability_audit, outcome_audit = discover_columns(raw)

    print(
        "PHASE20_COLUMN_MAP="
        + json.dumps(columns, sort_keys=True)
    )
    panel = prepare_panel(raw, columns)

    write_csv(
        OUT / "phase20_probability_column_audit.csv",
        probability_audit,
    )
    write_csv(
        OUT / "phase20_outcome_column_audit.csv",
        outcome_audit,
    )

    development = panel.loc[
        panel["sample_period"]
        == "weather_plus_market_development"
    ].copy()
    june = panel.loc[
        panel["sample_period"]
        == "june_out_of_sample"
    ].copy()

    weight_grid, date_metric_matrix, development_dates = (
        build_weight_grid(development)
    )
    selected_weight = choose_weight(
        weight_grid,
        PRIMARY_SELECTION_METRIC,
    )

    weight_replicates, weight_bootstrap_summary = (
        bootstrap_weight_selection(
            date_metric_matrix,
            development_dates,
        )
    )

    june_weight_grid, _, _ = build_weight_grid(june)
    oracle_june_weight = choose_weight(
        june_weight_grid,
        PRIMARY_SELECTION_METRIC,
    )

    rule_weights = rule_specific_weights(development)

    score_summary, date_score_panel, june_paired = (
        build_score_outputs(
            panel,
            selected_weight=selected_weight,
            oracle_june_weight=oracle_june_weight,
        )
    )

    event_discrepancy, book_discrepancy = (
        build_discrepancy_panels(panel)
    )
    book_summary = build_book_discrepancy_summary(
        book_discrepancy
    )
    rank_summary = build_rank_discrepancy_summary(
        event_discrepancy
    )
    (
        discrepancy_coefficients,
        discrepancy_regression_summary,
    ) = build_discrepancy_regressions(book_discrepancy)

    figure_paths = create_figures(
        weight_grid,
        score_summary,
        book_summary,
        rank_summary,
        weight_replicates,
    )

    gap_updates = pd.DataFrame(
        [
            {
                "gap_id": "G13",
                "gap": "Systematic GP-market discrepancy structure",
                "phase_closed": 20,
                "status": "CLOSED",
                "evidence": (
                    "phase20_book_discrepancy_panel.csv|"
                    "phase20_book_discrepancy_summary.csv|"
                    "phase20_rank_discrepancy_summary.csv|"
                    "phase20_discrepancy_regression_coefficients.csv|"
                    "phase20_discrepancy_regression_summary.csv"
                ),
            },
            {
                "gap_id": "G14",
                "gap": "Forecast combination",
                "phase_closed": 20,
                "status": "CLOSED",
                "evidence": (
                    "phase20_combination_weight_grid.csv|"
                    "phase20_combination_weight_bootstrap.csv|"
                    "phase20_combination_weight_summary.csv|"
                    "phase20_score_summary.csv|"
                    "phase20_june_paired_differences.csv"
                ),
            },
        ]
    )

    write_csv(
        OUT / "phase20_exact_common_support_event_panel.csv",
        panel,
    )
    write_csv(
        OUT / "phase20_combination_weight_grid.csv",
        weight_grid,
    )
    write_csv(
        OUT / "phase20_combination_weight_bootstrap.csv",
        weight_replicates,
    )

    selected_row = weight_grid.loc[
        weight_grid["gp_weight"] == selected_weight
    ].iloc[0]
    oracle_row = june_weight_grid.loc[
        june_weight_grid["gp_weight"]
        == oracle_june_weight
    ].iloc[0]

    weight_summary = weight_bootstrap_summary.copy()
    weight_summary[
        "selected_gp_weight"
    ] = selected_weight
    weight_summary[
        "selected_market_weight"
    ] = 1.0 - selected_weight
    weight_summary[
        "selected_development_categorical_log"
    ] = float(selected_row["categorical_log"])
    weight_summary[
        "june_oracle_gp_weight_post_hoc"
    ] = oracle_june_weight
    weight_summary[
        "june_oracle_categorical_log_post_hoc"
    ] = float(oracle_row["categorical_log"])
    weight_summary[
        "primary_selection_metric"
    ] = PRIMARY_SELECTION_METRIC
    weight_summary[
        "weight_grid_increment"
    ] = 0.001
    write_csv(
        OUT / "phase20_combination_weight_summary.csv",
        weight_summary,
    )

    write_csv(
        OUT / "phase20_rule_specific_weight_diagnostics.csv",
        rule_weights,
    )
    write_csv(
        OUT / "phase20_score_summary.csv",
        score_summary,
    )
    write_csv(
        OUT / "phase20_date_score_panel.csv",
        date_score_panel,
    )
    write_csv(
        OUT / "phase20_june_paired_differences.csv",
        june_paired,
    )
    write_csv(
        OUT / "phase20_event_discrepancy_panel.csv",
        event_discrepancy,
    )
    write_csv(
        OUT / "phase20_book_discrepancy_panel.csv",
        book_discrepancy,
    )
    write_csv(
        OUT / "phase20_book_discrepancy_summary.csv",
        book_summary,
    )
    write_csv(
        OUT / "phase20_rank_discrepancy_summary.csv",
        rank_summary,
    )
    write_csv(
        OUT / "phase20_discrepancy_regression_coefficients.csv",
        discrepancy_coefficients,
    )
    write_csv(
        OUT / "phase20_discrepancy_regression_summary.csv",
        discrepancy_regression_summary,
    )
    write_csv(
        OUT / "phase20_gap_updates.csv",
        gap_updates,
    )

    june_scores = score_summary.loc[
        score_summary["sample_period"] == "june_out_of_sample"
    ].copy()
    june_scores = june_scores.loc[
        june_scores["model"].isin(
            [
                "gp",
                "market_normalised",
                "equal_50_50_pool",
                "development_selected_pool",
                "june_oracle_pool_post_hoc",
            ]
        )
    ]

    selected_paired = june_paired.loc[
        june_paired["first_model"]
        == "development_selected_pool"
    ].copy()

    discrepancy_headlines = (
        book_summary.loc[
            (
                book_summary["scope"]
                == "sample_period"
            )
            & (
                book_summary["metric"].isin(
                    [
                        "total_variation_distance",
                        "expected_rank_shift_market_minus_gp",
                        "mode_disagreement",
                        "realised_probability_difference_gp_minus_market",
                    ]
                )
            )
        ]
        .sort_values(
            ["metric", "scope_value"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    spec = {
        "phase": 20,
        "name": (
            "Forecast combination and systematic GP-market "
            "discrepancy analysis"
        ),
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "git_branch": git("branch", "--show-current"),
        "git_commit_before_phase20": git("rev-parse", "HEAD"),
        "inputs": {
            rel(path): {
                "sha256": sha256(path),
                "rows": (
                    int(len(pd.read_csv(path)))
                    if path.suffix.lower() == ".csv"
                    else None
                ),
            }
            for path in REQUIRED_PATHS
        },
        "column_map": columns,
        "support": {
            "event_rows": int(len(panel)),
            "dates": int(panel["target_date"].nunique()),
            "books": int(panel["book_key"].nunique()),
            "development_dates": int(
                development["target_date"].nunique()
            ),
            "june_dates": int(june["target_date"].nunique()),
            "decision_rules": int(
                panel["decision_rule"].nunique()
            ),
            "complete_books_only": True,
        },
        "combination_design": {
            "pool": (
                "q_j(w) = w p_GP,j + (1-w) p_market,j"
            ),
            "market_probability": (
                "normalised complete-book Polymarket distribution"
            ),
            "weight_grid": {
                "minimum": 0.0,
                "maximum": 1.0,
                "increment": 0.001,
            },
            "primary_selection_metric": (
                "development-period date-balanced categorical log score"
            ),
            "selected_gp_weight": selected_weight,
            "selected_market_weight": 1.0 - selected_weight,
            "selection_period": (
                "weather-plus-market development dates only"
            ),
            "june_used_for_selection": False,
            "weight_bootstrap": {
                "replications": WEIGHT_BOOTSTRAP_REPLICATIONS,
                "unit": "target_date",
                "seed": BOOTSTRAP_SEED,
            },
            "june_oracle_weight": {
                "gp_weight": oracle_june_weight,
                "status": "post-hoc diagnostic only",
            },
        },
        "score_design": {
            "probability_floor": PROBABILITY_FLOOR,
            "book_scores": [
                "binary_brier",
                "binary_log",
                "categorical_log",
                "multiclass_brier",
            ],
            "aggregation": (
                "book score averaged within target date, "
                "then target dates equally weighted"
            ),
            "june_paired_bootstrap_replications": (
                DATE_BOOTSTRAP_REPLICATIONS
            ),
            "june_paired_bootstrap_unit": "target_date",
        },
        "discrepancy_design": {
            "book_metrics": [
                "total_variation_distance",
                "jensen_shannon_divergence",
                "maximum_absolute_probability_gap",
                "expected_rank_shift_market_minus_gp",
                "modal_rank_shift_market_minus_gp",
                "mode_disagreement",
                "upper and lower mass shift relative to GP mode",
                "realised-event probability difference",
            ],
            "event_metrics": [
                "GP probability minus market probability",
                "centred log-ratio of market probability to GP probability",
            ],
            "contract_order_source": (
                "event order where available; otherwise canonical "
                "interval bounds or parsed event label"
            ),
            "regression_covariance": "target-date cluster robust",
            "causal_interpretation": False,
        },
        "headline_outputs": {
            "weight_summary": weight_summary.to_dict(
                orient="records"
            ),
            "june_scores": june_scores.to_dict(
                orient="records"
            ),
            "june_paired_differences": selected_paired.to_dict(
                orient="records"
            ),
            "discrepancy_headlines": discrepancy_headlines.to_dict(
                orient="records"
            ),
            "discrepancy_regressions": (
                discrepancy_regression_summary.to_dict(
                    orient="records"
                )
            ),
        },
        "figures": [rel(path) for path in figure_paths],
        "closed_gaps": ["G13", "G14"],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "status": "PASSED",
    }
    write_json(
        CONFIG / "phase20_forecast_combination_spec.json",
        spec,
    )

    score_table = june_scores[
        [
            "model",
            "binary_brier",
            "binary_log",
            "categorical_log",
            "multiclass_brier",
        ]
    ].copy()

    paired_table = selected_paired[
        [
            "second_model",
            "metric",
            "mean_difference",
            "bootstrap_lower_95",
            "bootstrap_upper_95",
        ]
    ].copy()

    discrepancy_table = discrepancy_headlines[
        [
            "scope_value",
            "metric",
            "mean",
            "bootstrap_lower_95",
            "bootstrap_upper_95",
        ]
    ].copy()

    report_lines = [
        "# Phase 20 Forecast Combination and GP-Market Discrepancy",
        "",
        "## Status",
        "",
        "PASSED",
        "",
        "## Purpose",
        "",
        "Phase 10 deliberately compared the weather-only GP and Polymarket as separate information sources. It did not estimate a model-market combination because no development-only weight-selection protocol had yet been defined. Phase 20 closes that gap by defining a coherent convex probability pool, selecting its single weight only on the March-May weather-plus-market development period, and evaluating the fixed pool on June.",
        "",
        "The phase also studies the structure of GP-market disagreement rather than treating the proper-score difference as a single number.",
        "",
        "## Certified support",
        "",
        f"- Exact-common-support dates: {panel['target_date'].nunique()}.",
        f"- Complete date-rule books: {panel['book_key'].nunique()}.",
        f"- Contract-event rows: {len(panel)}.",
        f"- Development dates used for weight selection: {development['target_date'].nunique()}.",
        f"- June out-of-sample dates: {june['target_date'].nunique()}.",
        "- No missing GP forecast, market price or contract event was imputed.",
        "- The GP models remain fixed; market prices never enter GP fitting.",
        "",
        "## Forecast-combination definition",
        "",
        "For contract event j in a complete date-rule book, the pooled probability is",
        "",
        "`q_j(w) = w p_GP,j + (1-w) p_market,j`,",
        "",
        "where both input vectors are coherent complete-book probability distributions and `w` lies in `[0,1]`. Convex pooling therefore preserves non-negativity and unit total probability mass.",
        "",
        "The primary weight minimises development-period categorical log score on a 0.001 grid. Book scores are first averaged within target date and target dates then receive equal weight. June outcomes are excluded from weight selection.",
        "",
        "## Selected combination weight",
        "",
        f"- Selected GP weight: {selected_weight:.3f}.",
        f"- Selected market weight: {1.0-selected_weight:.3f}.",
        f"- Bootstrap median GP weight: {float(weight_summary['median_gp_weight'].iloc[0]):.3f}.",
        f"- Bootstrap 95% GP-weight interval: [{float(weight_summary['lower_95_gp_weight'].iloc[0]):.3f}, {float(weight_summary['upper_95_gp_weight'].iloc[0]):.3f}].",
        f"- Post-hoc June oracle GP weight: {oracle_june_weight:.3f}. This value is diagnostic and was not used for the primary evaluation.",
        "",
        "Rule-specific development optima are reported as diagnostics only. They are not combined into the primary June forecast because that would introduce four tuned weights into a relatively short development sample.",
        "",
        "## June out-of-sample scores",
        "",
    ]
    report_lines.extend(
        markdown_table(
            score_table,
            [
                "model",
                "binary_brier",
                "binary_log",
                "categorical_log",
                "multiclass_brier",
            ],
            [
                "Model",
                "Binary Brier",
                "Binary log",
                "Categorical log",
                "Multiclass Brier",
            ],
            decimals=6,
        )
    )
    report_lines.extend(
        [
            "",
            "These Phase 20 binary scores use the normalised market book distribution for all models so that the convex pool remains coherent. They are therefore not replacements for Phase 10's raw-price binary market scores.",
            "",
            "## June paired differences for the development-selected pool",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            paired_table,
            [
                "second_model",
                "metric",
                "mean_difference",
                "bootstrap_lower_95",
                "bootstrap_upper_95",
            ],
            [
                "Comparator",
                "Metric",
                "Pool minus comparator",
                "95% lower",
                "95% upper",
            ],
            decimals=6,
        )
    )
    report_lines.extend(
        [
            "",
            "Every difference is the development-selected pool score minus the comparator score. Negative values favour the pool. Intervals resample complete June target dates 10,000 times.",
            "",
            "## Systematic GP-market discrepancy",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            discrepancy_table,
            [
                "scope_value",
                "metric",
                "mean",
                "bootstrap_lower_95",
                "bootstrap_upper_95",
            ],
            [
                "Period",
                "Metric",
                "Mean",
                "95% lower",
                "95% upper",
            ],
            decimals=6,
        )
    )
    report_lines.extend(
        [
            "",
            "Total-variation distance measures the fraction of probability mass that must be moved to transform one complete-book distribution into the other. Expected-rank shift is positive when Polymarket places relatively more probability on higher-temperature contracts than the GP. Mode disagreement records whether the two sources select different modal contracts. Realised-event probability difference is GP probability minus market probability on the eventual winning event.",
            "",
            "Event-level summaries align every contract by signed rank relative to the GP modal contract. The centred log-ratio statistic measures relative market-versus-GP reallocation within the simplex and removes a common book-level normalisation term.",
            "",
            "## Discrepancy regression",
            "",
            "Two descriptive auxiliary regressions use expected-rank shift and total-variation distance as responses. Covariates comprise a June indicator, calendar time, decision-rule indicators and an available temperature-level measure. Covariance estimates cluster observations by target date. These regressions test whether disagreement varies systematically with observable book characteristics; they do not establish a causal market-information channel.",
            "",
            "## Interpretation",
            "",
            "The combination exercise answers whether the GP and market contain complementary out-of-sample information under a deliberately low-dimensional rule. A pooled forecast is supported only when its fixed June score improves on both inputs with economically and statistically meaningful paired differences. A development-period optimum alone is not evidence of complementarity.",
            "",
            "The discrepancy analysis explains how the two distributions differ. In particular, signed rank and upper-mass shifts reveal whether the market systematically moves probability towards warmer or cooler contracts relative to the weather-only GP. This is directly relevant because the deterministic forecast exhibited a persistent local underforecasting bias before post-processing.",
            "",
            "## Closed Phase 14 gaps",
            "",
            "- G13: systematic GP-market discrepancy structure.",
            "- G14: forecast combination.",
            "",
            "## Evidential boundary",
            "",
            "Phase 20 does not refit the GP, use June outcomes for weight selection, impute missing forecasts or market prices, or claim that Polymarket discrepancies causally identify private information. The primary pool has one globally selected weight. Rule-specific weights and the June oracle weight are explicitly post-hoc diagnostics. All comparisons use the exact complete-book intersection and date-level resampling.",
            "",
        ]
    )

    (OUT / "phase20_forecast_combination_report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("PHASE20_STATUS=PASSED")
    print(f"PHASE20_EVENT_ROWS={len(panel)}")
    print(
        f"PHASE20_DATES={panel['target_date'].nunique()}"
    )
    print(
        f"PHASE20_BOOKS={panel['book_key'].nunique()}"
    )
    print(
        f"PHASE20_SELECTED_GP_WEIGHT={selected_weight:.3f}"
    )
    print(
        f"PHASE20_JUNE_ORACLE_GP_WEIGHT={oracle_june_weight:.3f}"
    )
    print(
        f"PHASE20_JUNE_PAIRED_ROWS={len(june_paired)}"
    )


if __name__ == "__main__":
    main()
