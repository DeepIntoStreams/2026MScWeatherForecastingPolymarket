from __future__ import annotations

import hashlib
import math
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from scipy import stats

MODEL_ORDER = ["raw", "static", "matern"]
RULE_ORDER = ["24h_prior", "12h_prior", "6h_prior", "event_day_open"]


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
            f"git {' '.join(args)} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
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
            "true": True, "1": True, "yes": True, "passed": True,
            "false": False, "0": False, "no": False, "failed": False,
        })
        .fillna(False)
        .astype(bool)
    )


def dependency_check(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing={path}"
    frame = pd.read_csv(path)
    if {"critical", "passed"}.issubset(frame.columns):
        failed = frame.loc[as_bool(frame["critical"]) & ~as_bool(frame["passed"])]
        return failed.empty, f"critical_failures={len(failed)}"
    if "passed" in frame.columns:
        return bool(as_bool(frame["passed"]).all()), f"rows={len(frame)}"
    return False, f"unsupported_schema={list(frame.columns)}"


def clip_probability(values: np.ndarray, epsilon: float) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), epsilon, 1.0 - epsilon)


def logit(values: np.ndarray, epsilon: float) -> np.ndarray:
    p = clip_probability(values, epsilon)
    return np.log(p / (1.0 - p))


def sharpe_ratio(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    if x.size < 2:
        return np.nan
    mean = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    if sd <= 1e-15:
        return np.inf if mean > 0 else (-np.inf if mean < 0 else 0.0)
    return mean / sd


def max_drawdown(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    if x.size == 0:
        return 0.0
    cumulative = np.cumsum(x)
    running_peak = np.maximum.accumulate(np.concatenate([[0.0], cumulative]))[1:]
    return float(abs(np.min(cumulative - running_peak)))


def expected_shortfall(values: np.ndarray, alpha: float = 0.05) -> float:
    x = np.asarray(values, dtype=float)
    if x.size == 0:
        return np.nan
    cutoff = float(np.quantile(x, alpha))
    tail = x[x <= cutoff]
    return float(np.mean(tail)) if tail.size else cutoff


def safe_ratio(a: float, b: float) -> float:
    if not np.isfinite(b) or abs(b) <= 1e-15:
        return np.nan
    return float(a / b)


def profit_factor(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    gains = float(x[x > 0].sum())
    losses = abs(float(x[x < 0].sum()))
    if losses <= 1e-15:
        return np.inf if gains > 0 else np.nan
    return gains / losses


def probability_of_sharpe(values: np.ndarray, benchmark_sharpe: float = 0.0) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return np.nan
    sr = sharpe_ratio(x)
    if not np.isfinite(sr):
        return 1.0 if sr > benchmark_sharpe else 0.0
    skewness = float(stats.skew(x, bias=False))
    kurtosis = float(stats.kurtosis(x, fisher=False, bias=False))
    denominator = 1.0 - skewness * sr + ((kurtosis - 1.0) / 4.0) * sr * sr
    if denominator <= 0:
        return np.nan
    z = (sr - benchmark_sharpe) * math.sqrt(n - 1) / math.sqrt(denominator)
    return float(stats.norm.cdf(z))


def expected_maximum_sharpe(sharpes: np.ndarray, trials: int) -> float:
    finite = np.asarray(sharpes, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size < 2 or trials <= 1:
        return 0.0
    sigma = float(np.std(finite, ddof=1))
    gamma = 0.5772156649015329
    n = max(int(trials), 2)
    return float(
        sigma * (
            (1.0 - gamma) * stats.norm.ppf(1.0 - 1.0 / n)
            + gamma * stats.norm.ppf(1.0 - 1.0 / (n * math.e))
        )
    )


def summarise_daily(
    pnl: np.ndarray,
    positions: np.ndarray | None = None,
    active: np.ndarray | None = None,
    entry_cash: np.ndarray | None = None,
    alpha: float = 0.05,
) -> dict[str, float]:
    x = np.asarray(pnl, dtype=float)
    pos = np.asarray(positions if positions is not None else np.zeros_like(x), dtype=float)
    act = np.asarray(active if active is not None else (pos > 0), dtype=float)
    cash = np.asarray(entry_cash if entry_cash is not None else np.zeros_like(x), dtype=float)
    sr = sharpe_ratio(x)
    return {
        "dates": int(len(x)),
        "total_net_pnl": float(x.sum()),
        "mean_daily_net_pnl": float(x.mean()),
        "daily_pnl_sd": float(np.std(x, ddof=1)) if len(x) > 1 else np.nan,
        "sharpe": sr,
        "opportunity_annualised_sharpe": sr * math.sqrt(365.0) if np.isfinite(sr) else sr,
        "probabilistic_sharpe_vs_zero": probability_of_sharpe(x, 0.0),
        "maximum_drawdown": max_drawdown(x),
        "expected_shortfall_5pct": expected_shortfall(x, alpha),
        "positive_date_fraction": float(np.mean(x > 0.0)),
        "active_dates": int(np.sum(act > 0)),
        "position_count": int(np.sum(pos)),
        "mean_positions_per_active_date": safe_ratio(float(np.sum(pos)), float(np.sum(act > 0))),
        "total_entry_cash": float(np.sum(cash)),
        "return_on_entry_cash": safe_ratio(float(x.sum()), float(np.sum(cash))),
        "profit_factor_date_level": profit_factor(x),
    }


def read_phase6_panel(path: Path) -> pd.DataFrame:
    panel = pd.read_csv(path, compression="gzip", low_memory=False)
    required = {
        "target_date", "decision_rule", "split", "event_order", "model",
        "probability_raw", "probability_normalised", "outcome",
    }
    missing = sorted(required - set(panel.columns))
    if missing:
        raise ValueError(f"Phase 6 panel missing {missing}")
    panel["target_date"] = pd.to_datetime(panel["target_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in [
        "probability_raw", "probability_normalised", "outcome", "event_order",
        "event_lower_bound_c", "event_upper_bound_c",
    ]:
        if column in panel.columns:
            panel[column] = pd.to_numeric(panel[column], errors="coerce")
    return panel


def build_event_panel(panel: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    stable = ["target_date", "decision_rule", "split", "event_order"]
    counts = panel.groupby(stable + ["model"], dropna=False).size()
    if (counts != 1).any():
        raise ValueError(f"Non-unique event-model keys={int((counts != 1).sum())}")
    pivot = panel.pivot(
        index=stable,
        columns="model",
        values=["probability_raw", "probability_normalised"],
    )
    pivot.columns = [f"{a}_{b}" for a, b in pivot.columns]
    pivot = pivot.reset_index()

    metadata_columns = [
        c for c in ["event_label", "event_lower_bound_c", "event_upper_bound_c", "outcome"]
        if c in panel.columns
    ]
    rows: list[dict[str, Any]] = []
    for key, group in panel.groupby(stable, sort=False, dropna=False):
        row = dict(zip(stable, key))
        for column in metadata_columns:
            values = group[column].dropna()
            if column == "event_label":
                labels = values.astype(str)
                human = labels[
                    labels.str.contains(r"\s", regex=True, na=False)
                    & ~labels.str.fullmatch(r"0x[0-9a-fA-F]{32,}", na=False)
                ]
                row[column] = human.iloc[0] if len(human) else (labels.iloc[0] if len(labels) else np.nan)
                continue
            unique = pd.unique(values)
            if len(unique) > 1:
                numeric = pd.to_numeric(pd.Series(unique), errors="coerce")
                if numeric.notna().all() and float(numeric.max() - numeric.min()) <= tolerance:
                    row[column] = float(numeric.iloc[0])
                else:
                    raise ValueError(f"Inconsistent metadata {column} on {row}: {list(unique)}")
            elif len(unique) == 1:
                row[column] = unique[0]
            else:
                row[column] = np.nan
        rows.append(row)
    metadata = pd.DataFrame(rows)
    result = pivot.merge(metadata, on=stable, how="left", validate="one_to_one")
    required_probabilities = [
        "probability_raw_market", "probability_normalised_market",
        "probability_normalised_raw", "probability_normalised_static",
        "probability_normalised_matern",
    ]
    missing = [c for c in required_probabilities if c not in result.columns]
    if missing:
        raise ValueError(f"Missing pivoted probabilities {missing}")
    for column in required_probabilities:
        if not np.isfinite(result[column].to_numpy(dtype=float)).all():
            raise ValueError(f"Non-finite values in {column}")
    return result.sort_values(stable).reset_index(drop=True)


def add_cross_rule_features(event: pd.DataFrame) -> pd.DataFrame:
    key = ["target_date", "event_order"]
    features: pd.DataFrame | None = None
    for model in MODEL_ORDER:
        temp = event[key + ["decision_rule", f"probability_normalised_{model}", "probability_raw_market"]].copy()
        temp["edge"] = temp[f"probability_normalised_{model}"] - temp["probability_raw_market"]
        wide = temp.pivot_table(index=key, columns="decision_rule", values="edge", aggfunc="first")
        wide.columns = [f"{model}_edge_{c}" for c in wide.columns]
        wide = wide.reset_index()
        features = wide if features is None else features.merge(wide, on=key, how="outer", validate="one_to_one")
    assert features is not None
    return event.merge(features, on=key, how="left", validate="many_to_one")


def load_stability(path: Path, event: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = event.copy()
    for shock in [0.10, 0.25]:
        result[f"matern_robust_{shock:.2f}c"] = False
        result[f"matern_min_abs_edge_{shock:.2f}c"] = np.nan
    if not path.is_file():
        return result, pd.DataFrame([{
            "check": "shifted_event_panel_available", "passed": False,
            "critical": False, "detail": f"missing={path}",
        }])
    shifted = pd.read_csv(path, compression="gzip", low_memory=False)
    required = {"target_date", "decision_rule", "event_order", "mean_shift_c"}
    if not required.issubset(shifted.columns):
        return result, pd.DataFrame([{
            "check": "shifted_event_panel_schema", "passed": False,
            "critical": False, "detail": f"columns={list(shifted.columns)}",
        }])
    shifted["target_date"] = pd.to_datetime(shifted["target_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if "shifted_signal_gap" not in shifted.columns:
        if {"shifted_matern_probability", "market_probability_raw"}.issubset(shifted.columns):
            shifted["shifted_signal_gap"] = shifted["shifted_matern_probability"] - shifted["market_probability_raw"]
        else:
            return result, pd.DataFrame([{
                "check": "shifted_event_panel_signal", "passed": False,
                "critical": False, "detail": "signal columns unavailable",
            }])
    join_key = ["target_date", "decision_rule", "event_order"]
    base = result[join_key + ["probability_normalised_matern", "probability_raw_market"]].copy()
    base["base_edge"] = base["probability_normalised_matern"] - base["probability_raw_market"]
    for shock in [0.10, 0.25]:
        subset = shifted.loc[
            shifted["mean_shift_c"].round(6).isin([round(-shock, 6), round(shock, 6)])
        ].copy()
        if subset.empty:
            continue
        grouped = subset.groupby(join_key)["shifted_signal_gap"].agg(list).reset_index().merge(
            base[join_key + ["base_edge"]], on=join_key, how="left"
        )
        grouped["robust"] = grouped.apply(
            lambda r: len(r["shifted_signal_gap"]) >= 2
            and all(np.sign(v) == np.sign(r["base_edge"]) for v in r["shifted_signal_gap"]),
            axis=1,
        )
        grouped["min_abs"] = grouped["shifted_signal_gap"].apply(
            lambda v: float(np.min(np.abs(v))) if len(v) else np.nan
        )
        result = result.merge(
            grouped[join_key + ["robust", "min_abs"]].rename(columns={
                "robust": f"matern_robust_{shock:.2f}c",
                "min_abs": f"matern_min_abs_edge_{shock:.2f}c",
            }),
            on=join_key,
            how="left",
            suffixes=("", "_new"),
        )
        for name in [f"matern_robust_{shock:.2f}c", f"matern_min_abs_edge_{shock:.2f}c"]:
            if f"{name}_new" in result.columns:
                result[name] = result[f"{name}_new"].combine_first(result[name])
                result = result.drop(columns=f"{name}_new")
        result[f"matern_robust_{shock:.2f}c"] = result[f"matern_robust_{shock:.2f}c"].fillna(False).astype(bool)
    return result, pd.DataFrame([{
        "check": "shifted_event_panel_available", "passed": True,
        "critical": False, "detail": f"rows={len(shifted)}",
    }])


def strategy_registry(config: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    sid = 0
    for model in config["models"]:
        stability_options = config["stability_filters"] if model == "matern" else ["none"]
        for rule_filter in config["rule_filters"]:
            for side_mode in config["side_modes"]:
                for top_k in config["selection_counts"]:
                    for sizing in config["sizing_rules"]:
                        for ranking in config["ranking_signals"]:
                            for threshold in config["probability_edge_thresholds"]:
                                for stability in stability_options:
                                    sid += 1
                                    rows.append({
                                        "strategy_id": f"S{sid:06d}",
                                        "model": model,
                                        "decision_rule": rule_filter["decision_rule"],
                                        "rule_filter": rule_filter["filter"],
                                        "side_mode": side_mode,
                                        "top_k": int(top_k),
                                        "sizing_rule": sizing,
                                        "ranking_signal": ranking,
                                        "edge_threshold": float(threshold),
                                        "stability_filter": stability,
                                        "execution_track": (
                                            "observed_yes_long_only"
                                            if side_mode == "long_only"
                                            else "includes_synthetic_short_yes"
                                        ),
                                        "complexity_score": (
                                            int(top_k > 1)
                                            + int(sizing not in {"one_share", "equal_budget"})
                                            + int(ranking != "edge")
                                            + int(rule_filter["filter"] != "none")
                                            + int(stability != "none")
                                            + int(side_mode == "long_short")
                                        ),
                                    })
    return pd.DataFrame(rows)


@dataclass
class StrategyEvaluation:
    daily_pnl: np.ndarray
    daily_positions: np.ndarray
    daily_active: np.ndarray
    daily_entry_cash: np.ndarray
    trade_records: list[dict[str, Any]]


def candidate_side(q: np.ndarray, p: np.ndarray, side_mode: str) -> tuple[np.ndarray, np.ndarray]:
    raw_edge = q - p
    if side_mode == "long_only":
        return np.ones(len(q), dtype=int), raw_edge
    if side_mode == "short_only":
        return -np.ones(len(q), dtype=int), -raw_edge
    if side_mode == "long_short":
        side = np.where(raw_edge >= 0.0, 1, -1)
        return side, np.abs(raw_edge)
    raise ValueError(side_mode)


def filter_mask(frame: pd.DataFrame, model: str, side: np.ndarray, rule_filter: str) -> np.ndarray:
    if rule_filter == "none":
        return np.ones(len(frame), dtype=bool)
    current = frame[f"probability_normalised_{model}"].to_numpy(float) - frame["probability_raw_market"].to_numpy(float)
    if rule_filter == "confirm_6h":
        prior = frame[f"{model}_edge_6h_prior"].to_numpy(float)
        return np.isfinite(prior) & (np.sign(prior) == side) & (np.sign(current) == side)
    if rule_filter == "confirm_12h":
        prior = frame[f"{model}_edge_12h_prior"].to_numpy(float)
        return np.isfinite(prior) & (np.sign(prior) == side) & (np.sign(current) == side)
    if rule_filter == "widening_from_24h":
        prior = frame[f"{model}_edge_24h_prior"].to_numpy(float)
        return np.isfinite(prior) & (np.sign(prior) == side) & (np.sign(current) == side) & (np.abs(current) > np.abs(prior))
    raise ValueError(rule_filter)


def stability_mask(frame: pd.DataFrame, strategy: Mapping[str, Any], threshold: float) -> np.ndarray:
    stability = strategy["stability_filter"]
    if stability == "none":
        return np.ones(len(frame), dtype=bool)
    if strategy["model"] != "matern":
        return np.zeros(len(frame), dtype=bool)
    shock = 0.10 if stability == "robust_0.10c" else 0.25
    robust = frame[f"matern_robust_{shock:.2f}c"].to_numpy(bool)
    minimum = frame[f"matern_min_abs_edge_{shock:.2f}c"].to_numpy(float)
    return robust & np.isfinite(minimum) & (minimum >= threshold)


def ranking_values(q: np.ndarray, p: np.ndarray, side: np.ndarray, edge: np.ndarray, ranking: str, epsilon: float) -> np.ndarray:
    if ranking == "edge":
        return edge
    if ranking == "roi":
        denominator = np.where(side > 0, p, 1.0 - p)
        return edge / np.maximum(denominator, epsilon)
    if ranking == "logit_gap":
        return np.abs(logit(q, epsilon) - logit(p, epsilon))
    raise ValueError(ranking)


def position_weights(q: np.ndarray, p: np.ndarray, side: np.ndarray, edge: np.ndarray, sizing: str, config: Mapping[str, Any]) -> np.ndarray:
    n = len(edge)
    if n == 0:
        return np.array([], dtype=float)
    if sizing == "one_share":
        return np.ones(n)
    if sizing == "equal_budget":
        return np.repeat(1.0 / n, n)
    if sizing == "edge_weighted":
        total = float(edge.sum())
        return edge / total if total > 0 else np.repeat(1.0 / n, n)
    if sizing == "quarter_kelly":
        long_kelly = edge / np.maximum(1.0 - p, 1e-8)
        short_kelly = edge / np.maximum(p, 1e-8)
        weights = np.where(side > 0, long_kelly, short_kelly) * 0.25
        single_cap = float(config["position_caps"]["quarter_kelly_single_position_cap"])
        weights = np.minimum(np.maximum(weights, 0.0), single_cap)
        gross_cap = float(config["position_caps"]["quarter_kelly_daily_gross_cap"])
        gross = float(weights.sum())
        if gross > gross_cap:
            weights *= gross_cap / gross
        return weights
    raise ValueError(sizing)


def evaluate_strategy(
    event: pd.DataFrame,
    dates: list[str],
    strategy: Mapping[str, Any],
    cost: float,
    config: Mapping[str, Any],
    keep_trades: bool = False,
) -> StrategyEvaluation:
    frame = event.loc[event["decision_rule"] == strategy["decision_rule"]]
    date_pos = {date: i for i, date in enumerate(dates)}
    pnl = np.zeros(len(dates))
    positions = np.zeros(len(dates), dtype=int)
    active = np.zeros(len(dates), dtype=int)
    entry_cash = np.zeros(len(dates))
    records: list[dict[str, Any]] = []
    model = str(strategy["model"])
    threshold = float(strategy["edge_threshold"])
    epsilon = float(config["probability_clip"])

    for date, group in frame.groupby("target_date", sort=False):
        if date not in date_pos:
            continue
        q = group[f"probability_normalised_{model}"].to_numpy(float)
        p = group["probability_raw_market"].to_numpy(float)
        y = group["outcome"].to_numpy(float)
        side, edge = candidate_side(q, p, str(strategy["side_mode"]))
        mask = edge >= threshold
        mask &= filter_mask(group, model, side, str(strategy["rule_filter"]))
        mask &= stability_mask(group, strategy, threshold)
        candidate = np.flatnonzero(mask)
        if candidate.size == 0:
            continue
        ranking = ranking_values(
            q[candidate], p[candidate], side[candidate], edge[candidate],
            str(strategy["ranking_signal"]), epsilon,
        )
        order = candidate[np.argsort(-ranking, kind="mergesort")]
        selected = order[: min(int(strategy["top_k"]), len(order))]
        weights = position_weights(
            q[selected], p[selected], side[selected], edge[selected],
            str(strategy["sizing_rule"]), config,
        )
        if len(weights) == 0 or np.all(weights <= 0):
            continue
        unit_pnl = np.where(
            side[selected] > 0,
            y[selected] - p[selected] - cost,
            p[selected] - y[selected] - cost,
        )
        weighted = weights * unit_pnl
        entry = weights * np.where(
            side[selected] > 0,
            p[selected] + cost,
            1.0 - p[selected] + cost,
        )
        i = date_pos[date]
        pnl[i] = float(weighted.sum())
        positions[i] = len(selected)
        active[i] = 1
        entry_cash[i] = float(entry.sum())
        if keep_trades:
            selected_group = group.iloc[selected]
            ranks = ranking_values(
                q[selected], p[selected], side[selected], edge[selected],
                str(strategy["ranking_signal"]), epsilon,
            )
            for j, (_, row) in enumerate(selected_group.iterrows()):
                records.append({
                    "target_date": date,
                    "split": row["split"],
                    "strategy_id": strategy["strategy_id"],
                    "decision_rule": strategy["decision_rule"],
                    "model": model,
                    "side": "long_yes" if side[selected][j] > 0 else "synthetic_short_yes",
                    "event_order": row["event_order"],
                    "event_label": row.get("event_label", ""),
                    "model_probability": q[selected][j],
                    "market_yes_price": p[selected][j],
                    "probability_edge": edge[selected][j],
                    "ranking_value": ranks[j],
                    "weight": weights[j],
                    "outcome": y[selected][j],
                    "unit_net_pnl": unit_pnl[j],
                    "weighted_net_pnl": weighted[j],
                    "entry_cash": entry[j],
                    "execution_track": strategy["execution_track"],
                })
    return StrategyEvaluation(pnl, positions, active, entry_cash, records)


def ordinary_indices(n: int, replications: int, rng: np.random.Generator) -> np.ndarray:
    return rng.integers(0, n, size=(replications, n))


def moving_block_indices(
    n: int,
    block_length: int,
    replications: int,
    rng: np.random.Generator,
) -> np.ndarray:
    blocks = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(replications, blocks))
    offsets = np.arange(block_length)
    return ((starts[:, :, None] + offsets) % n).reshape(replications, -1)[:, :n]


def prepare_event_groups(event: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    groups: dict[str, dict[str, pd.DataFrame]] = {}
    for rule, rule_frame in event.groupby("decision_rule", sort=False):
        groups[str(rule)] = {
            str(date): group.reset_index(drop=True)
            for date, group in rule_frame.groupby("target_date", sort=False)
        }
    return groups


def evaluate_strategy_grouped(
    groups: dict[str, dict[str, pd.DataFrame]],
    dates: list[str],
    strategy: Mapping[str, Any],
    cost: float,
    config: Mapping[str, Any],
) -> StrategyEvaluation:
    rule_groups = groups.get(str(strategy["decision_rule"]), {})
    pnl = np.zeros(len(dates))
    positions = np.zeros(len(dates), dtype=int)
    active = np.zeros(len(dates), dtype=int)
    entry_cash = np.zeros(len(dates))
    model = str(strategy["model"])
    threshold = float(strategy["edge_threshold"])
    epsilon = float(config["probability_clip"])
    for i, date in enumerate(dates):
        group = rule_groups.get(date)
        if group is None:
            continue
        q = group[f"probability_normalised_{model}"].to_numpy(float)
        p = group["probability_raw_market"].to_numpy(float)
        y = group["outcome"].to_numpy(float)
        side, edge = candidate_side(q, p, str(strategy["side_mode"]))
        mask = edge >= threshold
        mask &= filter_mask(group, model, side, str(strategy["rule_filter"]))
        mask &= stability_mask(group, strategy, threshold)
        candidate = np.flatnonzero(mask)
        if candidate.size == 0:
            continue
        ranking = ranking_values(
            q[candidate], p[candidate], side[candidate], edge[candidate],
            str(strategy["ranking_signal"]), epsilon,
        )
        selected = candidate[np.argsort(-ranking, kind="mergesort")]
        selected = selected[: min(int(strategy["top_k"]), len(selected))]
        weights = position_weights(
            q[selected], p[selected], side[selected], edge[selected],
            str(strategy["sizing_rule"]), config,
        )
        if len(weights) == 0 or np.all(weights <= 0):
            continue
        unit_pnl = np.where(
            side[selected] > 0,
            y[selected] - p[selected] - cost,
            p[selected] - y[selected] - cost,
        )
        weighted = weights * unit_pnl
        entry = weights * np.where(
            side[selected] > 0,
            p[selected] + cost,
            1.0 - p[selected] + cost,
        )
        pnl[i] = float(weighted.sum())
        positions[i] = len(selected)
        active[i] = 1
        entry_cash[i] = float(entry.sum())
    return StrategyEvaluation(pnl, positions, active, entry_cash, [])
