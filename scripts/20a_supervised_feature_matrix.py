#!/usr/bin/env python3
"""
20a: Construct the leakage-controlled supervised feature matrix.

This step does not fit a predictive model. It converts the verified 19c
common-support panel into a reproducible tabular dataset for the later
date-grouped cross-validation and chronological holdout stages.

The output retains separate feature families for:
    1. weather-only post-processing;
    2. market-only modelling;
    3. combined market-weather modelling.

All contracts from the same HKO settlement date receive the same date_group_id.
Outcome-derived score columns from 19c are deliberately excluded from the
predictor set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


EPS = 1e-6
DECISION_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]
DECISION_HOURS = {
    "24h_prior": 24.0,
    "12h_prior": 12.0,
    "6h_prior": 6.0,
    "event_day_open": 0.0,
}
EVENT_TYPES = ["lower_tail_endpoint", "interior_bin", "upper_tail"]


@dataclass(frozen=True)
class Paths:
    root: Path
    processed: Path
    reports: Path
    figures: Path
    bundles: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--input-panel",
        type=Path,
        default=Path("data/processed/19c_common_support_calibrated_probability_panel.csv"),
    )
    parser.add_argument(
        "--input-book-panel",
        type=Path,
        default=Path("data/processed/19c_categorical_book_score_panel.csv"),
    )
    parser.add_argument(
        "--input-integrity",
        type=Path,
        default=Path("data/processed/19c_integrity_checks.csv"),
    )
    return parser.parse_args()


def resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})
        .fillna(False)
        .astype(bool)
    )


def logit(values: pd.Series | np.ndarray, eps: float = EPS) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    x = np.clip(x, eps, 1.0 - eps)
    return np.log(x / (1.0 - x))


def safe_numeric(series: pd.Series) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    return out.replace([np.inf, -np.inf], np.nan)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def normalised_entropy(probabilities: np.ndarray) -> float:
    p = np.asarray(probabilities, dtype=float)
    p = p[np.isfinite(p) & (p >= 0)]
    if p.size <= 1 or p.sum() <= 0:
        return np.nan
    p = p / p.sum()
    positive = p[p > 0]
    entropy = -np.sum(positive * np.log(positive))
    return float(entropy / np.log(p.size))


def add_book_features(
    frame: pd.DataFrame,
    probability_column: str,
    prefix: str,
) -> pd.DataFrame:
    keys = ["event_date", "decision_rule"]
    grouped = frame.groupby(keys, sort=False, dropna=False)

    total = grouped[probability_column].transform("sum")
    count = grouped[probability_column].transform("count")
    maximum = grouped[probability_column].transform("max")

    frame[f"{prefix}_book_total_probability"] = total
    frame[f"{prefix}_book_probability_normalised"] = np.where(
        total > 0,
        frame[probability_column] / total,
        np.nan,
    )
    frame[f"{prefix}_book_rank_desc"] = grouped[probability_column].rank(
        method="min", ascending=False
    )
    frame[f"{prefix}_book_top_probability"] = maximum
    frame[f"{prefix}_book_gap_to_top"] = maximum - frame[probability_column]
    frame[f"{prefix}_book_contract_count"] = count

    entropy = (
        frame.groupby(keys, sort=False, dropna=False)[probability_column]
        .apply(lambda s: normalised_entropy(s.to_numpy(dtype=float)))
        .rename(f"{prefix}_book_normalised_entropy")
        .reset_index()
    )
    frame = frame.merge(entropy, on=keys, how="left", validate="many_to_one")
    return frame


def build_feature_dictionary() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(
        name: str,
        family: str,
        dtype: str,
        description: str,
        availability: str = "decision cutoff",
    ) -> None:
        rows.append(
            {
                "feature": name,
                "family": family,
                "dtype": dtype,
                "role": "predictor",
                "availability": availability,
                "description": description,
            }
        )

    add("decision_horizon_hours", "structural", "float", "Nominal hours before the event-day reference point.")
    for rule in DECISION_ORDER:
        add(f"decision_is_{rule}", "structural", "int", f"One-hot indicator for decision rule {rule}.")
    for event_type in EVENT_TYPES:
        add(f"event_type_is_{event_type}", "structural", "int", f"One-hot indicator for event type {event_type}.")
    add("event_lower_C_finite", "structural", "float", "Finite lower event boundary in degrees Celsius; missing for a lower tail.")
    add("event_upper_C_finite", "structural", "float", "Finite upper event boundary in degrees Celsius; missing for an upper tail.")
    add("event_has_lower_bound", "structural", "int", "Indicator that the event has a finite lower boundary.")
    add("event_has_upper_bound", "structural", "int", "Indicator that the event has a finite upper boundary.")
    add("event_width_C", "structural", "float", "Width of a bounded event interval; missing for tail events.")
    add("event_midpoint_C", "structural", "float", "Midpoint of a bounded event interval; missing for tail events.")
    add("calendar_day_index", "temporal", "int", "Number of days since the first eligible event date.")
    add("calendar_month", "temporal", "int", "Calendar month of the HKO settlement date.")
    add("calendar_day_of_month", "temporal", "int", "Day of month of the HKO settlement date.")
    add("calendar_day_of_year", "temporal", "int", "Day of year of the HKO settlement date.")
    add("calendar_doy_sin", "temporal", "float", "Sine transform of day of year.")
    add("calendar_doy_cos", "temporal", "float", "Cosine transform of day of year.")

    add("forecast_hko_daily_max_C", "weather", "float", "Raw ECMWF single-run Hong Kong local-day maximum forecast.")
    add("corrected_forecast_hko_daily_max_C", "weather", "float", "Expanding-window additive-bias-corrected local-day maximum forecast.")
    add("bias_correction_C", "weather", "float", "Expanding-window additive local bias estimate.")
    add("sigma_used_C", "weather", "float", "Expanding-window residual Gaussian scale.")
    add("n_train_dates", "weather", "int", "Number of historical dates used by the leakage-controlled calibration.")
    add("p_ecmwf_raw", "weather", "float", "Raw fixed-scale Gaussian event probability.")
    add("p_ecmwf_bias_fixed_sigma", "weather", "float", "Bias-corrected event probability with fixed sigma.")
    add("p_ecmwf_bias_scale", "weather", "float", "Bias-and-scale post-processed event probability.")
    add("logit_p_ecmwf_raw", "weather", "float", "Clipped logit of the raw ECMWF proxy probability.")
    add("logit_p_ecmwf_bias_fixed_sigma", "weather", "float", "Clipped logit of the bias-corrected fixed-scale probability.")
    add("logit_p_ecmwf_bias_scale", "weather", "float", "Clipped logit of the bias-and-scale probability.")
    add("raw_forecast_minus_lower_C", "weather", "float", "Raw forecast minus finite lower event boundary.")
    add("upper_minus_raw_forecast_C", "weather", "float", "Finite upper event boundary minus raw forecast.")
    add("corrected_forecast_minus_lower_C", "weather", "float", "Corrected forecast minus finite lower event boundary.")
    add("upper_minus_corrected_forecast_C", "weather", "float", "Finite upper event boundary minus corrected forecast.")
    add("standardised_corrected_minus_lower", "weather", "float", "Corrected lower-bound margin divided by sigma.")
    add("standardised_upper_minus_corrected", "weather", "float", "Corrected upper-bound margin divided by sigma.")

    add("p_market", "market", "float", "Latest no-lookahead Polymarket YES price at the decision cutoff.")
    add("logit_p_market", "market", "float", "Clipped logit of the market-implied probability.")
    add("price_staleness_hours", "market", "float", "Hours between the selected CLOB observation and decision cutoff.")
    for prefix, label in [
        ("market", "market"),
        ("ecmwf_raw", "raw ECMWF"),
        ("ecmwf_bias_fixed_sigma", "bias-corrected fixed-scale ECMWF"),
        ("ecmwf_bias_scale", "bias-and-scale ECMWF"),
    ]:
        add(f"{prefix}_book_total_probability", "book", "float", f"Sum of {label} probabilities over the observed event book.")
        add(f"{prefix}_book_probability_normalised", "book", "float", f"Contract {label} probability normalised within the event book.")
        add(f"{prefix}_book_rank_desc", "book", "float", f"Descending probability rank within the {label} event book.")
        add(f"{prefix}_book_top_probability", "book", "float", f"Largest {label} probability in the event book.")
        add(f"{prefix}_book_gap_to_top", "book", "float", f"Gap between the book maximum and this contract's {label} probability.")
        add(f"{prefix}_book_contract_count", "book", "int", f"Number of common-support contracts in the {label} book.")
        add(f"{prefix}_book_normalised_entropy", "book", "float", f"Entropy of the normalised {label} event-book distribution.")

    for weather_name, label in [
        ("p_ecmwf_raw", "raw ECMWF"),
        ("p_ecmwf_bias_fixed_sigma", "bias-corrected fixed-scale ECMWF"),
        ("p_ecmwf_bias_scale", "bias-and-scale ECMWF"),
    ]:
        suffix = weather_name.removeprefix("p_")
        add(f"market_minus_{suffix}", "interaction", "float", f"Market probability minus {label} probability.")
        add(f"abs_market_minus_{suffix}", "interaction", "float", f"Absolute market-versus-{label} probability discrepancy.")
        add(f"logit_market_minus_{suffix}", "interaction", "float", f"Market logit minus {label} logit.")

    return rows


def write_figures(matrix: pd.DataFrame, paths: Paths, feature_columns: list[str]) -> list[Path]:
    paths.figures.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    counts = matrix.groupby("decision_rule", observed=False).size().reindex(DECISION_ORDER)
    fig, ax = plt.subplots(figsize=(9, 5))
    counts.plot(kind="bar", ax=ax)
    ax.set_title("20a supervised rows by decision rule")
    ax.set_xlabel("Decision rule")
    ax.set_ylabel("Rows")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    path = paths.figures / "20a_rows_by_decision_rule.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    outputs.append(path)

    prevalence = (
        matrix.groupby("contract_event_type_v2", observed=False)["target_Y_event"]
        .agg(["mean", "count"])
        .reindex(EVENT_TYPES)
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    prevalence["mean"].plot(kind="bar", ax=ax)
    ax.set_title("20a realised event rate by contract-event type")
    ax.set_xlabel("Contract-event type")
    ax.set_ylabel("Realised Yes frequency")
    ax.set_ylim(bottom=0)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    path = paths.figures / "20a_target_prevalence_by_event_type.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    outputs.append(path)

    missing = matrix[feature_columns].isna().mean().sort_values(ascending=False)
    missing = missing[missing > 0].head(20)
    if not missing.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        missing.sort_values().plot(kind="barh", ax=ax)
        ax.set_title("20a largest predictor missingness rates")
        ax.set_xlabel("Missing share")
        fig.tight_layout()
        path = paths.figures / "20a_feature_missingness_top20.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        outputs.append(path)

    corr_cols = [
        "p_market",
        "p_ecmwf_raw",
        "p_ecmwf_bias_fixed_sigma",
        "p_ecmwf_bias_scale",
        "forecast_hko_daily_max_C",
        "corrected_forecast_hko_daily_max_C",
        "bias_correction_C",
        "sigma_used_C",
    ]
    corr = matrix[corr_cols].corr()
    fig, ax = plt.subplots(figsize=(9, 8))
    image = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(corr_cols)), corr_cols, rotation=45, ha="right")
    ax.set_yticks(range(len(corr_cols)), corr_cols)
    ax.set_title("20a core predictor correlation matrix")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    path = paths.figures / "20a_core_predictor_correlation.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    outputs.append(path)

    return outputs


def main() -> int:
    args = parse_args()
    root = args.repo_root.expanduser().resolve()
    paths = Paths(
        root=root,
        processed=root / "data" / "processed",
        reports=root / "docs" / "research_outputs",
        figures=root / "figures" / "20a_supervised_feature_matrix",
        bundles=root / "data" / "review_bundles",
    )
    for directory in [paths.processed, paths.reports, paths.figures, paths.bundles]:
        directory.mkdir(parents=True, exist_ok=True)

    input_panel_path = resolve(root, args.input_panel)
    input_book_path = resolve(root, args.input_book_panel)
    input_integrity_path = resolve(root, args.input_integrity)

    for path in [input_panel_path, input_book_path, input_integrity_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    source = pd.read_csv(input_panel_path, low_memory=False)
    books = pd.read_csv(input_book_path, low_memory=False)
    upstream_checks = pd.read_csv(input_integrity_path)

    ensure_columns(
        source,
        [
            "event_date",
            "decision_rule",
            "_join_token",
            "market_slug",
            "contract_event_type_v2",
            "event_set_v2",
            "selected_yes_token_id",
            "Y_event_int",
            "p_market",
            "p_ecmwf_raw",
            "p_ecmwf_bias_fixed_sigma",
            "p_ecmwf_bias_scale",
            "forecast_hko_daily_max_C",
            "corrected_forecast_hko_daily_max_C",
            "bias_correction_C",
            "sigma_used_C",
            "n_train_dates",
            "training_end_date",
            "selected_run_init_utc",
            "decision_cutoff_utc",
            "price_staleness_hours",
            "event_lower_C",
            "event_upper_C",
            "calibration_ready",
        ],
        "19c common-support panel",
    )
    ensure_columns(
        books,
        [
            "event_date",
            "decision_rule",
            "n_contracts_common",
            "expected_n_contracts",
            "n_yes",
            "calibration_ready",
            "book_ready",
            "book_issue",
        ],
        "19c categorical book panel",
    )
    ensure_columns(upstream_checks, ["check", "passed", "detail"], "19c integrity checks")

    source["calibration_ready"] = as_bool(source["calibration_ready"])
    matrix = source.loc[source["calibration_ready"]].copy()
    if matrix.empty:
        raise ValueError("No calibration-ready 19c rows were found.")

    matrix["event_date"] = pd.to_datetime(matrix["event_date"], errors="raise")
    matrix["training_end_date"] = pd.to_datetime(matrix["training_end_date"], errors="coerce")
    matrix["selected_run_init_utc"] = pd.to_datetime(
        matrix["selected_run_init_utc"], utc=True, errors="coerce"
    )
    matrix["decision_cutoff_utc"] = pd.to_datetime(
        matrix["decision_cutoff_utc"], utc=True, errors="coerce"
    )
    matrix["target_Y_event"] = pd.to_numeric(matrix["Y_event_int"], errors="coerce").astype("Int64")

    unique_dates = sorted(matrix["event_date"].dropna().unique())
    date_to_group = {pd.Timestamp(date): index for index, date in enumerate(unique_dates)}
    matrix["date_group_id"] = matrix["event_date"].map(date_to_group).astype(int)
    matrix["calendar_day_index"] = (
        matrix["event_date"] - matrix["event_date"].min()
    ).dt.days.astype(int)
    matrix["calendar_month"] = matrix["event_date"].dt.month.astype(int)
    matrix["calendar_day_of_month"] = matrix["event_date"].dt.day.astype(int)
    matrix["calendar_day_of_year"] = matrix["event_date"].dt.dayofyear.astype(int)
    matrix["calendar_doy_sin"] = np.sin(
        2.0 * np.pi * matrix["calendar_day_of_year"] / 366.0
    )
    matrix["calendar_doy_cos"] = np.cos(
        2.0 * np.pi * matrix["calendar_day_of_year"] / 366.0
    )

    matrix["decision_horizon_hours"] = matrix["decision_rule"].map(DECISION_HOURS)
    for rule in DECISION_ORDER:
        matrix[f"decision_is_{rule}"] = (matrix["decision_rule"] == rule).astype(int)
    for event_type in EVENT_TYPES:
        matrix[f"event_type_is_{event_type}"] = (
            matrix["contract_event_type_v2"] == event_type
        ).astype(int)

    lower_raw = pd.to_numeric(matrix["event_lower_C"], errors="coerce")
    upper_raw = pd.to_numeric(matrix["event_upper_C"], errors="coerce")
    lower_finite = lower_raw.where(np.isfinite(lower_raw), np.nan)
    upper_finite = upper_raw.where(np.isfinite(upper_raw), np.nan)
    matrix["event_lower_C_finite"] = lower_finite
    matrix["event_upper_C_finite"] = upper_finite
    matrix["event_has_lower_bound"] = lower_finite.notna().astype(int)
    matrix["event_has_upper_bound"] = upper_finite.notna().astype(int)
    matrix["event_width_C"] = upper_finite - lower_finite
    matrix["event_midpoint_C"] = (upper_finite + lower_finite) / 2.0

    numeric_input_columns = [
        "p_market",
        "p_ecmwf_raw",
        "p_ecmwf_bias_fixed_sigma",
        "p_ecmwf_bias_scale",
        "forecast_hko_daily_max_C",
        "corrected_forecast_hko_daily_max_C",
        "bias_correction_C",
        "sigma_used_C",
        "n_train_dates",
        "price_staleness_hours",
    ]
    for column in numeric_input_columns:
        matrix[column] = safe_numeric(matrix[column])

    matrix["logit_p_market"] = logit(matrix["p_market"])
    matrix["logit_p_ecmwf_raw"] = logit(matrix["p_ecmwf_raw"])
    matrix["logit_p_ecmwf_bias_fixed_sigma"] = logit(
        matrix["p_ecmwf_bias_fixed_sigma"]
    )
    matrix["logit_p_ecmwf_bias_scale"] = logit(matrix["p_ecmwf_bias_scale"])

    matrix["raw_forecast_minus_lower_C"] = (
        matrix["forecast_hko_daily_max_C"] - lower_finite
    )
    matrix["upper_minus_raw_forecast_C"] = (
        upper_finite - matrix["forecast_hko_daily_max_C"]
    )
    matrix["corrected_forecast_minus_lower_C"] = (
        matrix["corrected_forecast_hko_daily_max_C"] - lower_finite
    )
    matrix["upper_minus_corrected_forecast_C"] = (
        upper_finite - matrix["corrected_forecast_hko_daily_max_C"]
    )
    positive_sigma = matrix["sigma_used_C"].where(matrix["sigma_used_C"] > 0)
    matrix["standardised_corrected_minus_lower"] = (
        matrix["corrected_forecast_minus_lower_C"] / positive_sigma
    )
    matrix["standardised_upper_minus_corrected"] = (
        matrix["upper_minus_corrected_forecast_C"] / positive_sigma
    )

    for probability_column, prefix in [
        ("p_market", "market"),
        ("p_ecmwf_raw", "ecmwf_raw"),
        ("p_ecmwf_bias_fixed_sigma", "ecmwf_bias_fixed_sigma"),
        ("p_ecmwf_bias_scale", "ecmwf_bias_scale"),
    ]:
        matrix = add_book_features(matrix, probability_column, prefix)

    for weather_name in [
        "p_ecmwf_raw",
        "p_ecmwf_bias_fixed_sigma",
        "p_ecmwf_bias_scale",
    ]:
        suffix = weather_name.removeprefix("p_")
        weather_logit = f"logit_{weather_name}"
        matrix[f"market_minus_{suffix}"] = matrix["p_market"] - matrix[weather_name]
        matrix[f"abs_market_minus_{suffix}"] = (
            matrix[f"market_minus_{suffix}"].abs()
        )
        matrix[f"logit_market_minus_{suffix}"] = (
            matrix["logit_p_market"] - matrix[weather_logit]
        )

    book_meta = books[
        [
            "event_date",
            "decision_rule",
            "n_contracts_common",
            "expected_n_contracts",
            "n_yes",
            "book_ready",
            "book_issue",
        ]
    ].copy()
    book_meta["event_date"] = pd.to_datetime(book_meta["event_date"], errors="raise")
    book_meta["book_ready"] = as_bool(book_meta["book_ready"])
    book_meta = book_meta.drop_duplicates(["event_date", "decision_rule"])
    matrix = matrix.merge(
        book_meta,
        on=["event_date", "decision_rule"],
        how="left",
        validate="many_to_one",
    )
    matrix["complete_book_feature_available"] = matrix["book_ready"].fillna(False).astype(int)

    dictionary_rows = build_feature_dictionary()
    feature_dictionary = pd.DataFrame(dictionary_rows)
    all_features = feature_dictionary["feature"].tolist()

    structural_features = feature_dictionary.loc[
        feature_dictionary["family"].isin(["structural", "temporal"]), "feature"
    ].tolist()
    weather_features = feature_dictionary.loc[
        feature_dictionary["family"] == "weather", "feature"
    ].tolist()
    market_features = feature_dictionary.loc[
        feature_dictionary["family"] == "market", "feature"
    ].tolist()
    book_features = feature_dictionary.loc[
        feature_dictionary["family"] == "book", "feature"
    ].tolist()
    interaction_features = feature_dictionary.loc[
        feature_dictionary["family"] == "interaction", "feature"
    ].tolist()

    market_book_features = [
        column for column in book_features if column.startswith("market_")
    ]
    weather_book_features = [
        column for column in book_features if not column.startswith("market_")
    ]

    feature_sets = {
        "weather_only": structural_features + weather_features + weather_book_features,
        "market_only": structural_features + market_features + market_book_features,
        "combined": (
            structural_features
            + weather_features
            + market_features
            + book_features
            + interaction_features
        ),
        "combined_no_book": (
            structural_features
            + weather_features
            + market_features
            + interaction_features
        ),
    }
    feature_sets = {
        name: list(dict.fromkeys(columns)) for name, columns in feature_sets.items()
    }

    missing_features = sorted(
        set(all_features).difference(matrix.columns)
    )
    if missing_features:
        raise RuntimeError(f"Feature construction failed for: {missing_features}")

    weather_required = [
        "p_ecmwf_raw",
        "p_ecmwf_bias_fixed_sigma",
        "p_ecmwf_bias_scale",
        "forecast_hko_daily_max_C",
        "corrected_forecast_hko_daily_max_C",
        "bias_correction_C",
        "sigma_used_C",
    ]
    market_required = ["p_market", "price_staleness_hours"]
    matrix["eligible_weather_only"] = matrix[weather_required].notna().all(axis=1)
    matrix["eligible_market_only"] = matrix[market_required].notna().all(axis=1)
    matrix["eligible_combined"] = (
        matrix["eligible_weather_only"] & matrix["eligible_market_only"]
    )
    matrix["eligible_complete_book_combined"] = (
        matrix["eligible_combined"]
        & matrix["complete_book_feature_available"].astype(bool)
    )

    metadata_columns = [
        "event_date",
        "date_group_id",
        "decision_rule",
        "_join_token",
        "market_slug",
        "group_item_title",
        "contract_event_type_v2",
        "event_set_v2",
        "selected_yes_token_id",
        "selected_run_init_utc",
        "decision_cutoff_utc",
        "training_end_date",
        "target_Y_event",
        "n_contracts_common",
        "expected_n_contracts",
        "n_yes",
        "book_ready",
        "book_issue",
        "complete_book_feature_available",
        "eligible_weather_only",
        "eligible_market_only",
        "eligible_combined",
        "eligible_complete_book_combined",
    ]
    metadata_columns = [column for column in metadata_columns if column in matrix.columns]

    output_columns = metadata_columns + all_features
    output_columns = list(dict.fromkeys(output_columns))
    matrix_out = matrix[output_columns].copy()
    matrix_out["event_date"] = matrix_out["event_date"].dt.strftime("%Y-%m-%d")
    for timestamp_column in [
        "selected_run_init_utc",
        "decision_cutoff_utc",
        "training_end_date",
    ]:
        if timestamp_column in matrix_out.columns:
            matrix_out[timestamp_column] = matrix_out[timestamp_column].astype(str)

    matrix_out = matrix_out.sort_values(
        ["event_date", "decision_rule", "contract_event_type_v2", "_join_token"]
    ).reset_index(drop=True)

    date_summary = (
        matrix_out.groupby(["event_date", "date_group_id"], as_index=False)
        .agg(
            n_rows=("target_Y_event", "size"),
            n_yes=("target_Y_event", "sum"),
            outcome_rate=("target_Y_event", "mean"),
            n_decision_rules=("decision_rule", "nunique"),
            n_event_types=("contract_event_type_v2", "nunique"),
            n_unique_contracts=("_join_token", "nunique"),
            n_eligible_combined=("eligible_combined", "sum"),
            n_complete_book_combined=("eligible_complete_book_combined", "sum"),
        )
        .sort_values("event_date")
    )

    missingness = pd.DataFrame(
        {
            "feature": all_features,
            "missing_count": [int(matrix_out[column].isna().sum()) for column in all_features],
            "missing_share": [float(matrix_out[column].isna().mean()) for column in all_features],
            "n_unique_nonmissing": [
                int(matrix_out[column].nunique(dropna=True)) for column in all_features
            ],
        }
    ).merge(
        feature_dictionary[["feature", "family", "description"]],
        on="feature",
        how="left",
        validate="one_to_one",
    )
    missingness = missingness.sort_values(
        ["missing_share", "family", "feature"], ascending=[False, True, True]
    )

    upstream_pass = as_bool(upstream_checks["passed"])
    duplicate_count = int(
        matrix_out.duplicated(["event_date", "decision_rule", "_join_token"]).sum()
    )
    probability_columns = [
        "p_market",
        "p_ecmwf_raw",
        "p_ecmwf_bias_fixed_sigma",
        "p_ecmwf_bias_scale",
    ]
    bad_probabilities = int(
        sum(
            (~matrix_out[column].between(0, 1, inclusive="both")).sum()
            for column in probability_columns
        )
    )
    numeric_features = matrix_out[all_features].select_dtypes(include=[np.number])
    inf_count = int(np.isinf(numeric_features.to_numpy(dtype=float)).sum())
    target_bad = int((~matrix_out["target_Y_event"].isin([0, 1])).sum())

    training_end = pd.to_datetime(matrix["training_end_date"], errors="coerce")
    event_dates = pd.to_datetime(matrix["event_date"], errors="coerce")
    future_training_rows = int((training_end >= event_dates).fillna(True).sum())
    timing_bad = int(
        (matrix["selected_run_init_utc"] > matrix["decision_cutoff_utc"])
        .fillna(True)
        .sum()
    )
    group_per_date = matrix_out.groupby("event_date")["date_group_id"].nunique()
    dates_per_group = matrix_out.groupby("date_group_id")["event_date"].nunique()

    forbidden_predictors = [
        feature
        for feature in all_features
        if any(
            token in feature.lower()
            for token in [
                "target",
                "outcome",
                "brier",
                "log_score",
                "temperature_error",
                "winning_probability",
                "n_yes",
            ]
        )
    ]

    checks = [
        ("upstream_19c_checks_passed", bool(upstream_pass.all()), f"passed={int(upstream_pass.sum())}/{len(upstream_pass)}"),
        ("source_panel_nonempty", len(source) > 0, f"rows={len(source)}"),
        ("calibration_ready_matrix_nonempty", len(matrix_out) > 0, f"rows={len(matrix_out)}"),
        ("unique_contract_date_decision_key", duplicate_count == 0, f"duplicates={duplicate_count}"),
        ("binary_target", target_bad == 0, f"bad={target_bad}"),
        ("source_probabilities_in_unit_interval", bad_probabilities == 0, f"bad={bad_probabilities}"),
        ("no_infinite_numeric_features", inf_count == 0, f"infinite={inf_count}"),
        ("one_date_group_per_event_date", bool((group_per_date == 1).all()), f"bad_dates={int((group_per_date != 1).sum())}"),
        ("one_event_date_per_date_group", bool((dates_per_group == 1).all()), f"bad_groups={int((dates_per_group != 1).sum())}"),
        ("calibration_training_strictly_historical", future_training_rows == 0, f"bad_rows={future_training_rows}"),
        ("selected_forecast_run_no_later_than_cutoff", timing_bad == 0, f"bad_rows={timing_bad}"),
        ("no_outcome_derived_predictors", len(forbidden_predictors) == 0, f"forbidden={forbidden_predictors}"),
        ("all_declared_features_present", len(missing_features) == 0, f"missing={missing_features}"),
        ("weather_feature_set_nonempty", len(feature_sets["weather_only"]) > 0, f"n={len(feature_sets['weather_only'])}"),
        ("market_feature_set_nonempty", len(feature_sets["market_only"]) > 0, f"n={len(feature_sets['market_only'])}"),
        ("combined_feature_set_nonempty", len(feature_sets["combined"]) > 0, f"n={len(feature_sets['combined'])}"),
        ("all_expected_decision_rules_present", set(DECISION_ORDER).issubset(set(matrix_out["decision_rule"])), f"observed={sorted(matrix_out['decision_rule'].unique())}"),
        ("all_expected_event_types_present", set(EVENT_TYPES).issubset(set(matrix_out["contract_event_type_v2"])), f"observed={sorted(matrix_out['contract_event_type_v2'].unique())}"),
    ]
    integrity = pd.DataFrame(checks, columns=["check", "passed", "detail"])

    issues: list[dict[str, object]] = []
    for feature, row in missingness.set_index("feature").iterrows():
        if row["missing_share"] > 0:
            issues.append(
                {
                    "issue_type": "feature_missingness",
                    "feature": feature,
                    "detail": row["description"],
                    "n_rows": int(row["missing_count"]),
                    "share": float(row["missing_share"]),
                }
            )
    incomplete_books = matrix_out.loc[
        ~matrix_out["book_ready"].fillna(False).astype(bool),
        ["event_date", "decision_rule"],
    ].drop_duplicates()
    if not incomplete_books.empty:
        issues.append(
            {
                "issue_type": "incomplete_common_support_books",
                "feature": "",
                "detail": "Book-normalised features should be treated cautiously or omitted for these date-decision groups.",
                "n_rows": int(len(incomplete_books)),
                "share": float(len(incomplete_books) / matrix_out[["event_date", "decision_rule"]].drop_duplicates().shape[0]),
            }
        )
    issues_df = pd.DataFrame(
        issues,
        columns=["issue_type", "feature", "detail", "n_rows", "share"],
    )

    output_matrix = paths.processed / "20a_supervised_feature_matrix.csv"
    output_dictionary = paths.processed / "20a_feature_dictionary.csv"
    output_date_summary = paths.processed / "20a_date_group_summary.csv"
    output_missingness = paths.processed / "20a_feature_missingness_summary.csv"
    output_integrity = paths.processed / "20a_integrity_checks.csv"
    output_issues = paths.processed / "20a_issues.csv"
    output_feature_sets = paths.processed / "20a_model_feature_sets.json"

    matrix_out.to_csv(output_matrix, index=False)
    feature_dictionary.to_csv(output_dictionary, index=False)
    date_summary.to_csv(output_date_summary, index=False)
    missingness.to_csv(output_missingness, index=False)
    integrity.to_csv(output_integrity, index=False)
    issues_df.to_csv(output_issues, index=False)
    output_feature_sets.write_text(
        json.dumps(feature_sets, indent=2, sort_keys=True), encoding="utf-8"
    )

    figure_paths = write_figures(matrix_out, paths, all_features)

    report_path = paths.reports / "20a_supervised_feature_matrix_report.md"
    family_counts = feature_dictionary.groupby("family").size().sort_index()
    decision_counts = matrix_out.groupby("decision_rule").size().reindex(DECISION_ORDER)
    event_counts = matrix_out.groupby("contract_event_type_v2").size().reindex(EVENT_TYPES)
    eligibility = {
        column: int(matrix_out[column].sum())
        for column in [
            "eligible_weather_only",
            "eligible_market_only",
            "eligible_combined",
            "eligible_complete_book_combined",
        ]
    }

    report_lines = [
        "# 20a supervised market-weather feature matrix",
        "",
        "## Purpose",
        "",
        "Construct a leakage-controlled, date-grouped feature matrix for the later tree-based supervised post-processing stage. No predictive model is fitted in this step.",
        "",
        "## Inputs",
        "",
        f"- `{input_panel_path.relative_to(root)}`",
        f"- `{input_book_path.relative_to(root)}`",
        f"- `{input_integrity_path.relative_to(root)}`",
        "",
        "## Main result",
        "",
        f"- Supervised rows: `{len(matrix_out)}`",
        f"- Unique event dates and date groups: `{matrix_out['event_date'].nunique()}`",
        f"- Unique contract-date-decision keys: `{matrix_out[['event_date', 'decision_rule', '_join_token']].drop_duplicates().shape[0]}`",
        f"- Predictors in the complete feature dictionary: `{len(all_features)}`",
        f"- Combined-model eligible rows: `{eligibility['eligible_combined']}`",
        f"- Complete-book combined eligible rows: `{eligibility['eligible_complete_book_combined']}`",
        "",
        "## Row counts by decision rule",
        "",
        decision_counts.rename("n_rows").to_frame().to_markdown(),
        "",
        "## Row counts by contract-event type",
        "",
        event_counts.rename("n_rows").to_frame().to_markdown(),
        "",
        "## Predictor families",
        "",
        family_counts.rename("n_features").to_frame().to_markdown(),
        "",
        "## Model feature sets",
        "",
        "| model feature set | number of predictors |",
        "|:--|--:|",
    ]
    report_lines.extend(
        [f"| {name} | {len(columns)} |" for name, columns in feature_sets.items()]
    )
    report_lines.extend(
        [
            "",
            "The `weather_only`, `market_only`, `combined`, and `combined_no_book` lists are stored in `data/processed/20a_model_feature_sets.json`. All contracts from the same HKO settlement date share one `date_group_id`; 20b must split by this group rather than by row.",
            "",
            "## Leakage control",
            "",
            "Only the realised binary target is retained as an outcome column. Upstream Brier scores, log scores, realised temperature errors, winning-contract probabilities, and other outcome-derived diagnostics are excluded from the predictor dictionary. The expanding ECMWF bias and scale features inherit the strict historical training rule verified in 19c.",
            "",
            "## Book features",
            "",
            "Book-normalised probabilities, ranks, entropy, totals, and gaps are observable at the decision cutoff. They are retained as optional predictors. The `combined_no_book` feature set provides a conservative specification that avoids reliance on complete event-book support.",
            "",
            "## Integrity checks",
            "",
            integrity.to_markdown(index=False),
            "",
            "## Issues and expected missingness",
            "",
            issues_df.to_markdown(index=False) if not issues_df.empty else "No issues recorded.",
            "",
            "## Outputs",
            "",
            f"- `{output_matrix.relative_to(root)}`",
            f"- `{output_dictionary.relative_to(root)}`",
            f"- `{output_feature_sets.relative_to(root)}`",
            f"- `{output_date_summary.relative_to(root)}`",
            f"- `{output_missingness.relative_to(root)}`",
            f"- `{output_integrity.relative_to(root)}`",
            f"- `{output_issues.relative_to(root)}`",
        ]
    )
    for figure_path in figure_paths:
        report_lines.append(f"- `{figure_path.relative_to(root)}`")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest_paths = [
        output_matrix,
        output_dictionary,
        output_feature_sets,
        output_date_summary,
        output_missingness,
        output_integrity,
        output_issues,
        report_path,
        *figure_paths,
    ]
    manifest = pd.DataFrame(
        [
            {
                "path": str(path.relative_to(root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in manifest_paths
        ]
    )
    manifest_path = paths.processed / "20a_output_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    manifest_paths.append(manifest_path)

    bundle_path = paths.bundles / "20a_review_bundle.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in manifest_paths:
            archive.write(path, arcname=str(path.relative_to(root)))

    print("20a complete")
    print(f"Rows: {len(matrix_out):,}")
    print(f"Dates: {matrix_out['event_date'].nunique():,}")
    print(f"Predictors: {len(all_features):,}")
    print(f"Combined eligible rows: {eligibility['eligible_combined']:,}")
    print(f"Complete-book combined rows: {eligibility['eligible_complete_book_combined']:,}")
    print(f"Integrity checks passed: {int(integrity['passed'].sum())}/{len(integrity)}")
    print(f"Review bundle: {bundle_path}")
    if not integrity["passed"].all():
        print(integrity.loc[~integrity["passed"]].to_string(index=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
