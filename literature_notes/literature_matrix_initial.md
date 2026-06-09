# Initial Literature Matrix

| Paper / source | Main contribution | Relevance to this project | How it may be used |
|---|---|---|---|
| GraphCast | Graph neural network model for global medium-range weather forecasting. | Relevant for global AI weather modelling and graph-based spatial structure. | Literature review; possible motivation for global-local forecast modelling. |
| FourCastNet | Fast high-resolution global weather forecasting using Adaptive Fourier Neural Operators. | Relevant for fast AI forecasting and possible ensemble generation. | Literature review; discussion of AI weather model efficiency. |
| AIFS-CRPS | Probabilistic ensemble forecasting model trained using a CRPS-based objective. | Highly relevant because the project requires probabilistic forecasts, not only point forecasts. | Main reference for probabilistic weather forecasting and scoring rules. |
| Aurora | Foundation model for the Earth system, adaptable to multiple forecasting tasks. | Useful for discussing modern foundation-model approaches to environmental forecasting. | Literature review and possible extension. |
| HEFTCom2024 competition summary | Forecasting and trading competition linking weather forecasts to energy trading decisions. | Closest analogue to this project's forecast-to-trading pipeline. | Methodological reference for forecast evaluation and trading value. |
| HEFTCom2024 winning CatBoost model | Practical stacked CatBoost framework for probabilistic wind and solar forecasting. | Relevant for post-processing, model stacking and robust tabular forecasting. | Possible baseline or inspiration for post-processing weather forecasts into probabilities. |
| Polymarket API documentation | Market, price, order-book and trade data access. | Core data source for market-implied probabilities and trading backtests. | Data collection and market microstructure analysis. |
