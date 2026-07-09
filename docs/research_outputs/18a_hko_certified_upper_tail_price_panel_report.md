# 18a Hong Kong certified upper-tail market price panel

Run time UTC: 2026-07-09T12:08:07.020603+00:00

## Inputs
- Certified universe: `data/processed/17l_hko_highest_upper_tail_formally_certified_subset_deduped.csv`
- Number of certified contracts: 5

## Outputs
- Price panel: `data/processed/18a_hko_certified_upper_tail_market_price_panel.csv`
- Coverage summary: `data/processed/18a_hko_certified_upper_tail_price_coverage_summary.csv`
- Raw CLOB history JSON directory: `data/raw/polymarket_clob_price_history_18a`

## Coverage
price_history_status
ok    5

## Interpretation note
The CLOB price-history observations are used as market-implied probability observations for empirical comparison. They should not be described as a fully executable trading series unless a separate bid/ask and liquidity execution audit is performed.

## Panel summary
- Price rows: 23
- Unique contracts with prices: 5
- First timestamp: 2026-06-07 00:00:15+00:00
- Last timestamp: 2026-07-09 12:08:04+00:00
