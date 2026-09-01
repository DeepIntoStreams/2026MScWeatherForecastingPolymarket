from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# FROZEN INPUTS
# =============================================================================

WEATHER_SUMMARY = Path(
    "outputs/final_pipeline/audit/weather_models_summary.json"
)

MARKET_SUMMARY = Path(
    "outputs/final_pipeline/audit/market_stage_summary.json"
)

TRADING_SUMMARY = Path(
    "outputs/final_pipeline/audit/trading_stage_summary.json"
)

SYNTHESIS_SUMMARY = Path(
    "outputs/final_pipeline/audit/synthesis_stage_summary.json"
)

POOL_SELECTION = Path(
    "outputs/final_pipeline/market/convex_pool_selection.json"
)

TRADING_POLICY = Path(
    "outputs/final_pipeline/trading/selected_trading_policy.json"
)

EVENT_PANEL = Path(
    "data/processed/final_pipeline/market/"
    "exact_common_event_panel.csv.gz"
)

TRADING_LEDGERS = Path(
    "data/processed/final_pipeline/trading/"
    "fixed_policy_ledgers.csv"
)

MARKET_SCORES = Path(
    "outputs/final_pipeline/market/"
    "exact_support_score_summary.csv"
)

MARKET_TV = Path(
    "outputs/final_pipeline/market/"
    "total_variation_summary.csv"
)

TRADING_RISK = Path(
    "outputs/final_pipeline/trading/"
    "trading_risk_summary.csv"
)

TRADING_BOOTSTRAP = Path(
    "outputs/final_pipeline/trading/"
    "trading_bootstrap_summary.csv"
)

BOOTSTRAP_INTERPRETATION = Path(
    "outputs/final_pipeline/synthesis/"
    "bootstrap_interpretation.csv"
)

CROSS_STAGE = Path(
    "outputs/final_pipeline/synthesis/"
    "cross_stage_attribution.csv"
)

RULE_SUPPORT = Path(
    "outputs/final_pipeline/synthesis/"
    "rule_support_robustness.csv"
)

EXISTING_EVIDENCE_REGISTER = Path(
    "outputs/final_pipeline/synthesis/"
    "thesis_evidence_register.csv"
)

EXISTING_THESIS_MANIFEST = Path(
    "outputs/final_pipeline/synthesis/"
    "thesis_output_manifest.csv"
)

PENDING_STATUS = Path(
    "outputs/final_pipeline/synthesis/"
    "pending_target_status.json"
)

MASTER_CONFIG = Path(
    "config/final_empirical_config.json"
)


# =============================================================================
# OUTPUTS
# =============================================================================

PROCESSED = Path(
    "data/processed/final_pipeline/reporting"
)

OUTPUT = Path(
    "outputs/final_pipeline/reporting"
)

THESIS = Path(
    "outputs/final_pipeline/thesis"
)

TABLES = THESIS / "tables"
FIGURES = THESIS / "figures"
GENERATED = THESIS / "generated"

AUDIT = Path(
    "outputs/final_pipeline/audit"
)

GENERALISATION_AUDIT = (
    OUTPUT
    / "development_external_comparison.csv"
)

BENCHMARK_RECON = (
    OUTPUT
    / "march_june_audit_reconciliation.csv"
)

DISCREPANCY_REGISTER = (
    OUTPUT
    / "benchmark_discrepancy_register.csv"
)

SAMPLE_SIZES = (
    OUTPUT
    / "authoritative_sample_sizes.csv"
)

FINAL_MANIFEST = (
    OUTPUT
    / "final_empirical_output_manifest.csv"
)

FINAL_CLAIMS = (
    OUTPUT
    / "final_thesis_claims_register.csv"
)

NUMBERS_TEX = (
    GENERATED
    / "numbers.tex"
)

REPORTING_SUMMARY = (
    AUDIT
    / "reporting_stage_summary.json"
)

REPORTING_CHECKS = (
    AUDIT
    / "reporting_stage_integrity_checks.csv"
)

BENCHMARK_MD = Path(
    "docs/final_pipeline/"
    "march_june_audit_reconciliation.md"
)

REPORTING_MD = Path(
    "docs/final_pipeline/"
    "thesis_reporting_outputs.md"
)


# =============================================================================
# HISTORICAL AUDITED BENCHMARK
# =============================================================================
#
# These values are used ONLY as a reconciliation benchmark.
#
# The old empirical design treated:
#
#   March-May = market development
#   June      = external evaluation
#
# The final design treats:
#
#   March-June = development
#   July-August = external evaluation
#
# The two-year weather target calendar is retained, but the final empirical
# pipeline rebuilt the deterministic ECMWF forecast inputs under the certified
# chronological core-repair selection logic. Consequently the old continuous
# weather scores are historical comparison values rather than must-match
# invariants. The selected Matérn-3/2 kernel remains an invariant. Market
# support, convex-pool selection and trading selectors are also allowed to
# differ because the final development allocation changed.
# =============================================================================


OLD = {
    "weather_raw_crps": 1.745685,
    "weather_static_crps": 0.911755,
    "weather_rbf_crps": 0.877561,
    "weather_matern32_crps": 0.863340,
    "weather_selected_kernel": "matern32",

    "old_exact_common_dates": 97,
    "old_exact_common_books": 350,
    "old_exact_common_event_rows": 3850,

    "old_pool_weight_gp": 0.489,

    "old_trading_rule": "event_day_open",
    "old_trading_threshold": 0.120,
    "old_external_trading_net_pnl": 0.0235,
}


# =============================================================================
# HELPERS
# =============================================================================


def read_json(path: Path):
    return json.loads(
        path.read_text()
    )


def sha256(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            h.update(
                chunk
            )

    return h.hexdigest()


def as_bool(series):
    if series.dtype == bool:
        return series

    x = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
            }
        )
    )

    if x.isna().any():
        raise RuntimeError(
            "Boolean parsing failed."
        )

    return x.astype(bool)


def isclose(a, b, tol=5e-6):
    return bool(
        math.isclose(
            float(a),
            float(b),
            abs_tol=tol,
            rel_tol=0.0,
        )
    )


def one_row(df, **filters):
    x = df.copy()

    for key, value in filters.items():
        x = x[
            x[key].astype(str)
            == str(value)
        ]

    if len(x) != 1:
        raise RuntimeError(
            f"Expected one row for {filters}; "
            f"found {len(x)}."
        )

    return x.iloc[0]


def git_tracked_files():
    out = subprocess.check_output(
        [
            "git",
            "ls-files",
        ],
        text=True,
    )

    return {
        x.strip()
        for x in out.splitlines()
        if x.strip()
    }


