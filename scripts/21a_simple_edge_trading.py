#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', type=Path, default=Path.cwd())
    p.add_argument('--thresholds', default='0,0.02,0.05,0.10')
    p.add_argument('--primary-threshold', type=float, default=0.05)
    p.add_argument('--trade-cost', type=float, default=0.0)
    a = p.parse_args()
    thresholds = tuple(float(x.strip()) for x in a.thresholds.split(',') if x.strip())
    if a.primary_threshold not in thresholds:
        raise ValueError('Primary threshold must be in threshold grid.')
    if any(t < 0 for t in thresholds) or a.trade_cost < 0:
        raise ValueError('Thresholds and costs must be non-negative.')
    return a.repo_root.expanduser().resolve(), thresholds, a.primary_threshold, a.trade_cost


def load_inputs(root: Path):
    p = root / 'data' / 'processed'
    panel_path = p / '20e_locked_holdout_prediction_panel.csv'
    manifest_path = p / '20e_locked_holdout_manifest.json'
    if not panel_path.exists() or not manifest_path.exists():
        raise FileNotFoundError('Missing 20e locked-holdout inputs.')
    panel = pd.read_csv(panel_path, low_memory=False)
    panel['event_date'] = pd.to_datetime(panel['event_date']).dt.normalize()
    manifest = json.loads(manifest_path.read_text())
    return panel, manifest


def model_mapping(panel: pd.DataFrame):
    mapping = {
        'catboost_raw': 'p_catboost_raw_holdout',
        'catboost_platt': 'p_catboost_platt_holdout',
        'ecmwf_raw': 'p_ecmwf_raw',
        'ecmwf_bias_fixed_sigma': 'p_ecmwf_bias_fixed_sigma',
        'ecmwf_bias_adaptive_sigma': 'p_ecmwf_bias_adaptive_sigma',
    }
    required = ['p_market', 'target_Y_event', 'decision_rule', 'event_date'] + list(mapping.values())
    missing = [c for c in required if c not in panel.columns]
    if missing:
        raise ValueError(f'Missing required columns: {missing}')
    return mapping


def simulate(panel, mapping, thresholds, cost):
    ids = [c for c in ['event_date','date_group_id','decision_rule','market_slug','condition_id','token_id','contract_event_type_v2','target_Y_event'] if c in panel.columns]
    frames = []
    for model, col in mapping.items():
        base = panel[ids].copy()
        base['model'] = model
        base['p_market'] = pd.to_numeric(panel['p_market'], errors='coerce')
        base['p_model'] = pd.to_numeric(panel[col], errors='coerce')
        base = base.dropna(subset=['p_market','p_model','target_Y_event'])
        base['edge_model_minus_market'] = base['p_model'] - base['p_market']
        for t in thresholds:
            d = base.copy()
            d['threshold'] = float(t)
            d['position'] = np.select(
                [d['edge_model_minus_market'] >= t, d['edge_model_minus_market'] <= -t],
                ['YES','NO'], default='FLAT')
            d['trade_indicator'] = d['position'].ne('FLAT').astype(int)
            d['yes_trade_indicator'] = d['position'].eq('YES').astype(int)
            d['no_trade_indicator'] = d['position'].eq('NO').astype(int)
            y = d['target_Y_event'].astype(int)
            d['gross_pnl'] = np.select(
                [d['position'].eq('YES'), d['position'].eq('NO')],
                [y - d['p_market'], d['p_market'] - y], default=0.0)
            d['net_pnl'] = np.where(d['trade_indicator'].eq(1), d['gross_pnl'] - cost, 0.0)
            d['absolute_edge'] = d['edge_model_minus_market'].abs()
            d['correct_direction'] = np.select(
                [d['position'].eq('YES') & y.eq(1), d['position'].eq('NO') & y.eq(0), d['position'].eq('FLAT')],
                [1.0,1.0,np.nan], default=0.0)
            frames.append(d)
    return pd.concat(frames, ignore_index=True)


