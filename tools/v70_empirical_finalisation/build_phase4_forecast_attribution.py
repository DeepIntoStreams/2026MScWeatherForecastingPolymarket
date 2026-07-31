#!/usr/bin/env python3
"""
Phase 4: full raw-static-RBF-Matérn forecast attribution.

Inputs are the accepted Phase 3 out-of-sample validation loss panel and its
date-level aggregation. This phase does not fit, tune, select or alter a model.

The phase:
- certifies the four-model 365-date, four-rule loss panel;
- reproduces the frozen mean date CRPS sequence;
- forms exact paired date-level, rule-level and block-level contrasts;
- computes ordinary date, circular moving-block and stationary-bootstrap
  inference;
- measures the breadth and concentration of improvements;
- performs leave-one-date-out and extreme-date influence analysis;
- describes where the selected Matérn procedure adds value;
- creates thesis-ready tables, figures, a report, manifest and review bundle.

Sign convention:
    loss_difference = model loss - benchmark loss.
Negative values favour the model named first.
    improvement = benchmark loss - model loss = -loss_difference.
Positive values favour the model named first.
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
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    raise RuntimeError("matplotlib is required") from exc


MODEL_ORDER = ["raw", "static", "rbf", "matern"]
MODEL_LABELS = {
    "raw": "Raw point",
    "static": "Static Gaussian",
    "rbf": "RBF GP",
    "matern": "Matérn-3/2 GP",
}
RULE_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]
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
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    alpha = 1.0 - confidence
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
    if n <= 0 or block_length <= 0:
        raise ValueError("n and block_length must be positive")
    blocks_needed = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(replications, blocks_needed))
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % n
    return indices.reshape(replications, -1)[:, :n]


def stationary_bootstrap_indices(
    n: int,
    mean_block_length: float,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Politis-Romano stationary bootstrap with circular continuation.

    Each new position restarts from a random date with probability 1/L and
    otherwise continues from the previous sampled index.
    """
    if n <= 0 or mean_block_length <= 0:
        raise ValueError("n and mean_block_length must be positive")
    restart_probability = 1.0 / float(mean_block_length)
    output = np.empty((replications, n), dtype=np.int64)
    output[:, 0] = rng.integers(0, n, size=replications)
    for position in range(1, n):
        restart = rng.random(replications) < restart_probability
        random_start = rng.integers(0, n, size=replications)
        continuation = (output[:, position - 1] + 1) % n
        output[:, position] = np.where(
            restart,
            random_start,
            continuation,
        )
    return output


