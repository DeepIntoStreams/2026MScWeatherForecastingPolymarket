# Reproducibility

The reported main pipeline results are generated through `src/final_pipeline/` and the corresponding scripts under `scripts/final_pipeline/`.

The recorded version is:

```text
msc-final-pipeline-final
```

The pipeline does not rely on notebook kernel state, manually edited result files, user-specific absolute paths or future information entering historical decision rules.

The main environment files are:

```text
environment-v2-completion.yml
requirements-v2-completion.txt
```

To check the recorded outputs:

```bash
git checkout msc-final-pipeline-final
bash scripts/final_pipeline/reproduce_final_pipeline.sh audit
```

A full rebuild is available with:

```bash
bash scripts/final_pipeline/reproduce_final_pipeline.sh full
```

The full rebuild may require access to the original external data sources.
