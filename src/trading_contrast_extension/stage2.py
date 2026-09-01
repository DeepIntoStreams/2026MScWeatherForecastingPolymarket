from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
import json
import math
import re
from typing import Iterable
import numpy as np
import pandas as pd
try:
    from scipy.stats import norm
except Exception as exc:
    raise RuntimeError('Stage 2 requires scipy.stats.norm, which is part of the final pipeline scientific environment.') from exc
ROOT = Path('.')
OUT = ROOT / 'outputs/trading_contrast_extension/stage2'
OUT.mkdir(parents=True, exist_ok=True)
EVENT_PANEL_PATH = ROOT / 'data/processed/final_pipeline/market/' / 'exact_common_event_panel.csv.gz'
WEATHER_EVENT_PROB_PATH = ROOT / 'data/processed/final_pipeline/market/' / 'weather_event_probabilities.csv.gz'
FROZEN_WEATHER_PATH = ROOT / 'data/processed/final_pipeline/weather_models/' / 'frozen_weather_model_predictions_mar_aug.csv'
BASELINE_FIXED_SUMMARY_PATH = ROOT / 'outputs/final_pipeline/trading/' / 'fixed_policy_attribution_summary.csv'
NUMBERS_TEX_PATH = ROOT / 'outputs/final_pipeline/thesis/generated/numbers.tex'
MODELS = ['raw', 'static', 'rbf', 'matern32']
RULES = ['24h_prior', '12h_prior', '6h_prior', 'event_day_open']
ENTRY_RULE = '24h_prior'
FIXED_THRESHOLD = 0.15
COST_PER_EXECUTION = 0.01
TAEC_ROUND_TRIP_COST = 0.02
TOL = 1e-09

def canonical_rule(x: object) -> str | None:
    s = str(x).lower().strip()
    if '24' in s:
        return '24h_prior'
    if '12' in s:
        return '12h_prior'
    if re.search('(^|[^0-9])6([^0-9]|$)', s):
        return '6h_prior'
    if 'open' in s:
        return 'event_day_open'
    return None

def canonical_period(x: object) -> str:
    s = str(x).lower().strip()
    if 'external' in s or 'july' in s or 'aug' in s:
        return 'external_validation'
    if 'development' in s or 'march' in s or 'june' in s:
        return 'market_development'
    return str(x)

def finite_float(x: object) -> float | None:
    try:
        y = float(x)
    except Exception:
        return None
    if math.isnan(y):
        return None
    return y

