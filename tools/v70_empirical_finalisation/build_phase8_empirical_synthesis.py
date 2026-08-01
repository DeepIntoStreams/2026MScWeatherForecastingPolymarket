#!/usr/bin/env python3
"""
Phase 8: final empirical synthesis and thesis insertion package.

This phase does not fit, select or alter any statistical model. It performs a
cross-phase integrity audit of Phases 1--7, consolidates the verified numerical
evidence, produces thesis-ready tables and LaTeX macros, registers supported and
unsupported claims, copies a deliberately small figure shortlist, and creates a
single review bundle for the final writing stage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


PHASE_ORDER = [f"phase{i}" for i in range(1, 8)]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "1": True,
            "yes": True,
            "passed": True,
            "false": False,
            "0": False,
            "no": False,
            "failed": False,
        })
        .fillna(False)
        .astype(bool)
    )


def safe_read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, **kwargs)


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    try:
        return frame.to_markdown(index=False)
    except Exception:
        columns = [str(column) for column in frame.columns]
        header = "| " + " | ".join(columns) + " |"
        divider = "| " + " | ".join(["---"] * len(columns)) + " |"
        rows = []
        for _, record in frame.iterrows():
            values = [
                str(record[column]).replace("|", r"\|")
                for column in frame.columns
            ]
            rows.append("| " + " | ".join(values) + " |")
        return "\n".join([header, divider, *rows])


def dependency_audit(
    repo_root: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for phase in PHASE_ORDER:
        root = repo_root / config["phase_roots"][phase]
        filename = config["dependency_files"][phase]
        path = root / filename
        if not path.is_file():
            rows.append({
                "phase": phase,
                "check": "dependency_file_present",
                "passed": False,
                "critical": True,
                "detail": f"missing={path}",
                "source_path": str(path.relative_to(repo_root)),
            })
            continue
        frame = pd.read_csv(path)
        required = {"passed", "critical"}
        missing = sorted(required - set(frame.columns))
        rows.append({
            "phase": phase,
            "check": "dependency_schema",
            "passed": not missing,
            "critical": True,
            "detail": f"missing={missing}",
            "source_path": str(path.relative_to(repo_root)),
        })
        if missing:
            continue
        failed = frame.loc[
            as_bool(frame["critical"]) & ~as_bool(frame["passed"])
        ]
        rows.append({
            "phase": phase,
            "check": "no_critical_failures",
            "passed": failed.empty,
            "critical": True,
            "detail": f"critical_failures={len(failed)}",
            "source_path": str(path.relative_to(repo_root)),
        })
        rows.append({
            "phase": phase,
            "check": "noncritical_limitations_registered",
            "passed": True,
            "critical": False,
            "detail": (
                f"noncritical_rows="
                f"{int((~as_bool(frame['critical'])).sum())}"
            ),
            "source_path": str(path.relative_to(repo_root)),
        })
    return pd.DataFrame(rows)


def resolve_manifest_records(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = manifest.get("files", [])
    if isinstance(records, list):
        return [record for record in records if isinstance(record, dict)]
    return []


def manifest_audit(
    repo_root: Path,
    config: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for phase in PHASE_ORDER:
        phase_root = repo_root / config["phase_roots"][phase]
        manifest_path = phase_root / config["manifest_files"][phase]
        if not manifest_path.is_file():
            summary_rows.append({
                "phase": phase,
                "manifest_present": False,
                "records": 0,
                "missing_files": np.nan,
                "size_mismatches": np.nan,
                "hash_mismatches": np.nan,
                "passed": False,
            })
            detail_rows.append({
                "phase": phase,
                "relative_path": "",
                "exists": False,
                "size_matches": False,
                "hash_matches": False,
                "detail": f"manifest_missing={manifest_path}",
            })
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = resolve_manifest_records(manifest)
        missing_count = 0
        size_mismatch_count = 0
        hash_mismatch_count = 0

        for record in records:
            relative = (
                record.get("relative_path")
                or record.get("path")
                or record.get("filename")
            )
            if not relative:
                continue
            candidate = phase_root / str(relative)
            exists = candidate.is_file()
            expected_size = record.get("size_bytes")
            expected_hash = record.get("sha256")
            size_matches = (
                exists
                and (
                    expected_size is None
                    or int(candidate.stat().st_size) == int(expected_size)
                )
            )
            actual_hash = sha256_file(candidate) if exists else ""
            hash_matches = (
                exists
                and (
                    not expected_hash
                    or actual_hash == str(expected_hash)
                )
            )
            missing_count += int(not exists)
            size_mismatch_count += int(exists and not size_matches)
            hash_mismatch_count += int(exists and not hash_matches)
            detail_rows.append({
                "phase": phase,
                "relative_path": str(relative),
                "exists": exists,
                "size_matches": size_matches,
                "hash_matches": hash_matches,
                "expected_size_bytes": expected_size,
                "actual_size_bytes": candidate.stat().st_size if exists else np.nan,
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "detail": "ok" if exists and size_matches and hash_matches else "mismatch",
            })

        passed = (
            bool(records)
            and missing_count == 0
            and size_mismatch_count == 0
            and hash_mismatch_count == 0
        )
        summary_rows.append({
            "phase": phase,
            "manifest_present": True,
            "records": len(records),
            "missing_files": missing_count,
            "size_mismatches": size_mismatch_count,
            "hash_mismatches": hash_mismatch_count,
            "passed": passed,
        })

    return pd.DataFrame(detail_rows), pd.DataFrame(summary_rows)


def standardise_candidate_summary(
    frame: pd.DataFrame,
    phase: str,
    source_path: str,
) -> pd.DataFrame:
    result = frame.copy()
    required = {"candidate_id", "quantity", "point_estimate"}
    missing = sorted(required - set(result.columns))
    if missing:
        raise ValueError(
            f"{phase} candidate summary missing columns {missing}"
        )
    for column in [
        "lower_95",
        "upper_95",
        "secondary_value",
        "secondary_quantity",
        "unit",
        "preferred_location",
    ]:
        if column not in result.columns:
            result[column] = np.nan
    result["phase"] = phase
    result["source_path"] = source_path
    result["point_estimate"] = pd.to_numeric(
        result["point_estimate"], errors="coerce"
    )
    result["lower_95"] = pd.to_numeric(
        result["lower_95"], errors="coerce"
    )
    result["upper_95"] = pd.to_numeric(
        result["upper_95"], errors="coerce"
    )
    return result[
        [
            "phase",
            "candidate_id",
            "quantity",
            "point_estimate",
            "lower_95",
            "upper_95",
            "secondary_value",
            "secondary_quantity",
            "unit",
            "preferred_location",
            "source_path",
        ]
    ]


def load_master_results(
    repo_root: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for phase, filename in config["candidate_summary_files"].items():
        phase_root = repo_root / config["phase_roots"][phase]
        path = phase_root / filename
        frame = safe_read_csv(path)
        frames.append(
            standardise_candidate_summary(
                frame,
                phase,
                str(path.relative_to(repo_root)),
            )
        )
    result = pd.concat(frames, ignore_index=True)
    duplicate_ids = result["candidate_id"].duplicated(keep=False)
    if duplicate_ids.any():
        raise ValueError(
            "Duplicate candidate IDs: "
            f"{sorted(result.loc[duplicate_ids, 'candidate_id'].unique())}"
        )
    return result


def result_map(master: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        str(row["candidate_id"]): row
        for _, row in master.iterrows()
    }


def get_value(
    results: Mapping[str, pd.Series],
    candidate_id: str,
) -> float:
    if candidate_id not in results:
        raise KeyError(f"Missing candidate result {candidate_id}")
    value = float(results[candidate_id]["point_estimate"])
    if not np.isfinite(value):
        raise ValueError(f"Non-finite result {candidate_id}")
    return value


def get_interval(
    results: Mapping[str, pd.Series],
    candidate_id: str,
) -> tuple[float, float]:
    row = results[candidate_id]
    return float(row["lower_95"]), float(row["upper_95"])


def build_main_result_selection(master: pd.DataFrame) -> pd.DataFrame:
    selected_ids = [
        "P2_MEAN",
        "P2_SD",
        "P2_UNDER",
        "P3_ENDPOINT_MAE",
        "P3_CRPS_MATERN",
        "P4_MEAN_RAW",
        "P4_MEAN_STATIC",
        "P4_MEAN_RBF",
        "P4_MEAN_MATERN",
        "P4_CONTRAST_STATIC_MINUS_RAW",
        "P4_CONTRAST_MATERN_MINUS_STATIC",
        "P4_CONTRAST_MATERN_MINUS_RBF",
        "P5_COVERAGE_50",
        "P5_COVERAGE_80",
        "P5_COVERAGE_90",
        "P5_LAG1_Z",
        "P5_LAG1_Z2",
        "P5_VARIANCE_WALD",
        "P6_JUNE_BINARY_BRIER",
        "P6_JUNE_BINARY_LOG",
        "P6_JUNE_CATEGORICAL_LOG",
        "P6_JUNE_MULTICLASS_BRIER",
        "P6_JUNE_EXTERNAL_TOTAL_VARIATION_MARKET_MATERN",
        "P6_JUNE_EXTERNAL_EXPECTED_RANK_MARKET_MINUS_MATERN",
        "P6_JUNE_EXTERNAL_REALISED_EVENT_PROBABILITY_MARKET_MINUS_MATERN",
        "P7_JUNE_TRADE_COUNT",
        "P7_JUNE_WINNING_TRADES",
        "P7_JUNE_TOTAL_NET_PNL",
        "P7_JUNE_RETURN_ON_ENTRY_CASH",
        "P7_JUNE_MAXIMUM_DRAWDOWN",
        "P7_JUNE_BREAK_EVEN_COST_PER_TRADE",
        "P7_JUNE_TOP1_CONCENTRATION",
        "P7_ATTR_RAW",
        "P7_ATTR_STATIC",
        "P7_ATTR_MATERN",
    ]
    missing = sorted(set(selected_ids) - set(master["candidate_id"]))
    if missing:
        raise ValueError(f"Missing main-result candidates: {missing}")
    order = {candidate_id: position for position, candidate_id in enumerate(selected_ids)}
    selected = master.loc[master["candidate_id"].isin(selected_ids)].copy()
    selected["display_order"] = selected["candidate_id"].map(order)
    return selected.sort_values("display_order").drop(columns="display_order")


def row_from_result(
    results: Mapping[str, pd.Series],
    candidate_id: str,
    display_name: str,
    interpretation: str,
    direction: str = "",
) -> dict[str, Any]:
    row = results[candidate_id]
    return {
        "result": display_name,
        "estimate": row["point_estimate"],
        "lower_95": row["lower_95"],
        "upper_95": row["upper_95"],
        "direction_convention": direction,
        "interpretation": interpretation,
        "evidence_id": candidate_id,
    }


def build_weather_table(results: Mapping[str, pd.Series]) -> pd.DataFrame:
    rows = [
        row_from_result(
            results,
            "P2_MEAN",
            "Mean HKO-minus-deterministic residual (°C)",
            "The deterministic forecast is systematically colder than the HKO settlement maximum.",
            "positive means HKO is warmer",
        ),
        row_from_result(
            results,
            "P2_UNDER",
            "Proportion of deterministic forecasts below HKO",
            "The cold discrepancy occurs on a large majority of date-rule observations.",
        ),
        row_from_result(
            results,
            "P3_ENDPOINT_MAE",
            "24h-to-open MAE improvement (°C)",
            "Later information modestly improves point accuracy while the settlement discrepancy persists.",
            "positive means later forecast is better",
        ),
        row_from_result(
            results,
            "P4_MEAN_RAW",
            "Raw point mean date CRPS",
            "Uncorrected deterministic benchmark.",
        ),
        row_from_result(
            results,
            "P4_MEAN_STATIC",
            "Static Gaussian mean date CRPS",
            "Most of the raw-to-Matérn improvement is achieved by local rule-specific correction.",
        ),
        row_from_result(
            results,
            "P4_MEAN_RBF",
            "RBF GP mean date CRPS",
            "Conditional GP structure adds a smaller refinement.",
        ),
        row_from_result(
            results,
            "P4_MEAN_MATERN",
            "Matérn-3/2 GP mean date CRPS",
            "Best retained weather-only predictive law.",
        ),
        row_from_result(
            results,
            "P4_CONTRAST_MATERN_MINUS_STATIC",
            "Matérn minus static paired CRPS",
            "Negative values favour Matérn; the incremental improvement is smaller than the static correction.",
            "negative favours Matérn",
        ),
        row_from_result(
            results,
            "P4_CONTRAST_MATERN_MINUS_RBF",
            "Matérn minus RBF paired CRPS",
            "Negative values favour Matérn; the kernel increment is modest.",
            "negative favours Matérn",
        ),
    ]
    return pd.DataFrame(rows)


def build_diagnostic_table(results: Mapping[str, pd.Series]) -> pd.DataFrame:
    rows = [
        row_from_result(
            results,
            "P5_COVERAGE_50",
            "Empirical 50% central coverage",
            "Close to but below nominal coverage.",
        ),
        row_from_result(
            results,
            "P5_COVERAGE_80",
            "Empirical 80% central coverage",
            "Mild undercoverage.",
        ),
        row_from_result(
            results,
            "P5_COVERAGE_90",
            "Empirical 90% central coverage",
            "Mild undercoverage.",
        ),
        row_from_result(
            results,
            "P5_LAG1_Z",
            "Lag-one standardised-residual correlation",
            "Residual serial dependence remains after postprocessing.",
        ),
        row_from_result(
            results,
            "P5_LAG1_Z2",
            "Lag-one squared-standardised-residual correlation",
            "Conditional scale dependence remains.",
        ),
        row_from_result(
            results,
            "P5_VARIANCE_WALD",
            "Conditional-variance joint p-value",
            "The homoskedastic Gaussian observation law remains misspecified.",
        ),
    ]
    return pd.DataFrame(rows)


def build_market_table(results: Mapping[str, pd.Series]) -> pd.DataFrame:
    rows = [
        row_from_result(
            results,
            "P6_JUNE_BINARY_BRIER",
            "June Matérn minus market binary Brier",
            "Positive values indicate lower realised market loss.",
            "positive favours market",
        ),
        row_from_result(
            results,
            "P6_JUNE_BINARY_LOG",
            "June Matérn minus market binary log",
            "Positive values indicate lower realised market loss.",
            "positive favours market",
        ),
        row_from_result(
            results,
            "P6_JUNE_CATEGORICAL_LOG",
            "June Matérn minus market categorical log",
            "Positive values indicate lower realised market loss.",
            "positive favours market",
        ),
        row_from_result(
            results,
            "P6_JUNE_MULTICLASS_BRIER",
            "June Matérn minus market multiclass Brier",
            "Positive values indicate lower realised market loss.",
            "positive favours market",
        ),
        row_from_result(
            results,
            "P6_JUNE_EXTERNAL_TOTAL_VARIATION_MARKET_MATERN",
            "June market-Matérn total variation",
            "The two probability books differ materially.",
        ),
        row_from_result(
            results,
            "P6_JUNE_EXTERNAL_EXPECTED_RANK_MARKET_MINUS_MATERN",
            "June expected-rank shift, market minus Matérn",
            "Positive values indicate a warmer market distribution.",
            "positive means warmer market rank",
        ),
        row_from_result(
            results,
            "P6_JUNE_EXTERNAL_REALISED_EVENT_PROBABILITY_MARKET_MINUS_MATERN",
            "June realised-event probability, market minus Matérn",
            "The market assigned more probability to the event that settled Yes.",
            "positive favours market realised-event mass",
        ),
    ]
    return pd.DataFrame(rows)


def build_trading_table(results: Mapping[str, pd.Series]) -> pd.DataFrame:
    rows = [
        row_from_result(
            results,
            "P7_JUNE_TRADE_COUNT",
            "June executed trades",
            "Frozen event-day-open policy at h=0.12.",
        ),
        row_from_result(
            results,
            "P7_JUNE_WINNING_TRADES",
            "June winning trades",
            "The result is concentrated in one profitable trade.",
        ),
        row_from_result(
            results,
            "P7_JUNE_TOTAL_NET_PNL",
            "June net PnL at one-cent cost",
            "The point estimate is slightly positive, but its interval includes zero widely.",
        ),
        row_from_result(
            results,
            "P7_JUNE_RETURN_ON_ENTRY_CASH",
            "June return on entry cash",
            "A descriptive historical ratio, not evidence of executable return.",
        ),
        row_from_result(
            results,
            "P7_JUNE_MAXIMUM_DRAWDOWN",
            "June maximum drawdown",
            "Chronological date-level path risk.",
        ),
        row_from_result(
            results,
            "P7_JUNE_BREAK_EVEN_COST_PER_TRADE",
            "June break-even cost per trade",
            "The apparent edge disappears above approximately 1.15 cents per trade.",
        ),
        row_from_result(
            results,
            "P7_JUNE_TOP1_CONCENTRATION",
            "Largest-trade absolute contribution share",
            "The PnL is highly concentrated.",
        ),
        row_from_result(
            results,
            "P7_ATTR_RAW",
            "June common-policy PnL using raw signal",
            "Raw deterministic probabilities perform poorly under the fixed policy.",
        ),
        row_from_result(
            results,
            "P7_ATTR_STATIC",
            "June common-policy PnL using static signal",
            "Static local settlement correction closes the realised raw-to-Matérn trading gap.",
        ),
        row_from_result(
            results,
            "P7_ATTR_MATERN",
            "June common-policy PnL using Matérn signal",
            "No incremental June PnL over static under the fixed policy.",
        ),
    ]
    return pd.DataFrame(rows)


def build_claims_register() -> pd.DataFrame:
    claims = [
        {
            "claim_id": "C01",
            "domain": "settlement_error",
            "status": "supported",
            "evidence_ids": "P2_MEAN|P2_UNDER",
            "safe_thesis_wording": (
                "The deterministic IFS local-day maximum exhibits a persistent "
                "cold discrepancy relative to the HKO settlement maximum."
            ),
            "prohibited_overstatement": (
                "Do not identify the discrepancy as a proven physical model bias "
                "or a single causal mechanism."
            ),
            "preferred_location": "Results 6.2 and Discussion",
        },
        {
            "claim_id": "C02",
            "domain": "forecast_attribution",
            "status": "supported",
            "evidence_ids": (
                "P4_MEAN_RAW|P4_MEAN_STATIC|"
                "P4_CONTRAST_MATERN_MINUS_STATIC|P4_CONTRAST_MATERN_MINUS_RBF"
            ),
            "safe_thesis_wording": (
                "Most of the distributional improvement is attributable to "
                "rule-specific local settlement correction, with a smaller "
                "increment from conditional Matérn GP structure."
            ),
            "prohibited_overstatement": (
                "Do not claim that the GP is the dominant source of skill."
            ),
            "preferred_location": "Results attribution and Discussion",
        },
        {
            "claim_id": "C03",
            "domain": "information_arrival",
            "status": "supported_with_scope",
            "evidence_ids": "P3_ENDPOINT_MAE|P3_CRPS_MATERN",
            "safe_thesis_wording": (
                "Later forecasts modestly improve accuracy over the retained "
                "one-day decision window."
            ),
            "prohibited_overstatement": (
                "Do not claim that later information removes the structural "
                "settlement discrepancy or identify causal information channels."
            ),
            "preferred_location": "Results or appendix",
        },
        {
            "claim_id": "C04",
            "domain": "calibration",
            "status": "supported_with_limitation",
            "evidence_ids": (
                "P5_COVERAGE_50|P5_COVERAGE_80|P5_COVERAGE_90|"
                "P5_LAG1_Z|P5_LAG1_Z2|P5_VARIANCE_WALD"
            ),
            "safe_thesis_wording": (
                "The selected predictive law is broadly useful but mildly "
                "underdispersed and retains serial and conditional-variance "
                "misspecification."
            ),
            "prohibited_overstatement": (
                "Do not describe the Gaussian GP law as fully calibrated or "
                "conditionally well specified."
            ),
            "preferred_location": "Results diagnostics and Discussion",
        },
        {
            "claim_id": "C05",
            "domain": "market_comparison",
            "status": "supported_on_june_exact_support",
            "evidence_ids": (
                "P6_JUNE_BINARY_BRIER|P6_JUNE_BINARY_LOG|"
                "P6_JUNE_CATEGORICAL_LOG|P6_JUNE_MULTICLASS_BRIER"
            ),
            "safe_thesis_wording": (
                "On the pre-designated June exact support, Polymarket has lower "
                "realised loss than the selected Matérn law under all four "
                "retained proper scores."
            ),
            "prohibited_overstatement": (
                "Do not claim universal market dominance outside the 30-date June "
                "external period."
            ),
            "preferred_location": "Results market comparison",
        },
        {
            "claim_id": "C06",
            "domain": "market_information",
            "status": "supported_descriptively",
            "evidence_ids": (
                "P6_JUNE_EXTERNAL_TOTAL_VARIATION_MARKET_MATERN|"
                "P6_JUNE_EXTERNAL_EXPECTED_RANK_MARKET_MINUS_MATERN|"
                "P6_JUNE_EXTERNAL_REALISED_EVENT_PROBABILITY_MARKET_MINUS_MATERN"
            ),
            "safe_thesis_wording": (
                "The market produces materially different probability books, "
                "shifts mass towards warmer-ranked outcomes and assigns more "
                "probability to the realised event in June."
            ),
            "prohibited_overstatement": (
                "Do not assert which private information or causal mechanism "
                "generated the market advantage."
            ),
            "preferred_location": "Results disagreement and Discussion",
        },
        {
            "claim_id": "C07",
            "domain": "trading",
            "status": "not_robust",
            "evidence_ids": (
                "P7_JUNE_TOTAL_NET_PNL|P7_JUNE_BREAK_EVEN_COST_PER_TRADE|"
                "P7_JUNE_TOP1_CONCENTRATION"
            ),
            "safe_thesis_wording": (
                "The one-cent historical point estimate is slightly positive, "
                "but it is statistically uncertain, cost-sensitive and highly "
                "concentrated."
            ),
            "prohibited_overstatement": (
                "Do not claim a persistent, scalable or executable trading edge."
            ),
            "preferred_location": "Results trading and Conclusion",
        },
        {
            "claim_id": "C08",
            "domain": "trading_attribution",
            "status": "supported_under_fixed_policy",
            "evidence_ids": "P7_ATTR_RAW|P7_ATTR_STATIC|P7_ATTR_MATERN",
            "safe_thesis_wording": (
                "Under the fixed June policy, static settlement correction "
                "accounts for the realised raw-to-Matérn PnL improvement, while "
                "the Matérn refinement adds no incremental June PnL."
            ),
            "prohibited_overstatement": (
                "Do not infer that Matérn has no forecasting value or no value "
                "under every trading rule."
            ),
            "preferred_location": "Results trading attribution",
        },
        {
            "claim_id": "C09",
            "domain": "forecast_risk",
            "status": "supported_as_stress_test",
            "evidence_ids": (
                "P7_SHIFT_M0_25|P7_SHIFT_P0_00|"
                "P7_SHIFT_P0_10|P7_SHIFT_P0_25"
            ),
            "safe_thesis_wording": (
                "Strategy PnL responds nonlinearly to predictive-mean shocks "
                "because contract selection and threshold activation are "
                "discrete."
            ),
            "prohibited_overstatement": (
                "Do not call the finite perturbation a globally smooth portfolio "
                "delta or a causal response to actual forecast releases."
            ),
            "preferred_location": "Results sensitivity and Discussion",
        },
        {
            "claim_id": "C10",
            "domain": "overall_contribution",
            "status": "supported",
            "evidence_ids": "C01|C02|C05|C07",
            "safe_thesis_wording": (
                "The contribution is a settlement-aware attribution framework "
                "linking local forecast correction, coherent event probabilities, "
                "market comparison and forecast-risk sensitivity."
            ),
            "prohibited_overstatement": (
                "Do not present the dissertation as proposing a new GP theorem or "
                "a profitable trading system."
            ),
            "preferred_location": "Introduction, Discussion and Conclusion",
        },
    ]
    return pd.DataFrame(claims)


def build_limitations_register() -> pd.DataFrame:
    rows = [
        {
            "limitation_id": "L01",
            "area": "market_timing",
            "status": "unavailable",
            "evidence": "P6_MARKET_AGE_STATUS",
            "description": (
                "Selected market-record timestamps are absent from the retained "
                "exact-support panels, so book-age and stale-record sensitivity "
                "cannot be reported without a separate data-recovery exercise."
            ),
            "required_thesis_action": (
                "State the limitation; do not fabricate contemporaneity or "
                "execution claims."
            ),
        },
        {
            "limitation_id": "L02",
            "area": "market_period_hko",
            "status": "unavailable",
            "evidence": "phase7_market_period_hko_availability.csv",
            "description": (
                "Exact market-period HKO temperatures are unavailable in the "
                "current Phase 7 evidence path."
            ),
            "required_thesis_action": (
                "Do not report exact temperature-error-to-PnL regressions; retain "
                "probability and PnL perturbation analysis."
            ),
        },
        {
            "limitation_id": "L03",
            "area": "dependence",
            "status": "remaining_misspecification",
            "evidence": "P5_LAG1_Z|P5_LAG1_Z2",
            "description": (
                "Residual and squared-residual serial dependence remains."
            ),
            "required_thesis_action": (
                "Use date and moving-block uncertainty and avoid IID claims."
            ),
        },
        {
            "limitation_id": "L04",
            "area": "conditional_variance",
            "status": "remaining_misspecification",
            "evidence": "P5_VARIANCE_WALD",
            "description": (
                "The observation-noise variance is homoskedastic within each rule, "
                "while diagnostics indicate conditional variance structure."
            ),
            "required_thesis_action": (
                "Describe the selected GP as a useful approximation, not a fully "
                "specified conditional law."
            ),
        },
        {
            "limitation_id": "L05",
            "area": "external_sample",
            "status": "small_sample",
            "evidence": "30 June settlement dates",
            "description": (
                "The external market and trading conclusions rely on 30 June dates."
            ),
            "required_thesis_action": (
                "Emphasise uncertainty and avoid universal generalisation."
            ),
        },
        {
            "limitation_id": "L06",
            "area": "execution",
            "status": "not_observed",
            "evidence": "historical market records",
            "description": (
                "Bid-ask spread, depth, fill probability, market impact and fees "
                "beyond the stylised per-trade cost are not observed."
            ),
            "required_thesis_action": (
                "Describe the backtest as a reduced-form historical decision "
                "evaluation, not an executable strategy."
            ),
        },
        {
            "limitation_id": "L07",
            "area": "forecast_source",
            "status": "interface_dependency",
            "evidence": "Open-Meteo Single Runs delivery of ECMWF IFS",
            "description": (
                "The deterministic IFS path is obtained through a third-party "
                "historical delivery interface rather than a direct ECMWF archive."
            ),
            "required_thesis_action": (
                "Document source lineage and avoid claiming direct ENS or AIFS "
                "archive access."
            ),
        },
        {
            "limitation_id": "L08",
            "area": "support",
            "status": "exact_support_restriction",
            "evidence": "375 supported keys and 350 complete books",
            "description": (
                "Thirty-seven theoretical market date-rule keys lack certified "
                "forecast support and are not imputed."
            ),
            "required_thesis_action": (
                "Report exact-support counts and preserve the no-imputation rule."
            ),
        },
        {
            "limitation_id": "L09",
            "area": "causality",
            "status": "descriptive_only",
            "evidence": "Phase 3 and Phase 6 transition analyses",
            "description": (
                "Observed forecast and market revisions do not identify causal "
                "forecast-release effects."
            ),
            "required_thesis_action": (
                "Use descriptive information-arrival language."
            ),
        },
    ]
    return pd.DataFrame(rows)


def build_insertion_ledger() -> pd.DataFrame:
    rows = [
        {
            "item_id": "I01",
            "type": "table",
            "source_output": "phase8_weather_results_table.csv",
            "recommended_location": "Results: settlement error and forecast attribution",
            "priority": "main",
            "action": "Condense to raw, static, RBF, Matérn means and two paired contrasts.",
        },
        {
            "item_id": "I02",
            "type": "table",
            "source_output": "phase8_diagnostic_results_table.csv",
            "recommended_location": "Results: distributional adequacy",
            "priority": "main_or_appendix",
            "action": "Report coverage, lag correlations and variance test compactly.",
        },
        {
            "item_id": "I03",
            "type": "table",
            "source_output": "phase8_market_results_table.csv",
            "recommended_location": "Results: exact-support market comparison",
            "priority": "main",
            "action": "Keep the four June score contrasts and one disagreement statistic.",
        },
        {
            "item_id": "I04",
            "type": "table",
            "source_output": "phase8_trading_results_table.csv",
            "recommended_location": "Results: trading sensitivity and attribution",
            "priority": "main",
            "action": "Keep frozen policy, interval, cost reversal and raw/static/Matérn attribution.",
        },
        {
            "item_id": "I05",
            "type": "figure",
            "source_output": "figures/phase8_forecast_attribution.pdf",
            "recommended_location": "Results: forecast attribution",
            "priority": "main",
            "action": "Use instead of several overlapping forecast-score figures.",
        },
        {
            "item_id": "I06",
            "type": "figure",
            "source_output": "figures/phase8_market_realised_probability.pdf",
            "recommended_location": "Results: market information",
            "priority": "main",
            "action": "Use to explain the market's June realised-event advantage.",
        },
        {
            "item_id": "I07",
            "type": "figure",
            "source_output": "figures/phase8_mean_shift_pnl_sensitivity.pdf",
            "recommended_location": "Results: forecast-risk sensitivity",
            "priority": "main",
            "action": "Use as the principal response to Wei Pan's PnL-sensitivity suggestion.",
        },
        {
            "item_id": "I08",
            "type": "figure",
            "source_output": "figures/phase8_june_trade_concentration.pdf",
            "recommended_location": "Appendix",
            "priority": "appendix",
            "action": "Support the fragility conclusion without overcrowding the main chapter.",
        },
        {
            "item_id": "I09",
            "type": "register",
            "source_output": "phase8_claims_register.csv",
            "recommended_location": "Private writing control",
            "priority": "binding",
            "action": "Use safe wording and avoid all listed overstatements.",
        },
        {
            "item_id": "I10",
            "type": "register",
            "source_output": "phase8_limitations_register.csv",
            "recommended_location": "Discussion and reproducibility appendix",
            "priority": "binding",
            "action": "Resolve only by evidence recovery; never by assumption.",
        },
        {
            "item_id": "I11",
            "type": "latex",
            "source_output": "phase8_overleaf_numbers.tex",
            "recommended_location": "Overleaf numerical source",
            "priority": "supporting",
            "action": "Use macros or manually transfer verified values.",
        },
        {
            "item_id": "I12",
            "type": "latex",
            "source_output": "phase8_overleaf_tables.tex",
            "recommended_location": "Overleaf Results chapter",
            "priority": "supporting",
            "action": "Adapt table captions and labels to the final chapter structure.",
        },
    ]
    return pd.DataFrame(rows)


def format_number(value: Any, digits: int = 6) -> str:
    try:
        number = float(value)
    except Exception:
        return ""
    if not np.isfinite(number):
        return ""
    return f"{number:.{digits}f}"


def latex_escape(text: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    result = str(text)
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def write_overleaf_numbers(
    out: Path,
    results: Mapping[str, pd.Series],
) -> None:
    macros = {
        "MeanSettlementResidual": ("P2_MEAN", 3),
        "UnderforecastShare": ("P2_UNDER", 3),
        "RawMeanCRPS": ("P4_MEAN_RAW", 3),
        "StaticMeanCRPS": ("P4_MEAN_STATIC", 3),
        "RBFMeanCRPS": ("P4_MEAN_RBF", 3),
        "MaternMeanCRPS": ("P4_MEAN_MATERN", 3),
        "MaternMinusStaticCRPS": ("P4_CONTRAST_MATERN_MINUS_STATIC", 3),
        "MaternMinusRBFCRPS": ("P4_CONTRAST_MATERN_MINUS_RBF", 3),
        "CoverageFifty": ("P5_COVERAGE_50", 3),
        "CoverageEighty": ("P5_COVERAGE_80", 3),
        "CoverageNinety": ("P5_COVERAGE_90", 3),
        "LagOneResidual": ("P5_LAG1_Z", 3),
        "LagOneSquaredResidual": ("P5_LAG1_Z2", 3),
        "VarianceWaldPValue": ("P5_VARIANCE_WALD", 3),
        "JuneBinaryBrierGap": ("P6_JUNE_BINARY_BRIER", 4),
        "JuneBinaryLogGap": ("P6_JUNE_BINARY_LOG", 4),
        "JuneCategoricalLogGap": ("P6_JUNE_CATEGORICAL_LOG", 4),
        "JuneMulticlassBrierGap": ("P6_JUNE_MULTICLASS_BRIER", 4),
        "JuneTradeCount": ("P7_JUNE_TRADE_COUNT", 0),
        "JuneWinningTradeCount": ("P7_JUNE_WINNING_TRADES", 0),
        "JuneNetPnL": ("P7_JUNE_TOTAL_NET_PNL", 4),
        "JuneBreakEvenCost": ("P7_JUNE_BREAK_EVEN_COST_PER_TRADE", 4),
        "JuneTopTradeConcentration": ("P7_JUNE_TOP1_CONCENTRATION", 3),
        "JuneRawSignalPnL": ("P7_ATTR_RAW", 4),
        "JuneStaticSignalPnL": ("P7_ATTR_STATIC", 4),
        "JuneMaternSignalPnL": ("P7_ATTR_MATERN", 4),
    }
    lines = [
        "% Auto-generated by Phase 8. Do not edit values manually.",
        "% These macros contain verified empirical point estimates.",
    ]
    for macro, (candidate_id, digits) in macros.items():
        value = get_value(results, candidate_id)
        if digits == 0:
            rendered = str(int(round(value)))
        else:
            rendered = f"{value:.{digits}f}"
        lines.append(rf"\newcommand{{\{macro}}}{{{rendered}}}")
    lower, upper = get_interval(results, "P7_JUNE_TOTAL_NET_PNL")
    lines.extend([
        rf"\newcommand{{\JunePnLLower}}{{{lower:.4f}}}",
        rf"\newcommand{{\JunePnLUpper}}{{{upper:.4f}}}",
    ])
    (out / "phase8_overleaf_numbers.tex").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def table_to_latex(
    frame: pd.DataFrame,
    caption: str,
    label: str,
) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{{latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        r"\small",
        r"\begin{tabular}{p{0.43\textwidth}rrp{0.31\textwidth}}",
        r"\toprule",
        r"Quantity & Estimate & 95\% interval & Interpretation \\",
        r"\midrule",
    ]
    for _, row in frame.iterrows():
        estimate = format_number(row["estimate"], 4)
        lower = format_number(row["lower_95"], 4)
        upper = format_number(row["upper_95"], 4)
        interval = f"[{lower}, {upper}]" if lower and upper else "--"
        lines.append(
            f"{latex_escape(row['result'])} & {estimate} & {interval} & "
            f"{latex_escape(row['interpretation'])} \\\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    return "\n".join(lines)


def write_overleaf_tables(
    out: Path,
    weather: pd.DataFrame,
    diagnostics: pd.DataFrame,
    market: pd.DataFrame,
    trading: pd.DataFrame,
) -> None:
    sections = [
        "% Auto-generated Phase 8 table drafts. Review captions and placement.",
        table_to_latex(
            weather,
            "Settlement correction and probabilistic forecast attribution.",
            "tab:phase8_weather_attribution",
        ),
        table_to_latex(
            diagnostics,
            "Distributional adequacy of the selected Matérn predictive law.",
            "tab:phase8_diagnostics",
        ),
        table_to_latex(
            market,
            "June exact-support comparison between the Matérn law and Polymarket.",
            "tab:phase8_market",
        ),
        table_to_latex(
            trading,
            "Frozen-policy trading sensitivity and attribution.",
            "tab:phase8_trading",
        ),
    ]
    (out / "phase8_overleaf_tables.tex").write_text(
        "\n\n".join(sections) + "\n",
        encoding="utf-8",
    )


def copy_figure_shortlist(
    repo_root: Path,
    out: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    figure_out = out / "figures"
    figure_out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for item in config["figure_shortlist"]:
        phase_root = repo_root / config["phase_roots"][item["phase"]]
        source = phase_root / item["source"]
        destination = figure_out / item["destination"]
        exists = source.is_file()
        if exists:
            shutil.copy2(source, destination)
        rows.append({
            "phase": item["phase"],
            "source_path": str(source.relative_to(repo_root)),
            "destination_path": (
                str(destination.relative_to(out)) if exists else ""
            ),
            "exists": exists,
            "placement": item["placement"],
            "purpose": item["purpose"],
            "sha256": sha256_file(destination) if exists else "",
        })
    return pd.DataFrame(rows)


def build_evidence_inventory(
    repo_root: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for phase in PHASE_ORDER:
        phase_root = repo_root / config["phase_roots"][phase]
        for path in sorted(phase_root.rglob("*")):
            if path.is_file():
                rows.append({
                    "phase": phase,
                    "relative_path": str(path.relative_to(repo_root)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "suffix": "".join(path.suffixes),
                })
    return pd.DataFrame(rows)


def build_cross_phase_checks(
    repo_root: Path,
    config: Mapping[str, Any],
    master: pd.DataFrame,
    dependency: pd.DataFrame,
    manifest_summary: pd.DataFrame,
    figures: pd.DataFrame,
) -> pd.DataFrame:
    results = result_map(master)
    expected = config["expected"]
    tolerance = float(config["numerical_tolerance"])
    strict = float(config["strict_tolerance"])
    rows: list[dict[str, Any]] = []

    def add(
        check: str,
        passed: bool,
        detail: str,
        critical: bool = True,
    ) -> None:
        rows.append({
            "check": check,
            "passed": bool(passed),
            "critical": bool(critical),
            "detail": detail,
        })

    add(
        "all_phase_dependencies",
        bool(
            dependency.loc[
                as_bool(dependency["critical"])
            ]["passed"].astype(bool).all()
        ),
        (
            f"critical_rows="
            f"{int(as_bool(dependency['critical']).sum())}"
        ),
    )
    add(
        "all_phase_manifests",
        bool(manifest_summary["passed"].all()),
        (
            f"phases_passed={int(manifest_summary['passed'].sum())}/"
            f"{len(manifest_summary)}"
        ),
    )
    add(
        "candidate_ids_unique",
        not master["candidate_id"].duplicated().any(),
        f"rows={len(master)}; unique_ids={master['candidate_id'].nunique()}",
    )

    key_summary_path = (
        repo_root
        / config["phase_roots"]["phase1"]
        / config["supplementary_files"]["phase1_key_summary"]
    )
    keys = pd.read_csv(key_summary_path).set_index("object")
    checks = [
        ("weather", "rows", expected["weather_rows"]),
        ("weather", "dates", expected["weather_dates"]),
        ("market_predictions", "unique_keys", expected["market_prediction_keys"]),
        ("phase10_exact_support", "rows", expected["exact_support_event_rows"]),
        ("phase10_exact_support", "dates", expected["exact_support_dates"]),
        ("phase11_trade_ledger", "rows", expected["exact_support_books"]),
    ]
    for object_name, column, reference in checks:
        calculated = int(keys.loc[object_name, column])
        add(
            f"support_{object_name}_{column}",
            calculated == int(reference),
            f"calculated={calculated}; reference={reference}",
        )

    numerical_checks = {
        "P4_MEAN_RAW": expected["raw_mean_crps"],
        "P4_MEAN_STATIC": expected["static_mean_crps"],
        "P4_MEAN_RBF": expected["rbf_mean_crps"],
        "P4_MEAN_MATERN": expected["matern_mean_crps"],
        "P4_CONTRAST_MATERN_MINUS_STATIC": expected["matern_minus_static"],
        "P4_CONTRAST_MATERN_MINUS_RBF": expected["matern_minus_rbf"],
        "P6_JUNE_BINARY_BRIER": expected["june_binary_brier_difference"],
        "P6_JUNE_BINARY_LOG": expected["june_binary_log_difference"],
        "P6_JUNE_CATEGORICAL_LOG": expected["june_categorical_log_difference"],
        "P6_JUNE_MULTICLASS_BRIER": expected["june_multiclass_brier_difference"],
        "P7_JUNE_TRADE_COUNT": expected["june_trade_count"],
        "P7_JUNE_WINNING_TRADES": expected["june_winning_trades"],
        "P7_JUNE_TOTAL_NET_PNL": expected["june_net_pnl"],
        "P7_ATTR_RAW": expected["june_raw_signal_pnl"],
        "P7_ATTR_STATIC": expected["june_static_signal_pnl"],
        "P7_ATTR_MATERN": expected["june_matern_signal_pnl"],
    }
    for candidate_id, reference in numerical_checks.items():
        calculated = get_value(results, candidate_id)
        add(
            f"reference_{candidate_id.lower()}",
            abs(calculated - float(reference)) <= tolerance,
            (
                f"calculated={calculated:.9f}; "
                f"reference={float(reference):.9f}"
            ),
        )

    mean_order = [
        get_value(results, "P4_MEAN_RAW"),
        get_value(results, "P4_MEAN_STATIC"),
        get_value(results, "P4_MEAN_RBF"),
        get_value(results, "P4_MEAN_MATERN"),
    ]
    add(
        "forecast_loss_ladder",
        mean_order[0] > mean_order[1] > mean_order[2] > mean_order[3],
        f"raw_static_rbf_matern={mean_order}",
    )
    add(
        "june_market_advantage_all_scores",
        all(
            get_value(results, candidate_id) > 0
            and get_interval(results, candidate_id)[0] > 0
            for candidate_id in [
                "P6_JUNE_BINARY_BRIER",
                "P6_JUNE_BINARY_LOG",
                "P6_JUNE_CATEGORICAL_LOG",
                "P6_JUNE_MULTICLASS_BRIER",
            ]
        ),
        "all four point estimates and ordinary lower bounds exceed zero",
    )
    add(
        "june_pnl_interval_contains_zero",
        (
            get_interval(results, "P7_JUNE_TOTAL_NET_PNL")[0] <= 0
            <= get_interval(results, "P7_JUNE_TOTAL_NET_PNL")[1]
        ),
        (
            f"interval="
            f"{get_interval(results, 'P7_JUNE_TOTAL_NET_PNL')}"
        ),
    )
    add(
        "june_static_equals_matern_fixed_policy",
        abs(
            get_value(results, "P7_ATTR_STATIC")
            - get_value(results, "P7_ATTR_MATERN")
        ) <= strict,
        (
            f"static={get_value(results, 'P7_ATTR_STATIC'):.9f}; "
            f"matern={get_value(results, 'P7_ATTR_MATERN'):.9f}"
        ),
    )
    add(
        "figure_shortlist_complete",
        bool(figures["exists"].all()),
        f"figures={int(figures['exists'].sum())}/{len(figures)}",
    )

    market_age_path = (
        repo_root
        / config["phase_roots"]["phase6"]
        / config["supplementary_files"]["phase6_market_age_status"]
    )
    market_age = pd.read_csv(market_age_path)
    add(
        "market_age_limitation_registered",
        market_age.shape[0] >= 1,
        (
            f"rows={len(market_age)}; "
            f"columns={list(market_age.columns)}"
        ),
        critical=False,
    )

    hko_path = (
        repo_root
        / config["phase_roots"]["phase7"]
        / config["supplementary_files"]["phase7_hko_status"]
    )
    hko = pd.read_csv(hko_path)
    available = (
        int(hko["rows_with_exact_hko"].iloc[0])
        if "rows_with_exact_hko" in hko.columns
        else 0
    )
    add(
        "market_period_hko_limitation_registered",
        available == 0,
        f"rows_with_exact_hko={available}",
        critical=False,
    )
    return pd.DataFrame(rows)


def build_gp_registry_summary(
    repo_root: Path,
    config: Mapping[str, Any],
) -> pd.DataFrame:
    path = (
        repo_root
        / config["phase_roots"]["phase1"]
        / config["supplementary_files"]["phase1_gp_registry"]
    )
    frame = pd.read_csv(path)
    columns = [
        column
        for column in [
            "source_path",
            "kernel_",
            "n_restarts_optimizer",
            "alpha",
            "normalize_y",
            "log_marginal_likelihood_value_",
            "random_state",
        ]
        if column in frame.columns
    ]
    result = frame[columns].copy()
    if "source_path" in result.columns:
        result["decision_rule"] = (
            result["source_path"]
            .astype(str)
            .str.extract(r"/([^/]+)_matern32_full_fit\.joblib$")[0]
        )
    return result


def write_report(
    out: Path,
    provenance: Mapping[str, Any],
    checks: pd.DataFrame,
    weather: pd.DataFrame,
    diagnostics: pd.DataFrame,
    market: pd.DataFrame,
    trading: pd.DataFrame,
    claims: pd.DataFrame,
    limitations: pd.DataFrame,
    figure_shortlist: pd.DataFrame,
    config: Mapping[str, Any],
) -> None:
    failures = checks.loc[
        as_bool(checks["critical"]) & ~as_bool(checks["passed"])
    ]
    status = "PASSED" if failures.empty else "FAILED"
    lines = [
        "# Phase 8 — Final Empirical Synthesis",
        "",
        f"Generated: `{utc_now()}`",
        "",
        f"## Overall status: **{status}**",
        "",
        "## Purpose",
        "",
        (
            "Phase 8 consolidates the completed Phase 1–7 evidence into one "
            "audited, thesis-ready package. It performs no refitting, model "
            "selection, support imputation or June-based tuning."
        ),
        "",
        "## Provenance",
        "",
        "```json",
        json.dumps(dict(provenance), indent=2, sort_keys=True),
        "```",
        "",
        "## Binding no-refit boundary",
        "",
        *[f"- {item}" for item in config["no_refit_boundary"]],
        "",
        "## Cross-phase integrity",
        "",
        markdown_table(checks),
        "",
        "## Weather and forecast attribution",
        "",
        markdown_table(weather),
        "",
        (
            "The final forecasting story is deliberately narrow: the raw "
            "deterministic forecast has a large local settlement discrepancy; "
            "the static rule-specific Gaussian law captures most of the gain; "
            "RBF and Matérn conditional structure provide smaller refinements."
        ),
        "",
        "## Distributional adequacy",
        "",
        markdown_table(diagnostics),
        "",
        (
            "The selected Matérn law is useful but not fully specified: mild "
            "undercoverage, residual serial dependence and conditional-variance "
            "structure remain."
        ),
        "",
        "## Exact-support market comparison",
        "",
        markdown_table(market),
        "",
        (
            "The June result is an external exact-support comparison. It does "
            "not imply that the market universally dominates the weather model "
            "outside this period."
        ),
        "",
        "## Trading and forecast-risk sensitivity",
        "",
        markdown_table(trading),
        "",
        (
            "The one-cent PnL point estimate is slightly positive but has a wide "
            "interval containing zero, reverses at modestly higher costs and is "
            "concentrated. Static correction accounts for the realised June "
            "raw-to-Matérn trading improvement under the fixed policy."
        ),
        "",
        "## Supported claims register",
        "",
        markdown_table(
            claims[
                [
                    "claim_id",
                    "domain",
                    "status",
                    "safe_thesis_wording",
                    "prohibited_overstatement",
                ]
            ]
        ),
        "",
        "## Limitations register",
        "",
        markdown_table(limitations),
        "",
        "## Figure shortlist",
        "",
        markdown_table(figure_shortlist),
        "",
        "## Final empirical conclusion",
        "",
        (
            "The deterministic global forecast exhibits a substantial and "
            "persistent mismatch with the local HKO settlement quantity. A "
            "simple rule-specific Gaussian correction removes most of the "
            "distributional loss, while conditional Matérn GP structure adds a "
            "smaller but supported refinement. Polymarket remains stronger on "
            "the June exact-support event-book comparison. The mapping from "
            "forecast improvement to trading performance is nonlinear, "
            "cost-sensitive and insufficient to establish a robust executable "
            "edge."
        ),
        "",
    ]
    (out / "phase8_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def build_manifest(out: Path, provenance: Mapping[str, Any]) -> None:
    records: list[dict[str, Any]] = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name not in {
            "phase8_manifest.json",
            "phase8_review_bundle.zip",
        }:
            records.append({
                "relative_path": path.relative_to(out).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    payload = {
        "phase": "phase8_final_empirical_synthesis",
        "generated_utc": utc_now(),
        "provenance": dict(provenance),
        "files": records,
    }
    (out / "phase8_manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def make_review_bundle(out: Path) -> None:
    bundle = out / "phase8_review_bundle.zip"
    with zipfile.ZipFile(
        bundle,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(out.rglob("*")):
            if path.is_file() and path != bundle:
                archive.write(
                    path,
                    path.relative_to(out).as_posix(),
                )


def self_test() -> None:
    sample = pd.DataFrame({
        "candidate_id": ["A", "B"],
        "quantity": ["one", "two"],
        "point_estimate": [1.0, 2.0],
    })
    standardised = standardise_candidate_summary(
        sample,
        "phaseX",
        "sample.csv",
    )
    assert len(standardised) == 2
    assert standardised["candidate_id"].is_unique

    claims = build_claims_register()
    assert claims["claim_id"].is_unique
    assert "persistent, scalable or executable trading edge" in (
        claims.loc[claims["claim_id"] == "C07", "prohibited_overstatement"]
        .iloc[0]
    )

    limitations = build_limitations_register()
    assert len(limitations) >= 8
    assert limitations["limitation_id"].is_unique

    assert latex_escape("A&B_1") == r"A\&B\_1"
    print("SELF-TEST: PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    if args.repo_root is None or args.spec is None or args.output_root is None:
        raise SystemExit(
            "--repo-root, --spec and --output-root are required"
        )

    repo_root = args.repo_root.resolve()
    spec_path = (repo_root / args.spec).resolve()
    out = (repo_root / args.output_root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads(spec_path.read_text(encoding="utf-8"))

    provenance = {
        "generated_utc": utc_now(),
        "working_branch": git(repo_root, "branch", "--show-current"),
        "working_commit": git(repo_root, "rev-parse", "HEAD"),
        "remote_alignment": git(
            repo_root,
            "rev-list",
            "--left-right",
            "--count",
            f"origin/{config['working_branch']}...HEAD",
            check=False,
        ),
        "no_refit": True,
        "phase_roots": config["phase_roots"],
    }
    (out / "phase8_repository_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    dependency = dependency_audit(repo_root, config)
    dependency.to_csv(
        out / "phase8_dependency_audit.csv",
        index=False,
    )

    manifest_detail, manifest_summary = manifest_audit(
        repo_root,
        config,
    )
    manifest_detail.to_csv(
        out / "phase8_phase_manifest_audit.csv.gz",
        index=False,
        compression="gzip",
    )
    manifest_summary.to_csv(
        out / "phase8_phase_manifest_summary.csv",
        index=False,
    )

    master = load_master_results(repo_root, config)
    master.to_csv(
        out / "phase8_master_results_long.csv",
        index=False,
    )
    main_selection = build_main_result_selection(master)
    main_selection.to_csv(
        out / "phase8_main_results_table.csv",
        index=False,
    )
    results = result_map(master)

    weather = build_weather_table(results)
    diagnostics = build_diagnostic_table(results)
    market = build_market_table(results)
    trading = build_trading_table(results)
    weather.to_csv(out / "phase8_weather_results_table.csv", index=False)
    diagnostics.to_csv(
        out / "phase8_diagnostic_results_table.csv",
        index=False,
    )
    market.to_csv(out / "phase8_market_results_table.csv", index=False)
    trading.to_csv(out / "phase8_trading_results_table.csv", index=False)

    claims = build_claims_register()
    limitations = build_limitations_register()
    insertion = build_insertion_ledger()
    claims.to_csv(out / "phase8_claims_register.csv", index=False)
    limitations.to_csv(
        out / "phase8_limitations_register.csv",
        index=False,
    )
    insertion.to_csv(
        out / "phase8_thesis_insertion_ledger.csv",
        index=False,
    )

    gp_registry = build_gp_registry_summary(repo_root, config)
    gp_registry.to_csv(
        out / "phase8_gp_implementation_summary.csv",
        index=False,
    )

    figures = copy_figure_shortlist(repo_root, out, config)
    figures.to_csv(
        out / "phase8_figure_shortlist.csv",
        index=False,
    )

    evidence_inventory = build_evidence_inventory(repo_root, config)
    evidence_inventory.to_csv(
        out / "phase8_evidence_inventory.csv.gz",
        index=False,
        compression="gzip",
    )

    checks = build_cross_phase_checks(
        repo_root,
        config,
        master,
        dependency,
        manifest_summary,
        figures,
    )
    checks.to_csv(
        out / "phase8_integrity_checks.csv",
        index=False,
    )

    write_overleaf_numbers(out, results)
    write_overleaf_tables(
        out,
        weather,
        diagnostics,
        market,
        trading,
    )
    write_report(
        out,
        provenance,
        checks,
        weather,
        diagnostics,
        market,
        trading,
        claims,
        limitations,
        figures,
        config,
    )

    failures = checks.loc[
        as_bool(checks["critical"]) & ~as_bool(checks["passed"])
    ]
    completion = pd.DataFrame([{
        "phase": "phase8_final_empirical_synthesis",
        "passed": failures.empty,
        "critical_failures": len(failures),
        "models_refitted": False,
        "pool_reselected": False,
        "trading_policy_reselected_on_june": False,
        "generated_utc": utc_now(),
        "working_commit": provenance["working_commit"],
    }])
    completion.to_csv(
        out / "phase8_completion_status.csv",
        index=False,
    )

    build_manifest(out, provenance)
    make_review_bundle(out)

    print("=" * 96)
    print("PHASE 8 — FINAL EMPIRICAL SYNTHESIS")
    print("=" * 96)
    print(checks.to_string(index=False))
    print()
    print(f"Output root: {out}")
    print(f"Review bundle: {out / 'phase8_review_bundle.zip'}")
    if failures.empty:
        print("FINAL STATUS: PASSED")
        return 0
    print("FINAL STATUS: FAILED")
    print(failures.to_string(index=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
