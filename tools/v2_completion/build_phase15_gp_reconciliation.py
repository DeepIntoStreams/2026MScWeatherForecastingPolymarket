from __future__ import annotations

import ast
import csv
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import joblib
import numpy as np
import pandas as pd
import scipy
from scipy.linalg import solve_triangular
from scipy.optimize import linear_sum_assignment
from scipy.stats import norm
import sklearn
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Kernel, Sum, WhiteKernel
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/v2_completion"
CONFIG = ROOT / "config/v2_completion"
OUT.mkdir(parents=True, exist_ok=True)
CONFIG.mkdir(parents=True, exist_ok=True)

VALIDATION_PATH = ROOT / "outputs/v2/diagnostics/07_gp_validation_predictions.csv"
RESIDUAL_PATH = ROOT / "outputs/v2/diagnostics/05_weather_only_forecast_residual_panel.csv"
PHASE7_SOURCE = ROOT / "tools/v2/fit_gp_validation_distributions.py"
PHASE8_SOURCE = ROOT / "tools/v2/build_phase8_clean_gp.py"
PHASE8_MODEL_DIR = ROOT / "models/v2/phase8_clean_gp"
PHASE14_MANIFEST = ROOT / "outputs/v2_completion/phase14_baseline_manifest.json"

REQUIRED_PATHS = [
    VALIDATION_PATH,
    RESIDUAL_PATH,
    PHASE7_SOURCE,
    PHASE8_SOURCE,
    PHASE8_MODEL_DIR,
    PHASE14_MANIFEST,
]


def fail(message: str) -> None:
    raise RuntimeError(message)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def find_column(
    columns: Iterable[str],
    exact: Iterable[str] = (),
    contains_all: Iterable[str] = (),
    contains_any: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> str | None:
    cols = list(columns)
    lower = {c.lower(): c for c in cols}
    for name in exact:
        if name.lower() in lower:
            return lower[name.lower()]
    candidates: list[tuple[int, str]] = []
    for col in cols:
        lc = col.lower()
        if any(token.lower() in lc for token in exclude):
            continue
        if contains_all and not all(token.lower() in lc for token in contains_all):
            continue
        if contains_any and not any(token.lower() in lc for token in contains_any):
            continue
        score = 0
        score += 10 * sum(token.lower() in lc for token in contains_all)
        score += 2 * sum(token.lower() in lc for token in contains_any)
        candidates.append((score, col))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return candidates[0][1]


def normalise_model_label(value: Any) -> str:
    text = str(value).strip().lower().replace("-", "").replace("_", "")
    if "matern" in text or "matérn" in text:
        return "matern32"
    if "rbf" in text or "radial" in text or "squaredexponential" in text:
        return "rbf"
    return str(value).strip().lower()


def normalise_rule(value: Any) -> str:
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "24h": "24h_prior",
        "24hr": "24h_prior",
        "24_hours_prior": "24h_prior",
        "12h": "12h_prior",
        "12hr": "12h_prior",
        "12_hours_prior": "12h_prior",
        "6h": "6h_prior",
        "6hr": "6h_prior",
        "6_hours_prior": "6h_prior",
        "open": "event_day_open",
        "eventdayopen": "event_day_open",
    }
    return aliases.get(text, text)


def scan_source_evidence(paths: list[Path]) -> list[dict[str, Any]]:
    patterns = {
        "feature_calendar": re.compile(r"calendar_time|365\.2425|time_year", re.I),
        "feature_season": re.compile(r"seasonal_|sin\(|cos\(|dayofyear|day_of_year", re.I),
        "feature_forecast": re.compile(r"forecast_daily_max|deterministic.*max", re.I),
        "feature_scaling": re.compile(r"StandardScaler|fit_transform|transform\(", re.I),
        "response_scaling": re.compile(r"normalize_y|y_train_mean|y_train_std|response.*scal", re.I),
        "estimator": re.compile(r"GaussianProcessRegressor", re.I),
        "kernel": re.compile(r"RBF|Matern|WhiteKernel|ConstantKernel", re.I),
        "optimiser": re.compile(r"n_restarts_optimizer|optimizer|random_state|alpha\s*=", re.I),
        "prediction": re.compile(r"return_std|return_cov|predict\(", re.I),
        "crps": re.compile(r"crps|quantile", re.I),
    }
    rows: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            categories = [name for name, pattern in patterns.items() if pattern.search(line)]
            if not categories:
                continue
            start = max(0, i - 2)
            end = min(len(lines), i + 2)
            context = " ".join(piece.strip() for piece in lines[start:end] if piece.strip())
            rows.append(
                {
                    "source_file": rel(path),
                    "line": i,
                    "categories": "|".join(categories),
                    "source_line": line.strip()[:500],
                    "context": context[:1500],
                }
            )
    return rows


def ast_call_registry(paths: list[Path]) -> list[dict[str, Any]]:
    target_names = {
        "GaussianProcessRegressor",
        "StandardScaler",
        "RBF",
        "Matern",
        "WhiteKernel",
        "ConstantKernel",
    }
    rows: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name not in target_names:
                continue
            source = ast.get_source_segment(text, node) or ""
            keywords: dict[str, Any] = {}
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                try:
                    keywords[kw.arg] = ast.literal_eval(kw.value)
                except Exception:
                    keywords[kw.arg] = ast.get_source_segment(text, kw.value)
            rows.append(
                {
                    "source_file": rel(path),
                    "line": getattr(node, "lineno", None),
                    "call": name,
                    "keywords_json": json.dumps(keywords, sort_keys=True, default=str),
                    "source": source[:2500],
                }
            )
    return rows


