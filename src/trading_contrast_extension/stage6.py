from __future__ import annotations

from pathlib import Path
import json
import shutil

import numpy as np
import pandas as pd


ROOT = Path(".")
S2 = ROOT / "outputs/trading_contrast_extension/stage2"
S3 = ROOT / "outputs/trading_contrast_extension/stage3"
S4 = ROOT / "outputs/trading_contrast_extension/stage4"
S5 = ROOT / "outputs/trading_contrast_extension/stage5"
OUT = ROOT / "outputs/trading_contrast_extension/stage6"
THESIS = ROOT / "outputs/trading_contrast_extension/thesis"

TABLES = THESIS / "tables"
FIGURES = THESIS / "figures"
GENERATED = THESIS / "generated"

for p in [
    OUT,
    TABLES,
    FIGURES,
    GENERATED,
]:
    p.mkdir(
        parents=True,
        exist_ok=True,
    )


def fmt(x: float, digits: int = 3) -> str:
    if pd.isna(x):
        return "--"
    return f"{float(x):.{digits}f}"


def write_latex_table(
    df: pd.DataFrame,
    path: Path,
    caption: str,
    label: str,
) -> None:
    tex = df.to_latex(
        index=False,
        escape=True,
        caption=caption,
        label=label,
        float_format=lambda x: f"{x:.3f}",
    )
    path.write_text(tex)


