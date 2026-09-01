# Final thesis handoff — trading contrast extension

## Recommended thesis role

This extension should be concise. It strengthens the dissertation by showing that a more aggressive use of model-market discrepancies does not automatically create superior economic value.

The main text should contain:

1. a short definition of TAEC-11;
2. one external Fixed-versus-TAEC performance table;
3. the four TAEC-minus-Fixed dependence-aware contrasts;
4. transaction-cost break-even interpretation;
5. one paragraph on Greek-like forecast-risk / nonlinear policy sensitivity;
6. the execution caveat.

The appendix can contain the full eight-portfolio risk table, threshold grid, block-length sensitivity, concentration diagnostics and full Greek table.

## Safe headline

The conservative fixed policy dominates the exploratory multi-contract TAEC strategy externally. The aggressive policy generates small positive pre-cost convergence point estimates, but these are not statistically resolved and are overwhelmed by turnover costs at the frozen round-trip cost assumption.

## Do not claim

- that TAEC is a newly selected strategy;
- that the ex-post best threshold is validated;
- that positive pre-cost convergence is statistically proven;
- that snapshot prices are executable bid/ask fills;
- that the Greek-like measures are Black-Scholes Greeks;
- that positive fixed-strategy profitability is statistically established when the corrected dependence-aware/Holm inference does not resolve it.

## Numerical hierarchy

1. `outputs/trading_contrast_extension/thesis/generated/numbers.tex`
2. `outputs/trading_contrast_extension/thesis/tables/*.tex`
3. `outputs/trading_contrast_extension/stage6/thesis_value_pruning_register.csv`
4. Stage 3–5 source CSVs
5. Implementation
