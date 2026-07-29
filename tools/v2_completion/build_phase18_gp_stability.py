from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import sklearn

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/v2_completion"
FIG = OUT / "phase18_figures"
CONFIG = ROOT / "config/v2_completion"

PREDICTIONS_PATH = (
    ROOT
    / "data/processed/v2_completion/"
    / "phase16_chronological_raw_static_predictions.csv"
)
FOLD_REGISTRY_PATH = (
    ROOT
    / "outputs/v2_completion/"
    / "phase15_fold_model_registry.csv"
)
FULL_REGISTRY_PATH = (
    ROOT
    / "outputs/v2_completion/"
    / "phase15_full_fit_model_registry.csv"
)
PHASE15_SPEC_PATH = (
    ROOT
    / "config/v2_completion/"
    / "phase15_gp_implementation_spec.json"
)
PHASE16_SPEC_PATH = (
    ROOT
    / "config/v2_completion/"
    / "phase16_static_benchmark_spec.json"
)
PHASE17_SPEC_PATH = (
    ROOT
    / "config/v2_completion/"
    / "phase17_error_missing_support_spec.json"
)
ORIGINAL_GP_SOURCE_PATH = (
    ROOT
    / "tools/v2/fit_gp_validation_distributions.py"
)
CERTIFIED_GP_VALIDATION_PATH = (
    ROOT
    / "outputs/v2/diagnostics/07_gp_validation_predictions.csv"
)
FEATURE_PANEL_PATH = (
    ROOT
    / "outputs/v2/diagnostics/06_gp_fold_matrix_panel.csv"
)

REQUIRED_PATHS = [
    PREDICTIONS_PATH,
    FOLD_REGISTRY_PATH,
    FULL_REGISTRY_PATH,
    PHASE15_SPEC_PATH,
    PHASE16_SPEC_PATH,
    PHASE17_SPEC_PATH,
    ORIGINAL_GP_SOURCE_PATH,
    CERTIFIED_GP_VALIDATION_PATH,
    FEATURE_PANEL_PATH,
]

MODELS = ["raw_point", "static_gaussian", "rbf", "matern32"]
MODEL_LABELS = {
    "raw_point": "Raw point",
    "static_gaussian": "Static Gaussian",
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
COMPARISONS = [
    ("static_gaussian", "raw_point", "static_minus_raw"),
    ("rbf", "static_gaussian", "rbf_minus_static"),
    ("matern32", "static_gaussian", "matern32_minus_static"),
    ("matern32", "rbf", "matern32_minus_rbf"),
]
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
    if "static" in compact:
        return "static_gaussian"
    if "raw" in compact or "point" in compact:
        return "raw_point"
    return text


def discover_prediction_columns(frame: pd.DataFrame) -> dict[str, str]:
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
            exact=["fold_id", "validation_block", "block_id", "fold_number"],
        ),
        "fold_number": find_column(
            columns,
            exact=["fold_number"],
        ),
        "crps": find_column(
            columns,
            exact=["crps_c", "continuous_crps_c"],
            contains_all=["crps"],
            exclude=["legacy"],
        ),
        "absolute_error": find_column(
            columns,
            exact=["absolute_temperature_error_c"],
            contains_all=["absolute", "temperature", "error"],
        ),
    }
    required = ["date", "rule", "model", "fold", "crps", "absolute_error"]
    missing = [key for key in required if not mapping[key]]
    if missing:
        fail(
            f"Could not identify Phase 16 prediction columns {missing}. "
            f"Available columns: {columns}"
        )
    return {
        key: str(value)
        for key, value in mapping.items()
        if value is not None
    }


def bootstrap_mean_interval(
    values: np.ndarray,
    seed: int,
    replications: int = BOOTSTRAP_REPLICATIONS,
) -> tuple[float, float, float, float]:
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
        float(np.mean(estimates < 0.0)),
    )


def prepare_predictions(
    raw: pd.DataFrame,
    columns: dict[str, str],
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "target_date": pd.to_datetime(
                raw[columns["date"]],
                errors="raise",
            ).dt.normalize(),
            "decision_rule": raw[columns["rule"]].map(normalise_rule),
            "model": raw[columns["model"]].map(normalise_model),
            "fold_id": raw[columns["fold"]],
            "fold_number": (
                raw[columns["fold_number"]]
                if columns.get("fold_number")
                else raw[columns["fold"]]
            ),
            "crps_c": pd.to_numeric(
                raw[columns["crps"]],
                errors="raise",
            ),
            "absolute_temperature_error_c": pd.to_numeric(
                raw[columns["absolute_error"]],
                errors="raise",
            ),
        }
    )

    if len(frame) != 5840:
        fail(f"Expected 5,840 Phase 16 model rows; found {len(frame)}.")
    if frame["target_date"].nunique() != 365:
        fail("Phase 16 predictions do not contain 365 validation dates.")
    if frame["decision_rule"].nunique() != 4:
        fail("Phase 16 predictions do not contain four decision rules.")
    if set(frame["decision_rule"]) != set(RULE_ORDER):
        fail("Phase 16 decision-rule labels do not match the certified four rules.")
    if set(frame["model"]) != set(MODELS):
        fail(
            "Phase 16 model labels do not match raw, static, RBF and Matérn."
        )
    if frame["fold_id"].nunique() != 4:
        fail("Phase 16 predictions do not contain four validation blocks.")
    if frame.duplicated(
        ["target_date", "decision_rule", "model"]
    ).any():
        fail("Phase 16 predictions contain duplicate date-rule-model keys.")
    counts = frame.groupby(
        ["target_date", "decision_rule"],
        sort=False,
    )["model"].nunique()
    if not (counts == 4).all():
        fail("At least one validation date-rule key does not contain all four models.")
    if (frame["crps_c"] < 0).any():
        fail("CRPS must be non-negative.")
    return frame


def score_table(
    frame: pd.DataFrame,
    group_columns: list[str],
    date_balanced: bool,
) -> pd.DataFrame:
    working = frame.copy()

    if date_balanced:
        # First average the four rule-specific losses within each target date.
        # The decision_rule column is intentionally collapsed here, so retain
        # its within-date count explicitly and aggregate that count below.
        date_groups = group_columns + ["target_date"]
        working = (
            working.groupby(date_groups, as_index=False)
            .agg(
                crps_c=("crps_c", "mean"),
                absolute_temperature_error_c=(
                    "absolute_temperature_error_c",
                    "mean",
                ),
                rules_within_date=("decision_rule", "nunique"),
            )
        )

        if not (working["rules_within_date"] == 4).all():
            fail(
                "Date-balanced scoring requires all four decision rules "
                "within every model-date-block group."
            )

        result = (
            working.groupby(group_columns, as_index=False)
            .agg(
                observations=("crps_c", "size"),
                dates=("target_date", "nunique"),
                decision_rules=("rules_within_date", "max"),
                minimum_rules_within_date=(
                    "rules_within_date",
                    "min",
                ),
                mean_crps_c=("crps_c", "mean"),
                median_crps_c=("crps_c", "median"),
                standard_deviation_crps_c=("crps_c", "std"),
                q25_crps_c=(
                    "crps_c",
                    lambda values: float(values.quantile(0.25)),
                ),
                q75_crps_c=(
                    "crps_c",
                    lambda values: float(values.quantile(0.75)),
                ),
                mean_absolute_temperature_error_c=(
                    "absolute_temperature_error_c",
                    "mean",
                ),
            )
            .sort_values(group_columns, kind="stable")
            .reset_index(drop=True)
        )

        if not (
            (result["decision_rules"] == 4)
            & (result["minimum_rules_within_date"] == 4)
        ).all():
            fail(
                "Date-balanced score output does not preserve complete "
                "four-rule support."
            )
    else:
        result = (
            working.groupby(group_columns, as_index=False)
            .agg(
                observations=("crps_c", "size"),
                dates=("target_date", "nunique"),
                decision_rules=("decision_rule", "nunique"),
                mean_crps_c=("crps_c", "mean"),
                median_crps_c=("crps_c", "median"),
                standard_deviation_crps_c=("crps_c", "std"),
                q25_crps_c=(
                    "crps_c",
                    lambda values: float(values.quantile(0.25)),
                ),
                q75_crps_c=(
                    "crps_c",
                    lambda values: float(values.quantile(0.75)),
                ),
                mean_absolute_temperature_error_c=(
                    "absolute_temperature_error_c",
                    "mean",
                ),
            )
            .sort_values(group_columns, kind="stable")
            .reset_index(drop=True)
        )

    result["aggregation"] = (
        "equal target-date weight after averaging rules within date"
        if date_balanced
        else "equal target-date weight within each decision rule"
    )
    return result


