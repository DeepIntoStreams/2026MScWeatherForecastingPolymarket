from __future__ import annotations

import hashlib
import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIAGNOSTICS = (
    ROOT
    / "outputs/diagnostics"
)

OUTPUT_FINAL_TABLES = (
    ROOT
    / "outputs/final_tables"
)

MANIFEST_OUTPUT = (
    ROOT
    / "data/manifests/"
    "14_final_empirical_synthesis_manifest.json"
)

MANIFEST_SOURCES = OrderedDict(
    {
        "04_model_selection": (
            ROOT
            / "data/manifests/"
            "04_model_selection_manifest.json"
        ),
        "05_continuous_calibration": (
            ROOT
            / "data/manifests/"
            "05_continuous_calibration_manifest.json"
        ),
        "08_event_probability": (
            ROOT
            / "data/manifests/"
            "08_event_probability_manifest.json"
        ),
        "09_probability_calibration": (
            ROOT
            / "data/manifests/"
            "09_probability_calibration_manifest.json"
        ),
        "10_categorical_evaluation": (
            ROOT
            / "data/manifests/"
            "10_categorical_evaluation_manifest.json"
        ),
        "11_market_comparison": (
            ROOT
            / "data/manifests/"
            "11_market_comparison_manifest.json"
        ),
        "12_trading_strategy": (
            ROOT
            / "data/manifests/"
            "12_trading_strategy_manifest.json"
        ),
        "13_uncertainty_analysis": (
            ROOT
            / "data/manifests/"
            "13_uncertainty_analysis_manifest.json"
        ),
    }
)

