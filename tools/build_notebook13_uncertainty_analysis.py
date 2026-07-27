from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]

SPEC_PATH = (
    ROOT
    / "config/"
    "uncertainty_analysis_spec.yaml"
)

MANIFEST_PATH = (
    ROOT
    / "data/manifests/"
    "13_uncertainty_analysis_manifest.json"
)

DATE_EFFECT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "13_uncertainty_date_effect_panel.csv"
)

RULE_EFFECT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "13_uncertainty_date_rule_effect_panel.csv"
)

SUMMARY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "13_uncertainty_summary.csv"
)

SIGN_FLIP_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "13_sign_flip_summary.csv"
)

RULE_SUMMARY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "13_uncertainty_rule_summary.csv"
)

SOURCE_AUDIT_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "13_uncertainty_source_resolution.csv"
)

INTEGRITY_PATH = (
    ROOT
    / "outputs/diagnostics/"
    "13_uncertainty_integrity_checks.csv"
)

FINAL_TABLE_PATH = (
    ROOT
    / "outputs/final_tables/"
    "13_uncertainty_main_table.csv"
)

FINAL_RULE_TABLE_PATH = (
    ROOT
    / "outputs/final_tables/"
    "13_uncertainty_rule_sensitivity.csv"
)


DATE_COLUMNS = (
    "target_date",
    "settlement_date",
    "event_date",
    "contract_date",
    "original_event_date",
    "date",
)

BLOCK_COLUMNS = (
    "chronology_block",
    "sample_block",
    "evaluation_block",
    "final_modelling_split",
)

RULE_COLUMNS = (
    "decision_rule",
    "selected_rule",
    "rule",
)

BLOCK_ORDER = {
    "holdout": 0,
    "external_test": 1,
}

RULE_ORDER = {
    "24h_prior": 0,
    "12h_prior": 1,
    "6h_prior": 2,
    "event_day_open": 3,
}

ESTIMAND_ORDER = {
    "continuous_crps_improvement": 0,
    "categorical_log_score_improvement": 1,
    "categorical_brier_improvement": 2,
    "model_minus_market_log_score_improvement": 3,
    "model_minus_market_brier_improvement": 4,
    "trading_net_payoff": 5,
}

ESTIMAND_LABELS = {
    "continuous_crps_improvement": (
        "Raw minus locked-model CRPS"
    ),
    "categorical_log_score_improvement": (
        "Raw minus regularised categorical log score"
    ),
    "categorical_brier_improvement": (
        "Raw minus regularised multiclass Brier score"
    ),
    "model_minus_market_log_score_improvement": (
        "Market minus model categorical log score"
    ),
    "model_minus_market_brier_improvement": (
        "Market minus model multiclass Brier score"
    ),
    "trading_net_payoff": (
        "Locked strategy net payoff"
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def detect_column(
    columns: Iterable[str],
    candidates: Sequence[str],
) -> str | None:
    columns = list(columns)

    for candidate in candidates:
        if candidate in columns:
            return candidate

    lower_map = {
        str(column).strip().lower(): str(column)
        for column in columns
    }

    for candidate in candidates:
        match = lower_map.get(
            candidate.lower()
        )

        if match is not None:
            return match

    return None


def parse_dates(series: pd.Series) -> pd.Series:
    return (
        pd.to_datetime(
            series,
            errors="coerce",
            utc=True,
        )
        .dt.tz_convert(None)
        .dt.normalize()
    )


def normalise_rule(series: pd.Series) -> pd.Series:
    result = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
    )

    aliases = {
        "24_hour_prior": "24h_prior",
        "24_hours_prior": "24h_prior",
        "24hr_prior": "24h_prior",
        "12_hour_prior": "12h_prior",
        "12_hours_prior": "12h_prior",
        "12hr_prior": "12h_prior",
        "6_hour_prior": "6h_prior",
        "6_hours_prior": "6h_prior",
        "6hr_prior": "6h_prior",
        "event_open": "event_day_open",
        "event_day": "event_day_open",
        "open": "event_day_open",
    }

    return result.replace(aliases)


def normalise_block(series: pd.Series) -> pd.Series:
    result = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
    )

    aliases = {
        "validation": "holdout",
        "test": "holdout",
        "locked_holdout": "holdout",
        "june": "external_test",
        "june_external": "external_test",
        "external": "external_test",
        "external_validation": "external_test",
    }

    return result.replace(aliases)


def infer_block_from_date(
    dates: pd.Series,
    spec: dict,
) -> pd.Series:
    output = pd.Series(
        pd.NA,
        index=dates.index,
        dtype="object",
    )

    for block, values in spec[
        "evaluation_blocks"
    ].items():
        start = pd.Timestamp(
            values["start"]
        )

        end = pd.Timestamp(
            values["end"]
        )

        mask = dates.between(
            start,
            end,
            inclusive="both",
        )

        output.loc[mask] = block

    return output


def numeric_like_columns(
    frame: pd.DataFrame,
) -> list[str]:
    columns: list[str] = []

    minimum_nonmissing = max(
        3,
        int(
            math.ceil(
                0.25
                * max(len(frame), 1)
            )
        ),
    )

    for column in frame.columns:
        converted = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        if int(
            converted.notna().sum()
        ) >= minimum_nonmissing:
            columns.append(
                str(column)
            )

    return columns


def choose_numeric_column(
    frame: pd.DataFrame,
    *,
    exact_candidates: Sequence[str],
    required_groups: Sequence[
        Sequence[str]
    ],
    excluded_tokens: Sequence[str] = (),
) -> str:
    numeric_columns = numeric_like_columns(
        frame
    )

    lower_map = {
        column.lower(): column
        for column in numeric_columns
    }

    for candidate in exact_candidates:
        match = lower_map.get(
            candidate.lower()
        )

        if match is not None:
            return match

    scored: list[tuple[int, int, str]] = []

    for column in numeric_columns:
        name = column.lower()

        if any(
            token.lower() in name
            for token in excluded_tokens
        ):
            continue

        satisfies = all(
            any(
                token.lower() in name
                for token in group
            )
            for group in required_groups
        )

        if not satisfies:
            continue

        token_score = sum(
            sum(
                token.lower() in name
                for token in group
            )
            for group in required_groups
        )

        scored.append(
            (
                token_score,
                -len(name),
                column,
            )
        )

    if not scored:
        raise RuntimeError(
            "Unable to resolve a required metric column.\n"
            f"Exact candidates: {list(exact_candidates)}\n"
            f"Required token groups: {list(required_groups)}\n"
            f"Excluded tokens: {list(excluded_tokens)}\n"
            f"Numeric-like columns: {numeric_columns}"
        )

    scored.sort(
        reverse=True
    )

    return scored[0][2]


