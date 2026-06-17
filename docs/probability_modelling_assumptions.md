# Probability Modelling Assumptions

## Purpose

This note clarifies the role of the preliminary probability-conversion method used in the single-market mini-pipeline and explains the revised probability-modelling direction for the dissertation.

The initial mini-pipeline converted a point temperature forecast into a probability distribution over Polymarket temperature bins using a normal approximation. This was useful as an early prototype because it made the full workflow testable: a weather forecast could be transformed into bin probabilities, compared with market-implied probabilities, scored against the realised outcome and linked to a simple trading interpretation.

However, this conversion should not be treated as the final probability model. The normal approximation introduces assumptions that require careful justification and empirical testing. The final methodology should therefore move towards probability estimates obtained either from probabilistic weather model outputs or from a supervised post-processing model trained directly for threshold exceedance or temperature-bin outcomes.

## Prototype method in the mini-pipeline

The single-market mini-pipeline used a point forecast for daily maximum temperature and assumed an error distribution around that point forecast. Under a normal approximation, the probability of a temperature bin was calculated by integrating the assumed normal predictive distribution over the relevant interval.

For example, if the model forecast for the daily maximum temperature is ( \hat{T} ), and the assumed forecast error standard deviation is ( \sigma ), then the prototype predictive distribution can be written as

[
T = \hat{T} + \varepsilon, \qquad \varepsilon \sim N(0,\sigma^2).
]

For a bin ([a,b)), the model-implied probability is then

[
P(a \leq T < b)
===============

## \Phi\left(\frac{b-\hat{T}}{\sigma}\right)

\Phi\left(\frac{a-\hat{T}}{\sigma}\right),
]

where ( \Phi ) denotes the standard normal cumulative distribution function.

This approach was useful for checking the mechanics of the project, but it is mathematically restrictive if used without further validation.

## Limitations of the Gaussian conversion

The Gaussian conversion requires several assumptions. First, the forecast errors must be centred around zero, or any systematic bias must be estimated and corrected. Second, the error variance must be estimated from historical data rather than chosen arbitrarily. Third, if a single constant ( \sigma ) is used, the method assumes homoskedastic forecast errors, even though temperature forecast uncertainty may vary with lead time, season, location and weather regime. Fourth, the normality assumption should be checked empirically because temperature forecast errors may show skewness, heavy tails or regime dependence.

The method also assumes that the forecast error distribution is stable over time. This is a strong assumption in a setting where the underlying data source, forecast model, location and season may all affect error behaviour. For daily maximum temperature contracts, there is an additional complication because the target is a daily maximum over a local calendar day rather than a single forecast valid time. This makes the mapping from model output to settlement variable non-trivial.

Therefore, the prototype normal approximation should not be presented as the dissertation’s final probability model unless the residual distribution is estimated, diagnosed and justified.

## Conditions required for a Gaussian residual model

A Gaussian residual model could still be used as a benchmark if the assumptions are made explicit and tested. A more rigorous version would require historical forecast and realised settlement-source data. Forecast errors would be defined as

[
e_t = T_t^{\text{settlement}} - \hat{T}_t^{\text{forecast}},
]

where (T_t^{\text{settlement}}) is the official realised value from the settlement source and (\hat{T}_t^{\text{forecast}}) is the forecast available at the chosen information time.

The mean, variance and distributional shape of (e_t) would need to be examined. At minimum, the analysis should estimate bias, residual variance and calibration by lead time. It should also inspect whether errors differ across forecast issue times, locations and months. If the residuals are not approximately Gaussian, or if the estimated variance changes materially with lead time or weather conditions, then a simple normal residual model would be insufficient.

For this reason, the Gaussian approach is best treated as an interpretable benchmark rather than the central contribution.

## Revised probability-modelling direction

The revised methodology should move towards probability estimates that are directly aligned with the contract payoff.

For binary threshold markets, the target variable can be defined as

[
Y_t^{(K)} = \mathbf{1}{T_t^{\text{settlement}} \geq K},
]

where (K) is the temperature threshold specified by the market. The modelling task then becomes a supervised probability-estimation problem:

[
p_t^{(K)} = P(Y_t^{(K)} = 1 \mid \mathcal{F}_t),
]

where (\mathcal{F}_t) represents the information available at the forecast issue time.

This formulation is better aligned with Polymarket temperature contracts because the model outputs a probability for the same event that the market is pricing. It also avoids imposing a full continuous temperature distribution when the trading decision only requires a threshold-exceedance probability.

For temperature-bin markets, the target can be extended to a multiclass classification problem, where each class corresponds to a settlement bin. The model would then output a probability vector over mutually exclusive temperature bins. This probability vector can be compared directly with the market-implied distribution.

## Candidate modelling approaches

The main revised approach is supervised post-processing. Inputs may include AI weather model forecasts, forecast lead time, forecast issue time, location, historical official settlement-source data and other relevant weather variables. The output should be either threshold-exceedance probabilities or bin probabilities.

Tree-based models such as CatBoost, random forests or gradient boosting are natural first candidates because they can handle nonlinear effects, interactions and tabular forecast features. They are also easier to interpret and validate than a deep learning model in the early empirical stage. A neural network can be considered later if the dataset is large enough and if the additional complexity is justified.

A direct probabilistic AI weather forecast should also be used as a benchmark where available. For example, ensemble or probabilistic model outputs can provide an empirical distribution over future temperature outcomes. These probabilities can then be compared with both the supervised post-processing model and the Polymarket-implied probabilities.

## Implications for scoring and trading

The revised probability framework supports proper probability scoring. For binary threshold events, the model can be evaluated using Brier score, log score and calibration checks. For temperature-bin markets, the probability vector can be evaluated using multiclass log score, Brier score and realised-bin accuracy.

The trading strategy should use only information available at the relevant issue time. Model probabilities should be compared with market-implied probabilities sampled at the same information time, following the time-alignment framework. Any trading rule should account for bid-ask spread, market liquidity, transaction costs and robustness across thresholds or cities.

The realised official temperature should only be used after the event for scoring and backtesting. It should not influence the forecast timestamp or market price timestamp.

## Conclusion

The Gaussian conversion in the mini-pipeline was a useful prototype for testing the end-to-end workflow, but it should not be treated as the final probability-modelling method. A rigorous dissertation methodology should either estimate and validate the residual distribution carefully, or move towards probability models that are directly trained for the market payoff.

The preferred direction is to use AI weather forecasts and official settlement-source data to build supervised post-processing models for threshold-exceedance or bin probabilities. This better matches the structure of Polymarket contracts, reduces reliance on arbitrary distributional assumptions and provides a stronger basis for probability scoring and trading evaluation.