def summaries(trades, primary):
    rows = []
    for (model, rule, t), g in trades.groupby(['model','decision_rule','threshold']):
        m = g['trade_indicator'].eq(1)
        rows.append({
            'model': model, 'decision_rule': rule, 'threshold': t,
            'n_opportunities': len(g), 'n_dates': g['event_date'].nunique(),
            'n_trades': int(m.sum()), 'n_yes_trades': int(g['yes_trade_indicator'].sum()),
            'n_no_trades': int(g['no_trade_indicator'].sum()), 'trade_rate': g['trade_indicator'].mean(),
            'mean_absolute_edge_all': g['absolute_edge'].mean(),
            'mean_absolute_edge_trades': g.loc[m,'absolute_edge'].mean() if m.any() else np.nan,
            'total_net_pnl': g['net_pnl'].sum(),
            'mean_net_pnl_per_opportunity': g['net_pnl'].mean(),
            'mean_net_pnl_per_trade': g.loc[m,'net_pnl'].mean() if m.any() else np.nan,
            'median_net_pnl_per_trade': g.loc[m,'net_pnl'].median() if m.any() else np.nan,
            'hit_rate_trades': g.loc[m,'correct_direction'].mean() if m.any() else np.nan,
        })
    strategy = pd.DataFrame(rows).sort_values(['threshold','model','decision_rule']).reset_index(drop=True)

    pooled_rows = []
    for (model, t), g in trades.groupby(['model','threshold']):
        m = g['trade_indicator'].eq(1)
        pooled_rows.append({
            'model': model, 'threshold': t, 'n_opportunities': len(g),
            'n_dates': g['event_date'].nunique(), 'n_decision_rules': g['decision_rule'].nunique(),
            'n_trades': int(m.sum()), 'trade_rate': g['trade_indicator'].mean(),
            'total_net_pnl': g['net_pnl'].sum(),
            'mean_net_pnl_per_opportunity': g['net_pnl'].mean(),
            'mean_net_pnl_per_trade': g.loc[m,'net_pnl'].mean() if m.any() else np.nan,
            'hit_rate_trades': g.loc[m,'correct_direction'].mean() if m.any() else np.nan,
            'is_primary_threshold': bool(np.isclose(float(t), float(primary))),
        })
    pooled = pd.DataFrame(pooled_rows).sort_values(['threshold','model']).reset_index(drop=True)

    headline = strategy[np.isclose(strategy['threshold'], primary)].copy()
    headline['strategy_scope'] = 'standalone_decision_rule'
    headline = headline.sort_values(['total_net_pnl','mean_net_pnl_per_trade'], ascending=False).reset_index(drop=True)

    pooled_primary = pooled[np.isclose(pooled['threshold'], primary)].copy()
    pooled_primary['strategy_scope'] = 'pooled_across_decision_rules_diagnostic_only'

    daily = trades.groupby(['model','decision_rule','threshold','event_date'], as_index=False).agg(
        n_trades=('trade_indicator','sum'), total_net_pnl=('net_pnl','sum'), total_gross_pnl=('gross_pnl','sum'))
    daily = daily.sort_values(['model','decision_rule','threshold','event_date'])
    daily['cumulative_net_pnl'] = daily.groupby(['model','decision_rule','threshold'])['total_net_pnl'].cumsum()
    return strategy, pooled, headline, pooled_primary, daily


