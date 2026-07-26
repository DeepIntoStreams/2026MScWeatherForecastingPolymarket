# 18j v2 contract-event parsing fix

Generated: `2026-07-14 22:24:17 UTC`

## Purpose

This patch fixes the two parsing errors found in the first 18j output. The first 18j correctly identified a large HKO Daily Extract one-decimal family, but it used `groupItemThreshold` as if it were the Celsius boundary and sometimes used closing/resolution dates instead of the contract date. In this v2 output, Celsius boundaries are parsed from visible labels, questions and slugs, while the contract date is parsed from the market slug/question. `groupItemThreshold` is retained only as metadata because it is often an ordinal group index.

## Correct event-set convention

- `K°C or higher` is mapped to `[K, infinity)`, i.e. `T_HKO >= K`.

- Interior `k°C` is mapped to `[k, k+1)`, i.e. `k <= T_HKO < k+1`.

- Lower endpoint `k°C or below` is mapped to `(-infinity, k+1)` under the HKO one-decimal floor-bin family, because the market rule states that the outcome is the temperature range containing the one-decimal HKO value.

## Validation checks

| check | value |
| --- | --- |
| input_rows | 901 |
| v2_audited_rows | 901 |
| v2_admissible_hko_event_contract_rows | 803 |
| v2_hko_lower_tail_endpoint_rows | 73 |
| v2_hko_interior_bin_rows | 657 |
| v2_hko_upper_tail_rows | 73 |
| rows_with_corrected_dates | 810 |
| rows_with_corrected_event_sets | 891 |
| rows_where_groupItemThreshold_is_ordinal_not_celsius | 810 |
| admissible_rows_with_validation_issues | 0 |
| march13_rows_after_contract_date_fix | 10 |
| march13_hko_admissible_rows | 0 |
| march13_wunderground_airport_rows | 9 |


## Settlement-family summary

| settlement_family | contracts | admissible_hko_event_contracts_v2 | token_valid_v2 | date_corrected | event_set_corrected |
| --- | --- | --- | --- | --- | --- |
| HKO_Daily_Extract_one_decimal | 803 | 803 | 803 | 792 | 793 |
| ambiguous_or_unknown | 80 | 0 | 0 | 0 | 80 |
| Wunderground_or_airport | 18 | 0 | 18 | 18 | 18 |


## Contract-event-type summary

| contract_event_type_v2 | settlement_family | contracts | admissible_hko_event_contracts_v2 |
| --- | --- | --- | --- |
| interior_bin | HKO_Daily_Extract_one_decimal | 657 | 657 |
| lower_tail_endpoint | HKO_Daily_Extract_one_decimal | 73 | 73 |
| upper_tail | HKO_Daily_Extract_one_decimal | 73 | 73 |
| unknown | ambiguous_or_unknown | 80 | 0 |
| interior_bin | Wunderground_or_airport | 14 | 0 |
| lower_tail_endpoint | Wunderground_or_airport | 2 | 0 |
| upper_tail | Wunderground_or_airport | 2 | 0 |


## Contract-date summary preview

| event_date | admissible_contracts | lower_tail_endpoints | interior_bins | upper_tails |
| --- | --- | --- | --- | --- |
| 2026-03-16 | 11 | 1 | 9 | 1 |
| 2026-03-17 | 11 | 1 | 9 | 1 |
| 2026-03-18 | 11 | 1 | 9 | 1 |
| 2026-03-19 | 11 | 1 | 9 | 1 |
| 2026-03-21 | 11 | 1 | 9 | 1 |
| 2026-03-22 | 11 | 1 | 9 | 1 |
| 2026-03-23 | 11 | 1 | 9 | 1 |
| 2026-03-24 | 11 | 1 | 9 | 1 |
| 2026-03-25 | 11 | 1 | 9 | 1 |
| 2026-03-26 | 11 | 1 | 9 | 1 |
| 2026-03-27 | 11 | 1 | 9 | 1 |
| 2026-03-28 | 11 | 1 | 9 | 1 |
| 2026-03-29 | 11 | 1 | 9 | 1 |
| 2026-03-30 | 11 | 1 | 9 | 1 |
| 2026-04-01 | 11 | 1 | 9 | 1 |
| 2026-04-02 | 11 | 1 | 9 | 1 |
| 2026-04-03 | 11 | 1 | 9 | 1 |
| 2026-04-04 | 11 | 1 | 9 | 1 |
| 2026-04-05 | 11 | 1 | 9 | 1 |
| 2026-04-06 | 11 | 1 | 9 | 1 |
| 2026-04-07 | 11 | 1 | 9 | 1 |
| 2026-04-08 | 11 | 1 | 9 | 1 |
| 2026-04-09 | 11 | 1 | 9 | 1 |
| 2026-04-10 | 11 | 1 | 9 | 1 |
| 2026-04-11 | 11 | 1 | 9 | 1 |
| 2026-04-12 | 11 | 1 | 9 | 1 |
| 2026-04-13 | 11 | 1 | 9 | 1 |
| 2026-04-14 | 11 | 1 | 9 | 1 |
| 2026-04-15 | 11 | 1 | 9 | 1 |
| 2026-04-16 | 11 | 1 | 9 | 1 |
| 2026-04-17 | 11 | 1 | 9 | 1 |
| 2026-04-18 | 11 | 1 | 9 | 1 |
| 2026-04-19 | 11 | 1 | 9 | 1 |
| 2026-04-20 | 11 | 1 | 9 | 1 |
| 2026-04-21 | 11 | 1 | 9 | 1 |
| 2026-04-22 | 11 | 1 | 9 | 1 |
| 2026-04-23 | 11 | 1 | 9 | 1 |
| 2026-04-24 | 11 | 1 | 9 | 1 |
| 2026-04-25 | 11 | 1 | 9 | 1 |
| 2026-04-26 | 11 | 1 | 9 | 1 |


