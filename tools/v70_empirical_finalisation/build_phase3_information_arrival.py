#!/usr/bin/env python3
"""
Phase 3: information-arrival and forecast-revision analysis.

This phase uses only frozen weather evidence and accepted Phase 1/2 outputs.
It does not refit, reselect or recalibrate any model.

Core estimands:
- deterministic forecast revision between decision rules;
- change in signed, absolute and squared settlement error;
- whether a revision moved towards the eventual HKO settlement value;
- out-of-sample CRPS change for raw, static, RBF and Matérn procedures;
- decomposition of GP predictive-mean revision into deterministic-forecast
  revision and conditional residual-correction revision;
- change in GP predictive uncertainty.

The words "information arrival" are descriptive. The phase does not identify
the causal effect of an individual observation because forecast issue cycle,
forecast state and elapsed lead time move together across decision rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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


RULE_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]
RULE_LABELS = {
    "24h_prior": "24h prior",
    "12h_prior": "12h prior",
    "6h_prior": "6h prior",
    "event_day_open": "Event-day open",
}
MODEL_ORDER = ["raw", "static", "rbf", "matern"]
MODEL_LABELS = {
    "raw": "Raw point",
    "static": "Static Gaussian",
    "rbf": "RBF GP",
    "matern": "Matérn-3/2 GP",
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


def normalise_kernel(value: Any) -> str:
    text = str(value).strip().lower()
    if "matern" in text or "mat32" in text:
        return "matern"
    if "rbf" in text or "squared" in text or "radial" in text:
        return "rbf"
    return text


def normalise_model(value: Any) -> str:
    text = str(value).strip().lower()
    if "matern" in text or "mat32" in text:
        return "matern"
    if "rbf" in text:
        return "rbf"
    if "static" in text:
        return "static"
    if "raw" in text or "point" in text:
        return "raw"
    return text


def season_from_month(month: pd.Series) -> pd.Series:
    mapping = {
        12: "DJF", 1: "DJF", 2: "DJF",
        3: "MAM", 4: "MAM", 5: "MAM",
        6: "JJA", 7: "JJA", 8: "JJA",
        9: "SON", 10: "SON", 11: "SON",
    }
    return month.map(mapping)


def percentile_interval(
    values: np.ndarray,
    confidence: float,
) -> tuple[float, float]:
    alpha = 1.0 - confidence
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    return (
        float(np.quantile(finite, alpha / 2.0)),
        float(np.quantile(finite, 1.0 - alpha / 2.0)),
    )


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
    blocks_needed = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(replications, blocks_needed))
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % n
    return indices.reshape(replications, -1)[:, :n]


def gaussian_crps(
    observation: np.ndarray,
    mean: np.ndarray,
    standard_deviation: np.ndarray,
) -> np.ndarray:
    y = np.asarray(observation, dtype=float)
    mu = np.asarray(mean, dtype=float)
    sigma = np.asarray(standard_deviation, dtype=float)
    if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("Gaussian CRPS requires finite positive standard deviations")
    z = (y - mu) / sigma
    return sigma * (
        z * (2.0 * stats.norm.cdf(z) - 1.0)
        + 2.0 * stats.norm.pdf(z)
        - 1.0 / math.sqrt(math.pi)
    )


def linear_relationship(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    mask = np.isfinite(x) & np.isfinite(y)
    x = np.asarray(x, dtype=float)[mask]
    y = np.asarray(y, dtype=float)[mask]
    if len(x) < 3 or np.std(x, ddof=1) <= 0:
        return {
            "intercept": np.nan,
            "slope": np.nan,
            "r_squared": np.nan,
            "pearson_correlation": np.nan,
            "spearman_correlation": np.nan,
        }
    design = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ beta
    total = float(np.sum((y - np.mean(y)) ** 2))
    residual = float(np.sum((y - fitted) ** 2))
    return {
        "intercept": float(beta[0]),
        "slope": float(beta[1]),
        "r_squared": float(1.0 - residual / total) if total > 0 else np.nan,
        "pearson_correlation": float(np.corrcoef(x, y)[0, 1]),
        "spearman_correlation": float(stats.spearmanr(x, y).statistic),
    }


def dependency_check(path: Path, phase_name: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing={path}"
    frame = pd.read_csv(path)
    required = {"passed", "critical"}
    if not required.issubset(frame.columns):
        return False, f"{phase_name} check table lacks {sorted(required)}"
    failed = frame.loc[
        frame["critical"].astype(bool)
        & ~frame["passed"].astype(bool)
    ]
    return failed.empty, f"critical_failures={len(failed)}"


def validate_inputs(
    weather: pd.DataFrame,
    gp: pd.DataFrame,
    static_registry: pd.DataFrame,
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

    required_weather = {
        "target_date", "decision_rule", "forecast_daily_max_c",
        "hko_daily_max_c", "residual_c", "absolute_error_c",
        "squared_error_c", "support_available", "complete_local_day",
        "issued_before_decision", "market_price_accessed",
        "outcome_accessed", "model_fitted", "model_selected",
        "calibration_selected", "trading_returns_calculated",
    }
    missing_weather = sorted(required_weather - set(weather.columns))
    add("weather_required_columns", not missing_weather, f"missing={missing_weather}")

    required_gp = {
        "target_date", "decision_rule", "kernel", "forecast_daily_max_c",
        "hko_daily_max_c", "residual_observed_c",
        "residual_predictive_mean_c", "predictive_standard_deviation_c",
        "temperature_predictive_mean_c", "crps_c",
    }
    missing_gp = sorted(required_gp - set(gp.columns))
    add("gp_required_columns", not missing_gp, f"missing={missing_gp}")

    required_static = {
        "fit_scope", "fold_id", "decision_rule", "validation_start",
        "validation_end", "residual_mean_c", "residual_standard_deviation_c",
    }
    missing_static = sorted(required_static - set(static_registry.columns))
    add("static_registry_required_columns", not missing_static, f"missing={missing_static}")

    if missing_weather or missing_gp or missing_static:
        return pd.DataFrame(checks)

    weather_dates = pd.to_datetime(weather["target_date"], errors="coerce")
    weather_rules = weather["decision_rule"].astype(str)
    weather_duplicates = int(
        pd.DataFrame({
            "target_date": weather_dates,
            "decision_rule": weather_rules,
        }).duplicated().sum()
    )
    counts = weather_rules.value_counts().to_dict()

    add("weather_expected_rows", len(weather) == expected["weather_rows"], f"rows={len(weather)}")
    add(
        "weather_expected_dates",
        weather_dates.dt.normalize().nunique() == expected["weather_dates"],
        f"dates={weather_dates.dt.normalize().nunique()}",
    )
    add(
        "weather_expected_rules",
        set(weather_rules.unique()) == set(expected["rules"]),
        f"rules={sorted(weather_rules.unique())}",
    )
    add(
        "weather_rows_per_rule",
        all(counts.get(rule, 0) == expected["rows_per_rule"] for rule in expected["rules"]),
        f"counts={counts}",
    )
    add("weather_unique_keys", weather_duplicates == 0, f"duplicates={weather_duplicates}")

    residual_identity = (
        pd.to_numeric(weather["hko_daily_max_c"], errors="coerce")
        - pd.to_numeric(weather["forecast_daily_max_c"], errors="coerce")
        - pd.to_numeric(weather["residual_c"], errors="coerce")
    ).abs()
    add(
        "weather_residual_identity",
        float(residual_identity.max()) <= tolerance,
        f"max_error={float(residual_identity.max()):.3e}",
    )

    for column in ["support_available", "complete_local_day", "issued_before_decision"]:
        values = weather[column].fillna(False).astype(bool)
        add(f"weather_all_{column}", bool(values.all()), f"false_rows={int((~values).sum())}")

    for column in [
        "market_price_accessed", "outcome_accessed", "model_fitted",
        "model_selected", "calibration_selected", "trading_returns_calculated",
    ]:
        values = weather[column].fillna(False).astype(bool)
        add(f"weather_no_{column}", bool((~values).all()), f"true_rows={int(values.sum())}")

    gp_dates = pd.to_datetime(gp["target_date"], errors="coerce")
    gp_rules = gp["decision_rule"].astype(str)
    gp_kernels = gp["kernel"].map(normalise_kernel)
    gp_duplicates = int(
        pd.DataFrame({
            "target_date": gp_dates,
            "decision_rule": gp_rules,
            "kernel": gp_kernels,
        }).duplicated().sum()
    )
    add("gp_expected_rows", len(gp) == expected["gp_rows"], f"rows={len(gp)}")
    add(
        "gp_expected_dates",
        gp_dates.dt.normalize().nunique() == expected["gp_validation_dates"],
        f"dates={gp_dates.dt.normalize().nunique()}",
    )
    add(
        "gp_expected_rules",
        set(gp_rules.unique()) == set(expected["rules"]),
        f"rules={sorted(gp_rules.unique())}",
    )
    add(
        "gp_expected_kernels",
        set(gp_kernels.unique()) == set(expected["gp_kernels"]),
        f"kernels={sorted(gp_kernels.unique())}",
    )
    add("gp_unique_date_rule_kernel", gp_duplicates == 0, f"duplicates={gp_duplicates}")

    gp_target_identity = (
        pd.to_numeric(gp["hko_daily_max_c"], errors="coerce")
        - pd.to_numeric(gp["forecast_daily_max_c"], errors="coerce")
        - pd.to_numeric(gp["residual_observed_c"], errors="coerce")
    ).abs()
    add(
        "gp_residual_identity",
        float(gp_target_identity.max()) <= tolerance,
        f"max_error={float(gp_target_identity.max()):.3e}",
    )

    add(
        "gp_crps_finite_nonnegative",
        bool(
            np.isfinite(pd.to_numeric(gp["crps_c"], errors="coerce")).all()
            and (pd.to_numeric(gp["crps_c"], errors="coerce") >= -tolerance).all()
        ),
        "",
    )
    add(
        "gp_sd_finite_positive",
        bool(
            np.isfinite(
                pd.to_numeric(gp["predictive_standard_deviation_c"], errors="coerce")
            ).all()
            and (
                pd.to_numeric(gp["predictive_standard_deviation_c"], errors="coerce")
                > 0
            ).all()
        ),
        "",
    )

    phase1_path = repo_root / config["input_paths"]["phase1_completion"]
    phase2_path = repo_root / config["input_paths"]["phase2_integrity"]
    passed, detail = dependency_check(phase1_path, "Phase 1")
    add("phase1_dependency", passed, detail)
    passed, detail = dependency_check(phase2_path, "Phase 2")
    add("phase2_dependency", passed, detail)

    return pd.DataFrame(checks)


def build_deterministic_transition_panel(
    weather: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    tolerance = float(config["numerical_tolerance"])
    frame = weather.copy()
    frame["target_date"] = pd.to_datetime(frame["target_date"]).dt.strftime("%Y-%m-%d")

    key_columns = [
        "forecast_daily_max_c", "hko_daily_max_c", "residual_c",
        "absolute_error_c", "squared_error_c",
    ]
    pivots = {
        column: frame.pivot(
            index="target_date",
            columns="decision_rule",
            values=column,
        ).reindex(columns=RULE_ORDER)
        for column in key_columns
    }
    for column, pivot in pivots.items():
        if pivot.isna().any().any():
            raise ValueError(f"Missing values in deterministic pivot: {column}")

    rows: list[dict[str, Any]] = []
    for transition_order, transition in enumerate(config["transitions"], start=1):
        early = transition["early_rule"]
        late = transition["late_rule"]
        for date in pivots["forecast_daily_max_c"].index:
            early_forecast = float(pivots["forecast_daily_max_c"].loc[date, early])
            late_forecast = float(pivots["forecast_daily_max_c"].loc[date, late])
            hko = float(pivots["hko_daily_max_c"].loc[date, early])
            early_residual = float(pivots["residual_c"].loc[date, early])
            late_residual = float(pivots["residual_c"].loc[date, late])
            revision = late_forecast - early_forecast
            abs_improvement = (
                float(pivots["absolute_error_c"].loc[date, early])
                - float(pivots["absolute_error_c"].loc[date, late])
            )
            square_improvement = (
                float(pivots["squared_error_c"].loc[date, early])
                - float(pivots["squared_error_c"].loc[date, late])
            )

            update_occurred = abs(revision) > tolerance
            correction_needed = abs(early_residual) > tolerance
            directionally_correct = (
                bool(revision * early_residual > tolerance)
                if update_occurred and correction_needed else np.nan
            )
            crossed_target = (
                update_occurred
                and correction_needed
                and early_residual * late_residual < -tolerance
            )
            exact_target = abs(late_residual) <= tolerance
            overshoot = bool(
                update_occurred
                and correction_needed
                and revision * early_residual > tolerance
                and abs(revision) > abs(early_residual) + tolerance
            )
            fraction_needed = (
                revision / early_residual if correction_needed else np.nan
            )
            improvement_state = (
                "improved" if abs_improvement > tolerance
                else "worsened" if abs_improvement < -tolerance
                else "unchanged"
            )

            rows.append(
                {
                    "target_date": date,
                    "transition_order": transition_order,
                    "transition": transition["transition"],
                    "transition_family": transition["transition_family"],
                    "early_rule": early,
                    "late_rule": late,
                    "hko_daily_max_c": hko,
                    "early_forecast_c": early_forecast,
                    "late_forecast_c": late_forecast,
                    "forecast_revision_c": revision,
                    "absolute_forecast_revision_c": abs(revision),
                    "early_residual_c": early_residual,
                    "late_residual_c": late_residual,
                    "residual_change_c": late_residual - early_residual,
                    "early_absolute_error_c": abs(early_residual),
                    "late_absolute_error_c": abs(late_residual),
                    "absolute_error_improvement_c": abs_improvement,
                    "early_squared_error_c2": early_residual ** 2,
                    "late_squared_error_c2": late_residual ** 2,
                    "squared_error_improvement_c2": square_improvement,
                    "update_occurred": update_occurred,
                    "correction_needed": correction_needed,
                    "directionally_correct_update": directionally_correct,
                    "crossed_settlement_target": crossed_target,
                    "ended_exactly_at_target": exact_target,
                    "overshot_settlement_target": overshoot,
                    "fraction_of_early_needed_correction": fraction_needed,
                    "improvement_state": improvement_state,
                }
            )
    return pd.DataFrame(rows)


def deterministic_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for transition, group in panel.groupby("transition", sort=False):
        relationship = linear_relationship(
            group["early_residual_c"].to_numpy(dtype=float),
            group["forecast_revision_c"].to_numpy(dtype=float),
        )
        updates = group.loc[group["update_occurred"]]
        correct_updates = updates["directionally_correct_update"].dropna()
        rows.append(
            {
                "transition": transition,
                "transition_family": group["transition_family"].iloc[0],
                "early_rule": group["early_rule"].iloc[0],
                "late_rule": group["late_rule"].iloc[0],
                "dates": int(group["target_date"].nunique()),
                "mean_forecast_revision_c": float(group["forecast_revision_c"].mean()),
                "median_forecast_revision_c": float(group["forecast_revision_c"].median()),
                "mean_absolute_forecast_revision_c": float(
                    group["absolute_forecast_revision_c"].mean()
                ),
                "q90_absolute_forecast_revision_c": float(
                    group["absolute_forecast_revision_c"].quantile(0.90)
                ),
                "update_rate": float(group["update_occurred"].mean()),
                "mean_early_residual_c": float(group["early_residual_c"].mean()),
                "mean_late_residual_c": float(group["late_residual_c"].mean()),
                "early_mae_c": float(group["early_absolute_error_c"].mean()),
                "late_mae_c": float(group["late_absolute_error_c"].mean()),
                "mean_absolute_error_improvement_c": float(
                    group["absolute_error_improvement_c"].mean()
                ),
                "early_rmse_c": float(
                    np.sqrt(group["early_squared_error_c2"].mean())
                ),
                "late_rmse_c": float(
                    np.sqrt(group["late_squared_error_c2"].mean())
                ),
                "mean_squared_error_improvement_c2": float(
                    group["squared_error_improvement_c2"].mean()
                ),
                "improved_date_fraction": float(
                    (group["improvement_state"] == "improved").mean()
                ),
                "worsened_date_fraction": float(
                    (group["improvement_state"] == "worsened").mean()
                ),
                "unchanged_date_fraction": float(
                    (group["improvement_state"] == "unchanged").mean()
                ),
                "directionally_correct_fraction_among_updates": (
                    float(correct_updates.mean()) if len(correct_updates) else np.nan
                ),
                "overshoot_fraction_among_updates": (
                    float(updates["overshot_settlement_target"].mean())
                    if len(updates) else np.nan
                ),
                "target_crossing_fraction": float(
                    group["crossed_settlement_target"].mean()
                ),
                "revision_on_needed_correction_intercept": relationship["intercept"],
                "revision_on_needed_correction_slope": relationship["slope"],
                "revision_on_needed_correction_r_squared": relationship["r_squared"],
                "revision_needed_correction_pearson": relationship[
                    "pearson_correlation"
                ],
                "revision_needed_correction_spearman": relationship[
                    "spearman_correlation"
                ],
            }
        )
    return pd.DataFrame(rows)


def bootstrap_transition_metrics(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
    metric_type: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Vectorised date-resampling inference.

    Each group has one row per settlement date. Ordinary and circular
    moving-block resampling therefore act directly on ordered date indices.
    """
    reps = int(config["bootstrap"]["replications"])
    seed = int(config["bootstrap"]["seed"])
    confidence = float(config["bootstrap"]["confidence_level"])
    chunk_size = int(config["bootstrap"]["chunk_size"])
    block_lengths = list(map(int, config["bootstrap"]["moving_block_lengths"]))

    if metric_type == "deterministic":
        group_columns = ["transition"]
        metric_names = [
            "mean_forecast_revision_c",
            "mean_absolute_forecast_revision_c",
            "mean_absolute_error_improvement_c",
            "mean_squared_error_improvement_c2",
            "improved_date_fraction",
            "directionally_correct_fraction_among_updates",
        ]
        test_column = "absolute_error_improvement_c"
        test_name = "mean_absolute_error_improvement_equals_zero"
    elif metric_type == "probabilistic":
        group_columns = ["model", "transition"]
        metric_names = [
            "mean_crps_improvement_c",
            "median_crps_improvement_c",
            "improved_date_fraction",
            "mean_absolute_crps_change_c",
        ]
        test_column = "crps_improvement_c"
        test_name = "mean_crps_improvement_equals_zero"
    else:
        raise ValueError(metric_type)

    interval_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []

    grouped = list(panel.groupby(group_columns, sort=False))
    for group_index, (keys, group) in enumerate(grouped):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_map = dict(zip(group_columns, keys))
        group = group.sort_values("target_date").reset_index(drop=True)
        n = len(group)

        if metric_type == "deterministic":
            revision = group["forecast_revision_c"].to_numpy(dtype=float)
            absolute_revision = group[
                "absolute_forecast_revision_c"
            ].to_numpy(dtype=float)
            absolute_improvement = group[
                "absolute_error_improvement_c"
            ].to_numpy(dtype=float)
            squared_improvement = group[
                "squared_error_improvement_c2"
            ].to_numpy(dtype=float)
            improved = (
                group["improvement_state"].to_numpy(dtype=object) == "improved"
            ).astype(float)
            update = group["update_occurred"].astype(bool).to_numpy()
            correct_raw = pd.to_numeric(
                group["directionally_correct_update"], errors="coerce"
            ).to_numpy(dtype=float)

            point_estimates = {
                "mean_forecast_revision_c": float(np.mean(revision)),
                "mean_absolute_forecast_revision_c": float(
                    np.mean(absolute_revision)
                ),
                "mean_absolute_error_improvement_c": float(
                    np.mean(absolute_improvement)
                ),
                "mean_squared_error_improvement_c2": float(
                    np.mean(squared_improvement)
                ),
                "improved_date_fraction": float(np.mean(improved)),
                "directionally_correct_fraction_among_updates": float(
                    np.nanmean(correct_raw[update])
                ) if np.any(update) else np.nan,
            }
            test_values = absolute_improvement
        else:
            crps_improvement = group[
                "crps_improvement_c"
            ].to_numpy(dtype=float)
            point_estimates = {
                "mean_crps_improvement_c": float(
                    np.mean(crps_improvement)
                ),
                "median_crps_improvement_c": float(
                    np.median(crps_improvement)
                ),
                "improved_date_fraction": float(
                    np.mean(crps_improvement > 0.0)
                ),
                "mean_absolute_crps_change_c": float(
                    np.mean(np.abs(crps_improvement))
                ),
            }
            test_values = crps_improvement

        methods: list[tuple[str, int | None]] = [("ordinary_date", None)]
        methods.extend(("circular_moving_block", b) for b in block_lengths)

        for method_index, (method, block_length) in enumerate(methods):
            local_seed = (
                seed
                + 10_000 * (1 if metric_type == "probabilistic" else 0)
                + group_index * 100
                + method_index
            )
            rng = np.random.default_rng(local_seed)
            distributions: dict[str, list[np.ndarray]] = {
                metric: [] for metric in metric_names
            }
            null_parts: list[np.ndarray] = []
            observed_test = float(np.mean(test_values))
            centred_values = test_values - observed_test

            completed = 0
            while completed < reps:
                current = min(chunk_size, reps - completed)
                if method == "ordinary_date":
                    indices = ordinary_indices(n, current, rng)
                else:
                    assert block_length is not None
                    indices = moving_block_indices(
                        n, block_length, current, rng
                    )

                if metric_type == "deterministic":
                    distributions["mean_forecast_revision_c"].append(
                        revision[indices].mean(axis=1)
                    )
                    distributions[
                        "mean_absolute_forecast_revision_c"
                    ].append(absolute_revision[indices].mean(axis=1))
                    distributions[
                        "mean_absolute_error_improvement_c"
                    ].append(absolute_improvement[indices].mean(axis=1))
                    distributions[
                        "mean_squared_error_improvement_c2"
                    ].append(squared_improvement[indices].mean(axis=1))
                    distributions["improved_date_fraction"].append(
                        improved[indices].mean(axis=1)
                    )

                    sampled_update = update[indices]
                    sampled_correct = np.nan_to_num(
                        correct_raw[indices],
                        nan=0.0,
                    )
                    numerator = (
                        sampled_correct * sampled_update
                    ).sum(axis=1)
                    denominator = sampled_update.sum(axis=1)
                    correct_fraction = np.divide(
                        numerator,
                        denominator,
                        out=np.full(current, np.nan, dtype=float),
                        where=denominator > 0,
                    )
                    distributions[
                        "directionally_correct_fraction_among_updates"
                    ].append(correct_fraction)
                else:
                    sampled = crps_improvement[indices]
                    distributions["mean_crps_improvement_c"].append(
                        sampled.mean(axis=1)
                    )
                    distributions["median_crps_improvement_c"].append(
                        np.median(sampled, axis=1)
                    )
                    distributions["improved_date_fraction"].append(
                        (sampled > 0.0).mean(axis=1)
                    )
                    distributions["mean_absolute_crps_change_c"].append(
                        np.abs(sampled).mean(axis=1)
                    )

                null_parts.append(
                    centred_values[indices].mean(axis=1)
                )
                completed += current

            for metric, parts in distributions.items():
                values_array = np.concatenate(parts)
                lower, upper = percentile_interval(
                    values_array, confidence
                )
                interval_rows.append(
                    {
                        **key_map,
                        "dates": n,
                        "metric": metric,
                        "point_estimate": point_estimates[metric],
                        "bootstrap_method": method,
                        "block_length_days": block_length,
                        "bootstrap_lower_95": lower,
                        "bootstrap_upper_95": upper,
                        "bootstrap_replications": reps,
                        "seed": local_seed,
                        "bootstrap_unit": "settlement_date",
                    }
                )

            null_distribution = np.concatenate(null_parts)
            p_value = float(
                (
                    1
                    + np.sum(
                        np.abs(null_distribution)
                        >= abs(observed_test)
                    )
                )
                / (reps + 1)
            )
            test_rows.append(
                {
                    **key_map,
                    "dates": n,
                    "null_hypothesis": test_name,
                    "observed_mean": observed_test,
                    "bootstrap_method": method,
                    "block_length_days": block_length,
                    "two_sided_centred_bootstrap_p_value": p_value,
                    "minimum_resolvable_p_value": 1.0 / (reps + 1),
                    "bootstrap_replications": reps,
                    "seed": local_seed,
                    "bootstrap_unit": "settlement_date",
                }
            )

    return pd.DataFrame(interval_rows), pd.DataFrame(test_rows)