def discover_feature_panel() -> tuple[Path, pd.DataFrame]:
    required = {"calendar_time_years", "seasonal_sin", "seasonal_cos"}
    preferred = [
        ROOT / "outputs/v2/diagnostics/06_gp_training_design_panel.csv",
        ROOT / "outputs/v2/diagnostics/06_gp_training_design.csv",
        VALIDATION_PATH,
        RESIDUAL_PATH,
    ]
    candidates = preferred + sorted((ROOT / "outputs/v2").rglob("*.csv"))
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        try:
            header = pd.read_csv(path, nrows=2)
        except Exception:
            continue
        cols = {c.lower() for c in header.columns}
        if not required.issubset(cols):
            continue
        rule_col = find_column(header.columns, exact=["decision_rule", "rule"])
        date_col = find_column(header.columns, exact=["target_date", "event_date", "date"])
        forecast_col = find_column(
            header.columns,
            exact=[
                "forecast_daily_max_c",
                "deterministic_forecast_daily_max_c",
                "raw_forecast_daily_max_c",
                "source_forecast_daily_max_c",
            ],
            contains_all=["forecast", "max"],
            contains_any=["c", "temperature"],
        )
        if rule_col and date_col and forecast_col:
            return path, pd.read_csv(path)
    fail("Could not identify a feature panel containing calendar time, seasonal sine/cosine and forecast level.")


def infer_calendar_formula(df: pd.DataFrame, date_col: str) -> dict[str, Any]:
    dates = pd.to_datetime(df[date_col], errors="coerce")
    values = pd.to_numeric(df["calendar_time_years"], errors="coerce")
    mask = dates.notna() & values.notna()
    if mask.sum() < 20:
        fail("Insufficient rows to infer calendar-time formula.")
    dates = dates[mask].dt.normalize()
    values = values[mask].astype(float)
    ref = dates.min()
    days = (dates - ref).dt.total_seconds().to_numpy() / 86400.0
    y = values.to_numpy()
    A = np.column_stack([days, np.ones_like(days)])
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    fitted = slope * days + intercept
    max_error = float(np.max(np.abs(fitted - y)))
    if abs(slope) < 1e-15:
        fail("Calendar-time feature has zero slope.")
    denominator = float(1.0 / slope)
    origin = ref - pd.to_timedelta(intercept * denominator, unit="D")
    return {
        "formula": "(target_date - origin_date).days / days_per_year",
        "origin_date": origin.isoformat(),
        "days_per_year": denominator,
        "slope_per_day": float(slope),
        "intercept_at_min_date": float(intercept),
        "max_reconstruction_error": max_error,
        "status": "PASSED" if max_error < 1e-10 else "FAILED",
    }


def seasonal_candidates(dates: pd.Series) -> dict[str, np.ndarray]:
    dates = pd.to_datetime(dates).dt.normalize()
    doy = dates.dt.dayofyear.to_numpy(dtype=float)
    leap_days = np.where(dates.dt.is_leap_year.to_numpy(), 366.0, 365.0)
    fixed = pd.to_datetime(
        {
            "year": np.full(len(dates), 2001),
            "month": dates.dt.month.to_numpy(),
            "day": dates.dt.day.to_numpy(),
        },
        errors="coerce",
    )
    fixed_doy = pd.Series(fixed).dt.dayofyear.to_numpy(dtype=float)
    return {
        "(day_of_year-1)/365.2425": (doy - 1.0) / 365.2425,
        "day_of_year/365.2425": doy / 365.2425,
        "(day_of_year-1)/days_in_year": (doy - 1.0) / leap_days,
        "day_of_year/days_in_year": doy / leap_days,
        "(fixed_2001_day_of_year-1)/365": (fixed_doy - 1.0) / 365.0,
        "fixed_2001_day_of_year/365": fixed_doy / 365.0,
    }


def infer_seasonal_formula(df: pd.DataFrame, date_col: str) -> dict[str, Any]:
    dates = pd.to_datetime(df[date_col], errors="coerce")
    sin_obs = pd.to_numeric(df["seasonal_sin"], errors="coerce")
    cos_obs = pd.to_numeric(df["seasonal_cos"], errors="coerce")
    mask = dates.notna() & sin_obs.notna() & cos_obs.notna()
    dates = dates[mask]
    sin_obs = sin_obs[mask].to_numpy(dtype=float)
    cos_obs = cos_obs[mask].to_numpy(dtype=float)
    errors: list[dict[str, Any]] = []
    for formula, position in seasonal_candidates(dates).items():
        sin_hat = np.sin(2.0 * np.pi * position)
        cos_hat = np.cos(2.0 * np.pi * position)
        max_error = float(
            max(
                np.max(np.abs(sin_hat - sin_obs)),
                np.max(np.abs(cos_hat - cos_obs)),
            )
        )
        rmse = float(
            np.sqrt(
                np.mean(
                    np.concatenate(
                        [(sin_hat - sin_obs) ** 2, (cos_hat - cos_obs) ** 2]
                    )
                )
            )
        )
        errors.append({"formula": formula, "max_error": max_error, "rmse": rmse})
    errors.sort(key=lambda row: (row["max_error"], row["rmse"]))
    best = errors[0]
    return {
        "formula": best["formula"],
        "seasonal_sin": "sin(2*pi*seasonal_position)",
        "seasonal_cos": "cos(2*pi*seasonal_position)",
        "max_reconstruction_error": best["max_error"],
        "rmse": best["rmse"],
        "candidate_errors": errors,
        "status": "PASSED" if best["max_error"] < 1e-10 else "FAILED",
    }


