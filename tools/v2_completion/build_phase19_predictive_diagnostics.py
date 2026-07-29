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
from typing import Any, Iterable, Iterator

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/v2_completion"
FIG = OUT / "phase19_figures"
CONFIG = ROOT / "config/v2_completion"

VALIDATION_PATH = (
    ROOT / "outputs/v2/diagnostics/07_gp_validation_predictions.csv"
)
PHASE15_SPEC_PATH = (
    ROOT / "config/v2_completion/phase15_gp_implementation_spec.json"
)
PHASE18_SPEC_PATH = (
    ROOT / "config/v2_completion/phase18_gp_stability_spec.json"
)
PHASE18_REPORT_PATH = (
    ROOT / "outputs/v2_completion/phase18_gp_stability_report.md"
)

REQUIRED_PATHS = [
    VALIDATION_PATH,
    PHASE15_SPEC_PATH,
    PHASE18_SPEC_PATH,
    PHASE18_REPORT_PATH,
]

MODELS = ["rbf", "matern32"]
MODEL_LABELS = {
    "rbf": "RBF GP",
    "matern32": "Matérn-3/2 GP",
}
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
CENTRAL_LEVELS = [0.50, 0.80, 0.90]
BOOTSTRAP_REPLICATIONS = 10_000
BOOTSTRAP_SEED = 20260729
BLOCK_BOOTSTRAP_REPLICATIONS = 5_000
BLOCK_BOOTSTRAP_LENGTH = 7
ACF_LAGS = 14
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
            10 * sum(
                token.lower() in lowered
                for token in contains_all
            )
            + 2 * sum(
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


def normalise_model(value: Any) -> str:
    text = str(value).strip().lower()
    compact = (
        text.replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .replace("é", "e")
    )
    if "matern" in compact:
        return "matern32"
    if "rbf" in compact or "radialbasis" in compact:
        return "rbf"
    return text


def discover_columns(
    frame: pd.DataFrame,
) -> tuple[dict[str, str], dict[float, str], dict[float, str]]:
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
            exact=["kernel", "model", "model_family"],
        ),
        "fold": find_column(
            columns,
            exact=[
                "fold_id",
                "validation_block",
                "block_id",
                "fold_number",
            ],
        ),
        "fold_number": find_column(
            columns,
            exact=["fold_number"],
        ),
        "outcome": find_column(
            columns,
            exact=[
                "hko_daily_max_c",
                "observed_temperature_c",
                "outcome_temperature_c",
            ],
            contains_all=["hko", "daily", "max"],
        ),
        "forecast": find_column(
            columns,
            exact=["forecast_daily_max_c"],
            contains_all=["forecast", "daily", "max"],
        ),
        "predictive_mean": find_column(
            columns,
            exact=["temperature_predictive_mean_c"],
            contains_all=["temperature", "predictive", "mean"],
        ),
        "predictive_std": find_column(
            columns,
            exact=["predictive_standard_deviation_c"],
            contains_all=["predictive", "standard", "deviation"],
        ),
        "residual": find_column(
            columns,
            exact=["corrected_temperature_error_c"],
            contains_all=["corrected", "temperature", "error"],
        ),
        "standardised_residual": find_column(
            columns,
            exact=["standardised_residual_error"],
            contains_all=["standardised", "residual"],
        ),
        "pit": find_column(
            columns,
            exact=["pit_value"],
            contains_all=["pit"],
        ),
        "crps": find_column(
            columns,
            exact=["crps_c"],
            contains_all=["crps"],
        ),
    }

    required = [
        "date",
        "rule",
        "model",
        "fold",
        "outcome",
        "forecast",
        "predictive_mean",
        "predictive_std",
        "crps",
    ]
    missing = [key for key in required if not mapping[key]]
    if missing:
        fail(
            f"Could not identify required Phase 7 columns {missing}. "
            f"Available columns: {columns}"
        )

    quantile_columns: dict[float, str] = {}
    for column in columns:
        match = re.fullmatch(
            r"q(\d{2})_c",
            column.lower(),
        )
        if not match:
            continue
        integer = int(match.group(1))
        if 1 <= integer <= 99:
            quantile_columns[integer / 100.0] = column

    if len(quantile_columns) != 99:
        fail(
            "Expected q01_c through q99_c in the Phase 7 validation "
            f"panel; found {len(quantile_columns)} quantile columns."
        )

    coverage_columns: dict[float, str] = {}
    for level in CENTRAL_LEVELS:
        percentage = int(round(100 * level))
        candidate = find_column(
            columns,
            exact=[
                f"central_{percentage}_covered",
                f"central_{percentage}_coverage",
            ],
        )
        if candidate:
            coverage_columns[level] = candidate

    return (
        {
            key: str(value)
            for key, value in mapping.items()
            if value is not None
        },
        quantile_columns,
        coverage_columns,
    )


def prepare_panel(
    raw: pd.DataFrame,
    columns: dict[str, str],
    quantile_columns: dict[float, str],
) -> pd.DataFrame:
    # Preserve the original CSV row position so every stored diagnostic
    # can be reconciled against the correct observation even after the
    # analytical panel is sorted for later chronological calculations.
    panel = pd.DataFrame(
        {
            "source_row_id": np.arange(len(raw), dtype=int),
            "target_date": pd.to_datetime(
                raw[columns["date"]],
                errors="raise",
            ).dt.normalize(),
            "decision_rule": raw[columns["rule"]].map(normalise_rule),
            "model": raw[columns["model"]].map(normalise_model),
            "fold_id": raw[columns["fold"]].astype(str),
            "fold_number": (
                pd.to_numeric(
                    raw[columns["fold_number"]],
                    errors="raise",
                ).astype(int)
                if columns.get("fold_number")
                else pd.factorize(
                    raw[columns["fold"]].astype(str),
                    sort=True,
                )[0]
                + 1
            ),
            "hko_daily_max_c": pd.to_numeric(
                raw[columns["outcome"]],
                errors="raise",
            ),
            "forecast_daily_max_c": pd.to_numeric(
                raw[columns["forecast"]],
                errors="raise",
            ),
            "temperature_predictive_mean_c": pd.to_numeric(
                raw[columns["predictive_mean"]],
                errors="raise",
            ),
            "predictive_standard_deviation_c": pd.to_numeric(
                raw[columns["predictive_std"]],
                errors="raise",
            ),
            "crps_c": pd.to_numeric(
                raw[columns["crps"]],
                errors="raise",
            ),
        }
    )

    panel["corrected_temperature_error_c"] = (
        panel["hko_daily_max_c"]
        - panel["temperature_predictive_mean_c"]
    )
    panel["standardised_residual_error"] = (
        panel["corrected_temperature_error_c"]
        / panel["predictive_standard_deviation_c"]
    )
    panel["pit_value"] = stats.norm.cdf(
        panel["standardised_residual_error"]
    )

    # Add all 99 quantiles in one operation. This avoids repeated column
    # insertion, preserves the source-row alignment and prevents pandas
    # DataFrame fragmentation warnings.
    quantile_frame = pd.DataFrame(
        {
            f"q{int(round(100 * probability)):02d}_c": pd.to_numeric(
                raw[column],
                errors="raise",
            ).to_numpy(dtype=float)
            for probability, column in sorted(
                quantile_columns.items()
            )
        },
        index=panel.index,
    )
    panel = pd.concat(
        [panel, quantile_frame],
        axis=1,
        copy=False,
    )

    if len(panel) != 2920:
        fail(
            f"Expected 2,920 Phase 7 validation rows; found {len(panel)}."
        )
    if panel["target_date"].nunique() != 365:
        fail("Phase 7 panel does not contain 365 validation dates.")
    if panel["decision_rule"].nunique() != 4:
        fail("Phase 7 panel does not contain four decision rules.")
    if set(panel["decision_rule"]) != set(RULE_ORDER):
        fail("Phase 7 panel decision-rule labels do not match the certified set.")
    if set(panel["model"]) != set(MODELS):
        fail("Phase 7 panel does not contain RBF and Matérn-3/2 only.")
    if panel["fold_id"].nunique() != 4:
        fail("Phase 7 panel does not contain four validation blocks.")
    if panel.duplicated(
        ["target_date", "decision_rule", "model"]
    ).any():
        fail("Duplicate date-rule-model keys exist in the validation panel.")

    model_counts = panel.groupby(
        ["target_date", "decision_rule"],
        sort=False,
    )["model"].nunique()
    if not (model_counts == 2).all():
        fail("At least one date-rule key does not contain both GP models.")

    if (
        panel[
            [
                "hko_daily_max_c",
                "forecast_daily_max_c",
                "temperature_predictive_mean_c",
                "predictive_standard_deviation_c",
                "crps_c",
            ]
        ]
        .isna()
        .any()
        .any()
    ):
        fail("Required validation values contain missing data.")

    numeric = panel.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        fail("Validation panel contains non-finite numerical values.")

    if (panel["predictive_standard_deviation_c"] <= 0).any():
        fail("Predictive standard deviations must be strictly positive.")
    if (panel["crps_c"] < 0).any():
        fail("CRPS must be non-negative.")

    date_sequence = (
        panel[["target_date"]]
        .drop_duplicates()
        .sort_values("target_date")
        ["target_date"]
    )
    expected_sequence = pd.date_range(
        date_sequence.iloc[0],
        date_sequence.iloc[-1],
        freq="D",
    )
    if len(expected_sequence) != 365 or not np.array_equal(
        date_sequence.to_numpy(),
        expected_sequence.to_numpy(),
    ):
        fail(
            "The chronological validation period is not a complete "
            "365-day sequence."
        )

    block_counts = (
        panel[["target_date", "fold_id"]]
        .drop_duplicates()
        .groupby("fold_id")["target_date"]
        .nunique()
        .sort_values()
        .tolist()
    )
    if block_counts != [91, 91, 91, 92]:
        fail(
            f"Unexpected validation-block date counts: {block_counts}"
        )

    return panel.sort_values(
        ["target_date", "decision_rule", "model"],
        kind="stable",
    ).reset_index(drop=True)