def main() -> None:
    stage2 = json.loads(
        (S2 / "stage2_summary.json").read_text()
    )
    stage3 = json.loads(
        (S3 / "stage3_summary.json").read_text()
    )
    stage4 = json.loads(
        (S4 / "stage4_summary.json").read_text()
    )
    stage5 = json.loads(
        (S5 / "stage5_summary.json").read_text()
    )

    for name, obj in [
        ("stage2", stage2),
        ("stage3", stage3),
        ("stage4", stage4),
        ("stage5", stage5),
    ]:
        if obj["status"] != "PASS":
            raise RuntimeError(
                f"{name} is not PASS."
            )

    risk = pd.read_csv(
        S3 / "external_eight_portfolio_risk_table.csv"
    )

    profit = pd.read_csv(
        S4 / "portfolio_profitability_inference.csv"
    )

    taec_fixed = pd.read_csv(
        S4 / "taec_vs_fixed_inference.csv"
    )

    convergence = pd.read_csv(
        S4 / "market_convergence_inference.csv"
    )

    sharpe_diff = pd.read_csv(
        S4 / "sharpe_strategy_difference_inference.csv"
    )

    break_even = pd.read_csv(
        S5 / "transaction_cost_break_even_summary.csv"
    )

    break_even = break_even.loc[
        break_even["empirical_period"]
        == "external_validation"
    ].copy()

    open_only = pd.read_csv(
        S5 / "taec_open_only_execution_sensitivity.csv"
    )

    open_only = open_only.loc[
        open_only["empirical_period"]
        == "external_validation"
    ].copy()

    deletion = pd.read_csv(
        S5 / "taec_minus_fixed_seven_observation_deletion.csv"
    )

    perturb = pd.read_csv(
        S5 / "temperature_perturbation_robustness_summary.csv"
    )

    greek = pd.read_csv(
        S3 / "portfolio_greek_risk_summary.csv"
    )

    greek = greek.loc[
        greek["empirical_period"]
        == "external_validation"
    ].copy()

    # ------------------------------------------------------------------
    # Claims/pruning register.
    # ------------------------------------------------------------------
    claims = [
        {
            "claim_id": "TC1",
            "destination": "MAIN_RESULTS",
            "priority": 1,
            "claim": (
                "The conservative fixed strategy remains the primary trading "
                "policy; the multi-contract TAEC-11 strategy is an exploratory "
                "stress-test extension and does not replace it."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC2",
            "destination": "MAIN_RESULTS",
            "priority": 1,
            "claim": (
                "On the 61-date external support, Fixed Matérn earns positive "
                "net PnL, while TAEC-11 Matérn is negative after costs."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC3",
            "destination": "MAIN_RESULTS",
            "priority": 1,
            "claim": (
                "TAEC-minus-Fixed external PnL is negative for Raw, Static, "
                "RBF and Matérn and remains statistically resolved under the "
                "primary moving-block/Holm procedure."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC4",
            "destination": "MAIN_RESULTS",
            "priority": 1,
            "claim": (
                "TAEC losses are primarily a turnover/friction result: gross "
                "pre-cost convergence PnL is positive for each model, but its "
                "per-position break-even cost lies far below the frozen 0.02 "
                "round-trip cost."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC5",
            "destination": "DISCUSSION",
            "priority": 1,
            "claim": (
                "Positive pre-cost TAEC convergence point estimates are not "
                "statistically resolved after dependence-aware inference and "
                "must not be described as proven market convergence."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC6",
            "destination": "DISCUSSION",
            "priority": 1,
            "claim": (
                "Forcing every TAEC position to event-day-open exit improves "
                "the probabilistic-model TAEC PnL but leaves it negative at "
                "the frozen cost assumption."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC7",
            "destination": "DISCUSSION",
            "priority": 1,
            "claim": (
                "TAEC remains worse than Fixed after deleting every possible "
                "seven-observation block from the 61-date external sample."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC8",
            "destination": "DISCUSSION",
            "priority": 2,
            "claim": (
                "Local temperature perturbations reveal a nonlinear mapping "
                "from forecast location to trading decisions and PnL; the "
                "Greek-like diagnostics are finite-difference forecast-risk "
                "sensitivities rather than option-pricing Greeks."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC9",
            "destination": "APPENDIX",
            "priority": 2,
            "claim": (
                "Full eight-portfolio Sharpe, Sortino, VaR, expected shortfall, "
                "drawdown, capital-efficiency and Greek exposure tables."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC10",
            "destination": "APPENDIX",
            "priority": 2,
            "claim": (
                "Alternative TAEC discrepancy thresholds are diagnostic only "
                "and do not reselect the frozen 0.02 strategy."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC11",
            "destination": "APPENDIX",
            "priority": 3,
            "claim": (
                "Alternative moving-block lengths, monthly splits, concentration "
                "and leave-one-date-out results are robustness diagnostics."
            ),
            "safe_use": True,
        },
        {
            "claim_id": "TC12",
            "destination": "DO_NOT_USE_AS_PRIMARY",
            "priority": 3,
            "claim": (
                "The ex-post best TAEC threshold must not be presented as a "
                "selected or validated trading rule."
            ),
            "safe_use": False,
        },
        {
            "claim_id": "TC13",
            "destination": "DO_NOT_USE_AS_PRIMARY",
            "priority": 3,
            "claim": (
                "Raw deterministic finite-difference Greek magnitudes are "
                "discontinuous diagnostics and should not be interpreted as "
                "smooth derivatives."
            ),
            "safe_use": False,
        },
        {
            "claim_id": "TC14",
            "destination": "DO_NOT_USE_AS_PRIMARY",
            "priority": 3,
            "claim": (
                "TAEC snapshot prices are not executable historical bid/ask "
                "fills; results must not be described as a live-trading backtest."
            ),
            "safe_use": False,
        },
    ]

    claims_df = pd.DataFrame(claims)
    claims_df.to_csv(
        OUT / "thesis_value_pruning_register.csv",
        index=False,
    )

    # ------------------------------------------------------------------
    # Main external trading table.
    # ------------------------------------------------------------------
    main = risk[
        [
            "strategy",
            "model",
            "positions",
            "total_net_pnl",
            "gross_pre_cost_pnl",
            "total_transaction_cost",
            "nonannualised_sharpe",
            "empirical_expected_shortfall95_loss",
            "maximum_drawdown",
        ]
    ].copy()

    main = main.rename(
        columns={
            "strategy": "Strategy",
            "model": "Model",
            "positions": "Positions",
            "total_net_pnl": "Net PnL",
            "gross_pre_cost_pnl": "Pre-cost PnL",
            "total_transaction_cost": "Costs",
            "nonannualised_sharpe": "Sharpe",
            "empirical_expected_shortfall95_loss": "ES95 loss",
            "maximum_drawdown": "Max drawdown",
        }
    )

    write_latex_table(
        main,
        TABLES / "external_strategy_model_comparison.tex",
        (
            "External trading performance for the conservative fixed policy "
            "and exploratory TAEC-11 strategy."
        ),
        "tab:trading-contrast-external",
    )

    # ------------------------------------------------------------------
    # TAEC robustness table.
    # ------------------------------------------------------------------
    robust = taec_fixed[
        [
            "model",
            "mbb_observed_total",
            "mbb_ci95_total_lower",
            "mbb_ci95_total_upper",
            "holm_p_two_sided",
        ]
    ].merge(
        break_even.loc[
            break_even["strategy"]
            == "taec11",
            [
                "model",
                "break_even_cost_per_position",
            ],
        ],
        on="model",
        how="left",
        validate="one_to_one",
    ).merge(
        open_only[
            [
                "model",
                "open_only_net_pnl",
            ]
        ],
        on="model",
        how="left",
        validate="one_to_one",
    ).merge(
        deletion[
            [
                "model",
                "max_after_deleting_any_7_observation_block",
            ]
        ],
        on="model",
        how="left",
        validate="one_to_one",
    )

    robust = robust.rename(
        columns={
            "model": "Model",
            "mbb_observed_total": "TAEC-Fixed PnL",
            "mbb_ci95_total_lower": "CI lower",
            "mbb_ci95_total_upper": "CI upper",
            "holm_p_two_sided": "Holm p",
            "break_even_cost_per_position": "TAEC break-even cost",
            "open_only_net_pnl": "Open-only TAEC PnL",
            "max_after_deleting_any_7_observation_block": (
                "Best TAEC-Fixed after deleting 7"
            ),
        }
    )

    write_latex_table(
        robust,
        TABLES / "taec_robustness_summary.tex",
        (
            "External robustness of the exploratory TAEC-11 strategy relative "
            "to the fixed policy."
        ),
        "tab:taec-robustness",
    )

    # ------------------------------------------------------------------
    # Greek-like table, kept concise.
    # ------------------------------------------------------------------
    greek_table = greek[
        [
            "strategy",
            "model",
            "mean_gross_abs_delta_per_c",
            "mean_abs_net_delta_per_c",
            "mean_gross_abs_gamma_per_c2",
            "mean_abs_net_gamma_per_c2",
        ]
    ].copy()

    greek_table = greek_table.rename(
        columns={
            "strategy": "Strategy",
            "model": "Model",
            "mean_gross_abs_delta_per_c": "Mean gross |Delta|",
            "mean_abs_net_delta_per_c": "Mean |net Delta|",
            "mean_gross_abs_gamma_per_c2": "Mean gross |Gamma|",
            "mean_abs_net_gamma_per_c2": "Mean |net Gamma|",
        }
    )

    write_latex_table(
        greek_table,
        TABLES / "greek_like_risk_summary.tex",
        (
            "Finite-difference forecast-risk sensitivities at the primary "
            "0.25 degree C perturbation."
        ),
        "tab:greek-like-risk",
    )

    # ------------------------------------------------------------------
    # Numbers.tex.
    # ------------------------------------------------------------------
    def risk_row(strategy: str, model: str) -> pd.Series:
        x = risk.loc[
            (risk["strategy"] == strategy)
            & (risk["model"] == model)
        ]
        if len(x) != 1:
            raise RuntimeError(
                f"Risk row not unique: {strategy}/{model}"
            )
        return x.iloc[0]

    def break_row(strategy: str, model: str) -> pd.Series:
        x = break_even.loc[
            (break_even["strategy"] == strategy)
            & (break_even["model"] == model)
        ]
        if len(x) != 1:
            raise RuntimeError(
                f"Break-even row not unique: {strategy}/{model}"
            )
        return x.iloc[0]

    def contrast_row(model: str) -> pd.Series:
        x = taec_fixed.loc[
            taec_fixed["model"] == model
        ]
        if len(x) != 1:
            raise RuntimeError(
                f"TAEC-vs-Fixed row not unique: {model}"
            )
        return x.iloc[0]

    mat_fixed = risk_row(
        "fixed_settlement",
        "matern32",
    )
    mat_taec = risk_row(
        "taec11",
        "matern32",
    )
    static_fixed = risk_row(
        "fixed_settlement",
        "static",
    )
    rbf_fixed = risk_row(
        "fixed_settlement",
        "rbf",
    )

    macros = {
        "TradingExternalDates": "61",
        "FixedMaternPnL": fmt(
            mat_fixed["total_net_pnl"],
            3,
        ),
        "FixedStaticPnL": fmt(
            static_fixed["total_net_pnl"],
            3,
        ),
        "FixedRBFPnL": fmt(
            rbf_fixed["total_net_pnl"],
            3,
        ),
        "TAECMaternPnL": fmt(
            mat_taec["total_net_pnl"],
            3,
        ),
        "TAECMaternPreCostPnL": fmt(
            mat_taec["gross_pre_cost_pnl"],
            3,
        ),
        "TAECMaternPositions": str(
            int(mat_taec["positions"])
        ),
        "TAECMaternBreakEvenCost": fmt(
            break_row(
                "taec11",
                "matern32",
            )[
                "break_even_cost_per_position"
            ],
            4,
        ),
        "TAECMaternVsFixed": fmt(
            contrast_row(
                "matern32"
            )[
                "mbb_observed_total"
            ],
            3,
        ),
        "TAECMaternVsFixedHolmP": fmt(
            contrast_row(
                "matern32"
            )[
                "holm_p_two_sided"
            ],
            4,
        ),
        "TAECStaticBreakEvenCost": fmt(
            break_row(
                "taec11",
                "static",
            )[
                "break_even_cost_per_position"
            ],
            4,
        ),
        "TAECRBFBreakEvenCost": fmt(
            break_row(
                "taec11",
                "rbf",
            )[
                "break_even_cost_per_position"
            ],
            4,
        ),
        "TAECRawBreakEvenCost": fmt(
            break_row(
                "taec11",
                "raw",
            )[
                "break_even_cost_per_position"
            ],
            4,
        ),
        "TAECRoundTripCost": "0.020",
        "FixedTradeCost": "0.010",
    }

    numbers = "".join(
        f"\\newcommand{{\\{name}}}{{{value}}}\n"
        for name, value in macros.items()
    )

    (GENERATED / "numbers.tex").write_text(
        numbers
    )

    # ------------------------------------------------------------------
    # Curated figures.
    # ------------------------------------------------------------------
    figure_sources = [
        (
            S3 / "external_cumulative_pnl_fixed_settlement.png",
            "external_cumulative_pnl_fixed_settlement.png",
        ),
        (
            S3 / "external_cumulative_pnl_taec11.png",
            "external_cumulative_pnl_taec11.png",
        ),
        (
            S4 / "external_taec_minus_fixed_mbb_intervals.png",
            "external_taec_minus_fixed_mbb_intervals.png",
        ),
        (
            S5 / "external_taec_cost_sensitivity.png",
            "external_taec_cost_sensitivity.png",
        ),
        (
            S5 / "external_taec_open_only_execution_sensitivity.png",
            "external_taec_open_only_execution_sensitivity.png",
        ),
    ]

    for src, name in figure_sources:
        if not src.exists():
            raise RuntimeError(
                f"Missing figure: {src}"
            )
        shutil.copy2(
            src,
            FIGURES / name,
        )

    # ------------------------------------------------------------------
    # Examiner-facing claims table.
    # ------------------------------------------------------------------
    key_inference = taec_fixed[
        [
            "model",
            "mbb_observed_total",
            "mbb_ci95_total_lower",
            "mbb_ci95_total_upper",
            "holm_p_two_sided",
            "holm_reject_5pct",
            "dependence_sensitive_5pct",
        ]
    ].copy()

    key_inference.to_csv(
        OUT / "key_taec_fixed_inference.csv",
        index=False,
    )

    main_profit = profit.loc[
        profit["strategy"]
        == "fixed_settlement"
    ].copy()

    main_profit.to_csv(
        OUT / "fixed_profitability_inference_context.csv",
        index=False,
    )

    convergence.to_csv(
        OUT / "precost_convergence_inference_context.csv",
        index=False,
    )

    sharpe_diff.to_csv(
        OUT / "sharpe_contrast_context.csv",
        index=False,
    )

    perturb.to_csv(
        OUT / "temperature_perturbation_context.csv",
        index=False,
    )

    checks = [
        {
            "check": "all_prior_stages_pass",
            "passed": True,
            "observed": "2,3,4,5 PASS",
            "expected": "PASS",
        },
        {
            "check": "main_claims_safe",
            "passed": bool(
                claims_df.loc[
                    claims_df["destination"]
                    .isin(
                        [
                            "MAIN_RESULTS",
                            "DISCUSSION",
                        ]
                    ),
                    "safe_use",
                ].all()
            ),
            "observed": "all",
            "expected": "True",
        },
        {
            "check": "do_not_use_primary_present",
            "passed": bool(
                (
                    claims_df["destination"]
                    == "DO_NOT_USE_AS_PRIMARY"
                ).sum()
                >= 3
            ),
            "observed": int(
                (
                    claims_df["destination"]
                    == "DO_NOT_USE_AS_PRIMARY"
                ).sum()
            ),
            "expected": ">=3",
        },
        {
            "check": "thesis_tables",
            "passed": len(
                list(TABLES.glob("*.tex"))
            ) >= 3,
            "observed": len(
                list(TABLES.glob("*.tex"))
            ),
            "expected": ">=3",
        },
        {
            "check": "thesis_figures",
            "passed": len(
                list(FIGURES.glob("*.png"))
            ) >= 5,
            "observed": len(
                list(FIGURES.glob("*.png"))
            ),
            "expected": ">=5",
        },
        {
            "check": "numbers_tex",
            "passed": (
                GENERATED / "numbers.tex"
            ).exists(),
            "observed": (
                GENERATED / "numbers.tex"
            ).exists(),
            "expected": True,
        },
        {
            "check": "external_diagnostics_do_not_reselect",
            "passed": (
                stage5[
                    "frozen_policy_guards"
                ][
                    "external_diagnostics_may_reselect"
                ]
                is False
            ),
            "observed": stage5[
                "frozen_policy_guards"
            ][
                "external_diagnostics_may_reselect"
            ],
            "expected": False,
        },
    ]

    checks_df = pd.DataFrame(checks)

    checks_df.to_csv(
        OUT / "stage6_integrity_checks.csv",
        index=False,
    )

    status = (
        "PASS"
        if checks_df["passed"].all()
        else "FAILED"
    )

    summary = {
        "status": status,
        "stage": 6,
        "stage_name": (
            "thesis_pruning_reproducibility_"
            "examiner_audit_and_final_release"
        ),
        "extension_status": (
            "FINAL_EXPLORATORY_TRADING_EXTENSION"
        ),
        "new_empirical_modelling_after_stage5": False,
        "external_data_used_for_reselection": False,
        "primary_fixed_policy_unchanged": True,
        "taec_policy_status": (
            "exploratory contrast; not a replacement policy"
        ),
        "external_common_support_dates": 61,
        "main_results_claims": int(
            (
                claims_df["destination"]
                == "MAIN_RESULTS"
            ).sum()
        ),
        "discussion_claims": int(
            (
                claims_df["destination"]
                == "DISCUSSION"
            ).sum()
        ),
        "appendix_claims": int(
            (
                claims_df["destination"]
                == "APPENDIX"
            ).sum()
        ),
        "do_not_use_as_primary": int(
            (
                claims_df["destination"]
                == "DO_NOT_USE_AS_PRIMARY"
            ).sum()
        ),
        "thesis_tables": [
            p.name
            for p in sorted(
                TABLES.glob("*.tex")
            )
        ],
        "thesis_figures": [
            p.name
            for p in sorted(
                FIGURES.glob("*.png")
            )
        ],
        "authoritative_numbers": (
            "outputs/trading_contrast_extension/"
            "thesis/generated/numbers.tex"
        ),
        "safe_headline": (
            "The conservative fixed policy dominates the exploratory "
            "multi-contract TAEC strategy externally; the aggressive "
            "strategy's small positive pre-cost convergence is overwhelmed "
            "by turnover costs and is not statistically resolved."
        ),
        "execution_caveat": (
            "TAEC uses market snapshot probabilities rather than "
            "historical executable bid/ask fills."
        ),
        "greek_caveat": (
            "Delta/Gamma are finite-difference forecast-risk sensitivities "
            "to temperature-location perturbations, not Black-Scholes Greeks."
        ),
        "status_note": (
            "No further empirical model, threshold or strategy is permitted "
            "after this closure."
        ),
    }

    (OUT / "stage6_summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if status != "PASS":
        raise RuntimeError(
            "Stage-6 thesis-value acceptance gate failed."
        )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