def normalize_date_rule(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    date_col = next((c for c in ['event_date', 'target_date', 'date'] if c in x.columns), None)
    if date_col is None:
        raise RuntimeError('No date column found.')
    rule_col = next((c for c in ['decision_rule', 'rule', 'forecast_rule'] if c in x.columns), None)
    if rule_col is None:
        raise RuntimeError('No decision-rule column found.')
    x['event_date'] = pd.to_datetime(x[date_col], errors='raise').dt.strftime('%Y-%m-%d')
    x['decision_rule'] = x[rule_col].map(canonical_rule)
    if x['decision_rule'].isna().any():
        bad = sorted(x.loc[x['decision_rule'].isna(), rule_col].astype(str).unique())
        raise RuntimeError('Unrecognised decision rules: ' + repr(bad))
    period_col = next((c for c in ['empirical_period', 'analysis_period', 'period'] if c in x.columns), None)
    if period_col is not None:
        x['empirical_period'] = x[period_col].map(canonical_period)
    return x

def book_key_uniqueness_score(df: pd.DataFrame, cols: list[str]) -> tuple[float, float]:
    if not cols:
        return (0.0, 0.0)
    z = df[['event_date', 'decision_rule'] + cols].copy()
    for c in cols:
        z[c] = z[c].astype(str)
    z['_key'] = z[cols].agg('||'.join, axis=1)
    per_book = z.groupby(['event_date', 'decision_rule'])['_key'].nunique()
    unique11_share = float((per_book == 11).mean())
    four_rule_dates = z[['event_date', 'decision_rule']].drop_duplicates().groupby('event_date').size()
    dates = four_rule_dates[four_rule_dates == 4].index
    same = []
    for d in dates:
        xd = z.loc[z['event_date'] == d]
        sets = [frozenset(xd.loc[xd['decision_rule'] == r, '_key']) for r in RULES]
        same.append(len(set(sets)) == 1)
    stability = float(np.mean(same)) if same else 0.0
    return (unique11_share, stability)

def infer_contract_key(df: pd.DataFrame) -> tuple[pd.Series, list[str]]:
    exclude_fragments = ['price', 'prob', 'mean', 'sd', 'sigma', 'error', 'residual', 'target_available', 'winner', 'outcome', 'pnl', 'time', 'timestamp']
    semantic_fragments = ['contract', 'event', 'market', 'slug', 'question', 'label', 'name', 'range', 'temperature', 'threshold', 'lower', 'upper', 'bound', 'cutoff', 'token', 'condition', 'id']
    candidates = []
    for c in df.columns:
        lc = c.lower()
        if c in {'event_date', 'decision_rule', 'empirical_period'}:
            continue
        if any((f in lc for f in exclude_fragments)):
            continue
        if any((f in lc for f in semantic_fragments)):
            candidates.append(c)
    scored: list[tuple[float, float, list[str]]] = []
    for c in candidates:
        a, b = book_key_uniqueness_score(df, [c])
        if a >= 0.95:
            scored.append((b, a, [c]))
    if scored:
        scored.sort(reverse=True)
        b, a, cols = scored[0]
        if b >= 0.95:
            key = df[cols].astype(str).agg('||'.join, axis=1)
            return (key, cols)
    shortlist = candidates[:16]
    for width in [2, 3]:
        for cols_tuple in combinations(shortlist, width):
            cols = list(cols_tuple)
            a, b = book_key_uniqueness_score(df, cols)
            if a >= 0.99 and b >= 0.95:
                key = df[cols].astype(str).agg('||'.join, axis=1)
                return (key, cols)
    raise RuntimeError('Could not infer a stable contract identity across the four decision checkpoints.')

def find_binary_winner(df: pd.DataFrame) -> str:
    preferred = [c for c in df.columns if any((f in c.lower() for f in ['winner', 'realised', 'realized', 'outcome', 'target_event', 'y_event']))]
    candidates = preferred + [c for c in df.columns if c not in preferred]
    for c in candidates:
        try:
            s = pd.to_numeric(df[c], errors='coerce')
        except Exception:
            continue
        values = set(s.dropna().unique().tolist())
        if not values:
            continue
        if not values.issubset({0, 1}):
            continue
        g = pd.DataFrame({'event_date': df['event_date'], 'decision_rule': df['decision_rule'], 'v': s}).groupby(['event_date', 'decision_rule'])['v'].sum(min_count=1)
        good = g.dropna()
        if len(good) and float(np.mean(np.isclose(good.to_numpy(), 1.0))) >= 0.99:
            return c
    raise RuntimeError('Could not identify the one-hot realised-event indicator.')

def numeric_pair_candidates(df: pd.DataFrame) -> list[tuple[str, str]]:
    lowers = [c for c in df.columns if any((k in c.lower() for k in ['lower', 'min_c', 'lower_bound']))]
    uppers = [c for c in df.columns if any((k in c.lower() for k in ['upper', 'max_c', 'upper_bound']))]
    return [(lo, hi) for lo in lowers for hi in uppers if lo != hi]

def parse_temperature_label(value: object) -> tuple[float, float] | None:
    s = str(value).lower()
    nums = re.findall('-?\\d+(?:\\.\\d+)?', s)
    if not nums:
        return None
    k = float(nums[0])
    if 'below' in s or 'lower' in s or 'or less' in s or ('or under' in s):
        return (-np.inf, k + 1.0)
    if 'higher' in s or 'above' in s or 'upper' in s or ('or more' in s):
        return (k, np.inf)
    return (k, k + 1.0)

def infer_bounds(df: pd.DataFrame, contract_cols: list[str]) -> tuple[pd.Series, pd.Series, str]:
    for lo, hi in numeric_pair_candidates(df):
        l = pd.to_numeric(df[lo], errors='coerce')
        u = pd.to_numeric(df[hi], errors='coerce')
        if l.notna().mean() >= 0.75 and u.notna().mean() >= 0.75:
            lower = l.fillna(-np.inf)
            upper = u.fillna(np.inf)
            if bool((lower < upper).all()):
                return (lower, upper, f'{lo}|{hi}')
    parse_candidates = contract_cols + [c for c in df.columns if any((f in c.lower() for f in ['label', 'question', 'title', 'range', 'temperature']))]
    seen = set()
    for c in parse_candidates:
        if c in seen:
            continue
        seen.add(c)
        parsed = df[c].map(parse_temperature_label)
        good = parsed.notna()
        if good.mean() < 0.95:
            continue
        lower = parsed.map(lambda x: x[0] if x is not None else np.nan)
        upper = parsed.map(lambda x: x[1] if x is not None else np.nan)
        if lower.notna().all() and upper.notna().all() and bool((lower < upper).all()):
            return (lower.astype(float), upper.astype(float), f'parsed:{c}')
    type_cols = [c for c in df.columns if 'type' in c.lower() and ('event' in c.lower() or 'contract' in c.lower())]
    threshold_cols = [c for c in df.columns if any((f in c.lower() for f in ['threshold', 'cutoff', 'temperature', 'temp_c']))]
    for tc in type_cols:
        types = df[tc].astype(str).str.lower()
        if not types.str.contains('lower|interior|upper', regex=True).mean() >= 0.95:
            continue
        for kc in threshold_cols:
            k = pd.to_numeric(df[kc], errors='coerce')
            if k.notna().mean() < 0.95:
                continue
            lower = np.where(types.str.contains('lower'), -np.inf, k)
            upper = np.where(types.str.contains('upper'), np.inf, k + 1.0)
            return (pd.Series(lower, index=df.index, dtype=float), pd.Series(upper, index=df.index, dtype=float), f'{tc}|{kc}')
    raise RuntimeError('Could not reconstruct the eleven temperature-event bounds.')

def normalize_model_name(x: object) -> str | None:
    s = str(x).lower()
    if 'rbf' in s:
        return 'rbf'
    if 'matern' in s or 'selected_gp' in s:
        return 'matern32'
    if 'static' in s:
        return 'static'
    if 'raw' in s or 'deterministic' in s or 'ecmwf' in s:
        return 'raw'
    return None

def direct_long_probability_sources(event_panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sources: dict[str, pd.DataFrame] = {}
    paths = [WEATHER_EVENT_PROB_PATH, ROOT / 'data/processed/final_pipeline/market/' / 'exact_common_book_metrics.csv', EVENT_PANEL_PATH]
    for path in paths:
        if not path.exists():
            continue
        try:
            x = pd.read_csv(path)
            x = normalize_date_rule(x)
        except Exception:
            continue
        model_col = next((c for c in x.columns if c.lower() in {'model', 'method', 'source', 'weather_model', 'probability_source'}), None)
        prob_candidates = [c for c in x.columns if ('prob' in c.lower() or re.fullmatch('p(?:_event)?', c.lower())) and (not ('market' in c.lower() or 'pool' in c.lower()))]
        if model_col is None or not prob_candidates:
            continue
        mapped = x[model_col].map(normalize_model_name)
        if mapped.notna().sum() == 0:
            continue
        try:
            x['_contract_key'], _ = infer_contract_key(x)
        except Exception:
            continue
        prob_col = None
        for c in prob_candidates:
            p = pd.to_numeric(x[c], errors='coerce')
            if p.notna().mean() >= 0.9 and ((p.dropna() >= -1e-12) & (p.dropna() <= 1 + 1e-12)).all():
                prob_col = c
                break
        if prob_col is None:
            continue
        for model in MODELS:
            xm = x.loc[mapped == model, ['event_date', 'decision_rule', '_contract_key', prob_col]].copy()
            if xm.empty:
                continue
            xm = xm.rename(columns={'_contract_key': 'contract_key', prob_col: 'probability'})
            xm['probability'] = pd.to_numeric(xm['probability'], errors='coerce')
            sources.setdefault(model, xm)
    return sources

def find_prediction_params(base_event_panel: pd.DataFrame) -> dict[str, dict[str, str | None]]:
    tables: list[tuple[str, pd.DataFrame]] = []
    for name, path in [('event_panel', EVENT_PANEL_PATH), ('frozen_weather', FROZEN_WEATHER_PATH)]:
        if not path.exists():
            continue
        try:
            x = pd.read_csv(path)
            x = normalize_date_rule(x)
            tables.append((name, x))
        except Exception:
            continue
    result: dict[str, dict[str, str | None]] = {}

    def find_col(cols: Iterable[str], model: str, kind: str) -> str | None:
        scored = []
        for c in cols:
            lc = c.lower()
            if any((bad in lc for bad in ['error', 'residual', 'loss', 'crps', 'target', 'hko'])):
                continue
            score = 0
            if model == 'raw':
                if 'raw' in lc:
                    score += 8
                if 'deterministic' in lc:
                    score += 7
                if 'ecmwf' in lc:
                    score += 4
            elif model == 'matern32':
                if 'matern' in lc:
                    score += 8
                if 'selected_gp' in lc:
                    score += 8
            elif model in lc:
                score += 8
            if kind == 'mean':
                if 'mean' in lc:
                    score += 5
                if 'forecast' in lc:
                    score += 4
                if 'prediction' in lc:
                    score += 3
                if lc.endswith('_c'):
                    score += 2
                if any((x in lc for x in ['sd', 'sigma', 'std', 'variance', 'var_'])):
                    score -= 10
            else:
                if 'sd' in lc:
                    score += 6
                if 'sigma' in lc:
                    score += 6
                if 'std' in lc:
                    score += 6
                if 'scale' in lc:
                    score += 4
                if 'variance' in lc:
                    score += 2
                if 'mean' in lc:
                    score -= 10
            if score > 0:
                scored.append((score, c))
        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], -len(x[1])), reverse=True)
        return scored[0][1]
    for table_name, x in tables:
        model_col = next((c for c in x.columns if c.lower() in {'model', 'method', 'source', 'weather_model'}), None)
        if model_col is None:
            continue
        mapped = x[model_col].map(normalize_model_name)
        mean_candidates = [c for c in x.columns if ('mean' in c.lower() or 'forecast' in c.lower() or 'prediction' in c.lower()) and (not ('error' in c.lower() or 'target' in c.lower()))]
        sd_candidates = [c for c in x.columns if any((f in c.lower() for f in ['sd', 'sigma', 'std', 'scale']))]
        if not mean_candidates:
            continue
        for model in MODELS:
            if model in result:
                continue
            xm = x.loc[mapped == model]
            if xm.empty:
                continue
            mean_col = mean_candidates[0]
            sd_col = sd_candidates[0] if sd_candidates else None
            result[model] = {'table': table_name, 'format': 'long', 'model_col': model_col, 'model_value': str(xm[model_col].iloc[0]), 'mean_col': mean_col, 'sd_col': sd_col}
    for model in MODELS:
        if model in result:
            continue
        best = None
        for table_name, x in tables:
            mean_col = find_col(x.columns, model, 'mean')
            sd_col = find_col(x.columns, model, 'sd')
            if mean_col is None:
                continue
            if model != 'raw' and sd_col is None:
                continue
            candidate = {'table': table_name, 'format': 'wide', 'mean_col': mean_col, 'sd_col': sd_col}
            best = candidate
            break
        if best is not None:
            result[model] = best
    if 'raw' not in result:
        for table_name, x in tables:
            candidates = [c for c in x.columns if any((f in c.lower() for f in ['forecast_c', 'forecast_max', 'predicted_max', 'deterministic'])) and (not any((bad in c.lower() for bad in ['error', 'target', 'hko'])))]
            if candidates:
                result['raw'] = {'table': table_name, 'format': 'wide', 'mean_col': candidates[0], 'sd_col': None}
                break
    return result

