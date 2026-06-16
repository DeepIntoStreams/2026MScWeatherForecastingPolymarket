# AI Weather Model Review and Selection

## 1. Project requirements for model selection

The selected weather models must support the dissertation’s empirical objective: producing probability estimates for weather prediction market events and comparing these estimates with market implied probabilities. Temperature threshold and temperature bin contracts require forecasts that can be linked to official settlement temperatures, forecast issue times, forecast valid times, lead times and market price timestamps.

The first requirement is relevance to modern data driven weather forecasting. The dissertation should demonstrate understanding of the main referenced model families, including global neural weather models, probabilistic or ensemble based models, and foundation model approaches. Model selection should therefore be based on both methodological relevance and practical usability.

The second requirement is availability of variables relevant to prediction market contracts. For the current temperature based scope, the selected models must provide, or support the extraction of, 2 metre temperature forecasts or closely related surface temperature variables.

The third requirement is time consistency. Model outputs should be traceable by forecast run time, issue time, valid time and lead time. This is essential because model implied probabilities must be compared with Polymarket prices observed at the same information time. A forecast issued at 12:00 UTC on 11 June should not be compared with a market price observed after the market has already incorporated later information.

The fourth requirement is practical implementation. A model may be academically important but unsuitable as a core empirical model if it cannot be accessed, run, or used within the dissertation time frame. The selected models should therefore have a realistic implementation route through open data, public code, cloud notebooks, or documented inference tools.

The fifth requirement is probabilistic usefulness. Polymarket contracts are priced as probabilities of future events. A selected model should either provide probabilistic or ensemble forecasts directly, or provide forecast features that can be used in a supervised post processing model for threshold exceedance probabilities.

The sixth requirement is suitability for settlement specific post processing. The final empirical target is not merely a generic city forecast, but a probability forecast for the official settlement source used by a contract. The selected model outputs should therefore be suitable inputs for a post processing layer that maps broad or global forecasts into settlement specific local probabilities.

## 2. Candidate model review

## 2.1 AIFS, AIFS ENS and AIFS CRPS

AIFS is ECMWF’s Artificial Intelligence Forecasting System. It is highly relevant because it is an operational machine learning weather forecasting system connected to ECMWF’s forecasting infrastructure. It has direct practical value for this dissertation because ECMWF forecast fields can be linked to forecast run time, valid time, lead time and meteorological variables such as 2 metre temperature.

AIFS Single provides deterministic forecasts. Its main role in the dissertation is as a raw AI weather benchmark. A deterministic AIFS forecast can be compared with official settlement temperature after spatial extraction, time alignment and local post processing. This gives a clear baseline: the performance of a modern AI weather model before any dissertation specific correction is applied.

AIFS ENS and AIFS CRPS are more directly linked to probability forecasting. AIFS ENS provides an ensemble direction, while the CRPS based literature emphasises probabilistic skill and proper scoring. This is particularly important because Polymarket contracts require probabilities rather than point forecasts. If ensemble members are accessible, threshold exceedance probabilities can be estimated directly from the proportion of ensemble members exceeding the contract threshold. This is more defensible than imposing an arbitrary Gaussian residual distribution on a point forecast.

The rationale for using AIFS is therefore threefold. First, it provides a modern AI weather forecast source with strong institutional and scientific credibility. Second, it can provide 2 metre temperature forecast fields that match the current temperature market scope. Third, its ensemble or probabilistic variants provide a natural benchmark for probability forecasting.

The proposed method is to use AIFS Single as a raw deterministic forecast benchmark and AIFS ENS, where available, as a direct probabilistic benchmark. AIFS outputs can also be used as input features in the supervised post processing model. For example, the classifier may use AIFS forecast temperature, lead time, forecast run hour, recent official settlement observations and seasonal variables to estimate the probability that the official settlement temperature exceeds a contract threshold.

The expected result is a benchmark that is both scientifically meaningful and practically usable. AIFS should provide the main empirical reference point for testing whether local post processing improves probability forecasts relative to raw AI weather forecasts.

## 2.2 NVIDIA Earth 2 and FourCastNet

NVIDIA Earth 2 and FourCastNet are important because they provide a distinct implementation route for neural weather forecasting. FourCastNet is based on Adaptive Fourier Neural Operators and was designed to produce fast global forecasts at high spatial resolution. It is relevant to the dissertation because it represents a different model architecture from AIFS and has public implementation routes through NVIDIA related tools, repositories and examples.

The rationale for considering NVIDIA Earth 2 and FourCastNet is that the dissertation should demonstrate technical understanding and implementation ability, rather than only retrieving precomputed forecasts. A public or cloud based implementation route makes this model family suitable for a feasibility test using Google Colab or another GPU enabled environment. If a minimal inference example can be run, the model can support the dissertation’s requirement to demonstrate practical use of an AI weather model.