def deterministic_nonparametric_tests(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for transition, group in panel.groupby("transition", sort=False):
        values = group["absolute_error_improvement_c"].to_numpy(dtype=float)
        nonzero = values[np.abs(values) > 1e-12]
        if len(nonzero):
            binomial = stats.binomtest(
                int(np.sum(nonzero > 0)),
                n=len(nonzero),
                p=0.5,
                alternative="two-sided",
            )
            try:
                wilcoxon = stats.wilcoxon(
                    values,
                    zero_method="wilcox",
                    alternative="two-sided",
                    method="auto",
                )
                wilcoxon_stat = float(wilcoxon.statistic)
                wilcoxon_p = float(wilcoxon.pvalue)
            except ValueError:
                wilcoxon_stat = np.nan
                wilcoxon_p = np.nan
        else:
            binomial = None
            wilcoxon_stat = np.nan
            wilcoxon_p = np.nan

        rows.append(
            {
                "transition": transition,
                "dates": len(group),
                "nonzero_absolute_error_changes": len(nonzero),
                "dates_improved": int(np.sum(values > 1e-12)),
                "dates_worsened": int(np.sum(values < -1e-12)),
                "two_sided_sign_test_p_value": (
                    float(binomial.pvalue) if binomial is not None else np.nan
                ),
                "wilcoxon_signed_rank_statistic": wilcoxon_stat,
                "wilcoxon_nominal_p_value": wilcoxon_p,
                "caveat": (
                    "Descriptive paired tests; moving-block bootstrap is the "
                    "dependence-aware sensitivity."
                ),
            }
        )
    return pd.DataFrame(rows)


def deterministic_stability_tables(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> dict[str, pd.DataFrame]:
    frame = panel.copy()
    frame["target_date_dt"] = pd.to_datetime(frame["target_date"])
    frame["target_year"] = frame["target_date_dt"].dt.year
    frame["target_month"] = frame["target_date_dt"].dt.month
    frame["season"] = season_from_month(frame["target_month"])

    date_order = pd.DataFrame(
        {"target_date": sorted(frame["target_date"].unique())}
    )
    n_dates = len(date_order)
    n_blocks = int(config["chronological_blocks"])
    date_order["chronological_block"] = (
        np.floor(np.arange(n_dates) * n_blocks / n_dates).astype(int) + 1
    )
    frame = frame.merge(
        date_order,
        on="target_date",
        how="left",
        validate="many_to_one",
    )

    frame["early_residual_magnitude_quartile"] = (
        frame.groupby("transition")["early_residual_c"]
        .transform(
            lambda values: pd.qcut(
                values.abs().rank(method="first"),
                q=4,
                labels=["Q1", "Q2", "Q3", "Q4"],
            ).astype(str)
        )
    )

    def summarise(group_columns: Sequence[str], name: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for keys, group in frame.groupby(list(group_columns), dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            rows.append(
                {
                    "analysis": name,
                    **dict(zip(group_columns, keys)),
                    "dates": int(group["target_date"].nunique()),
                    "mean_revision_c": float(group["forecast_revision_c"].mean()),
                    "mean_absolute_revision_c": float(
                        group["absolute_forecast_revision_c"].mean()
                    ),
                    "mean_absolute_error_improvement_c": float(
                        group["absolute_error_improvement_c"].mean()
                    ),
                    "improved_date_fraction": float(
                        (group["improvement_state"] == "improved").mean()
                    ),
                    "directionally_correct_fraction_among_updates": float(
                        group.loc[
                            group["update_occurred"],
                            "directionally_correct_update",
                        ].dropna().mean()
                    ),
                }
            )
        return pd.DataFrame(rows)

    return {
        "year": summarise(["transition", "target_year"], "by_year"),
        "season": summarise(["transition", "season"], "by_season"),
        "chronological_block": summarise(
            ["transition", "chronological_block"],
            "by_chronological_block",
        ),
        "early_error_quartile": summarise(
            ["transition", "early_residual_magnitude_quartile"],
            "by_early_error_magnitude_quartile",
        ),
    }


def assign_static_parameters(
    validation_rows: pd.DataFrame,
    registry: pd.DataFrame,
) -> pd.DataFrame:
    parameters = registry.copy()
    parameters["validation_start_dt"] = pd.to_datetime(
        parameters["validation_start"], errors="coerce"
    )
    parameters["validation_end_dt"] = pd.to_datetime(
        parameters["validation_end"], errors="coerce"
    )
    parameters["residual_mean_c"] = pd.to_numeric(
        parameters["residual_mean_c"], errors="coerce"
    )
    parameters["residual_standard_deviation_c"] = pd.to_numeric(
        parameters["residual_standard_deviation_c"], errors="coerce"
    )
    parameters = parameters.loc[
        parameters["validation_start_dt"].notna()
        & parameters["validation_end_dt"].notna()
        & parameters["residual_mean_c"].notna()
        & parameters["residual_standard_deviation_c"].notna()
    ].copy()

    rows: list[dict[str, Any]] = []
    for record in validation_rows.to_dict("records"):
        date = pd.Timestamp(record["target_date"])
        rule = record["decision_rule"]
        matches = parameters.loc[
            (parameters["decision_rule"].astype(str) == str(rule))
            & (parameters["validation_start_dt"] <= date)
            & (parameters["validation_end_dt"] >= date)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one static parameter row for {date.date()} {rule}; "
                f"found {len(matches)}"
            )
        parameter = matches.iloc[0]
        rows.append(
            {
                **record,
                "static_fold_id": parameter["fold_id"],
                "static_residual_mean_c": float(parameter["residual_mean_c"]),
                "static_residual_sd_c": float(
                    parameter["residual_standard_deviation_c"]
                ),
            }
        )
    return pd.DataFrame(rows)


def build_probabilistic_loss_panel(
    weather: pd.DataFrame,
    gp: pd.DataFrame,
    static_registry: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    gp_frame = gp.copy()
    gp_frame["target_date"] = pd.to_datetime(
        gp_frame["target_date"]
    ).dt.strftime("%Y-%m-%d")
    gp_frame["kernel_normalised"] = gp_frame["kernel"].map(normalise_kernel)

    validation_dates = sorted(gp_frame["target_date"].unique())
    base = weather.copy()
    base["target_date"] = pd.to_datetime(
        base["target_date"]
    ).dt.strftime("%Y-%m-%d")
    base = base.loc[base["target_date"].isin(validation_dates)].copy()
    base = base[
        [
            "target_date", "decision_rule", "forecast_daily_max_c",
            "hko_daily_max_c", "residual_c", "absolute_error_c",
        ]
    ]
    if len(base) != len(validation_dates) * len(RULE_ORDER):
        raise ValueError("Validation weather support is incomplete")

    assigned = assign_static_parameters(base, static_registry)
    assigned["static_temperature_mean_c"] = (
        assigned["forecast_daily_max_c"]
        + assigned["static_residual_mean_c"]
    )
    assigned["static_crps_c"] = gaussian_crps(
        assigned["hko_daily_max_c"].to_numpy(dtype=float),
        assigned["static_temperature_mean_c"].to_numpy(dtype=float),
        assigned["static_residual_sd_c"].to_numpy(dtype=float),
    )

    raw = assigned[
        [
            "target_date", "decision_rule", "forecast_daily_max_c",
            "hko_daily_max_c",
        ]
    ].copy()
    raw["model"] = "raw"
    raw["crps_c"] = assigned["absolute_error_c"].to_numpy(dtype=float)
    raw["temperature_predictive_mean_c"] = assigned[
        "forecast_daily_max_c"
    ].to_numpy(dtype=float)
    raw["predictive_standard_deviation_c"] = 0.0
    raw["residual_predictive_mean_c"] = 0.0
    raw["source"] = "raw_point_crps_equals_absolute_error"

    static = assigned[
        [
            "target_date", "decision_rule", "forecast_daily_max_c",
            "hko_daily_max_c",
        ]
    ].copy()
    static["model"] = "static"
    static["crps_c"] = assigned["static_crps_c"].to_numpy(dtype=float)
    static["temperature_predictive_mean_c"] = assigned[
        "static_temperature_mean_c"
    ].to_numpy(dtype=float)
    static["predictive_standard_deviation_c"] = assigned[
        "static_residual_sd_c"
    ].to_numpy(dtype=float)
    static["residual_predictive_mean_c"] = assigned[
        "static_residual_mean_c"
    ].to_numpy(dtype=float)
    static["source"] = "phase16_fold_specific_static_gaussian"

    gp_output = gp_frame[
        [
            "target_date", "decision_rule", "forecast_daily_max_c",
            "hko_daily_max_c", "kernel_normalised", "crps_c",
            "temperature_predictive_mean_c",
            "predictive_standard_deviation_c",
            "residual_predictive_mean_c",
        ]
    ].copy()
    gp_output = gp_output.rename(columns={"kernel_normalised": "model"})
    gp_output["source"] = "phase7_chronological_gp_validation"

    panel = pd.concat([raw, static, gp_output], ignore_index=True)
    panel["model"] = panel["model"].map(normalise_model)
    panel = panel.sort_values(
        ["target_date", "decision_rule", "model"]
    ).reset_index(drop=True)

    expected_rows = len(validation_dates) * len(RULE_ORDER) * len(MODEL_ORDER)
    if len(panel) != expected_rows:
        raise ValueError(
            f"Probabilistic loss panel has {len(panel)} rows, "
            f"expected {expected_rows}"
        )
    duplicate_count = int(
        panel.duplicated(["target_date", "decision_rule", "model"]).sum()
    )
    if duplicate_count:
        raise ValueError(f"Probabilistic loss panel duplicates={duplicate_count}")

    date_losses = (
        panel.groupby(["model", "target_date"], as_index=False)
        .agg(date_crps_c=("crps_c", "mean"), date_rules=("decision_rule", "nunique"))
    )
    return panel, date_losses


def probabilistic_crosschecks(
    loss_panel: pd.DataFrame,
    date_losses: pd.DataFrame,
    frozen_root: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    tolerance = float(config["numerical_tolerance"])

    overall_path = (
        frozen_root / config["input_paths"]["phase16_model_scores_overall"]
    )
    rule_path = (
        frozen_root / config["input_paths"]["phase16_model_scores_by_rule"]
    )
    date_path = (
        frozen_root / config["input_paths"]["phase16_date_level_model_losses"]
    )

    if not (overall_path.is_file() and rule_path.is_file() and date_path.is_file()):
        return pd.DataFrame(
            [
                {
                    "scope": "input",
                    "model": "",
                    "metric": "phase16_crosscheck_files",
                    "phase3_value": np.nan,
                    "phase16_value": np.nan,
                    "difference": np.nan,
                    "passed": False,
                    "detail": "one or more Phase 16 cross-check files are missing",
                }
            ]
        )

    overall = pd.read_csv(overall_path)
    overall["model_normalised"] = overall["model"].map(normalise_model)
    calculated_overall = (
        date_losses.groupby("model", as_index=False)["date_crps_c"]
        .mean()
        .rename(columns={"date_crps_c": "phase3_value"})
    )
    merged = calculated_overall.merge(
        overall[["model_normalised", "mean_date_crps_c"]],
        left_on="model",
        right_on="model_normalised",
        how="left",
        validate="one_to_one",
    )
    for record in merged.to_dict("records"):
        difference = float(
            record["phase3_value"] - record["mean_date_crps_c"]
        )
        rows.append(
            {
                "scope": "overall_mean_date",
                "model": record["model"],
                "metric": "mean_date_crps_c",
                "phase3_value": record["phase3_value"],
                "phase16_value": record["mean_date_crps_c"],
                "difference": difference,
                "passed": abs(difference) <= tolerance,
                "detail": "",
            }
        )

    rule = pd.read_csv(rule_path)
    rule["model_normalised"] = rule["model"].map(normalise_model)
    calculated_rule = (
        loss_panel.groupby(["model", "decision_rule"], as_index=False)["crps_c"]
        .mean()
        .rename(columns={"crps_c": "phase3_value"})
    )
    rule_merged = calculated_rule.merge(
        rule[["model_normalised", "decision_rule", "mean_crps_c"]],
        left_on=["model", "decision_rule"],
        right_on=["model_normalised", "decision_rule"],
        how="left",
        validate="one_to_one",
    )
    for record in rule_merged.to_dict("records"):
        difference = float(record["phase3_value"] - record["mean_crps_c"])
        rows.append(
            {
                "scope": "rule",
                "model": record["model"],
                "decision_rule": record["decision_rule"],
                "metric": "mean_crps_c",
                "phase3_value": record["phase3_value"],
                "phase16_value": record["mean_crps_c"],
                "difference": difference,
                "passed": abs(difference) <= tolerance,
                "detail": "",
            }
        )

    frozen_dates = pd.read_csv(date_path)
    frozen_dates["model_normalised"] = frozen_dates["model"].map(normalise_model)
    date_merged = date_losses.merge(
        frozen_dates[["model_normalised", "target_date", "date_crps_c"]],
        left_on=["model", "target_date"],
        right_on=["model_normalised", "target_date"],
        how="left",
        validate="one_to_one",
        suffixes=("_phase3", "_phase16"),
    )
    date_merged["difference"] = (
        date_merged["date_crps_c_phase3"]
        - date_merged["date_crps_c_phase16"]
    )
    for model, group in date_merged.groupby("model"):
        max_difference = float(group["difference"].abs().max())
        rows.append(
            {
                "scope": "date_level",
                "model": model,
                "metric": "maximum_absolute_date_crps_difference",
                "phase3_value": max_difference,
                "phase16_value": 0.0,
                "difference": max_difference,
                "passed": max_difference <= tolerance,
                "detail": f"dates={len(group)}",
            }
        )

    return pd.DataFrame(rows)


def build_probabilistic_transition_panel(
    loss_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model in MODEL_ORDER:
        model_frame = loss_panel.loc[loss_panel["model"] == model]
        crps = model_frame.pivot(
            index="target_date",
            columns="decision_rule",
            values="crps_c",
        ).reindex(columns=RULE_ORDER)
        if crps.isna().any().any():
            raise ValueError(f"Incomplete CRPS pivot for {model}")

        for transition_order, transition in enumerate(
            config["transitions"], start=1
        ):
            early = transition["early_rule"]
            late = transition["late_rule"]
            for date in crps.index:
                early_loss = float(crps.loc[date, early])
                late_loss = float(crps.loc[date, late])
                rows.append(
                    {
                        "target_date": date,
                        "model": model,
                        "transition_order": transition_order,
                        "transition": transition["transition"],
                        "transition_family": transition["transition_family"],
                        "early_rule": early,
                        "late_rule": late,
                        "early_crps_c": early_loss,
                        "late_crps_c": late_loss,
                        "crps_improvement_c": early_loss - late_loss,
                        "absolute_crps_change_c": abs(early_loss - late_loss),
                    }
                )
    return pd.DataFrame(rows)


def probabilistic_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (model, transition), group in panel.groupby(
        ["model", "transition"], sort=False
    ):
        values = group["crps_improvement_c"].to_numpy(dtype=float)
        rows.append(
            {
                "model": model,
                "transition": transition,
                "transition_family": group["transition_family"].iloc[0],
                "early_rule": group["early_rule"].iloc[0],
                "late_rule": group["late_rule"].iloc[0],
                "dates": len(group),
                "early_mean_crps_c": float(group["early_crps_c"].mean()),
                "late_mean_crps_c": float(group["late_crps_c"].mean()),
                "mean_crps_improvement_c": float(np.mean(values)),
                "median_crps_improvement_c": float(np.median(values)),
                "improved_date_fraction": float(np.mean(values > 0)),
                "worsened_date_fraction": float(np.mean(values < 0)),
                "unchanged_date_fraction": float(np.mean(values == 0)),
                "mean_absolute_crps_change_c": float(np.mean(np.abs(values))),
                "q05_crps_improvement_c": float(np.quantile(values, 0.05)),
                "q95_crps_improvement_c": float(np.quantile(values, 0.95)),
            }
        )
    return pd.DataFrame(rows)


def gp_distribution_revision_panel(
    loss_panel: pd.DataFrame,
    deterministic_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    det = deterministic_panel[
        [
            "target_date", "transition", "forecast_revision_c",
            "absolute_forecast_revision_c", "absolute_error_improvement_c",
            "improvement_state",
        ]
    ].copy()

    for model in ["rbf", "matern"]:
        model_frame = loss_panel.loc[loss_panel["model"] == model].copy()
        mean_pivot = model_frame.pivot(
            index="target_date",
            columns="decision_rule",
            values="temperature_predictive_mean_c",
        ).reindex(columns=RULE_ORDER)
        sd_pivot = model_frame.pivot(
            index="target_date",
            columns="decision_rule",
            values="predictive_standard_deviation_c",
        ).reindex(columns=RULE_ORDER)
        residual_mean_pivot = model_frame.pivot(
            index="target_date",
            columns="decision_rule",
            values="residual_predictive_mean_c",
        ).reindex(columns=RULE_ORDER)

        if mean_pivot.isna().any().any() or sd_pivot.isna().any().any():
            raise ValueError(f"Incomplete predictive distribution pivot for {model}")

        for transition_order, transition in enumerate(
            config["transitions"], start=1
        ):
            early = transition["early_rule"]
            late = transition["late_rule"]
            for date in mean_pivot.index:
                mean_shift = float(
                    mean_pivot.loc[date, late] - mean_pivot.loc[date, early]
                )
                sd_change = float(
                    sd_pivot.loc[date, late] - sd_pivot.loc[date, early]
                )
                residual_adjustment = float(
                    residual_mean_pivot.loc[date, late]
                    - residual_mean_pivot.loc[date, early]
                )
                w2 = math.sqrt(mean_shift ** 2 + sd_change ** 2)
                rows.append(
                    {
                        "target_date": date,
                        "model": model,
                        "transition_order": transition_order,
                        "transition": transition["transition"],
                        "transition_family": transition["transition_family"],
                        "early_rule": early,
                        "late_rule": late,
                        "predictive_mean_shift_c": mean_shift,
                        "absolute_predictive_mean_shift_c": abs(mean_shift),
                        "predictive_sd_change_c": sd_change,
                        "absolute_predictive_sd_change_c": abs(sd_change),
                        "residual_correction_revision_c": residual_adjustment,
                        "absolute_residual_correction_revision_c": abs(
                            residual_adjustment
                        ),
                        "gaussian_wasserstein2_distance_c": w2,
                    }
                )

    result = pd.DataFrame(rows).merge(
        det,
        on=["target_date", "transition"],
        how="left",
        validate="many_to_one",
    )
    result["mean_shift_reconciliation_error_c"] = (
        result["predictive_mean_shift_c"]
        - result["forecast_revision_c"]
        - result["residual_correction_revision_c"]
    )
    return result


def gp_distribution_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (model, transition), group in panel.groupby(
        ["model", "transition"], sort=False
    ):
        relationship = linear_relationship(
            group["forecast_revision_c"].to_numpy(dtype=float),
            group["predictive_mean_shift_c"].to_numpy(dtype=float),
        )
        rows.append(
            {
                "model": model,
                "transition": transition,
                "transition_family": group["transition_family"].iloc[0],
                "dates": len(group),
                "mean_predictive_mean_shift_c": float(
                    group["predictive_mean_shift_c"].mean()
                ),
                "mean_absolute_predictive_mean_shift_c": float(
                    group["absolute_predictive_mean_shift_c"].mean()
                ),
                "mean_predictive_sd_change_c": float(
                    group["predictive_sd_change_c"].mean()
                ),
                "mean_absolute_predictive_sd_change_c": float(
                    group["absolute_predictive_sd_change_c"].mean()
                ),
                "mean_residual_correction_revision_c": float(
                    group["residual_correction_revision_c"].mean()
                ),
                "mean_absolute_residual_correction_revision_c": float(
                    group["absolute_residual_correction_revision_c"].mean()
                ),
                "mean_gaussian_wasserstein2_distance_c": float(
                    group["gaussian_wasserstein2_distance_c"].mean()
                ),
                "forecast_revision_predictive_shift_slope": relationship["slope"],
                "forecast_revision_predictive_shift_r_squared": relationship[
                    "r_squared"
                ],
                "maximum_reconciliation_error_c": float(
                    group["mean_shift_reconciliation_error_c"].abs().max()
                ),
            }
        )
    return pd.DataFrame(rows)


def revision_loss_relationships(
    deterministic_panel: pd.DataFrame,
    probabilistic_panel: pd.DataFrame,
) -> pd.DataFrame:
    merged = probabilistic_panel.merge(
        deterministic_panel[
            [
                "target_date", "transition", "forecast_revision_c",
                "absolute_forecast_revision_c", "early_residual_c",
                "absolute_error_improvement_c", "update_occurred",
                "directionally_correct_update",
            ]
        ],
        on=["target_date", "transition"],
        how="left",
        validate="many_to_one",
    )
    rows: list[dict[str, Any]] = []
    for (model, transition), group in merged.groupby(
        ["model", "transition"], sort=False
    ):
        abs_relation = linear_relationship(
            group["absolute_forecast_revision_c"].to_numpy(dtype=float),
            group["crps_improvement_c"].to_numpy(dtype=float),
        )
        correction_relation = linear_relationship(
            np.abs(group["early_residual_c"].to_numpy(dtype=float)),
            group["crps_improvement_c"].to_numpy(dtype=float),
        )
        correct = group.loc[
            group["directionally_correct_update"] == True,  # noqa: E712
            "crps_improvement_c",
        ]
        incorrect = group.loc[
            group["directionally_correct_update"] == False,  # noqa: E712
            "crps_improvement_c",
        ]
        rows.append(
            {
                "model": model,
                "transition": transition,
                "dates": len(group),
                "absolute_revision_crps_improvement_pearson": abs_relation[
                    "pearson_correlation"
                ],
                "absolute_revision_crps_improvement_spearman": abs_relation[
                    "spearman_correlation"
                ],
                "absolute_revision_crps_improvement_slope": abs_relation["slope"],
                "absolute_revision_crps_improvement_r_squared": abs_relation[
                    "r_squared"
                ],
                "early_error_magnitude_crps_improvement_pearson": correction_relation[
                    "pearson_correlation"
                ],
                "mean_crps_improvement_directionally_correct_updates_c": (
                    float(correct.mean()) if len(correct) else np.nan
                ),
                "mean_crps_improvement_directionally_incorrect_updates_c": (
                    float(incorrect.mean()) if len(incorrect) else np.nan
                ),
                "correct_minus_incorrect_mean_crps_improvement_c": (
                    float(correct.mean() - incorrect.mean())
                    if len(correct) and len(incorrect) else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def rule_path_summary(
    weather: pd.DataFrame,
    loss_panel: pd.DataFrame,
) -> pd.DataFrame:
    weather_summary = (
        weather.groupby("decision_rule", as_index=False)
        .agg(
            dates=("target_date", "nunique"),
            mean_deterministic_forecast_c=("forecast_daily_max_c", "mean"),
            mean_hko_settlement_c=("hko_daily_max_c", "mean"),
            mean_residual_c=("residual_c", "mean"),
            mean_absolute_error_c=("absolute_error_c", "mean"),
            root_mean_squared_error_c=(
                "squared_error_c",
                lambda values: float(np.sqrt(np.mean(values))),
            ),
        )
    )
    crps_summary = (
        loss_panel.groupby(["model", "decision_rule"], as_index=False)
        .agg(mean_crps_c=("crps_c", "mean"))
        .pivot(index="decision_rule", columns="model", values="mean_crps_c")
        .reset_index()
    )
    crps_summary.columns = [
        "decision_rule"
        if column == "decision_rule"
        else f"{column}_mean_crps_c"
        for column in crps_summary.columns
    ]
    result = weather_summary.merge(
        crps_summary,
        on="decision_rule",
        how="left",
        validate="one_to_one",
    )
    result["decision_rule_order"] = result["decision_rule"].map(
        {rule: index for index, rule in enumerate(RULE_ORDER)}
    )
    return result.sort_values("decision_rule_order")


def make_figures(
    deterministic_panel: pd.DataFrame,
    deterministic_summary_frame: pd.DataFrame,
    rule_summary: pd.DataFrame,
    probabilistic_summary_frame: pd.DataFrame,
    gp_summary: pd.DataFrame,
    output_dir: Path,
    dpi: int,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata: list[dict[str, Any]] = []

    # 1. Mean deterministic forecast and HKO path.
    ordered = rule_summary.sort_values("decision_rule_order")
    labels = [RULE_LABELS[r] for r in ordered["decision_rule"]]
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(labels, ordered["mean_deterministic_forecast_c"], marker="o",
            label="Mean deterministic forecast")
    ax.plot(labels, ordered["mean_hko_settlement_c"], marker="o",
            label="Mean HKO settlement")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Forecast level across decision rules")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase3_figure_mean_forecast_path.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Main-text candidate: mean forecast path and persistent settlement gap",
    })

    # 2. Deterministic error path.
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(labels, ordered["mean_residual_c"], marker="o", label="Mean residual")
    ax.plot(
        labels,
        ordered["mean_absolute_error_c"],
        marker="o",
        label="Mean absolute error",
    )
    ax.plot(
        labels,
        ordered["root_mean_squared_error_c"],
        marker="o",
        label="Root mean squared error",
    )
    ax.set_ylabel("Error (°C)")
    ax.set_title("Settlement error across decision rules")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase3_figure_error_path_by_rule.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Main-text candidate: precision improves more than mean displacement",
    })

    # 3. Absolute-error improvement distribution.
    adjacent = deterministic_panel.loc[
        deterministic_panel["transition_family"] == "adjacent"
    ]
    transition_order = [
        item for item in deterministic_summary_frame["transition"]
        if item in set(adjacent["transition"])
    ]
    data = [
        adjacent.loc[
            adjacent["transition"] == transition,
            "absolute_error_improvement_c",
        ].to_numpy()
        for transition in transition_order
    ]
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.boxplot(data, labels=transition_order, showfliers=True)
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_ylabel("Earlier MAE minus later MAE (°C)")
    ax.set_title("Date-level absolute-error change after forecast revision")
    fig.tight_layout()
    path = output_dir / "phase3_figure_absolute_error_improvement.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: heterogeneous benefit of each adjacent update",
    })

    # 4. Revision versus needed correction for endpoint transition.
    endpoint = deterministic_panel.loc[
        deterministic_panel["transition"] == "24h_to_open"
    ]
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    ax.scatter(
        endpoint["early_residual_c"],
        endpoint["forecast_revision_c"],
        s=12,
        alpha=0.45,
    )
    lower = float(
        min(endpoint["early_residual_c"].min(), endpoint["forecast_revision_c"].min())
    )
    upper = float(
        max(endpoint["early_residual_c"].max(), endpoint["forecast_revision_c"].max())
    )
    ax.plot([lower, upper], [lower, upper], linestyle="--", linewidth=1)
    ax.axhline(0.0, linewidth=1)
    ax.axvline(0.0, linewidth=1)
    ax.set_xlabel("Correction needed at 24h rule (°C)")
    ax.set_ylabel("Forecast revision from 24h to open (°C)")
    ax.set_title("Forecast revision versus settlement correction needed")
    fig.tight_layout()
    path = output_dir / "phase3_figure_revision_vs_needed_correction.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: direction and magnitude of forecast revisions",
    })

    # 5. Mean CRPS by rule and model.
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for model in MODEL_ORDER:
        column = f"{model}_mean_crps_c"
        ax.plot(labels, ordered[column], marker="o", label=MODEL_LABELS[model])
    ax.set_ylabel("Mean CRPS (°C)")
    ax.set_title("Out-of-sample probabilistic loss across decision rules")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase3_figure_crps_path_by_model_rule.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: whether later rules lower probabilistic loss",
    })

    # 6. Adjacent CRPS improvement by model.
    adjacent_prob = probabilistic_summary_frame.loc[
        probabilistic_summary_frame["transition_family"] == "adjacent"
    ].copy()
    positions = np.arange(3, dtype=float)
    width = 0.18
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    for model_index, model in enumerate(MODEL_ORDER):
        sub = adjacent_prob.loc[adjacent_prob["model"] == model]
        sub = sub.set_index("transition").reindex(
            ["24h_to_12h", "12h_to_6h", "6h_to_open"]
        )
        ax.bar(
            positions + (model_index - 1.5) * width,
            sub["mean_crps_improvement_c"].to_numpy(),
            width=width,
            label=MODEL_LABELS[model],
        )
    ax.axhline(0.0, linewidth=1)
    ax.set_xticks(positions)
    ax.set_xticklabels(["24h→12h", "12h→6h", "6h→open"])
    ax.set_ylabel("Earlier CRPS minus later CRPS (°C)")
    ax.set_title("Average adjacent-rule CRPS change")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase3_figure_adjacent_crps_improvement.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: probabilistic effect of later decision rules",
    })

    # 7. GP predictive mean-shift decomposition.
    endpoint_gp = gp_summary.loc[
        gp_summary["transition"] == "24h_to_open"
    ].copy()
    x = np.arange(len(endpoint_gp))
    width = 0.25
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.bar(
        x - width,
        endpoint_gp["mean_absolute_predictive_mean_shift_c"],
        width=width,
        label="Absolute predictive-mean shift",
    )
    ax.bar(
        x,
        endpoint_gp["mean_absolute_residual_correction_revision_c"],
        width=width,
        label="Absolute GP correction revision",
    )
    ax.bar(
        x + width,
        endpoint_gp["mean_absolute_predictive_sd_change_c"],
        width=width,
        label="Absolute predictive-SD change",
    )
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_LABELS[m] for m in endpoint_gp["model"]])
    ax.set_ylabel("Mean absolute change (°C)")
    ax.set_title("GP distribution revision from 24h rule to event-day open")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase3_figure_gp_distribution_revision.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: deterministic and conditional GP update channels",
    })

    return pd.DataFrame(metadata)


