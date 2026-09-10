# Main pipeline source package

This directory contains the Python modules used for the main empirical pipeline.

The modules are organised as follows:

1. `hko.py` — Hong Kong Observatory target construction.
2. `ecmwf.py` — ECMWF deterministic forecast reconstruction.
3. `residuals.py` — forecast residual panels and sample construction.
4. `weather_models.py` — Static Gaussian Model, RBF GP and Matérn-3/2 GP estimation and prediction.
5. `market_books.py` — Polymarket contract books, probability vectors and market comparison inputs.
6. `trading.py` — conservative trading strategy and related trading calculations.
7. `synthesis.py` — combined empirical summaries and robustness results.
8. `reporting.py` — figures, tables and numerical outputs used in the dissertation.
9. `release.py` — checks and version information.

The final configuration is stored in `config/final_empirical_config.json`.