The method is to evaluate whether NVIDIA Earth 2 or FourCastNet can produce usable forecast features for the selected city and contract type. The most useful output for the current scope would be 2 metre temperature or a closely related surface temperature forecast. If direct probabilistic output is not available, the model can still contribute as a second raw forecast benchmark and as an input source for the supervised post processing classifier.

The expected result is a second model route that strengthens the project’s technical component. AIFS provides the strongest operational and probabilistic route, while NVIDIA Earth 2 or FourCastNet provides a complementary architecture and implementation route. This combination gives the dissertation both practical forecast access and evidence of engagement with model implementation.

The main limitation is computational feasibility. NVIDIA Earth 2 or FourCastNet may require GPU resources, package setup, model weights or specific input data. Therefore, its final role should be determined by a feasibility test. If runnable inference is feasible, it should serve as the second selected model. If the implementation proves too heavy within the dissertation time frame, it should remain a carefully reviewed model and implementation feasibility component, while another accessible model can be used as the second empirical benchmark.

## 2.3 GraphCast

GraphCast is a graph neural network model for global medium range weather forecasting. It uses a learned graph representation of the Earth system and produces global forecasts across multiple atmospheric and surface variables. It is one of the most influential modern AI weather models and is therefore important for the literature review.

GraphCast is relevant because it includes variables such as 2 metre temperature and can produce forecasts at lead times suitable for prediction market analysis. It also has official code and pretrained resources, which makes it a possible implementation route.

The main limitation is that GraphCast is primarily deterministic. A deterministic forecast does not directly produce the probability required for a Polymarket threshold contract. To use GraphCast in this dissertation, the output would need to enter a post processing model or be converted into probability through a carefully justified method. This makes it less immediately attractive than AIFS ENS for direct probability benchmarking.

GraphCast should therefore be treated as a major literature model and possible implementation fallback. It is highly relevant for explaining the development of graph based AI weather forecasting, but it is not the first selected model because the current project requires a direct route to probability estimation and settlement specific post processing.

## 2.4 Pangu Weather

Pangu Weather is a 3D neural network model for medium range global weather forecasting. It is relevant because it demonstrates the use of deep learning architectures that model atmospheric variables in three dimensions. This makes it an important comparison point for AI weather model design, especially in relation to vertical atmospheric structure and medium range forecast skill.

For this dissertation, Pangu Weather is useful in the literature review because it shows how neural models can compete with traditional numerical weather prediction systems. It is relevant to temperature forecasting and therefore to weather prediction markets.

However, its role as a core empirical model is less compelling than AIFS or NVIDIA Earth 2. It is mainly a deterministic model, and its use for threshold probabilities would still require a post processing layer. It may also involve heavier implementation requirements than the current first stage of the project allows.

Pangu Weather should therefore be reviewed as an important model in the AI weather literature, but not selected as one of the first two empirical models unless the selected implementation routes become infeasible.

## 2.5 Aurora

Aurora is a foundation model for the Earth system. It is broader than a single weather forecasting model because it is designed to support multiple Earth system tasks through pretraining and adaptation. This foundation model direction is important because it shows how weather forecasting is moving from specialised models towards more general pretrained systems.

Aurora is conceptually relevant to the dissertation because the project also requires adaptation from broad forecasts to a specific downstream target: the official settlement temperature of a prediction market contract. The foundation model idea supports the broader motivation for post processing and task specific adaptation.

The main limitation is that Aurora may be too broad for the first empirical pipeline. The current project requires a reliable one city probability forecasting system before extending into broader foundation model experiments. Aurora should therefore be included in the literature review as an important modern model and potential extension, but it should not be selected as one of the first two empirical models.

## 3. Model selection summary table

| Model                          | Forecast type                                                    | Temperature relevance | Practical route                                | Probability usefulness                       | Project role                           |
| ------------------------------ | ---------------------------------------------------------------- | --------------------- | ---------------------------------------------- | -------------------------------------------- | -------------------------------------- |
| AIFS, AIFS ENS and AIFS CRPS   | Deterministic and ensemble or probabilistic directions           | High                  | ECMWF forecast fields and GRIB processing      | High if ensemble members are accessible      | Selected as Model 1                    |
| NVIDIA Earth 2 and FourCastNet | Fast neural global forecasting with public implementation routes | High                  | GitHub, Earth2Studio, Colab or related tooling | Medium to high, depending on feasible output | Provisional Model 2                    |
| GraphCast                      | Deterministic graph neural network forecast                      | High                  | Official code and pretrained resources         | Medium, requires post processing             | Literature model and possible fallback |
| Pangu Weather                  | Deterministic 3D neural forecast                                 | High                  | Public implementation routes exist             | Medium, requires post processing             | Literature model and possible fallback |
| Aurora                         | Earth system foundation model                                    | High conceptually     | Public resources exist, but broader scope      | Medium, mainly conceptual for this project   | Literature model and extension         |