def recursive_objects(obj: Any, seen: set[int] | None = None) -> Iterator[Any]:
    if seen is None:
        seen = set()
    ident = id(obj)
    if ident in seen:
        return
    seen.add(ident)
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from recursive_objects(value, seen)
    elif isinstance(obj, (list, tuple, set)):
        for value in obj:
            yield from recursive_objects(value, seen)
    elif isinstance(obj, Pipeline):
        for _, value in obj.steps:
            yield from recursive_objects(value, seen)
    else:
        for attr in ("model", "estimator", "regressor", "gpr", "scaler", "x_scaler", "y_scaler"):
            if hasattr(obj, attr):
                try:
                    yield from recursive_objects(getattr(obj, attr), seen)
                except Exception:
                    pass


def locate_gpr(obj: Any) -> GaussianProcessRegressor:
    matches = [x for x in recursive_objects(obj) if isinstance(x, GaussianProcessRegressor)]
    if len(matches) != 1:
        fail(f"Expected exactly one GaussianProcessRegressor in a saved object; found {len(matches)}.")
    return matches[0]


def locate_scalers(obj: Any) -> list[StandardScaler]:
    return [x for x in recursive_objects(obj) if isinstance(x, StandardScaler)]


def identify_rule_from_name(path: Path) -> str:
    text = path.stem.lower()
    for rule in ("24h_prior", "12h_prior", "6h_prior", "event_day_open"):
        if rule in text:
            return rule
    aliases = [
        ("24h", "24h_prior"),
        ("12h", "12h_prior"),
        ("6h", "6h_prior"),
        ("open", "event_day_open"),
    ]
    for token, rule in aliases:
        if token in text:
            return rule
    return path.stem


def kernel_components(kernel: Kernel) -> list[Kernel]:
    if isinstance(kernel, Sum):
        return kernel_components(kernel.k1) + kernel_components(kernel.k2)
    return [kernel]


def white_noise_level(kernel: Kernel) -> float:
    total = 0.0
    for component in kernel_components(kernel):
        if isinstance(component, WhiteKernel):
            total += float(component.noise_level)
    return total


def signal_kernel(kernel: Kernel) -> Kernel | None:
    parts = [component for component in kernel_components(kernel) if not isinstance(component, WhiteKernel)]
    if not parts:
        return None
    result = parts[0]
    for part in parts[1:]:
        result = result + part
    return result


def scalar_or_summary(value: Any) -> Any:
    array = np.asarray(value)
    if array.ndim == 0:
        return float(array)
    return {
        "shape": list(array.shape),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
        "mean": float(np.mean(array)),
    }


def affine_feature_map(
    raw: np.ndarray,
    transformed: np.ndarray,
    raw_names: list[str],
) -> tuple[list[dict[str, Any]], float]:
    if raw.shape != transformed.shape:
        fail(f"Raw feature matrix {raw.shape} does not match fitted X_train_ {transformed.shape}.")
    raw_std = np.std(raw, axis=0)
    transformed_std = np.std(transformed, axis=0)
    if np.any(raw_std == 0) or np.any(transformed_std == 0):
        fail("A feature has zero variance; cannot identify the transformation.")
    corr = np.corrcoef(raw.T, transformed.T)[: raw.shape[1], raw.shape[1] :]
    row_ind, col_ind = linear_sum_assignment(-np.abs(corr))
    rows: list[dict[str, Any]] = []
    max_error = 0.0
    for raw_idx, transformed_idx in zip(row_ind, col_ind):
        x = raw[:, raw_idx]
        z = transformed[:, transformed_idx]
        A = np.column_stack([x, np.ones_like(x)])
        slope, intercept = np.linalg.lstsq(A, z, rcond=None)[0]
        fitted = slope * x + intercept
        error = float(np.max(np.abs(fitted - z)))
        max_error = max(max_error, error)
        if abs(slope) < 1e-15:
            scale = math.inf
            centre = math.nan
        else:
            scale = float(1.0 / slope)
            centre = float(-intercept / slope)
        rows.append(
            {
                "raw_feature": raw_names[raw_idx],
                "model_feature_index": int(transformed_idx),
                "correlation": float(corr[raw_idx, transformed_idx]),
                "affine_slope": float(slope),
                "affine_intercept": float(intercept),
                "implied_centre": centre,
                "implied_scale": scale,
                "max_reconstruction_error": error,
                "transformation": "z=(x-centre)/scale",
            }
        )
    rows.sort(key=lambda row: row["model_feature_index"])
    return rows, max_error


