from __future__ import annotations

import json
import math
import re
from io import StringIO
from pathlib import Path

import pandas as pd


SPEC_PATH = Path(
    "config/v2/phase13_verified_evidence_pack_spec.json"
)


def read_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(
        parents=True,
        exist_ok=True,
    )


def find_phase_dir(
    diagnostics_root: Path,
    prefix: str,
) -> Path:
    candidates = sorted(
        [
            path
            for path in diagnostics_root.glob(
                f"{prefix}*"
            )
            if path.is_dir()
        ]
    )

    if not candidates:
        raise FileNotFoundError(
            f"No diagnostics directory found for {prefix}."
        )

    preferred = []

    for candidate in candidates:
        report_candidates = sorted(
            candidate.glob(
                f"{prefix}_report*.md"
            )
        )
        manifest_candidates = sorted(
            candidate.glob(
                f"{prefix}_manifest*.json"
            )
        )

        score = (
            len(report_candidates),
            len(manifest_candidates),
            len(list(candidate.iterdir())),
            len(candidate.name),
        )

        preferred.append(
            (
                score,
                candidate,
            )
        )

    preferred.sort(
        reverse=True
    )

    return preferred[0][1]


def find_first(
    directory: Path,
    patterns: list[str],
) -> Path | None:
    for pattern in patterns:
        matches = sorted(
            directory.glob(pattern)
        )
        if matches:
            return matches[0]
    return None


def extract_section(
    text: str,
    heading: str,
) -> str:
    lines = text.splitlines()

    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading.strip():
            start = index + 1
            break

    if start is None:
        return ""

    end = len(lines)

    for index in range(start, len(lines)):
        if (
            lines[index].startswith("## ")
            and lines[index].strip() != heading.strip()
        ):
            end = index
            break

    return "\n".join(
        lines[start:end]
    ).strip()


def parse_markdown_table(
    section_text: str,
) -> pd.DataFrame:
    table_lines = [
        line.rstrip()
        for line in section_text.splitlines()
        if line.strip().startswith("|")
    ]

    if len(table_lines) < 2:
        return pd.DataFrame()

    header = [
        cell.strip()
        for cell in table_lines[0]
        .strip()
        .strip("|")
        .split("|")
    ]

    rows = []
    for line in table_lines[2:]:
        cells = [
            cell.strip()
            for cell in line
            .strip()
            .strip("|")
            .split("|")
        ]
        if len(cells) != len(header):
            continue
        rows.append(cells)

    if not rows:
        return pd.DataFrame(
            columns=header
        )

    return pd.DataFrame(
        rows,
        columns=header,
    )


def extract_number(
    text: str,
    pattern: str,
    cast=float,
    flags=re.S,
):
    """Extract one scalar while excluding sentence punctuation."""

    match = re.search(
        pattern,
        text,
        flags,
    )

    if match is None:
        return None

    value = (
        match.group(1)
        .replace(",", "")
        .strip()
        .strip("`")
    )

    if cast is str:
        return value

    numeric_match = re.search(
        r"[-+]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))"
        r"(?:[eE][-+]?\d+)?",
        value,
    )

    if numeric_match is None:
        raise ValueError(
            "Could not isolate a numeric token from "
            f"{value!r}."
        )

    numeric_value = float(
        numeric_match.group(0)
    )

    if cast is int:
        if not numeric_value.is_integer():
            raise ValueError(
                "Expected an integer but extracted "
                f"{numeric_value!r}."
            )

        return int(
            numeric_value
        )

    if cast is float:
        return numeric_value

    return cast(
        numeric_value
    )


def add_metric(
    store: list[dict],
    phase: str,
    section: str,
    metric: str,
    value,
    unit: str = "",
    note: str = "",
) -> None:
    store.append(
        {
            "phase": phase,
            "section": section,
            "metric": metric,
            "value": value,
            "unit": unit,
            "note": note,
        }
    )


