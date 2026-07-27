#!/usr/bin/env python3
"""Map locked 99-quantile distributions to certified event probabilities."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path.cwd()

CONFIG_PATH = (
    ROOT
    / "config"
    / "event_probability_construction_spec.yaml"
)

SETTLEMENT_MANIFEST_PATH = (
    ROOT
    / "data/manifests/01_event_book_certification_manifest.json"
)

CALIBRATION_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "05_continuous_calibration_manifest.json"
)

PREDICTION_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "06_locked_prediction_manifest.json"
)

EVALUATION_MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "07_continuous_evaluation_manifest.json"
)

PREDICTION_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "06_locked_calibrated_predictions.csv"
)

SOURCE_AUDIT_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "08_event_book_source_audit.csv"
)

PROBABILITY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "08_locked_event_probability_panel.csv"
)

BOOK_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "08_event_probability_book_summary.csv"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs"
    / "diagnostics"
    / "08_event_probability_integrity_checks.csv"
)

FINAL_SUMMARY_PATH = (
    ROOT
    / "outputs"
    / "final_tables"
    / "08_event_probability_book_summary.csv"
)

MANIFEST_PATH = (
    ROOT
    / "data"
    / "manifests"
    / "08_event_probability_manifest.json"
)


DATE_COLUMN_CANDIDATES = [
    "target_date",
    "event_date",
    "original_event_date",
    "outcome_date",
    "settlement_date",
]

LOWER_COLUMN_CANDIDATES = [
    "event_lower_bound_C",
    "event_lower_bound_c",
    "lower_bound_C",
    "lower_bound_c",
    "event_lower_bound",
    "lower_bound",
    "lower",
]

UPPER_COLUMN_CANDIDATES = [
    "event_upper_bound_C",
    "event_upper_bound_c",
    "upper_bound_C",
    "upper_bound_c",
    "event_upper_bound",
    "upper_bound",
    "upper",
]

LABEL_COLUMN_CANDIDATES = [
    "visible_contract_label",
    "event_label",
    "contract_label",
    "group_item_title",
    "market_question",
    "event_slug",
    "market_slug",
    "label",
]

IDENTIFIER_COLUMN_CANDIDATES = [
    "event_slug",
    "market_slug",
    "visible_contract_label",
    "contract_label",
    "group_item_title",
    "market_question",
    "event_label",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def quantile_columns() -> list[str]:
    return [
        f"q_{index:02d}"
        for index in range(
            1,
            100,
        )
    ]


def first_present(
    columns: list[str],
    candidates: list[str],
) -> str | None:
    exact = {
        str(column): str(column)
        for column in columns
    }

    lower_map = {
        str(column).lower(): str(column)
        for column in columns
    }

    for candidate in candidates:
        if candidate in exact:
            return exact[
                candidate
            ]

        if candidate.lower() in lower_map:
            return lower_map[
                candidate.lower()
            ]

    return None


def parse_numeric_bound(
    series: pd.Series,
) -> pd.Series:
    text = (
        series.astype(
            "string"
        )
        .str.strip()
        .str.lower()
    )

    replacements = {
        "": pd.NA,
        "none": pd.NA,
        "nan": pd.NA,
        "na": pd.NA,
        "null": pd.NA,
        "-infinity": "-inf",
        "infinity": "inf",
        "+infinity": "inf",
        "+inf": "inf",
    }

    text = text.replace(
        replacements
    )

    return pd.to_numeric(
        text,
        errors="coerce",
    )


def format_temperature(value: float) -> str:
    if math.isclose(
        value,
        round(value),
        abs_tol=1.0e-10,
    ):
        return str(
            int(
                round(value)
            )
        )

    return (
        f"{value:.6f}"
        .rstrip("0")
        .rstrip(".")
    )


def canonical_event_label(
    lower: float,
    upper: float,
) -> str:
    if np.isneginf(
        lower
    ):
        return (
            "T < "
            + format_temperature(
                upper
            )
            + "°C"
        )

    if np.isposinf(
        upper
    ):
        return (
            "T ≥ "
            + format_temperature(
                lower
            )
            + "°C"
        )

    return (
        format_temperature(
            lower
        )
        + "°C ≤ T < "
        + format_temperature(
            upper
        )
        + "°C"
    )


def candidate_paths() -> list[Path]:
    explicit = [
        ROOT
        / "data"
        / "processed"
        / "01_certified_event_book.csv",
        ROOT
        / "data"
        / "processed"
        / "01_certified_contract_event_panel.csv",
        ROOT
        / "data"
        / "processed"
        / "01_settlement_event_book.csv",
        ROOT
        / "data"
        / "manual"
        / "18w_outcome_free_contract_definitions"
        / "18w_outcome_free_contract_definition_panel.csv",
    ]

    discovered: list[Path] = []

    for directory in (
        ROOT / "data" / "processed",
        ROOT / "data" / "manual",
        ROOT / "data" / "interim",
    ):
        if directory.exists():
            discovered.extend(
                directory.rglob(
                    "*.csv"
                )
            )

    unique: dict[
        str,
        Path,
    ] = {}

    for path in (
        explicit
        + discovered
    ):
        if not path.exists():
            continue

        relative = str(
            path.relative_to(
                ROOT
            )
        )

        lower_name = relative.lower()

        excluded_fragments = [
            "probability",
            "score",
            "strategy",
            "allocation",
            "pnl",
            "price",
            "forecast",
            "issue",
            "integrity",
            "summary",
        ]

        if any(
            fragment in lower_name
            for fragment in excluded_fragments
        ):
            continue

        if path.stat().st_size > 250_000_000:
            continue

        unique[
            relative
        ] = path

    return [
        unique[key]
        for key in sorted(
            unique
        )
    ]


def validate_partition(
    frame: pd.DataFrame,
) -> tuple[
    bool,
    str,
]:
    for target_date, book in frame.groupby(
        "target_date",
        sort=True,
    ):
        if len(book) != 11:
            return (
                False,
                f"{target_date} contains {len(book)} events rather than 11.",
            )

        ordered = book.sort_values(
            [
                "lower_effective_c",
                "upper_effective_c",
            ]
        ).reset_index(
            drop=True
        )

        lower = ordered[
            "lower_effective_c"
        ].to_numpy(
            dtype=float
        )

        upper = ordered[
            "upper_effective_c"
        ].to_numpy(
            dtype=float
        )

        if not np.isneginf(
            lower[0]
        ):
            return (
                False,
                f"{target_date} has no unbounded lower-tail event.",
            )

        if not np.isposinf(
            upper[-1]
        ):
            return (
                False,
                f"{target_date} has no unbounded upper-tail event.",
            )

        if (
            lower >= upper
        ).any():
            return (
                False,
                f"{target_date} contains an empty or reversed interval.",
            )

        for index in range(
            len(ordered) - 1
        ):
            left_upper = upper[
                index
            ]

            right_lower = lower[
                index + 1
            ]

            if not np.isclose(
                left_upper,
                right_lower,
                atol=1.0e-9,
                rtol=0.0,
            ):
                return (
                    False,
                    f"{target_date} has a gap or overlap between "
                    f"events {index + 1} and {index + 2}: "
                    f"{left_upper} versus {right_lower}.",
                )

    return (
        True,
        "partition_valid",
    )


def inspect_candidate(
    path: Path,
    prediction_dates: set[str],
) -> tuple[
    dict[str, Any],
    pd.DataFrame | None,
]:
    relative = str(
        path.relative_to(
            ROOT
        )
    )

    audit: dict[
        str,
        Any,
    ] = {
        "path": relative,
        "status": "REJECTED",
        "reason": "",
        "date_column": "",
        "lower_column": "",
        "upper_column": "",
        "label_column": "",
        "identifier_column": "",
        "matching_prediction_dates": 0,
        "rows_on_prediction_dates": 0,
        "dates_with_exactly_11_events": 0,
        "priority_score": 0,
    }

    try:
        header = pd.read_csv(
            path,
            nrows=0,
        )
    except Exception as exc:
        audit[
            "reason"
        ] = (
            "header_read_failed: "
            + str(exc)
        )

        return (
            audit,
            None,
        )

    columns = [
        str(column)
        for column in header.columns
    ]

    date_column = first_present(
        columns,
        DATE_COLUMN_CANDIDATES,
    )

    lower_column = first_present(
        columns,
        LOWER_COLUMN_CANDIDATES,
    )

    upper_column = first_present(
        columns,
        UPPER_COLUMN_CANDIDATES,
    )

    label_column = first_present(
        columns,
        LABEL_COLUMN_CANDIDATES,
    )

    identifier_column = first_present(
        columns,
        IDENTIFIER_COLUMN_CANDIDATES,
    )

    audit[
        "date_column"
    ] = date_column or ""

    audit[
        "lower_column"
    ] = lower_column or ""

    audit[
        "upper_column"
    ] = upper_column or ""

    audit[
        "label_column"
    ] = label_column or ""

    audit[
        "identifier_column"
    ] = identifier_column or ""

    if not (
        date_column
        and lower_column
        and upper_column
    ):
        audit[
            "reason"
        ] = (
            "required_date_or_boundary_columns_missing"
        )

        return (
            audit,
            None,
        )

    use_columns = [
        date_column,
        lower_column,
        upper_column,
    ]

    for optional_column in (
        label_column,
        identifier_column,
    ):
        if (
            optional_column
            and optional_column
            not in use_columns
        ):
            use_columns.append(
                optional_column
            )

    try:
        source = pd.read_csv(
            path,
            usecols=use_columns,
            low_memory=False,
        )
    except Exception as exc:
        audit[
            "reason"
        ] = (
            "data_read_failed: "
            + str(exc)
        )

        return (
            audit,
            None,
        )

    source[
        "target_date"
    ] = pd.to_datetime(
        source[
            date_column
        ],
        errors="coerce",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    source = source.loc[
        source[
            "target_date"
        ].isin(
            prediction_dates
        )
    ].copy()

    matching_dates = set(
        source[
            "target_date"
        ].dropna()
    )

    audit[
        "matching_prediction_dates"
    ] = len(
        matching_dates
    )

    audit[
        "rows_on_prediction_dates"
    ] = len(
        source
    )

    if matching_dates != prediction_dates:
        missing = sorted(
            prediction_dates
            - matching_dates
        )

        audit[
            "reason"
        ] = (
            "missing_prediction_dates: "
            + ",".join(
                missing[:10]
            )
        )

        return (
            audit,
            None,
        )

    source[
        "lower_bound_c"
    ] = parse_numeric_bound(
        source[
            lower_column
        ]
    )

    source[
        "upper_bound_c"
    ] = parse_numeric_bound(
        source[
            upper_column
        ]
    )

    source[
        "lower_effective_c"
    ] = source[
        "lower_bound_c"
    ].fillna(
        -np.inf
    )

    source[
        "upper_effective_c"
    ] = source[
        "upper_bound_c"
    ].fillna(
        np.inf
    )

    count_by_date = source.groupby(
        "target_date"
    ).size()

    audit[
        "dates_with_exactly_11_events"
    ] = int(
        count_by_date.eq(11).sum()
    )

    if not count_by_date.eq(
        11
    ).all():
        audit[
            "reason"
        ] = (
            "not_exactly_11_events_per_prediction_date"
        )

        return (
            audit,
            None,
        )

    valid, reason = validate_partition(
        source
    )

    if not valid:
        audit[
            "reason"
        ] = reason

        return (
            audit,
            None,
        )

    if label_column:
        source[
            "source_event_label"
        ] = source[
            label_column
        ].astype(
            "string"
        )
    else:
        source[
            "source_event_label"
        ] = pd.NA

    if identifier_column:
        source[
            "source_event_identifier"
        ] = source[
            identifier_column
        ].astype(
            "string"
        )
    else:
        source[
            "source_event_identifier"
        ] = pd.NA

    source = source[
        [
            "target_date",
            "lower_bound_c",
            "upper_bound_c",
            "lower_effective_c",
            "upper_effective_c",
            "source_event_label",
            "source_event_identifier",
        ]
    ].copy()

    priority = 1000

    lower_path = relative.lower()

    for keyword, value in (
        (
            "01_",
            80,
        ),
        (
            "certified",
            70,
        ),
        (
            "outcome_free_contract_definition",
            60,
        ),
        (
            "contract_event",
            50,
        ),
        (
            "event_book",
            40,
        ),
        (
            "18w",
            30,
        ),
    ):
        if keyword in lower_path:
            priority += value

    audit[
        "status"
    ] = "ADMISSIBLE"

    audit[
        "reason"
    ] = "complete_certified_partition_candidate"

    audit[
        "priority_score"
    ] = priority

    return (
        audit,
        source,
    )


def resolve_event_book(
    prediction_dates: set[str],
) -> tuple[
    Path,
    pd.DataFrame,
    pd.DataFrame,
]:
    audit_rows: list[
        dict[str, Any]
    ] = []

    admissible: list[
        tuple[
            int,
            str,
            Path,
            pd.DataFrame,
        ]
    ] = []

    for path in candidate_paths():
        audit, source = inspect_candidate(
            path,
            prediction_dates,
        )

        audit_rows.append(
            audit
        )

        if (
            audit[
                "status"
            ]
            == "ADMISSIBLE"
            and source is not None
        ):
            admissible.append(
                (
                    int(
                        audit[
                            "priority_score"
                        ]
                    ),
                    str(
                        path.relative_to(
                            ROOT
                        )
                    ),
                    path,
                    source,
                )
            )

    audit_frame = pd.DataFrame(
        audit_rows
    )

    if not admissible:
        raise RuntimeError(
            "No certified eleven-event source covers all locked "
            "prediction dates. Inspect "
            "outputs/diagnostics/08_event_book_source_audit.csv."
        )

    admissible.sort(
        key=lambda item: (
            -item[0],
            item[1],
        )
    )

    _, _, selected_path, selected_source = (
        admissible[0]
    )

    audit_frame[
        "selected"
    ] = audit_frame[
        "path"
    ].eq(
        str(
            selected_path.relative_to(
                ROOT
            )
        )
    )

    return (
        selected_path,
        selected_source,
        audit_frame,
    )


def prepare_event_books(
    source: pd.DataFrame,
) -> pd.DataFrame:
    books: list[
        pd.DataFrame
    ] = []

    for target_date, book in source.groupby(
        "target_date",
        sort=True,
    ):
        ordered = (
            book.sort_values(
                [
                    "lower_effective_c",
                    "upper_effective_c",
                ]
            )
            .reset_index(
                drop=True
            )
            .copy()
        )

        ordered[
            "event_order"
        ] = np.arange(
            1,
            len(ordered) + 1,
        )

        ordered[
            "event_label"
        ] = [
            canonical_event_label(
                float(lower),
                float(upper),
            )
            for lower, upper in zip(
                ordered[
                    "lower_effective_c"
                ],
                ordered[
                    "upper_effective_c"
                ],
            )
        ]

        ordered[
            "event_id"
        ] = [
            (
                f"{target_date}|"
                f"{event_order:02d}"
            )
            for event_order in ordered[
                "event_order"
            ]
        ]

        ordered[
            "lower_unbounded"
        ] = np.isneginf(
            ordered[
                "lower_effective_c"
            ].to_numpy(
                dtype=float
            )
        )

        ordered[
            "upper_unbounded"
        ] = np.isposinf(
            ordered[
                "upper_effective_c"
            ].to_numpy(
                dtype=float
            )
        )

        ordered[
            "lower_inclusive"
        ] = True

        ordered[
            "upper_inclusive"
        ] = False

        books.append(
            ordered
        )

    result = pd.concat(
        books,
        ignore_index=True,
    )

    valid, reason = validate_partition(
        result
    )

    if not valid:
        raise RuntimeError(
            reason
        )

    return result


def construct_probability_panel(
    predictions: pd.DataFrame,
    event_books: pd.DataFrame,
) -> pd.DataFrame:
    q_columns = quantile_columns()

    outputs: list[
        dict[str, Any]
    ] = []

    books_by_date = {
        target_date: book.sort_values(
            "event_order"
        ).reset_index(
            drop=True
        )
        for target_date, book in event_books.groupby(
            "target_date",
            sort=False,
        )
    }

    for prediction in predictions.itertuples(
        index=False
    ):
        target_date = str(
            prediction.target_date
        )

        row_id = str(
            prediction.row_id
        )

        if target_date not in books_by_date:
            raise RuntimeError(
                f"No event book exists for {target_date}."
            )

        book = books_by_date[
            target_date
        ]

        particles = np.array(
            [
                float(
                    getattr(
                        prediction,
                        column
                    )
                )
                for column in q_columns
            ],
            dtype=float,
        )

        if not np.isfinite(
            particles
        ).all():
            raise RuntimeError(
                f"Prediction {row_id} contains a non-finite particle."
            )

        if not (
            np.diff(
                particles
            )
            >= -1.0e-10
        ).all():
            raise RuntimeError(
                f"Prediction {row_id} contains crossing quantiles."
            )

        lower = book[
            "lower_effective_c"
        ].to_numpy(
            dtype=float
        )

        upper = book[
            "upper_effective_c"
        ].to_numpy(
            dtype=float
        )

        membership = (
            (
                particles.reshape(
                    -1,
                    1,
                )
                >= lower.reshape(
                    1,
                    -1,
                )
            )
            & (
                particles.reshape(
                    -1,
                    1,
                )
                < upper.reshape(
                    1,
                    -1,
                )
            )
        )

        assignment_counts = membership.sum(
            axis=1
        )

        if not (
            assignment_counts == 1
        ).all():
            problematic = np.flatnonzero(
                assignment_counts != 1
            )

            raise RuntimeError(
                f"Prediction {row_id} does not assign every particle "
                f"to exactly one event. Problematic particle indices: "
                f"{problematic.tolist()}."
            )

        counts = membership.sum(
            axis=0
        ).astype(
            int
        )

        if int(
            counts.sum()
        ) != 99:
            raise RuntimeError(
                f"Prediction {row_id} assigned {counts.sum()} "
                "rather than 99 particles."
            )

        probabilities = (
            counts.astype(
                float
            )
            / 99.0
        )

        if not np.isclose(
            probabilities.sum(),
            1.0,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise RuntimeError(
                f"Prediction {row_id} probabilities do not sum to one."
            )

        for event_index, event in book.iterrows():
            outputs.append(
                {
                    "row_id": row_id,
                    "target_date": target_date,
                    "decision_rule": str(
                        prediction.decision_rule
                    ),
                    "chronology_block": str(
                        prediction.chronology_block
                    ),
                    "selected_model": str(
                        prediction.selected_model
                    ),
                    "selected_family": str(
                        prediction.selected_family
                    ),
                    "dispersion_scale": float(
                        prediction.dispersion_scale
                    ),
                    "event_id": str(
                        event[
                            "event_id"
                        ]
                    ),
                    "event_order": int(
                        event[
                            "event_order"
                        ]
                    ),
                    "event_label": str(
                        event[
                            "event_label"
                        ]
                    ),
                    "source_event_label": (
                        event[
                            "source_event_label"
                        ]
                    ),
                    "source_event_identifier": (
                        event[
                            "source_event_identifier"
                        ]
                    ),
                    "lower_bound_c": (
                        np.nan
                        if bool(
                            event[
                                "lower_unbounded"
                            ]
                        )
                        else float(
                            event[
                                "lower_bound_c"
                            ]
                        )
                    ),
                    "upper_bound_c": (
                        np.nan
                        if bool(
                            event[
                                "upper_unbounded"
                            ]
                        )
                        else float(
                            event[
                                "upper_bound_c"
                            ]
                        )
                    ),
                    "lower_unbounded": bool(
                        event[
                            "lower_unbounded"
                        ]
                    ),
                    "upper_unbounded": bool(
                        event[
                            "upper_unbounded"
                        ]
                    ),
                    "lower_inclusive": True,
                    "upper_inclusive": False,
                    "quantile_particle_count": int(
                        counts[
                            event_index
                        ]
                    ),
                    "quantile_particle_total": 99,
                    "raw_event_probability": float(
                        probabilities[
                            event_index
                        ]
                    ),
                    "probability_regularised": False,
                    "market_price_accessed": False,
                    "outcome_accessed": False,
                    "score_calculated": False,
                }
            )

    panel = pd.DataFrame(
        outputs
    )

    return (
        panel.sort_values(
            [
                "chronology_block",
                "target_date",
                "decision_rule",
                "event_order",
            ]
        )
        .reset_index(
            drop=True
        )
    )


def create_book_summary(
    panel: pd.DataFrame,
) -> pd.DataFrame:
    def entropy(
        probabilities: pd.Series,
    ) -> float:
        positive = probabilities.loc[
            probabilities > 0.0
        ].to_numpy(
            dtype=float
        )

        if len(positive) == 0:
            return 0.0

        return float(
            -np.sum(
                positive
                * np.log(
                    positive
                )
            )
        )

    grouped = panel.groupby(
        [
            "row_id",
            "target_date",
            "decision_rule",
            "chronology_block",
            "selected_model",
            "selected_family",
            "dispersion_scale",
        ],
        as_index=False,
    )

    summary = grouped.agg(
        events=(
            "event_id",
            "size",
        ),
        probability_sum=(
            "raw_event_probability",
            "sum",
        ),
        particle_count_sum=(
            "quantile_particle_count",
            "sum",
        ),
        occupied_events=(
            "quantile_particle_count",
            lambda series: int(
                (
                    series > 0
                ).sum()
            ),
        ),
        zero_probability_events=(
            "raw_event_probability",
            lambda series: int(
                (
                    series == 0.0
                ).sum()
            ),
        ),
        minimum_probability=(
            "raw_event_probability",
            "min",
        ),
        maximum_probability=(
            "raw_event_probability",
            "max",
        ),
    )

    entropy_frame = (
        panel.groupby(
            "row_id"
        )[
            "raw_event_probability"
        ]
        .apply(
            entropy
        )
        .rename(
            "probability_entropy"
        )
        .reset_index()
    )

    summary = summary.merge(
        entropy_frame,
        on="row_id",
        how="left",
        validate="one_to_one",
    )

    summary[
        "effective_event_count"
    ] = np.exp(
        summary[
            "probability_entropy"
        ]
    )

    return (
        summary.sort_values(
            [
                "chronology_block",
                "target_date",
                "decision_rule",
            ]
        )
        .reset_index(
            drop=True
        )
    )


def main() -> None:
    config = yaml.safe_load(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    settlement_manifest = json.loads(
        SETTLEMENT_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    calibration_manifest = json.loads(
        CALIBRATION_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    prediction_manifest = json.loads(
        PREDICTION_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    evaluation_manifest = json.loads(
        EVALUATION_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    if not prediction_manifest[
        "predictions_locked"
    ]:
        raise RuntimeError(
            "Locked predictions are unavailable."
        )

    if not evaluation_manifest[
        "evaluation_locked"
    ]:
        raise RuntimeError(
            "Continuous evaluation is incomplete."
        )

    if evaluation_manifest[
        "event_probabilities_calculated"
    ]:
        raise RuntimeError(
            "The prior evaluation manifest unexpectedly records "
            "event probability construction."
        )

    if evaluation_manifest[
        "market_data_accessed"
    ]:
        raise RuntimeError(
            "Market data were accessed before event probability construction."
        )

    if evaluation_manifest[
        "trading_returns_calculated"
    ]:
        raise RuntimeError(
            "Trading returns were calculated before event probabilities."
        )

    if (
        prediction_manifest[
            "selected_model"
        ]
        != calibration_manifest[
            "selected_model"
        ]
    ):
        raise RuntimeError(
            "Prediction and calibration manifests disagree."
        )

    predictions = pd.read_csv(
        PREDICTION_PATH,
        low_memory=False,
    )

    predictions[
        "target_date"
    ] = pd.to_datetime(
        predictions[
            "target_date"
        ],
        errors="raise",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    if len(
        predictions
    ) != 159:
        raise RuntimeError(
            f"Expected 159 locked predictions; found {len(predictions)}."
        )

    if predictions[
        "target_date"
    ].nunique() != 40:
        raise RuntimeError(
            "Expected 40 locked prediction dates."
        )

    if predictions[
        "row_id"
    ].duplicated().any():
        raise RuntimeError(
            "The locked prediction panel duplicates row IDs."
        )

    q_columns = quantile_columns()

    missing_quantiles = [
        column
        for column in q_columns
        if column not in predictions.columns
    ]

    if missing_quantiles:
        raise RuntimeError(
            "Locked predictions are missing quantiles: "
            + ", ".join(
                missing_quantiles
            )
        )

    quantile_values = predictions[
        q_columns
    ].to_numpy(
        dtype=float
    )

    if not np.isfinite(
        quantile_values
    ).all():
        raise RuntimeError(
            "Locked quantiles contain non-finite values."
        )

    if not (
        np.diff(
            quantile_values,
            axis=1,
        )
        >= -1.0e-10
    ).all():
        raise RuntimeError(
            "Locked quantiles are not monotone."
        )

    prediction_dates = set(
        predictions[
            "target_date"
        ]
    )

    (
        event_book_source_path,
        event_book_source,
        source_audit,
    ) = resolve_event_book(
        prediction_dates
    )

    event_books = prepare_event_books(
        event_book_source
    )

    panel = construct_probability_panel(
        predictions,
        event_books,
    )

    book_summary = create_book_summary(
        panel
    )

    expected_output_rows = (
        len(
            predictions
        )
        * 11
    )

    if expected_output_rows != 1749:
        raise RuntimeError(
            "The expected event probability row count is not 1749."
        )

    probability_sums = panel.groupby(
        "row_id"
    )[
        "raw_event_probability"
    ].sum()

    particle_sums = panel.groupby(
        "row_id"
    )[
        "quantile_particle_count"
    ].sum()

    event_counts = panel.groupby(
        "row_id"
    )[
        "event_id"
    ].size()

    lower_tail_counts = panel.groupby(
        "row_id"
    )[
        "lower_unbounded"
    ].sum()

    upper_tail_counts = panel.groupby(
        "row_id"
    )[
        "upper_unbounded"
    ].sum()

    probability_resolution = (
        1.0
        / 99.0
    )

    reconstructed_probability = (
        panel[
            "quantile_particle_count"
        ].to_numpy(
            dtype=float
        )
        / 99.0
    )

    observed_probability = panel[
        "raw_event_probability"
    ].to_numpy(
        dtype=float
    )

    prohibited_fragments = [
        "hko_daily_max",
        "realised",
        "realized",
        "outcome_value",
        "winning_event",
        "crps",
        "brier",
        "log_score",
        "market_price",
        "best_bid",
        "best_ask",
        "spread",
        "pnl",
        "profit",
    ]

    permitted_boundary_audit_columns = {
        "probability_regularised",
        "market_price_accessed",
        "outcome_accessed",
        "score_calculated",
    }

    prohibited_columns = [
        column
        for column in panel.columns
        if column not in permitted_boundary_audit_columns
        and any(
            fragment in column.lower()
            for fragment in prohibited_fragments
        )
    ]

    checks = pd.DataFrame(
        [
            {
                "check": "locked_prediction_rows_equal_159",
                "passed": len(predictions) == 159,
                "value": len(predictions),
            },
            {
                "check": "locked_prediction_dates_equal_40",
                "passed": (
                    predictions[
                        "target_date"
                    ].nunique()
                    == 40
                ),
                "value": (
                    predictions[
                        "target_date"
                    ].nunique()
                ),
            },
            {
                "check": "event_probability_rows_equal_1749",
                "passed": len(panel) == 1749,
                "value": len(panel),
            },
            {
                "check": "each_prediction_has_11_events",
                "passed": bool(
                    event_counts.eq(
                        11
                    ).all()
                ),
                "value": int(
                    event_counts.min()
                ),
            },
            {
                "check": "each_prediction_has_one_lower_tail",
                "passed": bool(
                    lower_tail_counts.eq(
                        1
                    ).all()
                ),
                "value": int(
                    lower_tail_counts.min()
                ),
            },
            {
                "check": "each_prediction_has_one_upper_tail",
                "passed": bool(
                    upper_tail_counts.eq(
                        1
                    ).all()
                ),
                "value": int(
                    upper_tail_counts.min()
                ),
            },
            {
                "check": "each_probability_book_sums_to_one",
                "passed": bool(
                    np.allclose(
                        probability_sums.to_numpy(
                            dtype=float
                        ),
                        1.0,
                        atol=1.0e-12,
                        rtol=0.0,
                    )
                ),
                "value": float(
                    np.max(
                        np.abs(
                            probability_sums.to_numpy(
                                dtype=float
                            )
                            - 1.0
                        )
                    )
                ),
            },
            {
                "check": "each_probability_book_assigns_99_particles",
                "passed": bool(
                    particle_sums.eq(
                        99
                    ).all()
                ),
                "value": int(
                    particle_sums.min()
                ),
            },
            {
                "check": "probabilities_equal_particle_counts_divided_by_99",
                "passed": bool(
                    np.allclose(
                        reconstructed_probability,
                        observed_probability,
                        atol=1.0e-12,
                        rtol=0.0,
                    )
                ),
                "value": float(
                    np.max(
                        np.abs(
                            reconstructed_probability
                            - observed_probability
                        )
                    )
                ),
            },
            {
                "check": "probabilities_are_finite",
                "passed": bool(
                    np.isfinite(
                        observed_probability
                    ).all()
                ),
                "value": True,
            },
            {
                "check": "probabilities_are_between_zero_and_one",
                "passed": bool(
                    (
                        (
                            observed_probability
                            >= 0.0
                        )
                        & (
                            observed_probability
                            <= 1.0
                        )
                    ).all()
                ),
                "value": True,
            },
            {
                "check": "no_duplicate_row_event_keys",
                "passed": not panel[
                    [
                        "row_id",
                        "event_order",
                    ]
                ].duplicated().any(),
                "value": True,
            },
            {
                "check": "no_prohibited_outcome_score_or_price_columns",
                "passed": len(
                    prohibited_columns
                ) == 0,
                "value": ",".join(
                    prohibited_columns
                ),
            },
            {
                "check": "probability_regularisation_not_applied",
                "passed": bool(
                    (
                        ~panel[
                            "probability_regularised"
                        ]
                    ).all()
                ),
                "value": False,
            },
            {
                "check": "market_prices_not_accessed",
                "passed": bool(
                    (
                        ~panel[
                            "market_price_accessed"
                        ]
                    ).all()
                ),
                "value": False,
            },
            {
                "check": "outcomes_not_accessed",
                "passed": bool(
                    (
                        ~panel[
                            "outcome_accessed"
                        ]
                    ).all()
                ),
                "value": False,
            },
            {
                "check": "scores_not_calculated",
                "passed": bool(
                    (
                        ~panel[
                            "score_calculated"
                        ]
                    ).all()
                ),
                "value": False,
            },
        ]
    )

    if not checks[
        "passed"
    ].all():
        failures = checks.loc[
            ~checks[
                "passed"
            ]
        ]

        raise RuntimeError(
            "Event probability integrity checks failed:\n"
            + failures.to_string(
                index=False
            )
        )

    for path in (
        SOURCE_AUDIT_PATH,
        PROBABILITY_PATH,
        BOOK_SUMMARY_PATH,
        INTEGRITY_PATH,
        FINAL_SUMMARY_PATH,
        MANIFEST_PATH,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    source_audit.to_csv(
        SOURCE_AUDIT_PATH,
        index=False,
    )

    panel.to_csv(
        PROBABILITY_PATH,
        index=False,
    )

    book_summary.to_csv(
        BOOK_SUMMARY_PATH,
        index=False,
    )

    book_summary.to_csv(
        FINAL_SUMMARY_PATH,
        index=False,
    )

    checks.to_csv(
        INTEGRITY_PATH,
        index=False,
    )

    zero_probability_event_share = float(
        panel[
            "raw_event_probability"
        ].eq(
            0.0
        ).mean()
    )

    occupied_event_mean = float(
        book_summary[
            "occupied_events"
        ].mean()
    )

    mean_entropy = float(
        book_summary[
            "probability_entropy"
        ].mean()
    )

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": (
            "LOCKED_EVENT_PROBABILITY_CONSTRUCTION_COMPLETE"
        ),
        "probability_construction_locked": True,
        "selected_model": (
            prediction_manifest[
                "selected_model"
            ]
        ),
        "selected_family": (
            prediction_manifest[
                "selected_family"
            ]
        ),
        "selected_dispersion_scale": float(
            prediction_manifest[
                "selected_dispersion_scale"
            ]
        ),
        "event_book_source": str(
            event_book_source_path.relative_to(
                ROOT
            )
        ),
        "event_book_source_sha256": sha256_file(
            event_book_source_path
        ),
        "settlement_certification_status": (
            settlement_manifest.get(
                "status"
            )
        ),
        "prediction_rows": len(
            predictions
        ),
        "prediction_dates": int(
            predictions[
                "target_date"
            ].nunique()
        ),
        "event_count_per_prediction": 11,
        "probability_rows": len(
            panel
        ),
        "quantile_particle_count": 99,
        "quantile_particle_interpretation": (
            "equally weighted deterministic quantile particles"
        ),
        "quantile_particles_are_independent_draws": False,
        "probability_resolution": (
            probability_resolution
        ),
        "boundary_convention": (
            "left closed and right open"
        ),
        "lower_tail_unbounded": True,
        "upper_tail_unbounded": True,
        "probability_books_sum_to_one": True,
        "all_particles_assigned_exactly_once": True,
        "zero_probabilities_retained": True,
        "zero_probability_event_share": (
            zero_probability_event_share
        ),
        "mean_occupied_events_per_probability_book": (
            occupied_event_mean
        ),
        "mean_probability_entropy": (
            mean_entropy
        ),
        "probability_regularisation_applied": False,
        "realised_outcomes_accessed": False,
        "categorical_scores_calculated": False,
        "market_contract_definitions_accessed": True,
        "market_prices_accessed": False,
        "trading_returns_calculated": False,
        "model_refitted": False,
        "model_reselected": False,
        "continuous_calibration_reselected": False,
        "input_hashes": {
            str(
                CONFIG_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CONFIG_PATH
            ),
            str(
                PREDICTION_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                PREDICTION_PATH
            ),
            str(
                PREDICTION_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                PREDICTION_MANIFEST_PATH
            ),
            str(
                EVALUATION_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                EVALUATION_MANIFEST_PATH
            ),
        },
        "output_hashes": {
            str(
                PROBABILITY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                PROBABILITY_PATH
            ),
            str(
                BOOK_SUMMARY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                BOOK_SUMMARY_PATH
            ),
            str(
                INTEGRITY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                INTEGRITY_PATH
            ),
        },
        "next_stage": (
            "development-only uniform probability mixing selection"
        ),
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 88)
    print(" LOCKED EVENT PROBABILITY CONSTRUCTION COMPLETE")
    print("=" * 88)
    print()
    print(
        "Selected event-book source:",
        manifest[
            "event_book_source"
        ],
    )
    print(
        "Selected model:",
        manifest[
            "selected_model"
        ],
    )
    print(
        "Selected family:",
        manifest[
            "selected_family"
        ],
    )
    print(
        "Locked dispersion scale:",
        manifest[
            "selected_dispersion_scale"
        ],
    )
    print()
    print(
        "Prediction rows:",
        manifest[
            "prediction_rows"
        ],
    )
    print(
        "Prediction dates:",
        manifest[
            "prediction_dates"
        ],
    )
    print(
        "Events per prediction:",
        manifest[
            "event_count_per_prediction"
        ],
    )
    print(
        "Probability rows:",
        manifest[
            "probability_rows"
        ],
    )
    print(
        "Quantile particles:",
        manifest[
            "quantile_particle_count"
        ],
    )
    print(
        "Probability resolution:",
        manifest[
            "probability_resolution"
        ],
    )
    print()
    print(
        "Probability books sum to one:",
        manifest[
            "probability_books_sum_to_one"
        ],
    )
    print(
        "All particles assigned exactly once:",
        manifest[
            "all_particles_assigned_exactly_once"
        ],
    )
    print(
        "Zero probabilities retained:",
        manifest[
            "zero_probabilities_retained"
        ],
    )
    print(
        "Zero-probability event share:",
        manifest[
            "zero_probability_event_share"
        ],
    )
    print(
        "Mean occupied events per book:",
        manifest[
            "mean_occupied_events_per_probability_book"
        ],
    )
    print(
        "Mean probability entropy:",
        manifest[
            "mean_probability_entropy"
        ],
    )
    print()
    print(
        "Probability regularisation applied:",
        manifest[
            "probability_regularisation_applied"
        ],
    )
    print(
        "Realised outcomes accessed:",
        manifest[
            "realised_outcomes_accessed"
        ],
    )
    print(
        "Categorical scores calculated:",
        manifest[
            "categorical_scores_calculated"
        ],
    )
    print(
        "Market prices accessed:",
        manifest[
            "market_prices_accessed"
        ],
    )
    print(
        "Trading returns calculated:",
        manifest[
            "trading_returns_calculated"
        ],
    )
    print()
    print(
        "Next stage: select uniform probability mixing using "
        "development OOF predictions only, then apply the locked "
        "mixing weight to holdout and external probabilities."
    )


if __name__ == "__main__":
    main()