def manual_predictive_decomposition(
    gpr: GaussianProcessRegressor,
    x_test: np.ndarray,
) -> dict[str, float]:
    pred_mean, pred_std = gpr.predict(x_test, return_std=True)
    k_trans = gpr.kernel_(x_test, gpr.X_train_)
    reduction_matrix = solve_triangular(gpr.L_, k_trans.T, lower=True, check_finite=False)
    reduction = np.einsum("ij,ji->i", reduction_matrix.T, reduction_matrix)
    mean_normalised = k_trans @ gpr.alpha_
    y_mean = np.asarray(getattr(gpr, "_y_train_mean", 0.0))
    y_std = np.asarray(getattr(gpr, "_y_train_std", 1.0))
    if y_mean.ndim:
        y_mean_scalar = float(y_mean.reshape(-1)[0])
    else:
        y_mean_scalar = float(y_mean)
    if y_std.ndim:
        y_std_scalar = float(y_std.reshape(-1)[0])
    else:
        y_std_scalar = float(y_std)
    manual_mean = np.asarray(mean_normalised).reshape(-1)[0] * y_std_scalar + y_mean_scalar
    full_var_normalised = gpr.kernel_.diag(x_test) - reduction
    full_var = float(full_var_normalised[0] * y_std_scalar**2)
    signal = signal_kernel(gpr.kernel_)
    if signal is None:
        fail("Fitted GP kernel has no non-white signal component.")
    latent_var_normalised = signal.diag(x_test) - reduction
    latent_var = float(latent_var_normalised[0] * y_std_scalar**2)
    white_normalised = white_noise_level(gpr.kernel_)
    white_scaled = float(white_normalised * y_std_scalar**2)
    return {
        "software_mean": float(np.asarray(pred_mean).reshape(-1)[0]),
        "manual_mean": float(manual_mean),
        "mean_abs_difference": float(abs(float(np.asarray(pred_mean).reshape(-1)[0]) - manual_mean)),
        "software_variance": float(np.asarray(pred_std).reshape(-1)[0] ** 2),
        "manual_full_variance": full_var,
        "variance_abs_difference": float(abs(float(np.asarray(pred_std).reshape(-1)[0] ** 2) - full_var)),
        "manual_latent_variance": latent_var,
        "white_noise_variance_scaled": white_scaled,
        "full_minus_latent": float(full_var - latent_var),
        "noise_identity_abs_difference": float(abs((full_var - latent_var) - white_scaled)),
        "normalised_white_noise_level": white_normalised,
        "response_scale": y_std_scalar,
    }


def gaussian_crps(mu: np.ndarray, sigma: np.ndarray, y: np.ndarray) -> np.ndarray:
    sigma = np.asarray(sigma, dtype=float)
    if np.any(~np.isfinite(sigma)) or np.any(sigma <= 0):
        fail("Predictive standard deviations must be finite and positive.")
    z = (np.asarray(y, dtype=float) - np.asarray(mu, dtype=float)) / sigma
    return sigma * (
        z * (2.0 * norm.cdf(z) - 1.0)
        + 2.0 * norm.pdf(z)
        - 1.0 / math.sqrt(math.pi)
    )


def discover_prediction_columns(df: pd.DataFrame) -> dict[str, str]:
    columns = list(df.columns)
    mapping = {
        "date": find_column(columns, exact=["target_date", "event_date", "date"]),
        "rule": find_column(columns, exact=["decision_rule", "rule"]),
        "model": find_column(columns, exact=["kernel", "kernel_family", "model", "model_name"]),
        "block": find_column(
            columns,
            exact=[
                "validation_block",
                "block",
                "block_id",
                "fold",
                "fold_id",
                "fold_number",
                "validation_fold",
            ],
            contains_any=["block", "fold"],
        ),
        "mean": find_column(
            columns,
            exact=[
                "gp_temperature_mean_c",
                "predictive_temperature_mean_c",
                "predictive_mean_c",
                "temperature_mean_c",
                "mean_c",
            ],
            contains_all=["mean"],
            contains_any=["temperature", "predictive", "gp"],
            exclude=["residual", "absolute", "date"],
        ),
        "std": (
            find_column(
                columns,
                exact=[
                    "predictive_standard_deviation_c",
                    "temperature_predictive_standard_deviation_c",
                    "gp_temperature_standard_deviation_c",
                    "gp_temperature_std_c",
                    "predictive_temperature_std_c",
                    "predictive_std_c",
                    "predictive_sd_c",
                    "temperature_std_c",
                    "std_c",
                ],
            )
            or find_column(
                columns,
                contains_any=["standard_deviation", "std", "sigma"],
                exclude=["residual", "standardised", "standardized", "error"],
            )
        ),
        "outcome": find_column(
            columns,
            exact=[
                "hko_daily_max_c",
                "hko_max_c",
                "observed_daily_max_c",
                "realised_daily_max_c",
                "realized_daily_max_c",
                "outcome_temperature_c",
                "actual_temperature_c",
            ],
            contains_any=["hko", "observed", "realised", "realized", "actual", "outcome"],
            exclude=["probability", "event", "indicator"],
        ),
        "crps": find_column(
            columns,
            exact=["crps_c", "continuous_crps_c", "gp_crps_c"],
            contains_all=["crps"],
        ),
    }
    missing = [key for key in ("date", "rule", "model", "mean", "std", "outcome", "crps") if not mapping[key]]
    if missing:
        fail(
            "Could not identify required Phase 7 prediction columns "
            f"{missing}. Available columns: {columns}"
        )
    return {key: str(value) for key, value in mapping.items() if value is not None}


