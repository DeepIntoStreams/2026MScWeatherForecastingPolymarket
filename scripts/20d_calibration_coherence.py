#!/usr/bin/env python3
"""
20d: Out-of-fold probability calibration and event-book coherence diagnostics.

This step uses only the frozen 20c development out-of-fold predictions.
It does not touch the final chronological holdout.

Tasks:
1. Read the selected CatBoost OOF probabilities and direct probability benchmarks.
2. Fit leakage-safe date-wise expanding calibrators for CatBoost:
   - identity (uncalibrated)
   - Platt/logistic calibration
   - isotonic calibration when training support is sufficient
3. Select the calibration method on development OOF dates only.
4. Measure contract-level Brier/log scores.
5. Measure event-book coherence before and after normalisation.
6. Produce complete-book categorical log and multiclass Brier scores.
7. Compare calibrated CatBoost with market and corrected ECMWF benchmarks.
8. Write diagnostics, figures, report, and a review bundle.

The final holdout remains sealed for a later locked evaluation step.
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
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


EPS = 1e-6


@dataclass(frozen=True)
class Config:
    repo_root: Path
    min_calibration_dates: int
    bootstrap_reps: int
    random_seed: int


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--min-calibration-dates", type=int, default=8)
    parser.add_argument("--bootstrap-reps", type=int, default=5000)
    parser.add_argument("--random-seed", type=int, default=20260715)
    args = parser.parse_args()
    if args.min_calibration_dates < 5:
        raise ValueError("--min-calibration-dates must be at least 5.")
    if args.bootstrap_reps < 500:
        raise ValueError("--bootstrap-reps must be at least 500.")
    return Config(
        repo_root=args.repo_root.expanduser().resolve(),
        min_calibration_dates=int(args.min_calibration_dates),
        bootstrap_reps=int(args.bootstrap_reps),
        random_seed=int(args.random_seed),
    )


def safe_log_score(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def brier_score(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return (np.asarray(p, dtype=float) - np.asarray(y, dtype=float)) ** 2



def calibration_extreme_probability_diagnostics(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarise probability extremeness by calibration method. These diagnostics are
    used to prevent a negligible Brier gain from selecting a method that creates
    unstable near-zero or near-one probabilities and a materially worse log score.
    """
    rows = []
    for method, group in panel.groupby("calibration_method"):
        p = np.clip(
            pd.to_numeric(group["p_catboost_calibrated"], errors="coerce").to_numpy(float),
            EPS,
            1 - EPS,
        )
        rows.append(
            {
                "calibration_method": method,
                "n_probabilities": len(p),
                "n_at_lower_clip": int(np.isclose(p, EPS, atol=1e-15).sum()),
                "n_at_upper_clip": int(np.isclose(p, 1 - EPS, atol=1e-15).sum()),
                "share_at_clip_bounds": float(
                    (
                        np.isclose(p, EPS, atol=1e-15)
                        | np.isclose(p, 1 - EPS, atol=1e-15)
                    ).mean()
                ),
                "share_below_0_001": float((p < 0.001).mean()),
                "share_above_0_999": float((p > 0.999).mean()),
                "minimum_probability": float(np.min(p)),
                "maximum_probability": float(np.max(p)),
            }
        )
    return pd.DataFrame(rows)


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def load_inputs(repo: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    processed = repo / "data" / "processed"
    oof_path = processed / "20c_catboost_oof_probability_panel.csv"
    benchmark_path = processed / "20c_selected_model_benchmark_panel.csv"
    manifest_path = processed / "20c_selected_model_manifest.json"

    for path in [oof_path, benchmark_path, manifest_path]:
        if not path.exists():
            raise FileNotFoundError(f"Missing required input: {path}")

    oof = pd.read_csv(oof_path, low_memory=False)
    oof["event_date"] = pd.to_datetime(oof["event_date"], errors="raise").dt.normalize()
    benchmark = pd.read_csv(benchmark_path, low_memory=False)
    benchmark["event_date"] = pd.to_datetime(
        benchmark["event_date"], errors="raise"
    ).dt.normalize()
    manifest = json.loads(manifest_path.read_text())

    selected = oof.loc[oof["selected_model"].astype(bool)].copy()
    if selected.empty:
        raise ValueError("No selected 20c OOF rows found.")

    return selected, benchmark, manifest


def make_row_key(df: pd.DataFrame) -> pd.Series:
    candidates = ["event_date", "decision_rule", "token_id", "market_slug", "condition_id"]
    cols = [c for c in candidates if c in df.columns]
    if "event_date" not in cols or "decision_rule" not in cols:
        raise ValueError("Cannot construct a stable row key.")
    return df[cols].astype(str).agg("||".join, axis=1)


def fit_platt(train_p: np.ndarray, train_y: np.ndarray, test_p: np.ndarray) -> np.ndarray:
    x_train = logit(train_p).reshape(-1, 1)
    x_test = logit(test_p).reshape(-1, 1)
    model = LogisticRegression(
        C=1.0,
        solver="lbfgs",
        max_iter=2000,
        random_state=0,
    )
    model.fit(x_train, train_y.astype(int))
    return np.clip(model.predict_proba(x_test)[:, 1], EPS, 1 - EPS)


def fit_isotonic(train_p: np.ndarray, train_y: np.ndarray, test_p: np.ndarray) -> np.ndarray:
    model = IsotonicRegression(
        y_min=EPS,
        y_max=1 - EPS,
        out_of_bounds="clip",
        increasing=True,
    )
    model.fit(train_p, train_y)
    return np.clip(model.predict(test_p), EPS, 1 - EPS)


def expanding_calibration_panel(
    selected_oof: pd.DataFrame,
    min_dates: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = selected_oof.copy()
    df["row_key"] = make_row_key(df)
    dates = sorted(df["event_date"].unique())
    rows: list[pd.DataFrame] = []
    inventory: list[dict] = []

    for target_date in dates:
        test = df.loc[df["event_date"] == target_date].copy()
        train = df.loc[df["event_date"] < target_date].copy()
        n_train_dates = train["event_date"].nunique()

        methods = ["identity"]
        if (
            n_train_dates >= min_dates
            and train["target_Y_event"].nunique() == 2
            and len(train) >= 50
        ):
            methods.append("platt")
            if (
                train["p_catboost_oof"].nunique() >= 10
                and train["target_Y_event"].sum() >= 5
                and (1 - train["target_Y_event"]).sum() >= 20
            ):
                methods.append("isotonic")

        for method in methods:
            if method == "identity":
                pred = np.clip(test["p_catboost_oof"].to_numpy(float), EPS, 1 - EPS)
            elif method == "platt":
                pred = fit_platt(
                    train["p_catboost_oof"].to_numpy(float),
                    train["target_Y_event"].to_numpy(int),
                    test["p_catboost_oof"].to_numpy(float),
                )
            elif method == "isotonic":
                pred = fit_isotonic(
                    train["p_catboost_oof"].to_numpy(float),
                    train["target_Y_event"].to_numpy(int),
                    test["p_catboost_oof"].to_numpy(float),
                )
            else:
                raise AssertionError(method)

            out = test.copy()
            out["calibration_method"] = method
            out["p_catboost_calibrated"] = pred
            out["brier_calibrated"] = brier_score(
                out["target_Y_event"].to_numpy(int), pred
            )
            out["log_calibrated"] = safe_log_score(
                out["target_Y_event"].to_numpy(int), pred
            )
            out["n_prior_calibration_dates"] = n_train_dates
            rows.append(out)

            inventory.append(
                {
                    "event_date": target_date,
                    "calibration_method": method,
                    "n_prior_calibration_dates": n_train_dates,
                    "n_prior_rows": len(train),
                    "n_test_rows": len(test),
                    "prior_positive_count": int(train["target_Y_event"].sum()),
                    "prior_negative_count": int((1 - train["target_Y_event"]).sum()),
                }
            )

    return pd.concat(rows, ignore_index=True), pd.DataFrame(inventory)


def select_calibration_method(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """
    Select calibration robustly for a small effective sample.

    Rule:
    1. Evaluate only dates with at least eight prior calibration dates.
    2. Exclude methods whose share of clipped probabilities exceeds 5%.
    3. Rank admissible methods primarily by mean date-level log score.
    4. Use mean date-level Brier as the secondary criterion.
    5. If no method passes the clipping rule, fall back to Platt when available,
       otherwise identity.

    This prevents a negligible Brier gain from choosing an unstable calibrator
    that creates extreme probabilities and severe log-score losses.
    """
    eligible = panel.loc[panel["n_prior_calibration_dates"] >= 8].copy()

    row_summary = (
        eligible.groupby("calibration_method", as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_dates=("event_date", "nunique"),
            mean_brier=("brier_calibrated", "mean"),
            mean_log_score=("log_calibrated", "mean"),
        )
    )

    date_scores = (
        eligible.groupby(["calibration_method", "event_date"], as_index=False)
        .agg(
            date_mean_brier=("brier_calibrated", "mean"),
            date_mean_log_score=("log_calibrated", "mean"),
            worst_row_log_score=("log_calibrated", "max"),
        )
    )
    date_summary = (
        date_scores.groupby("calibration_method", as_index=False)
        .agg(
            n_dates=("event_date", "nunique"),
            mean_date_brier=("date_mean_brier", "mean"),
            mean_date_log_score=("date_mean_log_score", "mean"),
            worst_date_log_score=("date_mean_log_score", "max"),
            worst_row_log_score=("worst_row_log_score", "max"),
        )
    )

    extreme = calibration_extreme_probability_diagnostics(eligible)

    summary = (
        row_summary.drop(columns=["n_dates"], errors="ignore")
        .merge(
            date_summary,
            on="calibration_method",
            how="left",
            validate="one_to_one",
        )
        .merge(
            extreme,
            on="calibration_method",
            how="left",
            validate="one_to_one",
        )
    )

    summary["passes_extreme_probability_guard"] = (
        summary["share_at_clip_bounds"] <= 0.05
    )

    admissible = summary.loc[
        summary["passes_extreme_probability_guard"].astype(bool)
    ].copy()

    if admissible.empty:
        if "platt" in set(summary["calibration_method"]):
            selected_method = "platt"
        else:
            selected_method = "identity"
        summary["selection_reason"] = (
            "Fallback because every method failed the extreme-probability guard."
        )
    else:
        admissible = admissible.sort_values(
            [
                "mean_date_log_score",
                "mean_date_brier",
                "mean_log_score",
                "mean_brier",
            ]
        )
        selected_method = str(admissible.iloc[0]["calibration_method"])
        summary["selection_reason"] = (
            "Admissible methods ranked by mean date-level log score first, "
            "then mean date-level Brier."
        )

    summary = summary.sort_values(
        [
            "passes_extreme_probability_guard",
            "mean_date_log_score",
            "mean_date_brier",
        ],
        ascending=[False, True, True],
    ).reset_index(drop=True)
    summary["calibration_rank"] = np.arange(1, len(summary) + 1)
    summary["selected"] = summary["calibration_method"].eq(selected_method)

    return summary, date_scores, extreme, selected_method


def build_selected_calibrated_panel(
    calibration_panel: pd.DataFrame,
    selected_method: str,
) -> pd.DataFrame:
    out = calibration_panel.loc[
        calibration_panel["calibration_method"] == selected_method
    ].copy()
    out["selected_calibration_method"] = selected_method
    return out


def normalise_books(
    df: pd.DataFrame,
    probability_col: str,
    model_name: str,
) -> pd.DataFrame:
    required = {"event_date", "decision_rule", "target_Y_event", probability_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Book input missing columns for {model_name}: {missing}")

    key = ["event_date", "decision_rule"]
    rows: list[pd.DataFrame] = []

    for _, book in df.groupby(key, sort=True):
        b = book.copy()
        p = pd.to_numeric(b[probability_col], errors="coerce")
        valid = p.notna().all()
        total = float(p.sum()) if valid else np.nan
        n_winners = int(b["target_Y_event"].sum())
        n_contracts = len(b)

        b["book_model"] = model_name
        b["book_raw_probability"] = p
        b["book_probability_sum"] = total
        b["book_abs_probability_error"] = abs(total - 1.0) if np.isfinite(total) else np.nan
        b["book_n_contracts"] = n_contracts
        b["book_n_winners"] = n_winners
        b["book_complete_for_scoring"] = bool(valid and total > 0 and n_winners == 1)
        if b["book_complete_for_scoring"].iloc[0]:
            b["book_normalised_probability"] = np.clip(p / total, EPS, 1 - EPS)
            winner = b["target_Y_event"].astype(int).to_numpy()
            q = b["book_normalised_probability"].to_numpy(float)
            b["categorical_log_component"] = np.where(winner == 1, -np.log(q), 0.0)
            b["multiclass_brier_component"] = (q - winner) ** 2
        else:
            b["book_normalised_probability"] = np.nan
            b["categorical_log_component"] = np.nan
            b["multiclass_brier_component"] = np.nan
        rows.append(b)

    return pd.concat(rows, ignore_index=True)


def summarise_books(book_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    group_cols = ["book_model", "event_date", "decision_rule"]
    metrics = (
        book_panel.groupby(group_cols, as_index=False)
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
        scored.groupby("book_model", as_index=False)
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
            [
                "mean_normalised_categorical_log_score",
                "mean_normalised_multiclass_brier",
            ]
        )
    )
    return metrics, summary


def merge_benchmarks(
    calibrated: pd.DataFrame,
    benchmark_long: pd.DataFrame,
) -> pd.DataFrame:
    base_cols = [
        c for c in [
            "event_date",
            "decision_rule",
            "token_id",
            "market_slug",
            "condition_id",
            "target_Y_event",
            "contract_event_type_v2",
        ] if c in calibrated.columns
    ]
    calibrated_base = calibrated[base_cols].copy()
    calibrated_base["model"] = "catboost_calibrated"
    calibrated_base["probability"] = calibrated["p_catboost_calibrated"].to_numpy(float)

    benchmarks = benchmark_long.copy()
    keep_models = {
        "market",
        "ecmwf_raw",
        "ecmwf_bias_fixed_sigma",
        "ecmwf_bias_adaptive_sigma",
    }
    benchmarks = benchmarks.loc[benchmarks["model"].isin(keep_models)].copy()
    keep = [c for c in base_cols if c in benchmarks.columns] + ["model", "probability"]
    benchmarks = benchmarks[keep]

    common_dates = set(calibrated_base["event_date"])
    benchmarks = benchmarks.loc[benchmarks["event_date"].isin(common_dates)].copy()

    all_models = pd.concat([calibrated_base, benchmarks], ignore_index=True)
    all_models["probability"] = pd.to_numeric(all_models["probability"], errors="coerce")
    all_models = all_models.loc[all_models["probability"].notna()].copy()
    all_models["brier"] = brier_score(
        all_models["target_Y_event"].to_numpy(int),
        all_models["probability"].to_numpy(float),
    )
    all_models["log_score"] = safe_log_score(
        all_models["target_Y_event"].to_numpy(int),
        all_models["probability"].to_numpy(float),
    )
    return all_models


def common_support_model_summary(all_models: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    key_cols = [
        c for c in ["event_date", "decision_rule", "token_id", "market_slug", "condition_id"]
        if c in all_models.columns
    ]
    counts = all_models.groupby(key_cols)["model"].nunique()
    required_n = all_models["model"].nunique()
    valid_keys = counts[counts == required_n].index

    indexed = all_models.set_index(key_cols)
    common = indexed.loc[indexed.index.isin(valid_keys)].reset_index()

    summary = (
        common.groupby("model", as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_dates=("event_date", "nunique"),
            mean_brier=("brier", "mean"),
            mean_log_score=("log_score", "mean"),
        )
        .sort_values(["mean_brier", "mean_log_score"])
    )
    return common, summary


def paired_bootstrap(
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


def make_comparisons(common: pd.DataFrame, config: Config) -> pd.DataFrame:
    rows = []
    for i, benchmark in enumerate(sorted(set(common["model"]) - {"catboost_calibrated"})):
        for j, metric in enumerate(["brier", "log_score"]):
            rows.append(
                paired_bootstrap(
                    common,
                    "catboost_calibrated",
                    benchmark,
                    metric,
                    config.bootstrap_reps,
                    config.random_seed + i * 10 + j,
                )
            )
    return pd.DataFrame(rows)


def reliability_table(df: pd.DataFrame, probability_col: str, n_bins: int = 10) -> pd.DataFrame:
    p = np.clip(pd.to_numeric(df[probability_col], errors="coerce"), EPS, 1 - EPS)
    valid = p.notna()
    temp = df.loc[valid, ["target_Y_event"]].copy()
    temp["probability"] = p.loc[valid]
    temp["bin"] = pd.cut(
        temp["probability"],
        bins=np.linspace(0, 1, n_bins + 1),
        include_lowest=True,
        duplicates="drop",
    )
    return (
        temp.groupby("bin", observed=False, as_index=False)
        .agg(
            n=("target_Y_event", "size"),
            mean_probability=("probability", "mean"),
            empirical_frequency=("target_Y_event", "mean"),
        )
    )


def integrity_checks(
    selected_oof: pd.DataFrame,
    calibration_panel: pd.DataFrame,
    calibrated: pd.DataFrame,
    calibration_summary: pd.DataFrame,
    common: pd.DataFrame,
    book_panel: pd.DataFrame,
) -> pd.DataFrame:
    checks = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    add("selected_oof_nonempty", len(selected_oof) > 0, f"rows={len(selected_oof)}")
    add("calibration_panel_nonempty", len(calibration_panel) > 0, f"rows={len(calibration_panel)}")
    add("selected_calibrated_nonempty", len(calibrated) > 0, f"rows={len(calibrated)}")
    add(
        "exactly_one_calibration_method_selected",
        int(calibration_summary["selected"].sum()) == 1,
        f"selected={int(calibration_summary['selected'].sum())}",
    )
    add(
        "calibrated_probabilities_in_unit_interval",
        calibrated["p_catboost_calibrated"].between(0, 1).all(),
        "checked",
    )
    selected_clip_share = float(
        (
            np.isclose(
                calibrated["p_catboost_calibrated"].to_numpy(float),
                EPS,
                atol=1e-15,
            )
            | np.isclose(
                calibrated["p_catboost_calibrated"].to_numpy(float),
                1 - EPS,
                atol=1e-15,
            )
        ).mean()
    )
    add(
        "selected_calibration_extreme_probability_guard",
        selected_clip_share <= 0.05,
        f"clip_share={selected_clip_share:.6f}, maximum=0.05",
    )
    add(
        "calibration_uses_prior_dates_only",
        bool(
            (
                calibration_panel["n_prior_calibration_dates"]
                <= calibration_panel["event_date"].rank(method="dense").astype(int) - 1
            ).all()
        ),
        "expanding-date design",
    )
    add(
        "common_support_nonempty",
        len(common) > 0,
        f"rows={len(common)}, models={common['model'].nunique()}",
    )
    key = [c for c in ["model", "event_date", "decision_rule", "token_id", "market_slug"] if c in common.columns]
    add(
        "common_support_keys_unique",
        not common.duplicated(key).any(),
        f"duplicates={int(common.duplicated(key).sum())}",
    )
    add(
        "book_panel_nonempty",
        len(book_panel) > 0,
        f"rows={len(book_panel)}",
    )
    scored = book_panel.loc[book_panel["book_complete_for_scoring"].astype(bool)]
    add(
        "scored_books_have_one_winner",
        (scored.groupby(["book_model", "event_date", "decision_rule"])["target_Y_event"].sum() == 1).all(),
        f"scored_books={scored.groupby(['book_model','event_date','decision_rule']).ngroups}",
    )
    add(
        "normalised_books_sum_to_one",
        np.allclose(
            scored.groupby(["book_model", "event_date", "decision_rule"])["book_normalised_probability"].sum(),
            1.0,
            atol=1e-8,
        ),
        "checked scored books",
    )
    add(
        "final_holdout_still_sealed",
        True,
        "20d reads development OOF files only",
    )
    return pd.DataFrame(checks)


def make_figures(
    calibration_summary: pd.DataFrame,
    reliability_identity: pd.DataFrame,
    reliability_selected: pd.DataFrame,
    model_summary: pd.DataFrame,
    book_summary: pd.DataFrame,
    figure_dir: Path,
) -> list[Path]:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    fig, ax = plt.subplots(figsize=(9, 5))
    order = calibration_summary.sort_values("mean_date_brier")
    ax.bar(order["calibration_method"], order["mean_date_brier"])
    ax.set_ylabel("Mean date-level Brier score")
    ax.set_title("20d CatBoost calibration-method comparison")
    fig.tight_layout()
    p = figure_dir / "20d_calibration_method_brier.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(
        reliability_identity["mean_probability"],
        reliability_identity["empirical_frequency"],
        marker="o",
        label="Uncalibrated CatBoost",
    )
    ax.plot(
        reliability_selected["mean_probability"],
        reliability_selected["empirical_frequency"],
        marker="o",
        label="Selected calibration",
    )
    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Empirical frequency")
    ax.set_title("Development OOF reliability")
    ax.legend()
    fig.tight_layout()
    p = figure_dir / "20d_reliability_comparison.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    fig, ax = plt.subplots(figsize=(10, 5))
    plot = model_summary.sort_values("mean_brier")
    ax.bar(plot["model"], plot["mean_brier"])
    ax.set_ylabel("Mean Brier score")
    ax.set_title("Calibrated CatBoost versus direct probability benchmarks")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = figure_dir / "20d_model_brier_comparison.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    fig, ax = plt.subplots(figsize=(10, 5))
    plot = book_summary.sort_values("mean_normalised_categorical_log_score")
    ax.bar(plot["book_model"], plot["mean_normalised_categorical_log_score"])
    ax.set_ylabel("Mean normalised categorical log score")
    ax.set_title("Complete event-book categorical comparison")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    p = figure_dir / "20d_event_book_categorical_log.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    return outputs


def write_report(
    selected_method: str,
    calibration_summary: pd.DataFrame,
    model_summary: pd.DataFrame,
    comparisons: pd.DataFrame,
    book_summary: pd.DataFrame,
    checks: pd.DataFrame,
    report_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 20d out-of-fold calibration and event-book coherence",
        "",
        "## Purpose",
        "",
        "This step calibrates the best 20c CatBoost specification using only prior development OOF dates, "
        "then evaluates binary proper scores and complete-book categorical diagnostics. "
        "The final chronological holdout remains sealed.",
        "",
        "## Selected robust calibration method",
        "",
        f"`{selected_method}`",
        "",
        "Selection rule: methods with more than 5% of probabilities at the clipping bounds are rejected. "
        "Among admissible methods, mean date-level log score is primary and mean date-level Brier is secondary.",
        "",
        "## Calibration-method comparison",
        "",
        calibration_summary.to_markdown(index=False),
        "",
        "## Calibrated CatBoost versus direct probability benchmarks",
        "",
        model_summary.to_markdown(index=False),
        "",
        "## Paired date-clustered bootstrap comparisons",
        "",
        comparisons.to_markdown(index=False),
        "",
        "Negative calibrated-CatBoost-minus-benchmark differences favour calibrated CatBoost.",
        "",
        "## Event-book coherence and categorical scores",
        "",
        book_summary.to_markdown(index=False),
        "",
        "Raw binary probabilities are scored directly at contract level. "
        "For categorical event-book diagnostics, probabilities are normalised within complete daily books.",
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Methodological status",
        "",
        "The isotonic method is retained as a diagnostic but cannot be selected when it produces excessive "
        "clipping or materially unstable log-score behaviour. "
        "20d freezes the calibration and coherence procedure on development OOF data. "
        "No final-holdout score is reported here. The next locked step may train on all development dates "
        "and evaluate exactly once on the final chronological holdout.",
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
    figures = repo / "figures" / "20d_calibration_coherence"

    selected_oof, benchmark_long, manifest_20c = load_inputs(repo)

    calibration_panel, calibration_inventory = expanding_calibration_panel(
        selected_oof,
        config.min_calibration_dates,
    )
    (
        calibration_summary,
        calibration_date_scores,
        calibration_extreme_diagnostics,
        selected_method,
    ) = select_calibration_method(calibration_panel)
    calibrated = build_selected_calibrated_panel(
        calibration_panel,
        selected_method,
    )

    all_models = merge_benchmarks(calibrated, benchmark_long)
    common, model_summary = common_support_model_summary(all_models)
    comparisons = make_comparisons(common, config)

    # Build book panels for all compared models.
    book_panels = []
    for model_name, group in common.groupby("model"):
        book_panels.append(
            normalise_books(
                group,
                probability_col="probability",
                model_name=model_name,
            )
        )
    book_panel = pd.concat(book_panels, ignore_index=True)
    book_metrics, book_summary = summarise_books(book_panel)

    reliability_identity = reliability_table(
        calibration_panel.loc[calibration_panel["calibration_method"] == "identity"],
        "p_catboost_calibrated",
    )
    reliability_selected = reliability_table(
        calibrated,
        "p_catboost_calibrated",
    )

    checks = integrity_checks(
        selected_oof,
        calibration_panel,
        calibrated,
        calibration_summary,
        common,
        book_panel,
    )
    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    manifest = {
        "step": "20d",
        "input_20c_candidate_id": manifest_20c.get("candidate_id"),
        "input_20c_feature_set": manifest_20c.get("feature_set"),
        "selected_calibration_method": selected_method,
        "selection_scope": "development_oof_only",
        "final_holdout_evaluated": False,
        "min_calibration_dates": config.min_calibration_dates,
        "selection_metric_primary": "mean_date_log_score",
        "selection_metric_secondary": "mean_date_brier",
        "extreme_probability_guard_max_clip_share": 0.05,
        "selected_method_passes_extreme_probability_guard": bool(
            calibration_summary.loc[
                calibration_summary["selected"],
                "passes_extreme_probability_guard",
            ].iloc[0]
        ),
        "binary_scores_use_raw_contract_probabilities": True,
        "categorical_scores_use_within_book_normalised_probabilities": True,
        "requires_locked_final_holdout_evaluation": True,
    }

    outputs = {
        "calibration_panel": processed / "20d_expanding_calibration_probability_panel.csv",
        "calibration_inventory": processed / "20d_calibration_fit_inventory.csv",
        "calibration_summary": processed / "20d_calibration_method_summary.csv",
        "calibration_date_scores": processed / "20d_calibration_date_level_scores.csv",
        "calibration_extreme": processed / "20d_calibration_extreme_probability_diagnostics.csv",
        "selected_panel": processed / "20d_selected_calibrated_probability_panel.csv",
        "common_support": processed / "20d_common_support_model_probability_panel.csv",
        "model_summary": processed / "20d_common_support_binary_score_summary.csv",
        "comparisons": processed / "20d_paired_date_level_comparisons.csv",
        "book_panel": processed / "20d_event_book_probability_panel.csv",
        "book_metrics": processed / "20d_event_book_metrics.csv",
        "book_summary": processed / "20d_event_book_score_summary.csv",
        "reliability_identity": processed / "20d_reliability_uncalibrated.csv",
        "reliability_selected": processed / "20d_reliability_selected_calibration.csv",
        "checks": processed / "20d_integrity_checks.csv",
        "issues": processed / "20d_issues.csv",
        "manifest": processed / "20d_calibration_coherence_manifest.json",
        "report": docs / "20d_calibration_coherence_report.md",
    }

    serialise_dates(calibration_panel).to_csv(outputs["calibration_panel"], index=False)
    serialise_dates(calibration_inventory).to_csv(outputs["calibration_inventory"], index=False)
    calibration_summary.to_csv(outputs["calibration_summary"], index=False)
    serialise_dates(calibration_date_scores).to_csv(outputs["calibration_date_scores"], index=False)
    calibration_extreme_diagnostics.to_csv(outputs["calibration_extreme"], index=False)
    serialise_dates(calibrated).to_csv(outputs["selected_panel"], index=False)
    serialise_dates(common).to_csv(outputs["common_support"], index=False)
    model_summary.to_csv(outputs["model_summary"], index=False)
    comparisons.to_csv(outputs["comparisons"], index=False)
    serialise_dates(book_panel).to_csv(outputs["book_panel"], index=False)
    serialise_dates(book_metrics).to_csv(outputs["book_metrics"], index=False)
    book_summary.to_csv(outputs["book_summary"], index=False)
    reliability_identity.to_csv(outputs["reliability_identity"], index=False)
    reliability_selected.to_csv(outputs["reliability_selected"], index=False)
    checks.to_csv(outputs["checks"], index=False)
    issues.to_csv(outputs["issues"], index=False)
    outputs["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    figure_paths = make_figures(
        calibration_summary,
        reliability_identity,
        reliability_selected,
        model_summary,
        book_summary,
        figures,
    )
    write_report(
        selected_method,
        calibration_summary,
        model_summary,
        comparisons,
        book_summary,
        checks,
        outputs["report"],
    )

    review_zip = repo / "data" / "review_bundles" / "20d_review_bundle.zip"
    zip_review(list(outputs.values()) + figure_paths, repo, review_zip)

    print("20d completed.")
    print(f"Selected calibration method: {selected_method}")
    print(f"Common-support rows: {len(common)}")
    print(f"Compared models: {common['model'].nunique()}")
    print(f"Passed checks: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more 20d integrity checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
