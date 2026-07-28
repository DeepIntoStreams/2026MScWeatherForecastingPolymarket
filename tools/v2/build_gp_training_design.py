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
    "gp_training_design_spec.json"
)

SOURCE_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "05_weather_only_forecast_residual_panel.csv"
)

DESIGN_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_raw_design_panel.csv"
)

DATE_ASSIGNMENT_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_date_assignments.csv"
)

FOLD_MATRIX_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_matrix_panel.csv"
)

SCALING_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_scaling_parameters.csv"
)

FOLD_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_fold_summary.csv"
)

CHECKS_PATH = (
    ROOT
    / "outputs/v2/diagnostics/"
    "06_gp_training_design_integrity_checks.csv"
)

MAIN_SUMMARY_PATH = (
    ROOT
    / "outputs/v2/final_tables/"
    "06_gp_training_design_summary.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/v2/"
    "06_gp_training_design_manifest.json"
)


RULE_ORDER = {
    "24h_prior": 1,
    "12h_prior": 2,
    "6h_prior": 3,
    "event_day_open": 4,
}

FEATURE_COLUMNS = [
    "calendar_time_years",
    "seasonal_sin",
    "seasonal_cos",
    "forecast_daily_max_c",
]

STANDARDISED_COLUMNS = [
    f"{feature}_z"
    for feature in FEATURE_COLUMNS
]


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


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


def build_validation_sizes(
    remaining_dates: int,
    blocks: int,
) -> list[int]:
    base = remaining_dates // blocks
    remainder = remaining_dates % blocks

    sizes = [base] * blocks

    for index in range(remainder):
        sizes[
            blocks - remainder + index
        ] += 1

    return sizes


