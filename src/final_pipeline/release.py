from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys

from pathlib import Path

import pandas as pd


ROOT = Path(".")

CONFIG = Path(
    "config/final_empirical_config.json"
)

REPORTING_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "reporting_stage_summary.json"
)

SYNTHESIS_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "synthesis_stage_summary.json"
)

TRADING_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "trading_stage_summary.json"
)

MARKET_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "market_stage_summary.json"
)

WEATHER_SUMMARY = Path(
    "outputs/final_pipeline/audit/"
    "weather_models_summary.json"
)

CLAIMS = Path(
    "outputs/final_pipeline/reporting/"
    "final_thesis_claims_register.csv"
)

SAMPLE_SIZES = Path(
    "outputs/final_pipeline/reporting/"
    "authoritative_sample_sizes.csv"
)

REPORTING_MANIFEST = Path(
    "outputs/final_pipeline/reporting/"
    "final_empirical_output_manifest.csv"
)

NUMBERS = Path(
    "outputs/final_pipeline/thesis/"
    "generated/numbers.tex"
)

PENDING = Path(
    "outputs/final_pipeline/synthesis/"
    "pending_target_status.json"
)

CROSS_STAGE = Path(
    "outputs/final_pipeline/synthesis/"
    "cross_stage_attribution.csv"
)

BOOTSTRAP = Path(
    "outputs/final_pipeline/synthesis/"
    "bootstrap_interpretation.csv"
)

RULE_SUPPORT = Path(
    "outputs/final_pipeline/synthesis/"
    "rule_support_robustness.csv"
)


RELEASE_DIR = Path(
    "outputs/final_pipeline/release"
)

CORE_MAP = RELEASE_DIR / "seven_question_core_narrative.csv"

PRUNING = RELEASE_DIR / "thesis_pruning_register.csv"

THREE_LAYER = RELEASE_DIR / "three_layer_final_audit.csv"

MANIFEST = RELEASE_DIR / "final_release_manifest.csv"

SUMMARY = RELEASE_DIR / "final_release_summary.json"

CHECKSUMS = RELEASE_DIR / "final_release_checksums.sha256"

EXAMINER = Path(
    "docs/final_pipeline/EXAMINER_README.md"
)

RUNBOOK = Path(
    "docs/final_pipeline/REPRODUCIBILITY_RUNBOOK.md"
)

HANDOFF = Path(
    "docs/final_pipeline/FINAL_THESIS_HANDOFF.md"
)

STATUS_MD = Path(
    "FINAL_PIPELINE_STATUS.md"
)

README = Path(
    "README.md"
)


def read_json(path: Path):
    return json.loads(
        path.read_text()
    )


