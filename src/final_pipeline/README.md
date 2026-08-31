# Final pipeline source package

This directory is the only authoritative code namespace for the final empirical
release.

The final implementation will be organised in the following order:

1. `hko.py`
   - HKO acquisition, parsing and audit.

2. `ecmwf.py`
   - ECMWF historical forecast acquisition and issue-time metadata.

3. `weather_panel.py`
   - four decision rules, deterministic maxima and HKO residuals.

4. `weather_models.py`
   - Raw, Static Gaussian, RBF GP benchmark and Matérn-3/2 GP.

5. `market_events.py`
   - Gamma metadata and eleven-contract event-book certification.

6. `market_prices.py`
   - historical YES prices and decision-time snapshots.

7. `event_probabilities.py`
   - Gaussian-to-contract probability mapping.

8. `scoring.py`
   - binary/categorical proper scores and total variation.

9. `development.py`
   - March-June market-dependent pool and threshold selection.

10. `external_validation.py`
    - untouched July-August evaluation.

11. `trading.py`
    - simple fixed-policy Raw/Static/Matérn trading attribution.

12. `robustness.py`
    - bootstrap, moving-block bootstrap, transaction-cost and
      temperature-probability-PnL sensitivity.

13. `thesis_outputs.py`
    - final tables, figures, sample-size registry and LaTeX numbers.

14. `run_all.py`
    - final deterministic reproduction orchestrator.

Modules will be implemented sequentially and tested before the next stage becomes
authoritative.