def make_checks(panel, trades, pooled, headline, daily, thresholds, primary):
    checks=[]
    def add(name, passed, detail): checks.append({'check':name,'passed':bool(passed),'detail':detail})
    add('prediction_panel_nonempty', len(panel)>0, f'rows={len(panel)}')
    add('trade_panel_nonempty', len(trades)>0, f'rows={len(trades)}')
    add('primary_threshold_present', any(np.isclose(thresholds,primary)), f'primary_threshold={primary}')
    add('market_probability_in_unit_interval', panel['p_market'].between(0,1).all(), 'checked')
    add('model_and_market_probabilities_in_unit_interval', trades[['p_market','p_model']].apply(lambda s:s.between(0,1).all()).all(), 'checked')
    add('positions_restricted_to_yes_no_flat', set(trades['position']).issubset({'YES','NO','FLAT'}), str(sorted(set(trades['position']))))
    add('trade_indicator_matches_position', (trades['trade_indicator'].eq(0)==trades['position'].eq('FLAT')).all(), 'checked')
    add('yes_no_positions_mutually_exclusive', ((trades['yes_trade_indicator']+trades['no_trade_indicator'])<=1).all(), 'checked')
    y=trades['target_Y_event'].astype(int); yes=trades['position'].eq('YES'); no=trades['position'].eq('NO'); flat=trades['position'].eq('FLAT')
    add('yes_trade_pnl_formula_correct', np.allclose(trades.loc[yes,'gross_pnl'], y.loc[yes]-trades.loc[yes,'p_market']), 'checked')
    add('no_trade_pnl_formula_correct', np.allclose(trades.loc[no,'gross_pnl'], trades.loc[no,'p_market']-y.loc[no]), 'checked')
    add('flat_trade_pnl_zero', np.allclose(trades.loc[flat,'net_pnl'],0), 'checked')
    add('threshold_summary_nonempty', len(pooled)>0, f'rows={len(pooled)}')
    add('daily_panel_nonempty', len(daily)>0, f'rows={len(daily)}')
    add('threshold_grid_preserved', set(np.round(pooled['threshold'],10))==set(np.round(thresholds,10)), f'observed={sorted(set(pooled["threshold"]))}')
    add('model_count_expected', trades['model'].nunique()==5, f'models={sorted(trades["model"].unique())}')
    add('holdout_dates_preserved', trades['event_date'].nunique()==panel['event_date'].nunique(), f'dates={trades["event_date"].nunique()}')
    flagged=pooled[pooled['is_primary_threshold'].astype(bool)]
    add('primary_threshold_flag_correct', len(flagged)>0 and np.isclose(flagged['threshold'],primary).all() and not pooled.loc[~np.isclose(pooled['threshold'],primary),'is_primary_threshold'].astype(bool).any(), f'flagged_rows={len(flagged)}')
    add('headline_strategies_keep_one_decision_rule', not headline.empty and headline['decision_rule'].notna().all() and headline['strategy_scope'].eq('standalone_decision_rule').all(), f'headline_rows={len(headline)}')
    add('headline_does_not_pool_decision_rules', not headline.empty and headline.groupby(['model','decision_rule','threshold']).ngroups==len(headline), 'headline is model × decision-rule specific')
    return pd.DataFrame(checks)


def figures(headline, daily, outdir):
    import matplotlib.pyplot as plt
    outdir.mkdir(parents=True, exist_ok=True)
    paths=[]
    plot=headline.copy(); plot['strategy_label']=plot['model']+' | '+plot['decision_rule']
    for col, ylabel, fname, title in [
        ('total_net_pnl','Total net PnL','21a_standalone_total_net_pnl_primary_threshold.png','Standalone total net PnL at primary threshold'),
        ('mean_net_pnl_per_trade','Mean net PnL per trade','21a_standalone_mean_net_pnl_per_trade.png','Standalone mean net PnL per trade'),
        ('n_trades','Number of trades','21a_standalone_trade_counts.png','Standalone trade counts')]:
        fig,ax=plt.subplots(figsize=(13,6)); ax.bar(plot['strategy_label'],plot[col]); ax.set_ylabel(ylabel); ax.set_title(title); ax.tick_params(axis='x',rotation=45); fig.tight_layout(); p=outdir/fname; fig.savefig(p,dpi=180); plt.close(fig); paths.append(p)
    primary_daily=daily[np.isclose(daily['threshold'],0.05)]
    for rule,g in primary_daily.groupby('decision_rule'):
        fig,ax=plt.subplots(figsize=(10,5))
        for model,m in g.groupby('model'):
            ax.plot(m['event_date'],m['cumulative_net_pnl'],marker='o',label=model)
        ax.set_ylabel('Cumulative net PnL'); ax.set_title(f'Cumulative net PnL, standalone {rule} strategy'); ax.legend(); fig.autofmt_xdate(); fig.tight_layout(); p=outdir/f'21a_cumulative_net_pnl_{rule}.png'; fig.savefig(p,dpi=180); plt.close(fig); paths.append(p)
    return paths


def write_report(manifest, headline, pooled_primary, pooled, checks, path):
    lines=[
        '# 21a simple edge-based trading simulation','',
        '## Status','',
        'This trading layer uses the frozen 20e locked final-holdout probabilities and does not alter the forecasting specification.','',
        '## Prespecified rule','',
        f"- threshold grid: {manifest['threshold_grid']}", f"- primary threshold: {manifest['primary_threshold']}", f"- trade cost per contract: {manifest['trade_cost_per_contract']}", '- position size: one unit per trade','',
        '## Execution assumptions','',
        'The observed Polymarket YES probability is used as a frictionless execution proxy. The simulation excludes bid-ask spread, fees, slippage, liquidity constraints, partial fills, market impact, capital limits, and position netting.','',
        '## Primary standalone model × decision-rule strategies','', headline.to_markdown(index=False),'',
        '## Pooled diagnostic only','',
        'The following table pools decision rules only as a descriptive diagnostic and is not an implementable portfolio.', '', pooled_primary.to_markdown(index=False),'',
        '## Full threshold diagnostic','', pooled.to_markdown(index=False),'',
        '## Integrity checks','', checks.to_markdown(index=False),'',
        '## Interpretation','',
        'The five percentage point threshold is prespecified. Alternative thresholds are sensitivity diagnostics. Results are hypothetical and based on ten settlement dates.','']
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text('\n'.join(lines),encoding='utf-8')