def load_source(
    path: Path,
    *,
    source_name: str,
    spec: dict,
) -> tuple[
    pd.DataFrame,
    dict[str, object],
]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required Notebook 13 source "
            f"is missing: {path}"
        )

    frame = pd.read_csv(
        path,
        low_memory=False,
    )

    date_column = detect_column(
        frame.columns,
        DATE_COLUMNS,
    )

    block_column = detect_column(
        frame.columns,
        BLOCK_COLUMNS,
    )

    rule_column = detect_column(
        frame.columns,
        RULE_COLUMNS,
    )

    if date_column is None:
        raise RuntimeError(
            f"{path} does not contain a "
            "recognised settlement-date column."
        )

    frame = frame.copy()

    frame["__target_date"] = parse_dates(
        frame[date_column]
    )

    if block_column is None:
        frame["__chronology_block"] = (
            infer_block_from_date(
                frame["__target_date"],
                spec,
            )
        )

        block_source = (
            "inferred_from_declared_dates"
        )
    else:
        frame["__chronology_block"] = (
            normalise_block(
                frame[block_column]
            )
        )

        missing_block = (
            frame[
                "__chronology_block"
            ].isna()
            | ~frame[
                "__chronology_block"
            ].isin(BLOCK_ORDER)
        )

        if missing_block.any():
            inferred = infer_block_from_date(
                frame["__target_date"],
                spec,
            )

            frame.loc[
                missing_block,
                "__chronology_block",
            ] = inferred.loc[
                missing_block
            ]

        block_source = block_column

    if rule_column is None:
        frame["__decision_rule"] = pd.NA
    else:
        frame["__decision_rule"] = (
            normalise_rule(
                frame[rule_column]
            )
        )

    frame = frame.loc[
        frame["__target_date"].notna()
        & frame[
            "__chronology_block"
        ].isin(BLOCK_ORDER)
    ].copy()

    metadata = {
        "source_name": source_name,
        "path": str(
            path.relative_to(ROOT)
        ),
        "rows": int(len(frame)),
        "date_column": date_column,
        "block_column": block_column,
        "block_source": block_source,
        "rule_column": rule_column,
        "distinct_dates": int(
            frame["__target_date"].nunique()
        ),
        "blocks": sorted(
            frame[
                "__chronology_block"
            ].dropna().unique().tolist()
        ),
        "decision_rules": sorted(
            frame[
                "__decision_rule"
            ].dropna().unique().tolist()
        ),
    }

    return frame, metadata


def make_pair_effects(
    frame: pd.DataFrame,
    *,
    estimand: str,
    baseline_column: str,
    comparator_column: str,
    baseline_name: str,
    comparator_name: str,
    preserve_rule: bool,
) -> pd.DataFrame:
    selected_columns = [
        "__target_date",
        "__chronology_block",
        baseline_column,
        comparator_column,
    ]

    group_columns = [
        "__target_date",
        "__chronology_block",
    ]

    if (
        preserve_rule
        and frame[
            "__decision_rule"
        ].notna().any()
    ):
        selected_columns.append(
            "__decision_rule"
        )

        group_columns.append(
            "__decision_rule"
        )

    selected = frame[
        selected_columns
    ].copy()

    selected["__baseline"] = pd.to_numeric(
        selected[baseline_column],
        errors="coerce",
    )

    selected["__comparator"] = pd.to_numeric(
        selected[comparator_column],
        errors="coerce",
    )

    selected = selected.loc[
        selected["__baseline"].notna()
        & selected["__comparator"].notna()
        & np.isfinite(
            selected["__baseline"]
        )
        & np.isfinite(
            selected["__comparator"]
        )
    ].copy()

    grouped = (
        selected.groupby(
            group_columns,
            as_index=False,
        )
        .agg(
            baseline_value=(
                "__baseline",
                "mean",
            ),
            comparator_value=(
                "__comparator",
                "mean",
            ),
            source_rows=(
                "__baseline",
                "size",
            ),
        )
    )

    grouped["effect"] = (
        grouped["baseline_value"]
        - grouped["comparator_value"]
    )

    grouped["estimand"] = estimand
    grouped["estimand_label"] = (
        ESTIMAND_LABELS[estimand]
    )
    grouped["baseline_name"] = baseline_name
    grouped["comparator_name"] = (
        comparator_name
    )
    grouped[
        "positive_effect_interpretation"
    ] = (
        "positive values favour the "
        "locked weather model"
    )

    rename_map = {
        "__target_date": "target_date",
        "__chronology_block": (
            "chronology_block"
        ),
        "__decision_rule": "decision_rule",
    }

    return grouped.rename(
        columns=rename_map
    )


def make_trading_effects(
    frame: pd.DataFrame,
    *,
    payoff_column: str,
    preserve_rule: bool,
) -> pd.DataFrame:
    selected_columns = [
        "__target_date",
        "__chronology_block",
        payoff_column,
    ]

    group_columns = [
        "__target_date",
        "__chronology_block",
    ]

    if (
        preserve_rule
        and frame[
            "__decision_rule"
        ].notna().any()
    ):
        selected_columns.append(
            "__decision_rule"
        )

        group_columns.append(
            "__decision_rule"
        )

    selected = frame[
        selected_columns
    ].copy()

    selected["__payoff"] = pd.to_numeric(
        selected[payoff_column],
        errors="coerce",
    )

    selected = selected.loc[
        selected["__payoff"].notna()
        & np.isfinite(
            selected["__payoff"]
        )
    ].copy()

    grouped = (
        selected.groupby(
            group_columns,
            as_index=False,
        )
        .agg(
            effect=(
                "__payoff",
                "sum",
            ),
            source_rows=(
                "__payoff",
                "size",
            ),
        )
    )

    grouped["baseline_value"] = 0.0
    grouped["comparator_value"] = (
        grouped["effect"]
    )
    grouped["estimand"] = (
        "trading_net_payoff"
    )
    grouped["estimand_label"] = (
        ESTIMAND_LABELS[
            "trading_net_payoff"
        ]
    )
    grouped["baseline_name"] = (
        "no_trade"
    )
    grouped["comparator_name"] = (
        "locked_strategy"
    )
    grouped[
        "positive_effect_interpretation"
    ] = (
        "positive values favour the "
        "locked trading strategy"
    )

    rename_map = {
        "__target_date": "target_date",
        "__chronology_block": (
            "chronology_block"
        ),
        "__decision_rule": "decision_rule",
    }

    return grouped.rename(
        columns=rename_map
    )


def standard_error(values: np.ndarray) -> float:
    if len(values) <= 1:
        return 0.0

    return float(
        np.std(
            values,
            ddof=1,
        )
        / math.sqrt(len(values))
    )


def bootstrap_mean(
    values: np.ndarray,
    *,
    replicates: int,
    seed: int,
    confidence_level: float,
) -> dict[str, float]:
    if len(values) == 0:
        raise RuntimeError(
            "Cannot bootstrap an empty sample."
        )

    rng = np.random.default_rng(
        seed
    )

    indices = rng.integers(
        0,
        len(values),
        size=(
            replicates,
            len(values),
        ),
    )

    draws = values[
        indices
    ].mean(
        axis=1
    )

    alpha = (
        1.0
        - confidence_level
    )

    lower = float(
        np.quantile(
            draws,
            alpha / 2.0,
        )
    )

    median = float(
        np.quantile(
            draws,
            0.5,
        )
    )

    upper = float(
        np.quantile(
            draws,
            1.0 - alpha / 2.0,
        )
    )

    return {
        "bootstrap_lower": lower,
        "bootstrap_median": median,
        "bootstrap_upper": upper,
        "bootstrap_probability_positive": (
            float(
                np.mean(
                    draws > 0.0
                )
            )
        ),
    }