def latex_escape(text):
    replacements = {
        "\\": r"\textbackslash{}",
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
        result = result.replace(
            old,
            new,
        )

    return result


def format_value(value, digits=4):
    if value is None:
        return ""

    try:
        x = float(value)

        if not np.isfinite(x):
            return ""

        return f"{x:.{digits}f}"

    except Exception:
        return str(value)


# =============================================================================
# STEP 81 — DEVELOPMENT / EXTERNAL COMPARISON
# =============================================================================


def build_development_external_comparison(
    event_panel,
    scores,
    tv,
    risk,
):
    rows = []

    for period in [
        "market_development",
        "external_validation",
    ]:
        p = event_panel[
            event_panel[
                "empirical_period"
            ]
            == period
        ]

        rows.append(
            {
                "domain":
                    "support",

                "metric":
                    "exact_common_dates",

                "source":
                    "all",

                "period":
                    period,

                "value":
                    p[
                        "event_date"
                    ].nunique(),
            }
        )

        rows.append(
            {
                "domain":
                    "support",

                "metric":
                    "complete_date_rule_books",

                "source":
                    "all",

                "period":
                    period,

                "value":
                    p[
                        [
                            "event_date",
                            "decision_rule",
                        ]
                    ]
                    .drop_duplicates()
                    .shape[0],
            }
        )

        target_ready = p[
            as_bool(
                p[
                    "target_available"
                ]
            )
        ]

        rows.append(
            {
                "domain":
                    "support",

                "metric":
                    "score_ready_dates",

                "source":
                    "all",

                "period":
                    period,

                "value":
                    target_ready[
                        "event_date"
                    ].nunique(),
            }
        )

    for metric in [
        "categorical_log",
        "multiclass_brier",
    ]:
        for source in [
            "static",
            "selected_gp",
            "market",
            "pool",
        ]:
            for period in [
                "market_development",
                "external_validation",
            ]:
                row = one_row(
                    scores,
                    analysis_period=period,
                    source=source,
                )

                rows.append(
                    {
                        "domain":
                            "proper_score",

                        "metric":
                            metric,

                        "source":
                            source,

                        "period":
                            period,

                        "value":
                            float(
                                row[
                                    metric
                                ]
                            ),
                    }
                )

    for source in [
        "raw",
        "static",
        "selected_gp",
    ]:
        for period in [
            "market_development",
            "external_validation",
        ]:
            row = one_row(
                tv,
                analysis_period=period,
                source=source,
            )

            rows.append(
                {
                    "domain":
                        "market_distance",

                    "metric":
                        "date_balanced_tv",

                    "source":
                        source,

                    "period":
                        period,

                    "value":
                        float(
                            row[
                                "date_balanced_tv"
                            ]
                        ),
                }
            )

    for metric in [
        "total_net_pnl",
        "mean_daily_net_pnl",
        "settlement_date_sharpe",
        "trade_count",
    ]:
        for source in [
            "raw",
            "static",
            "selected_gp",
        ]:
            for period in [
                "market_development",
                "external_validation",
            ]:
                row = one_row(
                    risk,
                    analysis_period=period,
                    probability_source=source,
                )

                rows.append(
                    {
                        "domain":
                            "trading",

                        "metric":
                            metric,

                        "source":
                            source,

                        "period":
                            period,

                        "value":
                            float(
                                row[
                                    metric
                                ]
                            ),
                    }
                )

    x = pd.DataFrame(rows)

    dev = x[
        x[
            "period"
        ]
        == "market_development"
    ].rename(
        columns={
            "value":
                "development"
        }
    )

    ext = x[
        x[
            "period"
        ]
        == "external_validation"
    ].rename(
        columns={
            "value":
                "external"
        }
    )

    merged = dev[
        [
            "domain",
            "metric",
            "source",
            "development",
        ]
    ].merge(
        ext[
            [
                "domain",
                "metric",
                "source",
                "external",
            ]
        ],
        on=[
            "domain",
            "metric",
            "source",
        ],
        how="outer",
        validate="one_to_one",
    )

    merged[
        "external_minus_development"
    ] = (
        merged[
            "external"
        ]
        - merged[
            "development"
        ]
    )

    return merged


# =============================================================================
# STEPS 82–84 — HISTORICAL AUDIT RECONCILIATION
# =============================================================================


def build_benchmark_reconciliation(
    weather_summary,
    pool,
    policy,
    event_panel,
    trading_summary,
):
    crps = weather_summary[
        "mean_date_crps_c"
    ]

    selected_kernel = (
        weather_summary[
            "selected_kernel"
        ]
    )

    development = event_panel[
        event_panel[
            "empirical_period"
        ]
        == "market_development"
    ]

    current_exact_dates = (
        development[
            "event_date"
        ].nunique()
    )

    current_books = (
        development[
            [
                "event_date",
                "decision_rule",
            ]
        ]
        .drop_duplicates()
        .shape[0]
    )

    current_rows = len(
        development
    )

    rows = []

    def add(
        metric,
        old_value,
        current_value,
        reconciliation_class,
        reason,
        tolerance=None,
    ):
        if reconciliation_class == "must_match":
            if isinstance(
                old_value,
                str,
            ):
                passed = (
                    str(
                        current_value
                    )
                    == str(
                        old_value
                    )
                )
            else:
                passed = isclose(
                    old_value,
                    current_value,
                    tol=(
                        5e-6
                        if tolerance is None
                        else tolerance
                    ),
                )

        else:
            passed = True

        rows.append(
            {
                "metric":
                    metric,

                "audited_old_value":
                    old_value,

                "current_value":
                    current_value,

                "reconciliation_class":
                    reconciliation_class,

                "reconciliation_pass":
                    passed,

                "reason":
                    reason,
            }
        )

    add(
        "weather_raw_crps",
        OLD[
            "weather_raw_crps"
        ],
        crps[
            "raw"
        ],
        "expected_change",
        (
            "The two-year target calendar is retained, but the final "
            "pipeline rebuilt the deterministic ECMWF input panel under "
            "the certified chronological core-repair selection policy. "
            "The earlier raw CRPS is therefore a historical benchmark, "
            "not a must-match invariant."
        ),
    )

    add(
        "weather_static_crps",
        OLD[
            "weather_static_crps"
        ],
        crps[
            "static"
        ],
        "expected_change",
        (
            "The target calendar is retained, but the deterministic "
            "forecast inputs feeding the residual distribution changed "
            "under the final certified ECMWF chronology. The earlier "
            "static CRPS is therefore expected to change."
        ),
    )

    add(
        "weather_rbf_crps",
        OLD[
            "weather_rbf_crps"
        ],
        crps[
            "rbf"
        ],
        "expected_change",
        (
            "The final chronological weather reconstruction changed the "
            "underlying forecast-error panel. The earlier RBF CRPS is "
            "retained as a historical comparison rather than a "
            "must-match invariant."
        ),
    )

    add(
        "weather_matern32_crps",
        OLD[
            "weather_matern32_crps"
        ],
        crps[
            "matern32"
        ],
        "expected_change",
        (
            "The final chronological weather reconstruction changed the "
            "underlying forecast-error panel. The earlier Matérn-3/2 "
            "CRPS is retained as a historical comparison; selection of "
            "Matérn-3/2 remains the invariant."
        ),
    )

    add(
        "weather_selected_kernel",
        OLD[
            "weather_selected_kernel"
        ],
        selected_kernel,
        "must_match",
        (
            "The final selected weather kernel remains "
            "Matérn-3/2."
        ),
    )

    add(
        "exact_common_dates",
        OLD[
            "old_exact_common_dates"
        ],
        current_exact_dates,
        "expected_change",
        (
            "Market reconstruction and chronology were "
            "rebuilt; June now belongs to development."
        ),
    )

    add(
        "exact_common_books",
        OLD[
            "old_exact_common_books"
        ],
        current_books,
        "expected_change",
        (
            "Improved market-event recovery and final "
            "March-June development support changed "
            "the exact common book inventory."
        ),
    )

    add(
        "exact_common_event_rows",
        OLD[
            "old_exact_common_event_rows"
        ],
        current_rows,
        "expected_change",
        (
            "Eleven-event books change mechanically "
            "with the rebuilt support inventory."
        ),
    )

    add(
        "pool_weight_gp",
        OLD[
            "old_pool_weight_gp"
        ],
        pool[
            "weight_gp"
        ],
        "expected_change",
        (
            "Old weight used March-May development. "
            "Final weight uses March-June development."
        ),
    )

    add(
        "trading_rule",
        OLD[
            "old_trading_rule"
        ],
        policy[
            "selected_rule"
        ],
        "expected_change",
        (
            "Trading selection was rerun from zero on "
            "the final March-June development sample."
        ),
    )

    add(
        "trading_threshold",
        OLD[
            "old_trading_threshold"
        ],
        policy[
            "selected_threshold"
        ],
        "expected_change",
        (
            "Threshold was reselected under the final "
            "March-June one-SE procedure."
        ),
    )

    add(
        "external_trading_net_pnl",
        OLD[
            "old_external_trading_net_pnl"
        ],
        trading_summary[
            "external_selected_gp"
        ][
            "total_net_pnl"
        ],
        "not_comparable",
        (
            "Old value was June-only under the old policy; "
            "current value is July-August under the final "
            "frozen policy."
        ),
    )

    recon = pd.DataFrame(
        rows
    )

    discrepancies = recon[
        (
            recon[
                "reconciliation_class"
            ]
            == "must_match"
        )
        & (
            ~recon[
                "reconciliation_pass"
            ]
        )
    ].copy()

    if discrepancies.empty:
        discrepancy_register = pd.DataFrame(
            [
                {
                    "status":
                        "NO_UNEXPLAINED_DISCREPANCY",

                    "metric":
                        "",

                    "audited_old_value":
                        "",

                    "current_value":
                        "",

                    "action":
                        (
                            "All quantities designated must-match "
                            "reproduced within tolerance."
                        ),
                }
            ]
        )

    else:
        discrepancy_register = (
            discrepancies[
                [
                    "metric",
                    "audited_old_value",
                    "current_value",
                ]
            ]
            .copy()
        )

        discrepancy_register.insert(
            0,
            "status",
            "INVESTIGATE",
        )

        discrepancy_register[
            "action"
        ] = (
            "Do not freeze reporting stage until explained."
        )

    return (
        recon,
        discrepancy_register,
    )


# =============================================================================
# STEP 86 — AUTHORITATIVE SAMPLE-SIZE TABLE
# =============================================================================


def build_sample_sizes(
    event_panel,
    ledgers,
    weather_summary,
):
    e = event_panel.copy()

    e[
        "target_available"
    ] = as_bool(
        e[
            "target_available"
        ]
    )

    l = ledgers.copy()

    l[
        "target_available"
    ] = as_bool(
        l[
            "target_available"
        ]
    )

    l[
        "trade"
    ] = as_bool(
        l[
            "trade"
        ]
    )

    rows = [
        {
            "sample":
                "weather_only_history",

            "role":
                "weather model estimation and chronological validation",

            "dates":
                730,

            "date_rule_books":
                2920,

            "event_rows":
                np.nan,

            "settled_dates":
                730,

            "notes":
                (
                    "16 March 2024 to 15 March 2026; "
                    "four decision rules per date."
                ),
        }
    ]

    for period, label in [
        (
            "market_development",
            "march_june_development",
        ),
        (
            "external_validation",
            "july_august_external",
        ),
    ]:
        x = e[
            e[
                "empirical_period"
            ]
            == period
        ]

        settled = x[
            x[
                "target_available"
            ]
        ]

        rows.append(
            {
                "sample":
                    label,

                "role":
                    (
                        "market development"
                        if period
                        == "market_development"
                        else "external validation"
                    ),

                "dates":
                    x[
                        "event_date"
                    ].nunique(),

                "date_rule_books":
                    (
                        x[
                            [
                                "event_date",
                                "decision_rule",
                            ]
                        ]
                        .drop_duplicates()
                        .shape[0]
                    ),

                "event_rows":
                    len(
                        x
                    ),

                "settled_dates":
                    settled[
                        "event_date"
                    ].nunique(),

                "notes":
                    (
                        "Exact common support only; "
                        "eleven events per complete book."
                    ),
            }
        )

    for period, label in [
        (
            "market_development",
            "trading_development_selected_rule",
        ),
        (
            "external_validation",
            "trading_external_selected_rule",
        ),
    ]:
        x = l[
            (
                l[
                    "empirical_period"
                ]
                == period
            )
            & (
                l[
                    "probability_source"
                ]
                == "selected_gp"
            )
        ]

        rows.append(
            {
                "sample":
                    label,

                "role":
                    "fixed-policy trading",

                "dates":
                    len(
                        x
                    ),

                "date_rule_books":
                    len(
                        x
                    ),

                "event_rows":
                    np.nan,

                "settled_dates":
                    int(
                        x[
                            "target_available"
                        ].sum()
                    ),

                "notes":
                    (
                        f"Executed trades="
                        f"{int(x.loc[x['target_available'], 'trade'].sum())}; "
                        "one candidate position per settlement date."
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 87 — FINAL EMPIRICAL OUTPUT MANIFEST
# =============================================================================


def build_manifest():
    tracked = git_tracked_files()

    prefixes = (
        "config/final_empirical_config.json",
        "src/final_pipeline/",
        "tests/final_pipeline/",
        "docs/final_pipeline/",
        "data/processed/final_pipeline/",
        "outputs/final_pipeline/",
    )

    rows = []

    for item in sorted(
        tracked
    ):
        if not (
            item
            == "config/final_empirical_config.json"
            or item.startswith(
                prefixes[1:]
            )
        ):
            continue

        path = Path(
            item
        )

        if not path.exists():
            continue

        if path.is_dir():
            continue

        if item.startswith(
            "data/raw/"
        ):
            continue

        if item.startswith(
            "src/final_pipeline/"
        ):
            role = "source_code"

        elif item.startswith(
            "tests/final_pipeline/"
        ):
            role = "automated_test"

        elif item.startswith(
            "docs/final_pipeline/"
        ):
            role = "methodology_or_handoff_documentation"

        elif item.startswith(
            "data/processed/final_pipeline/"
        ):
            role = "processed_empirical_data"

        elif item.startswith(
            "outputs/final_pipeline/audit/"
        ):
            role = "audit_output"

        elif item.startswith(
            "outputs/final_pipeline/"
        ):
            role = "empirical_result_output"

        else:
            role = "configuration"

        rows.append(
            {
                "path":
                    item,

                "role":
                    role,

                "bytes":
                    path.stat().st_size,

                "sha256":
                    sha256(
                        path
                    ),

                "git_tracked":
                    True,
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# STEP 88 — FINAL CLAIMS REGISTER
# =============================================================================


def build_claims_register(
    existing,
    pending,
):
    x = existing.copy()

    x[
        "authoritative_source"
    ] = True

    x[
        "final_inclusion_status"
    ] = np.where(
        x[
            "recommended_location"
        ]
        == "do_not_use_as_primary_claim",
        "DO_NOT_USE_AS_PRIMARY",
        np.where(
            x[
                "recommended_location"
            ]
            == "appendix",
            "APPENDIX",
            "MAIN_OR_DISCUSSION",
        ),
    )

    pending_dates = pending[
        "pending_dates"
    ]

    x[
        "requires_aug31_refresh"
    ] = False

    if pending_dates:
        terms = (
            "external",
            "July",
            "August",
            "PnL",
            "trading",
            "pool",
            "market",
        )

        mask = x[
            "safe_claim"
        ].astype(str).apply(
            lambda s:
                any(
                    term.lower()
                    in s.lower()
                    for term in terms
                )
        )

        x.loc[
            mask,
            "requires_aug31_refresh",
        ] = True

    x[
        "claim_status"
    ] = np.where(
        x[
            "requires_aug31_refresh"
        ],
        "CURRENT_PENDING_FINAL_AUG31_TARGET",
        "FINAL",
    )

    x[
        "prohibited_overstatement"
    ] = (
        x[
            "caveat"
        ].fillna("")
    )

    return x


# =============================================================================
# STEP 89 — THESIS-READY OUTPUTS
# =============================================================================


def write_table(
    df,
    path,
    caption,
    label,
    columns,
    headers,
    formats=None,
):
    if formats is None:
        formats = {}

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\begin{tabular}{"
        + "l"
        + "r" * (
            len(
                columns
            )
            - 1
        )
        + "}",
        r"\toprule",
        " & ".join(
            latex_escape(
                h
            )
            for h in headers
        )
        + r" \\",
        r"\midrule",
    ]

    for _, row in df.iterrows():
        values = []

        for col in columns:
            value = row[
                col
            ]

            if col in formats:
                value = formats[
                    col
                ](
                    value
                )

            values.append(
                latex_escape(
                    value
                )
            )

        lines.append(
            " & ".join(
                values
            )
            + r" \\"
        )

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )

    path.write_text(
        "\n".join(
            lines
        )
    )


def build_thesis_outputs(
    sample_sizes,
    cross_stage,
    scores,
    risk,
    bootstrap_interpretation,
    rule_support,
    thesis_manifest,
):
    TABLES.mkdir(
        parents=True,
        exist_ok=True,
    )

    FIGURES.mkdir(
        parents=True,
        exist_ok=True,
    )

    GENERATED.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # Sample sizes
    # ------------------------------------------------------------------

    ss = sample_sizes.copy()

    ss[
        "dates_text"
    ] = ss[
        "dates"
    ].apply(
        lambda x:
            str(
                int(
                    x
                )
            )
    )

    ss[
        "books_text"
    ] = ss[
        "date_rule_books"
    ].apply(
        lambda x:
            (
                ""
                if pd.isna(
                    x
                )
                else str(
                    int(
                        x
                    )
                )
            )
    )

    ss[
        "settled_text"
    ] = ss[
        "settled_dates"
    ].apply(
        lambda x:
            str(
                int(
                    x
                )
            )
    )

    write_table(
        ss,
        TABLES
        / "sample_sizes.tex",
        (
            "Authoritative sample roles and support "
            "in the final empirical pipeline."
        ),
        "tab:final-sample-sizes",
        [
            "sample",
            "dates_text",
            "books_text",
            "settled_text",
        ],
        [
            "Sample",
            "Dates",
            "Books",
            "Settled dates",
        ],
    )

    # ------------------------------------------------------------------
    # Cross-stage attribution
    # ------------------------------------------------------------------

    ca = cross_stage.copy()

    ca[
        "raw_text"
    ] = ca[
        "raw"
    ].map(
        lambda x:
            format_value(
                x,
                4,
            )
    )

    ca[
        "static_text"
    ] = ca[
        "static"
    ].map(
        lambda x:
            format_value(
                x,
                4,
            )
    )

    ca[
        "gp_text"
    ] = ca[
        "selected_gp"
    ].map(
        lambda x:
            format_value(
                x,
                4,
            )
    )

    ca[
        "share_text"
    ] = (
        100
        * ca[
            "static_share_of_raw_to_gp_improvement"
        ]
    ).map(
        lambda x:
            f"{x:.1f}%"
    )

    write_table(
        ca,
        TABLES
        / "cross_stage_attribution.tex",
        (
            "Share of the raw-to-GP improvement captured "
            "by the static probabilistic correction."
        ),
        "tab:cross-stage-attribution",
        [
            "domain",
            "raw_text",
            "static_text",
            "gp_text",
            "share_text",
        ],
        [
            "Domain",
            "Raw",
            "Static",
            "GP",
            "Static share",
        ],
    )

    # ------------------------------------------------------------------
    # External proper scores
    # ------------------------------------------------------------------

    ext = scores[
        scores[
            "analysis_period"
        ]
        == "external_validation"
    ].copy()

    desired = [
        "static",
        "selected_gp",
        "market",
        "pool",
    ]

    ext[
        "_order"
    ] = ext[
        "source"
    ].map(
        {
            x: i
            for i, x in enumerate(
                desired
            )
        }
    )

    ext = ext[
        ext[
            "source"
        ].isin(
            desired
        )
    ].sort_values(
        "_order"
    )

    ext[
        "cat_text"
    ] = ext[
        "categorical_log"
    ].map(
        lambda x:
            format_value(
                x,
                4,
            )
    )

    ext[
        "brier_text"
    ] = ext[
        "multiclass_brier"
    ].map(
        lambda x:
            format_value(
                x,
                4,
            )
    )

    write_table(
        ext,
        TABLES
        / "external_proper_scores.tex",
        (
            "July--August proper-score comparison "
            "on exact common support."
        ),
        "tab:external-proper-scores",
        [
            "source",
            "cat_text",
            "brier_text",
        ],
        [
            "Source",
            "Categorical log",
            "Multiclass Brier",
        ],
    )

    # ------------------------------------------------------------------
    # External trading attribution
    # ------------------------------------------------------------------

    tr = risk[
        (
            risk[
                "analysis_period"
            ]
            == "external_validation"
        )
        & (
            risk[
                "probability_source"
            ].isin(
                [
                    "raw",
                    "static",
                    "selected_gp",
                ]
            )
        )
    ].copy()

    tr[
        "_order"
    ] = tr[
        "probability_source"
    ].map(
        {
            "raw": 0,
            "static": 1,
            "selected_gp": 2,
        }
    )

    tr = tr.sort_values(
        "_order"
    )

    tr[
        "trades_text"
    ] = tr[
        "trade_count"
    ].map(
        lambda x:
            str(
                int(
                    x
                )
            )
    )

    tr[
        "pnl_text"
    ] = tr[
        "total_net_pnl"
    ].map(
        lambda x:
            format_value(
                x,
                3,
            )
    )

    tr[
        "sharpe_text"
    ] = tr[
        "settlement_date_sharpe"
    ].map(
        lambda x:
            format_value(
                x,
                3,
            )
    )

    tr[
        "drawdown_text"
    ] = tr[
        "maximum_drawdown"
    ].map(
        lambda x:
            format_value(
                x,
                3,
            )
    )

    write_table(
        tr,
        TABLES
        / "external_trading_attribution.tex",
        (
            "Frozen-policy July--August trading attribution."
        ),
        "tab:external-trading-attribution",
        [
            "probability_source",
            "trades_text",
            "pnl_text",
            "sharpe_text",
            "drawdown_text",
        ],
        [
            "Signal",
            "Trades",
            "Net PnL",
            "Sharpe",
            "Max. drawdown",
        ],
    )

    # ------------------------------------------------------------------
    # Bootstrap interpretation
    # ------------------------------------------------------------------

    bt = bootstrap_interpretation.copy()

    bt[
        "ordinary_text"
    ] = bt.apply(
        lambda r:
            (
                f"[{r['ordinary_lower_95']:.3f}, "
                f"{r['ordinary_upper_95']:.3f}]"
            ),
        axis=1,
    )

    bt[
        "block_text"
    ] = bt.apply(
        lambda r:
            (
                f"[{r['block7_lower_95']:.3f}, "
                f"{r['block7_upper_95']:.3f}]"
            ),
        axis=1,
    )

    bt[
        "contrast"
    ] = bt.apply(
        lambda r:
            (
                str(
                    r[
                        "source_a"
                    ]
                )
                if str(
                    r[
                        "source_b"
                    ]
                )
                in (
                    "",
                    "nan",
                )
                else (
                    str(
                        r[
                            "source_a"
                        ]
                    )
                    + " - "
                    + str(
                        r[
                            "source_b"
                        ]
                    )
                )
            ),
        axis=1,
    )

    write_table(
        bt,
        TABLES
        / "trading_bootstrap_interpretation.tex",
        (
            "Ordinary and seven-date block bootstrap "
            "interpretation for external trading PnL."
        ),
        "tab:trading-bootstrap",
        [
            "contrast",
            "ordinary_text",
            "block_text",
            "classification",
        ],
        [
            "Estimand",
            "Ordinary 95% CI",
            "Block-7 95% CI",
            "Classification",
        ],
    )

    # ------------------------------------------------------------------
    # Rule-support diagnostic
    # ------------------------------------------------------------------

    rs = rule_support.copy()

    rs[
        "threshold_text"
    ] = rs[
        "selected_threshold"
    ].map(
        lambda x:
            format_value(
                x,
                2,
            )
    )

    rs[
        "score_text"
    ] = rs[
        "conservative_score"
    ].map(
        lambda x:
            format_value(
                x,
                4,
            )
    )

    write_table(
        rs,
        TABLES
        / "rule_support_robustness.tex",
        (
            "Decision-rule selection under the primary "
            "and common-date development supports."
        ),
        "tab:rule-support-robustness",
        [
            "selection_basis",
            "selected_rule",
            "threshold_text",
            "score_text",
        ],
        [
            "Selection basis",
            "Rule",
            "Threshold",
            "Conservative score",
        ],
    )

    # ------------------------------------------------------------------
    # Copy approved figures into one clean thesis-facing directory
    # ------------------------------------------------------------------

    copied = []

    for _, row in thesis_manifest.iterrows():
        location = str(
            row[
                "recommended_location"
            ]
        )

        if location not in {
            "main_text",
            "main_text_candidate",
        }:
            continue

        source = Path(
            row[
                "path"
            ]
        )

        if not source.exists():
            continue

        destination = (
            FIGURES
            / source.name
        )

        shutil.copy2(
            source,
            destination,
        )

        copied.append(
            {
                "source":
                    str(
                        source
                    ),

                "destination":
                    str(
                        destination
                    ),

                "purpose":
                    row[
                        "purpose"
                    ],
            }
        )

    return pd.DataFrame(
        copied
    )


# =============================================================================
# STEP 90 — NUMBERS.TEX
# =============================================================================


def write_numbers_tex(
    weather_summary,
    pool,
    policy,
    event_panel,
    scores,
    tv,
    risk,
    bootstrap_interpretation,
    cross_stage,
    pending,
):
    crps = weather_summary[
        "mean_date_crps_c"
    ]

    ext_panel = event_panel[
        event_panel[
            "empirical_period"
        ]
        == "external_validation"
    ]

    dev_panel = event_panel[
        event_panel[
            "empirical_period"
        ]
        == "market_development"
    ]

    ext_ready = ext_panel[
        as_bool(
            ext_panel[
                "target_available"
            ]
        )
    ]

    market_ext = one_row(
        scores,
        analysis_period=
            "external_validation",
        source=
            "market",
    )

    pool_ext = one_row(
        scores,
        analysis_period=
            "external_validation",
        source=
            "pool",
    )

    static_ext = one_row(
        scores,
        analysis_period=
            "external_validation",
        source=
            "static",
    )

    gp_score_ext = one_row(
        scores,
        analysis_period=
            "external_validation",
        source=
            "selected_gp",
    )

    static_tv = one_row(
        tv,
        analysis_period=
            "external_validation",
        source=
            "static",
    )

    gp_tv = one_row(
        tv,
        analysis_period=
            "external_validation",
        source=
            "selected_gp",
    )

    risk_map = {
        source:
            one_row(
                risk,
                analysis_period=
                    "external_validation",
                probability_source=
                    source,
            )
        for source in [
            "raw",
            "static",
            "selected_gp",
        ]
    }

    gp_boot = bootstrap_interpretation[
        (
            bootstrap_interpretation[
                "estimand"
            ]
            == "method_level"
        )
        & (
            bootstrap_interpretation[
                "source_a"
            ]
            == "selected_gp"
        )
    ].iloc[
        0
    ]

    cross = {
        row[
            "domain"
        ]:
            row
        for _, row in cross_stage.iterrows()
    }

    pending_dates = pending[
        "pending_dates"
    ]

    macros = [
        (
            "WeatherRawCRPS",
            f"{float(crps['raw']):.4f}",
        ),
        (
            "WeatherStaticCRPS",
            f"{float(crps['static']):.4f}",
        ),
        (
            "WeatherRBFCRPS",
            f"{float(crps['rbf']):.4f}",
        ),
        (
            "WeatherMaternCRPS",
            f"{float(crps['matern32']):.4f}",
        ),
        (
            "WeatherStaticSharePct",
            (
                f"{100 * float(cross['weather_continuous_crps']['static_share_of_raw_to_gp_improvement']):.1f}"
            ),
        ),
        (
            "FinalPoolGPWeight",
            f"{float(pool['weight_gp']):.3f}",
        ),
        (
            "FinalPoolMarketWeight",
            f"{float(pool['weight_market']):.3f}",
        ),
        (
            "DevelopmentExactDates",
            str(
                dev_panel[
                    "event_date"
                ].nunique()
            ),
        ),
        (
            "ExternalExactDates",
            str(
                ext_panel[
                    "event_date"
                ].nunique()
            ),
        ),
        (
            "ExternalScoreReadyDates",
            str(
                ext_ready[
                    "event_date"
                ].nunique()
            ),
        ),
        (
            "ExternalStaticTV",
            f"{float(static_tv['date_balanced_tv']):.4f}",
        ),
        (
            "ExternalGPTV",
            f"{float(gp_tv['date_balanced_tv']):.4f}",
        ),
        (
            "ExternalTVStaticSharePct",
            (
                f"{100 * float(cross['weather_market_total_variation']['static_share_of_raw_to_gp_improvement']):.1f}"
            ),
        ),
        (
            "ExternalStaticCatLog",
            f"{float(static_ext['categorical_log']):.4f}",
        ),
        (
            "ExternalGPCatLog",
            f"{float(gp_score_ext['categorical_log']):.4f}",
        ),
        (
            "ExternalMarketCatLog",
            f"{float(market_ext['categorical_log']):.4f}",
        ),
        (
            "ExternalPoolCatLog",
            f"{float(pool_ext['categorical_log']):.4f}",
        ),
        (
            "TradingRuleText",
            str(
                policy[
                    "selected_rule"
                ]
            ).replace(
                "_",
                r"\_",
            ),
        ),
        (
            "TradingThreshold",
            f"{float(policy['selected_threshold']):.2f}",
        ),
        (
            "ReferenceTradingCost",
            f"{float(policy['reference_cost_per_share']):.2f}",
        ),
        (
            "ExternalRawPnL",
            f"{float(risk_map['raw']['total_net_pnl']):.3f}",
        ),
        (
            "ExternalStaticPnL",
            f"{float(risk_map['static']['total_net_pnl']):.3f}",
        ),
        (
            "ExternalGPPnL",
            f"{float(risk_map['selected_gp']['total_net_pnl']):.3f}",
        ),
        (
            "ExternalGPTrades",
            str(
                int(
                    risk_map[
                        "selected_gp"
                    ][
                        "trade_count"
                    ]
                )
            ),
        ),
        (
            "ExternalGPSharpe",
            f"{float(risk_map['selected_gp']['settlement_date_sharpe']):.3f}",
        ),
        (
            "ExternalGPMaxDrawdown",
            f"{float(risk_map['selected_gp']['maximum_drawdown']):.3f}",
        ),
        (
            "TradingStaticSharePct",
            (
                f"{100 * float(cross['fixed_policy_net_pnl']['static_share_of_raw_to_gp_improvement']):.1f}"
            ),
        ),
        (
            "ExternalGPOrdinaryPnLLower",
            f"{float(gp_boot['ordinary_lower_95']):.3f}",
        ),
        (
            "ExternalGPOrdinaryPnLUpper",
            f"{float(gp_boot['ordinary_upper_95']):.3f}",
        ),
        (
            "ExternalGPBlockPnLLower",
            f"{float(gp_boot['block7_lower_95']):.3f}",
        ),
        (
            "ExternalGPBlockPnLUpper",
            f"{float(gp_boot['block7_upper_95']):.3f}",
        ),
        (
            "AugThirtyOnePendingFlag",
            (
                "1"
                if "2026-08-31"
                in pending_dates
                else "0"
            ),
        ),
    ]

    lines = [
        "% AUTO-GENERATED FILE — DO NOT EDIT MANUALLY",
        "%",
        "% Generated by src/final_pipeline/reporting.py",
        "% Values are derived from the authoritative final empirical outputs.",
        "%",
    ]

    if pending_dates:
        lines.extend(
            [
                "% IMPORTANT:",
                "% Some July-August target-dependent values remain provisional",
                "% until the official 31 August HKO settlement is refreshed.",
                "%",
            ]
        )

    for name, value in macros:
        lines.append(
            rf"\newcommand{{\{name}}}{{{value}}}"
        )

    lines.append("")

    NUMBERS_TEX.write_text(
        "\n".join(
            lines
        )
    )


# =============================================================================
# DOCUMENTATION
# =============================================================================


def write_benchmark_document(
    recon,
):
    must = recon[
        recon[
            "reconciliation_class"
        ]
        == "must_match"
    ]

    expected = recon[
        recon[
            "reconciliation_class"
        ]
        == "expected_change"
    ]

    text = """# March–June audit reconciliation

## Purpose

Original master-plan Steps 82–84 require the final March–August rebuild to
be reconciled against the previously audited empirical evidence.

This is not a requirement that every old number remain unchanged.

The previous empirical design used March–May for market development and June
for external evaluation. The final design uses March–June for development
and July–August for external validation.

Consequently the reconciliation separates:

- quantities that **must reproduce** because their sample and methodology are
  unchanged;
- quantities that are **expected to change** because the empirical allocation,
  support reconstruction or development selection changed;
- quantities that are **not directly comparable** because the evaluation
  period itself changed.

## Must-match quantities

"""

    for _, row in must.iterrows():
        text += (
            f"- `{row['metric']}`: "
            f"old `{row['audited_old_value']}`, "
            f"current `{row['current_value']}`, "
            f"pass `{row['reconciliation_pass']}`.\n"
        )

    text += """

## Expected changes

"""

    for _, row in expected.iterrows():
        text += (
            f"- `{row['metric']}`: "
            f"old `{row['audited_old_value']}`, "
            f"current `{row['current_value']}`. "
            f"{row['reason']}\n"
        )

    text += """

## Interpretation

A changed pool weight, trading rule or trading threshold is not evidence of a
reproducibility failure because those selectors were deliberately rebuilt on
the new March–June development period.

A discrepancy in a quantity marked `must_match` is different: it blocks this
stage and must be investigated before any thesis-facing numbers are treated
as final.
"""

    BENCHMARK_MD.write_text(
        text
    )


def write_reporting_document(
    pending,
):
    text = """# Thesis reporting outputs

This directory layer corresponds to original master-plan Steps 81–90.

It does not modify the empirical methodology.

## Generated authoritative objects

- `development_external_comparison.csv`
- `march_june_audit_reconciliation.csv`
- `benchmark_discrepancy_register.csv`
- `authoritative_sample_sizes.csv`
- `final_empirical_output_manifest.csv`
- `final_thesis_claims_register.csv`
- thesis-ready LaTeX tables
- curated thesis-facing figures
- `numbers.tex`

## Source hierarchy

The thesis should take numerical values in this order:

1. `numbers.tex` for scalar headline values;
2. generated `.tex` tables for corresponding table values;
3. authoritative stage CSV/JSON outputs for detailed analysis;
4. raw or intermediate files only for audit and reproducibility.

Do not manually transcribe numbers when an authoritative generated macro or
table exists.

## 31 August

"""

    if pending[
        "pending_dates"
    ]:
        text += (
            "The official 31 August HKO target is still pending. "
            "Target-dependent external values generated here must be "
            "refreshed after settlement. Development-selected quantities "
            "remain frozen.\n"
        )

    else:
        text += (
            "No external settlement target is pending.\n"
        )

    REPORTING_MD.write_text(
        text
    )


# =============================================================================
# AUDIT
# =============================================================================


def build_checks(
    weather_summary,
    market_summary,
    trading_summary,
    synthesis_summary,
    recon,
    discrepancies,
    sample_sizes,
    manifest,
    claims,
    copied_figures,
    pending,
):
    rows = []

    def add(
        check,
        passed,
        observed,
        expected,
        note="",
    ):
        rows.append(
            {
                "check":
                    check,

                "passed":
                    bool(
                        passed
                    ),

                "observed":
                    observed,

                "expected":
                    expected,

                "note":
                    note,
            }
        )

    add(
        "weather_stage_pass",
        weather_summary[
            "status"
        ]
        == "PASS",
        weather_summary[
            "status"
        ],
        "PASS",
    )

    add(
        "market_stage_pass",
        market_summary[
            "status"
        ]
        == "PASS",
        market_summary[
            "status"
        ],
        "PASS",
    )

    add(
        "trading_stage_pass",
        trading_summary[
            "status"
        ]
        == "PASS",
        trading_summary[
            "status"
        ],
        "PASS",
    )

    add(
        "synthesis_stage_pass",
        synthesis_summary[
            "status"
        ]
        == "PASS",
        synthesis_summary[
            "status"
        ],
        "PASS",
    )

    must = recon[
        recon[
            "reconciliation_class"
        ]
        == "must_match"
    ]

    add(
        "all_historical_must_match_metrics_reproduce",
        bool(
            must[
                "reconciliation_pass"
            ].all()
        ),
        int(
            must[
                "reconciliation_pass"
            ].sum()
        ),
        len(
            must
        ),
    )

    add(
        "no_unexplained_benchmark_discrepancies",
        (
            (
                len(
                    discrepancies
                )
                == 1
            )
            and (
                discrepancies.iloc[
                    0
                ][
                    "status"
                ]
                == "NO_UNEXPLAINED_DISCREPANCY"
            )
        ),
        (
            discrepancies.iloc[
                0
            ][
                "status"
            ]
            if len(
                discrepancies
            )
            else ""
        ),
        "NO_UNEXPLAINED_DISCREPANCY",
    )

    add(
        "sample_size_table_nonempty",
        len(
            sample_sizes
        )
        >= 5,
        len(
            sample_sizes
        ),
        ">=5",
    )

    add(
        "output_manifest_nonempty",
        len(
            manifest
        )
        > 50,
        len(
            manifest
        ),
        ">50",
    )

    add(
        "manifest_hashes_valid",
        (
            manifest[
                "sha256"
            ]
            .astype(str)
            .str.len()
            .eq(
                64
            )
            .all()
        ),
        int(
            manifest[
                "sha256"
            ]
            .astype(str)
            .str.len()
            .eq(
                64
            )
            .sum()
        ),
        len(
            manifest
        ),
    )

    add(
        "claims_register_nonempty",
        len(
            claims
        )
        >= 10,
        len(
            claims
        ),
        ">=10",
    )

    add(
        "numbers_tex_created",
        NUMBERS_TEX.exists(),
        NUMBERS_TEX.exists(),
        True,
    )

    add(
        "all_primary_generated_tables_exist",
        all(
            (
                TABLES
                / filename
            ).exists()
            for filename in [
                "sample_sizes.tex",
                "cross_stage_attribution.tex",
                "external_proper_scores.tex",
                "external_trading_attribution.tex",
                "trading_bootstrap_interpretation.tex",
                "rule_support_robustness.tex",
            ]
        ),
        int(
            sum(
                (
                    TABLES
                    / filename
                ).exists()
                for filename in [
                    "sample_sizes.tex",
                    "cross_stage_attribution.tex",
                    "external_proper_scores.tex",
                    "external_trading_attribution.tex",
                    "trading_bootstrap_interpretation.tex",
                    "rule_support_robustness.tex",
                ]
            )
        ),
        6,
    )

    add(
        "thesis_figures_curated",
        len(
            copied_figures
        )
        >= 4,
        len(
            copied_figures
        ),
        ">=4",
    )

    add(
        "pending_status_expected",
        pending[
            "pending_dates"
        ]
        in (
            [],
            [
                "2026-08-31"
            ],
        ),
        pending[
            "pending_dates"
        ],
        "[] or ['2026-08-31']",
    )

    status = (
        "PASS"
        if all(
            row[
                "passed"
            ]
            for row in rows
        )
        else "FAILED"
    )

    return (
        pd.DataFrame(
            rows
        ),
        status,
    )


# =============================================================================
# MAIN
# =============================================================================


def main():
    PROCESSED.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    TABLES.mkdir(
        parents=True,
        exist_ok=True,
    )

    FIGURES.mkdir(
        parents=True,
        exist_ok=True,
    )

    GENERATED.mkdir(
        parents=True,
        exist_ok=True,
    )

    required = [
        WEATHER_SUMMARY,
        MARKET_SUMMARY,
        TRADING_SUMMARY,
        SYNTHESIS_SUMMARY,
        POOL_SELECTION,
        TRADING_POLICY,
        EVENT_PANEL,
        TRADING_LEDGERS,
        MARKET_SCORES,
        MARKET_TV,
        TRADING_RISK,
        TRADING_BOOTSTRAP,
        BOOTSTRAP_INTERPRETATION,
        CROSS_STAGE,
        RULE_SUPPORT,
        EXISTING_EVIDENCE_REGISTER,
        EXISTING_THESIS_MANIFEST,
        PENDING_STATUS,
        MASTER_CONFIG,
    ]

    missing = [
        str(
            p
        )
        for p in required
        if not p.exists()
    ]

    if missing:
        raise RuntimeError(
            "Missing frozen inputs:\n"
            + "\n".join(
                missing
            )
        )

    weather_summary = read_json(
        WEATHER_SUMMARY
    )

    market_summary = read_json(
        MARKET_SUMMARY
    )

    trading_summary = read_json(
        TRADING_SUMMARY
    )

    synthesis_summary = read_json(
        SYNTHESIS_SUMMARY
    )

    pool = read_json(
        POOL_SELECTION
    )

    policy = read_json(
        TRADING_POLICY
    )

    pending = read_json(
        PENDING_STATUS
    )

    event_panel = pd.read_csv(
        EVENT_PANEL
    )

    ledgers = pd.read_csv(
        TRADING_LEDGERS
    )

    scores = pd.read_csv(
        MARKET_SCORES
    )

    tv = pd.read_csv(
        MARKET_TV
    )

    risk = pd.read_csv(
        TRADING_RISK
    )

    bootstrap_interpretation = pd.read_csv(
        BOOTSTRAP_INTERPRETATION
    )

    cross_stage = pd.read_csv(
        CROSS_STAGE
    )

    rule_support = pd.read_csv(
        RULE_SUPPORT
    )

    existing_evidence = pd.read_csv(
        EXISTING_EVIDENCE_REGISTER
    )

    thesis_manifest = pd.read_csv(
        EXISTING_THESIS_MANIFEST
    )

    # -------------------------------------------------------------------------
    # Step 81
    # -------------------------------------------------------------------------

    print(
        "Step 81: development vs external comparison..."
    )

    generalisation = (
        build_development_external_comparison(
            event_panel,
            scores,
            tv,
            risk,
        )
    )

    generalisation.to_csv(
        GENERALISATION_AUDIT,
        index=False,
        float_format="%.10f",
    )

    # -------------------------------------------------------------------------
    # Steps 82–84
    # -------------------------------------------------------------------------

    print(
        "Steps 82–84: historical audited-evidence reconciliation..."
    )

    (
        recon,
        discrepancies,
    ) = build_benchmark_reconciliation(
        weather_summary,
        pool,
        policy,
        event_panel,
        trading_summary,
    )

    recon.to_csv(
        BENCHMARK_RECON,
        index=False,
    )

    discrepancies.to_csv(
        DISCREPANCY_REGISTER,
        index=False,
    )

    write_benchmark_document(
        recon
    )

    if not (
        recon.loc[
            recon[
                "reconciliation_class"
            ]
            == "must_match",
            "reconciliation_pass",
        ].all()
    ):
        print(
            "ERROR: unexplained historical benchmark disagreement."
        )

        print(
            discrepancies.to_string(
                index=False
            )
        )

        return 2

    # -------------------------------------------------------------------------
    # Step 86
    # -------------------------------------------------------------------------

    print(
        "Step 86: authoritative sample-size table..."
    )

    sample_sizes = (
        build_sample_sizes(
            event_panel,
            ledgers,
            weather_summary,
        )
    )

    sample_sizes.to_csv(
        SAMPLE_SIZES,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 87
    # -------------------------------------------------------------------------

    print(
        "Step 87: final empirical output manifest..."
    )

    manifest = (
        build_manifest()
    )

    manifest.to_csv(
        FINAL_MANIFEST,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 88
    # -------------------------------------------------------------------------

    print(
        "Step 88: final thesis claims register..."
    )

    claims = (
        build_claims_register(
            existing_evidence,
            pending,
        )
    )

    claims.to_csv(
        FINAL_CLAIMS,
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 89
    # -------------------------------------------------------------------------

    print(
        "Step 89: generating thesis-ready tables and figures..."
    )

    copied_figures = (
        build_thesis_outputs(
            sample_sizes,
            cross_stage,
            scores,
            risk,
            bootstrap_interpretation,
            rule_support,
            thesis_manifest,
        )
    )

    copied_figures.to_csv(
        OUTPUT
        / "curated_thesis_figures.csv",
        index=False,
    )

    # -------------------------------------------------------------------------
    # Step 90
    # -------------------------------------------------------------------------

    print(
        "Step 90: generating numbers.tex..."
    )

    write_numbers_tex(
        weather_summary,
        pool,
        policy,
        event_panel,
        scores,
        tv,
        risk,
        bootstrap_interpretation,
        cross_stage,
        pending,
    )

    write_reporting_document(
        pending
    )

    # -------------------------------------------------------------------------
    # Audit
    # -------------------------------------------------------------------------

    (
        checks,
        status,
    ) = build_checks(
        weather_summary,
        market_summary,
        trading_summary,
        synthesis_summary,
        recon,
        discrepancies,
        sample_sizes,
        manifest,
        claims,
        copied_figures,
        pending,
    )

    checks.to_csv(
        REPORTING_CHECKS,
        index=False,
    )

    summary = {
        "status":
            status,

        "stage":
            "original_master_plan_steps_81_90",

        "steps_1_80_frozen":
            True,

        "new_model_fitted":
            False,

        "development_selector_changed":
            False,

        "external_data_used_for_selection":
            False,

        "selected_weather_kernel":
            weather_summary[
                "selected_kernel"
            ],

        "selected_pool_weight_gp":
            pool[
                "weight_gp"
            ],

        "selected_trading_rule":
            policy[
                "selected_rule"
            ],

        "selected_trading_threshold":
            policy[
                "selected_threshold"
            ],

        "must_match_benchmark_metrics":
            int(
                (
                    recon[
                        "reconciliation_class"
                    ]
                    == "must_match"
                ).sum()
            ),

        "must_match_failures":
            int(
                (
                    (
                        recon[
                            "reconciliation_class"
                        ]
                        == "must_match"
                    )
                    & (
                        ~recon[
                            "reconciliation_pass"
                        ]
                    )
                ).sum()
            ),

        "sample_size_rows":
            len(
                sample_sizes
            ),

        "manifest_rows":
            len(
                manifest
            ),

        "claims_rows":
            len(
                claims
            ),

        "curated_main_figures":
            len(
                copied_figures
            ),

        "numbers_tex":
            str(
                NUMBERS_TEX
            ),

        "pending_target_dates":
            pending[
                "pending_dates"
            ],
    }

    REPORTING_SUMMARY.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print(
        "status=",
        status,
    )

    print(
        "must_match_failures=",
        summary[
            "must_match_failures"
        ],
    )

    print(
        "manifest_rows=",
        summary[
            "manifest_rows"
        ],
    )

    print(
        "claims_rows=",
        summary[
            "claims_rows"
        ],
    )

    print(
        "curated_main_figures=",
        summary[
            "curated_main_figures"
        ],
    )

    print(
        "pending_target_dates=",
        summary[
            "pending_target_dates"
        ],
    )

    if status != "PASS":
        print()
        print(
            checks[
                ~checks[
                    "passed"
                ]
            ].to_string(
                index=False
            )
        )

        return 2

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
