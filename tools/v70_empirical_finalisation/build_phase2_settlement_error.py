#!/usr/bin/env python3
"""
Phase 2: settlement approximation-error analysis.

The phase is read-only with respect to the frozen Version 2 evidence. It:
- certifies the 730-date, four-rule residual panel;
- computes full residual summaries and practical exceedance probabilities;
- conducts date-clustered ordinary and circular moving-block inference;
- tests the systematic HKO-minus-forecast displacement;
- compares empirical residual tails with the fitted static Gaussian law;
- analyses temporal, seasonal and forecast-level stability;
- performs leave-one-date-out influence checks;
- generates thesis-candidate figures and machine-readable outputs.

No model is selected, fitted or changed in this phase. The static Gaussian
comparison is a descriptive full-history fit to the frozen residual panel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import traceback
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

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
PRIMARY_SCOPES = ["pooled_all_rules", *RULE_ORDER]


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
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def percentile_interval(values: np.ndarray, confidence: float) -> tuple[float, float]:
    alpha = 1.0 - confidence
    return (
        float(np.quantile(values, alpha / 2.0)),
        float(np.quantile(values, 1.0 - alpha / 2.0)),
    )


def season_from_month(month: pd.Series) -> pd.Series:
    mapping = {
        12: "DJF", 1: "DJF", 2: "DJF",
        3: "MAM", 4: "MAM", 5: "MAM",
        6: "JJA", 7: "JJA", 8: "JJA",
        9: "SON", 10: "SON", 11: "SON",
    }
    return month.map(mapping)


def moving_block_indices(
    n: int,
    block_length: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if n <= 0:
        raise ValueError("n must be positive")
    if block_length <= 0:
        raise ValueError("block_length must be positive")
    blocks_needed = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(replications, blocks_needed))
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % n
    return indices.reshape(replications, -1)[:, :n]


def ordinary_indices(
    n: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    return rng.integers(0, n, size=(replications, n), dtype=np.int64)


def scope_matrix(panel: pd.DataFrame, scope: str) -> tuple[np.ndarray, list[str]]:
    pivot = (
        panel.pivot(
            index="target_date",
            columns="decision_rule",
            values="residual_c",
        )
        .sort_index()
        .reindex(columns=RULE_ORDER)
    )
    if pivot.isna().any().any():
        raise ValueError(f"Missing residuals in scope matrix for {scope}")
    if scope == "pooled_all_rules":
        return pivot.to_numpy(dtype=float), list(pivot.index.astype(str))
    if scope not in RULE_ORDER:
        raise ValueError(f"Unknown scope: {scope}")
    return pivot[[scope]].to_numpy(dtype=float), list(pivot.index.astype(str))


def point_statistics(values: np.ndarray) -> dict[str, float]:
    flat = np.asarray(values, dtype=float).reshape(-1)
    if flat.size < 2:
        raise ValueError("At least two observations are required")
    median = float(np.median(flat))
    return {
        "mean_residual_c": float(np.mean(flat)),
        "standard_deviation_c": float(np.std(flat, ddof=1)),
        "median_residual_c": median,
        "median_absolute_deviation_c": float(np.median(np.abs(flat - median))),
        "interquartile_range_c": float(
            np.quantile(flat, 0.75) - np.quantile(flat, 0.25)
        ),
        "mean_absolute_error_c": float(np.mean(np.abs(flat))),
        "root_mean_squared_error_c": float(np.sqrt(np.mean(flat ** 2))),
        "skewness": float(stats.skew(flat, bias=False)),
        "excess_kurtosis": float(stats.kurtosis(flat, fisher=True, bias=False)),
        "minimum_c": float(np.min(flat)),
        "maximum_c": float(np.max(flat)),
        "q01_c": float(np.quantile(flat, 0.01)),
        "q05_c": float(np.quantile(flat, 0.05)),
        "q10_c": float(np.quantile(flat, 0.10)),
        "q25_c": float(np.quantile(flat, 0.25)),
        "q50_c": float(np.quantile(flat, 0.50)),
        "q75_c": float(np.quantile(flat, 0.75)),
        "q90_c": float(np.quantile(flat, 0.90)),
        "q95_c": float(np.quantile(flat, 0.95)),
        "q99_c": float(np.quantile(flat, 0.99)),
        "underforecast_rate": float(np.mean(flat > 0.0)),
        "overforecast_rate": float(np.mean(flat < 0.0)),
        "exact_zero_rate": float(np.mean(flat == 0.0)),
    }


def bootstrap_metric_arrays(
    values_by_date: np.ndarray,
    index_generator: Callable[[int], np.ndarray],
    replications: int,
    chunk_size: int,
    signed_thresholds: Sequence[float],
    absolute_thresholds: Sequence[float],
) -> dict[str, np.ndarray]:
    """
    Resample settlement dates and keep every rule attached to the sampled date.
    """
    n_dates = values_by_date.shape[0]
    outputs: dict[str, list[np.ndarray]] = {
        "mean_residual_c": [],
        "median_residual_c": [],
        "mean_absolute_error_c": [],
        "root_mean_squared_error_c": [],
        "underforecast_rate": [],
    }
    for threshold in signed_thresholds:
        if threshold > 0:
            outputs[f"prob_residual_above_{threshold:g}c"] = []
    for threshold in absolute_thresholds:
        outputs[f"prob_absolute_residual_above_{threshold:g}c"] = []

    completed = 0
    while completed < replications:
        current = min(chunk_size, replications - completed)
        indices = index_generator(current)
        if indices.shape != (current, n_dates):
            raise ValueError(
                f"Index generator returned {indices.shape}, expected "
                f"{(current, n_dates)}"
            )
        sampled = values_by_date[indices, :]
        flat = sampled.reshape(current, -1)

        outputs["mean_residual_c"].append(np.mean(flat, axis=1))
        outputs["median_residual_c"].append(np.median(flat, axis=1))
        outputs["mean_absolute_error_c"].append(np.mean(np.abs(flat), axis=1))
        outputs["root_mean_squared_error_c"].append(
            np.sqrt(np.mean(flat ** 2, axis=1))
        )
        outputs["underforecast_rate"].append(np.mean(flat > 0.0, axis=1))

        for threshold in signed_thresholds:
            if threshold > 0:
                outputs[f"prob_residual_above_{threshold:g}c"].append(
                    np.mean(flat > threshold, axis=1)
                )
        for threshold in absolute_thresholds:
            outputs[f"prob_absolute_residual_above_{threshold:g}c"].append(
                np.mean(np.abs(flat) > threshold, axis=1)
            )
        completed += current

    return {
        key: np.concatenate(parts)
        for key, parts in outputs.items()
    }


def centred_mean_null_distribution(
    values_by_date: np.ndarray,
    index_generator: Callable[[int], np.ndarray],
    replications: int,
    chunk_size: int,
) -> np.ndarray:
    centred = values_by_date - np.mean(values_by_date)
    n_dates = values_by_date.shape[0]
    parts: list[np.ndarray] = []
    completed = 0
    while completed < replications:
        current = min(chunk_size, replications - completed)
        indices = index_generator(current)
        if indices.shape != (current, n_dates):
            raise ValueError("Invalid bootstrap index shape")
        sampled = centred[indices, :].reshape(current, -1)
        parts.append(np.mean(sampled, axis=1))
        completed += current
    return np.concatenate(parts)


def bootstrap_phase(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reps = int(config["bootstrap"]["replications"])
    seed = int(config["bootstrap"]["seed"])
    confidence = float(config["bootstrap"]["confidence_level"])
    chunk_size = int(config["bootstrap"]["chunk_size"])
    blocks = list(map(int, config["bootstrap"]["moving_block_lengths"]))
    signed_thresholds = list(map(float, config["residual_thresholds_c"]))
    absolute_thresholds = list(map(float, config["absolute_thresholds_c"]))

    interval_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []

    for scope_index, scope in enumerate(PRIMARY_SCOPES):
        matrix, dates = scope_matrix(panel, scope)
        flat = matrix.reshape(-1)
        points = point_statistics(flat)
        metric_points = {
            "mean_residual_c": points["mean_residual_c"],
            "median_residual_c": points["median_residual_c"],
            "mean_absolute_error_c": points["mean_absolute_error_c"],
            "root_mean_squared_error_c": points["root_mean_squared_error_c"],
            "underforecast_rate": points["underforecast_rate"],
        }
        for threshold in signed_thresholds:
            if threshold > 0:
                metric_points[f"prob_residual_above_{threshold:g}c"] = float(
                    np.mean(flat > threshold)
                )
        for threshold in absolute_thresholds:
            metric_points[
                f"prob_absolute_residual_above_{threshold:g}c"
            ] = float(np.mean(np.abs(flat) > threshold))

        methods: list[tuple[str, int | None]] = [("ordinary_date", None)]
        methods.extend(("circular_moving_block", block) for block in blocks)

        for method_index, (method, block_length) in enumerate(methods):
            local_seed = seed + scope_index * 1000 + method_index * 100
            rng = np.random.default_rng(local_seed)
            n_dates = matrix.shape[0]

            if method == "ordinary_date":
                def generator(current: int, *, _rng=rng, _n=n_dates) -> np.ndarray:
                    return ordinary_indices(_n, current, _rng)
            else:
                assert block_length is not None
                def generator(
                    current: int,
                    *,
                    _rng=rng,
                    _n=n_dates,
                    _b=block_length,
                ) -> np.ndarray:
                    return moving_block_indices(_n, _b, current, _rng)

            boot = bootstrap_metric_arrays(
                matrix,
                generator,
                reps,
                chunk_size,
                signed_thresholds,
                absolute_thresholds,
            )
            for metric, distribution in boot.items():
                lower, upper = percentile_interval(distribution, confidence)
                interval_rows.append(
                    {
                        "scope": scope,
                        "dates": len(dates),
                        "rows": int(matrix.size),
                        "metric": metric,
                        "point_estimate": metric_points[metric],
                        "bootstrap_method": method,
                        "block_length_days": block_length,
                        "bootstrap_lower_95": lower,
                        "bootstrap_upper_95": upper,
                        "bootstrap_replications": reps,
                        "seed": local_seed,
                        "bootstrap_unit": "settlement_date",
                    }
                )

            # Re-create an independent generator with the same recorded seed for
            # the centred null distribution.
            null_rng = np.random.default_rng(local_seed + 50_000)
            if method == "ordinary_date":
                def null_generator(
                    current: int,
                    *,
                    _rng=null_rng,
                    _n=n_dates,
                ) -> np.ndarray:
                    return ordinary_indices(_n, current, _rng)
            else:
                assert block_length is not None
                def null_generator(
                    current: int,
                    *,
                    _rng=null_rng,
                    _n=n_dates,
                    _b=block_length,
                ) -> np.ndarray:
                    return moving_block_indices(_n, _b, current, _rng)

            null_means = centred_mean_null_distribution(
                matrix,
                null_generator,
                reps,
                chunk_size,
            )
            observed = float(np.mean(matrix))
            p_value = float(
                (1 + np.sum(np.abs(null_means) >= abs(observed)))
                / (reps + 1)
            )
            mean_interval = next(
                row for row in interval_rows
                if row["scope"] == scope
                and row["metric"] == "mean_residual_c"
                and row["bootstrap_method"] == method
                and row["block_length_days"] == block_length
            )
            test_rows.append(
                {
                    "scope": scope,
                    "dates": len(dates),
                    "rows": int(matrix.size),
                    "null_hypothesis": "mean_residual_equals_zero",
                    "observed_mean_residual_c": observed,
                    "bootstrap_method": method,
                    "block_length_days": block_length,
                    "bootstrap_lower_95_c": mean_interval["bootstrap_lower_95"],
                    "bootstrap_upper_95_c": mean_interval["bootstrap_upper_95"],
                    "two_sided_centred_bootstrap_p_value": p_value,
                    "minimum_resolvable_p_value": 1.0 / (reps + 1),
                    "bootstrap_replications": reps,
                    "seed": local_seed + 50_000,
                    "bootstrap_unit": "settlement_date",
                }
            )

    return pd.DataFrame(interval_rows), pd.DataFrame(test_rows)


def build_summary_tables(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    exceedance_rows: list[dict[str, Any]] = []

    for scope in PRIMARY_SCOPES:
        matrix, dates = scope_matrix(panel, scope)
        flat = matrix.reshape(-1)
        row = {
            "scope": scope,
            "dates": len(dates),
            "rows": len(flat),
            "decision_rules": matrix.shape[1],
            **point_statistics(flat),
        }
        summary_rows.append(row)

        for threshold in map(float, config["residual_thresholds_c"]):
            exceedance_rows.append(
                {
                    "scope": scope,
                    "dates": len(dates),
                    "rows": len(flat),
                    "event": "residual_above_threshold",
                    "threshold_c": threshold,
                    "empirical_probability": float(np.mean(flat > threshold)),
                }
            )
        for threshold in map(float, config["absolute_thresholds_c"]):
            exceedance_rows.append(
                {
                    "scope": scope,
                    "dates": len(dates),
                    "rows": len(flat),
                    "event": "absolute_residual_above_threshold",
                    "threshold_c": threshold,
                    "empirical_probability": float(
                        np.mean(np.abs(flat) > threshold)
                    ),
                }
            )

    return pd.DataFrame(summary_rows), pd.DataFrame(exceedance_rows)


def gaussian_comparison_tables(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    quantile_rows: list[dict[str, Any]] = []
    exceedance_rows: list[dict[str, Any]] = []
    diagnostics_rows: list[dict[str, Any]] = []

    for scope in PRIMARY_SCOPES:
        matrix, dates = scope_matrix(panel, scope)
        flat = matrix.reshape(-1)
        mu = float(np.mean(flat))
        sd = float(np.std(flat, ddof=1))
        z = (flat - mu) / sd

        for probability in map(float, config["quantile_probabilities"]):
            empirical = float(np.quantile(flat, probability))
            gaussian = float(mu + sd * stats.norm.ppf(probability))
            quantile_rows.append(
                {
                    "scope": scope,
                    "dates": len(dates),
                    "rows": len(flat),
                    "probability": probability,
                    "empirical_quantile_c": empirical,
                    "fitted_gaussian_quantile_c": gaussian,
                    "empirical_minus_gaussian_c": empirical - gaussian,
                    "fitted_gaussian_mean_c": mu,
                    "fitted_gaussian_sd_c": sd,
                }
            )

        for threshold in map(float, config["residual_thresholds_c"]):
            empirical = float(np.mean(flat > threshold))
            gaussian = float(1.0 - stats.norm.cdf((threshold - mu) / sd))
            exceedance_rows.append(
                {
                    "scope": scope,
                    "event": "residual_above_threshold",
                    "threshold_c": threshold,
                    "empirical_probability": empirical,
                    "fitted_gaussian_probability": gaussian,
                    "empirical_minus_gaussian": empirical - gaussian,
                    "empirical_to_gaussian_ratio": (
                        empirical / gaussian if gaussian > 0 else np.nan
                    ),
                }
            )
        for threshold in map(float, config["absolute_thresholds_c"]):
            empirical = float(np.mean(np.abs(flat) > threshold))
            gaussian = float(
                stats.norm.cdf((-threshold - mu) / sd)
                + 1.0
                - stats.norm.cdf((threshold - mu) / sd)
            )
            exceedance_rows.append(
                {
                    "scope": scope,
                    "event": "absolute_residual_above_threshold",
                    "threshold_c": threshold,
                    "empirical_probability": empirical,
                    "fitted_gaussian_probability": gaussian,
                    "empirical_minus_gaussian": empirical - gaussian,
                    "empirical_to_gaussian_ratio": (
                        empirical / gaussian if gaussian > 0 else np.nan
                    ),
                }
            )

        jb = stats.jarque_bera(flat)
        dagostino = stats.normaltest(flat)
        ks = stats.kstest(z, "norm")
        cvm = stats.cramervonmises(z, "norm")
        ad = stats.anderson(z, dist="norm")
        ad_5_index = int(np.argmin(np.abs(np.asarray(ad.significance_level) - 5.0)))

        diagnostics_rows.append(
            {
                "scope": scope,
                "dates": len(dates),
                "rows": len(flat),
                "fitted_mean_c": mu,
                "fitted_sd_c": sd,
                "jarque_bera_statistic": float(jb.statistic),
                "jarque_bera_nominal_p_value": float(jb.pvalue),
                "dagostino_k2_statistic": float(dagostino.statistic),
                "dagostino_nominal_p_value": float(dagostino.pvalue),
                "kolmogorov_smirnov_statistic_fitted_parameters": float(
                    ks.statistic
                ),
                "kolmogorov_smirnov_nominal_p_value": float(ks.pvalue),
                "cramer_von_mises_statistic_fitted_parameters": float(
                    cvm.statistic
                ),
                "cramer_von_mises_nominal_p_value": float(cvm.pvalue),
                "anderson_darling_statistic": float(ad.statistic),
                "anderson_darling_5pct_critical_value": float(
                    ad.critical_values[ad_5_index]
                ),
                "p_value_caveat": (
                    "Nominal descriptive diagnostics only: Gaussian parameters "
                    "are estimated from the same data and date-rule rows are "
                    "dependent within settlement date."
                ),
            }
        )

    return (
        pd.DataFrame(quantile_rows),
        pd.DataFrame(exceedance_rows),
        pd.DataFrame(diagnostics_rows),
    )


def grouped_summary(
    frame: pd.DataFrame,
    group_columns: Sequence[str],
    analysis_name: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(list(group_columns), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        residual = group["residual_c"].to_numpy(dtype=float)
        stats_row = point_statistics(residual)
        row = {
            "analysis": analysis_name,
            **dict(zip(group_columns, keys)),
            "rows": len(group),
            "dates": int(group["target_date"].nunique()),
            **stats_row,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def stability_tables(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> dict[str, pd.DataFrame]:
    frame = panel.copy()
    frame["target_date"] = pd.to_datetime(frame["target_date"])
    frame["target_year"] = frame["target_date"].dt.year
    frame["target_month"] = frame["target_date"].dt.month
    frame["calendar_quarter"] = frame["target_date"].dt.quarter
    frame["year_quarter"] = frame["target_date"].dt.to_period("Q").astype(str)
    frame["meteorological_season"] = season_from_month(frame["target_month"])

    date_order = pd.DataFrame(
        {"target_date": sorted(frame["target_date"].drop_duplicates())}
    )
    n_dates = len(date_order)
    n_blocks = int(config["chronological_blocks"])
    date_order["full_sample_chronological_block"] = (
        np.floor(np.arange(n_dates) * n_blocks / n_dates).astype(int) + 1
    )
    frame = frame.merge(date_order, on="target_date", how="left", validate="many_to_one")

    frame["forecast_level_quartile"] = (
        frame.groupby("decision_rule")["forecast_daily_max_c"]
        .transform(
            lambda s: pd.qcut(
                s.rank(method="first"),
                q=4,
                labels=["Q1", "Q2", "Q3", "Q4"],
            ).astype(str)
        )
    )

    # Include pooled descriptive rows by duplicating with an explicit scope.
    pooled = frame.copy()
    pooled["decision_rule"] = "ALL_DATE_RULES"
    expanded = pd.concat([frame, pooled], ignore_index=True)

    return {
        "year": grouped_summary(
            expanded,
            ["decision_rule", "target_year"],
            "residual_stability_by_year",
        ),
        "quarter": grouped_summary(
            expanded,
            ["decision_rule", "calendar_quarter"],
            "residual_stability_by_calendar_quarter",
        ),
        "season": grouped_summary(
            expanded,
            ["decision_rule", "meteorological_season"],
            "residual_stability_by_season",
        ),
        "year_quarter": grouped_summary(
            expanded,
            ["decision_rule", "year_quarter"],
            "residual_stability_by_year_quarter",
        ),
        "chronological_block": grouped_summary(
            expanded,
            ["decision_rule", "full_sample_chronological_block"],
            "residual_stability_by_full_sample_chronological_block",
        ),
        "forecast_quartile": grouped_summary(
            frame,
            ["decision_rule", "forecast_level_quartile"],
            "residual_stability_by_forecast_level_quartile",
        ),
    }


def leave_one_date_out(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(panel["target_date"].astype(str).unique())
    rows: list[dict[str, Any]] = []

    scopes: dict[str, pd.DataFrame] = {
        "pooled_all_rules": panel,
        **{
            rule: panel.loc[panel["decision_rule"] == rule].copy()
            for rule in RULE_ORDER
        },
    }

    for scope, frame in scopes.items():
        full = frame["residual_c"].to_numpy(dtype=float)
        full_mean = float(np.mean(full))
        full_mae = float(np.mean(np.abs(full)))
        full_under = float(np.mean(full > 0.0))
        for omitted in dates:
            reduced = frame.loc[
                frame["target_date"].astype(str) != omitted,
                "residual_c",
            ].to_numpy(dtype=float)
            rows.append(
                {
                    "scope": scope,
                    "omitted_date": omitted,
                    "remaining_rows": len(reduced),
                    "remaining_dates": len(dates) - 1,
                    "mean_residual_c": float(np.mean(reduced)),
                    "mean_change_from_full_c": float(np.mean(reduced) - full_mean),
                    "mean_absolute_error_c": float(np.mean(np.abs(reduced))),
                    "mae_change_from_full_c": float(
                        np.mean(np.abs(reduced)) - full_mae
                    ),
                    "underforecast_rate": float(np.mean(reduced > 0.0)),
                    "underforecast_rate_change_from_full": float(
                        np.mean(reduced > 0.0) - full_under
                    ),
                }
            )

    detail = pd.DataFrame(rows)
    summary_rows: list[dict[str, Any]] = []
    for scope, group in detail.groupby("scope"):
        max_mean_idx = group["mean_change_from_full_c"].abs().idxmax()
        max_mae_idx = group["mae_change_from_full_c"].abs().idxmax()
        max_under_idx = group[
            "underforecast_rate_change_from_full"
        ].abs().idxmax()
        summary_rows.append(
            {
                "scope": scope,
                "maximum_absolute_mean_change_c": float(
                    group["mean_change_from_full_c"].abs().max()
                ),
                "most_influential_mean_date": detail.loc[
                    max_mean_idx, "omitted_date"
                ],
                "maximum_absolute_mae_change_c": float(
                    group["mae_change_from_full_c"].abs().max()
                ),
                "most_influential_mae_date": detail.loc[
                    max_mae_idx, "omitted_date"
                ],
                "maximum_absolute_underforecast_rate_change": float(
                    group["underforecast_rate_change_from_full"].abs().max()
                ),
                "most_influential_underforecast_date": detail.loc[
                    max_under_idx, "omitted_date"
                ],
            }
        )
    return detail, pd.DataFrame(summary_rows)


def validate_input(
    panel: pd.DataFrame,
    config: Mapping[str, Any],
    phase1_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    expected = config["expected"]
    checks: list[dict[str, Any]] = []

    def add(check: str, passed: bool, detail: str, critical: bool = True) -> None:
        checks.append(
            {
                "check": check,
                "passed": bool(passed),
                "critical": bool(critical),
                "detail": detail,
            }
        )

    required_columns = {
        "target_date",
        "decision_rule",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "residual_c",
        "forecast_error_c",
        "absolute_error_c",
        "squared_error_c",
        "support_available",
        "complete_local_day",
        "issued_before_decision",
        "market_price_accessed",
        "outcome_accessed",
        "model_fitted",
        "model_selected",
        "calibration_selected",
        "trading_returns_calculated",
    }
    missing = sorted(required_columns - set(panel.columns))
    add("required_columns", not missing, f"missing={missing}")
    if missing:
        return pd.DataFrame(checks), pd.DataFrame()

    panel = panel.copy()
    panel["target_date"] = pd.to_datetime(
        panel["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    duplicate_count = int(
        panel.duplicated(["target_date", "decision_rule"]).sum()
    )
    rule_counts = panel["decision_rule"].value_counts().to_dict()

    add("expected_rows", len(panel) == expected["rows"], f"rows={len(panel)}")
    add(
        "expected_dates",
        panel["target_date"].nunique() == expected["dates"],
        f"dates={panel['target_date'].nunique()}",
    )
    add(
        "expected_rules",
        set(panel["decision_rule"].unique()) == set(expected["rules"]),
        f"rules={sorted(panel['decision_rule'].unique())}",
    )
    add(
        "rows_per_rule",
        all(rule_counts.get(rule, 0) == expected["rows_per_rule"]
            for rule in expected["rules"]),
        f"counts={rule_counts}",
    )
    add(
        "unique_date_rule_keys",
        duplicate_count == 0,
        f"duplicate_keys={duplicate_count}",
    )

    residual_identity = (
        pd.to_numeric(panel["hko_daily_max_c"], errors="coerce")
        - pd.to_numeric(panel["forecast_daily_max_c"], errors="coerce")
        - pd.to_numeric(panel["residual_c"], errors="coerce")
    ).abs()
    add(
        "residual_identity",
        float(residual_identity.max()) <= 1e-10,
        f"max_absolute_error={float(residual_identity.max()):.3e}",
    )

    forecast_error_identity = (
        pd.to_numeric(panel["forecast_daily_max_c"], errors="coerce")
        - pd.to_numeric(panel["hko_daily_max_c"], errors="coerce")
        - pd.to_numeric(panel["forecast_error_c"], errors="coerce")
    ).abs()
    add(
        "forecast_error_identity",
        float(forecast_error_identity.max()) <= 1e-10,
        f"max_absolute_error={float(forecast_error_identity.max()):.3e}",
    )

    abs_identity = (
        pd.to_numeric(panel["residual_c"], errors="coerce").abs()
        - pd.to_numeric(panel["absolute_error_c"], errors="coerce")
    ).abs()
    square_identity = (
        pd.to_numeric(panel["residual_c"], errors="coerce") ** 2
        - pd.to_numeric(panel["squared_error_c"], errors="coerce")
    ).abs()
    add(
        "absolute_error_identity",
        float(abs_identity.max()) <= 1e-10,
        f"max_absolute_error={float(abs_identity.max()):.3e}",
    )
    add(
        "squared_error_identity",
        float(square_identity.max()) <= 1e-10,
        f"max_absolute_error={float(square_identity.max()):.3e}",
    )

    for column in [
        "support_available",
        "complete_local_day",
        "issued_before_decision",
    ]:
        values = panel[column].fillna(False).astype(bool)
        add(
            f"all_{column}",
            bool(values.all()),
            f"false_rows={int((~values).sum())}",
        )

    for column in [
        "market_price_accessed",
        "outcome_accessed",
        "model_fitted",
        "model_selected",
        "calibration_selected",
        "trading_returns_calculated",
    ]:
        values = panel[column].fillna(False).astype(bool)
        add(
            f"no_{column}",
            bool((~values).all()),
            f"true_rows={int(values.sum())}",
        )

    phase1_completion_path = phase1_root / "phase1_completion_status.csv"
    if phase1_completion_path.is_file():
        completion = pd.read_csv(phase1_completion_path)
        critical_failed = completion.loc[
            completion["critical"].astype(bool)
            & ~completion["passed"].astype(bool)
        ]
        add(
            "phase1_critical_checks_passed",
            critical_failed.empty,
            f"critical_failures={len(critical_failed)}",
        )
    else:
        add(
            "phase1_completion_available",
            False,
            f"missing={phase1_completion_path}",
        )

    static_path = phase1_root / "phase1_reconstructed_raw_static_event_books.csv.gz"
    static_crosscheck_rows: list[dict[str, Any]] = []
    if static_path.is_file():
        books = pd.read_csv(static_path)
        static = books.loc[books["model"] == "static"].copy()
        static["implied_bias_c"] = (
            static["predictive_mean_c"] - static["deterministic_forecast_c"]
        )
        residual_stats = (
            panel.groupby("decision_rule")["residual_c"]
            .agg(["mean", "std"])
            .reset_index()
        )
        for row in residual_stats.to_dict("records"):
            rule = row["decision_rule"]
            sub = static.loc[static["decision_rule"] == rule]
            bias_values = sub["implied_bias_c"].dropna().unique()
            sd_values = sub["predictive_sd_c"].dropna().unique()
            if len(bias_values) != 1 or len(sd_values) != 1:
                static_crosscheck_rows.append(
                    {
                        "decision_rule": rule,
                        "passed": False,
                        "detail": (
                            f"unique_biases={len(bias_values)}, "
                            f"unique_sds={len(sd_values)}"
                        ),
                    }
                )
                continue
            mean_difference = float(bias_values[0] - row["mean"])
            sd_difference = float(sd_values[0] - row["std"])
            static_crosscheck_rows.append(
                {
                    "decision_rule": rule,
                    "phase1_static_bias_c": float(bias_values[0]),
                    "phase2_residual_mean_c": float(row["mean"]),
                    "bias_difference_c": mean_difference,
                    "phase1_static_sd_c": float(sd_values[0]),
                    "phase2_residual_sd_c": float(row["std"]),
                    "sd_difference_c": sd_difference,
                    "passed": (
                        abs(mean_difference) <= 1e-10
                        and abs(sd_difference) <= 1e-10
                    ),
                    "detail": "",
                }
            )
        crosscheck = pd.DataFrame(static_crosscheck_rows)
        add(
            "phase1_static_parameter_crosscheck",
            bool(crosscheck["passed"].all()),
            (
                f"max_abs_bias_difference="
                f"{crosscheck['bias_difference_c'].abs().max():.3e}; "
                f"max_abs_sd_difference="
                f"{crosscheck['sd_difference_c'].abs().max():.3e}"
            ),
        )
    else:
        crosscheck = pd.DataFrame()
        add(
            "phase1_static_books_available",
            False,
            f"missing={static_path}",
        )

    return pd.DataFrame(checks), crosscheck


def phase17_crosscheck(
    summary: pd.DataFrame,
    frozen_root: Path,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = frozen_root / config["input_paths"]["phase17_rule_summary"]
    block_path = (
        frozen_root
        / config["input_paths"]["phase17_validation_block_summary"]
    )
    rows: list[dict[str, Any]] = []

    if path.is_file():
        old = pd.read_csv(path)
        current = summary.loc[
            summary["scope"].isin(RULE_ORDER)
        ].copy()
        merged = current.merge(
            old,
            left_on="scope",
            right_on="decision_rule",
            how="left",
            validate="one_to_one",
            suffixes=("_phase2", "_phase17"),
        )
        mappings = [
            ("mean_residual_c", "mean_error_hko_minus_forecast_c"),
            ("standard_deviation_c", "error_standard_deviation_c"),
            ("median_residual_c", "median_error_c"),
            ("mean_absolute_error_c", "mae_c"),
            ("q05_c", "q05_error_c"),
            ("q25_c", "q25_error_c"),
            ("q75_c", "q75_error_c"),
            ("q95_c", "q95_error_c"),
            ("underforecast_rate", "underforecast_rate"),
            ("skewness", "skewness"),
            ("excess_kurtosis", "excess_kurtosis"),
        ]
        for phase2_col, phase17_col in mappings:
            if phase17_col not in merged.columns:
                continue
            for row in merged.to_dict("records"):
                rows.append(
                    {
                        "decision_rule": row["scope"],
                        "metric": phase2_col,
                        "phase2_value": row[phase2_col],
                        "phase17_value": row[phase17_col],
                        "phase2_minus_phase17": (
                            row[phase2_col] - row[phase17_col]
                        ),
                    }
                )
    crosscheck = pd.DataFrame(rows)
    if not crosscheck.empty:
        crosscheck["passed"] = (
            crosscheck["phase2_minus_phase17"].abs() <= 1e-10
        )

    validation_blocks = (
        pd.read_csv(block_path) if block_path.is_file() else pd.DataFrame()
    )
    return crosscheck, validation_blocks


def make_figures(
    panel: pd.DataFrame,
    gaussian_exceedance: pd.DataFrame,
    output_dir: Path,
    dpi: int,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata: list[dict[str, Any]] = []

    pooled = panel["residual_c"].to_numpy(dtype=float)
    mu = float(np.mean(pooled))
    sd = float(np.std(pooled, ddof=1))

    # 1. Histogram with fitted Gaussian overlay.
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.hist(pooled, bins="fd", density=True, alpha=0.55)
    x = np.linspace(np.min(pooled), np.max(pooled), 500)
    ax.plot(x, stats.norm.pdf(x, loc=mu, scale=sd), linewidth=2)
    ax.axvline(0.0, linestyle="--", linewidth=1)
    ax.set_xlabel("HKO minus deterministic forecast residual (°C)")
    ax.set_ylabel("Density")
    ax.set_title("Deterministic settlement residual distribution")
    fig.tight_layout()
    path = output_dir / "phase2_figure_residual_histogram_gaussian.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Main-text candidate: pooled residual distribution and fitted Gaussian",
        "observational_unit": "date-rule residual; four rules retained together in inference",
    })

    # 2. Q-Q plot.
    ordered = np.sort(pooled)
    probabilities = (np.arange(1, len(ordered) + 1) - 0.5) / len(ordered)
    theoretical = stats.norm.ppf(probabilities, loc=mu, scale=sd)
    lower = min(float(theoretical.min()), float(ordered.min()))
    upper = max(float(theoretical.max()), float(ordered.max()))
    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    ax.scatter(theoretical, ordered, s=10, alpha=0.55)
    ax.plot([lower, upper], [lower, upper], linestyle="--", linewidth=1)
    ax.set_xlabel("Fitted Gaussian quantiles (°C)")
    ax.set_ylabel("Empirical residual quantiles (°C)")
    ax.set_title("Residual Q–Q diagnostic")
    fig.tight_layout()
    path = output_dir / "phase2_figure_residual_qq.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: Gaussian tail adequacy",
        "observational_unit": "date-rule residual",
    })

    # 3. Rule boxplot.
    data = [
        panel.loc[panel["decision_rule"] == rule, "residual_c"].to_numpy()
        for rule in RULE_ORDER
    ]
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.boxplot(data, labels=[RULE_LABELS[r] for r in RULE_ORDER], showfliers=True)
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_ylabel("HKO minus forecast residual (°C)")
    ax.set_title("Settlement residual by decision rule")
    fig.tight_layout()
    path = output_dir / "phase2_figure_residual_boxplot_by_rule.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Main/appendix candidate: rule-level residual spread",
        "observational_unit": "settlement date within rule",
    })

    # 4. Empirical CDF against fitted Gaussian.
    ecdf_x = np.sort(pooled)
    ecdf_y = np.arange(1, len(ecdf_x) + 1) / len(ecdf_x)
    gaussian_y = stats.norm.cdf(ecdf_x, loc=mu, scale=sd)
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(ecdf_x, ecdf_y, linewidth=2, label="Empirical CDF")
    ax.plot(ecdf_x, gaussian_y, linewidth=2, linestyle="--",
            label="Fitted Gaussian CDF")
    ax.set_xlabel("Residual (°C)")
    ax.set_ylabel("Cumulative probability")
    ax.set_title("Empirical and fitted Gaussian residual CDFs")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase2_figure_residual_ecdf_gaussian.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: whole-distribution Gaussian adequacy",
        "observational_unit": "date-rule residual",
    })

    # 5. Residual over time.
    time_panel = panel.copy()
    time_panel["target_date"] = pd.to_datetime(time_panel["target_date"])
    fig, ax = plt.subplots(figsize=(10.0, 5.2))
    for rule in RULE_ORDER:
        sub = time_panel.loc[time_panel["decision_rule"] == rule].sort_values(
            "target_date"
        )
        ax.plot(
            sub["target_date"],
            sub["residual_c"],
            linewidth=0.8,
            alpha=0.7,
            label=RULE_LABELS[rule],
        )
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Settlement date")
    ax.set_ylabel("Residual (°C)")
    ax.set_title("Settlement residual through time")
    ax.legend(ncol=2)
    fig.tight_layout()
    path = output_dir / "phase2_figure_residual_over_time.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: temporal stability",
        "observational_unit": "settlement date within rule",
    })

    # 6. Residual against deterministic forecast level.
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    for rule in RULE_ORDER:
        sub = panel.loc[panel["decision_rule"] == rule]
        ax.scatter(
            sub["forecast_daily_max_c"],
            sub["residual_c"],
            s=10,
            alpha=0.35,
            label=RULE_LABELS[rule],
        )
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Deterministic forecast maximum (°C)")
    ax.set_ylabel("Residual (°C)")
    ax.set_title("Settlement residual against forecast level")
    ax.legend(ncol=2)
    fig.tight_layout()
    path = output_dir / "phase2_figure_residual_vs_forecast_level.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: forecast-level dependence",
        "observational_unit": "date-rule residual",
    })

    # 7. Empirical-minus-Gaussian tail mismatch for pooled scope.
    tail = gaussian_exceedance.loc[
        gaussian_exceedance["scope"] == "pooled_all_rules"
    ].copy()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    for event, sub in tail.groupby("event"):
        ax.plot(
            sub["threshold_c"],
            sub["empirical_minus_gaussian"],
            marker="o",
            label=event.replace("_", " "),
        )
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Threshold (°C)")
    ax.set_ylabel("Empirical minus fitted-Gaussian probability")
    ax.set_title("Residual-tail mismatch")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase2_figure_gaussian_tail_mismatch.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append({
        "figure": path.name,
        "purpose": "Appendix candidate: practical Gaussian tail mismatch",
        "observational_unit": "pooled date-rule residual",
    })

    return pd.DataFrame(metadata)


def build_candidate_summary(
    summary: pd.DataFrame,
    bootstrap: pd.DataFrame,
    gaussian_exceedance: pd.DataFrame,
    influence: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pooled = summary.loc[summary["scope"] == "pooled_all_rules"].iloc[0]
    ordinary = bootstrap.loc[
        (bootstrap["scope"] == "pooled_all_rules")
        & (bootstrap["bootstrap_method"] == "ordinary_date")
    ]
    mean_ci = ordinary.loc[
        ordinary["metric"] == "mean_residual_c"
    ].iloc[0]
    under_ci = ordinary.loc[
        ordinary["metric"] == "underforecast_rate"
    ].iloc[0]
    rows.extend([
        {
            "candidate_id": "P2_MEAN",
            "quantity": "pooled mean HKO-minus-forecast residual",
            "point_estimate": pooled["mean_residual_c"],
            "lower_95": mean_ci["bootstrap_lower_95"],
            "upper_95": mean_ci["bootstrap_upper_95"],
            "unit": "degrees Celsius",
            "preferred_location": "Results Section 6.2",
        },
        {
            "candidate_id": "P2_SD",
            "quantity": "pooled residual standard deviation",
            "point_estimate": pooled["standard_deviation_c"],
            "lower_95": np.nan,
            "upper_95": np.nan,
            "unit": "degrees Celsius",
            "preferred_location": "Results Section 6.2",
        },
        {
            "candidate_id": "P2_MEDIAN",
            "quantity": "pooled residual median",
            "point_estimate": pooled["median_residual_c"],
            "lower_95": ordinary.loc[
                ordinary["metric"] == "median_residual_c",
                "bootstrap_lower_95",
            ].iloc[0],
            "upper_95": ordinary.loc[
                ordinary["metric"] == "median_residual_c",
                "bootstrap_upper_95",
            ].iloc[0],
            "unit": "degrees Celsius",
            "preferred_location": "Results Section 6.2",
        },
        {
            "candidate_id": "P2_UNDER",
            "quantity": "proportion of date-rule forecasts below HKO",
            "point_estimate": pooled["underforecast_rate"],
            "lower_95": under_ci["bootstrap_lower_95"],
            "upper_95": under_ci["bootstrap_upper_95"],
            "unit": "proportion",
            "preferred_location": "Results Section 6.2",
        },
    ])

    tail = gaussian_exceedance.loc[
        gaussian_exceedance["scope"] == "pooled_all_rules"
    ].copy()
    tail["absolute_mismatch"] = tail["empirical_minus_gaussian"].abs()
    largest = tail.sort_values("absolute_mismatch", ascending=False).iloc[0]
    rows.append(
        {
            "candidate_id": "P2_GAUSSIAN_TAIL",
            "quantity": (
                f"largest empirical-minus-Gaussian tail difference: "
                f"{largest['event']} at {largest['threshold_c']}°C"
            ),
            "point_estimate": largest["empirical_minus_gaussian"],
            "lower_95": np.nan,
            "upper_95": np.nan,
            "unit": "probability difference",
            "preferred_location": "Appendix/Discussion if material",
        }
    )

    pooled_influence = influence.loc[
        influence["scope"] == "pooled_all_rules"
    ].iloc[0]
    rows.append(
        {
            "candidate_id": "P2_INFLUENCE",
            "quantity": "maximum leave-one-date-out change in pooled mean",
            "point_estimate": pooled_influence[
                "maximum_absolute_mean_change_c"
            ],
            "lower_95": np.nan,
            "upper_95": np.nan,
            "unit": "degrees Celsius",
            "preferred_location": "Robustness appendix",
        }
    )
    return pd.DataFrame(rows)


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    summary: pd.DataFrame,
    bootstrap: pd.DataFrame,
    tests: pd.DataFrame,
    gaussian_exceedance: pd.DataFrame,
    influence_summary: pd.DataFrame,
) -> None:
    critical_failures = checks.loc[
        checks["critical"].astype(bool)
        & ~checks["passed"].astype(bool)
    ]
    status = "PASSED" if critical_failures.empty else "FAILED"

    pooled = summary.loc[summary["scope"] == "pooled_all_rules"].iloc[0]
    ordinary = bootstrap.loc[
        (bootstrap["scope"] == "pooled_all_rules")
        & (bootstrap["bootstrap_method"] == "ordinary_date")
    ]
    mean_ci = ordinary.loc[
        ordinary["metric"] == "mean_residual_c"
    ].iloc[0]
    under_ci = ordinary.loc[
        ordinary["metric"] == "underforecast_rate"
    ].iloc[0]
    mean_test = tests.loc[
        (tests["scope"] == "pooled_all_rules")
        & (tests["bootstrap_method"] == "ordinary_date")
    ].iloc[0]
    tail = gaussian_exceedance.loc[
        gaussian_exceedance["scope"] == "pooled_all_rules"
    ].copy()
    tail["abs_difference"] = tail["empirical_minus_gaussian"].abs()
    max_tail = tail.sort_values("abs_difference", ascending=False).iloc[0]
    influence = influence_summary.loc[
        influence_summary["scope"] == "pooled_all_rules"
    ].iloc[0]

    lines = [
        "# Phase 2 — Settlement Approximation-Error Analysis",
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
        "## Headline descriptive evidence",
        "",
        (
            f"The pooled HKO-minus-deterministic residual is "
            f"**{pooled['mean_residual_c']:.6f}°C**, with residual standard "
            f"deviation **{pooled['standard_deviation_c']:.6f}°C**, median "
            f"**{pooled['median_residual_c']:.6f}°C**, and mean absolute error "
            f"**{pooled['mean_absolute_error_c']:.6f}°C**."
        ),
        "",
        (
            f"The ordinary settlement-date bootstrap 95% interval for the "
            f"pooled mean is "
            f"[{mean_ci['bootstrap_lower_95']:.6f}, "
            f"{mean_ci['bootstrap_upper_95']:.6f}]°C. "
            f"The centred two-sided bootstrap p-value for a zero mean is "
            f"{mean_test['two_sided_centred_bootstrap_p_value']:.6g}."
        ),
        "",
        (
            f"The deterministic forecast is below the HKO settlement value on "
            f"**{100 * pooled['underforecast_rate']:.2f}%** of date-rule rows; "
            f"the ordinary date-bootstrap interval is "
            f"[{100 * under_ci['bootstrap_lower_95']:.2f}%, "
            f"{100 * under_ci['bootstrap_upper_95']:.2f}%]."
        ),
        "",
        "## Gaussian adequacy",
        "",
        (
            f"The largest pooled practical tail-probability discrepancy between "
            f"the empirical residual distribution and its fitted Gaussian is "
            f"{max_tail['empirical_minus_gaussian']:.6f} for "
            f"`{max_tail['event']}` at "
            f"{max_tail['threshold_c']:.2f}°C."
        ),
        "",
        (
            "Normality-test p-values are descriptive only because location and "
            "scale are estimated from the same residual sample and four rule "
            "observations share each settlement date."
        ),
        "",
        "## Influence",
        "",
        (
            f"The maximum leave-one-date-out change in the pooled mean is "
            f"{influence['maximum_absolute_mean_change_c']:.6f}°C, attained "
            f"when omitting {influence['most_influential_mean_date']}."
        ),
        "",
        "## Scope and interpretation",
        "",
        "- The phase measures settlement approximation error; it does not assess causal model bias.",
        "- Pooled uncertainty resamples settlement dates and preserves all four rules together.",
        "- Circular moving blocks with lengths 3, 5 and 7 assess short-range temporal sensitivity.",
        "- The static Gaussian comparison is descriptive and uses full-history residual moments.",
        "- No market information, model selection, calibration selection or trading return enters this phase.",
        "",
    ]
    (out / "phase2_report.md").write_text("\n".join(lines), encoding="utf-8")


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase2_manifest.json",
            "phase2_review_bundle.zip",
        }:
            files.append(
                {
                    "relative_path": path.relative_to(out).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "phase": "phase2_settlement_approximation_error",
        "generated_utc": utc_now(),
        "provenance": dict(provenance),
        "files": files,
    }
    (out / "phase2_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase2_review_bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                zf.write(path, path.relative_to(out).as_posix())


def self_test() -> None:
    rng = np.random.default_rng(123)
    ordinary = ordinary_indices(20, 7, rng)
    assert ordinary.shape == (7, 20)
    assert ordinary.min() >= 0 and ordinary.max() < 20

    rng = np.random.default_rng(123)
    moving = moving_block_indices(20, 3, 7, rng)
    assert moving.shape == (7, 20)
    assert moving.min() >= 0 and moving.max() < 20

    values = np.arange(80, dtype=float).reshape(20, 4) / 10.0
    rng = np.random.default_rng(321)

    def generator(current: int) -> np.ndarray:
        return ordinary_indices(20, current, rng)

    results = bootstrap_metric_arrays(
        values,
        generator,
        replications=50,
        chunk_size=13,
        signed_thresholds=[0.0, 0.5, 1.0],
        absolute_thresholds=[0.5, 1.0],
    )
    assert all(len(v) == 50 for v in results.values())
    assert np.isfinite(results["mean_residual_c"]).all()

    test_frame = pd.DataFrame(
        {
            "residual_c": np.array([-1.0, 0.0, 1.0, 2.0]),
        }
    )
    stats_result = point_statistics(test_frame[["residual_c"]].to_numpy())
    assert math.isclose(stats_result["mean_residual_c"], 0.5)
    assert math.isclose(stats_result["underforecast_rate"], 0.5)
    print("SELF-TEST: PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--frozen-root", type=Path)
    parser.add_argument("--phase1-root", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    required = [
        args.repo_root,
        args.frozen_root,
        args.phase1_root,
        args.spec,
        args.output_root,
    ]
    if any(value is None for value in required):
        raise SystemExit(
            "--repo-root, --frozen-root, --phase1-root, --spec and "
            "--output-root are required"
        )

    repo_root = args.repo_root.resolve()
    frozen_root = args.frozen_root.resolve()
    phase1_root = args.phase1_root.resolve()
    spec_path = (repo_root / args.spec).resolve()
    out = (repo_root / args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    figures_dir = out / "figures"

    config = json.loads(spec_path.read_text(encoding="utf-8"))
    weather_path = (
        frozen_root / config["input_paths"]["weather_residual_panel"]
    )
    if not weather_path.is_file():
        raise FileNotFoundError(weather_path)

    provenance = {
        "generated_utc": utc_now(),
        "working_branch": git(repo_root, "branch", "--show-current"),
        "working_commit": git(repo_root, "rev-parse", "HEAD"),
        "frozen_ref": config["frozen_ref"],
        "frozen_tag_object": git(
            repo_root, "rev-parse", config["frozen_ref"]
        ),
        "frozen_commit": git(
            repo_root, "rev-parse", f"{config['frozen_ref']}^{{commit}}"
        ),
        "weather_input": config["input_paths"]["weather_residual_panel"],
        "weather_input_sha256": sha256_file(weather_path),
        "phase1_root": phase1_root.relative_to(repo_root).as_posix(),
        "bootstrap_replications": config["bootstrap"]["replications"],
        "bootstrap_seed": config["bootstrap"]["seed"],
        "moving_block_lengths": config["bootstrap"][
            "moving_block_lengths"
        ],
    }
    (out / "phase2_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    panel = pd.read_csv(weather_path, low_memory=False)
    checks, static_crosscheck = validate_input(panel, config, phase1_root)
    checks.to_csv(out / "phase2_integrity_checks.csv", index=False)
    static_crosscheck.to_csv(
        out / "phase2_phase1_static_parameter_crosscheck.csv",
        index=False,
    )

    critical_failures = checks.loc[
        checks["critical"].astype(bool)
        & ~checks["passed"].astype(bool)
    ]
    if not critical_failures.empty:
        print(checks.to_string(index=False))
        raise RuntimeError(
            "Input integrity checks failed; analysis was not continued."
        )

    panel["target_date"] = pd.to_datetime(
        panel["target_date"]
    ).dt.strftime("%Y-%m-%d")
    for column in [
        "residual_c",
        "forecast_error_c",
        "absolute_error_c",
        "squared_error_c",
        "forecast_daily_max_c",
        "hko_daily_max_c",
    ]:
        panel[column] = pd.to_numeric(panel[column], errors="raise")

    summary, exceedances = build_summary_tables(panel, config)
    summary.to_csv(out / "phase2_residual_summary.csv", index=False)
    exceedances.to_csv(
        out / "phase2_practical_exceedance_probabilities.csv",
        index=False,
    )

    bootstrap, mean_tests = bootstrap_phase(panel, config)
    bootstrap.to_csv(
        out / "phase2_date_and_block_bootstrap_intervals.csv",
        index=False,
    )
    mean_tests.to_csv(
        out / "phase2_mean_zero_tests.csv",
        index=False,
    )

    (
        gaussian_quantiles,
        gaussian_exceedance,
        normality,
    ) = gaussian_comparison_tables(panel, config)
    gaussian_quantiles.to_csv(
        out / "phase2_empirical_vs_gaussian_quantiles.csv",
        index=False,
    )
    gaussian_exceedance.to_csv(
        out / "phase2_empirical_vs_gaussian_exceedances.csv",
        index=False,
    )
    normality.to_csv(
        out / "phase2_gaussian_descriptive_diagnostics.csv",
        index=False,
    )

    stability = stability_tables(panel, config)
    for name, frame in stability.items():
        frame.to_csv(
            out / f"phase2_stability_by_{name}.csv",
            index=False,
        )

    influence_detail, influence_summary = leave_one_date_out(panel)
    influence_detail.to_csv(
        out / "phase2_leave_one_date_out_detail.csv.gz",
        index=False,
        compression="gzip",
    )
    influence_summary.to_csv(
        out / "phase2_leave_one_date_out_summary.csv",
        index=False,
    )

    phase17_check, validation_blocks = phase17_crosscheck(
        summary, frozen_root, config
    )
    phase17_check.to_csv(
        out / "phase2_phase17_summary_crosscheck.csv",
        index=False,
    )
    validation_blocks.to_csv(
        out / "phase2_existing_validation_block_residual_summary.csv",
        index=False,
    )

    figure_metadata = make_figures(
        panel,
        gaussian_exceedance,
        figures_dir,
        dpi=int(config["figure_dpi"]),
    )
    figure_metadata.to_csv(
        out / "phase2_figure_registry.csv",
        index=False,
    )

    candidate_summary = build_candidate_summary(
        summary,
        bootstrap,
        gaussian_exceedance,
        influence_summary,
    )
    candidate_summary.to_csv(
        out / "phase2_thesis_candidate_summary.csv",
        index=False,
    )

    # Final output checks.
    output_checks = [
        {
            "check": "bootstrap_methods_present",
            "passed": set(
                bootstrap["bootstrap_method"].unique()
            ) == {"ordinary_date", "circular_moving_block"},
            "critical": True,
            "detail": (
                f"methods={sorted(bootstrap['bootstrap_method'].unique())}"
            ),
        },
        {
            "check": "moving_block_lengths_present",
            "passed": set(
                bootstrap.loc[
                    bootstrap["bootstrap_method"]
                    == "circular_moving_block",
                    "block_length_days",
                ].dropna().astype(int).unique()
            ) == set(config["bootstrap"]["moving_block_lengths"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "all_primary_scopes_present",
            "passed": set(summary["scope"]) == set(PRIMARY_SCOPES),
            "critical": True,
            "detail": f"scopes={sorted(summary['scope'])}",
        },
        {
            "check": "phase17_crosscheck",
            "passed": (
                not phase17_check.empty
                and bool(phase17_check["passed"].all())
            ),
            "critical": True,
            "detail": (
                f"max_abs_difference="
                f"{phase17_check['phase2_minus_phase17'].abs().max():.3e}"
                if not phase17_check.empty else "crosscheck unavailable"
            ),
        },
        {
            "check": "figures_created",
            "passed": len(figure_metadata) == 7 and all(
                (figures_dir / name).is_file()
                for name in figure_metadata["figure"]
            ),
            "critical": True,
            "detail": f"figures={len(figure_metadata)}",
        },
    ]
    all_checks = pd.concat(
        [checks, pd.DataFrame(output_checks)],
        ignore_index=True,
    )
    all_checks.to_csv(out / "phase2_integrity_checks.csv", index=False)

    write_report(
        out,
        provenance,
        all_checks,
        summary,
        bootstrap,
        mean_tests,
        gaussian_exceedance,
        influence_summary,
    )
    build_manifest(out, provenance)
    make_review_bundle(out)

    final_failures = all_checks.loc[
        all_checks["critical"].astype(bool)
        & ~all_checks["passed"].astype(bool)
    ]
    print("=" * 88)
    print("PHASE 2 — SETTLEMENT APPROXIMATION-ERROR ANALYSIS")
    print("=" * 88)
    print(all_checks.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase2_review_bundle.zip'}")
    if final_failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print(final_failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