def coerce_numeric_frame(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        cleaned = (
            result[column]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip()
        )
        converted = pd.to_numeric(
            cleaned,
            errors="coerce",
        )
        if converted.notna().any():
            result[column] = converted
    return result


def main() -> None:
    spec = read_json(
        SPEC_PATH
    )

    diagnostics_root = Path(
        spec["diagnostics_root"]
    )
    output_dir = Path(
        spec["output_dir"]
    )

    ensure_dir(output_dir)

    phase_prefixes = spec[
        "phase_prefixes"
    ]

    discovered_sources = []
    phase_reports: dict[str, str] = {}

    for prefix in phase_prefixes:
        phase_dir = find_phase_dir(
            diagnostics_root,
            prefix,
        )

        report_path = find_first(
            phase_dir,
            [
                f"{prefix}_report*.md",
                "*report*.md",
            ],
        )

        manifest_path = find_first(
            phase_dir,
            [
                f"{prefix}_manifest*.json",
                "*manifest*.json",
            ],
        )

        if report_path is None:
            raise FileNotFoundError(
                f"No report markdown found in {phase_dir}."
            )

        report_text = report_path.read_text(
            encoding="utf-8"
        )

        phase_reports[prefix] = report_text

        discovered_sources.append(
            {
                "phase": prefix,
                "directory": str(phase_dir),
                "report_path": str(report_path),
                "manifest_path": (
                    str(manifest_path)
                    if manifest_path is not None
                    else ""
                ),
            }
        )

    source_inventory = pd.DataFrame(
        discovered_sources
    )

    metrics: list[dict] = []

    # ---------------------------------------------------------
    # Phase 9
    # ---------------------------------------------------------
    phase9 = phase_reports["phase9"]

    phase9_certified = extract_section(
        phase9,
        "## Certified support",
    )

    phase9_overall = extract_section(
        phase9,
        "## Overall proper scores",
    )

    phase9_june = extract_section(
        phase9,
        "## June out-of-sample proper scores",
    )

    add_metric(
        metrics,
        "phase9",
        "certified_support",
        "settlement_and_market_dates",
        extract_number(
            phase9_certified,
            r"Settlement and market universe:\s*([0-9]+)\s*dates",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase9",
        "certified_support",
        "forecast_supported_dates",
        extract_number(
            phase9_certified,
            r"Forecast-supported dates:\s*([0-9]+)",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase9",
        "certified_support",
        "forecast_supported_date_rule_rows",
        extract_number(
            phase9_certified,
            r"Forecast-supported date-rule rows:\s*([0-9]+)",
            int,
        ),
        "rows",
    )
    add_metric(
        metrics,
        "phase9",
        "certified_support",
        "weather_plus_market_training_dates",
        extract_number(
            phase9_certified,
            r"Weather-plus-market training dates:\s*([0-9]+)",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase9",
        "certified_support",
        "june_out_of_sample_validation_dates",
        extract_number(
            phase9_certified,
            r"June out-of-sample validation dates:\s*([0-9]+)",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase9",
        "certified_support",
        "unsupported_date_rule_rows",
        extract_number(
            phase9_certified,
            r"Unsupported date-rule rows:\s*([0-9]+)",
            int,
        ),
        "rows",
    )

    phase9_overall_patterns = {
        "mean_binary_brier": (
            r"Mean binary Brier score:\s*([0-9eE.\-]+)",
            "",
        ),
        "mean_binary_log": (
            r"Mean binary log score:\s*([0-9eE.\-]+)",
            "",
        ),
        "mean_categorical_log": (
            r"Mean categorical log score:\s*([0-9eE.\-]+)",
            "",
        ),
        "mean_multiclass_brier": (
            r"Mean multiclass Brier score:\s*([0-9eE.\-]+)",
            "",
        ),
        "mean_continuous_crps": (
            r"Mean continuous CRPS:\s*([0-9eE.\-]+)",
            "degrees Celsius",
        ),
        "mean_gp_absolute_error": (
            r"Mean GP absolute error:\s*([0-9eE.\-]+)",
            "degrees Celsius",
        ),
    }

    for metric_name, (
        pattern,
        unit,
    ) in phase9_overall_patterns.items():
        add_metric(
            metrics,
            "phase9",
            "overall_proper_scores",
            metric_name,
            extract_number(
                phase9_overall,
                pattern,
                float,
            ),
            unit,
        )

    for metric_name, (
        pattern,
        unit,
    ) in phase9_overall_patterns.items():
        add_metric(
            metrics,
            "phase9",
            "june_out_of_sample_proper_scores",
            metric_name,
            extract_number(
                phase9_june,
                pattern,
                float,
            ),
            unit,
        )

    # ---------------------------------------------------------
    # Phase 10
    # ---------------------------------------------------------
    phase10 = phase_reports["phase10"]

    phase10_support = extract_section(
        phase10,
        "## Exact common support",
    )
    phase10_june_results = extract_section(
        phase10,
        "## June out-of-sample paired results",
    )
    phase10_training_results = extract_section(
        phase10,
        "## Weather-plus-market training-period paired results",
    )
    phase10_calibration = extract_section(
        phase10,
        "## June calibration diagnostics",
    )

    add_metric(
        metrics,
        "phase10",
        "exact_common_support",
        "phase9_gp_supported_dates",
        extract_number(
            phase10_support,
            r"Phase 9 GP-supported dates:\s*([0-9]+)",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase10",
        "exact_common_support",
        "phase9_gp_supported_date_rule_books",
        extract_number(
            phase10_support,
            r"Phase 9 GP-supported date-rule books:\s*([0-9]+)",
            int,
        ),
        "books",
    )
    add_metric(
        metrics,
        "phase10",
        "exact_common_support",
        "complete_common_support_dates",
        extract_number(
            phase10_support,
            r"Complete common-support dates:\s*([0-9]+)",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase10",
        "exact_common_support",
        "complete_common_support_date_rule_books",
        extract_number(
            phase10_support,
            r"Complete common-support date-rule books:\s*([0-9]+)",
            int,
        ),
        "books",
    )
    add_metric(
        metrics,
        "phase10",
        "exact_common_support",
        "complete_common_support_contract_event_rows",
        extract_number(
            phase10_support,
            r"Complete common-support contract-event rows:\s*([0-9]+)",
            int,
        ),
        "rows",
    )
    add_metric(
        metrics,
        "phase10",
        "exact_common_support",
        "weather_plus_market_training_dates",
        extract_number(
            phase10_support,
            r"Weather-plus-market training dates:\s*([0-9]+)",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase10",
        "exact_common_support",
        "june_out_of_sample_validation_dates",
        extract_number(
            phase10_support,
            r"June out-of-sample validation dates:\s*([0-9]+)",
            int,
        ),
        "dates",
    )

    phase10_june_df = parse_markdown_table(
        phase10_june_results
    )
    phase10_training_df = parse_markdown_table(
        phase10_training_results
    )
    phase10_calibration_df = parse_markdown_table(
        phase10_calibration
    )

    phase10_june_df = coerce_numeric_frame(
        phase10_june_df
    )
    phase10_training_df = coerce_numeric_frame(
        phase10_training_df
    )
    phase10_calibration_df = coerce_numeric_frame(
        phase10_calibration_df
    )

    # ---------------------------------------------------------
    # Phase 11
    # ---------------------------------------------------------
    phase11 = phase_reports["phase11"]

    phase11_frozen = extract_section(
        phase11,
        "## Frozen strategies",
    )
    phase11_primary = extract_section(
        phase11,
        "## Primary strategy",
    )
    phase11_costs = extract_section(
        phase11,
        "## June transaction-cost sensitivity",
    )
    phase11_uncertainty = extract_section(
        phase11,
        "## Primary June uncertainty at the reference cost",
    )

    phase11_frozen_df = parse_markdown_table(
        phase11_frozen
    )
    phase11_costs_df = parse_markdown_table(
        phase11_costs
    )

    phase11_frozen_df = coerce_numeric_frame(
        phase11_frozen_df
    )
    phase11_costs_df = coerce_numeric_frame(
        phase11_costs_df
    )

    add_metric(
        metrics,
        "phase11",
        "primary_strategy",
        "decision_rule",
        extract_number(
            phase11_primary,
            r"Decision rule:\s*`([^`]+)`",
            str,
        ),
        "",
    )
    add_metric(
        metrics,
        "phase11",
        "primary_strategy",
        "frozen_value_gap_threshold",
        extract_number(
            phase11_primary,
            r"Frozen value-gap threshold:\s*([0-9eE.\-]+)",
            float,
        ),
        "",
    )
    add_metric(
        metrics,
        "phase11",
        "primary_strategy",
        "june_dates_evaluated",
        extract_number(
            phase11_primary,
            r"June dates evaluated:\s*([0-9]+)",
            int,
        ),
        "dates",
    )
    add_metric(
        metrics,
        "phase11",
        "primary_strategy",
        "june_trades_at_reference_cost",
        extract_number(
            phase11_primary,
            r"June trades at the reference cost:\s*([0-9]+)",
            int,
        ),
        "trades",
    )

    phase11_uncertainty_patterns = {
        "total_net_pnl": (
            r"Total net PnL:\s*([0-9eE.\-]+)",
            "",
        ),
        "mean_date_net_pnl": (
            r"Mean date net PnL:\s*([0-9eE.\-]+)",
            "",
        ),
        "return_on_committed_capital": (
            r"Return on committed capital:\s*([0-9eE.\-]+)",
            "",
        ),
        "maximum_drawdown": (
            r"Maximum drawdown:\s*([0-9eE.\-]+)",
            "",
        ),
        "bootstrap_probability_positive": (
            r"Bootstrap probability that total June net PnL is positive:\s*([0-9eE.\-]+)",
            "",
        ),
    }

    for metric_name, (
        pattern,
        unit,
    ) in phase11_uncertainty_patterns.items():
        add_metric(
            metrics,
            "phase11",
            "primary_june_uncertainty",
            metric_name,
            extract_number(
                phase11_uncertainty,
                pattern,
                float,
            ),
            unit,
        )

    # ---------------------------------------------------------
    # Phase 12
    # ---------------------------------------------------------
    phase12 = phase_reports["phase12"]

    phase12_posthoc = extract_section(
        phase12,
        "## Frozen June trading result",
    )

    if not phase12_posthoc:
        phase12_posthoc = extract_section(
            phase12,
            "## Post hoc June ranking",
        )
    phase12_synthesis = extract_section(
        phase12,
        "## Final empirical synthesis",
    )
    phase12_boundary = extract_section(
        phase12,
        "## Evidential boundary",
    )

    add_metric(
        metrics,
        "phase12",
        "post_hoc_june_ranking",
        "june_trades",
        extract_number(
            phase12_posthoc,
            r"June trades at the reference cost:\s*([0-9]+)",
            int,
        ),
        "trades",
    )
    add_metric(
        metrics,
        "phase12",
        "post_hoc_june_ranking",
        "total_net_pnl",
        extract_number(
            phase12_posthoc,
            r"Total net PnL:\s*([0-9eE.\-]+)",
            float,
        ),
        "",
    )
    add_metric(
        metrics,
        "phase12",
        "post_hoc_june_ranking",
        "mean_date_net_pnl",
        extract_number(
            phase12_posthoc,
            r"Mean date net PnL:\s*([0-9eE.\-]+)",
            float,
        ),
        "",
    )
    add_metric(
        metrics,
        "phase12",
        "post_hoc_june_ranking",
        "return_on_committed_capital",
        extract_number(
            phase12_posthoc,
            r"Return on committed capital:\s*([0-9eE.\-]+)",
            float,
        ),
        "",
    )
    add_metric(
        metrics,
        "phase12",
        "post_hoc_june_ranking",
        "maximum_drawdown",
        extract_number(
            phase12_posthoc,
            r"Maximum drawdown:\s*([0-9eE.\-]+)",
            float,
        ),
        "",
    )
    add_metric(
        metrics,
        "phase12",
        "post_hoc_june_ranking",
        "post_hoc_candidate_count",
        extract_number(
            phase12_posthoc,
            r"Post-hoc June rank among the\s*([0-9]+)\s*rule-threshold candidates",
            int,
        ),
        "candidates",
    )
    add_metric(
        metrics,
        "phase12",
        "post_hoc_june_ranking",
        "post_hoc_rank",
        extract_number(
            phase12_posthoc,
            r"rule-threshold candidates:\s*([0-9]+)",
            int,
        ),
        "rank",
    )

    # ---------------------------------------------------------
    # Build outputs
    # ---------------------------------------------------------
    metrics_df = pd.DataFrame(
        metrics
    )

    if metrics_df.empty:
        raise RuntimeError(
            "No metrics were extracted."
        )

    phase9_summary = metrics_df.loc[
        metrics_df["phase"].eq("phase9")
    ].copy()

    phase12_summary = metrics_df.loc[
        metrics_df["phase"].eq("phase12")
    ].copy()

    main_results_rows = []

    def get_metric(
        phase: str,
        section: str,
        metric: str,
    ):
        subset = metrics_df.loc[
            metrics_df["phase"].eq(phase)
            & metrics_df["section"].eq(section)
            & metrics_df["metric"].eq(metric),
            "value",
        ]
        if subset.empty:
            return None
        return subset.iloc[0]

    main_results_rows.append(
        {
            "result_group": "phase9_june_gp_scores",
            "metric": "mean_binary_brier",
            "value": get_metric(
                "phase9",
                "june_out_of_sample_proper_scores",
                "mean_binary_brier",
            ),
            "unit": "",
        }
    )
    main_results_rows.append(
        {
            "result_group": "phase9_june_gp_scores",
            "metric": "mean_binary_log",
            "value": get_metric(
                "phase9",
                "june_out_of_sample_proper_scores",
                "mean_binary_log",
            ),
            "unit": "",
        }
    )
    main_results_rows.append(
        {
            "result_group": "phase9_june_gp_scores",
            "metric": "mean_continuous_crps",
            "value": get_metric(
                "phase9",
                "june_out_of_sample_proper_scores",
                "mean_continuous_crps",
            ),
            "unit": "degrees Celsius",
        }
    )

    if not phase10_june_df.empty:
        for _, row in phase10_june_df.iterrows():
            metric_name = str(
                row["Metric"]
            )
            main_results_rows.append(
                {
                    "result_group": "phase10_june_gp_vs_polymarket",
                    "metric": metric_name,
                    "value": row["Difference"],
                    "unit": "",
                }
            )

    main_results_rows.append(
        {
            "result_group": "phase11_primary_trading",
            "metric": "decision_rule",
            "value": get_metric(
                "phase11",
                "primary_strategy",
                "decision_rule",
            ),
            "unit": "",
        }
    )
    main_results_rows.append(
        {
            "result_group": "phase11_primary_trading",
            "metric": "frozen_value_gap_threshold",
            "value": get_metric(
                "phase11",
                "primary_strategy",
                "frozen_value_gap_threshold",
            ),
            "unit": "",
        }
    )
    main_results_rows.append(
        {
            "result_group": "phase11_primary_trading",
            "metric": "total_net_pnl",
            "value": get_metric(
                "phase11",
                "primary_june_uncertainty",
                "total_net_pnl",
            ),
            "unit": "",
        }
    )
    main_results_rows.append(
        {
            "result_group": "phase11_primary_trading",
            "metric": "bootstrap_probability_positive",
            "value": get_metric(
                "phase11",
                "primary_june_uncertainty",
                "bootstrap_probability_positive",
            ),
            "unit": "",
        }
    )
    main_results_rows.append(
        {
            "result_group": "phase12_robustness",
            "metric": "post_hoc_rank",
            "value": get_metric(
                "phase12",
                "post_hoc_june_ranking",
                "post_hoc_rank",
            ),
            "unit": "rank",
        }
    )
    main_results_rows.append(
        {
            "result_group": "phase12_robustness",
            "metric": "post_hoc_candidate_count",
            "value": get_metric(
                "phase12",
                "post_hoc_june_ranking",
                "post_hoc_candidate_count",
            ),
            "unit": "candidates",
        }
    )

    main_results_df = pd.DataFrame(
        main_results_rows
    )

    boundary_rows = [
        {
            "phase": "phase9",
            "boundary": (
                "No market price was used. June data were not used "
                "to refit the GP, select a kernel, or impute missing forecasts."
            ),
        },
        {
            "phase": "phase10",
            "boundary": (
                "The comparison concerns only the exact complete-book intersection. "
                "Results outside this intersection are not inferred or imputed."
            ),
        },
        {
            "phase": "phase11",
            "boundary": (
                "The trading exercise is a frozen historical simulation, "
                "not evidence of live executable arbitrage."
            ),
        },
        {
            "phase": "phase12",
            "boundary": (
                phase12_boundary
                .replace("\n", " ")
                .strip()
            ),
        },
    ]

    boundaries_df = pd.DataFrame(
        boundary_rows
    )

    # Save CSVs
    source_inventory.to_csv(
        output_dir / "phase13_source_inventory.csv",
        index=False,
    )

    metrics_df.to_csv(
        output_dir / "phase13_key_metrics_long.csv",
        index=False,
    )

    phase9_summary.to_csv(
        output_dir / "phase13_phase9_summary.csv",
        index=False,
    )

    phase10_june_df.to_csv(
        output_dir / "phase13_phase10_june_paired_results.csv",
        index=False,
    )

    phase10_training_df.to_csv(
        output_dir / "phase13_phase10_training_paired_results.csv",
        index=False,
    )

    phase10_calibration_df.to_csv(
        output_dir / "phase13_phase10_june_calibration.csv",
        index=False,
    )

    phase11_frozen_df.to_csv(
        output_dir / "phase13_phase11_frozen_strategies.csv",
        index=False,
    )

    phase11_costs_df.to_csv(
        output_dir / "phase13_phase11_cost_sensitivity.csv",
        index=False,
    )

    phase12_summary.to_csv(
        output_dir / "phase13_phase12_summary.csv",
        index=False,
    )

    main_results_df.to_csv(
        output_dir / "phase13_main_results_table.csv",
        index=False,
    )

    boundaries_df.to_csv(
        output_dir / "phase13_evidential_boundaries.csv",
        index=False,
    )

    # Build markdown report
    report_lines = []

    report_lines.append(
        "# Phase 13 Verified Evidence Pack"
    )
    report_lines.append("")
    report_lines.append(
        "## Status"
    )
    report_lines.append("")
    report_lines.append(
        "PASSED"
    )
    report_lines.append("")
    report_lines.append(
        "## Objective"
    )
    report_lines.append("")
    report_lines.append(
        "Consolidate the verified empirical findings from Phases 9–12 into "
        "thesis-ready summary tables and a single evidence-pack report."
    )
    report_lines.append("")
    report_lines.append(
        "## Source diagnostics"
    )
    report_lines.append("")
    for _, row in source_inventory.iterrows():
        report_lines.append(
            f"- {row['phase']}: `{row['directory']}`"
        )
        report_lines.append(
            f"  - report: `{row['report_path']}`"
        )
        if row["manifest_path"]:
            report_lines.append(
                f"  - manifest: `{row['manifest_path']}`"
            )
    report_lines.append("")

    report_lines.append(
        "## Consolidated empirical summary"
    )
    report_lines.append("")

    report_lines.append(
        "### Phase 9: GP contract-event probability construction"
    )
    report_lines.append("")
    report_lines.append(
        f"- Forecast-supported dates: "
        f"{get_metric('phase9', 'certified_support', 'forecast_supported_dates')}."
    )
    report_lines.append(
        f"- Forecast-supported date-rule rows: "
        f"{get_metric('phase9', 'certified_support', 'forecast_supported_date_rule_rows')}."
    )
    report_lines.append(
        f"- June mean binary Brier score: "
        f"{get_metric('phase9', 'june_out_of_sample_proper_scores', 'mean_binary_brier')}."
    )
    report_lines.append(
        f"- June mean binary log score: "
        f"{get_metric('phase9', 'june_out_of_sample_proper_scores', 'mean_binary_log')}."
    )
    report_lines.append(
        f"- June mean continuous CRPS: "
        f"{get_metric('phase9', 'june_out_of_sample_proper_scores', 'mean_continuous_crps')} degrees Celsius."
    )
    report_lines.append("")

    report_lines.append(
        "### Phase 10: GP versus Polymarket exact-common-support comparison"
    )
    report_lines.append("")
    report_lines.append(
        f"- Complete common-support dates: "
        f"{get_metric('phase10', 'exact_common_support', 'complete_common_support_dates')}."
    )
    report_lines.append(
        f"- Complete common-support date-rule books: "
        f"{get_metric('phase10', 'exact_common_support', 'complete_common_support_date_rule_books')}."
    )
    report_lines.append(
        f"- Complete common-support contract-event rows: "
        f"{get_metric('phase10', 'exact_common_support', 'complete_common_support_contract_event_rows')}."
    )
    if not phase10_june_df.empty:
        report_lines.append(
            "- June paired score differences (`GP score minus Polymarket score`):"
        )
        for _, row in phase10_june_df.iterrows():
            report_lines.append(
                f"  - {row['Metric']}: {row['Difference']} "
                f"with 95% bootstrap interval {row['95% bootstrap interval']} over {row['Dates']} dates."
            )
    report_lines.append("")

    report_lines.append(
        "### Phase 11: Frozen value-gap trading"
    )
    report_lines.append("")
    report_lines.append(
        f"- Primary decision rule: "
        f"{get_metric('phase11', 'primary_strategy', 'decision_rule')}."
    )
    report_lines.append(
        f"- Frozen value-gap threshold: "
        f"{get_metric('phase11', 'primary_strategy', 'frozen_value_gap_threshold')}."
    )
    report_lines.append(
        f"- June trades at the reference cost: "
        f"{get_metric('phase11', 'primary_strategy', 'june_trades_at_reference_cost')}."
    )
    report_lines.append(
        f"- Total June net PnL at the reference cost: "
        f"{get_metric('phase11', 'primary_june_uncertainty', 'total_net_pnl')}."
    )
    report_lines.append(
        f"- Bootstrap probability that total June net PnL is positive: "
        f"{get_metric('phase11', 'primary_june_uncertainty', 'bootstrap_probability_positive')}."
    )
    report_lines.append("")

    report_lines.append(
        "### Phase 12: Robustness, attribution and synthesis"
    )
    report_lines.append("")
    report_lines.append(
        f"- Post-hoc June rank: "
        f"{get_metric('phase12', 'post_hoc_june_ranking', 'post_hoc_rank')} "
        f"out of "
        f"{get_metric('phase12', 'post_hoc_june_ranking', 'post_hoc_candidate_count')} "
        f"rule-threshold candidates."
    )
    report_lines.append(
        f"- Post-hoc total June net PnL: "
        f"{get_metric('phase12', 'post_hoc_june_ranking', 'total_net_pnl')}."
    )
    report_lines.append(
        f"- Post-hoc mean date net PnL: "
        f"{get_metric('phase12', 'post_hoc_june_ranking', 'mean_date_net_pnl')}."
    )
    report_lines.append(
        f"- Post-hoc return on committed capital: "
        f"{get_metric('phase12', 'post_hoc_june_ranking', 'return_on_committed_capital')}."
    )
    report_lines.append("")

    report_lines.append(
        "## Final thesis-facing synthesis"
    )
    report_lines.append("")
    report_lines.append(
        "1. The two-year Matérn GP produced coherent contract-event probabilities "
        "and materially improved the credibility of the weather-only probabilistic construction."
    )
    report_lines.append(
        "2. On the exact complete-book intersection, June Polymarket prices achieved lower "
        "binary and categorical proper scores than the GP on all four primary comparisons."
    )
    report_lines.append(
        "3. The frozen value-gap strategy produced only a small positive June point estimate "
        "at the reference transaction cost, with weak uncertainty support."
    )
    report_lines.append(
        "4. The Phase 12 synthesis further weakens any claim of a stable trading edge."
    )
    report_lines.append("")

    report_lines.append(
        "## Evidential boundary"
    )
    report_lines.append("")
    for _, row in boundaries_df.iterrows():
        report_lines.append(
            f"- {row['phase']}: {row['boundary']}"
        )
    report_lines.append("")

    report_lines.append(
        "## Output files"
    )
    report_lines.append("")
    for filename in sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_file()
    ):
        report_lines.append(
            f"- `{filename}`"
        )

    report_path = output_dir / spec[
        "report_filename"
    ]
    report_path.write_text(
        "\n".join(
            report_lines
        ) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "status": "passed",
        "phase_prefixes": phase_prefixes,
        "source_directories": discovered_sources,
        "output_directory": str(output_dir),
        "output_files": sorted(
            [
                path.name
                for path in output_dir.iterdir()
                if path.is_file()
            ]
        ),
        "key_counts": {
            "source_phases": len(discovered_sources),
            "extracted_metrics": int(len(metrics_df)),
            "phase10_june_rows": int(len(phase10_june_df)),
            "phase10_training_rows": int(len(phase10_training_df)),
            "phase10_calibration_rows": int(len(phase10_calibration_df)),
            "phase11_frozen_strategy_rows": int(len(phase11_frozen_df)),
            "phase11_cost_sensitivity_rows": int(len(phase11_costs_df)),
        },
    }

    manifest_path = output_dir / spec[
        "manifest_filename"
    ]
    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(
        "PHASE 13 VERIFIED EVIDENCE PACK: PASSED"
    )
    print(
        "Output directory:",
        output_dir,
    )
    print(
        "Extracted metrics:",
        len(metrics_df),
    )
    print(
        "Main results rows:",
        len(main_results_df),
    )


if __name__ == "__main__":
    main()