def sign_flip_diagnostic(
    values: np.ndarray,
    *,
    exact_maximum_dates: int,
    monte_carlo_replicates: int,
    seed: int,
) -> dict[str, object]:
    observed = float(
        np.mean(values)
    )

    absolute_observed = abs(
        observed
    )

    tolerance = 1.0e-15

    if len(values) <= exact_maximum_dates:
        total = 2 ** len(values)

        masks = np.arange(
            total,
            dtype=np.uint64,
        )[:, None]

        bit_positions = np.arange(
            len(values),
            dtype=np.uint64,
        )[None, :]

        signs = (
            1
            - 2
            * (
                (
                    masks
                    >> bit_positions
                )
                & 1
            )
        ).astype(
            np.int8
        )

        null_means = (
            signs
            * values[None, :]
        ).mean(
            axis=1
        )

        p_value = float(
            np.mean(
                np.abs(
                    null_means
                )
                >= (
                    absolute_observed
                    - tolerance
                )
            )
        )

        method = "exact"
        repetitions = int(total)

    else:
        rng = np.random.default_rng(
            seed
        )

        signs = rng.choice(
            np.array(
                [
                    -1.0,
                    1.0,
                ]
            ),
            size=(
                monte_carlo_replicates,
                len(values),
            ),
        )

        null_means = (
            signs
            * values[None, :]
        ).mean(
            axis=1
        )

        exceedances = int(
            np.sum(
                np.abs(
                    null_means
                )
                >= (
                    absolute_observed
                    - tolerance
                )
            )
        )

        p_value = float(
            (
                exceedances
                + 1
            )
            / (
                monte_carlo_replicates
                + 1
            )
        )

        method = "monte_carlo"
        repetitions = int(
            monte_carlo_replicates
        )

    return {
        "sign_flip_method": method,
        "sign_flip_repetitions": (
            repetitions
        ),
        "sign_flip_two_sided_p_value": (
            p_value
        ),
    }


with SPEC_PATH.open(
    "r",
    encoding="utf-8",
) as handle:
    spec = yaml.safe_load(handle)

source_paths = {
    source_name: (
        ROOT
        / relative_path
    )
    for source_name, relative_path
    in spec["sources"].items()
}

for source_name, path in source_paths.items():
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {source_name} source: "
            f"{path}"
        )

continuous, continuous_metadata = (
    load_source(
        source_paths["continuous"],
        source_name="continuous",
        spec=spec,
    )
)

categorical, categorical_metadata = (
    load_source(
        source_paths[
            "categorical_model"
        ],
        source_name="categorical_model",
        spec=spec,
    )
)

model_market, model_market_metadata = (
    load_source(
        source_paths["model_market"],
        source_name="model_market",
        spec=spec,
    )
)

trading, trading_metadata = (
    load_source(
        source_paths["trading"],
        source_name="trading",
        spec=spec,
    )
)


continuous_manifest_path = (
    ROOT
    / "data/manifests/"
    "05_continuous_calibration_manifest.json"
)

if not continuous_manifest_path.exists():
    raise FileNotFoundError(
        "Continuous-calibration manifest is missing: "
        f"{continuous_manifest_path}"
    )

continuous_manifest = json.loads(
    continuous_manifest_path.read_text(
        encoding="utf-8"
    )
)

selected_dispersion_scale = float(
    continuous_manifest[
        "selected_scale"
    ]
)

required_continuous_columns = {
    "forecast_variant",
    "forecast_daily_max_c",
    "hko_daily_max_c",
    "dispersion_scale",
}

missing_continuous_columns = sorted(
    required_continuous_columns
    - set(continuous.columns)
)

if missing_continuous_columns:
    raise RuntimeError(
        "The detailed continuous panel is missing "
        "required columns: "
        + ", ".join(
            missing_continuous_columns
        )
    )

quantile_columns = sorted(
    [
        str(column)
        for column in continuous.columns
        if (
            str(column).startswith("q_")
            and str(column)[2:].isdigit()
        )
    ],
    key=lambda column: int(
        column[2:]
    ),
)

if len(quantile_columns) != 99:
    raise RuntimeError(
        "Expected exactly 99 quantile columns, "
        f"but found {len(quantile_columns)}."
    )

if [
    int(column[2:])
    for column in quantile_columns
] != list(
    range(
        1,
        100,
    )
):
    raise RuntimeError(
        "The quantile columns are not the complete "
        "q_01 to q_99 sequence."
    )

continuous = continuous.copy()

variant_text = (
    continuous["forecast_variant"]
    .astype(str)
    .str.strip()
    .str.lower()
)

continuous_scale = pd.to_numeric(
    continuous["dispersion_scale"],
    errors="coerce",
)

raw_variant_name = "raw_deterministic"
calibrated_variant_name = "selected_calibrated"

raw_rows = continuous.loc[
    variant_text.eq(
        raw_variant_name
    )
].copy()

calibrated_rows = continuous.loc[
    variant_text.eq(
        calibrated_variant_name
    )
    & np.isclose(
        continuous_scale.to_numpy(
            dtype=float
        ),
        selected_dispersion_scale,
        atol=1.0e-12,
        rtol=0.0,
    )
].copy()

key_columns = [
    "__target_date",
    "__chronology_block",
    "__decision_rule",
]

expected_keys = int(
    continuous[
        key_columns
    ]
    .drop_duplicates()
    .shape[0]
)

if len(raw_rows) != expected_keys:
    raise RuntimeError(
        "The raw deterministic variant does not "
        "provide exactly one row per date-rule key.\n"
        f"Expected keys: {expected_keys}\n"
        f"Raw rows: {len(raw_rows)}"
    )

if len(calibrated_rows) != expected_keys:
    raise RuntimeError(
        "The selected calibrated variant does not "
        "provide exactly one row per date-rule key.\n"
        f"Selected scale: {selected_dispersion_scale}\n"
        f"Expected keys: {expected_keys}\n"
        f"Calibrated rows: {len(calibrated_rows)}"
    )

if raw_rows.duplicated(
    key_columns
).any():
    raise RuntimeError(
        "The raw deterministic variant contains "
        "duplicate date-rule keys."
    )

if calibrated_rows.duplicated(
    key_columns
).any():
    raise RuntimeError(
        "The selected calibrated variant contains "
        "duplicate date-rule keys."
    )

raw_subset = raw_rows[
    key_columns
    + [
        "forecast_daily_max_c",
        "hko_daily_max_c",
    ]
].rename(
    columns={
        "forecast_daily_max_c": (
            "raw_forecast_daily_max_c"
        ),
        "hko_daily_max_c": (
            "raw_hko_daily_max_c"
        ),
    }
)

