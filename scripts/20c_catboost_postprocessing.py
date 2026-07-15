#!/usr/bin/env python3
"""
20c: Compact CatBoost post-processing on frozen date-grouped folds.

This step:
- reads the 20a supervised feature matrix and 20b frozen split design;
- trains only on development dates;
- never evaluates the final chronological holdout;
- compares weather-only, market-only, combined, and combined-no-book feature sets;
- uses a compact pre-declared CatBoost candidate grid;
- generates out-of-fold probabilities on expanding-window validation dates;
- ranks model specifications by mean date-level Brier, then mean date-level log score;
- writes reproducible diagnostics and a review bundle.

The selected specification is not yet calibrated. Calibration and event-book coherence
are deferred to 20d.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    from catboost import CatBoostClassifier
except Exception as exc:
    raise SystemExit(
        "CatBoost is required for 20c. Install it with:\n"
        "python -m pip install catboost\n"
        f"Original import error: {exc}"
    )


STEP = "20c"
EPS = 1e-6
DECISION_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]


@dataclass(frozen=True)
class Config:
    repo_root: Path
    bootstrap_reps: int
    random_seed: int


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--bootstrap-reps", type=int, default=5000)
    parser.add_argument("--random-seed", type=int, default=20260715)
    args = parser.parse_args()
    if args.bootstrap_reps < 500:
        raise ValueError("--bootstrap-reps must be at least 500.")
    return Config(
        repo_root=args.repo_root.expanduser().resolve(),
        bootstrap_reps=int(args.bootstrap_reps),
        random_seed=int(args.random_seed),
    )


def load_inputs(repo: Path) -> tuple[pd.DataFrame, dict[str, list[str]], pd.DataFrame, pd.DataFrame]:
    processed = repo / "data" / "processed"
    matrix_path = processed / "20a_supervised_feature_matrix.csv"
    feature_sets_path = processed / "20a_model_feature_sets.json"
    cv_dates_path = processed / "20b_cv_date_assignments.csv"
    partitions_path = processed / "20b_date_partition_assignments.csv"

    for path in [matrix_path, feature_sets_path, cv_dates_path, partitions_path]:
        if not path.exists():
            raise FileNotFoundError(f"Missing required input: {path}")

    matrix = pd.read_csv(matrix_path, low_memory=False)
    matrix["event_date"] = pd.to_datetime(matrix["event_date"], errors="raise").dt.normalize()
    feature_sets = json.loads(feature_sets_path.read_text())
    cv_dates = pd.read_csv(cv_dates_path)
    cv_dates["event_date"] = pd.to_datetime(cv_dates["event_date"], errors="raise").dt.normalize()
    partitions = pd.read_csv(partitions_path)
    partitions["event_date"] = pd.to_datetime(partitions["event_date"], errors="raise").dt.normalize()

    required_matrix = {"event_date", "decision_rule", "target_Y_event", "date_group_id"}
    missing = sorted(required_matrix - set(matrix.columns))
    if missing:
        raise ValueError(f"20a matrix missing required columns: {missing}")

    return matrix, feature_sets, cv_dates, partitions



def resolve_probability_columns(columns: Iterable[str]) -> dict[str, str]:
    """
    Resolve probability columns produced by 19a/19c/20a without assuming one exact
    historical spelling. The mapping is frozen once at run time and written to the
    selected-model manifest.
    """
    cols = list(columns)
    lower = {c.lower(): c for c in cols}

    exact_aliases = {
        "market": [
            "p_market",
            "market_probability",
            "polymarket_probability",
        ],
        "ecmwf_raw": [
            "p_ecmwf_proxy",
            "p_ecmwf_raw_proxy",
            "p_raw_ecmwf_proxy",
            "p_ecmwf_raw",
        ],
        "ecmwf_bias_fixed_sigma": [
            "p_ecmwf_bias_fixed_sigma",
            "p_ecmwf_bias_corrected_fixed_sigma",
            "p_ecmwf_fixed_sigma_bias_corrected",
            "p_bias_corrected_fixed_sigma",
        ],
        "ecmwf_bias_adaptive_sigma": [
            "p_ecmwf_bias_adaptive_sigma",
            "p_ecmwf_bias_scale",
            "p_ecmwf_bias_and_scale",
            "p_ecmwf_bias_scale_corrected",
            "p_bias_and_scale_corrected",
            "p_ecmwf_adaptive_sigma",
        ],
    }

    resolved: dict[str, str] = {}
    for model, aliases in exact_aliases.items():
        for alias in aliases:
            if alias.lower() in lower:
                resolved[model] = lower[alias.lower()]
                break

    # Conservative semantic fallback when an exact alias is unavailable.
    for c in cols:
        name = c.lower()
        if not name.startswith("p_"):
            continue
        if "market" in name and "market" not in resolved:
            resolved["market"] = c
        if "ecmwf" not in name:
            continue
        if (
            "raw" in name or "proxy" in name
        ) and not any(x in name for x in ["bias", "fixed", "adaptive", "scale"]):
            resolved.setdefault("ecmwf_raw", c)
        if "bias" in name and "fixed" in name:
            resolved.setdefault("ecmwf_bias_fixed_sigma", c)
        if "bias" in name and any(x in name for x in ["adaptive", "scale"]):
            resolved.setdefault("ecmwf_bias_adaptive_sigma", c)

    return resolved


def candidate_grid() -> list[dict[str, Any]]:
    # Deliberately compact because the effective sample size is measured in dates.
    return [
        {
            "candidate_id": "cb_d3_lr03_l2_8",
            "depth": 3,
            "learning_rate": 0.03,
            "l2_leaf_reg": 8.0,
            "iterations": 350,
        },
        {
            "candidate_id": "cb_d4_lr03_l2_12",
            "depth": 4,
            "learning_rate": 0.03,
            "l2_leaf_reg": 12.0,
            "iterations": 350,
        },
        {
            "candidate_id": "cb_d3_lr05_l2_12",
            "depth": 3,
            "learning_rate": 0.05,
            "l2_leaf_reg": 12.0,
            "iterations": 250,
        },
    ]


def safe_log_score(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def brier_score(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return (np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2


def identify_categorical_features(df: pd.DataFrame, features: list[str]) -> list[str]:
    categorical = []
    for col in features:
        if col not in df.columns:
            continue
        if (
            pd.api.types.is_object_dtype(df[col])
            or pd.api.types.is_string_dtype(df[col])
            or pd.api.types.is_bool_dtype(df[col])
            or pd.api.types.is_categorical_dtype(df[col])
        ):
            categorical.append(col)
    return categorical


def prepare_features(
    df: pd.DataFrame,
    features: list[str],
    categorical: list[str],
) -> pd.DataFrame:
    X = df[features].copy()
    for col in categorical:
        X[col] = X[col].astype("string").fillna("__MISSING__").astype(str)
    for col in features:
        if col not in categorical:
            X[col] = pd.to_numeric(X[col], errors="coerce")
    return X


def fit_predict_one_fold(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    features: list[str],
    params: dict[str, Any],
    seed: int,
) -> tuple[np.ndarray, list[str]]:
    categorical = identify_categorical_features(train, features)
    X_train = prepare_features(train, features, categorical)
    X_val = prepare_features(validation, features, categorical)
    y_train = train["target_Y_event"].astype(int)

    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="Logloss",
        depth=int(params["depth"]),
        learning_rate=float(params["learning_rate"]),
        l2_leaf_reg=float(params["l2_leaf_reg"]),
        iterations=int(params["iterations"]),
        random_seed=int(seed),
        random_strength=0.5,
        border_count=64,
        auto_class_weights=None,
        verbose=False,
        allow_writing_files=False,
        thread_count=-1,
    )
    model.fit(
        X_train,
        y_train,
        cat_features=categorical,
        verbose=False,
    )
    p = model.predict_proba(X_val)[:, 1]
    return np.clip(p, EPS, 1 - EPS), categorical


def make_oof_predictions(
    matrix: pd.DataFrame,
    feature_sets: dict[str, list[str]],
    cv_dates: pd.DataFrame,
    config: Config,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    results: list[pd.DataFrame] = []
    fit_inventory: list[dict[str, Any]] = []

    allowed_sets = ["weather_only", "market_only", "combined", "combined_no_book"]
    grid = candidate_grid()

    for feature_set_name in allowed_sets:
        if feature_set_name not in feature_sets:
            continue
        features = [c for c in feature_sets[feature_set_name] if c in matrix.columns]
        if not features:
            raise ValueError(f"No valid features found for set: {feature_set_name}")

        for params in grid:
            for fold_id in sorted(cv_dates["cv_fold"].unique()):
                fold = cv_dates.loc[cv_dates["cv_fold"] == fold_id]
                train_dates = set(fold.loc[fold["cv_role"] == "train", "event_date"])
                validation_dates = set(fold.loc[fold["cv_role"] == "validation", "event_date"])

                train = matrix.loc[matrix["event_date"].isin(train_dates)].copy()
                validation = matrix.loc[matrix["event_date"].isin(validation_dates)].copy()

                eligibility_col = {
                    "weather_only": "eligible_weather_only",
                    "market_only": "eligible_market_only",
                    "combined": "eligible_combined",
                    "combined_no_book": "eligible_combined",
                }.get(feature_set_name)

                if eligibility_col in matrix.columns:
                    train = train.loc[train[eligibility_col].astype(bool)].copy()
                    validation = validation.loc[validation[eligibility_col].astype(bool)].copy()

                if train.empty or validation.empty:
                    raise ValueError(
                        f"Empty train/validation set for {feature_set_name}, "
                        f"{params['candidate_id']}, fold {fold_id}"
                    )
                if train["target_Y_event"].nunique() < 2:
                    raise ValueError(
                        f"Training target has one class for fold {fold_id}, "
                        f"{feature_set_name}, {params['candidate_id']}"
                    )

                pred, categorical = fit_predict_one_fold(
                    train,
                    validation,
                    features,
                    params,
                    seed=config.random_seed + int(fold_id),
                )

                probability_columns = resolve_probability_columns(validation.columns)
                keep_cols = [
                    c for c in [
                        "event_date",
                        "date_group_id",
                        "decision_rule",
                        "market_slug",
                        "condition_id",
                        "token_id",
                        "contract_event_type_v2",
                        "target_Y_event",
                    ] if c in validation.columns
                ]
                for resolved_col in probability_columns.values():
                    if resolved_col not in keep_cols:
                        keep_cols.append(resolved_col)
                out = validation[keep_cols].copy()
                out["cv_fold"] = int(fold_id)
                out["feature_set"] = feature_set_name
                out["candidate_id"] = params["candidate_id"]
                out["p_catboost_oof"] = pred
                out["brier_catboost_oof"] = brier_score(
                    out["target_Y_event"].to_numpy(), pred
                )
                out["log_catboost_oof"] = safe_log_score(
                    out["target_Y_event"].to_numpy(), pred
                )
                results.append(out)

                fit_inventory.append(
                    {
                        "feature_set": feature_set_name,
                        "candidate_id": params["candidate_id"],
                        "cv_fold": int(fold_id),
                        "n_train_rows": len(train),
                        "n_train_dates": train["event_date"].nunique(),
                        "n_validation_rows": len(validation),
                        "n_validation_dates": validation["event_date"].nunique(),
                        "n_features": len(features),
                        "n_categorical_features": len(categorical),
                        "categorical_features": "|".join(categorical),
                        **params,
                    }
                )

    return pd.concat(results, ignore_index=True), pd.DataFrame(fit_inventory)


def summarise_oof(oof: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    row_summary = (
        oof.groupby(["feature_set", "candidate_id"], as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_dates=("event_date", "nunique"),
            outcome_rate=("target_Y_event", "mean"),
            mean_brier=("brier_catboost_oof", "mean"),
            mean_log_score=("log_catboost_oof", "mean"),
        )
    )

    date_level = (
        oof.groupby(
            ["feature_set", "candidate_id", "event_date"],
            as_index=False,
        )
        .agg(
            n_rows=("target_Y_event", "size"),
            outcome_rate=("target_Y_event", "mean"),
            date_mean_brier=("brier_catboost_oof", "mean"),
            date_mean_log_score=("log_catboost_oof", "mean"),
        )
    )

    date_summary = (
        date_level.groupby(["feature_set", "candidate_id"], as_index=False)
        .agg(
            n_dates=("event_date", "nunique"),
            mean_date_brier=("date_mean_brier", "mean"),
            median_date_brier=("date_mean_brier", "median"),
            mean_date_log_score=("date_mean_log_score", "mean"),
            median_date_log_score=("date_mean_log_score", "median"),
        )
    )

    ranking = row_summary.drop(columns=["n_dates"], errors="ignore").merge(
        date_summary,
        on=["feature_set", "candidate_id"],
        how="left",
        validate="one_to_one",
    )
    ranking = ranking.sort_values(
        ["mean_date_brier", "mean_date_log_score", "mean_brier", "mean_log_score"],
        ascending=True,
    ).reset_index(drop=True)
    ranking["overall_rank"] = np.arange(1, len(ranking) + 1)
    ranking["selected"] = ranking["overall_rank"].eq(1)

    return row_summary, date_level, ranking


def benchmark_panel(
    oof: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    id_cols = [
        c for c in [
            "event_date",
            "date_group_id",
            "decision_rule",
            "market_slug",
            "condition_id",
            "token_id",
            "contract_event_type_v2",
            "target_Y_event",
            "cv_fold",
        ] if c in oof.columns
    ]
    selected = oof.loc[oof["selected_model"].astype(bool)].copy()

    resolved = resolve_probability_columns(selected.columns)
    expected_benchmarks = [
        "market",
        "ecmwf_raw",
        "ecmwf_bias_fixed_sigma",
        "ecmwf_bias_adaptive_sigma",
    ]

    model_cols = {"catboost_selected": "p_catboost_oof", **resolved}
    rows = []
    for model, col in model_cols.items():
        if col not in selected.columns:
            continue
        tmp = selected[id_cols].copy()
        tmp["model"] = model
        tmp["source_probability_column"] = col
        tmp["probability"] = pd.to_numeric(selected[col], errors="coerce")
        tmp = tmp.loc[tmp["probability"].notna()].copy()
        tmp["brier"] = brier_score(
            tmp["target_Y_event"].to_numpy(),
            tmp["probability"].to_numpy(),
        )
        tmp["log_score"] = safe_log_score(
            tmp["target_Y_event"].to_numpy(),
            tmp["probability"].to_numpy(),
        )
        rows.append(tmp)

    if not rows:
        raise ValueError("No benchmark probabilities were retained.")
    return pd.concat(rows, ignore_index=True), resolved, expected_benchmarks


def paired_date_bootstrap(
    panel: pd.DataFrame,
    model_a: str,
    model_b: str,
    metric: str,
    reps: int,
    seed: int,
) -> dict[str, Any]:
    date_scores = (
        panel.loc[panel["model"].isin([model_a, model_b])]
        .groupby(["event_date", "model"], as_index=False)[metric]
        .mean()
        .pivot(index="event_date", columns="model", values=metric)
        .dropna(subset=[model_a, model_b])
    )
    diff = (date_scores[model_a] - date_scores[model_b]).to_numpy()
    rng = np.random.default_rng(seed)
    draws = rng.choice(diff, size=(reps, len(diff)), replace=True).mean(axis=1)
    return {
        "metric": metric,
        "model_a": model_a,
        "model_b": model_b,
        "n_dates": len(diff),
        "mean_difference_a_minus_b": float(diff.mean()),
        "bootstrap_ci_2_5": float(np.quantile(draws, 0.025)),
        "bootstrap_ci_97_5": float(np.quantile(draws, 0.975)),
        "lower_is_better": True,
    }


def benchmark_summary_and_comparisons(
    panel: pd.DataFrame,
    config: Config,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    row_summary = (
        panel.groupby("model", as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_dates=("event_date", "nunique"),
            mean_brier=("brier", "mean"),
            mean_log_score=("log_score", "mean"),
        )
        .sort_values(["mean_brier", "mean_log_score"])
    )

    date_panel = (
        panel.groupby(["event_date", "model"], as_index=False)
        .agg(
            date_mean_brier=("brier", "mean"),
            date_mean_log_score=("log_score", "mean"),
        )
    )

    comparisons = []
    for benchmark in [
        "market",
        "ecmwf_raw",
        "ecmwf_bias_fixed_sigma",
        "ecmwf_bias_adaptive_sigma",
    ]:
        if benchmark not in set(panel["model"]):
            continue
        for metric in ["brier", "log_score"]:
            comparisons.append(
                paired_date_bootstrap(
                    panel,
                    "catboost_selected",
                    benchmark,
                    metric,
                    config.bootstrap_reps,
                    config.random_seed + len(comparisons),
                )
            )
    if "catboost_selected" in set(row_summary["model"]):
        cat = row_summary.loc[row_summary["model"] == "catboost_selected"].iloc[0]
        direct = row_summary.loc[row_summary["model"] != "catboost_selected"].copy()
        catboost_beats_any_direct_brier = bool(
            (cat["mean_brier"] < direct["mean_brier"]).any()
        ) if not direct.empty else False
        catboost_beats_any_direct_log = bool(
            (cat["mean_log_score"] < direct["mean_log_score"]).any()
        ) if not direct.empty else False
        row_summary["catboost_beats_any_direct_brier"] = catboost_beats_any_direct_brier
        row_summary["catboost_beats_any_direct_log"] = catboost_beats_any_direct_log

    return row_summary, date_panel, pd.DataFrame(comparisons)


def feature_importance_for_selected(
    matrix: pd.DataFrame,
    cv_dates: pd.DataFrame,
    feature_sets: dict[str, list[str]],
    selected_row: pd.Series,
    config: Config,
) -> pd.DataFrame:
    feature_set = str(selected_row["feature_set"])
    candidate_id = str(selected_row["candidate_id"])
    params = next(x for x in candidate_grid() if x["candidate_id"] == candidate_id)
    features = [c for c in feature_sets[feature_set] if c in matrix.columns]

    development_dates = sorted(cv_dates["event_date"].unique())
    train = matrix.loc[matrix["event_date"].isin(development_dates)].copy()
    eligibility_col = {
        "weather_only": "eligible_weather_only",
        "market_only": "eligible_market_only",
        "combined": "eligible_combined",
        "combined_no_book": "eligible_combined",
    }.get(feature_set)
    if eligibility_col in train.columns:
        train = train.loc[train[eligibility_col].astype(bool)].copy()

    categorical = identify_categorical_features(train, features)
    X = prepare_features(train, features, categorical)
    y = train["target_Y_event"].astype(int)

    model = CatBoostClassifier(
        loss_function="Logloss",
        depth=int(params["depth"]),
        learning_rate=float(params["learning_rate"]),
        l2_leaf_reg=float(params["l2_leaf_reg"]),
        iterations=int(params["iterations"]),
        random_seed=config.random_seed,
        random_strength=0.5,
        border_count=64,
        verbose=False,
        allow_writing_files=False,
        thread_count=-1,
    )
    model.fit(X, y, cat_features=categorical, verbose=False)
    importance = pd.DataFrame(
        {
            "feature": features,
            "importance": model.get_feature_importance(),
            "is_categorical": [f in categorical for f in features],
        }
    ).sort_values("importance", ascending=False)
    importance["feature_set"] = feature_set
    importance["candidate_id"] = candidate_id
    return importance


def integrity_checks(
    matrix: pd.DataFrame,
    partitions: pd.DataFrame,
    cv_dates: pd.DataFrame,
    oof: pd.DataFrame,
    ranking: pd.DataFrame,
    benchmark_panel_df: pd.DataFrame,
    resolved_benchmark_columns: dict[str, str],
    expected_benchmarks: list[str],
) -> pd.DataFrame:
    checks = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    holdout_dates = set(
        partitions.loc[
            partitions["sample_partition"] == "final_holdout",
            "event_date",
        ]
    )
    development_dates = set(
        partitions.loc[
            partitions["sample_partition"] == "development",
            "event_date",
        ]
    )

    add("matrix_nonempty", len(matrix) > 0, f"rows={len(matrix)}")
    add("oof_nonempty", len(oof) > 0, f"rows={len(oof)}")
    add(
        "final_holdout_absent_from_oof",
        not holdout_dates & set(oof["event_date"]),
        f"holdout_overlap={len(holdout_dates & set(oof['event_date']))}",
    )
    add(
        "oof_dates_subset_of_development",
        set(oof["event_date"]).issubset(development_dates),
        f"oof_dates={oof['event_date'].nunique()}",
    )
    add(
        "oof_probabilities_present",
        oof["p_catboost_oof"].notna().all(),
        f"missing={int(oof['p_catboost_oof'].isna().sum())}",
    )
    add(
        "oof_probabilities_in_unit_interval",
        oof["p_catboost_oof"].between(0, 1).all(),
        "checked selected probabilities",
    )
    key = [
        c for c in [
            "feature_set",
            "candidate_id",
            "cv_fold",
            "event_date",
            "decision_rule",
            "token_id",
            "market_slug",
        ] if c in oof.columns
    ]
    add(
        "oof_keys_unique",
        not oof.duplicated(key).any(),
        f"duplicates={int(oof.duplicated(key).sum())}",
    )
    add(
        "binary_target_valid",
        oof["target_Y_event"].isin([0, 1]).all(),
        f"bad={int((~oof['target_Y_event'].isin([0,1])).sum())}",
    )
    add(
        "ranking_nonempty",
        len(ranking) > 0,
        f"rows={len(ranking)}",
    )
    add(
        "exactly_one_selected_specification",
        int(ranking["selected"].sum()) == 1,
        f"selected={int(ranking['selected'].sum())}",
    )
    add(
        "benchmark_panel_nonempty",
        len(benchmark_panel_df) > 0,
        f"rows={len(benchmark_panel_df)}",
    )
    observed_benchmarks = set(benchmark_panel_df["model"]) - {"catboost_selected"}
    missing_benchmarks = sorted(set(expected_benchmarks) - observed_benchmarks)
    add(
        "all_expected_direct_benchmarks_present",
        len(missing_benchmarks) == 0,
        "missing=" + ("|".join(missing_benchmarks) if missing_benchmarks else "none"),
    )
    add(
        "resolved_benchmark_columns_recorded",
        all(name in resolved_benchmark_columns for name in expected_benchmarks),
        json.dumps(resolved_benchmark_columns, sort_keys=True),
    )
    add(
        "holdout_never_scored",
        not holdout_dates & set(benchmark_panel_df["event_date"]),
        "final holdout remains sealed",
    )
    add(
        "cv_train_precedes_validation",
        all(
            pd.to_datetime(g.loc[g["cv_role"] == "train", "event_date"]).max()
            <
            pd.to_datetime(g.loc[g["cv_role"] == "validation", "event_date"]).min()
            for _, g in cv_dates.groupby("cv_fold")
        ),
        "all folds chronological",
    )
    return pd.DataFrame(checks)


def make_figures(
    ranking: pd.DataFrame,
    benchmark_summary: pd.DataFrame,
    comparisons: pd.DataFrame,
    importance: pd.DataFrame,
    figure_dir: Path,
) -> list[Path]:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    plot = ranking.sort_values("mean_date_brier").copy()
    labels = plot["feature_set"] + "\n" + plot["candidate_id"]
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(np.arange(len(plot)), plot["mean_date_brier"])
    ax.set_xticks(np.arange(len(plot)), labels, rotation=45, ha="right")
    ax.set_ylabel("Mean date-level Brier score")
    ax.set_title("20c out-of-fold CatBoost specification ranking")
    fig.tight_layout()
    p = figure_dir / "20c_oof_specification_brier_ranking.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    plot = benchmark_summary.sort_values("mean_brier").copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(plot["model"], plot["mean_brier"])
    ax.set_ylabel("Mean contract-level Brier score")
    ax.set_title("Selected CatBoost versus development-set probability benchmarks")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = figure_dir / "20c_selected_model_vs_benchmarks_brier.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    plot = benchmark_summary.sort_values("mean_log_score").copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(plot["model"], plot["mean_log_score"])
    ax.set_ylabel("Mean contract-level log score")
    ax.set_title("Selected CatBoost versus development-set probability benchmarks")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = figure_dir / "20c_selected_model_vs_benchmarks_log.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    top = importance.head(20).sort_values("importance")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(top["feature"], top["importance"])
    ax.set_xlabel("CatBoost feature importance")
    ax.set_title("Selected specification: top 20 development-set feature importances")
    fig.tight_layout()
    p = figure_dir / "20c_selected_model_feature_importance_top20.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    if not comparisons.empty:
        log_comp = comparisons.loc[comparisons["metric"] == "log_score"].copy()
        x = np.arange(len(log_comp))
        means = log_comp["mean_difference_a_minus_b"].to_numpy()
        lower = means - log_comp["bootstrap_ci_2_5"].to_numpy()
        upper = log_comp["bootstrap_ci_97_5"].to_numpy() - means
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.errorbar(x, means, yerr=[lower, upper], fmt="o", capsize=5)
        ax.axhline(0, linestyle="--", linewidth=1)
        labels = [
            f"CatBoost − {m.replace('_', ' ')}"
            for m in log_comp["model_b"]
        ]
        ax.set_xticks(x, labels, rotation=30, ha="right")
        ax.set_ylabel("Paired date-level log-score difference")
        ax.set_title("Date-clustered bootstrap comparisons on development OOF dates")
        fig.tight_layout()
        p = figure_dir / "20c_paired_log_score_bootstrap.png"
        fig.savefig(p, dpi=180)
        plt.close(fig)
        outputs.append(p)

    return outputs


def write_report(
    ranking: pd.DataFrame,
    selected: pd.Series,
    benchmark_summary: pd.DataFrame,
    comparisons: pd.DataFrame,
    checks: pd.DataFrame,
    report_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 20c compact CatBoost post-processing, corrected benchmark comparison",
        "",
        "## Purpose",
        "",
        "This step compares compact CatBoost probability models using the frozen 20b expanding-window folds. "
        "The final chronological holdout remains sealed.",
        "",
        "## Best CatBoost development-set specification",
        "",
        f"- Feature set: `{selected['feature_set']}`",
        f"- Candidate: `{selected['candidate_id']}`",
        f"- Mean date-level Brier: `{selected['mean_date_brier']:.8f}`",
        f"- Mean date-level log score: `{selected['mean_date_log_score']:.8f}`",
        "",
        "Selection rule: lowest mean date-level Brier score, followed by mean date-level log score, "
        "then contract-level Brier and log score as deterministic tie-breakers.",
        "",
        "## Full specification ranking",
        "",
        ranking.to_markdown(index=False),
        "",
        "## Best CatBoost specification versus direct probability benchmarks",
        "",
        benchmark_summary.to_markdown(index=False),
        "",
        "## Paired date-clustered bootstrap comparisons",
        "",
        comparisons.to_markdown(index=False),
        "",
        "A negative CatBoost-minus-benchmark difference favours CatBoost because lower proper scores are better.",
        "",
        (
            "**Overall benchmark conclusion:** the best CatBoost specification has the lowest direct-benchmark "
            "Brier and log scores."
            if (
                benchmark_summary.sort_values(["mean_brier", "mean_log_score"]).iloc[0]["model"]
                == "catboost_selected"
            )
            else
            "**Overall benchmark conclusion:** at least one direct probability benchmark outperforms the "
            "best CatBoost specification on the development out-of-fold sample."
        ),
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Methodological status",
        "",
        "The selected specification is the best model only within the pre-declared CatBoost candidate set. "
        "It is not described as the best overall probability forecast unless it also beats every direct probability benchmark. "
        "The 20c probabilities are out-of-fold development predictions. They are not yet probability-calibrated "
        "and are not yet forced to satisfy daily event-book coherence. Both tasks are deferred to 20d. "
        "The final holdout must remain untouched until the 20d procedure is frozen.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def serialise_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out


def zip_review(paths: Iterable[Path], repo: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if path.exists():
                zf.write(path, arcname=str(path.relative_to(repo)))


def main() -> int:
    warnings.filterwarnings("ignore", category=FutureWarning)
    config = parse_args()
    repo = config.repo_root
    processed = repo / "data" / "processed"
    docs = repo / "docs" / "research_outputs"
    figures = repo / "figures" / "20c_catboost_postprocessing"

    matrix, feature_sets, cv_dates, partitions = load_inputs(repo)

    development_dates = set(
        partitions.loc[
            partitions["sample_partition"] == "development",
            "event_date",
        ]
    )
    matrix_development = matrix.loc[matrix["event_date"].isin(development_dates)].copy()

    oof, fit_inventory = make_oof_predictions(
        matrix_development,
        feature_sets,
        cv_dates,
        config,
    )
    row_summary, date_level, ranking = summarise_oof(oof)
    selected = ranking.loc[ranking["selected"]].iloc[0]

    oof = oof.merge(
        ranking[
            ["feature_set", "candidate_id", "selected", "overall_rank"]
        ],
        on=["feature_set", "candidate_id"],
        how="left",
        validate="many_to_one",
    )
    oof["selected_model"] = oof["selected"].astype(bool)

    benchmark_panel_df, resolved_benchmark_columns, expected_benchmarks = benchmark_panel(oof)
    benchmark_summary, benchmark_date_panel, comparisons = (
        benchmark_summary_and_comparisons(benchmark_panel_df, config)
    )
    importance = feature_importance_for_selected(
        matrix_development,
        cv_dates,
        feature_sets,
        selected,
        config,
    )

    checks = integrity_checks(
        matrix,
        partitions,
        cv_dates,
        oof,
        ranking,
        benchmark_panel_df,
        resolved_benchmark_columns,
        expected_benchmarks,
    )
    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    selected_manifest = {
        "step": STEP,
        "selection_scope": "development_oof_only",
        "final_holdout_evaluated": False,
        "feature_set": str(selected["feature_set"]),
        "candidate_id": str(selected["candidate_id"]),
        "selection_metric_primary": "mean_date_brier",
        "selection_metric_secondary": "mean_date_log_score",
        "mean_date_brier": float(selected["mean_date_brier"]),
        "mean_date_log_score": float(selected["mean_date_log_score"]),
        "hyperparameters": next(
            x for x in candidate_grid()
            if x["candidate_id"] == str(selected["candidate_id"])
        ),
        "requires_20d_calibration": True,
        "requires_20d_event_book_coherence": True,
        "model_label": "best_catboost_specification",
        "resolved_probability_columns": resolved_benchmark_columns,
        "expected_direct_benchmarks": expected_benchmarks,
        "all_expected_direct_benchmarks_present": (
            set(expected_benchmarks)
            .issubset(set(benchmark_panel_df["model"]))
        ),
        "catboost_is_best_overall_probability_model": bool(
            benchmark_summary.sort_values(
                ["mean_brier", "mean_log_score"]
            ).iloc[0]["model"] == "catboost_selected"
        ),
    }

    outputs = {
        "oof": processed / "20c_catboost_oof_probability_panel.csv",
        "fit_inventory": processed / "20c_catboost_fit_inventory.csv",
        "row_summary": processed / "20c_oof_row_score_summary.csv",
        "date_panel": processed / "20c_oof_date_level_score_panel.csv",
        "ranking": processed / "20c_model_specification_ranking.csv",
        "benchmark_panel": processed / "20c_selected_model_benchmark_panel.csv",
        "benchmark_summary": processed / "20c_selected_model_benchmark_summary.csv",
        "benchmark_date_panel": processed / "20c_selected_model_benchmark_date_panel.csv",
        "comparisons": processed / "20c_paired_date_level_comparisons.csv",
        "importance": processed / "20c_selected_model_feature_importance.csv",
        "checks": processed / "20c_integrity_checks.csv",
        "issues": processed / "20c_issues.csv",
        "manifest": processed / "20c_selected_model_manifest.json",
        "report": docs / "20c_catboost_postprocessing_report.md",
    }

    serialise_dates(oof).to_csv(outputs["oof"], index=False)
    fit_inventory.to_csv(outputs["fit_inventory"], index=False)
    row_summary.to_csv(outputs["row_summary"], index=False)
    serialise_dates(date_level).to_csv(outputs["date_panel"], index=False)
    ranking.to_csv(outputs["ranking"], index=False)
    serialise_dates(benchmark_panel_df).to_csv(outputs["benchmark_panel"], index=False)
    benchmark_summary.to_csv(outputs["benchmark_summary"], index=False)
    serialise_dates(benchmark_date_panel).to_csv(outputs["benchmark_date_panel"], index=False)
    comparisons.to_csv(outputs["comparisons"], index=False)
    importance.to_csv(outputs["importance"], index=False)
    checks.to_csv(outputs["checks"], index=False)
    issues.to_csv(outputs["issues"], index=False)
    outputs["manifest"].write_text(
        json.dumps(selected_manifest, indent=2),
        encoding="utf-8",
    )

    figure_paths = make_figures(
        ranking,
        benchmark_summary,
        comparisons,
        importance,
        figures,
    )
    write_report(
        ranking,
        selected,
        benchmark_summary,
        comparisons,
        checks,
        outputs["report"],
    )

    review_zip = repo / "data" / "review_bundles" / "20c_review_bundle.zip"
    zip_review(list(outputs.values()) + figure_paths, repo, review_zip)

    print("20c completed.")
    print(f"Development rows: {len(matrix_development)}")
    print(f"OOF rows across all specifications: {len(oof)}")
    print(f"Selected feature set: {selected['feature_set']}")
    print(f"Selected candidate: {selected['candidate_id']}")
    print(f"Selected mean date Brier: {selected['mean_date_brier']:.8f}")
    print(f"Selected mean date log: {selected['mean_date_log_score']:.8f}")
    print(f"Passed checks: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more integrity checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
