# 18d HKO Daily Extract Source Discovery Report

Run timestamp UTC: `20260709T135331Z`

Certified contracts: `5`

Target dates: `2026-06-08, 2026-07-08, 2026-07-09, 2026-07-10, 2026-07-11`


## Source routes tested

- CLMMAXT all-year HKO open-data endpoint.

- Candidate current-year CSDI/CIS CSV endpoints for maximum temperature.

- HKO Daily Extract HTML pages for each target month in English and Chinese.


## Candidate URL summary

|   status_code |   bytes | content_type                       | url                                                                                      |
|--------------:|--------:|:-----------------------------------|:-----------------------------------------------------------------------------------------|
|           200 |    4333 | application/octet-stream, text/csv | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKO_MAXT_2026.csv     |
|           200 |    2792 | application/octet-stream, text/csv | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKO_MAXT_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKO_MAX_TEMP_2026.csv |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKO_MAX_TEMP_2026.csv  |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKO_TMAX_2026.csv     |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKO_TMAX_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKO_MXT_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKO_MXT_2026.csv       |
|           200 |    4310 | application/octet-stream, text/csv | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_KP_MAXT_2026.csv      |
|           200 |    2770 | application/octet-stream, text/csv | https://data.weather.gov.hk/weatherAPI/cis/csvfile/KP/2026/daily_KP_MAXT_2026.csv        |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_KP_MAXT_2026.csv       |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_KP_MAX_TEMP_2026.csv  |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/KP/2026/daily_KP_MAX_TEMP_2026.csv    |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_KP_MAX_TEMP_2026.csv   |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_KP_TMAX_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/KP/2026/daily_KP_TMAX_2026.csv        |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_KP_TMAX_2026.csv       |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_KP_MXT_2026.csv       |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/KP/2026/daily_KP_MXT_2026.csv         |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_KP_MXT_2026.csv        |
|           200 |    4351 | application/octet-stream, text/csv | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKA_MAXT_2026.csv     |
|           200 |    2801 | application/octet-stream, text/csv | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKA/2026/daily_HKA_MAXT_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKA_MAXT_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKA_MAX_TEMP_2026.csv |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKA/2026/daily_HKA_MAX_TEMP_2026.csv  |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKA_MAX_TEMP_2026.csv  |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKA_TMAX_2026.csv     |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKA/2026/daily_HKA_TMAX_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKA_TMAX_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/hko_data/csdi/dataset/daily_HKA_MXT_2026.csv      |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKA/2026/daily_HKA_MXT_2026.csv       |
|           404 |      16 | text/html; charset=UTF-8           | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKA_MXT_2026.csv       |
|           200 |    2754 | application/octet-stream, text/csv | https://data.weather.gov.hk/weatherAPI/cis/csvfile/HKO/2026/daily_HKO_RF_2026.csv        |


## Daily Extract parse summary

| url                                                        |   tables_found |   parsed_rows | raw_path                                                                                 |
|:-----------------------------------------------------------|---------------:|--------------:|:-----------------------------------------------------------------------------------------|
| https://www.hko.gov.hk/en/cis/dailyExtract.htm?m=6&y=2026  |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_en_cis_dailyExtract.htm_m_6_y_2026.txt  |
| https://www.hko.gov.hk/en/cis/dailyExtract.htm?m=06&y=2026 |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_en_cis_dailyExtract.htm_m_06_y_2026.txt |
| https://www.hko.gov.hk/tc/cis/dailyExtract.htm?m=6&y=2026  |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_tc_cis_dailyExtract.htm_m_6_y_2026.txt  |
| https://www.hko.gov.hk/tc/cis/dailyExtract.htm?m=06&y=2026 |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_tc_cis_dailyExtract.htm_m_06_y_2026.txt |
| https://www.hko.gov.hk/en/cis/dailyExtract.htm?m=7&y=2026  |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_en_cis_dailyExtract.htm_m_7_y_2026.txt  |
| https://www.hko.gov.hk/en/cis/dailyExtract.htm?m=07&y=2026 |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_en_cis_dailyExtract.htm_m_07_y_2026.txt |
| https://www.hko.gov.hk/tc/cis/dailyExtract.htm?m=7&y=2026  |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_tc_cis_dailyExtract.htm_m_7_y_2026.txt  |
| https://www.hko.gov.hk/tc/cis/dailyExtract.htm?m=07&y=2026 |              0 |             0 | data/raw/hko_source_discovery_18d/www.hko.gov.hk_tc_cis_dailyExtract.htm_m_07_y_2026.txt |


## Target outcome candidates

| event_date   |   hko_tmax_C |   parse_route |   source_name |   source_route |   url | target_found   |
|:-------------|-------------:|--------------:|--------------:|---------------:|------:|:---------------|
| 2026-06-08   |          nan |           nan |           nan |            nan |   nan | False          |
| 2026-07-08   |          nan |           nan |           nan |            nan |   nan | False          |
| 2026-07-09   |          nan |           nan |           nan |            nan |   nan | False          |
| 2026-07-10   |          nan |           nan |           nan |            nan |   nan | False          |
| 2026-07-11   |          nan |           nan |           nan |            nan |   nan | False          |


## Chosen event outcomes

| event_date   |   threshold_K |   hko_tmax_C |   Y_ge_K_18d |   source_route |   parse_route |   source_name |
|:-------------|--------------:|-------------:|-------------:|---------------:|--------------:|--------------:|
| 2026-06-08   |            34 |          nan |          nan |            nan |           nan |           nan |
| 2026-07-08   |            35 |          nan |          nan |            nan |           nan |           nan |
| 2026-07-09   |            35 |          nan |          nan |            nan |           nan |           nan |
| 2026-07-10   |            36 |          nan |          nan |            nan |           nan |           nan |
| 2026-07-11   |            39 |          nan |          nan |            nan |           nan |           nan |


## Interpretation

No official HKO realised maximum temperature was recovered for the certified event dates. The certified market and price panels remain valid, but strict realised-weather scoring remains pending source discovery or later HKO publication.