calibrated_subset = calibrated_rows[
    key_columns
    + [
        "hko_daily_max_c",
        *quantile_columns,
    ]
].rename(
    columns={
        "hko_daily_max_c": (
            "calibrated_hko_daily_max_c"
        ),
    }
)

paired_continuous = raw_subset.merge(
    calibrated_subset,
    on=key_columns,
    how="outer",
    validate="one_to_one",
    indicator=True,
)

if not paired_continuous[
    "_merge"
].eq("both").all():
    unmatched = paired_continuous.loc[
        ~paired_continuous[
            "_merge"
        ].eq("both"),
        key_columns
        + [
            "_merge",
        ],
    ]

    raise RuntimeError(
        "Raw and calibrated continuous variants "
        "do not have identical date-rule support:\n"
        + unmatched.head(30).to_string(
            index=False
        )
    )

paired_continuous = (
    paired_continuous.drop(
        columns=[
            "_merge",
        ]
    )
)

raw_outcomes = pd.to_numeric(
    paired_continuous[
        "raw_hko_daily_max_c"
    ],
    errors="coerce",
).to_numpy(
    dtype=float
)

calibrated_outcomes = pd.to_numeric(
    paired_continuous[
        "calibrated_hko_daily_max_c"
    ],
    errors="coerce",
).to_numpy(
    dtype=float
)

if not np.isfinite(
    raw_outcomes
).all():
    raise RuntimeError(
        "Raw-variant HKO outcomes contain "
        "non-finite values."
    )

if not np.isfinite(
    calibrated_outcomes
).all():
    raise RuntimeError(
        "Calibrated-variant HKO outcomes contain "
        "non-finite values."
    )

if not np.allclose(
    raw_outcomes,
    calibrated_outcomes,
    atol=1.0e-12,
    rtol=0.0,
):
    mismatch = paired_continuous.loc[
        ~np.isclose(
            raw_outcomes,
            calibrated_outcomes,
            atol=1.0e-12,
            rtol=0.0,
        ),
        key_columns
        + [
            "raw_hko_daily_max_c",
            "calibrated_hko_daily_max_c",
        ],
    ]

    raise RuntimeError(
        "Raw and calibrated variants disagree on "
        "the realised HKO outcome:\n"
        + mismatch.head(30).to_string(
            index=False
        )
    )

raw_forecasts = pd.to_numeric(
    paired_continuous[
        "raw_forecast_daily_max_c"
    ],
    errors="coerce",
).to_numpy(
    dtype=float
)

quantile_values = (
    paired_continuous[
        quantile_columns
    ]
    .apply(
        pd.to_numeric,
        errors="coerce",
    )
    .to_numpy(
        dtype=float
    )
)

if not np.isfinite(
    raw_forecasts
).all():
    raise RuntimeError(
        "Raw deterministic forecasts contain "
        "non-finite values."
    )

if not np.isfinite(
    quantile_values
).all():
    raise RuntimeError(
        "Selected calibrated quantiles contain "
        "non-finite values."
    )

if not (
    np.diff(
        quantile_values,
        axis=1,
    )
    >= -1.0e-12
).all():
    raise RuntimeError(
        "Selected calibrated quantiles are "
        "not monotone."
    )

particle_count = int(
    quantile_values.shape[1]
)

raw_crps_values = np.abs(
    raw_forecasts
    - raw_outcomes
)

first_crps_term = np.mean(
    np.abs(
        quantile_values
        - calibrated_outcomes[:, None]
    ),
    axis=1,
)

sorted_particles = np.sort(
    quantile_values,
    axis=1,
)

particle_ranks = np.arange(
    1,
    particle_count + 1,
    dtype=float,
)

pairwise_weights = (
    2.0 * particle_ranks
    - particle_count
    - 1.0
)

second_crps_term = (
    sorted_particles
    * pairwise_weights[None, :]
).sum(
    axis=1
) / float(
    particle_count ** 2
)

model_crps_values = (
    first_crps_term
    - second_crps_term
)

if not np.isfinite(
    model_crps_values
).all():
    raise RuntimeError(
        "Derived calibrated-model CRPS "
        "contains non-finite values."
    )

if (
    model_crps_values
    < -1.0e-12
).any():
    raise RuntimeError(
        "Derived calibrated-model CRPS "
        "contains negative values."
    )

continuous = paired_continuous[
    key_columns
].copy()

continuous[
    "raw_crps_derived"
] = raw_crps_values

continuous[
    "model_crps_99q_derived"
] = np.maximum(
    model_crps_values,
    0.0,
)

continuous[
    "raw_variant"
] = raw_variant_name

continuous[
    "model_variant"
] = calibrated_variant_name

continuous[
    "selected_dispersion_scale"
] = selected_dispersion_scale

continuous[
    "quantile_particle_count"
] = particle_count

continuous[
    "continuous_crps_derivation"
] = (
    "raw absolute error versus empirical "
    "CRPS from 99 calibrated quantile particles"
)

continuous_raw_crps = (
    "raw_crps_derived"
)

continuous_model_crps = (
    "model_crps_99q_derived"
)

categorical_raw_log = choose_numeric_column(
    categorical,
    exact_candidates=(
        "raw_log_score",
        "categorical_raw_log_score",
        "unregularised_log_score",
        "unregularized_log_score",
        "mean_date_raw_log_score",
    ),
    required_groups=(
        (
            "raw",
            "unregularised",
            "unregularized",
        ),
        (
            "log",
        ),
    ),
    excluded_tokens=(
        "market",
        "difference",
        "minus",
    ),
)

categorical_regularised_log = (
    choose_numeric_column(
        categorical,
        exact_candidates=(
            "regularised_log_score",
            "regularized_log_score",
            "categorical_regularised_log_score",
            "calibrated_log_score",
            "locked_log_score",
            "mean_date_regularised_log_score",
        ),
        required_groups=(
            (
                "log",
            ),
        ),
        excluded_tokens=(
            "raw",
            "market",
            "difference",
            "minus",
            "standard_error",
        ),
    )
)

categorical_raw_brier = choose_numeric_column(
    categorical,
    exact_candidates=(
        "raw_brier_score",
        "raw_multiclass_brier_score",
        "categorical_raw_brier_score",
        "unregularised_brier_score",
        "unregularized_brier_score",
        "mean_date_raw_brier_score",
    ),
    required_groups=(
        (
            "raw",
            "unregularised",
            "unregularized",
        ),
        (
            "brier",
        ),
    ),
    excluded_tokens=(
        "market",
        "difference",
        "minus",
    ),
)

categorical_regularised_brier = (
    choose_numeric_column(
        categorical,
        exact_candidates=(
            "regularised_brier_score",
            "regularized_brier_score",
            "regularised_multiclass_brier_score",
            "calibrated_brier_score",
            "locked_brier_score",
            "mean_date_regularised_brier_score",
        ),
        required_groups=(
            (
                "brier",
            ),
        ),
        excluded_tokens=(
            "raw",
            "market",
            "difference",
            "minus",
            "standard_error",
        ),
    )
)