def thesis_candidate_summary(
    deterministic_summary_frame: pd.DataFrame,
    deterministic_bootstrap: pd.DataFrame,
    probabilistic_summary_frame: pd.DataFrame,
    probabilistic_bootstrap: pd.DataFrame,
    gp_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    endpoint = deterministic_summary_frame.loc[
        deterministic_summary_frame["transition"] == "24h_to_open"
    ].iloc[0]
    endpoint_ci = deterministic_bootstrap.loc[
        (deterministic_bootstrap["transition"] == "24h_to_open")
        & (
            deterministic_bootstrap["metric"]
            == "mean_absolute_error_improvement_c"
        )
        & (deterministic_bootstrap["bootstrap_method"] == "ordinary_date")
    ].iloc[0]
    rows.append(
        {
            "candidate_id": "P3_ENDPOINT_MAE",
            "quantity": "mean 24h-to-open absolute-error improvement",
            "point_estimate": endpoint["mean_absolute_error_improvement_c"],
            "lower_95": endpoint_ci["bootstrap_lower_95"],
            "upper_95": endpoint_ci["bootstrap_upper_95"],
            "unit": "degrees Celsius",
            "preferred_location": "Results: deterministic forecast revision",
        }
    )
    rows.append(
        {
            "candidate_id": "P3_ENDPOINT_CORRECT",
            "quantity": "directionally correct 24h-to-open revisions among updates",
            "point_estimate": endpoint[
                "directionally_correct_fraction_among_updates"
            ],
            "lower_95": np.nan,
            "upper_95": np.nan,
            "unit": "proportion",
            "preferred_location": "Appendix or discussion",
        }
    )

    for model in MODEL_ORDER:
        record = probabilistic_summary_frame.loc[
            (probabilistic_summary_frame["model"] == model)
            & (probabilistic_summary_frame["transition"] == "24h_to_open")
        ].iloc[0]
        ci = probabilistic_bootstrap.loc[
            (probabilistic_bootstrap["model"] == model)
            & (probabilistic_bootstrap["transition"] == "24h_to_open")
            & (
                probabilistic_bootstrap["metric"]
                == "mean_crps_improvement_c"
            )
            & (probabilistic_bootstrap["bootstrap_method"] == "ordinary_date")
        ].iloc[0]
        rows.append(
            {
                "candidate_id": f"P3_CRPS_{model.upper()}",
                "quantity": (
                    f"{MODEL_LABELS[model]} 24h-to-open mean CRPS improvement"
                ),
                "point_estimate": record["mean_crps_improvement_c"],
                "lower_95": ci["bootstrap_lower_95"],
                "upper_95": ci["bootstrap_upper_95"],
                "unit": "degrees Celsius CRPS",
                "preferred_location": "Results or appendix, selected by materiality",
            }
        )

    for model in ["rbf", "matern"]:
        record = gp_summary.loc[
            (gp_summary["model"] == model)
            & (gp_summary["transition"] == "24h_to_open")
        ].iloc[0]
        rows.append(
            {
                "candidate_id": f"P3_GP_SHIFT_{model.upper()}",
                "quantity": (
                    f"{MODEL_LABELS[model]} mean absolute predictive-mean shift, "
                    "24h to open"
                ),
                "point_estimate": record[
                    "mean_absolute_predictive_mean_shift_c"
                ],
                "lower_95": np.nan,
                "upper_95": np.nan,
                "unit": "degrees Celsius",
                "preferred_location": "Appendix: information-set revision",
            }
        )

    return pd.DataFrame(rows)


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    deterministic_summary_frame: pd.DataFrame,
    deterministic_bootstrap: pd.DataFrame,
    probabilistic_summary_frame: pd.DataFrame,
    probabilistic_bootstrap: pd.DataFrame,
    gp_summary: pd.DataFrame,
    config: Mapping[str, Any],
) -> None:
    failures = checks.loc[
        checks["critical"].astype(bool)
        & ~checks["passed"].astype(bool)
    ]
    status = "PASSED" if failures.empty else "FAILED"

    endpoint = deterministic_summary_frame.loc[
        deterministic_summary_frame["transition"] == "24h_to_open"
    ].iloc[0]
    endpoint_ci = deterministic_bootstrap.loc[
        (deterministic_bootstrap["transition"] == "24h_to_open")
        & (
            deterministic_bootstrap["metric"]
            == "mean_absolute_error_improvement_c"
        )
        & (deterministic_bootstrap["bootstrap_method"] == "ordinary_date")
    ].iloc[0]

    lines = [
        "# Phase 3 — Information Arrival and Forecast Revision",
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
        "The phase therefore reports paired forecast revisions, not a causal "
        "estimate of the value of one newly observed meteorological variable.",
        "",
        "## Deterministic 24h-to-open result",
        "",
        (
            f"Across {int(endpoint['dates'])} dates, the mean deterministic "
            f"forecast revision is {endpoint['mean_forecast_revision_c']:.6f}°C "
            f"and the mean absolute revision is "
            f"{endpoint['mean_absolute_forecast_revision_c']:.6f}°C."
        ),
        "",
        (
            f"The mean reduction in absolute settlement error is "
            f"{endpoint['mean_absolute_error_improvement_c']:.6f}°C, with an "
            f"ordinary date-bootstrap 95% interval "
            f"[{endpoint_ci['bootstrap_lower_95']:.6f}, "
            f"{endpoint_ci['bootstrap_upper_95']:.6f}]°C."
        ),
        "",
        (
            f"The later forecast improves absolute error on "
            f"{100 * endpoint['improved_date_fraction']:.2f}% of dates and "
            f"worsens it on {100 * endpoint['worsened_date_fraction']:.2f}%."
        ),
        "",
        (
            f"Among dates with a non-zero revision, "
            f"{100 * endpoint['directionally_correct_fraction_among_updates']:.2f}% "
            f"of revisions move towards the eventual HKO settlement value."
        ),
        "",
        "## Out-of-sample CRPS revision",
        "",
    ]

    for model in MODEL_ORDER:
        record = probabilistic_summary_frame.loc[
            (probabilistic_summary_frame["model"] == model)
            & (probabilistic_summary_frame["transition"] == "24h_to_open")
        ].iloc[0]
        ci = probabilistic_bootstrap.loc[
            (probabilistic_bootstrap["model"] == model)
            & (probabilistic_bootstrap["transition"] == "24h_to_open")
            & (
                probabilistic_bootstrap["metric"]
                == "mean_crps_improvement_c"
            )
            & (probabilistic_bootstrap["bootstrap_method"] == "ordinary_date")
        ].iloc[0]
        lines.extend(
            [
                (
                    f"- **{MODEL_LABELS[model]}:** mean earlier-minus-later CRPS "
                    f"{record['mean_crps_improvement_c']:.6f}°C; 95% interval "
                    f"[{ci['bootstrap_lower_95']:.6f}, "
                    f"{ci['bootstrap_upper_95']:.6f}]."
                )
            ]
        )

    lines.extend(
        [
            "",
            "Positive CRPS improvement means that the later decision rule has "
            "lower loss. These comparisons use only the 365-date chronological "
            "validation year and reproduce the frozen Phase 16 losses.",
            "",
            "## GP distribution revision",
            "",
        ]
    )
    for model in ["rbf", "matern"]:
        record = gp_summary.loc[
            (gp_summary["model"] == model)
            & (gp_summary["transition"] == "24h_to_open")
        ].iloc[0]
        lines.extend(
            [
                (
                    f"- **{MODEL_LABELS[model]}:** mean absolute predictive-mean "
                    f"shift {record['mean_absolute_predictive_mean_shift_c']:.6f}°C; "
                    f"mean absolute conditional residual-correction revision "
                    f"{record['mean_absolute_residual_correction_revision_c']:.6f}°C; "
                    f"mean absolute predictive-SD change "
                    f"{record['mean_absolute_predictive_sd_change_c']:.6f}°C."
                )
            ]
        )

    lines.extend(
        [
            "",
            "## Thesis use",
            "",
            "- Use the rule-level error path and the 24h-to-open paired estimate if material.",
            "- Retain adjacent-transition heterogeneity and nonparametric tests in the appendix.",
            "- Use GP shift decomposition to explain how the predictive law changes, not to claim causal assimilation.",
            "- Do not interpret a small average revision as absence of new information; date-level changes can offset in the mean.",
            "- Do not infer that later rules must always be better. Proper-score changes are empirical and model-specific.",
            "",
        ]
    )
    (out / "phase3_report.md").write_text("\n".join(lines), encoding="utf-8")


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase3_manifest.json",
            "phase3_review_bundle.zip",
        }:
            files.append(
                {
                    "relative_path": path.relative_to(out).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "phase": "phase3_information_arrival",
        "generated_utc": utc_now(),
        "provenance": dict(provenance),
        "files": files,
    }
    (out / "phase3_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase3_review_bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                zf.write(path, path.relative_to(out).as_posix())


def self_test() -> None:
    assert normalise_kernel("Matern32") == "matern"
    assert normalise_kernel("RBF") == "rbf"

    y = np.array([0.0, 1.0])
    mu = np.array([0.0, 0.5])
    sd = np.array([1.0, 1.0])
    values = gaussian_crps(y, mu, sd)
    assert values.shape == (2,)
    assert np.isfinite(values).all()
    assert (values >= 0).all()

    rng = np.random.default_rng(123)
    assert ordinary_indices(10, 5, rng).shape == (5, 10)
    rng = np.random.default_rng(123)
    moving = moving_block_indices(10, 3, 5, rng)
    assert moving.shape == (5, 10)
    assert moving.min() >= 0 and moving.max() < 10

    relation = linear_relationship(
        np.array([1.0, 2.0, 3.0]),
        np.array([2.0, 4.0, 6.0]),
    )
    assert abs(relation["slope"] - 2.0) < 1e-12
    assert abs(relation["r_squared"] - 1.0) < 1e-12

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
    inputs = config["input_paths"]

    weather_path = frozen_root / inputs["weather_residual_panel"]
    gp_path = frozen_root / inputs["gp_validation_predictions"]
    static_path = frozen_root / inputs["static_parameter_registry"]
    for path in [weather_path, gp_path, static_path]:
        if not path.is_file():
            raise FileNotFoundError(path)

    provenance = {
        "generated_utc": utc_now(),
        "working_branch": git(repo_root, "branch", "--show-current"),
        "working_commit": git(repo_root, "rev-parse", "HEAD"),
        "frozen_ref": config["frozen_ref"],
        "frozen_tag_object": git(repo_root, "rev-parse", config["frozen_ref"]),
        "frozen_commit": git(
            repo_root, "rev-parse", f"{config['frozen_ref']}^{{commit}}"
        ),
        "weather_input": inputs["weather_residual_panel"],
        "weather_sha256": sha256_file(weather_path),
        "gp_validation_input": inputs["gp_validation_predictions"],
        "gp_validation_sha256": sha256_file(gp_path),
        "static_registry_input": inputs["static_parameter_registry"],
        "static_registry_sha256": sha256_file(static_path),
        "bootstrap_replications": config["bootstrap"]["replications"],
        "bootstrap_seed": config["bootstrap"]["seed"],
        "moving_block_lengths": config["bootstrap"]["moving_block_lengths"],
        "interpretation_boundary": config["interpretation_boundary"],
    }
    (out / "phase3_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    weather = pd.read_csv(weather_path, low_memory=False)
    gp = pd.read_csv(gp_path, low_memory=False)
    static_registry = pd.read_csv(static_path, low_memory=False)

    checks = validate_inputs(
        weather, gp, static_registry, config, repo_root
    )
    checks.to_csv(out / "phase3_integrity_checks.csv", index=False)
    initial_failures = checks.loc[
        checks["critical"].astype(bool)
        & ~checks["passed"].astype(bool)
    ]
    if not initial_failures.empty:
        print(checks.to_string(index=False))
        raise RuntimeError("Phase 3 input checks failed")

    for frame in [weather, gp]:
        frame["target_date"] = pd.to_datetime(
            frame["target_date"]
        ).dt.strftime("%Y-%m-%d")

    deterministic_panel = build_deterministic_transition_panel(
        weather, config
    )
    deterministic_panel.to_csv(
        out / "phase3_deterministic_transition_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    deterministic_summary_frame = deterministic_summary(
        deterministic_panel
    )
    deterministic_summary_frame.to_csv(
        out / "phase3_deterministic_transition_summary.csv",
        index=False,
    )
    deterministic_bootstrap, deterministic_tests = (
        bootstrap_transition_metrics(
            deterministic_panel,
            config,
            metric_type="deterministic",
        )
    )
    deterministic_bootstrap.to_csv(
        out / "phase3_deterministic_bootstrap_intervals.csv",
        index=False,
    )
    deterministic_tests.to_csv(
        out / "phase3_deterministic_bootstrap_tests.csv",
        index=False,
    )
    deterministic_nonparametric_tests(deterministic_panel).to_csv(
        out / "phase3_deterministic_nonparametric_tests.csv",
        index=False,
    )
    stability = deterministic_stability_tables(
        deterministic_panel, config
    )
    for name, frame in stability.items():
        frame.to_csv(
            out / f"phase3_deterministic_stability_by_{name}.csv",
            index=False,
        )

    loss_panel, date_losses = build_probabilistic_loss_panel(
        weather, gp, static_registry
    )
    loss_panel.to_csv(
        out / "phase3_validation_probabilistic_loss_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    date_losses.to_csv(
        out / "phase3_validation_date_level_model_losses.csv",
        index=False,
    )
    phase16_check = probabilistic_crosschecks(
        loss_panel, date_losses, frozen_root, config
    )
    phase16_check.to_csv(
        out / "phase3_phase16_loss_crosscheck.csv",
        index=False,
    )

    probabilistic_panel = build_probabilistic_transition_panel(
        loss_panel, config
    )
    probabilistic_panel.to_csv(
        out / "phase3_probabilistic_transition_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    probabilistic_summary_frame = probabilistic_summary(
        probabilistic_panel
    )
    probabilistic_summary_frame.to_csv(
        out / "phase3_probabilistic_transition_summary.csv",
        index=False,
    )
    probabilistic_bootstrap, probabilistic_tests = (
        bootstrap_transition_metrics(
            probabilistic_panel,
            config,
            metric_type="probabilistic",
        )
    )
    probabilistic_bootstrap.to_csv(
        out / "phase3_probabilistic_bootstrap_intervals.csv",
        index=False,
    )
    probabilistic_tests.to_csv(
        out / "phase3_probabilistic_bootstrap_tests.csv",
        index=False,
    )

    gp_revision_panel = gp_distribution_revision_panel(
        loss_panel, deterministic_panel, config
    )
    gp_revision_panel.to_csv(
        out / "phase3_gp_distribution_revision_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    gp_summary = gp_distribution_summary(gp_revision_panel)
    gp_summary.to_csv(
        out / "phase3_gp_distribution_revision_summary.csv",
        index=False,
    )

    relationships = revision_loss_relationships(
        deterministic_panel, probabilistic_panel
    )
    relationships.to_csv(
        out / "phase3_revision_loss_relationships.csv",
        index=False,
    )

    rule_summary = rule_path_summary(weather, loss_panel)
    rule_summary.to_csv(
        out / "phase3_rule_path_summary.csv",
        index=False,
    )

    figure_registry = make_figures(
        deterministic_panel,
        deterministic_summary_frame,
        rule_summary,
        probabilistic_summary_frame,
        gp_summary,
        figures_dir,
        int(config["figure_dpi"]),
    )
    figure_registry.to_csv(
        out / "phase3_figure_registry.csv",
        index=False,
    )

    candidate_summary = thesis_candidate_summary(
        deterministic_summary_frame,
        deterministic_bootstrap,
        probabilistic_summary_frame,
        probabilistic_bootstrap,
        gp_summary,
    )
    candidate_summary.to_csv(
        out / "phase3_thesis_candidate_summary.csv",
        index=False,
    )

    output_checks = [
        {
            "check": "deterministic_transition_rows",
            "passed": len(deterministic_panel)
            == config["expected"]["weather_dates"] * len(config["transitions"]),
            "critical": True,
            "detail": f"rows={len(deterministic_panel)}",
        },
        {
            "check": "deterministic_transition_identity",
            "passed": bool(
                (
                    deterministic_panel["residual_change_c"]
                    + deterministic_panel["forecast_revision_c"]
                ).abs().max()
                <= config["numerical_tolerance"]
            ),
            "critical": True,
            "detail": (
                f"max_error="
                f"{(deterministic_panel['residual_change_c'] + deterministic_panel['forecast_revision_c']).abs().max():.3e}"
            ),
        },
        {
            "check": "probabilistic_loss_rows",
            "passed": len(loss_panel)
            == config["expected"]["gp_validation_dates"]
            * len(RULE_ORDER)
            * len(MODEL_ORDER),
            "critical": True,
            "detail": f"rows={len(loss_panel)}",
        },
        {
            "check": "phase16_loss_crosscheck",
            "passed": bool(
                not phase16_check.empty
                and phase16_check["passed"].astype(bool).all()
            ),
            "critical": True,
            "detail": (
                f"max_abs_difference={phase16_check['difference'].abs().max():.3e}"
                if not phase16_check.empty else "unavailable"
            ),
        },
        {
            "check": "gp_mean_shift_reconciliation",
            "passed": bool(
                gp_revision_panel[
                    "mean_shift_reconciliation_error_c"
                ].abs().max()
                <= config["numerical_tolerance"]
            ),
            "critical": True,
            "detail": (
                f"max_error="
                f"{gp_revision_panel['mean_shift_reconciliation_error_c'].abs().max():.3e}"
            ),
        },
        {
            "check": "bootstrap_methods_present",
            "passed": set(
                deterministic_bootstrap["bootstrap_method"].unique()
            ) == {"ordinary_date", "circular_moving_block"}
            and set(
                probabilistic_bootstrap["bootstrap_method"].unique()
            ) == {"ordinary_date", "circular_moving_block"},
            "critical": True,
            "detail": "",
        },
        {
            "check": "moving_block_lengths_present",
            "passed": set(
                deterministic_bootstrap.loc[
                    deterministic_bootstrap["bootstrap_method"]
                    == "circular_moving_block",
                    "block_length_days",
                ].dropna().astype(int).unique()
            ) == set(config["bootstrap"]["moving_block_lengths"])
            and set(
                probabilistic_bootstrap.loc[
                    probabilistic_bootstrap["bootstrap_method"]
                    == "circular_moving_block",
                    "block_length_days",
                ].dropna().astype(int).unique()
            ) == set(config["bootstrap"]["moving_block_lengths"]),
            "critical": True,
            "detail": "",
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
    ]
    all_checks = pd.concat(
        [checks, pd.DataFrame(output_checks)],
        ignore_index=True,
    )
    all_checks.to_csv(
        out / "phase3_integrity_checks.csv",
        index=False,
    )

    write_report(
        out,
        provenance,
        all_checks,
        deterministic_summary_frame,
        deterministic_bootstrap,
        probabilistic_summary_frame,
        probabilistic_bootstrap,
        gp_summary,
        config,
    )
    build_manifest(out, provenance)
    make_review_bundle(out)

    final_failures = all_checks.loc[
        all_checks["critical"].astype(bool)
        & ~all_checks["passed"].astype(bool)
    ]
    print("=" * 92)
    print("PHASE 3 — INFORMATION ARRIVAL AND FORECAST REVISION")
    print("=" * 92)
    print(all_checks.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase3_review_bundle.zip'}")
    if final_failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print(final_failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