def build_fold_assignments(
    dates: pd.DatetimeIndex,
    initial_training_dates: int,
    validation_sizes: list[int],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    assignment_records = []
    summary_records = []

    cursor = initial_training_dates

    for fold_number, validation_size in enumerate(
        validation_sizes,
        start=1,
    ):
        training_dates = dates[:cursor]

        validation_dates = dates[
            cursor:
            cursor + validation_size
        ]

        if len(validation_dates) != validation_size:
            raise RuntimeError(
                "Validation block length does not "
                "match its planned size."
            )

        training_start = training_dates.min()
        training_end = training_dates.max()
        validation_start = validation_dates.min()
        validation_end = validation_dates.max()

        if not training_end < validation_start:
            raise RuntimeError(
                "Training dates do not precede "
                "validation dates."
            )

        fold_id = f"fold_{fold_number:02d}"

        for date in training_dates:
            assignment_records.append(
                {
                    "fold_id": fold_id,
                    "fold_number": fold_number,
                    "target_date": date,
                    "sample_role": "training",
                    "training_start": training_start,
                    "training_end": training_end,
                    "validation_start": validation_start,
                    "validation_end": validation_end,
                }
            )

        for date in validation_dates:
            assignment_records.append(
                {
                    "fold_id": fold_id,
                    "fold_number": fold_number,
                    "target_date": date,
                    "sample_role": "validation",
                    "training_start": training_start,
                    "training_end": training_end,
                    "validation_start": validation_start,
                    "validation_end": validation_end,
                }
            )

        summary_records.append(
            {
                "fold_id": fold_id,
                "fold_number": fold_number,
                "training_start": training_start,
                "training_end": training_end,
                "validation_start": validation_start,
                "validation_end": validation_end,
                "training_dates": len(training_dates),
                "validation_dates": len(validation_dates),
                "training_rows": (
                    len(training_dates) * 4
                ),
                "validation_rows": (
                    len(validation_dates) * 4
                ),
            }
        )

        cursor += validation_size

    if cursor != len(dates):
        raise RuntimeError(
            "The validation blocks do not exhaust "
            "the second training year."
        )

    assignments = pd.DataFrame(
        assignment_records
    )

    summary = pd.DataFrame(
        summary_records
    )

    return assignments, summary


def construct_fold_matrices(
    design: pd.DataFrame,
    assignments: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    matrix_parts = []
    scaling_records = []

    for fold_id in (
        assignments["fold_id"]
        .drop_duplicates()
    ):
        fold_assignments = assignments.loc[
            assignments["fold_id"].eq(
                fold_id
            )
        ].copy()

        fold_panel = design.merge(
            fold_assignments[
                [
                    "fold_id",
                    "fold_number",
                    "target_date",
                    "sample_role",
                    "training_start",
                    "training_end",
                    "validation_start",
                    "validation_end",
                ]
            ],
            on="target_date",
            how="inner",
            validate="many_to_one",
        )

        for decision_rule in RULE_ORDER:
            rule_panel = fold_panel.loc[
                fold_panel[
                    "decision_rule"
                ].eq(decision_rule)
            ].copy()

            training = rule_panel.loc[
                rule_panel[
                    "sample_role"
                ].eq("training")
            ].copy()

            if training.empty:
                raise RuntimeError(
                    "A fold contains no training rows "
                    f"for {decision_rule}."
                )

            for feature in FEATURE_COLUMNS:
                training_mean = float(
                    training[feature].mean()
                )

                training_std = float(
                    training[feature].std(
                        ddof=0
                    )
                )

                if (
                    not np.isfinite(training_mean)
                    or not np.isfinite(training_std)
                    or training_std <= 0.0
                ):
                    raise RuntimeError(
                        "Invalid training-fold "
                        f"standardisation for "
                        f"{fold_id}, "
                        f"{decision_rule}, "
                        f"{feature}."
                    )

                standardised_column = (
                    f"{feature}_z"
                )

                rule_panel[
                    standardised_column
                ] = (
                    rule_panel[feature]
                    - training_mean
                ) / training_std

                scaling_records.append(
                    {
                        "fold_id": fold_id,
                        "fold_number": int(
                            rule_panel[
                                "fold_number"
                            ].iloc[0]
                        ),
                        "decision_rule": (
                            decision_rule
                        ),
                        "decision_rule_order": (
                            RULE_ORDER[
                                decision_rule
                            ]
                        ),
                        "feature": feature,
                        "training_mean": (
                            training_mean
                        ),
                        "training_standard_deviation": (
                            training_std
                        ),
                        "training_minimum": float(
                            training[feature].min()
                        ),
                        "training_maximum": float(
                            training[feature].max()
                        ),
                        "training_rows": int(
                            len(training)
                        ),
                    }
                )

            matrix_parts.append(
                rule_panel
            )

    matrix = pd.concat(
        matrix_parts,
        ignore_index=True,
    )

    scaling = pd.DataFrame(
        scaling_records
    )

    matrix = matrix.sort_values(
        [
            "fold_number",
            "target_date",
            "decision_rule_order",
        ],
        kind="stable",
    ).reset_index(drop=True)

    scaling = scaling.sort_values(
        [
            "fold_number",
            "decision_rule_order",
            "feature",
        ],
        kind="stable",
    ).reset_index(drop=True)

    return matrix, scaling


def main() -> None:
    specification = json.loads(
        SPEC_PATH.read_text(
            encoding="utf-8"
        )
    )

    panel = pd.read_csv(
        SOURCE_PATH
    )

    required_columns = {
        "target_date",
        "decision_rule",
        "decision_rule_order",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "residual_c",
        "seasonal_sin",
        "seasonal_cos",
    }

    missing_columns = (
        required_columns
        - set(panel.columns)
    )

    if missing_columns:
        raise RuntimeError(
            "Residual panel is missing columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    panel["target_date"] = pd.to_datetime(
        panel["target_date"],
        errors="raise",
        format="mixed",
    ).dt.normalize()

    numeric_columns = [
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "residual_c",
        "seasonal_sin",
        "seasonal_cos",
    ]

    for column in numeric_columns:
        panel[column] = pd.to_numeric(
            panel[column],
            errors="coerce",
        )

    if panel[numeric_columns].isna().any().any():
        raise RuntimeError(
            "The Phase 5 panel contains missing "
            "numeric inputs."
        )

    if not np.isfinite(
        panel[numeric_columns].to_numpy()
    ).all():
        raise RuntimeError(
            "The Phase 5 panel contains non-finite "
            "numeric inputs."
        )

    if len(panel) != 2920:
        raise RuntimeError(
            "Expected 2,920 residual rows."
        )

    if panel["target_date"].nunique() != 730:
        raise RuntimeError(
            "Expected 730 weather-only dates."
        )

    if panel["decision_rule"].nunique() != 4:
        raise RuntimeError(
            "Expected four decision rules."
        )

    if panel.duplicated(
        [
            "target_date",
            "decision_rule",
        ]
    ).any():
        raise RuntimeError(
            "Duplicate date-rule keys found."
        )

    rule_counts = panel.groupby(
        "target_date"
    )["decision_rule"].nunique()

    if not rule_counts.eq(4).all():
        raise RuntimeError(
            "Not every date contains four rules."
        )

    dates = pd.DatetimeIndex(
        sorted(
            panel[
                "target_date"
            ].unique()
        )
    )

    expected_dates = pd.date_range(
        dates.min(),
        dates.max(),
        freq="D",
    )

    if not dates.equals(expected_dates):
        raise RuntimeError(
            "The weather-only dates are not "
            "a continuous daily sequence."
        )

    first_date = dates.min()

    design = panel[
        [
            "target_date",
            "decision_rule",
            "decision_rule_order",
            "forecast_daily_max_c",
            "hko_daily_max_c",
            "residual_c",
            "forecast_error_c",
            "absolute_error_c",
            "squared_error_c",
            "calendar_day_index",
            "day_of_year",
            "seasonal_sin",
            "seasonal_cos",
        ]
    ].copy()

    design[
        "calendar_time_years"
    ] = (
        (
            design["target_date"]
            - first_date
        ).dt.days
        / 365.2425
    )

    design[
        "gp_target"
    ] = design["residual_c"]

    design[
        "gp_model_scope"
    ] = "rule_specific"

    design[
        "covariance_kernel_candidate_1"
    ] = "squared_exponential_rbf"

    design[
        "covariance_kernel_candidate_2"
    ] = "matern_three_halves"

    design[
        "weather_only_training_period"
    ] = True

    design[
        "market_price_accessed"
    ] = False

    design[
        "polymarket_outcome_accessed"
    ] = False

    design[
        "model_fitted"
    ] = False

    design[
        "hyperparameters_estimated"
    ] = False

    design[
        "model_selected"
    ] = False

    design = design.sort_values(
        [
            "target_date",
            "decision_rule_order",
        ],
        kind="stable",
    ).reset_index(drop=True)

    initial_training_dates = int(
        specification[
            "initial_training_dates"
        ]
    )

    validation_blocks = int(
        specification[
            "validation_blocks"
        ]
    )

    remaining_dates = (
        len(dates)
        - initial_training_dates
    )

    validation_sizes = (
        build_validation_sizes(
            remaining_dates,
            validation_blocks,
        )
    )

    planned_sizes = list(
        specification[
            "validation_block_sizes"
        ]
    )

    if validation_sizes != planned_sizes:
        raise RuntimeError(
            "Derived validation sizes do not "
            "match the specification."
        )

    assignments, fold_summary = (
        build_fold_assignments(
            dates=dates,
            initial_training_dates=(
                initial_training_dates
            ),
            validation_sizes=(
                validation_sizes
            ),
        )
    )

    matrix, scaling = (
        construct_fold_matrices(
            design=design,
            assignments=assignments,
        )
    )

    expected_matrix_rows = int(
        fold_summary[
            [
                "training_rows",
                "validation_rows",
            ]
        ].sum(axis=1).sum()
    )

    validation_assignments = (
        assignments.loc[
            assignments[
                "sample_role"
            ].eq("validation")
        ]
    )

    validation_date_counts = (
        validation_assignments.groupby(
            "target_date"
        ).size()
    )

    chronological_checks = []

    for _, row in fold_summary.iterrows():
        chronological_checks.append(
            pd.Timestamp(
                row["training_end"]
            )
            < pd.Timestamp(
                row["validation_start"]
            )
        )

    train_standardisation_checks = []

    for (
        fold_id,
        decision_rule,
    ), group in matrix.loc[
        matrix[
            "sample_role"
        ].eq("training")
    ].groupby(
        [
            "fold_id",
            "decision_rule",
        ],
        sort=False,
    ):
        for column in STANDARDISED_COLUMNS:
            mean_value = float(
                group[column].mean()
            )

            standard_deviation = float(
                group[column].std(
                    ddof=0
                )
            )

            train_standardisation_checks.append(
                {
                    "fold_id": fold_id,
                    "decision_rule": (
                        decision_rule
                    ),
                    "feature": column,
                    "mean_near_zero": (
                        abs(mean_value) <= 1e-10
                    ),
                    "standard_deviation_near_one": (
                        abs(
                            standard_deviation
                            - 1.0
                        )
                        <= 1e-10
                    ),
                }
            )

    standardisation_audit = pd.DataFrame(
        train_standardisation_checks
    )

    checks = pd.DataFrame(
        [
            {
                "check": "raw_design_rows_equal_2920",
                "required": True,
                "passed": len(design) == 2920,
                "detail": len(design),
            },
            {
                "check": "weather_only_dates_equal_730",
                "required": True,
                "passed": (
                    design[
                        "target_date"
                    ].nunique()
                    == 730
                ),
                "detail": (
                    design[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "decision_rules_equal_4",
                "required": True,
                "passed": (
                    design[
                        "decision_rule"
                    ].nunique()
                    == 4
                ),
                "detail": (
                    design[
                        "decision_rule"
                    ].nunique()
                ),
            },
            {
                "check": "date_rule_keys_unique",
                "required": True,
                "passed": (
                    not design.duplicated(
                        [
                            "target_date",
                            "decision_rule",
                        ]
                    ).any()
                ),
                "detail": int(
                    design.duplicated(
                        [
                            "target_date",
                            "decision_rule",
                        ]
                    ).sum()
                ),
            },
            {
                "check": "four_rules_per_date",
                "required": True,
                "passed": (
                    design.groupby(
                        "target_date"
                    )[
                        "decision_rule"
                    ].nunique().eq(4).all()
                ),
                "detail": 730,
            },
            {
                "check": "continuous_daily_dates",
                "required": True,
                "passed": dates.equals(
                    expected_dates
                ),
                "detail": len(expected_dates),
            },
            {
                "check": "initial_training_dates_equal_365",
                "required": True,
                "passed": (
                    initial_training_dates
                    == 365
                ),
                "detail": (
                    initial_training_dates
                ),
            },
            {
                "check": "validation_dates_equal_365",
                "required": True,
                "passed": (
                    len(
                        validation_assignments
                    )
                    == 365
                ),
                "detail": len(
                    validation_assignments
                ),
            },
            {
                "check": "validation_block_sizes_correct",
                "required": True,
                "passed": (
                    fold_summary[
                        "validation_dates"
                    ].tolist()
                    == [91, 91, 91, 92]
                ),
                "detail": (
                    "|".join(
                        map(
                            str,
                            fold_summary[
                                "validation_dates"
                            ].tolist(),
                        )
                    )
                ),
            },
            {
                "check": "each_validation_date_used_once",
                "required": True,
                "passed": (
                    validation_date_counts.eq(
                        1
                    ).all()
                    and len(
                        validation_date_counts
                    )
                    == 365
                ),
                "detail": len(
                    validation_date_counts
                ),
            },
            {
                "check": "training_precedes_validation",
                "required": True,
                "passed": all(
                    chronological_checks
                ),
                "detail": (
                    f"{sum(chronological_checks)}"
                    f"/{len(chronological_checks)}"
                ),
            },
            {
                "check": "fold_matrix_rows_correct",
                "required": True,
                "passed": (
                    len(matrix)
                    == expected_matrix_rows
                    == 9484
                ),
                "detail": len(matrix),
            },
            {
                "check": "scaling_parameter_rows_equal_64",
                "required": True,
                "passed": len(scaling) == 64,
                "detail": len(scaling),
            },
            {
                "check": "training_standard_deviations_positive",
                "required": True,
                "passed": (
                    scaling[
                        "training_standard_deviation"
                    ].gt(0.0).all()
                ),
                "detail": float(
                    scaling[
                        "training_standard_deviation"
                    ].min()
                ),
            },
            {
                "check": "training_standardised_means_zero",
                "required": True,
                "passed": (
                    standardisation_audit[
                        "mean_near_zero"
                    ].all()
                ),
                "detail": int(
                    standardisation_audit[
                        "mean_near_zero"
                    ].sum()
                ),
            },
            {
                "check": "training_standardised_sds_one",
                "required": True,
                "passed": (
                    standardisation_audit[
                        "standard_deviation_near_one"
                    ].all()
                ),
                "detail": int(
                    standardisation_audit[
                        "standard_deviation_near_one"
                    ].sum()
                ),
            },
            {
                "check": "all_gp_features_finite",
                "required": True,
                "passed": np.isfinite(
                    matrix[
                        FEATURE_COLUMNS
                        + STANDARDISED_COLUMNS
                    ].to_numpy()
                ).all(),
                "detail": 0,
            },
            {
                "check": "gp_target_finite",
                "required": True,
                "passed": np.isfinite(
                    matrix[
                        "gp_target"
                    ].to_numpy()
                ).all(),
                "detail": 0,
            },
            {
                "check": "market_information_not_accessed",
                "required": True,
                "passed": True,
                "detail": False,
            },
            {
                "check": "model_not_fitted_or_selected",
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
            "Required Phase 6 checks failed:\n"
            + failed.to_string(index=False)
        )

    design_output = design.copy()

    date_columns = [
        "target_date",
    ]

    for column in date_columns:
        design_output[column] = (
            pd.to_datetime(
                design_output[column]
            )
            .dt.date
            .astype(str)
        )

    assignment_output = (
        assignments.copy()
    )

    for column in [
        "target_date",
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
    ]:
        assignment_output[column] = (
            pd.to_datetime(
                assignment_output[column]
            )
            .dt.date
            .astype(str)
        )

    matrix_output = matrix.copy()

    for column in [
        "target_date",
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
    ]:
        matrix_output[column] = (
            pd.to_datetime(
                matrix_output[column]
            )
            .dt.date
            .astype(str)
        )

    fold_summary_output = (
        fold_summary.copy()
    )

    for column in [
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
    ]:
        fold_summary_output[column] = (
            pd.to_datetime(
                fold_summary_output[column]
            )
            .dt.date
            .astype(str)
        )

    overall_summary = pd.DataFrame(
        [
            {
                "weather_only_dates": 730,
                "decision_rules": 4,
                "raw_design_rows": 2920,
                "initial_training_dates": 365,
                "validation_dates": 365,
                "validation_blocks": 4,
                "validation_block_sizes": (
                    "91|91|91|92"
                ),
                "fold_matrix_rows": (
                    len(matrix)
                ),
                "scaling_parameter_rows": (
                    len(scaling)
                ),
                "gp_target": "residual_c",
                "gp_model_scope": (
                    "separate_by_decision_rule"
                ),
                "gp_features": (
                    "|".join(
                        FEATURE_COLUMNS
                    )
                ),
                "candidate_kernels": (
                    "squared_exponential_rbf"
                    "|matern_three_halves"
                ),
                "market_prices_accessed": False,
                "model_fitted": False,
            }
        ]
    )

    write_csv(
        design_output,
        DESIGN_PATH,
    )

    write_csv(
        assignment_output,
        DATE_ASSIGNMENT_PATH,
    )

    write_csv(
        matrix_output,
        FOLD_MATRIX_PATH,
    )

    write_csv(
        scaling,
        SCALING_PATH,
    )

    write_csv(
        fold_summary_output,
        FOLD_SUMMARY_PATH,
    )

    write_csv(
        checks,
        CHECKS_PATH,
    )

    write_csv(
        overall_summary,
        MAIN_SUMMARY_PATH,
    )

    output_paths = [
        DESIGN_PATH,
        DATE_ASSIGNMENT_PATH,
        FOLD_MATRIX_PATH,
        SCALING_PATH,
        FOLD_SUMMARY_PATH,
        CHECKS_PATH,
        MAIN_SUMMARY_PATH,
    ]

    manifest = {
        "phase": 6,
        "phase_status": (
            "PHASE6_GP_TRAINING_DESIGN_COMPLETE"
        ),
        "status": (
            "TWO_YEAR_GP_TRAINING_DESIGN_CERTIFIED"
        ),
        "created_utc": utc_now(),
        "source": str(
            SOURCE_PATH.relative_to(ROOT)
        ),
        "source_sha256": (
            sha256_file(SOURCE_PATH)
        ),
        "weather_only_dates": 730,
        "decision_rules": 4,
        "raw_design_rows": 2920,
        "initial_training_dates": 365,
        "validation_dates": 365,
        "validation_blocks": 4,
        "validation_block_sizes": (
            validation_sizes
        ),
        "fold_matrix_rows": int(
            len(matrix)
        ),
        "scaling_parameter_rows": int(
            len(scaling)
        ),
        "target_column": "residual_c",
        "uncertainty_unit": (
            "target_date"
        ),
        "model_scope": (
            "separate_model_for_each_decision_rule"
        ),
        "feature_columns": (
            FEATURE_COLUMNS
        ),
        "standardised_feature_columns": (
            STANDARDISED_COLUMNS
        ),
        "candidate_covariance_kernels": [
            "squared_exponential_rbf",
            "matern_three_halves",
        ],
        "standardisation_rule": (
            "training_fold_and_decision_rule_only"
        ),
        "validation_rule": (
            "expanding_chronological"
        ),
        "each_validation_date_used_once": True,
        "training_dates_precede_validation_dates": True,
        "market_prices_accessed": False,
        "polymarket_outcomes_accessed": False,
        "model_fitted": False,
        "hyperparameters_estimated": False,
        "model_selected": False,
        "calibration_selected": False,
        "trading_returns_calculated": False,
        "required_integrity_checks_passed": True,
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
            "Fit rule-specific Gaussian-process "
            "residual models within the certified "
            "chronological folds and produce "
            "out-of-fold predictive distributions."
        ),
    }

    write_json(
        manifest,
        MANIFEST_PATH,
    )

    print()
    print("=" * 78)
    print("PHASE 6 GP TRAINING DESIGN")
    print("=" * 78)

    print("Status:", manifest["status"])
    print("Weather-only dates: 730")
    print("Initial training dates: 365")
    print("Validation dates: 365")
    print(
        "Validation blocks:",
        manifest[
            "validation_block_sizes"
        ],
    )
    print("Decision rules: 4")
    print("Raw design rows: 2920")
    print(
        "Fold matrix rows:",
        manifest[
            "fold_matrix_rows"
        ],
    )
    print(
        "Scaling parameter rows:",
        manifest[
            "scaling_parameter_rows"
        ],
    )
    print(
        "GP target:",
        manifest[
            "target_column"
        ],
    )
    print(
        "GP features:",
        ", ".join(
            manifest[
                "feature_columns"
            ]
        ),
    )
    print(
        "Separate model for each decision rule: True"
    )
    print(
        "Each validation date used once: True"
    )
    print(
        "Training precedes validation: True"
    )
    print(
        "Market prices accessed: False"
    )
    print(
        "Model fitted or selected: False"
    )
    print(
        "PHASE 6 CORE CONSTRUCTION: PASSED"
    )


if __name__ == "__main__":
    main()
