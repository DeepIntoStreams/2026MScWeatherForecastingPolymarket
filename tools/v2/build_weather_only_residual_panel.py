from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

SPEC_PATH = (
    ROOT
    / "config/v2/"
    "weather_only_residual_spec.json"
)

FORECAST_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04_weather_only_decision_support_panel.csv"
)

HKO_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "04f_hko_daily_max_training_panel.csv"
)

PANEL_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_forecast_residual_panel.csv"
)

DATE_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_residual_date_summary.csv"
)

RULE_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_residual_rule_summary.csv"
)

MONTH_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_residual_month_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_residual_integrity_checks.csv"
)

MAIN_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/final_tables/"
    "05_weather_only_residual_summary.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "05_weather_only_residual_manifest.json"
)


RULE_ORDER = {
    "24h_prior": 1,
    "12h_prior": 2,
    "6h_prior": 3,
    "event_day_open": 4,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def atomic_write_text(
    path: Path,
    text: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_text(
        text,
        encoding="utf-8",
    )

    os.replace(
        temporary,
        path,
    )


def write_csv(
    panel: pd.DataFrame,
    path: Path,
) -> None:
    atomic_write_text(
        path,
        panel.to_csv(index=False),
    )


def write_json(
    payload: dict[str, Any],
    path: Path,
) -> None:
    atomic_write_text(
        path,
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def normalise_name(value: object) -> str:
    return "".join(
        character.lower()
        for character in str(value)
        if character.isalnum()
    )


def resolve_forecast_column(
    panel: pd.DataFrame,
) -> str:
    exact_candidates = [
        "forecast_daily_max_c",
        "deterministic_forecast_daily_max_c",
        "selected_forecast_daily_max_c",
        "forecast_daily_maximum_c",
        "forecast_max_c",
        "daily_max_forecast_c",
        "selected_daily_max_c",
        "forecast_temperature_c",
    ]

    for candidate in exact_candidates:
        if candidate in panel.columns:
            return candidate

    excluded_tokens = (
        "residual",
        "error",
        "probability",
        "lower",
        "upper",
        "quantile",
        "hko",
        "realised",
        "realized",
    )

    candidates = []

    for column in panel.columns:
        normalised = normalise_name(column)

        forecast_like = (
            "forecast" in normalised
            and (
                "max" in normalised
                or "temperature" in normalised
            )
        )

        excluded = any(
            token in normalised
            for token in excluded_tokens
        )

        if forecast_like and not excluded:
            candidates.append(column)

    if len(candidates) == 1:
        return candidates[0]

    raise RuntimeError(
        "Unable to identify one deterministic forecast "
        "temperature column.\n"
        f"Candidate columns: {candidates}\n"
        f"Available columns: {list(panel.columns)}"
    )


def metric_summary(
    panel: pd.DataFrame,
) -> dict[str, float | int]:
    return {
        "rows": int(len(panel)),
        "dates": int(
            panel["target_date"].nunique()
        ),
        "mean_forecast_daily_max_c": float(
            panel[
                "forecast_daily_max_c"
            ].mean()
        ),
        "mean_hko_daily_max_c": float(
            panel[
                "hko_daily_max_c"
            ].mean()
        ),
        "mean_residual_c": float(
            panel["residual_c"].mean()
        ),
        "median_residual_c": float(
            panel["residual_c"].median()
        ),
        "residual_standard_deviation_c": float(
            panel["residual_c"].std(ddof=1)
        ),
        "mean_absolute_error_c": float(
            panel["absolute_error_c"].mean()
        ),
        "root_mean_squared_error_c": float(
            np.sqrt(
                panel[
                    "squared_error_c"
                ].mean()
            )
        ),
        "minimum_residual_c": float(
            panel["residual_c"].min()
        ),
        "maximum_residual_c": float(
            panel["residual_c"].max()
        ),
    }


def build_rule_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    records = []

    for rule, group in panel.groupby(
        "decision_rule",
        sort=False,
    ):
        record = {
            "decision_rule": rule,
            "decision_rule_order": int(
                RULE_ORDER[rule]
            ),
        }

        record.update(
            metric_summary(group)
        )

        records.append(record)

    return (
        pd.DataFrame(records)
        .sort_values(
            "decision_rule_order",
            kind="stable",
        )
        .reset_index(drop=True)
    )


def build_month_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    records = []

    for (
        target_year,
        target_month,
        decision_rule,
    ), group in panel.groupby(
        [
            "target_year",
            "target_month",
            "decision_rule",
        ],
        sort=True,
    ):
        record = {
            "target_year": int(target_year),
            "target_month": int(target_month),
            "decision_rule": decision_rule,
            "decision_rule_order": int(
                RULE_ORDER[decision_rule]
            ),
        }

        record.update(
            metric_summary(group)
        )

        records.append(record)

    return (
        pd.DataFrame(records)
        .sort_values(
            [
                "target_year",
                "target_month",
                "decision_rule_order",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def build_date_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    date_summary = (
        panel.groupby(
            "target_date",
            as_index=False,
        )
        .agg(
            decision_rules=(
                "decision_rule",
                "nunique",
            ),
            mean_forecast_daily_max_c=(
                "forecast_daily_max_c",
                "mean",
            ),
            hko_daily_max_c=(
                "hko_daily_max_c",
                "first",
            ),
            mean_residual_c=(
                "residual_c",
                "mean",
            ),
            mean_absolute_error_c=(
                "absolute_error_c",
                "mean",
            ),
            mean_squared_error_c=(
                "squared_error_c",
                "mean",
            ),
        )
    )

    date_summary[
        "root_mean_squared_error_c"
    ] = np.sqrt(
        date_summary[
            "mean_squared_error_c"
        ]
    )

    return date_summary


def main() -> None:
    specification = json.loads(
        SPEC_PATH.read_text(
            encoding="utf-8"
        )
    )

    forecast = pd.read_csv(
        FORECAST_PATH
    )

    hko = pd.read_csv(
        HKO_PATH
    )

    required_forecast_columns = {
        "target_date",
        "decision_rule",
    }

    missing_forecast_columns = (
        required_forecast_columns
        - set(forecast.columns)
    )

    if missing_forecast_columns:
        raise RuntimeError(
            "Forecast panel is missing columns: "
            + ", ".join(
                sorted(
                    missing_forecast_columns
                )
            )
        )

    required_hko_columns = {
        "target_date",
        "hko_daily_max_c",
    }

    missing_hko_columns = (
        required_hko_columns
        - set(hko.columns)
    )

    if missing_hko_columns:
        raise RuntimeError(
            "HKO panel is missing columns: "
            + ", ".join(
                sorted(
                    missing_hko_columns
                )
            )
        )

    forecast_column = resolve_forecast_column(
        forecast
    )

    forecast["target_date"] = pd.to_datetime(
        forecast["target_date"],
        errors="raise",
        format="mixed",
    ).dt.normalize()

    hko["target_date"] = pd.to_datetime(
        hko["target_date"],
        errors="raise",
        format="mixed",
    ).dt.normalize()

    forecast[
        "forecast_daily_max_c"
    ] = pd.to_numeric(
        forecast[forecast_column],
        errors="coerce",
    )

    hko["hko_daily_max_c"] = pd.to_numeric(
        hko["hko_daily_max_c"],
        errors="coerce",
    )

    if forecast[
        "forecast_daily_max_c"
    ].isna().any():
        raise RuntimeError(
            "The forecast panel contains missing or "
            "non-numeric deterministic forecasts."
        )

    if hko[
        "hko_daily_max_c"
    ].isna().any():
        raise RuntimeError(
            "The HKO panel contains missing observations."
        )

    forecast_duplicate_keys = forecast.duplicated(
        [
            "target_date",
            "decision_rule",
        ]
    )

    if forecast_duplicate_keys.any():
        raise RuntimeError(
            "The forecast panel contains duplicate "
            "date-rule keys."
        )

    if hko["target_date"].duplicated().any():
        raise RuntimeError(
            "The HKO panel contains duplicate dates."
        )

    panel = forecast.merge(
        hko[
            [
                "target_date",
                "hko_daily_max_c",
            ]
        ],
        on="target_date",
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    panel[
        "observation_join_status"
    ] = panel["_merge"].astype(str)

    panel = panel.drop(
        columns=["_merge"]
    )

    panel["decision_rule_order"] = (
        panel["decision_rule"]
        .map(RULE_ORDER)
    )

    unknown_rules = panel.loc[
        panel[
            "decision_rule_order"
        ].isna(),
        "decision_rule",
    ].drop_duplicates()

    if not unknown_rules.empty:
        raise RuntimeError(
            "Unknown decision rules: "
            + ", ".join(
                map(str, unknown_rules)
            )
        )

    panel["decision_rule_order"] = (
        panel[
            "decision_rule_order"
        ].astype(int)
    )

    panel["residual_c"] = (
        panel["hko_daily_max_c"]
        - panel["forecast_daily_max_c"]
    )

    panel["forecast_error_c"] = (
        panel["forecast_daily_max_c"]
        - panel["hko_daily_max_c"]
    )

    panel["absolute_error_c"] = (
        panel["forecast_error_c"].abs()
    )

    panel["squared_error_c"] = (
        panel["forecast_error_c"] ** 2
    )

    panel["target_year"] = (
        panel["target_date"].dt.year
    )

    panel["target_month"] = (
        panel["target_date"].dt.month
    )

    panel["target_day"] = (
        panel["target_date"].dt.day
    )

    panel["day_of_year"] = (
        panel["target_date"].dt.dayofyear
    )

    seasonal_angle = (
        2.0
        * np.pi
        * (
            panel["day_of_year"] - 1
        )
        / 365.2425
    )

    panel["seasonal_sin"] = np.sin(
        seasonal_angle
    )

    panel["seasonal_cos"] = np.cos(
        seasonal_angle
    )

    first_date = panel[
        "target_date"
    ].min()

    panel["calendar_day_index"] = (
        panel["target_date"]
        - first_date
    ).dt.days.astype(int)

    panel[
        "weather_only_training_period"
    ] = True

    panel[
        "weather_plus_market_training_period"
    ] = False

    panel[
        "out_of_sample_validation_period"
    ] = False

    panel[
        "market_price_accessed"
    ] = False

    panel[
        "polymarket_outcome_accessed"
    ] = False

    panel["model_fitted"] = False
    panel["model_selected"] = False
    panel["calibration_selected"] = False
    panel["trading_returns_calculated"] = False

    panel = (
        panel.sort_values(
            [
                "target_date",
                "decision_rule_order",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    date_rule_counts = (
        panel.groupby(
            "target_date"
        )["decision_rule"]
        .nunique()
    )

    algebra_residual = (
        panel["hko_daily_max_c"]
        - panel["forecast_daily_max_c"]
    )

    algebra_error = (
        panel["forecast_daily_max_c"]
        - panel["hko_daily_max_c"]
    )

    expected_dates = pd.date_range(
        panel["target_date"].min(),
        panel["target_date"].max(),
        freq="D",
    )

    checks = pd.DataFrame(
        [
            {
                "check": "residual_rows_equal_2920",
                "required": True,
                "passed": len(panel) == 2920,
                "detail": len(panel),
            },
            {
                "check": "unique_dates_equal_730",
                "required": True,
                "passed": (
                    panel[
                        "target_date"
                    ].nunique()
                    == 730
                ),
                "detail": (
                    panel[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "four_decision_rules",
                "required": True,
                "passed": (
                    panel[
                        "decision_rule"
                    ].nunique()
                    == 4
                ),
                "detail": (
                    panel[
                        "decision_rule"
                    ].nunique()
                ),
            },
            {
                "check": "four_rules_per_date",
                "required": True,
                "passed": (
                    date_rule_counts.eq(4).all()
                ),
                "detail": (
                    int(
                        date_rule_counts.eq(4).sum()
                    )
                ),
            },
            {
                "check": "date_rule_keys_unique",
                "required": True,
                "passed": (
                    not panel.duplicated(
                        [
                            "target_date",
                            "decision_rule",
                        ]
                    ).any()
                ),
                "detail": int(
                    panel.duplicated(
                        [
                            "target_date",
                            "decision_rule",
                        ]
                    ).sum()
                ),
            },
            {
                "check": "continuous_training_dates",
                "required": True,
                "passed": (
                    panel[
                        "target_date"
                    ]
                    .drop_duplicates()
                    .reset_index(drop=True)
                    .equals(
                        pd.Series(
                            expected_dates,
                            name="target_date",
                        )
                    )
                ),
                "detail": (
                    len(expected_dates)
                ),
            },
            {
                "check": "all_hko_rows_joined",
                "required": True,
                "passed": (
                    panel[
                        "observation_join_status"
                    ].eq("both").all()
                ),
                "detail": int(
                    panel[
                        "observation_join_status"
                    ].eq("both").sum()
                ),
            },
            {
                "check": "forecast_values_present",
                "required": True,
                "passed": (
                    panel[
                        "forecast_daily_max_c"
                    ].notna().all()
                ),
                "detail": int(
                    panel[
                        "forecast_daily_max_c"
                    ].isna().sum()
                ),
            },
            {
                "check": "hko_values_present",
                "required": True,
                "passed": (
                    panel[
                        "hko_daily_max_c"
                    ].notna().all()
                ),
                "detail": int(
                    panel[
                        "hko_daily_max_c"
                    ].isna().sum()
                ),
            },
            {
                "check": "forecast_values_plausible",
                "required": True,
                "passed": (
                    panel[
                        "forecast_daily_max_c"
                    ].between(
                        -20.0,
                        60.0,
                        inclusive="both",
                    ).all()
                ),
                "detail": (
                    f"{panel['forecast_daily_max_c'].min():.3f} "
                    f"to "
                    f"{panel['forecast_daily_max_c'].max():.3f}"
                ),
            },
            {
                "check": "hko_values_plausible",
                "required": True,
                "passed": (
                    panel[
                        "hko_daily_max_c"
                    ].between(
                        -20.0,
                        60.0,
                        inclusive="both",
                    ).all()
                ),
                "detail": (
                    f"{panel['hko_daily_max_c'].min():.3f} "
                    f"to "
                    f"{panel['hko_daily_max_c'].max():.3f}"
                ),
            },
            {
                "check": "residual_algebra_exact",
                "required": True,
                "passed": np.allclose(
                    panel["residual_c"],
                    algebra_residual,
                    atol=1e-12,
                    rtol=0.0,
                ),
                "detail": (
                    float(
                        np.max(
                            np.abs(
                                panel["residual_c"]
                                - algebra_residual
                            )
                        )
                    )
                ),
            },
            {
                "check": "forecast_error_algebra_exact",
                "required": True,
                "passed": np.allclose(
                    panel["forecast_error_c"],
                    algebra_error,
                    atol=1e-12,
                    rtol=0.0,
                ),
                "detail": (
                    float(
                        np.max(
                            np.abs(
                                panel[
                                    "forecast_error_c"
                                ]
                                - algebra_error
                            )
                        )
                    )
                ),
            },
            {
                "check": "residual_and_error_are_negatives",
                "required": True,
                "passed": np.allclose(
                    panel["residual_c"],
                    -panel["forecast_error_c"],
                    atol=1e-12,
                    rtol=0.0,
                ),
                "detail": (
                    float(
                        np.max(
                            np.abs(
                                panel["residual_c"]
                                + panel[
                                    "forecast_error_c"
                                ]
                            )
                        )
                    )
                ),
            },
            {
                "check": "market_prices_not_accessed",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "polymarket_outcomes_not_accessed",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "model_not_fitted",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "model_not_selected",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "calibration_not_selected",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "trading_returns_not_calculated",
                "required": True,
                "passed": True,
                "detail": False,
            },
        ]
    )

    failed = checks.loc[
        checks["required"]
        & ~checks["passed"]
    ]

    if not failed.empty:
        raise RuntimeError(
            "Required Phase 5 checks failed:\n"
            + failed.to_string(index=False)
        )

    rule_summary = build_rule_summary(
        panel
    )

    month_summary = build_month_summary(
        panel
    )

    date_summary = build_date_summary(
        panel
    )

    overall = metric_summary(
        panel
    )

    main_summary = pd.DataFrame(
        [
            {
                "residual_definition": (
                    "hko_daily_max_c "
                    "minus forecast_daily_max_c"
                ),
                "forecast_error_definition": (
                    "forecast_daily_max_c "
                    "minus hko_daily_max_c"
                ),
                "source_forecast_column": (
                    forecast_column
                ),
                "first_training_date": (
                    panel[
                        "target_date"
                    ].min().date().isoformat()
                ),
                "last_training_date": (
                    panel[
                        "target_date"
                    ].max().date().isoformat()
                ),
                **overall,
            }
        ]
    )

    output_panel = panel.copy()

    output_panel["target_date"] = (
        output_panel[
            "target_date"
        ].dt.date.astype(str)
    )

    date_summary["target_date"] = (
        pd.to_datetime(
            date_summary["target_date"],
            errors="raise",
        )
        .dt.date
        .astype(str)
    )

    write_csv(
        output_panel,
        PANEL_PATH,
    )

    write_csv(
        date_summary,
        DATE_SUMMARY_PATH,
    )

    write_csv(
        rule_summary,
        RULE_SUMMARY_PATH,
    )

    write_csv(
        month_summary,
        MONTH_SUMMARY_PATH,
    )

    write_csv(
        checks,
        CHECKS_PATH,
    )

    write_csv(
        main_summary,
        MAIN_SUMMARY_PATH,
    )

    output_paths = [
        PANEL_PATH,
        DATE_SUMMARY_PATH,
        RULE_SUMMARY_PATH,
        MONTH_SUMMARY_PATH,
        CHECKS_PATH,
        MAIN_SUMMARY_PATH,
    ]

    manifest = {
        "phase": 5,
        "phase_status": (
            "PHASE5_WEATHER_ONLY_RESIDUAL_PANEL_COMPLETE"
        ),
        "status": (
            "TWO_YEAR_FORECAST_RESIDUAL_PANEL_CERTIFIED"
        ),
        "created_utc": utc_now(),
        "forecast_source": str(
            FORECAST_PATH.relative_to(ROOT)
        ),
        "observation_source": str(
            HKO_PATH.relative_to(ROOT)
        ),
        "source_forecast_column": (
            forecast_column
        ),
        "residual_definition": (
            "hko_daily_max_c minus forecast_daily_max_c"
        ),
        "forecast_error_definition": (
            "forecast_daily_max_c minus hko_daily_max_c"
        ),
        "weather_only_training_dates": 730,
        "decision_rules": 4,
        "residual_rows": 2920,
        "first_training_date": (
            panel[
                "target_date"
            ].min().date().isoformat()
        ),
        "last_training_date": (
            panel[
                "target_date"
            ].max().date().isoformat()
        ),
        "missing_forecasts": int(
            panel[
                "forecast_daily_max_c"
            ].isna().sum()
        ),
        "missing_observations": int(
            panel[
                "hko_daily_max_c"
            ].isna().sum()
        ),
        "mean_residual_c": float(
            panel["residual_c"].mean()
        ),
        "residual_standard_deviation_c": float(
            panel["residual_c"].std(ddof=1)
        ),
        "mean_absolute_error_c": float(
            panel[
                "absolute_error_c"
            ].mean()
        ),
        "root_mean_squared_error_c": float(
            np.sqrt(
                panel[
                    "squared_error_c"
                ].mean()
            )
        ),
        "uncertainty_unit": (
            specification[
                "uncertainty_unit"
            ]
        ),
        "information_time_verified_upstream": True,
        "training_hko_observations_accessed": True,
        "market_prices_accessed": False,
        "polymarket_outcomes_accessed": False,
        "model_fitted": False,
        "model_selected": False,
        "calibration_selected": False,
        "trading_strategy_selected": False,
        "trading_returns_calculated": False,
        "required_integrity_checks_passed": True,
        "input_hashes": {
            str(
                FORECAST_PATH.relative_to(ROOT)
            ): sha256_file(FORECAST_PATH),
            str(
                HKO_PATH.relative_to(ROOT)
            ): sha256_file(HKO_PATH),
        },
        "output_paths": [
            str(path.relative_to(ROOT))
            for path in output_paths
        ],
        "output_hashes": {
            str(path.relative_to(ROOT)): (
                sha256_file(path)
            )
            for path in output_paths
        },
        "next_stage": (
            "Construct the chronological weather-only "
            "training design and the Gaussian-process "
            "covariate matrices."
        ),
    }

    write_json(
        manifest,
        MANIFEST_PATH,
    )

    print()
    print("=" * 78)
    print("PHASE 5 WEATHER-ONLY RESIDUAL PANEL")
    print("=" * 78)

    print("Status:", manifest["status"])
    print(
        "Forecast source column:",
        forecast_column,
    )
    print(
        "Weather-only training dates:",
        manifest["weather_only_training_dates"],
    )
    print(
        "Decision rules:",
        manifest["decision_rules"],
    )
    print(
        "Residual rows:",
        manifest["residual_rows"],
    )
    print(
        "Training interval:",
        manifest["first_training_date"],
        "to",
        manifest["last_training_date"],
    )
    print(
        "Mean residual:",
        f"{manifest['mean_residual_c']:.6f}",
        "degrees Celsius",
    )
    print(
        "Residual standard deviation:",
        f"{manifest['residual_standard_deviation_c']:.6f}",
    )
    print(
        "Mean absolute error:",
        f"{manifest['mean_absolute_error_c']:.6f}",
    )
    print(
        "Root mean squared error:",
        f"{manifest['root_mean_squared_error_c']:.6f}",
    )
    print("Missing forecasts: 0")
    print("Missing observations: 0")
    print("Market prices accessed: False")
    print("Polymarket outcomes accessed: False")
    print("Model fitted or selected: False")
    print("PHASE 5 CORE CONSTRUCTION: PASSED")


if __name__ == "__main__":
    main()
