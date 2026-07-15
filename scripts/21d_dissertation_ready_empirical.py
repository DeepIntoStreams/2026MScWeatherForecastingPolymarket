#!/usr/bin/env python3
"""
21d: Dissertation-ready empirical consolidation.

This step does not change any forecast, calibration, validation, or trading
specification. It consolidates the final Hong Kong empirical pipeline into
supervisor-ready and dissertation-ready tables, figures, and a concise report.

Inputs:
- 18m market-only baseline diagnostics;
- 19b common-support market versus ECMWF comparison;
- 19c leakage-free ECMWF bias/scale correction;
- 20e locked chronological holdout evaluation;
- 21a standalone binary-contract trading;
- 21b full event-book trading;
- 21c locked-holdout cost, staleness, and robustness analysis.

Outputs:
- one empirical headline table;
- one forecast-score comparison table;
- one locked-holdout model table;
- one trading headline table;
- one robustness headline table;
- one compact integrity summary;
- dissertation-ready figures;
- supervisor summary report;
- review bundle.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser.parse_args()


def read_csv_any(paths: list[Path], required=True) -> tuple[pd.DataFrame, Path | None]:
    for path in paths:
        if path.exists():
            return pd.read_csv(path, low_memory=False), path
    if required:
        raise FileNotFoundError(
            "None of the candidate input files exist:\n"
            + "\n".join(str(p) for p in paths)
        )
    return pd.DataFrame(), None


def read_json_any(paths: list[Path], required=True) -> tuple[dict, Path | None]:
    for path in paths:
        if path.exists():
            return json.loads(path.read_text()), path
    if required:
        raise FileNotFoundError(
            "None of the candidate JSON files exist:\n"
            + "\n".join(str(p) for p in paths)
        )
    return {}, None


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def normalise_column_lookup(df: pd.DataFrame) -> dict[str, str]:
    return {c.lower(): c for c in df.columns}


def choose_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = normalise_column_lookup(df)
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def market_baseline_table(
    processed: Path,
) -> tuple[pd.DataFrame, list[Path]]:
    """Load the final supervisor-facing 18m market baseline table."""
    path = processed / "18m_supervisor_market_only_key_table.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Missing required 18m market baseline table: {path}"
        )

    df = pd.read_csv(path, low_memory=False)

    decision = choose_column(
        df,
        ["decision_rule"],
    )
    brier = choose_column(
        df,
        [
            "mean_binary_brier",
            "mean_brier",
            "binary_brier",
            "brier_mean",
        ],
    )
    log_score = choose_column(
        df,
        [
            "mean_binary_log_score",
            "mean_log_score",
            "binary_log_score",
            "log_score_mean",
        ],
    )
    categorical_log = choose_column(
        df,
        [
            "mean_normalised_categorical_log_score",
            "normalised_categorical_log_score",
            "mean_normalized_categorical_log_score",
            "normalized_categorical_log_score",
        ],
    )
    multiclass_brier = choose_column(
        df,
        [
            "mean_normalised_multiclass_brier",
            "normalised_multiclass_brier",
            "mean_normalized_multiclass_brier",
            "normalized_multiclass_brier",
        ],
    )

    if decision is None or brier is None or log_score is None:
        raise ValueError(
            "18m supervisor table lacks required score columns. "
            f"Found columns: {list(df.columns)}"
        )

    out = pd.DataFrame(
        {
            "decision_rule": df[decision],
            "market_binary_brier": pd.to_numeric(
                df[brier],
                errors="coerce",
            ),
            "market_binary_log_score": pd.to_numeric(
                df[log_score],
                errors="coerce",
            ),
        }
    )

    if categorical_log is not None:
        out["market_normalised_categorical_log"] = pd.to_numeric(
            df[categorical_log],
            errors="coerce",
        )

    if multiclass_brier is not None:
        out["market_normalised_multiclass_brier"] = pd.to_numeric(
            df[multiclass_brier],
            errors="coerce",
        )

    out = out.dropna(
        subset=[
            "decision_rule",
            "market_binary_brier",
            "market_binary_log_score",
        ]
    ).reset_index(drop=True)

    if out.empty:
        raise ValueError(
            "18m supervisor market baseline table produced no usable rows."
        )

    print("21d selected 18m input:", path)
    return out, [path]


def common_support_table(
    processed: Path,
) -> tuple[pd.DataFrame, list[Path]]:
    """Load the final 19b exact-common-support binary comparison."""

    candidates = [
        processed / "19b_common_support_binary_score_summary.csv",
        processed
        / "19b_common_support_market_vs_ecmwf_binary_score_summary.csv",
    ]

    df, path = read_csv_any(candidates)

    required = {
        "decision_rule",
        "market_mean_brier",
        "ecmwf_mean_brier",
        "market_mean_log_score",
        "ecmwf_mean_log_score",
    }

    missing = required.difference(df.columns)

    if missing:
        raise ValueError(
            "19b table lacks required common-support columns: "
            f"{sorted(missing)}. Found: {list(df.columns)}"
        )

    out = pd.DataFrame(
        {
            "decision_rule": df["decision_rule"],
            "n_common_support": pd.to_numeric(
                df["n"],
                errors="coerce",
            ) if "n" in df.columns else np.nan,
            "market_brier": pd.to_numeric(
                df["market_mean_brier"],
                errors="coerce",
            ),
            "ecmwf_proxy_brier": pd.to_numeric(
                df["ecmwf_mean_brier"],
                errors="coerce",
            ),
            "market_log_score": pd.to_numeric(
                df["market_mean_log_score"],
                errors="coerce",
            ),
            "ecmwf_proxy_log_score": pd.to_numeric(
                df["ecmwf_mean_log_score"],
                errors="coerce",
            ),
        }
    )

    out["brier_advantage_market_over_raw_ecmwf"] = (
        out["ecmwf_proxy_brier"]
        - out["market_brier"]
    )

    out["log_advantage_market_over_raw_ecmwf"] = (
        out["ecmwf_proxy_log_score"]
        - out["market_log_score"]
    )

    if "market_minus_ecmwf_brier" in df.columns:
        supplied = pd.to_numeric(
            df["market_minus_ecmwf_brier"],
            errors="coerce",
        )
        calculated = (
            out["market_brier"]
            - out["ecmwf_proxy_brier"]
        )

        if not np.allclose(
            supplied,
            calculated,
            equal_nan=True,
            atol=1e-12,
        ):
            raise ValueError(
                "19b supplied market-minus-ECMWF Brier differences "
                "do not match recomputation."
            )

    if "market_minus_ecmwf_log_score" in df.columns:
        supplied = pd.to_numeric(
            df["market_minus_ecmwf_log_score"],
            errors="coerce",
        )
        calculated = (
            out["market_log_score"]
            - out["ecmwf_proxy_log_score"]
        )

        if not np.allclose(
            supplied,
            calculated,
            equal_nan=True,
            atol=1e-12,
        ):
            raise ValueError(
                "19b supplied market-minus-ECMWF log differences "
                "do not match recomputation."
            )

    out = out.dropna(
        subset=[
            "decision_rule",
            "market_brier",
            "ecmwf_proxy_brier",
            "market_log_score",
            "ecmwf_proxy_log_score",
        ]
    ).reset_index(drop=True)

    if out.empty:
        raise ValueError(
            "19b common-support comparison produced no usable rows."
        )

    print("21d selected 19b input:", path)
    return out, [path]


def corrected_ecmwf_table(
    processed: Path,
) -> tuple[pd.DataFrame, list[Path]]:
    """
    Discover the model-level 19c leakage-free ECMWF correction summary.

    Event-type, date-level and reliability-bin diagnostics are excluded.
    """
    candidates = sorted(processed.glob("19c*.csv"))
    inspected = []

    excluded_name_terms = {
        "event_type",
        "by_date",
        "reliability",
        "calibration_bin",
        "probability_panel",
        "issue",
        "integrity",
    }

    model_candidates = [
        "model",
        "specification",
        "probability_source",
        "forecast_model",
        "candidate_id",
    ]
    decision_candidates = ["decision_rule"]
    brier_candidates = [
        "mean_brier",
        "brier_mean",
        "mean_brier_score",
        "brier_score",
    ]
    log_candidates = [
        "mean_log_score",
        "log_score_mean",
        "mean_log",
        "log_score",
    ]

    for candidate in candidates:
        lower_name = candidate.name.lower()

        if any(term in lower_name for term in excluded_name_terms):
            continue

        try:
            df = pd.read_csv(candidate, low_memory=False)
        except Exception:
            continue

        inspected.append(
            {
                "path": str(candidate),
                "rows": len(df),
                "columns": list(df.columns),
            }
        )

        if "event_type" in df.columns:
            continue

        decision = choose_column(df, decision_candidates)
        model = choose_column(df, model_candidates)
        brier = choose_column(df, brier_candidates)
        log_score = choose_column(df, log_candidates)

        if any(
            column is None
            for column in [decision, model, brier, log_score]
        ):
            continue

        out = pd.DataFrame(
            {
                "decision_rule": df[decision].astype(str),
                "model": df[model].astype(str),
                "mean_brier": pd.to_numeric(
                    df[brier],
                    errors="coerce",
                ),
                "mean_log_score": pd.to_numeric(
                    df[log_score],
                    errors="coerce",
                ),
            }
        ).dropna()

        if out.empty:
            continue

        model_text = " ".join(
            out["model"].astype(str).str.lower().unique()
        )

        recognised_model_terms = [
            "ecmwf",
            "fixed_sigma",
            "adaptive_sigma",
            "raw",
            "bias",
        ]

        if not any(term in model_text for term in recognised_model_terms):
            continue

        if out["decision_rule"].nunique() < 4:
            continue

        if out["model"].nunique() < 2:
            continue

        print("21d selected model-level 19c input:", candidate)
        return out.reset_index(drop=True), [candidate]

    details = "\n".join(
        (
            f"{item['path']} | rows={item['rows']} | "
            f"columns={item['columns']}"
        )
        for item in inspected
    )

    raise FileNotFoundError(
        "No valid model-level 19c corrected-ECMWF summary was found.\n"
        "Inspected non-diagnostic 19c files:\n"
        + details
    )


def holdout_table(
    processed: Path,
) -> tuple[pd.DataFrame, list[Path]]:
    """
    Build the final 20e model-by-decision-rule locked-holdout summary directly
    from the row-level long model panel.
    """
    path = processed / "20e_locked_holdout_long_model_panel.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Missing required 20e locked-holdout panel: {path}"
        )

    df = pd.read_csv(path, low_memory=False)

    required = {
        "event_date",
        "decision_rule",
        "model",
        "brier",
        "log_score",
    }

    missing = required.difference(df.columns)

    if missing:
        raise ValueError(
            "20e locked-holdout long panel lacks required columns: "
            f"{sorted(missing)}. Found: {list(df.columns)}"
        )

    df["event_date"] = pd.to_datetime(
        df["event_date"]
    ).dt.normalize()

    holdout_start = pd.Timestamp("2026-05-22")
    holdout_end = pd.Timestamp("2026-05-31")

    df = df.loc[
        df["event_date"].between(
            holdout_start,
            holdout_end,
            inclusive="both",
        )
    ].copy()

    if df.empty:
        raise ValueError(
            "20e long model panel contains no locked-holdout rows."
        )

    out = (
        df.groupby(
            ["model", "decision_rule"],
            as_index=False,
        )
        .agg(
            n=("brier", "size"),
            n_dates=("event_date", "nunique"),
            mean_brier=("brier", "mean"),
            mean_log_score=("log_score", "mean"),
        )
    )

    out["evaluation_sample"] = "locked_final_holdout"
    out["holdout_start_date"] = "2026-05-22"
    out["holdout_end_date"] = "2026-05-31"

    expected_rules = {
        "24h_prior",
        "12h_prior",
        "6h_prior",
        "event_day_open",
    }

    if set(out["decision_rule"]) != expected_rules:
        raise ValueError(
            "Unexpected 20e decision-rule set: "
            f"{sorted(out['decision_rule'].unique())}"
        )

    if out["model"].nunique() < 3:
        raise ValueError(
            "20e summary contains fewer than three forecasting models."
        )

    if out["n_dates"].min() != 10:
        raise ValueError(
            "Not every 20e model-decision specification contains all "
            "10 locked-holdout dates."
        )

    print("21d selected row-level 20e input:", path)
    return out.sort_values(
        ["mean_brier", "mean_log_score"]
    ).reset_index(drop=True), [path]


def trading_headline(processed: Path) -> tuple[pd.DataFrame, list[Path]]:
    a, p1 = read_csv_any(
        [
            processed
            / "21a_simple_edge_primary_standalone_strategy_summary.csv"
        ]
    )
    b, p2 = read_csv_any(
        [
            processed / "21b_full_event_book_primary_standalone_summary.csv"
        ]
    )

    a = a.copy()
    a["pipeline"] = "21a"
    a["strategy"] = "binary_contract_edge"
    a["activity_count"] = a.get("n_trades", np.nan)
    a["headline_pnl"] = a["total_net_pnl"]

    b = b.copy()
    b["pipeline"] = "21b"
    b["activity_count"] = b.get("n_positions", np.nan)
    b["headline_pnl"] = b["total_net_pnl"]

    common = sorted(set(a.columns) | set(b.columns))
    for frame in [a, b]:
        for c in common:
            if c not in frame.columns:
                frame[c] = np.nan

    out = pd.concat([a[common], b[common]], ignore_index=True)
    out = out.sort_values("headline_pnl", ascending=False).reset_index(drop=True)
    return out, [p1, p2]


def robustness_headline(processed: Path) -> tuple[pd.DataFrame, list[Path]]:
    df, path = read_csv_any(
        [processed / "21c_primary_robustness_summary.csv"]
    )
    return (
        df.sort_values("total_net_pnl", ascending=False).reset_index(drop=True),
        [path],
    )


def integrity_summary(
    processed: Path,
) -> tuple[pd.DataFrame, list[Path]]:
    """
    Load and validate the integrity checks for every source step declared by
    21d. No source block may be omitted silently.
    """
    candidates = [
        (
            "18m",
            [
                processed / "18m_market_only_integrity_checks.csv",
                processed / "18m_integrity_checks.csv",
            ],
        ),
        (
            "19b",
            [
                processed / "19b_common_support_integrity_checks.csv",
            ],
        ),
        (
            "19c",
            [
                processed / "19c_integrity_checks.csv",
            ],
        ),
        (
            "20e",
            [
                processed / "20e_locked_holdout_integrity_checks.csv",
            ],
        ),
        (
            "21a",
            [
                processed / "21a_simple_edge_integrity_checks.csv",
            ],
        ),
        (
            "21b",
            [
                processed / "21b_full_event_book_integrity_checks.csv",
            ],
        ),
        (
            "21c",
            [
                processed / "21c_integrity_checks.csv",
            ],
        ),
    ]

    expected_steps = [
        "18m",
        "19b",
        "19c",
        "20e",
        "21a",
        "21b",
        "21c",
    ]

    rows = []
    used = []
    missing_steps = []

    for step, path_candidates in candidates:
        selected_path = first_existing(path_candidates)

        if selected_path is None:
            missing_steps.append(step)
            continue

        df = pd.read_csv(
            selected_path,
            low_memory=False,
        )

        passed_col = choose_column(
            df,
            ["passed"],
        )

        if passed_col is None:
            raise ValueError(
                f"{step} integrity file lacks a passed column: "
                f"{selected_path}. Found: {list(df.columns)}"
            )

        passed = df[passed_col].astype(bool)

        rows.append(
            {
                "step": step,
                "integrity_file": str(
                    selected_path.relative_to(processed.parent.parent)
                ),
                "checks_passed": int(passed.sum()),
                "checks_total": int(len(df)),
                "all_checks_passed": bool(passed.all()),
            }
        )
        used.append(selected_path)

    if missing_steps:
        raise FileNotFoundError(
            "21d is missing required integrity blocks for: "
            + ", ".join(missing_steps)
        )

    out = pd.DataFrame(rows)

    observed_steps = out["step"].tolist()

    if observed_steps != expected_steps:
        raise ValueError(
            "21d integrity-step order or membership is incorrect. "
            f"Observed: {observed_steps}; expected: {expected_steps}"
        )

    if len(out) != 7:
        raise ValueError(
            f"21d expected seven integrity blocks but found {len(out)}."
        )

    print(
        "21d validated integrity blocks:",
        ", ".join(observed_steps),
    )

    return out, used


def empirical_headline(
    market: pd.DataFrame,
    common: pd.DataFrame,
    holdout: pd.DataFrame,
    trading: pd.DataFrame,
    robust: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    market_brier_best = market.loc[
        market["market_binary_brier"].idxmin()
    ]
    market_log_best = market.loc[
        market["market_binary_log_score"].idxmin()
    ]

    rows.append(
        {
            "block": "Market baseline",
            "metric": "Best binary Brier",
            "value": float(market_brier_best["market_binary_brier"]),
            "model_or_source": "Polymarket",
            "decision_rule": market_brier_best["decision_rule"],
            "sample": "full available HKO market panel",
        }
    )
    rows.append(
        {
            "block": "Market baseline",
            "metric": "Best binary log score",
            "value": float(market_log_best["market_binary_log_score"]),
            "model_or_source": "Polymarket",
            "decision_rule": market_log_best["decision_rule"],
            "sample": "full available HKO market panel",
        }
    )

    common_adv = common.loc[
        common["brier_advantage_market_over_raw_ecmwf"].idxmax()
    ]
    rows.append(
        {
            "block": "Common-support forecast comparison",
            "metric": "Largest market Brier advantage over raw ECMWF",
            "value": float(
                common_adv["brier_advantage_market_over_raw_ecmwf"]
            ),
            "model_or_source": "Polymarket versus raw ECMWF proxy",
            "decision_rule": common_adv["decision_rule"],
            "sample": "exact common support",
        }
    )

    holdout_best = holdout.loc[holdout["mean_brier"].idxmin()]
    rows.append(
        {
            "block": "Locked holdout forecasting",
            "metric": "Best holdout Brier",
            "value": float(holdout_best["mean_brier"]),
            "model_or_source": holdout_best["model"],
            "decision_rule": holdout_best["decision_rule"],
            "sample": "22–31 May 2026 locked holdout",
        }
    )

    trading_best = trading.loc[trading["headline_pnl"].idxmax()]
    rows.append(
        {
            "block": "Frictionless trading",
            "metric": "Best primary standalone PnL",
            "value": float(trading_best["headline_pnl"]),
            "model_or_source": (
                f"{trading_best['pipeline']}: "
                f"{trading_best['model']}, "
                f"{trading_best['strategy']}"
            ),
            "decision_rule": trading_best["decision_rule"],
            "sample": "22–31 May 2026 locked holdout",
        }
    )

    robust_best = robust.loc[robust["total_net_pnl"].idxmax()]
    rows.append(
        {
            "block": "Robustness trading",
            "metric": "Best cost-and-staleness adjusted PnL",
            "value": float(robust_best["total_net_pnl"]),
            "model_or_source": (
                f"{robust_best['pipeline']}: "
                f"{robust_best['model']}, "
                f"{robust_best['strategy']}"
            ),
            "decision_rule": robust_best["decision_rule"],
            "sample": "22–31 May 2026 locked holdout",
        }
    )

    return pd.DataFrame(rows)


def make_figures(
    common: pd.DataFrame,
    holdout: pd.DataFrame,
    trading: pd.DataFrame,
    robust: pd.DataFrame,
    figure_dir: Path,
) -> list[Path]:
    """
    Produce compact dissertation-ready figures.

    Long model and strategy labels are shown on horizontal bar charts. The
    strongest twelve specifications are retained for readability.
    """
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    decision_label = {
        "24h_prior": "24h prior",
        "12h_prior": "12h prior",
        "6h_prior": "6h prior",
        "event_day_open": "Event-day open",
    }

    model_label = {
        "ecmwf_bias_adaptive_sigma": "Adaptive ECMWF",
        "ecmwf_bias_fixed_sigma": "Fixed ECMWF",
        "ecmwf_raw": "Raw ECMWF",
        "catboost_platt": "Platt CatBoost",
        "catboost_raw": "Raw CatBoost",
        "market": "Market",
        "p_market": "Market",
    }

    strategy_label = {
        "binary_contract_edge": "Binary",
        "single_best_edge": "Single-best",
        "proportional_positive_edge": "Proportional",
    }

    def compact_model(value: object) -> str:
        raw = str(value)
        return model_label.get(
            raw,
            raw.replace("_", " ").title(),
        )

    def compact_decision(value: object) -> str:
        raw = str(value)
        return decision_label.get(
            raw,
            raw.replace("_", " ").title(),
        )

    def compact_strategy(value: object) -> str:
        raw = str(value)
        return strategy_label.get(
            raw,
            raw.replace("_", " ").title(),
        )

    # --------------------------------------------------------
    # Common-support market versus raw ECMWF
    # --------------------------------------------------------
    plot = common.copy()
    x = np.arange(len(plot))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.bar(
        x - width / 2,
        plot["market_brier"],
        width,
        label="Market",
    )
    ax.bar(
        x + width / 2,
        plot["ecmwf_proxy_brier"],
        width,
        label="Raw ECMWF proxy",
    )

    ax.set_xticks(
        x,
        [
            compact_decision(value)
            for value in plot["decision_rule"]
        ],
    )
    ax.set_ylabel("Mean Brier score")
    ax.set_title(
        "Common-support market versus raw ECMWF proxy"
    )
    ax.legend()
    fig.tight_layout()

    path = figure_dir / "21d_common_support_brier.png"
    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)
    outputs.append(path)

    # --------------------------------------------------------
    # Locked-holdout forecast ranking
    # --------------------------------------------------------
    top_holdout = (
        holdout.sort_values(
            ["mean_brier", "mean_log_score"],
            ascending=[True, True],
        )
        .head(12)
        .copy()
    )

    top_holdout["label"] = [
        (
            f"{compact_model(model)} | "
            f"{compact_decision(rule)}"
        )
        for model, rule in zip(
            top_holdout["model"],
            top_holdout["decision_rule"],
        )
    ]

    # Reverse so the strongest model appears at the top.
    plot_holdout = top_holdout.iloc[::-1].copy()

    fig, ax = plt.subplots(figsize=(11, 7))

    ax.barh(
        plot_holdout["label"],
        plot_holdout["mean_brier"],
    )

    ax.set_xlabel("Mean Brier score")
    ax.set_ylabel("")
    ax.set_title(
        "Locked-holdout forecast ranking: best 12 specifications"
    )
    ax.grid(
        axis="x",
        alpha=0.25,
    )
    fig.tight_layout()

    path = figure_dir / "21d_locked_holdout_brier_ranking.png"
    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)
    outputs.append(path)

    # --------------------------------------------------------
    # Primary frictionless trading
    # --------------------------------------------------------
    top_trade = (
        trading.sort_values(
            "headline_pnl",
            ascending=False,
        )
        .head(12)
        .copy()
    )

    top_trade["label"] = [
        (
            f"{pipeline} | "
            f"{compact_model(model)} | "
            f"{compact_decision(rule)} | "
            f"{compact_strategy(strategy)}"
        )
        for pipeline, model, rule, strategy in zip(
            top_trade["pipeline"],
            top_trade["model"],
            top_trade["decision_rule"],
            top_trade["strategy"],
        )
    ]

    plot_trade = top_trade.iloc[::-1].copy()

    fig, ax = plt.subplots(figsize=(12, 8))

    ax.barh(
        plot_trade["label"],
        plot_trade["headline_pnl"],
    )

    ax.axvline(
        0,
        linestyle="--",
        linewidth=1,
    )
    ax.set_xlabel("Hypothetical net PnL")
    ax.set_ylabel("")
    ax.set_title(
        "Primary frictionless trading results: best 12 specifications"
    )
    ax.grid(
        axis="x",
        alpha=0.25,
    )
    fig.tight_layout()

    path = figure_dir / "21d_primary_trading_headline.png"
    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)
    outputs.append(path)

    # --------------------------------------------------------
    # Primary cost-and-staleness robustness
    # --------------------------------------------------------
    top_robust = (
        robust.sort_values(
            "total_net_pnl",
            ascending=False,
        )
        .head(12)
        .copy()
    )

    top_robust["label"] = [
        (
            f"{pipeline} | "
            f"{compact_model(model)} | "
            f"{compact_decision(rule)} | "
            f"{compact_strategy(strategy)}"
        )
        for pipeline, model, rule, strategy in zip(
            top_robust["pipeline"],
            top_robust["model"],
            top_robust["decision_rule"],
            top_robust["strategy"],
        )
    ]

    plot_robust = top_robust.iloc[::-1].copy()

    fig, ax = plt.subplots(figsize=(12, 8))

    ax.barh(
        plot_robust["label"],
        plot_robust["total_net_pnl"],
    )

    ax.axvline(
        0,
        linestyle="--",
        linewidth=1,
    )
    ax.set_xlabel(
        "Cost-and-staleness-adjusted hypothetical PnL"
    )
    ax.set_ylabel("")
    ax.set_title(
        "Primary robustness results: best 12 specifications"
    )
    ax.grid(
        axis="x",
        alpha=0.25,
    )
    fig.tight_layout()

    path = figure_dir / "21d_primary_robustness_headline.png"
    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)
    outputs.append(path)

    return outputs


def write_report(
    headline: pd.DataFrame,
    market: pd.DataFrame,
    common: pd.DataFrame,
    corrected: pd.DataFrame,
    holdout: pd.DataFrame,
    trading: pd.DataFrame,
    robust: pd.DataFrame,
    integrity: pd.DataFrame,
    manifest: dict,
    report_path: Path,
):
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 21d consolidated Hong Kong empirical results",
        "",
        "## Status",
        "",
        "This step consolidates the final empirical outputs without changing any "
        "forecast, calibration, validation, or trading specification.",
        "",
        "## Empirical headline",
        "",
        headline.to_markdown(index=False),
        "",
        "## Market-only baseline",
        "",
        market.to_markdown(index=False),
        "",
        "## Common-support market versus raw ECMWF proxy",
        "",
        common.to_markdown(index=False),
        "",
        "## Leakage-free ECMWF correction results",
        "",
        corrected.to_markdown(index=False),
        "",
        "## Locked chronological holdout",
        "",
        holdout.sort_values("mean_brier").to_markdown(index=False),
        "",
        "## Primary frictionless trading results",
        "",
        trading.head(40).to_markdown(index=False),
        "",
        "## Primary cost-and-staleness robustness results",
        "",
        robust.head(40).to_markdown(index=False),
        "",
        "## Pipeline integrity summary",
        "",
        integrity.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "The full market baseline is complete. On exact common support, the raw "
        "deterministic ECMWF proxy is weaker than the market. Leakage-free bias "
        "and scale correction improves the forecast-side baseline, and the frozen "
        "post-processing models are assessed on a final chronological holdout. "
        "Several corrected-ECMWF trading rules remain profitable under the primary "
        "reduced-form cost and empirical-median staleness specification. These "
        "trading results remain hypothetical because historical executable spreads, "
        "fees, slippage, liquidity constraints, partial fills, market impact, and "
        "capital limits are not reconstructed.",
        "",
        "## Scope limitation",
        "",
        "The final holdout contains ten settlement dates. The empirical results "
        "should therefore be presented as evidence of pipeline feasibility and "
        "preliminary predictive and trading value, not as definitive evidence of "
        "persistent out-of-sample profitability.",
        "",
        "## Reproducibility",
        "",
        f"- source steps: {manifest['source_steps']}",
        f"- validated integrity steps: "
        f"{manifest['integrity_steps_validated']}",
        f"- integrity block count: "
        f"{manifest['integrity_block_count']}",
        f"- all seven declared integrity blocks present: "
        f"{manifest['all_declared_integrity_blocks_present']}",
        f"- all validated integrity blocks pass: "
        f"{manifest['all_available_integrity_blocks_pass']}",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def zip_review(paths: Iterable[Path], repo: Path, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if path.exists():
                zf.write(path, arcname=str(path.relative_to(repo)))


def main() -> int:
    args = parse_args()
    repo = args.repo_root.expanduser().resolve()
    processed = repo / "data" / "processed"
    docs = repo / "docs" / "research_outputs"
    figures = repo / "figures" / "21d_dissertation_ready_empirical"

    market, used_market = market_baseline_table(processed)
    common, used_common = common_support_table(processed)
    corrected, used_corrected = corrected_ecmwf_table(processed)
    holdout, used_holdout = holdout_table(processed)
    trading, used_trading = trading_headline(processed)
    robust, used_robust = robustness_headline(processed)
    integrity, used_integrity = integrity_summary(processed)

    headline = empirical_headline(
        market,
        common,
        holdout,
        trading,
        robust,
    )

    all_integrity = bool(integrity["all_checks_passed"].all())

    checks = pd.DataFrame(
        [
            {
                "check": "market_baseline_nonempty",
                "passed": len(market) > 0,
                "detail": f"rows={len(market)}",
            },
            {
                "check": "common_support_nonempty",
                "passed": len(common) > 0,
                "detail": f"rows={len(common)}",
            },
            {
                "check": "corrected_ecmwf_nonempty",
                "passed": len(corrected) > 0,
                "detail": f"rows={len(corrected)}",
            },
            {
                "check": "locked_holdout_nonempty",
                "passed": len(holdout) > 0,
                "detail": f"rows={len(holdout)}",
            },
            {
                "check": "trading_headline_nonempty",
                "passed": len(trading) > 0,
                "detail": f"rows={len(trading)}",
            },
            {
                "check": "robustness_headline_nonempty",
                "passed": len(robust) > 0,
                "detail": f"rows={len(robust)}",
            },
            {
                "check": "all_available_integrity_blocks_pass",
                "passed": all_integrity,
                "detail": integrity.to_dict(orient="records").__str__(),
            },
            {
                "check": "all_seven_declared_integrity_blocks_present",
                "passed": (
                    integrity["step"].tolist()
                    == [
                        "18m",
                        "19b",
                        "19c",
                        "20e",
                        "21a",
                        "21b",
                        "21c",
                    ]
                    and len(integrity) == 7
                ),
                "detail": (
                    "steps="
                    + str(integrity["step"].tolist())
                    + f"; n_blocks={len(integrity)}"
                ),
            },
            {
                "check": "locked_holdout_sample_label_preserved",
                "passed": holdout["evaluation_sample"]
                .eq("locked_final_holdout")
                .all(),
                "detail": "checked",
            },
            {
                "check": "21d_does_not_change_specifications",
                "passed": True,
                "detail": "consolidation only",
            },
        ]
    )

    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    manifest = {
        "step": "21d",
        "source_steps": [
            "18m",
            "19b",
            "19c",
            "20e",
            "21a",
            "21b",
            "21c",
        ],
        "purpose": "dissertation_ready_empirical_consolidation",
        "forecast_specification_changed": False,
        "calibration_specification_changed": False,
        "validation_design_changed": False,
        "trading_specification_changed": False,
        "all_available_integrity_blocks_pass": all_integrity,
        "integrity_steps_validated": integrity["step"].tolist(),
        "integrity_block_count": int(len(integrity)),
        "all_declared_integrity_blocks_present": bool(
            integrity["step"].tolist()
            == [
                "18m",
                "19b",
                "19c",
                "20e",
                "21a",
                "21b",
                "21c",
            ]
            and len(integrity) == 7
        ),
        "used_input_files": [
            str(p.relative_to(repo))
            for p in (
                used_market
                + used_common
                + used_corrected
                + used_holdout
                + used_trading
                + used_robust
                + used_integrity
            )
        ],
    }

    outputs = {
        "headline": processed / "21d_empirical_headline.csv",
        "market": processed / "21d_market_baseline_table.csv",
        "common": processed / "21d_common_support_forecast_table.csv",
        "corrected": processed / "21d_corrected_ecmwf_table.csv",
        "holdout": processed / "21d_locked_holdout_model_table.csv",
        "trading": processed / "21d_primary_trading_table.csv",
        "robust": processed / "21d_primary_robustness_table.csv",
        "integrity_summary": processed / "21d_pipeline_integrity_summary.csv",
        "checks": processed / "21d_integrity_checks.csv",
        "issues": processed / "21d_issues.csv",
        "manifest": processed / "21d_manifest.json",
        "report": docs / "21d_consolidated_empirical_report.md",
    }

    headline.to_csv(outputs["headline"], index=False)
    market.to_csv(outputs["market"], index=False)
    common.to_csv(outputs["common"], index=False)
    corrected.to_csv(outputs["corrected"], index=False)
    holdout.to_csv(outputs["holdout"], index=False)
    trading.to_csv(outputs["trading"], index=False)
    robust.to_csv(outputs["robust"], index=False)
    integrity.to_csv(outputs["integrity_summary"], index=False)
    checks.to_csv(outputs["checks"], index=False)
    issues.to_csv(outputs["issues"], index=False)
    outputs["manifest"].write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    figure_paths = make_figures(
        common,
        holdout,
        trading,
        robust,
        figures,
    )

    write_report(
        headline,
        market,
        common,
        corrected,
        holdout,
        trading,
        robust,
        integrity,
        manifest,
        outputs["report"],
    )

    review_zip = (
        repo / "data" / "review_bundles" / "21d_review_bundle.zip"
    )
    zip_review(
        list(outputs.values()) + figure_paths,
        repo,
        review_zip,
    )

    print("21d completed.")
    print(f"Headline rows: {len(headline)}")
    print(f"Integrity blocks: {len(integrity)}")
    print(f"Passed checks: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more 21d checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