def sha256(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            b = f.read(
                1024 * 1024
            )

            if not b:
                break

            h.update(b)

    return h.hexdigest()


def parse_macros(path: Path):
    text = path.read_text()

    pattern = re.compile(
        r"\\newcommand\{\\([A-Za-z]+)\}\{([^}]*)\}"
    )

    return {
        name: value
        for name, value
        in pattern.findall(text)
    }


def passed_csv(path: Path):
    x = pd.read_csv(path)

    if "passed" not in x.columns:
        return False

    return bool(
        x[
            "passed"
        ]
        .astype(str)
        .str.lower()
        .eq("true")
        .all()
    )


def update_root_readme(release_state: str):
    start = "<!-- FINAL_PIPELINE_ENTRY_START -->"
    end = "<!-- FINAL_PIPELINE_ENTRY_END -->"

    block = f"""\
{start}

## Final March--August MSc empirical pipeline

The authoritative dissertation empirical implementation is on branch
`final-march-august-reproducible-pipeline`.

Current release state: **{release_state}**.

Examiner entry point:

`docs/final_pipeline/EXAMINER_README.md`

One-command audit replay:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

The final empirical source hierarchy is:

1. `outputs/final_pipeline/thesis/generated/numbers.tex`
2. `outputs/final_pipeline/thesis/tables/`
3. `outputs/final_pipeline/reporting/final_thesis_claims_register.csv`
4. authoritative CSV/JSON outputs under `outputs/final_pipeline/`
5. pipeline implementation under `src/final_pipeline/`

Do not use historical branches or obsolete pre-final outputs as thesis
numerical sources.

{end}
"""

    old = (
        README.read_text()
        if README.exists()
        else ""
    )

    if start in old and end in old:
        before = old.split(
            start,
            1,
        )[0]

        after = old.split(
            end,
            1,
        )[1]

        text = (
            before.rstrip()
            + "\n\n"
            + block
            + after
        )

    else:
        text = (
            old.rstrip()
            + "\n\n"
            + block
        )

    README.write_text(
        text.rstrip()
        + "\n"
    )


def build_core_map(macros, pending_dates):
    rows = [
        {
            "question_id": "Q1",
            "core_question":
                "How weak is the raw deterministic forecast as a probabilistic signal?",
            "answer":
                (
                    "Raw deterministic forecasts have materially worse "
                    f"continuous CRPS ({macros['WeatherRawCRPS']}) than "
                    "either probabilistic correction."
                ),
            "primary_evidence":
                "chronological CRPS / weather model attribution",
            "thesis_role":
                "main_text",
            "pending_aug31":
                False,
        },
        {
            "question_id": "Q2",
            "core_question":
                "How much value comes simply from representing uncertainty probabilistically?",
            "answer":
                (
                    "The static Gaussian captures "
                    f"{macros['WeatherStaticSharePct']}% of the "
                    "raw-to-selected-GP CRPS improvement."
                ),
            "primary_evidence":
                "cross-stage attribution",
            "thesis_role":
                "main_text",
            "pending_aug31":
                False,
        },
        {
            "question_id": "Q3",
            "core_question":
                "Does the GP add substantial value beyond the simple static correction?",
            "answer":
                (
                    "The GP improves continuous CRPS modestly, while the "
                    "static correction is slightly closer to Polymarket "
                    "externally in total variation; GP marginal value is "
                    "therefore real but limited."
                ),
            "primary_evidence":
                "weather CRPS + external total variation",
            "thesis_role":
                "main_text",
            "pending_aug31":
                bool(pending_dates),
        },
        {
            "question_id": "Q4",
            "core_question":
                "How do weather probabilities compare with Polymarket?",
            "answer":
                (
                    "Polymarket has lower external proper-score loss than "
                    "either standalone weather model."
                ),
            "primary_evidence":
                "external proper scores",
            "thesis_role":
                "main_text",
            "pending_aug31":
                bool(pending_dates),
        },
        {
            "question_id": "Q5",
            "core_question":
                "Do the weather forecast and prediction market contain complementary information?",
            "answer":
                (
                    "The development-selected convex pool uses GP weight "
                    f"{macros['FinalPoolGPWeight']} and market weight "
                    f"{macros['FinalPoolMarketWeight']}; its external "
                    "proper-score point estimate is best, although its "
                    "advantage over Polymarket is not statistically resolved."
                ),
            "primary_evidence":
                "convex pool selection + paired score inference",
            "thesis_role":
                "main_text",
            "pending_aug31":
                bool(pending_dates),
        },
        {
            "question_id": "Q6",
            "core_question":
                "Does the weather signal translate into external economic value?",
            "answer":
                (
                    "Under the frozen policy, raw/static/GP external PnL is "
                    f"{macros['ExternalRawPnL']}, "
                    f"{macros['ExternalStaticPnL']} and "
                    f"{macros['ExternalGPPnL']}; GP executes "
                    f"{macros['ExternalGPTrades']} trades with "
                    f"non-annualised Sharpe {macros['ExternalGPSharpe']}."
                ),
            "primary_evidence":
                "fixed-policy external trading attribution",
            "thesis_role":
                "main_text",
            "pending_aug31":
                bool(pending_dates),
        },
        {
            "question_id": "Q7",
            "core_question":
                "How robust and nonlinear is the forecast-to-trading link?",
            "answer":
                (
                    "PnL inference is dependence-sensitive, rule selection "
                    "has a support-composition caveat, and forecast "
                    "perturbations produce nonlinear contract-selection "
                    "and activation effects."
                ),
            "primary_evidence":
                "bootstrap + rule support + perturbation + concentration diagnostics",
            "thesis_role":
                "main_text_and_appendix",
            "pending_aug31":
                bool(pending_dates),
        },
    ]

    return pd.DataFrame(rows)


def build_pruning(claims):
    x = claims.copy()

    mapping = {
        "MAIN_OR_DISCUSSION":
            "KEEP_MAIN_OR_DISCUSSION",

        "APPENDIX":
            "KEEP_APPENDIX_ONLY",

        "DO_NOT_USE_AS_PRIMARY":
            "EXCLUDE_FROM_PRIMARY_RESULTS",
    }

    x[
        "final_empirical_decision"
    ] = x[
        "final_inclusion_status"
    ].map(mapping).fillna(
        "KEEP_WITH_CAUTION"
    )

    x[
        "why"
    ] = x.apply(
        lambda row:
            (
                "Directly advances the seven-question thesis narrative."
                if row[
                    "final_empirical_decision"
                ]
                == "KEEP_MAIN_OR_DISCUSSION"
                else
                (
                    "Useful robustness evidence but too detailed for the core narrative."
                    if row[
                        "final_empirical_decision"
                    ]
                    == "KEEP_APPENDIX_ONLY"
                    else
                    (
                        "Potentially misleading or low-value as a headline thesis result."
                        if row[
                            "final_empirical_decision"
                        ]
                        == "EXCLUDE_FROM_PRIMARY_RESULTS"
                        else
                        "Retain only with the stated qualification."
                    )
                )
            ),
        axis=1,
    )

    return x


def build_three_layer_audit(
    reporting,
    synthesis,
    trading,
    market,
    weather,
    pending_dates,
    macros,
):
    audit_files = [
        Path(
            "outputs/final_pipeline/audit/"
            "reporting_stage_integrity_checks.csv"
        ),
        Path(
            "outputs/final_pipeline/audit/"
            "synthesis_stage_integrity_checks.csv"
        ),
        Path(
            "outputs/final_pipeline/audit/"
            "trading_stage_integrity_checks.csv"
        ),
        Path(
            "outputs/final_pipeline/audit/"
            "market_stage_integrity_checks.csv"
        ),
    ]

    all_integrity = all(
        path.exists()
        and passed_csv(path)
        for path in audit_files
    )

    thesis_text = ""

    for path in Path(
        "outputs/final_pipeline/thesis"
    ).rglob("*.tex"):
        thesis_text += (
            "\n"
            + path.read_text()
        )

    stale_signatures = [
        "event_day_open",
        "0.489",
    ]

    stale_absent = not any(
        x in thesis_text
        for x in stale_signatures
    )

    rows = [
        {
            "layer":
                "data",

            "check":
                "all_upstream_stage_statuses_pass",

            "passed":
                (
                    weather[
                        "status"
                    ]
                    == "PASS"
                    and market[
                        "status"
                    ]
                    == "PASS"
                    and trading[
                        "status"
                    ]
                    == "PASS"
                    and synthesis[
                        "status"
                    ]
                    == "PASS"
                    and reporting[
                        "status"
                    ]
                    == "PASS"
                ),

            "interpretation":
                "All frozen empirical stages report PASS.",
        },
        {
            "layer":
                "data",

            "check":
                "only_expected_external_target_may_be_pending",

            "passed":
                pending_dates in (
                    [],
                    [
                        "2026-08-31"
                    ],
                ),

            "interpretation":
                (
                    "The only permitted unresolved target is "
                    "31 August 2026."
                ),
        },
        {
            "layer":
                "methodology",

            "check":
                "development_selectors_frozen",

            "passed":
                (
                    reporting[
                        "selected_weather_kernel"
                    ]
                    == "matern32"
                    and abs(
                        float(
                            reporting[
                                "selected_pool_weight_gp"
                            ]
                        )
                        - 0.188
                    )
                    < 1e-12
                    and reporting[
                        "selected_trading_rule"
                    ]
                    == "24h_prior"
                    and abs(
                        float(
                            reporting[
                                "selected_trading_threshold"
                            ]
                        )
                        - 0.15
                    )
                    < 1e-12
                ),

            "interpretation":
                (
                    "Matérn-3/2, pool weight 0.188, "
                    "24h_prior and h=0.15 remain frozen."
                ),
        },
        {
            "layer":
                "methodology",

            "check":
                "external_not_used_for_selection",

            "passed":
                (
                    reporting[
                        "external_data_used_for_selection"
                    ]
                    is False
                ),

            "interpretation":
                "July-August remains external evaluation.",
        },
        {
            "layer":
                "methodology",

            "check":
                "all_integrity_check_files_pass",

            "passed":
                all_integrity,

            "interpretation":
                (
                    "Market, trading, synthesis and reporting "
                    "integrity gates all pass."
                ),
        },
        {
            "layer":
                "results",

            "check":
                "authoritative_numbers_file_complete",

            "passed":
                all(
                    key in macros
                    for key in [
                        "WeatherRawCRPS",
                        "WeatherMaternCRPS",
                        "FinalPoolGPWeight",
                        "ExternalGPPnL",
                        "TradingThreshold",
                    ]
                ),

            "interpretation":
                "Headline scalar values are centrally generated.",
        },
        {
            "layer":
                "results",

            "check":
                "stale_pre_final_signatures_absent_from_thesis_outputs",

            "passed":
                stale_absent,

            "interpretation":
                (
                    "Old event_day_open / w=0.489 values are not "
                    "present in thesis-facing generated TeX."
                ),
        },
    ]

    return pd.DataFrame(rows)


def write_examiner_docs(
    release_state,
    pending_dates,
    core,
    pruning,
):
    pending_text = (
        "31 August 2026 remains pending in target-dependent external outputs."
        if pending_dates
        else
        "All March-August settlement targets are complete."
    )

    EXAMINER.write_text(
        f"""# Examiner entry point — final empirical pipeline

## Status

{release_state}

{pending_text}

## Start here

1. `config/final_empirical_config.json`
2. `docs/final_pipeline/methodology.md`
3. `docs/final_pipeline/weather_models.md`
4. `docs/final_pipeline/market_books.md`
5. `docs/final_pipeline/trading.md`
6. `docs/final_pipeline/synthesis.md`
7. `docs/final_pipeline/FINAL_THESIS_HANDOFF.md`

## Reproduce / verify

Fast deterministic audit:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

Full rebuild:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The full rebuild may require live access to the original official/public
data endpoints. The audit mode verifies the committed empirical artefacts,
tests, frozen selections and thesis-facing reporting layer.

## Numerical source of truth

Use:

`outputs/final_pipeline/thesis/generated/numbers.tex`

The branch deliberately preserves historical audit outputs, but old values
must not be used in place of the final reporting layer.
"""
    )

    RUNBOOK.write_text(
        """# Reproducibility runbook

## Audit replay

From the repository root:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

This performs no model reselection and no data mutation. It rebuilds the
release metadata and runs all `tests/final_pipeline/test_*.py` tests.

## Full empirical rebuild

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The intended stage order is:

1. HKO target acquisition/certification;
2. ECMWF deterministic forecast reconstruction;
3. residual-panel construction;
4. probabilistic weather-model estimation;
5. Polymarket event-book reconstruction;
6. scoring and market comparison;
7. frozen-policy trading and forecast-risk analysis;
8. synthesis;
9. thesis reporting;
10. release verification.

Live endpoint availability can affect acquisition in a future rerun.
Development/external allocations and all methodological rules are frozen in
`config/final_empirical_config.json`.

## 31 August

If the final target is still pending, use:

```bash
bash scripts/final_pipeline/refresh_aug31.sh
```

The refresh must not change:

- Matérn-3/2 weather-kernel selection;
- GP pool weight 0.188;
- 24h_prior trading rule;
- threshold 0.15.
"""
    )

    main_count = int(
        (
            pruning[
                "final_empirical_decision"
            ]
            == "KEEP_MAIN_OR_DISCUSSION"
        ).sum()
    )

    appendix_count = int(
        (
            pruning[
                "final_empirical_decision"
            ]
            == "KEEP_APPENDIX_ONLY"
        ).sum()
    )

    excluded_count = int(
        (
            pruning[
                "final_empirical_decision"
            ]
            == "EXCLUDE_FROM_PRIMARY_RESULTS"
        ).sum()
    )

    lines = [
        "# Final empirical-to-thesis handoff",
        "",
        "The empirical build is closed except for the controlled 31-August target refresh if required.",
        "",
        "## Seven-question narrative",
        "",
    ]

    for _, row in core.iterrows():
        lines.extend(
            [
                f"### {row['question_id']}. {row['core_question']}",
                "",
                str(
                    row[
                        "answer"
                    ]
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Pruning discipline",
            "",
            f"- Main/discussion claims retained: {main_count}",
            f"- Appendix-only claims retained: {appendix_count}",
            f"- Claims excluded from primary results: {excluded_count}",
            "",
            "The final thesis should not add every available robustness output merely because it exists.",
            "Use the claims register and seven-question map to preserve a concise empirical argument.",
            "",
            "## Numerical source",
            "",
            "`outputs/final_pipeline/thesis/generated/numbers.tex`",
            "",
        ]
    )

    HANDOFF.write_text(
        "\n".join(lines)
    )


def write_status(
    release_state,
    pending_dates,
):
    STATUS_MD.write_text(
        f"""# Final empirical pipeline status

**State:** {release_state}

**Branch:** `final-march-august-reproducible-pipeline`

Frozen development selections:

- weather kernel: Matérn-3/2;
- convex-pool GP weight: 0.188;
- convex-pool market weight: 0.812;
- trading decision rule: 24h prior;
- trading probability-gap threshold: 0.15;
- reference cost: 0.01.

Pending external targets: `{pending_dates}`.

No further empirical model development is authorised in this branch.
The only permitted target-dependent update is the controlled 31-August
settlement refresh.
"""
    )


def build_manifest():
    """Build the release manifest from Git-tracked files only."""

    include_prefixes = (
        "config/",
        "environment/final_pipeline/",
        "src/final_pipeline/",
        "tests/final_pipeline/",
        "scripts/final_pipeline/",
        "docs/final_pipeline/",
        "data/processed/final_pipeline/",
        "outputs/final_pipeline/audit/",
        "outputs/final_pipeline/weather/",
        "outputs/final_pipeline/market/",
        "outputs/final_pipeline/trading/",
        "outputs/final_pipeline/synthesis/",
        "outputs/final_pipeline/reporting/",
        "outputs/final_pipeline/thesis/",
    )

    include_exact = {
        "README.md",
        "FINAL_PIPELINE_STATUS.md",
    }

    tracked = subprocess.check_output(
        ["git", "ls-files"],
        text=True,
    ).splitlines()

    files = []

    for item in tracked:
        item = item.strip()

        if not item:
            continue

        if item in include_exact or item.startswith(include_prefixes):
            p = Path(item)

            if p.exists() and p.is_file():
                files.append(p)

    files = sorted(
        files,
        key=lambda p: str(p),
    )

    rows = []

    for p in files:
        rows.append(
            {
                "path": str(p),
                "bytes": p.stat().st_size,
                "sha256": sha256(p),
            }
        )

    return pd.DataFrame(rows)

def main():
    RELEASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    required = [
        CONFIG,
        REPORTING_SUMMARY,
        SYNTHESIS_SUMMARY,
        TRADING_SUMMARY,
        MARKET_SUMMARY,
        WEATHER_SUMMARY,
        CLAIMS,
        SAMPLE_SIZES,
        REPORTING_MANIFEST,
        NUMBERS,
        PENDING,
        CROSS_STAGE,
        BOOTSTRAP,
        RULE_SUPPORT,
    ]

    missing = [
        str(path)
        for path in required
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Missing authoritative closure inputs:\n"
            + "\n".join(missing)
        )

    config = read_json(CONFIG)
    reporting = read_json(REPORTING_SUMMARY)
    synthesis = read_json(SYNTHESIS_SUMMARY)
    trading = read_json(TRADING_SUMMARY)
    market = read_json(MARKET_SUMMARY)
    weather = read_json(WEATHER_SUMMARY)
    pending = read_json(PENDING)

    claims = pd.read_csv(CLAIMS)
    macros = parse_macros(NUMBERS)

    pending_dates = pending[
        "pending_dates"
    ]

    release_state = (
        "FINAL_RELEASE_COMPLETE"
        if not pending_dates
        else
        "RELEASE_CANDIDATE_PENDING_2026_08_31_SETTLEMENT"
    )

    # Step 91
    pruning = build_pruning(
        claims
    )

    pruning.to_csv(
        PRUNING,
        index=False,
    )

    # Step 92
    core = build_core_map(
        macros,
        pending_dates,
    )

    core.to_csv(
        CORE_MAP,
        index=False,
    )

    # Steps 93-94 / 100
    write_examiner_docs(
        release_state,
        pending_dates,
        core,
        pruning,
    )

    write_status(
        release_state,
        pending_dates,
    )

    update_root_readme(
        release_state
    )

    # Step 97
    audit = build_three_layer_audit(
        reporting,
        synthesis,
        trading,
        market,
        weather,
        pending_dates,
        macros,
    )

    audit.to_csv(
        THREE_LAYER,
        index=False,
    )

    if not audit[
        "passed"
    ].all():
        print(
            audit[
                ~audit[
                    "passed"
                ]
            ].to_string(
                index=False
            )
        )

        return 2

    # Step 98
    manifest = build_manifest()

    manifest.to_csv(
        MANIFEST,
        index=False,
    )

    checksum_lines = [
        f"{row.sha256}  {row.path}"
        for row in manifest.itertuples()
    ]

    CHECKSUMS.write_text(
        "\n".join(
            checksum_lines
        )
        + "\n"
    )

    # Step 99 / 101 state
    recommended_tag = (
        "msc-final-pipeline-final"
        if not pending_dates
        else
        "msc-final-pipeline-rc-pre-aug31"
    )

    summary = {
        "status":
            "PASS",

        "stage":
            "original_master_plan_steps_91_102",

        "release_state":
            release_state,

        "steps_1_90_frozen":
            True,

        "new_empirical_modeling":
            False,

        "external_data_used_for_reselection":
            False,

        "weather_kernel":
            reporting[
                "selected_weather_kernel"
            ],

        "pool_weight_gp":
            reporting[
                "selected_pool_weight_gp"
            ],

        "trading_rule":
            reporting[
                "selected_trading_rule"
            ],

        "trading_threshold":
            reporting[
                "selected_trading_threshold"
            ],

        "pending_target_dates":
            pending_dates,

        "permitted_future_empirical_change":
            (
                "31-August target-dependent refresh only"
                if pending_dates
                else "none"
            ),

        "core_questions":
            len(core),

        "claims_total":
            len(pruning),

        "main_or_discussion_claims":
            int(
                (
                    pruning[
                        "final_empirical_decision"
                    ]
                    == "KEEP_MAIN_OR_DISCUSSION"
                ).sum()
            ),

        "appendix_only_claims":
            int(
                (
                    pruning[
                        "final_empirical_decision"
                    ]
                    == "KEEP_APPENDIX_ONLY"
                ).sum()
            ),

        "excluded_primary_claims":
            int(
                (
                    pruning[
                        "final_empirical_decision"
                    ]
                    == "EXCLUDE_FROM_PRIMARY_RESULTS"
                ).sum()
            ),

        "three_layer_audit_checks":
            len(audit),

        "release_manifest_files":
            len(manifest),

        "recommended_tag":
            recommended_tag,
    }

    SUMMARY.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
