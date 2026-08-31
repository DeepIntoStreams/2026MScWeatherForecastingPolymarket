# Final probabilistic weather-model stage

## Scope

This stage implements the deliberately narrow probabilistic weather hierarchy:

1. raw deterministic point forecast;
2. rule-specific static Gaussian residual law;
3. rule-specific RBF Gaussian process;
4. rule-specific Matérn-3/2 Gaussian process.

These are alternative estimators used for attribution. Greater complexity is not
assumed to imply greater predictive skill.

No Polymarket price, probability, trading payoff or July-August validation
outcome enters model selection.

## Chronological design

Weather-history dates are 16 March 2024 through 15 March 2026.

The first 365 calendar dates form the initial estimation year.

The next 365 calendar dates form the chronological validation year:

- block 1: 91 dates;
- block 2: 91 dates;
- block 3: 91 dates;
- block 4: 92 dates.

For validation block b, a rule-specific training sample contains only usable
residual observations whose target date precedes the first date of block b.

Transformations and GP hyperparameters are re-estimated inside every
block-rule fit.

Unsupported weather forecasts remain absent. A model is not fitted to a
synthetic residual and common validation support is the set of genuinely usable
date-rule observations.

## Residual

For target date d and decision rule r,

    R_{d,r} = HKO_d - ECMWF_{d,r}.

Positive residuals indicate deterministic underprediction of HKO settlement.

## Exact raw GP features

The final GP feature generator uses

    c_d = days since 16 March 2024 / 365.2425,

and

    s_d = (Gregorian day-of-year(d) - 1) / 365.2425.

The raw feature vector is

    x_{d,r}
      = (
          c_d,
          sin(2 pi s_d),
          cos(2 pi s_d),
          deterministic daily maximum
        ).

The four coordinates are deliberately low dimensional.

They permit gradual temporal drift, annual seasonality and temperature-regime
dependence without introducing a broad meteorological feature search.

## Training-only standardisation

Within each rule and training history, all four raw inputs are standardised by
subtracting their training means and dividing by their training population
standard deviations.

The residual response is likewise transformed using the training residual mean
and training population standard deviation.

No validation, market-development or external-validation observation enters a
preprocessing quantity used for an earlier prediction.

The isotropic kernel then uses one common length scale across the four
standardised coordinates.

## Static Gaussian benchmark

For each rule and chronological training history,

    R ~ Normal(mu_r, sigma_r^2),

where mu_r and sigma_r are the training residual mean and Gaussian-MLE
population standard deviation.

The corresponding settlement law is

    HKO ~ Normal(
        deterministic forecast + mu_r,
        sigma_r^2
    ).

The static benchmark identifies the value of a local location-and-dispersion
correction without feature conditioning.

## Gaussian-process model

The transformed response obeys

    R_tilde = f(x_tilde) + epsilon,

with

    f ~ GP(0, k),

and

    epsilon ~ Normal(0, sigma_epsilon^2).

The zero prior mean is imposed only after response centring.

The two latent covariance alternatives are:

- RBF;
- Matérn-3/2.

Both use

    ConstantKernel * covariance + WhiteKernel.

The final explicit implementation is:

- ConstantKernel initial variance: 1;
- ConstantKernel variance bounds: [1e-2, 1e2];
- isotropic length-scale initial value: 1;
- length-scale bounds: [0.05, 10];
- WhiteKernel variance initial value: 0.25;
- WhiteKernel bounds: [1e-3, 10];
- numerical jitter alpha: 1e-8;
- optimiser: L-BFGS-B;
- optimiser restarts: 0;
- fixed random-state record: 20260721;
- external response standardisation;
- `normalize_y=False` inside GaussianProcessRegressor.

The final pipeline therefore makes every preprocessing and statistical-noise
operation explicit rather than relying on hidden estimator normalisation.

## Predictive variance

Settlement probabilities require the predictive distribution of a future
observed residual, not merely the latent GP function.

The software-returned predictive variance is therefore audited numerically
against the GP matrix formula.

The audit verifies:

    observation variance
    =
    latent variance
    +
    WhiteKernel variance,

up to numerical tolerance, with the WhiteKernel contribution included exactly
once.

The 1e-8 jitter is numerical stabilisation only and is not interpreted as
statistical uncertainty.

## CRPS

For a Gaussian predictive law Normal(mu, sigma^2), CRPS is evaluated using the
closed form

    sigma [
        z(2 Phi(z)-1)
        + 2 phi(z)
        - 1/sqrt(pi)
    ],

where z=(y-mu)/sigma.

For the raw point forecast, CRPS equals absolute error.

## Model selection

The four estimators are evaluated on identical chronological date-rule support.

Within a settlement date, available rule losses are averaged first.

The reported validation criterion is then the arithmetic mean over settlement
dates.

Only RBF versus Matérn-3/2 constitutes GP covariance selection.

The GP family with the lower aggregate date-balanced weather-history CRPS is
selected automatically.

The code does not force the historically selected Matérn family to remain
selected if the reconstructed final data favour RBF.

## Uncertainty and dependence

Paired method differences are formed at settlement-date level.

Ordinary date bootstrap intervals use 10,000 replications.

Dependence sensitivity uses circular moving-block bootstrap with block lengths
3, 5 and 7 dates and 10,000 replications.

The date remains the resampling unit.

## Distribution diagnostics

The selected GP is assessed using:

- 50%, 80%, 90% and 95% predictive interval coverage;
- interval width;
- PIT;
- normal Q-Q behaviour;
- standardised predictive residual mean, variance, skewness and kurtosis;
- within-rule lag-one correlation of z;
- within-rule lag-one correlation of z squared;
- rule and chronological-block CRPS.

These diagnostics test the retained probabilistic model. They do not create
additional model-selection branches.

## Frozen March-August prediction

After covariance selection, each rule-specific static, RBF and Matérn model is
refitted once using all usable weather-history observations through 15 March
2026.

Those models are then frozen.

They generate weather distributions for 16 March through 31 August 2026.

March-June HKO outcomes do not refit the weather model, and July-August outcomes
do not enter model selection or fitting.

This preserves the clean separation

    two-year weather estimation
        -> frozen March-August weather distributions
        -> market development
        -> external validation.

The selected weather distribution produced here is the input to the later
temperature-contract event mapping.
