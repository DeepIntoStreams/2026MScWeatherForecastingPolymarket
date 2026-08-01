from __future__ import annotations

import itertools
import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from phase9_core import (
    evaluate_strategy,
    evaluate_strategy_grouped,
    prepare_event_groups,
    expected_maximum_sharpe,
    moving_block_indices,
    ordinary_indices,
)
from phase9_core import (
    probability_of_sharpe,
    safe_ratio,
    sharpe_ratio,
    summarise_daily,
)

# Local percentile helper avoids a circular import dependency on report code.
def percentile_interval(values: np.ndarray, confidence: float) -> tuple[float, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return np.nan, np.nan
    alpha = 1.0 - confidence
    return float(np.quantile(finite, alpha / 2.0)), float(np.quantile(finite, 1.0 - alpha / 2.0))


def evaluate_registry(event, registry, dates, config):
    n_strategy = len(registry)
    n_dates = len(dates)
    pnl = np.zeros((n_strategy, n_dates), dtype=np.float32)
    positions = np.zeros((n_strategy, n_dates), dtype=np.int16)
    active = np.zeros((n_strategy, n_dates), dtype=np.int8)
    entry = np.zeros((n_strategy, n_dates), dtype=np.float32)
    rows = []
    cost = float(config["primary_cost"])
    alpha = float(config["tail_probability"])
    groups = prepare_event_groups(event)
    for i, row in registry.iterrows():
        result = evaluate_strategy_grouped(groups, dates, row, cost, config)
        pnl[i] = result.daily_pnl
        positions[i] = result.daily_positions
        active[i] = result.daily_active
        entry[i] = result.daily_entry_cash
        summary = summarise_daily(
            result.daily_pnl,
            result.daily_positions,
            result.daily_active,
            result.daily_entry_cash,
            alpha,
        )
        gross = float(result.daily_pnl.sum() + cost * result.daily_positions.sum())
        rows.append({
            **row.to_dict(),
            **summary,
            "gross_pnl_before_cost": gross,
            "break_even_cost_per_position": safe_ratio(gross, float(result.daily_positions.sum())),
        })
        if (i + 1) % 5000 == 0:
            print(f"Evaluated {i+1:,}/{n_strategy:,} strategies")
    return pnl, positions, active, entry, pd.DataFrame(rows)


def outer_folds(dates: list[str], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    v = config["validation"]
    initial = int(v["outer_initial_dates"])
    blocks = int(v["outer_blocks"])
    block = int(v["outer_block_dates"])
    expected = initial + blocks * block
    if expected != len(dates):
        raise ValueError(f"Outer design expects {expected} dates, found {len(dates)}")
    return [
        {
            "outer_fold": i + 1,
            "train_indices": np.arange(0, initial + i * block),
            "test_indices": np.arange(initial + i * block, initial + (i + 1) * block),
        }
        for i in range(blocks)
    ]


def inner_blocks(train_indices: np.ndarray, config: Mapping[str, Any]) -> list[np.ndarray]:
    n = len(train_indices)
    count = int(config["validation"]["inner_blocks"])
    minimum = int(config["validation"]["inner_min_block_dates"])
    block = max(minimum, int(math.floor(n * 0.15)))
    while count * block >= n and block > 2:
        block -= 1
    start = n - count * block
    return [train_indices[start + i * block : start + (i + 1) * block] for i in range(count)]


def vector_sharpe(matrix: np.ndarray, columns: np.ndarray) -> np.ndarray:
    subset = matrix[:, columns].astype(float)
    mean = subset.mean(axis=1)
    sd = subset.std(axis=1, ddof=1)
    return np.divide(
        mean,
        sd,
        out=np.where(mean > 0, np.inf, np.where(mean < 0, -np.inf, 0.0)),
        where=sd > 1e-15,
    )


def select_for_fold(pnl, positions, active, registry, train_indices, objective, config):
    blocks = inner_blocks(train_indices, config)
    validation_indices = np.concatenate(blocks)
    pooled_sr = vector_sharpe(pnl, validation_indices)
    pooled_mean = pnl[:, validation_indices].mean(axis=1)
    total_positions = positions[:, validation_indices].sum(axis=1)
    active_dates = active[:, validation_indices].sum(axis=1)
    block_srs = np.column_stack([vector_sharpe(pnl, block) for block in blocks])
    dispersion = np.nanstd(np.where(np.isfinite(block_srs), block_srs, np.nan), axis=1)
    positive_blocks = np.sum(
        np.column_stack([pnl[:, block].sum(axis=1) > 0 for block in blocks]),
        axis=1,
    )
    eligible = (
        (total_positions >= int(config["validation"]["minimum_inner_positions"]))
        & (active_dates >= int(config["validation"]["minimum_inner_active_dates"]))
        & (positive_blocks >= int(config["validation"]["minimum_positive_inner_blocks"]))
        & np.isfinite(pooled_sr)
    )
    if not eligible.any():
        eligible = (total_positions > 0) & (active_dates > 0) & np.isfinite(pooled_sr)
    if not eligible.any():
        raise RuntimeError("No eligible strategy in inner selection")
    complexity = registry["complexity_score"].to_numpy(float)
    if objective == "robust_sharpe":
        settings = config["selection_objectives"]["robust_sharpe"]
        score = (
            float(settings["pooled_sharpe_weight"]) * pooled_sr
            - float(settings["block_sharpe_dispersion_penalty"]) * np.nan_to_num(dispersion, nan=10.0)
            - float(settings["negative_mean_penalty"]) * np.maximum(-pooled_mean, 0.0)
            - 0.002 * complexity
        )
    elif objective == "pure_sharpe":
        score = pooled_sr - 0.001 * complexity
    elif objective == "mean_pnl":
        score = pooled_mean - 0.0001 * complexity
    else:
        raise ValueError(objective)
    score = np.where(eligible, score, -np.inf)
    selected = int(np.nanargmax(score))
    diagnostics = registry.copy()
    diagnostics["objective"] = objective
    diagnostics["pooled_inner_sharpe"] = pooled_sr
    diagnostics["pooled_inner_mean_pnl"] = pooled_mean
    diagnostics["inner_block_sharpe_sd"] = dispersion
    diagnostics["positive_inner_blocks"] = positive_blocks
    diagnostics["inner_positions"] = total_positions
    diagnostics["inner_active_dates"] = active_dates
    diagnostics["eligible"] = eligible
    diagnostics["selection_score"] = score
    diagnostics["selected"] = np.arange(len(registry)) == selected
    return selected, diagnostics


def nested_walkforward(pnl, positions, active, entry, registry, dates, config):
    folds = outer_folds(dates, config)
    daily_rows = []
    selection_rows = []
    summary_rows = []
    for objective in config["selection_objectives"]:
        aggregate_pnl = np.zeros(len(dates))
        aggregate_positions = np.zeros(len(dates))
        aggregate_active = np.zeros(len(dates))
        aggregate_entry = np.zeros(len(dates))
        tested = np.zeros(len(dates), dtype=bool)
        for fold in folds:
            selected, diagnostics = select_for_fold(
                pnl, positions, active, registry, fold["train_indices"], objective, config
            )
            diagnostics.insert(0, "outer_fold", fold["outer_fold"])
            selection_rows.append(diagnostics.sort_values("selection_score", ascending=False).head(500))
            test = fold["test_indices"]
            tested[test] = True
            aggregate_pnl[test] = pnl[selected, test]
            aggregate_positions[test] = positions[selected, test]
            aggregate_active[test] = active[selected, test]
            aggregate_entry[test] = entry[selected, test]
            strategy = registry.iloc[selected]
            for index in test:
                daily_rows.append({
                    "objective": objective,
                    "outer_fold": fold["outer_fold"],
                    "target_date": dates[index],
                    "strategy_id": strategy["strategy_id"],
                    "model": strategy["model"],
                    "decision_rule": strategy["decision_rule"],
                    "rule_filter": strategy["rule_filter"],
                    "side_mode": strategy["side_mode"],
                    "top_k": strategy["top_k"],
                    "sizing_rule": strategy["sizing_rule"],
                    "ranking_signal": strategy["ranking_signal"],
                    "edge_threshold": strategy["edge_threshold"],
                    "stability_filter": strategy["stability_filter"],
                    "execution_track": strategy["execution_track"],
                    "daily_net_pnl": pnl[selected, index],
                    "positions": positions[selected, index],
                    "active": active[selected, index],
                    "entry_cash": entry[selected, index],
                })
        indices = np.flatnonzero(tested)
        summary = summarise_daily(
            aggregate_pnl[indices],
            aggregate_positions[indices],
            aggregate_active[indices],
            aggregate_entry[indices],
            float(config["tail_probability"]),
        )
        summary_rows.append({
            "objective": objective,
            "outer_test_dates": len(indices),
            **summary,
            "positive_outer_blocks": int(sum(
                np.sum(aggregate_pnl[fold["test_indices"]]) > 0 for fold in folds
            )),
        })
    return pd.DataFrame(daily_rows), pd.concat(selection_rows, ignore_index=True), pd.DataFrame(summary_rows)


def bootstrap_series(values: np.ndarray, config: Mapping[str, Any], label: Mapping[str, Any]) -> pd.DataFrame:
    x = np.asarray(values, dtype=float)
    n = len(x)
    reps = int(config["bootstrap"]["replications"])
    confidence = float(config["bootstrap"]["confidence_level"])
    seed = int(config["bootstrap"]["seed"])
    methods = [("ordinary_date", None)] + [
        ("circular_moving_block", int(b))
        for b in config["bootstrap"]["moving_block_lengths"] if int(b) <= n
    ]
    rows = []
    for j, (method, block) in enumerate(methods):
        rng = np.random.default_rng(seed + 1000 * j)
        indices = ordinary_indices(n, reps, rng) if method == "ordinary_date" else moving_block_indices(n, int(block), reps, rng)
        samples = x[indices]
        totals = samples.sum(axis=1)
        sharpes = np.array([sharpe_ratio(row) for row in samples])
        lower, upper = percentile_interval(totals, confidence)
        sr_lower, sr_upper = percentile_interval(sharpes, confidence)
        rows.append({
            **dict(label),
            "method": method,
            "block_length": block,
            "point_total_pnl": float(x.sum()),
            "total_pnl_lower_95": lower,
            "total_pnl_upper_95": upper,
            "point_sharpe": sharpe_ratio(x),
            "sharpe_lower_95": sr_lower,
            "sharpe_upper_95": sr_upper,
            "positive_total_fraction": float(np.mean(totals > 0)),
            "positive_sharpe_fraction": float(np.mean(sharpes > 0)),
            "replications": reps,
        })
    return pd.DataFrame(rows)


def deflated_sharpe_table(full_results: pd.DataFrame, pnl: np.ndarray) -> pd.DataFrame:
    benchmark = expected_maximum_sharpe(full_results["sharpe"].to_numpy(float), len(full_results))
    top = full_results.replace([np.inf, -np.inf], np.nan).dropna(subset=["sharpe"]).sort_values("sharpe", ascending=False).head(100)
    rows = []
    for index, row in top.iterrows():
        series = pnl[index].astype(float)
        rows.append({
            "strategy_id": row["strategy_id"],
            "sharpe": row["sharpe"],
            "expected_maximum_sharpe_under_trials": benchmark,
            "deflated_sharpe_probability": probability_of_sharpe(series, benchmark),
            "probabilistic_sharpe_vs_zero": probability_of_sharpe(series, 0.0),
            "trials": len(full_results),
        })
    return pd.DataFrame(rows)


def pbo_cscv(pnl: np.ndarray, full_results: pd.DataFrame, config: Mapping[str, Any]):
    slices = int(config["multiple_testing"]["pbo_slices"])
    top_n = min(int(config["multiple_testing"]["pbo_top_strategies"]), len(full_results))
    top_indices = (
        full_results.replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["sharpe"])
        .sort_values("sharpe", ascending=False)
        .head(top_n)
        .index.to_numpy(int)
    )
    matrix = pnl[top_indices].astype(float)
    date_slices = np.array_split(np.arange(matrix.shape[1]), slices)
    half = slices // 2
    records = []
    logits = []
    for number, in_ids in enumerate(itertools.combinations(range(slices), half), start=1):
        out_ids = [i for i in range(slices) if i not in in_ids]
        in_idx = np.concatenate([date_slices[i] for i in in_ids])
        out_idx = np.concatenate([date_slices[i] for i in out_ids])
        in_sr = vector_sharpe(matrix, in_idx)
        winner = int(np.nanargmax(in_sr))
        out_sr = vector_sharpe(matrix, out_idx)
        finite = np.where(np.isfinite(out_sr), out_sr, -np.inf)
        rank = int(np.sum(finite <= finite[winner]))
        relative = np.clip(rank / max(len(finite), 1), 1e-6, 1 - 1e-6)
        logit_rank = float(np.log(relative / (1 - relative)))
        logits.append(logit_rank)
        records.append({
            "combination": number,
            "in_slices": "|".join(map(str, in_ids)),
            "out_slices": "|".join(map(str, out_ids)),
            "selected_strategy_id": full_results.loc[top_indices[winner], "strategy_id"],
            "in_sample_sharpe": in_sr[winner],
            "out_of_sample_sharpe": out_sr[winner],
            "out_of_sample_relative_rank": relative,
            "logit_rank": logit_rank,
            "overfit_indicator": logit_rank < 0,
        })
    return pd.DataFrame([{
        "pbo": float(np.mean(np.array(logits) < 0)),
        "combinations": len(records),
        "strategies_considered": len(top_indices),
        "slices": slices,
    }]), pd.DataFrame(records)


def reality_check(pnl: np.ndarray, full_results: pd.DataFrame, benchmark: np.ndarray, config: Mapping[str, Any]) -> pd.DataFrame:
    top_n = min(int(config["multiple_testing"]["reality_check_top_strategies"]), len(full_results))
    top = (
        full_results.replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["sharpe"])
        .sort_values("sharpe", ascending=False)
        .head(top_n)
    )
    indices = top.index.to_numpy(int)
    diff = pnl[indices].astype(float) - benchmark[None, :]
    observed_means = diff.mean(axis=1)
    observed_max = float(np.max(observed_means))
    centered = diff - observed_means[:, None]
    reps = int(config["bootstrap"]["reality_check_replications"])
    rng = np.random.default_rng(int(config["bootstrap"]["seed"]) + 98765)
    bootstrap_max = np.empty(reps)
    for r in range(reps):
        idx = moving_block_indices(centered.shape[1], 5, 1, rng)[0]
        bootstrap_max[r] = float(np.max(centered[:, idx].mean(axis=1)))
    p_value = float(np.mean(bootstrap_max >= observed_max))
    return pd.DataFrame([{
        "strategies_considered": len(indices),
        "benchmark": "phase7_frozen_strategy",
        "observed_max_mean_pnl_advantage": observed_max,
        "moving_block_length": 5,
        "bootstrap_replications": reps,
        "white_reality_check_p_value": p_value,
        "reject_no_superior_strategy_at_5pct": p_value < 0.05,
    }])


