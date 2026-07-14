# Hong Kong empirical baseline freeze v1

Generated: `2026-07-14 13:50:19 UTC`

Branch: `edward-17j-hko-upper-tail-audit`

Frozen source HEAD: `eddf2f6`

Full commit hash: `eddf2f64c8a4f40ea0682a952c4703da588c1de4`

## Purpose

This file freezes the first validated Hong Kong empirical baseline generated from the 18f, 18h and 18i pipeline. It should be treated as the reference version before the subsequent settlement-family audit, full HKO contract-event expansion, ECMWF forecast alignment, supervised postprocessing and trading simulation layers are added.

## Baseline status

The current baseline verifies that the following empirical chain is operational:

1. official HKO Daily Extract maximum-temperature outcomes;
2. Polymarket Hong Kong event and child-market extraction;
3. upper-tail threshold contract certification;
4. CLOB narrow-window historical price recovery;
5. no-lookahead market decision prices;
6. market-only Brier and log-score evaluation;
7. dissertation-facing summary tables and figures.

## Key sample sizes

- Main formally certified scoring rows: `265`
- Official HKO daily maximum-temperature observations: ``
- Matched Polymarket event pages: ``
- Flattened child markets: ``
- Formally certified upper-tail rows: ``
- Recovered CLOB price observations: ``
- No-lookahead decision rows: ``
- Scoring-ready rows: ``
- Manifest path: `data/processed/baseline_freezes/18i_hko_empirical_baseline_v1_manifest.csv`

## Best market-only decision rule in frozen baseline

- Decision rule: `last_price_before_6h_prior`
- Empirical role: ``
- n: `68`
- Mean Brier score: `0.067528419117647`
- Mean log score: `0.2305866693128196`
- Mean market probability: `0.1663676470588235`
- Outcome rate: `0.1617647058823529`

## Integrity checks

- `main_role_present`: `True`
- `probabilities_in_unit_interval`: `True`
- `binary_outcomes`: `True`
- `non_negative_scores`: `True`
- `no_lookahead_timestamps`: `True`
- `formal_certified_subset_nonempty`: `True`

## Interpretation

This freeze does not claim that the Hong Kong contract universe is final. It freezes the first validated upper-tail baseline. The next empirical layer will update the market admissibility framework by adding a Gamma/rule-text settlement-family audit and by generalising from threshold-only events to certified HKO contract events, including both upper-tail and interior-bin contracts where the HKO Daily Extract one-decimal family is verified.

## Frozen artefact manifest

The full manifest contains file sizes, row counts and SHA256 hashes for all required 18f, 18h and 18i baseline artefacts.
