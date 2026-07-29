from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import scipy
from scipy.stats import norm
import sklearn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/v2_completion"
DATA_OUT = ROOT / "data/processed/v2_completion"
CONFIG = ROOT / "config/v2_completion"

VALIDATION_PATH = ROOT / "outputs/v2/diagnostics/07_gp_validation_predictions.csv"
RESIDUAL_PATH = ROOT / "outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv"
PHASE8_MARKET_PATH = (
    ROOT
    / "data/processed/v2/phase8_clean_gp/phase8_gp_market_period_predictions.csv"
)
PHASE9_EVENT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/phase9_gp_event_probabilities/"
    / "phase9_gp_contract_event_probability_panel.csv"
)
PHASE10_COMMON_PATH = (
    ROOT
    / "outputs/v2/diagnostics/phase10_gp_market_comparison/"
    / "phase10_exact_common_support_event_panel.csv"
)
PHASE15_SPEC = ROOT / "config/v2_completion/phase15_gp_implementation_spec.json"
PHASE15_CRPS = ROOT / "outputs/v2_completion/phase15_crps_reconciliation.csv"

REQUIRED_PATHS = [
    VALIDATION_PATH,
    RESIDUAL_PATH,
    PHASE8_MARKET_PATH,
    PHASE9_EVENT_PATH,
    PHASE10_COMMON_PATH,
    PHASE15_SPEC,
    PHASE15_CRPS,
]

BOOTSTRAP_REPLICATIONS = 10_000
BOOTSTRAP_SEED = 20260729
EPSILON = 1e-12
EXPECTED_LEGACY_GP_SCORES = {
    "rbf": 0.877561,
    "matern32": 0.863340,
}
EXPECTED_PHASE9_SCORES = {
    "mean_binary_brier": 0.06664735,
    "mean_binary_log": 0.21621827,
    "mean_categorical_log": 1.53611577,
    "mean_multiclass_brier": 0.73312081,
}
EXPECTED_PHASE10_JUNE_DIFFERENCES = {
    "mean_binary_brier": 0.009324,
    "mean_binary_log": 0.038628,
    "mean_categorical_log": 0.357342,
    "mean_multiclass_brier": 0.101710,
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


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
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
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
        if contains_all and not all(token.lower() in lowered for token in contains_all):
            continue
        if contains_any and not any(token.lower() in lowered for token in contains_any):
            continue
        score = (
            10 * sum(token.lower() in lowered for token in contains_all)
            + 2 * sum(token.lower() in lowered for token in contains_any)
        )
        candidates.append((-score, len(column), column))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def normalise_rule(value: Any) -> str:
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
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
    }
    return aliases.get(text, text)


def normalise_model(value: Any) -> str:
    text = str(value).strip().lower().replace("-", "").replace("_", "")
    if "matern" in text or "matérn" in text:
        return "matern32"
    if "rbf" in text or "radial" in text or "squaredexponential" in text:
        return "rbf"
    if "static" in text:
        return "static_gaussian"
    if "raw" in text or "point" in text:
        return "raw_point"
    return str(value).strip().lower()


def parse_binary(series: pd.Series) -> pd.Series | None:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(int)
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all() and set(numeric.astype(float).unique()).issubset({0.0, 1.0}):
        return numeric.astype(int)

    mapping = {
        "true": 1,
        "false": 0,
        "yes": 1,
        "no": 0,
        "y": 1,
        "n": 0,
        "won": 1,
        "lost": 0,
        "winner": 1,
        "loser": 0,
        "1": 1,
        "0": 0,
    }
    mapped = series.astype(str).str.strip().str.lower().map(mapping)
    if mapped.notna().all():
        return mapped.astype(int)
    return None


def discover_outcome_column(
    frame: pd.DataFrame,
    date_col: str,
    rule_col: str,
) -> tuple[str, pd.Series]:
    preferred = [
        "realised_outcome",
        "realized_outcome",
        "realised_yes",
        "realized_yes",
        "is_winner",
        "winner",
        "outcome",
        "event_outcome",
        "y",
    ]
    ordered: list[str] = []
    lower = {column.lower(): column for column in frame.columns}
    for name in preferred:
        if name in lower:
            ordered.append(lower[name])
    for column in frame.columns:
        lowered = column.lower()
        if column in ordered:
            continue
        if (
            any(token in lowered for token in ("realised", "realized", "winner", "outcome"))
            and not any(token in lowered for token in ("prob", "price", "label", "text"))
        ):
            ordered.append(column)

    for column in ordered:
        parsed = parse_binary(frame[column])
        if parsed is None:
            continue
        sums = (
            pd.DataFrame(
                {
                    "date": pd.to_datetime(frame[date_col]).dt.normalize(),
                    "rule": frame[rule_col].map(normalise_rule),
                    "outcome": parsed,
                }
            )
            .groupby(["date", "rule"], sort=False)["outcome"]
            .sum()
        )
        if len(sums) and (sums == 1).all():
            return column, parsed
    fail(
        "Could not identify a binary event-outcome column with exactly one realised "
        f"event per date-rule book. Available columns: {list(frame.columns)}"
    )


def discover_probability_column(
    frame: pd.DataFrame,
    model: str,
    normalised: bool | None = None,
) -> str:
    columns = list(frame.columns)
    if model == "gp":
        exact = [
            "p_gp",
            "gp_event_probability",
            "gp_probability",
            "event_probability",
            "probability_gp",
        ]
        contains_all = ["gp"]
        contains_any = ["probability", "prob"]
        exclude = ["market", "price", "gap", "difference"]
    elif model == "market":
        if normalised is True:
            exact = [
                "p_market_normalised",
                "p_market_normalized",
                "normalised_market_probability",
                "normalized_market_probability",
                "market_probability_normalised",
                "market_probability_normalized",
            ]
            contains_all = ["market"]
            contains_any = ["normalised", "normalized"]
            exclude = ["gp", "gap", "difference"]
        else:
            exact = [
                "p_market_raw",
                "market_probability_raw",
                "raw_market_probability",
                "market_yes_price_raw",
                "raw_market_yes_price",
                "polymarket_yes_price_raw",
                "raw_polymarket_yes_price",
                "market_price_raw",
                "raw_market_price",
                "polymarket_price_raw",
                "raw_polymarket_price",
                "p_market",
                "market_yes_price",
                "polymarket_yes_price",
                "market_probability",
                "polymarket_probability",
                "market_price",
                "polymarket_price",
                "price",
            ]
            contains_all = []
            contains_any = [
                "p_market",
                "market_probability",
                "polymarket_probability",
                "market_price",
                "polymarket_price",
                "yes_price",
            ]
            exclude = [
                "normalised",
                "normalized",
                "gp",
                "gap",
                "difference",
                "volume",
                "brier",
                "log",
                "loss",
                "score",
                "component",
                "calibration",
                "error",
                "outcome",
                "realised",
                "realized",
                "winner",
            ]
    else:
        fail(f"Unsupported probability model label: {model}")

    column = find_column(
        columns,
        exact=exact,
        contains_all=contains_all,
        contains_any=contains_any,
        exclude=exclude,
    )
    if column is None:
        fail(
            f"Could not identify the {model} probability column "
            f"(normalised={normalised}). Available columns: {columns}"
        )
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any():
        fail(f"Probability column {column} contains non-numeric or missing values.")
    if ((values < -1e-12) | (values > 1 + 1e-12)).any():
        fail(f"Probability column {column} contains values outside [0,1].")
    return column