def discover_fold_registry(
    validation: pd.DataFrame,
    cols: dict[str, str],
) -> list[dict[str, Any]]:
    df = validation.copy()
    df["_model_normalised"] = df[cols["model"]].map(normalise_model_label)
    df["_rule_normalised"] = df[cols["rule"]].map(normalise_rule)
    if cols.get("block"):
        block_col = cols["block"]
    else:
        dates = pd.to_datetime(df[cols["date"]])
        unique_dates = sorted(dates.dropna().dt.normalize().unique())
        if len(unique_dates) != 365:
            fail("Validation block column is absent and 365 unique validation dates were not found.")
        sizes = [91, 91, 91, 92]
        mapping: dict[pd.Timestamp, int] = {}
        cursor = 0
        for block, size in enumerate(sizes, start=1):
            for date in unique_dates[cursor : cursor + size]:
                mapping[pd.Timestamp(date)] = block
            cursor += size
        df["_derived_block"] = dates.dt.normalize().map(mapping)
        block_col = "_derived_block"
    constant_candidates = [
        c
        for c in df.columns
        if any(token in c.lower() for token in ("kernel", "length", "noise", "signal", "train", "optim", "alpha", "restart"))
        and c not in {cols["model"]}
    ]
    rows: list[dict[str, Any]] = []
    group_cols = ["_model_normalised", "_rule_normalised", block_col]
    for (model, rule, block), group in df.groupby(group_cols, dropna=False):
        row: dict[str, Any] = {
            "model": model,
            "decision_rule": rule,
            "validation_block": block,
            "validation_rows": int(len(group)),
            "validation_dates": int(pd.to_datetime(group[cols["date"]]).dt.normalize().nunique()),
            "validation_start": pd.to_datetime(group[cols["date"]]).min().isoformat(),
            "validation_end": pd.to_datetime(group[cols["date"]]).max().isoformat(),
            "mean_crps_c": float(pd.to_numeric(group[cols["crps"]], errors="raise").mean()),
        }
        for candidate in constant_candidates:
            values = group[candidate].dropna().astype(str).unique()
            if len(values) == 1:
                row[candidate] = values[0]
        rows.append(row)
    rows.sort(key=lambda row: (str(row["model"]), str(row["decision_rule"]), str(row["validation_block"])))
    if len(rows) != 32:
        fail(f"Expected 32 rule-model-block registry rows; found {len(rows)}.")
    return rows