def build_score_outputs(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    by_rule = score_table(
        frame,
        ["model", "decision_rule"],
        date_balanced=False,
    )
    by_block = score_table(
        frame,
        ["model", "fold_id", "fold_number"],
        date_balanced=True,
    )
    by_rule_block = score_table(
        frame,
        ["model", "fold_id", "fold_number", "decision_rule"],
        date_balanced=False,
    )

    if len(by_rule) != 16:
        fail(f"Expected 16 model-rule score rows; found {len(by_rule)}.")
    if len(by_block) != 16:
        fail(f"Expected 16 model-block score rows; found {len(by_block)}.")
    if len(by_rule_block) != 64:
        fail(
            f"Expected 64 model-rule-block score rows; "
            f"found {len(by_rule_block)}."
        )
    return by_rule, by_block, by_rule_block


def build_paired_differences(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    scopes: list[
        tuple[str, str, pd.DataFrame, bool]
    ] = [
        ("overall", "all", frame, True),
    ]

    for rule in RULE_ORDER:
        scopes.append(
            (
                "decision_rule",
                rule,
                frame.loc[frame["decision_rule"] == rule],
                False,
            )
        )

    for fold, group in frame.groupby("fold_id", sort=True):
        scopes.append(
            ("validation_block", str(fold), group, True)
        )

    for (fold, rule), group in frame.groupby(
        ["fold_id", "decision_rule"],
        sort=True,
    ):
        scopes.append(
            (
                "rule_by_validation_block",
                f"{rule}|{fold}",
                group,
                False,
            )
        )

    rows: list[dict[str, Any]] = []

    for scope, scope_value, group, average_rules in scopes:
        if average_rules:
            losses = (
                group.groupby(
                    ["target_date", "model"],
                    as_index=False,
                )["crps_c"]
                .mean()
            )
        else:
            losses = group[
                ["target_date", "model", "crps_c"]
            ].copy()

        pivot = losses.pivot(
            index="target_date",
            columns="model",
            values="crps_c",
        ).sort_index()

        for first, second, label in COMPARISONS:
            if first not in pivot.columns or second not in pivot.columns:
                fail(
                    f"Missing {first} or {second} in paired scope "
                    f"{scope}:{scope_value}."
                )
            paired = pivot[[first, second]].dropna()
            difference = (
                paired[first] - paired[second]
            ).to_numpy(dtype=float)
            seed = (
                BOOTSTRAP_SEED
                + sum(
                    ord(character)
                    for character in f"{scope}:{scope_value}:{label}"
                )
            )
            (
                point,
                lower,
                upper,
                probability_lower,
            ) = bootstrap_mean_interval(
                difference,
                seed=seed,
            )
            rows.append(
                {
                    "scope": scope,
                    "scope_value": scope_value,
                    "comparison": label,
                    "first_model": first,
                    "second_model": second,
                    "difference_definition": (
                        "first model CRPS minus second model CRPS"
                    ),
                    "dates": int(len(difference)),
                    "mean_difference_c": point,
                    "bootstrap_lower_95_c": lower,
                    "bootstrap_upper_95_c": upper,
                    "bootstrap_probability_first_lower_crps": (
                        probability_lower
                    ),
                    "bootstrap_replications": BOOTSTRAP_REPLICATIONS,
                    "bootstrap_unit": "target_date",
                    "seed": seed,
                }
            )

    result = pd.DataFrame(rows)
    if len(result) != 100:
        fail(
            f"Expected 100 paired comparison rows; found {len(result)}."
        )
    return result


def build_rank_outputs(
    rule_block_scores: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rankings = rule_block_scores.copy()
    rankings["rank"] = rankings.groupby(
        ["fold_id", "decision_rule"],
        sort=False,
    )["mean_crps_c"].rank(
        method="min",
        ascending=True,
    )
    rankings["best_in_cell"] = rankings["rank"] == 1.0

    cell_counts = rankings.groupby(
        ["fold_id", "decision_rule"],
        sort=False,
    )["model"].nunique()
    if not (cell_counts == 4).all():
        fail("At least one rule-block cell does not contain all four models.")

    summary = (
        rankings.groupby("model", as_index=False)
        .agg(
            rule_block_cells=("rank", "size"),
            best_cells=("best_in_cell", "sum"),
            mean_rank=("rank", "mean"),
            median_rank=("rank", "median"),
            rank_standard_deviation=("rank", "std"),
            minimum_rank=("rank", "min"),
            maximum_rank=("rank", "max"),
            mean_rule_block_crps_c=("mean_crps_c", "mean"),
        )
        .sort_values(
            ["mean_rank", "mean_rule_block_crps_c"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if len(rankings) != 64 or len(summary) != 4:
        fail("Model ranking outputs have unexpected dimensions.")
    if int(summary["best_cells"].sum()) != 16:
        fail("Exactly one best model must be identified in each of 16 cells.")

    return rankings, summary


def combine_row_text(row: pd.Series) -> str:
    return " | ".join(
        f"{column}={value}"
        for column, value in row.items()
        if pd.notna(value)
    )


def first_numeric_value(
    row: pd.Series,
    exact: Iterable[str] = (),
    contains_all: Iterable[str] = (),
    contains_any: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> float | None:
    column = find_column(
        row.index,
        exact=exact,
        contains_all=contains_all,
        contains_any=contains_any,
        exclude=exclude,
    )
    if not column:
        return None
    value = pd.to_numeric(
        pd.Series([row[column]]),
        errors="coerce",
    ).iloc[0]
    if pd.isna(value):
        return None
    return float(value)


def parse_regex_float(
    text: str,
    patterns: list[str],
) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                continue
    return None



def stable_array_hash(values: np.ndarray, sort_values: bool = False) -> str:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if sort_values:
        array = np.sort(array)
    rounded = np.round(array, 12)
    return hashlib.sha256(rounded.tobytes()).hexdigest()


def parse_kernel_text(kernel_text: str, model: str) -> dict[str, float]:
    amplitude = parse_regex_float(
        kernel_text,
        [
            r"([0-9eE+\-.]+)\s*\*\*\s*2\s*\*\s*(?:RBF|Matern)",
            r"([0-9eE+\-.]+)\s*\^\s*2\s*\*\s*(?:RBF|Matern)",
        ],
    )
    length_scale = parse_regex_float(
        kernel_text,
        [r"length_scale\s*=\s*\[?\s*([0-9eE+\-.]+)"],
    )
    noise_level = parse_regex_float(
        kernel_text,
        [r"noise_level\s*=\s*([0-9eE+\-.]+)"],
    )
    nu = parse_regex_float(
        kernel_text,
        [r"\bnu\s*=\s*([0-9eE+\-.]+)"],
    )
    if model == "rbf" and nu is None:
        nu = math.nan

    missing = [
        name
        for name, value in {
            "signal_amplitude": amplitude,
            "length_scale": length_scale,
            "noise_level": noise_level,
        }.items()
        if value is None or not math.isfinite(float(value))
    ]
    if missing:
        fail(
            f"Could not parse {missing} from fitted kernel {kernel_text!r}."
        )

    assert amplitude is not None
    assert length_scale is not None
    assert noise_level is not None
    if amplitude <= 0 or length_scale <= 0 or noise_level < 0:
        fail(f"Invalid fitted kernel parameters in {kernel_text!r}.")

    return {
        "signal_amplitude": float(amplitude),
        "signal_variance": float(amplitude**2),
        "length_scale": float(length_scale),
        "noise_level": float(noise_level),
        "matern_nu": (
            float(nu)
            if nu is not None and math.isfinite(float(nu))
            else math.nan
        ),
    }


def replay_hook_source() -> str:
    return r'''import hashlib
import json
import os
from pathlib import Path

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor

_LOG_PATH = Path(os.environ["PHASE18_FIT_LOG"])
_ORIGINAL_FIT = GaussianProcessRegressor.fit


def _hash(values, sort_values=False):
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if sort_values:
        array = np.sort(array)
    rounded = np.round(array, 12)
    return hashlib.sha256(rounded.tobytes()).hexdigest()


def _simple(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_simple(item) for item in value]
    return repr(value)


def _wrapped_fit(self, X, y):
    initial_kernel = str(self.kernel)
    y_array = np.asarray(y, dtype=np.float64).reshape(-1)
    result = _ORIGINAL_FIT(self, X, y)
    record = {
        "n_train": int(y_array.size),
        "n_features": int(np.asarray(X).shape[1]),
        "y_hash_ordered": _hash(y_array, False),
        "y_hash_sorted": _hash(y_array, True),
        "y_mean": float(y_array.mean()),
        "y_standard_deviation": float(y_array.std(ddof=0)),
        "y_minimum": float(y_array.min()),
        "y_maximum": float(y_array.max()),
        "kernel_initial": initial_kernel,
        "kernel_fitted": str(self.kernel_),
        "kernel_theta": _simple(getattr(self.kernel_, "theta", None)),
        "log_marginal_likelihood_value": _simple(
            getattr(self, "log_marginal_likelihood_value_", None)
        ),
        "alpha": _simple(getattr(self, "alpha", None)),
        "normalize_y": bool(getattr(self, "normalize_y", False)),
        "optimizer": _simple(getattr(self, "optimizer", None)),
        "n_restarts_optimizer": int(
            getattr(self, "n_restarts_optimizer", 0)
        ),
        "random_state": _simple(getattr(self, "random_state", None)),
        "response_training_mean": _simple(
            getattr(self, "_y_train_mean", None)
        ),
        "response_training_std": _simple(
            getattr(self, "_y_train_std", None)
        ),
    }
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return result


GaussianProcessRegressor.fit = _wrapped_fit
'''


def copy_repository_for_replay(destination: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            if name in {".git", "__pycache__", ".DS_Store"}:
                ignored.add(name)
                continue
            if name.endswith(".pyc"):
                ignored.add(name)
                continue
            if name.startswith("phase18_"):
                ignored.add(name)
        return ignored

    shutil.copytree(ROOT, destination, ignore=ignore)


def discover_replay_columns(
    frame: pd.DataFrame,
) -> dict[str, str]:
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
        "target": find_column(
            columns,
            exact=[
                "gp_target",
                "residual_c",
                "residual_observed_c",
            ],
            contains_any=["gp_target", "residual"],
            exclude=["predictive", "mean", "standard", "error"],
        ),
    }
    missing = [key for key, value in mapping.items() if value is None]
    if missing:
        fail(
            f"Could not identify replay feature columns {missing}. "
            f"Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items()}


def reconcile_replay_predictions(
    certified: pd.DataFrame,
    replayed: pd.DataFrame,
) -> pd.DataFrame:
    key_candidates = [
        "target_date",
        "fold_id",
        "fold_number",
        "decision_rule",
        "kernel",
        "model_identifier",
    ]
    keys = [
        column
        for column in key_candidates
        if column in certified.columns and column in replayed.columns
    ]
    required_keys = {
        "target_date",
        "fold_id",
        "decision_rule",
        "kernel",
        "model_identifier",
    }
    if not required_keys.issubset(keys):
        fail(
            "Replay reconciliation cannot identify the complete certified "
            "prediction key."
        )

    left = certified.copy()
    right = replayed.copy()
    for frame in (left, right):
        frame["target_date"] = pd.to_datetime(
            frame["target_date"], errors="raise"
        ).dt.strftime("%Y-%m-%d")
        frame["decision_rule"] = frame["decision_rule"].map(normalise_rule)
        frame["kernel"] = frame["kernel"].map(normalise_model)

    left = left.sort_values(keys, kind="stable").reset_index(drop=True)
    right = right.sort_values(keys, kind="stable").reset_index(drop=True)

    if len(left) != 2920 or len(right) != 2920:
        fail(
            f"Expected 2,920 certified and replayed prediction rows; "
            f"found {len(left)} and {len(right)}."
        )
    if left[keys].duplicated().any() or right[keys].duplicated().any():
        fail("Certified or replayed prediction keys are duplicated.")
    if not left[keys].equals(right[keys]):
        mismatch = left[keys].merge(
            right[keys],
            how="outer",
            on=keys,
            indicator=True,
        )
        diagnostic = OUT / "phase18_replay_key_mismatch.csv"
        write_csv(
            diagnostic,
            mismatch.loc[mismatch["_merge"] != "both"],
        )
        fail(
            "Replayed Phase 7 prediction keys do not match the certified "
            f"panel. Diagnostic: {rel(diagnostic)}"
        )

    critical = {
        "residual_predictive_mean_c",
        "predictive_standard_deviation_c",
        "temperature_predictive_mean_c",
        "crps_c",
    }
    rows: list[dict[str, Any]] = []

    for column in left.columns:
        if column not in right.columns or column in keys:
            continue
        left_numeric = pd.to_numeric(left[column], errors="coerce")
        right_numeric = pd.to_numeric(right[column], errors="coerce")
        if left_numeric.notna().sum() == 0 and right_numeric.notna().sum() == 0:
            continue
        if not left_numeric.notna().equals(right_numeric.notna()):
            fail(f"Replay missing-value pattern differs for {column}.")
        mask = left_numeric.notna()
        difference = (
            left_numeric.loc[mask].to_numpy(dtype=float)
            - right_numeric.loc[mask].to_numpy(dtype=float)
        )
        maximum = float(np.max(np.abs(difference))) if len(difference) else 0.0
        tolerance = 5e-10 if column in critical else 1e-8
        rows.append(
            {
                "column": column,
                "observations": int(mask.sum()),
                "maximum_absolute_error": maximum,
                "tolerance": tolerance,
                "status": "PASSED" if maximum <= tolerance else "FAILED",
            }
        )

    result = pd.DataFrame(rows).sort_values("column", kind="stable")
    if result.empty:
        fail("No numeric replay columns were reconciled.")
    missing_critical = critical.difference(set(result["column"]))
    if missing_critical:
        fail(f"Critical replay columns are missing: {sorted(missing_critical)}")
    if not (result["status"] == "PASSED").all():
        diagnostic = OUT / "phase18_replay_prediction_reconciliation.csv"
        write_csv(diagnostic, result)
        fail(
            "Exact Phase 7 replay failed numerical reconciliation. "
            f"Diagnostic: {rel(diagnostic)}"
        )
    return result.reset_index(drop=True)


def build_expected_training_registry(
    certified: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    required_design = [
        "fold_id",
        "fold_number",
        "decision_rule",
        "kernel",
        "training_start",
        "training_end",
    ]
    missing = [column for column in required_design if column not in certified]
    if missing:
        fail(f"Certified validation panel lacks design columns {missing}.")

    design = certified[required_design].drop_duplicates().copy()
    design["decision_rule"] = design["decision_rule"].map(normalise_rule)
    design["model"] = design["kernel"].map(normalise_model)
    design["training_start"] = pd.to_datetime(
        design["training_start"], errors="raise"
    ).dt.normalize()
    design["training_end"] = pd.to_datetime(
        design["training_end"], errors="raise"
    ).dt.normalize()
    if len(design) != 32:
        fail(f"Expected 32 certified fold designs; found {len(design)}.")

    feature_columns = discover_replay_columns(features)
    panel = pd.DataFrame(
        {
            "target_date": pd.to_datetime(
                features[feature_columns["date"]], errors="raise"
            ).dt.normalize(),
            "decision_rule": features[feature_columns["rule"]].map(
                normalise_rule
            ),
            "gp_target": pd.to_numeric(
                features[feature_columns["target"]], errors="raise"
            ),
        }
    )

    if panel["gp_target"].isna().any():
        fail("Feature panel contains missing GP target values.")

    if not np.isfinite(panel["gp_target"].to_numpy(dtype=float)).all():
        fail("Feature panel contains non-finite GP target values.")

    raw_feature_rows = int(len(panel))
    duplicate_mask = panel.duplicated(
        ["target_date", "decision_rule"],
        keep=False,
    )

    duplicate_audit_rows: list[dict[str, Any]] = []

    if duplicate_mask.any():
        duplicate_groups = panel.loc[duplicate_mask].groupby(
            ["target_date", "decision_rule"],
            sort=True,
        )

        conflict_rows: list[dict[str, Any]] = []

        for (target_date, decision_rule), group in duplicate_groups:
            values = group["gp_target"].to_numpy(dtype=float)
            spread = float(values.max() - values.min())

            audit_row = {
                "target_date": target_date,
                "decision_rule": decision_rule,
                "source_rows": int(len(group)),
                "unique_exact_target_values": int(
                    pd.Series(values).nunique(dropna=False)
                ),
                "minimum_gp_target": float(values.min()),
                "maximum_gp_target": float(values.max()),
                "target_spread": spread,
                "values_consistent_within_1e_12": bool(
                    spread <= 1e-12
                ),
            }
            duplicate_audit_rows.append(audit_row)

            if spread > 1e-12:
                conflict_rows.append(audit_row)

        if conflict_rows:
            diagnostic = OUT / (
                "phase18_conflicting_feature_response_duplicates.csv"
            )
            write_csv(diagnostic, pd.DataFrame(conflict_rows))
            fail(
                "The fold-expanded feature panel contains conflicting "
                "GP targets within at least one date-rule key. "
                f"Diagnostic: {rel(diagnostic)}"
            )

        # The Phase 6 feature file is fold-expanded: the same underlying
        # weather-only date-rule response can appear in several fold-design
        # records. After proving that every repeated target is numerically
        # identical, collapse to the unique 730-by-4 response panel used to
        # identify the replayed training vectors.
        panel = (
            panel.groupby(
                ["target_date", "decision_rule"],
                as_index=False,
                sort=True,
            )
            .agg(gp_target=("gp_target", "first"))
            .sort_values(
                ["decision_rule", "target_date"],
                kind="stable",
            )
            .reset_index(drop=True)
        )

    if panel.duplicated(["target_date", "decision_rule"]).any():
        fail(
            "Feature-panel duplicate collapse did not produce unique "
            "date-rule response keys."
        )

    if len(panel) != 2920:
        fail(
            "Expected 2,920 unique weather-only date-rule responses after "
            f"collapsing the fold-expanded feature panel; found {len(panel)}."
        )

    if panel["target_date"].nunique() != 730:
        fail(
            "Collapsed feature response panel does not contain 730 dates."
        )

    if set(panel["decision_rule"]) != set(RULE_ORDER):
        fail(
            "Collapsed feature response panel does not contain the four "
            "certified decision rules."
        )

    collapse_audit = pd.DataFrame(
        duplicate_audit_rows,
        columns=[
            "target_date",
            "decision_rule",
            "source_rows",
            "unique_exact_target_values",
            "minimum_gp_target",
            "maximum_gp_target",
            "target_spread",
            "values_consistent_within_1e_12",
        ],
    )
    if collapse_audit.empty:
        collapse_audit = pd.DataFrame(
            [
                {
                    "target_date": pd.NaT,
                    "decision_rule": "none",
                    "source_rows": 1,
                    "unique_exact_target_values": 1,
                    "minimum_gp_target": math.nan,
                    "maximum_gp_target": math.nan,
                    "target_spread": 0.0,
                    "values_consistent_within_1e_12": True,
                }
            ]
        )

    write_csv(
        OUT / "phase18_feature_response_duplicate_audit.csv",
        collapse_audit,
    )

    print(
        "PHASE18_FEATURE_RESPONSE_COLLAPSE="
        + json.dumps(
            {
                "raw_feature_rows": raw_feature_rows,
                "duplicate_source_rows": int(duplicate_mask.sum()),
                "duplicate_date_rule_keys": int(
                    len(duplicate_audit_rows)
                ),
                "collapsed_unique_date_rule_keys": int(len(panel)),
                "collapsed_dates": int(
                    panel["target_date"].nunique()
                ),
                "decision_rules": int(
                    panel["decision_rule"].nunique()
                ),
                "maximum_duplicate_target_spread": float(
                    max(
                        (
                            row["target_spread"]
                            for row in duplicate_audit_rows
                        ),
                        default=0.0,
                    )
                ),
            },
            sort_keys=True,
        )
    )

    rows: list[dict[str, Any]] = []
    for _, row in design.iterrows():
        subset = panel.loc[
            (panel["decision_rule"] == row["decision_rule"])
            & (panel["target_date"] >= row["training_start"])
            & (panel["target_date"] <= row["training_end"])
        ].sort_values("target_date", kind="stable")
        values = subset["gp_target"].to_numpy(dtype=float)
        if len(values) == 0:
            fail(f"No training responses found for {row.to_dict()}.")
        rows.append(
            {
                **row.to_dict(),
                "training_dates": int(len(values)),
                "y_hash_ordered": stable_array_hash(values, False),
                "y_hash_sorted": stable_array_hash(values, True),
                "y_mean": float(values.mean()),
                "y_standard_deviation": float(values.std(ddof=0)),
                "y_minimum": float(values.min()),
                "y_maximum": float(values.max()),
            }
        )

    expected = pd.DataFrame(rows)
    training_counts = sorted(expected["training_dates"].unique().tolist())
    if len(training_counts) != 4:
        fail(
            "Chronological replay should contain four distinct expanding "
            f"training sizes; found {training_counts}."
        )
    return expected


def map_fit_records_to_design(
    records: list[dict[str, Any]],
    expected: pd.DataFrame,
) -> pd.DataFrame:
    relevant: list[dict[str, Any]] = []
    training_sizes = set(expected["training_dates"].astype(int))

    for sequence, record in enumerate(records, start=1):
        model = normalise_model(
            f"{record.get('kernel_initial', '')} "
            f"{record.get('kernel_fitted', '')}"
        )
        if model not in {"rbf", "matern32"}:
            continue
        if int(record.get("n_train", -1)) not in training_sizes:
            continue
        enriched = dict(record)
        enriched["sequence"] = sequence
        enriched["model"] = model
        relevant.append(enriched)

    if len(relevant) != 32:
        fail(
            f"Expected 32 relevant Gaussian-process fits in the exact replay; "
            f"found {len(relevant)}."
        )

    available = expected.copy()
    assignments: list[dict[str, Any]] = []

    for record in relevant:
        candidates = available.loc[
            (available["training_dates"] == int(record["n_train"]))
            & (available["model"] == record["model"])
        ].copy()
        if candidates.empty:
            fail(
                "No unused certified fold design matches replay fit "
                f"sequence {record['sequence']}."
            )

        ordered = candidates.loc[
            candidates["y_hash_ordered"] == record["y_hash_ordered"]
        ]
        sorted_match = candidates.loc[
            candidates["y_hash_sorted"] == record["y_hash_sorted"]
        ]
        if len(ordered) == 1:
            match = ordered.iloc[0]
            mapping_method = "ordered_response_hash"
        elif len(sorted_match) == 1:
            match = sorted_match.iloc[0]
            mapping_method = "sorted_response_hash"
        else:
            candidates = candidates.copy()
            candidates["mapping_distance"] = (
                (candidates["y_mean"] - float(record["y_mean"])).abs()
                + (
                    candidates["y_standard_deviation"]
                    - float(record["y_standard_deviation"])
                ).abs()
                + (candidates["y_minimum"] - float(record["y_minimum"])).abs()
                + (candidates["y_maximum"] - float(record["y_maximum"])).abs()
            )
            candidates = candidates.sort_values(
                "mapping_distance", kind="stable"
            )
            if len(candidates) > 1 and not (
                float(candidates.iloc[0]["mapping_distance"]) + 1e-12
                < float(candidates.iloc[1]["mapping_distance"])
            ):
                fail(
                    "Replay response summaries do not uniquely identify fit "
                    f"sequence {record['sequence']}."
                )
            match = candidates.iloc[0]
            if float(match["mapping_distance"]) > 1e-9:
                fail(
                    "Replay response does not reconcile with the certified "
                    f"training panel for sequence {record['sequence']}."
                )
            mapping_method = "response_summary"

        kernel_text = str(record["kernel_fitted"])
        parameters = parse_kernel_text(kernel_text, record["model"])
        assignments.append(
            {
                "registry_source": "exact_phase7_replay",
                "replay_fit_sequence": int(record["sequence"]),
                "mapping_method": mapping_method,
                "fold_id": match["fold_id"],
                "fold_number": int(match["fold_number"]),
                "decision_rule": match["decision_rule"],
                "model": record["model"],
                "training_start": match["training_start"],
                "training_end": match["training_end"],
                "training_dates": int(match["training_dates"]),
                "kernel_initial": record["kernel_initial"],
                "kernel_text": kernel_text,
                **parameters,
                "alpha": record.get("alpha"),
                "normalize_y": record.get("normalize_y"),
                "optimizer": record.get("optimizer"),
                "n_restarts_optimizer": record.get("n_restarts_optimizer"),
                "random_state": record.get("random_state"),
                "log_marginal_likelihood_value": record.get(
                    "log_marginal_likelihood_value"
                ),
                "y_hash_ordered": record["y_hash_ordered"],
                "y_hash_sorted": record["y_hash_sorted"],
            }
        )
        available = available.drop(index=match.name)

    result = pd.DataFrame(assignments).sort_values(
        ["fold_number", "decision_rule", "model"], kind="stable"
    ).reset_index(drop=True)
    if len(result) != 32 or len(available) != 0:
        fail("Exact replay did not establish a one-to-one 32-model mapping.")
    return result


def replay_phase7_fold_models(
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    certified = pd.read_csv(CERTIFIED_GP_VALIDATION_PATH)
    features = pd.read_csv(FEATURE_PANEL_PATH)
    expected = build_expected_training_registry(certified, features)

    execution_log_path = OUT / "phase18_replay_execution.log"
    fit_log_records: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="phase18_exact_replay_") as temp:
        temporary = Path(temp)
        replay_root = temporary / "repository"
        hook_directory = temporary / "hook"
        fit_log_path = temporary / "phase18_fit_log.jsonl"
        copy_repository_for_replay(replay_root)
        hook_directory.mkdir(parents=True, exist_ok=True)
        (hook_directory / "sitecustomize.py").write_text(
            replay_hook_source(), encoding="utf-8"
        )

        replay_prediction_path = (
            replay_root
            / "outputs/v2/diagnostics/07_gp_validation_predictions.csv"
        )
        for path in replay_prediction_path.parent.glob("07_*"):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)

        replay_source = (
            replay_root / "tools/v2/fit_gp_validation_distributions.py"
        )
        environment = os.environ.copy()
        environment["PHASE18_FIT_LOG"] = str(fit_log_path)
        existing_pythonpath = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = str(hook_directory) + (
            os.pathsep + existing_pythonpath
            if existing_pythonpath
            else ""
        )

        completed = subprocess.run(
            [sys.executable, str(replay_source)],
            cwd=replay_root,
            env=environment,
            text=True,
            capture_output=True,
        )
        execution_log_path.write_text(
            "COMMAND: "
            + repr([sys.executable, str(replay_source)])
            + "\n\nSTDOUT\n"
            + completed.stdout
            + "\nSTDERR\n"
            + completed.stderr,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            fail(
                "The isolated Phase 7 replay failed. Inspect "
                f"{rel(execution_log_path)}."
            )
        if not replay_prediction_path.is_file():
            fail("The isolated Phase 7 replay did not create its prediction panel.")
        if not fit_log_path.is_file():
            fail("The replay hook did not record Gaussian-process fits.")

        replayed = pd.read_csv(replay_prediction_path)
        reconciliation = reconcile_replay_predictions(certified, replayed)
        for line in fit_log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                fit_log_records.append(json.loads(line))

    fold_parameters = map_fit_records_to_design(
        fit_log_records,
        expected,
    )
    return fold_parameters, reconciliation, execution_log_path

def discover_registry_columns(
    frame: pd.DataFrame,
    require_fold: bool,
) -> dict[str, str | None]:
    columns = list(frame.columns)
    mapping: dict[str, str | None] = {
        "rule": find_column(
            columns,
            exact=["decision_rule", "rule"],
        ),
        "model": find_column(
            columns,
            exact=[
                "kernel_family",
                "model_family",
                "model",
                "kernel",
                "kernel_name",
            ],
            contains_any=["kernel", "model"],
            exclude=["initial", "fitted", "representation", "string"],
        ),
        "fold": find_column(
            columns,
            exact=[
                "fold_id",
                "fold_number",
                "validation_block",
                "block_id",
                "fold",
            ],
        ),
        "kernel_text": find_column(
            columns,
            exact=[
                "fitted_kernel",
                "kernel_fitted",
                "fitted_kernel_repr",
                "fitted_kernel_string",
                "kernel_representation",
                "kernel_string",
            ],
            contains_all=["kernel"],
            contains_any=["fitted", "repr", "string", "representation"],
            exclude=["initial"],
        ),
    }
    required = ["rule", "model"]
    if require_fold:
        required.append("fold")
    missing = [key for key in required if not mapping[key]]
    if missing:
        fail(
            f"Could not identify model-registry columns {missing}. "
            f"Available columns: {columns}"
        )
    return mapping


def parse_registry(
    frame: pd.DataFrame,
    require_fold: bool,
    source_name: str,
) -> pd.DataFrame:
    columns = discover_registry_columns(frame, require_fold=require_fold)
    rows: list[dict[str, Any]] = []

    for index, row in frame.iterrows():
        text = combine_row_text(row)
        rule = normalise_rule(row[str(columns["rule"])])
        model_source = row[str(columns["model"])]
        model = normalise_model(model_source)

        if model not in {"rbf", "matern32"}:
            model = normalise_model(text)

        if rule not in RULE_ORDER:
            fail(
                f"{source_name} row {index}: unrecognised decision rule {rule!r}."
            )
        if model not in {"rbf", "matern32"}:
            fail(
                f"{source_name} row {index}: could not identify RBF or "
                "Matérn model family."
            )

        fold_id: Any = "full"
        if require_fold:
            fold_id = row[str(columns["fold"])]

        kernel_text = (
            str(row[str(columns["kernel_text"])])
            if columns.get("kernel_text")
            and pd.notna(row[str(columns["kernel_text"])])
            else text
        )

        length_scale = first_numeric_value(
            row,
            exact=[
                "length_scale",
                "fitted_length_scale",
                "kernel_length_scale",
            ],
            contains_all=["length", "scale"],
            exclude=["lower", "upper", "bound", "initial"],
        )
        if length_scale is None:
            length_scale = parse_regex_float(
                kernel_text,
                [
                    r"length_scale\s*=\s*\[?\s*([0-9eE+\-.]+)",
                    r"length[_ ]?scale\s*[:=]\s*\[?\s*([0-9eE+\-.]+)",
                ],
            )

        noise_level = first_numeric_value(
            row,
            exact=[
                "noise_level",
                "fitted_noise_level",
                "white_noise_level",
                "whitekernel_noise_level",
            ],
            contains_all=["noise"],
            contains_any=["level", "variance"],
            exclude=[
                "initial",
                "identity",
                "error",
                "lower",
                "upper",
                "bound",
            ],
        )
        if noise_level is None:
            noise_level = parse_regex_float(
                kernel_text,
                [
                    r"noise_level\s*=\s*([0-9eE+\-.]+)",
                    r"white(?:kernel)?[^|]*?variance\s*[:=]\s*([0-9eE+\-.]+)",
                ],
            )

        signal_variance = first_numeric_value(
            row,
            exact=[
                "signal_variance",
                "constant_value",
                "fitted_constant_value",
                "kernel_constant_value",
            ],
            contains_any=["signal_variance", "constant_value"],
            exclude=["initial", "lower", "upper", "bound"],
        )

        amplitude_base = first_numeric_value(
            row,
            exact=[
                "signal_amplitude",
                "amplitude",
                "constant_amplitude",
            ],
            contains_all=["amplitude"],
            exclude=["initial", "lower", "upper", "bound"],
        )

        if signal_variance is None:
            base_from_text = parse_regex_float(
                kernel_text,
                [
                    r"([0-9eE+\-.]+)\s*\*\*\s*2\s*\*\s*(?:RBF|Matern)",
                    r"([0-9eE+\-.]+)\s*\^\s*2\s*\*\s*(?:RBF|Matern)",
                ],
            )
            if base_from_text is not None:
                amplitude_base = base_from_text
                signal_variance = base_from_text**2

        if signal_variance is None:
            signal_variance = parse_regex_float(
                kernel_text,
                [
                    r"constant_value\s*=\s*([0-9eE+\-.]+)",
                    r"signal_variance\s*[:=]\s*([0-9eE+\-.]+)",
                ],
            )

        if amplitude_base is None and signal_variance is not None:
            if signal_variance >= 0:
                amplitude_base = math.sqrt(signal_variance)

        nu = first_numeric_value(
            row,
            exact=["nu", "matern_nu"],
            contains_all=["nu"],
            exclude=["number"],
        )
        if nu is None:
            nu = parse_regex_float(
                kernel_text,
                [r"\bnu\s*=\s*([0-9eE+\-.]+)"],
            )
        if model == "rbf" and nu is None:
            nu = math.nan

        alpha = first_numeric_value(
            row,
            exact=[
                "alpha",
                "gpr_alpha",
                "numerical_jitter",
                "jitter",
            ],
            contains_any=["alpha", "jitter"],
            exclude=["error", "lower", "upper"],
        )

        training_dates = first_numeric_value(
            row,
            exact=[
                "training_dates",
                "training_rows",
                "n_train",
                "training_observations",
            ],
            contains_all=["training"],
            contains_any=["dates", "rows", "observations"],
            exclude=["start", "end"],
        )

        missing_fields = [
            name
            for name, value in {
                "length_scale": length_scale,
                "noise_level": noise_level,
                "signal_variance": signal_variance,
            }.items()
            if value is None or not math.isfinite(float(value))
        ]
        if missing_fields:
            diagnostic_path = OUT / (
                f"phase18_unparsed_{source_name}_registry_row_{index}.txt"
            )
            diagnostic_path.write_text(
                text + "\n",
                encoding="utf-8",
            )
            fail(
                f"{source_name} row {index}: could not parse {missing_fields}. "
                f"Diagnostic: {rel(diagnostic_path)}"
            )

        if (
            float(length_scale) <= 0
            or float(noise_level) < 0
            or float(signal_variance) <= 0
        ):
            fail(
                f"{source_name} row {index}: parsed hyperparameters are invalid."
            )

        rows.append(
            {
                "registry_source": source_name,
                "source_row": int(index),
                "fold_id": fold_id,
                "decision_rule": rule,
                "model": model,
                "kernel_text": kernel_text,
                "signal_amplitude": float(amplitude_base),
                "signal_variance": float(signal_variance),
                "length_scale": float(length_scale),
                "noise_level": float(noise_level),
                "matern_nu": (
                    float(nu)
                    if nu is not None and math.isfinite(float(nu))
                    else math.nan
                ),
                "alpha": (
                    float(alpha)
                    if alpha is not None and math.isfinite(float(alpha))
                    else math.nan
                ),
                "training_dates": (
                    int(round(float(training_dates)))
                    if training_dates is not None
                    and math.isfinite(float(training_dates))
                    else math.nan
                ),
            }
        )

    result = pd.DataFrame(rows)

    expected_rows = 32 if require_fold else 4
    if len(result) != expected_rows:
        fail(
            f"Expected {expected_rows} parsed rows in {source_name}; "
            f"found {len(result)}."
        )

    expected_models = {"rbf", "matern32"}
    if require_fold:
        if set(result["model"]) != expected_models:
            fail(f"{source_name} does not contain both GP families.")
        counts = result.groupby(
            ["model", "decision_rule"],
            sort=False,
        )["fold_id"].nunique()
        if not (counts == 4).all():
            fail(
                f"{source_name} does not contain four folds for every "
                "model-rule combination."
            )
    else:
        if set(result["model"]) != {"matern32"}:
            # Phase 8 saved only the selected full-history Matérn models.
            fail(
                f"{source_name} should contain four selected Matérn full-fit models."
            )
        if result["decision_rule"].nunique() != 4:
            fail(f"{source_name} does not contain four decision rules.")

    return result


def hyperparameter_summary(
    fold_parameters: pd.DataFrame,
    full_parameters: pd.DataFrame,
) -> pd.DataFrame:
    metrics = [
        "signal_variance",
        "length_scale",
        "noise_level",
    ]
    rows: list[dict[str, Any]] = []

    for (model, rule), group in fold_parameters.groupby(
        ["model", "decision_rule"],
        sort=True,
    ):
        row: dict[str, Any] = {
            "model": model,
            "decision_rule": rule,
            "folds": int(group["fold_id"].nunique()),
        }
        for metric in metrics:
            values = group[metric].to_numpy(dtype=float)
            mean = float(values.mean())
            standard_deviation = float(values.std(ddof=1))
            minimum = float(values.min())
            maximum = float(values.max())
            row[f"{metric}_mean"] = mean
            row[f"{metric}_standard_deviation"] = standard_deviation
            row[f"{metric}_minimum"] = minimum
            row[f"{metric}_maximum"] = maximum
            row[f"{metric}_coefficient_of_variation"] = (
                standard_deviation / abs(mean)
                if mean != 0
                else math.nan
            )
            row[f"{metric}_max_to_min_ratio"] = (
                maximum / minimum
                if minimum > 0
                else math.nan
            )

        full_match = full_parameters.loc[
            (full_parameters["model"] == model)
            & (full_parameters["decision_rule"] == rule)
        ]
        if len(full_match) == 1:
            for metric in metrics:
                value = float(full_match.iloc[0][metric])
                row[f"full_fit_{metric}"] = value
                row[f"full_fit_{metric}_within_fold_range"] = bool(
                    row[f"{metric}_minimum"]
                    <= value
                    <= row[f"{metric}_maximum"]
                )
        else:
            for metric in metrics:
                row[f"full_fit_{metric}"] = math.nan
                row[f"full_fit_{metric}_within_fold_range"] = math.nan

        rows.append(row)

    result = pd.DataFrame(rows)
    if len(result) != 8:
        fail(
            f"Expected eight model-rule hyperparameter summaries; "
            f"found {len(result)}."
        )
    return result


def create_figures(
    rule_block_scores: pd.DataFrame,
    paired: pd.DataFrame,
    fold_parameters: pd.DataFrame,
) -> list[Path]:
    FIG.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    matern = rule_block_scores.loc[
        rule_block_scores["model"] == "matern32"
    ].copy()
    fold_order = sorted(matern["fold_id"].unique(), key=lambda value: str(value))
    matrix = (
        matern.pivot(
            index="decision_rule",
            columns="fold_id",
            values="mean_crps_c",
        )
        .reindex(index=RULE_ORDER, columns=fold_order)
        .to_numpy(dtype=float)
    )

    figure, axis = plt.subplots(figsize=(8.5, 5.0))
    image = axis.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest",
    )
    axis.set_xticks(range(len(fold_order)))
    axis.set_xticklabels([str(value) for value in fold_order])
    axis.set_yticks(range(len(RULE_ORDER)))
    axis.set_yticklabels([RULE_LABELS[rule] for rule in RULE_ORDER])
    axis.set_xlabel("Chronological validation block")
    axis.set_ylabel("Decision rule")
    axis.set_title("Matérn-3/2 mean CRPS by decision rule and block")
    colourbar = figure.colorbar(image, ax=axis, pad=0.02)
    colourbar.set_label("Mean CRPS (°C)")
    figure.tight_layout()

    for suffix in ("png", "pdf"):
        path = FIG / f"phase18_matern_crps_rule_block_heatmap.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    improvement = paired.loc[
        (paired["scope"] == "rule_by_validation_block")
        & (paired["comparison"] == "matern32_minus_static")
    ].copy()
    split = improvement["scope_value"].str.rsplit("|", n=1, expand=True)
    improvement["decision_rule"] = split[0]
    improvement["fold_id_text"] = split[1]
    improvement_matrix = (
        improvement.pivot(
            index="decision_rule",
            columns="fold_id_text",
            values="mean_difference_c",
        )
        .reindex(
            index=RULE_ORDER,
            columns=[str(value) for value in fold_order],
        )
        .to_numpy(dtype=float)
    )

    figure, axis = plt.subplots(figsize=(8.5, 5.0))
    image = axis.imshow(
        improvement_matrix,
        aspect="auto",
        interpolation="nearest",
    )
    axis.set_xticks(range(len(fold_order)))
    axis.set_xticklabels([str(value) for value in fold_order])
    axis.set_yticks(range(len(RULE_ORDER)))
    axis.set_yticklabels([RULE_LABELS[rule] for rule in RULE_ORDER])
    axis.set_xlabel("Chronological validation block")
    axis.set_ylabel("Decision rule")
    axis.set_title("Matérn-3/2 minus static Gaussian mean CRPS")
    colourbar = figure.colorbar(image, ax=axis, pad=0.02)
    colourbar.set_label("CRPS difference (°C); negative favours Matérn")
    figure.tight_layout()

    for suffix in ("png", "pdf"):
        path = FIG / f"phase18_matern_minus_static_heatmap.{suffix}"
        figure.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(path)
    plt.close(figure)

    matern_parameters = fold_parameters.loc[
        fold_parameters["model"] == "matern32"
    ].copy()

    figure, axis = plt.subplots(figsize=(8.5, 5.0))
    for rule in RULE_ORDER:
        group = matern_parameters.loc[
            matern_parameters["decision_rule"] == rule
        ].sort_values("fold_id", key=lambda series: series.astype(str))
        axis.plot(
            range(1, len(group) + 1),
            group["length_scale"].to_numpy(dtype=float),
            marker="o",
            label=RULE_LABELS[rule],
        )
    axis.set_xticks([1, 2, 3, 4])
    axis.set_xlabel("Chronological validation block")
    axis.set_ylabel("Fitted Matérn length scale")
    axis.set_title("Fold-to-fold Matérn length-scale stability")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()

    for suffix in ("png", "pdf"):
        path = FIG / f"phase18_matern_length_scale_stability.{suffix}"
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
            fail(f"Required Phase 18 input is missing: {rel(path)}")

    phase15_spec = json.loads(PHASE15_SPEC_PATH.read_text(encoding="utf-8"))
    phase16_spec = json.loads(PHASE16_SPEC_PATH.read_text(encoding="utf-8"))
    phase17_spec = json.loads(PHASE17_SPEC_PATH.read_text(encoding="utf-8"))

    for phase, specification in (
        (15, phase15_spec),
        (16, phase16_spec),
        (17, phase17_spec),
    ):
        if specification.get("status") != "PASSED":
            fail(f"Phase {phase} specification is not certified as PASSED.")

    predictions_raw = pd.read_csv(PREDICTIONS_PATH)
    fold_registry_raw = pd.read_csv(FOLD_REGISTRY_PATH)
    full_registry_raw = pd.read_csv(FULL_REGISTRY_PATH)

    prediction_columns = discover_prediction_columns(predictions_raw)
    print(
        "PHASE18_PREDICTION_COLUMN_MAP="
        + json.dumps(prediction_columns, sort_keys=True)
    )
    print(
        "PHASE18_FOLD_REGISTRY_COLUMNS="
        + json.dumps(list(fold_registry_raw.columns))
    )
    print(
        "PHASE18_FULL_REGISTRY_COLUMNS="
        + json.dumps(list(full_registry_raw.columns))
    )

    predictions = prepare_predictions(
        predictions_raw,
        prediction_columns,
    )

    (
        scores_by_rule,
        scores_by_block,
        scores_by_rule_block,
    ) = build_score_outputs(predictions)

    paired = build_paired_differences(predictions)
    rankings, rank_summary = build_rank_outputs(
        scores_by_rule_block
    )

    (
        fold_parameters,
        replay_reconciliation,
        replay_execution_log,
    ) = replay_phase7_fold_models()
    full_parameters = parse_registry(
        full_registry_raw,
        require_fold=False,
        source_name="phase15_full",
    )
    parameter_stability = hyperparameter_summary(
        fold_parameters,
        full_parameters,
    )

    figure_paths = create_figures(
        scores_by_rule_block,
        paired,
        fold_parameters,
    )

    overall_matern_static = paired.loc[
        (paired["scope"] == "overall")
        & (paired["comparison"] == "matern32_minus_static")
    ].iloc[0]
    overall_matern_rbf = paired.loc[
        (paired["scope"] == "overall")
        & (paired["comparison"] == "matern32_minus_rbf")
    ].iloc[0]

    rule_matern_static = paired.loc[
        (paired["scope"] == "decision_rule")
        & (paired["comparison"] == "matern32_minus_static")
    ].copy()
    block_matern_static = paired.loc[
        (paired["scope"] == "validation_block")
        & (paired["comparison"] == "matern32_minus_static")
    ].copy()
    cell_matern_static = paired.loc[
        (paired["scope"] == "rule_by_validation_block")
        & (paired["comparison"] == "matern32_minus_static")
    ].copy()
    cell_matern_rbf = paired.loc[
        (paired["scope"] == "rule_by_validation_block")
        & (paired["comparison"] == "matern32_minus_rbf")
    ].copy()

    matern_better_static_rules = int(
        (rule_matern_static["mean_difference_c"] < 0).sum()
    )
    matern_better_static_blocks = int(
        (block_matern_static["mean_difference_c"] < 0).sum()
    )
    matern_better_static_cells = int(
        (cell_matern_static["mean_difference_c"] < 0).sum()
    )
    matern_better_rbf_cells = int(
        (cell_matern_rbf["mean_difference_c"] < 0).sum()
    )

    matern_rank = rank_summary.loc[
        rank_summary["model"] == "matern32"
    ].iloc[0]

    matern_stability = parameter_stability.loc[
        parameter_stability["model"] == "matern32"
    ].copy()
    maximum_length_cv = float(
        matern_stability[
            "length_scale_coefficient_of_variation"
        ].max()
    )
    maximum_noise_cv = float(
        matern_stability[
            "noise_level_coefficient_of_variation"
        ].max()
    )
    full_length_within = int(
        matern_stability[
            "full_fit_length_scale_within_fold_range"
        ].fillna(False).sum()
    )
    full_noise_within = int(
        matern_stability[
            "full_fit_noise_level_within_fold_range"
        ].fillna(False).sum()
    )

    gap_updates = pd.DataFrame(
        [
            {
                "gap_id": "G08",
                "gap": "Rule and validation-block model results",
                "phase_closed": 18,
                "status": "CLOSED",
                "evidence": (
                    "phase18_model_scores_by_rule.csv|"
                    "phase18_model_scores_by_block.csv|"
                    "phase18_model_scores_by_rule_block.csv|"
                    "phase18_paired_model_differences.csv|"
                    "phase18_model_rank_stability.csv"
                ),
            },
            {
                "gap_id": "G09",
                "gap": "GP hyperparameter stability",
                "phase_closed": 18,
                "status": "CLOSED",
                "evidence": (
                    "phase18_gp_fold_hyperparameters.csv|"
                    "phase18_gp_full_fit_hyperparameters.csv|"
                    "phase18_gp_hyperparameter_stability.csv"
                ),
            },
        ]
    )

    spec = {
        "phase": 18,
        "name": (
            "Rule-specific, validation-block and "
            "GP hyperparameter stability analysis"
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_branch": git("branch", "--show-current"),
        "git_commit_before_phase18": git("rev-parse", "HEAD"),
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
        "exact_phase7_replay": {
            "source": rel(ORIGINAL_GP_SOURCE_PATH),
            "certified_prediction_panel": rel(
                CERTIFIED_GP_VALIDATION_PATH
            ),
            "feature_panel": rel(FEATURE_PANEL_PATH),
            "replayed_fold_models": int(len(fold_parameters)),
            "reconciled_numeric_columns": int(
                len(replay_reconciliation)
            ),
            "maximum_absolute_prediction_reconciliation_error": float(
                replay_reconciliation["maximum_absolute_error"].max()
            ),
            "execution_log": rel(replay_execution_log),
            "status": "PASSED",
        },
        "comparison_design": {
            "validation_dates": 365,
            "decision_rules": RULE_ORDER,
            "validation_blocks": 4,
            "models": MODELS,
            "prediction_rows": 5840,
            "rule_score_rows": int(len(scores_by_rule)),
            "block_score_rows": int(len(scores_by_block)),
            "rule_block_score_rows": int(len(scores_by_rule_block)),
            "paired_difference_rows": int(len(paired)),
            "bootstrap": {
                "replications": BOOTSTRAP_REPLICATIONS,
                "unit": "target_date",
                "base_seed": BOOTSTRAP_SEED,
                "interval": "2.5th and 97.5th percentiles",
            },
        },
        "headline_stability": {
            "matern_minus_static_overall": float(
                overall_matern_static["mean_difference_c"]
            ),
            "matern_minus_static_overall_lower_95": float(
                overall_matern_static["bootstrap_lower_95_c"]
            ),
            "matern_minus_static_overall_upper_95": float(
                overall_matern_static["bootstrap_upper_95_c"]
            ),
            "matern_minus_rbf_overall": float(
                overall_matern_rbf["mean_difference_c"]
            ),
            "matern_minus_rbf_overall_lower_95": float(
                overall_matern_rbf["bootstrap_lower_95_c"]
            ),
            "matern_minus_rbf_overall_upper_95": float(
                overall_matern_rbf["bootstrap_upper_95_c"]
            ),
            "matern_better_than_static_rules": (
                matern_better_static_rules
            ),
            "matern_better_than_static_blocks": (
                matern_better_static_blocks
            ),
            "matern_better_than_static_rule_block_cells": (
                matern_better_static_cells
            ),
            "matern_better_than_rbf_rule_block_cells": (
                matern_better_rbf_cells
            ),
            "matern_best_rule_block_cells": int(
                matern_rank["best_cells"]
            ),
            "matern_mean_rank": float(matern_rank["mean_rank"]),
        },
        "hyperparameter_stability": {
            "fold_registry_rows": int(len(fold_parameters)),
            "full_registry_rows": int(len(full_parameters)),
            "matern_maximum_rule_specific_length_scale_cv": (
                maximum_length_cv
            ),
            "matern_maximum_rule_specific_noise_level_cv": (
                maximum_noise_cv
            ),
            "matern_full_fit_length_scale_within_fold_range_rules": (
                full_length_within
            ),
            "matern_full_fit_noise_level_within_fold_range_rules": (
                full_noise_within
            ),
            "interpretation": (
                "descriptive fold-to-fold stability; no new model "
                "selection or June refit"
            ),
        },
        "figures": [rel(path) for path in figure_paths],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "status": "PASSED",
    }

    write_csv(
        OUT / "phase18_model_scores_by_rule.csv",
        scores_by_rule,
    )
    write_csv(
        OUT / "phase18_model_scores_by_block.csv",
        scores_by_block,
    )
    write_csv(
        OUT / "phase18_model_scores_by_rule_block.csv",
        scores_by_rule_block,
    )
    write_csv(
        OUT / "phase18_paired_model_differences.csv",
        paired,
    )
    write_csv(
        OUT / "phase18_rule_block_rankings.csv",
        rankings,
    )
    write_csv(
        OUT / "phase18_model_rank_stability.csv",
        rank_summary,
    )
    write_csv(
        OUT / "phase18_gp_fold_hyperparameters.csv",
        fold_parameters,
    )
    write_csv(
        OUT / "phase18_replay_prediction_reconciliation.csv",
        replay_reconciliation,
    )
    write_csv(
        OUT / "phase18_gp_full_fit_hyperparameters.csv",
        full_parameters,
    )
    write_csv(
        OUT / "phase18_gp_hyperparameter_stability.csv",
        parameter_stability,
    )
    write_csv(
        OUT / "phase18_gap_updates.csv",
        gap_updates,
    )
    write_json(
        CONFIG / "phase18_gp_stability_spec.json",
        spec,
    )

    rule_table = rule_matern_static[
        [
            "scope_value",
            "mean_difference_c",
            "bootstrap_lower_95_c",
            "bootstrap_upper_95_c",
        ]
    ].rename(
        columns={"scope_value": "decision_rule"}
    )
    block_table = block_matern_static[
        [
            "scope_value",
            "mean_difference_c",
            "bootstrap_lower_95_c",
            "bootstrap_upper_95_c",
        ]
    ].rename(
        columns={"scope_value": "validation_block"}
    )

    report_lines = [
        "# Phase 18 Rule and Validation-Block GP Stability",
        "",
        "## Status",
        "",
        "PASSED",
        "",
        "## Purpose",
        "",
        "Phase 16 established the aggregate ordering of the raw point forecast, static Gaussian correction, RBF GP and Matérn-3/2 GP. Phase 18 tests whether that ordering is concentrated in a single decision rule or validation period and reconciles fold-specific GP hyperparameters with the saved full-history Matérn models.",
        "",
        "## Exact comparison support",
        "",
        "- Validation dates: 365.",
        "- Decision rules: 4.",
        "- Chronological validation blocks: 4.",
        "- Models: raw point, static Gaussian, RBF GP and Matérn-3/2 GP.",
        "- Model rows: 5,840.",
        "- Every date-rule key contains all four models.",
        "- Paired uncertainty intervals resample target dates 10,000 times.",
        "",
        "## Exact replay of the 32 Phase 7 fold fits",
        "",
        "The fold-specific fitted model objects were not persisted in Phase 7. Phase 18 therefore reruns the original Phase 7 source in an isolated temporary copy of the repository while instrumenting scikit-learn's GaussianProcessRegressor.fit method. The replay does not alter the certified repository outputs.",
        "",
        f"- Replayed fold models: {len(fold_parameters)}.",
        f"- Reconciled numeric prediction columns: {len(replay_reconciliation)}.",
        f"- Maximum absolute replay-versus-certified prediction discrepancy: {float(replay_reconciliation['maximum_absolute_error'].max()):.3e}.",
        "- Every replayed fit is mapped one-to-one to a certified fold, rule and kernel through its training-response hash and recorded date range.",
        "- Hyperparameter stability is reported only after the replay reproduces the frozen Phase 7 predictions within the stated numerical tolerances.",
        "",
        "## Overall paired results",
        "",
        (
            f"- Matérn-3/2 minus static Gaussian CRPS: "
            f"{float(overall_matern_static['mean_difference_c']):.6f} °C "
            f"with 95% date-bootstrap interval "
            f"[{float(overall_matern_static['bootstrap_lower_95_c']):.6f}, "
            f"{float(overall_matern_static['bootstrap_upper_95_c']):.6f}]."
        ),
        (
            f"- Matérn-3/2 minus RBF CRPS: "
            f"{float(overall_matern_rbf['mean_difference_c']):.6f} °C "
            f"with 95% date-bootstrap interval "
            f"[{float(overall_matern_rbf['bootstrap_lower_95_c']):.6f}, "
            f"{float(overall_matern_rbf['bootstrap_upper_95_c']):.6f}]."
        ),
        "- Every difference is first-model minus second-model CRPS; negative favours the first model.",
        "",
        "## Matérn-3/2 improvement over the static Gaussian benchmark by rule",
        "",
    ]
    report_lines.extend(
        markdown_table(
            rule_table,
            [
                "decision_rule",
                "mean_difference_c",
                "bootstrap_lower_95_c",
                "bootstrap_upper_95_c",
            ],
            [
                "Decision rule",
                "Mean difference (°C)",
                "95% lower",
                "95% upper",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            "## Matérn-3/2 improvement over the static Gaussian benchmark by validation block",
            "",
        ]
    )
    report_lines.extend(
        markdown_table(
            block_table,
            [
                "validation_block",
                "mean_difference_c",
                "bootstrap_lower_95_c",
                "bootstrap_upper_95_c",
            ],
            [
                "Validation block",
                "Mean difference (°C)",
                "95% lower",
                "95% upper",
            ],
            decimals=5,
        )
    )
    report_lines.extend(
        [
            "",
            "## Stability counts",
            "",
            f"- Matérn-3/2 has lower mean CRPS than static Gaussian in {matern_better_static_rules} of 4 decision rules.",
            f"- Matérn-3/2 has lower mean CRPS than static Gaussian in {matern_better_static_blocks} of 4 validation blocks.",
            f"- Matérn-3/2 has lower mean CRPS than static Gaussian in {matern_better_static_cells} of 16 rule-by-block cells.",
            f"- Matérn-3/2 has lower mean CRPS than RBF in {matern_better_rbf_cells} of 16 rule-by-block cells.",
            f"- Matérn-3/2 is the lowest-CRPS model in {int(matern_rank['best_cells'])} of 16 cells, with mean rank {float(matern_rank['mean_rank']):.3f}.",
            "",
            "These counts are descriptive stability diagnostics. A cell-level sign does not by itself establish independent statistical evidence because blocks and decision rules share target dates and underlying weather conditions.",
            "",
            "## GP hyperparameter stability",
            "",
            "- Fold models reconciled: 32, comprising two kernel families, four rules and four chronological folds.",
            "- Saved full-history models reconciled: 4 selected Matérn-3/2 models.",
            f"- Largest rule-specific Matérn length-scale coefficient of variation across folds: {maximum_length_cv:.6f}.",
            f"- Largest rule-specific Matérn WhiteKernel-noise coefficient of variation across folds: {maximum_noise_cv:.6f}.",
            f"- Full-history Matérn length scale lies within the corresponding four-fold range for {full_length_within} of 4 rules.",
            f"- Full-history Matérn noise level lies within the corresponding four-fold range for {full_noise_within} of 4 rules.",
            "- Exact fold and full-fit values are stored in the Phase 18 hyperparameter registries; no rounded report value is used for calculation.",
            "",
            "## Interpretation",
            "",
            "The GP contribution should not be described only through the aggregate Phase 16 mean. Phase 18 separates performance by decision rule and chronological block, showing where the Matérn improvement over static correction is persistent and where it weakens or reverses. This is the appropriate evidential basis for claiming conditional residual structure rather than merely a better aggregate average.",
            "",
            "Fold-to-fold movement in the fitted signal variance, length scale and WhiteKernel noise quantifies estimation sensitivity. The comparison with the four saved full-history models shows whether the final fitted parameters are consistent with the ranges observed under chronological validation.",
            "",
            "## Closed Phase 14 gaps",
            "",
            "- G08: rule and validation-block model results.",
            "- G09: GP hyperparameter stability.",
            "",
            "## Evidential boundary",
            "",
            "Phase 18 does not refit, reselect or modify any certified GP. June observations and market prices do not enter the weather-only model comparison. Bootstrap intervals use target dates as the resampling unit and remain descriptive under the current serial-dependence assumptions. Predictive coverage, calibration, heteroskedasticity and residual dependence are reserved for Phase 19.",
            "",
        ]
    )

    (OUT / "phase18_gp_stability_report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("PHASE18_STATUS=PASSED")
    print(f"PHASE18_MODEL_ROWS={len(predictions)}")
    print(f"PHASE18_RULE_SCORE_ROWS={len(scores_by_rule)}")
    print(f"PHASE18_BLOCK_SCORE_ROWS={len(scores_by_block)}")
    print(
        f"PHASE18_RULE_BLOCK_SCORE_ROWS="
        f"{len(scores_by_rule_block)}"
    )
    print(f"PHASE18_PAIRED_ROWS={len(paired)}")
    print(f"PHASE18_FOLD_HYPERPARAMETER_ROWS={len(fold_parameters)}")
    print(
        "PHASE18_REPLAY_MAX_ERROR="
        f"{float(replay_reconciliation['maximum_absolute_error'].max()):.12e}"
    )
    print(f"PHASE18_FULL_HYPERPARAMETER_ROWS={len(full_parameters)}")
    print(
        "PHASE18_STABILITY_COUNTS="
        + json.dumps(
            {
                "matern_better_static_rules": matern_better_static_rules,
                "matern_better_static_blocks": matern_better_static_blocks,
                "matern_better_static_cells": matern_better_static_cells,
                "matern_better_rbf_cells": matern_better_rbf_cells,
                "matern_best_cells": int(matern_rank["best_cells"]),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
