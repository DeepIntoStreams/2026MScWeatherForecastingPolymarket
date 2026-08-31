from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys

from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# =============================================================================
# FROZEN FINAL EMPIRICAL SPLITS
# =============================================================================

START_DATE = pd.Timestamp("2024-03-16")
WEATHER_HISTORY_END = pd.Timestamp("2026-03-15")

MARKET_DEVELOPMENT_START = pd.Timestamp("2026-03-16")
MARKET_DEVELOPMENT_END = pd.Timestamp("2026-06-30")

EXTERNAL_START = pd.Timestamp("2026-07-01")
END_DATE = pd.Timestamp("2026-08-31")

RULE_ORDER = [
    "24h_prior",
    "12h_prior",
    "6h_prior",
    "event_day_open",
]


# =============================================================================
# PATHS
# =============================================================================

FORECAST_CSV = Path(
    "data/processed/final_pipeline/"
    "ecmwf_deterministic_forecasts.csv"
)

HKO_CSV = Path(
    "data/processed/final_pipeline/"
    "hko_daily_max_temperature.csv"
)

HKO_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "hko_summary.json"
)

ECMWF_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "ecmwf_summary.json"
)

PROCESSED_DIR = Path(
    "data/processed/final_pipeline"
)

SAMPLE_DIR = (
    PROCESSED_DIR
    / "residual_samples"
)

OUTPUT_DIR = Path(
    "outputs/final_pipeline/weather"
)

AUDIT_DIR = Path(
    "outputs/final_pipeline/audit"
)

MASTER_PANEL = (
    PROCESSED_DIR
    / "weather_residual_panel.csv"
)

SAMPLE_MANIFEST = (
    PROCESSED_DIR
    / "residual_sample_manifest.csv"
)

TRAIN_SAMPLE = (
    SAMPLE_DIR
    / "weather_history_training.csv"
)

DEVELOPMENT_SAMPLE = (
    SAMPLE_DIR
    / "market_development.csv"
)

EXTERNAL_SAMPLE = (
    SAMPLE_DIR
    / "external_validation.csv"
)

SUPPORT_SUMMARY = (
    OUTPUT_DIR
    / "residual_support_summary.csv"
)

ERROR_SUMMARY = (
    OUTPUT_DIR
    / "deterministic_error_summary.csv"
)

MONTHLY_SUMMARY = (
    OUTPUT_DIR
    / "deterministic_monthly_error_summary.csv"
)

PAIRWISE_SUMMARY = (
    OUTPUT_DIR
    / "deterministic_pairwise_rule_comparison.csv"
)

MAE_FIGURE = (
    OUTPUT_DIR
    / "deterministic_mae_by_period_rule.png"
)

MONTHLY_FIGURE = (
    OUTPUT_DIR
    / "deterministic_monthly_mae_by_rule.png"
)

SUMMARY_JSON = (
    AUDIT_DIR
    / "residual_panel_summary.json"
)

CHECKS_CSV = (
    AUDIT_DIR
    / "residual_panel_integrity_checks.csv"
)


# =============================================================================
# UTILITIES
# =============================================================================


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            block = f.read(
                1024 * 1024
            )

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def to_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series

    mapping = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
    }

    result = (
        series
        .astype(str)
        .str.strip()
        .str.lower()
        .map(mapping)
    )

    if result.isna().any():
        bad = sorted(
            series[
                result.isna()
            ]
            .astype(str)
            .unique()
            .tolist()
        )

        raise RuntimeError(
            "Unable to parse boolean values: "
            f"{bad}"
        )

    return result.astype(bool)


def assign_period(
    targets: pd.Series,
) -> pd.Series:
    conditions = [
        targets <= WEATHER_HISTORY_END,
        (
            (targets >= MARKET_DEVELOPMENT_START)
            & (targets <= MARKET_DEVELOPMENT_END)
        ),
        targets >= EXTERNAL_START,
    ]

    choices = [
        "weather_history",
        "market_development",
        "external_validation",
    ]

    result = np.select(
        conditions,
        choices,
        default="outside_final_period",
    )

    return pd.Series(
        result,
        index=targets.index,
    )


