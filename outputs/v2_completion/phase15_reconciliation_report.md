# Phase 15 Exact GP Code-to-Mathematics Reconciliation

## Status

PASSED

## Certified inputs

- Feature panel: `outputs/v2/diagnostics/06_gp_fold_matrix_panel.csv`.
- Validation panel: `outputs/v2/diagnostics/07_gp_validation_predictions.csv`.
- Full-history models: 4 rule-specific joblib objects.
- Phase 14 starting commit: `recorded in manifest`.

## Exact feature construction

- Calendar time: `(target_date - origin_date).days / days_per_year`.
- Calendar origin: `2024-03-16T00:00:00`.
- Days per year: `365.2425`.
- Seasonal position: `(day_of_year-1)/365.2425`.
- Seasonal coordinates: `sin(2*pi*s)` and `cos(2*pi*s)`.
- Deterministic forecast feature: `forecast_daily_max_c`.
- Maximum empirical feature-formula reconstruction error: 3.109e-15.

## Feature scaling

- Every full-history rule-specific model's stored `X_train_` was reconciled to the raw four-feature panel through an affine map.
- Maximum transformation reconstruction error: 2.665e-15.
- Exact rule-specific centres and scales are in `phase15_feature_transformations.csv`.

## Estimator and response convention

- Estimator: `sklearn.gaussian_process.GaussianProcessRegressor`.
- scikit-learn version: `1.4.2`.
- Exact `normalize_y`, response mean, response scale, `alpha`, optimiser, restarts, random state and kernels are in `phase15_full_fit_model_registry.csv`.

## Predictive variance

- The software predictive variance was independently reconstructed from the fitted Cholesky factor.
- The latent variance was obtained by removing the WhiteKernel test-point diagonal while retaining the fitted observation covariance in conditioning.
- The difference between full and latent variance equals the response-scale-adjusted WhiteKernel variance.
- Maximum predictive-mean reconciliation error: 0.000e+00.
- Maximum predictive-variance reconciliation error: 2.220e-16.
- Maximum white-noise identity error: 2.220e-16.
- Observation noise is therefore identified and included exactly once in the saved model's `return_std` distribution.

## CRPS

- Closed-form Gaussian CRPS was recomputed from every Phase 7 predictive mean and standard deviation.
- The comparison with the stored Phase 7 score is recorded separately for RBF and Matérn-3/2.
- Legacy Phase 7 headline scores remain frozen; new Phase 16 onward Gaussian comparisons will use the analytical formula.

## Closed Phase 14 gaps

- G03: exact feature formulas and scaling.
- G04: exact response transformation.
- G05: observation noise, WhiteKernel and numerical jitter.
- G06: Gaussian CRPS implementation.

## Evidential boundary

Phase 15 does not refit, reselect or alter the certified Phase 7 or Phase 8 models. It inspects the saved models, source code and stored predictions, and verifies their mathematical interpretation. No market record or June outcome enters any model.
