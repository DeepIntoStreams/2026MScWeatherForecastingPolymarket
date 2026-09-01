from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

from src.trading_contrast_extension import stage2 as s2
from src.trading_contrast_extension import rbf_provenance_repair as rbf_repair


OUT = Path("outputs/trading_contrast_extension/stage2")


def rebuild_from_corrected_panel() -> None:
    panel = pd.read_csv(
        OUT / "canonical_four_model_event_panel.csv.gz"
    )

    diff = (
        panel["p_rbf"].astype(float)
        - panel["p_static"].astype(float)
    ).abs()

    if not (diff > 1e-12).any():
        raise RuntimeError(
            "Corrected Stage-2 rebuild refuses an RBF book "
            "that is identical to Static."
        )

    mass_rows = []

    for model in s2.MODELS:
        mass = (
            panel.groupby(
                ["event_date", "decision_rule"]
            )[f"p_{model}"]
            .sum()
        )

        if not np.isclose(
            mass,
            1.0,
            atol=5e-6,
        ).all():
            raise RuntimeError(
                f"{model}: probability mass failure."
            )

        for (date, rule), value in mass.items():
            mass_rows.append(
                {
                    "event_date": date,
                    "decision_rule": rule,
                    "model": model,
                    "probability_mass": float(value),
                }
            )

    pd.DataFrame(
        mass_rows
    ).to_csv(
        OUT / "model_probability_book_checks.csv",
        index=False,
    )

    fixed_positions, fixed_daily = (
        s2.build_fixed_ledgers(panel)
    )

    reproduction = (
        s2.baseline_reproduction(fixed_daily)
    )

    checkpoints = (
        s2.build_market_checkpoints(panel)
    )

    taec_positions, taec_daily = (
        s2.build_taec_ledgers(
            panel,
            checkpoints,
        )
    )

    fixed_positions.to_csv(
        OUT / "fixed_strategy_position_ledger.csv",
        index=False,
    )

    fixed_daily.to_csv(
        OUT / "fixed_strategy_daily_ledger.csv",
        index=False,
    )

    reproduction.to_csv(
        OUT / "fixed_baseline_reproduction.csv",
        index=False,
    )

    taec_positions.to_csv(
        OUT / "taec11_position_ledger.csv.gz",
        index=False,
        compression={
            "method": "gzip",
            "mtime": 0,
        },
    )

    taec_daily.to_csv(
        OUT / "taec11_daily_ledger.csv",
        index=False,
    )

    fixed_summary = (
        fixed_daily.groupby(
            ["empirical_period", "model"],
            as_index=False,
        )
        .agg(
            dates=("event_date", "nunique"),
            active_dates=("active", "sum"),
            positions=("positions", "sum"),
            total_net_pnl=("net_pnl", "sum"),
            total_entry_capital=("entry_capital", "sum"),
        )
    )

    taec_summary = (
        taec_daily.groupby(
            ["empirical_period", "model"],
            as_index=False,
        )
        .agg(
            dates=("event_date", "nunique"),
            active_dates=("active", "sum"),
            positions=("positions", "sum"),
            yes_positions=("yes_positions", "sum"),
            no_positions=("no_positions", "sum"),
            total_net_pnl=("net_pnl", "sum"),
            total_entry_capital=("entry_capital", "sum"),
            mean_gap_closed_fraction=(
                "mean_gap_closed_fraction",
                "mean",
            ),
            target_hit_positions=(
                "target_hit_positions",
                "sum",
            ),
            forced_open_positions=(
                "forced_open_positions",
                "sum",
            ),
        )
    )

    fixed_summary.to_csv(
        OUT / "fixed_strategy_stage2_summary.csv",
        index=False,
    )

    taec_summary.to_csv(
        OUT / "taec11_stage2_summary.csv",
        index=False,
    )

    summary_path = OUT / "stage2_summary.json"
    summary = json.loads(
        summary_path.read_text()
    )

    summary["fixed_summary"] = (
        fixed_summary.to_dict(
            orient="records"
        )
    )

    summary["taec_summary"] = (
        taec_summary.to_dict(
            orient="records"
        )
    )

    summary["baseline_reproduction"] = (
        reproduction.to_dict(
            orient="records"
        )
    )

    summary["rbf_provenance_status"] = (
        "EXPLICIT_FROZEN_RBF_REPAIRED_AND_DISTINCT"
    )

    summary[
        "rbf_static_max_abs_probability_difference"
    ] = float(diff.max())

    summary[
        "rbf_static_rows_different_gt_1e_12"
    ] = int((diff > 1e-12).sum())

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n"
    )


def main() -> None:
    # Stage 2's original builder is deliberately followed by the explicit
    # frozen-RBF provenance repair discovered during Stage-2 certification.
    # All downstream ledgers are then rebuilt from the corrected canonical panel.
    s2.main()
    rbf_repair.main()
    rebuild_from_corrected_panel()

    print(
        "PASS: Stage 2 reproduced with explicit frozen RBF provenance."
    )


if __name__ == "__main__":
    main()
