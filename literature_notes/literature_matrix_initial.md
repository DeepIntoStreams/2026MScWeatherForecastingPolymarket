# Initial Literature Matrix — Weather Forecasting and Polymarket Trading

## Purpose of this note

This note summarises the key literature for the MSc project on weather forecasting and Polymarket trading. The aim is not yet to provide a full literature review, but to identify how each paper contributes to the project’s methodology.

The project requires three connected strands of literature:

1. Modern machine-learning weather forecasting models.
2. Probabilistic forecasting, calibration and scoring rules.
3. Forecast-to-trading frameworks, especially where weather forecasts are converted into economic decisions.

The initial empirical project will focus on temperature-based Polymarket contracts. Therefore, the most important methodological challenge is converting weather forecasts into calibrated probabilities for binary or multi-outcome temperature events.

---

## Literature matrix

| Source                                                                                                                         | Main contribution                                                                                                                                                                                                                                                                                        | Relevance to this project                                                                                                                                                                                                                                    | How I will use it                                                                                                                                                                                                                                       |
| ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Project proposal: *Weather Forecasting and Polymarket Trading*                                                                 | Defines the project around two components: weather prediction and prediction-market strategy design. It explicitly mentions comparing model-based probabilities with Polymarket-implied probabilities using Brier score, log score and calibration analysis, followed by backtesting trading strategies. | This is the main project anchor. It confirms that the dissertation should connect forecast generation, probabilistic evaluation and trading strategy design.                                                                                                 | I will use this to justify the overall structure of the thesis: forecast data → probabilistic post-processing → market-implied probability comparison → trading backtest.                                                                               |
| GraphCast — *Learning Skillful Medium-Range Global Weather Forecasting*                                                        | Introduces a graph neural network for medium-range global weather forecasting. It predicts many surface and atmospheric variables, including 2m temperature, on a global grid.                                                                                                                           | Highly relevant for the global-weather-model side of the project. It motivates the idea that modern graph-based models can generate useful global forecasts, but also highlights that deterministic forecasts do not directly give full event probabilities. | I will use GraphCast mainly in the literature review and as motivation for global-to-local weather modelling. It may also motivate an extension where global forecasts are post-processed into local city-level probabilities.                          |
| FourCastNet — *A Global Data-Driven High-Resolution Weather Model Using Adaptive Fourier Neural Operators*                     | Presents a fast high-resolution global weather model using Adaptive Fourier Neural Operators. It is notable for computational speed and the possibility of producing large forecast ensembles efficiently.                                                                                               | Relevant because fast AI weather models can potentially support probabilistic forecasting and frequent forecast updates, which matter for trading applications.                                                                                              | I will use FourCastNet to discuss the speed advantage of AI weather models and their possible role in generating forecast updates or large ensembles. It is unlikely to be my first empirical model unless data and compute access are straightforward. |
| Pangu-Weather — *Accurate Medium-Range Global Weather Forecasting with 3D Neural Networks*                                     | Uses 3D neural networks and Earth-specific priors for medium-range global weather forecasting, with strong deterministic performance compared with operational numerical weather prediction systems.                                                                                                     | Relevant as another major AI weather model. It strengthens the literature review by showing that modern weather AI is not limited to graph neural networks.                                                                                                  | I will use it as part of the model-review section, especially when comparing different AI-weather-model architectures: graph models, Fourier neural operators, 3D transformers and foundation models.                                                   |
| Aurora — *A Foundation Model for the Earth System*                                                                             | Introduces a large-scale foundation model trained on diverse geophysical data and fine-tuned for multiple Earth-system forecasting tasks.                                                                                                                                                                | Relevant for discussing the newest direction in weather and environmental forecasting: general-purpose foundation models rather than task-specific models.                                                                                                   | I will use Aurora to frame the “foundation model” direction and to explain why the project may review such models without necessarily training one from scratch.                                                                                        |
| AIFS-CRPS — *Ensemble Forecasting Using a Model Trained with a Loss Function Based on the Continuous Ranked Probability Score* | Develops a probabilistic ensemble version of ECMWF’s Artificial Intelligence Forecasting System, trained using a CRPS-based proper scoring-rule objective.                                                                                                                                               | Very important because Polymarket trading needs probabilities, not only point forecasts. AIFS-CRPS directly connects machine-learning weather models with probabilistic forecasting and uncertainty quantification.                                          | I will use AIFS-CRPS as a key reference for proper scoring rules, ensemble forecasts, CRPS, uncertainty representation and calibration. It supports the project’s focus on turning forecast information into probability distributions.                 |
| HEFTCom2024 competition summary — *The Hybrid Renewable Energy Forecasting and Trading Competition 2024*                       | Studies a live forecasting and trading competition where participants transformed weather forecasts into renewable-energy forecasts and trading decisions. It evaluates both forecast accuracy and trading value.                                                                                        | This is the closest analogue to my project. Although it concerns energy trading rather than Polymarket, the structure is similar: weather forecasts are converted into probabilistic forecasts, then into trading decisions.                                 | I will use this as the main methodological analogy for the forecast-to-trading pipeline. It supports the idea that forecast quality should be assessed both statistically and economically.                                                             |
| HEFTCom winning model — *A Stacked CatBoost Approach for Probabilistic Wind and Solar Power Forecasting*                       | Describes the winning HEFTCom model, using stacked CatBoost, multiple weather forecast datasets, robust data handling and probabilistic forecasting.                                                                                                                                                     | Relevant because it shows that practical post-processing and model stacking can be highly competitive. This is useful for my project because a transparent post-processing layer may be more feasible than training a large AI weather model from scratch.   | I will use this paper to justify practical post-processing models such as linear calibration, quantile regression, gradient boosting or CatBoost. It also supports using multiple forecast sources and careful data-quality handling.                   |
| Polymarket API documentation                                                                                                   | Provides access to market metadata, outcome prices, price history, order books, trades and other market information.                                                                                                                                                                                     | This is the core source for market-implied probabilities and later trading backtests.                                                                                                                                                                        | I will use the API to move from manual market inspection to systematic data collection. The initial target is to retrieve market metadata, outcome prices, token IDs and price histories for selected temperature contracts.                            |
| Forecast verification and scoring-rule literature                                                                              | Proper scoring rules such as Brier score, log score, CRPS and pinball loss measure different aspects of probabilistic forecast quality. Calibration analysis checks whether predicted probabilities match empirical frequencies.                                                                         | Central to the numerical evaluation. The dissertation needs to compare model-implied probabilities with market-implied probabilities in a rigorous way.                                                                                                      | I will use Brier score and log score for binary Polymarket outcomes, calibration/reliability diagrams for probability quality, and CRPS or pinball loss if the forecast source provides full distributions or quantiles.                                |