def metric_dict(
    x: pd.DataFrame,
) -> dict:
    if x.empty:
        return {
            "n": 0,
            "unique_dates": 0,
            "mean_forecast_c": np.nan,
            "mean_hko_c": np.nan,
            "mean_residual_c": np.nan,
            "forecast_bias_c": np.nan,
            "mae_c": np.nan,
            "rmse_c": np.nan,
            "median_absolute_error_c": np.nan,
            "residual_sd_c": np.nan,
            "residual_q05_c": np.nan,
            "residual_q25_c": np.nan,
            "residual_q50_c": np.nan,
            "residual_q75_c": np.nan,
            "residual_q95_c": np.nan,
            "max_absolute_error_c": np.nan,
            "forecast_hko_correlation": np.nan,
        }

    residual = x["residual_c"]
    error = x["forecast_error_c"]
    abs_error = x["absolute_error_c"]

    if (
        len(x) >= 2
        and x["forecast_daily_max_c"].nunique() > 1
        and x["hko_daily_max_c"].nunique() > 1
    ):
        correlation = x[
            [
                "forecast_daily_max_c",
                "hko_daily_max_c",
            ]
        ].corr().iloc[0, 1]
    else:
        correlation = np.nan

    return {
        "n":
            int(len(x)),
        "unique_dates":
            int(
                x["target_date"].nunique()
            ),
        "mean_forecast_c":
            float(
                x[
                    "forecast_daily_max_c"
                ].mean()
            ),
        "mean_hko_c":
            float(
                x[
                    "hko_daily_max_c"
                ].mean()
            ),
        "mean_residual_c":
            float(
                residual.mean()
            ),
        "forecast_bias_c":
            float(
                error.mean()
            ),
        "mae_c":
            float(
                abs_error.mean()
            ),
        "rmse_c":
            float(
                np.sqrt(
                    x[
                        "squared_error_c"
                    ].mean()
                )
            ),
        "median_absolute_error_c":
            float(
                abs_error.median()
            ),
        "residual_sd_c":
            float(
                residual.std(
                    ddof=1
                )
            )
            if len(x) > 1
            else np.nan,
        "residual_q05_c":
            float(
                residual.quantile(
                    0.05
                )
            ),
        "residual_q25_c":
            float(
                residual.quantile(
                    0.25
                )
            ),
        "residual_q50_c":
            float(
                residual.quantile(
                    0.50
                )
            ),
        "residual_q75_c":
            float(
                residual.quantile(
                    0.75
                )
            ),
        "residual_q95_c":
            float(
                residual.quantile(
                    0.95
                )
            ),
        "max_absolute_error_c":
            float(
                abs_error.max()
            ),
        "forecast_hko_correlation":
            float(correlation)
            if pd.notna(correlation)
            else np.nan,
    }


def complete_case(
    df: pd.DataFrame,
) -> pd.DataFrame:
    return df[
        df["residual_usable"]
    ].copy()


# =============================================================================
# MASTER PANEL
# =============================================================================


