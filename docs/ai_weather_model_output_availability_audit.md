# AI Weather-Model Output Availability Audit

## Purpose

This note screens whether outputs from modern AI weather models and related forecast sources are practically usable for the Polymarket weather-trading dissertation.

The aim at this stage is not to train or run all models from scratch. The aim is to identify which sources can provide usable forecast outputs, especially 2m temperature forecasts with clear run time, valid time and lead time. The output of this audit will help decide which forecast sources should enter the empirical pipeline.

The target empirical use case is:

`forecast source -> 2m temperature forecast -> city-level daily maximum forecast -> predictive distribution -> Polymarket temperature-bin probabilities`

## Output availability table

| Source / model                           | Role in project                                          | Forecast type                                             | 2m temperature availability                                                                        | Historical forecast availability                                                                                    | Lead-time information                                                        | Access route                                                                            | Can be used without running model?                                                   | Difficulty     | Current verdict                                   | Possible dissertation use                                                                                        |
| ---------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | -------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| ECMWF AIFS Single                        | Main AI-weather candidate                                | Deterministic AI forecast                                 | Likely available through ECMWF open forecast products                                              | Real-time / recent open data appears more accessible than full historical archive                                   | Forecast run time and forecast step should be available                      | ECMWF Open Data / `ecmwf-opendata` package / ECMWF data endpoints                       | Yes, if forecast fields can be downloaded directly                                   | Medium         | High-priority source to test next                 | Strong candidate to replace or complement Open-Meteo as the main AI forecast source                              |
| ECMWF AIFS ENS                           | Main probabilistic AI-weather candidate                  | Ensemble AI forecast                                      | Likely available through ECMWF AIFS ensemble products                                              | Real-time / recent open data appears more accessible than full historical archive                                   | Forecast run time, ensemble structure and forecast steps should be available | ECMWF Open Data / AIFS ENS product pages / ECMWF APIs                                   | Yes, if ensemble forecast fields can be downloaded directly                          | Medium to high | Very important, but needs retrieval test          | Potentially strongest source because ensemble forecasts can directly support probability distributions           |
| ECMWF IFS Open Data                      | Traditional NWP benchmark                                | Deterministic / ensemble numerical forecast               | Available for standard ECMWF forecast products                                                     | Rolling open-data archive; full historical access may require other ECMWF routes                                    | Forecast run time and forecast step available                                | ECMWF Open Data / AWS / `ecmwf-opendata`                                                | Yes                                                                                  | Medium         | Strong benchmark source                           | Useful traditional benchmark against AI-weather models                                                           |
| Open-Meteo Previous Runs                 | Practical forecast-data baseline                         | Forecast API with fixed lead-time variables               | Available for `temperature_2m`                                                                     | Historical previous-run variables available for recent years and fixed lead times                                   | Very convenient: previous_day1 to previous_day7                              | Open-Meteo API                                                                          | Yes                                                                                  | Low            | Already usable                                    | Best immediate fallback for lead-time forecast-error estimation and pipeline testing                             |
| Open-Meteo ECMWF API                     | Convenient ECMWF-style API                               | Forecast API                                              | Available for `temperature_2m`                                                                     | Mainly current / short-horizon style API; historical availability depends on endpoint                               | Hourly forecast horizon available                                            | Open-Meteo API                                                                          | Yes                                                                                  | Low            | Useful practical source                           | Useful for quick ECMWF-style forecast retrieval without handling GRIB files                                      |
| GraphCast                                | Core literature and possible forecast source             | Deterministic AI forecast                                 | Model supports relevant atmospheric/surface variables, but usable output access needs checking     | Pretrained weights and examples are available; precomputed historical forecast archive may require separate sources | Lead-time structure exists in model output if run or if archive exists       | DeepMind repository / possible external hindcast datasets / ECMWF experimental products | Not necessarily; may require running model unless archive is found                   | Medium to high | Literature anchor plus output-availability check  | Important for framing modern AI weather models; empirical use depends on finding downloadable outputs            |
| FourCastNet / NVIDIA Earth-2 FourCastNet | Core literature and possible forecast source             | Deterministic / ensemble AI forecast depending on product | FourCastNet-style systems include surface variables such as 2m temperature in some implementations | Availability depends on NVIDIA Earth-2 / NIM access or other public products                                        | Forecast steps generally available                                           | NVIDIA Earth-2 / NGC / NIM API / possible open implementations                          | Possibly, if API or precomputed product is accessible                                | Medium to high | Needs access check                                | Useful if inference/API access is available; otherwise literature/model-comparison anchor                        |
| Pangu-Weather                            | Core literature and possible forecast source             | Deterministic AI forecast                                 | Model supports global weather forecasting; exact output access needs testing                       | Official repositories/checkpoints exist, but precomputed city-level outputs are not immediately obvious             | Forecast steps exist if model is run                                         | Official repository / ECMWF AI-models plugin / checkpoints                              | Possibly not; may require running model                                              | High           | Mostly literature unless output route is found    | Useful as a benchmark in the literature review; empirical use depends on whether outputs can be accessed cheaply |
| Aurora                                   | Foundation-model literature and possible forecast source | Foundation model with specialised weather versions        | Predicts atmospheric variables including temperature                                               | Public code/model access exists, but precomputed historical output availability needs checking                      | Forecast-task dependent                                                      | Microsoft Aurora repository / documentation                                             | Possibly, if model/inference examples are easy to run; precomputed output less clear | Medium to high | Strong literature anchor; empirical use uncertain | Useful for explaining foundation-model direction and post-processing relevance                                   |
| Windy API                                | Practical weather API source                             | Multi-model point forecast API                            | Temperature available through point forecast API                                                   | Historical availability uncertain; likely more useful for current/future forecasts                                  | Forecast timeline available                                                  | Windy Point Forecast API                                                                | Yes, but requires API access/key                                                     | Medium         | Useful if API access is available                 | Practical forecast source, especially if Wei recommends it                                                       |
| Hong Kong Observatory                    | Exact realised source for Hong Kong contracts            | Realised weather observation / daily extract              | Daily maximum temperature available in contract-relevant form if retrievable                       | Historical daily data likely available through HKO pages or downloads                                               | Not a forecast source                                                        | HKO website / data pages                                                                | Yes                                                                                  | Medium         | High-priority realised-data source                | Needed to replace Open-Meteo proxy realised values for Hong Kong                                                 |
| Wunderground station pages               | Exact realised source for some London / NYC contracts    | Realised station observation                              | Station-level temperature available if accessible                                                  | Historical station pages may be accessible, but automated retrieval uncertain                                       | Not a forecast source                                                        | Wunderground station pages                                                              | Yes, if retrievable                                                                  | Medium to high | Needs retrieval test                              | Needed for exact settlement matching for London / NYC contracts                                                  |