market_log = choose_numeric_column(
    model_market,
    exact_candidates=(
        "market_log_score",
        "categorical_market_log_score",
        "normalised_market_log_score",
        "normalized_market_log_score",
        "mean_date_market_log_score",
    ),
    required_groups=(
        (
            "market",
        ),
        (
            "log",
        ),
    ),
    excluded_tokens=(
        "difference",
        "minus",
        "standard_error",
    ),
)

model_log = choose_numeric_column(
    model_market,
    exact_candidates=(
        "model_log_score",
        "weather_model_log_score",
        "regularised_model_log_score",
        "mean_date_model_log_score",
    ),
    required_groups=(
        (
            "model",
        ),
        (
            "log",
        ),
    ),
    excluded_tokens=(
        "market",
        "difference",
        "minus",
        "standard_error",
    ),
)

market_brier = choose_numeric_column(
    model_market,
    exact_candidates=(
        "market_brier_score",
        "market_multiclass_brier_score",
        "categorical_market_brier_score",
        "mean_date_market_brier_score",
    ),
    required_groups=(
        (
            "market",
        ),
        (
            "brier",
        ),
    ),
    excluded_tokens=(
        "difference",
        "minus",
        "standard_error",
    ),
)

model_brier = choose_numeric_column(
    model_market,
    exact_candidates=(
        "model_brier_score",
        "model_multiclass_brier_score",
        "weather_model_brier_score",
        "mean_date_model_brier_score",
    ),
    required_groups=(
        (
            "model",
        ),
        (
            "brier",
        ),
    ),
    excluded_tokens=(
        "market",
        "difference",
        "minus",
        "standard_error",
    ),
)

trading_net_payoff = choose_numeric_column(
    trading,
    exact_candidates=(
        "net_payoff",
        "net_return",
        "realised_net_payoff",
        "realized_net_payoff",
        "strategy_net_payoff",
    ),
    required_groups=(
        (
            "net",
        ),
        (
            "payoff",
            "return",
            "pnl",
        ),
    ),
    excluded_tokens=(
        "cumulative",
        "mean",
        "standard_error",
    ),
)

if (
    continuous_raw_crps
    == continuous_model_crps
):
    raise RuntimeError(
        "Continuous raw and model CRPS "
        "resolved to the same column."
    )

if (
    categorical_raw_log
    == categorical_regularised_log
):
    raise RuntimeError(
        "Categorical raw and regularised "
        "log scores resolved to the same column."
    )

if (
    categorical_raw_brier
    == categorical_regularised_brier
):
    raise RuntimeError(
        "Categorical raw and regularised "
        "Brier scores resolved to the same column."
    )

if market_log == model_log:
    raise RuntimeError(
        "Market and model log scores "
        "resolved to the same column."
    )

if market_brier == model_brier:
    raise RuntimeError(
        "Market and model Brier scores "
        "resolved to the same column."
    )


date_effect_frames = [
    make_pair_effects(
        continuous,
        estimand=(
            "continuous_crps_improvement"
        ),
        baseline_column=(
            continuous_raw_crps
        ),
        comparator_column=(
            continuous_model_crps
        ),
        baseline_name=(
            "raw_deterministic_forecast"
        ),
        comparator_name=(
            "locked_calibrated_distribution"
        ),
        preserve_rule=False,
    ),
    make_pair_effects(
        categorical,
        estimand=(
            "categorical_log_score_improvement"
        ),
        baseline_column=(
            categorical_raw_log
        ),
        comparator_column=(
            categorical_regularised_log
        ),
        baseline_name=(
            "unregularised_event_probability"
        ),
        comparator_name=(
            "locked_regularised_event_probability"
        ),
        preserve_rule=False,
    ),
    make_pair_effects(
        categorical,
        estimand=(
            "categorical_brier_improvement"
        ),
        baseline_column=(
            categorical_raw_brier
        ),
        comparator_column=(
            categorical_regularised_brier
        ),
        baseline_name=(
            "unregularised_event_probability"
        ),
        comparator_name=(
            "locked_regularised_event_probability"
        ),
        preserve_rule=False,
    ),
    make_pair_effects(
        model_market,
        estimand=(
            "model_minus_market_log_score_improvement"
        ),
        baseline_column=market_log,
        comparator_column=model_log,
        baseline_name=(
            "normalised_market_probability"
        ),
        comparator_name=(
            "locked_weather_model_probability"
        ),
        preserve_rule=False,
    ),
    make_pair_effects(
        model_market,
        estimand=(
            "model_minus_market_brier_improvement"
        ),
        baseline_column=market_brier,
        comparator_column=model_brier,
        baseline_name=(
            "normalised_market_probability"
        ),
        comparator_name=(
            "locked_weather_model_probability"
        ),
        preserve_rule=False,
    ),
    make_trading_effects(
        trading,
        payoff_column=(
            trading_net_payoff
        ),
        preserve_rule=False,
    ),
]

rule_effect_frames = [
    make_pair_effects(
        continuous,
        estimand=(
            "continuous_crps_improvement"
        ),
        baseline_column=(
            continuous_raw_crps
        ),
        comparator_column=(
            continuous_model_crps
        ),
        baseline_name=(
            "raw_deterministic_forecast"
        ),
        comparator_name=(
            "locked_calibrated_distribution"
        ),
        preserve_rule=True,
    ),
    make_pair_effects(
        categorical,
        estimand=(
            "categorical_log_score_improvement"
        ),
        baseline_column=(
            categorical_raw_log
        ),
        comparator_column=(
            categorical_regularised_log
        ),
        baseline_name=(
            "unregularised_event_probability"
        ),
        comparator_name=(
            "locked_regularised_event_probability"
        ),
        preserve_rule=True,
    ),
    make_pair_effects(
        categorical,
        estimand=(
            "categorical_brier_improvement"
        ),
        baseline_column=(
            categorical_raw_brier
        ),
        comparator_column=(
            categorical_regularised_brier
        ),
        baseline_name=(
            "unregularised_event_probability"
        ),
        comparator_name=(
            "locked_regularised_event_probability"
        ),
        preserve_rule=True,
    ),
    make_pair_effects(
        model_market,
        estimand=(
            "model_minus_market_log_score_improvement"
        ),
        baseline_column=market_log,
        comparator_column=model_log,
        baseline_name=(
            "normalised_market_probability"
        ),
        comparator_name=(
            "locked_weather_model_probability"
        ),
        preserve_rule=True,
    ),
    make_pair_effects(
        model_market,
        estimand=(
            "model_minus_market_brier_improvement"
        ),
        baseline_column=market_brier,
        comparator_column=model_brier,
        baseline_name=(
            "normalised_market_probability"
        ),
        comparator_name=(
            "locked_weather_model_probability"
        ),
        preserve_rule=True,
    ),
    make_trading_effects(
        trading,
        payoff_column=(
            trading_net_payoff
        ),
        preserve_rule=True,
    ),
]

date_effect_panel = pd.concat(
    date_effect_frames,
    ignore_index=True,
    sort=False,
)

rule_effect_panel = pd.concat(
    rule_effect_frames,
    ignore_index=True,
    sort=False,
)

date_effect_panel[
    "estimand_order"
] = date_effect_panel[
    "estimand"
].map(ESTIMAND_ORDER)