## 4. Selected models and justification

The selected model direction is:

Model 1: AIFS, with AIFS ENS or AIFS CRPS related probabilistic output where accessible.

Model 2: NVIDIA Earth 2 or FourCastNet, subject to feasibility testing in a GPU enabled environment.

AIFS is selected as the first model because it best satisfies the dissertation’s core empirical requirements. The rationale is that AIFS is a modern AI forecasting system with a realistic route to obtaining forecast fields, including 2 metre temperature. Its outputs can be aligned with forecast run time, valid time and lead time, which is essential for avoiding look ahead bias in the comparison with Polymarket prices. AIFS also has a natural connection to probabilistic forecasting through AIFS ENS and the CRPS based probabilistic literature. This makes it more suitable than a purely deterministic model for a project where the final object of interest is a probability.

The method for using AIFS is to treat AIFS Single as a raw deterministic benchmark and AIFS ENS as a direct probabilistic benchmark where accessible. AIFS forecast variables will also be used as features in the supervised post processing model. This structure separates three different roles: raw forecast performance, direct probabilistic forecast performance and settlement specific post processed probability performance.

The expected result is a scientifically credible baseline and a practical source of forecast features. If post processing improves on raw AIFS or AIFS ENS probabilities, the dissertation can show that local settlement specific modelling adds value beyond retrieving a modern AI weather forecast.

NVIDIA Earth 2 or FourCastNet is selected provisionally as the second model because it provides a complementary implementation route and a different model architecture. The rationale is that the dissertation should not depend entirely on one operational forecast source. FourCastNet’s neural operator structure and NVIDIA’s public tooling make this model family a strong candidate for demonstrating technical understanding and implementation ability. This responds directly to the requirement that the project should show how selected models are used, rather than simply report downloaded outputs.

The method for using NVIDIA Earth 2 or FourCastNet is to test whether a minimal inference or example workflow can be run in a GPU enabled environment such as Google Colab. If feasible, the resulting output will be used either as a second raw forecast benchmark or as an additional feature set in the supervised threshold exceedance model. If direct probabilistic output is available, it can also be evaluated as a probability benchmark. If only point forecast output is available, it will be used as a deterministic forecast feature rather than as a final probability model.

The expected result is a second model route that strengthens the technical contribution of the dissertation. AIFS provides operational accessibility and probabilistic relevance, while NVIDIA Earth 2 or FourCastNet provides an implementation oriented neural weather model route. Together, these two models provide a balanced selection: one model is selected for practical and probabilistic strength, while the other is selected for architectural diversity and implementation value.

GraphCast, Pangu Weather and Aurora remain important for the literature review. They explain the wider development of AI weather forecasting and help justify why AIFS and NVIDIA Earth 2 or FourCastNet are selected. GraphCast is the strongest fallback because of its influence and public code availability. Pangu Weather is important for understanding 3D neural forecasting. Aurora is important for understanding the foundation model direction. However, none of these three is selected as the first empirical model because the project’s first priority is a feasible, settlement aligned, probability producing pipeline.

## 5. Use of the selected models in the dissertation pipeline

The preferred pipeline should be:

AI weather forecast outputs
→ official settlement source data
→ supervised post processing model
→ threshold exceedance probabilities
→ comparison with market implied probabilities
→ trading and robustness evaluation

This structure avoids relying on arbitrary probability assumptions. In the earlier prototype, a point forecast was converted into a probability distribution using an assumed residual distribution. That approach is useful for illustrating the mechanics of probability mapping, but it is not sufficient as the final methodology unless the residual assumptions are estimated, verified and calibrated.

The selected models enter the pipeline in three ways.

First, raw model forecasts provide benchmark forecasts. AIFS Single and NVIDIA Earth 2 or FourCastNet outputs can be compared with the official settlement temperature to evaluate the accuracy of raw AI weather forecasts.

Second, probabilistic or ensemble outputs provide direct probability benchmarks where accessible. AIFS ENS is the most natural candidate for this role. For a threshold contract, the exceedance probability can be estimated from the ensemble distribution if ensemble members are available.

Third, selected model outputs become features in the supervised post processing model. The main target is the probability that the official settlement temperature exceeds a contract threshold. The model can be written conceptually as:

