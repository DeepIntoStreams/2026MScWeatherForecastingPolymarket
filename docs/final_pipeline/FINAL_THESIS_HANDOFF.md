# Final empirical-to-thesis handoff

The empirical build is closed except for the controlled 31-August target refresh if required.

## Seven-question narrative

### Q1. How weak is the raw deterministic forecast as a probabilistic signal?

Raw deterministic forecasts have materially worse continuous CRPS (1.7857) than either probabilistic correction.

### Q2. How much value comes simply from representing uncertainty probabilistically?

The static Gaussian captures 95.8% of the raw-to-selected-GP CRPS improvement.

### Q3. Does the GP add substantial value beyond the simple static correction?

The GP improves continuous CRPS modestly, while the static correction is slightly closer to Polymarket externally in total variation; GP marginal value is therefore real but limited.

### Q4. How do weather probabilities compare with Polymarket?

Polymarket has lower external proper-score loss than either standalone weather model.

### Q5. Do the weather forecast and prediction market contain complementary information?

The development-selected convex pool uses GP weight 0.188 and market weight 0.812; its external proper-score point estimate is best, although its advantage over Polymarket is not statistically resolved.

### Q6. Does the weather signal translate into external economic value?

Under the frozen policy, raw/static/GP external PnL is 0.397, 2.281 and 2.451; GP executes 12 trades with non-annualised Sharpe 0.192.

### Q7. How robust and nonlinear is the forecast-to-trading link?

PnL inference is dependence-sensitive, rule selection has a support-composition caveat, and forecast perturbations produce nonlinear contract-selection and activation effects.

## Pruning discipline

- Main/discussion claims retained: 11
- Appendix-only claims retained: 3
- Claims excluded from primary results: 2

The final thesis should not add every available robustness output merely because it exists.
Use the claims register and seven-question map to preserve a concise empirical argument.

## Numerical source

`outputs/final_pipeline/thesis/generated/numbers.tex`
