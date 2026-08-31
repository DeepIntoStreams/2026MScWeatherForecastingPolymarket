# Authoritative empirical scope

This branch is the final examiner-facing empirical implementation for the MSc
Financial Mathematics dissertation.

## Authoritative material

Only the following new namespace is authoritative for the final March-August
reproduction:

- `config/final_empirical_config.json`
- `src/final_pipeline/`
- `data/raw/{hko,ecmwf,polymarket}/`
- `data/interim/final_pipeline/`
- `data/processed/final_pipeline/`
- `outputs/final_pipeline/`
- `docs/final_pipeline/`
- `environment/final_pipeline/`

## Historical material

Older notebooks, Version-1/Version-2 outputs, `17j` work, experimental CatBoost
work, provisional Gaussian bridges, earlier Phase 8/9 outputs and other historical
directories are retained temporarily for audit/reconciliation only.

They are NOT permitted as empirical inputs to the final pipeline.

The final pipeline may reproduce historical results for audit purposes, but all
submitted March-August thesis evidence must ultimately be regenerated through
`src/final_pipeline/`.

Obsolete material should only be removed from this branch after the corresponding
new final-pipeline stage has reproduced the required result.

Git history remains the permanent record of previous experimentation.
