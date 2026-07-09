# 17l HKO Contract Rule Text Certification Report

Generated: 2026-07-09T11:39:30.527645+00:00

## Purpose

This report records the public contract rule text audit for Hong Kong upper-tail Polymarket temperature markets.

The target payoff is

```latex
Z^M_{d,K} = \mathbf{1}\{T_d^{\mathrm{HKO}} \ge K\}.
```

## Certification logic

A market is classified as `formally_certified_by_contract_rule_text` only when the public rule evidence supports all of:

1. Hong Kong Observatory / HKO source.
2. Absolute Daily Max or maximum-temperature source language.
3. Daily Extract source language.
4. One-decimal or equivalent precision convention.
5. Upper-tail child outcome label such as `K°C or higher`.
6. No contradictory source or precision wording.
7. No known realised-outcome mismatch from the previous 17j audit.

A market is classified as `formally_certified_by_gamma_boundary_metadata` only if dedicated boundary metadata explicitly encodes an upper-tail interval.

A market can later be upgraded to `formally_certified_by_polymarket_confirmation` if a written Polymarket or resolver reply confirms the endpoint convention.

## Output files

- `data/processed/17l_hko_contract_rule_text_certification_decision.csv`
- `data/processed/17l_hko_contract_rule_text_evidence.csv`
- Raw JSON/HTML evidence under `data/raw/polymarket_contract_rule_text`

## Certification counts

| status | count |
|---|---:|
| not_certified_descriptive_only | 240 |
| formally_certified_by_contract_rule_text | 14 |

## Interpretation

If the table contains `formally_certified_by_contract_rule_text`, the thesis may state that, within the audited strict Hong Kong HKO Daily Extract one-decimal family, the upper-tail child markets are certified threshold contracts by public rule text.

If the table contains only `empirically_supported_pending_confirmation`, the thesis should not claim formal certification until written Polymarket/resolver confirmation is received or stronger boundary metadata is found.
