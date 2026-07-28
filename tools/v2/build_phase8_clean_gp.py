#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (
    ConstantKernel,
    Matern,
    WhiteKernel,
)
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "config/v2/phase8_clean_gp_spec.json"

DATE_COLUMNS = [
    "target_date",
    "event_date",
    "contract_date",
    "settlement_date",
    "date",
]

RULE_COLUMNS = [
    "decision_rule",
    "current_decision_rule",
]

FORECAST_COLUMNS = [
    "forecast_daily_max_c",
    "deterministic_forecast_daily_max_c",
    "raw_forecast_daily_max_c",
    "source_forecast_daily_max_c",
    "forecast_max_c",
    "forecast_value",
]

RESIDUAL_COLUMNS = [
    "residual_hko_minus_forecast_c",
    "hko_minus_forecast_c",
    "residual_c",
    "residual",
    "forecast_residual_c",
    "forecast_error_c",
]

OBSERVED_COLUMNS = [
    "hko_daily_max_c",
    "observed_daily_max_c",
    "realised_daily_max_c",
    "actual_daily_max_c",
    "observed_max_c",
]

RULE_ALIASES = {
    "24h": "24h_prior",
    "24hr": "24h_prior",
    "24hprior": "24h_prior",
    "24_hours_prior": "24h_prior",
    "12h": "12h_prior",
    "12hr": "12h_prior",
    "12hprior": "12h_prior",
    "12_hours_prior": "12h_prior",
    "6h": "6h_prior",
    "6hr": "6h_prior",
    "6hprior": "6h_prior",
    "6_hours_prior": "6h_prior",
    "open": "event_day_open",
    "event_open": "event_day_open",
    "eventdayopen": "event_day_open",
    "event_day": "event_day_open",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def first_existing(
    columns: pd.Index,
    candidates: list[str],
) -> str | None:
    return next(
        (
            column
            for column in candidates
            if column in columns
        ),
        None,
    )


def normalise_rules(series: pd.Series) -> pd.Series:
    normalised = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
    )

    return normalised.replace(RULE_ALIASES)


def parse_dates(series: pd.Series) -> pd.Series:
    return (
        pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
            utc=True,
        )
        .dt.tz_convert(None)
        .dt.normalize()
    )


def source_candidates() -> list[Path]:
    roots = [
        ROOT / "data/processed",
        ROOT / "artifacts",
        ROOT / "outputs",
    ]

    candidates: list[Path] = []

    for search_root in roots:
        if not search_root.exists():
            continue

        for path in search_root.rglob("*.csv"):
            lower = str(path).lower()

            if "phase8_clean_gp" in lower:
                continue

            if (
                "residual" in lower
                or "phase5" in lower
                or "/v2/" in lower
            ):
                try:
                    if path.stat().st_size <= 150_000_000:
                        candidates.append(path)
                except OSError:
                    continue

    return sorted(set(candidates))


