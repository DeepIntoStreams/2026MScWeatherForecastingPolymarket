#!/usr/bin/env python3
"""Evaluate locked event probabilities against certified HKO outcomes."""

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

SPEC_PATH = ROOT / "config/categorical_evaluation_spec.yaml"
MANIFEST_09_PATH = (
    ROOT / "data/manifests/09_probability_calibration_manifest.json"
)
PROBABILITY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "09_locked_regularised_event_probability_panel.csv"
)
EVENT_BOOK_PATH = ROOT / "data/processed/certified_event_books.csv"

OUTCOME_PANEL_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "10_locked_event_probability_outcome_panel.csv"
)
SCORE_PANEL_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "10_locked_categorical_score_panel.csv"
)
DATE_SCORE_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "10_locked_categorical_date_score_panel.csv"
)
RULE_SUMMARY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "10_locked_categorical_rule_summary.csv"
)
BLOCK_SUMMARY_PATH = (
    ROOT
    / "outputs/final_tables/"
    "10_locked_categorical_block_summary.csv"
)
INTEGRITY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "10_locked_categorical_integrity_checks.csv"
)
MANIFEST_10_PATH = (
    ROOT / "data/manifests/10_categorical_evaluation_manifest.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes", "y"})
    )


def normalise_label(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )


def standard_error(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.loc[np.isfinite(numeric)]

    if len(numeric) <= 1:
        return float("nan")

    return float(numeric.std(ddof=1) / math.sqrt(len(numeric)))


def load_and_join() -> tuple[pd.DataFrame, dict]:
    specification = yaml.safe_load(
        SPEC_PATH.read_text(encoding="utf-8")
    )

    manifest_09 = json.loads(
        MANIFEST_09_PATH.read_text(encoding="utf-8")
    )

    if manifest_09["status"] != "PROBABILITY_CALIBRATION_LOCKED":
        raise RuntimeError("Notebook 09 probability calibration is not locked.")

    if not math.isclose(
        float(manifest_09["selected_uniform_mixing_lambda"]),
        0.01,
        abs_tol=1.0e-12,
    ):
        raise RuntimeError("Unexpected locked uniform mixing parameter.")

    probabilities = pd.read_csv(
        PROBABILITY_PATH,
        low_memory=False,
    )

    events = pd.read_csv(
        EVENT_BOOK_PATH,
        low_memory=False,
    )

    required_probability_columns = {
        "row_id",
        "target_date",
        "decision_rule",
        "chronology_block",
        "event_order",
        "source_event_label",
        "raw_event_probability",
        "regularised_event_probability",
        "selected_model",
        "selected_family",
        "dispersion_scale",
        "uniform_mixing_lambda",
        "market_price_accessed",
    }

    required_event_columns = {
        "event_date",
        "event_index",
        "event_label",
        "realised_yes",
        "hko_daily_max_c",
        "certification_status",
    }

    missing_probability = (
        required_probability_columns - set(probabilities.columns)
    )
    missing_event = required_event_columns - set(events.columns)

    if missing_probability:
        raise RuntimeError(
            "Probability source is missing columns: "
            + ", ".join(sorted(missing_probability))
        )

    if missing_event:
        raise RuntimeError(
            "Outcome source is missing columns: "
            + ", ".join(sorted(missing_event))
        )

    probabilities["target_date"] = pd.to_datetime(
        probabilities["target_date"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    events["target_date"] = pd.to_datetime(
        events["event_date"],
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    evaluation_dates = set(probabilities["target_date"])

    events = events.loc[
        events["target_date"].isin(evaluation_dates)
    ].copy()

    probabilities["_join_label"] = normalise_label(
        probabilities["source_event_label"]
    )
    events["_join_label"] = normalise_label(events["event_label"])

    if events.duplicated(["target_date", "_join_label"]).any():
        raise RuntimeError(
            "Certified outcome labels are duplicated within a date."
        )

    joined = probabilities.merge(
        events[
            [
                "target_date",
                "_join_label",
                "event_index",
                "event_label",
                "realised_yes",
                "hko_daily_max_c",
                "certification_status",
            ]
        ],
        on=["target_date", "_join_label"],
        how="left",
        validate="many_to_one",
        indicator=True,
        suffixes=("_probability", "_certified"),
    )

    if not joined["_merge"].eq("both").all():
        raise RuntimeError("Not all locked probability rows joined to outcomes.")

    event_order = pd.to_numeric(
        joined["event_order"],
        errors="raise",
    )
    event_index = pd.to_numeric(
        joined["event_index"],
        errors="raise",
    )

    if not (event_order.eq(event_index + 1)).all():
        raise RuntimeError(
            "The label join failed the event-order structural verification."
        )

    joined["realised_yes"] = as_bool(joined["realised_yes"])

    if len(joined) != 1749:
        raise RuntimeError(
            f"Expected 1,749 joined rows; found {len(joined)}."
        )

    if joined["row_id"].nunique() != 159:
        raise RuntimeError("Expected 159 probability books.")

    if joined["target_date"].nunique() != 40:
        raise RuntimeError("Expected 40 evaluation dates.")

    event_counts = joined.groupby("row_id").size()
    winner_counts = joined.groupby("row_id")["realised_yes"].sum()

    if not event_counts.eq(11).all():
        raise RuntimeError("Each probability book must contain eleven events.")

    if not winner_counts.eq(1).all():
        raise RuntimeError(
            "Each probability book must contain one realised event."
        )

    for probability_column in (
        "raw_event_probability",
        "regularised_event_probability",
    ):
        values = pd.to_numeric(
            joined[probability_column],
            errors="raise",
        )

        if not np.isfinite(values).all():
            raise RuntimeError(
                f"{probability_column} contains non-finite values."
            )

        if (values < 0.0).any() or (values > 1.0).any():
            raise RuntimeError(
                f"{probability_column} lies outside [0,1]."
            )

        sums = joined.groupby("row_id")[probability_column].sum()

        if not np.allclose(
            sums.to_numpy(dtype=float),
            1.0,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise RuntimeError(
                f"{probability_column} books do not sum to one."
            )

    if not (
        joined["regularised_event_probability"] > 0.0
    ).all():
        raise RuntimeError(
            "Regularised probabilities must be strictly positive."
        )

    if as_bool(joined["market_price_accessed"]).any():
        raise RuntimeError(
            "The locked probability source indicates market-price access."
        )

    return joined, {
        "specification": specification,
        "manifest_09": manifest_09,
    }


def calculate_scores(joined: pd.DataFrame) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    rows: list[dict] = []

    for row_id, book in joined.groupby("row_id", sort=True):
        book = book.sort_values("event_order").copy()

        outcome = book["realised_yes"].to_numpy(dtype=float)
        raw_probability = book[
            "raw_event_probability"
        ].to_numpy(dtype=float)
        regularised_probability = book[
            "regularised_event_probability"
        ].to_numpy(dtype=float)

        realised_position = int(np.argmax(outcome))

        raw_realised_probability = float(
            raw_probability[realised_position]
        )
        regularised_realised_probability = float(
            regularised_probability[realised_position]
        )

        raw_log_score = (
            float(-np.log(raw_realised_probability))
            if raw_realised_probability > 0.0
            else float("inf")
        )

        regularised_log_score = float(
            -np.log(regularised_realised_probability)
        )

        raw_brier_score = float(
            np.sum((raw_probability - outcome) ** 2)
        )
        regularised_brier_score = float(
            np.sum((regularised_probability - outcome) ** 2)
        )

        first = book.iloc[0]
        realised_row = book.iloc[realised_position]

        rows.append(
            {
                "row_id": row_id,
                "target_date": first["target_date"],
                "decision_rule": first["decision_rule"],
                "chronology_block": first["chronology_block"],
                "selected_model": first["selected_model"],
                "selected_family": first["selected_family"],
                "dispersion_scale": float(first["dispersion_scale"]),
                "uniform_mixing_lambda": float(
                    first["uniform_mixing_lambda"]
                ),
                "hko_daily_max_c": float(first["hko_daily_max_c"]),
                "realised_event_index": int(
                    realised_row["event_index"]
                ),
                "realised_event_label": realised_row[
                    "event_label_certified"
                ],
                "raw_realised_probability": (
                    raw_realised_probability
                ),
                "regularised_realised_probability": (
                    regularised_realised_probability
                ),
                "raw_categorical_log_score": raw_log_score,
                "regularised_categorical_log_score": (
                    regularised_log_score
                ),
                "raw_log_score_finite": bool(
                    np.isfinite(raw_log_score)
                ),
                "raw_multiclass_brier_score": raw_brier_score,
                "regularised_multiclass_brier_score": (
                    regularised_brier_score
                ),
                "brier_difference_regularised_minus_raw": (
                    regularised_brier_score - raw_brier_score
                ),
            }
        )

    score_panel = pd.DataFrame(rows).sort_values(
        ["target_date", "decision_rule"]
    ).reset_index(drop=True)

    date_scores = (
        score_panel.groupby(
            ["chronology_block", "target_date"],
            as_index=False,
        )
        .agg(
            decision_rule_count=("decision_rule", "nunique"),
            raw_zero_probability_books=(
                "raw_log_score_finite",
                lambda values: int((~values).sum()),
            ),
            mean_raw_log_score=(
                "raw_categorical_log_score",
                "mean",
            ),
            mean_regularised_log_score=(
                "regularised_categorical_log_score",
                "mean",
            ),
            mean_raw_brier_score=(
                "raw_multiclass_brier_score",
                "mean",
            ),
            mean_regularised_brier_score=(
                "regularised_multiclass_brier_score",
                "mean",
            ),
            mean_brier_difference_regularised_minus_raw=(
                "brier_difference_regularised_minus_raw",
                "mean",
            ),
        )
        .sort_values(["chronology_block", "target_date"])
        .reset_index(drop=True)
    )

    block_rows: list[dict] = []

    for block, frame in date_scores.groupby(
        "chronology_block",
        sort=True,
    ):
        book_frame = score_panel.loc[
            score_panel["chronology_block"].eq(block)
        ]

        block_rows.append(
            {
                "chronology_block": block,
                "dates": int(frame["target_date"].nunique()),
                "probability_books": int(len(book_frame)),
                "decision_rules": int(
                    book_frame["decision_rule"].nunique()
                ),
                "raw_zero_probability_books": int(
                    (~book_frame["raw_log_score_finite"]).sum()
                ),
                "mean_date_regularised_log_score": float(
                    frame["mean_regularised_log_score"].mean()
                ),
                "standard_error_date_regularised_log_score": (
                    standard_error(
                        frame["mean_regularised_log_score"]
                    )
                ),
                "mean_date_raw_brier_score": float(
                    frame["mean_raw_brier_score"].mean()
                ),
                "mean_date_regularised_brier_score": float(
                    frame[
                        "mean_regularised_brier_score"
                    ].mean()
                ),
                "standard_error_date_regularised_brier_score": (
                    standard_error(
                        frame["mean_regularised_brier_score"]
                    )
                ),
                "mean_date_brier_difference_regularised_minus_raw": (
                    float(
                        frame[
                            "mean_brier_difference_regularised_minus_raw"
                        ].mean()
                    )
                ),
                "standard_error_date_brier_difference": (
                    standard_error(
                        frame[
                            "mean_brier_difference_regularised_minus_raw"
                        ]
                    )
                ),
            }
        )

    block_summary = pd.DataFrame(block_rows)

    rule_summary = (
        score_panel.groupby(
            ["chronology_block", "decision_rule"],
            as_index=False,
        )
        .agg(
            dates=("target_date", "nunique"),
            probability_books=("row_id", "size"),
            raw_zero_probability_books=(
                "raw_log_score_finite",
                lambda values: int((~values).sum()),
            ),
            mean_regularised_log_score=(
                "regularised_categorical_log_score",
                "mean",
            ),
            mean_raw_brier_score=(
                "raw_multiclass_brier_score",
                "mean",
            ),
            mean_regularised_brier_score=(
                "regularised_multiclass_brier_score",
                "mean",
            ),
            mean_brier_difference_regularised_minus_raw=(
                "brier_difference_regularised_minus_raw",
                "mean",
            ),
        )
        .sort_values(["chronology_block", "decision_rule"])
        .reset_index(drop=True)
    )

    return score_panel, date_scores, block_summary, rule_summary


def main() -> None:
    joined, lineage = load_and_join()

    (
        score_panel,
        date_scores,
        block_summary,
        rule_summary,
    ) = calculate_scores(joined)

    block_dimensions = {
        row["chronology_block"]: {
            "dates": int(row["dates"]),
            "probability_books": int(row["probability_books"]),
        }
        for row in block_summary.to_dict("records")
    }

    checks = pd.DataFrame(
        [
            {
                "check": "all_probability_rows_joined",
                "passed": len(joined) == 1749,
                "value": len(joined),
            },
            {
                "check": "label_join_is_unique",
                "passed": True,
                "value": (
                    "target_date plus normalised "
                    "source_event_label"
                ),
            },
            {
                "check": "event_order_matches_event_index_plus_one",
                "passed": (
                    pd.to_numeric(joined["event_order"])
                    .eq(pd.to_numeric(joined["event_index"]) + 1)
                    .all()
                ),
                "value": True,
            },
            {
                "check": "probability_books_equal_159",
                "passed": score_panel["row_id"].nunique() == 159,
                "value": score_panel["row_id"].nunique(),
            },
            {
                "check": "holdout_dimensions",
                "passed": block_dimensions.get("holdout")
                == {"dates": 10, "probability_books": 40},
                "value": block_dimensions.get("holdout"),
            },
            {
                "check": "external_test_dimensions",
                "passed": block_dimensions.get("external_test")
                == {"dates": 30, "probability_books": 119},
                "value": block_dimensions.get("external_test"),
            },
            {
                "check": "regularised_scores_are_finite",
                "passed": np.isfinite(
                    score_panel[
                        "regularised_categorical_log_score"
                    ]
                ).all(),
                "value": True,
            },
            {
                "check": "market_prices_not_accessed",
                "passed": not as_bool(
                    joined["market_price_accessed"]
                ).any(),
                "value": False,
            },
            {
                "check": "trading_returns_not_calculated",
                "passed": True,
                "value": False,
            },
        ]
    )

    if not checks["passed"].astype(bool).all():
        raise RuntimeError(
            "Notebook 10 integrity checks failed:\n"
            + checks.loc[
                ~checks["passed"].astype(bool)
            ].to_string(index=False)
        )

    joined = joined.drop(columns=["_join_label", "_merge"])

    for path in (
        OUTCOME_PANEL_PATH,
        SCORE_PANEL_PATH,
        DATE_SCORE_PATH,
        RULE_SUMMARY_PATH,
        BLOCK_SUMMARY_PATH,
        INTEGRITY_PATH,
        MANIFEST_10_PATH,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    joined.to_csv(OUTCOME_PANEL_PATH, index=False)
    score_panel.to_csv(SCORE_PANEL_PATH, index=False)
    date_scores.to_csv(DATE_SCORE_PATH, index=False)
    rule_summary.to_csv(RULE_SUMMARY_PATH, index=False)
    block_summary.to_csv(BLOCK_SUMMARY_PATH, index=False)
    checks.to_csv(INTEGRITY_PATH, index=False)

    manifest_09 = lineage["manifest_09"]

    manifest_10 = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "LOCKED_CATEGORICAL_EVALUATION_COMPLETE",
        "probability_calibration_status": manifest_09["status"],
        "selected_model": manifest_09["selected_model"],
        "selected_family": manifest_09["selected_family"],
        "locked_continuous_dispersion_scale": (
            manifest_09["locked_continuous_dispersion_scale"]
        ),
        "locked_uniform_mixing_lambda": (
            manifest_09["selected_uniform_mixing_lambda"]
        ),
        "primary_join": (
            "target_date plus normalised source_event_label "
            "to certified event_label"
        ),
        "structural_join_verification": (
            "event_order equals event_index plus one"
        ),
        "primary_score": "categorical_log_score",
        "secondary_score": "multiclass_brier_score",
        "uncertainty_unit": "settlement_date",
        "decision_rules_averaged_within_date": True,
        "evaluation_dates": 40,
        "probability_books": 159,
        "probability_rows": 1749,
        "holdout_dates": 10,
        "holdout_probability_books": 40,
        "external_test_dates": 30,
        "external_test_probability_books": 119,
        "raw_and_regularised_probabilities_evaluated": True,
        "probabilities_clipped_for_log_score": False,
        "realised_hko_outcomes_accessed": True,
        "model_reselected": False,
        "continuous_calibration_reselected": False,
        "probability_calibration_reselected": False,
        "market_prices_accessed": False,
        "trading_returns_calculated": False,
        "input_hashes": {
            str(SPEC_PATH.relative_to(ROOT)): sha256_file(SPEC_PATH),
            str(MANIFEST_09_PATH.relative_to(ROOT)): sha256_file(
                MANIFEST_09_PATH
            ),
            str(PROBABILITY_PATH.relative_to(ROOT)): sha256_file(
                PROBABILITY_PATH
            ),
            str(EVENT_BOOK_PATH.relative_to(ROOT)): sha256_file(
                EVENT_BOOK_PATH
            ),
        },
        "output_hashes": {
            str(SCORE_PANEL_PATH.relative_to(ROOT)): sha256_file(
                SCORE_PANEL_PATH
            ),
            str(DATE_SCORE_PATH.relative_to(ROOT)): sha256_file(
                DATE_SCORE_PATH
            ),
            str(BLOCK_SUMMARY_PATH.relative_to(ROOT)): sha256_file(
                BLOCK_SUMMARY_PATH
            ),
            str(INTEGRITY_PATH.relative_to(ROOT)): sha256_file(
                INTEGRITY_PATH
            ),
        },
        "next_stage": (
            "common-support comparison with market probabilities"
        ),
    }

    MANIFEST_10_PATH.write_text(
        json.dumps(manifest_10, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 78)
    print("LOCKED CATEGORICAL EVALUATION COMPLETE")
    print("=" * 78)
    print()
    print(block_summary.to_string(index=False))
    print()
    print("Integrity checks passed:", True)
    print("Realised HKO outcomes accessed:", True)
    print("Model reselected:", False)
    print("Continuous calibration reselected:", False)
    print("Probability calibration reselected:", False)
    print("Market prices accessed:", False)
    print("Trading returns calculated:", False)


if __name__ == "__main__":
    main()