def reconcile_stored_diagnostics(
    raw: pd.DataFrame,
    panel: pd.DataFrame,
    columns: dict[str, str],
    quantile_columns: dict[float, str],
    coverage_columns: dict[float, str],
) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    if "source_row_id" not in panel.columns:
        fail(
            "The analytical validation panel does not retain source-row "
            "identifiers required for exact reconciliation."
        )

    if panel["source_row_id"].duplicated().any():
        fail("Source-row identifiers are not unique.")

    if set(panel["source_row_id"]) != set(range(len(raw))):
        fail(
            "Source-row identifiers do not form the complete raw-row "
            "index required for reconciliation."
        )

    # Reconciliation is observation-by-observation against the original
    # CSV order. Later score and dependence calculations may use the
    # chronologically sorted panel, but that ordering must not be used
    # when comparing stored and independently reconstructed columns.
    source_order_panel = (
        panel.sort_values("source_row_id", kind="stable")
        .reset_index(drop=True)
    )

    def add_check(
        name: str,
        maximum_error: float,
        tolerance: float,
        detail: str,
    ) -> None:
        checks.append(
            {
                "check": name,
                "maximum_absolute_error": float(maximum_error),
                "tolerance": float(tolerance),
                "status": (
                    "PASSED"
                    if maximum_error <= tolerance
                    else "FAILED"
                ),
                "detail": detail,
            }
        )

    if columns.get("residual"):
        stored = pd.to_numeric(
            raw[columns["residual"]],
            errors="raise",
        ).to_numpy(dtype=float)
        derived = source_order_panel[
            "corrected_temperature_error_c"
        ].to_numpy(dtype=float)
        add_check(
            "stored corrected temperature error",
            float(np.max(np.abs(stored - derived))),
            NUMERICAL_TOLERANCE,
            "stored value versus outcome minus predictive mean",
        )

    if columns.get("standardised_residual"):
        stored = pd.to_numeric(
            raw[columns["standardised_residual"]],
            errors="raise",
        ).to_numpy(dtype=float)
        derived = source_order_panel[
            "standardised_residual_error"
        ].to_numpy(dtype=float)
        add_check(
            "stored standardised residual",
            float(np.max(np.abs(stored - derived))),
            NUMERICAL_TOLERANCE,
            "stored value versus corrected error divided by predictive standard deviation",
        )

    if columns.get("pit"):
        stored = pd.to_numeric(
            raw[columns["pit"]],
            errors="raise",
        ).to_numpy(dtype=float)
        derived = source_order_panel[
            "pit_value"
        ].to_numpy(dtype=float)
        add_check(
            "stored PIT value",
            float(np.max(np.abs(stored - derived))),
            NUMERICAL_TOLERANCE,
            "stored value versus Gaussian CDF of standardised residual",
        )

    maximum_quantile_error = 0.0
    maximum_monotonicity_violation = 0.0
    probabilities = sorted(quantile_columns)
    quantile_matrix = np.column_stack(
        [
            source_order_panel[
                f"q{int(round(100 * probability)):02d}_c"
            ].to_numpy(dtype=float)
            for probability in probabilities
        ]
    )
    expected_quantiles = np.column_stack(
        [
            source_order_panel[
                "temperature_predictive_mean_c"
            ].to_numpy(dtype=float)
            + source_order_panel[
                "predictive_standard_deviation_c"
            ].to_numpy(dtype=float)
            * stats.norm.ppf(probability)
            for probability in probabilities
        ]
    )
    maximum_quantile_error = float(
        np.max(np.abs(quantile_matrix - expected_quantiles))
    )
    differences = np.diff(quantile_matrix, axis=1)
    maximum_monotonicity_violation = float(
        max(0.0, -float(differences.min()))
    )

    add_check(
        "Gaussian quantile reconstruction",
        maximum_quantile_error,
        5e-8,
        "q01_c through q99_c versus predictive mean plus Gaussian quantile times predictive standard deviation",
    )
    add_check(
        "quantile monotonicity",
        maximum_monotonicity_violation,
        1e-12,
        "largest decrease between consecutive stored predictive quantiles",
    )

    for level, column in coverage_columns.items():
        lower_probability = (1.0 - level) / 2.0
        upper_probability = 1.0 - lower_probability
        lower_column = f"q{int(round(100 * lower_probability)):02d}_c"
        upper_column = f"q{int(round(100 * upper_probability)):02d}_c"
        derived = (
            (
                source_order_panel["hko_daily_max_c"]
                >= source_order_panel[lower_column]
            )
            & (
                source_order_panel["hko_daily_max_c"]
                <= source_order_panel[upper_column]
            )
        ).astype(int)
        stored = pd.to_numeric(
            raw[column],
            errors="raise",
        ).astype(int)
        maximum_error = float(
            np.max(
                np.abs(
                    stored.to_numpy(dtype=float)
                    - derived.to_numpy(dtype=float)
                )
            )
        )
        add_check(
            f"stored central {int(round(100 * level))}% coverage",
            maximum_error,
            0.0,
            "stored indicator versus interval reconstructed from predictive quantiles",
        )

    result = pd.DataFrame(checks)
    failed = result.loc[result["status"] != "PASSED"]
    if not failed.empty:
        diagnostic_path = (
            OUT / "phase19_failed_reconciliation_checks.csv"
        )
        write_csv(diagnostic_path, result)
        print(
            "PHASE19_FAILED_RECONCILIATION_CHECKS="
            + failed.to_json(
                orient="records",
                double_precision=15,
            )
        )
        fail(
            "At least one Phase 19 predictive-diagnostic "
            "reconciliation check failed. Diagnostic: "
            f"{rel(diagnostic_path)}"
        )
    return result


def stable_seed(*parts: Any) -> int:
    text = "|".join(str(part) for part in parts)
    return BOOTSTRAP_SEED + sum(
        (index + 1) * ord(character)
        for index, character in enumerate(text)
    ) % 1_000_000


