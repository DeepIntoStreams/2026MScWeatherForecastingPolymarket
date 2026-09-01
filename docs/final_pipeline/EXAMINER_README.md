# Examiner entry point — final empirical pipeline

## Status

FINAL_RELEASE_COMPLETE

All March-August settlement targets are complete.

## Start here

1. `config/final_empirical_config.json`
2. `docs/final_pipeline/methodology.md`
3. `docs/final_pipeline/weather_models.md`
4. `docs/final_pipeline/market_books.md`
5. `docs/final_pipeline/trading.md`
6. `docs/final_pipeline/synthesis.md`
7. `docs/final_pipeline/FINAL_THESIS_HANDOFF.md`

## Reproduce / verify

Fast deterministic audit:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

Full rebuild:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The full rebuild may require live access to the original official/public
data endpoints. The audit mode verifies the committed empirical artefacts,
tests, frozen selections and thesis-facing reporting layer.

## Numerical source of truth

Use:

`outputs/final_pipeline/thesis/generated/numbers.tex`

The branch deliberately preserves historical audit outputs, but old values
must not be used in place of the final reporting layer.
