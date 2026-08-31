# Reproducibility specification

The final submitted empirical release must satisfy the following conditions.

## Single authoritative execution path

All submitted empirical tables, figures and headline numbers must ultimately be
generated through `src/final_pipeline/`.

Historical outputs may be used only for reconciliation.

## No hidden state

The final reproduction must not depend on:

- Jupyter kernel state;
- manually edited result CSVs;
- hard-coded user-specific absolute paths;
- unpublished local files;
- a different Git branch;
- future information entering a historical decision rule.

## Environment

The final branch records:

- source/base commit;
- branch;
- Python executable and version;
- installed Python packages;
- operating-system snapshot;
- repository remotes;
- UTC setup timestamp.

The dependency snapshot produced during initialisation is provisional and will be
reduced to the minimal final dependency set after the completed pipeline has run
successfully from a clean environment.

## Final acceptance target

The completed project should expose a short top-level reproduction command, ideally:

`python -m src.final_pipeline.run_all`

or an equivalent `make reproduce` target.

That command will be implemented only after the individual empirical stages have
been rebuilt and audited.