def build_master_panel() -> tuple[
    pd.DataFrame,
    dict,
    dict,
]:
    if not FORECAST_CSV.exists():
        raise RuntimeError(
            f"Missing forecast panel: {FORECAST_CSV}"
        )

    if not HKO_CSV.exists():
        raise RuntimeError(
            f"Missing HKO panel: {HKO_CSV}"
        )

    if not HKO_SUMMARY.exists():
        raise RuntimeError(
            f"Missing HKO summary: {HKO_SUMMARY}"
        )

    if not ECMWF_SUMMARY.exists():
        raise RuntimeError(
            f"Missing ECMWF summary: {ECMWF_SUMMARY}"
        )

    hko_summary = json.loads(
        HKO_SUMMARY.read_text()
    )

    ecmwf_summary = json.loads(
        ECMWF_SUMMARY.read_text()
    )

    forecasts = pd.read_csv(
        FORECAST_CSV
    )

    hko = pd.read_csv(
        HKO_CSV
    )

    forecasts[
        "target_date"
    ] = pd.to_datetime(
        forecasts["target_date"]
    )

    hko[
        "target_date"
    ] = pd.to_datetime(
        hko["target_date"]
    )

    forecasts[
        "support_available"
    ] = to_bool(
        forecasts[
            "support_available"
        ]
    )

    forecasts[
        "forecast_daily_max_c"
    ] = pd.to_numeric(
        forecasts[
            "forecast_daily_max_c"
        ],
        errors="coerce",
    )

    hko[
        "hko_daily_max_c"
    ] = pd.to_numeric(
        hko[
            "hko_daily_max_c"
        ],
        errors="raise",
    )

    if (
        hko["target_date"]
        .duplicated()
        .any()
    ):
        dup = (
            hko.loc[
                hko[
                    "target_date"
                ].duplicated(
                    keep=False
                ),
                "target_date",
            ]
            .dt.strftime(
                "%Y-%m-%d"
            )
            .tolist()
        )

        raise RuntimeError(
            "Duplicate HKO dates: "
            f"{dup[:20]}"
        )

    panel = forecasts.merge(
        hko[
            [
                "target_date",
                "hko_daily_max_c",
                "source_system",
                "source_period",
            ]
        ].rename(
            columns={
                "source_system":
                    "hko_source_system",
                "source_period":
                    "hko_source_period",
            }
        ),
        on="target_date",
        how="left",
        validate="many_to_one",
    )

    panel[
        "hko_available"
    ] = panel[
        "hko_daily_max_c"
    ].notna()

    panel[
        "residual_usable"
    ] = (
        panel[
            "support_available"
        ]
        & panel[
            "hko_available"
        ]
        & panel[
            "forecast_daily_max_c"
        ].notna()
    )

    panel[
        "residual_c"
    ] = np.where(
        panel[
            "residual_usable"
        ],
        (
            panel[
                "hko_daily_max_c"
            ]
            - panel[
                "forecast_daily_max_c"
            ]
        ),
        np.nan,
    )

    panel[
        "forecast_error_c"
    ] = np.where(
        panel[
            "residual_usable"
        ],
        -panel[
            "residual_c"
        ],
        np.nan,
    )

    panel[
        "absolute_error_c"
    ] = np.where(
        panel[
            "residual_usable"
        ],
        np.abs(
            panel[
                "forecast_error_c"
            ]
        ),
        np.nan,
    )

    panel[
        "squared_error_c"
    ] = np.where(
        panel[
            "residual_usable"
        ],
        (
            panel[
                "forecast_error_c"
            ]
            ** 2
        ),
        np.nan,
    )

    panel[
        "empirical_period"
    ] = assign_period(
        panel[
            "target_date"
        ]
    )

    panel[
        "weather_history_training"
    ] = (
        panel[
            "empirical_period"
        ]
        == "weather_history"
    )

    panel[
        "market_development_period"
    ] = (
        panel[
            "empirical_period"
        ]
        == "market_development"
    )

    panel[
        "external_validation_period"
    ] = (
        panel[
            "empirical_period"
        ]
        == "external_validation"
    )

    # -------------------------------------------------------------
    # Calendar/seasonal variables required by later post-processing.
    #
    # Within each forecast-time GP the eventual four raw covariates
    # will be:
    #
    #   forecast_daily_max_c
    #   seasonal_sin
    #   seasonal_cos
    #   calendar_day_index
    #
    # Standardisation occurs later inside the training fold only.
    # -------------------------------------------------------------

    panel[
        "target_year"
    ] = panel[
        "target_date"
    ].dt.year

    panel[
        "target_month"
    ] = panel[
        "target_date"
    ].dt.month

    panel[
        "target_day"
    ] = panel[
        "target_date"
    ].dt.day

    panel[
        "day_of_year"
    ] = panel[
        "target_date"
    ].dt.dayofyear

    panel[
        "seasonal_sin"
    ] = np.sin(
        2.0
        * np.pi
        * (
            panel[
                "day_of_year"
            ]
            - 1
        )
        / 365.25
    )

    panel[
        "seasonal_cos"
    ] = np.cos(
        2.0
        * np.pi
        * (
            panel[
                "day_of_year"
            ]
            - 1
        )
        / 365.25
    )

    panel[
        "calendar_day_index"
    ] = (
        panel[
            "target_date"
        ]
        - START_DATE
    ).dt.days

    panel[
        "sample_status"
    ] = np.select(
        [
            ~panel[
                "hko_available"
            ],
            ~panel[
                "support_available"
            ],
            panel[
                "residual_usable"
            ],
        ],
        [
            "target_pending",
            "forecast_unsupported",
            "usable",
        ],
        default=
            "invalid_unclassified",
    )

    order_map = {
        rule: i
        for i, rule
        in enumerate(
            RULE_ORDER,
            start=1,
        )
    }

    panel[
        "_rule_sort"
    ] = panel[
        "decision_rule"
    ].map(
        order_map
    )

    if (
        panel[
            "_rule_sort"
        ].isna().any()
    ):
        raise RuntimeError(
            "Unexpected decision rule encountered."
        )

    panel = panel.sort_values(
        [
            "target_date",
            "_rule_sort",
        ]
    ).drop(
        columns=[
            "_rule_sort"
        ]
    )

    return (
        panel,
        hko_summary,
        ecmwf_summary,
    )


# =============================================================================
# SUPPORT / SAMPLE FREEZE
# =============================================================================


def build_support_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for period in [
        "weather_history",
        "market_development",
        "external_validation",
    ]:
        for rule in RULE_ORDER:
            x = panel[
                (
                    panel[
                        "empirical_period"
                    ]
                    == period
                )
                & (
                    panel[
                        "decision_rule"
                    ]
                    == rule
                )
            ]

            rows.append(
                {
                    "empirical_period":
                        period,
                    "decision_rule":
                        rule,
                    "theoretical_keys":
                        int(len(x)),
                    "forecast_supported_keys":
                        int(
                            x[
                                "support_available"
                            ].sum()
                        ),
                    "forecast_unsupported_keys":
                        int(
                            (
                                ~x[
                                    "support_available"
                                ]
                            ).sum()
                        ),
                    "hko_available_keys":
                        int(
                            x[
                                "hko_available"
                            ].sum()
                        ),
                    "target_pending_keys":
                        int(
                            (
                                ~x[
                                    "hko_available"
                                ]
                            ).sum()
                        ),
                    "residual_usable_keys":
                        int(
                            x[
                                "residual_usable"
                            ].sum()
                        ),
                    "usable_unique_dates":
                        int(
                            x.loc[
                                x[
                                    "residual_usable"
                                ],
                                "target_date",
                            ].nunique()
                        ),
                }
            )

    return pd.DataFrame(rows)


