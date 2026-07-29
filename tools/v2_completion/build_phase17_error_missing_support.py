from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
from itertools import combinations
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
FIG = OUT / "phase17_figures"
CONFIG = ROOT / "config/v2_completion"

RESIDUAL_PATH = ROOT / "outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv"
PHASE16_PREDICTIONS = (
    ROOT
    / "data/processed/v2_completion/"
    / "phase16_chronological_raw_static_predictions.csv"
)
PHASE8_SUPPORT = (
    ROOT
    / "data/processed/v2/phase8_clean_gp/"
    / "phase8_gp_market_period_predictions.csv"
)
PHASE8_MISSING = (
    ROOT
    / "data/processed/v2/phase8_clean_gp/"
    / "phase8_missing_forecast_support.csv"
)
CONTRACT_UNIVERSE = (
    ROOT
    / "data/processed/18s_expanded_march_june_canonical_sample/"
    / "18s_expanded_certified_contract_outcome_panel.csv"
)
PHASE16_SPEC = ROOT / "config/v2_completion/phase16_static_benchmark_spec.json"
PHASE16_REPORT = ROOT / "outputs/v2_completion/phase16_static_benchmark_report.md"

REQUIRED_PATHS = [
    RESIDUAL_PATH,
    PHASE16_PREDICTIONS,
    PHASE8_SUPPORT,
    PHASE8_MISSING,
    CONTRACT_UNIVERSE,
    PHASE16_SPEC,
    PHASE16_REPORT,
]

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

BOOTSTRAP_REPLICATIONS = 10_000
BOOTSTRAP_SEED = 20260729


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
        if contains_all and not all(
            token.lower() in lowered for token in contains_all
        ):
            continue
        if contains_any and not any(
            token.lower() in lowered for token in contains_any
        ):
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
        "event_day": "event_day_open",
    }
    return aliases.get(text, text)