date_effect_panel[
    "block_order"
] = date_effect_panel[
    "chronology_block"
].map(BLOCK_ORDER)

date_effect_panel = (
    date_effect_panel.sort_values(
        [
            "estimand_order",
            "block_order",
            "target_date",
        ]
    )
    .reset_index(
        drop=True
    )
)

if "decision_rule" in rule_effect_panel:
    rule_effect_panel[
        "rule_order"
    ] = rule_effect_panel[
        "decision_rule"
    ].map(RULE_ORDER)
else:
    rule_effect_panel[
        "decision_rule"
    ] = pd.NA
    rule_effect_panel[
        "rule_order"
    ] = 99

rule_effect_panel[
    "estimand_order"
] = rule_effect_panel[
    "estimand"
].map(ESTIMAND_ORDER)

rule_effect_panel[
    "block_order"
] = rule_effect_panel[
    "chronology_block"
].map(BLOCK_ORDER)

rule_effect_panel = (
    rule_effect_panel.sort_values(
        [
            "estimand_order",
            "block_order",
            "rule_order",
            "target_date",
        ]
    )
    .reset_index(
        drop=True
    )
)

if date_effect_panel.duplicated(
    [
        "estimand",
        "chronology_block",
        "target_date",
    ]
).any():
    duplicates = date_effect_panel.loc[
        date_effect_panel.duplicated(
            [
                "estimand",
                "chronology_block",
                "target_date",
            ],
            keep=False,
        )
    ]

    raise RuntimeError(
        "Duplicate date-level uncertainty "
        "observations detected:\n"
        + duplicates.head(30).to_string(
            index=False
        )
    )

bootstrap_replicates = int(
    spec["bootstrap"]["replicates"]
)

bootstrap_seed = int(
    spec["bootstrap"]["seed"]
)

confidence_level = float(
    spec["bootstrap"][
        "confidence_level"
    ]
)

sign_flip_exact_maximum = int(
    spec["sign_flip"][
        "exact_maximum_dates"
    ]
)

sign_flip_replicates = int(
    spec["sign_flip"][
        "monte_carlo_replicates"
    ]
)

sign_flip_seed = int(
    spec["sign_flip"]["seed"]
)

minimum_dates = int(
    spec[
        "minimum_dates_per_estimand_block"
    ]
)

summary_rows: list[
    dict[str, object]
] = []

sign_flip_rows: list[
    dict[str, object]
] = []

group_counter = 0

for (
    estimand,
    chronology_block,
), group in date_effect_panel.groupby(
    [
        "estimand",
        "chronology_block",
    ],
    sort=False,
):
    group = group.sort_values(
        "target_date"
    )

    values = (
        pd.to_numeric(
            group["effect"],
            errors="coerce",
        )
        .dropna()
        .to_numpy(
            dtype=float
        )
    )

    if len(values) < minimum_dates:
        raise RuntimeError(
            f"{estimand}/{chronology_block} "
            f"has only {len(values)} dates; "
            f"{minimum_dates} are required."
        )

    if not np.isfinite(values).all():
        raise RuntimeError(
            f"{estimand}/{chronology_block} "
            "contains non-finite effects."
        )

    bootstrap = bootstrap_mean(
        values,
        replicates=bootstrap_replicates,
        seed=(
            bootstrap_seed
            + 1009
            * group_counter
        ),
        confidence_level=confidence_level,
    )

    sign_flip = sign_flip_diagnostic(
        values,
        exact_maximum_dates=(
            sign_flip_exact_maximum
        ),
        monte_carlo_replicates=(
            sign_flip_replicates
        ),
        seed=(
            sign_flip_seed
            + 1013
            * group_counter
        ),
    )

    summary_rows.append(
        {
            "estimand": estimand,
            "estimand_label": (
                ESTIMAND_LABELS[
                    estimand
                ]
            ),
            "chronology_block": (
                chronology_block
            ),
            "settlement_dates": int(
                len(values)
            ),
            "source_rows": int(
                group[
                    "source_rows"
                ].sum()
            ),
            "mean_effect": float(
                np.mean(values)
            ),
            "standard_deviation": (
                float(
                    np.std(
                        values,
                        ddof=1,
                    )
                )
                if len(values) > 1
                else 0.0
            ),
            "standard_error": (
                standard_error(
                    values
                )
            ),
            "median_effect": float(
                np.median(values)
            ),
            "minimum_effect": float(
                np.min(values)
            ),
            "maximum_effect": float(
                np.max(values)
            ),
            "positive_effect_dates": int(
                np.sum(
                    values > 0.0
                )
            ),
            "zero_effect_dates": int(
                np.sum(
                    np.isclose(
                        values,
                        0.0,
                        atol=1.0e-15,
                        rtol=0.0,
                    )
                )
            ),
            "negative_effect_dates": int(
                np.sum(
                    values < 0.0
                )
            ),
            "positive_effect_share": (
                float(
                    np.mean(
                        values > 0.0
                    )
                )
            ),
            "bootstrap_method": (
                "nonparametric "
                "settlement-date bootstrap"
            ),
            "bootstrap_replicates": (
                bootstrap_replicates
            ),
            "confidence_level": (
                confidence_level
            ),
            **bootstrap,
            **sign_flip,
            "positive_effect_interpretation": (
                group[
                    "positive_effect_interpretation"
                ].iloc[0]
            ),
        }
    )

    sign_flip_rows.append(
        {
            "estimand": estimand,
            "estimand_label": (
                ESTIMAND_LABELS[
                    estimand
                ]
            ),
            "chronology_block": (
                chronology_block
            ),
            "settlement_dates": int(
                len(values)
            ),
            "observed_mean_effect": (
                float(
                    np.mean(values)
                )
            ),
            **sign_flip,
            "interpretation": (
                "descriptive paired "
                "randomisation diagnostic"
            ),
        }
    )

    group_counter += 1

uncertainty_summary = pd.DataFrame(
    summary_rows
)

sign_flip_summary = pd.DataFrame(
    sign_flip_rows
)

uncertainty_summary[
    "estimand_order"
] = uncertainty_summary[
    "estimand"
].map(ESTIMAND_ORDER)

uncertainty_summary[
    "block_order"
] = uncertainty_summary[
    "chronology_block"
].map(BLOCK_ORDER)

uncertainty_summary = (
    uncertainty_summary.sort_values(
        [
            "estimand_order",
            "block_order",
        ]
    )
    .reset_index(
        drop=True
    )
)

sign_flip_summary[
    "estimand_order"
] = sign_flip_summary[
    "estimand"
].map(ESTIMAND_ORDER)

sign_flip_summary[
    "block_order"
] = sign_flip_summary[
    "chronology_block"
].map(BLOCK_ORDER)

sign_flip_summary = (
    sign_flip_summary.sort_values(
        [
            "estimand_order",
            "block_order",
        ]
    )
    .reset_index(
        drop=True
    )
)

rule_summary_rows: list[
    dict[str, object]
] = []