def write_samples(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    SAMPLE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    definitions = [
        (
            "weather_history_training",
            "weather_history",
            TRAIN_SAMPLE,
        ),
        (
            "market_development",
            "market_development",
            DEVELOPMENT_SAMPLE,
        ),
        (
            "external_validation",
            "external_validation",
            EXTERNAL_SAMPLE,
        ),
    ]

    manifest = []

    for (
        sample_name,
        period,
        path,
    ) in definitions:

        x = panel[
            (
                panel[
                    "empirical_period"
                ]
                == period
            )
            & panel[
                "residual_usable"
            ]
        ].copy()

        x.to_csv(
            path,
            index=False,
            float_format="%.10f",
        )

        manifest.append(
            {
                "sample_name":
                    sample_name,
                "empirical_period":
                    period,
                "start_date":
                    (
                        x[
                            "target_date"
                        ].min()
                        .strftime(
                            "%Y-%m-%d"
                        )
                        if len(x)
                        else ""
                    ),
                "end_date":
                    (
                        x[
                            "target_date"
                        ].max()
                        .strftime(
                            "%Y-%m-%d"
                        )
                        if len(x)
                        else ""
                    ),
                "rows":
                    int(len(x)),
                "unique_dates":
                    int(
                        x[
                            "target_date"
                        ].nunique()
                    ),
                "decision_rules":
                    "|".join(
                        sorted(
                            x[
                                "decision_rule"
                            ].unique(),
                            key=lambda z:
                                RULE_ORDER.index(z),
                        )
                    )
                    if len(x)
                    else "",
                "path":
                    str(path),
                "sha256":
                    sha256_file(path),
            }
        )

    result = pd.DataFrame(
        manifest
    )

    result.to_csv(
        SAMPLE_MANIFEST,
        index=False,
    )

    return result


# =============================================================================
# RAW DETERMINISTIC ERROR DIAGNOSTICS
# =============================================================================


def build_error_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:

    period_filters = {
        "weather_history":
            panel[
                "empirical_period"
            ]
            == "weather_history",

        "market_development":
            panel[
                "empirical_period"
            ]
            == "market_development",

        "external_validation":
            panel[
                "empirical_period"
            ]
            == "external_validation",

        "market_mar_aug":
            panel[
                "target_date"
            ]
            >= MARKET_DEVELOPMENT_START,

        "full_available_period":
            pd.Series(
                True,
                index=panel.index,
            ),
    }

    rows = []

    for period_name, filt in (
        period_filters.items()
    ):
        for rule in RULE_ORDER:
            x = panel[
                filt
                & (
                    panel[
                        "decision_rule"
                    ]
                    == rule
                )
                & panel[
                    "residual_usable"
                ]
            ]

            row = {
                "analysis_period":
                    period_name,
                "decision_rule":
                    rule,
            }

            row.update(
                metric_dict(x)
            )

            rows.append(row)

    return pd.DataFrame(rows)


def build_monthly_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:

    x = complete_case(
        panel
    ).copy()

    x[
        "target_month_id"
    ] = x[
        "target_date"
    ].dt.to_period(
        "M"
    ).astype(str)

    rows = []

    for (
        month_id,
        rule,
    ), group in x.groupby(
        [
            "target_month_id",
            "decision_rule",
        ],
        sort=True,
    ):
        row = {
            "target_month":
                month_id,
            "decision_rule":
                rule,
        }

        row.update(
            metric_dict(group)
        )

        rows.append(row)

    result = pd.DataFrame(rows)

    result[
        "_rule_sort"
    ] = result[
        "decision_rule"
    ].map(
        {
            rule: i
            for i, rule
            in enumerate(
                RULE_ORDER,
                start=1,
            )
        }
    )

    result = result.sort_values(
        [
            "target_month",
            "_rule_sort",
        ]
    ).drop(
        columns=[
            "_rule_sort"
        ]
    )

    return result


def build_pairwise_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:

    period_filters = {
        "weather_history":
            panel[
                "empirical_period"
            ]
            == "weather_history",

        "market_development":
            panel[
                "empirical_period"
            ]
            == "market_development",

        "external_validation":
            panel[
                "empirical_period"
            ]
            == "external_validation",

        "market_mar_aug":
            panel[
                "target_date"
            ]
            >= MARKET_DEVELOPMENT_START,
    }

    rows = []

    for period, filt in (
        period_filters.items()
    ):

        x = panel[
            filt
            & panel[
                "residual_usable"
            ]
        ].copy()

        pivot_abs = x.pivot(
            index="target_date",
            columns="decision_rule",
            values="absolute_error_c",
        )

        pivot_sq = x.pivot(
            index="target_date",
            columns="decision_rule",
            values="squared_error_c",
        )

        for rule_a, rule_b in combinations(
            RULE_ORDER,
            2,
        ):
            common = (
                pivot_abs[
                    [
                        rule_a,
                        rule_b,
                    ]
                ]
                .dropna()
            )

            common_sq = (
                pivot_sq[
                    [
                        rule_a,
                        rule_b,
                    ]
                ]
                .dropna()
                .loc[
                    common.index
                ]
            )

            if common.empty:
                rows.append(
                    {
                        "analysis_period":
                            period,
                        "rule_a":
                            rule_a,
                        "rule_b":
                            rule_b,
                        "common_dates":
                            0,
                        "mae_a_c":
                            np.nan,
                        "mae_b_c":
                            np.nan,
                        "mae_a_minus_b_c":
                            np.nan,
                        "rmse_a_c":
                            np.nan,
                        "rmse_b_c":
                            np.nan,
                        "rmse_a_minus_b_c":
                            np.nan,
                    }
                )

                continue

            mae_a = float(
                common[
                    rule_a
                ].mean()
            )

            mae_b = float(
                common[
                    rule_b
                ].mean()
            )

            rmse_a = float(
                np.sqrt(
                    common_sq[
                        rule_a
                    ].mean()
                )
            )

            rmse_b = float(
                np.sqrt(
                    common_sq[
                        rule_b
                    ].mean()
                )
            )

            rows.append(
                {
                    "analysis_period":
                        period,
                    "rule_a":
                        rule_a,
                    "rule_b":
                        rule_b,
                    "common_dates":
                        int(
                            len(common)
                        ),
                    "mae_a_c":
                        mae_a,
                    "mae_b_c":
                        mae_b,
                    "mae_a_minus_b_c":
                        mae_a
                        - mae_b,
                    "rmse_a_c":
                        rmse_a,
                    "rmse_b_c":
                        rmse_b,
                    "rmse_a_minus_b_c":
                        rmse_a
                        - rmse_b,
                }
            )

    return pd.DataFrame(rows)


# =============================================================================
# DIAGNOSTIC FIGURES
# =============================================================================


def make_mae_figure(
    error_summary: pd.DataFrame,
):
    periods = [
        "weather_history",
        "market_development",
        "external_validation",
    ]

    fig, ax = plt.subplots(
        figsize=(10, 6)
    )

    width = 0.18

    x = np.arange(
        len(periods)
    )

    for i, rule in enumerate(
        RULE_ORDER
    ):
        values = []

        for period in periods:
            row = error_summary[
                (
                    error_summary[
                        "analysis_period"
                    ]
                    == period
                )
                & (
                    error_summary[
                        "decision_rule"
                    ]
                    == rule
                )
            ]

            values.append(
                (
                    float(
                        row[
                            "mae_c"
                        ].iloc[0]
                    )
                    if len(row)
                    else np.nan
                )
            )

        ax.bar(
            x
            + (
                i
                - 1.5
            )
            * width,
            values,
            width=width,
            label=rule,
        )

    ax.set_xticks(x)

    ax.set_xticklabels(
        [
            "Weather history",
            "Mar–Jun development",
            "Jul–Aug external",
        ]
    )

    ax.set_ylabel(
        "MAE (°C)"
    )

    ax.set_title(
        "Deterministic ECMWF error by empirical period and forecast time"
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        MAE_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)


def make_monthly_figure(
    monthly: pd.DataFrame,
):
    fig, ax = plt.subplots(
        figsize=(12, 6)
    )

    for rule in RULE_ORDER:
        x = monthly[
            monthly[
                "decision_rule"
            ]
            == rule
        ].copy()

        if x.empty:
            continue

        dates = pd.to_datetime(
            x[
                "target_month"
            ]
            + "-01"
        )

        ax.plot(
            dates,
            x["mae_c"],
            marker="o",
            markersize=3,
            linewidth=1.2,
            label=rule,
        )

    ax.axvline(
        pd.Timestamp(
            "2026-03-16"
        ),
        linestyle="--",
        linewidth=1,
    )

    ax.axvline(
        pd.Timestamp(
            "2026-07-01"
        ),
        linestyle="--",
        linewidth=1,
    )

    ax.set_ylabel(
        "Monthly MAE (°C)"
    )

    ax.set_title(
        "Monthly deterministic ECMWF forecast error"
    )

    ax.legend()

    fig.autofmt_xdate()

    fig.tight_layout()

    fig.savefig(
        MONTHLY_FIGURE,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)


# =============================================================================
# INTEGRITY AUDIT
# =============================================================================


def build_checks(
    panel: pd.DataFrame,
    hko_summary: dict,
    ecmwf_summary: dict,
    samples: pd.DataFrame,
    error_summary: pd.DataFrame,
) -> tuple[
    list[dict],
    str,
]:

    keys = list(
        zip(
            panel[
                "target_date"
            ].dt.strftime(
                "%Y-%m-%d"
            ),
            panel[
                "decision_rule"
            ],
        )
    )

    weather = panel[
        panel[
            "empirical_period"
        ]
        == "weather_history"
    ]

    development = panel[
        panel[
            "empirical_period"
        ]
        == "market_development"
    ]

    external = panel[
        panel[
            "empirical_period"
        ]
        == "external_validation"
    ]

    usable = panel[
        panel[
            "residual_usable"
        ]
    ]

    residual_formula_error = (
        np.abs(
            usable[
                "residual_c"
            ]
            - (
                usable[
                    "hko_daily_max_c"
                ]
                - usable[
                    "forecast_daily_max_c"
                ]
            )
        ).max()
        if len(usable)
        else 0.0
    )

    error_formula_error = (
        np.abs(
            usable[
                "forecast_error_c"
            ]
            + usable[
                "residual_c"
            ]
        ).max()
        if len(usable)
        else 0.0
    )

    invalid_missing_residual = panel[
        (
            ~panel[
                "residual_usable"
            ]
        )
        & (
            panel[
                [
                    "residual_c",
                    "forecast_error_c",
                    "absolute_error_c",
                    "squared_error_c",
                ]
            ]
            .notna()
            .any(
                axis=1
            )
        )
    ]

    invalid_usable_residual = panel[
        panel[
            "residual_usable"
        ]
        & (
            panel[
                [
                    "residual_c",
                    "forecast_error_c",
                    "absolute_error_c",
                    "squared_error_c",
                ]
            ]
            .isna()
            .any(
                axis=1
            )
        )
    ]

    hko_status = (
        hko_summary.get(
            "status"
        )
    )

    pending_final_date = (
        hko_status
        == "PENDING_FINAL_DATE"
    )

    hko_missing_dates = (
        hko_summary.get(
            "missing_dates",
            [],
        )
    )

    if pending_final_date:
        hko_state_pass = (
            hko_missing_dates
            == [
                "2026-08-31"
            ]
        )
    else:
        hko_state_pass = (
            hko_status
            == "COMPLETE"
            and hko_missing_dates
            == []
        )

    # Current frozen ECMWF support counts.
    expected_weather_usable = 2726
    expected_development_usable = 424

    expected_external_usable = (
        244
        if pending_final_date
        else 248
    )

    expected_total_usable = (
        expected_weather_usable
        + expected_development_usable
        + expected_external_usable
    )

    sample_lookup = {
        row[
            "sample_name"
        ]: int(row["rows"])
        for _, row
        in samples.iterrows()
    }

    checks = [
        {
            "check":
                "master_date_rule_keys",
            "passed":
                len(panel)
                == 3596,
            "observed":
                int(len(panel)),
            "expected":
                3596,
            "notes":
                "899 dates x 4 forecast times",
        },
        {
            "check":
                "no_duplicate_date_rule_keys",
            "passed":
                len(keys)
                == len(set(keys)),
            "observed":
                int(
                    len(keys)
                    - len(set(keys))
                ),
            "expected":
                0,
            "notes":
                "",
        },
        {
            "check":
                "weather_history_theoretical_keys",
            "passed":
                len(weather)
                == 2920,
            "observed":
                int(len(weather)),
            "expected":
                2920,
            "notes":
                "730 dates x 4",
        },
        {
            "check":
                "market_development_theoretical_keys",
            "passed":
                len(development)
                == 428,
            "observed":
                int(
                    len(development)
                ),
            "expected":
                428,
            "notes":
                "16 Mar to 30 Jun 2026",
        },
        {
            "check":
                "external_validation_theoretical_keys",
            "passed":
                len(external)
                == 248,
            "observed":
                int(len(external)),
            "expected":
                248,
            "notes":
                "1 Jul to 31 Aug 2026",
        },
        {
            "check":
                "ecmwf_supported_key_count",
            "passed":
                int(
                    panel[
                        "support_available"
                    ].sum()
                )
                == 3398,
            "observed":
                int(
                    panel[
                        "support_available"
                    ].sum()
                ),
            "expected":
                3398,
            "notes":
                "",
        },
        {
            "check":
                "hko_current_state_valid",
            "passed":
                hko_state_pass,
            "observed":
                json.dumps(
                    hko_missing_dates
                ),
            "expected":
                (
                    '["2026-08-31"]'
                    if pending_final_date
                    else "[]"
                ),
            "notes":
                hko_status,
        },
        {
            "check":
                "weather_history_usable_keys",
            "passed":
                int(
                    weather[
                        "residual_usable"
                    ].sum()
                )
                == expected_weather_usable,
            "observed":
                int(
                    weather[
                        "residual_usable"
                    ].sum()
                ),
            "expected":
                expected_weather_usable,
            "notes":
                "",
        },
        {
            "check":
                "market_development_usable_keys",
            "passed":
                int(
                    development[
                        "residual_usable"
                    ].sum()
                )
                == expected_development_usable,
            "observed":
                int(
                    development[
                        "residual_usable"
                    ].sum()
                ),
            "expected":
                expected_development_usable,
            "notes":
                "",
        },
        {
            "check":
                "external_validation_usable_keys",
            "passed":
                int(
                    external[
                        "residual_usable"
                    ].sum()
                )
                == expected_external_usable,
            "observed":
                int(
                    external[
                        "residual_usable"
                    ].sum()
                ),
            "expected":
                expected_external_usable,
            "notes":
                (
                    "31 Aug target pending"
                    if pending_final_date
                    else "complete Jul-Aug"
                ),
        },
        {
            "check":
                "total_residual_usable_keys",
            "passed":
                int(
                    panel[
                        "residual_usable"
                    ].sum()
                )
                == expected_total_usable,
            "observed":
                int(
                    panel[
                        "residual_usable"
                    ].sum()
                ),
            "expected":
                expected_total_usable,
            "notes":
                "",
        },
        {
            "check":
                "residual_formula",
            "passed":
                float(
                    residual_formula_error
                )
                < 1e-10,
            "observed":
                float(
                    residual_formula_error
                ),
            "expected":
                0,
            "notes":
                "residual = HKO - forecast",
        },
        {
            "check":
                "forecast_error_formula",
            "passed":
                float(
                    error_formula_error
                )
                < 1e-10,
            "observed":
                float(
                    error_formula_error
                ),
            "expected":
                0,
            "notes":
                "forecast_error = forecast - HKO",
        },
        {
            "check":
                "unusable_rows_have_no_residual",
            "passed":
                len(
                    invalid_missing_residual
                )
                == 0,
            "observed":
                int(
                    len(
                        invalid_missing_residual
                    )
                ),
            "expected":
                0,
            "notes":
                "",
        },
        {
            "check":
                "usable_rows_have_complete_residual_fields",
            "passed":
                len(
                    invalid_usable_residual
                )
                == 0,
            "observed":
                int(
                    len(
                        invalid_usable_residual
                    )
                ),
            "expected":
                0,
            "notes":
                "",
        },
        {
            "check":
                "training_sample_manifest_count",
            "passed":
                sample_lookup.get(
                    "weather_history_training"
                )
                == expected_weather_usable,
            "observed":
                sample_lookup.get(
                    "weather_history_training"
                ),
            "expected":
                expected_weather_usable,
            "notes":
                "",
        },
        {
            "check":
                "development_sample_manifest_count",
            "passed":
                sample_lookup.get(
                    "market_development"
                )
                == expected_development_usable,
            "observed":
                sample_lookup.get(
                    "market_development"
                ),
            "expected":
                expected_development_usable,
            "notes":
                "",
        },
        {
            "check":
                "external_sample_manifest_count",
            "passed":
                sample_lookup.get(
                    "external_validation"
                )
                == expected_external_usable,
            "observed":
                sample_lookup.get(
                    "external_validation"
                ),
            "expected":
                expected_external_usable,
            "notes":
                "",
        },
        {
            "check":
                "no_external_rows_in_training_sample",
            "passed":
                not (
                    panel[
                        "weather_history_training"
                    ]
                    & panel[
                        "external_validation_period"
                    ]
                ).any(),
            "observed":
                int(
                    (
                        panel[
                            "weather_history_training"
                        ]
                        & panel[
                            "external_validation_period"
                        ]
                    ).sum()
                ),
            "expected":
                0,
            "notes":
                "split leakage check",
        },
        {
            "check":
                "seasonal_features_finite",
            "passed":
                np.isfinite(
                    panel[
                        [
                            "seasonal_sin",
                            "seasonal_cos",
                            "calendar_day_index",
                        ]
                    ].to_numpy()
                ).all(),
            "observed":
                int(
                    np.isfinite(
                        panel[
                            [
                                "seasonal_sin",
                                "seasonal_cos",
                                "calendar_day_index",
                            ]
                        ].to_numpy()
                    ).all()
                ),
            "expected":
                1,
            "notes":
                "",
        },
        {
            "check":
                "deterministic_error_summary_complete",
            "passed":
                len(
                    error_summary
                )
                == 20,
            "observed":
                int(
                    len(
                        error_summary
                    )
                ),
            "expected":
                20,
            "notes":
                "5 periods x 4 forecast times",
        },
    ]

    status = (
        "PASS_PENDING_HKO_FINAL_DATE"
        if (
            all(
                row[
                    "passed"
                ]
                for row in checks
            )
            and pending_final_date
        )
        else (
            "PASS"
            if all(
                row[
                    "passed"
                ]
                for row in checks
            )
            else "FAILED"
        )
    )

    return checks, status


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.parse_args()

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SAMPLE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        panel,
        hko_summary,
        ecmwf_summary,
    ) = build_master_panel()

    panel.to_csv(
        MASTER_PANEL,
        index=False,
        float_format="%.10f",
        date_format="%Y-%m-%d",
    )

    support = (
        build_support_summary(
            panel
        )
    )

    support.to_csv(
        SUPPORT_SUMMARY,
        index=False,
    )

    samples = (
        write_samples(
            panel
        )
    )

    errors = (
        build_error_summary(
            panel
        )
    )

    errors.to_csv(
        ERROR_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    monthly = (
        build_monthly_summary(
            panel
        )
    )

    monthly.to_csv(
        MONTHLY_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    pairwise = (
        build_pairwise_summary(
            panel
        )
    )

    pairwise.to_csv(
        PAIRWISE_SUMMARY,
        index=False,
        float_format="%.10f",
    )

    make_mae_figure(
        errors
    )

    make_monthly_figure(
        monthly
    )

    (
        checks,
        status,
    ) = build_checks(
        panel,
        hko_summary,
        ecmwf_summary,
        samples,
        errors,
    )

    pd.DataFrame(
        checks
    ).to_csv(
        CHECKS_CSV,
        index=False,
    )

    period_counts = {}

    for period in [
        "weather_history",
        "market_development",
        "external_validation",
    ]:
        x = panel[
            panel[
                "empirical_period"
            ]
            == period
        ]

        period_counts[
            period
        ] = {
            "theoretical_keys":
                int(len(x)),
            "forecast_supported_keys":
                int(
                    x[
                        "support_available"
                    ].sum()
                ),
            "residual_usable_keys":
                int(
                    x[
                        "residual_usable"
                    ].sum()
                ),
            "usable_dates":
                int(
                    x.loc[
                        x[
                            "residual_usable"
                        ],
                        "target_date",
                    ].nunique()
                ),
        }

    rule_counts = {}

    for rule in RULE_ORDER:
        x = panel[
            panel[
                "decision_rule"
            ]
            == rule
        ]

        rule_counts[
            rule
        ] = {
            "theoretical_keys":
                int(len(x)),
            "forecast_supported_keys":
                int(
                    x[
                        "support_available"
                    ].sum()
                ),
            "residual_usable_keys":
                int(
                    x[
                        "residual_usable"
                    ].sum()
                ),
        }

    summary = {
        "status":
            status,
        "residual_definition":
            "hko_daily_max_c - forecast_daily_max_c",
        "forecast_error_definition":
            "forecast_daily_max_c - hko_daily_max_c",
        "period_start":
            START_DATE.strftime(
                "%Y-%m-%d"
            ),
        "period_end":
            END_DATE.strftime(
                "%Y-%m-%d"
            ),
        "theoretical_date_rule_keys":
            int(len(panel)),
        "forecast_supported_keys":
            int(
                panel[
                    "support_available"
                ].sum()
            ),
        "hko_available_keys":
            int(
                panel[
                    "hko_available"
                ].sum()
            ),
        "residual_usable_keys":
            int(
                panel[
                    "residual_usable"
                ].sum()
            ),
        "forecast_unsupported_keys":
            int(
                (
                    ~panel[
                        "support_available"
                    ]
                ).sum()
            ),
        "target_pending_keys":
            int(
                (
                    ~panel[
                        "hko_available"
                    ]
                ).sum()
            ),
        "target_pending_dates":
            sorted(
                panel.loc[
                    ~panel[
                        "hko_available"
                    ],
                    "target_date",
                ]
                .drop_duplicates()
                .dt.strftime(
                    "%Y-%m-%d"
                )
                .tolist()
            ),
        "hko_status":
            hko_summary.get(
                "status"
            ),
        "ecmwf_status":
            ecmwf_summary.get(
                "status"
            ),
        "period_counts":
            period_counts,
        "rule_counts":
            rule_counts,
        "gp_raw_feature_columns": [
            "forecast_daily_max_c",
            "seasonal_sin",
            "seasonal_cos",
            "calendar_day_index",
        ],
        "gp_response_column":
            "residual_c",
        "master_panel":
            str(
                MASTER_PANEL
            ),
        "master_panel_sha256":
            sha256_file(
                MASTER_PANEL
            ),
        "sample_manifest":
            str(
                SAMPLE_MANIFEST
            ),
        "error_summary":
            str(
                ERROR_SUMMARY
            ),
        "monthly_error_summary":
            str(
                MONTHLY_SUMMARY
            ),
        "pairwise_rule_comparison":
            str(
                PAIRWISE_SUMMARY
            ),
        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "status="
        + status
    )

    print(
        "theoretical_keys="
        + str(
            len(panel)
        )
    )

    print(
        "forecast_supported="
        + str(
            panel[
                "support_available"
            ].sum()
        )
    )

    print(
        "residual_usable="
        + str(
            panel[
                "residual_usable"
            ].sum()
        )
    )

    for period in [
        "weather_history",
        "market_development",
        "external_validation",
    ]:
        x = panel[
            panel[
                "empirical_period"
            ]
            == period
        ]

        print(
            period
            + "_usable="
            + str(
                x[
                    "residual_usable"
                ].sum()
            )
        )

    if status == "FAILED":
        failed = [
            row
            for row in checks
            if not row["passed"]
        ]

        print(
            "failed_checks="
            + json.dumps(
                failed,
                default=str,
            )
        )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