def prepare_residual_candidate(
    path: Path,
    expected_rules: list[str],
) -> pd.DataFrame | None:
    try:
        header = pd.read_csv(
            path,
            nrows=0,
        ).columns
    except Exception:
        return None

    date_column = first_existing(
        header,
        DATE_COLUMNS,
    )

    rule_column = first_existing(
        header,
        RULE_COLUMNS,
    )

    forecast_column = first_existing(
        header,
        FORECAST_COLUMNS,
    )

    residual_column = first_existing(
        header,
        RESIDUAL_COLUMNS,
    )

    observed_column = first_existing(
        header,
        OBSERVED_COLUMNS,
    )

    if date_column is None or rule_column is None:
        return None

    if forecast_column is None and not (
        observed_column is not None
        and residual_column is not None
    ):
        return None

    if residual_column is None and not (
        observed_column is not None
        and forecast_column is not None
    ):
        return None

    try:
        frame = pd.read_csv(
            path,
            low_memory=False,
        )
    except Exception:
        return None

    dates = parse_dates(
        frame[date_column]
    )

    rules = normalise_rules(
        frame[rule_column]
    )

    observed = (
        pd.to_numeric(
            frame[observed_column],
            errors="coerce",
        )
        if observed_column is not None
        else None
    )

    forecast = (
        pd.to_numeric(
            frame[forecast_column],
            errors="coerce",
        )
        if forecast_column is not None
        else None
    )

    residual = (
        pd.to_numeric(
            frame[residual_column],
            errors="coerce",
        )
        if residual_column is not None
        else None
    )

    if forecast is None:
        forecast = observed - residual

    if residual is None:
        residual = observed - forecast

    candidate = pd.DataFrame(
        {
            "target_date": dates,
            "decision_rule": rules,
            "forecast_daily_max_c": forecast,
            "residual_c": residual,
        }
    )

    candidate = candidate.loc[
        candidate["target_date"].notna()
        & candidate["decision_rule"].isin(
            expected_rules
        )
        & np.isfinite(
            candidate["forecast_daily_max_c"]
        )
        & np.isfinite(
            candidate["residual_c"]
        )
    ].copy()

    if candidate.empty:
        return None

    conflict_counts = (
        candidate.groupby(
            [
                "target_date",
                "decision_rule",
            ]
        )[
            [
                "forecast_daily_max_c",
                "residual_c",
            ]
        ]
        .nunique(
            dropna=True
        )
    )

    if conflict_counts.gt(1).any().any():
        return None

    candidate = (
        candidate.sort_values(
            [
                "target_date",
                "decision_rule",
            ],
            kind="stable",
        )
        .drop_duplicates(
            [
                "target_date",
                "decision_rule",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    if (
        len(candidate) != 2920
        or candidate["target_date"].nunique() != 730
        or set(candidate["decision_rule"].unique())
        != set(expected_rules)
    ):
        return None

    mean_residual = float(
        candidate["residual_c"].mean()
    )

    mean_absolute_residual = float(
        candidate["residual_c"].abs().mean()
    )

    # Phase 5 certified approximately:
    # mean residual 1.429658 C and MAE 1.680068 C.
    if abs(mean_residual + 1.429658) < 0.20:
        candidate["residual_c"] *= -1.0
        mean_residual *= -1.0

    if (
        abs(mean_residual - 1.429658) > 0.30
        or abs(mean_absolute_residual - 1.680068) > 0.30
    ):
        return None

    candidate.attrs["date_column"] = date_column
    candidate.attrs["rule_column"] = rule_column
    candidate.attrs["forecast_column"] = forecast_column
    candidate.attrs["residual_column"] = residual_column
    candidate.attrs["observed_column"] = observed_column

    return candidate


def discover_residual_panel(
    expected_rules: list[str],
) -> tuple[Path, pd.DataFrame]:
    matches: list[
        tuple[int, Path, pd.DataFrame]
    ] = []

    for path in source_candidates():
        candidate = prepare_residual_candidate(
            path,
            expected_rules,
        )

        if candidate is None:
            continue

        lower = str(path).lower()

        score = 0
        score += 20 if "residual" in lower else 0
        score += 10 if "phase5" in lower else 0
        score += 5 if "/v2/" in lower else 0

        matches.append(
            (
                score,
                path,
                candidate,
            )
        )

    if not matches:
        raise RuntimeError(
            "Could not discover the certified Phase 5 "
            "730-date, 2,920-row residual panel."
        )

    matches.sort(
        key=lambda item: (
            -item[0],
            len(str(item[1])),
            str(item[1]),
        )
    )

    selected = matches[0]

    return selected[1], selected[2]


def discover_settlement_universe(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[Path, str, pd.DatetimeIndex]:
    directory = (
        ROOT
        / "data/processed"
        / "18s_expanded_march_june_canonical_sample"
    )

    if not directory.exists():
        raise FileNotFoundError(directory)

    matches: list[
        tuple[int, Path, str, pd.DatetimeIndex]
    ] = []

    for path in directory.rglob("*.csv"):
        try:
            header = pd.read_csv(
                path,
                nrows=0,
            ).columns
        except Exception:
            continue

        for date_column in DATE_COLUMNS:
            if date_column not in header:
                continue

            try:
                values = pd.read_csv(
                    path,
                    usecols=[date_column],
                    low_memory=False,
                )
            except Exception:
                continue

            dates = parse_dates(
                values[date_column]
            )

            dates = pd.DatetimeIndex(
                sorted(
                    dates.loc[
                        dates.between(
                            start_date,
                            end_date,
                        )
                    ]
                    .dropna()
                    .unique()
                )
            )

            if len(dates) != 103:
                continue

            lower = path.name.lower()

            score = 0
            score += 10 if "canonical" in lower else 0
            score += 8 if "realised" in lower else 0
            score += 5 if "sample" in lower else 0
            score += 3 if "contract" in lower else 0

            matches.append(
                (
                    score,
                    path,
                    date_column,
                    dates,
                )
            )

    if not matches:
        raise RuntimeError(
            "Could not discover a certified 103-date "
            "settlement and market universe."
        )

    matches.sort(
        key=lambda item: (
            -item[0],
            len(str(item[1])),
            str(item[1]),
        )
    )

    selected = matches[0]

    return (
        selected[1],
        selected[2],
        selected[3],
    )


def load_certified_forecasts(
    path: Path,
    expected_rules: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, int]:
    if not path.exists():
        raise FileNotFoundError(path)

    raw = pd.read_csv(
        path,
        low_memory=False,
    )

    required = {
        "event_date",
        "decision_rule",
        "forecast_daily_max_c",
    }

    missing = required - set(raw.columns)

    if missing:
        raise RuntimeError(
            "Certified forecast source is missing: "
            + ", ".join(sorted(missing))
        )

    panel = pd.DataFrame(
        {
            "target_date": parse_dates(
                raw["event_date"]
            ),
            "decision_rule": normalise_rules(
                raw["decision_rule"]
            ),
            "forecast_daily_max_c": pd.to_numeric(
                raw["forecast_daily_max_c"],
                errors="coerce",
            ),
        }
    )

    panel = panel.loc[
        panel["target_date"].between(
            start_date,
            end_date,
        )
        & panel["decision_rule"].isin(
            expected_rules
        )
        & np.isfinite(
            panel["forecast_daily_max_c"]
        )
    ].copy()

    conflicts = (
        panel.groupby(
            [
                "target_date",
                "decision_rule",
            ]
        )[
            "forecast_daily_max_c"
        ]
        .nunique(
            dropna=True
        )
    )

    if conflicts.gt(1).any():
        raise RuntimeError(
            "Conflicting deterministic forecast values "
            "exist within a date-rule key."
        )

    raw_valid_rows = len(panel)

    panel = (
        panel.sort_values(
            [
                "target_date",
                "decision_rule",
            ],
            kind="stable",
        )
        .drop_duplicates(
            [
                "target_date",
                "decision_rule",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    if (
        panel["target_date"].nunique() != 102
        or len(panel) != 375
    ):
        raise RuntimeError(
            "Certified deterministic source must produce "
            "102 dates and 375 date-rule rows; found "
            f"{panel['target_date'].nunique()} dates and "
            f"{len(panel)} rows."
        )

    return panel, raw_valid_rows


def feature_matrix(
    frame: pd.DataFrame,
    origin: pd.Timestamp,
) -> np.ndarray:
    dates = pd.to_datetime(
        frame["target_date"]
    )

    time_years = (
        (
            dates
            - origin
        ).dt.total_seconds()
        / (
            365.2425
            * 24.0
            * 60.0
            * 60.0
        )
    )

    seasonal_angle = (
        2.0
        * np.pi
        * (
            dates.dt.dayofyear.to_numpy(
                dtype=float
            )
            - 1.0
        )
        / 365.2425
    )

    return np.column_stack(
        [
            time_years.to_numpy(
                dtype=float
            ),
            np.sin(seasonal_angle),
            np.cos(seasonal_angle),
            frame[
                "forecast_daily_max_c"
            ].to_numpy(
                dtype=float
            ),
        ]
    )


def atomic_replace_directory(
    staged: Path,
    target: Path,
) -> None:
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if target.exists():
        shutil.rmtree(target)

    shutil.move(
        str(staged),
        str(target),
    )


def main() -> None:
    warnings.filterwarnings(
        "ignore",
        category=pd.errors.PerformanceWarning,
    )

    specification = load_json(
        SPEC_PATH
    )

    rules = specification[
        "decision_rules"
    ]

    counts = specification[
        "expected_counts"
    ]

    periods = specification[
        "periods"
    ]

    start_date = pd.Timestamp(
        periods["market_period_start"]
    )

    training_end = pd.Timestamp(
        periods[
            "weather_plus_market_training_end"
        ]
    )

    validation_start = pd.Timestamp(
        periods[
            "out_of_sample_validation_start"
        ]
    )

    validation_end = pd.Timestamp(
        periods[
            "out_of_sample_validation_end"
        ]
    )

    forecast_source = (
        ROOT
        / specification[
            "certified_forecast_source"
        ]
    )

    residual_source, residual_panel = (
        discover_residual_panel(rules)
    )

    (
        settlement_source,
        settlement_date_column,
        settlement_dates,
    ) = discover_settlement_universe(
        start_date,
        validation_end,
    )

    forecast_panel, raw_forecast_rows = (
        load_certified_forecasts(
            forecast_source,
            rules,
            start_date,
            validation_end,
        )
    )

    if (
        residual_panel["target_date"].nunique()
        != counts["weather_only_training_dates"]
        or len(residual_panel)
        != counts[
            "weather_only_training_date_rule_rows"
        ]
    ):
        raise RuntimeError(
            "Weather-only residual panel count mismatch."
        )

    if (
        len(settlement_dates)
        != counts[
            "settlement_market_universe_dates"
        ]
    ):
        raise RuntimeError(
            "Settlement universe count mismatch."
        )

    supported_dates = pd.DatetimeIndex(
        sorted(
            forecast_panel[
                "target_date"
            ].unique()
        )
    )

    if not supported_dates.isin(
        settlement_dates
    ).all():
        raise RuntimeError(
            "Forecast support contains dates outside "
            "the settlement and market universe."
        )

    theoretical_support = pd.MultiIndex.from_product(
        [
            settlement_dates,
            rules,
        ],
        names=[
            "target_date",
            "decision_rule",
        ],
    ).to_frame(
        index=False
    )

    supported_keys = forecast_panel[
        [
            "target_date",
            "decision_rule",
        ]
    ].drop_duplicates()

    missing_support = (
        theoretical_support.merge(
            supported_keys.assign(
                _supported=True
            ),
            on=[
                "target_date",
                "decision_rule",
            ],
            how="left",
        )
        .loc[
            lambda frame:
            frame["_supported"].isna(),
            [
                "target_date",
                "decision_rule",
            ],
        ]
        .sort_values(
            [
                "target_date",
                "decision_rule",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if (
        len(theoretical_support)
        != counts[
            "theoretical_market_date_rule_rows"
        ]
        or len(missing_support)
        != counts[
            "missing_forecast_date_rule_rows"
        ]
    ):
        raise RuntimeError(
            "Theoretical or missing forecast support "
            "count mismatch."
        )

    dates_without_any_forecast = (
        pd.Index(settlement_dates)
        .difference(
            pd.Index(supported_dates)
        )
    )

    if len(dates_without_any_forecast) != 1:
        raise RuntimeError(
            "Expected exactly one settlement date with "
            "no deterministic forecast support."
        )

    origin = residual_panel[
        "target_date"
    ].min()

    parameters = specification[
        "fixed_phase7_kernel_parameters"
    ]

    prediction_parts: list[pd.DataFrame] = []
    model_summary_rows: list[dict[str, Any]] = []

    stage_root = Path(
        tempfile.mkdtemp(
            prefix="phase8_clean_gp_"
        )
    )

    stage_data = stage_root / "data"
    stage_models = stage_root / "models"

    stage_data.mkdir(
        parents=True,
        exist_ok=True,
    )

    stage_models.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        for rule in rules:
            training_rule = (
                residual_panel.loc[
                    residual_panel[
                        "decision_rule"
                    ].eq(rule)
                ]
                .sort_values(
                    "target_date",
                    kind="stable",
                )
                .reset_index(drop=True)
            )

            prediction_rule = (
                forecast_panel.loc[
                    forecast_panel[
                        "decision_rule"
                    ].eq(rule)
                ]
                .sort_values(
                    "target_date",
                    kind="stable",
                )
                .reset_index(drop=True)
            )

            if len(training_rule) != 730:
                raise RuntimeError(
                    f"{rule} does not contain "
                    "730 weather-only training dates."
                )

            parameter = parameters[rule]

            kernel = (
                ConstantKernel(
                    constant_value=(
                        float(
                            parameter["amplitude"]
                        )
                        ** 2
                    ),
                    constant_value_bounds="fixed",
                )
                * Matern(
                    length_scale=float(
                        parameter["length_scale"]
                    ),
                    length_scale_bounds="fixed",
                    nu=1.5,
                )
                + WhiteKernel(
                    noise_level=float(
                        parameter["noise_level"]
                    ),
                    noise_level_bounds="fixed",
                )
            )

            x_train = feature_matrix(
                training_rule,
                origin,
            )

            x_predict = feature_matrix(
                prediction_rule,
                origin,
            )

            y_train = training_rule[
                "residual_c"
            ].to_numpy(
                dtype=float
            )

            scaler = StandardScaler()
            x_train_scaled = scaler.fit_transform(
                x_train
            )

            x_predict_scaled = scaler.transform(
                x_predict
            )

            model = GaussianProcessRegressor(
                kernel=kernel,
                alpha=1e-10,
                optimizer=None,
                normalize_y=True,
                random_state=20260728,
            )

            model.fit(
                x_train_scaled,
                y_train,
            )

            residual_mean, residual_std = (
                model.predict(
                    x_predict_scaled,
                    return_std=True,
                )
            )

            corrected_mean = (
                prediction_rule[
                    "forecast_daily_max_c"
                ].to_numpy(
                    dtype=float
                )
                + residual_mean
            )

            quantile_levels = (
                np.arange(
                    1,
                    100,
                    dtype=float,
                )
                / 100.0
            )

            quantile_values = (
                corrected_mean[:, None]
                + residual_std[:, None]
                * norm.ppf(
                    quantile_levels
                )[None, :]
            )

            quantile_columns = [
                f"gp_temperature_q{index:02d}_c"
                for index in range(
                    1,
                    100,
                )
            ]

            base_output = prediction_rule[
                [
                    "target_date",
                    "decision_rule",
                    "forecast_daily_max_c",
                ]
            ].copy()

            diagnostics = pd.DataFrame(
                {
                    "gp_residual_mean_c":
                        residual_mean,
                    "gp_residual_std_c":
                        residual_std,
                    "gp_temperature_mean_c":
                        corrected_mean,
                    "gp_temperature_std_c":
                        residual_std,
                }
            )

            quantiles = pd.DataFrame(
                quantile_values,
                columns=quantile_columns,
            )

            rule_output = pd.concat(
                [
                    base_output.reset_index(
                        drop=True
                    ),
                    diagnostics,
                    quantiles,
                ],
                axis=1,
            )

            prediction_parts.append(
                rule_output
            )

            model_file = (
                stage_models
                / f"{rule}_matern32_full_fit.joblib"
            )

            joblib.dump(
                {
                    "decision_rule": rule,
                    "feature_origin": origin,
                    "feature_columns": [
                        "calendar_time_years",
                        "seasonal_sin",
                        "seasonal_cos",
                        "forecast_daily_max_c",
                    ],
                    "scaler": scaler,
                    "model": model,
                    "fixed_kernel_parameters":
                        parameter,
                },
                model_file,
            )

            model_summary_rows.append(
                {
                    "decision_rule": rule,
                    "kernel_family": "matern32",
                    "training_dates":
                        training_rule[
                            "target_date"
                        ].nunique(),
                    "training_rows":
                        len(training_rule),
                    "training_residual_mean_c":
                        float(
                            training_rule[
                                "residual_c"
                            ].mean()
                        ),
                    "training_residual_mae_c":
                        float(
                            training_rule[
                                "residual_c"
                            ].abs().mean()
                        ),
                    "kernel":
                        str(model.kernel_),
                    "model_file":
                        model_file.name,
                }
            )

        predictions = (
            pd.concat(
                prediction_parts,
                ignore_index=True,
            )
            .sort_values(
                [
                    "target_date",
                    "decision_rule",
                ],
                kind="stable",
            )
            .reset_index(drop=True)
        )

        if (
            predictions[
                "target_date"
            ].nunique()
            != counts[
                "forecast_supported_dates"
            ]
            or len(predictions)
            != counts[
                "forecast_supported_date_rule_rows"
            ]
        ):
            raise RuntimeError(
                "Final GP prediction support count mismatch."
            )

        weather_plus_market_training = (
            predictions.loc[
                predictions[
                    "target_date"
                ].between(
                    start_date,
                    training_end,
                )
            ]
            .copy()
            .reset_index(drop=True)
        )

        out_of_sample_validation = (
            predictions.loc[
                predictions[
                    "target_date"
                ].between(
                    validation_start,
                    validation_end,
                )
            ]
            .copy()
            .reset_index(drop=True)
        )

        if (
            weather_plus_market_training[
                "target_date"
            ].nunique()
            != counts[
                "weather_plus_market_training_dates"
            ]
        ):
            raise RuntimeError(
                "Weather-plus-market training support "
                "does not contain 72 dates; found "
                f"{weather_plus_market_training['target_date'].nunique()}."
            )

        if (
            out_of_sample_validation[
                "target_date"
            ].nunique()
            != counts[
                "out_of_sample_validation_dates"
            ]
        ):
            raise RuntimeError(
                "June validation support does not contain "
                "30 dates; found "
                f"{out_of_sample_validation['target_date'].nunique()}."
            )

        settlement_universe = pd.DataFrame(
            {
                "target_date":
                    settlement_dates,
            }
        )

        missing_support[
            "missing_reason"
        ] = (
            "no_certified_deterministic_forecast"
        )

        model_summary = pd.DataFrame(
            model_summary_rows
        )

        residual_output = (
            residual_panel.sort_values(
                [
                    "target_date",
                    "decision_rule",
                ],
                kind="stable",
            )
            .reset_index(drop=True)
        )

        residual_output.to_csv(
            stage_data
            / "phase8_weather_only_training_panel.csv",
            index=False,
        )

        predictions.to_csv(
            stage_data
            / "phase8_gp_market_period_predictions.csv",
            index=False,
        )

        weather_plus_market_training.to_csv(
            stage_data
            / "phase8_weather_plus_market_training_panel.csv",
            index=False,
        )

        out_of_sample_validation.to_csv(
            stage_data
            / "phase8_june_out_of_sample_panel.csv",
            index=False,
        )

        settlement_universe.to_csv(
            stage_data
            / "phase8_settlement_market_universe_dates.csv",
            index=False,
        )

        missing_support.to_csv(
            stage_data
            / "phase8_missing_forecast_support.csv",
            index=False,
        )

        model_summary.to_csv(
            stage_data
            / "phase8_gp_model_summary.csv",
            index=False,
        )

        manifest = {
            "phase": 8,
            "status": "passed",
            "selected_kernel_family":
                "matern32",
            "inputs": {
                "residual_panel": {
                    "path": str(
                        residual_source.relative_to(
                            ROOT
                        )
                    ),
                    "sha256": sha256(
                        residual_source
                    ),
                },
                "settlement_universe": {
                    "path": str(
                        settlement_source.relative_to(
                            ROOT
                        )
                    ),
                    "date_column":
                        settlement_date_column,
                    "sha256": sha256(
                        settlement_source
                    ),
                },
                "certified_forecasts": {
                    "path": str(
                        forecast_source.relative_to(
                            ROOT
                        )
                    ),
                    "sha256": sha256(
                        forecast_source
                    ),
                    "raw_valid_rows":
                        raw_forecast_rows,
                },
            },
            "counts": {
                "weather_only_training_dates":
                    residual_panel[
                        "target_date"
                    ].nunique(),
                "weather_only_training_date_rule_rows":
                    len(residual_panel),
                "settlement_market_universe_dates":
                    len(settlement_dates),
                "theoretical_market_date_rule_rows":
                    len(theoretical_support),
                "forecast_supported_dates":
                    predictions[
                        "target_date"
                    ].nunique(),
                "forecast_supported_date_rule_rows":
                    len(predictions),
                "missing_forecast_date_rule_rows":
                    len(missing_support),
                "settlement_dates_without_any_forecast":
                    len(
                        dates_without_any_forecast
                    ),
                "weather_plus_market_training_dates":
                    weather_plus_market_training[
                        "target_date"
                    ].nunique(),
                "weather_plus_market_training_rows":
                    len(
                        weather_plus_market_training
                    ),
                "out_of_sample_validation_dates":
                    out_of_sample_validation[
                        "target_date"
                    ].nunique(),
                "out_of_sample_validation_rows":
                    len(
                        out_of_sample_validation
                    ),
            },
            "settlement_dates_without_any_forecast": [
                str(
                    pd.Timestamp(date).date()
                )
                for date in
                dates_without_any_forecast
            ],
            "restrictions": specification[
                "restrictions"
            ],
        }

        (
            stage_data
            / "phase8_manifest.json"
        ).write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        target_data = (
            ROOT
            / specification[
                "outputs"
            ][
                "data_directory"
            ]
        )

        target_models = (
            ROOT
            / specification[
                "outputs"
            ][
                "model_directory"
            ]
        )

        atomic_replace_directory(
            stage_data,
            target_data,
        )

        atomic_replace_directory(
            stage_models,
            target_models,
        )

        print()
        print(
            "=" * 68
        )
        print(
            "PHASE 8 CLEAN REBUILD: PASSED"
        )
        print(
            "=" * 68
        )
        print(
            "Residual source:",
            residual_source.relative_to(ROOT),
        )
        print(
            "Settlement source:",
            settlement_source.relative_to(ROOT),
        )
        print(
            "Weather-only training:",
            residual_panel[
                "target_date"
            ].nunique(),
            "dates,",
            len(residual_panel),
            "date-rule rows.",
        )
        print(
            "Settlement and market universe:",
            len(settlement_dates),
            "dates,",
            len(theoretical_support),
            "theoretical date-rule rows.",
        )
        print(
            "Certified forecast support:",
            predictions[
                "target_date"
            ].nunique(),
            "dates,",
            len(predictions),
            "date-rule rows.",
        )
        print(
            "Missing forecast support:",
            len(missing_support),
            "date-rule rows.",
        )
        print(
            "Weather-plus-market training:",
            weather_plus_market_training[
                "target_date"
            ].nunique(),
            "dates,",
            len(
                weather_plus_market_training
            ),
            "rows.",
        )
        print(
            "June out-of-sample validation:",
            out_of_sample_validation[
                "target_date"
            ].nunique(),
            "dates,",
            len(
                out_of_sample_validation
            ),
            "rows.",
        )
        print(
            "No forecast imputation was used."
        )
        print(
            "No market prices or outcomes were used."
        )
        print(
            "June was not used for model selection or fitting."
        )
        print(
            "=" * 68
        )
        print(
            "Data outputs:",
            target_data.relative_to(ROOT),
        )
        print(
            "Model outputs:",
            target_models.relative_to(ROOT),
        )

    finally:
        if stage_root.exists():
            shutil.rmtree(
                stage_root,
                ignore_errors=True,
            )


if __name__ == "__main__":
    main()