def serialize(df):
    out=df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]): out[c]=out[c].dt.strftime('%Y-%m-%d')
    return out


def main():
    root, thresholds, primary, cost = parse_args()
    processed=root/'data'/'processed'; docs=root/'docs'/'research_outputs'; figdir=root/'figures'/'21a_simple_edge_trading'
    panel,m20e=load_inputs(root); mapping=model_mapping(panel); trades=simulate(panel,mapping,thresholds,cost)
    strategy,pooled,headline,pooled_primary,daily=summaries(trades,primary)
    checks=make_checks(panel,trades,pooled,headline,daily,thresholds,primary)
    issues=checks[~checks['passed'].astype(bool)].copy()
    if issues.empty: issues=pd.DataFrame(columns=['check','passed','detail'])
    manifest={
        'step':'21a','input_step':'20e','evaluation_sample':'locked_final_holdout',
        'development_start_date':m20e['development_start_date'],'development_end_date':m20e['development_end_date'],
        'holdout_start_date':m20e['holdout_start_date'],'holdout_end_date':m20e['holdout_end_date'],
        'n_holdout_dates':int(panel['event_date'].nunique()),'n_holdout_rows':int(len(panel)),
        'model_columns_used':mapping,'threshold_grid':list(thresholds),'primary_threshold':primary,
        'trade_cost_per_contract':cost,'position_size':'one_unit','market_probability_source':'p_market',
        'frozen_feature_set':m20e['feature_set'],'frozen_candidate_id':m20e['candidate_id'],
        'frozen_calibration_method':m20e['calibration_method'],'forecast_specification_changed':False,
        'headline_strategy_scope':'standalone_model_by_decision_rule',
        'pooled_across_decision_rules_is_diagnostic_only':True,
        'execution_price_assumption':'observed_market_probability_as_frictionless_proxy',
        'excluded_execution_frictions':['bid_ask_spread','fees','slippage','liquidity_constraints','partial_fills','market_impact','capital_limits','position_netting']}
    outputs={
        'trade':processed/'21a_simple_edge_trade_panel.csv','strategy':processed/'21a_simple_edge_strategy_summary.csv',
        'threshold':processed/'21a_simple_edge_threshold_summary.csv','headline':processed/'21a_simple_edge_primary_standalone_strategy_summary.csv',
        'pooled':processed/'21a_simple_edge_primary_pooled_diagnostic.csv','daily':processed/'21a_simple_edge_daily_pnl.csv',
        'checks':processed/'21a_simple_edge_integrity_checks.csv','issues':processed/'21a_simple_edge_issues.csv',
        'manifest':processed/'21a_simple_edge_manifest.json','report':docs/'21a_simple_edge_trading_report.md'}
    serialize(trades).to_csv(outputs['trade'],index=False); strategy.to_csv(outputs['strategy'],index=False); pooled.to_csv(outputs['threshold'],index=False); headline.to_csv(outputs['headline'],index=False); pooled_primary.to_csv(outputs['pooled'],index=False); serialize(daily).to_csv(outputs['daily'],index=False); checks.to_csv(outputs['checks'],index=False); issues.to_csv(outputs['issues'],index=False); outputs['manifest'].write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    fpaths=figures(headline,daily,figdir); write_report(manifest,headline,pooled_primary,pooled,checks,outputs['report'])
    review=root/'data'/'review_bundles'/'21a_review_bundle.zip'; review.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(review,'w',zipfile.ZIP_DEFLATED) as z:
        for path in list(outputs.values())+fpaths:
            if path.exists(): z.write(path,arcname=str(path.relative_to(root)))
    print(f'21a completed: {int(checks.passed.sum())}/{len(checks)} checks passed')
    print(f'Review bundle: {review}')
    return 0 if checks['passed'].all() else 2

if __name__=='__main__':
    raise SystemExit(main())