---

## Emerging structure from the literature

The literature suggests that the thesis should not be framed as simply “use an AI weather model to trade”. A stronger and more feasible framing is:

1. Modern AI weather models provide increasingly accurate global forecasts.
2. Prediction-market contracts require local, event-specific probabilities.
3. Therefore, a post-processing layer is needed to map broad/global weather forecasts into local temperature distributions.
4. These distributions can then be translated into binary or multi-outcome Polymarket probabilities.
5. The resulting model-implied probabilities can be compared with market-implied probabilities.
6. If systematic discrepancies exist, they can be tested through scoring rules and paper-trading backtests.

This framing keeps the project mathematically rigorous while avoiding the risk of overcommitting to training a large weather model from scratch.

---

## Provisional methodology implied by the literature

The initial empirical methodology should follow this structure:

1. Select temperature-based Polymarket contracts with clear settlement rules.
2. Retrieve Polymarket market metadata and price histories.
3. Retrieve relevant weather forecasts and realised temperature data.
4. Convert weather forecasts into local predictive temperature distributions.
5. Convert predictive distributions into contract probabilities.
6. Compare model probabilities with Polymarket-implied probabilities.
7. Evaluate probability quality using Brier score, log score and calibration analysis.
8. Test whether model-market discrepancies generate useful paper-trading signals.

A simple first post-processing model can be written as:

```text
T_obs = alpha_c + beta_c T_forecast + error
```

where `T_obs` is the realised temperature for city `c`, and the residual error distribution is used to transform a point forecast into an event probability.

For a threshold contract:

```text
P(Y = 1) = P(T_obs > threshold)
```

For a multi-outcome temperature-bin contract:

```text
P(a_j < T_obs <= b_j) = F(b_j) - F(a_j)
```

where `F` is the predictive cumulative distribution function.

---

## Key implications for the project

The literature implies five important project-design decisions:

1. The empirical work should begin with a narrow and clean market sample rather than all weather markets.
2. The main novelty should be the post-processing and probability-conversion layer, not necessarily training a global foundation model from scratch.
3. Probabilistic evaluation is essential because Polymarket contracts trade probabilities, not point forecasts.
4. Data alignment is a major methodological issue: forecast issue time, event date, settlement source, lead time and market price timestamp must be matched carefully.
5. Trading analysis should be treated as paper trading and should account for bid-ask spread, liquidity and model uncertainty.

---

## Immediate literature gaps to fill later

This initial matrix is sufficient for the first stage, but the full literature review should later add:

1. Prediction-market efficiency and market-implied probability literature.
2. Weather-forecast calibration and statistical post-processing literature.
3. Proper scoring rules and probabilistic forecast evaluation.
4. Market microstructure issues for prediction markets, including bid-ask spread and liquidity.
5. Weather derivatives or weather-linked financial instruments as an optional extension.

