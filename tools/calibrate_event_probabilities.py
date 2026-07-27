#!/usr/bin/env python3
"""Select and lock uniform mixing for the eleven-event probabilities."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = ROOT / "config/probability_regularisation_spec.yaml"
MODEL_MANIFEST_PATH = ROOT / "data/manifests/04_model_selection_manifest.json"
CONTINUOUS_MANIFEST_PATH = (
    ROOT / "data/manifests/05_continuous_calibration_manifest.json"
)
EVENT_MANIFEST_PATH = ROOT / "data/manifests/08_event_probability_manifest.json"

CHRONOLOGY_PATH = ROOT / "data/processed/02_chronological_design_panel.csv"
EVENT_BOOK_PATH = ROOT / "data/processed/certified_event_books.csv"

DEVELOPMENT_PREDICTION_PATH = (
    ROOT / "outputs/diagnostics/05_selected_oof_calibrated_predictions.csv"
)

LOCKED_RAW_PROBABILITY_PATH = (
    ROOT / "outputs/diagnostics/08_locked_event_probability_panel.csv"
)

DEVELOPMENT_RAW_OUTPUT = (
    ROOT / "outputs/diagnostics/09_development_raw_event_probability_panel.csv"
)

DEVELOPMENT_REGULARISED_OUTPUT = (
    ROOT
    / "outputs/diagnostics/"
    "09_development_regularised_event_probability_panel.csv"
)

DATE_SCORE_OUTPUT = (
    ROOT / "outputs/diagnostics/09_probability_mixing_date_scores.csv"
)

GRID_SCORE_OUTPUT = (
    ROOT / "outputs/diagnostics/09_probability_mixing_grid_scores.csv"
)

LOCKED_REGULARISED_OUTPUT = (
    ROOT
    / "outputs/diagnostics/"
    "09_locked_regularised_event_probability_panel.csv"
)

INTEGRITY_OUTPUT = (
    ROOT
    / "outputs/diagnostics/"
    "09_probability_calibration_integrity_checks.csv"
)

SELECTION_OUTPUT = (
    ROOT / "outputs/final_tables/09_probability_mixing_selection.csv"
)

MANIFEST_OUTPUT = (
    ROOT / "data/manifests/09_probability_calibration_manifest.json"
)

QUANTILE_COLUMNS = [
    f"q_{index:02d}"
    for index in range(1, 100)
]


def read_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def boolean_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "yes",
                "y",
            }
        )
    )


def validate_locked_lineage() -> tuple[dict, dict, dict]:
    model_manifest = read_json(
        MODEL_MANIFEST_PATH
    )

    continuous_manifest = read_json(
        CONTINUOUS_MANIFEST_PATH
    )

    event_manifest = read_json(
        EVENT_MANIFEST_PATH
    )

    if not model_manifest["selection_locked"]:
        raise RuntimeError(
            "Notebook 04 model selection is not locked."
        )

    if model_manifest["selected_model"] != "pooled_empirical_residual":
        raise RuntimeError(
            "Unexpected selected probabilistic model."
        )

    if model_manifest["selected_family"] != "empirical_residual":
        raise RuntimeError(
            "Unexpected selected probabilistic family."
        )

    if not continuous_manifest["calibration_locked"]:
        raise RuntimeError(
            "Notebook 05 continuous calibration is not locked."
        )

    if not math.isclose(
        float(
            continuous_manifest["selected_scale"]
        ),
        1.25,
        abs_tol=1.0e-12,
    ):
        raise RuntimeError(
            "Unexpected continuous dispersion scale."
        )

    if event_manifest["selected_model"] != "pooled_empirical_residual":
        raise RuntimeError(
            "Notebook 08 model lineage is inconsistent."
        )

    if not event_manifest["probability_construction_locked"]:
        raise RuntimeError(
            "Notebook 08 probability construction is not locked."
        )

    if event_manifest["probability_regularisation_applied"]:
        raise RuntimeError(
            "Notebook 08 unexpectedly applied probability regularisation."
        )

    if event_manifest["categorical_scores_calculated"]:
        raise RuntimeError(
            "Notebook 08 unexpectedly calculated categorical scores."
        )

    if event_manifest["realised_outcomes_accessed"]:
        raise RuntimeError(
            "Notebook 08 unexpectedly accessed evaluation outcomes."
        )

    if event_manifest["market_prices_accessed"]:
        raise RuntimeError(
            "Notebook 08 unexpectedly accessed market prices."
        )

    return (
        model_manifest,
        continuous_manifest,
        event_manifest,
    )


def load_development_predictions() -> pd.DataFrame:
    frame = pd.read_csv(
        DEVELOPMENT_PREDICTION_PATH,
        low_memory=False,
    )

    required_columns = {
        "row_id",
        "target_date",
        "decision_rule",
        "development_fold",
        "chronology_block",
        "candidate_model",
        "forecast_daily_max_c",
        "hko_daily_max_c",
        "dispersion_scale",
        *QUANTILE_COLUMNS,
    }

    missing = required_columns - set(
        frame.columns
    )

    if missing:
        raise RuntimeError(
            "Development prediction source is missing columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    if len(frame) != 152:
        raise RuntimeError(
            f"Expected 152 development predictions; found {len(frame)}."
        )

    frame["target_date"] = pd.to_datetime(
        frame["target_date"],
        errors="raise",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    if frame["target_date"].nunique() != 38:
        raise RuntimeError(
            "Expected 38 development dates."
        )

    if frame["row_id"].nunique() != 152:
        raise RuntimeError(
            "Development row identifiers are not unique."
        )

    if frame[
        [
            "target_date",
            "decision_rule",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "Development date-rule keys are duplicated."
        )

    if not frame["chronology_block"].eq(
        "development_validation"
    ).all():
        raise RuntimeError(
            "The OOF source contains non-development rows."
        )

    if not frame["candidate_model"].eq(
        "pooled_empirical_residual"
    ).all():
        raise RuntimeError(
            "The OOF source contains another model."
        )

    if not np.allclose(
        frame["dispersion_scale"].to_numpy(
            dtype=float
        ),
        1.25,
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise RuntimeError(
            "The OOF source does not use the locked scale 1.25."
        )

    quantiles = frame[
        QUANTILE_COLUMNS
    ].apply(
        pd.to_numeric,
        errors="coerce",
    ).to_numpy(
        dtype=float
    )

    if not np.isfinite(
        quantiles
    ).all():
        raise RuntimeError(
            "Development quantiles contain non-finite values."
        )

    if (
        np.diff(
            quantiles,
            axis=1,
        )
        < -1.0e-10
    ).any():
        raise RuntimeError(
            "Development quantiles cross."
        )

    return frame.sort_values(
        [
            "target_date",
            "decision_rule",
        ]
    ).reset_index(
        drop=True
    )


def verify_development_chronology(
    predictions: pd.DataFrame,
) -> None:
    chronology = pd.read_csv(
        CHRONOLOGY_PATH,
        low_memory=False,
    )

    development = chronology.loc[
        chronology["chronology_block"].eq(
            "development_validation"
        ),
        [
            "target_date",
            "decision_rule",
            "development_fold",
            "hko_daily_max_c",
        ],
    ].copy()

    development["target_date"] = pd.to_datetime(
        development["target_date"],
        errors="raise",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    development = development.drop_duplicates(
        [
            "target_date",
            "decision_rule",
        ]
    )

    if len(development) != 152:
        raise RuntimeError(
            "The chronology does not contain 152 development date-rule rows."
        )

    comparison = predictions.merge(
        development,
        on=[
            "target_date",
            "decision_rule",
        ],
        how="outer",
        suffixes=(
            "_prediction",
            "_chronology",
        ),
        indicator=True,
    )

    if not comparison["_merge"].eq(
        "both"
    ).all():
        raise RuntimeError(
            "Development predictions and chronology do not have identical keys."
        )

    if not np.allclose(
        comparison[
            "hko_daily_max_c_prediction"
        ].to_numpy(
            dtype=float
        ),
        comparison[
            "hko_daily_max_c_chronology"
        ].to_numpy(
            dtype=float
        ),
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Development outcomes disagree with the chronology."
        )


def load_development_event_books(
    development_dates: set[str],
) -> pd.DataFrame:
    events = pd.read_csv(
        EVENT_BOOK_PATH,
        low_memory=False,
    )

    required_columns = {
        "event_date",
        "event_id",
        "event_index",
        "event_label",
        "lower_bound_c",
        "upper_bound_c",
        "lower_closed",
        "upper_closed",
        "realised_yes",
        "certification_status",
    }

    missing = required_columns - set(
        events.columns
    )

    if missing:
        raise RuntimeError(
            "Certified event-book source is missing columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    events["target_date"] = pd.to_datetime(
        events["event_date"],
        errors="raise",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    events = events.loc[
        events["target_date"].isin(
            development_dates
        )
    ].copy()

    if events["target_date"].nunique() != 38:
        raise RuntimeError(
            "The certified source does not contain all 38 development dates."
        )

    if len(events) != 418:
        raise RuntimeError(
            f"Expected 418 development event rows; found {len(events)}."
        )

    counts = events.groupby(
        "target_date"
    ).size()

    if not counts.eq(
        11
    ).all():
        raise RuntimeError(
            "Each development date must contain exactly eleven events."
        )

    events["realised_yes_bool"] = boolean_series(
        events["realised_yes"]
    )

    realised_counts = events.groupby(
        "target_date"
    )[
        "realised_yes_bool"
    ].sum()

    if not realised_counts.eq(
        1
    ).all():
        raise RuntimeError(
            "Each development date must have exactly one realised event."
        )

    if events[
        [
            "target_date",
            "event_index",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "Certified event indices are duplicated within dates."
        )

    return events.sort_values(
        [
            "target_date",
            "event_index",
        ]
    ).reset_index(
        drop=True
    )


def construct_development_probability_panel(
    predictions: pd.DataFrame,
    events: pd.DataFrame,
) -> pd.DataFrame:
    books = {
        target_date: book.sort_values(
            "event_index"
        ).reset_index(
            drop=True
        )
        for target_date, book in events.groupby(
            "target_date",
            sort=True,
        )
    }

    rows: list[dict] = []

    for prediction in predictions.itertuples(
        index=False
    ):
        target_date = str(
            prediction.target_date
        )

        particles = np.array(
            [
                float(
                    getattr(
                        prediction,
                        quantile_column,
                    )
                )
                for quantile_column in QUANTILE_COLUMNS
            ],
            dtype=float,
        )

        book = books[
            target_date
        ]

        raw_lower = pd.to_numeric(
            book["lower_bound_c"],
            errors="coerce",
        ).to_numpy(
            dtype=float
        )

        raw_upper = pd.to_numeric(
            book["upper_bound_c"],
            errors="coerce",
        ).to_numpy(
            dtype=float
        )

        lower = np.where(
            np.isnan(
                raw_lower
            ),
            -np.inf,
            raw_lower,
        )

        upper = np.where(
            np.isnan(
                raw_upper
            ),
            np.inf,
            raw_upper,
        )

        lower_closed = boolean_series(
            book["lower_closed"]
        ).to_numpy(
            dtype=bool
        )

        upper_closed = boolean_series(
            book["upper_closed"]
        ).to_numpy(
            dtype=bool
        )

        lower_membership = np.where(
            lower_closed.reshape(
                1,
                -1,
            ),
            particles.reshape(
                -1,
                1,
            )
            >= lower.reshape(
                1,
                -1,
            ),
            particles.reshape(
                -1,
                1,
            )
            > lower.reshape(
                1,
                -1,
            ),
        )

        upper_membership = np.where(
            upper_closed.reshape(
                1,
                -1,
            ),
            particles.reshape(
                -1,
                1,
            )
            <= upper.reshape(
                1,
                -1,
            ),
            particles.reshape(
                -1,
                1,
            )
            < upper.reshape(
                1,
                -1,
            ),
        )

        membership = (
            lower_membership
            & upper_membership
        )

        particle_assignments = membership.sum(
            axis=1
        )

        if not (
            particle_assignments
            == 1
        ).all():
            raise RuntimeError(
                "A quantile particle was assigned to zero or multiple events "
                f"for row {prediction.row_id}."
            )

        particle_counts = membership.sum(
            axis=0
        ).astype(
            int
        )

        if int(
            particle_counts.sum()
        ) != 99:
            raise RuntimeError(
                f"Particle count does not equal 99 for row {prediction.row_id}."
            )

        for event_position, event in book.iterrows():
            rows.append(
                {
                    "row_id": prediction.row_id,
                    "target_date": target_date,
                    "decision_rule": prediction.decision_rule,
                    "development_fold": prediction.development_fold,
                    "chronology_block": prediction.chronology_block,
                    "selected_model": prediction.candidate_model,
                    "selected_family": "empirical_residual",
                    "dispersion_scale": float(
                        prediction.dispersion_scale
                    ),
                    "event_id": event["event_id"],
                    "event_index": int(
                        event["event_index"]
                    ),
                    "event_label": event["event_label"],
                    "lower_bound_c": event["lower_bound_c"],
                    "upper_bound_c": event["upper_bound_c"],
                    "lower_closed": bool(
                        lower_closed[
                            event_position
                        ]
                    ),
                    "upper_closed": bool(
                        upper_closed[
                            event_position
                        ]
                    ),
                    "quantile_particle_count": int(
                        particle_counts[
                            event_position
                        ]
                    ),
                    "quantile_particle_total": 99,
                    "raw_event_probability": float(
                        particle_counts[
                            event_position
                        ]
                        / 99.0
                    ),
                    "realised_yes": bool(
                        event[
                            "realised_yes_bool"
                        ]
                    ),
                }
            )

    panel = pd.DataFrame(
        rows
    )

    if len(panel) != 1672:
        raise RuntimeError(
            f"Expected 1,672 development probability rows; found {len(panel)}."
        )

    if panel["row_id"].nunique() != 152:
        raise RuntimeError(
            "Expected 152 development probability books."
        )

    probability_sums = panel.groupby(
        "row_id"
    )[
        "raw_event_probability"
    ].sum()

    if not np.allclose(
        probability_sums.to_numpy(
            dtype=float
        ),
        1.0,
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Development probability books do not sum to one."
        )

    realised_counts = panel.groupby(
        "row_id"
    )[
        "realised_yes"
    ].sum()

    if not realised_counts.eq(
        1
    ).all():
        raise RuntimeError(
            "Each development forecast must have one realised event."
        )

    return panel.sort_values(
        [
            "target_date",
            "decision_rule",
            "event_index",
        ]
    ).reset_index(
        drop=True
    )


def select_uniform_mixing(
    panel: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    float,
    float,
    float,
]:
    probability_matrix = panel.pivot(
        index="row_id",
        columns="event_index",
        values="raw_event_probability",
    ).sort_index(
        axis=1
    )

    outcome_matrix = panel.pivot(
        index="row_id",
        columns="event_index",
        values="realised_yes",
    ).sort_index(
        axis=1
    ).astype(
        float
    )

    if list(
        probability_matrix.columns
    ) != list(
        outcome_matrix.columns
    ):
        raise RuntimeError(
            "Probability and outcome event indices do not agree."
        )

    metadata = (
        panel[
            [
                "row_id",
                "target_date",
                "decision_rule",
            ]
        ]
        .drop_duplicates()
        .set_index(
            "row_id"
        )
        .loc[
            probability_matrix.index
        ]
    )

    probabilities = probability_matrix.to_numpy(
        dtype=float
    )

    outcomes = outcome_matrix.to_numpy(
        dtype=float
    )

    date_score_frames: list[pd.DataFrame] = []
    grid_rows: list[dict] = []

    lambda_grid = np.round(
        np.linspace(
            0.0,
            1.0,
            101,
        ),
        2,
    )

    for mixing_lambda in lambda_grid:
        mixed = (
            (
                1.0
                - mixing_lambda
            )
            * probabilities
            + mixing_lambda
            / 11.0
        )

        realised_probability = (
            mixed
            * outcomes
        ).sum(
            axis=1
        )

        with np.errstate(
            divide="ignore",
            invalid="ignore",
        ):
            log_scores = -np.log(
                realised_probability
            )

        brier_scores = (
            (
                mixed
                - outcomes
            )
            ** 2
        ).sum(
            axis=1
        )

        row_scores = metadata.reset_index().copy()

        row_scores["mixing_lambda"] = float(
            mixing_lambda
        )

        row_scores["categorical_log_score"] = log_scores
        row_scores["multiclass_brier_score"] = brier_scores

        date_scores = (
            row_scores.groupby(
                "target_date",
                as_index=False,
            )
            .agg(
                decision_rule_count=(
                    "decision_rule",
                    "nunique",
                ),
                date_mean_log_score=(
                    "categorical_log_score",
                    "mean",
                ),
                date_mean_brier_score=(
                    "multiclass_brier_score",
                    "mean",
                ),
            )
        )

        if len(date_scores) != 38:
            raise RuntimeError(
                "Expected 38 date-level development score observations."
            )

        if not date_scores[
            "decision_rule_count"
        ].eq(
            4
        ).all():
            raise RuntimeError(
                "Every development date must contain four decision rules."
            )

        date_scores.insert(
            0,
            "mixing_lambda",
            float(
                mixing_lambda
            ),
        )

        date_score_frames.append(
            date_scores
        )

        date_log = date_scores[
            "date_mean_log_score"
        ].to_numpy(
            dtype=float
        )

        date_brier = date_scores[
            "date_mean_brier_score"
        ].to_numpy(
            dtype=float
        )

        finite_log = bool(
            np.isfinite(
                date_log
            ).all()
        )

        grid_rows.append(
            {
                "mixing_lambda": float(
                    mixing_lambda
                ),
                "settlement_dates": 38,
                "date_rule_rows": 152,
                "mean_date_log_score": (
                    float(
                        date_log.mean()
                    )
                    if finite_log
                    else np.inf
                ),
                "standard_error_date_log_score": (
                    float(
                        date_log.std(
                            ddof=1
                        )
                        / math.sqrt(
                            len(
                                date_log
                            )
                        )
                    )
                    if finite_log
                    else np.inf
                ),
                "mean_date_brier_score": float(
                    date_brier.mean()
                ),
                "standard_error_date_brier_score": float(
                    date_brier.std(
                        ddof=1
                    )
                    / math.sqrt(
                        len(
                            date_brier
                        )
                    )
                ),
                "zero_realised_probability_rows": int(
                    (
                        realised_probability
                        == 0.0
                    ).sum()
                ),
                "minimum_event_probability": float(
                    mixed.min()
                ),
                "maximum_event_probability": float(
                    mixed.max()
                ),
            }
        )

    date_score_panel = pd.concat(
        date_score_frames,
        ignore_index=True,
    )

    grid_scores = pd.DataFrame(
        grid_rows
    ).sort_values(
        "mixing_lambda"
    ).reset_index(
        drop=True
    )

    finite_candidates = grid_scores.loc[
        np.isfinite(
            grid_scores[
                "mean_date_log_score"
            ]
        )
    ].copy()

    if finite_candidates.empty:
        raise RuntimeError(
            "No finite probability-mixing candidate was found."
        )

    best_row = finite_candidates.sort_values(
        [
            "mean_date_log_score",
            "mean_date_brier_score",
            "mixing_lambda",
        ]
    ).iloc[
        0
    ]

    best_lambda = float(
        best_row[
            "mixing_lambda"
        ]
    )

    best_mean_log_score = float(
        best_row[
            "mean_date_log_score"
        ]
    )

    best_standard_error = float(
        best_row[
            "standard_error_date_log_score"
        ]
    )

    one_standard_error_threshold = (
        best_mean_log_score
        + best_standard_error
    )

    eligible = finite_candidates.loc[
        finite_candidates[
            "mean_date_log_score"
        ]
        <= (
            one_standard_error_threshold
            + 1.0e-12
        )
    ].copy()

    selected_lambda = float(
        eligible[
            "mixing_lambda"
        ].min()
    )

    grid_scores["strict_log_score_winner"] = np.isclose(
        grid_scores["mixing_lambda"],
        best_lambda,
        atol=1.0e-12,
    )

    grid_scores["within_one_standard_error"] = (
        np.isfinite(
            grid_scores[
                "mean_date_log_score"
            ]
        )
        & (
            grid_scores[
                "mean_date_log_score"
            ]
            <= (
                one_standard_error_threshold
                + 1.0e-12
            )
        )
    )

    grid_scores["selected_lambda"] = np.isclose(
        grid_scores["mixing_lambda"],
        selected_lambda,
        atol=1.0e-12,
    )

    regularised_panel = panel.copy()

    regularised_panel["uniform_mixing_lambda"] = (
        selected_lambda
    )

    regularised_panel["regularised_event_probability"] = (
        (
            1.0
            - selected_lambda
        )
        * regularised_panel[
            "raw_event_probability"
        ]
        + selected_lambda
        / 11.0
    )

    regularised_panel["probability_regularised"] = (
        selected_lambda > 0.0
    )

    return (
        date_score_panel,
        grid_scores,
        regularised_panel,
        selected_lambda,
        best_lambda,
        one_standard_error_threshold,
    )


def apply_locked_lambda(
    selected_lambda: float,
) -> pd.DataFrame:
    locked = pd.read_csv(
        LOCKED_RAW_PROBABILITY_PATH,
        low_memory=False,
    )

    required_columns = {
        "row_id",
        "target_date",
        "decision_rule",
        "chronology_block",
        "selected_model",
        "selected_family",
        "dispersion_scale",
        "event_id",
        "event_order",
        "raw_event_probability",
        "probability_regularised",
        "market_price_accessed",
        "outcome_accessed",
        "score_calculated",
    }

    missing = required_columns - set(
        locked.columns
    )

    if missing:
        raise RuntimeError(
            "Locked Notebook 08 source is missing columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    locked["target_date"] = pd.to_datetime(
        locked["target_date"],
        errors="raise",
    ).dt.strftime(
        "%Y-%m-%d"
    )

    if len(locked) != 1749:
        raise RuntimeError(
            f"Expected 1,749 locked probability rows; found {len(locked)}."
        )

    if locked["row_id"].nunique() != 159:
        raise RuntimeError(
            "Expected 159 locked probability books."
        )

    if locked["target_date"].nunique() != 40:
        raise RuntimeError(
            "Expected 40 locked evaluation dates."
        )

    if set(
        locked["chronology_block"].unique()
    ) != {
        "holdout",
        "external_test",
    }:
        raise RuntimeError(
            "Locked probabilities contain an unexpected chronology block."
        )

    if boolean_series(
        locked["probability_regularised"]
    ).any():
        raise RuntimeError(
            "Notebook 08 probabilities were already regularised."
        )

    if boolean_series(
        locked["market_price_accessed"]
    ).any():
        raise RuntimeError(
            "Notebook 08 probability construction accessed market prices."
        )

    if boolean_series(
        locked["outcome_accessed"]
    ).any():
        raise RuntimeError(
            "Notebook 08 probability construction accessed outcomes."
        )

    if boolean_series(
        locked["score_calculated"]
    ).any():
        raise RuntimeError(
            "Notebook 08 probability construction calculated scores."
        )

    locked["uniform_mixing_lambda"] = selected_lambda

    locked["regularised_event_probability"] = (
        (
            1.0
            - selected_lambda
        )
        * pd.to_numeric(
            locked[
                "raw_event_probability"
            ],
            errors="raise",
        )
        + selected_lambda
        / 11.0
    )

    locked["probability_regularised"] = (
        selected_lambda > 0.0
    )

    locked["probability_calibration_locked"] = True
    locked["outcome_accessed"] = False
    locked["score_calculated"] = False
    locked["market_price_accessed"] = False
    locked["trading_returns_calculated"] = False

    probability_sums = locked.groupby(
        "row_id"
    )[
        "regularised_event_probability"
    ].sum()

    if not np.allclose(
        probability_sums.to_numpy(
            dtype=float
        ),
        1.0,
        atol=1.0e-12,
        rtol=0.0,
    ):
        raise RuntimeError(
            "Locked regularised probability books do not sum to one."
        )

    return locked.sort_values(
        [
            "target_date",
            "decision_rule",
            "event_order",
        ]
    ).reset_index(
        drop=True
    )


def main() -> None:
    yaml.safe_load(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    (
        model_manifest,
        continuous_manifest,
        event_manifest,
    ) = validate_locked_lineage()

    predictions = load_development_predictions()

    verify_development_chronology(
        predictions
    )

    development_dates = set(
        predictions[
            "target_date"
        ]
    )

    development_events = load_development_event_books(
        development_dates
    )

    development_raw = construct_development_probability_panel(
        predictions,
        development_events,
    )

    (
        date_scores,
        grid_scores,
        development_regularised,
        selected_lambda,
        strict_winner_lambda,
        one_standard_error_threshold,
    ) = select_uniform_mixing(
        development_raw
    )

    locked_regularised = apply_locked_lambda(
        selected_lambda
    )

    selected_row = grid_scores.loc[
        grid_scores[
            "selected_lambda"
        ]
    ].copy()

    if len(
        selected_row
    ) != 1:
        raise RuntimeError(
            "Exactly one uniform mixing weight must be selected."
        )

    selected_row[
        "strict_winner_lambda"
    ] = strict_winner_lambda

    selected_row[
        "one_standard_error_threshold"
    ] = one_standard_error_threshold

    selected_row[
        "selection_rule"
    ] = (
        "smallest lambda within one standard error "
        "of the best settlement-date mean log score"
    )

    selected_row[
        "uncertainty_unit"
    ] = "settlement_date"

    selected_row[
        "development_source"
    ] = str(
        DEVELOPMENT_PREDICTION_PATH.relative_to(
            ROOT
        )
    )

    development_sums = development_regularised.groupby(
        "row_id"
    )[
        "regularised_event_probability"
    ].sum()

    locked_sums = locked_regularised.groupby(
        "row_id"
    )[
        "regularised_event_probability"
    ].sum()

    integrity_checks = pd.DataFrame(
        [
            {
                "check": "model_selection_locked",
                "passed": model_manifest[
                    "selection_locked"
                ],
                "value": model_manifest[
                    "selected_model"
                ],
            },
            {
                "check": "continuous_calibration_locked",
                "passed": continuous_manifest[
                    "calibration_locked"
                ],
                "value": continuous_manifest[
                    "selected_scale"
                ],
            },
            {
                "check": "event_probability_construction_locked",
                "passed": event_manifest[
                    "probability_construction_locked"
                ],
                "value": event_manifest[
                    "status"
                ],
            },
            {
                "check": "development_dates_equal_38",
                "passed": predictions[
                    "target_date"
                ].nunique()
                == 38,
                "value": predictions[
                    "target_date"
                ].nunique(),
            },
            {
                "check": "development_forecasts_equal_152",
                "passed": len(
                    predictions
                )
                == 152,
                "value": len(
                    predictions
                ),
            },
            {
                "check": "development_probability_rows_equal_1672",
                "passed": len(
                    development_regularised
                )
                == 1672,
                "value": len(
                    development_regularised
                ),
            },
            {
                "check": "candidate_lambda_count_equal_101",
                "passed": len(
                    grid_scores
                )
                == 101,
                "value": len(
                    grid_scores
                ),
            },
            {
                "check": "selected_lambda_in_unit_interval",
                "passed": 0.0
                <= selected_lambda
                <= 1.0,
                "value": selected_lambda,
            },
            {
                "check": "selected_lambda_is_smallest_one_se_candidate",
                "passed": math.isclose(
                    selected_lambda,
                    float(
                        grid_scores.loc[
                            grid_scores[
                                "within_one_standard_error"
                            ],
                            "mixing_lambda",
                        ].min()
                    ),
                    abs_tol=1.0e-12,
                ),
                "value": selected_lambda,
            },
            {
                "check": "development_books_sum_to_one",
                "passed": bool(
                    np.allclose(
                        development_sums.to_numpy(
                            dtype=float
                        ),
                        1.0,
                        atol=1.0e-12,
                        rtol=0.0,
                    )
                ),
                "value": float(
                    (
                        development_sums
                        - 1.0
                    ).abs().max()
                ),
            },
            {
                "check": "locked_prediction_books_equal_159",
                "passed": locked_regularised[
                    "row_id"
                ].nunique()
                == 159,
                "value": locked_regularised[
                    "row_id"
                ].nunique(),
            },
            {
                "check": "locked_probability_rows_equal_1749",
                "passed": len(
                    locked_regularised
                )
                == 1749,
                "value": len(
                    locked_regularised
                ),
            },
            {
                "check": "locked_dates_equal_40",
                "passed": locked_regularised[
                    "target_date"
                ].nunique()
                == 40,
                "value": locked_regularised[
                    "target_date"
                ].nunique(),
            },
            {
                "check": "locked_books_sum_to_one",
                "passed": bool(
                    np.allclose(
                        locked_sums.to_numpy(
                            dtype=float
                        ),
                        1.0,
                        atol=1.0e-12,
                        rtol=0.0,
                    )
                ),
                "value": float(
                    (
                        locked_sums
                        - 1.0
                    ).abs().max()
                ),
            },
            {
                "check": "holdout_and_external_outcomes_not_accessed",
                "passed": not boolean_series(
                    locked_regularised[
                        "outcome_accessed"
                    ]
                ).any(),
                "value": False,
            },
            {
                "check": "holdout_and_external_scores_not_calculated",
                "passed": not boolean_series(
                    locked_regularised[
                        "score_calculated"
                    ]
                ).any(),
                "value": False,
            },
            {
                "check": "market_prices_not_accessed",
                "passed": not boolean_series(
                    locked_regularised[
                        "market_price_accessed"
                    ]
                ).any(),
                "value": False,
            },
            {
                "check": "trading_returns_not_calculated",
                "passed": not boolean_series(
                    locked_regularised[
                        "trading_returns_calculated"
                    ]
                ).any(),
                "value": False,
            },
        ]
    )

    if not integrity_checks[
        "passed"
    ].astype(
        bool
    ).all():
        failures = integrity_checks.loc[
            ~integrity_checks[
                "passed"
            ].astype(
                bool
            )
        ]

        raise RuntimeError(
            "Notebook 09 integrity checks failed:\n"
            + failures.to_string(
                index=False
            )
        )

    for output_path in (
        DEVELOPMENT_RAW_OUTPUT,
        DEVELOPMENT_REGULARISED_OUTPUT,
        DATE_SCORE_OUTPUT,
        GRID_SCORE_OUTPUT,
        LOCKED_REGULARISED_OUTPUT,
        INTEGRITY_OUTPUT,
        SELECTION_OUTPUT,
        MANIFEST_OUTPUT,
    ):
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    development_raw.to_csv(
        DEVELOPMENT_RAW_OUTPUT,
        index=False,
    )

    development_regularised.to_csv(
        DEVELOPMENT_REGULARISED_OUTPUT,
        index=False,
    )

    date_scores.to_csv(
        DATE_SCORE_OUTPUT,
        index=False,
    )

    grid_scores.to_csv(
        GRID_SCORE_OUTPUT,
        index=False,
    )

    locked_regularised.to_csv(
        LOCKED_REGULARISED_OUTPUT,
        index=False,
    )

    integrity_checks.to_csv(
        INTEGRITY_OUTPUT,
        index=False,
    )

    selected_row.to_csv(
        SELECTION_OUTPUT,
        index=False,
    )

    selected_metrics = selected_row.iloc[
        0
    ]

    strict_metrics = grid_scores.loc[
        grid_scores[
            "strict_log_score_winner"
        ]
    ].iloc[
        0
    ]

    manifest = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "PROBABILITY_CALIBRATION_LOCKED",
        "probability_calibration_locked": True,
        "selected_model": "pooled_empirical_residual",
        "selected_family": "empirical_residual",
        "locked_continuous_dispersion_scale": 1.25,
        "development_source": str(
            DEVELOPMENT_PREDICTION_PATH.relative_to(
                ROOT
            )
        ),
        "development_source_is_calibrated_oof": True,
        "uncalibrated_notebook04_source_used": False,
        "development_dates": 38,
        "development_date_rule_rows": 152,
        "development_probability_rows": 1672,
        "uncertainty_unit": "settlement_date",
        "decision_rules_aggregated_within_date": True,
        "candidate_lambda_count": 101,
        "candidate_lambda_minimum": 0.0,
        "candidate_lambda_maximum": 1.0,
        "candidate_lambda_increment": 0.01,
        "primary_selection_score": (
            "settlement-date mean categorical log score"
        ),
        "secondary_selection_score": (
            "settlement-date mean multiclass Brier score"
        ),
        "selection_rule": (
            "smallest lambda within one standard error "
            "of the best settlement-date mean log score"
        ),
        "strict_winner_lambda": float(
            strict_winner_lambda
        ),
        "strict_winner_mean_date_log_score": float(
            strict_metrics[
                "mean_date_log_score"
            ]
        ),
        "strict_winner_standard_error": float(
            strict_metrics[
                "standard_error_date_log_score"
            ]
        ),
        "one_standard_error_threshold": float(
            one_standard_error_threshold
        ),
        "selected_uniform_mixing_lambda": float(
            selected_lambda
        ),
        "selected_mean_date_log_score": float(
            selected_metrics[
                "mean_date_log_score"
            ]
        ),
        "selected_mean_date_brier_score": float(
            selected_metrics[
                "mean_date_brier_score"
            ]
        ),
        "locked_prediction_books": 159,
        "locked_probability_rows": 1749,
        "locked_dates": 40,
        "locked_blocks": [
            "holdout",
            "external_test",
        ],
        "model_refitted": False,
        "model_reselected": False,
        "continuous_calibration_reselected": False,
        "holdout_outcomes_used_for_selection": False,
        "external_test_outcomes_used_for_selection": False,
        "holdout_scores_calculated": False,
        "external_test_scores_calculated": False,
        "market_prices_accessed": False,
        "trading_returns_calculated": False,
        "input_hashes": {
            str(
                CONFIG_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CONFIG_PATH
            ),
            str(
                MODEL_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                MODEL_MANIFEST_PATH
            ),
            str(
                CONTINUOUS_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CONTINUOUS_MANIFEST_PATH
            ),
            str(
                EVENT_MANIFEST_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                EVENT_MANIFEST_PATH
            ),
            str(
                CHRONOLOGY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                CHRONOLOGY_PATH
            ),
            str(
                EVENT_BOOK_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                EVENT_BOOK_PATH
            ),
            str(
                DEVELOPMENT_PREDICTION_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                DEVELOPMENT_PREDICTION_PATH
            ),
            str(
                LOCKED_RAW_PROBABILITY_PATH.relative_to(
                    ROOT
                )
            ): sha256_file(
                LOCKED_RAW_PROBABILITY_PATH
            ),
        },
        "output_hashes": {
            str(
                GRID_SCORE_OUTPUT.relative_to(
                    ROOT
                )
            ): sha256_file(
                GRID_SCORE_OUTPUT
            ),
            str(
                LOCKED_REGULARISED_OUTPUT.relative_to(
                    ROOT
                )
            ): sha256_file(
                LOCKED_REGULARISED_OUTPUT
            ),
            str(
                INTEGRITY_OUTPUT.relative_to(
                    ROOT
                )
            ): sha256_file(
                INTEGRITY_OUTPUT
            ),
        },
        "next_stage": (
            "locked holdout and external categorical evaluation"
        ),
    }

    MANIFEST_OUTPUT.write_text(
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
    print(" NOTEBOOK 09 CORE PROBABILITY CALIBRATION COMPLETE")
    print("=" * 88)
    print()
    print(
        "Status:",
        manifest["status"],
    )
    print(
        "Selected model:",
        manifest["selected_model"],
    )
    print(
        "Locked continuous scale:",
        manifest[
            "locked_continuous_dispersion_scale"
        ],
    )
    print()
    print(
        "Development dates:",
        manifest["development_dates"],
    )
    print(
        "Development date-rule rows:",
        manifest[
            "development_date_rule_rows"
        ],
    )
    print(
        "Development event-probability rows:",
        manifest[
            "development_probability_rows"
        ],
    )
    print(
        "Uncertainty unit:",
        manifest["uncertainty_unit"],
    )
    print()
    print(
        "Strict winner lambda:",
        manifest["strict_winner_lambda"],
    )
    print(
        "Selected one-SE lambda:",
        manifest[
            "selected_uniform_mixing_lambda"
        ],
    )
    print(
        "Selected mean date log score:",
        manifest[
            "selected_mean_date_log_score"
        ],
    )
    print(
        "Selected mean date Brier score:",
        manifest[
            "selected_mean_date_brier_score"
        ],
    )
    print()
    print(
        "Locked probability books:",
        manifest["locked_prediction_books"],
    )
    print(
        "Locked probability rows:",
        manifest["locked_probability_rows"],
    )
    print(
        "Locked dates:",
        manifest["locked_dates"],
    )
    print()
    print(
        "Holdout outcomes used for selection:",
        manifest[
            "holdout_outcomes_used_for_selection"
        ],
    )
    print(
        "June outcomes used for selection:",
        manifest[
            "external_test_outcomes_used_for_selection"
        ],
    )
    print(
        "Holdout scores calculated:",
        manifest[
            "holdout_scores_calculated"
        ],
    )
    print(
        "June scores calculated:",
        manifest[
            "external_test_scores_calculated"
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


if __name__ == "__main__":
    main()