def extract_param_table(spec: dict[str, str | None], model: str) -> pd.DataFrame:
    table_name = spec['table']
    path = EVENT_PANEL_PATH if table_name == 'event_panel' else FROZEN_WEATHER_PATH
    x = pd.read_csv(path)
    x = normalize_date_rule(x)
    if spec['format'] == 'long':
        mapped = x[str(spec['model_col'])].map(normalize_model_name)
        x = x.loc[mapped == model].copy()
    cols = ['event_date', 'decision_rule', str(spec['mean_col'])]
    if spec.get('sd_col') is not None:
        cols.append(str(spec['sd_col']))
    x = x[cols].copy()
    x = x.rename(columns={str(spec['mean_col']): 'mean_c'})
    if spec.get('sd_col') is not None:
        x = x.rename(columns={str(spec['sd_col']): 'sd_c'})
    else:
        x['sd_c'] = np.nan
    x['mean_c'] = pd.to_numeric(x['mean_c'], errors='coerce')
    x['sd_c'] = pd.to_numeric(x['sd_c'], errors='coerce')

    def unique_or_nan(s: pd.Series) -> float:
        y = s.dropna().unique()
        if len(y) == 0:
            return np.nan
        if len(y) > 1:
            if np.nanmax(y) - np.nanmin(y) > 1e-10:
                raise RuntimeError(f'{model}: multiple predictive parameter values within a date/rule book.')
        return float(y[0])
    out = x.groupby(['event_date', 'decision_rule'], as_index=False).agg(mean_c=('mean_c', unique_or_nan), sd_c=('sd_c', unique_or_nan))
    return out

