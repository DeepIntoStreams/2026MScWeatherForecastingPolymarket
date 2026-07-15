#!/usr/bin/env python3
"""
20b: Freeze date-grouped cross-validation and chronological holdout design.

This step does not fit any forecasting model. It creates immutable date-level split
assignments for the supervised matrix produced by 20a.

Design:
- Entire HKO event dates remain together.
- Final chronological holdout is the latest 20% of dates, with a minimum of 8 dates.
- The remaining development dates are split into expanding-window validation folds.
- Every validation fold occurs strictly after its training dates.
- All split metadata are written explicitly for reproducibility.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


STEP = "20b"
DECISION_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]


@dataclass(frozen=True)
class Config:
    repo_root: Path
    holdout_fraction: float
    min_holdout_dates: int
    n_cv_folds: int
    min_train_dates: int


def parse_args() -> Config:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--holdout-fraction", type=float, default=0.20)
    parser.add_argument("--min-holdout-dates", type=int, default=8)
    parser.add_argument("--n-cv-folds", type=int, default=4)
    parser.add_argument("--min-train-dates", type=int, default=16)
    args = parser.parse_args()

    if not (0 < args.holdout_fraction < 0.5):
        raise ValueError("--holdout-fraction must lie in (0, 0.5).")
    if args.min_holdout_dates < 1:
        raise ValueError("--min-holdout-dates must be positive.")
    if args.n_cv_folds < 2:
        raise ValueError("--n-cv-folds must be at least 2.")
    if args.min_train_dates < 5:
        raise ValueError("--min-train-dates must be at least 5.")

    return Config(
        repo_root=args.repo_root.expanduser().resolve(),
        holdout_fraction=float(args.holdout_fraction),
        min_holdout_dates=int(args.min_holdout_dates),
        n_cv_folds=int(args.n_cv_folds),
        min_train_dates=int(args.min_train_dates),
    )


def read_matrix(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing 20a matrix: {path}")
    df = pd.read_csv(path, low_memory=False)
    required = {"event_date", "decision_rule", "target_Y_event"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"20a matrix missing required columns: {missing}")

    df["event_date"] = pd.to_datetime(df["event_date"], errors="raise").dt.normalize()
    if "date_group_id" not in df.columns:
        unique_dates = sorted(df["event_date"].drop_duplicates())
        group_map = {d: f"date_{i:03d}" for i, d in enumerate(unique_dates, start=1)}
        df["date_group_id"] = df["event_date"].map(group_map)

    if "eligible_combined" not in df.columns:
        df["eligible_combined"] = True

    return df


def compute_date_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby(["event_date", "date_group_id"], as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_positive=("target_Y_event", "sum"),
            n_decision_rules=("decision_rule", "nunique"),
            n_event_types=("contract_event_type_v2", "nunique")
            if "contract_event_type_v2" in df.columns
            else ("decision_rule", "size"),
            n_eligible_combined=("eligible_combined", "sum"),
        )
        .sort_values("event_date")
        .reset_index(drop=True)
    )
    g["date_index"] = np.arange(1, len(g) + 1)
    g["outcome_rate"] = g["n_positive"] / g["n_rows"]
    return g


def choose_holdout_count(n_dates: int, fraction: float, minimum: int, min_train_dates: int) -> int:
    proposed = max(minimum, int(math.ceil(n_dates * fraction)))
    max_allowed = n_dates - min_train_dates
    if max_allowed < 1:
        raise ValueError(
            f"Only {n_dates} dates are available, fewer than required for "
            f"{min_train_dates} development dates plus holdout."
        )
    return min(proposed, max_allowed)


def contiguous_blocks(items: list[pd.Timestamp], n_blocks: int) -> list[list[pd.Timestamp]]:
    arrays = np.array_split(np.array(items, dtype="datetime64[ns]"), n_blocks)
    return [[pd.Timestamp(x).normalize() for x in arr.tolist()] for arr in arrays if len(arr)]


def build_expanding_folds(
    development_dates: list[pd.Timestamp],
    n_folds: int,
    min_train_dates: int,
) -> pd.DataFrame:
    n_dev = len(development_dates)
    remaining = n_dev - min_train_dates
    if remaining < n_folds:
        raise ValueError(
            f"Development period has {n_dev} dates; not enough for "
            f"{min_train_dates} initial training dates and {n_folds} validation folds."
        )

    validation_dates = development_dates[min_train_dates:]
    validation_blocks = contiguous_blocks(validation_dates, n_folds)

    rows: list[dict] = []
    for fold_id, block in enumerate(validation_blocks, start=1):
        validation_start = min(block)
        train_dates = [d for d in development_dates if d < validation_start]
        if len(train_dates) < min_train_dates:
            raise AssertionError("Fold training period is shorter than min_train_dates.")

        for d in development_dates:
            if d in train_dates:
                role = "train"
            elif d in block:
                role = "validation"
            else:
                role = "unused"
            rows.append(
                {
                    "cv_fold": fold_id,
                    "event_date": d,
                    "cv_role": role,
                    "train_start_date": min(train_dates),
                    "train_end_date": max(train_dates),
                    "validation_start_date": min(block),
                    "validation_end_date": max(block),
                    "n_train_dates": len(train_dates),
                    "n_validation_dates": len(block),
                }
            )
    return pd.DataFrame(rows)


def add_row_assignments(
    matrix: pd.DataFrame,
    date_summary: pd.DataFrame,
    holdout_dates: set[pd.Timestamp],
) -> pd.DataFrame:
    assignment = date_summary[
        ["event_date", "date_group_id", "date_index"]
    ].copy()
    assignment["sample_partition"] = np.where(
        assignment["event_date"].isin(holdout_dates),
        "final_holdout",
        "development",
    )

    out = matrix.merge(
        assignment,
        on=["event_date", "date_group_id"],
        how="left",
        validate="many_to_one",
    )
    return out


def make_integrity_checks(
    matrix: pd.DataFrame,
    date_summary: pd.DataFrame,
    folds: pd.DataFrame,
    row_assignments: pd.DataFrame,
    holdout_dates: list[pd.Timestamp],
    config: Config,
) -> pd.DataFrame:
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    add("matrix_nonempty", len(matrix) > 0, f"rows={len(matrix)}")
    add(
        "unique_date_group_mapping",
        date_summary["event_date"].nunique() == date_summary["date_group_id"].nunique(),
        f"dates={date_summary['event_date'].nunique()}, groups={date_summary['date_group_id'].nunique()}",
    )
    add(
        "holdout_nonempty",
        len(holdout_dates) > 0,
        f"holdout_dates={len(holdout_dates)}",
    )
    dev_dates = sorted(set(date_summary["event_date"]) - set(holdout_dates))
    add(
        "holdout_strictly_after_development",
        max(dev_dates) < min(holdout_dates),
        f"development_end={max(dev_dates).date()}, holdout_start={min(holdout_dates).date()}",
    )
    add(
        "minimum_development_dates",
        len(dev_dates) >= config.min_train_dates,
        f"development_dates={len(dev_dates)}, minimum={config.min_train_dates}",
    )
    add(
        "all_rows_assigned",
        row_assignments["sample_partition"].notna().all(),
        f"missing={int(row_assignments['sample_partition'].isna().sum())}",
    )
    add(
        "no_date_split_between_development_and_holdout",
        row_assignments.groupby("event_date")["sample_partition"].nunique().max() == 1,
        "each date has one final partition",
    )
    add(
        "cv_fold_count",
        folds["cv_fold"].nunique() == config.n_cv_folds,
        f"folds={folds['cv_fold'].nunique()}",
    )

    leakage_count = 0
    validation_overlap = 0
    for fold_id, group in folds.groupby("cv_fold"):
        train_dates = set(group.loc[group["cv_role"] == "train", "event_date"])
        val_dates = set(group.loc[group["cv_role"] == "validation", "event_date"])
        validation_overlap += len(train_dates & val_dates)
        if train_dates and val_dates and max(train_dates) >= min(val_dates):
            leakage_count += 1

    add(
        "cv_train_precedes_validation",
        leakage_count == 0,
        f"violating_folds={leakage_count}",
    )
    add(
        "cv_train_validation_disjoint",
        validation_overlap == 0,
        f"overlap_dates={validation_overlap}",
    )

    validation_counts = (
        folds.loc[folds["cv_role"] == "validation"]
        .groupby("event_date")["cv_fold"]
        .nunique()
    )
    add(
        "each_post_initial_date_validated_once",
        (validation_counts == 1).all(),
        f"validated_dates={len(validation_counts)}",
    )
    add(
        "holdout_excluded_from_cv",
        not set(holdout_dates) & set(folds["event_date"]),
        "final holdout dates do not appear in CV assignments",
    )
    add(
        "binary_target_valid",
        row_assignments["target_Y_event"].dropna().isin([0, 1]).all(),
        f"bad={int((~row_assignments['target_Y_event'].dropna().isin([0,1])).sum())}",
    )

    if "contract_event_type_v2" in row_assignments.columns:
        holdout_types = row_assignments.loc[
            row_assignments["sample_partition"] == "final_holdout",
            "contract_event_type_v2",
        ].nunique()
        add(
            "holdout_contains_event_types",
            holdout_types >= 2,
            f"event_types={holdout_types}",
        )

    return pd.DataFrame(checks)


def build_fold_row_panel(
    row_assignments: pd.DataFrame,
    folds: pd.DataFrame,
) -> pd.DataFrame:
    development = row_assignments.loc[
        row_assignments["sample_partition"] == "development"
    ].copy()
    fold_cols = [
        "cv_fold",
        "event_date",
        "cv_role",
        "train_start_date",
        "train_end_date",
        "validation_start_date",
        "validation_end_date",
        "n_train_dates",
        "n_validation_dates",
    ]
    panel = development.merge(
        folds[fold_cols],
        on="event_date",
        how="left",
        validate="many_to_many",
    )
    return panel


def fold_summary(fold_row_panel: pd.DataFrame) -> pd.DataFrame:
    used = fold_row_panel.loc[fold_row_panel["cv_role"].isin(["train", "validation"])].copy()
    summary = (
        used.groupby(["cv_fold", "cv_role"], as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_dates=("event_date", "nunique"),
            n_positive=("target_Y_event", "sum"),
            outcome_rate=("target_Y_event", "mean"),
            first_date=("event_date", "min"),
            last_date=("event_date", "max"),
        )
        .sort_values(["cv_fold", "cv_role"])
    )
    if "decision_rule" in used.columns:
        decision = (
            used.groupby(["cv_fold", "cv_role", "decision_rule"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        summary = summary.merge(decision, on=["cv_fold", "cv_role"], how="left")
    return summary


def final_partition_summary(row_assignments: pd.DataFrame) -> pd.DataFrame:
    return (
        row_assignments.groupby("sample_partition", as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_dates=("event_date", "nunique"),
            n_positive=("target_Y_event", "sum"),
            outcome_rate=("target_Y_event", "mean"),
            first_date=("event_date", "min"),
            last_date=("event_date", "max"),
        )
        .sort_values("sample_partition")
    )


def write_figures(
    date_summary: pd.DataFrame,
    folds: pd.DataFrame,
    row_assignments: pd.DataFrame,
    figure_dir: Path,
) -> list[Path]:
    import matplotlib.pyplot as plt

    figure_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    fig, ax = plt.subplots(figsize=(13, 4.5))
    partition_by_date = (
        row_assignments[["event_date", "sample_partition"]]
        .drop_duplicates()
        .sort_values("event_date")
    )
    y = np.where(partition_by_date["sample_partition"].eq("final_holdout"), 1, 0)
    ax.scatter(partition_by_date["event_date"], y, s=60)
    ax.set_yticks([0, 1], ["Development", "Final holdout"])
    ax.set_title("Frozen chronological development and holdout dates")
    ax.set_xlabel("HKO settlement date")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    p = figure_dir / "20b_final_chronological_partition.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    validation = folds.loc[folds["cv_role"] == "validation"].copy()
    fig, ax = plt.subplots(figsize=(13, 5))
    for fold_id, group in validation.groupby("cv_fold"):
        ax.scatter(
            group["event_date"],
            np.full(len(group), fold_id),
            s=70,
            label=f"Fold {fold_id}",
        )
    ax.set_yticks(sorted(validation["cv_fold"].unique()))
    ax.set_ylabel("Validation fold")
    ax.set_xlabel("HKO settlement date")
    ax.set_title("Expanding-window date-grouped validation blocks")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    p = figure_dir / "20b_expanding_window_validation_blocks.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.plot(date_summary["event_date"], date_summary["outcome_rate"], marker="o")
    ax.set_title("Contract-level positive-outcome share by settlement date")
    ax.set_ylabel("Positive share")
    ax.set_xlabel("HKO settlement date")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    p = figure_dir / "20b_date_level_target_prevalence.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    outputs.append(p)

    return outputs


def serialise_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out


def write_report(
    config: Config,
    date_summary: pd.DataFrame,
    folds: pd.DataFrame,
    fold_summary_df: pd.DataFrame,
    final_summary: pd.DataFrame,
    checks: pd.DataFrame,
    report_path: Path,
) -> None:
    holdout_dates = date_summary.loc[
        date_summary["sample_partition"] == "final_holdout", "event_date"
    ]
    dev_dates = date_summary.loc[
        date_summary["sample_partition"] == "development", "event_date"
    ]

    lines = [
        "# 20b date-grouped cross-validation and chronological holdout design",
        "",
        "## Purpose",
        "",
        "This step freezes the supervised-learning evaluation design before any tree-based model is fitted.",
        "All contracts from the same HKO settlement date remain in the same partition.",
        "",
        "## Frozen design",
        "",
        f"- Total settlement dates: `{len(date_summary)}`",
        f"- Development dates: `{len(dev_dates)}`",
        f"- Final chronological holdout dates: `{len(holdout_dates)}`",
        f"- Final holdout begins: `{holdout_dates.min().date()}`",
        f"- Final holdout ends: `{holdout_dates.max().date()}`",
        f"- Expanding-window validation folds: `{config.n_cv_folds}`",
        f"- Initial minimum training dates: `{config.min_train_dates}`",
        "",
        "The final holdout is never used for feature selection, hyperparameter comparison, calibration fitting, or early stopping.",
        "",
        "## Final partition summary",
        "",
        serialise_dates(final_summary).to_markdown(index=False),
        "",
        "## Cross-validation fold summary",
        "",
        serialise_dates(fold_summary_df).to_markdown(index=False),
        "",
        "## Integrity checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "The effective independent sample size is the number of settlement dates rather than the number of contract rows. "
        "The expanding-window design preserves chronology and prevents contracts from the same daily event book from being split across training and validation.",
        "",
        "## Restrictions for 20c",
        "",
        "1. Do not reshuffle rows or dates.",
        "2. Do not inspect final-holdout scores during hyperparameter selection.",
        "3. Fit preprocessing, calibration and class-weight choices using training dates only.",
        "4. Report both contract-level proper scores and date-aggregated paired score differences.",
        "5. Keep tree complexity modest because the development sample contains few independent dates.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def zip_review_bundle(paths: Iterable[Path], repo_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            if path.exists():
                zf.write(path, arcname=str(path.relative_to(repo_root)))


def main() -> int:
    config = parse_args()
    repo = config.repo_root
    processed = repo / "data" / "processed"
    figures = repo / "figures" / "20b_validation_design"
    docs = repo / "docs" / "research_outputs"

    matrix_path = processed / "20a_supervised_feature_matrix.csv"
    matrix = read_matrix(matrix_path)
    date_summary = compute_date_summary(matrix)

    n_holdout = choose_holdout_count(
        len(date_summary),
        config.holdout_fraction,
        config.min_holdout_dates,
        config.min_train_dates,
    )
    all_dates = date_summary["event_date"].tolist()
    holdout_dates = all_dates[-n_holdout:]
    development_dates = all_dates[:-n_holdout]

    folds = build_expanding_folds(
        development_dates,
        config.n_cv_folds,
        config.min_train_dates,
    )
    row_assignments = add_row_assignments(matrix, date_summary, set(holdout_dates))
    fold_row_panel = build_fold_row_panel(row_assignments, folds)
    fold_summary_df = fold_summary(fold_row_panel)
    final_summary = final_partition_summary(row_assignments)

    date_summary = date_summary.merge(
        row_assignments[["event_date", "sample_partition"]].drop_duplicates(),
        on="event_date",
        how="left",
        validate="one_to_one",
    )

    checks = make_integrity_checks(
        matrix,
        date_summary,
        folds,
        row_assignments,
        holdout_dates,
        config,
    )

    issues = checks.loc[~checks["passed"]].copy()
    if issues.empty:
        issues = pd.DataFrame(columns=["check", "passed", "detail"])

    split_manifest = {
        "step": STEP,
        "design": "date_grouped_expanding_window_with_final_chronological_holdout",
        "total_dates": len(all_dates),
        "development_dates": len(development_dates),
        "final_holdout_dates": len(holdout_dates),
        "holdout_fraction_requested": config.holdout_fraction,
        "holdout_start_date": min(holdout_dates).strftime("%Y-%m-%d"),
        "holdout_end_date": max(holdout_dates).strftime("%Y-%m-%d"),
        "n_cv_folds": config.n_cv_folds,
        "min_train_dates": config.min_train_dates,
        "final_holdout_locked": True,
        "random_seed_required": False,
    }

    output_paths = {
        "date_assignments": processed / "20b_date_partition_assignments.csv",
        "row_assignments": processed / "20b_supervised_row_partition_assignments.csv",
        "cv_date_assignments": processed / "20b_cv_date_assignments.csv",
        "cv_row_panel": processed / "20b_cv_row_assignment_panel.csv",
        "cv_summary": processed / "20b_cv_fold_summary.csv",
        "final_summary": processed / "20b_final_partition_summary.csv",
        "checks": processed / "20b_integrity_checks.csv",
        "issues": processed / "20b_issues.csv",
        "manifest": processed / "20b_split_manifest.json",
        "report": docs / "20b_validation_design_report.md",
    }

    serialise_dates(date_summary).to_csv(output_paths["date_assignments"], index=False)
    serialise_dates(row_assignments).to_csv(output_paths["row_assignments"], index=False)
    serialise_dates(folds).to_csv(output_paths["cv_date_assignments"], index=False)
    serialise_dates(fold_row_panel).to_csv(output_paths["cv_row_panel"], index=False)
    serialise_dates(fold_summary_df).to_csv(output_paths["cv_summary"], index=False)
    serialise_dates(final_summary).to_csv(output_paths["final_summary"], index=False)
    checks.to_csv(output_paths["checks"], index=False)
    issues.to_csv(output_paths["issues"], index=False)
    output_paths["manifest"].write_text(
        json.dumps(split_manifest, indent=2),
        encoding="utf-8",
    )

    figure_paths = write_figures(date_summary, folds, row_assignments, figures)
    write_report(
        config,
        date_summary,
        folds,
        fold_summary_df,
        final_summary,
        checks,
        output_paths["report"],
    )

    review_paths = list(output_paths.values()) + figure_paths
    review_zip = repo / "data" / "review_bundles" / "20b_review_bundle.zip"
    zip_review_bundle(review_paths, repo, review_zip)

    print("20b completed.")
    print(f"Dates: {len(all_dates)}")
    print(f"Development dates: {len(development_dates)}")
    print(f"Final holdout dates: {len(holdout_dates)}")
    print(f"CV folds: {config.n_cv_folds}")
    print(f"Passed checks: {int(checks['passed'].sum())}/{len(checks)}")
    print(f"Review bundle: {review_zip}")

    if not checks["passed"].all():
        print("One or more integrity checks failed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
