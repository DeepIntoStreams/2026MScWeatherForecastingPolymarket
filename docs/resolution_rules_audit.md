# Resolution Rules Audit

## Purpose

This note verifies the settlement rules for three representative Polymarket temperature markets. The purpose is to ensure that the realised temperature target used in the dissertation matches the exact source and definition used by Polymarket.

This is important because the project is not simply forecasting “city temperature”. Each contract resolves according to a specific source, station, unit, precision rule and revision rule. These details determine the correct target variable for model evaluation and trading backtests.

---

## Summary table

| Market                                       | City          | Event date | Settlement source                   | Station / location                | Temperature variable                                  | Unit       | Precision                | Revision / timing rule                                                                                 | Modelling implication                                                                                                    |
| -------------------------------------------- | ------------- | ---------: | ----------------------------------- | --------------------------------- | ----------------------------------------------------- | ---------- | ------------------------ | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Highest temperature in Hong Kong on June 10? | Hong Kong     | 2026-06-10 | Hong Kong Observatory Daily Extract | Hong Kong Observatory             | Absolute Daily Max                                    | Celsius    | 1 decimal place          | Cannot resolve until data is published; revisions after initial publication are ignored                | Forecast target should be daily maximum temperature at the HKO-reported location/source, not a generic city average      |
| Highest temperature in London on June 10?    | London        | 2026-06-10 | Wunderground                        | London City Airport Station, EGLC | Highest temperature recorded for all times on the day | Celsius    | Whole degrees Celsius    | Cannot resolve until first data point for following date is published                                  | Forecast target should be London City Airport, not wider London or generic Met Office London temperature                 |
| Highest temperature in NYC on June 9?        | New York City | 2026-06-09 | Wunderground                        | LaGuardia Airport Station, KLGA   | Highest temperature recorded for all times on the day | Fahrenheit | Whole degrees Fahrenheit | Revisions considered until first data point for following date is published; later alterations ignored | Forecast target should be LaGuardia Airport station temperature; forecast data may need Celsius-to-Fahrenheit conversion |

---

## Market 1: Highest temperature in Hong Kong on June 10?

### Verified rule

This market resolves to the temperature range containing the highest temperature recorded by the Hong Kong Observatory in degrees Celsius on 10 June 2026.

The resolution source is the Hong Kong Observatory, specifically the `Absolute Daily Max (deg. C)` field in the relevant `Daily Extract`.

The source measures temperature in Celsius to one decimal place. This is the precision used for market resolution.

The market cannot resolve until the data for the date has been published. Revisions after the temperature is initially published are not considered for resolution.

### Key modelling implication

The realised target should be the Hong Kong Observatory daily maximum temperature, not a generic Hong Kong city temperature and not a reanalysis grid-cell average.

Because the settlement value is measured to one decimal place, model probabilities should be mapped carefully into the market’s discrete outcome bins. For example, if the market bin is `30°C`, the exact interpretation of the bin boundary should be checked before final modelling.

---

## Market 2: Highest temperature in London on June 10?

### Verified rule

This market resolves to the temperature range containing the highest temperature recorded at the London City Airport Station in degrees Celsius on 10 June 2026.

The resolution source is Wunderground, specifically the highest temperature recorded for all times on the day for the London City Airport Station, station code `EGLC`.

The source measures temperature to whole degrees Celsius. This is the precision used for market resolution.

The market cannot resolve until the first data point for the following date has been published on the resolution source.

### Key modelling implication

The realised target should be the London City Airport Station daily maximum, not the average temperature across London and not necessarily the official Met Office London-wide value.

This matters because London City Airport may have station-specific effects. A global model grid point or a generic London forecast may need local post-processing to match the settlement source.

---

## Market 3: Highest temperature in NYC on June 9?

### Verified rule

This market resolves to the temperature range containing the highest temperature recorded at the LaGuardia Airport Station in degrees Fahrenheit on 9 June 2026.

The resolution source is Wunderground, specifically the highest temperature recorded for all times on the day for the LaGuardia Airport Station, station code `KLGA`.

The source measures temperatures to whole degrees Fahrenheit. This is the precision used for market resolution.

Revisions to temperatures recorded within the market’s timeframe are considered until the first data point for the following date has been published. After that, later alterations are not considered.

### Key modelling implication

The realised target should be the LaGuardia Airport daily maximum temperature. Because many weather forecast APIs provide Celsius by default, forecasts may need to be converted to Fahrenheit before mapping into the contract’s outcome bins.

The Fahrenheit bin structure also differs from the Celsius markets. For example, NYC markets may use two-degree Fahrenheit bins such as `80-81°F`, while Hong Kong and London markets may use one-degree Celsius bins. This affects the probability-conversion step.

---

## Cross-market methodological lessons

The resolution audit shows that the project must treat each Polymarket contract as a precisely defined derivative on a settlement source, not merely as a general weather forecast.

Three issues are especially important:

1. **Source matching**: the realised target must match the Polymarket settlement source.
2. **Station matching**: London and NYC resolve to airport stations, so local station-level post-processing may be necessary.
3. **Precision and bin mapping**: Hong Kong uses one decimal place in Celsius, London uses whole degrees Celsius, and NYC uses whole degrees Fahrenheit.

This has direct implications for the thesis methodology. The pipeline should be:

forecast source
→ local station / settlement-source adjustment
→ predictive temperature distribution
→ contract-specific bin probabilities
→ comparison with Polymarket-implied probabilities
→ scoring-rule evaluation and paper-trading backtest.

---

## Consequences for data collection

For each future market, the project should record:

* market name;
* city;
* event date;
* settlement source;
* station or location;
* temperature variable;
* unit;
* precision;
* revision rule;
* outcome bins;
* market URL;
* API identifiers;
* price history availability.

The next step is to automate retrieval of Polymarket market metadata and prices through the API, while keeping this settlement-rule audit as the manual quality-control layer.