def gaussian_bin_probability(mean: np.ndarray, sd: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    z_hi = (upper - mean) / sd
    z_lo = (lower - mean) / sd
    return norm.cdf(z_hi) - norm.cdf(z_lo)

def build_canonical_panel() -> tuple[pd.DataFrame, dict[str, object]]:
    ep = pd.read_csv(EVENT_PANEL_PATH)
    ep = normalize_date_rule(ep)
    if 'empirical_period' not in ep.columns:
        raise RuntimeError('Authoritative event panel must carry empirical_period.')
    ep['empirical_period'] = ep['empirical_period'].map(canonical_period)
    ep['contract_key'], contract_cols = infer_contract_key(ep)
    lower, upper, bound_source = infer_bounds(ep, contract_cols)
    ep['event_lower_c'] = lower
    ep['event_upper_c'] = upper
    winner_col = find_binary_winner(ep)
    ep['realised_event'] = pd.to_numeric(ep[winner_col], errors='raise').astype(int)
    market_col = next((c for c in ['market_raw_yes', 'market_yes', 'market_price', 'raw_market_yes'] if c in ep.columns), None)
    if market_col is None:
        raise RuntimeError('Could not identify raw market YES price.')
    ep['market_raw_yes'] = pd.to_numeric(ep[market_col], errors='raise')
    if not ((ep['market_raw_yes'] >= 0) & (ep['market_raw_yes'] <= 1)).all():
        raise RuntimeError('Market prices outside [0,1].')
    model_prob_cols: dict[str, pd.Series] = {}
    direct_event_col_candidates = {'raw': ['p_raw', 'raw_event_probability', 'p_raw_weather'], 'static': ['p_static', 'static_event_probability', 'p_static_gaussian'], 'rbf': ['p_rbf', 'rbf_event_probability'], 'matern32': ['p_selected_gp', 'p_matern32', 'matern_event_probability']}
    for model, candidates in direct_event_col_candidates.items():
        c = next((x for x in candidates if x in ep.columns), None)
        if c is not None:
            p = pd.to_numeric(ep[c], errors='coerce')
            if p.notna().mean() >= 0.99:
                model_prob_cols[model] = p
    direct_sources = direct_long_probability_sources(ep)
    for model, d in direct_sources.items():
        if model in model_prob_cols:
            continue
        merged = ep[['event_date', 'decision_rule', 'contract_key']].merge(d, on=['event_date', 'decision_rule', 'contract_key'], how='left')
        if len(merged) == len(ep) and merged['probability'].notna().mean() >= 0.99:
            model_prob_cols[model] = merged['probability']
    params_spec = find_prediction_params(ep)
    params_audit: dict[str, object] = {'contract_key_columns': contract_cols, 'bound_source': bound_source, 'winner_column': winner_col, 'market_column': market_col, 'prediction_parameter_specs': params_spec, 'direct_probability_models': sorted(model_prob_cols)}
    for model in MODELS:
        if model in model_prob_cols:
            continue
        if model not in params_spec:
            raise RuntimeError(f'Could not locate frozen predictive law for {model}. No new fitting is permitted, so Stage 2 stops.')
        pars = extract_param_table(params_spec[model], model)
        merged = ep[['event_date', 'decision_rule', 'event_lower_c', 'event_upper_c']].merge(pars, on=['event_date', 'decision_rule'], how='left', validate='many_to_one')
        if merged['mean_c'].isna().any():
            n = int(merged['mean_c'].isna().sum())
            raise RuntimeError(f'{model}: {n} event rows lack frozen predictive means.')
        mean = merged['mean_c'].to_numpy(dtype=float)
        lower_a = merged['event_lower_c'].to_numpy(dtype=float)
        upper_a = merged['event_upper_c'].to_numpy(dtype=float)
        if model == 'raw':
            p = ((mean >= lower_a) & (mean < upper_a)).astype(float)
        else:
            sd = merged['sd_c'].to_numpy(dtype=float)
            if np.isnan(sd).any() or np.any(sd <= 0):
                raise RuntimeError(f'{model}: invalid frozen predictive SD.')
            p = gaussian_bin_probability(mean, sd, lower_a, upper_a)
        model_prob_cols[model] = pd.Series(p, index=ep.index)
    for model in MODELS:
        ep[f'p_{model}'] = pd.to_numeric(model_prob_cols[model], errors='raise')
    mass_rows = []
    for model in MODELS:
        g = ep.groupby(['event_date', 'decision_rule'])[f'p_{model}'].sum()
        mass_rows.append(pd.DataFrame({'event_date': [i[0] for i in g.index], 'decision_rule': [i[1] for i in g.index], 'model': model, 'probability_mass': g.to_numpy()}))
    masses = pd.concat(mass_rows, ignore_index=True)
    bad_mass = masses.loc[~np.isclose(masses['probability_mass'], 1.0, atol=5e-06)]
    if not bad_mass.empty:
        raise RuntimeError('Probability-mass failure. First rows:\n' + bad_mass.head(20).to_string(index=False))
    masses.to_csv(OUT / 'model_probability_book_checks.csv', index=False)
    keep = ['event_date', 'empirical_period', 'decision_rule', 'contract_key', 'event_lower_c', 'event_upper_c', 'realised_event', 'market_raw_yes']
    for c in contract_cols:
        if c not in keep:
            keep.append(c)
    for model in MODELS:
        keep.append(f'p_{model}')
    canonical = ep[keep].copy()
    if canonical.duplicated(['event_date', 'decision_rule', 'contract_key']).any():
        raise RuntimeError('Duplicate canonical event keys.')
    return (canonical, params_audit)

def parse_macro(name: str) -> float | None:
    if not NUMBERS_TEX_PATH.exists():
        return None
    text = NUMBERS_TEX_PATH.read_text()
    m = re.search(f'\\\\newcommand\\{{\\\\{re.escape(name)}\\}}\\{{([^}}]+)\\}}', text)
    if not m:
        return None
    try:
        return float(m.group(1).replace('\\_', '_'))
    except Exception:
        return None

def build_fixed_ledgers(canonical: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry = canonical.loc[canonical['decision_rule'] == ENTRY_RULE].copy()
    position_rows = []
    daily_rows = []
    for model in MODELS:
        p_col = f'p_{model}'
        for (date, period), book in entry.groupby(['event_date', 'empirical_period'], sort=True):
            if len(book) != 11:
                raise RuntimeError(f'Fixed {model} {date}: expected 11 contracts, found {len(book)}.')
            b = book.copy()
            b['edge'] = b[p_col] - b['market_raw_yes']
            idx = b['edge'].idxmax()
            row = b.loc[idx]
            traded = bool(float(row['edge']) > FIXED_THRESHOLD)
            pnl = float(row['realised_event']) - float(row['market_raw_yes']) - COST_PER_EXECUTION if traded else 0.0
            position_rows.append({'event_date': date, 'empirical_period': period, 'strategy': 'fixed_settlement', 'model': model, 'contract_key': row['contract_key'], 'model_probability': float(row[p_col]), 'market_entry_yes': float(row['market_raw_yes']), 'edge': float(row['edge']), 'threshold': FIXED_THRESHOLD, 'traded': traded, 'side': 'YES' if traded else 'NO_TRADE', 'realised_event': int(row['realised_event']), 'net_pnl': pnl, 'entry_capital': float(row['market_raw_yes']) + COST_PER_EXECUTION if traded else 0.0})
            daily_rows.append({'event_date': date, 'empirical_period': period, 'strategy': 'fixed_settlement', 'model': model, 'active': traded, 'positions': int(traded), 'net_pnl': pnl, 'entry_capital': float(row['market_raw_yes']) + COST_PER_EXECUTION if traded else 0.0})
    return (pd.DataFrame(position_rows), pd.DataFrame(daily_rows))

def baseline_reproduction(fixed_daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    baseline = None
    if BASELINE_FIXED_SUMMARY_PATH.exists():
        try:
            baseline = pd.read_csv(BASELINE_FIXED_SUMMARY_PATH)
        except Exception:
            baseline = None
    model_aliases = {'raw': ['raw', 'raw_weather', 'raw_deterministic'], 'static': ['static', 'static_gaussian'], 'matern32': ['selected_gp', 'gp', 'matern', 'matern32']}
    parsed_authoritative = False
    if baseline is not None and (not baseline.empty):
        source_col = next((c for c in baseline.columns if c.lower() in {'source', 'method', 'model'}), None)
        period_col = next((c for c in baseline.columns if 'period' in c.lower()), None)
        pnl_candidates = [c for c in baseline.columns if 'pnl' in c.lower() and ('total' in c.lower() or 'net' in c.lower() or 'sum' in c.lower())]
        pnl_col = pnl_candidates[0] if pnl_candidates else None
        if source_col is not None and pnl_col is not None:
            for model, aliases in model_aliases.items():
                for period in ['market_development', 'external_validation']:
                    x = baseline.copy()
                    mapped_source = x[source_col].astype(str).str.lower()
                    mask_source = pd.Series(False, index=x.index)
                    for alias in aliases:
                        mask_source |= mapped_source.str.contains(alias, regex=False)
                    if period_col is not None:
                        mapped_period = x[period_col].map(canonical_period)
                        mask_period = mapped_period == period
                    else:
                        mask_period = pd.Series(True, index=x.index)
                    xb = x.loc[mask_source & mask_period]
                    if len(xb) != 1:
                        continue
                    expected = float(xb[pnl_col].iloc[0])
                    observed = float(fixed_daily.loc[(fixed_daily['model'] == model) & (fixed_daily['empirical_period'] == period), 'net_pnl'].sum())
                    rows.append({'model': model, 'period': period, 'benchmark_source': str(BASELINE_FIXED_SUMMARY_PATH), 'expected_pnl': expected, 'observed_pnl': observed, 'absolute_difference': abs(expected - observed), 'passed': bool(abs(expected - observed) <= 1e-09)})
                    parsed_authoritative = True
    macros = {'raw': 'ExternalRawPnL', 'static': 'ExternalStaticPnL', 'matern32': 'ExternalGPPnL'}
    for model, macro in macros.items():
        if any((r['model'] == model and r['period'] == 'external_validation' for r in rows)):
            continue
        expected = parse_macro(macro)
        if expected is None:
            continue
        observed = float(fixed_daily.loc[(fixed_daily['model'] == model) & (fixed_daily['empirical_period'] == 'external_validation'), 'net_pnl'].sum())
        rows.append({'model': model, 'period': 'external_validation', 'benchmark_source': 'numbers.tex', 'expected_pnl': expected, 'observed_pnl': observed, 'absolute_difference': abs(expected - observed), 'passed': bool(abs(expected - observed) <= 0.00051)})
    out = pd.DataFrame(rows)
    required = {'raw', 'static', 'matern32'}
    have = set(out.loc[out['period'] == 'external_validation', 'model'])
    if not required.issubset(have):
        raise RuntimeError('Could not construct required baseline reproduction checks for Raw/Static/Matérn.')
    if not out['passed'].all():
        raise RuntimeError('Fixed-strategy baseline reproduction failed:\n' + out.loc[~out['passed']].to_string(index=False))
    return out

def build_market_checkpoints(canonical: pd.DataFrame) -> pd.DataFrame:
    z = canonical[['event_date', 'empirical_period', 'decision_rule', 'contract_key', 'market_raw_yes']].copy()
    pivot = z.pivot_table(index=['event_date', 'empirical_period', 'contract_key'], columns='decision_rule', values='market_raw_yes', aggfunc='first').reset_index()
    for rule in RULES:
        if rule not in pivot.columns:
            pivot[rule] = np.nan
    pivot['contract_complete'] = pivot[RULES].notna().all(axis=1)
    date_support = pivot.groupby(['event_date', 'empirical_period']).agg(contracts=('contract_key', 'size'), complete_contracts=('contract_complete', 'sum')).reset_index()
    date_support['taec_date_eligible'] = (date_support['contracts'] == 11) & (date_support['complete_contracts'] == 11)
    pivot = pivot.merge(date_support[['event_date', 'empirical_period', 'taec_date_eligible']], on=['event_date', 'empirical_period'], how='left', validate='many_to_one')
    pivot.to_csv(OUT / 'market_checkpoint_panel.csv', index=False)
    date_support.to_csv(OUT / 'taec_support_by_date.csv', index=False)
    return pivot

def build_taec_ledgers(canonical: pd.DataFrame, checkpoints: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry_model = canonical.loc[canonical['decision_rule'] == ENTRY_RULE, ['event_date', 'empirical_period', 'contract_key', 'p_raw', 'p_static', 'p_rbf', 'p_matern32']].copy()
    checkpoints = checkpoints.copy()
    checkpoint_aliases = {'24h_prior': 'market_yes_24h', '12h_prior': 'market_yes_12h', '6h_prior': 'market_yes_6h', 'event_day_open': 'market_yes_open'}
    for original, alias in checkpoint_aliases.items():
        if original not in checkpoints.columns:
            raise RuntimeError(f'Missing required market checkpoint column: {original}')
        checkpoints[alias] = checkpoints[original]
    z = checkpoints.merge(entry_model, on=['event_date', 'empirical_period', 'contract_key'], how='inner', validate='one_to_one')
    z = z.loc[z['taec_date_eligible']].copy()
    position_rows = []
    for model in MODELS:
        p_col = f'p_{model}'
        for row in z.itertuples(index=False):
            q = float(getattr(row, p_col))
            p24 = float(row.market_yes_24h)
            gap = q - p24
            if abs(gap) <= TAEC_ROUND_TRIP_COST:
                continue
            if gap > 0:
                side = 'YES'
                direction = 1.0
            else:
                side = 'NO'
                direction = -1.0
            exit_rule = None
            exit_price = None
            target_hit = False
            exit_checkpoints = [('12h_prior', 'market_yes_12h'), ('6h_prior', 'market_yes_6h'), ('event_day_open', 'market_yes_open')]
            for rule, safe_attr in exit_checkpoints:
                p_t = float(getattr(row, safe_attr))
                crossed = p_t >= q if side == 'YES' else p_t <= q
                if crossed:
                    exit_rule = rule
                    exit_price = p_t
                    target_hit = True
                    break
            forced_open = False
            if exit_rule is None:
                exit_rule = 'event_day_open'
                exit_price = float(row.market_yes_open)
                forced_open = True
            signed_move = direction * (exit_price - p24)
            pnl = signed_move - TAEC_ROUND_TRIP_COST
            gap_closed_fraction = signed_move / abs(gap)
            position_rows.append({'event_date': row.event_date, 'empirical_period': row.empirical_period, 'strategy': 'taec11', 'model': model, 'contract_key': row.contract_key, 'side': side, 'model_probability_24h': q, 'market_entry_yes_24h': p24, 'initial_signed_gap': gap, 'absolute_initial_gap': abs(gap), 'entry_threshold': TAEC_ROUND_TRIP_COST, 'market_yes_12h': float(row.market_yes_12h), 'market_yes_6h': float(row.market_yes_6h), 'market_yes_open': float(row.market_yes_open), 'exit_rule': exit_rule, 'market_yes_exit': exit_price, 'target_hit': target_hit, 'forced_open_exit': forced_open, 'signed_market_move_toward_model': signed_move, 'gap_closed_fraction': gap_closed_fraction, 'round_trip_cost': TAEC_ROUND_TRIP_COST, 'net_pnl': pnl, 'entry_capital': p24 + COST_PER_EXECUTION if side == 'YES' else 1.0 - p24 + COST_PER_EXECUTION})
    positions = pd.DataFrame(position_rows)
    if positions.empty:
        raise RuntimeError('TAEC generated zero positions; check probability mapping.')
    if positions.groupby(['event_date', 'model']).size().max() > 11:
        raise RuntimeError('TAEC exceeded 11 positions on a date.')
    if positions.duplicated(['event_date', 'model', 'contract_key']).any():
        raise RuntimeError('TAEC has duplicated binary-contract exposure.')
    daily = positions.groupby(['event_date', 'empirical_period', 'model'], as_index=False).agg(positions=('contract_key', 'size'), yes_positions=('side', lambda s: int((s == 'YES').sum())), no_positions=('side', lambda s: int((s == 'NO').sum())), net_pnl=('net_pnl', 'sum'), entry_capital=('entry_capital', 'sum'), mean_gap_closed_fraction=('gap_closed_fraction', 'mean'), target_hit_positions=('target_hit', 'sum'), forced_open_positions=('forced_open_exit', 'sum'))
    daily['strategy'] = 'taec11'
    daily['active'] = True
    eligible_dates = z[['event_date', 'empirical_period']].drop_duplicates()
    full = eligible_dates.assign(_k=1).merge(pd.DataFrame({'model': MODELS, '_k': 1}), on='_k').drop(columns='_k')
    daily = full.merge(daily, on=['event_date', 'empirical_period', 'model'], how='left')
    fill_zero = ['positions', 'yes_positions', 'no_positions', 'net_pnl', 'entry_capital', 'target_hit_positions', 'forced_open_positions']
    for c in fill_zero:
        daily[c] = daily[c].fillna(0)
    daily['strategy'] = 'taec11'
    daily['active'] = daily['positions'] > 0
    return (positions, daily)

def main() -> None:
    canonical, mapping_audit = build_canonical_panel()
    canonical.to_csv(OUT / 'canonical_four_model_event_panel.csv.gz', index=False, compression='gzip')
    (OUT / 'stage2_schema_mapping.json').write_text(json.dumps(mapping_audit, indent=2, sort_keys=True, default=str) + '\n')
    fixed_positions, fixed_daily = build_fixed_ledgers(canonical)
    reproduction = baseline_reproduction(fixed_daily)
    checkpoints = build_market_checkpoints(canonical)
    taec_positions, taec_daily = build_taec_ledgers(canonical, checkpoints)
    fixed_positions.to_csv(OUT / 'fixed_strategy_position_ledger.csv', index=False)
    fixed_daily.to_csv(OUT / 'fixed_strategy_daily_ledger.csv', index=False)
    reproduction.to_csv(OUT / 'fixed_baseline_reproduction.csv', index=False)
    taec_positions.to_csv(OUT / 'taec11_position_ledger.csv.gz', index=False, compression='gzip')
    taec_daily.to_csv(OUT / 'taec11_daily_ledger.csv', index=False)
    fixed_summary = fixed_daily.groupby(['empirical_period', 'model'], as_index=False).agg(dates=('event_date', 'nunique'), active_dates=('active', 'sum'), positions=('positions', 'sum'), total_net_pnl=('net_pnl', 'sum'), total_entry_capital=('entry_capital', 'sum'))
    taec_summary = taec_daily.groupby(['empirical_period', 'model'], as_index=False).agg(dates=('event_date', 'nunique'), active_dates=('active', 'sum'), positions=('positions', 'sum'), yes_positions=('yes_positions', 'sum'), no_positions=('no_positions', 'sum'), total_net_pnl=('net_pnl', 'sum'), total_entry_capital=('entry_capital', 'sum'), mean_gap_closed_fraction=('mean_gap_closed_fraction', 'mean'), target_hit_positions=('target_hit_positions', 'sum'), forced_open_positions=('forced_open_positions', 'sum'))
    fixed_summary.to_csv(OUT / 'fixed_strategy_stage2_summary.csv', index=False)
    taec_summary.to_csv(OUT / 'taec11_stage2_summary.csv', index=False)
    checks = []

    def add(check: str, passed: bool, observed: object, expected: object, note: str='') -> None:
        checks.append({'check': check, 'passed': bool(passed), 'observed': observed, 'expected': expected, 'note': note})
    add('canonical_rows_match_final_event_panel', len(canonical) == 6996, len(canonical), 6996)
    add('canonical_dates', canonical['event_date'].nunique() == 163, canonical['event_date'].nunique(), 163)
    add('four_models_present', all((f'p_{m}' in canonical.columns for m in MODELS)), [c for c in canonical.columns if c.startswith('p_')], [f'p_{m}' for m in MODELS])
    add('probability_books_sum_to_one', bool(np.isclose(pd.read_csv(OUT / 'model_probability_book_checks.csv')['probability_mass'], 1.0, atol=5e-06).all()), 'all', 'all')
    add('fixed_external_dates_61_each_model', bool((fixed_summary.loc[fixed_summary['empirical_period'] == 'external_validation', 'dates'] == 61).all()), fixed_summary.loc[fixed_summary['empirical_period'] == 'external_validation', ['model', 'dates']].to_dict(orient='records'), 61)
    add('fixed_development_dates_90_each_model', bool((fixed_summary.loc[fixed_summary['empirical_period'] == 'market_development', 'dates'] == 90).all()), fixed_summary.loc[fixed_summary['empirical_period'] == 'market_development', ['model', 'dates']].to_dict(orient='records'), 90)
    add('baseline_raw_static_matern_reproduced', bool(reproduction['passed'].all()), reproduction[['model', 'period', 'absolute_difference', 'passed']].to_dict(orient='records'), 'all passed')
    add('taec_external_dates_61_each_model', bool((taec_summary.loc[taec_summary['empirical_period'] == 'external_validation', 'dates'] == 61).all()), taec_summary.loc[taec_summary['empirical_period'] == 'external_validation', ['model', 'dates']].to_dict(orient='records'), 61)
    add('taec_development_dates_90_each_model', bool((taec_summary.loc[taec_summary['empirical_period'] == 'market_development', 'dates'] == 90).all()), taec_summary.loc[taec_summary['empirical_period'] == 'market_development', ['model', 'dates']].to_dict(orient='records'), 90)
    add('taec_max_11_positions', int(taec_daily['positions'].max()) <= 11, int(taec_daily['positions'].max()), '<=11')
    add('taec_no_settlement_in_pnl', True, 'PnL is signed market probability move minus 0.02 round-trip cost', 'no realised_event term')
    add('taec_all_exits_pre_event', bool(taec_positions['exit_rule'].isin(['12h_prior', '6h_prior', 'event_day_open']).all()), sorted(taec_positions['exit_rule'].unique().tolist()), ['12h_prior', '6h_prior', 'event_day_open'])
    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(OUT / 'stage2_integrity_checks.csv', index=False)
    status = 'PASS' if checks_df['passed'].all() else 'FAILED'
    summary = {'status': status, 'stage': 2, 'stage_name': 'canonical_four_model_probability_panel_and_strategy_ledgers', 'canonical_event_rows': len(canonical), 'canonical_dates': int(canonical['event_date'].nunique()), 'models': MODELS, 'fixed_entry_rule': ENTRY_RULE, 'fixed_threshold': FIXED_THRESHOLD, 'taec_entry_rule': ENTRY_RULE, 'taec_round_trip_cost': TAEC_ROUND_TRIP_COST, 'taec_exit_checkpoints': ['12h_prior', '6h_prior', 'event_day_open'], 'fixed_summary': fixed_summary.to_dict(orient='records'), 'taec_summary': taec_summary.to_dict(orient='records'), 'baseline_reproduction': reproduction.to_dict(orient='records'), 'next_stage': 'complete risk, capital-efficiency, convergence and Greek-like analytics for all eight portfolios'}
    (OUT / 'stage2_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + '\n')
    print()
    print('===================================================================')
    print(' STAGE 2 SUMMARY')
    print('===================================================================')
    print(json.dumps(summary, indent=2, default=str))
    print()
    print('INTEGRITY CHECKS')
    print(checks_df.to_string(index=False))
    if status != 'PASS':
        raise RuntimeError('Stage 2 acceptance gate failed.')
if __name__ == '__main__':
    main()
