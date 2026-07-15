#!/usr/bin/env python3
"""
20e: Single locked final chronological holdout evaluation.

This step performs the first and only evaluation on the frozen 20b final holdout.

Frozen inputs:
- best CatBoost specification selected in 20c;
- robust Platt calibration selected in 20d;
- 20b development/holdout date split;
- 20a supervised feature matrix.

Procedure:
1. Fit the frozen CatBoost specification on all development rows.
2. Generate raw CatBoost probabilities for the final holdout.
3. Fit a Platt calibrator on development OOF CatBoost probabilities only.
4. Apply that calibrator to final-holdout CatBoost probabilities.
5. Compare against market, raw ECMWF, fixed-sigma corrected ECMWF, and
   adaptive-sigma corrected ECMWF on exact common support.
6. Compute binary scores, date-clustered paired differences, and event-book
   categorical diagnostics.
7. Do not change any feature set, hyperparameter, calibration rule, or split
   after observing holdout results.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

try:
    from catboost import CatBoostClassifier
except Exception as exc:
    raise SystemExit(
        "CatBoost is required. Install with:\n"
        "python -m pip install catboost\n"
        f"Original import error: {exc}"
    )

EPS = 1e-6


@dataclass(frozen=True)
class Config:
    repo_root: Path
    bootstrap_reps: int
    random_seed: int


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--bootstrap-reps", type=int, default=10000)
    parser.add_argument("--random-seed", type=int, default=20260715)
    args = parser.parse_args()
    if args.bootstrap_reps < 1000:
        raise ValueError("--bootstrap-reps must be at least 1000.")
    return Config(
        repo_root=args.repo_root.expanduser().resolve(),
        bootstrap_reps=int(args.bootstrap_reps),
        random_seed=int(args.random_seed),
    )


def brier_score(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return (np.asarray(p, float) - np.asarray(y, float)) ** 2


def safe_log_score(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def load_inputs(repo: Path):
    p = repo / "data" / "processed"
    required = [
        p / "20a_supervised_feature_matrix.csv",
        p / "20a_model_feature_sets.json",
        p / "20b_date_partition_assignments.csv",
        p / "20c_selected_model_manifest.json",
        p / "20c_catboost_oof_probability_panel.csv",
        p / "20d_calibration_coherence_manifest.json",
        p / "20d_selected_calibrated_probability_panel.csv",
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"Missing required input: {path}")

    matrix = pd.read_csv(required[0], low_memory=False)
    matrix["event_date"] = pd.to_datetime(matrix["event_date"]).dt.normalize()
    feature_sets = json.loads(required[1].read_text())
    partitions = pd.read_csv(required[2])
    partitions["event_date"] = pd.to_datetime(partitions["event_date"]).dt.normalize()
    manifest_20c = json.loads(required[3].read_text())
    oof = pd.read_csv(required[4], low_memory=False)
    oof["event_date"] = pd.to_datetime(oof["event_date"]).dt.normalize()
    manifest_20d = json.loads(required[5].read_text())
    calibrated_oof = pd.read_csv(required[6], low_memory=False)
    calibrated_oof["event_date"] = pd.to_datetime(calibrated_oof["event_date"]).dt.normalize()

    return matrix, feature_sets, partitions, manifest_20c, oof, manifest_20d, calibrated_oof


def identify_categorical_features(df: pd.DataFrame, features: list[str]) -> list[str]:
    out = []
    for col in features:
        if (
            pd.api.types.is_object_dtype(df[col])
            or pd.api.types.is_string_dtype(df[col])
            or pd.api.types.is_bool_dtype(df[col])
            or pd.api.types.is_categorical_dtype(df[col])
        ):
            out.append(col)
    return out


def prepare_features(df: pd.DataFrame, features: list[str], categorical: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    for col in categorical:
        X[col] = X[col].astype("string").fillna("__MISSING__").astype(str)
    for col in features:
        if col not in categorical:
            X[col] = pd.to_numeric(X[col], errors="coerce")
    return X


def fit_frozen_catboost(
    development: pd.DataFrame,
    holdout: pd.DataFrame,
    features: list[str],
    hyperparameters: dict[str, Any],
    seed: int,
) -> tuple[np.ndarray, list[str]]:
    categorical = identify_categorical_features(development, features)
    X_train = prepare_features(development, features, categorical)
    X_holdout = prepare_features(holdout, features, categorical)
    y_train = development["target_Y_event"].astype(int)

    model = CatBoostClassifier(
        loss_function="Logloss",
        eval_metric="Logloss",
        depth=int(hyperparameters["depth"]),
        learning_rate=float(hyperparameters["learning_rate"]),
        l2_leaf_reg=float(hyperparameters["l2_leaf_reg"]),
        iterations=int(hyperparameters["iterations"]),
        random_seed=seed,
        random_strength=0.5,
        border_count=64,
        auto_class_weights=None,
        verbose=False,
        allow_writing_files=False,
        thread_count=-1,
    )
    model.fit(X_train, y_train, cat_features=categorical, verbose=False)
    p = model.predict_proba(X_holdout)[:, 1]
    return np.clip(p, EPS, 1 - EPS), categorical


def fit_platt_on_development_oof(
    selected_oof: pd.DataFrame,
    holdout_raw_p: np.ndarray,
) -> tuple[np.ndarray, dict]:
    train = selected_oof.copy()
    train = train.loc[
        train["p_catboost_oof"].notna() & train["target_Y_event"].notna()
    ].copy()
    x = logit(train["p_catboost_oof"].to_numpy(float)).reshape(-1, 1)
    y = train["target_Y_event"].astype(int).to_numpy()

    model = LogisticRegression(
        C=1.0,
        solver="lbfgs",
        max_iter=2000,
        random_state=0,
    )
    model.fit(x, y)
    pred = model.predict_proba(logit(holdout_raw_p).reshape(-1, 1))[:, 1]
    inventory = {
        "n_platt_training_rows": int(len(train)),
        "n_platt_training_dates": int(train["event_date"].nunique()),
        "platt_intercept": float(model.intercept_[0]),
        "platt_slope": float(model.coef_[0, 0]),
    }
    return np.clip(pred, EPS, 1 - EPS), inventory


def resolve_probability_columns(matrix: pd.DataFrame, manifest_20c: dict) -> dict[str, str]:
    mapping = dict(manifest_20c.get("resolved_probability_columns", {}))
    expected = {
        "market",
        "ecmwf_raw",
        "ecmwf_bias_fixed_sigma",
        "ecmwf_bias_adaptive_sigma",
    }
    missing = expected - set(mapping)
    if missing:
        raise ValueError(f"20c manifest lacks probability mappings: {sorted(missing)}")
    unavailable = {k: v for k, v in mapping.items() if v not in matrix.columns}
    if unavailable:
        raise ValueError(f"Mapped probability columns absent from 20a matrix: {unavailable}")
    return mapping


def create_holdout_prediction_panel(
    holdout: pd.DataFrame,
    p_raw: np.ndarray,
    p_calibrated: np.ndarray,
    probability_mapping: dict[str, str],
) -> pd.DataFrame:
    keep = [
        c for c in [
            "event_date", "date_group_id", "decision_rule", "market_slug",
            "condition_id", "token_id", "contract_event_type_v2",
            "target_Y_event", "eligible_combined",
        ] if c in holdout.columns
    ]
    out = holdout[keep].copy()
    out["p_catboost_raw_holdout"] = p_raw
    out["p_catboost_platt_holdout"] = p_calibrated
    for model, col in probability_mapping.items():
        out[f"p_{model}"] = pd.to_numeric(holdout[col], errors="coerce").to_numpy()
    return out


def long_model_panel(panel: pd.DataFrame) -> pd.DataFrame:
    id_cols = [
        c for c in [
            "event_date", "date_group_id", "decision_rule", "market_slug",
            "condition_id", "token_id", "contract_event_type_v2",
            "target_Y_event",
        ] if c in panel.columns
    ]
    model_cols = {
        "catboost_raw": "p_catboost_raw_holdout",
        "catboost_platt": "p_catboost_platt_holdout",
        "market": "p_market",
        "ecmwf_raw": "p_ecmwf_raw",
        "ecmwf_bias_fixed_sigma": "p_ecmwf_bias_fixed_sigma",
        "ecmwf_bias_adaptive_sigma": "p_ecmwf_bias_adaptive_sigma",
    }
    rows = []
    for model, col in model_cols.items():
        tmp = panel[id_cols].copy()
        tmp["model"] = model
        tmp["probability"] = pd.to_numeric(panel[col], errors="coerce")
        tmp = tmp.loc[tmp["probability"].notna()].copy()
        tmp["brier"] = brier_score(
            tmp["target_Y_event"].to_numpy(int),
            tmp["probability"].to_numpy(float),
        )
        tmp["log_score"] = safe_log_score(
            tmp["target_Y_event"].to_numpy(int),
            tmp["probability"].to_numpy(float),
        )
        rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


def exact_common_support(long_panel: pd.DataFrame) -> pd.DataFrame:
    key = [
        c for c in [
            "event_date", "decision_rule", "token_id", "market_slug", "condition_id"
        ] if c in long_panel.columns
    ]
    n_models = long_panel["model"].nunique()
    counts = long_panel.groupby(key)["model"].nunique()
    valid = counts[counts == n_models].index
    indexed = long_panel.set_index(key)
    return indexed.loc[indexed.index.isin(valid)].reset_index()


def binary_summary(common: pd.DataFrame) -> pd.DataFrame:
    return (
        common.groupby("model", as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_dates=("event_date", "nunique"),
            outcome_rate=("target_Y_event", "mean"),
            mean_brier=("brier", "mean"),
            mean_log_score=("log_score", "mean"),
        )
        .sort_values(["mean_brier", "mean_log_score"])
    )


def paired_date_bootstrap(
    common: pd.DataFrame,
    model_a: str,
    model_b: str,
    metric: str,
    reps: int,
    seed: int,
) -> dict:
    scores = (
        common.loc[common["model"].isin([model_a, model_b])]
        .groupby(["event_date", "model"], as_index=False)[metric]
        .mean()
        .pivot(index="event_date", columns="model", values=metric)
        .dropna(subset=[model_a, model_b])
    )
    diff = (scores[model_a] - scores[model_b]).to_numpy(float)
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
    }


def make_paired_comparisons(common: pd.DataFrame, config: Config) -> pd.DataFrame:
    rows = []
    benchmarks = sorted(set(common["model"]) - {"catboost_platt"})
    for i, benchmark in enumerate(benchmarks):
        for j, metric in enumerate(["brier", "log_score"]):
            rows.append(
                paired_date_bootstrap(
                    common,
                    "catboost_platt",
                    benchmark,
                    metric,
                    config.bootstrap_reps,
                    config.random_seed + 100 * i + j,
                )
            )
    return pd.DataFrame(rows)


def build_book_panel(common: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_key = ["model", "event_date", "decision_rule"]
    for (model, event_date, decision_rule), book in common.groupby(group_key):
        b = book.copy()
        p = b["probability"].to_numpy(float)
        total = float(p.sum())
        n_winners = int(b["target_Y_event"].sum())
        complete = bool(total > 0 and n_winners == 1)
        b["book_probability_sum"] = total
        b["book_abs_probability_error"] = abs(total - 1)
        b["book_n_contracts"] = len(b)
        b["book_n_winners"] = n_winners
        b["book_complete_for_scoring"] = complete
        if complete:
            q = np.clip(p / total, EPS, 1 - EPS)
            y = b["target_Y_event"].to_numpy(int)
            b["book_normalised_probability"] = q
            b["categorical_log_component"] = np.where(y == 1, -np.log(q), 0.0)
            b["multiclass_brier_component"] = (q - y) ** 2
        else:
            b["book_normalised_probability"] = np.nan
            b["categorical_log_component"] = np.nan
            b["multiclass_brier_component"] = np.nan
        rows.append(b)
    return pd.concat(rows, ignore_index=True)


def book_summaries(book_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = (
        book_panel.groupby(["model", "event_date", "decision_rule"], as_index=False)
        .agg(
            n_contracts=("book_n_contracts", "first"),
            n_winners=("book_n_winners", "first"),
            raw_probability_sum=("book_probability_sum", "first"),
            abs_probability_error=("book_abs_probability_error", "first"),
            complete_for_scoring=("book_complete_for_scoring", "first"),
            normalised_categorical_log_score=("categorical_log_component", "sum"),
            normalised_multiclass_brier=("multiclass_brier_component", "sum"),
        )
    )
    scored = metrics.loc[metrics["complete_for_scoring"].astype(bool)].copy()
    summary = (
        scored.groupby("model", as_index=False)
        .agg(
            n_books=("event_date", "size"),
            mean_abs_book_probability_error=("abs_probability_error", "mean"),
            median_abs_book_probability_error=("abs_probability_error", "median"),
            mean_normalised_categorical_log_score=(
                "normalised_categorical_log_score", "mean"
            ),
            mean_normalised_multiclass_brier=(
                "normalised_multiclass_brier", "mean"
            ),
        )
        .sort_values(
            ["mean_normalised_categorical_log_score", "mean_normalised_multiclass_brier"]
        )
    )
    return metrics, summary


def integrity_checks(
    matrix: pd.DataFrame,
    development: pd.DataFrame,
    holdout: pd.DataFrame,
    selected_oof: pd.DataFrame,
    manifest_20c: dict,
    manifest_20d: dict,
    prediction_panel: pd.DataFrame,
    common: pd.DataFrame,
    book_panel: pd.DataFrame,
) -> pd.DataFrame:
    checks = []

    def add(name: str, passed: bool, detail: str):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    add("matrix_nonempty", len(matrix) > 0, f"rows={len(matrix)}")
    add("development_nonempty", len(development) > 0, f"rows={len(development)}")
    add("holdout_nonempty", len(holdout) > 0, f"rows={len(holdout)}")
    add(
        "development_precedes_holdout",
        development["event_date"].max() < holdout["event_date"].min(),
        f"development_end={development['event_date'].max().date()}, holdout_start={holdout['event_date'].min().date()}",
    )
    add(
        "holdout_dates_exactly_frozen",
        holdout["event_date"].nunique() == 10,
        f"dates={holdout['event_date'].nunique()}",
    )
    add(
        "frozen_catboost_manifest_used",
        manifest_20c.get("candidate_id") is not None
        and manifest_20c.get("feature_set") is not None,
        f"feature_set={manifest_20c.get('feature_set')}, candidate={manifest_20c.get('candidate_id')}",
    )
    add(
        "frozen_platt_calibration_used",
        manifest_20d.get("selected_calibration_method") == "platt",
        f"method={manifest_20d.get('selected_calibration_method')}",
    )
    add(
        "platt_fit_uses_development_oof_only",
        not set(selected_oof["event_date"]) & set(holdout["event_date"]),
        f"oof_dates={selected_oof['event_date'].nunique()}",
    )
    add(
        "holdout_predictions_present",
        prediction_panel["p_catboost_platt_holdout"].notna().all(),
        f"missing={int(prediction_panel['p_catboost_platt_holdout'].isna().sum())}",
    )
    add(
        "holdout_probabilities_in_unit_interval",
        prediction_panel.filter(regex=r"^p_").apply(
            lambda s: pd.to_numeric(s, errors="coerce").dropna().between(0, 1).all()
        ).all(),
        "checked all probability columns",
    )
    add(
        "common_support_nonempty",
        len(common) > 0,
        f"rows={len(common)}, models={common['model'].nunique()}",
    )
    key = [
        c for c in ["model", "event_date", "decision_rule", "token_id", "market_slug"]
        if c in common.columns
    ]
    add(
        "common_support_keys_unique",
        not common.duplicated(key).any(),
        f"duplicates={int(common.duplicated(key).sum())}",
    )
    add(
        "all_models_same_common_support",
        common.groupby("model").size().nunique() == 1,
        common.groupby("model").size().to_dict().__str__(),
    )
    scored = book_panel.loc[book_panel["book_complete_for_scoring"].astype(bool)]
    add(
        "scored_books_have_one_winner",
        (
            scored.groupby(["model", "event_date", "decision_rule"])["target_Y_event"].sum()
            == 1
        ).all(),
        f"books={scored.groupby(['model','event_date','decision_rule']).ngroups}",
    )
    add(
        "normalised_books_sum_to_one",
        np.allclose(
            scored.groupby(["model", "event_date", "decision_rule"])[
                "book_normalised_probability"
            ].sum(),
            1.0,
            atol=1e-8,
        ),
        "checked",
    )
    add(
        "single_locked_holdout_evaluation",
        True,
        "20e is designated as the one locked final evaluation",
    )
    return pd.DataFrame(checks)


def make_figures(
    binary: pd.DataFrame,
    comparisons: pd.DataFrame,
    book_summary: pd.DataFrame,
    figure_dir: Path,
) -> list[Path]:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    plot = binary.sort_values("mean_brier")
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(plot["model"], plot["mean_brier"])
    ax.set_ylabel("Mean holdout Brier score")
    ax.set_title("Locked final-holdout binary Brier comparison")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = figure_dir / "20e_holdout_brier_comparison.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    plot = binary.sort_values("mean_log_score")
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(plot["model"], plot["mean_log_score"])
    ax.set_ylabel("Mean holdout log score")
    ax.set_title("Locked final-holdout binary log-score comparison")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = figure_dir / "20e_holdout_log_score_comparison.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    plot = book_summary.sort_values("mean_normalised_categorical_log_score")
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(plot["model"], plot["mean_normalised_categorical_log_score"])
    ax.set_ylabel("Mean categorical log score")
    ax.set_title("Locked holdout event-book categorical comparison")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = figure_dir / "20e_holdout_categorical_log_comparison.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    log_comp = comparisons.loc[comparisons["metric"] == "log_score"].copy()
    if not log_comp.empty:
        means = log_comp["mean_difference_a_minus_b"].to_numpy()
        lower = means - log_comp["bootstrap_ci_2_5"].to_numpy()
        upper = log_comp["bootstrap_ci_97_5"].to_numpy() - means
        fig, ax = plt.subplots(figsize=(11, 5))
        x = np.arange(len(log_comp))
        ax.errorbar(x, means, yerr=[lower, upper], fmt="o", capsize=5)
        ax.axhline(0, linestyle="--", linewidth=1)
        ax.set_xticks(
            x,
            [f"Platt CatBoost − {x}" for x in log_comp["model_b"]],
            rotation=30,
            ha="right",
        )
        ax.set_ylabel("Date-level log-score difference")
        ax.set_title("Locked holdout paired date bootstrap")
        fig.tight_layout()
        p = figure_dir / "20e_holdout_paired_log_score_bootstrap.png"
        fig.savefig(p, dpi=180)
        plt.close(fig)
        outputs.append(p)

    return outputs


def write_report(
    manifest: dict,
    binary: pd.DataFrame,
    comparisons: pd.DataFrame,
    book_summary: pd.DataFrame,
    checks: pd.DataFrame,
    report_path: Path,
):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 20e single locked final chronological holdout evaluation",
        "",
        "## Status",
        "",
        "This is the designated first and only evaluation on the frozen final holdout. "
        "No specification, feature, hyperparameter, calibration, or split may be changed in response to these results.",
        "",
        "## Frozen procedure",
        "",
        f"- CatBoost feature set: `{manifest['feature_set']}`",
        f"- CatBoost candidate: `{manifest['candidate_id']}`",
        f"- Calibration: `{manifest['calibration_method']}`",
        f"- Development end: `{manifest['development_end_date']}`",
        f"- Holdout start: `{manifest['holdout_start_date']}`",
        f"- Holdout end: `{manifest['holdout_end_date']}`",
        "",
        "## Exact common-support binary scores",
        "",
        binary.to_markdown(index=False),
        "",
        "## Paired date-level bootstrap comparisons",
        "",
        comparisons.to_markdown(index=False),
        "",
        "Negative Platt-CatBoost-minus-benchmark differences favour Platt-calibrated CatBoost.",
        "",
        "## Event-book coherence and categorical scores",
        "",
        book_summary.to_markdown(index=False),
        "",
        "Binary scores use raw contract probabilities. Categorical scores use probabilities normalised within each complete event book.",
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Interpretation rule",
        "",
        "These holdout results are confirmatory. Subsequent robustness analysis may vary assumptions transparently, "
        "but must not retroactively redefine the primary model or primary holdout result.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def serialise_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out


def zip_review(paths: Iterable[Path], repo: Path, output: Path):
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
    figures = repo / "figures" / "20e_locked_holdout"

    (
        matrix,
        feature_sets,
        partitions,
        manifest_20c,
        oof,
        manifest_20d,
        calibrated_oof,
    ) = load_inputs(repo)

    dev_dates = set(
        partitions.loc[partitions["sample_partition"] == "development", "event_date"]
    )
    holdout_dates = set(
        partitions.loc[partitions["sample_partition"] == "final_holdout", "event_date"]
    )
    development = matrix.loc[matrix["event_date"].isin(dev_dates)].copy()
    holdout = matrix.loc[matrix["event_date"].isin(holdout_dates)].copy()

    feature_set = manifest_20c["feature_set"]
    candidate_id = manifest_20c["candidate_id"]
    hyperparameters = manifest_20c["hyperparameters"]
    features = [c for c in feature_sets[feature_set] if c in matrix.columns]

    eligibility_col = {
        "weather_only": "eligible_weather_only",
        "market_only": "eligible_market_only",
        "combined": "eligible_combined",
        "combined_no_book": "eligible_combined",
    }.get(feature_set)
    if eligibility_col in matrix.columns:
        development = development.loc[development[eligibility_col].astype(bool)].copy()
        holdout = holdout.loc[holdout[eligibility_col].astype(bool)].copy()

    p_raw, categorical = fit_frozen_catboost(
        development,
        holdout,
        features,
        hyperparameters,
        config.random_seed,
    )

    selected_oof = oof.loc[oof["selected_model"].astype(bool)].copy()
    p_platt, platt_inventory = fit_platt_on_development_oof(selected_oof, p_raw)

    probability_mapping = resolve_probability_columns(matrix, manifest_20c)
    prediction_panel = create_holdout_prediction_panel(
        holdout,
        p_raw,
        p_platt,
        probability_mapping,
    )
    long_panel = long_model_panel(prediction_panel)
    common = exact_common_support(long_panel)
    binary = binary_summary(common)
    comparisons = make_paired_comparisons(common, config)
    book_panel = build_book_panel(common)
    book_metrics, book_summary = book_summaries(book_panel)

    checks = integrity_checks(
        matrix,
        development,
        holdout,
        selected_oof,
        manifest_20c,
        manifest_20d,
        prediction_panel,
        common,
        book_panel,
    )
    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    manifest = {
        "step": "20e",
        "evaluation_status": "single_locked_final_holdout",
        "feature_set": feature_set,
        "candidate_id": candidate_id,
        "hyperparameters": hyperparameters,
        "calibration_method": manifest_20d["selected_calibration_method"],
        "development_start_date": development["event_date"].min().strftime("%Y-%m-%d"),
        "development_end_date": development["event_date"].max().strftime("%Y-%m-%d"),
        "holdout_start_date": holdout["event_date"].min().strftime("%Y-%m-%d"),
        "holdout_end_date": holdout["event_date"].max().strftime("%Y-%m-%d"),
        "n_development_dates": int(development["event_date"].nunique()),
        "n_holdout_dates": int(holdout["event_date"].nunique()),
        "n_development_rows": int(len(development)),
        "n_holdout_rows": int(len(holdout)),
        "n_features": int(len(features)),
        "categorical_features": categorical,
        "probability_mapping": probability_mapping,
        **platt_inventory,
        "model_changes_after_holdout_forbidden": True,
    }

    outputs = {
        "prediction_panel": processed / "20e_locked_holdout_prediction_panel.csv",
        "long_panel": processed / "20e_locked_holdout_long_model_panel.csv",
        "common": processed / "20e_locked_holdout_common_support_panel.csv",
        "binary": processed / "20e_locked_holdout_binary_score_summary.csv",
        "comparisons": processed / "20e_locked_holdout_paired_date_comparisons.csv",
        "book_panel": processed / "20e_locked_holdout_event_book_probability_panel.csv",
        "book_metrics": processed / "20e_locked_holdout_event_book_metrics.csv",
        "book_summary": processed / "20e_locked_holdout_event_book_score_summary.csv",
        "checks": processed / "20e_locked_holdout_integrity_checks.csv",
        "issues": processed / "20e_locked_holdout_issues.csv",
        "manifest": processed / "20e_locked_holdout_manifest.json",
        "report": docs / "20e_locked_holdout_evaluation_report.md",
    }

    serialise_dates(prediction_panel).to_csv(outputs["prediction_panel"], index=False)
    serialise_dates(long_panel).to_csv(outputs["long_panel"], index=False)
    serialise_dates(common).to_csv(outputs["common"], index=False)
    binary.to_csv(outputs["binary"], index=False)
    comparisons.to_csv(outputs["comparisons"], index=False)
    serialise_dates(book_panel).to_csv(outputs["book_panel"], index=False)
    serialise_dates(book_metrics).to_csv(outputs["book_metrics"], index=False)
    book_summary.to_csv(outputs["book_summary"], index=False)
    checks.to_csv(outputs["checks"], index=False)
    issues.to_csv(outputs["issues"], index=False)
    outputs["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    figure_paths = make_figures(binary, comparisons, book_summary, figures)
    write_report(manifest, binary, comparisons, book_summary, checks, outputs["report"])

    review_zip = repo / "data" / "review_bundles" / "20e_review_bundle.zip"
    zip_review(list(outputs.values()) + figure_paths, repo, review_zip)

    print("20e completed.")
    print(f"Holdout dates: {holdout['event_date'].nunique()}")
    print(f"Holdout rows: {len(holdout)}")
    print(f"Exact common-support rows: {len(common)}")
    print(f"Compared models: {common['model'].nunique()}")
    print(f"Passed checks: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more 20e integrity checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
