# First City Selection

## 1. Selection objective

The first empirical case should be chosen based on data quality, settlement clarity and implementation feasibility. The purpose is to build one complete and rigorous city-level pipeline before scaling to additional cities or weather contract types.

The first city must support the full research workflow:

weather forecast output  
→ official settlement source  
→ forecast issue time, valid time and lead time alignment  
→ Polymarket market price at the correct information time  
→ model implied probability  
→ market implied probability  
→ scoring and trading evaluation

The key selection principle is that one city should be made fully correct before the project is expanded. A broader multi-city dataset is valuable only after the first city pipeline has solved settlement matching, timestamp alignment, forecast extraction and probability evaluation.

## 2. Selection criteria

The first city is assessed using six criteria.

First, the Polymarket settlement rule should be explicit. The contract should clearly state the source used for resolution and the exact temperature variable used.

Second, the official realised temperature should be retrievable. The realised value must be accessible in a stable format, preferably through an official source, open data portal or reproducible download route.

Third, the settlement variable should be suitable for temperature threshold or temperature bin modelling. Daily maximum temperature is preferred because it maps naturally into threshold exceedance targets and Polymarket temperature bins.

Fourth, weather forecast data should be available for the location. The selected city should be compatible with AIFS, ECMWF, NVIDIA Earth 2 or other AI weather model outputs after spatial extraction or post processing.

Fifth, market data should be available through Polymarket. The event should provide market metadata, CLOB token IDs, market prices and historical price paths.

Sixth, the local time convention should be manageable. The target date, local day, forecast valid time and settlement date should be clearly defined to avoid look ahead bias.

## 3. Candidate cities

## 3.1 Hong Kong

Hong Kong is the strongest first candidate because the settlement source is clear and directly connected to an official weather authority. Recent Polymarket Hong Kong temperature markets resolve according to the highest temperature recorded by the Hong Kong Observatory, specifically the “Absolute Daily Max” in the relevant Daily Extract.

This is attractive for the dissertation because the official settlement source is not merely a third party weather website. It is the official Hong Kong weather authority. This makes the realised target more credible and reduces ambiguity in scoring and backtesting.

The method for using Hong Kong is to retrieve the official Hong Kong Observatory daily maximum temperature for the relevant settlement date, then align this value with the Polymarket event rule. For forecast inputs, global or gridded AI weather forecasts can be extracted around Hong Kong and post processed into an estimate of the official Hong Kong Observatory settlement temperature.

Hong Kong also fits Wei Pan’s suggested post processing idea. A global AI forecast for Hong Kong can be mapped into an estimated Hong Kong Observatory settlement temperature. The discrepancy between the broad forecast and the official local settlement temperature can then be modelled as a local post processing problem.

The expected result is a clean one city case where the project can demonstrate settlement source matching, lead time alignment and probability modelling without immediately adding the complexity of multiple cities.

The main limitation is that the Hong Kong Observatory data retrieval route still needs to be tested in code. The Polymarket rule and official data source appear suitable, but the retrieval process must be made reproducible.

## 3.2 London

London is a useful later candidate because Polymarket has temperature markets for London and the contract rules identify a specific station, usually London City Airport Station, with Wunderground as the resolution source.

The main advantage of London is that it is geographically familiar and has clear airport station weather records. It may also be useful for scaling because London temperature markets appear to have repeated contract structures.

The main limitation is that the realised settlement source is Wunderground rather than an official national meteorological data portal in the contract wording. Wunderground station pages may be suitable, but they may require more careful scraping, page parsing or manual verification. This makes London slightly less attractive as the first rigorous city.

London should therefore be kept as a second stage city after the Hong Kong pipeline works.

## 3.3 New York City

New York City is another useful scaling candidate because Polymarket temperature markets often specify LaGuardia Airport Station and use Wunderground as the resolution source. The station based rule is relatively clear and the market structure is similar to London.

The main advantage of New York is that station based airport data may be easy to interpret, and there may be many temperature contracts. This could be useful later for testing more markets, more thresholds and portfolio allocation.

The main limitation is similar to London. The first city should prioritise official settlement source clarity and reproducible realised data retrieval. Since New York markets rely on Wunderground station pages, additional work may be required to make the realised data extraction stable.

New York City should therefore be kept as a later scaling candidate, especially once the one city pipeline has been validated.

## 4. Comparison table

| Criterion | Hong Kong | London | New York City |
|---|---|---|---|
| Settlement source clarity | High | Medium to high | Medium to high |
| Source type | Hong Kong Observatory | Wunderground station page | Wunderground station page |
| Settlement variable | Official daily maximum temperature | Station daily highest temperature | Station daily highest temperature |
| Data retrieval expectation | Official data route likely available | Requires Wunderground handling | Requires Wunderground handling |
| Existing prototype relevance | High | Medium | Medium |
| Forecast extraction feasibility | High | High | High |
| Local post processing relevance | High | High | High |
| Recommended role | First city | Later scaling candidate | Later scaling candidate |

## 5. Selected first city

Hong Kong is selected as the first empirical city.

The rationale is that Hong Kong provides the cleanest first test of the full dissertation pipeline. The Polymarket resolution rule points to the Hong Kong Observatory and the relevant official temperature variable. This makes the realised target more credible than a proxy source and directly addresses the requirement to use exact settlement data.

The method is to construct the first rigorous city level dataset around Hong Kong. Each observation should include the contract slug, settlement date, official settlement source, realised official temperature, forecast model, forecast run time, forecast valid time, lead time, market price timestamp and Polymarket implied probability.

The expected result is a complete one city framework that can be extended later. Once Hong Kong works, London and New York can be added as additional cities using the same structure, with Wunderground station pages treated as settlement sources.

## 6. Implications for the next stage

The first implementation should focus on Hong Kong official settlement data rather than scaling immediately. The next empirical task is to retrieve the Hong Kong Observatory realised daily maximum temperature for the existing Hong Kong Polymarket example and verify that it matches the contract rule.

After the realised settlement source is retrieved, the time alignment framework should be applied. For each forecast, the market price should be sampled at the forecast issue time or at the first available market timestamp after the forecast becomes usable. This avoids comparing an earlier forecast with a later market price that may already contain additional information.

The first Hong Kong pipeline should therefore produce a table with the following fields:

contract slug  
city  
settlement date local  
settlement source  
official realised temperature  
forecast model  
forecast run time UTC  
forecast valid time UTC  
lead time hours  
target local date  
market price time UTC  
market implied probability  
model implied probability  
realised outcome

This structure will provide the foundation for supervised threshold classification, market discrepancy analysis and trading evaluation.

## 7. Conclusion

Hong Kong should be used as the first city because it has the strongest combination of settlement source clarity, official realised temperature relevance, existing prototype work and suitability for local post processing.

London and New York should remain important scaling candidates, but they should not be prioritised before the Hong Kong pipeline has solved settlement matching, time alignment, forecast extraction and probability evaluation.