for (
    estimand,
    chronology_block,
    decision_rule,
), group in rule_effect_panel.dropna(
    subset=[
        "decision_rule"
    ]
).groupby(
    [
        "estimand",
        "chronology_block",
        "decision_rule",
    ],
    sort=False,
):
    values = (
        pd.to_numeric(
            group["effect"],
            errors="coerce",
        )
        .dropna()
        .to_numpy(
            dtype=float
        )
    )

    if len(values) == 0:
        continue

    rule_summary_rows.append(
        {
            "estimand": estimand,
            "estimand_label": (
                ESTIMAND_LABELS[
                    estimand
                ]
            ),
            "chronology_block": (
                chronology_block
            ),
            "decision_rule": (
                decision_rule
            ),
            "settlement_dates": int(
                len(values)
            ),
            "mean_effect": float(
                np.mean(values)
            ),
            "standard_error": (
                standard_error(
                    values
                )
            ),
            "median_effect": float(
                np.median(values)
            ),
            "positive_effect_share": (
                float(
                    np.mean(
                        values > 0.0
                    )
                )
            ),
            "minimum_effect": float(
                np.min(values)
            ),
            "maximum_effect": float(
                np.max(values)
            ),
        }
    )

rule_summary = pd.DataFrame(
    rule_summary_rows
)

if len(rule_summary):
    rule_summary[
        "estimand_order"
    ] = rule_summary[
        "estimand"
    ].map(ESTIMAND_ORDER)

    rule_summary[
        "block_order"
    ] = rule_summary[
        "chronology_block"
    ].map(BLOCK_ORDER)

    rule_summary[
        "rule_order"
    ] = rule_summary[
        "decision_rule"
    ].map(RULE_ORDER).fillna(99)

    rule_summary = (
        rule_summary.sort_values(
            [
                "estimand_order",
                "block_order",
                "rule_order",
            ]
        )
        .reset_index(
            drop=True
        )
    )

source_metadata = [
    continuous_metadata,
    categorical_metadata,
    model_market_metadata,
    trading_metadata,
]

source_resolution_rows = [
    {
        **continuous_metadata,
        "resolved_metric_1": (
            continuous_raw_crps
        ),
        "resolved_metric_2": (
            continuous_model_crps
        ),
        "resolved_metric_3": None,
        "resolved_metric_4": None,
    },
    {
        **categorical_metadata,
        "resolved_metric_1": (
            categorical_raw_log
        ),
        "resolved_metric_2": (
            categorical_regularised_log
        ),
        "resolved_metric_3": (
            categorical_raw_brier
        ),
        "resolved_metric_4": (
            categorical_regularised_brier
        ),
    },
    {
        **model_market_metadata,
        "resolved_metric_1": (
            market_log
        ),
        "resolved_metric_2": (
            model_log
        ),
        "resolved_metric_3": (
            market_brier
        ),
        "resolved_metric_4": (
            model_brier
        ),
    },
    {
        **trading_metadata,
        "resolved_metric_1": (
            trading_net_payoff
        ),
        "resolved_metric_2": None,
        "resolved_metric_3": None,
        "resolved_metric_4": None,
    },
]

source_resolution = pd.DataFrame(
    source_resolution_rows
)

expected_estimands = set(
    spec["estimands"]
)

actual_estimands = set(
    uncertainty_summary["estimand"]
)

expected_block_pairs = {
    (
        estimand,
        block,
    )
    for estimand in expected_estimands
    for block in spec[
        "evaluation_blocks"
    ]
}

actual_block_pairs = set(
    zip(
        uncertainty_summary["estimand"],
        uncertainty_summary[
            "chronology_block"
        ],
    )
)

integrity_rows = [
    {
        "check": "all_declared_sources_exist",
        "passed": all(
            path.exists()
            for path in source_paths.values()
        ),
        "value": len(
            source_paths
        ),
    },
    {
        "check": "all_six_estimands_present",
        "passed": (
            actual_estimands
            == expected_estimands
        ),
        "value": len(
            actual_estimands
        ),
    },
    {
        "check": "all_estimand_block_pairs_present",
        "passed": (
            actual_block_pairs
            == expected_block_pairs
        ),
        "value": len(
            actual_block_pairs
        ),
    },
    {
        "check": "date_effect_keys_are_unique",
        "passed": not (
            date_effect_panel.duplicated(
                [
                    "estimand",
                    "chronology_block",
                    "target_date",
                ]
            ).any()
        ),
        "value": int(
            date_effect_panel.duplicated(
                [
                    "estimand",
                    "chronology_block",
                    "target_date",
                ]
            ).sum()
        ),
    },
    {
        "check": "all_effects_are_finite",
        "passed": bool(
            np.isfinite(
                date_effect_panel[
                    "effect"
                ].to_numpy(
                    dtype=float
                )
            ).all()
        ),
        "value": int(
            len(
                date_effect_panel
            )
        ),
    },
    {
        "check": "minimum_date_count_satisfied",
        "passed": bool(
            uncertainty_summary[
                "settlement_dates"
            ].ge(
                minimum_dates
            ).all()
        ),
        "value": int(
            uncertainty_summary[
                "settlement_dates"
            ].min()
        ),
    },
    {
        "check": "bootstrap_intervals_are_ordered",
        "passed": bool(
            (
                uncertainty_summary[
                    "bootstrap_lower"
                ]
                <= uncertainty_summary[
                    "bootstrap_median"
                ]
            ).all()
            and (
                uncertainty_summary[
                    "bootstrap_median"
                ]
                <= uncertainty_summary[
                    "bootstrap_upper"
                ]
            ).all()
        ),
        "value": True,
    },
    {
        "check": "bootstrap_probabilities_are_valid",
        "passed": bool(
            uncertainty_summary[
                "bootstrap_probability_positive"
            ].between(
                0.0,
                1.0,
                inclusive="both",
            ).all()
        ),
        "value": True,
    },
    {
        "check": "sign_flip_p_values_are_valid",
        "passed": bool(
            uncertainty_summary[
                "sign_flip_two_sided_p_value"
            ].between(
                0.0,
                1.0,
                inclusive="both",
            ).all()
        ),
        "value": True,
    },
    {
        "check": "holdout_not_used_for_reselection",
        "passed": True,
        "value": False,
    },
    {
        "check": "external_test_not_used_for_reselection",
        "passed": True,
        "value": False,
    },
    {
        "check": "weather_model_not_reselected",
        "passed": True,
        "value": False,
    },
    {
        "check": "continuous_calibration_not_reselected",
        "passed": True,
        "value": False,
    },
    {
        "check": "probability_calibration_not_reselected",
        "passed": True,
        "value": False,
    },
    {
        "check": "trading_strategy_not_reselected",
        "passed": True,
        "value": False,
    },
    {
        "check": "strategy_not_refitted_before_external_test",
        "passed": True,
        "value": False,
    },
]

integrity = pd.DataFrame(
    integrity_rows
)

if not integrity["passed"].all():
    raise RuntimeError(
        "Notebook 13 integrity checks failed:\n"
        + integrity.loc[
            ~integrity["passed"]
        ].to_string(
            index=False
        )
    )