P(T official > threshold | AI forecast features, lead time, recent official observations, seasonal variables)

This target is directly aligned with binary temperature threshold contracts. If the contract is a multi bin temperature market, the same framework can be extended to bin classification.

The rationale for this approach is that the official settlement temperature is local and contract specific, while global AI forecasts are broader model outputs. A post processing layer is therefore needed to translate global or gridded forecasts into settlement specific probability estimates. This is also where the dissertation’s original contribution is located.

The expected result is a probability forecasting framework that can be compared with Polymarket prices at the correct information time. If the supervised post processed probabilities differ from market implied probabilities and produce better scoring or trading outcomes, the project can evaluate whether AI weather forecasts contain information that is not fully reflected in the market.

## 6. Proposed modelling structure

The main supervised learning target should initially be binary threshold exceedance:

y = 1{T official > threshold}

Examples include:

T official > 25°C

T official > 26°C

T official > 27°C

If sufficient data are available, the target can be extended to temperature bin classification:

y = official temperature bin

The input features may include:

raw AIFS forecast temperature;

AIFS ENS summary statistics if available;

NVIDIA Earth 2 or FourCastNet forecast temperature if feasible;

forecast lead time;

forecast run hour;

recent official settlement source temperatures;

seasonality variables;

forecast changes between runs;

other weather variables if available and justified.

The modelling sequence should start with simple and interpretable benchmarks before moving to more complex methods. A suitable sequence is:

climatological benchmark;

raw AI forecast threshold benchmark;

logistic regression;

tree based classifier;

neural network model if data size and feature richness justify the additional complexity.

This order is methodologically appropriate because it separates the value of AI forecast features from the value of the supervised post processing layer. It also avoids introducing model complexity before establishing a reliable baseline.

## 7. Benchmarks

The empirical analysis should compare several probability sources.

The first benchmark is the market implied probability from Polymarket prices. This represents the market’s assessment at a given information time.

The second benchmark is the raw AI forecast. For deterministic outputs, this may be evaluated as a threshold signal or as an input to a simple benchmark probability model.

The third benchmark is a direct probabilistic or ensemble forecast where available, such as AIFS ENS exceedance probabilities.

The fourth model is the supervised post processing classifier. This is the dissertation’s main modelling contribution because it maps AI forecast features and settlement source information into contract specific probabilities.

The fifth benchmark is a trading benchmark, such as no trade, raw AI based trading or market implied probability only.

This benchmark structure allows the dissertation to answer four questions. First, whether raw AI forecasts are informative for settlement temperatures. Second, whether direct probabilistic AI forecasts are well calibrated for contract thresholds. Third, whether supervised post processing improves probability forecasts. Fourth, whether model market discrepancies translate into robust trading performance after market frictions.

## 8. Main risks and mitigation

The first risk is that NVIDIA Earth 2 or FourCastNet may be computationally heavy. This is mitigated by testing feasibility in a GPU enabled environment and using a minimal runnable workflow rather than attempting to train a global model from scratch.

The second risk is that AIFS ENS historical data may not be available for the full Polymarket sample. This is mitigated by using AIFS Single or available ECMWF forecast fields as benchmark inputs, while clearly separating direct probabilistic benchmarks from the supervised post processing model.

The third risk is that one city may not provide enough observations for a robust supervised learning model. This is mitigated by starting with one city to make settlement, timing and data handling correct, then scaling to more thresholds, more dates or one additional city once the pipeline works.

The fourth risk is poor probability calibration. This is mitigated by reporting proper scoring rules and calibration diagnostics, including Brier score, log score and calibration tables.

The fifth risk is unstable trading performance. This is mitigated by using conservative trading rules, transaction cost buffers, liquidity filters, out of sample testing and benchmark comparisons.

## 9. Current model selection conclusion

AIFS, with AIFS ENS or AIFS CRPS related probabilistic output where accessible, is selected as the primary AI weather model route. It provides the strongest combination of practical accessibility, temperature relevance, lead time structure and probabilistic potential.

NVIDIA Earth 2 or FourCastNet is selected as the provisional second route. It provides architectural diversity, implementation value and a credible route for demonstrating technical understanding through public tools or GPU based examples.

GraphCast, Pangu Weather and Aurora remain central literature review models. They provide the broader context for graph based forecasting, 3D neural weather forecasting and foundation model approaches. Their main role is to support the model selection rationale and provide fallback or extension options if implementation feasibility changes.

This selection supports the final dissertation structure: direct AI weather forecasts and probabilistic forecasts are used as benchmarks, while the supervised post processing classifier provides the project’s original probability forecasting contribution.