def dependency_check(path: Path, label: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing={path}"
    frame = pd.read_csv(path)
    if not {"critical", "passed"}.issubset(frame.columns):
        return False, f"{label} check file lacks critical/passed columns"
    failed = frame.loc[
        frame["critical"].astype(bool)
        & ~frame["passed"].astype(bool)
    ]
    return failed.empty, f"critical_failures={len(failed)}"


def assign_chronological_blocks(
    dates: Sequence[str],
    expected_sizes: Sequence[int],
) -> pd.DataFrame:
    ordered = pd.DataFrame(
        {"target_date": sorted(pd.Series(dates).astype(str).unique())}
    )
    if sum(expected_sizes) != len(ordered):
        raise ValueError(
            f"Block sizes sum to {sum(expected_sizes)}, dates={len(ordered)}"
        )
    labels: list[int] = []
    positions: list[int] = []
    for block, size in enumerate(expected_sizes, start=1):
        labels.extend([block] * int(size))
        positions.extend(list(range(1, int(size) + 1)))
    ordered["validation_block"] = labels
    ordered["position_within_block"] = positions
    ordered["chronological_index"] = np.arange(1, len(ordered) + 1)
    return ordered


def validate_inputs(
    loss_panel: pd.DataFrame,
    date_losses: pd.DataFrame,
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

    for phase, key in [
        ("Phase 1", "phase1_completion"),
        ("Phase 2", "phase2_integrity"),
        ("Phase 3", "phase3_integrity"),
    ]:
        passed, detail = dependency_check(
            repo_root / config["input_paths"][key],
            phase,
        )
        add(f"{phase.lower().replace(' ', '')}_dependency", passed, detail)

    required_panel = {
        "target_date", "decision_rule", "model", "crps_c",
        "forecast_daily_max_c", "hko_daily_max_c",
        "temperature_predictive_mean_c",
        "predictive_standard_deviation_c",
        "residual_predictive_mean_c", "source",
    }
    missing_panel = sorted(required_panel - set(loss_panel.columns))
    add(
        "loss_panel_required_columns",
        not missing_panel,
        f"missing={missing_panel}",
    )

    required_dates = {"model", "target_date", "date_crps_c", "date_rules"}
    missing_dates = sorted(required_dates - set(date_losses.columns))
    add(
        "date_loss_required_columns",
        not missing_dates,
        f"missing={missing_dates}",
    )
    if missing_panel or missing_dates:
        return pd.DataFrame(checks)

    panel = loss_panel.copy()
    panel["model"] = panel["model"].map(normalise_model)
    panel["target_date"] = pd.to_datetime(
        panel["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    panel["decision_rule"] = panel["decision_rule"].astype(str)
    panel["crps_c"] = pd.to_numeric(panel["crps_c"], errors="coerce")

    date_frame = date_losses.copy()
    date_frame["model"] = date_frame["model"].map(normalise_model)
    date_frame["target_date"] = pd.to_datetime(
        date_frame["target_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    date_frame["date_crps_c"] = pd.to_numeric(
        date_frame["date_crps_c"], errors="coerce"
    )

    add(
        "loss_panel_expected_rows",
        len(panel) == expected["loss_panel_rows"],
        f"rows={len(panel)}",
    )
    add(
        "date_loss_expected_rows",
        len(date_frame) == expected["date_loss_rows"],
        f"rows={len(date_frame)}",
    )
    add(
        "expected_dates",
        panel["target_date"].nunique() == expected["validation_dates"]
        and date_frame["target_date"].nunique() == expected["validation_dates"],
        (
            f"panel_dates={panel['target_date'].nunique()}; "
            f"date_loss_dates={date_frame['target_date'].nunique()}"
        ),
    )
    add(
        "expected_models",
        set(panel["model"].unique()) == set(expected["models"])
        and set(date_frame["model"].unique()) == set(expected["models"]),
        (
            f"panel_models={sorted(panel['model'].unique())}; "
            f"date_models={sorted(date_frame['model'].unique())}"
        ),
    )
    add(
        "expected_rules",
        set(panel["decision_rule"].unique())
        == set(expected["decision_rules"]),
        f"rules={sorted(panel['decision_rule'].unique())}",
    )

    duplicate_panel = int(
        panel.duplicated(
            ["target_date", "decision_rule", "model"]
        ).sum()
    )
    duplicate_dates = int(
        date_frame.duplicated(["target_date", "model"]).sum()
    )
    add(
        "loss_panel_unique_keys",
        duplicate_panel == 0,
        f"duplicates={duplicate_panel}",
    )
    add(
        "date_loss_unique_keys",
        duplicate_dates == 0,
        f"duplicates={duplicate_dates}",
    )

    group_counts = (
        panel.groupby(["target_date", "model"])["decision_rule"]
        .agg(["count", "nunique"])
    )
    add(
        "four_rules_per_date_model",
        bool(
            (group_counts["count"] == expected["rows_per_date_model"]).all()
            and (
                group_counts["nunique"]
                == expected["rows_per_date_model"]
            ).all()
        ),
        (
            f"bad_count_groups="
            f"{int((group_counts['count'] != expected['rows_per_date_model']).sum())}; "
            f"bad_unique_groups="
            f"{int((group_counts['nunique'] != expected['rows_per_date_model']).sum())}"
        ),
    )

    add(
        "crps_finite_nonnegative",
        bool(
            np.isfinite(panel["crps_c"]).all()
            and (panel["crps_c"] >= -tolerance).all()
            and np.isfinite(date_frame["date_crps_c"]).all()
            and (date_frame["date_crps_c"] >= -tolerance).all()
        ),
        "",
    )

    recalculated = (
        panel.groupby(["target_date", "model"], as_index=False)
        .agg(
            recalculated_date_crps_c=("crps_c", "mean"),
            recalculated_rules=("decision_rule", "nunique"),
        )
    )
    merged = date_frame.merge(
        recalculated,
        on=["target_date", "model"],
        how="left",
        validate="one_to_one",
    )
    differences = (
        merged["date_crps_c"]
        - merged["recalculated_date_crps_c"]
    ).abs()
    add(
        "date_loss_reconciliation",
        float(differences.max()) <= tolerance
        and bool(
            (
                merged["recalculated_rules"]
                == expected["rows_per_date_model"]
            ).all()
        ),
        f"max_error={float(differences.max()):.3e}",
    )

    means = date_frame.groupby("model")["date_crps_c"].mean()
    reference = expected["reference_mean_date_crps"]
    reference_tolerance = float(expected["reference_tolerance"])
    for model in expected["models"]:
        value = float(means.loc[model])
        expected_value = float(reference[model])
        add(
            f"reference_mean_crps_{model}",
            abs(value - expected_value) <= reference_tolerance,
            (
                f"calculated={value:.9f}; "
                f"reference={expected_value:.9f}; "
                f"difference={value - expected_value:.3e}"
            ),
        )

    phase16_path = repo_root / config["input_paths"][
        "phase3_phase16_crosscheck"
    ]
    if phase16_path.is_file():
        phase16 = pd.read_csv(phase16_path)
        add(
            "phase3_phase16_crosscheck_passed",
            bool(
                not phase16.empty
                and phase16["passed"].astype(bool).all()
            ),
            (
                f"rows={len(phase16)}; "
                f"failed={int((~phase16['passed'].astype(bool)).sum())}"
            ),
        )
    else:
        add(
            "phase3_phase16_crosscheck_available",
            False,
            f"missing={phase16_path}",
        )

    return pd.DataFrame(checks)


def prepare_inputs(
    loss_panel: pd.DataFrame,
    date_losses: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = loss_panel.copy()
    panel["model"] = panel["model"].map(normalise_model)
    panel["target_date"] = pd.to_datetime(
        panel["target_date"]
    ).dt.strftime("%Y-%m-%d")
    panel["decision_rule"] = panel["decision_rule"].astype(str)
    numeric_columns = [
        "crps_c", "forecast_daily_max_c", "hko_daily_max_c",
        "temperature_predictive_mean_c",
        "predictive_standard_deviation_c",
        "residual_predictive_mean_c",
    ]
    for column in numeric_columns:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")

    date_frame = date_losses.copy()
    date_frame["model"] = date_frame["model"].map(normalise_model)
    date_frame["target_date"] = pd.to_datetime(
        date_frame["target_date"]
    ).dt.strftime("%Y-%m-%d")
    date_frame["date_crps_c"] = pd.to_numeric(
        date_frame["date_crps_c"], errors="coerce"
    )

    block_map = assign_chronological_blocks(
        date_frame["target_date"].unique(),
        config["expected"]["chronological_block_sizes"],
    )
    panel = panel.merge(
        block_map,
        on="target_date",
        how="left",
        validate="many_to_one",
    )
    date_frame = date_frame.merge(
        block_map,
        on="target_date",
        how="left",
        validate="many_to_one",
    )
    return panel, date_frame, block_map


def build_model_score_summary(
    date_losses: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model in MODEL_ORDER:
        values = date_losses.loc[
            date_losses["model"] == model,
            "date_crps_c",
        ].to_numpy(dtype=float)
        rows.append(
            {
                "model": model,
                "model_label": MODEL_LABELS[model],
                "dates": len(values),
                "mean_date_crps_c": float(np.mean(values)),
                "median_date_crps_c": float(np.median(values)),
                "standard_deviation_date_crps_c": float(
                    np.std(values, ddof=1)
                ),
                "q05_date_crps_c": float(np.quantile(values, 0.05)),
                "q25_date_crps_c": float(np.quantile(values, 0.25)),
                "q75_date_crps_c": float(np.quantile(values, 0.75)),
                "q95_date_crps_c": float(np.quantile(values, 0.95)),
            }
        )
    result = pd.DataFrame(rows)
    result["rank_by_mean_crps"] = result[
        "mean_date_crps_c"
    ].rank(method="min").astype(int)
    result["model_order"] = result["model"].map(
        {model: index for index, model in enumerate(MODEL_ORDER)}
    )
    return result.sort_values("model_order")


def build_ordered_attribution(
    model_summary: pd.DataFrame,
) -> pd.DataFrame:
    means = model_summary.set_index("model")["mean_date_crps_c"]
    sequence = [
        ("raw_to_static", "raw", "static"),
        ("static_to_rbf", "static", "rbf"),
        ("rbf_to_matern", "rbf", "matern"),
    ]
    total_gain = float(means["raw"] - means["matern"])
    rows: list[dict[str, Any]] = []
    for stage_order, (stage, before, after) in enumerate(
        sequence, start=1
    ):
        before_loss = float(means[before])
        after_loss = float(means[after])
        reduction = before_loss - after_loss
        rows.append(
            {
                "stage_order": stage_order,
                "stage": stage,
                "before_model": before,
                "after_model": after,
                "before_mean_date_crps_c": before_loss,
                "after_mean_date_crps_c": after_loss,
                "absolute_crps_reduction_c": reduction,
                "relative_reduction_from_previous": (
                    reduction / before_loss if before_loss != 0 else np.nan
                ),
                "reduction_as_fraction_of_raw_loss": (
                    reduction / float(means["raw"])
                    if means["raw"] != 0 else np.nan
                ),
                "share_of_total_raw_to_matern_reduction": (
                    reduction / total_gain if total_gain != 0 else np.nan
                ),
                "interpretation_caveat": (
                    "Ordered empirical attribution only; RBF and Matérn are "
                    "alternative, non-nested covariance specifications."
                ),
            }
        )
    return pd.DataFrame(rows)


def build_contrast_panels(
    panel: pd.DataFrame,
    date_losses: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    contrasts = config["contrasts"]

    date_pivot = date_losses.pivot(
        index="target_date",
        columns="model",
        values="date_crps_c",
    ).reindex(columns=MODEL_ORDER)
    if date_pivot.isna().any().any():
        raise ValueError("Date-level loss pivot is incomplete")

    rule_pivot = panel.pivot(
        index=["target_date", "decision_rule"],
        columns="model",
        values="crps_c",
    ).reindex(columns=MODEL_ORDER)
    if rule_pivot.isna().any().any():
        raise ValueError("Rule-level loss pivot is incomplete")

    date_metadata = (
        date_losses[
            [
                "target_date", "validation_block",
                "chronological_index", "position_within_block",
            ]
        ]
        .drop_duplicates("target_date")
        .set_index("target_date")
        .reindex(date_pivot.index)
    )

    date_rows: list[pd.DataFrame] = []
    rule_rows: list[pd.DataFrame] = []
    for contrast_order, contrast in enumerate(contrasts, start=1):
        model = contrast["model"]
        benchmark = contrast["benchmark"]

        date_difference = date_pivot[model] - date_pivot[benchmark]
        date_frame = pd.DataFrame(
            {
                "target_date": date_pivot.index,
                "contrast_order": contrast_order,
                "contrast": contrast["contrast"],
                "model": model,
                "benchmark": benchmark,
                "primary": bool(contrast["primary"]),
                "interpretation": contrast["interpretation"],
                "model_date_crps_c": date_pivot[model].to_numpy(),
                "benchmark_date_crps_c": date_pivot[
                    benchmark
                ].to_numpy(),
                "loss_difference_c": date_difference.to_numpy(),
                "improvement_c": -date_difference.to_numpy(),
                "validation_block": date_metadata[
                    "validation_block"
                ].to_numpy(),
                "chronological_index": date_metadata[
                    "chronological_index"
                ].to_numpy(),
                "position_within_block": date_metadata[
                    "position_within_block"
                ].to_numpy(),
            }
        )
        date_rows.append(date_frame)

        rule_difference = (
            rule_pivot[model] - rule_pivot[benchmark]
        )
        rule_frame = rule_pivot[
            [model, benchmark]
        ].reset_index()
        rule_frame = rule_frame.rename(
            columns={
                model: "model_rule_crps_c",
                benchmark: "benchmark_rule_crps_c",
            }
        )
        rule_frame["contrast_order"] = contrast_order
        rule_frame["contrast"] = contrast["contrast"]
        rule_frame["model"] = model
        rule_frame["benchmark"] = benchmark
        rule_frame["primary"] = bool(contrast["primary"])
        rule_frame["interpretation"] = contrast["interpretation"]
        rule_frame["loss_difference_c"] = (
            rule_frame["model_rule_crps_c"]
            - rule_frame["benchmark_rule_crps_c"]
        )
        rule_frame["improvement_c"] = -rule_frame[
            "loss_difference_c"
        ]
        rule_frame = rule_frame.merge(
            date_metadata.reset_index(),
            on="target_date",
            how="left",
            validate="many_to_one",
        )
        rule_rows.append(rule_frame)

    date_panel = pd.concat(date_rows, ignore_index=True)
    rule_panel = pd.concat(rule_rows, ignore_index=True)
    return date_panel, rule_panel


def contrast_point_summary(
    date_panel: pd.DataFrame,
    rule_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    def summarise(
        group: pd.DataFrame,
        scope_type: str,
        scope_value: str,
    ) -> dict[str, Any]:
        values = group["loss_difference_c"].to_numpy(dtype=float)
        improvements = -values
        return {
            "scope_type": scope_type,
            "scope_value": scope_value,
            "contrast": group["contrast"].iloc[0],
            "model": group["model"].iloc[0],
            "benchmark": group["benchmark"].iloc[0],
            "primary": bool(group["primary"].iloc[0]),
            "dates": int(group["target_date"].nunique()),
            "mean_loss_difference_c": float(np.mean(values)),
            "mean_improvement_c": float(np.mean(improvements)),
            "median_loss_difference_c": float(np.median(values)),
            "median_improvement_c": float(np.median(improvements)),
            "standard_deviation_loss_difference_c": float(
                np.std(values, ddof=1)
            ),
            "q05_loss_difference_c": float(np.quantile(values, 0.05)),
            "q10_loss_difference_c": float(np.quantile(values, 0.10)),
            "q25_loss_difference_c": float(np.quantile(values, 0.25)),
            "q75_loss_difference_c": float(np.quantile(values, 0.75)),
            "q90_loss_difference_c": float(np.quantile(values, 0.90)),
            "q95_loss_difference_c": float(np.quantile(values, 0.95)),
            "model_better_fraction": float(np.mean(values < 0.0)),
            "benchmark_better_fraction": float(np.mean(values > 0.0)),
            "equal_fraction": float(np.mean(values == 0.0)),
            "gross_model_favouring_improvement_c": float(
                np.sum(np.maximum(improvements, 0.0))
            ),
            "gross_benchmark_favouring_deterioration_c": float(
                np.sum(np.maximum(-improvements, 0.0))
            ),
            "net_total_improvement_c": float(np.sum(improvements)),
        }

    overall_rows: list[dict[str, Any]] = []
    rule_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    rule_block_rows: list[dict[str, Any]] = []

    for contrast, group in date_panel.groupby(
        "contrast", sort=False
    ):
        overall_rows.append(summarise(group, "overall", "all_dates"))
        for block, subgroup in group.groupby(
            "validation_block", sort=True
        ):
            block_rows.append(
                summarise(
                    subgroup,
                    "validation_block",
                    f"block_{int(block)}",
                )
            )

    for (contrast, rule), group in rule_panel.groupby(
        ["contrast", "decision_rule"],
        sort=False,
    ):
        rule_rows.append(
            summarise(group, "decision_rule", str(rule))
        )
        for block, subgroup in group.groupby(
            "validation_block", sort=True
        ):
            rule_block_rows.append(
                summarise(
                    subgroup,
                    "rule_by_block",
                    f"{rule}__block_{int(block)}",
                )
            )

    return (
        pd.DataFrame(overall_rows),
        pd.DataFrame(rule_rows),
        pd.DataFrame(block_rows),
        pd.DataFrame(rule_block_rows),
    )


def bootstrap_scope_matrix(
    scope_frame: pd.DataFrame,
    contrasts: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    scope_type: str,
    scope_value: str,
    include_stationary: bool,
    seed_offset: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    contrast_names = [item["contrast"] for item in contrasts]
    pivot = scope_frame.pivot(
        index="target_date",
        columns="contrast",
        values="loss_difference_c",
    ).reindex(columns=contrast_names)
    pivot = pivot.sort_index()
    if pivot.isna().any().any():
        raise ValueError(
            f"Incomplete contrast matrix for {scope_type} {scope_value}"
        )
    values = pivot.to_numpy(dtype=float)
    n, contrast_count = values.shape

    reps = int(config["bootstrap"]["replications"])
    confidence = float(config["bootstrap"]["confidence_level"])
    chunk_size = int(config["bootstrap"]["chunk_size"])
    base_seed = int(config["bootstrap"]["seed"]) + seed_offset

    methods: list[tuple[str, float | None]] = [("ordinary_date", None)]
    methods.extend(
        ("circular_moving_block", float(length))
        for length in config["bootstrap"]["moving_block_lengths"]
    )
    if include_stationary:
        methods.extend(
            ("stationary_bootstrap", float(length))
            for length in config["bootstrap"][
                "stationary_mean_block_lengths"
            ]
        )

    point_mean = values.mean(axis=0)
    point_median = np.median(values, axis=0)
    point_better = (values < 0.0).mean(axis=0)
    point_improvement = -point_mean

    interval_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []

    for method_index, (method, block_parameter) in enumerate(methods):
        local_seed = base_seed + method_index * 100
        rng = np.random.default_rng(local_seed)
        metric_parts: dict[str, list[np.ndarray]] = {
            "mean_loss_difference_c": [],
            "mean_improvement_c": [],
            "median_loss_difference_c": [],
            "model_better_fraction": [],
        }
        null_parts: list[np.ndarray] = []
        centred = values - point_mean[None, :]

        completed = 0
        while completed < reps:
            current = min(chunk_size, reps - completed)
            if method == "ordinary_date":
                indices = ordinary_indices(n, current, rng)
            elif method == "circular_moving_block":
                assert block_parameter is not None
                indices = moving_block_indices(
                    n,
                    int(block_parameter),
                    current,
                    rng,
                )
            elif method == "stationary_bootstrap":
                assert block_parameter is not None
                indices = stationary_bootstrap_indices(
                    n,
                    float(block_parameter),
                    current,
                    rng,
                )
            else:  # pragma: no cover
                raise ValueError(method)

            sampled = values[indices, :]
            sample_mean = sampled.mean(axis=1)
            metric_parts["mean_loss_difference_c"].append(
                sample_mean
            )
            metric_parts["mean_improvement_c"].append(
                -sample_mean
            )
            metric_parts["median_loss_difference_c"].append(
                np.median(sampled, axis=1)
            )
            metric_parts["model_better_fraction"].append(
                (sampled < 0.0).mean(axis=1)
            )
            null_parts.append(centred[indices, :].mean(axis=1))
            completed += current

        distributions = {
            metric: np.concatenate(parts, axis=0)
            for metric, parts in metric_parts.items()
        }
        null_distribution = np.concatenate(null_parts, axis=0)
        point_by_metric = {
            "mean_loss_difference_c": point_mean,
            "mean_improvement_c": point_improvement,
            "median_loss_difference_c": point_median,
            "model_better_fraction": point_better,
        }

        for contrast_index, contrast in enumerate(contrasts):
            for metric, distribution in distributions.items():
                lower, upper = percentile_interval(
                    distribution[:, contrast_index],
                    confidence,
                )
                interval_rows.append(
                    {
                        "scope_type": scope_type,
                        "scope_value": scope_value,
                        "contrast": contrast["contrast"],
                        "model": contrast["model"],
                        "benchmark": contrast["benchmark"],
                        "primary": bool(contrast["primary"]),
                        "dates": n,
                        "metric": metric,
                        "point_estimate": float(
                            point_by_metric[metric][contrast_index]
                        ),
                        "bootstrap_method": method,
                        "block_parameter_days": block_parameter,
                        "bootstrap_lower_95": lower,
                        "bootstrap_upper_95": upper,
                        "bootstrap_replications": reps,
                        "seed": local_seed,
                        "bootstrap_unit": "settlement_date",
                    }
                )

            null_values = null_distribution[:, contrast_index]
            observed = float(point_mean[contrast_index])
            p_value = float(
                (
                    1
                    + np.sum(
                        np.abs(null_values) >= abs(observed)
                    )
                )
                / (reps + 1)
            )
            test_rows.append(
                {
                    "scope_type": scope_type,
                    "scope_value": scope_value,
                    "contrast": contrast["contrast"],
                    "model": contrast["model"],
                    "benchmark": contrast["benchmark"],
                    "primary": bool(contrast["primary"]),
                    "dates": n,
                    "null_hypothesis": "mean_loss_difference_equals_zero",
                    "observed_mean_loss_difference_c": observed,
                    "bootstrap_method": method,
                    "block_parameter_days": block_parameter,
                    "two_sided_centred_bootstrap_p_value": p_value,
                    "minimum_resolvable_p_value": 1.0 / (reps + 1),
                    "bootstrap_replications": reps,
                    "seed": local_seed,
                    "bootstrap_unit": "settlement_date",
                }
            )

    return pd.DataFrame(interval_rows), pd.DataFrame(test_rows)


def run_bootstrap_inference(
    date_panel: pd.DataFrame,
    rule_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    contrasts = config["contrasts"]
    interval_frames: list[pd.DataFrame] = []
    test_frames: list[pd.DataFrame] = []
    seed_counter = 0

    overall_intervals, overall_tests = bootstrap_scope_matrix(
        date_panel,
        contrasts,
        config,
        scope_type="overall",
        scope_value="all_dates",
        include_stationary=True,
        seed_offset=seed_counter,
    )
    interval_frames.append(overall_intervals)
    test_frames.append(overall_tests)
    seed_counter += 10_000

    for rule_index, rule in enumerate(RULE_ORDER):
        frame = rule_panel.loc[
            rule_panel["decision_rule"] == rule
        ]
        intervals, tests = bootstrap_scope_matrix(
            frame,
            contrasts,
            config,
            scope_type="decision_rule",
            scope_value=rule,
            include_stationary=False,
            seed_offset=seed_counter + rule_index * 1_000,
        )
        interval_frames.append(intervals)
        test_frames.append(tests)
    seed_counter += 10_000

    for block in sorted(date_panel["validation_block"].unique()):
        frame = date_panel.loc[
            date_panel["validation_block"] == block
        ]
        intervals, tests = bootstrap_scope_matrix(
            frame,
            contrasts,
            config,
            scope_type="validation_block",
            scope_value=f"block_{int(block)}",
            include_stationary=False,
            seed_offset=seed_counter + int(block) * 1_000,
        )
        interval_frames.append(intervals)
        test_frames.append(tests)

    return (
        pd.concat(interval_frames, ignore_index=True),
        pd.concat(test_frames, ignore_index=True),
    )


def concentration_analysis(
    date_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    top_k_values = list(map(int, config["influence"]["top_k_values"]))
    best_worst_n = int(config["influence"]["best_worst_dates"])
    concentration_rows: list[dict[str, Any]] = []
    date_rows: list[pd.DataFrame] = []

    for contrast, group in date_panel.groupby(
        "contrast", sort=False
    ):
        ordered = group.sort_values(
            "improvement_c", ascending=False
        ).copy()
        gross_gain = float(
            np.maximum(ordered["improvement_c"], 0.0).sum()
        )
        gross_loss = float(
            np.maximum(-ordered["improvement_c"], 0.0).sum()
        )
        absolute_mass = float(
            ordered["improvement_c"].abs().sum()
        )
        positive = ordered.loc[ordered["improvement_c"] > 0.0]
        weights = (
            ordered["improvement_c"].abs() / absolute_mass
            if absolute_mass > 0
            else pd.Series(np.nan, index=ordered.index)
        )
        hhi = float(np.nansum(np.asarray(weights) ** 2))
        row: dict[str, Any] = {
            "contrast": contrast,
            "model": group["model"].iloc[0],
            "benchmark": group["benchmark"].iloc[0],
            "dates": len(group),
            "gross_model_favouring_improvement_c": gross_gain,
            "gross_benchmark_favouring_deterioration_c": gross_loss,
            "net_total_improvement_c": float(
                group["improvement_c"].sum()
            ),
            "absolute_contribution_mass_c": absolute_mass,
            "absolute_contribution_hhi": hhi,
            "absolute_contribution_effective_dates": (
                1.0 / hhi if hhi > 0 else np.nan
            ),
        }
        for k in top_k_values:
            top_positive = positive.nlargest(
                k, "improvement_c"
            )["improvement_c"].sum()
            top_absolute = ordered.nlargest(
                k, "improvement_c",
                keep="all",
            )["improvement_c"].abs().sum()
            largest_absolute = group.assign(
                absolute_improvement=group[
                    "improvement_c"
                ].abs()
            ).nlargest(k, "absolute_improvement")[
                "absolute_improvement"
            ].sum()
            row[
                f"top_{k}_model_favouring_share_of_gross_gain"
            ] = (
                float(top_positive / gross_gain)
                if gross_gain > 0 else np.nan
            )
            row[
                f"top_{k}_absolute_share_of_total_absolute_mass"
            ] = (
                float(largest_absolute / absolute_mass)
                if absolute_mass > 0 else np.nan
            )
        concentration_rows.append(row)

        best = group.nlargest(
            best_worst_n, "improvement_c"
        ).copy()
        best["tail"] = "largest_model_favouring_improvements"
        best["tail_rank"] = np.arange(1, len(best) + 1)
        worst = group.nsmallest(
            best_worst_n, "improvement_c"
        ).copy()
        worst["tail"] = "largest_benchmark_favouring_deteriorations"
        worst["tail_rank"] = np.arange(1, len(worst) + 1)
        date_rows.extend([best, worst])

    return (
        pd.DataFrame(concentration_rows),
        pd.concat(date_rows, ignore_index=True),
    )


def influence_analysis(
    date_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    scenario_rows: list[dict[str, Any]] = []
    remove_counts = list(
        map(int, config["influence"]["remove_extreme_counts"])
    )

    for contrast, group in date_panel.groupby(
        "contrast", sort=False
    ):
        group = group.sort_values("target_date").reset_index(drop=True)
        values = group["loss_difference_c"].to_numpy(dtype=float)
        full_mean = float(np.mean(values))
        n = len(group)
        total = float(np.sum(values))
        loo_means = (total - values) / (n - 1)
        changes = loo_means - full_mean

        local_detail = pd.DataFrame(
            {
                "contrast": contrast,
                "model": group["model"].iloc[0],
                "benchmark": group["benchmark"].iloc[0],
                "omitted_date": group["target_date"],
                "full_mean_loss_difference_c": full_mean,
                "leave_one_date_out_mean_loss_difference_c": loo_means,
                "change_from_full_c": changes,
                "absolute_change_from_full_c": np.abs(changes),
            }
        )
        detail_rows.append(local_detail)

        influential_index = int(np.argmax(np.abs(changes)))
        summary_rows.append(
            {
                "contrast": contrast,
                "model": group["model"].iloc[0],
                "benchmark": group["benchmark"].iloc[0],
                "dates": n,
                "full_mean_loss_difference_c": full_mean,
                "minimum_leave_one_out_mean_c": float(
                    np.min(loo_means)
                ),
                "maximum_leave_one_out_mean_c": float(
                    np.max(loo_means)
                ),
                "maximum_absolute_leave_one_out_change_c": float(
                    np.max(np.abs(changes))
                ),
                "most_influential_date": group.loc[
                    influential_index, "target_date"
                ],
                "most_influential_date_loss_difference_c": float(
                    values[influential_index]
                ),
                "sign_stable_under_all_leave_one_out": bool(
                    np.all(np.sign(loo_means) == np.sign(full_mean))
                ),
            }
        )

        scenario_rows.append(
            {
                "contrast": contrast,
                "scenario": "full_sample",
                "dates_remaining": n,
                "mean_loss_difference_c": full_mean,
                "change_from_full_c": 0.0,
            }
        )
        for count in remove_counts:
            model_favouring = group.nsmallest(
                count, "loss_difference_c"
            )
            benchmark_favouring = group.nlargest(
                count, "loss_difference_c"
            )
            largest_absolute = group.assign(
                absolute_difference=group[
                    "loss_difference_c"
                ].abs()
            ).nlargest(count, "absolute_difference")

            for label, removed in [
                (
                    f"remove_{count}_most_model_favouring_dates",
                    model_favouring,
                ),
                (
                    f"remove_{count}_most_benchmark_favouring_dates",
                    benchmark_favouring,
                ),
                (
                    f"remove_{count}_largest_absolute_dates",
                    largest_absolute,
                ),
            ]:
                remaining = group.loc[
                    ~group["target_date"].isin(
                        removed["target_date"]
                    )
                ]
                estimate = float(
                    remaining["loss_difference_c"].mean()
                )
                scenario_rows.append(
                    {
                        "contrast": contrast,
                        "scenario": label,
                        "dates_remaining": len(remaining),
                        "removed_dates": "|".join(
                            removed["target_date"].astype(str)
                        ),
                        "mean_loss_difference_c": estimate,
                        "change_from_full_c": estimate - full_mean,
                    }
                )

        for block in sorted(group["validation_block"].unique()):
            remaining = group.loc[
                group["validation_block"] != block
            ]
            estimate = float(
                remaining["loss_difference_c"].mean()
            )
            scenario_rows.append(
                {
                    "contrast": contrast,
                    "scenario": f"remove_validation_block_{int(block)}",
                    "dates_remaining": len(remaining),
                    "removed_dates": "",
                    "mean_loss_difference_c": estimate,
                    "change_from_full_c": estimate - full_mean,
                }
            )

    return (
        pd.concat(detail_rows, ignore_index=True),
        pd.DataFrame(summary_rows),
        pd.DataFrame(scenario_rows),
    )


def build_date_features(
    panel: pd.DataFrame,
    date_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    dates = (
        panel[
            [
                "target_date", "validation_block",
                "chronological_index",
            ]
        ]
        .drop_duplicates("target_date")
        .copy()
    )
    dates["target_date_dt"] = pd.to_datetime(dates["target_date"])
    dates["season"] = season_from_month(
        dates["target_date_dt"].dt.month
    )
    dates["year"] = dates["target_date_dt"].dt.year

    raw = panel.loc[panel["model"] == "raw"].copy()
    static = panel.loc[panel["model"] == "static"].copy()
    raw_features = (
        raw.groupby("target_date", as_index=False)
        .agg(
            mean_deterministic_forecast_c=(
                "forecast_daily_max_c", "mean"
            ),
            mean_hko_settlement_c=("hko_daily_max_c", "mean"),
            mean_raw_crps_c=("crps_c", "mean"),
        )
    )
    static_features = (
        static.groupby("target_date", as_index=False)
        .agg(
            mean_static_residual_correction_c=(
                "residual_predictive_mean_c", "mean"
            ),
            mean_static_predictive_sd_c=(
                "predictive_standard_deviation_c", "mean"
            ),
            mean_static_crps_c=("crps_c", "mean"),
        )
    )
    features = (
        dates.merge(
            raw_features,
            on="target_date",
            how="left",
            validate="one_to_one",
        )
        .merge(
            static_features,
            on="target_date",
            how="left",
            validate="one_to_one",
        )
    )
    features["mean_raw_absolute_error_c"] = features[
        "mean_raw_crps_c"
    ]

    quantile_columns = [
        "mean_deterministic_forecast_c",
        "mean_static_residual_correction_c",
        "mean_static_predictive_sd_c",
        "mean_raw_absolute_error_c",
    ]
    labels = [
        f"Q{index}"
        for index in range(1, int(config["subgroup_quantiles"]) + 1)
    ]
    for column in quantile_columns:
        features[f"{column}_quartile"] = pd.qcut(
            features[column].rank(method="first"),
            q=int(config["subgroup_quantiles"]),
            labels=labels,
        ).astype(str)

    matern_static = date_panel.loc[
        date_panel["contrast"] == "matern_minus_static",
        [
            "target_date", "loss_difference_c", "improvement_c",
        ],
    ].copy()
    return features.merge(
        matern_static,
        on="target_date",
        how="left",
        validate="one_to_one",
    )


def subgroup_analysis(
    date_features: pd.DataFrame,
    rule_panel: pd.DataFrame,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    reps = int(config["bootstrap"]["replications"])
    confidence = float(config["bootstrap"]["confidence_level"])
    base_seed = int(config["bootstrap"]["seed"]) + 90_000
    rows: list[dict[str, Any]] = []

    group_specs = [
        ("validation_block", "validation_block"),
        ("season", "season"),
        (
            "deterministic_forecast_quartile",
            "mean_deterministic_forecast_c_quartile",
        ),
        (
            "static_correction_quartile",
            "mean_static_residual_correction_c_quartile",
        ),
        (
            "static_spread_quartile",
            "mean_static_predictive_sd_c_quartile",
        ),
        (
            "raw_absolute_error_quartile",
            "mean_raw_absolute_error_c_quartile",
        ),
    ]

    group_counter = 0
    for group_type, column in group_specs:
        for group_value, group in date_features.groupby(
            column, sort=True, dropna=False
        ):
            values = group["loss_difference_c"].to_numpy(dtype=float)
            rng = np.random.default_rng(base_seed + group_counter)
            indices = ordinary_indices(len(values), reps, rng)
            bootstrap_means = values[indices].mean(axis=1)
            lower, upper = percentile_interval(
                bootstrap_means, confidence
            )
            rows.append(
                {
                    "group_type": group_type,
                    "group_value": str(group_value),
                    "contrast": "matern_minus_static",
                    "dates": len(values),
                    "mean_loss_difference_c": float(np.mean(values)),
                    "mean_improvement_c": float(np.mean(-values)),
                    "median_loss_difference_c": float(
                        np.median(values)
                    ),
                    "model_better_fraction": float(
                        np.mean(values < 0.0)
                    ),
                    "ordinary_date_bootstrap_lower_95_c": lower,
                    "ordinary_date_bootstrap_upper_95_c": upper,
                    "bootstrap_replications": reps,
                    "seed": base_seed + group_counter,
                    "confirmatory_status": "descriptive_subgroup",
                }
            )
            group_counter += 1

    rule_data = rule_panel.loc[
        rule_panel["contrast"] == "matern_minus_static"
    ]
    for rule_index, (rule, group) in enumerate(
        rule_data.groupby("decision_rule", sort=False)
    ):
        values = group["loss_difference_c"].to_numpy(dtype=float)
        rng = np.random.default_rng(base_seed + 10_000 + rule_index)
        indices = ordinary_indices(len(values), reps, rng)
        bootstrap_means = values[indices].mean(axis=1)
        lower, upper = percentile_interval(
            bootstrap_means, confidence
        )
        rows.append(
            {
                "group_type": "decision_rule",
                "group_value": str(rule),
                "contrast": "matern_minus_static",
                "dates": len(values),
                "mean_loss_difference_c": float(np.mean(values)),
                "mean_improvement_c": float(np.mean(-values)),
                "median_loss_difference_c": float(
                    np.median(values)
                ),
                "model_better_fraction": float(
                    np.mean(values < 0.0)
                ),
                "ordinary_date_bootstrap_lower_95_c": lower,
                "ordinary_date_bootstrap_upper_95_c": upper,
                "bootstrap_replications": reps,
                "seed": base_seed + 10_000 + rule_index,
                "confirmatory_status": "predeclared_rule_diagnostic",
            }
        )

    return pd.DataFrame(rows)


def optional_phase18_inventory(
    frozen_root: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    root = (
        frozen_root
        / config["input_paths"]["optional_frozen_phase18_root"]
    )
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return pd.DataFrame(
            [
                {
                    "relative_path": "",
                    "status": "root_missing",
                    "size_bytes": np.nan,
                    "sha256": "",
                }
            ]
        )
    for path in sorted(root.rglob("phase18*")):
        if path.is_file():
            rows.append(
                {
                    "relative_path": path.relative_to(
                        frozen_root
                    ).as_posix(),
                    "status": "found",
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    if not rows:
        rows.append(
            {
                "relative_path": "",
                "status": "no_phase18_named_files_found",
                "size_bytes": np.nan,
                "sha256": "",
            }
        )
    return pd.DataFrame(rows)


def make_figures(
    model_summary: pd.DataFrame,
    attribution: pd.DataFrame,
    date_panel: pd.DataFrame,
    rule_summary: pd.DataFrame,
    block_summary: pd.DataFrame,
    concentration: pd.DataFrame,
    output_dir: Path,
    dpi: int,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata: list[dict[str, Any]] = []

    ordered = model_summary.sort_values("model_order")

    # 1. Mean date CRPS by model.
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    ax.plot(
        [MODEL_LABELS[m] for m in ordered["model"]],
        ordered["mean_date_crps_c"],
        marker="o",
        linewidth=2,
    )
    ax.set_ylabel("Mean date CRPS (°C)")
    ax.set_title("Out-of-sample forecast attribution")
    fig.tight_layout()
    path = output_dir / "phase4_figure_mean_crps_by_model.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append(
        {
            "figure": path.name,
            "purpose": "Main-text candidate: raw-static-RBF-Matérn sequence",
        }
    )

    # 2. Ordered incremental reductions.
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    ax.bar(
        attribution["stage"],
        attribution["absolute_crps_reduction_c"],
    )
    ax.axhline(0.0, linewidth=1)
    ax.set_ylabel("Incremental mean date CRPS reduction (°C)")
    ax.set_title("Ordered empirical attribution of forecast improvement")
    fig.tight_layout()
    path = output_dir / "phase4_figure_incremental_attribution.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append(
        {
            "figure": path.name,
            "purpose": "Main-text candidate: most value arises from static correction",
        }
    )

    # 3. Paired date-level improvements.
    primary_names = [
        "static_minus_raw",
        "matern_minus_static",
        "matern_minus_rbf",
    ]
    data = [
        date_panel.loc[
            date_panel["contrast"] == contrast,
            "improvement_c",
        ].to_numpy()
        for contrast in primary_names
    ]
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    ax.boxplot(data, labels=primary_names, showfliers=True)
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_ylabel("Benchmark CRPS minus model CRPS (°C)")
    ax.set_title("Distribution of paired date-level improvements")
    fig.tight_layout()
    path = output_dir / "phase4_figure_paired_improvement_distributions.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append(
        {
            "figure": path.name,
            "purpose": "Appendix candidate: breadth and heterogeneity of gains",
        }
    )

    # 4. Cumulative mean improvement.
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    for contrast in ["matern_minus_static", "matern_minus_rbf"]:
        frame = date_panel.loc[
            date_panel["contrast"] == contrast
        ].sort_values("target_date")
        cumulative = frame["improvement_c"].expanding().mean()
        ax.plot(
            pd.to_datetime(frame["target_date"]),
            cumulative,
            label=contrast,
        )
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_xlabel("Validation date")
    ax.set_ylabel("Cumulative mean improvement (°C CRPS)")
    ax.set_title("Accumulation of conditional-GP improvements")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase4_figure_cumulative_improvement.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append(
        {
            "figure": path.name,
            "purpose": "Appendix candidate: temporal accumulation of small gains",
        }
    )

    # 5. Rule-level mean difference matrix.
    selected_contrasts = [
        "static_minus_raw",
        "matern_minus_static",
        "matern_minus_rbf",
    ]
    matrix = (
        rule_summary.loc[
            rule_summary["contrast"].isin(selected_contrasts)
        ]
        .pivot(
            index="contrast",
            columns="scope_value",
            values="mean_loss_difference_c",
        )
        .reindex(index=selected_contrasts, columns=RULE_ORDER)
    )
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    image = ax.imshow(matrix.to_numpy(), aspect="auto")
    ax.set_xticks(np.arange(len(RULE_ORDER)))
    ax.set_xticklabels([RULE_LABELS[r] for r in RULE_ORDER])
    ax.set_yticks(np.arange(len(selected_contrasts)))
    ax.set_yticklabels(selected_contrasts)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(
                j,
                i,
                f"{matrix.iloc[i, j]:.3f}",
                ha="center",
                va="center",
            )
    ax.set_title("Rule-level paired loss differences")
    fig.colorbar(image, ax=ax, label="Model minus benchmark CRPS (°C)")
    fig.tight_layout()
    path = output_dir / "phase4_figure_rule_contrast_matrix.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append(
        {
            "figure": path.name,
            "purpose": "Main/appendix candidate: improvement across decision rules",
        }
    )

    # 6. Validation-block heterogeneity.
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    for contrast in ["matern_minus_static", "matern_minus_rbf"]:
        frame = block_summary.loc[
            block_summary["contrast"] == contrast
        ].copy()
        frame["block"] = frame["scope_value"].str.extract(
            r"(\d+)"
        ).astype(int)
        frame = frame.sort_values("block")
        ax.plot(
            frame["block"],
            frame["mean_loss_difference_c"],
            marker="o",
            label=contrast,
        )
    ax.axhline(0.0, linestyle="--", linewidth=1)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("Chronological validation block")
    ax.set_ylabel("Model minus benchmark CRPS (°C)")
    ax.set_title("Temporal heterogeneity of conditional-GP gains")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase4_figure_block_heterogeneity.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append(
        {
            "figure": path.name,
            "purpose": "Main-text candidate: gains vary materially through time",
        }
    )

    # 7. Concentration curve of absolute paired contributions.
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    for contrast in ["matern_minus_static", "matern_minus_rbf"]:
        values = date_panel.loc[
            date_panel["contrast"] == contrast,
            "improvement_c",
        ].abs().sort_values(ascending=False).to_numpy()
        cumulative = np.cumsum(values) / np.sum(values)
        x = np.arange(1, len(values) + 1) / len(values)
        ax.plot(x, cumulative, label=contrast)
    ax.plot([0.0, 1.0], [0.0, 1.0], linestyle="--", linewidth=1)
    ax.set_xlabel("Fraction of dates, ordered by absolute contribution")
    ax.set_ylabel("Cumulative fraction of absolute contribution")
    ax.set_title("Concentration of paired forecast improvements")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "phase4_figure_improvement_concentration.pdf"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    metadata.append(
        {
            "figure": path.name,
            "purpose": "Appendix candidate: whether mean gains are broad or concentrated",
        }
    )

    return pd.DataFrame(metadata)


def thesis_candidate_summary(
    model_summary: pd.DataFrame,
    attribution: pd.DataFrame,
    overall_summary: pd.DataFrame,
    bootstrap_intervals: pd.DataFrame,
    concentration: pd.DataFrame,
    influence_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for model in MODEL_ORDER:
        record = model_summary.loc[
            model_summary["model"] == model
        ].iloc[0]
        rows.append(
            {
                "candidate_id": f"P4_MEAN_{model.upper()}",
                "quantity": f"{MODEL_LABELS[model]} mean date CRPS",
                "point_estimate": record["mean_date_crps_c"],
                "lower_95": np.nan,
                "upper_95": np.nan,
                "unit": "degrees Celsius CRPS",
                "preferred_location": "Results attribution table",
            }
        )

    for contrast in [
        "static_minus_raw",
        "matern_minus_static",
        "matern_minus_rbf",
    ]:
        point = overall_summary.loc[
            overall_summary["contrast"] == contrast
        ].iloc[0]
        interval = bootstrap_intervals.loc[
            (bootstrap_intervals["scope_type"] == "overall")
            & (bootstrap_intervals["scope_value"] == "all_dates")
            & (bootstrap_intervals["contrast"] == contrast)
            & (
                bootstrap_intervals["metric"]
                == "mean_loss_difference_c"
            )
            & (
                bootstrap_intervals["bootstrap_method"]
                == "ordinary_date"
            )
        ].iloc[0]
        block7 = bootstrap_intervals.loc[
            (bootstrap_intervals["scope_type"] == "overall")
            & (bootstrap_intervals["scope_value"] == "all_dates")
            & (bootstrap_intervals["contrast"] == contrast)
            & (
                bootstrap_intervals["metric"]
                == "mean_loss_difference_c"
            )
            & (
                bootstrap_intervals["bootstrap_method"]
                == "circular_moving_block"
            )
            & (
                bootstrap_intervals["block_parameter_days"]
                == 7.0
            )
        ].iloc[0]
        concentration_row = concentration.loc[
            concentration["contrast"] == contrast
        ].iloc[0]
        influence_row = influence_summary.loc[
            influence_summary["contrast"] == contrast
        ].iloc[0]
        rows.append(
            {
                "candidate_id": f"P4_CONTRAST_{contrast.upper()}",
                "quantity": f"{contrast} mean paired loss difference",
                "point_estimate": point["mean_loss_difference_c"],
                "lower_95": interval["bootstrap_lower_95"],
                "upper_95": interval["bootstrap_upper_95"],
                "moving_block_7_lower_95": block7[
                    "bootstrap_lower_95"
                ],
                "moving_block_7_upper_95": block7[
                    "bootstrap_upper_95"
                ],
                "model_better_fraction": point[
                    "model_better_fraction"
                ],
                "top_5_absolute_contribution_share": concentration_row[
                    "top_5_absolute_share_of_total_absolute_mass"
                ],
                "maximum_leave_one_out_change_c": influence_row[
                    "maximum_absolute_leave_one_out_change_c"
                ],
                "unit": "degrees Celsius CRPS",
                "preferred_location": "Results and robustness",
            }
        )

    for _, record in attribution.iterrows():
        rows.append(
            {
                "candidate_id": f"P4_STAGE_{record['stage'].upper()}",
                "quantity": (
                    f"{record['stage']} share of total raw-to-Matérn reduction"
                ),
                "point_estimate": record[
                    "share_of_total_raw_to_matern_reduction"
                ],
                "lower_95": np.nan,
                "upper_95": np.nan,
                "unit": "fraction",
                "preferred_location": "Results attribution interpretation",
            }
        )
    return pd.DataFrame(rows)


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    model_summary: pd.DataFrame,
    attribution: pd.DataFrame,
    overall_summary: pd.DataFrame,
    bootstrap_intervals: pd.DataFrame,
    block_summary: pd.DataFrame,
    concentration: pd.DataFrame,
    influence_summary: pd.DataFrame,
    config: Mapping[str, Any],
) -> None:
    failures = checks.loc[
        checks["critical"].astype(bool)
        & ~checks["passed"].astype(bool)
    ]
    status = "PASSED" if failures.empty else "FAILED"
    means = model_summary.set_index("model")["mean_date_crps_c"]

    lines = [
        "# Phase 4 — Full Forecast Attribution",
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
        "## Mean date CRPS sequence",
        "",
        (
            f"Raw point: **{means['raw']:.6f}**; static Gaussian: "
            f"**{means['static']:.6f}**; RBF GP: **{means['rbf']:.6f}**; "
            f"Matérn-3/2 GP: **{means['matern']:.6f}**."
        ),
        "",
        "The ordered reductions are:",
        "",
        attribution[
            [
                "stage", "absolute_crps_reduction_c",
                "relative_reduction_from_previous",
                "share_of_total_raw_to_matern_reduction",
            ]
        ].to_markdown(index=False),
        "",
        "## Primary paired contrasts",
        "",
    ]

    for contrast in [
        "static_minus_raw",
        "matern_minus_static",
        "matern_minus_rbf",
    ]:
        point = overall_summary.loc[
            overall_summary["contrast"] == contrast
        ].iloc[0]
        ordinary = bootstrap_intervals.loc[
            (bootstrap_intervals["scope_type"] == "overall")
            & (bootstrap_intervals["contrast"] == contrast)
            & (
                bootstrap_intervals["metric"]
                == "mean_loss_difference_c"
            )
            & (
                bootstrap_intervals["bootstrap_method"]
                == "ordinary_date"
            )
        ].iloc[0]
        moving_rows = bootstrap_intervals.loc[
            (bootstrap_intervals["scope_type"] == "overall")
            & (bootstrap_intervals["contrast"] == contrast)
            & (
                bootstrap_intervals["metric"]
                == "mean_loss_difference_c"
            )
            & (
                bootstrap_intervals["bootstrap_method"]
                == "circular_moving_block"
            )
        ].sort_values("block_parameter_days")
        concentration_row = concentration.loc[
            concentration["contrast"] == contrast
        ].iloc[0]
        influence_row = influence_summary.loc[
            influence_summary["contrast"] == contrast
        ].iloc[0]
        lines.extend(
            [
                f"### {contrast}",
                "",
                (
                    f"Mean model-minus-benchmark loss difference: "
                    f"**{point['mean_loss_difference_c']:.6f}°C**. "
                    f"Negative values favour the first model."
                ),
                "",
                (
                    f"Ordinary date-bootstrap 95% interval: "
                    f"[{ordinary['bootstrap_lower_95']:.6f}, "
                    f"{ordinary['bootstrap_upper_95']:.6f}]. "
                    f"The first model has lower loss on "
                    f"{100 * point['model_better_fraction']:.2f}% of dates."
                ),
                "",
                (
                    "Circular moving-block intervals: "
                    + "; ".join(
                        (
                            f"b={int(row['block_parameter_days'])}: "
                            f"[{row['bootstrap_lower_95']:.6f}, "
                            f"{row['bootstrap_upper_95']:.6f}]"
                        )
                        for _, row in moving_rows.iterrows()
                    )
                    + "."
                ),
                "",
                (
                    f"The five largest absolute date contributions account for "
                    f"{100 * concentration_row['top_5_absolute_share_of_total_absolute_mass']:.2f}% "
                    f"of total absolute contrast mass. The maximum "
                    f"leave-one-date-out change in the mean is "
                    f"{influence_row['maximum_absolute_leave_one_out_change_c']:.6f}°C."
                ),
                "",
            ]
        )

    matern_blocks = block_summary.loc[
        block_summary["contrast"] == "matern_minus_static",
        ["scope_value", "mean_loss_difference_c", "model_better_fraction"],
    ]
    lines.extend(
        [
            "## Temporal heterogeneity",
            "",
            matern_blocks.to_markdown(index=False),
            "",
            "The block analysis is diagnostic. A block-level reversal does not "
            "invalidate the overall paired result, but it limits claims that "
            "conditional GP gains are uniform through time.",
            "",
            "## Thesis use",
            "",
            "- Main text: four-model CRPS sequence and the three primary paired contrasts.",
            "- Main text or one compact figure: temporal block heterogeneity.",
            "- Appendix: full rule-level interval matrix, stationary bootstrap and subgroup diagnostics.",
            "- Empirical archive: all leave-one-date-out, extreme-date and concentration tables.",
            "- Do not describe the ordered stages as a causal decomposition or claim that RBF is nested inside Matérn.",
            "",
        ]
    )
    (out / "phase4_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase4_manifest.json",
            "phase4_review_bundle.zip",
        }:
            files.append(
                {
                    "relative_path": path.relative_to(out).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "phase": "phase4_full_forecast_attribution",
        "generated_utc": utc_now(),
        "provenance": dict(provenance),
        "files": files,
    }
    (out / "phase4_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase4_review_bundle.zip"
    with zipfile.ZipFile(
        bundle, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                archive.write(
                    path, path.relative_to(out).as_posix()
                )


def self_test() -> None:
    rng = np.random.default_rng(123)
    ordinary = ordinary_indices(20, 7, rng)
    assert ordinary.shape == (7, 20)

    rng = np.random.default_rng(123)
    moving = moving_block_indices(20, 3, 7, rng)
    assert moving.shape == (7, 20)
    assert moving.min() >= 0 and moving.max() < 20

    rng = np.random.default_rng(123)
    stationary = stationary_bootstrap_indices(20, 4, 7, rng)
    assert stationary.shape == (7, 20)
    assert stationary.min() >= 0 and stationary.max() < 20

    block_map = assign_chronological_blocks(
        [f"2025-01-{day:02d}" for day in range(1, 11)],
        [2, 2, 3, 3],
    )
    assert block_map["validation_block"].value_counts().sort_index().tolist() == [
        2, 2, 3, 3
    ]

    synthetic = pd.DataFrame(
        {
            "model": ["raw", "static", "rbf", "matern"],
            "mean_date_crps_c": [2.0, 1.0, 0.9, 0.8],
        }
    )
    attribution = build_ordered_attribution(synthetic)
    assert abs(attribution["absolute_crps_reduction_c"].sum() - 1.2) < 1e-12
    assert abs(
        attribution["share_of_total_raw_to_matern_reduction"].sum() - 1.0
    ) < 1e-12

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
    loss_path = repo_root / inputs["phase3_loss_panel"]
    date_loss_path = repo_root / inputs["phase3_date_losses"]
    if not loss_path.is_file():
        raise FileNotFoundError(loss_path)
    if not date_loss_path.is_file():
        raise FileNotFoundError(date_loss_path)

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
        "phase3_loss_panel": inputs["phase3_loss_panel"],
        "phase3_loss_panel_sha256": sha256_file(loss_path),
        "phase3_date_losses": inputs["phase3_date_losses"],
        "phase3_date_losses_sha256": sha256_file(date_loss_path),
        "bootstrap_replications": config["bootstrap"][
            "replications"
        ],
        "bootstrap_seed": config["bootstrap"]["seed"],
        "moving_block_lengths": config["bootstrap"][
            "moving_block_lengths"
        ],
        "stationary_mean_block_lengths": config["bootstrap"][
            "stationary_mean_block_lengths"
        ],
        "interpretation_boundary": config[
            "interpretation_boundary"
        ],
    }
    (out / "phase4_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    loss_panel = pd.read_csv(loss_path, low_memory=False)
    date_losses = pd.read_csv(date_loss_path, low_memory=False)

    checks = validate_inputs(
        loss_panel, date_losses, config, repo_root
    )
    checks.to_csv(out / "phase4_integrity_checks.csv", index=False)
    initial_failures = checks.loc[
        checks["critical"].astype(bool)
        & ~checks["passed"].astype(bool)
    ]
    if not initial_failures.empty:
        print(checks.to_string(index=False))
        raise RuntimeError("Phase 4 input checks failed")

    panel, date_frame, block_map = prepare_inputs(
        loss_panel, date_losses, config
    )
    block_map.to_csv(
        out / "phase4_validation_block_map.csv",
        index=False,
    )

    model_summary = build_model_score_summary(date_frame)
    model_summary.to_csv(
        out / "phase4_model_score_summary.csv",
        index=False,
    )
    attribution = build_ordered_attribution(model_summary)
    attribution.to_csv(
        out / "phase4_ordered_attribution.csv",
        index=False,
    )

    date_panel, rule_panel = build_contrast_panels(
        panel, date_frame, config
    )
    date_panel.to_csv(
        out / "phase4_date_level_contrast_panel.csv.gz",
        index=False,
        compression="gzip",
    )
    rule_panel.to_csv(
        out / "phase4_rule_level_contrast_panel.csv.gz",
        index=False,
        compression="gzip",
    )

    (
        overall_summary,
        rule_summary,
        block_summary,
        rule_block_summary,
    ) = contrast_point_summary(date_panel, rule_panel)
    overall_summary.to_csv(
        out / "phase4_overall_contrast_summary.csv",
        index=False,
    )
    rule_summary.to_csv(
        out / "phase4_rule_contrast_summary.csv",
        index=False,
    )
    block_summary.to_csv(
        out / "phase4_block_contrast_summary.csv",
        index=False,
    )
    rule_block_summary.to_csv(
        out / "phase4_rule_by_block_contrast_summary.csv",
        index=False,
    )

    bootstrap_intervals, bootstrap_tests = run_bootstrap_inference(
        date_panel, rule_panel, config
    )
    bootstrap_intervals.to_csv(
        out / "phase4_paired_bootstrap_intervals.csv",
        index=False,
    )
    bootstrap_tests.to_csv(
        out / "phase4_paired_bootstrap_tests.csv",
        index=False,
    )

    concentration, best_worst_dates = concentration_analysis(
        date_panel, config
    )
    concentration.to_csv(
        out / "phase4_improvement_concentration.csv",
        index=False,
    )
    best_worst_dates.to_csv(
        out / "phase4_best_worst_dates.csv",
        index=False,
    )

    (
        leave_one_out_detail,
        influence_summary,
        influence_scenarios,
    ) = influence_analysis(date_panel, config)
    leave_one_out_detail.to_csv(
        out / "phase4_leave_one_date_out_detail.csv.gz",
        index=False,
        compression="gzip",
    )
    influence_summary.to_csv(
        out / "phase4_leave_one_date_out_summary.csv",
        index=False,
    )
    influence_scenarios.to_csv(
        out / "phase4_influence_scenarios.csv",
        index=False,
    )

    date_features = build_date_features(
        panel, date_panel, config
    )
    date_features.to_csv(
        out / "phase4_date_feature_panel.csv",
        index=False,
    )
    subgroups = subgroup_analysis(
        date_features, rule_panel, config
    )
    subgroups.to_csv(
        out / "phase4_matern_value_subgroups.csv",
        index=False,
    )

    phase18_inventory = optional_phase18_inventory(
        frozen_root, config
    )
    phase18_inventory.to_csv(
        out / "phase4_optional_phase18_inventory.csv",
        index=False,
    )

    figure_registry = make_figures(
        model_summary,
        attribution,
        date_panel,
        rule_summary,
        block_summary,
        concentration,
        figures_dir,
        int(config["figure_dpi"]),
    )
    figure_registry.to_csv(
        out / "phase4_figure_registry.csv",
        index=False,
    )

    candidate_summary = thesis_candidate_summary(
        model_summary,
        attribution,
        overall_summary,
        bootstrap_intervals,
        concentration,
        influence_summary,
    )
    candidate_summary.to_csv(
        out / "phase4_thesis_candidate_summary.csv",
        index=False,
    )

    primary_contrasts = [
        item["contrast"]
        for item in config["contrasts"]
        if item["primary"]
    ]
    expected_block_sizes = sorted(
        config["expected"]["chronological_block_sizes"]
    )
    actual_block_sizes = sorted(
        block_map["validation_block"].value_counts().tolist()
    )
    contrast_identity_error = float(
        (
            date_panel["loss_difference_c"]
            + date_panel["improvement_c"]
        ).abs().max()
    )
    mean_reconciliation = (
        overall_summary.set_index("contrast")[
            "mean_loss_difference_c"
        ]
        - date_panel.groupby("contrast")[
            "loss_difference_c"
        ].mean()
    ).abs().max()

    ordinary_overall = bootstrap_intervals.loc[
        (bootstrap_intervals["scope_type"] == "overall")
        & (
            bootstrap_intervals["metric"]
            == "mean_loss_difference_c"
        )
        & (
            bootstrap_intervals["bootstrap_method"]
            == "ordinary_date"
        )
    ]
    moving_overall = bootstrap_intervals.loc[
        (bootstrap_intervals["scope_type"] == "overall")
        & (
            bootstrap_intervals["metric"]
            == "mean_loss_difference_c"
        )
        & (
            bootstrap_intervals["bootstrap_method"]
            == "circular_moving_block"
        )
    ]
    stationary_overall = bootstrap_intervals.loc[
        (bootstrap_intervals["scope_type"] == "overall")
        & (
            bootstrap_intervals["metric"]
            == "mean_loss_difference_c"
        )
        & (
            bootstrap_intervals["bootstrap_method"]
            == "stationary_bootstrap"
        )
    ]

    output_checks = [
        {
            "check": "validation_block_sizes",
            "passed": actual_block_sizes == expected_block_sizes,
            "critical": True,
            "detail": (
                f"actual={actual_block_sizes}; "
                f"expected={expected_block_sizes}"
            ),
        },
        {
            "check": "date_contrast_panel_rows",
            "passed": len(date_panel)
            == config["expected"]["validation_dates"]
            * len(config["contrasts"]),
            "critical": True,
            "detail": f"rows={len(date_panel)}",
        },
        {
            "check": "rule_contrast_panel_rows",
            "passed": len(rule_panel)
            == config["expected"]["validation_dates"]
            * len(RULE_ORDER)
            * len(config["contrasts"]),
            "critical": True,
            "detail": f"rows={len(rule_panel)}",
        },
        {
            "check": "contrast_sign_identity",
            "passed": contrast_identity_error
            <= config["numerical_tolerance"],
            "critical": True,
            "detail": f"max_error={contrast_identity_error:.3e}",
        },
        {
            "check": "contrast_mean_reconciliation",
            "passed": float(mean_reconciliation)
            <= config["numerical_tolerance"],
            "critical": True,
            "detail": f"max_error={float(mean_reconciliation):.3e}",
        },
        {
            "check": "ordinary_intervals_all_contrasts",
            "passed": set(ordinary_overall["contrast"])
            == set(item["contrast"] for item in config["contrasts"]),
            "critical": True,
            "detail": f"contrasts={sorted(ordinary_overall['contrast'].unique())}",
        },
        {
            "check": "moving_block_lengths_all_primary",
            "passed": set(
                moving_overall.loc[
                    moving_overall["contrast"].isin(
                        primary_contrasts
                    ),
                    "block_parameter_days",
                ].astype(int).unique()
            )
            == set(config["bootstrap"]["moving_block_lengths"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "stationary_bootstrap_lengths_all_primary",
            "passed": set(
                stationary_overall.loc[
                    stationary_overall["contrast"].isin(
                        primary_contrasts
                    ),
                    "block_parameter_days",
                ].astype(int).unique()
            )
            == set(
                config["bootstrap"][
                    "stationary_mean_block_lengths"
                ]
            ),
            "critical": True,
            "detail": "",
        },
        {
            "check": "rule_interval_matrix_complete",
            "passed": len(
                bootstrap_intervals.loc[
                    (bootstrap_intervals["scope_type"]
                     == "decision_rule")
                    & (
                        bootstrap_intervals["metric"]
                        == "mean_loss_difference_c"
                    )
                    & (
                        bootstrap_intervals["bootstrap_method"]
                        == "ordinary_date"
                    )
                ]
            )
            == len(RULE_ORDER) * len(config["contrasts"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "block_interval_matrix_complete",
            "passed": len(
                bootstrap_intervals.loc[
                    (bootstrap_intervals["scope_type"]
                     == "validation_block")
                    & (
                        bootstrap_intervals["metric"]
                        == "mean_loss_difference_c"
                    )
                    & (
                        bootstrap_intervals["bootstrap_method"]
                        == "ordinary_date"
                    )
                ]
            )
            == config["chronological_blocks"]
            * len(config["contrasts"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "ordered_attribution_reconciles",
            "passed": abs(
                attribution["absolute_crps_reduction_c"].sum()
                - (
                    model_summary.set_index("model").loc[
                        "raw", "mean_date_crps_c"
                    ]
                    - model_summary.set_index("model").loc[
                        "matern", "mean_date_crps_c"
                    ]
                )
            )
            <= config["numerical_tolerance"],
            "critical": True,
            "detail": "",
        },
        {
            "check": "influence_all_contrasts",
            "passed": set(influence_summary["contrast"])
            == set(item["contrast"] for item in config["contrasts"]),
            "critical": True,
            "detail": "",
        },
        {
            "check": "subgroup_outputs_present",
            "passed": {
                "validation_block", "season",
                "deterministic_forecast_quartile",
                "static_correction_quartile",
                "static_spread_quartile",
                "raw_absolute_error_quartile",
                "decision_rule",
            }.issubset(set(subgroups["group_type"])),
            "critical": True,
            "detail": f"types={sorted(subgroups['group_type'].unique())}",
        },
        {
            "check": "figures_created",
            "passed": len(figure_registry) == 7
            and all(
                (figures_dir / figure).is_file()
                for figure in figure_registry["figure"]
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
        out / "phase4_integrity_checks.csv",
        index=False,
    )

    write_report(
        out,
        provenance,
        all_checks,
        model_summary,
        attribution,
        overall_summary,
        bootstrap_intervals,
        block_summary,
        concentration,
        influence_summary,
        config,
    )
    build_manifest(out, provenance)
    make_review_bundle(out)

    final_failures = all_checks.loc[
        all_checks["critical"].astype(bool)
        & ~all_checks["passed"].astype(bool)
    ]
    print("=" * 92)
    print("PHASE 4 — FULL RAW-STATIC-RBF-MATÉRN FORECAST ATTRIBUTION")
    print("=" * 92)
    print(all_checks.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase4_review_bundle.zip'}")
    if final_failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print(final_failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