def discover_validation_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns = list(frame.columns)
    mapping = {
        "date": find_column(columns, exact=["target_date", "event_date", "date"]),
        "rule": find_column(columns, exact=["decision_rule", "rule"]),
        "fold_id": find_column(
            columns,
            exact=["fold_id", "validation_block", "block_id", "block", "fold"],
        ),
        "fold_number": find_column(columns, exact=["fold_number"]),
        "training_start": find_column(columns, exact=["training_start"]),
        "training_end": find_column(columns, exact=["training_end"]),
        "validation_start": find_column(columns, exact=["validation_start"]),
        "validation_end": find_column(columns, exact=["validation_end"]),
        "forecast": find_column(
            columns,
            exact=["forecast_daily_max_c"],
            contains_all=["forecast", "max"],
        ),
        "outcome": find_column(
            columns,
            exact=["hko_daily_max_c", "hko_max_c"],
            contains_all=["hko", "max"],
        ),
        "residual": find_column(
            columns,
            exact=["residual_observed_c"],
            contains_all=["residual", "observed"],
        ),
        "model": find_column(
            columns,
            exact=["kernel", "kernel_family", "model", "model_name"],
        ),
        "mean": find_column(
            columns,
            exact=["temperature_predictive_mean_c", "predictive_temperature_mean_c"],
            contains_all=["temperature", "mean"],
            exclude=["error"],
        ),
        "std": find_column(
            columns,
            exact=[
                "predictive_standard_deviation_c",
                "temperature_predictive_standard_deviation_c",
                "predictive_std_c",
            ],
            contains_any=["standard_deviation", "predictive_std"],
            exclude=["residual", "standardised", "standardized"],
        ),
        "legacy_crps": find_column(
            columns,
            exact=["crps_c", "continuous_crps_c"],
            contains_all=["crps"],
        ),
    }
    required = [
        "date",
        "rule",
        "fold_id",
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
        "forecast",
        "outcome",
        "residual",
        "model",
        "mean",
        "std",
        "legacy_crps",
    ]
    missing = [key for key in required if not mapping[key]]
    if missing:
        fail(
            f"Could not identify required validation columns {missing}. "
            f"Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items() if value is not None}


def discover_residual_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns = list(frame.columns)
    mapping = {
        "date": find_column(columns, exact=["target_date", "event_date", "date"]),
        "rule": find_column(columns, exact=["decision_rule", "rule"]),
        "residual": find_column(
            columns,
            exact=[
                "residual_c",
                "weather_residual_c",
                "hko_minus_forecast_c",
                "residual_observed_c",
            ],
            contains_all=["residual"],
            exclude=["standardised", "standardized", "predictive", "absolute", "squared"],
        ),
        "forecast": find_column(
            columns,
            exact=["forecast_daily_max_c"],
            contains_all=["forecast", "max"],
        ),
        "outcome": find_column(
            columns,
            exact=["hko_daily_max_c", "hko_max_c"],
            contains_all=["hko", "max"],
        ),
    }
    missing = [key for key in ("date", "rule", "residual") if not mapping[key]]
    if missing:
        fail(
            f"Could not identify required residual-panel columns {missing}. "
            f"Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items() if value is not None}


def discover_market_prediction_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns = list(frame.columns)
    mapping = {
        "date": find_column(columns, exact=["target_date", "event_date", "date"]),
        "rule": find_column(columns, exact=["decision_rule", "rule"]),
        "forecast": find_column(
            columns,
            exact=["forecast_daily_max_c"],
            contains_all=["forecast", "max"],
        ),
    }
    missing = [key for key in mapping if not mapping[key]]
    if missing:
        fail(
            f"Could not identify Phase 8 market-prediction columns {missing}. "
            f"Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items() if value is not None}


def discover_event_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns = list(frame.columns)
    mapping = {
        "date": find_column(columns, exact=["target_date", "event_date", "date"]),
        "rule": find_column(columns, exact=["decision_rule", "rule"]),
        "lower": find_column(
            columns,
            exact=[
                "lower_bound_c",
                "event_lower_bound_c",
                "canonical_lower_bound_c",
            ],
            contains_all=["lower", "bound"],
        ),
        "upper": find_column(
            columns,
            exact=[
                "upper_bound_c",
                "event_upper_bound_c",
                "canonical_upper_bound_c",
            ],
            contains_all=["upper", "bound"],
        ),
        "label": find_column(
            columns,
            exact=[
                "normalised_event_label",
                "normalized_event_label",
                "canonical_event_label",
                "event_label",
                "contract_event_label",
            ],
            contains_any=["event_label", "contract_label"],
        ),
    }
    missing = [key for key in ("date", "rule", "lower", "upper") if not mapping[key]]
    if missing:
        fail(
            f"Could not identify event-panel columns {missing}. "
            f"Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items() if value is not None}


def parse_bound(value: Any) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return math.nan
    text = str(value).strip().lower().replace("°c", "").replace("c", "")
    if text in {"-inf", "-infinity", "negative infinity", "-∞"}:
        return -math.inf
    if text in {"inf", "+inf", "infinity", "+infinity", "∞", "+∞"}:
        return math.inf
    try:
        return float(text)
    except ValueError:
        return math.nan


def complete_bounds(
    frame: pd.DataFrame,
    date_col: str,
    rule_col: str,
    lower_col: str,
    upper_col: str,
) -> tuple[pd.Series, pd.Series]:
    lower = frame[lower_col].map(parse_bound).astype(float)
    upper = frame[upper_col].map(parse_bound).astype(float)
    keys = pd.DataFrame(
        {
            "date": pd.to_datetime(frame[date_col]).dt.normalize(),
            "rule": frame[rule_col].map(normalise_rule),
        },
        index=frame.index,
    )
    for _, indices in keys.groupby(["date", "rule"], sort=False).groups.items():
        index = list(indices)
        group_lower = lower.loc[index]
        group_upper = upper.loc[index]

        missing_lower = group_lower[group_lower.isna()].index.tolist()
        missing_upper = group_upper[group_upper.isna()].index.tolist()

        if len(missing_lower) == 1:
            candidate = missing_lower[0]
            finite_uppers = group_upper.replace([np.inf, -np.inf], np.nan)
            if (
                pd.notna(group_upper.loc[candidate])
                and group_upper.loc[candidate] == finite_uppers.min()
            ):
                lower.loc[candidate] = -math.inf

        if len(missing_upper) == 1:
            candidate = missing_upper[0]
            finite_lowers = group_lower.replace([np.inf, -np.inf], np.nan)
            if (
                pd.notna(group_lower.loc[candidate])
                and group_lower.loc[candidate] == finite_lowers.max()
            ):
                upper.loc[candidate] = math.inf

    if lower.isna().any() or upper.isna().any():
        diagnostics = frame.loc[lower.isna() | upper.isna(), [date_col, rule_col, lower_col, upper_col]]
        diagnostic_path = OUT / "phase16_unresolved_event_bounds.csv"
        write_csv(diagnostic_path, diagnostics)
        fail(
            "Event bounds could not be completed. "
            f"Diagnostic written to {rel(diagnostic_path)}."
        )
    if (lower >= upper).any():
        fail("At least one event interval has lower bound greater than or equal to upper bound.")
    return lower, upper


def gaussian_crps(
    mean: np.ndarray | pd.Series,
    standard_deviation: np.ndarray | pd.Series,
    outcome: np.ndarray | pd.Series,
) -> np.ndarray:
    mu = np.asarray(mean, dtype=float)
    sigma = np.asarray(standard_deviation, dtype=float)
    y = np.asarray(outcome, dtype=float)
    if np.any(~np.isfinite(mu)) or np.any(~np.isfinite(y)):
        fail("CRPS inputs contain non-finite means or outcomes.")
    if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
        fail("CRPS standard deviations must be finite and positive.")
    z = (y - mu) / sigma
    return sigma * (
        z * (2.0 * norm.cdf(z) - 1.0)
        + 2.0 * norm.pdf(z)
        - 1.0 / math.sqrt(math.pi)
    )


def model_date_losses(predictions: pd.DataFrame) -> pd.DataFrame:
    result = (
        predictions.groupby(["model", "target_date"], as_index=False)
        .agg(
            date_crps_c=("crps_c", "mean"),
            date_rules=("decision_rule", "nunique"),
        )
    )
    if not (result["date_rules"] == 4).all():
        fail("At least one model-date does not contain all four decision rules.")
    return result


def score_summary(
    predictions: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    return (
        predictions.groupby(group_columns, as_index=False)
        .agg(
            observations=("crps_c", "size"),
            dates=("target_date", "nunique"),
            decision_rules=("decision_rule", "nunique"),
            mean_crps_c=("crps_c", "mean"),
            median_crps_c=("crps_c", "median"),
            mean_absolute_temperature_error_c=("absolute_temperature_error_c", "mean"),
        )
        .sort_values(group_columns, kind="stable")
        .reset_index(drop=True)
    )


def bootstrap_mean_interval(
    values: np.ndarray,
    replications: int = BOOTSTRAP_REPLICATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float, float]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) < 2 or np.any(~np.isfinite(array)):
        fail("Bootstrap input must be a finite one-dimensional array with at least two dates.")
    rng = np.random.default_rng(seed)
    n = len(array)
    estimates = np.empty(replications, dtype=float)
    batch_size = 1000
    completed = 0
    while completed < replications:
        batch = min(batch_size, replications - completed)
        indices = rng.integers(0, n, size=(batch, n))
        estimates[completed : completed + batch] = array[indices].mean(axis=1)
        completed += batch
    return (
        float(array.mean()),
        float(np.quantile(estimates, 0.025)),
        float(np.quantile(estimates, 0.975)),
        float(np.mean(estimates < 0.0)),
    )


def paired_model_differences(predictions: pd.DataFrame) -> pd.DataFrame:
    comparisons = [
        ("static_gaussian", "raw_point", "static_minus_raw"),
        ("rbf", "static_gaussian", "rbf_minus_static"),
        ("matern32", "static_gaussian", "matern32_minus_static"),
        ("matern32", "rbf", "matern32_minus_rbf"),
    ]
    rows: list[dict[str, Any]] = []

    scopes: list[tuple[str, str, pd.DataFrame]] = [("overall", "all", predictions)]
    for rule, group in predictions.groupby("decision_rule", sort=True):
        scopes.append(("decision_rule", str(rule), group))

    for scope, scope_value, frame in scopes:
        pivot = (
            frame.groupby(["target_date", "model"], as_index=False)["crps_c"]
            .mean()
            .pivot(index="target_date", columns="model", values="crps_c")
            .sort_index()
        )
        for first, second, label in comparisons:
            if first not in pivot.columns or second not in pivot.columns:
                fail(f"Missing {first} or {second} in paired model comparison.")
            paired = pivot[[first, second]].dropna()
            difference = (paired[first] - paired[second]).to_numpy(dtype=float)
            point, lower, upper, probability_lower = bootstrap_mean_interval(
                difference,
                seed=BOOTSTRAP_SEED
                + sum(ord(character) for character in f"{scope}:{scope_value}:{label}"),
            )
            rows.append(
                {
                    "scope": scope,
                    "scope_value": scope_value,
                    "comparison": label,
                    "first_model": first,
                    "second_model": second,
                    "difference_definition": "first model CRPS minus second model CRPS",
                    "dates": len(difference),
                    "mean_difference_c": point,
                    "bootstrap_lower_95_c": lower,
                    "bootstrap_upper_95_c": upper,
                    "bootstrap_probability_first_lower_crps": probability_lower,
                    "bootstrap_replications": BOOTSTRAP_REPLICATIONS,
                    "bootstrap_unit": "target_date",
                    "seed": BOOTSTRAP_SEED
                    + sum(ord(character) for character in f"{scope}:{scope_value}:{label}"),
                }
            )
    return pd.DataFrame(rows)


def event_book_scores(
    frame: pd.DataFrame,
    date_col: str,
    rule_col: str,
    outcome: pd.Series,
    binary_probability: pd.Series,
    categorical_probability: pd.Series,
) -> pd.DataFrame:
    working = pd.DataFrame(
        {
            "target_date": pd.to_datetime(frame[date_col]).dt.normalize(),
            "decision_rule": frame[rule_col].map(normalise_rule),
            "outcome": outcome.astype(int).to_numpy(),
            "binary_probability": np.asarray(binary_probability, dtype=float),
            "categorical_probability": np.asarray(categorical_probability, dtype=float),
        },
        index=frame.index,
    )
    working["binary_probability"] = working["binary_probability"].clip(EPSILON, 1.0 - EPSILON)
    working["categorical_probability"] = working["categorical_probability"].clip(EPSILON, 1.0)
    working["binary_brier_component"] = (
        working["binary_probability"] - working["outcome"]
    ) ** 2
    working["binary_log_component"] = -(
        working["outcome"] * np.log(working["binary_probability"])
        + (1 - working["outcome"]) * np.log(1 - working["binary_probability"])
    )
    working["categorical_log_component"] = -working["outcome"] * np.log(
        working["categorical_probability"]
    )
    working["multiclass_brier_component"] = (
        working["categorical_probability"] - working["outcome"]
    ) ** 2

    books = (
        working.groupby(["target_date", "decision_rule"], as_index=False)
        .agg(
            event_rows=("outcome", "size"),
            realised_events=("outcome", "sum"),
            binary_brier=("binary_brier_component", "mean"),
            binary_log=("binary_log_component", "mean"),
            categorical_log=("categorical_log_component", "sum"),
            multiclass_brier=("multiclass_brier_component", "sum"),
            categorical_probability_mass=("categorical_probability", "sum"),
        )
    )
    if not (books["event_rows"] == 11).all():
        fail("At least one event book does not contain 11 canonical events.")
    if not (books["realised_events"] == 1).all():
        fail("At least one event book does not contain exactly one realised event.")
    return books


def aggregate_event_scores(
    books: pd.DataFrame,
    model: str,
    support_scope: str,
) -> pd.DataFrame:
    periods = {
        "overall": books,
        "development": books.loc[books["target_date"].dt.month <= 5],
        "june": books.loc[books["target_date"].dt.month == 6],
    }
    rows: list[dict[str, Any]] = []
    for period, frame in periods.items():
        if frame.empty:
            continue
        date_scores = (
            frame.groupby("target_date", as_index=False)
            .agg(
                mean_binary_brier=("binary_brier", "mean"),
                mean_binary_log=("binary_log", "mean"),
                mean_categorical_log=("categorical_log", "mean"),
                mean_multiclass_brier=("multiclass_brier", "mean"),
                books=("decision_rule", "size"),
            )
        )
        rows.append(
            {
                "support_scope": support_scope,
                "period": period,
                "model": model,
                "aggregation": "equal target-date weight after averaging date-rule books within date",
                "dates": int(date_scores["target_date"].nunique()),
                "books": int(len(frame)),
                "event_rows": int(frame["event_rows"].sum()),
                "mean_binary_brier": float(date_scores["mean_binary_brier"].mean()),
                "mean_binary_log": float(date_scores["mean_binary_log"].mean()),
                "mean_categorical_log": float(date_scores["mean_categorical_log"].mean()),
                "mean_multiclass_brier": float(date_scores["mean_multiclass_brier"].mean()),
            }
        )
    return pd.DataFrame(rows)


def build_chronological_predictions(
    validation: pd.DataFrame,
    residuals: pd.DataFrame,
    validation_columns: dict[str, str],
    residual_columns: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    val = validation.copy()
    val["target_date"] = pd.to_datetime(val[validation_columns["date"]], errors="raise").dt.normalize()
    val["decision_rule"] = val[validation_columns["rule"]].map(normalise_rule)
    val["model"] = val[validation_columns["model"]].map(normalise_model)
    for column in (
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
    ):
        val[column] = pd.to_datetime(
            val[validation_columns[column]], errors="raise"
        ).dt.normalize()

    residual = residuals.copy()
    residual["target_date"] = pd.to_datetime(
        residual[residual_columns["date"]], errors="raise"
    ).dt.normalize()
    residual["decision_rule"] = residual[residual_columns["rule"]].map(normalise_rule)
    residual["residual_c"] = pd.to_numeric(
        residual[residual_columns["residual"]], errors="raise"
    )

    validation_base_columns = [
        "target_date",
        "decision_rule",
        validation_columns["fold_id"],
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
        validation_columns["forecast"],
        validation_columns["outcome"],
        validation_columns["residual"],
    ]
    if validation_columns.get("fold_number"):
        validation_base_columns.insert(3, validation_columns["fold_number"])

    duplicated = val.duplicated(["target_date", "decision_rule", "model"])
    if duplicated.any():
        fail("Validation panel contains duplicate date-rule-model rows.")

    base = (
        val.sort_values(["target_date", "decision_rule", "model"], kind="stable")
        .drop_duplicates(["target_date", "decision_rule"], keep="first")
        .copy()
    )
    if len(base) != 1460:
        fail(f"Expected 1,460 unique validation date-rule rows; found {len(base)}.")

    static_parameter_rows: list[dict[str, Any]] = []
    static_parameters: dict[tuple[Any, str], tuple[float, float, int]] = {}

    fold_column = validation_columns["fold_id"]
    for (fold, rule), group in base.groupby([fold_column, "decision_rule"], sort=True):
        training_start = group["training_start"].iloc[0]
        training_end = group["training_end"].iloc[0]
        validation_start = group["validation_start"].iloc[0]
        validation_end = group["validation_end"].iloc[0]
        if not (
            (group["training_start"] == training_start).all()
            and (group["training_end"] == training_end).all()
            and (group["validation_start"] == validation_start).all()
            and (group["validation_end"] == validation_end).all()
        ):
            fail(f"Fold {fold}, rule {rule}: inconsistent chronological boundaries.")
        if not training_end < validation_start:
            fail(f"Fold {fold}, rule {rule}: training period overlaps validation.")

        training = residual.loc[
            (residual["decision_rule"] == rule)
            & (residual["target_date"] >= training_start)
            & (residual["target_date"] <= training_end)
        ].copy()
        if training["target_date"].nunique() != len(training):
            fail(f"Fold {fold}, rule {rule}: duplicate training dates.")
        if len(training) < 2:
            fail(f"Fold {fold}, rule {rule}: insufficient static training rows.")

        mean = float(training["residual_c"].mean())
        standard_deviation = float(training["residual_c"].std(ddof=1))
        if not math.isfinite(standard_deviation) or standard_deviation <= 0:
            fail(f"Fold {fold}, rule {rule}: invalid static residual standard deviation.")

        static_parameters[(fold, rule)] = (mean, standard_deviation, len(training))
        static_parameter_rows.append(
            {
                "fit_scope": "chronological_fold",
                "fold_id": fold,
                "decision_rule": rule,
                "training_start": training_start,
                "training_end": training_end,
                "validation_start": validation_start,
                "validation_end": validation_end,
                "training_dates": len(training),
                "residual_mean_c": mean,
                "residual_standard_deviation_c": standard_deviation,
                "variance_denominator": "n-1",
                "market_data_used": False,
                "june_data_used": False,
            }
        )

    prediction_rows: list[pd.DataFrame] = []
    forecast = pd.to_numeric(base[validation_columns["forecast"]], errors="raise")
    outcome = pd.to_numeric(base[validation_columns["outcome"]], errors="raise")
    observed_residual = pd.to_numeric(base[validation_columns["residual"]], errors="raise")

    raw = pd.DataFrame(
        {
            "target_date": base["target_date"],
            "fold_id": base[fold_column],
            "fold_number": (
                base[validation_columns["fold_number"]]
                if validation_columns.get("fold_number")
                else base[fold_column]
            ),
            "decision_rule": base["decision_rule"],
            "training_start": base["training_start"],
            "training_end": base["training_end"],
            "validation_start": base["validation_start"],
            "validation_end": base["validation_end"],
            "forecast_daily_max_c": forecast,
            "hko_daily_max_c": outcome,
            "residual_observed_c": observed_residual,
            "model": "raw_point",
            "temperature_predictive_mean_c": forecast,
            "predictive_standard_deviation_c": np.nan,
            "crps_c": np.abs(outcome - forecast),
            "legacy_crps_c": np.nan,
            "score_implementation": "point-mass CRPS equals absolute error",
        }
    )
    raw["temperature_error_c"] = raw["temperature_predictive_mean_c"] - raw["hko_daily_max_c"]
    raw["absolute_temperature_error_c"] = raw["temperature_error_c"].abs()
    prediction_rows.append(raw)

    static = raw.copy()
    static["model"] = "static_gaussian"
    static_means: list[float] = []
    static_stds: list[float] = []
    static_training_counts: list[int] = []
    for fold, rule in zip(static["fold_id"], static["decision_rule"]):
        mean, standard_deviation, count = static_parameters[(fold, rule)]
        static_means.append(mean)
        static_stds.append(standard_deviation)
        static_training_counts.append(count)
    static["static_residual_mean_c"] = static_means
    static["static_residual_standard_deviation_c"] = static_stds
    static["static_training_dates"] = static_training_counts
    static["temperature_predictive_mean_c"] = (
        static["forecast_daily_max_c"] + static["static_residual_mean_c"]
    )
    static["predictive_standard_deviation_c"] = static[
        "static_residual_standard_deviation_c"
    ]
    static["crps_c"] = gaussian_crps(
        static["temperature_predictive_mean_c"],
        static["predictive_standard_deviation_c"],
        static["hko_daily_max_c"],
    )
    static["legacy_crps_c"] = np.nan
    static["score_implementation"] = "closed-form Gaussian CRPS"
    static["temperature_error_c"] = (
        static["temperature_predictive_mean_c"] - static["hko_daily_max_c"]
    )
    static["absolute_temperature_error_c"] = static["temperature_error_c"].abs()
    prediction_rows.append(static)

    for model in ("rbf", "matern32"):
        source = val.loc[val["model"] == model].copy()
        if len(source) != 1460:
            fail(f"Expected 1,460 {model} validation rows; found {len(source)}.")
        gp = pd.DataFrame(
            {
                "target_date": source["target_date"],
                "fold_id": source[fold_column],
                "fold_number": (
                    source[validation_columns["fold_number"]]
                    if validation_columns.get("fold_number")
                    else source[fold_column]
                ),
                "decision_rule": source["decision_rule"],
                "training_start": source["training_start"],
                "training_end": source["training_end"],
                "validation_start": source["validation_start"],
                "validation_end": source["validation_end"],
                "forecast_daily_max_c": pd.to_numeric(
                    source[validation_columns["forecast"]], errors="raise"
                ),
                "hko_daily_max_c": pd.to_numeric(
                    source[validation_columns["outcome"]], errors="raise"
                ),
                "residual_observed_c": pd.to_numeric(
                    source[validation_columns["residual"]], errors="raise"
                ),
                "model": model,
                "temperature_predictive_mean_c": pd.to_numeric(
                    source[validation_columns["mean"]], errors="raise"
                ),
                "predictive_standard_deviation_c": pd.to_numeric(
                    source[validation_columns["std"]], errors="raise"
                ),
                "legacy_crps_c": pd.to_numeric(
                    source[validation_columns["legacy_crps"]], errors="raise"
                ),
                "score_implementation": "closed-form Gaussian CRPS",
            }
        )
        gp["crps_c"] = gaussian_crps(
            gp["temperature_predictive_mean_c"],
            gp["predictive_standard_deviation_c"],
            gp["hko_daily_max_c"],
        )
        gp["temperature_error_c"] = (
            gp["temperature_predictive_mean_c"] - gp["hko_daily_max_c"]
        )
        gp["absolute_temperature_error_c"] = gp["temperature_error_c"].abs()
        prediction_rows.append(gp)

        legacy_date_mean = (
            gp.groupby("target_date", as_index=False)["legacy_crps_c"]
            .mean()["legacy_crps_c"]
            .mean()
        )
        if not math.isclose(
            float(legacy_date_mean),
            EXPECTED_LEGACY_GP_SCORES[model],
            rel_tol=0.0,
            abs_tol=5e-6,
        ):
            fail(
                f"Legacy {model} headline CRPS changed: "
                f"expected {EXPECTED_LEGACY_GP_SCORES[model]}, "
                f"observed {legacy_date_mean}."
            )

    predictions = pd.concat(prediction_rows, ignore_index=True, sort=False)
    predictions = predictions.sort_values(
        ["target_date", "decision_rule", "model"], kind="stable"
    ).reset_index(drop=True)

    if len(predictions) != 5840:
        fail(f"Expected 5,840 chronological model rows; found {len(predictions)}.")
    if predictions["target_date"].nunique() != 365:
        fail("Chronological prediction panel does not contain 365 validation dates.")
    if predictions["decision_rule"].nunique() != 4:
        fail("Chronological prediction panel does not contain four decision rules.")
    if set(predictions["model"]) != {
        "raw_point",
        "static_gaussian",
        "rbf",
        "matern32",
    }:
        fail("Chronological prediction panel does not contain the four required models.")

    raw_check = predictions.loc[predictions["model"] == "raw_point"]
    if not np.allclose(
        raw_check["crps_c"],
        np.abs(raw_check["forecast_daily_max_c"] - raw_check["hko_daily_max_c"]),
        atol=1e-12,
        rtol=0.0,
    ):
        fail("Raw point forecast CRPS does not equal absolute forecast error.")

    return predictions, pd.DataFrame(static_parameter_rows)


def full_history_static_parameters(
    residuals: pd.DataFrame,
    residual_columns: dict[str, str],
) -> pd.DataFrame:
    frame = residuals.copy()
    frame["target_date"] = pd.to_datetime(
        frame[residual_columns["date"]], errors="raise"
    ).dt.normalize()
    frame["decision_rule"] = frame[residual_columns["rule"]].map(normalise_rule)
    frame["residual_c"] = pd.to_numeric(
        frame[residual_columns["residual"]], errors="raise"
    )

    rows: list[dict[str, Any]] = []
    for rule, group in frame.groupby("decision_rule", sort=True):
        if group["target_date"].nunique() != 730 or len(group) != 730:
            fail(
                f"Full-history static fit for {rule} does not contain 730 unique dates."
            )
        rows.append(
            {
                "fit_scope": "full_weather_history",
                "fold_id": "full",
                "decision_rule": rule,
                "training_start": group["target_date"].min(),
                "training_end": group["target_date"].max(),
                "validation_start": pd.NaT,
                "validation_end": pd.NaT,
                "training_dates": len(group),
                "residual_mean_c": float(group["residual_c"].mean()),
                "residual_standard_deviation_c": float(
                    group["residual_c"].std(ddof=1)
                ),
                "variance_denominator": "n-1",
                "market_data_used": False,
                "june_data_used": False,
            }
        )
    result = pd.DataFrame(rows)
    if len(result) != 4:
        fail(f"Expected four full-history static parameter rows; found {len(result)}.")
    return result


def build_static_event_panel(
    market_predictions: pd.DataFrame,
    phase9_events: pd.DataFrame,
    full_parameters: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str], pd.Series]:
    market_columns = discover_market_prediction_columns(market_predictions)
    event_columns = discover_event_columns(phase9_events)

    market = market_predictions.copy()
    market["target_date"] = pd.to_datetime(
        market[market_columns["date"]], errors="raise"
    ).dt.normalize()
    market["decision_rule"] = market[market_columns["rule"]].map(normalise_rule)
    market["forecast_daily_max_c"] = pd.to_numeric(
        market[market_columns["forecast"]], errors="raise"
    )
    market = market.drop_duplicates(["target_date", "decision_rule"], keep="first")
    if len(market) != 375 or market["target_date"].nunique() != 102:
        fail(
            "Phase 8 market prediction support changed: expected 375 books over 102 dates."
        )

    parameters = full_parameters[
        [
            "decision_rule",
            "residual_mean_c",
            "residual_standard_deviation_c",
        ]
    ].copy()
    market = market.merge(parameters, on="decision_rule", how="left", validate="many_to_one")
    if market[["residual_mean_c", "residual_standard_deviation_c"]].isna().any().any():
        fail("Full-history static parameters did not merge to all market predictions.")
    market["static_temperature_mean_c"] = (
        market["forecast_daily_max_c"] + market["residual_mean_c"]
    )
    market["static_temperature_standard_deviation_c"] = market[
        "residual_standard_deviation_c"
    ]

    events = phase9_events.copy()
    events["target_date"] = pd.to_datetime(
        events[event_columns["date"]], errors="raise"
    ).dt.normalize()
    events["decision_rule"] = events[event_columns["rule"]].map(normalise_rule)
    outcome_column, outcome = discover_outcome_column(
        events, event_columns["date"], event_columns["rule"]
    )
    events["realised_event"] = outcome.to_numpy(dtype=int)

    lower, upper = complete_bounds(
        events,
        event_columns["date"],
        event_columns["rule"],
        event_columns["lower"],
        event_columns["upper"],
    )
    events["event_lower_bound_c"] = lower
    events["event_upper_bound_c"] = upper

    # Phase 9 already carries some forecast metadata.  Remove any columns that
    # would collide with the canonical Phase 8/static values before merging;
    # otherwise pandas creates `_x`/`_y` names and downstream evidence fields
    # become ambiguous.
    canonical_static_columns = [
        "forecast_daily_max_c",
        "residual_mean_c",
        "residual_standard_deviation_c",
        "static_temperature_mean_c",
        "static_temperature_standard_deviation_c",
    ]
    overlapping_static_columns = [
        column for column in canonical_static_columns if column in events.columns
    ]
    if overlapping_static_columns:
        events = events.drop(columns=overlapping_static_columns)

    events = events.merge(
        market[
            [
                "target_date",
                "decision_rule",
                *canonical_static_columns,
            ]
        ],
        on=["target_date", "decision_rule"],
        how="inner",
        validate="many_to_one",
    )
    if len(events) != 4125:
        fail(f"Expected 4,125 static event rows; found {len(events)}.")

    missing_static_columns = [
        column for column in canonical_static_columns if column not in events.columns
    ]
    if missing_static_columns:
        fail(
            "Canonical static-prediction columns are missing after the Phase 8 "
            f"merge: {missing_static_columns}. Available columns: {list(events.columns)}"
        )

    duplicate_suffix_columns = [
        column
        for column in events.columns
        if column.endswith("_x") or column.endswith("_y")
    ]
    if duplicate_suffix_columns:
        fail(
            "Unexpected merge-suffix columns remain in the static event panel: "
            f"{duplicate_suffix_columns}"
        )

    print(
        "PHASE16_STATIC_EVENT_MERGE="
        + json.dumps(
            {
                "dropped_overlapping_columns": overlapping_static_columns,
                "canonical_columns": canonical_static_columns,
                "rows": int(len(events)),
                "books": int(
                    events[["target_date", "decision_rule"]]
                    .drop_duplicates()
                    .shape[0]
                ),
            },
            sort_keys=True,
        )
    )

    mean = events["static_temperature_mean_c"].to_numpy(dtype=float)
    standard_deviation = events[
        "static_temperature_standard_deviation_c"
    ].to_numpy(dtype=float)
    lower_array = events["event_lower_bound_c"].to_numpy(dtype=float)
    upper_array = events["event_upper_bound_c"].to_numpy(dtype=float)

    lower_cdf = np.where(
        np.isneginf(lower_array),
        0.0,
        norm.cdf((lower_array - mean) / standard_deviation),
    )
    upper_cdf = np.where(
        np.isposinf(upper_array),
        1.0,
        norm.cdf((upper_array - mean) / standard_deviation),
    )
    events["static_event_probability"] = np.clip(
        upper_cdf - lower_cdf, 0.0, 1.0
    )

    mass = (
        events.groupby(["target_date", "decision_rule"], as_index=False)
        .agg(
            probability_mass=("static_event_probability", "sum"),
            event_rows=("static_event_probability", "size"),
            realised_events=("realised_event", "sum"),
        )
    )
    if not (mass["event_rows"] == 11).all():
        fail("Static event panel contains an incomplete event book.")
    if not (mass["realised_events"] == 1).all():
        fail("Static event panel contains a book without exactly one realised event.")
    if float((mass["probability_mass"] - 1.0).abs().max()) > 1e-10:
        fail("Static event probabilities do not sum to one.")

    return events, event_columns, events["realised_event"]


def compute_event_score_outputs(
    static_events: pd.DataFrame,
    phase9_events: pd.DataFrame,
    phase10_common: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    score_frames: list[pd.DataFrame] = []

    static_books = event_book_scores(
        static_events,
        "target_date",
        "decision_rule",
        static_events["realised_event"],
        static_events["static_event_probability"],
        static_events["static_event_probability"],
    )
    score_frames.append(
        aggregate_event_scores(
            static_books, "static_gaussian", "forecast_supported"
        )
    )

    phase9_columns = discover_event_columns(phase9_events)
    phase9_outcome_column, phase9_outcome = discover_outcome_column(
        phase9_events, phase9_columns["date"], phase9_columns["rule"]
    )
    phase9_gp_probability = discover_probability_column(phase9_events, "gp")
    phase9_gp_books = event_book_scores(
        phase9_events,
        phase9_columns["date"],
        phase9_columns["rule"],
        phase9_outcome,
        pd.to_numeric(phase9_events[phase9_gp_probability], errors="raise"),
        pd.to_numeric(phase9_events[phase9_gp_probability], errors="raise"),
    )
    score_frames.append(
        aggregate_event_scores(phase9_gp_books, "matern32_gp", "forecast_supported")
    )

    # The certified Phase 9 headline used equal date-rule-book weighting.
    # Because support is incomplete on some dates, this is not numerically
    # identical to the new completion programme's equal target-date weighting.
    # Preserve both conventions explicitly rather than silently replacing one.
    phase9_legacy = pd.DataFrame(
        [
            {
                "support_scope": "phase9_legacy_forecast_supported",
                "period": "overall",
                "model": "matern32_gp",
                "aggregation": "equal date-rule-book weight, matching certified Phase 9",
                "dates": int(phase9_gp_books["target_date"].nunique()),
                "books": int(len(phase9_gp_books)),
                "event_rows": int(phase9_gp_books["event_rows"].sum()),
                "mean_binary_brier": float(phase9_gp_books["binary_brier"].mean()),
                "mean_binary_log": float(phase9_gp_books["binary_log"].mean()),
                "mean_categorical_log": float(
                    phase9_gp_books["categorical_log"].mean()
                ),
                "mean_multiclass_brier": float(
                    phase9_gp_books["multiclass_brier"].mean()
                ),
            }
        ]
    )
    score_frames.append(phase9_legacy)

    phase9_overall = phase9_legacy.iloc[0]
    for metric, expected in EXPECTED_PHASE9_SCORES.items():
        observed = float(phase9_overall[metric])
        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=5e-8):
            fail(
                f"Phase 9 legacy book-weighted score reconciliation failed for "
                f"{metric}: expected {expected}, observed {observed}."
            )

    common_columns = discover_event_columns(phase10_common)
    common_outcome_column, common_outcome = discover_outcome_column(
        phase10_common, common_columns["date"], common_columns["rule"]
    )
    common_gp_probability = discover_probability_column(phase10_common, "gp")
    common_market_raw = discover_probability_column(
        phase10_common, "market", normalised=False
    )
    print(
        "PHASE16_EXACT_SUPPORT_PROBABILITY_COLUMNS="
        + json.dumps(
            {
                "gp_probability": common_gp_probability,
                "market_raw_probability": common_market_raw,
            },
            sort_keys=True,
        )
    )

    common_working = phase10_common.copy()
    common_working["_target_date"] = pd.to_datetime(
        common_working[common_columns["date"]], errors="raise"
    ).dt.normalize()
    common_working["_decision_rule"] = common_working[
        common_columns["rule"]
    ].map(normalise_rule)
    common_working["_market_raw"] = pd.to_numeric(
        common_working[common_market_raw], errors="raise"
    )
    raw_mass = common_working.groupby(
        ["_target_date", "_decision_rule"], sort=False
    )["_market_raw"].transform("sum")
    if (raw_mass <= 0).any():
        fail("At least one exact-support market book has non-positive price mass.")
    common_working["_market_normalised"] = common_working["_market_raw"] / raw_mass

    gp_books = event_book_scores(
        common_working,
        "_target_date",
        "_decision_rule",
        common_outcome,
        pd.to_numeric(common_working[common_gp_probability], errors="raise"),
        pd.to_numeric(common_working[common_gp_probability], errors="raise"),
    )
    market_books = event_book_scores(
        common_working,
        "_target_date",
        "_decision_rule",
        common_outcome,
        common_working["_market_raw"],
        common_working["_market_normalised"],
    )

    exact_keys = gp_books[["target_date", "decision_rule"]].drop_duplicates()
    if (
        len(exact_keys) != 350
        or exact_keys["target_date"].nunique() != 97
    ):
        fail("Exact common support changed: expected 350 books over 97 dates.")

    static_exact_rows = static_events.merge(
        exact_keys,
        on=["target_date", "decision_rule"],
        how="inner",
        validate="many_to_one",
    )
    if len(static_exact_rows) != 3850:
        fail(f"Expected 3,850 exact-support static event rows; found {len(static_exact_rows)}.")
    static_exact_books = event_book_scores(
        static_exact_rows,
        "target_date",
        "decision_rule",
        static_exact_rows["realised_event"],
        static_exact_rows["static_event_probability"],
        static_exact_rows["static_event_probability"],
    )

    score_frames.extend(
        [
            aggregate_event_scores(
                static_exact_books, "static_gaussian", "exact_common_support"
            ),
            aggregate_event_scores(
                gp_books, "matern32_gp", "exact_common_support"
            ),
            aggregate_event_scores(
                market_books, "polymarket", "exact_common_support"
            ),
        ]
    )

    summary = pd.concat(score_frames, ignore_index=True)
    summary = summary.sort_values(
        ["support_scope", "period", "model"], kind="stable"
    ).reset_index(drop=True)

    june = summary.loc[
        (summary["support_scope"] == "exact_common_support")
        & (summary["period"] == "june")
    ].set_index("model")
    for metric, expected in EXPECTED_PHASE10_JUNE_DIFFERENCES.items():
        observed = float(june.loc["matern32_gp", metric] - june.loc["polymarket", metric])
        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=5e-6):
            fail(
                f"Phase 10 June score-difference reconciliation failed for {metric}: "
                f"expected {expected}, observed {observed}."
            )

    static_exact_panel = static_exact_rows[
        [
            "target_date",
            "decision_rule",
            "event_lower_bound_c",
            "event_upper_bound_c",
            "realised_event",
            "forecast_daily_max_c",
            "residual_mean_c",
            "residual_standard_deviation_c",
            "static_temperature_mean_c",
            "static_temperature_standard_deviation_c",
            "static_event_probability",
        ]
    ].copy()

    return summary, static_exact_panel


def main() -> None:
    for path in REQUIRED_PATHS:
        if not path.exists():
            fail(f"Required Phase 16 input is missing: {rel(path)}")

    validation = pd.read_csv(VALIDATION_PATH)
    residuals = pd.read_csv(RESIDUAL_PATH)
    market_predictions = pd.read_csv(PHASE8_MARKET_PATH)
    phase9_events = pd.read_csv(PHASE9_EVENT_PATH)
    phase10_common = pd.read_csv(PHASE10_COMMON_PATH)
    phase15_spec = json.loads(PHASE15_SPEC.read_text(encoding="utf-8"))

    if phase15_spec.get("status") != "PASSED":
        fail("Phase 15 implementation specification is not certified as PASSED.")

    validation_columns = discover_validation_columns(validation)
    residual_columns = discover_residual_columns(residuals)

    print(
        "PHASE16_VALIDATION_COLUMN_MAP="
        + json.dumps(validation_columns, sort_keys=True)
    )
    print(
        "PHASE16_RESIDUAL_COLUMN_MAP="
        + json.dumps(residual_columns, sort_keys=True)
    )

    predictions, chronological_parameters = build_chronological_predictions(
        validation,
        residuals,
        validation_columns,
        residual_columns,
    )
    full_parameters = full_history_static_parameters(residuals, residual_columns)
    parameter_registry = pd.concat(
        [chronological_parameters, full_parameters],
        ignore_index=True,
        sort=False,
    )

    overall_scores = score_summary(predictions, ["model"])
    date_losses = model_date_losses(predictions)
    overall_date_balanced = (
        date_losses.groupby("model", as_index=False)
        .agg(
            dates=("target_date", "nunique"),
            mean_date_crps_c=("date_crps_c", "mean"),
            median_date_crps_c=("date_crps_c", "median"),
        )
    )
    overall_scores = overall_scores.merge(
        overall_date_balanced, on="model", how="left", validate="one_to_one"
    )

    legacy_gp_scores = (
        predictions.loc[predictions["model"].isin(["rbf", "matern32"])]
        .groupby(["model", "target_date"], as_index=False)["legacy_crps_c"]
        .mean()
        .groupby("model", as_index=False)
        .agg(legacy_mean_date_crps_c=("legacy_crps_c", "mean"))
    )
    overall_scores = overall_scores.merge(
        legacy_gp_scores, on="model", how="left", validate="one_to_one"
    )
    overall_scores["analytical_minus_legacy_crps_c"] = (
        overall_scores["mean_date_crps_c"]
        - overall_scores["legacy_mean_date_crps_c"]
    )

    scores_by_rule = score_summary(predictions, ["model", "decision_rule"])
    scores_by_block = score_summary(
        predictions, ["model", "fold_id", "fold_number"]
    )
    paired = paired_model_differences(predictions)

    static_events, _, _ = build_static_event_panel(
        market_predictions,
        phase9_events,
        full_parameters,
    )
    event_scores, static_exact_panel = compute_event_score_outputs(
        static_events,
        phase9_events,
        phase10_common,
    )

    gap_updates = pd.DataFrame(
        [
            {
                "gap_id": "G01",
                "gap": "Static Gaussian chronological benchmark",
                "phase_closed": 16,
                "status": "CLOSED",
                "evidence": (
                    "phase16_chronological_raw_static_predictions.csv|"
                    "phase16_model_scores_overall.csv|"
                    "phase16_paired_model_differences.csv"
                ),
            },
            {
                "gap_id": "G02",
                "gap": "Raw point forecast chronological benchmark",
                "phase_closed": 16,
                "status": "CLOSED",
                "evidence": (
                    "phase16_chronological_raw_static_predictions.csv|"
                    "phase16_model_scores_overall.csv"
                ),
            },
        ]
    )

    spec = {
        "phase": 16,
        "name": "Raw and static Gaussian chronological benchmarks",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_branch": git("branch", "--show-current"),
        "git_commit_before_phase16": git("rev-parse", "HEAD"),
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
        "chronological_design": {
            "models": [
                "raw_point",
                "static_gaussian",
                "rbf",
                "matern32",
            ],
            "validation_dates": int(predictions["target_date"].nunique()),
            "decision_rules": int(predictions["decision_rule"].nunique()),
            "prediction_rows": int(len(predictions)),
            "static_mean": "sample mean of rule-specific residuals in the applicable expanding training history",
            "static_standard_deviation": "sample standard deviation with denominator n-1",
            "raw_crps": "absolute error",
            "gaussian_crps": (
                "sigma * [z*(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi)]"
            ),
            "aggregation": (
                "average across rules within each target date, then average "
                "equally across target dates"
            ),
            "bootstrap": {
                "replications": BOOTSTRAP_REPLICATIONS,
                "unit": "target_date",
                "base_seed": BOOTSTRAP_SEED,
                "interval": "2.5th and 97.5th percentiles",
            },
        },
        "full_history_static_fit": {
            "training_dates_per_rule": 730,
            "market_data_used": False,
            "june_data_used": False,
            "forecast_supported_books": 375,
            "forecast_supported_event_rows": 4125,
            "exact_common_support_books": 350,
            "exact_common_support_event_rows": 3850,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "status": "PASSED",
    }

    write_csv(
        DATA_OUT / "phase16_chronological_raw_static_predictions.csv",
        predictions,
    )
    write_csv(
        DATA_OUT / "phase16_full_history_static_market_predictions.csv",
        static_events[
            [
                "target_date",
                "decision_rule",
                "event_lower_bound_c",
                "event_upper_bound_c",
                "realised_event",
                "forecast_daily_max_c",
                "residual_mean_c",
                "residual_standard_deviation_c",
                "static_temperature_mean_c",
                "static_temperature_standard_deviation_c",
                "static_event_probability",
            ]
        ].copy(),
    )
    write_csv(
        DATA_OUT / "phase16_exact_common_support_static_event_panel.csv",
        static_exact_panel,
    )
    write_csv(OUT / "phase16_static_parameter_registry.csv", parameter_registry)
    write_csv(OUT / "phase16_date_level_model_losses.csv", date_losses)
    write_csv(OUT / "phase16_model_scores_overall.csv", overall_scores)
    write_csv(OUT / "phase16_model_scores_by_rule.csv", scores_by_rule)
    write_csv(OUT / "phase16_model_scores_by_block.csv", scores_by_block)
    write_csv(OUT / "phase16_paired_model_differences.csv", paired)
    write_csv(OUT / "phase16_static_event_probability_scores.csv", event_scores)
    write_csv(OUT / "phase16_gap_updates.csv", gap_updates)
    write_json(CONFIG / "phase16_static_benchmark_spec.json", spec)

    score_lookup = overall_scores.set_index("model")
    static_minus_raw = paired.loc[
        (paired["scope"] == "overall")
        & (paired["comparison"] == "static_minus_raw")
    ].iloc[0]
    matern_minus_static = paired.loc[
        (paired["scope"] == "overall")
        & (paired["comparison"] == "matern32_minus_static")
    ].iloc[0]
    matern_minus_rbf = paired.loc[
        (paired["scope"] == "overall")
        & (paired["comparison"] == "matern32_minus_rbf")
    ].iloc[0]

    if float(static_minus_raw["mean_difference_c"]) < 0:
        static_interpretation = (
            "The static Gaussian correction improves on the raw deterministic point "
            "forecast under mean date CRPS."
        )
    else:
        static_interpretation = (
            "The static Gaussian correction does not improve on the raw deterministic "
            "point forecast under mean date CRPS."
        )

    if float(matern_minus_static["mean_difference_c"]) < 0:
        gp_interpretation = (
            "The Matérn-3/2 GP improves on the static Gaussian correction under mean "
            "date CRPS, so conditional residual structure adds descriptive predictive value."
        )
    else:
        gp_interpretation = (
            "The Matérn-3/2 GP does not improve on the static Gaussian correction under "
            "mean date CRPS; simple local location-and-scale correction explains at least "
            "as much of the predictive gain."
        )

    report_lines = [
        "# Phase 16 Raw and Static Gaussian Benchmarks",
        "",
        "## Status",
        "",
        "PASSED",
        "",
        "## Why the static benchmark was previously absent",
        "",
        "Phases 7 and 8 were originally constructed to compare RBF and Matérn-3/2 Gaussian-process covariance families. The static rule-specific Gaussian law was introduced later as the required attribution benchmark, but no same-support chronological output had yet been generated. Phase 16 now fits that benchmark on the identical expanding histories and validation observations rather than inferring or imputing a result.",
        "",
        "## Chronological comparison design",
        "",
        "- Validation dates: 365.",
        "- Decision rules: 4.",
        "- Model rows: 5,840.",
        "- Models: raw point forecast, static Gaussian, RBF GP and Matérn-3/2 GP.",
        "- Static moments are estimated separately by rule and fold from earlier weather-only residuals.",
        "- Raw point CRPS equals absolute temperature error.",
        "- All Gaussian models are evaluated with closed-form Gaussian CRPS.",
        "- Every aggregate score gives each target date one unit of weight.",
        "- Paired uncertainty intervals resample target dates 10,000 times.",
        "",
        "## Overall mean date CRPS",
        "",
        f"- Raw point forecast: {float(score_lookup.loc['raw_point', 'mean_date_crps_c']):.9f} degrees Celsius.",
        f"- Static Gaussian: {float(score_lookup.loc['static_gaussian', 'mean_date_crps_c']):.9f} degrees Celsius.",
        f"- RBF GP, analytical CRPS: {float(score_lookup.loc['rbf', 'mean_date_crps_c']):.9f} degrees Celsius.",
        f"- Matérn-3/2 GP, analytical CRPS: {float(score_lookup.loc['matern32', 'mean_date_crps_c']):.9f} degrees Celsius.",
        f"- RBF GP, frozen legacy Phase 7 CRPS: {float(score_lookup.loc['rbf', 'legacy_mean_date_crps_c']):.9f} degrees Celsius.",
        f"- Matérn-3/2 GP, frozen legacy Phase 7 CRPS: {float(score_lookup.loc['matern32', 'legacy_mean_date_crps_c']):.9f} degrees Celsius.",
        "",
        "## Main paired attribution results",
        "",
        (
            f"- Static minus raw: {float(static_minus_raw['mean_difference_c']):.9f} "
            f"with 95% date-bootstrap interval "
            f"[{float(static_minus_raw['bootstrap_lower_95_c']):.9f}, "
            f"{float(static_minus_raw['bootstrap_upper_95_c']):.9f}]."
        ),
        (
            f"- Matérn-3/2 minus static: "
            f"{float(matern_minus_static['mean_difference_c']):.9f} "
            f"with 95% date-bootstrap interval "
            f"[{float(matern_minus_static['bootstrap_lower_95_c']):.9f}, "
            f"{float(matern_minus_static['bootstrap_upper_95_c']):.9f}]."
        ),
        (
            f"- Matérn-3/2 minus RBF: "
            f"{float(matern_minus_rbf['mean_difference_c']):.9f} "
            f"with 95% date-bootstrap interval "
            f"[{float(matern_minus_rbf['bootstrap_lower_95_c']):.9f}, "
            f"{float(matern_minus_rbf['bootstrap_upper_95_c']):.9f}]."
        ),
        "- Every difference is first-model CRPS minus second-model CRPS; negative is better for the first model.",
        "",
        "## Interpretation",
        "",
        static_interpretation,
        "",
        gp_interpretation,
        "",
        "Rule-specific results are stored in `phase16_model_scores_by_rule.csv`; validation-block results are stored in `phase16_model_scores_by_block.csv`. Phase 18 will analyse their stability in depth rather than overinterpreting the aggregate score alone.",
        "",
        "## Event-score aggregation reconciliation",
        "",
        "- The certified Phase 9 headline scores used equal date-rule-book weighting.",
        "- Because some market-period dates lack one or more decision-rule forecasts, equal book weighting differs slightly from equal target-date weighting.",
        "- Phase 16 preserves the certified Phase 9 row under `phase9_legacy_forecast_supported` and separately reports the completion programme's date-balanced forecast-supported scores.",
        "- This difference is an aggregation convention, not a change to any probability or outcome.",
        "",
        "## Full-history static event probabilities",
        "",
        "- Four rule-specific static Gaussian laws were estimated from 730 weather-only dates each.",
        "- They were applied to 375 forecast-supported date-rule books over 102 dates.",
        "- The resulting 4,125 contract-event probabilities sum to one within every book.",
        "- A 350-book, 97-date exact-common-support static panel was also created for later market attribution.",
        "- No market price or June outcome was used to estimate the static model.",
        "",
        "## Closed Phase 14 gaps",
        "",
        "- G01: static Gaussian chronological benchmark.",
        "- G02: raw point forecast chronological benchmark.",
        "",
        "## Evidential boundary",
        "",
        "Phase 16 does not alter the certified Phase 7 or Phase 8 GP models. The raw and static comparators use the same chronological validation support as the two saved GP families. The full-history static market-period law uses only the 730-date weather history. Market prices are used only to identify the already certified exact-common-support subset for secondary score comparison.",
        "",
    ]
    (OUT / "phase16_static_benchmark_report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("PHASE16_STATUS=PASSED")
    print(f"PHASE16_CHRONOLOGICAL_ROWS={len(predictions)}")
    print(f"PHASE16_VALIDATION_DATES={predictions['target_date'].nunique()}")
    print(f"PHASE16_STATIC_PARAMETER_ROWS={len(parameter_registry)}")
    print(f"PHASE16_STATIC_EVENT_ROWS={len(static_events)}")
    print(f"PHASE16_EXACT_STATIC_EVENT_ROWS={len(static_exact_panel)}")
    print(
        "PHASE16_OVERALL_SCORES="
        + json.dumps(
            {
                model: float(row["mean_date_crps_c"])
                for model, row in overall_scores.set_index("model").iterrows()
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
