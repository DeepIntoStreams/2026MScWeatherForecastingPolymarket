# 18p June 2026 CLOB market-price recovery

Generated at UTC: `2026-07-21T04:37:44.016524+00:00`

## Overall judgement

**PASS**

## Purpose

Recover historical Polymarket CLOB YES-token prices for all 330 certified June HKO event contracts and construct strict no-look-ahead snapshots at the four established decision rules.

## Main result

- Input contract rows: 330
- Unique event dates: 30
- Unique YES tokens: 330
- Price-history observation rows: 10789
- Decision candidates: 1320
- No-look-ahead decision prices: 1265
- Missing decision-price rows: 55
- Event-book snapshots with at least one price: 115
- Complete eleven-contract event-book snapshots: 115

## CLOB recovery

- History window: 7 days ending at event-day open.
- Fidelity: 60 minutes.
- Selection rule: latest recovered price timestamp at or before the decision cut-off.
- Missing prices are retained as missing and are not imputed.

## Decision cut-offs

| Rule | Hong Kong local time |
|---|---|
| `24h_prior` | 00:00 HKT on the day before the event |
| `12h_prior` | 12:00 HKT on the day before the event |
| `6h_prior` | 18:00 HKT on the day before the event |
| `event_day_open` | 00:00 HKT on the event date |

## Market-only binary score summary

| Rule | n | Mean Brier | Mean log score | Median staleness hours | Mean market probability | Outcome rate |
|---|---:|---:|---:|---:|---:|---:|
| 24h_prior | 297 | 0.05871549 | 0.18402499 | 0.998056 | 0.09408754 | 0.09090909 |
| 12h_prior | 308 | 0.05873689 | 0.18471691 | 0.998333 | 0.09313149 | 0.09090909 |
| 6h_prior | 330 | 0.05601172 | 0.17704579 | 0.998333 | 0.09352121 | 0.09090909 |
| event_day_open | 330 | 0.05575073 | 0.17737592 | 0.998333 | 0.09402424 | 0.09090909 |

## Event-book categorical summary

| Rule | Books | Full books | Full-book rate | Mean total probability | Mean normalised categorical log | Mean normalised multiclass Brier |
|---|---:|---:|---:|---:|---:|---:|
| 24h_prior | 27 | 27 | 1.000000 | 1.034963 | 1.229658 | 0.648074 |
| 12h_prior | 28 | 28 | 1.000000 | 1.024446 | 1.239007 | 0.648440 |
| 6h_prior | 30 | 30 | 1.000000 | 1.028733 | 1.182630 | 0.617790 |
| event_day_open | 30 | 30 | 1.000000 | 1.034267 | 1.189793 | 0.613239 |

## Integrity checks

| Check | Passed | Detail |
|---|---|---|
| target_panel_nonempty | True | target rows=330 |
| target_rows_have_binary_payoff | True | bad rows=0 |
| target_rows_have_yes_tokens | True | missing tokens=0 |
| fetch_inventory_complete | True | fetch rows=330 |
| all_fetches_http_200 | True | non-200 rows=0 |
| price_history_nonempty | True | price rows=10789 |
| decision_panel_complete_grid | True | decision candidate rows=1320 |
| decision_panel_unique_keys | True | duplicate rows=0 |
| scoring_panel_nonempty | True | scoring rows=1265 |
| no_lookahead_decision_timestamps | True | violations=0 |
| probabilities_in_unit_interval | True | bad probabilities=0 |
| non_negative_staleness | True | negative staleness=0 |
| missing_price_issue_table_written | True | issue rows=55 |
| some_event_book_snapshots_observed | True | book snapshots=115 |
| some_full_books_observed | True | full books=115 |
| full_books_have_one_winner | True | bad full books=0 |

## Interpretation

The June market panel is suitable for downstream use where a decision price is available. Missing cells remain explicit. The panel does not use any price observation after its corresponding decision cut-off.