def bootstrap_mean_interval(
    values: np.ndarray,
    seed: int,
    replications: int = BOOTSTRAP_REPLICATIONS,
) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=float)
    if (
        array.ndim != 1
        or len(array) < 2
        or np.any(~np.isfinite(array))
    ):
        fail(
            "Bootstrap input must be a finite one-dimensional array "
            "with at least two target dates."
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
        estimates[completed : completed + batch] = (
            array[indices].mean(axis=1)
        )
        completed += batch

    return (
        float(array.mean()),
        float(np.quantile(estimates, 0.025)),
        float(np.quantile(estimates, 0.975)),
    )


def scope_groups(
    frame: pd.DataFrame,
    include_rule_block: bool = True,
) -> Iterator[tuple[str, str, pd.DataFrame, bool]]:
    yield "overall", "all", frame, True

    for rule in RULE_ORDER:
        yield (
            "decision_rule",
            rule,
            frame.loc[frame["decision_rule"] == rule],
            False,
        )

    for fold_id, group in frame.groupby("fold_id", sort=True):
        yield "validation_block", str(fold_id), group, True

    if include_rule_block:
        for (fold_id, rule), group in frame.groupby(
            ["fold_id", "decision_rule"],
            sort=True,
        ):
            yield (
                "rule_by_validation_block",
                f"{rule}|{fold_id}",
                group,
                False,
            )


def date_balanced_values(
    group: pd.DataFrame,
    columns: list[str],
    average_rules: bool,
) -> pd.DataFrame:
    if average_rules:
        return (
            group.groupby("target_date", as_index=False)[columns]
            .mean()
            .sort_values("target_date")
            .reset_index(drop=True)
        )
    return (
        group[["target_date", *columns]]
        .sort_values("target_date")
        .reset_index(drop=True)
    )


def build_coverage_outputs(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for model in MODELS:
        model_frame = panel.loc[panel["model"] == model].copy()

        for (
            scope,
            scope_value,
            group,
            average_rules,
        ) in scope_groups(model_frame):
            for level in CENTRAL_LEVELS:
                lower_probability = (1.0 - level) / 2.0
                upper_probability = 1.0 - lower_probability
                lower_column = (
                    f"q{int(round(100 * lower_probability)):02d}_c"
                )
                upper_column = (
                    f"q{int(round(100 * upper_probability)):02d}_c"
                )

                working = group[
                    [
                        "target_date",
                        "decision_rule",
                        "hko_daily_max_c",
                        lower_column,
                        upper_column,
                    ]
                ].copy()
                working["covered"] = (
                    (working["hko_daily_max_c"] >= working[lower_column])
                    & (working["hko_daily_max_c"] <= working[upper_column])
                ).astype(float)
                working["interval_width_c"] = (
                    working[upper_column] - working[lower_column]
                )

                date_values = date_balanced_values(
                    working,
                    ["covered", "interval_width_c"],
                    average_rules=average_rules,
                )
                (
                    empirical,
                    lower,
                    upper,
                ) = bootstrap_mean_interval(
                    date_values["covered"].to_numpy(dtype=float),
                    seed=stable_seed(
                        "coverage",
                        model,
                        scope,
                        scope_value,
                        level,
                    ),
                )

                rows.append(
                    {
                        "model": model,
                        "scope": scope,
                        "scope_value": scope_value,
                        "nominal_coverage": level,
                        "rows": int(len(working)),
                        "dates": int(
                            working["target_date"].nunique()
                        ),
                        "decision_rules": int(
                            working["decision_rule"].nunique()
                        ),
                        "empirical_coverage": empirical,
                        "coverage_error": empirical - level,
                        "bootstrap_lower_95_coverage": lower,
                        "bootstrap_upper_95_coverage": upper,
                        "bootstrap_lower_95_coverage_error": (
                            lower - level
                        ),
                        "bootstrap_upper_95_coverage_error": (
                            upper - level
                        ),
                        "mean_interval_width_c": float(
                            date_values["interval_width_c"].mean()
                        ),
                        "median_interval_width_c": float(
                            date_values["interval_width_c"].median()
                        ),
                        "bootstrap_replications": (
                            BOOTSTRAP_REPLICATIONS
                        ),
                        "bootstrap_unit": "target_date",
                    }
                )

    result = pd.DataFrame(rows)
    if len(result) != 150:
        fail(
            f"Expected 150 coverage-summary rows; found {len(result)}."
        )
    return result


def build_quantile_calibration(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []

    scopes = [("overall", "all", panel, True)]
    for rule in RULE_ORDER:
        scopes.append(
            (
                "decision_rule",
                rule,
                panel.loc[panel["decision_rule"] == rule],
                False,
            )
        )

    for model in MODELS:
        for scope, scope_value, group, average_rules in scopes:
            model_group = group.loc[group["model"] == model]
            for integer in range(1, 100):
                nominal = integer / 100.0
                quantile_column = f"q{integer:02d}_c"
                working = model_group[
                    ["target_date", "hko_daily_max_c", quantile_column]
                ].copy()
                working["covered"] = (
                    working["hko_daily_max_c"]
                    <= working[quantile_column]
                ).astype(float)

                date_values = date_balanced_values(
                    working,
                    ["covered"],
                    average_rules=average_rules,
                )
                empirical = float(date_values["covered"].mean())

                rows.append(
                    {
                        "model": model,
                        "scope": scope,
                        "scope_value": scope_value,
                        "nominal_probability": nominal,
                        "empirical_probability": empirical,
                        "calibration_error": empirical - nominal,
                        "absolute_calibration_error": abs(
                            empirical - nominal
                        ),
                        "squared_calibration_error": (
                            empirical - nominal
                        )
                        ** 2,
                        "dates": int(
                            working["target_date"].nunique()
                        ),
                    }
                )

    curve = pd.DataFrame(rows)
    if len(curve) != 990:
        fail(
            f"Expected 990 quantile-calibration rows; found {len(curve)}."
        )

    summary = (
        curve.groupby(
            ["model", "scope", "scope_value"],
            as_index=False,
        )
        .agg(
            nominal_points=("nominal_probability", "size"),
            dates=("dates", "max"),
            integrated_absolute_calibration_error=(
                "absolute_calibration_error",
                "mean",
            ),
            root_mean_squared_calibration_error=(
                "squared_calibration_error",
                lambda values: float(
                    math.sqrt(float(values.mean()))
                ),
            ),
            maximum_absolute_calibration_error=(
                "absolute_calibration_error",
                "max",
            ),
            mean_signed_calibration_error=(
                "calibration_error",
                "mean",
            ),
        )
        .sort_values(
            ["scope", "scope_value", "model"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    selected = curve.loc[
        curve["nominal_probability"].isin([0.10, 0.50, 0.90])
    ].pivot_table(
        index=["model", "scope", "scope_value"],
        columns="nominal_probability",
        values="calibration_error",
    )
    selected.columns = [
        f"calibration_error_q{int(round(100 * value)):02d}"
        for value in selected.columns
    ]
    selected = selected.reset_index()
    summary = summary.merge(
        selected,
        on=["model", "scope", "scope_value"],
        how="left",
        validate="one_to_one",
    )

    if len(summary) != 10:
        fail(
            f"Expected 10 calibration-summary rows; found {len(summary)}."
        )

    return curve, summary


def pit_uniformity_statistics(
    values: np.ndarray,
) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    if np.any((array < 0) | (array > 1)):
        fail("PIT values must lie in [0,1].")

    ks = stats.kstest(array, "uniform")
    cvm = stats.cramervonmises(array, "uniform")

    counts, _ = np.histogram(
        array,
        bins=np.linspace(0.0, 1.0, 11),
    )
    expected = len(array) / 10.0
    chi_square = float(
        np.sum((counts - expected) ** 2 / expected)
    )
    chi_square_p = float(stats.chi2.sf(chi_square, 9))

    return {
        "mean_pit": float(array.mean()),
        "variance_pit": float(array.var(ddof=1)),
        "variance_error_from_uniform": float(
            array.var(ddof=1) - (1.0 / 12.0)
        ),
        "mean_absolute_deviation_from_half": float(
            np.mean(np.abs(array - 0.5))
        ),
        "ks_statistic": float(ks.statistic),
        "ks_nominal_iid_p_value": float(ks.pvalue),
        "cramer_von_mises_statistic": float(cvm.statistic),
        "cramer_von_mises_nominal_iid_p_value": float(
            cvm.pvalue
        ),
        "ten_bin_chi_square": chi_square,
        "ten_bin_nominal_iid_p_value": chi_square_p,
    }


def build_pit_outputs(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    histogram_rows: list[dict[str, Any]] = []

    for model in MODELS:
        model_frame = panel.loc[panel["model"] == model]

        scopes: list[tuple[str, str, pd.DataFrame]] = [
            ("overall", "all", model_frame),
        ]
        for rule in RULE_ORDER:
            scopes.append(
                (
                    "decision_rule",
                    rule,
                    model_frame.loc[
                        model_frame["decision_rule"] == rule
                    ],
                )
            )
        for fold_id, group in model_frame.groupby(
            "fold_id",
            sort=True,
        ):
            scopes.append(
                ("validation_block", str(fold_id), group)
            )

        for scope, scope_value, group in scopes:
            values = group["pit_value"].to_numpy(dtype=float)
            statistics = pit_uniformity_statistics(values)
            summary_rows.append(
                {
                    "model": model,
                    "scope": scope,
                    "scope_value": scope_value,
                    "rows": int(len(group)),
                    "dates": int(group["target_date"].nunique()),
                    **statistics,
                    "p_value_interpretation": (
                        "nominal i.i.d. reference only; rows share "
                        "target dates and may be serially dependent"
                    ),
                }
            )

            counts, edges = np.histogram(
                values,
                bins=np.linspace(0.0, 1.0, 11),
            )
            for index, count in enumerate(counts):
                histogram_rows.append(
                    {
                        "model": model,
                        "scope": scope,
                        "scope_value": scope_value,
                        "bin_number": index + 1,
                        "lower_bound": float(edges[index]),
                        "upper_bound": float(edges[index + 1]),
                        "count": int(count),
                        "proportion": float(count / len(values)),
                        "uniform_reference_proportion": 0.10,
                        "proportion_error": float(
                            count / len(values) - 0.10
                        ),
                    }
                )

    summary = pd.DataFrame(summary_rows)
    histogram = pd.DataFrame(histogram_rows)

    if len(summary) != 18:
        fail(
            f"Expected 18 PIT-summary rows; found {len(summary)}."
        )
    if len(histogram) != 180:
        fail(
            f"Expected 180 PIT-histogram rows; found {len(histogram)}."
        )

    return summary, histogram


def distribution_summary(
    values: np.ndarray,
) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(array.mean()),
        "standard_deviation": float(array.std(ddof=1)),
        "rmse": float(math.sqrt(float(np.mean(array**2)))),
        "median": float(np.median(array)),
        "mean_absolute_value": float(np.mean(np.abs(array))),
        "skewness": float(stats.skew(array, bias=False)),
        "excess_kurtosis": float(
            stats.kurtosis(array, fisher=True, bias=False)
        ),
        "proportion_absolute_above_1": float(
            np.mean(np.abs(array) > 1.0)
        ),
        "proportion_absolute_above_1_645": float(
            np.mean(np.abs(array) > 1.6448536269514722)
        ),
        "proportion_absolute_above_1_96": float(
            np.mean(np.abs(array) > 1.959963984540054)
        ),
        "proportion_absolute_above_2_576": float(
            np.mean(np.abs(array) > 2.5758293035489004)
        ),
    }


def build_sharpness_and_residual_outputs(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sharpness_rows: list[dict[str, Any]] = []
    residual_rows: list[dict[str, Any]] = []

    for model in MODELS:
        model_frame = panel.loc[panel["model"] == model]

        for (
            scope,
            scope_value,
            group,
            average_rules,
        ) in scope_groups(model_frame):
            sharp = date_balanced_values(
                group,
                [
                    "predictive_standard_deviation_c",
                    "q75_c",
                    "q25_c",
                    "q90_c",
                    "q10_c",
                    "q95_c",
                    "q05_c",
                ],
                average_rules=average_rules,
            )
            sharp["width_50_c"] = sharp["q75_c"] - sharp["q25_c"]
            sharp["width_80_c"] = sharp["q90_c"] - sharp["q10_c"]
            sharp["width_90_c"] = sharp["q95_c"] - sharp["q05_c"]

            sharpness_rows.append(
                {
                    "model": model,
                    "scope": scope,
                    "scope_value": scope_value,
                    "rows": int(len(group)),
                    "dates": int(group["target_date"].nunique()),
                    "mean_predictive_standard_deviation_c": float(
                        sharp[
                            "predictive_standard_deviation_c"
                        ].mean()
                    ),
                    "median_predictive_standard_deviation_c": float(
                        sharp[
                            "predictive_standard_deviation_c"
                        ].median()
                    ),
                    "q10_predictive_standard_deviation_c": float(
                        sharp[
                            "predictive_standard_deviation_c"
                        ].quantile(0.10)
                    ),
                    "q90_predictive_standard_deviation_c": float(
                        sharp[
                            "predictive_standard_deviation_c"
                        ].quantile(0.90)
                    ),
                    "mean_central_50_width_c": float(
                        sharp["width_50_c"].mean()
                    ),
                    "mean_central_80_width_c": float(
                        sharp["width_80_c"].mean()
                    ),
                    "mean_central_90_width_c": float(
                        sharp["width_90_c"].mean()
                    ),
                    "aggregation": (
                        "equal target-date weight after averaging "
                        "rules within date"
                        if average_rules
                        else "equal target-date weight"
                    ),
                }
            )

            residual_values = date_balanced_values(
                group,
                ["standardised_residual_error"],
                average_rules=average_rules,
            )["standardised_residual_error"].to_numpy(dtype=float)
            residual_rows.append(
                {
                    "model": model,
                    "scope": scope,
                    "scope_value": scope_value,
                    "rows": int(len(group)),
                    "dates": int(group["target_date"].nunique()),
                    **distribution_summary(residual_values),
                    "aggregation": (
                        "date-mean standardised residual after "
                        "averaging rules"
                        if average_rules
                        else "rule-specific standardised residual"
                    ),
                }
            )

    sharpness = pd.DataFrame(sharpness_rows)
    residual = pd.DataFrame(residual_rows)

    if len(sharpness) != 50 or len(residual) != 50:
        fail(
            "Expected 50 sharpness rows and 50 standardised-residual "
            f"rows; found {len(sharpness)} and {len(residual)}."
        )

    return sharpness, residual


def autocorrelation(
    values: np.ndarray,
    maximum_lag: int,
) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    centered = array - array.mean()
    denominator = float(np.dot(centered, centered))
    if denominator <= 0:
        fail("Autocorrelation is undefined for a constant series.")

    result = np.empty(maximum_lag, dtype=float)
    for lag in range(1, maximum_lag + 1):
        result[lag - 1] = float(
            np.dot(centered[:-lag], centered[lag:])
            / denominator
        )
    return result


def circular_block_bootstrap_acf1(
    values: np.ndarray,
    seed: int,
    transform: str,
) -> tuple[float, float, float]:
    base = np.asarray(values, dtype=float)
    n = len(base)
    if n < 30:
        fail("Block-bootstrap ACF requires at least 30 dates.")

    if transform == "standardised_residual":
        transformed = base
    elif transform == "absolute_standardised_residual":
        transformed = np.abs(base)
    elif transform == "squared_standardised_residual":
        transformed = base**2
    else:
        fail(f"Unknown ACF transform: {transform}")

    observed = float(autocorrelation(transformed, 1)[0])
    rng = np.random.default_rng(seed)
    replicates = np.empty(
        BLOCK_BOOTSTRAP_REPLICATIONS,
        dtype=float,
    )

    block_length = min(BLOCK_BOOTSTRAP_LENGTH, n)
    blocks_needed = math.ceil(n / block_length)
    offsets = np.arange(block_length)

    for replication in range(BLOCK_BOOTSTRAP_REPLICATIONS):
        starts = rng.integers(0, n, size=blocks_needed)
        indices = (
            starts[:, None] + offsets[None, :]
        ) % n
        sample = transformed[indices.ravel()[:n]]
        replicates[replication] = autocorrelation(sample, 1)[0]

    return (
        observed,
        float(np.quantile(replicates, 0.025)),
        float(np.quantile(replicates, 0.975)),
    )


def ljung_box(
    values: np.ndarray,
    maximum_lag: int,
) -> tuple[float, float]:
    array = np.asarray(values, dtype=float)
    n = len(array)
    correlations = autocorrelation(array, maximum_lag)
    lags = np.arange(1, maximum_lag + 1)
    statistic = float(
        n
        * (n + 2)
        * np.sum(correlations**2 / (n - lags))
    )
    p_value = float(
        stats.chi2.sf(statistic, maximum_lag)
    )
    return statistic, p_value


def build_dependence_outputs(
    panel: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    acf_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    correlation_rows: list[dict[str, Any]] = []

    series_types = [
        "standardised_residual",
        "absolute_standardised_residual",
        "squared_standardised_residual",
    ]

    for model in MODELS:
        model_frame = panel.loc[panel["model"] == model]

        scopes: list[
            tuple[str, str, pd.DataFrame, bool]
        ] = [
            ("overall", "all", model_frame, True),
        ]
        for rule in RULE_ORDER:
            scopes.append(
                (
                    "decision_rule",
                    rule,
                    model_frame.loc[
                        model_frame["decision_rule"] == rule
                    ],
                    False,
                )
            )

        for scope, scope_value, group, average_rules in scopes:
            date_frame = date_balanced_values(
                group,
                ["standardised_residual_error"],
                average_rules=average_rules,
            )
            base = date_frame[
                "standardised_residual_error"
            ].to_numpy(dtype=float)

            summary: dict[str, Any] = {
                "model": model,
                "scope": scope,
                "scope_value": scope_value,
                "dates": int(len(base)),
                "block_bootstrap_length_days": (
                    BLOCK_BOOTSTRAP_LENGTH
                ),
                "block_bootstrap_replications": (
                    BLOCK_BOOTSTRAP_REPLICATIONS
                ),
            }

            for series_type in series_types:
                if series_type == "standardised_residual":
                    transformed = base
                elif series_type == (
                    "absolute_standardised_residual"
                ):
                    transformed = np.abs(base)
                else:
                    transformed = base**2

                correlations = autocorrelation(
                    transformed,
                    ACF_LAGS,
                )
                for lag, correlation in enumerate(
                    correlations,
                    start=1,
                ):
                    acf_rows.append(
                        {
                            "model": model,
                            "scope": scope,
                            "scope_value": scope_value,
                            "series": series_type,
                            "lag_days": lag,
                            "autocorrelation": float(correlation),
                            "dates": int(len(base)),
                        }
                    )

                (
                    lag1,
                    lower,
                    upper,
                ) = circular_block_bootstrap_acf1(
                    base,
                    seed=stable_seed(
                        "acf1",
                        model,
                        scope,
                        scope_value,
                        series_type,
                    ),
                    transform=series_type,
                )
                summary[f"{series_type}_lag1"] = lag1
                summary[
                    f"{series_type}_lag1_block_bootstrap_lower_95"
                ] = lower
                summary[
                    f"{series_type}_lag1_block_bootstrap_upper_95"
                ] = upper

                for lag in (7, 14):
                    statistic, p_value = ljung_box(
                        transformed,
                        lag,
                    )
                    summary[
                        f"{series_type}_ljung_box_q{lag}"
                    ] = statistic
                    summary[
                        f"{series_type}_ljung_box_q{lag}_nominal_iid_p_value"
                    ] = p_value

            summary_rows.append(summary)

        pivot = model_frame.pivot(
            index="target_date",
            columns="decision_rule",
            values="standardised_residual_error",
        ).reindex(columns=RULE_ORDER)

        if pivot.isna().any().any() or len(pivot) != 365:
            fail(
                "Cross-rule standardised-residual panel is incomplete."
            )

        for first_index, first in enumerate(RULE_ORDER):
            for second in RULE_ORDER[first_index + 1 :]:
                pearson = stats.pearsonr(
                    pivot[first],
                    pivot[second],
                )
                spearman = stats.spearmanr(
                    pivot[first],
                    pivot[second],
                )
                correlation_rows.append(
                    {
                        "model": model,
                        "first_rule": first,
                        "second_rule": second,
                        "dates": int(len(pivot)),
                        "pearson_correlation": float(
                            pearson.statistic
                        ),
                        "pearson_nominal_iid_p_value": float(
                            pearson.pvalue
                        ),
                        "spearman_correlation": float(
                            spearman.statistic
                        ),
                        "spearman_nominal_iid_p_value": float(
                            spearman.pvalue
                        ),
                        "p_value_interpretation": (
                            "nominal i.i.d. reference only"
                        ),
                    }
                )

    acf = pd.DataFrame(acf_rows)
    summary = pd.DataFrame(summary_rows)
    correlations = pd.DataFrame(correlation_rows)

    if len(acf) != 420:
        fail(f"Expected 420 ACF rows; found {len(acf)}.")
    if len(summary) != 10:
        fail(
            f"Expected 10 dependence-summary rows; found {len(summary)}."
        )
    if len(correlations) != 12:
        fail(
            f"Expected 12 cross-rule correlation rows; "
            f"found {len(correlations)}."
        )

    return acf, summary, correlations


def safe_qcut(
    values: pd.Series,
) -> pd.Series:
    ranked = values.rank(method="first")
    return pd.qcut(
        ranked,
        q=4,
        labels=["Q1", "Q2", "Q3", "Q4"],
    )


def build_heteroskedasticity_quartiles(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    variables = [
        "predictive_standard_deviation_c",
        "temperature_predictive_mean_c",
        "forecast_daily_max_c",
    ]

    for model in MODELS:
        model_frame = panel.loc[panel["model"] == model]

        scopes = [("overall", "all", model_frame)]
        for rule in RULE_ORDER:
            scopes.append(
                (
                    "decision_rule",
                    rule,
                    model_frame.loc[
                        model_frame["decision_rule"] == rule
                    ],
                )
            )

        for scope, scope_value, group in scopes:
            for variable in variables:
                working = group.copy()
                working["quartile"] = safe_qcut(
                    working[variable]
                )
                working["squared_standardised_residual"] = (
                    working["standardised_residual_error"] ** 2
                )
                working["absolute_standardised_residual"] = np.abs(
                    working["standardised_residual_error"]
                )
                working["central_90_covered"] = (
                    (working["hko_daily_max_c"] >= working["q05_c"])
                    & (working["hko_daily_max_c"] <= working["q95_c"])
                ).astype(float)

                summary = (
                    working.groupby(
                        "quartile",
                        observed=True,
                        as_index=False,
                    )
                    .agg(
                        rows=("target_date", "size"),
                        dates=("target_date", "nunique"),
                        variable_minimum=(variable, "min"),
                        variable_maximum=(variable, "max"),
                        variable_mean=(variable, "mean"),
                        mean_squared_standardised_residual=(
                            "squared_standardised_residual",
                            "mean",
                        ),
                        mean_absolute_standardised_residual=(
                            "absolute_standardised_residual",
                            "mean",
                        ),
                        central_90_empirical_coverage=(
                            "central_90_covered",
                            "mean",
                        ),
                        mean_crps_c=("crps_c", "mean"),
                    )
                )
                for _, row in summary.iterrows():
                    rows.append(
                        {
                            "model": model,
                            "scope": scope,
                            "scope_value": scope_value,
                            "stratification_variable": variable,
                            **row.to_dict(),
                        }
                    )

    result = pd.DataFrame(rows)
    if len(result) != 120:
        fail(
            "Expected 120 heteroskedasticity-quartile rows; "
            f"found {len(result)}."
        )
    return result


def standardise(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    standard_deviation = float(array.std(ddof=0))
    if standard_deviation <= 0:
        fail("Cannot standardise a constant auxiliary-regression variable.")
    return (array - array.mean()) / standard_deviation


def cluster_robust_ols(
    y: np.ndarray,
    x: np.ndarray,
    clusters: np.ndarray,
) -> dict[str, Any]:
    y_array = np.asarray(y, dtype=float)
    x_array = np.asarray(x, dtype=float)
    cluster_array = np.asarray(clusters)

    n, k = x_array.shape
    if len(y_array) != n or len(cluster_array) != n:
        fail("Auxiliary-regression dimensions do not match.")
    if np.linalg.matrix_rank(x_array) < k:
        fail("Auxiliary-regression design matrix is rank deficient.")

    xtx_inverse = np.linalg.inv(x_array.T @ x_array)
    beta = xtx_inverse @ x_array.T @ y_array
    fitted = x_array @ beta
    residual = y_array - fitted

    unique_clusters = pd.unique(cluster_array)
    g = len(unique_clusters)
    if g <= k:
        fail("Too few date clusters for cluster-robust inference.")

    meat = np.zeros((k, k), dtype=float)
    for cluster in unique_clusters:
        mask = cluster_array == cluster
        score = x_array[mask].T @ residual[mask]
        meat += np.outer(score, score)

    correction = (g / (g - 1.0)) * ((n - 1.0) / (n - k))
    covariance = correction * xtx_inverse @ meat @ xtx_inverse
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

    total_sum_squares = float(
        np.sum((y_array - y_array.mean()) ** 2)
    )
    residual_sum_squares = float(np.sum(residual**2))
    r_squared = (
        1.0 - residual_sum_squares / total_sum_squares
        if total_sum_squares > 0
        else math.nan
    )

    restriction = np.eye(k)[1:, :]
    restricted_beta = restriction @ beta
    restricted_covariance = restriction @ covariance @ restriction.T
    wald = float(
        restricted_beta.T
        @ np.linalg.pinv(restricted_covariance)
        @ restricted_beta
    )
    degrees_freedom = k - 1
    wald_p = float(
        stats.chi2.sf(wald, degrees_freedom)
    )

    return {
        "beta": beta,
        "standard_errors": standard_errors,
        "z_statistics": z_statistics,
        "p_values": p_values,
        "fitted": fitted,
        "residual": residual,
        "covariance": covariance,
        "n": n,
        "k": k,
        "clusters": g,
        "r_squared": r_squared,
        "joint_wald_statistic": wald,
        "joint_wald_degrees_freedom": degrees_freedom,
        "joint_wald_p_value": wald_p,
    }


def build_variance_regression(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    coefficient_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for model in MODELS:
        group = (
            panel.loc[panel["model"] == model]
            .sort_values(
                ["target_date", "decision_rule"],
                kind="stable",
            )
            .copy()
        )
        group["time_years"] = (
            (
                group["target_date"]
                - group["target_date"].min()
            ).dt.days
            / 365.2425
        )
        day_of_year = group["target_date"].dt.dayofyear.astype(float)
        seasonal_position = (day_of_year - 1.0) / 365.2425
        group["seasonal_sin"] = np.sin(
            2.0 * np.pi * seasonal_position
        )
        group["seasonal_cos"] = np.cos(
            2.0 * np.pi * seasonal_position
        )

        predictive_mean_z = standardise(
            group["temperature_predictive_mean_c"].to_numpy(
                dtype=float
            )
        )
        predictive_std_z = standardise(
            group["predictive_standard_deviation_c"].to_numpy(
                dtype=float
            )
        )
        time_z = standardise(
            group["time_years"].to_numpy(dtype=float)
        )

        names = [
            "intercept",
            "predictive_mean_z",
            "predictive_mean_z_squared",
            "predictive_std_z",
            "predictive_std_z_squared",
            "time_z",
            "seasonal_sin",
            "seasonal_cos",
            "rule_12h_prior",
            "rule_6h_prior",
            "rule_event_day_open",
        ]

        x = np.column_stack(
            [
                np.ones(len(group)),
                predictive_mean_z,
                predictive_mean_z**2,
                predictive_std_z,
                predictive_std_z**2,
                time_z,
                group["seasonal_sin"].to_numpy(dtype=float),
                group["seasonal_cos"].to_numpy(dtype=float),
                (
                    group["decision_rule"] == "12h_prior"
                ).to_numpy(dtype=float),
                (
                    group["decision_rule"] == "6h_prior"
                ).to_numpy(dtype=float),
                (
                    group["decision_rule"] == "event_day_open"
                ).to_numpy(dtype=float),
            ]
        )
        y = (
            group["standardised_residual_error"].to_numpy(
                dtype=float
            )
            ** 2
        )

        fit = cluster_robust_ols(
            y,
            x,
            clusters=group["target_date"].to_numpy(),
        )

        for index, name in enumerate(names):
            coefficient_rows.append(
                {
                    "model": model,
                    "term": name,
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
                    "response": "squared_standardised_residual",
                    "reference_rule": "24h_prior",
                    "rows": int(fit["n"]),
                    "date_clusters": int(fit["clusters"]),
                }
            )

        summary_rows.append(
            {
                "model": model,
                "response": "squared_standardised_residual",
                "rows": int(fit["n"]),
                "date_clusters": int(fit["clusters"]),
                "parameters": int(fit["k"]),
                "r_squared": float(fit["r_squared"]),
                "joint_non_intercept_wald_statistic": float(
                    fit["joint_wald_statistic"]
                ),
                "joint_non_intercept_degrees_freedom": int(
                    fit["joint_wald_degrees_freedom"]
                ),
                "joint_non_intercept_cluster_robust_p_value": float(
                    fit["joint_wald_p_value"]
                ),
                "inference": (
                    "date-cluster-robust asymptotic normal and "
                    "chi-square reference"
                ),
            }
        )

    coefficients = pd.DataFrame(coefficient_rows)
    summary = pd.DataFrame(summary_rows)

    if len(coefficients) != 22:
        fail(
            f"Expected 22 variance-regression coefficients; "
            f"found {len(coefficients)}."
        )
    if len(summary) != 2:
        fail(
            f"Expected two variance-regression summaries; "
            f"found {len(summary)}."
        )

    return coefficients, summary


def create_figures(
    quantile_curve: pd.DataFrame,
    coverage: pd.DataFrame,
    pit_histogram: pd.DataFrame,
    acf: pd.DataFrame,
    quartiles: pd.DataFrame,
) -> list[Path]:
    FIG.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    overall_curve = quantile_curve.loc[
        quantile_curve["scope"] == "overall"
    ]
    figure, axis = plt.subplots(figsize=(7.0, 6.0))
    axis.plot([0, 1], [0, 1], linestyle="--", label="Perfect calibration")
    for model in MODELS:
        group = overall_curve.loc[
            overall_curve["model"] == model
        ].sort_values("nominal_probability")
        axis.plot(
            group["nominal_probability"],
            group["empirical_probability"],
            label=MODEL_LABELS[model],
        )
    axis.set_xlabel("Nominal predictive quantile")
    axis.set_ylabel("Empirical proportion below quantile")
    axis.set_title("Overall predictive-quantile calibration")
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase19_quantile_calibration.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    overall_coverage = coverage.loc[
        coverage["scope"] == "overall"
    ]
    figure, axis = plt.subplots(figsize=(7.5, 5.0))
    for model in MODELS:
        group = overall_coverage.loc[
            overall_coverage["model"] == model
        ].sort_values("nominal_coverage")
        axis.plot(
            100 * group["nominal_coverage"],
            100 * group["coverage_error"],
            marker="o",
            label=MODEL_LABELS[model],
        )
    axis.axhline(0.0, linestyle="--")
    axis.set_xlabel("Nominal central interval coverage (%)")
    axis.set_ylabel("Empirical minus nominal coverage (percentage points)")
    axis.set_title("Central-interval calibration")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase19_central_coverage_errors.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    overall_histogram = pit_histogram.loc[
        pit_histogram["scope"] == "overall"
    ].copy()
    centres = (
        overall_histogram["lower_bound"]
        + overall_histogram["upper_bound"]
    ) / 2.0
    width = 0.035
    figure, axis = plt.subplots(figsize=(8.0, 5.0))
    for offset, model in zip((-width / 2.0, width / 2.0), MODELS):
        group = overall_histogram.loc[
            overall_histogram["model"] == model
        ].sort_values("bin_number")
        group_centres = (
            group["lower_bound"].to_numpy(dtype=float)
            + group["upper_bound"].to_numpy(dtype=float)
        ) / 2.0
        axis.bar(
            group_centres + offset,
            group["proportion"].to_numpy(dtype=float),
            width=width,
            alpha=0.75,
            label=MODEL_LABELS[model],
        )
    axis.axhline(0.10, linestyle="--", label="Uniform reference")
    axis.set_xlabel("PIT bin")
    axis.set_ylabel("Proportion")
    axis.set_title("Overall probability integral transform histogram")
    axis.set_xlim(0, 1)
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase19_pit_histogram.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    overall_acf = acf.loc[
        (acf["scope"] == "overall")
        & (acf["series"] == "standardised_residual")
    ]
    figure, axis = plt.subplots(figsize=(8.0, 5.0))
    for model in MODELS:
        group = overall_acf.loc[
            overall_acf["model"] == model
        ].sort_values("lag_days")
        axis.plot(
            group["lag_days"],
            group["autocorrelation"],
            marker="o",
            label=MODEL_LABELS[model],
        )
    axis.axhline(0.0, linestyle="--")
    axis.set_xlabel("Lag (days)")
    axis.set_ylabel("Autocorrelation")
    axis.set_title("Date-averaged standardised-residual dependence")
    axis.set_xticks(range(1, ACF_LAGS + 1))
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase19_standardised_residual_acf.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    squared_acf = acf.loc[
        (acf["scope"] == "overall")
        & (acf["series"] == "squared_standardised_residual")
    ]
    figure, axis = plt.subplots(figsize=(8.0, 5.0))
    for model in MODELS:
        group = squared_acf.loc[
            squared_acf["model"] == model
        ].sort_values("lag_days")
        axis.plot(
            group["lag_days"],
            group["autocorrelation"],
            marker="o",
            label=MODEL_LABELS[model],
        )
    axis.axhline(0.0, linestyle="--")
    axis.set_xlabel("Lag (days)")
    axis.set_ylabel("Autocorrelation")
    axis.set_title("Date-averaged squared-standardised-residual dependence")
    axis.set_xticks(range(1, ACF_LAGS + 1))
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase19_squared_standardised_residual_acf.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    overall_quartiles = quartiles.loc[
        (quartiles["scope"] == "overall")
        & (
            quartiles["stratification_variable"]
            == "predictive_standard_deviation_c"
        )
    ]
    figure, axis = plt.subplots(figsize=(8.0, 5.0))
    positions = np.arange(4)
    width = 0.35
    for offset, model in zip((-width / 2.0, width / 2.0), MODELS):
        group = overall_quartiles.loc[
            overall_quartiles["model"] == model
        ].copy()
        group["quartile_order"] = group["quartile"].map(
            {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
        )
        group = group.sort_values("quartile_order")
        axis.bar(
            positions + offset,
            group[
                "mean_squared_standardised_residual"
            ].to_numpy(dtype=float),
            width=width,
            label=MODEL_LABELS[model],
        )
    axis.axhline(1.0, linestyle="--", label="Calibrated reference")
    axis.set_xticks(positions)
    axis.set_xticklabels(["Q1", "Q2", "Q3", "Q4"])
    axis.set_xlabel("Predictive-standard-deviation quartile")
    axis.set_ylabel("Mean squared standardised residual")
    axis.set_title("Residual scale by predictive-uncertainty quartile")
    axis.legend()
    figure.tight_layout()
    for suffix in ("png", "pdf"):
        path = FIG / f"phase19_variance_by_sharpness_quartile.{suffix}"
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
            fail(f"Required Phase 19 input is missing: {rel(path)}")

    phase15_spec = json.loads(
        PHASE15_SPEC_PATH.read_text(encoding="utf-8")
    )
    phase18_spec = json.loads(
        PHASE18_SPEC_PATH.read_text(encoding="utf-8")
    )
    if phase15_spec.get("status") != "PASSED":
        fail("Phase 15 specification is not certified as PASSED.")
    if phase18_spec.get("status") != "PASSED":
        fail("Phase 18 specification is not certified as PASSED.")

    raw = pd.read_csv(VALIDATION_PATH)
    (
        columns,
        quantile_columns,
        coverage_columns,
    ) = discover_columns(raw)

    print(
        "PHASE19_COLUMN_MAP="
        + json.dumps(columns, sort_keys=True)
    )
    print(
        "PHASE19_QUANTILE_COLUMNS="
        + json.dumps(
            {
                str(probability): column
                for probability, column in sorted(
                    quantile_columns.items()
                )
            },
            sort_keys=True,
        )
    )
    print(
        "PHASE19_STORED_COVERAGE_COLUMNS="
        + json.dumps(
            {
                str(level): column
                for level, column in sorted(
                    coverage_columns.items()
                )
            },
            sort_keys=True,
        )
    )

    panel = prepare_panel(
        raw,
        columns,
        quantile_columns,
    )
    reconciliation = reconcile_stored_diagnostics(
        raw,
        panel,
        columns,
        quantile_columns,
        coverage_columns,
    )

    coverage = build_coverage_outputs(panel)
    quantile_curve, calibration_summary = (
        build_quantile_calibration(panel)
    )
    pit_summary, pit_histogram = build_pit_outputs(panel)
    sharpness, residual_summary = (
        build_sharpness_and_residual_outputs(panel)
    )
    acf, dependence_summary, cross_rule_correlations = (
        build_dependence_outputs(panel)
    )
    heteroskedasticity_quartiles = (
        build_heteroskedasticity_quartiles(panel)
    )
    variance_coefficients, variance_summary = (
        build_variance_regression(panel)
    )

    figure_paths = create_figures(
        quantile_curve,
        coverage,
        pit_histogram,
        acf,
        heteroskedasticity_quartiles,
    )

    gap_updates = pd.DataFrame(
        [
            {
                "gap_id": "G10",
                "gap": "Predictive calibration and sharpness",
                "phase_closed": 19,
                "status": "CLOSED",
                "evidence": (
                    "phase19_coverage_summary.csv|"
                    "phase19_quantile_calibration.csv|"
                    "phase19_quantile_calibration_summary.csv|"
                    "phase19_pit_summary.csv|"
                    "phase19_pit_histogram.csv|"
                    "phase19_sharpness_summary.csv|"
                    "phase19_standardised_residual_summary.csv"
                ),
            },
            {
                "gap_id": "G11",
                "gap": "Residual dependence and heteroskedasticity",
                "phase_closed": 19,
                "status": "CLOSED",
                "evidence": (
                    "phase19_autocorrelation.csv|"
                    "phase19_dependence_summary.csv|"
                    "phase19_cross_rule_residual_correlations.csv|"
                    "phase19_heteroskedasticity_quartiles.csv|"
                    "phase19_variance_regression_coefficients.csv|"
                    "phase19_variance_regression_summary.csv"
                ),
            },
        ]
    )

    write_csv(
        OUT / "phase19_reconciliation_checks.csv",
        reconciliation,
    )
    write_csv(
        OUT / "phase19_coverage_summary.csv",
        coverage,
    )
    write_csv(
        OUT / "phase19_quantile_calibration.csv",
        quantile_curve,
    )
    write_csv(
        OUT / "phase19_quantile_calibration_summary.csv",
        calibration_summary,
    )
    write_csv(
        OUT / "phase19_pit_summary.csv",
        pit_summary,
    )
    write_csv(
        OUT / "phase19_pit_histogram.csv",
        pit_histogram,
    )
    write_csv(
        OUT / "phase19_sharpness_summary.csv",
        sharpness,
    )
    write_csv(
        OUT / "phase19_standardised_residual_summary.csv",
        residual_summary,
    )
    write_csv(
        OUT / "phase19_autocorrelation.csv",
        acf,
    )
    write_csv(
        OUT / "phase19_dependence_summary.csv",
        dependence_summary,
    )
    write_csv(
        OUT / "phase19_cross_rule_residual_correlations.csv",
        cross_rule_correlations,
    )
    write_csv(
        OUT / "phase19_heteroskedasticity_quartiles.csv",
        heteroskedasticity_quartiles,
    )
    write_csv(
        OUT / "phase19_variance_regression_coefficients.csv",
        variance_coefficients,
    )
    write_csv(
        OUT / "phase19_variance_regression_summary.csv",
        variance_summary,
    )
    write_csv(
        OUT / "phase19_gap_updates.csv",
        gap_updates,
    )

    overall_coverage = coverage.loc[
        coverage["scope"] == "overall"
    ].copy()
    overall_calibration = calibration_summary.loc[
        calibration_summary["scope"] == "overall"
    ].copy()
    overall_pit = pit_summary.loc[
        pit_summary["scope"] == "overall"
    ].copy()
    overall_sharpness = sharpness.loc[
        sharpness["scope"] == "overall"
    ].copy()
    overall_residual = residual_summary.loc[
        residual_summary["scope"] == "overall"
    ].copy()
    overall_dependence = dependence_summary.loc[
        dependence_summary["scope"] == "overall"
    ].copy()

    spec = {
        "phase": 19,
        "name": (
            "Predictive calibration, sharpness, residual dependence "
            "and heteroskedasticity diagnostics"
        ),
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "git_branch": git("branch", "--show-current"),
        "git_commit_before_phase19": git("rev-parse", "HEAD"),
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
        "support": {
            "validation_rows": int(len(panel)),
            "validation_dates": int(
                panel["target_date"].nunique()
            ),
            "decision_rules": int(
                panel["decision_rule"].nunique()
            ),
            "models": MODELS,
            "validation_blocks": int(
                panel["fold_id"].nunique()
            ),
            "date_range": [
                str(panel["target_date"].min().date()),
                str(panel["target_date"].max().date()),
            ],
        },
        "calibration_design": {
            "central_interval_levels": CENTRAL_LEVELS,
            "predictive_quantiles": [
                integer / 100.0
                for integer in range(1, 100)
            ],
            "bootstrap_replications": BOOTSTRAP_REPLICATIONS,
            "bootstrap_unit": "target_date",
            "pit_reference": (
                "nominal i.i.d. uniform reference; p-values are "
                "reported as descriptive diagnostics"
            ),
        },
        "dependence_design": {
            "maximum_acf_lag_days": ACF_LAGS,
            "series": [
                "standardised_residual",
                "absolute_standardised_residual",
                "squared_standardised_residual",
            ],
            "circular_block_bootstrap": {
                "block_length_days": BLOCK_BOOTSTRAP_LENGTH,
                "replications": BLOCK_BOOTSTRAP_REPLICATIONS,
            },
            "variance_regression": {
                "response": "squared_standardised_residual",
                "covariance": "target-date cluster robust",
                "reference_rule": "24h_prior",
            },
        },
        "headline_outputs": {
            "overall_coverage": overall_coverage.to_dict(
                orient="records"
            ),
            "overall_quantile_calibration": (
                overall_calibration.to_dict(orient="records")
            ),
            "overall_pit": overall_pit.to_dict(
                orient="records"
            ),
            "overall_sharpness": overall_sharpness.to_dict(
                orient="records"
            ),
            "overall_standardised_residuals": (
                overall_residual.to_dict(orient="records")
            ),
            "overall_dependence": (
                overall_dependence.to_dict(orient="records")
            ),
            "variance_regression": variance_summary.to_dict(
                orient="records"
            ),
        },
        "figures": [rel(path) for path in figure_paths],
        "closed_gaps": ["G10", "G11"],
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
        CONFIG / "phase19_predictive_diagnostics_spec.json",
        spec,
    )

    coverage_table = overall_coverage[
        [
            "model",
            "nominal_coverage",
            "empirical_coverage",
            "coverage_error",
            "bootstrap_lower_95_coverage_error",
            "bootstrap_upper_95_coverage_error",
            "mean_interval_width_c",
        ]
    ].copy()
    coverage_table["model"] = coverage_table["model"].map(
        MODEL_LABELS
    )

    calibration_table = overall_calibration[
        [
            "model",
            "integrated_absolute_calibration_error",
            "root_mean_squared_calibration_error",
            "maximum_absolute_calibration_error",
            "mean_signed_calibration_error",
        ]
    ].copy()
    calibration_table["model"] = calibration_table["model"].map(
        MODEL_LABELS
    )

    residual_table = overall_residual[
        [
            "model",
            "mean",
            "standard_deviation",
            "rmse",
            "skewness",
            "excess_kurtosis",
        ]
    ].copy()
    residual_table["model"] = residual_table["model"].map(
        MODEL_LABELS
    )

    dependence_table = overall_dependence[
        [
            "model",
            "standardised_residual_lag1",
            "standardised_residual_lag1_block_bootstrap_lower_95",
            "standardised_residual_lag1_block_bootstrap_upper_95",
            "squared_standardised_residual_lag1",
            "squared_standardised_residual_lag1_block_bootstrap_lower_95",
            "squared_standardised_residual_lag1_block_bootstrap_upper_95",
        ]
    ].copy()
    dependence_table["model"] = dependence_table["model"].map(
        MODEL_LABELS
    )

    variance_table = variance_summary[
        [
            "model",
            "r_squared",
            "joint_non_intercept_wald_statistic",
            "joint_non_intercept_degrees_freedom",
            "joint_non_intercept_cluster_robust_p_value",
        ]
    ].copy()
    variance_table["model"] = variance_table["model"].map(
        MODEL_LABELS
    )

    report_lines = [
        "# Phase 19 Predictive Diagnostics and Residual Structure",
        "",
        "## Status",
        "",
        "PASSED",
        "",
        "## Purpose",
        "",
        "Phase 18 showed that the Matérn-3/2 GP has lower aggregate CRPS than the static Gaussian benchmark, but its advantage varies across chronological blocks and its fitted hyperparameters move across folds. Phase 19 therefore evaluates whether the predictive distributions are calibrated and sharp, and whether standardised residuals retain temporal, cross-rule or conditional variance structure.",
        "",
        "## Certified support",
        "",
        "- Validation dates: 365 consecutive days.",
        "- Decision rules: 4.",
        "- GP families: RBF and Matérn-3/2.",
        "- Validation rows: 2,920.",
        "- Chronological validation blocks: 4.",
        "- Every date-rule key contains both GP families.",
        "- June outcomes and market prices are absent from every diagnostic.",
        "",
        "## Code-to-output reconciliation",
        "",
        f"- Reconciliation checks passed: {len(reconciliation)}.",
        f"- Maximum Gaussian quantile reconstruction error: {float(reconciliation.loc[reconciliation['check'] == 'Gaussian quantile reconstruction', 'maximum_absolute_error'].iloc[0]):.3e}.",
        "- Stored predictive quantiles, PIT values, standardised residuals and available central-coverage indicators were independently reconstructed from the predictive mean and standard deviation.",
        "",
        "## Overall central-interval calibration",
        "",
    ]
    report_lines.extend(
        markdown_table(
            coverage_table,
            [
                "model",
                "nominal_coverage",
                "empirical_coverage",
                "coverage_error",
                "bootstrap_lower_95_coverage_error",
                "bootstrap_upper_95_coverage_error",
                "mean_interval_width_c",
            ],
            [
                "Model",
                "Nominal",
                "Empirical",
                "Error",
                "95% lower",
                "95% upper",
                "Mean width (°C)",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            "Coverage uncertainty intervals resample complete target dates 10,000 times. Negative coverage error means undercoverage.",
            "",
            "## Overall quantile calibration",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            calibration_table,
            [
                "model",
                "integrated_absolute_calibration_error",
                "root_mean_squared_calibration_error",
                "maximum_absolute_calibration_error",
                "mean_signed_calibration_error",
            ],
            [
                "Model",
                "Integrated absolute error",
                "RMSE",
                "Maximum absolute error",
                "Mean signed error",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            "The complete 1% to 99% reliability curves are stored in `phase19_quantile_calibration.csv`. Rule-specific curves are retained rather than inferred from the aggregate result.",
            "",
            "## Probability integral transform diagnostics",
            "",
        ]
    )

    pit_table = overall_pit[
        [
            "model",
            "mean_pit",
            "variance_pit",
            "ks_statistic",
            "cramer_von_mises_statistic",
            "ten_bin_chi_square",
        ]
    ].copy()
    pit_table["model"] = pit_table["model"].map(MODEL_LABELS)
    report_lines.extend(
        markdown_table(
            pit_table,
            [
                "model",
                "mean_pit",
                "variance_pit",
                "ks_statistic",
                "cramer_von_mises_statistic",
                "ten_bin_chi_square",
            ],
            [
                "Model",
                "Mean PIT",
                "PIT variance",
                "KS statistic",
                "CvM statistic",
                "10-bin chi-square",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            "For a calibrated continuous predictive distribution the PIT reference mean is 0.5 and the reference variance is 1/12. The reported goodness-of-fit p-values use nominal independent-row reference distributions and are not interpreted as definitive tests because rules share target dates and the dates may be serially dependent.",
            "",
            "## Standardised residual shape",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            residual_table,
            [
                "model",
                "mean",
                "standard_deviation",
                "rmse",
                "skewness",
                "excess_kurtosis",
            ],
            [
                "Model",
                "Mean",
                "SD",
                "RMSE",
                "Skewness",
                "Excess kurtosis",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            "A correctly centred and scaled Gaussian predictive distribution has standardised-residual mean zero, variance one and approximately Gaussian tail shape. Rule and block decompositions are stored separately.",
            "",
            "## Residual dependence",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            dependence_table,
            [
                "model",
                "standardised_residual_lag1",
                "standardised_residual_lag1_block_bootstrap_lower_95",
                "standardised_residual_lag1_block_bootstrap_upper_95",
                "squared_standardised_residual_lag1",
                "squared_standardised_residual_lag1_block_bootstrap_lower_95",
                "squared_standardised_residual_lag1_block_bootstrap_upper_95",
            ],
            [
                "Model",
                "Residual lag-1",
                "95% lower",
                "95% upper",
                "Squared-residual lag-1",
                "95% lower",
                "95% upper",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            f"Lag-one uncertainty uses a circular moving-block bootstrap with {BLOCK_BOOTSTRAP_LENGTH}-day blocks and {BLOCK_BOOTSTRAP_REPLICATIONS:,} replications. Full residual, absolute-residual and squared-residual autocorrelation functions through lag {ACF_LAGS} are stored in `phase19_autocorrelation.csv`.",
            "",
            "## Remaining conditional variance structure",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            variance_table,
            [
                "model",
                "r_squared",
                "joint_non_intercept_wald_statistic",
                "joint_non_intercept_degrees_freedom",
                "joint_non_intercept_cluster_robust_p_value",
            ],
            [
                "Model",
                "Auxiliary R²",
                "Joint Wald",
                "df",
                "Cluster-robust p-value",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            "The auxiliary regression uses squared standardised residuals as the response. Covariates comprise standardised predictive mean and its square, standardised predictive standard deviation and its square, calendar time, seasonal sine and cosine terms, and decision-rule indicators. Covariance estimates cluster observations by target date. This tests for remaining conditional second-moment structure after dividing errors by the GP predictive standard deviation.",
            "",
            "Quartile diagnostics in `phase19_heteroskedasticity_quartiles.csv` report residual scale and 90% coverage across predictive-uncertainty, predictive-mean and deterministic-forecast strata.",
            "",
            "## Interpretation",
            "",
            "Calibration and sharpness must be interpreted jointly. Narrower predictive distributions are not preferable when they materially undercover realised temperatures. Likewise, an aggregate CRPS advantage does not establish that the standardised residual sequence is independent or conditionally homoskedastic.",
            "",
            "Phase 19 therefore separates four questions: whether nominal probabilities agree with empirical frequencies; how concentrated the predictive distributions are; whether residual location and scale resemble the Gaussian reference; and whether residual or squared-residual structure remains across dates, rules and forecast regimes.",
            "",
            "## Closed Phase 14 gaps",
            "",
            "- G10: predictive calibration and sharpness.",
            "- G11: residual dependence and heteroskedasticity.",
            "",
            "## Evidential boundary",
            "",
            "Phase 19 does not refit or select a GP, alter any Phase 7 prediction, use June outcomes, use market prices or impute missing forecasts. Bootstrap intervals resample target dates, and lag-one dependence intervals use seven-day moving blocks. Nominal PIT and Ljung-Box p-values are retained only as familiar descriptive references; substantive conclusions should rely on effect sizes, block-bootstrap intervals, rule and block decompositions, and the date-cluster-robust auxiliary variance analysis.",
            "",
        ]
    )

    (OUT / "phase19_predictive_diagnostics_report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("PHASE19_STATUS=PASSED")
    print(f"PHASE19_VALIDATION_ROWS={len(panel)}")
    print(
        f"PHASE19_VALIDATION_DATES="
        f"{panel['target_date'].nunique()}"
    )
    print(f"PHASE19_COVERAGE_ROWS={len(coverage)}")
    print(
        f"PHASE19_QUANTILE_CALIBRATION_ROWS="
        f"{len(quantile_curve)}"
    )
    print(f"PHASE19_ACF_ROWS={len(acf)}")
    print(
        f"PHASE19_VARIANCE_REGRESSION_COEFFICIENTS="
        f"{len(variance_coefficients)}"
    )


if __name__ == "__main__":
    main()