def load_benchmark(path, dates):
    if not path.is_file():
        return np.zeros(len(dates))
    frame = pd.read_csv(path)
    frame["target_date"] = pd.to_datetime(frame["target_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    column = "net_pnl" if "net_pnl" in frame.columns else "daily_net_pnl"
    if column not in frame.columns:
        return np.zeros(len(dates))
    values = frame.groupby("target_date")[column].sum()
    return np.array([float(values.get(date, 0.0)) for date in dates])


def choose_candidates(full_results, outer_summary, registry, pnl, positions, active, config):
    finite = full_results.replace([np.inf, -np.inf], np.nan).dropna(subset=["sharpe"])
    oracle = finite.sort_values(["sharpe", "total_net_pnl"], ascending=False).iloc[0]
    observed = finite.loc[finite["execution_track"] == "observed_yes_long_only"].sort_values(["sharpe", "total_net_pnl"], ascending=False).iloc[0]
    primary_objective = config["primary_selection_objective"]
    primary_outer = outer_summary.loc[outer_summary["objective"] == primary_objective].iloc[0]
    best_outer = outer_summary.sort_values(["sharpe", "total_net_pnl"], ascending=False).iloc[0]
    future_index, _ = select_for_fold(
        pnl, positions, active, registry, np.arange(pnl.shape[1]), primary_objective, config
    )
    future = full_results.loc[future_index]
    return pd.DataFrame([
        {
            "candidate_role": "full_sample_oracle_best_sharpe",
            "strategy_id": oracle["strategy_id"],
            "selection_status": "post_hoc_in_sample_only",
            "sharpe": oracle["sharpe"],
            "total_net_pnl": oracle["total_net_pnl"],
            "execution_track": oracle["execution_track"],
        },
        {
            "candidate_role": "best_observed_price_long_only",
            "strategy_id": observed["strategy_id"],
            "selection_status": "post_hoc_in_sample_only",
            "sharpe": observed["sharpe"],
            "total_net_pnl": observed["total_net_pnl"],
            "execution_track": observed["execution_track"],
        },
        {
            "candidate_role": "primary_nested_walkforward_selector",
            "strategy_id": "",
            "selection_status": "pre_registered_selector",
            "sharpe": primary_outer["sharpe"],
            "total_net_pnl": primary_outer["total_net_pnl"],
            "execution_track": "changes_by_outer_fold",
        },
        {
            "candidate_role": "best_post_hoc_outer_selector",
            "strategy_id": "",
            "selection_status": "post_hoc_selector_comparison",
            "sharpe": best_outer["sharpe"],
            "total_net_pnl": best_outer["total_net_pnl"],
            "execution_track": "changes_by_outer_fold",
        },
        {
            "candidate_role": "future_candidate_after_full_exploration",
            "strategy_id": future["strategy_id"],
            "selection_status": "requires_new_external_validation",
            "sharpe": future["sharpe"],
            "total_net_pnl": future["total_net_pnl"],
            "execution_track": future["execution_track"],
        },
    ])