def discover_residual_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns = list(frame.columns)
    mapping = {
        "date": find_column(
            columns,
            exact=["target_date", "event_date", "date"],
        ),
        "rule": find_column(
            columns,
            exact=["decision_rule", "rule"],
        ),
        "residual": find_column(
            columns,
            exact=[
                "residual_c",
                "weather_residual_c",
                "hko_minus_forecast_c",
                "residual_observed_c",
            ],
            contains_all=["residual"],
            exclude=[
                "standardised",
                "standardized",
                "predictive",
                "absolute",
                "squared",
            ],
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
    missing = [
        key
        for key in ("date", "rule", "residual", "forecast", "outcome")
        if not mapping[key]
    ]
    if missing:
        fail(
            f"Could not identify residual columns {missing}. "
            f"Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items()}


def discover_phase16_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns = list(frame.columns)
    mapping = {
        "date": find_column(
            columns,
            exact=["target_date", "event_date", "date"],
        ),
        "rule": find_column(
            columns,
            exact=["decision_rule", "rule"],
        ),
        "model": find_column(
            columns,
            exact=["model", "model_name"],
        ),
        "fold": find_column(
            columns,
            exact=["fold_id", "fold_number", "validation_block"],
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
    missing = [key for key, value in mapping.items() if not value]
    if missing:
        fail(
            f"Could not identify Phase 16 columns {missing}. "
            f"Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items()}


def discover_key_columns(frame: pd.DataFrame) -> dict[str, str]:
    date_col = find_column(
        frame.columns,
        exact=["target_date", "event_date", "date"],
    )
    rule_col = find_column(
        frame.columns,
        exact=["decision_rule", "rule"],
    )
    if not date_col or not rule_col:
        fail(
            "Could not identify date-rule key columns. "
            f"Available columns: {list(frame.columns)}"
        )
    return {"date": date_col, "rule": rule_col}


def discover_contract_date_column(frame: pd.DataFrame) -> str:
    date_col = find_column(
        frame.columns,
        exact=["target_date", "event_date", "date", "settlement_date"],
        contains_any=["date"],
        exclude=["created", "updated", "start", "end", "decision"],
    )
    if not date_col:
        fail(
            "Could not identify the settlement-date column in the canonical "
            f"contract universe. Available columns: {list(frame.columns)}"
        )
    return date_col


def bootstrap_mean(
    values: np.ndarray,
    seed: int,
    replications: int = BOOTSTRAP_REPLICATIONS,
) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) < 2 or np.any(~np.isfinite(array)):
        fail(
            "Bootstrap input must be a finite one-dimensional array "
            "with at least two observations."
        )

    rng = np.random.default_rng(seed)
    estimates = np.empty(replications, dtype=float)
    completed = 0
    batch_size = 1000

    while completed < replications:
        batch = min(batch_size, replications - completed)
        indices = rng.integers(
            0,
            len(array),
            size=(batch, len(array)),
        )
        estimates[completed : completed + batch] = array[indices].mean(axis=1)
        completed += batch

    return (
        float(array.mean()),
        float(np.quantile(estimates, 0.025)),
        float(np.quantile(estimates, 0.975)),
    )


def rule_error_summary(residual: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for rule in RULE_ORDER:
        group = residual.loc[
            residual["decision_rule"] == rule
        ].sort_values("target_date")
        if len(group) != 730 or group["target_date"].nunique() != 730:
            fail(
                f"Rule {rule} does not contain 730 unique weather-only dates."
            )

        error = group["residual_c"].to_numpy(dtype=float)
        absolute_error = np.abs(error)
        squared_error = error**2

        bias_point, bias_lower, bias_upper = bootstrap_mean(
            error,
            seed=BOOTSTRAP_SEED + sum(ord(c) for c in rule) + 1,
        )
        mae_point, mae_lower, mae_upper = bootstrap_mean(
            absolute_error,
            seed=BOOTSTRAP_SEED + sum(ord(c) for c in rule) + 2,
        )

        rows.append(
            {
                "decision_rule": rule,
                "dates": int(len(group)),
                "forecast_mean_c": float(
                    group["forecast_daily_max_c"].mean()
                ),
                "hko_mean_c": float(group["hko_daily_max_c"].mean()),
                "mean_error_hko_minus_forecast_c": float(error.mean()),
                "mean_error_bootstrap_lower_95_c": bias_lower,
                "mean_error_bootstrap_upper_95_c": bias_upper,
                "median_error_c": float(np.median(error)),
                "error_standard_deviation_c": float(
                    np.std(error, ddof=1)
                ),
                "mae_c": float(absolute_error.mean()),
                "mae_bootstrap_lower_95_c": mae_lower,
                "mae_bootstrap_upper_95_c": mae_upper,
                "rmse_c": float(np.sqrt(squared_error.mean())),
                "q05_error_c": float(np.quantile(error, 0.05)),
                "q25_error_c": float(np.quantile(error, 0.25)),
                "q75_error_c": float(np.quantile(error, 0.75)),
                "q95_error_c": float(np.quantile(error, 0.95)),
                "underforecast_rate": float(np.mean(error > 0.0)),
                "overforecast_rate": float(np.mean(error < 0.0)),
                "within_0_5c_rate": float(np.mean(absolute_error <= 0.5)),
                "within_1c_rate": float(np.mean(absolute_error <= 1.0)),
                "skewness": float(stats.skew(error, bias=False)),
                "excess_kurtosis": float(
                    stats.kurtosis(error, fisher=True, bias=False)
                ),
                "bootstrap_replications": BOOTSTRAP_REPLICATIONS,
                "bootstrap_unit": "target_date",
            }
        )

    return pd.DataFrame(rows)


def validation_block_summary(
    phase16: pd.DataFrame,
    columns: dict[str, str],
) -> pd.DataFrame:
    raw = phase16.loc[
        phase16[columns["model"]].astype(str).str.lower() == "raw_point"
    ].copy()

    raw["target_date"] = pd.to_datetime(
        raw[columns["date"]],
        errors="raise",
    ).dt.normalize()
    raw["decision_rule"] = raw[columns["rule"]].map(normalise_rule)
    raw["fold_id"] = raw[columns["fold"]]
    raw["residual_c"] = (
        pd.to_numeric(raw[columns["outcome"]], errors="raise")
        - pd.to_numeric(raw[columns["forecast"]], errors="raise")
    )

    if len(raw) != 1460:
        fail(
            f"Expected 1,460 raw validation rows; found {len(raw)}."
        )
    if raw["target_date"].nunique() != 365:
        fail("Raw validation panel does not contain 365 dates.")

    rows: list[dict[str, Any]] = []
    for (fold, rule), group in raw.groupby(
        ["fold_id", "decision_rule"],
        sort=True,
    ):
        error = group["residual_c"].to_numpy(dtype=float)
        rows.append(
            {
                "fold_id": fold,
                "decision_rule": rule,
                "validation_dates": int(group["target_date"].nunique()),
                "validation_start": group["target_date"].min(),
                "validation_end": group["target_date"].max(),
                "mean_error_hko_minus_forecast_c": float(error.mean()),
                "median_error_c": float(np.median(error)),
                "error_standard_deviation_c": float(
                    np.std(error, ddof=1)
                ),
                "mae_c": float(np.mean(np.abs(error))),
                "rmse_c": float(np.sqrt(np.mean(error**2))),
                "underforecast_rate": float(np.mean(error > 0.0)),
            }
        )

    result = pd.DataFrame(rows)
    if len(result) != 16:
        fail(
            f"Expected 16 rule-fold deterministic-error rows; "
            f"found {len(result)}."
        )
    return result


def pairwise_rule_differences(
    residual: pd.DataFrame,
) -> pd.DataFrame:
    signed = residual.pivot(
        index="target_date",
        columns="decision_rule",
        values="residual_c",
    )[RULE_ORDER]
    absolute = signed.abs()

    if signed.shape != (730, 4) or signed.isna().any().any():
        fail(
            "The rule-comparison matrix is not a complete 730-by-4 panel."
        )

    rows: list[dict[str, Any]] = []

    for first, second in combinations(RULE_ORDER, 2):
        signed_difference = (
            signed[first] - signed[second]
        ).to_numpy(dtype=float)
        absolute_difference = (
            absolute[first] - absolute[second]
        ).to_numpy(dtype=float)

        signed_point, signed_lower, signed_upper = bootstrap_mean(
            signed_difference,
            seed=(
                BOOTSTRAP_SEED
                + sum(ord(c) for c in f"signed:{first}:{second}")
            ),
        )
        mae_point, mae_lower, mae_upper = bootstrap_mean(
            absolute_difference,
            seed=(
                BOOTSTRAP_SEED
                + sum(ord(c) for c in f"absolute:{first}:{second}")
            ),
        )

        rows.append(
            {
                "first_rule": first,
                "second_rule": second,
                "dates": 730,
                "signed_error_difference_definition": (
                    "first rule HKO-minus-forecast error minus "
                    "second rule HKO-minus-forecast error"
                ),
                "mean_signed_error_difference_c": signed_point,
                "signed_error_bootstrap_lower_95_c": signed_lower,
                "signed_error_bootstrap_upper_95_c": signed_upper,
                "absolute_error_difference_definition": (
                    "first rule absolute error minus "
                    "second rule absolute error"
                ),
                "mean_absolute_error_difference_c": mae_point,
                "absolute_error_bootstrap_lower_95_c": mae_lower,
                "absolute_error_bootstrap_upper_95_c": mae_upper,
                "bootstrap_replications": BOOTSTRAP_REPLICATIONS,
                "bootstrap_unit": "target_date",
            }
        )

    return pd.DataFrame(rows)


def residual_correlation_outputs(
    residual: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    matrix = residual.pivot(
        index="target_date",
        columns="decision_rule",
        values="residual_c",
    )[RULE_ORDER]

    pearson = matrix.corr(method="pearson")
    spearman = matrix.corr(method="spearman")

    def long_form(correlation: pd.DataFrame, method: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for first in RULE_ORDER:
            for second in RULE_ORDER:
                rows.append(
                    {
                        "method": method,
                        "first_rule": first,
                        "second_rule": second,
                        "correlation": float(
                            correlation.loc[first, second]
                        ),
                        "dates": 730,
                    }
                )
        return pd.DataFrame(rows)

    return (
        long_form(pearson, "pearson"),
        long_form(spearman, "spearman"),
    )


def variance_decomposition(
    residual: pd.DataFrame,
) -> pd.DataFrame:
    matrix = residual.pivot(
        index="target_date",
        columns="decision_rule",
        values="residual_c",
    )[RULE_ORDER].to_numpy(dtype=float)

    if matrix.shape != (730, 4) or np.any(~np.isfinite(matrix)):
        fail(
            "Variance decomposition requires a finite balanced 730-by-4 matrix."
        )

    n_dates, n_rules = matrix.shape
    grand_mean = float(matrix.mean())
    date_means = matrix.mean(axis=1)
    rule_means = matrix.mean(axis=0)

    total_ss = float(np.sum((matrix - grand_mean) ** 2))
    date_ss = float(
        n_rules * np.sum((date_means - grand_mean) ** 2)
    )
    rule_ss = float(
        n_dates * np.sum((rule_means - grand_mean) ** 2)
    )
    interaction_ss = float(total_ss - date_ss - rule_ss)

    if interaction_ss < -1e-8:
        fail(
            "The two-way deterministic-error variance decomposition "
            "produced a negative interaction sum of squares."
        )
    interaction_ss = max(interaction_ss, 0.0)

    components = [
        ("target_date", date_ss, n_dates - 1),
        ("decision_rule", rule_ss, n_rules - 1),
        (
            "date_by_rule_interaction",
            interaction_ss,
            (n_dates - 1) * (n_rules - 1),
        ),
        ("total", total_ss, n_dates * n_rules - 1),
    ]

    rows: list[dict[str, Any]] = []
    for component, sum_squares, degrees_freedom in components:
        rows.append(
            {
                "component": component,
                "sum_squares": sum_squares,
                "degrees_freedom": degrees_freedom,
                "mean_square": (
                    sum_squares / degrees_freedom
                    if degrees_freedom > 0
                    else math.nan
                ),
                "share_of_total_sum_squares": (
                    sum_squares / total_ss
                    if component != "total"
                    else 1.0
                ),
                "grand_mean_error_c": grand_mean,
                "dates": n_dates,
                "decision_rules": n_rules,
                "interpretation": (
                    "descriptive balanced two-way decomposition; "
                    "the interaction term also contains remaining variation "
                    "because there is one observation per date-rule cell"
                ),
            }
        )

    return pd.DataFrame(rows)


def rank_diagnostics(
    residual: pd.DataFrame,
) -> pd.DataFrame:
    matrix = residual.pivot(
        index="target_date",
        columns="decision_rule",
        values="residual_c",
    )[RULE_ORDER]

    rows: list[dict[str, Any]] = []
    for measure, values in (
        ("signed_error", matrix),
        ("absolute_error", matrix.abs()),
    ):
        result = stats.friedmanchisquare(
            *(values[rule].to_numpy(dtype=float) for rule in RULE_ORDER)
        )
        kendall_w = float(
            result.statistic / (len(values) * (len(RULE_ORDER) - 1))
        )
        rows.append(
            {
                "measure": measure,
                "dates": len(values),
                "decision_rules": len(RULE_ORDER),
                "friedman_chi_square": float(result.statistic),
                "degrees_freedom": len(RULE_ORDER) - 1,
                "p_value": float(result.pvalue),
                "kendall_w": kendall_w,
                "status": "DESCRIPTIVE_ONLY",
                "caveat": (
                    "The standard Friedman reference distribution treats "
                    "target dates as independent. Serial dependence is "
                    "examined later, so this diagnostic is not used as "
                    "stand-alone inferential evidence."
                ),
            }
        )

    return pd.DataFrame(rows)


def combine_reason_text(
    row: pd.Series,
    excluded_columns: set[str],
) -> str:
    pieces: list[str] = []

    for column, value in row.items():
        if column in excluded_columns:
            continue
        if pd.isna(value):
            continue

        text = str(value).strip()
        if not text or text.lower() in {
            "nan",
            "none",
            "null",
            "false",
            "0",
        }:
            continue

        pieces.append(f"{column}={text}")

    return " | ".join(pieces)[:4000]


def classify_reason(text: str) -> tuple[str, str]:
    lowered = text.lower()

    if not lowered.strip():
        return (
            "certified_forecast_absent_no_finer_reason_recorded",
            "The certified missing-support registry identifies the key "
            "but records no more specific machine-readable cause.",
        )

    pattern_groups = [
        (
            "no_admissible_run_before_decision_time",
            [
                "decision time",
                "decision_time",
                "cutoff",
                "lead time",
                "lead_time",
                "eligible",
                "admissible",
                "before decision",
                "freeze",
            ],
        ),
        (
            "retrieval_or_request_failure",
            [
                "http",
                "request",
                "retrieval",
                "retrieve",
                "download",
                "fetch",
                "timeout",
                "connection",
                "response code",
            ],
        ),
        (
            "incomplete_or_invalid_hourly_run",
            [
                "hourly",
                "incomplete",
                "coverage",
                "missing hour",
                "missing_hour",
                "invalid run",
                "integrity",
                "daily maximum unavailable",
            ],
        ),
        (
            "source_run_unavailable",
            [
                "no run",
                "no_run",
                "source unavailable",
                "archive unavailable",
                "no candidate",
                "no_candidate",
                "missing source",
                "run unavailable",
            ],
        ),
        (
            "certification_conflict_or_exclusion",
            [
                "duplicate",
                "conflict",
                "excluded",
                "not certified",
                "certification",
                "quarantine",
            ],
        ),
        (
            "missing_certified_forecast_value",
            [
                "missing forecast",
                "forecast missing",
                "no forecast",
                "nan forecast",
                "null forecast",
            ],
        ),
    ]

    for category, patterns in pattern_groups:
        if any(pattern in lowered for pattern in patterns):
            return (
                category,
                "Category assigned from the documented Phase 8 "
                "machine-readable reason text.",
            )

    return (
        "documented_missing_support_other",
        "The Phase 8 registry contains documentary text, but it does not "
        "match a narrower predefined technical category.",
    )


def build_missing_support_registry(
    support: pd.DataFrame,
    missing_source: pd.DataFrame,
    contract: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    support_columns = discover_key_columns(support)
    support_keys = pd.DataFrame(
        {
            "target_date": pd.to_datetime(
                support[support_columns["date"]],
                errors="raise",
            ).dt.normalize(),
            "decision_rule": support[
                support_columns["rule"]
            ].map(normalise_rule),
        }
    ).drop_duplicates()

    if len(support_keys) != 375:
        fail(
            f"Expected 375 certified supported date-rule keys; "
            f"found {len(support_keys)}."
        )
    if support_keys["target_date"].nunique() != 102:
        fail(
            "Expected 102 forecast-supported dates in Phase 8."
        )

    contract_date_col = discover_contract_date_column(contract)
    settlement_dates = (
        pd.to_datetime(
            contract[contract_date_col],
            errors="raise",
        )
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    if len(settlement_dates) != 103:
        fail(
            f"Expected 103 settlement and market dates; "
            f"found {len(settlement_dates)}."
        )

    universe = pd.MultiIndex.from_product(
        [settlement_dates, RULE_ORDER],
        names=["target_date", "decision_rule"],
    ).to_frame(index=False)

    merged = universe.merge(
        support_keys.assign(certified_forecast_supported=True),
        on=["target_date", "decision_rule"],
        how="left",
        validate="one_to_one",
    )
    merged["certified_forecast_supported"] = (
        merged["certified_forecast_supported"]
        .fillna(False)
        .astype(bool)
    )

    derived_missing = (
        merged.loc[~merged["certified_forecast_supported"]]
        [["target_date", "decision_rule"]]
        .sort_values(
            ["target_date", "decision_rule"],
            key=lambda series: (
                series.map({rule: index for index, rule in enumerate(RULE_ORDER)})
                if series.name == "decision_rule"
                else series
            ),
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if len(derived_missing) != 37:
        fail(
            f"Expected exactly 37 unsupported date-rule keys; "
            f"found {len(derived_missing)}."
        )
    if len(support_keys) + len(derived_missing) != 412:
        fail(
            "Supported and unsupported keys do not partition "
            "the 412-key theoretical universe."
        )

    missing_columns = discover_key_columns(missing_source)
    missing_document = missing_source.copy()
    missing_document["target_date"] = pd.to_datetime(
        missing_document[missing_columns["date"]],
        errors="raise",
    ).dt.normalize()
    missing_document["decision_rule"] = missing_document[
        missing_columns["rule"]
    ].map(normalise_rule)

    duplicate_registry_keys = missing_document.duplicated(
        ["target_date", "decision_rule"],
        keep=False,
    )
    if duplicate_registry_keys.any():
        duplicate_path = OUT / "phase17_duplicate_missing_registry_keys.csv"
        write_csv(
            duplicate_path,
            missing_document.loc[duplicate_registry_keys],
        )
        fail(
            "The Phase 8 missing-support registry contains duplicate keys. "
            f"Diagnostic: {rel(duplicate_path)}"
        )

    registry_keys = missing_document[
        ["target_date", "decision_rule"]
    ].drop_duplicates()

    comparison = derived_missing.merge(
        registry_keys.assign(recorded_in_phase8_missing_registry=True),
        on=["target_date", "decision_rule"],
        how="outer",
        indicator=True,
    )
    if not (comparison["_merge"] == "both").all():
        diagnostic_path = OUT / "phase17_missing_registry_key_mismatch.csv"
        write_csv(diagnostic_path, comparison)
        fail(
            "The derived 37 missing keys do not exactly match the Phase 8 "
            f"missing-support registry. Diagnostic: {rel(diagnostic_path)}"
        )

    excluded = {
        missing_columns["date"],
        missing_columns["rule"],
        "target_date",
        "decision_rule",
    }
    missing_document["documented_reason_text"] = missing_document.apply(
        combine_reason_text,
        axis=1,
        excluded_columns=excluded,
    )

    classifications = missing_document[
        "documented_reason_text"
    ].map(classify_reason)
    missing_document["reason_category"] = [
        value[0] for value in classifications
    ]
    missing_document["reason_classification_basis"] = [
        value[1] for value in classifications
    ]

    output = derived_missing.merge(
        missing_document[
            [
                "target_date",
                "decision_rule",
                "documented_reason_text",
                "reason_category",
                "reason_classification_basis",
            ]
        ],
        on=["target_date", "decision_rule"],
        how="left",
        validate="one_to_one",
    )

    date_missing_count = output.groupby(
        "target_date"
    )["decision_rule"].transform("size")
    output["missing_keys_on_target_date"] = date_missing_count
    output["missing_scope"] = np.where(
        output["missing_keys_on_target_date"] == 4,
        "complete_date_absence",
        "partial_date_rule_absence",
    )
    output["sample_period"] = np.where(
        output["target_date"].dt.month == 6,
        "june_out_of_sample",
        "weather_plus_market_development",
    )
    output["supported_keys_on_target_date"] = (
        4 - output["missing_keys_on_target_date"]
    )
    output["imputed"] = False

    support_by_rule_period = (
        merged.assign(
            sample_period=np.where(
                merged["target_date"].dt.month == 6,
                "june_out_of_sample",
                "weather_plus_market_development",
            )
        )
        .groupby(
            ["sample_period", "decision_rule"],
            as_index=False,
        )
        .agg(
            theoretical_keys=(
                "certified_forecast_supported",
                "size",
            ),
            supported_keys=(
                "certified_forecast_supported",
                "sum",
            ),
        )
    )
    support_by_rule_period["missing_keys"] = (
        support_by_rule_period["theoretical_keys"]
        - support_by_rule_period["supported_keys"]
    )
    support_by_rule_period["support_rate"] = (
        support_by_rule_period["supported_keys"]
        / support_by_rule_period["theoretical_keys"]
    )

    support_by_date = (
        merged.groupby("target_date", as_index=False)
        .agg(
            supported_keys=(
                "certified_forecast_supported",
                "sum",
            ),
            theoretical_keys=(
                "certified_forecast_supported",
                "size",
            ),
        )
    )
    support_by_date["missing_keys"] = (
        support_by_date["theoretical_keys"]
        - support_by_date["supported_keys"]
    )
    support_by_date["complete_four_rule_support"] = (
        support_by_date["supported_keys"] == 4
    )
    support_by_date["any_forecast_support"] = (
        support_by_date["supported_keys"] > 0
    )
    support_by_date["sample_period"] = np.where(
        support_by_date["target_date"].dt.month == 6,
        "june_out_of_sample",
        "weather_plus_market_development",
    )

    pattern_summary = (
        output.groupby(
            [
                "sample_period",
                "missing_scope",
                "decision_rule",
                "reason_category",
            ],
            as_index=False,
        )
        .agg(
            missing_keys=("decision_rule", "size"),
            target_dates=("target_date", "nunique"),
        )
        .sort_values(
            [
                "sample_period",
                "missing_scope",
                "decision_rule",
                "reason_category",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    return (
        output,
        support_by_rule_period,
        support_by_date,
        pattern_summary,
    )


def create_figures(
    residual: pd.DataFrame,
    support_by_date: pd.DataFrame,
    missing_registry: pd.DataFrame,
) -> list[Path]:
    FIG.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    box_data = [
        residual.loc[
            residual["decision_rule"] == rule,
            "residual_c",
        ].to_numpy(dtype=float)
        for rule in RULE_ORDER
    ]

    figure, axis = plt.subplots(figsize=(8.5, 5.5))
    axis.boxplot(
        box_data,
        labels=[RULE_LABELS[rule] for rule in RULE_ORDER],
        showfliers=False,
    )
    axis.axhline(0.0, linewidth=1.0)
    axis.set_ylabel("HKO minus deterministic forecast (°C)")
    axis.set_xlabel("Decision rule")
    axis.set_title(
        "Rule-specific deterministic forecast errors over 730 dates"
    )
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()

    for suffix in ("png", "pdf"):
        path = FIG / f"phase17_rule_error_boxplot.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    dates = list(
        pd.to_datetime(support_by_date["target_date"]).sort_values()
    )
    date_index = {date: index for index, date in enumerate(dates)}
    rule_index = {rule: index for index, rule in enumerate(RULE_ORDER)}

    matrix = np.ones((len(RULE_ORDER), len(dates)), dtype=float)
    for row in missing_registry.itertuples(index=False):
        matrix[
            rule_index[row.decision_rule],
            date_index[pd.Timestamp(row.target_date)],
        ] = 0.0

    figure, axis = plt.subplots(figsize=(12, 3.7))
    image = axis.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest",
        vmin=0.0,
        vmax=1.0,
    )
    axis.set_yticks(range(len(RULE_ORDER)))
    axis.set_yticklabels([RULE_LABELS[rule] for rule in RULE_ORDER])
    tick_positions = np.linspace(
        0,
        len(dates) - 1,
        min(8, len(dates)),
        dtype=int,
    )
    axis.set_xticks(tick_positions)
    axis.set_xticklabels(
        [dates[position].strftime("%d %b") for position in tick_positions],
        rotation=30,
        ha="right",
    )
    axis.set_xlabel("Settlement date")
    axis.set_title(
        "Certified deterministic forecast support by date and decision rule"
    )
    colourbar = figure.colorbar(image, ax=axis, pad=0.02)
    colourbar.set_ticks([0.0, 1.0])
    colourbar.set_ticklabels(["missing", "supported"])
    figure.tight_layout()

    for suffix in ("png", "pdf"):
        path = FIG / f"phase17_missing_support_matrix.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    return paths


def markdown_table(
    frame: pd.DataFrame,
    columns: list[str],
    headers: list[str],
    decimals: int = 4,
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
            fail(f"Required Phase 17 input is missing: {rel(path)}")

    phase16_spec = json.loads(
        PHASE16_SPEC.read_text(encoding="utf-8")
    )
    if phase16_spec.get("status") != "PASSED":
        fail("Phase 16 specification is not certified as PASSED.")

    residual_raw = pd.read_csv(RESIDUAL_PATH)
    phase16 = pd.read_csv(PHASE16_PREDICTIONS)
    support = pd.read_csv(PHASE8_SUPPORT)
    missing_source = pd.read_csv(PHASE8_MISSING)
    contract = pd.read_csv(CONTRACT_UNIVERSE)

    residual_columns = discover_residual_columns(residual_raw)
    phase16_columns = discover_phase16_columns(phase16)

    print(
        "PHASE17_RESIDUAL_COLUMN_MAP="
        + json.dumps(residual_columns, sort_keys=True)
    )
    print(
        "PHASE17_PHASE16_COLUMN_MAP="
        + json.dumps(phase16_columns, sort_keys=True)
    )

    residual = pd.DataFrame(
        {
            "target_date": pd.to_datetime(
                residual_raw[residual_columns["date"]],
                errors="raise",
            ).dt.normalize(),
            "decision_rule": residual_raw[
                residual_columns["rule"]
            ].map(normalise_rule),
            "forecast_daily_max_c": pd.to_numeric(
                residual_raw[residual_columns["forecast"]],
                errors="raise",
            ),
            "hko_daily_max_c": pd.to_numeric(
                residual_raw[residual_columns["outcome"]],
                errors="raise",
            ),
            "residual_c": pd.to_numeric(
                residual_raw[residual_columns["residual"]],
                errors="raise",
            ),
        }
    )

    if len(residual) != 2920:
        fail(
            f"Expected 2,920 weather-only residual rows; found {len(residual)}."
        )
    if residual["target_date"].nunique() != 730:
        fail(
            "Weather-only residual panel does not contain 730 dates."
        )
    if set(residual["decision_rule"]) != set(RULE_ORDER):
        fail(
            "Weather-only residual panel does not contain the four "
            "certified decision rules."
        )
    if residual.duplicated(
        ["target_date", "decision_rule"]
    ).any():
        fail(
            "Weather-only residual panel contains duplicate date-rule keys."
        )
    if not np.allclose(
        residual["residual_c"],
        residual["hko_daily_max_c"]
        - residual["forecast_daily_max_c"],
        atol=1e-10,
        rtol=0.0,
    ):
        fail(
            "Residual sign convention is inconsistent with HKO minus forecast."
        )

    summary = rule_error_summary(residual)
    block_summary = validation_block_summary(
        phase16,
        phase16_columns,
    )
    pairwise = pairwise_rule_differences(residual)
    pearson, spearman = residual_correlation_outputs(residual)
    correlations = pd.concat(
        [pearson, spearman],
        ignore_index=True,
    )
    decomposition = variance_decomposition(residual)
    rank_tests = rank_diagnostics(residual)

    (
        missing_registry,
        support_by_rule_period,
        support_by_date,
        missing_pattern_summary,
    ) = build_missing_support_registry(
        support,
        missing_source,
        contract,
    )

    figure_paths = create_figures(
        residual,
        support_by_date,
        missing_registry,
    )

    development_missing = int(
        (
            missing_registry["sample_period"]
            == "weather_plus_market_development"
        ).sum()
    )
    june_missing = int(
        (
            missing_registry["sample_period"]
            == "june_out_of_sample"
        ).sum()
    )
    fully_missing_dates = int(
        missing_registry.loc[
            missing_registry["missing_scope"]
            == "complete_date_absence",
            "target_date",
        ].nunique()
    )
    partial_missing_dates = int(
        missing_registry.loc[
            missing_registry["missing_scope"]
            == "partial_date_rule_absence",
            "target_date",
        ].nunique()
    )
    complete_support_dates = int(
        support_by_date["complete_four_rule_support"].sum()
    )
    any_support_dates = int(
        support_by_date["any_forecast_support"].sum()
    )

    date_share = float(
        decomposition.loc[
            decomposition["component"] == "target_date",
            "share_of_total_sum_squares",
        ].iloc[0]
    )
    rule_share = float(
        decomposition.loc[
            decomposition["component"] == "decision_rule",
            "share_of_total_sum_squares",
        ].iloc[0]
    )
    interaction_share = float(
        decomposition.loc[
            decomposition["component"]
            == "date_by_rule_interaction",
            "share_of_total_sum_squares",
        ].iloc[0]
    )

    if not math.isclose(
        date_share + rule_share + interaction_share,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-10,
    ):
        fail(
            "Deterministic-error variance shares do not sum to one."
        )

    gap_updates = pd.DataFrame(
        [
            {
                "gap_id": "G07",
                "gap": "Rule-specific deterministic error",
                "phase_closed": 17,
                "status": "CLOSED",
                "evidence": (
                    "phase17_rule_error_summary.csv|"
                    "phase17_pairwise_rule_differences.csv|"
                    "phase17_error_by_validation_block.csv|"
                    "phase17_error_variance_decomposition.csv"
                ),
            },
            {
                "gap_id": "G12",
                "gap": "Missing forecast support",
                "phase_closed": 17,
                "status": "CLOSED",
                "evidence": (
                    "phase17_missing_key_registry.csv|"
                    "phase17_support_by_rule_period.csv|"
                    "phase17_support_by_date.csv|"
                    "phase17_missing_pattern_summary.csv"
                ),
            },
        ]
    )

    spec = {
        "phase": 17,
        "name": (
            "Rule-specific deterministic error and "
            "missing-support analysis"
        ),
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "git_branch": git("branch", "--show-current"),
        "git_commit_before_phase17": git("rev-parse", "HEAD"),
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
        "deterministic_error": {
            "sign_convention": (
                "residual = HKO realised daily maximum minus "
                "deterministic forecast daily maximum"
            ),
            "weather_only_dates": 730,
            "decision_rules": RULE_ORDER,
            "weather_only_rows": 2920,
            "validation_dates": 365,
            "rule_validation_block_rows": 16,
            "bootstrap": {
                "replications": BOOTSTRAP_REPLICATIONS,
                "unit": "target_date",
                "base_seed": BOOTSTRAP_SEED,
                "interval": "2.5th and 97.5th percentiles",
            },
            "variance_decomposition": (
                "balanced two-way descriptive decomposition into "
                "date, decision-rule and date-by-rule interaction "
                "sums of squares"
            ),
        },
        "missing_support": {
            "settlement_dates": 103,
            "theoretical_date_rule_keys": 412,
            "forecast_supported_dates": 102,
            "forecast_supported_date_rule_keys": 375,
            "unsupported_date_rule_keys": 37,
            "development_unsupported_keys": development_missing,
            "june_unsupported_keys": june_missing,
            "dates_with_complete_absence": fully_missing_dates,
            "dates_with_partial_absence": partial_missing_dates,
            "dates_with_any_support": any_support_dates,
            "dates_with_complete_four_rule_support": complete_support_dates,
            "imputation_used": False,
            "classification_source": rel(PHASE8_MISSING),
        },
        "figures": [rel(path) for path in figure_paths],
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

    write_csv(
        OUT / "phase17_rule_error_summary.csv",
        summary,
    )
    write_csv(
        OUT / "phase17_error_by_validation_block.csv",
        block_summary,
    )
    write_csv(
        OUT / "phase17_pairwise_rule_differences.csv",
        pairwise,
    )
    write_csv(
        OUT / "phase17_rule_error_correlations.csv",
        correlations,
    )
    write_csv(
        OUT / "phase17_error_variance_decomposition.csv",
        decomposition,
    )
    write_csv(
        OUT / "phase17_rule_rank_diagnostics.csv",
        rank_tests,
    )
    write_csv(
        OUT / "phase17_missing_key_registry.csv",
        missing_registry,
    )
    write_csv(
        OUT / "phase17_support_by_rule_period.csv",
        support_by_rule_period,
    )
    write_csv(
        OUT / "phase17_support_by_date.csv",
        support_by_date,
    )
    write_csv(
        OUT / "phase17_missing_pattern_summary.csv",
        missing_pattern_summary,
    )
    write_csv(
        OUT / "phase17_gap_updates.csv",
        gap_updates,
    )
    write_json(
        CONFIG / "phase17_error_missing_support_spec.json",
        spec,
    )

    best_mae = summary.sort_values(
        "mae_c",
        kind="stable",
    ).iloc[0]
    worst_mae = summary.sort_values(
        "mae_c",
        kind="stable",
    ).iloc[-1]
    highest_bias = summary.sort_values(
        "mean_error_hko_minus_forecast_c",
        kind="stable",
    ).iloc[-1]

    report_lines = [
        "# Phase 17 Rule-Specific Deterministic Error and Missing Support",
        "",
        "## Status",
        "",
        "PASSED",
        "",
        "## Connection to Phase 16",
        "",
        "Phase 16 established that the static rule-specific Gaussian correction materially improves on the raw deterministic forecast, and that the Matérn-3/2 GP improves further on the static correction. Phase 17 now identifies how the raw deterministic errors differ across decision rules and documents exactly where the 37 market-period forecast keys are unavailable.",
        "",
        "## Deterministic-error definition",
        "",
        "For target date `d` and decision rule `r`, the deterministic error is",
        "",
        "`e_{d,r} = HKO realised daily maximum - deterministic forecast daily maximum`.",
        "",
        "A positive value therefore means that the deterministic forecast underpredicted the realised HKO maximum.",
        "",
        "## Rule-specific results over the 730-date weather-only period",
        "",
    ]
    report_lines.extend(
        markdown_table(
            summary,
            [
                "decision_rule",
                "mean_error_hko_minus_forecast_c",
                "mae_c",
                "rmse_c",
                "error_standard_deviation_c",
                "underforecast_rate",
            ],
            [
                "Decision rule",
                "Mean error (°C)",
                "MAE (°C)",
                "RMSE (°C)",
                "SD (°C)",
                "Underforecast rate",
            ],
            decimals=4,
        )
    )
    report_lines.extend(
        [
            "",
            f"- Lowest MAE: `{best_mae['decision_rule']}` at {float(best_mae['mae_c']):.6f} °C.",
            f"- Highest MAE: `{worst_mae['decision_rule']}` at {float(worst_mae['mae_c']):.6f} °C.",
            f"- Largest mean underprediction: `{highest_bias['decision_rule']}` at {float(highest_bias['mean_error_hko_minus_forecast_c']):.6f} °C.",
            "- Rule-specific bootstrap intervals, quantiles, tail shape and accuracy rates are stored in `phase17_rule_error_summary.csv`.",
            "",
            "## Matched rule comparisons",
            "",
            "Each pairwise comparison uses the same 730 target dates. Signed-error differences measure relative bias; absolute-error differences measure relative accuracy. Negative absolute-error differences favour the first rule.",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            pairwise,
            [
                "first_rule",
                "second_rule",
                "mean_signed_error_difference_c",
                "mean_absolute_error_difference_c",
                "absolute_error_bootstrap_lower_95_c",
                "absolute_error_bootstrap_upper_95_c",
            ],
            [
                "First rule",
                "Second rule",
                "Signed difference (°C)",
                "Absolute-error difference (°C)",
                "95% lower",
                "95% upper",
            ],
            decimals=4,
        )
    )
    report_lines.extend(
        [
            "",
            "## Error-structure decomposition",
            "",
            f"- Target-date component: {date_share:.4%} of total deterministic-error sum of squares.",
            f"- Decision-rule component: {rule_share:.4%}.",
            f"- Date-by-rule interaction and remaining cell variation: {interaction_share:.4%}.",
            "- This is a descriptive balanced decomposition. It does not treat the interaction term as an independently replicated error variance.",
            "- Pearson and Spearman cross-rule correlations are in `phase17_rule_error_correlations.csv`.",
            "- Friedman rank diagnostics are reported only descriptively because serial dependence across dates is examined later.",
            "",
            "## Validation-block stability",
            "",
            "- The 365 chronological validation dates are divided into the same four blocks used for GP validation.",
            "- Sixteen rule-by-block deterministic-error summaries are stored in `phase17_error_by_validation_block.csv`.",
            "- These results provide the raw-forecast component needed for the joint model and validation-block comparison in Phase 18.",
            "",
            "## Exact missing-support accounting",
            "",
            "- Settlement and market dates: 103.",
            "- Theoretical date-rule keys: 412.",
            "- Certified supported date-rule keys: 375 across 102 dates.",
            "- Unsupported date-rule keys: 37.",
            f"- Unsupported development-period keys: {development_missing}.",
            f"- Unsupported June keys: {june_missing}.",
            f"- Dates with complete four-rule forecast absence: {fully_missing_dates}.",
            f"- Dates with partial rule-specific absence: {partial_missing_dates}.",
            f"- Dates with any certified forecast support: {any_support_dates}.",
            f"- Dates with complete four-rule support: {complete_support_dates}.",
            "- Every derived missing key exactly matches the Phase 8 missing-support registry.",
            "- No missing forecast has been imputed.",
            "",
            "## Missing-key classification",
            "",
            "Every unsupported key is classified by date, rule, sample period, complete-date versus partial-rule absence, documented Phase 8 reason text and broad technical reason category. The full registry is `phase17_missing_key_registry.csv`; aggregated patterns are in `phase17_missing_pattern_summary.csv`.",
            "",
            "The classification does not claim that the missingness is statistically random. Forecast accuracy cannot be observed for a key whose deterministic forecast is absent. Phase 17 therefore reports the operational missingness structure and preserves exact common support rather than attempting to estimate unavailable errors.",
            "",
            "## Thesis-facing interpretation",
            "",
            "The Phase 16 gain from raw point forecast to static Gaussian correction is consistent with a substantial systematic local error in the deterministic forecast. Phase 17 separates the part shared by all rules on a target date from smaller rule-specific and date-by-rule components. This provides the empirical rationale for rule-specific residual post-processing while avoiding the stronger claim that decision lead time alone explains all residual variation.",
            "",
            "The 37 unsupported market-period keys are an archive and support limitation, not observations to be reconstructed statistically. Model, market and trading comparisons must continue to use explicitly defined common-support samples.",
            "",
            "## Closed Phase 14 gaps",
            "",
            "- G07: rule-specific deterministic error.",
            "- G12: missing forecast support.",
            "",
            "## Evidential boundary",
            "",
            "Phase 17 does not refit a GP, alter the frozen Phase 16 comparison or introduce a forecast imputation rule. Bootstrap intervals resample target dates and are descriptive under the current dependence assumptions. More detailed dependence, coverage and heteroskedasticity diagnostics remain for Phase 19.",
            "",
        ]
    )

    (OUT / "phase17_error_missing_support_report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("PHASE17_STATUS=PASSED")
    print(f"PHASE17_WEATHER_ONLY_ROWS={len(residual)}")
    print(
        f"PHASE17_WEATHER_ONLY_DATES="
        f"{residual['target_date'].nunique()}"
    )
    print(f"PHASE17_RULE_SUMMARY_ROWS={len(summary)}")
    print(f"PHASE17_RULE_BLOCK_ROWS={len(block_summary)}")
    print(f"PHASE17_PAIRWISE_RULE_ROWS={len(pairwise)}")
    print(
        "PHASE17_VARIANCE_SHARES="
        + json.dumps(
            {
                "target_date": date_share,
                "decision_rule": rule_share,
                "date_by_rule_interaction": interaction_share,
            },
            sort_keys=True,
        )
    )
    print(
        "PHASE17_MISSING_SUPPORT="
        + json.dumps(
            {
                "theoretical_keys": 412,
                "supported_keys": 375,
                "missing_keys": 37,
                "development_missing": development_missing,
                "june_missing": june_missing,
                "complete_absence_dates": fully_missing_dates,
                "partial_absence_dates": partial_missing_dates,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
