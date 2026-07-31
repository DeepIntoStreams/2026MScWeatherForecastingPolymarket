#!/usr/bin/env python3
"""
Phase 5: calibration and GP misspecification diagnostics.

The phase is diagnostic only. It reads the accepted chronological validation
predictions and the frozen Phase 19 evidence, and does not fit, tune, select or
alter any forecasting model.

It produces:
- selected-model row-level and date-level diagnostic panels;
- central coverage, interval width and date/block bootstrap sensitivity;
- 1%-99% quantile calibration curves and summaries;
- PIT summaries and histograms;
- standardised residual moments under explicit aggregation conventions;
- within-rule and date-balanced serial-dependence diagnostics;
- lag-one circular moving-block intervals for 3, 5, 7 and 14 days;
- cross-rule residual correlations;
- predictive-scale quartile diagnostics;
- exact extraction of the frozen date-clustered variance regression;
- a reconciliation register, thesis-ready tables, figures and review bundle.

Any discrepancy between direct row-level reconstruction and a frozen Phase 19
headline is surfaced explicitly rather than silently overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    raise RuntimeError("matplotlib is required") from exc

try:
    from scipy import stats
except Exception as exc:  # pragma: no cover
    raise RuntimeError("scipy is required") from exc


MODEL_ORDER = ["rbf", "matern"]
MODEL_LABELS = {
    "rbf": "RBF GP",
    "matern": "Matérn-3/2 GP",
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
    "event_day_open": "Event-day open",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed\nSTDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalise_model(value: Any) -> str:
    text = str(value).strip().lower()
    if "matern" in text or "mat32" in text:
        return "matern"
    if "rbf" in text or "squared" in text or "radial" in text:
        return "rbf"
    return text


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "1": True,
            "yes": True,
            "passed": True,
            "false": False,
            "0": False,
            "no": False,
            "failed": False,
        })
        .fillna(False)
        .astype(bool)
    )


def dependency_check(path: Path, label: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing={path}"
    frame = pd.read_csv(path)
    if not {"critical", "passed"}.issubset(frame.columns):
        return False, f"{label} table lacks critical/passed columns"
    critical = bool_series(frame["critical"])
    passed = bool_series(frame["passed"])
    failed = frame.loc[critical & ~passed]
    return failed.empty, f"critical_failures={len(failed)}"


def assign_chronological_blocks(
    dates: Sequence[str],
    sizes: Sequence[int],
) -> pd.DataFrame:
    ordered = pd.DataFrame(
        {"target_date": sorted(pd.Series(dates).astype(str).unique())}
    )
    if sum(map(int, sizes)) != len(ordered):
        raise ValueError(
            f"Block sizes sum to {sum(map(int, sizes))}; dates={len(ordered)}"
        )
    labels: list[int] = []
    positions: list[int] = []
    for block, size in enumerate(sizes, start=1):
        labels.extend([block] * int(size))
        positions.extend(range(1, int(size) + 1))
    ordered["validation_block"] = labels
    ordered["position_within_block"] = positions
    ordered["chronological_index"] = np.arange(1, len(ordered) + 1)
    return ordered


def ordinary_indices(
    n: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    return rng.integers(0, n, size=(replications, n), dtype=np.int64)


def moving_block_indices(
    n: int,
    block_length: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if n <= 0 or block_length <= 0:
        raise ValueError("n and block_length must be positive")
    blocks_needed = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(replications, blocks_needed))
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % n
    return indices.reshape(replications, -1)[:, :n]


def percentile_interval(
    values: np.ndarray,
    confidence: float,
) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    alpha = 1.0 - confidence
    return (
        float(np.quantile(finite, alpha / 2.0)),
        float(np.quantile(finite, 1.0 - alpha / 2.0)),
    )


def sample_standard_deviation(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    return float(np.std(array, ddof=1))


def rowwise_lag1_correlation(sampled: np.ndarray) -> np.ndarray:
    array = np.asarray(sampled, dtype=float)
    if array.ndim != 2 or array.shape[1] < 3:
        return np.full(array.shape[0], np.nan)
    x = array[:, :-1]
    y = array[:, 1:]
    x_centered = x - x.mean(axis=1, keepdims=True)
    y_centered = y - y.mean(axis=1, keepdims=True)
    numerator = np.sum(x_centered * y_centered, axis=1)
    denominator = np.sqrt(
        np.sum(x_centered ** 2, axis=1)
        * np.sum(y_centered ** 2, axis=1)
    )
    return np.divide(
        numerator,
        denominator,
        out=np.full(array.shape[0], np.nan, dtype=float),
        where=denominator > 0,
    )


def autocorrelation(values: np.ndarray, lag: int) -> float:
    array = np.asarray(values, dtype=float)
    if lag <= 0 or lag >= len(array):
        return np.nan
    return float(np.corrcoef(array[:-lag], array[lag:])[0, 1])


def ljung_box(values: np.ndarray, max_lag: int) -> tuple[float, float]:
    array = np.asarray(values, dtype=float)
    n = len(array)
    if max_lag <= 0 or n <= max_lag + 1:
        return np.nan, np.nan
    correlations = np.array(
        [autocorrelation(array, lag) for lag in range(1, max_lag + 1)],
        dtype=float,
    )
    terms = correlations ** 2 / (n - np.arange(1, max_lag + 1))
    statistic = float(n * (n + 2) * np.nansum(terms))
    p_value = float(stats.chi2.sf(statistic, max_lag))
    return statistic, p_value


def scope_label(row: pd.Series) -> str:
    scope = str(row.get("scope", "")).strip().lower()
    value = str(row.get("scope_value", "")).strip().lower()
    combined = f"{scope} {value}"
    if "overall" in combined or "all_" in combined or value in {
        "all",
        "all_dates",
        "all_date_rule_rows",
    }:
        return "overall"
    for rule in RULE_ORDER:
        if rule.lower() in combined:
            return rule
    return value or scope


def load_phase19_tables(
    frozen_root: Path,
    config: Mapping[str, Any],
) -> dict[str, pd.DataFrame]:
    root = frozen_root / config["input_paths"]["phase19_root"]
    tables: dict[str, pd.DataFrame] = {}
    for filename in config["phase19_files"]:
        path = root / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        tables[filename] = pd.read_csv(path, low_memory=False)
    return tables


def validate_inputs(
    loss_panel: pd.DataFrame,
    phase19: Mapping[str, pd.DataFrame],
    config: Mapping[str, Any],
    repo_root: Path,
) -> pd.DataFrame:
    expected = config["expected"]
    tolerance = float(config["numerical_tolerance"])
    checks: list[dict[str, Any]] = []

    def add(
        check: str,
        passed: bool,
        detail: str,
        critical: bool = True,
    ) -> None:
        checks.append(
            {
                "check": check,
                "passed": bool(passed),
                "critical": bool(critical),
                "detail": detail,
            }
        )

    for label, key in [
        ("Phase 1", "phase1_completion"),
        ("Phase 2", "phase2_integrity"),
        ("Phase 3", "phase3_integrity"),
        ("Phase 4", "phase4_integrity"),
    ]:
        passed, detail = dependency_check(
            repo_root / config["input_paths"][key],
            label,
        )
        add(f"{label.lower().replace(' ', '')}_dependency", passed, detail)

    required = {
        "target_date",
        "decision_rule",
        "model",
        "crps_c",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "temperature_predictive_mean_c",
        "predictive_standard_deviation_c",
        "residual_predictive_mean_c",
    }
    missing = sorted(required - set(loss_panel.columns))
    add("loss_panel_required_columns", not missing, f"missing={missing}")
    if missing:
        return pd.DataFrame(checks)

    panel = loss_panel.copy()
    panel["model"] = panel["model"].map(normalise_model)
    panel = panel.loc[panel["model"].isin(expected["models"])].copy()
    panel["target_date"] = pd.to_datetime(
        panel["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    panel["decision_rule"] = panel["decision_rule"].astype(str)

    add("gp_expected_rows", len(panel) == expected["gp_rows"], f"rows={len(panel)}")
    add(
        "gp_expected_dates",
        panel["target_date"].nunique() == expected["validation_dates"],
        f"dates={panel['target_date'].nunique()}",
    )
    add(
        "gp_expected_models",
        set(panel["model"].unique()) == set(expected["models"]),
        f"models={sorted(panel['model'].unique())}",
    )
    add(
        "gp_expected_rules",
        set(panel["decision_rule"].unique())
        == set(expected["decision_rules"]),
        f"rules={sorted(panel['decision_rule'].unique())}",
    )

    model_counts = panel["model"].value_counts().to_dict()
    rule_model_counts = (
        panel.groupby(["model", "decision_rule"]).size().to_dict()
    )
    add(
        "rows_per_model",
        all(
            model_counts.get(model, 0) == expected["rows_per_model"]
            for model in expected["models"]
        ),
        f"counts={model_counts}",
    )
    add(
        "rows_per_rule_model",
        all(
            rule_model_counts.get((model, rule), 0)
            == expected["rows_per_rule_model"]
            for model in expected["models"]
            for rule in expected["decision_rules"]
        ),
        f"counts={rule_model_counts}",
    )

    duplicates = int(
        panel.duplicated(
            ["target_date", "decision_rule", "model"]
        ).sum()
    )
    add("gp_unique_keys", duplicates == 0, f"duplicates={duplicates}")

    numeric = [
        "crps_c",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "temperature_predictive_mean_c",
        "predictive_standard_deviation_c",
        "residual_predictive_mean_c",
    ]
    for column in numeric:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")

    add(
        "gp_numeric_finite",
        bool(np.isfinite(panel[numeric].to_numpy(dtype=float)).all()),
        "",
    )
    add(
        "gp_predictive_sd_positive",
        bool((panel["predictive_standard_deviation_c"] > 0).all()),
        (
            f"minimum_sd="
            f"{panel['predictive_standard_deviation_c'].min():.9f}"
        ),
    )
    add(
        "gp_crps_nonnegative",
        bool((panel["crps_c"] >= -tolerance).all()),
        f"minimum_crps={panel['crps_c'].min():.9f}",
    )

    add(
        "all_phase19_files_loaded",
        set(phase19) == set(config["phase19_files"]),
        f"files={len(phase19)}",
    )
    reconciliation = phase19["phase19_reconciliation_checks.csv"]
    if "passed" in reconciliation.columns:
        passed = bool(bool_series(reconciliation["passed"]).all())
        add(
            "frozen_phase19_reconciliation_passed",
            passed,
            f"failed={int((~bool_series(reconciliation['passed'])).sum())}",
        )
    else:
        add(
            "frozen_phase19_reconciliation_has_passed_column",
            False,
            f"columns={list(reconciliation.columns)}",
        )

    regression = phase19["phase19_variance_regression_summary.csv"]
    coefficients = phase19["phase19_variance_regression_coefficients.csv"]
    add(
        "phase19_variance_regression_rows",
        len(regression)
        == expected["phase19_variance_regression_rows"],
        f"rows={len(regression)}",
    )
    add(
        "phase19_variance_coefficient_rows",
        len(coefficients)
        == expected["phase19_variance_coefficient_rows"],
        f"rows={len(coefficients)}",
    )

    return pd.DataFrame(checks)


def prepare_panel(
    loss_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = loss_panel.copy()
    panel["model"] = panel["model"].map(normalise_model)
    panel = panel.loc[panel["model"].isin(MODEL_ORDER)].copy()
    panel["target_date"] = pd.to_datetime(
        panel["target_date"]
    ).dt.strftime("%Y-%m-%d")
    panel["decision_rule"] = panel["decision_rule"].astype(str)

    numeric = [
        "crps_c",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "temperature_predictive_mean_c",
        "predictive_standard_deviation_c",
        "residual_predictive_mean_c",
    ]
    for column in numeric:
        panel[column] = pd.to_numeric(panel[column], errors="raise")

    panel["standardised_residual"] = (
        panel["hko_daily_max_c"]
        - panel["temperature_predictive_mean_c"]
    ) / panel["predictive_standard_deviation_c"]
    panel["absolute_standardised_residual"] = panel[
        "standardised_residual"
    ].abs()
    panel["squared_standardised_residual"] = (
        panel["standardised_residual"] ** 2
    )
    panel["pit"] = stats.norm.cdf(panel["standardised_residual"])

    for level in map(float, config["coverage_levels"]):
        alpha = 1.0 - level
        multiplier = float(stats.norm.ppf(1.0 - alpha / 2.0))
        suffix = str(int(round(100 * level)))
        panel[f"central_{suffix}_lower_c"] = (
            panel["temperature_predictive_mean_c"]
            - multiplier * panel["predictive_standard_deviation_c"]
        )
        panel[f"central_{suffix}_upper_c"] = (
            panel["temperature_predictive_mean_c"]
            + multiplier * panel["predictive_standard_deviation_c"]
        )
        panel[f"central_{suffix}_covered"] = (
            (panel["hko_daily_max_c"] >= panel[f"central_{suffix}_lower_c"])
            & (panel["hko_daily_max_c"] <= panel[f"central_{suffix}_upper_c"])
        )
        panel[f"central_{suffix}_width_c"] = (
            panel[f"central_{suffix}_upper_c"]
            - panel[f"central_{suffix}_lower_c"]
        )

    block_map = assign_chronological_blocks(
        panel["target_date"].unique(),
        config["expected"]["chronological_block_sizes"],
    )
    panel = panel.merge(
        block_map,
        on="target_date",
        how="left",
        validate="many_to_one",
    )
    panel["rule_order"] = panel["decision_rule"].map(
        {rule: index for index, rule in enumerate(RULE_ORDER)}
    )
    panel["model_order"] = panel["model"].map(
        {model: index for index, model in enumerate(MODEL_ORDER)}
    )
    panel = panel.sort_values(
        ["model_order", "target_date", "rule_order"]
    ).reset_index(drop=True)

    aggregations = {
        "mean_standardised_residual": (
            "standardised_residual", "mean"
        ),
        "mean_absolute_standardised_residual": (
            "absolute_standardised_residual", "mean"
        ),
        "mean_squared_standardised_residual": (
            "squared_standardised_residual", "mean"
        ),
        "mean_pit": ("pit", "mean"),
        "mean_crps_c": ("crps_c", "mean"),
        "mean_predictive_standard_deviation_c": (
            "predictive_standard_deviation_c", "mean"
        ),
        "mean_predictive_mean_c": (
            "temperature_predictive_mean_c", "mean"
        ),
        "mean_hko_c": ("hko_daily_max_c", "mean"),
    }
    for level in map(float, config["coverage_levels"]):
        suffix = str(int(round(100 * level)))
        aggregations[f"central_{suffix}_coverage_fraction"] = (
            f"central_{suffix}_covered", "mean"
        )
        aggregations[f"mean_central_{suffix}_width_c"] = (
            f"central_{suffix}_width_c", "mean"
        )

    named_agg = {
        output: pd.NamedAgg(column=column, aggfunc=function)
        for output, (column, function) in aggregations.items()
    }
    date_panel = (
        panel.groupby(
            ["model", "target_date", "validation_block"],
            as_index=False,
        )
        .agg(**named_agg)
        .sort_values(["model", "target_date"])
    )

    selected = panel.loc[panel["model"] == "matern"].copy()
    return panel, date_panel, selected


def iter_scopes(
    panel: pd.DataFrame,
    include_blocks: bool = True,
):
    yield "overall", "all_dates", panel
    for rule in RULE_ORDER:
        yield "decision_rule", rule, panel.loc[
            panel["decision_rule"] == rule
        ]
    if include_blocks:
        for block in sorted(panel["validation_block"].unique()):
            yield (
                "validation_block",
                f"block_{int(block)}",
                panel.loc[panel["validation_block"] == block],
            )


def coverage_summary(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model in MODEL_ORDER:
        model_frame = panel.loc[panel["model"] == model]
        for scope_type, scope_value, group in iter_scopes(
            model_frame,
            include_blocks=True,
        ):
            for level in map(float, config["coverage_levels"]):
                suffix = str(int(round(100 * level)))
                covered = group[f"central_{suffix}_covered"].astype(float)
                width = group[f"central_{suffix}_width_c"].astype(float)
                rows.append(
                    {
                        "model": model,
                        "scope_type": scope_type,
                        "scope_value": scope_value,
                        "nominal_coverage": level,
                        "rows": len(group),
                        "dates": int(group["target_date"].nunique()),
                        "decision_rules": int(
                            group["decision_rule"].nunique()
                        ),
                        "empirical_coverage": float(covered.mean()),
                        "coverage_error": float(covered.mean() - level),
                        "mean_interval_width_c": float(width.mean()),
                        "median_interval_width_c": float(width.median()),
                        "q10_interval_width_c": float(width.quantile(0.10)),
                        "q90_interval_width_c": float(width.quantile(0.90)),
                    }
                )
    return pd.DataFrame(rows)


def coverage_bootstrap(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reps = int(config["bootstrap"]["replications"])
    seed = int(config["bootstrap"]["seed"])
    confidence = float(config["bootstrap"]["confidence_level"])
    chunk_size = int(config["bootstrap"]["chunk_size"])
    block_lengths = list(
        map(int, config["bootstrap"]["moving_block_lengths"])
    )
    levels = list(map(float, config["coverage_levels"]))
    rows: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []

    scope_counter = 0
    for model in MODEL_ORDER:
        model_frame = panel.loc[panel["model"] == model]
        for scope_type, scope_value, group in iter_scopes(
            model_frame,
            include_blocks=False,
        ):
            dates = sorted(group["target_date"].unique())
            rule_columns = (
                RULE_ORDER if scope_type == "overall" else [scope_value]
            )
            coverage_arrays = []
            width_arrays = []
            for level in levels:
                suffix = str(int(round(100 * level)))
                coverage_pivot = (
                    group.pivot(
                        index="target_date",
                        columns="decision_rule",
                        values=f"central_{suffix}_covered",
                    )
                    .reindex(index=dates, columns=rule_columns)
                )
                width_pivot = (
                    group.pivot(
                        index="target_date",
                        columns="decision_rule",
                        values=f"central_{suffix}_width_c",
                    )
                    .reindex(index=dates, columns=rule_columns)
                )
                if coverage_pivot.isna().any().any():
                    raise ValueError(
                        f"Incomplete coverage pivot: {model} {scope_value}"
                    )
                coverage_arrays.append(
                    coverage_pivot.to_numpy(dtype=float)
                )
                width_arrays.append(width_pivot.to_numpy(dtype=float))
            coverage_cube = np.stack(coverage_arrays, axis=2)
            width_cube = np.stack(width_arrays, axis=2)
            n_dates = len(dates)

            methods: list[tuple[str, int | None]] = [
                ("ordinary_date", None)
            ]
            methods.extend(
                ("circular_moving_block", block)
                for block in block_lengths
            )

            point_coverage = coverage_cube.mean(axis=(0, 1))
            point_width = width_cube.mean(axis=(0, 1))
            for method_index, (method, block_length) in enumerate(
                methods
            ):
                local_seed = (
                    seed
                    + scope_counter * 1000
                    + method_index * 100
                )
                rng = np.random.default_rng(local_seed)
                coverage_parts: list[np.ndarray] = []
                width_parts: list[np.ndarray] = []
                null_parts: list[np.ndarray] = []
                centred = (
                    coverage_cube
                    - point_coverage[None, None, :]
                )

                completed = 0
                while completed < reps:
                    current = min(chunk_size, reps - completed)
                    if method == "ordinary_date":
                        indices = ordinary_indices(
                            n_dates, current, rng
                        )
                    else:
                        assert block_length is not None
                        indices = moving_block_indices(
                            n_dates,
                            block_length,
                            current,
                            rng,
                        )
                    sampled_coverage = coverage_cube[indices, :, :]
                    sampled_width = width_cube[indices, :, :]
                    coverage_parts.append(
                        sampled_coverage.mean(axis=(1, 2))
                    )
                    width_parts.append(
                        sampled_width.mean(axis=(1, 2))
                    )
                    null_parts.append(
                        centred[indices, :, :].mean(axis=(1, 2))
                    )
                    completed += current

                coverage_distribution = np.concatenate(
                    coverage_parts, axis=0
                )
                width_distribution = np.concatenate(
                    width_parts, axis=0
                )
                null_distribution = np.concatenate(
                    null_parts, axis=0
                )
                for level_index, level in enumerate(levels):
                    coverage_lower, coverage_upper = percentile_interval(
                        coverage_distribution[:, level_index],
                        confidence,
                    )
                    width_lower, width_upper = percentile_interval(
                        width_distribution[:, level_index],
                        confidence,
                    )
                    rows.extend(
                        [
                            {
                                "model": model,
                                "scope_type": scope_type,
                                "scope_value": scope_value,
                                "dates": n_dates,
                                "nominal_coverage": level,
                                "metric": "empirical_coverage",
                                "point_estimate": float(
                                    point_coverage[level_index]
                                ),
                                "bootstrap_method": method,
                                "block_length_days": block_length,
                                "bootstrap_lower_95": coverage_lower,
                                "bootstrap_upper_95": coverage_upper,
                                "bootstrap_replications": reps,
                                "seed": local_seed,
                                "bootstrap_unit": "settlement_date",
                            },
                            {
                                "model": model,
                                "scope_type": scope_type,
                                "scope_value": scope_value,
                                "dates": n_dates,
                                "nominal_coverage": level,
                                "metric": "mean_interval_width_c",
                                "point_estimate": float(
                                    point_width[level_index]
                                ),
                                "bootstrap_method": method,
                                "block_length_days": block_length,
                                "bootstrap_lower_95": width_lower,
                                "bootstrap_upper_95": width_upper,
                                "bootstrap_replications": reps,
                                "seed": local_seed,
                                "bootstrap_unit": "settlement_date",
                            },
                        ]
                    )
                    observed_error = (
                        point_coverage[level_index] - level
                    )
                    null_values = null_distribution[:, level_index]
                    p_value = float(
                        (
                            1
                            + np.sum(
                                np.abs(null_values)
                                >= abs(observed_error)
                            )
                        )
                        / (reps + 1)
                    )
                    tests.append(
                        {
                            "model": model,
                            "scope_type": scope_type,
                            "scope_value": scope_value,
                            "dates": n_dates,
                            "nominal_coverage": level,
                            "null_hypothesis": (
                                "empirical_coverage_equals_nominal"
                            ),
                            "observed_coverage_error": float(
                                observed_error
                            ),
                            "bootstrap_method": method,
                            "block_length_days": block_length,
                            "two_sided_centred_bootstrap_p_value": p_value,
                            "minimum_resolvable_p_value": 1.0 / (reps + 1),
                            "bootstrap_replications": reps,
                            "seed": local_seed,
                            "bootstrap_unit": "settlement_date",
                        }
                    )
            scope_counter += 1

    return pd.DataFrame(rows), pd.DataFrame(tests)


def quantile_calibration(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    grid = config["quantile_grid"]
    probabilities = np.round(
        np.arange(
            float(grid["start"]),
            float(grid["stop"]) + 0.5 * float(grid["step"]),
            float(grid["step"]),
        ),
        10,
    )
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for model in MODEL_ORDER:
        model_frame = panel.loc[panel["model"] == model]
        for scope_type, scope_value, group in iter_scopes(
            model_frame,
            include_blocks=False,
        ):
            z = group["standardised_residual"].to_numpy(dtype=float)
            errors: list[float] = []
            for probability in probabilities:
                empirical = float(
                    np.mean(z <= stats.norm.ppf(probability))
                )
                error = empirical - float(probability)
                errors.append(error)
                rows.append(
                    {
                        "model": model,
                        "scope_type": scope_type,
                        "scope_value": scope_value,
                        "nominal_probability": float(probability),
                        "empirical_probability": empirical,
                        "calibration_error": error,
                        "absolute_calibration_error": abs(error),
                        "squared_calibration_error": error ** 2,
                        "rows": len(group),
                        "dates": int(group["target_date"].nunique()),
                    }
                )
            error_array = np.asarray(errors, dtype=float)
            summaries.append(
                {
                    "model": model,
                    "scope_type": scope_type,
                    "scope_value": scope_value,
                    "nominal_points": len(probabilities),
                    "rows": len(group),
                    "dates": int(group["target_date"].nunique()),
                    "integrated_absolute_calibration_error": float(
                        np.mean(np.abs(error_array))
                    ),
                    "root_mean_squared_calibration_error": float(
                        np.sqrt(np.mean(error_array ** 2))
                    ),
                    "maximum_absolute_calibration_error": float(
                        np.max(np.abs(error_array))
                    ),
                    "mean_signed_calibration_error": float(
                        np.mean(error_array)
                    ),
                    "calibration_error_q10": float(
                        np.quantile(error_array, 0.10)
                    ),
                    "calibration_error_q50": float(
                        np.quantile(error_array, 0.50)
                    ),
                    "calibration_error_q90": float(
                        np.quantile(error_array, 0.90)
                    ),
                }
            )

    return pd.DataFrame(rows), pd.DataFrame(summaries)


def standardised_residual_summary(
    panel: pd.DataFrame,
    date_panel: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add_summary(
        model: str,
        scope_type: str,
        scope_value: str,
        aggregation: str,
        values: np.ndarray,
        rows_count: int,
        dates_count: int,
    ) -> None:
        array = np.asarray(values, dtype=float)
        rows.append(
            {
                "model": model,
                "scope_type": scope_type,
                "scope_value": scope_value,
                "aggregation": aggregation,
                "rows": rows_count,
                "dates": dates_count,
                "mean": float(np.mean(array)),
                "variance": float(np.var(array, ddof=1)),
                "standard_deviation": float(np.std(array, ddof=1)),
                "rmse": float(np.sqrt(np.mean(array ** 2))),
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
                    np.mean(np.abs(array) > 1.645)
                ),
                "proportion_absolute_above_1_96": float(
                    np.mean(np.abs(array) > 1.96)
                ),
                "proportion_absolute_above_2_576": float(
                    np.mean(np.abs(array) > 2.576)
                ),
            }
        )

    for model in MODEL_ORDER:
        model_rows = panel.loc[panel["model"] == model]
        add_summary(
            model,
            "overall",
            "all_dates",
            "all_date_rule_rows",
            model_rows["standardised_residual"].to_numpy(dtype=float),
            len(model_rows),
            int(model_rows["target_date"].nunique()),
        )
        model_dates = date_panel.loc[date_panel["model"] == model]
        add_summary(
            model,
            "overall",
            "all_dates",
            "date_mean_across_rules",
            model_dates["mean_standardised_residual"].to_numpy(
                dtype=float
            ),
            len(model_dates),
            len(model_dates),
        )
        for rule in RULE_ORDER:
            group = model_rows.loc[
                model_rows["decision_rule"] == rule
            ]
            add_summary(
                model,
                "decision_rule",
                rule,
                "within_rule_chronological_rows",
                group["standardised_residual"].to_numpy(dtype=float),
                len(group),
                int(group["target_date"].nunique()),
            )
        for block in sorted(model_rows["validation_block"].unique()):
            group = model_rows.loc[
                model_rows["validation_block"] == block
            ]
            add_summary(
                model,
                "validation_block",
                f"block_{int(block)}",
                "all_date_rule_rows_within_block",
                group["standardised_residual"].to_numpy(dtype=float),
                len(group),
                int(group["target_date"].nunique()),
            )

    return pd.DataFrame(rows)


def pit_diagnostics(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bins = int(config["pit_bins"])
    summary_rows: list[dict[str, Any]] = []
    histogram_rows: list[dict[str, Any]] = []

    for model in MODEL_ORDER:
        model_frame = panel.loc[panel["model"] == model]
        for scope_type, scope_value, group in iter_scopes(
            model_frame,
            include_blocks=False,
        ):
            pit = group["pit"].to_numpy(dtype=float)
            ks = stats.kstest(pit, "uniform")
            cvm = stats.cramervonmises(pit, "uniform")
            counts, edges = np.histogram(
                pit, bins=bins, range=(0.0, 1.0)
            )
            expected = len(pit) / bins
            chi_square = float(
                np.sum((counts - expected) ** 2 / expected)
            )
            chi_p = float(stats.chi2.sf(chi_square, bins - 1))
            summary_rows.append(
                {
                    "model": model,
                    "scope_type": scope_type,
                    "scope_value": scope_value,
                    "rows": len(group),
                    "dates": int(group["target_date"].nunique()),
                    "mean_pit": float(np.mean(pit)),
                    "variance_pit": float(np.var(pit, ddof=1)),
                    "variance_error_from_uniform": float(
                        np.var(pit, ddof=1) - 1.0 / 12.0
                    ),
                    "mean_absolute_deviation_from_half": float(
                        np.mean(np.abs(pit - 0.5))
                    ),
                    "ks_statistic": float(ks.statistic),
                    "ks_nominal_iid_p_value": float(ks.pvalue),
                    "cramer_von_mises_statistic": float(cvm.statistic),
                    "cramer_von_mises_nominal_iid_p_value": float(
                        cvm.pvalue
                    ),
                    "ten_bin_chi_square": chi_square,
                    "ten_bin_nominal_iid_p_value": chi_p,
                    "p_value_interpretation": (
                        "Nominal IID diagnostics only; date clustering and "
                        "serial dependence are assessed separately."
                    ),
                }
            )
            for bin_index in range(bins):
                proportion = float(counts[bin_index] / len(pit))
                histogram_rows.append(
                    {
                        "model": model,
                        "scope_type": scope_type,
                        "scope_value": scope_value,
                        "bin_number": bin_index + 1,
                        "lower_bound": float(edges[bin_index]),
                        "upper_bound": float(edges[bin_index + 1]),
                        "count": int(counts[bin_index]),
                        "proportion": proportion,
                        "uniform_reference_proportion": 1.0 / bins,
                        "proportion_error": proportion - 1.0 / bins,
                    }
                )

    return pd.DataFrame(summary_rows), pd.DataFrame(histogram_rows)


def scope_series(
    panel: pd.DataFrame,
    model: str,
    scope_value: str,
    series_name: str,
) -> tuple[np.ndarray, list[str]]:
    model_frame = panel.loc[panel["model"] == model].copy()
    if scope_value == "all_dates":
        pivot = (
            model_frame.pivot(
                index="target_date",
                columns="decision_rule",
                values=series_name,
            )
            .sort_index()
            .reindex(columns=RULE_ORDER)
        )
        if pivot.isna().any().any():
            raise ValueError(
                f"Incomplete overall date-rule matrix: {model} {series_name}"
            )
        return (
            pivot.mean(axis=1).to_numpy(dtype=float),
            list(pivot.index.astype(str)),
        )
    group = (
        model_frame.loc[
            model_frame["decision_rule"] == scope_value,
            ["target_date", series_name],
        ]
        .sort_values("target_date")
    )
    return (
        group[series_name].to_numpy(dtype=float),
        list(group["target_date"].astype(str)),
    )


def autocorrelation_diagnostics(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    series_map = {
        "standardised_residual": "standardised_residual",
        "absolute_standardised_residual": (
            "absolute_standardised_residual"
        ),
        "squared_standardised_residual": (
            "squared_standardised_residual"
        ),
    }
    for model in MODEL_ORDER:
        for scope_value in ["all_dates", *RULE_ORDER]:
            scope_type = (
                "overall"
                if scope_value == "all_dates"
                else "decision_rule"
            )
            for label, column in series_map.items():
                values, dates = scope_series(
                    panel, model, scope_value, column
                )
                for lag in range(1, int(config["acf_max_lag"]) + 1):
                    rows.append(
                        {
                            "model": model,
                            "scope_type": scope_type,
                            "scope_value": scope_value,
                            "series": label,
                            "lag_days": lag,
                            "autocorrelation": autocorrelation(
                                values, lag
                            ),
                            "dates": len(dates),
                        }
                    )
    return pd.DataFrame(rows)


def dependence_block_bootstrap(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reps = int(config["bootstrap"]["replications"])
    seed = int(config["bootstrap"]["seed"]) + 50_000
    confidence = float(config["bootstrap"]["confidence_level"])
    chunk_size = int(config["bootstrap"]["chunk_size"])
    blocks = list(
        map(int, config["bootstrap"]["moving_block_lengths"])
    )
    series_map = {
        "standardised_residual": "standardised_residual",
        "absolute_standardised_residual": (
            "absolute_standardised_residual"
        ),
        "squared_standardised_residual": (
            "squared_standardised_residual"
        ),
    }
    interval_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    counter = 0

    for model in MODEL_ORDER:
        for scope_value in ["all_dates", *RULE_ORDER]:
            scope_type = (
                "overall"
                if scope_value == "all_dates"
                else "decision_rule"
            )
            for label, column in series_map.items():
                values, dates = scope_series(
                    panel, model, scope_value, column
                )
                point = autocorrelation(values, 1)
                q7, q7_p = ljung_box(values, 7)
                q14, q14_p = ljung_box(values, 14)
                for block in blocks:
                    local_seed = seed + counter * 100 + block
                    rng = np.random.default_rng(local_seed)
                    parts: list[np.ndarray] = []
                    completed = 0
                    while completed < reps:
                        current = min(chunk_size, reps - completed)
                        indices = moving_block_indices(
                            len(values), block, current, rng
                        )
                        sampled = values[indices]
                        parts.append(
                            rowwise_lag1_correlation(sampled)
                        )
                        completed += current
                    distribution = np.concatenate(parts)
                    lower, upper = percentile_interval(
                        distribution, confidence
                    )
                    interval_rows.append(
                        {
                            "model": model,
                            "scope_type": scope_type,
                            "scope_value": scope_value,
                            "series": label,
                            "dates": len(dates),
                            "lag_days": 1,
                            "point_autocorrelation": point,
                            "bootstrap_method": (
                                "circular_moving_block"
                            ),
                            "block_length_days": block,
                            "bootstrap_lower_95": lower,
                            "bootstrap_upper_95": upper,
                            "bootstrap_replications": reps,
                            "seed": local_seed,
                            "bootstrap_unit": "settlement_date",
                        }
                    )
                summary_rows.append(
                    {
                        "model": model,
                        "scope_type": scope_type,
                        "scope_value": scope_value,
                        "series": label,
                        "dates": len(dates),
                        "lag1_autocorrelation": point,
                        "ljung_box_q7": q7,
                        "ljung_box_q7_nominal_iid_p_value": q7_p,
                        "ljung_box_q14": q14,
                        "ljung_box_q14_nominal_iid_p_value": q14_p,
                        "p_value_interpretation": (
                            "Nominal IID Ljung-Box reference; moving-block "
                            "intervals are the dependence sensitivity."
                        ),
                    }
                )
                counter += 1

    return pd.DataFrame(interval_rows), pd.DataFrame(summary_rows)


def cross_rule_correlations(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    series_columns = {
        "standardised_residual": "standardised_residual",
        "squared_standardised_residual": (
            "squared_standardised_residual"
        ),
    }
    for model in MODEL_ORDER:
        model_frame = panel.loc[panel["model"] == model]
        for label, column in series_columns.items():
            pivot = (
                model_frame.pivot(
                    index="target_date",
                    columns="decision_rule",
                    values=column,
                )
                .sort_index()
                .reindex(columns=RULE_ORDER)
            )
            for first_index, first_rule in enumerate(RULE_ORDER):
                for second_rule in RULE_ORDER[first_index + 1:]:
                    first = pivot[first_rule].to_numpy(dtype=float)
                    second = pivot[second_rule].to_numpy(dtype=float)
                    pearson = stats.pearsonr(first, second)
                    spearman = stats.spearmanr(first, second)
                    rows.append(
                        {
                            "model": model,
                            "series": label,
                            "first_rule": first_rule,
                            "second_rule": second_rule,
                            "dates": len(pivot),
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
                                "Nominal IID reference only; correlations "
                                "describe same-date cross-rule dependence."
                            ),
                        }
                    )
    return pd.DataFrame(rows)


def sharpness_quartile_diagnostics(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model in MODEL_ORDER:
        model_frame = panel.loc[panel["model"] == model].copy()
        for scope_type, scope_value, group in iter_scopes(
            model_frame,
            include_blocks=False,
        ):
            group = group.copy()
            group["predictive_sd_quartile"] = pd.qcut(
                group["predictive_standard_deviation_c"].rank(
                    method="first"
                ),
                q=4,
                labels=["Q1", "Q2", "Q3", "Q4"],
            ).astype(str)
            for quartile, subgroup in group.groupby(
                "predictive_sd_quartile",
                sort=True,
            ):
                rows.append(
                    {
                        "model": model,
                        "scope_type": scope_type,
                        "scope_value": scope_value,
                        "stratification_variable": (
                            "predictive_standard_deviation_c"
                        ),
                        "quartile": quartile,
                        "rows": len(subgroup),
                        "dates": int(
                            subgroup["target_date"].nunique()
                        ),
                        "variable_minimum": float(
                            subgroup[
                                "predictive_standard_deviation_c"
                            ].min()
                        ),
                        "variable_maximum": float(
                            subgroup[
                                "predictive_standard_deviation_c"
                            ].max()
                        ),
                        "variable_mean": float(
                            subgroup[
                                "predictive_standard_deviation_c"
                            ].mean()
                        ),
                        "mean_squared_standardised_residual": float(
                            subgroup[
                                "squared_standardised_residual"
                            ].mean()
                        ),
                        "mean_absolute_standardised_residual": float(
                            subgroup[
                                "absolute_standardised_residual"
                            ].mean()
                        ),
                        "central_90_empirical_coverage": float(
                            subgroup["central_90_covered"].mean()
                        ),
                        "mean_crps_c": float(
                            subgroup["crps_c"].mean()
                        ),
                    }
                )
    return pd.DataFrame(rows)


def write_frozen_phase19_extracts(
    phase19: Mapping[str, pd.DataFrame],
    out: Path,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    extract_dir = out / "frozen_phase19_extracts"
    extract_dir.mkdir(parents=True, exist_ok=True)
    for filename, frame in phase19.items():
        target = extract_dir / filename
        frame.to_csv(target, index=False)
        rows.append(
            {
                "source_filename": filename,
                "output_relative_path": target.relative_to(out).as_posix(),
                "rows": len(frame),
                "columns": len(frame.columns),
                "sha256": sha256_file(target),
            }
        )
    return pd.DataFrame(rows)


def overall_row(
    frame: pd.DataFrame,
    model: str,
) -> pd.Series | None:
    working = frame.copy()
    if "model" not in working.columns:
        return None
    working["_model"] = working["model"].map(normalise_model)
    working = working.loc[working["_model"] == model].copy()
    if working.empty:
        return None
    working["_scope"] = working.apply(scope_label, axis=1)
    overall = working.loc[working["_scope"] == "overall"]
    if overall.empty:
        if "dates" in working.columns:
            overall = working.loc[
                pd.to_numeric(
                    working["dates"], errors="coerce"
                )
                == pd.to_numeric(
                    working["dates"], errors="coerce"
                ).max()
            ]
        else:
            overall = working
    return overall.iloc[0] if not overall.empty else None


def phase19_reconciliation(
    coverage: pd.DataFrame,
    quantile_summary: pd.DataFrame,
    pit_summary: pd.DataFrame,
    standardised: pd.DataFrame,
    phase19: Mapping[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    frozen_coverage = phase19["phase19_coverage_summary.csv"].copy()
    frozen_coverage["_model"] = frozen_coverage["model"].map(
        normalise_model
    )
    frozen_coverage["_scope"] = frozen_coverage.apply(
        scope_label, axis=1
    )
    direct_overall = coverage.loc[
        (coverage["scope_type"] == "overall")
        & (coverage["scope_value"] == "all_dates")
    ]
    for model in MODEL_ORDER:
        for level in sorted(
            direct_overall["nominal_coverage"].unique()
        ):
            direct_row = direct_overall.loc[
                (direct_overall["model"] == model)
                & (
                    np.isclose(
                        direct_overall["nominal_coverage"],
                        level,
                    )
                )
            ].iloc[0]
            frozen_match = frozen_coverage.loc[
                (frozen_coverage["_model"] == model)
                & (frozen_coverage["_scope"] == "overall")
                & (
                    np.isclose(
                        pd.to_numeric(
                            frozen_coverage["nominal_coverage"],
                            errors="coerce",
                        ),
                        level,
                    )
                )
            ]
            if frozen_match.empty:
                rows.append(
                    {
                        "domain": "coverage",
                        "model": model,
                        "metric": f"coverage_{level:.2f}",
                        "direct_value": direct_row[
                            "empirical_coverage"
                        ],
                        "frozen_phase19_value": np.nan,
                        "difference": np.nan,
                        "status": "frozen_row_not_found",
                    }
                )
                continue
            frozen_row = frozen_match.iloc[0]
            frozen_value = float(
                frozen_row["empirical_coverage"]
            )
            direct_value = float(
                direct_row["empirical_coverage"]
            )
            rows.append(
                {
                    "domain": "coverage",
                    "model": model,
                    "metric": f"coverage_{level:.2f}",
                    "direct_value": direct_value,
                    "frozen_phase19_value": frozen_value,
                    "difference": direct_value - frozen_value,
                    "status": (
                        "matched"
                        if abs(direct_value - frozen_value) <= 1e-10
                        else "review_required"
                    ),
                }
            )
            if "mean_interval_width_c" in frozen_row.index:
                frozen_width = float(
                    frozen_row["mean_interval_width_c"]
                )
                direct_width = float(
                    direct_row["mean_interval_width_c"]
                )
                rows.append(
                    {
                        "domain": "coverage",
                        "model": model,
                        "metric": f"mean_width_{level:.2f}",
                        "direct_value": direct_width,
                        "frozen_phase19_value": frozen_width,
                        "difference": direct_width - frozen_width,
                        "status": (
                            "matched"
                            if abs(direct_width - frozen_width)
                            <= 1e-10
                            else "review_required"
                        ),
                    }
                )

    frozen_quantile = phase19[
        "phase19_quantile_calibration_summary.csv"
    ].copy()
    frozen_quantile["_model"] = frozen_quantile["model"].map(
        normalise_model
    )
    frozen_quantile["_scope"] = frozen_quantile.apply(
        scope_label, axis=1
    )
    for model in MODEL_ORDER:
        direct = quantile_summary.loc[
            (quantile_summary["model"] == model)
            & (quantile_summary["scope_type"] == "overall")
        ].iloc[0]
        frozen = frozen_quantile.loc[
            (frozen_quantile["_model"] == model)
            & (frozen_quantile["_scope"] == "overall")
        ]
        if frozen.empty:
            continue
        frozen_row = frozen.iloc[0]
        for metric in [
            "integrated_absolute_calibration_error",
            "root_mean_squared_calibration_error",
            "maximum_absolute_calibration_error",
            "mean_signed_calibration_error",
        ]:
            direct_value = float(direct[metric])
            frozen_value = float(frozen_row[metric])
            rows.append(
                {
                    "domain": "quantile_calibration",
                    "model": model,
                    "metric": metric,
                    "direct_value": direct_value,
                    "frozen_phase19_value": frozen_value,
                    "difference": direct_value - frozen_value,
                    "status": (
                        "matched"
                        if abs(direct_value - frozen_value) <= 1e-10
                        else "review_required"
                    ),
                }
            )

    frozen_pit = phase19["phase19_pit_summary.csv"].copy()
    frozen_pit["_model"] = frozen_pit["model"].map(normalise_model)
    frozen_pit["_scope"] = frozen_pit.apply(scope_label, axis=1)
    for model in MODEL_ORDER:
        direct = pit_summary.loc[
            (pit_summary["model"] == model)
            & (pit_summary["scope_type"] == "overall")
        ].iloc[0]
        frozen = frozen_pit.loc[
            (frozen_pit["_model"] == model)
            & (frozen_pit["_scope"] == "overall")
        ]
        if frozen.empty:
            continue
        frozen_row = frozen.iloc[0]
        for metric in [
            "mean_pit",
            "variance_pit",
            "ks_statistic",
            "cramer_von_mises_statistic",
            "ten_bin_chi_square",
        ]:
            direct_value = float(direct[metric])
            frozen_value = float(frozen_row[metric])
            rows.append(
                {
                    "domain": "pit",
                    "model": model,
                    "metric": metric,
                    "direct_value": direct_value,
                    "frozen_phase19_value": frozen_value,
                    "difference": direct_value - frozen_value,
                    "status": (
                        "matched"
                        if abs(direct_value - frozen_value) <= 1e-10
                        else "review_required"
                    ),
                }
            )

    frozen_standard = phase19[
        "phase19_standardised_residual_summary.csv"
    ].copy()
    frozen_standard["_model"] = frozen_standard["model"].map(
        normalise_model
    )
    frozen_standard["_scope"] = frozen_standard.apply(
        scope_label, axis=1
    )
    for model in MODEL_ORDER:
        direct = standardised.loc[
            (standardised["model"] == model)
            & (standardised["scope_type"] == "overall")
            & (
                standardised["aggregation"]
                == "date_mean_across_rules"
            )
        ].iloc[0]
        frozen = frozen_standard.loc[
            (frozen_standard["_model"] == model)
            & (frozen_standard["_scope"] == "overall")
        ].copy()
        if "aggregation" in frozen.columns:
            date_rows = frozen.loc[
                frozen["aggregation"].astype(str).str.lower().str.contains(
                    "date"
                )
            ]
            if not date_rows.empty:
                frozen = date_rows
        if frozen.empty:
            continue
        frozen_row = frozen.iloc[0]
        for direct_metric, frozen_metric in [
            ("mean", "mean"),
            ("standard_deviation", "standard_deviation"),
            ("rmse", "rmse"),
            ("skewness", "skewness"),
            ("excess_kurtosis", "excess_kurtosis"),
        ]:
            direct_value = float(direct[direct_metric])
            frozen_value = float(frozen_row[frozen_metric])
            rows.append(
                {
                    "domain": "standardised_residual",
                    "model": model,
                    "metric": direct_metric,
                    "direct_value": direct_value,
                    "frozen_phase19_value": frozen_value,
                    "difference": direct_value - frozen_value,
                    "status": (
                        "matched"
                        if abs(direct_value - frozen_value) <= 1e-10
                        else "review_required"
                    ),
                }
            )

    return pd.DataFrame(rows)


def variance_regression_extract(
    phase19: Mapping[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = phase19[
        "phase19_variance_regression_summary.csv"
    ].copy()
    coefficients = phase19[
        "phase19_variance_regression_coefficients.csv"
    ].copy()
    summary["model"] = summary["model"].map(normalise_model)
    coefficients["model"] = coefficients["model"].map(
        normalise_model
    )
    return summary, coefficients


def thesis_ready_table(
    coverage: pd.DataFrame,
    coverage_boot: pd.DataFrame,
    quantile_summary: pd.DataFrame,
    pit_summary: pd.DataFrame,
    standardised: pd.DataFrame,
    dependence_intervals: pd.DataFrame,
    dependence_summary: pd.DataFrame,
    variance_summary: pd.DataFrame,
    reconciliation: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    matern_coverage = coverage.loc[
        (coverage["model"] == "matern")
        & (coverage["scope_type"] == "overall")
    ]
    for _, record in matern_coverage.iterrows():
        level = float(record["nominal_coverage"])
        interval = coverage_boot.loc[
            (coverage_boot["model"] == "matern")
            & (coverage_boot["scope_type"] == "overall")
            & (
                np.isclose(
                    coverage_boot["nominal_coverage"], level
                )
            )
            & (
                coverage_boot["metric"] == "empirical_coverage"
            )
            & (
                coverage_boot["bootstrap_method"]
                == "ordinary_date"
            )
        ].iloc[0]
        rows.append(
            {
                "diagnostic": (
                    f"{int(round(100 * level))}% central coverage"
                ),
                "reference_or_nominal": level,
                "estimate": record["empirical_coverage"],
                "lower_95": interval["bootstrap_lower_95"],
                "upper_95": interval["bootstrap_upper_95"],
                "secondary_value": record[
                    "mean_interval_width_c"
                ],
                "secondary_label": "mean interval width (°C)",
                "aggregation": "all 1,460 date-rule rows; date bootstrap",
                "interpretation": (
                    "Undercoverage" if record["coverage_error"] < 0
                    else "Overcoverage"
                ),
            }
        )

    z_row = standardised.loc[
        (standardised["model"] == "matern")
        & (standardised["scope_type"] == "overall")
        & (
            standardised["aggregation"]
            == "date_mean_across_rules"
        )
    ].iloc[0]
    for metric, reference in [
        ("mean", 0.0),
        ("standard_deviation", 1.0),
        ("rmse", 1.0),
        ("skewness", 0.0),
        ("excess_kurtosis", 0.0),
    ]:
        rows.append(
            {
                "diagnostic": f"standardised residual {metric}",
                "reference_or_nominal": reference,
                "estimate": z_row[metric],
                "lower_95": np.nan,
                "upper_95": np.nan,
                "secondary_value": np.nan,
                "secondary_label": "",
                "aggregation": "365 date means across four rules",
                "interpretation": "Gaussian reference diagnostic",
            }
        )

    q_row = quantile_summary.loc[
        (quantile_summary["model"] == "matern")
        & (quantile_summary["scope_type"] == "overall")
    ].iloc[0]
    for metric in [
        "integrated_absolute_calibration_error",
        "root_mean_squared_calibration_error",
        "maximum_absolute_calibration_error",
        "mean_signed_calibration_error",
    ]:
        rows.append(
            {
                "diagnostic": metric,
                "reference_or_nominal": 0.0,
                "estimate": q_row[metric],
                "lower_95": np.nan,
                "upper_95": np.nan,
                "secondary_value": np.nan,
                "secondary_label": "",
                "aggregation": "99 quantile points, 1%-99%",
                "interpretation": "Smaller absolute value is better",
            }
        )

    pit_row = pit_summary.loc[
        (pit_summary["model"] == "matern")
        & (pit_summary["scope_type"] == "overall")
    ].iloc[0]
    rows.extend(
        [
            {
                "diagnostic": "mean PIT",
                "reference_or_nominal": 0.5,
                "estimate": pit_row["mean_pit"],
                "lower_95": np.nan,
                "upper_95": np.nan,
                "secondary_value": pit_row["ks_statistic"],
                "secondary_label": "KS statistic",
                "aggregation": "1,460 date-rule PIT values",
                "interpretation": "Uniform PIT reference",
            },
            {
                "diagnostic": "PIT variance",
                "reference_or_nominal": 1.0 / 12.0,
                "estimate": pit_row["variance_pit"],
                "lower_95": np.nan,
                "upper_95": np.nan,
                "secondary_value": pit_row[
                    "cramer_von_mises_statistic"
                ],
                "secondary_label": "CvM statistic",
                "aggregation": "1,460 date-rule PIT values",
                "interpretation": "Uniform PIT reference",
            },
        ]
    )

    for series in [
        "standardised_residual",
        "squared_standardised_residual",
    ]:
        point = dependence_summary.loc[
            (dependence_summary["model"] == "matern")
            & (dependence_summary["scope_type"] == "overall")
            & (dependence_summary["series"] == series)
        ].iloc[0]
        interval = dependence_intervals.loc[
            (dependence_intervals["model"] == "matern")
            & (
                dependence_intervals["scope_type"]
                == "overall"
            )
            & (dependence_intervals["series"] == series)
            & (
                dependence_intervals["block_length_days"]
                == 7
            )
        ].iloc[0]
        rows.append(
            {
                "diagnostic": f"{series} lag-one correlation",
                "reference_or_nominal": 0.0,
                "estimate": point["lag1_autocorrelation"],
                "lower_95": interval["bootstrap_lower_95"],
                "upper_95": interval["bootstrap_upper_95"],
                "secondary_value": point["ljung_box_q14"],
                "secondary_label": "Ljung-Box Q(14)",
                "aggregation": "365 date means across rules",
                "interpretation": "Moving-block interval, b=7",
            }
        )

    variance = variance_summary.loc[
        variance_summary["model"] == "matern"
    ].iloc[0]
    rows.append(
        {
            "diagnostic": "conditional-variance joint Wald test",
            "reference_or_nominal": 0.05,
            "estimate": variance[
                "joint_non_intercept_cluster_robust_p_value"
            ],
            "lower_95": np.nan,
            "upper_95": np.nan,
            "secondary_value": variance["r_squared"],
            "secondary_label": "auxiliary R²",
            "aggregation": (
                f"{int(variance['date_clusters'])} date clusters"
            ),
            "interpretation": (
                f"Wald={variance['joint_non_intercept_wald_statistic']:.6f}, "
                f"df={int(variance['joint_non_intercept_degrees_freedom'])}"
            ),
        }
    )

    coverage_reviews = reconciliation.loc[
        (reconciliation["domain"] == "coverage")
        & (reconciliation["model"] == "matern")
        & (reconciliation["status"] == "review_required")
    ]
    if not coverage_reviews.empty:
        rows.append(
            {
                "diagnostic": "frozen/direct coverage reconciliation",
                "reference_or_nominal": np.nan,
                "estimate": float(
                    coverage_reviews["difference"].abs().max()
                ),
                "lower_95": np.nan,
                "upper_95": np.nan,
                "secondary_value": len(coverage_reviews),
                "secondary_label": "rows requiring review",
                "aggregation": "direct panel versus frozen Phase 19",
                "interpretation": (
                    "Resolve before final thesis insertion; no value is "
                    "silently overwritten."
                ),
            }
        )

    return pd.DataFrame(rows)


def thesis_candidate_summary(
    thesis_table: pd.DataFrame,
    coverage: pd.DataFrame,
    dependence_intervals: pd.DataFrame,
    variance_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for level in [0.50, 0.80, 0.90]:
        record = coverage.loc[
            (coverage["model"] == "matern")
            & (coverage["scope_type"] == "overall")
            & (np.isclose(coverage["nominal_coverage"], level))
        ].iloc[0]
        rows.append(
            {
                "candidate_id": f"P5_COVERAGE_{int(level*100)}",
                "quantity": f"{int(level*100)}% central coverage",
                "point_estimate": record["empirical_coverage"],
                "secondary_value": record["mean_interval_width_c"],
                "secondary_quantity": "mean interval width (°C)",
                "preferred_location": "Results distributional adequacy table",
            }
        )

    for series, identifier in [
        ("standardised_residual", "Z"),
        ("squared_standardised_residual", "Z2"),
    ]:
        interval = dependence_intervals.loc[
            (dependence_intervals["model"] == "matern")
            & (
                dependence_intervals["scope_type"]
                == "overall"
            )
            & (dependence_intervals["series"] == series)
            & (
                dependence_intervals["block_length_days"]
                == 7
            )
        ].iloc[0]
        rows.append(
            {
                "candidate_id": f"P5_LAG1_{identifier}",
                "quantity": f"{series} lag-one correlation",
                "point_estimate": interval[
                    "point_autocorrelation"
                ],
                "lower_95": interval["bootstrap_lower_95"],
                "upper_95": interval["bootstrap_upper_95"],
                "preferred_location": "Results or diagnostic appendix",
            }
        )

    variance = variance_summary.loc[
        variance_summary["model"] == "matern"
    ].iloc[0]
    rows.append(
        {
            "candidate_id": "P5_VARIANCE_WALD",
            "quantity": "conditional-variance joint cluster-robust p-value",
            "point_estimate": variance[
                "joint_non_intercept_cluster_robust_p_value"
            ],
            "secondary_value": variance["r_squared"],
            "secondary_quantity": "auxiliary R²",
            "preferred_location": "Results distributional adequacy table",
        }
    )
    return pd.DataFrame(rows)


def make_figures(
    panel: pd.DataFrame,
    coverage: pd.DataFrame,
    quantile_curve: pd.DataFrame,
    pit_histogram: pd.DataFrame,
    autocorrelation_frame: pd.DataFrame,
    quartiles: pd.DataFrame,
    output_dir: Path,
    dpi: int,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata: list[dict[str, Any]] = []

    # 1. Coverage.
    selected = coverage.loc[
        (coverage["model"] == "matern")
        & (coverage["scope_type"] == "overall")
    ].sort_values("nominal_coverage")
    x = np.arange(len(selected))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.bar(
        x - width / 2,
        selected["nominal_coverage"],
        width,
        label="Nominal",
    )
    ax.bar(
        x + width / 2,
        selected["empirical_coverage"],
        width,
        label="Empirical",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{int(value*100)}%" for value in selected["nominal_coverage"]]
    )
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Coverage proportion")
    ax.set_title("Selected Matérn predictive interval coverage")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase5_figure_selected_matern_coverage.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Main-text candidate: selected-model central coverage",
    })

    # 2. Quantile calibration.
    selected_q = quantile_curve.loc[
        (quantile_curve["model"] == "matern")
        & (quantile_curve["scope_type"] == "overall")
    ].sort_values("nominal_probability")
    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    ax.plot(
        selected_q["nominal_probability"],
        selected_q["empirical_probability"],
        linewidth=2,
    )
    ax.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", linewidth=1)
    ax.set_xlabel("Nominal probability")
    ax.set_ylabel("Empirical probability")
    ax.set_title("Selected Matérn quantile calibration")
    fig.tight_layout()
    path = output_dir / "phase5_figure_quantile_calibration.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: 1%-99% quantile calibration",
    })

    # 3. PIT histogram.
    selected_pit = pit_histogram.loc[
        (pit_histogram["model"] == "matern")
        & (pit_histogram["scope_type"] == "overall")
    ].sort_values("bin_number")
    centres = (
        selected_pit["lower_bound"] + selected_pit["upper_bound"]
    ) / 2.0
    widths = (
        selected_pit["upper_bound"] - selected_pit["lower_bound"]
    )
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.bar(
        centres,
        selected_pit["proportion"],
        width=widths,
        align="center",
    )
    ax.axhline(
        float(selected_pit["uniform_reference_proportion"].iloc[0]),
        linestyle="--",
        linewidth=1,
    )
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("PIT")
    ax.set_ylabel("Proportion")
    ax.set_title("Selected Matérn PIT histogram")
    fig.tight_layout()
    path = output_dir / "phase5_figure_pit_histogram.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: PIT shape",
    })

    # 4. Normal Q-Q.
    z = panel.loc[
        panel["model"] == "matern",
        "standardised_residual",
    ].sort_values().to_numpy(dtype=float)
    probabilities = (np.arange(1, len(z) + 1) - 0.5) / len(z)
    theoretical = stats.norm.ppf(probabilities)
    lower = min(float(theoretical.min()), float(z.min()))
    upper = max(float(theoretical.max()), float(z.max()))
    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    ax.scatter(theoretical, z, s=9, alpha=0.5)
    ax.plot([lower, upper], [lower, upper], linestyle="--", linewidth=1)
    ax.set_xlabel("Standard normal quantiles")
    ax.set_ylabel("Empirical standardised residual quantiles")
    ax.set_title("Selected Matérn normal Q-Q diagnostic")
    fig.tight_layout()
    path = output_dir / "phase5_figure_normal_qq.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: Gaussian marginal-shape diagnostic",
    })

    # 5. ACF of z.
    acf_z = autocorrelation_frame.loc[
        (autocorrelation_frame["model"] == "matern")
        & (
            autocorrelation_frame["series"]
            == "standardised_residual"
        )
    ]
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    for scope in ["all_dates", *RULE_ORDER]:
        sub = acf_z.loc[
            acf_z["scope_value"] == scope
        ].sort_values("lag_days")
        label = (
            "Date mean"
            if scope == "all_dates"
            else RULE_LABELS[scope]
        )
        ax.plot(
            sub["lag_days"],
            sub["autocorrelation"],
            marker="o",
            label=label,
        )
    ax.axhline(0.0, linewidth=1)
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Autocorrelation")
    ax.set_title("Selected Matérn standardised-residual dependence")
    ax.legend(ncol=2)
    fig.tight_layout()
    path = output_dir / "phase5_figure_standardised_residual_acf.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: residual serial dependence",
    })

    # 6. ACF of z^2.
    acf_z2 = autocorrelation_frame.loc[
        (autocorrelation_frame["model"] == "matern")
        & (
            autocorrelation_frame["series"]
            == "squared_standardised_residual"
        )
    ]
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    for scope in ["all_dates", *RULE_ORDER]:
        sub = acf_z2.loc[
            acf_z2["scope_value"] == scope
        ].sort_values("lag_days")
        label = (
            "Date mean"
            if scope == "all_dates"
            else RULE_LABELS[scope]
        )
        ax.plot(
            sub["lag_days"],
            sub["autocorrelation"],
            marker="o",
            label=label,
        )
    ax.axhline(0.0, linewidth=1)
    ax.set_xlabel("Lag (days)")
    ax.set_ylabel("Autocorrelation")
    ax.set_title("Selected Matérn squared-residual dependence")
    ax.legend(ncol=2)
    fig.tight_layout()
    path = output_dir / "phase5_figure_squared_residual_acf.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: variance persistence",
    })

    # 7. Variance by sharpness quartile.
    selected_quartiles = quartiles.loc[
        (quartiles["model"] == "matern")
        & (quartiles["scope_type"] == "overall")
    ].sort_values("quartile")
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.plot(
        selected_quartiles["quartile"],
        selected_quartiles[
            "mean_squared_standardised_residual"
        ],
        marker="o",
    )
    ax.axhline(1.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Predictive-SD quartile")
    ax.set_ylabel("Mean squared standardised residual")
    ax.set_title("Conditional scale adequacy by predictive sharpness")
    fig.tight_layout()
    path = output_dir / "phase5_figure_variance_by_sharpness_quartile.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: conditional-variance structure",
    })

    return pd.DataFrame(metadata)


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    coverage: pd.DataFrame,
    coverage_boot: pd.DataFrame,
    quantile_summary: pd.DataFrame,
    pit_summary: pd.DataFrame,
    standardised: pd.DataFrame,
    dependence_intervals: pd.DataFrame,
    dependence_summary: pd.DataFrame,
    variance_summary: pd.DataFrame,
    reconciliation: pd.DataFrame,
    config: Mapping[str, Any],
) -> None:
    critical = bool_series(checks["critical"])
    passed = bool_series(checks["passed"])
    failures = checks.loc[critical & ~passed]
    status = "PASSED" if failures.empty else "FAILED"

    selected_coverage = coverage.loc[
        (coverage["model"] == "matern")
        & (coverage["scope_type"] == "overall")
    ].sort_values("nominal_coverage")
    selected_q = quantile_summary.loc[
        (quantile_summary["model"] == "matern")
        & (quantile_summary["scope_type"] == "overall")
    ].iloc[0]
    selected_pit = pit_summary.loc[
        (pit_summary["model"] == "matern")
        & (pit_summary["scope_type"] == "overall")
    ].iloc[0]
    selected_z = standardised.loc[
        (standardised["model"] == "matern")
        & (standardised["scope_type"] == "overall")
        & (
            standardised["aggregation"]
            == "date_mean_across_rules"
        )
    ].iloc[0]
    variance = variance_summary.loc[
        variance_summary["model"] == "matern"
    ].iloc[0]

    lines = [
        "# Phase 5 — Calibration and GP Misspecification",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"## Overall status: **{status}**",
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(dict(provenance), indent=2, sort_keys=True),
        "```",
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Interpretation boundary",
        "",
        config["interpretation_boundary"],
        "",
        "## Selected Matérn coverage and sharpness",
        "",
        selected_coverage[
            [
                "nominal_coverage",
                "empirical_coverage",
                "coverage_error",
                "mean_interval_width_c",
                "median_interval_width_c",
            ]
        ].to_markdown(index=False),
        "",
        "Ordinary and circular moving-block intervals are stored for every "
        "coverage level, both overall and by decision rule.",
        "",
        "## Marginal calibration",
        "",
        (
            f"The 1%-99% quantile-calibration integrated absolute error is "
            f"**{selected_q['integrated_absolute_calibration_error']:.6f}**, "
            f"RMSE is **{selected_q['root_mean_squared_calibration_error']:.6f}**, "
            f"maximum absolute error is "
            f"**{selected_q['maximum_absolute_calibration_error']:.6f}**, and "
            f"mean signed error is "
            f"**{selected_q['mean_signed_calibration_error']:.6f}**."
        ),
        "",
        (
            f"Mean PIT is **{selected_pit['mean_pit']:.6f}** and PIT variance "
            f"is **{selected_pit['variance_pit']:.6f}**, against uniform "
            f"references 0.5 and {1/12:.6f}."
        ),
        "",
        "## Standardised residuals",
        "",
        (
            f"Using the settlement-date mean across the four decision rules, "
            f"the standardised residual has mean **{selected_z['mean']:.6f}**, "
            f"standard deviation **{selected_z['standard_deviation']:.6f}**, "
            f"RMSE **{selected_z['rmse']:.6f}**, skewness "
            f"**{selected_z['skewness']:.6f}** and excess kurtosis "
            f"**{selected_z['excess_kurtosis']:.6f}**."
        ),
        "",
        "## Dependence",
        "",
    ]

    for series in [
        "standardised_residual",
        "squared_standardised_residual",
    ]:
        point = dependence_summary.loc[
            (dependence_summary["model"] == "matern")
            & (dependence_summary["scope_type"] == "overall")
            & (dependence_summary["series"] == series)
        ].iloc[0]
        intervals = dependence_intervals.loc[
            (dependence_intervals["model"] == "matern")
            & (
                dependence_intervals["scope_type"]
                == "overall"
            )
            & (dependence_intervals["series"] == series)
        ].sort_values("block_length_days")
        lines.extend(
            [
                f"### {series}",
                "",
                (
                    f"Lag-one correlation: "
                    f"**{point['lag1_autocorrelation']:.6f}**. "
                    "Circular moving-block 95% intervals: "
                    + "; ".join(
                        (
                            f"b={int(row['block_length_days'])}: "
                            f"[{row['bootstrap_lower_95']:.6f}, "
                            f"{row['bootstrap_upper_95']:.6f}]"
                        )
                        for _, row in intervals.iterrows()
                    )
                    + "."
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Conditional variance",
            "",
            (
                f"The frozen date-clustered auxiliary regression reports "
                f"R² **{variance['r_squared']:.6f}**, joint Wald statistic "
                f"**{variance['joint_non_intercept_wald_statistic']:.6f}** "
                f"on {int(variance['joint_non_intercept_degrees_freedom'])} "
                f"non-intercept restrictions, with p-value "
                f"**{variance['joint_non_intercept_cluster_robust_p_value']:.6f}**."
            ),
            "",
            "The explanatory power is small, but the test detects remaining "
            "feature-related conditional-variance structure.",
            "",
            "## Frozen/direct reconciliation",
            "",
            reconciliation.to_markdown(index=False),
            "",
            "Rows marked `review_required` are preserved as an audit item. "
            "The phase does not silently replace a frozen value with a direct "
            "recalculation.",
            "",
            "## Thesis use",
            "",
            "- Main text: one compact adequacy table with coverage, width, quantile error, lag-one dependence and variance-regression evidence.",
            "- Main text: at most one coverage or residual-dependence figure.",
            "- Appendix: PIT histogram, Q-Q plot, full ACFs, rule-level intervals and coefficient table.",
            "- Archive: all 1%-99% calibration points, block-length sensitivities and quartile diagnostics.",
            "- Interpret the law as useful but misspecified; do not claim exact Gaussian calibration.",
            "",
        ]
    )
    (out / "phase5_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    records: list[dict[str, Any]] = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase5_manifest.json",
            "phase5_review_bundle.zip",
        }:
            records.append(
                {
                    "relative_path": path.relative_to(out).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "phase": "phase5_calibration_misspecification",
        "generated_utc": utc_now(),
        "provenance": dict(provenance),
        "files": records,
    }
    (out / "phase5_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase5_review_bundle.zip"
    with zipfile.ZipFile(
        bundle,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                archive.write(
                    path,
                    path.relative_to(out).as_posix(),
                )


def self_test() -> None:
    rng = np.random.default_rng(123)
    assert ordinary_indices(20, 7, rng).shape == (7, 20)

    rng = np.random.default_rng(123)
    moving = moving_block_indices(20, 3, 7, rng)
    assert moving.shape == (7, 20)
    assert moving.min() >= 0 and moving.max() < 20

    synthetic = np.vstack(
        [
            np.arange(20, dtype=float),
            np.arange(20, dtype=float)[::-1],
        ]
    )
    correlations = rowwise_lag1_correlation(synthetic)
    assert correlations.shape == (2,)
    assert np.all(np.isfinite(correlations))

    values = np.arange(30, dtype=float)
    assert abs(autocorrelation(values, 1) - 1.0) < 1e-12
    q, p = ljung_box(values, 7)
    assert np.isfinite(q) and np.isfinite(p)

    blocks = assign_chronological_blocks(
        [f"2025-01-{day:02d}" for day in range(1, 11)],
        [2, 2, 3, 3],
    )
    assert blocks["validation_block"].value_counts().sort_index().tolist() == [
        2, 2, 3, 3
    ]

    print("SELF-TEST: PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--frozen-root", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    if any(
        value is None
        for value in [
            args.repo_root,
            args.frozen_root,
            args.spec,
            args.output_root,
        ]
    ):
        raise SystemExit(
            "--repo-root, --frozen-root, --spec and --output-root are required"
        )

    repo_root = args.repo_root.resolve()
    frozen_root = args.frozen_root.resolve()
    spec_path = (repo_root / args.spec).resolve()
    out = (repo_root / args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    figures_dir = out / "figures"

    config = json.loads(spec_path.read_text(encoding="utf-8"))
    loss_path = (
        repo_root / config["input_paths"]["phase3_loss_panel"]
    )
    if not loss_path.is_file():
        raise FileNotFoundError(loss_path)

    phase19 = load_phase19_tables(frozen_root, config)
    phase19_hashes = {
        filename: sha256_file(
            frozen_root
            / config["input_paths"]["phase19_root"]
            / filename
        )
        for filename in config["phase19_files"]
    }
    provenance = {
        "generated_utc": utc_now(),
        "working_branch": git(repo_root, "branch", "--show-current"),
        "working_commit": git(repo_root, "rev-parse", "HEAD"),
        "frozen_ref": config["frozen_ref"],
        "frozen_tag_object": git(
            repo_root, "rev-parse", config["frozen_ref"]
        ),
        "frozen_commit": git(
            repo_root,
            "rev-parse",
            f"{config['frozen_ref']}^{{commit}}",
        ),
        "phase3_loss_panel": config["input_paths"][
            "phase3_loss_panel"
        ],
        "phase3_loss_panel_sha256": sha256_file(loss_path),
        "phase19_source_hashes": phase19_hashes,
        "bootstrap_replications": config["bootstrap"][
            "replications"
        ],
        "bootstrap_seed": config["bootstrap"]["seed"],
        "moving_block_lengths": config["bootstrap"][
            "moving_block_lengths"
        ],
        "interpretation_boundary": config[
            "interpretation_boundary"
        ],
    }
    (out / "phase5_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    loss_panel = pd.read_csv(loss_path, low_memory=False)
    checks = validate_inputs(
        loss_panel,
        phase19,
        config,
        repo_root,
    )
    checks.to_csv(
        out / "phase5_integrity_checks.csv",
        index=False,
    )
    critical = bool_series(checks["critical"])
    passed = bool_series(checks["passed"])
    initial_failures = checks.loc[critical & ~passed]
    if not initial_failures.empty:
        print(checks.to_string(index=False))
        raise RuntimeError("Phase 5 input checks failed")

    panel, date_panel, selected = prepare_panel(
        loss_panel,
        config,
    )
    panel.to_csv(
        out / "phase5_gp_diagnostic_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    date_panel.to_csv(
        out / "phase5_gp_date_level_diagnostic_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    selected.to_csv(
        out / "phase5_selected_matern_diagnostic_panel.csv.gz",
        index=False,
        compression="gzip",
    )

    coverage = coverage_summary(panel, config)
    coverage.to_csv(
        out / "phase5_coverage_width_summary.csv",
        index=False,
    )
    coverage_boot, coverage_tests = coverage_bootstrap(
        panel,
        config,
    )
    coverage_boot.to_csv(
        out / "phase5_coverage_width_bootstrap_intervals.csv",
        index=False,
    )
    coverage_tests.to_csv(
        out / "phase5_coverage_bootstrap_tests.csv",
        index=False,
    )

    quantile_curve, quantile_summary = quantile_calibration(
        panel,
        config,
    )
    quantile_curve.to_csv(
        out / "phase5_quantile_calibration_curve.csv",
        index=False,
    )
    quantile_summary.to_csv(
        out / "phase5_quantile_calibration_summary.csv",
        index=False,
    )

    standardised = standardised_residual_summary(
        panel,
        date_panel,
    )
    standardised.to_csv(
        out / "phase5_standardised_residual_summary.csv",
        index=False,
    )

    pit_summary, pit_histogram = pit_diagnostics(
        panel,
        config,
    )
    pit_summary.to_csv(
        out / "phase5_pit_summary.csv",
        index=False,
    )
    pit_histogram.to_csv(
        out / "phase5_pit_histogram.csv",
        index=False,
    )

    acf = autocorrelation_diagnostics(panel, config)
    acf.to_csv(
        out / "phase5_autocorrelation.csv",
        index=False,
    )
    dependence_intervals, dependence_summary = (
        dependence_block_bootstrap(panel, config)
    )
    dependence_intervals.to_csv(
        out / "phase5_lag1_moving_block_intervals.csv",
        index=False,
    )
    dependence_summary.to_csv(
        out / "phase5_dependence_summary.csv",
        index=False,
    )

    cross_rule = cross_rule_correlations(panel)
    cross_rule.to_csv(
        out / "phase5_cross_rule_correlations.csv",
        index=False,
    )

    quartiles = sharpness_quartile_diagnostics(panel)
    quartiles.to_csv(
        out / "phase5_sharpness_quartile_diagnostics.csv",
        index=False,
    )

    frozen_registry = write_frozen_phase19_extracts(
        phase19,
        out,
    )
    frozen_registry.to_csv(
        out / "phase5_frozen_phase19_extract_registry.csv",
        index=False,
    )

    variance_summary, variance_coefficients = (
        variance_regression_extract(phase19)
    )
    variance_summary.to_csv(
        out / "phase5_variance_regression_summary.csv",
        index=False,
    )
    variance_coefficients.to_csv(
        out / "phase5_variance_regression_coefficients.csv",
        index=False,
    )

    reconciliation = phase19_reconciliation(
        coverage,
        quantile_summary,
        pit_summary,
        standardised,
        phase19,
    )
    reconciliation.to_csv(
        out / "phase5_frozen_direct_reconciliation.csv",
        index=False,
    )

    thesis_table = thesis_ready_table(
        coverage,
        coverage_boot,
        quantile_summary,
        pit_summary,
        standardised,
        dependence_intervals,
        dependence_summary,
        variance_summary,
        reconciliation,
    )
    thesis_table.to_csv(
        out / "phase5_thesis_ready_diagnostic_table.csv",
        index=False,
    )

    candidate_summary = thesis_candidate_summary(
        thesis_table,
        coverage,
        dependence_intervals,
        variance_summary,
    )
    candidate_summary.to_csv(
        out / "phase5_thesis_candidate_summary.csv",
        index=False,
    )

    figure_registry = make_figures(
        panel,
        coverage,
        quantile_curve,
        pit_histogram,
        acf,
        quartiles,
        figures_dir,
        int(config.get("figure_dpi", 180)),
    )
    figure_registry.to_csv(
        out / "phase5_figure_registry.csv",
        index=False,
    )

    # Final integrity checks.
    reference = config["reference_diagnostics"]
    calibration_check_rows: list[dict[str, Any]] = []
    for model in MODEL_ORDER:
        direct_q = quantile_summary.loc[
            (quantile_summary["model"] == model)
            & (quantile_summary["scope_type"] == "overall")
        ].iloc[0]
        for metric, expected_value in reference[
            "quantile_calibration"
        ][model].items():
            calibration_check_rows.append(
                {
                    "check": f"reference_{model}_{metric}",
                    "passed": abs(
                        float(direct_q[metric])
                        - float(expected_value)
                    ) <= 0.00005,
                    "critical": True,
                    "detail": (
                        f"calculated={float(direct_q[metric]):.8f}; "
                        f"reference={float(expected_value):.8f}"
                    ),
                }
            )
        direct_pit = pit_summary.loc[
            (pit_summary["model"] == model)
            & (pit_summary["scope_type"] == "overall")
        ].iloc[0]
        for metric, expected_value in reference["pit"][model].items():
            calibration_check_rows.append(
                {
                    "check": f"reference_{model}_{metric}",
                    "passed": abs(
                        float(direct_pit[metric])
                        - float(expected_value)
                    ) <= 0.00005,
                    "critical": True,
                    "detail": (
                        f"calculated={float(direct_pit[metric]):.8f}; "
                        f"reference={float(expected_value):.8f}"
                    ),
                }
            )
        direct_z = standardised.loc[
            (standardised["model"] == model)
            & (standardised["scope_type"] == "overall")
            & (
                standardised["aggregation"]
                == "date_mean_across_rules"
            )
        ].iloc[0]
        for metric, expected_value in reference[
            "date_balanced_standardised_residual"
        ][model].items():
            calibration_check_rows.append(
                {
                    "check": f"reference_{model}_z_{metric}",
                    "passed": abs(
                        float(direct_z[metric])
                        - float(expected_value)
                    ) <= 0.00005,
                    "critical": True,
                    "detail": (
                        f"calculated={float(direct_z[metric]):.8f}; "
                        f"reference={float(expected_value):.8f}"
                    ),
                }
            )

    variance = variance_summary.loc[
        variance_summary["model"] == "matern"
    ].iloc[0]
    variance_reference = reference["matern_variance_regression"]
    variance_checks = [
        {
            "check": "reference_matern_variance_r_squared",
            "passed": abs(
                float(variance["r_squared"])
                - variance_reference["r_squared"]
            ) <= 0.00005,
            "critical": True,
            "detail": (
                f"calculated={float(variance['r_squared']):.8f}; "
                f"reference={variance_reference['r_squared']:.8f}"
            ),
        },
        {
            "check": "reference_matern_variance_wald",
            "passed": abs(
                float(
                    variance[
                        "joint_non_intercept_wald_statistic"
                    ]
                )
                - variance_reference["wald_statistic"]
            ) <= 0.00005,
            "critical": True,
            "detail": (
                f"calculated="
                f"{float(variance['joint_non_intercept_wald_statistic']):.8f}; "
                f"reference={variance_reference['wald_statistic']:.8f}"
            ),
        },
        {
            "check": "reference_matern_variance_df",
            "passed": int(
                variance[
                    "joint_non_intercept_degrees_freedom"
                ]
            )
            == int(variance_reference["degrees_freedom"]),
            "critical": True,
            "detail": (
                f"calculated="
                f"{int(variance['joint_non_intercept_degrees_freedom'])}; "
                f"reference={int(variance_reference['degrees_freedom'])}"
            ),
        },
        {
            "check": "reference_matern_variance_p_value",
            "passed": abs(
                float(
                    variance[
                        "joint_non_intercept_cluster_robust_p_value"
                    ]
                )
                - variance_reference["cluster_robust_p_value"]
            ) <= 0.00005,
            "critical": True,
            "detail": (
                f"calculated="
                f"{float(variance['joint_non_intercept_cluster_robust_p_value']):.8f}; "
                f"reference={variance_reference['cluster_robust_p_value']:.8f}"
            ),
        },
    ]

    coverage_review_count = int(
        (
            (reconciliation["domain"] == "coverage")
            & (reconciliation["status"] == "review_required")
        ).sum()
    )
    output_checks = [
        {
            "check": "diagnostic_panel_rows",
            "passed": len(panel) == config["expected"]["gp_rows"],
            "critical": True,
            "detail": f"rows={len(panel)}",
        },
        {
            "check": "selected_matern_rows",
            "passed": len(selected)
            == config["expected"]["rows_per_model"],
            "critical": True,
            "detail": f"rows={len(selected)}",
        },
        {
            "check": "coverage_bootstrap_methods",
            "passed": set(
                coverage_boot["bootstrap_method"].unique()
            )
            == {"ordinary_date", "circular_moving_block"},
            "critical": True,
            "detail": (
                f"methods="
                f"{sorted(coverage_boot['bootstrap_method'].unique())}"
            ),
        },
        {
            "check": "coverage_block_lengths",
            "passed": set(
                coverage_boot.loc[
                    coverage_boot["bootstrap_method"]
                    == "circular_moving_block",
                    "block_length_days",
                ]
                .dropna()
                .astype(int)
                .unique()
            )
            == set(config["bootstrap"]["moving_block_lengths"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "dependence_block_lengths",
            "passed": set(
                dependence_intervals["block_length_days"]
                .astype(int)
                .unique()
            )
            == set(config["bootstrap"]["moving_block_lengths"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "quantile_grid_complete",
            "passed": set(
                quantile_curve.loc[
                    (quantile_curve["model"] == "matern")
                    & (
                        quantile_curve["scope_type"]
                        == "overall"
                    ),
                    "nominal_probability",
                ].round(2)
            )
            == set(np.round(np.arange(0.01, 1.00, 0.01), 2)),
            "critical": True,
            "detail": "",
        },
        {
            "check": "variance_coefficients_complete",
            "passed": len(variance_coefficients)
            == config["expected"][
                "phase19_variance_coefficient_rows"
            ],
            "critical": True,
            "detail": f"rows={len(variance_coefficients)}",
        },
        {
            "check": "figures_created",
            "passed": len(figure_registry) == 7
            and all(
                (figures_dir / name).is_file()
                for name in figure_registry["figure"]
            ),
            "critical": True,
            "detail": f"figures={len(figure_registry)}",
        },
        {
            "check": "coverage_reconciliation_review_register",
            "passed": True,
            "critical": False,
            "detail": (
                f"coverage_rows_requiring_review={coverage_review_count}"
            ),
        },
    ]

    all_checks = pd.concat(
        [
            checks,
            pd.DataFrame(calibration_check_rows),
            pd.DataFrame(variance_checks),
            pd.DataFrame(output_checks),
        ],
        ignore_index=True,
    )
    all_checks.to_csv(
        out / "phase5_integrity_checks.csv",
        index=False,
    )

    write_report(
        out,
        provenance,
        all_checks,
        coverage,
        coverage_boot,
        quantile_summary,
        pit_summary,
        standardised,
        dependence_intervals,
        dependence_summary,
        variance_summary,
        reconciliation,
        config,
    )
    build_manifest(out, provenance)
    make_review_bundle(out)

    final_critical = bool_series(all_checks["critical"])
    final_passed = bool_series(all_checks["passed"])
    final_failures = all_checks.loc[
        final_critical & ~final_passed
    ]
    print("=" * 96)
    print("PHASE 5 — CALIBRATION AND GP MISSPECIFICATION")
    print("=" * 96)
    print(all_checks.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase5_review_bundle.zip'}")
    if final_failures.empty:
        print("FINAL STATUS: PASSED")
        if coverage_review_count:
            print(
                "NON-CRITICAL REVIEW: direct and frozen coverage values "
                f"differ in {coverage_review_count} rows; inspect the "
                "reconciliation table before thesis insertion."
            )
        return 0
    print("FINAL STATUS: FAILED")
    print(final_failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