## Preliminary source ranking

### Most promising empirical sources

1. **ECMWF AIFS / AIFS ENS**
   These are the most important next sources to test because they are directly aligned with the AI-weather-model direction of the project. If 2m temperature forecasts can be downloaded with run time, valid time and lead time, AIFS can become the main AI forecast input.

2. **ECMWF IFS Open Data**
   This is a strong traditional numerical weather prediction benchmark. It can help separate the value of AI forecasts from the value of conventional NWP forecasts.

3. **Open-Meteo Previous Runs**
   This is already useful as a practical fallback. It provides easy lead-time forecast variables and is suitable for early pipeline development and forecast-error estimation.

4. **Windy API**
   This may be useful as a practical multi-model forecast source, especially if access is straightforward. It needs an API access check.

### Most important literature and methodology anchors

1. **GraphCast**
   Important for motivating global AI weather models and the idea of fast medium-range forecasting. Empirical use depends on whether downloadable forecast outputs or hindcast archives can be found.

2. **FourCastNet**
   Important for the Fourier neural operator approach and fast global forecasting. Empirical use depends on NVIDIA Earth-2 / API access or other accessible outputs.

3. **Pangu-Weather**
   Important deterministic AI-weather benchmark. Likely more useful as a literature anchor unless running the model or accessing precomputed outputs becomes feasible.

4. **Aurora**
   Important foundation-model reference. It helps frame the broader direction of Earth-system foundation models, but empirical use depends on available outputs or manageable inference.

### Exact realised-data sources

1. **Hong Kong Observatory**
   High priority for Hong Kong markets because it is contract-relevant.

2. **Wunderground station pages**
   High priority for London and New York examples where contracts refer to specific stations.

## Minimal AIFS-to-Polymarket feasibility mapping

If AIFS 2m temperature forecast fields can be retrieved, they can enter the existing Polymarket pipeline as follows:

1. Retrieve AIFS forecast field for 2m temperature.
2. Record forecast run time, valid time and lead time.
3. Extract the nearest grid point or interpolated forecast for the contract city / station.
4. Convert hourly or 6-hourly forecasts into a local-day daily maximum temperature forecast.
5. Estimate a predictive distribution around the forecast, initially using empirical forecast errors by city and lead time.
6. Map the predictive distribution into Polymarket temperature bins.
7. Compare model-implied probabilities with Polymarket YES prices.
8. Evaluate using Brier score, log score, calibration and later trading/backtest performance.

## Current findings

The most important next technical test is an AIFS / ECMWF retrieval attempt for 2m temperature. If AIFS or AIFS ENS output can be retrieved directly, it should become a leading candidate forecast source for the empirical work.

If AIFS retrieval is difficult, Open-Meteo Previous Runs remains a useful fallback for building the forecast-error and post-processing pipeline, while GraphCast, FourCastNet, Pangu-Weather, Aurora and AIFS-CRPS can still provide the main literature and methodological framing.

The current project should therefore proceed with two parallel tracks:

1. **Feasibility track:** test whether AIFS / ECMWF outputs can be downloaded and mapped to city-level daily maximum temperature.
2. **Pipeline track:** continue developing the generic forecast-to-probability-to-market-comparison pipeline using accessible forecast data.

## Questions to raise with supervisors

1. Should AIFS / AIFS ENS be prioritised as the first AI-weather-model output source?
2. Does ECMWF provide an easy route to retrieve AIFS 2m temperature forecasts by run time, valid time, lead time and location?
3. If historical AIFS output is difficult to access, is it acceptable to use Open-Meteo Previous Runs or ECMWF IFS-style forecasts for the empirical analysis while using GraphCast, FourCastNet, Pangu-Weather and Aurora mainly as methodological anchors?
4. Should the first empirical implementation use one city deeply, or should it use a small multi-city panel if global forecast data are available?
5. For the first post-processing model, should the focus be on bias correction and empirical forecast-error distributions before attempting more complex machine-learning post-processing?