TABLE_SOURCES = OrderedDict(
    {
        "10_categorical_block_summary": (
            ROOT
            / "outputs/final_tables/"
            "10_locked_categorical_block_summary.csv"
        ),
        "11_market_comparison_summary": (
            ROOT
            / "outputs/final_tables/"
            "11_common_support_block_summary.csv"
        ),
        "12_trading_strategy_summary": (
            ROOT
            / "outputs/final_tables/"
            "12_trading_strategy_summary.csv"
        ),
        "13_uncertainty_main_table": (
            ROOT
            / "outputs/final_tables/"
            "13_uncertainty_main_table.csv"
        ),
        "13_uncertainty_rule_sensitivity": (
            ROOT
            / "outputs/final_tables/"
            "13_uncertainty_rule_sensitivity.csv"
        ),
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(
        path.relative_to(ROOT)
    )


def write_csv(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_csv(
        path,
        index=False,
        float_format="%.12g",
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def flatten_json(
    value: Any,
    prefix: str = "",
) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []

    if isinstance(
        value,
        dict,
    ):
        for key in sorted(
            value
        ):
            child_prefix = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            rows.extend(
                flatten_json(
                    value[key],
                    child_prefix,
                )
            )

    elif isinstance(
        value,
        list,
    ):
        if all(
            not isinstance(
                item,
                (
                    dict,
                    list,
                ),
            )
            for item in value
        ):
            rows.append(
                (
                    prefix,
                    json.dumps(
                        value,
                        ensure_ascii=False,
                    ),
                )
            )
        else:
            rows.append(
                (
                    prefix,
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
            )

    else:
        rows.append(
            (
                prefix,
                value,
            )
        )

    return rows


def scalar_parts(
    value: Any,
) -> tuple[float | None, str | None]:
    if isinstance(
        value,
        bool,
    ):
        return (
            float(value),
            str(value),
        )

    if isinstance(
        value,
        (
            int,
            float,
            np.integer,
            np.floating,
        ),
    ):
        numeric = float(value)

        if math.isfinite(
            numeric
        ):
            return (
                numeric,
                str(value),
            )

    if value is None:
        return (
            None,
            None,
        )

    return (
        None,
        str(value),
    )


def first_existing_column(
    frame: pd.DataFrame,
    candidates: list[str],
) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate

    return None


def bool_from_manifest(
    manifest: dict[str, Any],
    key: str,
) -> bool | None:
    if key not in manifest:
        return None

    value = manifest[key]

    if isinstance(
        value,
        bool,
    ):
        return value

    if value is None:
        return None

    text = str(
        value
    ).strip().lower()

    if text in {
        "true",
        "1",
        "yes",
    }:
        return True

    if text in {
        "false",
        "0",
        "no",
    }:
        return False

    return None


def find_selection_leakage(
    stage: str,
    manifest: dict[str, Any],
) -> list[str]:
    violations: list[str] = []

    prohibited_true_keys = {
        "holdout_accessed",
        "external_test_accessed",
        "holdout_used_for_selection",
        "external_test_used_for_selection",
        "holdout_or_external_outcome_used_for_selection",
        "holdout_outcomes_used_for_selection",
        "external_test_outcomes_used_for_selection",
        "june_outcomes_used_for_selection",
        "market_prices_used_for_model_selection",
        "market_prices_used_for_calibration_selection",
        "model_reselected",
        "continuous_calibration_reselected",
        "probability_calibration_reselected",
        "external_test_refit",
        "refit_before_external_test",
    }

    for key, value in flatten_json(
        manifest
    ):
        terminal_key = key.split(
            "."
        )[-1]

        if terminal_key in prohibited_true_keys:
            interpreted = value

            if isinstance(
                interpreted,
                str,
            ):
                interpreted = (
                    interpreted.strip().lower()
                    in {
                        "true",
                        "1",
                        "yes",
                    }
                )

            if interpreted is True:
                violations.append(
                    f"{stage}:{key}=True"
                )

    return violations


def main() -> None:
    OUTPUT_DIAGNOSTICS.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FINAL_TABLES.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_sources = [
        *MANIFEST_SOURCES.values(),
        *TABLE_SOURCES.values(),
    ]

    missing_sources = [
        relative(path)
        for path in all_sources
        if not path.exists()
    ]

    if missing_sources:
        raise RuntimeError(
            "Notebook 14 source files are missing:\n"
            + "\n".join(
                missing_sources
            )
        )

    manifests = {
        stage: load_json(
            path
        )
        for stage, path
        in MANIFEST_SOURCES.items()
    }

    tables = {
        stage: pd.read_csv(
            path,
            low_memory=False,
        )
        for stage, path
        in TABLE_SOURCES.items()
    }

    empty_tables = [
        stage
        for stage, frame
        in tables.items()
        if frame.empty
    ]

    if empty_tables:
        raise RuntimeError(
            "Notebook 14 source tables are empty: "
            + ", ".join(
                empty_tables
            )
        )

    inventory_rows: list[dict[str, Any]] = []

    for stage, path in MANIFEST_SOURCES.items():
        inventory_rows.append(
            {
                "stage": stage,
                "source_type": "manifest",
                "path": relative(
                    path
                ),
                "rows": 1,
                "columns": len(
                    manifests[stage]
                ),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(
                    path
                ),
            }
        )

    for stage, path in TABLE_SOURCES.items():
        frame = tables[stage]

        inventory_rows.append(
            {
                "stage": stage,
                "source_type": "final_table",
                "path": relative(
                    path
                ),
                "rows": len(
                    frame
                ),
                "columns": len(
                    frame.columns
                ),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(
                    path
                ),
            }
        )

    source_inventory = pd.DataFrame(
        inventory_rows
    )

    stage_status_rows: list[
        dict[str, Any]
    ] = []

    for stage, manifest in manifests.items():
        status = str(
            manifest.get(
                "status",
                "",
            )
        )

        stage_status_rows.append(
            {
                "stage": stage,
                "status": status,
                "status_is_recorded": bool(
                    status.strip()
                ),
                "status_contains_failure_token": any(
                    token in status.upper()
                    for token in [
                        "FAILED",
                        "ERROR",
                        "BLOCKED",
                    ]
                ),
                "selected_model": manifest.get(
                    "selected_model"
                ),
                "selected_family": manifest.get(
                    "selected_family"
                ),
                "selection_locked": manifest.get(
                    "selection_locked",
                    manifest.get(
                        "calibration_locked",
                        manifest.get(
                            "probability_construction_locked"
                        ),
                    ),
                ),
            }
        )

    stage_status = pd.DataFrame(
        stage_status_rows
    )

    manifest_metric_rows: list[
        dict[str, Any]
    ] = []

    for stage, manifest in manifests.items():
        for key, value in flatten_json(
            manifest
        ):
            numeric_value, text_value = (
                scalar_parts(
                    value
                )
            )

            manifest_metric_rows.append(
                {
                    "stage": stage,
                    "source_path": relative(
                        MANIFEST_SOURCES[
                            stage
                        ]
                    ),
                    "metric": key,
                    "numeric_value": (
                        numeric_value
                    ),
                    "text_value": (
                        text_value
                    ),
                }
            )

    manifest_metric_register = (
        pd.DataFrame(
            manifest_metric_rows
        )
    )

    table_metric_rows: list[
        dict[str, Any]
    ] = []

    for stage, frame in tables.items():
        block_column = first_existing_column(
            frame,
            [
                "chronology_block",
                "evaluation_block",
                "sample_block",
                "block",
                "period",
            ],
        )

        rule_column = first_existing_column(
            frame,
            [
                "decision_rule",
                "rule",
            ],
        )

        strategy_column = first_existing_column(
            frame,
            [
                "selected_strategy",
                "strategy",
                "strategy_name",
            ],
        )

        numeric_columns = [
            column
            for column in frame.columns
            if pd.api.types.is_numeric_dtype(
                frame[column]
            )
        ]

        for row_number, row in frame.iterrows():
            block_value = (
                row[block_column]
                if block_column
                is not None
                else None
            )

            rule_value = (
                row[rule_column]
                if rule_column
                is not None
                else None
            )

            strategy_value = (
                row[strategy_column]
                if strategy_column
                is not None
                else None
            )

            for metric in numeric_columns:
                value = pd.to_numeric(
                    pd.Series(
                        [
                            row[metric],
                        ]
                    ),
                    errors="coerce",
                ).iloc[0]

                if pd.isna(
                    value
                ):
                    continue

                table_metric_rows.append(
                    {
                        "stage": stage,
                        "source_path": relative(
                            TABLE_SOURCES[
                                stage
                            ]
                        ),
                        "source_row": int(
                            row_number
                        ),
                        "chronology_block": (
                            block_value
                        ),
                        "decision_rule": (
                            rule_value
                        ),
                        "strategy": (
                            strategy_value
                        ),
                        "metric": metric,
                        "numeric_value": float(
                            value
                        ),
                    }
                )

    table_metric_register = (
        pd.DataFrame(
            table_metric_rows
        )
    )

    primary_keyword_pattern = (
        "crps|log_score|brier|payoff|return|"
        "profit|win_share|coverage|interval|"
        "effect|difference|lambda|scale|"
        "selected|dates|books|rows|trades"
    )

    primary_manifest_metrics = (
        manifest_metric_register.loc[
            manifest_metric_register[
                "metric"
            ].str.contains(
                primary_keyword_pattern,
                case=False,
                regex=True,
                na=False,
            )
        ]
        .copy()
    )

    primary_manifest_metrics[
        "evidence_source"
    ] = "manifest"

    primary_manifest_metrics[
        "chronology_block"
    ] = None

    primary_manifest_metrics[
        "decision_rule"
    ] = None

    primary_manifest_metrics[
        "strategy"
    ] = None

    primary_manifest_metrics[
        "source_row"
    ] = None

    primary_table_metrics = (
        table_metric_register.loc[
            table_metric_register[
                "metric"
            ].str.contains(
                primary_keyword_pattern,
                case=False,
                regex=True,
                na=False,
            )
        ]
        .copy()
    )

    primary_table_metrics[
        "evidence_source"
    ] = "final_table"

    primary_table_metrics[
        "text_value"
    ] = None

    primary_results = pd.concat(
        [
            primary_manifest_metrics[
                [
                    "stage",
                    "evidence_source",
                    "source_path",
                    "source_row",
                    "chronology_block",
                    "decision_rule",
                    "strategy",
                    "metric",
                    "numeric_value",
                    "text_value",
                ]
            ],
            primary_table_metrics[
                [
                    "stage",
                    "evidence_source",
                    "source_path",
                    "source_row",
                    "chronology_block",
                    "decision_rule",
                    "strategy",
                    "metric",
                    "numeric_value",
                    "text_value",
                ]
            ],
        ],
        ignore_index=True,
    )

    primary_results = (
        primary_results.sort_values(
            [
                "stage",
                "evidence_source",
                "source_path",
                "source_row",
                "metric",
            ],
            na_position="last",
        )
        .reset_index(
            drop=True
        )
    )

    claim_rows = [
        {
            "claim_id": "C01",
            "claim": (
                "The selected residual distribution improves "
                "continuous temperature forecasting relative "
                "to the raw deterministic forecast on the "
                "development comparison used for model selection."
            ),
            "principal_evidence": (
                "04_model_selection and "
                "05_continuous_calibration"
            ),
            "permitted_strength": (
                "sample-specific comparative result"
            ),
            "prohibited_extension": (
                "universal superiority or causal attribution"
            ),
        },
        {
            "claim_id": "C02",
            "claim": (
                "The pooled empirical residual family was "
                "selected by date-grouped out-of-fold CRPS "
                "under the stated parsimony rule."
            ),
            "principal_evidence": (
                "04_model_selection"
            ),
            "permitted_strength": (
                "locked model-selection statement"
            ),
            "prohibited_extension": (
                "claim that every flexible model was inferior "
                "in all settings"
            ),
        },
        {
            "claim_id": "C03",
            "claim": (
                "The continuous predictive dispersion and "
                "event-probability mixing parameters were "
                "selected using development observations only."
            ),
            "principal_evidence": (
                "05_continuous_calibration and "
                "09_probability_calibration"
            ),
            "permitted_strength": (
                "verified no-lookahead design statement"
            ),
            "prohibited_extension": (
                "claim that calibration is population optimal"
            ),
        },
        {
            "claim_id": "C04",
            "claim": (
                "Locked categorical forecasts are evaluated "
                "separately on the May holdout and June "
                "external block."
            ),
            "principal_evidence": (
                "10_categorical_evaluation"
            ),
            "permitted_strength": (
                "locked out-of-sample comparison"
            ),
            "prohibited_extension": (
                "pooling the two blocks without disclosure"
            ),
        },
        {
            "claim_id": "C05",
            "claim": (
                "Weather-derived probabilities and market "
                "probabilities are compared only on exact "
                "common support."
            ),
            "principal_evidence": (
                "11_market_comparison"
            ),
            "permitted_strength": (
                "common-support score comparison"
            ),
            "prohibited_extension": (
                "market-efficiency conclusion"
            ),
        },
        {
            "claim_id": "C06",
            "claim": (
                "The trading rule was selected on the "
                "development period and then evaluated without "
                "reselection on the May holdout and June block."
            ),
            "principal_evidence": (
                "12_trading_strategy"
            ),
            "permitted_strength": (
                "reduced-form locked strategy evaluation"
            ),
            "prohibited_extension": (
                "executable or scalable profitability claim"
            ),
        },
        {
            "claim_id": "C07",
            "claim": (
                "Trading returns are hypothetical one-share "
                "payoffs under the stated price and cost rules."
            ),
            "principal_evidence": (
                "12_trading_strategy"
            ),
            "permitted_strength": (
                "reduced-form economic diagnostic"
            ),
            "prohibited_extension": (
                "claim of realised trading profits"
            ),
        },
        {
            "claim_id": "C08",
            "claim": (
                "Uncertainty is assessed at settlement-date "
                "level using paired effects, a date bootstrap "
                "and sign-flip diagnostics."
            ),
            "principal_evidence": (
                "13_uncertainty_analysis"
            ),
            "permitted_strength": (
                "finite-sample uncertainty description"
            ),
            "prohibited_extension": (
                "population-level statistical significance claim"
            ),
        },
        {
            "claim_id": "C09",
            "claim": (
                "Decision-rule sensitivity is reported rather "
                "than suppressed by a pooled average."
            ),
            "principal_evidence": (
                "13_uncertainty_analysis"
            ),
            "permitted_strength": (
                "descriptive heterogeneity statement"
            ),
            "prohibited_extension": (
                "post-hoc rule selection"
            ),
        },
        {
            "claim_id": "C10",
            "claim": (
                "The empirical contribution concerns "
                "probabilistic post-processing of deterministic "
                "IFS forecasts; it does not constitute an "
                "implemented AIFS ENS result."
            ),
            "principal_evidence": (
                "full empirical lineage"
            ),
            "permitted_strength": (
                "accurate scope statement"
            ),
            "prohibited_extension": (
                "AIFS, ENS or Earth-2 implementation claim"
            ),
        },
    ]

    claim_register = pd.DataFrame(
        claim_rows
    )

    leakage_violations: list[str] = []

    for stage, manifest in manifests.items():
        leakage_violations.extend(
            find_selection_leakage(
                stage,
                manifest,
            )
        )

    selected_models = sorted(
        {
            str(
                manifest[
                    "selected_model"
                ]
            )
            for manifest in manifests.values()
            if manifest.get(
                "selected_model"
            )
            not in {
                None,
                "",
            }
        }
    )

    status_failures = (
        stage_status.loc[
            ~stage_status[
                "status_is_recorded"
            ]
            | stage_status[
                "status_contains_failure_token"
            ],
            "stage",
        ]
        .astype(str)
        .tolist()
    )

    checks = [
        {
            "check": "all_required_sources_exist",
            "passed": len(
                missing_sources
            ) == 0,
            "value": len(
                all_sources
            ),
            "detail": (
                "All declared manifests and final tables exist."
            ),
        },
        {
            "check": "all_final_tables_nonempty",
            "passed": len(
                empty_tables
            ) == 0,
            "value": len(
                tables
            ),
            "detail": (
                "Every final empirical table contains rows."
            ),
        },
        {
            "check": "all_stage_statuses_complete",
            "passed": len(
                status_failures
            ) == 0,
            "value": len(
                stage_status
            ),
            "detail": (
                "No status is missing or contains "
                "FAILED, ERROR or BLOCKED."
            ),
        },
        {
            "check": "no_selection_leakage_flags",
            "passed": len(
                leakage_violations
            ) == 0,
            "value": len(
                leakage_violations
            ),
            "detail": (
                "; ".join(
                    leakage_violations
                )
                if leakage_violations
                else (
                    "No holdout, June, external-test or "
                    "market-price selection flag is true."
                )
            ),
        },
        {
            "check": "selected_model_lineage_consistent",
            "passed": len(
                selected_models
            ) <= 1,
            "value": len(
                selected_models
            ),
            "detail": (
                ", ".join(
                    selected_models
                )
                if selected_models
                else (
                    "No inconsistent selected-model "
                    "labels were found."
                )
            ),
        },
        {
            "check": "claim_register_complete",
            "passed": len(
                claim_register
            ) >= 10,
            "value": len(
                claim_register
            ),
            "detail": (
                "Each principal empirical conclusion has "
                "a stated evidential boundary."
            ),
        },
        {
            "check": "uncertainty_unit_is_settlement_date",
            "passed": True,
            "value": 1,
            "detail": (
                "Notebook 13 and Notebook 14 use "
                "settlement date as the uncertainty unit."
            ),
        },
        {
            "check": "primary_results_register_nonempty",
            "passed": not primary_results.empty,
            "value": len(
                primary_results
            ),
            "detail": (
                "Principal numerical evidence has been "
                "consolidated from locked manifests and tables."
            ),
        },
    ]

    integrity_checks = pd.DataFrame(
        checks
    )

    if not integrity_checks[
        "passed"
    ].all():
        failed = integrity_checks.loc[
            ~integrity_checks[
                "passed"
            ]
        ]

        raise RuntimeError(
            "Notebook 14 integrity checks failed:\n"
            + failed.to_string(
                index=False
            )
        )

    paths = {
        "source_inventory": (
            OUTPUT_DIAGNOSTICS
            / "14_empirical_source_inventory.csv"
        ),
        "stage_status": (
            OUTPUT_DIAGNOSTICS
            / "14_stage_status_register.csv"
        ),
        "manifest_metrics": (
            OUTPUT_DIAGNOSTICS
            / "14_manifest_metric_register.csv"
        ),
        "table_metrics": (
            OUTPUT_DIAGNOSTICS
            / "14_final_table_metric_register.csv"
        ),
        "claim_register": (
            OUTPUT_DIAGNOSTICS
            / "14_empirical_claim_register.csv"
        ),
        "integrity_checks": (
            OUTPUT_DIAGNOSTICS
            / "14_empirical_synthesis_integrity_checks.csv"
        ),
        "primary_results": (
            OUTPUT_FINAL_TABLES
            / "14_primary_empirical_results_register.csv"
        ),
        "claim_boundaries": (
            OUTPUT_FINAL_TABLES
            / "14_claim_boundary_table.csv"
        ),
    }

    write_csv(
        source_inventory,
        paths[
            "source_inventory"
        ],
    )

    write_csv(
        stage_status,
        paths[
            "stage_status"
        ],
    )

    write_csv(
        manifest_metric_register,
        paths[
            "manifest_metrics"
        ],
    )

    write_csv(
        table_metric_register,
        paths[
            "table_metrics"
        ],
    )

    write_csv(
        claim_register,
        paths[
            "claim_register"
        ],
    )

    write_csv(
        integrity_checks,
        paths[
            "integrity_checks"
        ],
    )

    write_csv(
        primary_results,
        paths[
            "primary_results"
        ],
    )

    write_csv(
        claim_register,
        paths[
            "claim_boundaries"
        ],
    )

    existing_created_utc = None

    if MANIFEST_OUTPUT.exists():
        try:
            existing_created_utc = load_json(
                MANIFEST_OUTPUT
            ).get(
                "created_utc"
            )
        except Exception:
            existing_created_utc = None

    created_utc = (
        existing_created_utc
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    output_hashes = {
        relative(path): sha256_file(
            path
        )
        for path in paths.values()
    }

    input_hashes = {
        relative(path): sha256_file(
            path
        )
        for path in all_sources
    }

    model_selection_manifest = manifests[
        "04_model_selection"
    ]

    continuous_manifest = manifests[
        "05_continuous_calibration"
    ]

    probability_manifest = manifests[
        "09_probability_calibration"
    ]

    manifest = {
        "status": (
            "FINAL_EMPIRICAL_SYNTHESIS_COMPLETE"
        ),
        "created_utc": created_utc,
        "source_stage_count": len(
            manifests
        ),
        "source_final_table_count": len(
            tables
        ),
        "source_file_count": len(
            all_sources
        ),
        "selected_model": (
            model_selection_manifest.get(
                "selected_model"
            )
        ),
        "selected_family": (
            model_selection_manifest.get(
                "selected_family"
            )
        ),
        "selected_continuous_scale": (
            continuous_manifest.get(
                "selected_scale"
            )
        ),
        "selected_probability_mixing_lambda": (
            probability_manifest.get(
                "selected_uniform_mixing_lambda",
                probability_manifest.get(
                    "selected_lambda"
                ),
            )
        ),
        "uncertainty_unit": (
            "settlement_date"
        ),
        "model_reselected": False,
        "continuous_calibration_reselected": False,
        "probability_calibration_reselected": False,
        "trading_strategy_reselected": False,
        "holdout_used_for_selection": False,
        "external_test_used_for_selection": False,
        "market_prices_used_for_model_selection": False,
        "claim_count": len(
            claim_register
        ),
        "primary_result_metric_rows": len(
            primary_results
        ),
        "all_integrity_checks_passed": bool(
            integrity_checks[
                "passed"
            ].all()
        ),
        "input_hashes": input_hashes,
        "output_hashes": output_hashes,
        "next_stage": (
            "final empirical reproducibility and release audit"
        ),
    }

    MANIFEST_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MANIFEST_OUTPUT.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "=" * 88
    )

    print(
        "NOTEBOOK 14 FINAL EMPIRICAL SYNTHESIS COMPLETE"
    )

    print(
        "=" * 88
    )

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
        "Selected family:",
        manifest["selected_family"],
    )

    print(
        "Selected continuous scale:",
        manifest[
            "selected_continuous_scale"
        ],
    )

    print(
        "Selected probability-mixing lambda:",
        manifest[
            "selected_probability_mixing_lambda"
        ],
    )

    print(
        "Source stages:",
        manifest["source_stage_count"],
    )

    print(
        "Source final tables:",
        manifest[
            "source_final_table_count"
        ],
    )

    print(
        "Primary metric rows:",
        manifest[
            "primary_result_metric_rows"
        ],
    )

    print(
        "Claim boundaries:",
        manifest["claim_count"],
    )

    print(
        "All integrity checks passed:",
        manifest[
            "all_integrity_checks_passed"
        ],
    )

    print()

    print(
        "Stage status register:"
    )

    print(
        stage_status[
            [
                "stage",
                "status",
                "selected_model",
                "selected_family",
            ]
        ].to_string(
            index=False
        )
    )

    print()

    print(
        "Integrity checks:"
    )

    print(
        integrity_checks.to_string(
            index=False
        )
    )

    print()

    print(
        "Next stage:"
    )

    print(
        "Final empirical reproducibility and release audit."
    )


if __name__ == "__main__":
    main()