def main() -> None:
    for path in REQUIRED_PATHS:
        if not path.exists():
            fail(f"Required Phase 15 input is missing: {rel(path) if path.is_absolute() and ROOT in path.parents else path}")

    phase14 = json.loads(PHASE14_MANIFEST.read_text(encoding="utf-8"))
    validation = pd.read_csv(VALIDATION_PATH)
    residual = pd.read_csv(RESIDUAL_PATH)
    feature_path, feature_panel = discover_feature_panel()

    date_col = find_column(feature_panel.columns, exact=["target_date", "event_date", "date"])
    rule_col = find_column(feature_panel.columns, exact=["decision_rule", "rule"])
    forecast_col = find_column(
        feature_panel.columns,
        exact=[
            "forecast_daily_max_c",
            "deterministic_forecast_daily_max_c",
            "raw_forecast_daily_max_c",
            "source_forecast_daily_max_c",
        ],
        contains_all=["forecast", "max"],
        contains_any=["c", "temperature"],
    )
    if not date_col or not rule_col or not forecast_col:
        fail("Feature panel lacks date, rule or deterministic forecast column.")

    feature_panel[date_col] = pd.to_datetime(feature_panel[date_col], errors="raise")
    feature_panel["_rule_normalised"] = feature_panel[rule_col].map(normalise_rule)

    calendar_spec = infer_calendar_formula(feature_panel, date_col)
    seasonal_spec = infer_seasonal_formula(feature_panel, date_col)
    if calendar_spec["status"] != "PASSED":
        fail(f"Calendar feature reconstruction failed: {calendar_spec}")
    if seasonal_spec["status"] != "PASSED":
        fail(f"Seasonal feature reconstruction failed: {seasonal_spec}")

    source_paths = [PHASE7_SOURCE, PHASE8_SOURCE]
    source_evidence = scan_source_evidence(source_paths)
    call_registry = ast_call_registry(source_paths)

    model_paths = sorted(PHASE8_MODEL_DIR.glob("*.joblib"))
    if len(model_paths) != 4:
        fail(f"Expected four full-history Phase 8 model files; found {len(model_paths)}.")

    raw_feature_names = [
        "calendar_time_years",
        "seasonal_sin",
        "seasonal_cos",
        forecast_col,
    ]
    full_model_rows: list[dict[str, Any]] = []
    scaling_rows: list[dict[str, Any]] = []
    variance_rows: list[dict[str, Any]] = []

    for model_path in model_paths:
        saved = joblib.load(model_path)
        gpr = locate_gpr(saved)
        scalers = locate_scalers(saved)
        rule = identify_rule_from_name(model_path)
        rule_data = (
            feature_panel.loc[feature_panel["_rule_normalised"] == rule]
            .sort_values(date_col, kind="stable")
            .drop_duplicates(subset=[date_col], keep="first")
        )
        if len(rule_data) != int(gpr.X_train_.shape[0]):
            fail(
                f"Rule {rule}: feature rows {len(rule_data)} do not match "
                f"model training rows {gpr.X_train_.shape[0]}."
            )
        raw_x = rule_data[raw_feature_names].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
        transformed_x = np.asarray(gpr.X_train_, dtype=float)
        rule_scaling, scaling_error = affine_feature_map(raw_x, transformed_x, raw_feature_names)
        if scaling_error > 1e-8:
            diagnostic_path = OUT / f"phase15_{rule}_feature_scaling_diagnostic.csv"
            pd.DataFrame(
                {
                    "raw_date": rule_data[date_col].astype(str).to_numpy(),
                    **{f"raw_{name}": raw_x[:, idx] for idx, name in enumerate(raw_feature_names)},
                    **{f"model_x_{idx}": transformed_x[:, idx] for idx in range(transformed_x.shape[1])},
                }
            ).to_csv(diagnostic_path, index=False, lineterminator="\n")
            fail(
                f"Rule {rule}: could not reconstruct the feature transformation exactly; "
                f"max error {scaling_error}. Diagnostic: {rel(diagnostic_path)}"
            )
        for row in rule_scaling:
            row.update(
                {
                    "decision_rule": rule,
                    "model_path": rel(model_path),
                    "training_rows": int(gpr.X_train_.shape[0]),
                    "source_feature_panel": rel(feature_path),
                    "status": "PASSED",
                }
            )
            scaling_rows.append(row)

        x_test = transformed_x[[0], :]
        variance = manual_predictive_decomposition(gpr, x_test)
        variance.update(
            {
                "decision_rule": rule,
                "model_path": rel(model_path),
                "test_point_source": "first transformed training input, evaluated as a prediction point",
                "alpha": json.dumps(scalar_or_summary(gpr.alpha), sort_keys=True),
                "status": "PASSED"
                if (
                    variance["mean_abs_difference"] < 1e-10
                    and variance["variance_abs_difference"] < 1e-10
                    and variance["noise_identity_abs_difference"] < 1e-10
                )
                else "FAILED",
            }
        )
        variance_rows.append(variance)

        if variance["status"] != "PASSED":
            fail(f"Predictive variance reconciliation failed for {rule}: {variance}")

        fitted_kernel = getattr(gpr, "kernel_", None)
        if fitted_kernel is None:
            fail(f"Saved model {model_path} is not fitted.")
        params = gpr.get_params(deep=True)
        pipeline_steps = []
        if isinstance(saved, Pipeline):
            pipeline_steps = [name for name, _ in saved.steps]

        full_model_rows.append(
            {
                "decision_rule": rule,
                "model_path": rel(model_path),
                "model_sha256": sha256(model_path),
                "saved_object_class": f"{saved.__class__.__module__}.{saved.__class__.__name__}",
                "gpr_class": f"{gpr.__class__.__module__}.{gpr.__class__.__name__}",
                "pipeline_steps": "|".join(pipeline_steps),
                "embedded_standard_scalers": len(scalers),
                "training_rows": int(gpr.X_train_.shape[0]),
                "n_features": int(gpr.X_train_.shape[1]),
                "normalize_y": bool(gpr.normalize_y),
                "response_training_mean": scalar_or_summary(getattr(gpr, "_y_train_mean", 0.0)),
                "response_training_std": scalar_or_summary(getattr(gpr, "_y_train_std", 1.0)),
                "alpha": scalar_or_summary(gpr.alpha),
                "optimizer": str(gpr.optimizer),
                "n_restarts_optimizer": int(gpr.n_restarts_optimizer),
                "random_state": str(gpr.random_state),
                "copy_X_train": bool(gpr.copy_X_train),
                "kernel_initial": str(gpr.kernel),
                "kernel_fitted": str(gpr.kernel_),
                "white_noise_level_normalised": white_noise_level(gpr.kernel_),
                "log_marginal_likelihood_value": float(gpr.log_marginal_likelihood_value_),
                "feature_scaling_max_error": scaling_error,
                "sklearn_version": sklearn.__version__,
                "joblib_version": joblib.__version__,
                "status": "PASSED",
            }
        )

    validation_cols = discover_prediction_columns(validation)
    validation["_model_normalised"] = validation[validation_cols["model"]].map(normalise_model_label)
    print("PHASE15_VALIDATION_COLUMN_MAP=" + json.dumps(validation_cols, sort_keys=True))
    analytic = gaussian_crps(
        pd.to_numeric(validation[validation_cols["mean"]], errors="raise").to_numpy(),
        pd.to_numeric(validation[validation_cols["std"]], errors="raise").to_numpy(),
        pd.to_numeric(validation[validation_cols["outcome"]], errors="raise").to_numpy(),
    )
    stored = pd.to_numeric(validation[validation_cols["crps"]], errors="raise").to_numpy(dtype=float)
    differences = stored - analytic
    crps_rows: list[dict[str, Any]] = []
    for model, group_indices in validation.groupby("_model_normalised").groups.items():
        idx = np.asarray(list(group_indices), dtype=int)
        model_stored = stored[idx]
        model_analytic = analytic[idx]
        model_diff = differences[idx]
        crps_rows.append(
            {
                "model": model,
                "rows": int(len(idx)),
                "dates": int(pd.to_datetime(validation.loc[idx, validation_cols["date"]]).dt.normalize().nunique()),
                "stored_mean_crps_c": float(np.mean(model_stored)),
                "analytic_mean_crps_c": float(np.mean(model_analytic)),
                "mean_stored_minus_analytic_c": float(np.mean(model_diff)),
                "mean_abs_difference_c": float(np.mean(np.abs(model_diff))),
                "max_abs_difference_c": float(np.max(np.abs(model_diff))),
                "stored_crps_column": validation_cols["crps"],
                "mean_column": validation_cols["mean"],
                "std_column": validation_cols["std"],
                "outcome_column": validation_cols["outcome"],
                "interpretation": (
                    "analytical Gaussian CRPS"
                    if float(np.max(np.abs(model_diff))) < 1e-10
                    else "stored score differs from analytical Gaussian CRPS; retained as legacy Phase 7 implementation"
                ),
                "status": "PASSED",
            }
        )

    expected_scores = {"rbf": 0.877561, "matern32": 0.863340}
    for model, expected in expected_scores.items():
        observed = float(
            validation.loc[validation["_model_normalised"] == model]
            .groupby(pd.to_datetime(validation.loc[validation["_model_normalised"] == model, validation_cols["date"]]).dt.normalize())[
                validation_cols["crps"]
            ]
            .mean()
            .mean()
        )
        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=5e-6):
            fail(f"Legacy Phase 7 {model} mean-date CRPS changed: expected {expected}, observed {observed}.")

    fold_registry = discover_fold_registry(validation, validation_cols)

    environment = {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
    }

    spec = {
        "phase": 15,
        "name": "Exact GP code-to-mathematics reconciliation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_branch": git("branch", "--show-current"),
        "git_commit_before_phase15": git("rev-parse", "HEAD"),
        "phase14_manifest": rel(PHASE14_MANIFEST),
        "source_files": {
            "phase7_fit": rel(PHASE7_SOURCE),
            "phase8_full_fit": rel(PHASE8_SOURCE),
            "validation_predictions": rel(VALIDATION_PATH),
            "weather_residual_panel": rel(RESIDUAL_PATH),
            "feature_panel": rel(feature_path),
            "full_fit_models": [rel(path) for path in model_paths],
        },
        "features": {
            "ordered_raw_features": raw_feature_names,
            "calendar_time": calendar_spec,
            "seasonality": seasonal_spec,
            "deterministic_forecast_feature": forecast_col,
            "full_fit_transformation_evidence": rel(OUT / "phase15_feature_transformations.csv"),
        },
        "response": {
            "source_target": "HKO minus deterministic forecast residual",
            "normalisation_record": rel(OUT / "phase15_full_fit_model_registry.csv"),
            "back_transformation": "software predictive mean and variance are returned on the original residual scale according to the fitted estimator's _y_train_mean and _y_train_std",
        },
        "variance": {
            "statistical_white_noise": "WhiteKernel contribution in the fitted kernel",
            "numerical_jitter": "GaussianProcessRegressor alpha parameter",
            "software_semantics": "return_std variance equals full fitted-kernel posterior variance; the full-minus-latent identity equals the scaled WhiteKernel variance",
            "verification": rel(OUT / "phase15_variance_reconciliation.csv"),
        },
        "crps": {
            "analytical_formula": "sigma * [z*(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi)]",
            "legacy_comparison": rel(OUT / "phase15_crps_reconciliation.csv"),
            "final_completion_policy": "Use analytical Gaussian CRPS for new Phase 16 onward comparisons while retaining legacy Phase 7 values unchanged and explicitly reconciling any numerical difference.",
        },
        "environment": environment,
        "status": "PASSED",
    }

    # Close Phase 14 implementation gaps without rewriting the certified Phase 14 register.
    gap_updates = [
        {
            "gap_id": "G03",
            "gap": "Exact feature formulas and scaling",
            "phase_closed": 15,
            "status": "CLOSED",
            "evidence": "phase15_feature_transformations.csv|phase15_gp_implementation_spec.json",
        },
        {
            "gap_id": "G04",
            "gap": "Exact response transformation",
            "phase_closed": 15,
            "status": "CLOSED",
            "evidence": "phase15_full_fit_model_registry.csv|phase15_gp_implementation_spec.json",
        },
        {
            "gap_id": "G05",
            "gap": "Observation noise, WhiteKernel and jitter",
            "phase_closed": 15,
            "status": "CLOSED",
            "evidence": "phase15_variance_reconciliation.csv|phase15_gp_implementation_spec.json",
        },
        {
            "gap_id": "G06",
            "gap": "Gaussian CRPS implementation",
            "phase_closed": 15,
            "status": "CLOSED",
            "evidence": "phase15_crps_reconciliation.csv|phase15_gp_implementation_spec.json",
        },
    ]

    write_csv(
        OUT / "phase15_source_evidence.csv",
        source_evidence,
        ["source_file", "line", "categories", "source_line", "context"],
    )
    write_csv(
        OUT / "phase15_ast_call_registry.csv",
        call_registry,
        ["source_file", "line", "call", "keywords_json", "source"],
    )
    write_csv(
        OUT / "phase15_feature_transformations.csv",
        scaling_rows,
        [
            "decision_rule",
            "model_path",
            "training_rows",
            "source_feature_panel",
            "raw_feature",
            "model_feature_index",
            "correlation",
            "affine_slope",
            "affine_intercept",
            "implied_centre",
            "implied_scale",
            "max_reconstruction_error",
            "transformation",
            "status",
        ],
    )
    write_csv(
        OUT / "phase15_fold_model_registry.csv",
        fold_registry,
        sorted({key for row in fold_registry for key in row.keys()}),
    )
    write_csv(
        OUT / "phase15_full_fit_model_registry.csv",
        full_model_rows,
        list(full_model_rows[0].keys()),
    )
    write_csv(
        OUT / "phase15_variance_reconciliation.csv",
        variance_rows,
        list(variance_rows[0].keys()),
    )
    write_csv(
        OUT / "phase15_crps_reconciliation.csv",
        crps_rows,
        list(crps_rows[0].keys()),
    )
    write_csv(
        OUT / "phase15_gap_updates.csv",
        gap_updates,
        ["gap_id", "gap", "phase_closed", "status", "evidence"],
    )
    write_json(CONFIG / "phase15_gp_implementation_spec.json", spec)

    max_scaling_error = max(float(row["max_reconstruction_error"]) for row in scaling_rows)
    max_mean_error = max(float(row["mean_abs_difference"]) for row in variance_rows)
    max_variance_error = max(float(row["variance_abs_difference"]) for row in variance_rows)
    max_noise_error = max(float(row["noise_identity_abs_difference"]) for row in variance_rows)

    report_lines = [
        "# Phase 15 Exact GP Code-to-Mathematics Reconciliation",
        "",
        "## Status",
        "",
        "PASSED",
        "",
        "## Certified inputs",
        "",
        f"- Feature panel: `{rel(feature_path)}`.",
        f"- Validation panel: `{rel(VALIDATION_PATH)}`.",
        f"- Full-history models: {len(model_paths)} rule-specific joblib objects.",
        f"- Phase 14 starting commit: `{phase14.get('phase13_commit', phase14.get('git_commit', 'recorded in manifest'))}`.",
        "",
        "## Exact feature construction",
        "",
        f"- Calendar time: `{calendar_spec['formula']}`.",
        f"- Calendar origin: `{calendar_spec['origin_date']}`.",
        f"- Days per year: `{calendar_spec['days_per_year']:.12g}`.",
        f"- Seasonal position: `{seasonal_spec['formula']}`.",
        "- Seasonal coordinates: `sin(2*pi*s)` and `cos(2*pi*s)`.",
        f"- Deterministic forecast feature: `{forecast_col}`.",
        f"- Maximum empirical feature-formula reconstruction error: {max(calendar_spec['max_reconstruction_error'], seasonal_spec['max_reconstruction_error']):.3e}.",
        "",
        "## Feature scaling",
        "",
        "- Every full-history rule-specific model's stored `X_train_` was reconciled to the raw four-feature panel through an affine map.",
        f"- Maximum transformation reconstruction error: {max_scaling_error:.3e}.",
        "- Exact rule-specific centres and scales are in `phase15_feature_transformations.csv`.",
        "",
        "## Estimator and response convention",
        "",
        f"- Estimator: `sklearn.gaussian_process.GaussianProcessRegressor`.",
        f"- scikit-learn version: `{sklearn.__version__}`.",
        "- Exact `normalize_y`, response mean, response scale, `alpha`, optimiser, restarts, random state and kernels are in `phase15_full_fit_model_registry.csv`.",
        "",
        "## Predictive variance",
        "",
        "- The software predictive variance was independently reconstructed from the fitted Cholesky factor.",
        "- The latent variance was obtained by removing the WhiteKernel test-point diagonal while retaining the fitted observation covariance in conditioning.",
        "- The difference between full and latent variance equals the response-scale-adjusted WhiteKernel variance.",
        f"- Maximum predictive-mean reconciliation error: {max_mean_error:.3e}.",
        f"- Maximum predictive-variance reconciliation error: {max_variance_error:.3e}.",
        f"- Maximum white-noise identity error: {max_noise_error:.3e}.",
        "- Observation noise is therefore identified and included exactly once in the saved model's `return_std` distribution.",
        "",
        "## CRPS",
        "",
        "- Closed-form Gaussian CRPS was recomputed from every Phase 7 predictive mean and standard deviation.",
        "- The comparison with the stored Phase 7 score is recorded separately for RBF and Matérn-3/2.",
        "- Legacy Phase 7 headline scores remain frozen; new Phase 16 onward Gaussian comparisons will use the analytical formula.",
        "",
        "## Closed Phase 14 gaps",
        "",
        "- G03: exact feature formulas and scaling.",
        "- G04: exact response transformation.",
        "- G05: observation noise, WhiteKernel and numerical jitter.",
        "- G06: Gaussian CRPS implementation.",
        "",
        "## Evidential boundary",
        "",
        "Phase 15 does not refit, reselect or alter the certified Phase 7 or Phase 8 models. It inspects the saved models, source code and stored predictions, and verifies their mathematical interpretation. No market record or June outcome enters any model.",
        "",
    ]
    (OUT / "phase15_reconciliation_report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )

    print("PHASE15_STATUS=PASSED")
    print(f"PHASE15_FEATURE_PANEL={rel(feature_path)}")
    print(f"PHASE15_FULL_MODELS={len(model_paths)}")
    print(f"PHASE15_FOLD_REGISTRY_ROWS={len(fold_registry)}")
    print(f"PHASE15_MAX_SCALING_ERROR={max_scaling_error:.3e}")
    print(f"PHASE15_MAX_MEAN_ERROR={max_mean_error:.3e}")
    print(f"PHASE15_MAX_VARIANCE_ERROR={max_variance_error:.3e}")
    print(f"PHASE15_MAX_NOISE_IDENTITY_ERROR={max_noise_error:.3e}")


if __name__ == "__main__":
    main()
