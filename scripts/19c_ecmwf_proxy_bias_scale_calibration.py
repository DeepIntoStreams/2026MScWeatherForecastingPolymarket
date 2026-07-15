#!/usr/bin/env python3
"""
19c: Leakage-free expanding-window bias and scale correction for the
temporary deterministic ECMWF Gaussian proxy.

This step:
1. Collapses contract rows to unique event-date/decision-rule temperature forecasts.
2. Estimates local forecast bias and residual scale using prior event dates only.
3. Generates out-of-sample event probabilities for the HKO event-book family.
4. Compares Polymarket, raw ECMWF proxy, bias-only ECMWF proxy, and
   bias-and-scale ECMWF proxy on exact common support.
5. Uses date-clustered paired bootstrap intervals for score differences.

The ECMWF inputs remain deterministic IFS HRES point forecasts. The corrected
probabilities are post-processed Gaussian proxy probabilities, not ECMWF ENS
or AIFS ensemble probabilities.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DECISION_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]
MODEL_ORDER = [
    "market",
    "ecmwf_raw",
    "ecmwf_bias_fixed_sigma",
    "ecmwf_bias_scale",
]
MODEL_LABELS = {
    "market": "Market",
    "ecmwf_raw": "ECMWF raw proxy",
    "ecmwf_bias_fixed_sigma": "ECMWF bias corrected, sigma=1.5",
    "ecmwf_bias_scale": "ECMWF bias-and-scale corrected",
}
PROB_COLS = {
    "market": "p_market",
    "ecmwf_raw": "p_ecmwf_raw",
    "ecmwf_bias_fixed_sigma": "p_ecmwf_bias_fixed_sigma",
    "ecmwf_bias_scale": "p_ecmwf_bias_scale",
}
EPS = 1e-6
RAW_SIGMA_C = 1.5
MIN_SIGMA_C = 0.5
MAX_SIGMA_C = 3.0
DEFAULT_MIN_TRAIN_DATES = 14
DEFAULT_BOOTSTRAP_REPS = 5000
DEFAULT_OUTCOME_AVAILABILITY_LAG_HOURS = 24
RNG_SEED = 20260715


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Leakage-free expanding-window ECMWF proxy bias and scale correction."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to auto-detection from this script.",
    )
    parser.add_argument(
        "--min-train-dates",
        type=int,
        default=DEFAULT_MIN_TRAIN_DATES,
        help="Minimum number of strictly prior event dates before out-of-sample scoring.",
    )
    parser.add_argument(
        "--bootstrap-reps",
        type=int,
        default=DEFAULT_BOOTSTRAP_REPS,
        help="Number of date-clustered bootstrap repetitions.",
    )
    parser.add_argument(
        "--outcome-availability-lag-hours",
        type=float,
        default=DEFAULT_OUTCOME_AVAILABILITY_LAG_HOURS,
        help=(
            "Conservative assumed delay from the end of an HKO local day "
            "until its realised maximum is available for model updating."
        ),
    )
    return parser.parse_args()


def detect_repo_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "data").exists() and (candidate / "scripts").exists():
            return candidate
    return Path.cwd().resolve()


def read_csv_auto(path_without_suffix: Path) -> pd.DataFrame:
    candidates = [
        path_without_suffix,
        Path(str(path_without_suffix) + ".gz"),
    ]
    for path in candidates:
        if path.exists():
            return pd.read_csv(path)
    raise FileNotFoundError(
        "Could not find either "
        + " or ".join(str(p) for p in candidates)
    )


def normal_cdf(z: np.ndarray | pd.Series | float) -> np.ndarray:
    arr = np.asarray(z, dtype=float)
    # numpy does not expose erf in all installations; vectorising math.erf
    # keeps the script independent of scipy.
    erf_vec = np.vectorize(math.erf, otypes=[float])
    return 0.5 * (1.0 + erf_vec(arr / math.sqrt(2.0)))


def brier(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return np.square(p - y)


def log_score(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    q = np.clip(p, EPS, 1.0 - EPS)
    return -(y * np.log(q) + (1.0 - y) * np.log(1.0 - q))


def extract_event_bounds(event_type: str, event_set: str) -> tuple[float, float]:
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", str(event_set))]
    if event_type == "lower_tail_endpoint":
        if len(nums) != 1:
            raise ValueError(f"Expected one upper bound for {event_set!r}")
        return -np.inf, nums[0]
    if event_type == "upper_tail":
        if len(nums) != 1:
            raise ValueError(f"Expected one lower bound for {event_set!r}")
        return nums[0], np.inf
    if event_type == "interior_bin":
        if len(nums) != 2:
            raise ValueError(f"Expected two bounds for {event_set!r}")
        return nums[0], nums[1]
    raise ValueError(f"Unknown contract_event_type_v2={event_type!r}")


def gaussian_event_probability(
    mean_c: np.ndarray,
    sigma_c: np.ndarray,
    lower_c: np.ndarray,
    upper_c: np.ndarray,
) -> np.ndarray:
    mean_c = np.asarray(mean_c, dtype=float)
    sigma_c = np.asarray(sigma_c, dtype=float)
    lower_c = np.asarray(lower_c, dtype=float)
    upper_c = np.asarray(upper_c, dtype=float)
    if np.any(~np.isfinite(mean_c)):
        raise ValueError("Non-finite Gaussian mean.")
    if np.any(~np.isfinite(sigma_c)) or np.any(sigma_c <= 0):
        raise ValueError("Gaussian sigma must be finite and positive.")

    lower_cdf = np.zeros_like(mean_c, dtype=float)
    upper_cdf = np.ones_like(mean_c, dtype=float)

    finite_lower = np.isfinite(lower_c)
    finite_upper = np.isfinite(upper_c)
    lower_cdf[finite_lower] = normal_cdf(
        (lower_c[finite_lower] - mean_c[finite_lower]) / sigma_c[finite_lower]
    )
    upper_cdf[finite_upper] = normal_cdf(
        (upper_c[finite_upper] - mean_c[finite_upper]) / sigma_c[finite_upper]
    )
    return np.clip(upper_cdf - lower_cdf, 0.0, 1.0)


def validate_common_panel(df: pd.DataFrame) -> None:
    required = {
        "event_date",
        "decision_rule",
        "selected_yes_token_id",
        "market_slug",
        "contract_event_type_v2",
        "event_set_v2",
        "Y_event_int",
        "p_market",
        "p_ecmwf_proxy",
        "forecast_hko_daily_max_C",
        "hko_tmax_C",
        "selected_run_init_utc",
        "decision_cutoff_utc",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"19b common-support panel is missing columns: {missing}")
    if df.empty:
        raise ValueError("19b common-support panel is empty.")

    key = ["event_date", "decision_rule", "selected_yes_token_id"]
    if df.duplicated(key).any():
        bad = int(df.duplicated(key, keep=False).sum())
        raise ValueError(f"Duplicate common-support keys found: rows={bad}")

    for col in ["p_market", "p_ecmwf_proxy"]:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{col} contains missing/non-numeric values.")
        if ((values < 0) | (values > 1)).any():
            raise ValueError(f"{col} contains values outside [0,1].")

    y = pd.to_numeric(df["Y_event_int"], errors="coerce")
    if not y.isin([0, 1]).all():
        raise ValueError("Y_event_int is not binary on all rows.")


def build_date_level_forecasts(
    forecast_panel: pd.DataFrame,
    outcome_availability_lag_hours: float,
) -> pd.DataFrame:
    required = {
        "event_date",
        "decision_rule",
        "forecast_hko_daily_max_C",
        "hko_tmax_C",
        "selected_run_init_utc",
        "decision_cutoff_utc",
    }
    missing = sorted(required - set(forecast_panel.columns))
    if missing:
        raise ValueError(f"Forecast calibration panel is missing columns: {missing}")

    cols = sorted(required)
    source = forecast_panel[cols].copy()
    source["forecast_hko_daily_max_C"] = pd.to_numeric(
        source["forecast_hko_daily_max_C"], errors="coerce"
    )
    source["hko_tmax_C"] = pd.to_numeric(source["hko_tmax_C"], errors="coerce")
    source = source.dropna(
        subset=[
            "event_date",
            "decision_rule",
            "forecast_hko_daily_max_C",
            "hko_tmax_C",
            "decision_cutoff_utc",
        ]
    )
    source = source.loc[source["decision_rule"].isin(DECISION_ORDER)].copy()
    date_level = source.drop_duplicates().copy()

    counts = (
        date_level.groupby(["event_date", "decision_rule"], dropna=False)
        .size()
        .reset_index(name="n_unique_forecasts")
    )
    if (counts["n_unique_forecasts"] != 1).any():
        bad = counts.loc[counts["n_unique_forecasts"] != 1]
        raise ValueError(
            "A date-decision book has multiple forecast/observation records:\n"
            + bad.to_string(index=False)
        )

    date_level["event_date"] = pd.to_datetime(date_level["event_date"]).dt.normalize()
    date_level["decision_cutoff_utc"] = pd.to_datetime(
        date_level["decision_cutoff_utc"], utc=True
    )
    date_level["selected_run_init_utc"] = pd.to_datetime(
        date_level["selected_run_init_utc"], utc=True, errors="coerce"
    )
    # An HKO local day ends at 00:00 HKT on the following local date,
    # which is 16:00 UTC on the labelled event date.
    local_day_end_utc = (
        pd.to_datetime(date_level["event_date"], utc=True)
        + pd.Timedelta(hours=16)
    )
    date_level["assumed_outcome_available_utc"] = (
        local_day_end_utc
        + pd.Timedelta(hours=float(outcome_availability_lag_hours))
    )
    date_level["raw_temperature_error_C"] = (
        date_level["forecast_hko_daily_max_C"] - date_level["hko_tmax_C"]
    )
    date_level = date_level.sort_values(
        ["decision_rule", "event_date"]
    ).reset_index(drop=True)
    return date_level

def expanding_parameters(
    date_level: pd.DataFrame,
    min_train_dates: int,
) -> pd.DataFrame:
    rows: list[dict] = []
    for rule in DECISION_ORDER:
        group = date_level.loc[
            date_level["decision_rule"].eq(rule)
        ].sort_values("event_date").reset_index(drop=True)
        for _, row in group.iterrows():
            # A historical error is admissible only if the realised HKO outcome
            # is conservatively assumed available no later than this decision cutoff.
            prior = group.loc[
                group["assumed_outcome_available_utc"]
                <= row["decision_cutoff_utc"]
            ].copy()
            # Exclude the target record explicitly, even if malformed timestamps
            # would otherwise permit it.
            prior = prior.loc[prior["event_date"] < row["event_date"]]
            ready = len(prior) >= min_train_dates
            if ready:
                training_error = prior["raw_temperature_error_C"].to_numpy(dtype=float)
                bias_correction = -float(np.mean(training_error))
                corrected_training_error = training_error + bias_correction
                sigma_mle = float(np.sqrt(np.mean(np.square(corrected_training_error))))
                sigma_used = float(np.clip(sigma_mle, MIN_SIGMA_C, MAX_SIGMA_C))
                training_start = prior["event_date"].min()
                training_end = prior["event_date"].max()
                last_outcome_available = prior["assumed_outcome_available_utc"].max()
            else:
                bias_correction = np.nan
                sigma_mle = np.nan
                sigma_used = np.nan
                training_start = pd.NaT
                training_end = pd.NaT
                last_outcome_available = pd.NaT

            corrected_mean = (
                float(row["forecast_hko_daily_max_C"]) + bias_correction
                if ready
                else np.nan
            )
            corrected_error = (
                corrected_mean - float(row["hko_tmax_C"])
                if ready
                else np.nan
            )
            rows.append(
                {
                    "event_date": row["event_date"],
                    "decision_rule": rule,
                    "calibration_ready": bool(ready),
                    "n_train_dates": int(len(prior)),
                    "training_start_date": training_start,
                    "training_end_date": training_end,
                    "training_last_outcome_available_utc": last_outcome_available,
                    "bias_correction_C": bias_correction,
                    "sigma_mle_C": sigma_mle,
                    "sigma_used_C": sigma_used,
                    "raw_forecast_hko_daily_max_C": row["forecast_hko_daily_max_C"],
                    "corrected_forecast_hko_daily_max_C": corrected_mean,
                    "hko_tmax_C": row["hko_tmax_C"],
                    "raw_temperature_error_C": row["raw_temperature_error_C"],
                    "corrected_temperature_error_C": corrected_error,
                    "selected_run_init_utc": row["selected_run_init_utc"],
                    "decision_cutoff_utc": row["decision_cutoff_utc"],
                    "assumed_outcome_available_utc": row[
                        "assumed_outcome_available_utc"
                    ],
                }
            )
    out = pd.DataFrame(rows)
    out["event_date"] = pd.to_datetime(out["event_date"]).dt.strftime("%Y-%m-%d")
    for col in ["training_start_date", "training_end_date"]:
        out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d")
    for col in [
        "training_last_outcome_available_utc",
        "selected_run_init_utc",
        "decision_cutoff_utc",
        "assumed_outcome_available_utc",
    ]:
        out[col] = pd.to_datetime(out[col], utc=True).astype("string")
    return out

def add_calibrated_probabilities(
    common: pd.DataFrame,
    parameters: pd.DataFrame,
) -> pd.DataFrame:
    panel = common.copy()
    panel["event_date"] = pd.to_datetime(panel["event_date"]).dt.strftime("%Y-%m-%d")
    merge_cols = [
        "event_date",
        "decision_rule",
        "calibration_ready",
        "n_train_dates",
        "training_start_date",
        "training_end_date",
        "training_last_outcome_available_utc",
        "bias_correction_C",
        "sigma_mle_C",
        "sigma_used_C",
        "corrected_forecast_hko_daily_max_C",
        "corrected_temperature_error_C",
    ]
    panel = panel.merge(
        parameters[merge_cols],
        on=["event_date", "decision_rule"],
        how="left",
        validate="many_to_one",
    )
    if panel["calibration_ready"].isna().any():
        raise ValueError("Some common-support rows failed to match calibration parameters.")

    bounds = panel.apply(
        lambda r: extract_event_bounds(
            str(r["contract_event_type_v2"]),
            str(r["event_set_v2"]),
        ),
        axis=1,
        result_type="expand",
    )
    bounds.columns = ["event_lower_C", "event_upper_C"]
    panel = pd.concat([panel, bounds], axis=1)

    panel["p_ecmwf_raw"] = pd.to_numeric(panel["p_ecmwf_proxy"], errors="raise")
    ready = panel["calibration_ready"].astype(bool)

    panel["p_ecmwf_bias_fixed_sigma"] = np.nan
    panel["p_ecmwf_bias_scale"] = np.nan

    if ready.any():
        idx = panel.index[ready]
        means = panel.loc[idx, "corrected_forecast_hko_daily_max_C"].to_numpy(float)
        lower = panel.loc[idx, "event_lower_C"].to_numpy(float)
        upper = panel.loc[idx, "event_upper_C"].to_numpy(float)

        panel.loc[idx, "p_ecmwf_bias_fixed_sigma"] = gaussian_event_probability(
            mean_c=means,
            sigma_c=np.full(len(idx), RAW_SIGMA_C),
            lower_c=lower,
            upper_c=upper,
        )
        panel.loc[idx, "p_ecmwf_bias_scale"] = gaussian_event_probability(
            mean_c=means,
            sigma_c=panel.loc[idx, "sigma_used_C"].to_numpy(float),
            lower_c=lower,
            upper_c=upper,
        )

    y = panel["Y_event_int"].to_numpy(float)
    for model, p_col in PROB_COLS.items():
        if model == "market":
            # p_market already exists.
            pass
        scores_ready = ready & panel[p_col].notna()
        panel[f"brier_{model}"] = np.nan
        panel[f"log_{model}"] = np.nan
        panel.loc[scores_ready, f"brier_{model}"] = brier(
            y[scores_ready.to_numpy()],
            panel.loc[scores_ready, p_col].to_numpy(float),
        )
        panel.loc[scores_ready, f"log_{model}"] = log_score(
            y[scores_ready.to_numpy()],
            panel.loc[scores_ready, p_col].to_numpy(float),
        )

    return panel


def temperature_summary(parameters: pd.DataFrame) -> pd.DataFrame:
    ready = parameters.loc[parameters["calibration_ready"].astype(bool)].copy()
    rows: list[dict] = []
    for rule in DECISION_ORDER:
        g = ready.loc[ready["decision_rule"].eq(rule)]
        for model, error_col in [
            ("ecmwf_raw_temperature", "raw_temperature_error_C"),
            ("ecmwf_bias_corrected_temperature", "corrected_temperature_error_C"),
        ]:
            e = g[error_col].to_numpy(float)
            rows.append(
                {
                    "decision_rule": rule,
                    "model": model,
                    "n_dates": int(len(g)),
                    "mean_error_C": float(np.mean(e)),
                    "mae_C": float(np.mean(np.abs(e))),
                    "rmse_C": float(np.sqrt(np.mean(np.square(e)))),
                    "median_error_C": float(np.median(e)),
                }
            )
    return pd.DataFrame(rows)


def gaussian_calibration_summary(parameters: pd.DataFrame) -> pd.DataFrame:
    ready = parameters.loc[parameters["calibration_ready"].astype(bool)].copy()
    rows: list[dict] = []
    z_quantiles = {
        "coverage_50": 0.6744897501960817,
        "coverage_80": 1.2815515655446004,
        "coverage_90": 1.6448536269514722,
    }
    for rule in DECISION_ORDER:
        g = ready.loc[ready["decision_rule"].eq(rule)].copy()
        configurations = [
            (
                "ecmwf_bias_fixed_sigma",
                np.full(len(g), RAW_SIGMA_C),
            ),
            (
                "ecmwf_bias_scale",
                g["sigma_used_C"].to_numpy(float),
            ),
        ]
        errors = g["corrected_temperature_error_C"].to_numpy(float)
        for model, sigmas in configurations:
            z = errors / sigmas
            row = {
                "decision_rule": rule,
                "model": model,
                "n_dates": int(len(g)),
                "mean_standardised_error": float(np.mean(z)),
                "std_standardised_error": float(np.std(z, ddof=0)),
                "mean_sigma_C": float(np.mean(sigmas)),
            }
            abs_z = np.abs(z)
            for name, threshold in z_quantiles.items():
                row[name] = float(np.mean(abs_z <= threshold))
            rows.append(row)
    return pd.DataFrame(rows)


def binary_score_summary(panel: pd.DataFrame) -> pd.DataFrame:
    ready = panel.loc[panel["calibration_ready"].astype(bool)].copy()
    rows: list[dict] = []
    for rule in DECISION_ORDER:
        g = ready.loc[ready["decision_rule"].eq(rule)]
        y = g["Y_event_int"].to_numpy(float)
        for model in MODEL_ORDER:
            p_col = PROB_COLS[model]
            p = g[p_col].to_numpy(float)
            bs = brier(y, p)
            ls = log_score(y, p)
            rows.append(
                {
                    "decision_rule": rule,
                    "model": model,
                    "model_label": MODEL_LABELS[model],
                    "n": int(len(g)),
                    "mean_brier": float(np.mean(bs)),
                    "mean_log_score": float(np.mean(ls)),
                    "median_brier": float(np.median(bs)),
                    "median_log_score": float(np.median(ls)),
                    "mean_probability": float(np.mean(p)),
                    "outcome_rate": float(np.mean(y)),
                }
            )
    out = pd.DataFrame(rows)
    out["brier_rank_within_rule"] = (
        out.groupby("decision_rule")["mean_brier"]
        .rank(method="min", ascending=True)
        .astype(int)
    )
    out["log_rank_within_rule"] = (
        out.groupby("decision_rule")["mean_log_score"]
        .rank(method="min", ascending=True)
        .astype(int)
    )
    return out


def binary_score_by_event_type(panel: pd.DataFrame) -> pd.DataFrame:
    ready = panel.loc[panel["calibration_ready"].astype(bool)].copy()
    rows: list[dict] = []
    event_types = [
        "lower_tail_endpoint",
        "interior_bin",
        "upper_tail",
    ]
    for rule in DECISION_ORDER:
        for event_type in event_types:
            g = ready.loc[
                ready["decision_rule"].eq(rule)
                & ready["contract_event_type_v2"].eq(event_type)
            ]
            if g.empty:
                continue
            y = g["Y_event_int"].to_numpy(float)
            for model in MODEL_ORDER:
                p = g[PROB_COLS[model]].to_numpy(float)
                rows.append(
                    {
                        "decision_rule": rule,
                        "contract_event_type_v2": event_type,
                        "model": model,
                        "model_label": MODEL_LABELS[model],
                        "n": int(len(g)),
                        "mean_brier": float(np.mean(brier(y, p))),
                        "mean_log_score": float(np.mean(log_score(y, p))),
                        "mean_probability": float(np.mean(p)),
                        "outcome_rate": float(np.mean(y)),
                    }
                )
    return pd.DataFrame(rows)


def categorical_panels(
    panel: pd.DataFrame,
    original_book_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original = original_book_panel[
        ["event_date", "decision_rule", "expected_n_contracts", "book_ready"]
    ].copy()
    original["event_date"] = pd.to_datetime(original["event_date"]).dt.strftime("%Y-%m-%d")
    original["book_ready"] = original["book_ready"].astype(bool)

    rows: list[dict] = []
    issues: list[dict] = []
    for (event_date, rule), g in panel.groupby(["event_date", "decision_rule"], sort=False):
        calibration_ready = bool(g["calibration_ready"].all())
        meta = original.loc[
            original["event_date"].eq(event_date)
            & original["decision_rule"].eq(rule)
        ]
        original_ready = bool(meta["book_ready"].iloc[0]) if len(meta) == 1 else False
        expected = (
            int(meta["expected_n_contracts"].iloc[0])
            if len(meta) == 1
            else int(g.shape[0])
        )
        n_contracts = int(len(g))
        n_yes = int(g["Y_event_int"].sum())
        book_ready = (
            calibration_ready
            and original_ready
            and n_contracts == expected
            and n_yes == 1
        )
        issue = ""
        if not calibration_ready:
            issue = "calibration_warmup"
        elif not original_ready or n_contracts != expected:
            issue = f"incomplete_common_book common={n_contracts} expected={expected}"
        elif n_yes != 1:
            issue = f"winner_count={n_yes}"

        row: dict = {
            "event_date": event_date,
            "decision_rule": rule,
            "n_contracts_common": n_contracts,
            "expected_n_contracts": expected,
            "n_yes": n_yes,
            "calibration_ready": calibration_ready,
            "original_19b_book_ready": original_ready,
            "book_ready": book_ready,
            "book_issue": issue,
        }
        y = g["Y_event_int"].to_numpy(float)
        for model in MODEL_ORDER:
            p = g[PROB_COLS[model]].to_numpy(float)
            total = float(np.sum(p))
            row[f"{model}_total_book_probability"] = total
            row[f"{model}_abs_book_probability_error"] = abs(total - 1.0)
            if book_ready and total > 0:
                pn = p / total
                winner_index = int(np.flatnonzero(y == 1)[0])
                winner_raw = float(p[winner_index])
                winner_norm = float(pn[winner_index])
                row[f"{model}_winning_probability_raw"] = winner_raw
                row[f"{model}_winning_probability_normalised"] = winner_norm
                row[f"{model}_normalised_categorical_log_score"] = float(
                    -math.log(max(winner_norm, EPS))
                )
                row[f"{model}_normalised_multiclass_brier"] = float(
                    np.sum(np.square(pn - y))
                )
            else:
                row[f"{model}_winning_probability_raw"] = np.nan
                row[f"{model}_winning_probability_normalised"] = np.nan
                row[f"{model}_normalised_categorical_log_score"] = np.nan
                row[f"{model}_normalised_multiclass_brier"] = np.nan
        rows.append(row)
        if issue and issue != "calibration_warmup":
            issues.append(
                {
                    "issue_type": "categorical_book_not_ready",
                    "event_date": event_date,
                    "decision_rule": rule,
                    "detail": issue,
                    "n_contracts_common": n_contracts,
                    "expected_n_contracts": expected,
                    "n_yes": n_yes,
                }
            )

    book_panel = pd.DataFrame(rows)
    ready_books = book_panel.loc[book_panel["book_ready"]].copy()

    summary_rows: list[dict] = []
    for rule in DECISION_ORDER:
        g = ready_books.loc[ready_books["decision_rule"].eq(rule)]
        for model in MODEL_ORDER:
            summary_rows.append(
                {
                    "decision_rule": rule,
                    "model": model,
                    "model_label": MODEL_LABELS[model],
                    "n_books": int(len(g)),
                    "mean_total_book_probability": float(
                        g[f"{model}_total_book_probability"].mean()
                    ),
                    "mean_abs_book_probability_error": float(
                        g[f"{model}_abs_book_probability_error"].mean()
                    ),
                    "median_winning_probability_normalised": float(
                        g[f"{model}_winning_probability_normalised"].median()
                    ),
                    "mean_normalised_categorical_log_score": float(
                        g[f"{model}_normalised_categorical_log_score"].mean()
                    ),
                    "mean_normalised_multiclass_brier": float(
                        g[f"{model}_normalised_multiclass_brier"].mean()
                    ),
                }
            )
    summary = pd.DataFrame(summary_rows)
    summary["categorical_log_rank_within_rule"] = (
        summary.groupby("decision_rule")["mean_normalised_categorical_log_score"]
        .rank(method="min", ascending=True)
        .astype(int)
    )
    summary["multiclass_brier_rank_within_rule"] = (
        summary.groupby("decision_rule")["mean_normalised_multiclass_brier"]
        .rank(method="min", ascending=True)
        .astype(int)
    )
    return book_panel, summary, pd.DataFrame(issues)


def date_level_score_panel(panel: pd.DataFrame) -> pd.DataFrame:
    ready = panel.loc[panel["calibration_ready"].astype(bool)].copy()
    agg: dict[str, tuple[str, str]] = {
        "n_contracts": ("Y_event_int", "size"),
        "outcome_count": ("Y_event_int", "sum"),
    }
    for model in MODEL_ORDER:
        agg[f"mean_brier_{model}"] = (f"brier_{model}", "mean")
        agg[f"mean_log_{model}"] = (f"log_{model}", "mean")
    return (
        ready.groupby(["event_date", "decision_rule"], as_index=False)
        .agg(**agg)
        .sort_values(["decision_rule", "event_date"])
    )


def bootstrap_mean_ci(
    values: np.ndarray,
    reps: int,
    rng: np.random.Generator,
) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return np.nan, np.nan, np.nan
    draws = rng.choice(values, size=(reps, len(values)), replace=True)
    means = draws.mean(axis=1)
    return (
        float(np.mean(values)),
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
    )


def paired_date_comparisons(
    date_scores: pd.DataFrame,
    bootstrap_reps: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    comparisons = [
        ("ecmwf_bias_fixed_sigma", "ecmwf_raw"),
        ("ecmwf_bias_scale", "ecmwf_raw"),
        ("market", "ecmwf_bias_scale"),
    ]
    rows: list[dict] = []
    for rule in DECISION_ORDER:
        g = date_scores.loc[date_scores["decision_rule"].eq(rule)]
        for model_a, model_b in comparisons:
            for metric in ["brier", "log"]:
                difference = (
                    g[f"mean_{metric}_{model_a}"]
                    - g[f"mean_{metric}_{model_b}"]
                ).to_numpy(float)
                mean_diff, ci_low, ci_high = bootstrap_mean_ci(
                    difference,
                    bootstrap_reps,
                    rng,
                )
                rows.append(
                    {
                        "decision_rule": rule,
                        "metric": metric,
                        "model_a": model_a,
                        "model_b": model_b,
                        "difference_definition": "model_a_minus_model_b",
                        "n_dates": int(len(g)),
                        "mean_difference": mean_diff,
                        "bootstrap_ci_2_5": ci_low,
                        "bootstrap_ci_97_5": ci_high,
                        "lower_score_better": True,
                        "favours_model_a": bool(ci_high < 0),
                        "favours_model_b": bool(ci_low > 0),
                    }
                )
    return pd.DataFrame(rows)


def decision_rule_rankings(
    binary_summary: pd.DataFrame,
    categorical_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []
    for _, r in binary_summary.iterrows():
        rows.extend(
            [
                {
                    "metric": "binary_mean_brier",
                    "decision_rule": r["decision_rule"],
                    "model": r["model"],
                    "value": r["mean_brier"],
                },
                {
                    "metric": "binary_mean_log_score",
                    "decision_rule": r["decision_rule"],
                    "model": r["model"],
                    "value": r["mean_log_score"],
                },
            ]
        )
    for _, r in categorical_summary.iterrows():
        rows.extend(
            [
                {
                    "metric": "normalised_categorical_log_score",
                    "decision_rule": r["decision_rule"],
                    "model": r["model"],
                    "value": r["mean_normalised_categorical_log_score"],
                },
                {
                    "metric": "normalised_multiclass_brier",
                    "decision_rule": r["decision_rule"],
                    "model": r["model"],
                    "value": r["mean_normalised_multiclass_brier"],
                },
            ]
        )
    out = pd.DataFrame(rows)
    out["rank_within_decision_rule"] = (
        out.groupby(["metric", "decision_rule"])["value"]
        .rank(method="min", ascending=True)
        .astype(int)
    )
    out["rank_across_all_rule_model_pairs"] = (
        out.groupby("metric")["value"]
        .rank(method="min", ascending=True)
        .astype(int)
    )
    return out.sort_values(
        ["metric", "rank_across_all_rule_model_pairs", "decision_rule", "model"]
    )


def integrity_checks(
    common: pd.DataFrame,
    parameters: pd.DataFrame,
    panel: pd.DataFrame,
    binary_summary: pd.DataFrame,
    book_panel: pd.DataFrame,
    categorical_summary: pd.DataFrame,
) -> pd.DataFrame:
    ready = panel["calibration_ready"].astype(bool)
    checks: list[dict] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    add("common_input_nonempty", not common.empty, f"rows={len(common)}")
    add(
        "date_level_parameters_nonempty",
        not parameters.empty,
        f"rows={len(parameters)}",
    )
    add(
        "some_out_of_sample_dates_ready",
        int(parameters["calibration_ready"].sum()) > 0,
        f"ready_date_rules={int(parameters['calibration_ready'].sum())}",
    )
    ready_parameters = parameters.loc[parameters["calibration_ready"]].copy()
    add(
        "training_uses_only_available_outcomes",
        bool(
            (
                pd.to_datetime(
                    ready_parameters["training_last_outcome_available_utc"],
                    utc=True,
                )
                <= pd.to_datetime(
                    ready_parameters["decision_cutoff_utc"],
                    utc=True,
                )
            ).all()
        ),
        "last assumed outcome availability <= decision cutoff",
    )
    add(
        "training_uses_strictly_earlier_event_dates",
        bool(
            (
                pd.to_datetime(ready_parameters["training_end_date"])
                < pd.to_datetime(ready_parameters["event_date"])
            ).all()
        ),
        "training_end_date < event_date",
    )
    add(
        "corrected_probabilities_present_on_ready_rows",
        bool(
            panel.loc[
                ready,
                ["p_ecmwf_bias_fixed_sigma", "p_ecmwf_bias_scale"],
            ].notna().all().all()
        ),
        f"ready_rows={int(ready.sum())}",
    )
    prob_cols = list(PROB_COLS.values())
    probs = panel.loc[ready, prob_cols]
    add(
        "all_ready_probabilities_in_unit_interval",
        bool(((probs >= 0) & (probs <= 1)).all().all()),
        "checked all four models",
    )
    add(
        "adaptive_sigma_within_bounds",
        bool(
            parameters.loc[
                parameters["calibration_ready"], "sigma_used_C"
            ].between(MIN_SIGMA_C, MAX_SIGMA_C).all()
        ),
        f"bounds=[{MIN_SIGMA_C},{MAX_SIGMA_C}]",
    )
    add(
        "binary_summary_complete",
        len(binary_summary) == len(DECISION_ORDER) * len(MODEL_ORDER),
        f"rows={len(binary_summary)}",
    )
    add(
        "categorical_panel_nonempty",
        not book_panel.empty,
        f"rows={len(book_panel)}",
    )
    add(
        "some_categorical_books_ready",
        int(book_panel["book_ready"].sum()) > 0,
        f"ready={int(book_panel['book_ready'].sum())}",
    )
    add(
        "categorical_ready_books_have_one_winner",
        bool(
            book_panel.loc[book_panel["book_ready"], "n_yes"].eq(1).all()
        ),
        "checked ready books",
    )
    add(
        "gaussian_complete_books_sum_to_one",
        bool(
            np.allclose(
                book_panel.loc[
                    book_panel["book_ready"],
                    [
                        "ecmwf_raw_total_book_probability",
                        "ecmwf_bias_fixed_sigma_total_book_probability",
                        "ecmwf_bias_scale_total_book_probability",
                    ],
                ].to_numpy(float),
                1.0,
                atol=1e-10,
                rtol=0,
            )
        ),
        "raw and corrected Gaussian books",
    )
    add(
        "categorical_summary_complete",
        len(categorical_summary) == len(DECISION_ORDER) * len(MODEL_ORDER),
        f"rows={len(categorical_summary)}",
    )
    return pd.DataFrame(checks)


def make_figures(
    figure_dir: Path,
    temperature: pd.DataFrame,
    binary_summary: pd.DataFrame,
    categorical_summary: pd.DataFrame,
    parameters: pd.DataFrame,
    paired: pd.DataFrame,
) -> list[Path]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    # 1. Temperature mean error.
    pivot = temperature.pivot(
        index="decision_rule",
        columns="model",
        values="mean_error_C",
    ).reindex(DECISION_ORDER)
    ax = pivot.plot(kind="bar", figsize=(11, 6))
    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_title("Out-of-sample HKO daily-maximum temperature bias")
    ax.set_xlabel("")
    ax.set_ylabel("Mean forecast error (°C)")
    ax.legend(["Bias corrected", "Raw ECMWF proxy"])
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    path = figure_dir / "19c_temperature_mean_error_raw_vs_corrected.png"
    plt.savefig(path, dpi=180)
    plt.close()
    paths.append(path)

    # 2. Temperature MAE.
    pivot = temperature.pivot(
        index="decision_rule",
        columns="model",
        values="mae_C",
    ).reindex(DECISION_ORDER)
    ax = pivot.plot(kind="bar", figsize=(11, 6))
    ax.set_title("Out-of-sample HKO daily-maximum temperature MAE")
    ax.set_xlabel("")
    ax.set_ylabel("Mean absolute error (°C)")
    ax.legend(["Bias corrected", "Raw ECMWF proxy"])
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    path = figure_dir / "19c_temperature_mae_raw_vs_corrected.png"
    plt.savefig(path, dpi=180)
    plt.close()
    paths.append(path)

    # 3-4. Binary score comparison.
    for metric, title, ylabel, filename in [
        (
            "mean_brier",
            "Out-of-sample common-support binary Brier score",
            "Mean Brier score",
            "19c_binary_brier_model_comparison.png",
        ),
        (
            "mean_log_score",
            "Out-of-sample common-support binary log score",
            "Mean log score",
            "19c_binary_log_model_comparison.png",
        ),
    ]:
        pivot = binary_summary.pivot(
            index="decision_rule",
            columns="model",
            values=metric,
        ).reindex(index=DECISION_ORDER, columns=MODEL_ORDER)
        ax = pivot.plot(kind="bar", figsize=(13, 7))
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel(ylabel)
        ax.legend([MODEL_LABELS[m] for m in MODEL_ORDER])
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        path = figure_dir / filename
        plt.savefig(path, dpi=180)
        plt.close()
        paths.append(path)

    # 5-6. Categorical score comparison.
    for metric, title, ylabel, filename in [
        (
            "mean_normalised_categorical_log_score",
            "Out-of-sample normalised categorical log score",
            "Mean categorical log score",
            "19c_normalised_categorical_log_model_comparison.png",
        ),
        (
            "mean_normalised_multiclass_brier",
            "Out-of-sample normalised multiclass Brier score",
            "Mean multiclass Brier",
            "19c_normalised_multiclass_brier_model_comparison.png",
        ),
    ]:
        pivot = categorical_summary.pivot(
            index="decision_rule",
            columns="model",
            values=metric,
        ).reindex(index=DECISION_ORDER, columns=MODEL_ORDER)
        ax = pivot.plot(kind="bar", figsize=(13, 7))
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel(ylabel)
        ax.legend([MODEL_LABELS[m] for m in MODEL_ORDER])
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        path = figure_dir / filename
        plt.savefig(path, dpi=180)
        plt.close()
        paths.append(path)

    # 7. Expanding bias path.
    ready_params = parameters.loc[parameters["calibration_ready"]].copy()
    ready_params["event_date"] = pd.to_datetime(ready_params["event_date"])
    plt.figure(figsize=(12, 7))
    for rule in DECISION_ORDER:
        g = ready_params.loc[ready_params["decision_rule"].eq(rule)]
        plt.plot(g["event_date"], g["bias_correction_C"], label=rule)
    plt.title("Expanding-window ECMWF local bias correction")
    plt.xlabel("Event date")
    plt.ylabel("Additive correction (°C)")
    plt.legend()
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    path = figure_dir / "19c_expanding_bias_correction_path.png"
    plt.savefig(path, dpi=180)
    plt.close()
    paths.append(path)

    # 8. Expanding sigma path.
    plt.figure(figsize=(12, 7))
    for rule in DECISION_ORDER:
        g = ready_params.loc[ready_params["decision_rule"].eq(rule)]
        plt.plot(g["event_date"], g["sigma_used_C"], label=rule)
    plt.axhline(RAW_SIGMA_C, linestyle="--", linewidth=1, label="Raw sigma=1.5")
    plt.title("Expanding-window Gaussian residual scale")
    plt.xlabel("Event date")
    plt.ylabel("Sigma (°C)")
    plt.legend()
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    path = figure_dir / "19c_expanding_sigma_path.png"
    plt.savefig(path, dpi=180)
    plt.close()
    paths.append(path)

    # 9. Date-clustered paired log-score differences: corrected versus raw.
    subset = paired.loc[
        paired["metric"].eq("log")
        & paired["model_b"].eq("ecmwf_raw")
    ].copy()
    labels = []
    means = []
    lower_err = []
    upper_err = []
    for model in ["ecmwf_bias_fixed_sigma", "ecmwf_bias_scale"]:
        for rule in DECISION_ORDER:
            r = subset.loc[
                subset["model_a"].eq(model)
                & subset["decision_rule"].eq(rule)
            ].iloc[0]
            labels.append(f"{rule}\n{MODEL_LABELS[model]}")
            means.append(r["mean_difference"])
            lower_err.append(r["mean_difference"] - r["bootstrap_ci_2_5"])
            upper_err.append(r["bootstrap_ci_97_5"] - r["mean_difference"])
    x = np.arange(len(labels))
    plt.figure(figsize=(15, 7))
    plt.errorbar(
        x,
        means,
        yerr=np.vstack([lower_err, upper_err]),
        fmt="o",
        capsize=4,
    )
    plt.axhline(0, linestyle="--", linewidth=1)
    plt.xticks(x, labels, rotation=30, ha="right")
    plt.ylabel("Corrected minus raw mean log score")
    plt.title("Date-clustered paired log-score differences with 95% bootstrap intervals")
    plt.tight_layout()
    path = figure_dir / "19c_paired_log_score_improvement_bootstrap.png"
    plt.savefig(path, dpi=180)
    plt.close()
    paths.append(path)

    return paths


def markdown_table(df: pd.DataFrame, columns: list[str] | None = None) -> str:
    shown = df if columns is None else df[columns]
    try:
        return shown.to_markdown(index=False)
    except Exception:
        return "```\n" + shown.to_string(index=False) + "\n```"


def build_report(
    output_path: Path,
    min_train_dates: int,
    outcome_availability_lag_hours: float,
    forecast_calibration_panel: pd.DataFrame,
    common: pd.DataFrame,
    parameters: pd.DataFrame,
    temperature: pd.DataFrame,
    gaussian_cal: pd.DataFrame,
    binary_summary: pd.DataFrame,
    categorical_summary: pd.DataFrame,
    paired: pd.DataFrame,
    checks: pd.DataFrame,
    issues: pd.DataFrame,
    figures: list[Path],
    output_files: list[Path],
) -> None:
    ready_params = parameters.loc[parameters["calibration_ready"]]
    ready_rows_by_rule = (
        binary_summary.loc[binary_summary["model"].eq("market")]
        [["decision_rule", "n"]]
    )
    best_binary = (
        binary_summary.sort_values(["decision_rule", "mean_brier"])
        .groupby("decision_rule", as_index=False)
        .first()
    )
    best_cat = (
        categorical_summary.sort_values(
            ["decision_rule", "mean_normalised_categorical_log_score"]
        )
        .groupby("decision_rule", as_index=False)
        .first()
    )
    sigma_summary = (
        ready_params.groupby("decision_rule", as_index=False)
        .agg(
            mean_bias_correction_C=("bias_correction_C", "mean"),
            final_bias_correction_C=("bias_correction_C", "last"),
            mean_sigma_used_C=("sigma_used_C", "mean"),
            final_sigma_used_C=("sigma_used_C", "last"),
            n_scored_dates=("event_date", "size"),
        )
    )

    lines = [
        "# 19c leakage-free ECMWF proxy bias and scale correction",
        "",
        f"Generated: `{pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}`",
        "",
        "## Purpose",
        "",
        "This step estimates Hong Kong local temperature bias and Gaussian residual scale using strictly prior event dates, then regenerates HKO contract-event probabilities out of sample.",
        "",
        "## Methodological status",
        "",
        "The source forecast remains a deterministic ECMWF IFS HRES point forecast obtained through the temporary Open-Meteo single-runs route. The corrected probabilities are expanding-window Gaussian post-processing proxies. They are not ECMWF ENS, AIFS ENS or calibrated AIFS-CRPS probabilities.",
        "",
        "## Leakage-control design",
        "",
        f"- Parameters are estimated separately for each decision rule.",
        f"- A date becomes score-ready only after at least `{min_train_dates}` admissible historical forecast dates.",
        f"- An HKO outcome is conservatively assumed usable only `{outcome_availability_lag_hours:g}` hours after the end of its local day.",
        "- Historical outcomes must be available no later than the current decision cutoff.",
        "- All contracts from the same event date share the same temperature forecast and the same fitted parameters.",
        "- Bias and scale are fitted on unique date-level forecast errors, not repeated contract rows.",
        "- The additive correction is the negative expanding mean forecast error.",
        f"- The Gaussian scale is the expanding root-mean-square residual after bias correction, clipped ex ante to `[{MIN_SIGMA_C}, {MAX_SIGMA_C}]` °C.",
        f"- The original raw proxy continues to use sigma `{RAW_SIGMA_C}` °C.",
        f"- Log scores use probability clipping epsilon `{EPS}` only inside the logarithm.",
        "",
        "## Sample",
        "",
        f"- Input 19a calibration-panel contract rows: `{len(forecast_calibration_panel)}`",
        f"- Input 19b common-support contract rows: `{len(common)}`",
        f"- Unique 19a date-decision forecasts: `{len(parameters)}`",
        f"- Out-of-sample date-decision forecasts: `{int(parameters['calibration_ready'].sum())}`",
        f"- Out-of-sample contract rows: `{int(ready_rows_by_rule['n'].sum())}`",
        "",
        "### Out-of-sample rows by decision rule",
        "",
        markdown_table(ready_rows_by_rule),
        "",
        "## Expanding parameter summary",
        "",
        markdown_table(sigma_summary),
        "",
        "## Temperature error summary",
        "",
        markdown_table(temperature),
        "",
        "## Gaussian interval calibration summary",
        "",
        markdown_table(gaussian_cal),
        "",
        "## Binary common-support score summary",
        "",
        markdown_table(binary_summary),
        "",
        "### Best binary Brier model within each decision rule",
        "",
        markdown_table(
            best_binary[
                ["decision_rule", "model", "n", "mean_brier", "mean_log_score"]
            ]
        ),
        "",
        "## Event-book categorical score summary",
        "",
        markdown_table(categorical_summary),
        "",
        "### Best categorical log-score model within each decision rule",
        "",
        markdown_table(
            best_cat[
                [
                    "decision_rule",
                    "model",
                    "n_books",
                    "mean_normalised_categorical_log_score",
                    "mean_normalised_multiclass_brier",
                ]
            ]
        ),
        "",
        "## Date-clustered paired comparisons",
        "",
        "Differences are defined as `model_a - model_b`; negative values favour model A because lower scores are better. Confidence intervals resample event dates, not individual contracts.",
        "",
        markdown_table(paired),
        "",
        "## Integrity checks",
        "",
        markdown_table(checks),
        "",
        "## Issues requiring review",
        "",
        markdown_table(issues) if not issues.empty else "No non-warmup issues.",
        "",
        "## Interpretation rule",
        "",
        "A post-processed proxy improves on the raw proxy only when it achieves lower out-of-sample proper scores on the same rows. A lower temperature MAE by itself is not sufficient. The market comparison remains a paired common-support comparison and does not imply that deterministic ECMWF forecasts are intrinsically uninformative.",
        "",
        "## Figures",
        "",
    ]
    lines.extend([f"- `{p.relative_to(output_path.parents[2])}`" for p in figures])
    lines.extend(["", "## Output files", ""])
    lines.extend([f"- `{p.relative_to(output_path.parents[2])}`" for p in output_files])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_review_bundle(
    bundle_path: Path,
    files: Iterable[Path],
    repo_root: Path,
) -> None:
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            if path.exists():
                zf.write(path, arcname=str(path.relative_to(repo_root)))


def main() -> int:
    args = parse_args()
    if args.min_train_dates < 5:
        raise ValueError("--min-train-dates must be at least 5.")
    if args.bootstrap_reps < 500:
        raise ValueError("--bootstrap-reps must be at least 500.")
    if args.outcome_availability_lag_hours < 0:
        raise ValueError("--outcome-availability-lag-hours cannot be negative.")

    repo_root = detect_repo_root(args.repo_root)
    processed_dir = repo_root / "data" / "processed"
    report_dir = repo_root / "docs" / "research_outputs"
    figure_dir = repo_root / "figures" / "19c_ecmwf_proxy_bias_scale_calibration"
    bundle_dir = repo_root / "data" / "review_bundles"

    forecast_calibration_path = (
        processed_dir / "19a_hko_ecmwf_contract_event_probability_panel.csv"
    )
    common_path = processed_dir / "19b_common_support_market_vs_ecmwf_panel.csv"
    original_book_path = (
        processed_dir / "19b_common_support_categorical_book_score_panel.csv"
    )

    forecast_calibration_panel = read_csv_auto(forecast_calibration_path)
    common = read_csv_auto(common_path)
    original_book = read_csv_auto(original_book_path)
    validate_common_panel(common)

    date_level = build_date_level_forecasts(
        forecast_calibration_panel,
        args.outcome_availability_lag_hours,
    )
    parameters = expanding_parameters(date_level, args.min_train_dates)
    panel = add_calibrated_probabilities(common, parameters)

    temperature = temperature_summary(parameters)
    gaussian_cal = gaussian_calibration_summary(parameters)
    binary_summary = binary_score_summary(panel)
    binary_event_type = binary_score_by_event_type(panel)
    book_panel, categorical_summary, categorical_issues = categorical_panels(
        panel,
        original_book,
    )
    date_scores = date_level_score_panel(panel)
    paired = paired_date_comparisons(date_scores, args.bootstrap_reps)
    rankings = decision_rule_rankings(binary_summary, categorical_summary)
    checks = integrity_checks(
        common,
        parameters,
        panel,
        binary_summary,
        book_panel,
        categorical_summary,
    )

    warmup_issues = (
        parameters.loc[~parameters["calibration_ready"]]
        .groupby("decision_rule", as_index=False)
        .agg(
            n_warmup_date_rules=("event_date", "size"),
            first_event_date=("event_date", "min"),
            last_warmup_event_date=("event_date", "max"),
        )
    )
    warmup_issues.insert(0, "issue_type", "calibration_warmup_summary")
    issues = pd.concat(
        [warmup_issues, categorical_issues],
        ignore_index=True,
        sort=False,
    )

    output_paths = {
        "parameter_path": processed_dir / "19c_expanding_bias_scale_parameter_path.csv",
        "panel": processed_dir / "19c_common_support_calibrated_probability_panel.csv",
        "temperature": processed_dir / "19c_temperature_error_summary.csv",
        "gaussian_cal": processed_dir / "19c_gaussian_calibration_summary.csv",
        "binary": processed_dir / "19c_binary_score_summary.csv",
        "binary_event_type": processed_dir / "19c_binary_score_by_event_type.csv",
        "date_scores": processed_dir / "19c_date_level_score_panel.csv",
        "paired": processed_dir / "19c_paired_date_level_comparisons.csv",
        "book_panel": processed_dir / "19c_categorical_book_score_panel.csv",
        "categorical": processed_dir / "19c_categorical_score_summary.csv",
        "rankings": processed_dir / "19c_decision_rule_rankings.csv",
        "checks": processed_dir / "19c_integrity_checks.csv",
        "issues": processed_dir / "19c_issues.csv",
        "report": report_dir / "19c_ecmwf_proxy_bias_scale_calibration_report.md",
        "bundle": bundle_dir / "19c_review_bundle.zip",
    }

    processed_dir.mkdir(parents=True, exist_ok=True)
    parameters.to_csv(output_paths["parameter_path"], index=False)
    panel.to_csv(output_paths["panel"], index=False)
    temperature.to_csv(output_paths["temperature"], index=False)
    gaussian_cal.to_csv(output_paths["gaussian_cal"], index=False)
    binary_summary.to_csv(output_paths["binary"], index=False)
    binary_event_type.to_csv(output_paths["binary_event_type"], index=False)
    date_scores.to_csv(output_paths["date_scores"], index=False)
    paired.to_csv(output_paths["paired"], index=False)
    book_panel.to_csv(output_paths["book_panel"], index=False)
    categorical_summary.to_csv(output_paths["categorical"], index=False)
    rankings.to_csv(output_paths["rankings"], index=False)
    checks.to_csv(output_paths["checks"], index=False)
    issues.to_csv(output_paths["issues"], index=False)

    figures = make_figures(
        figure_dir,
        temperature,
        binary_summary,
        categorical_summary,
        parameters,
        paired,
    )

    report_outputs = [
        output_paths[k]
        for k in [
            "parameter_path",
            "panel",
            "temperature",
            "gaussian_cal",
            "binary",
            "binary_event_type",
            "date_scores",
            "paired",
            "book_panel",
            "categorical",
            "rankings",
            "checks",
            "issues",
        ]
    ]
    build_report(
        output_paths["report"],
        args.min_train_dates,
        args.outcome_availability_lag_hours,
        forecast_calibration_panel,
        common,
        parameters,
        temperature,
        gaussian_cal,
        binary_summary,
        categorical_summary,
        paired,
        checks,
        issues,
        figures,
        report_outputs,
    )

    bundle_files = [
        output_paths["report"],
        *report_outputs,
        *figures,
    ]
    create_review_bundle(output_paths["bundle"], bundle_files, repo_root)

    failed = checks.loc[~checks["passed"].astype(bool)]
    print("=" * 79)
    print("19c leakage-free ECMWF proxy bias and scale correction")
    print("=" * 79)
    print(f"Repository root: {repo_root}")
    print(f"Input 19a calibration rows: {len(forecast_calibration_panel):,}")
    print(f"Input 19b common rows: {len(common):,}")
    print(
        "Out-of-sample date-rules: "
        f"{int(parameters['calibration_ready'].sum()):,} / {len(parameters):,}"
    )
    print(f"Out-of-sample contract rows: {int(panel['calibration_ready'].sum()):,}")
    print(f"Categorical ready books: {int(book_panel['book_ready'].sum()):,}")
    print("")
    print("Binary score summary:")
    print(
        binary_summary[
            ["decision_rule", "model", "n", "mean_brier", "mean_log_score"]
        ].to_string(index=False)
    )
    print("")
    print("Temperature summary:")
    print(temperature.to_string(index=False))
    print("")
    print(f"Integrity checks passed: {len(checks) - len(failed)} / {len(checks)}")
    if not failed.empty:
        print(failed.to_string(index=False))
    print("")
    print(f"Review bundle: {output_paths['bundle']}")
    print("=" * 79)

    if not failed.empty:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