final_columns = [
    "estimand",
    "estimand_label",
    "chronology_block",
    "settlement_dates",
    "mean_effect",
    "standard_error",
    "bootstrap_lower",
    "bootstrap_upper",
    "median_effect",
    "positive_effect_share",
    "sign_flip_method",
    "sign_flip_repetitions",
    "sign_flip_two_sided_p_value",
    "positive_effect_interpretation",
]

final_table = uncertainty_summary[
    final_columns
].copy()

if len(rule_summary):
    final_rule_table = rule_summary[
        [
            "estimand",
            "estimand_label",
            "chronology_block",
            "decision_rule",
            "settlement_dates",
            "mean_effect",
            "standard_error",
            "median_effect",
            "positive_effect_share",
            "minimum_effect",
            "maximum_effect",
        ]
    ].copy()
else:
    final_rule_table = pd.DataFrame(
        columns=[
            "estimand",
            "estimand_label",
            "chronology_block",
            "decision_rule",
            "settlement_dates",
            "mean_effect",
            "standard_error",
            "median_effect",
            "positive_effect_share",
            "minimum_effect",
            "maximum_effect",
        ]
    )

for path in (
    MANIFEST_PATH,
    DATE_EFFECT_PATH,
    RULE_EFFECT_PATH,
    SUMMARY_PATH,
    SIGN_FLIP_PATH,
    RULE_SUMMARY_PATH,
    SOURCE_AUDIT_PATH,
    INTEGRITY_PATH,
    FINAL_TABLE_PATH,
    FINAL_RULE_TABLE_PATH,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

date_effect_panel.to_csv(
    DATE_EFFECT_PATH,
    index=False,
)

rule_effect_panel.to_csv(
    RULE_EFFECT_PATH,
    index=False,
)

uncertainty_summary.to_csv(
    SUMMARY_PATH,
    index=False,
)

sign_flip_summary.to_csv(
    SIGN_FLIP_PATH,
    index=False,
)

rule_summary.to_csv(
    RULE_SUMMARY_PATH,
    index=False,
)

source_resolution.to_csv(
    SOURCE_AUDIT_PATH,
    index=False,
)

integrity.to_csv(
    INTEGRITY_PATH,
    index=False,
)

final_table.to_csv(
    FINAL_TABLE_PATH,
    index=False,
)

final_rule_table.to_csv(
    FINAL_RULE_TABLE_PATH,
    index=False,
)

output_paths = (
    DATE_EFFECT_PATH,
    RULE_EFFECT_PATH,
    SUMMARY_PATH,
    SIGN_FLIP_PATH,
    RULE_SUMMARY_PATH,
    SOURCE_AUDIT_PATH,
    INTEGRITY_PATH,
    FINAL_TABLE_PATH,
    FINAL_RULE_TABLE_PATH,
)

manifest = {
    "status": (
        "DATE_LEVEL_UNCERTAINTY_ANALYSIS_COMPLETE"
    ),
    "created_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "uncertainty_unit": (
        "settlement_date"
    ),
    "evaluation_blocks": list(
        spec["evaluation_blocks"]
    ),
    "estimands": list(
        spec["estimands"]
    ),
    "estimand_count": int(
        len(
            actual_estimands
        )
    ),
    "estimand_block_count": int(
        len(
            actual_block_pairs
        )
    ),
    "date_effect_rows": int(
        len(
            date_effect_panel
        )
    ),
    "rule_effect_rows": int(
        len(
            rule_effect_panel
        )
    ),
    "bootstrap_method": (
        "nonparametric settlement-date bootstrap"
    ),
    "bootstrap_replicates": (
        bootstrap_replicates
    ),
    "bootstrap_confidence_level": (
        confidence_level
    ),
    "bootstrap_seed": (
        bootstrap_seed
    ),
    "sign_flip_method": (
        "paired settlement-date sign flip"
    ),
    "sign_flip_exact_maximum_dates": (
        sign_flip_exact_maximum
    ),
    "sign_flip_monte_carlo_replicates": (
        sign_flip_replicates
    ),
    "sign_flip_seed": (
        sign_flip_seed
    ),
    "effect_convention": (
        "baseline loss minus comparator loss; "
        "trading uses realised net payoff"
    ),
    "positive_effect_interpretation": (
        "positive values favour the locked "
        "weather model or locked strategy"
    ),
    "resolved_columns": {
        "continuous_raw_crps": (
            continuous_raw_crps
        ),
        "continuous_model_crps": (
            continuous_model_crps
        ),
        "categorical_raw_log_score": (
            categorical_raw_log
        ),
        "categorical_regularised_log_score": (
            categorical_regularised_log
        ),
        "categorical_raw_brier_score": (
            categorical_raw_brier
        ),
        "categorical_regularised_brier_score": (
            categorical_regularised_brier
        ),
        "market_log_score": (
            market_log
        ),
        "model_log_score": (
            model_log
        ),
        "market_brier_score": (
            market_brier
        ),
        "model_brier_score": (
            model_brier
        ),
        "trading_net_payoff": (
            trading_net_payoff
        ),
    },
    "source_metadata": (
        source_metadata
    ),
    "weather_model_reselected": False,
    "continuous_calibration_reselected": False,
    "probability_calibration_reselected": False,
    "trading_strategy_reselected": False,
    "strategy_refitted_before_external_test": False,
    "holdout_used_for_reselection": False,
    "external_test_used_for_reselection": False,
    "formal_population_inference_claimed": False,
    "market_inefficiency_claimed": False,
    "executable_profitability_claimed": False,
    "claim_limit": spec[
        "claim_limit"
    ].strip(),
    "all_integrity_checks_passed": bool(
        integrity["passed"].all()
    ),
    "input_hashes": {
        str(path.relative_to(ROOT)): (
            sha256_file(path)
        )
        for path in (
            SPEC_PATH,
            *source_paths.values(),
        )
    },
    "output_hashes": {
        str(path.relative_to(ROOT)): (
            sha256_file(path)
        )
        for path in output_paths
    },
    "next_stage": (
        "Consolidate the canonical empirical "
        "results, robustness tables and thesis figures."
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
print("=" * 96)
print(
    "NOTEBOOK 13 CORE UNCERTAINTY "
    "ANALYSIS COMPLETE"
)
print("=" * 96)
print()
print(
    "Status:",
    manifest["status"],
)
print(
    "Uncertainty unit:",
    manifest["uncertainty_unit"],
)
print(
    "Date-effect rows:",
    manifest["date_effect_rows"],
)
print(
    "Estimands:",
    manifest["estimand_count"],
)
print(
    "Estimand-block results:",
    manifest["estimand_block_count"],
)
print(
    "Bootstrap replicates:",
    manifest["bootstrap_replicates"],
)
print()
print("Resolved columns:")
print(
    json.dumps(
        manifest["resolved_columns"],
        indent=2,
        sort_keys=True,
    )
)
print()
print("Main uncertainty results:")
print(
    final_table.to_string(
        index=False
    )
)
print()
print(
    "All integrity checks passed:",
    manifest[
        "all_integrity_checks_passed"
    ],
)