## March 13 audit after date fix

| event_date | market_slug | market_question | group_item_title | settlement_family | contract_event_type_v2 | event_set_v2 | event_condition_v2 | admissible_hko_event_contract_v2 | settlement_family_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-03-13 |  |  |  | ambiguous_or_unknown | unknown |  |  | False | Insufficient settlement-source evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-15corbelow | Will the highest temperature in Hong Kong be 15°C or below on March 13? | 15°C or below | Wunderground_or_airport | lower_tail_endpoint | (-infinity, 16) | T_HKO < 16 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-16c | Will the highest temperature in Hong Kong be 16°C on March 13? | 16°C | Wunderground_or_airport | interior_bin | [16, 17) | 16 <= T_HKO < 17 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-17c | Will the highest temperature in Hong Kong be 17°C on March 13? | 17°C | Wunderground_or_airport | interior_bin | [17, 18) | 17 <= T_HKO < 18 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-18c | Will the highest temperature in Hong Kong be 18°C on March 13? | 18°C | Wunderground_or_airport | interior_bin | [18, 19) | 18 <= T_HKO < 19 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-19c | Will the highest temperature in Hong Kong be 19°C on March 13? | 19°C | Wunderground_or_airport | interior_bin | [19, 20) | 19 <= T_HKO < 20 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-20c | Will the highest temperature in Hong Kong be 20°C on March 13? | 20°C | Wunderground_or_airport | interior_bin | [20, 21) | 20 <= T_HKO < 21 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-21c | Will the highest temperature in Hong Kong be 21°C on March 13? | 21°C | Wunderground_or_airport | interior_bin | [21, 22) | 21 <= T_HKO < 22 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-22c | Will the highest temperature in Hong Kong be 22°C on March 13? | 22°C | Wunderground_or_airport | interior_bin | [22, 23) | 22 <= T_HKO < 23 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |
| 2026-03-13 | highest-temperature-in-hong-kong-on-march-13-2026-23corhigher | Will the highest temperature in Hong Kong be 23°C or higher on March 13? | 23°C or higher | Wunderground_or_airport | upper_tail | [23, infinity) | T_HKO >= 23 | False | Wunderground/airport evidence detected without sufficient HKO evidence. |


## Admissible HKO contract-event universe preview

| event_date | market_slug | market_question | group_item_title | settlement_family | contract_event_type_v2 | event_set_v2 | event_condition_v2 | selected_yes_token_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-20corbelow | Will the highest temperature in Hong Kong be 20°C or below on April 1? | 20°C or below | HKO_Daily_Extract_one_decimal | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 8604720886787485019697790883292245503562985545875997741180261352304494220128 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 1? | 21°C | HKO_Daily_Extract_one_decimal | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 40014900626589044189029630768093662713815741737430235059361070842764241218823 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 1? | 22°C | HKO_Daily_Extract_one_decimal | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 55079827773872631729176930461884414860375524560638114135289382035970218663038 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 1? | 23°C | HKO_Daily_Extract_one_decimal | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 83841444489435774308014761014987456636927246644172209548916425298470168255910 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 1? | 24°C | HKO_Daily_Extract_one_decimal | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 44949916810529548120680678974005916291746611437060914085328650456191313099194 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 1? | 25°C | HKO_Daily_Extract_one_decimal | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 74029023981756759082197939119003286627001628189391619854668747272006096227673 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 1? | 26°C | HKO_Daily_Extract_one_decimal | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 43076841186972569954589188275745972187022313669271379429828637168322720934433 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 1? | 27°C | HKO_Daily_Extract_one_decimal | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 15286266942096997100441907272183828891275214701549879934850424172490056004762 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 1? | 28°C | HKO_Daily_Extract_one_decimal | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 2217105085674160947057305310232537454370298167764248642073346728367195238715 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 1? | 29°C | HKO_Daily_Extract_one_decimal | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 13757421407633171963826033095139937965738957582512295012829992103522849849893 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 1? | 30°C or higher | HKO_Daily_Extract_one_decimal | upper_tail | [30, infinity) | T_HKO >= 30 | 20796348205047967733869729627896331196596616742840951445748283819848266836944 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-20corbelow | Will the highest temperature in Hong Kong be 20°C or below on April 10? | 20°C or below | HKO_Daily_Extract_one_decimal | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 22949151863078752582196083265341890533083952581087552910627824170177285810469 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 10? | 21°C | HKO_Daily_Extract_one_decimal | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 54836983936980878212606421868210803097902568402169344278015434270494268497477 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 10? | 22°C | HKO_Daily_Extract_one_decimal | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 64601735238886796622927629959507020019160609939140331765301887751898128552410 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 10? | 23°C | HKO_Daily_Extract_one_decimal | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 27108372496993268654926442590603826923879365862633957505324227158731269160365 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 10? | 24°C | HKO_Daily_Extract_one_decimal | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 33920930266990684139171199131588879631620210162811979261259740749860755381977 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 10? | 25°C | HKO_Daily_Extract_one_decimal | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 41642465981386783567093252900415715824417450066807872070855509555051948550405 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 10? | 26°C | HKO_Daily_Extract_one_decimal | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 36850248312549903875364114577225516929899282555521479198145552785017591833115 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 10? | 27°C | HKO_Daily_Extract_one_decimal | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 88262719188573566470251670873242729419758093265490171670915320458063421254960 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 10? | 28°C | HKO_Daily_Extract_one_decimal | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 58956322473206871218357865379829554333961784487932969144570010590439148147860 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 10? | 29°C | HKO_Daily_Extract_one_decimal | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 114221833123908158105887372263604526651035188443468358054614096591140838124990 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 10? | 30°C or higher | HKO_Daily_Extract_one_decimal | upper_tail | [30, infinity) | T_HKO >= 30 | 21410421144675005956027138392042585861329063186102722742002484227225248573706 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-20corbelow | Will the highest temperature in Hong Kong be 20°C or below on April 11? | 20°C or below | HKO_Daily_Extract_one_decimal | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 99930559057710551029371876710342208093308728579790256394238027160576126928316 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 11? | 21°C | HKO_Daily_Extract_one_decimal | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 35879719803810768508611009685428510433959413848777763007743594550055939964018 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 11? | 22°C | HKO_Daily_Extract_one_decimal | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 12794935403832978907597576149827725505165804525101254774030044540293910764702 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 11? | 23°C | HKO_Daily_Extract_one_decimal | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 45708551049554033634350032853753718009141030316149444142960545499853150869971 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 11? | 24°C | HKO_Daily_Extract_one_decimal | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 71015926237664695819190069349633226964696933882377479362384588034762150762857 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 11? | 25°C | HKO_Daily_Extract_one_decimal | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 76783062408906872327708539394668637558494963875845953992950843706271674508706 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 11? | 26°C | HKO_Daily_Extract_one_decimal | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 115323362012133967493704850051604257679341456620719145674170295163942973964852 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 11? | 27°C | HKO_Daily_Extract_one_decimal | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 82778080487551185763334075014686932270091422590989760299055816825048372587854 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 11? | 28°C | HKO_Daily_Extract_one_decimal | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 73712799162388775159427291550890203203666102742449442433252430982779807784372 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 11? | 29°C | HKO_Daily_Extract_one_decimal | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 36143562334637565063970049458654785003551167675901869757774239018369416172106 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 11? | 30°C or higher | HKO_Daily_Extract_one_decimal | upper_tail | [30, infinity) | T_HKO >= 30 | 109670798574747185853429891426457365783370233096204837880877997939129390812751 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-20corbelow | Will the highest temperature in Hong Kong be 20°C or below on April 12? | 20°C or below | HKO_Daily_Extract_one_decimal | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 3132811527238312836263575614350430269923706889338590753719330223712337930127 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 12? | 21°C | HKO_Daily_Extract_one_decimal | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 95407826925914946336643405384501184976180641795062108114518961575661241514277 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 12? | 22°C | HKO_Daily_Extract_one_decimal | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 83662538222777860292389767984263238962567802565862327556198814758385298659816 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 12? | 23°C | HKO_Daily_Extract_one_decimal | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 71121808715390735640599054502498556858825656848951017405299226650847282719271 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 12? | 24°C | HKO_Daily_Extract_one_decimal | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 98056206886920395187063628887347265100972900393545487973318684899311317533554 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 12? | 25°C | HKO_Daily_Extract_one_decimal | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 100333235281670465080071734788280366907376455625839464815730335050100061014823 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 12? | 26°C | HKO_Daily_Extract_one_decimal | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 97222777706577848036961102988169046243923427138308254842001548461519760593317 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 12? | 27°C | HKO_Daily_Extract_one_decimal | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 108947040358953994279545569359514292704251194307921803827466610331634022413754 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 12? | 28°C | HKO_Daily_Extract_one_decimal | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 70877020873068393683668313520728986915239094865319327014117538689679159285073 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 12? | 29°C | HKO_Daily_Extract_one_decimal | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 82751711863239094682915780023947413340015851545585231421153333500088775544090 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 12? | 30°C or higher | HKO_Daily_Extract_one_decimal | upper_tail | [30, infinity) | T_HKO >= 30 | 42534833793131152787940940650462504736697545275448677657744052058459793675583 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-21corbelow | Will the highest temperature in Hong Kong be 21°C or below on April 13? | 21°C or below | HKO_Daily_Extract_one_decimal | lower_tail_endpoint | (-infinity, 22) | T_HKO < 22 | 97738960646174405599492671120798975234473473891362512867142859636452668830264 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 13? | 22°C | HKO_Daily_Extract_one_decimal | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 99293621040730549325231814820410610832547732350335020675054652276589174114357 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 13? | 23°C | HKO_Daily_Extract_one_decimal | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 89916957096136682132924917633634048025087476514235776938773942283886309924625 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 13? | 24°C | HKO_Daily_Extract_one_decimal | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 29080195822267444386165649910402364530099441450849530341043845767837347461061 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 13? | 25°C | HKO_Daily_Extract_one_decimal | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 115174939423224925168740068794692759585238904168976538381937391113259374197047 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 13? | 26°C | HKO_Daily_Extract_one_decimal | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 62099603512781579860973431102523682933703135157382610058975557882648191716596 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 13? | 27°C | HKO_Daily_Extract_one_decimal | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 34491913205221681463207044821744867829885565533570547467894534209265318155741 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 13? | 28°C | HKO_Daily_Extract_one_decimal | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 71620471481517480702473693260939429946258855782517416458483748133540376045129 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 13? | 29°C | HKO_Daily_Extract_one_decimal | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 22221388475281013860848007538942977086708290425322534714785647078464038861994 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-30c | Will the highest temperature in Hong Kong be 30°C on April 13? | 30°C | HKO_Daily_Extract_one_decimal | interior_bin | [30, 31) | 30 <= T_HKO < 31 | 101611528061924439869750543339188192462591036912302611110969858486926507729000 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-31corhigher | Will the highest temperature in Hong Kong be 31°C or higher on April 13? | 31°C or higher | HKO_Daily_Extract_one_decimal | upper_tail | [31, infinity) | T_HKO >= 31 | 14097171019495854480993041567939052141066319840357605075917546750909592860309 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-14-2026-20corbelow | Will the highest temperature in Hong Kong be 20°C or below on April 14? | 20°C or below | HKO_Daily_Extract_one_decimal | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 51196267787375220239249014120131355103310952687542254056429875066642467453212 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-14-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 14? | 21°C | HKO_Daily_Extract_one_decimal | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 66641798241165753211489903705246684777385274370533677356411419213464933438987 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-14-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 14? | 22°C | HKO_Daily_Extract_one_decimal | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 13370546282065697473371729572242097824239918684499475220284240858935920723041 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-14-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 14? | 23°C | HKO_Daily_Extract_one_decimal | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 113207127978191097885229707545567156326206459658678095990961358545827439600369 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-14-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 14? | 24°C | HKO_Daily_Extract_one_decimal | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 2328851494895717659133690267688489021646281569491861569206504975271186629895 |


## Interpretation

The v2 audit should be used as the repaired 18j output. The HKO Daily Extract one-decimal family is large enough to support the updated full Hong Kong contract-event framework. The main empirical universe should be built from the admissible HKO rows in `18j_v2_full_hko_contract_event_universe.csv`, not from the original preliminary 18j universe. Non-HKO rows, including Wunderground / airport rows, remain excluded from the headline Hong Kong analysis.
